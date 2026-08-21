"use client";

import Link from "next/link";
import { Suspense, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import { Encounter, QueueEntry } from "../../../features/clinic";
import { IconAlertTriangle, IconCheckCircle, IconConsultation } from "../../../components/icons";
import {
  Button,
  Card,
  CardTitleBar,
  EmptyState,
  ErrorBanner,
  Field,
  PageHeader,
  SequenceCircle,
  StatusBadge,
  Textarea,
  UnauthorisedState,
  formatTime,
  queueStatusBadge,
} from "../../../components/ui";

function errorMessage(error: unknown) {
  if (error instanceof Error && error.message.includes("permission")) {
    return "You don't have permission to perform this action.";
  }
  return error instanceof Error ? error.message : "The request could not be completed.";
}

const WORKSPACE_SECTIONS = [
  { id: "summary", label: "Summary" },
  { id: "history", label: "History" },
  { id: "examination", label: "Examination" },
  { id: "investigations", label: "Investigations" },
  { id: "diagnosis", label: "Diagnosis" },
  { id: "treatment", label: "Treatment" },
  { id: "notes", label: "Notes" },
] as const;
const WORKSPACE_PANEL_ID = "consultation-workspace-panel";

type WorkspaceSectionId = (typeof WORKSPACE_SECTIONS)[number]["id"];
type FoundationSectionId = Exclude<WorkspaceSectionId, "notes">;
const DEFAULT_CONSULTATION_NOTE = "Assessment: \nPlan: ";

function consultationNoteText(encounter: Encounter) {
  const notes = (encounter as Encounter & {
    notes?: Array<{ note_type: string; content: Record<string, unknown> }>;
  }).notes;
  const consultation = notes?.find((entry) => entry.note_type === "CONSULTATION")?.content.consultation;
  return typeof consultation === "string" ? consultation : null;
}

const FOUNDATION_HINTS: Record<FoundationSectionId, string> = {
  summary: "Additional summary information is not available from the current consultation data.",
  history: "History capture is reserved for a later consultation phase.",
  examination: "Examination capture is reserved for a later consultation phase.",
  investigations: "Investigations are not implemented in this foundation phase.",
  diagnosis: "Diagnosis capture is reserved for a later consultation phase.",
  treatment: "Treatment capture is reserved for a later consultation phase.",
};

function WorkspaceSectionTabs({
  activeSection,
  onChange,
}: {
  activeSection: WorkspaceSectionId;
  onChange: (section: WorkspaceSectionId) => void;
}) {
  const tabRefs = useRef<Partial<Record<WorkspaceSectionId, HTMLButtonElement | null>>>({});

  function moveFocus(event: KeyboardEvent<HTMLButtonElement>, currentSection: WorkspaceSectionId) {
    const currentIndex = WORKSPACE_SECTIONS.findIndex((section) => section.id === currentSection);
    let nextIndex = currentIndex;

    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % WORKSPACE_SECTIONS.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + WORKSPACE_SECTIONS.length) % WORKSPACE_SECTIONS.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = WORKSPACE_SECTIONS.length - 1;

    if (nextIndex === currentIndex) return;

    event.preventDefault();
    const nextSection = WORKSPACE_SECTIONS[nextIndex].id;
    onChange(nextSection);
    tabRefs.current[nextSection]?.focus();
  }

  return (
    <div role="tablist" aria-label="Consultation workspace sections" className="flex flex-wrap gap-2 border-b border-line-soft pb-3">
      {WORKSPACE_SECTIONS.map((section) => {
        const active = activeSection === section.id;
        return (
          <button
            key={section.id}
            ref={(element) => {
              tabRefs.current[section.id] = element;
            }}
            type="button"
            role="tab"
            id={`consultation-tab-${section.id}`}
            aria-selected={active}
            aria-controls={WORKSPACE_PANEL_ID}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(section.id)}
            onKeyDown={(event) => moveFocus(event, section.id)}
            className={`inline-flex items-center rounded-full px-3.5 py-1.5 text-[12px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${
              active
                ? "bg-primary text-white shadow-primary"
                : "bg-white border border-line text-secondary hover:bg-primary-hover hover:text-ink"
            }`}
          >
            {section.label}
          </button>
        );
      })}
    </div>
  );
}

