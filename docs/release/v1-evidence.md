# KlinKlik v1 clinic-spine release evidence

**Status: local verification evidence only. Deployment is not authorized.**

Base: `db19523` (published `main` / `release/v1-clinic-spine`).
Candidate tip: `3cab3c2` on `codex/s16-release-evidence`.
Evidence assembled: 2026-11-19 (Africa/Kampala), in the local verification worktree `codex/s16-release-evidence`.
This dossier records what was run and what was not run. It is not a release approval, a pilot approval, a security certification, or a legal/fiscal attestation.

## Verification environment

| Component | Version / value |
| --- | --- |
| OS | Windows 11 (10.0.26200), Git Bash |
| Python | 3.14.6 |
| Django | 5.2.15 |
| Database (proof) | PostgreSQL 16.4 in a disposable `postgres:16.4` container, port 55432 |
| Database (journeys) | SQLite, fresh temporary e2e database |
| Application role | `clinicopus_app`, `NOSUPERUSER NOBYPASSRLS` |
| Node | v26.3.0 |
| Playwright | 1.62.1, Desktop Chrome, one worker |
| Git base | `db19523` |

## Contract verification

Machine artifact: [`docs/implementation/s16-contract-verification.json`](../implementation/s16-contract-verification.json).
Human report: [`docs/implementation/s16-contract-verification.md`](../implementation/s16-contract-verification.md).
Machine assertions: `backend/tests/test_s16_release_evidence.py` — **5 passed**.

| Family | Active contracts | Verified status counts |
| --- | --- | --- |
| PC | 80 (`PC-001..PC-081` minus retired `PC-061`) | 62 `IMPLEMENTED`, 7 `PARTIAL`, 11 `FENCED` |
| CMD | 134 (`CMD-001..CMD-136` minus retired `CMD-097`/`CMD-107`) | 104 `EVIDENCE LINKED`, 30 `FENCED` |
| MIG | 11 (`MIG-001..MIG-011`) | 11 `IMPLEMENTED` |
| ADR | 14 (`ADR-C-01..ADR-C-14`) | 14 `SETTLED` |

`EVIDENCE LINKED` means the contract is mapped to the named slice test evidence; it is not a claim that every branch in that command is complete. The fenced and partial lists below carry the honest limits.

**This table is an evidence index, not a branch-by-branch contract audit.** PC `IMPLEMENTED` only proves a model/migration file exists; it does not prove the PC row's fields, constraints or state rules. CMD `EVIDENCE LINKED` only proves the traceability table points at a slice with a test file; it does not prove that command's route, service branch, permission, audit and concurrency evidence. The machine test checks inventories and pointer existence, not semantic sufficiency. A full CMD-by-CMD audit remains open.

## Journey drills (J-01..J-05)

Consolidated fresh-database run: **26 passed in 3.2 minutes** across the sixteen canonical specs, with seed_demo plus MIG-002/003/004 cutovers completed first.

| Journey | Evidence | Result |
| --- | --- | --- |
| J-01 / J-02 clinical variants: registration → triage → consultation → billing → closure | `s01-reception`, `s02-queue`, `s03-triage`, `s04-encounter`, `clinic-slice`, `billing-handoff-edges`, `s05-cashier`, `s06-corrections`, `s07-repricing`, `s08-closure` | PASS |
| J-03 pharmacy: prescribe → dispense → charge | `s12-dispensing` plus S-12 backend evidence | PASS |
| J-04 laboratory: order → collect → result → release | `s11-lab` plus S-11 backend evidence | PASS |
| J-05 ANC | Not run — S-13 remains blocked by owner authority (OD-C/OD-17, BP-BL-05) | FENCED |
| General appointment lifecycle / Journey F | Not run — out of scope; only CMD-087 supplied fragment exists | FENCED |

Supporting specs also passed in the same run: `s01-accessibility`, `s09-inventory`, `s10-counts`, and `s16-release-drills`.

Note: an earlier run against a reused e2e database hit the 120-second Playwright timeout in `clinic-slice`; the fresh-database run passed in 25 seconds standalone and within the 26-pass consolidated run. This is recorded as an environment/data-volume observation, not a product fix.

