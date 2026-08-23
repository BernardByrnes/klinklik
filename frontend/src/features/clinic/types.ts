export type Patient = {
  id: string;
  patient_no: string;
  display_name: string;
  first_name: string;
  last_name: string;
  sex: string;
  date_of_birth: string | null;
  phone: string;
};

export type Department = {
  id: string;
  name: string;
  code: string;
  facility: string;
};

export type QueueEntry = {
  id: string;
  queue_label: string;
  patient: string;
  patient_name: string;
  department: string;
  department_name: string;
  queue_date: string;
  sequence: number;
  visit_type: string;
  status: string;
  current_stage: string;
  arrival_at: string;
  claimed_by: string | null;
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

export type Encounter = {
  id: string;
  encounter_no: string;
  patient: string;
  patient_name: string;
  queue_entry: string;
  status: string;
  consultation_etag?: string;
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
