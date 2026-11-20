# S-17 CMD-by-command contract audit

Base: `54291e4` (published main / release/v1-clinic-spine).
Generated: 2026-11-19 (Africa/Kampala), local verification worktree `codex/s17-cmd-audit`.

This is an evidence audit. It does not change product code, add routes, or fix defects.

## Summary

- Active commands audited: 134 of 134; retired CMD-097 and CMD-107 excluded.
- Verdicts: FENCED 52, MISMATCH 2, PARTIAL 52, VERIFIED 28.
- Machine inventory: `docs/implementation/s17-cmd-audit.json`; machine assertions: `backend/tests/test_s17_cmd_audit.py`.
- Discrepancy severity: P2 54.
- Manual findings applied: 16.

## Discrepancy list (severity ordered)

| Severity | CMD | Operation | Verdict | Discrepancy | Evidence |
| --- | --- | --- | --- | --- | --- |
| P2 | CMD-001 | visit_check_in | VERIFIED | Legacy scheduling.CheckInView also exposes a POST check-ins route without declaring CMD-001; the canonical CMD-001 view is correctly labelled. | `backend/scheduling/views.py` |
| P2 | CMD-002 | patient_register | VERIFIED | Legacy patients.PatientListCreateView also exposes a POST patient-create route without declaring CMD-002; the canonical reception view is correctly labelled. | `backend/patients/views.py` |
| P2 | CMD-007 | visit_close_lwbs | PARTIAL | Declared audit codes not found in code: ['INVOICE_STATE', 'QUEUE_LWBS']. | `backend/tests/test_s01_reception.py` |
| P2 | CMD-014 | queue_start_service | MISMATCH | queue_start_service is exposed by QueueClaimView (POST queue/<pk>/claim/) without an idempotency_operation label. | `backend/scheduling/views.py:QueueClaimView` |
| P2 | CMD-016 | queue_hold | PARTIAL | INTERNAL step: service function defined and called; parent CMD call site requires manual confirmation. | `backend/tests/test_s02_queue.py` |
| P2 | CMD-017 | queue_resume | PARTIAL | INTERNAL step: service function defined and called; parent CMD call site requires manual confirmation. | `backend/tests/test_s02_queue.py` |
| P2 | CMD-019 | queue_complete | PARTIAL | INTERNAL step: service function defined and called; parent CMD call site requires manual confirmation. | `backend/tests/test_s02_queue.py` |
| P2 | CMD-020 | queue_no_response | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s02_queue.py` |
| P2 | CMD-024 | queue_expire_sweep | PARTIAL | QueueExpireSweepView declares CMD-024, but S-16 fenced the slice and no operational cutoff/authorization evidence was found; route exists, authority not evidenced. | `backend/application/queue/views.py:QueueExpireSweepView` |
| P2 | CMD-026 | triage_save | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s03_triage.py` |
| P2 | CMD-027 | triage_complete | PARTIAL | TriageView and TriageRecordCompleteView both declare CMD-027; they are MIG-002 mode-gated compatibility/canonical routes, so no simultaneous collision was proven, but one namespace serves two routes. | `backend/clinical/views.py:119,1287` |
| P2 | CMD-030 | encounter_open | PARTIAL | Declared audit codes not found in code: ['ENCOUNTER_RESUMED']. | `backend/tests/test_s02_queue.py` |
| P2 | CMD-034 | encounter_resume | PARTIAL | encounter_resume service exists but no dedicated route declares CMD-034; resume appears folded into the encounter open path under CMD-030. | `backend/clinical/services.py` |
| P2 | CMD-035 | encounter_sign | PARTIAL | Declared audit codes not found in code: ['CLINICAL_NOTE_SIGNED', 'QUEUE_COMPLETED']. | `backend/tests/test_s04_encounter.py` |
| P2 | CMD-038 | encounter_addendum | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s04_encounter.py` |
| P2 | CMD-039 | encounter_transfer_takeover | PARTIAL | encounter_transfer_takeover service exists but no route or idempotency namespace declares CMD-039. | `backend/clinical/services.py` |
| P2 | CMD-040 | lab_order | PARTIAL | Declared audit codes not found in code: ['INVOICE_LINES_ADDED']. | `backend/tests/test_s05_billing.py` |
| P2 | CMD-042 | lab_collect | PARTIAL | Declared audit codes not found in code: ['QUEUE_COMPLETED']. | `backend/tests/test_s02_queue.py` |
| P2 | CMD-044 | lab_result_save | PARTIAL | Declared audit codes not found in code: ['LAB_RESULT_DRAFT_SAVED', 'LAB_RESULT_ENTERED']. | `backend/tests/test_s11_lab.py` |
| P2 | CMD-045 | lab_verify | PARTIAL | No dedicated lab_verify route declares CMD-045; verification is bundled with release in LabResultReleaseView, so the standalone command is not evidenced. | `backend/laboratory/views.py:172` |
| P2 | CMD-046 | lab_release | PARTIAL | Declared audit codes not found in code: ['LAB_RESULT_VERIFIED']. | `backend/tests/test_s02_queue.py` |
| P2 | CMD-047 | lab_cancel | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s02_queue.py` |
| P2 | CMD-049 | lab_result_correct | PARTIAL | Declared audit codes not found in code: ['LAB_RESULT_CORRECTED']. | `backend/tests/test_s11_lab.py` |
| P2 | CMD-056 | provisional_dispense_create | PARTIAL | Declared audit codes not found in code: ['DISPENSE_CREATED', 'INVOICE_LINES_ADDED']. | `backend/tests/test_s05_billing.py` |
| P2 | CMD-058 | dispense_handover | PARTIAL | Declared audit codes not found in code: ['PRESCRIPTION_CLAIM_RELEASED', 'PRESCRIPTION_OUTCOME']. | `backend/tests/test_s09_inventory.py` |
| P2 | CMD-062 | otc_sale | PARTIAL | Declared audit codes not found in code: ['OTC_SALE_CONFIRMED', 'RECEIPT_ISSUED']. | `backend/tests/test_s05_billing.py` |
| P2 | CMD-063 | stock_receive | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s09_inventory.py` |
| P2 | CMD-064 | stock_transfer | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s09_inventory.py` |
| P2 | CMD-066 | stock_count_approve | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s09_inventory.py` |
| P2 | CMD-068 | stock_quarantine | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s09_inventory.py` |
| P2 | CMD-069 | stock_dispose | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s09_inventory.py` |
| P2 | CMD-071 | invoice_issue | PARTIAL | D-13: canonical invoice_issue runs through visit check-in (issue_exact_source_lines); manual InvoiceListCreateView now uses the documented compat namespace and is allowlisted. | `backend/billing/views.py:71,112` |
| P2 | CMD-073 | invoice_manual_line_add | PARTIAL | Declared audit codes not found in code: ['INVOICE_MANUAL_LINE_ADDED']. | `backend/tests/test_s05_billing.py` |
| P2 | CMD-075 | payment_confirm_allocate | PARTIAL | Owner-authorised compatibility namespace: legacy InvoicePaymentView uses 'legacy.invoice.payment.compat' and is allowlisted in the machine test; canonical InvoiceCanonicalPaymentView retains CMD-075. No route retired. | `backend/billing/views.py:175,205` |
| P2 | CMD-076 | payment_reverse | PARTIAL | Declared audit codes not found in code: ['ALLOCATIONS_REVERSED', 'INVOICE_STATE']. | `backend/tests/test_s05_billing.py` |
| P2 | CMD-077 | credit_note_create | PARTIAL | Declared audit codes not found in code: ['CREDIT_NOTE_CREATED', 'INVOICE_STATE']. | `backend/tests/test_s05_billing.py` |
| P2 | CMD-079 | refund_process | PARTIAL | Declared audit codes not found in code: ['REFUND_PROCESSED']. | `backend/tests/test_s05_billing.py` |
| P2 | CMD-082 | cashier_shift_open | PARTIAL | Declared audit codes not found in code: ['CASHIER_SHIFT_OPENED']. | `backend/tests/test_s05_billing.py` |
| P2 | CMD-083 | cashier_shift_close | PARTIAL | Declared audit codes not found in code: ['CASHIER_SHIFT_CLOSED', 'CASHIER_SHIFT_FORCE_CLOSED']. | `backend/tests/test_s05_billing.py` |
| P2 | CMD-087 | appointment_no_show_check_in | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s01_reception.py` |
| P2 | CMD-088 | medication_product_create | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s09_inventory.py` |
| P2 | CMD-089 | product_price_set | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s09_inventory.py` |
| P2 | CMD-092 | patient_allergy_record | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s03_triage.py` |
| P2 | CMD-093 | patient_allergy_status_set | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s03_triage.py` |
| P2 | CMD-094 | allergy_entered_error | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s03_triage.py` |
| P2 | CMD-096 | diagnosis_save | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s04_encounter.py` |
| P2 | CMD-099 | disposition_set | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s04_encounter.py` |
| P2 | CMD-101 | followup_record | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s04_encounter.py` |
| P2 | CMD-104 | stock_location_configure | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s09_inventory.py` |
| P2 | CMD-105 | supplier_upsert | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s09_inventory.py` |
| P2 | CMD-108 | lab_test_catalogue_configure | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s11_lab.py` |
| P2 | CMD-111 | inventory_threshold_set | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s09_inventory.py` |
| P2 | CMD-115 | dispense_item_not_dispensed | PARTIAL | Declared audit codes not found in code: ['DISPENSE_ITEM_NOT_DISPENSED', 'INVOICE_LINE_VOIDED_OR_REDUCED']. | `backend/tests/test_s12_dispensing.py` |
| P2 | CMD-124 | pharmacy_claim | PARTIAL | Declared audit codes not found in code: ['PRESCRIPTION_ACCESSED']. | `backend/tests/test_s12_dispensing.py` |
| P2 | CMD-131 | stock_adjustment_approve | PARTIAL | Slice test file does not name this CMD or operation; test exercise not proven mechanically. | `backend/tests/test_s09_inventory.py` |
| P2 | CMD-136 | stock_ledger_reconcile | MISMATCH | Registry declares stock_ledger_reconcile as INTERNAL, but LedgerReconcileView is an HTTP POST route declaring CMD-136; route/declared-location conflict. | `backend/inventory/views.py:581` |
| P3 | CMD-004 | emergency_visit_start | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-005 | emergency_setup_complete | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-009 | stale_visit_zero_record | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-012 | visit_slip_reprint | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-028 | triage_amend | FENCED | No view declares this CMD id; no HTTP route evidence. | `backend/tests/test_s03_triage.py` |
| P3 | CMD-029 | repeat_vitals_record | FENCED | No view declares this CMD id; no HTTP route evidence. | `backend/tests/test_s03_triage.py` |
| P3 | CMD-032 | encounter_park_awaiting_results | FENCED | No view declares this CMD id; no HTTP route evidence. | `backend/tests/test_s02_queue.py` |
| P3 | CMD-033 | encounter_results_readiness | FENCED | INTERNAL step: declared service function not found. | `backend/tests/test_s02_queue.py` |
| P3 | CMD-036 | encounter_sign_pending | FENCED | No view declares this CMD id; no HTTP route evidence. | `backend/tests/test_s02_queue.py` |
| P3 | CMD-037 | encounter_void_entered_error | FENCED | No view declares this CMD id; no HTTP route evidence. | `backend/tests/test_s04_encounter.py` |
| P3 | CMD-041 | lab_gate_release | FENCED | INTERNAL step: declared service function not found. | `backend/tests/test_s11_lab.py` |
| P3 | CMD-048 | lab_refer_out | FENCED | No lab_refer_out route exists; external referral/notification remains a registry fence. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-050 | lab_late_result | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-051 | lab_external_order | FENCED | lab_external_order is fenced by the S-11 slice; no external-order route is expected. The former wrong reference from LabItemCancelView was removed with the label fix. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-053 | prescription_activate | FENCED | INTERNAL step: declared service function not found. | `backend/tests/test_s12_dispensing.py` |
| P3 | CMD-055 | prescription_repeat | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-057 | dispense_gate_release | FENCED | INTERNAL step: declared service function not found. | `backend/tests/test_s12_dispensing.py` |
| P3 | CMD-059 | dispense_cancel | FENCED | dispense_cancel has service code but no route; S-12 scope fence leaves dispense cancellation out of the supplied slice. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-060 | prescription_partial_close | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-061 | dispense_reverse_return | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-070 | stock_correction | FENCED | INTERNAL step: declared service function not found. | `backend/tests/test_s09_inventory.py` |
| P3 | CMD-072 | invoice_source_line_add | FENCED | INTERNAL step: declared service function not found. | `backend/tests/test_s04_encounter.py` |
| P3 | CMD-078 | refund_request | FENCED | RefundFencedView and RefundRejectFencedView both declare CMD-078, but both refuse the command until §973 MFA authority; no state-changing route is active. | `backend/billing/views.py:598` |
| P3 | CMD-080 | receipt_issue | FENCED | INTERNAL step: declared service function not found. | `backend/tests/test_s05_billing.py` |
| P3 | CMD-084 | invoice_void | FENCED | INTERNAL step: declared service function not found. | `backend/tests/test_s01_reception.py` |
| P3 | CMD-085 | anc_enroll | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-086 | anc_contact_compose | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-098 | treatment_plan_save | FENCED | No view declares this CMD id; no HTTP route evidence. | `backend/tests/test_s04_encounter.py` |
| P3 | CMD-100 | referral_letter_create | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-102 | procedure_order | FENCED | No view declares this CMD id; no HTTP route evidence. | `backend/tests/test_s04_encounter.py` |
| P3 | CMD-103 | medical_certificate_issue | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-109 | lab_self_verification_policy_set | FENCED | No view declares this CMD id; no HTTP route evidence. | `backend/tests/test_s11_lab.py` |
| P3 | CMD-112 | invoice_discount_waiver | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-113 | dispense_substitute | FENCED | No view declares this CMD id; no HTTP route evidence. | `backend/tests/test_s12_dispensing.py` |
| P3 | CMD-114 | dispense_basket_update | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-116 | late_result_acknowledge | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-117 | expired_delivery_quarantine_intake | FENCED | No view declares this CMD id; no HTTP route evidence. | `backend/tests/test_s09_inventory.py` |
| P3 | CMD-118 | patient_problem_add | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-119 | patient_problem_resolve | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-120 | patient_obstetric_summary_update | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-121 | anc_history_update | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-122 | anc_risk_factors_record | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-123 | anc_obstetric_exam_record | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-125 | anc_dating_basis_update | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-126 | anc_contact_sequence_update | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-128 | repeat_vitals_request | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-129 | stale_visit_abandonment | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-130 | second_visit_override | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-132 | procedure_perform | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-133 | service_gate_override | FENCED | Registry/slice authority fence active; no implementation claim. | `IMPLEMENTATION_BLUEPRINT.md` |
| P3 | CMD-134 | lab_result_entry_reject | FENCED | No view declares this CMD id; no HTTP route evidence. | `backend/tests/test_s11_lab.py` |
| P3 | CMD-135 | arrival_enquiry_convert | FENCED | INTERNAL step: declared service function not found. | `backend/tests/test_s01_reception.py` |