## Operational drills

| Drill | Exact command / method | Fresh result |
| --- | --- | --- |
| Runtime S-00 proof gate | `python tools/check_s00_postgres.py` as `clinicopus_app` against `test_clinicopus` | **PASS** — policy, scope, migration, backfill, constraint and trigger proofs |
| RLS gate at tip | `python manage.py check_rls --require-postgres` as `clinicopus_app` | **PASS** — `enforced=True`, role `clinicopus_app`, `bypass_rls=False`, **82 tables**, all with RLS + FORCE + tenant policy |
| Backup | `pg_dump -Fc` of the migrated database | 712,144-byte custom dump |
| Restore | `pg_restore` into a fresh `restored_clinicopus` database | exit 0, **12 seconds** |
| Restored runtime gate | `check_s00_postgres.py` against the restored database | **PASS** |
| Restored RLS gate | `check_rls --require-postgres` against the restored database | **PASS** — 82 tables, all FORCE RLS, same app role |
| Migration reversal/reapply | `migrate scheduling 0007`, then `migrate scheduling 0008` | reverse OK, forward OK |
| Full backend regression | `PYTHONPATH=.. python -m pytest -q` | **439 passed, 92 skipped** in 230.31s |
| Static gates | `manage.py check`, `makemigrations --check`, frontend `typecheck`, `lint`, production `build` | clean |

## Accessibility, low bandwidth and print

- **Accessibility:** `s01-accessibility.spec.ts` passed inside the consolidated 26-pass run.
- **Low bandwidth:** `s16-release-drills.spec.ts` throttled Chromium with 450 ms latency, 50 KB/s down and 20 KB/s up (`cellular3g`); reception login, patient registration and check-in completed. **PASS**.
- **Receipt print:** the S-16 drill posted a synthetic payment in the real billing UI, invoked the audited receipt reprint path, switched to print media and rendered the receipt through Chromium `page.pdf`. Result: **102,184 bytes**, SHA-256 `6e36c6a1cfaf3145552a6a12aa6a7779165be2178b3b1f47f2f59e36801990ca`. **PASS**.
- **Not run:** physical printer certification, printer-driver testing, and fiscal/legal print validation. These remain owner/authority gates.

## Fenced items and owner decisions

| Fence | Contracts / behavior | Owner decision named |
| --- | --- | --- |
| S-13 ANC / J-05 | PC-046, PC-071..PC-075; CMD-085, CMD-086, CMD-120..CMD-123, CMD-125, CMD-126 | S-13 owner authority; OD-C1/C2/C5, OD-17, BP-BL-05 |
| S-14 reporting / documents | PC-057; CMD-012, CMD-100, CMD-103; real-print certification | S-14 owner authority; REP/AUD, OD-L4/L5, BP-BL-04 |
| S-12 residual pharmacy branches | CMD-055 repeat, CMD-060 partial close, CMD-061 reverse/return, CMD-114 basket update, payment-before-handover gate | S-12 scope fence; DSP-008/OD-PH8, BP-BL-08 |
| S-05/S-06 residual finance branches | CMD-112 discount/waiver | Owner authority; BIL-009/OD-L6 |
| General Appointment lifecycle / Journey F | Everything except CMD-087 | S-15 scope fence; BP-BL-05 |
| Deployment, provider integration, pilot, external notification, retention periods | All release/ops behavior | Owner/pilot/provider gates; OD-L1..L8, BP-BL-09, RG-01..RG-15 not fully exercised |

The full per-contract fenced list is in the contract report: 11 PC contracts, 30 CMD contracts, plus J-05 and the general APT lifecycle.

## Findings routed to the supervisor (not fixed in this verification slice)

