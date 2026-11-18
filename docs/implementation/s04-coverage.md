# S-04 acceptance coverage map

**Candidate base:** `711522de3a07c8b02eebc1a62b8806eb79bdfe97` (accepted S-03) on `codex/s-04-encounter`.
**Scope:** the authorized Encounter lifecycle — same-Visit open/resume, draft save, signing with
one immutable version and consultation stage completion, the Encounter addendum/takeover paths
already present, and MIG-004. Blocked branches name their owner/dependency and are not claimed.

Statuses: **COVERED** = candidate test, **PRIOR** = existing accepted-base test, **PARTIAL** =
implemented subset with the remaining acceptance text named, **BLOCKED** = authority/dependency unavailable.

| AC | Status | Evidence / gap |
| --- | --- | --- |
| ENC-001-AC01 | PARTIAL | Candidate `test_s04_open_reuses_one_open_encounter_for_the_visit`, `test_pg_s04_concurrent_open_has_one_encounter` and the S-04 browser journey cover same-Visit open/reuse. Credential and PAY_BEFORE override branches remain bounded (BP-BL-03/06). |
| ENC-001-AC02 | PARTIAL | Candidate `test_s04_open_reuses_one_open_encounter_for_the_visit`, `test_pg_s04_concurrent_open_has_one_encounter` and the S-04 browser journey cover same-Visit open/reuse. Credential and PAY_BEFORE override branches remain bounded (BP-BL-03/06). |
| ENC-001-AC03 | PARTIAL | Candidate `test_s04_open_reuses_one_open_encounter_for_the_visit`, `test_pg_s04_concurrent_open_has_one_encounter` and the S-04 browser journey cover same-Visit open/reuse. Credential and PAY_BEFORE override branches remain bounded (BP-BL-03/06). |
| ENC-001-AC04 | PARTIAL | Candidate `test_s04_open_reuses_one_open_encounter_for_the_visit`, `test_pg_s04_concurrent_open_has_one_encounter` and the S-04 browser journey cover same-Visit open/reuse. Credential and PAY_BEFORE override branches remain bounded (BP-BL-03/06). |
| ENC-001-AC05 | PARTIAL | Candidate `test_s04_open_reuses_one_open_encounter_for_the_visit`, `test_pg_s04_concurrent_open_has_one_encounter` and the S-04 browser journey cover same-Visit open/reuse. Credential and PAY_BEFORE override branches remain bounded (BP-BL-03/06). |
| ENC-002-AC01 | PARTIAL | Normal resume returns the same Encounter (browser reload and `test_pg_s04_concurrent_open_has_one_encounter`). RESULTS_READY/AWAITING_RESULTS resume (ENC-016) is blocked on Lab owner paths. |
| ENC-002-AC02 | PARTIAL | Normal resume returns the same Encounter (browser reload and `test_pg_s04_concurrent_open_has_one_encounter`). RESULTS_READY/AWAITING_RESULTS resume (ENC-016) is blocked on Lab owner paths. |
| ENC-002-AC03 | PARTIAL | Normal resume returns the same Encounter (browser reload and `test_pg_s04_concurrent_open_has_one_encounter`). RESULTS_READY/AWAITING_RESULTS resume (ENC-016) is blocked on Lab owner paths. |
| ENC-002-AC04 | PARTIAL | Normal resume returns the same Encounter (browser reload and `test_pg_s04_concurrent_open_has_one_encounter`). RESULTS_READY/AWAITING_RESULTS resume (ENC-016) is blocked on Lab owner paths. |
| ENC-002-AC05 | PARTIAL | Normal resume returns the same Encounter (browser reload and `test_pg_s04_concurrent_open_has_one_encounter`). RESULTS_READY/AWAITING_RESULTS resume (ENC-016) is blocked on Lab owner paths. |
| ENC-002-AC06 | PARTIAL | Normal resume returns the same Encounter (browser reload and `test_pg_s04_concurrent_open_has_one_encounter`). RESULTS_READY/AWAITING_RESULTS resume (ENC-016) is blocked on Lab owner paths. |
| ENC-003-AC01 | PRIOR | Existing encounter-context tests on the accepted base (`test_phase_1c*`, QRY-003). |
| ENC-003-AC02 | PRIOR | Existing encounter-context tests on the accepted base (`test_phase_1c*`, QRY-003). |
| ENC-003-AC03 | PRIOR | Existing encounter-context tests on the accepted base (`test_phase_1c*`, QRY-003). |
| ENC-003-AC04 | PRIOR | Existing encounter-context tests on the accepted base (`test_phase_1c*`, QRY-003). |
| ENC-004-AC01 | PRIOR | S-03 clinician triage projection and the consultation History panel tests. |
| ENC-004-AC02 | PRIOR | S-03 clinician triage projection and the consultation History panel tests. |
| ENC-005-AC01 | COVERED | `_save_and_sign` in `test_s04_encounter.py`; existing phase draft/conflict tests. |
| ENC-005-AC02 | COVERED | `_save_and_sign` in `test_s04_encounter.py`; existing phase draft/conflict tests. |
| ENC-005-AC03 | COVERED | `_save_and_sign` in `test_s04_encounter.py`; existing phase draft/conflict tests. |
| ENC-006-AC01 | COVERED | Existing note ETag/version tests plus the S-04 save; no TREATMENT note subtype is invented (SPEC_UNSUPPLIED). |
| ENC-006-AC02 | COVERED | Existing note ETag/version tests plus the S-04 save; no TREATMENT note subtype is invented (SPEC_UNSUPPLIED). |
| ENC-007-AC01 | PARTIAL | Free examination text is covered by the existing note tests; templates/quick picks need BP-BL-03/04/06 configuration authority. |
| ENC-007-AC02 | PARTIAL | Free examination text is covered by the existing note tests; templates/quick picks need BP-BL-03/04/06 configuration authority. |
| ENC-008-AC01 | PARTIAL | Chronic context is stored in the triage version and shown in the summary; ENC-008 prefill/templates await BP-BL authority. |
| ENC-008-AC02 | PARTIAL | Chronic context is stored in the triage version and shown in the summary; ENC-008 prefill/templates await BP-BL authority. |
| ENC-009-AC01 | BLOCKED | CMD-118/119 patient-problem fields and roles are unsupplied (OD-08 forbids auto-derivation). |
| ENC-009-AC02 | BLOCKED | CMD-118/119 patient-problem fields and roles are unsupplied (OD-08 forbids auto-derivation). |
| ENC-009-AC03 | BLOCKED | CMD-118/119 patient-problem fields and roles are unsupplied (OD-08 forbids auto-derivation). |
| ENC-010-AC01 | PARTIAL | S-03 captures current medications/chronic text and the summary reads them; prescription/clerking prefill is owned by RX (S-12). |
| ENC-010-AC02 | PARTIAL | S-03 captures current medications/chronic text and the summary reads them; prescription/clerking prefill is owned by RX (S-12). |
| ENC-011-AC01 | COVERED | Sign requires a current encounter allergy review (`test_s04_sign_*`); existing allergy routes/tests cover record/NKA/entered-in-error. |
| ENC-011-AC02 | COVERED | Sign requires a current encounter allergy review (`test_s04_sign_*`); existing allergy routes/tests cover record/NKA/entered-in-error. |
| ENC-011-AC03 | COVERED | Sign requires a current encounter allergy review (`test_s04_sign_*`); existing allergy routes/tests cover record/NKA/entered-in-error. |
| ENC-012-AC01 | PARTIAL | Diagnosis state renders in the workspace; patient-problem list is blocked with ENC-009. |
| ENC-013-AC01 | BLOCKED | CMD-120 patient obstetric summary fields/authority are unsupplied. |
| ENC-013-AC02 | BLOCKED | CMD-120 patient obstetric summary fields/authority are unsupplied. |
| ENC-014-AC01 | PRIOR | Existing examination-section note tests (phase 1l/1n) on the accepted base. |
| ENC-014-AC02 | PRIOR | Existing examination-section note tests (phase 1l/1n) on the accepted base. |
| ENC-014-AC03 | PRIOR | Existing examination-section note tests (phase 1l/1n) on the accepted base. |
| ENC-015-AC01 | PRIOR | Existing note section/autosave/immutability tests on the accepted base. |
| ENC-015-AC02 | PRIOR | Existing note section/autosave/immutability tests on the accepted base. |
| ENC-015-AC03 | PRIOR | Existing note section/autosave/immutability tests on the accepted base. |
| ENC-015-AC04 | PRIOR | Existing note section/autosave/immutability tests on the accepted base. |
| ENC-015-AC05 | PRIOR | Existing note section/autosave/immutability tests on the accepted base. |
| ENC-016-AC01 | BLOCKED | CMD-032/033 park and results-ready require actual Lab item dependencies and Lab owner transitions. |
| ENC-016-AC02 | BLOCKED | CMD-032/033 park and results-ready require actual Lab item dependencies and Lab owner transitions. |
| ENC-016-AC03 | BLOCKED | CMD-032/033 park and results-ready require actual Lab item dependencies and Lab owner transitions. |
| ENC-016-AC04 | BLOCKED | CMD-032/033 park and results-ready require actual Lab item dependencies and Lab owner transitions. |
| ENC-016-AC05 | BLOCKED | CMD-032/033 park and results-ready require actual Lab item dependencies and Lab owner transitions. |
| ENC-017-AC01 | COVERED | `test_s04_sign_completes_consultation_and_preserves_invoice`, `test_pg_s04_concurrent_sign_has_one_version_and_completion`; one signed version, one queue completion, invoice unchanged. |
| ENC-017-AC02 | COVERED | `test_s04_sign_completes_consultation_and_preserves_invoice`, `test_pg_s04_concurrent_sign_has_one_version_and_completion`; one signed version, one queue completion, invoice unchanged. |
| ENC-017-AC03 | COVERED | `test_s04_sign_completes_consultation_and_preserves_invoice`, `test_pg_s04_concurrent_sign_has_one_version_and_completion`; one signed version, one queue completion, invoice unchanged. |
| ENC-017-AC04 | COVERED | `test_s04_sign_completes_consultation_and_preserves_invoice`, `test_pg_s04_concurrent_sign_has_one_version_and_completion`; one signed version, one queue completion, invoice unchanged. |
| ENC-017-AC05 | COVERED | `test_s04_sign_completes_consultation_and_preserves_invoice`, `test_pg_s04_concurrent_sign_has_one_version_and_completion`; one signed version, one queue completion, invoice unchanged. |
| ENC-017-AC06 | COVERED | `test_s04_sign_completes_consultation_and_preserves_invoice`, `test_pg_s04_concurrent_sign_has_one_version_and_completion`; one signed version, one queue completion, invoice unchanged. |
| ENC-017-AC07 | COVERED | `test_s04_sign_completes_consultation_and_preserves_invoice`, `test_pg_s04_concurrent_sign_has_one_version_and_completion`; one signed version, one queue completion, invoice unchanged. |
| ENC-018-AC01 | BLOCKED | CMD-036 sign-pending requires the Lab owner and explicit sign-pending authority. |
| ENC-019-AC01 | BLOCKED | CMD-037 void requires supplied correction authority and every downstream blocker; no void is synthesized. |
| ENC-019-AC02 | BLOCKED | CMD-037 void requires supplied correction authority and every downstream blocker; no void is synthesized. |
| ENC-019-AC03 | BLOCKED | CMD-037 void requires supplied correction authority and every downstream blocker; no void is synthesized. |
| ENC-020-AC01 | PRIOR | Existing encounter-context projection tests. |
| ENC-020-AC02 | PRIOR | Existing encounter-context projection tests. |
| ENC-020-AC03 | PRIOR | Existing encounter-context projection tests. |
| ENC-021-AC01 | PRIOR | S-03 triage clinician projection and consultation summary tests. |
| ENC-021-AC02 | PRIOR | S-03 triage clinician projection and consultation summary tests. |
| ENC-021-AC03 | PRIOR | S-03 triage clinician projection and consultation summary tests. |
| ENC-021-AC04 | PRIOR | S-03 triage clinician projection and consultation summary tests. |
| ENC-022-AC01 | PRIOR | S-02 queue takeover and Encounter co-author test; no authoured history is rewritten. |
| ENC-022-AC02 | PRIOR | S-02 queue takeover and Encounter co-author test; no authoured history is rewritten. |
| ENC-022-AC03 | PRIOR | S-02 queue takeover and Encounter co-author test; no authoured history is rewritten. |
| ENC-022-AC04 | PRIOR | S-02 queue takeover and Encounter co-author test; no authoured history is rewritten. |
| ENC-023-AC01 | PRIOR | Existing `amend_note` service, `EncounterAmendView` and phase amendment tests; signed version retained. |
| ENC-023-AC02 | PRIOR | Existing `amend_note` service, `EncounterAmendView` and phase amendment tests; signed version retained. |
| ENC-023-AC03 | PRIOR | Existing `amend_note` service, `EncounterAmendView` and phase amendment tests; signed version retained. |
| ENC-023-AC04 | PRIOR | Existing `amend_note` service, `EncounterAmendView` and phase amendment tests; signed version retained. |
| ENC-024-AC01 | BLOCKED | Authorised document/print projection needs supplied legal templates and print gates. |
| ENC-024-AC02 | BLOCKED | Authorised document/print projection needs supplied legal templates and print gates. |
| ENC-024-AC03 | BLOCKED | Authorised document/print projection needs supplied legal templates and print gates. |
| DX-001-AC01 | PRIOR | Existing diagnosis save tests (phase 1n). |
| DX-001-AC02 | PRIOR | Existing diagnosis save tests (phase 1n). |
| DX-001-AC03 | PRIOR | Existing diagnosis save tests (phase 1n). |
| DX-002-AC01 | PRIOR | Existing diagnosis revision/history tests. |
| DX-002-AC02 | PRIOR | Existing diagnosis revision/history tests. |
| DX-002-AC03 | PRIOR | Existing diagnosis revision/history tests. |
| DX-002-AC04 | PRIOR | Existing diagnosis revision/history tests. |
| DX-003-AC01 | PRIOR | Existing no-diagnosis and coded/uncoded tests. |
| DX-003-AC02 | PRIOR | Existing no-diagnosis and coded/uncoded tests. |
| DX-003-AC03 | PRIOR | Existing no-diagnosis and coded/uncoded tests. |
| DX-004-AC01 | PRIOR | Existing treatment-plan note tests. |
| DX-004-AC02 | PRIOR | Existing treatment-plan note tests. |
| DX-004-AC03 | PRIOR | Existing treatment-plan note tests. |
| DX-005-AC01 | BLOCKED | Procedure order/perform needs catalogue, pricing and stock/lot authority (S-09) and CMD-102/132 gates. |
| DX-005-AC02 | BLOCKED | Procedure order/perform needs catalogue, pricing and stock/lot authority (S-09) and CMD-102/132 gates. |
| DX-005-AC03 | BLOCKED | Procedure order/perform needs catalogue, pricing and stock/lot authority (S-09) and CMD-102/132 gates. |
| DX-005-AC04 | BLOCKED | Procedure order/perform needs catalogue, pricing and stock/lot authority (S-09) and CMD-102/132 gates. |
| DX-005-AC05 | BLOCKED | Procedure order/perform needs catalogue, pricing and stock/lot authority (S-09) and CMD-102/132 gates. |
| DX-005-AC06 | BLOCKED | Procedure order/perform needs catalogue, pricing and stock/lot authority (S-09) and CMD-102/132 gates. |
| DX-006-AC01 | PRIOR | Existing disposition tests (phase 1p); BP-BL-05 branch remains bounded. |
| DX-006-AC02 | PRIOR | Existing disposition tests (phase 1p); BP-BL-05 branch remains bounded. |
| DX-006-AC03 | PRIOR | Existing disposition tests (phase 1p); BP-BL-05 branch remains bounded. |
| DX-006-AC04 | PRIOR | Existing disposition tests (phase 1p); BP-BL-05 branch remains bounded. |
| DX-006-AC05 | PRIOR | Existing disposition tests (phase 1p); BP-BL-05 branch remains bounded. |
| DX-007-AC01 | BLOCKED | Referral letter legal text/template and issue numbering are unsupplied. |
| DX-007-AC02 | BLOCKED | Referral letter legal text/template and issue numbering are unsupplied. |
| DX-007-AC03 | BLOCKED | Referral letter legal text/template and issue numbering are unsupplied. |
| DX-007-AC04 | BLOCKED | Referral letter legal text/template and issue numbering are unsupplied. |
| DX-008-AC01 | PRIOR | Existing follow-up recommendation tests; no Appointment is created. |
| DX-008-AC02 | PRIOR | Existing follow-up recommendation tests; no Appointment is created. |
| DX-008-AC03 | PRIOR | Existing follow-up recommendation tests; no Appointment is created. |
| DX-009-AC01 | BLOCKED | Medical-certificate legal text/template authority is unsupplied. |
| DX-009-AC02 | BLOCKED | Medical-certificate legal text/template authority is unsupplied. |
| DX-010-AC01 | BLOCKED | Authorised reporting projection needs REP authority. |
| DX-010-AC02 | BLOCKED | Authorised reporting projection needs REP authority. |
| DX-010-AC03 | BLOCKED | Authorised reporting projection needs REP authority. |

## Cross-cutting evidence

- Candidate tests: `backend/tests/test_s04_encounter.py` (5), `backend/tests/test_s04_postgres.py` (4),
  `frontend/tests/s04-encounter.spec.ts` (1 browser journey).
- PostgreSQL proof runs as `clinicopus_app` with FORCE RLS, no ownership/BYPASSRLS, the one-open
  Encounter index, note-version hash check and append-only/retained triggers; the disabled-guard
  cutover proof starts from CONSTRAINED. MIG-004 backfills/verifies signed-version hashes and
  classifies legacy CLOSED/CANCELLED or unproven rows as PC-050 exceptions without rewriting them.
- Prior evidence reused: S-01 invoice/check-in, S-02 queue/takeover, S-03 triage/summary, and the
  existing diagnosis/disposition/follow-up/allergy note tests on the accepted base.
