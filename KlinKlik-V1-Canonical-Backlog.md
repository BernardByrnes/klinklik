# KlinKlik V1 Functional Specification

## 1. Document Status

**CANONICAL FUNCTIONAL BACKLOG — RECONCILED VERSION.**

- Reconciliation date: 2026-08-21.
- Supersedes all earlier concatenated/partial user-story drafts, including the multi-part generation drafts from which this document was reconciled (`userstoriesclinic1.md` and its copies).
- Source material supplied for reconciliation contained two overlapping generations of the REC/QUE/TRI epics plus one later-generation set of the ENC–ANC epics, with conflicting story numbering, triage terminology, queue states and lab status names. This document is the single authoritative reconciliation.
- **Scope note.** The supplied source defined stories for fourteen epics: `REC, QUE, TRI, ENC, LAB, DX, RX, PHM, INV, DSP, BIL, PAY, RCP, ANC`. The wider backlog also contains the epics `AUTH, TEN, USR, CAT, PAT, APT, REP, AUD, BRN, OPS` (stories AUTH-001 → PAT-007 and the Part 4–6 epics referenced as ~214 stories in total across six generation parts); **those story definitions were not part of the supplied source** and are therefore not reproduced here. References to those epics (e.g. `TEN-005`, `PAT-009`, `REP-004`, `AUD-008`, `OPS-004`) are retained verbatim as **external references** and are catalogued in §31.2. No story from an unsupplied epic has been invented.
- Canonical unique stories in this document: **194** (see §27 Priority Summary and §32 Reconciliation Log for the count reconciliation).

---

## 2. Executive Summary

KlinKlik V1 is a single platform for a private outpatient **CLINIC**, **PHARMACY**, or **CLINIC + PHARMACY** facility in Uganda, built around one attendance loop: a person becomes a **Visit** at reception, is observed at triage, is seen by a clinician in a long-lived **Encounter**, may loop through the laboratory and pharmacy without losing their place, pays at a cash desk with manual cash/Mobile-Money rigour, and leaves with printed, statutory-quality documents. The queue is the location spine; every handoff is an explicit, auditable queue transition; no patient can silently disappear between departments.

The clinical record is deliberately conservative: signed notes are immutable and corrected only by attributed addenda; the laboratory loop keeps unverified results invisible to clinicians; expired KlinKlik-managed stock can never be issued, dispensed, sold, or used by any role through any path; and the platform provides **no clinical decision support** — no diagnosis suggestion, no dose or interaction checking, no automatic acuity computation. Observations may be flagged against reference ranges, but clinical judgement always belongs to a named human provider.

Money is treated as carefully as medicine: every chargeable act raises exactly one invoice line, payments are immutable and reversible-only, cashier shifts reconcile, and gated services (pay-before-lab, pay-before-pharmacy) are enforced by the platform while remaining overridable by authorised humans with reasons. Stock moves only through an append-only ledger with batch and expiry control, FEFO proposal, and quarantine/disposal paths.

This document reconciles the full V1 functional backlog for the fourteen supplied epics into one canonical specification: stories, state machines, handoff matrix, permissions matrix, audit catalogue, pilot-core selection and implementation waves.

---

## 3. Actors and Roles

Canonical role vocabulary (technical role IDs). Human-facing prose may say "doctor", but permission definitions use exactly these IDs.

| Role | Meaning |
| --- | --- |
| `SYS_ADMIN` | Platform-level operator (hosting/support), no clinical or financial data access by default. |
| `ORG_OWNER` | Owner of the organisation (tenant root). May set controlled-medicine flags; sees segregation-of-duties reporting. |
| `ORG_ADMIN` | Organisation administrator (tenant-level administration). |
| `FACILITY_ADMIN` | Administrator of one facility (branch): departments, price lists, policies, catalogue setup, force-close, gate overrides. |
| `SUPERVISOR` | Senior in-facility role: overrides, approvals, takeovers, dashboards, force-close. |
| `RECEPTIONIST` | Front desk: check-in, visits, routing, attendance list, closure at exit desk. Never enters clinical content. |
| `NURSE` | Triage, vitals, allergies, repeat observations, treatment-room procedures. |
| `MIDWIFE` | ANC contacts and midwifery clerking; clinician-equivalent permissions within ANC scope. |
| `CLINICIAN` | Doctor / medical officer / clinical officer: clerking, diagnosis, prescriptions, signing encounters. |
| `LAB_TECH` | Laboratory technician: specimen collection, result entry. |
| `LAB_VERIFIER` | Laboratory in-charge: result verification and release (may be same person as LAB_TECH under LAB-016 configuration). |
| `PHARMACIST` | Dispensing, retail sales, pharmacy catalogue, stock. |
| `STORE_KEEPER` | Goods receipt, stock movements, counts. |
| `CASHIER` | Payments, receipts, shifts. |
| `SYSTEM` | Automated platform actor (derived status, gates, sweeps, event fan-out). Audited as `SYSTEM`. |

Aliases found in the source drafts and normalised: "Doctor", "Doctor User", "Medical Officer" → `CLINICIAN` in all technical contexts; "lab in-charge" → `LAB_VERIFIER`; "triage nurse" → `NURSE`.

---

## 4. Product / Operating Assumptions

Compiled from the story set; they constrain every story below.

1. **Ugandan private-sector facility** (initial pilot: single-branch medical centre, Kampala), EAT timezone, UGX currency.
2. **One organisation = tenant root**; a facility is a branch, not a tenant. Cross-facility reads fail closed (404, not 403).
3. **Low-bandwidth, unreliable power** operations: list APIs ≤400 ms p95 and rendered worklists ≤2 s p95 on the 3G-equivalent profile (§7), autosave with visible save-state, no offline completion of stock, money, dispensing or clinical sign-off.
4. **No insurance in V1**; payer types are `CASH` and `SELF_PAY_MOMO` only.
5. **No direct Mobile Money/bank/card API integration**; MoMo references are operator-entered evidence only.
6. **Pay-before gating is configurable** per service family (`PAY_BEFORE` / `PAY_AFTER` / no gate) — the dominant Ugandan private-sector rule is pay-before.
7. **Small-clinic laboratory reality**: one technician, RDTs/microscopy/haematology analyser, minutes-scale bench work, batch verify-and-release.
8. **Pharmacy is retail as well as dispensing**: OTC walk-in sales are a large share of revenue; NDA inspection expects a dispensing register.
9. **Statutory alignment is manual**: HMIS Form 031 (OPD register), HMIS Form 071 (ANC record) shape reporting exports, which are aids for manual register completion — not certified HMIS/DHIS2 submissions.
10. **Paper remains the fallback** for every print flow (labels, slips, reports) — the system must degrade to screen-displayable documents.
11. **AS-11 (referenced assumption)**: KlinKlik V1 performs **no clinical decision support** — no interaction or contraindication checking, no dose checking, no acuity computation from vitals, no diagnosis suggestion, no interpretation of results. All displays of reference ranges/flags are neutral.
12. **Controlled / Class A medicines are unsupported in baseline V1** (RX-008); expired KlinKlik-managed stock can never be issued, dispensed, sold, or used (INV-005).
13. **Signed clinical records are immutable**; corrections occur through addenda/amendments/versioning, never destructive rewrites.
14. **PHI protection**: no PHI in localStorage/sessionStorage/IndexedDB, no PHI in logs/telemetry/audit payloads, access tokens in memory only, no SSR of patient charts.
15. **Every mutation is audited**; money, clinical and stock creations are idempotent (Idempotency-Key); concurrent edits use ETag/If-Match.

---

## 5. End-to-End Journeys

Canonical journeys. Every journey must be realisable story-by-story with no dead end, no duplicated encounter, no duplicated charge or payment, and every handoff landing on a receiving worklist.

**JOURNEY A — Simple outpatient.**
Reception (REC-001/002, REC-003/004) → Triage (TRI-001..007, TRI-009, TRI-011) → Clinician (ENC-001, ENC-005..017, DX-001/002/004/006) → Billing (BIL-001..006) → Payment (PAY-002/003/005) → Receipt (RCP-001) → Visit closure (REC-012). Every chargeable OPD consultation receives exactly one consultation invoice line at check-in; encounter signing never creates a second consultation line.

**JOURNEY B — Outpatient with laboratory.**
Reception → Triage → Clinician clerking (ENC-001) → Lab order (LAB-002/004) → clinician parks the SAME encounter (ENC-016) and holds the consultation queue entry (QUE-006). Under `LABORATORY=PAY_BEFORE`, the LabOrderItems are visible only as non-actionable laboratory worklist items in `AWAITING_PAYMENT` while the patient is on a cashier `QueueEntry=WAITING`; no patient-facing laboratory QueueEntry exists yet. Qualifying payment completes the cashier entry, moves paid items to `READY_FOR_COLLECTION`, and creates `QueueEntry(LAB)=WAITING`. Under `PAY_AFTER`/no gate, the lab QueueEntry may be created immediately. The laboratory QueueEntry is the patient-facing service movement and progresses `WAITING → CALLED → IN_SERVICE → COMPLETED` when the collection/receipt interaction ends; bench processing continues independently on the LabOrderItems (`SAMPLE_COLLECTED → RESULT_ENTERED → VERIFIED → RELEASED`). The held consultation entry is the return obligation, and the two entries coexist with at most one `IN_SERVICE` at any instant. Partial released results are immediately readable with "n of m results ready" progress; the encounter leaves `AWAITING_RESULTS` only when every blocking item is `RELEASED` or `CANCELLED` → consultation entry `READY_TO_RESUME` → SAME clinician encounter resumed (ENC-002; manual early resume is supported) → results reviewed (LAB-019) → diagnosis/treatment (DX) → sign (ENC-017) → billing/payment → closure. If the patient leaves before results, ENC-018 signs the encounter with pending orders and atomically completes the held consultation entry (`COMPLETED`, reason `SIGNED_WITH_PENDING_RESULTS`) before a `CLOSED(PENDING_RESULTS)` visit closure; late results follow LAB-023 without reopening the visit, the encounter or the entry.

**JOURNEY C — Prescription/pharmacy.**
Clinician (ENC-017) → Prescription (RX-001..005) → Pharmacy queue (DSP-001/002) → FEFO stock allocation (INV-004, DSP-003) → under `MEDICINE=PAY_BEFORE` the provisional Dispense is created `AWAITING_PAYMENT` and the same pharmacy entry holds `ON_HOLD(AWAITING_PAYMENT)` while the cashier entry is the active location (DSP-008); qualifying payment completes the cashier entry and flags the same pharmacy entry `READY_TO_RESUME` (PAY-012) → resumed handover confirms the SAME Dispense `DISPENSED` (DSP-009) → stock deduction once (INV-012) → closure. Abandonment variant: an unpaid provisional Dispense the patient declines or cannot afford exits atomically via DSP-005 (`Dispense → CANCELLED`, unpaid lines voided, pharmacy/cashier entries terminal, prescription `NOT_DISPENSED` or retained `PARTIALLY_DISPENSED`). Paid pre-handover revision variant: batch-only reselection is non-financial (versioned); value changes use BIL-010 credit notes and new source-versioned lines (DSP-007).

**JOURNEY D — Lab + pharmacy.**
Reception → Triage → Doctor → Lab → Doctor resumes SAME encounter (ENC-002) → Prescription → Pharmacy (pay-before: hold → cashier → resume per DSP-008) → Payment/Dispense → closure. At no moment are two queue entries `IN_SERVICE`.

**JOURNEY E — ANC.**
Check-in (visit type `ANC`, REC-004) → ANC provider (ANC-001/002) → documentation (ANC-003..006) → investigation if required (ANC-007 via LAB loop) → medication/supplements if prescribed (RX) → follow-up appointment (DX-008/APT-001) → billing/payment where applicable.

> Note: the source drafts reference a Journey F within a fuller A–F journey set defined in an unsupplied part of the backlog. Journeys A–E above are fully specified by the supplied stories and are canonical; Journey F is not reconstructed.

---

## 6. Epic Catalogue

Canonical order follows the blueprint epic sequence. Fourteen epics are supplied and canonical here; ten further epics exist in the wider backlog and are referenced externally (§1, §31.2).

| # | Epic | Name | Stories | P0 | P1 | P2 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `REC` | Reception & Check-In | 13 | 7 | 4 | 2 |
| 2 | `QUE` | Queue Management | 16 | 7 | 8 | 1 |
| 3 | `TRI` | Triage | 13 | 8 | 5 | 0 |
| 4 | `ENC` | Clinical Encounter / Doctor Clerking | 24 | 18 | 4 | 2 |
| 5 | `LAB` | Laboratory Orders and Results | 25 | 20 | 4 | 1 |
| 6 | `DX` | Diagnosis and Treatment | 10 | 5 | 3 | 2 |
| 7 | `RX` | Prescriptions | 11 | 7 | 2 | 2 |
| 8 | `PHM` | Pharmacy Catalogue | 8 | 3 | 4 | 1 |
| 9 | `INV` | Inventory and Stock | 16 | 10 | 4 | 2 |
| 10 | `DSP` | Pharmacy Dispensing and Retail | 16 | 11 | 5 | 0 |
| 11 | `BIL` | Billing and Invoicing | 14 | 9 | 5 | 0 |
| 12 | `PAY` | Cashier and Payments | 14 | 11 | 2 | 1 |
| 13 | `RCP` | Receipts and Printing | 7 | 5 | 2 | 0 |
| 14 | `ANC` | Antenatal Care | 7 | 7 | 0 | 0 |
| | | **Total (supplied, canonical)** | **194** | **128** | **52** | **14** |
| ext | `AUTH TEN USR CAT PAT APT REP AUD BRN OPS` | Wider-backlog epics (definitions not supplied) | — | — | — | — |

---

## 7. Global Story Contract

Applies to every story below; it is part of each story's acceptance criteria and is not repeated per story.

| Default | Rule |
| --- | --- |
| Tenancy | Every query is filtered by `organisation_id` + `facility_id` from session context, enforced at the PostgreSQL RLS layer, not only in the ORM. Cross-facility reads default to 404 (not 403), so record existence is not leaked. An exception exists only where an explicitly authorised external `BRN` cross-facility-sharing policy grants a dedicated capability: it remains within the same organisation, is audited, and never weakens cross-tenant RLS. |
| Permission denial | Missing permission → HTTP 403, no partial data, no record IDs in the error body. The UI hides the control **and** the API rejects. |
| Audit | Every mutation writes `audit_event(actor_user_id, actor_role, organisation_id, facility_id, entity_type, entity_id, record_version_id, action, changed_field_names, reason, before_json, after_json, ip, user_agent, request_id, occurred_at)`. The generic AuditEvent contains only non-PHI operational/audit metadata; `before_json`/`after_json`, if used, are redacted non-PHI metadata only. It may retain version references and content hashes, never raw vital values, diagnoses, clinical text, lab values, allergies, medication text, or clinical JSON dumps. Clinical reconstruction uses the immutable/versioned domain record itself. Every patient-chart read writes one `category=PHI_READ, action=PATIENT_RECORD_VIEWED` event. No PHI in logs, telemetry or audit payloads. |
| Idempotency | All POSTs that create money, clinical or stock records accept `Idempotency-Key`; replay returns the original 201 body. |
| Concurrency | Mutable records return `ETag`; `If-Match` required on PUT/PATCH; mismatch → 409 (412 where the contract specifies) with the server's current version. Payment allocation additionally locks the invoice/allocation rows, recomputes the current outstanding balance inside the transaction, validates allocations, then commits the payment and invoice state. A later concurrent request that exceeds the recomputed balance returns 409 `BALANCE_CHANGED` with the current outstanding balance; no overpayment is silently created unless facility credit balances are explicitly enabled. |
| Validation | The server is authoritative. Client validation is convenience only. |
| UI | Two performance targets. **Server/API:** interactive list API operations ≤ 400 ms p95 under the agreed reference dataset at normal load, excluding network/render time. **End-to-end:** primary worklist usable/rendered state ≤ 2 s p95 under the agreed 3G-equivalent test profile. Individual stories may set stricter targets. All screens keyboard-operable, no PHI in localStorage/sessionStorage/IndexedDB, access token in memory only. Loading, empty and error states are explicit (never a blank panel). |
| Tests | Each story ships: unit tests on the service function, API contract tests incl. 403/404/409, one UI happy path, one negative path, one tenant-isolation test. |

**Story field conventions.** Every story carries the fields: `ID · Title · Priority · Primary role · Secondary roles` followed by **Story** (user story + value), **Pre** (preconditions), **Trig** (trigger), **Flow** (main flow), **Alt** (alternate flows), **AC** (acceptance criteria, GIVEN/WHEN/THEN), **Perm**, **Data**, **Audit**, **Err** (errors/edge cases), **UI**, **Dep** (dependencies), **OOS** (out of scope), **Test**. Compact form is used throughout; the contract above supplies the defaults.

**Canonical vocabulary.** `Visit`, `QueueEntry`, `TriageRecord`, `Encounter`, `LabOrder`/`LabOrderItem`, `Prescription`, `Dispense`, `Invoice`/`InvoiceLine`, `Payment`/`PaymentAllocation`, `Receipt`. Queue priority and triage acuity vocabulary is exactly `EMERGENCY | URGENT | ROUTINE`. Lab item entry status is `ORDERED` (never "REQUESTED"). Queue entries belong to a **department** (service point) whose **queue_type** is one of `TRIAGE, CONSULTATION, ANC, LAB, PHARMACY, CASHIER`. A queue entry's enqueue timestamp is `queued_at`.

---

## 8. EPIC REC — Reception & Check-In

Purpose: turn a person standing at the desk into a **Visit** record with a queue position, correct payer type, and correct first destination. Reception never enters clinical content.

**REC-001 · Check in a patient and open a Visit · P0 · `RECEPTIONIST`; secondary `FACILITY_ADMIN`, `NURSE`**
**Story** As a receptionist, I want to check in a patient (returning or from an appointment) so that a Visit is opened and the patient appears on today's queue for triage. **Value** The single entry point of the attendance loop; without it no downstream record has a parent and daily attendance cannot be counted for HMIS 031.
**Pre** Patient record exists in this facility's tenant (PAT-001/PAT-003); receptionist authenticated with a facility selected; facility `ACTIVE`; at least one active check-in destination department (TEN-005).
**Trig** Receptionist searches the patient, opens the patient summary, clicks **Check in** — or checks in from today's appointments panel.
**Flow** Check-in panel shows patient name, age, sex, facility patient number, last visit date, outstanding balance (if any), allergy flag banner → select **Visit type** (`OUTPATIENT_NEW`, `OUTPATIENT_REVIEW`, `ANC`, `LAB_ONLY`, `PHARMACY_ONLY`, `FOLLOW_UP_RESULTS`) → select **Payer** (`CASH`, `SELF_PAY_MOMO`; REC-003) → optional administrative **reason for visit** (≤120 chars, not a clinical complaint) → **Destination department** defaults from visit type (REC-004) → confirm → `Visit(state=OPEN)` + `QueueEntry(state=WAITING)` for the destination department, visit number from the facility scheme (TEN-007); for every chargeable OPD consultation visit, regardless of consultation payment-timing policy, an invoice is created with exactly one consultation line and is **automatically `ISSUED`** (facility invoice number, TEN-007) on the successful check-in commit — `DRAFT` exists only transiently while the invoice is constructed/repriced within the transaction (BIL-001/002, §22.8); payment-timing policy controls only whether payment gates progression. `LAB_ONLY` and `PHARMACY_ONLY` receive no consultation line → visit slip printed/offered (REC-006, RCP-002) with visit number, queue token, date, facility header.
**Alt** (a) Patient already has an OPEN visit today → block, show the existing visit with state and location, "Go to existing visit" (REC-005/REC-011). (b) Outstanding balance from a prior visit → warning banner with amount and prior visit number; may proceed (V1 does not hard-block care for debt), audited. (c) `PAY_BEFORE_TRIAGE` policy → queue entry created `WAITING_PAYMENT`, absent from the triage list until the consultation lines are paid (PAY-002/PAY-012). (d) Destination department disabled mid-session → validation error, pick another. (e) **Appointment check-in**: if the appointment specifies a clinician, the resulting queue entry is routed to that clinician's list (QUE-004); a "no-show" appointment arriving later the same day can still be checked in and the appointment moves `NO_SHOW → CHECKED_IN` with an audit entry.
**AC** GIVEN an active patient with no open visit WHEN check-in is confirmed with type `OUTPATIENT_NEW` and payer `CASH` THEN a `Visit(OPEN, opened_at, opened_by)` and a `QueueEntry(WAITING, queue_type=TRIAGE)` exist for the destination department. GIVEN the same patient checked in again the same day at the same facility THEN 409 `VISIT_ALREADY_OPEN` with the existing `visit_id`, and no second Visit or QueueEntry is created. GIVEN a chargeable OPD consultation priced UGX 20,000 under any consultation payment-timing policy THEN on check-in commit exactly one consultation line exists and the invoice is `ISSUED` with a facility invoice number (never left `DRAFT` — §22.8). GIVEN `LAB_ONLY` or `PHARMACY_ONLY` THEN no consultation line exists. GIVEN `PAY_BEFORE_TRIAGE` THEN the entry is `WAITING_PAYMENT` and absent from the triage queue. GIVEN two facilities in one organisation WHEN facility B requests facility A's visit THEN 404 unless the explicit BRN exception in §7 authorises the same-organisation read. GIVEN an appointment-driven check-in for a no-show appointment THEN check-in succeeds and the appointment status moves to `CHECKED_IN` with audit; two receptionists checking in the same appointment concurrently → exactly one succeeds (unique constraint + 412). GIVEN check-in confirmed THEN `VISIT_OPENED` and `QUEUE_ENTRY_CREATED` audit events exist with actor and visit; `patient.last_seen_at` updates.
**Perm** `visit.create` (RECEPTIONIST, FACILITY_ADMIN, NURSE) + `appointment.read` for appointment check-in; `visit.read` to view; clinicians hold `visit.read` not `visit.create` unless granted.
**Data** Insert `visit`, `queue_entry`; for a chargeable OPD consultation, `invoice` + exactly one `invoice_line` (source `CONSULTATION`) at check-in; `Visit.appointment_id`. No clinical fields written.
**Audit** `VISIT_OPENED`, `QUEUE_ENTRY_CREATED`, conditional `INVOICE_ISSUED`, conditional `OUTSTANDING_BALANCE_OVERRIDDEN`, appointment link.
**Err** Duplicate open visit → 409. Inactive patient → 422 `PATIENT_INACTIVE`. Missing consultation price → 422 `SERVICE_NOT_PRICED` with the service code; check-in refused (no free care by accident). Double appointment check-in → unique constraint + 412. Double-submit → idempotency key returns the original visit.
**UI** Single screen, no modal chain; payer and visit type are radio groups; confirm disabled until visit type + destination chosen; after success focus returns to patient search; visit number displayed large for verbal call-out; today's appointments panel with inline Check-in.
**Dep** PAT-001, PAT-003, TEN-005, TEN-006, TEN-007, CAT-002, APT-001..003, QUE-001, REC-003, REC-004, BIL-001, BIL-002.
**OOS** Insurance/scheme selection, reminders, self-check-in, triage vitals, clinical complaint coding, patient photo capture.
**Test** Table test across 6 visit types × gating policies; concurrency (two receptionists, one visit); appointment double-check-in guard; the invoice reaches `ISSUED` on check-in commit with exactly one consultation line.

**REC-002 · Register and check in a new walk-in in one flow · P0 · `RECEPTIONIST`**
**Story** As a receptionist, I want to register a brand-new patient and check them in without navigating between modules, so the desk queue does not back up during morning rush. **Value** ~30–40% of daily attendance at a new private clinic is first-time patients; a two-module flow doubles desk time.
**Pre** `patient.create` + `visit.create`; facility active.
**Trig** Patient search (PAT-003) returns no match; **Register new patient**.
**Flow** Registration form (PAT-001 fields: names, sex, DOB or estimated age, phone, village/parish/sub-county/district, next of kin name + phone) → duplicate detection (PAT-002) before persisting → patient created with facility patient number → flow continues directly into the REC-001 check-in panel with the patient pre-selected → complete visit type/payer/destination → confirm.
**Alt** (a) Probable duplicate → candidate list with match score and last visit date; "Use this patient" (continue with existing) or "Not the same — create new" (reason captured, audited). (b) Registration succeeds but check-in fails (e.g. `SERVICE_NOT_PRICED`) → patient retained, error shown, retryable; no orphaned visit; patient creation and visit creation are separate transactions so a visit can never exist without a patient.
**AC** GIVEN a completed form with no duplicate match THEN a `Patient` is created with a configured-scheme number AND the UI lands on the check-in panel with the patient bound in one navigation step. GIVEN surname + sex + DOB exactly matching an existing patient THEN the API returns 200 with `duplicate_candidates[]` (not 201) and nothing is created until resolved. GIVEN "Not the same" with a reason THEN the patient is created AND `DUPLICATE_OVERRIDE` records the reason and rejected candidate IDs. GIVEN check-in then fails with `SERVICE_NOT_PRICED` THEN the patient exists exactly once and zero visits exist.
**Perm** `patient.create` + `visit.create` both required for the combined flow; `patient.create` alone stops at the patient summary.
**Data** Insert `patient`, identifiers, contacts, then `visit`, `queue_entry`.
**Audit** `PATIENT_CREATED`, optional `DUPLICATE_OVERRIDE`, then REC-001 events.
**Err** As PAT-001 + REC-001; network failure between the two writes must not create a visit without a patient.
**UI** Two-pane: form left, live duplicate-candidate panel right (debounced 400 ms). Age may be entered in years when DOB unknown → `dob_estimated=true` (common in Uganda).
**Dep** PAT-001, PAT-002, PAT-004, REC-001.
**OOS** NIN verification against NIRA, biometric capture, photograph.
**Test** Duplicate matrix (exact name+DOB, phonetic variant, same phone different name, same name different sex); partial-failure behaviour.

**REC-003 · Select and record payer type and price list for the visit · P0 · `RECEPTIONIST`; secondary `CASHIER`**
**Story** As a receptionist, I want the visit's payer type recorded at check-in so every charge raised later uses the right price and the cashier knows how payment will be collected. **Value** Prevents end-of-day reconciliation disputes and MoMo payments recorded as cash.
**Pre** At least one active price list (CAT-002); visit being created or `OPEN` and unbilled.
**Trig** Payer selection during REC-001, or **Change payer** on an open visit before any payment exists.
**Flow** Pick `CASH` or `SELF_PAY_MOMO`; bind `visit.payer_type` and `visit.price_list_id`. All subsequent charge capture reads the bound price list, not the live default, so mid-day price changes do not retroactively alter open visits.
**Alt** (a) Payer changed after charges exist but before payment → recalculate all `DRAFT` lines against the new price list with a before/after diff, confirmation, audited delta. (b) After any payment → blocked (409 `PAYER_LOCKED`); supervisor-approved adjustment only (BIL-010).
**AC** GIVEN a visit bound to price list "Standard 2026" WHEN a new list is published at 14:00 THEN charges added at 15:00 still use "Standard 2026". GIVEN an unpaid, unpartially-paid invoice of 20,000 re-priced to 25,000 (before any payment; the invoice may be re-priced while unpaid, per §22.8 — `DRAFT` exists only transiently during construction/repricing) THEN the UI shows the diff (+5,000), confirmation applies it, and `INVOICE_REPRICED` records old/new totals. GIVEN any `CONFIRMED` payment WHEN payer change is attempted THEN 409 `PAYER_LOCKED`.
**Perm** `visit.update_payer` (RECEPTIONIST, CASHIER, FACILITY_ADMIN).
**Data** `visit.payer_type`, `visit.price_list_id`; unpaid-line re-pricing only (pre-payment).
**Audit** `VISIT_PAYER_SET`, `INVOICE_REPRICED`.
**Err** No active price list → 422 `NO_PRICE_LIST`, check-in blocked.
**UI** Payer shown as a persistent chip in the visit header for every downstream role.
**Dep** CAT-002, TEN-006, BIL-002.
**OOS** Insurance, corporate accounts, split payer, discounts (BIL-009).
**Test** Price-list immutability across a publish event.

**REC-004 · Route the checked-in patient to the correct first destination · P0 · `RECEPTIONIST`**
**Story** As a receptionist, I want visit type to drive the first queue automatically so a lab-only or pharmacy-only walk-in is not forced through triage and a consultation. **Value** A patient collecting results or buying prescribed medicines should not consume a clinician slot or be charged a consultation fee.
**Pre** TEN-005 routing rules configured.
**Trig** Visit type selection in REC-001.
**Flow** Resolve destination: `OUTPATIENT_*` → TRIAGE queue; `ANC` → ANC/midwife queue (skips general triage; ANC has its own vitals set); `LAB_ONLY` → LAB queue, no consultation charge; `PHARMACY_ONLY` → PHARMACY queue, no consultation charge; `FOLLOW_UP_RESULTS` → CLINICIAN queue directly with `results_review=true`.
**Alt** (a) Override the default destination → allowed, reason optional, audited. (b) `FOLLOW_UP_RESULTS` with no released results → warning "No released results found"; override permitted.
**AC** GIVEN `LAB_ONLY` THEN `queue_type=LAB`, no consultation line, absent from triage list. GIVEN `FOLLOW_UP_RESULTS` with a lab order item in `RELEASED` THEN the clinician queue entry shows a "Results ready (n)" badge and links to the released results and the original encounter. GIVEN `ANC` THEN the entry lands on the ANC queue and the triage count is unchanged. GIVEN an override THEN `ROUTING_OVERRIDDEN` records default and chosen destinations.
**Perm** `visit.create`; override uses the same permission (no separate gate in V1).
**Data** `queue_entry.queue_type`, `queue_entry.department_id`, `visit.results_review_flag`.
**Audit** `ROUTING_OVERRIDDEN` when non-default.
**Err** No department of the required type → 422 with a facility-setup link (admin-only link).
**UI** Destination preview line before confirmation: "This patient will go to: Triage — Room 2".
**Dep** TEN-005, QUE-001, LAB-015.
**OOS** Skill/load-balanced routing, appointment-driven routing.
**Test** One case per visit type verifying queue type, charge creation, list membership.

**REC-005 · Block or warn on duplicate open visit · P0 · `RECEPTIONIST`**
**Story** As a receptionist, I want the system to stop me creating a second visit for a patient already in the building, so queue and attendance counts stay accurate. **Value** Duplicate visits inflate HMIS attendance, split the clinical record across two encounters, and create two invoices for one episode.
**Pre** Patient has a `Visit` in `OPEN` or `IN_PROGRESS` at this facility.
**Trig** Check-in attempt.
**Flow** Detect the open visit; present it with current state, queue/location, assigned clinician; actions: **Open existing visit**, **Reprint slip**, **Close previous visit as abandoned** (permission-gated).
**Alt** (a) Open visit from a previous day (staff forgot to close) → offer close as abandoned with reason, then permit new check-in. (b) Legitimate same-day second episode (e.g. returned after an accident) → supervisor-approved second visit with mandatory reason; both visits linked via `related_visit_id`.
**AC** GIVEN an `OPEN` visit created today THEN 409 `VISIT_ALREADY_OPEN` with `visit_id`, `visit_state`, `current_queue`, `assigned_clinician`. GIVEN an `OPEN` visit 3 days old closed as abandoned THEN the old visit becomes `CLOSED(ABANDONED)` with `closed_reason`, its queue entry becomes terminal (`CANCELLED`), its unpaid invoice is voided, and the new visit is created. GIVEN the old visit has a `PAID` invoice THEN close proceeds, the invoice is untouched, and the visit closes `CLOSED(INCOMPLETE)`. GIVEN a supervisor-approved same-day second visit THEN both visits carry mutually-linked `related_visit_id` and `SECOND_VISIT_OVERRIDE` is audited with the reason.
**Perm** `visit.create`; abandonment close `visit.close_abandoned` (FACILITY_ADMIN, SUPERVISOR, RECEPTIONIST-with-grant); same-day duplicate `visit.override_duplicate` (SUPERVISOR, FACILITY_ADMIN).
**Data** Prior `visit.state/closed_reason/closed_by`; void the unpaid invoice (BIL-004); insert new visit.
**Audit** `VISIT_ABANDONED`, `SECOND_VISIT_OVERRIDE`, `INVOICE_VOIDED`.
**Err** Abandoning a visit with a signed encounter → 409; use the normal close path (REC-012).
**UI** The conflict panel is informative, not a dead end — every branch has a button; never a bare error toast.
**Dep** REC-001, BIL-004, QUE-007.
**OOS** Cross-facility duplicate detection (BRN-004 covers visibility only).
**Test** Matrix of prior-visit states × invoice states.

**REC-006 · Reprint the visit slip / queue token · P1 · `RECEPTIONIST`**
**Story** As a receptionist, I want to reprint a visit slip when the patient loses it, so they can be identified at triage and the pharmacy window.
**Pre** Visit exists and is not `CLOSED` older than 24 h.
**Trig** **Reprint slip** on the visit or attendance list.
**Flow** Regenerate the slip with the identical visit number and queue token, marked `REPRINT #n`, to the browser print dialog.
**AC** GIVEN a slip reprinted THEN the body is identical except a visible "REPRINT (2)" marker and `DOCUMENT_REPRINTED` is audited with the count. GIVEN a closed visit older than 24 h THEN 422 `REPRINT_WINDOW_EXPIRED`.
**Perm** `visit.print_slip`. **Data** `visit.slip_print_count`. **Audit** `DOCUMENT_REPRINTED`.
**Err** Missing facility print header → 422 pointing to TEN-003.
**UI** A5 layout working on 58 mm thermal and A4; facility name, phone, visit number, queue token, date/time, patient name and number; no diagnosis or clinical data.
**Dep** TEN-003, RCP-002, RCP-003, RCP-004. **OOS** Barcode/QR scanning (P2), SMS of the token.
**Test** Render test for both paper sizes; assert no PHI beyond name and number.

**REC-007 · View and filter today's attendance list · P0 · `RECEPTIONIST`; secondary `FACILITY_ADMIN`, `SUPERVISOR`**
**Story** As a receptionist, I want a live list of everyone checked in today with their current stage, so I can answer "where is my patient / how long more" without walking the corridor.
**Pre** Authenticated at a facility.
**Trig** **Today** from main navigation; auto-refresh every 20 s.
**Flow** List shows queue token, patient name + number, age/sex, visit type, current stage (`Waiting triage`, `In triage`, `Waiting clinician`, `With clinician`, `Awaiting lab`, `Awaiting payment`, `At pharmacy`, `Ready to leave`, `Closed`), waiting time in the current stage, assigned staff, payment status chip, and actions.
**Alt** (a) Filter by stage, visit type, payer, or overdue (>45 min in one stage). (b) Search within today's list by name or token.
**AC** GIVEN 12 patients across 5 stages THEN all appear with stage labels derived from live queue-entry and encounter states, sorted by check-in time. GIVEN a queue entry moves `WAITING → IN_SERVICE` THEN the stage label changes within one refresh cycle without a full reload. GIVEN the overdue filter THEN only entries past the configured threshold appear, each with elapsed minutes. GIVEN a receptionist token THEN the payload contains no diagnosis, complaint, vitals or medication data (contract-level verification). GIVEN facility B's session THEN zero facility A visits appear.
**Perm** `visit.read_list`; clinical columns permission-filtered server-side, not hidden in CSS.
**Data** Read-only. **Audit** No `PHI_READ` for the list itself (name + number only); opening a chart does audit.
**Err** Refresh failure → stale-data banner with last-updated time, never a blank list.
**UI** Dense table, colour-coded waiting time (green <20, amber 20–45, red >45 min — never colour alone); works on a 13" laptop without horizontal scroll; count badges per stage.
**Dep** QUE-002, ENC-002. **OOS** Historical attendance analytics (REP-002), cross-branch view (BRN-004).
**Test** Contract test asserting absence of clinical fields for a receptionist token; load test with 300 same-day visits.

**REC-008 · Record referral-in source · P2 · `RECEPTIONIST`**
**Story** As a receptionist, I want to record where a patient was referred from, so the owner can see which referral sources drive attendance.
**Pre** Visit being created. **Trig** Optional field in the check-in panel.
**Flow** Select source type (`SELF`, `REFERRED_FACILITY`, `REFERRED_PERSON`, `CAMP_OUTREACH`, `WALK_BY`) + optional free-text name.
**AC** GIVEN source `REFERRED_FACILITY` "Kisenyi HC IV" THEN `visit.referral_source_type/name` persist and appear in REP-006. GIVEN no selection THEN default `SELF`, check-in not blocked.
**Perm** `visit.create`. **Data** Two visit columns. **Audit** Included in `VISIT_OPENED` payload.
**Err** Free text >100 chars → truncation warning, not an error.
**UI** Collapsed "More details" section so it never slows the common path.
**Dep** REC-001, REP-006. **OOS** Referral letter attachment, referral-out tracking (DX-007 covers referral letters out).
**Test** Default-value test.

**REC-009 · Mark a patient as "left without being seen" · P1 · `RECEPTIONIST`; secondary `NURSE`, `SUPERVISOR`**
**Story** As a receptionist, I want to remove a patient who left before being seen, so the queue reflects reality and the clinician is not called to an empty room. **Value** LWBS rate is a real quality metric and a queue hygiene requirement.
**Pre** Queue entry `WAITING`, `CALLED` or `WAITING_PAYMENT` (unpaid abandonment); **no encounter for the visit in `OPEN`, `AWAITING_RESULTS`, `RESULTS_READY` or `SIGNED`** — a `VOIDED` encounter alone does not block. LWBS is a pre-service / pre-substantive-clinical abandonment workflow and never bypasses REC-012's clinical-integrity guards.
**Trig** **Mark as left** on the queue or attendance row.
**Flow** Confirm with reason (`LEFT_WITHOUT_BEING_SEEN`, `WENT_ELSEWHERE`, `COST`, `WAIT_TOO_LONG`, `OTHER` + text) → queue entry terminal `LWBS` (a real exit from `WAITING_PAYMENT` — never a fake pass through `WAITING`), visit `CLOSED(reason=LWBS)`, unpaid invoice voided. This confirmed LWBS workflow completes visit closure; no second manual visit-close step follows.
**Alt** (a) Already paid → invoice untouched; visit `CLOSED(LWBS_PAID)`; refund task flagged for the cashier (PAY-008). (b) Patient returns later the same day → REC-005 A2 linked new visit; the LWBS visit is not reopened. (c) Any encounter exists in `OPEN`/`AWAITING_RESULTS`/`RESULTS_READY` → 409 `ENCOUNTER_UNRESOLVED` with the encounter ID and state; the clinician resolves it through the applicable existing path (normal sign, ENC-018 sign-with-pending, or ENC-019 void where appropriate), after which closure follows the normal REC-012 workflow. (d) Encounter `SIGNED` → REC-009 is not appropriate; use normal REC-012 closure.
**AC** GIVEN a `WAITING` entry with an unpaid invoice marked LWBS `WAIT_TOO_LONG` THEN queue entry = `LWBS`, visit = `CLOSED(LWBS)`, invoice voided, three audit events written. GIVEN a `WAITING_PAYMENT` entry under `PAY_BEFORE_TRIAGE` with no encounter and an unpaid invoice WHEN the patient leaves after 30 minutes and LWBS is confirmed THEN queue entry = `LWBS` directly (no intermediate `WAITING`), visit = `CLOSED(LWBS)`, and the unpaid invoice is handled by the existing rules. GIVEN a paid invoice THEN invoice remains `PAID`, visit `CLOSED(LWBS_PAID)`, and a `RefundRequest(PENDING)` is visible to the cashier. GIVEN any encounter in `OPEN`, `AWAITING_RESULTS` or `RESULTS_READY` (e.g. a parked encounter with a downstream waiting entry) WHEN LWBS is attempted THEN 409 `ENCOUNTER_UNRESOLVED` naming the encounter ID/state, the visit remains open, and the encounter is unchanged. GIVEN a `SIGNED` encounter THEN LWBS is refused — normal REC-012 closure applies. GIVEN LWBS recorded THEN REP-002 counts it under "left without being seen", not "attended".
**Perm** `queue.remove` (RECEPTIONIST, NURSE, SUPERVISOR, FACILITY_ADMIN).
**Data** `queue_entry.state`, `visit.state/closed_reason`, invoice void, optional refund request.
**Audit** `QUEUE_ENTRY_REMOVED`, `VISIT_CLOSED_LWBS`, conditional `REFUND_REQUESTED`.
**Err** Entry already `IN_SERVICE` → 409; ask the clinician to close the encounter instead.
**UI** Reason is mandatory, selected from a list; free text only for `OTHER`.
**Dep** QUE-007, BIL-004, PAY-008, REP-002.
**Test** Both invoice branches; report attribution.

**REC-010 · Undo an erroneous check-in within a grace window · P1 · `RECEPTIONIST`**
**Story** As a receptionist, I want to cancel a check-in I created by mistake (wrong patient) within a short window, so I don't leave a phantom visit and a phantom charge.
**Pre** Visit `OPEN`, created <15 minutes ago, no vitals, no encounter, no payment.
**Trig** **Cancel check-in**, visible only inside the grace window.
**Flow** Confirm with reason → visit `CANCELLED_ERROR`, queue entry `CANCELLED`, unpaid invoice voided, visit number not reused.
**AC** GIVEN a visit created 4 minutes ago with no downstream records cancelled "wrong patient selected" THEN visit = `CANCELLED_ERROR`, queue entry = `CANCELLED`, invoice voided, the visit remains queryable in audit but excluded from attendance reports. GIVEN 20 minutes elapsed THEN 422 `GRACE_WINDOW_EXPIRED`, directed to REC-009. GIVEN a triage record exists THEN 409 `CLINICAL_DATA_EXISTS` regardless of elapsed time. GIVEN a cancelled visit THEN the next check-in uses the next number — cancelled numbers are never recycled.
**Perm** `visit.cancel_error`. **Data** State changes only; nothing hard-deleted.
**Audit** `VISIT_CANCELLED_ERROR` with reason and elapsed seconds.
**Err** Any downstream record → 409 naming the blocking record type. Visit already `IN_PROGRESS` → 409 — erroneous check-in cancellation is a pre-service correction only; use the applicable existing closure/error workflows.
**UI** Countdown chip showing remaining grace minutes.
**Dep** REC-001, TRI-002. **OOS** Hard delete, number recycling.
**Test** Boundary tests at 14:59/15:01 minutes; blocking-record matrix.

**REC-011 · Resume an in-progress visit from the desk · P1 · `RECEPTIONIST`**
**Story** As a receptionist, I want to reopen a patient's active visit to add or correct administrative details, so I don't create a duplicate to fix a typo.
**Pre** Visit `OPEN` or `IN_PROGRESS`. **Trig** Clicking the patient on the attendance list.
**Flow** Administrative visit workspace: visit header, payer, destination, invoice summary, queue history (QUE-015), edit actions for payer (REC-003), routing (REC-004), referral source (REC-008). Clinical sections appear only as locked summaries ("Triage completed 09:14 by S. Nabirye") with no values.
**AC** GIVEN a receptionist opens an in-progress visit THEN vitals values, complaint text, diagnoses and medicines are absent from the API payload; only completion timestamps and staff names return. GIVEN the same visit opened by a clinician THEN clinical values are present. GIVEN a payer edit THEN REC-003 rules apply including the payment lock.
**Perm** `visit.read`, `visit.update_admin`; clinical read requires `encounter.read`.
**Audit** `PHI_READ` only when clinical values are actually returned.
**UI** Locked clinical sections show a padlock and the reason ("Requires clinical role"), preventing staff assuming the system is broken.
**Dep** REC-001, REC-003, REC-004, REC-008, QUE-015, ENC-002. **OOS** Clinical editing by non-clinical roles (never permitted).
**Test** Two-role payload diff test.

**REC-012 · Close the visit at the exit desk · P0 · `RECEPTIONIST`; secondary `CASHIER`, `CLINICIAN`; `SYSTEM`, `FACILITY_ADMIN`**
**Story** As reception/cashier I want to close a completed visit so the patient stops appearing as present and the day's attendance can be reconciled. **Value** Defines "finished"; prevents endlessly-open visits polluting queues and reports.
**Pre** Visit `OPEN`/`IN_PROGRESS`. **Trig** Patient leaves / all steps complete, or automatic prompt when the last queue entry completes.
**Flow** Close checklist: all queue entries terminal; all encounters `SIGNED`/`VOIDED` (or explicitly abandoned); all lab order items `RELEASED`/`CANCELLED`, except that a `PENDING_RESULTS` closure permits live lab items only when their encounter is already `SIGNED` with `signed_with_pending_orders=true` through ENC-018, whose held consultation queue entry was completed at signing with reason `SIGNED_WITH_PENDING_RESULTS`; all prescriptions terminal (`DISPENSED`/`CANCELLED`/`NOT_DISPENSED`) **or** `PARTIALLY_DISPENSED` with no active pharmacy work — no pharmacy queue entry in `WAITING`/`CALLED`/`IN_SERVICE`/`ON_HOLD`/`READY_TO_RESUME` and no provisional dispense awaiting handover — in which case the checklist asks "Prescription partially dispensed — close remaining unfilled items?" and the explicit closure confirmation atomically moves `PARTIALLY_DISPENSED → PARTIALLY_DISPENSED_CLOSED` together with `Visit → CLOSED` in the **same transaction** (undispensed quantities remain historically visible; no new dispense and no stock movement are created for them; §22.6); if any pharmacy queue entry or provisional dispense is still active, closure is blocked (a `CANCELLED` provisional dispense never blocks closure — its prescription outcome is `NOT_DISPENSED` or retained `PARTIALLY_DISPENSED`, DSP-005); invoice issued and fully paid **or** explicitly waived (BIL-009) / closed with debt. LWBS closure (REC-009) obeys the same unresolved-encounter guard as this checklist — it is never a bypass around it. Blockers listed with deep links; non-blocking items are warnings requiring acknowledgment. On confirm: `Visit CLOSED` with `closed_at`, `closed_by`, `closed_reason` (closure reasons: `COMPLETED`, `PENDING_RESULTS`, `ABANDONED`, `INCOMPLETE`, `LWBS`, `LWBS_PAID`).
**Alt** (a) Unsigned `OPEN`, `AWAITING_RESULTS`, or `RESULTS_READY` encounter → hard block naming the encounter and its clinician; only the authoring clinician can sign (ENC-017/ENC-018), and no force-close bypasses this guard. (b) Outstanding lab result → only after ENC-018 has signed the encounter with pending orders may the visit close as `CLOSED(PENDING_RESULTS)`; the lab order stays live and actionable, and later release follows LAB-023. (c) Outstanding balance → blocked with amount and lines; `visit.close_with_debt` (SUPERVISOR/FACILITY_ADMIN) records the debt (BIL-014), or a waiver applies (BIL-009). (d) Other blockers → no force-close for `RECEPTIONIST`; `FACILITY_ADMIN` may force-close with mandatory reason, but may not bypass an unsigned encounter; bypassed blockers are recorded on the visit and surfaced on REP-007. (e) Nightly job flags visits open >24 h as `STALE_OPEN` for morning review (OPS-004) — see OD-22.
**AC** GIVEN a visit with an unsigned encounter in `OPEN`, `AWAITING_RESULTS`, or `RESULTS_READY` THEN closure is rejected listing the encounter and its clinician. GIVEN a signed encounter with `signed_with_pending_orders=true` and active lab items THEN `CLOSED(PENDING_RESULTS)` is allowed once its consultation queue entry is terminal (`COMPLETED` with reason `SIGNED_WITH_PENDING_RESULTS`, completed atomically at ENC-018 signing), the live items remain actionable, and later release follows LAB-023. GIVEN a `PARTIALLY_DISPENSED` prescription with no active pharmacy queue entry and no provisional dispense awaiting handover WHEN closure is confirmed with the "close remaining unfilled items" acknowledgement THEN the prescription becomes `PARTIALLY_DISPENSED_CLOSED` and the visit `CLOSED` in the same transaction. GIVEN a visit with an outstanding balance and no waiver/debt path THEN closure is rejected with the amount. GIVEN all conditions met THEN the visit disappears from "currently present" counts, remains fully readable, and no further ordinary clinical or billing records may be attached (409 `VISIT_CLOSED`); only explicitly defined post-closure workflows such as LAB-023 may append their permitted versioned/addendum records — this is not reopening. GIVEN an admin force-close THEN the reason and each permitted bypassed blocker are recorded in the audit event. GIVEN a closed visit WHEN a late lab result is released THEN the result attaches to the original encounter through LAB-023 and the visit is auto-flagged `POST_CLOSURE_ACTIVITY` for review (never silently reopened). GIVEN concurrent close attempts THEN the second gets 409 with current state.
**Perm** `visit.close`; `visit.close_with_debt`; force `visit.force_close`. A clinician may sign and hand off to closure but is not granted `visit.close`.
**Data** `Visit.status/closed_*`, audit. **Audit** `VISIT_CLOSED` with a redacted, non-PHI closure-checklist snapshot in `after_json`; closure + every force-close blocker.
**Err** Concurrent closure (409/412); closing while a cashier is mid-payment.
**UI** Checklist with green ticks and red blockers; the close button stays disabled while any blocker exists; each blocker is clickable.
**Dep** ENC-017, ENC-019, LAB-015, LAB-022, DSP-009, BIL-005, BIL-009, BIL-014, PAY-002.
**OOS** Automatic nightly auto-close of visits with clinical/financial records (OPS-004 covers only flagging; see OD-22), discharge summaries.
**Test** Full matrix of blocking conditions; `CLOSED(PENDING_RESULTS)` requires a signed-with-pending-orders encounter and keeps the lab loop alive; no closed-visit-plus-unsigned-encounter path; post-closure result handling.

**REC-013 · Record patient arrival without check-in (walk-in enquiry) · P2 · `RECEPTIONIST`**
*(Renumbered from a duplicate-numbered draft story "REC-010" in the compact generation; content unchanged.)*
**Story** As a receptionist I want to log an enquiry/turn-away so we know demand we did not serve. **Value** Explains lost revenue and capacity gaps.
**Pre** Facility open. **Trig** Person asks for a service we can't provide now.
**Flow** Log reason (`NO_CLINICIAN`, `SERVICE_UNAVAILABLE`, `PRICE`, `REFERRED_OUT`, `OTHER`) + optional name/phone → no patient record required.
**Alt** Enquiry converts to check-in → link records.
**AC** GIVEN a turn-away logged THEN it appears on REP-004 turn-away counts and creates no `Visit`, no `Patient`, no charge. GIVEN conversion to check-in THEN the enquiry is marked `CONVERTED` and linked to the visit.
**Perm** `visit.create`. **Data** `Enquiry`. **Audit** Create/convert.
**Err** Enquiry logging abused as shadow registration → no clinical fields available.
**UI** One-click reason buttons. **Dep** REP-004. **OOS** Waitlists.
**Test** No-visit invariant.

---

## 9. EPIC QUE — Queue Management

Purpose: a queue entry is the patient's position in one stage. A visit generates several sequential queue entries (triage → clinician → lab → cashier → pharmacy). Queue entries are cheap, auditable, and never deleted. **The location spine: every handoff is a queue transition, and a patient waiting for results never disappears from operational worklists (QUE-006).**

**QUE-001 · Queue entry created on check-in or stage handoff · P0 · `SYSTEM`/`RECEPTIONIST`**
**Story** As the platform I want a queue entry per service-point episode so the patient's location is always known. **Value** The location spine; every handoff is a queue transition.
**Pre** Visit `OPEN`/`IN_PROGRESS`; target department enabled.
**Trig** Check-in (REC-001), forward-routing (QUE-005), triage completion (TRI-007), clinician send-to-lab (ENC-016), send-to-pharmacy (ENC-017/RX-005), charge requiring payment (BIL-005).
**Flow** Create `QueueEntry(visit, department, queue_type, priority, queued_at=server time, state=WAITING, source_stage, token)`. Priority inherits the explicitly selected triage acuity if triage has occurred; otherwise `ROUTINE` applies as an operational queue default only for entries not requiring triage (e.g. `LAB_ONLY`, `PHARMACY_ONLY`) — consultation-path entries always receive their priority from the explicit human acuity selection (TRI-006).
**Alt** Retail pharmacy sale creates none. Disabled target queue → 422 and the calling action rolls back so a clinician never thinks a patient was sent when they were not.
**AC** GIVEN check-in to Triage THEN exactly one `WAITING` entry exists for that visit+department. GIVEN a second creation attempt for an active entry on the same queue THEN no duplicate is created (unique partial index on `visit+department+state IN (WAITING_PAYMENT,WAITING,CALLED,IN_SERVICE,ON_HOLD,READY_TO_RESUME)`); an idempotent re-request returns the existing entry. GIVEN triage completed with acuity `EMERGENCY` THEN the onward clinician entry has `priority=EMERGENCY` and sorts above all `URGENT`/`ROUTINE` regardless of arrival time. GIVEN creation THEN `queued_at` is server time, never client time.
**Perm** Internal service call; no direct public create endpoint except reception check-in (`queue.manage` or via `visit.create`).
**Data** `QueueEntry`. **Audit** `QUEUE_ENTRY_CREATED` with source stage.
**Err** Department deactivated after entry created → entry remains; admin must move it (QUE-005).
**UI** None (implicit). **Dep** REC-001, TRI-006, TEN-005. **OOS** Physical ticket dispensers; parallel non-hold membership in two department queues at once — the `ON_HOLD` upstream + active downstream pattern of QUE-006 is supported.
**Test** Duplicate-entry constraint; priority inheritance.

**QUE-002 · Department work queue view · P0 · `NURSE`,`CLINICIAN`,`LAB_TECH`,`PHARMACIST`,`CASHIER`**
**Story** As a service-point user I want a list of patients waiting for me, ordered fairly, so I know who to call next. **Value** The primary daily screen for five roles; shared role-scoped worklists replace paper cards and shouting names down a corridor.
**Pre** Entries exist; user has a role mapped to at least one queue type. **Trig** User opens their queue; refresh every 15 s.
**Flow** List filtered to the user's department(s): token, patient name, number, age/sex (age in months if <5), wait time, priority chip, source (from Triage/Reception), state, brief context (triage acuity for the clinician queue; test names for the lab queue; amount due for the cashier; item count for the pharmacy); sorted priority desc then `queued_at` asc. Row count and longest wait in the header.
**Alt** (a) Clinician-assigned entries show first on that clinician's list (QUE-004) and in the department pool marked "assigned to X". (b) Multi-role user → queue switcher tabs with unread counts. (c) Empty queue → explicit empty state with the count of patients at earlier stages.
**AC** GIVEN 3 routine and 1 emergency entry THEN the emergency sorts first regardless of arrival time. GIVEN two routine entries THEN the earlier `queued_at` sorts first. GIVEN a patient triaged 40 minutes ago THEN wait time displays "40 min" and the row is highlighted past the configured SLA (QUE-011). GIVEN a lab tech's session THEN each row shows requested test names but no diagnosis and no clinical notes (API payload verified). GIVEN a cashier's session THEN rows show amount due and invoice number but no test names, diagnosis or medicines. GIVEN a user without the department's capability THEN 403. GIVEN a new arrival THEN it appears within 15 s without manual reload. GIVEN an entry taken into service by another user THEN the row shows "In service — Dr. Okello" with the action disabled. GIVEN facility A's queue requested by a facility B user THEN 404.
**Perm** `queue.read` scoped to department type (`queue.read:<queue_type>`); field-level payload filtering is server-side.
**Data** Read; aggregate access audit (no per-row `PHI_READ`; opening a patient does audit).
**Err** Clock skew; long lists (paginate 25). Refresh failure → stale banner with timestamp; the last good list stays visible.
**UI** Dense rows, wait-time chips (colour + icon + text, never colour alone), single primary action per row ("Call"/"Start"); large touch targets for tablets.
**Dep** QUE-001, TRI-006, TRI-007. **OOS** Predicted wait times, cross-department view (QUE-014), drag-and-drop reordering.
**Test** Sort determinism; SLA highlighting; per-role payload snapshots.

**QUE-003 · Call and start serving a patient · P0 · all service-point roles**
**Story** As a nurse/clinician I want to call the next patient and mark that I've started so colleagues don't call the same person. **Value** Prevents double-calling and gives real wait/service-time data.
**Pre** Entry `WAITING`. **Trig** Staff clicks **Call next** or a specific row's **Call**; then **Start**, or clicks **Start** directly.
**Flow** `WAITING → CALLED` (`called_by`, `called_at`) with a soft lock; the patient's name and token display large for verbal call-out → on **Start** (opening the stage workspace) `CALLED → IN_SERVICE` (`served_by`, `service_started_at`); the wait clock stops and `wait_seconds` freezes on the entry; the stage's working record is created if absent — triage record (TRI-001), encounter (ENC-001), dispense session (DSP-002) — or reopened if it exists (ENC-002). **Start** directly from `WAITING` is a convenience path that atomically records `called_at=service_started_at` and `called_by=served_by`, emits the semantic call audit, and proceeds through `CALLED` for metrics before `IN_SERVICE`.
**Alt** (a) Call a specific patient out of order → `queue.call_out_of_order`; reason optional; audited with skipped count. (b) Two staff press "Call next" simultaneously → optimistic locking; each receives a different entry; the loser of a single-entry race receives the next entry, not an error; a direct concurrent call on one entry yields 409 `ENTRY_LOCKED` naming the caller (or 409 `ALREADY_CALLED`), with a takeover option (QUE-013). (c) Patient absent → QUE-009 (`NO_SHOW` path). (d) Call expiry (configurable, default 10 min) without service start → entry returns to `WAITING` with `call_attempts+1` (QUE-009). (e) Stage-record creation failure → the entry rolls back to `CALLED` so the patient is not lost between states.
**AC** GIVEN two staff calling the same entry concurrently THEN exactly one succeeds and the other receives 409 naming the caller. GIVEN 5 concurrent callers on a populated queue THEN each receives a different patient and no entry has two `called_by` values. GIVEN direct **Start** from `WAITING` THEN the entry records the starting user as `called_by` and `served_by`, sets `called_at` to `service_started_at`, and records both semantic transitions for metrics/audit. GIVEN `IN_SERVICE` THEN the entry disappears from other users' waiting lists but remains visible with the server's name. GIVEN service start on a visit whose encounter is `AWAITING_RESULTS` authored by the same clinician THEN **no new encounter is created** — the existing encounter reopens with the same ID (ENC-002; mandatory regression test). GIVEN state changes THEN each is audited with actor and timestamp.
**Perm** `queue.serve` (`queue.call`/`queue.start_service` per queue type) plus the stage's own create permission.
**Data** `QueueEntry` state/actor/times/`wait_seconds`. **Audit** Each transition (`QUEUE_CALLED`, conditional `QUEUE_CALLED_OUT_OF_ORDER`, `QUEUE_CALL_EXPIRED`, `QUEUE_SERVICE_STARTED`).
**Err** Staff forgets to mark served → `IN_SERVICE` ageing report (QUE-011). Empty queue → 200 with `null`, not an error.
**UI** Big Call button; "Being seen by X" label; immediate transition into the stage workspace, no intermediate confirmation screen.
**Dep** QUE-002, QUE-009, ENC-001, ENC-002. **OOS** Audio announcements, TTS.
**Test** Concurrency (race with 5 callers, single-entry 409); call timeout expiry; encounter-reuse regression.

**QUE-004 · Assign patient to a specific clinician · P1 · `RECEPTIONIST`,`NURSE`,`SUPERVISOR`**
**Story** As reception I want to send a patient to a named clinician (their usual doctor, or the ANC midwife) so continuity is preserved. **Value** Continuity of care and fair workload.
**Pre** Clinician active today. **Trig** Routing decision (check-in appointment link, triage completion, or manual).
**Flow** Optional `assigned_user` on the queue entry → appears at the top of that clinician's personal list ("My patients"), and in the department pool marked "assigned to X".
**Alt** Assigned clinician unavailable → any clinician with `encounter.create` may take over with a reason (audited; see ENC-022 for encounter-level takeover and QUE-013 for lock takeover).
**AC** GIVEN an entry assigned to Dr A THEN it appears at the top of Dr A's list and is visible-but-marked in the pool. GIVEN Dr B takes it over THEN a reason is required and the audit records the takeover. GIVEN no assignment THEN the entry is a pool entry.
**Perm** `queue.assign`. **Data** `QueueEntry.assigned_user_id`, audit. **Err** Assigned clinician logged out all day (see QUE-011 stale alerts).
**UI** "My patients" vs "Department" tabs. **Dep** QUE-002, QUE-013, ENC-022. **OOS** Load-balancing algorithms.
**Test** Takeover audit.

**QUE-005 · Move / forward a patient to another department (complete a stage and hand off) · P0 · all service-point roles**
**Story** As a clinician/nurse I want to send the patient onward so the next department sees them immediately. **Value** The handoff mechanic itself.
**Pre** Entry `IN_SERVICE` (or completed); the stage's own completion rules satisfied. **Trig** The stage's completion action (Complete triage, complete a patient-facing laboratory collection/receipt interaction, Sign encounter, Confirm payment, Complete dispense) or redirection. Releasing a lab result completes laboratory work, not the patient-facing laboratory QueueEntry.
**Flow** Complete current entry (`COMPLETED`, `completed_at`, `service_seconds` computed) → create the next entry at the target department (`WAITING`) in the same transaction, carrying visit, priority and a short handoff note; the visit's current stage recomputes.
**Alt** (a) Redirect without completing (wrong queue) → `TRANSFERRED` with reason. (b) Terminal stage (patient leaves) → no next entry; visit-close prompt (REC-012). (c) Multiple next stages (e.g. lab **and** pharmacy) → V1 rule: create the payment entry first if the facility gates on payment, then lab, then pharmacy — sequenced, not parallel, so the patient is never on two active queues at once. (d) Forwarding to a department with a disabled module → rejected.
**AC** GIVEN a nurse completes triage and forwards to Consultation THEN the triage entry is `COMPLETED`, a new Consultation entry is `WAITING` with the triage acuity as priority, and the patient appears in the clinician queue within 15 s. GIVEN a forward THEN the visit has at most one active queue entry **per department**, and at most one `IN_SERVICE` entry across all departments at any instant (invariant tests); a held `ON_HOLD` entry in an upstream department coexists with an active `WAITING`/`CALLED`/`IN_SERVICE` entry in a downstream department (QUE-006). GIVEN a clinician completes with two lab tests + one prescription under `PAY_BEFORE` THEN exactly one next entry is created on the CASHIER queue; the LAB entry is created only after payment confirmation (PAY-012). GIVEN a handoff note THEN it is visible to the receiving user on their queue row. GIVEN mandatory stage data missing at completion THEN 422 listing every missing field; the entry remains `IN_SERVICE`. GIVEN an injected failure on next-entry creation THEN the whole transaction rolls back — no completed stage without a next stage (OPS-003 reconciliation detects orphans).
**Perm** `queue.move` (`queue.complete` per queue type) plus the stage completion permission.
**Data** Two `QueueEntry` rows, audit. **Audit** `QUEUE_SERVICE_COMPLETED`, `QUEUE_HANDOFF` with from/to stage and reason.
**Err** Partial failure must not strand the patient (atomicity).
**UI** "Send to…" with department cards, waiting counts, and a plain-words statement of where the patient goes next ("Send to Cashier — 2 patients ahead").
**Dep** QUE-001..003. **OOS** Multi-destination parallel routing (handled by hold states, QUE-006).
**Test** Per-department active-entry invariant plus the global single-`IN_SERVICE` invariant (including the QUE-006 hold-coexistence case); atomicity under injected failure.

**QUE-006 · Hold a patient awaiting results / payment / procedure · P0 · `CLINICIAN`**
**Story** As a clinician I want to park a patient who has gone for tests so my room is free but the patient is not lost. **Value** **This story is what makes Journey B possible.** Without it, patients vanish or encounters get wrongly signed.
**Pre** Entry `IN_SERVICE`; a blocking dependency exists (open lab order, unpaid gated charge, pending procedure).
**Trig** Clinician orders investigations and releases the patient from the room.
**Flow** Entry `IN_SERVICE → ON_HOLD` with `hold_reason` (`AWAITING_RESULTS`|`AWAITING_PAYMENT`|`AWAITING_PROCEDURE`) and `hold_ref` (lab order / invoice / procedure ID) → the patient moves to the "On hold" section of the clinician's list with an elapsed timer → when the dependency resolves the entry auto-flags `READY_TO_RESUME`.
**Alt** (a) Clinician resumes manually before resolution (ENC-002). (b) Patient goes home and returns tomorrow → the entry stays on hold across the day boundary and appears on the stale-hold report (QUE-011; cross-day handling per QUE-016).
**AC** GIVEN a lab order is placed and the clinician clicks "Send to lab" THEN the consultation queue entry becomes `ON_HOLD(AWAITING_RESULTS)` referencing the order and the encounter becomes `AWAITING_RESULTS` (ENC-016). GIVEN a hold referencing three blocking tests WHEN only the first is released THEN the released result is readable and the entry remains `ON_HOLD` showing "1 of 3 results ready". GIVEN **ALL** blocking items referenced by the hold — across every referenced order — reach a terminal state (`RELEASED` or `CANCELLED`; `SAMPLE_REJECTED` is not terminal) THEN the entry becomes `READY_TO_RESUME` and is highlighted on the clinician's list within 30 s (LAB-018). GIVEN the consultation entry is `ON_HOLD` THEN a downstream LAB entry may simultaneously be `WAITING`/`CALLED`/`IN_SERVICE` and becomes `COMPLETED` after the patient-facing collection/receipt interaction; bench processing may continue after that completion. The held entry is the return point and stays on the clinician's worklist while the downstream entry is the patient's current location; only one entry is `IN_SERVICE` at any instant. GIVEN a held entry THEN it never disappears from any list and is counted in "patients in facility". GIVEN the clinician logs out and back in THEN the held patient is still listed; if the clinician is off shift the patient also appears on the department-level ready list (ENC-021). GIVEN resume THEN the entry returns to `IN_SERVICE` and the **same** encounter opens (ENC-002). GIVEN the clinician signs with pending results through ENC-018 THEN the held entry completes (`ON_HOLD → COMPLETED`, reason `SIGNED_WITH_PENDING_RESULTS`) rather than resuming — it never becomes `READY_TO_RESUME` (ENC-018). GIVEN the hold reference is cancelled THEN that cancellation is a terminal outcome for the dependency (reason `ORDER_CANCELLED`); with multiple blocking dependencies → ready only when every one is terminal.
**Perm** `queue.hold` (`CLINICIAN` for consultation workflows; `MIDWIFE` when acting on an ANC encounter/ANC queue entry — a scoped ANC grant, not unrestricted; `PHARMACIST` only for pharmacy entries with `hold_reason=AWAITING_PAYMENT` per DSP-008). **Data** `QueueEntry.state/hold_reason/hold_ref/held_at`, audit. **Audit** Hold, auto-ready, resume.
**Err** Hold with no dependency and no reason → 400 (mirrors ENC-016).
**UI** Three sections: Waiting / On hold / Ready to resume, with counts and ageing.
**Dep** LAB-004, LAB-018, ENC-016, ENC-002. **OOS** Cross-day auto-cleanup.
**Test** Full Journey-B hold/resume including a logout in between; assert the coexistence state (consultation `ON_HOLD` + lab `IN_SERVICE`, then `COMPLETED` while the item is `RESULT_ENTERED`) is valid, that auto-ready fires only when ALL blocking dependencies are terminal, and that manual resume before resolution opens the same encounter.

**QUE-007 · Remove patient from queue (left / cancelled) · P0 · `RECEPTIONIST`,`SUPERVISOR`**
**Story** As staff I want to remove a patient who left so the queue reflects reality. **Value** Queue trust; accurate waiting metrics.
**Pre** Entry active (`WAITING`, `WAITING_PAYMENT`, `CALLED`, `NO_SHOW`). **Trig** Patient left / entry created in error.
**Flow** Select entry → mandatory reason (`LEFT_WITHOUT_BEING_SEEN`, `WRONG_QUEUE`, `DUPLICATE`, `SENT_HOME`, `SENT_ELSEWHERE`, `ROUTED_IN_ERROR`, `OTHER`) → terminal state `CANCELLED` (or `LWBS` for left-without-being-seen, feeding REC-009). Entries are never deleted; the removal is always visible in the visit's queue history (QUE-015).
**Alt** Generic removal with a non-LWBS reason does not necessarily close the visit; if no other active entry exists it prompts the authorised user to close or cancel it (REC-010/REC-012). The explicit `LEFT_WITHOUT_BEING_SEEN` branch invokes REC-009.
**AC** GIVEN removal through the explicit `LEFT_WITHOUT_BEING_SEEN`/LWBS workflow THEN the entry is terminal, excluded from served counts, included in the LWBS report, and the visit is atomically closed as `CLOSED(LWBS)` or `CLOSED(LWBS_PAID)` under REC-009 with no second manual close step. GIVEN removal for `WRONG_QUEUE`, `DUPLICATE`, `SENT_HOME`, `SENT_ELSEWHERE`, `ROUTED_IN_ERROR`, or `OTHER` THEN the visit is not automatically closed by this generic removal alone. GIVEN removal without a reason THEN 400. GIVEN an `IN_SERVICE` entry THEN removal is refused (409) — complete or cancel the stage first; removing an `IN_SERVICE` entry with an open encounter requires supervisor override with a warning. GIVEN wait-time reports THEN removed entries are excluded from service-time averages but counted in a "removed" tally.
**Perm** `queue.remove`. **Data** `QueueEntry`, audit. **Audit** `QUEUE_ENTRY_REMOVED` with reason.
**UI** Reason picker. **Dep** QUE-002, QUE-015. **OOS** Auto-purge, hard delete.
**Test** Report exclusion; history retrieval.

**QUE-008 · Priority and emergency flags · P0 · `NURSE`,`RECEPTIONIST`,`CLINICIAN`; de-escalation `CLINICIAN`,`SUPERVISOR`**
**Story** As a triage nurse I want to raise a patient's priority so the sickest are seen first. **Value** Basic safety in a first-come-first-served culture.
**Pre** Entry exists (`WAITING` or `CALLED`). **Trig** Emergency arrival, triage acuity (TRI-006), or deterioration observed during the visit.
**Flow** Priority `EMERGENCY|URGENT|ROUTINE` set at check-in, inherited from triage acuity (TRI-006/QUE-001), or changed explicitly with a mandatory reason → affects sort order and colour; escalation to `EMERGENCY` raises a visible alert on the clinician queue.
**Alt** Downgrade/de-escalation requires a reason and is permitted only for `CLINICIAN`/`SUPERVISOR` — nurses may escalate but not de-escalate.
**AC** GIVEN triage acuity `EMERGENCY` THEN the onward consultation entry inherits priority `EMERGENCY` automatically. GIVEN a `ROUTINE` entry escalated to `EMERGENCY` with reason "SpO2 88% on recheck" THEN the clinician queue shows it first with a red escalation banner carrying the reason and the escalating nurse's name. GIVEN a priority change THEN the audit records old/new, reason and actor. GIVEN an `EMERGENCY` entry waiting >10 min THEN it is visually escalated on all department screens.
**Perm** `queue.priority.set` (escalate: NURSE, RECEPTIONIST, CLINICIAN, SUPERVISOR; de-escalate: CLINICIAN, SUPERVISOR).
**Data** `QueueEntry.priority`, `priority_changed_at`, `priority_reason`, audit. **Err** Everyone marked urgent → REP-004 tracks priority distribution. Change on a terminal entry → 409.
**UI** Colour + icon; never colour alone. Reason shown to the receiving clinician, not buried in audit; three quick-pick reason suggestions.
**Dep** TRI-006, QUE-002. **OOS** Formal triage scales (MTS/ESI/SATS), automated deterioration scoring (that would be clinical decision support — explicitly out of V1 scope).
**Test** Inheritance from triage; escalate/de-escalate permission asymmetry.

**QUE-009 · No-response / recall handling (no-show) · P1 · service-point roles**
**Story** As a nurse I want to record that a called patient didn't answer and re-queue them so I can move on. **Value** Keeps throughput while being fair.
**Pre** Entry `CALLED`. **Trig** No response, **No show** button, or automatic call timeout.
**Flow** "No response" → `call_attempts`/`no_show_count` +1 → back to `WAITING` retaining the original `queued_at` (fairness: the patient keeps their place, flagged with an attempt badge). After a configurable number of attempts (default 3; second no-show already flags reception follow-up) the entry may move to `NO_SHOW` (leaves the active queue, appears on reception's follow-up list) or be removed as `LWBS` (QUE-007/REC-009).
**Alt** Patient in the toilet/at the cashier — never auto-LWBS; a human must decide.
**AC** GIVEN a no-response THEN the entry returns to `WAITING` with its original queue time preserved and `call_attempts=1`, and the row carries an attempt badge. GIVEN the second no-show THEN the entry may be set `NO_SHOW`, leaves the active queue, and reception receives a follow-up item. GIVEN the configured final attempt THEN the UI offers LWBS (QUE-007) and the row is flagged. GIVEN an `EMERGENCY`-priority entry marked no-show THEN it stays `EMERGENCY` and reception receives an immediate alert row — an emergency patient who disappears is a safety event. GIVEN marking no-show on a `WAITING` entry THEN 409.
**Perm** `queue.serve`/`queue.mark_no_show`. **Data** `QueueEntry.call_attempts`/`no_show_count`, audit. **Audit** `QUEUE_NO_SHOW`, `QUEUE_CALL_EXPIRED`.
**Err** Never auto-LWBS. **UI** Attempt badge; confirm dialog only for emergency-priority entries.
**Dep** QUE-003, QUE-007, REC-009. **OOS** Paging/announcement systems, automated recall notifications (no SMS in V1).
**Test** Fairness of retained queue time; band re-sorting; emergency alert path.

**QUE-010 · Patient location strip on every screen · P1 · all roles with `queue.read`**
**Story** As any staff member I want to see where a patient currently is so I can answer questions without hunting. **Value** Cuts the commonest interruption in a clinic.
**AC** GIVEN a patient with an active queue entry THEN the patient header shows "Currently: Laboratory — waiting (12 min)". A LabOrderItem visible in a laboratory worklist, including `AWAITING_PAYMENT`, is not a patient QueueEntry and never supplies the physical location. GIVEN an upstream entry `ON_HOLD` (e.g. consultation awaiting results) and a downstream entry active (e.g. lab `IN_SERVICE`) THEN the strip derives the current location from the active downstream entry ("Currently: Laboratory — in service") and shows the held entry as the return obligation ("Consultation — awaiting results"). GIVEN a pay-before lab order before payment THEN the strip shows the cashier QueueEntry, not Laboratory; after payment creates the lab QueueEntry, it shows Laboratory. GIVEN a patient with no active entry but an open visit THEN "In facility — no active queue". GIVEN a closed visit THEN "Not present".
**Perm** `queue.read`. **Data** Read. **Dep** QUE-001, PAT-009. **OOS** Physical location tracking.
**Test** State-string mapping for all queue states.

**QUE-011 · Waiting-time SLA and stale-state alerts · P1 · `SUPERVISOR`,`FACILITY_ADMIN`**
**Story** As a supervisor I want alerts when patients wait too long or sit in a state too long so nobody is forgotten. **Value** The main safety net against dead-ends.
**Pre** SLA config per department (default: waiting 30 min, `IN_SERVICE` 60 min, `ON_HOLD` 120 min). **Trig** Periodic evaluation (client-side on refresh + Celery beat sweep every 10 min).
**Flow** Breaches surface on the supervisor dashboard and as a badge on the department queue; a daily digest lists all breaches.
**AC** GIVEN an entry waiting 35 min against a 30-min SLA THEN it is flagged on the department queue and counted on the supervisor dashboard. GIVEN an `ON_HOLD(AWAITING_RESULTS)` entry older than 120 min THEN it appears on the "stuck patients" list naming the blocking lab order and the ordering clinician. GIVEN no breaches THEN the dashboard explicitly shows zero rather than an empty panel.
**Perm** `queue.read` + `supervisor.dashboard`. **Data** Computed; `Alert` rows optional. **Audit** None (read).
**Err** Alert fatigue → per-department tuning. **UI** Counts with drill-down.
**Dep** QUE-006. **OOS** SMS/email escalation.
**Test** Clock-controlled SLA tests.

**QUE-012 · Waiting-room display board · P2 · `RECEPTIONIST` (facility)**
**Story** As a facility I want a screen showing who is being called, without exposing PHI. **Value** Reduces crowding at the desk.
**AC** GIVEN the board is displayed THEN it shows patient number or first name + initial only (facility-configurable), never full name, diagnosis, age or phone. GIVEN the board URL THEN it requires a device token and shows only currently-called entries.
**Perm** Device token, read-only. **Dep** QUE-003, AUTH-013. **OOS** TTS announcements.
**Test** PHI-exposure review of the rendered board.

**QUE-013 · Take over an entry locked by another user · P1 · `SUPERVISOR`,`FACILITY_ADMIN`; secondary `CLINICIAN`**
*(Absorbed from the alternate-generation queue set; preserves its full behaviour.)*
**Story** As a supervisor, I want to release a queue entry that a colleague locked and then went off shift, so the patient is not stuck.
**Pre** Entry `CALLED` or `IN_SERVICE`, inactive longer than the configured threshold (default 30 min).
**Trig** **Release / take over** on the entry.
**Flow** Confirm with reason → lock released; if `IN_SERVICE` with an open stage record, the record is left intact; the new user becomes co-author or the record is reassigned per stage rules (an encounter is never silently reassigned — see ENC-022).
**AC** GIVEN an entry `IN_SERVICE` idle for 45 min taken over with reason THEN the entry's `assigned_user` changes, `QUEUE_TAKEOVER` is audited with both user IDs and the reason, and the original open encounter remains authored by the original clinician. GIVEN takeover attempted after 5 min idle THEN 422 `TAKEOVER_TOO_EARLY` with remaining minutes. GIVEN a takeover of an entry with an open encounter WHEN the new clinician writes notes THEN the encounter records both a primary author and a co-author, each note line carrying its own author ID.
**Perm** `queue.takeover` (SUPERVISOR, FACILITY_ADMIN). **Audit** `QUEUE_TAKEOVER`.
**Err** Original user active in the last 5 min → blocked.
**UI** Clear warning naming the current holder and their last activity time.
**Dep** QUE-003, ENC-022. **OOS** Automatic takeover without human decision.
**Test** Idle-threshold boundary; authorship preservation.

**QUE-014 · Supervisor view of all queues · P1 · `SUPERVISOR`,`FACILITY_ADMIN`,`ORG_OWNER`**
**Story** As a supervisor, I want a single board showing every queue's depth and longest wait, so I can move staff to the bottleneck.
**Pre** Supervisory role at the facility. **Trig** **Flow board**; refresh 30 s.
**Flow** Card per stage: waiting count, in-service count, longest wait, median wait today, staff currently serving. Clicking a card opens that queue read-only.
**AC** GIVEN 4 waiting at triage (longest 38 min) and 9 waiting for clinicians (longest 71 min) THEN both cards show correct counts/waits and the clinician card is flagged red per the configured threshold. GIVEN a supervisor without clinical permissions opening a queue THEN the payload contains no clinical values — only counts, names and timings. GIVEN an organisation owner with two facilities THEN only the currently selected facility's data shows (cross-branch roll-up is BRN-004).
**Perm** `queue.read_board`. **Audit** None (aggregate, no PHI).
**UI** Deliberately simple: 5–7 cards, no charts, readable from 2 m on a wall-mounted screen.
**Dep** QUE-002. **OOS** Predicted wait times, staffing recommendations.
**Test** Aggregate correctness against seeded data; payload PHI absence.

**QUE-015 · Queue history on the visit record · P1 · all roles with `visit.read`**
**Story** As any staff member, I want the full stage timeline of a visit, so I can explain exactly where time was spent.
**Pre** Visit exists. **Trig** Opening the visit workspace timeline.
**Flow** Chronological list of every queue entry with stage, queued/called/started/completed timestamps, actor names, waits, and any removal or escalation reason.
**AC** GIVEN a visit that passed triage → clinician → cashier → lab → clinician (resumed) → pharmacy THEN six entries appear chronologically with the second clinician entry labelled "Resumed — results review" and linked to the same encounter ID as the first. GIVEN a removed entry THEN it appears greyed with its removal reason and actor. GIVEN total visit duration THEN it equals `last_completed_at − visit.opened_at` and waits + services + untracked gaps reconcile.
**Perm** `visit.read`. **Audit** None beyond standard. **UI** Vertical timeline, collapsible nodes, waits in minutes.
**Dep** QUE-001..009. **OOS** Export of the timeline (REP-008 covers exports).
**Test** Reconciliation arithmetic test.

**QUE-016 · Daily queue reset and stale-entry sweep · P1 · `SYSTEM`; secondary `FACILITY_ADMIN`**
**Story** As a facility admin, I want yesterday's abandoned queue entries cleared automatically, so today's board is not polluted by stale rows.
**Pre** Scheduled job enabled; facility timezone Africa/Kampala. **Trig** Nightly at the facility's configured cut-off (default 23:59) plus on-demand admin action.
**Flow** Entries still `WAITING`/`WAITING_PAYMENT`/`CALLED`/`NO_SHOW` from previous days → `EXPIRED` with reason `DAY_ROLLOVER` (`WAITING_PAYMENT` expiry is a real exit — the unpaid patient is never left permanently active, and unpaid abandonment never converts to payment success). Visit handling: visits with **no clinical or financial records** may auto-close `CLOSED(ABANDONED)`; visits with a signed encounter close `CLOSED(INCOMPLETE)` only after morning review; visits with a paid invoice are flagged `REVIEW_REQUIRED` with the paid amount so money is never silently written off; all other stale visits are flagged `STALE_OPEN` for morning review and are **never auto-closed** (REC-012, OD-22). `IN_SERVICE` entries are never auto-expired; they are listed on an exceptions report.
**AC** GIVEN an entry `WAITING` since yesterday THEN it becomes `EXPIRED`, audited with actor `SYSTEM`; a zero-record visit may close `CLOSED(ABANDONED)`, also audited. GIVEN an `IN_SERVICE` entry from yesterday THEN it is untouched and appears on the exceptions list shown to the facility admin at next login. GIVEN a visit with a paid invoice and a waiting entry THEN the visit is flagged `REVIEW_REQUIRED` with the paid amount. GIVEN the sweep runs twice THEN no additional state changes occur (idempotent).
**Perm** System job; manual trigger `ops.run_sweep` (FACILITY_ADMIN).
**Audit** `QUEUE_SWEEP_RUN` summary plus per-entity events.
**Err** Job failure retried with backoff; ops alert after 3 failures; never partially applied without an audit record.
**UI** Exceptions list on the admin dashboard with a count badge.
**Dep** REC-012, QUE-011, OPS-004. **OOS** Configurable per-department cut-offs.
**Test** Idempotency; timezone correctness across 00:00; paid-invoice guard.

---
## 10. EPIC TRI — Triage

Purpose: capture the structured observation set that gives the clinician a head start, and record the **human-assigned** acuity. Triage is a nursing record, editable by nurses, readable by clinicians, and never overwritten silently. **KlinKlik displays neutral out-of-range markers; it never computes or suggests an acuity (OD-18).**

**TRI-001 · Open triage for a queued patient (triage worklist and start) · P0 · `NURSE`; secondary `MIDWIFE`**
**Story** As a triage nurse I want to open the triage form for the next patient so I can record their baseline. **Value** Objective data before the clinician; the clinician's first context.
**Pre** Entry `WAITING` at a `TRIAGE` department; `triage.create`. **Trig** Nurse calls the patient (QUE-003) from the triage worklist.
**Flow** The triage home is the role queue (QUE-002) filtered to `queue_type=TRIAGE` with extra columns: age (in months if <5 years), sex, visit type, wait time, and chips for under-5 or pregnant (from the patient record / prior ANC). Call → triage form opens with patient header, visit type, last visit's key vitals for comparison; `TriageRecord(visit, patient, recorded_by, started_at, state=DRAFT)` created; queue entry `IN_SERVICE`.
**Alt** (a) Patient already triaged this visit → open the existing record in amend mode (TRI-008); never create a second, unless a re-triage is explicitly requested (TRI-010). (b) Active ANC episode → the row carries an "ANC" chip and the action routes to the ANC vitals form (ANC-004). (c) Nurse session expires mid-form → the `DRAFT` record is recoverable with autosaved values (server-side autosave every 20 s, never browser storage).
**AC** GIVEN a patient aged 11 months THEN age displays "11 mo" with an "Under 5" chip. GIVEN an existing triage record for this visit WHEN triage is opened THEN the existing record loads for editing, not a new one. GIVEN opening triage THEN the queue entry becomes `IN_SERVICE`. GIVEN the previous visit had vitals THEN the last recorded weight and BP show as reference with their dates; height recorded within 12 months pre-fills marked "from [date] — confirm or change", persisted only on confirmation. GIVEN a nurse's worklist payload THEN no prior diagnoses or notes are included.
**Perm** `queue.read:TRIAGE` + `triage.create`. **Data** `TriageRecord`. **Audit** `TRIAGE_STARTED` + save.
**Err** Two nurses opening simultaneously → 409/412. Visit closed → 409.
**UI** Single screen, numeric keypads on mobile, tab order following the physical measurement sequence; persistent red allergy banner above the form.
**Dep** QUE-003, PAT-001, PAT-007, ANC-004. **OOS** Device integration (BP machine feeds), prior-visit clinical summary on the worklist.
**Test** No-duplicate-record test; draft recovery; age-formatting boundaries (0–23 mo, 2–4 y, ≥5 y).

**TRI-002 · Record vital signs · P0 · `NURSE`,`MIDWIFE`,`CLINICIAN`**
**Story** As a nurse I want to record vitals with sane limits so errors are caught at entry. **Value** Wrong vitals cause wrong clinical decisions; typos are frequent. Vitals are the most reused clinical data in the system (follow-up comparison, ANC, repeat observations).
**Pre** Triage record `DRAFT`. **Trig** Measurement taken.
**Flow** Capture temperature (°C), pulse (bpm), respiratory rate, BP systolic/diastolic (mmHg), SpO₂ (%), weight (kg), height (cm), and MUAC (cm) for children 6–59 months. Each field individually optional (or explicitly **Not done** with a reason — equipment unavailable, patient declined — which is a first-class value); at least one observation required to save; blanks are never recorded as zeros. BMI computed server-side (one decimal) whenever weight + height exist, stored as derived, **no interpretation text shown**. Values outside the configured reference band are flagged in the payload (`abnormal_high`/`abnormal_low`/`critical_low`) and displayed with a neutral "outside reference range" marker and no advice; queue rows may show a neutral fever chip from these flags.
**Alt** Equipment unavailable → "Not done — equipment unavailable" does not block completion and displays as such everywhere (never a blank or a zero).
**AC** GIVEN temperature 39.8 THEN it saves and is flagged `abnormal_high` (fever chip permitted downstream). GIVEN temperature 3.98 or 65 THEN rejected with a range error (accepted band 30.0–45.0 °C). GIVEN systolic 120 and diastolic 130 THEN rejected (`DIASTOLIC_EXCEEDS_SYSTOLIC`). GIVEN pulse 0 THEN rejected (use blank/not-done for not measured). GIVEN weight and height THEN BMI computed server-side to 1 decimal and displayed without interpretation. GIVEN a saved vital outside a configured reference band THEN a neutral marker, no advice. GIVEN MUAC for a 14-month-old THEN the field is present (cm); BMI is not displayed for under-2s without a valid height context. GIVEN a "Not done" field THEN completion is allowed and the clinician view shows "Not done (equipment unavailable)". GIVEN save THEN values, units, recorder and timestamp are stored in the versioned `TriageRecord`/`VitalsObservation` domain records, and `TRIAGE_VITALS_RECORDED` references that record version with actor, timestamp, changed field names and content hash; the generic audit payload contains no clinical values.
**Perm** `triage.create` (record vitals). **Data** `TriageRecord` vitals + flags, derived BMI, `VitalsObservation`. **Audit** Non-PHI metadata, changed field names, version reference and hash.
**Err** Unit confusion (°F entry) → unit label adjacent to every field, no unit switching in V1 (a wrong unit selection is a real safety risk); extremely low SpO₂ typo caught by hard bounds.
**UI** Wide numeric inputs, units always visible, normal range for the patient's age band in small grey text, out-of-range shown after blur not per keystroke; abnormal amber, critical red with icon.
**Dep** TRI-001, PAT-001. **OOS** Growth charts, paediatric early-warning scores, weight-for-age percentile bands (OD-20), device integration, trend graphs.
**Test** Boundary tests per field across age bands (neonate → elderly); BMI arithmetic; implausible-value rejection for every field.

**TRI-003 · Record presenting complaint at triage · P0 · `NURSE`**
**Story** As a nurse I want to capture why the patient came, in their words, so the clinician starts informed. **Value** Speeds clerking; supports routing.
**Pre** Triage record `DRAFT`. **Trig** Complaint section.
**Flow** Select one or more complaints from a facility-configurable short list (fever, cough, diarrhoea, vomiting, abdominal pain, headache, injury, rash, difficulty breathing, dizziness, pregnancy-related, review of results, other) each with a duration value + unit (hours/days/weeks), plus optional free text ≤500 chars — a **nursing observation**, explicitly not a diagnosis. Alternatively record a single verbatim free-text complaint (≤500 chars) where no list is configured.
**Alt** Blank complaint on an OPD visit → saving blocked with `COMPLAINT_REQUIRED`; "other" without free text → 422 `OTHER_REQUIRES_TEXT`.
**AC** GIVEN complaints "fever" (3 days) and "cough" (5 days) THEN both persist as structured rows with durations and appear on the clinician's encounter screen read-only. GIVEN a complaint of up to 500 characters THEN it saves verbatim and appears in the clinician's triage panel (ENC-004). GIVEN common complaints THEN a quick-pick list (facility-configurable) inserts text that remains editable. GIVEN more than 5 complaints THEN 422 (triage is not a full history). GIVEN the clinician later records a diagnosis THEN the triage complaint remains visible and unmodified — the clinician cannot edit the nurse's entry, only add their own history.
**Perm** `triage.create`. **Data** `TriageComplaint` rows / `TriageRecord.presenting_complaint`. **Audit** `TRIAGE_COMPLAINT_RECORDED`.
**Err** Nurse writing a diagnosis here → helper text "record the patient's words, not a diagnosis".
**UI** Chip-style multi-select with duration steppers; the free-text box is deliberately small.
**Dep** TRI-001, CAT-006. **OOS** Structured symptom coding, ICD coding at triage, symptom-to-diagnosis suggestion (that is CDS — out of scope).
**Test** Verbatim round-trip incl. non-ASCII; complaint-limit rule; clinician-side immutability.

**TRI-004 · Record allergies at triage · P0 · `NURSE`; secondary `CLINICIAN`,`PHARMACIST`,`MIDWIFE`**
**Story** As a nurse I want to record known allergies so they follow the patient permanently. **Value** The single highest-value safety datum V1 carries; the only medication-safety data V1 collects, and triage is the reliable capture point.
**Pre** Patient exists; triage record `DRAFT`. **Trig** Triage question — mandatory to either enter allergies or explicitly confirm none.
**Flow** Choose `NO_KNOWN_ALLERGIES` | `UNKNOWN` | list of allergies (substance free text or facility short-list quick-pick — penicillin, sulfa, aspirin/NSAIDs, other; reaction free text; severity `MILD|MODERATE|SEVERE`) → stored **at patient level**, not visit level, with the recording visit referenced. An existing allergy from a previous visit displays with a **Confirm still accurate** action rather than requiring re-entry.
**Alt** (a) Patient reports a new allergy later → added by clinician/pharmacist; existing entries are never silently deleted — mark `ENTERED_IN_ERROR` with a reason (clinician refuting an allergy uses the same path); the entry is struck-through in history and removed from the active banner. (b) See OD-19: an exact-string-match prescription warning exists in a draft generation; V1 performs **no automatic matching** (banner display only).
**AC** GIVEN an allergy recorded THEN a `patient_allergy` row exists with `recorded_by`/`recorded_at` and the red banner appears on every screen showing this patient thereafter — triage, encounter, prescription, dispense — the same component everywhere, never dismissible. GIVEN `NO_KNOWN_ALLERGIES` THEN `patient.allergy_status=NKA` with timestamp and the banner shows "No known allergies (confirmed [date])", distinguishable from "not asked". GIVEN neither allergies nor NKA set WHEN triage completion is attempted THEN 422 `ALLERGY_STATUS_REQUIRED`. GIVEN allergy status never captured THEN the header shows "Allergies: not recorded" in a warning style. GIVEN an allergy marked entered-in-error THEN it is hidden from the banner, retained in history with the reason, and the change is audited. GIVEN the platform THEN **no automatic interaction checking is performed and the UI must not imply any** (AS-11).
**Perm** `allergy.manage` (NURSE, CLINICIAN, MIDWIFE, PHARMACIST); entered-in-error requires CLINICIAN or above.
**Data** `PatientAllergy` (patient-scoped, versioned), `patient.allergy_status`. **Audit** `ALLERGY_RECORDED`, `ALLERGY_CONFIRMED`, `ALLERGY_ENTERED_IN_ERROR`.
**Err** "Allergy" to a food vs drug — free text accepted. Free-text allergen >100 chars → 422.
**UI** Red header chip; add dialog with three fields.
**Dep** PAT-007, PAT-009, RX-003, DSP-002. **OOS** Automated allergy–drug alerts (OD-19), coded allergen terminology, cross-reactivity logic.
**Test** Banner presence on all clinical routes; not-recorded vs NKA distinction; entered-in-error path.

**TRI-005 · Record current medications and brief history at triage · P1 · `NURSE`**
**Story** As a nurse I want to note what the patient is already taking so the clinician doesn't duplicate therapy.
**AC** GIVEN up to 10 current medications entered as free text (name, dose/frequency if known) THEN they display in the clinician's triage panel and prefill the clerking "current medications" field as editable text (ENC-010), clearly labelled "from triage". GIVEN chronic conditions ticked from a short configurable list (e.g. hypertension, diabetes, HIV, asthma, epilepsy, sickle cell) THEN they appear in the clinician's context panel and prefill ENC-008.
**Perm** `triage.create`. **Data** `TriageRecord.current_meds_text`, `chronic_flags`. **Err** Duplication with ENC-010 → clerking clearly labels the source.
**Dep** ENC-008, ENC-010. **OOS** Medication reconciliation workflow.
**Test** Prefill and editability.

**TRI-006 · Set triage acuity · P0 · `NURSE`**
**Story** As a nurse I want to assign an acuity so the queue orders by clinical need. **Value** Simple prioritisation without pretending to run a validated triage scale; the single most important safety feature of the attendance loop.
**Pre** Vitals recorded or explicitly marked not done; complaint recorded. **Trig** Acuity section of the triage form, or emergency arrival (QUE-008).
**Flow** The **nurse selects** `EMERGENCY` (see immediately) | `URGENT` (see before routine) | `ROUTINE` (routine) with an optional reason. **V1 provides no automatic acuity computation, suggestion or pre-selection from vitals or danger signs** (AS-11; the draft-generation suggestion mechanism is recorded as OD-18 and is not V1 behaviour). Acuity propagates to the clinician queue entry priority on triage completion (TRI-007/QUE-001).
**Alt** Acuity changed → queue priority updates and the change is audited with actor and reason. Selecting a level **lower** than a previously assigned `EMERGENCY` → reason mandatory (downgrade discipline).
**AC** GIVEN acuity `EMERGENCY` THEN the onward consultation queue entry has priority `EMERGENCY`, sorts first with a distinct marker, the clinician queue header shows "1 emergency waiting", and the nurse is prompted to notify a clinician directly (prompt display and the nurse's confirmation/dismissal are recorded). GIVEN acuity changed THEN the queue priority updates and the audit records old/new, actor and reason. GIVEN no acuity selected WHEN triage completion is attempted THEN 422 `ACUITY_REQUIRED` — acuity has **no automatic default and no preselection**; `ROUTINE` is stored only when an authorised human explicitly selects it. GIVEN acuity assigned THEN the acuity and its reason display in the clinician's encounter header.
**Perm** `triage.create` (NURSE, CLINICIAN, MIDWIFE). **Data** `TriageRecord.acuity`, `acuity_reason`, `QueueEntry.priority`. **Audit** `TRIAGE_ACUITY_ASSIGNED`, conditional `TRIAGE_ACUITY_DOWNGRADED`.
**Err** Over-use of `EMERGENCY` → distribution reported (REP-004).
**UI** Three large buttons with colour + icon + text; the nurse is accountable for the decision.
**Dep** QUE-001, QUE-008, TRI-002, TRI-003. **OOS** MTS/ESI/CTAS/SATS scoring, automated acuity suggestion (OD-18), deterioration prediction.
**Test** Priority propagation; downgrade-reason enforcement.

**TRI-007 · Save triage and forward to the clinician · P0 · `NURSE`**
**Story** As a nurse I want to finish triage and send the patient onward so the handoff is explicit. **Value** The Reception→Nurse→Doctor baton.
**Pre** Triage has at least one vital (or not-done reasons) + complaint + acuity. **Trig** Nurse clicks **Complete triage / Save & send**.
**Flow** Completeness check (missing mandatory items listed) → persist triage; `TriageRecord → COMPLETED` (`completed_at`, `completed_by`), read-only thereafter except via amendment (TRI-008) → triage queue entry `COMPLETED` → create consultation (or ANC) queue entry `WAITING` with inherited priority and optional assigned clinician (destination selectable: general clinician queue, named clinician, or department) → confirmation showing destination and position.
**Alt** (a) Patient sent to Laboratory or Cashier first (facility flow) → destination selectable; routing to LAB is limited to tests already ordered by an authorised orderer — nurse-initiated test ordering is not V1 behaviour (OD-21). (b) Patient sent home from triage (wrong facility) → QUE-007 + REC-012. (c) Named clinician not on duty today → warning with the option to use the general queue; proceeding is audited. (d) Validation failure → nothing is forwarded; the nurse stays on the form with errors.
**AC** GIVEN a completed triage saved and forwarded THEN the clinician's queue shows the patient with a triage summary (time, temp, BP, pulse, acuity, complaint) visible on the row or one click away; vitals, complaints, acuity, allergy banner and the nurse's name and time are all visible to the clinician without further navigation. GIVEN validation failure THEN nothing is forwarded. GIVEN forwarding THEN the audit records the triage save and the queue transition as separate correlated events (`TRIAGE_COMPLETED`, `QUEUE_HANDOFF`). GIVEN acuity `EMERGENCY` THEN the notification prompt is displayed and the clinician queue shows a red banner.
**Perm** `triage.create` + `queue.move`. **Data** `TriageRecord`, two `QueueEntry` rows.
**Err** Network failure after save before forward → idempotent retry; the triage record must not be duplicated. Concurrent completion → 409 with current state.
**UI** Single "Save & send to…" with destination preselected; the completion screen summarises what the clinician will see.
**Dep** QUE-005, TRI-006, ENC-004, CAT-007 (OD-21). **OOS** Nurse-initiated protocol treatment, nurse prescribing, nurse diagnosis, standing orders.
**Test** Partial-failure retry; mandatory-field matrix; emergency prompt recording.

**TRI-008 · Amend a triage record · P1 · `NURSE` (author); secondary `SUPERVISOR`**
**Story** As a nurse I want to correct a mistyped vital so the clinician isn't misled, while the original remains visible for audit.
**Pre** Triage record `COMPLETED`; amendment within the facility window (default 24 h) or supervisor permission.
**Trig** **Amend** on the triage record.
**Flow** Edit values with a mandatory reason → an amendment row stores before/after values, author and reason; the current record shows the corrected value with an "Amended" badge (hover shows "was X, corrected by Y, reason"); the original remains retrievable. Before the clinician signs the encounter, the corrected value is what the clinician sees; after signing, the amendment also notifies the signing clinician (AUD-008) and appears as an addendum-style entry in the visit timeline; the signed note content itself is unchanged.
**Alt** Non-author nurse → 403 unless `triage.amend_any` (SUPERVISOR, FACILITY_ADMIN). Window expired → 422 `AMENDMENT_WINDOW_EXPIRED` with instruction to request supervisor amendment. After visit closure → allowed with supervisor + reason; flags the visit `POST_CLOSURE_ACTIVITY`.
**AC** GIVEN temperature recorded 3.74 amended to 37.4 with reason "transcription error" THEN the displayed value is 37.4, the badge and hover history are present, and the versioned amendment record retains both values while `TRIAGE_AMENDED` records its version references/hashes, changed field names, actor and reason without raw clinical values. GIVEN an amendment changes acuity after the clinician has already seen the patient THEN the queue priority is **not** retroactively changed and a notice explains why. GIVEN any amendment THEN the printed record shows the current value with an amendment footnote; amended fields carry the badge everywhere, including the clinician's triage panel.
**Perm** `triage.update` (own record within window) / `triage.amend_any` otherwise. **Data** `TriageRecord` version/amendment rows. **Audit** Changed field names, version references/hashes and reason; no clinical before/after JSON.
**Err** Empty reason → 422. Amendment on a closed and reported visit → flagged in REP-009 data-quality report.
**Dep** AUD-008, AUD-003. **OOS** Deleting triage (never permitted).
**Test** Version-history rendering; author vs non-author permission; window boundary.

**TRI-009 · Clinician view of triage data · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want the triage data visible while I clerk so I don't re-ask or re-measure. **Value** The main reason clinicians trust or ignore a triage module.
**Pre** Visit has a `COMPLETED` triage record; clinician has started service. **Trig** Opening the encounter workspace.
**Flow** A fixed triage panel (sticky/collapsible, default expanded, state stored server-side in user preferences) shows: acuity chip + reason; all vitals with units in a single row, abnormal values highlighted, normal ranges on hover; BMI; complaints with durations; current meds and chronic flags; allergy banner; recorder name and time; "recorded X min ago" freshness indicator (past the configured age it states neutrally, e.g. "Vitals recorded 3 h ago"); link to previous visits' vitals (TRI-012).
**AC** GIVEN an encounter opened for a triaged visit THEN the panel shows everything above and remains visible throughout clerking; at 1366×768 all seven core vitals are visible above the fold. GIVEN a vital marked "Not done — equipment unavailable" THEN it renders as such, never a blank or zero. GIVEN vitals amended after the clinician opened the encounter THEN a "triage updated" indicator appears with the new values on refresh. GIVEN no triage exists THEN the panel states "No triage recorded for this visit" with a **Record vitals now** action if the clinician holds `triage.create`; clerking proceeds. GIVEN the clinician amends nothing THEN the triage record is byte-identical to what the nurse saved (read-only to clinicians, enforced at the API). GIVEN the panel is opened THEN the encounter-open `PHI_READ` covers it; a comparison read (TRI-012) audits separately.
**Perm** `triage.read` (CLINICIAN, MIDWIFE, NURSE, SUPERVISOR — not cashier/receptionist/pharmacist). **Data** Read-only.
**Dep** TRI-007, ENC-004, TRI-012. **OOS** Graphical trends, automatic interpretation of vitals.
**Test** Amendment-visibility test; above-the-fold rendering; read-only enforcement.

**TRI-010 · Re-triage / repeat vitals in the same visit · P1 · `NURSE`,`CLINICIAN`**
**Story** As a nurse/clinician I want to record a second set of vitals (e.g. after antipyretics, on deterioration, or before discharge) without overwriting the first.
**AC** GIVEN a visit with an existing triage record WHEN a repeat set is recorded THEN a new `VitalsObservation(context=REPEAT, sequence=n)` is created linked to the same visit (and open encounter if any); both sets are visible in time order; the clinician panel shows the latest with access to earlier sets; the triage record's own values are unchanged. GIVEN a repeat set THEN the queue is not re-routed automatically. GIVEN a repeat vital falls outside its configured reference range (e.g. SpO₂ 89%) WHEN the observation is saved THEN the value is stored and displayed with a neutral out-of-range marker, its unit, timestamp and recorder — no acuity or priority recommendation is generated, no escalation action is offered, suggested or preselected because of the value, and the patient's current queue priority remains unchanged unless an authorised user explicitly changes it through the standard priority control (QUE-008; AS-11, OD-18). GIVEN a nurse records the repeat while the clinician's encounter is open THEN the new set appears on refresh without losing the clinician's unsaved note text.
**Perm** `triage.create`. **Data** `VitalsObservation` (1..n per visit; the triage record references the first). **Audit** `VITALS_RECORDED` (context REPEAT).
**Err** Same validation as TRI-002. **UI** Compact inline form; only the repeated fields need values.
**Dep** TRI-002, ENC-002. **OOS** Observation charts/graphs (P2), continuous monitoring.
**Test** Ordering and latest-selection; concurrent-edit test proving unsaved clinician text survives.

**TRI-011 · Mandatory paediatric weight · P0 · `NURSE`**
**Story** As a facility I want weight to be compulsory for under-5s because dosing depends on it.
**AC** GIVEN a patient aged under 5 years WHEN triage is saved without weight (or an explicit not-done reason) THEN the save is rejected with `WEIGHT_REQUIRED_UNDER_5`. GIVEN a patient aged under 5 THEN weight is displayed prominently in the clinician header and printed on the prescription (RX-007). GIVEN an age-estimated infant THEN the same rule applies.
**Perm** `triage.create`. **Dep** PAT-010, RX-007. **OOS** Weight-based dose calculation (explicitly excluded — AS-11).
**Test** Boundary at the 5th birthday.

**TRI-012 · View the patient's vitals history · P1 · `CLINICIAN`,`NURSE`,`MIDWIFE`**
**Story** As a clinician, I want to see this patient's previous vitals in a table, so I can judge whether today's values represent a change.
**Pre** ≥1 prior recorded vital set at this facility. **Trig** **Compare / history** in the triage panel.
**Flow** Table: date, context (triage/repeat/ANC), each vital, recorded by. Default last 5 sets, expandable to 12 months.
**AC** GIVEN 8 prior sets THEN the 5 most recent show newest first with a "show more" control. GIVEN sets recorded at another facility in the same organisation THEN they are included only if the explicitly authorised external BRN-003 sharing policy grants the dedicated cross-facility capability; each row is labelled with its facility, the read is audited, and when disabled no count of hidden records is leaked. Cross-tenant access remains denied. GIVEN history opened THEN one `PHI_READ` event records the patient ID and result count.
**Perm** `triage.read` + `patient.read_cross_facility` for the shared case.
**UI** Plain table, abnormal values highlighted per TRI-002 rules; deliberately no charts in V1.
**Dep** TRI-002, BRN-003. **OOS** Trend graphs, growth charts, export.
**Test** Cross-branch visibility both ways; audit event correctness.

**TRI-013 · Triage a patient without a prior check-in (walk-in emergency) · P1 · `NURSE`; secondary `CLINICIAN`,`MIDWIFE`**
**Story** As a triage nurse, I want to start triage immediately for a collapsing patient and let reception complete registration afterwards, so care is never delayed by paperwork. **Value** A system that forces registration before emergency assessment will be bypassed on paper, and the record will be lost.
**Pre** Nurse holds `triage.create_emergency`. **Trig** **Emergency triage** button on the triage home screen.
**Flow** (1) Minimum identity set: any known name (or "Unknown male, approx 30"), approximate age, sex. (2) System creates a provisional `Patient(is_provisional=true)` with a temporary identifier, plus a `Visit` and `TriageRecord`, and places the patient at the top of the clinician queue with `EMERGENCY` priority. (3) A task appears on reception's list: "Complete registration — provisional patient". (4) Reception later merges/completes the record (PAT-002 merge path) without breaking the encounter link.
**AC** GIVEN "Unknown male, approx 30" entered THEN a provisional patient, open visit and triage record exist; the clinician queue shows the entry first with `EMERGENCY` and "Provisional record" chips; reception's follow-up list has one item. GIVEN reception later matches and merges THEN the visit, triage record and any encounter re-point to the surviving patient ID, the provisional record is retired (not deleted), and `PATIENT_MERGED` is audited with both IDs and all moved record counts; merge conflicts (both records have allergies) require explicit per-field resolution — no silent overwrite. GIVEN an invoice created for a provisional patient THEN it is permitted and after the merge belongs to the surviving patient. GIVEN a provisional record older than 24 h incomplete THEN it appears on the data-quality exceptions report (REP-009) and is not auto-deleted. GIVEN a user without `triage.create_emergency` THEN 403.
**Perm** `triage.create_emergency` (NURSE, CLINICIAN, MIDWIFE).
**Data** Insert provisional `patient`, `visit`, `triage_record`, `queue_entry`. **Audit** `PROVISIONAL_PATIENT_CREATED`, `TRIAGE_STARTED`, later `PATIENT_MERGED`.
**UI** Visually distinct button, single confirmation tap, four fields maximum.
**Dep** PAT-002, REC-001, QUE-001, REP-009. **OOS** Mass-casualty batch registration, unidentified-patient photography.
**Test** Full merge test verifying referential integrity across visit, triage, encounter, invoice and payment.

---

## 11. EPIC ENC — Clinical Encounter / Doctor Clerking

> This epic is deliberately granular. The encounter is a **long-lived, resumable, versioned clinical record**, not a form submission. A patient returning from the laboratory, cashier or another room resumes the **same** encounter; a second encounter is never created for the same visit while one is open.

**ENC-001 · Start an encounter from the clinician queue · P0 · `CLINICIAN`; secondary `MIDWIFE`**
**Story** As a clinician I want to start seeing the next patient so an encounter record exists and my colleagues know the patient is with me. **Value** Creates the clinical container and claims the patient.
**Pre** Queue entry `WAITING`/`CALLED` at a `CONSULTATION` department; `encounter.create`; visit `OPEN`.
**Trig** Clinician clicks "Start consultation".
**Flow** Call → queue entry `IN_SERVICE` → **check for an existing non-terminal encounter for this visit**: if one exists, open it (ENC-002); otherwise create `Encounter(visit, patient, provider, type=OPD, state=OPEN, started_at)` → clerking workspace opens.
**Alt** (a) Patient has an open encounter from _another_ clinician → do not create a second; show "Open encounter held by Dr X" with a takeover path (ENC-022). (b) Consultation not paid under `PAY_BEFORE` → warn with the outstanding amount; clinician may proceed with `billing.gate.override` (audited) or send the patient to the cashier.
**AC** GIVEN a visit with no encounter WHEN the clinician starts THEN exactly one encounter is created in state `OPEN` linked to that visit. GIVEN a visit with an existing `OPEN`/`AWAITING_RESULTS`/`RESULTS_READY` encounter WHEN the clinician starts THEN **no new encounter is created** and the existing one opens with all previously entered content. GIVEN concurrent starts by two clinicians THEN exactly one encounter exists (unique partial index on `visit + state NOT IN (SIGNED,VOIDED)`). GIVEN an unpaid gated consultation THEN the clinician sees the outstanding amount before the workspace opens. GIVEN encounter creation THEN the audit records provider, visit, patient and time.
**Perm** `encounter.create`. **Data** `Encounter`, `QueueEntry.state`. **Audit** Create + open.
**Err** Visit closed between queueing and starting → 409 `VISIT_CLOSED` (visit reopening is not defined in V1).
**UI** Workspace: left = context (patient, triage, history), centre = clerking sections, right = orders/prescriptions tray.
**Dep** QUE-003, TRI-009. **OOS** Templates per specialty (P2).
**Test** **Single-encounter-per-visit invariant under concurrency** (mandatory regression test every release).

**ENC-002 · Resume an existing open encounter · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want to reopen the same encounter after the patient returns from the lab, cashier or another room so my notes continue where I left them. **Value** **The core correction of the previous design mistake.**
**Pre** Encounter in `OPEN`/`AWAITING_RESULTS`/`RESULTS_READY`; user is the author or has takeover rights. **Trig** Clinician clicks the patient in "On hold"/"Ready to resume", or opens the visit.
**Flow** Load the same encounter ID with all sections, draft text, orders, results and prescriptions → state moves to `OPEN` if it was `RESULTS_READY` → queue entry returns to `IN_SERVICE`.
**Alt** Encounter authored by another clinician → read-only unless takeover (ENC-022).
**AC** GIVEN an encounter left in `AWAITING_RESULTS` two hours ago WHEN resumed THEN the encounter ID is unchanged, every previously entered field is present verbatim, and the previously placed orders are listed with their current statuses. GIVEN resume from `RESULTS_READY` THEN released results display inline in the encounter and the state becomes `OPEN`. GIVEN a resume across a logout/login boundary THEN behaviour is identical. GIVEN a resume THEN an audit event `ENCOUNTER_RESUMED` records actor and previous state. GIVEN the visit was closed in error WHEN resume is attempted THEN 409 `VISIT_CLOSED` and neither the Encounter nor its queue entry is modified; visit reopening is **not defined** by the supplied V1 stories and must be separately specified before any implementation. GIVEN an encounter `AWAITING_RESULTS` with only 1 of 3 blocking results released WHEN the clinician resumes early THEN the same encounter opens (`OPEN`), the consultation queue entry returns to `IN_SERVICE`, and the remaining laboratory work continues undisturbed — early manual resume never creates a second encounter.
**Perm** `encounter.update` (author) or `encounter.takeover`. **Data** `Encounter` state, audit.
**Err** Two devices resuming the same encounter → ETag conflict on save with a field-level diff.
**UI** "Ready to resume" list item shows what changed ("3 results released").
**Dep** QUE-006, LAB-018. **OOS** Real-time collaborative editing.
**Test** Journey-B resume with identical encounter ID asserted.

**ENC-003 · Patient context panel in the encounter · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want the patient's key background beside my note so I don't switch screens.
**AC** GIVEN an open encounter THEN the context panel shows: name, sex, age (with "est." if estimated), patient number, allergies (or NKA / not recorded), chronic flags, last 3 visits with dates and primary diagnoses, active prescriptions from the last 30 days, and the last 3 lab results with dates. GIVEN a minor THEN guardian and weight are shown. GIVEN no history THEN each section shows an explicit empty state. GIVEN the panel is opened THEN a single access-audit event is written for the encounter view, not one per sub-section.
**Perm** `encounter.read` + `patient.read`. **Dep** PAT-009. **OOS** Cross-facility history unless the explicitly authorised external BRN-005 policy grants the dedicated same-organisation capability; any such read remains audited and never weakens cross-tenant RLS.
**Test** Payload authorisation; empty states.

**ENC-004 · Triage context inside the encounter · P0 · `CLINICIAN`** — see TRI-009 for the reciprocal view.
**AC** GIVEN triage exists THEN vitals with units, BMI, acuity, complaint, recorder and time appear without extra navigation and are read-only to the clinician. GIVEN the clinician needs new vitals THEN they can request a repeat (creates a nursing task in the triage queue, QUE-005 / TRI-010) rather than editing the nurse's record.
**Perm** `triage.read`. **Dep** TRI-009. **Test** Read-only enforcement (API rejects clinician edits to triage).

**ENC-005 · Presenting complaint · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want to record the presenting complaint(s) and duration so the note starts correctly.
**AC** GIVEN one or more complaints entered (text up to 500 chars each, optional duration value + unit `HOURS|DAYS|WEEKS|MONTHS`) THEN they are stored as an ordered list and printed as such. GIVEN the triage complaint exists THEN it is offered as a one-click copy into this field and remains separately visible. GIVEN an encounter saved without a presenting complaint THEN signing is blocked (ENC-017) although drafting is allowed.
**Data** `Encounter.complaints[]`. **Dep** ENC-015. **Test** Sign-blocking rule.

**ENC-006 · History of presenting complaint · P0 · `CLINICIAN`**
**AC** GIVEN free text up to 4000 characters THEN it saves, autosaves (ENC-015), preserves line breaks, and renders identically on print. GIVEN the field exceeds the limit THEN a clear character counter and a 400 error prevent silent truncation.
**Data** `Encounter.hpc`. **Test** Round-trip of long text with newlines.

**ENC-007 · Review of systems (optional, structured-lite) · P2 · `CLINICIAN`**
**AC** GIVEN a configurable system checklist (CVS, RS, GIT, CNS, GUS, MSS) THEN the clinician can mark each `NOT_ASSESSED|NORMAL|ABNORMAL` with a free-text note, and only assessed systems print. GIVEN nothing is marked THEN the section is omitted from print entirely.
**Data** `Encounter.ros[]`. **OOS** Symptom coding.

**ENC-008 · Past medical history · P0 · `CLINICIAN`**
**AC** GIVEN chronic conditions selected from the configurable list plus free text THEN they save against the **encounter** and optionally promote to a patient-level problem list entry (ENC-009) when the clinician ticks "add to problem list". GIVEN triage chronic flags THEN they are prefilled and editable, labelled "from triage".
**Data** `Encounter.pmh`, `PatientProblem` (if promoted). **Test** Promotion behaviour.

**ENC-009 · Patient problem list · P1 · `CLINICIAN`**
**Story** As a clinician I want a persistent list of the patient's ongoing problems so every future visit starts informed.
**AC** GIVEN a problem added with onset date and status `ACTIVE|RESOLVED` THEN it appears on the patient header/context in all future encounters until resolved. GIVEN a problem is resolved THEN it is retained with a resolution date and is excluded from the active display. GIVEN problem changes THEN they are audited with actor and encounter reference.
**Data** `PatientProblem`. **OOS** Automatic derivation from diagnoses (OD-08). **Test** Persistence across visits.

**ENC-010 · Current medications in clerking · P0 · `CLINICIAN`**
**AC** GIVEN medications prefilled from triage and from prescriptions dispensed in the last 30 days THEN the clinician can confirm, edit or add entries as free text; the stored value is the clinician's confirmed list, with the source of each line indicated. GIVEN "none" is selected THEN it is stored explicitly and distinguishable from an unanswered field.
**Data** `Encounter.current_meds[]`. **Dep** TRI-005, DSP-012. **OOS** Interaction checking (AS-11).

**ENC-011 · Allergies review in clerking · P0 · `CLINICIAN`**
**AC** GIVEN patient allergies exist THEN the clinician must acknowledge or update them before signing (a single "reviewed" tick with timestamp). GIVEN allergy status is "not recorded" THEN signing is blocked until the clinician records `NKA`, `UNKNOWN`, or one or more allergies. GIVEN an allergy is added here THEN it is stored at patient level (TRI-004) and immediately reflected in the header.
**Data** `PatientAllergy`, `Encounter.allergies_reviewed_at`. **Dep** TRI-004, ENC-017. **Test** Sign-blocking on unrecorded allergy status.

**ENC-012 · Family and social history · P2 · `CLINICIAN`**
**AC** GIVEN free-text family history and structured-lite social fields (smoking `NEVER|FORMER|CURRENT`, alcohol `NEVER|OCCASIONAL|REGULAR`, occupation) THEN they save and print when populated and are omitted when empty.
**Data** `Encounter.fh`, `Encounter.sh`. **OOS** Risk scoring.

**ENC-013 · Surgical / obstetric / drug history · P1 · `CLINICIAN`,`MIDWIFE`**
**AC** GIVEN past surgeries (procedure, year, facility) as repeatable rows THEN they save and display in the context panel of future encounters. GIVEN a female patient of reproductive age THEN obstetric summary fields (gravida, para, living children) are available and, when the ANC module is enabled, are shared with the ANC record (ANC-003) as a single source of truth.
**Data** `Encounter.surgical_history[]`, `PatientObstetricSummary`. **Dep** ANC-003. **Test** Single-source consistency between ENC and ANC.

**ENC-014 · Examination findings · P0 · `CLINICIAN`**
**AC** GIVEN general examination free text plus per-system examination fields (each optional, up to 2000 chars) THEN only populated sections are stored and printed. GIVEN a "normal examination" quick action THEN it inserts editable template text and never auto-signs or auto-fills clinical findings the clinician has not reviewed. GIVEN examination text THEN it is included in the signed note verbatim.
**Data** `Encounter.examination`. **OOS** Body diagrams, images (P2).

**ENC-015 · Autosave and explicit draft save · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want my typing preserved even if the power or network drops, because power cuts are routine. **Value** Prevents the single most rage-inducing failure in Ugandan clinic software.
**Pre** Encounter `OPEN`. **Trig** Typing pauses (debounced 3 s) or explicit Save.
**Flow** Draft content PATCHed to the server with an ETag; success shows "Saved HH:MM:SS"; failure shows an unmistakable "Not saved — retrying" state with a manual retry.
**Alt** Offline/failed → content retained **in memory only** with a persistent warning banner; the clinician is warned not to navigate away; no PHI is written to browser storage (AUTH-013).
**AC** GIVEN a clinician types HPC text and pauses 3 seconds THEN the draft is persisted server-side and the UI shows a saved indicator with the server timestamp. GIVEN the browser is closed and reopened after an autosave THEN resuming the encounter shows the saved content. GIVEN the network fails during autosave THEN the UI shows "Not saved" persistently (not a transient toast) and retries with backoff; on reconnection the content saves without duplication. GIVEN a stale ETag (another device edited) THEN the save returns 412 and the clinician is shown both versions to reconcile — content is never silently overwritten. GIVEN the idle lock fires (AUTH-012) THEN the draft is already persisted and no content is lost.
**Perm** `encounter.update`. **Data** `Encounter` draft fields, `version`. **Audit** Autosaves are **not** individually audited (volume); a single `ENCOUNTER_DRAFT_UPDATED` summary per session-minute is retained.
**Err** Two tabs; power loss mid-request.
**UI** Persistent save-state chip near the title; never a disappearing toast as the only indicator.
**Dep** AUD-012, AUTH-012, AUTH-013. **OOS** Offline queueing.
**Test** Kill-the-tab test; 412 reconciliation UI.

**ENC-016 · Park encounter as awaiting results · P0 · `CLINICIAN`,`MIDWIFE` (ANC encounters)`
**Story** As a clinician I want to send the patient for tests and free my room without signing the note. **Value** Makes Journeys B and D real.
**Pre** Encounter `OPEN` with ≥1 non-terminal lab order (or an explicit "awaiting other" reason). **Trig** Clinician clicks "Send for investigations / park".
**Flow** Encounter `OPEN → AWAITING_RESULTS`; consultation queue entry `IN_SERVICE → ON_HOLD(AWAITING_RESULTS)` (QUE-006) — the held entry is the return point. Under `LABORATORY=PAY_BEFORE`, the cashier QueueEntry is the patient's active current location and no patient-facing lab QueueEntry exists until qualifying payment; then the lab QueueEntry becomes the active location. Under `PAY_AFTER`/no gate, the lab QueueEntry may be active immediately. The entries coexist with only one `IN_SERVICE` at any instant; patient added to the clinician's "Awaiting results" list; a patient-facing slip can be printed showing where to go (cashier/lab).
**Alt** (a) No open orders → the clinician must choose a reason (`AWAITING_PROCEDURE`, `AWAITING_PAYMENT`, `PATIENT_STEPPED_OUT`) and the parked state still holds. (b) Clinician parks and goes off shift → the patient remains on a **department-level** awaiting-results list so any clinician can pick up (with takeover, ENC-022).
**AC** GIVEN an encounter with 3 ordered tests WHEN the clinician parks it THEN the encounter is `AWAITING_RESULTS`, unsigned, fully editable on resume, and appears in the clinician's "Awaiting results" list with an elapsed timer. GIVEN parking THEN no diagnosis, prescription or invoice finalisation is required. GIVEN parking THEN the patient remains counted as present in the facility (REP-002). GIVEN the clinician logs out THEN the parked encounter persists and reappears at next login. GIVEN a parked encounter THEN attempting to sign it while orders are non-terminal produces a confirmation prompt (ENC-018), not a silent block.
**Perm** `encounter.update`. **Data** `Encounter.state`, `QueueEntry`, audit. **Audit** Park with reason and referenced orders.
**Err** Parking with zero orders and no reason → 400.
**UI** Prominent "Send for investigations" primary action next to Save; confirmation shows what the patient must do next.
**Dep** LAB-002, QUE-006. **OOS** Auto-park on order placement (deliberate: the clinician decides).
**Test** Journey B end-to-end.

**ENC-017 · Sign / finalise the encounter · P0 · `CLINICIAN`,`MIDWIFE` (never nurses, never admins)**
**Story** As a clinician I want to sign my note so it becomes the legal, immutable record of the consultation. **Value** Record integrity, medico-legal defensibility, and the trigger for downstream handoffs.
**Pre** Normal Sign action: Encounter `OPEN` or `RESULTS_READY`, user is the author (or has taken over), required minimum content present. The only direct signing path from `AWAITING_RESULTS` is the explicit ENC-018 "Sign now" action. **Trig** Clinician clicks Sign.
**Flow** (1) Server validates minimum content: ≥1 presenting complaint, allergy status recorded/reviewed, ≥1 diagnosis (working or final) **or** an explicit "no diagnosis — reason" entry, and a disposition (DX-006). (2) Confirmation dialog summarising what will become immutable and listing any non-terminal orders. (3) On confirm: `Encounter SIGNED` with `signed_by`, `signed_at`, provider name/cadre/licence snapshot, content hash (AUD-003), `version=1`. (4) Downstream events fire: prescriptions `DRAFT → ACTIVE` (RX-005), procedure orders released to the treatment room, and queue entry `COMPLETED` with onward routing chosen by the clinician (pharmacy/cashier/exit). Charges are created by their source events under BIL-001; signing never creates a second consultation charge.
**Alt** (a) Non-terminal lab orders exist → the decision is governed **entirely by ENC-018**: "Park and wait for results" or "Sign now — results will be added as an addendum"; ENC-017 itself offers no independent sign-anyway path. (b) Minimum content missing → 400 with a checklist of what is missing. (c) The consultation charge is unpaid under `PAY_AFTER` → signing proceeds; the invoice remains outstanding.
**AC** GIVEN an encounter missing a diagnosis WHEN sign is attempted THEN it is rejected with `DIAGNOSIS_REQUIRED` and the note remains editable. GIVEN a valid encounter WHEN signed THEN all clinical fields become read-only via the API (any PATCH returns 409 `RECORD_SIGNED`), a content hash is stored, and the signed note is printable with the provider's name, cadre and licence number. GIVEN signing THEN any `DRAFT` prescription for that encounter becomes `ACTIVE` and appears in the pharmacy queue within 15 seconds. GIVEN signing with an outstanding lab order through ENC-018 THEN the encounter is marked `signed_with_pending_orders=true`. GIVEN signing THEN an audit event records actor, timestamp, content hash and the downstream events triggered. GIVEN a chargeable consultation already charged at check-in THEN signing creates no second consultation line. GIVEN two sign requests with the same idempotency key THEN the encounter is signed once and no duplicate prescriptions are activated.
**Perm** `encounter.sign` (`CLINICIAN`,`MIDWIFE` only). **Data** `Encounter` (state, signature snapshot, hash), `Prescription`, `Invoice`, `QueueEntry`. **Audit** High-value; hash retained.
**Err** Signing an already-signed encounter (409); signing after visit closure → 409 `VISIT_CLOSED` — the encounter, its queue entry and any draft prescriptions are unchanged, no activation and no downstream fan-out occurs (the only post-closure clinical activity is the defined LAB-023/addendum workflow; visit reopening is not defined in V1); clinician's licence expired (warn, do not block — OD-04).
**UI** Sign is visually distinct and requires explicit confirmation; the dialog is a checklist, not a wall of text.
**Dep** DX-001, DX-002, DX-006, RX-005, REC-001, BIL-001, AUD-003. **OOS** Cryptographic e-signature with personal keys, co-signing (P2).
**Test** Immutability enforcement at API level; downstream event fan-out; idempotent sign.

**ENC-018 · Sign with pending investigations (explicit choice) · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want a clear choice between parking and signing when results are still pending, because sometimes I treat empirically and the result is for follow-up.
**AC** GIVEN non-terminal blocking investigation orders exist WHEN Sign is clicked — whether the encounter is currently `OPEN` or `AWAITING_RESULTS` — THEN the ENC-018 dialog governs the decision and lists each pending test with exactly two actions: "Park and wait for results" or "Sign now — results will be added as an addendum" (neither preselected). **Path A — `OPEN` + Park:** atomically `OPEN → AWAITING_RESULTS` and consultation entry `IN_SERVICE → ON_HOLD(AWAITING_RESULTS)` (executing ENC-016); lab/payment routing proceeds normally. **Path B — `OPEN` + Sign now:** atomically `OPEN → SIGNED` with `signed_with_pending_orders=true` and consultation entry `IN_SERVICE → COMPLETED` with completion reason `SIGNED_WITH_PENDING_RESULTS`; items remain active; the visit may later close `CLOSED(PENDING_RESULTS)` subject to REC-012. **Path C — `AWAITING_RESULTS` + Sign now:** `AWAITING_RESULTS → SIGNED` without a fake resume to `OPEN` (and never via `ON_HOLD → IN_SERVICE → COMPLETED`), sets `signed_with_pending_orders=true`, leaves the lab order active, and **atomically completes the held consultation queue entry** `ON_HOLD → COMPLETED` with completion reason `SIGNED_WITH_PENDING_RESULTS` — the entry is terminal, never becomes `READY_TO_RESUME`, and is not revived when results later release (LAB-023 applies instead). Only then may the visit close `CLOSED(PENDING_RESULTS)`, subject to REC-012's remaining conditions. **Path D — `AWAITING_RESULTS` + Wait:** the encounter stays `AWAITING_RESULTS` and the entry `ON_HOLD` toward `READY_TO_RESUME` — the clinician choices remain distinct. On release the result attaches to the encounter as an addendum with a notification to the signer (LAB-023); the visit is flagged `POST_CLOSURE_ACTIVITY` as already specified — the visit, the signed encounter and the completed queue entry are never reopened or mutated.
**Dep** ENC-016, ENC-017, LAB-023. **Test** Both branches produce correct downstream states. Mandatory tests: (1) encounter `AWAITING_RESULTS` + consultation entry `ON_HOLD` + lab entry `COMPLETED` + item `SAMPLE_COLLECTED` → "Sign now" → encounter `SIGNED` with `signed_with_pending_orders=true`, consultation entry `COMPLETED(SIGNED_WITH_PENDING_RESULTS)`, item still `SAMPLE_COLLECTED`, visit passes the queue precondition of REC-012 and closes `CLOSED(PENDING_RESULTS)`; a later release leaves the encounter `SIGNED`, the visit `CLOSED(PENDING_RESULTS)`, the entry `COMPLETED`, and triggers LAB-023 only. (2) encounter `OPEN` + blocking item + Sign → the same dialog: "Park" yields `AWAITING_RESULTS` + `ON_HOLD`; "Sign now" yields `SIGNED` + `IN_SERVICE → COMPLETED(SIGNED_WITH_PENDING_RESULTS)` directly.

**ENC-019 · Void an encounter created in error · P1 · `SUPERVISOR`; secondary `CLINICIAN`**
**Story** As a supervisor I want to void an encounter opened on the wrong patient so the wrong chart isn't polluted.
**Pre** Encounter exists. **Flow** Void with mandatory reason (min 20 chars) → state `VOIDED` → content hidden from the clinical timeline but retained in full for audit → related draft prescriptions cancelled, unbilled charges voided, released lab results **not** deleted but detached and flagged for review.
**Alt** Signed encounter → voiding requires `SUPERVISOR` + reason and produces a visible "VOIDED" watermark on any reprint; the record is never physically deleted.
**AC** GIVEN a voided encounter THEN it does not appear in the patient's clinical history by default, is retrievable via an "include voided" filter by authorised roles, and is excluded from diagnosis and visit statistics. GIVEN voiding THEN the audit stores the full prior content hash, the reason and the actor. GIVEN a voided encounter with a paid invoice THEN the payment is untouched and a reversal must be handled separately (PAY-008).
**Perm** `encounter.void`. **Err** Wrong-patient encounters that already drove dispensing → dispense reversal is a separate manual process (DSP-016).
**Test** Statistics exclusion; audit completeness.

**ENC-020 · View a signed encounter · P0 · `CLINICIAN`,`MIDWIFE`,`SUPERVISOR`; limited others**
**AC** GIVEN a signed encounter THEN it renders read-only with the full note, orders and their results, diagnoses, prescriptions, provider identity snapshot, signed timestamp and version number, plus any addenda in chronological order. GIVEN a nurse or pharmacist opens it THEN they see only the sections their capabilities allow (pharmacist: diagnoses + prescriptions + allergies; nurse: vitals + instructions), enforced in the API payload. GIVEN any view THEN exactly one access audit event is written with `category=PHI_READ` and `action=PATIENT_RECORD_VIEWED`.
**Perm** `encounter.read` variants. **Dep** AUD-001. **Test** Per-role payload assertions.

**ENC-021 · Clinician's personal worklists · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want my own dashboard of who is waiting, who is with me, who is awaiting results and what is unsigned, so nothing falls through. **Value** The clinician's home screen and the primary anti-dead-end mechanism.
**AC** GIVEN a clinician signs in THEN their home shows four counted lists: **Waiting for me** (queue), **In progress** (open encounters), **Awaiting results** (encounters in `AWAITING_RESULTS`), and **Ready to review** (encounters in `RESULTS_READY`), plus **Unsigned** (encounters `OPEN`/`RESULTS_READY` older than 24 hours). GIVEN a result is released THEN the "Awaiting results" row's progress badge updates within 30 seconds ("2 of 3 results ready"); the patient moves to "Ready to review" only when ALL blocking dependencies are terminal (LAB-018). GIVEN an encounter has been unsigned for more than 24 hours THEN it appears in the "Unsigned" list and on the supervisor dashboard (REP-015). GIVEN a clinician with no patients THEN each list shows an explicit zero state.
**Perm** `encounter.read` (own) + `queue.read`. **Dep** QUE-006, LAB-018, REP-015. **Test** Badge transition timing; 24-hour unsigned rule.

**ENC-022 · Transfer or take over an encounter · P1 · `SUPERVISOR`,`CLINICIAN`**
**Story** As a clinician taking over from a colleague who has gone off shift, I want to continue their unsigned encounter so the patient isn't restarted.
**Pre** Encounter non-terminal; original author unavailable or consenting. **Flow** Request takeover with reason → encounter's `current_provider` changes while `created_by` is preserved → both providers are recorded on the note and on the print ("Started by Dr A, completed by Dr B") → the new provider signs. Each note line retains its own author ID.
**AC** GIVEN a takeover THEN the encounter ID is unchanged, all content is preserved, and the printed note names both providers with their roles and times. GIVEN a takeover without a reason THEN it is rejected. GIVEN a takeover THEN the original author retains read access and is notified in their worklist. GIVEN a signed encounter THEN takeover is not possible (use addendum, ENC-023).
**Perm** `encounter.takeover` (`SUPERVISOR`, or `CLINICIAN` when the author's session has been inactive for a configured period). **Audit** High-value.
**Dep** USR-004, QUE-013. **Test** Dual-provider print.

**ENC-023 · Amend a signed encounter (addendum) · P0 · `CLINICIAN` (author); secondary `SUPERVISOR`**
**Story** As a clinician I want to add a correction or new information to a signed note without altering the original, so the record stays truthful. **Value** Real clinical need + legal integrity.
**Pre** Encounter `SIGNED`. **Trig** New information, error found, late result.
**Flow** Create an addendum: type (`CORRECTION`|`ADDITIONAL_INFORMATION`|`LATE_RESULT`|`CLARIFICATION`), text, mandatory reason → addendum signed separately with its own timestamp and hash → encounter `version` increments; the original text remains visible and unaltered.
**Alt** Addendum by a non-author → permitted for `SUPERVISOR` with reason; the addendum is attributed to them, not to the original author.
**AC** GIVEN a signed encounter WHEN an addendum is added THEN the original content is byte-identical and its hash still validates, the addendum appears below the original with its own author, timestamp and reason, and the encounter version becomes 2. GIVEN a printed note after amendment THEN it shows the original content followed by all addenda in order, each clearly labelled. GIVEN an attempt to PATCH the original signed fields THEN 409 `RECORD_SIGNED` regardless of role. GIVEN an addendum THEN a high-value audit event is written.
**Perm** `encounter.amend`. **Data** `EncounterAddendum`, `Encounter.version`. **Audit** High-value non-PHI metadata with version references and hashes; addendum text remains only in the signed domain record.
**Err** Addendum spam; addenda on voided encounters (blocked).
**UI** Amend button on the signed view; the dialog states plainly that the original will remain visible.
**Dep** AUD-003, AUD-008, LAB-023. **OOS** Retracting an addendum (add another).
**Test** Hash-validation-after-amendment test.

**ENC-024 · Print / export the consultation note · P0 · `CLINICIAN`; secondary `RECEPTIONIST`**
**AC** GIVEN a signed encounter WHEN printed THEN the document contains the facility header (TEN-003), patient identifiers, visit date, triage vitals, full clerking content, diagnoses, investigations with results (if released), treatment plan, prescriptions, follow-up, provider name/cadre/licence, signature timestamp and version, plus a "Page X of Y". GIVEN an unsigned encounter WHEN printed THEN the document is watermarked "DRAFT — NOT SIGNED" and the action is audited. GIVEN a reprint THEN it is audited with actor and time (AUD-009).
**Perm** `encounter.print`. **Dep** TEN-003, RCP-003, RCP-004. **OOS** PDF email/WhatsApp delivery.
**Test** Snapshot of A4/A5 layouts; draft watermark.

---
## 12. EPIC LAB — Laboratory Orders and Results

### 12.0 Why the V1 lab statuses are what they are

Proposed set, evaluated: `ORDERED`, `AWAITING_PAYMENT`, `READY_FOR_COLLECTION`, `SAMPLE_COLLECTED`, `IN_PROGRESS`, `RESULT_ENTERED`, `VERIFIED`, `RELEASED`, `CANCELLED`.

**Kept, with justification:**

- **`ORDERED`** — the clinician's intent exists; the lab has not accepted it. Needed as the entry state and for "ordered but never actioned" reporting. *(Canonical term: the initial lab status is `ORDERED`, never "REQUESTED".)*
- **`AWAITING_PAYMENT`** — mandatory because `PAY_BEFORE` is the dominant Ugandan private-sector rule and the lab must be able to see, but not process, unpaid work. Only entered when policy says so.
- **`READY_FOR_COLLECTION`** — the operational "lab may now proceed" state; distinct from `ORDERED` because the gate (payment/consent/preparation) has cleared. Merging it into `ORDERED` would lose the ability to show the lab an actionable list.
- **`SAMPLE_COLLECTED`** — the physical custody event. Without it, "the patient says they gave blood" is unresolvable and rejection handling has no anchor.
- **`RESULT_ENTERED`** — result exists but is not clinically usable. Essential to prevent clinicians acting on unverified values.
- **`VERIFIED`** — a second (or explicitly configured same-person) check has occurred.
- **`RELEASED`** — visible to the clinician and printable. Kept **separate from `VERIFIED`** because some facilities verify in batch and release individually, and because release is the event that drives the clinician's `RESULTS_READY` state and the patient's report.
- **`CANCELLED`** — terminal, with reason.
- **`SAMPLE_REJECTED`** — **added** (not in the proposed list, but required): haemolysed, insufficient, mislabelled, or wrong container samples are routine, and without an explicit state the order silently stalls. It is a non-terminal, recoverable state: recollection returns the item to `READY_FOR_COLLECTION`; if recollection will not occur, an authorised clinician or supervisor transitions it to terminal `CANCELLED`.

**Dropped, with justification:**

- **`IN_PROGRESS`** — for a small clinic lab running RDTs, microscopy and a haematology analyser, the interval between "sample collected" and "result typed" is minutes and no one will maintain a separate click. It adds a mandatory transition with no consumer. **Decision: dropped from V1**; if a facility later needs bench tracking, it can be added without breaking the machine (it would sit between `SAMPLE_COLLECTED` and `RESULT_ENTERED`). Recorded as OD-10 for the pilot to confirm.

State granularity is at the **`LabOrderItem`** (per test) level; the **`LabOrder`** state is derived (LAB-006), because a clinician frequently orders a CBC that comes back in ten minutes and a culture that takes three days.

---

**LAB-001 · Laboratory test catalogue · P0 · `FACILITY_ADMIN`; secondary `LAB_TECH`**
**Story** As an administrator I want to define the tests we offer, with their analytes and reference ranges, so results are structured and consistently reported.
**Pre** Lab module enabled. **Trig** Setup.
**Flow** Create `LabTestDefinition`: name, short code, specimen type (blood/urine/stool/sputum/swab/other), container/tube, method (optional), result type (`NUMERIC`, `CODED`, `TEXT`, `PANEL`), turnaround target, linked `Service` for pricing (CAT-001), active flag. For `PANEL`, define ordered analytes each with their own result type, unit, decimal places and reference ranges. Ranges may be defined by sex and age band, plus a free-text reference note.
**Alt** Seed a starter catalogue for a Ugandan small lab (Malaria RDT, Malaria BS, CBC/FBC panel, Hb, blood group & Rh, RBS/FBS, widal, H. pylori, HIV rapid, urinalysis panel, urine HCG, stool routine, Hep B surface antigen, RPR/syphilis, sickling test, ESR, LFTs, RFTs, urea/creatinine) with editable defaults.
**AC** GIVEN a `PANEL` test with 8 analytes THEN result entry presents exactly those 8 fields in the defined order with their units. GIVEN a numeric analyte with a range 4.0–11.0 ×10⁹/L THEN entering 13.2 stores the value and flags it `HIGH` **without any interpretive text**. GIVEN sex- or age-specific ranges THEN the range applied is selected from the patient's sex and age at the time of the result and the applied range is stored on the result. GIVEN a test with no linked priced service THEN it cannot be ordered and an admin setup warning is shown. GIVEN a catalogue change THEN previously released results retain the ranges and units captured at release.
**Perm** `lab.catalogue.manage`. **Data** `LabTestDefinition`, `LabAnalyte`, `LabReferenceRange`. **Audit** Definition changes.
**Err** Changing a unit after results exist → new version of the definition; old results unaffected.
**UI** Test list with panel expansion; range editor with sex/age bands.
**Dep** CAT-001. **OOS** LOINC coding, analyser interfacing, quality-control workflows.
**Test** Range-selection-by-demographics; snapshot immutability.

**LAB-002 · Clinician orders investigations · P0 · `CLINICIAN`,`MIDWIFE`; secondary `LAB_TECH`**
**Story** As a clinician I want to order one or more tests from inside the encounter so the lab knows exactly what to do and for whom.
**Pre** Encounter `OPEN`/`RESULTS_READY`; lab module enabled; `lab.order.create`. **Trig** Clinician opens the Investigations tray.
**Flow** Search/select tests (multi-select, with a facility "frequently ordered" shortlist) → set priority per order (`ROUTINE`|`URGENT`) → optional clinical notes to the lab (free text, e.g. "on antimalarials since yesterday") → optional required-by time for urgent → confirm → one `LabOrder` (items in state `ORDERED`) with n `LabOrderItem`s, linked to the encounter, visit and patient.
**Alt** (a) Duplicate test already ordered in this visit and not cancelled → warn "CBC already ordered 20 minutes ago (status: sample collected)" and require confirmation. (b) Test's service is not priced → not orderable. (c) Lab module disabled → tray hidden and API 403.
**AC**
- GIVEN a patient with an open encounter and a clinician with `lab.order.create` WHEN the clinician orders a CBC THEN a `LabOrder` is created **linked to the existing encounter**, the encounter remains `OPEN` and unsigned, the laboratory work queue displays the order, the clinician may leave the encounter without signing it, and the patient appears in the clinician's "Awaiting results" state once parked (ENC-016).
- GIVEN three tests ordered together THEN one order with three items is created, each item independently trackable.
- GIVEN priority `URGENT` THEN the order sorts above routine orders in the lab queue and is visually marked.
- GIVEN ordering THEN a charge event is emitted per orderable item (LAB-004) exactly once, even on retry with the same idempotency key.
- GIVEN a signed encounter THEN new orders cannot be added to it (a new encounter or an addendum-linked order is required — OD-07).
**Perm** `lab.order.create` (`CLINICIAN`,`MIDWIFE`; **not** nurses in V1 — see OD-21). **Data** `LabOrder`, `LabOrderItem`, charge events, audit. **Audit** Order creation referencing `LabOrder`/`LabOrderItem` IDs and version hashes, priority and ordering actor; ordered test details remain in the protected domain records.
**Err** Ordering after the patient has left; ordering a test whose specimen the facility can't collect (catalogue should be curated).
**UI** Tray with search, shortlist chips, selected-items list with per-item remove, single confirm.
**Dep** ENC-001, LAB-001, LAB-004. **OOS** Order sets/protocols, standing orders, external lab referral orders (LAB-025 is P2).
**Test** Encounter linkage and open-state assertions (the canonical Journey-B acceptance test).

**LAB-003 · Order priority and clinical notes to the lab · P1 · `CLINICIAN`**
**AC** GIVEN priority `URGENT` THEN the lab queue shows the order at the top with an urgent marker and the target turnaround from the catalogue. GIVEN clinical notes THEN they are visible to the lab technician on the work item and are printed on the internal worksheet, but are **not** printed on the patient-facing report unless configured.
**Data** `LabOrder.priority`, `clinical_notes`. **Dep** LAB-002. **Test** Sort and visibility.

**LAB-004 · Charge generation on order · P0 · `SYSTEM`**
**Story** As a facility I want ordering a test to create the charge automatically so we never do unbilled lab work.
**Flow** On order creation, for each item resolve the linked service and facility price → create invoice lines on the visit's invoice with `source=LAB_ORDER_ITEM` and `source_id` → invoice `ISSUED`. For `LABORATORY=PAY_BEFORE`, order/item creation and its required charge lines are one transaction: failure to create a required line fails the initiating operation and leaves no actionable item.
**AC** GIVEN three ordered tests THEN three invoice lines exist with the current facility prices snapshotted, referencing the specific order items. GIVEN the same order submitted twice with one idempotency key THEN three lines exist, not six (unique constraint on `(invoice, source_type, source_id)` — BIL-013). GIVEN `LABORATORY=PAY_BEFORE` and required charge creation fails THEN the order operation returns an explicit billing/setup error and no actionable `LabOrderItem` or lab worklist entry exists. GIVEN an item is cancelled before collection THEN its invoice line is voided if unpaid, or flagged for refund/credit if paid (LAB-022). GIVEN a lab-only walk-in with no encounter THEN charges attach to the visit's invoice or to a standalone invoice for that patient.
**Data** `InvoiceLine`. **Audit** Charge creation with source. **Dep** BIL-001, BIL-013. **Test** Duplicate-line constraint; cancellation refund path.

**LAB-005 · Payment gate for laboratory work · P0 · `SYSTEM`; secondary `CASHIER`,`LAB_TECH`**
**Story** As a facility with a pay-before rule I want the lab to be unable to process unpaid tests, while still seeing them.
**Flow** If `LABORATORY=PAY_BEFORE`: item `ORDERED → AWAITING_PAYMENT`; the laboratory **worklist** shows it in a separate "Awaiting payment" section, not actionable. This worklist item is not a patient-facing LAB QueueEntry. The clinician's consultation entry remains `ON_HOLD(AWAITING_RESULTS)` and the patient is routed to a cashier `QueueEntry=WAITING`. When related invoice lines are fully paid, waived, or validly overridden, the items move to `READY_FOR_COLLECTION`, the cashier entry completes, and a patient-facing `QueueEntry(LAB)=WAITING` is created. If `PAY_AFTER`/`NO_GATE`: items go straight to `READY_FOR_COLLECTION` and the lab QueueEntry may be created immediately when the clinician sends the patient.
**Alt** Override by a user with `billing.gate.override` (reason mandatory) moves items to `READY_FOR_COLLECTION` while the charge stays outstanding.
**AC** GIVEN `PAY_BEFORE` and an unpaid lab charge WHEN the technician attempts to record collection THEN the action is refused with `PAYMENT_REQUIRED` and the outstanding amount is displayed. GIVEN `PAY_BEFORE` before payment THEN the unpaid item appears only in the non-actionable lab worklist, the cashier QueueEntry is `WAITING`, and no patient-facing LAB QueueEntry exists. GIVEN the cashier records qualifying payment for those lines THEN the items become `READY_FOR_COLLECTION`, the cashier entry becomes `COMPLETED`, and `QueueEntry(LAB)=WAITING` is created within 15 seconds. GIVEN a partial payment covering only 2 of 3 tests THEN exactly those 2 items become collectable and the third remains `AWAITING_PAYMENT` (allocation per PAY-005). GIVEN a required gated charge line is absent THEN the item cannot become actionable. GIVEN an override THEN the item becomes collectable, the charge remains outstanding, and the audit records the actor and reason.
**Data** Item state, `gate_policy_at_charge`. **Audit** Gate transitions and overrides.
**Err** Payment reversed after collection → the item continues (work already done) and the invoice returns to outstanding; flagged on REP-008. Payment reversed **before** collection under `PAY_BEFORE` → the item returns `READY_FOR_COLLECTION → AWAITING_PAYMENT`, the patient-facing Lab queue entry is cancelled (reason `PAYMENT_REVERSED` — including the `IN_SERVICE`-but-no-specimen-yet case, where collection is blocked immediately and any unsaved collection form is discarded), a cashier entry is created, and no active Lab entry remains until repayment (PAY-012).
**Dep** TEN-006, PAY-012. **Test** Partial-payment line-level gating.

**LAB-006 · Derived order status · P0 · `SYSTEM`**
**AC** LabOrder status is derived only. GIVEN all items `CANCELLED` THEN the order is `CANCELLED`. GIVEN all items terminal and at least one is `RELEASED` THEN the order is `COMPLETED`, including `RELEASED + CANCELLED` and `RELEASED + RELEASED`. GIVEN at least one item is `RELEASED` and at least one item remains non-terminal THEN the order is `PARTIALLY_RELEASED`, including `RELEASED + SAMPLE_COLLECTED`. GIVEN no item is released and at least one remains non-terminal THEN the order uses the pending/active derived presentation. GIVEN `ORDERED + SAMPLE_COLLECTED` THEN it uses that pending/active presentation. GIVEN mixed states THEN the worklist shows per-item states, never a misleadingly aggregated single state. `SAMPLE_REJECTED` is non-terminal and is not a readiness outcome.
**Data** Derived (computed, not stored, or stored as a denormalised cache updated in the same transaction). **Test** All state-combination permutations.

**LAB-007 · Laboratory work queue · P0 · `LAB_TECH`,`LAB_VERIFIER`**
**Story** As a lab technician I want a prioritised list of work so I know what to do next and nothing is missed.
**AC** GIVEN orders exist THEN the laboratory worklist shows sections: **Awaiting payment** (visible, not actionable), **To collect** (`READY_FOR_COLLECTION`), **Collected / in bench** (`SAMPLE_COLLECTED`), **To verify** (`RESULT_ENTERED`), **Rejected / action needed** (`SAMPLE_REJECTED`). These are LabOrderItem work states, not patient QueueEntry states or physical locations. GIVEN each row THEN it shows patient name and number, test(s), priority, ordering clinician, order time and elapsed time. GIVEN an urgent order THEN it sorts first within its section. GIVEN a technician without `lab.result.verify` THEN the "To verify" section is visible but its actions are disabled with an explanatory tooltip. GIVEN 200 items in a day THEN the queue paginates and meets both §7 targets: API operations ≤ 400 ms p95 and an end-to-end rendered usable state ≤ 2 s p95 under the 3G-equivalent profile.
**Perm** `lab.queue.read`. **Dep** LAB-002, LAB-005. **Test** Section membership per state.

**LAB-008 · Record sample collection / receipt · P0 · `LAB_TECH`; secondary `NURSE`**
**Story** As a lab technician I want to record that I have the specimen so custody is clear and the clock starts.
**Pre** Item `READY_FOR_COLLECTION`. **Flow** Verify patient identity (name + patient number read-back prompt) → select items collected (may be a subset) → record specimen type (defaulted from the catalogue), collection time (defaults to now, editable within limits), collector → generate a specimen ID per item or per container → print a specimen label if a printer exists → items `SAMPLE_COLLECTED`. Once the patient-facing collection/receipt interaction is complete, the active `QueueEntry(LAB)` becomes `COMPLETED`; bench processing continues through the items independently. If another specimen is immediately due, the lab entry may remain `IN_SERVICE` until that collection episode ends; if the patient must return later, a new patient-facing lab action is created through the existing recollection workflow.
**Alt** Sample collected by a nurse in the treatment room → the nurse records collection (with `lab.sample.collect`) and the lab records receipt; both timestamps are stored. Patient not present → cannot collect.
**AC** GIVEN two of three items collected THEN only those two become `SAMPLE_COLLECTED` and the third remains `READY_FOR_COLLECTION`. GIVEN collection THEN a unique specimen ID is generated per facility per day and printed on the label with patient name, number, test, date/time and collector initials. GIVEN the collection/receipt interaction ends THEN the patient-facing LAB QueueEntry is `COMPLETED` even while a collected item remains in bench processing. GIVEN an attempt to collect an `AWAITING_PAYMENT` item THEN it is refused (LAB-005). GIVEN payment is reversed mid-interaction while the entry is `IN_SERVICE` and no specimen has been recorded for the affected items THEN collection is refused with `PAYMENT_REQUIRED`, any unsaved collection form is discarded uncommitted, no `LabSpecimen` is created, and the entry is cancelled with reason `PAYMENT_REVERSED` (PAY-012/§22.1) — starting lab service alone is not the delivery boundary; the recorded specimen is. GIVEN collection THEN the audit records collector, time and specimen IDs.
**Perm** `lab.sample.collect`. **Data** `LabSpecimen`, item state.
**Err** Wrong patient's sample → rejection/relabel path (LAB-009) plus an incident note; label printer offline → handwritten fallback with the ID displayed large on screen.
**UI** Read-back identity prompt is a required checkbox, not decorative.
**Dep** TEN-007. **OOS** Barcode scanning (P2), chain-of-custody signatures.
**Test** Partial collection; specimen ID uniqueness.

**LAB-009 · Reject a sample / unable to process · P0 · `LAB_TECH`**
**Story** As a lab technician I want to record that a sample cannot be processed, with the reason, so the clinician knows and a recollection can happen. **Value** Without this, the order silently dies and the patient waits forever.
**Pre** Item `SAMPLE_COLLECTED` (or `READY_FOR_COLLECTION` when the patient cannot provide a sample). **Flow** Select item → reason (`HAEMOLYSED`, `INSUFFICIENT_VOLUME`, `CLOTTED`, `WRONG_CONTAINER`, `MISLABELLED`, `LEAKED`, `PATIENT_UNABLE_TO_PROVIDE`, `REAGENT_UNAVAILABLE`, `EQUIPMENT_DOWN`, `OTHER` + note) → item `SAMPLE_REJECTED` → the ordering clinician's worklist shows an alert; reception/nurse see a recollection task.
**Alt** Recollect → item returns to `READY_FOR_COLLECTION` with `recollection_count+1`, retaining the original order and **without a second charge** (unless the reason is patient-caused and facility policy says otherwise — OD-12); when the patient must return later, the completed prior lab QueueEntry is followed by the next patient-facing lab action. Cannot recollect → clinician or authorised supervisor cancels the item (LAB-022).
**AC** GIVEN a rejected sample THEN the ordering clinician sees the rejection with its reason in their worklist within 30 seconds and the encounter remains `AWAITING_RESULTS` until the item is recollected and eventually `RELEASED`, or explicitly `CANCELLED`; `SAMPLE_REJECTED` alone never makes an encounter `RESULTS_READY`. GIVEN a rejection THEN the patient is **never** left with no next step: the item appears in the "Action needed" lab section and on the reception recollection list. GIVEN recollection THEN no duplicate invoice line is created. GIVEN rejection THEN the audit records the reason, actor and time.
**Perm** `lab.sample.reject`. **Data** `LabOrderItem.rejection_*`, `recollection_count`.
**Err** Repeated rejections (>2) → flagged to the supervisor.
**UI** Reason list with a mandatory note for `OTHER`. **Dep** LAB-018, LAB-022. **Test** No-double-charge on recollection; dead-end prevention assertion.

**LAB-010 · Enter numeric and panel results · P0 · `LAB_TECH`**
**Story** As a lab technician I want to type results into the exact fields the test defines so nothing is ambiguous.
**Pre** Item `SAMPLE_COLLECTED`; `lab.result.enter`. **Flow** Open the item → the form renders the analytes from the catalogue with units and decimal precision → enter values → optional per-analyte comment → optional overall comment → save → item `RESULT_ENTERED`.
**AC** GIVEN a CBC panel with 8 analytes THEN all 8 fields are shown with units, and saving with 6 filled is allowed only if the unfilled ones are explicitly marked "not done" (no silent blanks in a released report). GIVEN a value outside the sanity bounds for the analyte (e.g. Hb 250 g/dL) THEN the save is rejected with a range error. GIVEN a value outside the reference range THEN it is stored with a `HIGH`/`LOW` flag and rendered with a neutral marker; **no interpretation, no advice, no suggested action is displayed anywhere**. GIVEN the entering technician THEN their identity and the entry time are stored. GIVEN a result saved THEN it is **not** visible to the ordering clinician until released (LAB-015).
**Perm** `lab.result.enter`. **Data** `LabResult` (v1), `LabResultAnalyteValue`. **Audit** Result-version reference, changed field names, actor, timestamp and hash; raw values remain only in the LabResult domain record.
**Err** Decimal/comma confusion → strict numeric parsing with an explicit hint; unit mismatch.
**UI** Keyboard-driven grid, Enter moves to the next analyte, reference range shown greyed beside each field.
**Dep** LAB-001. **OOS** Analyser import, delta checks, QC rules.
**Test** Not-done handling; invisibility before release.

**LAB-011 · Enter coded results · P0 · `LAB_TECH`**
**AC** GIVEN a test defined as `CODED` with options (e.g. Malaria RDT: `POSITIVE`/`NEGATIVE`/`INVALID`; Blood group: `A/B/AB/O` × `POSITIVE/NEGATIVE`) THEN the entry form presents exactly those options as a single-select and free text is not accepted in the coded field. GIVEN `INVALID` THEN a comment is mandatory. GIVEN a coded result THEN it prints as the option label and is countable in reports (REP-009).
**Data** `LabResult.coded_value`. **Test** Option enforcement.

**LAB-012 · Enter text/descriptive results · P1 · `LAB_TECH`**
**AC** GIVEN a `TEXT` result type (e.g. stool microscopy, urinalysis microscopy description) THEN a structured-lite form with a free-text area up to 2000 characters is provided, optionally with facility-defined template phrases that insert editable text. GIVEN a text result THEN it prints preserving line breaks.
**Dep** LAB-010. **Test** Long-text round trip.

**LAB-013 · Attach reference ranges and units to the stored result · P0 · `SYSTEM`**
**AC** GIVEN a released result THEN the report displays the value, unit, and the reference range **as it was at the time of release**, and changing the catalogue afterwards does not alter historical reports. GIVEN a patient-specific range selection (by sex/age) THEN the applied range is stored on the result row.
**Data** Snapshot fields on `LabResultAnalyteValue`. **Test** Catalogue-change immutability.

**LAB-014 · Save partial results within a panel · P1 · `LAB_TECH`**
**AC** GIVEN a panel where only some analytes are complete THEN the technician can save progress without moving the item to `RESULT_ENTERED`, and the queue shows it as "in entry" with the entering technician's name. GIVEN a partial save THEN the values are not visible to clinicians. GIVEN completion THEN the item transitions to `RESULT_ENTERED` in one explicit action.
**Dep** LAB-010. **Test** Visibility boundary.

**LAB-015 · Verify and release a result · P0 · `LAB_VERIFIER`; secondary `LAB_TECH`**
**Story** As the lab in-charge I want to check a result before the clinician can act on it, so we don't release a mistyped value. **Value** The safety gate of the lab loop.
**Pre** Item `RESULT_ENTERED`; `lab.result.verify`. **Trig** Verifier opens the "To verify" section.
**Flow** Review entered values against the reference ranges and any comments → either **Verify & release** (single action, default) or **Verify** then **Release** separately if the facility uses batch verification → item `VERIFIED → RELEASED` with verifier identity and timestamps → release event fires (LAB-018).
**Alt** Verifier rejects the entry → item returns to `SAMPLE_COLLECTED`/entry with a mandatory comment to the technician; the previous entry is retained as a non-released version.
**AC** GIVEN a result in `RESULT_ENTERED` WHEN the verifier releases it THEN the item becomes `RELEASED`, the ordering clinician's encounter transitions toward `RESULTS_READY` (LAB-018), and the result becomes printable. GIVEN the entering technician lacks `lab.result.verify` THEN they cannot release, and the action is absent and API-refused. GIVEN a released result THEN it cannot be edited; corrections require an amended version (LAB-017). GIVEN verification THEN the generic audit records the verifier, timestamp, released result-version reference and content hash; the exact values remain in the immutable result version. GIVEN a rejected entry THEN the technician sees the rejection with the comment in their queue.
**Perm** `lab.result.verify`. **Data** `LabResult.verified_by/at`, `released_at`, state. **Audit** High-value.
**Err** Verifier releasing their own entry — permitted only under LAB-016.
**UI** Side-by-side entered values and ranges; single prominent Release action.
**Dep** LAB-010, LAB-018. **Test** Author-cannot-self-release enforcement (unless LAB-016 is configured).

**LAB-016 · Single-technician facility configuration · P0 · `FACILITY_ADMIN`**
**Story** As a small facility with one lab technician I need results to be releasable by the person who entered them, because there is nobody else. **Value** Without this, the pilot lab stalls; with an unconfigured default, safety is silently lost.
**Flow** Facility setting `lab_allow_self_verification` (default **false**). When true, users holding both `lab.result.enter` and `lab.result.verify` may release their own entries; every such release is tagged `self_verified=true`.
**AC** GIVEN the setting is false and a technician holding both capabilities WHEN they attempt to release their own entry THEN it is refused with `SELF_VERIFICATION_NOT_ALLOWED`. GIVEN the setting is true THEN release succeeds, the result record is marked `self_verified`, and the fact is included on the printed report footer and in REP-009. GIVEN the setting is changed THEN it is audited with actor and reason.
**Perm** `facility.policy.manage`. **Audit** Setting change + each self-verified release. **Dep** LAB-015. **Test** Both configurations.

**LAB-017 · Correct or amend a released result · P0 · `LAB_VERIFIER`; secondary `SUPERVISOR`**
**Story** As the lab in-charge I want to correct a released result without erasing what the clinician already saw.
**Pre** Item `RELEASED`. **Flow** Create a new result version with corrected values + mandatory reason → previous version retained and marked superseded → the item stays `RELEASED` but at version n+1 → **the ordering clinician is alerted explicitly** and, if the encounter is already signed, an addendum is created noting the corrected result (LAB-023).
**AC** GIVEN a released Hb of 3.2 corrected to 13.2 THEN both versions are retained and visible, the report prints "AMENDED RESULT — supersedes version 1 released at [time]" with both values, and the clinician receives a high-visibility alert in their worklist that persists until acknowledged. GIVEN a signed encounter THEN an addendum is created automatically referencing the amendment (content authored by the system, attributed to the lab). GIVEN an amendment THEN the generic audit references both result versions/hashes and records actor and reason; the actual values remain in the LabResult version records. GIVEN a patient report was already printed THEN the reprint carries the amended marker and the print history shows both events.
**Perm** `lab.result.amend`. **Data** `LabResult` versions. **Audit** High-value.
**Err** Amending after the patient has been treated → alert must be unmissable; repeated amendments.
**UI** Red banner on the result; acknowledgement required by the clinician (recorded).
**Dep** LAB-023, AUD-008. **Test** Acknowledgement persistence; print markers.

**LAB-018 · Result-ready signalling to the clinician · P0 · `SYSTEM`**
**Story** As the platform I want to tell the ordering clinician the moment results are usable, so the patient is called back promptly.
**Trig** A blocking item reaching a terminal state (`RELEASED` via LAB-015 or `CANCELLED` via LAB-022). **Flow** On release: released items become immediately readable to authorised clinicians, with "n of m results ready" progress on the clinician's worklist. The encounter transitions `AWAITING_RESULTS → RESULTS_READY` and the held consultation queue entry `ON_HOLD → READY_TO_RESUME` **only when ALL blocking LabOrderItems referenced by the encounter hold are `RELEASED` or `CANCELLED` — across every referenced order**; completion of a subset of orders never triggers readiness; if the clinician is off shift, the patient also appears on the department-level ready list. Result release never completes a patient-facing LAB QueueEntry; that entry completed at the collection/receipt interaction (LAB-008).
**AC** GIVEN an encounter awaiting three tests WHEN the first is released THEN the encounter remains `AWAITING_RESULTS` and the clinician's row shows "1 of 3 results ready" (partial visibility is permitted and results are readable immediately). GIVEN the last blocking item is released THEN within 30 seconds the encounter is `RESULTS_READY` and the patient appears in "Ready to review". GIVEN a hold referencing two orders (CBC released, blood culture pending) WHEN the CBC order alone is fully terminal THEN the encounter remains `AWAITING_RESULTS` — completion of a subset of orders never triggers readiness. GIVEN the last blocking item is instead `CANCELLED` THEN the encounter becomes `RESULTS_READY` with an indicator explaining why ("2 released, 1 cancelled"). GIVEN `SAMPLE_REJECTED` THEN the encounter remains `AWAITING_RESULTS` until recollection reaches `RELEASED` or the item is explicitly `CANCELLED`. GIVEN the clinician resumes manually before all blocking results are terminal THEN the same encounter opens with its ID unchanged and the outstanding laboratory work continues normally (ENC-002/QUE-006). GIVEN a signed encounter THEN no state change occurs and LAB-023 applies instead.
**Data** `Encounter.state`, `QueueEntry.state`. **Audit** State transitions with the triggering event.
**Err** Clinician deactivated → department-level fallback; multiple orders across two clinicians → each clinician is signalled for their own orders.
**Dep** ENC-016, QUE-006. **Test** Partial vs full readiness (the subset-of-orders case must NOT trigger readiness); cancellation- and rejection-driven readiness including recollection-pending; early manual resume with the same encounter ID.

**LAB-019 · Clinician views results inside the encounter · P0 · `CLINICIAN`,`MIDWIFE`**
**AC** GIVEN a resumed encounter with released results THEN the results appear inline in the Investigations section showing test, analyte, value, unit, reference range, flag, released time and verifier, without leaving the encounter. GIVEN an unreleased result THEN the clinician sees only the status (e.g. "sample collected 14:20"), never the unverified value. GIVEN previous results for the same test from earlier visits THEN a compact trend (last 3 values with dates) is shown for numeric analytes — values only, **no interpretation**. GIVEN the clinician views results THEN an access-audit event is written.
**Perm** `lab.result.read`. **Dep** LAB-015, ENC-002. **Test** Unreleased-value invisibility.

**LAB-020 · Print the laboratory report · P0 · `LAB_TECH`,`RECEPTIONIST`,`CLINICIAN`**
**AC** GIVEN released items WHEN printed THEN the report shows the facility header, patient identifiers, order date, specimen type and collection time, each test with values/units/ranges/flags, comments, the ordering clinician, the entering technician, the verifier and release timestamp, an amended marker if applicable, a self-verified marker if applicable, and a "results relate only to the specimen tested" footer. GIVEN unreleased items on the same order THEN they are listed as "pending" rather than omitted. GIVEN a reprint THEN it is audited. GIVEN a patient collecting results in person THEN the receptionist can print without seeing the clinician's notes (payload authorisation).
**Perm** `lab.result.print`. **Dep** TEN-003, RCP-003, RCP-004. **OOS** Emailing/WhatsApping results.
**Test** Role-scoped print payload; A5/A4 snapshots.

**LAB-021 · Ageing and stuck-order monitoring · P0 · `LAB_TECH`,`SUPERVISOR`,`CLINICIAN`**
**Story** As a supervisor I want to see orders that are stuck so no patient is forgotten in the lab loop. **Value** The explicit anti-dead-end guarantee.
**AC** GIVEN an item in `AWAITING_PAYMENT` for more than 60 minutes THEN it appears on the reception/cashier "unpaid lab" list naming the patient and amount. GIVEN an item in `READY_FOR_COLLECTION` beyond its turnaround target THEN it is flagged in the lab queue and on the supervisor dashboard. GIVEN an item in `RESULT_ENTERED` for more than 60 minutes THEN it appears as "awaiting verification" on the supervisor dashboard. GIVEN any item non-terminal for more than 24 hours THEN it appears on a daily "stuck orders" report with the patient, ordering clinician, state and age. GIVEN a facility with zero stuck orders THEN the dashboard shows an explicit zero.
**Perm** `lab.queue.read`/`supervisor.dashboard`. **Dep** QUE-011, REP-009. **Test** Clock-controlled ageing at each state.

**LAB-022 · Cancel an order or item · P0 · `CLINICIAN` (orderer), `SUPERVISOR`; secondary `LAB_TECH`**
**AC** GIVEN an item not yet collected WHEN the ordering clinician cancels it with a reason THEN the item is `CANCELLED`, its unpaid invoice line is voided, and the lab worklist removes it. GIVEN an item already collected WHEN cancellation is requested THEN it requires `SUPERVISOR` approval with a reason and the charge remains payable unless explicitly credited (BIL-010). GIVEN a paid item that is cancelled THEN a credit note is created and the refund is handled through PAY-008; the money is never silently retained or silently refunded. GIVEN a `SAMPLE_REJECTED` item that will not be recollected THEN clinician or authorised supervisor cancellation is required to reach `CANCELLED`. GIVEN cancellation of the last pending item THEN the encounter's awaiting-results dependency resolves (LAB-018).
**Perm** `lab.order.cancel`. **Audit** Reason mandatory. **Test** Financial consequence matrix (unpaid/paid × collected/not collected).

**LAB-023 · Late results after the encounter is signed · P0 · `SYSTEM`; secondary `CLINICIAN`**
**Story** As a clinician who signed and sent the patient home, I want late results brought to my attention and attached to the record.
**AC** GIVEN a signed encounter with a pending order WHEN the result is released THEN an addendum of type `LATE_RESULT` is attached to the encounter containing a reference to the result (not a rewrite of the note), the signing clinician receives a persistent "unreviewed result" item in their worklist, and the item remains until they acknowledge it. GIVEN the visit is already closed `PENDING_RESULTS` THEN it is flagged `POST_CLOSURE_ACTIVITY`; it is never silently reopened. GIVEN acknowledgement THEN the clinician may add a clinical addendum (ENC-023) and/or create a follow-up appointment (APT-001), and the acknowledgement is audited with a timestamp. GIVEN an abnormal-flagged late result THEN it is sorted to the top of the unreviewed list (a display order only — **no clinical interpretation**). GIVEN no acknowledgement within 48 hours THEN it appears on the supervisor dashboard.
**Data** `EncounterAddendum`, `ResultAcknowledgement`. **Audit** Acknowledgement. **Dep** ENC-018, ENC-023. **Test** Persistence until acknowledged; supervisor escalation.

**LAB-024 · Walk-in / external-request lab order · P1 · `LAB_TECH`,`RECEPTIONIST`**
**Story** As a lab technician I want to register a test for a patient who arrives with a request from elsewhere, so we can serve and charge them without a consultation.
**Flow** Create a `LabOrder` with `external_requester_name`, `external_facility` (free text) and no encounter; visit type `LAB_ONLY` (REC-004) → normal payment/collection/result/release loop → release makes the report printable; there is no clinician-resume step.
**AC** GIVEN an external order THEN it requires no encounter and the report prints "Requested by: [external requester]". GIVEN release THEN the patient/reception is notified via the reception "results ready for collection" list. GIVEN a walk-in order THEN charges follow the same gate policy.
**Perm** `lab.order.create.external`. **Dep** LAB-002, REC-004. **OOS** Sending results back to the external facility electronically.
**Test** Encounter-free path integrity.

**LAB-025 · Refer a test to an external laboratory · P2 · `LAB_TECH`**
**AC** GIVEN a test the facility cannot perform THEN the item can be marked `REFERRED_OUT` with the destination lab name, dispatch time and a reference; the item remains non-terminal and appears on the ageing report. When a paper result returns, it is entered as an external/text result with an attached scanned-document reference, follows the appropriate result-entry and verification/release records, and only then becomes `RELEASED`, marked "performed externally at [name]".
**Perm** `lab.refer_out`. **OOS** Electronic integration with external labs. **Test** Ageing inclusion.

---

## 13. EPIC DX — Diagnosis and Treatment

**DX-001 · Record working diagnosis · P0 · `CLINICIAN`,`MIDWIFE`**
**AC** GIVEN an open encounter THEN the clinician can record one or more working (provisional) diagnoses, each coded (CAT-004) or free text, with an optional certainty note. GIVEN a working diagnosis THEN it is clearly labelled "working" in the UI and on any draft print, and it is **not** counted in the diagnosis statistics report (REP-014). GIVEN investigations are ordered THEN a working diagnosis is encouraged but not mandatory.
**Data** `Diagnosis(type=WORKING)`. **Dep** CAT-004. **Test** Report exclusion.

**DX-002 · Record final diagnosis · P0 · `CLINICIAN`,`MIDWIFE`**
**AC** GIVEN an encounter being signed THEN at least one final diagnosis is required, or an explicit `NO_DIAGNOSIS` entry with a mandatory reason (e.g. "referred before diagnosis", "patient declined assessment"). GIVEN multiple final diagnoses THEN exactly one must be marked **primary** and the others secondary. GIVEN a final diagnosis THEN it is counted in REP-014 and appears in the patient's chart history and on the printed note. GIVEN a coded diagnosis THEN its code and label are snapshotted onto the record so later catalogue edits do not rewrite history.
**Data** `Diagnosis(type=FINAL, is_primary)`. **Dep** ENC-017. **Test** Primary-uniqueness constraint; sign-blocking.

**DX-003 · Diagnosis certainty and free-text fallback · P1 · `CLINICIAN`**
**AC** GIVEN no suitable coded term exists THEN the clinician may enter free text, which saves with `coded=false` and appears in reports grouped as "Uncoded". GIVEN a free-text entry that closely matches a coded term THEN the UI suggests the coded term but never substitutes it automatically. GIVEN more than 20% of a month's diagnoses being uncoded THEN this is surfaced on the admin dashboard as a data-quality note.
**Test** No silent substitution.

**DX-004 · Treatment plan and clinical instructions · P0 · `CLINICIAN`,`MIDWIFE`**
**AC** GIVEN an encounter THEN the clinician can record a treatment plan as free text (up to 4000 chars) plus structured items: prescriptions (RX), procedures (DX-005), investigations (LAB), referral (DX-007) and follow-up (DX-008). GIVEN patient advice text THEN it is printed on the patient's copy in a clearly separated section. GIVEN signing THEN the plan becomes immutable with the note.
**Data** `Encounter.plan`, `Encounter.patient_advice`. **Test** Print separation of clinician-facing vs patient-facing content.

**DX-005 · Order a procedure / nursing treatment · P1 · `CLINICIAN`; secondary `NURSE`**
**AC** GIVEN a procedure ordered from the catalogue (CAT-005) THEN a charge is created (per gate policy), a task appears in the treatment-room/nursing worklist with the patient, procedure, instructions and priority, and the encounter shows the procedure as pending. GIVEN a `PAY_BEFORE` procedure requires a charge line and that line cannot be created THEN the initiating operation fails with an explicit billing/setup error and no performable procedure task exists. GIVEN the nurse marks a procedure performed using a consumable/injectable that is **not** managed as KlinKlik inventory THEN performer, time, optional free-text batch/lot, and notes are clinical documentation only, not a stock movement. GIVEN the consumable/injectable is configured as a KlinKlik-stocked Product THEN structured stock issue is mandatory: select product, non-expired batch, quantity and location; INV-005 applies and the API refuses an expired batch with no override. GIVEN the procedure is gated by payment and unpaid THEN the nurse cannot mark it performed and sees the outstanding amount. GIVEN a procedure ordered but not performed by visit closure THEN it appears on the unresolved-tasks report.
**Data** `ProcedureOrder`; structured stock-issue reference only when a KlinKlik-stocked product is selected. **Dep** CAT-005, QUE-005, INV-005. **OOS** Automatic unprompted consumable deduction; expiry enforcement for externally sourced/non-inventory free-text documentation.
**Test** Gate enforcement; unresolved reporting.

**DX-006 · Record disposition · P0 · `CLINICIAN`,`MIDWIFE`**
**AC** GIVEN signing THEN a disposition is mandatory, chosen from `TREATED_AND_DISCHARGED`, `REVIEW_SCHEDULED`, `REFERRED_OUT`, `ADMITTED_ELSEWHERE`, `LEFT_AGAINST_ADVICE`, `DECEASED`, `OTHER` (+ note). GIVEN `REFERRED_OUT` THEN a referral record is required (DX-007). GIVEN `REVIEW_SCHEDULED` THEN a follow-up date is required (DX-008) and an appointment is offered. GIVEN `DECEASED` THEN the patient deceased flag workflow is offered (PAT-013). GIVEN disposition THEN it is included in the visit summary and REP-002.
**Data** `Encounter.disposition`. **Test** Conditional-requirement matrix.

**DX-007 · Create a referral letter · P1 · `CLINICIAN`,`MIDWIFE`**
**AC** GIVEN a referral THEN the clinician records the destination facility/specialist (free text), reason for referral, clinical summary (prefilled from the encounter and editable), investigations already done with results, treatment given, and urgency. GIVEN the referral is saved THEN a printable letter is produced with the facility header, patient identifiers, the clinician's name/cadre/licence and signature line, and it is retained on the patient's record. GIVEN a signed encounter THEN the referral content is immutable with it. GIVEN a reprint THEN it is audited.
**Data** `Referral`. **Dep** TEN-003, RCP-003. **OOS** Electronic referral transmission, referral tracking/feedback loops.
**Test** Prefill accuracy; print snapshot.

**DX-008 · Record follow-up instruction · P0 · `CLINICIAN`,`MIDWIFE`**
**AC** GIVEN a follow-up interval or date THEN it is stored on the encounter, printed on the patient's copy, and offered as a one-click appointment creation (APT-001). GIVEN an appointment is created from it THEN the encounter references the appointment. GIVEN no appointment is created THEN the follow-up instruction still prints ("return in 3 days or earlier if worse").
**Dep** APT-001. **Test** Link integrity.

**DX-009 · Sick leave / medical certificate · P2 · `CLINICIAN`**
**AC** GIVEN a certificate request THEN the clinician records the number of days, the period, and a generic reason (fit/unfit for duty), producing a printable certificate with the facility header, patient identity, clinician name/cadre/licence, date and a certificate serial number. GIVEN issuance THEN it is recorded on the patient record and audited, and reprints are marked as duplicates.
**Data** `MedicalCertificate`. **OOS** Diagnosis disclosure rules per employer. **Test** Serial uniqueness; duplicate marking.

**DX-010 · HMIS-aligned diagnosis grouping for reporting · P2 · `FACILITY_ADMIN`**
**AC** GIVEN the diagnosis catalogue THEN each entry may be mapped to an HMIS OPD diagnosis category (aligned to the Uganda outpatient register, HMIS Form 031) so that REP-016 can produce a register-shaped tally. GIVEN unmapped diagnoses THEN they are grouped under "Other" and listed separately so the mapping gap is visible. GIVEN the export THEN it is explicitly labelled as an aid for manual register completion and **not** as a certified HMIS/DHIS2 submission.
**Dep** CAT-004, REP-016. **OOS** DHIS2 integration. **Test** Mapping coverage report.

---

## 14. EPIC RX — Prescriptions

**RX-001 · Create a prescription within the encounter · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want to prescribe medicines within the consultation so the pharmacy receives exactly what I intended.
**Pre** Encounter `OPEN`; `prescription.create`. **Flow** Open the prescription tray → add items (RX-002) → the prescription exists as `DRAFT` bound to the encounter → activated on signing (RX-005).
**AC** GIVEN an open encounter THEN a single `DRAFT` prescription per encounter holds all items (no duplicate drafts). GIVEN a draft prescription THEN it is **not** visible to the pharmacy. GIVEN the encounter is voided THEN the draft is cancelled.
**Data** `Prescription(state=DRAFT)`. **Dep** ENC-001. **Test** Pharmacy invisibility of drafts.

**RX-002 · Add a prescription item · P0 · `CLINICIAN`,`MIDWIFE`**
**AC** GIVEN the item form THEN the clinician selects a product from the pharmacy catalogue (PHM-001) **or** enters a free-text medicine name (for items the facility does not stock), and records: dose (amount + unit), route (`PO`,`IM`,`IV`,`PR`,`PV`,`TOP`,`INH`,`SL`,`OPTH`,`OTIC`, other), frequency (`OD`,`BD`,`TDS`,`QDS`,`NOCTE`,`PRN`,`STAT`, custom), duration (value + unit), quantity to dispense, and instructions to the patient (free text). GIVEN product, dose, frequency and duration THEN the system **arithmetically** proposes a quantity (dose units × frequency per day × days), which the clinician may override; the proposal is labelled as arithmetic only and performs **no dose checking** (AS-11). GIVEN a free-text medicine THEN the item is flagged `external=true`, cannot be dispensed internally, and prints on an external prescription (RX-007) — an external item never leaves the prescription permanently `ACTIVE` and never blocks Visit closure (an all-external prescription terminalises `NOT_DISPENSED` at signing, reason `EXTERNAL_SUPPLY`; in a mixed prescription it carries no internal obligation — RX-005). GIVEN a catalogue product flagged as controlled/Class A THEN it is **not selectable** and the UI states that controlled medicines are not supported in this system (RX-008). GIVEN the patient's recorded allergies THEN they are displayed prominently beside the prescribing form; **no automatic matching or blocking occurs** and the UI must not imply it does (OD-19).
**Data** `PrescriptionItem`. **Err** Quantity zero/negative rejected; duration beyond a configurable maximum (default 90 days) warns.
**Test** Quantity arithmetic; controlled-product block; external-item behaviour.

**RX-003 · See allergies and current medications while prescribing · P0 · `CLINICIAN`**
**AC** GIVEN the prescribing tray is open THEN the patient's allergies (or NKA / not recorded) and current medications are visible without navigation. GIVEN allergy status is "not recorded" THEN a warning chip is shown and signing is blocked until recorded (ENC-011). GIVEN the platform THEN it performs no interaction or contraindication checking and displays no statement suggesting that it does.
**Dep** TRI-004, ENC-010. **Test** UI copy review for any implied CDS.

**RX-004 · Review and edit the prescription before signing · P0 · `CLINICIAN`**
**AC** GIVEN a draft prescription THEN items can be edited or removed freely, and a summary shows each item's full sig line ("Amoxicillin 500 mg capsule — 1 cap PO TDS × 5 days = 15 capsules"). GIVEN a duplicate product already on the same prescription THEN a warning is shown requiring confirmation. GIVEN the prescription is empty at signing THEN the encounter signs normally with no prescription created.
**Test** Sig-line rendering rules.

**RX-005 · Activate the prescription on signing · P0 · `SYSTEM`**
**AC** GIVEN an encounter with a draft prescription containing **at least one internally dispensable item** and an enabled Pharmacy module WHEN the encounter is signed THEN the prescription becomes `ACTIVE`, records the prescriber identity snapshot (name, cadre, licence), and appears in the pharmacy dispensing queue within 15 seconds. GIVEN activation THEN the prescription content becomes immutable; changes require cancellation and a new prescription (RX-009) or a signed addendum. GIVEN activation THEN charges are **not** created yet (charging happens at dispensing, DSP-007, because quantities may change with availability). GIVEN a prescription with **zero internally dispensable items** (all items `external=true` / not internally dispensable) WHEN the encounter is signed THEN the prescription terminalises directly `DRAFT → NOT_DISPENSED` with the structured reason `EXTERNAL_SUPPLY` — the external prescription remains printable (RX-007), no Pharmacy QueueEntry is created, no Dispense is created, no pharmacy stock movement occurs, no internal medicine charge is created for those external-only items, the prescription remains visible in the patient record as an external prescription with its prescriber snapshot retained, the audit references the terminalisation reason, and Visit closure (REC-012) never treats it as unresolved. GIVEN the **Pharmacy module is disabled** and the prescription can only be fulfilled externally WHEN the encounter is signed THEN the same external-supply path applies with reason `PHARMACY_DISABLED`. GIVEN a **mixed** prescription (internally dispensable + external-only items) WHEN the encounter is signed THEN the prescription becomes `ACTIVE` (internal pharmacy work exists): internal items enter the pharmacy workflow, external items remain part of the record marked external/non-internal with no internal DispenseLine, stock movement or internal charge, and the prescription terminalises later based only on the internal dispensing result — no duplicate prescription is created.
**Data** `Prescription.state`, prescriber snapshot. **Audit** Activation (or external/pharmacy-disabled terminalisation with its reason) referencing the Prescription ID/version and item version hashes with the prescriber snapshot; prescribed-medicine details remain in the protected prescription record. **Dep** ENC-017, DSP-001. **Test** Fan-out timing; immutability; mandatory tests — (1) CLINIC facility with Pharmacy disabled: sign external prescription → `NOT_DISPENSED`(`PHARMACY_DISABLED`), printable, no pharmacy queue/dispense/stock movement, visit closable under REC-012; (2) external-only item with Pharmacy enabled → `NOT_DISPENSED`(`EXTERNAL_SUPPLY`), same guarantees; (3) mixed internal+external → `ACTIVE`, pharmacy queue entry created, internal item dispensed through normal states, external item carries no internal obligation.

**RX-006 · View prescription history · P1 · `CLINICIAN`,`PHARMACIST`**
**AC** GIVEN a patient chart THEN prescriptions from previous visits are listed with date, prescriber, items, and dispensing status (fully/partially/not dispensed). GIVEN an item dispensed THEN the dispensed quantity, batch and date are shown to authorised roles. GIVEN a pharmacist THEN they see prescriptions and allergies but not the full clinical note.
**Dep** PAT-009, DSP-012. **Test** Role-scoped payload.

**RX-007 · Print a prescription · P0 · `CLINICIAN`,`PHARMACIST`,`RECEPTIONIST`**
**AC** GIVEN an active prescription WHEN printed THEN the document contains the facility header, patient name/number/age/sex (and weight for under-5s), date, each item with full sig, quantity, prescriber name/cadre/licence number, signature line, and a prescription serial number. GIVEN items flagged `external=true` THEN they print on the prescription clearly marked "not dispensed here"; external-only and pharmacy-disabled prescriptions terminalised `NOT_DISPENSED` (RX-005) remain printable as external prescriptions and stay visible in the patient record with the prescriber snapshot retained. GIVEN a reprint THEN it is marked as a duplicate copy and audited. GIVEN a draft prescription THEN printing is blocked.
**Dep** TEN-003, USR-003, RCP-003, RCP-007. **Test** Under-5 weight presence; duplicate marking.

**RX-008 · Controlled / Class A medicines are out of scope · P0 · `SYSTEM`**
**Story** As the platform I must refuse to handle controlled medicines because V1 cannot satisfy the statutory register and custody requirements.
**AC** GIVEN a catalogue product flagged `controlled=true` THEN it cannot be added to a prescription, cannot be received into stock, cannot be dispensed, and cannot be sold, in every code path, with the message "Controlled medicines are not supported in KlinKlik V1 — use your paper controlled-drugs register". GIVEN an attempt via the API THEN 403 `CONTROLLED_NOT_SUPPORTED`. GIVEN an import of catalogue data containing controlled items THEN they are imported as inactive and flagged, never silently enabled. GIVEN the flag THEN only `ORG_OWNER` may set or clear it, and every change is audited.
**Data** `Product.controlled`. **Audit** Flag changes; blocked attempts (to detect demand). **Dep** PHM-001, DSP-003. **OOS** Any controlled-drug workflow.
**Test** All four code paths refuse.

**RX-009 · Cancel or discontinue a prescription · P1 · `CLINICIAN` (prescriber), `SUPERVISOR`**
**AC** GIVEN an `ACTIVE` prescription with no dispensing THEN the prescriber may cancel it with a reason; it becomes `CANCELLED` and disappears from the pharmacy queue with a visible notice to pharmacy. GIVEN partial dispensing has occurred THEN only the undispensed items may be cancelled; dispensed items and their stock movements are untouched. GIVEN cancellation after the pharmacist has started preparing THEN the pharmacist sees an immediate alert on their open dispense screen.
**Audit** Reason mandatory. **Test** Race between cancel and dispense (dispense wins if already committed; cancel then fails with 409).

**RX-010 · Repeat / refill an earlier prescription · P2 · `CLINICIAN`**
**AC** GIVEN a previous prescription THEN the clinician may copy it into the current encounter as a **draft**, with all items editable and the source prescription referenced. GIVEN a copy THEN it never activates without the current encounter being signed, and the new prescriber is the current clinician.
**Test** Provenance recording.

**RX-011 · Nurse/midwife limited prescribing scope · P2 · `FACILITY_ADMIN`**
**AC** GIVEN a facility configuration listing products a `MIDWIFE` may prescribe (e.g. iron/folic acid, paracetamol, ORS) THEN holders of `prescription.create.limited` may prescribe only those products, and attempts to prescribe outside the list are refused with `OUTSIDE_PRESCRIBING_SCOPE`. GIVEN such a prescription THEN it prints with that provider's cadre and licence and is flagged as limited-scope in the audit. **`NURSE` limited prescribing is not active in the supplied V1**: the 194-story backlog defines no nurse prescription activation/sign-off workflow (a nurse cannot sign the encounter, and no countersigning exists); enabling it later requires an explicit authorisation/sign-off specification before implementation.
**Dep** RX-002, USR-003. **OOS** Any clinical protocol enforcement; nurse limited prescribing in V1.

---

## 15. EPIC PHM — Pharmacy Catalogue

**PHM-001 · Create a product · P0 · `PHARMACIST`,`FACILITY_ADMIN`**
**AC** GIVEN the product form THEN the user records: generic name (required), brand/trade name (optional), dosage form (`TABLET`,`CAPSULE`,`SYRUP`,`SUSPENSION`,`INJECTION`,`CREAM`,`OINTMENT`,`DROPS`,`INHALER`,`SUPPOSITORY`,`SACHET`,`OTHER`), strength (text, e.g. "500 mg", "125 mg/5 mL"), pack description, dispensing unit (`TABLET`,`CAPSULE`,`ML`,`BOTTLE`,`SACHET`,`VIAL`,`TUBE`,`PIECE`), category (`MEDICINE`,`CONSUMABLE`,`SUNDRY`), prescription-only flag, controlled flag (RX-008), active flag. GIVEN a duplicate generic+strength+form in one facility THEN a warning with the existing product is shown; creation requires confirmation. GIVEN a product THEN it is searchable by generic and brand name. GIVEN creation/edit THEN it is audited.
**Data** `Product`. **Err** Strength typed inconsistently ("500mg" vs "500 mg") → normalise on save for search.
**OOS** National drug register import, ATC coding. **Test** Search by both names.

**PHM-002 · Set selling price · P0 · `PHARMACIST`,`FACILITY_ADMIN`**
**AC** GIVEN a product THEN a selling price per dispensing unit is set per facility, with an optional pack price. GIVEN a dispense or sale THEN the price is snapshotted onto the invoice line so later price changes never alter historical invoices. GIVEN a price change THEN it is audited with old/new and actor and appears in the price-history view. GIVEN a product with no price THEN it cannot be dispensed or sold and appears on the setup-warnings list.
**Data** `ProductPrice`. **Dep** CAT-002. **OOS** Automatic margin calculation from cost (P2: display-only margin is allowed if cost is captured in INV-002).
**Test** Snapshot immutability.

**PHM-003 · Link products to prescribing · P0 · `SYSTEM`**
**AC** GIVEN the prescribing search THEN it returns active, non-controlled products with their form and strength, showing current stock availability as an indicator (`In stock`, `Low`, `Out of stock`) **without exposing exact stock counts to clinicians unless they hold `inventory.read`**. GIVEN an out-of-stock product THEN the clinician may still prescribe it (the patient may buy elsewhere) but sees the indicator.
**Dep** RX-002, INV-006. **Test** Indicator accuracy and permission scoping.

**PHM-004 · Deactivate a product · P1 · `PHARMACIST`**
**AC** GIVEN a product with zero stock THEN it may be deactivated, disappearing from prescribing, dispensing and sale searches while remaining in historical records and reports. GIVEN a product with stock on hand THEN deactivation is blocked with the quantity shown, requiring adjustment or disposal first. GIVEN reactivation THEN it is audited.
**Test** Stock-blocking rule.

**PHM-005 · Product search performance · P1 · `PHARMACIST`,`CLINICIAN`**
**AC** GIVEN a catalogue of 3,000 products WHEN a user types three characters THEN results return within 300 ms p95 from the server, ranked by exact-prefix, then generic-name match, then brand match, then frequency of use at that facility.
**Test** Latency and ranking.

**PHM-006 · Consumables and sundries · P1 · `PHARMACIST`**
**AC** GIVEN category `CONSUMABLE`/`SUNDRY` (gloves, syringes, gauze, cotton, plasters) THEN the item participates in stock, sale and adjustment workflows but is excluded from prescribing search by default and from the "medicines" reports, appearing instead in consumables reporting.
**Dep** INV-001. **Test** Search exclusion.

**PHM-007 · Import a starter catalogue · P1 · `FACILITY_ADMIN`**
**AC** GIVEN a CSV in the published template THEN the system validates every row before importing any, reports row-level errors with line numbers, and imports only on a clean file or on explicit "import valid rows only". GIVEN a row flagged as controlled THEN it is imported inactive with the controlled flag set. GIVEN an import THEN it is audited with the file name, row counts and actor.
**Err** Duplicate rows; malformed prices; encoding issues. **OOS** Automatic mapping to any national register.
**Test** All-or-nothing and partial modes.

**PHM-008 · Product dispensing instructions template · P2 · `PHARMACIST`**
**AC** GIVEN a product THEN a default patient instruction (e.g. "Take with food") may be stored and is auto-inserted, **editable**, into the dispense label and the prescription instruction field. GIVEN no template THEN nothing is inserted.
**Dep** DSP-010. **OOS** Any clinical advice library.

---

## 16. EPIC INV — Inventory and Stock

**INV-001 · Stock locations · P1 · `FACILITY_ADMIN`**
**AC** GIVEN a facility THEN at least one stock location exists (default "Main Pharmacy"); additional locations (Store, Dispensary, Lab Store, Treatment Room) may be created. GIVEN multiple locations THEN stock balances are tracked per location and dispensing draws from a configured default location. GIVEN a location with stock THEN it cannot be deleted, only deactivated after transfer.
**Data** `StockLocation`. **Dep** INV-007. **Test** Per-location balance isolation.

**INV-002 · Receive stock (goods received note) · P0 · `STORE_KEEPER`,`PHARMACIST`**
**Story** As a pharmacist I want to record medicines received from a supplier, with batches and expiry dates, so stock and expiry control are accurate.
**Pre** Products exist. **Trig** Delivery arrives.
**Flow** Create a GRN: supplier name (free text or from a simple supplier list), invoice/delivery-note reference, received date, receiving location, and lines of: product, batch/lot number, expiry date (month precision minimum), quantity received in the dispensing unit, unit cost (optional but recommended), and any pack-to-unit conversion. Save → stock ledger entries created → balances increase.
**AC** GIVEN a GRN line with an expiry date in the past WHEN saved THEN it is **rejected** with `EXPIRED_STOCK_CANNOT_BE_RECEIVED`. GIVEN a GRN line with an expiry within 3 months THEN it is accepted with a prominent warning recorded on the GRN. GIVEN a saved GRN THEN each line creates a `StockLedger(IN)` entry referencing the GRN, the batch record is created or incremented, and the balance for that product/batch/location increases by exactly the received quantity. GIVEN the same GRN submitted twice with one idempotency key THEN stock increases once. GIVEN a GRN THEN it is printable and immutable after posting; corrections require a stock adjustment (INV-011) with a reason.
**Perm** `inventory.receive`. **Data** `GoodsReceipt`, `GoodsReceiptLine`, `Batch`, `StockLedger`, `StockBalance`. **Audit** Posting with all lines.
**Err** Duplicate batch numbers from different suppliers → batch identity is `(product, batch_no, expiry)`; missing expiry on a product that requires it → blocked.
**UI** Fast line-entry grid with keyboard navigation; running total.
**OOS** Purchase orders, supplier invoices/payables, barcode scanning.
**Test** Past-expiry rejection; idempotency; ledger arithmetic.

**INV-003 · Batch and expiry tracking · P0 · `SYSTEM`**
**AC** GIVEN any stock movement THEN it is attributed to a specific batch with its expiry date; no movement may exist without a batch for products flagged as batch-tracked (all `MEDICINE` products are batch-tracked by default). GIVEN a batch THEN its remaining quantity per location is always derivable from the ledger and matches the cached balance (a nightly reconciliation job asserts this and raises a discrepancy alert). GIVEN a batch reaching zero THEN it remains visible in history and is excluded from dispensing selection.
**Data** `Batch`, `StockLedger`, `StockBalance`. **Test** Ledger-vs-balance reconciliation.

**INV-004 · FEFO batch selection · P0 · `SYSTEM`; secondary `PHARMACIST`**
**Story** As a pharmacist I want the system to propose the earliest-expiring usable batch so we don't accumulate expiries.
**AC** GIVEN three batches with different expiry dates WHEN a dispense or sale is prepared THEN the system proposes the **non-expired** batch with the earliest expiry that has sufficient quantity, and displays the batch number and expiry. GIVEN insufficient quantity in the earliest batch THEN the system proposes a split across batches in expiry order and shows the split explicitly. GIVEN the pharmacist selects a different (non-expired) batch THEN a reason is required and the deviation is audited and reported (INV-016). GIVEN only expired batches exist THEN the product is treated as out of stock and dispensing is refused (INV-005).
**Data** Batch selection recorded on the dispense line. **Audit** FEFO deviations. **Dep** INV-005, DSP-003. **Test** Split-batch arithmetic; deviation audit.

**INV-005 · Expired stock can never be dispensed or sold · P0 · `SYSTEM`**
**Story** As a facility I need absolute certainty that expired KlinKlik-managed stock cannot be issued, dispensed, sold, or used through this system. **Value** Patient safety and NDA compliance; the highest-severity rule in the product.
**AC**
- GIVEN a batch whose expiry date is before today WHEN it is offered for dispensing, sale, transfer-out to a dispensing location, prescription fulfilment, or structured procedure stock issue/use THEN it is excluded from selection in every interface.
- GIVEN a direct API request specifying an expired batch THEN the request is rejected with 422 `EXPIRED_BATCH` regardless of the caller's role, including `ORG_OWNER` and `SYS_ADMIN`.
- GIVEN **no** configuration setting, permission, capability, reason code, or override parameter exists anywhere in the system that permits dispensing expired stock (verified by a code-level test that no such flag exists and by an API fuzz test asserting refusal).
- GIVEN a batch that expires while reserved in an in-progress dispense THEN the dispense cannot be confirmed and the pharmacist is instructed to reselect a batch.
- GIVEN expired stock on hand THEN the only permitted movements are quarantine (INV-010) and disposal write-off (INV-011). Any positive movement into an already-expired KlinKlik-managed batch is rejected or lands directly in quarantine/non-usable stock; it can never increase usable availability.
- GIVEN a dispense attempt on an expired batch THEN the attempt is audited as a blocked action.
**Perm** No permission grants this. **Data** None created on refusal; audit of the blocked attempt. **Dep** INV-004, DSP-003. **OOS** Any override mechanism — permanently.
**Test** **Security-grade test suite**: role matrix × interface matrix × direct API, all refusing; plus a static check that no `allow_expired` flag exists in the codebase.

**INV-006 · Stock balance view · P0 · `PHARMACIST`,`STORE_KEEPER`,`FACILITY_ADMIN`**
**AC** GIVEN the stock list THEN it shows, per product: total quantity on hand at the facility, quantity by location, number of batches, earliest expiry, and status chips (`OK`, `LOW`, `OUT`, `EXPIRING_SOON`, `EXPIRED`). GIVEN a product is expanded THEN each batch is listed with batch number, expiry, location and quantity. GIVEN expired batches THEN they are shown in a visually distinct, non-selectable style with the quantity counted separately from usable stock (usable stock excludes expired). GIVEN a search THEN it filters by product name, status and location.
**Perm** `inventory.read`. **Test** Usable-vs-total arithmetic.

**INV-007 · Stock transfer between locations · P1 · `STORE_KEEPER`,`PHARMACIST`**
**AC** GIVEN stock at the Store THEN a transfer to the Dispensary creates paired ledger entries (OUT at source, IN at destination) preserving batch and expiry, leaving the facility total unchanged. GIVEN an expired batch THEN it may be transferred **only** to a location flagged as quarantine (INV-010). GIVEN a transfer THEN it is audited with actor, batches and quantities. GIVEN insufficient quantity THEN it is rejected.
**Data** `StockTransfer`, ledger pairs. **Test** Total-conservation invariant.

**INV-008 · Low-stock threshold and alerts · P0 · `PHARMACIST`,`FACILITY_ADMIN`**
**AC** GIVEN a reorder level set per product per facility THEN products at or below it appear on the low-stock list and on the pharmacy dashboard with the current quantity and the level. GIVEN a product with no reorder level THEN it is excluded from alerts and appears on a "thresholds not set" list. GIVEN a dispense that takes stock below the level THEN the product appears on the low-stock list on the next refresh. GIVEN the low-stock list THEN it is exportable to CSV for ordering.
**Data** `Product.reorder_level` (per facility). **Dep** REP-012. **Test** Threshold-crossing detection.

**INV-009 · Expiry warnings · P0 · `PHARMACIST`,`FACILITY_ADMIN`**
**AC** GIVEN batches expiring within a configurable horizon (default 90 days) THEN they appear on the expiring-stock list with product, batch, expiry, quantity, location and days remaining, sorted by soonest. GIVEN batches already expired THEN they appear on a separate expired list with a prompt to quarantine or write off. GIVEN the pharmacy dashboard THEN it shows counts for both. GIVEN a batch crossing the expiry date overnight THEN it moves from expiring to expired without manual action (evaluated on read; a nightly job refreshes cached flags).
**Dep** REP-012. **Test** Date-boundary behaviour at midnight EAT.

**INV-010 · Quarantine expired or damaged stock · P1 · `PHARMACIST`,`STORE_KEEPER`**
**AC** GIVEN expired or damaged stock THEN it can be moved to a quarantine location, which is excluded from all availability calculations and from dispensing entirely. GIVEN quarantined stock THEN it remains on the books until written off (INV-011) so it can be counted and reconciled. GIVEN quarantine THEN the reason and actor are recorded.
**Data** `StockLocation(is_quarantine=true)`. **Test** Availability exclusion.

**INV-011 · Stock adjustment and write-off with reason · P0 · `PHARMACIST`,`STORE_KEEPER`; approval `FACILITY_ADMIN`**
**AC** GIVEN a discrepancy THEN an adjustment can be recorded per product/batch/location with a signed quantity, a mandatory reason (`EXPIRY_DISPOSAL`, `DAMAGE`, `BREAKAGE`, `THEFT_LOSS`, `COUNT_CORRECTION`, `RETURN_TO_SUPPLIER`, `DONATION_OUT`, `OTHER` + note) and an optional reference (disposal certificate number). GIVEN an adjustment above a configurable value threshold THEN it requires `FACILITY_ADMIN` approval before posting, and remains `PENDING_APPROVAL` until then. GIVEN posting THEN a ledger entry is created and the balance changes by exactly that amount; the adjustment record is immutable thereafter. GIVEN a positive adjustment or count correction into an already-expired batch THEN it is rejected or lands in quarantine/non-usable stock and cannot make that batch available. GIVEN a write-off of expired stock THEN the value is reported separately in REP-012 so wastage is visible. GIVEN any adjustment THEN it is audited with the actor, reason and before/after balances.
**Data** `StockAdjustment`, ledger. **Err** Adjustment making a balance negative → rejected.
**Test** Approval threshold; negative-balance prevention.

**INV-012 · Automatic stock deduction on dispense/sale · P0 · `SYSTEM`**
**AC** GIVEN a confirmed dispense or sale THEN a `StockLedger(OUT)` entry is created per batch per line **in the same database transaction** as the dispense record, and the balance decreases accordingly. GIVEN insufficient stock at the moment of confirmation (a race with another dispense) THEN the whole dispense fails atomically with `INSUFFICIENT_STOCK` and the pharmacist is asked to reselect; no partial deduction occurs. GIVEN a reversal (DSP-016) THEN a compensating `IN` entry is created referencing the original, never a deletion. GIVEN any ledger entry THEN it is immutable.
**Test** Concurrency race with two pharmacists dispensing the last pack.

**INV-013 · Stock count (physical inventory) · P1 · `PHARMACIST`,`STORE_KEEPER`**
**AC** GIVEN a count session THEN the system produces a count sheet (printable) listing products/batches at a location with a blank counted-quantity column and **without showing the system quantity** by default (blind count, configurable). GIVEN counted quantities are entered THEN variances are shown per line with value impact. GIVEN the count is posted THEN adjustments are created automatically with reason `COUNT_CORRECTION` referencing the count session, subject to the approval threshold (INV-011). GIVEN an open count session THEN dispensing at that location is allowed but flagged, and movements during the count are listed so the variance can be interpreted. GIVEN posting THEN the session becomes immutable.
**Data** `StockCount`, `StockCountLine`. **Test** Variance arithmetic; movements-during-count reporting.

**INV-014 · Stock ledger / movement history · P0 · `PHARMACIST`,`FACILITY_ADMIN`,`SUPERVISOR`**
**AC** GIVEN a product THEN a chronological ledger shows every movement with date/time, type (`IN_GRN`, `OUT_DISPENSE`, `OUT_SALE`, `TRANSFER_IN/OUT`, `ADJUSTMENT`, `REVERSAL`), quantity, batch, location, running balance, actor and source reference (GRN, dispense, sale, adjustment, count). GIVEN the ledger THEN the running balance recomputed from zero equals the current balance (asserted by test and by a nightly job). GIVEN any user with `inventory.read` THEN they can filter by date range, batch and movement type, and export to CSV (audited).
**Test** Recomputation invariant.

**INV-015 · Suppliers list · P2 · `STORE_KEEPER`**
**AC** GIVEN a simple supplier record (name, contact person, phone, notes) THEN GRNs may reference it, and a supplier view lists all GRNs received from them. GIVEN no supplier record THEN free-text supplier names remain permitted on GRNs.
**OOS** Payables, purchase orders, supplier performance analytics.

**INV-016 · FEFO deviation report · P2 · `SUPERVISOR`,`FACILITY_ADMIN`**
**AC** GIVEN dispenses where a non-earliest batch was chosen THEN a report lists them with product, chosen batch, earliest available batch, reason, pharmacist and date, so the practice can be reviewed.
**Dep** INV-004.

---

## 17. EPIC DSP — Pharmacy Dispensing and Retail

**DSP-001 · Pharmacy dispensing queue · P0 · `PHARMACIST`**
**AC** GIVEN active prescriptions THEN the pharmacy queue lists them with patient name and number, prescriber, time prescribed, item count, payment status of any related charges, and age. GIVEN a prescription is `ACTIVE` and undispensed THEN it appears within 15 seconds of the encounter being signed. GIVEN a prescription is being prepared by another pharmacist THEN it shows as claimed with that person's name and cannot be opened for dispensing concurrently (409). GIVEN partially dispensed prescriptions THEN they appear in a separate "Partially dispensed" section with the outstanding items listed. GIVEN a prescription older than a configurable window (default 7 days) and undispensed THEN it moves to an "Expired/uncollected" section and stops cluttering the active queue while remaining retrievable.
**Perm** `dispense.queue.read`. **Dep** RX-005. **Test** Claim concurrency.

**DSP-002 · Open a prescription and check availability · P0 · `PHARMACIST`**
**AC** GIVEN a prescription is opened THEN each item shows the prescribed product, dose, frequency, duration, prescribed quantity, current usable stock (excluding expired), the FEFO-proposed batch(es), the unit price and the line total. GIVEN an item that is out of stock THEN it is marked `OUT_OF_STOCK` with a proposed action (partially dispense, substitute per DSP-006, or not dispense). GIVEN an item that is an external free-text medicine THEN it is displayed as "not stocked here — patient to obtain externally" and excluded from the dispensable set. GIVEN patient allergies THEN they are displayed prominently on the dispensing screen; **no automatic checking occurs**. GIVEN the prescription is opened THEN the pharmacist claims it and an access-audit event is written.
**Perm** `dispense.perform`. **Test** Availability accuracy against usable stock.

**DSP-003 · Select batches (FEFO enforced) · P0 · `PHARMACIST`**
**AC** GIVEN a dispensable item THEN the FEFO batch is preselected and displayed with batch number and expiry. GIVEN the pharmacist changes the batch THEN only non-expired batches with stock are selectable and a reason is required (INV-004). GIVEN a quantity greater than the selected batch holds THEN the system splits across batches in expiry order and shows each batch and quantity explicitly on the screen and on the label. GIVEN any expired batch THEN it is not selectable anywhere (INV-005).
**Dep** INV-004, INV-005. **Test** Split display and label accuracy.

**DSP-004 · Adjust dispensed quantity · P0 · `PHARMACIST`**
**AC** GIVEN a prescribed quantity of 15 and only 10 in stock THEN the pharmacist may dispense 10, and the item is recorded as partially dispensed with the outstanding 5 retained on the prescription (until dispensed or closed out at visit closure — REC-012/§22.6). GIVEN a dispensed quantity greater than prescribed THEN it is rejected with `EXCEEDS_PRESCRIBED_QUANTITY` (no over-dispensing without a new prescription). GIVEN a reduced quantity THEN the charge is calculated on the dispensed quantity only — if the line was already paid, the value difference is corrected through the BIL-010 credit-note path (DSP-007 paid-revision rules), never by editing the paid line. GIVEN a quantity change THEN the reason is recorded when it is below the prescribed amount.
**Test** Charge-quantity coupling.

**DSP-005 · Record items not dispensed · P0 · `PHARMACIST`**
**AC** GIVEN an item that cannot be dispensed THEN the pharmacist records a reason (`OUT_OF_STOCK`, `PATIENT_DECLINED`, `PATIENT_CANNOT_AFFORD`, `PRESCRIBER_CANCELLED`, `NOT_STOCKED`, `OTHER` + note), and no charge is created for it. GIVEN a not-dispensed item THEN the prescribing clinician sees it in their worklist with the reason within 60 seconds, so they can substitute or advise. GIVEN all items are not dispensed THEN the prescription becomes `NOT_DISPENSED` (terminal) with reasons retained. GIVEN out-of-stock reasons THEN they are aggregated into a "missed sales / stock-out impact" report (REP-011). GIVEN an unpaid provisional Dispense in `AWAITING_PAYMENT` with the pharmacy entry `ON_HOLD(AWAITING_PAYMENT)` WHEN the patient declines, cannot afford or abandons the medicines before payment/handover THEN, atomically: the Dispense moves `AWAITING_PAYMENT → CANCELLED` with a mandatory reason from the same vocabulary above; **no stock movement occurs**; the unpaid medicine invoice lines are voided with a reason referencing the cancelled provisional Dispense (BIL-004); the pharmacy queue entry moves `ON_HOLD → CANCELLED` with the corresponding abandonment reason; any cashier queue entry created solely for those medicine charges is `CANCELLED` when no other payable gated lines remain (it stays active otherwise); and the prescription consequence is `NOT_DISPENSED` with item-level reasons if nothing was ever supplied, or retained `PARTIALLY_DISPENSED` (closing later via REC-012's atomic `PARTIALLY_DISPENSED_CLOSED`) if an earlier completed dispense supplied part of it — after which the visit may proceed toward REC-012 closure once other blockers clear. A `CANCELLED` Dispense is an immutable historical record: never deleted, never revived, never converted to `DISPENSED`; a returning patient gets a **new** provisional Dispense.
**Dep** REP-011. **Test** Clinician notification; report aggregation.

**DSP-006 · Generic/brand substitution · P1 · `PHARMACIST`**
**AC** GIVEN a prescribed product THEN the pharmacist may dispense a different product only when it is flagged as an equivalent (same generic name, same strength, same form) or when explicitly authorised by the prescriber. GIVEN a substitution THEN the substituted product, the reason, and whether the prescriber was consulted (yes/no + who) are recorded, and both the prescribed and dispensed products appear on the label, the receipt and the record. GIVEN a substitution across a different strength or form THEN it is **blocked** and requires a new prescription. GIVEN a substitution THEN the prescriber sees it in their worklist.
**Test** Equivalence rule enforcement (same generic+strength+form only).

**DSP-007 · Generate dispensing charges · P0 · `SYSTEM`**
**AC** GIVEN the pharmacist confirms the proposed dispensing basket THEN a stable provisional `Dispense` and its proposed `DispenseLine` records are created with patient/prescription, selected products, batch allocations, quantities and price snapshots; the invoice lines are created for exactly those quantities and reference the specific dispense-line source record/version. Under `MEDICINE=PAY_BEFORE`, provisional dispense creation and its required invoice lines are atomic: if line creation fails, no payment-gated/provisional dispense becomes actionable and an explicit billing/setup error is returned. GIVEN the same basket submitted twice with one idempotency key THEN one provisional dispense and one set of lines exist. GIVEN a change to the basket before final handover THEN the prior **unpaid** invoice lines are voided, their historical dispense-line source/version remains linked, and replacement lines reference distinct new/current dispense-line source records/versions; both actions are audited. **Paid lines are never edited or voided** (BIL-004): (a) *non-financial batch reselection* — after payment but before handover, changing only the batch allocation while keeping the same product, strength/form, quantity, unit price and total requires no invoice/payment correction; the allocation is versioned and audited, the new batch must pass availability, expiry and FEFO/authorisation rules, and no stock moves until DSP-009; (b) *financial basket revision* — any change to product, quantity, unit price or total charged value uses existing correction mechanisms: a BIL-010 credit note against the original paid line/source for removed or reduced undelivered value, and new invoice lines referencing the new DispenseLine source/version for replacement/additional value (BIL-013 uniqueness continues to hold per source version). If the new total exceeds the covered value, the additional balance is due, the pharmacy entry is/remains `ON_HOLD(AWAITING_PAYMENT)` with a cashier entry `WAITING` and handover blocked until cleared (then the same entry `READY_TO_RESUME`); if equal, no additional payment is required and the entry may be/become `READY_TO_RESUME`; if less, the credit note creates a refundable credit handled by BIL-010/PAY-008 — the original payment is never edited and no unexplained patient credit is created unless existing facility credit policy explicitly permits it. Historical paid/credited lines remain auditable, and no stock OUT occurs before the final DSP-009 confirmation. GIVEN a retail sale (DSP-013) THEN charges are created identically without a prescription reference.
**Dep** BIL-001. **Test** Basket-edit line hygiene.

**DSP-008 · Payment gate for medicines · P0 · `SYSTEM`; secondary `CASHIER`,`PHARMACIST`**
**AC** GIVEN `MEDICINE=PAY_BEFORE` THEN the stable provisional dispense record exists in `AWAITING_PAYMENT` with its stable dispense-line invoice sources, stock is **not** deducted, and the pharmacist cannot confirm handover until the related lines are paid; the screen shows the outstanding amount and the invoice number to give the patient. **Patient movement:** the pharmacy queue entry moves `IN_SERVICE → ON_HOLD` with `hold_reason=AWAITING_PAYMENT` and `hold_ref` = the invoice/provisional dispense, and a `QueueEntry(CASHIER)=WAITING` becomes the patient's active current location — the held pharmacy entry is the return obligation (QUE-006 coexistence rules apply; the same entry is reused, never duplicated). GIVEN a required payment-gate line is absent THEN the provisional dispense cannot become actionable. GIVEN the cashier records payment THEN the same dispense becomes confirmable within 15 seconds, the cashier entry completes, and the **same** pharmacy entry moves `ON_HOLD → READY_TO_RESUME` (no second pharmacy entry is created); at handover the pharmacist resumes it (`READY_TO_RESUME → IN_SERVICE`) and confirms (DSP-009). GIVEN `PAY_AFTER` THEN no payment hold is required: the same stable provisional dispense may be confirmed immediately (`IN_SERVICE → COMPLETED` at handover while the dispense is finalised) and the charge remains outstanding on the visit invoice. GIVEN an override by `billing.gate.override` THEN the dispense proceeds without the hold, the charge remains outstanding, and actor + reason are audited. GIVEN the patient declines or cannot pay after the provisional dispense exists THEN the abandonment path of DSP-005 applies atomically (`AWAITING_PAYMENT → CANCELLED`, lines voided, entries terminal). GIVEN a pharmacist who also holds `CASHIER` THEN they may take payment in the same session; the payment and the dispense are separate audited records.
**Dep** TEN-006, PAY-012. **Test** No-stock-deduction-before-payment assertion.

**DSP-009 · Confirm dispense (handover) · P0 · `PHARMACIST`**
**Story** As a pharmacist I want to confirm that the medicines were physically handed over, which is the moment stock leaves.
**AC** GIVEN a payment-cleared (or non-gated) provisional basket WHEN the pharmacist confirms THEN, in a single transaction, the **existing** stable `Dispense` is finalised: `AWAITING_PAYMENT → DISPENSED` where gated; its lines, batches and quantities are confirmed; stock ledger OUT entries are written; balances decrease; the prescription state updates to `DISPENSED` or `PARTIALLY_DISPENSED`; the pharmacy queue entry completes (`IN_SERVICE → COMPLETED` — the held-then-resumed **same** entry under pay-before, or the direct entry under pay-after); the dispenser identity and timestamp are recorded; and the record becomes immutable. No second dispense is created at handover. GIVEN insufficient stock at confirmation THEN the entire transaction fails with no partial effect and the pharmacist reselects. GIVEN confirmation THEN the label(s) and receipt become printable. GIVEN a duplicate confirmation with the same idempotency key THEN exactly one dispense exists and stock is deducted once. GIVEN confirmation THEN an audit event references the immutable Dispense/DispenseLine/StockMovement records and their content hashes; patient-linked medicine, batch and quantity details remain in the protected domain records.
**Perm** `dispense.perform`. **Data** `Dispense`, `DispenseLine`, `StockLedger`, `Prescription.state`. **Test** Atomicity under injected failure; idempotency.

**DSP-010 · Print dispensing label · P0 · `PHARMACIST`**
**AC** GIVEN a confirmed dispense THEN a label per item is printable containing: facility name, patient name, date, product name and strength, quantity dispensed, the sig in plain language (e.g. "Take ONE tablet THREE times a day for 5 days"), any product instruction (PHM-008), batch number and expiry, and the dispenser's initials. GIVEN a syrup or suspension THEN the label includes the volume and the measuring instruction where provided. GIVEN a reprint THEN it is permitted and audited. GIVEN a label printer is unavailable THEN a compact A5 "medicines given" sheet can be printed instead, listing all items.
**Dep** TEN-003, RCP-003, RCP-004. **Test** Sig rendering from structured fields; snapshot per layout.

**DSP-011 · Record counselling and receiver · P1 · `PHARMACIST`**
**AC** GIVEN handover THEN the pharmacist records who received the medicines (`PATIENT`, `GUARDIAN`, `RELATIVE` + name) and ticks the counselling points covered from a facility-configurable list (dose, timing, food, storage, side-effects to watch, completion of course). GIVEN counselling is not recorded THEN the dispense still completes but the omission is reported in REP-011. GIVEN a guardian receiving on behalf of a patient THEN their name is stored and printed on the receipt.
**Data** `Dispense.received_by_*`, `counselling_points[]`. **OOS** Counselling content library.

**DSP-012 · Dispensing history · P1 · `PHARMACIST`,`CLINICIAN`**
**AC** GIVEN a patient THEN all dispenses are listed with date, items, quantities, batches, dispenser and prescriber, filtered by date range. GIVEN a clinician THEN they see dispensing history in the encounter context (ENC-010 prefill source). GIVEN a batch recall scenario THEN the pharmacist can search dispenses by batch number to identify affected patients.
**Perm** `dispense.read`. **Test** Batch-based lookup.

**DSP-013 · Over-the-counter retail sale · P0 · `PHARMACIST`**
**Story** As a pharmacist I want to sell directly to a walk-in customer without a clinical visit, because that is a large part of daily revenue.
**Flow** New sale → optional customer (existing patient, or name-only, or anonymous) → add products with quantity (FEFO batches) → totals → payment (cash/manual MoMo) → confirm → stock deducted, receipt printed.
**AC** GIVEN an anonymous sale THEN no patient record is required and the sale completes with a receipt. GIVEN a prescription-only product (PHM-001 flag) THEN selling it requires either a linked prescription or a recorded reason with the pharmacist's acknowledgement, and such sales are listed on a separate report (this is a control, not a prohibition — OD-13). GIVEN a controlled product THEN the sale is refused (RX-008). GIVEN a sale THEN it creates an invoice, a payment and a receipt with the same rigour as clinical billing, and deducts stock atomically. GIVEN a sale to an identified patient THEN it appears in their dispensing history.
**Dep** INV-012, PAY-002, RCP-001, BIL-002. **Test** Anonymous-sale completeness; POM control.

**DSP-014 · Dispensing log for inspection · P1 · `PHARMACIST`,`FACILITY_ADMIN`**
**AC** GIVEN a date range THEN a chronological dispensing log can be produced and printed/exported containing: date/time, patient name or "OTC", product, strength, quantity, batch, expiry, prescriber (or "OTC"), dispenser, and prescription reference — the fields a National Drug Authority inspection or an internal audit would expect from a dispensing register. GIVEN the export THEN it is audited (AUD-009). GIVEN controlled medicines THEN they are absent because they are unsupported (RX-008), and the log states this explicitly so no one assumes coverage.
**Dep** REP-011, RCP-003. **Test** Field completeness; export audit.

**DSP-015 · Expired-stock dispensing is impossible (dispense-path assertion) · P0 · `SYSTEM`**
**AC** GIVEN every dispensing and sale entry point, and every structured issue/use of a KlinKlik-managed procedure consumable, THEN expired batches are absent from selection and refused by the API (INV-005). Free-text documentation for externally sourced/non-inventory procedure items is not a stock issue path and carries no claimed expiry enforcement. GIVEN a dispense prepared before midnight and confirmed after a batch expires THEN confirmation is refused and the pharmacist must reselect. GIVEN a test suite THEN it asserts refusal across all KlinKlik-managed stock entry points for all roles.
**Dep** INV-005. **Test** Midnight-boundary case.

**DSP-016 · Reverse or correct a dispense · P1 · `PHARMACIST` with `SUPERVISOR` approval**
**AC** GIVEN a dispense recorded in error (wrong patient, wrong product) and the medicines are physically returned THEN a reversal creates compensating stock IN entries referencing the original dispense, marks the dispense `REVERSED` with a mandatory reason, and either voids the unpaid charge or triggers a credit/refund path (PAY-008) if paid. GIVEN medicines that were **not** returned THEN reversal is refused and the correction must be handled as a write-off (INV-011) so stock records remain truthful. GIVEN a reversal THEN the original record is retained in full and both records are linked and audited. GIVEN a reversal THEN returned stock re-enters the **same batch**; if it is expired, the positive movement lands in quarantine/non-usable stock and can never become usable.
**Perm** `dispense.reverse`. **Test** Returned-vs-not-returned branches; financial consequence.

---

## 18. EPIC BIL — Billing and Invoicing

**BIL-001 · Automatic charge capture from clinical events · P0 · `SYSTEM`**
**Story** As a facility I want every chargeable act to raise a charge automatically so we stop losing revenue to forgetfulness.
**AC** GIVEN a chargeable event (every chargeable OPD consultation at check-in — REC-001; lab order — LAB-004; procedure order — DX-005; dispense/sale — DSP-007) THEN an invoice line is created on the visit's open invoice (or a new one if none exists) using the source event's stable source record/version. GIVEN the clinical event fails THEN no charge is created. GIVEN the event's charge is required to enforce a `PAY_BEFORE` gate THEN the source/business record and required charge line are created atomically; charge failure aborts the initiating operation with an explicit billing/setup error and leaves no actionable gated service state. GIVEN the event is `PAY_AFTER` or ungated and charge creation fails THEN the clinical event may succeed only with guaranteed billing reconciliation, and the missing charge appears on the unbilled-events exception report (REP-007) within 15 minutes. GIVEN any charge THEN it records `source_type`, `source_id`, the price snapshot, the service/product reference, the gate policy at charge time, and the creating actor.
**Data** `Invoice`, `InvoiceLine`. **Audit** Each line with source. **Test** Failure-mode reconciliation; no orphan charges.

**BIL-002 · One open invoice per visit · P0 · `SYSTEM`**
**AC** GIVEN a visit THEN at most one invoice is in a non-terminal state at any time, accumulating consultation, lab, procedure and medicine lines. GIVEN a retail sale with no visit THEN a standalone invoice is created. GIVEN a concurrent charge from two sources THEN both lines land on the same invoice without duplication or deadlock (row-level locking with retry). GIVEN an invoice THEN the displayed total always equals the sum of its non-voided lines (asserted by test and a nightly integrity job).
**Test** Concurrency; arithmetic invariant.

**BIL-003 · Add a manual invoice line · P1 · `CASHIER`,`FACILITY_ADMIN`**
**AC** GIVEN a service in the catalogue THEN a cashier may add it manually to a visit's invoice with a quantity, and the price is taken from the catalogue (not typed). GIVEN a service not in the catalogue THEN a free-text line with a typed amount requires `billing.manual_line` and a mandatory description and reason, and such lines are listed on a monthly review report. GIVEN any manual line THEN it is audited with actor and reason.
**Test** Free-text line reporting.

**BIL-004 · Void an invoice line · P0 · `CASHIER`,`FACILITY_ADMIN`**
**AC** GIVEN an unpaid line THEN it may be voided with a mandatory reason; the line remains visible marked `VOID` with strike-through and is excluded from totals — including the unpaid medicine lines of a pre-handover-cancelled provisional Dispense, voided with a reason referencing that cancellation (DSP-005). GIVEN a paid or partially paid line THEN voiding is refused; a credit note (BIL-010 — the path for paid pre-handover basket reductions, DSP-007) or payment reversal (PAY-008) is required. GIVEN voiding a lab or medicine line THEN the corresponding clinical record's payment gate re-evaluates (e.g. the lab item may return to `AWAITING_PAYMENT` or become gate-free). GIVEN voiding THEN it is audited with before/after totals.
**Test** Gate re-evaluation.

**BIL-005 · Issue / finalise an invoice · P0 · `SYSTEM`,`CASHIER`**
**AC** GIVEN an invoice with at least one line THEN it is `ISSUED` and visible to the cashier with a facility invoice number (TEN-007). GIVEN an issued invoice THEN new lines may still be added while it is unpaid or partially paid (outpatient reality), and every addition updates the total and is audited. GIVEN a fully paid invoice THEN adding a line moves it back to `PARTIALLY_PAID` with the new balance, and the cashier and the patient's balance display update immediately.
**Test** Post-payment line addition.

**BIL-006 · Cashier's awaiting-payment list · P0 · `CASHIER`**
**AC** GIVEN issued invoices with an outstanding balance THEN they appear in the cashier's list with patient name and number, invoice number, total, paid, balance, the services included (grouped by type), the age of the invoice, and where the patient currently is (QUE-010). GIVEN a new charge is created anywhere in the facility THEN it appears in the cashier's list within 15 seconds. GIVEN a gated service blocking a patient (lab awaiting payment, medicines awaiting payment) THEN the row is marked as blocking so the cashier prioritises it. GIVEN a search by patient name, number or invoice number THEN the invoice is found immediately.
**Perm** `invoice.read`. **Test** Freshness and blocking indicators.

**BIL-007 · View invoice detail · P0 · `CASHIER`,`FACILITY_ADMIN`,`SUPERVISOR`; limited `RECEPTIONIST`**
**AC** GIVEN an invoice THEN its detail shows every line with description, quantity, unit price, line total, source (which order/dispense created it), status, plus payments made with method, reference, date and receipt number, and the outstanding balance. GIVEN a receptionist THEN they see totals and balance but not clinical descriptions beyond service names. GIVEN a voided line THEN it is displayed with its reason and the voiding actor.
**Test** Role-scoped payload.

**BIL-008 · Patient balance across visits · P1 · `CASHIER`,`RECEPTIONIST`**
**AC** GIVEN a patient with unpaid invoices from previous visits THEN their total outstanding balance is displayed on the patient header for finance-capable roles and at check-in (REC-001). GIVEN a payment THEN it may be allocated across invoices oldest-first or explicitly chosen (PAY-005). GIVEN a facility policy requiring settlement before new services THEN check-in shows a blocking warning that `FACILITY_ADMIN` can override with a reason (BIL-014).
**Test** Multi-invoice arithmetic.

**BIL-009 · Discounts, waivers and exemptions · P1 · `FACILITY_ADMIN`,`SUPERVISOR`**
**AC** GIVEN authority THEN a discount may be applied to a line or an invoice as a percentage or a fixed amount, with a mandatory reason from a configurable list (`STAFF`, `INDIGENT`, `GOODWILL`, `PROMOTION`, `MANAGEMENT_DECISION`, `OTHER` + note). GIVEN a discount THEN the original amount, the discount and the net are all retained and printed, so nothing is silently rewritten. GIVEN a full waiver THEN the invoice reaches zero balance through a waiver record, **never** by deleting lines. GIVEN a discount above a configurable threshold THEN it requires `FACILITY_ADMIN`. GIVEN any discount THEN it is audited and appears on a discounts report (REP-008).
**Data** `InvoiceDiscount`. **Test** Threshold enforcement; report totals.

**BIL-010 · Credit note · P1 · `FACILITY_ADMIN`**
**AC** GIVEN a paid line for a service that was not delivered (cancelled lab test after payment, reversed dispense) THEN a credit note is created against the invoice with a mandatory reason and reference to the original line, reducing the amount due or creating a refundable credit. GIVEN a credit note THEN the original invoice and payment records are unchanged, the credit note has its own number, and it is printable. GIVEN a refundable credit THEN the refund is executed as a payment reversal or a cash refund record (PAY-008), never by editing the original payment.
**Test** Ledger consistency between invoice, payment and credit note.

**BIL-011 · Invoice line grouping by category on print · P0 · `CASHIER`**
**AC** GIVEN an invoice with mixed lines THEN the printed invoice groups them under Consultation, Laboratory, Procedures and Medicines with subtotals, then the grand total, amount paid and balance. GIVEN medicines THEN each line shows the product, strength, quantity and unit price. GIVEN laboratory THEN each test is named individually.
**Dep** RCP-002. **Test** Grouping snapshot.

**BIL-012 · Print or reprint an invoice · P1 · `CASHIER`**
**AC** GIVEN an invoice THEN it can be printed showing the facility header, invoice number, date, patient identity, grouped lines, totals, payments and balance, plus "This is not a receipt" when unpaid. GIVEN a reprint THEN it is audited.
**Dep** TEN-003, RCP-003. **Test** Unpaid-marking.

**BIL-013 · Prevent duplicate charges · P0 · `SYSTEM`**
**AC** GIVEN a charge source (order item, specific dispense-line record/version, visit consultation) THEN a database unique constraint on `(invoice, source_type, source_id)` prevents a second line for that exact source. GIVEN a retried request THEN the constraint plus idempotency returns the original line without error. GIVEN a basket edit then the voided line remains linked to its original dispense-line source/version and the replacement line references a distinct current source record/version, so the unique constraint permits the auditable replacement without duplicate-charging either source. GIVEN a legitimate repeat of the same service (a second CBC the same day) THEN it has a distinct source ID and is charged separately. GIVEN a duplicate-charge attempt THEN it is logged for monitoring.
**Test** Constraint behaviour under retry and under legitimate repeats.

**BIL-014 · Outstanding balance at visit closure · P0 · `CASHIER`,`FACILITY_ADMIN`**
**AC** GIVEN a visit with an outstanding balance WHEN closure is attempted THEN it is blocked with the amount and the blocking lines listed. GIVEN `FACILITY_ADMIN` authority THEN the visit may be closed with the balance recorded as a debt/credit-sale with a mandatory reason and a follow-up flag, and the amount appears on the debtors report (REP-008). GIVEN a waiver instead THEN BIL-009 applies and the balance becomes zero through a waiver record. GIVEN any of these THEN the audit records which path was used, by whom and why.
**Dep** REC-012. **Test** All three closure paths.

---

## 19. EPIC PAY — Cashier and Payments

**PAY-001 · Payment methods configuration · P0 · `FACILITY_ADMIN`**
**AC** GIVEN the facility THEN the enabled payment methods are `CASH` (always), `MOBILE_MONEY_MANUAL` (with a required transaction-reference field and an optional provider label such as MTN/Airtel), and up to three facility-defined manual methods (e.g. `BANK_DEPOSIT_SLIP`, `POS_CARD_TERMINAL`, `COMPANY_ACCOUNT`) each with a configurable reference-required flag. GIVEN a method THEN it can be deactivated without affecting historical payments. GIVEN no direct integration THEN the UI never claims a payment is verified with a provider — mobile money references are **operator-entered evidence only**.
**Data** `PaymentMethodConfig`. **OOS** MoMo/bank/card APIs, automatic reconciliation. **Test** Reference-required enforcement.

**PAY-002 · Record a payment · P0 · `CASHIER`; secondary `PHARMACIST` (retail)**
**Story** As a cashier I want to record money received against an invoice so the patient can proceed and our books are right.
**Pre** Invoice with a balance; `payment.record`; an open shift if shifts are enabled (PAY-009).
**Flow** Open the invoice → enter the amount received → select the method → enter the reference if required → optionally enter the amount tendered for cash to compute change → confirm → payment recorded, allocated (PAY-005), receipt generated and printed (RCP-001), gates released (PAY-012).
**AC** GIVEN an invoice with a balance of UGX 45,000 and cash of 50,000 tendered THEN the payment records 45,000 received with 5,000 change displayed, and the invoice becomes `PAID`. GIVEN a mobile-money payment without a reference when the method requires one THEN it is rejected with `REFERENCE_REQUIRED`. GIVEN an amount exceeding the balance THEN it is rejected unless the facility allows credit balances (default: not allowed; the cashier must adjust the amount). Payment commit locks the invoice/allocation rows, recomputes the outstanding balance, validates the proposed allocation, then creates the payment/allocation and updates invoice state in one transaction. GIVEN two cashiers each see UGX 45,000 outstanding and both submit UGX 45,000 THEN exactly one commits; the later request re-evaluates and returns 409 `BALANCE_CHANGED` with the current balance. GIVEN a payment THEN it is immutable; corrections require reversal (PAY-008). GIVEN a duplicate submission with the same idempotency key THEN exactly one payment exists and one receipt is issued. GIVEN a payment THEN the audit records amount, method, reference, actor, shift, invoice and allocations. GIVEN a recorded payment THEN any gated service is released within 15 seconds.
**Perm** `payment.record`. **Data** `Payment`, `PaymentAllocation`, `Receipt`. **Test** Idempotency; over-payment rule; gate release timing.

**PAY-003 · Partial payment · P0 · `CASHIER`**
**AC** GIVEN a balance of 60,000 and 20,000 paid THEN the invoice becomes `PARTIALLY_PAID` with a 40,000 balance, a receipt is issued for 20,000 showing the remaining balance, and the patient can return to pay the rest. GIVEN multiple partial payments THEN each has its own receipt and the invoice shows the full payment history. GIVEN partial payment under a `PAY_BEFORE` gate THEN only the specific gated lines that are fully covered by the allocation are released (PAY-005/LAB-005).
**Test** Line-level release from partial payment.

**PAY-004 · Payment against multiple invoices · P2 · `CASHIER`**
**AC** GIVEN a patient with two outstanding invoices THEN one payment may be allocated across them, with the allocation shown explicitly before confirmation and printed on the receipt. GIVEN no explicit allocation THEN the default is oldest-invoice-first.
**Dep** PAY-005.

**PAY-005 · Payment allocation rules · P0 · `SYSTEM`,`CASHIER`**
**AC** GIVEN a payment THEN it is allocated to invoice lines with an explicit, deterministic and displayed rule: **gated unpaid lines that are currently blocking a service first (in the order the services were requested), then remaining lines oldest-first**. GIVEN the cashier wants a different allocation THEN they may allocate manually line by line before confirming. Allocation runs under the transactional invoice/allocation lock: current outstanding balance and line allocations are recomputed before validation and commit. GIVEN allocation THEN each `PaymentAllocation` row records the line and the amount, the sum of allocations equals the payment amount exactly, and no line is over-allocated. If another payment changes the balance first and the requested allocation now exceeds it, the later request returns 409 `BALANCE_CHANGED` with the current outstanding balance and requires cashier re-entry/confirmation. GIVEN an allocation THEN it is displayed on the receipt so the patient knows what they have paid for.
**Test** Sum invariant; blocking-first ordering; manual override; two-cashier final-balance race (one commit, one 409 `BALANCE_CHANGED`).

**PAY-006 · Cash change calculation · P1 · `CASHIER`**
**AC** GIVEN cash tendered THEN change is computed and displayed prominently before confirmation and printed on the receipt; the stored payment amount is the amount **received against the invoice**, never the tendered amount. GIVEN tendered less than the amount being paid THEN it is rejected.
**Test** Stored-amount correctness.

**PAY-007 · Payment lookup and history · P0 · `CASHIER`,`FACILITY_ADMIN`**
**AC** GIVEN a date range, method, cashier or patient filter THEN matching payments are listed with time, patient, invoice, amount, method, reference, cashier, shift and receipt number, and can be exported (audited). GIVEN a receipt number THEN the payment is found directly.
**Perm** `payment.read`. **Test** Filter correctness.

**PAY-008 · Payment reversal / correction · P0 · `SUPERVISOR`,`FACILITY_ADMIN`**
**Story** As a supervisor I want to reverse a payment recorded in error, in a way that leaves the original visible.
**AC** GIVEN a payment THEN it can never be edited or deleted. GIVEN a reversal request with a mandatory reason (`WRONG_AMOUNT`, `WRONG_INVOICE`, `WRONG_PATIENT`, `DUPLICATE_ENTRY`, `SERVICE_NOT_RENDERED_REFUND`, `OTHER` + note) THEN a reversal record is created referencing the original, the allocations are undone, the invoice balance is restored, and any released gates are re-evaluated under the **undelivered-only principle** (PAY-012): only services not yet delivered may be re-gated — services already delivered (sample collected, medicines handed over, consultation performed) keep their clinical/stock records intact and are merely flagged, with the restored balance outstanding. GIVEN a reversal THEN both the original receipt and the reversal are retained, a reversal note is printable, and the original receipt is marked reversed on reprint. GIVEN a cash refund THEN it is recorded with the refunding cashier and shift so the drawer reconciles. GIVEN a reversal after the shift is closed THEN it is recorded against the current open shift with a reference to the original shift, and both shift reports show it. GIVEN a reversal THEN it is a high-severity audit event and appears on the daily reversals report reviewed by the owner.
**Perm** `payment.reverse` (**not** granted to `CASHIER` by default). **Test** Balance restoration; cross-shift accounting; gate re-evaluation.

**PAY-009 · Cashier shift open/close and reconciliation · P0 · `CASHIER`,`SUPERVISOR`**
**AC** GIVEN a cashier starts work THEN they open a shift recording an opening float; payments they record are attributed to that shift. GIVEN shift close THEN the system shows expected totals by method (cash expected = float + cash received − cash refunds), the cashier enters the counted cash, and any variance is computed, requires a comment if non-zero, and is recorded. GIVEN a closed shift THEN it is immutable and a shift report is printable listing every transaction, totals by method, reversals and the variance. GIVEN an attempt to record a payment without an open shift when shifts are enabled THEN it is refused with `NO_OPEN_SHIFT`. GIVEN a shift left open past a configurable period THEN it appears on the supervisor dashboard, and `SUPERVISOR` may force-close it with a reason. GIVEN a variance beyond a configurable threshold THEN the supervisor is alerted.
**Data** `CashierShift`. **Test** Expected-total arithmetic including reversals; force-close path.

**PAY-010 · Daily cash-up / handover · P1 · `SUPERVISOR`,`FACILITY_ADMIN`**
**AC** GIVEN end of day THEN a facility-level summary aggregates all shifts: total collected by method, number of transactions, refunds/reversals, discounts and waivers granted, outstanding debts created, and the day's revenue by service group. GIVEN the summary THEN it is printable and exportable and reconciles exactly with the sum of shift reports (asserted by test).
**Dep** REP-006, REP-010. **Test** Cross-report reconciliation.

**PAY-011 · Duplicate-payment prevention · P0 · `SYSTEM`**
**AC** GIVEN a payment submitted twice due to a double click or a network retry THEN the idempotency key ensures one payment and one receipt. GIVEN two payments of the identical amount for the same invoice within 60 seconds by the same cashier without an idempotency match THEN a confirmation prompt appears warning of a possible duplicate, which the cashier must explicitly accept (some patients genuinely pay twice for two people). GIVEN two distinct cashiers concurrently attempt the final outstanding balance THEN invoice/allocation locking permits only one commit and the later request returns 409 `BALANCE_CHANGED` rather than creating an overpayment. GIVEN acceptance THEN the second payment is flagged `possible_duplicate` for the daily review report.
**Test** Both automatic and heuristic paths; distinct-cashier race.

**PAY-012 · Payment events release gated services · P0 · `SYSTEM`**
**AC** GIVEN a payment that fully covers a gated lab item's required line THEN the item transitions `AWAITING_PAYMENT → READY_FOR_COLLECTION`, the cashier QueueEntry completes, and a patient-facing `QueueEntry(LAB)=WAITING` is created within 15 seconds; before payment, the unpaid lab worklist item is not a lab QueueEntry. GIVEN a gated service lacks its required charge line THEN it cannot be released/actionable. GIVEN a payment covering medicine lines THEN the same provisional dispense becomes confirmable within 15 seconds and a pharmacy entry held `ON_HOLD(AWAITING_PAYMENT)` becomes `READY_TO_RESUME` — the **same** entry is resumed, never duplicated (DSP-008). GIVEN a payment covering the consultation THEN any clinician-side warning clears (and a `WAITING_PAYMENT` queue entry becomes `WAITING`). GIVEN a reversal THEN gates re-evaluate under the **undelivered-only principle** — a reversal may re-gate only a service that has not yet been delivered; delivered services' clinical/stock records stand and only the financial state is restored. Specifically: **(lab, before collection — including `IN_SERVICE` at the lab service point with no specimen recorded)** opening/starting the lab queue entry does not itself constitute delivery; the decisive boundary is the item reaching `SAMPLE_COLLECTED` and/or a `LabSpecimen` custody record existing. If payment is reversed while no affected item has reached that boundary — including while the lab entry is `WAITING`, `CALLED` or `IN_SERVICE` — then collection is blocked immediately, any unsaved collection form is discarded uncommitted, no `LabSpecimen` is created and no collection event is audited as completed, the item returns `READY_FOR_COLLECTION → AWAITING_PAYMENT`, the active patient-facing lab queue entry is `CANCELLED` with reason `PAYMENT_REVERSED` (the `IN_SERVICE → CANCELLED` variant is narrowly guarded in §22.1), a `QueueEntry(CASHIER)=WAITING` is created and becomes the current operational location, the technician UI shows "Payment reversed — collection is blocked. Send patient to Cashier.", and no active lab queue entry remains (after repayment, cashier completes and a **new** Lab entry `WAITING` is created — the cancelled one is terminal — preserving the no-lab-queue-while-unpaid invariant); **(lab, at/after `SAMPLE_COLLECTED` or an existing specimen record)** the item never moves backward — `SAMPLE_COLLECTED` is never rolled back to `AWAITING_PAYMENT`, processing continues and only the balance is restored; any separate still-uncollected item that becomes unpaid must not be newly collected until its gate clears; **(consultation/triage gate, service not begun)** service begins at `IN_SERVICE`, so while the queue entry is `WAITING` **or `CALLED`** a reversal atomically re-gates it to `WAITING_PAYMENT` — for `CALLED` the soft call lock is released while `called_at`/`called_by`/attempt history are retained, Start is blocked with `PAYMENT_REQUIRED`, and after repayment the entry returns only to `WAITING` (the patient must be called again); entries already `IN_SERVICE`/`COMPLETED` never move backward and only the balance is restored; **(pharmacy, before handover)** the provisional dispense remains/returns `AWAITING_PAYMENT`, the pharmacy entry returns to (or remains) `ON_HOLD(AWAITING_PAYMENT)` — including `READY_TO_RESUME → ON_HOLD`, and if service had resumed `IN_SERVICE` without handover the pharmacist must explicitly acknowledge the reversal before any handover, which stays blocked, and the entry returns `ON_HOLD` with a cashier entry `WAITING` (no stock has moved); **(pharmacy, after `DISPENSED`)** the dispense, stock movements and prescription state are never automatically undone — financial reversal follows PAY-008 and any physical medicine return requires DSP-016. Every re-gate raises a visible notice to the affected department.
**Dep** LAB-005, DSP-008, REC-001. **Test** Event propagation latency and reversal behaviour.

**PAY-013 · Mobile money manual reference capture · P0 · `CASHIER`**
**AC** GIVEN a mobile-money payment THEN the cashier records the provider label, the transaction reference (validated for a minimum length and uniqueness within the facility over a rolling 90 days) and the payer phone number if given. GIVEN a duplicate reference within the window THEN a warning appears requiring confirmation, because duplicates usually indicate a mis-keyed or reused reference. GIVEN the reference THEN it prints on the receipt and appears in the payments-by-method report so manual reconciliation against the MoMo statement is possible. GIVEN the system THEN it never asserts that the transaction was verified with the provider.
**Test** Duplicate-reference warning; receipt content.

**PAY-014 · Payment permissions and segregation of duties · P0 · `SYSTEM`**
**AC** GIVEN a `CASHIER` THEN they may record payments and print receipts but **not** reverse payments, apply discounts above the threshold, or void paid lines. GIVEN a user holding both `payment.record` and `payment.reverse` THEN the combination is permitted (small facilities) but is listed on the segregation-of-duties report (REP-013) for owner awareness. GIVEN any privileged financial action THEN it is audited with actor, reason and amount.
**Dep** AUTH-008, REP-013. **Test** Capability matrix enforcement.

---

## 20. EPIC RCP — Receipts and Printing

**RCP-001 · Generate and print a receipt · P0 · `CASHIER`,`PHARMACIST`**
**AC** GIVEN a recorded payment THEN a receipt is generated immediately with a unique facility receipt number, containing the facility header (name, address, phone, TIN), receipt number, date/time, patient name and number (or "walk-in" for anonymous sales), the items paid for with amounts (allocation from PAY-005), the total paid, the method and reference, the change given for cash, the remaining balance if any, the cashier's name, and the facility footer text. GIVEN the payment THEN the receipt prints automatically to the configured printer and can be reprinted. GIVEN a reprint THEN it is marked "DUPLICATE" and audited with actor and time. GIVEN a reversed payment THEN reprints are marked "REVERSED" with the reversal date.
**Data** `Receipt`. **Test** Numbering uniqueness; duplicate/reversed markings.

**RCP-002 · Print layouts for 80mm thermal and A5/A4 · P0 · `SYSTEM`**
**AC** GIVEN a receipt THEN an 80mm thermal layout is provided that prints legibly with a monochrome logo and no clipped content. GIVEN lab reports, invoices, prescriptions, consultation notes and ANC cards THEN A5 or A4 layouts are provided as appropriate. GIVEN any layout THEN page breaks preserve table headers and no content is lost at boundaries. GIVEN a printer that is unavailable THEN a print-preview view is shown that can be printed later or photographed, and the document is retrievable from the record at any time.
**Test** Snapshot tests per document per size; long-content page-break test.

**RCP-003 · Reprint with audit · P0 · `SYSTEM`**
**AC** GIVEN any printable clinical or financial document THEN reprinting is permitted to authorised roles and every print and reprint writes an audit event with document type, record ID, actor, timestamp and copy number. GIVEN a document's print history THEN it is viewable by `SUPERVISOR`/`FACILITY_ADMIN`. GIVEN clinical documents THEN reprint counts appear in the access-review report (AUD-011).
**Dep** AUD-009. **Test** Copy numbering.

**RCP-004 · Document header/footer service · P0 · `SYSTEM`**
**AC** GIVEN any printable document THEN it renders the facility header from TEN-003 and a standard footer containing the page number, the generating user, the generation timestamp, and (for clinical documents) the phrase identifying the source system and record version. GIVEN a facility profile change THEN newly generated documents use the new values while previously generated PDFs stored on records (if any) remain as generated.
**Test** Header presence across all document types.

**RCP-005 · Printer configuration per workstation · P1 · `FACILITY_ADMIN`**
**AC** GIVEN a workstation THEN a default document-to-printer mapping (receipts → thermal, reports → A4) can be stored as a non-PHI local preference and applied through the browser print flow. GIVEN no configuration THEN the standard browser print dialog is used and nothing breaks.
**OOS** Direct raw printing/driver integration. **Test** No PHI in stored preferences.

**RCP-006 · Patient visit summary printout · P1 · `RECEPTIONIST`,`CLINICIAN`**
**AC** GIVEN a completed visit THEN a one-page patient-facing summary can be printed containing the diagnosis (if the clinician has marked it shareable), the medicines dispensed with instructions, the tests done with results if released, follow-up instructions, the next appointment, and the amount paid. GIVEN clinician-only content (full clerking notes, working differentials) THEN it is excluded from the patient summary.
**Test** Content-exclusion assertions.

**RCP-007 · Document numbering and uniqueness · P0 · `SYSTEM`**
**AC** GIVEN receipts, invoices, credit notes, lab reports, prescriptions, referrals and certificates THEN each has a unique, sequential, non-reusable number per facility per type. GIVEN concurrent generation THEN no duplicates occur. GIVEN a voided document THEN its number is retired, never reissued.
**Dep** TEN-007. **Test** Concurrency and retirement.

---

## 21. EPIC ANC — Antenatal Care

> ANC in V1 is **documentation and scheduling**, aligned to the structure of the Uganda MoH integrated antenatal record (HMIS Form 071) and the WHO/Uganda eight-contact model. It records what the midwife did and what she observed. **It provides no clinical decision support, no risk scoring, no protocol enforcement and no guidance text** unless the facility has explicitly authored that text itself (OD-09).

**ANC-001 · Enrol a patient in ANC · P0 · `MIDWIFE`; secondary `CLINICIAN`**
**AC** GIVEN a pregnant patient THEN the midwife creates an ANC enrolment recording: ANC number (facility sequence, TEN-007), LMP (with a "certain/uncertain" flag) or an ultrasound-based EDD, gravida, para, number of living children, previous pregnancy outcomes summary, blood group if known, and the enrolment date and provider. GIVEN an LMP THEN the EDD is computed as LMP + 280 days and displayed as derived, editable only by entering a clinician-supplied EDD with a reason (e.g. ultrasound dating), in which case both values and the basis are stored. GIVEN an active enrolment THEN a second concurrent enrolment for the same patient is blocked. GIVEN enrolment THEN the patient's chart shows an ANC banner with EDD and current gestational age. GIVEN an obstetric summary that also exists in ENC-013 THEN a single stored record is used by both.
**Data** `ANCEnrolment`. **Test** EDD arithmetic; single-active-enrolment constraint.

**ANC-002 · Start an ANC contact/visit · P0 · `MIDWIFE`**
**AC** GIVEN an enrolled patient checked in with visit type `ANC` THEN the midwife starts an ANC encounter, which is an `Encounter` of type `ANC` with an attached `ANCVisit` record carrying the contact sequence number (1..8+, auto-incremented and editable) and the visit date. GIVEN a start THEN the gestational age in completed weeks and days is computed from the EDD basis and displayed and stored on the visit. GIVEN a patient not yet enrolled THEN the midwife is prompted to enrol first (ANC-001) in the same flow. GIVEN an ANC encounter THEN all encounter lifecycle rules (draft, autosave, park for results, sign, amend) apply identically (Epic ENC) — the midwife holds `encounter.update` and `queue.hold` within ANC scope, so she may park the ANC encounter `AWAITING_RESULTS`, hold its queue entry `ON_HOLD`, and later resume the same encounter (ENC-016/ENC-002/QUE-006) without any clinician involvement.
**Data** `ANCVisit`. **Test** GA computation at boundaries; reuse of encounter lifecycle.

**ANC-003 · Maternal, obstetric and medical history · P0 · `MIDWIFE`**
**AC** GIVEN the first contact THEN the midwife records: previous pregnancy details (year, outcome, mode of delivery, birth weight, complications) as repeatable rows; medical history (hypertension, diabetes, HIV status and ART if disclosed, TB, epilepsy, sickle cell, surgery); allergies (shared with TRI-004); and family/social history. GIVEN subsequent contacts THEN the history is displayed read-only with an "update history" action that versions the change. GIVEN HIV or other sensitive status THEN it is stored as recorded by the provider with no automatic disclosure in printed documents unless the document is explicitly the ANC card and the facility has enabled it (OD-17).
**Test** Version history; sensitive-field print control.

**ANC-004 · ANC vitals and measurements · P0 · `MIDWIFE`,`NURSE`**
**AC** GIVEN a contact THEN the provider records BP, pulse, temperature, weight, height (first contact), MUAC, and Hb if tested at point of care, using the shared vitals component (TRI-002) with the same validation. GIVEN weight across contacts THEN the change since the previous contact is displayed as a computed difference **without interpretation**. GIVEN a BP value THEN it is displayed with an out-of-range marker per the configured reference band and no advice text.
**Dep** TRI-002. **Test** Shared-component consistency.

**ANC-005 · Risk-factor documentation · P0 · `MIDWIFE`**
**AC** GIVEN a facility-configured checklist of risk factors (e.g. age <18 or >35, previous caesarean, previous stillbirth, multiple pregnancy, anaemia, hypertension, diabetes, HIV, previous PPH, grand multiparity) THEN the midwife may tick those present and add free-text notes. GIVEN ticked factors THEN they are displayed prominently on the ANC banner for subsequent contacts and printed on the ANC card. GIVEN the platform THEN it computes **no risk score, no risk category and no recommended action**, and the UI contains no such language. GIVEN a facility that wishes to display its own guidance THEN that text is authored and owned by the facility (OD-09) and is clearly attributed to them.
**Data** `ANCRiskFactor[]`. **Test** UI copy audit for absence of CDS language.

**ANC-006 · Obstetric examination · P0 · `MIDWIFE`**
**AC** GIVEN a contact at an appropriate gestation THEN the midwife records fundal height (cm), presentation (`CEPHALIC`,`BREECH`,`TRANSVERSE`,`UNDETERMINED`), lie, fetal heart rate (bpm, or `NOT_HEARD` with a note), fetal movements (`PRESENT`,`ABSENT`,`NOT_ASSESSED`), oedema (`NONE`,`MILD`,`MODERATE`,`SEVERE`), pallor, and general examination notes. GIVEN fundal height THEN it is stored with the gestational age at that contact so the pair is retrievable; **no automatic comparison or flagging is performed**. GIVEN FHR outside a configured band THEN a neutral out-of-range marker is displayed with no advice.
**Test** Field persistence; absence of derived clinical judgement.

**ANC-007 · ANC investigations · P0 · `MIDWIFE`**
**Story** As a midwife I want to order the ANC contact's investigations from inside the ANC encounter so the standard laboratory loop applies without a separate workflow.
**AC** GIVEN an open ANC encounter (ANC-002) THEN the midwife orders investigations using the standard ordering flow (LAB-002; `lab.order.create` includes `MIDWIFE`) and the standard laboratory loop applies unchanged: charges (LAB-004), gate policy (LAB-005, PAY-012), and the patient-facing laboratory queue movement `WAITING → CALLED → IN_SERVICE → COMPLETED` ending with the specimen-collection/receipt interaction, while LabOrderItem processing continues independently (`SAMPLE_COLLECTED → RESULT_ENTERED → VERIFIED → RELEASED`). GIVEN the encounter is waiting for results THEN the **same** ANC encounter may be parked `AWAITING_RESULTS` with the consultation queue entry `ON_HOLD` (ENC-016/QUE-006 — the midwife holds `queue.hold` within ANC scope) and resumes with the same encounter ID (ENC-002); no second ANC encounter is ever created. GIVEN released results THEN they return to the same ANC encounter (LAB-018/LAB-019): partial results are readable with "n of m results ready" progress; automatic `RESULTS_READY` follows the all-blocking rule (every blocking item `RELEASED` or `CANCELLED`); `SAMPLE_REJECTED` remains non-terminal (recollect or cancel — LAB-009/LAB-022); unreleased values remain invisible to the midwife/clinician. GIVEN the midwife signs with pending results through ENC-018 THEN the signed record remains immutable, the ANC consultation queue entry completes with reason `SIGNED_WITH_PENDING_RESULTS`, and late results follow the LAB-023 addendum path. GIVEN the catalogue THEN ANC-routine tests (e.g. Hb, HIV/syphilis screening, urinalysis, blood group) exist only as **configurable examples**, not mandatory protocol rules. GIVEN the ANC card printout THEN released investigation results appear according to the existing ANC card layout only.
**Perm** `lab.order.create` (MIDWIFE included per LAB-002). **Data** `LabOrder`/`LabOrderItem` linked to the ANC encounter; no ANC-specific laboratory states or statuses.
**Audit** Standard laboratory audit events (LAB-002..LAB-023). **Err** Standard laboratory errors; no ANC-specific exceptions.
**Dep** ANC-002, LAB-002, LAB-004, LAB-005, LAB-015, LAB-018, LAB-023, ENC-016, ENC-018, ENC-002, QUE-006, PAY-012.
**OOS** Automatic ANC protocol enforcement, test-scheduling recommendations, interpretation of laboratory results, diagnosis or treatment suggestion, automatic risk classification, new HMIS fields, certified HMIS/DHIS2 submission — KlinKlik performs none of these (AS-11, OD-09).
**Test** Mandatory Journey-E integrity test: ANC visit → same ANC encounter → midwife orders a lab test → encounter parks → standard laboratory workflow → result `RELEASED` → the **same** ANC encounter receives it → resume or the signed-pending path → no duplicate encounter, no unreleased value exposed, no CDS.

---
## 22. State Machines (authoritative)

Every story referring to these states matches these machines exactly. `TERMINAL?` = no outgoing transitions (except where noted). Audited actor + reason required wherever a guard says "reason".

### 22.1 QueueEntry

States: `WAITING_PAYMENT`, `WAITING`, `CALLED`, `IN_SERVICE`, `ON_HOLD`, `READY_TO_RESUME`, `NO_SHOW`, `COMPLETED`, `TRANSFERRED`, `CANCELLED`, `LWBS`, `EXPIRED`.

| State | Meaning | Allowed from | Allowed to | Who may trigger | Guards | Terminal? |
| --- | --- | --- | --- | --- | --- | --- |
| `WAITING_PAYMENT` | Gated physical service queue entry: not on that service list until paid | — (initial), `WAITING` (payment reversal re-gate, service not begun — PAY-012), `CALLED` (payment reversal before service start — PAY-012) | `WAITING` (payment/waiver/override), `LWBS` (explicit abandonment, REC-009 semantics incl. the unresolved-encounter guard), `CANCELLED` (administrative/error removal, reason required), `EXPIRED` (nightly sweep, reason `DAY_ROLLOVER` — QUE-016) | `SYSTEM` (creation under `PAY_BEFORE_*` policy); `SYSTEM` (re-gate on reversal); `RECEPTIONIST`/`SUPERVISOR` (LWBS/removal); `SYSTEM` (sweep) | Facility gate policy configured; invoice lines drafted. Real state-machine exits — never a fake `WAITING_PAYMENT → WAITING` merely to reach another exit; unpaid abandonment never converts to payment success. Unpaid laboratory work instead uses `LabOrderItem=AWAITING_PAYMENT` in the lab worklist and creates no patient-facing LAB QueueEntry until payment. Sweep visit-handling follows QUE-016 (records-bearing visits flagged, never silently closed) | No |
| `WAITING` | On a department worklist awaiting call | — (initial), `WAITING_PAYMENT`, `CALLED` | `CALLED`, `CANCELLED`, `LWBS`, `EXPIRED`, `WAITING_PAYMENT` (payment reversal re-gate when service has not begun — PAY-012) | `SYSTEM`/`RECEPTIONIST` (create), `CASHIER`+`SYSTEM` (gate release), serving roles (`no-response` return), `SYSTEM` (sweep/reversal re-gate) | No duplicate active entry per visit+department (unique partial index); gate release requires lines paid/waived; no-response return retains original `queued_at` and increments `call_attempts`; reversal re-gate only when the service has not begun (`IN_SERVICE`/`COMPLETED` entries never move backward) | No |
| `CALLED` | Called and soft-locked to a caller | `WAITING` | `IN_SERVICE`, `WAITING` (no-response/lock timeout), `WAITING_PAYMENT` (payment reversal while the service has not started — PAY-012), `NO_SHOW`, `CANCELLED`, `LWBS`, `EXPIRED` | Serving role with `queue.serve`; `SYSTEM` (payment-reversal re-gate only) | One `called_by` only (concurrent call → 409); lock expires after configured timeout. `CALLED → WAITING_PAYMENT` is narrow: gated service + payment reversed + not yet `IN_SERVICE`; the soft call lock is released while `called_at`/`called_by`/attempt history are retained for audit/metrics, Start is blocked with `PAYMENT_REQUIRED`, the service-point UI shows a payment-reversed notice, and after repayment the entry returns only to `WAITING` — the patient must be called again (the old `CALLED` state is never restored automatically) | No |
| `IN_SERVICE` | Being served at this department | `CALLED`, `ON_HOLD`/`READY_TO_RESUME` (resume), `WAITING` (direct Start semantically records `WAITING → CALLED → IN_SERVICE`) | `COMPLETED`, `TRANSFERRED`, `ON_HOLD`, `WAITING` (abandoned, reason required), `CANCELLED` (ONLY: queue_type=LAB + trigger `PAYMENT_REVERSED` + `PAY_BEFORE` + no specimen recorded for the active collection interaction + affected items still pre-`SAMPLE_COLLECTED` — PAY-012; actor `SYSTEM`) | Serving role; `SYSTEM` (the narrow LAB pre-collection payment-reversal cancellation only) | Stage record exists/created; direct Start atomically records `called_at=service_started_at` and `called_by=served_by`; resume returns to the SAME stage record (encounter ID unchanged). The `IN_SERVICE → CANCELLED` payment-gate path is not a generic cancellation ability: collection is blocked immediately, any unsaved collection form is discarded uncommitted, no `LabSpecimen` is created, the technician UI shows "Payment reversed — collection is blocked. Send patient to Cashier.", and after repayment a **new** Lab entry `WAITING` is created (the cancelled one is terminal). Once any affected item is `SAMPLE_COLLECTED` (or a specimen custody record exists) this path never applies — delivered work stands and only the financial balance is restored | No |
| `ON_HOLD` | Patient temporarily left this service point; still belongs to the active visit (Journey B) | `IN_SERVICE`, `READY_TO_RESUME` (payment reversal of an undelivered dependency returns the entry to hold) | `READY_TO_RESUME`, `IN_SERVICE` (manual resume), `COMPLETED` (only the explicit ENC-018 "Sign now" action), `CANCELLED` (unpaid provisional-pharmacy abandonment/cancellation — DSP-005/DSP-008: dispense cancelled pre-handover with mandatory reason) | `CLINICIAN` (`queue.hold`); `MIDWIFE` for ANC-encounter entries (ANC scope only); `PHARMACIST` for pharmacy entries with `hold_reason=AWAITING_PAYMENT` only (DSP-008); `CLINICIAN`/`MIDWIFE` via the encounter-sign service for the ENC-018 completion | Blocking dependency referenced (`hold_reason` + `hold_ref`); never disappears from worklists; counted "in facility". `ON_HOLD → COMPLETED` is narrowly guarded: ENC-018 explicit signing with pending results only, completion reason `SIGNED_WITH_PENDING_RESULTS` — never a generic queue action, and never fired by a lab result releasing. `ON_HOLD → CANCELLED` applies only to pharmacy abandonment of a cancelled provisional dispense | No |
| `READY_TO_RESUME` | Dependency resolved; highlighted for resume | `ON_HOLD` | `IN_SERVICE`, `ON_HOLD` (payment reversal of an undelivered dependency — DSP-008/PAY-012) | `SYSTEM` (auto-flag), clinician (resume) | **ALL** blocking dependencies referenced by the hold terminal — lab items must be `RELEASED` or `CANCELLED`; payment/procedure dependencies must resolve; partial release alone never qualifies. A later reversal of a not-yet-delivered payment dependency may validly return the entry to `ON_HOLD(AWAITING_PAYMENT)` | No |
| `NO_SHOW` | Called repeatedly, not present; semi-terminal | `CALLED` | `WAITING` (re-queue by reception), `LWBS`, `EXPIRED` | Serving role (`queue.mark_no_show`), `RECEPTIONIST` (re-queue) | 2nd+ no-show; emergency-priority no-show raises an immediate reception alert | Semi |
| `COMPLETED` | Stage finished | `IN_SERVICE`, `ON_HOLD` (ENC-018 sign-with-pending only) | — | Serving role (`queue.move`/stage completion); `ON_HOLD → COMPLETED` and the ENC-018 Path-B `IN_SERVICE → COMPLETED`: clinician/midwife via the encounter-sign service | Stage mandatory data satisfied; next entry created in same transaction. The `SIGNED_WITH_PENDING_RESULTS` completions (from `ON_HOLD` or `IN_SERVICE`) require the explicit ENC-018 action; they never occur merely because a lab result released | Yes |
| `TRANSFERRED` | Redirected to another department without completing (wrong queue) | `IN_SERVICE` | — | Serving role | Reason required | Yes |
| `CANCELLED` | Removed (error, duplicate, sent home/elsewhere, routed in error, check-in undo, payment reversal before service, unpaid provisional-pharmacy abandonment) | `WAITING`, `CALLED`, `NO_SHOW`, `WAITING_PAYMENT` (administrative/error removal), `IN_SERVICE` (ONLY the narrow LAB pre-collection payment-reversal rule — PAY-012), `ON_HOLD` (unpaid provisional-pharmacy abandonment — DSP-005/DSP-008) | — | `RECEPTIONIST`,`SUPERVISOR` (`queue.remove`); `SYSTEM` (check-in undo; PAY-012 reversal paths; DSP-005 abandonment workflow invoked by the pharmacist action) | Mandatory reason; `IN_SERVICE` staff-driven removal requires supervisor (the `SYSTEM` LAB payment-reversal path is its own narrowly guarded rule); never hard-deleted | Yes |
| `LWBS` | Left without being seen (explicit REC-009 abandonment; pre-service / pre-substantive-clinical only) | `WAITING`, `CALLED`, `NO_SHOW`, `WAITING_PAYMENT` (unpaid abandonment — REC-009 semantics) | — | `RECEPTIONIST`,`NURSE`,`SUPERVISOR` (explicit REC-009 LWBS workflow) | Mandatory reason; **no encounter for the visit may exist in `OPEN`, `AWAITING_RESULTS`, `RESULTS_READY` or `SIGNED`** — otherwise 409 `ENCOUNTER_UNRESOLVED` with the encounter ID/state and the clinician resolves it via normal sign / ENC-018 sign-with-pending / ENC-019 void, after which closure follows REC-012 (a `VOIDED` encounter alone does not block); atomically closes the Visit as `CLOSED(LWBS)` or `CLOSED(LWBS_PAID)`; feeds LWBS report | Yes |
| `EXPIRED` | Stale from a previous service day (nightly sweep) | `WAITING`, `WAITING_PAYMENT`, `CALLED`, `NO_SHOW` | — | `SYSTEM` (sweep, QUE-016) | Never `IN_SERVICE`; idempotent; visit handling per OD-22; reciprocal with the WAITING_PAYMENT row's `EXPIRED` exit (reason `DAY_ROLLOVER`) | Yes |

**Invariants:** (1) at most one active (non-terminal) queue entry per **(visit, department)** — the unique partial index of QUE-001 (`WAITING_PAYMENT`, `WAITING`, `CALLED`, `IN_SERVICE`, `ON_HOLD`, `READY_TO_RESUME` count as active); (2) a visit MAY hold an `ON_HOLD` entry in one department while simultaneously holding a `WAITING`, `CALLED` or `IN_SERVICE` entry in a downstream department — Journey B's consultation `ON_HOLD(AWAITING_RESULTS)` + lab entry active is a **valid** state; (3) at most one `IN_SERVICE` entry per visit **globally** at any instant — the patient cannot actively be served in two rooms; (4) a patient-facing LAB QueueEntry completes after the collection/receipt interaction, while LabOrderItem bench processing may continue; result release never completes that QueueEntry; (5) `ON_HOLD` is not the patient's physical location — it is an unresolved return obligation, and the current operational location derives from the active downstream entry (QUE-010). An unpaid LabOrderItem worklist entry is not a physical LAB QueueEntry; under pay-before, the cashier entry is the current location until payment creates the lab entry. (6) the held upstream entry remains visible on the owning role's On hold / Awaiting results / Awaiting payment / Awaiting procedure worklist, and a downstream completion may create another downstream entry, resolve the upstream hold, or both, per the workflow. Also: `queued_at` is server time; `wait_seconds` freezes at `IN_SERVICE`; entries are never hard-deleted; every transition writes an audit event with actor (+reason where required). This machine is exactly the one exercised by QUE-003/QUE-005/QUE-006, ENC-002/ENC-016, LAB-008/LAB-018 and the handoff matrix.

### 22.2 Visit

States: `OPEN`, `IN_PROGRESS`, `CLOSED`, `CANCELLED_ERROR`. Closure carries a reason: `COMPLETED | PENDING_RESULTS | ABANDONED | INCOMPLETE | LWBS | LWBS_PAID`. Non-state flags: `STALE_OPEN`, `POST_CLOSURE_ACTIVITY`, `REVIEW_REQUIRED`.

| State | Meaning | Allowed from | Allowed to | Who may trigger | Guards | Terminal? |
| --- | --- | --- | --- | --- | --- | --- |
| `OPEN` | Visit opened at check-in | — | `IN_PROGRESS`, `CLOSED`, `CANCELLED_ERROR` | `RECEPTIONIST`/`SYSTEM` | One open visit per patient per day per facility (409); duplicate-visit rules REC-005 | No |
| `IN_PROGRESS` | First service started | `OPEN` | `CLOSED` | `SYSTEM` (first queue entry `CALLED→IN_SERVICE`) | Implicit transition. Erroneous check-in cancellation is a **pre-service** correction: once `IN_PROGRESS`, REC-010 is refused (409) and the applicable existing closure/error workflows apply — `CANCELLED_ERROR` is reachable from `OPEN` only | No |
| `CLOSED` | Visit finished; reason recorded | `OPEN`, `IN_PROGRESS` | — | `RECEPTIONIST`/`CASHIER` (`visit.close`); debt path `visit.close_with_debt`; force `visit.force_close` | Close checklist (REC-012): no unsigned `OPEN`, `AWAITING_RESULTS`, or `RESULTS_READY` encounter; `PENDING_RESULTS` requires `SIGNED` with `signed_with_pending_orders=true`; prescriptions terminal, invoice settled/waived/debt-recorded; concurrent close → 409 | Yes |
| `CANCELLED_ERROR` | Erroneous check-in undone in grace window | `OPEN` **only** | — | `RECEPTIONIST` (`visit.cancel_error`) | <15 min old; no vitals/encounter/payment; number never recycled; refused once the visit is `IN_PROGRESS` (REC-010) | Yes |

Nightly sweep may auto-close as `CLOSED(ABANDONED)` only zero-record stale visits; every other stale visit is flagged `STALE_OPEN` and closed by a human after morning review (QUE-016, OD-22). Late released results on a closed visit set `POST_CLOSURE_ACTIVITY`; paid-invoice sweep cases set `REVIEW_REQUIRED`.

### 22.3 TriageRecord

States: `DRAFT`, `COMPLETED` (amendments create version rows; the record is never deleted).

| State | Meaning | Allowed from | Allowed to | Who may trigger | Guards | Terminal? |
| --- | --- | --- | --- | --- | --- | --- |
| `DRAFT` | Triage in progress; server-side autosave | — | `COMPLETED` | `NURSE` (`triage.create`) | One record per visit (re-open, never duplicate) | No |
| `COMPLETED` | Saved and forwarded; read-only except amendment | `DRAFT` | — (amend via TRI-008 versions) | `NURSE` (complete+forward) | ≥1 vital (or not-done reason) + complaint + **explicitly selected** acuity (no default, no preselection — otherwise 422 `ACUITY_REQUIRED`); forward creates the next queue entry | Yes |

### 22.4 Encounter

States: `OPEN`, `AWAITING_RESULTS`, `RESULTS_READY`, `SIGNED`, `VOIDED`. Park reasons under `AWAITING_RESULTS`: `AWAITING_RESULTS | AWAITING_PROCEDURE | AWAITING_PAYMENT | PATIENT_STEPPED_OUT`.

| State | Meaning | Allowed from | Allowed to | Who may trigger | Guards | Terminal? |
| --- | --- | --- | --- | --- | --- | --- |
| `OPEN` | Clerking workspace active | — (creation), `AWAITING_RESULTS`, `RESULTS_READY` (resume) | `AWAITING_RESULTS`, `SIGNED`, `VOIDED` | `CLINICIAN`/`MIDWIFE` | Exactly one non-terminal encounter per visit; author or takeover | No |
| `AWAITING_RESULTS` | Parked; patient out of the room; encounter remains open and resumable | `OPEN` | `RESULTS_READY`, `OPEN` (manual resume), `SIGNED` (with pending orders via ENC-018) | `CLINICIAN` (`encounter.update`) | ≥1 non-terminal lab order or explicit park reason | No |
| `RESULTS_READY` | ALL blocking lab dependencies terminal; clinician prompted to resume | `AWAITING_RESULTS` | `OPEN` (resume), `SIGNED` | `SYSTEM` (LAB-018) | ALL blocking LabOrderItems referenced by the encounter hold are `RELEASED` or `CANCELLED`, across every referenced order — never a subset; within 30 s of the last one | No |
| `SIGNED` | Legal immutable record; version ≥1; content hash | `OPEN`, `RESULTS_READY`, `AWAITING_RESULTS` (both pending-order paths only via explicit ENC-018 Sign now) | — (addenda only, ENC-023) | `CLINICIAN`/`MIDWIFE` (`encounter.sign`) | Minimum content (complaint, allergy status, diagnosis or no-diagnosis reason, disposition); signing with pending orders (from `OPEN` or `AWAITING_RESULTS`, via ENC-018 only) sets `signed_with_pending_orders=true` and atomically completes the consultation QueueEntry with reason `SIGNED_WITH_PENDING_RESULTS` (§22.1); visit must not be `CLOSED` (409 `VISIT_CLOSED`); idempotent; never nurses/admins | Yes |
| `VOIDED` | Created in error; retained in full for audit | `OPEN`, `AWAITING_RESULTS`, `RESULTS_READY`, `SIGNED` | — | `SUPERVISOR` (+`CLINICIAN` for unsigned) | Mandatory reason (≥20 chars); signed-encounter void needs supervisor + watermark | Yes |

### 22.5 LabOrderItem (per test) — LabOrder status is derived (LAB-006)

States: `ORDERED`, `AWAITING_PAYMENT`, `READY_FOR_COLLECTION`, `SAMPLE_COLLECTED`, `SAMPLE_REJECTED`, `RESULT_ENTERED`, `VERIFIED`, `RELEASED`, `CANCELLED`, `REFERRED_OUT` (P2).

| State | Meaning | Allowed from | Allowed to | Who may trigger | Guards | Terminal? |
| --- | --- | --- | --- | --- | --- | --- |
| `ORDERED` | Clinician intent exists; lab has not accepted (initial) | — | `AWAITING_PAYMENT`, `READY_FOR_COLLECTION`, `CANCELLED` | `CLINICIAN`/`MIDWIFE` (`lab.order.create`) | Encounter open/`RESULTS_READY`; test priced; canonical term `ORDERED` | No |
| `AWAITING_PAYMENT` | Visible to lab, not actionable | `ORDERED` | `READY_FOR_COLLECTION`, `CANCELLED` | `SYSTEM` (gate policy) | `LABORATORY=PAY_BEFORE`; lines unpaid | No |
| `READY_FOR_COLLECTION` | Lab may proceed (gate cleared) | `ORDERED`, `AWAITING_PAYMENT`, `SAMPLE_REJECTED` (recollection) | `SAMPLE_COLLECTED`, `CANCELLED`, `REFERRED_OUT`, `AWAITING_PAYMENT` (payment reversal before collection — PAY-012) | `SYSTEM` (payment/waiver/override), `LAB_TECH` (recollection), `SYSTEM` (reversal re-gate) | Recollection keeps the original order and charges nothing new (OD-12); reversal re-gate only before `SAMPLE_COLLECTED` — collected-or-later items never move backward | No |
| `SAMPLE_COLLECTED` | Specimen in lab custody; the decisive payment-gate delivery boundary | `READY_FOR_COLLECTION` | `RESULT_ENTERED`, `SAMPLE_REJECTED`, `CANCELLED` (supervisor) | `LAB_TECH`/`NURSE` (`lab.sample.collect`) | Identity read-back; specimen ID assigned. **Never moves backward** on payment reversal — `SAMPLE_COLLECTED → AWAITING_PAYMENT` is forbidden (PAY-012); reversal restores the financial balance only | No |
| `SAMPLE_REJECTED` | Sample unusable — actionable/recoverable | `SAMPLE_COLLECTED`, `READY_FOR_COLLECTION` | `READY_FOR_COLLECTION` (recollection), `CANCELLED` | `LAB_TECH` (`lab.sample.reject`) | Mandatory reason; clinician alerted ≤30 s; recollection count tracked; it does not satisfy readiness | No |
| `RESULT_ENTERED` | Values exist; not clinically visible | `SAMPLE_COLLECTED`, `REFERRED_OUT` (returned external/text result) | `VERIFIED`, `SAMPLE_COLLECTED` (verifier rejects entry) | `LAB_TECH` (`lab.result.enter`) | Sanity bounds enforced; invisible to clinicians | No |
| `VERIFIED` | Second check done; not yet released | `RESULT_ENTERED` | `RELEASED` | `LAB_VERIFIER` (`lab.result.verify`) | Batch-verification facilities only; otherwise verify+release is one action | No |
| `RELEASED` | Clinician-visible and printable; amendments create new versions | `VERIFIED` (or `RESULT_ENTERED` under single-action verify&release; self-release only under LAB-016) | — (amend via LAB-017) | `LAB_VERIFIER` | Release drives `RESULTS_READY`/`READY_TO_RESUME` (LAB-018); hash recorded | Yes |
| `CANCELLED` | Cancelled with reason | `ORDERED`, `AWAITING_PAYMENT`, `READY_FOR_COLLECTION`, `SAMPLE_COLLECTED` (supervisor), `SAMPLE_REJECTED` | — | `CLINICIAN` (orderer), `SUPERVISOR` | Post-collection needs supervisor; financial consequences per LAB-022 | Yes |
| `REFERRED_OUT` | Sent to external lab; non-terminal | `READY_FOR_COLLECTION` | `RESULT_ENTERED` (returned external/text result) | `LAB_TECH` (`lab.refer_out`) | P2; ageing-report inclusion; the returned result follows `RESULT_ENTERED → VERIFIED → RELEASED` and never releases directly | No |

**Derived LabOrder status (LAB-006):** derived only, never an additional persisted item state. `CANCELLED` = all items `CANCELLED`. `COMPLETED` = all items terminal and at least one `RELEASED` (therefore `RELEASED + CANCELLED` and `RELEASED + RELEASED` are `COMPLETED`). `PARTIALLY_RELEASED` = at least one `RELEASED` and at least one non-terminal item (for example `RELEASED + SAMPLE_COLLECTED`). Pending/active display = no item released and at least one non-terminal item (for example `ORDERED + SAMPLE_COLLECTED`). Never display an aggregate that hides per-item states.

### 22.6 Prescription

States: `DRAFT`, `ACTIVE`, `DISPENSED`, `PARTIALLY_DISPENSED`, `PARTIALLY_DISPENSED_CLOSED`, `NOT_DISPENSED`, `CANCELLED`.

| State | Meaning | Allowed from | Allowed to | Who may trigger | Guards | Terminal? |
| --- | --- | --- | --- | --- | --- | --- |
| `DRAFT` | Being composed in the open encounter; invisible to pharmacy | — | `ACTIVE` (only when ≥1 internally dispensable item exists and the Pharmacy module is enabled), `NOT_DISPENSED` (SYSTEM, at encounter signing, when all items are external-only — reason `EXTERNAL_SUPPLY` — or the Pharmacy module is disabled — reason `PHARMACY_DISABLED`; external prescription remains printable, no pharmacy queue/dispense/stock/charge), `CANCELLED` (encounter voided) | `CLINICIAN`/`MIDWIFE`; `SYSTEM` (signing terminalisation) | One draft per encounter; no new states — external/pharmacy-disabled terminalisation reuses `NOT_DISPENSED` with a structured reason | No |
| `ACTIVE` | Signed into force; in pharmacy queue ≤15 s; content immutable | `DRAFT` (on ENC-017 sign) | `DISPENSED`, `PARTIALLY_DISPENSED`, `NOT_DISPENSED`, `CANCELLED` | `SYSTEM` (signing fan-out) | Prescriber snapshot recorded; no charges yet | No |
| `PARTIALLY_DISPENSED` | Some items dispensed; outstanding items retained | `ACTIVE` | `DISPENSED`, `PARTIALLY_DISPENSED_CLOSED`, `CANCELLED` (undispensed items only) | `PHARMACIST` (DSP-009) | Dispensed items immutable | No |
| `PARTIALLY_DISPENSED_CLOSED` | Partially dispensed and closed out at visit closure | `PARTIALLY_DISPENSED` | — | `SYSTEM`/`RECEPTIONIST` via the REC-012 closure confirmation | Only when no pharmacy queue entry remains active and no provisional dispense awaits handover; atomic with `Visit → CLOSED` in the same transaction; undispensed quantities remain historically visible; no new dispense or stock movement | Yes |
| `DISPENSED` | Fully dispensed | `ACTIVE`, `PARTIALLY_DISPENSED` | — | `PHARMACIST` | Payment gate cleared; stock deducted atomically | Yes |
| `NOT_DISPENSED` | All items recorded not-dispensed with reasons — or external-only/pharmacy-disabled terminalised at signing (RX-005) | `ACTIVE`, `DRAFT` | — | `PHARMACIST` (DSP-005); `SYSTEM` (signing terminalisation) | Reasons retained (incl. `EXTERNAL_SUPPLY`/`PHARMACY_DISABLED`); clinician notified where applicable; never blocks Visit closure | Yes |
| `CANCELLED` | Cancelled/discontinued with reason | `DRAFT`, `ACTIVE`, `PARTIALLY_DISPENSED` (undispensed only) | — | Prescriber / `SUPERVISOR` (RX-009) | Race with dispense: committed dispense wins (409 to cancel) | Yes |

### 22.7 Dispense

States: `AWAITING_PAYMENT`, `CANCELLED` (pre-handover abandonment only), `DISPENSED`, `REVERSED`. `CANCELLED` is reachable only from `AWAITING_PAYMENT`; `CANCELLED → DISPENSED` is forbidden; no stock movement ever occurs for a `CANCELLED` dispense.

| State | Meaning | Allowed from | Allowed to | Who may trigger | Guards | Terminal? |
| --- | --- | --- | --- | --- | --- | --- |
| `AWAITING_PAYMENT` | Stable provisional basket/Dispense built; stock NOT deducted | — | `DISPENSED`, `CANCELLED` (pre-handover abandonment — DSP-005) | `SYSTEM` (creation under `MEDICINE=PAY_BEFORE`) | Stable DispenseLines, batch allocations and invoice-line source identities exist; payment gate or authorised override; no stock movement. A payment reversal before handover keeps/returns the Dispense here (PAY-012) — no stock has moved | No |
| `CANCELLED` | Provisional dispense abandoned/cancelled before physical handover; immutable historical record | `AWAITING_PAYMENT` only | — | `PHARMACIST` (or the SYSTEM workflow invoked by the pharmacist action — DSP-005) | No physical handover; no stock OUT entries; still provisional; **mandatory reason** (reuses DSP-005 vocabulary: `PATIENT_DECLINED`, `PATIENT_CANNOT_AFFORD`, `OUT_OF_STOCK`, `PRESCRIBER_CANCELLED`, `NOT_STOCKED`, `OTHER`). Terminal: never deleted, never reused, never converted to `DISPENSED`; a returning patient requires a **new** provisional Dispense through the normal workflow | Yes |
| `DISPENSED` | Confirmed handover; stock deducted; immutable | `AWAITING_PAYMENT` (or the same stable provisional dispense directly when non-gated) | `REVERSED` | `PHARMACIST` (`dispense.perform`) | Finalises the existing Dispense in one transaction; idempotent; expiry re-checked at confirm; never creates a second Dispense at handover | Yes¹ |
| `REVERSED` | Corrected with compensating stock IN | `DISPENSED` | — | `PHARMACIST` + `SUPERVISOR` approval | Medicines physically returned; same batch re-entry; financial path per DSP-016 | Yes |

¹ Reversible only via the audited reversal path; never editable or deleted.

### 22.8 Invoice

States: `DRAFT`, `ISSUED`, `PARTIALLY_PAID`, `PAID`, `VOIDED` (line-level voids via BIL-004; invoice-level `VOIDED` for cancelled/undone check-ins).

| State | Meaning | Allowed from | Allowed to | Who may trigger | Guards | Terminal? |
| --- | --- | --- | --- | --- | --- | --- |
| `DRAFT` | Transitional state inside the check-in/pricing transaction while the invoice is constructed or repriced (REC-001/REC-003) | — | `ISSUED`, `VOIDED` | `SYSTEM` | Payer/price list bound (REC-003); a successfully checked-in chargeable OPD visit's invoice is automatically `ISSUED` on commit — it never rests in `DRAFT`; payment-timing policy controls progression, not consultation-line creation or issue | No |
| `ISSUED` | At least one line; visible to cashier; lines still addable | `DRAFT` | `PARTIALLY_PAID`, `PAID`, `VOIDED` (only if unpaid) | `SYSTEM`/`CASHIER` | Facility invoice number (TEN-007) | No |
| `PARTIALLY_PAID` | Some payment allocated; balance > 0 | `ISSUED`, `PAID` (new line added) | `PAID` | `CASHIER` (via payments) | Allocation sum invariant (PAY-005) | No |
| `PAID` | Balance zero | `ISSUED`, `PARTIALLY_PAID` | `PARTIALLY_PAID` (post-payment line) | `CASHIER`/`SYSTEM` | Waiver path allowed (BIL-009) | No² |
| `VOIDED` | Invoice cancelled (e.g. check-in undo, LWBS before payment) | `DRAFT`, `ISSUED` (unpaid only) | — | `SYSTEM`/`RECEPTIONIST` (via REC-005/009/010) | Paid invoices are never voided — credit note instead (BIL-010) | Yes |

² `PAID` is financially final for its then-current lines; adding lines legitimately returns it to `PARTIALLY_PAID` (BIL-005). Payments themselves are immutable (PAY-008).

### 22.9 Payment

States: `CONFIRMED`, `REVERSED`. A payment is immutable from creation; the only "transition" is the audited reversal record referencing the original.

| State | Meaning | Allowed from | Allowed to | Who may trigger | Guards | Terminal? |
| --- | --- | --- | --- | --- | --- | --- |
| `CONFIRMED` | Recorded, allocated, receipted | — | `REVERSED` | `CASHIER` (`payment.record`) | Idempotency key; shift attribution; allocation invariants | No |
| `REVERSED` | Undone via reversal record; original retained | `CONFIRMED` | — | `SUPERVISOR`/`FACILITY_ADMIN` (`payment.reverse`) | Mandatory reason; gates re-evaluated under the undelivered-only principle (PAY-012 — delivered services are flagged, never undone); cross-shift accounting | Yes |

### 22.10 Appointment (fragment — APT epic not supplied)

The only transition defined by the supplied material: `NO_SHOW → CHECKED_IN` when a no-show appointment's patient arrives later the same day (REC-001 alt e), with an audit entry, plus an appointment→clinician routing effect (QUE-004). The full appointment state machine is defined in the unsupplied APT epic; do not implement beyond these references until APT is reconciled.

### 22.11 ANC enrolment / contact (fragment)

`ANCEnrolment` supports exactly one active enrolment per patient (ANC-001); closure semantics are not defined in the supplied material. An ANC **contact** is an `Encounter(type=ANC)` and uses the Encounter machine (22.4) in full — draft, park for results, resume, sign, addendum (ANC-002).

---

## 23. Handoff Matrix (consolidated)

Rows 1–9 are the attendance-loop rows supplied with the (reconciled) triage-generation draft, terminology-corrected. Rows 10–16 are consolidated from the supplied ENC/LAB/RX/DSP/PAY/REC stories. No contradictory states remain; all states reference §22.

| # | From role | Action (story) | To role | Record + new state | What the receiving role sees |
| --- | --- | --- | --- | --- | --- |
| 1 | `RECEPTIONIST` | Confirm check-in (REC-001) | `NURSE` | `Visit=OPEN`, `QueueEntry(TRIAGE)=WAITING` | Token, name, age (months if <5), sex, visit type, wait timer, under-5 / ANC chips |
| 2 | `RECEPTIONIST` | Check in `LAB_ONLY` (REC-004) | `LAB_TECH` | `QueueEntry(LAB)=WAITING` | Token, name, prior released orders, no-consultation-charge flag |
| 3 | `RECEPTIONIST` | Check in `FOLLOW_UP_RESULTS` (REC-004) | `CLINICIAN` | `QueueEntry(CONSULTATION)=WAITING`, `results_review=true` | "Results ready (n)" badge, link to released results, the original encounter ID |
| 4 | `CASHIER` | Confirm gated consultation payment (PAY-002/PAY-012) | `NURSE` | `QueueEntry: WAITING_PAYMENT → WAITING` | Patient now appears on the triage list; payment chip = Paid |
| 5 | `NURSE` | Complete triage (TRI-007) | `CLINICIAN` | `TriageRecord=COMPLETED`, `QueueEntry(CONSULTATION)=WAITING` at acuity priority | Acuity chip + reason, all vitals with abnormal highlighting, complaints + durations, allergy banner, recording nurse and time |
| 6 | `NURSE` | Escalate priority (TRI-006 / QUE-008) | `CLINICIAN` | `QueueEntry.priority=EMERGENCY` | Red banner "1 emergency waiting" with the escalation reason and nurse name |
| 7 | `NURSE` | Nurse-initiated test (TRI-007 alt a — **OD-21, not V1**) | `LAB_TECH` | `LabOrderItem=ORDERED`, `QueueEntry(LAB)=WAITING` | Test name, ordering clinician, triage acuity |
| 8 | `NURSE` | Emergency triage of provisional patient (TRI-013) | `CLINICIAN` + `RECEPTIONIST` | Provisional `Patient`, `Visit=OPEN`, `QueueEntry=WAITING/EMERGENCY` | Clinician: top of queue with "Provisional record" chip. Reception: "Complete registration" task |
| 9 | Any serving role | Mark LWBS (REC-009 / QUE-007) | `RECEPTIONIST` | `QueueEntry=LWBS`, `Visit=CLOSED(LWBS)` | Removed from all active lists; appears in the day's LWBS tally; refund task if paid |
| 10 | `CLINICIAN` | Send for investigations / park (ENC-016 + QUE-006; charges LAB-004; gate LAB-005) | `CASHIER` if gated, otherwise `LAB_TECH` | `Encounter=AWAITING_RESULTS`; consultation `QueueEntry=ON_HOLD(AWAITING_RESULTS)` (return point). Under `PAY_BEFORE`, items `ORDERED → AWAITING_PAYMENT` appear only in the non-actionable lab worklist, `QueueEntry(CASHIER)=WAITING` is the active location, and no LAB QueueEntry exists. After qualifying payment: cashier `COMPLETED`, paid items `READY_FOR_COLLECTION`, then `QueueEntry(LAB)=WAITING`. Under pay-after/no gate the lab QueueEntry may be created immediately. | Cashier: blocking unpaid lab lines (BIL-006). Lab: actionable test list only after ready for collection; worklist visibility is not physical queue location. |
| 11 | `LAB_TECH` / `LAB_VERIFIER` | Complete collection/receipt (LAB-008), then process/release results (LAB-015 + LAB-018) | `CLINICIAN` | Patient-facing `QueueEntry(LAB)=COMPLETED` after collection/receipt; item bench work continues independently. On `RELEASED`, when ALL blocking items are `RELEASED`/`CANCELLED`: `Encounter=RESULTS_READY`, consultation `QueueEntry=READY_TO_RESUME` (partial releases show "n of m ready" without transition) | "Ready to review" worklist entry with released-result count; results inline on resume |
| 12 | `CLINICIAN` | Sign encounter with prescription (ENC-017 + RX-005) | `PHARMACIST` | `Prescription=ACTIVE`, `QueueEntry(PHARMACY)=WAITING` (per clinician's onward routing) | Pharmacy queue entry ≤15 s with patient, prescriber, items, payment status |
| 13 | `CLINICIAN` | Order procedure (DX-005) | `NURSE` (treatment room) | `ProcedureOrder` pending + charge per gate | Nursing task with patient, procedure, instructions, priority |
| 14 | `PHARMACIST` | Confirm proposed basket, then finalise handover (DSP-007..009) | `CASHIER` / exit | Stable provisional `Dispense` with source-specific invoice lines; under pay-before `Dispense=AWAITING_PAYMENT` and the **same** pharmacy entry holds `ON_HOLD(AWAITING_PAYMENT)` while the cashier entry is the active location — after payment it resumes `READY_TO_RESUME → IN_SERVICE` and completes at handover; no stock OUT until then. After payment, the **same** dispense is finalised `DISPENSED`, stock OUT, prescription `DISPENSED`/`PARTIALLY_DISPENSED` | Cashier: medicine lines to collect payment when gated; patient: labels + receipt |
| 15 | `SYSTEM` | Payment releases gated services (PAY-012) | `LAB_TECH` / `PHARMACIST` / `CLINICIAN` | Required paid lab line: item `AWAITING_PAYMENT → READY_FOR_COLLECTION`, cashier `COMPLETED`, then LAB QueueEntry `WAITING`; same provisional dispense confirmable and held pharmacy entry `ON_HOLD → READY_TO_RESUME` (same entry, DSP-008); other physical service queue `WAITING_PAYMENT → WAITING` | Affected department sees the patient become actionable ≤15 s |
| 16 | `RECEPTIONIST` | Close visit (REC-012) | — | `Visit=CLOSED(reason)`; `PENDING_RESULTS` only with a signed encounter carrying pending orders and its consultation queue entry completed at signing (ENC-018 `SIGNED_WITH_PENDING_RESULTS`) | Patient leaves "currently present" counts; day reconcilable; blockers recorded if force-closed |

---

## 24. Permissions Matrix (canonical)

Compiled from the `Perm` fields of the stories. ✓ = explicitly granted in story text; ○ = conditional/configuration-dependent; blank = not granted (denied by the Global Story Contract). Server-authoritative; frontend gates are UX only.

| Capability (permission) | SYS_ADMIN | ORG_OWNER | ORG_ADMIN | FACILITY_ADMIN | SUPERVISOR | RECEPTIONIST | NURSE | MIDWIFE | CLINICIAN | LAB_TECH | LAB_VERIFIER | PHARMACIST | STORE_KEEPER | CASHIER | SYSTEM |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `visit.create` | | | | ✓ | | ✓ | ✓ | | | | | | | | |
| `visit.read` / `visit.read_list` | | | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | | | | ✓ | |
| `visit.update_payer` | | | | ✓ | | ✓ | | | | | | | | ✓ | |
| `visit.update_admin` (REC-011) | | | | | | ✓ | | | | | | | | | |
| `visit.close` | | | | ✓ | | ✓ | | | | | | | | ✓ | |
| `visit.close_with_debt` / `visit.force_close` | | | | ✓ | ○ | | | | | | | | | | |
| `visit.close_abandoned` / `visit.override_duplicate` | | | | ✓ | ✓ | ○ | | | | | | | | | |
| `visit.cancel_error` | | | | | | ✓ | | | | | | | | | |
| `visit.print_slip` | | | | | | ✓ | | | | | | | | | |
| `queue.read` (scoped by queue type) | | | | ✓ | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | ✓ | |
| `queue.read_board` (QUE-014) | | ✓ | | ✓ | ✓ | | | | | | | | | | |
| `queue.serve` (call/start; `queue.call_out_of_order` ○) | | | | | | | ✓ | ✓ | ✓ | ✓ | | ✓ | | ✓ | |
| `queue.assign` | | | | | ✓ | ✓ | ✓ | | | | | | | | |
| `queue.move` (complete + hand off) | | | | | | | ✓ | ✓ | ✓ | ✓ | | ✓ | | ✓ | |
| `queue.hold` (consultation workflows; MIDWIFE in ANC scope; PHARMACIST for pharmacy `AWAITING_PAYMENT` holds only — DSP-008) | | | | | | | | ○ | ✓ | | | ○ | | | |
| `queue.remove` | | | | ✓ | ✓ | ✓ | ✓ | | | | | | | | |
| `queue.priority.set` (escalate; de-escalate: CLINICIAN/SUPERVISOR only) | | | | | ✓ | ✓ | ✓ | | ✓ | | | | | | |
| `queue.takeover` | | | | ✓ | ✓ | | | | ○ | | | | | | |
| `queue.mark_no_show` | | | | | | | ✓ | ✓ | ✓ | ✓ | | ✓ | | ✓ | |
| `triage.create` (record vitals/complaint/acuity) | | | | | | | ✓ | ✓ | ✓ | | | | | | |
| `triage.create_emergency` (TRI-013) | | | | | | | ✓ | ✓ | ✓ | | | | | | |
| `triage.read` | | | | | ✓ | | ✓ | ✓ | ✓ | | | | | | |
| `triage.update` (amend own; `triage.amend_any`: SUPERVISOR/FACILITY_ADMIN) | | | | ✓ | ✓ | | ✓ | | | | | | | | |
| `allergy.manage` (incl. mark entered-in-error: CLINICIAN+) | | | | | | | ✓ | ✓ | ✓ | | | ✓ | | | |
| `encounter.create` | | | | | | | | ✓ | ✓ | | | | | | |
| `encounter.read` (variants; role-scoped payloads) | | | | ✓ | ✓ | ○ | ○ | ✓ | ✓ | | | ○ | | | |
| `encounter.update` (author) / `encounter.takeover` | | | | | ✓ | | | ✓ | ✓ | | | | | | |
| `encounter.sign` (never nurses, never admins) | | | | | | | | ✓ | ✓ | | | | | | |
| `encounter.void` | | | | | ✓ | | | ○ | ○ | | | | | | |
| `encounter.amend` (author; SUPERVISOR non-author) | | | | | ✓ | | | ✓ | ✓ | | | | | | |
| `encounter.print` | | | | | | ○ | | ✓ | ✓ | | | | | | |
| `lab.catalogue.manage` | | | | ✓ | | | | | | ○ | | | | | |
| `lab.order.create` (not nurses in V1 — OD-21) | | | | | | | | ✓ | ✓ | | | | | | |
| `lab.order.create.external` (LAB-024) | | | | | | ✓ | | | | ✓ | | | | | |
| `lab.queue.read` | | | | | ✓ | | | ✓ | ✓ | ✓ | ✓ | | | | |
| `lab.sample.collect` | | | | | | | ✓ | | | ✓ | | | | | |
| `lab.sample.reject` | | | | | | | | | | ✓ | | | | | |
| `lab.result.enter` | | | | | | | | | | ✓ | | | | | |
| `lab.result.verify` (self-verify only under LAB-016 ○) | | | | | | | | | | | ✓ | | | | |
| `lab.result.read` / `lab.result.print` | | | | | | ○(print) | | ✓ | ✓ | ✓(print) | ✓ | | | | |
| `lab.result.amend` | | | | | ✓ | | | | | | ✓ | | | | |
| `lab.order.cancel` (post-collection: SUPERVISOR) | | | | | ✓ | | | ✓ | ✓ | ○ | | | | | |
| `lab.refer_out` | | | | | | | | | | ✓ | | | | | |
| `prescription.create` / `.limited` (RX-011 ○ — MIDWIFE only in V1; NURSE deferred) | | | | | | | | ○ | ✓ | | | | | | |
| `dispense.queue.read` / `dispense.perform` / `dispense.read` | | | | | | | | ○(read) | ○(read) | | | ✓ | | | |
| `dispense.reverse` (SUPERVISOR approval) | | | | | ✓ | | | | | | | ✓ | | | |
| `inventory.receive` | | | | | | | | | | | | ✓ | ✓ | |
| `inventory.read` | | | | ✓ | ✓ | | | | ○ | | | ✓ | ✓ | |
| `inventory.adjust` (above threshold: FACILITY_ADMIN approval) | | | | ✓ | | | | | | | | ✓ | ✓ | |
| `invoice.read` | | | | ✓ | ✓ | ○(limited) | | | | | | | | ✓ | |
| `billing.manual_line` | | | | ✓ | | | | | | | | | | ✓ | |
| `billing.gate.override` (reason mandatory) | | | | ✓ | ✓ | | | | ○ | | | ○ | | ○ | |
| `payment.record` | | | | | | | | | | | | ○(retail) | | ✓ | |
| `payment.read` | | | | ✓ | | | | | | | | | | ✓ | |
| `payment.reverse` (never CASHIER by default) | | | | ✓ | ✓ | | | | | | | | | | |
| `facility.policy.manage` (LAB-016 etc.) | | | | ✓ | | | | | | | | | | | |
| `supervisor.dashboard` | | | | ✓ | ✓ | | | | | | | | | | |
| `ops.run_sweep` | | | | ✓ | | | | | | | | | | | |
| Controlled-flag set/clear (RX-008) | | ✓ | | | | | | | | | | | | | |
| Device token (display board, read-only) | | | | | | | | | | | | | | | |

*(Cells reflect only what the supplied stories state; the platform-level roles' full capability sets live in the unsupplied AUTH/TEN/USR epics.)*

---

## 25. Audit Event Catalogue (as specified in the stories)

High-value events (content hashes and redacted non-PHI metadata) marked ★.

**Tenancy-wide defaults** (Global Story Contract): every mutation writes an audit event with actor, role, tenant/facility, entity/version reference, action, changed-field names, reason where applicable, redacted non-PHI before/after metadata if used, IP, user agent, request ID and time. Generic audit events never duplicate raw clinical content; versioned domain records retain it. Every PHI chart read writes one `category=PHI_READ, action=PATIENT_RECORD_VIEWED` event; no PHI in payloads.

| Domain | Events |
| --- | --- |
| Reception / Visit | `VISIT_OPENED`, `QUEUE_ENTRY_CREATED`, `INVOICE_ISSUED`, `OUTSTANDING_BALANCE_OVERRIDDEN`, `PATIENT_CREATED`, `DUPLICATE_OVERRIDE`, `VISIT_PAYER_SET`, `INVOICE_REPRICED`, `ROUTING_OVERRIDDEN`, `VISIT_ABANDONED`, `SECOND_VISIT_OVERRIDE`, `INVOICE_VOIDED`, `DOCUMENT_REPRINTED`, `QUEUE_ENTRY_REMOVED`, `VISIT_CLOSED_LWBS`, `REFUND_REQUESTED`, `VISIT_CANCELLED_ERROR`, ★`VISIT_CLOSED` (redacted non-PHI closure-checklist metadata in `after_json`), enquiry create/convert |
| Queue | `QUEUE_ENTRY_CREATED` (with source), per-transition events, `QUEUE_CALLED`, `QUEUE_CALLED_OUT_OF_ORDER`, `QUEUE_CALL_EXPIRED`, `QUEUE_NO_SHOW`, `QUEUE_SERVICE_STARTED`, `QUEUE_SERVICE_COMPLETED`, `QUEUE_HANDOFF`, `QUEUE_TAKEOVER`, `QUEUE_PRIORITY_CHANGED`, `QUEUE_SWEEP_RUN` |
| Triage | `TRIAGE_STARTED`, `TRIAGE_VITALS_RECORDED` (record-version reference, changed field names, hash), `TRIAGE_COMPLAINT_RECORDED`, `TRIAGE_ACUITY_ASSIGNED`, `TRIAGE_ACUITY_DOWNGRADED`, `TRIAGE_COMPLETED`, ★`TRIAGE_AMENDED` (old/new version references/hashes, changed field names, reason), `VITALS_RECORDED` (REPEAT), `ALLERGY_RECORDED`, `ALLERGY_CONFIRMED`, `ALLERGY_ENTERED_IN_ERROR`, `PROVISIONAL_PATIENT_CREATED`, ★`PATIENT_MERGED` |
| Encounter | create/open, ★sign (hash, downstream fan-out), `ENCOUNTER_RESUMED`, `ENCOUNTER_DRAFT_UPDATED` (per session-minute summary), park (reason + orders), ★void (prior hash), ★takeover, ★addendum (own hash), `category=PHI_READ, action=PATIENT_RECORD_VIEWED`, print/reprint (AUD-009) |
| Laboratory | order creation (order/item IDs + version hashes, priority, ordering actor), gate transitions + overrides, collection (collector, specimen IDs), rejection (reason), result entry (result-version reference/changed fields/hash), ★verify/release (verifier + result-version hash), ★amendment (old/new result-version references/hashes + reason), state transitions with trigger, late-result acknowledgement, blocked-expired attempts (via INV) |
| Prescriptions | ★activation (prescription ID/version + item version hashes + prescriber snapshot), cancellation (reason mandatory), dispense-time substitution records (DSP-006) |
| Pharmacy / Inventory | product create/edit, price changes (old/new), catalogue import (file, rows), ★GRN posting (all lines), transfers, quarantine, adjustments (actor, reason, before/after balances; threshold approval), count sessions, ledger exports |
| Dispensing | ★dispense confirmation (Dispense/DispenseLine/StockMovement references + content hashes), reversals, not-dispensed reasons |
| Billing | each invoice line with source, voids (before/after totals), discounts/waivers (reason, threshold), credit notes, manual lines (reason) |
| Payments | each payment (amount, method, reference, actor, shift, invoice, allocations), ★reversals (high-severity; reason), shift open/close (float, counted cash, variance), duplicate flags, MoMo duplicate-reference confirmations |
| Printing | every print/reprint: document type, record ID, actor, timestamp, copy number (RCP-003); reprint history viewable by SUPERVISOR/FACILITY_ADMIN |
| External (unsupplied AUD epic) | `PHI_READ` with `PATIENT_RECORD_VIEWED` as its named action subtype, content hashes (AUD-003), amendment notifications (AUD-008), reprint audit (AUD-009), access-review reporting (AUD-011), draft-summary retention (AUD-012) |

---

## 26. Current Implementation Gap Analysis

The supplied source did **not** include its planned gap-analysis section (it was scheduled for a later, unsupplied generation part). Per the reconciliation rules, no functionality is claimed to exist unless the supplied backlog supports it — and this document is documentation-only, with no code audit performed. Conservative classification of all fourteen supplied epics:

| Epic | Classification | Note |
| --- | --- | --- |
| REC, QUE, TRI | UNKNOWN / NEEDS CODE REVIEW | No implementation-status evidence in the supplied source. |
| ENC, LAB, DX, RX | UNKNOWN / NEEDS CODE REVIEW | Same. |
| PHM, INV, DSP | UNKNOWN / NEEDS CODE REVIEW | Same. |
| BIL, PAY, RCP | UNKNOWN / NEEDS CODE REVIEW | Same. |
| ANC | UNKNOWN / NEEDS CODE REVIEW | Same. |

A real IMPLEMENTED / PARTIALLY IMPLEMENTED / NOT IMPLEMENTED pass requires a story-by-story code review against the repository, which is a separate task.

---

## 27. Priority Summary

| Epic | P0 | P1 | P2 | Total |
| --- | --- | --- | --- | --- |
| REC | 7 | 4 | 2 | 13 |
| QUE | 7 | 8 | 1 | 16 |
| TRI | 8 | 5 | 0 | 13 |
| ENC | 18 | 4 | 2 | 24 |
| LAB | 20 | 4 | 1 | 25 |
| DX | 5 | 3 | 2 | 10 |
| RX | 7 | 2 | 2 | 11 |
| PHM | 3 | 4 | 1 | 8 |
| INV | 10 | 4 | 2 | 16 |
| DSP | 11 | 5 | 0 | 16 |
| BIL | 9 | 5 | 0 | 14 |
| PAY | 11 | 2 | 1 | 14 |
| RCP | 5 | 2 | 0 | 7 |
| ANC | 7 | 0 | 0 | 7 |
| **Total** | **128** | **52** | **14** | **194** |

Count reconciliation: source apparent story definitions = 213 (plus one truncated leading fragment whose ID was lost = ~214, matching the source's own "71 of 214" bookkeeping) → canonical unique = 194 after 20 duplicate/alternate versions were merged and the fragment folded into REC-001. No stories were added.

---

## 28. Pilot Core

Subset of **existing stories** necessary to run the initial single-branch Kampala medical-centre workflow (Journeys A–D end-to-end). Not every P0 is included; the existing P1 INV-001 is a hard pilot prerequisite; deferrals are listed with reasons.

**Attendance loop**
- REC-001, REC-002, REC-003, REC-004, REC-005 — check-in, registration, payer/price binding, routing, duplicate guard: the desk cannot run without these.
- REC-007 — the desk's information hub ("where is my patient").
- REC-012 — defines "finished"; without closure the day never reconciles.
- QUE-001, QUE-002, QUE-003 — location spine, worklists, call/start.
- QUE-005, QUE-006, QUE-007, QUE-008 — handoff, Journey-B hold, removal, emergency priority.
- TRI-001, TRI-002, TRI-003, TRI-004, TRI-006, TRI-007, TRI-009, TRI-011 — triage loop incl. human acuity, allergies, paediatric weight.

**Clinical core**
- ENC-001..ENC-006, ENC-008, ENC-010, ENC-011, ENC-014..ENC-018, ENC-020, ENC-021, ENC-023, ENC-024 — the long-lived encounter: create/resume/park/sign/amend/print and the clinician worklists.
- DX-001, DX-002, DX-004, DX-006, DX-008 — diagnoses, plan, disposition, follow-up.
- RX-001..RX-005, RX-007, RX-008 — prescribing, activation, print, controlled-block.

**Laboratory** (the pilot facility runs a small lab — Journeys B/D)
- LAB-001, LAB-002, LAB-004..LAB-011, LAB-013, LAB-015..LAB-020, LAB-022, LAB-023 — catalogue, orders, charges/gates, collection, entry, verify/release, clinician signalling, cancellation, late results.
- LAB-016 — single-technician self-release configuration: the pilot lab has one technician; without this it stalls.
- LAB-021 — defensible to defer to immediately-post-pilot: supervisor monitoring; manual review suffices on day one.

**Pharmacy & stock**
- PHM-001, PHM-002, PHM-003 — catalogue, price, prescribing link.
- INV-001, INV-002..INV-006, INV-008, INV-009, INV-011, INV-012, INV-014 — stock locations (a hard pilot prerequisite), receipts, batch/expiry, FEFO, the never-dispense-expired rule, balances, alerts, adjustments, atomic deduction, ledger.
- DSP-001..DSP-005, DSP-007..DSP-010, DSP-013, DSP-015 — queue, availability, FEFO selection, quantity adjustment, not-dispensed, charges, gate, confirm, labels, retail, expired-assertion.

**Money & documents**
- BIL-001, BIL-002, BIL-004..BIL-007, BIL-013, BIL-014 — charge capture, one-invoice invariant, voids, issue, cashier list, detail, duplicate-charge prevention, closure balance.
- PAY-001, PAY-002, PAY-003, PAY-005, PAY-007..PAY-009, PAY-011..PAY-014 — methods, recording, partials, allocation, lookup, reversal, shifts, duplicates, gate release, MoMo reference, segregation of duties.
- RCP-001..RCP-004, RCP-007 — receipts, layouts, reprint audit, headers, numbering.

**Conditional (include iff the pilot facility offers the service)**
- ANC-001..ANC-007 — the ANC clinic slice (Journey E); include when ANC services run at the pilot branch.

**Deliberately deferred (P0 but not first-pilot-critical), with reasons**
- LAB-021 — ageing/stuck-order dashboard: monitoring nicety; QUE-011 SLA badges + manual review cover day one.
- BIL-011 — invoice print grouping: presentation polish; the cashier list and RCP-002 layouts suffice initially.

Pilot-core total: 120 story IDs (plus 7 conditional ANC).

---

## 29. Recommended Implementation Waves

Derived from story priorities and dependencies (the source's own wave plan was in an unsupplied part). Each wave is a vertical slice of existing stories only.

**Wave 1 — Attendance loop (the desk, queue and triage).**
REC-001..REC-005, REC-007, REC-012; QUE-001..QUE-003, QUE-005..QUE-008; TRI-001..TRI-004, TRI-006, TRI-007, TRI-009, TRI-011. Deliverable: a patient can check in, be triaged with human acuity, queue fairly, and leave with a closed visit and an auditable queue history.

**Wave 2 — Clinical core + laboratory (Journeys B/D).**
ENC-001..ENC-006, ENC-008, ENC-010, ENC-011, ENC-014..ENC-018, ENC-020..ENC-024; DX-001, DX-002, DX-004, DX-006, DX-008; RX-001..RX-005, RX-007, RX-008; LAB-001, LAB-002, LAB-004..LAB-011, LAB-013, LAB-015..LAB-020, LAB-022, LAB-023; plus the remaining queue/triage breadth (QUE-004, QUE-009..QUE-016; TRI-005, TRI-008, TRI-010, TRI-012, TRI-013) as the slice matures. Deliverable: the encounter is long-lived and resumable; results return to the same encounter; signed notes are immutable.

**Wave 3 — Pharmacy, stock and money (Journey C + the cash desk).**
PHM-001..PHM-003 (then PHM-004..PHM-008); INV-002..INV-006, INV-008, INV-009, INV-011, INV-012, INV-014 (then INV-001, INV-007, INV-010, INV-013, INV-015, INV-016); DSP-001..DSP-005, DSP-007..DSP-010, DSP-013, DSP-015 (then DSP-006, DSP-011, DSP-012, DSP-014, DSP-016); BIL-001..BIL-014; PAY-001..PAY-014; RCP-001..RCP-007. Deliverable: FEFO dispensing and retail with the expired-stock absolute rule, and a reconcilable cash desk.

**Wave 4 — ANC and operational breadth.**
ANC-001..ANC-007 (Journey E); LAB-021, LAB-024, LAB-025; DX-003, DX-005, DX-007, DX-009, DX-010; RX-006, RX-009..RX-011; QUE-012; REC-006, REC-008..REC-011, REC-013; remaining P2s. Deliverable: full V1 breadth on top of the hardened core.

---

## 30. Definition of Done (per story / per slice)

Preserved from the Global Story Contract and the stories' test expectations (the source's per-slice DoD section was planned for an unsupplied part; these are its compiled requirements, which the stories already restate).

A story is done when:

1. Service-level unit tests exist and pass for the service function(s) implementing it.
2. API contract tests pass, including the specified 403 (permission), 404 (cross-tenant) and 409/412 (concurrency) behaviours.
3. One UI happy path and one negative path are demonstrated, with explicit loading, empty and error states.
4. One tenant-isolation test proves cross-facility reads fail closed (404).
5. Audit assertions cover every audited action the story specifies (including high-value hash events where marked ★).
6. State-transition tests cover both legal and illegal transitions for every machine in §22 the story touches.
7. Accessibility coverage exists for core workflow screens (keyboard-operable, no colour-alone signalling).
8. Generated OpenAPI/client types validate where applicable.
9. A clear migration path and rollback/correction behaviour exist (nothing final is ever hard-deleted).
10. For money, clinical and stock creations: idempotency-key behaviour and ETag/If-Match concurrency are tested.

A task is not complete merely because the UI works.

---

## 31. Open Product Decisions

Each decision: **OD-ID · Question · Why unresolved · Affected stories · Safe temporary V1 assumption.** Items OD-04..OD-17 are referenced by the source drafts themselves; OD-18..OD-22 were surfaced by this reconciliation. None of these may be silently settled where clinical or financial safety is involved.

### 31.1 Decision register

**OD-04 · Expired clinician licence at signing.** Block or warn? Medico-legal position not validated. *Affects:* ENC-017. *V1 assumption:* warn, do not block.

**OD-07 · Orders after the encounter is signed.** New encounter vs addendum-linked order. *Affects:* LAB-002, ENC-023, LAB-023. *V1 assumption:* no new orders on a signed encounter; late results attach as addenda.

**OD-08 · Problem-list auto-derivation from diagnoses.** Should resolved/chronic problems derive automatically? *Affects:* ENC-009. *V1 assumption:* manual promotion only.

**OD-09 · Facility-authored ANC guidance text.** May facilities display their own ANC guidance, clearly attributed? Ownership/liability unvalidated. *Affects:* ANC-005 (and the ANC epic preamble). *V1 assumption:* no platform guidance; facility-authored text must be clearly attributed if enabled.

**OD-10 · Laboratory `IN_PROGRESS` bench-tracking state.** Dropped for V1; pilot must confirm no facility needs a separate bench click. *Affects:* LAB §12.0, LAB-007, LAB-010. *V1 assumption:* dropped; add later between `SAMPLE_COLLECTED` and `RESULT_ENTERED` if needed.

**OD-12 · Recollection charging when the rejection is patient-caused.** *Affects:* LAB-009. *V1 assumption:* recollection never recharges; policy hook deferred.

**OD-13 · OTC sale of prescription-only medicines.** Control-and-report vs hard prohibition. *Affects:* DSP-013, PHM-001. *V1 assumption:* permitted with recorded reason + pharmacist acknowledgement + separate report.

**OD-15 · Injectable batch/lot capture for treatment-room items.** Free-text batch/lot documentation applies only to externally sourced/non-inventory items and is clinical documentation, not a stock movement. For a KlinKlik-stocked product, structured stock issue with product, non-expired batch, quantity and location is mandatory; INV-005 applies with no override. *Affects:* DX-005, INV-005, DSP-015. *V1 rule:* the safety guarantee applies to KlinKlik-managed inventory and makes no claim of enforcement over external free-text items.

**OD-17 · ANC sensitive-field printing (HIV status etc.).** Disclosure rules for the ANC card print. *Affects:* ANC-003. *V1 assumption:* stored as recorded; no automatic disclosure unless explicitly the ANC card and facility-enabled.

**OD-18 · REQUIRES CLINICAL VALIDATION — Triage acuity scheme and any automated suggestion.** Should KlinKlik (a) adopt a validated instrument (SATS/MTS/ESI) in place of the simple 3-tier scheme, and (b) ever suggest/pre-select an acuity from vitals or danger signs? A draft generation implemented exactly such auto-suggestion (SpO₂ → pre-selected `EMERGENCY`; "difficulty breathing" → at least `PRIORITY`); another generation prohibited it. Automated suggestion is clinical decision support and is **not V1 behaviour**. *Affects:* TRI-002 (flags only), TRI-003 (danger-sign documentation), TRI-006, QUE-001, QUE-008, TRI-007, handoff rows 5–6. *V1 assumption:* human-assigned `EMERGENCY|URGENT|ROUTINE`; neutral out-of-range flags only; no computation, suggestion, or pre-selection.

**OD-19 · REQUIRES CLINICAL VALIDATION — Allergy exact-string-match warning at prescribing.** A draft generation warned when a prescribed generic string-matched a recorded allergen (with acknowledgment override). Even exact-string matching is a form of safety logic with false-reassurance risk. *Affects:* TRI-004, RX-002, RX-003, DSP-002. *V1 assumption:* prominent allergy banner display only; **no automatic matching, warning, or blocking**; UI copy must not imply checking occurs.

**OD-20 · REQUIRES CLINICAL VALIDATION — Paediatric weight-for-age percentile band display.** A draft generation computed a percentile band for under-5s (simple table lookup). It conflicts with the other generation's explicit "growth charts out of scope". *Affects:* TRI-002, TRI-011. *V1 assumption:* reference-range display only; no percentile computation.

**OD-21 · Nurse-initiated laboratory ordering from a configured list.** A draft generation allowed nurse-ordered malaria RDTs from a facility-configured nurse-orderable list (CAT-007); the lab epic explicitly excludes nurses from `lab.order.create` in V1. *Affects:* TRI-007 (alt a), LAB-002, handoff row 7, CAT-007 (external). *V1 assumption:* ordering restricted to `CLINICIAN`/`MIDWIFE`; nurses may route a patient to a department but not create orders.

**OD-22 · Nightly sweep vs never-auto-close for stale visits.** One generation's nightly job only flags stale visits (`STALE_OPEN`, never auto-closes); the other's sweep auto-closes them (`CLOSED(ABANDONED)`/`CLOSED(INCOMPLETE)`). Reconciled in QUE-016/REC-012 to auto-close only zero-record visits, but the operational rule should be confirmed with the facility. *Affects:* QUE-016, REC-012, REC-005, OPS-004 (external). *V1 assumption:* auto-close only visits with no clinical or financial records; everything else flagged for human review.

### 31.2 External references (stories referenced but not supplied)

The following IDs are referenced by canonical stories and exist in the wider backlog (AUTH→PAT and Part 4–6 epics) whose definitions were **not** part of the supplied source. They are retained as dependencies and must be resolved when those parts are reconciled: `AUTH-008, AUTH-012, AUTH-013`; `TEN-003, TEN-005, TEN-006, TEN-007`; `USR-003, USR-004`; `CAT-001, CAT-002, CAT-004, CAT-005, CAT-006, CAT-007`; `PAT-001, PAT-002, PAT-003, PAT-004, PAT-007, PAT-009, PAT-010, PAT-013`; `APT-001..APT-003, APT-005`; `REP-002, REP-004, REP-006..REP-016`; `AUD-001, AUD-003, AUD-008, AUD-009, AUD-011, AUD-012`; `BRN-003, BRN-004, BRN-005, BRN-006`; `OPS-003, OPS-004`. No reference in this document points to an ID that is neither a canonical story nor listed here.

---

## 32. Reconciliation Log

Editorial record of this reconciliation; **not part of product requirements**. Routine grammar/format edits are not listed.

1. **Source identified as two concatenated generations.** The supplied file contained the tail of a compact-generation draft (epics 4–17: REC-tail, QUE, TRI, ENC, LAB, DX, RX, PHM, INV, DSP, BIL, PAY, RCP, ANC) followed by a complete verbose-generation part ("Continued (Part 3 of 6)": REC, QUE, TRI + queue state machine + 9 handoff rows + closing commentary). All "Part X of Y", "Continued", "Part 4 next", "Delivered so far", "Where this leaves us" and similar generation/continuation artefacts were removed; the useful content underneath was kept.
2. **ID collision between generations resolved.** Both generations numbered REC/QUE/TRI from 001 with **different content** (e.g. compact REC-011 "Close a visit" vs verbose REC-011 "Resume an in-progress visit"; compact QUE-004 "Assign to clinician" vs verbose QUE-004 "No-show"; compact TRI-005 "current medications" vs verbose TRI-005 "assign acuity"). Canonical numbering keeps the **compact generation's QUE/TRI numbering** (it is the generation the ENC/LAB/DX/RX/PHM/INV/DSP/BIL/PAY/RCP/ANC epics — and this reconciliation's binding references QUE-006, ENC-016, LAB-018 — are written against) and the **verbose generation's REC-001..011 numbering** (its REC epic is complete in the source; the compact REC-001..009 definitions were never supplied).
3. **REC merges and renumbering.** Verbose REC-001..011 kept as REC-001..011. Compact REC-011 (close visit, with force-close, blocker matrix, `STALE_OPEN`, `POST_CLOSURE_ACTIVITY`) merged into REC-012 (close at exit desk, with `CLOSED(PENDING_RESULTS)`, debt path). Compact REC-010 (walk-in enquiry) renumbered **REC-013** to resolve the collision with verbose REC-010 (undo check-in). Result: 13 canonical REC stories.
4. **QUE merge map** (verbose → canonical): QUE-001→001, QUE-002→002, QUE-003+QUE-005→003 (call + start unified, as in the compact generation), QUE-004→009 (no-show unified with no-response/recall), QUE-006→005 (complete+handoff unified with move/forward), QUE-007→**013** (kept as its own story; the compact generation had it only as an alternate flow of QUE-004/ENC-022), QUE-008→007, QUE-009→008. Verbose-only stories appended: QUE-010→**014** (supervisor board), QUE-011→**015** (queue history), QUE-012→**016** (daily sweep). Result: 16 canonical QUE stories; **QUE-006 remains the Journey-B hold story**, exactly as referenced by ENC-002/ENC-016/LAB-018.
5. **TRI merge map** (verbose → canonical): TRI-001+TRI-002→001 (worklist + start), TRI-003→002 (vitals), TRI-004→003 (complaint), TRI-005→006 (acuity), TRI-006→007 (complete & send), TRI-007→009 (clinician view), TRI-008→010 (repeat vitals), TRI-009→008 (amend), TRI-011 split across 004 (allergies) and 005 (current medicines). Verbose-only stories appended: TRI-010→**012** (vitals history), TRI-012→**013** (walk-in emergency triage). Result: 13 canonical TRI stories.
6. **Triage acuity conflict reconciled (OD-18).** `EMERGENCY|PRIORITY|STANDARD` with system-suggested/pre-selected acuity from vitals and danger signs (verbose generation) vs `EMERGENCY|URGENT|ROUTINE` with explicit "no automatic acuity computation" (compact generation). Canonical: the human-assigned three-tier `EMERGENCY|URGENT|ROUTINE`; all auto-suggestion behaviour moved to OD-18; neutral out-of-range flags (fever chips, `abnormal_high` payload flags) retained as display-only.
7. **Queue state machine unified.** The verbose generation's machine omitted `ON_HOLD`/`READY_TO_RESUME` (the Journey-B states its own workflow stories required) and used `REMOVED`/`NO_SHOW`/`EXPIRED`; the compact generation had `ON_HOLD`/`READY_TO_RESUME`/`TRANSFERRED`/`CANCELLED`/`LWBS` plus `WAITING_PAYMENT` (from the verbose REC-001). Canonical machine (§22.1) is the union with `REMOVED` mapped to `CANCELLED`/`LWBS` by reason, and satisfies QUE-006, ENC-002, ENC-016, LAB-018 and the handoff matrix exactly.
8. **Lab status terminology unified: `REQUESTED` → `ORDERED`** (one handoff-matrix row used `REQUESTED`; the lab epic's §8.0 rationale and every story use `ORDERED`). Also `RESULT_RELEASED` → `RELEASED` (one REC-004 acceptance criterion). No aliases retained.
9. **Allergy auto-warning moved to OD-19.** The verbose TRI-011 specified an exact-string-match prescription warning with acknowledgment; the compact TRI-004/RX-002/RX-003 explicitly prohibit any matching and any UI implication of it. Canonical V1: banner only. (The source's own closing commentary flagged this as an open decision.)
10. **Nurse-initiated lab ordering moved to OD-21.** Verbose TRI-006 A2 (nurse-ordered RDTs from a configured list) conflicts with LAB-002's "`lab.order.create` — not nurses in V1". Canonical V1: clinician/midwife-only ordering; nurses may route.
11. **Nightly-sweep vs never-auto-close reconciled (OD-22).** Compact REC-011: nightly job only flags `STALE_OPEN`. Verbose QUE-012: sweep auto-closes stale visits. Canonical (QUE-016): entries expire; zero-record visits may auto-close `CLOSED(ABANDONED)`; any visit with clinical or financial records is flagged for human review and never auto-closed.
12. **Leading truncated fragment folded into REC-001.** The source file began mid-story (an appointment-driven check-in story whose ID and first fields were lost in truncation). Its surviving content (appointment-specified clinician routing; same-day no-show appointment check-in `NO_SHOW → CHECKED_IN`) is preserved in REC-001 flow/alt/AC.
13. **ANC-007 truncated in source.** The compact ANC-007 ("ANC investigations") was cut off mid-acceptance-criterion in the supplied source. A minimal scope was first reconstructed from the surviving text and flagged; the canonical acceptance criteria were subsequently completed strictly from the already-established standard laboratory/encounter rules (LAB-002..LAB-023, ENC-016/ENC-018, QUE-006), with no new clinical protocol behaviour invented.
14. **Forward references from the verbose generation remapped by meaning** to canonical IDs, because they were written against the unsupplied Part 4–6 numbering: `ENC-015`→ENC-017 (sign), `ENC-011`→ENC-022 (takeover), `ENC-018`→REC-012 (close path), `BIL-011`→BIL-004 (void), `BIL-006`→BIL-005 (issue), `PAY-003`→PAY-002 (record payment), `DSP-006`→DSP-009 (confirm dispense), `LAB-010`→LAB-015 (release), `LAB-014`→LAB-015 (release), `TRI-003`→TRI-002 (vitals), `TRI-005`→TRI-006 (acuity), `TRI-006`→TRI-007 (complete triage), `QUE-005`→QUE-003 (start service), `QUE-006`→QUE-005 (handoff), `QUE-008`→QUE-007 (remove), `QUE-009`→QUE-008 (priority), `QUE-010`→QUE-014 (board), `RX-004`→RX-003 (allergy view), `DSP-004`→DSP-002 (dispense screen). Compact-generation references remapped: `REC-005`(consultation charge)→REC-001, `REC-006`(cancel visit)→REC-010, `REC-011`(close visit)→REC-012 (in BIL-014, QUE-007, TRI-007).
15. **Visit closure vocabulary unified.** Verbose literal states `CLOSED_COMPLETED`, `CLOSED_PENDING_RESULTS`, `CLOSED_ABANDONED`, `CLOSED_INCOMPLETE`, `CLOSED_LWBS`, `CLOSED_LWBS_PAID` became `CLOSED` with a closure-reason discriminator; `CANCELLED_ERROR` kept as a state. Queue `REMOVED` became `CANCELLED`/`LWBS` by reason.
16. **Vitals validation bound conflict kept conservative-source value.** Temperature plausibility bound 30.0–45.0 °C (compact) vs 30.0–43.0 (verbose): kept 30.0–45.0; "Not done — with reason" (verbose) merged into the optional-fields rule (compact) as a first-class alternative; MUAC unit kept cm (compact) with the verbose 6–59-month age rule; BMI server-computed (both). Weight-for-age percentile band (verbose) → OD-20.
17. **Prescription-payment-gate and handoff terminology normalised**: "PAY-003 consultation payment" rows → PAY-002/PAY-012; queue enqueue timestamp named `queued_at` (verbose used `entered_at`); permission names normalised to the compact set (`queue.remove` not `queue.remove_entry`, `allergy.manage` not `patient.record_allergy`, `triage.update`/`triage.amend_any` for amend permissions), preserving verbose-only capabilities (`queue.call_out_of_order`, `queue.takeover`, `queue.read_board`, `triage.create_emergency`, `visit.close_abandoned`, `visit.override_duplicate`, `visit.cancel_error`, `visit.update_payer`).
18. **Duplicate-detection semantics merged** (QUE-001): compact unique-partial-index rejection and verbose idempotent return-existing combined — no duplicate is ever created; idempotent re-requests return the existing entry.
19. **Encounter-reuse rule strengthened by merge** (ENC-001/ENC-002/QUE-003): the verbose generation's "no new encounter on resume — the central design rule of V1" acceptance criterion was merged into ENC-001/ENC-002 and made a mandatory release regression test; co-author semantics folded into ENC-022.
20. **Story counts.** Source: 213 defined stories + 1 truncated leading fragment (~214, matching the source's own "71 of 214" note). Canonical: **194** unique stories. 20 duplicate/alternate versions merged or absorbed (REC 2, QUE 8, TRI 10); 1 story renumbered (compact REC-010 → REC-013); 0 new stories added. Epic counts: REC 13, QUE 16, TRI 13, ENC 24, LAB 25, DX 10, RX 11, PHM 8, INV 16, DSP 16, BIL 14, PAY 14, RCP 7, ANC 7. Priorities preserved except where duplicate versions disagreed (merged stories took the stricter/higher priority of their versions; e.g. queue priority handling remains P0).
21. **Unsupplied epics documented, not invented.** AUTH, TEN, USR, CAT, PAT, APT, REP, AUD, BRN, OPS story definitions were absent from the source; their references are catalogued in §31.2 and no content was fabricated for them. The executive summary, assumptions, Global Story Contract, permissions matrix, audit catalogue, gap analysis, pilot core, waves and definition of done were **compiled from content present in the supplied stories** (or marked as not supplied); the source's own planned versions of those sections (its Parts 1 and 6) were not available.
22. **Generation-plan discrepancy noted.** The verbose generation's closing note planned Part 4 as ENC=20/LAB=18 stories; the supplied compact generation contains ENC=24/LAB=25. The supplied (more granular) versions are canonical; nothing was split or merged to match the plan.
