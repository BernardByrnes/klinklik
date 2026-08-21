# Clinicopus Blueprint Review

## Decision summary

**Verdict: REVISE THEN FREEZE**

The blueprint has a strong product direction and several unusually good architectural instincts: one healthcare operations platform, organisation-to-facility tenancy, a longitudinal ANC episode, an append-only stock ledger, immutable clinical and financial history, manual Mobile Money records, role-specific workspaces, and a conservative offline boundary.

It is not yet safe to designate it the Canonical Product Blueprint v1.0. The problem is not that the blueprint lacks detail. The problem is that the detail currently hides several incompatible scope decisions and a few unsafe escape hatches.

The minimum revision is:

1. Move minimal direct goods receiving into V1.0.
2. Move basic physical stock counting and controlled reconciliation into V1.0.
3. Move a deliberately simple appointment/follow-up capability into V1.0.
4. Explicitly exclude controlled/Class A medicines from the baseline V1 unless a pharmacist and regulatory advisor approve a complete controlled-drug workflow.
5. Remove every expired-stock sale or dispensing override.
6. Make regulatory minimums non-disableable; facility configuration may only add stricter rules.
7. Separate workflow reminders from clinical interpretation and version every clinical rule that survives validation.
8. Reduce the V1 implementation surface and treat the five-to-six-month estimate as, at most, an engineering alpha estimate rather than a pilot-ready commitment.
9. Resolve data-residency, ANC, pharmacy, HMIS, and financial-regulatory questions before general availability.

The recommended architecture remains a modular Django/PostgreSQL monolith with a Next.js client application. No microservices redesign is warranted.

## Review basis and limitation

Primary source reviewed: K:/new/clinicopus.md.

The supplied source file begins at section 38.3 and contains sections 38.3–99 plus the recommended product baseline. It refers to earlier sections such as 8, 11, 20–38, and 48, but those sections are not present in the supplied file. Findings that depend on those omitted sections are therefore treated as risks or open questions, not as confirmed defects.

The attached review brief was also used as the governing product context. It explicitly keeps ANC in V1, keeps the organisation → facility → modules direction, targets Ugandan private outpatient clinics and small pharmacies, and rejects early dependence on expensive integrations.

This is a product, architecture, safety, and delivery review. It is not a legal opinion, clinical guideline, pharmacist practice standard, or regulatory approval.

## Scorecard

| Area | Score | Assessment |
| --- | ---: | --- |
| Product vision | 8.5/10 | Clear, coherent platform direction for clinic, pharmacy, and combined facilities. |
| V1 scope discipline | 5.0/10 | The split is a useful idea, but the actual V1.0 boundary contradicts the operating model. |
| Clinic workflows | 7.0/10 | Good outpatient spine; needs thinner first-contact workflows and a clearer minimum service path. |
| ANC architecture | 8.0/10 | The pregnancy episode and contact model are right; clinical rules and midwife ergonomics remain high risk. |
| Pharmacy architecture | 8.0/10 | FEFO, batches, traceability, and dispensing transactions are strong; receiving and controlled medicines are unresolved. |
| Inventory architecture | 8.5/10 | Append-only movements and reconciliation are excellent; the location/batch balance model needs correction. |
| Finance and billing | 7.5/10 | PaymentAllocation and immutable corrections are worth keeping; two billing modes and fiscal assumptions add avoidable scope. |
| UX | 6.5/10 | Role dashboards are thoughtful, but the screen inventory and form surface are too large for the team and the target user. |
| Security and privacy | 7.5/10 | Strong baseline, but RLS operations, data residency, and support/recovery controls need proof rather than prose. |
| Technical architecture | 8.0/10 | Appropriate modular monolith and REST choices; several enterprise controls can be staged. |
| Implementation realism | 4.5/10 | Five to six months for a pilot-ready integrated product is not a credible default assumption. |
| Uganda relevance | 7.5/10 | Manual Mobile Money, printing, low-bandwidth behavior, and ANC fit the market; controlled-drug and regulatory validation are gaps. |
| Future extensibility | 8.0/10 | Good forward-compatible patterns, with some premature generalisation and stubs. |
| **Overall** | **7.0/10** | Strong foundation; not ready to freeze without the boundary and safety revisions above. |

# 1. What is excellent and should remain unchanged

## 1.1 Product direction

Keep the product as one Healthcare Operations Platform:

    Organisation
        ↓
    Facility / Branch
        ↓
    Enabled modules

The facility modes CLINIC, PHARMACY, and CLINIC + PHARMACY are commercially and operationally correct. Separate clinic and pharmacy applications would duplicate patients, payments, staff, and support work, and would make the prescription-to-dispense path worse.

## 1.2 Longitudinal ANC

Keep Patient → PregnancyEpisode → ANCContact → PregnancyOutcome as the core model. The blueprint is right to reject a generic consultation_type = ANC shortcut.

Keep:

- one active pregnancy episode per patient;
- recorded dating method and EDD revisions;
- scheduled contact templates;
- an intervention ledger;
- investigation and prescription links;
- an ANC-specific summary and printable card;
- a separated, permission-gated sensitive section;
- a path to postnatal and newborn records.

The source’s late-booking concept is also directionally right: the system should combine due goals for a late booker, while preserving the actual booking gestation and the reason for the schedule.

## 1.3 Pharmacy and stock integrity

Keep:

- MedicineDefinition separated from stockable Product;
- product batches with expiry and acquisition cost;
- FEFO proposals;
- exact batch-level consumption;
- no direct user editing of on-hand quantities;
- append-only StockMovement records;
- quarantine as a real stock location;
- recall traceability;
- atomic sale/dispense transactions;
- idempotency and row locking;
- a pharmacist-controlled return-to-resale decision.

The statement in section 45 that stock has no other mutation path should remain a non-negotiable design rule.

## 1.4 Financial primitives

Keep Invoice, InvoiceItem, Payment, PaymentAllocation, Refund, CreditNote, and CashierShift as separate concepts.

PaymentAllocation is not needless enterprise complexity. It supports split tender, partial payment, deposits, payment against several invoices, and overpayment without corrupting invoice balances. It is cheaper to keep the right abstraction now than to rewrite every balance calculation later.

Keep immutable finalised invoices and reversal documents rather than edits. Keep manual Mobile Money reference entry and reconciliation exports in V1.

## 1.5 Role and workspace model

Keep one User with multiple roles, facility scope, department scope where needed, credentials, and server-side permissions. The examples of a receptionist who is also a cashier, a nurse who is also a lab technician, and an owner who is also a doctor are realistic.

Keep role-resolved landing workspaces. A cashier should land in POS or payments, not in a hospital-sized sidebar.

## 1.6 Security fundamentals

Do not weaken:

- tenant isolation;
- server-authoritative authorization;
- privileged MFA;
- secure password storage and session revocation;
- fast user switching on shared devices;
- audit of clinical access and high-risk mutations;
- immutable clinical, financial, and stock history;
- no PHI in logs and error telemetry;
- encrypted private file storage;
- verified backups and restore tests;
- paper fallback workflows;
- no offline completion of stock, money, dispensing, or final clinical sign-off.

## 1.7 Technical direction

Keep:

- Next.js, React, TypeScript, TanStack Query, and a restrained component system;
- Django and Django REST Framework;
- PostgreSQL;
- Celery only where durable background work is needed;
- Docker and managed infrastructure;
- REST with explicit action endpoints;
- a modular monolith rather than microservices.

The stack is ordinary, maintainable, and appropriate for a modest team. A more fashionable stack would create migration risk without improving the customer outcome.

# 2. What is unnecessarily complex

The source often makes a good architectural concern sound like a V1 product requirement. The following should be staged or simplified.

