# KlinKlik Repository Review Handoff

## 1. Project Identity

Product: KlinKlik.

Legacy technical identifiers intentionally retained: the repository directory is `clinicopus`; the Django settings/package is `backend/clinicopus`; the frontend package is `clinicopus-web`; and the local SQLite file is `backend/db.sqlite3`. These are technical compatibility names, not a product rename decision.

Canonical functional specification: `KlinKlik-V1-Canonical-Backlog.md`.

Canonical product and architecture blueprint: `K:\new\clinicopus2.md`.

## 2. Current Stack

Frontend: Next.js 15.5.23, React 19, TypeScript, Tailwind CSS 4, and TanStack Query. The client uses in-memory access tokens with an httpOnly rotating refresh-cookie session.

Backend: Django 5.2.17 with Django REST Framework 3.18.0, organised as a modular monolith. The dependency definition is `backend/requirements.txt`.

Database: SQLite for local development and tests (`backend/db.sqlite3`); PostgreSQL is the deployment database and carries the RLS design.

Other infrastructure: Docker Compose provides optional local PostgreSQL and Redis support. No external services, payments, messages, webhooks, or production infrastructure were used for Phase 1A-V.

## 3. Repository Structure

- `backend/`: Django project and domain apps, including `accounts`, `audit`, `billing`, `clinical`, `core`, `patients`, `scheduling`, and `tenancy`, plus the current app seams for inventory, laboratory, maternity, pharmacy, reporting, and platform administration.
- `frontend/`: Next.js client, shared shell/components, route screens, generated-build output, and Playwright tests.
- `docs/`: architecture notes, ADRs, product references, implementation notes, and this handoff.
- `docker/`: local infrastructure support.
- `.github/`: CI configuration.
- `artifacts/`: repository-local review/build artifacts.

## 4. Current Working Product Journey

The implemented and verified clinic vertical slice is:

Patient registration → Check-in → Queue → Claim → Triage → Consultation → Service charge → Invoice → Payment → Receipt.

The authenticated Phase 1A-V E2E run completed this journey with synthetic development data. The consultation foundation exposes Summary, History, Examination, Investigations, Diagnosis, Treatment, and Notes. Only the existing consultation note/sign flow is functional in this foundation; the other sections are explicit empty/foundation states. Investigations contains no laboratory workflow.

Signed consultation notes are immutable in the UI and backend correction is through the existing amendment path. No patient data from outside the local development database was used.

## 5. Current Roles

Implemented role templates are `OWNER_ADMIN`, `RECEPTION_CASHIER`, `NURSE_TRIAGE`, and `CLINICIAN`. The development seed maps these to administrator, reception/cashier, triage nurse, and clinician workflows. Server-side capability checks remain authoritative.

## 6. Current Routes

Frontend routes:

- `/login`
- `/overview`
- `/patients`
- `/queue`
- `/triage`
- `/consultations`
- `/billing`

Relevant API families:

- `/api/v1/health/`
- `/api/v1/auth/`
- `/api/v1/tenancy/`
- `/api/v1/patients/`
- `/api/v1/clinic/`
- `/api/v1/billing/`
- `/api/schema/`

## 7. Current Backend Domains

- Tenancy and facility context: `tenancy`, `core`.
- Authentication, roles, capabilities, sessions, and credentials: `accounts`.
- Patient identity and demographics: `patients`.
- Queue/check-in: `scheduling` and related clinic services.
- Clinical workflow: `clinical` models and services for `Encounter`, `ClinicalNote`, `ClinicalNoteVersion`, `TriageAssessment`, and `VitalsObservation`.
- Billing: `billing` services and models for service catalogue, prices, invoices, invoice items, payments, and receipts.
- Audit: append-only audit services and records in `audit`.

Business workflows are implemented in service modules; views authorize/orchestrate; serializers validate input shape; models persist data and local invariants.

## 8. Visual System

The current canonical KlinKlik styles live in `frontend/src/app/globals.css`. Shared controls and visual patterns live in `frontend/src/components/ui.tsx`; the authenticated shell, sidebar, facility switcher, and topbar live in `frontend/src/components/shell/AppShell.tsx`.

The current system uses the repository theme tokens for the purple primary, canvas/surface colors, muted text, borders, accent states, focus rings, rounded cards, badges, and button hierarchy. Typography, spacing, cards, buttons, forms, tables/lists, and tabs are composed from these shared utilities and components.

**Existing KlinKlik CSS/UI is canonical. New phases extend this visual system; they do not redesign it.**

## 9. Completed Build Phases

### Phase 1A — Doctor Consultation Workspace Foundation

Status: VERIFIED.

Objective: provide the doctor consultation workspace foundation without implementing later clinical modules or redesigning the existing shell.

Files changed: `frontend/src/app/(app)/consultations/page.tsx` and `frontend/tests/clinic-slice.spec.ts`.

Functionality: seven reachable semantic tabs; visible active state; mouse and keyboard navigation with ArrowLeft, ArrowRight, Home, and End; context strip; existing Start Encounter action; existing Assessment/Plan note field; section-switch draft retention; immutable sign confirmation; explicit empty states for foundation sections.

Tests: authenticated browser verification and the relevant clinic vertical-slice E2E test passed. Frontend typecheck, lint, and production build passed. Backend checks and tests passed.

Known limitations: History, Examination, Diagnosis, Treatment, and laboratory-related work remain foundation placeholders. No clinical interpretation, dosing, interaction checking, risk scoring, or laboratory workflow was added.

### Phase 1A-V — Environment + Verification

Status: PASS.

Environment correction: created `K:\clinicopus\.venv` with the only available local Python interpreter (3.14.6), installed the existing `backend/requirements.txt`, and changed no dependency files. CI still targets Python 3.12; that interpreter was not available on this host.

Verification: Django imported and ran; the backend started on localhost; authenticated clinician browser verification exercised the real `/consultations` route; synthetic note entry, section switching, signing, and read-back after reload were verified; desktop and narrow viewport screenshots were captured and checked for overflow; browser diagnostics were clean.

Correction made: the consultation page now hydrates the existing note content returned by the encounter API and resets the note draft when switching patients. This fixes the observed post-reload display defect without changing the API, signing workflow, or backend schema.

Files changed: `frontend/src/app/(app)/consultations/page.tsx`, `frontend/tests/clinic-slice.spec.ts`, and this handoff document. The `.venv` is a local environment artifact, not an application source change.

Migrations: none; `manage.py migrate --plan` reported no planned operations.

APIs: no new endpoints. The correction consumes the existing encounter `notes` response and existing consultation sign endpoint.

Tests: `19 passed, 5 skipped, 0 failed` backend tests; the five skips are PostgreSQL-only authentication/RLS tests. The relevant Playwright test reported `1 passed`; frontend typecheck, lint, and build passed. The local synthetic browser run reported no Phase 1A console errors or failed Phase 1A requests.

## 10. Current Known Issues

- Local verification used Python 3.14.6 because Python 3.12 was unavailable; CI remains the Python-version parity check.
- PostgreSQL/RLS-specific tests are skipped by design in the SQLite-only local verification; they must be run against PostgreSQL before infrastructure approval.
- The sandbox could not fetch the external Inter font during development, so the dev server used its existing fallback font. This did not affect the Phase 1A functional or layout checks.
- The local SQLite database contains development/test records from the verification runs. They are synthetic local records only and must not be treated as production data.

No unresolved Phase 1A application defect remains from the authenticated verification.

## 11. Frozen / Do-Not-Reopen Decisions

- The canonical backlog is frozen and was not modified.
- The current CSS/UI system is canonical.
- The same long-lived Encounter supports the Doctor → Lab → Doctor journey; do not introduce a separate lab consultation model.
- V1 provides no clinical decision support, diagnosis suggestions, dosing, interaction checking, allergy checking, or automatic risk scoring.
- Expired medicine is absolutely blocked; controlled/Class A medicines remain blocked in baseline V1.
- Stock changes are append-only movements; final clinical, financial, stock, payment, and audit records use immutable correction, reversal, amendment, or versioning paths.
- Organisation is the tenant root and Facility is a branch; PostgreSQL RLS must fail closed and use FORCE RLS under a non-bypass application role.
- Final stock, money, dispensing, and clinical sign-off operations are not offline-completable.

## 12. Next Approved Phase

**Phase 1B — NOT YET AUTHORISED**

## 13. Review Notes

Independent reviewers should inspect the current repository, this handoff, `KlinKlik-V1-Canonical-Backlog.md`, and the authoritative blueprint at `K:\new\clinicopus2.md`. Verify the code and tests directly rather than treating this document as the sole source of truth.

### Phase G0 — Public GitHub Repository Bootstrap

Status: PASS WITH VALIDATION LIMITATION.

Repository initialised: YES
GitHub repository name: `klinklik`
Visibility: PUBLIC
Initial baseline commit SHA: `a52615a9ee4b0b786c5783e530880a0437ffa948`
Public remote URL: `https://github.com/BernardByrnes/klinklik`
Security scan result: PASS. Pre-init, staged-tree, and post-push public-clone scans found no private keys, real data, browser auth/session state, local databases, or runtime/build artifacts. Synthetic development fixtures and environment templates were reviewed; Docker credentials were converted to environment-bound bootstrap values.
Any intentionally ignored local files/categories: local SQLite database, Python virtualenv/cache files, Node modules/Next build output, browser test output, logs, private keys/certificates, local environment files, and review artifacts.
Any publication-related adjustments: expanded `.gitignore`; removed committed Docker development credentials; added an environment-bound Docker bootstrap script; retained clearly synthetic seed/test fixture credentials.
Tests were not feature-regression changes: YES. Django check, backend tests, frontend typecheck, lint, build, and the safe no-payment Playwright subset passed. Payment-creating E2E cases were not run under the explicit no-payments constraint.
Next phase: Phase 1B — NOT YET AUTHORISED

Current Git status: clean `main` branch tracking the public `origin/main` baseline. No merge, deployment, or pull request was performed.

### Phase 1B — Presenting Complaint + HPI

Status: VERIFIED / PASS.

Objective: Add Presenting Complaint and History of Present Illness capture to the existing History section of the consultation workflow, using the existing Encounter and ClinicalNote persistence path.

Scope: Added only clinician-authored Presenting Complaint and HPI fields. Assessment/Plan remains available and is preserved through draft save, signing, reload, and patient switching. No diagnosis, treatment, medication, allergy, review-of-systems, examination, investigation, laboratory, payment, referral, follow-up, CDS, AI, interpretation, dosing, interaction checking, or risk-scoring workflow was added.

Files changed: backend/clinical/serializers.py, backend/clinical/services.py, backend/tests/test_phase_1b.py, frontend/src/app/(app)/consultations/page.tsx, frontend/src/features/clinic/types.ts, frontend/tests/phase-1b-history.spec.ts, and this handoff document.

Migration: none. The existing JSON ClinicalNote content is extended in place; manage.py migrate --plan reported no planned migration operations.

API/data contract: The existing note endpoint accepts presenting_complaint text up to 500 characters and hpi text up to 4000 characters. Existing consultation content remains supported. Signed notes remain immutable through the ordinary save path. Audit metadata records field presence and status transitions only; raw complaint/HPI values are not written to audit payloads.

Tests: Django check passed. Full backend suite passed with 23 passed and 5 PostgreSQL-only tests skipped. Focused Phase 1B backend coverage passed with 4 tests. Frontend typecheck, lint, and production build passed. No migration operations were pending.

Authenticated browser verification: The local Playwright Phase 1B test passed with 1 passed. Using synthetic local development patients, it verified real note POST persistence, section switching, Assessment/Plan retention, signing, patient isolation, reload read-back, signed read-only behavior, narrow viewport width 768 layout, and clean authenticated API/console diagnostics. No payment or external side effect was exercised.

Limitations: Verification used local SQLite synthetic data only; PostgreSQL/RLS-specific tests remain skipped pending a PostgreSQL environment. The in-app browser-control bridge was unavailable on this host, so the repository's authenticated local Playwright harness was used for the browser pass. The canonical blueprint and frozen backlog were not modified.

Next approved phase: NOT YET AUTHORISED

### Phase 1C — Relevant Past Medical + Surgical History

Status: VERIFIED / PASS.

Objective: Extend the existing History section with clinician-authored Relevant Past Medical History and Relevant Past Surgical History using the existing Encounter and ClinicalNote structured-content path, while preserving Presenting Complaint, HPI, and Assessment/Plan.

Frontend files changed: frontend/src/app/(app)/consultations/page.tsx, frontend/src/features/clinic/types.ts, and frontend/tests/phase-1c-history.spec.ts.

Backend files changed: backend/clinical/serializers.py, backend/clinical/services.py, and backend/tests/test_phase_1c.py.

Data contract changes: Existing ClinicalNote content now accepts past_medical_history and past_surgical_history text values up to 4,000 characters each. Partial draft and signing updates merge incoming keys with existing structured content, preserving other note fields. Existing clinical-note permissions, Encounter association, signed immutability, tenant/facility filters, and metadata-only audit behavior remain authoritative.

Migration status: NONE. No new model, table, column, endpoint, or migration was added; manage.py migrate --plan reported no planned migration operations.

Tests: Full backend suite passed with 26 passed and 5 PostgreSQL-only tests skipped. Focused Phase 1C backend coverage passed with 3 tests; existing Phase 1B backend regression coverage passed with 4 tests. Django check, frontend typecheck, lint, and production build passed.

Authenticated browser verification: The local Playwright Phase 1C test passed with 1 passed in 33.8 seconds using synthetic local development patients. It verified real note persistence, partial save, existing Presenting Complaint/HPI retention, Assessment/Plan retention through signing, section switching, reload hydration, patient isolation, signed read-only behavior, desktop and narrow viewport width 768 layout, no horizontal overflow, and no authenticated console/API diagnostics. The existing no-payment Phase 1B browser regression also passed with 1 passed in 47.2 seconds.

Known limitations: Verification used local SQLite synthetic data only; five PostgreSQL/RLS-specific tests remain skipped pending a PostgreSQL environment. The in-app browser-control bridge was unavailable on this host, so the repository Playwright harness was used for the authenticated browser pass. No family, social, medication, allergy, ROS, examination, diagnosis, laboratory, billing, payment, pharmacy, queue, CDS, AI, interpretation, or Phase 1D functionality was added. The canonical blueprint and frozen backlog were not modified.

Next approved phase: NOT YET AUTHORISED

### Phase 1C-F - Clinical Note Concurrency Integrity

Result: PASS WITH VALIDATION LIMITATION.

Objective: close the ClinicalNote save-versus-sign race and prevent duplicate first consultation-note creation without changing the Phase 1B/1C data contract or adding frontend scope.

Correction: note write paths now acquire locks in one order, Encounter first and then the consultation ClinicalNote. The signed-state check occurs after the locks are held. This serializes save, sign, and amend operations for an Encounter. A database UniqueConstraint on (encounter, note_type) provides the durable one-note invariant; the migration is backend/clinical/migrations/0003_clinicalnote_unique_encounter_type.py.

Files changed: backend/clinical/models.py, backend/clinical/services.py, backend/clinical/migrations/0003_clinicalnote_unique_encounter_type.py, backend/tests/test_phase_1c_f.py, and this handoff document. No frontend files or canonical backlog files changed.

Data and audit safety: existing tenant/facility authorization filters, signed-note immutability, amendment/version behavior, content merging, and metadata-only audit behavior were preserved. The synthetic tests contain no real patient data and no raw clinical content is added to audit payloads.

Migration verification: duplicate preflight groups were zero in local SQLite and local PostgreSQL. The uniqueness migration applied successfully to both local databases; makemigrations --check --dry-run reported No changes detected, and migrate --plan reported no pending operations after application.

Concurrency verification: the real PostgreSQL suite passed with 4 passed, including save-versus-sign serialization and concurrent first-save creation. The SQLite-focused run reported 2 passed, 2 skipped; the two skips are the PostgreSQL-only row-lock tests and are not treated as concurrency evidence.

PostgreSQL limitation: the same test module could not complete under the non-bypass application role because pytest-django fixture teardown requires table truncate/ownership privileges that role intentionally does not have. No database permissions were changed. The passing PostgreSQL owner-role run exercised the actual PostgreSQL row-lock and uniqueness behavior; the application-role fixture limitation is recorded rather than treated as an application failure.

