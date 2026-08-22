"use client";

import Link from "next/link";
import { Suspense, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, apiRequest } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import { ClinicalNoteContent, Encounter, QueueEntry } from "../../../features/clinic";
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

type ConsultationDraft = {
  content: ClinicalNoteContent;
  presentingComplaint: string;
  hpi: string;
  pastMedicalHistory: string;
  pastSurgicalHistory: string;
  familyHistory: string;
  socialHistory: string;
  consultation: string;
};

type ClinicalNoteField =
  | "presenting_complaint"
  | "hpi"
  | "past_medical_history"
  | "past_surgical_history"
  | "family_history"
  | "social_history"
  | "consultation";

type EditableDraftValues = Pick<
  ConsultationDraft,
  "presentingComplaint" | "hpi" | "pastMedicalHistory" | "pastSurgicalHistory" | "familyHistory" | "socialHistory" | "consultation"
>;

type DraftMutationVariables = {
  content: ClinicalNoteContent;
  fields: ClinicalNoteField[];
  values: EditableDraftValues;
  encounterId: string;
  session: number;
  etag: string;
  rebaseAttempt: number;
};

type NoteSaveResponse = {
  note: string;
  status: string;
  content: ClinicalNoteContent;
  etag: string;
};

type NoteSignResponse = NoteSaveResponse & {
  current_version: number;
};

const FIELD_TO_DRAFT_VALUE: Record<ClinicalNoteField, keyof EditableDraftValues> = {
  presenting_complaint: "presentingComplaint",
  hpi: "hpi",
  past_medical_history: "pastMedicalHistory",
  past_surgical_history: "pastSurgicalHistory",
  family_history: "familyHistory",
  social_history: "socialHistory",
  consultation: "consultation",
};

const CLINICAL_NOTE_FIELDS: ClinicalNoteField[] = [
  "presenting_complaint",
  "hpi",
  "past_medical_history",
  "past_surgical_history",
  "family_history",
  "social_history",
  "consultation",
];

const CLINICAL_FIELD_LABELS: Record<ClinicalNoteField, string> = {
  presenting_complaint: "Presenting complaint",
  hpi: "History of present illness",
  past_medical_history: "Past medical history",
  past_surgical_history: "Past surgical history",
  family_history: "Family history",
  social_history: "Social history",
  consultation: "Consultation note",
};

type ClinicalNoteConflictData = {
  etag: string;
  status: string;
  encounter_status: string;
  content: ClinicalNoteContent;
};

function clinicalNoteConflict(error: unknown): ClinicalNoteConflictData | null {
  if (!(error instanceof ApiRequestError) || error.status !== 409 || typeof error.data !== "object" || error.data === null) {
    return null;
  }
  const data = error.data as Record<string, unknown>;
  if (
    typeof data.etag !== "string" ||
    typeof data.status !== "string" ||
    typeof data.encounter_status !== "string" ||
    typeof data.content !== "object" ||
    data.content === null
  ) {
    return null;
  }
  return {
    etag: data.etag,
    status: data.status,
    encounter_status: data.encounter_status,
    content: data.content as ClinicalNoteContent,
  };
}

function emptyDraftValues(): EditableDraftValues {
  return {
    presentingComplaint: "",
    hpi: "",
    pastMedicalHistory: "",
    pastSurgicalHistory: "",
    familyHistory: "",
    socialHistory: "",
    consultation: DEFAULT_CONSULTATION_NOTE,
  };
}

function consultationContent(encounter: Encounter): ClinicalNoteContent {
  return encounter.notes?.find((entry) => entry.note_type === "CONSULTATION")?.content ?? {};
}

function contentText(content: ClinicalNoteContent, key: string): string {
  const value = content[key];
  return typeof value === "string" ? value : "";
}

function editableDraftValuesFromContent(content: ClinicalNoteContent): EditableDraftValues {
  const consultation = contentText(content, "consultation");
  const assessment = contentText(content, "assessment");
  const plan = contentText(content, "plan");
  const assessmentPlan = assessment || plan ? "Assessment: " + assessment + "\nPlan: " + plan : DEFAULT_CONSULTATION_NOTE;
  return {
    presentingComplaint: contentText(content, "presenting_complaint"),
    hpi: contentText(content, "hpi"),
    pastMedicalHistory: contentText(content, "past_medical_history"),
    pastSurgicalHistory: contentText(content, "past_surgical_history"),
    familyHistory: contentText(content, "family_history"),
    socialHistory: contentText(content, "social_history"),
    consultation: consultation || assessmentPlan,
  };
}

