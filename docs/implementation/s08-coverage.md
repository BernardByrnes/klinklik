# S-08 acceptance coverage — Visit closure and payment gates

Base: `027935ce436abcef471d6e069dc2131c67a7b67e` (`codex/integration`).
Candidate worktree: `K:/klinklik-s08-closure` (`codex/s-08-closure`).

## Per-file test counts (fresh for this candidate)

| File | Tests | Inputs |
| --- | --- | --- |
| `backend/tests/test_s08_closure.py` | 6 | blocked checklist + denial audit, successful/idempotent closure + post-close guard, unsigned/outstanding/emergency blockers, fenced paths, payment gate, permission |
| `backend/tests/test_s08_postgres.py` | 3 | concurrent close, close-vs-payment, payment-gate-vs-close as `clinicopus_app` |
| `frontend/tests/s08-closure.spec.ts` | 1 | blocked-closure checklist surface |
| `frontend/tests/clinic-slice.spec.ts` | 1 | full journey extended through payment → Visit closure |
| `backend/tests/test_s05_billing.py` | 9 | PRIOR money regression after gate/Visit guards |
| `backend/tests/test_s06_corrections.py` | 5 | PRIOR correction regression |
| `backend/tests/test_s07_repricing.py` | 2 | PRIOR repricing regression |

## Acceptance IDs

| AC | Status | Evidence / fenced decision |
| --- | --- | --- |
| BIL-014-AC01 | COVERED | Outstanding balance blocks closure with invoice number and exact amount: `test_s08_closure.py::test_s08_blocked_closure_returns_exact_blockers_and_audits_denial`, `test_s08_closure.py::test_s08_unsigned_encounter_outstanding_and_emergency_blockers`. |
| BIL-014-AC02 | BLOCKED | Debt/credit-sale closure (OD-P4) is fenced: `closure_path=DEBT/CREDIT` returns 422 `PREREQUISITE_MISSING` with `owner_decision=BP-BL-02/03/04/09`; no debt/credit-sale record or debtors report is invented. |
| BIL-014-AC03 | BLOCKED | Waiver closure depends on the unset BIL-009 policy; `closure_path=WAIVER` is refused with the owner decision named. |
| BIL-014-AC04 | PARTIAL | The enabled NORMAL close records `VISIT_CLOSED` with actor/reason; refused and fenced attempts record durable `AUTHORIZATION_DENIED`/`VISIT_CLOSE_DENIED` with blocker codes. Debt/waiver outcomes and the debtors report remain blocked with AC02/AC03. |
| REC-012-AC01 | COVERED | An OPEN Encounter blocks closure with encounter ID and clinician: `test_s08_closure.py::test_s08_unsigned_encounter_outstanding_and_emergency_blockers`. |
| REC-012-AC02 | BLOCKED | `signed_with_pending_orders`/live lab items are not built; `CLOSED(PENDING_RESULTS)` is not enabled. |
| REC-012-AC03 | BLOCKED | Partially-dispensed prescription closure awaits the pharmacy owner slice; no prescription state is fabricated. |
| REC-012-AC04 | COVERED | Outstanding balance blocks with amount; `EMERGENCY_FINANCIAL_SETUP_PENDING` blocks with the required setup action. |
| REC-012-AC05 | PARTIAL | Closed Visit is readable, leaves active queue/current work, and rejects post-closure invoice line changes and payments with 409 `VISIT_CLOSED` (`test_s08_successful_closure_is_state_bearing_idempotent_and_guarded`). Queue work is rejected by the existing active-Visit guards; not every possible owner-specific attachment path was exercised. |
| REC-012-AC06 | COVERED | Refusal returns the exact blocker set with owning action, leaves linked states unchanged, and writes a durable Rank-1 denial audit with actor/object/blocker codes and no PHI: `test_s08_blocked_closure_returns_exact_blockers_and_audits_denial`. No force-close capability was added. |
| REC-012-AC07 | BLOCKED | Late lab-result attachment (`LAB-023`) requires the laboratory owner service; no post-closure lab path exists. |
| REC-012-AC08 | COVERED | Concurrent close attempts produce one CLOSED outcome and one 409 version conflict: `test_s08_postgres.py::test_pg_s08_concurrent_close_has_one_winner`. |

## Commands and gates

- **CMD-008 `visit.close`:** `POST /api/v1/reception/visits/{id}/close/`, Visit-first lock → queue entries → encounters → invoices, exact checklist, idempotent success, state-bearing close with attribution.
- **CMD-075 ordinary gate release:** `confirm_payment` releases exactly `WAITING_PAYMENT` → `WAITING` after every Visit invoice settles (`PAYMENT_GATE_RELEASED`); partial payment leaves the gate held. Lock order is Visit → Invoice → QueueEntry to match closure and avoid cross-command deadlock.
- **CMD-006/007:** existing cancel-error and LWBS paths remain; this slice adds no new queue state.
- **CMD-041/057 (lab/pharmacy gate release) and CMD-133 override:** BLOCKED — laboratory and pharmacy owner services are not built; no lab/pharmacy gate, stock, custody or handover effect is enabled. No override route was invented for the ordinary gate.
- **Debt/waiver/OPS/OD-22:** explicit fenced blockers naming the owner decision; settlement-before-service policy remains unset.

## Denial audit

`write_denial_audit` now accepts safe extra source identifiers; the closure view persists `blocker_1..n` codes alongside the stable opaque reference. No patient name, clinical content, or tender detail is written.

## Verification results

| Lane | Result |
| --- | --- |
| Full merged SQLite | 387 passed, 75 skipped |
| PostgreSQL as `clinicopus_app`, both families (S-00/auth/S-01..S-08) | 72 passed, 0 skipped |
| Disabled-guard proofs (S-02/S-03/S-04) | 3 passed |
| Browser, all eleven specs | 20 passed |
| Static gates (check, migration drift, generated client, lint/typecheck/build, diff check) | pass |
| `check_rls --require-postgres` | enforced: true |

Red proof on the accepted integration tip `027935c`: the blocked and successful closure tests fail with `404` at `/api/v1/reception/visits/{id}/close/` before the S-08 command exists; green on this candidate.

## Lock-order correction

Payment confirmation now pre-locks the affected Visit before its Invoices, and repricing does the same, matching closure's Visit → Invoice → QueueEntry order. This prevents cross-command deadlocks in the PG close-vs-payment, gate-vs-close and reprice-vs-payment races; no observable behavior changed.