| Source approach | Verdict | Recommended treatment |
| --- | --- | --- |
| Fourteen Django apps with strict one-way dependency rules | Useful boundary, not a launch requirement | Keep the conceptual domains; begin with fewer deployable concerns and split code when the boundaries are proven. |
| JWT access token plus rotating refresh cookie plus shared-device session pool | More moving parts than necessary | Prefer a secure same-origin session-cookie model for the first product. If a separate API requires access tokens, keep access tokens in memory only and use one refresh mechanism. |
| TOTP for every highly privileged permission and optional MFA for everyone | Directionally good, operationally heavy | Require MFA for owner/admin, permission grant, bulk export, refunds, and platform staff. Offer it to others; do not block every clinical worker on initial setup. |
| S3-compatible storage, ClamAV, image re-encoding, EXIF stripping, multiple document types | Security is important, but the V1 attachment surface is broad | V1: private object storage, allow-listed PDF/image files, malware scan, short-lived access. Defer DOCX/XLSX, browser camera capture, and sophisticated image pipelines unless pilots require them. |
| Domain event table plus outbound event bus before any integration exists | Premature | Use transactionally recorded domain events or an outbox only for proven needs. Do not build a general integration platform in V1. |
| Nightly materialised reporting tables for the first pilots | Likely premature | Use indexed OLTP queries, bounded date ranges, and cached daily summaries first. Add materialised reporting tables when measured query load justifies them. |
| Every report in on-screen, CSV, XLSX, and PDF form | Broad surface area | V1: screen, CSV, and print/PDF for the reports that owners actually use. Add XLSX where a pilot confirms it is needed; it is not a reason to build a warehouse. |
| Both UNIFIED and DEPARTMENTAL billing models in V1 | Two cash workflows before demand is known | Implement unified encounter billing plus a separate pharmacy sale. Keep department attribution in the model; defer independently payable departmental invoices. |
| Gapless invoice sequences described as EFRIS-compatible | Regulatory assumption, not architecture | Use non-reusable facility sequences with explicit void records. Make gapless fiscal numbering and EFRIS behavior a legal/tax decision before building it. |
| Full future-facing stubs for postnatal, newborn, FHIR, wholesale, and care-episode evolution | Some forward compatibility is useful; stubs can mislead | Keep stable IDs, foreign-key extension points, and the episode/contact pattern. Do not build empty tables or UI for capabilities with no validated V1 workflow. |
| Full support-access, customer health, export, retention, and platform-admin suites | Important governance, but not all needs to be polished before first pilot | Build minimum auditable support access, exports, backups, and deactivation before pilot. Defer dashboards and advanced self-service. |
| Twelve role templates plus a granular matrix editor visible to administrators | Correct underneath, overwhelming at the surface | Ship role templates and a small set of controlled add-ons. Hide advanced custom permissions behind an expert screen. |

The rule should be: preserve the architectural seam when it is cheap and prevents a rewrite; do not implement the future product inside V1.

# 3. Contradictions found

| Finding | Source approach | Verdict | Recommended change |
| --- | --- | --- | --- |
| Pharmacy cannot receive stock | Section 47 calls purchasing V1.1; section 84 says V1.0 can operate with opening stock, while its explanation says the receiving screen is in V1.0 | **Contradiction** | Direct goods receiving is V1.0. Purchase orders and procurement workflow are V1.1. |
| Physical stock cannot be reconciled | Section 45 forbids direct quantity edits; section 46 and section 84 defer counts to V1.1 | **Operational contradiction** | Basic count, variance reason, and controlled adjustment approval are V1.0. Blind/cycle/recount analytics are V1.1. |
| ANC needs appointments but appointments are V1.1 | Section 53 places appointments in V1.1, but ANC completion creates the next appointment and the user brief makes scheduling a V1 need | **Workflow contradiction** | Add a simple day-list appointment record to V1.0. Advanced calendar features remain deferred. |
| Expired stock is hard-blocked but a pharmacist can override it | Section 44.2 says sale is blocked, then describes pharmacy.dispense.override_expiry and the PHA-007 acceptance test permits it | **Safety contradiction** | Delete the override permission, endpoint, acceptance test, and related UI. Expired medicine is never saleable or dispensable in baseline V1. |
| V1 has dispensing registers but no controlled-drug path | Section 41 describes a general dispensing register; section 99 admits controlled-drug registers are not implemented | **Compliance contradiction** | Baseline V1 explicitly excludes controlled/Class A medicines. The product must block them rather than silently treating them as ordinary stock. |
| No clinical decision support but urgent clinical alerts exist | Section 84 excludes CDS, while section 56 includes critical lab alerts and post-term pregnancy ≥41w urgent notifications | **Safety contradiction** | Workflow events may be shown. Clinical urgency requires a validated, versioned rule and governance. Remove the default urgent classification for post-term and unverified lab thresholds. |
| Regulatory requirements are sometimes facility settings | Section 41 allows facility-configurable external prescription fields; other sections use permissions to override expiry or selling rules | **Governance contradiction** | Introduce non-disableable regulatory floors. Facility settings can add stricter requirements only. |
| Batch identity and location are conflated | Section 43 places location on Batch, while section 49 says a partial transfer preserves batch identity | **Model contradiction** | Separate lot identity from location balance: Batch/Lot identifies product, batch number, expiry, and cost; BatchLocationBalance holds quantity by location. |
| Allocation is authoritative but cached invoice balances are also stored | Section 51 stores amount_paid and balance, while section 52 defines balance from SUM(PaymentAllocation) | **Data-integrity risk** | Make allocation sums authoritative. If cached totals exist for speed, maintain them transactionally and assert invariants. |
| V1 report set includes purchasing reports before receiving is in V1 | Section 55 lists purchase history and supplier balances; section 84 says purchasing is V1.1 | **Scope contradiction** | V1.0 reports use direct receipts and stock movements. Supplier balances, PO reports, and purchasing analytics are V1.1. |
| Full source cannot be audited from the supplied file | The supplied file starts at section 38.3 but references earlier decisions as settled | **Review limitation** | Before freezing, assemble a single versioned canonical source and run the same consistency check across all sections. |

# 4. What is missing or too weak

## 4.1 The operational minimum

The source’s V1.0 is described as a product that can run a day, but a pharmacy cannot run for weeks on opening stock alone. The revised V1.0 must include:

- minimal supplier record;
- direct goods receipt without a purchase order;
- product, unit, batch, expiry, cost, quantity, and receiving user;
- receipt number and optional invoice/delivery-note reference;
- atomic positive stock movement;
- basic physical stock count;
- variance reason and controlled adjustment;
- quarantine and disposal register;
- simple appointments and follow-up dates.

These are not business-control luxuries. They are the minimum needed to keep the recorded world connected to the physical world.

## 4.2 Patient identity and continuity

The source correctly prioritises duplicate detection, but the baseline needs explicit handling for:

- an emergency or unknown patient with a temporary identity;
- a patient with no phone;
- a patient whose age is estimated;
- a patient found to be deceased;
- a patient moving between branches;
- duplicate linking versus irreversible merge;
- a failed or unavailable duplicate service;
- a patient who withdraws from a workflow without losing the draft.

V1 should support duplicate warning, safe linking, and a reviewed merge preview. A merge must not blindly repoint every clinical and financial foreign key in one opaque operation. Preserve the loser ID, source records, before/after mapping, and an audit trail; make the operation resumable and reversible at the logical mapping layer.

## 4.3 Pharmacy compliance

The blueprint needs a clear V1 product eligibility policy:

- target pharmacies must be licensed and have a named pharmacist or responsible professional;
- the pilot catalogue must be reviewed and classified;
- controlled medicines are excluded from the baseline;
- unknown regulatory classification cannot be silently treated as ordinary OTC stock;
- cold-chain products may be recorded only with an explicit limitation that temperature monitoring is not supported;
- expired, recalled, damaged, or returned-not-resalable stock cannot enter saleable stock;
- the dispensing register must be exportable and printable;
- product classification and required prescription status must not be made less strict by a facility administrator.

## 4.4 Data protection and operational governance

The source has a good list of privacy controls, but the product baseline must also include:

- a processor/controller responsibility model in customer contracts;
- a data processing agreement;
- a retention schedule approved by counsel, not merely a configurable number;
- a subject access/export process;
- an account closure and staff-leaver process;
- recovery and tenant-exit procedures;
- a breach evidence pack that can be generated without exposing audit payloads;
- a support-access procedure that works even if the customer cannot approve a request during an outage;
- a clear policy for customer-created attachments and deletion/tombstones.

Cross-border consent must not be treated as a universal answer. The PDPO’s public guidance describes due diligence for processing outside Uganda and provides an undertaking concerning storage and processing outside Uganda. Hosting, processors, backups, monitoring, email, error tracking, and support tooling all need to be included in the residency assessment.

## 4.5 Clinical safety

