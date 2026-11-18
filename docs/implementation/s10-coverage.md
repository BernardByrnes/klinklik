# S-10 acceptance coverage — stock counts, quarantine and disposal

Base: `436ced41aec22d2a3e400ff62df1d4ed9aafbf3d` (`codex/s-09-inventory`).
Candidate worktree: `K:/klinklik-s10-counts` (`codex/s-10-counts`).

## Per-file test counts (fresh for this candidate)

| File | Tests | Inputs |
| --- | --- | --- |
| `backend/tests/test_s10_counts.py` | 6 | blind count/approval/counter-movement, threshold separation, standalone adjustments, missing threshold, quarantine/disposal, running ledger/export |
| `backend/tests/test_s10_postgres.py` | 3 | new-table FORCE RLS/guards, concurrent count approval, adjustment/quarantine races |
| `frontend/tests/s10-counts.spec.ts` | 1 | blind count → submit → approve → correction surface |

## Result: 17 IDs — COVERED 15, PARTIAL 1, BLOCKED 1

| AC | Status | Evidence / fenced owner decision |
| --- | --- | --- |
| INV-010-AC01 | COVERED | Quarantine movement removes stock from usable availability and moves it to a quarantine location; `test_s10_counts.py::test_s10_quarantine_then_disposal_is_append_only`, `test_s10_postgres.py::test_pg_s10_adjustment_and_quarantine_races_cannot_oversell`. |
| INV-010-AC02 | COVERED | Quarantined quantity remains in balances/reconciliation until disposal writes it off; same tests assert both buckets. |
| INV-010-AC03 | COVERED | `QuarantineRecord` retains reason/actor/time and `STOCK_QUARANTINED` audits; same test. |
| INV-011-AC01 | COVERED | Signed adjustment with mandatory structured reason, note and optional reference; `test_s10_standalone_adjustment_threshold_and_approval`. |
| INV-011-AC02 | COVERED | Above the configured facility threshold the adjustment stays `PENDING_APPROVAL` with no movement; a distinct FACILITY_ADMIN posts it. Same test plus `test_s10_above_threshold_count_needs_distinct_admin`. |
| INV-011-AC03 | COVERED | Posting appends a movement and balance change; posted rows are immutable under the PG trigger; `test_s10_postgres.py::test_pg_s10_count_tables_force_rls_and_count_immutability`. |
| INV-011-AC04 | COVERED | Positive adjustments into expired stock are refused unless the destination is quarantine; S-09 regression `test_s09_expired_positive_movement_never_increases_usable_stock` re-run here. |
| INV-011-AC05 | BLOCKED | REP-012 wastage report and disposal certificate/compliance export remain V1.1 pending pharmacist/regulatory validation. |
| INV-011-AC06 | COVERED | `STOCK_ADJUSTMENT_RECORDED`/`STOCK_ADJUSTED` audits record actor, reason and movement; `test_s10_standalone_adjustment_threshold_and_approval`. |
| INV-013-AC01 | COVERED | Blind count sheet hides expected quantities by default and reveals them only to an approver; `test_s10_counts.py::test_s10_blind_count_submits_and_posts_exact_correction`, `test_s10_counts.py` browser journey. |
| INV-013-AC02 | COVERED | Submitted lines retain counted/variance quantities and the approved sheet displays the variance; same tests. |
| INV-013-AC03 | COVERED | Approval creates `COUNT_CORRECTION` adjustments with exact signed movements; same test. |
| INV-013-AC04 | PARTIAL | Count sheet returns movements during the count; dispensing at the location does not exist yet, so the “dispensing allowed but flagged” branch is fenced on the pharmacy dispensing slice. |
| INV-013-AC05 | COVERED | Posted count becomes immutable; PG trigger `klin_klink_count_evidence_immutable` and the second-approval 409 test. |
| INV-014-AC01 | COVERED | Product ledger returns chronological movements with running balance, batch/location, actor/source and reason; `test_s10_ledger_running_balance_and_audited_export`. |
| INV-014-AC02 | COVERED | Running balance recomputed from zero equals the current projection; reconciliation proof re-run. |
| INV-014-AC03 | COVERED | Date/batch/type filters and audited CSV export are implemented; export test asserts `INVENTORY_LEDGER_EXPORTED`. |

## Fenced owner decisions

- OD-T3 single-user second-approver waiver is inactive; only the configured base threshold path exists, and above-threshold adjustments/counts require a distinct FACILITY_ADMIN.
- No permanent expiry override and no usable expired intake; expired disposal/write-off remains the only clearing path.
- Disposal certificates, compliance exports and REP-012 are V1.1 after pharmacist/regulatory validation.
- Dispensing-at-location flags and the pharmacy count integration await the dispensing owner slice.
- Adjustment threshold is configured on `FacilityWorkflowPolicy.stock_adjustment_approval_threshold`; no default is invented and an unset threshold refuses with `PREREQUISITE_MISSING`.
