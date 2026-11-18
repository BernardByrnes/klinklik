# S-09 acceptance coverage — inventory and retail foundations

Base: `1a04012e91eb81648a262873e2bdcaaffedf7cbb` (`codex/s-08-closure`).
Candidate worktree: `K:/klinklik-s09-inventory` (`codex/s-09-inventory`).

Statuses: **COVERED** implemented and asserted; **PARTIAL** the supplied path works but an adjacent owner step is fenced or not built; **BLOCKED** deliberately not enabled with the owner decision named.

## Per-file test counts (fresh for this candidate)

| File | Tests | Inputs |
| --- | --- | --- |
| `backend/tests/test_s09_inventory.py` | 8 | receiving/expiry/idempotency, FEFO/splits, transfers/quarantine, adjustments/reconciliation/threshold, catalogue import, deactivation, expired refusal |
| `backend/tests/test_s09_postgres.py` | 3 | app-role FORCE RLS and guards, concurrent receipts, concurrent out movements |
| `frontend/tests/s09-inventory.spec.ts` | 1 | receive near-expiry stock, stock/ledger surface, expired refusal |

## Result: 62 IDs — COVERED 36, PARTIAL 16, BLOCKED 10

## Acceptance rows

| AC | Status | Evidence / fenced owner decision |
| --- | --- | --- |
| INV-001-AC01 | COVERED | ensure_default_location creates Main Pharmacy on demand; additional locations via configure_location. test_s09_inventory.py::test_s09_receive_creates_exact_ledger_and_idempotent_receipt and test_s09_transfer_and_expired_quarantine_rules. |
| INV-001-AC02 | COVERED | Balances are per batch+location; one configured default location. test_s09_transfer_and_expired_quarantine_rules asserts per-location balances and facility-total preservation. |
| INV-001-AC03 | PARTIAL | Delete is not exposed and deactivation exists, but deactivation does not yet require a stock transfer first; owner follow-up. |
| INV-002-AC01 | COVERED | Expired GRN line refuses the whole receipt with 422 EXPIRED_STOCK_CANNOT_BE_RECEIVED; test_s09_expired_receipt_is_refused_without_partial_records. |
| INV-002-AC02 | COVERED | Expiry inside 90 days is accepted and warning_near_expiry persisted; test_s09_receive_creates_exact_ledger_and_idempotent_receipt. |
| INV-002-AC03 | COVERED | Each line creates/reuses its batch, appends IN_GRN and increments the exact balance; same test. |
| INV-002-AC04 | COVERED | Same idempotency key replays the committed receipt with stock counted once; same test. |
| INV-002-AC05 | PARTIAL | Posted receipt/lines are immutable under the PG guard; printable GRN and adjustment-linked correction view are not implemented. |
| INV-003-AC01 | COVERED | Every movement has a required batch FK with expiry; test_s09_receive_creates_exact_ledger_and_idempotent_receipt. |
| INV-003-AC02 | COVERED | reconcile_ledger derives each balance from movements, mutates neither and audits PASSED/DISCREPANCY; test_s09_adjustment_reconcile_and_threshold. |
| INV-003-AC03 | COVERED | Zero balances are excluded from FEFO/usable totals while history remains; test_s09_fefo_selects_earliest_and_splits_without_expired. |
| INV-004-AC01 | COVERED | FEFO returns the earliest non-expired batch with batch/expiry/location; same test. |
| INV-004-AC02 | COVERED | FEFO returns an explicit expiry-ordered split; same test. |
| INV-004-AC03 | BLOCKED | Manual non-FEFO selection with mandatory reason and INV-016 report require the dispensing owner slice, not built. |
| INV-004-AC04 | COVERED | Only expired stock yields INSUFFICIENT_STOCK from FEFO; test_s09_fefo_selects_earliest_and_splits_without_expired. |
| INV-005-AC01 | COVERED | FEFO and stock_summary exclude expired batches from usable stock; same test. |
| INV-005-AC02 | COVERED | Direct expired batch transfers/adjustments refuse 422 EXPIRED_BATCH; test_s09_transfer_and_expired_quarantine_rules and test_s09_expired_positive_movement_never_increases_usable_stock. |
| INV-005-AC03 | COVERED | No override parameter or reason exists; the only positive expired path is explicit quarantine movement. Same two tests. |
| INV-005-AC04 | BLOCKED | Dispense reservation/confirmation is not built; no reservation can be re-checked. |
| INV-005-AC05 | COVERED | Positive expired movements are refused; expired transfers go only to quarantine and negative write-off is the disposal path. Tests above. |
| INV-005-AC06 | PARTIAL | Refusals are canonical and safe, but a blocked expired dispense attempt does not yet append a dedicated denial audit. |
| INV-006-AC01 | COVERED | Stock summary returns usable/expired totals, batch count, earliest expiry, per-location map and status chip; test_s09_receive_creates_exact_ledger_and_idempotent_receipt. |
| INV-006-AC02 | COVERED | GET /inventory/batches/ lists batch number, expiry, status and per-location quantities. |
| INV-006-AC03 | PARTIAL | Expired quantity is counted separately and flagged; a non-selectable dispense style cannot exist until dispensing is built. |
| INV-006-AC04 | PARTIAL | Search by name/code and status/category works; location filtering is not exposed on the summary. |
| INV-007-AC01 | COVERED | Paired TRANSFER_OUT/TRANSFER_IN preserve batch/expiry and facility total; test_s09_transfer_and_expired_quarantine_rules. |
| INV-007-AC02 | COVERED | Expired batches transfer only to a quarantine destination; same test. |
| INV-007-AC03 | COVERED | STOCK_TRANSFERRED audit records actor, source/destination and quantity; same test. |
| INV-007-AC04 | COVERED | Negative movements refuse INSUFFICIENT_STOCK; test_s09_postgres.py::test_pg_s09_concurrent_out_movements_cannot_oversell. |
| INV-008-AC01 | COVERED | Threshold rows produce LOW status with current quantity and level; test_s09_adjustment_reconcile_and_threshold. |
| INV-008-AC02 | PARTIAL | Rows without a threshold expose reorder_level null; an explicit thresholds-not-set list is not built. |
| INV-008-AC03 | COVERED | Adjustment below the level flips the summary to LOW; same test. |
| INV-008-AC04 | BLOCKED | CSV export of the low-stock list is not implemented. |
| INV-009-AC01 | PARTIAL | Expiring batches use the exact 90-day default and sort by expiry; a dedicated days-remaining list endpoint is not built. |
| INV-009-AC02 | PARTIAL | Expired batches are separately counted/flagged; a quarantine/write-off prompt is not built. |
| INV-009-AC03 | BLOCKED | Pharmacy dashboard counts are not built. |
| INV-009-AC04 | COVERED | Expiry state is computed on read from the batch date, so crossing midnight moves it without mutation; batch_expiry_state. |
| INV-012-AC01 | BLOCKED | Dispense/sale confirmation and same-outcome deduction require the pharmacy dispensing slice. |
| INV-012-AC02 | BLOCKED | Concurrent dispense confirmation is not built; movement-level oversell is covered by the PG race proof. |
| INV-012-AC03 | BLOCKED | Dispense reversal (DSP-016) is not built. |
| INV-012-AC04 | COVERED | Movement rows are append-only under klin_klink_stock_movement_immutable; test_s09_postgres.py::test_pg_s09_force_rls_and_append_only_guards. |
| INV-015-AC01 | PARTIAL | Suppliers are configurable and receipts reference them; a supplier-to-GRN list view is not exposed. |
| INV-015-AC02 | COVERED | Free-text supplier names remain accepted on receipts; StockReceipt.supplier_name and test_s09_receive_creates_exact_ledger_and_idempotent_receipt. |
| INV-016-AC01 | BLOCKED | FEFO deviation report requires the dispensing selection workflow, which is not built. |
| PHM-001-AC01 | PARTIAL | Product creation captures supplied identity/form/unit/category/controlled/active facts; classification authority and a dedicated product-form UI remain fenced. |
| PHM-001-AC02 | COVERED | Duplicate generic+strength+form returns 409 with the existing product and requires confirmation; create_product. |
| PHM-001-AC03 | COVERED | Product search matches generic, brand and code; search_products and test_s09_product_deactivation_requires_zero_stock. |
| PHM-001-AC04 | COVERED | Creation/update audit events emitted (MEDICATION_PRODUCT_CREATED; CATALOGUE_IMPORTED). |
| PHM-002-AC01 | COVERED | Per-facility unit price with optional pack price; test_s09_receive_creates_exact_ledger_and_idempotent_receipt. |
| PHM-002-AC02 | BLOCKED | Dispense/sale invoice-line price snapshot requires the pharmacy dispensing slice. |
| PHM-002-AC03 | PARTIAL | PRODUCT_PRICE_SET is audited and immutable rows retain history; a dedicated price-history view is not built. |
| PHM-002-AC04 | PARTIAL | No sale/dispense path exists to enforce it; the setup-warnings list is not built. |
| PHM-003-AC01 | PARTIAL | Prescribing search filters active non-controlled medicines; stock availability is not joined into that response. |
| PHM-003-AC02 | PARTIAL | Out-of-stock products remain searchable; the clinician prescribing journey is not built. |
| PHM-004-AC01 | COVERED | Zero-stock products deactivate and disappear from active search; test_s09_product_deactivation_requires_zero_stock. |
| PHM-004-AC02 | COVERED | Deactivation with stock refuses 409 and returns the quantity; same test. |
| PHM-004-AC03 | PARTIAL | Reactivation is not exposed; deactivation audit exists. |
| PHM-005-AC01 | BLOCKED | 300 ms p95 ranking benchmark and frequency-of-use ranking are not implemented. |
| PHM-006-AC01 | PARTIAL | CONSUMABLE/SUNDRY participate in stock and are excluded from prescribing search; consumables report is not built. |
| PHM-007-AC01 | COVERED | CSV validates every row with line numbers; ALL_OR_NOTHING refuses all on error and VALID_ROWS_ONLY imports only valid rows; test_s09_catalogue_import_is_atomic_and_controlled_rows_are_inactive. |
| PHM-007-AC02 | COVERED | Controlled rows import inactive with the flag set; same test. |
| PHM-007-AC03 | COVERED | CATALOGUE_IMPORTED audit records file name/hash, actor and counts; same test. |

