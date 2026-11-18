"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, apiRequest, newIdempotencyKey } from "../../../lib/api";
import { protectedQueryKey, useProtectedQueryKey } from "../../../lib/authority";
import { useSession } from "../../../lib/session";
import { OperationalQueueEnvelope, canonicalQueueState } from "../../../features/clinic";
import type {
  TriageRecordCompleteResponse,
  TriageRecordSaveResponse,
  TriageRecordStartResponse,
} from "../../../generated/api-client";
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
  { value: "EMERGENCY", label: "Emergency" },
  { value: "URGENT", label: "Urgent" },
  { value: "ROUTINE", label: "Routine" },
];

type Complaint = {
  text: string;
  duration_value?: number | null;
  duration_unit?: string | null;
};

type MedicationContext = {
  medications: string[];
  chronic_conditions: string[];
};

type Observation = {
  id?: string;
  sequence?: number;
  pulse?: number | null;
  temperature_c?: string | null;
  systolic?: number | null;
  diastolic?: number | null;
  respiratory_rate?: number | null;
  oxygen_saturation?: number | null;
  weight_kg?: string | null;
  height_cm?: string | null;
  muac_cm?: string | null;
  unable_reason_fields?: Record<string, string>;
  measured_at?: string;
};

type Snapshot = TriageRecordStartResponse["triage_record"];
type TriageRecord = Omit<
  Snapshot,
  "presenting_complaints" | "current_medications" | "observation"
> & {
  presenting_complaints: Complaint[];
  current_medications: MedicationContext;
  observation: Observation | null;
};

type QueueRow = OperationalQueueEnvelope["entries"][number];

function normalizeRecord(record: Snapshot): TriageRecord {
  return {
    ...record,
    presenting_complaints: (record.presenting_complaints as Complaint[] | null) ?? [],
    current_medications: (record.current_medications as MedicationContext | null) ?? {
      medications: [],
      chronic_conditions: [],
    },
    observation: (record.observation as Observation | null) ?? null,
  };
}