The source correctly says it will not provide dosing, interaction checking, or automatic risk scoring. It still needs a formal clinical safety boundary:

- every clinical rule has an owner, source, version, effective date, review date, and retirement path;
- a developer cannot create a threshold by editing a JSON setting;
- clinical copy is reviewed, not merely technically tested;
- a workflow reminder says what is pending or due, not what treatment to choose;
- a clinician remains responsible for interpretation and action;
- abnormal results can be displayed exactly as entered, with a source-provided flag, without the product independently deciding that a patient is dangerous;
- any urgent notification requires a validated rule and an acknowledgement trail.

The MoH 2022 guideline summary supports the eight-contact direction and late-booking combination of preceding goals, but the exact rules in the source—such as the SFH threshold, scan cut-off, risk flags, and post-term urgency—still require clinical sign-off.

# 5. Specific review findings

## 5.1 V1.0 / V1.1 split

The labels Run the day and Control the business are useful. The current allocation is not.

### Keep in V1.0

- core organisation, facility, module, user, role, and permission model;
- patient identity, search, duplicate warning, and quick registration;
- reception, check-in, queue, triage, and consultation;
- clinical note draft/sign/amendment;
- allergies as a prominent display, without automated interaction checking;
- prescription creation and safe pharmacist review;
- full core ANC episode/contact workflow;
- lab order, collection, entry, verification, release, and print;
- product catalogue, batches, expiry, FEFO, POS, internal and external dispensing;
- direct goods receiving;
- basic stock count and approved variance adjustment;
- quarantine and minimal disposal record;
- invoices, payments, allocations, split tender, manual Mobile Money references, receipts, refunds, and cashier shifts;
- simple appointments and follow-up;
- operational reports and exports;
- security, audit, backups, paper fallback, and draft resilience.

### Move to V1.1

- purchase orders and approvals;
- partial PO receipt and supplier balances;
- supplier returns;
- blind counts, cycle counts, recount thresholds, and variance analytics;
- advanced adjustment workflow framework;
- advanced disposal batches and certificate workflows;
- full expense workflow and debtor/credit controls;
- the full report catalogue and reporting materialisation;
- CSV onboarding and bulk import tooling beyond a carefully supported opening-stock template;
- richer appointment views and provider calendars;
- branch dashboards and advanced operational controls;
- unusual-access detection and advanced support tooling.

### Move to Phase 2 or later

- cross-branch stock transfers;
- SMS and WhatsApp;
- external payment APIs;
- insurance claims;
- postnatal, immunisation, family planning, labour, delivery, and newborn workflows;
- true offline additive clinical writes;
- controlled-drug workflow if it is not validated for V1.1;
- advanced procurement analytics;
- accounting integrations;
- patient portal and telemedicine.

The revised split makes V1.0 slightly larger in a few high-value fundamentals and materially smaller in speculative controls.

## 5.2 Pharmacy receiving

### Finding

The source identifies receiving as the highest-stakes pharmacy data-entry moment, then places the operational receiving workflow in V1.1. That is not viable.

### Verdict

Minimal direct goods receiving is V1.0.

### V1.0 receiving screen

Required:

- supplier or cash purchase marker;
- product and purchase unit;
- quantity received;
- batch number for medicines;
- expiry date for medicines;
- actual purchase cost;
- receiving date and user;
- optional supplier invoice or delivery-note number;
- optional note and attachment;
- post action that creates the batch/lot and an append-only GOODS_RECEIPT movement.

A facility may receive without a Purchase Order. That is the normal small-pharmacy path.

### V1.1 purchasing

Add:

- PO draft, submit, approve, send;
- partial receipt;
- discrepancy handling;
- supplier balances;
- supplier returns;
- purchasing analytics.

Do not make the receipt form depend on a PO. The PO should be an optional source document, not a prerequisite for stock integrity.

## 5.3 Stock counts

### Finding

An immutable ledger without a legitimate count-and-adjustment path becomes a trustworthy record of an untrustworthy number.

### Verdict

Basic stock reconciliation is V1.0.

### V1.0

- start a full, spot, or selected-product count;
- snapshot expected stock at count start;
- record counted quantity by product and batch where feasible;
- show movements since the snapshot;
- calculate variance;
- require a reason for a non-zero variance;
- require a second authorised user for approval;
- create COUNT_ADJUSTMENT movements only after approval;
- preserve the count and the original values.

The V1.0 UI need not be blind by default if that materially slows first deployment, but the system should support blind entry behind a simple flag. The approval and no-direct-edit rule are more important than a sophisticated counting program.

### V1.1

- blind counts as the default;
- cycle-count schedules;
- recount thresholds;
- category/location assignment;
- variance value dashboards;
- repeated-loss detection;
- supervisor queue and escalation.

## 5.4 Appointments

### Finding

ANC follow-up and ordinary clinic follow-up need a date even when they do not need a sophisticated calendar.

### Verdict

Simple appointments are V1.0.

### V1.0 shape

Patient, facility, department, optional provider, date, optional time or daypart, reason/type, status, and linked pregnancy or follow-up recommendation.

The primary view is a day list. The system should support book, reschedule, cancel, attend, and no-show. ANC contact completion should suggest the next scheduled contact based on a versioned template, but the clinician or midwife must be able to edit the date and record a reason.

Defer drag-and-drop calendars, recurring appointments, capacity management, online booking, SMS reminders, and optimisation.

## 5.5 Controlled medicines

### Decision

Adopt Option A for the baseline: V1 does not support controlled/Class A medicines.

This is the safer and more realistic decision for a modest-budget product whose target customers and pilot catalogue are not yet validated. It is not acceptable to leave the issue as a pharmacist setting.

V1 must:

- mark controlled products as unsupported;
- block sale, dispensing, and external-prescription completion for those products;
- prevent an organisation administrator from enabling them;
- show a clear message telling the facility that the product requires a controlled-drug workflow;
- require a validated catalogue classification before the item can be included in the pilot.

The pilot selection process must exclude pharmacies that require controlled medicines for their normal operation. If commercial research shows that controlled medicines are unavoidable, create a separate V1.1 or Phase 2 regulatory workstream with a pharmacist, legal/regulatory advisor, and target-pharmacy inspection input. That workstream must define the register, prescriber, dispenser, stock, record retention, inspection export, and supervision rules before implementation.

The source’s general dispensing register is not automatically a controlled-drug register.

## 5.6 Expired medicines

### Decision

Expired medicine is completely blocked from sale and dispensing.

There is no cashier override and no pharmacist override in the baseline. Remove pharmacy.dispense.override_expiry from:

- permission templates;
- API actions;
- user stories;
- acceptance tests;
- audit reports;
- UI copy.

Expired stock can move only to quarantine and then to a documented disposal workflow. A daily job may mark it expired, but the transaction boundary must re-check the expiry date at the moment of sale or dispensing. The product should never rely on a job having run.

The NDA’s public licensing guidance says pharmaceutical outlets are expected to routinely destroy expired drugs following NDA procedures. The system should document the facility’s process; it must not imply that the software grants disposal approval.

## 5.7 Regulatory baselines versus facility configuration

The rule must be:

    Regulatory minimum
            +
    Facility may choose stricter controls

Not:

    Facility chooses whether legal controls apply

Implement this as a versioned rule layer with at least:

- jurisdiction;
- rule identifier;
- source and document version;
- effective date;
- product/workflow scope;
- minimum behavior;
- facility tightening options;
- approval owner;
- review date.

Non-disableable V1 floors should include:

- no expired medicine sale or dispense;
- no controlled medicine sale when controlled support is excluded;
- required batch and expiry for medicine receiving;
- required prescription handling where the validated catalogue says it is required;
- no negative medicine stock;
- audit of high-risk actions;
- server-side authorisation;
- retention and privacy obligations;
- immutable completed stock, payment, and clinical records.

If a source field is legally mandatory, its requiredness cannot be a facility setting. A facility may require a prescriber registration number even if the baseline does not; it may not turn off a legally required field.

## 5.8 Clinical decision support

The source’s conservative direction is right, but the boundary needs to be explicit.

### Safe workflow information

- appointment is due or overdue;
- lab result is available for review;
- prescription is awaiting pharmacy action;
- an investigation is outstanding;
- a batch is near expiry;
- a pregnancy has passed a documented scheduled date;
- a staff credential is nearing expiry.