## Fenced owner decisions

- CAT/OD-PH classification activation: import mechanics and the controlled flag work, but classification authority is unsupplied; controlled products are inactive and refused by receiving.
- Controlled/Class A medicines: refused in baseline V1 at product-receipt and movement boundaries; no partial controlled workflow.
- Pharmacy go-live, dispensing, FEFO deviation reporting, stock counts, supplier/consumption reports, adjustment approval thresholds and CSV exports remain fenced on their owning slices.
- Stock quantities are only written through `append_movement`; PostgreSQL rejects movement/receipt/price edits; expired stock never becomes usable.

## Verification results

| Lane | Result |
| --- | --- |
| Full merged SQLite | 395 passed, 78 skipped |
| PostgreSQL as `clinicopus_app`, all families (S-00/auth/S-01..S-09) | 74 passed; 1 failed on the known independent S-01 pricing 40P01 race (23P01 expected) |
| S-09 PostgreSQL lane | 3 passed, 0 skipped |
| Disabled-guard proofs (S-02/S-03/S-04) | 3 passed |
| Browser, all twelve specs | 21 passed |
| Static gates (check, migration drift, generated client, lint/typecheck/build, diff check) | pass |
| `check_rls --require-postgres` | enforced: true |

Red proof on base `1a04012`: the S-09 test module cannot import `inventory.models` (ModuleNotFoundError) before this candidate exists; green on this candidate.

## Hard invariants

- Stock quantities are written only by `append_movement`; no route edits a balance.
- Receipt/movement rows and product prices are immutable under PostgreSQL triggers; balances permit only quantity/version changes.
- Expired batches are never usable: receiving refuses them, FEFO excludes them, positive movements refuse them, transfers permit quarantine only.
- Controlled products are created inactive and refused at receiving/movement boundaries in baseline V1.
- FORCE RLS and tenant policies cover every new tenant table.