Regression verification: full backend suite 28 passed, 7 skipped; focused Phase 1B suite 4 passed; focused Phase 1C suite 3 passed; Django check passed; frontend typecheck, lint, and production build passed. The existing safe authenticated synthetic Phase 1C browser regression passed with 1 passed using the repository Playwright harness. No payment or external side effect was exercised.

Next approved phase: NOT YET AUTHORISED. Phase 1D was not started.

### Phase 1D - Family History + Social History

Status: VERIFIED / PASS.

Objective: add only clinician-authored narrative Relevant Family History and Relevant Social History to the existing consultation History workspace.

Fields implemented: family_history and social_history, both multiline narrative fields with a 4,000-character maximum. Structured smoking, alcohol, substance, occupation, safeguarding, and social-risk fields were not added.

Persistence mechanism: existing Encounter -> ClinicalNote structured JSON content, using the Phase 1C-F hardened Encounter-first / ClinicalNote-second save and sign paths. No new model, endpoint, or database column was added.

Frontend files changed: frontend/src/app/(app)/consultations/page.tsx, frontend/src/features/clinic/types.ts, and frontend/tests/phase-1d-history.spec.ts.

Backend files changed: backend/clinical/serializers.py, backend/clinical/services.py, and backend/tests/test_phase_1d.py.

Migration status: NONE. makemigrations --check --dry-run reported No changes detected.

API/data-contract changes: existing note write/amend validation now accepts family_history and social_history as strings up to 4,000 characters. Existing partial merge, signing, amendment, and Encounter response behavior remains authoritative.

Security/PHI verification: audit metadata records changed field names only; raw history text is not added to generic audit payloads, logs, or browser storage. Existing clinical-note capability, tenant, and facility isolation was verified.

Tests: focused Phase 1D backend 7 passed; full backend 35 passed and 7 skipped; Phase 1B 4 passed; Phase 1C 3 passed; Phase 1C-F PostgreSQL integrity 4 passed; frontend typecheck, lint, and build passed.

PostgreSQL concurrency regression status: PASS. Existing Phase 1C-F PostgreSQL owner-role suite passed 4/4; the previously documented non-bypass application-role pytest teardown limitation remains unchanged and no permissions were loosened.

Authenticated browser verification: Phase 1D 1 passed; existing Phase 1B and Phase 1C consultation regressions 2 passed. Synthetic local Playwright verification covered reload, section switching, patient isolation, signing, signed read-only state, storage checks, narrow layout, and clean diagnostics. The in-app bridge was unavailable, so the repository harness was used.

Known limitations: this implements the explicitly authorized narrative-only slice; the canonical backlog's broader structured-lite social expansion remains outside this phase. The canonical backlog was not modified.
Next approved phase: NOT YET AUTHORISED

### Phase 1D-F — Draft Lost-Update Protection

Status: VERIFIED / PASS.

Objective: prevent stale clinical draft snapshots from overwriting fields edited by another client or while a save request is in flight, without changing the Phase 1C-F locking or partial-merge contract.

Correction: the consultation workspace now keeps an in-memory canonical snapshot, draft values, dirty field IDs, and a patient/session token. Save and sign requests submit only the dirty clinical fields. Successful responses update the canonical snapshot and clear only fields whose values are still unchanged; edits made during an in-flight request remain unsaved. Patient switching invalidates prior responses and clears draft state. Section switching retains the React draft state.

Signing: signing uses the same dirty-field partial payload and hydrates the authoritative signed response. The existing Encounter-first / ClinicalNote-second locks, signed immutability, versioning, and backend merge behavior remain unchanged. The sign response now returns authoritative content so the client cannot rebuild a signed note from a stale snapshot.

Race coverage: backend tests cover family-versus-social, family-versus-HPI, and family-versus-Assessment/Plan stale partial writes, audit field-name minimization, and stale partial signing. The authenticated browser tests cover two stale local clients editing different fields and a second edit made while the first save is delayed. Both writers survive.

PHI safety: dirty field IDs and draft values exist only in React memory. No PHI was added to browser storage, logs, or audit payloads; backend assertions verify raw synthetic values are absent from the latest audit metadata. Verification used synthetic local development records only and exercised no external side effects.

Files changed: backend/clinical/views.py, backend/tests/test_phase_1d_f.py, frontend/src/app/(app)/consultations/page.tsx, frontend/tests/phase-1d-history.spec.ts, and this handoff document.

Migration status: NONE. Django check passed; makemigrations --check --dry-run reported No changes detected.

Tests: focused Phase 1D-F backend 4 passed; full backend suite 39 passed and 7 skipped; existing Phase 1C-F PostgreSQL owner-role integrity suite 4 passed; frontend typecheck, lint, and production build passed. The documented non-bypass application-role pytest teardown limitation remains unchanged and no permissions were loosened.

Authenticated browser verification: Phase 1D regression file 3 passed, including the two new race tests; existing Phase 1B and Phase 1C consultation regressions 2 passed. The in-app Chrome bridge was unavailable despite diagnostics, so the repository Playwright harness was used against the local development server.

Scope and architecture: no canonical blueprint or backlog changes, no Phase 1E work, no new endpoint or model, no redesign, and no Phase 2/3 functionality. Existing service, authorization, tenant/facility, audit, signed-note, and PostgreSQL locking boundaries were preserved.

Known limitations: PostgreSQL verification is the existing Phase 1C-F owner-role integrity suite; pytest teardown under the intentionally restricted application role remains a test-fixture privilege limitation. Optimistic locking/ETag conflict detection remains outside this slice.

Next approved phase: NOT YET AUTHORISED

### Phase 1D-F2 — Clinical Draft ETag Conflict Protection

Status: VERIFIED / PASS WITH VALIDATION LIMITATION.

Objective: protect clinical draft revision, signing, and amendment writes against stale clients while preserving the Phase 1D-F dirty-field merge contract and the Phase 1C-F lock order.

Original integrity defect: two clients could edit the same clinical field from the same baseline; partial dirty-field merging preserved unrelated concurrent fields but did not reject a same-field stale write. That allowed the later stale writer to overwrite the earlier writer's value.

Canonical concurrency contract: the implementation follows the ENC-002 concurrency requirement in the canonical backlog. Clinical note mutations require HTTP If-Match. A missing precondition fails closed with 428 PRECONDITION_REQUIRED. A stale token returns 409 CLINICAL_NOTE_REVISION_CONFLICT with the current opaque ETag, status, Encounter status, and authorized current content for review. The authoritative token is returned on Encounter load and on clinical mutation responses, including the no-note state.

ETag design: the token is an opaque HMAC-SHA256 value keyed by Django SECRET_KEY over a versioned clinical-note scope, tenant/facility/Encounter/note identity, note status/version/timestamp, and content. It does not contain raw PHI. The no-note state has an authoritative absent-note token; the first successful save changes it. Mutable Encounter status is not included in the token so signing does not create an artificial post-mutation token mismatch.

Backend protection: save, sign, and amend lock Encounter first and ClinicalNote second, then perform the decisive ETag comparison while both rows are locked. The conflict response includes the current ETag header and current state without creating a clinical UPDATE audit event. Amendment/version preservation and signed-note immutability remain enforced. No schema migration was required.

Frontend protection: the consultation workspace keeps the authoritative baseline, draft values, dirty field IDs, ETag, and session token in React memory. Same-field conflicts preserve the local draft and require an explicit retry; the UI names the conflicting field. A stale request whose dirty fields do not overlap the remote changes may rebase and retry once only. Signing never auto-retries; a stale sign preserves the local draft, updates the authoritative baseline/ETag, closes confirmation, and requires explicit review and retry. In-flight request/session guards, section switching, patient switching, and no-PHI browser persistence remain intact.

Migration status: NONE. Django check passed; makemigrations --check --dry-run reported No changes detected; migrate --plan reported No planned migration operations.

Files changed: backend/clinical/concurrency.py, backend/clinical/serializers.py, backend/clinical/services.py, backend/clinical/views.py, backend/tests/clinical_test_helpers.py, backend/tests/test_phase_1b.py, backend/tests/test_phase_1c.py, backend/tests/test_phase_1c_f.py, backend/tests/test_phase_1d.py, backend/tests/test_phase_1d_f.py, backend/tests/test_phase_1d_f2.py, backend/tests/test_vertical_slice.py, frontend/src/app/(app)/consultations/page.tsx, frontend/src/features/clinic/types.ts, frontend/src/lib/api.ts, frontend/tests/phase-1d-history.spec.ts, and this handoff document.

Tests: full backend suite 45 passed and 7 skipped; the skipped tests are the five PostgreSQL-only auth/RLS tests and two PostgreSQL-only Phase 1C-F row-lock tests in the current SQLite-only environment. The combined Phase 1B/1C/1C-F/1D/1D-F/1D-F2/vertical suite passed 31 with 2 PostgreSQL-only skips; focused Phase 1D-F2 passed 6. Frontend typecheck, lint, and production build passed. The full authenticated Phase 1D history Playwright file passed 5/5, including same-field stale-draft preservation, one-time non-overlapping rebase, stale-sign preservation, in-flight editing, and existing history coverage.

PostgreSQL limitation: the current local verification run does not provision or use an external database and therefore skips the two PostgreSQL-only row-lock tests. The prior Phase 1C-F owner-role PostgreSQL integrity baseline recorded 4/4 passing; the documented restricted application-role pytest teardown limitation remains unchanged and no permissions were loosened.

Security and scope: verification and browser data were synthetic local development data only. No credentials, seed passwords, secrets, PHI, local database, browser session state, or runtime artifacts were added or exposed. ETags contain no raw clinical values; conflict state is returned only through the authorized clinical API response, and audit/log assertions continue to exclude raw note content. No email, SMS, payment, webhook, or other external side effect occurred. The canonical blueprint and backlog were not modified. Phase 1E and later phases were not started.

Next approved phase: NOT YET AUTHORISED

### Phase 1D-F3 — Conflict Rebase Visibility

Status: VERIFIED / PASS WITH VALIDATION LIMITATION.

Original issue: Phase 1D-F2 updated the authoritative content ref and ETag after a 409 conflict but did not reliably rehydrate visible React fields. A clinician could therefore see stale remote clinical content, including stale HPI content before a stale-sign retry.

Rebase behaviour: for all seven editable fields (presenting_complaint, hpi, past_medical_history, past_surgical_history, family_history, social_history, and consultation), remote-changed non-dirty values now update the visible React field and draft ref immediately. Locally dirty values remain unchanged. The canonical content ref and current ETag are updated from the server response. Non-overlapping save conflicts retain the existing safe one-time retry.

Same-field comparison behaviour: same-field conflicts preserve the local textarea value, remain unsaved, and show an in-memory comparison panel with the current saved server value and the affected field name. The comparison clears after explicit save success. No comparison content is written to logs, telemetry, audit, URLs, or browser persistent storage.

Stale-sign review behaviour: a stale sign conflict closes confirmation without retrying, visibly hydrates remote non-dirty fields such as HPI, preserves the local Consultation Note draft, and leaves the Encounter unsigned. The clinician must explicitly retry using the latest ETag. The browser regression verifies the final signed content contains the latest remote HPI and local Consultation Note, with ClinicalNoteVersion 1.

Patient isolation: selecting another patient clears prior dirty fields, comparison values, draft state, ETag, and conflict messaging. No conflict comparison from the prior patient is rendered for the next patient.

Backend changes: NONE. ETag HMAC generation, If-Match/428/409 contract, Encounter-first and ClinicalNote-second locking, unique note invariant, sign/version logic, amendment logic, and signed immutability were not changed.

Files changed: frontend/src/app/(app)/consultations/page.tsx, frontend/tests/phase-1d-history.spec.ts, and this handoff document.

Migration status: NONE. Django check passed; makemigrations --check --dry-run reported No changes detected; migrate --plan reported no planned migration operations.

Tests: full backend suite 45 passed and 7 skipped; the seven skips are the documented PostgreSQL-only auth/RLS and row-lock tests in the local SQLite environment. The focused Phase 1B/1C/1C-F/1D/1D-F/1D-F2/vertical regression group passed 31 with 2 PostgreSQL-only row-lock skips. Frontend typecheck, lint, and production build passed.

Authenticated browser verification: the full local Playwright consultation file passed 6/6 in 2.6 minutes. It covered existing persistence/isolation, non-overlapping visible rebase, same-field comparison and explicit retry, in-flight editing, stale-sign remote-field visibility and no automatic sign retry, final signed content/version, and patient conflict-state isolation. Synthetic local development data only was used; no external side effects occurred.

Known limitations: PostgreSQL-only tests were not rerun in this local SQLite-only verification; the prior Phase 1C-F owner-role PostgreSQL baseline remains 4/4 passing, with the documented restricted application-role pytest teardown limitation unchanged. The in-app browser bridge was unavailable, so the repository Playwright harness was used.

Security and scope: no backend architecture, canonical backlog, blueprint, new clinical field, persistent PHI storage, or Phase 1E functionality was introduced. Conflict comparison values exist only in authenticated React memory and rendered clinical workspace state. No credentials, secrets, PHI, database, browser state, or runtime artifacts were added.

Next approved phase: NOT YET AUTHORISED

### Phase 1E — General Examination

Status: VERIFIED / PASS WITH VALIDATION LIMITATION.

Objective: implement only the first ENC-014 slice: clinician-authored multiline General Examination narrative with a 2,000-character maximum. Per-system examination fields, normal-exam quick action, ROS, clinical interpretation, and Phase 1F work were not added.

ClinicalNote key: general_examination in the existing Encounter -> ClinicalNote.content JSON document. No new model, column, endpoint, or migration was introduced.

Persistence: existing Encounter-first / ClinicalNote-second locking, partial content merge, dirty-field-only submission, authoritative consultation ETag, If-Match/428/409 conflict handling, one-time non-overlap rebase, signed-note immutability, ClinicalNoteVersion, and amendment paths all include the new key. Reload, section switching, correct-Encounter association, and patient isolation were verified.

Validation: backend rejects non-string values and values over 2,000 characters without truncation; exactly 2,000 characters round-trip unchanged. The frontend presents a multiline field with the same maximum.

Frontend files: frontend/src/app/(app)/consultations/page.tsx, frontend/src/features/clinic/types.ts, frontend/tests/phase-1d-history.spec.ts.

Backend files: backend/clinical/serializers.py, backend/clinical/services.py, backend/tests/test_phase_1e.py.

Migration status: NONE. Django check passed; makemigrations --check --dry-run reported No changes detected; migrate --plan reported No planned migration operations.

Concurrency regression: focused backend coverage passed same-field stale-write rejection, HPI-versus-General Examination stale-client retry, current-value conflict response, and post-sign protection. Browser coverage passed representative HPI-versus-General Examination stale-client rebase with both values retained. Existing Encounter-first / ClinicalNote-second lock order and ETag contract were unchanged.

Security/PHI: verification used synthetic local SQLite development data only. Audit metadata records field names without raw examination text. No raw note text was added to logs, telemetry, URLs, browser persistent storage, or audit payloads. Existing clinical-note capability, tenant, facility, session, and patient guards remain authoritative. No external side effects occurred.

Tests: focused Phase 1E backend 13 passed; full backend suite 58 passed and 7 skipped for the documented PostgreSQL-only auth/RLS and row-lock checks; focused clinical regression group 44 passed and 2 skipped; frontend typecheck passed; lint passed; production build passed.

Browser verification: the two new Phase 1E Playwright tests passed; the full authenticated consultation regression file passed 8/8 in 2.1 minutes. Coverage included synthetic encounter creation, dirty-only request payload, save/reload, section switching, patient A/B isolation, signing, exact signed read-only rendering, stale-client rebase, and no captured console errors or failed API requests in the new persistence/isolation test. The in-app browser bridge was unavailable, so the repository Playwright harness was used.

Known limitations: PostgreSQL-only tests were not rerun in this local SQLite-only verification; the prior owner-role PostgreSQL integrity baseline and restricted application-role pytest teardown limitation remain unchanged. The canonical blueprint and backlog were not modified. Phase 1F and later phases remain out of scope.

Next approved phase: NOT YET AUTHORISED


