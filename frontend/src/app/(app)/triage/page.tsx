"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "../../../lib/api";
import { protectedQueryKey, useProtectedQueryKey } from "../../../lib/authority";
import { useSession } from "../../../lib/session";
import { QueueEntry } from "../../../features/clinic";
import { IconCheckCircle, IconTriage } from "../../../components/icons";
import {
  Button,
  Card,
  CardTitleBar,
  EmptyState,
  ErrorBanner,
  Field,
  PageHeader,
  Select,
  SequenceCircle,
  StatusBadge,
  Textarea,
  TextInput,
  UnauthorisedState,
  formatTime,
  queueStatusBadge,
} from "../../../components/ui";

const ACUITY_OPTIONS = [
  { value: "ROUTINE", label: "Routine" },
  { value: "URGENT", label: "Urgent" },
  { value: "EMERGENCY", label: "Emergency" },
];

function errorMessage(error: unknown) {
  if (error instanceof Error && error.message.includes("permission")) {
    return "You don't have permission to perform this action.";
  }
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function TriageWorkspace() {
  const { can } = useSession();
  const queryClient = useQueryClient();
  const queueKey = useProtectedQueryKey("queue", "WAITING,CALLED");
  const searchParams = useSearchParams();
  const preselectedId = searchParams.get("entry");
  const [selectedId, setSelectedId] = useState<string | null>(preselectedId);
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [acuity, setAcuity] = useState("ROUTINE");
  const [pulse, setPulse] = useState("");
  const [temperature, setTemperature] = useState("");
  const [systolic, setSystolic] = useState("");
  const [diastolic, setDiastolic] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const queue = useQuery({
    queryKey: queueKey,
    queryFn: () => apiRequest<QueueEntry[]>("/api/v1/clinic/queue/?status=WAITING,CALLED"),
    enabled: can("triage.record"),
  });

  const selected = useMemo(
    () => (queue.data ?? []).find((entry) => entry.id === selectedId) ?? null,
    [queue.data, selectedId],
  );

  useEffect(() => {
    if (!selectedId && queue.data && queue.data.length > 0) {
      setSelectedId(preselectedId ?? null);
    }
  }, [queue.data, selectedId, preselectedId]);

  const triage = useMutation({
    mutationFn: () => {
      const vitals: Record<string, string> = {};
      if (pulse.trim()) vitals.pulse = pulse.trim();
      if (temperature.trim()) vitals.temperature_c = temperature.trim();
      if (systolic.trim() && diastolic.trim()) {
        vitals.systolic = systolic.trim();
        vitals.diastolic = diastolic.trim();
      }
      return apiRequest(`/api/v1/clinic/triage/${selected?.id}/`, {
        method: "POST",
        body: JSON.stringify({
          acuity,
          chief_complaint: chiefComplaint,
          ...(Object.keys(vitals).length > 0 ? { vitals } : {}),
        }),
      });
    },
    onSuccess: () => {
      setNotice(`Triage recorded for ${selected?.patient_name}. The patient is now ready for consultation.`);
      setError("");
      setChiefComplaint("");
      setPulse("");
      setTemperature("");
      setSystolic("");
      setDiastolic("");
      setSelectedId(null);
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("queue") });
    },
    onError: (reason) => {
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  if (!can("triage.record")) {
    return <UnauthorisedState capability="triage.record" />;
  }

  return (
    <>
      <PageHeader
        title="Triage"
        subtitle="First observations for patients waiting to be seen."
      />

      {notice ? (
        <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
          <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
          {notice}
        </p>
      ) : null}
      {error ? <ErrorBanner message={error} onDismiss={() => setError("")} /> : null}

      <section className="grid grid-cols-1 xl:grid-cols-[1fr_1.35fr] gap-5 items-start">
        <Card>
          <CardTitleBar title={`Awaiting triage (${queue.data?.length ?? 0})`} />
          {queue.isLoading ? (
            <div className="px-5 py-6 space-y-5" aria-busy="true" aria-label="Loading triage queue">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="h-12 animate-pulse rounded-[10px] bg-line-soft" />
              ))}
            </div>
          ) : queue.isError ? (
            <EmptyState
              icon={<IconTriage className="h-5 w-5" />}
              title="The triage queue could not be loaded."
              action={<Button variant="secondary" onClick={() => queue.refetch()}>Retry</Button>}
            />
          ) : (queue.data ?? []).length === 0 ? (
            <EmptyState
              icon={<IconTriage className="h-5 w-5" />}
              title="No patients are currently waiting for triage."
              hint="New check-ins will appear here automatically."
            />
          ) : (
            <ul className="px-5 pt-2 pb-4 divide-y divide-line-soft">
              {(queue.data ?? []).map((entry, index) => {
                const badge = queueStatusBadge(entry.status);
                const active = entry.id === selectedId;
                return (
                  <li key={entry.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedId(entry.id);
                        setNotice("");
                      }}
                      aria-pressed={active}
                      className={`w-full flex items-center gap-3 py-3 rounded-xl text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${
                        active ? "bg-primary-soft" : "hover:bg-primary-hover"
                      }`}
                    >
                      <span className="pl-2 flex items-center gap-3 flex-1 min-w-0">
                        <SequenceCircle value={entry.sequence || index + 1} index={index} />
                        <span className="flex-1 min-w-0 leading-tight">
                          <span className="block text-[13px] font-semibold text-ink">{entry.patient_name}</span>
                          <span className="mt-0.5 block text-[11.5px] font-medium text-muted">
                            {entry.queue_label}
                            <span className="mx-0.5">•</span>
                            {entry.department_name}
                          </span>
                        </span>
                      </span>
                      <span className="pr-2 text-right leading-tight">
                        <StatusBadge tone={badge.tone}>{badge.label}</StatusBadge>
                        <span className="mt-1 block text-[10.5px] font-medium text-muted">{formatTime(entry.arrival_at)}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card>
          <CardTitleBar title="Triage record" />
          {selected ? (
            <div className="px-5 py-5 space-y-5">
              <div className="flex items-start gap-3 rounded-[14px] bg-surface-muted border border-line-soft p-4">
                <SequenceCircle value={selected.sequence || "•"} index={0} />
                <div className="leading-tight">
                  <p className="text-[14px] font-bold text-ink">{selected.patient_name}</p>
                  <p className="mt-1 text-[11.5px] font-medium text-muted">
                    {selected.queue_label}
                    <span className="mx-0.5">•</span>
                    {selected.department_name}
                    <span className="mx-0.5">•</span>
                    Arrived {formatTime(selected.arrival_at)}
                  </p>
                </div>
              </div>

              <Field label="Chief complaint" htmlFor="chief-complaint">
                <Textarea
                  id="chief-complaint"
                  value={chiefComplaint}
                  onChange={(event) => setChiefComplaint(event.target.value)}
                  placeholder="Record the patient's stated concern"
                />
              </Field>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <Field label="Priority" htmlFor="acuity">
                  <Select id="acuity" value={acuity} onChange={(event) => setAcuity(event.target.value)}>
                    {ACUITY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Pulse (bpm)" htmlFor="pulse">
                  <TextInput id="pulse" inputMode="numeric" value={pulse} onChange={(event) => setPulse(event.target.value)} placeholder="—" />
                </Field>
                <Field label="Temperature (°C)" htmlFor="temperature">
                  <TextInput id="temperature" inputMode="decimal" value={temperature} onChange={(event) => setTemperature(event.target.value)} placeholder="—" />
                </Field>
                <Field label="Systolic BP" htmlFor="systolic">
                  <TextInput id="systolic" inputMode="numeric" value={systolic} onChange={(event) => setSystolic(event.target.value)} placeholder="—" />
                </Field>
                <Field label="Diastolic BP" htmlFor="diastolic">
                  <TextInput id="diastolic" inputMode="numeric" value={diastolic} onChange={(event) => setDiastolic(event.target.value)} placeholder="—" />
                </Field>
              </div>

              <Button disabled={triage.isPending} onClick={() => triage.mutate()}>
                {triage.isPending ? "Recording…" : "Complete triage"}
              </Button>
              <p className="text-[11.5px] font-medium text-muted">
                Priority is nurse-assigned. The system does not compute acuity.
              </p>
            </div>
          ) : (
            <EmptyState
              icon={<IconTriage className="h-5 w-5" />}
              title="No patient selected."
              hint="Choose a patient from the triage queue to record observations."
            />
          )}
        </Card>
      </section>
    </>
  );
}

export default function TriagePage() {
  return (
    <Suspense fallback={<Card/>}>
      <TriageWorkspace />
    </Suspense>
  );
}
