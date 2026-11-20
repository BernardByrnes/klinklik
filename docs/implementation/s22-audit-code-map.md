# S-22 audit-event conformance map

Base: `93c1af7`. Investigation only; no product change.

Affected rows: 27. Classifications: NAMING_MAPPING 16, UNRESOLVED 21.

| CMD | Operation | Declared code | Classification | Emitted code | Evidence | Note |
| --- | --- | --- | --- | --- | --- | --- |
| CMD-007 | visit_close_lwbs | INVOICE_STATE | UNRESOLVED | CREATE | `backend/scheduling/services.py:311` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-007 | visit_close_lwbs | QUEUE_LWBS | UNRESOLVED | CREATE | `backend/scheduling/services.py:311` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-030 | encounter_open | ENCOUNTER_RESUMED | UNRESOLVED | UPDATE | `backend/clinical/services.py:75` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-035 | encounter_sign | CLINICAL_NOTE_SIGNED | UNRESOLVED | UPDATE | `backend/clinical/services.py:75` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-035 | encounter_sign | QUEUE_COMPLETED | NAMING_MAPPING | QUEUE_SERVICE_COMPLETED | `backend/scheduling/queue.py:741` | Registry code maps to emitted QUEUE_SERVICE_COMPLETED. |
| CMD-038 | encounter_addendum | CLINICAL_NOTE_AMENDED | UNRESOLVED | UPDATE | `backend/clinical/services.py:75` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-040 | lab_order | INVOICE_LINES_ADDED | NAMING_MAPPING | INVOICE_LINE_ADDED | `backend/billing/services.py:1299` | Registry code maps to emitted INVOICE_LINE_ADDED. |
| CMD-042 | lab_collect | QUEUE_COMPLETED | NAMING_MAPPING | QUEUE_SERVICE_COMPLETED | `backend/scheduling/queue.py:741` | Registry code maps to emitted QUEUE_SERVICE_COMPLETED. |
| CMD-044 | lab_result_save | LAB_RESULT_DRAFT_SAVED | NAMING_MAPPING | LAB_RESULT_SAVED | `backend/laboratory/services.py:578` | Registry code maps to emitted LAB_RESULT_SAVED. |
| CMD-044 | lab_result_save | LAB_RESULT_ENTERED | NAMING_MAPPING | LAB_RESULT_SAVED | `backend/laboratory/services.py:578` | Registry code maps to emitted LAB_RESULT_SAVED. |
| CMD-046 | lab_release | LAB_RESULT_VERIFIED | NAMING_MAPPING | LAB_RESULT_SAVED | `backend/laboratory/services.py:578` | Registry code maps to emitted LAB_RESULT_SAVED. |
| CMD-049 | lab_result_correct | LAB_RESULT_CORRECTED | NAMING_MAPPING | LAB_RESULT_SAVED | `backend/laboratory/services.py:578` | Registry code maps to emitted LAB_RESULT_SAVED. |
| CMD-056 | provisional_dispense_create | DISPENSE_CREATED | UNRESOLVED | CREATE | `backend/pharmacy/dispensing.py:229` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-056 | provisional_dispense_create | INVOICE_LINES_ADDED | NAMING_MAPPING | INVOICE_LINE_ADDED | `backend/billing/services.py:1299` | Registry code maps to emitted INVOICE_LINE_ADDED. |
| CMD-058 | dispense_handover | PRESCRIPTION_CLAIM_RELEASED | UNRESOLVED | CREATE | `backend/pharmacy/dispensing.py:229` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-058 | dispense_handover | PRESCRIPTION_OUTCOME | UNRESOLVED | CREATE | `backend/pharmacy/dispensing.py:229` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-062 | otc_sale | OTC_SALE_CONFIRMED | NAMING_MAPPING | OTC_SALE_COMPLETED | `backend/pharmacy/dispensing.py:916` | Registry code maps to emitted OTC_SALE_COMPLETED. |
| CMD-062 | otc_sale | RECEIPT_ISSUED | UNRESOLVED | CREATE | `backend/pharmacy/dispensing.py:229` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-073 | invoice_manual_line_add | INVOICE_MANUAL_LINE_ADDED | NAMING_MAPPING | INVOICE_LINE_ADDED | `backend/billing/services.py:1299` | Registry code maps to emitted INVOICE_LINE_ADDED. |
| CMD-076 | payment_reverse | ALLOCATIONS_REVERSED | UNRESOLVED | CREATE | `backend/billing/services.py:374` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-076 | payment_reverse | INVOICE_STATE | UNRESOLVED | CREATE | `backend/billing/services.py:374` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-077 | credit_note_create | CREDIT_NOTE_CREATED | NAMING_MAPPING | CREDIT_NOTE_VOIDED | `backend/billing/services.py:1493` | Registry code maps to emitted CREDIT_NOTE_VOIDED. |
| CMD-077 | credit_note_create | INVOICE_STATE | UNRESOLVED | CREATE | `backend/billing/services.py:374` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-079 | refund_process | REFUND_PROCESSED | UNRESOLVED | CREATE | `backend/billing/services.py:374` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-082 | cashier_shift_open | CASHIER_SHIFT_OPENED | NAMING_MAPPING | SHIFT_OPENED | `backend/billing/services.py:685` | Registry code maps to emitted SHIFT_OPENED. |
| CMD-083 | cashier_shift_close | CASHIER_SHIFT_CLOSED | NAMING_MAPPING | SHIFT_CLOSED | `backend/billing/services.py:769` | Registry code maps to emitted SHIFT_CLOSED. |
| CMD-083 | cashier_shift_close | CASHIER_SHIFT_FORCE_CLOSED | NAMING_MAPPING | SHIFT_CLOSED | `backend/billing/services.py:769` | Registry code maps to emitted SHIFT_CLOSED. |
| CMD-092 | patient_allergy_record | ALLERGY_RECORDED | UNRESOLVED | CREATE | `backend/clinical/allergies.py:266` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-093 | patient_allergy_status_set | ALLERGY_STATUS_SET | UNRESOLVED | CREATE | `backend/clinical/allergies.py:266` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-094 | allergy_entered_error | ALLERGY_ENTERED_ERROR | UNRESOLVED | CREATE | `backend/clinical/allergies.py:266` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-095 | encounter_allergy_review | ALLERGY_REVIEWED | UNRESOLVED | CREATE | `backend/clinical/allergies.py:266` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-096 | diagnosis_save | DIAGNOSIS_SAVED | UNRESOLVED | CREATE | `backend/clinical/diagnoses.py:210` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-099 | disposition_set | DISPOSITION_SET | UNRESOLVED | UPDATE | `backend/clinical/dispositions.py:167` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-101 | followup_record | FOLLOWUP_RECORDED | UNRESOLVED | CREATE | `backend/clinical/followups.py:226` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |
| CMD-115 | dispense_item_not_dispensed | DISPENSE_ITEM_NOT_DISPENSED | NAMING_MAPPING | PRESCRIPTION_ITEM_NOT_DISPENSED | `backend/pharmacy/dispensing.py:784` | Registry code maps to emitted PRESCRIPTION_ITEM_NOT_DISPENSED. |
| CMD-115 | dispense_item_not_dispensed | INVOICE_LINE_VOIDED_OR_REDUCED | NAMING_MAPPING | INVOICE_VOIDED | `backend/scheduling/queue.py:1709` | Registry code maps to emitted INVOICE_VOIDED. |
| CMD-124 | pharmacy_claim | PRESCRIPTION_ACCESSED | UNRESOLVED | CREATE | `backend/pharmacy/dispensing.py:229` | Only a generic action audit event was found in the implementing path; no domain-specific emission confirmed. |

## Honest limits

- NAMING_MAPPING is based on strong token similarity plus a registered audit-writer call site; it is not an owner-approved rename.
- UNRESOLVED rows have only a generic action audit event in the implementing path; a full path review is still required before calling them missing.
- MISSING_EMISSION rows name a risk class; none are fixed in this slice.
- No audit emission, service, registry row, or S-17 verdict was changed.
