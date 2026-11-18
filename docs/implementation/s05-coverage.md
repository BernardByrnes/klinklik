# S-05 acceptance coverage — billing, payments and receipts

Base: `69104dac1be443912c72d8550613a9b3d1c0bcee` (`codex/clinic-visit-invoice`).
Candidate worktree: `K:/klinklik-s05-cashier` (`codex/s-05-cashier`).

Status vocabulary: **COVERED** = implemented and asserted in the named test;
**PARTIAL** = the enabled path is tested but the AC spans a fenced dependency;
**BLOCKED** = the AC depends on authority or an owner integration that is not
supplied and is deliberately not enabled; **PRIOR** = accepted evidence from
the S-01/billing base, re-run here.

## Per-file test counts (fresh for this candidate)

| File | Tests | Inputs |
| --- | --- | --- |
| `backend/tests/test_s05_billing.py` | 9 | S-05 SQLite service/API/permission/shift/method/line/receipt cases |
| `backend/tests/test_s05_mig005.py` | 2 | MIG-005..009 inventory/verify/constrain/cutover/rollback and blocker case |
| `backend/tests/test_s05_postgres.py` | 4 | app-role RLS/guards, competing final payment, cross-invoice reversal, exact numbering + blind close |
| `frontend/tests/s05-cashier.spec.ts` | 1 | shift open → canonical payment → exact receipt → reprint → reversal → blind close |
| `backend/tests/test_visit_invoice_handoff.py` | 8 | PRIOR billing/check-in handoff regression |
| `backend/tests/test_vertical_slice.py` | 5 | PRIOR end-to-end vertical slice |
| `backend/tests/test_session_roles_and_invoice_lookup.py` | 11 | PRIOR capability and invoice lookup |
| `backend/tests/test_s01_postgres.py` | 16 | PRIOR S-01 PostgreSQL proofs (payment handoff case re-run here) |
| `frontend/tests/clinic-slice.spec.ts` | 1 | PRIOR routed vertical slice |
| `frontend/tests/billing-handoff-edges.spec.ts` | 5 | PRIOR payment/receipt edge journeys |

## Invoice lifecycle

