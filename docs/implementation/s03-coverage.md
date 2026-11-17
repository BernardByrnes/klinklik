# S-03 acceptance coverage map

**Candidate base:** `21b0653457594b2de49d1c0658067b6ddfbcb1fc` (accepted S-02) on `codex/s-03-triage`.
**Scope:** the ordinary versioned triage workflow (TRI-001..007, TRI-009, TRI-011), the
MIG-003 migration path, and the supplied UI summary. TRI-008, TRI-010/012 and TRI-013
remain blocked by the authority/dependency conditions recorded below.

Statuses:

- **COVERED** — exercised by a candidate test or an unchanged prior test whose inputs still match.
- **PARTIAL** — the named part is implemented and tested; the remaining acceptance text is listed as a gap.
- **BLOCKED** — not implemented because its authority, rules or dependency are unavailable.

## TRI-001 — Open triage for a queued patient (CMD-025)

| AC | Status | Evidence / gap |
| --- | --- | --- |
| TRI-001-AC01 | PARTIAL | Age and under-5 chip are supplied by the existing operational projection; the triage row currently shows patient/queue/department only. No new S-03 test; UI gap. |
| TRI-001-AC02 | COVERED | `test_s03_start_save_complete_preserves_the_check_in_invoice` (resume same DRAFT), `test_pg_s03_concurrent_start_has_one_draft`; `uniq_triage_record_visit`. |
| TRI-001-AC03 | COVERED | Same tests: start transitions the TRIAGE entry to `IN_SERVICE` in the same transaction. |
| TRI-001-AC04 | BLOCKED | Prior-vitals/height prefill is conditional on TRI-001-AC04 approval on this baseline; not supplied. Owner: product. |
| TRI-001-AC05 | PARTIAL | The S-02 operational projection is unchanged and carries no diagnoses/notes; no S-03-specific worklist payload was added. Prior `test_s02_queue.py` scope tests. |

## TRI-002 — Record vital signs (CMD-026)

| AC | Status | Evidence / gap |
| --- | --- | --- |
| TRI-002-AC01 | PARTIAL | Saves; the `abnormal_high` flag/reference-band marker needs facility reference bands that are not supplied. Owner: clinical configuration. |
| TRI-002-AC02 | COVERED | `test_s03_replay_and_concurrency_guards` rejects `temperature_c` 3.98 with `VITAL_OUT_OF_RANGE`; accepted band 30.0–45.0. |
| TRI-002-AC03 | COVERED | Same test rejects diastolic ≥ systolic with `DIASTOLIC_EXCEEDS_SYSTOLIC`. |
| TRI-002-AC04 | COVERED | Same test rejects pulse 0 with `VITAL_OUT_OF_RANGE`. |
| TRI-002-AC05 | COVERED | `test_s03_start_save_complete_preserves_the_check_in_invoice` asserts server-derived BMI `22.1`, no interpretation. |
| TRI-002-AC06 | BLOCKED | Neutral outside-reference marker requires the unsupplied reference bands. Owner: clinical configuration. |
| TRI-002-AC07 | PARTIAL | MUAC is accepted, stored and displayed; the under-2 BMI display exception needs age-band rules that are not supplied. |
| TRI-002-AC08 | PARTIAL | `unable_reason_fields` is accepted, stored with the observation, audited without values, and rendered in the clinician summary; the nurse form exposes no per-field not-done control yet. |
| TRI-002-AC09 | COVERED | Happy-path test asserts the observation, version/hash and `TRIAGE_VITALS_RECORDED` metadata; idempotency bodies contain no values. |

## TRI-003 — Presenting complaint (CMD-026)

| AC | Status | Evidence / gap |
| --- | --- | --- |
| TRI-003-AC01 | PARTIAL | Structured complaints with durations are accepted and persisted in the version (happy-path test asserts the `DAYS` duration); the nurse textarea sends free-text rows without duration controls. |
| TRI-003-AC02 | COVERED | Unicode round-trip `Kuharisha — 2 siku`; `normalize_complaints` enforces 500 characters and prior complaint tests cover the limit. |
| TRI-003-AC03 | BLOCKED | Facility quick-pick options exist in `FacilityWorkflowPolicy`, but the triage form has no quick-pick control yet. Owner: product/UI. |
| TRI-003-AC04 | COVERED | More than five complaints returns `COMPLAINT_LIMIT_EXCEEDED` in `test_s03_replay_and_concurrency_guards`. |
| TRI-003-AC05 | COVERED | The clinician summary is read-only; there is no clinician edit path to the nurse record. |

