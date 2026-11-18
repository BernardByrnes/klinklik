# S-11 acceptance coverage — laboratory order, collection and release

Base: `ae4880f8a8154150c6a8a7d738162135f81b4d9b` (`codex/s-10-counts`).
Candidate worktree: `K:/klinklik-s11-lab` (`codex/s-11-lab`).

## Per-file test counts (fresh for this candidate)

| File | Tests | Inputs |
| --- | --- | --- |
| `backend/tests/test_s11_lab.py` | 5 | order/charge, collect, structured result, release/self-verification, amendment, cancellation, rejection, coded validation |
| `backend/tests/test_s11_postgres.py` | 2 | FORCE RLS/version guards and concurrent release |
| `frontend/tests/s11-lab.spec.ts` | 1 | order from Encounter → collect → result → release |

## Result: 106 IDs — BLOCKED 40, COVERED 39, PARTIAL 27

| AC | Status | Evidence / fenced owner decision |
| --- | --- | --- |
| LAB-001-AC01 | COVERED | structured analyte contract and range/flag handling; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend`, `test_s11_result_validation_coded_sanity_and_partial_save`. |
| LAB-001-AC02 | COVERED | structured analyte contract and range/flag handling; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend`, `test_s11_result_validation_coded_sanity_and_partial_save`. |
| LAB-001-AC03 | COVERED | structured analyte contract and range/flag handling; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend`, `test_s11_result_validation_coded_sanity_and_partial_save`. |
| LAB-001-AC04 | PARTIAL | structured analyte contract and range/flag handling; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend`, `test_s11_result_validation_coded_sanity_and_partial_save`. |
| LAB-001-AC05 | COVERED | structured analyte contract and range/flag handling; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend`, `test_s11_result_validation_coded_sanity_and_partial_save`. |
| LAB-002-AC01 | COVERED | order/encounter linkage, multi-item, priority and signed-encounter refusal; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend` and PG release lane. |
| LAB-002-AC02 | COVERED | order/encounter linkage, multi-item, priority and signed-encounter refusal; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend` and PG release lane. |
| LAB-002-AC03 | COVERED | order/encounter linkage, multi-item, priority and signed-encounter refusal; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend` and PG release lane. |
| LAB-002-AC04 | COVERED | order/encounter linkage, multi-item, priority and signed-encounter refusal; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend` and PG release lane. |
| LAB-002-AC05 | COVERED | order/encounter linkage, multi-item, priority and signed-encounter refusal; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend` and PG release lane. |
| LAB-003-AC01 | PARTIAL | worklist sections, urgent sorting and clinician notes (worksheet/target display partly absent). |
| LAB-003-AC02 | PARTIAL | worklist sections, urgent sorting and clinician notes (worksheet/target display partly absent). |
| LAB-004-AC01 | COVERED | per-item invoice source lines and idempotent order; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend`, `test_s11_cancel_before_collection_voids_unpaid_line`. |
| LAB-004-AC02 | COVERED | per-item invoice source lines and idempotent order; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend`, `test_s11_cancel_before_collection_voids_unpaid_line`. |
| LAB-004-AC03 | PARTIAL | per-item invoice source lines and idempotent order; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend`, `test_s11_cancel_before_collection_voids_unpaid_line`. |
| LAB-004-AC04 | PARTIAL | per-item invoice source lines and idempotent order; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend`, `test_s11_cancel_before_collection_voids_unpaid_line`. |
| LAB-004-AC05 | BLOCKED | not enabled in the supplied core; per-item invoice source lines and idempotent order; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend`, `test_s11_cancel_before_collection_voids_unpaid_line`. |
| LAB-005-AC01 | BLOCKED | PAY_BEFORE laboratory gate/cashier/LAB queue integration is not supplied; no actionable unpaid release or override route invented. |
| LAB-005-AC02 | BLOCKED | PAY_BEFORE laboratory gate/cashier/LAB queue integration is not supplied; no actionable unpaid release or override route invented. |
| LAB-005-AC03 | BLOCKED | PAY_BEFORE laboratory gate/cashier/LAB queue integration is not supplied; no actionable unpaid release or override route invented. |
| LAB-005-AC04 | BLOCKED | PAY_BEFORE laboratory gate/cashier/LAB queue integration is not supplied; no actionable unpaid release or override route invented. |
| LAB-005-AC05 | BLOCKED | PAY_BEFORE laboratory gate/cashier/LAB queue integration is not supplied; no actionable unpaid release or override route invented. |
| LAB-005-AC06 | BLOCKED | PAY_BEFORE laboratory gate/cashier/LAB queue integration is not supplied; no actionable unpaid release or override route invented. |
| LAB-006-AC01 | COVERED | derived order status from item states; `order_status` and `test_s11_lab.py` state assertions. |
| LAB-006-AC02 | COVERED | derived order status from item states; `order_status` and `test_s11_lab.py` state assertions. |
| LAB-006-AC03 | COVERED | derived order status from item states; `order_status` and `test_s11_lab.py` state assertions. |
| LAB-006-AC04 | COVERED | derived order status from item states; `order_status` and `test_s11_lab.py` state assertions. |
| LAB-006-AC05 | COVERED | derived order status from item states; `order_status` and `test_s11_lab.py` state assertions. |
| LAB-006-AC06 | COVERED | derived order status from item states; `order_status` and `test_s11_lab.py` state assertions. |
| LAB-006-AC07 | PARTIAL | derived order status from item states; `order_status` and `test_s11_lab.py` state assertions. |
| LAB-007-AC01 | PARTIAL | worklist API/UI sections and per-item states; pagination, verify-disable tooltip and 200-item performance proof are absent. |
| LAB-007-AC02 | PARTIAL | worklist API/UI sections and per-item states; pagination, verify-disable tooltip and 200-item performance proof are absent. |
| LAB-007-AC03 | PARTIAL | worklist API/UI sections and per-item states; pagination, verify-disable tooltip and 200-item performance proof are absent. |
| LAB-007-AC04 | PARTIAL | worklist API/UI sections and per-item states; pagination, verify-disable tooltip and 200-item performance proof are absent. |
| LAB-007-AC05 | BLOCKED | not enabled in the supplied core; worklist API/UI sections and per-item states; pagination, verify-disable tooltip and 200-item performance proof are absent. |
| LAB-008-AC01 | COVERED | collection/specimen identity/audit; patient-facing LAB queue and label print remain fenced. |
| LAB-008-AC02 | PARTIAL | collection/specimen identity/audit; patient-facing LAB queue and label print remain fenced. |
| LAB-008-AC03 | BLOCKED | not enabled in the supplied core; collection/specimen identity/audit; patient-facing LAB queue and label print remain fenced. |
| LAB-008-AC04 | BLOCKED | not enabled in the supplied core; collection/specimen identity/audit; patient-facing LAB queue and label print remain fenced. |
| LAB-008-AC05 | BLOCKED | not enabled in the supplied core; collection/specimen identity/audit; patient-facing LAB queue and label print remain fenced. |
| LAB-008-AC06 | COVERED | collection/specimen identity/audit; patient-facing LAB queue and label print remain fenced. |
| LAB-009-AC01 | PARTIAL | rejection evidence and no duplicate charge; clinician 30-second worklist and reception recollection list are not built. |
| LAB-009-AC02 | PARTIAL | rejection evidence and no duplicate charge; clinician 30-second worklist and reception recollection list are not built. |
| LAB-009-AC03 | COVERED | rejection evidence and no duplicate charge; clinician 30-second worklist and reception recollection list are not built. |
| LAB-009-AC04 | COVERED | rejection evidence and no duplicate charge; clinician 30-second worklist and reception recollection list are not built. |
| LAB-010-AC01 | COVERED | all-analyte/not-done, sanity bounds, HIGH/LOW flag with no interpretation, unreleased invisibility; `test_s11_result_validation_coded_sanity_and_partial_save`, `test_s11_order_collect_enter_release_and_amend`. |
| LAB-010-AC02 | COVERED | all-analyte/not-done, sanity bounds, HIGH/LOW flag with no interpretation, unreleased invisibility; `test_s11_result_validation_coded_sanity_and_partial_save`, `test_s11_order_collect_enter_release_and_amend`. |
| LAB-010-AC03 | COVERED | all-analyte/not-done, sanity bounds, HIGH/LOW flag with no interpretation, unreleased invisibility; `test_s11_result_validation_coded_sanity_and_partial_save`, `test_s11_order_collect_enter_release_and_amend`. |
| LAB-010-AC04 | COVERED | all-analyte/not-done, sanity bounds, HIGH/LOW flag with no interpretation, unreleased invisibility; `test_s11_result_validation_coded_sanity_and_partial_save`, `test_s11_order_collect_enter_release_and_amend`. |
| LAB-010-AC05 | COVERED | all-analyte/not-done, sanity bounds, HIGH/LOW flag with no interpretation, unreleased invisibility; `test_s11_result_validation_coded_sanity_and_partial_save`, `test_s11_order_collect_enter_release_and_amend`. |
| LAB-011-AC01 | COVERED | coded options and INVALID-comment enforcement; printed/countable report path is absent. |
| LAB-011-AC02 | COVERED | coded options and INVALID-comment enforcement; printed/countable report path is absent. |
| LAB-011-AC03 | PARTIAL | coded options and INVALID-comment enforcement; printed/countable report path is absent. |
| LAB-012-AC01 | PARTIAL | 2000-character text path is accepted; template phrases and preserved-line-break printing are absent. |
| LAB-012-AC02 | PARTIAL | 2000-character text path is accepted; template phrases and preserved-line-break printing are absent. |
| LAB-013-AC01 | COVERED | released LabResultVersion snapshots value/unit/applied range; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend`. |
| LAB-013-AC02 | COVERED | released LabResultVersion snapshots value/unit/applied range; `test_s11_lab.py::test_s11_order_collect_enter_release_and_amend`. |
| LAB-014-AC01 | PARTIAL | partial saves stay DRAFT and are invisible; explicit completion moves to RESULT_ENTERED; `test_s11_result_validation_coded_sanity_and_partial_save`. |
| LAB-014-AC02 | COVERED | partial saves stay DRAFT and are invisible; explicit completion moves to RESULT_ENTERED; `test_s11_result_validation_coded_sanity_and_partial_save`. |
| LAB-014-AC03 | COVERED | partial saves stay DRAFT and are invisible; explicit completion moves to RESULT_ENTERED; `test_s11_result_validation_coded_sanity_and_partial_save`. |
| LAB-015-AC01 | PARTIAL | release is author-separated, rejected for self-entry, immutable afterwards and hash-audited; printable report remains absent. |
| LAB-015-AC02 | COVERED | release is author-separated, rejected for self-entry, immutable afterwards and hash-audited; printable report remains absent. |
| LAB-015-AC03 | COVERED | release is author-separated, rejected for self-entry, immutable afterwards and hash-audited; printable report remains absent. |
| LAB-015-AC04 | COVERED | release is author-separated, rejected for self-entry, immutable afterwards and hash-audited; printable report remains absent. |
| LAB-015-AC05 | PARTIAL | release is author-separated, rejected for self-entry, immutable afterwards and hash-audited; printable report remains absent. |
| LAB-016-AC01 | COVERED | default self-verification false; enabled policy sets self_verified (test); policy-change audit and printed/REP-009 marker are absent. |
| LAB-016-AC02 | PARTIAL | default self-verification false; enabled policy sets self_verified (test); policy-change audit and printed/REP-009 marker are absent. |
| LAB-016-AC03 | PARTIAL | default self-verification false; enabled policy sets self_verified (test); policy-change audit and printed/REP-009 marker are absent. |
| LAB-017-AC01 | PARTIAL | amendment creates a new retained version and audit references both hashes; encounter addendum/print history/alert are absent. |
| LAB-017-AC02 | BLOCKED | not enabled in the supplied core; amendment creates a new retained version and audit references both hashes; encounter addendum/print history/alert are absent. |
| LAB-017-AC03 | COVERED | amendment creates a new retained version and audit references both hashes; encounter addendum/print history/alert are absent. |
| LAB-017-AC04 | BLOCKED | not enabled in the supplied core; amendment creates a new retained version and audit references both hashes; encounter addendum/print history/alert are absent. |
| LAB-018-AC01 | PARTIAL | encounter result status projection exists; automatic AWAITING_RESULTS/RESULTS_READY state transitions and holds are not built. |
| LAB-018-AC02 | BLOCKED | not enabled in the supplied core; encounter result status projection exists; automatic AWAITING_RESULTS/RESULTS_READY state transitions and holds are not built. |
| LAB-018-AC03 | BLOCKED | not enabled in the supplied core; encounter result status projection exists; automatic AWAITING_RESULTS/RESULTS_READY state transitions and holds are not built. |
| LAB-018-AC04 | BLOCKED | not enabled in the supplied core; encounter result status projection exists; automatic AWAITING_RESULTS/RESULTS_READY state transitions and holds are not built. |
| LAB-018-AC05 | BLOCKED | not enabled in the supplied core; encounter result status projection exists; automatic AWAITING_RESULTS/RESULTS_READY state transitions and holds are not built. |
| LAB-018-AC06 | BLOCKED | not enabled in the supplied core; encounter result status projection exists; automatic AWAITING_RESULTS/RESULTS_READY state transitions and holds are not built. |
| LAB-018-AC07 | BLOCKED | not enabled in the supplied core; encounter result status projection exists; automatic AWAITING_RESULTS/RESULTS_READY state transitions and holds are not built. |
| LAB-019-AC01 | PARTIAL | released-only result read with access audit; inline encounter UI, unreleased status display and trends are absent. |
| LAB-019-AC02 | PARTIAL | released-only result read with access audit; inline encounter UI, unreleased status display and trends are absent. |
| LAB-019-AC03 | BLOCKED | not enabled in the supplied core; released-only result read with access audit; inline encounter UI, unreleased status display and trends are absent. |
| LAB-019-AC04 | COVERED | released-only result read with access audit; inline encounter UI, unreleased status display and trends are absent. |
| LAB-020-AC01 | BLOCKED | printable report and reprint audit are not supplied. |
| LAB-020-AC02 | BLOCKED | printable report and reprint audit are not supplied. |
| LAB-020-AC03 | BLOCKED | printable report and reprint audit are not supplied. |
| LAB-020-AC04 | BLOCKED | printable report and reprint audit are not supplied. |
| LAB-021-AC01 | BLOCKED | dashboard/stuck/unpaid/awaiting-verification reports are not built. |
| LAB-021-AC02 | BLOCKED | dashboard/stuck/unpaid/awaiting-verification reports are not built. |
| LAB-021-AC03 | BLOCKED | dashboard/stuck/unpaid/awaiting-verification reports are not built. |
| LAB-021-AC04 | BLOCKED | dashboard/stuck/unpaid/awaiting-verification reports are not built. |
| LAB-021-AC05 | BLOCKED | dashboard/stuck/unpaid/awaiting-verification reports are not built. |
| LAB-022-AC01 | COVERED | pre-collection cancellation voids the unpaid line; collected/paid cancellation, supervisor approval and credit note are fenced. |
| LAB-022-AC02 | BLOCKED | not enabled in the supplied core; pre-collection cancellation voids the unpaid line; collected/paid cancellation, supervisor approval and credit note are fenced. |
| LAB-022-AC03 | BLOCKED | not enabled in the supplied core; pre-collection cancellation voids the unpaid line; collected/paid cancellation, supervisor approval and credit note are fenced. |
| LAB-022-AC04 | PARTIAL | pre-collection cancellation voids the unpaid line; collected/paid cancellation, supervisor approval and credit note are fenced. |
| LAB-022-AC05 | PARTIAL | pre-collection cancellation voids the unpaid line; collected/paid cancellation, supervisor approval and credit note are fenced. |
| LAB-023-AC01 | BLOCKED | late-result addendum/acknowledgement/review is not built. |
| LAB-023-AC02 | BLOCKED | late-result addendum/acknowledgement/review is not built. |
| LAB-023-AC03 | BLOCKED | late-result addendum/acknowledgement/review is not built. |
| LAB-023-AC04 | BLOCKED | late-result addendum/acknowledgement/review is not built. |
| LAB-023-AC05 | BLOCKED | late-result addendum/acknowledgement/review is not built. |
| LAB-024-AC01 | BLOCKED | external orders and reception results-ready list are not built. |
| LAB-024-AC02 | BLOCKED | external orders and reception results-ready list are not built. |
| LAB-024-AC03 | BLOCKED | external orders and reception results-ready list are not built. |
| LAB-025-AC01 | BLOCKED | REFERRED_OUT action and ageing report are not built. |