### Phase 1F — Cardiovascular + Respiratory Examination

Status: VERIFIED / PASS WITH VALIDATION LIMITATION.

Objective: implement only the ENC-014 cardiovascular and respiratory examination slice as clinician-authored multiline text. General Examination remains available. Abdominal, CNS, GUS, musculoskeletal, normal-exam quick action, ROS, automated interpretation, clinical decision support, and Phase 1G work were not added.

ClinicalNote keys: cardiovascular_examination and respiratory_examination in the existing Encounter -> ClinicalNote.content JSON document. The existing general_examination key remains unchanged.

Persistence: the existing Encounter-first / ClinicalNote-second locking, partial content merge, dirty-field-only submission, authoritative ETag, If-Match precondition, 428/409 conflict handling, one-time non-overlap rebase, signed-note immutability, ClinicalNoteVersion, and amendment paths include both new keys. Reload, section switching, correct Encounter association, and patient A/B isolation were verified.

Validation: backend rejects non-string values and values over 2,000 characters without truncation; exactly 2,000 characters are accepted and round-trip unchanged. The frontend presents two multiline fields with 2,000-character limits and clear clinician-authored-only guidance.

Concurrency behaviour: non-overlapping stale respiratory edits rebase after a general examination update and preserve both writers. Same-field cardiovascular conflicts preserve the local draft, expose the current server comparison in authenticated React memory, and require an explicit retry. An in-flight cardiovascular save does not clear a later respiratory edit; the second request contains only the respiratory dirty field.

Signed behaviour: signed notes render General Examination, Cardiovascular Examination, and Respiratory Examination as immutable read-only cards. Empty signed fields render Not recorded. Exact signed values were verified, and all three editable textboxes disappear after signing.

Security/PHI: verification used synthetic local SQLite development data only. Audit metadata records field names without raw examination text. No raw note text was added to logs, telemetry, URLs, localStorage, sessionStorage, or audit payloads. Existing server-side tenant, facility, session, capability, and patient guards remain authoritative. No email, SMS, payment, webhook, or other external side effect occurred.

Files changed: backend/clinical/serializers.py, backend/clinical/services.py, backend/tests/test_phase_1f.py, frontend/src/app/(app)/consultations/page.tsx, frontend/src/features/clinic/types.ts, frontend/tests/phase-1d-history.spec.ts, and this handoff document.

Migration status: NONE. Django check passed; makemigrations --check --dry-run reported No changes detected; migrate --plan reported No planned migration operations.

Tests: focused Phase 1F backend coverage passed 16 tests. Full backend suite passed 74 tests with 7 documented PostgreSQL-only skips: five PostgreSQL authentication/RLS tests and two PostgreSQL row-lock tests. The required focused clinical regression group passed 60 tests with 2 PostgreSQL row-lock skips. Frontend typecheck, lint, and production build passed.

Browser verification: the full authenticated local Playwright consultation file passed 12/12 in 4.6 minutes. It covered Phase 1D/1E regressions plus Phase 1F persistence, dirty-only payloads, reload, section switching, patient isolation, empty and populated signed read-only rendering, non-overlapping rebase, same-field conflict and explicit retry, in-flight editing, and no captured console errors or failed API requests in the new persistence/isolation case. Synthetic local development data only was used; the repository Playwright harness was used because the in-app browser bridge was unavailable.

Known limitations: PostgreSQL-only tests were not rerun in this local SQLite-only verification. The prior owner-role PostgreSQL integrity baseline and restricted application-role pytest teardown limitation remain unchanged. The canonical blueprint and canonical backlog were not modified. No Phase 1G work was started.

Next approved phase: NOT YET AUTHORISED


### Phase 1G — Abdominal/Gastrointestinal + Neurological/CNS Examination

Status: VERIFIED / PASS WITH VALIDATION LIMITATION.

Objective: implement only the ENC-014 abdominal/gastrointestinal and neurological/CNS examination slice as clinician-authored multiline text. No normal-exam quick action, structured findings, body diagrams, automated interpretation, GUS, musculoskeletal examination, or Phase 1H work was added.

ClinicalNote keys: abdominal_examination and neurological_examination in the existing Encounter -> ClinicalNote.content JSON document. The existing general_examination, cardiovascular_examination, and respiratory_examination keys remain unchanged.

Persistence: the existing Encounter-first / ClinicalNote-second locking, partial content merge, dirty-field-only submission, authoritative ETag, If-Match precondition, 428/409 conflict handling, one-time non-overlap rebase, signed-note immutability, ClinicalNoteVersion, and amendment paths include both new keys. Reload, section switching, correct Encounter association, and patient A/B isolation were verified. No new model, endpoint, database column, or migration was introduced.

Validation: backend rejects non-string values and values over 2,000 characters without truncation; exactly 2,000 characters are accepted and round-trip unchanged. The frontend presents two multiline fields with 2,000-character limits and clinician-authored-only guidance.

Concurrency behaviour: non-overlapping stale neurological edits rebase after a respiratory examination update and preserve both writers. Same-field abdominal conflicts preserve the local draft, expose the current server comparison in authenticated React memory, and require an explicit retry. An in-flight abdominal save does not clear a later neurological edit; the second request contains only the neurological dirty field. ETag, If-Match, 428, 409, stale sign protection, and version consistency remain covered.

Signed behaviour: signed notes render General Examination, Cardiovascular Examination, Respiratory Examination, Abdominal / Gastrointestinal Examination, and Neurological / CNS Examination as immutable read-only cards. Empty signed fields render Not recorded. Exact signed values were verified, and all five editable textboxes disappear after signing.

Security/PHI: verification used synthetic local SQLite development data only. Audit metadata records field names without raw examination text. No raw note text was added to logs, telemetry, URLs, localStorage, sessionStorage, or audit payloads. Existing server-side tenant, facility, session, capability, and patient guards remain authoritative. No email, SMS, payment, webhook, or other external side effect occurred.

Files changed: backend/clinical/serializers.py, backend/clinical/services.py, backend/tests/test_phase_1g.py, frontend/src/app/(app)/consultations/page.tsx, frontend/src/features/clinic/types.ts, frontend/tests/phase-1d-history.spec.ts, and this handoff document.

Migration status: NONE. Django check passed; makemigrations --check --dry-run reported No changes detected; migrate --plan reported No planned migration operations.

Tests: focused Phase 1G backend coverage passed 16 tests in 13.84 seconds. Full backend suite passed 90 tests with 7 documented PostgreSQL-only skips: five PostgreSQL authentication/RLS tests and two PostgreSQL row-lock tests. The required focused clinical regression group passed 76 tests with 2 PostgreSQL row-lock skips. Frontend typecheck, lint, and production build passed.

Browser verification: the focused Phase 1G Playwright run passed 4/4 in 2.5 minutes. The full authenticated local Playwright consultation file passed 16/16 in 5.4 minutes. Coverage included synthetic encounter creation, dirty-only payloads for existing and new fields, save/reload, section switching, patient isolation, empty and populated signed read-only rendering, non-overlapping rebase, same-field comparison and explicit retry, in-flight editing, exact ETag retry behaviour, and no captured console errors or failed API requests in the new persistence/isolation case. The repository Playwright harness was used because the in-app browser bridge was unavailable.

PostgreSQL limitation: PostgreSQL-only tests were not rerun in this local SQLite-only verification. The prior owner-role PostgreSQL integrity baseline and restricted application-role pytest teardown limitation remain unchanged. No permissions were loosened.

Security and scope: the canonical blueprint and canonical backlog were not modified. No Phase 1H work was started. No credentials, seed passwords, secrets, PHI, local database, browser session state, or runtime artifacts were added or exposed.

Known limitations: this remains the explicitly authorized narrative-only abdominal/GI and neurological/CNS slice; structured examination findings, normal-exam quick action, clinical interpretation, body diagrams, GUS, musculoskeletal, and later phases remain outside scope.

Next approved phase: NOT YET AUTHORISED


### Phase 1H — Genitourinary + Musculoskeletal Examination

Status: VERIFIED / PASS WITH VALIDATION LIMITATION.

Objective: implement only the ENC-014 genitourinary and musculoskeletal examination slice as two clinician-authored multiline narrative fields. No normal-exam quick action, structured findings, automated interpretation, additional examination systems, lab, diagnosis/treatment, queue, billing, pharmacy, or Phase 1I work was added.

ClinicalNote keys: genitourinary_examination and musculoskeletal_examination in the existing Encounter -> ClinicalNote.content JSON document. The existing general_examination, cardiovascular_examination, respiratory_examination, abdominal_examination, and neurological_examination keys remain unchanged.

Persistence: the existing Encounter-first / ClinicalNote-second locking, partial content merge, dirty-field-only submission, authoritative ETag, If-Match precondition, 428/409 conflict handling, one-time non-overlap rebase, signed-note immutability, ClinicalNoteVersion, and amendment paths include both new keys. Save, reload, section switching, correct Encounter association, and patient A/B isolation were verified. No new model, endpoint, database column, or migration was introduced.

Validation: backend rejects non-string values and values over 2,000 characters without truncation; exactly 2,000 characters are accepted and round-trip unchanged. The frontend presents two multiline fields with 2,000-character limits and clinician-authored-only guidance.

Concurrency behaviour: dirty-field-only requests contain only the edited genitourinary or musculoskeletal key. A stale musculoskeletal edit rebases after a neurological examination update and preserves both writers. A same-field genitourinary conflict preserves the local draft, exposes the current server comparison in authenticated React memory, and requires an explicit retry. An in-flight genitourinary save does not clear a later musculoskeletal edit. ETag, If-Match, 428, 409, stale-sign protection, and version consistency remain covered.

Signed behaviour: signed notes render General Examination, Cardiovascular Examination, Respiratory Examination, Abdominal / Gastrointestinal Examination, Neurological / CNS Examination, Genitourinary Examination, and Musculoskeletal Examination as immutable read-only cards. Empty signed fields render Not recorded. Exact synthetic values were verified, and all seven editable examination textboxes disappear after signing.

Security/PHI: verification used synthetic local SQLite development data only. Audit metadata records field names without raw examination text. No raw note text was added to logs, telemetry, URLs, localStorage, sessionStorage, or audit payloads. Existing server-side tenant, facility, session, capability, and patient guards remain authoritative. No email, SMS, payment, webhook, or other external side effect occurred.

Files changed: backend/clinical/serializers.py, backend/clinical/services.py, backend/tests/test_phase_1h.py, frontend/src/app/(app)/consultations/page.tsx, frontend/src/features/clinic/types.ts, frontend/tests/phase-1d-history.spec.ts, and this handoff document.

Migration status: NONE. Django check passed; makemigrations --check --dry-run reported No changes detected; migrate --plan reported No planned migration operations.

Tests: focused Phase 1H backend coverage passed 25 tests in 25.07 seconds. Full backend suite passed 115 tests with 7 documented PostgreSQL-only skips in 58.86 seconds. The required focused clinical regression group passed 101 tests with 2 PostgreSQL-only row-lock skips in 45.63 seconds. Frontend typecheck, lint, and production build passed.

Browser verification: the focused Phase 1H Playwright run passed 5/5 in 2.6 minutes. The final full authenticated local Playwright consultation file passed 21/21 in 8.0 minutes. Coverage included synthetic encounter creation, dirty-only payloads, save/reload, section switching, patient isolation, empty and populated signed read-only rendering, non-overlapping rebase, same-field comparison and explicit retry, in-flight editing, stale-sign explicit retry, exact ETag retry behaviour, and no captured console errors or failed API requests in the new persistence/isolation case. An earlier full-suite run had one transient session-restoration timeout; the affected test passed in isolation and the final full rerun passed all 21 tests. The repository Playwright harness was used because the in-app browser bridge was unavailable.

PostgreSQL limitation: PostgreSQL-only tests were not rerun in this local SQLite-only verification. The prior owner-role PostgreSQL integrity baseline and restricted application-role pytest teardown limitation remain unchanged. No permissions were loosened.

Architecture and scope: the existing canonical Django/DRF monolith, Encounter/ClinicalNote persistence model, service workflow, authorization boundaries, ETag conflict contract, and frontend consultation architecture were reused. The canonical blueprint and canonical backlog were not modified. No Phase 1I work was started.

Known limitations: this remains the explicitly authorized narrative-only genitourinary and musculoskeletal slice; structured examination findings, normal-exam quick action, clinical interpretation, body diagrams, and later phases remain outside scope.

Next approved phase: NOT YET AUTHORISED


### Phase 1I — Reviewed Normal Examination Quick Action

Status: VERIFIED / PASS WITH VALIDATION LIMITATION.

Objective: implement only a frontend drafting convenience for the reviewed normal examination quick action across the seven existing narrative examination systems. No backend workflow, model, endpoint, migration, clinical interpretation, structured findings, or Phase 1J work was introduced.

Clinical safety: the action is available only in an unsigned mutable Examination section. All seven systems are shown with explicit clinician selection required; none is preselected and no Select all or Mark all control exists. The static templates are concise and editable: General — “Patient appears clinically well. No abnormal general findings noted.”; Cardiovascular — “Cardiovascular examination: no abnormal findings noted.”; Respiratory — “Respiratory examination: no abnormal findings noted.”; Abdominal — “Abdominal examination: no abnormal findings noted.”; Neurological — “Neurological examination: no abnormal findings noted.”; Genitourinary — “Genitourinary examination: no abnormal findings noted.”; Musculoskeletal — “Musculoskeletal examination: no abnormal findings noted.” The feature does not infer that a system was examined or reviewed.

Existing-content protection: fields with saved content, local dirty content, or an active conflict comparison are disabled and are never replaced. Selection is rechecked at insertion time so a field becoming unavailable during the interaction is skipped. Unselected systems remain unchanged. Cancel and Escape close the panel without mutation. The heading receives focus when the panel opens, system labels are associated with keyboard-operable checkboxes, and the insertion panel exposes a clear accessible heading and group label.

Draft and persistence behaviour: insertion calls the existing clinical-field draft update helper, so the visible value, draft ref, dirty-field tracking, unsaved state, and notice handling remain on the established path. The note-content ref is not mutated by the quick action. No request is made until the clinician explicitly chooses Save draft or Sign consultation; inserted text remains editable. Save requests contain only dirty fields, and the existing ETag, If-Match, 428, 409, comparison, retry, rebase, and in-flight-save logic remains authoritative.

Concurrency: focused browser coverage verified a same-field stale conflict for a template-inserted field, preservation of the local template and server comparison, explicit retry with the conflict ETag, and non-overlapping rebase with both examination values retained. An insertion made while another examination save was in flight remained unsaved and was sent only on the later explicit save.

Signed and isolation behaviour: after signing, the quick action and editable controls are unavailable and the existing immutable read-only Examination rendering is unchanged. Opening/closing the panel and switching sections clears transient panel selections while preserving inserted draft values; switching patients clears the transient state and does not leak draft values. No browser persistent storage is used. No automatic save or sign was added.

Security and audit: no new audit event was introduced for local insertion; existing save/sign audit behaviour remains unchanged and records field keys rather than raw examination text. Templates are static source text and contain no patient data. Verification used synthetic local SQLite development data only, with no credentials, secrets, PHI, email, SMS, payment, webhook, or other external side effect.

Backend and migration status: NONE. No backend file, API contract, model, database column, migration, or generated client type changed. The existing Django/DRF service and authorization boundaries, tenant isolation, signed-note immutability, and Next.js consultation architecture were reused. The canonical blueprint and canonical backlog were not modified.

Files changed: frontend/src/app/(app)/consultations/page.tsx, frontend/tests/phase-1d-history.spec.ts, and this handoff document.

Validation: full backend pytest passed 115 tests with 7 documented PostgreSQL-only skips in 63.06 seconds. The focused clinical regression group passed 101 tests with 2 PostgreSQL-only row-lock skips in 56.31 seconds. The focused Phase 1I Playwright run passed 7 tests in 4.2 minutes. The full authenticated consultation Playwright file passed 28 tests in 16.1 minutes. Frontend typecheck, lint, and production build passed. Django check reported no issues; makemigrations --check --dry-run reported No changes detected; migrate --plan reported No planned migration operations. The repository Playwright harness was used because the in-app browser bridge was unavailable.

