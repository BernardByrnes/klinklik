# S-15 coverage — supplied Appointment fragment

Base: `462be47` (accepted S-12 lineage). Worktree: `K:/klinklik-s15-fragment`, branch `codex/s15-appointment-fragment`.
Scope: **CMD-087 only** — the supplied `NO_SHOW -> CHECKED_IN` fragment. No general Appointment lifecycle, no Journey F, no scheduling/reminder UI, and no APT authority inferred.

## Acceptance map

| AC | Command | Status | Distinct evidence |
| --- | --- | --- | --- |
| REC-001-AC07 | CMD-087 `POST appointment_no_show_check_in` | COVERED | `test_s15_appointment_fragment.py` has 9 tests: the happy path asserts one `CHECKED_IN` appointment with `checked_in_visit` and `version=2`, one Visit/QueueEntry/Invoice with lines, and `APPOINTMENT_CHECKED_IN` + ordinary `VISIT_OPENED`/`QUEUE_ENTRY_CREATED`/`INVOICE_ISSUED` audits; the replay test asserts exact same-key replay with `Idempotent-Replay: true` and a new-key `already_checked_in=true` response with no duplicate Visit/queue/audit. `BOOKED`/`COMPLETED`/`CANCELLED` each return 409 `UNSUPPORTED_OPERATION` with no Visit; `CHECKED_IN` without a link returns 409 `ALREADY_EXISTS`; a NURSE is refused 403 while a RECEPTION_CASHIER succeeds; a cross-facility appointment is 404. `test_s15_postgres.py` has 3 tests: FORCE RLS on `scheduling_appointment`; two concurrent service calls produce exactly one `already_checked_in=false` winner, one Visit, `version=2`, one `APPOINTMENT_CHECKED_IN` and one `VISIT_OPENED`; the partial unique constraint refuses linking the same Visit to a second appointment. `test_s01_postgres.py` + `test_s02_postgres.py` regression: 31 passed. |

## Boundaries kept

- `scheduling.appointment.assert_no_show_fragment` refuses every status other than `NO_SHOW` and requires a service day and no existing Visit link.
- `link_checked_in_visit` is the only state mutation and sets exactly `CHECKED_IN` plus `checked_in_visit`.
- The application command reuses the ordinary check-in owner sequence inside one transaction; it never calls the CMD-001 HTTP command or nests idempotency.
- No Appointment create/book/cancel/reschedule/complete, reminder, Journey F, frontend, or scheduling UI was added.

## Compatibility and migration path

`backend/scheduling/migrations/0008_s15_appointment_fragment.py` adds `service_day`, `checked_in_visit`, `version`, the partial unique `(organisation, checked_in_visit)` constraint and the fragment lookup index; it backfills `service_day` from each legacy `scheduled_start` in Africa/Kampala and leaves all legacy status/reason/department values intact. It also applies FORCE RLS to `scheduling_appointment`. Reverse order drops the RLS policy, index, constraint and new fields; the backfilled compatibility value is derived, not invented. `makemigrations --check` is clean.

## Evidence files

- `backend/tests/test_s15_appointment_fragment.py` — 9 tests.
- `backend/tests/test_s15_postgres.py` — 3 tests.
- Full SQLite regression — see handback.
- S-01/S-02 PostgreSQL regression — 31 passed.
- Red proof: disabling both the command and owner-fragment status guards made all three `UNSUPPORTED_OPERATION` parameter cases fail with `201`; restoring the guards returned 9 passed.
