# KlinKlik UX / Product Implementation Handoff

Prepared for: Qwen 3.8 Chat (UX/UI prototyping agent)
Prepared from: the actual KlinKlik repository at `K:\clinicopus` (inspected 2026-08-21)
Purpose: static HTML/Tailwind prototype design for future KlinKlik workflows.

You (Qwen) cannot see the repository, the database, or the running app. Everything
you need is in this document. Internal file paths are cited only for traceability;
the important content is restated here directly.

---

## 1. Executive Summary

KlinKlik (wordmark **KLINKLIK**, descriptor "Clinic Management System") is a
Uganda-first clinic operations SaaS. It is designed for small and mid-sized
healthcare facilities in Uganda: standalone clinics, pharmacies, and combined
clinic + pharmacy businesses. Currency defaults to **UGX**, timezone defaults to
**Africa/Kampala**, and demo data uses Ugandan names and phone numbers
(`07…`). Prices are shown as whole-shilling amounts (e.g. `UGX 30000`).

The product is **multi-tenant**. A customer organisation (the tenant root) owns
facilities (branches); facilities own departments; users belong to the
organisation with per-facility/per-department roles. One platform serves three
facility modes: CLINIC, PHARMACY, and CLINIC + PHARMACY. In the current build
only the clinic flow is implemented end to end.

The current implementation is a **working product, not a mockup**. A real
Django/DRF backend (modular monolith, PostgreSQL with row-level tenant
isolation) and a real Next.js frontend (role-aware routed workspaces) are
running and covered by automated tests, including full-browser Playwright flows
that walk a patient from registration to receipt across four different staff
logins.

The implemented clinical journey today is:

> Reception registers/finds the patient and checks them in → the patient
> appears on today's queue → a nurse records triage (acuity, chief complaint,
> vitals) → a clinician starts an encounter, writes a free-text consultation
> note, and signs it (signing is final; corrections require a recorded
> amendment) → an invoice is created for the visit → a cashier looks up the
> unpaid invoice, posts a payment, and prints a receipt.

What is **intentionally not implemented yet**: pharmacy, medicines/inventory,
dispensing, laboratory orders and results, prescriptions, structured diagnosis
workflows, ANC/maternity, appointments UI, reports, notifications, SMS,
WhatsApp, and mobile-money integrations. Empty backend app scaffolds exist for
some of these (they contain no code), so you may design their UX, but you must
not present them as working product.

