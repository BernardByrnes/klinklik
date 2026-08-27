"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, apiRequest } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import {
  ActiveAllergy,
  AllergyStatus,
  ClinicalNoteContent,
  Diagnosis,
  ComplaintDurationUnit,
  Encounter,
  EncounterDisposition,
  FollowUpRecommendation,
  PresentingComplaint,
  QueueEntry,
} from "../../../features/clinic";
import { AllergyBanner, type AllergyFormValues } from "../../../components/clinical/allergy-banner";
import {
  DiagnosisSection,
  emptyDiagnosisFormState,
  type DiagnosisFormState,
  type DiagnosisWritePayload,
} from "../../../components/clinical/diagnosis-section";
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
  Select,
  StatusBadge,
  TextInput,
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
type FoundationSectionId = Exclude<WorkspaceSectionId, "notes" | "treatment">;
const DEFAULT_CONSULTATION_NOTE = "Assessment: \nPlan: ";
const AUTOSAVE_DELAY_MS = 3000;
const RETRY_BACKOFF_MS = [2000, 5000, 10000, 20000, 30000] as const;
const TERMINAL_ENCOUNTER_STATUSES = ["SIGNED", "CLOSED", "CANCELLED"] as const;

const DISPOSITION_OPTIONS: Array<{ value: EncounterDisposition; label: string }> = [
  { value: "TREATED_AND_DISCHARGED", label: "Treated and discharged" },
  { value: "REVIEW_SCHEDULED", label: "Review scheduled" },
  { value: "REFERRED_OUT", label: "Referred out" },
  { value: "ADMITTED_ELSEWHERE", label: "Admitted elsewhere" },
  { value: "LEFT_AGAINST_ADVICE", label: "Left against advice" },
  { value: "DECEASED", label: "Deceased" },
  { value: "OTHER", label: "Other" },
];

type DraftSaveState = "idle" | "unsaved" | "saved" | "retrying";

type ConsultationDraft = {
  content: ClinicalNoteContent;
  complaints: PresentingComplaint[];
  triageComplaint: string | null;
  hpi: string;
  pastMedicalHistory: string;
  pastSurgicalHistory: string;
  familyHistory: string;
  socialHistory: string;
  generalExamination: string;
  cardiovascularExamination: string;
  respiratoryExamination: string;
  abdominalExamination: string;
  neurologicalExamination: string;
  genitourinaryExamination: string;
  musculoskeletalExamination: string;
  treatmentPlan: string;
  consultation: string;
};

type ClinicalNoteField =
  | "hpi"
  | "past_medical_history"
  | "past_surgical_history"
  | "family_history"
  | "social_history"
  | "general_examination"
  | "cardiovascular_examination"
  | "respiratory_examination"
  | "abdominal_examination"
  | "neurological_examination"
  | "genitourinary_examination"
  | "musculoskeletal_examination"
  | "treatment_plan"
  | "consultation";

type ExaminationField = Extract<
  ClinicalNoteField,
  | "general_examination"
  | "cardiovascular_examination"
  | "respiratory_examination"
  | "abdominal_examination"
  | "neurological_examination"
  | "genitourinary_examination"
  | "musculoskeletal_examination"
>;

const REVIEWED_NORMAL_SYSTEMS: Array<{ field: ExaminationField; label: string }> = [
  { field: "general_examination", label: "General" },
  { field: "cardiovascular_examination", label: "Cardiovascular" },
  { field: "respiratory_examination", label: "Respiratory" },
  { field: "abdominal_examination", label: "Abdominal / Gastrointestinal" },
  { field: "neurological_examination", label: "Neurological / CNS" },
  { field: "genitourinary_examination", label: "Genitourinary" },
  { field: "musculoskeletal_examination", label: "Musculoskeletal" },
];

const REVIEWED_NORMAL_TEMPLATES: Record<ExaminationField, string> = {
  general_examination: "Patient appears clinically well. No abnormal general findings noted.",
  cardiovascular_examination: "Cardiovascular examination: no abnormal findings noted.",
  respiratory_examination: "Respiratory examination: no abnormal findings noted.",
  abdominal_examination: "Abdominal examination: no abnormal findings noted.",
  neurological_examination: "Neurological examination: no abnormal findings noted.",
  genitourinary_examination: "Genitourinary examination: no abnormal findings noted.",
  musculoskeletal_examination: "Musculoskeletal examination: no abnormal findings noted.",
};

type EditableDraftValues = Pick<
  ConsultationDraft,
  "hpi" | "pastMedicalHistory" | "pastSurgicalHistory" | "familyHistory" | "socialHistory" | "generalExamination" | "cardiovascularExamination" | "respiratoryExamination" | "abdominalExamination" | "neurologicalExamination" | "genitourinaryExamination" | "musculoskeletalExamination" | "treatmentPlan" | "consultation"
>;

type DraftMutationVariables = {
  content: ClinicalNoteContent;
  fields: ClinicalNoteField[];
  values: EditableDraftValues;
  complaintSnapshot?: PresentingComplaint[];
  encounterId: string;
  session: number;
  etag: string;
  rebaseAttempt: number;
  origin: "manual" | "autosave";
};

type StartEncounterVariables = {
  queueEntryId: string;
  session: number;
};
type NoteSaveResponse = {
  note: string;
  status: string;
  content: ClinicalNoteContent;
  complaints: PresentingComplaint[];
  etag: string;
  saved_at: string;
};

type NoteSignResponse = NoteSaveResponse & {
  current_version: number;
};

type DispositionSaveState = "idle" | "unsaved" | "saved";

type DispositionSaveResponse = {
  disposition: EncounterDisposition | null;
  disposition_note: string;
  consultation_etag: string;
  encounter_status: string;
};

type FollowUpDraftValues = {
  recommendedDate: string;
  instructions: string;
};

type FollowUpSaveState = "idle" | "unsaved" | "saved";

type FollowUpContext = {
  patientId: string;
  encounterId: string;
  queueEntryId: string;
  session: number;
  etag: string;
};

type FollowUpMutationVariables = FollowUpContext & {
  values: FollowUpDraftValues;
};

type FollowUpSaveResponse = {
  follow_up: FollowUpRecommendation;
  consultation_etag: string;
  encounter_status: string;
};
type DispositionContext = {
  patientId: string;
  encounterId: string;
  queueEntryId: string;
  session: number;
  etag: string;
};

type DispositionMutationVariables = DispositionContext & {
  disposition: EncounterDisposition | null;
  disposition_note: string;
};

type AllergyStateResponse = {
  allergy_status: AllergyStatus;
  active_allergies: ActiveAllergy[];
  allergy_revision: number;
  allergy_state_etag: string;
  allergies_reviewed_at?: string | null;
  allergies_reviewed_revision?: number | null;
  allergies_review_is_current?: boolean;
};

type AllergyContext = {
  patientId: string;
  encounterId: string;
  queueEntryId: string;
  session: number;
  etag: string;
};

type AllergyStatusMutationVariables = AllergyContext & {
  status: Extract<AllergyStatus, "NKA" | "UNKNOWN">;
};

type AllergyAddMutationVariables = Omit<AllergyContext, "etag"> & {
  values: AllergyFormValues;
};

type AllergyEnteredInErrorMutationVariables = AllergyContext & {
  allergyId: string;
  reason: string;
};

type AllergyReviewMutationVariables = AllergyContext;
type DiagnosisStateResponse = {
  diagnoses: Diagnosis[];
  consultation_etag: string;
};

type DiagnosisConflictData = DiagnosisStateResponse & {
  detail: string;
  encounter_status: string;
};

type DiagnosisContext = {
  patientId: string;
  encounterId: string;
  queueEntryId: string;
  session: number;
  etag: string;
};

type DiagnosisMutationVariables = DiagnosisContext & {
  action: "create" | "update" | "remove";
  diagnosisId?: string;
  payload?: DiagnosisWritePayload;
};
const FIELD_TO_DRAFT_VALUE: Record<ClinicalNoteField, keyof EditableDraftValues> = {
  hpi: "hpi",
  past_medical_history: "pastMedicalHistory",
  past_surgical_history: "pastSurgicalHistory",
  family_history: "familyHistory",
  social_history: "socialHistory",
  general_examination: "generalExamination",
  cardiovascular_examination: "cardiovascularExamination",
  respiratory_examination: "respiratoryExamination",
  abdominal_examination: "abdominalExamination",
  neurological_examination: "neurologicalExamination",
  genitourinary_examination: "genitourinaryExamination",
  musculoskeletal_examination: "musculoskeletalExamination",
  treatment_plan: "treatmentPlan",
  consultation: "consultation",
};

const CLINICAL_NOTE_FIELDS: ClinicalNoteField[] = [
  "hpi",
  "past_medical_history",
  "past_surgical_history",
  "family_history",
  "social_history",
  "general_examination",
  "cardiovascular_examination",
  "respiratory_examination",
  "abdominal_examination",
  "neurological_examination",
  "genitourinary_examination",
  "musculoskeletal_examination",
  "treatment_plan",
  "consultation",
];

const CLINICAL_FIELD_LABELS: Record<ClinicalNoteField, string> = {
  hpi: "History of present illness",
  past_medical_history: "Past medical history",
  past_surgical_history: "Past surgical history",
  family_history: "Family history",
  social_history: "Social history",
  general_examination: "General examination",
  cardiovascular_examination: "Cardiovascular examination",
  respiratory_examination: "Respiratory examination",
  abdominal_examination: "Abdominal / Gastrointestinal examination",
  neurological_examination: "Neurological / CNS examination",
  genitourinary_examination: "Genitourinary examination",
  musculoskeletal_examination: "Musculoskeletal examination",
  treatment_plan: "Treatment plan",
  consultation: "Consultation note",
};

type ClinicalNoteConflictData = {
  etag: string;
  status: string;
  encounter_status: string;
  content: ClinicalNoteContent;
  complaints: PresentingComplaint[];
  diagnoses: Diagnosis[];
  saved_at: string | null;
  follow_up?: FollowUpRecommendation | null;
};
type DispositionConflictValues = {
  disposition: EncounterDisposition | null;
  disposition_note: string;
};


type ConflictComparisonValues = Partial<
  Record<ClinicalNoteField, { serverValue: string; localDirty: boolean }>
>;

function clinicalNoteConflict(error: unknown): ClinicalNoteConflictData | null {
  if (
    !(error instanceof ApiRequestError) ||
    ![409, 412].includes(error.status) ||
    typeof error.data !== "object" ||
    error.data === null
  ) {
    return null;
  }
  const data = error.data as Record<string, unknown>;
  if (
    typeof data.etag !== "string" ||
    typeof data.status !== "string" ||
    typeof data.encounter_status !== "string" ||
    typeof data.content !== "object" ||
    data.content === null ||
    !Array.isArray(data.complaints) ||
    !Array.isArray(data.diagnoses)
  ) {
    return null;
  }
  return {
    etag: data.etag,
    status: data.status,
    encounter_status: data.encounter_status,
    content: data.content as ClinicalNoteContent,
    complaints: data.complaints as PresentingComplaint[],
    diagnoses: data.diagnoses as Diagnosis[],
    saved_at: typeof data.saved_at === "string" ? data.saved_at : null,
    follow_up: "follow_up" in data ? data.follow_up as FollowUpRecommendation | null : undefined,
  };
}

function isRetryableDraftFailure(error: unknown) {
  if (error instanceof ApiRequestError) {
    return error.status >= 500 && error.status <= 599;
  }
  return error instanceof TypeError || (
    typeof DOMException !== "undefined" &&
    error instanceof DOMException &&
    error.name === "NetworkError"
  );
}

function isTerminalEncounterStatus(status: string) {
  return TERMINAL_ENCOUNTER_STATUSES.some((terminalStatus) => terminalStatus === status);
}

function allergyStateConflict(error: unknown): AllergyStateResponse | null {
  if (
    !(error instanceof ApiRequestError) ||
    error.status !== 412 ||
    typeof error.data !== "object" ||
    error.data === null
  ) {
    return null;
  }
  const data = error.data as Record<string, unknown>;
  if (
    typeof data.allergy_status !== "string" ||
    !Array.isArray(data.active_allergies) ||
    typeof data.allergy_revision !== "number" ||
    typeof data.allergy_state_etag !== "string"
  ) {
    return null;
  }
  return {
    allergy_status: data.allergy_status as AllergyStatus,
    active_allergies: data.active_allergies as ActiveAllergy[],
    allergy_revision: data.allergy_revision,
    allergy_state_etag: data.allergy_state_etag,
  };
}

function allergyMutationErrorMessage(error: unknown) {
  if (allergyStateConflict(error)) {
    return "Allergy information changed. Review the latest record before trying again.";
  }
  return errorMessage(error);
}

function signAllergyServerErrorMessage(error: unknown) {
  if (!(error instanceof ApiRequestError) || typeof error.data !== "object" || error.data === null) {
    return null;
  }
  const code = (error.data as Record<string, unknown>).code;
  if (code === "ALLERGY_STATUS_REQUIRED") return "Record the patient's allergy status before signing.";
  if (code === "ALLERGY_REVIEW_REQUIRED" || code === "ALLERGY_REVIEW_STALE") {
    return "Review the current allergy status before signing.";
  }
  return null;
}

function allergySignPrerequisiteMessage(encounter: Encounter | null) {
  if (!encounter || encounter.allergy_status === "NOT_RECORDED") {
    return "Record the patient's allergy status before signing.";
  }
  if (!encounter.allergies_review_is_current) {
    return "Review the current allergy status before signing.";
  }
  return null;
}
function diagnosisStateConflict(error: unknown): DiagnosisConflictData | null {
  if (
    !(error instanceof ApiRequestError) ||
    error.status !== 412 ||
    typeof error.data !== "object" ||
    error.data === null
  ) {
    return null;
  }
  const data = error.data as Record<string, unknown>;
  const etag = typeof data.consultation_etag === "string" ? data.consultation_etag : data.etag;
  if (
    typeof etag !== "string" ||
    typeof data.detail !== "string" ||
    typeof data.encounter_status !== "string" ||
    !Array.isArray(data.diagnoses)
  ) {
    return null;
  }
  return {
    diagnoses: data.diagnoses as Diagnosis[],
    consultation_etag: etag,
    detail: data.detail,
    encounter_status: data.encounter_status,
  };
}

function diagnosisMutationErrorMessage(error: unknown) {
  if (diagnosisStateConflict(error)) {
    return "This consultation changed elsewhere. Review the latest diagnoses before trying again.";
  }
  if (error instanceof ApiRequestError && typeof error.data === "object" && error.data !== null) {
    const code = (error.data as Record<string, unknown>).code;
    if (code === "DIAGNOSIS_LABEL_REQUIRED") return "Enter the diagnosis.";
    if (code === "NO_DIAGNOSIS_REASON_REQUIRED") return "Enter a reason for recording no final diagnosis.";
    if (code === "PRIMARY_DIAGNOSIS_INVALID") return "Only one final diagnosis can be primary.";
    if (code === "DIAGNOSIS_STATE_INVALID") return "The current final diagnosis state conflicts with this action. Review the diagnosis list first.";
    if (code === "DIAGNOSIS_IMMUTABLE") return "This encounter is signed and diagnoses can no longer be changed.";
  }
  return errorMessage(error);
}

function diagnosisSignPrerequisiteMessage(diagnoses: Diagnosis[]) {
  const finals = diagnoses.filter((diagnosis) => diagnosis.diagnosis_type === "FINAL");
  const noDiagnoses = diagnoses.filter((diagnosis) => diagnosis.diagnosis_type === "NO_DIAGNOSIS");
  if (finals.length > 0 && noDiagnoses.length > 0) {
    return "Review the final diagnosis state before signing.";
  }
  if (noDiagnoses.length > 0) {
    return noDiagnoses.length === 1 && Boolean(noDiagnoses[0].no_diagnosis_reason.trim())
      ? null
      : "Review the final diagnosis state before signing.";
  }
  if (finals.length === 0) return "Record a final diagnosis or document why no final diagnosis was reached before signing.";
  const primaryCount = finals.filter((diagnosis) => diagnosis.is_primary).length;
  if (primaryCount === 0) return "Choose one primary final diagnosis before signing.";
  if (primaryCount !== 1) return "Review the final diagnosis state before signing.";
  return null;
}

function diagnosisSignServerErrorMessage(error: unknown) {
  if (!(error instanceof ApiRequestError) || typeof error.data !== "object" || error.data === null) return null;
  const code = (error.data as Record<string, unknown>).code;
  if (code === "DIAGNOSIS_REQUIRED") return "Record a final diagnosis or document why no final diagnosis was reached before signing.";
  if (code === "PRIMARY_DIAGNOSIS_REQUIRED") return "Choose one primary final diagnosis before signing.";
  if (code === "PRIMARY_DIAGNOSIS_INVALID" || code === "DIAGNOSIS_STATE_INVALID") return "Review the final diagnosis state before signing.";
  return null;
}
function followUpDraftValues(followUp: FollowUpRecommendation | null | undefined): FollowUpDraftValues {
  return {
    recommendedDate: followUp?.recommended_date ?? "",
    instructions: followUp?.instructions ?? "",
  };
}

function followUpDraftsEqual(left: FollowUpDraftValues, right: FollowUpDraftValues) {
  return left.recommendedDate === right.recommendedDate && left.instructions === right.instructions;
}
function dispositionLabel(disposition: EncounterDisposition | null) {
  return DISPOSITION_OPTIONS.find((option) => option.value === disposition)?.label ?? "Not recorded";
}

function dispositionFormValidationMessage(disposition: EncounterDisposition | null, dispositionNote: string) {
  if (!disposition) return "Choose a disposition before signing.";
  if (disposition === "OTHER" && !dispositionNote.trim()) return "Enter a note for the Other disposition.";
  if (disposition === "REFERRED_OUT") return "Complete the referral record before signing.";
  return null;
}

function dispositionSignPrerequisiteMessage(
  disposition: EncounterDisposition | null,
  dispositionNote: string,
  followUpDate: string,
) {
  const formMessage = dispositionFormValidationMessage(disposition, dispositionNote);
  if (formMessage) return formMessage;
  if (disposition === "REVIEW_SCHEDULED" && !followUpDate) {
    return "Record the follow-up date before signing.";
  }
  return null;
}
function dispositionServerErrorMessage(error: unknown) {
  if (!(error instanceof ApiRequestError) || typeof error.data !== "object" || error.data === null) return null;
  const code = (error.data as Record<string, unknown>).code;
  if (code === "DISPOSITION_REQUIRED") return "Choose a disposition before signing.";
  if (code === "DISPOSITION_NOTE_REQUIRED") return "Enter a note for the Other disposition.";
  if (code === "REFERRAL_REQUIRED") return "Complete the referral record before signing.";
  if (code === "FOLLOW_UP_REQUIRED") return "Record the follow-up date before signing.";
  if (code === "DISPOSITION_IMMUTABLE") return "This encounter is closed and its disposition can no longer be changed.";
  return null;
}
const COMPLAINT_DURATION_UNITS: ComplaintDurationUnit[] = ["HOURS", "DAYS", "WEEKS", "MONTHS"];

function emptyComplaint(): PresentingComplaint {
  return { text: "", duration_value: null, duration_unit: null };
}

function cloneComplaints(complaints: PresentingComplaint[]): PresentingComplaint[] {
  return complaints.map((complaint) => ({ ...complaint }));
}

function complaintsEqual(left: PresentingComplaint[], right: PresentingComplaint[]) {
  return left.length === right.length && left.every((complaint, index) => {
    const other = right[index];
    return Boolean(other) &&
      complaint.text === other.text &&
      complaint.duration_value === other.duration_value &&
      complaint.duration_unit === other.duration_unit;
  });
}

function complaintRowValidationMessage(complaint: PresentingComplaint): string | null {
  if (complaint.text.trim().length === 0) return "Enter a presenting complaint.";
  if (complaint.text.length > 500) return "Keep this complaint to 500 characters or fewer.";
  const hasDurationValue = complaint.duration_value !== null;
  const hasDurationUnit = complaint.duration_unit !== null;
  if (hasDurationValue !== hasDurationUnit) {
    return "Enter both a positive duration and a duration unit, or leave both blank.";
  }
  if (hasDurationValue && (
    !Number.isFinite(complaint.duration_value) ||
    (complaint.duration_value as number) <= 0
  )) {
    return "Duration must be a positive number.";
  }
  if (hasDurationUnit && !COMPLAINT_DURATION_UNITS.includes(complaint.duration_unit as ComplaintDurationUnit)) {
    return "Choose a valid duration unit.";
  }
  return null;
}

function complaintsValidationMessage(complaints: PresentingComplaint[]): string | null {
  for (const complaint of complaints) {
    const message = complaintRowValidationMessage(complaint);
    if (message) return message;
  }
  return null;
}

const DURATION_LABELS: Record<ComplaintDurationUnit, { singular: string; plural: string }> = {
  HOURS: { singular: "hour", plural: "hours" },
  DAYS: { singular: "day", plural: "days" },
  WEEKS: { singular: "week", plural: "weeks" },
  MONTHS: { singular: "month", plural: "months" },
};