Known limitations: PostgreSQL-only tests were not rerun in this local SQLite-only verification; the documented PostgreSQL owner-role integrity baseline and restricted application-role pytest teardown limitation remain unchanged. No new blueprint decision was made. Phase 1J and all later work remain outside scope.

Next approved phase: NOT YET AUTHORISED

### Phase 1J — Debounced Autosave Core

Status: IMPLEMENTED / VERIFIED / PASS WITH VALIDATION LIMITATION.

Baseline: e5c30bacdac90fe86608e92a9a7d37efc34e2f84 on main, with the local public remote unchanged.

Objective: add the approved Phase 1J debounced autosave core for the existing consultation draft workflow. All editable ClinicalNote fields use one three-second debounce, including history, the seven examination fields, and consultation Assessment/Plan content. Explicit Save remains available and cancels the timer; manual saves use the existing dirty-field-only payload and do not receive the autosave marker.

Persistence and timestamp: the existing Encounter/ClinicalNote workflow, ETag, If-Match, 428 precondition, 409 conflict comparison, safe non-overlap rebase, and signed-note immutability were reused. Successful note responses now expose saved_at from the persisted ClinicalNote.updated_at; the UI renders Saved HH:MM:SS. Unsaved and failed states remain truthful as Not saved or Not saved - use Save draft. No browser storage, persistent query cache, or local PHI persistence was added.

In-flight and session safety: same-tab saves do not overlap. Edits made during an in-flight save remain dirty and receive a follow-up debounce after the response; late responses from a switched patient/session cannot update the active draft. Section switching preserves the session and timer. Patient switching cancels the timer and resets autosave session state. Signed, closed, and cancelled encounters do not autosave.

Conflict and retry scope: a same-field autosave 409 retains the local draft, exposes the server comparison, blocks further autosave, and requires explicit Save. Non-overlapping autosave conflicts reuse the existing one-time safe rebase/retry. Ordinary autosave failures remain unsaved without a Retry loop. No automatic retry/backoff policy was added.

Reviewed-normal insertion: insertion continues through the ordinary dirty-field update path. It makes the selected field dirty, schedules the normal debounce, and does not issue an immediate request. Existing-content, local-dirty, conflict, signed, and patient-isolation protections remain in force.

Audit: autosave requests are identified only by the safe X-KlinKlik-Autosave: 1 header, which is not an authorization boundary. They do not create an ordinary ClinicalNote audit event for every save. The existing AuditEvent model records at most one safe ENCOUNTER_DRAFT_UPDATED summary marker per clinician, Encounter, and minute, containing only note type and minute metadata; no clinical text is recorded. Manual save and sign audit behaviour remains unchanged. The header was added to the existing CORS allow-list for the local frontend request path.

Architecture and migration status: NONE. The canonical Django/DRF monolith, service-layer workflow, server-side authorization, tenant/facility boundaries, Encounter/ClinicalNote persistence, ETag contract, and Next.js consultation architecture were reused. No model, endpoint, database column, generated client type, or migration changed. The canonical blueprint and canonical backlog were not modified.

Validation: python -m pytest -q passed 121 tests with 7 documented PostgreSQL-only skips: five PostgreSQL authentication/RLS tests and two PostgreSQL row-lock tests. Focused Phase 1J backend coverage passed 6 tests. Django check reported no issues; makemigrations --check --dry-run reported No changes detected; migrate --plan reported no planned migration operations. Frontend typecheck, lint, and production build passed. Focused Phase 1J Playwright coverage passed 8 tests. The corrected reviewed-normal regression passed in isolation, and the final full authenticated local consultation Playwright file passed 36/36 tests.

Security and verification: verification used synthetic local SQLite development data only. No credentials, seed passwords, secrets, real patient data, PHI, email, SMS, payment, webhook, or other external side effect was used or exposed. No unsafe tracked artifact, local database, browser session state, or runtime artifact was added. No Phase 1K reference was found in the checked frontend/backend source and test scope.

Known limitations: PostgreSQL-only tests were not rerun in this local SQLite-only verification; the existing PostgreSQL owner-role integrity baseline and restricted application-role pytest teardown limitation remain unchanged. Autosave remains intentionally limited to the approved core and does not include the deferred full ENC-015 workflow or automatic retry/backoff.

Files changed for Phase 1J: backend/clinical/services.py, backend/clinical/views.py, backend/clinicopus/settings.py, backend/tests/test_phase_1j.py, frontend/src/app/(app)/consultations/page.tsx, frontend/tests/phase-1d-history.spec.ts, and this handoff document.

Next approved phase: NOT YET AUTHORISED

### Phase 1K — Network Retry + Unsaved Navigation Protection

Status: IMPLEMENTED / VERIFIED / PASS WITH VALIDATION LIMITATION.

Objective: continue ENC-015 by adding bounded retry for transient clinical draft-save failures and protecting in-memory unsaved consultation drafts during reconnects, browser unloads, and patient switches. Phase 1L was not started.

Retryable failure classification: automatic retry applies only to HTTP 5xx ApiRequestError responses and browser network failures represented by TypeError or NetworkError. HTTP 400 validation failures, 401/403 authorization failures, 409 revision conflicts, 428 missing If-Match, signed/closed/cancelled encounters, and other permanent failures stop background retry and remain truthful to the clinician.

Backoff: one consultation-local retry timer uses 2 seconds, 5 seconds, 10 seconds, 20 seconds, and 30 seconds, then continues at the bounded 30-second interval while the draft remains dirty and the failure remains retryable. Editing during retry updates the current React draft and does not create another timer or overlapping mutation.

Connectivity: the offline browser event retains the dirty draft in React memory, shows Not saved — retrying, cancels pending autosave/retry timers, and prevents repeated requests while offline. The online event is only a prompt; it does not prove server reachability. When the encounter is mutable, dirty, unblocked, and idle, one prompt retry uses the normal response/error path and resumes backoff if the request fails.

Persistent unsaved warning: retryable failures remain visibly labelled Not saved — retrying until success, conflict resolution, session/patient change, or a terminal encounter state. Successful responses continue to use the authoritative server saved_at and render Saved HH:MM:SS. Non-retryable failures remain Not saved — use Save draft with the existing truthful error.

Current-draft retry behaviour: every retry builds a dirty-field-only payload from the current draft refs and current dirty-field set, carries the current ETag through If-Match, and carries the existing X-KlinKlik-Autosave marker. Edits made after a failed request are therefore included in the next attempt without freezing the failed payload.

Lost-response reconciliation: the existing 409 response now includes the authoritative saved_at from the current ClinicalNote revision; no model or migration changed. On recovery 409, overlapping fields whose authoritative server content equals the current local dirty value are treated as already applied, adopt the latest content/ETag, clear only still-equal dirty fields, and do not show a false same-field conflict. If all dirty fields match, the draft becomes Saved. Non-overlap changes retain the Phase 1J visible rebase and one retry with the latest ETag/current dirty values.

True conflict behaviour: when an overlapping authoritative value differs from the current local dirty value, the local draft and server comparison remain visible, automatic retry stops, autosave is blocked, and explicit Save draft is required. Further typing does not restart background retry while the conflict remains unresolved. No authorship or provenance inference was added.

Manual Save and sign behaviour: Save draft remains available during retry; it cancels the pending retry timer and uses the current dirty values immediately. A successful manual save clears retry mode and adopts the authoritative saved timestamp. A retryable manual-save failure re-enters bounded retry; a true 409 retains the existing explicit conflict workflow. Sign and draft-save mutations cannot overlap; explicit sign cancels a pending retry timer, uses current dirty values/current ETag, and has no automatic sign retry. Successful sign and terminal states clear retry state and timers.

Patient-switch and unload protection: changing patients with dirty mutable content requires the browser-native confirmation, “This consultation has unsaved changes. Leave and discard them?”. Cancel leaves the patient, draft, retry state, and timer intact. Confirm cancels timers, invalidates the draft session, clears all in-memory draft refs/state, and switches without late writes crossing into the next patient. Section switching remains within the same Encounter and does not warn. beforeunload blocks browser reload/close while dirty using only the native browser mechanism; no PHI is placed in the warning.

Timer/session cleanup: autosave and retry timers are cleared on success, explicit sign, patient switch, terminal encounter state, true conflict, and component unmount. Session and encounter guards reject late responses from an old patient/session.

Audit behaviour: the existing safe autosave audit summarisation remains unchanged. Retries remain autosave-originated, do not create an ordinary ClinicalNote audit event per attempt, and do not add raw clinical text to audit payloads. Rejected requests do not create false success audit events.

Files changed: backend/clinical/concurrency.py, backend/clinical/views.py, backend/tests/test_phase_1j.py, frontend/src/app/(app)/consultations/page.tsx, frontend/tests/phase-1d-history.spec.ts, and this handoff document. No canonical backlog file was changed.

Validation: Django check passed with no issues; makemigrations --check --dry-run reported No changes detected; migrate --plan reported No planned migration operations. Focused Phase 1J backend coverage passed 6 tests in 4.82 seconds. Full backend pytest passed 121 tests with 7 documented PostgreSQL-only skips in 38.43 seconds: five PostgreSQL authentication/RLS tests and two PostgreSQL row-lock tests. Frontend typecheck passed, lint passed, and production build passed. Focused Phase 1K Playwright coverage passed 6 tests in 3.1 minutes. The final full authenticated local consultation Playwright file passed 39 tests in 15.4 minutes.

Migration status: NONE. The only backend adjustment adds saved_at to the existing revision-conflict response needed for authoritative lost-response reconciliation; no model, endpoint workflow, database column, generated client type, or migration was introduced.

Security and verification: verification used synthetic local SQLite development data only. No credentials, seed passwords, secrets, real patient data, PHI, email, SMS, payment, webhook, or other external side effect was used or exposed. No browser PHI persistence was introduced: no localStorage, IndexedDB, offline queue, service worker, background sync, persistent draft cache, or browser session state was added. No unsafe runtime artifact was added to the repository.

Known limitations: retry state is intentionally limited to the active consultation React session; there is no offline recovery after reload/close and navigator.onLine is only a helpful trigger. PostgreSQL-only tests were not rerun in this local SQLite-only verification; the existing PostgreSQL owner-role integrity baseline and restricted application-role pytest teardown limitation remain unchanged. No new blueprint decision was made, and no canonical architecture redesign was performed.

Next approved phase: NOT YET AUTHORISED

### Phase 1K-F — Start Encounter Session Ownership Guard

Status: VERIFIED / PASS.

Objective: protect the active consultation workspace from a late Start Encounter response/error belonging to a prior patient/session while preserving the existing workflow.

Problem and ownership capture: Start Encounter now captures the selected queue-entry ID and current draft session at click time, and sends that captured queue-entry ID to the existing endpoint. A selected queue-entry ref is updated immediately during patient switching so callbacks observe the current identity even before React state rerenders.

Late success behavior: every successful server response still invalidates the queue. Hydration, encounter state, Notes section activation, and stale error clearing occur only when both captured session and current selected queue-entry ID still match. A late Patient-A success after switching to Patient B is ignored and cannot populate B.

Late failure behavior: error display uses the same session and selected queue-entry guard, so a late Patient-A error cannot appear in Patient B’s workspace. Patient switching remains enabled and is not used as a workaround.

Regression coverage: authenticated Playwright coverage uses synthetic local Patient A and Patient B records, delays Patient A’s Start Encounter response, switches to Patient B before completion, confirms B remains selected with no A encounter/note hydration, releases A successfully, and then starts B normally. The existing Phase 1K focused suite and full authenticated consultation regression also passed.

Queue refresh and session safety: stale-session server success still refreshes the consultation queue. No backend or migration change was required; the existing Encounter endpoint and local session/draft protections remain authoritative. No delayed-error browser variant was added because the success race plus guarded error callback is covered by the same ownership logic and static validation.

Files changed: frontend/src/app/(app)/consultations/page.tsx, frontend/tests/phase-1d-history.spec.ts, and this handoff document. No backend file, migration, canonical backlog, or Phase 1L file changed.

Validation: focused Phase 1K-F race test passed 1 test. Focused Phase 1K Playwright suite passed 7 tests. Full authenticated consultation Playwright file passed 40 tests in 12.3 minutes. Frontend typecheck passed, lint passed, and production build passed. Backend checks were not rerun because no backend file or migration changed.

Security and scope: verification used synthetic local SQLite development data only. No real patient data, PHI, credentials, seed passwords, secrets, emails, SMS, payments, webhooks, or other external side effect was used or exposed. No browser PHI persistence was introduced. Phase 1L was not started.

Next approved phase: NOT YET AUTHORISED

### Phase 1K-G — ENC-014 Populated-Only Examination Persistence

Status: VERIFIED / PASS.

Objective: enforce the ENC-014 invariant that only populated findings are stored or represented for the seven existing examination fields, without changing blank semantics for other consultation fields or redesigning the note workflow.

Governed fields: general_examination, cardiovascular_examination, respiratory_examination, abdominal_examination, neurological_examination, genitourinary_examination, and musculoskeletal_examination.

Normalization semantics: a shared backend helper copies incoming content and removes a governed examination key only when its value is a string whose stripped value is empty. Empty strings and whitespace-only strings are therefore absent from stored ClinicalNote.content and signed ClinicalNoteVersion.content. Populated examination text is not trimmed and is stored verbatim. Caller-owned dictionaries are not mutated. Other fields, including hpi, retain their existing blank semantics.

Save and clear behaviour: new-note creation normalizes before persistence, and existing-note saves merge first and then normalize. Clearing a previously saved examination field therefore removes only that JSON key, preserves unrelated content, changes the persisted content/ETag revision, and remains a real mutation.

Signing and amendment behaviour: signing normalizes the complete merged note immediately before creating the immutable version and saving the signed note, including cleanup of legacy blank examination keys. The existing amendment path stores the same normalized content in both the new ClinicalNoteVersion and the amended ClinicalNote. Signature immutability, versioning, and amendment workflow were otherwise unchanged.

Concurrency preservation: If-Match requirements, ETag calculation, 409 revision-conflict status and response shape, stale-content preservation, lost-response reconciliation, and Phase 1K retry behavior were not changed. A stale clear or replacement still receives the existing conflict response and cannot overwrite newer examination content.

Audit preservation: manual clears continue to identify the changed examination field through safe field metadata without previous or new clinical text. Autosave clears continue through the existing ENCOUNTER_DRAFT_UPDATED summary mechanism and do not add raw examination text or a per-attempt ClinicalNote audit event.

Validation: focused Phase 1K-G backend coverage passed 9 tests. Existing Phase 1E–1H examination regressions and Phase 1J backend regressions passed 76 tests. Full backend pytest passed 130 tests with 7 documented PostgreSQL-only skips in 68.30 seconds. Django check reported no issues; makemigrations --check --dry-run reported No changes detected; migrate --plan reported no planned migration operations. The optional browser smoke regression was not run because the checkout does not have the frontend Playwright or Next binaries installed; frontend production code was unchanged.

Security and scope: verification used synthetic local SQLite development data only. No real patient data, PHI, credentials, seed passwords, secrets, email, SMS, payment, webhook, or other external side effect was used or exposed. No frontend production code, model, serializer, migration, canonical backlog, printing path, or Phase 1L work was added.

Files changed: backend/clinical/services.py, backend/tests/test_phase_1k_g.py, and this handoff document. Migration status: NONE.

Next approved phase: NOT YET AUTHORISED

### Phase 1K-H — ENC-015 PATCH / 412 Contract Alignment

Status: IMPLEMENTED / VERIFIED / PASS.

Baseline: e7f99b8b64be0da51a0e961e910dfb914d9c57c3 on main, aligned with origin/main before implementation.

Objective: align the canonical clinical draft-write transport with the ENC-015 PATCH / 412 precondition contract while retaining legacy POST compatibility and preserving the Phase 1J/1K save, conflict, retry, rebase, audit, and session-isolation architecture. Phase 1L was not started.

Canonical draft contract: mutable ClinicalNote draft writes now use PATCH /api/v1/clinic/encounters/{id}/notes/ with If-Match. A current ETag returns 200 with the existing note response and authoritative saved_at plus the ETag response header. Missing If-Match remains 428. A stale PATCH ETag returns 412; its reconciliation body remains the existing exact field set: code, detail, etag, status, encounter_status, content, and saved_at, with the current ETag response header. The legacy POST note handler remains available with identical save semantics and missing-precondition behavior, and a stale POST remains 409. Start Encounter, Sign, and Amend remain POST workflows.

