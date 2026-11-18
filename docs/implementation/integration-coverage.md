# Integration candidate — clinic spine × billing chain

## Starting points

- Clinic spine: `73458c5` (`codex/s-04-encounter`)
- Billing chain: `9283357ce305b8eab456a979c1c86cbe7d4ef0dc` (`codex/s-07-repricing`)
- Merge base: `f5327e3cecfe608e0b8cdb37a84f38c60a51ffdb`
- Integration branch: `codex/integration`, worktree `K:/klinklik-integration`
- Merge commit: `3f2859b` (first-parent billing tip; second parent clinic tip)

## Conflict resolution

| File | Conflict | Resolution |
| --- | --- | --- |
| `.github/workflows/ci.yml` | Each chain added PostgreSQL/e2e lanes | Union: one `S02_OWNER_DSN` env, deselect the three guard proofs from the bulk lane, then run all S-00…S-07 PostgreSQL modules; browser lane lists all ten specs. |
| `backend/tests/test_session_roles_and_invoice_lookup.py` | Capability count 27 vs 29 | Merged registry has 35 definitions; assertion set to 35. |
| `frontend/src/app/(app)/consultations/page.tsx` | Billing “Open invoice”/existing Visit link vs clinic `patient_id` link | Kept billing's `billingVisitId` branch (opens the check-in invoice when present) and clinic's `selected.patient_id` fallback. `encounterVisitId` accepts the merged operational-row shape (`patient_id`/`visit_id`). |
| `frontend/src/generated/api-client.ts` | Both chains regenerated | Not hand-merged; regenerated from the merged OpenAPI, then `generate_api_client.py --check` passed. |

## Semantic near-misses (resolved without behavior redesign)

1. **Encounter opening queue type.** The billing handoff test opened an Encounter on the check-in/TRIAGE queue. S-04 intentionally restricts Encounter opening to `CONSULTATION`/`CLINICIAN`. The test fixture now creates a consultation destination in its own department and grants the actor scope there; production behavior is unchanged. Evidence: `backend/tests/test_visit_invoice_handoff.py::signed_encounter_for`.
2. **Payer-binding immutability.** S-01 asserted any `VisitPayerBinding` update fails. S-07 migration 0010 intentionally allows only `active: true → false` for supersession. The S-01 PG proof now asserts supersession succeeds while financial-field updates and reactivation still raise `55006`. Evidence: `backend/tests/test_s01_postgres.py::test_pg_price_contracts_fail_closed_and_keep_referenced_history`.
3. **Legacy clinic-slice triage journey.** S-03 requires explicit acuity, at least one observation, and a recorded allergy state before triage completion. The old journey now selects priority, records temperature, and sets NKA through the canonical endpoint. Evidence: `frontend/tests/clinic-slice.spec.ts`.
4. **Signed consultation state.** S-04 completes the consultation queue entry and clears selection on signature, so the old reload/resume and “Open invoice” link expectations no longer apply. The journey asserts the signed notice and navigates to the Visit invoice directly. Evidence: `frontend/tests/clinic-slice.spec.ts`.
5. **Shift close arithmetic.** The accepted S-06 correction excludes reversed cash once; the S-05 browser expectation was updated to expected 20,000 / variance -11,000 after reversing the 10,000 cash payment. Evidence: `frontend/tests/s05-cashier.spec.ts`.
6. **UI text collisions.** Merged queue rows render both a “called” meta string and a “Called” badge; the S-05 payment row renders `CASH · REVERSED`. Locators made exact/specific. Evidence: `clinic-slice.spec.ts`, `s05-cashier.spec.ts`.

## Combined proof results

| Lane | Command | Result |
| --- | --- | --- |
| SQLite union | `PYTHONPATH=.. python -m pytest -q` | 381 passed, 72 skipped |
| PostgreSQL app role | S-00/auth/S-01/S-02/S-03/S-04/S-05/S-06/S-07 with three guard proofs deselected | 69 passed, 0 skipped |
| Disabled guards | S-02 + S-03 + S-04 guard proofs | 3 passed |
| Browser | all ten specs | 19 passed |
| Static | check, migration drift, generated client, lint/typecheck/build, diff check | pass |

No new acceptance IDs are claimed. The merged candidate adds no product behavior.
