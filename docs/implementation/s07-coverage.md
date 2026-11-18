# S-07 acceptance coverage — atomic ISSUED-to-ISSUED repricing

Base: `156422155079b254dccad278390b36acb92a257d` (`codex/s-06-corrections`).
Candidate worktree: `K:/klinklik-s07-repricing` (`codex/s-07-repricing`).

## Per-file test counts (fresh for this candidate)

| File | Tests | Inputs |
| --- | --- | --- |
| `backend/tests/test_s07_repricing.py` | 2 | atomic reprice/retention/replay, stale/paid/no-change refusals |
| `backend/tests/test_s07_postgres.py` | 3 | RLS/prior-version immutability, concurrent reprice, reprice-vs-payment |
| `backend/tests/test_s05_billing.py` | 9 | PRIOR money regression after current-set filtering |
| `backend/tests/test_s06_corrections.py` | 5 | PRIOR correction regression |
| `backend/tests/test_s06_mig010.py` | 2 | PRIOR MIG-010 regression |

## Acceptance IDs

| AC | Status | Evidence |
| --- | --- | --- |
| REC-003-AC01 | PRIOR | A Visit stays bound to its original price list; only an explicit CMD-003 repricing appends a new binding. Existing binding is superseded, never rewritten: `test_s07_repricing.py::test_s07_issued_invoice_reprices_atomically_with_retained_versions` asserts two binding versions with one active. |
| REC-003-AC02 | COVERED | One atomic `ISSUED → ISSUED` outcome with same Invoice ID/number, complete line-set version 2 appended, current pointer switched, gross/total recomputed to the new price, diff shown in the UI, `INVOICE_REPRICED` audited, prior set retained/immutable, replay creates no second set/audit, conflicting/stale/paid attempts refused with `VERSION_CONFLICT`, `PAYER_LOCKED` or `REPRICE_NO_CHANGE`: `test_s07_repricing.py` (2), `test_s07_postgres.py` (3). |
| REC-003-AC03 | COVERED | Any CONFIRMED/effective allocation makes repricing refuse with 409 `PAYER_LOCKED`; no payer, line or total change commits: `test_s07_repricing.py::test_s07_reprice_refuses_paid_partial_stale_and_conflicting_attempts`. |

## Implementation notes

- `reprice_invoice` locks Visit → Invoice → payer binding → current line set → target prices, revalidates the expected invoice version after locks, appends a complete `n+1` set, supersedes the payer binding (append-only guard now permits only `active: true → false`), switches `current_line_set_version` and recomputes in one transaction.
- `recompute_invoice_projection` now sums only the pointed line set; prior versions remain queryable and immutable. Line void/duplicate checks are scoped to the current set.
- `InvoiceItemSerializer.is_current` distinguishes retained versions. The billing page shows the old/new diff and a disabled action outside the eligible path.
- Migration `0010_s07_repricing_line_sets` replaces the payer-binding guard with a supersession-safe version and adds positive line-set checks. Reverse restores the original append-only guard.
- No migration backfill command is required; MIG-005 projection machinery already covers the resulting equations.

## Fenced

- No repricing of paid/partially-paid history.
- No S-06 credit/refund interaction; an invoice with correction evidence is refused.
- No payer switching beyond the supplied CMD-003 binding path.
- BIL-009 discount policy and fiscal claims remain unsupplied.
- S-08 not started.
