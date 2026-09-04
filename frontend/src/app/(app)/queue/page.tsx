"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "../../../lib/api";
import { protectedQueryKey, useProtectedQueryKey } from "../../../lib/authority";
import { useSession } from "../../../lib/session";
import { QueueEntry } from "../../../features/clinic";
import { IconQueue, IconSearch } from "../../../components/icons";
import {
  Button,
  Card,
  CardTitleBar,
  EmptyState,
  ErrorBanner,
  SequenceCircle,
  StatusBadge,
  TextInput,
  formatTime,
  queueStatusBadge,
} from "../../../components/ui";

const FILTERS = [
  { key: "all", label: "All", status: "" },
  { key: "waiting", label: "Awaiting triage", status: "WAITING,CALLED" },
  { key: "triage", label: "In triage", status: "IN_TRIAGE" },
  { key: "ready", label: "Ready", status: "TRIAGED" },
  { key: "consultation", label: "In consultation", status: "IN_CONSULTATION" },
] as const;

type FilterKey = (typeof FILTERS)[number]["key"];

export default function QueuePage() {
  const { can } = useSession();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<FilterKey>("all");
  const [search, setSearch] = useState("");
  const [visibleCount, setVisibleCount] = useState(10);
  const [error, setError] = useState("");

  const statusParam = FILTERS.find((item) => item.key === filter)!.status;
  const queueKey = useProtectedQueryKey("queue", statusParam);
  const queue = useQuery({
    queryKey: queueKey,
    queryFn: () =>
      apiRequest<QueueEntry[]>("/api/v1/clinic/queue/" + (statusParam ? `?status=${statusParam}` : "")),
    enabled: can("queue.view"),
  });

  const claim = useMutation({
    mutationFn: (id: string) => apiRequest<QueueEntry>(`/api/v1/clinic/queue/${id}/claim/`, { method: "POST", body: "{}" }),
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("queue") });
    },
    onError: (reason) => setError(reason instanceof Error ? reason.message : "The claim could not be completed."),
  });

  const entries = useMemo(() => {
    const term = search.trim().toLowerCase();
    const all = queue.data ?? [];
    if (!term) return all;
    return all.filter(
      (entry) =>
        entry.patient_name.toLowerCase().includes(term) ||
        entry.queue_label.toLowerCase().includes(term) ||
        entry.department_name.toLowerCase().includes(term),
    );
  }, [queue.data, search]);

  const visible = entries.slice(0, visibleCount);

  return (
    <>
      <section className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-bold tracking-[-0.02em] text-ink">Queue</h1>
          <p className="mt-1 text-[13.5px] font-medium text-secondary">
            Today&apos;s operational queue. Status is scannable at a glance.
          </p>
        </div>
        <div className="relative w-full sm:w-72">
          <IconSearch className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-muted" />
          <TextInput
            className="pl-11"
            placeholder="Filter by patient, label, department…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setVisibleCount(10);
            }}
            aria-label="Filter queue"
          />
        </div>
      </section>

      <div role="tablist" aria-label="Queue status filter" className="flex flex-wrap gap-2">
        {FILTERS.map((item) => (
          <button
            key={item.key}
            role="tab"
            aria-selected={filter === item.key}
            onClick={() => {
              setFilter(item.key);
              setVisibleCount(10);
            }}
            className={`inline-flex items-center rounded-full px-3.5 py-1.5 text-[12px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${
              filter === item.key
                ? "bg-primary text-white shadow-primary"
                : "bg-white border border-line text-secondary hover:bg-primary-hover hover:text-ink"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {error ? <ErrorBanner message={error} onDismiss={() => setError("")} /> : null}

      <Card>
        <CardTitleBar title={`Queue entries (${entries.length})`} />
        {queue.isLoading ? (
          <div className="px-5 py-6 space-y-5" aria-busy="true" aria-label="Loading queue">
            {Array.from({ length: 5 }).map((_, index) => (
              <div key={index} className="h-12 animate-pulse rounded-[10px] bg-line-soft" />
            ))}
          </div>
        ) : queue.isError ? (
          <EmptyState
            icon={<IconQueue className="h-5 w-5" />}
            title="The queue could not be loaded."
            hint="Check your connection and try again."
            action={<Button variant="secondary" onClick={() => queue.refetch()}>Retry</Button>}
          />
        ) : entries.length === 0 ? (
          <EmptyState
            icon={<IconQueue className="h-5 w-5" />}
            title={
              search.trim()
                ? "No queue entries match this filter."
                : filter === "all"
                  ? "No patients are in the queue right now."
                  : "Nothing in this stage right now."
            }
            hint={
              filter === "all" && !search.trim()
                ? "Check in a patient from the Patients workspace to start the visit."
                : undefined
            }
            action={
              can("patient.create") ? (
                <Link href="/patients">
                  <Button variant="secondary">Go to patients</Button>
                </Link>
              ) : undefined
            }
          />
        ) : (
          <>
            <ul className="px-5 pt-2 pb-2 divide-y divide-line-soft">
              {visible.map((entry, index) => {
                const badge = queueStatusBadge(entry.status);
                const canClaim = entry.status === "WAITING" && can("queue.claim");
                const openHref = can("triage.record") ? "/triage" : "/consultations";
                return (
                  <li key={entry.id} className="flex flex-wrap items-center gap-3 py-3">
                    <SequenceCircle value={entry.sequence || index + 1} index={index} />
                    <div className="flex-1 min-w-0 leading-tight">
                      <div className="text-[13px] font-semibold text-ink">{entry.patient_name}</div>
                      <div className="mt-0.5 text-[11.5px] font-medium text-muted">
                        {entry.queue_label}
                        <span className="mx-0.5">•</span>
                        {entry.department_name}
                        <span className="mx-0.5">•</span>
                        {entry.current_stage.charAt(0) + entry.current_stage.slice(1).toLowerCase()}
                      </div>
                    </div>
                    <div className="text-right leading-tight">
                      <StatusBadge tone={badge.tone}>{badge.label}</StatusBadge>
                      <div className="mt-1 text-[10.5px] font-medium text-muted">{formatTime(entry.arrival_at)}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      {canClaim ? (
                        <Button
                          variant="small-secondary"
                          disabled={claim.isPending}
                          onClick={() => claim.mutate(entry.id)}
                        >
                          {claim.isPending ? "Claiming…" : "Claim"}
                        </Button>
                      ) : null}
                      <Link href={`${openHref}?entry=${entry.id}`}>
                        <Button variant="small-secondary">Open</Button>
                      </Link>
                    </div>
                  </li>
                );
              })}
            </ul>
            {entries.length > visibleCount ? (
              <div className="px-5 py-4">
                <Button variant="link" className="w-full" onClick={() => setVisibleCount((count) => count + 10)}>
                  Show more ({entries.length - visibleCount} remaining)
                </Button>
              </div>
            ) : null}
          </>
        )}
      </Card>
    </>
  );
}
