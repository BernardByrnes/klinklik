# S-06 acceptance coverage — financial corrections

Base: `fa2fdaaad6726dd0d0fcd73bdf7bf33a9ac5351e` (`codex/s-05-cashier`).
Candidate worktree: `K:/klinklik-s06-corrections` (`codex/s-06-corrections`).

Status vocabulary: **COVERED** = implemented and asserted; **PARTIAL** = the
enabled path is tested but the AC spans a fenced/unsupplied dependency;
**BLOCKED** = deliberately not enabled; **PRIOR** = accepted S-05 evidence.

## Per-file test counts (fresh for this candidate)

| File | Tests | Inputs |
| --- | --- | --- |
| `backend/tests/test_s06_corrections.py` | 5 | credit note, refundable credit, MFA/separation refund flow, fenced endpoint, Z-report |
| `backend/tests/test_s06_mig010.py` | 2 | MIG-010 happy path/rollback and projection-mismatch blocker |
| `backend/tests/test_s06_postgres.py` | 3 | app-role RLS/guards, concurrent credits, refundable bound |
| `frontend/tests/s06-corrections.spec.ts` | 1 | credit note issue, disabled refund action, Z-report print surface |
| `backend/tests/test_s05_billing.py` | 9 | PRIOR S-05 payment/reversal/receipt regression |
| `backend/tests/test_s05_postgres.py` | 5 | PRIOR S-05 money/concurrency proofs |
| `frontend/tests/s05-cashier.spec.ts` | 1 | PRIOR cashier journey |

## BIL-009 — discounts and waivers

| AC | Status | Evidence / remaining decision |
| --- | --- | --- |
| BIL-009-AC01 | BLOCKED | Discount reason list and approval authority are unset. No discount write path is enabled; owner policy decision required. |
| BIL-009-AC02 | BLOCKED | No discount document/print path exists; the invoice `discount` compatibility field is not rewritten here. |
| BIL-009-AC03 | BLOCKED | Full waiver record requires the unsupplied waiver policy; credit notes are not re-labelled as waivers. |
| BIL-009-AC04 | BLOCKED | Configurable approval threshold is unset. |
| BIL-009-AC05 | BLOCKED | Discounts report REP-008 is not supplied. |

## BIL-010 — credit notes and refundable credit

| AC | Status | Evidence / remaining decision |
| --- | --- | --- |
| BIL-010-AC01 | PARTIAL | CMD-077 issues an immutable invoice-attributed CreditNote with mandatory reason, actor/time, own number, bounded by remaining creditable value and serialized by the invoice row lock: `test_s06_corrections.py::test_s06_credit_note_reduces_due_without_rewriting_history`, `test_s06_postgres.py::test_pg_s06_concurrent_credits_cannot_exceed_creditable_value`. Line-level source attribution is not yet modelled (invoice-level only). |
| BIL-010-AC02 | PARTIAL | Projection recomputes gross/applied/credit/balance without editing lines or payments; the credit is stored separately: `test_s06_corrections.py::test_s06_credit_note_on_paid_invoice_creates_bounded_refundable_credit`. Printable credit-note document is not implemented. |
| BIL-010-AC03 | PARTIAL | Bounded `Refund` record references payment, invoice, credit note and open shift; refundable credit is derived from effective allocations/credits and cannot be exceeded: `test_s06_corrections.py::test_s06_refund_flow_requires_mfa_and_separation`, `test_s06_postgres.py::test_pg_s06_refund_request_is_bounded_by_refundable_credit`. Issuance endpoint is disabled pending §973 MFA and the original Payment stays CONFIRMED. |

## PAY-008 — reversal and refund evidence

| AC | Status | Evidence / remaining decision |
| --- | --- | --- |
| PAY-008-AC01 | PRIOR | Payment is append-only under the `klin_klink_payment_evidence_immutable` trigger; `test_s05_postgres.py::test_pg_s05_force_rls_receipt_guards_and_money_constraints`. |
| PAY-008-AC02 | PARTIAL | Whole-payment reversal reverses allocations via `Payment.status`, recomputes every invoice and never voids: `test_s05_billing.py::test_s05_reversal_preserves_evidence_and_unrelated_invoice`, `test_s05_postgres.py::test_pg_s05_reversal_restores_every_allocated_invoice`. Structured reason codes and lab/pharmacy re-gating are not supplied; the reason is hash-only (owner-visible S-05 follow-up). |
| PAY-008-AC03 | PARTIAL | Original payment, allocations and receipt are retained and reversal is audited. Printable reversal note and “original receipt marked reversed on reprint” are not implemented; reprint currently refuses a reversed receipt. |
| PAY-008-AC04 | PARTIAL | Refund request records refunding cashier/shift, cannot exceed refundable credit, leaves the Payment CONFIRMED and unrelated invoices unchanged: `test_s06_corrections.py::test_s06_refund_flow_requires_mfa_and_separation`. Issuance remains pending/disabled; no provider or general-purpose patient credit is invented. |
| PAY-008-AC05 | BLOCKED | Reversal after shift close is not attached to a current open shift or original-shift reference; the shift-report linkage is not implemented. |
| PAY-008-AC06 | PARTIAL | `PAYMENT_REVERSED` and `REFUND_APPROVED/REJECTED` audit events exist, but no severity classification or daily reversals report is supplied. |

## Supplementary implemented evidence (no separate AC row)

- **QRY-009 / CMD-083:** `shift_z_report` and `GET /billing/shifts/{id}/z-report/` expose committed tender totals, payment/reversal/refund counts, discounts, opening/expected/declared cash, variance and reason; asserted in `test_s06_corrections.py::test_s06_z_report_uses_committed_shift_evidence` and the browser spec.
- **MIG-010:** `core/mig010.py` + `manage.py mig010` implement inventory/verify/constrain/cutover/rollback with two stable scans, PC-050 reconciliation evidence and synthetic seeded exceptions; asserted in `test_s06_mig010.py` (2 tests).

## Fenced owner decisions

1. Refund issuance remains disabled pending canonical §973 privileged MFA; service and approval flow are complete but no issuance endpoint is enabled. Tests call the service directly with explicit `mfa_verified=True`.
2. OD-P4 credit sales (`CORPORATE_CREDIT`/`STAFF_CREDIT`) and the debtors list remain fenced on the owner's pilot-demand decision.
3. Fiscal numbering, VAT and printed-invoice compliance remain unsupplied. Credit-note numbers are internal `CN-YYYYMMDD-NNNNNN`; Z-report states it is not a fiscal receipt.
4. S-07 repricing, SaleReturn restock/quarantine, lab/pharmacy gate re-evaluation and external refund providers remain outside the slice.
