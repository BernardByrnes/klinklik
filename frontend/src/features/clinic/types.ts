import type { LegacyQueueEntry, OperationalQueueRow } from "../../generated/api-client";

// Transport shapes are generated from the Django OpenAPI contract.
export type {
  ActiveAllergy,
  ArrivalEnquiryResponse,
  ClinicalNote,
  ClinicalNoteContent,
  ComplaintDurationUnit,
  CreatePatientRegisterResponse,
  Department,
  DepartmentEnvelope,
  DiagnosisType,
  Encounter,
  EncounterDisposition,
  FollowUpRecommendation,
  Invoice,
  InvoiceItem,
  Patient,
  PatientCheckInSummary,
  PatientDuplicateResponse,
  PatientDuplicateCandidate,
  PatientRegisterResponse,
  Payment,
  PresentingComplaint,
  QueueEntry,
  LegacyQueueEntry,
  OperationalQueueEnvelope,
  OperationalQueueRow,
  QueueMutationResponse,
  Receipt,
  Service,
  Visit,
  VisitCancelErrorResponse,
  VisitCheckInResponse,
  VisitCloseLwbs,
  VisitCloseLwbsResponse,
  VisitContextResponse,
} from "../../generated/api-client";

// Diagnosis mutations and their query both return DiagnosisStateResponse. Keep
// the consumer aligned with the generated response item's shape instead of
// importing a similarly named component that may drift independently.
export type Diagnosis = import("../../generated/api-client").DiagnosisStateResponse["diagnoses"][number];

export type AllergyStatus = import("../../generated/api-client").Encounter["allergy_status"];

export type CanonicalQueueState =
  | "WAITING_PAYMENT"
  | "WAITING"
  | "CALLED"
  | "IN_SERVICE"
  | "ON_HOLD"
  | "READY_TO_RESUME"
  | "COMPLETED"
  | "TRANSFERRED"
  | "CANCELLED"
  | "LWBS"
  | "NO_SHOW"
  | "EXPIRED";

type QueueStateSource = Pick<LegacyQueueEntry, "state" | "status"> | Pick<OperationalQueueRow, "state" | "status">;

const CANONICAL_QUEUE_STATES = new Set<CanonicalQueueState>([
  "WAITING_PAYMENT",
  "WAITING",
  "CALLED",
  "IN_SERVICE",
  "ON_HOLD",
  "READY_TO_RESUME",
  "COMPLETED",
  "TRANSFERRED",
  "CANCELLED",
  "LWBS",
  "NO_SHOW",
  "EXPIRED",
]);

export function canonicalQueueState(entry: QueueStateSource): CanonicalQueueState {
  if (entry.state && CANONICAL_QUEUE_STATES.has(entry.state as CanonicalQueueState)) {
    return entry.state as CanonicalQueueState;
  }
  const legacyMap: Record<string, CanonicalQueueState> = {
    WAITING: "WAITING",
    CALLED: "CALLED",
    IN_TRIAGE: "IN_SERVICE",
    TRIAGED: "COMPLETED",
    IN_CONSULTATION: "IN_SERVICE",
    COMPLETED: "COMPLETED",
    CANCELLED: "CANCELLED",
    WAITING_PAYMENT: "WAITING_PAYMENT",
    ON_HOLD: "ON_HOLD",
    READY_TO_RESUME: "READY_TO_RESUME",
    TRANSFERRED: "TRANSFERRED",
    LWBS: "LWBS",
    NO_SHOW: "NO_SHOW",
    EXPIRED: "EXPIRED",
  };
  return legacyMap[entry.status] ?? "WAITING";
}
