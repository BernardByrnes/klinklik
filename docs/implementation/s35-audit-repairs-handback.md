# S-35 — Independent audit repair batch handback

Base: `858f364`. Branch/worktree: `codex/s35-audit-repairs` at `K:/klinklik-s35-audit-repairs`. Local only: no push, merge, PR or deployment.

## Fix SHAs

| Fix | SHA | Subject |
| --- | --- | --- |
| Fix 1 | `e84ed82` | `fix(S-35-R1): block release of draft lab versions` |
| Fix 2 | `2295b74` | `fix(S-35-R2): recheck pharmacy handover eligibility` |
| Fix 3 | `b86a405` | `fix(S-35-R3): settle pending commands and reject missing bearer` |
| Fix 4 | `531dacf` | `fix(S-35-R4): capture immutable commands and reconcile targets` |
| Fix 5 | `f45c76f` | `fix(S-35-R5): guard transfer replay and bound count evidence` |
| Fix 6 | `56e3a59` | `fix(S-35-R6): bound reads, validate filters, and measure NFR` |
| Close-out | this commit | pointer refresh, S-34 dossier correction, this handback |

## Findings closed (red → green)

- **R1 (P1):** a submitted item with a draft head could be released with HTTP 200. `release_result` now locks and validates the current head, refuses draft/released versions with `409 RESULT_NOT_SUBMITTED`, and worklists route draft heads back to bench. Detail/serializer expose `result_state`; the review panel hides release and offers refresh. Item state, immutable versions, author separation, downstream readiness and audit remain unchanged on refusal.
- **R2 (P1):** a provisional dispense could be handed over after prescription cancellation with HTTP 200. Confirmation now locks Prescription → items → Claim → Dispense → Invoice → balances, requires the actor's active claim and open signed prescription, refuses cancelled/not-dispensed items and over-quantity handovers, and performs all eligibility checks before ledger/charge writes. Cancellation and item refusal take parent locks; review/queue projections match. FEFO, expiry, controlled, custody, payment and stock guards are preserved. No Q4 events were added.
- **R3:** unauthenticated `GET /api/v1/patients/` and `POST /api/v1/auth/logout/` returned 500; a second transport failure dropped the pending retry. `TenantAPIView.initial` now rejects missing auth with DRF 401 before `tenant_atomic`. Intents capture authority at submission, dedupe by command/target, await `mutateAsync`, keep `IDEMPOTENCY_IN_PROGRESS` and uncertain outcomes, and reject stale authority. Retry controls are mobile/keyboard accessible and disabled offline/in-flight; tab visibility no longer clears authorized intents.
- **R4:** retries rebuilt bodies from live form/selection state. Patient registration/check-in (including duplicate resolution), inventory count open/submit/approve, and billing payment/reprint now capture one immutable request at the deliberate submit boundary. Count POST results are separated from follow-up GETs; a failed read refreshes only the read. Pharmacy already used the snapshot pattern and was verified unchanged.
- **R5:** canonical terminal transfer replay returned a historical row selected by `work_identity` alone. The return path now rechecks department/queue type and raises `409 DESTINATION_CONFLICT`. Count evidence is bounded by authoritative `created_at` between count creation and submission; blind draft reveal and approval-only movements are stage-gated; explicit reveal denial survives a non-blind facility.
- **R6:** historical released rows crowded the first lab worklist page; malformed inventory filters could reach the ORM; token rotation reset facility/epoch. The worklist has active vs explicit history views with annotated rejection counts and a UI toggle. Inventory UUID/date filters validate at the API boundary and empty location scopes hide batches. Same-authority refresh preserves an authorized facility without an epoch bump, drops stale refresh responses, tracks the final response, and connectivity state resets on authority change.

## Verification

- Focused SQLite lane (`s02`, `s09`, `s10`, `s11`, `s12`, `session_roles`): **135 passed**.
- Focused PostgreSQL lane under `clinicopus_app` (`clinicopus_app_test`, non-BYPASS): **44 passed, 1 skipped** (owner-DSN guard only).
- Owner-DSN guard proof (`S02_OWNER_DSN` configured): **3 passed**.
- Full SQLite suite at the final code tip: **494 passed, 103 skipped in 263.43s**. Before the trailing pointer refresh it was 486 passed / 2 failed (and an intermediate run was 492 passed / 2 failed) from shifted S-22 evidence line numbers; classification signature stayed exactly `NAMING_MAPPING 20 / MISSING_EMISSION 15 / REGISTRY_SUPERSEDED 2`, and all per-entry notes/risk classes were byte-identical.
- S-00 PostgreSQL proof and `check_rls --require-postgres`: **PASS** after seeding the deterministic proof organisation in `test_clinicopus`; `check_s00_migration_state.py`: **PASS**.
- Browser lanes: s16 10 passed, s10 5 passed, s11 7 passed, s12 2 passed, billing-handoff-edges 5 passed, s09 2 passed. Fix 1 and the 200-item NFR test were proven in both orders using a temporary reversed-order spec that was removed afterwards. The 200-item fixture now has an `afterEach` teardown that cancels the synthetic lab items with fresh credentials; the full s11 file was run **twice consecutively on the same database** (`s35-s11-twice.sqlite3`) with **7 passed / 1.5m** then **7 passed / 1.7m**, proving later lab tests no longer starve on reused DB state.
- Engineering gates: `manage.py check` clean; `makemigrations --check --dry-run` no changes; generated API client regenerated and clean; `tools/validate_s00.py` PASS; `tools/check_s00_migration_contract.py` PASS; lint/typecheck/build PASS; `git diff --check` PASS.
- Canonical production NFR at `400 kbps / 300 ms RTT` (`frontend/scripts/measure-s35-nfr.mjs`): cold **5,440 ms**, warm p95 **92 ms**; cold shell transfer **156,428 bytes** (Script 145,570 + Stylesheet 8,057 + Document 2,801), warm route JS p95 **7,729 bytes**. All inside 8 s / 2.5 s and 180 KB / 120 KB. All-bytes cold transfer was 208,129 bytes including 48,732 font bytes and 2,969 fetch bytes; recorded separately, not included in the shell budget.

## Decisions and architecture

- Kept the modular Django/DRF monolith and Next.js client; business logic stayed in service modules and views authorize/orchestrate.
- Used existing state machines, append-only movements, idempotency and FORCE RLS; no new migrations, no BYPASSRLS role, no stock quantity edits or expiry override.
- No PHI in labels, logs or artifacts; retry labels use operation/target only.
- Q1–Q5 remain owner-reserved and unanswered. Refund MFA remains fenced. Deployment, push, merge and PR remain unauthorized.
- This is a local Markdown handback; it is not release, pilot, physical printer or regulator approval.

## Remaining risks / open items

- Owner decisions Q1–Q5 (CMD-014/136/058/062/076/077 framing) remain open by authority.
- S-13 ANC, S-14 reporting/print and deployment remain outside this batch.
- The PG proof role password had to be re-applied in the disposable container (`clinicopus_app_test`); this is an environment detail, not a product regression.
- The canonical NFR measurement uses encoded transfer bytes by CDP resource type; font bytes are reported but excluded from the shell budget as documented above.
