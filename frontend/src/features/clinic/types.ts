export type Patient = {
  id: string;
  patient_no: string;
  display_name: string;
  first_name: string;
  last_name: string;
  sex: string;
  date_of_birth: string | null;
  phone: string;
  village?: string;
  parish?: string;
  sub_county?: string;
  district?: string;
  next_of_kin_name?: string;
  next_of_kin_phone?: string;
  estimated_age_years?: number | null;
  estimated_age_months?: number | null;
  dob_estimated?: boolean;
  identity_status?: string;
  last_seen_at?: string | null;
  version?: number;
};

export type Department = {
  id: string;
  name: string;
  code: string;
  facility: string;
};

export type QueueEntry = {
  id: string;
  visit?: string | null;
  queue_label: string;
  patient: string;
  patient_name: string;
  department: string;
  department_name: string;
  queue_date: string;
  sequence: number;
  queue_type?: string;
  work_identity?: string;
  hold_reason?: string;
  priority?: string;
  visit_type: string;
  status: string;
  current_stage: string;
  arrival_at: string;
  claimed_by: string | null;
};

export type Visit = {
  id: string;
  patient: string;
  patient_name: string;
  facility: string;
  local_service_date: string;
  visit_type: string;
  state: string;
  payer_binding_id: string | null;
  referral_source_type: string;
  referral_source_name: string;
  results_review: boolean;
  version: number;
};

export type VisitCheckInResponse = {
  id: string;
  visit_id: string;
  queue_id: string | null;
  invoice_id: string | null;
  patient_id: string;
  next_action: string;
  visit: Visit;
  queue: QueueEntry | null;
  invoice: Invoice | null;
};

export type PatientRegisterResponse = Patient & {
  patient_id?: string;
  next_action?: string;
  patient?: Patient;
  duplicate_candidates?: Patient[];
};

export type ClinicalNoteContent = {
  consultation?: string;
  presenting_complaint?: string;
  hpi?: string;
  past_medical_history?: string;
  past_surgical_history?: string;
  family_history?: string;
  social_history?: string;
  general_examination?: string;
  cardiovascular_examination?: string;
  respiratory_examination?: string;
  abdominal_examination?: string;
  neurological_examination?: string;
  genitourinary_examination?: string;
  musculoskeletal_examination?: string;
  treatment_plan?: string;
  [key: string]: unknown;
};

export type ComplaintDurationUnit = "HOURS" | "DAYS" | "WEEKS" | "MONTHS";

export type PresentingComplaint = {
  text: string;
  duration_value: number | null;
  duration_unit: ComplaintDurationUnit | null;
};

export type ClinicalNote = {
  id: string;
  note_type: string;
  content: ClinicalNoteContent;
  status: string;
  author: string;
  signed_by: string | null;
  signed_at: string | null;
  current_version: number;
};

export type DiagnosisType = "WORKING" | "FINAL" | "NO_DIAGNOSIS";

export type Diagnosis = {
  id: string;
  encounter: string;
  diagnosis_type: DiagnosisType;
  code: string;
  label: string;
  coded: boolean;
  certainty_note: string;
  is_primary: boolean;
  no_diagnosis_reason: string;
  status: "ACTIVE";
  recorded_by: string;
  created_at: string;
  updated_at: string;
};

export type EncounterDisposition =
  | "TREATED_AND_DISCHARGED"
  | "REVIEW_SCHEDULED"
  | "REFERRED_OUT"
  | "ADMITTED_ELSEWHERE"
  | "LEFT_AGAINST_ADVICE"
  | "DECEASED"
  | "OTHER";

export type FollowUpRecommendation = {
  id: string;
  patient: string;
  encounter: string;
  recommended_date: string | null;
  instructions: string;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
};
export type Encounter = {
  id: string;
  encounter_no: string;
  patient: string;
  patient_name: string;
  queue_entry: string;
  status: string;
  consultation_etag?: string;
  disposition: EncounterDisposition | null;
  disposition_note: string;
  follow_up: FollowUpRecommendation | null;
  diagnoses: Diagnosis[];
  complaints: PresentingComplaint[];
  triage_complaint: string | null;
  allergy_status: AllergyStatus;
  active_allergies: ActiveAllergy[];
  allergy_revision: number;
  allergy_state_etag: string;
  allergies_reviewed_at: string | null;
  allergies_reviewed_revision: number | null;
  allergies_review_is_current: boolean;
  notes?: ClinicalNote[];
};

export type AllergyStatus = "NOT_RECORDED" | "NKA" | "UNKNOWN" | "RECORDED";

export type ActiveAllergy = {
  id: string;
  substance: string;
  reaction: string;
  severity: "MILD" | "MODERATE" | "SEVERE";
};

export type Service = {
  id: string;
  code: string;
  name: string;
  prices: Array<{ amount: string; currency: string }>;
};

export type InvoiceItem = {
  id: string;
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
};

export type Invoice = {
  id: string;
  invoice_no: string;
  patient: string;
  patient_name: string;
  encounter: string | null;
  status: string;
  currency: string;
  subtotal: string;
  total: string;
  amount_paid: string;
  balance: string;
  issued_at: string;
  items: InvoiceItem[];
  payments: Payment[];
};

export type Payment = {
  id: string;
  receipt_no: string;
  amount: string;
  method: string;
  status: string;
  received_at: string;
};

export type Receipt = {
  receipt_no: string;
  invoice_no: string;
  patient_name: string;
  patient_no: string;
  amount: string;
  currency: string;
  method: string;
  reference: string | null;
  received_at: string;
  invoice_total: string;
  invoice_balance: string;
  printable_text: string;
};