### Clinical interpretation

- this blood pressure is dangerous;
- this pregnancy is high risk;
- this result is critical;
- this patient is post-term and requires intervention;
- this prescription should change;
- this dose is safe.

The second category is not a V1 feature unless the rule has a named clinical owner, validated source, versioning, effective date, test cases, override/escalation behavior, and governance.

Specific changes:

- Replace the default post-term urgent notification with a due-date workflow flag until a clinician approves the rule and wording.
- Do not generate a critical-lab alert from arbitrary facility reference ranges. In V1, allow the lab professional to mark a result for clinician review, or only use a validated catalogue rule pack.
- Keep manual risk flags as clinician-entered records; do not infer risk from data.
- Keep the BP plausibility check as a data-entry check, not a clinical alert.
- Treat ANC schedule/template rules as clinical content: version them and prevent casual administrator editing.

## 5.9 ANC usability

The ANC architecture is good enough to preserve. The midwife-facing screen is the highest product risk.

### Immediately visible

At the top of the pregnancy workspace and contact screen, show:

- patient identity and age;
- gestational age and EDD;
- dating basis and last EDD revision;
- current contact number and date;
- last recorded BP and SFH with their dates;
- goals due for this contact;
- outstanding investigations/results;
- manually recorded risk flags;
- next appointment/follow-up;
- a clear save state and connectivity status.

Do not put the full obstetric history, sensitive data, all interventions, every lab result, and every document above the fold.

### Collapsed by default

- prior pregnancy details;
- sensitive HIV/eMTCT, IPV, STI, and reproductive-history detail;
- older contact narrative;
- completed interventions;
- documents and attachments;
- report-only fields.

The sensitive section must stay permission-gated and must never be included on the printed card.

### Copy-forward

Prior values may be shown as ghost text or a clearly labelled Previous value. Copying is explicit and field-level or group-level. Copied values are draft values until saved as current. The UI must never silently promote old BP, weight, SFH, examination findings, or intervention status into the new contact.

The current contact must visibly distinguish:

- previous;
- copied as starting point;
- newly entered;
- not measured;
- refused;
- unknown.

### Booking versus follow-up

Booking is a higher-information event: dating, obstetric history, baseline risk, consent/privacy, and initial plan. It should use progressive disclosure, not a five-step wizard that forces a midwife through empty screens.

Recommended booking flow:

1. Patient and pregnancy dating.
2. Pregnancy history and relevant risk information.
3. Baseline examination and investigations.
4. Interventions and plan.
5. Next appointment and print.

Make it possible to save a draft after each group and to complete the same flow on a 768px Android tablet.

Follow-up contact is one screen:

1. goals due now;
2. current observations;
3. investigations and results;
4. interventions;
5. assessment entered by the clinician;
6. plan and next appointment;
7. save and print if required.

### Keyboard and tablet behavior

- predictable tab order;
- numeric keypad for vitals;
- Enter moves to the next common field;
- large targets and no hover-only actions;
- no modal for every small edit;
- auto-save drafts locally, but do not persist a full PHI cache;
- save contact in a measured two-minute workflow after the measurements are available;
- allow an incomplete draft when the mother declines or an item is unavailable;
- make print available without returning to a dashboard.

The contact should be benchmarked against the paper card with a real midwife. The acceptance criterion is not that the screen looks complete; it is that a trained midwife can finish it without workarounds.

## 5.10 Security versus practicality

### Essential V1

- shared-schema tenant isolation with proven RLS;
- server-side permissions and facility scope;
- secure session management and revocation;
- quick PIN lock on shared devices;
- privileged MFA;
- audit of chart access, exports, permissions, stock, money, and clinical state transitions;
- immutable clinical, financial, and stock history;
- private attachments with access checks;
- encrypted backups and a restore test before pilot;
- PHI scrubbing in logs and error reporting;
- paper fallback forms;
- no PHI in browser persistence beyond controlled encrypted drafts;
- no offline completion of stock, money, dispensing, or clinical sign-off.

### Defer or simplify

- unusual-access analytics;
- OpenTelemetry and elaborate trace analysis;
- customer-facing infrastructure health dashboards;
- broad attachment file types;
- general event bus;
- multi-region disaster recovery;
- tenant-level self-service restore;
- advanced support analytics;
- full custom permission editor.

Do not make a security feature optional merely because the target customer is small. Make the implementation and user experience small.

## 5.11 PostgreSQL RLS

Keep shared schema plus organisation_id plus PostgreSQL RLS. For the target of a few branches and dozens of staff per organisation, it is a sensible operational choice.

RLS is only real if the following are enforced:

1. Every tenant-owned table has a non-null organisation_id, including report and audit tables where applicable.
2. The application database role is not the table owner and does not have BYPASSRLS.
3. FORCE ROW LEVEL SECURITY is enabled.
4. Policies cover SELECT, INSERT, UPDATE, and DELETE behavior, including WITH CHECK.
5. Tenant context is set with SET LOCAL inside an explicit transaction from authenticated server state.
6. A missing tenant context causes an error, not a broad query.
7. Connection pooling cannot leak a previous request’s context.
8. Every Celery task carries organisation_id explicitly and establishes its own transaction context.
9. Reporting tables, materialised tables, exports, read replicas, and raw SQL use the same tenant discipline.
10. Platform operations use a separately protected path, MFA, reason, time limit, and T3 audit; ordinary application code never receives a silent bypass.
11. Migrations create policies before data becomes accessible, and CI fails if a tenant model lacks a policy.
12. Negative tests cover every endpoint and important background path with Org A and Org B.
13. Facility scope and department scope are separately enforced. RLS protects the organisation boundary; it does not replace object-level authorisation.
14. Tenant export, restore, support access, and account closure are tested as isolation-sensitive operations.

The source’s RLS idea is appropriate. The risk is believing that a policy declaration is the same thing as a proven operational control.

## 5.12 Domain model

### Keep

- Organisation, Facility, Department;
- User, membership, UserFacilityRole, Role, Permission, Credential;
- organisation-scoped Patient with facility-scoped care records;
- Encounter and immutable ClinicalNoteVersion;
- PregnancyEpisode and ANCContact;
- Prescription connected to MedicineDefinition;
- MedicineDefinition separate from Product;
- ProductUnit, ProductPrice, Batch, StockMovement;
- Invoice, Payment, PaymentAllocation, Refund, CreditNote;
- CashierShift;
- AuditEvent.

### Change

#### Batch and location

The source puts stock_location_id on Batch and also says a transfer preserves batch identity. A single batch row cannot represent 40 tablets in the main store and 20 tablets in the dispensary at the same time without awkward row splitting.

Use:

    BatchLot
        product, batch number, expiry, manufacture date, acquisition cost

    BatchLocationBalance
        batch lot, stock location, quantity on hand, version

Stock movements reference both the lot and the location. A transfer moves quantity between balances while preserving lot identity.

This is a small extra table now and prevents a major rewrite when a facility has a store and dispensary or when branches are added.

#### Polymorphic references

The source uses reference_type/reference_id on StockMovement and source_type/source_id on InvoiceItem. Generic references are convenient but weaken referential integrity and make deletion, migration, and audit queries harder.

For V1, prefer a common source-document table or explicit typed source fields with a database check that exactly one source is present. At minimum, provide a reliable source-document identifier and prevent orphaned movement origins. Do not allow a stock movement to point to an object that the database cannot validate.

#### Derived quantities

The ledger should be authoritative. BatchLocationBalance is a transactional projection, not a second editable truth. Reconcile it against movements and raise an alert on drift. Do not allow a nightly job to silently fix a discrepancy.

#### Product catalogue

Seeded medicine data must be versioned and reviewed. A seeded catalogue is not a legal or clinical classification by itself. Facility-created products should have an explicit review state.

#### Pregnancy closure

V1 needs a safe way to close, transfer, or mark a pregnancy episode ended without pretending that V1 supports full maternity. Do not leave active pregnancies open forever because outcome detail is Phase 2. The outcome/status vocabulary requires clinician validation.

#### Patient merge

Do not implement merge as an opaque repoint-every-FK transaction. Use a reviewed merge preview, preserve both IDs, create an immutable mapping, and handle clinical and financial source documents deliberately.

## 5.13 Pharmacy unit conversion

The base-unit strategy is correct and should remain, with modifications.