Backend implementation: EncounterNoteView now routes POST and PATCH through one local _save path, the existing NoteWriteSerializer, and the authoritative save_note service. Only the conflict HTTP status is selected by the handler: POST uses 409 and PATCH uses 412. No backend model, serializer workflow, migration, or canonical architecture redesign was introduced. Phase 1K-G examination normalization remains in the shared service path for save, sign, and amend, including populated-only clear semantics.

Frontend contract: the shared consultation draft mutation uses PATCH for both explicit Save draft and autosave. Start Encounter and Sign continue to use POST, and no Amend transport was changed. The conflict parser accepts both legacy 409 and canonical 412 reconciliation responses. A 412 is treated as a non-retryable revision conflict, so the existing true-conflict blocking, explicit-save resolution, non-overlap rebase, retry/backoff, patient/session guards, and signed immutability remain authoritative. Autosave and retry requests retain the existing dirty-field-only body, If-Match header, and X-KlinKlik-Autosave marker.

Conflict and lost-response safety: a PATCH request that reaches the server but loses its response can retry with the stale ETag and receive 412. The existing content-based already-applied reconciliation adopts the authoritative content and latest ETag when it equals the current local dirty value, clears only still-equal dirty fields, and avoids a false same-field conflict. A differing overlapping value remains a true conflict and stops automatic retry. Non-overlap rebase preserves both writers and retries once with the latest ETag/current dirty values.

Audit and privacy: PATCH and legacy POST use the same service audit behavior. Autosave retries remain autosave-originated and do not create an ordinary ClinicalNote audit event per attempt; safe per-Encounter/actor/minute summary semantics remain unchanged and no raw clinical text is added to audit payloads. Verification used synthetic local SQLite development data only. No browser PHI persistence, localStorage, IndexedDB, offline queue, service worker, persistent draft cache, credentials, seed passwords, secrets, real patient data, PHI, email, SMS, payment, webhook, or other external side effect was introduced or exposed. The canonical backlog was not modified.

Files changed: backend/clinical/views.py, backend/tests/test_phase_1k_h.py, frontend/src/app/(app)/consultations/page.tsx, frontend/tests/phase-1d-history.spec.ts, and this handoff document.

Validation: focused Phase 1K-H backend coverage passed 6 tests; Phase 1K-G regression passed 9 tests; Phase 1J regression passed 6 tests. Full backend pytest passed 136 tests with 7 documented PostgreSQL-only skips (5 PostgreSQL authentication/RLS tests and 2 PostgreSQL row-lock tests). Django check reported no issues; makemigrations --check --dry-run reported No changes detected; migrate --plan reported No planned migration operations. Frontend typecheck, lint, and production build passed. Focused Phase 1J/1K Playwright coverage passed 12/12 tests in 3.9 minutes. The full authenticated local consultation Playwright file passed 40/40 tests in 11.3 minutes, including PATCH request assertions, 412 stale-note conflicts, retry/current-draft behavior, manual-save timer cancellation, offline/online behavior, lost-response reconciliation, true-conflict blocking, patient switching, section switching, and Phase 1D-F through 1I consultation regressions.

Migration status: NONE. No database schema, generated client type, or backend endpoint workflow beyond the requested draft-note method/status contract changed.

Known limitations: PostgreSQL-only tests were not rerun in this local SQLite-only verification; the existing PostgreSQL owner-role integrity baseline and restricted application-role pytest teardown limitation remain unchanged. The retry draft remains in React memory only and is intentionally not recoverable after reload or close. No new blueprint decision was made.

Next approved phase: NOT YET AUTHORISED

### Phase 1L-A — ENC-005 Structured Presenting Complaints Backend Foundation

Status: IMPLEMENTED / VERIFIED / PASS WITH VALIDATION LIMITATION.

Baseline: 82c5d946f7ee71c2e051f9cd992d33dfaffc3d79 on main, aligned with origin/main before implementation.

Objective and scope: implement only the backend/API foundation for ENC-005 structured presenting complaints. Phase 1L-B frontend structured-complaint work was not started; no frontend production code or canonical backlog content was changed.

Canonical data: Encounter now stores `complaints` as an ordered JSON list. Each item is canonicalized as `{text, duration_value, duration_unit}`. Text is a nonblank string of at most 500 characters and is preserved verbatim. Duration fields are optional but paired, positive numeric values with units limited to HOURS, DAYS, WEEKS, or MONTHS. Empty drafts are valid as `[]`; no invented maximum duration was added.

Persistence and API: Encounter read responses expose `complaints` and a separate read-only `triage_complaint` sourced from the matching TriageAssessment. Triage is not copied into the consultation complaint list. Note POST and canonical PATCH accept optional structured complaints through the same locked `save_note` transaction. Omitted complaints leave the Encounter value unchanged; explicit `[]` clears it; an explicit list replaces it. Successful note responses include complaints. The existing ETag includes complaints, PATCH stale writes remain 412, legacy POST stale writes remain 409, and both conflict bodies return authoritative current complaints.

Legacy bridge and migration: when structured complaints are omitted, a legacy `content.presenting_complaint` string becomes one structured item (or `[]` when blank) while the legacy ClinicalNote content key remains unchanged. Explicit structured complaints are authoritative. Migration `backend/clinical/migrations/0004_encounter_complaints.py` adds the field and copies a nonblank legacy consultation complaint into empty Encounter.complaints without rewriting ClinicalNote or ClinicalNoteVersion content; its reverse clears the new field. The migration function was directly tested with legacy, blank, and signed-history records.

Signing and state safety: server-side signing requires a nonempty structured complaint or legacy bridge value and returns stable code `PRESENTING_COMPLAINT_REQUIRED` with HTTP 400 when absent. The blocked transaction creates no note version, sign audit, or terminal state. Triage alone never satisfies the rule. Successful signing preserves signed immutability and existing version behavior.

ETag and audit safety: complaint changes use the existing Encounter-first/note-second transaction and revision checks. Generic audit metadata may identify the `complaints` field but never contains complaint text or duration values. Autosave summary behavior remains unchanged and rejected requests do not create false success events.

Security and privacy: verification used synthetic local SQLite development data only. No browser PHI persistence was introduced: no localStorage, IndexedDB, offline queue, service worker, background sync, or persistent draft cache. No raw complaint text was added to generic audit payloads, logs, URLs, or telemetry. No credentials, seed passwords, secrets, real patient data, PHI, email, SMS, payment, webhook, or other external side effect was used or exposed.

Files changed: `backend/clinical/models.py`, `backend/clinical/complaints.py`, `backend/clinical/migrations/0004_encounter_complaints.py`, `backend/clinical/concurrency.py`, `backend/clinical/serializers.py`, `backend/clinical/services.py`, `backend/clinical/views.py`, `backend/tests/test_phase_1l_a.py`, compatibility fixture updates in `backend/tests/test_phase_1c_f.py`, `test_phase_1d_f.py`, `test_phase_1d_f2.py`, `test_phase_1e.py`, `test_phase_1f.py`, `test_phase_1g.py`, `test_phase_1h.py`, `test_phase_1k_g.py`, and `test_vertical_slice.py`, synthetic complaint actions in `frontend/tests/clinic-slice.spec.ts`, `frontend/tests/role-handoff.spec.ts`, `frontend/tests/phase-1d-history.spec.ts`, and this handoff document. No frontend production file changed.

Validation: focused Phase 1L-A backend coverage passed 22 tests. Focused Phase 1K-H, 1K-G, and 1J regressions passed 21 tests. Full backend pytest passed 158 tests with 7 documented PostgreSQL-only skips: five PostgreSQL authentication/RLS tests and two PostgreSQL row-lock tests. Django check reported no issues. `makemigrations --check --dry-run` reported No changes detected. `migrate --plan` reported the expected `clinical.0004_encounter_complaints` AddField plus RunPython operations. The browser consultation smoke was not run: the local frontend dependency tree was incomplete (`@playwright/test`, Next, TypeScript, and ESLint were absent), `npm ci` could not replace a locked native module held by an existing local Next process, and the authorized Chrome control connection also failed before exposing a tab. Frontend production code was unchanged; browser fixture updates were static synthetic actions only.

Known limitations: PostgreSQL-only validation remains limited to the documented skips in this local SQLite environment. The migration has been validated by plan and direct migration-function tests but was not applied to the development database during this implementation turn. Phase 1L-B remains outside scope and unauthorised.

Next approved phase: NOT YET AUTHORISED
### Phase 1L-B — Structured Presenting Complaints UI + Reliability Integration

Status: COMPLETE

Objective: Complete ENC-005 with a structured, ordered presenting-complaint editor integrated with the existing Phase 1J/1K draft-save reliability model.

Implementation:
- Structured `Encounter.complaints[]` editor with ordered rows, verbatim text, 500-character max, paired positive duration value/unit, add/remove/reorder controls, inline validation, and signed read-only rendering.
- Triage complaint remains separately visible as context; only an explicit `Copy from triage` appends a new complaint. No NLP or automatic copy was introduced.
- Legacy `content.presenting_complaint` remains historical and is not actively written or synchronised by the new UI.
- Complaint-only dirty state uses the same in-memory dirty/save/retry/session isolation protections as clinical note fields.
- Complaint-only autosave/manual save sends `{content:{}, complaints:[...]}` with current ETag and autosave marker only for autosave; invalid rows do not send requests.
- Current complaint drafts are used for retries; in-flight newer edits remain dirty and are preserved.
- 409/412 reconciliation adopts already-applied identical authoritative content without a false conflict, preserves true structured conflicts for explicit resolution, and retains non-overlap rebase behavior.
- Offline/online retry, bounded backoff, beforeunload, patient-switch confirmation, timer/session cleanup, sign gating, signed immutability, and safe autosave audit summarisation remain in-memory and session-scoped.
- No browser PHI persistence was introduced.

Validation:
- Focused Phase 1L-B Playwright: 20 passed.
- Existing Phase 1J/1K consultation regressions: 12 passed.
- Existing History persistence regressions: 2 passed after aligning stale POST assertions and complaint locators with the established PATCH endpoint and structured editor.
- Focused Phase 1L-A/1K/1J backend: 43 passed.
- Full backend suite: 158 passed, 7 skipped (PostgreSQL-only checks).
- Django check, makemigrations --check --dry-run, migrate --plan: PASS; no new migration.
- Frontend typecheck, lint, production build: PASS.
- Migration file status: NONE; pre-existing Phase 1L-A migration was applied to local SQLite for verification only.

Files changed:
- `frontend/src/features/clinic/types.ts`
- `frontend/src/app/(app)/consultations/page.tsx`
- `frontend/tests/phase-1l-b-complaints.spec.ts`
- `frontend/tests/phase-1b-history.spec.ts`
- `frontend/tests/phase-1c-history.spec.ts`
- `docs/REPO_REVIEW_HANDOFF.md`

Known limitations:
- Browser connectivity events are advisory; server reachability remains authoritative.
- Drafts remain React memory only and are lost on full tab close/reload after any native browser warning is dismissed.
- Existing PostgreSQL-only checks were skipped because local verification uses SQLite.

ENC-005 status: COMPLETE

Next approved phase: NOT YET AUTHORISED

### Phase 1M-A — Patient Allergy State + Encounter Review Backend Foundation

Status: COMPLETE

Objective:

- Establish the patient-level allergy-state backend foundation for ENC-011 and the shared encounter review prerequisite for TRI-004.
- Keep this slice backend-only. No allergy banner UI, triage redesign, prescribing, CDS, medication workflow, or Phase 1M-B work was started.

Model and state semantics:

- The existing facility-scoped Allergy model was reused and evolved; no competing allergy-detail model was introduced.
- PatientAllergyState is explicit and unique per organisation, facility, and patient. An absent state row is interpreted as NOT_RECORDED; encounter reads do not eagerly create a row.
- Supported state values are NOT_RECORDED, NKA, UNKNOWN, and RECORDED.
- NKA and UNKNOWN are explicit acknowledgements and cannot coexist with active allergy rows.
- Recorded allergies remain Allergy rows with substance, optional reaction, and canonical severity values MILD, MODERATE, or SEVERE.
- Allergy rows use ACTIVE and ENTERED_IN_ERROR. Entering an allergy in error preserves the row and stores the reason, actor, and timestamp; it is excluded from the active encounter banner.
- NKA and UNKNOWN do not create fake allergy rows. Entering the last active allergy in error produces NOT_RECORDED, never inferred NKA.
- Patient allergy-state revision increments on every authoritative status, add, and entered-in-error mutation.

Review freshness and signing:

- Encounter stores allergies_reviewed_at, allergies_reviewed_by, and allergies_reviewed_revision.
- Review is encounter-specific and current only when the review revision equals the current patient allergy revision.
- Signing now blocks with ALLERGY_STATUS_REQUIRED, ALLERGY_REVIEW_REQUIRED, or ALLERGY_REVIEW_STALE as appropriate.
- Rejected signing creates no note version, terminal encounter state, or sign audit event. The existing presenting-complaint prerequisite remains authoritative after allergy prerequisites pass.
- Signed encounters cannot be re-reviewed, while the patient allergy state may be updated later; that correctly makes prior reviews stale.

API surface:

- POST /api/v1/clinic/patients/{patient_id}/allergies/ records an active allergy and returns the state ETag/revision.
- POST /api/v1/clinic/patients/{patient_id}/allergy-status/ accepts only NKA or UNKNOWN.
- POST /api/v1/clinic/patients/{patient_id}/allergies/{allergy_id}/entered-in-error/ requires a nonblank reason.
- POST /api/v1/clinic/encounters/{encounter_id}/allergies/review/ records the current state revision with no PHI request body.
- Encounter reads expose allergy_status, active allergy details (id, substance, reaction, severity), allergy revision/ETag, review timestamp/revision, and allergies_review_is_current. Entered-in-error details are not included in the normal active banner.
- Status, entered-in-error, and review mutations require If-Match; transactions lock the patient/state/affected records. The consultation ETag was not changed.
- allergy.manage is granted to NURSE_TRIAGE and CLINICIAN, not RECEPTION_CASHIER. Review uses clinical.note.sign.

Migration:

- Added backend/clinical/migrations/0005_allergy_entered_in_error_at_and_more.py.
- Existing scopes containing ACTIVE allergy rows are reconciled to RECORDED, revision 1.
- Patients with no allergy rows remain absent from PatientAllergyState and therefore NOT_RECORDED. No NKA or UNKNOWN state is inferred.
- makemigrations --check --dry-run: PASS (No changes detected).
- migrate --plan: PASS; the migration includes the model/field changes and the reconciliation operation.

Audit and safety:

- Allergy mutations and encounter reviews are audited with safe metadata only.
- Audit records contain field names, state/revision metadata, and a boolean reason_recorded marker; substance, reaction, severity, and the entered-in-error reason are not written to generic audit JSON.
- No automatic drug/allergy matching or CDS was introduced.
- No browser PHI persistence was introduced. No localStorage, IndexedDB, service worker, offline queue, or persistent draft store was added.

Tests and validation:

- Focused Phase 1M-A backend suite: 24 passed.
- Full backend suite: 182 passed, 7 skipped (PostgreSQL-only authentication and row-lock checks).
- Existing Phase 1J, Phase 1K, Phase 1L-A, vertical-slice, signing, permissions, audit, and consultation regression coverage passed.
- Django check: PASS.
- Frontend production code and frontend production validation were not changed or required for this backend-only slice.
- No Playwright tests were added because Phase 1M-A is explicitly backend-only.

Files changed:

- backend/accounts/services.py
- backend/clinical/models.py
- backend/clinical/allergies.py
- backend/clinical/migrations/0005_allergy_entered_in_error_at_and_more.py
- backend/clinical/serializers.py
- backend/clinical/services.py
- backend/clinical/views.py
- backend/clinical/urls.py
- backend/tests/clinical_test_helpers.py
- Existing sign/consultation regression fixtures in backend/tests/
- backend/tests/test_phase_1m_a.py
- backend/tests/test_session_roles_and_invoice_lookup.py
- backend/tests/test_vertical_slice.py

