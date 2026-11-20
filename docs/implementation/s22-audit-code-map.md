# S-22 audit-event conformance map

Base: `509c50d`. S-23 full-path review added; investigation only, no product change.

S-24 header note: CLINICAL_NOTE_AMENDED, ALLERGY_RECORDED, ALLERGY_STATUS_SET, ALLERGY_ENTERED_ERROR, ALLERGY_REVIEWED, DIAGNOSIS_SAVED, DISPOSITION_SET and FOLLOWUP_RECORDED were closed by attaching their declared codes to existing audit writers. This map remains the pre-fix evidence record; its entries are not reclassified post-hoc. Money and registry-superseded entries remain open findings.

Affected rows: 27. Classifications: MISSING_EMISSION 15, NAMING_MAPPING 20, REGISTRY_SUPERSEDED 2. Resolved from UNRESOLVED in S-23: 0.

MISSING_EMISSION rows are findings by risk class; none were fixed here.

| CMD | Operation | Declared code | Classification | Risk | Emitted code | Path reviewed | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CMD-007 | visit_close_lwbs | INVOICE_STATE | MISSING_EMISSION | other | CREATE | `backend/application/reception/views.py:479; backend/scheduling/services.py:618` | LWBS close path emits VISIT_CLOSED_LWBS and a refund-review fact, but no invoice-state event; all branches read. |
| CMD-007 | visit_close_lwbs | QUEUE_LWBS | NAMING_MAPPING | - | VISIT_CLOSED_LWBS | `backend/application/reception/views.py:479; backend/scheduling/services.py:618` | Declared queue outcome is emitted by the Visit close path under VISIT_CLOSED_LWBS. |
| CMD-030 | encounter_open | ENCOUNTER_RESUMED | REGISTRY_SUPERSEDED | - | UPDATE | `backend/clinical/views.py:534; backend/clinical/services.py:34` | Resume is folded into encounter open/reuse; no separate resume command exists in the implemented design. Owner §59 registry revision question. |
| CMD-035 | encounter_sign | CLINICAL_NOTE_SIGNED | NAMING_MAPPING | - | ENCOUNTER_SIGNED | `backend/clinical/views.py:937; backend/clinical/services.py:326` | The signed note event is emitted as ENCOUNTER_SIGNED by the sign owner service. |
| CMD-035 | encounter_sign | QUEUE_COMPLETED | NAMING_MAPPING | - | QUEUE_SERVICE_COMPLETED | `backend/clinical/views.py:486; backend/clinical/services.py:23` | Registry code maps to emitted QUEUE_SERVICE_COMPLETED. |
| CMD-038 | encounter_addendum | CLINICAL_NOTE_AMENDED | MISSING_EMISSION | final-clinical | UPDATE | `backend/clinical/views.py:995; backend/clinical/services.py:395` | Amend path writes the immutable note version and generic UPDATE audit action but no declared amendment event; all branches read. |
| CMD-040 | lab_order | INVOICE_LINES_ADDED | NAMING_MAPPING | - | INVOICE_LINE_ADDED | `backend/laboratory/views.py:33; backend/laboratory/services.py:33` | Registry code maps to emitted INVOICE_LINE_ADDED. |
| CMD-042 | lab_collect | QUEUE_COMPLETED | NAMING_MAPPING | - | QUEUE_SERVICE_COMPLETED | `backend/laboratory/views.py:33; backend/laboratory/services.py:33` | Registry code maps to emitted QUEUE_SERVICE_COMPLETED. |
| CMD-044 | lab_result_save | LAB_RESULT_DRAFT_SAVED | NAMING_MAPPING | - | LAB_RESULT_SAVED | `backend/laboratory/views.py:33; backend/laboratory/services.py:33` | Registry code maps to emitted LAB_RESULT_SAVED. |
| CMD-044 | lab_result_save | LAB_RESULT_ENTERED | NAMING_MAPPING | - | LAB_RESULT_SAVED | `backend/laboratory/views.py:33; backend/laboratory/services.py:33` | Registry code maps to emitted LAB_RESULT_SAVED. |
| CMD-046 | lab_release | LAB_RESULT_VERIFIED | NAMING_MAPPING | - | LAB_RESULT_SAVED | `backend/laboratory/views.py:33; backend/laboratory/services.py:33` | Registry code maps to emitted LAB_RESULT_SAVED. |
| CMD-049 | lab_result_correct | LAB_RESULT_CORRECTED | NAMING_MAPPING | - | LAB_RESULT_SAVED | `backend/laboratory/views.py:33; backend/laboratory/services.py:33` | Registry code maps to emitted LAB_RESULT_SAVED. |
| CMD-056 | provisional_dispense_create | DISPENSE_CREATED | NAMING_MAPPING | - | DISPENSE_PREPARED | `backend/pharmacy/views.py:177; backend/pharmacy/dispensing.py:404` | Provisional dispense creation emits DISPENSE_PREPARED at the prepare service. |
| CMD-056 | provisional_dispense_create | INVOICE_LINES_ADDED | NAMING_MAPPING | - | INVOICE_LINE_ADDED | `backend/pharmacy/views.py:177; backend/pharmacy/dispensing.py:35` | Registry code maps to emitted INVOICE_LINE_ADDED. |
| CMD-058 | dispense_handover | PRESCRIPTION_CLAIM_RELEASED | MISSING_EMISSION | dispensing | CREATE | `backend/pharmacy/views.py:197; backend/pharmacy/dispensing.py:564` | Handover confirms the dispense but no claim-release event is emitted; the active claim becomes implicit via dispense state. All branches read. |
| CMD-058 | dispense_handover | PRESCRIPTION_OUTCOME | MISSING_EMISSION | dispensing | CREATE | `backend/pharmacy/views.py:197; backend/pharmacy/dispensing.py:564` | Item state is versioned on confirmation, but no PRESCRIPTION_OUTCOME audit event is emitted. All branches read. |
| CMD-062 | otc_sale | OTC_SALE_CONFIRMED | NAMING_MAPPING | - | OTC_SALE_COMPLETED | `backend/pharmacy/views.py:308; backend/pharmacy/dispensing.py:35` | Registry code maps to emitted OTC_SALE_COMPLETED. |
| CMD-062 | otc_sale | RECEIPT_ISSUED | MISSING_EMISSION | money | CREATE | `backend/pharmacy/views.py:308; backend/pharmacy/dispensing.py:790` | OTC sale emits OTC_SALE_COMPLETED and a stock movement but no receipt event; no receipt is created on this path. All branches read. |
| CMD-073 | invoice_manual_line_add | INVOICE_MANUAL_LINE_ADDED | NAMING_MAPPING | - | INVOICE_LINE_ADDED | `backend/billing/views.py:71; backend/billing/services.py:34` | Registry code maps to emitted INVOICE_LINE_ADDED. |
| CMD-076 | payment_reverse | ALLOCATIONS_REVERSED | MISSING_EMISSION | money | CREATE | `backend/billing/views.py:355; backend/billing/services.py:1137` | Reversal emits PAYMENT_REVERSED only; allocation rows are reversed without a distinct audit event. All branches read. |
| CMD-076 | payment_reverse | INVOICE_STATE | MISSING_EMISSION | money | CREATE | `backend/billing/views.py:355; backend/billing/services.py:1137` | Payment reversal recomputes the invoice projection but emits no invoice-state event. All branches read. |
| CMD-077 | credit_note_create | CREDIT_NOTE_CREATED | NAMING_MAPPING | - | CREDIT_NOTE_VOIDED | `backend/billing/views.py:545; backend/billing/services.py:34` | Registry code maps to emitted CREDIT_NOTE_VOIDED. |
| CMD-077 | credit_note_create | INVOICE_STATE | MISSING_EMISSION | money | CREATE | `backend/billing/views.py:545; backend/billing/services.py:1366` | Credit-note creation emits CREDIT_NOTE_ISSUED and recomputes the invoice projection but emits no INVOICE_STATE event. All branches read. |
| CMD-079 | refund_process | REFUND_PROCESSED | REGISTRY_SUPERSEDED | - | CREATE | `backend/billing/views.py:616; backend/billing/services.py:1597` | CMD-079 route is RefundApproveFencedView and refuses until §973 MFA authority; no processing path exists to emit REFUND_PROCESSED. Owner §59 registry/fence question. |
| CMD-082 | cashier_shift_open | CASHIER_SHIFT_OPENED | NAMING_MAPPING | - | SHIFT_OPENED | `backend/billing/views.py:389; backend/billing/services.py:34` | Registry code maps to emitted SHIFT_OPENED. |
| CMD-083 | cashier_shift_close | CASHIER_SHIFT_CLOSED | NAMING_MAPPING | - | SHIFT_CLOSED | `backend/billing/views.py:389; backend/billing/services.py:34` | Registry code maps to emitted SHIFT_CLOSED. |
| CMD-083 | cashier_shift_close | CASHIER_SHIFT_FORCE_CLOSED | NAMING_MAPPING | - | SHIFT_CLOSED | `backend/billing/views.py:389; backend/billing/services.py:34` | Registry code maps to emitted SHIFT_CLOSED. |
| CMD-092 | patient_allergy_record | ALLERGY_RECORDED | MISSING_EMISSION | final-clinical | CREATE | `backend/clinical/views.py:374; backend/clinical/allergies.py:209` | add_allergy emits a generic CREATE action audit fact with no declared event code; all branches read. |
| CMD-093 | patient_allergy_status_set | ALLERGY_STATUS_SET | MISSING_EMISSION | final-clinical | CREATE | `backend/clinical/views.py:406; backend/clinical/allergies.py:280` | set_allergy_status emits a generic action audit fact with no declared event code; all branches read. |
| CMD-094 | allergy_entered_error | ALLERGY_ENTERED_ERROR | MISSING_EMISSION | final-clinical | CREATE | `backend/clinical/views.py:440; backend/clinical/allergies.py:352` | enter_allergy_in_error emits a generic action audit fact with no declared event code; all branches read. |
| CMD-095 | encounter_allergy_review | ALLERGY_REVIEWED | MISSING_EMISSION | final-clinical | CREATE | `backend/clinical/views.py:486; backend/clinical/allergies.py:453` | review_encounter_allergies emits a generic action audit fact with no declared event code; all branches read. |
| CMD-096 | diagnosis_save | DIAGNOSIS_SAVED | MISSING_EMISSION | final-clinical | CREATE | `backend/clinical/views.py:590; backend/clinical/diagnoses.py:191` | Diagnosis create/update/remove emit generic action audit facts only; no declared DIAGNOSIS_SAVED event on any branch. |
| CMD-099 | disposition_set | DISPOSITION_SET | MISSING_EMISSION | final-clinical | UPDATE | `backend/clinical/views.py:754; backend/clinical/dispositions.py:134` | set_disposition emits action='UPDATE' with no event_code on every branch; no declared event exists. |
| CMD-101 | followup_record | FOLLOWUP_RECORDED | MISSING_EMISSION | final-clinical | CREATE | `backend/clinical/views.py:793; backend/clinical/followups.py:158` | save_follow_up emits generic action audit facts only; no declared FOLLOWUP_RECORDED event on any branch. |
| CMD-115 | dispense_item_not_dispensed | DISPENSE_ITEM_NOT_DISPENSED | NAMING_MAPPING | - | PRESCRIPTION_ITEM_NOT_DISPENSED | `backend/pharmacy/views.py:177; backend/pharmacy/dispensing.py:35` | Registry code maps to emitted PRESCRIPTION_ITEM_NOT_DISPENSED. |
| CMD-115 | dispense_item_not_dispensed | INVOICE_LINE_VOIDED_OR_REDUCED | NAMING_MAPPING | - | INVOICE_VOIDED | `backend/pharmacy/views.py:177; backend/pharmacy/dispensing.py:35` | Registry code maps to emitted INVOICE_VOIDED. |
| CMD-124 | pharmacy_claim | PRESCRIPTION_ACCESSED | NAMING_MAPPING | - | PRESCRIPTION_CLAIMED | `backend/pharmacy/views.py:153; backend/pharmacy/dispensing.py:332` | Claim access is emitted as PRESCRIPTION_CLAIMED by the claim service. |

## Honest limits

- No emission, service, registry row, S-17 verdict or severity was changed.
- MISSING_EMISSION classifications claim the declared code is absent from every audited branch of the reviewed path; they are not fixes.
- Safety-critical MISSING_EMISSION rows (money, dispensing, final-clinical) require a separate authorized slice.
