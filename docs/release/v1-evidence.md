# KlinKlik v1 clinic-spine release evidence

**Status: local verification evidence only. Deployment is not authorized.**

Current evidence base: `51a3e8d` (accepted S-35 audit-repair tip; published `main` / `release/v1-clinic-spine` under the standing D-11 authority). This dossier closes the owner work order: repairs R1–R6, Features F1–F4 and the independent audit repair batch S-35. It is not a release approval, pilot approval, security certification, or legal/fiscal attestation.

Heavy lanes below are recorded as **evidence-at-SHA** unless explicitly stated as run in the slice named. The S-35 consolidated gates were executed at `51a3e8d`; S-34 and S-36 are documentation refreshes plus pinning tests, with no product code or browser lane re-run by those slices.

## 1. Work-order completion

Baseline before the repair batch: `899c1fc` (S-27 accepted tip, 462 passed / 92 skipped).

### Repair batch — accepted at `6ec1245` (review-29)

| Repair | Commit | Change and gate evidence |
| --- | --- | --- |
| R1 | `d1e5050` | Lab worklist uses `lab.result.entry` OR `lab.result.verify`, never stock read; stock-only/wrong-facility/foreign-tenant denied with no payload. Focused S-11 lane 6 passed; batch full suite 466/93. |
| R2 | `4216bed` | Blank/invalid count lines produce no submit request; explicit zero submitted verbatim; backend incomplete-count rejection fixed to a keyword `status_code`. Focused S-10 lane 7 passed; browser s10 2 passed; batch full suite 466/93. |
| R3 | `4878b8d` | Receipt identity, key and body captured once; uncertain retry resends the exact intent; one receipt and one `IN_GRN` movement. Browser s09 2 passed; batch full suite 466/93. |
| R4 | `d749686` | Confirm-time fulfilment derived from confirmed quantities plus the current handover; LOCK-01 and event policy preserved. Focused S-12 lane 22 passed; PG S-12 7 passed under `clinicopus_app`; batch full suite 466/93. |
| R5 | `6e5bdc0` | Destination reuse requires department AND effective work type; incompatible reuse is a safe conflict with source transition rollback. Focused S-02 lane 55 passed; PG S-02 13 passed; batch full suite 466/93. |
| R6 | `ed58eb2` | Pharmacy step keys and bodies preserved across uncertain outcomes; lost prepare response replays the same provisional identity. Focused S-12 lane 26 passed; browser s12 2 passed; batch full suite 466/93. |
| Artifact | `6ec1245` | Shifted S-22 audit evidence pointers refreshed; classifications and verdicts unchanged. Review-29 accepted. |

Gate evidence: focused repairs red→green through real entry points; batch full SQLite **466 passed / 93 skipped** (S-27 462/92 + 4 new backend tests; skips +1 from new PG-only tests). PostgreSQL proof total for the repair batch was **19 passed + 1 owner-DSN skip**; the skip is the disabled-guard proof requiring `S02_OWNER_DSN`.

### Feature 1 — Laboratory bench and clinician result review — `21225e8` (review-30)

| Commit | Change and gate evidence |
| --- | --- |
| `d1bdcce` | Bounded `/api/v1/lab/items/<id>/detail/` read added because the worklist and encounter payload could not support review; uses the lab entry/verify pair, scopes tenant/facility, audits `LAB_RESULTS_READ` without values. Release requires `expected_version`; stale review gets 412. |
| `143b8f4` | Worklist enriched with review metadata, stable urgent-first order and bounded pages; no draft values in the worklist. |
| `84ea560` | `/lab` bench: Enter results, Review and release, rejected reason/action, released section, units, labels, neutral flags, keyboard focus. |
| `3b5bdd8` | Clinician Investigations panel consumes `LabEncounterResultsView`; unreleased items show status only; authority-bound query keys and late-response discard. |
| `02de49f` | S-11 backend/PG/browser proofs including draft-absent-until-release, stale review, duplicate-version replay, rejection and NFR samples. |
| `21225e8` | Shifted lab audit evidence pointers refreshed. Review-30 accepted. |

Gate evidence: focused S-11 module 12 passed; PG S-11 3 passed under `clinicopus_app`; browser s11-lab.spec.ts 6 passed on a fresh seeded stack with MIG cutovers; full SQLite 472/95 at F1 tip. NFR with 200 items: API p95 110 ms, SPA render p95 146 ms on a declared synthetic 3G-equivalent profile; exact site profile remained owner-open.