Keep:

- one base unit per product;
- decimal quantities, never floating-point;
- direct conversion to base, not chained conversion at transaction time;
- immutable packaging factors once movements exist;
- price per sellable unit;
- historical price rows and invoice price snapshots.

Change the rule that the base unit must always be the smallest dispensable unit. That is not true for every supported product:

- tablets and sachets can use a discrete base;
- liquid stock can use millilitres and allow a configured fractional precision;
- a sealed vial or ampoule can use vial as the base if it is not split;
- a multi-dose vial needs explicit support before it is treated as millilitres;
- kits should be a single stockable kit in V1; component decomposition is Phase 2;
- packs, boxes, blisters, and cartons need a fixed packaging factor;
- repackaging is not V1;
- a changed pack size or barcode should create a new SKU/product packaging version, not edit history.

Add:

- quantity precision;
- discrete versus measurable quantity type;
- minimum transaction quantity;
- rounding policy;
- an explicit rule for opening a pack or partial dispensing;
- product barcode aliases for old packaging.

Use currency minor-unit configuration for UGX rather than assuming two decimal places in every interface. The arithmetic can remain decimal.

## 5.14 Stock ledger

Keep the append-only ledger as a non-negotiable architecture rule.

Required invariants:

- every movement has an organisation, facility, location, product, and source;
- movement quantity is non-zero and uses the product’s base unit;
- negative stock is rejected in the same transaction that allocates batches;
- batch/location balances cannot fall below zero;
- FEFO allocation locks candidate balances in a deterministic order;
- sale, dispense, return, and receipt operations are idempotent;
- duplicate requests with the same key and different payloads fail;
- completed operations cannot be cancelled by editing; they are corrected with a return or counter-movement;
- quarantine moves quantity between locations without changing total stock;
- expiry is checked at transaction time;
- an approved count creates adjustment movements, never direct edits;
- reconciliation is visible and actionable;
- receipt printing occurs after a committed server transaction.

The source’s proposed nightly reconciliation is good as a monitor. It is not a substitute for correct transaction locking.

## 5.15 Billing and payments

Keep the model, simplify the V1 behavior.

### V1 behavior

- one unified clinic invoice per encounter;
- separate pharmacy sale invoice at POS;
- service catalogue and prices;
- manual Mobile Money and card/bank references where used;
- cash, split tender, partial payment, deposits, and payment allocations;
- cashier shift reconciliation;
- refunds and sale returns;
- credit notes for correcting unpaid or partially paid invoices;
- receipts and reprints with watermark;
- no tax or EFRIS claim until legally confirmed;
- no full insurance workflow;
- no credit limit management.

Make invoice amount_paid and balance derived from allocations. If cached, enforce them transactionally and test the invariant.

Move separately payable department invoices, corporate credit controls, credit limits, ageing, insurance, and tax integration to V1.1 or Phase 2.

Do not implement two complete billing models for V1. Keep department attribution so the second model is additive later.

## 5.16 Roles and permissions

The model is right, but the administrative surface should be smaller.

Start with role templates:

- Owner / Administrator;
- Reception / Clinic Cashier;
- Nurse / Triage;
- Clinician;
- Midwife / ANC;
- Lab Technician;
- Pharmacist;
- Pharmacy Cashier / Storekeeper;
- Manager / Accountant as an optional template.

Allow multiple templates per user and controlled add-on permissions. Present the permission matrix by business capability, not by hundreds of technical permission names.

Preserve separation of duties:

- refund and credit note issuance;
- price override;
- stock adjustment approval;
- count approval;
- permission grant;
- support access approval.

A person may hold several operational roles, but the product should make approval conflicts visible and configurable.

## 5.17 Role-specific UX

The question for every workspace is: what is the single most important thing this user is trying to accomplish?

| Role | Primary job | Default workspace |
| --- | --- | --- |
| Owner | Know whether the business is healthy | Branch summary, revenue, stock risk, variances, approvals |
| Administrator | Keep the day moving | Queue, staffing, appointments, unresolved operational items |
| Receptionist | Register and route patients correctly | Search, register, check-in, appointment list |
| Nurse/Triage | Record safe first observations and route patients | Triage queue and claimed patients |
| Clinician | Complete and sign care safely | My queue, outstanding results, drafts, follow-ups |
| Midwife | Complete today’s ANC contacts | Today’s ANC, due goals, overdue follow-up, print |
| Lab Technician | Process specimens and results | Collection, in-progress, verification queue |
| Pharmacist | Dispense safely and control stock | Dispensing queue, batches, expiries, approvals |
| Pharmacy Cashier | Sell quickly and reconcile cash | POS, held carts, current shift |
| Storekeeper | Receive and count accurately | Pending receipts, counts, quarantine |
| Accountant/Manager | Reconcile money and exceptions | Payments, shifts, refunds, debtors, exports |

The source’s role dashboards are a good starting point. The risk is allowing every role’s dashboard to become another reporting product. Keep each landing page short and task-oriented.

## 5.18 Low bandwidth and offline

The phased philosophy is right.

### V1

- preserve unsaved drafts locally for a short, explicit period;
- encrypt drafts and clear them on logout, session expiry, or account switch;
- show connectivity and save state;
- retry safe reads and idempotent writes;
- keep the POS cart locally while disconnected;
- do not complete sale, payment, dispensing, stock receipt, stock adjustment, or clinical sign-off without server confirmation;
- provide printable downtime forms;
- provide a clear recovery queue after reconnect.

Do not call a queued payment action an offline sale. It is a saved attempt awaiting server completion.

### Phase 2

- read-only cache of today’s queue and summaries;
- additive triage vitals or appointment check-in only after conflict and privacy testing;
- no medication, stock, invoice, payment, or prescription synchronization.

### Phase 3

True offline clinical operation only if a commercial need justifies the substantial synchronization, device-security, conflict-resolution, and clinical-safety work.

## 5.19 Reporting

The source’s report architecture is sound, but the first report set is too broad.

### V1 report minimum

- patients seen and encounters by date;
- queue and waiting-time summary;
- payments by method and cashier shift;
- clinic revenue and outstanding balances;
- pharmacy sales by day, product, and cashier;
- dispensing register;
- stock on hand and stock movement;
- near-expiry and expired/quarantine stock;
- approved adjustments and count variances;
- laboratory throughput and outstanding results;
- ANC register;
- ANC operational follow-up;
- monthly summary figures clearly labelled as transcription assistance, not official submission.

Use indexed queries with strict date ranges. CSV and PDF/print are enough for the first pilots; add XLSX wherever the pilot’s records officer actually uses it.

The ReportDefinition/ReportCell idea is worth keeping for structured ANC and HMIS-shaped output. It must be server-owned, versioned, tested, and sourced to an identified form version. It should not become a free-form query-builder for facility administrators.

## 5.20 Technical stack

Keep the proposed stack. Add a deployment rule: one modular monolith, one primary PostgreSQL database, one background worker, and managed object storage/Redis only where justified.

Do not make WebSockets, microservices, Kubernetes, a general event bus, or a data warehouse prerequisites for the first pilot.

The stated infrastructure cost is an estimate, not a product requirement. Obtain vendor quotes for in-country hosting, backups, Redis, object storage, email, monitoring, and support before promising a price.

## 5.21 Frontend rendering

The recommendation to use Next.js primarily as an authenticated client application shell is correct.

Use:

- static or non-PHI shell rendering;
- client-side TanStack Query for patient and operational data;
- no SSR of patient charts or clinical data;
- no authenticated PHI responses cached by a CDN;
- no access tokens in localStorage;
- query-cache clearing on logout, lock, facility switch, and user switch;
- no persistent TanStack Query cache for PHI;
- encrypted, narrowly scoped draft persistence only;
- no service-worker cache of patient records;
- no optimistic update for money, stock, dispensing, or clinical sign-off.

The source’s choice is simpler and safer than SSR-ing authenticated PHI. The implementation must still set no-store behavior correctly; “client-side” does not automatically mean “uncached.”

## 5.22 API

REST with /api/v1 and explicit transition endpoints is the right choice.

Retain:

- POST action endpoints for sign, dispense, receive, approve, close, refund;
- idempotency keys;
- ETag/If-Match or an equivalent version check;
- cursor pagination for timelines, audit, and movements;
- allow-listed filtering;
- RFC 7807 errors;
- server-derived tenant and permission context.