function complaintDurationLabel(complaint: PresentingComplaint) {
  if (complaint.duration_value === null || complaint.duration_unit === null) return "Duration not recorded";
  const labels = DURATION_LABELS[complaint.duration_unit];
  return complaint.duration_value + " " + (complaint.duration_value === 1 ? labels.singular : labels.plural);
}

function emptyFollowUpDraft(): FollowUpDraftValues {
  return { recommendedDate: "", instructions: "" };
}
function emptyDraftValues(): EditableDraftValues {
  return {
    hpi: "",
    pastMedicalHistory: "",
    pastSurgicalHistory: "",
    familyHistory: "",
    socialHistory: "",
    generalExamination: "",
    cardiovascularExamination: "",
    respiratoryExamination: "",
    abdominalExamination: "",
    neurologicalExamination: "",
    genitourinaryExamination: "",
    musculoskeletalExamination: "",
    treatmentPlan: "",
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
    hpi: contentText(content, "hpi"),
    pastMedicalHistory: contentText(content, "past_medical_history"),
    pastSurgicalHistory: contentText(content, "past_surgical_history"),
    familyHistory: contentText(content, "family_history"),
    socialHistory: contentText(content, "social_history"),
    generalExamination: contentText(content, "general_examination"),
    cardiovascularExamination: contentText(content, "cardiovascular_examination"),
    respiratoryExamination: contentText(content, "respiratory_examination"),
    abdominalExamination: contentText(content, "abdominal_examination"),
    neurologicalExamination: contentText(content, "neurological_examination"),
    genitourinaryExamination: contentText(content, "genitourinary_examination"),
    musculoskeletalExamination: contentText(content, "musculoskeletal_examination"),
    treatmentPlan: contentText(content, "treatment_plan"),
    consultation: consultation || assessmentPlan,
  };
}