## TRI-004 — Allergies at triage (CMD-092/093/094, CMD-026)

| AC | Status | Evidence / gap |
| --- | --- | --- |
| TRI-004-AC01 | PARTIAL | The existing patient-level allergy routes and banner are unchanged (prior S-01/clinical tests); completion now requires a recorded status. |
| TRI-004-AC02 | COVERED | Existing NKA/UNKNOWN/RECORDED distinction; completion test uses NKA and requires it. |
| TRI-004-AC03 | COVERED | `test_s03_completion_requires_human_fields_and_allergy_status` returns 422 `ALLERGY_STATUS_REQUIRED`. |
| TRI-004-AC04 | PARTIAL | The existing allergy banner shows "not recorded"; no new S-03 header test. |
| TRI-004-AC05 | PRIOR | Existing entered-in-error route/tests (`CMD-094`); unchanged. |
| TRI-004-AC06 | COVERED | No interaction checking or acuity suggestion exists; the UI states that the system does not interpret observations. |

## TRI-005 — Current medications and history (CMD-026)

| AC | Status | Evidence / gap |
| --- | --- | --- |
| TRI-005-AC01 | PARTIAL | Up to ten free-text medication rows are validated, stored and shown in the clinician summary; prefill into the clerking field is not implemented. Owner: S-04 Encounter lifecycle. |
| TRI-005-AC02 | PARTIAL | Chronic-condition labels are validated, stored and shown; clerking prefill is not implemented. Owner: S-04. |

## TRI-006 — Human-selected acuity (CMD-026/027)

| AC | Status | Evidence / gap |
| --- | --- | --- |
| TRI-006-AC01 | PARTIAL | The selected acuity becomes the destination priority in the same transaction (happy-path test asserts `URGENT`); the emergency header count/notification prompt is not implemented. Owner: product/UI. |
| TRI-006-AC02 | PARTIAL | Completion audits `TRIAGE_ACUITY_ASSIGNED` / `TRIAGE_ACUITY_DOWNGRADED` with previous/current, actor and reason presence; a draft save audits field names only. Queue priority changes at completion by design. |
| TRI-006-AC03 | COVERED | Missing acuity returns 422 `ACUITY_REQUIRED`; the header has no default or preselection. |
| TRI-006-AC04 | PARTIAL | Acuity and priority reason are exposed in the read-only clinician summary; the encounter header chip is not built. Owner: S-04/UI. |

## TRI-007 — Complete and forward (CMD-027)

| AC | Status | Evidence / gap |
| --- | --- | --- |
| TRI-007-AC01 | COVERED | The browser spec opens the consultation Encounter and asserts the triage summary (acuity, complaint, temperature, recorder/read-only marker). |
| TRI-007-AC02 | COVERED | Missing required fields leave the record `DRAFT` with no destination/audit in `test_s03_completion_requires_human_fields_and_allergy_status`. |
| TRI-007-AC03 | COVERED | Happy-path test asserts `TRIAGE_COMPLETED` and `QUEUE_HANDOFF`; the queue handoff remains the S-02 owner transition. |
| TRI-007-AC04 | BLOCKED | Emergency prompt/notification depends on the TRI-013 workflow. Owner: product. |

## TRI-008 — Amend a triage record (CMD-028)

| AC | Status | Evidence / gap |
| --- | --- | --- |
| TRI-008-AC01 | BLOCKED | The amendment window and amendment authority are not explicitly supplied for this slice. The immutable `TriageRecordVersion` model and append-only trigger are ready. Owner: product/owner decision (window/authority), then a narrow CMD-028 follow-up. |
| TRI-008-AC02 | BLOCKED | Acuity-not-retroactive amendment behavior depends on CMD-028 being authorized. |
| TRI-008-AC03 | BLOCKED | Print/amendment-badge behavior depends on CMD-028 and the printing slice. |

## TRI-009 — Clinician view of triage data (CMD-027 read)

