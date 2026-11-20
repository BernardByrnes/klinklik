"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, apiRequest, newIdempotencyKey } from "../../../lib/api";
import { protectedQueryKey, useProtectedQueryKey } from "../../../lib/authority";
import { useSession } from "../../../lib/session";
import { IconBilling, IconCheckCircle } from "../../../components/icons";
import {
  Button,
  Card,
  CardTitleBar,
  EmptyState,
  ErrorBanner,
  PageHeader,
  StatusBadge,
  UnauthorisedState,
  formatDate,
} from "../../../components/ui";

type QueueItem = {
  id: string;
  medicine_name: string;
  quantity: string;
  state: string;
};

type QueueRow = {
  prescription_id: string;
  patient_name: string;
  patient_no: string;
  prescribed_at: string;
  item_count: number;
  state: string;
  dispensed_count: number;
  age_days: number;
  items: QueueItem[];
  claim_holder_id: string | null;
  claim_holder_name: string | null;
  resumable_dispense_id: string | null;
};

type CounsellingRow = {
  dispense_id: string;
  patient_name: string;
  line_count: number;
  confirmed_at: string;
  counselling_recorded: boolean;
};

type Queue = {
  active: QueueRow[];
  partially_dispensed: QueueRow[];
  uncollected: QueueRow[];
  uncollected_window_days: number;
  counselling: CounsellingRow[];
};

type PharmacyStep = "claim" | "prepare" | "confirm";
type PharmacyIntent = {
  prescriptionId: string;
  lines: Array<{ prescription_item_id: string; quantity: string }>;
  keys: { claim: string; prepare: string; confirm: string };
  provisionalId: string | null;
  step: PharmacyStep;
};

type ReviewLine = {
  id: string;
  prescribed_medicine_name: string | null;
  prescribed_quantity: string | null;
  dose_amount: string | null;
  dose_unit: string | null;
  route: string | null;
  frequency: string | null;
  duration_value: number | null;
  duration_unit: string | null;
  instructions: string | null;
  product_name: string;
  batch_no: string;
  expiry_date: string;
  quantity: string;
  unit_price: string;
  amount: string;
  version: number;
};

type DispenseReview = {
  id: string;
  prescription_id: string | null;
  patient_name: string | null;
  status: string;
  total: string;
  currency: string;
  claim_holder_name: string | null;
  allergy: { status?: string; active_allergies?: Array<{ substance: string; reaction: string }> } | null;
  eligible: boolean;
  blocked_reason: string | null;
  lines: ReviewLine[];
};

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function intentKey(organisationId: string | null, facilityId: string | null, userId: string | null, prescriptionId: string) {
  return `pharmacy-intent:${organisationId ?? ""}:${facilityId ?? ""}:${userId ?? ""}:${prescriptionId}`;
}

function loadIntent(key: string): PharmacyIntent | null {
  const raw = sessionStorage.getItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PharmacyIntent;
  } catch {
    sessionStorage.removeItem(key);
    return null;
  }
}

function Row({
  row,
  action,
  note,
}: {
  row: QueueRow;
  action?: React.ReactNode;
  note?: string;
}) {
  return (
    <li className="px-3.5 py-2.5 text-[12.5px]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-ink">
          {row.patient_name}
          <span className="ml-1 font-medium text-muted">{row.patient_no}</span>
        </span>
        <span className="flex items-center gap-2">
          <StatusBadge tone="neutral">{row.state}</StatusBadge>
        </span>
      </div>
      <p className="mt-1 text-secondary">
        Prescribed {formatDate(row.prescribed_at)} · {row.item_count} item
        {row.item_count === 1 ? "" : "s"}
        {note ? ` · ${note}` : ""}
      </p>
      <ul className="mt-1 space-y-0.5 text-secondary">
        {row.items.map((item) => (
          <li key={item.id}>
            {item.medicine_name} · {item.quantity} · {item.state}
          </li>
        ))}
      </ul>
      {action ? <div className="mt-2">{action}</div> : null}
    </li>
  );
}