function errorMessage(error: unknown) {
  if (error instanceof ApiRequestError) {
    if (error.status === 403) return "You don't have permission to perform this action.";
    if (error.status === 409) return "This triage record changed. Reloading the current version.";
    if (error.status === 412) return "The triage record changed. Reload the current version and retry.";
    if (error.status === 428) return "Reload the current triage version before retrying.";
  }
  if (error instanceof Error && error.message.includes("permission")) {
    return "You don't have permission to perform this action.";
  }
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function errorCode(error: unknown) {
  if (error instanceof ApiRequestError && error.data && typeof error.data === "object") {
    return (error.data as { code?: string }).code ?? "";
  }
  return "";
}

function TriageWorkspace() {
  const { can } = useSession();
  const queryClient = useQueryClient();
  const queueKey = useProtectedQueryKey("queue", "WAITING,CALLED,IN_SERVICE");
  const searchParams = useSearchParams();
  const preselectedId = searchParams.get("entry");
  const canCreate = can("triage.create");
  const canRecord = can("triage.record");
  const canTriage = canCreate || canRecord;

  const [selectedId, setSelectedId] = useState<string | null>(preselectedId);
  const [record, setRecord] = useState<TriageRecord | null>(null);
  const [queueVersion, setQueueVersion] = useState<number | null>(null);
  const [legacy, setLegacy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [medications, setMedications] = useState("");
  const [chronicConditions, setChronicConditions] = useState("");
  const [acuity, setAcuity] = useState("");
  const [acuityReason, setAcuityReason] = useState("");
  const [pulse, setPulse] = useState("");
  const [temperature, setTemperature] = useState("");
  const [systolic, setSystolic] = useState("");
  const [diastolic, setDiastolic] = useState("");
  const [respiratoryRate, setRespiratoryRate] = useState("");
  const [oxygenSaturation, setOxygenSaturation] = useState("");
  const [weight, setWeight] = useState("");
  const [height, setHeight] = useState("");
  const [muac, setMuac] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const saveKeyRef = useRef<string | null>(null);
  const completeKeyRef = useRef<string | null>(null);
  const openedEntryRef = useRef<string | null>(null);
  const dirtyRef = useRef(false);

  const queue = useQuery({
    queryKey: queueKey,
    queryFn: () =>
      apiRequest<OperationalQueueEnvelope>(
        "/api/v1/clinic/queue/operational/?state=WAITING,CALLED,IN_SERVICE&queue_type=TRIAGE"
      ),
    enabled: canTriage,
  });

  const selected = useMemo(
    () => (queue.data?.entries ?? []).find((entry) => entry.id === selectedId) ?? null,
    [queue.data?.entries, selectedId]
  );

  useEffect(() => {
    if (!selectedId && queue.data?.entries && queue.data.entries.length > 0) {
      setSelectedId(preselectedId ?? null);
    }
  }, [queue.data?.entries, selectedId, preselectedId]);

  function applyRecord(next: TriageRecord, { keepFields = false } = {}) {
    setRecord(next);
    if (keepFields) {
      // A start/resume response must not erase values the nurse typed while
      // the request was in flight.
      return;
    }
    setChiefComplaint((next.presenting_complaints ?? []).map((item) => item.text).join("\n"));
    setMedications((next.current_medications?.medications ?? []).join("\n"));
    setChronicConditions((next.current_medications?.chronic_conditions ?? []).join(", "));
    setAcuity(next.acuity ?? "");
    setPulse(next.observation?.pulse != null ? String(next.observation.pulse) : "");
    setTemperature(
      next.observation?.temperature_c != null ? String(next.observation.temperature_c) : ""
    );
    setSystolic(next.observation?.systolic != null ? String(next.observation.systolic) : "");
    setDiastolic(next.observation?.diastolic != null ? String(next.observation.diastolic) : "");
    setRespiratoryRate(
      next.observation?.respiratory_rate != null
        ? String(next.observation.respiratory_rate)
        : ""
    );
    setOxygenSaturation(
      next.observation?.oxygen_saturation != null
        ? String(next.observation.oxygen_saturation)
        : ""
    );
    setWeight(next.observation?.weight_kg != null ? String(next.observation.weight_kg) : "");
    setHeight(next.observation?.height_cm != null ? String(next.observation.height_cm) : "");
    setMuac(next.observation?.muac_cm != null ? String(next.observation.muac_cm) : "");
    dirtyRef.current = false;
    setDirty(false);
    setSaveState("saved");
  }

  function markDirty() {
    dirtyRef.current = true;
    setDirty(true);
    setSaveState("idle");
    saveKeyRef.current = null;
    completeKeyRef.current = null;
  }

  function payload() {
    const complaints = chiefComplaint
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean)
      .map((text) => ({ text }));
    const medicationList = medications
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    const chronicList = chronicConditions
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const observation: Record<string, string> = {};
    if (pulse.trim()) observation.pulse = pulse.trim();
    if (temperature.trim()) observation.temperature_c = temperature.trim();
    if (systolic.trim() && diastolic.trim()) {
      observation.systolic = systolic.trim();
      observation.diastolic = diastolic.trim();
    }
    if (respiratoryRate.trim()) observation.respiratory_rate = respiratoryRate.trim();
    if (oxygenSaturation.trim()) observation.oxygen_saturation = oxygenSaturation.trim();
    if (weight.trim()) observation.weight_kg = weight.trim();
    if (height.trim()) observation.height_cm = height.trim();
    if (muac.trim()) observation.muac_cm = muac.trim();
    const body: Record<string, unknown> = {
      presenting_complaints: complaints,
      current_medications: {
        medications: medicationList,
        chronic_conditions: chronicList,
      },
    };
    if (Object.keys(observation).length > 0) body.observation = observation;
    if (acuity) body.acuity = acuity;
    if (acuityReason.trim()) body.acuity_reason = acuityReason.trim();
    return body;
  }

  const start = useMutation({
    mutationFn: (entry: QueueRow) =>
      apiRequest<TriageRecordStartResponse>(
        `/api/v1/clinic/triage/${entry.id}/start/`,
        {
          method: "POST",
          headers: {
            "Idempotency-Key": `cmd-025-${entry.id}-${entry.version}`,
            "If-Match": `"${entry.version}"`,
          },
          body: JSON.stringify({ expected_version: entry.version }),
        }
      ),
    onSuccess: (data) => {
      applyRecord(normalizeRecord(data.triage_record), { keepFields: dirtyRef.current });
      setQueueVersion(data.queue_entry.version ?? null);
      setError("");
    },
    onError: async (reason, entry) => {
      if (reason instanceof ApiRequestError) {
        if (
          (reason.status === 503 && errorCode(reason) === "MIGRATION_TARGET_DISABLED") ||
          (reason.status === 403 && canRecord)
        ) {
          setLegacy(true);
          setQueueVersion(entry.version);
          setError("");
          return;
        }
        if (reason.status === 409) {
          const recordId = (reason.data as { triage_record_id?: string })?.triage_record_id;
          if (recordId) {
            try {
              const data = await apiRequest<{ triage_record: Snapshot }>(
                `/api/v1/clinic/triage-records/${recordId}/`
              );
              applyRecord(normalizeRecord(data.triage_record));
              setQueueVersion(entry.version);
              setError("");
              return;
            } catch (reloadError) {
              setError(errorMessage(reloadError));
              return;
            }
          }
          setError(errorMessage(reason));
          return;
        }
      }
      setError(errorMessage(reason));
    },
  });

  const reloadRecord = async (recordId: string) => {
    try {
      const data = await apiRequest<{ triage_record: Snapshot }>(
        `/api/v1/clinic/triage-records/${recordId}/`
      );
      applyRecord(normalizeRecord(data.triage_record));
    } catch (reloadError) {
      setError(errorMessage(reloadError));
    }
  };

  const saveDraft = useMutation({
    mutationFn: async () => {
      let current = record;
      if (!current) {
        if (!selected) throw new Error("Select a patient before saving triage.");
        const started = await start.mutateAsync(selected);
        current = normalizeRecord(started.triage_record);
        setQueueVersion(started.queue_entry.version ?? null);
      }
      if (current.state !== "DRAFT") {
        throw new Error("This triage record is already complete.");
      }
      const key = saveKeyRef.current ?? newIdempotencyKey(`cmd-026-${current.id}`);
      saveKeyRef.current = key;
      setSaveState("saving");
      return apiRequest<TriageRecordSaveResponse>(
        `/api/v1/clinic/triage-records/${current.id}/`,
        {
          method: "PATCH",
          headers: {
            "Idempotency-Key": key,
            "If-Match": `"${current.version}"`,
          },
          body: JSON.stringify({ ...payload(), expected_version: current.version }),
        }
      );
    },
    onSuccess: (data) => {
      saveKeyRef.current = null;
      applyRecord(normalizeRecord(data.triage_record));
      setError("");
      setNotice("Draft saved.");
    },
    onError: async (reason) => {
      setSaveState("idle");
      if (reason instanceof ApiRequestError && (reason.status === 409 || reason.status === 412)) {
        if (record) await reloadRecord(record.id);
        setError(errorMessage(reason));
        return;
      }
      setError(errorMessage(reason));
    },
  });

  useEffect(() => {
    if (!record || record.state !== "DRAFT" || !dirty || legacy) return;
    const timer = window.setTimeout(() => saveDraft.mutate(), 20_000);
    return () => window.clearTimeout(timer);
  }, [record, dirty, legacy, saveDraft]);

  const complete = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("Select a patient before completing triage.");
      if (!acuity) throw new Error("Select a priority before completing triage.");
      if (legacy) {
        const vitals: Record<string, string> = {};
        if (pulse.trim()) vitals.pulse = pulse.trim();
        if (temperature.trim()) vitals.temperature_c = temperature.trim();
        if (systolic.trim() && diastolic.trim()) {
          vitals.systolic = systolic.trim();
          vitals.diastolic = diastolic.trim();
        }
        const key =
          completeKeyRef.current ?? newIdempotencyKey(`cmd-027-${selected.id}`);
        completeKeyRef.current = key;
        return apiRequest<{ queue_entry?: { state?: string } }>(
          `/api/v1/clinic/triage/${selected.id}/`,
          {
            method: "POST",
            headers: {
              "Idempotency-Key": key,
              "If-Match": `"${selected.version}"`,
            },
            body: JSON.stringify({
              expected_version: selected.version,
              acuity,
              chief_complaint: chiefComplaint,
              ...(Object.keys(vitals).length > 0 ? { vitals } : {}),
            }),
          }
        );
      }
      let current = record;
      let currentQueueVersion = queueVersion;
      if (!current) {
        const started = await start.mutateAsync(selected);
        current = normalizeRecord(started.triage_record);
        currentQueueVersion = started.queue_entry.version ?? null;
        setQueueVersion(currentQueueVersion);
      }
      if (current.state !== "DRAFT") {
        throw new Error("This triage record is already complete.");
      }
      if (dirty) {
        const saved = await saveDraft.mutateAsync();
        current = normalizeRecord(saved.triage_record);
      }
      if (currentQueueVersion == null) {
        throw new Error("Reload the triage queue before completing.");
      }
      const key = completeKeyRef.current ?? newIdempotencyKey(`cmd-027-${current.id}`);
      completeKeyRef.current = key;
      return apiRequest<TriageRecordCompleteResponse>(
        `/api/v1/clinic/triage-records/${current.id}/complete/`,
        {
          method: "POST",
          headers: {
            "Idempotency-Key": key,
            "If-Match": `"${current.version}"`,
          },
          body: JSON.stringify({
            ...payload(),
            expected_version: current.version,
            expected_queue_version: currentQueueVersion,
            acuity,
          }),
        }
      );
    },
    onSuccess: (data) => {
      completeKeyRef.current = null;
      if (data && "triage_record" in data) {
        applyRecord(normalizeRecord(data.triage_record));
      }
      setNotice(
        `Triage recorded for ${selected?.patient_name}. The patient is now ready for consultation.`
      );
      setError("");
      setSelectedId(null);
      setRecord(null);
      setQueueVersion(null);
      dirtyRef.current = false;
      setDirty(false);
      setSaveState("idle");
      setChiefComplaint("");
      setMedications("");
      setChronicConditions("");
      setAcuity("");
      setAcuityReason("");
      setPulse("");
      setTemperature("");
      setSystolic("");
      setDiastolic("");
      setRespiratoryRate("");
      setOxygenSaturation("");
      setWeight("");
      setHeight("");
      setMuac("");
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("queue") });
    },
    onError: (reason) => {
      if (reason instanceof ApiRequestError && (reason.status === 409 || reason.status === 412)) {
        if (record) void reloadRecord(record.id);
      }
      setError(errorMessage(reason));
    },
  });

  function openEntry(entry: QueueRow) {
    setSelectedId(entry.id);
    setNotice("");
    setError("");
    setRecord(null);
    setQueueVersion(entry.version);
    const useLegacy = !canCreate;
    setLegacy(useLegacy);
    dirtyRef.current = false;
    setDirty(false);
    setSaveState("idle");
    setChiefComplaint("");
    setMedications("");
    setChronicConditions("");
    setAcuity("");
    setAcuityReason("");
    setPulse("");
    setTemperature("");
    setSystolic("");
    setDiastolic("");
    setRespiratoryRate("");
    setOxygenSaturation("");
    setWeight("");
    setHeight("");
    setMuac("");
    if (!useLegacy) {
      openedEntryRef.current = entry.id;
      start.mutate(entry);
    }
  }

  useEffect(() => {
    if (!preselectedId || !selected) return;
    if (openedEntryRef.current === selected.id) return;
    openedEntryRef.current = selected.id;
    if (canCreate) {
      start.mutate(selected);
    } else {
      setLegacy(true);
      setQueueVersion(selected.version);
    }
    // The start mutation is stable for the request lifetime.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preselectedId, selected, canCreate]);

  const isCompleted = record?.state === "COMPLETED";
  const disabled = isCompleted || (!canCreate && !legacy);
  const busy = start.isPending || saveDraft.isPending || complete.isPending;

  if (!canTriage) {
    return <UnauthorisedState capability="triage.create" />;
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
          <CardTitleBar title={`Awaiting triage (${queue.data?.count ?? 0})`} />
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
          ) : (queue.data?.entries ?? []).length === 0 ? (
            <EmptyState
              icon={<IconTriage className="h-5 w-5" />}
              title="No patients are currently waiting for triage."
              hint="New check-ins will appear here automatically."
            />
          ) : (
            <ul className="px-5 pt-2 pb-4 divide-y divide-line-soft">
              {(queue.data?.entries ?? []).map((entry, index) => {
                const badge = queueStatusBadge(canonicalQueueState(entry));
                const active = entry.id === selectedId;
                return (
                  <li key={entry.id}>
                    <button
                      type="button"
                      onClick={() => openEntry(entry)}
                      aria-pressed={active}
                      className={`w-full flex items-center gap-3 py-3 rounded-xl text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${
                        active ? "bg-primary-soft" : "hover:bg-primary-hover"
                      }`}
                    >
                      <span className="pl-2 flex items-center gap-3 flex-1 min-w-0">
                        <SequenceCircle value={entry.token || index + 1} index={index} />
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
                        <span className="mt-1 block text-[10.5px] font-medium text-muted">{formatTime(entry.queue_time)}</span>
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
                <SequenceCircle value={selected.token || "•"} index={0} />
                <div className="leading-tight">
                  <p className="text-[14px] font-bold text-ink">{selected.patient_name}</p>
                  <p className="mt-1 text-[11.5px] font-medium text-muted">
                    {selected.queue_label}
                    <span className="mx-0.5">•</span>
                    {selected.department_name}
                    <span className="mx-0.5">•</span>
                    Arrived {formatTime(selected.queue_time)}
                    {record ? (
                      <>
                        <span className="mx-0.5">•</span>
                        {record.state === "COMPLETED" ? "Completed" : "Draft"}
                        <span className="mx-0.5">•</span>
                        v{record.version}
                      </>
                    ) : null}
                  </p>
                </div>
              </div>

              {isCompleted ? (
                <p className="rounded-[12px] bg-surface-muted px-4 py-3 text-[12px] font-medium text-secondary">
                  This triage is complete and read-only. Corrections require the amendment
                  path, which is not enabled on this baseline.
                </p>
              ) : null}

              {!record && !legacy && canCreate ? (
                <Button
                  variant="secondary"
                  disabled={start.isPending}
                  onClick={() => start.mutate(selected)}
                >
                  {start.isPending ? "Opening…" : "Start triage"}
                </Button>
              ) : null}

              <Field label="Chief complaint" htmlFor="chief-complaint">
                <Textarea
                  id="chief-complaint"
                  value={chiefComplaint}
                  disabled={disabled}
                  onChange={(event) => {
                    setChiefComplaint(event.target.value);
                    markDirty();
                  }}
                  placeholder="Record the patient's stated concern, one per line (up to 5)"
                />
              </Field>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field label="Current medications (one per line)" htmlFor="current-medications">
                  <Textarea
                    id="current-medications"
                    value={medications}
                    disabled={disabled}
                    onChange={(event) => {
                      setMedications(event.target.value);
                      markDirty();
                    }}
                    placeholder="Optional, up to 10"
                  />
                </Field>
                <Field label="Chronic conditions (comma separated)" htmlFor="chronic-conditions">
                  <Textarea
                    id="chronic-conditions"
                    value={chronicConditions}
                    disabled={disabled}
                    onChange={(event) => {
                      setChronicConditions(event.target.value);
                      markDirty();
                    }}
                    placeholder="Optional"
                  />
                </Field>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <Field label="Priority" htmlFor="acuity">
                  <Select
                    id="acuity"
                    value={acuity}
                    disabled={disabled}
                    onChange={(event) => {
                      setAcuity(event.target.value);
                      markDirty();
                    }}
                  >
                    <option value="">Select priority</option>
                    {ACUITY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Priority reason (optional)" htmlFor="acuity-reason">
                  <TextInput
                    id="acuity-reason"
                    value={acuityReason}
                    disabled={disabled}
                    onChange={(event) => {
                      setAcuityReason(event.target.value);
                      markDirty();
                    }}
                    placeholder="Why this priority?"
                  />
                </Field>
                <Field label="Pulse (bpm)" htmlFor="pulse">
                  <TextInput id="pulse" inputMode="numeric" value={pulse} disabled={disabled} onChange={(event) => { setPulse(event.target.value); markDirty(); }} placeholder="—" />
                </Field>
                <Field label="Temperature (°C)" htmlFor="temperature">
                  <TextInput id="temperature" inputMode="decimal" value={temperature} disabled={disabled} onChange={(event) => { setTemperature(event.target.value); markDirty(); }} placeholder="30.0–45.0" />
                </Field>
                <Field label="Systolic BP (mmHg)" htmlFor="systolic">
                  <TextInput id="systolic" inputMode="numeric" value={systolic} disabled={disabled} onChange={(event) => { setSystolic(event.target.value); markDirty(); }} placeholder="—" />
                </Field>
                <Field label="Diastolic BP (mmHg)" htmlFor="diastolic">
                  <TextInput id="diastolic" inputMode="numeric" value={diastolic} disabled={disabled} onChange={(event) => { setDiastolic(event.target.value); markDirty(); }} placeholder="—" />
                </Field>
                <Field label="Respiratory rate (/min)" htmlFor="respiratory-rate">
                  <TextInput id="respiratory-rate" inputMode="numeric" value={respiratoryRate} disabled={disabled} onChange={(event) => { setRespiratoryRate(event.target.value); markDirty(); }} placeholder="—" />
                </Field>
                <Field label="SpO₂ (%)" htmlFor="oxygen-saturation">
                  <TextInput id="oxygen-saturation" inputMode="numeric" value={oxygenSaturation} disabled={disabled} onChange={(event) => { setOxygenSaturation(event.target.value); markDirty(); }} placeholder="—" />
                </Field>
                <Field label="Weight (kg)" htmlFor="weight">
                  <TextInput id="weight" inputMode="decimal" value={weight} disabled={disabled} onChange={(event) => { setWeight(event.target.value); markDirty(); }} placeholder="Required under 5" />
                </Field>
                <Field label="Height (cm)" htmlFor="height">
                  <TextInput id="height" inputMode="decimal" value={height} disabled={disabled} onChange={(event) => { setHeight(event.target.value); markDirty(); }} placeholder="—" />
                </Field>
                <Field label="MUAC (cm)" htmlFor="muac">
                  <TextInput id="muac" inputMode="decimal" value={muac} disabled={disabled} onChange={(event) => { setMuac(event.target.value); markDirty(); }} placeholder="Children 6–59 months" />
                </Field>
              </div>

              {record?.bmi ? (
                <p className="text-[11.5px] font-medium text-muted">BMI {record.bmi} (derived)</p>
              ) : null}

              {!isCompleted ? (
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    variant="secondary"
                    disabled={busy || disabled || legacy}
                    onClick={() => saveDraft.mutate()}
                  >
                    {saveDraft.isPending ? "Saving…" : "Save draft"}
                  </Button>
                  <Button disabled={busy || disabled} onClick={() => complete.mutate()}>
                    {complete.isPending ? "Recording…" : "Complete triage"}
                  </Button>
                  {saveState === "saving" ? (
                    <span role="status" className="text-[11.5px] font-medium text-muted">
                      Saving draft…
                    </span>
                  ) : saveState === "saved" ? (
                    <span role="status" className="text-[11.5px] font-medium text-muted">
                      Draft saved
                    </span>
                  ) : null}
                </div>
              ) : null}
              <p className="text-[11.5px] font-medium text-muted">
                Priority is nurse-assigned. The system does not compute acuity or interpret
                observations.
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
    <Suspense fallback={<div role="status" aria-busy="true" className="rounded-[14px] border border-line-soft bg-white px-5 py-6 text-[13px] font-medium text-secondary">Loading triage workspace…</div>}>
      <TriageWorkspace />
    </Suspense>
  );
}
