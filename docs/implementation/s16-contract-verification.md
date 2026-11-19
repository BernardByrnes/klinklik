# S-16 contract verification

Base: `db19523` (published main / `release/v1-clinic-spine`).

## Summary

| Family | Active contracts | Range/exclusion |
| --- | --- | --- |
| PC | 80 | PC-001..PC-081 excluding retired PC-061 |
| CMD | 134 | CMD-001..CMD-136 excluding retired CMD-097 and CMD-107 |
| MIG | 11 | MIG-001..MIG-011 |
| ADR | 14 | ADR-C-01..ADR-C-14 |

Status counts: ADR|SETTLED=14, CMD|EVIDENCE LINKED=104, CMD|FENCED=30, MIG|IMPLEMENTED=11, PC|FENCED=11, PC|IMPLEMENTED=62, PC|PARTIAL=7.

Status meaning: **IMPLEMENTED/EVIDENCE LINKED** means the contract is mapped to the named code or slice test evidence; **PARTIAL** means a legacy/renamed or inline representation; **FENCED** means the applicable registry authority/slice remains blocked and no executable evidence is claimed. **SETTLED** is used only for the blueprint ADR register.

## Contracts

| ID | Family | Name | Owner | Status | Evidence | Note |
| --- | --- | --- | --- | --- | --- | --- |
| PC-001 | PC | Organisation | tenancy | IMPLEMENTED | `backend/tenancy/models.py` | Model/migration evidence present. |
| PC-002 | PC | Facility | tenancy | IMPLEMENTED | `backend/tenancy/models.py` | Model/migration evidence present. |
| PC-003 | PC | Department | tenancy | IMPLEMENTED | `backend/tenancy/models.py` | Model/migration evidence present. |
| PC-004 | PC | User/member authority references | accounts | IMPLEMENTED | `backend/accounts/models.py` | Model/migration evidence present. |
| PC-005 | PC | Patient | patients | IMPLEMENTED | `backend/patients/models.py` | Model/migration evidence present. |
| PC-006 | PC | Visit | scheduling | IMPLEMENTED | `backend/scheduling/models.py` | Model/migration evidence present. |
| PC-007 | PC | QueueEntry | scheduling | IMPLEMENTED | `backend/scheduling/models.py` | Model/migration evidence present. |
| PC-008 | PC | TriageRecord | clinical | IMPLEMENTED | `backend/clinical/models.py` | Model/migration evidence present. |
| PC-009 | PC | VitalsObservation | clinical | IMPLEMENTED | `backend/clinical/models.py` | Model/migration evidence present. |
| PC-010 | PC | Encounter | clinical | IMPLEMENTED | `backend/clinical/models.py` | Model/migration evidence present. |
| PC-011 | PC | ClinicalNote | clinical | IMPLEMENTED | `backend/clinical/models.py` | Model/migration evidence present. |
| PC-012 | PC | ClinicalNoteVersion | clinical | IMPLEMENTED | `backend/clinical/models.py` | Model/migration evidence present. |
| PC-013 | PC | PatientAllergy | clinical | IMPLEMENTED | `backend/clinical/models.py` | Model/migration evidence present. |
| PC-014 | PC | PatientAllergyState | clinical | IMPLEMENTED | `backend/clinical/models.py` | Model/migration evidence present. |
| PC-015 | PC | LabOrder | laboratory | IMPLEMENTED | `backend/laboratory/models.py` | Model/migration evidence present. |
| PC-016 | PC | LabOrderItem | laboratory | IMPLEMENTED | `backend/laboratory/models.py` | Model/migration evidence present. |
| PC-017 | PC | LabSpecimenCustody | laboratory | PARTIAL | `backend/laboratory/models.py` | Implemented under a legacy/renamed or inline representation; registry field naming differs. |
| PC-018 | PC | LabResult | laboratory | IMPLEMENTED | `backend/laboratory/models.py` | Model/migration evidence present. |
| PC-019 | PC | LabResultVersion | laboratory | IMPLEMENTED | `backend/laboratory/models.py` | Model/migration evidence present. |
| PC-020 | PC | MedicationProduct | pharmacy | IMPLEMENTED | `backend/pharmacy/models.py` | Model/migration evidence present. |
| PC-021 | PC | Prescription | pharmacy | IMPLEMENTED | `backend/pharmacy/models.py` | Model/migration evidence present. |
| PC-022 | PC | PrescriptionLine | pharmacy | PARTIAL | `backend/pharmacy/models.py` | Implemented under a legacy/renamed or inline representation; registry field naming differs. |
| PC-023 | PC | Dispense | pharmacy | IMPLEMENTED | `backend/pharmacy/models.py` | Model/migration evidence present. |
| PC-024 | PC | DispenseLine | pharmacy | IMPLEMENTED | `backend/pharmacy/models.py` | Model/migration evidence present. |
| PC-025 | PC | Batch | inventory | PARTIAL | `backend/inventory/models.py` | Implemented under a legacy/renamed or inline representation; registry field naming differs. |
| PC-026 | PC | StockLocation | inventory | IMPLEMENTED | `backend/inventory/models.py` | Model/migration evidence present. |
| PC-027 | PC | BatchLocationBalance | inventory | IMPLEMENTED | `backend/inventory/models.py` | Model/migration evidence present. |
| PC-028 | PC | StockMovement | inventory | IMPLEMENTED | `backend/inventory/models.py` | Model/migration evidence present. |
| PC-029 | PC | StockReceipt | inventory | IMPLEMENTED | `backend/inventory/models.py` | Model/migration evidence present. |
| PC-030 | PC | StockReceiptLine | inventory | IMPLEMENTED | `backend/inventory/models.py` | Model/migration evidence present. |
| PC-031 | PC | StockCount | inventory | IMPLEMENTED | `backend/inventory/models.py` | Model/migration evidence present. |
| PC-032 | PC | StockCountLine | inventory | IMPLEMENTED | `backend/inventory/models.py` | Model/migration evidence present. |
| PC-033 | PC | StockAdjustment | inventory | IMPLEMENTED | `backend/inventory/models.py` | Model/migration evidence present. |
| PC-034 | PC | QuarantineRecord | inventory | IMPLEMENTED | `backend/inventory/models.py` | Model/migration evidence present. |
| PC-035 | PC | DisposalRecord | inventory | IMPLEMENTED | `backend/inventory/models.py` | Model/migration evidence present. |
| PC-036 | PC | Invoice | billing | IMPLEMENTED | `backend/billing/models.py` | Model/migration evidence present. |
| PC-037 | PC | InvoiceLine | billing | PARTIAL | `backend/billing/models.py` | Implemented under a legacy/renamed or inline representation; registry field naming differs. |
| PC-038 | PC | Payment | billing | IMPLEMENTED | `backend/billing/models.py` | Model/migration evidence present. |
| PC-039 | PC | PaymentAllocation | billing | IMPLEMENTED | `backend/billing/models.py` | Model/migration evidence present. |
| PC-040 | PC | Receipt | billing | PARTIAL | `backend/billing/models.py` | Implemented under a legacy/renamed or inline representation; registry field naming differs. |
| PC-041 | PC | CashierShift | billing | IMPLEMENTED | `backend/billing/models.py` | Model/migration evidence present. |
| PC-042 | PC | CreditNote | billing | IMPLEMENTED | `backend/billing/models.py` | Model/migration evidence present. |
| PC-043 | PC | RefundRequest | billing | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Owner authority remains blocked for this contract's slice. |
| PC-044 | PC | Refund | billing | IMPLEMENTED | `backend/billing/models.py` | Model/migration evidence present. |
| PC-045 | PC | Appointment fragment record | scheduling | IMPLEMENTED | `backend/scheduling/models.py` | Model/migration evidence present. |
| PC-046 | PC | ANCEnrolment | maternity | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Owner authority remains blocked for this contract's slice. |
| PC-047 | PC | AuditEvent | audit | IMPLEMENTED | `backend/audit/models.py` | Model/migration evidence present. |
| PC-048 | PC | IdempotencyRecord | core | IMPLEMENTED | `backend/core/models.py` | Model/migration evidence present. |
| PC-049 | PC | NumberSequence | core | IMPLEMENTED | `backend/core/models.py` | Model/migration evidence present. |
| PC-050 | PC | MigrationReconciliation | core | IMPLEMENTED | `backend/core/models.py` | Model/migration evidence present. |
| PC-051 | PC | ArrivalEnquiry | scheduling | IMPLEMENTED | `backend/scheduling/models.py` | Model/migration evidence present. |
| PC-052 | PC | TriageRecordVersion | clinical | IMPLEMENTED | `backend/clinical/models.py` | Model/migration evidence present. |
| PC-053 | PC | Diagnosis | clinical | IMPLEMENTED | `backend/clinical/models.py` | Model/migration evidence present. |
| PC-054 | PC | ProcedureOrder | clinical | IMPLEMENTED | `backend/clinical/models.py` | Model/migration evidence present. |
| PC-055 | PC | Referral | clinical | IMPLEMENTED | `backend/clinical/models.py` | Model/migration evidence present. |
| PC-056 | PC | FollowUpRecommendation | scheduling | IMPLEMENTED | `backend/scheduling/models.py` | Model/migration evidence present. |
| PC-057 | PC | MedicalCertificate | clinical | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Owner authority remains blocked for this contract's slice. |
| PC-058 | PC | LabTestDefinition | laboratory | IMPLEMENTED | `backend/laboratory/models.py` | Model/migration evidence present. |
| PC-059 | PC | Supplier | inventory | IMPLEMENTED | `backend/inventory/models.py` | Model/migration evidence present. |
| PC-060 | PC | PaymentMethodConfiguration | billing | IMPLEMENTED | `backend/billing/models.py` | Model/migration evidence present. |
| PC-062 | PC | InventoryThreshold | inventory | IMPLEMENTED | `backend/inventory/models.py` | Model/migration evidence present. |
| PC-063 | PC | ProductPrice | pharmacy | IMPLEMENTED | `backend/pharmacy/models.py` | Model/migration evidence present. |
| PC-064 | PC | ServiceDefinition | billing | IMPLEMENTED | `backend/billing/models.py` | Model/migration evidence present. |
| PC-065 | PC | PriceList | billing | IMPLEMENTED | `backend/billing/models.py` | Model/migration evidence present. |
| PC-066 | PC | ServicePrice | billing | IMPLEMENTED | `backend/billing/models.py` | Model/migration evidence present. |
| PC-067 | PC | VisitPayerBinding | billing | IMPLEMENTED | `backend/billing/models.py` | Model/migration evidence present. |
| PC-068 | PC | DiscountWaiver | billing | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Owner authority remains blocked for this contract's slice. |
| PC-069 | PC | LateResultReview | clinical | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Owner authority remains blocked for this contract's slice. |
| PC-070 | PC | PatientProblem | clinical | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Owner authority remains blocked for this contract's slice. |
| PC-071 | PC | PatientObstetricSummary | clinical | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Owner authority remains blocked for this contract's slice. |
| PC-072 | PC | ANCVisit | maternity | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Owner authority remains blocked for this contract's slice. |
| PC-073 | PC | ANCHistoryVersion | maternity | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Owner authority remains blocked for this contract's slice. |
| PC-074 | PC | ANCRiskFactor | maternity | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Owner authority remains blocked for this contract's slice. |
| PC-075 | PC | ANCObstetricExamination | maternity | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Owner authority remains blocked for this contract's slice. |
| PC-076 | PC | PharmacyClaim | pharmacy | IMPLEMENTED | `backend/pharmacy/models.py` | Model/migration evidence present. |
| PC-077 | PC | DispenseSubstitution | pharmacy | PARTIAL | `backend/pharmacy/models.py` | Implemented under a legacy/renamed or inline representation; registry field naming differs. |
| PC-078 | PC | LabAnalyteDefinition | laboratory | IMPLEMENTED | `backend/laboratory/models.py` | Model/migration evidence present. |
| PC-079 | PC | LabReferenceRange | laboratory | IMPLEMENTED | `backend/laboratory/models.py` | Model/migration evidence present. |
| PC-080 | PC | LabResultAnalyteValue | laboratory | PARTIAL | `backend/laboratory/models.py` | Implemented under a legacy/renamed or inline representation; registry field naming differs. |
| PC-081 | PC | FacilityWorkflowPolicy | tenancy | IMPLEMENTED | `backend/tenancy/models.py` | Model/migration evidence present. |
| CMD-001 | CMD | visit_check_in | application.reception | EVIDENCE LINKED | `backend/tests/test_s01_reception.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-002 | CMD | patient_register | application.reception | EVIDENCE LINKED | `backend/tests/test_s01_reception.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-003 | CMD | visit_payer_reprice | application.reception | EVIDENCE LINKED | `backend/tests/test_s07_repricing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-004 | CMD | emergency_visit_start | application.reception | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-005 | CMD | emergency_setup_complete | application.reception | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-006 | CMD | visit_cancel_error | application.reception | EVIDENCE LINKED | `backend/tests/test_s01_reception.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-007 | CMD | visit_close_lwbs | application.reception | EVIDENCE LINKED | `backend/tests/test_s01_reception.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-008 | CMD | visit_close | application.reception | EVIDENCE LINKED | `backend/tests/test_s08_closure.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-009 | CMD | stale_visit_zero_record | application.operations | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-010 | CMD | visit_referral_source_record | application.reception | EVIDENCE LINKED | `backend/tests/test_s01_reception.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-011 | CMD | arrival_enquiry_record | application.reception | EVIDENCE LINKED | `backend/tests/test_s01_reception.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-012 | CMD | visit_slip_reprint | application.documents | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-013 | CMD | queue_call | application.queue | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-014 | CMD | queue_start_service | application.queue | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-015 | CMD | queue_assign | application.queue | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-016 | CMD | queue_hold | application.queue | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-017 | CMD | queue_resume | application.queue | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-018 | CMD | queue_transfer | application.queue | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-019 | CMD | queue_complete | application.queue | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-020 | CMD | queue_no_response | application.queue | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-021 | CMD | queue_requeue | application.queue | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-022 | CMD | queue_cancel | application.queue | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-023 | CMD | queue_takeover | application.queue | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-024 | CMD | queue_expire_sweep | application.operations | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-025 | CMD | triage_start | application.clinical | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-026 | CMD | triage_save | application.clinical | EVIDENCE LINKED | `backend/tests/test_s03_triage.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-027 | CMD | triage_complete | application.clinical | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-028 | CMD | triage_amend | application.clinical | EVIDENCE LINKED | `backend/tests/test_s03_triage.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-029 | CMD | repeat_vitals_record | application.clinical | EVIDENCE LINKED | `backend/tests/test_s03_triage.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-030 | CMD | encounter_open | application.clinical | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-031 | CMD | encounter_draft_save | application.clinical | EVIDENCE LINKED | `backend/tests/test_s04_encounter.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-032 | CMD | encounter_park_awaiting_results | application.clinical | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-033 | CMD | encounter_results_readiness | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-034 | CMD | encounter_resume | application.clinical | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-035 | CMD | encounter_sign | application.clinical | EVIDENCE LINKED | `backend/tests/test_s04_encounter.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-036 | CMD | encounter_sign_pending | application.clinical | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-037 | CMD | encounter_void_entered_error | application.clinical | EVIDENCE LINKED | `backend/tests/test_s04_encounter.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-038 | CMD | encounter_addendum | application.clinical | EVIDENCE LINKED | `backend/tests/test_s04_encounter.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-039 | CMD | encounter_transfer_takeover | application.clinical | EVIDENCE LINKED | `backend/tests/test_s04_encounter.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-040 | CMD | lab_order | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-041 | CMD | lab_gate_release | application.billing | EVIDENCE LINKED | `backend/tests/test_s11_lab.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-042 | CMD | lab_collect | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-043 | CMD | lab_reject_specimen | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s11_lab.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-044 | CMD | lab_result_save | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s11_lab.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-045 | CMD | lab_verify | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s11_lab.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-046 | CMD | lab_release | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-047 | CMD | lab_cancel | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-048 | CMD | lab_refer_out | application.laboratory | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-049 | CMD | lab_result_correct | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s11_lab.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-050 | CMD | lab_late_result | application.laboratory | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-051 | CMD | lab_external_order | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s11_lab.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-052 | CMD | prescription_draft_save | application.pharmacy | EVIDENCE LINKED | `backend/tests/test_s12_dispensing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-053 | CMD | prescription_activate | application.clinical | EVIDENCE LINKED | `backend/tests/test_s12_dispensing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-054 | CMD | prescription_cancel | application.pharmacy | EVIDENCE LINKED | `backend/tests/test_s12_dispensing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-055 | CMD | prescription_repeat | application.pharmacy | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-056 | CMD | provisional_dispense_create | application.pharmacy | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-057 | CMD | dispense_gate_release | application.billing | EVIDENCE LINKED | `backend/tests/test_s12_dispensing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-058 | CMD | dispense_handover | application.pharmacy | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-059 | CMD | dispense_cancel | application.pharmacy | EVIDENCE LINKED | `backend/tests/test_s12_dispensing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-060 | CMD | prescription_partial_close | application.pharmacy | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-061 | CMD | dispense_reverse_return | application.pharmacy | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-062 | CMD | otc_sale | application.pharmacy | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-063 | CMD | stock_receive | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-064 | CMD | stock_transfer | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-065 | CMD | stock_count_submit | application.inventory | EVIDENCE LINKED | `backend/tests/test_s10_counts.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-066 | CMD | stock_count_approve | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-067 | CMD | stock_adjust | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-068 | CMD | stock_quarantine | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-069 | CMD | stock_dispose | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-070 | CMD | stock_correction | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-071 | CMD | invoice_issue | application.billing | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-072 | CMD | invoice_source_line_add | application.billing | EVIDENCE LINKED | `backend/tests/test_s04_encounter.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-073 | CMD | invoice_manual_line_add | application.billing | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-074 | CMD | invoice_line_void | application.billing | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-075 | CMD | payment_confirm_allocate | application.billing | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-076 | CMD | payment_reverse | application.billing | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-077 | CMD | credit_note_create | application.billing | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-078 | CMD | refund_request | application.billing | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-079 | CMD | refund_process | application.billing | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-080 | CMD | receipt_issue | application.billing | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-081 | CMD | receipt_reprint | application.documents | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-082 | CMD | cashier_shift_open | application.billing | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-083 | CMD | cashier_shift_close | application.billing | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-084 | CMD | invoice_void | application.billing | EVIDENCE LINKED | `backend/tests/test_s01_reception.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-085 | CMD | anc_enroll | application.maternity | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-086 | CMD | anc_contact_compose | application.maternity | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-087 | CMD | appointment_no_show_check_in | application.reception | EVIDENCE LINKED | `backend/tests/test_s01_reception.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-088 | CMD | medication_product_create | application.catalogue | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-089 | CMD | product_price_set | application.catalogue | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-090 | CMD | medication_product_deactivate | application.catalogue | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-091 | CMD | catalogue_import | application.catalogue | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-092 | CMD | patient_allergy_record | application.clinical | EVIDENCE LINKED | `backend/tests/test_s03_triage.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-093 | CMD | patient_allergy_status_set | application.clinical | EVIDENCE LINKED | `backend/tests/test_s03_triage.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-094 | CMD | allergy_entered_error | application.clinical | EVIDENCE LINKED | `backend/tests/test_s03_triage.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-095 | CMD | encounter_allergy_review | application.clinical | EVIDENCE LINKED | `backend/tests/test_s04_encounter.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-096 | CMD | diagnosis_save | application.clinical | EVIDENCE LINKED | `backend/tests/test_s04_encounter.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-098 | CMD | treatment_plan_save | application.clinical | EVIDENCE LINKED | `backend/tests/test_s04_encounter.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-099 | CMD | disposition_set | application.clinical | EVIDENCE LINKED | `backend/tests/test_s04_encounter.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-100 | CMD | referral_letter_create | application.documents | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-101 | CMD | followup_record | application.clinical | EVIDENCE LINKED | `backend/tests/test_s04_encounter.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-102 | CMD | procedure_order | application.clinical | EVIDENCE LINKED | `backend/tests/test_s04_encounter.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-103 | CMD | medical_certificate_issue | application.documents | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-104 | CMD | stock_location_configure | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-105 | CMD | supplier_upsert | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-106 | CMD | payment_method_configure | application.billing | EVIDENCE LINKED | `backend/tests/test_s05_billing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-108 | CMD | lab_test_catalogue_configure | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s11_lab.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-109 | CMD | lab_self_verification_policy_set | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s11_lab.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-110 | CMD | product_instruction_template_set | application.pharmacy | EVIDENCE LINKED | `backend/tests/test_s12_dispensing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-111 | CMD | inventory_threshold_set | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-112 | CMD | invoice_discount_waiver | application.billing | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-113 | CMD | dispense_substitute | application.pharmacy | EVIDENCE LINKED | `backend/tests/test_s12_dispensing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-114 | CMD | dispense_basket_update | application.pharmacy | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-115 | CMD | dispense_item_not_dispensed | application.pharmacy | EVIDENCE LINKED | `backend/tests/test_s12_dispensing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-116 | CMD | late_result_acknowledge | application.clinical | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-117 | CMD | expired_delivery_quarantine_intake | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-118 | CMD | patient_problem_add | application.clinical | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-119 | CMD | patient_problem_resolve | application.clinical | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-120 | CMD | patient_obstetric_summary_update | application.clinical | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-121 | CMD | anc_history_update | application.maternity | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-122 | CMD | anc_risk_factors_record | application.maternity | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-123 | CMD | anc_obstetric_exam_record | application.maternity | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-124 | CMD | pharmacy_claim | application.pharmacy | EVIDENCE LINKED | `backend/tests/test_s12_dispensing.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-125 | CMD | anc_dating_basis_update | application.maternity | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-126 | CMD | anc_contact_sequence_update | application.maternity | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-127 | CMD | queue_priority_change | application.queue | EVIDENCE LINKED | `backend/tests/test_s02_queue.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-128 | CMD | repeat_vitals_request | application.clinical | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-129 | CMD | stale_visit_abandonment | application.operations | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-130 | CMD | second_visit_override | application.reception | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-131 | CMD | stock_adjustment_approve | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-132 | CMD | procedure_perform | application.clinical | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-133 | CMD | service_gate_override | application.billing | FENCED | `IMPLEMENTATION_BLUEPRINT.md` | Fenced by the named slice/owner decision; no executable evidence claimed. |
| CMD-134 | CMD | lab_result_entry_reject | application.laboratory | EVIDENCE LINKED | `backend/tests/test_s11_lab.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-135 | CMD | arrival_enquiry_convert | application.reception | EVIDENCE LINKED | `backend/tests/test_s01_reception.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| CMD-136 | CMD | stock_ledger_reconcile | application.inventory | EVIDENCE LINKED | `backend/tests/test_s09_inventory.py` | Contract mapped to the slice test evidence; branch-level gaps are listed in the dossier findings. |
| MIG-001 | MIG | migration reconciliation | core | IMPLEMENTED | `backend/core/migration_reconciliation.py` | Reconciliation/RLS evidence: backend/core/migration_reconciliation.py, backend/tests/test_s01_postgres.py |
| MIG-002 | MIG | migration reconciliation | core | IMPLEMENTED | `backend/core/migration_reconciliation.py` | Reconciliation/RLS evidence: backend/core/migration_reconciliation.py, backend/tests/test_s02_postgres.py |
| MIG-003 | MIG | migration reconciliation | core | IMPLEMENTED | `backend/core/mig003.py` | Reconciliation/RLS evidence: backend/core/mig003.py, backend/tests/test_s03_mig003.py |
| MIG-004 | MIG | migration reconciliation | core | IMPLEMENTED | `backend/core/mig004.py` | Reconciliation/RLS evidence: backend/core/mig004.py, backend/tests/test_s04_mig004.py |
| MIG-005 | MIG | migration reconciliation | core | IMPLEMENTED | `backend/core/migration_reconciliation.py` | Reconciliation/RLS evidence: backend/core/migration_reconciliation.py, backend/tests/test_s05_mig005.py |
| MIG-006 | MIG | migration reconciliation | core | IMPLEMENTED | `backend/core/migration_reconciliation.py` | Reconciliation/RLS evidence: backend/core/migration_reconciliation.py, backend/tests/test_s06_mig010.py |
| MIG-007 | MIG | migration reconciliation | core | IMPLEMENTED | `backend/core/migration_reconciliation.py` | Reconciliation/RLS evidence: backend/core/migration_reconciliation.py, backend/tests/test_s06_mig010.py |
| MIG-008 | MIG | migration reconciliation | core | IMPLEMENTED | `backend/core/migration_reconciliation.py` | Reconciliation/RLS evidence: backend/core/migration_reconciliation.py, backend/tests/test_s06_mig010.py |
| MIG-009 | MIG | migration reconciliation | core | IMPLEMENTED | `backend/core/migration_reconciliation.py` | Reconciliation/RLS evidence: backend/core/migration_reconciliation.py, backend/tests/test_s06_mig010.py |
| MIG-010 | MIG | migration reconciliation | core | IMPLEMENTED | `backend/core/migration_reconciliation.py` | Reconciliation/RLS evidence: backend/core/migration_reconciliation.py, backend/tests/test_s06_mig010.py |
| MIG-011 | MIG | migration reconciliation | core | IMPLEMENTED | `backend/core/rls.py` | Reconciliation/RLS evidence: backend/core/rls.py, backend/tests/test_s00_postgres.py |
| ADR-C-01 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-02 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-03 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-04 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-05 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-06 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-07 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-08 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-09 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-10 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-11 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-12 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-13 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
| ADR-C-14 | ADR | architecture decision | blueprint | SETTLED | `IMPLEMENTATION_BLUEPRINT.md` | ADR-C-01..14 register state retained; no implementation override claimed. |