### Feature 2 — Pharmacy preparation, pickup and resume — `771e2f5` (review-31)

| Commit | Change and gate evidence |
| --- | --- |
| `0c10a6b` | Queue projection exposes actor-scoped resumable provisional ID and claim holder; detail read returns server-derived review payload under `pharmacy.dispense`. |
| `e18e613` | `/pharmacy` one-step action replaced with claim → prepare → review → confirm; key stability, keyboard focus, final confirmation and non-actionable terminal rows. |
| `7e644d8` | Contention, claim owner, FEFO split, exact ledger/invoice source equality, stale/expired and unauthorized-detail tests. |
| `771e2f5` | Review fix: browser assertion added for non-actionable terminal rows. Review-31 accepted. |

Gate evidence: focused S-12 lane 26 passed; PG S-12 8 passed under `clinicopus_app`; browser s12-dispensing.spec.ts 2 passed on a fresh seeded stack; full SQLite 478/95 at F2 tip.

### Feature 3 — Inventory reconciliation workbench — `e6de464` (review-32)

| Commit | Change and gate evidence |
| --- | --- |
| `ea2dcab` | Multi-line receipt support confirmed; stock summary separates usable/expired/quarantined; batch/movement location/date filters; paginated blind-safe count list added because no count lookup existed. |
| `c8da1db` | `/inventory` workbench UI: stock drill-down, multi-line receipt, counting, independent count review and D-04 movements rendering. |
| `2e8d121` | S-09/S-10 PostgreSQL proofs for receipt, stock, count discovery and D-04. |
| `e6de464` | Review fix: `movements_during_count` gated on `inventory.approve`; non-approvers receive an empty list even with `?reveal=1`. Review-32 accepted. |

Gate evidence: focused S-10 8 passed; PG S-09/S-10 8 passed under `clinicopus_app`; browser s09 2 + s10 3 passed on fresh seeded stacks; full SQLite 482/97 at F3 tip.

### Feature 4 — Recoverable low-bandwidth clinic and stock workflows — `d5d930e` (review-33)

| Commit | Change and gate evidence |
| --- | --- |
| `99a3d77` | Shared connectivity/sync indicator and in-memory intent registry; last successful sync per view, accessible offline status, review-and-retry, authority clearing. |
| `d3a8777` | Exact-key per-intent replay capture for registration/check-in, receipt reprint, lab, pharmacy and inventory; no generic mutation retry wrapper; F2 `sessionStorage` removed in favour of server-backed resume identity. |
| `d5d930e` | S-16/S-33 browser recovery tests and throttle samples. Review-33 accepted; work order closed. |

Gate evidence: browser s16-release-drills.spec.ts 6 passed on a fresh seeded stack (original S-16 journey and print retained); full SQLite 482/97 unchanged; RLS gate PASS under `clinicopus_app` with 82 FORCE-RLS tables, `bypass_rls=false`; S-00 PostgreSQL proof environment note below.

### Independent audit repair batch (S-35) — accepted and published at `51a3e8d`

Audit source: independent audit `audit-q1-q5-r1-r6-f1-f4.md` (owner workspace; not a repository link). Published repair record: [S-35 handback](../implementation/s35-audit-repairs-handback.md). Each fix was supervisor-red-proven at its pre-fix commit before acceptance; the closing SHA series from `858f364` is `e84ed82`, `2295b74`, `b86a405`, `531dacf`, `f45c76f`, `56e3a59`, `a2c834a`, `0247b14`, `51a3e8d`. No S-35 commit has been amended or rewritten.