Strengthen:

- persist idempotency records with a request-body hash, status, and response;
- reject reuse of a key with a different payload;
- do not rely on a 24-hour cache alone for money or stock;
- require an expected resource version on state transitions;
- make invalid state transitions explicit and machine-readable;
- include facility and organisation in every server-side authorization decision;
- treat X-Facility-Id as a selection hint, never as proof of access;
- ensure Celery and report endpoints establish tenant context;
- forbid DELETE for immutable clinical, stock, payment, and final invoice records;
- keep clinical dates distinct from server audit timestamps.

## 5.23 Implementation sequence

The source’s dependency ordering is mostly sound, but the stated critical path is too narrow. A product that includes clinic, pharmacy, lab, ANC, billing, and inventory has several parallel critical paths.

### True critical path

1. Legal/data-residency gate and named advisors.
2. Tenancy, authentication, permissions, RLS test harness, audit, numbering, and idempotency.
3. Patient identity and registration.
4. Clinic vertical slice: check-in → queue → triage → encounter → service charge → payment → receipt.
5. Inventory vertical slice: product → direct receipt → batch/lot → stock balance → POS sale → shift close.
6. Prescription/dispensing vertical slice: prescription → pharmacist review → FEFO dispense → payment/receipt.
7. Lab vertical slice: order → specimen → result → verification → release.
8. ANC vertical slice: booking → contact → next appointment → print → report.
9. Reports, imports, hardening, restore, and pilot operations.

### Safe parallel work

- ANC field and workflow design from week one;
- pharmacist catalogue and receiving validation from week one;
- design system and tablet/print prototypes;
- RLS and tenant-isolation harness;
- billing and inventory primitives after tenancy;
- paper fallback forms and training materials;
- performance fixtures and seeded datasets;
- legal review, DPA, data-residency assessment, and clinical sign-off.

### Do not do in parallel without contracts

- let developers invent ANC thresholds while building screens;
- let facility administrators define regulatory requirements;
- build all reports before workflows settle;
- let a general platform team implement a broad permission matrix without role research;
- let the POS team assume stock receipt and product classification are somebody else’s problem.

ANC design should begin in week one; ANC implementation does not have to be the first production slice, but it must not be left until the end for first usability review.

## 5.24 Delivery estimate

The source claim of V1.0 in five to six months with a team of four to five is not a safe commitment for a pilot-ready product containing:

- multi-tenant security;
- clinic care;
- ANC;
- laboratory;
- pharmacy POS and dispensing;
- batch-level inventory;
- billing and shifts;
- audit and privacy;
- printer workflows;
- low-bandwidth behavior;
- validation and training.

Five to six months could be an internal code-complete alpha under unusually strong conditions. It is not a credible default for a product that has passed clinical, pharmacist, security, data-protection, and pilot validation.

Use milestones and exit criteria instead:

| Milestone | Indicative range | Exit criterion |
| --- | --- | --- |
| Decisions, source consolidation, clinical/pharmacist/legal validation | 4–8 weeks, overlapping | No unresolved blocker on pilot eligibility, residency, ANC core, expired stock, or controlled medicines. |
| Foundation and clinic vertical slice | 8–12 weeks | A controlled test site can register, queue, triage, consult, bill, and print without data loss. |
| Pharmacy/inventory and finance hardening | 8–12 weeks | Direct receipt, FEFO sale, shift close, count/adjustment, return, and reconciliation pass repeatable tests. |
| Lab and ANC integrated slices | 8–12 weeks | Real users complete representative workflows; clinical advisor signs content and states. |
| Pilot hardening and training | 6–10 weeks | Restore drill, security review, accessibility pass, paper fallback drill, support plan, and measured workflow times. |

For the stated team, an integrated pilot-ready V1.0 should be planned as a range around eight to twelve calendar months, not promised as five to six. A narrower internal alpha may arrive sooner. V1.1 should be scheduled from pilot evidence, not automatically assumed to be another eight to twelve weeks.

## 5.25 Pilot strategy

The preferred first pilot is correct:

> One friendly single-branch medical centre with outpatient care, ANC, a small laboratory, and an attached pharmacy.

It exercises the product’s real differentiator: one patient identity and one operational flow across clinic, lab, ANC, pharmacy, and finance.

Do not begin with a two-branch pilot. Branch transfers and cross-branch permissions add complexity before the first site has proven basic workflows.

### Recommended rollout

#### Pilot Wave A

Patients, reception, queue, triage, consultation, clinic services, payments, receipts.

#### Pilot Wave B

Lab, prescribing, pharmacy dispensing, direct receiving, POS, cashier shifts.

#### Pilot Wave C

ANC booking, contacts, print card, next appointment, ANC reports.

#### Pilot Wave D

Counts, adjustments, expiry/quarantine, owner reports, opening-stock and import controls.

Because direct receiving and basic reconciliation are now V1.0, Wave B/D may overlap technically, but the operational rollout should still introduce the controls gradually.

Run paper in parallel for high-risk workflows during the first period, but do not require staff to duplicate every record indefinitely. Define which source is authoritative for each workflow and use paper as contingency and comparison, not as a second permanent database.

Exit criteria should include:

- no cross-tenant leakage;
- no irreversible data-loss incident;
- zero unexplained stock-ledger drift;
- successful direct-receipt and count reconciliation;
- cashier shift close used daily;
- ANC contact time no worse than the paper benchmark after training;
- real printer operation;
- paper fallback rehearsed;
- restoration tested;
- clinical/pharmacist/legal sign-offs completed for the features actually enabled.

## 5.26 Backlog strategy

Do not create and blindly execute 180–220 stories.

Use:

    Canonical blueprint
        ↓
    Epics
        ↓
    Dependency map
        ↓
    Next 10–20 stories
        ↓
    Build and test
        ↓
    Pilot feedback
        ↓
    Next stories

Write detailed acceptance criteria early for:

- tenant isolation;
- patient identity and duplicate handling;
- clinical sign/amend;
- ANC booking and contact;
- direct goods receipt;
- stock allocation and reconciliation;
- dispensing;
- payments and shift close;
- audit;
- print and paper fallback.

For lower-risk screens, use a smaller definition of ready and evolve from observed workflows. The first backlog should cover one vertical slice, not every future screen.

## 5.27 Missing capability classification

| Capability | Recommendation |
| --- | --- |
| Chronic disease follow-up | V1.0 generic FollowUpRecommendation and appointment; disease-specific templates Phase 2. |
| Paediatric workflow | V1.0 minimum safe support: age units, weight, paediatric vitals, and clinician-entered dosing text; no dosing calculator. Clinician validation required. |
| Vaccination | Phase 2 unless the selected pilot makes it essential. |
| Postnatal care | Phase 2, using the episode/contact/intervention pattern. |
| Labour, delivery, maternity register | Phase 2; partograph Phase 3 unless a maternity pilot changes the product. |
| Newborn record | Phase 2. Preserve patient relationship and outcome seams now. |
| Procedure billing | V1.0 service catalogue and billing; full procedure documentation Phase 2. |
| Medical certificates and sick notes | V1.1 printable templates with clinician sign-off; not a clinical rules engine. |
| Referral letters | V1.0 printable referral; external response tracking Phase 2. |
| Medical documents | V1.0 limited private attachments and print; richer document workflows later. |
| Pharmacy credit customers | V1.0 optional unpaid invoice/credit record only if pilot demands it; credit limits and debtor controls V1.1. |
| Supplier returns | V1.1. Do not silently discard returned stock in V1.0. |
| Controlled medicines | Explicitly unsupported in baseline V1; revisit only with a validated workflow. |
| Cold-chain inventory | V1.0 storage-condition label and explicit limitation; temperature logging and excursions Phase 2. |
| Emergency/unknown patient | V1.0 temporary identity and later link/merge. |
| Deceased patients | V1.0 status and access preservation; formal death documentation workflow V1.1 if needed. |
| Patient merge | V1.0 duplicate warning/link; governed merge preview and mapping V1.1. |
| Patient transfer between facilities | V1.0 controlled cross-branch lookup/stub; formal transfer package V1.1/Phase 2. |
| Branch-level privacy | V1.0 as a product decision and permission rule, not an afterthought. |
| Account closure | V1.0 deactivate organisation/user, revoke sessions, retain records; tenant export/closure automation Phase 2. |
| Staff leaving | V1.0 deactivate, revoke sessions, preserve authorship. |
| Licence expiry | V1.0 credential gate; reminder digests V1.1. |
| Device/session loss | V1.0 session list and remote revocation. |
| Printed downtime workflows | V1.0 required. |
| Data export and tenant exit | V1.0 admin export with audit; polished self-service export Phase 2. |
| Multilingual UI | Not V1. Printed English/Luganda task cards are more valuable initially. |

