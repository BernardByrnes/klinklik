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
  Receipt,
  Service,
  Visit,
  VisitCancelErrorResponse,
  VisitCheckInResponse,
  VisitContextResponse,
} from "../../generated/api-client";

// Diagnosis mutations and their query both return DiagnosisStateResponse. Keep
// the consumer aligned with the generated response item's shape instead of
// importing a similarly named component that may drift independently.
export type Diagnosis = import("../../generated/api-client").DiagnosisStateResponse["diagnoses"][number];

export type AllergyStatus = import("../../generated/api-client").Encounter["allergy_status"];