| Fix | SHA | One-line outcome and red proof |
| --- | --- | --- |
| R1 | `e84ed82` | Draft-headed lab result release red at HTTP 200 with `RELEASED`; now 409 `RESULT_NOT_SUBMITTED` from the locked result head, with draft heads routed to bench and `result_state` exposed. |
| R2 | `2295b74` | Handover after prescription cancellation red at HTTP 200 `CONFIRMED`; now refused with active claim, open signed prescription and current item-state gates under LOCK-01 before any ledger or charge write. |
| R3 | `b86a405` | Missing-Bearer protected read/logout red at HTTP 500; now DRF 401 in `TenantAPIView.initial` before `tenant_atomic`, with submission-time authority, single-flight settle and `IDEMPOTENCY_IN_PROGRESS` kept pending. |
| R4 | `531dacf` | Changed-form retry red by fingerprint conflict; patient/check-in/duplicate-resolution, inventory counts and billing payment/reprint now replay one immutable captured command, with count POST results split from follow-up GETs. |
| R5 | `f45c76f` | Terminal transfer replay red by returning a mismatched historical row; now 409 `DESTINATION_CONFLICT` after department/type recheck. Count evidence is bounded by posting time to `[created_at, submitted_at]`, with blind-draft reveal and approver-only movements stage-gated. |
| R6 | `56e3a59` | Lab worklist red with released rows crowding page one; now active/explicit history views with annotated rejection counts. Inventory UUID/date filters return safe 400s, empty location scopes hide batches, and same-authority refresh preserves facility without epoch bump. Rotation/sync coverage was added at `51a3e8d` with red epoch `2 → 3` at `f45c76f`. |

Consolidated verification at `51a3e8d`: full SQLite **494 passed, 103 skipped**; PG all six suites **45 passed, zero skips** under `clinicopus_app` with the owner-DSN guard proof executed; S-00 proof **PASS** using the deterministic `s00-backfill-clinic` seed SQL recorded in [`s35-audit-repairs-handback.md`](../implementation/s35-audit-repairs-handback.md); `check_rls --require-postgres` **PASS**, 82 tables FORCE RLS with owner ≠ app role. Affected browser evidence totals **34 tests** (s16 10, rotation 3, s10/s12/billing 12, s09/s11 9). Canonical production NFR at 400 kbps / 300 ms: cold **5,440–5,498 ms**, shell **156,428–156,433 B**, warm p95 **91–92 ms**, route JS **7,729 B** — all budgets pass. S-22/S-23 pointer signature stayed `NAMING_MAPPING 20 / MISSING_EMISSION 15 / REGISTRY_SUPERSEDED 2` with byte-identical notes and risk classes; full s11 file passed twice consecutively on one DB (7/7 then 7/7); static gates, generator check and migration checks were clean. No browser lane was re-run for this documentation refresh.

## 2. Current contract and verification state

At `d5d930e`, `docs/implementation/s17-cmd-audit.json` still reports:

| Verdict | Count |
| --- | --- |
| VERIFIED | 48 |
| PARTIAL | 32 |
| MISMATCH | 2 |
| FENCED | 52 |
| Total active CMDs | 134 (retired CMD-097/CMD-107 excluded) |

P1 **0**, P2 **34**. CMD-014 and CMD-136 remain the two MISMATCH rows and are owner questions Q1/Q2.

Current full backend suite at `51a3e8d`: **494 passed, 103 skipped**. Arithmetic from accepted runs: S-27 462/92 → repair batch +4 = 466/93; F1 +6 = 472/95; F2 +6 = 478/95; F3 +4 = 482/97; F4 browser-only = 482/97; S-35 +12 SQLite tests and +6 PG-only skips = 494/103. The earlier `d5d930e` full suite was **482 passed, 97 skipped** and remains evidence-at-SHA.

Current browser evidence by suite (all executed on fresh seeded stacks with MIG-002/003/004 cutovers where applicable):

| Suite | Tests |
| --- | --- |
| `s11-lab.spec.ts` | 6 passed |
| `s12-dispensing.spec.ts` | 2 passed |
| `s10-counts.spec.ts` | 3 passed |
| `s09-inventory.spec.ts` | 2 passed |
| `s16-release-drills.spec.ts` | 6 passed |

S-35 at `51a3e8d` extended the affected browser evidence to **34 tests**: `s16-release-drills.spec.ts` 10 passed, `s35-fix6-rotation.spec.ts` 3 passed, `s10-counts.spec.ts` + `s12-dispensing.spec.ts` + `billing-handoff-edges.spec.ts` 12 passed, and `s09-inventory.spec.ts` + `s11-lab.spec.ts` 9 passed.

`CLINICOPUS_E2E_PASSWORD` must be `ClinicopusDemo!2026` for legacy demo flows; `@clinicopus.local` uses `ClinicopusDemo123!` — never mix them. Browser lanes were chunked under sustained-load limits; `ERR_NO_BUFFER_SPACE` discipline remains recorded.