function FoundationSection({ section }: { section: FoundationSectionId }) {
  return (
    <div className="rounded-[14px] border border-line-soft bg-surface-muted">
      <EmptyState
        icon={<IconConsultation className="h-5 w-5" />}
        title="Not recorded yet"
        hint={FOUNDATION_HINTS[section]}
      />
    </div>
  );
}

function ConsultationsWorkspace() {
  const { can } = useSession();
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const preselectedId = searchParams.get("entry");
  const [selectedId, setSelectedId] = useState<string | null>(preselectedId);
  const [encounter, setEncounter] = useState<Encounter | null>(null);
  const [note, setNote] = useState(DEFAULT_CONSULTATION_NOTE);
  const [activeSection, setActiveSection] = useState<WorkspaceSectionId>("summary");
  const [confirmingSign, setConfirmingSign] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const queue = useQuery({
    queryKey: ["queue", "TRIAGED,IN_CONSULTATION"],
    queryFn: () => apiRequest<QueueEntry[]>("/api/v1/clinic/queue/?status=TRIAGED,IN_CONSULTATION"),
    enabled: can("clinical.note.create"),
  });

  const selected = useMemo(
    () => (queue.data ?? []).find((entry) => entry.id === selectedId) ?? null,
    [queue.data, selectedId],
  );

  function selectEntry(entry: QueueEntry) {
    setSelectedId(entry.id);
    setEncounter(null);
    setNote(DEFAULT_CONSULTATION_NOTE);
    setActiveSection("summary");
    setConfirmingSign(false);
    setNotice("");
    setError("");
  }

  const startEncounter = useMutation({
    mutationFn: () =>
      apiRequest<Encounter>("/api/v1/clinic/encounters/", {
        method: "POST",
        body: JSON.stringify({ queue_entry_id: selected?.id }),
      }),
    onSuccess: (created) => {
      setEncounter(created);
      setNote(consultationNoteText(created) ?? DEFAULT_CONSULTATION_NOTE);
      setActiveSection("notes");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
    onError: (reason) => setError(errorMessage(reason)),
  });

  const signNote = useMutation({
    mutationFn: () =>
      apiRequest(`/api/v1/clinic/encounters/${encounter?.id}/sign/`, {
        method: "POST",
        body: JSON.stringify({ content: { consultation: note } }),
      }),
    onSuccess: () => {
      setEncounter((current) => (current ? { ...current, status: "SIGNED" } : current));
      setConfirmingSign(false);
      setNotice(`Consultation signed for ${selected?.patient_name ?? "the patient"}.`);
      setError("");
      queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
    onError: (reason) => {
      setConfirmingSign(false);
      setError(errorMessage(reason));
    },
  });

  if (!can("clinical.note.create")) {
    return <UnauthorisedState capability="clinical.note.create" />;
  }

  return (
    <>
      <PageHeader
        title="Consultations"
        subtitle="A calm, focused workspace for seeing and signing consultations."
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
          <CardTitleBar title={`Ready for consultation (${queue.data?.length ?? 0})`} />
          {queue.isLoading ? (
            <div className="px-5 py-6 space-y-5" aria-busy="true" aria-label="Loading consultation queue">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="h-12 animate-pulse rounded-[10px] bg-line-soft" />
              ))}
            </div>
          ) : queue.isError ? (
            <EmptyState
              icon={<IconConsultation className="h-5 w-5" />}
              title="The consultation queue could not be loaded."
              action={<Button variant="secondary" onClick={() => queue.refetch()}>Retry</Button>}
            />
          ) : (queue.data ?? []).length === 0 ? (
            <EmptyState
              icon={<IconConsultation className="h-5 w-5" />}
              title="No patients are waiting for consultation."
              hint="Patients appear here once triage is complete."
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
                      onClick={() => selectEntry(entry)}
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
          <CardTitleBar title="Consultation" />
          {selected ? (
            <div className="px-5 py-5 space-y-5">
              <div
                aria-label="Patient and encounter context"
                className="flex items-start gap-3 rounded-[14px] bg-surface-muted border border-line-soft p-4"
              >
                <SequenceCircle value={selected.sequence || "•"} index={2} />
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
                {encounter ? (
                  <span className="ml-auto self-center">
                    <StatusBadge tone={encounter.status === "SIGNED" ? "teal" : "purple"}>
                      {encounter.encounter_no} · {encounter.status === "SIGNED" ? "Signed" : "Open"}
                    </StatusBadge>
                  </span>
                ) : null}
              </div>

              <WorkspaceSectionTabs activeSection={activeSection} onChange={setActiveSection} />

              <div
                id={WORKSPACE_PANEL_ID}
                role="tabpanel"
                aria-labelledby={`consultation-tab-${activeSection}`}
                className="min-w-0"
              >
                {activeSection !== "notes" ? (
                  activeSection === "summary" && !encounter ? (
                    <div className="space-y-3">
                      <p className="text-[12.5px] font-medium text-secondary">
                        Start the encounter to open the consultation note for this visit.
                      </p>
                      <Button disabled={startEncounter.isPending} onClick={() => startEncounter.mutate()}>
                        {startEncounter.isPending ? "Starting…" : "Start encounter"}
                      </Button>
                    </div>
                  ) : (
                    <FoundationSection section={activeSection} />
                  )
                ) : !encounter ? (
                  <div className="space-y-3">
                    <p className="text-[12.5px] font-medium text-secondary">
                      Start the encounter to open the consultation note for this visit.
                    </p>
                    <Button disabled={startEncounter.isPending} onClick={() => startEncounter.mutate()}>
                      {startEncounter.isPending ? "Starting…" : "Start encounter"}
                    </Button>
                  </div>
                ) : encounter.status === "SIGNED" ? (
                  <div className="space-y-4">
                    <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
                      <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
                      This consultation is signed and immutable. Corrections require a recorded amendment.
                    </p>
                    <div className="rounded-[14px] border border-line bg-white p-4">
                      <h3 className="text-[13px] font-bold text-ink">Consultation note</h3>
                      <pre className="mt-2 whitespace-pre-wrap font-sans text-[12.5px] leading-relaxed text-secondary">{note}</pre>
                    </div>
                    {can("billing.invoice.create") ? (
                      <Link href={`/billing?patient=${selected.patient}&encounter=${encounter.id}`}>
                        <Button>Create invoice</Button>
                      </Link>
                    ) : (
                      <p className="text-[12px] font-medium text-muted">
                        The patient is ready for billing. Hand over to the cashier.
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="space-y-4">
                    <Field label="Consultation note" htmlFor="consultation-note">
                      <Textarea
                        id="consultation-note"
                        className="min-h-[220px]"
                        value={note}
                        onChange={(event) => setNote(event.target.value)}
                      />
                    </Field>

                    {confirmingSign ? (
                      <div role="alert" className="flex flex-wrap items-center gap-3 rounded-[14px] bg-accent-orange-soft px-4 py-3">
                        <IconAlertTriangle className="h-[18px] w-[18px] text-accent-orange shrink-0" />
                        <p className="flex-1 min-w-0 text-[12.5px] font-medium text-ink">
                          Signing finalises this note. It cannot be edited afterwards — corrections require a recorded
                          amendment.
                        </p>
                        <Button variant="secondary" onClick={() => setConfirmingSign(false)}>
                          Cancel
                        </Button>
                        <Button disabled={signNote.isPending} onClick={() => signNote.mutate()}>
                          {signNote.isPending ? "Signing…" : "Confirm signature"}
                        </Button>
                      </div>
                    ) : (
                      <Button onClick={() => setConfirmingSign(true)}>Sign consultation</Button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <EmptyState
              icon={<IconConsultation className="h-5 w-5" />}
              title="No patient selected."
              hint="Choose a patient from the consultation queue to start or continue the visit."
            />
          )}
        </Card>
      </section>
    </>
  );
}

export default function ConsultationsPage() {
  return (
    <Suspense fallback={<Card />}>
      <ConsultationsWorkspace />
    </Suspense>
  );
}