# CANONICAL DECISIONS TO FREEZE

The following are mature enough to be architectural constraints:

1. Clinicopus is one healthcare operations platform for CLINIC, PHARMACY, and CLINIC + PHARMACY facilities.
2. Organisation is the tenant root. Facility is a branch, not a tenant.
3. Patient identity is organisation-scoped. Care records are facility- and permission-scoped.
4. Users may have multiple roles and facility/department scopes.
5. Permissions are server-authoritative. UI hiding is not security.
6. The first implementation is a modular monolith: Next.js client, Django/DRF, PostgreSQL, and limited Celery/Redis use.
7. Shared-schema PostgreSQL RLS is the tenancy strategy for V1.
8. Every tenant table has explicit organisation context; the app role is non-BYPASSRLS; FORCE RLS and negative isolation tests are mandatory.
9. Background jobs and reporting establish tenant context explicitly.
10. Clinical history, finalised financial documents, payments, audit events, and stock movements are append-only or corrected by new state-bearing records.
11. ANC uses PregnancyEpisode → ANCContact, not a flat ANC encounter type.
12. ANC contacts are scheduled from versioned templates and retain the actual dating basis.
13. Clinical workflow is separate from clinical interpretation. V1 has no unvalidated clinical decision support or clinical AI.
14. Stock changes only through an append-only movement ledger.
15. Stock balances are by product, batch lot, and location; location movement preserves batch identity.
16. Stock quantities and money use decimal arithmetic; no floating point.
17. Product unit conversions are immutable once movements exist; packaging changes create a new SKU or packaging version.
18. Negative medicine stock is blocked in V1.
19. Expired medicine is never saleable or dispensable in baseline V1.
20. Controlled/Class A medicines are unsupported in baseline V1 and cannot be enabled by a facility setting.
21. V1 pharmacy has direct goods receiving; purchase orders are additive V1.1.
22. V1 pharmacy has basic physical count and controlled variance adjustment; advanced counting is V1.1.
23. V1 has simple appointments and follow-up dates; advanced scheduling is later.
24. Billing uses PaymentAllocation even if credit and insurance features are deferred.
25. Mobile Money remains manual reference capture in V1.
26. No offline completion of stock, money, dispensing, or final clinical sign-off.
27. Browser persistence is limited to short-lived encrypted drafts; no persistent PHI query cache.
28. Reports are indexed OLTP queries and export jobs first; a reporting warehouse is not a V1 prerequisite.
29. Regulatory minima cannot be disabled. Facility configuration can only be stricter.
30. External integrations are not required for V1; CSV, XLSX where needed, PDF, printing, and email are sufficient.

# DECISIONS STILL OPEN

## Product-owner decision

- Confirm the revised V1.0 boundary, including direct receiving, basic counts, simple appointments, and minimal disposal.
- Confirm pilot pricing and whether pricing is per facility with unlimited users.
- Confirm default unified billing and whether any clinic requires pay-before-service.
- Confirm default cross-branch patient visibility and whether only a minimal stub is shown outside the home facility.
- Confirm whether optional unpaid invoices/credit customers are needed in V1.
- Confirm the first pilot site and the wave sequence.
- Confirm that controlled medicines are excluded from the baseline.
- Confirm which report formats are essential on day one.
- Confirm whether staff may configure their own service catalogue and prices or whether owner approval is required.

## Clinician decision

- Validate the complete ANC field and contact set against the current Uganda guidance.
- Validate GA/EDD precedence, dating-scan cut-off, late-booking schedule, and pregnancy closure states.
- Validate BP and SFH requirements; the source’s SFH threshold must not be frozen from a developer assumption.
- Validate manual risk-flag vocabulary and every clinical label/copy.
- Decide whether a diagnosis is mandatory before encounter sign-off.
- Approve critical-lab workflow or prohibit automated critical-result alerts in V1.
- Validate paediatric vitals and the minimum paediatric workflow.
- Approve sensitive IPV, HIV/eMTCT, STI, reproductive-history, and printing rules.
- Approve consultation templates and copy-forward behavior.

## Pharmacist decision

- Confirm baseline pilot catalogue and regulatory classification.
- Confirm pharmacist presence/supervision behavior.
- Confirm external prescription minimum fields and validity period.
- Confirm dispensing register contents and retention.
- Confirm that expired-stock override is removed.
- Confirm return-to-resale policy; baseline should default to quarantine, not restock.
- Confirm disposal record fields and required witnesses/certificates.
- Decide whether cold-chain stock is in pilot scope.
- Decide whether controlled medicines are absent from the pilot or require a separate validated module.

## Legal/regulatory decision

- Confirm the hosting and processor arrangement under Uganda’s data-protection requirements, including backups, email, monitoring, support, and error tracking.
- Confirm whether cross-border processing is permissible for the intended architecture and what documentation is required.
- Confirm controller/processor roles, DPA wording, PDPO registration, DPO obligations, DPIA scope, breach handling, and retention.
- Confirm current HMIS 071/105 forms and the obligations of private facilities; label outputs as transcription assistance unless officially confirmed.
- Confirm NDA/pharmacy requirements for dispensing records, restricted/controlled medicines, expired-stock destruction, recalls, and disposal.
- Confirm VAT, EFRIS, invoice numbering, credit notes, and tax-reporting obligations before making compliance claims.
- Confirm clinical and financial record retention periods.

## Pilot-research decision

- Measure paper ANC booking and contact time.
- Measure real network latency and outage frequency at the selected site.
- Observe whether the facility pays before or after clinic services.
- Observe how products are received, counted, repacked, and sold.
- Measure duplicate-patient creation and phone availability.
- Test role combinations and shared-device behavior.
- Confirm whether a day-list appointment is sufficient.
- Observe which reports the owner and records officer actually use.
- Test the printer models and paper sizes available on site.
- Confirm whether the selected pharmacy can operate without controlled medicines in the baseline.

# RECOMMENDED V1.0 — RUN THE DAY

## Foundation

- Organisation, facility, department, and module setup.
- User membership, multiple roles, facility scope, role templates, and credential records.
- Secure authentication, privileged MFA, session revocation, shared-device PIN lock.
- PostgreSQL RLS with the safeguards above.
- Patient identity, MRN, quick registration, unknown/emergency patient, duplicate warning, and safe link/merge preview.
- Consent/privacy notice records, DPO/customer settings, retention policy record, and audit.
- Immutable state transitions, idempotency, concurrency checks, numbering, print pipeline, backups, restore drill, and paper fallback.

## Clinic

- Patient search and registration.
- Check-in, queue, triage, and department routing.
- Consultation drafts, autosave, sign, amend, and entered-in-error workflow.
- Diagnoses/problems, allergies, procedures as service records, prescriptions, referrals, and generic follow-up recommendations.
- Clinic billing, receipts, and access-controlled patient timeline.

## ANC

- PregnancyEpisode with one active pregnancy rule.
- Booking with recorded dating method, EDD, and revision history.
- Obstetric history, privacy-gated sensitive section, and manual risk flags.
- Versioned schedule template and late-booking combined goals.
- One-screen follow-up contact with BP, SFH, observations, investigations, interventions, plan, and next appointment.
- Lab/prescription links, print-ready ANC card excluding sensitive content, and paper-aligned ANC register.
- Workflow reminders for due, overdue, outstanding, or unreviewed items.
- No unvalidated risk scoring, dosing, interaction checking, or urgent clinical interpretation.

## Laboratory

- Facility catalogue with analytes, units, and validated reference information.
- Orders, specimen collection, result entry, verification, release, amendment, and print.
- Clinician review queue.
- No autonomous critical-value interpretation without an approved rule pack.

## Pharmacy