function consultationDraftFromEncounter(encounter: Encounter): ConsultationDraft {
  const content = consultationContent(encounter);
  return { content, ...editableDraftValuesFromContent(content) };
}

function noteContentForFields(values: EditableDraftValues, fields: ClinicalNoteField[]): ClinicalNoteContent {
  return fields.reduce<ClinicalNoteContent>((content, field) => {
    content[field] = values[FIELD_TO_DRAFT_VALUE[field]];
    return content;
  }, {});
}

function changedClinicalFields(before: ClinicalNoteContent, after: ClinicalNoteContent): ClinicalNoteField[] {
  const beforeValues = editableDraftValuesFromContent(before);
  const afterValues = editableDraftValuesFromContent(after);
  return CLINICAL_NOTE_FIELDS.filter(
    (field) => beforeValues[FIELD_TO_DRAFT_VALUE[field]] !== afterValues[FIELD_TO_DRAFT_VALUE[field]],
  );
}

function fieldNames(fields: ClinicalNoteField[]) {
  return fields.map((field) => CLINICAL_FIELD_LABELS[field]).join(", ");
}

function conflictMessage(remoteFields: ClinicalNoteField[], overlappingFields: ClinicalNoteField[], action: "save" | "sign") {
  const actionLabel = action === "sign" ? "signing" : "saving";
  if (overlappingFields.length > 0) {
    return "This consultation changed elsewhere. Your unsaved " + fieldNames(overlappingFields) +
      " has been preserved. Review the latest record before " + actionLabel + " again.";
  }
  const remoteLabel = remoteFields.length > 0 ? fieldNames(remoteFields) : "the latest record";
  return "This consultation changed elsewhere in " + remoteLabel +
    ". Review the latest record before " + actionLabel + " again.";
}