Known limitations:

- PostgreSQL-only RLS/row-lock tests remain environment-skipped locally; the service uses transaction boundaries, patient row locks, state row locks, and ETags for the production concurrency path.
- The allergy banner and clinician review workflow UI remain for Phase 1M-B and were not started.
- No clinical interpretation, medication, prescribing, or CDS behavior is included.

ENC-011 backend: COMPLETE

TRI-004 shared backend: READY FOR UI

Next approved phase: NOT YET AUTHORISED

### Phase 1M-B — Clinician Allergy Banner + Review Workflow

Status: COMPLETE

Objective:

- Complete ENC-011 clinician-facing allergy visibility and the encounter-specific review workflow in the consultation workspace.
- Keep the implementation frontend-only on top of the Phase 1M-A backend contract; do not start triage redesign, prescribing, medication matching, CDS, or Phase 1N.

Banner and workflow:

- A reusable consultation allergy banner is visible across Summary, History, Examination, and Notes after an encounter is selected.
- NOT_RECORDED, NKA, UNKNOWN, and RECORDED states render explicit, safe clinician-facing status text.
- Active allergies render substance, reaction when present, and severity; multiple active allergies remain visible together.
- Clinicians can record NKA/UNKNOWN only when no active allergy exists, add multiple active allergies, and enter an active allergy in error with a required reason. No allergy row is deleted.
- Review is a separate encounter action. The banner distinguishes current review from stale/unreviewed state and exposes the review action only while the encounter is mutable.
- No automatic drug matching, interpretation, CDS, medication suggestion, or triage redesign was introduced.

Concurrency and session safety:

- Status, entered-in-error, and review mutations send the current If-Match value; each successful response becomes the authoritative local snapshot.
- 412 responses adopt the server-provided allergy snapshot and ETag, show a safe review message, and do not replay the stale mutation.
- Patient/encounter/session guards prevent late responses from changing a different patient’s banner or review state.
- Signing is blocked locally until allergy status is explicit and the encounter review is current; server allergy prerequisite codes map to safe clinician copy. Signing remains explicit and is not automatically retried.
- Signed, closed, and cancelled encounters render the banner read-only. Existing clinical note conflict, autosave, dirty-state, and signed-immutability behavior remains authoritative.

Navigation and safety:

- Allergy form dirtiness participates in the existing patient-switch confirmation and beforeunload protection.
- Section switching does not discard the in-memory allergy form or consultation draft.
- Confirmed patient changes invalidate the session and clear the current in-memory draft; cancelled changes preserve it.
- No browser PHI persistence was introduced. No localStorage, IndexedDB, service worker, offline queue, or persistent draft store was added.

Validation:

- Focused Phase 1M-B Playwright: 12 passed.
- Existing Phase 1L-B complaint regression: 18 passed in the full run; the two sign-fixture cases passed in a subsequent targeted rerun after adding the required allergy-review precondition.
- Full vertical consultation Playwright: 1 passed after aligning the stale examination expectation and establishing the required allergy-review precondition in the synthetic fixture.
- Existing Phase 1J/1K consultation reliability regressions: PASS.
- Backend production checks from the Phase 1M-A foundation: 182 passed, 7 skipped (PostgreSQL-only authentication/RLS and row-lock checks); Django check, makemigrations --check --dry-run, and migrate --plan: PASS.
- Frontend typecheck, lint, and production build: PASS.
- Migration status: NONE for Phase 1M-B. No backend production source or migration was changed.

Files changed:

- `frontend/src/features/clinic/types.ts`
- `frontend/src/components/clinical/allergy-banner.tsx`
- `frontend/src/app/(app)/consultations/page.tsx`
- `frontend/tests/phase-1m-b-allergies.spec.ts`
- `frontend/tests/phase-1l-b-complaints.spec.ts` (synthetic sign fixtures aligned with the new allergy prerequisite)
- `frontend/tests/clinic-slice.spec.ts` (current examination expectation and synthetic allergy prerequisite)
- `docs/REPO_REVIEW_HANDOFF.md`

Known limitations:

- Browser connectivity and server responses remain authoritative; no offline completion or persistent recovery queue exists.
- Local authenticated Playwright verification uses only the existing synthetic development fixture and local SQLite. PostgreSQL-only checks remain environment-skipped.
- The allergy workflow is wired to consultation only. TRI-004 triage UI, prescribing, drug matching, CDS, and other clinical modules remain outside this slice.

ENC-011: COMPLETE

TRI-004 shared backend: READY FOR TRIAGE UI

No browser PHI persistence was introduced.

Next approved phase: NOT YET AUTHORISED

### Phase 1N-A — Working + Final Diagnosis Backend Foundation

Status: COMPLETE / PASS WITH VALIDATION LIMITATION.

Baseline: `64866f2b74fd4af2e2045379bbf59e8f30a0586c` on `main`, aligned with `origin/main` before implementation.

Objective and scope: implement the backend foundation for ENC-015 diagnosis capture using the existing facility-scoped `clinical.Diagnosis` model. The model was evolved in place; no competing diagnosis model, catalogue workflow, reporting, printing, CDS, treatment, medication, or Phase 1N-B functionality was introduced. Frontend production code was not changed.

Diagnosis state contract:

- Supported diagnosis types are `WORKING`, `FINAL`, and `NO_DIAGNOSIS`.
- Working and final entries require a non-blank label. Code is optional and remains a verbatim snapshot; `coded` is derived from a non-blank code. Certainty notes are optional verbatim snapshots.
- Working diagnoses cannot be primary. Active final diagnoses may have at most one primary entry per Encounter through service validation and a conditional database uniqueness constraint.
- No-diagnosis entries clear code, label, coded, certainty, and primary state and require a non-whitespace reason. Active `NO_DIAGNOSIS` is mutually exclusive with active `FINAL`; working entries may coexist with final entries and the sign gate ignores working-only state.
- Diagnosis rows are never physically deleted. Removal records `REMOVED`, actor, timestamp, and clears primary state; active serializers, Encounter reads, and signing exclude removed rows.

API and concurrency:

- Added scoped GET/POST `/api/v1/clinic/encounters/{id}/diagnoses/`, PATCH `/api/v1/clinic/encounters/{id}/diagnoses/{diagnosis_id}/`, and POST `/api/v1/clinic/encounters/{id}/diagnoses/{diagnosis_id}/remove/` endpoints.
- Diagnosis mutations require the existing `clinical.note.create` capability, so receptionist/cashier and triage-only roles cannot mutate diagnoses. Organisation and facility scope is enforced server-side.
- All diagnosis mutations require `If-Match`. Successful mutations return authoritative active `diagnoses`, `consultation_etag`, and an `ETag` header. Stale writes return HTTP 412 with the current active diagnosis state and latest consultation ETag.
- Consultation ETags now include only diagnosis revision metadata: row ID, type, status, primary flag, and `updated_at`, wrapped in the existing HMAC opaque ETag. No diagnosis text is placed in the ETag payload.
- Existing note autosave 412/409 reconciliation bodies retain their prior fields and now include authoritative active `diagnoses`.

Signing and audit safety:

- Signing preserves the existing allergy-state/review and presenting-complaint prerequisites, then requires either active final diagnosis entries with exactly one primary or exactly one active no-diagnosis entry with a non-blank reason and zero active finals. Working-only state returns `DIAGNOSIS_REQUIRED`; missing primary returns `PRIMARY_DIAGNOSIS_REQUIRED`; invalid primary/state combinations return `PRIMARY_DIAGNOSIS_INVALID` or `DIAGNOSIS_STATE_INVALID`.
- Diagnosis mutations are rejected after `SIGNED`, `CLOSED`, or `CANCELLED` encounter state (and after signed/amended consultation-note state). Failed sign validation leaves the Encounter open, creates no ClinicalNoteVersion, and creates no sign audit event.
- Diagnosis create/edit/remove audit events contain only safe state metadata such as type, coded flag, primary flag, status, and Encounter ID. Labels, codes, certainty notes, no-diagnosis reasons, and full diagnosis JSON are not written to generic audit payloads.
- No browser PHI persistence was introduced: no localStorage, IndexedDB, service worker, offline queue, background sync, or persistent draft cache.

Legacy migration:

- `backend/clinical/migrations/0006_diagnosis_certainty_note_diagnosis_coded_and_more.py` adds the typed fields, soft-removal metadata, conditional uniqueness constraints, and a deterministic reconciliation step before constraints. Existing active legacy rows retain code and label verbatim, become `FINAL`, derive `coded` from code presence, and receive one deterministic primary per Encounter when none existed. ClinicalNote or ClinicalNoteVersion content is not rewritten.

Files changed:

- `backend/clinical/models.py`
- `backend/clinical/diagnosis_state.py`
- `backend/clinical/diagnoses.py`
- `backend/clinical/concurrency.py`
- `backend/clinical/serializers.py`
- `backend/clinical/services.py`
- `backend/clinical/views.py`
- `backend/clinical/urls.py`
- `backend/clinical/migrations/0006_diagnosis_certainty_note_diagnosis_coded_and_more.py`
- `backend/tests/clinical_test_helpers.py`
- `backend/tests/test_phase_1n_a.py`
- Existing synthetic signing fixtures in `backend/tests/` were explicitly given a synthetic primary final diagnosis and refreshed ETags; no production frontend fixtures or frontend production code changed.
- `docs/REPO_REVIEW_HANDOFF.md`

Tests and validation:

- Focused Phase 1N-A backend suite: 14 passed.
- Affected consultation/signing regression suite: 156 passed, 2 PostgreSQL-only row-lock tests skipped.
- Full backend pytest suite: 196 passed, 7 skipped. Skips are the existing five PostgreSQL authentication/RLS tests and two PostgreSQL row-lock tests.
- Django check: PASS.
- `makemigrations --check --dry-run`: PASS; No changes detected.
- `migrate --plan`: PASS; expected `clinical.0006_diagnosis_certainty_note_diagnosis_coded_and_more` field, data-reconciliation, and conditional-constraint operations are planned.
- Ruff was not available in the local runtime (`ruff` executable and Python module were absent); no configured lint result is claimed for this backend-only phase.
- Frontend typecheck, lint, production build, and Playwright were not rerun because this slice made no frontend production changes. No frontend production file changed.

Architecture and decision boundary:

- Business rules remain in the explicit `clinical.diagnoses` service module; views authorize/orchestrate, serializers validate request shape, and models persist local invariants.
- Tenant/facility scope, append-only audit behavior, signed immutability, and opaque HMAC ETags remain authoritative. The canonical backlog was not modified.
- Blueprint OD-C4 describes mandatory diagnosis before sign-off as an open clinical decision. The explicit Phase 1N-A authorization applies that prerequisite only for this approved slice; it does not silently resolve or generalize the broader blueprint decision beyond this phase.
- DX-001 backend: COMPLETE. DX-002 backend: COMPLETE.

Known limitations:

- PostgreSQL/RLS and PostgreSQL row-lock execution remain environment-skipped in this local SQLite validation; the code retains the existing transaction/lock architecture and requires PostgreSQL verification before infrastructure approval.
- Diagnosis snapshots are intentionally active-only in normal API/Encounter responses; removed history is retained in the database but has no Phase 1N-A history endpoint.
- Phase 1N-B frontend work remains outside this slice and unauthorised.

No browser PHI persistence was introduced.

Canonical backlog changed: NO.

Frontend production changed: NO.

Phase 1N-B started: NO.

Next approved phase: NOT YET AUTHORISED

### Phase 1N-A-F — Working + NO_DIAGNOSIS Symmetry Fix

Status: COMPLETE / PASS.

Baseline: `0f058875de4513b00b498d715aea74fe3588f8a5` on `main`, aligned with `origin/main` before this correction.

Objective and scope: correct the Phase 1N-A diagnosis exclusivity symmetry without changing the model, API shape, ETag architecture, signing architecture, or frontend. WORKING diagnoses may coexist with one active `NO_DIAGNOSIS` entry in either creation/edit order; active FINAL plus active `NO_DIAGNOSIS` remains forbidden.

Diagnosis rules verified:

- WORKING then NO_DIAGNOSIS and NO_DIAGNOSIS then WORKING both succeed with both entries active.
- Multiple WORKING entries may coexist with one active NO_DIAGNOSIS entry.
- FINAL then NO_DIAGNOSIS and NO_DIAGNOSIS then FINAL remain blocked.
- WORKING to NO_DIAGNOSIS is allowed while other WORKING entries exist; NO_DIAGNOSIS to WORKING is allowed with the required label; WORKING to FINAL remains blocked when NO_DIAGNOSIS is active.
- NO_DIAGNOSIS to FINAL is allowed when the current entry is the only no-diagnosis entry and normal final/primary rules are satisfied. FINAL to NO_DIAGNOSIS remains blocked when another active FINAL exists.
- The exclusivity check remains transactionally enforced and all primary-final uniqueness checks are preserved.

Signing, concurrency, and audit safety:

- A valid active state containing WORKING plus one reason-bearing NO_DIAGNOSIS satisfies the existing sign prerequisite after valid presenting complaint, current allergy review, and consultation ETag checks; signing creates exactly one ClinicalNoteVersion and makes the Encounter SIGNED.
- Existing ETag behavior, soft removal, primary uniqueness, signed immutability, tenant/facility scoping, and diagnosis audit metadata safety remain covered by the Phase 1N-A suite. No raw diagnosis label, code, certainty note, or no-diagnosis reason is added to audit metadata.
- No browser PHI persistence was introduced.

Files changed:

- `backend/clinical/diagnoses.py`
- `backend/tests/test_phase_1n_a.py`
- `docs/REPO_REVIEW_HANDOFF.md`

Tests and validation:

- Focused Phase 1N-A suite: 17 passed.
- Phase 1M-A allergy suite: 24 passed.
- Full backend pytest suite: 199 passed, 7 skipped. Skips are the existing five PostgreSQL authentication/RLS tests and two PostgreSQL row-lock tests.
- Django check: PASS; no issues identified.
- `makemigrations --check --dry-run`: PASS; No changes detected.
- Migration: NONE expected; no model or migration file changed.

Scope and decision boundary:

- Canonical backlog changed: NO.
- Frontend production changed: NO.
- Phase 1N-B started: NO. No frontend diagnosis UI was implemented.
- The existing local SQLite validation limitation remains: PostgreSQL/RLS and PostgreSQL row-lock execution require the project PostgreSQL environment.

Ready for review: YES.

Next approved phase: NOT YET AUTHORISED
### Phase 1N-B — Working + Final Diagnosis Clinician Workflow

Status: COMPLETE / PASS.

Baseline: 8d4ea8fa6c8ce6e3b4e594a6601cbdba65a89c04 on main, aligned with origin/main before implementation.

Objective and scope: complete the clinician-facing diagnosis workflow for ENC-015 using the Phase 1N-A backend foundation. This slice adds only the consultation Diagnosis section and its frontend coordination; treatment, prescriptions, laboratory workflows, reports, printing, CDS, suggestions, catalogue search, and Phase 1O work remain outside scope.

Clinician workflow:

- Added a real Diagnosis consultation section with separate WORKING, FINAL, and NO_DIAGNOSIS forms.
- Working and final diagnoses support free-text labels, optional manual code snapshots, and optional certainty notes where applicable. No catalogue or diagnostic suggestion behavior was introduced.
- Multiple active final diagnoses are supported with an explicit single-primary control. Working diagnoses can be explicitly promoted to final. Existing entries can be edited or soft-removed through the Phase 1N-A API.
- NO_DIAGNOSIS requires an explicit reason and remains compatible with working diagnoses. Invalid or mutually exclusive combinations are blocked with safe clinician-facing validation.
- The form is memory-only, survives History/Examination/Notes section switching, and becomes read-only for signed, closed, or cancelled encounters.

Concurrency and conflict safety:

- Diagnosis mutations use the existing authoritative consultation ETag and If-Match flow. Diagnosis mutation success adopts the returned active diagnosis snapshot and latest ETag before note autosave can resume.
- Stale diagnosis mutations map 412 responses safely. A clean form adopts the authoritative diagnosis snapshot; a dirty form is rebased against the latest encounter state while preserving current local form input. The stale diagnosis mutation is never automatically replayed.
- Existing note autosave/sign conflict responses now adopt authoritative diagnoses as part of the consultation snapshot. Non-overlapping note changes remain preserved, while overlapping diagnosis state is not silently overwritten.
- Only one consultation mutation owns the shared ETag at a time. Diagnosis actions coordinate with note save/sign and Phase 1J/1K autosave and retry state.