## Full command table

| CMD | Operation | Slice(s) | Idempotency | Verdict | Severity | Evidence / discrepancy |
| --- | --- | --- | --- | --- | --- | --- |
| CMD-001 | visit_check_in | S-01,S-02,S-05,S-14 | YES | VERIFIED | P2 | Legacy scheduling.CheckInView also exposes a POST check-ins route without declaring CMD-001; the canonical CMD-001 view is correctly labelled. |
| CMD-002 | patient_register | S-01 | YES | VERIFIED | P2 | Legacy patients.PatientListCreateView also exposes a POST patient-create route without declaring CMD-002; the canonical reception view is correctly labelled. |
| CMD-003 | visit_payer_reprice | S-07 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s07_repricing.py`. |
| CMD-004 | emergency_visit_start | S-03 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-005 | emergency_setup_complete | S-03,S-05,S-14 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-006 | visit_cancel_error | S-01 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s01_reception.py`. |
| CMD-007 | visit_close_lwbs | S-01,S-02 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['INVOICE_STATE', 'QUEUE_LWBS']. |
| CMD-008 | visit_close | S-08 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s08_closure.py`. |
| CMD-009 | stale_visit_zero_record | S-02 | NO | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-010 | visit_referral_source_record | S-01 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s01_reception.py`. |
| CMD-011 | arrival_enquiry_record | S-01 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s01_reception.py`. |
| CMD-012 | visit_slip_reprint | S-14 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-013 | queue_call | S-02 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s02_queue.py`. |
| CMD-014 | queue_start_service | S-02 | NO | MISMATCH | P2 | queue_start_service is exposed by QueueClaimView (POST queue/<pk>/claim/) without an idempotency_operation label. |
| CMD-015 | queue_assign | S-02 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s02_queue.py`. |
| CMD-016 | queue_hold | S-02 | NO | PARTIAL | P2 | INTERNAL step: service function defined and called; parent CMD call site requires manual confirmation. |
| CMD-017 | queue_resume | S-02 | NO | PARTIAL | P2 | INTERNAL step: service function defined and called; parent CMD call site requires manual confirmation. |
| CMD-018 | queue_transfer | S-02 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s02_queue.py`. |
| CMD-019 | queue_complete | S-02 | NO | PARTIAL | P2 | INTERNAL step: service function defined and called; parent CMD call site requires manual confirmation. |
| CMD-020 | queue_no_response | S-02 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-021 | queue_requeue | S-02 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s02_queue.py`. |
| CMD-022 | queue_cancel | S-02 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s02_queue.py`. |
| CMD-023 | queue_takeover | S-02 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s02_queue.py`. |
| CMD-024 | queue_expire_sweep | S-02 | YES | PARTIAL | P2 | QueueExpireSweepView declares CMD-024, but S-16 fenced the slice and no operational cutoff/authorization evidence was found; route exists, authority not evidenced. |
| CMD-025 | triage_start | S-02,S-03 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s02_queue.py`. |
| CMD-026 | triage_save | S-03 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-027 | triage_complete | S-02,S-03 | YES | PARTIAL | P2 | TriageView and TriageRecordCompleteView both declare CMD-027; they are MIG-002 mode-gated compatibility/canonical routes, so no simultaneous collision was proven, but one namespace serves two routes. |
| CMD-028 | triage_amend | S-03 | YES | FENCED | P3 | No view declares this CMD id; no HTTP route evidence. |
| CMD-029 | repeat_vitals_record | S-03 | YES | FENCED | P3 | No view declares this CMD id; no HTTP route evidence. |
| CMD-030 | encounter_open | S-02,S-04 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['ENCOUNTER_RESUMED']. |
| CMD-031 | encounter_draft_save | S-04,S-13 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s04_encounter.py`. |
| CMD-032 | encounter_park_awaiting_results | S-02,S-04,S-13 | YES | FENCED | P3 | No view declares this CMD id; no HTTP route evidence. |
| CMD-033 | encounter_results_readiness | S-02,S-11,S-13 | NO | FENCED | P3 | INTERNAL step: declared service function not found. |
| CMD-034 | encounter_resume | S-02,S-04,S-13 | YES | PARTIAL | P2 | encounter_resume service exists but no dedicated route declares CMD-034; resume appears folded into the encounter open path under CMD-030. |
| CMD-035 | encounter_sign | S-04,S-14 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['CLINICAL_NOTE_SIGNED', 'QUEUE_COMPLETED']. |
| CMD-036 | encounter_sign_pending | S-02,S-04,S-13,S-14 | YES | FENCED | P3 | No view declares this CMD id; no HTTP route evidence. |
| CMD-037 | encounter_void_entered_error | S-04 | YES | FENCED | P3 | No view declares this CMD id; no HTTP route evidence. |
| CMD-038 | encounter_addendum | S-04,S-11 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-039 | encounter_transfer_takeover | S-04 | YES | PARTIAL | P2 | encounter_transfer_takeover service exists but no route or idempotency namespace declares CMD-039. |
| CMD-040 | lab_order | S-05,S-11,S-13,S-14 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['INVOICE_LINES_ADDED']. |
| CMD-041 | lab_gate_release | S-11,S-13 | NO | FENCED | P3 | INTERNAL step: declared service function not found. |
| CMD-042 | lab_collect | S-02,S-11 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['QUEUE_COMPLETED']. |
| CMD-043 | lab_reject_specimen | S-11 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s11_lab.py`. |
| CMD-044 | lab_result_save | S-11 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['LAB_RESULT_DRAFT_SAVED', 'LAB_RESULT_ENTERED']. |
| CMD-045 | lab_verify | S-11 | YES | PARTIAL | P2 | No dedicated lab_verify route declares CMD-045; verification is bundled with release in LabResultReleaseView, so the standalone command is not evidenced. |
| CMD-046 | lab_release | S-02,S-11,S-13,S-14 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['LAB_RESULT_VERIFIED']. |
| CMD-047 | lab_cancel | S-02,S-11 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-048 | lab_refer_out | S-11 | YES | FENCED | P3 | No lab_refer_out route exists; external referral/notification remains a registry fence. |
| CMD-049 | lab_result_correct | S-11 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['LAB_RESULT_CORRECTED']. |
| CMD-050 | lab_late_result | S-11,S-13 | NO | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-051 | lab_external_order | S-11 | YES | FENCED | P3 | lab_external_order is fenced by the S-11 slice; no external-order route is expected. The former wrong reference from LabItemCancelView was removed with the label fix. |
| CMD-052 | prescription_draft_save | S-12 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s12_dispensing.py`. |
| CMD-053 | prescription_activate | S-12,S-14 | NO | FENCED | P3 | INTERNAL step: declared service function not found. |
| CMD-054 | prescription_cancel | S-12 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s12_dispensing.py`. |
| CMD-055 | prescription_repeat | S-12 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-056 | provisional_dispense_create | S-05,S-09,S-12,S-14 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['DISPENSE_CREATED', 'INVOICE_LINES_ADDED']. |
| CMD-057 | dispense_gate_release | S-12 | NO | FENCED | P3 | INTERNAL step: declared service function not found. |
| CMD-058 | dispense_handover | S-09,S-12 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['PRESCRIPTION_CLAIM_RELEASED', 'PRESCRIPTION_OUTCOME']. |
| CMD-059 | dispense_cancel | S-12 | YES | FENCED | P3 | dispense_cancel has service code but no route; S-12 scope fence leaves dispense cancellation out of the supplied slice. |
| CMD-060 | prescription_partial_close | S-08 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-061 | dispense_reverse_return | S-09,S-12 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-062 | otc_sale | S-05,S-09,S-12,S-14 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['OTC_SALE_CONFIRMED', 'RECEIPT_ISSUED']. |
| CMD-063 | stock_receive | S-09,S-12 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-064 | stock_transfer | S-09,S-12 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-065 | stock_count_submit | S-10 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s10_counts.py`. |
| CMD-066 | stock_count_approve | S-09,S-10 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-067 | stock_adjust | S-09,S-10 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s09_inventory.py`. |
| CMD-068 | stock_quarantine | S-09,S-10 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-069 | stock_dispose | S-09,S-10 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-070 | stock_correction | S-09,S-10 | NO | FENCED | P3 | INTERNAL step: declared service function not found. |
| CMD-071 | invoice_issue | S-05,S-14 | YES | PARTIAL | P2 | D-13: canonical invoice_issue runs through visit check-in (issue_exact_source_lines); manual InvoiceListCreateView now uses the documented compat namespace and is allowlisted. |
| CMD-072 | invoice_source_line_add | S-04,S-05,S-09,S-11,S-12 | NO | FENCED | P3 | INTERNAL step: declared service function not found. |
| CMD-073 | invoice_manual_line_add | S-05 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['INVOICE_MANUAL_LINE_ADDED']. |
| CMD-074 | invoice_line_void | S-05,S-11 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s05_billing.py`. |
| CMD-075 | payment_confirm_allocate | S-05,S-11,S-12,S-13 | YES | PARTIAL | P2 | Owner-authorised compatibility namespace: legacy InvoicePaymentView uses 'legacy.invoice.payment.compat' and is allowlisted in the machine test; canonical InvoiceCanonicalPaymentView retains CMD-075. No route retired. |
| CMD-076 | payment_reverse | S-05,S-06 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['ALLOCATIONS_REVERSED', 'INVOICE_STATE']. |
| CMD-077 | credit_note_create | S-05,S-06,S-11,S-12,S-14 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['CREDIT_NOTE_CREATED', 'INVOICE_STATE']. |
| CMD-078 | refund_request | S-05,S-06,S-11,S-12 | YES | FENCED | P3 | RefundFencedView and RefundRejectFencedView both declare CMD-078, but both refuse the command until §973 MFA authority; no state-changing route is active. |
| CMD-079 | refund_process | S-05,S-06,S-11,S-12 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['REFUND_PROCESSED']. |
| CMD-080 | receipt_issue | S-05,S-14 | NO | FENCED | P3 | INTERNAL step: declared service function not found. |
| CMD-081 | receipt_reprint | S-05 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s05_billing.py`. |
| CMD-082 | cashier_shift_open | S-05 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['CASHIER_SHIFT_OPENED']. |
| CMD-083 | cashier_shift_close | S-05 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['CASHIER_SHIFT_CLOSED', 'CASHIER_SHIFT_FORCE_CLOSED']. |
| CMD-084 | invoice_void | S-01 | NO | FENCED | P3 | INTERNAL step: declared service function not found. |
| CMD-085 | anc_enroll | S-13 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-086 | anc_contact_compose | S-13 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-087 | appointment_no_show_check_in | S-01 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-088 | medication_product_create | S-09 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-089 | product_price_set | S-09 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-090 | medication_product_deactivate | S-09 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s09_inventory.py`. |
| CMD-091 | catalogue_import | S-09,S-12 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s09_inventory.py`. |
| CMD-092 | patient_allergy_record | S-03,S-04,S-13 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-093 | patient_allergy_status_set | S-03 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-094 | allergy_entered_error | S-03 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-095 | encounter_allergy_review | S-04 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s04_encounter.py`. |
| CMD-096 | diagnosis_save | S-04 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-098 | treatment_plan_save | S-04 | YES | FENCED | P3 | No view declares this CMD id; no HTTP route evidence. |
| CMD-099 | disposition_set | S-04 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-100 | referral_letter_create | S-04,S-14 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-101 | followup_record | S-04 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-102 | procedure_order | S-04,S-05,S-14 | YES | FENCED | P3 | No view declares this CMD id; no HTTP route evidence. |
| CMD-103 | medical_certificate_issue | S-04,S-14 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-104 | stock_location_configure | S-09 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-105 | supplier_upsert | S-09 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-106 | payment_method_configure | S-05 | YES | VERIFIED | P3 | Route/service/audit/test evidence indexed at `backend/billing/views.py:443,466`. |
| CMD-108 | lab_test_catalogue_configure | S-11,S-13 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-109 | lab_self_verification_policy_set | S-11 | YES | FENCED | P3 | No view declares this CMD id; no HTTP route evidence. |
| CMD-110 | product_instruction_template_set | S-12 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s12_dispensing.py`. |
| CMD-111 | inventory_threshold_set | S-09 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-112 | invoice_discount_waiver | S-05,S-06 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-113 | dispense_substitute | S-12 | YES | FENCED | P3 | No view declares this CMD id; no HTTP route evidence. |
| CMD-114 | dispense_basket_update | S-05,S-09,S-12 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-115 | dispense_item_not_dispensed | S-12 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['DISPENSE_ITEM_NOT_DISPENSED', 'INVOICE_LINE_VOIDED_OR_REDUCED']. |
| CMD-116 | late_result_acknowledge | S-11 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-117 | expired_delivery_quarantine_intake | S-09,S-10 | YES | FENCED | P3 | No view declares this CMD id; no HTTP route evidence. |
| CMD-118 | patient_problem_add | S-04 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-119 | patient_problem_resolve | S-04 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-120 | patient_obstetric_summary_update | S-04,S-13 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-121 | anc_history_update | S-13 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-122 | anc_risk_factors_record | S-13 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-123 | anc_obstetric_exam_record | S-13 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-124 | pharmacy_claim | S-12 | YES | PARTIAL | P2 | Declared audit codes not found in code: ['PRESCRIPTION_ACCESSED']. |
| CMD-125 | anc_dating_basis_update | S-13 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-126 | anc_contact_sequence_update | S-13 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-127 | queue_priority_change | S-02 | YES | VERIFIED | P2 | Route/service/audit/test evidence indexed at `backend/tests/test_s02_queue.py`. |
| CMD-128 | repeat_vitals_request | S-03,S-04 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-129 | stale_visit_abandonment | S-01 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-130 | second_visit_override | S-01 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-131 | stock_adjustment_approve | S-09,S-10 | YES | PARTIAL | P2 | Slice test file does not name this CMD or operation; test exercise not proven mechanically. |
| CMD-132 | procedure_perform | S-04,S-09,S-12 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-133 | service_gate_override | S-11,S-12 | YES | FENCED | P3 | Registry/slice authority fence active; no implementation claim. |
| CMD-134 | lab_result_entry_reject | S-11 | YES | FENCED | P3 | No view declares this CMD id; no HTTP route evidence. |
| CMD-135 | arrival_enquiry_convert | S-01 | NO | FENCED | P3 | INTERNAL step: declared service function not found. |
| CMD-136 | stock_ledger_reconcile | S-09 | YES | MISMATCH | P2 | Registry declares stock_ledger_reconcile as INTERNAL, but LedgerReconcileView is an HTTP POST route declaring CMD-136; route/declared-location conflict. |