1. **S-12 CMD idempotency labels are mismatched with the registry.** `backend/pharmacy/views.py`: claim uses `CMD-055` (registry CMD-124 pharmacy_claim), prepare uses `CMD-057` (registry CMD-056 provisional_dispense_create), prescription cancel uses `CMD-059` (registry CMD-054 prescription_cancel; CMD-059 is dispense_cancel), not-dispensed uses `CMD-060` (registry CMD-115 dispense_item_not_dispensed; CMD-060 is prescription_partial_close), OTC uses `CMD-113` (registry CMD-062 otc_sale; CMD-113 is dispense_substitute). Behavior tests pass, but replay namespaces and audit/idempotency operation identities are mislabeled. No product code was changed here.
2. **PC partial representations:** PC-017, PC-022, PC-025, PC-037, PC-040, PC-077 and PC-080 are implemented through legacy/renamed or inline models (for example `PrescriptionItem`, `StockBatch`, `InvoiceItem`, `PaymentReceipt`, inline substitution and analyte values). The registry field names are not a one-to-one schema match.
3. **Command coverage is evidence-linked, not branch-complete.** 30 CMD contracts are fenced and are listed above; the dossier does not claim their execution.
4. **Reused-database journey timeout:** the earlier `clinic-slice` 120-second timeout on an accumulated e2e database is recorded above; the fresh-database run passed. I did not root-cause the earlier timeout: the server log showed a transient 503 on the Visit context, and the same context returned 200 later. Treating it as data-volume/environment is a hypothesis, not proven.
5. **Plan-16 scope gaps found while executing it:** (a) "all sixteen specs" is the CI canonical set, but this repo contains 26 spec files — the 10 legacy `phase-1*`/`role-handoff` specs were not run and are not in CI; (b) J-05 is fenced, so only J-01/J-02 (clinical), J-03 and J-04 have fresh journey evidence; (c) only MIG-001..004 were explicitly cut over for the browser lane; MIG-005..011 were not re-run as e2e cutovers; (d) the migration drill reversed only scheduling 0008, not all 11 MIG reversals; (e) browser print rendering is not physical-printer certification; (f) the plan asks to "verify" 80/134 contracts but does not define a branch-level acceptance test, which is why this dossier labels CMDs as evidence-linked rather than verified.
6. **Conflicting S-12 idempotency evidence:** because the S-12 route labels are mismatched (finding 1), the contract table's evidence-linking for CMD-054/056/062/113/115/124 is weaker than a command-by-command reader would assume. Their behavior tests pass, but the CMD ID namespace must be corrected and the table rechecked.

## Explicit non-authorizations

- No deployment, infrastructure provisioning, DNS, secret rotation, production database access or provider configuration was performed.
- No push, merge, pull request, release tag or publication was performed by the implementor.
- No production, real-patient, PHI, fiscal, insurance or external-provider data was used; all names and records are synthetic.
- The repository publication at `db19523` was performed by the supervisor, not this slice.

## Reproduce

```
# backend
cd backend
PYTHONPATH=.. python -m pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run

# disposable PostgreSQL runtime gates
DB_ENGINE=postgresql DB_NAME=test_clinicopus DB_HOST=127.0.0.1 DB_PORT=55432 \
  DB_USER=clinicopus_app DB_PASSWORD=clinicopus_app_test \
  PYTHONPATH=. python tools/check_s00_postgres.py
DB_ENGINE=postgresql DB_NAME=test_clinicopus DB_HOST=127.0.0.1 DB_PORT=55432 \
  DB_USER=clinicopus_app DB_PASSWORD=clinicopus_app_test \
  python manage.py check_rls --require-postgres

# consolidated journeys (fresh e2e DB with seed_demo + MIG-002/003/004 cutovers)
cd frontend
DB_NAME=<fresh-e2e.sqlite3> npx playwright test \
  tests/s01-reception.spec.ts tests/s01-accessibility.spec.ts \
  tests/s02-queue.spec.ts tests/s03-triage.spec.ts tests/s04-encounter.spec.ts \
  tests/clinic-slice.spec.ts tests/billing-handoff-edges.spec.ts \
  tests/s05-cashier.spec.ts tests/s06-corrections.spec.ts tests/s07-repricing.spec.ts \
  tests/s08-closure.spec.ts tests/s09-inventory.spec.ts tests/s10-counts.spec.ts \
  tests/s11-lab.spec.ts tests/s12-dispensing.spec.ts tests/s16-release-drills.spec.ts
```