function consultationDraftFromEncounter(encounter: Encounter): ConsultationDraft {
  const content = consultationContent(encounter);
  return {
    content,
    complaints: cloneComplaints(encounter.complaints ?? []),
    triageComplaint: encounter.triage_complaint ?? null,
    ...editableDraftValuesFromContent(content),
  };
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

function savedTimeLabel(savedAt: string | null) {
  if (!savedAt) return "Saved";
  const parsed = new Date(savedAt);
  if (Number.isNaN(parsed.getTime())) return "Saved";
  return "Saved " + parsed.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function DraftSaveStatus({ saveState, savedAt }: { saveState: DraftSaveState; savedAt: string | null }) {
  if (saveState === "saved") {
    return <span role="status" className="text-[12px] font-medium text-accent-teal">{savedTimeLabel(savedAt)}</span>;
  }
  if (saveState === "retrying") {
    return <span role="status" className="text-[12px] font-medium text-accent-orange">Not saved — retrying</span>;
  }
  if (saveState === "unsaved") {
    return <span role="status" className="text-[12px] font-medium text-accent-orange">Not saved — use Save draft.</span>;
  }
  return null;
}

function ConflictComparisonPanel({ values }: { values: ConflictComparisonValues }) {
  const fields = CLINICAL_NOTE_FIELDS.filter((field) => values[field]);
  if (fields.length === 0) return null;

  return (
    <div
      role="status"
      aria-label="Latest saved conflict values"
      className="space-y-3 rounded-[14px] border border-accent-orange/40 bg-accent-orange-soft px-4 py-3"
    >
      <p className="text-[12.5px] font-semibold text-ink">Latest saved values from another update</p>
      {fields.map((field) => {
        const comparison = values[field];
        if (!comparison) return null;
        return (
          <div key={field} className="rounded-[10px] border border-accent-orange/25 bg-white/70 px-3 py-2">
            <p className="text-[11.5px] font-semibold text-ink">
              Current saved value — {CLINICAL_FIELD_LABELS[field]}
            </p>
            <pre
              data-testid={"conflict-server-value-" + field}
              className="mt-1 whitespace-pre-wrap font-sans text-[12px] leading-relaxed text-secondary"
            >
              {comparison.serverValue || "Not recorded."}
            </pre>
            <p className="mt-1 text-[11.5px] font-medium text-muted">
              {comparison.localDirty
                ? "Your unsaved value remains in the editable field."
                : "This latest saved value is now reflected in the field."}
            </p>
          </div>
        );
      })}
    </div>
  );
}

const FOUNDATION_HINTS: Record<FoundationSectionId, string> = {
  summary: "Additional summary information is not available from the current consultation data.",
  history: "Start the encounter to capture the presenting complaint, HPI, and relevant past history.",
  examination: "Record the general physical examination in the clinician-authored note.",
  investigations: "Investigations are not implemented in this foundation phase.",
  diagnosis: "Start the encounter to record working, final, or no-final-diagnosis disposition.",
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


type ExaminationSectionProps = {
  status: string;
  generalExamination: string;
  cardiovascularExamination: string;
  respiratoryExamination: string;
  abdominalExamination: string;
  neurologicalExamination: string;
  genitourinaryExamination: string;
  musculoskeletalExamination: string;
  onGeneralExaminationChange: (value: string) => void;
  onCardiovascularExaminationChange: (value: string) => void;
  onRespiratoryExaminationChange: (value: string) => void;
  onAbdominalExaminationChange: (value: string) => void;
  onNeurologicalExaminationChange: (value: string) => void;
  onGenitourinaryExaminationChange: (value: string) => void;
  onMusculoskeletalExaminationChange: (value: string) => void;
  onSave: () => void;
  savePending: boolean;
  saveState: DraftSaveState;
  savedAt: string | null;
  reviewedNormalActionOpen: boolean;
  reviewedNormalSelection: ExaminationField[];
  isExaminationFieldUnavailable: (field: ExaminationField) => boolean;
  hasExaminationFieldValue: (field: ExaminationField) => boolean;
  onOpenReviewedNormalAction: () => void;
  onToggleReviewedNormalField: (field: ExaminationField) => void;
  onCancelReviewedNormalAction: () => void;
  onInsertReviewedNormalFindings: () => void;
};

function ExaminationSection({
  status,
  generalExamination,
  cardiovascularExamination,
  respiratoryExamination,
  abdominalExamination,
  neurologicalExamination,
  genitourinaryExamination,
  musculoskeletalExamination,
  onGeneralExaminationChange,
  onCardiovascularExaminationChange,
  onRespiratoryExaminationChange,
  onAbdominalExaminationChange,
  onNeurologicalExaminationChange,
  onGenitourinaryExaminationChange,
  onMusculoskeletalExaminationChange,
  onSave,
  savePending,
  saveState,
  savedAt,
  reviewedNormalActionOpen,
  reviewedNormalSelection,
  isExaminationFieldUnavailable,
  hasExaminationFieldValue,
  onOpenReviewedNormalAction,
  onToggleReviewedNormalField,
  onCancelReviewedNormalAction,
  onInsertReviewedNormalFindings,
}: ExaminationSectionProps) {
  const reviewedNormalHeadingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (!reviewedNormalActionOpen) return;
    reviewedNormalHeadingRef.current?.focus();
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") onCancelReviewedNormalAction();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [reviewedNormalActionOpen, onCancelReviewedNormalAction]);

  if (status === "SIGNED") {
    return (
      <div className="space-y-4">
        <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
          <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
          This Examination section is signed and immutable.
        </p>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">General Examination</h3>
          <p
            data-testid="general-examination-read-only"
            className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary"
          >
            {generalExamination || "Not recorded."}
          </p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Cardiovascular Examination</h3>
          <p
            data-testid="cardiovascular-examination-read-only"
            className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary"
          >
            {cardiovascularExamination || "Not recorded."}
          </p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Respiratory Examination</h3>
          <p
            data-testid="respiratory-examination-read-only"
            className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary"
          >
            {respiratoryExamination || "Not recorded."}
          </p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Abdominal / Gastrointestinal Examination</h3>
          <p
            data-testid="abdominal-examination-read-only"
            className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary"
          >
            {abdominalExamination || "Not recorded."}
          </p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Neurological / CNS Examination</h3>
          <p
            data-testid="neurological-examination-read-only"
            className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary"
          >
            {neurologicalExamination || "Not recorded."}
          </p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Genitourinary Examination</h3>
          <p
            data-testid="genitourinary-examination-read-only"
            className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary"
          >
            {genitourinaryExamination || "Not recorded."}
          </p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Musculoskeletal Examination</h3>
          <p
            data-testid="musculoskeletal-examination-read-only"
            className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary"
          >
            {musculoskeletalExamination || "Not recorded."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-[12.5px] font-medium text-secondary">
        Record clinician-authored examination findings only. No automated interpretation, suggestions, or normal-exam template is applied.
      </p>
      <div className="rounded-[14px] border border-line-soft bg-surface-muted p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-ink">Reviewed normal findings</p>
            <p className="mt-1 max-w-2xl text-[11.5px] font-medium leading-relaxed text-secondary">
              Select only systems you examined and reviewed as having no abnormal findings. Existing documentation will not be replaced.
            </p>
          </div>
          <Button variant="secondary" onClick={onOpenReviewedNormalAction}>
            Insert reviewed normal findings
          </Button>
        </div>
        {reviewedNormalActionOpen ? (
          <div
            data-testid="reviewed-normal-panel"
            role="dialog"
            aria-labelledby="reviewed-normal-heading"
            className="mt-4 rounded-[12px] border border-line bg-white p-4 shadow-card"
          >
            <h3
              ref={reviewedNormalHeadingRef}
              id="reviewed-normal-heading"
              tabIndex={-1}
              className="text-[13px] font-bold text-ink focus-visible:outline-none"
            >
              Reviewed normal examination
            </h3>
            <p className="mt-1 text-[11.5px] font-medium leading-relaxed text-secondary">
              Select only systems you examined and reviewed as having no abnormal findings. Existing documentation will not be replaced.
            </p>
            <div
              role="group"
              aria-label="Examination systems reviewed as normal"
              className="mt-4 grid gap-2 sm:grid-cols-2"
            >
              {REVIEWED_NORMAL_SYSTEMS.map((system) => {
                const unavailable = isExaminationFieldUnavailable(system.field);
                const checked = reviewedNormalSelection.includes(system.field);
                const statusId = `reviewed-normal-${system.field}-status`;
                return (
                  <div
                    key={system.field}
                    className="flex items-start gap-3 rounded-[10px] border border-line-soft bg-surface-muted px-3 py-2.5"
                  >
                    <input
                      id={`reviewed-normal-${system.field}`}
                      type="checkbox"
                      checked={checked}
                      disabled={unavailable}
                      onChange={() => onToggleReviewedNormalField(system.field)}
                      aria-describedby={statusId}
                      className="mt-0.5 h-4 w-4 rounded border-line text-primary focus:ring-primary"
                    />
                    <div className="min-w-0">
                      <label
                        htmlFor={`reviewed-normal-${system.field}`}
                        className={`block text-[12px] font-semibold ${unavailable ? "text-muted" : "text-ink"}`}
                      >
                        {system.label}
                      </label>
                      <span id={statusId} className="mt-0.5 block text-[10.5px] font-medium text-muted">
                        {unavailable
                          ? hasExaminationFieldValue(system.field)
                            ? "Already documented — not replaced."
                            : "Unsaved local documentation — not replaced."
                          : "Select to insert a concise reviewed-normal template."}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-4 flex flex-wrap justify-end gap-3">
              <Button variant="secondary" onClick={onCancelReviewedNormalAction}>
                Cancel
              </Button>
              <Button disabled={reviewedNormalSelection.length === 0} onClick={onInsertReviewedNormalFindings}>
                Insert selected findings
              </Button>
            </div>
          </div>
        ) : null}
      </div>
      <Field
        label="General Examination"
        htmlFor="general-examination"
        hint="General physical examination findings (2,000 characters maximum)."
      >
        <Textarea
          id="general-examination"
          className="min-h-[220px]"
          maxLength={2000}
          value={generalExamination}
          onChange={(event) => onGeneralExaminationChange(event.target.value)}
        />
      </Field>
      <Field
        label="Cardiovascular Examination"
        htmlFor="cardiovascular-examination"
        hint="Clinician-authored cardiovascular findings (2,000 characters maximum)."
      >
        <Textarea
          id="cardiovascular-examination"
          className="min-h-[220px]"
          maxLength={2000}
          value={cardiovascularExamination}
          onChange={(event) => onCardiovascularExaminationChange(event.target.value)}
        />
      </Field>
      <Field
        label="Respiratory Examination"
        htmlFor="respiratory-examination"
        hint="Clinician-authored respiratory findings (2,000 characters maximum)."
      >
        <Textarea
          id="respiratory-examination"
          className="min-h-[220px]"
          maxLength={2000}
          value={respiratoryExamination}
          onChange={(event) => onRespiratoryExaminationChange(event.target.value)}
        />
      </Field>
      <Field
        label="Abdominal / Gastrointestinal Examination"
        htmlFor="abdominal-examination"
        hint="Clinician-authored abdominal and gastrointestinal findings (2,000 characters maximum)."
      >
        <Textarea
          id="abdominal-examination"
          className="min-h-[220px]"
          maxLength={2000}
          value={abdominalExamination}
          onChange={(event) => onAbdominalExaminationChange(event.target.value)}
        />
      </Field>
      <Field
        label="Neurological / CNS Examination"
        htmlFor="neurological-examination"
        hint="Clinician-authored neurological and CNS findings (2,000 characters maximum)."
      >
        <Textarea
          id="neurological-examination"
          className="min-h-[220px]"
          maxLength={2000}
          value={neurologicalExamination}
          onChange={(event) => onNeurologicalExaminationChange(event.target.value)}
        />
      </Field>
      <Field
        label="Genitourinary Examination"
        htmlFor="genitourinary-examination"
        hint="Clinician-authored genitourinary findings (2,000 characters maximum)."
      >
        <Textarea
          id="genitourinary-examination"
          className="min-h-[220px]"
          maxLength={2000}
          value={genitourinaryExamination}
          onChange={(event) => onGenitourinaryExaminationChange(event.target.value)}
        />
      </Field>
      <Field
        label="Musculoskeletal Examination"
        htmlFor="musculoskeletal-examination"
        hint="Clinician-authored musculoskeletal findings (2,000 characters maximum)."
      >
        <Textarea
          id="musculoskeletal-examination"
          className="min-h-[220px]"
          maxLength={2000}
          value={musculoskeletalExamination}
          onChange={(event) => onMusculoskeletalExaminationChange(event.target.value)}
        />
      </Field>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" disabled={savePending} onClick={onSave}>
          {savePending ? "Saving..." : "Save draft"}
        </Button>
        <DraftSaveStatus saveState={saveState} savedAt={savedAt} />
      </div>
    </div>
  );
}

type HistorySectionProps = {
  status: string;
  complaints: PresentingComplaint[];
  triageComplaint: string | null;
  complaintConflict: PresentingComplaint[] | null;
  hpi: string;
  pastMedicalHistory: string;
  pastSurgicalHistory: string;
  familyHistory: string;
  socialHistory: string;
  onComplaintsChange: (value: PresentingComplaint[]) => void;
  onCopyTriage: () => void;
  onHpiChange: (value: string) => void;
  onPastMedicalHistoryChange: (value: string) => void;
  onPastSurgicalHistoryChange: (value: string) => void;
  onFamilyHistoryChange: (value: string) => void;
  onSocialHistoryChange: (value: string) => void;
  onSave: () => void;
  savePending: boolean;
  saveState: DraftSaveState;
  savedAt: string | null;
};

function ComplaintReadOnlyList({ complaints, testId }: { complaints: PresentingComplaint[]; testId?: string }) {
  if (complaints.length === 0) {
    return <p className="mt-2 text-[12.5px] leading-relaxed text-muted">No presenting complaints recorded.</p>;
  }
  return (
    <ol data-testid={testId} aria-label="Ordered presenting complaints" className="mt-2 space-y-2">
      {complaints.map((complaint, index) => (
        <li key={index} className="flex items-start gap-3 rounded-[10px] bg-surface-muted px-3 py-2.5">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[11px] font-bold text-primary">
            {index + 1}
          </span>
          <div className="min-w-0">
            <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-ink">{complaint.text}</p>
            <p className="mt-1 text-[11px] font-medium text-muted">{complaintDurationLabel(complaint)}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function HistorySection({
  status,
  complaints,
  triageComplaint,
  complaintConflict,
  hpi,
  pastMedicalHistory,
  pastSurgicalHistory,
  familyHistory,
  socialHistory,
  onComplaintsChange,
  onCopyTriage,
  onHpiChange,
  onPastMedicalHistoryChange,
  onPastSurgicalHistoryChange,
  onFamilyHistoryChange,
  onSocialHistoryChange,
  onSave,
  savePending,
  saveState,
  savedAt,
}: HistorySectionProps) {
  const visibleComplaints = complaints.length > 0 ? complaints : [emptyComplaint()];

  function updateComplaint(index: number, update: Partial<PresentingComplaint>) {
    const base = complaints.length > 0 ? complaints : [emptyComplaint()];
    const next = base.map((complaint, rowIndex) => rowIndex === index ? { ...complaint, ...update } : complaint);
    onComplaintsChange(next);
  }

  function removeComplaint(index: number) {
    if (complaints.length === 0) return;
    onComplaintsChange(complaints.filter((_, rowIndex) => rowIndex !== index));
  }

  function moveComplaint(index: number, direction: -1 | 1) {
    if (complaints.length === 0) return;
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= complaints.length) return;
    const next = cloneComplaints(complaints);
    const current = next[index];
    next[index] = next[nextIndex];
    next[nextIndex] = current;
    onComplaintsChange(next);
  }

  function addComplaint() {
    onComplaintsChange(complaints.length === 0 ? [emptyComplaint()] : [...complaints, emptyComplaint()]);
  }

  if (status === "SIGNED") {
    return (
      <div className="space-y-4">
        <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
          <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
          This History section is signed and immutable.
        </p>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Presenting complaints</h3>
          <ComplaintReadOnlyList complaints={complaints} testId="signed-presenting-complaints" />
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Triage complaint</h3>
          <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">
            {triageComplaint || "Not recorded."}
          </p>
          <p className="mt-1 text-[11px] font-medium text-muted">Triage context is shown separately and is not a structured complaint row.</p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">History of present illness (HPI)</h3>
          <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">{hpi || "Not recorded."}</p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Relevant Past Medical History</h3>
          <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">{pastMedicalHistory || "Not recorded."}</p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Relevant Past Surgical History</h3>
          <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">{pastSurgicalHistory || "Not recorded."}</p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Relevant Family History</h3>
          <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">{familyHistory || "Not recorded."}</p>
        </div>
        <div className="rounded-[14px] border border-line bg-white p-4">
          <h3 className="text-[13px] font-bold text-ink">Relevant Social History</h3>
          <p className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">{socialHistory || "Not recorded."}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-[12.5px] font-medium text-secondary">
        Record ordered patient-reported presenting complaints, the history of this illness, and relevant past history. This section does not add a diagnosis or treatment.
      </p>
      <section data-testid="presenting-complaints-editor" className="space-y-4 rounded-[14px] border border-line-soft bg-surface-muted p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-[13px] font-bold text-ink">Presenting complaints</h3>
            <p className="mt-1 text-[11.5px] font-medium leading-relaxed text-secondary">Add each complaint in the order it was reported. Text is preserved verbatim and is limited to 500 characters per row.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={addComplaint}>Add complaint</Button>
            <Button variant="secondary" disabled={!triageComplaint || triageComplaint.trim().length === 0} onClick={onCopyTriage}>Copy from triage</Button>
          </div>
        </div>
        <div className="rounded-[10px] border border-line bg-white px-3 py-2.5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">Triage complaint · context only</p>
          <p data-testid="triage-complaint" className="mt-1 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">{triageComplaint || "No triage complaint recorded."}</p>
          <p className="mt-1 text-[11px] font-medium text-muted">It is never copied automatically. Use Copy from triage to append it as a new row.</p>
        </div>
        {complaintConflict ? (
          <div data-testid="complaint-conflict" role="status" aria-label="Latest saved complaint values" className="space-y-3 rounded-[10px] border border-accent-orange/40 bg-accent-orange-soft px-3 py-3">
            <p className="text-[12px] font-semibold text-ink">Current saved complaints from another update</p>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-muted">Latest saved</p>
                <ComplaintReadOnlyList complaints={complaintConflict} />
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.06em] text-muted">Your unsaved draft</p>
                <ComplaintReadOnlyList complaints={complaints} />
              </div>
            </div>
            <p className="text-[11.5px] font-medium text-secondary">Review both versions, then choose Save draft explicitly if you intend to reconcile this conflict.</p>
          </div>
        ) : null}
        <ol aria-label="Presenting complaints" className="space-y-3">
          {visibleComplaints.map((complaint, index) => {
            const validation = complaints.length === 0 ? null : complaintRowValidationMessage(complaint);
            const errorId = "presenting-complaint-error-" + index;
            return (
              <li key={index} data-testid={"presenting-complaint-row-" + index} className="rounded-[12px] border border-line bg-white p-3">
                <div className="flex items-start gap-3">
                  <span aria-label={"Complaint order " + (index + 1)} className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[11px] font-bold text-primary">{index + 1}</span>
                  <div className="min-w-0 flex-1 space-y-3">
                    <Field label={"Presenting complaint " + (index + 1)} htmlFor={"presenting-complaint-" + index} hint="Patient-reported reason for the visit.">
                      <Textarea
                        id={"presenting-complaint-" + index}
                        aria-label={index === 0 ? "Presenting complaint" : "Presenting complaint " + (index + 1)}
                        aria-invalid={Boolean(validation)}
                        aria-describedby={validation ? errorId : undefined}
                        maxLength={500}
                        value={complaint.text}
                        onChange={(event) => updateComplaint(index, { text: event.target.value })}
                      />
                    </Field>
                    <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                      <Field label="Duration value" htmlFor={"presenting-complaint-duration-value-" + index} hint="Optional; must be positive when provided.">
                        <input
                          id={"presenting-complaint-duration-value-" + index}
                          aria-label={"Duration value for presenting complaint " + (index + 1)}
                          aria-invalid={Boolean(validation && (complaint.duration_value !== null || complaint.duration_unit !== null))}
                          type="number"
                          inputMode="decimal"
                          min="0"
                          step="any"
                          value={complaint.duration_value ?? ""}
                          onChange={(event) => updateComplaint(index, { duration_value: event.target.value === "" ? null : Number(event.target.value) })}
                          className="h-11 w-full rounded-[12px] border border-line bg-white px-3.5 text-[13px] font-medium text-ink shadow-card focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                        />
                      </Field>
                      <Field label="Duration unit" htmlFor={"presenting-complaint-duration-unit-" + index}>
                        <select
                          id={"presenting-complaint-duration-unit-" + index}
                          aria-label={"Duration unit for presenting complaint " + (index + 1)}
                          aria-invalid={Boolean(validation && (complaint.duration_value !== null || complaint.duration_unit !== null))}
                          value={complaint.duration_unit ?? ""}
                          onChange={(event) => updateComplaint(index, { duration_unit: event.target.value === "" ? null : event.target.value as ComplaintDurationUnit })}
                          className="h-11 w-full rounded-[12px] border border-line bg-white px-3.5 text-[13px] font-medium text-ink shadow-card focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                        >
                          <option value="">No duration recorded</option>
                          {COMPLAINT_DURATION_UNITS.map((unit) => <option key={unit} value={unit}>{unit}</option>)}
                        </select>
                      </Field>
                    </div>
                    {validation ? <p id={errorId} role="alert" className="text-[11.5px] font-medium text-accent-pink">{validation}</p> : null}
                    <div className="flex flex-wrap gap-2">
                      <Button variant="small-secondary" disabled={complaints.length === 0 || index === 0} onClick={() => moveComplaint(index, -1)} aria-label={"Move presenting complaint " + (index + 1) + " up"}>Move up</Button>
                      <Button variant="small-secondary" disabled={complaints.length === 0 || index === complaints.length - 1} onClick={() => moveComplaint(index, 1)} aria-label={"Move presenting complaint " + (index + 1) + " down"}>Move down</Button>
                      <Button variant="danger" disabled={complaints.length === 0} onClick={() => removeComplaint(index)} aria-label={"Remove presenting complaint " + (index + 1)}>Remove</Button>
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </section>
      <Field label="History of present illness (HPI)" htmlFor="history-of-present-illness" hint="Current illness history in the patient&apos;s account (4,000 characters maximum).">
        <Textarea id="history-of-present-illness" className="min-h-[180px]" maxLength={4000} value={hpi} onChange={(event) => onHpiChange(event.target.value)} />
      </Field>
      <Field label="Relevant Past Medical History" htmlFor="past-medical-history" hint="Relevant prior medical conditions or history (4,000 characters maximum).">
        <Textarea id="past-medical-history" className="min-h-[150px]" maxLength={4000} value={pastMedicalHistory} onChange={(event) => onPastMedicalHistoryChange(event.target.value)} />
      </Field>
      <Field label="Relevant Past Surgical History" htmlFor="past-surgical-history" hint="Relevant prior surgical history (4,000 characters maximum).">
        <Textarea id="past-surgical-history" className="min-h-[150px]" maxLength={4000} value={pastSurgicalHistory} onChange={(event) => onPastSurgicalHistoryChange(event.target.value)} />
      </Field>
      <Field label="Relevant Family History" htmlFor="family-history" hint="Relevant family history in the clinician&apos;s narrative (4,000 characters maximum).">
        <Textarea id="family-history" className="min-h-[150px]" maxLength={4000} value={familyHistory} onChange={(event) => onFamilyHistoryChange(event.target.value)} />
      </Field>
      <Field label="Relevant Social History" htmlFor="social-history" hint="Relevant social or contextual history in the clinician&apos;s narrative (4,000 characters maximum).">
        <Textarea id="social-history" className="min-h-[150px]" maxLength={4000} value={socialHistory} onChange={(event) => onSocialHistoryChange(event.target.value)} />
      </Field>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" disabled={savePending} onClick={onSave}>{savePending ? "Saving…" : "Save draft"}</Button>
        <DraftSaveStatus saveState={saveState} savedAt={savedAt} />
      </div>
    </div>
  );
}

type TreatmentSectionProps = {
  status: string;
  treatmentPlan: string;
  onTreatmentPlanChange: (value: string) => void;
  onSave: () => void;
  savePending: boolean;
  saveState: DraftSaveState;
  savedAt: string | null;
  disposition: EncounterDisposition | null;
  dispositionNote: string;
  followUp: FollowUpRecommendation | null;
  followUpRecommendedDate: string;
  followUpInstructions: string;
  followUpSaveState: FollowUpSaveState;
  followUpSavePending: boolean;
  followUpError: string;
  followUpConflict: FollowUpDraftValues | null;
  followUpFormDirty: boolean;
  followUpRevisionUncertain: boolean;
  onFollowUpRecommendedDateChange: (value: string) => void;
  onFollowUpInstructionsChange: (value: string) => void;
  onSaveFollowUp: () => void;
  onDiscardFollowUp: () => void;
  dispositionSaveState: DispositionSaveState;
  dispositionSavePending: boolean;
  dispositionError: string;
  dispositionConflict: DispositionConflictValues | null;
  dispositionFormDirty: boolean;
  dispositionRevisionUncertain: boolean;
  onDispositionChange: (value: EncounterDisposition | null) => void;
  onDispositionNoteChange: (value: string) => void;
  onSaveDisposition: () => void;
  onDiscardDisposition: () => void;
};

function DispositionSection({
  status,
  disposition,
  dispositionNote,
  followUp,
  dispositionSaveState,
  dispositionSavePending,
  dispositionError,
  dispositionConflict,
  dispositionFormDirty,
  dispositionRevisionUncertain,
  onDispositionChange,
  onDispositionNoteChange,
  onSaveDisposition,
  onDiscardDisposition,
}: Pick<
  TreatmentSectionProps,
  | "status"
  | "disposition"
  | "dispositionNote"
  | "followUp"
  | "dispositionSaveState"
  | "dispositionSavePending"
  | "dispositionError"
  | "dispositionConflict"
  | "dispositionFormDirty"
  | "dispositionRevisionUncertain"
  | "onDispositionChange"
  | "onDispositionNoteChange"
  | "onSaveDisposition"
  | "onDiscardDisposition"
>) {
  const readOnly = isTerminalEncounterStatus(status);
  const disabled = readOnly || dispositionSavePending || dispositionRevisionUncertain;

  return (
    <section data-testid="disposition-section" className="space-y-4 rounded-[14px] border border-line-soft bg-surface-muted p-4">
      <div>
        <h3 className="text-[13px] font-bold text-ink">Disposition</h3>
        <p className="mt-1 text-[11.5px] font-medium leading-relaxed text-secondary">
          Record the selected outcome for this encounter before signing.
        </p>
      </div>

      {readOnly ? (
        <div data-testid="disposition-read-only" className="rounded-[12px] border border-line bg-white p-3">
          <p className="text-[11.5px] font-semibold text-muted">Saved disposition</p>
          <p data-testid="disposition-read-only-value" className="mt-1 text-[13px] font-semibold text-ink">
            {dispositionLabel(disposition)}
          </p>
          {dispositionNote ? (
            <div className="mt-3 border-t border-line-soft pt-3">
              <p className="text-[11.5px] font-semibold text-muted">Disposition note</p>
              <p data-testid="disposition-read-only-note" className="mt-1 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">
                {dispositionNote}
              </p>
            </div>
          ) : null}
        </div>
      ) : (
        <>
          <Field
            label="Disposition"
            htmlFor="disposition"
            hint="Choose deliberately; no disposition is selected by default."
          >
            <Select
              id="disposition"
              aria-label="Disposition"
              value={disposition ?? ""}
              disabled={disabled}
              onChange={(event) => {
                const value = event.target.value;
                onDispositionChange(value ? value as EncounterDisposition : null);
              }}
            >
              <option value="">Choose a disposition</option>
              {DISPOSITION_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </Select>
          </Field>

          {disposition === "OTHER" ? (
            <Field
              label="Disposition note"
              htmlFor="disposition-note"
              hint="Required for Other; maximum 1000 characters."
            >
              <Textarea
                id="disposition-note"
                aria-label="Disposition note"
                aria-required="true"
                maxLength={1000}
                value={dispositionNote}
                disabled={disabled}
                onChange={(event) => onDispositionNoteChange(event.target.value)}
              />
            </Field>
          ) : null}

          {disposition === "REFERRED_OUT" ? (
            <p data-testid="disposition-referral-notice" role="status" className="rounded-[10px] border border-accent-orange/40 bg-accent-orange-soft px-3 py-2 text-[12px] font-medium text-ink">
              A referral record is required before this encounter can be signed.
            </p>
          ) : null}
          {disposition === "REVIEW_SCHEDULED" && !followUp?.recommended_date ? (
            <p data-testid="disposition-follow-up-notice" role="status" className="rounded-[10px] border border-accent-orange/40 bg-accent-orange-soft px-3 py-2 text-[12px] font-medium text-ink">
              A follow-up date is required before this encounter can be signed.
            </p>
          ) : null}

          {dispositionConflict ? (
            <div data-testid="disposition-conflict" role="status" className="space-y-2 rounded-[10px] border border-accent-orange/40 bg-accent-orange-soft px-3 py-3">
              <p className="text-[12px] font-semibold text-ink">Current saved disposition from another update</p>
              <p className="text-[12px] text-secondary">{dispositionLabel(dispositionConflict.disposition)}</p>
              {dispositionConflict.disposition_note ? (
                <p className="whitespace-pre-wrap text-[12px] text-secondary">{dispositionConflict.disposition_note}</p>
              ) : null}
              <p className="text-[11.5px] font-medium text-muted">Your unsaved disposition remains selected above.</p>
            </div>
          ) : null}

          {dispositionRevisionUncertain ? (
            <p role="alert" className="text-[12px] font-medium text-accent-orange">
              The latest consultation state could not be loaded. Reload before trying the disposition again.
            </p>
          ) : null}
          {dispositionError ? (
            <p data-testid="disposition-error" role="alert" className="text-[12px] font-medium text-accent-orange">
              {dispositionError}
            </p>
          ) : null}

          <div className="flex flex-wrap items-center gap-3">
            <Button disabled={disabled} onClick={onSaveDisposition}>
              {dispositionSavePending ? "Saving disposition…" : "Save disposition"}
            </Button>
            {dispositionFormDirty ? (
              <Button variant="secondary" disabled={dispositionSavePending} onClick={onDiscardDisposition}>
                Cancel changes
              </Button>
            ) : null}
            {dispositionSaveState === "saved" ? (
              <span role="status" className="text-[12px] font-medium text-accent-teal">Disposition saved.</span>
            ) : null}
          </div>
        </>
      )}
    </section>
  );
}

type FollowUpSectionProps = {
  status: string;
  recommendedDate: string;
  instructions: string;
  saveState: FollowUpSaveState;
  savePending: boolean;
  error: string;
  conflict: FollowUpDraftValues | null;
  formDirty: boolean;
  revisionUncertain: boolean;
  onRecommendedDateChange: (value: string) => void;
  onInstructionsChange: (value: string) => void;
  onSave: () => void;
  onDiscard: () => void;
};

function FollowUpSection({
  status,
  recommendedDate,
  instructions,
  saveState,
  savePending,
  error,
  conflict,
  formDirty,
  revisionUncertain,
  onRecommendedDateChange,
  onInstructionsChange,
  onSave,
  onDiscard,
}: FollowUpSectionProps) {
  const readOnly = isTerminalEncounterStatus(status);
  const disabled = readOnly || savePending || revisionUncertain;

  return (
    <section data-testid="follow-up-section" className="space-y-4 rounded-[14px] border border-line-soft bg-surface-muted p-4">
      <div>
        <h3 className="text-[13px] font-bold text-ink">Follow-up</h3>
        <p className="mt-1 text-[11.5px] font-medium leading-relaxed text-secondary">
          Record the recommended review date and clinician instructions for this encounter.
        </p>
      </div>

      {readOnly ? (
        <div data-testid="follow-up-read-only" className="rounded-[12px] border border-line bg-white p-3">
          <p className="text-[11.5px] font-semibold text-muted">Saved follow-up date</p>
          <p data-testid="follow-up-read-only-date" className="mt-1 text-[13px] font-semibold text-ink">
            {recommendedDate || "Not recorded"}
          </p>
          {instructions ? (
            <div className="mt-3 border-t border-line-soft pt-3">
              <p className="text-[11.5px] font-semibold text-muted">Instructions</p>
              <p data-testid="follow-up-read-only-instructions" className="mt-1 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary">
                {instructions}
              </p>
            </div>
          ) : null}
        </div>
      ) : (
        <>
          <Field
            label="Follow-up date"
            htmlFor="follow-up-date"
            hint="Choose the date the patient should return for review."
          >
            <TextInput
              id="follow-up-date"
              type="date"
              aria-label="Follow-up date"
              required
              value={recommendedDate}
              disabled={disabled}
              onChange={(event) => onRecommendedDateChange(event.target.value)}
            />
          </Field>

          <Field
            label="Instructions"
            htmlFor="follow-up-instructions"
            hint="Clinician-authored follow-up instructions."
          >
            <Textarea
              id="follow-up-instructions"
              aria-label="Instructions"
              className="min-h-[150px]"
              value={instructions}
              disabled={disabled}
              onChange={(event) => onInstructionsChange(event.target.value)}
            />
          </Field>

          {conflict ? (
            <div data-testid="follow-up-conflict" role="status" className="space-y-2 rounded-[10px] border border-accent-orange/40 bg-accent-orange-soft px-3 py-3">
              <p className="text-[12px] font-semibold text-ink">Current saved follow-up from another update</p>
              <p className="text-[12px] text-secondary">Date: {conflict.recommendedDate || "Not recorded"}</p>
              {conflict.instructions ? (
                <p className="whitespace-pre-wrap text-[12px] text-secondary">{conflict.instructions}</p>
              ) : null}
              <p className="text-[11.5px] font-medium text-muted">Your unsaved follow-up remains above.</p>
            </div>
          ) : null}

          {revisionUncertain ? (
            <p role="alert" className="text-[12px] font-medium text-accent-orange">
              The latest consultation state could not be loaded. Reload before trying the follow-up again.
            </p>
          ) : null}
          {error ? (
            <p data-testid="follow-up-error" role="alert" className="text-[12px] font-medium text-accent-orange">
              {error}
            </p>
          ) : null}

          <div className="flex flex-wrap items-center gap-3">
            <Button disabled={disabled} onClick={onSave}>
              {savePending ? "Saving follow-up…" : "Save follow-up"}
            </Button>
            {formDirty ? (
              <Button variant="secondary" disabled={savePending} onClick={onDiscard}>
                Cancel changes
              </Button>
            ) : null}
            {saveState === "saved" ? (
              <span role="status" className="text-[12px] font-medium text-accent-teal">Follow-up saved.</span>
            ) : null}
          </div>
        </>
      )}
    </section>
  );
}
function TreatmentSection({
  status,
  treatmentPlan,
  onTreatmentPlanChange,
  onSave,
  savePending,
  saveState,
  savedAt,
  disposition,
  dispositionNote,
  followUp,
  followUpRecommendedDate,
  followUpInstructions,
  followUpSaveState,
  followUpSavePending,
  followUpError,
  followUpConflict,
  followUpFormDirty,
  followUpRevisionUncertain,
  onFollowUpRecommendedDateChange,
  onFollowUpInstructionsChange,
  onSaveFollowUp,
  onDiscardFollowUp,
  dispositionSaveState,
  dispositionSavePending,
  dispositionError,
  dispositionConflict,
  dispositionFormDirty,
  dispositionRevisionUncertain,
  onDispositionChange,
  onDispositionNoteChange,
  onSaveDisposition,
  onDiscardDisposition,
}: TreatmentSectionProps) {
  return (
    <div data-testid="treatment-plan-section" className="space-y-6">
      {status === "SIGNED" ? (
        <>
          <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
            <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
            This Treatment plan is signed and immutable.
          </p>
          <div className="rounded-[14px] border border-line bg-white p-4">
            <h3 className="text-[13px] font-bold text-ink">Treatment plan</h3>
            <p
              data-testid="treatment-plan-read-only"
              className="mt-2 whitespace-pre-wrap text-[12.5px] leading-relaxed text-secondary"
            >
              {treatmentPlan || "Not recorded."}
            </p>
          </div>
        </>
      ) : (
        <>
          <p className="text-[12.5px] font-medium text-secondary">
            Record clinician-authored treatment instructions only. Prescriptions, procedures, investigations, referrals, and follow-up are separate workflows.
          </p>
          <Field
            label="Treatment plan"
            htmlFor="treatment-plan"
            hint="Free-text treatment plan or clinical instructions (4,000 characters maximum)."
          >
            <Textarea
              id="treatment-plan"
              className="min-h-[220px]"
              maxLength={4000}
              value={treatmentPlan}
              onChange={(event) => onTreatmentPlanChange(event.target.value)}
            />
          </Field>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="secondary" disabled={savePending} onClick={onSave}>
              {savePending ? "Saving..." : "Save draft"}
            </Button>
            <DraftSaveStatus saveState={saveState} savedAt={savedAt} />
          </div>
        </>
      )}

      <DispositionSection
        status={status}
        disposition={disposition}
        dispositionNote={dispositionNote}
        followUp={followUp}
        dispositionSaveState={dispositionSaveState}
        dispositionSavePending={dispositionSavePending}
        dispositionError={dispositionError}
        dispositionConflict={dispositionConflict}
        dispositionFormDirty={dispositionFormDirty}
        dispositionRevisionUncertain={dispositionRevisionUncertain}
        onDispositionChange={onDispositionChange}
        onDispositionNoteChange={onDispositionNoteChange}
        onSaveDisposition={onSaveDisposition}
        onDiscardDisposition={onDiscardDisposition}
      />
      <FollowUpSection
        status={status}
        recommendedDate={followUpRecommendedDate}
        instructions={followUpInstructions}
        saveState={followUpSaveState}
        savePending={followUpSavePending}
        error={followUpError}
        conflict={followUpConflict}
        formDirty={followUpFormDirty}
        revisionUncertain={followUpRevisionUncertain}
        onRecommendedDateChange={onFollowUpRecommendedDateChange}
        onInstructionsChange={onFollowUpInstructionsChange}
        onSave={onSaveFollowUp}
        onDiscard={onDiscardFollowUp}
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
  const selectedQueueEntryIdRef = useRef<string | null>(preselectedId);
  const [encounter, setEncounter] = useState<Encounter | null>(null);
  const [note, setNote] = useState(DEFAULT_CONSULTATION_NOTE);
  const noteContentRef = useRef<ClinicalNoteContent>({});
  const encounterEtagRef = useRef<string | null>(null);
  const [complaints, setComplaints] = useState<PresentingComplaint[]>([]);
  const [triageComplaint, setTriageComplaint] = useState<string | null>(null);
  const [hpi, setHpi] = useState("");
  const [pastMedicalHistory, setPastMedicalHistory] = useState("");
  const [pastSurgicalHistory, setPastSurgicalHistory] = useState("");
  const [familyHistory, setFamilyHistory] = useState("");
  const [socialHistory, setSocialHistory] = useState("");
  const [generalExamination, setGeneralExamination] = useState("");
  const [cardiovascularExamination, setCardiovascularExamination] = useState("");
  const [respiratoryExamination, setRespiratoryExamination] = useState("");
  const [abdominalExamination, setAbdominalExamination] = useState("");
  const [neurologicalExamination, setNeurologicalExamination] = useState("");
  const [genitourinaryExamination, setGenitourinaryExamination] = useState("");
  const [musculoskeletalExamination, setMusculoskeletalExamination] = useState("");
  const [treatmentPlan, setTreatmentPlan] = useState("");
  const [disposition, setDisposition] = useState<EncounterDisposition | null>(null);
  const [dispositionNote, setDispositionNote] = useState("");
  const [dispositionSaveState, setDispositionSaveState] = useState<DispositionSaveState>("idle");
  const [dispositionError, setDispositionError] = useState("");
  const [dispositionConflict, setDispositionConflict] = useState<DispositionConflictValues | null>(null);
  const [dispositionFormDirty, setDispositionFormDirty] = useState(false);
  const [followUpRecommendedDate, setFollowUpRecommendedDate] = useState("");
  const [followUpInstructions, setFollowUpInstructions] = useState("");
  const [followUpSaveState, setFollowUpSaveState] = useState<FollowUpSaveState>("idle");
  const [followUpError, setFollowUpError] = useState("");
  const [followUpConflict, setFollowUpConflict] = useState<FollowUpDraftValues | null>(null);
  const [followUpFormDirty, setFollowUpFormDirty] = useState(false);
  const [consultationRevisionUncertain, setConsultationRevisionUncertain] = useState(false);
  const [draftSaveState, setDraftSaveState] = useState<DraftSaveState>("idle");
  const [activeSection, setActiveSection] = useState<WorkspaceSectionId>("summary");
  const [confirmingSign, setConfirmingSign] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [allergyMutationError, setAllergyMutationError] = useState("");
  const [conflictComparison, setConflictComparison] = useState<ConflictComparisonValues>({});
  const [complaintConflict, setComplaintConflict] = useState<PresentingComplaint[] | null>(null);
  const [reviewedNormalActionOpen, setReviewedNormalActionOpen] = useState(false);
  const [reviewedNormalSelection, setReviewedNormalSelection] = useState<ExaminationField[]>([]);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [diagnosisFormState, setDiagnosisFormState] = useState<DiagnosisFormState>(emptyDiagnosisFormState());
  const [diagnosisMutationError, setDiagnosisMutationError] = useState("");
  const [diagnosisMutationBusy, setDiagnosisMutationBusy] = useState(false);
  const autosaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryAttemptRef = useRef(0);
  const retryActiveRef = useRef(false);
  const retryAttemptRunnerRef = useRef<() => void>(() => undefined);
  const offlineRef = useRef(false);
  const autosaveBlockedRef = useRef(false);
  const autosaveDeferredRef = useRef(false);
  const clinicalMutationInFlightRef = useRef(false);
  const dirtyFieldsRef = useRef<Set<ClinicalNoteField>>(new Set());
  const complaintsDraftRef = useRef<PresentingComplaint[]>([]);
  const authoritativeComplaintsRef = useRef<PresentingComplaint[]>([]);
  const complaintsDirtyRef = useRef(false);
  const draftValuesRef = useRef<EditableDraftValues>(emptyDraftValues());
  const draftSessionRef = useRef(0);
  const allergyFormDirtyRef = useRef(false);
  const allergyMutationInFlightRef = useRef(false);
  const diagnosisFormDirtyRef = useRef(false);
  const diagnosisMutationInFlightRef = useRef(false);
  const diagnosisReconciliationInFlightRef = useRef(false);
  const activePatientIdRef = useRef<string | null>(null);
  const activeEncounterIdRef = useRef<string | null>(null);
  const signGuardErrorRef = useRef<string | null>(null);
  const dispositionDraftRef = useRef<EncounterDisposition | null>(null);
  const dispositionNoteDraftRef = useRef("");
  const authoritativeDispositionRef = useRef<EncounterDisposition | null>(null);
  const authoritativeDispositionNoteRef = useRef("");
  const dispositionFormDirtyRef = useRef(false);
  const dispositionMutationInFlightRef = useRef(false);
  const dispositionReconciliationInFlightRef = useRef(false);
  const followUpDraftRef = useRef<FollowUpDraftValues>(emptyFollowUpDraft());
  const authoritativeFollowUpRef = useRef<FollowUpDraftValues>(emptyFollowUpDraft());
  const followUpFormDirtyRef = useRef(false);
  const followUpMutationInFlightRef = useRef(false);
  const followUpReconciliationInFlightRef = useRef(false);

  function hasDirtyDraft() {
    return dirtyFieldsRef.current.size > 0 || complaintsDirtyRef.current;
  }

  useEffect(() => () => {
    if (autosaveTimerRef.current !== null) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    retryActiveRef.current = false;
    retryAttemptRef.current = 0;
    allergyFormDirtyRef.current = false;
    allergyMutationInFlightRef.current = false;
    diagnosisFormDirtyRef.current = false;
    diagnosisMutationInFlightRef.current = false;
    diagnosisReconciliationInFlightRef.current = false;
    activePatientIdRef.current = null;
    activeEncounterIdRef.current = null;
    signGuardErrorRef.current = null;
    dispositionFormDirtyRef.current = false;
    dispositionMutationInFlightRef.current = false;
    dispositionReconciliationInFlightRef.current = false;
    followUpFormDirtyRef.current = false;
    followUpMutationInFlightRef.current = false;
    followUpReconciliationInFlightRef.current = false;
    followUpDraftRef.current = emptyFollowUpDraft();
    authoritativeFollowUpRef.current = emptyFollowUpDraft();
    dispositionDraftRef.current = null;
    dispositionNoteDraftRef.current = "";
    authoritativeDispositionRef.current = null;
    authoritativeDispositionNoteRef.current = "";
    draftSessionRef.current += 1;
  }, []);

  const hasUnsavedContent = useCallback(() => {
    return dirtyFieldsRef.current.size > 0 || complaintsDirtyRef.current || allergyFormDirtyRef.current || diagnosisFormDirtyRef.current || dispositionFormDirtyRef.current || followUpFormDirtyRef.current;
  }, []);

  const queue = useQuery({
    queryKey: ["queue", "TRIAGED,IN_CONSULTATION"],
    queryFn: () => apiRequest<QueueEntry[]>("/api/v1/clinic/queue/?status=TRIAGED,IN_CONSULTATION"),
    enabled: can("clinical.note.create"),
  });

  const selected = useMemo(
    () => (queue.data ?? []).find((entry) => entry.id === selectedId) ?? null,
    [queue.data, selectedId],
  );
  function applyAllergySnapshot(snapshot: AllergyStateResponse) {
    setEncounter((current) => {
      if (!current || current.id !== activeEncounterIdRef.current) return current;
      const reviewedAt = snapshot.allergies_reviewed_at !== undefined
        ? snapshot.allergies_reviewed_at
        : current.allergies_reviewed_at;
      const reviewedRevision = snapshot.allergies_reviewed_revision !== undefined
        ? snapshot.allergies_reviewed_revision
        : current.allergies_reviewed_revision;
      const reviewIsCurrent = snapshot.allergies_review_is_current ?? (
        snapshot.allergy_status !== "NOT_RECORDED" &&
        reviewedAt !== null &&
        reviewedRevision === snapshot.allergy_revision
      );
      return {
        ...current,
        allergy_status: snapshot.allergy_status,
        active_allergies: snapshot.active_allergies,
        allergy_revision: snapshot.allergy_revision,
        allergy_state_etag: snapshot.allergy_state_etag,
        allergies_reviewed_at: reviewedAt ?? null,
        allergies_reviewed_revision: reviewedRevision ?? null,
        allergies_review_is_current: reviewIsCurrent,
      };
    });
  }

  function applyDiagnosisSnapshot(diagnoses: Diagnosis[], etag?: string, encounterStatus?: string) {
    if (etag && activeEncounterIdRef.current) encounterEtagRef.current = etag;
    setEncounter((current) => {
      if (!current || current.id !== activeEncounterIdRef.current) return current;
      return {
        ...current,
        diagnoses,
        ...(etag ? { consultation_etag: etag } : {}),
        ...(encounterStatus ? { status: encounterStatus } : {}),
      };
    });
  }

  function currentDiagnosisContext(): DiagnosisContext | null {
    if (!encounter?.id || !selected?.patient || !encounterEtagRef.current) {
      setDiagnosisMutationError("The current consultation revision is unavailable. Reload before changing diagnoses.");
      return null;
    }
    if (consultationRevisionUncertain) {
      setDiagnosisMutationError("Reload before changing diagnoses because the latest consultation revision is uncertain.");
      return null;
    }
    return {
      patientId: selected.patient,
      encounterId: encounter.id,
      queueEntryId: selected.id,
      session: draftSessionRef.current,
      etag: encounterEtagRef.current,
    };
  }

  function isCurrentDiagnosisMutation(variables: Pick<DiagnosisContext, "session" | "patientId" | "encounterId" | "queueEntryId">) {
    return (
      variables.session === draftSessionRef.current &&
      variables.patientId === activePatientIdRef.current &&
      variables.encounterId === activeEncounterIdRef.current &&
      variables.queueEntryId === selectedQueueEntryIdRef.current
    );
  }
  function currentDispositionContext(): DispositionContext | null {
    if (!encounter?.id || !selected?.patient || !encounterEtagRef.current) {
      setDispositionError("The current consultation revision is unavailable. Reload before saving the disposition.");
      return null;
    }
    if (consultationRevisionUncertain) {
      setDispositionError("Reload before saving the disposition because the latest consultation revision is uncertain.");
      return null;
    }
    return {
      patientId: selected.patient,
      encounterId: encounter.id,
      queueEntryId: selected.id,
      session: draftSessionRef.current,
      etag: encounterEtagRef.current,
    };
  }

  function isCurrentDispositionMutation(variables: Pick<DispositionContext, "session" | "patientId" | "encounterId" | "queueEntryId">) {
    return (
      variables.session === draftSessionRef.current &&
      variables.patientId === activePatientIdRef.current &&
      variables.encounterId === activeEncounterIdRef.current &&
      variables.queueEntryId === selectedQueueEntryIdRef.current
    );
  }

  function currentFollowUpContext(): FollowUpContext | null {
    if (!encounter?.id || !selected?.patient || !encounterEtagRef.current) {
      setFollowUpError("The current consultation revision is unavailable. Reload before saving the follow-up.");
      return null;
    }
    if (consultationRevisionUncertain) {
      setFollowUpError("Reload before saving the follow-up because the latest consultation revision is uncertain.");
      return null;
    }
    return {
      patientId: selected.patient,
      encounterId: encounter.id,
      queueEntryId: selected.id,
      session: draftSessionRef.current,
      etag: encounterEtagRef.current,
    };
  }

  function isCurrentFollowUpMutation(variables: Pick<FollowUpContext, "session" | "patientId" | "encounterId" | "queueEntryId">) {
    return (
      variables.session === draftSessionRef.current &&
      variables.patientId === activePatientIdRef.current &&
      variables.encounterId === activeEncounterIdRef.current &&
      variables.queueEntryId === selectedQueueEntryIdRef.current
    );
  }
  function currentAllergyContext(): AllergyContext | null {
    if (!encounter?.id || !selected?.patient || !encounter.allergy_state_etag) {
      setAllergyMutationError("The current allergy state is unavailable. Reload the consultation before trying again.");
      return null;
    }
    return {
      patientId: selected.patient,
      encounterId: encounter.id,
      queueEntryId: selected.id,
      session: draftSessionRef.current,
      etag: encounter.allergy_state_etag,
    };
  }

  function isCurrentAllergyMutation(variables: Pick<AllergyContext, "session" | "patientId" | "encounterId" | "queueEntryId">) {
    return (
      variables.session === draftSessionRef.current &&
      variables.patientId === activePatientIdRef.current &&
      variables.encounterId === activeEncounterIdRef.current &&
      variables.queueEntryId === selectedQueueEntryIdRef.current
    );
  }
  function closeReviewedNormalAction() {
    setReviewedNormalActionOpen(false);
    setReviewedNormalSelection([]);
  }

  function cancelAutosaveTimer() {
    if (autosaveTimerRef.current !== null) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
  }

  function cancelRetryTimer() {
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  }

  function resetRetryState() {
    cancelRetryTimer();
    retryActiveRef.current = false;
    retryAttemptRef.current = 0;
  }

  function markRetrying() {
    retryActiveRef.current = true;
    setDraftSaveState("retrying");
    setNotice("");
    setError("");
  }

  function scheduleAutosave() {
    if (retryActiveRef.current) return;
    cancelAutosaveTimer();
    if (
      !encounter?.id ||
      !hasDirtyDraft() ||
      autosaveBlockedRef.current ||
      diagnosisMutationInFlightRef.current ||
      diagnosisReconciliationInFlightRef.current ||
      dispositionMutationInFlightRef.current ||
      dispositionReconciliationInFlightRef.current ||
      followUpMutationInFlightRef.current ||
      followUpReconciliationInFlightRef.current ||
      consultationRevisionUncertain ||
      isTerminalEncounterStatus(encounter.status)
    ) {
      return;
    }
    if (offlineRef.current) {
      retryActiveRef.current = true;
      retryAttemptRef.current = 0;
      markRetrying();
      return;
    }
    const session = draftSessionRef.current;
    const encounterId = encounter.id;
    autosaveTimerRef.current = setTimeout(() => {
      autosaveTimerRef.current = null;
      if (
        session !== draftSessionRef.current ||
        encounter?.id !== encounterId ||
        !hasDirtyDraft() ||
        autosaveBlockedRef.current ||
        dispositionMutationInFlightRef.current ||
        dispositionReconciliationInFlightRef.current ||
        followUpMutationInFlightRef.current ||
        followUpReconciliationInFlightRef.current ||
        consultationRevisionUncertain ||
        isTerminalEncounterStatus(encounter.status)
      ) {
        return;
      }
      if (offlineRef.current) {
        retryActiveRef.current = true;
        markRetrying();
        return;
      }
      if (clinicalMutationInFlightRef.current || diagnosisMutationInFlightRef.current || diagnosisReconciliationInFlightRef.current || dispositionMutationInFlightRef.current || dispositionReconciliationInFlightRef.current || followUpMutationInFlightRef.current || followUpReconciliationInFlightRef.current) {
        autosaveDeferredRef.current = true;
        return;
      }
      autosaveDeferredRef.current = false;
      const mutation = currentDraftMutation(0, "autosave");
      if (mutation) saveDraft.mutate(mutation);
    }, AUTOSAVE_DELAY_MS);
  }
  function hydrateNote(created: Encounter) {
    cancelAutosaveTimer();
    resetRetryState();
    autosaveBlockedRef.current = false;
    autosaveDeferredRef.current = false;
    clinicalMutationInFlightRef.current = false;
    setSavedAt(null);
    closeReviewedNormalAction();
    setDiagnosisFormState(emptyDiagnosisFormState());
    setDiagnosisMutationError("");
    setDiagnosisMutationBusy(false);
    diagnosisFormDirtyRef.current = false;
    diagnosisMutationInFlightRef.current = false;
    diagnosisReconciliationInFlightRef.current = false;
    const draft = consultationDraftFromEncounter(created);
    const hydratedDisposition = created.disposition ?? null;
    const hydratedDispositionNote = created.disposition_note ?? "";
    const hydratedFollowUp = followUpDraftValues(created.follow_up);
    const values = editableDraftValuesFromContent(draft.content);
    encounterEtagRef.current = created.consultation_etag ?? null;
    activePatientIdRef.current = created.patient;
    activeEncounterIdRef.current = created.id;
    signGuardErrorRef.current = null;
    setConsultationRevisionUncertain(false);
    dispositionDraftRef.current = hydratedDisposition;
    dispositionNoteDraftRef.current = hydratedDispositionNote;
    authoritativeDispositionRef.current = hydratedDisposition;
    authoritativeDispositionNoteRef.current = hydratedDispositionNote;
    dispositionFormDirtyRef.current = false;
    dispositionMutationInFlightRef.current = false;
    dispositionReconciliationInFlightRef.current = false;
    setDisposition(hydratedDisposition);
    setDispositionNote(hydratedDispositionNote);
    setDispositionSaveState(hydratedDisposition ? "saved" : "idle");
    setDispositionError("");
    setDispositionConflict(null);
    setDispositionFormDirty(false);
    followUpDraftRef.current = hydratedFollowUp;
    authoritativeFollowUpRef.current = hydratedFollowUp;
    followUpFormDirtyRef.current = false;
    followUpMutationInFlightRef.current = false;
    followUpReconciliationInFlightRef.current = false;
    setFollowUpRecommendedDate(hydratedFollowUp.recommendedDate);
    setFollowUpInstructions(hydratedFollowUp.instructions);
    setFollowUpSaveState(created.follow_up ? "saved" : "idle");
    setFollowUpError("");
    setFollowUpConflict(null);
    setFollowUpFormDirty(false);
    setAllergyMutationError("");
    noteContentRef.current = draft.content;
    draftValuesRef.current = values;
    dirtyFieldsRef.current = new Set();
    const hydratedComplaints = cloneComplaints(draft.complaints);
    complaintsDraftRef.current = hydratedComplaints;
    authoritativeComplaintsRef.current = cloneComplaints(hydratedComplaints);
    complaintsDirtyRef.current = false;
    draftSessionRef.current += 1;
    setComplaints(cloneComplaints(draft.complaints));
    setTriageComplaint(draft.triageComplaint);
    setHpi(values.hpi);
    setPastMedicalHistory(values.pastMedicalHistory);
    setPastSurgicalHistory(values.pastSurgicalHistory);
    setFamilyHistory(values.familyHistory);
    setSocialHistory(values.socialHistory);
    setGeneralExamination(values.generalExamination);
    setCardiovascularExamination(values.cardiovascularExamination);
    setRespiratoryExamination(values.respiratoryExamination);
    setAbdominalExamination(values.abdominalExamination);
    setNeurologicalExamination(values.neurologicalExamination);
    setGenitourinaryExamination(values.genitourinaryExamination);
    setMusculoskeletalExamination(values.musculoskeletalExamination);
    setTreatmentPlan(values.treatmentPlan);
    setNote(values.consultation);
    setDraftSaveState(Object.keys(draft.content).length > 0 || draft.complaints.length > 0 ? "saved" : "idle");
    setConflictComparison({});
    setComplaintConflict(null);
  }

  function setVisibleDraftValue(field: ClinicalNoteField, value: string) {
    if (field === "hpi") setHpi(value);
    if (field === "past_medical_history") setPastMedicalHistory(value);
    if (field === "past_surgical_history") setPastSurgicalHistory(value);
    if (field === "family_history") setFamilyHistory(value);
    if (field === "social_history") setSocialHistory(value);
    if (field === "general_examination") setGeneralExamination(value);
    if (field === "cardiovascular_examination") setCardiovascularExamination(value);
    if (field === "respiratory_examination") setRespiratoryExamination(value);
    if (field === "abdominal_examination") setAbdominalExamination(value);
    if (field === "neurological_examination") setNeurologicalExamination(value);
    if (field === "genitourinary_examination") setGenitourinaryExamination(value);
    if (field === "musculoskeletal_examination") setMusculoskeletalExamination(value);
    if (field === "treatment_plan") setTreatmentPlan(value);
    if (field === "consultation") setNote(value);
  }

  function rebaseVisibleDraft(content: ClinicalNoteContent, remoteFields: ClinicalNoteField[]) {
    const remoteValues = editableDraftValuesFromContent(content);
    const nextDraftValues = { ...draftValuesRef.current };
    const comparison: ConflictComparisonValues = {};

    for (const field of remoteFields) {
      const draftKey = FIELD_TO_DRAFT_VALUE[field];
      const serverValue = remoteValues[draftKey];
      const localDirty = dirtyFieldsRef.current.has(field);
      comparison[field] = { serverValue, localDirty };
      if (!localDirty) {
        nextDraftValues[draftKey] = serverValue;
        setVisibleDraftValue(field, serverValue);
      }
    }

    draftValuesRef.current = nextDraftValues;
    setConflictComparison(comparison);
  }

  function applyRemoteDispositionState(remote: Encounter) {
    const remoteDisposition = remote.disposition ?? null;
    const remoteDispositionNote = typeof remote.disposition_note === "string" ? remote.disposition_note : "";
    const changedRemotely =
      remoteDisposition !== authoritativeDispositionRef.current ||
      remoteDispositionNote !== authoritativeDispositionNoteRef.current;
    const localMatchesRemote =
      dispositionDraftRef.current === remoteDisposition &&
      dispositionNoteDraftRef.current === remoteDispositionNote;
    const alreadyApplied = dispositionFormDirtyRef.current && changedRemotely && localMatchesRemote;
    const trueConflict = dispositionFormDirtyRef.current && changedRemotely && !localMatchesRemote;

    authoritativeDispositionRef.current = remoteDisposition;
    authoritativeDispositionNoteRef.current = remoteDispositionNote;

    if (isTerminalEncounterStatus(remote.status) || !dispositionFormDirtyRef.current || alreadyApplied) {
      dispositionDraftRef.current = remoteDisposition;
      dispositionNoteDraftRef.current = remoteDispositionNote;
      dispositionFormDirtyRef.current = false;
      setDispositionFormDirty(false);
      setDisposition(remoteDisposition);
      setDispositionNote(remoteDispositionNote);
      setDispositionSaveState(remoteDisposition ? "saved" : "idle");
      setDispositionConflict(null);
    } else if (trueConflict) {
      setDispositionConflict({
        disposition: remoteDisposition,
        disposition_note: remoteDispositionNote,
      });
      setDispositionSaveState("unsaved");
    }

    return { changedRemotely, alreadyApplied, trueConflict };
  }
  function applyRemoteFollowUpState(remote: Pick<Encounter, "follow_up" | "status">) {
    const remoteValues = followUpDraftValues(remote.follow_up);
    const changedRemotely = !followUpDraftsEqual(remoteValues, authoritativeFollowUpRef.current);
    const localMatchesRemote = followUpDraftsEqual(followUpDraftRef.current, remoteValues);
    const alreadyApplied = followUpFormDirtyRef.current && changedRemotely && localMatchesRemote;
    const trueConflict = followUpFormDirtyRef.current && changedRemotely && !localMatchesRemote;

    authoritativeFollowUpRef.current = remoteValues;
    setEncounter((current) => {
      if (!current || current.id !== activeEncounterIdRef.current) return current;
      return {
        ...current,
        follow_up: remote.follow_up,
        status: remote.status,
      };
    });

    if (isTerminalEncounterStatus(remote.status) || !followUpFormDirtyRef.current || alreadyApplied) {
      followUpDraftRef.current = remoteValues;
      followUpFormDirtyRef.current = false;
      setFollowUpFormDirty(false);
      setFollowUpRecommendedDate(remoteValues.recommendedDate);
      setFollowUpInstructions(remoteValues.instructions);
      setFollowUpConflict(null);
      setFollowUpSaveState(remote.follow_up ? "saved" : "idle");
    } else if (trueConflict) {
      setFollowUpConflict(remoteValues);
      setFollowUpSaveState("unsaved");
    }

    return { changedRemotely, alreadyApplied, trueConflict };
  }
  function currentDraftMutation(
    rebaseAttempt = 0,
    origin: "manual" | "autosave" = "manual",
  ): DraftMutationVariables | null {
    const etag = encounterEtagRef.current;
    if (!encounter?.id || !etag) {
      setError("The current consultation revision is unavailable. Reload before saving.");
      return null;
    }
    if (dispositionMutationInFlightRef.current || dispositionReconciliationInFlightRef.current || followUpMutationInFlightRef.current || followUpReconciliationInFlightRef.current || diagnosisMutationInFlightRef.current || diagnosisReconciliationInFlightRef.current) {
      autosaveDeferredRef.current = true;
      return null;
    }
    if (consultationRevisionUncertain) {
      setDraftSaveState(hasDirtyDraft() ? "unsaved" : "idle");
      setError("The latest consultation state is uncertain. Reload before saving the clinical draft.");
      return null;
    }
    const values = { ...draftValuesRef.current };
    const fields = Array.from(dirtyFieldsRef.current);
    const complaintSnapshot = complaintsDirtyRef.current ? cloneComplaints(complaintsDraftRef.current) : undefined;
    if (complaintSnapshot !== undefined) {
      const complaintError = complaintsValidationMessage(complaintSnapshot);
      if (complaintError) {
        setDraftSaveState("unsaved");
        setError("Fix the presenting complaint before saving: " + complaintError);
        return null;
      }
    }
    if (fields.length === 0 && complaintSnapshot === undefined && origin === "autosave") return null;
    return {
      content: noteContentForFields(values, fields),
      fields,
      values,
      complaintSnapshot,
      encounterId: encounter.id,
      session: draftSessionRef.current,
      etag,
      rebaseAttempt,
      origin,
    };
  }

  function updateComplaints(next: PresentingComplaint[]) {
    signGuardErrorRef.current = null;
    const snapshot = cloneComplaints(next);
    complaintsDraftRef.current = snapshot;
    setComplaints(snapshot);
    complaintsDirtyRef.current = true;
    setDraftSaveState(retryActiveRef.current ? "retrying" : "unsaved");
    setNotice("");
    setError("");
    if (complaintsValidationMessage(snapshot)) return;
    if (retryActiveRef.current) {
      scheduleRetry();
    } else {
      scheduleAutosave();
    }
  }

  function copyTriageComplaint() {
    if (!triageComplaint || triageComplaint.trim().length === 0) return;
    updateComplaints([...complaintsDraftRef.current, {
      text: triageComplaint,
      duration_value: null,
      duration_unit: null,
    }]);
  }

  function selectEntry(entry: QueueEntry) {
    if (
      entry.id !== selectedId &&
      hasUnsavedContent() &&
      encounter &&
      !isTerminalEncounterStatus(encounter.status) &&
      !window.confirm("This consultation has unsaved changes. Leave and discard them?")
    ) {
      return;
    }
    cancelAutosaveTimer();
    resetRetryState();
    autosaveBlockedRef.current = false;
    autosaveDeferredRef.current = false;
    clinicalMutationInFlightRef.current = false;
    setSavedAt(null);
    closeReviewedNormalAction();
    setDiagnosisFormState(emptyDiagnosisFormState());
    setDiagnosisMutationError("");
    setDiagnosisMutationBusy(false);
    diagnosisFormDirtyRef.current = false;
    diagnosisMutationInFlightRef.current = false;
    diagnosisReconciliationInFlightRef.current = false;
    draftSessionRef.current += 1;
    noteContentRef.current = {};
    encounterEtagRef.current = null;
    setConflictComparison({});
    setComplaintConflict(null);
    draftValuesRef.current = emptyDraftValues();
    dirtyFieldsRef.current = new Set();
    complaintsDraftRef.current = [];
    authoritativeComplaintsRef.current = [];
    complaintsDirtyRef.current = false;
    selectedQueueEntryIdRef.current = entry.id;
    activePatientIdRef.current = entry.patient;
    activeEncounterIdRef.current = null;
    signGuardErrorRef.current = null;
    allergyFormDirtyRef.current = false;
    allergyMutationInFlightRef.current = false;
    setAllergyMutationError("");
    setSelectedId(entry.id);
    setEncounter(null);
    setNote(DEFAULT_CONSULTATION_NOTE);
    setTriageComplaint(null);
    setComplaints([]);
    setHpi("");
    setPastMedicalHistory("");
    setPastSurgicalHistory("");
    setFamilyHistory("");
    setSocialHistory("");
    setGeneralExamination("");
    setCardiovascularExamination("");
    setRespiratoryExamination("");
    setAbdominalExamination("");
    setNeurologicalExamination("");
    setGenitourinaryExamination("");
    setMusculoskeletalExamination("");
    setTreatmentPlan("");
    dispositionDraftRef.current = null;
    dispositionNoteDraftRef.current = "";
    authoritativeDispositionRef.current = null;
    authoritativeDispositionNoteRef.current = "";
    dispositionFormDirtyRef.current = false;
    dispositionMutationInFlightRef.current = false;
    dispositionReconciliationInFlightRef.current = false;
    setDisposition(null);
    setDispositionNote("");
    setDispositionSaveState("idle");
    setDispositionError("");
    setDispositionConflict(null);
    setDispositionFormDirty(false);
    followUpDraftRef.current = emptyFollowUpDraft();
    authoritativeFollowUpRef.current = emptyFollowUpDraft();
    followUpFormDirtyRef.current = false;
    followUpMutationInFlightRef.current = false;
    followUpReconciliationInFlightRef.current = false;
    setFollowUpRecommendedDate("");
    setFollowUpInstructions("");
    setFollowUpSaveState("idle");
    setFollowUpError("");
    setFollowUpConflict(null);
    setFollowUpFormDirty(false);
    setConsultationRevisionUncertain(false);
    setDraftSaveState("idle");
    setActiveSection("summary");
    setConfirmingSign(false);
    setNotice("");
    setError("");
  }

  const startEncounter = useMutation<Encounter, unknown, StartEncounterVariables>({
    mutationFn: ({ queueEntryId }) =>
      apiRequest<Encounter>("/api/v1/clinic/encounters/", {
        method: "POST",
        body: JSON.stringify({ queue_entry_id: queueEntryId }),
      }),
    onSuccess: (created, variables) => {
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      if (
        variables.session !== draftSessionRef.current ||
        selectedQueueEntryIdRef.current !== variables.queueEntryId
      ) {
        return;
      }
      setEncounter(created);
      hydrateNote(created);
      setActiveSection("notes");
      setError("");
    },
    onError: (reason, variables) => {
      if (
        variables.session !== draftSessionRef.current ||
        selectedQueueEntryIdRef.current !== variables.queueEntryId
      ) {
        return;
      }
      setError(errorMessage(reason));
    },
  });

  function startCurrentEncounter() {
    const queueEntryId = selected?.id;
    if (!queueEntryId) return;
    startEncounter.mutate({ queueEntryId, session: draftSessionRef.current });
  }

  const allergyStatusMutation = useMutation<AllergyStateResponse, unknown, AllergyStatusMutationVariables>({
    mutationFn: ({ patientId, status, etag }) =>
      apiRequest<AllergyStateResponse>("/api/v1/clinic/patients/" + patientId + "/allergy-status/", {
        method: "POST",
        headers: { "If-Match": etag },
        body: JSON.stringify({ status }),
      }),
    onMutate: (variables) => {
      if (isCurrentAllergyMutation(variables)) {
        allergyMutationInFlightRef.current = true;
        setAllergyMutationError("");
        setNotice("");
      }
    },
    onSuccess: (snapshot, variables) => {
      if (!isCurrentAllergyMutation(variables)) return;
      allergyMutationInFlightRef.current = false;
      applyAllergySnapshot(snapshot);
      setAllergyMutationError("");
      setNotice("Allergy information updated. Review the current status before signing.");
    },
    onError: (reason, variables) => {
      if (!isCurrentAllergyMutation(variables)) return;
      allergyMutationInFlightRef.current = false;
      const conflict = allergyStateConflict(reason);
      if (conflict) applyAllergySnapshot(conflict);
      setAllergyMutationError(allergyMutationErrorMessage(reason));
    },
  });

  const addAllergyMutation = useMutation<AllergyStateResponse, unknown, AllergyAddMutationVariables>({
    mutationFn: ({ patientId, values }) =>
      apiRequest<AllergyStateResponse>("/api/v1/clinic/patients/" + patientId + "/allergies/", {
        method: "POST",
        body: JSON.stringify({
          substance: values.substance,
          reaction: values.reaction,
          severity: values.severity,
        }),
      }),
    onMutate: (variables) => {
      if (isCurrentAllergyMutation(variables)) {
        allergyMutationInFlightRef.current = true;
        setAllergyMutationError("");
        setNotice("");
      }
    },
    onSuccess: (snapshot, variables) => {
      if (!isCurrentAllergyMutation(variables)) return;
      allergyMutationInFlightRef.current = false;
      applyAllergySnapshot(snapshot);
      setAllergyMutationError("");
      setNotice("Allergy recorded. Review the current status before signing.");
    },
    onError: (reason, variables) => {
      if (!isCurrentAllergyMutation(variables)) return;
      allergyMutationInFlightRef.current = false;
      const conflict = allergyStateConflict(reason);
      if (conflict) applyAllergySnapshot(conflict);
      setAllergyMutationError(allergyMutationErrorMessage(reason));
    },
  });

  const enterAllergyInErrorMutation = useMutation<AllergyStateResponse, unknown, AllergyEnteredInErrorMutationVariables>({
    mutationFn: ({ patientId, allergyId, reason, etag }) =>
      apiRequest<AllergyStateResponse>("/api/v1/clinic/patients/" + patientId + "/allergies/" + allergyId + "/entered-in-error/", {
        method: "POST",
        headers: { "If-Match": etag },
        body: JSON.stringify({ reason }),
      }),
    onMutate: (variables) => {
      if (isCurrentAllergyMutation(variables)) {
        allergyMutationInFlightRef.current = true;
        setAllergyMutationError("");
        setNotice("");
      }
    },
    onSuccess: (snapshot, variables) => {
      if (!isCurrentAllergyMutation(variables)) return;
      allergyMutationInFlightRef.current = false;
      applyAllergySnapshot(snapshot);
      setAllergyMutationError("");
      setNotice("Allergy record updated. Review the current status before signing.");
    },
    onError: (reason, variables) => {
      if (!isCurrentAllergyMutation(variables)) return;
      allergyMutationInFlightRef.current = false;
      const conflict = allergyStateConflict(reason);
      if (conflict) applyAllergySnapshot(conflict);
      setAllergyMutationError(allergyMutationErrorMessage(reason));
    },
  });

  const reviewAllergiesMutation = useMutation<AllergyStateResponse, unknown, AllergyReviewMutationVariables>({
    mutationFn: ({ encounterId, etag }) =>
      apiRequest<AllergyStateResponse>("/api/v1/clinic/encounters/" + encounterId + "/allergies/review/", {
        method: "POST",
        headers: { "If-Match": etag },
        body: JSON.stringify({}),
      }),
    onMutate: (variables) => {
      if (isCurrentAllergyMutation(variables)) {
        allergyMutationInFlightRef.current = true;
        setAllergyMutationError("");
        setNotice("");
      }
    },
    onSuccess: (snapshot, variables) => {
      if (!isCurrentAllergyMutation(variables)) return;
      allergyMutationInFlightRef.current = false;
      applyAllergySnapshot(snapshot);
      setAllergyMutationError("");
      setNotice("Allergy status reviewed for this encounter.");
    },
    onError: (reason, variables) => {
      if (!isCurrentAllergyMutation(variables)) return;
      allergyMutationInFlightRef.current = false;
      const conflict = allergyStateConflict(reason);
      if (conflict) applyAllergySnapshot(conflict);
      setAllergyMutationError(allergyMutationErrorMessage(reason));
    },
  });

  async function setAllergyStatus(status: Extract<AllergyStatus, "NKA" | "UNKNOWN">) {
    const context = currentAllergyContext();
    if (!context) return;
    await allergyStatusMutation.mutateAsync({ ...context, status });
  }

  async function addAllergy(values: AllergyFormValues) {
    const context = currentAllergyContext();
    if (!context) throw new Error("The current allergy state is unavailable.");
    const { etag: _etag, ...addContext } = context;
    await addAllergyMutation.mutateAsync({ ...addContext, values });
  }

  async function enterAllergyInError(allergyId: string, reason: string) {
    const context = currentAllergyContext();
    if (!context) throw new Error("The current allergy state is unavailable.");
    await enterAllergyInErrorMutation.mutateAsync({ ...context, allergyId, reason });
  }

  async function reviewAllergies() {
    const context = currentAllergyContext();
    if (!context) return;
    await reviewAllergiesMutation.mutateAsync(context);
  }

  const allergyMutationPending =
    allergyMutationInFlightRef.current ||
    allergyStatusMutation.isPending ||
    addAllergyMutation.isPending ||
    enterAllergyInErrorMutation.isPending ||
    reviewAllergiesMutation.isPending;
  const followUpMutation = useMutation<FollowUpSaveResponse, unknown, FollowUpMutationVariables>({
    mutationFn: ({ encounterId, etag, values }) =>
      apiRequest<FollowUpSaveResponse>("/api/v1/clinic/encounters/" + encounterId + "/follow-up/", {
        method: "PATCH",
        headers: { "If-Match": etag },
        body: JSON.stringify({
          recommended_date: values.recommendedDate || null,
          instructions: values.instructions,
        }),
      }),
    onMutate: (variables) => {
      if (!isCurrentFollowUpMutation(variables)) return;
      followUpMutationInFlightRef.current = true;
      followUpReconciliationInFlightRef.current = false;
      setFollowUpError("");
      setFollowUpConflict(null);
      setNotice("");
      setError("");
      cancelAutosaveTimer();
      cancelRetryTimer();
      autosaveDeferredRef.current = true;
    },
    onSuccess: (saved, variables) => {
      if (!isCurrentFollowUpMutation(variables)) return;
      followUpMutationInFlightRef.current = false;
      followUpReconciliationInFlightRef.current = false;
      setConsultationRevisionUncertain(false);
      const savedValues = followUpDraftValues(saved.follow_up);
      authoritativeFollowUpRef.current = savedValues;
      encounterEtagRef.current = saved.consultation_etag;
      setEncounter((current) => {
        if (!current || current.id !== activeEncounterIdRef.current) return current;
        return {
          ...current,
          follow_up: saved.follow_up,
          consultation_etag: saved.consultation_etag,
          status: saved.encounter_status || current.status,
        };
      });
      const localStillMatchesSubmitted = followUpDraftsEqual(followUpDraftRef.current, variables.values);
      if (localStillMatchesSubmitted) {
        followUpDraftRef.current = savedValues;
        followUpFormDirtyRef.current = false;
        setFollowUpFormDirty(false);
        setFollowUpRecommendedDate(savedValues.recommendedDate);
        setFollowUpInstructions(savedValues.instructions);
        setFollowUpSaveState("saved");
      } else {
        followUpFormDirtyRef.current = true;
        setFollowUpFormDirty(true);
        setFollowUpSaveState("unsaved");
      }
      setFollowUpConflict(null);
      setFollowUpError("");
      setNotice("Follow-up saved.");
      setError("");
      autosaveDeferredRef.current = false;
      if (hasDirtyDraft()) {
        if (retryActiveRef.current) scheduleRetry();
        else scheduleAutosave();
      }
    },
    onError: (reason, variables) => {
      if (!variables || !isCurrentFollowUpMutation(variables)) return;
      followUpMutationInFlightRef.current = false;
      if (reason instanceof ApiRequestError && reason.status === 412) {
        followUpReconciliationInFlightRef.current = true;
        autosaveDeferredRef.current = true;
        cancelAutosaveTimer();
        cancelRetryTimer();
        setFollowUpError("This consultation changed elsewhere. Loading the latest record before retrying.");
        setError("");
        void reconcileFollowUpConflict(variables);
        return;
      }
      followUpReconciliationInFlightRef.current = false;
      autosaveDeferredRef.current = false;
      setFollowUpSaveState(followUpFormDirtyRef.current ? "unsaved" : "idle");
      setFollowUpError(errorMessage(reason));
      setNotice("");
      if (hasDirtyDraft()) {
        if (retryActiveRef.current) scheduleRetry();
        else scheduleAutosave();
      }
    },
  });

  const followUpMutationPending =
    followUpMutation.isPending ||
    followUpMutationInFlightRef.current ||
    followUpReconciliationInFlightRef.current;

  async function reconcileFollowUpConflict(variables: FollowUpMutationVariables) {
    if (!isCurrentFollowUpMutation(variables)) return;
    let resumeNoteAutosave = false;
    let reconciliationFailed = false;
    try {
      const remote = await apiRequest<Encounter>("/api/v1/clinic/encounters/" + variables.encounterId + "/");
      if (
        !isCurrentFollowUpMutation(variables) ||
        remote.id !== variables.encounterId ||
        remote.patient !== variables.patientId ||
        remote.queue_entry !== variables.queueEntryId
      ) {
        return;
      }
      const remoteContent = consultationContent(remote);
      const remoteValues = editableDraftValuesFromContent(remoteContent);
      const remoteFields = changedClinicalFields(noteContentRef.current, remoteContent);
      const overlappingFields = remoteFields.filter((field) => dirtyFieldsRef.current.has(field));
      const alreadyAppliedFields = overlappingFields.filter((field) => {
        const draftKey = FIELD_TO_DRAFT_VALUE[field];
        return draftValuesRef.current[draftKey] === remoteValues[draftKey];
      });
      const trueOverlappingFields = overlappingFields.filter((field) => !alreadyAppliedFields.includes(field));
      const serverComplaints = cloneComplaints(remote.complaints ?? []);
      const complaintsChangedRemotely = !complaintsEqual(serverComplaints, authoritativeComplaintsRef.current);
      const complaintWasAlreadyApplied = complaintsDirtyRef.current &&
        complaintsChangedRemotely &&
        complaintsEqual(serverComplaints, complaintsDraftRef.current);
      const trueComplaintConflict = complaintsDirtyRef.current &&
        complaintsChangedRemotely &&
        !complaintsEqual(serverComplaints, complaintsDraftRef.current);
      const latestEtag = remote.consultation_etag;
      if (typeof latestEtag !== "string" || !Array.isArray(remote.diagnoses)) {
        throw new Error("Authoritative consultation revision is unavailable.");
      }

      noteContentRef.current = remoteContent;
      encounterEtagRef.current = latestEtag;
      authoritativeComplaintsRef.current = cloneComplaints(serverComplaints);
      setEncounter((current) => {
        if (!current || current.id !== activeEncounterIdRef.current) return current;
        return {
          ...current,
          ...remote,
          complaints: serverComplaints,
          diagnoses: remote.diagnoses,
          consultation_etag: latestEtag,
          status: remote.status,
        };
      });
      const dispositionState = applyRemoteDispositionState(remote);
      const followUpState = applyRemoteFollowUpState(remote);
      if (!complaintsDirtyRef.current || complaintWasAlreadyApplied) {
        complaintsDraftRef.current = cloneComplaints(serverComplaints);
        setComplaints(cloneComplaints(serverComplaints));
        complaintsDirtyRef.current = false;
        setComplaintConflict(null);
      } else if (trueComplaintConflict) {
        setComplaintConflict(cloneComplaints(serverComplaints));
      }
      for (const field of alreadyAppliedFields) {
        const draftKey = FIELD_TO_DRAFT_VALUE[field];
        if (draftValuesRef.current[draftKey] === remoteValues[draftKey]) dirtyFieldsRef.current.delete(field);
      }
      rebaseVisibleDraft(remoteContent, remoteFields.filter((field) => !alreadyAppliedFields.includes(field)));

      if (isTerminalEncounterStatus(remote.status)) {
        cancelAutosaveTimer();
        resetRetryState();
        autosaveDeferredRef.current = false;
      }
      if (trueOverlappingFields.length > 0 || trueComplaintConflict || followUpState.trueConflict) {
        autosaveBlockedRef.current = true;
        cancelAutosaveTimer();
        resetRetryState();
        autosaveDeferredRef.current = false;
      } else {
        autosaveBlockedRef.current = false;
        resumeNoteAutosave = !isTerminalEncounterStatus(remote.status) && hasDirtyDraft();
      }

      if (dispositionState.trueConflict) {
        setDispositionError("The saved disposition differs from your unsaved selection. Review it before saving again.");
      } else if (dispositionFormDirtyRef.current) {
        setDispositionError("The disposition change was not replayed. Review the latest record and save deliberately.");
      } else {
        setDispositionError("");
      }
      if (followUpState.trueConflict) {
        setFollowUpError("The saved follow-up differs from your unsaved draft. Review it before saving again.");
      } else if (followUpFormDirtyRef.current) {
        setFollowUpError("The follow-up change was not replayed. Review the latest record and save deliberately.");
      } else {
        setFollowUpError("");
      }

      if (!hasDirtyDraft()) {
        setDraftSaveState("saved");
      } else {
        setDraftSaveState("unsaved");
      }
      setConsultationRevisionUncertain(false);
      setNotice(followUpState.alreadyApplied && !followUpFormDirtyRef.current
        ? "Latest consultation state loaded. The follow-up change was already present."
        : "Latest consultation state loaded. The follow-up change was not replayed.");
      if (trueOverlappingFields.length > 0 || trueComplaintConflict) {
        const complaintMessage = trueComplaintConflict
          ? " Presenting complaints changed elsewhere; your unsaved complaint list has been preserved."
          : "";
        setError(conflictMessage(remoteFields, trueOverlappingFields, "save") + complaintMessage);
      } else {
        setError("");
      }
    } catch {
      reconciliationFailed = true;
      if (isCurrentFollowUpMutation(variables)) {
        setConsultationRevisionUncertain(true);
        autosaveBlockedRef.current = true;
        cancelAutosaveTimer();
        resetRetryState();
        autosaveDeferredRef.current = false;
        setFollowUpSaveState(followUpFormDirtyRef.current ? "unsaved" : "idle");
        setFollowUpError("The latest consultation could not be loaded. Reload before trying the follow-up again.");
        setError("The latest consultation could not be loaded. Reload before trying the follow-up again.");
      }
    } finally {
      if (isCurrentFollowUpMutation(variables)) {
        followUpReconciliationInFlightRef.current = false;
        followUpMutationInFlightRef.current = false;
        if (!reconciliationFailed && resumeNoteAutosave && hasDirtyDraft()) {
          if (retryActiveRef.current) scheduleRetry();
          else scheduleAutosave();
        }
      }
    }
  }
  const dispositionMutation = useMutation<DispositionSaveResponse, unknown, DispositionMutationVariables>({
    mutationFn: ({ encounterId, etag, disposition, disposition_note }) =>
      apiRequest<DispositionSaveResponse>("/api/v1/clinic/encounters/" + encounterId + "/disposition/", {
        method: "PATCH",
        headers: { "If-Match": etag },
        body: JSON.stringify({ disposition, disposition_note }),
      }),
    onMutate: (variables) => {
      if (!isCurrentDispositionMutation(variables)) return;
      dispositionMutationInFlightRef.current = true;
      dispositionReconciliationInFlightRef.current = false;
      setDispositionError("");
      setNotice("");
      setError("");
      cancelAutosaveTimer();
      cancelRetryTimer();
      autosaveDeferredRef.current = true;
    },
    onSuccess: (saved, variables) => {
      if (!isCurrentDispositionMutation(variables)) return;
      dispositionMutationInFlightRef.current = false;
      dispositionReconciliationInFlightRef.current = false;
      setConsultationRevisionUncertain(false);
      encounterEtagRef.current = saved.consultation_etag;
      authoritativeDispositionRef.current = saved.disposition ?? null;
      authoritativeDispositionNoteRef.current = saved.disposition_note ?? "";
      setEncounter((current) => {
        if (!current || current.id !== activeEncounterIdRef.current) return current;
        return {
          ...current,
          disposition: saved.disposition ?? null,
          disposition_note: saved.disposition_note ?? "",
          consultation_etag: saved.consultation_etag,
          status: saved.encounter_status || current.status,
        };
      });
      const localStillMatchesSubmitted =
        dispositionDraftRef.current === variables.disposition &&
        dispositionNoteDraftRef.current === variables.disposition_note;
      if (localStillMatchesSubmitted) {
        dispositionDraftRef.current = saved.disposition ?? null;
        dispositionNoteDraftRef.current = saved.disposition_note ?? "";
        dispositionFormDirtyRef.current = false;
        setDispositionFormDirty(false);
        setDisposition(saved.disposition ?? null);
        setDispositionNote(saved.disposition_note ?? "");
        setDispositionSaveState(saved.disposition ? "saved" : "idle");
      } else {
        dispositionFormDirtyRef.current = true;
        setDispositionFormDirty(true);
        setDispositionSaveState("unsaved");
      }
      setDispositionConflict(null);
      setDispositionError("");
      setNotice("Disposition saved.");
      setError("");
      autosaveDeferredRef.current = false;
      if (hasDirtyDraft()) {
        if (retryActiveRef.current) scheduleRetry();
        else scheduleAutosave();
      }
    },
    onError: (reason, variables) => {
      if (!variables || !isCurrentDispositionMutation(variables)) return;
      dispositionMutationInFlightRef.current = false;
      if (reason instanceof ApiRequestError && reason.status === 412) {
        dispositionReconciliationInFlightRef.current = true;
        autosaveDeferredRef.current = true;
        cancelAutosaveTimer();
        cancelRetryTimer();
        setDispositionError("This consultation changed elsewhere. Loading the latest record before retrying.");
        setError("");
        void reconcileDispositionConflict(variables);
        return;
      }
      dispositionReconciliationInFlightRef.current = false;
      autosaveDeferredRef.current = false;
      setDispositionSaveState(dispositionFormDirtyRef.current ? "unsaved" : "idle");
      setDispositionError(errorMessage(reason));
      setNotice("");
    },
  });

  const dispositionMutationPending =
    dispositionMutation.isPending ||
    dispositionMutationInFlightRef.current ||
    dispositionReconciliationInFlightRef.current;

  async function reconcileDispositionConflict(variables: DispositionMutationVariables) {
    if (!isCurrentDispositionMutation(variables)) return;
    let resumeNoteAutosave = false;
    let reconciliationFailed = false;
    try {
      const remote = await apiRequest<Encounter>("/api/v1/clinic/encounters/" + variables.encounterId + "/");
      if (
        !isCurrentDispositionMutation(variables) ||
        remote.id !== variables.encounterId ||
        remote.patient !== variables.patientId ||
        remote.queue_entry !== variables.queueEntryId
      ) {
        return;
      }
      const remoteContent = consultationContent(remote);
      const remoteValues = editableDraftValuesFromContent(remoteContent);
      const remoteFields = changedClinicalFields(noteContentRef.current, remoteContent);
      const overlappingFields = remoteFields.filter((field) => dirtyFieldsRef.current.has(field));
      const alreadyAppliedFields = overlappingFields.filter((field) => {
        const draftKey = FIELD_TO_DRAFT_VALUE[field];
        return draftValuesRef.current[draftKey] === remoteValues[draftKey];
      });
      const trueOverlappingFields = overlappingFields.filter((field) => !alreadyAppliedFields.includes(field));
      const serverComplaints = cloneComplaints(remote.complaints ?? []);
      const complaintsChangedRemotely = !complaintsEqual(serverComplaints, authoritativeComplaintsRef.current);
      const complaintWasAlreadyApplied = complaintsDirtyRef.current &&
        complaintsChangedRemotely &&
        complaintsEqual(serverComplaints, complaintsDraftRef.current);
      const trueComplaintConflict = complaintsDirtyRef.current &&
        complaintsChangedRemotely &&
        !complaintsEqual(serverComplaints, complaintsDraftRef.current);
      const latestEtag = remote.consultation_etag;
      if (typeof latestEtag !== "string" || !Array.isArray(remote.diagnoses)) {
        throw new Error("Authoritative consultation revision is unavailable.");
      }

      noteContentRef.current = remoteContent;
      encounterEtagRef.current = latestEtag;
      authoritativeComplaintsRef.current = cloneComplaints(serverComplaints);
      setEncounter((current) => {
        if (!current || current.id !== activeEncounterIdRef.current) return current;
        return {
          ...current,
          ...remote,
          complaints: serverComplaints,
          diagnoses: remote.diagnoses,
          consultation_etag: latestEtag,
          status: remote.status,
        };
      });
      const dispositionState = applyRemoteDispositionState(remote);
      applyRemoteFollowUpState(remote);
      if (!complaintsDirtyRef.current || complaintWasAlreadyApplied) {
        complaintsDraftRef.current = cloneComplaints(serverComplaints);
        setComplaints(cloneComplaints(serverComplaints));
        complaintsDirtyRef.current = false;
        setComplaintConflict(null);
      } else if (trueComplaintConflict) {
        setComplaintConflict(cloneComplaints(serverComplaints));
      }
      for (const field of alreadyAppliedFields) {
        const draftKey = FIELD_TO_DRAFT_VALUE[field];
        if (draftValuesRef.current[draftKey] === remoteValues[draftKey]) dirtyFieldsRef.current.delete(field);
      }
      rebaseVisibleDraft(remoteContent, remoteFields.filter((field) => !alreadyAppliedFields.includes(field)));

      if (isTerminalEncounterStatus(remote.status)) {
        cancelAutosaveTimer();
        resetRetryState();
        autosaveDeferredRef.current = false;
      }
      if (trueOverlappingFields.length > 0 || trueComplaintConflict) {
        autosaveBlockedRef.current = true;
        cancelAutosaveTimer();
        resetRetryState();
        autosaveDeferredRef.current = false;
      } else {
        autosaveBlockedRef.current = false;
        resumeNoteAutosave = !isTerminalEncounterStatus(remote.status) && hasDirtyDraft();
      }

      if (dispositionState.trueConflict) {
        setDispositionError("The saved disposition differs from your unsaved selection. Review it before saving again.");
      } else if (dispositionFormDirtyRef.current) {
        setDispositionError("The disposition change was not replayed. Review the latest record and save deliberately.");
      } else {
        setDispositionError("");
      }

      if (!hasDirtyDraft()) {
        setDraftSaveState("saved");
      } else {
        setDraftSaveState("unsaved");
      }
      setConsultationRevisionUncertain(false);
      setNotice("Latest consultation state loaded. The disposition change was not replayed.");
      if (trueOverlappingFields.length > 0 || trueComplaintConflict) {
        const complaintMessage = trueComplaintConflict
          ? " Presenting complaints changed elsewhere; your unsaved complaint list has been preserved."
          : "";
        setError(conflictMessage(remoteFields, trueOverlappingFields, "save") + complaintMessage);
      } else {
        setError("");
      }
    } catch {
      reconciliationFailed = true;
      if (isCurrentDispositionMutation(variables)) {
        setConsultationRevisionUncertain(true);
        autosaveBlockedRef.current = true;
        cancelAutosaveTimer();
        resetRetryState();
        autosaveDeferredRef.current = false;
        setDispositionSaveState(dispositionFormDirtyRef.current ? "unsaved" : "idle");
        setDispositionError("The latest consultation could not be loaded. Reload before trying the disposition again.");
        setError("The latest consultation could not be loaded. Reload before trying the disposition again.");
      }
    } finally {
      if (isCurrentDispositionMutation(variables)) {
        dispositionReconciliationInFlightRef.current = false;
        dispositionMutationInFlightRef.current = false;
        if (!reconciliationFailed && resumeNoteAutosave && hasDirtyDraft()) {
          if (retryActiveRef.current) scheduleRetry();
          else scheduleAutosave();
        }
      }
    }
  }
  async function reconcileDiagnosisConflict(variables: DiagnosisMutationVariables, _conflict: DiagnosisConflictData) {
    if (!isCurrentDiagnosisMutation(variables)) return;
    try {
      const remote = await apiRequest<Encounter>("/api/v1/clinic/encounters/" + variables.encounterId + "/");
      if (
        !isCurrentDiagnosisMutation(variables) ||
        remote.id !== variables.encounterId ||
        remote.patient !== variables.patientId ||
        remote.queue_entry !== variables.queueEntryId
      ) {
        return;
      }
      const remoteContent = consultationContent(remote);
      const remoteValues = editableDraftValuesFromContent(remoteContent);
      const remoteFields = changedClinicalFields(noteContentRef.current, remoteContent);
      const overlappingFields = remoteFields.filter((field) => dirtyFieldsRef.current.has(field));
      const alreadyAppliedFields = overlappingFields.filter((field) => {
        const draftKey = FIELD_TO_DRAFT_VALUE[field];
        return draftValuesRef.current[draftKey] === remoteValues[draftKey];
      });
      const trueOverlappingFields = overlappingFields.filter((field) => !alreadyAppliedFields.includes(field));
      const serverComplaints = cloneComplaints(remote.complaints ?? []);
      const complaintsChangedRemotely = !complaintsEqual(serverComplaints, authoritativeComplaintsRef.current);
      const complaintWasAlreadyApplied = complaintsDirtyRef.current && complaintsChangedRemotely && complaintsEqual(serverComplaints, complaintsDraftRef.current);
      const trueComplaintConflict = complaintsDirtyRef.current && complaintsChangedRemotely && !complaintsEqual(serverComplaints, complaintsDraftRef.current);
      const latestEtag = remote.consultation_etag;
      if (!latestEtag || !Array.isArray(remote.diagnoses)) {
        throw new Error("Authoritative consultation revision is unavailable.");
      }

      noteContentRef.current = remoteContent;
      encounterEtagRef.current = latestEtag;
      authoritativeComplaintsRef.current = cloneComplaints(serverComplaints);
      setEncounter((current) => {
        if (!current || current.id !== activeEncounterIdRef.current) return current;
        return {
          ...current,
          ...remote,
          complaints: serverComplaints,
          diagnoses: remote.diagnoses,
          consultation_etag: latestEtag,
          status: remote.status,
        };
      });
      applyRemoteDispositionState(remote);
      applyRemoteFollowUpState(remote);
      if (!complaintsDirtyRef.current || complaintWasAlreadyApplied) {
        complaintsDraftRef.current = cloneComplaints(serverComplaints);
        setComplaints(cloneComplaints(serverComplaints));
        complaintsDirtyRef.current = false;
        setComplaintConflict(null);
      } else if (trueComplaintConflict) {
        setComplaintConflict(cloneComplaints(serverComplaints));
      }
      for (const field of alreadyAppliedFields) {
        const draftKey = FIELD_TO_DRAFT_VALUE[field];
        if (draftValuesRef.current[draftKey] === remoteValues[draftKey]) dirtyFieldsRef.current.delete(field);
      }
      rebaseVisibleDraft(remoteContent, remoteFields.filter((field) => !alreadyAppliedFields.includes(field)));
      const draftStillDirty = hasDirtyDraft();
      if (!draftStillDirty) setConflictComparison({});

      if (isTerminalEncounterStatus(remote.status)) {
        cancelAutosaveTimer();
        resetRetryState();
        autosaveDeferredRef.current = false;
      }
      if (trueOverlappingFields.length > 0 || trueComplaintConflict) {
        autosaveBlockedRef.current = true;
        cancelAutosaveTimer();
        resetRetryState();
        autosaveDeferredRef.current = false;
        setDraftSaveState("unsaved");
        const complaintMessage = trueComplaintConflict
          ? " Presenting complaints changed elsewhere; your unsaved complaint list has been preserved."
          : "";
        setError(conflictMessage(remoteFields, trueOverlappingFields, "save") + complaintMessage);
      } else if (!draftStillDirty) {
        autosaveBlockedRef.current = false;
        resetRetryState();
        setDraftSaveState("saved");
        setNotice("Latest consultation state loaded. The diagnosis change was not replayed.");
        setError("");
      } else {
        autosaveBlockedRef.current = false;
        setDraftSaveState("unsaved");
        setNotice("Latest consultation state loaded. The diagnosis change was not replayed.");
        setError("");
        if (retryActiveRef.current) scheduleRetry();
        else scheduleAutosave();
      }
    } catch {
      if (isCurrentDiagnosisMutation(variables)) {
        autosaveBlockedRef.current = true;
        cancelAutosaveTimer();
        resetRetryState();
        setDiagnosisMutationError("The latest consultation could not be loaded. Reload before trying the diagnosis change again.");
      }
    } finally {
      if (isCurrentDiagnosisMutation(variables)) {
        diagnosisReconciliationInFlightRef.current = false;
        diagnosisMutationInFlightRef.current = false;
        setDiagnosisMutationBusy(false);
      }
    }
  }

  const diagnosisMutation = useMutation<DiagnosisStateResponse, unknown, DiagnosisMutationVariables>({
    mutationFn: ({ action, encounterId, diagnosisId, etag, payload }) => {
      const path = action === "create"
        ? "/api/v1/clinic/encounters/" + encounterId + "/diagnoses/"
        : action === "update"
          ? "/api/v1/clinic/encounters/" + encounterId + "/diagnoses/" + diagnosisId + "/"
          : "/api/v1/clinic/encounters/" + encounterId + "/diagnoses/" + diagnosisId + "/remove/";
      return apiRequest<DiagnosisStateResponse>(path, {
        method: action === "create" ? "POST" : action === "update" ? "PATCH" : "POST",
        headers: { "If-Match": etag },
        body: JSON.stringify(action === "remove" ? {} : payload ?? {}),
      });
    },
    onMutate: (variables) => {
      if (!isCurrentDiagnosisMutation(variables)) return;
      diagnosisMutationInFlightRef.current = true;
      diagnosisReconciliationInFlightRef.current = false;
      setDiagnosisMutationBusy(true);
      setDiagnosisMutationError("");
      setNotice("");
      cancelAutosaveTimer();
      cancelRetryTimer();
      autosaveDeferredRef.current = true;
    },
    onSuccess: (saved, variables) => {
      if (!isCurrentDiagnosisMutation(variables)) return;
      diagnosisMutationInFlightRef.current = false;
      diagnosisReconciliationInFlightRef.current = false;
      setDiagnosisMutationBusy(false);
      signGuardErrorRef.current = null;
      setError("");
      applyDiagnosisSnapshot(saved.diagnoses, saved.consultation_etag);
      setDiagnosisMutationError("");
      setNotice("Diagnosis record updated.");
      autosaveDeferredRef.current = false;
      if (hasDirtyDraft()) {
        if (retryActiveRef.current) scheduleRetry();
        else scheduleAutosave();
      }
    },
    onError: (reason, variables) => {
      if (!variables || !isCurrentDiagnosisMutation(variables)) return;
      diagnosisMutationInFlightRef.current = false;
      autosaveDeferredRef.current = false;
      const conflict = diagnosisStateConflict(reason);
      if (conflict) {
        setDiagnosisMutationError("This consultation changed elsewhere. Review the latest diagnoses before trying again.");
        diagnosisReconciliationInFlightRef.current = true;
        setDiagnosisMutationBusy(true);
        void reconcileDiagnosisConflict(variables, conflict);
        return;
      }
      diagnosisReconciliationInFlightRef.current = false;
      setDiagnosisMutationBusy(false);
      setDiagnosisMutationError(diagnosisMutationErrorMessage(reason));
      setNotice("");
      if (hasDirtyDraft()) {
        if (retryActiveRef.current) scheduleRetry();
        else scheduleAutosave();
      }
    },
  });
  async function runDiagnosisMutation(
    action: DiagnosisMutationVariables["action"],
    diagnosisId: string | undefined,
    payload?: DiagnosisWritePayload,
  ): Promise<DiagnosisStateResponse> {
    if (clinicalMutationInFlightRef.current || dispositionMutationInFlightRef.current || dispositionReconciliationInFlightRef.current || followUpMutationInFlightRef.current || followUpReconciliationInFlightRef.current) {
      setDiagnosisMutationError("Wait for the consultation save or sign request to finish before changing diagnoses.");
      throw new Error("A consultation mutation is already in flight.");
    }
    if (diagnosisMutationInFlightRef.current || diagnosisReconciliationInFlightRef.current) {
      setDiagnosisMutationError("Wait for the diagnosis update to finish before trying another diagnosis action.");
      throw new Error("A diagnosis mutation is already in flight.");
    }
    const context = currentDiagnosisContext();
    if (!context) throw new Error("The current consultation revision is unavailable.");
    return diagnosisMutation.mutateAsync({ ...context, action, diagnosisId, payload });
  }

  async function createDiagnosis(payload: DiagnosisWritePayload) {
    const currentPrimary = encounter?.diagnoses?.find(
      (diagnosis) => diagnosis.diagnosis_type === "FINAL" && diagnosis.is_primary,
    );
    if (payload.diagnosis_type === "FINAL" && payload.is_primary && currentPrimary) {
      const existingIds = new Set((encounter?.diagnoses ?? []).map((diagnosis) => diagnosis.id));
      const created = await runDiagnosisMutation("create", undefined, { ...payload, is_primary: false });
      const createdFinal = created.diagnoses.find(
        (diagnosis) => diagnosis.diagnosis_type === "FINAL" && !existingIds.has(diagnosis.id),
      );
      if (!createdFinal) {
        setDiagnosisMutationError("The new final diagnosis could not be identified. Review the diagnosis list before trying again.");
        throw new Error("Created final diagnosis was not present in the authoritative response.");
      }
      await runDiagnosisMutation("update", currentPrimary.id, { diagnosis_type: "FINAL", is_primary: false });
      await runDiagnosisMutation("update", createdFinal.id, { diagnosis_type: "FINAL", is_primary: true });
      return;
    }
    await runDiagnosisMutation("create", undefined, payload);
  }

  async function saveDiagnosisEdit(diagnosisId: string, payload: DiagnosisWritePayload) {
    const current = encounter?.diagnoses?.find((diagnosis) => diagnosis.id === diagnosisId);
    const primary = encounter?.diagnoses?.find((diagnosis) => diagnosis.diagnosis_type === "FINAL" && diagnosis.is_primary);
    const needsPrimarySwitch = payload.diagnosis_type === "FINAL" &&
      payload.is_primary === true &&
      !current?.is_primary &&
      Boolean(primary && primary.id !== diagnosisId);
    if (needsPrimarySwitch && primary) {
      await runDiagnosisMutation("update", primary.id, { diagnosis_type: "FINAL", is_primary: false });
      await runDiagnosisMutation("update", diagnosisId, { ...payload, diagnosis_type: "FINAL", is_primary: true });
      return;
    }
    await runDiagnosisMutation("update", diagnosisId, payload);
  }

  async function setPrimaryDiagnosis(diagnosisId: string) {
    const target = encounter?.diagnoses?.find((diagnosis) => diagnosis.id === diagnosisId && diagnosis.diagnosis_type === "FINAL");
    if (!target || target.is_primary) return;
    const currentPrimary = encounter?.diagnoses?.find((diagnosis) => diagnosis.diagnosis_type === "FINAL" && diagnosis.is_primary);
    if (currentPrimary) {
      await runDiagnosisMutation("update", currentPrimary.id, { diagnosis_type: "FINAL", is_primary: false });
    }
    await runDiagnosisMutation("update", target.id, { diagnosis_type: "FINAL", is_primary: true });
  }

  async function removeDiagnosis(diagnosisId: string) {
    await runDiagnosisMutation("remove", diagnosisId);
  }

  const diagnosisMutationPending = diagnosisMutationBusy || diagnosisReconciliationInFlightRef.current;
  const saveDraft = useMutation<NoteSaveResponse, unknown, DraftMutationVariables>({
    mutationFn: ({ content, complaintSnapshot, encounterId, etag, origin }) =>
      apiRequest<NoteSaveResponse>(
        "/api/v1/clinic/encounters/" + encounterId + "/notes/",
        {
          method: "PATCH",
          headers: {
            "If-Match": etag,
            ...(origin === "autosave" ? { "X-KlinKlik-Autosave": "1" } : {}),
          },
          body: JSON.stringify({
            content,
            ...(complaintSnapshot !== undefined ? { complaints: complaintSnapshot } : {}),
          }),
        },
      ),
    onMutate: (variables) => {
      if (variables.session === draftSessionRef.current) {
        clinicalMutationInFlightRef.current = true;
      }
    },
    onSuccess: (saved, variables) => {
      if (variables.session !== draftSessionRef.current) return;
      clinicalMutationInFlightRef.current = false;
      autosaveDeferredRef.current = false;
      resetRetryState();
      if (variables.origin === "manual") autosaveBlockedRef.current = false;
      noteContentRef.current = saved.content;
      encounterEtagRef.current = saved.etag;
      const serverComplaints = cloneComplaints(saved.complaints ?? []);
      authoritativeComplaintsRef.current = cloneComplaints(serverComplaints);
      if (!complaintsDirtyRef.current || (variables.complaintSnapshot !== undefined && complaintsEqual(complaintsDraftRef.current, variables.complaintSnapshot))) {
        complaintsDraftRef.current = cloneComplaints(serverComplaints);
        setComplaints(cloneComplaints(serverComplaints));
        complaintsDirtyRef.current = false;
        setComplaintConflict(null);
      }
      setSavedAt(saved.saved_at);
      setConflictComparison({});
      for (const field of variables.fields) {
        const draftKey = FIELD_TO_DRAFT_VALUE[field];
        if (draftValuesRef.current[draftKey] === variables.values[draftKey]) {
          dirtyFieldsRef.current.delete(field);
        }
      }
      const stillDirty = hasDirtyDraft();
      setDraftSaveState(stillDirty ? "unsaved" : "saved");
      setNotice(stillDirty
        ? "Consultation draft saved; newer edits remain unsaved."
        : (variables.origin === "autosave" ? "Consultation draft autosaved." : "Consultation draft saved."));
      setError(signGuardErrorRef.current ?? "");
      if (stillDirty) scheduleAutosave();
    },
    onError: (reason, variables) => {
      if (!variables || variables.session !== draftSessionRef.current) return;
      clinicalMutationInFlightRef.current = false;
      signGuardErrorRef.current = null;
      const conflict = clinicalNoteConflict(reason);
      if (!conflict) {
        autosaveDeferredRef.current = false;
        if (isRetryableDraftFailure(reason) && hasDirtyDraft()) {
          continueRetryAfterFailure();
          return;
        }
        resetRetryState();
        setDraftSaveState(hasDirtyDraft() ? "unsaved" : "idle");
        setError(errorMessage(reason));
        return;
      }

      applyDiagnosisSnapshot(conflict.diagnoses, conflict.etag, conflict.encounter_status);
      if (conflict.follow_up !== undefined) {
        applyRemoteFollowUpState({ follow_up: conflict.follow_up, status: conflict.encounter_status });
      }
      const remoteValues = editableDraftValuesFromContent(conflict.content);
      const remoteFields = changedClinicalFields(noteContentRef.current, conflict.content);
      const overlappingFields = remoteFields.filter((field) => dirtyFieldsRef.current.has(field));
      const alreadyAppliedFields = overlappingFields.filter((field) => {
        const draftKey = FIELD_TO_DRAFT_VALUE[field];
        return draftValuesRef.current[draftKey] === remoteValues[draftKey];
      });
      const trueOverlappingFields = overlappingFields.filter((field) => !alreadyAppliedFields.includes(field));
      const serverComplaints = cloneComplaints(conflict.complaints);
      const complaintsChangedRemotely = !complaintsEqual(serverComplaints, authoritativeComplaintsRef.current);
      const complaintWasAlreadyApplied = complaintsDirtyRef.current && complaintsChangedRemotely && complaintsEqual(serverComplaints, complaintsDraftRef.current);
      const trueComplaintConflict = complaintsDirtyRef.current && complaintsChangedRemotely && !complaintsEqual(serverComplaints, complaintsDraftRef.current);

      noteContentRef.current = conflict.content;
      encounterEtagRef.current = conflict.etag;
      authoritativeComplaintsRef.current = cloneComplaints(serverComplaints);
      if (!complaintsDirtyRef.current || complaintWasAlreadyApplied) {
        complaintsDraftRef.current = cloneComplaints(serverComplaints);
        setComplaints(cloneComplaints(serverComplaints));
        complaintsDirtyRef.current = false;
        setComplaintConflict(null);
      } else if (trueComplaintConflict) {
        setComplaintConflict(cloneComplaints(serverComplaints));
      }
      for (const field of alreadyAppliedFields) {
        const draftKey = FIELD_TO_DRAFT_VALUE[field];
        if (draftValuesRef.current[draftKey] === remoteValues[draftKey]) {
          dirtyFieldsRef.current.delete(field);
        }
      }

      if (isTerminalEncounterStatus(conflict.encounter_status)) {
        setEncounter((current) => (current ? { ...current, status: conflict.encounter_status } : current));
        resetRetryState();
        cancelAutosaveTimer();
        autosaveDeferredRef.current = false;
      }
      rebaseVisibleDraft(conflict.content, remoteFields.filter((field) => !alreadyAppliedFields.includes(field)));

      if (trueOverlappingFields.length > 0 || trueComplaintConflict) {
        resetRetryState();
        autosaveBlockedRef.current = true;
        cancelAutosaveTimer();
        autosaveDeferredRef.current = false;
      }

      if (!hasDirtyDraft()) {
        resetRetryState();
        setSavedAt(conflict.saved_at);
        setDraftSaveState("saved");
        setNotice("Consultation draft reconciled with the latest saved record.");
        setError("");
        return;
      }

      if (
        trueOverlappingFields.length === 0 &&
        !trueComplaintConflict &&
        variables.rebaseAttempt < 1 &&
        conflict.status === "DRAFT" &&
        conflict.encounter_status === "OPEN"
      ) {
        const rebasedMutation = currentDraftMutation(variables.rebaseAttempt + 1, variables.origin);
        if (rebasedMutation) {
          setError("");
          saveDraft.mutate(rebasedMutation);
          return;
        }
      }

      if (trueOverlappingFields.length === 0 && !trueComplaintConflict) resetRetryState();
      setDraftSaveState("unsaved");
      setNotice("");
      if (trueComplaintConflict) {
        const complaintMessage = "Presenting complaints changed elsewhere. Your unsaved complaint list has been preserved. Review the latest record before saving again.";
        setError(trueOverlappingFields.length > 0 ? conflictMessage(remoteFields, trueOverlappingFields, "save") + " " + complaintMessage : complaintMessage);
      } else {
        setError(conflictMessage(remoteFields, trueOverlappingFields, "save"));
      }
    },
  });
  function attemptRetryNow() {
    if (
      !retryActiveRef.current ||
      offlineRef.current ||
      clinicalMutationInFlightRef.current ||
      diagnosisMutationInFlightRef.current ||
      diagnosisReconciliationInFlightRef.current ||
      dispositionMutationInFlightRef.current ||
      dispositionReconciliationInFlightRef.current ||
      followUpMutationInFlightRef.current ||
      followUpReconciliationInFlightRef.current ||
      consultationRevisionUncertain ||
      !encounter?.id ||
      !hasDirtyDraft() ||
      autosaveBlockedRef.current ||
      isTerminalEncounterStatus(encounter.status)
    ) {
      if (retryActiveRef.current && !hasDirtyDraft()) {
        resetRetryState();
        setDraftSaveState("saved");
      }
      return;
    }
    autosaveDeferredRef.current = false;
    const mutation = currentDraftMutation(0, "autosave");
    if (mutation) saveDraft.mutate(mutation);
  }

  retryAttemptRunnerRef.current = attemptRetryNow;

  function scheduleRetry() {
    if (
      !retryActiveRef.current ||
      offlineRef.current ||
      !encounter?.id ||
      !hasDirtyDraft() ||
      autosaveBlockedRef.current ||
      dispositionMutationInFlightRef.current ||
      dispositionReconciliationInFlightRef.current ||
      followUpMutationInFlightRef.current ||
      followUpReconciliationInFlightRef.current ||
      consultationRevisionUncertain ||
      isTerminalEncounterStatus(encounter.status)
    ) {
      return;
    }
    if (retryTimerRef.current !== null) return;
    const session = draftSessionRef.current;
    const encounterId = encounter.id;
    const delay = RETRY_BACKOFF_MS[Math.min(retryAttemptRef.current, RETRY_BACKOFF_MS.length - 1)];
    retryTimerRef.current = setTimeout(() => {
      retryTimerRef.current = null;
      if (
        session !== draftSessionRef.current ||
        encounter?.id !== encounterId ||
        !hasDirtyDraft() ||
        autosaveBlockedRef.current ||
        dispositionMutationInFlightRef.current ||
        dispositionReconciliationInFlightRef.current ||
        followUpMutationInFlightRef.current ||
        followUpReconciliationInFlightRef.current ||
        consultationRevisionUncertain ||
        isTerminalEncounterStatus(encounter.status)
      ) {
        return;
      }
      if (offlineRef.current || clinicalMutationInFlightRef.current || diagnosisMutationInFlightRef.current || diagnosisReconciliationInFlightRef.current || dispositionMutationInFlightRef.current || dispositionReconciliationInFlightRef.current || followUpMutationInFlightRef.current || followUpReconciliationInFlightRef.current) return;
      attemptRetryNow();
    }, delay);
  }

  function continueRetryAfterFailure() {
    const wasRetrying = retryActiveRef.current;
    retryActiveRef.current = true;
    if (wasRetrying) {
      retryAttemptRef.current = Math.min(retryAttemptRef.current + 1, RETRY_BACKOFF_MS.length - 1);
    } else {
      retryAttemptRef.current = 0;
    }
    markRetrying();
    scheduleRetry();
  }

  useEffect(() => {
    offlineRef.current = typeof navigator !== "undefined" && !navigator.onLine;
    function handleOffline() {
      offlineRef.current = true;
      if (
        hasDirtyDraft() &&
        encounter?.id &&
        !autosaveBlockedRef.current &&
        !isTerminalEncounterStatus(encounter.status)
      ) {
        cancelAutosaveTimer();
        cancelRetryTimer();
        if (!retryActiveRef.current) retryAttemptRef.current = 0;
        markRetrying();
      }
    }
    function handleOnline() {
      offlineRef.current = false;
      if (
        retryActiveRef.current &&
        hasDirtyDraft() &&
        !autosaveBlockedRef.current &&
        !clinicalMutationInFlightRef.current &&
        !diagnosisMutationInFlightRef.current &&
        !diagnosisReconciliationInFlightRef.current &&
        !dispositionMutationInFlightRef.current &&
        !dispositionReconciliationInFlightRef.current &&
        !followUpMutationInFlightRef.current &&
        !followUpReconciliationInFlightRef.current &&
        !consultationRevisionUncertain &&
        encounter?.id &&
        !isTerminalEncounterStatus(encounter.status)
      ) {
        cancelRetryTimer();
        retryAttemptRunnerRef.current();
      }
    }
    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);
    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, [encounter, consultationRevisionUncertain]);

  useEffect(() => {
    function handleBeforeUnload(event: BeforeUnloadEvent) {
      if (!hasUnsavedContent()) return;
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedContent]);
  const signNote = useMutation<NoteSignResponse, unknown, DraftMutationVariables>({
    mutationFn: ({ content, complaintSnapshot, encounterId, etag }) =>
      apiRequest<NoteSignResponse>("/api/v1/clinic/encounters/" + encounterId + "/sign/", {
        method: "POST",
        headers: { "If-Match": etag },
        body: JSON.stringify({
          content,
          ...(complaintSnapshot !== undefined ? { complaints: complaintSnapshot } : {}),
        }),
      }),
    onMutate: (variables) => {
      if (variables.session === draftSessionRef.current) {
        clinicalMutationInFlightRef.current = true;
      }
    },
    onSuccess: (signed, variables) => {
      if (variables.session !== draftSessionRef.current) return;
      clinicalMutationInFlightRef.current = false;
      signGuardErrorRef.current = null;
      resetRetryState();
      cancelAutosaveTimer();
      const signedDraft = editableDraftValuesFromContent(signed.content);
      const signedComplaints = cloneComplaints(signed.complaints ?? []);
      noteContentRef.current = signed.content;
      encounterEtagRef.current = signed.etag;
      authoritativeComplaintsRef.current = cloneComplaints(signedComplaints);
      complaintsDraftRef.current = cloneComplaints(signedComplaints);
      complaintsDirtyRef.current = false;
      setComplaints(cloneComplaints(signedComplaints));
      setComplaintConflict(null);
      setSavedAt(signed.saved_at);
      draftValuesRef.current = signedDraft;
      dirtyFieldsRef.current = new Set();
      setHpi(signedDraft.hpi);
      setPastMedicalHistory(signedDraft.pastMedicalHistory);
      setPastSurgicalHistory(signedDraft.pastSurgicalHistory);
      setFamilyHistory(signedDraft.familyHistory);
      setSocialHistory(signedDraft.socialHistory);
      setGeneralExamination(signedDraft.generalExamination);
      setCardiovascularExamination(signedDraft.cardiovascularExamination);
      setRespiratoryExamination(signedDraft.respiratoryExamination);
      setAbdominalExamination(signedDraft.abdominalExamination);
      setNeurologicalExamination(signedDraft.neurologicalExamination);
      setGenitourinaryExamination(signedDraft.genitourinaryExamination);
      setMusculoskeletalExamination(signedDraft.musculoskeletalExamination);
      setTreatmentPlan(signedDraft.treatmentPlan);
      setNote(signedDraft.consultation);
      setConflictComparison({});
      setEncounter((current) => (current ? { ...current, status: "SIGNED" } : current));
      setDraftSaveState("saved");
      closeReviewedNormalAction();
      setConfirmingSign(false);
      setNotice("Consultation signed for " + (selected?.patient_name ?? "the patient") + ".");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
    onError: (reason, variables) => {
      if (!variables || variables.session !== draftSessionRef.current) return;
      clinicalMutationInFlightRef.current = false;
      signGuardErrorRef.current = null;
      resetRetryState();
      const conflict = clinicalNoteConflict(reason);
      setConfirmingSign(false);
      if (!conflict) {
        const diagnosisMessage = diagnosisSignServerErrorMessage(reason);
        if (diagnosisMessage) {
          setActiveSection("diagnosis");
          setError(diagnosisMessage);
          return;
        }
        const dispositionMessage = dispositionServerErrorMessage(reason);
        if (dispositionMessage) {
          setActiveSection("treatment");
          setError(dispositionMessage);
          setDispositionError(dispositionMessage);
          return;
        }
        const allergyMessage = signAllergyServerErrorMessage(reason);
        if (allergyMessage) {
          setActiveSection("summary");
          setError(allergyMessage);
          return;
        }
        if (reason instanceof ApiRequestError && reason.status === 400 && typeof reason.data === "object" && reason.data !== null && (reason.data as Record<string, unknown>).code === "PRESENTING_COMPLAINT_REQUIRED") {
          setActiveSection("history");
          setError("Add at least one valid presenting complaint before signing this consultation.");
          return;
        }
        setError(errorMessage(reason));
        return;
      }
      applyDiagnosisSnapshot(conflict.diagnoses, conflict.etag, conflict.encounter_status);
      if (conflict.follow_up !== undefined) {
        applyRemoteFollowUpState({ follow_up: conflict.follow_up, status: conflict.encounter_status });
      }
      const remoteFields = changedClinicalFields(noteContentRef.current, conflict.content);
      const overlappingFields = remoteFields.filter((field) => dirtyFieldsRef.current.has(field));
      const alreadyAppliedFields = overlappingFields.filter((field) => {
        const remoteValues = editableDraftValuesFromContent(conflict.content);
        const draftKey = FIELD_TO_DRAFT_VALUE[field];
        return draftValuesRef.current[draftKey] === remoteValues[draftKey];
      });
      const trueOverlappingFields = overlappingFields.filter((field) => !alreadyAppliedFields.includes(field));
      const serverComplaints = cloneComplaints(conflict.complaints);
      const complaintsChangedRemotely = !complaintsEqual(serverComplaints, authoritativeComplaintsRef.current);
      const complaintWasAlreadyApplied = complaintsDirtyRef.current && complaintsChangedRemotely && complaintsEqual(serverComplaints, complaintsDraftRef.current);
      const trueComplaintConflict = complaintsDirtyRef.current && complaintsChangedRemotely && !complaintsEqual(serverComplaints, complaintsDraftRef.current);
      noteContentRef.current = conflict.content;
      encounterEtagRef.current = conflict.etag;
      authoritativeComplaintsRef.current = cloneComplaints(serverComplaints);
      if (!complaintsDirtyRef.current || complaintWasAlreadyApplied) {
        complaintsDraftRef.current = cloneComplaints(serverComplaints);
        setComplaints(cloneComplaints(serverComplaints));
        complaintsDirtyRef.current = false;
        setComplaintConflict(null);
      } else if (trueComplaintConflict) {
        setComplaintConflict(cloneComplaints(serverComplaints));
      }
      if (isTerminalEncounterStatus(conflict.encounter_status)) {
        setEncounter((current) => (current ? { ...current, status: conflict.encounter_status } : current));
        cancelAutosaveTimer();
        autosaveDeferredRef.current = false;
      }
      rebaseVisibleDraft(conflict.content, remoteFields.filter((field) => !alreadyAppliedFields.includes(field)));
      if (trueOverlappingFields.length > 0 || trueComplaintConflict) {
        autosaveBlockedRef.current = true;
        cancelAutosaveTimer();
        autosaveDeferredRef.current = false;
      }
      setDraftSaveState("unsaved");
      setNotice("");
      if (trueComplaintConflict) {
        const complaintMessage = "Presenting complaints changed elsewhere. Your unsaved complaint list has been preserved. Review the latest record before signing again.";
        setError(trueOverlappingFields.length > 0 ? conflictMessage(remoteFields, trueOverlappingFields, "sign") + " " + complaintMessage : complaintMessage);
      } else {
        setError(conflictMessage(remoteFields, trueOverlappingFields, "sign"));
      }
    },
  });
  function updateClinicalField(field: ClinicalNoteField, value: string, setValue: (value: string) => void) {
    signGuardErrorRef.current = null;
    setValue(value);
    draftValuesRef.current = {
      ...draftValuesRef.current,
      [FIELD_TO_DRAFT_VALUE[field]]: value,
    };
    setConflictComparison((current) => {
      const comparison = current[field];
      return comparison && !comparison.localDirty
        ? { ...current, [field]: { ...comparison, localDirty: true } }
        : current;
    });
    dirtyFieldsRef.current.add(field);
    setDraftSaveState(retryActiveRef.current ? "retrying" : "unsaved");
    setNotice("");
    if (!retryActiveRef.current) scheduleAutosave();
  }

  function setDispositionDraftValue(value: EncounterDisposition | null) {
    signGuardErrorRef.current = null;
    dispositionDraftRef.current = value;
    setDisposition(value);
    const dirty =
      value !== authoritativeDispositionRef.current ||
      dispositionNoteDraftRef.current !== authoritativeDispositionNoteRef.current;
    dispositionFormDirtyRef.current = dirty;
    setDispositionFormDirty(dirty);
    setDispositionSaveState(dirty ? "unsaved" : (authoritativeDispositionRef.current ? "saved" : "idle"));
    setDispositionConflict(null);
    setDispositionError("");
    setNotice("");
    setError("");
  }

  function setDispositionDraftNote(value: string) {
    signGuardErrorRef.current = null;
    dispositionNoteDraftRef.current = value;
    setDispositionNote(value);
    const dirty =
      dispositionDraftRef.current !== authoritativeDispositionRef.current ||
      value !== authoritativeDispositionNoteRef.current;
    dispositionFormDirtyRef.current = dirty;
    setDispositionFormDirty(dirty);
    setDispositionSaveState(dirty ? "unsaved" : (authoritativeDispositionRef.current ? "saved" : "idle"));
    setDispositionConflict(null);
    setDispositionError("");
    setNotice("");
    setError("");
  }

  function discardDispositionChanges() {
    dispositionDraftRef.current = authoritativeDispositionRef.current;
    dispositionNoteDraftRef.current = authoritativeDispositionNoteRef.current;
    dispositionFormDirtyRef.current = false;
    setDispositionFormDirty(false);
    setDisposition(authoritativeDispositionRef.current);
    setDispositionNote(authoritativeDispositionNoteRef.current);
    setDispositionSaveState(authoritativeDispositionRef.current ? "saved" : "idle");
    setDispositionConflict(null);
    setDispositionError("");
    signGuardErrorRef.current = null;
    setNotice("Disposition changes discarded.");
    setError("");
  }

  function saveCurrentDisposition() {
    if (!encounter?.id || isTerminalEncounterStatus(encounter.status)) return;
    if (clinicalMutationInFlightRef.current || diagnosisMutationInFlightRef.current || diagnosisReconciliationInFlightRef.current) {
      setDispositionError("Wait for the current consultation update to finish before saving the disposition.");
      return;
    }
    if (dispositionMutationInFlightRef.current || dispositionReconciliationInFlightRef.current || followUpMutationInFlightRef.current || followUpReconciliationInFlightRef.current) return;

    const draftDisposition = dispositionDraftRef.current;
    const draftNote = dispositionNoteDraftRef.current;
    const localError = dispositionFormValidationMessage(draftDisposition, draftNote);
    if (draftDisposition === "OTHER" && localError) {
      setDispositionSaveState("unsaved");
      setDispositionError("Enter a note for the Other disposition.");
      setNotice("");
      return;
    }

    const context = currentDispositionContext();
    if (!context) return;
    cancelAutosaveTimer();
    cancelRetryTimer();
    autosaveDeferredRef.current = true;
    setDispositionError("");
    setNotice("");
    setError("");
    dispositionMutation.mutate({
      ...context,
      disposition: draftDisposition,
      disposition_note: draftNote,
    });
  }
  function updateFollowUpDraft(values: Partial<FollowUpDraftValues>) {
    signGuardErrorRef.current = null;
    const next = { ...followUpDraftRef.current, ...values };
    followUpDraftRef.current = next;
    setFollowUpRecommendedDate(next.recommendedDate);
    setFollowUpInstructions(next.instructions);
    const dirty = !followUpDraftsEqual(next, authoritativeFollowUpRef.current);
    followUpFormDirtyRef.current = dirty;
    setFollowUpFormDirty(dirty);
    setFollowUpSaveState(dirty ? "unsaved" : (encounter?.follow_up ? "saved" : "idle"));
    setFollowUpConflict(null);
    setFollowUpError("");
    setNotice("");
    setError("");
  }

  function discardFollowUpChanges() {
    const authoritative = authoritativeFollowUpRef.current;
    followUpDraftRef.current = authoritative;
    followUpFormDirtyRef.current = false;
    setFollowUpFormDirty(false);
    setFollowUpRecommendedDate(authoritative.recommendedDate);
    setFollowUpInstructions(authoritative.instructions);
    setFollowUpSaveState(encounter?.follow_up ? "saved" : "idle");
    setFollowUpConflict(null);
    setFollowUpError("");
    signGuardErrorRef.current = null;
    setNotice("Follow-up changes discarded.");
    setError("");
  }

  function saveCurrentFollowUp() {
    if (!encounter?.id || isTerminalEncounterStatus(encounter.status)) return;
    if (
      clinicalMutationInFlightRef.current ||
      diagnosisMutationInFlightRef.current ||
      diagnosisReconciliationInFlightRef.current ||
      dispositionMutationInFlightRef.current ||
      dispositionReconciliationInFlightRef.current
    ) {
      setFollowUpError("Wait for the current consultation update to finish before saving the follow-up.");
      return;
    }
    if (followUpMutationInFlightRef.current || followUpReconciliationInFlightRef.current) return;

    const values = { ...followUpDraftRef.current };
    if (!values.recommendedDate) {
      setFollowUpSaveState("unsaved");
      setFollowUpError("Enter a follow-up date before saving.");
      setNotice("");
      return;
    }
    const context = currentFollowUpContext();
    if (!context) return;
    cancelAutosaveTimer();
    cancelRetryTimer();
    autosaveDeferredRef.current = true;
    setFollowUpError("");
    setNotice("");
    setError("");
    followUpMutation.mutate({ ...context, values });
  }
  function isExaminationFieldUnavailable(field: ExaminationField) {
    const draftValue = draftValuesRef.current[FIELD_TO_DRAFT_VALUE[field]];
    return draftValue.length > 0 || dirtyFieldsRef.current.has(field) || Boolean(conflictComparison[field]?.localDirty);
  }

  function hasExaminationFieldValue(field: ExaminationField) {
    return draftValuesRef.current[FIELD_TO_DRAFT_VALUE[field]].length > 0;
  }

  function openReviewedNormalAction() {
    setReviewedNormalSelection([]);
    setReviewedNormalActionOpen(true);
  }

  function toggleReviewedNormalField(field: ExaminationField) {
    if (isExaminationFieldUnavailable(field)) return;
    setReviewedNormalSelection((current) =>
      current.includes(field) ? current.filter((selectedField) => selectedField !== field) : [...current, field],
    );
  }

  function insertReviewedNormalFindings() {
    for (const field of reviewedNormalSelection) {
      if (isExaminationFieldUnavailable(field)) continue;
      const template = REVIEWED_NORMAL_TEMPLATES[field];
      if (field === "general_examination") updateClinicalField(field, template, setGeneralExamination);
      if (field === "cardiovascular_examination") updateClinicalField(field, template, setCardiovascularExamination);
      if (field === "respiratory_examination") updateClinicalField(field, template, setRespiratoryExamination);
      if (field === "abdominal_examination") updateClinicalField(field, template, setAbdominalExamination);
      if (field === "neurological_examination") updateClinicalField(field, template, setNeurologicalExamination);
      if (field === "genitourinary_examination") updateClinicalField(field, template, setGenitourinaryExamination);
      if (field === "musculoskeletal_examination") updateClinicalField(field, template, setMusculoskeletalExamination);
    }
    closeReviewedNormalAction();
  }

  function handleWorkspaceSectionChange(section: WorkspaceSectionId) {
    if (section !== "examination") closeReviewedNormalAction();
    setActiveSection(section);
  }

  function saveCurrentDraft() {
    if (clinicalMutationInFlightRef.current || diagnosisMutationInFlightRef.current || diagnosisReconciliationInFlightRef.current || dispositionMutationInFlightRef.current || dispositionReconciliationInFlightRef.current || followUpMutationInFlightRef.current || followUpReconciliationInFlightRef.current) return;
    cancelAutosaveTimer();
    resetRetryState();
    autosaveDeferredRef.current = false;
    autosaveBlockedRef.current = false;
    const mutation = currentDraftMutation(0, "manual");
    if (mutation) saveDraft.mutate(mutation);
  }

  function showSignGuard(message: string) {
    signGuardErrorRef.current = message;
    setError(message);
  }

  function signCurrentDraft() {
    if (diagnosisFormDirtyRef.current) {
      setActiveSection("diagnosis");
      setConfirmingSign(false);
      showSignGuard("Save or cancel the diagnosis changes before signing.");
      return;
    }
    if (diagnosisMutationInFlightRef.current || diagnosisReconciliationInFlightRef.current) {
      setActiveSection("diagnosis");
      setConfirmingSign(false);
      showSignGuard("Wait for the diagnosis update to finish before signing.");
      return;
    }
    if (dispositionMutationInFlightRef.current || dispositionReconciliationInFlightRef.current) {
      setActiveSection("treatment");
      setConfirmingSign(false);
      showSignGuard("Wait for the disposition update to finish before signing.");
      return;
    }
    if (followUpMutationInFlightRef.current || followUpReconciliationInFlightRef.current) {
      setActiveSection("treatment");
      setConfirmingSign(false);
      showSignGuard("Wait for the follow-up update to finish before signing.");
      return;
    }
    if (dispositionFormDirtyRef.current) {
      setActiveSection("treatment");
      setConfirmingSign(false);
      showSignGuard("Save or cancel the disposition changes before signing.");
      return;
    }
    if (followUpFormDirtyRef.current) {
      setActiveSection("treatment");
      setConfirmingSign(false);
      showSignGuard("Save or cancel the follow-up changes before signing.");
      return;
    }
    if (consultationRevisionUncertain) {
      setActiveSection("treatment");
      setConfirmingSign(false);
      showSignGuard("Reload before signing because the latest consultation revision is uncertain.");
      return;
    }
    const dispositionPrerequisite = dispositionSignPrerequisiteMessage(authoritativeDispositionRef.current, authoritativeDispositionNoteRef.current, authoritativeFollowUpRef.current.recommendedDate);
    if (dispositionPrerequisite) {
      setActiveSection("treatment");
      setConfirmingSign(false);
      showSignGuard(dispositionPrerequisite);
      return;
    }
    const diagnosisPrerequisite = diagnosisSignPrerequisiteMessage(encounter?.diagnoses ?? []);
    if (diagnosisPrerequisite) {
      setActiveSection("diagnosis");
      setConfirmingSign(false);
      showSignGuard(diagnosisPrerequisite);
      return;
    }
    const allergyPrerequisite = allergySignPrerequisiteMessage(encounter);
    const candidateComplaints = cloneComplaints(complaintsDraftRef.current);
    const complaintError = complaintsValidationMessage(candidateComplaints);
    if (allergyPrerequisite) {
      setActiveSection("summary");
      setConfirmingSign(false);
      showSignGuard(allergyPrerequisite);
      document.getElementById("allergy-banner")?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    if (allergyMutationInFlightRef.current) {
      setConfirmingSign(false);
      showSignGuard("Wait for the allergy update to finish before signing.");
      return;
    }
    if (candidateComplaints.length === 0 || complaintError) {
      setActiveSection("history");
      setConfirmingSign(false);
      showSignGuard(candidateComplaints.length === 0
        ? "Add at least one valid presenting complaint before signing this consultation."
        : "Fix the presenting complaint before signing: " + complaintError);
      return;
    }
    if (clinicalMutationInFlightRef.current || dispositionMutationInFlightRef.current || dispositionReconciliationInFlightRef.current || followUpMutationInFlightRef.current || followUpReconciliationInFlightRef.current) return;
    signGuardErrorRef.current = null;
    cancelAutosaveTimer();
    resetRetryState();
    autosaveDeferredRef.current = false;
    autosaveBlockedRef.current = false;
    const mutation = currentDraftMutation(0, "manual");
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
      {error ? <ErrorBanner message={error} onDismiss={() => { signGuardErrorRef.current = null; setError(""); }} /> : null}

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

              {encounter ? (
                <AllergyBanner
                encounter={encounter}
                canManage={can("allergy.manage")}
                canReview={can("clinical.note.sign")}
                mutationPending={allergyMutationPending}
                mutationError={allergyMutationError}
                onSetStatus={setAllergyStatus}
                onAddAllergy={addAllergy}
                onEnterInError={enterAllergyInError}
                onReview={reviewAllergies}
                onFormDirtyChange={(dirty) => {
                  allergyFormDirtyRef.current = dirty;
                }}
                />
              ) : null}
              <WorkspaceSectionTabs activeSection={activeSection} onChange={handleWorkspaceSectionChange} />

              <ConflictComparisonPanel values={conflictComparison} />

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
                      <Button disabled={startEncounter.isPending} onClick={startCurrentEncounter}>
                        {startEncounter.isPending ? "Starting…" : "Start encounter"}
                      </Button>
                    </div>
                  ) : (
                    <HistorySection
                      status={encounter.status}
                      complaints={complaints}
                      triageComplaint={triageComplaint}
                      complaintConflict={complaintConflict}
                      hpi={hpi}
                      pastMedicalHistory={pastMedicalHistory}
                      pastSurgicalHistory={pastSurgicalHistory}
                      familyHistory={familyHistory}
                      socialHistory={socialHistory}
                      onComplaintsChange={updateComplaints}
                      onCopyTriage={copyTriageComplaint}
                      onHpiChange={(value) => updateClinicalField("hpi", value, setHpi)}
                      onPastMedicalHistoryChange={(value) => updateClinicalField("past_medical_history", value, setPastMedicalHistory)}
                      onPastSurgicalHistoryChange={(value) => updateClinicalField("past_surgical_history", value, setPastSurgicalHistory)}
                      onFamilyHistoryChange={(value) => updateClinicalField("family_history", value, setFamilyHistory)}
                      onSocialHistoryChange={(value) => updateClinicalField("social_history", value, setSocialHistory)}
                      onSave={saveCurrentDraft}
                      savePending={saveDraft.isPending || signNote.isPending || dispositionMutationPending || followUpMutationPending}
                      saveState={draftSaveState}
                      savedAt={savedAt}
                    />
                  )
                ) : activeSection === "examination" ? (
                  !encounter ? (
                    <div className="space-y-3">
                      <p className="text-[12.5px] font-medium text-secondary">
                        Not recorded yet. Start the encounter to capture the general examination.
                      </p>
                      <Button disabled={startEncounter.isPending} onClick={startCurrentEncounter}>
                        {startEncounter.isPending ? "Starting..." : "Start encounter"}
                      </Button>
                    </div>
                  ) : (
                    <ExaminationSection
                      status={encounter.status}
                      generalExamination={generalExamination}
                      cardiovascularExamination={cardiovascularExamination}
                      respiratoryExamination={respiratoryExamination}
                      abdominalExamination={abdominalExamination}
                      neurologicalExamination={neurologicalExamination}
                      genitourinaryExamination={genitourinaryExamination}
                      musculoskeletalExamination={musculoskeletalExamination}
                      onGeneralExaminationChange={(value) => updateClinicalField("general_examination", value, setGeneralExamination)}
                      onCardiovascularExaminationChange={(value) => updateClinicalField("cardiovascular_examination", value, setCardiovascularExamination)}
                      onRespiratoryExaminationChange={(value) => updateClinicalField("respiratory_examination", value, setRespiratoryExamination)}
                      onAbdominalExaminationChange={(value) => updateClinicalField("abdominal_examination", value, setAbdominalExamination)}
                      onNeurologicalExaminationChange={(value) => updateClinicalField("neurological_examination", value, setNeurologicalExamination)}
                      onGenitourinaryExaminationChange={(value) => updateClinicalField("genitourinary_examination", value, setGenitourinaryExamination)}
                      onMusculoskeletalExaminationChange={(value) => updateClinicalField("musculoskeletal_examination", value, setMusculoskeletalExamination)}
                      onSave={saveCurrentDraft}
                      savePending={saveDraft.isPending || signNote.isPending || dispositionMutationPending || followUpMutationPending}
                      saveState={draftSaveState}
                      savedAt={savedAt}
                      reviewedNormalActionOpen={reviewedNormalActionOpen}
                      reviewedNormalSelection={reviewedNormalSelection}
                      isExaminationFieldUnavailable={isExaminationFieldUnavailable}
                      hasExaminationFieldValue={hasExaminationFieldValue}
                      onOpenReviewedNormalAction={openReviewedNormalAction}
                      onToggleReviewedNormalField={toggleReviewedNormalField}
                      onCancelReviewedNormalAction={closeReviewedNormalAction}
                      onInsertReviewedNormalFindings={insertReviewedNormalFindings}
                    />
                  )
                ) : activeSection === "treatment" ? (
                  !encounter ? (
                    <div className="space-y-3">
                      <p className="text-[12.5px] font-medium text-secondary">
                        Not recorded yet. Start the encounter to capture the treatment plan.
                      </p>
                      <Button disabled={startEncounter.isPending} onClick={startCurrentEncounter}>
                        {startEncounter.isPending ? "Starting…" : "Start encounter"}
                      </Button>
                    </div>
                  ) : (
                    <TreatmentSection
                      status={encounter.status}
                      treatmentPlan={treatmentPlan}
                      onTreatmentPlanChange={(value) => updateClinicalField("treatment_plan", value, setTreatmentPlan)}
                      onSave={saveCurrentDraft}
                      savePending={saveDraft.isPending || signNote.isPending || dispositionMutationPending || followUpMutationPending}
                      saveState={draftSaveState}
                      savedAt={savedAt}
                      disposition={disposition}
                      dispositionNote={dispositionNote}
                      followUp={encounter.follow_up}
                      followUpRecommendedDate={followUpRecommendedDate}
                      followUpInstructions={followUpInstructions}
                      followUpSaveState={followUpSaveState}
                      followUpSavePending={followUpMutationPending}
                      followUpError={followUpError}
                      followUpConflict={followUpConflict}
                      followUpFormDirty={followUpFormDirty}
                      followUpRevisionUncertain={consultationRevisionUncertain}
                      onFollowUpRecommendedDateChange={(value) => updateFollowUpDraft({ recommendedDate: value })}
                      onFollowUpInstructionsChange={(value) => updateFollowUpDraft({ instructions: value })}
                      onSaveFollowUp={saveCurrentFollowUp}
                      onDiscardFollowUp={discardFollowUpChanges}
                      dispositionSaveState={dispositionSaveState}
                      dispositionSavePending={dispositionMutationPending}
                      dispositionError={dispositionError}
                      dispositionConflict={dispositionConflict}
                      dispositionFormDirty={dispositionFormDirty}
                      dispositionRevisionUncertain={consultationRevisionUncertain}
                      onDispositionChange={setDispositionDraftValue}
                      onDispositionNoteChange={setDispositionDraftNote}
                      onSaveDisposition={saveCurrentDisposition}
                      onDiscardDisposition={discardDispositionChanges}
                    />
                )
                ) : activeSection === "diagnosis" ? (
                  !encounter ? (
                    <div className="space-y-3">
                      <p className="text-[12.5px] font-medium text-secondary">
                        Not recorded yet. Start the encounter to record the diagnosis disposition.
                      </p>
                      <Button disabled={startEncounter.isPending} onClick={startCurrentEncounter}>
                        {startEncounter.isPending ? "Starting…" : "Start encounter"}
                      </Button>
                    </div>
                  ) : (
                    <DiagnosisSection
                      status={encounter.status}
                      diagnoses={encounter.diagnoses ?? []}
                      canManage={can("clinical.note.create")}
                      mutationPending={diagnosisMutationPending || saveDraft.isPending || signNote.isPending || dispositionMutationPending || followUpMutationPending}
                      mutationError={diagnosisMutationError}
                      formState={diagnosisFormState}
                      onFormStateChange={setDiagnosisFormState}
                      onCreate={createDiagnosis}
                      onSaveEdit={saveDiagnosisEdit}
                      onSetPrimary={setPrimaryDiagnosis}
                      onRemove={removeDiagnosis}
                      onFormDirtyChange={(dirty) => {
                        diagnosisFormDirtyRef.current = dirty;
                      }}
                    />
                  )
                ) : activeSection !== "notes" ? (
                  activeSection === "summary" && !encounter ? (
                    <div className="space-y-3">
                      <p className="text-[12.5px] font-medium text-secondary">
                        Start the encounter to open the consultation note for this visit.
                      </p>
                      <Button disabled={startEncounter.isPending} onClick={startCurrentEncounter}>
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
                    <Button disabled={startEncounter.isPending} onClick={startCurrentEncounter}>
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
                      <Button variant="secondary" disabled={saveDraft.isPending || signNote.isPending || diagnosisMutationPending || dispositionMutationPending} onClick={saveCurrentDraft}>
                        {saveDraft.isPending ? "Saving…" : "Save draft"}
                      </Button>
                      <DraftSaveStatus saveState={draftSaveState} savedAt={savedAt} />
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
                        <Button disabled={saveDraft.isPending || signNote.isPending || allergyMutationPending || diagnosisMutationPending || dispositionMutationPending || followUpMutationPending} onClick={signCurrentDraft}>
                          {signNote.isPending ? "Signing…" : "Confirm signature"}
                        </Button>
                      </div>
                    ) : (
                      <Button disabled={saveDraft.isPending || signNote.isPending || allergyMutationPending || diagnosisMutationPending || dispositionMutationPending || followUpMutationPending} onClick={() => setConfirmingSign(true)}>Sign consultation</Button>
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