## Honest limits

- Machine checks verify inventory, URL callback linkage, idempotency-label namespace and declared audit-code presence. They cannot prove a service function performs the named state transition or that a test asserts the outcome.
- Manual verdicts are based on declared facts, view/service source inspection and slice-test indexing; `VERIFIED` means the declared route, label, capability, audit codes and named slice test were located and found consistent, not that every error branch was executed.
- Many registry audit event names differ from implementation names (for example `DISPENSE_CREATED` vs `DISPENSE_PREPARED`). Those rows are `PARTIAL`, not `VERIFIED`.
- Capability declarations use role names in the registry and code strings in views; direct equality is rarely possible, so capability enforcement is checked qualitatively, not machine-asserted.
- FENCED commands are authority/scope fences, not failures. A few FENCED rows additionally carry a real duplicate-label note where both fenced views refuse state change.
- At the S-17 base d6a92b6 the laboratory/inventory label misroutes were findings only. This S-18 branch corrected CMD-042/043/044/046/047/064 and re-marked CMD-051 FENCED; no other product behavior, verb, route or unlabeled clinical view was changed.
- Plan-17 asks for a route with 'the same path', but the registry declares operation names (for example `POST lab_collect`), not URL paths. The audit uses the authoritative idempotency label -> view -> URL callback link; URL names differ by app (underscored reception names vs hyphenated clinical/pharmacy names), so operation-name-to-URL-name equality was not used.
- S-21 resolved three D-13 residuals: CMD-065 is now claimed only by StockCountSubmitView (open uses a documented compat namespace); InvoiceListCreateView uses a documented compat namespace because canonical invoice issue runs through visit check-in; PaymentMethodListView is the actual canonical CMD-106 path and now carries that registry label. CMD-014 and CMD-136 remain MISMATCH rows by owner decision (no code change).
- S-20 aligned the four registry verbs (CMD-044 PATCH, CMD-099/101/110 POST) with the same paths, payloads and idempotency namespaces. The three clinical/lab rows remain PARTIAL only because declared audit event names differ from code names; CMD-110 is VERIFIED.
- S-19 closed the clinical P1 class: ten active clinical views now carry their registry CMD id and `requires_idempotency=True`. EncounterDiagnosisDetailView/RemoveView remain unlabelled by design: registry CMD-097 is a retired tombstone and no active id was invented. P1 count is now zero; all remaining discrepancy rows are P2 owner-deferred findings (verbs, duplicate legacy routes, compatibility namespaces, audit-name/test-naming limits).
