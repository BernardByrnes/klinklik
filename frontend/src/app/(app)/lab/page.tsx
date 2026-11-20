"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest, newIdempotencyKey } from "../../../lib/api";
import {
  getAuthoritySnapshot,
  isCurrentAuthority,
  protectedQueryKey,
  useProtectedQueryKey,
} from "../../../lib/authority";
import { useConnectivity } from "../../../lib/connectivity";
import { isIntentActive, registerIntent, resolveIntent } from "../../../lib/intent-registry";
import { shouldRegisterIntent } from "../../../lib/recovery";
import { useSession } from "../../../lib/session";
import { IconBilling } from "../../../components/icons";
import {
  Button,
  Card,
  CardTitleBar,
  EmptyState,
  ErrorBanner,
  StatusBadge,
  UnauthorisedState,
  formatDate,
} from "../../../components/ui";

type LabAnalyte = {
  id: string;
  code: string;
  name: string;
  unit: string;
  result_type: string;
  sequence: number;
  coded_options: string[];
  range_low: string | null;
  range_high: string | null;
};

type ResultValue = {
  analyte_id: string;
  code: string;
  name: string;
  unit: string;
  value: string | null;
  flag: string;
  range_low?: string | null;
  range_high?: string | null;
  not_done?: boolean;
};

type LabRow = {
  item_id: string;
  order_id: string;
  test_id: string;
  patient_name: string;
  patient_no: string;
  test_name: string;
  priority: string;
  state: string;
  ordered_by: string;
  ordered_by_name: string;
  ordered_at: string;
  elapsed_minutes: number;
  clinical_notes: string;
  specimen_id: string;
  urgency: boolean;
  rejection_reason: string;
  recollection_count: number;
  version_no: number | null;
};

type Pagination = { limit: number; offset: number; count: number; has_more: boolean };

type Worklist = {
  awaiting_payment: LabRow[];
  to_collect: LabRow[];
  in_bench: LabRow[];
  to_verify: LabRow[];
  rejected: LabRow[];
  released: LabRow[];
  pagination: Pagination;
};

type ResultDetail = {
  item_id: string;
  test_name: string;
  specimen_id: string | null;
  state: string;
  result_state: string | null;
  priority: string;
  version_no: number | null;
  analytes: LabAnalyte[];
  values: ResultValue[];
  comments: string;
  entered_by: string | null;
  entered_at: string | null;
  released_at: string | null;
  verified_by: string | null;
};