| AC | Status | Evidence / remaining decision |
| --- | --- | --- |
| BIL-001-AC01 | PARTIAL | Ordinary OPD check-in consultation line and single Visit invoice: `test_visit_invoice_handoff.py::test_visit_invoice_read_returns_the_check_in_invoice`, `test_s05_billing.py::test_s05_shift_bound_payment_has_exact_receipt_and_safe_replay`. Lab/procedure/dispense charge sources are blocked on S-03/S-07 integration. |
| BIL-001-AC02 | PRIOR | Check-in transaction aborts without a charge: `test_s01_postgres.py::test_pg_competing_checkins_have_one_visit_invoice_and_consultation_line`. |
| BIL-001-AC03 | BLOCKED | `PAY_BEFORE` source gates are unsupplied; no gated service state is enabled. Owner decision required with the owning service slice. |
| BIL-001-AC04 | BLOCKED | Unbilled-event exception report REP-007 and guaranteed reconciliation are not supplied. |
| BIL-001-AC05 | PRIOR | Source type/id, price snapshot, service and actor on the consultation line: `test_s01_postgres.py::test_pg_competing_checkins_have_one_visit_invoice_and_consultation_line`. |
| BIL-002-AC01 | COVERED | `uniq_active_visit_invoice` plus reuse in `issue_exact_source_lines`; `test_s05_billing.py::test_s05_shift_bound_payment_has_exact_receipt_and_safe_replay` asserts one Visit invoice. |
| BIL-002-AC02 | PARTIAL | A standalone Invoice can be created by `create_invoice`; no retail-sale story or product path is enabled. |
| BIL-002-AC03 | PARTIAL | Invoice row locks serialize concurrent charges; check-in concurrency is proven in `test_s01_postgres.py::test_pg_competing_checkins_have_one_visit_invoice_and_consultation_line`. Concurrent line-add is not separately exercised. |
| BIL-002-AC04 | COVERED | `recompute_invoice_projection` keeps gross = non-voided lines and applied/outstanding separate; asserted in `test_s05_billing.py::test_s05_manual_line_and_void_protect_paid_invoices`. |
| BIL-003-AC01 | COVERED | Catalogue lines take the active catalogue price inside `add_invoice_line`; `test_s05_billing.py::test_s05_catalogue_line_reopens_a_paid_invoice_with_audit`. |
| BIL-003-AC02 | COVERED | Free-text line requires description, positive amount, reason and `billing.manual_line`; `test_s05_billing.py::test_s05_manual_line_and_void_protect_paid_invoices` proves the evidence refusal. |
| BIL-003-AC03 | COVERED | `INVOICE_LINE_ADDED` audit includes actor, before/after totals and manual flag; asserted in `test_s05_billing.py::test_s05_catalogue_line_reopens_a_paid_invoice_with_audit`. |
| BIL-004-AC01 | COVERED | Void keeps the line with `VOIDED`, reason, actor/time and excludes it from totals: `test_s05_billing.py::test_s05_manual_line_and_void_protect_paid_invoices`. |
| BIL-004-AC02 | COVERED | Paid/partially paid invoice refuses line void with `PAID_LINE_VOID_REFUSED`: same test. |
| BIL-004-AC03 | BLOCKED | Lab/medicine gate re-evaluation needs the laboratory/pharmacy owner integration. |
| BIL-004-AC04 | COVERED | `INVOICE_LINE_VOIDED` audit carries before/after totals (`void_invoice_line`). |
| BIL-005-AC01 | PRIOR | Check-in issues `ISSUED` with a facility invoice number; `test_visit_invoice_handoff.py::test_visit_invoice_read_returns_the_check_in_invoice`. |
| BIL-005-AC02 | COVERED | Manual/catalogue lines append while unpaid and recompute/audit; `test_s05_billing.py::test_s05_manual_line_and_void_protect_paid_invoices`, `test_s05_billing.py::test_s05_catalogue_line_reopens_a_paid_invoice_with_audit`. |
| BIL-005-AC03 | COVERED | A paid invoice moves to `PARTIALLY_PAID` with the new balance when a line is added: `test_s05_billing.py::test_s05_catalogue_line_reopens_a_paid_invoice_with_audit`. |
| BIL-006-AC01 | PARTIAL | Cashier list exposes patient, invoice number, gross, applied, balance and services. Invoice age and patient location (QUE-010) are not supplied. |
| BIL-006-AC02 | PARTIAL | The list refreshes on mutations; the 15-second facility-wide event propagation is not measured without queue/lab/pharmacy events. |
| BIL-006-AC03 | BLOCKED | Gated lab/medicine blocking markers need those owner paths. |
| BIL-006-AC04 | COVERED | Invoice search by number/patient name/number: `test_session_roles_and_invoice_lookup.py::test_invoice_list_filters_by_status` plus search filter in `InvoiceListCreateView.get`. |
| BIL-007-AC01 | COVERED | Detail returns lines, source fields, gross/applied/balance and payments with allocations/receipt identity: `test_s05_billing.py::test_s05_shift_bound_payment_has_exact_receipt_and_safe_replay`. |
| BIL-007-AC02 | PARTIAL | Reception sees totals and service names; no independent role-specific redaction test beyond the capability gate. |
| BIL-007-AC03 | COVERED | Voided line returns reason and `voided_by`: `test_s05_billing.py::test_s05_manual_line_and_void_protect_paid_invoices`. |
| BIL-008-AC01 | PRIOR | `patient_outstanding_balance` aggregates current-facility unpaid invoices; consumed by reception reads. |
| BIL-008-AC02 | PARTIAL | Explicit multi-invoice allocation is proven; automatic oldest-first allocation is not enabled. |
| BIL-008-AC03 | BLOCKED | Settlement-before-service facility policy is unset; no blocking override is invented. |
| BIL-009-AC01 | BLOCKED | Discount reason list and approval authority are not supplied; no new discount path is enabled. |
| BIL-009-AC02 | BLOCKED | No discount record/print path is enabled in S-05. |
| BIL-009-AC03 | BLOCKED | Waiver record path requires the unsupplied discount/waiver owner decision. |
| BIL-009-AC04 | BLOCKED | Discount approval threshold policy is unset. |
| BIL-009-AC05 | BLOCKED | Discounts report REP-008 is not supplied. |
| BIL-010-AC01 | BLOCKED | CreditNote is S-06; not implemented here. |
| BIL-010-AC02 | BLOCKED | CreditNote retention/print is S-06. |
| BIL-010-AC03 | BLOCKED | Refund and partial credit are S-06; S-05 implements only whole-payment reversal. |
| BIL-011-AC01 | PARTIAL | Receipt print is implemented; grouped invoice print is not. |
| BIL-011-AC02 | BLOCKED | Medicine line strength/quantity print needs pharmacy lines. |
| BIL-011-AC03 | BLOCKED | Laboratory test grouping needs laboratory lines. |
| BIL-012-AC01 | PARTIAL | Receipt print includes facility header, receipt/invoice numbers, patient, totals, payments and balance. Invoice print is not implemented. |
| BIL-012-AC02 | COVERED | Reprint is audited and idempotent: `test_s05_billing.py::test_s05_reprint_is_idempotent_and_audited`, `frontend/tests/s05-cashier.spec.ts`. |
| BIL-013-AC01 | PRIOR | `uniq_invoice_source_line_version` and one consultation line per source: `test_visit_invoice_handoff.py`. |
| BIL-013-AC02 | COVERED | Same idempotency key replays the first payment and receipt: `test_s05_billing.py::test_s05_shift_bound_payment_has_exact_receipt_and_safe_replay`. |
| BIL-013-AC03 | PARTIAL | Void keeps the original source identity and manual replacements use a new UUID identity; a dispense-basket replacement is not enabled. |
| BIL-013-AC04 | COVERED | Each manual/catalogue line gets a distinct `source_line_identity` (`add_invoice_line`). |
| BIL-013-AC05 | PARTIAL | Database uniqueness prevents duplicate charging; a duplicate-attempt monitoring log/report is not supplied. |
| BIL-014-AC01 | PRIOR | Erroneous check-in with payment data is refused: `test_pg_visit_invoice_handoff_refuses_duplicate_and_pays_the_original`. |
| BIL-014-AC02 | BLOCKED | Debt/credit-sale closure is S-06; REP-008 debtors report is unsupplied. |
| BIL-014-AC03 | BLOCKED | Waiver path depends on BIL-009 authority. |
| BIL-014-AC04 | BLOCKED | Closure-path audit depends on the unsupplied closure transactions. |
| PAY-001-AC01 | COVERED | CASH, MOBILE_MONEY_MANUAL with required reference, up to three facility manual methods: `test_s05_billing.py::test_s05_payment_method_configuration_and_manual_reference`. |
| PAY-001-AC02 | COVERED | Deactivation refuses new payments and leaves historical payments intact: same test. |
| PAY-001-AC03 | COVERED | No provider verification is claimed; the method is labelled manual and the reference is operator evidence only (`resolve_payment_method`, method test). |

## Fenced owner decisions

- S-06 credit/refund (BIL-010, BIL-014-AC02) — not started.
- S-07 repricing — not started; paid history is never rewritten.
- Unsupplied service gates and queue/lab/pharmacy integrations (BIL-001-AC03/04,
  BIL-004-AC03, BIL-006-AC03, BIL-013-AC05) — endpoints remain disabled/absent.
- External payment providers and verification (PAY-001-AC03) — manual evidence only.
- Fiscal/retention rules and printed invoice templates (BIL-011/BIL-012) — not supplied.
- Discount/waiver policy and approval thresholds (BIL-009) — policy unset; disabled.
- Shift variance alerting and force-close (CMD-083) — supervisor threshold/permission
  not supplied; ordinary blind close only.
- Retail standalone sale (BIL-002-AC02) — no supplied retail story.