const FOUNDATION_HINTS: Record<FoundationSectionId, string> = {
  summary: "Additional summary information is not available from the current consultation data.",
  history: "Start the encounter to capture the presenting complaint, HPI, and relevant past history.",
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
type HistorySectionProps = {
  status: string;
  presentingComplaint: string;
  hpi: string;
  pastMedicalHistory: string;
  pastSurgicalHistory: string;
  familyHistory: string;
  socialHistory: string;
  onPresentingComplaintChange: (value: string) => void;
  onHpiChange: (value: string) => void;
  onPastMedicalHistoryChange: (value: string) => void;
  onPastSurgicalHistoryChange: (value: string) => void;
  onFamilyHistoryChange: (value: string) => void;
  onSocialHistoryChange: (value: string) => void;
  onSave: () => void;
  savePending: boolean;
  saveState: "idle" | "unsaved" | "saved";
};

function HistorySection({
  status,
  presentingComplaint,
  hpi,
  pastMedicalHistory,
  pastSurgicalHistory,
  familyHistory,
  socialHistory,
  onPresentingComplaintChange,
  onHpiChange,
  onPastMedicalHistoryChange,
  onPastSurgicalHistoryChange,
  onFamilyHistoryChange,
  onSocialHistoryChange,
  onSave,
  savePending,
  saveState,
}: HistorySectionProps) {
  if (status === "SIGNED") {
    return (
      <div className="space-y-4">
        <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
          <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
          This History section is signed and immutable.
        </p>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Presenting complaint</h3>
          <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">
            {presentingComplaint || "Not recorded."}
          </p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">History of present illness (HPI)</h3>
          <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">
            {hpi || "Not recorded."}
          </p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Relevant Past Medical History</h3>
          <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">
            {pastMedicalHistory || "Not recorded."}
          </p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Relevant Past Surgical History</h3>
          <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">
            {pastSurgicalHistory || "Not recorded."}
          </p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Relevant Family History</h3>
          <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">
            {familyHistory || "Not recorded."}
          </p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Relevant Social History</h3>
          <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">
            {socialHistory || "Not recorded."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-[12.5px] font-medium text-secondary">
        Record the patient&apos;s presenting complaint, history of this illness, and relevant past history. This section does not add a diagnosis or treatment.
      </p>
      <Field
        label="Presenting complaint"
        htmlFor="presenting-complaint"
        hint="Patient-reported reason for the visit (500 characters maximum)."
      >
        <Textarea
          id="presenting-complaint"
          maxLength={500}
          value={presentingComplaint}
          onChange={(event) => onPresentingComplaintChange(event.target.value)}
        />
      </Field>
      <Field
        label="History of present illness (HPI)"
        htmlFor="history-of-present-illness"
        hint="Current illness history in the patient&apos;s account (4,000 characters maximum)."
      >
        <Textarea
          id="history-of-present-illness"
          className="min-h-[180px]"
          maxLength={4000}
          value={hpi}
          onChange={(event) => onHpiChange(event.target.value)}
        />
      </Field>
      <Field
        label="Relevant Past Medical History"
        htmlFor="past-medical-history"
        hint="Relevant prior medical conditions or history (4,000 characters maximum)."
      >
        <Textarea
          id="past-medical-history"
          className="min-h-[150px]"
          maxLength={4000}
          value={pastMedicalHistory}
          onChange={(event) => onPastMedicalHistoryChange(event.target.value)}
        />
      </Field>
      <Field
        label="Relevant Past Surgical History"
        htmlFor="past-surgical-history"
        hint="Relevant prior surgical history (4,000 characters maximum)."
      >
        <Textarea
          id="past-surgical-history"
          className="min-h-[150px]"
          maxLength={4000}
          value={pastSurgicalHistory}
          onChange={(event) => onPastSurgicalHistoryChange(event.target.value)}
        />
      </Field>
      <Field
        label="Relevant Family History"
        htmlFor="family-history"
        hint="Relevant family history in the clinician's narrative (4,000 characters maximum)."
      >
        <Textarea
          id="family-history"
          className="min-h-[150px]"
          maxLength={4000}
          value={familyHistory}
          onChange={(event) => onFamilyHistoryChange(event.target.value)}
        />
      </Field>
      <Field
        label="Relevant Social History"
        htmlFor="social-history"
        hint="Relevant social or contextual history in the clinician's narrative (4,000 characters maximum)."
      >
        <Textarea
          id="social-history"
          className="min-h-[150px]"
          maxLength={4000}
          value={socialHistory}
          onChange={(event) => onSocialHistoryChange(event.target.value)}
        />
      </Field>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" disabled={savePending} onClick={onSave}>
          {savePending ? "Saving…" : "Save draft"}
        </Button>
        {saveState === "saved" ? (
          <span role="status" className="text-[12px] font-medium text-accent-teal">Draft saved.</span>
        ) : saveState === "unsaved" ? (
          <span role="status" className="text-[12px] font-medium text-accent-orange">Not saved — use Save draft.</span>
        ) : null}
      </div>
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
  const noteContentRef = useRef<ClinicalNoteContent>({});
  const encounterEtagRef = useRef<string | null>(null);
  const [presentingComplaint, setPresentingComplaint] = useState("");
  const [hpi, setHpi] = useState("");
  const [pastMedicalHistory, setPastMedicalHistory] = useState("");
  const [pastSurgicalHistory, setPastSurgicalHistory] = useState("");
  const [familyHistory, setFamilyHistory] = useState("");
  const [socialHistory, setSocialHistory] = useState("");
  const [draftSaveState, setDraftSaveState] = useState<"idle" | "unsaved" | "saved">("idle");
  const [activeSection, setActiveSection] = useState<WorkspaceSectionId>("summary");
  const [confirmingSign, setConfirmingSign] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const dirtyFieldsRef = useRef<Set<ClinicalNoteField>>(new Set());
  const draftValuesRef = useRef<EditableDraftValues>(emptyDraftValues());
  const draftSessionRef = useRef(0);

  const queue = useQuery({
    queryKey: ["queue", "TRIAGED,IN_CONSULTATION"],
    queryFn: () => apiRequest<QueueEntry[]>("/api/v1/clinic/queue/?status=TRIAGED,IN_CONSULTATION"),
    enabled: can("clinical.note.create"),
  });

  const selected = useMemo(
    () => (queue.data ?? []).find((entry) => entry.id === selectedId) ?? null,
    [queue.data, selectedId],
  );
  function hydrateNote(created: Encounter) {
    const draft = consultationDraftFromEncounter(created);
    const values = editableDraftValuesFromContent(draft.content);
    encounterEtagRef.current = created.consultation_etag ?? null;
    noteContentRef.current = draft.content;
    draftValuesRef.current = values;
    dirtyFieldsRef.current = new Set();
    draftSessionRef.current += 1;
    setPresentingComplaint(values.presentingComplaint);
    setHpi(values.hpi);
    setPastMedicalHistory(values.pastMedicalHistory);
    setPastSurgicalHistory(values.pastSurgicalHistory);
    setFamilyHistory(values.familyHistory);
    setSocialHistory(values.socialHistory);
    setNote(values.consultation);
    setDraftSaveState(Object.keys(draft.content).length > 0 ? "saved" : "idle");
  }

  function currentDraftMutation(rebaseAttempt = 0): DraftMutationVariables | null {
    const etag = encounterEtagRef.current;
    if (!encounter?.id || !etag) {
      setError("The current consultation revision is unavailable. Reload before saving.");
      return null;
    }
    const values = { ...draftValuesRef.current };
    const fields = Array.from(dirtyFieldsRef.current);
    return {
      content: noteContentForFields(values, fields),
      fields,
      values,
      encounterId: encounter.id,
      session: draftSessionRef.current,
      etag,
      rebaseAttempt,
    };
  }

  function selectEntry(entry: QueueEntry) {
    draftSessionRef.current += 1;
    noteContentRef.current = {};
    encounterEtagRef.current = null;
    draftValuesRef.current = emptyDraftValues();
    dirtyFieldsRef.current = new Set();
    setSelectedId(entry.id);
    setEncounter(null);
    setNote(DEFAULT_CONSULTATION_NOTE);
    setPresentingComplaint("");
    setHpi("");
    setPastMedicalHistory("");
    setPastSurgicalHistory("");
    setFamilyHistory("");
    setSocialHistory("");
    setDraftSaveState("idle");
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
      hydrateNote(created);
      setActiveSection("notes");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
    onError: (reason) => setError(errorMessage(reason)),
  });

  const saveDraft = useMutation<NoteSaveResponse, unknown, DraftMutationVariables>({
    mutationFn: ({ content, encounterId, etag }) =>
      apiRequest<NoteSaveResponse>(
        "/api/v1/clinic/encounters/" + encounterId + "/notes/",
        {
          method: "POST",
          headers: { "If-Match": etag },
          body: JSON.stringify({ content }),
        },
      ),
    onSuccess: (saved, variables) => {
      if (variables.session !== draftSessionRef.current) return;
      noteContentRef.current = saved.content;
      encounterEtagRef.current = saved.etag;
      for (const field of variables.fields) {
        const draftKey = FIELD_TO_DRAFT_VALUE[field];
        if (draftValuesRef.current[draftKey] === variables.values[draftKey]) {
          dirtyFieldsRef.current.delete(field);
        }
      }
      setDraftSaveState(dirtyFieldsRef.current.size > 0 ? "unsaved" : "saved");
      setNotice("Consultation draft saved.");
      setError("");
    },
    onError: (reason, variables) => {
      if (!variables || variables.session !== draftSessionRef.current) return;
      const conflict = clinicalNoteConflict(reason);
      if (!conflict) {
        setDraftSaveState("unsaved");
        setError(errorMessage(reason));
        return;
      }
      const remoteFields = changedClinicalFields(noteContentRef.current, conflict.content);
      const overlappingFields = remoteFields.filter((field) => dirtyFieldsRef.current.has(field));
      noteContentRef.current = conflict.content;
      encounterEtagRef.current = conflict.etag;
      if (["SIGNED", "CLOSED", "CANCELLED"].includes(conflict.encounter_status)) {
        setEncounter((current) => (current ? { ...current, status: conflict.encounter_status } : current));
      }
      if (
        overlappingFields.length === 0 &&
        variables.rebaseAttempt < 1 &&
        conflict.status === "DRAFT" &&
        conflict.encounter_status === "OPEN"
      ) {
        setError("");
        saveDraft.mutate({
          ...variables,
          etag: conflict.etag,
          rebaseAttempt: variables.rebaseAttempt + 1,
        });
        return;
      }
      setDraftSaveState("unsaved");
      setNotice("");
      setError(conflictMessage(remoteFields, overlappingFields, "save"));
    },
  });
  const signNote = useMutation<NoteSignResponse, unknown, DraftMutationVariables>({
    mutationFn: ({ content, encounterId, etag }) =>
      apiRequest<NoteSignResponse>("/api/v1/clinic/encounters/" + encounterId + "/sign/", {
        method: "POST",
        headers: { "If-Match": etag },
        body: JSON.stringify({ content }),
      }),
    onSuccess: (signed, variables) => {
      if (variables.session !== draftSessionRef.current) return;
      const signedDraft = editableDraftValuesFromContent(signed.content);
      noteContentRef.current = signed.content;
      encounterEtagRef.current = signed.etag;
      draftValuesRef.current = signedDraft;
      dirtyFieldsRef.current = new Set();
      setPresentingComplaint(signedDraft.presentingComplaint);
      setHpi(signedDraft.hpi);
      setPastMedicalHistory(signedDraft.pastMedicalHistory);
      setPastSurgicalHistory(signedDraft.pastSurgicalHistory);
      setFamilyHistory(signedDraft.familyHistory);
      setSocialHistory(signedDraft.socialHistory);
      setNote(signedDraft.consultation);
      setEncounter((current) => (current ? { ...current, status: "SIGNED" } : current));
      setDraftSaveState("saved");
      setConfirmingSign(false);
      setNotice("Consultation signed for " + (selected?.patient_name ?? "the patient") + ".");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
    onError: (reason, variables) => {
      if (!variables || variables.session !== draftSessionRef.current) return;
      const conflict = clinicalNoteConflict(reason);
      setConfirmingSign(false);
      if (!conflict) {
        setError(errorMessage(reason));
        return;
      }
      const remoteFields = changedClinicalFields(noteContentRef.current, conflict.content);
      const overlappingFields = remoteFields.filter((field) => dirtyFieldsRef.current.has(field));
      noteContentRef.current = conflict.content;
      encounterEtagRef.current = conflict.etag;
      if (["SIGNED", "CLOSED", "CANCELLED"].includes(conflict.encounter_status)) {
        setEncounter((current) => (current ? { ...current, status: conflict.encounter_status } : current));
      }
      setDraftSaveState("unsaved");
      setNotice("");
      setError(conflictMessage(remoteFields, overlappingFields, "sign"));
    },
  });
  function updateClinicalField(field: ClinicalNoteField, value: string, setValue: (value: string) => void) {
    setValue(value);
    draftValuesRef.current = {
      ...draftValuesRef.current,
      [FIELD_TO_DRAFT_VALUE[field]]: value,
    };
    dirtyFieldsRef.current.add(field);
    setDraftSaveState("unsaved");
    setNotice("");
  }

  function saveCurrentDraft() {
    const mutation = currentDraftMutation();
    if (mutation) saveDraft.mutate(mutation);
  }

  function signCurrentDraft() {
    const mutation = currentDraftMutation();
    if (mutation) signNote.mutate(mutation);
  }

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
                {activeSection === "history" ? (
                  !encounter ? (
                    <div className="space-y-3">
                      <p className="text-[12.5px] font-medium text-secondary">
                        Not recorded yet. Start the encounter to capture the presenting complaint and HPI.
                      </p>
                      <Button disabled={startEncounter.isPending} onClick={() => startEncounter.mutate()}>
                        {startEncounter.isPending ? "Starting…" : "Start encounter"}
                      </Button>
                    </div>
                  ) : (
                    <HistorySection
                      status={encounter.status}
                      presentingComplaint={presentingComplaint}
                      hpi={hpi}
                      pastMedicalHistory={pastMedicalHistory}
                      pastSurgicalHistory={pastSurgicalHistory}
                      familyHistory={familyHistory}
                      socialHistory={socialHistory}
                      onPresentingComplaintChange={(value) => updateClinicalField("presenting_complaint", value, setPresentingComplaint)}
                      onHpiChange={(value) => updateClinicalField("hpi", value, setHpi)}
                      onPastMedicalHistoryChange={(value) => updateClinicalField("past_medical_history", value, setPastMedicalHistory)}
                      onPastSurgicalHistoryChange={(value) => updateClinicalField("past_surgical_history", value, setPastSurgicalHistory)}
                      onFamilyHistoryChange={(value) => updateClinicalField("family_history", value, setFamilyHistory)}
                      onSocialHistoryChange={(value) => updateClinicalField("social_history", value, setSocialHistory)}
                      onSave={saveCurrentDraft}
                      savePending={saveDraft.isPending || signNote.isPending}
                      saveState={draftSaveState}
                    />
                  )
                ) : activeSection !== "notes" ? (
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
                        onChange={(event) => {
                           updateClinicalField("consultation", event.target.value, setNote);
                        }}
                      />
                    </Field>

                    <div className="flex flex-wrap items-center gap-3">
                      <Button variant="secondary" disabled={saveDraft.isPending || signNote.isPending} onClick={saveCurrentDraft}>
                        {saveDraft.isPending ? "Saving…" : "Save draft"}
                      </Button>
                      {draftSaveState === "saved" ? (
                        <span role="status" className="text-[12px] font-medium text-accent-teal">Draft saved.</span>
                      ) : draftSaveState === "unsaved" ? (
                        <span role="status" className="text-[12px] font-medium text-accent-orange">Not saved — use Save draft.</span>
                      ) : null}
                    </div>
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
                        <Button disabled={saveDraft.isPending || signNote.isPending} onClick={signCurrentDraft}>
                          {signNote.isPending ? "Signing…" : "Confirm signature"}
                        </Button>
                      </div>
                    ) : (
                      <Button disabled={saveDraft.isPending || signNote.isPending} onClick={() => setConfirmingSign(true)}>Sign consultation</Button>
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