- Validated pilot catalogue of non-controlled products.
- MedicineDefinition and Product separation.
- Product units, prices, barcodes, batches/lots, expiry, FEFO, and quarantine.
- Direct goods receipt with minimal supplier data.
- POS with walk-in customer, registered customer optional, units, quantity, discounts within controlled caps, receipts, and held carts.
- Internal dispensing without retyping.
- External prescription capture with validated minimum fields.
- Dispensing register.
- Sale returns/refunds with restock false by default and pharmacist-authorised quarantine/release only.
- Hard block on expired and unsupported controlled products.

## Inventory

- Organisation/facility/location-aware stock ledger.
- Main store, dispensary, and quarantine locations.
- Atomic movements and transaction-time expiry/negative-stock checks.
- Opening balance.
- Basic physical count, variance, reason, and second-person approval.
- Minimal disposal record and quarantine status.
- Stock on hand, movement, expiry, and adjustment reports.

## Finance

- Service catalogue and facility prices.
- Unified clinic invoices and pharmacy sale invoices.
- Invoice items with immutable finalisation.
- Payments, PaymentAllocation, partial payments, split tender, deposits, manual Mobile Money references, reversals, refunds, and credit notes.
- Cashier shifts, blind cash close, variance reason, supervisor review, and Z-report.
- Thermal and A4 receipt printing and reprint watermark.

## Appointments/Follow-up

- Patient, date, optional time/daypart, department/provider, reason/type, status, and linked pregnancy/follow-up.
- Day-list view.
- Book, reschedule, cancel, attend, no-show.
- Next ANC appointment prompt.
- No advanced calendar, recurring booking, reminders, or capacity engine.

## Reporting

- Patients and encounters.
- Queue/waiting time.
- Payments and shifts.
- Clinic revenue and outstanding balances.
- Pharmacy sales and dispensing register.
- Stock, expiry, quarantine, movement, and count variance.
- Lab throughput and pending results.
- ANC register and operational report.
- CSV and PDF/print; XLSX for validated pilot needs.
- Tenant/facility/permission filtering on the server.

## Reliability/Security

- RLS and generated isolation tests.
- Server permissions and access audit.
- Immutable records and correction workflows.
- Secure sessions, privileged MFA, fast user switch, remote revocation.
- Private attachments with narrow V1 file types.
- PHI-scrubbed logs and error reporting.
- Verified backup and restore.
- Connectivity indicator, encrypted short-lived drafts, and no final offline mutation.
- Printed downtime forms and a practiced paper rollback.

# RECOMMENDED V1.1 — CONTROL THE BUSINESS

- Purchase orders, approvals, partial receiving, supplier balances, and supplier returns.
- Blind and cycle counts, recount thresholds, variance analytics, and approval queues.
- General approval workflow framework.
- Full disposal batches, certificates, witnesses, and compliance exports after pharmacist/regulatory validation.
- Expenses, cash-out controls, basic debtor/credit controls, and operational finance.
- Full report catalogue, report caching/materialisation where measured, XLSX exports, scheduled exports.
- CSV patient/product/import tooling with dry-run and duplicate review.
- Richer appointment views, provider calendars, and no-show analysis.
- Branch dashboards, owner controls, staff/licence expiry digests, and better support tools.
- Governed patient merge and formal patient transfer package.
- Controlled-medicine workstream only if pharmacist/legal validation and pilot demand justify it; otherwise leave it out.

# PHASE 2

- Multi-branch stock transfers with preserved batch lots.
- Safe PWA read mode and carefully scoped additive offline actions.
- SMS reminders with consent and cost controls.
- Postnatal care, immunisation, and family planning using the episode/contact/intervention pattern.
- Labour/delivery/newborn records for facilities that need them.
- Corporate accounts and basic insurance support after customer demand.
- HMIS/DHIS2 export packs, not an API by default.
- Advanced purchasing, reorder suggestions, supplier performance, and stock forecasting once data exists.
- Accounting CSV exports shaped for common systems.
- Unusual-access detection and clinical break-glass governance.
- Browser camera capture for documents.
- Controlled medicines if the complete workflow has been validated and the commercial case is real.

# PHASE 3

- True offline clinical operation and any offline stock/money operation only after a safe synchronization model.
- Inpatient, wards, beds, admissions, theatre, radiology, and hospital-scale billing.
- Wholesale pharmacy and business customers.
- External laboratory exchange and insurer integrations.
- Mobile Money APIs and settlement reconciliation.
- Full FHIR facade/interoperability where a real consumer exists.
- Multi-country deployment and country-specific rule packs.
- Validated clinical decision support under formal clinical governance.
- AI assistance only with a clinical safety officer, hazard log, data governance, evaluation, and change control.
- Database-per-tenant or reporting infrastructure changes only when scale or contractual isolation requires them.

## Re-prioritised first implementation milestones

1. Consolidate the full blueprint into one versioned source and resolve omitted-section references.
2. Appoint contracted clinical, pharmacist, legal/regulatory, and data-protection advisors.
3. Establish repo, CI, environments, managed database, backups, deployment, and PHI-safe observability.
4. Implement organisation/facility tenancy, RLS, FORCE RLS, non-BYPASSRLS role, and negative isolation tests.
5. Implement authentication, roles, facility scope, privileged MFA, session revocation, and shared-device PIN lock.
6. Build design-system primitives, print frame, tablet layouts, empty/loading/error states, and permission-driven navigation.
7. Build patient registration/search/duplicate detection/unknown patient flow.
8. Deliver clinic vertical slice: check-in → queue → triage → consultation → invoice → payment → receipt.
9. Deliver ANC paper comparison prototype and obtain clinical sign-off on fields and schedule rules.
10. Build Product, ProductUnit, price, BatchLot, BatchLocationBalance, location, and StockMovement primitives.
11. Build direct goods receipt and opening-stock import with idempotency.
12. Build stock count, variance reason, approval, and adjustment movement.
13. Build POS, cashier shift, sale, FEFO allocation, payment, and receipt.
14. Build prescription-to-dispense flow with pharmacist review, external prescription, register, and hard expiry/controlled-product blocks.
15. Build lab order, specimen, result, verification, release, and print.
16. Build ANC booking/contact/print/next appointment with one-screen usability.
17. Build minimal appointments, follow-up, referrals, and notifications.
18. Build the V1 report minimum and CSV/PDF exports.
19. Run seeded-data performance, accessibility, security, restore, and paper-fallback tests.
20. Release through the integrated pilot waves, measure, and only then write the next backlog.

## External validation points checked

The following official/public sources were checked as signals for what must remain validated:

- Uganda Ministry of Health, Essential Maternal and Newborn Clinical Care Guidelines: https://library.health.go.ug/sites/default/files/resources/Essential%20Maternal%20Newborn%20Care%20Guidelines%202022%20V3-1.pdf
- Uganda Ministry of Health ANC protocol summary: https://attend.health.go.ug/safe_mama/records/resource?id=5
- Uganda Personal Data Protection Office obligations: https://pdpo.go.ug/information-center/organisation
- PDPO guidance notes including the undertaking concerning processing or storing personal data outside Uganda: https://pdpo.go.ug/media//2022/01/20102021105143-Registration_Classification_and_Guidance_Notes.pdf
- National Drug Authority licensing guidance: https://www.nda.or.ug/wp-content/uploads/2024/03/Guidelines-on-Licensing-of-Pharmacies-and-Pharmaceutical-Manufacturers.pdf
- National Drug Policy and Authority Act, Cap 206: https://www.nda.or.ug/wp-content/uploads/2022/03/National-Drug-Policy-Authority-Act-Cap-206.pdf

These sources reinforce the need to validate ANC content, data residency/processor obligations, restricted-drug records, and expired-drug disposal. They do not replace Ugandan counsel, a clinician, or a pharmacist reviewing the final implementation.

# Final go / no-go

### REVISE THEN FREEZE

The blueprint should not be discarded or redesigned from scratch. Its core direction is sound. Before calling it the Canonical Product Blueprint v1.0, the team must apply the revised V1 boundary, remove expired-stock override paths, make controlled medicines explicitly unsupported or fully specified, add direct receiving/basic counts/simple appointments, freeze the RLS safeguards, and obtain the named clinical/pharmacist/legal decisions.

After those changes, freeze the architecture and the V1 safety constraints. Keep the detailed backlog adaptive and let the pilot determine which V1.1 controls earn implementation.