## Fenced owner decisions

- Clinical interpretation, external/critical notification, unvalidated-range authority and unsupplied professional credentials remain OUT.
- Facility self-verification defaults FALSE; only an explicit facility policy enables self_verified and it is marked on the result.
- LAB-005 payable-before-collection gates, cashier/LAB queue integration, patient-facing labels/worksheets and external/reception notification are not built.
- Laboratory print reports/reprints, dashboards/REP reports, late-result addenda (LAB-023), external orders (LAB-024) and referral-out ageing (LAB-025) remain fenced.
- Released result values are immutable; corrections append a new version with reason and dual-hash audit. No interpretation, advice or suggested action is generated.

## Verification results

| Lane | Result |
| --- | --- |
| Full merged SQLite | 406 passed, 83 skipped |
| PostgreSQL as `clinicopus_app`, all families (S-00/auth/S-01..S-11) | 80 passed, 0 failed |
| S-11 PostgreSQL lane | 2 passed, 0 skipped |
| Disabled-guard proofs (S-02/S-03/S-04) | 3 passed |
| Browser, all fourteen specs | 23 passed |
| Static gates (check, migration drift, generated client, lint/typecheck/build, diff check) | pass |
| `check_rls --require-postgres` | enforced: true |

Red proof on base `ae4880f`: the S-11 test module cannot import `laboratory.models` before this candidate exists; green here.

## Hard invariants

- Every order is linked to an open Encounter and charged through billing-owned source lines; no duplicate line on replay.
- Results are entered against defined analytes with units and applied ranges stored on the immutable result version.
- Unvalidated ranges never authorize interpretation; no interpretive text or advice is generated.
- Self-verification defaults false; a different verifier releases unless the facility explicitly enables it.
- Released values are immutable; corrections append a new version with reason and dual-hash audit.
- All new laboratory tables have FORCE RLS and tenant policies.