Signing and immutability:

- Client-side sign guards require a valid final diagnosis with one primary or a valid explicit no-diagnosis state; working-only and final-without-primary states remain blocked.
- Sign remains an explicit action and is not automatically retried. Diagnosis mutation, note save, and sign requests cannot overlap.
- After signing, diagnosis controls and forms are read-only. Existing signed/closed/cancelled immutability remains authoritative.

Navigation and session safety:

- Unsaved diagnosis form state participates in patient-switch confirmation and the browser-native beforeunload warning without putting PHI into the warning.
- Cancelling a patient switch keeps the current patient, diagnosis form, and in-memory consultation state. Confirming discards the in-memory state, invalidates the session, and prevents late responses from writing into the next patient.
- Section switching does not warn or discard the shared consultation state. No browser PHI persistence was introduced.

Audit and security:

- No backend production source, audit schema, or migration was changed in Phase 1N-B. Existing Phase 1N-A diagnosis audit semantics remain authoritative.
- No raw diagnosis content was added to audit payloads by the frontend. No localStorage, sessionStorage, IndexedDB, service worker, offline queue, background sync, or persistent draft cache was introduced.
- The canonical backlog was not modified.

Files changed:

- frontend/src/app/(app)/consultations/page.tsx
- frontend/src/features/clinic/types.ts
- frontend/src/components/clinical/diagnosis-section.tsx
- frontend/tests/phase-1n-b-diagnoses.spec.ts
- frontend/tests/phase-1m-b-allergies.spec.ts (synthetic signing prerequisite fixture)
- frontend/tests/phase-1l-b-complaints.spec.ts (synthetic signing prerequisite and reconnect timing fixture)
- frontend/tests/clinic-slice.spec.ts (synthetic signing prerequisite fixture)
- docs/REPO_REVIEW_HANDOFF.md

Tests and validation:

- Focused Phase 1N-B Playwright: 10 passed.
- Relevant consultation Playwright regressions: 33 passed.
- Focused Phase 1N-A/M-A/L-A backend suites: 63 passed.
- Full backend pytest suite: 199 passed, 7 skipped. The skips are the existing PostgreSQL-only authentication/RLS and row-lock checks.
- Django check: PASS.
- makemigrations --check --dry-run: PASS; no changes detected.
- migrate --plan: PASS; it identified the pre-existing Phase 1N-A clinical.0006_diagnosis_certainty_note_diagnosis_coded_and_more migration. The local development SQLite database required that existing migration to be applied for authenticated UI verification; no Phase 1N-B migration was added.
- Frontend typecheck: PASS.
- Frontend lint: PASS.
- Frontend production build: PASS.
- git diff --check: PASS.

Known limitations:

- Diagnosis codes remain clinician-entered snapshots; diagnosis catalogue/search, coding validation, suggestions, and clinical decision support are intentionally deferred.
- PostgreSQL/RLS and PostgreSQL row-lock checks remain environment-skipped in the local validation environment.
- The consultation diagnosis workflow is limited to the approved Phase 1N-B slice; no treatment, prescriptions, laboratory, reports, printing, or other clinical modules were started.

No browser PHI persistence was introduced.

Phase 1O started: NO.

Next approved phase: NOT YET AUTHORISED
### Phase 1N-B-F — Edit-Form Primary Switch Fix

Status: COMPLETE / PASS.

Baseline: 99923130e3ebd864b275e148141d5514a84ead32 on main, aligned with origin/main before this correction.

Objective and scope: correct the edit-form switch from a secondary FINAL diagnosis to primary without changing backend production, the diagnosis model/API, ETag architecture, signing rules, soft removal, NO_DIAGNOSIS, allergy workflows, complaint workflows, or other clinical scope.

Fix:

- When an edited secondary FINAL diagnosis is submitted as primary while another FINAL diagnosis is primary, the existing primary is patched first with diagnosis_type FINAL and is_primary false.
- The existing authoritative mutation flow adopts the response diagnoses and fresh consultation ETag before the edited target is patched.
- The edited target is patched once with the complete edited payload, diagnosis_type FINAL, is_primary true, and the fresh ETag. No old ETag is reused and no duplicate target PATCH is sent.
- If demotion fails, the edit flow does not claim success; existing safe error handling and authoritative state remain in force.

Regression coverage:

- Added a focused Playwright regression that creates primary A and secondary B, edits B, changes its label, promotes it through the edit form, asserts exactly two relevant PATCH requests in demotion-then-promotion order, verifies distinct If-Match values, confirms the edited payload survives, checks visible Primary/Secondary state, and rejects PRIMARY_DIAGNOSIS_INVALID.
- Existing Make-primary behavior remains unchanged and passes.

Tests and validation:

- Focused edit-form regression: 1 passed.
- Full focused Phase 1N-B Playwright: 11 passed with one retry permitted for local startup authentication.
- Relevant consultation Playwright regressions: 33 passed.
- Phase 1N-A backend suite: 17 passed.
- Frontend typecheck: PASS.
- Frontend lint: PASS.
- Frontend production build: PASS.
- git diff --check: PASS.
- Migration: NONE.

Files changed:

- frontend/src/app/(app)/consultations/page.tsx
- frontend/tests/phase-1n-b-diagnoses.spec.ts
- docs/REPO_REVIEW_HANDOFF.md

Scope and safety:

- Backend production changed: NO.
- Canonical backlog changed: NO.
- No browser PHI persistence was introduced.
- No runtime artifact is included in the commit.
- Phase 1O started: NO.

Known limitations:

- The local authenticated Playwright environment can emit expected initial refresh 401 responses and required one retry during a startup-authentication flake; the authoritative retry run passed all focused tests.
- Existing PostgreSQL-only validation limitations remain unchanged.

Ready for review: YES.

Next approved phase: NOT YET AUTHORISED

### Phase 1N-B-F2 — Clean Diagnosis-412 Authoritative Refresh

Status: COMPLETE / PASS.

Baseline: c3970b793d81f82d3623ccf5158e435e66bc0216 on main, aligned with origin/main before this correction.

Objective and scope: ensure every current-session diagnosis 412 response refreshes the complete authoritative Encounter before shared consultation state is adopted. This correction covers clean HPI and presenting-complaint refresh, diagnosis snapshot refresh, ETag alignment, dirty-draft reconciliation, and delayed-response session isolation. No Phase 1O work was started.

Implementation:

- Every current diagnosis 412 now performs an authoritative Encounter GET before adopting diagnoses or the shared consultation ETag. The response must contain the current Encounter, patient, queue entry, consultation ETag, and diagnosis snapshot for adoption.
- The refresh adopts authoritative ClinicalNote content, presenting complaints, diagnoses, encounter status, and consultation ETag together. Clean HPI and complaint drafts visibly update without a conflict comparison panel and without replaying the rejected diagnosis command.
- A later note edit uses the refreshed ETag. A dirty HPI or complaint remains local, the authoritative server value remains visible for reconciliation, autosave remains blocked, and the stale diagnosis command is not replayed.
- If the authoritative GET fails or is incomplete, no new ETag is adopted and no diagnosis replay occurs. Autosave is stopped in an uncertain state and the clinician is told to reload before trying the diagnosis change again.
- Existing patient, encounter, queue, and current-mutation session guards prevent a delayed refresh from applying to another patient session.

Tests and validation:

- Focused Phase 1N-B-F2 Playwright: 5 passed.
- Existing diagnosis primary-switch/edit regressions: 2 passed.
- Relevant consultation, complaint, and allergy Playwright regressions: 32 passed in the combined run; one existing NKA review test had a local UI timing flake and passed when rerun in isolation (33 effective passes).
- Phase 1N-A backend suite: 17 passed.
- Frontend typecheck: PASS.
- Frontend lint: PASS.
- Frontend production build: PASS.
- Django check: PASS.
- makemigrations --check --dry-run: PASS; no changes detected.
- migrate --plan: PASS; no planned migration operations.
- git diff --check: PASS.

Files changed:

- frontend/src/app/(app)/consultations/page.tsx
- frontend/tests/phase-1n-b-diagnoses.spec.ts
- docs/REPO_REVIEW_HANDOFF.md

Security and scope:

- Backend production changed: NO. Migration: NONE.
- No browser PHI persistence was introduced. No localStorage, sessionStorage, IndexedDB, service worker, offline queue, background sync, or persistent draft cache was added.
- Verification used synthetic local development data only. No credentials, secrets, real patient data, PHI, or external side effects were used or exposed.
- Canonical backlog changed: NO. Runtime artifacts changed: NO. Phase 1O started in this Phase 1N-B-F2 slice: NO.

Known limitations:

- The relevant combined Playwright run exposed one pre-existing local UI timing flake in the NKA review test; the isolated rerun passed. PostgreSQL-only checks remain environment-dependent as recorded in the prior handoff.

Ready for review: YES.

Next approved phase: NOT YET AUTHORISED

### Phase 1O-A — Treatment Plan Backend Foundation

Status: COMPLETE / PASS (backend-only foundation; ready for review).

Objective and canonical basis:

- DX-004 canonical wording was inspected. This slice implements only the bounded free-text treatment-plan foundation for an Encounter.
- The later structured prescription, procedure, investigation/LAB, referral, and follow-up items, patient-copy printing, reporting, and UI remain outside this slice.

Storage and validation:

- Treatment-plan text is stored in the existing `ClinicalNote.content["treatment_plan"]` JSON field; no new model or migration was introduced.
- Existing `NoteWriteSerializer` validation now accepts a string up to 4000 characters and preserves multiline text exactly. Non-string and over-limit values are rejected.
- Existing consultation PATCH behavior is reused, including dirty-field payload handling and authoritative saved response data.

Concurrency and signing:

- Treatment-plan changes participate in the existing consultation ETag, If-Match, stale-revision 412 response, authoritative conflict content, and conflict-field detection.
- A stale treatment-plan PATCH returns 412 and is not replayed automatically.
- The existing sign flow snapshots the exact treatment plan into `ClinicalNoteVersion`; later treatment-plan mutation is blocked by signed immutability.

Audit and security:

- Generic ClinicalNote audit metadata records that `treatment_plan` changed without storing the raw treatment text.
- No browser PHI persistence, frontend production code, offline queue, CDS, diagnosis suggestion, printing, or external side effect was introduced.

Validation:

- Focused Phase 1O-A backend tests: PASS — 4 passed.
- Diagnosis, allergy, complaint, concurrency, autosave, and retry regressions: PASS — 85 passed.
- Full backend suite: PASS — 203 passed, 7 expected PostgreSQL-only skips.
- Django check: PASS.
- `makemigrations --check --dry-run`: PASS; no changes detected.
- `migrate --plan`: PASS; no planned migration operations.
- Migration status: NONE.

Files changed:

### Phase 1O-B — Final Verification/Reconciliation Gate

Status: COMPLETE / PASS — DX-004 treatment-plan foundation and frontend workflow are ready for review.

Scope and implementation:

- The approved slice adds only the bounded free-text Treatment section to the existing consultation workspace.
- Treatment text uses the existing ClinicalNote content contract, dirty-field-only submission, autosave/manual-save/retry machinery, If-Match consultation ETag, conflict handling, session guards, signed read-only state, and patient-switch protection.
- The frontend production implementation was already present in the Phase 1O-B working tree; no frontend production correction was required during this final reconciliation.
- Backend production source was not changed. No migration was introduced.

Initial legacy consultation failure reconciliation:

- Initial legacy failures: 20.
- Stale test expectations: 6. These were two obsolete exact complaint-label selectors and four obsolete transient Consultation draft saved. assertions while newer dirty edits were still pending.
- Fixture prerequisite gaps: 9. These were sign scenarios missing the current complaint, allergy-status/review, and final-diagnosis or NO_DIAGNOSIS prerequisites.
- Real product regressions: 0.
- Timing/infrastructure issues: 5. These covered debounce/autosave/request sequencing, patient-switch timing, and retry timer timing.
- The initial Phase 1O-B focused run also exposed test-only timing races; paused fake-clock/request-gating corrections made those scenarios deterministic.
- No production code fix was required.

Test-only reconciliation updates:

- frontend/tests/phase-1b-history.spec.ts: added the current synthetic sign prerequisites.
- frontend/tests/phase-1c-history.spec.ts: added the current synthetic sign prerequisites.
- frontend/tests/phase-1d-history.spec.ts: aligned selectors and status expectations with current behavior, added sign prerequisites, and stabilized request/timer/session sequencing without weakening assertions.
- frontend/tests/phase-1o-b-treatment-plan.spec.ts: added fake-clock stabilization for patient switching and the existing retry/rebase timing cases.
- No raw credentials, PHI, or runtime artifacts were added.

Final validation:

- Previously failing legacy tests: PASS — all 20 initial failures were resolved through stale-expectation, fixture, and timing/infrastructure corrections; no product regression remained.
- Full consultation reliability: PASS — 42 passed across the full invocation and fresh-worker partition reruns. One monolithic invocation also hit a worker-process crash; this was treated as infrastructure and did not reproduce as an assertion failure in the partitioned verification.
- Phase 1O-B focused Playwright: PASS — 10 passed in the final clean invocation.
- Diagnosis regressions: PASS — 16 passed. The current diagnosis file contains 16 tests; the earlier handoff count of 15 was stale.
- Complaint regressions: PASS — 20 passed in the current suite; the earlier 21 total included an isolated rerun of a timing case.
- Allergy regressions: PASS — 12 passed.
- Phase 1O-A backend contract tests: PASS — 4 passed.
- Django check: PASS — no issues identified.
- makemigrations --check --dry-run: PASS — no changes detected.
- migrate --plan: PASS — no planned migration operations.
- Frontend typecheck: PASS.
- Frontend lint: PASS.
- Frontend production build: PASS.
- Migration status: NONE.

Security and architecture:

- No browser PHI persistence was introduced: no localStorage, IndexedDB, service worker, offline queue, or persistent draft store.
- Generic audit behavior remains metadata-only; raw treatment or other clinical text is not added to generic audit payloads.
- No prescriptions, medication selection, dosage, interaction checking, procedures, referrals, investigations/LAB, printing, reporting, CDS, AI assistance, or external side effects were introduced.
- Synthetic local development records only; no real patient data or external services were used.
- Canonical backlog changed: NO.
- Canonical architecture touched: NO.
- Phase 1O-C and later clinical work: NOT STARTED.
- DX-004: COMPLETE.
- Commit: final commit SHA is reported in the completion report; this is the single requested commit.
- Push: normal push pending after the final commit.
- Next approved phase: NOT YET AUTHORISED.

### Phase 1O-B-F — Stable TreatmentSection Component Identity

Status: COMPLETE — the approved component-identity correction is implemented and the focused Phase 1O-B verification passed. The broader legacy regression gate remains PARTIAL because unrelated pre-existing tests failed in the combined and isolated runs.

Objective:
- Make `TreatmentSection` a stable module-level component alongside `HistorySection`.
- Add real incremental keyboard-typing and populated-text caret regression coverage.
- Preserve the existing treatment-plan state, autosave, navigation, and terminal-state behavior.

Implementation:
- Moved `TreatmentSectionProps` and `TreatmentSection` out of `ConsultationsWorkspace` without changing treatment-plan behavior.
- Added incremental per-character assertions for value preservation and focus retention.
- Added append-to-existing-value assertions for caret placement, value preservation, and focus retention.

Validation:
- Phase 1O-B focused Playwright: PASS — 12 passed, including the new incremental typing and populated caret tests.
- Incremental keyboard typing: PASS.
- Focus retained while typing: PASS.
- Editing existing text preserves caret/value: PASS.
- Consultation reliability regressions: PARTIAL — 37/42 passed in the combined run. The five failures were existing timing/fixture or test-code issues outside this correction; isolated rechecks passed for complaint patient-switch safety and delayed diagnosis reconciliation. Existing deterministic `respiratory is not defined` test errors at phase-1d lines 1480 and 1868 were not modified.
- Diagnosis regressions: PARTIAL — 14/16 passed in the combined run. The delayed patient-session reconciliation case passed in isolation; the existing sign-prerequisite case remained a timeout.
- Complaint regressions: PARTIAL — 18/20 passed in the combined run. The patient-switch case passed in isolation; the existing manual retry-marker assertion still observed an extra autosave marker.
- Allergy regressions: PASS — 12 passed.
- Phase 1O-A backend tests: PASS — 4 passed.
- Frontend typecheck: PASS.
- Frontend lint: PASS.
- Frontend production build: PASS.
- Migration status: NONE.