export default function PharmacyPage() {
  const { can, session, currentFacility } = useSession();
  const queryClient = useQueryClient();
  const organisationId = session?.organisation.id ?? null;
  const facilityId = currentFacility?.id ?? null;
  const userId = session?.user.id ?? null;
  const queueKey = useProtectedQueryKey("pharmacy-queue");
  const queue = useQuery({
    queryKey: queueKey,
    queryFn: () => apiRequest<Queue>("/api/v1/pharmacy/queue/"),
    enabled: can("pharmacy.queue.view"),
  });
  const [intent, setIntent] = useState<PharmacyIntent | null>(null);
  const [error, setError] = useState("");
  const [finalConfirmation, setFinalConfirmation] = useState("");
  const reviewRef = useRef<HTMLDivElement | null>(null);

  const reviewKey = useProtectedQueryKey(
    "pharmacy-dispense-review",
    intent?.provisionalId ?? "",
  );
  const review = useQuery({
    queryKey: reviewKey,
    queryFn: () =>
      apiRequest<DispenseReview>(`/api/v1/pharmacy/dispenses/${intent!.provisionalId}/`),
    enabled: Boolean(intent?.provisionalId) && intent?.step === "confirm",
  });

  useEffect(() => {
    if (review.data && reviewRef.current) reviewRef.current.focus();
  }, [review.data]);

  const refreshQueue = () => {
    void queryClient.invalidateQueries({ queryKey: protectedQueryKey("pharmacy-queue") });
  };

  const storeIntent = (next: PharmacyIntent | null) => {
    setIntent(next);
    if (!next) return;
    sessionStorage.setItem(
      intentKey(organisationId, facilityId, userId, next.prescriptionId),
      JSON.stringify(next),
    );
  };

  const clearIntent = (prescriptionId?: string) => {
    if (prescriptionId) sessionStorage.removeItem(intentKey(organisationId, facilityId, userId, prescriptionId));
    setIntent(null);
  };

  const handleError = (reason: unknown, current: PharmacyIntent) => {
    const definite =
      reason instanceof ApiRequestError &&
      reason.status < 500 &&
      reason.status !== 408 &&
      reason.status !== 429;
    if (definite) {
      clearIntent(current.prescriptionId);
      refreshQueue();
      setError(errorMessage(reason));
      return;
    }
    setError("The pharmacy outcome is uncertain. Retry the same step after checking the queue.");
  };

  const claim = useMutation({
    mutationFn: (current: PharmacyIntent) =>
      apiRequest(`/api/v1/pharmacy/prescriptions/${current.prescriptionId}/claim/`, {
        method: "POST",
        headers: { "Idempotency-Key": current.keys.claim },
        body: JSON.stringify({}),
      }),
    onSuccess: (_result, current) => {
      storeIntent({ ...current, step: "prepare" });
      setError("");
      refreshQueue();
    },
    onError: (reason, current) => handleError(reason, current),
  });

  const prepare = useMutation({
    mutationFn: (current: PharmacyIntent) =>
      apiRequest<{ id: string }>(
        `/api/v1/pharmacy/prescriptions/${current.prescriptionId}/dispenses/`,
        {
          method: "POST",
          headers: { "Idempotency-Key": current.keys.prepare },
          body: JSON.stringify({ lines: current.lines }),
        }
      ),
    onSuccess: (result, current) => {
      storeIntent({ ...current, provisionalId: result.id, step: "confirm" });
      setError("");
      refreshQueue();
    },
    onError: (reason, current) => handleError(reason, current),
  });

  const confirm = useMutation({
    mutationFn: (current: PharmacyIntent) =>
      apiRequest(`/api/v1/pharmacy/dispenses/${current.provisionalId}/confirm/`, {
        method: "POST",
        headers: { "Idempotency-Key": current.keys.confirm },
        body: JSON.stringify({}),
      }),
    onSuccess: (_result, current) => {
      clearIntent(current.prescriptionId);
      setError("");
      setFinalConfirmation(`${queue.data?.active.find((row) => row.prescription_id === current.prescriptionId)?.patient_name ?? "Patient"} · dispense confirmed`);
      refreshQueue();
    },
    onError: (reason, current) => handleError(reason, current),
  });

  const startClaim = (row: QueueRow) => {
    const lines = row.items
      .filter((item) => item.state === "PENDING")
      .map((item) => ({ prescription_item_id: item.id, quantity: item.quantity }));
    if (!lines.length) {
      setError("This prescription has no pending item to dispense.");
      return;
    }
    const next: PharmacyIntent = {
      prescriptionId: row.prescription_id,
      lines,
      keys: {
        claim: newIdempotencyKey("pharmacy-claim"),
        prepare: newIdempotencyKey("pharmacy-prepare"),
        confirm: newIdempotencyKey("pharmacy-confirm"),
      },
      provisionalId: null,
      step: "claim",
    };
    setFinalConfirmation("");
    storeIntent(next);
    claim.mutate(next);
  };

  const resume = (row: QueueRow) => {
    const existing = loadIntent(intentKey(organisationId, facilityId, userId, row.prescription_id));
    const next: PharmacyIntent = existing ?? {
      prescriptionId: row.prescription_id,
      lines: row.items
        .filter((item) => item.state === "PENDING")
        .map((item) => ({ prescription_item_id: item.id, quantity: item.quantity })),
      keys: {
        claim: newIdempotencyKey("pharmacy-claim"),
        prepare: newIdempotencyKey("pharmacy-prepare"),
        confirm: newIdempotencyKey("pharmacy-confirm"),
      },
      provisionalId: row.resumable_dispense_id,
      step: "confirm",
    };
    storeIntent({ ...next, provisionalId: row.resumable_dispense_id, step: "confirm" });
    setFinalConfirmation("");
    setError("");
  };

  const retry = () => {
    if (!intent) return;
    if (intent.step === "claim") claim.mutate(intent);
    else if (intent.step === "prepare") prepare.mutate(intent);
    else confirm.mutate(intent);
  };

  if (!can("pharmacy.queue.view")) {
    return <UnauthorisedState capability="pharmacy.queue.view" />;
  }

  const busy = claim.isPending || prepare.isPending || confirm.isPending;

  return (
    <>
      <PageHeader
        title="Pharmacy"
        subtitle="Claim, prepare, review and hand over prescribed medicine with one audited outcome."
      />
      {error ? <ErrorBanner message={error} onDismiss={() => setError("")} /> : null}
      {intent && (claim.isError || prepare.isError || confirm.isError) ? (
        <Button variant="secondary" disabled={busy} onClick={retry}>
          Retry uncertain pharmacy step
        </Button>
      ) : null}
      {finalConfirmation ? (
        <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink" role="status">
          <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
          {finalConfirmation}
        </p>
      ) : null}

      {review.data && intent?.step === "confirm" ? (
        <div
          ref={reviewRef}
          role="region"
          aria-label="Dispense review"
          tabIndex={-1}
          className="rounded-[14px] border border-line bg-white p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-[13px] font-bold text-ink">Dispense review</h2>
              <p className="mt-1 text-[12px] text-secondary">
                {review.data.patient_name} · {review.data.status} · provisional {review.data.id}
              </p>
            </div>
            <StatusBadge tone={review.data.eligible ? "teal" : "pink"}>
              {review.data.eligible ? "ELIGIBLE" : review.data.blocked_reason ?? "BLOCKED"}
            </StatusBadge>
          </div>
          {review.data.allergy?.active_allergies?.length ? (
            <p className="mt-3 rounded-[12px] bg-accent-orange-soft px-3 py-2 text-[12px] font-medium text-ink">
              Allergies: {review.data.allergy.active_allergies.map((item) => `${item.substance} (${item.reaction})`).join(", ")}
            </p>
          ) : null}
          <ul className="mt-3 divide-y divide-line-soft">
            {review.data.lines.map((line) => (
              <li key={line.id} className="py-2.5 text-[12.5px]">
                <p className="font-semibold text-ink">
                  {line.prescribed_medicine_name ?? line.product_name} · {line.quantity} {line.dose_unit ?? ""}
                </p>
                <p className="mt-0.5 text-secondary">
                  {line.product_name} · batch {line.batch_no} · exp {line.expiry_date} · {line.route} · {line.frequency}
                </p>
                <p className="mt-0.5 text-secondary">
                  Unit price {line.unit_price} · amount {line.amount} · v{line.version}
                </p>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[13px] font-bold text-ink">Total {review.data.total} {review.data.currency}</p>
          <div className="mt-3">
            <Button
              disabled={!review.data.eligible || busy}
              onClick={() => intent && confirm.mutate(intent)}
            >
              {confirm.isPending ? "Confirming…" : "Confirm handover"}
            </Button>
            {!review.data.eligible ? (
              <p className="mt-1 text-[12px] text-secondary">
                Handover is unavailable while {review.data.blocked_reason ?? "the allocation is blocked"}.
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      {intent && intent.step === "prepare" ? (
        <Card>
          <CardTitleBar title="Prepare dispense" />
          <p className="px-5 py-4 text-[12.5px] text-secondary">
            Claim held for {intent.prescriptionId}. Prepare the committed allocation from the server.
          </p>
          <div className="px-5 pb-4">
            <Button disabled={busy} onClick={() => prepare.mutate(intent)}>
              {prepare.isPending ? "Preparing…" : "Prepare dispense"}
            </Button>
          </div>
        </Card>
      ) : null}

      {queue.isLoading ? (
        <Card>
          <div className="px-5 py-6 text-[12.5px] font-medium text-secondary" role="status" aria-busy="true">
            Loading the pharmacy queue…
          </div>
        </Card>
      ) : queue.isError ? (
        <Card>
          <div className="px-5 py-6 text-[12.5px] font-medium text-ink" role="alert">
            The pharmacy queue could not be loaded.
          </div>
        </Card>
      ) : queue.data ? (
        <section className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
          <Card>
            <CardTitleBar title={`To dispense (${queue.data.active.length})`} />
            {queue.data.active.length ? (
              <ul className="divide-y divide-line-soft">
                {queue.data.active.map((row) => {
                  const claimedByOther = Boolean(
                    row.claim_holder_id && row.claim_holder_id !== userId
                  );
                  return (
                    <Row
                      key={row.prescription_id}
                      row={row}
                      note={row.claim_holder_name ? ` · claimed by ${row.claim_holder_name}` : undefined}
                      action={
                        claimedByOther ? (
                          <p className="text-[12.5px] text-secondary">In preparation by another pharmacist.</p>
                        ) : row.resumable_dispense_id ? (
                          <Button variant="secondary" disabled={busy} onClick={() => resume(row)}>
                            Resume preparation
                          </Button>
                        ) : (
                          <Button variant="secondary" disabled={busy} onClick={() => startClaim(row)}>
                            Claim prescription
                          </Button>
                        )
                      }
                    />
                  );
                })}
              </ul>
            ) : (
              <EmptyState icon={<IconBilling className="h-5 w-5" />} title="No prescriptions waiting." hint="Signed prescriptions appear here for dispensing." />
            )}
          </Card>

          <Card>
            <CardTitleBar title={`Partially dispensed (${queue.data.partially_dispensed.length})`} />
            {queue.data.partially_dispensed.length ? (
              <ul className="divide-y divide-line-soft">
                {queue.data.partially_dispensed.map((row) => <Row key={row.prescription_id} row={row} />)}
              </ul>
            ) : (
              <p className="px-5 py-4 text-[12.5px] font-medium text-secondary">No partially dispensed prescriptions.</p>
            )}
          </Card>

          <Card>
            <CardTitleBar title={`Uncollected over ${queue.data.uncollected_window_days} days (${queue.data.uncollected.length})`} />
            {queue.data.uncollected.length ? (
              <ul className="divide-y divide-line-soft">
                {queue.data.uncollected.map((row) => <Row key={row.prescription_id} row={row} note={`${row.age_days} days old`} />)}
              </ul>
            ) : (
              <p className="px-5 py-4 text-[12.5px] font-medium text-secondary">No uncollected prescriptions.</p>
            )}
          </Card>

          <Card>
            <CardTitleBar title={`Counselling follow-up (${queue.data.counselling.length})`} />
            {queue.data.counselling.length ? (
              <ul className="divide-y divide-line-soft">
                {queue.data.counselling.map((row) => (
                  <li key={row.dispense_id} className="px-3.5 py-2.5 text-[12.5px]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-ink">{row.patient_name}</span>
                      <StatusBadge tone="pink">COUNSELLING</StatusBadge>
                    </div>
                    <p className="mt-1 text-secondary">
                      {row.line_count} line{row.line_count === 1 ? "" : "s"} · {formatDate(row.confirmed_at)}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-5 py-4 text-[12.5px] font-medium text-secondary">No dispenses awaiting counselling follow-up.</p>
            )}
          </Card>
        </section>
      ) : null}
    </>
  );
}