| AC | Status | Evidence / gap |
| --- | --- | --- |
| TRI-009-AC01 | PARTIAL | Summary shows acuity/reason, vitals with units, BMI, complaints, medications/chronic conditions and recorder/time; the existing allergy banner remains separate; previous-history link is not built. |
| TRI-009-AC02 | PARTIAL | Not-done reasons render in the summary; the nurse form has no not-done controls. |
| TRI-009-AC03 | BLOCKED | "Triage updated" indicator after an amendment needs TRI-008. |
| TRI-009-AC04 | PARTIAL | The summary is absent when no completed record exists; the legacy "no triage complaint" panel remains for the pre-cutover window. |
| TRI-009-AC05 | COVERED | The clinician path is a read-only projection; no update route for clinicians. |
| TRI-009-AC06 | PRIOR | The Encounter-open `PHI_READ` audit is unchanged and covers the composed context; no new S-03 test. |

## TRI-010 / TRI-012 — Repeat vitals and history (CMD-029)

| AC | Status | Evidence / gap |
| --- | --- | --- |
| TRI-010-AC01 | BLOCKED | The repeat-task flow, supplied measurement rules and CMD-029/CMD-128 authority are not available. `VitalsObservation` now carries `context`, `sequence`, `unable_reason_fields` and `supersedes` so the branch can be added without a schema rewrite. Owner: product/S-04. |
| TRI-010-AC02 | BLOCKED | Concurrent-edit/unsaved-note survival requires the repeat flow (CMD-029). |
| TRI-010-AC03 | BLOCKED | The out-of-range repeat marker needs the unsupplied reference bands. |
| TRI-010-AC04 | BLOCKED | Repeat-vitals validation/audit is not built without CMD-029 authority. |
| TRI-012-AC01 | BLOCKED | Same-facility vitals history requires the bounded QRY-006 history read and is not implemented in this slice. |
| TRI-012-AC02 | BLOCKED | Cross-facility history needs the explicit BRN-003 sharing authority; it remains fenced. |
| TRI-012-AC03 | BLOCKED | The history `PHI_READ` event is part of the unimplemented history read. |

## TRI-011 — Mandatory paediatric weight

| AC | Status | Evidence / gap |
| --- | --- | --- |
| TRI-011-AC01 | COVERED | `test_s03_under_five_weight_and_unicode_round_trip` rejects a save without weight or an unable reason with `WEIGHT_REQUIRED_UNDER_5`. |
| TRI-011-AC02 | PARTIAL | The form exposes weight prominently; prescription/print emphasis belongs to S-04/S-05 output work. |
| TRI-011-AC03 | COVERED | An estimated age is represented by the patient's date of birth, so the same under-five weight rule applies; no separate estimated-age field is invented. |

## TRI-013 — Emergency care-first triage (CMD-004/005)

| AC | Status | Evidence / gap |
| --- | --- | --- |
| TRI-013-AC01 | BLOCKED | Provisional identity, PAT-002 merge, financial setup, REP-009 and the emergency authority are unavailable. The entry point remains inactive; no partial demo is claimed. Owner: product + S-04/S-05. |
| TRI-013-AC02 | BLOCKED | The emergency DRAFT/same-consultation-entry route depends on CMD-004/CMD-005. |
| TRI-013-AC03 | BLOCKED | The pending registration/financial setup obligations need the financial path. |
| TRI-013-AC04 | BLOCKED | The merge/reconciliation guarantees need PAT-002 and REP-009. |
| TRI-013-AC05 | BLOCKED | The whole TRI-013 journey and blocked ordinary closure cannot be claimed without those dependencies. |

## Cross-cutting evidence

- Candidate tests: `backend/tests/test_s03_triage.py` (5 workflow), `backend/tests/test_s03_mig003.py`
  (2 migration), `backend/tests/test_s03_postgres.py` (5), `frontend/tests/s03-triage.spec.ts`
  (1 browser journey).
- PostgreSQL proof runs as `clinicopus_app` with FORCE RLS, no ownership and no BYPASSRLS;
  the disabled-guard proof runs from `CONSTRAINED`.
- Prior evidence reused: S-01 reception/check-in invoice and allergy tests, S-02 queue
  scope/authorization tests, Encounter context audit tests.
- The S-01 concurrent service-price test remains a separately tracked timing flake.