The visual language is an approved, specific design system: light theme only,
Inter typeface, purple primary (#6D4AFF), soft pastel accent family, 18px card
radii, 264px desktop sidebar, 72px topbar. It is translated faithfully from an
approved static reference (`K:\new\clinic.html`) into the production app.

Your job is to design **missing and deeper workflows as static prototypes**
inside this shell — most urgently the clinician experience (rich clerking, the
lab loop, prescriptions) — without changing the approved shell, brand, or the
working concepts described here.

---

## 2. Source-of-Truth Hierarchy

Four sources, in this order of authority:

1. **FUNCTIONAL REQUIREMENTS — the approved user-story backlog from Opus**
   (supplied to you separately, per design batch). This tells you WHAT users
   must accomplish. When a story conflicts with anything below, the story wins
   — but flag the conflict rather than silently redesigning.

2. **CURRENT IMPLEMENTATION — the actual KlinKlik repository** (summarized in
   this document). This tells you WHAT ALREADY EXISTS and works. Do not
   contradict it; extend it.

3. **VISUAL LANGUAGE — `K:\new\clinic.html`** (the approved static reference)
   **and the implemented design system** (Section 11). This tells you HOW
   KlinKlik LOOKS. When they differ on a detail, the implemented values in
   Section 11 are the ones to use.

4. **ARCHITECTURE — `K:\new\clinicopus2.md`** (canonical product/architecture
   blueprint; filename is historical). This governs engineering structure. You
   are not redesigning architecture; treat it as fixed context.

Rules for Qwen:

- Do not contradict approved user stories.
- Preserve existing working concepts (statuses, handoffs, roles, records).
- Use the current visual language exactly (Section 11).
- Do not redesign architecture, tenancy, or data integrity rules (Section 22).

---

## 3. Product Naming

- Public product name: **KlinKlik** (exact spelling; "KlinKlik", "KLINKLIK",
  "klinklik" are the only allowed casings).
- Wordmark (sidebar/login): **KLINKLIK**.
- Descriptor line under the wordmark: **Clinic Management System**.
- API title: "KlinKlik API". Browser/metadata title: "KlinKlik".

Internal technical identifiers still say **clinicopus** and that is
intentional (a rename of infrastructure was deliberately deferred). You will
see "clinicopus" in: the database name, the database role, the Django project
package, the filesystem path, demo e-mail addresses, and the demo slug. These
are **not** visual brand references and must never appear in your prototypes.

Always render the brand as KlinKlik / KLINKLIK. Never "Clinicopus",
"Klin Klik", "Klin-Klik", "ClinKlik", or any other variant.

Facility names are data, not branding: the demo facility is called
**Kampala Medical Centre** (keep it in prototypes).

---

## 4. Tenant / Facility Model

Hierarchy:

```
Organisation (tenant root)
└── Facility (a branch; unique code, e.g. "MAIN")
    ├── Departments (unique codes: RECEPTION, OPD, TRIAGE, BILLING, …)
    └── Enabled Modules (per-facility feature flags)
```

Key concepts:

- **Organisation** is the tenant root and the unit of isolation, billing
  (currency, default UGX), and identity. Attributes visible in UX: name,
  status (Active/Suspended/Closed), timezone, default currency.
- **Facility** is a branch, not a tenant. Every working screen is scoped to
  one active facility at a time; the current facility is selectable in the
  sidebar (facility switcher). A facility has a mode: CLINIC, PHARMACY, or
  CLINIC + PHARMACY (future modes beyond clinic are not implemented).
- **Department** is a sub-unit of a facility (e.g. Outpatient "OPD"). Queue
  numbers are per department per day; users can be assigned to a department.
- **Enabled Modules** gate which product areas a facility uses ( Patients,
  Reception, Queue, Triage, Consultation, Billing, Appointments, Reporting are
  defined; only the first six have working features today).
- **Users** have a global login identity, an organisation membership, and one
  or more **role grants** (role + optional facility + optional department).
  A user can hold different roles in different facilities. The same role
  template can behave differently by department (see Reception vs Cashier,
  Section 5).
- **Permissions (capabilities)** are fine-grained codes (e.g.
  `patient.view`, `triage.record`, `billing.payment.record`) attached to roles.
  The server computes the effective capability list at login and returns it
  with the session.

Demo tenant used across the app and tests:

- Organisation: **Kampala Medical Centre**
- Facility: **Main Branch** (code `MAIN`, mode CLINIC)
- Departments: Reception (`RECEPTION`), Outpatient (`OPD`), Triage (`TRIAGE`),
  Billing (`BILLING`)

Server-authoritative decisions (never re-invented client-side): membership,
role grants, capability checks, facility membership, tenant isolation, and
module enablement. The frontend receives the capability list and merely hides
or shows navigation/actions — every API call is re-checked server-side.

You do not need internal row-level-security details for UX work; know only
that a user from one organisation can never see another organisation's data.

---

## 5. Current User Roles

Four **role templates** exist today. Five **UX personas** are derived from
them (Reception and Cashier share one template; the department decides which
workspace they land in).

Capabilities are exact server-defined codes. Full catalogue (15):
`patient.view`, `patient.create`, `patient.edit`, `patient.link`,
`queue.view`, `queue.claim`, `triage.record`, `clinical.note.create`,
`clinical.note.sign`, `clinical.note.amend`, `billing.invoice.create`,
`billing.payment.record`, `billing.receipt.print`, `audit.log.view`,
`staff.permission.grant`.

### Admin — role template `OWNER_ADMIN`
- Purpose: full access; runs the facility.
- Landing page: `/overview`.
- Sidebar items: Overview, Patients, Queue, Triage, Consultations, Billing &
  Payments (all capabilities).
- Key capabilities: all 15.
- Restricted actions: none (in current scope).
- Workspace character: operational overview — greeting, metric cards, today's
  queue summary, quick actions. No admin/staff-management UI exists yet.

### Reception — role template `RECEPTION_CASHIER`, non-BILLING department
- Purpose: patient registration, search, check-in; may also invoice and take
  payment (the template allows billing capabilities).
- Landing page: `/overview`.
- Sidebar items: Overview, Patients, Queue, Billing & Payments (no Triage, no
  Consultations).
- Key capabilities: patient.view/create/edit, queue.view/claim,
  billing.invoice.create, billing.payment.record, billing.receipt.print.
- Restricted actions: triage and clinical notes.
- Workspace character: registry-first — search dominates; register form;
  selected-patient panel with check-in.

### Nurse — role template `NURSE_TRIAGE`
- Purpose: triage patients who are waiting.
- Landing page: `/triage`.
- Sidebar items: Overview, Patients, Queue, Triage.
- Key capabilities: patient.view, queue.view, queue.claim, triage.record.
- Restricted actions: consultation notes, billing.
- Workspace character: two-pane — waiting list left, triage record right.

### Doctor / Clinician — role template `CLINICIAN`
- Purpose: see triaged patients, write and sign the consultation note.
- Landing page: `/consultations`.
- Sidebar items: Overview, Patients, Queue, Consultations.
- Key capabilities: patient.view, queue.view, queue.claim,
  clinical.note.create/sign/amend.
- Restricted actions: billing (no invoice creation UI; handoff message shown
  after signing).
- Workspace character: two-pane — ready list left, consultation editor right.

### Cashier — role template `RECEPTION_CASHIER` with a BILLING department
- Purpose: collect payments on unpaid invoices from any staff member, print
  receipts.
- Landing page: `/billing`.
- Sidebar items: Overview, Patients, Queue, Billing & Payments.
- Key capabilities: same template as Reception.
- Restricted actions: triage and clinical notes.
- Workspace character: unpaid-invoice lookup first; payment panel; receipt.

### Future roles — NOT IMPLEMENTED (do not imply they work)
Lab Technician, Pharmacy Staff/Dispenser, Midwife/ANC nurse, and any
platform-level staff roles. The data model (roles are data-driven) could
support them, but nothing exists: no capabilities, no UI, no API.

---

## 6. Current Navigation / Routes

All current frontend routes (Next.js App Router):

| Route | Page | Primary roles | Purpose | Status |
|---|---|---|---|---|
| `/login` | Login | unauthenticated | username + password + organisation ID | Working |
| `/` | Root redirect | all | redirects to role landing route (or `/login`) | Working |
| `/overview` | Overview/landing | Admin, Reception (default for others) | greeting, metrics, today's queue, quick actions | Working |
| `/patients` (+`?q=`) | Patients | Admin, Reception, Cashier, Nurse, Clinician (view) | search, register, select, check-in | Working |
| `/queue` | Queue | all with `queue.view` | today's queue, status filter pills, client filter, claim/open | Working |
| `/triage` (+`?entry=`) | Triage | Nurse | waiting list + triage record form | Working |
| `/consultations` (+`?entry=`) | Consultations | Clinician | ready list + encounter + note + sign | Working |
| `/billing` (+`?patient=` +`?encounter=`) | Billing & Payments | Cashier, Reception, Admin | unpaid invoices, new invoice, payment, receipt | Working |

There are **no nested routes** — each workspace is a single page with
in-page panels and query-string deep links (e.g. `/triage?entry=<uuid>`
preselects a queue entry; `/billing?patient=…&encounter=…` prefills invoice
creation after a signed consultation).

Role redirect behavior: after login the app routes by role — admin/reception →
`/overview`, nurse → `/triage`, clinician → `/consultations`, cashier →
`/billing`. Direct navigation to an unauthorised page shows an
"UnauthorisedState" card naming the required capability (not a redirect).

Sidebar modules present in the approved visual reference but intentionally
**absent from the product because the capability does not exist**: Laboratory,
Pharmacy, Inventory, Appointments/Schedule, ANC/Maternity, Reports,
Notifications, Settings/Administration. When Qwen designs those areas, add
them as new sidebar entries in the same visual grammar — do not pretend the
current app already has them.

---

## 7. Current End-to-End Workflow

**THIS FLOW CURRENTLY WORKS** and is covered by automated browser tests with
four separate role logins. It is the spine of the product; preserve it.

1. **Reception → Patient → Check-in → Queue**
   Reception searches the registry (by name fragment, phone, or patient
   number), or registers a new patient (first name, last name, phone, sex).
   New patients receive an auto-allocated patient number (`P-` + 8
   alphanumeric characters, e.g. `P-4KX92A7Q`). Reception selects a patient,
   picks a department, and checks them in. Check-in creates a queue entry with
   a per-department daily sequence and label `DEPT-###` (e.g. `OPD-004`),
   status WAITING, current_stage RECEPTION.

2. **Nurse → Triage**
   The nurse sees WAITING/CALLED patients at `/triage`, selects one, records
   chief complaint (free text), priority (Routine/Urgent/Emergency —
   nurse-assigned, the system never computes acuity), and optional vitals
   (pulse, temperature °C, systolic/diastolic BP). On submit the queue entry
   becomes TRIAGED and current_stage becomes CONSULTATION. A vitals
   observation record is stored on the patient.

3. **Doctor → Consultation → Sign**
   The clinician sees TRIAGED/IN_CONSULTATION patients at `/consultations`,
   selects one, and starts the encounter (creates an `ENC-` reference; queue
   entry becomes IN_CONSULTATION). They write a free-text consultation note
   (pre-seeded with "Assessment: \nPlan: "), then click "Sign consultation",
   which reveals an explicit confirmation strip warning that signing is final.
   Confirming signs the note: note status SIGNED, encounter status SIGNED,
   an immutable version snapshot is recorded, and the note is locked forever.
   After signing, the clinician either sees a "Create invoice" link (if they
   have billing capability) or a handoff message to the cashier.

4. **Billing → Invoice**
   Any user with billing capability can create an invoice at `/billing`:
   search patient, pick a service from the facility catalogue (e.g. "General
   consultation · 30000.00"), create. Invoices are `INV-` references, start
   ISSUED, and can optionally be linked to a signed encounter (the backend
   refuses to bill an unsigned encounter).

5. **Cashier → Invoice lookup → Payment → Receipt**
   A cashier (fresh login, different person from the invoice creator) finds
   the unpaid invoice via the "Awaiting payment" list and search (invoice
   number, patient name, or patient number — this cross-user lookup is a
   solved, tested behavior). They post a payment (amount ≤ balance; method
   Cash/Mobile money/Card/Bank; optional reference for non-cash). Invoice
   becomes PAID (or PARTIALLY_PAID for partial amounts). A receipt
   (`RCT-` reference) is fetched and displayed as a print sheet; the Print
   button prints only the receipt (the app shell is excluded via CSS).

Major limitation — the **clinically complete loop does NOT yet exist**:

> Doctor → Lab → Doctor resume → Prescription → Pharmacy → Dispensing

Today the doctor has one free-text note and signing terminates the clinical
record. There is no investigation ordering, no awaiting-results state, no lab
handoff, no result review, no structured diagnosis, no prescription, and no
pharmacy path. These are the primary design targets for Qwen (Section 20).

Signing semantics: signing **finalises** the clinical note under
immutable-record rules. A signed note can never be edited — corrections are
made by a **recorded amendment** (new immutable version + mandatory reason).
Any prototype you make must visibly honor this lock.

---

## 8. Current Domain Model

UX-relevant summary of entities that CURRENTLY EXIST. (Grouped; all IDs are
UUIDs; every clinical/financial record also carries organisation and facility
context.)

### Tenancy
- **Organisation** — the tenant. User-visible: name, status
  (ACTIVE/SUSPENDED/CLOSED), default currency (UGX), timezone.
- **Facility** — branch with code (e.g. MAIN), mode
  (CLINIC/PHARMACY/CLINIC_PHARMACY), active flag.
- **Department** — facility sub-unit with code (RECEPTION/OPD/TRIAGE/BILLING).
- **Module / FacilityModule** — per-facility feature flags (8 defined; see
  Section 4).
- **Subscription** (schema only, no UI/API) — TRIAL/ACTIVE/PAST_DUE/CANCELLED.

### Identity / Security
- **User** — global identity: username (e-mail-style in demo), full name,
  active flag. Has a PIN hash field (unused in UX today).
- **Role** — named per organisation, with a template code
  (OWNER_ADMIN/RECEPTION_CASHIER/NURSE_TRIAGE/CLINICIAN).
- **Permission (capability)** — code + sensitivity tier T1–T3.
- **RolePermission / UserFacilityRole** — which roles carry which
  capabilities; which users hold which role (optionally scoped to facility
  and department, with status ACTIVE/EXPIRED/REVOKED and expiry).
- **OrganisationMembership** — ACTIVE/REVOKED per user per organisation.
- **AuthSession** — server session record: hashed access + refresh tokens,
  expiry timestamps, revocation, rotation chain. Supports "sessions are
  revocable and rotate on refresh" UX without exposing detail.
- **UserCredential** — professional credentials (e.g. clinical licence
  number, issuing body, validity) — captured in seed data, not yet surfaced
  in UX.

### Patients
- **Patient** — demographics: patient_no (unique per organisation), first /
  middle / last name, sex (FEMALE/MALE/INTERSEX/UNKNOWN/NOT_STATED),
  date of birth, phone, e-mail, address, notes; status
  ACTIVE/DECEASED/ARCHIVED. Never hard-deleted; status changes instead.
- **PatientIdentifier** — national ID / passport / insurance / other numbers,
  with normalization and a verified flag; searchable.
- **PatientContact** — related contacts (relationship, name, phone).
- **PatientLink** — links two patients: type
  SUSPECTED_DUPLICATE/RELATED/EMERGENCY_CONTACT, status
  OPEN/CONFIRMED/REJECTED, reason, review trail. API exists; no dedicated UI
  yet.
- **Consent** (schema only) — treatment/data-processing/communication
  consent, GRANTED/WITHDRAWN, notice version.

### Scheduling / Queue
- **QueueEntry** — one visit on one day: patient, department, queue_date,
  daily sequence, label `DEPT-###`, visit_type (WALK_IN default), status,
  current_stage, arrival/called/claimed/completed timestamps, claiming user,
  notes. Unique (facility, date, sequence).
- **Appointment** (schema only — model exists, NO API/UI) — booked slots with
  status BOOKED/CHECKED_IN/COMPLETED/CANCELLED/NO_SHOW.
- **FollowUpRecommendation** (schema only) — follow-up date/instructions.

### Clinical
- **Encounter** — one clinical visit: `ENC-` number, patient, optional
  1:1 link to a QueueEntry, clinician, status OPEN/SIGNED/CLOSED/CANCELLED,
  started/signed/closed timestamps. Billing may attach to it.
- **TriageAssessment** — one per queue entry: acuity
  ROUTINE/URGENT/EMERGENCY, chief complaint, observations JSON, nurse.
- **VitalsObservation** — measured vitals: systolic, diastolic, pulse,
  temperature_c, respiratory_rate, oxygen_saturation, weight_kg, height_cm.
  (Triage UI currently captures pulse, temperature, BP; the model holds more.)
- **ClinicalNote** — the consultation note: JSON content, status
  DRAFT/SIGNED/AMENDED, author, signer, signed_at, current_version.
  Immutable once signed; corrections only via amendment.
- **ClinicalNoteVersion** — append-only version snapshots with reason
  ("Initial signature" / amendment reasons).
- **Diagnosis / Allergy / Procedure / Referral** (schema only — no API/UI) —
  structured clinical entries ready for future workflows.

### Billing
- **ServiceCatalogItem** — billable service (code, name, category, active).
- **ServicePrice** — facility-scoped price with effective dates and currency
  (UGX).
- **Invoice** — `INV-` number, patient, optional signed encounter, status
  DRAFT/ISSUED/PARTIALLY_PAID/PAID/VOID, currency, subtotal, discount,
  total, amount_paid, balance, issued_at, creator.
- **InvoiceItem** — line items (service, description, quantity, unit price,
  amount).
- **Payment** — `RCT-` receipt number (unique), amount, method
  CASH/MOBILE_MONEY/CARD/BANK, optional reference, status
  POSTED/REVERSED, receiver, received_at.
- **PaymentAllocation** — allocates a payment amount against a specific
  invoice (supports future multi-invoice settlement semantics — do not
  redefine).
- **CashierShift** (schema only — no API/UI) — open/closed shift with
  opening float, declared cash, close reason.

### Platform Infrastructure
- **AuditEvent** — append-only audit trail: action
  (CREATE/UPDATE/READ/SIGN/AMEND/LINK/PAYMENT/LOGIN/LOGOUT/EXPORT), entity,
  actor, facility, request id, IP, user agent, before/after snapshots,
  timestamp. Database-level triggers block updates and deletes.
- **IdempotencyRecord** — stores request-hash + response for safe client
  retries of POST/PATCH/PUT with an `Idempotency-Key` header.

---

## 9. Current State Machines / Statuses

EXACT implemented values. Do not invent others; do not rename them.

### QueueEntry.status
| State | Meaning | Who causes it | What the user sees |
|---|---|---|---|
| WAITING | checked in, awaiting triage | Reception (check-in) | amber "Waiting" badge |
| CALLED | claimed by staff (triage) | Nurse/any claimer via Claim | blue "Called" badge |
| IN_TRIAGE | (reserved value — triage write moves entries straight to TRIAGED; currently no UI sets this) | — | blue "In triage" badge (filter exists) |
| TRIAGED | triage complete, ready for doctor | Nurse (Complete triage) | purple "Ready for consultation" |
| IN_CONSULTATION | doctor started encounter | Clinician (Start encounter) | purple "In consultation" |
| COMPLETED | visit finished | system (end of flow; default list excludes) | teal "Completed" |
| CANCELLED | cancelled | system (default list excludes) | neutral "Cancelled" |

Parallel field `current_stage`: RECEPTION → TRIAGE → CONSULTATION (shown as a
small stage label on the queue page). Queue list defaults to excluding
COMPLETED/CANCELLED; filters accept comma-separated or repeated `status`
values; unknown values are rejected with a 400 error.

### Encounter.status
| State | Meaning | Who causes it | What the user sees |
|---|---|---|---|
| OPEN | encounter started, note editable | Clinician | purple "ENC-… · Open" chip |
| SIGNED | note signed — final | Clinician (Confirm signature) | teal "Signed" + locked note UI |
| CLOSED | administrative close | system (rare; not in UI) | — |
| CANCELLED | cancelled | system (not in UI) | — |

### ClinicalNote.status
| State | Meaning | Who causes it | What the user sees |
|---|---|---|---|
| DRAFT | editable | Clinician | editable textarea |
| SIGNED | final, locked | Clinician (sign) | "signed and immutable" banner |
| AMENDED | corrected via amendment | Clinician (amend, with reason) | version history concept |

### Invoice.status
| State | Meaning | Who causes it | What the user sees |
|---|---|---|---|
| DRAFT | transient during creation | system (brief; creation immediately issues) | — |
| ISSUED | awaiting payment | Reception/Cashier/Admin (Create invoice) | amber "Awaiting payment" |
| PARTIALLY_PAID | some payments posted | Cashier (partial payment) | blue "Partially paid" |
| PAID | balance zero | Cashier (full payment) | teal "Paid" |
| VOID | cancelled | system (no UI to void yet) | neutral "Void" |

### Payment.status / methods
| State | Meaning | Who causes it | What the user sees |
|---|---|---|---|
| POSTED | recorded payment | Cashier (Post payment) | receipt |
| REVERSED | reversed (correction path) | system (no UI yet) | — |

Methods: CASH, MOBILE_MONEY, CARD, BANK (shown as "Cash", "Mobile money",
"Card", "Bank"; non-cash optionally carries a reference string).

### Session state
AuthSession has no user-facing enum: it is either active (refresh works) or
revoked/expired (user must log in again). Access tokens are short-lived
(15 min); refresh cookies are long-lived (7 days) and **rotate** on every
refresh (an intercepted old cookie is detected and rejected).

### Patient.status
ACTIVE (normal), DECEASED, ARCHIVED (search only returns ACTIVE).

### FUTURE STATES NEEDED BY STORIES (do NOT treat as existing)
Anything for lab orders/results (e.g. awaiting-results, results-ready),
prescription states, dispense states, ANC visit states. None of these exist
in code today. When a story needs them, design them and clearly mark them as
NEW concepts for production implementation.

---

## 10. Current API Capabilities

Map of what the UX can already rely on. All endpoints are under
`/api/v1/…` on the backend; the frontend calls them with a Bearer access
token and the `X-Facility-Id` header when a facility is chosen.

| Area | Capability | Current API support | Important filters/search | Notes |
|---|---|---|---|---|
| Platform | health | GET `/health/` | — | `{"status":"ok","service":"klinklik-api"}` |
| Auth | login | POST `/auth/login/` | — | username+password+organisation_id; returns access token, user, organisation, facilities, roles, capabilities |
| Auth | refresh | POST `/auth/refresh/` | — | httpOnly rotating cookie; returns fresh session |
| Auth | logout | POST `/auth/logout/` | — | revokes session |
| Auth | me | GET `/auth/me/` | — | current session incl. roles/capabilities |
| Tenancy | facilities | GET `/tenancy/facilities/` | active only | for facility switcher |
| Tenancy | departments | GET `/tenancy/departments/` | scoped to active facility | used by check-in form |
| Patients | search | GET `/patients/?q=` | matches **individual fields**: patient_no, first name, middle name, last name, phone, and normalized identifiers | NOT a concatenated "First Last" match — a full-name query may return nothing. Ordered last name, first name. Capped at 100. |
| Patients | register | POST `/patients/` | — | first/last name required; sex, phone, DOB, identifier optional; patient_no auto-allocated `P-XXXXXXXX` |
| Patients | detail | GET `/patients/{id}/` | — | includes identifiers + contacts |
| Patients | edit demographics | PATCH `/patients/{id}/` | requires `If-Match` ETag | 428 if ETag missing; 412 if record changed (conflict UX) |
| Patients | link duplicates | POST `/patients/{id}/link/` | — | link type + reason; returns OPEN link. No dedicated UI yet. |
| Queue | check-in | POST `/clinic/check-ins/` | — | patient_id + optional department_id; returns entry with label `DEPT-###` |
| Queue | list | GET `/clinic/queue/` | `status` (comma/repeated, validated), `date` | default excludes COMPLETED/CANCELLED |
| Queue | claim | POST `/clinic/queue/{id}/claim/` | — | only WAITING/CALLED entries; sets CALLED + claimed_by |
| Triage | record | POST `/clinic/triage/{queue_id}/` | — | acuity, chief_complaint, optional vitals (pulse, temperature_c, systolic, diastolic, + respiratory rate, O2 sat, weight, height supported by model); updates/overwrites the entry's single assessment; moves entry to TRIAGED |
| Encounter | start/open | POST `/clinic/encounters/` | — | by queue_entry_id; idempotent per queue entry (re-start returns same encounter); moves queue to IN_CONSULTATION |
| Encounter | detail | GET `/clinic/encounters/{id}/` | — | includes notes |
| Clinical notes | draft/edit | POST `/clinic/encounters/{id}/notes/` | — | creates or updates the DRAFT consultation note; refuses once signed |
| Clinical notes | sign | POST `/clinic/encounters/{id}/sign/` | — | finalizes note + encounter; immutable afterwards |
| Clinical notes | amend | POST `/clinic/encounters/{id}/amend/` | — | only on signed notes; requires reason; bumps version. API only — no UI yet. |
| Billing | service catalogue | GET `/billing/services/` | active services with facility prices | e.g. "General consultation · 30000.00 UGX" |
| Billing | create invoice | POST `/billing/invoices/` | — | patient + items (service_id, quantity); optional encounter_id (must be SIGNED/CLOSED); supports discount; returns ISSUED invoice |
| Billing | invoice lookup | GET `/billing/invoices/` | `status` (comma/repeated, validated), `q` matches invoice_no, patient_no, patient **first** or **last** name individually | newest first; capped 100. Cross-user lookup works (cashier finds reception's invoice). |
| Billing | invoice detail | GET `/billing/invoices/{id}/` | — | with items + payments |
| Payments | post payment | POST `/billing/invoices/{id}/pay/` | — | amount > 0 and ≤ balance; updates amount_paid/balance/status |
| Receipts | retrieve | GET `/billing/invoices/{id}/receipt/` | — | latest posted payment; receipt/invoice numbers, patient, amount, method, reference, invoice balance, printable text line |

Cross-cutting API behaviors the UX can assume: every authenticated GET 200
carries an ETag; mutations may send `Idempotency-Key` for safe retries
(replays are flagged with an `Idempotent-Replay: true` header); permission
failures return 403; cross-tenant or wrong-facility records return 404;
validation errors return 400 with a human-readable `detail` message.

---

## 11. Current Design System

The approved visual language, as actually implemented (source of truth:
`frontend/src/app/globals.css`, `frontend/src/components/ui.tsx`, translated
from `K:\new\clinic.html`). This is a HARD specification — reuse these exact
values.

### Theme
Light only. `color-scheme: light`. No dark mode; do not design one.

### Font
**Inter** everywhere (`--font-sans`). Base body size 14px, antialiased.
Type scale in practice: page title 26px bold (-0.02em tracking), card title
15px bold, primary body/label 13–13.5px semibold/medium, secondary meta
11.5–12.5px medium, micro text 10.5–11px, badge text 10.5px semibold,
uppercase eyebrow 11px bold with 0.12em tracking (login "CLINIC
OPERATIONS").

### Geometry
- Desktop sidebar: **264px** wide (≥1024px, `lg`); collapses to a **76px icon
  rail** at 768–1023px (`md`); below 768px it becomes a slide-in overlay
  (264px) opened from a topbar menu button.
- Sidebar header height: 76px. Topbar: **72px**, sticky, `canvas` background
  at 95% opacity with backdrop blur, bottom border.
- Page content padding: `px-5` (20px), `lg:px-7` (28px), `pt-6` `pb-8`; page
  sections spaced 20px (`space-y-5`).
- Cards: radius **18px**, border 1px, padding 20px (`p-5`), inner list rows
  divided by soft hairlines, ~12px vertical rhythm per row.
- Primary buttons/inputs: height **44px** (`h-11`), radius 12px. Small/action
  buttons: 36px (`h-9`), radius 10px. Filter pills: fully rounded, px-3.5
  py-1.5.
- Buttons: radius 12px; primary h-44px; secondary same; small 36px/10px.
- Inputs: 44px, radius 12px (see Forms).
- Sequence circles: 36px; avatar circles: 36–44px; metric icon discs: 44px
  round.

### Core Palette (canonical values)
Surfaces & text:
| Token | Value | Use |
|---|---|---|
| canvas | `#F8F9FC` | app background |
| surface | `#FFFFFF` | cards, sidebar, topbar inputs |
| surface-muted | `#FBFBFD` | subtle inner surfaces |
| ink | `#15172B` | primary text |
| secondary | `#667085` | secondary text, labels |
| muted | `#98A2B3` | placeholder/meta text |
| line | `#E7E9F1` | borders, hairlines |
| line-soft | `#F1F2F7` | dividers, skeleton fill |

Primary purple:
| Token | Value | Use |
|---|---|---|
| primary | `#6D4AFF` | primary buttons, active nav accents, focus ring |
| primary-strong | `#5B3AE0` | primary hover |
| primary-text | `#6846E8` | purple text on soft backgrounds (links, badges) |
| primary-soft | `#F1EDFF` | purple tint surface (badges, active nav, selected rows) |
| primary-hover | `#F6F5FB` | subtle hover surface for nav/rows |

Semantic accents (solid / soft surface / accessible text where needed):
| Family | Solid | Soft | Text |
|---|---|---|---|
| Blue | `#3478F6` | `#EDF4FF` | — |
| Pink (danger) | `#F43F8C` | `#FFF0F6` | — |
| Orange (warning) | `#F59E0B` | `#FFF6E8` | `#B45309` |
| Teal (success) | `#12B886` | `#EAFBF5` | `#0E9F73` |

Brand mark gradient: `#8B6DFF → #6D4AFF` (also used for avatars).
Login background: radial gradient `circle at 10% 10%`: `#F1EDFF 0% →
#F8F9FC 42% → #EDF4FF 100%`.
One-off: queue sidebar badge count `#EFECFB` bg / `#6846E8` text.

### Shadows
| Token | Value | Use |
|---|---|---|
| card | `0 4px 18px rgba(31,35,55,0.045)` | cards, inputs, white chips |
| card-hover | `0 8px 26px rgba(31,35,55,0.08)` | hover lift on cards/tiles |
| elevated | `0 10px 35px rgba(31,35,55,0.08)` | dropdown menus, mobile sidebar |
| primary | `0 6px 18px rgba(109,74,255,0.28)` | primary buttons, active filter pill |

### Card Grammar
White surface, 1px `#E7E9F1` border, radius 18px, shadow `card`, padding
20px. Title bar: 15px bold ink title at top-left, optional action link
top-right (`12.5px` semibold `primary-text` with arrow icon). Hover (where
interactive): shadow grows to `card-hover` and the card lifts 1px. Rows
inside lists are divided by `line-soft` hairlines, not boxed.

### Button Hierarchy
1. **Primary** — h-11, radius 12, bg primary, white 13.5px semibold text,
   shadow-primary, hover → primary-strong, press → scale 0.98. Example
   labels: "Register patient", "Complete triage", "Sign consultation", "Post
   payment", "Check in patient".
2. **Secondary** — h-11, radius 12, white bg, 1px line border, ink text,
   card shadow, hover → surface-muted. Example: "Go to patients", "Cancel",
   "Print receipt" (with printer icon).
3. **Small secondary (action)** — h-9, radius 10, same styling. Examples:
   "Select"/"Selected", "Claim", "Open", "Collect".
4. **Link** — text-only, 12.5px semibold `primary-text`, hover darker.
   Examples: "View all →", "Show more (N remaining)", "Change".
5. **Danger** — h-11, pink-soft bg, pink text (used for destructive intent;
   currently rare).
Disabled: 50% opacity, pointer-events none. Pending labels swap to gerunds:
"Registering…", "Recording…", "Signing…", "Posting…".

### Badge System
`StatusBadge`: pill (rounded-full), px-2.5 py-1, 10.5px semibold, soft
background + accessible text. Tones: amber, blue, purple, pink, teal,
neutral. Status → tone mapping in use:
- Queue: WAITING→amber "Waiting"; CALLED→blue "Called"; IN_TRIAGE→blue "In
  triage"; TRIAGED→purple "Ready for consultation"; IN_CONSULTATION→purple
  "In consultation"; COMPLETED→teal "Completed".
- Invoice: ISSUED→amber "Awaiting payment"; PARTIALLY_PAID→blue "Partially
  paid"; PAID→teal "Paid"; VOID→neutral "Void".
- Encounter chip: Open→purple; Signed→teal.
Sequence circles rotate through 5 tone pairs (purple, blue, pink, orange,
teal) by row index.

### Form System
- `Field`: label 12px semibold secondary, 6px gap, optional 11.5px medium
  muted hint below.
- `TextInput` / `Select`: h-11 (44px), radius 12, white bg, 1px line border,
  13px medium ink text, muted placeholder, card shadow; focus: 2px primary
  ring, transparent border. Selects have a custom muted chevron.
- `Textarea`: min-height 120px (consultation note 220px), same styling,
  resizable.
- Errors: `ErrorBanner` — pink-soft surface, radius 14, alert triangle icon
  (pink), 12.5px ink message, optional dismiss X. Inline field errors are
  not currently styled separately.
- Success: teal-soft strip with check-circle icon, same geometry.
- Focus everywhere: `focus-visible:ring-2 ring-primary ring-offset-2`.

### Icons
Inline SVG, Lucide-style outline: 24×24 viewBox, `fill=none`,
`stroke=currentColor`, stroke-width **1.8**, round caps/joins; rendered at
16–20px. Available set: Overview(grid), Patients(users), Queue(list),
Triage(heart-pulse), Consultation(stethoscope), Billing(receipt),
Search, UserPlus, CheckCircle, CheckIn, AlertTriangle, ArrowRight,
ChevronDown, ChevronRight, Menu, Dismiss(X), Logout, Facility(building),
Note, Calendar, Plus, Printer, Activity, TrendUp. The **BrandMark** is a
gradient rounded-cross glyph (40×40 viewBox; white center dot), never
replaced by text alone.

### Responsive Behavior
Verified at 1366×768, 1024×768, 768×1024:
- ≥1024px (lg): full 264px sidebar; two-column workspaces (list + panel,
  ratios like `1.55fr 1fr` or `1fr 1.35fr`); metric grid 4-up.
- 768–1023px (md): 76px icon rail (labels hidden); grids collapse to one
  column at xl-only breakpoints.
- <768px: topbar hamburger opens overlay sidebar with scrim
  (`ink/30` + 2px blur); search collapses; all grids single column.

### Motion
Subtle only: card/tile hover lift (-1px) with shadow growth (200ms);
button press scale 0.97–0.98; color transitions on nav/hovers (150–200ms);
pulsing skeletons while loading. No page transitions, no spinners-as-content,
no large animations. Respect this restraint.

---

## 12. Existing Shared UI Components

Real component inventory (`frontend/src/components/ui.tsx`,
`shell/AppShell.tsx`, `icons.tsx`):

| Component | Purpose | Visual pattern | Used in | Reuse conceptually |
|---|---|---|---|---|
| `AppShell` | page frame: fixed sidebar + sticky topbar + main | see Section 11 geometry | all authed pages | always wrap prototypes in this shell |
| `SidebarNav` (inside AppShell) | role-filtered nav | icon+label list, active = primary-soft bg + purple text + semibold; queue badge count | shell | copy for new modules |
| `FacilitySwitcher` | change active facility | bordered muted card, blue building icon disc, chevron; listbox dropdown (radius 14, elevated shadow) | sidebar | fixed |
| `TopBar` | search + user | 72px sticky; Ctrl+K patient search input (radius 14); avatar chip menu with name/role + "Sign out" | shell | fixed |
| `Button` | 5 variants | Section 11 | everywhere | exact reuse |
| `Card` / `CardTitleBar` | surface + titled header | Section 11 | everywhere | exact reuse |
| `PageHeader` | page title block | 26px bold title + 13.5px subtitle + right-aligned actions | every page | exact reuse |
| `MetricCard` | KPI tile | 44px round icon disc (5 tones) + 13px label + 24px bold value + hint; hover lift | Overview | reuse for new dashboards |
| `StatusBadge` + `queueStatusBadge`/`invoiceStatusBadge` | status pills | Section 11 | lists | exact reuse + extend mappings |
| `SequenceCircle` | queue number | 36px circle, rotating 5-tone pairs, 13px bold | queue/triage/consultation lists | exact reuse |
| `AvatarInitials` | user avatar | gradient circle, white initials | sidebar, topbar | exact reuse |
| `EmptyState` | empty/loading-zero state | centered, 48px primary-soft circle icon, 13.5px title, 12.5px hint, optional action button | all lists | exact reuse for every new list |
| `ErrorBanner` | inline errors | pink strip + triangle + dismiss | forms/lists | exact reuse |
| `UnauthorisedState` | permission denied | card + EmptyState naming required capability | gated pages | exact reuse |
| `LoadingSkeleton` / `CardSkeleton` / `MetricSkeleton` | loading states | pulsing `line-soft` blocks matching final layout | all lists/metrics | exact reuse |
| `Field` / `TextInput` / `Select` / `Textarea` | form primitives | Section 11 | all forms | exact reuse |
| `formatTime` / `formatDate` | locale time/date | "9:41 AM" / "Aug 21, 2026" | lists | reuse conventions |
| `BrandMark` | logo glyph | gradient cross | sidebar, login | never change |
| `QueryProvider` / `SessionProvider` | data/session context (React) | invisible | app-wide | N/A for prototypes |

---

## 13. Current Page UX

### Login (`/login`)
- Goal: sign in; communicate brand.
- Layout: full-screen radial gradient; centered 440px card (radius 22,
  elevated shadow): BrandMark + KLINKLIK + descriptor; eyebrow "CLINIC
  OPERATIONS"; "Welcome back"; three fields (Username, Password,
  Organisation ID with hint); primary "Sign in"; local demo hint line.
- Actions: sign in → role landing route.
- Limitations: no "forgot password" (not a feature — do not invent
  flows that imply email recovery exists); organisation ID field is a UUID
  paste in real deployments.
- Preserve: composition, gradient, single-card focus.
- Could evolve: language selector (future), facility selection post-login
  (currently first facility is auto-selected).

### Overview (`/overview`)
- Goal: orient the user; surface today's load and next action.
- Layout: PageHeader with time-based greeting ("Good morning/afternoon/
  evening, {first name}"), facility subtitle, date chip, role CTA button;
  4 MetricCards (Active queue, Awaiting triage, Ready for consultation /
  With clinician — capability-dependent label, Awaiting payment or In
  consultation); two-column: "Today's Queue" card (top 6 entries, "View
  full queue" link) + "Quick Actions" tile grid (role-dependent 2–5 tiles:
  Register Patient, Check-in Patient, Triage Queue, New Consultation,
  Collect Payment, View Queue).
- Limitations: metrics are live counts only (no trends — trend icons exist
  but data doesn't); no per-department breakdown.
- Preserve: greeting pattern, metric row, queue preview + quick actions
  structure.
- Could evolve: richer admin metrics, department filter, day-over-day
  deltas.

### Patients (`/patients`, `?q=`)
- Goal: find/register a patient; start the visit.
- Layout: two columns (1.55fr/1fr). Left: search field (debounced 350ms),
  success/error strips, results list (name, patient_no, sex, phone; Select
  buttons; capped at 8 shown with "Showing 8 of N matches" note), Register
  patient form (First name, Last name, Phone, Sex). Right: sticky Selected
  patient card — identity summary (initial disc, name, number, sex, age from
  DOB, phone), Check-in department select, "Check in patient" primary
  button, link to queue; or "View-only access" badge / empty state.
- Limitations: no pagination beyond 100-row server cap; no patient detail
  page or visit history; identifiers/contacts/links not editable in UI;
  duplicate-linking has API but no UI.
- Preserve: search-first pattern, selected-patient side panel, check-in
  semantics.
- Could evolve: patient profile page with timeline (visits, triage, notes,
  invoices), identifier capture at registration, duplicate review queue.

### Queue (`/queue`)
- Goal: operational oversight of today's queue.
- Layout: header + inline filter input ("Filter by patient, label,
  department…" — client-side); status filter pills (All, Awaiting triage,
  In triage, Ready, In consultation); single card list (SequenceCircle,
  name, label · department · stage, status badge + arrival time, per-row
  Claim [only WAITING + capability] and Open buttons → deep links to
  /triage or /consultations with `?entry=`); "Show more (N remaining)"
  after 10 rows.
- Limitations: no COMPLETED/CANCELLED view; no reordering or priority
  display (acuity is not shown on the queue — a known gap); no per-stage
  timing.
- Preserve: pill + filter pattern, scannable rows, claim/open actions.
- Could evolve: acuity indicator column, wait-time column, completed
  history toggle.

### Triage (`/triage`)
- Goal: record first observations quickly.
- Layout: two columns (1fr/1.35fr). Left: "Awaiting triage (N)" list of
  WAITING/CALLED entries (selectable rows, active = primary-soft). Right:
  "Triage record" — patient summary strip (sequence circle, name, label ·
  department · Arrived time); Chief complaint textarea; grid of Priority
  (Routine/Urgent/Emergency), Pulse (bpm), Temperature (°C), Systolic BP,
  Diastolic BP; "Complete triage" primary button; footnote "Priority is
  nurse-assigned. The system does not compute acuity."
- Limitations: no acuity highlighting of urgent/emergency patients in the
  list; vitals limited to 5 fields in UI (model supports more); no triage
  history view.
- Preserve: two-pane select-then-record pattern, the acuity disclaimer.
- Could evolve: emergency/urgent visual prominence, full vitals set (SpO2,
  respiratory rate, weight/height), previous-visit triage context.

### Consultations (`/consultations`)
- Goal: focused clinician workspace: see triaged patients, document, sign.
- Layout: two columns (1fr/1.35fr). Left: "Ready for consultation (N)" list
  of TRIAGED/IN_CONSULTATION entries. Right: "Consultation" card — patient
  summary strip + encounter chip (ENC no · Open/Signed); if no encounter:
  explanation + "Start encounter"; if open: Consultation note textarea
  (pre-seeded "Assessment: \nPlan: "), "Sign consultation" → confirmation
  strip (orange warning "Signing finalises this note…", Cancel / Confirm
  signature); if signed: teal immutability banner, read-only note block,
  then either "Create invoice" link (billing capability) or handoff note to
  cashier.
- Limitations: **this is the shallowest part of the product** — one
  free-text note; no structured history/exam/diagnosis; no link to triage
  data in the panel; no patient context (age, allergies); no lab loop; no
  prescriptions.
- Preserve: ready-list pattern, two-step signing with explicit finality
  warning, signed = locked presentation.
- Could evolve: THIS is Qwen's primary canvas (Section 20) — richer
  clerking layout, investigation ordering, results review, prescription
  writing, all within this shell.

### Billing / Cashier (`/billing`)
- Goal: find unpaid invoices, create invoices, collect payments, receipts.
- Layout: two columns (1.35fr/1fr). Left: "Awaiting payment (N)" card with
  search ("Find by invoice number, patient name, or patient number…"),
  invoice rows (INV no · patient, Issued date · Total, status badge +
  Balance, Collect button) + "New invoice" card (patient search listbox,
  selected-patient confirmation with Change, Service select with price,
  Create invoice). Right (sticky): "Collect payment" — invoice summary
  (numbers, total/paid/balance), itemized list, Amount + Method + optional
  Reference fields, "Post payment"; after payment a **Receipt** card
  (data-print-sheet): organisation/facility name, hairlines, definition list
  (Receipt no, Invoice, Patient, Amount, Method, Reference, Invoice
  balance), footer "Thank you. This receipt was issued by KlinKlik.",
  "Print receipt" (prints only the sheet), "Done — collect another payment".
- Limitations: UI creates single-service quantity-1 invoices (API supports
  multi-item/quantity/discount); no partial-payment plan UI (it works but is
  not surfaced beyond the amount field); no void/refund UI; no shift
  management (model exists).
- Preserve: awaiting-payment lookup as the cashier's home, receipt layout
  and print behavior.
- Could evolve: multi-line invoice builder, discounts, refunds/void flows,
  shift open/close summary, MoMo reference capture patterns.

### Receipt
- Covered under Billing above; treat the printed sheet layout as frozen
  (numbering, fields, and integrity rules are not decorative).

---

## 14. Current Demo Data

Synthetic development context — safe and useful for realistic prototypes.

- Organisation: **Kampala Medical Centre** (slug `clinicopus-demo` — internal).
- Facility: **Main Branch** (code `MAIN`, mode CLINIC).
- Departments: Reception (`RECEPTION`), Outpatient (`OPD`), Triage
  (`TRIAGE`), Billing (`BILLING`).
- Demo staff accounts (usernames only — no credentials in this document):
  `admin@clinicopus.local` (Amina Administrator, OWNER_ADMIN),
  `reception@clinicopus.local` (Ruth Reception),
  `nurse@clinicopus.local` (Nabirye Nurse),
  `doctor@clinicopus.local` (David Clinician),
  `cashier@clinicopus.local` (Grace Cashier),
  plus a `demo` superuser account.
- Example patients: **Sarah Nakato** (`DEMO-0001`, female, 0700000101),
  **Peter Okello** (`DEMO-0002`, male, 0700000102), **Grace Namusose**
  (`DEMO-0003`, female, 0700000103). Address field: "Synthetic development
  record".
- Service catalogue: **General consultation** (code `CONSULTATION`,
  category CLINIC) at **UGX 30,000.00**.
- Identifier formats (real, generated at runtime):
  - Patient numbers: `P-XXXXXXXX` (8 random uppercase alphanumerics), e.g.
    `P-4KX92A7Q`. Seeded demo patients use `DEMO-000N`.
  - Queue labels: `{DEPT}-{sequence:03d}`, e.g. **`OPD-004`** (per facility
    per day).
  - Encounters: `ENC-XXXXXXXXXX` (10 random uppercase alphanumerics).
  - Invoices: `INV-XXXXXXXXXX`.
  - Receipts: `RCT-XXXXXXXXXX`.
- Currency rendering: `UGX 30000` / totals like `UGX 30000.00`.
- Visits: walk-in (`WALK_IN`) is the only visit type surfaced.

Do not include passwords, tokens, secrets, or database credentials anywhere
in prototypes; Qwen does not need them.

---

## 15. Current Permission / Handoff Matrix

Reflects ACTUAL current implementation.

| Role | Can see | Can do | Cannot do | Hands off to |
|---|---|---|---|---|
| Admin (OWNER_ADMIN) | everything | all actions in scope | staff/permission management UI (capabilities exist, no UI) | — (oversight) |
| Reception | patients, queue, invoices | search/register/edit patients, check in, create invoices, take payments, print receipts | triage, consultation notes | → Nurse (via queue status WAITING) |
| Nurse | patients, queue, triage workspace | claim entries, record triage | consultation notes, billing | → Doctor (queue becomes TRIAGED) |
| Clinician | patients, queue, consultations | claim, start encounter, write note, sign, amend (API) | create invoices in UI (sees handoff message instead) | → Billing/Cashier (encounter SIGNED) |
| Cashier | patients, queue, unpaid invoices | invoice lookup (cross-user), create invoices, post payments, print receipts | triage, consultation notes | → Receipt (terminal) |

Handoff mechanics today are queue-status-driven: each role's workspace list
shows only the statuses relevant to them (nurse: WAITING/CALLED; clinician:
TRIAGED/IN_CONSULTATION; cashier: ISSUED/PARTIALLY_PAID invoices). There are
no notifications; staff poll their lists.

---

## 16. Current Safety / Integrity Rules

UX-relevant safety behavior already implemented — your prototypes must not
visually contradict these:

- **Server permissions are authoritative.** Frontend gates are UX only.
  Unauthorised pages show the UnauthorisedState card, not fake access.
- **Cross-tenant/cross-facility access returns 404** ("not found", not
  "forbidden" — no existence leak). Error banners surface the server's
  human-readable `detail` messages.
- **Signed clinical notes are immutable.** Signed consultations display a
  locked presentation with a teal immutability banner; signing uses an
  explicit two-step confirmation warning that it cannot be edited afterward.
- **Amendments, not edits.** Corrections to signed notes create a new
  recorded version with a mandatory reason (API exists; UI pending — a good
  design opportunity).
- **Concurrency:** every GET carries an ETag; patient demographic edits
  require `If-Match` (missing → 428 "precondition required"; stale → 412
  "record changed; refresh"). Design conflict prompts accordingly.
- **Idempotency:** mutations can carry an `Idempotency-Key`; retries replay
  the original response instead of double-charging/double-creating. Payment
  double-submission protection exists at the transport layer.
- **Money integrity:** payments cannot exceed the invoice balance; invoice
  totals are server-computed from the priced catalogue (staff cannot type
  arbitrary prices); receipts get unique `RCT-` numbers.
- **Audit:** every significant action (create/update/sign/amend/link/
  payment/login/logout/export) is written to an append-only audit log.
  Nothing is silently deleted — patients are ARCHIVED, clinical/financial
  records are never destroyed.
- **Pharmacy-specific rules (no expiry override, controlled-drug blocks) are
  NOT implemented yet** because pharmacy is not built. Do not show expiry
  warnings or controlled-substance gates as if they exist; they are future
  design subjects.
- **Session security:** the access token lives only in memory (never
  localStorage/sessionStorage — verified by tests); the refresh token is an
  httpOnly rotating cookie; refresh re-establishes the session silently.
  Do not design "remember me" token flows or visible token handling.
- **Facility context:** the active facility scopes every request
  (`X-Facility-Id`); the switcher is prominent in the sidebar.
- **PHI discipline:** no patient data in URLs beyond ids already used, no
  patient charts in localStorage, print sheets exclude the app shell.

Visible UX treatments these REQUIRE: locked/final styling for signed notes;
conflict prompts (412) on stale edits; honest 404/403 messaging; receipt
print isolation; amendment flows that demand a reason.

---

## 17. What Is NOT Implemented Yet

Classification legend: **EXISTS** (working, tested) / **PARTIAL** (model or
API exists, incomplete UX or scope) / **NOT IMPLEMENTED** (nothing user-facing).

| Area | Status | Detail |
|---|---|---|
| Patient registry, search, register, check-in | EXISTS | Sections 7, 10 |
| Queue management + status filters + claim | EXISTS | |
| Triage (acuity, complaint, 5 vitals fields) | EXISTS | model supports 8 vitals fields |
| Encounter start + consultation note + sign | EXISTS | free-text note only |
| Note amendment | PARTIAL | API + version model exist; NO UI |
| Full clinician clerking (structured Hx/exam/dx) | NOT IMPLEMENTED | one textarea today |
| Diagnosis workflow (coded/structured) | NOT IMPLEMENTED | Diagnosis model exists, no API/UI |
| Allergies / procedures / referrals capture | NOT IMPLEMENTED | models exist, no API/UI |
| Laboratory (orders, work queue, results) | NOT IMPLEMENTED | empty `laboratory` app scaffold |
| Investigation ordering from consultation | NOT IMPLEMENTED | |
| Doctor resume-after-results | NOT IMPLEMENTED | no awaiting-results states |
| Prescription writing | NOT IMPLEMENTED | |
| Pharmacy (stock, dispensing) | NOT IMPLEMENTED | empty `pharmacy` app scaffold |
| Inventory / medicines catalogue / expiry control | NOT IMPLEMENTED | empty `inventory` scaffold |
| ANC / maternity | NOT IMPLEMENTED | empty `maternity` scaffold |
| Appointments | PARTIAL | model (+ BOOKED/CHECKED_IN/COMPLETED/CANCELLED/NO_SHOW) and module flag exist; NO API or UI |
| Reports | NOT IMPLEMENTED | empty `reporting` scaffold (module flag exists) |
| Notifications (in-app), SMS, WhatsApp | NOT IMPLEMENTED | |
| Mobile money (MoMo) integration | PARTIAL | MOBILE_MONEY is a valid payment *method* with a reference field; no gateway integration |
| Staff/role administration UI | NOT IMPLEMENTED | `staff.permission.grant` + `audit.log.view` capabilities exist; no UI |
| Audit log viewer | NOT IMPLEMENTED | events recorded; no UI |
| Cashier shifts | PARTIAL | CashierShift model (OPEN/CLOSED, float, declared cash); no API/UI |
| Patient identifiers at registration | PARTIAL | API supports identifier capture; UI omits the field |
| Patient duplicate linking | PARTIAL | API exists; no UI |
| Consents capture | NOT IMPLEMENTED | model only |
| User credentials (licence numbers) | PARTIAL | model + seed data; no UI |
| Print/reprint past receipts | PARTIAL | receipt endpoint exists (latest payment per invoice); no receipt archive UI |

Do not infer more than this table. When a story needs a NOT IMPLEMENTED
area, that is a design target — clearly a new surface, not an existing one.

---

## 18. Known UX / Product Gaps

**FUNCTIONAL gaps**
- Doctor workflow is too shallow: one free-text note; no structured
  history/exam/diagnosis; no patient context (age, allergies, prior visits)
  beside the note.
- No investigation loop: cannot order labs, no awaiting-results state, no
  results review, doctor cannot "resume" a consultation after results.
- No prescription → pharmacy → dispensing path at all.
- No appointments: walk-in queue only; the module flag and model exist.
- No notifications: handoffs rely on staff refreshing their lists.
- Billing UI is single-service/quantity-1 (API is richer); no refunds/voids.
- No amendment UI despite the API being ready.
- No staff administration or audit viewer for the OWNER_ADMIN.

**VISUAL gaps**
- Queue rows do not show acuity — an EMERGENCY triage patient looks like a
  routine one in the list (high-value fix).
- No wait-time/stage-duration indicators.
- No patient profile page — the registry has no "open patient" destination.
- Overview metrics lack trend context (icons suggest it; data doesn't).

**DOMAIN gaps**
- Triage acuity does not influence queue ordering or visibility anywhere.
- ANC workflow unresolved (blueprint scope, future).
- PaymentAllocation multi-invoice semantics exist in the model but not in UX.
- Cashier shift reconciliation is modeled but absent.

Any additional friction discovered during browser review (e.g. search
matching below) should be treated as known context, not new invention.

**Search behavior to design around (real, current):** patient search matches
individual fields (first name OR last name OR phone OR patient number), not
concatenated full names — "Nakato" works, "Sarah Nakato" may not. Invoice
search matches invoice number, patient number, or first/last name
individually. Prototype search hints should set that expectation until the
backend changes.

---

## 19. Frozen UX Elements — QWEN MUST PRESERVE

- **KlinKlik wordmark placement**: sidebar header (BrandMark + "KLINKLIK" +
  "Clinic Management System") and login card; receipt footer line "Thank
  you. This receipt was issued by KlinKlik."
- **Light theme only**; **Inter**; base 14px body.
- **Purple primary accent** (#6D4AFF family) and the semantic accent family
  (blue/pink/orange/teal with soft surfaces) exactly as specified in
  Section 11.
- **Sidebar architecture**: 264px/76px rail, header 76px, nav item grammar
  (icon + label, active = primary-soft + purple), queue badge, facility
  switcher + user card + logout at the bottom.
- **Topbar architecture**: 72px sticky, menu button (mobile), patient search
  with Ctrl+K hint, avatar chip with name/role menu.
- **Card grammar, button hierarchy, badge grammar, form system, focus
  rings** (Sections 11–12) — reuse, do not restyle.
- **Page-oriented routing** with role-aware landing and capability-gated
  navigation; UnauthorisedState pattern.
- **Role-specific workspaces** (a cashier's home is unpaid invoices; a
  nurse's home is the waiting list; a clinician's home is the ready list).
- **Spacing/density**: 20px gutters, 20px section rhythm, list-row hairline
  pattern, restrained motion.
- **Responsive philosophy**: three verified breakpoints and the md-rail /
  lg-full / mobile-overlay sidebar behavior.
- **Signed = locked** presentation and two-step signing confirmation.
- **Receipt print sheet** structure and isolation.

Qwen may NOT replace the design system with another visual identity, another
typeface, another palette, dark mode, or another shell layout. New
workflows live INSIDE this shell.

---

## 20. UX Areas Qwen MAY Redesign

Freedom is broad **inside the frozen shell** (Section 19):

- Contents of the consultation workspace: rich clerking layout (structured
  history, examination, assessment/plan), patient-context sidebar (demographics,
  allergies, prior visits, current triage), clinical documentation patterns.
- Investigation ordering UX: test catalogue picker, orders summary,
  "awaiting results" state design on the queue/consultation.
- Doctor → Lab → Doctor resume workflow: lab handoff, notification of ready
  results, results review layout, integrate-into-note patterns.
- Laboratory worklist and result entry screens (a new role workspace —
  follow the two-pane workspace character).
- Prescription UX: medication selection, dosage instructions, signing,
  transmission to pharmacy.
- Pharmacy work queue and dispensing flow (stock check, dispense
  confirmation, patient handover) — remembering expiry/controlled rules are
  future product decisions to surface, not invent details for.
- ANC/maternity workflows (per future stories).
- Future reports/dashboards and administration pages (staff, roles,
  capabilities, audit viewer) — MetricCard/PageHeader grammar applies.
- Refinements to existing pages that do not change working semantics
  (e.g. acuity display on the queue, patient profile page, amendment UI,
  appointment booking UI once stories approve).

Every new screen must: use the AppShell, the design tokens, the component
grammar, honest states (loading/empty/error/unauthorised), and label new
concepts as new.

---

## 21. Prototype Rules for Qwen

Produce **static prototypes** with:

- **Static HTML** files (one file per screen/state is fine).
- **Tailwind via the Play CDN** (`https://cdn.tailwindcss.com`), configured
  with the Section 11 tokens as custom theme values; otherwise use the exact
  hex values inline.
- **Inline SVG** icons in the Lucide style (24×24, stroke 1.8, currentColor)
  — no icon fonts, no external image assets. The BrandMark is the gradient
  cross glyph described in Section 11.
- **Minimal vanilla JS** only for state toggles (tabs, modals, list
  selection). No fake complex logic, no fake API calls, no persistence.
- **Inter** via a standard webfont link.
- **Synthetic data only**, using Section 14's demo context (Kampala Medical
  Centre, Sarah Nakato / OPD-004 / INV-… / RCT-… / UGX 30000, etc.). No real
  patient data. No credentials.

Model states and transitions explicitly: render each meaningful state
(loading, empty, populated, error, unauthorised, signed/locked, partially
paid, awaiting results …) so UX review can see them without a backend.

The prototypes are a **HARD VISUAL SPECIFICATION**: Luna/GLM (the
implementation agent) will later translate them into the real Next.js app
component-for-component. Precision beats flourish.

---

## 22. Handoff Constraints for Production Implementation

Qwen must NOT redefine (they are settled architecture, enforced by tests):

- Organisation tenancy and the Organisation → Facility → Department
  hierarchy; facility scoping of all work.
- Server-authoritative permissions and the capability model (15 codes).
- The authentication model (in-memory access token, rotating httpOnly
  refresh cookie, organisation-scoped login).
- Row-level tenant isolation and fail-closed behavior (cross-tenant =
  404).
- The append-only audit trail.
- Immutable final clinical records: signed notes, versioning, amendment
  semantics; never destructive edits of clinical history.
- Invoice/payment/receipt integrity: server-computed totals, balance
  validation, unique receipt numbers, PaymentAllocation semantics.
- Patient identity concepts: organisation-unique patient numbers,
  identifiers, duplicate links.
- The working reception→triage→consultation→billing→cashier flow, unless an
  approved story explicitly supersedes a part of it.
- Queue semantics: per-department daily sequence and `DEPT-###` labels,
  status machine values.

If a story seems to require changing one of these, prototype the UX and
**flag the conflict explicitly** in the prototype notes instead of quietly
assuming a change.

---

## 23. Current Test Coverage / Proven Behavior

What is already verified working (as of the latest runs):

- **Backend (PostgreSQL, as the non-privileged app role):** the full pytest
  suite passes against PostgreSQL — including auth bootstrap isolation,
  API hardening (ETag/If-Match, idempotency), audit immutability,
  concurrency (claim races), the clinic vertical slice, and
  roles/capabilities + invoice/queue lookup filters (24 tests on PG;
  additional SQLite suites for the same code).
- **RLS verification:** a `check_rls` command confirms all 37
  organisation-scoped tables have ENABLE + FORCE row-level security and the
  tenant-isolation policy; the app role is neither superuser nor bypassrls;
  missing tenant context fails closed; cross-organisation reads return
  nothing for patients, queue (including multi-status filters), and
  invoices.
- **Browser (Playwright, real browsers):** the full slice works —
  login → register patient → check-in → triage → consultation sign →
  invoice → payment → receipt (`RCT-` printed); the **cross-role handoff**
  test logs in reception, nurse, doctor, and cashier as four separate
  sessions in sequence and proves the cashier finds and settles the invoice
  created by reception; wrong-password and permission failures behave;
  refresh-cookie persistence restores sessions; a web-storage audit asserts
  no tokens leak into localStorage/sessionStorage; responsive screenshots
  at 1366×768, 1024×768, 768×1024.
- **Design fidelity:** computed-style comparison against the approved
  reference verified sidebar width, topbar height, card radius, palette,
  and button geometry match.

Implication for Qwen: these behaviors already work and must not be visually
redesigned into contradictory flows (e.g. do not "simplify" away the signing
confirmation or the receipt sheet).

---

## 24. Recommended Qwen Prototype Sequence

Design in dependency order; each batch builds on the previous shell
vocabulary:

1. **BATCH 1 — Refine what exists.** Patient profile page (timeline of
   visits/triage/notes/invoices); acuity + wait-time on the queue;
   amendment UI for signed notes; appointment booking UI (stories
   permitting). Low risk; validates the shell grammar with Luna.
2. **BATCH 2 — Doctor clerking.** Rich consultation workspace: structured
   note sections, patient context panel, diagnosis capture. Depends on:
   nothing; unlocks 3–4.
3. **BATCH 3 — Doctor → Lab → Doctor.** Investigation ordering from the
   consultation, lab worklist (new role), result entry/release, results
   review, "resume consultation" and awaiting-results queue states.
   Depends on: 2 (clerking layout hosts orders/results).
4. **BATCH 4 — Prescription → Pharmacy → Dispensing.** Prescription authoring
   in the consultation, pharmacy work queue, dispense confirmation.
   Depends on: 2 (prescriptions originate in consultations); interacts
   with future inventory concepts.
5. **BATCH 5 — Billing/cashier refinements.** Multi-line invoices,
   discounts, partial-payment plans, void/refund corrections, shift
   open/close and reconciliation.
6. **BATCH 6 — ANC / maternity.** Antenatal visit workflows per future
   stories. Independent of 2–4 but reuses the workspace grammar.
7. **BATCH 7 — Administration/reports/settings.** Staff & role management,
   capability grant screens, audit viewer, operational reports.

Each batch should deliver: primary screen, key states (loading/empty/error/
unauthorised), the state-transition variants, and mobile/tablet layouts.

---

## 25. Glossary

- **Organisation** — the tenant root; owns facilities, users, currency,
  and all data. Example: Kampala Medical Centre.
- **Facility** — a branch of an organisation (e.g. Main Branch); the scope
  of every working screen.
- **Department** — a sub-unit of a facility (Reception, OPD, Triage,
  Billing); issues daily queue numbers.
- **Module** — a per-facility feature flag (Patients, Reception, Queue,
  Triage, Consultation, Billing, Appointments, Reporting).
- **Patient** — a person in the organisation's registry.
- **Patient Number** — organisation-unique identifier, format `P-XXXXXXXX`.
- **Encounter** — one clinical visit; `ENC-` reference; ties queue entry,
  note, and invoices together.
- **Queue Entry** — a patient's place in a facility's queue for one day;
  label `DEPT-###`.
- **Triage** — nurse-recorded first assessment: acuity
  (Routine/Urgent/Emergency), chief complaint, vitals.
- **Clinical Note** — the consultation documentation; DRAFT → SIGNED →
  (AMENDED).
- **Service** — a billable catalogue item with a facility price (General
  consultation, UGX 30000).
- **Invoice** — bill for a patient/encounter; `INV-` reference; ISSUED →
  PARTIALLY_PAID/PAID.
- **Payment** — money received against an invoice; method Cash/Mobile
  money/Card/Bank.
- **Payment Allocation** — the record tying a payment amount to a specific
  invoice.
- **Receipt** — printed proof of payment; `RCT-` reference.
- **Signed** — final and immutable; corrections require an amendment.
- **Amended** — a signed record corrected via a new recorded version with a
  mandatory reason.
- **Capability** — a server-defined permission code (e.g.
  `triage.record`) attached to roles; the frontend only mirrors it.
- FUTURE: **Lab Order** (investigation request from a consultation),
  **Prescription** (medication order authored by a clinician), **Dispense**
  (pharmacy release of prescribed medication).

---

## 26. Final Qwen Instructions

> You are extending the approved KlinKlik product, not inventing a
> replacement.
>
> The user-story backlog tells you WHAT users must accomplish.
> This handoff tells you WHAT ALREADY EXISTS.
> The approved design system tells you HOW KLINKLIK LOOKS.
>
> Preserve all approved shell/design patterns (Section 19).
> Design missing workflows inside them (Section 20).
> Use the exact statuses, identifiers, and roles documented here — never
> invent state names that the backend does not have, and clearly mark new
> concepts that require production implementation.
> Never silently invent backend behavior. When a story requires behavior not
> currently implemented, prototype the UX clearly and flag the new concept
> for production implementation.
>
> Ship static HTML + Tailwind + inline SVG + minimal vanilla JS, with every
> meaningful state rendered, using only synthetic demo data.
