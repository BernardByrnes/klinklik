"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest, newIdempotencyKey } from "../../../lib/api";
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

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
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
  const { can } = useSession();
  const queryClient = useQueryClient();
  const queueKey = useProtectedQueryKey("pharmacy-queue");
  const queue = useQuery({
    queryKey: queueKey,
    queryFn: () => apiRequest<Queue>("/api/v1/pharmacy/queue/"),
    enabled: can("pharmacy.queue.view"),
  });

  const dispense = useMutation({
    mutationFn: async (row: QueueRow) => {
      await apiRequest(`/api/v1/pharmacy/prescriptions/${row.prescription_id}/claim/`, {
        method: "POST",
        headers: { "Idempotency-Key": newIdempotencyKey("pharmacy-claim") },
        body: JSON.stringify({}),
      });
      const pending = row.items.filter((item) => item.state === "PENDING");
      if (!pending.length) {
        throw new Error("This prescription has no pending item to dispense.");
      }
      const prepared = await apiRequest<{ id: string }>(
        `/api/v1/pharmacy/prescriptions/${row.prescription_id}/dispenses/`,
        {
          method: "POST",
          headers: { "Idempotency-Key": newIdempotencyKey("pharmacy-prepare") },
          body: JSON.stringify({
            lines: pending.map((item) => ({
              prescription_item_id: item.id,
              quantity: item.quantity,
            })),
          }),
        }
      );
      return apiRequest(`/api/v1/pharmacy/dispenses/${prepared.id}/confirm/`, {
        method: "POST",
        headers: { "Idempotency-Key": newIdempotencyKey("pharmacy-confirm") },
        body: JSON.stringify({}),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("pharmacy-queue") });
    },
  });

  if (!can("pharmacy.queue.view")) {
    return <UnauthorisedState capability="pharmacy.queue.view" />;
  }

  return (
    <>
      <PageHeader
        title="Pharmacy"
        subtitle="Dispense prescribed medicine from non-expired stock and charge it in the same handover."
      />
      {dispense.isError ? <ErrorBanner message={errorMessage(dispense.error)} /> : null}
      {dispense.isSuccess ? (
        <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
          <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
          Dispense handed over, stock moved and the charge recorded.
        </p>
      ) : null}

      {queue.isLoading ? (
        <Card>
          <div
            className="px-5 py-6 text-[12.5px] font-medium text-secondary"
            role="status"
            aria-busy="true"
          >
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
                {queue.data.active.map((row) => (
                  <Row
                    key={row.prescription_id}
                    row={row}
                    action={
                      <Button
                        variant="secondary"
                        disabled={dispense.isPending}
                        onClick={() => dispense.mutate(row)}
                      >
                        Dispense &amp; charge
                      </Button>
                    }
                  />
                ))}
              </ul>
            ) : (
              <EmptyState
                icon={<IconBilling className="h-5 w-5" />}
                title="No prescriptions waiting."
                hint="Signed prescriptions appear here for dispensing."
              />
            )}
          </Card>

          <Card>
            <CardTitleBar
              title={`Partially dispensed (${queue.data.partially_dispensed.length})`}
            />
            {queue.data.partially_dispensed.length ? (
              <ul className="divide-y divide-line-soft">
                {queue.data.partially_dispensed.map((row) => (
                  <Row key={row.prescription_id} row={row} />
                ))}
              </ul>
            ) : (
              <p className="px-5 py-4 text-[12.5px] font-medium text-secondary">
                No partially dispensed prescriptions.
              </p>
            )}
          </Card>

          <Card>
            <CardTitleBar
              title={`Uncollected over ${queue.data.uncollected_window_days} days (${queue.data.uncollected.length})`}
            />
            {queue.data.uncollected.length ? (
              <ul className="divide-y divide-line-soft">
                {queue.data.uncollected.map((row) => (
                  <Row
                    key={row.prescription_id}
                    row={row}
                    note={`${row.age_days} days old`}
                  />
                ))}
              </ul>
            ) : (
              <p className="px-5 py-4 text-[12.5px] font-medium text-secondary">
                No uncollected prescriptions.
              </p>
            )}
          </Card>

          <Card>
            <CardTitleBar
              title={`Counselling follow-up (${queue.data.counselling.length})`}
            />
            {queue.data.counselling.length ? (
              <ul className="divide-y divide-line-soft">
                {queue.data.counselling.map((row) => (
                  <li key={row.dispense_id} className="px-3.5 py-2.5 text-[12.5px]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-ink">{row.patient_name}</span>
                      <StatusBadge tone="pink">COUNSELLING</StatusBadge>
                    </div>
                    <p className="mt-1 text-secondary">
                      {row.line_count} line{row.line_count === 1 ? "" : "s"} ·{" "}
                      {formatDate(row.confirmed_at)}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-5 py-4 text-[12.5px] font-medium text-secondary">
                No dispenses awaiting counselling follow-up.
              </p>
            )}
          </Card>
        </section>
      ) : null}
    </>
  );
}