Scope and safety:
- Backend production changed: NO.
- No migration was created.
- Canonical backlog changed: NO.
- No Phase 1O-C or later work started.
- No browser PHI persistence was introduced: no localStorage, IndexedDB, service worker, offline queue, or persistent draft store.
- Only synthetic local development data was used for verification; no external side effects were performed.
- No genuine TreatmentSection regression was found.

Files changed for this phase:
- frontend/src/app/(app)/consultations/page.tsx
- frontend/tests/phase-1o-b-treatment-plan.spec.ts
- docs/REPO_REVIEW_HANDOFF.md

Known limitations:
- The broader regression suite still contains unrelated timing/fixture failures and two existing test-code `ReferenceError`s. They were not changed because fixing them would broaden this tiny component-identity slice.

Next approved phase: NOT YET AUTHORISED

### Phase 1O-B-F2 — Consultation Regression Gate Cleanup

Status: COMPLETE / PASS — the Phase 1O regression gate is closed after test-only cleanup and full verification.

Objective:
- Remove the remaining deterministic test-code defect and stabilize the identified consultation regression tests without changing production behavior or weakening assertions.

Initial failing-test classification:
- Unique initial failing tests: 9.
- Test-code defects: 2 — two in-flight examination predicates referenced `respiratory` instead of the field under test.
- Stale expectations: 0.
- Fixture prerequisite gaps: 0.
- Timing/synchronization issues: 7 — request/timer/session sequencing in the retry, sign, navigation, and delayed-response scenarios.
- Real product regressions: 0.

Corrections:
- Corrected the neurological and musculoskeletal in-flight request/response predicates to assert the actual field and value under test.
- Stabilized the complaint manual-save retry test with Playwright fake-clock control so the pending retry cannot race the explicit save.
- Added targeted request/session synchronization for examination rebase and delayed-response cases, including authoritative queue-entry selection for the stale page.
- Added only per-test timeout allowances for the two long-running local synthetic scenarios; no global timeout was changed.
- Assertions, selectors, retry markers, and product behavior were preserved.

Validation:
- Full consultation reliability: PASS — 90 passed, no tests skipped.
- Phase 1O-B treatment Playwright: PASS — 12 passed.
- Diagnosis regressions: PASS — 16 passed as part of the full consultation invocation.
- Complaint regressions: PASS — 20 passed as part of the full consultation invocation.
- Allergy regressions: PASS — 12 passed as part of the full consultation invocation.
- Phase 1O-A backend tests: PASS — 4 passed with `python -m pytest tests/test_phase_1o_a.py -q`.
- Frontend typecheck: PASS.
- Frontend lint: PASS.
- Frontend production build: PASS.
- Tests skipped: NO.
- Migration status: NONE.

Scope and safety:
- Production frontend code changed: NO. Backend production code changed: NO.
- Files changed: `frontend/tests/phase-1d-history.spec.ts`, `frontend/tests/phase-1l-b-complaints.spec.ts`, and this handoff file.
- No browser PHI persistence was introduced. No localStorage, IndexedDB, service worker, offline queue, background sync, or persistent draft cache was added.
- Verification used local synthetic development records only; no real patient data, secrets, credentials, or external side effects were used or exposed.
- Canonical backlog changed: NO. Runtime artifacts changed: NO. Phase 1O-C or later work started: NO.

Known limitations:
- The local synthetic database now contains a large accumulated queue from repeated E2E runs, so the full one-worker suite is slow. The completed run was deterministic and fully green; no product regression was demonstrated.

Phase 1O regression gate: CLOSED.

Next approved phase: NOT YET AUTHORISED


### Phase 1P-A — Encounter Disposition Backend Foundation

Status: COMPLETE / PASS for the visible Phase 1P-A requirements; backend-only and ready for review.

Objective:
- Added authoritative Encounter disposition state to the existing consultation revision and signing model.
- Kept the work limited to DX-006 backend foundation. No frontend disposition UI, referral workflow, follow-up scheduling, prescriptions, procedures, investigations, or pharmacy work was started.
- DX-006 backend foundation: COMPLETE.
- DX-007: NOT STARTED.
- DX-008: NOT STARTED.
- Phase 1P-B: NOT STARTED.

Canonical disposition choices:
- TREATED_AND_DISCHARGED
- REVIEW_SCHEDULED
- REFERRED_OUT
- ADMITTED_ELSEWHERE
- LEFT_AGAINST_ADVICE
- DECEASED
- OTHER

Storage and API:
- Added nullable/blank Encounter.disposition and bounded Encounter.disposition_note (maximum 1000 characters).
- Added PATCH /api/v1/clinic/encounters/{encounter_id}/disposition/.
- Disposition mutations require the current If-Match consultation ETag and return authoritative disposition, disposition_note, encounter_status, consultation_etag, and the ETag response header.
- Disposition and disposition_note are exposed by EncounterSerializer and are not stored inside ClinicalNote.content.
- Mutations use transaction.atomic and lock the scoped Encounter and consultation note.

Validation and signing:
- OTHER requires a non-whitespace disposition note; other choices may have a blank note. Omitted notes preserve the existing note under PATCH semantics; explicit blank clears it.
- Signing now requires a disposition after the existing complaint, allergy-review, and diagnosis prerequisites.
- REFERRED_OUT can be stored OPEN but signing returns REFERRAL_REQUIRED unless an existing scoped Referral record is present.
- REVIEW_SCHEDULED can be stored OPEN but signing returns FOLLOW_UP_REQUIRED unless an existing scoped FollowUpRecommendation with a date is present.
- DECEASED can be stored and signed; no fake PAT-013 record or deceased workflow was created.
- Dependent DX-007/DX-008 workflows were not implemented.

Concurrency and immutability:
- Disposition state participates in the shared consultation ETag.
- A stale disposition mutation returns HTTP 412 with authoritative encounter, note, complaints, diagnoses, disposition, disposition_note, status, saved_at, and the current ETag; it never silently overwrites.
- Signed, amended, closed, and cancelled encounters reject disposition mutation with DISPOSITION_IMMUTABLE.
- The failed mutation does not create a false success audit event.

Audit and security:
- Disposition updates record only state metadata and disposition_note_present/changed_fields; the raw disposition note is not placed in generic audit payloads.
- No browser PHI persistence was introduced. No localStorage, IndexedDB, service worker, offline queue, or persistent draft store was added.
- All test data is synthetic development data only.

Validation:
- Focused Phase 1P-A backend tests: PASS — 14 passed.
- Phase 1N-A, Phase 1M-A, and Phase 1O-A backend regressions plus Phase 1P-A: PASS — 59 passed.
- Full backend suite: PASS — 217 passed, 7 expected PostgreSQL-only skips.
- Skips: 5 PostgreSQL-only authentication/RLS tests and 2 PostgreSQL row-lock tests; the local validation database is SQLite.
- Django check: PASS — no issues identified.
- makemigrations --check --dry-run: PASS — no changes detected.
- migrate --plan: PASS — only clinical.0007_encounter_disposition_encounter_disposition_note is planned.
- Ruff: NOT RUN — the standalone command and Python module are unavailable in this environment.

Migration:
- Added clinical.0007_encounter_disposition_encounter_disposition_note.py.
- No data migration, referral record, follow-up record, or PAT-013 workflow was created.

Files changed:
- backend/clinical/models.py
- backend/clinical/serializers.py
- backend/clinical/concurrency.py
- backend/clinical/dispositions.py
- backend/clinical/services.py
- backend/clinical/urls.py
- backend/clinical/views.py
- backend/clinical/migrations/0007_encounter_disposition_encounter_disposition_note.py
- backend/tests/clinical_test_helpers.py
- backend/tests/test_phase_1n_a.py
- backend/tests/test_phase_1p_a.py
- docs/REPO_REVIEW_HANDOFF.md

Scope and limitations:
- Canonical backlog changed: NO.
- Frontend disposition UI: NOT STARTED.
- Phase 1P-B and later phases: NOT STARTED.
- The supplied Phase 1P-A instruction attachment ended mid-SIGNING immediately after "Add:"; no requirements beyond the visible text were inferred.
- PostgreSQL-specific RLS/row-lock execution remains for the PostgreSQL validation environment.

Next approved phase: NOT YET AUTHORISED

### Phase 1P-B — Encounter Disposition Clinician UI

Status: COMPLETE / ready for review.

Objective:
- Added clinician-facing Encounter disposition capture to the existing Treatment section using the Phase 1P-A backend contract.
- Added the canonical choices TREATED_AND_DISCHARGED, REVIEW_SCHEDULED, REFERRED_OUT, ADMITTED_ELSEWHERE, LEFT_AGAINST_ADVICE, DECEASED, and OTHER.
- The select has no default. OTHER requires a trimmed note and the note is bounded to 1000 characters. Saving is explicit and sends only the disposition payload with the current shared consultation ETag.
- Disposition is coordinated with the existing note, complaint, diagnosis, autosave, sign, and patient/session state; the existing save architecture was preserved.

Dependency and signing behavior:
- REFERRED_OUT and REVIEW_SCHEDULED show neutral notices and remain blocked at signing until the corresponding existing referral/follow-up prerequisites are present. Those dependent workflows were not implemented.
- Other dispositions can be saved and signed when the existing complaint, allergy, and diagnosis prerequisites also pass. A missing disposition blocks signing.
- Signed/terminal encounters display disposition and note read-only. No deceased patient-state workflow was invented.

Concurrency and recovery:
- Disposition mutation uses PATCH /api/v1/clinic/encounters/{encounter_id}/disposition/ with If-Match and adopts the authoritative response ETag/state on success.
- A disposition 412 performs an authoritative Encounter GET, reconciles note content, complaints, diagnoses, disposition, encounter status, and shared ETag under encounter/patient/queue/session guards, and does not replay the failed disposition command.
- Dirty local note/complaint/diagnosis drafts are preserved or surfaced as conflicts according to the existing Phase 1J/1N behavior. Failed reconciliation does not adopt an uncertain ETag and blocks further mutation until reload.
- Patient switching and beforeunload protection include unsaved disposition state. Section switching remains safe. In-flight and delayed responses cannot update a later patient session.

Audit and security:
- Existing autosave/audit summary semantics were preserved; no raw disposition note was added to generic audit payloads.
- No browser PHI persistence was introduced: no localStorage, IndexedDB, service worker, offline queue, or persistent draft store.
- All browser checks used synthetic local data and disposable SQLite databases only. Backend production code was not changed.

Files changed:
- frontend/src/app/(app)/consultations/page.tsx
- frontend/src/features/clinic/types.ts
- frontend/tests/phase-1p-b-disposition.spec.ts
- frontend/tests/clinic-slice.spec.ts
- frontend/tests/phase-1b-history.spec.ts
- frontend/tests/phase-1c-history.spec.ts
- frontend/tests/phase-1d-history.spec.ts
- frontend/tests/phase-1l-b-complaints.spec.ts
- frontend/tests/phase-1m-b-allergies.spec.ts
- frontend/tests/phase-1n-b-diagnoses.spec.ts
- frontend/tests/phase-1o-b-treatment-plan.spec.ts
- docs/REPO_REVIEW_HANDOFF.md

Tests:
- Focused Phase 1P-B Playwright: PASS — 12 passed.
- Consultation reliability / Phase 1D-F through Phase 1K regressions: PASS — 40 passed.
- Phase 1L-B complaints: PASS — 20 passed.
- Phase 1M-B allergies: PASS — 12 passed.
- Phase 1N-B diagnoses: PASS — 16 passed.
- Phase 1O-B treatment plan: PASS — 12 passed.
- Clinic vertical slice plus Phase 1B and Phase 1C regression cases: PASS — 3 passed.
- Phase 1P-A backend: PASS — 14 passed.
- Django check: PASS — no issues identified.
- makemigrations --check --dry-run: PASS — no changes detected.
- migrate --plan: PASS — no planned migration operations.
- Frontend typecheck: PASS.
- Frontend lint: PASS.
- Frontend production build: PASS — Next.js 15.5.23.

Migration status:
- NONE for Phase 1P-B. The existing Phase 1P-A migration was used locally; no new migration was created.

Known limitations:
- Referral creation, follow-up scheduling, and downstream referral/follow-up workflows remain unimplemented.
- DECEASED does not create a patient-status workflow.
- Downstream reporting/printing integration remains outside this slice.
- The local browser suite uses synthetic development records only.

No browser PHI persistence was introduced.

Next approved phase: NOT YET AUTHORISED
### Phase 1Q-A — DX-008 Follow-Up Backend Foundation

Status: COMPLETE / PASS for the approved backend-only follow-up foundation; ready for review.

Objective:
- Reused the existing `scheduling.FollowUpRecommendation` model. No alternate follow-up model was created.
- Added scoped GET/PATCH support at `/api/v1/clinic/encounters/{encounter_id}/follow-up/` for `recommended_date` and clinician-authored `instructions`.
- Creation requires a valid recommended date; partial updates preserve omitted existing fields. Instruction text is stored and returned verbatim.
- The recommendation is linked to the current Encounter and its Patient, and the endpoint serializes create/update on the locked Encounter so repeated/concurrent endpoint mutations reuse one authoritative current recommendation.

Authorization and isolation:
- The endpoint reuses the existing server-side `clinical.note.create` capability used for clinical authoring. A clinical MIDWIFE role with that capability is accepted; reception capability is denied in focused tests.
- Encounter, follow-up, organisation, facility, and patient queries are scoped together. Cross-facility and cross-organisation records are not visible or mutable.

Concurrency and signing:
- Follow-up state is included in the shared consultation ETag. Every mutation requires `If-Match`; stale state returns HTTP 412 with the authoritative follow-up and consultation state, without applying the failed command.
- Signed, closed, and cancelled encounters, plus signed/amended consultation notes, reject follow-up mutation.
- `REVIEW_SCHEDULED` continues to require a scoped follow-up with a valid recommended date; once saved, the existing sign workflow succeeds. Without one, signing returns `FOLLOW_UP_REQUIRED`.

Audit and security:
- Follow-up audit events contain encounter/follow-up identifiers, field-presence metadata, and changed field names only; raw instruction text is never written to generic audit payloads.
- No browser persistence, reminders, SMS/email, appointments, printing, referrals, or frontend production code was added. No PHI or credentials were used in validation.

Files changed:
- `backend/clinical/concurrency.py`
- `backend/clinical/dispositions.py`
- `backend/clinical/followups.py`
- `backend/clinical/serializers.py`
- `backend/clinical/urls.py`
- `backend/clinical/views.py`
- `backend/tests/test_phase_1q_a.py`
- `docs/REPO_REVIEW_HANDOFF.md`

Validation:
- Focused Phase 1Q-A backend tests: PASS — 9 passed.
- Phase 1P-A, diagnosis, allergy, and sign regressions: PASS — 57 passed; 2 existing PostgreSQL-only row-lock tests skipped under local SQLite.
- Full backend suite: PASS — 226 passed; 7 existing PostgreSQL-only tests skipped (5 authentication/RLS and 2 row-lock checks).
- Django check: PASS — no issues identified.
- `makemigrations --check --dry-run`: PASS — no changes detected.
- `migrate --plan`: PASS — no planned migration operations.

Migration status:
- NONE. The existing `scheduling.FollowUpRecommendation` schema already provides the required date/instructions fields; no migration was created.

Known limitations:
- Follow-up interval entry, appointment creation (APT-001), printing, reminders, referral/DX-007, and frontend UI remain outside this phase.
- PostgreSQL-specific RLS and row-lock execution remains for the PostgreSQL validation environment; the local full-suite skips are recorded above.
- No Phase 1R or later work was started.

No browser PHI persistence was introduced.

Next approved phase: NOT YET AUTHORISED