type SelectedItem = { itemId: string; mode: "entry" | "review" };

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function Row({ row, action }: { row: LabRow; action?: React.ReactNode }) {
  return (
    <li className="px-3.5 py-2.5 text-[12.5px]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-ink">
          {row.test_name} · {row.patient_name}
          <span className="ml-1 font-medium text-muted">{row.patient_no}</span>
        </span>
        <span className="flex items-center gap-2">
          {row.urgency ? <StatusBadge tone="pink">URGENT</StatusBadge> : null}
          <StatusBadge tone="neutral">{row.state}</StatusBadge>
        </span>
      </div>
      <p className="mt-1 text-secondary">
        Ordered {formatDate(row.ordered_at)} · {row.elapsed_minutes} min ago
        {row.ordered_by_name ? ` · ${row.ordered_by_name}` : ""}
        {row.specimen_id ? ` · specimen ${row.specimen_id}` : ""}
        {row.clinical_notes ? ` · notes: ${row.clinical_notes}` : ""}
      </p>
      {row.rejection_reason ? (
        <p className="mt-1 font-medium text-ink">Reason: {row.rejection_reason}</p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </li>
  );
}

export default function LabPage() {
  const online = useConnectivity().online;
  const { can } = useSession();
  const canEnter = can("lab.result.entry");
  const canVerify = can("lab.result.verify");
  const canReadWorklist = canEnter || canVerify;
  const queryClient = useQueryClient();
  const labIntentRefs = useRef<Record<string, string>>({});
  const [selected, setSelected] = useState<SelectedItem | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [notDone, setNotDone] = useState<Record<string, boolean>>({});
  const [comments, setComments] = useState("");
  const [notice, setNotice] = useState("");

  const worklistKey = useProtectedQueryKey("lab-worklist");
  const worklist = useInfiniteQuery({
    queryKey: worklistKey,
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      apiRequest<Worklist>(`/api/v1/lab/worklist/?limit=50&offset=${pageParam}`),
    getNextPageParam: (last) =>
      last.pagination.has_more
        ? last.pagination.offset + last.pagination.limit
        : undefined,
    enabled: canReadWorklist,
  });

  const sections = useMemo(() => {
    const merged: Worklist = {
      awaiting_payment: [],
      to_collect: [],
      in_bench: [],
      to_verify: [],
      rejected: [],
      released: [],
      pagination: { limit: 50, offset: 0, count: 0, has_more: false },
    };
    for (const page of worklist.data?.pages ?? []) {
      for (const name of [
        "awaiting_payment", "to_collect", "in_bench", "to_verify", "rejected", "released",
      ] as const) {
        merged[name].push(...page[name]);
      }
      merged.pagination = page.pagination;
    }
    return merged;
  }, [worklist.data]);

  const detailKey = useProtectedQueryKey("lab-item-detail", selected?.itemId ?? "");
  const detail = useQuery({
    queryKey: detailKey,
    queryFn: () => apiRequest<ResultDetail>(`/api/v1/lab/items/${selected!.itemId}/detail/`),
    enabled: Boolean(selected),
  });

  const fields = useMemo(() => {
    if (!detail.data) return [];
    if (detail.data.values.length) {
      return detail.data.values.map((value) => ({
        id: value.analyte_id,
        name: value.name,
        unit: value.unit,
        range_low: value.range_low ?? null,
        range_high: value.range_high ?? null,
        flag: value.flag,
        value: value.value,
        not_done: Boolean(value.not_done),
      }));
    }
    return detail.data.analytes.map((analyte) => ({
      id: analyte.id,
      name: analyte.name,
      unit: analyte.unit,
      range_low: analyte.range_low,
      range_high: analyte.range_high,
      flag: "NONE",
      value: null,
      not_done: false,
    }));
  }, [detail.data]);

  useEffect(() => {
    if (!detail.data || selected?.mode !== "entry") return;
    setFormValues(
      Object.fromEntries(fields.map((field) => [field.id, field.value ?? ""])),
    );
    setNotDone(
      Object.fromEntries(fields.map((field) => [field.id, field.not_done])),
    );
    setComments(detail.data.comments ?? "");
  }, [detail.data, selected?.mode, fields]);

  const invalidateLab = () => {
    void queryClient.invalidateQueries({ queryKey: protectedQueryKey("lab-worklist") });
    if (selected) {
      void queryClient.invalidateQueries({
        queryKey: protectedQueryKey("lab-item-detail", selected.itemId),
      });
    }
  };

  const registerLabIntent = (
    operation: string,
    authority: ReturnType<typeof getAuthoritySnapshot> | undefined,
    retry: () => Promise<void>,
  ) => {
    if (!isIntentActive(labIntentRefs.current[operation])) {
      delete labIntentRefs.current[operation];
    }
    labIntentRefs.current[operation] = registerIntent({
      operation,
      target: "laboratory-item",
      authority,
      retry,
    });
  };
  const resolveLabIntent = (operation: string) => {
    resolveIntent(labIntentRefs.current[operation]);
    delete labIntentRefs.current[operation];
  };

  const collect = useMutation({
    mutationFn: (input: { itemId: string; key: string }) =>
      apiRequest(`/api/v1/lab/items/${input.itemId}/collect/`, {
        method: "POST",
        headers: { "Idempotency-Key": input.key },
        body: JSON.stringify({}),
      }),
    onMutate: () => getAuthoritySnapshot(),
    onSuccess: () => {
      resolveLabIntent("lab-collect");
      setNotice("Sample recorded.");
      invalidateLab();
    },
    onError: (reason, input, authority) => {
      if (!shouldRegisterIntent(reason)) resolveLabIntent("lab-collect");
      else {
        registerLabIntent("lab-collect", authority, async () => {
          if (!authority || !isCurrentAuthority(authority)) return;
          await collect.mutateAsync(input).catch(() => undefined);
        });
      }
    },
  });

  const save = useMutation({
    mutationFn: ({
      itemId,
      key,
      values,
    }: {
      itemId: string;
      key: string;
      values: Array<Record<string, unknown>>;
    }) =>
      apiRequest(`/api/v1/lab/items/${itemId}/results/`, {
        method: "PATCH",
        headers: { "Idempotency-Key": key },
        body: JSON.stringify({ values, comments, complete: true }),
      }),
    onMutate: () => getAuthoritySnapshot(),
    onSuccess: () => {
      resolveLabIntent("lab-result-save");
      setSelected(null);
      setNotice("Results saved for verification.");
      invalidateLab();
    },
    onError: (reason, input, authority) => {
      if (!shouldRegisterIntent(reason)) resolveLabIntent("lab-result-save");
      else {
        registerLabIntent("lab-result-save", authority, async () => {
          if (!authority || !isCurrentAuthority(authority)) return;
          await save.mutateAsync(input).catch(() => undefined);
        });
      }
    },
  });

  const release = useMutation({
    mutationFn: ({
      itemId,
      key,
      expectedVersion,
    }: {
      itemId: string;
      key: string;
      expectedVersion: number;
    }) =>
      apiRequest(`/api/v1/lab/items/${itemId}/release/`, {
        method: "POST",
        headers: { "Idempotency-Key": key },
        body: JSON.stringify({ expected_version: expectedVersion }),
      }),
    onMutate: () => getAuthoritySnapshot(),
    onSuccess: () => {
      resolveLabIntent("lab-release");
      setSelected(null);
      setNotice("Result released to the ordering clinician.");
      invalidateLab();
    },
    onError: (reason, input, authority) => {
      if (!shouldRegisterIntent(reason)) resolveLabIntent("lab-release");
      else {
        registerLabIntent("lab-release", authority, async () => {
          if (!authority || !isCurrentAuthority(authority)) return;
          await release.mutateAsync(input).catch(() => undefined);
        });
      }
    },
  });

  const mutationError = collect.error ?? save.error ?? release.error;
  const busy = collect.isPending || save.isPending || release.isPending;

  if (!canReadWorklist) {
    return <UnauthorisedState capability="lab.result.entry or lab.result.verify" />;
  }

  const startCollect = (itemId: string) => {
    collect.mutate({ itemId, key: newIdempotencyKey(`lab-collect-${itemId}`) });
  };

  const openEntry = (row: LabRow) => {
    setSelected({ itemId: row.item_id, mode: "entry" });
    setFormValues({});
    setNotDone({});
    setComments("");
  };

  const openReview = (row: LabRow) => {
    setSelected({ itemId: row.item_id, mode: "review" });
  };

  const submitResults = () => {
    if (!selected || !detail.data) return;
    const values = fields.map((field) => ({
      analyte_id: field.id,
      not_done: Boolean(notDone[field.id]),
      value: notDone[field.id] ? null : formValues[field.id]?.trim(),
      comment: "",
    }));
    save.mutate({
      itemId: selected.itemId,
      key: newIdempotencyKey(`lab-result-save-${selected.itemId}`),
      values,
    });
  };

  const moveFocus = (event: React.KeyboardEvent<HTMLInputElement>, index: number) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const next = fields[index + 1];
    if (next) document.getElementById(`lab-analyte-${next.id}`)?.focus();
  };

  return (
    <>
      <div className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-[20px] font-bold text-ink">Laboratory</h1>
            <p className="mt-1 text-[12.5px] text-secondary">
              Collect samples, enter structured values and release only verified work.
            </p>
          </div>
          {selected ? (
            <Button variant="secondary" onClick={() => setSelected(null)}>
              Close detail
            </Button>
          ) : null}
        </div>

        {notice ? <p role="status" className="rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">{notice}</p> : null}
        {mutationError ? <ErrorBanner message={errorMessage(mutationError)} /> : null}

        {selected ? (
          <Card>
            <CardTitleBar
              title={
                selected.mode === "entry"
                  ? `Enter results · ${detail.data?.test_name ?? "Loading…"}`
                  : `Review and release · ${detail.data?.test_name ?? "Loading…"}`
              }
            />
            {detail.isLoading ? (
              <p className="px-5 py-6 text-[12.5px] text-secondary" role="status" aria-busy="true">
                Loading the result detail…
              </p>
            ) : detail.isError ? (
              <p className="px-5 py-6 text-[12.5px] text-ink" role="alert">
                The result detail could not be loaded.
              </p>
            ) : detail.data ? (
              <div className="space-y-4 px-5 py-4">
                <div className="flex flex-wrap items-center gap-3 text-[12px] text-secondary">
                  {selected.mode === "review" ? (
                    <Button variant="small-secondary" onClick={() => void detail.refetch()}>
                      Refresh result
                    </Button>
                  ) : null}
                  <span>Version {detail.data.version_no ?? "—"}</span>
                  <span>Entered by {detail.data.entered_by ?? "—"}</span>
                  <span>{detail.data.entered_at ? formatDate(detail.data.entered_at) : ""}</span>
                  {detail.data.released_at ? (
                    <span>Released {formatDate(detail.data.released_at)} by {detail.data.verified_by ?? "—"}</span>
                  ) : null}
                </div>
                {selected.mode === "entry" ? (
                  <div className="grid gap-3">
                    {fields.map((field, index) => (
                      <div key={field.id} className="grid gap-1.5 rounded-[12px] border border-line-soft px-3 py-2.5">
                        <label htmlFor={`lab-analyte-${field.id}`} className="text-[12.5px] font-semibold text-ink">
                          {field.name} ({field.unit})
                        </label>
                        <p className="text-[11.5px] text-muted">
                          {field.range_low ?? "—"} – {field.range_high ?? "—"} {field.unit}
                        </p>
                        <div className="flex items-center gap-3">
                          <input
                            id={`lab-analyte-${field.id}`}
                            className="w-40 rounded-[10px] border border-line px-3 py-2 text-[12.5px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                            inputMode="decimal"
                            value={formValues[field.id] ?? ""}
                            disabled={Boolean(notDone[field.id]) || busy}
                            onChange={(event) =>
                              setFormValues((current) => ({
                                ...current,
                                [field.id]: event.target.value,
                              }))
                            }
                            onKeyDown={(event) => moveFocus(event, index)}
                          />
                          <label className="flex items-center gap-1.5 text-[12px] text-secondary">
                            <input
                              type="checkbox"
                              checked={Boolean(notDone[field.id])}
                              disabled={busy}
                              onChange={(event) =>
                                setNotDone((current) => ({
                                  ...current,
                                  [field.id]: event.target.checked,
                                }))
                              }
                            />
                            Not done
                          </label>
                        </div>
                      </div>
                    ))}
                    <label htmlFor="lab-comments" className="text-[12.5px] font-semibold text-ink">
                      Overall comment
                      <textarea
                        id="lab-comments"
                        className="mt-1.5 w-full rounded-[12px] border border-line px-3 py-2 text-[12.5px]"
                        value={comments}
                        disabled={busy}
                        onChange={(event) => setComments(event.target.value)}
                      />
                    </label>
                    <div>
                      <Button disabled={busy || !online} onClick={submitResults}>
                        {save.isPending ? "Saving…" : "Save results"}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <ul className="divide-y divide-line-soft rounded-[14px] border border-line-soft">
                      {detail.data.values.map((value) => (
                        <li key={value.analyte_id} className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 text-[12.5px]">
                          <span className="font-medium text-ink">
                            {value.name} · {value.value ?? "Not done"} {value.unit}
                          </span>
                          <span className="flex items-center gap-2 text-secondary">
                            <span>{value.range_low ?? "—"} – {value.range_high ?? "—"}</span>
                            {value.flag !== "NONE" ? (
                              <StatusBadge tone="neutral">{value.flag}</StatusBadge>
                            ) : null}
                          </span>
                        </li>
                      ))}
                    </ul>
                    {detail.data.comments ? (
                      <p className="text-[12.5px] text-secondary">Comment: {detail.data.comments}</p>
                    ) : null}
                    {canVerify && detail.data.version_no !== null && detail.data.result_state === "RESULT_ENTERED" ? (
                      <Button
                        disabled={busy}
                        onClick={() =>
                          release.mutate({
                            itemId: selected.itemId,
                            key: newIdempotencyKey(`lab-release-${selected.itemId}`),
                            expectedVersion: detail.data!.version_no!,
                          })
                        }
                      >
                        {release.isPending ? "Releasing…" : "Verify & release"}
                      </Button>
                    ) : canVerify && detail.data.result_state === "DRAFT" ? (
                      <p className="text-[12.5px] text-secondary" role="status">
                        This result has an editable draft head. Refresh after the technician resubmits it.
                      </p>
                    ) : (
                      <p className="text-[12.5px] text-secondary">
                        A separate authorized verifier must release this result.
                      </p>
                    )}
                  </div>
                )}
              </div>
            ) : null}
          </Card>
        ) : null}

        {worklist.isLoading ? (
          <Card>
            <p className="px-5 py-6 text-[12.5px] text-secondary" role="status" aria-busy="true">
              Loading the laboratory worklist…
            </p>
          </Card>
        ) : worklist.isError ? (
          <Card>
            <p className="px-5 py-6 text-[12.5px] text-ink" role="alert">
              The laboratory worklist could not be loaded.
            </p>
          </Card>
        ) : (
          <section className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
            <Card>
              <CardTitleBar title={`To collect (${sections.to_collect.length})`} />
              {sections.to_collect.length ? (
                <ul className="divide-y divide-line-soft">
                  {sections.to_collect.map((row) => (
                    <Row key={row.item_id} row={row} action={canEnter ? (
                      <Button variant="secondary" disabled={busy || !online} onClick={() => startCollect(row.item_id)}>
                        Collect sample
                      </Button>
                    ) : (
                      <p className="text-[12.5px] text-secondary">Result-entry access is required.</p>
                    )} />
                  ))}
                </ul>
              ) : (
                <EmptyState icon={<IconBilling className="h-5 w-5" />} title="No samples to collect." hint="Paid or ungated items appear here." />
              )}
            </Card>

            <Card>
              <CardTitleBar title={`In bench (${sections.in_bench.length})`} />
              {sections.in_bench.length ? (
                <ul className="divide-y divide-line-soft">
                  {sections.in_bench.map((row) => (
                    <Row key={row.item_id} row={row} action={canEnter ? (
                      <Button variant="secondary" disabled={busy} onClick={() => openEntry(row)}>
                        Enter results
                      </Button>
                    ) : (
                      <p className="text-[12.5px] text-secondary">Result-entry access is required.</p>
                    )} />
                  ))}
                </ul>
              ) : (
                <EmptyState icon={<IconBilling className="h-5 w-5" />} title="No samples in the bench." hint="Collected samples appear here." />
              )}
            </Card>

            <Card>
              <CardTitleBar title={`To verify (${sections.to_verify.length})`} />
              {sections.to_verify.length ? (
                <ul className="divide-y divide-line-soft">
                  {sections.to_verify.map((row) => (
                    <Row key={row.item_id} row={row} action={
                      <div>
                        <Button
                          variant="secondary"
                          disabled={!canVerify || busy}
                          aria-describedby={canVerify ? undefined : `release-help-${row.item_id}`}
                          onClick={() => openReview(row)}
                        >
                          Review and release
                        </Button>
                        {!canVerify ? (
                          <p id={`release-help-${row.item_id}`} className="mt-1 text-[12.5px] text-secondary">
                            A separate authorized verifier must release this result.
                          </p>
                        ) : null}
                      </div>
                    } />
                  ))}
                </ul>
              ) : (
                <EmptyState icon={<IconBilling className="h-5 w-5" />} title="No results awaiting verification." hint="Entered results appear here." />
              )}
            </Card>

            <Card>
              <CardTitleBar title={`Rejected / action needed (${sections.rejected.length})`} />
              {sections.rejected.length ? (
                <ul className="divide-y divide-line-soft">
                  {sections.rejected.map((row) => (
                    <Row key={row.item_id} row={row} action={canEnter ? (
                      <Button variant="secondary" disabled={busy || !online} onClick={() => startCollect(row.item_id)}>
                        Recollect sample
                      </Button>
                    ) : null} />
                  ))}
                </ul>
              ) : (
                <p className="px-5 py-4 text-[12.5px] text-secondary">No rejected samples.</p>
              )}
            </Card>

            <Card className="xl:col-span-2">
              <CardTitleBar title={`Awaiting payment (${sections.awaiting_payment.length})`} />
              {sections.awaiting_payment.length ? (
                <ul className="divide-y divide-line-soft">
                  {sections.awaiting_payment.map((row) => <Row key={row.item_id} row={row} />)}
                </ul>
              ) : (
                <p className="px-5 py-4 text-[12.5px] text-secondary">No laboratory items are waiting for payment.</p>
              )}
            </Card>

            <Card className="xl:col-span-2">
              <CardTitleBar title={`Released (${sections.released.length})`} />
              {sections.released.length ? (
                <ul className="divide-y divide-line-soft">
                  {sections.released.map((row) => <Row key={row.item_id} row={row} />)}
                </ul>
              ) : (
                <p className="px-5 py-4 text-[12.5px] text-secondary">No released results in this worklist page.</p>
              )}
            </Card>
          </section>
        )}

        {worklist.hasNextPage ? (
          <div className="flex justify-center">
            <Button
              variant="secondary"
              disabled={worklist.isFetchingNextPage}
              onClick={() => void worklist.fetchNextPage()}
            >
              {worklist.isFetchingNextPage ? "Loading…" : "Load more"}
            </Button>
          </div>
        ) : null}
      </div>
    </>
  );
}