PostgreSQL gates: each backend-bearing slice above proved its module as `clinicopus_app` (non-BYPASSRLS). S-35 at `51a3e8d` ran all six PG suites with `S02_OWNER_DSN` configured: **45 passed, zero skips**, including the disabled-guard owner proof. `manage.py check_rls --require-postgres` reported **82 tables**, all FORCE RLS with tenant policy, owner ≠ app role and `bypass_rls=false`. Historical S-16 PG dump/restore and cutover drill results remain evidence-at-`3cab3c2`/`54291e4`. S-34 and S-36 did not re-run heavy lanes.

Historical S-16 journey/drill evidence-at-`3cab3c2`/`54291e4` (not re-run in this close-out): the consolidated 26-test fresh-stack journey passed; J-05 ANC and general Journey F remained FENCED; accessibility, throttled journey and print-media drills passed with a Chromium receipt PDF of 102,184 bytes; physical printer certification was not run. The earlier S-25 evidence-at-`ab1e259` full suite was 459 passed, 92 skipped; the exact refreshed close-out counts are pinned by `test_s26_evidence_dossier.py`.

## 3. Owner questions and settled decisions

[`s25-owner-questions.md`](../implementation/s25-owner-questions.md) remains the annex.

- Q1 — CMD-014 `queue_start_service` registry INTERNAL vs live HTTP route: **open**.
- Q2 — CMD-136 `stock_ledger_reconcile` registry INTERNAL vs HTTP POST route: **open**.
- Q3 — money emissions with no attachable event (CMD-062/076/077): **open**.
- Q4 — dispensing emissions with no attachable event (CMD-058): **open**.
- Q5 — confirm/reject the two REGISTRY_SUPERSEDED framings (CMD-030/079): **open**.
- Q6 — standing P2 weak-test-evidence class: **answered by D-14** in S-27; the owner may override, in which case affected rows revert to PARTIAL with the original gap named.

Settled decisions D-01, D-03/D-13, D-08, D-11, D-12, D-14 and accepted S-18/S-19 outcomes are listed in the annex so the owner is not re-asked. In particular, D-08 refund MFA has **no waiver**; refund issuance remains fenced.

## 4. Honest limits

- The F4 NFR result is a **recorded result, not a budget claim**: 450 ms latency / 50 KB/s down / 20 KB/s up, cold 47,439 ms and warm 220 ms (p95 47,439 ms over two samples). The real site profile remains owner-open (OD-R2 / AS-03).
- The S-33 throttled drill failed only under concurrent CPU load/cold compile and passed alone in ~50 s; browser lanes were chunked to respect the sustained-load limit. The canonical S-35 measurement is a production-build smoke result at 400 kbps / 300 ms, not a user-population or capacity claim.
- `check_s00_postgres.py` requires the deterministic S-00 proof organisation. In S-33/S-34 the disposable close-out database lacked it; the exact seed SQL was recorded in the S-35 handback and used successfully at `51a3e8d`, where the S-00 proof passed. The application-role password was re-applied per run in the disposable container (`clinicopus_app_test`); that is an environment detail, not a product regression.
- Historical `IdempotencyRecord` rows under pre-correction labels are not migrated (S-16/S-18/S-19 statements remain true; this lineage is synthetic).
- Refund issuance remains fenced per D-08 (§973 privileged MFA, no waiver). No refusal rule was waived or invented. Q1–Q5 remain open owner questions; Q6/D-14 and the D-08 no-waiver decision are unchanged by S-35.
- **Deployment is not authorized.**
- Audit-code map status is a pre-fix record; S-24 closures are additive header notes only.
- PC `IMPLEMENTED` in the S-16 inventory proves a model/migration exists, not every field/constraint/state rule. CMD `VERIFIED` in S-17 means declared route, label, audit and named slice test were located and consistent — not that every error branch was executed.
- No PHI appears in this dossier; all records cited are synthetic or registry/evidence metadata.

## 5. Reproduce the lightweight checks

```
cd backend
PYTHONPATH=.. python -m pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
cd ..
PYTHONPATH=. python tools/generate_api_client.py --check
git diff --check
```

S-34 ran these checks at the close-out tip. Browser and heavy PostgreSQL lanes are not re-run by this documentation refresh; use the evidence-at-SHA records above.
