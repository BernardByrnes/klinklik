# PROJECT_SPEC.md

Bernard Project Standard — v1.0 FROZEN

This document defines **what** a product must do, **why** it exists, and
which product rules are non-negotiable. It is the highest **internal** product
authority for the project. Applicable external binding authority may outrank
internal documents for its legal, regulatory, contractual, or formally binding
policy obligations. The Implementation Blueprint translates this document
into buildable systems and experiences; it must not silently redefine
behaviour, scope, or trust guarantees.

## How to use this template

Replace bracketed placeholders with project-specific content. Do not remove
guidance merely because it is instructional; only text explicitly marked as
TEMPLATE NOTE — REMOVE BEFORE FREEZE may be removed. Keep stable IDs for
goals, invariants, contracts, journeys, decisions,
assumptions, blockers, and changes. If information is missing, label it
OPEN, ASSUMPTION, BLOCKER, or NOT APPLICABLE. Do not fill a gap with an
unstated best practice.

### Template-note convention

**TEMPLATE NOTE — REMOVE BEFORE FREEZE:** Bracketed placeholders and any
instructional or example block carrying this label are removed or replaced
when a project document is populated.

**PERMANENT STANDARD RULE — RETAIN:** Authority hierarchy, no-guess rules,
change control, trust-regression expectations, agent boundaries, and scope
rules remain in the populated project document when applicable.

Only explicitly marked template-only text may be removed. Use these labels on
obvious reusable example/template blocks; do not mechanically label every
paragraph.

This template is intentionally depth-scalable:

- Level 1 projects may mark non-applicable sections NOT APPLICABLE and keep only the
  decisions needed to build safely.
- Level 2 projects normally complete the majority of sections.
- Level 3 projects must complete the trust, state, concurrency, audit,
  security, blocker, change-control, and regression sections.

---

## 0. Document Control

| Field | Value |
| --- | --- |
| Product name | KlinKlik |
| File name | PROJECT_SPEC.md |
| Version | 1.0 |
| Status | FROZEN |
| Document owner | Mutambo Bernard |
| Last reviewed date | 2026-08-30 (generation metadata only; not evidence of human approval) |
| Current implementable release | V1 |
| Future releases described for context | V1.1; Phase 2; Phase 3 (context only) |
| Authority level | Frozen product-behaviour authority (Bernard Standard meaning; this FROZEN document is the Rank 1 internal Product Spec authority for implementation behaviour) |
| Supersedes | NONE — first formally frozen KlinKlik Product Spec |
| Related documents / authority records | K:/new/clinicopus2.md; KlinKlik-V1-Canonical-Backlog.md; docs/product-rename.md; Bernard Project Standard templates |
| Project level | LEVEL 3 |
| Project-level owner / approver | Mutambo Bernard |

### Formal freeze provenance

| Field | Value |
| --- | --- |
| Reviewed candidate | PROJECT_SPEC.md v0.10.15 |
| Reviewed candidate SHA-256 | F6FB6008D21E951FBEE4D9DD296D54EC66E01765AD420C5F99BA05FA9BB4D678 |
| Independent reviewer | GPT-5.5 Sol xhigh — fresh independent review session |
| Review completeness | All six source parts reviewed; independent reconstruction matched the reviewed candidate SHA |
| Severity counts | S0 = 0; S1 = 0; S2 = 0; S3 = 0 |
| Independent review recommendation | FREEZE AS V1.0 |
| Human freeze approver | Mutambo Bernard |
| Human freeze approval date | 2026-08-30 |
| Human freeze approval | APPROVED FOR FORMAL V1.0 FREEZE |

### Status meanings

- **DRAFT**: being authored; not an implementation authority.
- **IN REVIEW**: proposed content is under explicit review; do not treat
  disputed content as approved.
- **FROZEN**: approved product behaviour for the represented release.
  FROZEN does not mean that every technical question is solved; unresolved
  technical or product questions remain visible in the appropriate registers.
- **SUPERSEDED**: retained for history only; a newer frozen document is
  authoritative.

### Review record

| Version | Date | Change summary | Reviewer / approver | Status |
| --- | --- | --- | --- | --- |
| 0.1 | 2026-08-28 | K0B controlled Product Spec foundation population | OPEN | DRAFT |
| 0.2 | 2026-08-28 | K0C controlled population of Sections 7–10 | OPEN | DRAFT |
| 0.3 | 2026-08-28 | K0D controlled population of Sections 11–13 | OPEN | DRAFT |
| 0.4 | 2026-08-28 | K0E-A controlled population of Section 14 Major User Journeys | OPEN | DRAFT |
| 0.5 | 2026-08-29 | Q1 complete Section 15 state machines and cross-machine constraints | OPEN | DRAFT |
| 0.6 | 2026-08-29 | Q2 Section 16 canonical stories REC–LAB | OPEN | DRAFT |
| 0.7 | 2026-08-29 | Q3 complete Section 16 canonical supplied story population | OPEN | DRAFT |
| 0.8 | 2026-08-29 | Q4 Sections 17–21 NFR/trust/coverage/domain/security population | OPEN | DRAFT |
| 0.9 | 2026-08-29 | Q5 Sections 22–26 blocker/decision/OOS/change-control population | OPEN | DRAFT |
| 0.10 | 2026-08-29 | Q6 complete Product Spec template completion and whole-document reconciliation | OPEN | DRAFT |
| 0.10.1 | 2026-08-29 | Pre-review source-audit corrections: structure, error-family taxonomy, expired-stock regression/OOS semantics, audit provenance, and SM-10 wording | OPEN | DRAFT |
| 0.10.2 | 2026-08-29 | GPT freeze-review reconciliation: clinical interpretation, credential gating, pharmacy exception, APT/ANC gating, queue state, payment reversal, pharmacy journey, traceability and editorial corrections | OPEN | DRAFT |
| 0.10.3 | 2026-08-29 | Final pre-re-review cleanup: SM-08 inventory reconciliation and review-record placement correction | OPEN | DRAFT |
| 0.10.4 | 2026-08-29 | Final GPT financial reconciliation: multi-Invoice Payment reversal, CreditNote amount-due/state semantics, and bounded refund scope | OPEN | DRAFT |
| 0.10.5 | 2026-08-29 | Final GPT visit/lab reconciliation: stale duplicate-Visit abandonment guards and canonical LAB_ONLY Visit-linked billing | OPEN | DRAFT |
| 0.10.6 | 2026-08-29 | Pre-freeze source-audit cleanup: distinguish REC-005 unresolved-work safety guards from its explicit stale queue/invoice cleanup | OPEN | DRAFT |
| 0.10.7 | 2026-08-29 | GPT cross-consistency reconciliation: active Visit encounter start, LAB_ONLY external-order creation/gating, LAB intake versus collection queue, and reception clinical-data boundary | OPEN | DRAFT |
| 0.10.8 | 2026-08-29 | Deep pre-freeze reconciliation: GPT-5.5 Pro findings KK-FR-021..023 plus independent whole-spec adversarial consistency corrections | OPEN | DRAFT |
| 0.10.9 | 2026-08-29 | Pre-freeze source-check cleanup: TRI-013 emergency triage transitions the Visit to IN_PROGRESS without inventing a triage QueueEntry | OPEN | DRAFT |
| 0.10.10 | 2026-08-30 | Final freeze-review reconciliation: unique CMC traceability, PARTIALLY_PAID abandonment safety, and Journey D Visit-state consistency | OPEN | DRAFT |
| 0.10.11 | 2026-08-30 | Pre-freeze governance reconciliation: BL-02 / OD-P1..OD-P9 freeze-gate and project-level approval semantics | OPEN | DRAFT |
| 0.10.12 | 2026-08-30 | Human governance approval reconciliation: named Product Spec/project approver, OD-P1 V1-boundary approval, and KEEP LEVEL 3 decision | Mutambo Bernard | DRAFT |
| 0.10.13 | 2026-08-30 | GPT-5.5 Pro freeze-review reconciliation: KK-FR-025 explicit UNKNOWN allergy status semantics, KK-FR-026 unpaid issued-Invoice payer repricing semantics, and KK-FR-024 review-delivery remediation | Mutambo Bernard | DRAFT |
| 0.10.14 | 2026-08-30 | Pre-final-review governance reference cleanup: remove stale v0.10.12 current-review references and make pending independent-review wording candidate-version-neutral | Mutambo Bernard | DRAFT |
| 0.10.15 | 2026-08-30 | SOL xhigh preflight reconciliation: SOL-PF-001 authoritative SM-08 ISSUED-to-ISSUED atomic REC-003 repricing transition | Mutambo Bernard | DRAFT |
| 1.0 | 2026-08-30 | Formal V1.0 Product Spec freeze following independent whole-candidate review of v0.10.15 SHA F6FB6008D21E951FBEE4D9DD296D54EC66E01765AD420C5F99BA05FA9BB4D678 with S0=0, S1=0, S2=0, S3=0 and FREEZE AS V1.0 recommendation; final human freeze approval recorded. | GPT-5.5 Sol xhigh (independent reviewer); Mutambo Bernard (human freeze approver) | FROZEN |

Source authority:

K:/Project-Standards/PROJECT_SPEC_TEMPLATE.md; K:/clinicopus/docs/product-rename.md; K:/new/clinicopus2.md; K:/clinicopus/AGENTS.md.

---

## 1. Authority Hierarchy

Projects shall complete this table without weakening the default ordering.
External Binding Authority is rank 0 for obligations that apply to the
project; the Product Spec remains the highest INTERNAL product authority.

| Rank | Source | Authority in a conflict |
| --- | --- | --- |
| 0 | External Binding Authority | Applicable law, regulation, signed contractual obligation, or formally binding policy identified and interpreted by the named authorised human or professional authority. It outranks internal documents for the obligation it binds. |
| 1 | Frozen Product Specification | Defines all normative frozen Product Spec content, including product definition, scope, stories, acceptance criteria, Trust Invariants, Global Story Contracts, journeys, state machines, release rules, permissions, canonical error behaviour, and other frozen normative content. |
| 2 | Frozen Implementation Blueprint | Defines implementation and experience translation within the Product Spec. |
| 3 | Approved architecture decision records | Defines how an approved rule is implemented; cannot change what the product does. |
| 4 | External backlog / project tracker | Non-authoritative planning, work-selection, ownership, and progress artifact only; it cannot create, add to, or override Product Spec behaviour. |
| 5 | Historical design, research, review, or prototype documents | Context only unless explicitly promoted through change control. |
| 6 | Agent-generated notes, plans, and suggestions | Non-authoritative working material. |

The Product Spec story section and its canonical acceptance criteria are part
of Rank 1 Frozen Product Specification authority; they are never subordinate
to the Blueprint or an architecture decision. Approved Section 26 change
records are not a competing lower-ranked source: they prepare a new frozen
Product Spec or supply explicitly bounded temporary effective authority only
where Section 26 permits it. An ACTIVE temporary authority takes precedence
only for its explicitly affected IDs, exact temporary conflict-resolution
text, valid effective period, and allowed change class; it does not globally
outrank or rewrite unrelated Product Spec content.

### KlinKlik transitional source mapping

This document is FROZEN and is the Rank 1 internal Product Spec authority.

- Applicable External Binding Authority remains Rank 0 where an obligation
  applies. No external legal or regulatory authority register or authorised
  interpretation was found in the K0A source set; this is an explicit
  OPEN/BLOCKER and must not be inferred.
- K:/new/clinicopus2.md was the current frozen KlinKlik product and architecture
  authority during preparation. Its product-definition, scope, safety, and
  outcome material was input to this Product Spec; its technical
  architecture material is HOW input for the future Blueprint.
- K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md is the canonical source for the
  194 supplied stories and their acceptance criteria during preparation. It
  does not supply the unsupplied epic definitions. After this Product Spec is
  frozen, backlog and tracker material cannot override Rank 1.
- IMPLEMENTATION_BLUEPRINT.md, when later created and frozen, will be
  subordinate Rank 2 and will translate approved Product Spec meaning into
  implementation and experience.
- Approved architecture decision records remain Rank 3 and may define HOW only.
- Existing code and tests are implementation evidence, not product authority.
- Historical blueprints, reviews, prototypes, and superseded story drafts do
  not regain authority.

### Conflict protocol

1. Stop the affected work and identify the conflicting statements.
2. If an external binding obligation is involved, record the conflict or
   blocker and escalate it to the named human, legal, compliance, or domain
   authority. AI agents must not independently interpret ambiguous
   law/regulation and turn that interpretation into product requirements.
3. Preserve both statements in the review or blocker record; do not choose a
   preferred document by convenience.
4. Classify the required change as CLARIFICATION, CORRECTION, ARCHITECTURE
   DECISION, or PRODUCT SCOPE CHANGE under Section 26.
5. Obtain the named owner or approver before changing a frozen authority.
6. Record the resulting decision, effective authority, and validation impact.

An external conflict is updated in the Product Spec only through the
applicable change-control process after the named authority has resolved it.

No agent may resolve a contradiction by selecting whichever document appears
easier to implement. A frozen Product Spec remains the highest INTERNAL
product authority; it does not override applicable external binding authority.

Source authority:

K:/Project-Standards/PROJECT_SPEC_TEMPLATE.md; K:/new/clinicopus2.md; K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md; K:/clinicopus/AGENTS.md; K:/clinicopus/docs/product/blueprint-reference.md.

---

## 2. Executive Product Definition

| Field | Definition |
| --- | --- |
| One-sentence definition | KlinKlik is a Uganda-first Clinic Management System for organisations operating a clinic, pharmacy, or combined clinic-and-pharmacy setting that supports controlled patient-care, dispensing, inventory, billing, and operational workflows. |
| Problem being solved | Clinic operations need a reliable way to move patients through care while preserving trustworthy clinical records, laboratory and pharmacy state, stock truth, financial consistency, privacy, and accountable history across organisation and facility boundaries. |
| Target users | Organisations and facility teams using the supported roles: organisation/facility administrators, reception, nursing/midwifery, clinicians, laboratory staff, pharmacists, store keepers, cashiers, and authorised supervisors. Buyer and commercial-owner details are OPEN. |
| Value proposition | A single operational record connects patient flow, care, investigations, diagnosis, treatment, pharmacy/dispensing, inventory, billing, payments, receipts, and audit outcomes while preventing prohibited or unsafe actions and preserving visible state when work is pending, failed, or unknown. |
| Operating context | Uganda-first clinic operations; organisation-rooted multi-tenancy with facility branches; clinic, pharmacy, and combined modes; low-bandwidth/device-constrained use where supported; UGX/EAT context where applicable; high-impact clinical, stock, money, and final-sign-off actions do not complete offline. |
| Product character | Operational, conservative, auditable, privacy-preserving, and practical for low-bandwidth clinic work. |
| Business / commercial context | OPEN — pricing, buyer, and revenue model are not established in the current authority set. |
| Explicit exclusions | The current V1 boundary excludes or defers capabilities identified in the authoritative scope and open-decision records; see the Section 4 summary and the canonical detailed Section 25 register. |

KlinKlik is one platform for clinic, pharmacy, and combined clinic-and-pharmacy
operations. The V1 authority names capability groups covering identity and
tenancy, reception and patient flow, consultation and encounters,
investigations/laboratory, diagnosis and treatment/prescribing, pharmacy and
dispensing, inventory, billing and payment, receipts, appointments, reporting,
and ANC, subject to the applicable validation gates.

This foundation does not claim that every referenced epic is fully specified.
Only the 194 supplied stories in the canonical backlog and the current
authoritative blueprint material are represented; unsupplied epic references
remain gaps.

Source authority:

K:/new/clinicopus2.md §§1, 3–7, 9–10, 12–31, 44–48; K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §§2–5; K:/clinicopus/docs/product-rename.md.

---

## 3. Product Goals

Goals have stable IDs and are measurable or behaviourally meaningful.

| ID | Goal | Measure or observable outcome | Release | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| G1 | Safe end-to-end patient care workflow | Supported patients can move through identity, check-in, queue, triage, consultation, and service completion with required authority and state checks; invalid or unsafe transitions are rejected. | V1 | OPEN | PROPOSED |
| G2 | Reliable clinical records | Authorised users can create, sign, and amend supported clinical records while final history remains attributable and cannot be silently rewritten. | V1 | OPEN | PROPOSED |
| G3 | Medication, pharmacy, and inventory integrity | Expired medicine is not sold or dispensed; unsupported controlled/Class A medicine is blocked in baseline V1; stock and dispensing outcomes remain physically and operationally consistent. | V1 | OPEN | PROPOSED |
| G4 | Financial consistency | Charges, invoices, payments, allocations, receipts, and applicable shifts remain internally consistent and material financial history is not silently mutated. | V1 | OPEN | PROPOSED |
| G5 | Organisation/facility isolation and privacy | Users can access only the organisation and facility data permitted by authoritative rules; protected data is minimised and not exposed through inappropriate operational records. | V1 | OPEN | PROPOSED |
| G6 | Practical low-bandwidth usability | Supported roles can understand and complete supported workflows on constrained devices/connectivity with clear empty, loading, pending, failure, and unknown outcomes; unsupported high-impact offline completion is not enabled. | V1 | OPEN | PROPOSED |
| G7 | Accountable and auditable operation | Material actions are attributable, auditable, and governed by explicit permissions, approvals, validation gates, and recoverable correction paths. | V1 | OPEN | PROPOSED |

No unsupported numerical targets are asserted. Quantitative targets remain OPEN
unless supplied by an approved authority record.

Source authority:

K:/new/clinicopus2.md §§3, 5, 7, 9, 11–12, 15, 19–22, 25–27, 31–35, 42–44, 53–59; K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §§2–4, 7, 22–30; K:/clinicopus/AGENTS.md.

---

## 4. Non-Goals / Scope Boundary Summary

This section is a navigation summary, not a second detailed exclusion
inventory. Section 25 — Out-of-Scope Register — is the one canonical detailed
source for exclusions, deferrals, rejected ideas, and possibilities requiring
re-chartering. Use the same OOS IDs here and in Section 25; do not retype the
complete behaviour or rationale in this summary.

| Category | High-level boundary summary | Canonical OOS IDs in Section 25 |
| --- | --- | --- |
| Permanently out of scope | Any mechanism that allows expired KlinKlik-managed stock to become usable, issued, dispensed, sold, or used through an override is permanently excluded. Quarantine, disposal/write-off, and safe correction paths remain permitted safety outcomes. | OOS-01, OOS-06 |
| Current V1 out of scope / safety boundaries | Controlled/Class A workflows, clinical decision support/automatic interpretation, and offline high-impact finalisation are not V1 behavior. These remain release/safety boundaries, not silently permanent exclusions. | OOS-05, OOS-07, OOS-09 |
| Explicitly deferred | V1.1, Phase 2, and Phase 3 capability groups, plus any other capability groups explicitly marked deferred by current authority; missing detail alone is not deferral. | OOS-02 (OPEN) |
| Rejected ideas | No new rejected-idea record is created here. Superseded drafts and conflicting proposals do not regain authority. | OOS-03 (OPEN) |
| Future possibilities requiring re-chartering or missing authority | External-provider effects, Journey F, unsupplied epics, and other capabilities requiring unresolved clinical, pharmacy, legal, regulatory, pilot, or product authority require later authority and a new/superseding Product Spec where applicable. | OOS-04, OOS-08, OOS-10, OOS-11 |
| Story-level OOS traceability | Story-specific exclusions remain binding in their stories without creating additional top-level exclusions by convenience. | OOS-12 |

If Section 4 and Section 25 disagree, the specification is internally
inconsistent and fails self-review. Section 25 remains the canonical detailed
source unless it is changed through approved change control. Section 4 must
normally be reconciled to the canonical Section 25 record. If the canonical
Section 25 record itself is wrong, correct Section 25 through the applicable
change-control process and then update the summary. Never create two
competing OOS meanings for the same OOS ID. Implementation agents must not
promote a non-goal into a feature because it would be convenient or
technically nearby.

The Section 25 detailed register is populated in Q5 and is the canonical
detailed record for the OOS IDs shown above. The summary remains navigation
only and does not duplicate the detailed behavior or rationale.

Referenced unsupplied epics are specification/authority gaps. Missing stories
or acceptance criteria do not by themselves classify a capability as deferred;
release placement follows existing authoritative KlinKlik decisions. Where
current authority places a capability in V1 but the specification is
incomplete, it remains a V1 dependency/gap and may be BLOCKED until sufficient
authority is supplied. No missing behaviour may be invented.

Source authority:

K:/Project-Standards/PROJECT_SPEC_TEMPLATE.md §4/§25; K:/new/clinicopus2.md §§6, 44–48, 55; K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §§4, 27–29, 31–32.

---

## 5. Product Principles

Use principles to resolve ordinary design choices without creating hidden
product requirements. Mark a category NOT APPLICABLE when it genuinely does not apply;
do not hard-code domain-specific rules into this generic template.

| Category | Principle ID | Project principle | Observable implication | Priority |
| --- | --- | --- | --- | --- |
| Correctness | PP-01 | KlinKlik preserves correct, authoritative patient, clinical, stock, and financial meaning. | Invalid or unsafe transitions are rejected, and users are not shown silently inconsistent material state. | MUST |
| User trust | PP-02 | KlinKlik does not silently lose, rewrite, conceal, or overstate material work. | Final history, pending work, failures, unknown outcomes, and correction paths remain visible and attributable. | MUST |
| Simplicity | PP-03 | Supported workflows remain understandable and bounded to approved product scope. | Users are not led into unsupported behaviour or hidden assumptions; scope gaps are explicit. | SHOULD |
| Server authority | PP-04 | The server is authoritative for protected behaviour and state. | Permissions, protected transitions, and final outcomes cannot be safely overridden by an untrusted client or local assumption. | MUST |
| Privacy | PP-05 | Collect, reveal, retain, and transmit only what the product requires. | Organisation/facility boundaries are enforced, PHI exposure is minimised, and sensitive values are not placed in inappropriate logs or telemetry. | MUST |
| Accessibility | PP-06 | Core tasks remain operable and understandable for supported users and devices. | Core workflows, status, errors, and required actions remain perceivable and operable. | MUST |
| Performance | PP-07 | Performance targets are explicit and testable where they matter. | No numerical target is invented; an approved target remains a visible acceptance obligation when one exists. | SHOULD |
| Low-bandwidth operation | PP-08 | Core supported workflows remain practical under constrained connectivity, without pretending that high-impact work can safely complete offline. | The product makes pending, failure, and unknown states clear and does not enable offline completion of stock, money, dispensing, or final clinical sign-off. | MUST |
| Architecture restraint | PP-09 | Technical convenience must not add product behaviour, scope, or a weaker trust guarantee. | Implementation choices preserve the approved observable outcome and return unresolved scope or authority questions for decision. | MUST |

Source authority:

K:/new/clinicopus2.md §§3, 5, 7, 11, 19, 22, 31–35, 42–43, 53–59; K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §§2, 4, 7, 22–30; K:/clinicopus/AGENTS.md.

---

## 6. Release Strategy

Release names are project-defined. Pilot, V1, Commercial V1, and Phase 2 are
examples, not required names.

| Release | Purpose | Included capabilities | Excluded capabilities | Entry gates | Exit gates | Dependencies |
| --- | --- | --- | --- | --- | --- | --- |
| V1 | Current implementable “Run the Day” release. | Authority-named groups: organisation/facility tenancy and access; patient identity; reception/check-in/queue; triage; consultation/encounters; diagnosis and treatment/prescribing; small laboratory; pharmacy POS/dispensing/batch stock; direct receiving; basic stock counts/controlled adjustment; billing/payment allocation; receipts and shifts; simple appointments; printing/reports; complete ANC where applicable gates are satisfied. Detailed supplied story behaviour is limited to the 194 canonical backlog stories. | V1.1/Phase 2/Phase 3 groups; unsupported controlled/Class A medicines; expired-stock override; clinical decision support/automated interpretation; offline completion of high-impact actions; unsupplied epics are not treated as complete behaviour. | Applicable clinical, pharmacist, legal/regulatory, privacy, pilot, and product validation gates in blueprint §53; unresolved authority is BLOCKED. | Product acceptance, trust/security/regression, implementation readiness, and named approvals; exact project gate records remain OPEN where not established. | K:/new/clinicopus2.md §§44, 53–55; canonical backlog; external authority records; unsupplied stories; open decisions; implementation evidence. |
| V1.1 / Phase 2 / Phase 3 (context only) | Later capability context, not current implementation scope. | Only later-release groups explicitly named in blueprint §§45–47; no additional behaviour is invented here. | No permission to implement future capability under this V1 Product Spec; any unselected or unresolved capability remains deferred or BLOCKED. | A new or superseding frozen Product Spec version and applicable authority/validation gates. | Release-specific product, trust, operational, and implementation readiness gates. | Bernard change control; closure of relevant open decisions and external/clinical/pharmacy/legal gates. |

Missing detailed story authority does not itself move an authority-supported
capability out of V1; it remains a specification gap/dependency and is not
implementation permission until sufficiently defined.

Each release must state what is deliberately absent. A capability may not
move between releases without change control and an updated readiness review.

Document Control must distinguish the CURRENT IMPLEMENTABLE RELEASE from
FUTURE RELEASES DESCRIBED FOR CONTEXT. Future-release material may be canonical
roadmap context, but it is not permission to implement until it is selected as
the current release through the applicable authority and change-control
process. Current-release stories and acceptance criteria are the canonical
implementation scope.

Source authority:

K:/new/clinicopus2.md §§6, 44–48, 53–59; K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §§6, 27–30, 32; K:/clinicopus/docs/REPO_REVIEW_HANDOFF.md.

---

## 7. Personas / Actors

These are the supplied product actors. A person may hold multiple active
organisation/facility/department grants, subject to the separation rules below.
The software role is not, by itself, professional, business, contractual, or
legal authority; credentials and the applicable authority decisions remain
separate.

| ID | Persona / actor | Human or SYSTEM | Role ID | Goals | Constraints | Risk / authority level | Release |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P-01 | Platform administrator | HUMAN | SYS_ADMIN | Support platform operation and tenant setup | No clinical or financial authority by default; support boundary applies | HIGH platform authority, not business authority | V1 |
| P-02 | Organisation owner | HUMAN | ORG_OWNER | Govern the organisation tenant and subscription | Organisation scope; must not infer professional authority | HIGH tenant authority | V1 |
| P-03 | Organisation administrator | HUMAN | ORG_ADMIN | Configure organisation users, facilities, and enabled capabilities | Organisation scope; no automatic clinical/legal authority | HIGH tenant administration | V1 |
| P-04 | Facility administrator | HUMAN | FACILITY_ADMIN | Operate a branch and its queues, staff, and settings | Facility scope; cannot cross organisation boundary | HIGH facility administration | V1 |
| P-05 | Authorised supervisor | HUMAN | SUPERVISOR | Make approved in-facility overrides, approvals, takeovers, CashierShift force-close decisions, and explicitly supplied Visit-closure decisions | Only configured facility scope and approved business authority; no general Visit force-close authority exists | HIGH operational authority | V1 |
| P-06 | Reception / front desk | HUMAN | RECEPTIONIST | Register patients, check in, schedule, and support front desk work | Never clinical; only granted operational/financial actions | MEDIUM operational authority | V1 |
| P-07 | Nurse / triage | HUMAN | NURSE | Triage, record vitals, allergies, and procedures, and manage queue work | No diagnosis, prescription, or clinical sign-off unless separately authorised | HIGH clinical-data risk | V1 |
| P-08 | Midwife | HUMAN | MIDWIFE | Deliver the approved ANC workflow and documentation | ANC authority and credential decisions remain OPEN/BLOCKED where validation is required | HIGH clinical-data risk | V1 |
| P-09 | Clinician | HUMAN | CLINICIAN | Clerk, diagnose, treat, prescribe, and sign clinical records | Credential-gated; no invented scope beyond approved product decisions | HIGH clinical authority risk | V1 |
| P-10 | Laboratory technician | HUMAN | LAB_TECH | Collect specimens and enter laboratory results | Facility/permission scope; verification/release is separate unless explicitly configured | HIGH clinical-data risk | V1 |
| P-11 | Laboratory verifier / in-charge | HUMAN | LAB_VERIFIER | Verify and release results | Must satisfy the configured verification and separation rule | HIGH clinical-data risk | V1 |
| P-12 | Pharmacist | HUMAN | PHARMACIST | Dispense, manage pharmacy catalogue, and perform approved stock work | Credential-gated; expired and controlled/Class A medicine remain blocked | HIGH medication/stock risk | V1 |
| P-13 | Store keeper | HUMAN | STORE_KEEPER | Receive goods, record movements, and submit counts | Append-only stock movement rules; approval may be separate | HIGH stock/financial risk | V1 |
| P-14 | Cashier | HUMAN | CASHIER | Collect payments, manage shifts, and issue receipts | Refund, reversal, discount, void, and approval powers are separately bounded | HIGH financial risk | V1 |
| P-15 | Manager / accountant | HUMAN | OPEN — exact technical role identifier not supplied | Review approved management and accounting information | Exact role/capabilities require authority decision; cannot be inferred from title | HIGH financial/privacy risk | V1 |
| P-16 | Automated platform actor | SYSTEM | SYSTEM | Run approved gates, status sweeps, reminders, and fan-out | Only deterministic, audited system actions; no invented authority | HIGH systemic impact | V1 |

Role grants are additive only where the capability and scope rules allow them.
The product must make these separation pairs separable and visible: payment
collection versus refund issuance; stock-adjustment request versus approval;
count submission versus approval; permission grant versus use; and support
access request versus approval. Small facilities may combine roles, but that
combination must remain visible and configurable. Credential-gated actions
refuse missing, expired, uncertain, or unverified credentials; for V1 clinical signing, an expired, missing, or uncertain clinical credential blocks signing while OD-04 remains OPEN. This is a default-deny Product Spec safety outcome, not a legal conclusion;
no qualification is invented here. A SYSTEM actor is not
a human approver and does not create professional or legal authority.

Source authority:

K:/new/clinicopus2.md §§7, 9–10, 31, 53–55; K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §§3–4, 7 and REC-001, REC-012, TRI-001, TRI-008, ENC-017, LAB-016, INV-005, PAY-014, RCP-001, ANC-001; K:/clinicopus/AGENTS.md.

---

## 8. Governance / Authority Model

Software permissions express an approved capability; they do not create
business, professional, contractual, legal, or organisational authority.
Authority owners, credential decisions, and external interpretations remain
explicit and unresolved where the supplied sources leave them unresolved.

### Business authority

| Decision / action | Business authority | Software capability that expresses it | Required assurance | Delegation / revocation rule |
| --- | --- | --- | --- | --- |
| Organisation membership, facility and module administration | ORG_OWNER / ORG_ADMIN under approved organisation policy | organisation.manage, facility.manage, module configuration | Authenticated member, organisation scope, audit | Grant/revoke by authorised organisation owner/admin; no cross-organisation grant |
| Patient registration, identity, check-in, and queue | RECEPTIONIST / FACILITY_ADMIN; clinical roles where the supplied story permits | patient.register, visit.create, queue capabilities | Organisation and facility scope; identity and duplicate checks | Facility-scoped grant; revoke before next required check |
| Triage, vitals, allergies, and procedures | NURSE; MIDWIFE where ANC scope applies | triage.create, triage.amend within stated scope | Facility/permission scope; audit; amendment rule | Own-record amendment versus supervisor/facility-admin any-record path remains separate |
| Clinical note, diagnosis, treatment, prescription, and sign-off | CLINICIAN / MIDWIFE only where the approved workflow and credential permit | Clinical documentation and prescription capabilities | Valid current credential, facility/permission scope, and signing/immutable-record rules; an expired, missing, or uncertain clinical credential blocks V1 signing while OD-04 is OPEN; this is a Product Spec default-deny outcome, not a legal conclusion | Credential and grant revocation block the next protected action; no admin substitution |
| Laboratory collection, entry, verification, and release | LAB_TECH; LAB_VERIFIER for verification/release | lab.* capabilities | Facility scope, verification/separation configuration, audit | Verification authority separately grantable and revocable |
| ANC workflow | MIDWIFE / CLINICIAN subject to clinical validation | ANC capabilities | Contracted clinical-advisor decisions remain OPEN/BLOCKED | No ANC authority inferred from a title alone |
| Dispensing, catalogue, and pharmacy operations | PHARMACIST; STORE_KEEPER for approved stock operations | pharmacy.*, stock.* capabilities | Valid pharmacy credential; expiry and controlled/Class A blocks | Revoke credential/grant; never bypass blocked medicine rules |
| Goods receipt, stock movements, counts, adjustments, and approvals | STORE_KEEPER and separately authorised supervisor/facility admin | Append-only stock and approval capabilities | Segregation of request/approval and immutable audit | Requester/approver separation visible; revoke both independently |
| Payment collection, shifts, and receipts | CASHIER; PHARMACIST for approved retail receipt path | payment.record, receipt.generate, shift capabilities | Facility scope, payment state, audit and visible separation | Collection does not confer reversal/refund authority |
| Reversal, refund, discount, void, credit, debt, CashierShift force-close, and explicitly supplied Visit-closure decisions | Qualified supervisor/facility authority under approved policy; exact legal/financial authority OPEN where unresolved | Privileged finance and explicitly supplied closure capabilities; no general Visit force-close capability | Explicit approval, exact state rules, audit, separation of duties | Separate grant and approval; revocation blocks new actions |
| Reporting and audit review | ORG_OWNER / ORG_ADMIN / FACILITY_ADMIN or approved reporting role | Reporting and audit-read capabilities | Scope, sensitivity, immutable evidence | Scope and role revocation apply to subsequent access |
| Status sweeps, gates, reminders, and fan-out | SYSTEM only for specified deterministic actions | System capabilities | Deterministic rule, idempotency, audit | System cannot approve a human business or professional decision |

### Platform boundaries

- Organisation is the tenant root; Facility is a branch, not a tenant.
- Default deny, explicit scope, credential, state, and assurance checks apply
  to every protected capability.
- A role label never substitutes for professional qualification, business
  approval, contractual authority, or legal interpretation.
- The product must refuse cross-organisation access, expired or controlled/
  Class A medicine, unsigned final clinical records, silent financial/stock
  rewrites, and any behaviour prohibited by an unresolved blocking decision.
- The product does not invent clinical decision support, regulatory meaning, or
  an external legal obligation.

### Contractual / legal decisions

| ID | Decision | Authority / owner | Status | Required review |
| --- | --- | --- | --- | --- |
| OD-P1–OD-P9 | Product scope, V1 boundary, subscription, and product-policy decisions | Product owner | OD-P1 APPROVED; OD-P2–OD-P9 OPEN / BLOCKED as marked in the source | Product-owner decision before each affected gate |
| OD-C1–OD-C12 | Clinical, ANC, wording, thresholds, and care-workflow decisions | Contracted clinical advisor | OPEN / BLOCKED | Clinician validation before affected gate |
| OD-PH1–OD-PH9 | Pharmacy, dispensing, catalogue, and pharmacy pilot decisions | Contracted pharmacist advisor | OPEN / BLOCKED | Pharmacist validation before affected gate |
| OD-L1–OD-L8 | Legal, privacy, retention, HMIS, fiscal, and regulatory decisions | Ugandan counsel + DPO | OPEN / BLOCKED | Legal/regulatory validation before affected gate |
| OD-R1–OD-R9 | Pilot, rollout, and operational-readiness decisions | Product/pilot owner | OPEN / BLOCKED | Pilot owner decision before affected release |
| OD-T1–OD-T3 | Technical decisions that require product-authority confirmation | Engineering lead with product authority | OPEN | Product/engineering review before dependent implementation |
| OD-18–OD-22 | Existing cross-cutting open decisions | Existing named owners in the source | OPEN / BLOCKED | Resolve through the existing decision record; do not duplicate |

### External Binding Authority Register

This compact register is the canonical index of identified binding external
authority. No external binding authority source has been supplied for this
Product Spec. The register state is **REGISTER NOT YET POPULATED — AUTHORITY SOURCES
REQUIRED; applicability unresolved**. No law, regulation, contract, or policy
is invented here, and no entry is treated as a declaration that no authority
applies. This is not AI legal analysis and is not a separate legal document.

| External Authority ID | Exact source / citation / version | Effective date / applicability date | Authorised human / professional interpreter | Stable authorised-interpretation reference | Interpretation / approval date | Affected Product Spec IDs | Status | Blocks implementation? | Superseded by / review trigger | Last reviewed | Monitoring owner | Next review date / monitoring trigger |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EBA-00 | NONE SUPPLIED — exact source required | UNKNOWN | OPEN — authorised interpreter required | NONE | UNKNOWN | OPEN — affected areas/IDs | INTERPRETATION REQUIRED | YES where the unresolved source governs the affected gate | Authoritative source, applicability, or supersession review | NOT REVIEWED | Ugandan counsel + DPO once appointed | Before any affected decision or gate |

Agents never independently interpret ambiguous law, regulation, contract, or
binding policy. Rank 0 in Section 1 continues to apply. When an authoritative
source is supplied, record its exact citation/version, applicability date,
authorised interpretation, affected IDs, monitoring owner, and review trigger.
An overdue required review makes the affected entry INTERPRETATION REQUIRED;
it does not erase the obligation. New dependent decisions are BLOCKED where
authority remains unresolved. Existing handling follows authorised risk and
legal paths, never agent guesswork. A supporting interpretation artifact is
not a third canonical product document.

### Unresolved authority decisions

| ID | Question | Owner | Blocks which behaviour | Status |
| --- | --- | --- | --- | --- |
| OD-P1–OD-P9 | Which product-policy and V1 boundary decisions are approved? | Product owner | Affected scope, subscription, and release behaviour | OD-P1 APPROVED; OD-P2–OD-P9 OPEN / BLOCKED |
| OD-C1–OD-C12 | Which clinical and ANC rules are authorised? | Contracted clinical advisor | Affected clinical/ANC behaviour | OPEN / BLOCKED |
| OD-PH1–OD-PH9 | Which pharmacy rules and pilot gates are authorised? | Contracted pharmacist advisor | Affected pharmacy behaviour | OPEN / BLOCKED |
| OD-L1–OD-L8 | Which legal, privacy, retention, fiscal, and regulatory obligations apply? | Ugandan counsel + DPO | Affected legal/privacy/regulatory behaviour | OPEN / BLOCKED |
| OD-R1–OD-R9 | Which pilot and operational-readiness conditions are met? | Pilot owner | Affected pilot/release behaviour | OPEN / BLOCKED |
| OD-T1–OD-T3 | Which technical choices have required product authority? | Engineering lead + product owner | Dependent implementation | OPEN |
| OD-18–OD-22 | What do the existing cross-cutting open records require? | Their existing named owners | Referenced capabilities | OPEN / BLOCKED |
| AUTH/TEN/USR | What are the missing authentication, tenancy, and user-management stories and authority rules? | Product owner + authorised domain owners | Dependent capabilities | PARTIAL / OPEN / BLOCKED |

Unresolved authority questions must remain visible; implementation agents may
not turn them into default permissions or silently create a duplicate decision
record. A change to a software capability does not itself change its governing
business or external authority.

Source authority:

K:/new/clinicopus2.md §§7–10, 31, 53–55; K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §§3–4, 7, 31–31.2; K:/clinicopus/AGENTS.md.

---

## 9. Permission / Capability Model

The default is DENY. Every protected operation requires an identified actor,
verified organisation/facility scope, an explicitly granted capability, and
the required resource, state, credential, approval, and assurance context.
Missing capability, scope, state, or assurance never becomes permission by
convenience.

| Identity / actor | Tenant or organisation context | Capability | Resource scope | State / assurance requirements | Default |
| --- | --- | --- | --- | --- | --- |
| ORG_OWNER / ORG_ADMIN | Organisation membership | Organisation and facility administration | Their organisation only | Active membership, approved authority, audit | DENY |
| FACILITY_ADMIN | Organisation membership and facility grant | Facility operations and configuration | Granted facility | Active grant, facility scope, audit | DENY |
| RECEPTIONIST / FACILITY_ADMIN / NURSE where the story permits | Organisation and facility | Patient registration, visit creation, check-in | Organisation patient and granted facility | Identity/duplicate checks; no clinical fields for front desk | DENY |
| RECEPTIONIST / authorised operational role | Organisation and facility | Queue read, appointment/check-in support | Granted facility queue | Active grant and facility scope | DENY |
| NURSE / MIDWIFE | Organisation and facility | Triage, vitals, allergy, and procedure recording | Granted facility and permitted record | Active role, record state, audit; amendment limits | DENY |
| CLINICIAN / MIDWIFE | Organisation and facility | Clinical note, diagnosis, treatment, prescription, and sign | Permitted patient/encounter | Valid current credential, workflow state, sign-off and immutable-record rules; an expired, missing, or uncertain clinical credential blocks V1 signing while OD-04 is OPEN; this is a Product Spec default-deny outcome, not a legal conclusion | DENY |
| NURSE / SUPERVISOR / FACILITY_ADMIN | Organisation and facility | Triage amendment within the supplied separation rule | Own or explicitly permitted records | Record state, reason, audit, and any-record authority where granted | DENY |
| LAB_TECH | Organisation and facility | Specimen collection and result entry | Granted facility laboratory work | Order/specimen state, audit, and no self-release unless configured | DENY |
| LAB_VERIFIER | Organisation and facility | Laboratory verification and release | Granted facility laboratory work | Verification authority, separation/configuration rule, audit | DENY |
| PHARMACIST | Organisation and facility | Dispense and approved pharmacy operations | Granted facility prescription, patient, catalogue, and stock scope | Valid credential; prescription/allergy state; expiry and controlled/Class A blocks | DENY |
| STORE_KEEPER / authorised approver | Organisation and facility | Goods receipt, append-only movements, count, adjustment request/approval | Granted facility stock | State, requester/approver separation, audit | DENY |
| CASHIER / PHARMACIST where the story permits | Organisation and facility | Payment record, shift, and receipt generation | Granted facility invoice/order | Payment state, audit, visible separation | DENY |
| SUPERVISOR / FACILITY_ADMIN or other approved finance authority | Organisation and facility | Reversal, refund, discount, void, credit, debt, CashierShift force-close, or an explicitly supplied Visit-closure action | Explicitly affected facility records | Exact state, approval, separation, audit, and unresolved-authority gates; no general Visit force-close permission | DENY |
| ORG_OWNER / ORG_ADMIN / FACILITY_ADMIN or approved reporting role | Organisation and facility | Reports and audit review | Scope- and sensitivity-bounded records | Active grant, scope, sensitivity, audit | DENY |
| SYSTEM | Explicit target organisation/facility context | Approved status gates, sweeps, reminders, and fan-out | Only the records named by the rule | Deterministic rule, idempotent result, audit; no human authority | DENY |

### Optional Role × Capability matrix

| Capability | Role coverage | Scope / notes |
| --- | --- | --- |
| Supplied story capabilities | See the capability rows and canonical story Perm fields | An exhaustive role matrix is not asserted while AUTH/TEN/USR stories remain unsupplied |

Define:

- what identity proves who is acting, without inventing missing AUTH/TEN/USR
  behaviour;
- how organisation, facility, department, patient, and other scope is selected
  and verified;
- which capabilities are conditional on record state, approval, credential,
  separation, or an unresolved authority decision;
- missing capability is denied; an actor outside the organisation boundary is
  not exposed; a requested facility outside the actor's scope is not exposed;
- a disabled module is absent from the actor's available product surface, and
  a missing subscription or entitlement remains denied;
- presentation gates are convenience only; product authority is enforced by
  the authoritative product enforcement boundary;
- how authority is revoked and how active sessions, in-flight work, queued
  work, links, and cached decisions react.

### Unsupplied AUTH / TEN / USR behaviour

The canonical backlog supplies no complete AUTH, TEN, or USR story definitions.
This Product Spec does not reconstruct authentication, tenancy-management, or
user-management workflows from implementation or convention. Dependent
identity, membership, invitation, login, recovery, role-administration, and
session semantics remain PARTIAL / OPEN / BLOCKED as applicable. Missing
stories are not silently treated as feature absence or permission.

### Authority revocation propagation

For every revocable capability or authority, record the maximum acceptable
propagation time and the effect of revocation on each channel below. Do not
prescribe a particular authentication technology.

| Revocable authority / capability | Maximum propagation time | Active sessions | Access tokens | Long-running / in-flight requests | Queued / scheduled jobs | Temporary / pre-signed links | Cached authority decisions | Enforcement / regression evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Organisation membership or facility/department grant | OPEN — maximum not supplied | Stop at the next required protected-action check | OPEN — channel behaviour not supplied | Recheck before a protected side effect | Recheck before execution | OPEN — channel/expiry behaviour not supplied | OPEN — cache behaviour not supplied | OPEN — Section 18 evidence and gate required |
| Clinical, laboratory, pharmacy, or other professional credential | OPEN — maximum not supplied | Block the next credential-gated action | OPEN — channel behaviour not supplied | Recheck before protected completion | Recheck before execution | OPEN — channel/expiry behaviour not supplied | OPEN — cache behaviour not supplied | OPEN — credential regression evidence required |
| Support or exceptional access grant | OPEN — maximum not supplied | End at the next required scope/authority check | OPEN — channel behaviour not supplied | Recheck before protected disclosure or mutation | Recheck before execution | OPEN — channel/expiry behaviour not supplied | OPEN — cache behaviour not supplied | OPEN — access-review evidence required |

Unknown maximums and channel behaviours remain OPEN; they are not guessed.
Material revocation guarantees must map to trust and regression coverage.

Source authority:

K:/new/clinicopus2.md §§7–10, 31–33, 53–55; K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §§3–4, 7, 31–31.2 and REC-001, REC-012, TRI-001, TRI-008, ENC-017, LAB-016, INV-005, PAY-014, RCP-001, ANC-001; K:/clinicopus/AGENTS.md.

---

## 10. Domain / Tenancy Model

Organisation is the tenant root. Facility is an operational branch and is not
a tenant. The model retains those product boundaries even if an initial
deployment has only one organisation.

| Entity / dimension | Global or scoped | Owner | Identity boundary | Read / write boundary | Segregation rule |
| --- | --- | --- | --- | --- | --- |
| User identity | GLOBAL identity with organisation memberships | User / authorised identity owner | One identity may have one or more explicit organisation memberships | Identity administration is bounded by the governing organisation/user authority | No membership means no organisation data exposure |
| Organisation | ORGANISATION / tenant root | ORG_OWNER and authorised organisation governance | Organisation is the primary tenant boundary | Organisation-owned settings, members, subscription, and entitlements | Cross-organisation reads and writes fail closed |
| Facility / branch | FACILITY within an organisation | FACILITY_ADMIN under organisation authority | Must belong to exactly one organisation | Facility operations, queues, departments, and facility-scoped records | Facility is not a tenant; never crosses organisation boundary |
| Department | DEPARTMENT within a facility | Facility authority | Bound to its facility and organisation | Queue and revenue attribution within facility | No department grant expands organisation or facility scope |
| Patient identity | ORGANISATION where supplied authority supports it; facility/home-facility semantics OPEN | Organisation clinical/business authority | Patient identity is organisation-scoped where supplied authority supports it | Registration and identity edits follow supplied patient/registration authority | Cross-organisation identity linking, matching, deduplication, and transfer semantics are not invented |
| Clinical and ANC records | FACILITY plus patient organisation and explicit applicable authority | Clinical authority | Organisation patient; care facility and permission scope | Read/write only in permitted care and record state | Cross-facility reads fail closed unless specifically authorised by applicable BRN authority |
| Laboratory work and results | FACILITY plus patient organisation and permission | Laboratory authority | Facility laboratory scope | Collection, entry, verification, and release follow capability/state | No cross-organisation exposure; verification remains bounded |
| Prescription, dispensing, catalogue, batches, and stock | FACILITY within organisation | Pharmacy/stock authority | Facility and organisation scope | Pharmacy and append-only stock capabilities | Expired and controlled/Class A medicine remain blocked |
| Invoices, payments, receipts, and shifts | FACILITY within organisation | Finance authority | Facility and organisation scope | State- and capability-bounded financial actions | No cross-facility or cross-organisation write by implication |
| Subscription, entitlement, and module enablement | Organisation owner; module enabled per facility | Organisation governance | Organisation subscription; facility enablement | Organisation billing/entitlement and facility module decisions | Disabled module is not available in that facility |
| Audit and access-review evidence | Organisation and relevant facility context | Organisation/platform authority | Retains actor, organisation, facility, and action context | Append/audit review according to sensitivity and authority | Evidence cannot be used to broaden data scope |
| SYSTEM-derived work | Explicit organisation/facility target from the governing rule | SYSTEM within approved rule | Target context is explicit and bounded | Only named status/gate/sweep/fan-out records | SYSTEM never crosses scope or creates human authority |

### Required decisions

- Global entities: user identity and SYSTEM behaviour only where the
  AUTH/TEN/USR authority decisions define them; those decisions remain OPEN.
- Organisation-owned entities: memberships, subscription/entitlement,
  organisation settings, patient identity, and organisation audit context.
- Facility dimension: every branch operation and facility-owned clinical,
  laboratory, pharmacy, stock, appointment, invoice, payment, receipt, and
  shift record remains inside its organisation.
- Ownership and transfer rules: organisation/facility ownership, membership,
  patient home-facility changes, and record transfers require the existing
  authority decisions; agents may not infer them.
- For the currently supplied canonical stories, cross-facility reads fail
  closed. A specific same-organisation read may be permitted only where an
  explicitly authorised external BRN cross-facility-sharing policy grants its
  dedicated capability; it remains audited and must not expose hidden
  cross-facility record existence. BRN-003, BRN-004, BRN-005, and BRN-006 are
  referenced but UNSUPPLIED dependencies.
- K:/new/clinicopus2.md contains the OD-P3 /
  HOME_FACILITY_WITH_SEARCH direction, but OD-P3 remains OPEN. It is therefore
  not a settled default in this Product Spec. Minimal-stub discovery,
  request-access behaviour, and any immutable stub floor are not defined here.
  OD-P3 and the relevant BRN authority may later be reconciled through Product
  Spec authority/change control.
- PAT stories are UNSUPPLIED dependencies. Beyond the organisation-scoped
  patient identity stated above, facility/home-facility, cross-organisation
  identity linking, matching, deduplication, and transfer behaviour are not
  invented.
- Cross-organisation access always fails closed. A missing organisation,
  facility, department, patient, or capability scope is not guessed or
  broadened by an administrator title.
- Single-tenant simplification: an initial one-organisation deployment does
  not remove the organisation boundary; no extra tenant dimension is invented.

Cross-scope access must be explicit, authorised, auditable, and bounded. Never
use a broad administrator role as a substitute for a scope decision. Product
Spec meaning is expressed here conceptually; implementation mechanisms are
defined only by the subordinate Blueprint.

Source authority:

K:/new/clinicopus2.md §§7–10, 31–33, 53–55; K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §§3–4, 7, 31–31.2; K:/clinicopus/AGENTS.md.

---

## 11. Trust / Safety Invariants

An invariant is a property whose violation may make the product unsafe,
untrustworthy, or commercially unacceptable. Invariants have stable IDs,
explicit enforcement, and permanent regression coverage.

| ID | Invariant type | Invariant statement | Violation impact | Enforcement point | Regression gate | Releases |
| --- | --- | --- | --- | --- | --- | --- |
| TI-01 | Organisation and authorised-scope isolation | A protected read or action may occur only within the verified organisation and explicitly authorised facility, department, patient, object, and configuration scope. Supplied-story cross-facility access fails closed unless an explicitly authorised same-organisation BRN capability applies; cross-organisation access never gains that exception. | Cross-tenant or unauthorised disclosure or mutation of clinical, financial, stock, or operational data. | Organisation, facility, and protected-object access boundary. | RG-01 | V1 |
| TI-02 | Server-authoritative protected behaviour | A protected outcome is decided from authoritative identity, authority, state, and applicable configuration. Missing, expired, uncertain, or revoked authority denies the action; presentation controls and client context cannot grant it. | An unauthorised actor or stale client could perform a protected action. | Protected action and state-transition boundary. | RG-02 | V1 |
| TI-03 | Final clinical-history correction integrity | A signed clinical record remains preserved and is not destructively rewritten or deleted. A correction uses the defined attributed amendment, addendum, or entered-in-error path while retaining the prior history. | Loss of clinical provenance, unsafe treatment context, or an unreconstructable correction. | Clinical signing, amendment, and error-correction boundary. | RG-03 | V1 |
| TI-04 | Released laboratory-result integrity | An unverified result is not clinically released. A correction after release preserves the released history and creates the defined attributable amended result and required review/notification outcome. | A clinician could act on an unverified, silently changed, or untraceable result. | Laboratory verification, release, and amendment boundary. | RG-04 | V1 |
| TI-05 | Expired KlinKlik-managed medicine prohibition | Expired KlinKlik-managed medicine cannot be sold, dispensed, issued, or used through any supported path. No role, configuration, permission, reason, or override may permit it. Expiry is rechecked at the confirmation boundary; an expired item is refused, and only quarantine, disposal, or an auditable correction path may follow. Blocked attempts and all quarantine, disposal, and correction activity remain auditable. | Patient harm, false stock truth, and an unsafe medicine-handling outcome. | Medicine receipt, preparation, confirmation, sale, dispensing, issue, quarantine, and disposal boundary. | RG-05 | V1 |
| TI-06 | Controlled/Class A V1 refusal | Baseline V1 refuses receiving, prescribing, dispensing, sale, and external-prescription completion for a product classified as controlled/Class A. An authorised classification owner may set or clear the classification, but that classification action cannot enable a controlled/Class A workflow in V1. | The product would appear to support a controlled-medicine workflow that is outside baseline V1 authority. | Catalogue classification and medicine workflow entry boundary. | RG-06 | V1 |
| TI-07 | Stock-ledger conservation and correction integrity | KlinKlik-managed stock changes only through attributable stock movements. The movement history remains authoritative; direct balance rewriting, silent correction, and a resulting negative usable balance are not permitted. Corrections preserve history through the defined approval, counter-movement, quarantine, disposal, or other authorised correction path. | Stock truth, expiry controls, and downstream dispensing or financial records become unreliable. | Stock movement, count, adjustment, dispensing, and disposal boundary. | RG-07 | V1 |
| TI-08 | Financial final-record and allocation integrity | Finalised financial records and recorded payments remain preserved. Corrections use the defined credit, void, reversal, refund, or authorised follow-on record; allocations are authoritative and a payment cannot silently over-allocate or create an unapproved excess outcome. | Misstated patient balance, cash exposure, or an unreconstructable financial history. | Invoice finalisation, payment confirmation, allocation, and correction boundary. | RG-08 | V1 |
| TI-09 | Single committed high-impact outcome | A high-impact action has one committed product outcome; competing attempts cannot leave a partial bundle or multiple winners. A losing attempt receives a safe current-state result. | Duplicate or partial clinical, queue, stock, dispensing, payment, or final-record activity. | High-impact command and state-transition boundary. | RG-09 | V1 |
| TI-10 | Duplicate and retry safety | Retrying a high-impact create or command does not create duplicate clinical, money, stock, dispensing, or finalisation effects. A reused request identity with materially different intent is refused rather than treated as the original request. | Duplicate charge, stock movement, clinical record, or other irreversible effect. | High-impact command acceptance boundary. | RG-10 | V1 |
| TI-11 | Stale-state conflict safety | A stale actor cannot silently overwrite newer authoritative mutable state. The product rejects the attempt or requires explicit reconciliation against the current authorised state. | Lost or contradictory clinical, queue, inventory, or financial updates. | Mutable-record and state-transition boundary. | RG-11 | V1 |
| TI-12 | PHI and sensitive-payload minimisation | PHI is disclosed only within the authorised product record and role scope. Raw sensitive clinical payloads do not enter generic logs, telemetry, diagnostics, analytics, or audit payloads; required reconstruction uses approved non-sensitive references. | Privacy breach or secondary disclosure of sensitive data. | Sensitive-data disclosure and diagnostic-evidence boundary. | RG-12 | V1 |
| TI-13 | Audit integrity and reconstruction | An audited mutation or required access event produces attributable, immutable, non-sensitive reconstruction evidence as part of the product action. If required audit evidence cannot be recorded, the action does not complete. | A material action cannot be reconstructed or is falsely represented as completed. | Audited action and finalisation boundary. | RG-13 | V1 |
| TI-14 | No unapproved clinical interpretation | V1 records and presents workflow and human-entered clinical information but does not automatically diagnose, prescribe, calculate dosing, match allergies or interactions, classify risk, interpret results, or issue critical-result conclusions. A clinical interpretation rule is unavailable until expressly validated and authorised through the governing change process. | The product could be mistaken for an unauthorised clinical decision maker. | Clinical workflow and interpretation boundary. | RG-14 | V1 |
| TI-15 | No high-impact offline completion | A clinical sign-off, payment, stock receipt or adjustment, dispensing, sale, or other high-impact final action completes only after authoritative product confirmation. A locally saved or queued attempt is not a completed product outcome. | An offline or disconnected action could be treated as final without authoritative safeguards, stock truth, payment truth, or audit evidence. | High-impact finalisation boundary. | RG-15 | V1 |

The `RG-01` through `RG-15` identifiers are unique prospective Mandatory
Regression Gate IDs for later population in Section 18. They are not evidence
that a gate has already run. Every currently effective high-risk invariant in
this section maps to one of those future gates; no invariant is weakened by a
story-level exception.

Source authority:

K:/new/clinicopus2.md §§5, 7, 9, 12, 14–15, 18–26, 31–36, 42, 54–55, 59;
K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §§4, 7, 22, 24–25, 30–31 and
the supplied REC, TRI, ENC, LAB, RX, INV, DSP, BIL, PAY, and AUD story
contracts; K:/clinicopus/AGENTS.md.

---

## 12. Global Story Contract

Global Story Contracts are reusable cross-cutting obligations inherited by
stories unless a story explicitly differs. The project must mark every
contract REQUIRED, APPLICABLE IF..., or NOT APPLICABLE and record its
rationale. Do not force every project to use every contract.

| ID | Contract | Project status | Applicability / rationale | Story override rule |
| --- | --- | --- | --- | --- |
| GSC-1 | Explicit scope / context | REQUIRED | Every protected operation needs its acting identity, organisation, facility, relevant department or patient scope, target, and state/configuration context. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |
| GSC-2 | Cross-scope fail-closed behaviour | REQUIRED | Supplied-story cross-facility access fails closed without exposing existence. A same-organisation BRN exception is conditional on an explicitly authorised dedicated capability; the BRN policy/dependencies are unsupplied and no active exception may be assumed. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |
| GSC-3 | Server authority | REQUIRED | The authoritative product decides protected validation, state, pricing, permissions, and side effects, and rechecks them at the protected action. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |
| GSC-4 | Default-deny authorisation | REQUIRED | Missing, ambiguous, or stale authority denies access; client presentation is not authority and protected data is not partially disclosed. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |
| GSC-5 | Stale-write detection / concurrency conflict safety | REQUIRED | A stale update cannot silently replace newer authoritative state. It is refused with a safe current-state outcome or follows an explicitly defined reconciliation path. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |
| GSC-6 | Single-winner high-impact state transitions | REQUIRED | Competing high-impact actions have one committed product outcome and no partial bundle; losing attempts receive a safe actionable result. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |
| GSC-7 | Idempotency / duplicate safety | REQUIRED | Retried high-impact commands cannot duplicate a clinical record, money, stock, dispense, queue, or finalisation effect; materially different reuse is refused. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |
| GSC-8 | Audit expectations | REQUIRED | Required mutations and audited access produce attributable reconstruction evidence, with no raw sensitive clinical payload in generic audit data. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |
| GSC-9 | Sensitive payload minimisation | REQUIRED | PHI and sensitive clinical data remain inside authorised product scope and are excluded from generic logs, telemetry, diagnostics, analytics, and error payloads. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |
| GSC-10 | External effects, inbound events, and retry safety | APPLICABLE IF... | Transactional email is the only external-API class explicitly reserved/allowed by frozen V1 authority (OPS-002), and internal notification/export dispatch infrastructure remains available for genuine V1 needs. Its detailed Product Spec effect is UNSUPPLIED / OPEN / BLOCKED: no email may be implemented from that architectural allowance or internal dispatch infrastructure alone. Once product authority defines an actual email effect, this full outbound contract is mandatory before activation. Direct Mobile Money, bank, card, public webhook, SMS, WhatsApp, and other provider integrations remain unapproved unless separately authorised; a manually entered reference is not such an integration. | Silence = FULL INHERITANCE when applicable; a contract cannot be created or changed by a story alone. |
| GSC-11 | Authoritative timezone / time source | REQUIRED | V1 user/facility operational timezone is EAT / Africa-Kampala; facility-day calculations use that authoritative local-day boundary. An authoritative product/server clock determines expiry, ordering, elapsed time, queue timing, schedules, and audit chronology. Client/device time cannot determine a protected product outcome. Clinical event time entered or recorded as domain information is distinct from authoritative audit/system chronology. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |
| GSC-12 | Standard UI states | REQUIRED | Important workflow surfaces provide applicable loading, empty, success, error, unavailable, denied, stale/conflict, degraded, read-only, and terminal/immutable outcomes rather than a blank or misleading state. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |
| GSC-13 | Standard test obligations | REQUIRED | Each supplied story carries applicable domain, API, negative, permission/scope, audit, state-transition, concurrency, accessibility, and regression evidence obligations. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |
| GSC-14 | State / session / context isolation for asynchronous operations | REQUIRED | A late response, job, session, tab, or changed active context cannot overwrite, expose, or act upon another user, patient, facility, or resource context. | Silence = FULL INHERITANCE; only the Section 12 change-controlled override rule may apply. |

### Contract definitions

- **GSC-1 Explicit scope / context:** Every operation names the acting
  identity, tenant or scope, target resource, and relevant release or
  configuration context.
- **GSC-2 Cross-scope fail-closed:** A request cannot read or mutate another
  scope unless an explicitly approved capability and policy allow it.
- **GSC-3 Server authority:** Protected state, validation, transitions,
  pricing, permissions, and side effects are decided and rechecked server-side.
- **GSC-4 Default-deny authorisation:** Missing or uncertain capability is
  denied; the UI cannot grant access the server rejects.
- **GSC-5 Stale-write detection / concurrency conflict safety:** Concurrent or stale updates
  are detected before they can silently overwrite newer authoritative state;
  stale updates are rejected or explicitly reconciled according to the
  product contract.
- **GSC-6 Single-winner transitions:** High-impact actions have one committed
  winner under retries and concurrency; losers receive a safe, actionable
  result.
- **GSC-7 Idempotency / duplicate safety:** Retried creates and commands do
  not duplicate money, records, messages, or external effects.
- **GSC-8 Audit expectations:** Audited actions record actor, scope, action,
  target, time, reason where needed, and non-sensitive references required for
  reconstruction.
- **GSC-9 Sensitive payload minimisation:** Sensitive data is not placed in
  logs, telemetry, analytics, errors, or audit fields unless an approved
  product rule explicitly requires it and the authority record allows it.
- **GSC-10 External effects and inbound events:** Every material external
  effect or inbound event uses its applicable structured contract below.
  Product Spec authority defines the required observable consistency, duplicate
  safety, authority, ordering, pending/unknown/failure outcomes, and recovery
  semantics; the Blueprint chooses the technical implementation without
  changing that meaning.
- **GSC-11 Authoritative time:** State which clock, timezone, and timestamp
  authority determines ordering, expiry, schedules, and audit chronology.
- **GSC-12 Standard UI states:** Important surfaces define loading, empty,
  success, error, unavailable, denied, stale/conflict, offline/degraded,
  read-only, and terminal/immutable states where applicable.
- **GSC-13 Test obligations:** Stories map to unit/domain, API, negative,
  security, accessibility, concurrency, and regression tests according to
  applicability.
- **GSC-14 Async isolation:** Late responses, jobs, sessions, tabs, and
  contexts cannot overwrite or disclose state belonging to another active
  resource or user context.

### Inbound external event contract (GSC-10)

Where inbound external events exist, define each contract with all of the
following fields. An external provider is not automatically authoritative for
local product state merely because it reports an event. Authority must be
declared explicitly per state, field, or fact. An external provider may be
authoritative for facts it exclusively owns, such as provider payment capture
status, provider delivery status, provider identity assertion, or a provider-generated
transaction identifier, when the Product Spec explicitly says so. The local
product remains authoritative for its own product state, permissions,
workflow transitions, derived outcomes, and business meaning unless the
Product Spec explicitly assigns authority otherwise. Receiving an external
event must never automatically bypass local state guards or
server-authoritative workflow rules. Where provider-owned truth and local
product truth differ, use the declared reconciliation/disagreement contract.

| Event / contract ID | Source authentication / trust | Duplicate / replay handling | Idempotency | Out-of-order handling | Correlation | Authoritative system per state piece | Disagreement handling | Audit | Rejected / quarantined handling | Reconciliation if external success but acknowledgement is lost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NONE CURRENTLY | No authorised inbound provider-event contract is supplied for V1. | Not applicable unless approved authority introduces a contract. | Not applicable unless approved authority introduces a contract. | Not applicable unless approved authority introduces a contract. | Not applicable unless approved authority introduces a contract. | KlinKlik remains authoritative for its product state. | No current external disagreement path is authorised. | No current inbound event evidence is authorised. | No current inbound event is authorised; an introduced event must use the full contract. | An introduced event must define this before activation. |

No inbound events or webhooks may be marked NOT APPLICABLE without a rationale. Reject or
quarantine untrusted, duplicate, malformed, or otherwise unsafe events
without changing local truth; retain safe diagnostic and audit evidence.

### Outbound external effect contract (GSC-10)

For every material outbound external effect where applicable, record the
required product outcome in this contract. Examples include payment
capture/refund, email/SMS/message send, provider provisioning,
booking/reservation, external order, and external document submission; these
are examples only and are not mandatory domains.

| Effect / contract ID | Trigger / local intent | Product state that must exist before effect | Required ordering / commit relationship | Idempotency / duplicate-suppression requirement | Authoritative system per relevant fact/state | Timeout / unknown-result semantics | Retry semantics | Product-visible pending / failure / unknown state | External success but local acknowledgement/commit failure handling | Compensation / reconciliation requirement | Audit / evidence requirement | Relevant Trust Invariant / Regression Gate IDs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TRANSACTIONAL EMAIL — PRODUCT CONTRACT OPEN / BLOCKED | Frozen V1 architecture permits/reserves transactional email; exact product trigger, recipient, and content semantics are UNSUPPLIED / OPEN / BLOCKED. | Required local product state is UNSUPPLIED / OPEN and must be defined before activation. | OPEN until the product effect is specified; no ordering is chosen here. | OPEN until the product effect is specified; no duplicate-suppression rule is chosen here. | Provider OPEN; no provider or implementation mechanism is chosen; Product Spec authority must define local state. | OPEN until the product effect is specified. | OPEN until the product effect is specified. | OPEN until the product effect is specified. | OPEN until the product effect is specified. | OPEN until the product effect is specified. | OPEN, including privacy-payload and audit requirements, until the product effect is specified. | OPEN until the product effect identifies applicable TI/RG IDs. |

The Product Spec defines the required observable consistency, duplicate
safety, authority, and recovery semantics. An implementation may not choose
effect-before-commit, commit-before-effect, or another ordering merely for
convenience. The Blueprint may choose an outbox, queue, provider idempotency
key, transaction boundary, reconciliation worker, or compensation mechanism
without changing Product Spec meaning.

If an effect cannot follow the normal preferred ordering, the contract must
state the required alternate behaviour, why it is required, its authority or
owner, residual risk where applicable, and recovery/reconciliation semantics.
It must explicitly handle EXTERNAL EFFECT SUCCEEDED plus LOCAL
ACKNOWLEDGEMENT / COMMIT FAILED without assuming automatic replay is safe.

Silence in a story means FULL INHERITANCE of every applicable GSC. A story
may override or narrow an applicable GSC only when all of the following are
true: the exact GSC ID is named; the exact narrowed behaviour is stated; an
approved change record exists; the named approving authority is recorded;
residual risk is recorded; affected Trust Invariant IDs are identified; and
affected Mandatory Regression Gate IDs and validation impact are identified.

A story authored by an implementation agent cannot itself grant an override.
If the GSC is backed by a Trust Invariant, the invariant owner or named
equivalent authority must approve the override. A story-level statement
without this authority is INVALID and the GSC wins. Do not require repeated
GSC text inside every story.

Source authority:

K:/new/clinicopus2.md §§7, 9, 31–33, 35, 37, 40, 42, 53–55, 59;
K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §§4, 7, 22, 24–25, 30–31,
including the supplied REC, QUE, TRI, ENC, LAB, RX, INV, DSP, BIL, PAY, RCP,
and ANC story contracts; K:/clinicopus/AGENTS.md.

---

## 13. Canonical Error Families

Use a small, stable vocabulary. Add domain-specific errors only when a
standard family cannot explain the user action or test expectation.

| Error family | Meaning | Typical response / recovery |
| --- | --- | --- |
| NOT_FOUND | Target does not exist in the permitted scope. | Safe not-found response; do not disclose hidden existence. |
| PERMISSION_DENIED | Identity lacks the required capability. | No partial protected data; show the permitted next step. |
| UNSUPPORTED_OPERATION | Requested behaviour is deliberately not supported in the current product release regardless of actor capability. | Use the approved external/non-KlinKlik process or a later Product Spec version; no role or permission escalation can enable it. |
| VALIDATION_FAILED | Submitted values violate an authoritative product validation rule and the operation cannot be accepted until the input is corrected. | Correct the supplied values and retry. |
| SCOPE_NOT_FOUND | Target exists elsewhere or scope is invalid. | Fail closed; do not reveal cross-scope existence. |
| VERSION_CONFLICT | Mutable record is stale. | Refresh authoritative state and require explicit reconciliation. |
| INVALID_STATE | Requested transition is not allowed. | Explain current state and valid next action. |
| ALREADY_EXISTS | Uniqueness or open-resource rule was met by another request. | Return existing safe reference where the contract permits. |
| ALREADY_COMPLETED | A terminal or already-won operation cannot be repeated. | Show the committed outcome; do not replay side effects. |
| RATE_LIMITED | Request volume exceeds a configured limit. | Retry according to server guidance. |
| PREREQUISITE_MISSING | Required setup, approval, or dependent record is absent. | Name the missing prerequisite without inventing it. |
| IDEMPOTENCY_CONFLICT | Same key was used for materially different input. | Reject and require a new key after review. |

The project-specific mappings below use only explicit identifiers supplied by
the canonical backlog. The two additional families above provide the required
semantic distinctions; no new error code is created and no row replaces a
story's more specific API contract. “User-safe message” states the required
safe outcome, not invented final UI copy; exact copy and a message owner remain
OPEN unless the source supplies them.

| Project-specific code | Family | Trigger | User-safe message | Recovery | Owner |
| --- | --- | --- | --- | --- | --- |
| `VISIT_ALREADY_OPEN` | ALREADY_EXISTS | A same-day open visit already exists for the patient at the facility. | Safe outcome: do not create a second visit; identify the existing visit only where the caller may see it. | Use the existing visit or an expressly authorised second-visit path. | OPEN |
| `PATIENT_INACTIVE` | INVALID_STATE | Check-in is attempted for an inactive patient. | Safe outcome: do not confirm check-in for the inactive patient. | Use the authorised patient-status path before retrying. | OPEN |
| `SERVICE_NOT_PRICED` | PREREQUISITE_MISSING | A required consultation or service price is absent. | Safe outcome: do not create an unintended free chargeable service. | Complete authorised price setup, then retry. | OPEN |
| `PAYER_LOCKED` | INVALID_STATE | A payer change is requested after payment has made the payer immutable. | Safe outcome: retain the existing payer and financial history. | Use the defined authorised financial correction path where applicable. | OPEN |
| `NO_PRICE_LIST` | PREREQUISITE_MISSING | No active price list is available for the requested check-in. | Safe outcome: do not complete check-in without authorised pricing. | Activate or select an authorised price list, then retry. | OPEN |
| `REPRINT_WINDOW_EXPIRED` | INVALID_STATE | A reprint is requested outside the defined reprint window. | Safe outcome: do not issue an unauthorised reprint. | Use an authorised record-access or exception path if one is later defined. | OPEN |
| `ENCOUNTER_UNRESOLVED` | INVALID_STATE | A visit closure or LWBS action is attempted while an unresolved encounter remains. | Safe outcome: retain the encounter and refuse the incompatible closure. | Resolve the encounter through its defined path, then retry closure. | OPEN |
| `GRACE_WINDOW_EXPIRED` | INVALID_STATE | A pre-service check-in correction is attempted after its permitted grace window. | Safe outcome: preserve the visit history and refuse the late shortcut. | Use the applicable existing closure or correction workflow. | OPEN |
| `CLINICAL_DATA_EXISTS` | INVALID_STATE | A pre-service check-in correction is attempted after clinical data exists. | Safe outcome: preserve the clinical history and refuse the shortcut. | Use the applicable existing closure or correction workflow. | OPEN |
| `VISIT_CLOSED` | INVALID_STATE | An ordinary action is attempted after a visit is closed. | Safe outcome: do not attach an ordinary new record to the closed visit. | Use only an explicitly defined post-closure workflow where applicable. | OPEN |
| `ENTRY_LOCKED` | VERSION_CONFLICT | Another authorised user has already won the queue-entry action. | Safe outcome: do not create a second winner or overwrite the current holder. | Refresh the authoritative queue state; use an allowed takeover path only when eligible. | OPEN |
| `ALREADY_CALLED` | ALREADY_COMPLETED | A queue entry has already been called by a competing action. | Safe outcome: show the committed call outcome without replaying it. | Continue from the current queue state. | OPEN |
| `TAKEOVER_TOO_EARLY` | INVALID_STATE | A queue takeover is requested before the defined inactivity threshold. | Safe outcome: retain the current holder and refuse an early takeover. | Retry only when the defined takeover condition is met. | OPEN |
| `DIASTOLIC_EXCEEDS_SYSTOLIC` | VALIDATION_FAILED | Recorded diastolic pressure exceeds recorded systolic pressure. | Safe outcome: do not save the internally inconsistent vital set. | Correct or re-measure the values, then retry. | OPEN |
| `COMPLAINT_REQUIRED` | PREREQUISITE_MISSING | An OPD triage record is saved without a required presenting complaint. | Safe outcome: do not complete the required triage record. | Record the complaint, then retry. | OPEN |
| `OTHER_REQUIRES_TEXT` | PREREQUISITE_MISSING | “Other” is selected without its required free text. | Safe outcome: do not save an unexplained “Other” selection. | Provide the required text, then retry. | OPEN |
| `ALLERGY_STATUS_REQUIRED` | PREREQUISITE_MISSING | Triage completion is attempted without an explicitly captured allergy status: one or more active recorded allergies, NKA / NO_KNOWN_ALLERGIES, or UNKNOWN. | Safe outcome: do not complete triage while allergy status is NOT RECORDED or treat UNKNOWN as NKA. | Record one or more allergies, explicitly confirm NKA / NO_KNOWN_ALLERGIES, or explicitly record UNKNOWN, then retry. | OPEN |
| `ACUITY_REQUIRED` | PREREQUISITE_MISSING | Triage completion is attempted without an explicitly selected acuity. | Safe outcome: do not complete triage with an assumed or automatic acuity. | An authorised human selects acuity, then retry. | OPEN |
| `AMENDMENT_WINDOW_EXPIRED` | INVALID_STATE | A triage amendment is requested outside its ordinary amendment window. | Safe outcome: retain the original and refuse the ordinary amendment route. | Request the defined supervisor amendment path. | OPEN |
| `RECORD_SIGNED` | INVALID_STATE | A change is attempted to a signed encounter through an ordinary editing path. | Safe outcome: preserve the signed record. | Use the defined addendum, amendment, or error-correction path where applicable. | OPEN |
| `DIAGNOSIS_REQUIRED` | PREREQUISITE_MISSING | Encounter signing is attempted without a final diagnosis or explicit no-diagnosis reason. | Safe outcome: do not finalise an incomplete encounter. | Record the required diagnosis information or explicit permitted reason, then retry. | OPEN |
| `PAYMENT_REQUIRED` | PREREQUISITE_MISSING | A payment-gated service action is attempted before required payment is confirmed. | Safe outcome: do not release the gated service. | Complete the required payment or authorised gate-resolution path, then retry. | OPEN |
| `SELF_VERIFICATION_NOT_ALLOWED` | PERMISSION_DENIED | A laboratory result verifier attempts to verify their own entry without the defined exception. | Safe outcome: do not release the result through an unauthorised self-verification path. | Use an eligible verifier or the explicitly defined exception when applicable. | OPEN |
| `CONTROLLED_NOT_SUPPORTED` | UNSUPPORTED_OPERATION | A controlled/Class A medicine workflow is attempted in baseline V1. | Safe outcome: refuse the V1 workflow without exposing an override. | Use the approved external/non-KlinKlik process or a later Product Spec version; no role or permission escalation can enable it. | OPEN |
| `OUTSIDE_PRESCRIBING_SCOPE` | PERMISSION_DENIED | A prescribing action exceeds the actor's defined scope. | Safe outcome: do not create an unauthorised prescription. | Use an appropriately authorised prescriber or defined referral path. | OPEN |
| `WEIGHT_REQUIRED_UNDER_5` | PREREQUISITE_MISSING | Triage is saved for a patient under five without weight or an explicit not-done reason. | Safe outcome: do not save the incomplete paediatric triage record. | Record weight or the explicit permitted not-done reason, then retry. | OPEN |
| `EXPIRED_STOCK_CANNOT_BE_RECEIVED` | INVALID_STATE | Receipt is attempted for stock that is already expired. | Safe outcome: do not receive expired stock into usable KlinKlik stock. | Use only the defined non-usable stock disposition path. | OPEN |
| `EXPIRED_BATCH` | INVALID_STATE | A direct request names an expired batch for a protected stock action. | Safe outcome: refuse the expired batch regardless of caller role. | Select an eligible batch; no override path exists. | OPEN |
| `INSUFFICIENT_STOCK` | PREREQUISITE_MISSING | The requested stock action exceeds available usable stock. | Safe outcome: do not create a negative usable balance. | Adjust the requested quantity or use an authorised replenishment/correction path. | OPEN |
| `OUT_OF_STOCK` | PREREQUISITE_MISSING | A prescription item has no usable stock available. | Safe outcome: do not promise or dispense unavailable stock. | Use the defined partial-dispense, substitute, or not-dispensed path. | OPEN |
| `EXCEEDS_PRESCRIBED_QUANTITY` | VALIDATION_FAILED | A proposed dispense quantity exceeds the prescribed quantity. | Safe outcome: do not over-dispense. | Correct the quantity or use a new authorised prescription. | OPEN |
| `BALANCE_CHANGED` | VERSION_CONFLICT | A concurrent payment or allocation changed the authoritative outstanding balance. | Safe outcome: do not commit an over-allocation or unintended excess payment. | Refresh the current balance and require re-entry or confirmation. | OPEN |
| `REFERENCE_REQUIRED` | PREREQUISITE_MISSING | A payment method that requires a reference is recorded without one. | Safe outcome: do not confirm an insufficiently referenced payment. | Provide the required reference, then retry. | OPEN |
| `NO_OPEN_SHIFT` | PREREQUISITE_MISSING | A payment is recorded while shifts are enabled and no open shift exists. | Safe outcome: do not record an unattributed payment. | Open an authorised shift, then retry. | OPEN |

### Safe scope disclosure

Preserve the SCOPE_NOT_FOUND family for internal classification, but do not
reveal that a hidden resource exists in another tenant or scope through an
external API or UI unless the Product Spec explicitly authorises that
disclosure. Where distinguishing SCOPE_NOT_FOUND from NOT_FOUND creates an
inference risk, SCOPE_NOT_FOUND and ordinary NOT_FOUND must use the same
externally safe status/body semantics: return the same externally visible
status and body. Internal audit and diagnostics may retain the more precise
family under the approved sensitive-payload rules.

Source authority:

K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §7 and supplied story contracts
REC-001, REC-003, REC-005, REC-006, REC-009–012, QUE-003, QUE-013,
TRI-002–008, TRI-011, ENC-017 and ENC-023, LAB-015, RX-005–008, INV-003–005,
DSP-002–004, PAY-002, PAY-005, and PAY-009; K:/new/clinicopus2.md §§7, 15,
18–26, 31–33, 40, 42, 54; K:/clinicopus/AGENTS.md.

---

## 14. Major User Journeys

Journeys are canonical end-to-end behaviour, not implementation diagrams.
Include the normal path and every material alternate or error path.

### J-01 — Simple Outpatient (JOURNEY A)

Source alias: JOURNEY A

RECEPTIONIST → check-in → Visit OPEN + Invoice ISSUED with one consultation
line → normal/no PAY_BEFORE_TRIAGE: triage QueueEntry WAITING → NURSE, or
PAY_BEFORE_TRIAGE: triage QueueEntry WAITING_PAYMENT → CASHIER → WAITING →
NURSE → consultation gate check → CLINICIAN → Encounter signing → remaining
billing/payment → Receipt → visit closure → terminal Visit CLOSED outcome.

The first real service starts the Visit's `OPEN → IN_PROGRESS` transition;
the clinician then starts the Encounter on the active Visit without reopening it.

| Step | Actor / SYSTEM | Action | Canonical state | Next actor / system | Failure or alternate path |
| --- | --- | --- | --- | --- | --- |
| 1 | RECEPTIONIST | Check in an active patient at the authorised facility, select visit type and destination, create the attendance path, and create the chargeable consultation line when applicable. | Visit OPEN; Invoice ISSUED with exactly one chargeable OPD consultation line at check-in. Normal/no PAY_BEFORE_TRIAGE: triage QueueEntry WAITING. PAY_BEFORE_TRIAGE: triage QueueEntry WAITING_PAYMENT and absent from the triage worklist. | NURSE (normal) or CASHIER (PAY_BEFORE_TRIAGE) | VISIT_ALREADY_OPEN, PATIENT_INACTIVE, SERVICE_NOT_PRICED, or an unavailable destination refuses the unsafe check-in; payment timing does not create the Visit or charge, and no duplicate Visit, QueueEntry, or consultation line is created. |
| 2 | CASHIER / SYSTEM | Where PAY_BEFORE_TRIAGE applies, collect qualifying payment, accept an authorised waiver, or apply an authorised gate override with audit, then release the existing initial gate. | The same triage QueueEntry WAITING_PAYMENT → WAITING; the existing Invoice remains ISSUED unless payment changes it to PARTIALLY_PAID or PAID. | NURSE | Until the initial gate clears, the patient remains out of triage. This releases an existing Visit/charge and creates neither. If payment reverses before triage or consultation service begins, the applicable WAITING or CALLED QueueEntry may re-gate to WAITING_PAYMENT; once IN_SERVICE or COMPLETED, it does not move backward merely because payment was reversed and financial truth is restored. |
| 3 | NURSE | After any applicable initial gate has cleared, record vitals or permitted not-done reasons, presenting complaint, and explicitly capture allergy status as one or more active allergies, NKA / NO_KNOWN_ALLERGIES, or UNKNOWN, plus explicitly selected acuity; complete triage. | Triage DRAFT → COMPLETED; triage QueueEntry → COMPLETED; consultation QueueEntry WAITING. | SYSTEM / CLINICIAN | Missing COMPLAINT_REQUIRED, ALLERGY_STATUS_REQUIRED, ACUITY_REQUIRED, WEIGHT_REQUIRED_UNDER_5, or other required input keeps triage incomplete. Triage records observation, not diagnosis or automatic interpretation. |
| 4 | SYSTEM / CASHIER / CLINICIAN | After triage and before the clinician workspace opens, evaluate the applicable consultation PAY_BEFORE policy. If it remains gated/unpaid, show the outstanding amount and either send the patient to the cashier or permit the clinician to proceed only through an authorised billing.gate.override with audit. PAY_AFTER or no gate does not force pre-consultation payment. | If the applicable consultation gate remains unpaid: consultation QueueEntry WAITING_PAYMENT; otherwise the applicable QueueEntry remains WAITING. The Invoice retains only canonical states. | CASHIER or CLINICIAN | Payment, an authorised waiver, or the audited billing.gate.override releases this later clinician-side gate. Missing pricing or an unresolved gate blocks release; this is separate from PAY_BEFORE_TRIAGE and no outpatient is sent to the cashier solely by default. |
| 5 | CLINICIAN | Start the consultation QueueEntry, use the approved Encounter workflow, record diagnosis/treatment, and sign the encounter when complete. | Visit OPEN or IN_PROGRESS → IN_PROGRESS when consultation service starts; Consultation QueueEntry WAITING → CALLED → IN_SERVICE → COMPLETED; Encounter OPEN → SIGNED; the signed clinical record remains immutable and is corrected only through its defined attributed path. | SYSTEM / CASHIER | Incomplete signing requirements, VISIT_CLOSED, stale state, or an invalid transition refuses signing. Signing does not create a second consultation line. |
| 6 | SYSTEM / CASHIER | After signing, resolve any remaining authoritative balance, debt, waiver, or receipt/payment requirement without applying the initial pre-consultation gate for the first time. | Payment is recorded immutably; Invoice remains ISSUED while unpaid, may become PARTIALLY_PAID or PAID, and is VOIDED only through a defined void path. | CASHIER / SYSTEM / Receipt | BALANCE_CHANGED, missing required payment context, or an unsafe allocation refuses the action; a retry cannot create a second payment. |
| 7 | SYSTEM / CASHIER | Produce the authoritative receipt for the committed financial outcome. | Receipt issued and linked to the payment and invoice. | RECEPTIONIST / CASHIER | A failed or unavailable print surface does not change financial truth; use the defined displayable/document fallback. |
| 8 | RECEPTIONIST / CASHIER | Apply the REC-012 close checklist and close the visit only when every required blocker is resolved. | Visit CLOSED, with signed clinical history, financial/receipt history, and audit evidence preserved. | Terminal outcome | Unresolved encounter, outstanding balance without an authorised path, active prescription/work, or unsafe concurrent close refuses closure. LWBS uses its defined terminal path and does not silently reopen the visit. |

| Field | Value |
| --- | --- |
| Entry condition | An active patient and an authorised organisation/facility context exist; required reception configuration and any applicable pricing are available. |
| Success outcome | One Visit is opened, triage is completed, one consultation charge is retained, the Encounter is signed without a second consultation line, payment/receipt is authoritative, and REC-012 closes the Visit safely. |
| Material failure outcomes | Duplicate or inactive check-in refused; PAY_BEFORE_TRIAGE keeps triage out of its worklist until the initial gate clears; incomplete triage or signing retained for correction; clinician-side payment gate or balance remains visible; invalid closure refused; defined LWBS, debt, waiver, or terminal visit outcome is used where supported. |
| Stories / invariants covered | REC-001..004, REC-012; TRI-001..007, TRI-009, TRI-011; ENC-001, ENC-005..017; BIL-001..006; PAY-002/003/005/012; RCP-001; TI-01, TI-02, TI-03, TI-08, TI-09, TI-10, TI-11, TI-12, TI-13, TI-14, TI-15. |
| Release | V1 |

### J-02 — Outpatient with Laboratory (JOURNEY B)

Source alias: JOURNEY B

RECEPTIONIST → Triage → CLINICIAN laboratory order → same Encounter parks
and consultation QueueEntry ON_HOLD → cashier/laboratory loop → same
Encounter resumes → result review and treatment → sign or ENC-018 pending
sign → Billing and payment → closure.

In this OPD journey, triage starts the first real service and changes the Visit
from `OPEN` to `IN_PROGRESS`; `LAB_ONLY` follows its distinct
request-capture path.

| Step | Actor / SYSTEM | Action | Canonical state | Next actor / system | Failure or alternate path |
| --- | --- | --- | --- | --- | --- |
| 1 | RECEPTIONIST / NURSE | Open the visit and complete the supplied reception and triage path. | Visit OPEN at check-in; triage starts the first real service and transitions the Visit to IN_PROGRESS; triage completed; consultation QueueEntry WAITING. | CLINICIAN | The J-01 duplicate, scope, pricing, triage, and observation safeguards apply. |
| 2 | CLINICIAN | Use one Encounter to order laboratory work, then park that same Encounter while the consultation return obligation remains explicit. | LabOrderItem ORDERED; Encounter AWAITING_RESULTS; consultation QueueEntry ON_HOLD. | SYSTEM / CASHIER | No second Encounter is created. An incomplete order or invalid park leaves the current Encounter and handoff visible for correction. |
| 3 | SYSTEM / CASHIER | Apply the laboratory payment policy. Under LABORATORY=PAY_BEFORE, hold unpaid work as non-actionable laboratory work and route the patient to payment; after qualifying payment release the work. Under PAY_AFTER or no gate, permit the laboratory path directly. | PAY_BEFORE: LabOrderItem AWAITING_PAYMENT, no patient-facing LAB QueueEntry, cashier QueueEntry WAITING; after payment LabOrderItem READY_FOR_COLLECTION and LAB QueueEntry WAITING. PAY_AFTER/no gate: LAB QueueEntry may be WAITING. | LAB_TECH | No patient-facing LAB QueueEntry exists before the required PAY_BEFORE release. Payment or setup failure leaves the consultation hold and unpaid work explicit. |
| 4 | LAB_TECH | Call the patient, collect or receive the specimen, and finish the patient-facing collection/receipt interaction. | LAB QueueEntry WAITING → CALLED → IN_SERVICE → COMPLETED; LabOrderItem READY_FOR_COLLECTION → SAMPLE_COLLECTED when collection succeeds. | Laboratory bench processing / SYSTEM | The LAB QueueEntry completes at the patient-facing interaction, not at result release. SAMPLE_REJECTED is not terminal; recollection/cancellation follows the supplied laboratory rules. |
| 5 | LAB_TECH / LAB_VERIFIER | Continue bench processing, enter and verify results, and release each result when authorised. | LabOrderItem SAMPLE_COLLECTED → RESULT_ENTERED → VERIFIED → RELEASED. | SYSTEM / CLINICIAN | Partial released results are readable with progress; partial release does not make the Encounter RESULTS_READY. Every blocking dependency must be RELEASED or CANCELLED. Result release never completes or reopens the patient-facing LAB QueueEntry. |
| 6 | SYSTEM | When ALL blocking laboratory dependencies referenced by the hold are terminal under the canonical rule, make the two distinct readiness states explicit. | Encounter AWAITING_RESULTS → RESULTS_READY; consultation QueueEntry ON_HOLD → READY_TO_RESUME. These are separate domain states. | CLINICIAN | Partial release triggers neither readiness transition. SAMPLE_REJECTED remains non-terminal. Manual early resume uses the separate early path in the next step and never creates a second Encounter. |
| 7 | CLINICIAN | Resume the same Encounter through the normal ready path, or use the supplied manual early-resume path before all blockers resolve, then review available results, record diagnosis/treatment, and sign when complete. | Normal ready resume: Encounter RESULTS_READY → OPEN; consultation QueueEntry READY_TO_RESUME → IN_SERVICE. Manual early resume: Encounter AWAITING_RESULTS → OPEN; consultation QueueEntry ON_HOLD → IN_SERVICE; remaining laboratory work continues. The Encounter ID is the same in both paths. | Billing / payment / closure | A stale or closed Encounter, unresolved blocker, or incomplete signing requirement remains visible and refuses the unsafe action; no second Encounter is created. |
| 8 | CLINICIAN | If the clinician explicitly signs while results remain pending, use the ENC-018 branch without a fake resume through OPEN. | Encounter AWAITING_RESULTS → SIGNED with signed_with_pending_orders=true; held consultation QueueEntry ON_HOLD → COMPLETED(SIGNED_WITH_PENDING_RESULTS). It does not later become READY_TO_RESUME. | REC-012 closure / LAB-023 | The visit may close as CLOSED(PENDING_RESULTS) only under REC-012. Late results use LAB-023; Visit, Encounter, and completed QueueEntry are not silently reopened. |
| 9 | RECEPTIONIST / CASHIER | Complete the applicable billing, payment, receipt, and REC-012 close path after the clinical branch. | Invoice/payment/Receipt authoritative; Visit CLOSED or CLOSED(PENDING_RESULTS) where the explicit branch permits it. | Terminal outcome | Unsafe closure, unresolved balance, or another active blocker refuses closure; no result or payment retry duplicates a committed outcome. |

| Field | Value |
| --- | --- |
| Entry condition | A valid V1 visit and completed triage have handed one Encounter to the CLINICIAN; laboratory ordering and the applicable payment policy are in scope. |
| Success outcome | The patient-facing LAB QueueEntry completes before bench release; laboratory items follow their independent result path; the held consultation returns to the same Encounter, which is reviewed and signed or follows ENC-018, then billing and REC-012 complete. |
| Material failure outcomes | PAY_BEFORE work remains non-actionable until payment; SAMPLE_REJECTED remains recollectable/non-terminal; partial release remains short of RESULTS_READY; unresolved blockers or unsafe closure are refused; late results use LAB-023 without reopening signed/closed product state. |
| Stories / invariants covered | REC-001/012; TRI-001..007; QUE-006; ENC-001/002/016/017/018/023; LAB-002/004/015/019/023; PAY-002/012; BIL-001..006; TI-01, TI-02, TI-03, TI-04, TI-08, TI-09, TI-10, TI-11, TI-12, TI-13, TI-14, TI-15. |
| Release | V1 |

### J-03 — Prescription / Pharmacy (JOURNEY C)

Source alias: JOURNEY C

CLINICIAN signs Encounter → prescription activation → pharmacy work → confirmed
basket → applicable payment gate → authoritative medicine handover → stock
deduction → downstream closure.

| Step | Actor / SYSTEM | Action | Canonical state | Next actor / system | Failure or alternate path |
| --- | --- | --- | --- | --- | --- |
| 1 | CLINICIAN / SYSTEM | Sign the Encounter and activate the prescription from the signed clinical decision. | Encounter SIGNED; Prescription DRAFT → ACTIVE. Activation creates no medicine charge by itself. | PHARMACIST | Incomplete signing or invalid clinical state refuses activation; a draft prescription is not pharmacy-visible. |
| 2 | PHARMACIST | Open the signed prescription and build/confirm the proposed basket: select the product, quantity, eligible batch allocation, price/source identity, and expiry/availability validation. No stock movement occurs at this stage. | Prescription ACTIVE; the proposed basket is confirmed but no stable Dispense, payment gate, or stock effect exists yet. | PHARMACIST / SYSTEM | Expired stock is never selectable or confirmable. Controlled/Class A products remain refused in V1; no automated allergy matching or clinical decision support is introduced. An authorised pre-handover basket revision/correction remains governed by DSP-007. |
| 3 | SYSTEM | Create the stable provisional Dispense and corresponding invoice lines from that confirmed basket. | One stable provisional Dispense exists with its proposed lines and source identities; no stock movement has occurred. | CASHIER / PHARMACIST | If line creation fails, no payment-gated/provisional dispense becomes actionable and an explicit billing/setup error is returned (DSP-007). |
| 4 | SYSTEM / CASHIER | Apply the medicine payment policy to that same provisional Dispense. Under MEDICINE=PAY_BEFORE, route payment before handover. | PAY_BEFORE: Dispense = AWAITING_PAYMENT; pharmacy QueueEntry = ON_HOLD(AWAITING_PAYMENT); cashier QueueEntry = WAITING. Qualifying payment completes cashier work and makes the same pharmacy entry READY_TO_RESUME. PAY_AFTER/no gate follows the applicable direct path. | PHARMACIST | No stock moves before final handover; payment failure leaves the hold and required next action visible. |
| 5 | PHARMACIST / SYSTEM | After the gate clears, resume the SAME provisional Dispense and the same pharmacy QueueEntry. | The same provisional Dispense is ready to resume; the same pharmacy entry moves READY_TO_RESUME → IN_SERVICE for handover, never a duplicate dispense or entry. | PHARMACIST | A retry cannot create a second dispense, payment, queue entry, or stock outcome; any authorised basket revision remains governed by DSP-007. |
| 6 | PHARMACIST / SYSTEM | At final handover, recheck stock and expiry and confirm the medicine handover. | Same Dispense → DISPENSED; its confirmed lines, batches, and quantities commit; stock is deducted once through the authorised movement; Prescription becomes the applicable completed or partially dispensed state. | REC-012 closure | EXPIRED_BATCH, OUT_OF_STOCK, INSUFFICIENT_STOCK, or a stale basket refuses the unsafe handover with no partial stock effect. Handover cannot complete offline. |
| 7 | PHARMACIST / SYSTEM | If the patient declines, cannot afford, or abandons unpaid provisional work, apply the supplied abandonment path; if paid pre-handover value changes, use the supplied correction path. | Unpaid Dispense → CANCELLED; unpaid lines voided; pharmacy/cashier entries terminal; Prescription NOT_DISPENSED or retained PARTIALLY_DISPENSED. Paid value changes use credit notes and new source-versioned lines. | Clinician / cashier / closure as applicable | A cancelled Dispense is historical and is not revived. Paid records are not silently edited; no automatic stock reversal is assumed. |
| 8 | RECEPTIONIST / CASHIER | Close the visit after the prescription and financial/stock outcomes are terminal under REC-012. | Visit CLOSED with preserved prescription, stock, financial, receipt, and audit history. | Terminal outcome | Outstanding balance, active work, or another closure blocker refuses the unsafe close; no high-impact pharmacy action completes from an offline attempt. |

| Field | Value |
| --- | --- |
| Entry condition | A signed V1 Encounter has an active prescription and the patient is within the authorised pharmacy/organisation/facility scope. |
| Success outcome | Pharmacy works from the signed prescription and a confirmed basket; any medicine payment gate is honoured; only eligible non-expired stock is selected; one authoritative Dispense and stock outcome is committed at final handover; the visit can close safely. |
| Material failure outcomes | Draft prescription remains hidden; controlled/Class A workflow is refused; expired or unavailable stock is refused; partial or not-dispensed outcome is recorded where supplied; unpaid abandonment and paid pre-handover correction preserve history. |
| Stories / invariants covered | ENC-017; RX-001..005; DSP-001..009; DSP-005/007/008/009; INV-004/005/012; PAY-012; BIL-004/010; REC-012; TI-01, TI-02, TI-05, TI-06, TI-07, TI-08, TI-09, TI-10, TI-11, TI-12, TI-13, TI-14, TI-15. |
| Release | V1 |

### J-04 — Laboratory + Pharmacy (JOURNEY D)

Source alias: JOURNEY D

RECEPTIONIST → Triage → CLINICIAN orders laboratory work and parks the same
Encounter → laboratory loop → CLINICIAN resumes that Encounter and reviews
results → diagnosis/treatment → prescription → pharmacy and applicable
payment/dispense → visit closure.

| Step | Actor / SYSTEM | Action | Canonical state | Next actor / system | Failure or alternate path |
| --- | --- | --- | --- | --- | --- |
| 1 | RECEPTIONIST / NURSE | Open the visit, complete triage, and hand the patient to the clinician. The first ordinary QueueEntry-backed substantive triage service causes the canonical OPEN → IN_PROGRESS Visit transition. | Visit IN_PROGRESS; TriageRecord COMPLETED; consultation QueueEntry WAITING. | CLINICIAN | The J-01 scope, pricing, triage, allergy, acuity, and no-automatic-interpretation safeguards apply. |
| 2 | CLINICIAN | Order laboratory work in the active Encounter and park that same Encounter while retaining the consultation return obligation. | LabOrderItem ORDERED; Encounter AWAITING_RESULTS; consultation QueueEntry ON_HOLD. | SYSTEM / CASHIER | No second Encounter or second consultation charge is created. |
| 3 | SYSTEM / CASHIER | Apply LABORATORY=PAY_BEFORE or the applicable PAY_AFTER/no-gate path. | PAY_BEFORE: LabOrderItem AWAITING_PAYMENT, no patient-facing LAB QueueEntry, cashier QueueEntry WAITING; qualifying payment makes the item READY_FOR_COLLECTION and creates LAB QueueEntry WAITING. | LAB_TECH | Unpaid work remains non-actionable; a payment/setup failure leaves the held consultation and required next action visible. |
| 4 | LAB_TECH / SYSTEM | Complete the patient-facing laboratory collection/receipt interaction, then continue the independent laboratory result loop. | LAB QueueEntry WAITING → CALLED → IN_SERVICE → COMPLETED; LabOrderItem may continue SAMPLE_COLLECTED → RESULT_ENTERED → VERIFIED → RELEASED; at most one QueueEntry is IN_SERVICE at any instant. | CLINICIAN when the same Encounter can resume | Queue completion is not result release. Partial release does not produce RESULTS_READY; SAMPLE_REJECTED is non-terminal and follows the supplied recollection/cancellation path. |
| 5 | SYSTEM / CLINICIAN | When all blocking laboratory dependencies resolve, make the readiness states explicit and resume the same Encounter normally; the supplied manual early-resume path remains available before all blockers resolve. | All blockers terminal: Encounter AWAITING_RESULTS → RESULTS_READY and consultation QueueEntry ON_HOLD → READY_TO_RESUME. Normal resume: same Encounter RESULTS_READY → OPEN and QueueEntry READY_TO_RESUME → IN_SERVICE. Manual early resume: same Encounter AWAITING_RESULTS → OPEN and QueueEntry ON_HOLD → IN_SERVICE; the Encounter ID is unchanged in every path. | CLINICIAN | Partial release does not trigger either readiness transition. Remaining laboratory work continues on the early path; no duplicate Encounter is allowed. |
| 6 | CLINICIAN | Use reviewed results for the clinical decision, record diagnosis/treatment, and sign the Encounter. | Same Encounter SIGNED; consultation QueueEntry completes on the normal path. | SYSTEM / PHARMACIST | If the clinician explicitly signs with results pending, ENC-018 completes the held consultation QueueEntry with SIGNED_WITH_PENDING_RESULTS; it never later becomes READY_TO_RESUME, and late results follow LAB-023 without reopening signed/closed state. |
| 7 | PHARMACIST / CASHIER / SYSTEM | Activate and work the prescription through its own pharmacy gate, eligible stock selection, payment, and authoritative handover. | Prescription ACTIVE; applicable pharmacy hold/resume; same Dispense → DISPENSED; stock deducted once. | RECEPTIONIST / CASHIER | Expired or controlled stock, payment failure, unavailable stock, or duplicate retry follows J-03 safeguards. No duplicate payment, dispense, or stock outcome is created. |
| 8 | RECEPTIONIST / CASHIER | Apply the applicable receipt and REC-012 close path after the laboratory and pharmacy work is resolved. | Invoice/payment/Receipt and clinical history preserved; Visit CLOSED or the explicit CLOSED(PENDING_RESULTS) branch. | Terminal outcome | Outstanding balance, unresolved work, or another unsafe blocker refuses closure; no queue handoff silently loses the patient. |

| Field | Value |
| --- | --- |
| Entry condition | A valid V1 visit and completed triage hand to one CLINICIAN Encounter; laboratory and pharmacy work are both required by the clinical path. |
| Success outcome | Laboratory collection completes its patient-facing QueueEntry before bench release; the same Encounter resumes for result review and treatment; prescription, pharmacy gates, dispense, payment, stock, and REC-012 closure each complete without duplicate outcomes. |
| Material failure outcomes | Laboratory payment gate, incomplete/partial result, SAMPLE_REJECTED, unsafe early or late clinical action, controlled/expired/unavailable stock, pharmacy payment hold, duplicate retry, or invalid closure remains explicit and follows the applicable J-02 or J-03 path. |
| Stories / invariants covered | REC-001/012; TRI-001..007; QUE-006; ENC-001/002/016/017/018/023; LAB-002/004/015/019/023; RX-001..005; DSP-001..009; INV-004/005/012; PAY-002/012; BIL-001..006; TI-01, TI-02, TI-03, TI-04, TI-05, TI-06, TI-07, TI-08, TI-09, TI-10, TI-11, TI-12, TI-13, TI-14, TI-15. |
| Release | V1 |

### J-05 — Antenatal Care (JOURNEY E)

Source alias: JOURNEY E

ANC check-in → ANC provider → ANC documentation → standard laboratory loop
when required → standard prescription path when medication or supplements are
prescribed → follow-up dependency → applicable billing/payment → visit closure.

| Step | Actor / SYSTEM | Action | Canonical state | Next actor / system | Failure or alternate path |
| --- | --- | --- | --- | --- | --- |
| 1 | RECEPTIONIST | Check in the patient with visit type ANC under the authorised facility scope. | Visit OPEN; ANC QueueEntry follows the ordinary receiving queue path. | MIDWIFE / CLINICIAN | Normal check-in scope, duplicate, inactive-patient, pricing, and destination safeguards apply. |
| 2 | MIDWIFE / CLINICIAN | Conduct the ANC contact and record the supported ANC documentation through the approved Encounter behaviour. | One ANC Encounter is OPEN and its ANC documentation remains attributable to that contact. | MIDWIFE / CLINICIAN | No automatic ANC risk classification, diagnosis, treatment suggestion, or invented threshold is applied; unresolved clinical validation remains OPEN/BLOCKED. |
| 3 | MIDWIFE / CLINICIAN | If investigation is required, place the laboratory order through the standard laboratory path and park the same Encounter when the source-defined hold applies. | LabOrderItem ORDERED; standard laboratory payment/collection/result states; consultation QueueEntry ON_HOLD where the Encounter parks. | SYSTEM / CASHIER / LAB_TECH | ANC has no special laboratory state machine or ANC-specific laboratory status. Under PAY_BEFORE, unpaid work is non-actionable with no patient-facing LAB QueueEntry until qualifying payment. |
| 4 | LAB_TECH / LAB_VERIFIER / SYSTEM | Complete the standard patient-facing laboratory and independent bench loop, then apply the standard readiness and resume paths to the same ANC Encounter. | LAB QueueEntry WAITING → CALLED → IN_SERVICE → COMPLETED; LabOrderItem follows standard states. When all blocking dependencies resolve: ANC Encounter AWAITING_RESULTS → RESULTS_READY and ANC consultation QueueEntry ON_HOLD → READY_TO_RESUME. Normal resume: same ANC Encounter RESULTS_READY → OPEN and QueueEntry READY_TO_RESUME → IN_SERVICE. Manual early resume: same ANC Encounter AWAITING_RESULTS → OPEN and QueueEntry ON_HOLD → IN_SERVICE; the Encounter ID is unchanged. | MIDWIFE / CLINICIAN | Partial release triggers neither readiness transition; SAMPLE_REJECTED, manual early resume, and late results use the standard J-02 rules. Unreleased values remain unavailable. No second ANC Encounter or ANC-specific laboratory state is created. |
| 5 | MIDWIFE / CLINICIAN | Review available results in the same Encounter and, where clinically authorised, prescribe medication or supplements through the standard prescription path. | Same Encounter remains the ANC clinical record; Prescription DRAFT → ACTIVE only after the applicable clinical signing path. | PHARMACIST / SYSTEM | If signed with pending results, use ENC-018 and LAB-023. No automatic interpretation, dosing, interaction checking, or treatment suggestion is introduced. |
| 6 | MIDWIFE / CLINICIAN / SYSTEM | Record the supported follow-up dependency and proceed through any applicable billing/payment path. | Follow-up need is recorded or referenced; applicable Invoice/payment/Receipt states remain standard. | RECEPTIONIST / CASHIER / patient follow-up | APT-001 and the full appointment workflow are UNSUPPLIED / OPEN / BLOCKED; no scheduling, reminder, slot, or permission behaviour is inferred. |
| 7 | RECEPTIONIST / CASHIER | Close the ANC visit only under the standard clinical, prescription, financial, and REC-012 conditions. | Visit CLOSED with ANC Encounter, laboratory, prescription, payment, receipt, and audit history preserved. | Terminal outcome | Unresolved clinical work, pending/blocked payment, or another unsafe closure condition refuses close; no ANC-specific shortcut is created. |

| Field | Value |
| --- | --- |
| Entry condition | An ANC visit is opened in an authorised V1 facility and an ANC provider is available; any investigation, prescription, and follow-up need is determined only by supported product behaviour. |
| Success outcome | One ANC Encounter records the contact; any investigation uses the standard laboratory loop; any medication/supplement uses the standard prescription path; the supported follow-up dependency and applicable billing/payment are preserved through safe closure. |
| Material failure outcomes | Standard check-in, clinical completeness, laboratory gate/result, prescription, payment, and closure failures apply. APT detail and unresolved clinical validation remain explicitly UNSUPPLIED / OPEN / BLOCKED. |
| Stories / invariants covered | REC-004; ANC-001/002/003..007; DX-008; APT-001 dependency; standard ENC, LAB, RX, PAY, and REC-012 paths; TI-01, TI-02, TI-03, TI-04, TI-05, TI-06, TI-07, TI-08, TI-09, TI-10, TI-11, TI-12, TI-13, TI-14, TI-15 where the corresponding standard path applies. |
| Release | V1 |

The supplied canonical backlog defines Journeys A–E only for this phase. Its
Journey F reference belongs to an unsupplied source part and is not
reconstructed; no J-06 is created.

Do not create a journey that bypasses a permission boundary, payment or
approval rule, or other canonical contract. Every handoff must land on a
defined receiving surface or explicit terminal outcome.

Source authority:

K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §5 and the referenced REC, QUE,
TRI, ENC, LAB, DX, RX, DSP, INV, BIL, PAY, RCP, and ANC stories; K:/new/clinicopus2.md
only where its compatible frozen product behaviour does not contradict the
reconciled supplied backlog; K:/clinicopus/AGENTS.md.

---

## 15. State Machines

Define every stateful domain that matters to product behaviour. The table is
authoritative; implementation agents must not invent transitions during
development.

### State-machine inventory

| Machine ID | Domain / record | Release | Owner | Terminal states | Reversible? | Concurrency rule |
| --- | --- | --- | --- | --- | --- | --- |
| SM-01 | QueueEntry | V1 | OPEN | COMPLETED, TRANSFERRED, CANCELLED, LWBS, EXPIRED | Explicit paths only: NO_SHOW may be re-queued; a pre-service payment reversal may re-gate; a cancelled LAB entry is replaced by a new authorised entry after repayment | One authoritative winner per transition; at most one active entry per visit+department and at most one IN_SERVICE entry per visit |
| SM-02 | Visit | V1 | OPEN | CLOSED, CANCELLED_ERROR | CLOSED has no normal reopening; permitted post-closure result/addendum activity is not reopening; CANCELLED_ERROR is not reversible | One authoritative closure/cancellation outcome; stale handling never silently closes records-bearing visits |
| SM-03 | TriageRecord | V1 | OPEN | COMPLETED for the current version | Amendments create attributable versions; COMPLETED never reopens to DRAFT | One authoritative completion/version outcome; no duplicate record for a visit |
| SM-04 | Encounter | V1 | OPEN | SIGNED (clinically final with explicit ENC-019 void path), VOIDED | Resume paths before signing; signed content is immutable except the explicit entered-in-error void path and addenda | One authoritative encounter per visit; competing resume/sign/readiness actions leave one valid outcome |
| SM-05 | LabOrderItem | V1 | OPEN | RELEASED, CANCELLED | Recollection and LAB-017 amendment/version paths preserve history; payment reversal may re-gate only before custody | One authoritative item transition; readiness is idempotent and requires every blocking item to be terminal |
| SM-06 | Prescription | V1 | OPEN | DISPENSED, PARTIALLY_DISPENSED_CLOSED, NOT_DISPENSED, CANCELLED | Explicit paths: PARTIALLY_DISPENSED may close only through the supplied visit-closure path; terminal records remain retained; controlled/Class A work is not a V1 path | One authoritative activation/dispense/cancellation outcome; no duplicate prescription or pharmacy work is created |
| SM-07 | Dispense | V1 | OPEN | CANCELLED, DISPENSED, REVERSED | CANCELLED is pre-handover only and cannot revive; DISPENSED is reversible only through the supplied audited return path | One authoritative handover and stock outcome; no duplicate dispense or stock movement |
| SM-08 | Invoice | V1 | OPEN | VOIDED | DRAFT is transient; PAID is final for its current allocations and current authoritative amount due, but a legitimate new line or valid CreditNote may recompute the current Invoice state under SM-08, while a valid full Payment reversal recomputes every affected Invoice under SM-08; paid invoices are never VOIDED through payment reversal or CreditNote creation; excess effective paid value is explicit REFUNDABLE CREDIT | One authoritative allocation and invoice-state outcome; no duplicate consultation line |
| SM-09 | Payment | V1 | OPEN | REVERSED | Original payment remains immutable; reversal is an attributable compensating record | One confirmed payment outcome under retries; one winner under concurrent balance actions |
| SM-10 | Appointment | V1 | OPEN | UNSUPPLIED / NONE | Fragment only: full appointment machine remains UNSUPPLIED / OPEN / BLOCKED; no transitions are invented | Explicit supplied fragment only; no invented appointment transitions |
| SM-11 | ANC enrolment / contact | V1 | OPEN | UNSUPPLIED / NONE | Fragment only: ANC enrolment closure is undefined; ANC contact uses SM-04 and investigations use SM-05 | Existing Encounter, LabOrderItem, and QueueEntry machines govern; no ANC-specific machine is invented |

### SM-01 — QueueEntry

| Field | Definition |
| --- | --- |
| Purpose | Represents one patient-facing service-stage position and its attributable movement through a department. It is the product location spine for a Visit. |
| States | WAITING_PAYMENT, WAITING, CALLED, IN_SERVICE, ON_HOLD, READY_TO_RESUME, NO_SHOW, COMPLETED, TRANSFERRED, CANCELLED, LWBS, EXPIRED. CLAIMED and IN_PROGRESS are not states. |
| Initial state | WAITING, or WAITING_PAYMENT when the applicable service gate is not yet released. |
| Terminal states | COMPLETED, TRANSFERRED, CANCELLED, LWBS, EXPIRED. These have no normal outgoing queue-state transition. |
| Reversibility | Explicit paths only: NO_SHOW is semi-terminal and may be re-queued; WAITING or CALLED may be re-gated to WAITING_PAYMENT before service begins; an in-service LAB payment-reversal cancellation is replaced by a new LAB entry after repayment. Terminal entries remain retained history. |
| Global constraints | 1. At most one active non-terminal QueueEntry exists per visit and department; active means WAITING_PAYMENT, WAITING, CALLED, IN_SERVICE, ON_HOLD, or READY_TO_RESUME.<br>2. An upstream ON_HOLD entry may coexist with a downstream WAITING, CALLED, or IN_SERVICE entry.<br>3. At most one QueueEntry for a Visit is IN_SERVICE globally at any instant.<br>4. A patient-facing LAB QueueEntry completes when collection or receipt ends; bench processing and result release continue independently.<br>5. Result release never completes a patient-facing LAB QueueEntry.<br>6. ON_HOLD is a return obligation, not the patient's physical location.<br>7. Current location derives from the active downstream QueueEntry where one exists.<br>8. Unpaid LabOrderItem worklist visibility is not a patient-facing LAB QueueEntry; the cashier entry is the current location until release creates the LAB entry.<br>9. Every transition and required reason remains attributable and auditable; held entries remain visible on the owning worklist and count as present in the facility.<br>10. Queue timing, expiry, and ordering use authoritative product time in EAT / Africa-Kampala. |
| Trigger types used | USER / SYSTEM / TIME. No approved EXTERNAL trigger is required by this machine. |

LAB_ONLY intake exception: a LAB_ONLY check-in opens the active Visit but does
not create a patient-facing LAB QueueEntry. A request-capture/intake worklist
before LabOrder creation is not an SM-01 QueueEntry, grants no specimen-
collection authority, is not READY_FOR_COLLECTION, and does not bypass a
payment gate.

TRI-013 emergency care-first exception: an authorised emergency-triage action
creates the consultation QueueEntry directly in WAITING with priority
EMERGENCY even while registration, payer, price-list, consultation charge,
Invoice, and payment remain pending. This is the narrow supplied care-first
path, not a general payment-gate override. Missing payer, price, or payment
cannot block emergency triage or emergency clinician service start; the
pending financial setup remains visible and blocks ordinary Visit closure
until the same Visit receives the canonical financial outcome defined by
TRI-013 / SM-02 / SM-08 / CMC-06. Emergency triage itself is substantive
service and transitions the same Visit OPEN → IN_PROGRESS in the TRI-013
initiation bundle without moving the consultation QueueEntry out of WAITING.
When that consultation entry later enters IN_SERVICE for clinician care, the
Visit remains IN_PROGRESS and no second Visit transition is recorded. Once
service is underway or delivered, later financial completion or reversal
never moves that service backward.

| From | Trigger type | Trigger / action | To | Actor / capability | Preconditions | Side effects | Audit / reason | Concurrency behaviour |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | USER / SYSTEM | Check-in, TRI-013 emergency initiation, or a completed stage creates the service entry. | WAITING or WAITING_PAYMENT | SYSTEM with the authorised reception, emergency-triage, or stage action | Visit is OPEN or IN_PROGRESS and destination is enabled. The applicable gate policy is known for ordinary paths; TRI-013 instead uses the explicit EMERGENCY_CARE_FIRST exception and creates WAITING regardless of unresolved payer/price/payment. | One entry is created with its Visit, department, queue type, priority, token, and authoritative queued time; an ordinarily gated entry is absent from the corresponding service worklist until released, while the TRI-013 consultation entry is immediately actionable with EMERGENCY priority and a visible pending-registration/financial marker. | QUEUE_ENTRY_CREATED with source stage and any required reason; TRI-013 records EMERGENCY_CARE_FIRST. | SINGLE WINNER; a retry has the same outcome and does not create a duplicate active entry. |
| WAITING_PAYMENT | USER / SYSTEM | Release the applicable gate after qualifying payment, authorised waiver, or authorised override. | WAITING | CASHIER plus SYSTEM; authorised gate capability where applicable | Gate policy applies and all required lines are paid, waived, or validly overridden. | The same entry becomes visible and actionable in the service worklist; no new Visit, queue entry, or service charge is created. | Gate release and payment/waiver/override reason are attributable. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| WAITING_PAYMENT | USER | Explicit REC-009 abandonment of an unpaid patient. | LWBS | RECEPTIONIST, NURSE, or SUPERVISOR with queue.remove | No unresolved encounter in OPEN, AWAITING_RESULTS, RESULTS_READY, or SIGNED; mandatory abandonment reason. | Direct terminal exit; no intermediate WAITING and no payment-success meaning; applicable Visit closes through the LWBS path. | QUEUE_ENTRY_REMOVED and VISIT_CLOSED_LWBS with reason. | SINGLE WINNER; a competing removal receives the committed current state. |
| WAITING_PAYMENT | USER / SYSTEM | Administrative or error removal. | CANCELLED | RECEPTIONIST, SUPERVISOR, or SYSTEM under the defined correction path | Mandatory removal reason and the applicable removal authority. | Entry remains in queue history and is not revived by later payment. | QUEUE_ENTRY_REMOVED with reason. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| WAITING_PAYMENT | TIME | Day-rollover sweep at the authoritative EAT / Africa-Kampala operational-day boundary. | EXPIRED | SYSTEM | Entry is still gated and belongs to the prior service day; the sweep is idempotent. | Entry is no longer active; visit handling follows the stale-visit rules and never converts unpaid abandonment into payment success. | QUEUE_SWEEP_RUN and per-entry EXPIRED reason DAY_ROLLOVER. | IDEMPOTENT / SAME OUTCOME. |
| WAITING | USER | Call the patient from the department worklist. | CALLED | Serving role with queue.serve | Entry is WAITING and remains the current entry. | Called actor/time and call attempt are retained; the patient-facing call invitation is shown. | QUEUE_CALLED with actor and time. | SINGLE WINNER; a competing call receives the safe current state. |
| WAITING | USER | Start the service directly from the waiting row. | IN_SERVICE | Serving role with queue.serve and the stage capability | Entry is WAITING and the stage may start immediately. | The product records the semantic call and service-start outcomes, retains called/served attribution and authoritative service timing, and creates or resumes the existing stage record. | QUEUE_CALLED and QUEUE_SERVICE_STARTED with actor and time. | SINGLE WINNER; a competing start receives the committed current state. |
| WAITING | USER | Remove the waiting patient for an administrative or error reason. | CANCELLED | RECEPTIONIST, NURSE, or SUPERVISOR with queue.remove | Mandatory non-LWBS removal reason. | Terminal history is retained; ordinary cancellation does not silently close the Visit. | QUEUE_ENTRY_REMOVED with reason. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| WAITING | USER | Explicit REC-009 abandonment of the waiting patient. | LWBS | RECEPTIONIST, NURSE, or SUPERVISOR with queue.remove | No unresolved encounter in OPEN, AWAITING_RESULTS, RESULTS_READY, or SIGNED; mandatory abandonment reason. | Direct terminal exit; the Visit closes through the LWBS path. | QUEUE_ENTRY_REMOVED and VISIT_CLOSED_LWBS with reason. | SINGLE WINNER; a competing removal receives the committed current state. |
| WAITING | TIME | Service-day expiry sweep. | EXPIRED | SYSTEM | Prior service day, never IN_SERVICE; authoritative EAT / Africa-Kampala time. | Entry leaves active worklists; stale Visit handling is applied without silently closing records-bearing visits. | QUEUE_SWEEP_RUN and DAY_ROLLOVER. | IDEMPOTENT / SAME OUTCOME. |
| WAITING | SYSTEM | Payment is reversed before service begins for the gated stage. | WAITING_PAYMENT | SYSTEM under PAY-012 | The entry is not IN_SERVICE or COMPLETED and the affected gate is again unpaid. | Existing entry is re-gated; the patient leaves the service worklist and must be released again. | PAYMENT_REVERSED and queue re-gate reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| CALLED | USER | Start the service stage. | IN_SERVICE | Serving role with queue.serve and the stage capability | The call is still valid and required stage data can be opened or resumed. | Service start is recorded, the wait measure freezes, and the existing stage record is created or resumed. | QUEUE_SERVICE_STARTED with actor and time. | SINGLE WINNER; losing start receives the committed current state. |
| CALLED | SYSTEM | Call invitation expires or the patient does not respond. | WAITING | SYSTEM | Configured call period elapsed and service has not started. | The call attempt history remains attributable, call attempts increment, and the entry returns to waiting with its original queued position rules. | QUEUE_CALL_EXPIRED / no-response reason. | IDEMPOTENT / SAME OUTCOME. |
| CALLED | SYSTEM | Payment is reversed before the gated service starts. | WAITING_PAYMENT | SYSTEM under PAY-012 | Gated service, payment no longer valid, and entry is not IN_SERVICE. | The call invitation ends; called actor/time and attempt history remain; after repayment the same entry returns only to WAITING, never silently to CALLED. | PAYMENT_REVERSED and re-gate reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| CALLED | USER | Mark the patient as no-show after the supplied call attempts. | NO_SHOW | Serving role with the no-show capability | Patient is absent and the no-show reason is recorded. | The entry is semi-terminal and recoverable by authorised re-queue; no normal service begins from this exit. | QUEUE_NO_SHOW with reason. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| CALLED | USER | Remove the called patient for an administrative or error reason. | CANCELLED | RECEPTIONIST or SUPERVISOR with queue.remove | Mandatory non-LWBS removal reason. | Terminal history is retained and is not revived by later payment. | QUEUE_ENTRY_REMOVED with reason. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| CALLED | USER | Explicit REC-009 abandonment of the called patient. | LWBS | RECEPTIONIST, NURSE, or SUPERVISOR with queue.remove | No unresolved encounter in OPEN, AWAITING_RESULTS, RESULTS_READY, or SIGNED; mandatory abandonment reason. | Direct terminal exit; the Visit closes through the LWBS path. | QUEUE_ENTRY_REMOVED and VISIT_CLOSED_LWBS with reason. | SINGLE WINNER; a competing removal receives the committed current state. |
| CALLED | TIME | Day-rollover sweep at the authoritative EAT / Africa-Kampala operational-day boundary. | EXPIRED | SYSTEM | Prior service day and service has not begun. | Entry is terminal and stale handling follows the Visit rules. | QUEUE_SWEEP_RUN and DAY_ROLLOVER. | IDEMPOTENT / SAME OUTCOME. |
| IN_SERVICE | USER | Complete the service stage after all mandatory stage data is present. | COMPLETED | Serving role with the stage completion capability | Completion rules are satisfied. | Service timing and completion are recorded; any onward entry is created as the defined next patient-visible outcome, with no partial handoff meaning. | QUEUE_SERVICE_COMPLETED and QUEUE_HANDOFF where applicable. | SINGLE WINNER; competing completion sees the committed outcome. |
| IN_SERVICE | USER | Redirect the patient to another department without completing this stage. | TRANSFERRED | Serving role with queue.move | Wrong-queue or other authorised transfer reason is supplied. | This entry is terminal and the receiving path is explicit; the original history remains readable. | QUEUE_TRANSFERRED with mandatory reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| IN_SERVICE | USER | Park the patient while a blocking dependency is unresolved. | ON_HOLD | CLINICIAN, scoped MIDWIFE, or scoped PHARMACIST | A blocking dependency and hold reason/ref exist. | Entry remains visible as a return obligation; the downstream active entry, if any, is the current patient location. | QUEUE_HELD with hold reason and reference. | SINGLE WINNER; hold and handoff outcome are all-or-nothing from the user's perspective. |
| IN_SERVICE | USER | Release an abandoned stage back to the queue through the canonical reasoned path. | WAITING | Serving role with the supplied release-back permission | Explicit abandoned/release-back reason exists and the stage has not completed. | Entry is again actionable without creating a second entry or stage record. | QUEUE_RETURNED with reason. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| IN_SERVICE | SYSTEM | Narrow laboratory payment-reversal cancellation before collection. | CANCELLED | SYSTEM under PAY-012 | queue type is LAB, policy is PAY_BEFORE, payment is reversed, no specimen custody or collection has completed, and all affected items remain before SAMPLE_COLLECTED. | Collection is blocked, no specimen is created, and any uncommitted collection attempt is discarded. After repayment a new authorised LAB QueueEntry WAITING is created; this entry is never reactivated. | PAYMENT_REVERSED, QUEUE_ENTRY_CANCELLED, and mandatory financial/reversal reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| ON_HOLD | SYSTEM | All blocking dependencies resolve. | READY_TO_RESUME | SYSTEM | Every referenced blocking LabOrderItem is RELEASED or CANCELLED; partial release and SAMPLE_REJECTED do not qualify. For a payment or procedure hold, the referenced dependency must likewise resolve. | Entry is highlighted for return within the supplied readiness timing while remaining the same return obligation; result release does not complete it. | QUEUE_READY_TO_RESUME with dependency evidence. | IDEMPOTENT / SAME OUTCOME. |
| ON_HOLD | USER | Resume early before dependencies resolve. | IN_SERVICE | CLINICIAN, MIDWIFE, or scoped PHARMACIST as applicable | Manual resume is authorised; the same stage record is resumed. | The downstream work may continue independently and the return obligation remains attributable. | QUEUE_RESUMED with actor and reason. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| ON_HOLD | USER | Explicit ENC-018 sign-with-pending-results action. | COMPLETED | CLINICIAN or MIDWIFE through the encounter-sign capability | The explicit pending-sign branch is valid; completion reason is SIGNED_WITH_PENDING_RESULTS. | Consultation entry completes without waiting for result release; later results follow their separate path. | QUEUE_SERVICE_COMPLETED with SIGNED_WITH_PENDING_RESULTS. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| ON_HOLD | USER / SYSTEM | Abandon an unpaid provisional pharmacy stage before handover. | CANCELLED | PHARMACIST, or the SYSTEM workflow invoked by that pharmacist action | Pharmacy hold is AWAITING_PAYMENT, no physical handover occurred, and a mandatory reason is supplied. | Provisional work is terminal and retained; a returning patient requires a new authorised pharmacy entry. | QUEUE_ENTRY_CANCELLED and abandonment reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| READY_TO_RESUME | USER | Resume the held stage. | IN_SERVICE | Authorised serving role | Entry is ready and the same stage record is available. | Patient returns to service; no second encounter or stage record is created. | QUEUE_RESUMED with actor and time. | SINGLE WINNER; competing resume receives the current state. |
| READY_TO_RESUME | SYSTEM | An undelivered payment dependency is reversed before its service begins. | ON_HOLD | SYSTEM under PAY-012 | The dependency is again unpaid and service has not begun. | Return obligation is visible again with the applicable payment reason. | PAYMENT_REVERSED and QUEUE_HELD reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| NO_SHOW | USER | Authorised re-queue after the patient is present. | WAITING | RECEPTIONIST with the re-queue capability | Re-queue is authorised; no new QueueEntry is created. | The same entry becomes actionable and its no-show history remains visible. | QUEUE_REQUEUED with reason. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| NO_SHOW | USER | Explicit abandonment after no-show. | LWBS | RECEPTIONIST, NURSE, or SUPERVISOR | REC-009 reason and unresolved-encounter guard. | Terminal LWBS path and Visit closure apply. | QUEUE_ENTRY_REMOVED / VISIT_CLOSED_LWBS. | SINGLE WINNER. |
| NO_SHOW | TIME | Service-day expiry sweep. | EXPIRED | SYSTEM | Prior service day and authoritative EAT / Africa-Kampala time. | Entry is terminal and stale history remains available. | QUEUE_SWEEP_RUN and DAY_ROLLOVER. | IDEMPOTENT / SAME OUTCOME. |

Invalid transitions and canonical errors: CLAIMED and IN_PROGRESS are not
QueueEntry states. WAITING_PAYMENT must not pass through WAITING merely to
reach LWBS, CANCELLED, or EXPIRED. A terminal state has no normal outgoing
transition; a cancelled LAB entry after payment reversal is never revived.
IN_SERVICE → CANCELLED is permitted only for the narrow LAB pre-collection
payment-reversal rule above; once specimen custody exists, that path is
forbidden. Invalid guards use the existing families
INVALID_STATE, PREREQUISITE_MISSING, PERMISSION_DENIED, VERSION_CONFLICT, or
ALREADY_EXISTS as applicable.

Trust mapping: TI-01 / RG-01 (scope), TI-02 / RG-02 (server authority),
TI-09 / RG-09 (single committed outcome), TI-10 / RG-10 (duplicate and retry
safety), TI-11 / RG-11 (stale state), TI-13 / RG-13 (audit reconstruction),
and TI-15 / RG-15 (authoritative high-impact finalisation).

Source authority: K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §22.1;
QUE-001, QUE-003, QUE-005, QUE-006, QUE-007, QUE-016; REC-001, REC-005,
REC-009, REC-010, REC-012; ENC-002, ENC-016, ENC-018; LAB-005, LAB-008,
LAB-009, LAB-018; DSP-005, DSP-008; PAY-012; plus the applicable referenced queue, reception,
encounter, laboratory, dispensing, and payment story contracts.

### SM-02 — Visit

REC-005 stale abandonment is a narrowly bounded administrative closure path,
not an alternate clinical closure. It must satisfy the applicable REC-012
unresolved-work safety guards before closure: no Encounter OPEN,
AWAITING_RESULTS, or RESULTS_READY; no SIGNED Encounter is being shortcut
around; and no active laboratory, prescription/pharmacy, or other protected
non-financial clinical/service blocker. REC-005's explicit stale queue/invoice
cleanup is performed as part of that abandonment outcome and is not required
to have already occurred or to have already satisfied REC-012's ordinary
queue/financial completion prerequisites. The zero-record nightly abandonment
rule and morning-review path remain unchanged.

| Field | Definition |
| --- | --- |
| Purpose | Represents one patient attendance episode from successful ordinary check-in or authorised TRI-013 emergency care-first initiation through an authorised closure or a pre-service error cancellation. |
| States | OPEN, IN_PROGRESS, CLOSED, CANCELLED_ERROR. |
| Initial state | OPEN at successful ordinary check-in. TRI-013 creates its Visit in OPEN and, because emergency triage starts substantive service immediately, transitions that same Visit OPEN → IN_PROGRESS within the same authoritative initiation outcome; no completed TRI-013 initiation exposes an OPEN Visit. |
| Terminal states | CLOSED and CANCELLED_ERROR. CLOSED carries a closure reason; the reason is not a separate state. |
| Reversibility | CLOSED has no normal reopening. Permitted late-result/addendum activity and review flags do not reopen it. CANCELLED_ERROR is not reversible and its visit number is never reused. |
| Global constraints | A patient has at most one ordinary open Visit per day at a facility unless the supplied supervisor-approved second-episode path applies. TRI-013 creates one provisional emergency Visit and transitions it to IN_PROGRESS when emergency triage starts in the same initiation bundle; later TriageRecord completion, clinician service start, registration/financial completion, and merge reuse it rather than create another Visit or repeat the Visit transition. Closure preserves clinical, financial, queue, laboratory, prescription, and audit history. A Visit cannot close with an unresolved unsigned Encounter or unresolved TRI-013 registration/financial setup. CLOSED(PENDING_RESULTS) requires the explicit signed-with-pending-orders path. STALE_OPEN, POST_CLOSURE_ACTIVITY, REVIEW_REQUIRED, and EMERGENCY_FINANCIAL_SETUP_PENDING are flags/obligations, not Visit states. |
| Trigger types used | USER / SYSTEM / TIME. No approved EXTERNAL trigger is required by this machine. |

| From | Trigger type | Trigger / action | To | Actor / capability | Preconditions | Side effects | Audit / reason | Concurrency behaviour |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | USER / SYSTEM | Successful authorised check-in opens the attendance episode. | OPEN | RECEPTIONIST / SYSTEM with visit.create | Active patient, authorised facility context, valid visit type, destination, and required pricing. | Visit number and attendance record exist; the first applicable QueueEntry and one chargeable consultation line are created according to the check-in contract. | VISIT_OPENED and QUEUE_ENTRY_CREATED. | SINGLE WINNER; a repeated request returns the existing safe outcome and does not create a second Visit. |
| — | USER / SYSTEM | Start TRI-013 emergency care before ordinary registration and financial setup. | IN_PROGRESS | NURSE, CLINICIAN, or MIDWIFE with triage.create_emergency plus SYSTEM | Authorised facility and emergency destination exist; minimum provisional identity is supplied. Payer, price list, price, Invoice, and payment are not preconditions. | As one committed bundle, one provisional Patient and one emergency Visit in OPEN are created; emergency triage starts a DRAFT TriageRecord and immediately transitions that same Visit OPEN → IN_PROGRESS; one consultation QueueEntry remains WAITING with EMERGENCY priority; no triage QueueEntry exists. EMERGENCY_FINANCIAL_SETUP_PENDING is visible, and no payer, price, consultation line, Invoice, payment success, or gate release is guessed. | PROVISIONAL_PATIENT_CREATED, VISIT_OPENED, TRIAGE_STARTED, VISIT_IN_PROGRESS, QUEUE_ENTRY_CREATED, and EMERGENCY_CARE_FIRST. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME; retry returns the same IN_PROGRESS Visit and cannot create a second Patient, Visit, TriageRecord, QueueEntry, or Visit transition. |
| IN_PROGRESS | USER / SYSTEM | Complete the TRI-013 registration and financial setup for the existing emergency Visit. | IN_PROGRESS | RECEPTIONIST or other actor already authorised for the ordinary registration/financial fields, plus SYSTEM | The same emergency Visit is active; authoritative payer and price-list selections are supplied; the consultation service/price is valid. Care may already be underway or completed and is not moved backward. | On the same Visit, exactly one consultation line and exactly one Visit-linked Invoice are created and the Invoice reaches ISSUED; EMERGENCY_FINANCIAL_SETUP_PENDING clears. Existing Encounter, queue, clinical, and financial history is re-associated to the surviving Patient on an authorised merge without duplication. Signing and merge never create the charge or another Visit transition. | EMERGENCY_FINANCIAL_SETUP_COMPLETED, CONSULTATION_LINE_CREATED, and INVOICE_ISSUED with the original emergency Visit reference; PATIENT_MERGED where applicable. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME; retry or merge returns/reuses the existing Visit, consultation line, and Invoice; conflicting payer/price input requires explicit reconciliation. |
| OPEN | SYSTEM | The first QueueEntry-backed substantive patient service begins for an ordinary OPEN Visit. | IN_PROGRESS | SYSTEM when a queue entry enters service | A valid QueueEntry begins service and the Visit is still OPEN. TRI-013 is not this path because its emergency triage already moved the Visit to IN_PROGRESS without a triage QueueEntry. | Visit records the start of substantive service; the episode is no longer eligible for pre-service REC-010 cancellation. A later TRI-013 consultation QueueEntry service start changes only that QueueEntry and related clinician work; its Visit remains IN_PROGRESS and no second VISIT_IN_PROGRESS transition is emitted. | VISIT_IN_PROGRESS with authoritative time for the ordinary OPEN → IN_PROGRESS transition. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| OPEN | USER / SYSTEM | Complete the supplied close checklist before substantive service or through an authorised terminal path. | CLOSED | RECEPTIONIST, CASHIER, CLINICIAN handoff, or authorised SYSTEM path | All required queue, Encounter, laboratory, prescription, and financial conditions are satisfied; any TRI-013 EMERGENCY_FINANCIAL_SETUP_PENDING obligation is resolved; closure reason is one of COMPLETED, PENDING_RESULTS, ABANDONED, INCOMPLETE, LWBS, or LWBS_PAID. | Visit leaves currently-present counts and remains fully readable; no ordinary new clinical or billing record may be attached. | VISIT_CLOSED with closed_by, closed_at, closure reason, and required non-sensitive checklist evidence. | SINGLE WINNER; a concurrent close sees the committed state. |
| OPEN | USER | Correct an erroneous check-in during the pre-service grace window. | CANCELLED_ERROR | RECEPTIONIST with visit.cancel_error | Visit is under the grace limit and has no vitals, encounter, or payment; mandatory reason supplied. | Queue entry is CANCELLED, unpaid invoice is voided through its defined path, history remains queryable, and the visit number is not reused. | VISIT_CANCELLED_ERROR with reason and elapsed time. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| OPEN | TIME | Nightly stale handling at the authoritative EAT / Africa-Kampala operational-day boundary. | CLOSED | SYSTEM | Visit has no clinical or financial records and satisfies the zero-record stale rule. | Visit closes as CLOSED(ABANDONED); other stale visits are not silently closed and instead receive STALE_OPEN or REVIEW_REQUIRED for the supplied review path. | QUEUE_SWEEP_RUN and VISIT_CLOSED with ABANDONED, or the applicable review flag. | IDEMPOTENT / SAME OUTCOME. |
| IN_PROGRESS | USER / SYSTEM | Apply REC-012 when all required work is finished or one of its explicitly supplied closure alternatives is satisfied. | CLOSED | RECEPTIONIST / CASHIER / authorised actor with the exact closure capability required by that path | No unsigned OPEN, AWAITING_RESULTS, or RESULTS_READY Encounter; every queue, laboratory, prescription/pharmacy, provisional Dispense, and financial outcome satisfies the ordinary checklist or the complete semantics of an explicitly supplied alternative. PENDING_RESULTS requires a SIGNED Encounter with signed_with_pending_orders and the consultation QueueEntry completed by ENC-018; debt and waiver use BIL-014/BIL-009; partial dispensing uses the supplied PARTIALLY_DISPENSED_CLOSED outcome. | Visit closes with the selected supplied reason; active laboratory work may remain only under the signed-pending rule, and later release uses LAB-023 without reopening. No undefined blocker is discarded or converted to terminal state by Visit closure. | VISIT_CLOSED with reason and the applicable supplied closure/debt/waiver reference. | SINGLE WINNER / EXPLICIT RECONCILIATION. |

Closure and stale notes: CLOSED is terminal operationally and has no normal
reopening. A late released laboratory result may append its permitted
LAB-023/addendum record and set POST_CLOSURE_ACTIVITY, but it never reopens
the Visit. A paid-invoice stale case is flagged REVIEW_REQUIRED rather than
silently written off. A visit with a signed encounter may be closed as
CLOSED(INCOMPLETE) only after the supplied morning review and closure
semantics. An
IN_PROGRESS visit cannot transition to CANCELLED_ERROR.

Invalid transitions and canonical errors: IN_PROGRESS → CANCELLED_ERROR,
ordinary CLOSED reopening, and any closure that bypasses an unsigned encounter
are INVALID_STATE or PREREQUISITE_MISSING. Duplicate check-in uses
ALREADY_EXISTS or the existing VISIT_ALREADY_OPEN contract; missing authority
uses PERMISSION_DENIED; stale competing closure uses VERSION_CONFLICT.
Closure reasons and flags are not additional Visit states.

Trust mapping: TI-01 / RG-01 (scope), TI-02 / RG-02 (server authority),
TI-03 / RG-03 (retained clinical history), TI-08 / RG-08 (financial
final-record integrity), TI-09 / RG-09 (single closure outcome),
TI-10 / RG-10 (duplicate safety), TI-11 / RG-11 (stale state),
TI-13 / RG-13 (audit reconstruction), and TI-15 / RG-15 (authoritative
finalisation).

Source authority: K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §22.2;
REC-005, REC-009, REC-010, REC-012; TRI-013; QUE-016; ENC-018; LAB-023; and the
applicable supplied visit, queue, encounter, laboratory, and payment story
contracts.

### SM-03 — TriageRecord

| Field | Definition |
| --- | --- |
| Purpose | Represents authorised human-recorded triage observations and explicit acuity that normally forward to clinician workflow on completion; TRI-013 is the bounded care-first exception in which the emergency consultation entry already exists and is reused. |
| States | DRAFT, COMPLETED. |
| Initial state | DRAFT. An existing record for the Visit is resumed rather than duplicated. |
| Terminal states | COMPLETED for the current version. |
| Reversibility | COMPLETED does not reopen to DRAFT. TRI-008 creates an attributable amendment/version path that preserves the prior record. |
| Global constraints | At most one current ordinary or TRI-013 emergency TriageRecord exists for a Visit; an explicitly authorised re-triage path is distinct. Completion requires the supplied minimum observations and a human-selected acuity. TRI-013 initiation is an explicit human emergency action, not an inferred or pre-selected acuity, and creates the current record in DRAFT without requiring an ordinary triage QueueEntry. Amendments preserve history, do not silently change a signed note, and do not retroactively alter an already-seen queue priority. |
| Trigger types used | USER / SYSTEM. No approved EXTERNAL trigger is required by this machine. |

| From | Trigger type | Trigger / action | To | Actor / capability | Preconditions | Side effects | Audit / reason | Concurrency behaviour |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | USER | Open triage for a queued patient. | DRAFT | NURSE, or explicitly scoped MIDWIFE, with triage.create | QueueEntry is WAITING at the triage department and the Visit is available. If a record already exists, it is opened rather than recreated. | Draft observations are recoverable and the triage QueueEntry enters IN_SERVICE. | TRIAGE_STARTED and draft-save evidence. | SINGLE WINNER; a competing start receives the existing record/current state. |
| — | USER / SYSTEM | Start the explicit TRI-013 emergency triage path without prior check-in or a triage QueueEntry. | DRAFT | NURSE / CLINICIAN / MIDWIFE with triage.create_emergency; SYSTEM performs the authorised bundle | TRI-013 minimum identity is supplied, the actor explicitly selects the emergency action, and no current TriageRecord exists; a concurrent existing record is resumed rather than duplicated. | The TRI-013 provisional Patient, Visit, DRAFT TriageRecord, and one consultation QueueEntry at EMERGENCY priority are created as the supplied care-first bundle. Emergency triage is substantive service, so the same Visit is created OPEN and transitions to IN_PROGRESS in that bundle. No triage QueueEntry is required or invented; the consultation entry remains WAITING and immediately actionable under the bounded emergency exception. | PROVISIONAL_PATIENT_CREATED, VISIT_OPENED, TRIAGE_STARTED, VISIT_IN_PROGRESS, QUEUE_ENTRY_CREATED, and EMERGENCY_CARE_FIRST with actor and references. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME; retry returns the same Patient, IN_PROGRESS Visit, TriageRecord, and consultation QueueEntry without another Visit transition. |
| DRAFT | USER | Save the incomplete triage form. | DRAFT | NURSE / scoped MIDWIFE; CLINICIAN only for an authorised TRI-013 record | Draft may be saved while incomplete; no completion is claimed. The actor has the applicable ordinary triage capability or triage.create_emergency for TRI-013. | Recorded values and permitted not-done reasons remain visible for recovery. On the ordinary path no onward clinical entry is created until completion; on TRI-013 the already-created emergency consultation entry is retained and no additional entry is created. | TRIAGE_SAVED with actor and time. | IDEMPOTENT / SAME OUTCOME for retries; stale edits require explicit reconciliation. |
| DRAFT | USER | Complete triage and forward the patient. | COMPLETED | NURSE / scoped MIDWIFE with the applicable triage capability; CLINICIAN only for an authorised TRI-013 record with triage.create_emergency | At least one required vital or authorised not-done reason where applicable; presenting complaint; explicit human-selected acuity; no default or pre-selected acuity. | Triage becomes read-only for the current version. On the ordinary path, the triage QueueEntry completes and one onward consultation QueueEntry is created with the selected priority. On TRI-013, no triage QueueEntry is invented: the already-created emergency consultation QueueEntry is reused in its current non-terminal actionable state, remains EMERGENCY priority unless an authorised later priority change occurs, and no second consultation entry is created. | TRIAGE_COMPLETED and the applicable ordinary handoff or TRI-013 queue-reuse audit with actor. | SINGLE WINNER; competing completion cannot create a second record or onward entry. |
| COMPLETED | USER | Correct a completed triage record through TRI-008. | COMPLETED (new version; state remains completed) | Authoring NURSE within the amendment window, or SUPERVISOR / FACILITY_ADMIN through triage.amend_any | Mandatory reason, authorised scope, and applicable amendment window or supervisor authority. | New version/amendment retains before/after references and reason; original remains retrievable. The current value is shown as amended; the signed clinical note is unchanged. | TRIAGE_AMENDED with version references, changed field names, actor, and reason; no raw clinical payload in generic audit. | SINGLE WINNER / EXPLICIT RECONCILIATION; stale amendment cannot silently overwrite a newer version. |

Invalid transitions and canonical errors: COMPLETED → DRAFT is not allowed;
AMENDED and REOPENED are not states. A second current ordinary or TRI-013
TriageRecord for one Visit is refused. Missing completion data uses PREREQUISITE_MISSING or
ACUITY_REQUIRED; missing authority uses PERMISSION_DENIED; stale competing
updates use VERSION_CONFLICT; a closed or unavailable Visit uses
INVALID_STATE.

Trust mapping: TI-01 / RG-01 (scope), TI-02 / RG-02 (server authority),
TI-09 / RG-09 (single completion), TI-10 / RG-10 (duplicate safety),
TI-11 / RG-11 (stale amendments), TI-12 / RG-12 (sensitive payload
minimisation), TI-13 / RG-13 (audit reconstruction), and TI-14 / RG-14
(no unapproved clinical interpretation or automatic acuity).

Source authority: K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §22.3;
TRI-001, TRI-006, TRI-008, TRI-009, TRI-013; and the applicable supplied queue and
triage story contracts.

### SM-04 — Encounter

| Field | Definition |
| --- | --- |
| Purpose | Represents one clinician or midwife clinical work record for a Visit, including a resumable results hold and the immutable signed outcome. |
| States | OPEN, AWAITING_RESULTS, RESULTS_READY, SIGNED, VOIDED. |
| Initial state | OPEN for a new Encounter. If a non-terminal Encounter already exists for the Visit, the workflow resumes that Encounter instead of creating another. |
| Terminal states | SIGNED and VOIDED. SIGNED is clinically final and immutable for ordinary care, with the explicit entered-in-error ENC-019 void exception. |
| Reversibility | OPEN, AWAITING_RESULTS, and RESULTS_READY have the explicit resume/park paths. SIGNED has no ordinary reopening; ENC-023 addenda and the exceptional ENC-019 void path preserve history. VOIDED is retained and not deleted. |
| Park reasons | AWAITING_RESULTS, AWAITING_PROCEDURE, AWAITING_PAYMENT, and PATIENT_STEPPED_OUT are attributes/reasons for AWAITING_RESULTS, not additional Encounter states. |
| Global constraints | Exactly one non-terminal Encounter exists per Visit. AWAITING_RESULTS is a return obligation with a reason, not a second Encounter. RESULTS_READY occurs only when every blocking referenced LabOrderItem is RELEASED or CANCELLED; partial release and SAMPLE_REJECTED do not qualify. Manual early resume is allowed before all results. Signing with pending orders is only the explicit ENC-018 path. |
| Trigger types used | USER / SYSTEM. No approved EXTERNAL trigger is required by this machine. |

| From | Trigger type | Trigger / action | To | Actor / capability | Preconditions | Side effects | Audit / reason | Concurrency behaviour |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | USER | Create the clinician or midwife work record when service begins. | OPEN | CLINICIAN / MIDWIFE with encounter.create | Visit is available and no other non-terminal Encounter exists; an existing non-terminal record is resumed instead. | One Encounter is associated with the Visit and the same identifier is used for all later resumes. | ENCOUNTER_OPENED with actor and Visit reference. | SINGLE WINNER; a competing create receives or resumes the existing Encounter. |
| OPEN | USER | Park while awaiting laboratory results, a procedure, payment, or a patient who stepped out. | AWAITING_RESULTS | CLINICIAN, or scoped MIDWIFE | A blocking dependency or explicit park reason and hold reference exist. | Encounter remains open and resumable; the consultation QueueEntry becomes ON_HOLD with the matching reason. | ENCOUNTER_PARKED with reason and reference. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| OPEN | USER | Complete a normal valid clinical sign. | SIGNED | CLINICIAN / MIDWIFE with encounter.sign | Minimum complaint, explicitly captured allergy status (one or more active allergies, NKA / NO_KNOWN_ALLERGIES, or UNKNOWN), diagnosis or permitted no-diagnosis reason, and disposition are present; no pending-sign exception is being used. | Clinical record is immutable and the normal consultation QueueEntry completion/handoff occurs. | ENCOUNTER_SIGNED with actor and authoritative time. | SINGLE WINNER; retries return the same signed outcome without duplicate fan-out. |
| OPEN | USER | Use the explicit ENC-018 “Sign now” branch while orders remain pending. | SIGNED | CLINICIAN / MIDWIFE with encounter.sign | Pending order path is explicitly selected and valid; the Visit is not closed. | signed_with_pending_orders is recorded; the consultation QueueEntry completes with reason SIGNED_WITH_PENDING_RESULTS and late results follow their separate path. | ENCOUNTER_SIGNED with SIGNED_WITH_PENDING_RESULTS reason. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| OPEN | USER | Correct an entered-in-error unsigned Encounter. | VOIDED | Authorised CLINICIAN or SUPERVISOR | Mandatory reason and entered-in-error authority; every related non-terminal LabOrderItem is already resolved through LAB-022, otherwise void is refused with the exact blockers. | Full record is retained with visible VOIDED status; related draft prescriptions are cancelled as supplied, while terminal laboratory history is preserved and detached/flagged where applicable. | ENCOUNTER_VOIDED with mandatory reason and downstream-resolution evidence. | SINGLE WINNER / EXPLICIT RECONCILIATION; a competing lab commit requires refresh and re-evaluation. |
| AWAITING_RESULTS | SYSTEM | Recompute readiness after result or cancellation changes. | RESULTS_READY | SYSTEM | ALL blocking LabOrderItems referenced by the hold, across every referenced order, are RELEASED or CANCELLED; SAMPLE_REJECTED and partial release do not qualify. | Encounter is highlighted for resume and the consultation QueueEntry becomes READY_TO_RESUME; released values remain governed by their own history. | ENCOUNTER_RESULTS_READY with dependency evidence. | IDEMPOTENT / SAME OUTCOME; repeated signals do not duplicate readiness. |
| AWAITING_RESULTS | USER | Resume manually before results are all complete. | OPEN | CLINICIAN / MIDWIFE | Authorised early resume; the same Encounter identifier is used. | Clinician continues with pending work visible as pending; remaining laboratory work continues independently. | ENCOUNTER_RESUMED with early-resume reason where required. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| AWAITING_RESULTS | USER | Use ENC-018 “Sign now” with pending orders. | SIGNED | CLINICIAN / MIDWIFE | Explicit pending-sign branch and minimum sign requirements; Visit not closed. | Immutable signed record, signed_with_pending_orders, and consultation QueueEntry completion with SIGNED_WITH_PENDING_RESULTS; no intermediate OPEN or IN_SERVICE state is fabricated. | ENCOUNTER_SIGNED with pending-results reason. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| AWAITING_RESULTS | USER | Correct an entered-in-error Encounter. | VOIDED | Authorised CLINICIAN or SUPERVISOR | Mandatory reason and entered-in-error authority; every related non-terminal LabOrderItem is already resolved through LAB-022, otherwise void is refused with the exact blockers. | Full history retained; terminal laboratory history is preserved and detached/flagged where applicable, and no active lab work is orphaned. | ENCOUNTER_VOIDED with reason and downstream-resolution evidence. | SINGLE WINNER / EXPLICIT RECONCILIATION; a competing lab commit requires refresh and re-evaluation. |
| RESULTS_READY | USER | Resume the ready Encounter. | OPEN | CLINICIAN / MIDWIFE | Readiness is authoritative and the same Encounter remains non-terminal. | Same Encounter opens for review; no duplicate Encounter is created. | ENCOUNTER_RESUMED. | SINGLE WINNER; competing resume receives the current state. |
| RESULTS_READY | USER | Sign after reviewing the available results. | SIGNED | CLINICIAN / MIDWIFE | Normal sign requirements are satisfied. | Clinical record becomes immutable and the consultation path proceeds. | ENCOUNTER_SIGNED. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| RESULTS_READY | USER | Correct an entered-in-error Encounter. | VOIDED | Authorised CLINICIAN or SUPERVISOR | Mandatory reason and entered-in-error authority; every related non-terminal LabOrderItem, including any non-blocking item not covered by the readiness calculation, is already resolved through LAB-022. | Full history retained with visible VOIDED status; released laboratory history is preserved and detached/flagged where applicable. | ENCOUNTER_VOIDED with reason and downstream-resolution evidence. | SINGLE WINNER / EXPLICIT RECONCILIATION; a competing lab commit requires refresh and re-evaluation. |
| SIGNED | USER | Entered-in-error correction of a signed Encounter under ENC-019. | VOIDED | SUPERVISOR with the required entered-in-error authority | Exceptional path only; mandatory reason, full history retention, and visible void status. Every related non-terminal LabOrderItem and every still-actionable unhanded prescription, undispensed remainder, pharmacy QueueEntry, and provisional Dispense is already non-actionable through the supplied LAB-022, RX-009, and DSP-005 paths; otherwise the void is refused with the exact blockers. | Signed clinical content is not ordinarily edited. Already delivered/handed-over medicine and its stock history, paid financial effects, and released laboratory results are not silently reversed or deleted; their separate correction/review paths remain visible. | ENCOUNTER_VOIDED with supervisor, reason, audit, visible VOIDED watermark/status, and downstream-resolution evidence. | SINGLE WINNER / EXPLICIT RECONCILIATION; a competing downstream commit requires refresh and re-evaluation before void. |

Source reconciliation note: the source table marks SIGNED as terminal with
addenda only, while its VOIDED row and ENC-019 define a signed-to-voided
entered-in-error path. This Product Spec therefore treats SIGNED as
OPERATIONALLY / CLINICALLY FINAL WITH EXPLICIT ENTERED-IN-ERROR VOID PATH.
Ordinary clinical workflow cannot edit or reopen signed content; ENC-023
addenda and the authorised ENC-019 exception retain the complete history.
VOIDED remains retained in full, is hidden from the ordinary clinical timeline
by default where that presentation rule applies, remains available through
authorised include-voided access, and never silently reverses paid financial
effects or deletes released laboratory results.

Invalid transitions and canonical errors: a second non-terminal Encounter,
partial-release RESULTS_READY, ordinary SIGNED → OPEN, ordinary edits to a
SIGNED record, VOIDED reopening, and pending signing without ENC-018 are
INVALID_STATE or PREREQUISITE_MISSING. An existing active Encounter uses
ALREADY_EXISTS or the same-Encounter resume path; missing authority uses
PERMISSION_DENIED; stale resume/sign attempts use VERSION_CONFLICT. VOIDED
never means hard deletion.

Trust mapping: TI-01 / RG-01 (scope), TI-02 / RG-02 (server authority),
TI-03 / RG-03 (clinical-history correction integrity), TI-04 / RG-04
(released-result integrity), TI-09 / RG-09 (single committed outcome),
TI-10 / RG-10 (duplicate and retry safety), TI-11 / RG-11 (stale state),
TI-12 / RG-12 (sensitive payload minimisation), TI-13 / RG-13 (audit
reconstruction), and TI-15 / RG-15 (authoritative clinical finalisation).

Source authority: K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §22.4;
ENC-001, ENC-002, ENC-016, ENC-017, ENC-018, ENC-019, ENC-023; LAB-018,
LAB-022, LAB-023; RX-009; DSP-005; and the applicable supplied encounter,
queue, laboratory, pharmacy, and clinical story contracts.

### SM-05 — LabOrderItem

| Field | Definition |
| --- | --- |
| Purpose | Represents one authorised laboratory test request through collection, result verification, release, cancellation, or the P2 external-return path. |
| States | ORDERED, AWAITING_PAYMENT, READY_FOR_COLLECTION, SAMPLE_COLLECTED, SAMPLE_REJECTED, RESULT_ENTERED, VERIFIED, RELEASED, CANCELLED, REFERRED_OUT (P2). REQUESTED, RESULT_RELEASED, and IN_PROGRESS are not V1 states. |
| Initial state | ORDERED. |
| Terminal states | RELEASED and CANCELLED. REFERRED_OUT is non-terminal P2; SAMPLE_REJECTED is recoverable and non-terminal. |
| Reversibility | READY_FOR_COLLECTION may return to AWAITING_PAYMENT only for payment reversal before collection. SAMPLE_REJECTED may return to READY_FOR_COLLECTION for recollection. Released results use LAB-017 version/amendment history and are not destructively edited. |
| Global constraints | LabOrder presentation is derived from its LabOrderItems and is not a separate transition machine. AWAITING_PAYMENT is visible to the laboratory worklist but is not actionable and is not a patient-facing LAB QueueEntry; the patient-facing entry exists only after release. SAMPLE_COLLECTED is the custody boundary: payment reversal after it restores financial truth but never moves laboratory processing backward. Recollection keeps the original work and creates no automatic new charge or order. A result contributes to Encounter RESULTS_READY and consultation READY_TO_RESUME only when every blocking item is RELEASED or CANCELLED. |
| Trigger types used | USER / SYSTEM. Returned REFERRED_OUT results are entered through an authorised user action; no approved EXTERNAL event is required by this machine. |

Initial creation has two authorised paths: the Encounter-based `lab.order.create`
path below and the LAB_ONLY external/walk-in `lab.order.create.external` path
below. Neither path adds a state or broadens ordinary nurse ordering authority.

| From | Trigger type | Trigger / action | To | Actor / capability | Preconditions | Side effects | Audit / reason | Concurrency behaviour |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | USER | Clinician or midwife orders one priced laboratory test. | ORDERED | CLINICIAN / MIDWIFE with lab.order.create | Encounter is OPEN or RESULTS_READY and the test is available and priced. | One LabOrderItem is visible with its source Encounter and ordering context. | LAB_ORDERED with actor and test reference. | SINGLE WINNER; retry does not create a duplicate item. |
| — | USER | Authorised external/walk-in laboratory request captured under LAB-024. | ORDERED | LAB_TECH or RECEPTIONIST with lab.order.create.external | Active Visit exists; Visit type is LAB_ONLY; Visit state is OPEN or IN_PROGRESS; laboratory module is enabled; selected test is available and priced; supplied external-request fields satisfy LAB-024; no Encounter is required. | LabOrder and LabOrderItem link to the Visit and patient; no Encounter relationship is invented; external requester/source context is retained; charge generation follows LAB-004 and gate evaluation follows LAB-005. | LAB_ORDERED_EXTERNAL, or the existing canonical attributable external-order event, with actor and request context. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME; retry does not duplicate the order, item, or charge. |
| ORDERED | SYSTEM | Apply LABORATORY=PAY_BEFORE gating. | AWAITING_PAYMENT | SYSTEM | Applicable laboratory gate requires payment and the line is unpaid. | Item is visible to the lab as non-actionable; no patient-facing LAB QueueEntry is created. | LAB_PAYMENT_GATE_APPLIED. | IDEMPOTENT / SAME OUTCOME. |
| ORDERED | SYSTEM | Gate is already clear or not required. | READY_FOR_COLLECTION | SYSTEM | Qualifying payment, waiver, override, or no gate applies. | Item becomes actionable; the patient-facing LAB QueueEntry may be created as WAITING. | LAB_READY_FOR_COLLECTION. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| ORDERED | USER | Authorised cancellation before collection. | CANCELLED | CLINICIAN or SUPERVISOR with the supplied cancellation capability | Cancellation reason and authority are present. | Item is terminal, retained, and counted as terminal for blocking readiness. | LAB_ITEM_CANCELLED with reason. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| AWAITING_PAYMENT | USER / SYSTEM | Qualifying payment, authorised waiver, or authorised override releases the laboratory gate. | READY_FOR_COLLECTION | SYSTEM with CASHIER / authorised gate action | LABORATORY=PAY_BEFORE item remains uncollected and release authority is valid. | Item becomes actionable; the patient-facing LAB QueueEntry is then created as WAITING. | LAB_PAYMENT_RELEASED with payment/waiver/override reference. | SINGLE WINNER; repeated release has the same outcome. |
| AWAITING_PAYMENT | USER | Authorised cancellation before collection. | CANCELLED | CLINICIAN or SUPERVISOR | Mandatory cancellation reason. | No patient-facing LAB QueueEntry is created; item remains terminal history. | LAB_ITEM_CANCELLED with reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| READY_FOR_COLLECTION | USER | Collect and accept the identified specimen. | SAMPLE_COLLECTED | LAB_TECH or NURSE with lab.sample.collect | Identity read-back, collection completed, and specimen custody established. | Specimen identity/custody is recorded; the patient-facing LAB QueueEntry completes at the collection/receipt interaction while bench work continues. | LAB_SAMPLE_COLLECTED with actor, time, and specimen reference. | SINGLE WINNER; duplicate collection is refused or reconciled to the current state. |
| READY_FOR_COLLECTION | USER | Record that the patient cannot provide a usable specimen or another supplied collection rejection applies. | SAMPLE_REJECTED | LAB_TECH | Mandatory rejection reason; no specimen custody is established. | Item is actionable for recollection or authorised cancellation; it does not satisfy all-blocking readiness. | LAB_SAMPLE_REJECTED with reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| READY_FOR_COLLECTION | USER | Authorised cancellation before collection. | CANCELLED | CLINICIAN or SUPERVISOR | Reason and cancellation authority are present. | Item is terminal; no collection or result release follows. | LAB_ITEM_CANCELLED with reason. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| READY_FOR_COLLECTION | USER | Refer the test to an external laboratory under the P2 path. | REFERRED_OUT | LAB_TECH with lab.refer_out | P2 is enabled and referral reason/record is present. | Referral remains non-terminal and is included in ageing/return tracking. | LAB_REFERRED_OUT with reason and referral reference. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| READY_FOR_COLLECTION | SYSTEM | Reverse payment before collection for a gated item. | AWAITING_PAYMENT | SYSTEM under PAY-012 | No SAMPLE_COLLECTED or specimen custody exists; the affected item is still pre-collection. | Item is non-actionable again; any patient-facing LAB QueueEntry is not created or is handled by the narrow queue reversal rule. | PAYMENT_REVERSED and laboratory re-gate reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| SAMPLE_COLLECTED | USER | Enter the laboratory values for the collected specimen. | RESULT_ENTERED | LAB_TECH | Specimen custody exists and the entry is attributable to the item. | Values exist but remain invisible to clinicians until verification/release. | LAB_RESULT_ENTERED with actor and specimen reference. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| SAMPLE_COLLECTED | USER | Reject an unusable specimen. | SAMPLE_REJECTED | LAB_TECH | Mandatory rejection reason; clinician notification applies. | Item remains recoverable; recollection is required or cancellation may follow; it does not satisfy all-blocking readiness. | LAB_SAMPLE_REJECTED with reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| SAMPLE_COLLECTED | USER | Cancel after collection under the stronger supplied authority. | CANCELLED | SUPERVISOR | Supervisor authority, mandatory reason, and applicable financial consequence. | Processing stops for this item; specimen/history and financial consequences remain attributable. | LAB_ITEM_CANCELLED with supervisor reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| SAMPLE_REJECTED | USER | Recollect the rejected specimen. | READY_FOR_COLLECTION | LAB_TECH | Recollection is authorised and the original item remains identified. | Original order and history are retained; no automatic new charge or order is created. | LAB_RECOLLECTION with rejection reference. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| SAMPLE_REJECTED | USER | Cancel the rejected test. | CANCELLED | CLINICIAN or SUPERVISOR | Authorised cancellation and reason. | Item becomes terminal and counts toward the all-blocking rule. | LAB_ITEM_CANCELLED with reason. | SINGLE WINNER. |
| RESULT_ENTERED | USER | Verify the entered result. | VERIFIED | LAB_VERIFIER | Required verification and applicable quality checks are satisfied. | Values remain unreleased to clinicians. | LAB_RESULT_VERIFIED with verifier. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| RESULT_ENTERED | USER | Reject the entered result for correction or re-entry. | SAMPLE_COLLECTED | LAB_VERIFIER | Rejection reason and correction path are recorded; specimen remains available where applicable. | Unreleased values are not exposed; the item returns to the collection/result path without losing history. | LAB_RESULT_REJECTED with reason. | EXPLICIT RECONCILIATION. |
| VERIFIED | USER | Release the verified result, or use the authorised combined verify-and-release action. | RELEASED | LAB_VERIFIER under lab.result.verify, or the explicitly configured LAB_TECH path under LAB-016 | Verification and release authority are satisfied. | Result becomes clinician-visible/printable; release may signal readiness only under the all-blocking rule. | LAB_RESULT_RELEASED with verifier and time. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| REFERRED_OUT | USER | Enter a returned external/text result into the normal verification path. | RESULT_ENTERED | LAB_TECH with the authorised result-entry capability | Referral return is identified and the returned value is attributable. | Result remains unreleased until VERIFIED and RELEASED; no direct release is allowed. | LAB_RESULT_ENTERED with referral reference. | SINGLE WINNER / EXPLICIT RECONCILIATION. |

Derived LabOrder presentation/status (LAB-006): these are aggregate
presentations derived from the item states, not additional persisted states or
an independent machine.

| Derived presentation | Required item truth |
| --- | --- |
| CANCELLED | All items are CANCELLED. |
| COMPLETED | All items are terminal and at least one item is RELEASED. |
| PARTIALLY_RELEASED | At least one item is RELEASED and at least one item is non-terminal. |
| PENDING / ACTIVE PRESENTATION | No item is RELEASED and at least one item is non-terminal. |

Every per-item state remains visible; an aggregate must not conceal mixed
truth. A single released item never by itself makes an encounter
RESULTS_READY.

Invalid transitions and canonical errors: SAMPLE_COLLECTED → AWAITING_PAYMENT
is forbidden; payment reversal after custody restores financial balance only.
SAMPLE_REJECTED is not terminal. REFERRED_OUT cannot move directly to
RELEASED. RELEASED is not destructively edited; LAB-017 creates the permitted
version/amendment path. REQUESTED, RESULT_RELEASED, and IN_PROGRESS are not
canonical V1 states. Invalid guards use INVALID_STATE,
PREREQUISITE_MISSING, PERMISSION_DENIED, VERSION_CONFLICT, or ALREADY_EXISTS
as applicable.

Trust mapping: TI-01 / RG-01 (scope), TI-02 / RG-02 (server authority),
TI-04 / RG-04 (released-result integrity), TI-08 / RG-08 (financial
reversal truth), TI-09 / RG-09 (single item outcome), TI-10 / RG-10
(duplicate and retry safety), TI-11 / RG-11 (stale result state),
TI-12 / RG-12 (sensitive payload minimisation), TI-13 / RG-13 (audit
reconstruction), and TI-15 / RG-15 (authoritative high-impact finalisation).

Source authority: K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §22.5;
LAB-005, LAB-006, LAB-008, LAB-009, LAB-015, LAB-016, LAB-017, LAB-018, LAB-022,
LAB-023; PAY-012; and the applicable supplied laboratory, encounter, queue,
and payment story contracts.

### SM-06 — Prescription

| Field | Definition |
| --- | --- |
| Purpose | Represents clinician-authored medication intent and its attributable pharmacy outcome for a Visit. |
| States | DRAFT, ACTIVE, DISPENSED, PARTIALLY_DISPENSED, PARTIALLY_DISPENSED_CLOSED, NOT_DISPENSED, CANCELLED. |
| Initial state | DRAFT while the Encounter is being composed. A draft is not visible as actionable pharmacy work. |
| Terminal states | DISPENSED, PARTIALLY_DISPENSED_CLOSED, NOT_DISPENSED, and CANCELLED. PARTIALLY_DISPENSED remains open while eligible pharmacy work exists. |
| Reversibility | Prescription content becomes immutable when ACTIVE. Terminal outcomes are retained; a later correction uses the supplied cancellation, amendment, or compensating record and never silently rewrites the original. |
| Global constraints | One ordinary draft belongs to one Encounter. Signing activates only internally dispensable items when the Pharmacy module is enabled. External-only items or a disabled Pharmacy module terminalise at signing as NOT_DISPENSED with the supplied reason. Controlled/Class A medicines have no baseline V1 prescription or dispensing path. A visit cannot close while an active pharmacy obligation or provisional handover remains. |
| Trigger types used | USER / SYSTEM. No approved EXTERNAL trigger is required by this machine. |

| From | Trigger type | Trigger / action | To | Actor / capability | Preconditions | Side effects | Audit / reason | Concurrency behaviour |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | USER | Compose or save medication intent in the open Encounter. | DRAFT | CLINICIAN / MIDWIFE with the applicable prescribing capability | Encounter is available and the actor is within prescribing scope; required medicine and quantity information is recorded. | Draft remains attributable to the Encounter and is not sent to pharmacy as actionable work. | PRESCRIPTION_DRAFT_SAVED with actor and Encounter reference. | IDEMPOTENT / SAME OUTCOME; a retry does not create a second draft. |
| DRAFT | USER / SYSTEM | Sign the Encounter with at least one internally dispensable item and an enabled Pharmacy module. | ACTIVE | CLINICIAN / MIDWIFE sign action followed by SYSTEM | Prescription content is complete, within scope, and the Encounter sign is valid. | Prescriber snapshot and immutable prescription content are recorded; eligible pharmacy work becomes visible without creating a second prescription. | PRESCRIPTION_ACTIVATED with sign reference. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| DRAFT | SYSTEM | Sign the Encounter when every item is external-only or the Pharmacy module is disabled. | NOT_DISPENSED | SYSTEM under the signing path | Structured reason is EXTERNAL_SUPPLY or PHARMACY_DISABLED. | Prescription remains printable or referable as applicable; no pharmacy queue, dispense, stock, or medicine charge is created. | PRESCRIPTION_NOT_DISPENSED with reason. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| DRAFT | SYSTEM | Void the Encounter before activation. | CANCELLED | SYSTEM under the authorised Encounter void path | Encounter void is valid and the prescription has not become ACTIVE. | Draft is retained as cancelled history and cannot enter pharmacy work. | PRESCRIPTION_CANCELLED with the Encounter-void reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| ACTIVE | USER | Dispense all prescribed items through the authorised pharmacy path. | DISPENSED | PHARMACIST with dispense capability | Payment gate is clear where applicable, eligible stock is available, and quantities remain within the prescription. | The related Dispense reaches handover; all prescribed items are recorded as dispensed. | PRESCRIPTION_DISPENSED with pharmacist and dispense reference. | SINGLE WINNER; a repeated confirmation returns the committed outcome. |
| ACTIVE | USER | Dispense some items while other prescribed items remain unresolved. | PARTIALLY_DISPENSED | PHARMACIST | At least one item is dispensed and undispensed items remain attributable. | Dispensed items are immutable; remaining work remains visible and cannot be mistaken for completion. | PRESCRIPTION_PARTIALLY_DISPENSED with item references. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| ACTIVE | USER | Record that all items will not be dispensed. | NOT_DISPENSED | PHARMACIST with the supplied not-dispensed capability | Each item has an attributable reason; no item is falsely represented as handed over. | Pharmacy work ends for the prescription and reasons remain visible to the clinical workflow. | PRESCRIPTION_NOT_DISPENSED with item reasons. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| ACTIVE | USER | Cancel or discontinue the prescription before any prohibited item is changed. | CANCELLED | Prescriber or SUPERVISOR with the supplied cancellation authority | Mandatory reason; if a dispense race has already won, cancellation is refused for that item. | Cancellation is retained and does not delete prior history. | PRESCRIPTION_CANCELLED with actor and reason. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| PARTIALLY_DISPENSED | USER | Complete the remaining eligible items. | DISPENSED | PHARMACIST | Remaining quantities and stock are eligible and the payment gate is clear. | The prescription reaches the fully dispensed outcome without duplicating prior items. | PRESCRIPTION_DISPENSED with remaining-item references. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| PARTIALLY_DISPENSED | SYSTEM | Close the Visit while no active pharmacy work or provisional handover remains. | PARTIALLY_DISPENSED_CLOSED | SYSTEM / authorised closure path | REC-012 closure conditions are satisfied; outstanding quantities remain explicitly undispensed. | Visit closes without inventing a dispense; undispensed quantities remain historically visible. | PRESCRIPTION_PARTIALLY_DISPENSED_CLOSED with closure reference. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| PARTIALLY_DISPENSED | USER | Cancel only the undispensed remainder. | CANCELLED | Prescriber or SUPERVISOR | Dispensed items remain immutable; mandatory reason covers only the undispensed remainder. | Prior handovers remain valid and the cancellation is attributable. | PRESCRIPTION_CANCELLED with remainder reference. | SINGLE WINNER / STALE CONFLICT DETECTED. |

Invalid transitions and canonical errors: ACTIVE content is not edited by an
ordinary workflow; DISPENSED, PARTIALLY_DISPENSED_CLOSED, NOT_DISPENSED, and
CANCELLED do not reactivate. A controlled/Class A request uses
UNSUPPORTED_OPERATION; a missing scope or required prescription field uses
PERMISSION_DENIED or PREREQUISITE_MISSING; a dispense/cancel race uses
VERSION_CONFLICT or ALREADY_COMPLETED. The external-only and
Pharmacy-disabled paths use NOT_DISPENSED, not a new state.

Trust mapping: TI-02 / RG-02 (server authority), TI-03 / RG-03 (retained
clinical history), TI-05 / RG-05 (medicine safety), TI-06 / RG-06
(controlled/Class A refusal), TI-07 / RG-07 (stock conservation), TI-08 /
RG-08 (financial final-record integrity), TI-09 / RG-09 (single outcome),
TI-10 / RG-10 (duplicate safety), TI-11 / RG-11 (stale state), TI-13 / RG-13
(audit reconstruction), and TI-15 / RG-15 (authoritative finalisation).

Source authority: K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §22.6;
RX-001, RX-002, RX-003, RX-005, RX-009; ENC-017, ENC-019; DSP-005,
DSP-009; REC-012; PAY-012; and the applicable supplied prescribing,
dispensing, encounter, visit, stock, and payment story contracts.

### SM-07 — Dispense

| Field | Definition |
| --- | --- |
| Purpose | Represents one pharmacy handover decision and its attributable stock and correction outcome. |
| States | AWAITING_PAYMENT, CANCELLED, DISPENSED, REVERSED. CANCELLED is pre-handover only. |
| Initial state | AWAITING_PAYMENT for a stable provisional dispense, including a non-gated provisional basket until its handover is confirmed. |
| Terminal states | CANCELLED, DISPENSED, and REVERSED. DISPENSED is reversible only through the explicit audited return path. |
| Reversibility | A cancelled provisional dispense cannot revive. A dispensed handover may be corrected only through the supplied physical-return and reversal path; neither path edits or deletes the original. While OD-PH5 is BLOCKED, every physical return uses the safe non-resale outcome: the same batch identity is preserved but the returned quantity lands only in quarantine/non-usable stock and cannot increase usable availability. |
| Global constraints | No stock movement or physical handover exists for AWAITING_PAYMENT or CANCELLED. The same stable provisional dispense is used after payment release; a returning patient needs a new provisional dispense after cancellation. Expiry and eligibility are checked at confirmation, and controlled/Class A medicines remain unsupported in baseline V1. Return-to-resale is unavailable while OD-PH5 remains BLOCKED; no role or configuration may silently treat returned medicine as usable stock. |
| Trigger types used | USER / SYSTEM. No approved EXTERNAL trigger is required by this machine. |

| From | Trigger type | Trigger / action | To | Actor / capability | Preconditions | Side effects | Audit / reason | Concurrency behaviour |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | SYSTEM | Create a stable provisional basket and dispense record. | AWAITING_PAYMENT | SYSTEM under the pharmacy workflow | Dispense lines, prescribed quantities, eligible batch choices, and invoice-line source identities are present; no stock has moved. | A payment or other required gate is visible; pharmacy work is attributable to the prescription. | DISPENSE_CREATED with prescription and source references. | SINGLE WINNER; retry returns the same provisional dispense. |
| AWAITING_PAYMENT | USER / SYSTEM | Confirm an authorised handover after payment, waiver, or valid non-gated release. | DISPENSED | PHARMACIST with dispense.perform and SYSTEM | Payment gate is clear, quantities are eligible, usable stock exists, and expiry is acceptable at confirmation. | Physical handover is recorded and the corresponding stock outcome occurs once; the prescription receives the matching outcome. | DISPENSE_CONFIRMED with actor, time, and reason. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| AWAITING_PAYMENT | USER | Abandon or cancel the provisional dispense before handover. | CANCELLED | PHARMACIST through the supplied abandonment path | No physical handover and no stock OUT outcome; mandatory reason is one of the supplied abandonment reasons. | No stock movement; the immutable cancelled record remains visible and cannot be revived. | DISPENSE_CANCELLED with reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| AWAITING_PAYMENT | SYSTEM | Re-evaluate a reversed undelivered payment before handover. | AWAITING_PAYMENT | SYSTEM under PAY-012 | The dispense is still provisional and no handover occurred. | Gate remains unresolved; no stock or handover is inferred from the reversal. | PAYMENT_REVERSED and DISPENSE_PAYMENT_PENDING. | IDEMPOTENT / SAME OUTCOME. |
| DISPENSED | USER | Correct a physical return through the authorised reversal path. | REVERSED | PHARMACIST plus SUPERVISOR approval | Medicines are physically returned, the reason is recorded, and the supplied financial path is available. | Compensating stock IN preserves the original batch identity but lands only in quarantine/non-usable stock while OD-PH5 is BLOCKED; usable availability does not increase. The financial correction is attributable and the original handover remains preserved. | DISPENSE_REVERSED with return evidence, destination, and reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |

Invalid transitions and canonical errors: CANCELLED → DISPENSED and
REVERSED → DISPENSED are forbidden; a missing payment uses PAYMENT_REQUIRED;
expired or unsupported medicine uses EXPIRED_BATCH or
UNSUPPORTED_OPERATION; unavailable stock uses INSUFFICIENT_STOCK or
OUT_OF_STOCK; a competing confirmation uses ALREADY_EXISTS,
ALREADY_COMPLETED, or VERSION_CONFLICT. Confirmation never silently retries a
physical handover after an unknown or failed result.

Trust mapping: TI-05 / RG-05 (expired medicine prohibition), TI-06 / RG-06
(controlled/Class A refusal), TI-07 / RG-07 (stock-ledger conservation),
TI-08 / RG-08 (financial correction), TI-09 / RG-09 (single handover),
TI-10 / RG-10 (duplicate/retry safety), TI-11 / RG-11 (stale state), TI-13 /
RG-13 (audit), and TI-15 / RG-15 (authoritative finalisation).

Source authority: K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §22.7;
DSP-005, DSP-007, DSP-008, DSP-009, DSP-016; INV-012; PAY-012; and the
applicable supplied pharmacy, stock, invoice, and payment story contracts.

### SM-08 — Invoice

SM-08 governs Visit-linked Invoices and an explicitly authorised standalone
Invoice only where a supplied no-Visit story permits it, currently
BIL-002-AC02 retail sale. A LAB_ONLY Visit always uses its Visit-linked
Invoice; no standalone Invoice is created for that path.

| Field | Definition |
| --- | --- |
| Purpose | Represents the chargeable lines, allocation state, and attributable financial outcome for a Visit-linked Invoice; it also governs an explicitly authorised standalone Invoice only where a supplied no-Visit story permits it, currently BIL-002-AC02 retail sale. |
| States | DRAFT, ISSUED, PARTIALLY_PAID, PAID, VOIDED. OUTSTANDING is not a state. |
| Initial state | DRAFT is the canonical pre-issue state while an Invoice is initially constructed; a successful ordinary chargeable OPD check-in issues it as part of the check-in outcome. An already ISSUED Invoice repriced through REC-003 remains ISSUED as one atomic same-state product transition; any temporary internal repricing computation is not an authoritative or externally observable DRAFT state. TRI-013 emergency initiation creates no Invoice and guesses no payer/price; its later authorised financial completion constructs and issues exactly one Visit-linked Invoice for the existing emergency Visit. |
| Terminal states | VOIDED is terminal. PAID remains PAID after a valid CreditNote when effective applied value exceeds the post-credit amount due (the excess is explicit REFUNDABLE CREDIT); a valid full Payment reversal recomputes each affected Invoice to ISSUED, PARTIALLY_PAID, or PAID from current effective allocations; a legitimate new line may return it to PARTIALLY_PAID. |
| Reversibility | An unpaid invoice may follow the supplied void path. An Invoice with any effective applied payment is not voided; a CreditNote, full Payment reversal, bounded Refund, or new attributable line path is used instead. Reversing a Payment recomputes every affected Invoice from CURRENT EFFECTIVE APPLIED VALUE under the reversal-driven outcomes below. REC-005 stale abandonment and REC-009 LWBS may auto-void only their supplied unpaid Invoice branch: a PARTIALLY_PAID Invoice refuses the abandonment/LWBS completion atomically with PREREQUISITE_MISSING until an authorised existing financial correction leaves the Invoice in a fully specified unpaid or PAID branch; the retry then follows that story's exact branch. The refused attempt changes no Visit, QueueEntry, Invoice, InvoiceLine, Payment, PaymentAllocation, receipt, RefundRequest, CreditNote, or Refund state. |
| Amount definitions | GROSS INVOICE TOTAL is the sum of non-voided InvoiceLines and is not rewritten by a CreditNote. CURRENT AUTHORITATIVE AMOUNT DUE is that gross total adjusted by currently valid authorised financial adjustments that affect amount due, including applicable CreditNotes and already-defined discount/waiver outcomes. CreditNotes are displayed separately from original lines so history remains reconstructable. |
| Effective applied value | CURRENT EFFECTIVE APPLIED VALUE reflects confirmed valid PaymentAllocations, removes allocations belonging to fully REVERSED Payments, and subtracts completed attributable Refund amounts for the affected Invoice only; unrelated allocation/refund effects do not apply. |
| Refundable credit | REFUNDABLE CREDIT is the positive amount by which retained CURRENT EFFECTIVE APPLIED VALUE exceeds CURRENT AUTHORITATIVE AMOUNT DUE after valid CreditNotes and other authorised financial adjustments. It is visible, attributable, tied to the relevant Invoice/CreditNote, and remains a pending refund obligation rather than general-purpose reusable patient credit unless an explicit facility-credit policy authorises that use. |
| CreditNote / Refund | A CreditNote is an attributable compensating record against an affected Invoice and original paid InvoiceLine/source, with amount, mandatory reason, actor/authority, and authoritative time; it cannot exceed the remaining creditable value and cannot double-credit; creation and retry use the existing duplicate/single-winner guarantees. A bounded Refund against resulting refundable credit is a separate compensating money-out record, does not edit the original Payment, and does not change unrelated allocations, Invoices, or service gates. If no explicitly authorised facility-credit policy exists, refundable credit remains a visible pending refund obligation and is not general-purpose reusable patient credit. |
| State after CreditNote | When a CreditNote changes CURRENT AUTHORITATIVE AMOUNT DUE, recompute the affected Invoice from that amount and CURRENT EFFECTIVE APPLIED VALUE: positive due with zero applied → ISSUED; positive due with applied above zero but below due → PARTIALLY_PAID; fully covered due → PAID. If effective applied value exceeds post-credit due, remain PAID and show the difference as REFUNDABLE CREDIT. CreditNote creation never reaches VOIDED. |
| Global constraints | A successful ordinary chargeable OPD check-in creates exactly one consultation line and one issued Invoice for that Visit. TRI-013 emergency initiation delays, but never waives or guesses, this financial outcome: authorised completion of the same emergency Visit creates exactly one consultation line and one Visit-linked Invoice in ISSUED, and merge/sign/retry cannot create another. Payment allocations never exceed the authoritative balance. Adding a legitimate post-payment line makes the new balance explicit; it is not a silent mutation. A full Payment reversal affects all of that Payment's allocations and every affected Invoice; each affected Invoice is recomputed independently, and the complete financial/gate result commits as one consistent product outcome. |
| Trigger types used | USER / SYSTEM. No approved EXTERNAL trigger is required by this machine. |

| From | Trigger type | Trigger / action | To | Actor / capability | Preconditions | Side effects | Audit / reason | Concurrency behaviour |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | SYSTEM | Initially construct an Invoice before first issue. | DRAFT | SYSTEM under the supplied pricing path | Payer and price context are valid; no payment has been falsely claimed. | Draft lines and their source identities remain attributable. | INVOICE_DRAFTED with pricing context. | IDEMPOTENT / SAME OUTCOME. |
| DRAFT | SYSTEM | Complete a successful chargeable OPD check-in. | ISSUED | SYSTEM | Visit creation, destination, and required price are valid. | Exactly one consultation line and one invoice are issued; the same check-in retry cannot add another line. | INVOICE_ISSUED and CONSULTATION_LINE_CREATED. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| ISSUED | USER | Apply REC-003 eligible payer / price-list repricing. | ISSUED | Actor authorised by REC-003 with `visit.update_payer` | The Visit remains on the REC-003-supported `OPEN` path; the Invoice is ISSUED and wholly unpaid / unpartially-paid; no `CONFIRMED` payment or effective PaymentAllocation exists; every affected line remains repricing-eligible; current authority, pricing, stale-state, and request-identity checks succeed. | As one consistent product outcome, change the payer / price-list binding, every affected eligible InvoiceLine price snapshot, and authoritative totals; retain the same Invoice ID and facility Invoice number. Failure commits none of those changes and leaves the prior ISSUED Invoice, bindings, snapshots, and totals authoritative; no mixed-price outcome may exist. | `INVOICE_REPRICED` with actor, authoritative time, applicable reason/context, and attributable old/new payer, price-list, line-price, and total values. | SINGLE WINNER / VERSION_CONFLICT on a stale competing attempt; the loser cannot overwrite the winner. IDEMPOTENT SAME OUTCOME for the same legitimate retry; materially different request-identity reuse is refused under GSC-7. |
| — / DRAFT | USER / SYSTEM | Complete authorised TRI-013 emergency financial setup for the existing emergency Visit. | ISSUED | RECEPTIONIST or other actor already authorised for ordinary payer/price fields, plus SYSTEM | Same emergency Visit; EMERGENCY_FINANCIAL_SETUP_PENDING; authoritative payer and price-list selections supplied; valid consultation price; no existing consultation line or non-terminal Visit-linked Invoice except a matching transient DRAFT from the same request. | Exactly one consultation line and one Visit-linked Invoice are issued for the original emergency Visit; the pending obligation clears; the patient merge, clinician signing, and retry paths reuse this outcome and never create it independently. | EMERGENCY_FINANCIAL_SETUP_COMPLETED, INVOICE_ISSUED, and CONSULTATION_LINE_CREATED with Visit and source references. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME; existing matching outcome is returned, while materially conflicting payer/price input requires explicit reconciliation. |
| DRAFT | SYSTEM | Undo an unpaid erroneous check-in through its supplied correction path. | VOIDED | SYSTEM / RECEPTIONIST through visit correction | No payment or other disqualifying clinical record exists; mandatory reason. | Invoice history remains queryable and no chargeable consultation is left active. | INVOICE_VOIDED with correction reason. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| ISSUED | USER / SYSTEM | Allocate a valid payment that leaves a positive balance. | PARTIALLY_PAID | CASHIER / SYSTEM | Payment is confirmed and allocation is within the current balance. | Allocation and remaining balance are visible; no over-allocation occurs. | INVOICE_PARTIALLY_PAID with payment reference. | SINGLE WINNER / VERSION_CONFLICT on stale balance. |
| ISSUED | USER / SYSTEM | Allocate payment that settles the current lines. | PAID | CASHIER / SYSTEM | Confirmed payment or authorised waiver satisfies the allocation invariant. | Current lines become financially settled and the receipt outcome is attributable. | INVOICE_PAID with payment or waiver reference. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| ISSUED | USER / SYSTEM | Void an unpaid invoice through check-in undo, LWBS, or the supplied correction path. | VOIDED | RECEPTIONIST / SYSTEM | No payment has been allocated; mandatory reason and authority apply. | Invoice and related unpaid line history remain retained. | INVOICE_VOIDED with reason. | SINGLE WINNER / STALE CONFLICT DETECTED. |
| PARTIALLY_PAID | USER / SYSTEM | Allocate payment that settles the remaining current balance. | PAID | CASHIER / SYSTEM | Allocation equals the remaining balance or valid waiver amount. | Receipt and settled balance are recorded. | INVOICE_PAID with final allocation. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |
| PAID | SYSTEM | Add a legitimate new chargeable line after payment. | PARTIALLY_PAID | SYSTEM / authorised billing path | New line is attributable and permitted; prior allocations remain unchanged. | New balance and the new line are explicit; the prior paid outcome remains historical truth. | INVOICE_LINE_ADDED with source and reason. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| ISSUED / PARTIALLY_PAID / PAID | USER / SYSTEM | Reverse a Payment through SM-09 / PAY-008. | ISSUED / PARTIALLY_PAID / PAID | SYSTEM under PAY-008 / PAY-012 | The full Payment is validly reversed; all currently effective PaymentAllocations belonging to it become reversed/ineffective for current-balance purposes; historical allocation records remain attributable and retained; every Invoice touched by those allocations is an affected Invoice. | For EACH affected Invoice, recompute independently its CURRENT AUTHORITATIVE AMOUNT DUE, CURRENT EFFECTIVE APPLIED VALUE, outstanding balance, and SM-08 state: zero effective applied with positive due → ISSUED; applied above zero but below due → PARTIALLY_PAID; due fully covered → PAID. Payment reversal never changes an Invoice to VOIDED. Re-evaluate every applicable undelivered gate associated with every affected allocation/Invoice under PAY-012; all affected financial/gate outcomes are one consistent reversal outcome, and an incomplete set is not represented as completed. | INVOICE_STATE_RECOMPUTED for every affected Invoice and PAYMENT_REVERSED with the original reference. | SINGLE WINNER / EXPLICIT RECONCILIATION. |

Invalid transitions and canonical errors: PAID is not silently edited or
voided, and no OUTSTANDING state is introduced. A valid CreditNote or bounded
Refund never reaches VOIDED and never silently edits original financial
history. Over-allocation uses
BALANCE_CHANGED or VERSION_CONFLICT; an unpaid prerequisite uses
PREREQUISITE_MISSING; a duplicate consultation line uses ALREADY_EXISTS; a
paid-invoice cancellation uses INVALID_STATE and the supplied credit or
reversal path.

Trust mapping: TI-01 / RG-01 (scope), TI-02 / RG-02 (server authority), TI-08
/ RG-08 (financial final-record integrity), TI-09 / RG-09 (single financial
outcome), TI-10 / RG-10 (duplicate safety), TI-11 / RG-11 (stale balance),
TI-13 / RG-13 (audit reconstruction), and TI-15 / RG-15 (authoritative
finalisation).

Source authority: K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §22.8;
REC-001, REC-003, REC-005, REC-009, REC-010; BIL-001, BIL-002, BIL-004,
BIL-005, BIL-009, BIL-010; PAY-002, PAY-005, PAY-008; and the applicable
supplied visit, billing, receipt, and payment story contracts.

### SM-09 — Payment

| Field | Definition |
| --- | --- |
| Purpose | Represents a confirmed Payment and its attributable full-reversal outcome; bounded Refunds are separate records. |
| States | CONFIRMED, REVERSED. |
| Initial state | CONFIRMED when an authorised payment is recorded with its required attribution and allocation. |
| Terminal states | REVERSED. The original CONFIRMED record remains retained even after reversal. |
| Reversibility | A Payment is immutable after confirmation; a full reversal is a separately attributable compensating record and is not an edit to the original. A bounded CreditNote-specific Refund is also separate and does not change the Payment from CONFIRMED. |
| Global constraints | Allocation, receipt, payer, method, shift, and applicable reference remain consistent. A full reversal applies to the Payment as a whole: every currently effective PaymentAllocation belonging to it becomes reversed/ineffective for current-balance purposes, historical allocations remain retained, and every Invoice touched by those allocations is recomputed independently for CURRENT AUTHORITATIVE AMOUNT DUE, CURRENT EFFECTIVE APPLIED VALUE, outstanding balance, and state under SM-08. Every applicable undelivered gate associated with every affected allocation/Invoice is re-evaluated under PAY-012; delivered clinical, laboratory custody, and stock outcomes are not silently undone. A bounded Refund does not re-evaluate unrelated gates or alter unrelated allocations/Invoices. |
| Trigger types used | USER / SYSTEM. No approved EXTERNAL trigger is required by this machine. |

| From | Trigger type | Trigger / action | To | Actor / capability | Preconditions | Side effects | Audit / reason | Concurrency behaviour |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | USER | Record and allocate an authorised payment. | CONFIRMED | CASHIER with payment.record | Required payer, method, amount, allocation, shift, and reference rules are satisfied. | Invoice balance and receipt reflect the confirmed payment; any eligible service gates may be released once. | PAYMENT_CONFIRMED with actor and payment reference. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME; materially different reuse of a key is rejected. |
| CONFIRMED | USER | Reverse a confirmed Payment through the authorised whole-Payment correction path. | REVERSED | SUPERVISOR / FACILITY_ADMIN with payment.reverse | Mandatory reason, authority, and cross-shift accounting requirements are satisfied. | Original Payment remains visible as REVERSED; ALL currently effective allocations belonging to it become reversed/ineffective for current-balance purposes; every affected Invoice is recomputed independently under SM-08; every applicable undelivered gate associated with the affected allocations/Invoices is re-evaluated under PAY-012; historical records remain retained. | PAYMENT_REVERSED with reason, approver, original reference, affected allocation IDs, and affected Invoice IDs. | SINGLE WINNER / EXPLICIT RECONCILIATION. |
| CONFIRMED | SYSTEM | Retry or re-read an already confirmed payment request. | CONFIRMED | SYSTEM | Request represents the same payment identity and materially identical outcome. | No second payment, allocation, receipt, or service release is created. | PAYMENT_REPLAY_RECOGNISED with original reference. | IDEMPOTENT / SAME OUTCOME. |

Invalid transitions and canonical errors: REVERSED cannot be confirmed again;
missing shift, reference, payer, or allocation uses PREREQUISITE_MISSING or
REFERENCE_REQUIRED; stale balance uses BALANCE_CHANGED or VERSION_CONFLICT;
missing authority uses PERMISSION_DENIED. A full Payment reversal is a
whole-Payment correction and cannot target only an arbitrarily selected
primary Invoice. A CreditNote-specific partial/cash Refund is a separate
compensating Refund record: it does not create a PARTIALLY_REVERSED Payment
state, does not mark the original Payment REVERSED, and leaves unrelated
allocations, Invoices, and service gates unchanged. A full reversal and all of
its affected financial/gate outcomes are either authoritative together or the
reversal is not represented as completed; no automatic rollback of delivered
work is implied.

Trust mapping: TI-01 / RG-01 (scope), TI-02 / RG-02 (server authority), TI-07
/ RG-07 (stock correction truth), TI-08 / RG-08 (financial integrity), TI-09
/ RG-09 (single payment outcome), TI-10 / RG-10 (duplicate/retry safety),
TI-11 / RG-11 (stale balance), TI-13 / RG-13 (audit), and TI-15 / RG-15
(authoritative high-impact finalisation).

Source authority: K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §22.9;
PAY-002, PAY-005, PAY-008, PAY-012; BIL-010; DSP-016; LAB-005, LAB-008;
REC-001; and the applicable supplied billing, dispensing, laboratory, and
payment story contracts.

### SM-10 — Appointment (fragment — APT epic not supplied)

| Field | Definition |
| --- | --- |
| Purpose | Records only the supplied appointment-to-attendance fragment; it does not reconstruct the unsupplied APT lifecycle. |
| States | UNSUPPLIED / OPEN / BLOCKED for the full appointment machine. The supplied fragment names NO_SHOW and CHECKED_IN only for the one documented path. |
| Initial state | UNSUPPLIED for the complete appointment lifecycle. |
| Terminal states | NONE supplied for the complete appointment lifecycle. |
| Reversibility | No general appointment reversibility is defined in the supplied material. |
| Global constraints | Do not invent booking, slot, reminder, cancellation, rescheduling, or appointment-permission transitions. The only supplied attendance path is a same-day arrival after NO_SHOW; appointment-to-clinician routing remains the QUE-004 effect. |
| Trigger types used | USER / SYSTEM for the supplied attendance and routing effects only. |

| From | Trigger type | Trigger / action | To | Actor / capability | Preconditions | Side effects | Audit / reason | Concurrency behaviour |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NO_SHOW | USER | Record the patient's later same-day arrival and check in the appointment. | CHECKED_IN | RECEPTIONIST through REC-001 | The appointment was marked NO_SHOW and the patient arrives later on the same service day; the ordinary check-in rules are satisfied. | A same-day check-in is attributable to the appointment and the clinician-routing effect may be applied; no full appointment lifecycle is inferred. | APPOINTMENT_CHECKED_IN_AFTER_NO_SHOW with actor and reason. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |

Invalid transitions and canonical errors: any appointment action not supplied
by the fragment is UNSUPPLIED / BLOCKED and must not be guessed. Use
PREREQUISITE_MISSING or INVALID_STATE for a missing or ineligible same-day
arrival path; use ALREADY_EXISTS for a competing check-in when the supplied
check-in contract applies.

Source authority: K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §22.10;
REC-001 alternative (e), QUE-004, and the explicit note that the APT epic is
not supplied.

### SM-11 — ANC enrolment / contact (fragment)

| Field | Definition |
| --- | --- |
| Purpose | Records the supplied ANC enrolment constraint and maps ANC contacts to the standard clinical, laboratory, and queue machines without inventing an ANC-specific lifecycle. |
| States | ANCEnrolment ACTIVE condition only; full enrolment closure and lifecycle are UNSUPPLIED / OPEN / BLOCKED. ANC contact is Encounter(type=ANC) and therefore uses SM-04; investigations use SM-05 and the ordinary QueueEntry uses SM-01. |
| Initial state | No ANC-specific initial state is supplied. An authorised patient may have one active ANC enrolment under ANC-001. |
| Terminal states | NONE supplied for ANC enrolment. |
| Reversibility | Enrolment closure and reversal are UNSUPPLIED; history changes follow the supplied versioning rules rather than a new ANC state. |
| Global constraints | Exactly one active ANC enrolment exists per patient. ANC contact, queue, laboratory, prescription, payment, and closure behaviour reuse the corresponding standard machines. No automatic ANC protocol, risk classification, interpretation, diagnosis, treatment suggestion, or separate laboratory status is introduced. |
| Trigger types used | USER / SYSTEM only through the standard mapped machines; no independent ANC transition trigger is defined. |

| From | Trigger type | Trigger / action | To | Actor / capability | Preconditions | Side effects | Audit / reason | Concurrency behaviour |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| — | USER | Enrol a pregnant patient under ANC-001 when no active enrolment exists. | ACTIVE condition | MIDWIFE, or scoped CLINICIAN, with ANC enrolment capability | Patient is eligible for the supplied enrolment path and no concurrent active enrolment exists. | ANC number, supplied obstetric information, provider, and enrolment date are attributable; the chart may show the ANC banner. | ANC_ENROLLED with actor and enrolment reference. | SINGLE WINNER; a competing enrolment receives ALREADY_EXISTS and the existing active reference where permitted. |
| ACTIVE condition | USER | Start an ANC contact or order an ANC investigation. | SM-04 / SM-05 standard path | MIDWIFE / CLINICIAN within the supplied ANC scope | An ANC visit is checked in and the standard Encounter or laboratory preconditions are met. | The same ANC Encounter, standard QueueEntry, and standard LabOrderItem rules apply; no ANC-specific machine is created. | ANC_STANDARD_PATH_USED with the mapped record reference. | SINGLE WINNER / IDEMPOTENT SAME OUTCOME. |

Invalid transitions and canonical errors: ANC enrolment closure, a second
active enrolment, or any ANC-specific laboratory or risk state not supplied by
the source is UNSUPPORTED_OPERATION, ALREADY_EXISTS, or BLOCKED as applicable;
the standard Encounter, QueueEntry, LabOrderItem, Prescription, Invoice, and
Payment errors apply to their mapped actions.

Trust mapping: TI-01 / RG-01 (scope), TI-02 / RG-02 (server authority), TI-03
/ RG-03 (clinical-history integrity), TI-04 / RG-04 (released-result
integrity), TI-09 / RG-09 (single outcome), TI-10 / RG-10 (duplicate safety),
TI-11 / RG-11 (stale state), TI-12 / RG-12 (sensitive payload minimisation),
TI-13 / RG-13 (audit), and TI-14 / RG-14 (no unapproved clinical
interpretation).

Source authority: K:/clinicopus/KlinKlik-V1-Canonical-Backlog.md §22.11;
ANC-001, ANC-002, ANC-003, ANC-007; LAB-002, LAB-004, LAB-005, LAB-018,
LAB-023; ENC-002, ENC-016, ENC-018, QUE-006, PAY-012; and the applicable
supplied ANC, encounter, queue, laboratory, and payment story contracts.

### Cross-machine constraints

Rules involving more than one state machine belong here, not only in one
machine's free-text preconditions. Name every relevant machine and state,
define the required product consistency and recovery outcome, and map material
rules to regression gates. The Product Spec defines the required consistency,
single-outcome and product-visible recovery semantics; the Blueprint defines
the technical implementation without changing those outcomes. Projects with
no interacting state machines may mark this table NOT APPLICABLE with a
rationale.

| Constraint ID | Machines / states involved | Canonical rule | Trigger / transition affected | Required consistency / atomicity outcome | Product-visible recovery / compensation requirement | Canonical error family | Regression gate IDs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CMC-01 | SM-02 OPEN/IN_PROGRESS; SM-04 OPEN/AWAITING_RESULTS/RESULTS_READY | Exactly one non-terminal Encounter belongs to a Visit; resuming work uses that same Encounter. | Encounter create, resume, or queue service start. | One authoritative Encounter reference is associated with the Visit; competing creates cannot produce a second record. | Return the existing safe reference/current state and require explicit reconciliation for a stale actor. | ALREADY_EXISTS / VERSION_CONFLICT | TI-09 / RG-09; TI-10 / RG-10; TI-11 / RG-11 |
| CMC-02 | SM-01 IN_SERVICE/ON_HOLD/READY_TO_RESUME; SM-04 OPEN/AWAITING_RESULTS/RESULTS_READY | A parked Encounter and its consultation QueueEntry carry the same return obligation; downstream work may proceed without losing the upstream hold. | Park, dependency resolution, manual resume, or return from a downstream stage. | One Encounter ID and one matching queue outcome remain authoritative; ON_HOLD is not replaced by a second Encounter. | Show the hold reason and return action; allow the same Encounter to resume early or when all dependencies resolve. | INVALID_STATE / VERSION_CONFLICT | TI-09 / RG-09; TI-11 / RG-11; TI-13 / RG-13 |
| CMC-03 | SM-04 AWAITING_RESULTS/RESULTS_READY; SM-05 RELEASED/CANCELLED/SAMPLE_REJECTED and other item states; SM-01 ON_HOLD/READY_TO_RESUME | Encounter readiness and queue readiness occur only when every blocking LabOrderItem is RELEASED or CANCELLED; partial release or SAMPLE_REJECTED never qualifies. | Lab item release, cancellation, rejection, or readiness recomputation. | No RESULTS_READY or READY_TO_RESUME outcome is asserted before the all-blocking condition is true. | Display per-item progress; route SAMPLE_REJECTED to recollection or cancellation and keep remaining blockers visible. | PREREQUISITE_MISSING / INVALID_STATE | TI-04 / RG-04; TI-09 / RG-09; TI-11 / RG-11; TI-13 / RG-13 |
| CMC-04 | SM-01 LAB WAITING/CALLED/IN_SERVICE/COMPLETED; SM-05 READY_FOR_COLLECTION/SAMPLE_COLLECTED/RELEASED | Patient-facing LAB queue completion represents collection or receipt, while LabOrderItem bench processing and result release continue independently. | Collection/receipt completion, result entry, verification, or release. | Result release never completes a patient-facing LAB QueueEntry, and the per-item history remains visible. | Show collection completion separately from pending bench/release work; reconcile a duplicate signal to the current states. | INVALID_STATE / VERSION_CONFLICT | TI-04 / RG-04; TI-09 / RG-09; TI-13 / RG-13 |
| CMC-05 | SM-01 consultation ON_HOLD/COMPLETED; SM-04 OPEN/AWAITING_RESULTS/RESULTS_READY/SIGNED/VOIDED; SM-05 pending item states | ENC-018 is the only pending-results sign path that completes the held consultation QueueEntry with SIGNED_WITH_PENDING_RESULTS. Any ENC-019 Encounter void cannot leave a related non-terminal LabOrderItem actionable. | Explicit clinician or midwife “Sign now” with pending orders; entered-in-error Encounter void. | Encounter signing, signed_with_pending_orders, and queue completion are one consistent product outcome; a later result cannot create readiness. Before any void, each related non-terminal item must already be resolved through LAB-022; released results remain preserved and use their supplied detach/review history. | Keep the signed record immutable; late results use the supplied addendum path without reopening the Visit or Encounter. Refuse void with exact unresolved-lab blockers rather than silently orphaning actionable work. | PREREQUISITE_MISSING / INVALID_STATE | TI-03 / RG-03; TI-04 / RG-04; TI-09 / RG-09; TI-13 / RG-13 |
| CMC-06 | SM-02 OPEN/IN_PROGRESS; SM-01 initial consultation entry; SM-03 DRAFT; SM-08 DRAFT/ISSUED | A successful ordinary chargeable OPD check-in creates exactly one consultation line and one issued Invoice. TRI-013 emergency initiation creates one Visit OPEN and transitions that same Visit to IN_PROGRESS when emergency triage starts, while delaying financial setup; its later authorised financial completion creates the same exact-one charge/Invoice outcome on that original Visit. Triage completion, clinician start, signing, patient merge, and retry never create a second Visit, Visit transition, consultation entry, or consultation charge. | Ordinary check-in, TRI-013 emergency initiation or financial completion, triage completion, clinician service start, invoice issue, patient merge, Encounter signing, or retry. | One Visit reaches IN_PROGRESS once, one consultation QueueEntry remains WAITING until clinician service, and one later consultation line and issued Invoice remain linked and attributable; while TRI-013 setup is pending, the missing financial outcome is explicit, care stays actionable, and Visit closure is blocked. | Return/reuse the existing Visit, TriageRecord, consultation QueueEntry, consultation line, and Invoice on later stages, retry, or merge; materially conflicting payer/price input requires explicit reconciliation without adding a line or changing Visit state. | ALREADY_EXISTS / PREREQUISITE_MISSING / VERSION_CONFLICT | TI-08 / RG-08; TI-09 / RG-09; TI-10 / RG-10; TI-13 / RG-13 |
| CMC-07 | SM-01 WAITING_PAYMENT/WAITING/IN_SERVICE; SM-02 OPEN/IN_PROGRESS; SM-03 DRAFT; SM-08 ISSUED; SM-09 CONFIRMED/REVERSED | Under PAY_BEFORE_TRIAGE, an ordinary initial queue entry is WAITING_PAYMENT; qualifying payment releases the same entry to WAITING and its first QueueEntry-backed service start moves the ordinary Visit OPEN → IN_PROGRESS. The only supplied care-first exception is TRI-013 EMERGENCY_CARE_FIRST: emergency triage itself moves the Visit OPEN → IN_PROGRESS without a triage QueueEntry, while its consultation entry remains WAITING and immediately actionable with unresolved registration/financial setup visibly pending. This exception grants no ordinary payment-gate bypass. | Ordinary check-in, TRI-013 emergency initiation, payment confirmation, payment reversal, or service start. | Ordinary unpaid service cannot become actionable; one payment release produces one WAITING outcome for the same ordinary Visit and department. TRI-013 may proceed before payment/price exists, but retains its pending obligation; later triage completion reuses the consultation QueueEntry, and clinician start moves that entry to IN_SERVICE while the Visit remains IN_PROGRESS with no repeated Visit transition. | Show the payment requirement and next action; an undelivered ordinary reversal re-gates the existing entry and requires re-release. Keep TRI-013 pending setup visible until authoritative completion; never generalise it to another Visit or create a triage QueueEntry for this exception. | PREREQUISITE_MISSING / INVALID_STATE | TI-08 / RG-08; TI-09 / RG-09; TI-10 / RG-10; TI-13 / RG-13 |
| CMC-08 | SM-01 cashier WAITING and LAB absent/WAITING; SM-05 AWAITING_PAYMENT/READY_FOR_COLLECTION; SM-08 ISSUED; SM-09 CONFIRMED/REVERSED | A laboratory PAY_BEFORE item remains non-actionable with no patient-facing LAB QueueEntry until release; for LAB_ONLY, request capture precedes this gate and is not the LAB collection queue; release then creates the LAB entry in WAITING. | Lab ordering, qualifying payment/waiver, gate release, or undelivered payment reversal. | Lab item gate, cashier outcome, and patient-facing LAB queue presence agree; collection cannot occur before release. | Keep the cashier action visible; reversal before custody leaves the item re-gated and requires a new release, never a silent collection. | PREREQUISITE_MISSING / INVALID_STATE | TI-08 / RG-08; TI-09 / RG-09; TI-10 / RG-10; TI-13 / RG-13 |
| CMC-09 | SM-01 pharmacy ON_HOLD/READY_TO_RESUME; SM-06 ACTIVE/PARTIALLY_DISPENSED; SM-07 AWAITING_PAYMENT/DISPENSED; SM-08 ISSUED/PARTIALLY_PAID/PAID; SM-09 CONFIRMED/REVERSED | A medicine PAY_BEFORE hold uses one provisional Dispense; payment release resumes that same handover path, and no stock or handover exists before release. | Prescription activation, pharmacy hold, qualifying payment, resume, dispense, or undelivered reversal. | Prescription, pharmacy return obligation, Dispense, invoice, and payment have one matching outcome; no second provisional handover is created. | Show the payment hold; pre-handover abandonment is terminal and a returning patient needs a new provisional dispense; reversal reopens only the unpaid gate. | PREREQUISITE_MISSING / INVALID_STATE | TI-07 / RG-07; TI-08 / RG-08; TI-09 / RG-09; TI-10 / RG-10; TI-13 / RG-13 |
| CMC-10 | SM-01 service entries; SM-04 clinical Encounter; SM-05 pre-collection item states; SM-07 AWAITING_PAYMENT/DISPENSED; SM-09 CONFIRMED/REVERSED | Payment reversal affects undelivered work only. Delivered clinical work, specimen custody, released results, and stock handover stand; the narrow pre-collection LAB path may re-gate or cancel as specified. | Payment reversal and dependent-gate re-evaluation. | Financial truth is restored without asserting an incompatible backward clinical or custody state. | Re-gate or cancel the eligible pre-service work with a visible reason; report delivered work as standing and require explicit reconciliation. | PREREQUISITE_MISSING / INVALID_STATE | TI-07 / RG-07; TI-08 / RG-08; TI-09 / RG-09; TI-11 / RG-11; TI-13 / RG-13 |
| CMC-11 | SM-04 OPEN/SIGNED/VOIDED; SM-06 DRAFT/ACTIVE/PARTIALLY_DISPENSED/NOT_DISPENSED/CANCELLED; SM-01 pharmacy entry | Signing activates internally dispensable prescriptions only; external-only or Pharmacy-disabled prescriptions become NOT_DISPENSED, and controlled/Class A work remains unsupported. Before the exceptional ENC-019 signed void, every related still-actionable unhanded prescription or undispensed remainder must already be non-actionable through RX-009 and the corresponding pharmacy work must be resolved through DSP-005 where applicable. | Encounter signing and prescription fan-out; exceptional signed-Encounter void. | No pharmacy work exists before a valid signed activation, and exactly one supported prescription outcome is recorded. A signed void cannot leave unhanded related work actionable; already handed-over items and stock history remain and use their separate DSP-016 correction path if needed. | Provide the supplied external/non-KlinKlik path or printable outcome; no role or gate change can enable controlled/Class A V1 work. Refuse signed void with exact unresolved prescription/pharmacy blockers. | INVALID_STATE / UNSUPPORTED_OPERATION / PREREQUISITE_MISSING | TI-02 / RG-02; TI-06 / RG-06; TI-09 / RG-09; TI-13 / RG-13 |
| CMC-12 | SM-06 ACTIVE/PARTIALLY_DISPENSED/DISPENSED; SM-07 AWAITING_PAYMENT/CANCELLED/DISPENSED/REVERSED | Prescription item outcomes, dispense handover, and stock movement agree exactly once; a cancelled provisional dispense has no stock movement. While OD-PH5 is BLOCKED, a physical return preserves its batch identity but returns only to quarantine/non-usable stock and cannot increase usable availability. | Dispense confirmation, partial dispense, abandonment, or authorised return. | One handover produces the matching prescription and stock outcome; retries cannot create duplicate dispense or movement. A return produces one compensating non-usable stock outcome, never a silent return-to-resale. | Use partial/not-dispensed outcomes when appropriate; use only the audited return path for correction, preserve the original handover, and keep returned quantity quarantined/non-usable until OD-PH5 is authoritatively resolved through change control. | INVALID_STATE / ALREADY_EXISTS / PREREQUISITE_MISSING | TI-05 / RG-05; TI-07 / RG-07; TI-09 / RG-09; TI-10 / RG-10; TI-13 / RG-13 |
| CMC-13 | SM-07 AWAITING_PAYMENT/DISPENSED; applicable medicine stock and prescription eligibility | Expired medicine is refused at confirmation regardless of role; no expired handover or usable stock outcome is allowed. | Stock selection, dispense confirmation, receipt, or retry. | No DISPENSED outcome or stock deduction is recorded for an expired batch. | Select an eligible batch or record the approved not-dispensed outcome; no override path exists. | INVALID_STATE / UNSUPPORTED_OPERATION | TI-05 / RG-05; TI-09 / RG-09; TI-13 / RG-13 |
| CMC-14 | SM-08 ISSUED/PARTIALLY_PAID/PAID; SM-09 CONFIRMED/REVERSED | Invoice allocations equal recorded payment and current lines; a legitimate new post-payment line makes the Invoice PARTIALLY_PAID; a CreditNote changes CURRENT AUTHORITATIVE AMOUNT DUE without editing original lines; a full Payment reversal affects ALL allocations of that Payment and EVERY affected Invoice; a bounded Refund affects only its CreditNote/Invoice context; OUTSTANDING is not a state. LAB_ONLY always has a Visit and its laboratory charges use that Visit-linked Invoice; the only supplied no-Visit standalone-Invoice path is BIL-002-AC02 retail sale. REC-005 and REC-009 never void an Invoice with effective applied payment and never treat PARTIALLY_PAID as either their unpaid or PAID branch. | Payment allocation, full reversal, CreditNote adjustment, bounded Refund, balance refresh, new line addition, or an abandonment/LWBS financial-state check. | No over-allocation, double-credit, over-refund, or silent balance mutation; each affected Invoice is independently reconciled from current due and effective applied value; unrelated allocations, Invoices, and gates remain unchanged. A PARTIALLY_PAID abandonment/LWBS attempt is refused atomically until an authorised existing financial path leaves the Invoice in one of that story's fully specified branches. | Refresh and require explicit reconciliation on a stale balance; use CreditNote, full reversal, or bounded Refund according to the correction scope rather than voiding or editing paid history. Do not invent a standalone LAB_ONLY Invoice or an automatic debt, waiver, refund, reversal, or credit outcome for PARTIALLY_PAID abandonment. | VERSION_CONFLICT / PREREQUISITE_MISSING | TI-08 / RG-08; TI-09 / RG-09; TI-10 / RG-10; TI-11 / RG-11; TI-13 / RG-13 |
| CMC-15 | SM-01 terminal/held entries; SM-02 OPEN/IN_PROGRESS/CLOSED; SM-03 DRAFT/COMPLETED; SM-04 OPEN/AWAITING_RESULTS/RESULTS_READY/SIGNED/VOIDED; SM-05 item states; SM-06/SM-07 pharmacy states; SM-08/SM-09 financial states | Visit closure requires the supplied checklist: no unresolved Encounter, required queue and laboratory outcomes are handled, prescriptions are terminal or use the defined PARTIALLY_DISPENSED_CLOSED outcome, no provisional Dispense remains active, and financial conditions are settled or use an explicitly supplied waiver/debt path. No general Visit force-close exists. REC-005 stale abandonment is a narrow exception only to the ordinary requirement that its stale queues and eligible unpaid Invoice already be terminal/settled: it performs that supplied cleanup as part of one abandonment outcome, but still must pass REC-012 unresolved-work safety guards and cannot bypass an unresolved Encounter, active laboratory or prescription/pharmacy work, another protected non-financial blocker, or the PARTIALLY_PAID refusal in CMC-14. The same-day supervisor-approved second-Visit override is a separate supplied path. | Ordinary Visit close; ENC-018 CLOSED(PENDING_RESULTS); PARTIALLY_DISPENSED_CLOSED; BIL-014 close-with-debt; BIL-009 waiver; REC-005 stale abandonment; REC-009 LWBS; or another explicitly supplied closure path with complete cross-machine semantics. | One closure reason is recorded with all linked history preserved; signed-with-pending is the only permitted pending-results closure branch, and each other alternative changes only the states its own supplied rule names. REC-005 may terminalise only its supplied stale queue entries and eligible unpaid Invoice as part of its atomic closure. An unclassified blocker remains a hard block. | Show every blocker and its required owner/action; do not silently discard or terminalise a held stage, active queue/lab/pharmacy/Dispense obligation, partially paid or otherwise unresolved balance, or unresolved clinical record. | INVALID_STATE / PREREQUISITE_MISSING | TI-03 / RG-03; TI-04 / RG-04; TI-07 / RG-07; TI-08 / RG-08; TI-09 / RG-09; TI-13 / RG-13 |
| CMC-16 | SM-02 CLOSED(PENDING_RESULTS)/POST_CLOSURE_ACTIVITY; SM-04 SIGNED; SM-05 RELEASED; SM-01 completed laboratory entry | A late released result attaches through the supplied addendum/history path, sets POST_CLOSURE_ACTIVITY, and never reopens a signed Encounter or closed Visit. | Result release after closure and authorised review. | Signed and closed states remain intact while the late result is attributable and visible under its access rules. | Show the late activity and addendum; do not silently reverse payment, reopen workflow, or delete the released result. | INVALID_STATE | TI-03 / RG-03; TI-04 / RG-04; TI-13 / RG-13 |
| CMC-17 | All relevant machines and linked states | Retries and concurrent high-impact actions have one winning product outcome; losing requests cannot create duplicates or overwrite a newer state. | Create, call/start, sign, release, pay, dispense, reverse, resume, or close retries and conflicts. | Linked records expose one consistent committed outcome with no duplicate charge, queue entry, Encounter, payment, dispense, or stock effect. | Return the current authoritative outcome for safe retries; surface VERSION_CONFLICT or require explicit reconciliation for stale or materially different requests. | ALREADY_EXISTS / ALREADY_COMPLETED / VERSION_CONFLICT / IDEMPOTENCY_CONFLICT | TI-09 / RG-09; TI-10 / RG-10; TI-11 / RG-11; TI-13 / RG-13 |

Record invalid transitions and their canonical error family. A terminal
record is not edited or deleted unless the product explicitly defines a
reversal, amendment, or compensating path.

---

## 16. Complete User-Story Backlog

The backlog follows Bernard's User Story House Standard philosophy. The
frozen Product Spec story section is the canonical authority for product
behaviour and canonical acceptance criteria for the represented/current
release. Jira, GitHub, boards, spreadsheets, and other external trackers are
planning, work-selection, ownership, and progress artifacts only; they
cannot create, add to, or override product behaviour, and a contradictory or
additive tracker item is not permission to implement. Behaviour must first
enter the frozen Product Spec through Section 26. Global Story
Contract obligations are inherited and must not be redundantly copied into
every story unless the story differs.

### Release and story hygiene

- Current-release stories and acceptance criteria are canonical for the
  CURRENT IMPLEMENTABLE RELEASE only.
- Future-release material is context and roadmap intent, not permission to
  implement until selected as current through authority and change control.
- Superseded behaviour must be labelled **SUPERSEDED** with its replacement
  story ID and Product Spec version, or remain only in the superseded Spec
  version; old acceptance criteria must not appear current beside a
  replacement.
- External trackers may support planning and progress but cannot create or
  override product behaviour. Historical completion evidence remains outside
  these two canonical documents. Do not create a third canonical backlog.

### Identifier lifecycle

Once a canonical ID has been published, it is never reassigned to a different
meaning. This applies to stories and acceptance criteria, Trust Invariants,
regression gates, Global Story Contracts, journeys, state machines, decisions,
blockers, OOS items, change records, and other stable normative identifiers.
When the current documents no longer contain the old full record, preserve a
compact tombstone sufficient to prevent reuse; do not preserve the entire
obsolete story merely to retain its ID.

#### Retired Identifier Tombstones

| ID | Type | Status | Retired / superseded in version | Replacement ID / NONE |
| --- | --- | --- | --- | --- |
| NONE CURRENTLY | NOT APPLICABLE | NONE | N/A | NONE |

Historical superseded Product Specs remain history. This compact tombstone
table is the current Product Spec record for preventing identifier reuse and
ambiguity; it is not a third ID registry document.

Retired Identifier Tombstones are cumulative. Once a tombstone is created, it
is carried forward into every later frozen Product Spec, is not removed merely
because the retirement occurred several versions ago, and keeps the retired ID
permanently unavailable for reassignment. Historical full story content does
not need to remain in the current Spec; only the compact tombstone must persist.

### Story fields

| Field | Required content |
| --- | --- |
| ID | Stable identifier; never silently renumber. |
| Release | Release that owns the behaviour. |
| Epic | Domain grouping. |
| Persona | Human or SYSTEM actor. |
| Priority | Project-defined priority with an explicit meaning. |
| Story statement | As a [persona], I want [capability], so that [value]. |
| Why it matters | User, business, safety, trust, or operational value. |
| Acceptance criteria | Observable GIVEN / WHEN / THEN outcomes, including negative paths, each with a stable sub-ID such as [STORY-ID]-AC1. |
| Permissions | Required capability, resource scope, and assurance. |
| Dependencies | Story, invariant, contract, decision, or external dependency IDs. |
| Edge cases | Boundary, retry, conflict, failure, and terminal behaviour. |
| Security / privacy | Data exposure, abuse, scope, and minimisation rules. |
| Audit | Action, actor, target, reason, and safe reconstruction metadata. |
| Data / state impacts | Records, versions, state transitions, and reversibility. |
| Testing notes | Service, API, permission, tenant/scope, UI, accessibility, concurrency, and regression coverage. |

---

### Section 16A canonicalisation note

This section canonicalises the supplied REC, QUE, TRI, ENC, and LAB stories in source order. The supplied backlog contains story-level acceptance-criteria blocks but no permanent acceptance-criterion sub-identifiers. This Product Spec introduces deterministic sub-IDs in source order (`<STORY-ID>-AC01`, `<STORY-ID>-AC02`, and so on) without changing acceptance meaning, combining materially separate criteria, or splitting an atomic criterion. These sub-IDs are stable once introduced.

All stories below belong to the current V1 functional backlog. References to AUTH, TEN, USR, CAT, PAT, APT, REP, AUD, BRN, or OPS remain dependencies exactly as supplied; their detailed Product Spec authority is UNSUPPLIED / OPEN / BLOCKED, and no missing story is manufactured. DX and later epics are intentionally not populated in this phase.

### Epic REC — Reception & Check-In

**REC-001 · Check in a patient and open a Visit · V1 · P0 · `RECEPTIONIST`; secondary `FACILITY_ADMIN`, `NURSE`**
**Release** V1
**Epic** REC
**Priority** P0
**Persona** `RECEPTIONIST`; secondary `FACILITY_ADMIN`, `NURSE`
**Story** As a receptionist, I want to check in a patient (returning or from an appointment) so that a Visit is opened and the patient follows the correct first-service path.
**Why** The single entry point of the attendance loop; without it no downstream record has a parent and daily attendance cannot be counted for HMIS 031.
**Pre** Patient record exists in this facility's tenant (PAT-001/PAT-003); receptionist authenticated with a facility selected; facility `ACTIVE`; at least one active check-in destination department (TEN-005).
**Trig** Receptionist searches the patient, opens the patient summary, clicks **Check in** — or checks in from today's appointments panel.
**Flow** Check-in panel shows patient name, age, sex, facility patient number, last visit date, outstanding balance (if any) → select **Visit type** (`OUTPATIENT_NEW`, `OUTPATIENT_REVIEW`, `ANC`, `LAB_ONLY`, `PHARMACY_ONLY`, `FOLLOW_UP_RESULTS`) → select **Payer** (`CASH`, `SELF_PAY_MOMO`; REC-003) → optional administrative **reason for visit** (≤120 chars, not a clinical complaint) → **Destination department** defaults from visit type (REC-004) → confirm → `Visit(state=OPEN)`; ordinary destination types create `QueueEntry(state=WAITING)` (or `WAITING_PAYMENT` under `PAY_BEFORE_TRIAGE`) for the destination department, while successful `LAB_ONLY` check-in is the explicit exception: it creates the active Visit but no patient-facing LAB collection QueueEntry and exposes the LAB_ONLY request-capture/intake action governed by LAB-024. For every chargeable OPD consultation visit, regardless of consultation payment-timing policy, an invoice is created with exactly one consultation line and is **automatically `ISSUED`** (facility invoice number, TEN-007) on the successful check-in commit — `DRAFT` is only the pre-issue state during initial construction, while an existing ISSUED Invoice repriced under REC-003 remains ISSUED (BIL-001/002, SM-08); payment-timing policy controls only whether payment gates progression. After LAB-024 order capture and LAB-005 gate evaluation, the patient-facing LAB QueueEntry is created only when `READY_FOR_COLLECTION`. `LAB_ONLY` and `PHARMACY_ONLY` receive no consultation line → visit slip printed/offered (REC-006, RCP-002) with visit number, date, facility header, and a queue token only where an applicable QueueEntry exists.
**Alt** (a) Patient already has an OPEN visit today → block, show the existing visit with state and location, "Go to existing visit" (REC-005/REC-011). (b) Outstanding balance from a prior visit → warning banner with amount and prior visit number; may proceed (V1 does not hard-block care for debt), audited. (c) `PAY_BEFORE_TRIAGE` policy → queue entry created `WAITING_PAYMENT`, absent from the triage list until the consultation lines are paid (PAY-002/PAY-012). (d) Destination department disabled mid-session → validation error, pick another. (e) **Appointment check-in**: if the appointment specifies a clinician, the resulting queue entry is routed to that clinician's list (QUE-004); a "no-show" appointment arriving later the same day can still be checked in and the appointment moves `NO_SHOW → CHECKED_IN` with an audit entry. (f) A Visit already opened through TRI-013 is completed on that same emergency Visit; reception does not run ordinary check-in or create another Visit, and authoritative payer/price completion creates the exact-one consultation line and Invoice under SM-02/SM-08/CMC-06.
**REC-001-AC01** GIVEN an active patient with no open visit WHEN check-in is confirmed with type `OUTPATIENT_NEW` and payer `CASH` THEN a `Visit(OPEN, opened_at, opened_by)` and a `QueueEntry(WAITING, queue_type=TRIAGE)` exist for the destination department.
**REC-001-AC02** GIVEN the same patient checked in again the same day at the same facility THEN 409 `VISIT_ALREADY_OPEN` with the existing `visit_id`, and no second Visit or QueueEntry is created.
**REC-001-AC03** GIVEN an ordinary chargeable OPD consultation priced UGX 20,000 under any consultation payment-timing policy THEN on check-in commit exactly one consultation line exists and the Invoice is `ISSUED` with a facility invoice number (never left `DRAFT` — SM-08). GIVEN the Visit originated through TRI-013 instead, emergency initiation creates neither line nor Invoice; later authorised registration/financial completion creates exactly one of each on that same Visit, and merge/sign/retry cannot duplicate them.
**REC-001-AC04** GIVEN `LAB_ONLY` or `PHARMACY_ONLY` THEN no consultation line exists.
**REC-001-AC05** GIVEN `PAY_BEFORE_TRIAGE` THEN the entry is `WAITING_PAYMENT` and absent from the triage queue.
**REC-001-AC06** GIVEN two facilities in one organisation WHEN facility B requests facility A's visit THEN 404 unless the explicit same-organisation BRN read authority in TI-01 / GSC-2 / Section 10 authorises the same-organisation read; no exception is active without supplied BRN authority.
**REC-001-AC07** GIVEN an appointment-driven check-in for a no-show appointment THEN check-in succeeds and the appointment status moves to `CHECKED_IN` with audit; two receptionists checking in the same appointment concurrently → exactly one succeeds (uniqueness rule + 412).
**REC-001-AC08** GIVEN check-in confirmed THEN `VISIT_OPENED` and, where an initial QueueEntry is applicable, `QUEUE_ENTRY_CREATED` audit events exist with actor and visit; a `LAB_ONLY` check-in instead exposes the request-capture/intake obligation without a patient-facing LAB QueueEntry; `patient.last_seen_at` updates.
**Perm** `visit.create` (RECEPTIONIST, FACILITY_ADMIN, NURSE) + `appointment.read` for appointment check-in; `visit.read` to view; clinicians hold `visit.read` not `visit.create` unless granted.
**Data** Insert `visit` and any applicable `queue_entry`; for an ordinary chargeable OPD consultation, `invoice` + exactly one `invoice_line` (source `CONSULTATION`) at check-in; a TRI-013 Visit receives those records only through its later same-Visit financial-completion path; `LAB_ONLY` does not create a patient-facing LAB `queue_entry` at check-in and its request-capture/intake surface is not a QueueEntry; `Visit.appointment_id`. No clinical fields written.
**Audit** `VISIT_OPENED`, conditional `QUEUE_ENTRY_CREATED`, conditional `INVOICE_ISSUED`, conditional `OUTSTANDING_BALANCE_OVERRIDDEN`, appointment link; TRI-013 convergence uses `EMERGENCY_FINANCIAL_SETUP_COMPLETED` and retains the original emergency Visit reference.
**Err** Duplicate open visit → 409. Inactive patient → 422 `PATIENT_INACTIVE`. Missing consultation price → 422 `SERVICE_NOT_PRICED` with the service code; ordinary check-in is refused (no free care by accident), while TRI-013 care remains actionable with `EMERGENCY_FINANCIAL_SETUP_PENDING` until authorised completion succeeds. Double appointment check-in → uniqueness rule + 412. Double-submit → idempotency key returns the original visit.
**UI** Single screen, no modal chain; payer and visit type are radio groups; confirm disabled until visit type + destination chosen; after success focus returns to patient search; visit number displayed large for verbal call-out; today's appointments panel with inline Check-in.
**Dep** PAT-001, PAT-003, TEN-005, TEN-006, TEN-007, CAT-002, APT-001..003, QUE-001, REC-003, REC-004, BIL-001, BIL-002. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Insurance/scheme selection, reminders, self-check-in, triage vitals, clinical complaint coding, patient photo capture.
**Test** Table test across 6 visit types × gating policies; concurrency (two receptionists, one visit); appointment double-check-in guard; an ordinary chargeable OPD Invoice reaches `ISSUED` on check-in commit with exactly one consultation line; TRI-013 initiation remains care-actionable without guessed finance, and later registration/financial completion, merge, sign, and retry leave one original Visit, one consultation line, and one issued Invoice.

**REC-002 · Register and check in a new walk-in in one flow · V1 · P0 · `RECEPTIONIST`**
**Release** V1
**Epic** REC
**Priority** P0
**Persona** `RECEPTIONIST`
**Story** As a receptionist, I want to register a brand-new patient and check them in without navigating between modules, so the desk queue does not back up during morning rush.
**Why** ~30–40% of daily attendance at a new private clinic is first-time patients; a two-module flow doubles desk time.
**Pre** `patient.create` + `visit.create`; facility active.
**Trig** Patient search (PAT-003) returns no match; **Register new patient**.
**Flow** Registration form (PAT-001 fields: names, sex, DOB or estimated age, phone, village/parish/sub-county/district, next of kin name + phone) → duplicate detection (PAT-002) before persisting → patient created with facility patient number → flow continues directly into the REC-001 check-in panel with the patient pre-selected → complete visit type/payer/destination → confirm.
**Alt** (a) Probable duplicate → candidate list with match score and last visit date; "Use this patient" (continue with existing) or "Not the same — create new" (reason captured, audited). (b) Registration succeeds but check-in fails (e.g. `SERVICE_NOT_PRICED`) → patient retained, error shown, retryable; no orphaned visit; patient creation and visit creation are separate product actions so a visit can never exist without a patient.
**REC-002-AC01** GIVEN a completed form with no duplicate match THEN a `Patient` is created with a configured-scheme number AND the UI lands on the check-in panel with the patient bound in one navigation step.
**REC-002-AC02** GIVEN surname + sex + DOB exactly matching an existing patient THEN the API returns 200 with `duplicate_candidates[]` (not 201) and nothing is created until resolved.
**REC-002-AC03** GIVEN "Not the same" with a reason THEN the patient is created AND `DUPLICATE_OVERRIDE` records the reason and rejected candidate IDs.
**REC-002-AC04** GIVEN check-in then fails with `SERVICE_NOT_PRICED` THEN the patient exists exactly once and zero visits exist.
**Perm** `patient.create` + `visit.create` both required for the combined flow; `patient.create` alone stops at the patient summary.
**Data** Insert `patient`, identifiers, contacts, then `visit`, `queue_entry`.
**Audit** `PATIENT_CREATED`, optional `DUPLICATE_OVERRIDE`, then REC-001 events.
**Err** As PAT-001 + REC-001; network failure between the two writes must not create a visit without a patient.
**UI** Two-pane: form left, live duplicate-candidate panel right (debounced 400 ms). Age may be entered in years when DOB unknown → `dob_estimated=true` (common in Uganda).
**Dep** PAT-001, PAT-002, PAT-004, REC-001. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** NIN verification against NIRA, biometric capture, photograph.
**Test** Duplicate matrix (exact name+DOB, phonetic variant, same phone different name, same name different sex); partial-failure behaviour.

**REC-003 · Select and record payer type and price list for the visit · V1 · P0 · `RECEPTIONIST`; secondary `CASHIER`**
**Release** V1
**Epic** REC
**Priority** P0
**Persona** `RECEPTIONIST`; secondary `CASHIER`
**Story** As a receptionist, I want the visit's payer type recorded at check-in so every charge raised later uses the right price and the cashier knows how payment will be collected.
**Why** Prevents end-of-day reconciliation disputes and MoMo payments recorded as cash.
**Pre** At least one active applicable price list (CAT-002); Visit is being created or is in the existing REC-003-supported `OPEN` path; no `CONFIRMED` payment/effective payment allocation exists; if an Invoice exists, it is wholly unpaid / unpartially-paid and its applicable lines remain eligible for the supplied repricing outcome.
**Trig** Payer selection during REC-001, or **Change payer** on the existing supported `OPEN` Visit path before any `CONFIRMED` payment/effective payment allocation exists.
**Flow** Pick `CASH` or `SELF_PAY_MOMO`; bind `visit.payer_type` and `visit.price_list_id`. All subsequent charge capture reads the bound price list, not the live default, so mid-day price changes do not retroactively alter open visits.
**Alt** (a) Payer changed after charges exist but before any `CONFIRMED` payment/effective payment allocation → recalculate all applicable repricing-eligible unpaid Invoice lines against the new price list with a before/after diff, confirmation, and audited delta; an existing Invoice may already be `ISSUED` but must remain wholly unpaid / unpartially-paid, and successful repricing follows the atomic SM-08 `ISSUED → ISSUED` transition without an externally observable DRAFT state. (b) After any payment → blocked (409 `PAYER_LOCKED`); supervisor-approved adjustment only (BIL-010).
**REC-003-AC01** GIVEN a visit bound to price list "Standard 2026" WHEN a new list is published at 14:00 THEN charges added at 15:00 still use "Standard 2026".
**REC-003-AC02** GIVEN an eligible existing `ISSUED` Invoice of 20,000 with no `CONFIRMED` payment/effective payment allocation and wholly unpaid / unpartially-paid lines WHEN an authorised REC-003 actor confirms repricing to 25,000 THEN the UI shows the old/new diff (+5,000) and one atomic SM-08 `ISSUED → ISSUED` outcome commits: the same Invoice ID and facility Invoice number remain, every affected eligible line price snapshot and the authoritative total agree at 25,000, and `INVOICE_REPRICED` records the attributable old/new outcome; no authoritative DRAFT state is externally visible. GIVEN two materially conflicting repricing attempts THEN exactly one valid outcome wins, the stale loser receives the applicable existing stale/version-conflict outcome and cannot overwrite the winner, and no partial or mixed-price Invoice exists. GIVEN validation, authorisation, pricing, or another required prerequisite fails THEN no payer/price-list, line snapshot, or total change commits and the original ISSUED Invoice and original authoritative values remain unchanged. The same legitimate idempotent retry returns the committed outcome without another repricing event/outcome; materially different request-identity reuse follows the existing conflict semantics.
**REC-003-AC03** GIVEN any `CONFIRMED` payment WHEN payer change is attempted THEN 409 `PAYER_LOCKED`.
**Perm** `visit.update_payer` (RECEPTIONIST, CASHIER, FACILITY_ADMIN).
**Data** `visit.payer_type`, `visit.price_list_id`; unpaid-line re-pricing only (pre-payment), with affected eligible InvoiceLine price snapshots and authoritative totals committed atomically on the same ISSUED Invoice identity/number.
**Audit** `VISIT_PAYER_SET`, `INVOICE_REPRICED` with attributable prior/new payer, price-list, line-price, and total values.
**Err** No active price list → 422 `NO_PRICE_LIST`, check-in blocked.
**UI** Payer shown as a persistent chip in the visit header for every downstream role.
**Dep** CAT-002, TEN-006, BIL-002. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Insurance, corporate accounts, split payer, discounts (BIL-009).
**Test** Price-list immutability across a publish event; existing ISSUED 20,000 → 25,000 repricing retains Invoice ID/number and ISSUED state, exposes no authoritative DRAFT state, commits all eligible line snapshots/totals with one `INVOICE_REPRICED` outcome, preserves all prior values on failure, produces one winner plus a stale/version-conflict loser under materially competing attempts with no mixed pricing, and returns the same committed outcome without duplication on a legitimate retry.

**REC-004 · Route the checked-in patient to the correct first destination · V1 · P0 · `RECEPTIONIST`**
**Release** V1
**Epic** REC
**Priority** P0
**Persona** `RECEPTIONIST`
**Story** As a receptionist, I want visit type to drive the first queue automatically so a lab-only or pharmacy-only walk-in is not forced through triage and a consultation.
**Why** A patient collecting results or buying prescribed medicines should not consume a clinician slot or be charged a consultation fee.
**Pre** TEN-005 routing rules configured.
**Trig** Visit type selection in REC-001.
**Flow** Resolve destination: `OUTPATIENT_*` → TRIAGE queue; `ANC` → ANC/midwife queue (skips general triage; ANC has its own vitals set); `LAB_ONLY` → LAB request-capture/intake route with no patient-facing LAB collection QueueEntry at check-in → LAB-024 external/walk-in order capture → LAB-005 gate evaluation → patient-facing LAB QueueEntry only when `READY_FOR_COLLECTION`, with no consultation charge; `PHARMACY_ONLY` → PHARMACY queue, no consultation charge; `FOLLOW_UP_RESULTS` → CLINICIAN queue directly with `results_review=true`.
**Alt** (a) Override the default destination → allowed, reason optional, audited. (b) `FOLLOW_UP_RESULTS` with no released results → warning "No released results found"; override permitted.
**REC-004-AC01** GIVEN `LAB_ONLY` THEN no consultation line exists; the patient is absent from triage; the LAB request/intake path is selected; no patient-facing LAB collection QueueEntry exists before LAB-024 order capture and applicable LAB-005 gate release; when `READY_FOR_COLLECTION` is reached, `queue_type=LAB` is created as the patient-facing LAB QueueEntry.
**REC-004-AC02** GIVEN `FOLLOW_UP_RESULTS` with a lab order item in `RELEASED` THEN the clinician queue entry shows a "Results ready (n)" badge and links to the released results and the original encounter.
**REC-004-AC03** GIVEN `ANC` THEN the entry lands on the ANC queue and the triage count is unchanged.
**REC-004-AC04** GIVEN an override THEN `ROUTING_OVERRIDDEN` records default and chosen destinations.
**Perm** `visit.create`; override uses the same permission (no separate gate in V1).
**Data** `queue_entry.queue_type`, `queue_entry.department_id`, `visit.results_review_flag`.
**Audit** `ROUTING_OVERRIDDEN` when non-default.
**Err** No department of the required type → 422 with a facility-setup link (admin-only link).
**UI** Destination preview line before confirmation: "This patient will go to: Triage — Room 2".
**Dep** TEN-005, QUE-001, LAB-015. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Skill/load-balanced routing, appointment-driven routing.
**Test** One case per visit type verifying queue type, charge creation, list membership.

**REC-005 · Block or warn on duplicate open visit · V1 · P0 · `RECEPTIONIST`**
**Release** V1
**Epic** REC
**Priority** P0
**Persona** `RECEPTIONIST`
**Story** As a receptionist, I want the system to stop me creating a second visit for a patient already in the building, so queue and attendance counts stay accurate.
**Why** Duplicate visits inflate HMIS attendance, split the clinical record across two encounters, and create two invoices for one episode.
**Pre** Patient has a `Visit` in `OPEN` or `IN_PROGRESS` at this facility.
**Trig** Check-in attempt.
**Flow** Detect the open visit; present it with current state, queue/location, assigned clinician; actions: **Open existing visit**, **Reprint slip**, **Close previous visit as abandoned** (permission-gated). The abandonment action is a narrowly bounded administrative closure shortcut: it is available only when the supplied stale/abandonment path is eligible, no Encounter is `OPEN`, `AWAITING_RESULTS`, or `RESULTS_READY`, no `SIGNED` Encounter is being shortcut around (a `SIGNED` Encounter uses normal REC-012), and no active laboratory work, prescription/pharmacy work, or other non-financial active clinical/service blocker would block REC-012. It may perform only the supplied abandonment cleanup — terminalise stale queue entries as defined by this path, void the applicable unpaid Invoice under BIL-004, and preserve a `PAID` Invoice unchanged where REC-005-AC03 applies — and cannot erase or bypass unresolved clinical, laboratory, pharmacy, or financial work. Before any cleanup or closure commits, a `PARTIALLY_PAID` Invoice refuses the action atomically under REC-005-AC05; it is neither the unpaid nor the `PAID` branch.
**Alt** (a) Open visit from a previous day (staff forgot to close) → offer close as abandoned with reason only after the stale/abandonment eligibility and applicable REC-012 unresolved-work safety guards pass; REC-005's explicit stale queue/invoice cleanup is performed as part of that abandonment outcome and need not have already satisfied REC-012's ordinary queue/financial completion prerequisites (the stale queue entries need not already be terminal and the applicable unpaid Invoice need not already be paid, waived, or debt-resolved), then permit new check-in after the old closure commits. (b) If any unresolved Encounter or active clinical, laboratory, prescription/pharmacy, or other non-financial service blocker would prevent REC-012, refuse this abandonment branch and resolve through the existing authoritative path. (c) Legitimate same-day second episode (e.g. returned after an accident) → supervisor-approved second visit with mandatory reason; both visits linked via `related_visit_id`. (d) `PARTIALLY_PAID` Invoice → refuse before changing any linked state; an actor authorised by the applicable existing PAY-008 or BIL-010 correction path resolves the financial record as that path permits. KlinKlik does not automatically select or create a debt, waiver, refund, reversal, or credit outcome. Retry REC-005 only after the Invoice is in its supplied unpaid or `PAID` branch.
**REC-005-AC01** GIVEN an `OPEN` visit created today THEN 409 `VISIT_ALREADY_OPEN` with `visit_id`, `visit_state`, `current_queue`, `assigned_clinician`.
**REC-005-AC02** GIVEN an `OPEN` Visit 3 days old with an unpaid Invoice that satisfies the supplied stale/abandonment eligibility rules, has no Encounter in `OPEN`, `AWAITING_RESULTS`, or `RESULTS_READY`, has no `SIGNED` Encounter requiring normal REC-012 closure, and has no active laboratory, prescription/pharmacy, or other non-financial clinical/service blocker THEN the old Visit becomes `CLOSED(ABANDONED)` with `closed_reason`, its stale QueueEntry/QueueEntries become terminal (`CANCELLED`), its applicable unpaid Invoice is voided, and the new Visit is created only after the old closure commits. A `PAID` Invoice is exclusively REC-005-AC03 and a `PARTIALLY_PAID` Invoice is exclusively REC-005-AC05.
**REC-005-AC03** GIVEN the old visit has a `PAID` invoice and otherwise satisfies the supplied stale-abandonment eligibility rules, including no unresolved Encounter, no `SIGNED` Encounter requiring normal REC-012 closure, and no active laboratory, prescription/pharmacy, or other non-financial clinical/service blocker THEN the applicable closure proceeds without changing the invoice, and the visit closes `CLOSED(INCOMPLETE)`; a `SIGNED` Encounter uses normal REC-012 rather than the stale abandonment shortcut.
**REC-005-AC04** GIVEN a supervisor-approved same-day second visit THEN both visits carry mutually-linked `related_visit_id` and `SECOND_VISIT_OVERRIDE` is audited with the reason.
**REC-005-AC05** GIVEN the old Visit's Invoice is `PARTIALLY_PAID` WHEN **Close previous visit as abandoned** is attempted THEN the request is refused atomically with `PREREQUISITE_MISSING`, the response identifies the Invoice, CURRENT AUTHORITATIVE AMOUNT DUE, CURRENT EFFECTIVE APPLIED VALUE, remaining balance, and the applicable authorised financial owner/action, the old Visit remains open with no closure reason, all QueueEntries and financial records remain unchanged, and no new ordinary Visit is created. Original Payment, PaymentAllocation, receipt, InvoiceLine, CreditNote, RefundRequest, and Refund history is preserved. After an authorised existing financial path leaves the Invoice in a supplied unpaid or `PAID` branch, a retry follows REC-005-AC02 or REC-005-AC03 exactly; no automatic resolution is inferred.
**Perm** `visit.create`; abandonment close `visit.close_abandoned` (FACILITY_ADMIN, SUPERVISOR, RECEPTIONIST-with-grant); same-day duplicate `visit.override_duplicate` (SUPERVISOR, FACILITY_ADMIN).
**Data** Successful branch only: prior `visit.state/closed_reason/closed_by`; void the unpaid invoice under BIL-004 or preserve the `PAID` Invoice under REC-005-AC03; insert the new Visit only after old closure commits. The `PARTIALLY_PAID` refusal mutates none of these records.
**Audit** `VISIT_ABANDONED`, `SECOND_VISIT_OVERRIDE`, and conditional `INVOICE_VOIDED` for successful branches; a refused `PARTIALLY_PAID` privileged closure attempt follows REC-012-AC06's redacted denied-attempt audit contract and emits no success event.
**Err** If any Encounter is `OPEN`, `AWAITING_RESULTS`, or `RESULTS_READY`, or if active laboratory work, prescription/pharmacy work, or another non-financial clinical/service blocker would block REC-012, return the applicable unresolved-state conflict naming the blocking Encounter/work; the old Visit remains open and no new ordinary Visit is created through this abandonment branch. Resolve through ENC-017, ENC-018, or ENC-019 as applicable, then close through REC-012. A `SIGNED` Encounter also uses normal REC-012 rather than this shortcut; no receptionist/admin Encounter-abandon action or Encounter `ABANDONED` state exists. A `PARTIALLY_PAID` Invoice returns `PREREQUISITE_MISSING` with the financial blocker and required authorised next action; it is never voided or silently treated as `PAID`.
**UI** The conflict panel is informative, not a dead end — every branch has a button; never a bare error toast.
**Dep** REC-001, REC-012, BIL-004, BIL-010, PAY-008, QUE-007.
**OOS** Cross-facility duplicate detection (BRN-004 covers visibility only).
**Test** Matrix of prior-visit states × Invoice states, including the supplied unpaid and `PAID` outcomes; a `PARTIALLY_PAID` refusal asserting zero mutation of Visit, queues, Invoice, lines, Payment, allocations, receipt, refund/credit records, and new-Visit count; a valid stale abandonment with no unresolved Encounter or active lab/pharmacy blocker; and a negative case for each `OPEN`, `AWAITING_RESULTS`, and `RESULTS_READY` Encounter that verifies refusal, old Visit remains open, no new ordinary Visit is created, and the blocking path is REC-012.

**REC-006 · Reprint the visit slip / queue token · V1 · P1 · `RECEPTIONIST`**
**Release** V1
**Epic** REC
**Priority** P1
**Persona** `RECEPTIONIST`
**Story** As a receptionist, I want to reprint a visit slip when the patient loses it, so they can be identified at triage and the pharmacy window.
**Pre** Visit exists and is not `CLOSED` older than 24 h.
**Trig** **Reprint slip** on the visit or attendance list.
**Flow** Regenerate the slip with the identical visit number and queue token, marked `REPRINT #n`, to the browser print dialog.
**REC-006-AC01** GIVEN a slip reprinted THEN the body is identical except a visible "REPRINT (2)" marker and `DOCUMENT_REPRINTED` is audited with the count.
**REC-006-AC02** GIVEN a closed visit older than 24 h THEN 422 `REPRINT_WINDOW_EXPIRED`.
**Perm** `visit.print_slip`.
**Data** `visit.slip_print_count`.
**Audit** `DOCUMENT_REPRINTED`.
**Err** Missing facility print header → 422 pointing to TEN-003.
**UI** A5 layout working on 58 mm thermal and A4; facility name, phone, visit number, queue token, date/time, patient name and number; no diagnosis or clinical data.
**Dep** TEN-003, RCP-002, RCP-003, RCP-004. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Barcode/QR scanning (P2), SMS of the token.
**Test** Render test for both paper sizes; assert no PHI beyond name and number.

**REC-007 · View and filter today's attendance list · V1 · P0 · `RECEPTIONIST`; secondary `FACILITY_ADMIN`, `SUPERVISOR`**
**Release** V1
**Epic** REC
**Priority** P0
**Persona** `RECEPTIONIST`; secondary `FACILITY_ADMIN`, `SUPERVISOR`
**Story** As a receptionist, I want a live list of everyone checked in today with their current stage, so I can answer "where is my patient / how long more" without walking the corridor.
**Pre** Authenticated at a facility.
**Trig** **Today** from main navigation; auto-refresh every 20 s.
**Flow** List shows queue token, patient name + number, age/sex, visit type, current stage (`Waiting triage`, `In triage`, `Waiting clinician`, `With clinician`, `Awaiting lab`, `Awaiting payment`, `At pharmacy`, `Ready to leave`, `Closed`), waiting time in the current stage, assigned staff, payment status chip, and actions.
**Alt** (a) Filter by stage, visit type, payer, or overdue (>45 min in one stage). (b) Search within today's list by name or token.
**REC-007-AC01** GIVEN 12 patients across 5 stages THEN all appear with stage labels derived from live queue-entry and encounter states, sorted by check-in time.
**REC-007-AC02** GIVEN a queue entry moves `WAITING → IN_SERVICE` THEN the stage label changes within one refresh cycle without a full reload.
**REC-007-AC03** GIVEN the overdue filter THEN only entries past the configured threshold appear, each with elapsed minutes.
**REC-007-AC04** GIVEN a receptionist token THEN the payload contains no diagnosis, complaint, vitals or medication data (contract-level verification).
**REC-007-AC05** GIVEN facility B's session THEN zero facility A visits appear.
**Perm** `visit.read_list`; clinical columns permission-filtered in the authoritative record, not hidden in CSS.
**Data** Read-only.
**Audit** No `PHI_READ` for the list itself (name + number only); opening a chart does audit.
**Err** Refresh failure → stale-data banner with last-updated time, never a blank list.
**UI** Dense table, colour-coded waiting time (green <20, amber 20–45, red >45 min — never colour alone); works on a 13" laptop without horizontal scroll; count badges per stage.
**Dep** QUE-002, ENC-002.
**OOS** Historical attendance analytics (REP-002), cross-branch view (BRN-004).
**Test** Contract test asserting absence of clinical fields for a receptionist token; load test with 300 same-day visits.

**REC-008 · Record referral-in source · V1 · P2 · `RECEPTIONIST`**
**Release** V1
**Epic** REC
**Priority** P2
**Persona** `RECEPTIONIST`
**Story** As a receptionist, I want to record where a patient was referred from, so the owner can see which referral sources drive attendance.
**Pre** Visit being created.
**Trig** Optional field in the check-in panel.
**Flow** Select source type (`SELF`, `REFERRED_FACILITY`, `REFERRED_PERSON`, `CAMP_OUTREACH`, `WALK_BY`) + optional free-text name.
**REC-008-AC01** GIVEN source `REFERRED_FACILITY` "Kisenyi HC IV" THEN `visit.referral_source_type/name` persist and appear in REP-006.
**REC-008-AC02** GIVEN no selection THEN default `SELF`, check-in not blocked.
**Perm** `visit.create`.
**Data** Two visit columns.
**Audit** Included in `VISIT_OPENED` payload.
**Err** Free text >100 chars → truncation warning, not an error.
**UI** Collapsed "More details" section so it never slows the common path.
**Dep** REC-001, REP-006. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Referral letter attachment, referral-out tracking (DX-007 covers referral letters out).
**Test** Default-value test.

**REC-009 · Mark a patient as "left without being seen" · V1 · P1 · `RECEPTIONIST`; secondary `NURSE`, `SUPERVISOR`**
**Release** V1
**Epic** REC
**Priority** P1
**Persona** `RECEPTIONIST`; secondary `NURSE`, `SUPERVISOR`
**Story** As a receptionist, I want to remove a patient who left before being seen, so the queue reflects reality and the clinician is not called to an empty room.
**Why** LWBS rate is a real quality metric and a queue hygiene requirement.
**Pre** Queue entry `WAITING`, `CALLED` or `WAITING_PAYMENT` (unpaid abandonment); **no encounter for the visit in `OPEN`, `AWAITING_RESULTS`, `RESULTS_READY` or `SIGNED`** — a `VOIDED` encounter alone does not block. LWBS is a pre-service / pre-substantive-clinical abandonment workflow and never bypasses REC-012's clinical-integrity guards.
**Trig** **Mark as left** on the queue or attendance row.
**Flow** Confirm with reason (`LEFT_WITHOUT_BEING_SEEN`, `WENT_ELSEWHERE`, `COST`, `WAIT_TOO_LONG`, `OTHER` + text) → queue entry terminal `LWBS` (a real exit from `WAITING_PAYMENT` — never a fake pass through `WAITING`), visit `CLOSED(reason=LWBS)`, unpaid invoice voided. This accepted unpaid LWBS workflow completes Visit closure; no second manual Visit-close step follows. A `PARTIALLY_PAID` Invoice is not accepted as this unpaid branch or as the `PAID` branch: before QueueEntry, Visit, or financial state changes, the attempt is refused atomically under REC-009-AC07.
**Alt** (a) Already paid → Invoice untouched; Visit `CLOSED(LWBS_PAID)`; the applicable refund task is created or reused under REC-009-AC03 and PAY-008. (b) Patient returns later the same day → REC-005 A2 linked new Visit; the LWBS Visit is not reopened. (c) Any Encounter exists in `OPEN`/`AWAITING_RESULTS`/`RESULTS_READY` → 409 `ENCOUNTER_UNRESOLVED` with the Encounter ID and state; the clinician resolves it through the applicable existing path (normal sign, ENC-018 sign-with-pending, or ENC-019 void where appropriate), after which closure follows the normal REC-012 workflow. (d) Encounter `SIGNED` → REC-009 is not appropriate; use normal REC-012 closure. (e) `PARTIALLY_PAID` Invoice → refuse before changing any linked state; an actor authorised by the applicable existing PAY-008 or BIL-010 correction path resolves the financial record as that path permits. KlinKlik does not automatically select or create a debt, waiver, refund, reversal, or credit outcome. Retry REC-009 only after the Invoice is in its supplied unpaid or `PAID` branch.
**REC-009-AC01** GIVEN a `WAITING` entry with an unpaid invoice marked LWBS `WAIT_TOO_LONG` THEN queue entry = `LWBS`, visit = `CLOSED(LWBS)`, invoice voided, three audit events written.
**REC-009-AC02** GIVEN a `WAITING_PAYMENT` entry under `PAY_BEFORE_TRIAGE` with no encounter and an unpaid invoice WHEN the patient leaves after 30 minutes and LWBS is confirmed THEN queue entry = `LWBS` directly (no intermediate `WAITING`), visit = `CLOSED(LWBS)`, and the unpaid invoice is handled by the existing rules.
**REC-009-AC03** GIVEN a `PAID` Invoice THEN the Invoice remains `PAID`, the Visit becomes `CLOSED(LWBS_PAID)`, and a `RefundRequest(PENDING)` for the paid undelivered service is visible to the cashier. Creation and retry reuse an existing matching RefundRequest/refund obligation and never create a duplicate; if an authorised bounded Refund has already completely discharged that same obligation, its retained history is shown and no zero-value or duplicate RefundRequest is created.
**REC-009-AC04** GIVEN any encounter in `OPEN`, `AWAITING_RESULTS` or `RESULTS_READY` (e.g. a parked encounter with a downstream waiting entry) WHEN LWBS is attempted THEN 409 `ENCOUNTER_UNRESOLVED` naming the encounter ID/state, the visit remains open, and the encounter is unchanged.
**REC-009-AC05** GIVEN a `SIGNED` encounter THEN LWBS is refused — normal REC-012 closure applies.
**REC-009-AC06** GIVEN LWBS recorded THEN REP-002 counts it under "left without being seen", not "attended".
**REC-009-AC07** GIVEN the Visit's Invoice is `PARTIALLY_PAID` WHEN LWBS is attempted THEN the request is refused atomically with `PREREQUISITE_MISSING`, the response identifies the Invoice, CURRENT AUTHORITATIVE AMOUNT DUE, CURRENT EFFECTIVE APPLIED VALUE, remaining balance, and the applicable authorised financial owner/action, the Visit remains open with no closure reason, and the QueueEntry and all financial records remain unchanged. Original Payment, PaymentAllocation, receipt, InvoiceLine, CreditNote, RefundRequest, and Refund history is preserved. After an authorised existing financial path leaves the Invoice in a supplied unpaid or `PAID` branch, a retry follows REC-009-AC01/AC02 or REC-009-AC03 exactly; no automatic resolution is inferred.
**Perm** `queue.remove` (RECEPTIONIST, NURSE, SUPERVISOR, FACILITY_ADMIN).
**Data** Successful branch only: `queue_entry.state`, `visit.state/closed_reason`, unpaid Invoice void, or the supplied `PAID` Invoice/refund-task outcome. The `PARTIALLY_PAID` refusal mutates none of these records.
**Audit** `QUEUE_ENTRY_REMOVED`, `VISIT_CLOSED_LWBS`, and conditional `REFUND_REQUESTED` for successful branches; a refused `PARTIALLY_PAID` closure attempt follows REC-012-AC06's redacted denied-attempt audit contract and emits no success event.
**Err** Entry already `IN_SERVICE` → 409; ask the clinician to close the Encounter instead. A `PARTIALLY_PAID` Invoice returns `PREREQUISITE_MISSING` with the financial blocker and required authorised next action; it is never voided or silently treated as `PAID`.
**UI** Reason is mandatory, selected from a list; free text only for `OTHER`.
**Dep** REC-012, QUE-007, BIL-004, BIL-010, PAY-008, REP-002. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** All three Invoice branches: unpaid success, `PAID` success with duplicate-safe RefundRequest/refund handling, and `PARTIALLY_PAID` refusal asserting zero mutation of Visit, QueueEntry, Invoice, lines, Payment, allocations, receipt, and refund/credit records; report attribution.

**REC-010 · Undo an erroneous check-in within a grace window · V1 · P1 · `RECEPTIONIST`**
**Release** V1
**Epic** REC
**Priority** P1
**Persona** `RECEPTIONIST`
**Story** As a receptionist, I want to cancel a check-in I created by mistake (wrong patient) within a short window, so I don't leave a phantom visit and a phantom charge.
**Pre** Visit `OPEN`, created <15 minutes ago, no vitals, no encounter, no payment.
**Trig** **Cancel check-in**, visible only inside the grace window.
**Flow** Confirm with reason → visit `CANCELLED_ERROR`, queue entry `CANCELLED`, unpaid invoice voided, visit number not reused.
**REC-010-AC01** GIVEN a visit created 4 minutes ago with no downstream records cancelled "wrong patient selected" THEN visit = `CANCELLED_ERROR`, queue entry = `CANCELLED`, invoice voided, the visit remains queryable in audit but excluded from attendance reports.
**REC-010-AC02** GIVEN 20 minutes elapsed THEN 422 `GRACE_WINDOW_EXPIRED`, directed to REC-009.
**REC-010-AC03** GIVEN a triage record exists THEN 409 `CLINICAL_DATA_EXISTS` regardless of elapsed time.
**REC-010-AC04** GIVEN a cancelled visit THEN the next check-in uses the next number — cancelled numbers are never recycled.
**Perm** `visit.cancel_error`.
**Data** State changes only; nothing hard-deleted.
**Audit** `VISIT_CANCELLED_ERROR` with reason and elapsed seconds.
**Err** Any downstream record → 409 naming the blocking record type. Visit already `IN_PROGRESS` → 409 — erroneous check-in cancellation is a pre-service correction only; use the applicable existing closure/error workflows.
**UI** Countdown chip showing remaining grace minutes.
**Dep** REC-001, TRI-002.
**OOS** Hard delete, number recycling.
**Test** Boundary tests at 14:59/15:01 minutes; blocking-record matrix.

**REC-011 · Resume an in-progress visit from the desk · V1 · P1 · `RECEPTIONIST`**
**Release** V1
**Epic** REC
**Priority** P1
**Persona** `RECEPTIONIST`
**Story** As a receptionist, I want to reopen a patient's active visit to add or correct administrative details, so I don't create a duplicate to fix a typo.
**Pre** Visit `OPEN` or `IN_PROGRESS`.
**Trig** Clicking the patient on the attendance list.
**Flow** Administrative visit workspace: visit header, payer, destination, invoice summary, queue history (QUE-015), edit actions for payer (REC-003), routing (REC-004), referral source (REC-008). Clinical sections appear only as locked summaries ("Triage completed 09:14 by S. Nabirye") with no values.
**REC-011-AC01** GIVEN a receptionist opens an in-progress visit THEN vitals values, complaint text, diagnoses and medicines are absent from the API payload; only completion timestamps and staff names return.
**REC-011-AC02** GIVEN the same visit opened by a clinician THEN clinical values are present.
**REC-011-AC03** GIVEN a payer edit THEN REC-003 rules apply including the payment lock and the SM-08 atomic `ISSUED → ISSUED` repricing outcome for an eligible existing Invoice.
**Perm** `visit.read`, `visit.update_admin`; clinical read requires `encounter.read`.
**Audit** `PHI_READ` only when clinical values are actually returned.
**UI** Locked clinical sections show a padlock and the reason ("Requires clinical role"), preventing staff assuming the system is broken.
**Dep** REC-001, REC-003, REC-004, REC-008, QUE-015, ENC-002.
**OOS** Clinical editing by non-clinical roles (never permitted).
**Test** Two-role payload diff test.

**REC-012 · Close the visit at the exit desk · V1 · P0 · `RECEPTIONIST`; secondary `CASHIER`, `CLINICIAN`; `SYSTEM`, `FACILITY_ADMIN`**
**Release** V1
**Epic** REC
**Priority** P0
**Persona** `RECEPTIONIST`; secondary `CASHIER`, `CLINICIAN`; `SYSTEM`, `FACILITY_ADMIN`
**Story** As reception/cashier I want to close a completed visit so the patient stops appearing as present and the day's attendance can be reconciled.
**Why** Defines "finished"; prevents endlessly-open visits polluting queues and reports.
**Pre** Visit `OPEN`/`IN_PROGRESS`.
**Trig** Patient leaves / all steps complete, or automatic prompt when the last queue entry completes.
**Flow** Close checklist: all queue entries terminal; all encounters `SIGNED`/`VOIDED`; any TRI-013 `EMERGENCY_FINANCIAL_SETUP_PENDING` obligation is resolved on the original emergency Visit; all lab order items `RELEASED`/`CANCELLED`, except that a `PENDING_RESULTS` closure permits live lab items only when their encounter is already `SIGNED` with `signed_with_pending_orders=true` through ENC-018, whose held consultation queue entry was completed at signing with reason `SIGNED_WITH_PENDING_RESULTS`; all prescriptions terminal (`DISPENSED`/`CANCELLED`/`NOT_DISPENSED`) **or** `PARTIALLY_DISPENSED` with no active pharmacy work — no pharmacy queue entry in `WAITING`/`CALLED`/`IN_SERVICE`/`ON_HOLD`/`READY_TO_RESUME` and no provisional dispense awaiting handover — in which case the checklist asks "Prescription partially dispensed — close remaining unfilled items?" and the explicit closure confirmation as one consistent product outcome moves `PARTIALLY_DISPENSED → PARTIALLY_DISPENSED_CLOSED` together with `Visit → CLOSED` in the **single product outcome** (undispensed quantities remain historically visible; no new dispense and no stock movement are created for them; SM-06); if any pharmacy queue entry or provisional dispense is still active, closure is blocked (a `CANCELLED` provisional dispense never blocks closure — its prescription outcome is `NOT_DISPENSED` or retained `PARTIALLY_DISPENSED`, DSP-005); invoice issued and fully paid **or** explicitly waived (BIL-009) / closed with debt. LWBS closure (REC-009) obeys the same unresolved-encounter guard as this checklist — it is never a bypass around it. Blockers listed with deep links; non-blocking items are warnings requiring acknowledgment. On confirm: `Visit CLOSED` with `closed_at`, `closed_by`, `closed_reason` (closure reasons: `COMPLETED`, `PENDING_RESULTS`, `ABANDONED`, `INCOMPLETE`, `LWBS`, `LWBS_PAID`). ABANDONED and INCOMPLETE are Visit closure reasons under SM-02 / REC authority, not Encounter states; V1 defines no Encounter ABANDONED state. The REC-005 stale-abandonment shortcut inherits this checklist's unresolved-work safety guards but uses REC-005's explicitly supplied stale queue/invoice cleanup instead of requiring those cleanup targets to have already satisfied ordinary completion prerequisites. It cannot bypass unresolved Encounter or active downstream clinical/service work.
**Alt** (a) Unsigned `OPEN`, `AWAITING_RESULTS`, or `RESULTS_READY` Encounter → hard block naming the Encounter and its clinician; only the authoring clinician can sign (ENC-017/ENC-018), and no closure role bypasses this guard. (b) Outstanding lab result → only after ENC-018 has signed the Encounter with pending orders may the Visit close as `CLOSED(PENDING_RESULTS)`; the lab order stays live and actionable, and later release follows LAB-023. (c) Outstanding balance → blocked with amount and lines; `visit.close_with_debt` (SUPERVISOR/FACILITY_ADMIN) records the debt under BIL-014, or a waiver applies under BIL-009. (d) Any queue, laboratory, prescription/pharmacy, provisional Dispense, financial, or other service blocker not covered by an explicitly supplied closure alternative remains a hard block for every role, including `FACILITY_ADMIN`; V1 has no general Visit force-close and closure never invents downstream terminal states. (e) Nightly job flags visits open >24 h as `STALE_OPEN` for morning review (OPS-004) — see OD-22.
**REC-012-AC01** GIVEN a visit with an unsigned encounter in `OPEN`, `AWAITING_RESULTS`, or `RESULTS_READY` THEN closure is rejected listing the encounter and its clinician.
**REC-012-AC02** GIVEN a signed encounter with `signed_with_pending_orders=true` and active lab items THEN `CLOSED(PENDING_RESULTS)` is allowed once its consultation queue entry is terminal (`COMPLETED` with reason `SIGNED_WITH_PENDING_RESULTS`, completed as one consistent product outcome at ENC-018 signing), the live items remain actionable, and later release follows LAB-023.
**REC-012-AC03** GIVEN a `PARTIALLY_DISPENSED` prescription with no active pharmacy queue entry and no provisional dispense awaiting handover WHEN closure is confirmed with the "close remaining unfilled items" acknowledgement THEN the prescription becomes `PARTIALLY_DISPENSED_CLOSED` and the visit `CLOSED` in the single product outcome.
**REC-012-AC04** GIVEN a Visit with an outstanding balance and no waiver/debt path THEN closure is rejected with the amount. GIVEN a TRI-013 Visit with `EMERGENCY_FINANCIAL_SETUP_PENDING` THEN closure is rejected with the missing payer/price/consultation-charge setup action even if emergency care is already delivered; closure never guesses or waives that financial outcome.
**REC-012-AC05** GIVEN all conditions met THEN the visit disappears from "currently present" counts, remains fully readable, and no further ordinary clinical or billing records may be attached (409 `VISIT_CLOSED`); only explicitly defined post-closure workflows such as LAB-023 may append their permitted versioned/addendum records — this is not reopening.
**REC-012-AC06** GIVEN any actor attempts to close a Visit while a blocker remains and no explicitly supplied closure alternative defines the complete result for that blocker THEN closure is refused with the blocker and required next action identified, all linked states remain unchanged, and the denied privileged attempt is audited without PHI; `FACILITY_ADMIN` and `SUPERVISOR` have no general Visit force-close exception.
**REC-012-AC07** GIVEN a closed visit WHEN a late lab result is released THEN the result attaches to the original encounter through LAB-023 and the visit is auto-flagged `POST_CLOSURE_ACTIVITY` for review (never silently reopened).
**REC-012-AC08** GIVEN concurrent close attempts THEN the second gets 409 with current state.
**Perm** `visit.close`; `visit.close_with_debt` only for the BIL-014 path; applicable waiver/abandonment/LWBS capabilities remain defined by their own stories. No general `visit.force_close` capability exists. A clinician may sign and hand off to closure but is not granted `visit.close`.
**Data** `Visit.status/closed_*`, audit.
**Audit** `VISIT_CLOSED` with a redacted, non-PHI closure-checklist snapshot in `after_json`; denied privileged closure attempts record actor, scope, blocker type/reference, and outcome without clinical content.
**Err** Concurrent closure (409/412); closing while a cashier is mid-payment; any unresolved blocker without a supplied closure alternative → `PREREQUISITE_MISSING` or `INVALID_STATE`, with no linked state change.
**UI** Checklist with green ticks and red blockers; the close button stays disabled while any blocker exists; each blocker is clickable.
**Dep** ENC-017, ENC-019, LAB-015, LAB-022, DSP-009, BIL-005, BIL-009, BIL-014, PAY-002.
**OOS** Automatic nightly auto-close of visits with clinical/financial records (OPS-004 covers only flagging; see OD-22), discharge summaries.
**Test** Full matrix of blocking conditions and explicit closure alternatives; `CLOSED(PENDING_RESULTS)` requires a signed-with-pending-orders Encounter and keeps the lab loop alive; no closed-Visit-plus-unsigned-Encounter path; active queue/lab/pharmacy/provisional-Dispense or undefined blocker is refused for every role; post-closure result handling.

**REC-013 · Record patient arrival without check-in (walk-in enquiry) · V1 · P2 · `RECEPTIONIST`**
**Release** V1
**Epic** REC
**Priority** P2
**Persona** `RECEPTIONIST`
*(Renumbered from a duplicate-numbered draft story "REC-010" in the compact generation; content unchanged.)*
**Story** As a receptionist I want to log an enquiry/turn-away so we know demand we did not serve.
**Why** Explains lost revenue and capacity gaps.
**Pre** Facility open.
**Trig** Person asks for a service we can't provide now.
**Flow** Log reason (`NO_CLINICIAN`, `SERVICE_UNAVAILABLE`, `PRICE`, `REFERRED_OUT`, `OTHER`) + optional name/phone → no patient record required.
**Alt** Enquiry converts to check-in → link records.
**REC-013-AC01** GIVEN a turn-away logged THEN it appears on REP-004 turn-away counts and creates no `Visit`, no `Patient`, no charge.
**REC-013-AC02** GIVEN conversion to check-in THEN the enquiry is marked `CONVERTED` and linked to the visit.
**Perm** `visit.create`.
**Data** `Enquiry`.
**Audit** Create/convert.
**Err** Enquiry logging abused as shadow registration → no clinical fields available.
**UI** One-click reason buttons.
**Dep** REP-004. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Waitlists.
**Test** No-visit invariant.

---

**Source epic context — Queue Management**

Purpose: a queue entry is the patient's position in one stage. A visit generates several sequential queue entries (triage → clinician → lab → cashier → pharmacy). Queue entries are cheap, auditable, and never deleted. **The location spine: every handoff is a queue transition, and a patient waiting for results never disappears from operational worklists (QUE-006).**


---

### Epic QUE — Queue Management

**QUE-001 · Queue entry created on check-in or stage handoff · V1 · P0 · `SYSTEM`/`RECEPTIONIST`**
**Release** V1
**Epic** QUE
**Priority** P0
**Persona** `SYSTEM`/`RECEPTIONIST`
**Story** As the platform I want a queue entry per service-point episode so the patient's location is always known.
**Why** The location spine; every handoff is a queue transition.
**Pre** Visit `OPEN`/`IN_PROGRESS`; target department enabled.
**Trig** Check-in (REC-001), forward-routing (QUE-005), triage completion (TRI-007), clinician send-to-lab (ENC-016), send-to-pharmacy (ENC-017/RX-005), charge requiring payment (BIL-005).
**Flow** For an ordinary check-in or stage handoff, create `QueueEntry(visit, department, queue_type, priority, queued_at=server time, state=WAITING, source_stage, token)`. A `LAB_ONLY` check-in is an explicit exception: it opens the active Visit but does not create a patient-facing LAB QueueEntry; its request-capture/intake surface is not an `SM-01` QueueEntry. After LAB-024 order capture and LAB-005 gate evaluation, create the patient-facing LAB QueueEntry only when `READY_FOR_COLLECTION`. Priority inherits the explicitly selected triage acuity if triage has occurred; otherwise `ROUTINE` applies as an operational queue default only for entries not requiring triage (e.g. `PHARMACY_ONLY`) — consultation-path entries always receive their priority from the explicit human acuity selection (TRI-006).
**Alt** Retail pharmacy sale creates none. Disabled target queue → 422 and the calling action rolls back so a clinician never thinks a patient was sent when they were not.
**QUE-001-AC01** GIVEN check-in to Triage THEN exactly one `WAITING` entry exists for that visit+department.
**QUE-001-AC02** GIVEN a second creation attempt for an active entry on the same queue THEN no duplicate is created (active-entry uniqueness rule on `visit+department+state IN (WAITING_PAYMENT,WAITING,CALLED,IN_SERVICE,ON_HOLD,READY_TO_RESUME)`); an idempotent re-request returns the existing entry.
**QUE-001-AC03** GIVEN triage completed with acuity `EMERGENCY` THEN the onward clinician entry has `priority=EMERGENCY` and sorts above all `URGENT`/`ROUTINE` regardless of arrival time.
**QUE-001-AC04** GIVEN creation THEN `queued_at` is server time, never client time.
**Perm** Internal service call; no direct public create endpoint except reception check-in (`queue.manage` or via `visit.create`).
**Data** `QueueEntry`.
**Audit** `QUEUE_ENTRY_CREATED` with source stage.
**Err** Department deactivated after entry created → entry remains; admin must move it (QUE-005).
**UI** None (implicit).
**Dep** REC-001, TRI-006, TEN-005. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Physical ticket dispensers; parallel non-hold membership in two department queues at once — the `ON_HOLD` upstream + active downstream pattern of QUE-006 is supported.
**Test** Duplicate-entry constraint; priority inheritance.

**QUE-002 · Department work queue view · V1 · P0 · `NURSE`,`CLINICIAN`,`LAB_TECH`,`PHARMACIST`,`CASHIER`**
**Release** V1
**Epic** QUE
**Priority** P0
**Persona** `NURSE`,`CLINICIAN`,`LAB_TECH`,`PHARMACIST`,`CASHIER`
**Story** As a service-point user I want a list of patients waiting for me, ordered fairly, so I know who to call next.
**Why** The primary daily screen for five roles; shared role-scoped worklists replace paper cards and shouting names down a corridor.
**Pre** Entries exist; user has a role mapped to at least one queue type.
**Trig** User opens their queue; refresh every 15 s.
**Flow** List filtered to the user's department(s): token, patient name, number, age/sex (age in months if <5), wait time, priority chip, source (from Triage/Reception), state, brief context (triage acuity for the clinician queue; test names for the lab queue; amount due for the cashier; item count for the pharmacy); sorted priority desc then `queued_at` asc. Row count and longest wait in the header.
**Alt** (a) Clinician-assigned entries show first on that clinician's list (QUE-004) and in the department pool marked "assigned to X". (b) Multi-role user → queue switcher tabs with unread counts. (c) Empty queue → explicit empty state with the count of patients at earlier stages.
**QUE-002-AC01** GIVEN 3 routine and 1 emergency entry THEN the emergency sorts first regardless of arrival time.
**QUE-002-AC02** GIVEN two routine entries THEN the earlier `queued_at` sorts first.
**QUE-002-AC03** GIVEN a patient triaged 40 minutes ago THEN wait time displays "40 min" and the row is highlighted past the configured SLA (QUE-011).
**QUE-002-AC04** GIVEN a lab tech's session THEN each row shows requested test names but no diagnosis and no clinical notes (API payload verified).
**QUE-002-AC05** GIVEN a cashier's session THEN rows show amount due and invoice number but no test names, diagnosis or medicines.
**QUE-002-AC06** GIVEN a user without the department's capability THEN 403.
**QUE-002-AC07** GIVEN a new arrival THEN it appears within 15 s without manual reload.
**QUE-002-AC08** GIVEN an entry taken into service by another user THEN the row shows "In service — Dr. Okello" with the action disabled.
**QUE-002-AC09** GIVEN facility A's queue requested by a facility B user THEN 404.
**Perm** `queue.read` scoped to department type (`queue.read:<queue_type>`); field-level payload filtering is in the authoritative record.
**Data** Read; aggregate access audit (no per-row `PHI_READ`; opening a patient does audit).
**Err** Clock skew; long lists (paginate 25). Refresh failure → stale banner with timestamp; the last good list stays visible.
**UI** Dense rows, wait-time chips (colour + icon + text, never colour alone), single primary action per row ("Call"/"Start"); large touch targets for tablets.
**Dep** QUE-001, TRI-006, TRI-007.
**OOS** Predicted wait times, cross-department view (QUE-014), drag-and-drop reordering.
**Test** Sort determinism; SLA highlighting; per-role payload snapshots.

**QUE-003 · Call and start serving a patient · V1 · P0 · all service-point roles**
**Release** V1
**Epic** QUE
**Priority** P0
**Persona** all service-point roles
**Story** As a nurse/clinician I want to call the next patient and mark that I've started so colleagues don't call the same person.
**Why** Prevents double-calling and gives real wait/service-time data.
**Pre** Entry `WAITING`.
**Trig** Staff clicks **Call next** or a specific row's **Call**; then **Start**, or clicks **Start** directly.
**Flow** `WAITING → CALLED` (`called_by`, `called_at`) with a single-caller hold; the patient's name and token display large for verbal call-out → on **Start** (opening the stage workspace) `CALLED → IN_SERVICE` (`served_by`, `service_started_at`); the wait clock stops and `wait_seconds` freezes on the entry; the stage's working record is created if absent — triage record (TRI-001), encounter (ENC-001), dispense session (DSP-002) — or reopened if it exists (ENC-002). **Start** directly from `WAITING` is a convenience path that as one consistent product outcome records `called_at=service_started_at` and `called_by=served_by`, emits the semantic call audit, and proceeds through `CALLED` for metrics before `IN_SERVICE`.
**Alt** (a) Call a specific patient out of order → `queue.call_out_of_order`; reason optional; audited with skipped count. (b) Two staff press "Call next" simultaneously → optimistic locking; each receives a different entry; the loser of a single-entry race receives the next entry, not an error; a direct concurrent call on one entry yields 409 `ENTRY_LOCKED` naming the caller (or 409 `ALREADY_CALLED`), with a takeover option (QUE-013). (c) Patient absent → QUE-009 (`NO_SHOW` path). (d) Call expiry (configurable, default 10 min) without service start → entry returns to `WAITING` with `call_attempts+1` (QUE-009). (e) Stage-record creation failure → the entry rolls back to `CALLED` so the patient is not lost between states.
**QUE-003-AC01** GIVEN two staff calling the same entry concurrently THEN exactly one succeeds and the other receives 409 naming the caller.
**QUE-003-AC02** GIVEN 5 concurrent callers on a populated queue THEN each receives a different patient and no entry has two `called_by` values.
**QUE-003-AC03** GIVEN direct **Start** from `WAITING` THEN the entry records the starting user as `called_by` and `served_by`, sets `called_at` to `service_started_at`, and records both semantic transitions for metrics/audit.
**QUE-003-AC04** GIVEN `IN_SERVICE` THEN the entry disappears from other users' waiting lists but remains visible with the server's name.
**QUE-003-AC05** GIVEN service start on a visit whose encounter is `AWAITING_RESULTS` authored by the same clinician THEN **no new encounter is created** — the existing encounter reopens with the same ID (ENC-002; mandatory regression test).
**QUE-003-AC06** GIVEN state changes THEN each is audited with actor and timestamp.
**Perm** `queue.serve` (`queue.call`/`queue.start_service` per queue type) plus the stage's own create permission.
**Data** `QueueEntry` state/actor/times/`wait_seconds`.
**Audit** Each transition (`QUEUE_CALLED`, conditional `QUEUE_CALLED_OUT_OF_ORDER`, `QUEUE_CALL_EXPIRED`, `QUEUE_SERVICE_STARTED`).
**Err** Staff forgets to mark served → `IN_SERVICE` ageing report (QUE-011). Empty queue → 200 with `null`, not an error.
**UI** Big Call button; "Being seen by X" label; immediate transition into the stage workspace, no intermediate confirmation screen.
**Dep** QUE-002, QUE-009, ENC-001, ENC-002.
**OOS** Audio announcements, TTS.
**Test** Concurrency (race with 5 callers, single-entry 409); call timeout expiry; encounter-reuse regression.

**QUE-004 · Assign patient to a specific clinician · V1 · P1 · `RECEPTIONIST`,`NURSE`,`SUPERVISOR`**
**Release** V1
**Epic** QUE
**Priority** P1
**Persona** `RECEPTIONIST`,`NURSE`,`SUPERVISOR`
**Story** As reception I want to send a patient to a named clinician (their usual doctor, or the ANC midwife) so continuity is preserved.
**Why** Continuity of care and fair workload.
**Pre** Clinician active today.
**Trig** Routing decision (check-in appointment link, triage completion, or manual).
**Flow** Optional `assigned_user` on the queue entry → appears at the top of that clinician's personal list ("My patients"), and in the department pool marked "assigned to X".
**Alt** Assigned clinician unavailable → any clinician with `encounter.create` may take over with a reason (audited; see ENC-022 for encounter-level takeover and QUE-013 for lock takeover).
**QUE-004-AC01** GIVEN an entry assigned to Dr A THEN it appears at the top of Dr A's list and is visible-but-marked in the pool.
**QUE-004-AC02** GIVEN Dr B takes it over THEN a reason is required and the audit records the takeover.
**QUE-004-AC03** GIVEN no assignment THEN the entry is a pool entry.
**Perm** `queue.assign`.
**Data** `QueueEntry.assigned_user_id`, audit.
**Err** Assigned clinician logged out all day (see QUE-011 stale alerts).
**UI** "My patients" vs "Department" tabs.
**Dep** QUE-002, QUE-013, ENC-022.
**OOS** Load-balancing algorithms.
**Test** Takeover audit.

**QUE-005 · Move / forward a patient to another department (complete a stage and hand off) · V1 · P0 · all service-point roles**
**Release** V1
**Epic** QUE
**Priority** P0
**Persona** all service-point roles
**Story** As a clinician/nurse I want to send the patient onward so the next department sees them immediately.
**Why** The handoff mechanic itself.
**Pre** Entry `IN_SERVICE` (or completed); the stage's own completion rules satisfied.
**Trig** The stage's completion action (Complete triage, complete a patient-facing laboratory collection/receipt interaction, Sign encounter, Confirm payment, Complete dispense) or redirection. Releasing a lab result completes laboratory work, not the patient-facing laboratory QueueEntry.
**Flow** Complete current entry (`COMPLETED`, `completed_at`, `service_seconds` computed) → create the next entry at the target department (`WAITING`) in the single product outcome, carrying visit, priority and a short handoff note; the visit's current stage recomputes.
**Alt** (a) Redirect without completing (wrong queue) → `TRANSFERRED` with reason. (b) Terminal stage (patient leaves) → no next entry; visit-close prompt (REC-012). (c) Multiple next stages (e.g. lab **and** pharmacy) → V1 rule: create the payment entry first if the facility gates on payment, then lab, then pharmacy — sequenced, not parallel, so the patient is never on two active queues at once. (d) Forwarding to a department with a disabled module → rejected.
**QUE-005-AC01** GIVEN a nurse completes triage and forwards to Consultation THEN the triage entry is `COMPLETED`, a new Consultation entry is `WAITING` with the triage acuity as priority, and the patient appears in the clinician queue within 15 s.
**QUE-005-AC02** GIVEN a forward THEN the visit has at most one active queue entry **per department**, and at most one `IN_SERVICE` entry across all departments at any instant (invariant tests); a held `ON_HOLD` entry in an upstream department coexists with an active `WAITING`/`CALLED`/`IN_SERVICE` entry in a downstream department (QUE-006).
**QUE-005-AC03** GIVEN a clinician completes with two lab tests + one prescription under `PAY_BEFORE` THEN exactly one next entry is created on the CASHIER queue; the LAB entry is created only after payment confirmation (PAY-012).
**QUE-005-AC04** GIVEN a handoff note THEN it is visible to the receiving user on their queue row.
**QUE-005-AC05** GIVEN mandatory stage data missing at completion THEN 422 listing every missing field; the entry remains `IN_SERVICE`.
**QUE-005-AC06** GIVEN an injected failure on next-entry creation THEN the product outcome is not committed — no completed stage without a next stage (OPS-003 reconciliation detects orphans).
**Perm** `queue.move` (`queue.complete` per queue type) plus the stage completion permission.
**Data** Two `QueueEntry` rows, audit.
**Audit** `QUEUE_SERVICE_COMPLETED`, `QUEUE_HANDOFF` with from/to stage and reason.
**Err** Partial failure must not strand the patient (consistency).
**UI** "Send to…" with department cards, waiting counts, and a plain-words statement of where the patient goes next ("Send to Cashier — 2 patients ahead").
**Dep** QUE-001..003.
**OOS** Multi-destination parallel routing (handled by hold states, QUE-006).
**Test** Per-department active-entry invariant plus the global single-`IN_SERVICE` invariant (including the QUE-006 hold-coexistence case); consistency under injected failure.

**QUE-006 · Hold a patient awaiting results / payment / procedure · V1 · P0 · `CLINICIAN`**
**Release** V1
**Epic** QUE
**Priority** P0
**Persona** `CLINICIAN`
**Story** As a clinician I want to park a patient who has gone for tests so my room is free but the patient is not lost.
**Why** **This story is what makes Journey B possible.** Without it, patients vanish or encounters get wrongly signed.
**Pre** Entry `IN_SERVICE`; a blocking dependency exists (open lab order, unpaid gated charge, pending procedure).
**Trig** Clinician orders investigations and releases the patient from the room.
**Flow** Entry `IN_SERVICE → ON_HOLD` with `hold_reason` (`AWAITING_RESULTS`|`AWAITING_PAYMENT`|`AWAITING_PROCEDURE`) and `hold_ref` (lab order / invoice / procedure ID) → the patient moves to the "On hold" section of the clinician's list with an elapsed timer → when the dependency resolves the entry auto-flags `READY_TO_RESUME`.
**Alt** (a) Clinician resumes manually before resolution (ENC-002). (b) Patient goes home and returns tomorrow → the entry stays on hold across the day boundary and appears on the stale-hold report (QUE-011; cross-day handling per QUE-016).
**QUE-006-AC01** GIVEN a lab order is placed and the clinician clicks "Send to lab" THEN the consultation queue entry becomes `ON_HOLD(AWAITING_RESULTS)` referencing the order and the encounter becomes `AWAITING_RESULTS` (ENC-016).
**QUE-006-AC02** GIVEN a hold referencing three blocking tests WHEN only the first is released THEN the released result is readable and the entry remains `ON_HOLD` showing "1 of 3 results ready".
**QUE-006-AC03** GIVEN **ALL** blocking items referenced by the hold — across every referenced order — reach a terminal state (`RELEASED` or `CANCELLED`; `SAMPLE_REJECTED` is not terminal) THEN the entry becomes `READY_TO_RESUME` and is highlighted on the clinician's list within 30 s (LAB-018).
**QUE-006-AC04** GIVEN the consultation entry is `ON_HOLD` THEN a downstream LAB entry may simultaneously be `WAITING`/`CALLED`/`IN_SERVICE` and becomes `COMPLETED` after the patient-facing collection/receipt interaction; bench processing may continue after that completion. The held entry is the return point and stays on the clinician's worklist while the downstream entry is the patient's current location; only one entry is `IN_SERVICE` at any instant.
**QUE-006-AC05** GIVEN a held entry THEN it never disappears from any list and is counted in "patients in facility".
**QUE-006-AC06** GIVEN the clinician logs out and back in THEN the held patient is still listed; if the clinician is off shift the patient also appears on the department-level ready list (ENC-021).
**QUE-006-AC07** GIVEN resume THEN the entry returns to `IN_SERVICE` and the **same** encounter opens (ENC-002).
**QUE-006-AC08** GIVEN the clinician signs with pending results through ENC-018 THEN the held entry completes (`ON_HOLD → COMPLETED`, reason `SIGNED_WITH_PENDING_RESULTS`) rather than resuming — it never becomes `READY_TO_RESUME` (ENC-018).
**QUE-006-AC09** GIVEN the hold reference is cancelled THEN that cancellation is a terminal outcome for the dependency (reason `ORDER_CANCELLED`); with multiple blocking dependencies → ready only when every one is terminal.
**Perm** `queue.hold` (`CLINICIAN` for consultation workflows; `MIDWIFE` when acting on an ANC encounter/ANC queue entry — a scoped ANC grant, not unrestricted; `PHARMACIST` only for pharmacy entries with `hold_reason=AWAITING_PAYMENT` per DSP-008).
**Data** `QueueEntry.state/hold_reason/hold_ref/held_at`, audit.
**Audit** Hold, auto-ready, resume.
**Err** Hold with no dependency and no reason → 400 (mirrors ENC-016).
**UI** Three sections: Waiting / On hold / Ready to resume, with counts and ageing.
**Dep** LAB-004, LAB-018, ENC-016, ENC-002.
**OOS** Cross-day auto-cleanup.
**Test** Full Journey-B hold/resume including a logout in between; assert the coexistence state (consultation `ON_HOLD` + lab `IN_SERVICE`, then `COMPLETED` while the item is `RESULT_ENTERED`) is valid, that auto-ready fires only when ALL blocking dependencies are terminal, and that manual resume before resolution opens the same encounter.

**QUE-007 · Remove patient from queue (left / cancelled) · V1 · P0 · `RECEPTIONIST`,`SUPERVISOR`**
**Release** V1
**Epic** QUE
**Priority** P0
**Persona** `RECEPTIONIST`,`SUPERVISOR`
**Story** As staff I want to remove a patient who left so the queue reflects reality.
**Why** Queue trust; accurate waiting metrics.
**Pre** Entry active (`WAITING`, `WAITING_PAYMENT`, `CALLED`, `NO_SHOW`).
**Trig** Patient left / entry created in error.
**Flow** Select entry → mandatory reason (`LEFT_WITHOUT_BEING_SEEN`, `WRONG_QUEUE`, `DUPLICATE`, `SENT_HOME`, `SENT_ELSEWHERE`, `ROUTED_IN_ERROR`, `OTHER`) → terminal state `CANCELLED` (or `LWBS` for left-without-being-seen, feeding REC-009). Entries are never deleted; the removal is always visible in the visit's queue history (QUE-015).
**Alt** Generic removal with a non-LWBS reason does not necessarily close the visit; if no other active entry exists it prompts the authorised user to close or cancel it (REC-010/REC-012). The explicit `LEFT_WITHOUT_BEING_SEEN` branch invokes REC-009.
**QUE-007-AC01** GIVEN removal through the explicit `LEFT_WITHOUT_BEING_SEEN`/LWBS workflow THEN the entry is terminal, excluded from served counts, included in the LWBS report, and the visit is as one consistent product outcome closed as `CLOSED(LWBS)` or `CLOSED(LWBS_PAID)` under REC-009 with no second manual close step.
**QUE-007-AC02** GIVEN removal for `WRONG_QUEUE`, `DUPLICATE`, `SENT_HOME`, `SENT_ELSEWHERE`, `ROUTED_IN_ERROR`, or `OTHER` THEN the visit is not automatically closed by this generic removal alone.
**QUE-007-AC03** GIVEN removal without a reason THEN 400.
**QUE-007-AC04** GIVEN an `IN_SERVICE` entry THEN generic removal is forbidden and refused with 409 / `INVALID_STATE`; complete or resolve the active service through its authoritative workflow. The narrow laboratory payment-reversal exception remains only the SYSTEM/product transition defined by PAY-012, LAB-008, and SM-01, not QUE-007 generic removal.
**QUE-007-AC05** GIVEN wait-time reports THEN removed entries are excluded from service-time averages but counted in a "removed" tally.
**Perm** `queue.remove`.
**Data** `QueueEntry`, audit.
**Audit** `QUEUE_ENTRY_REMOVED` with reason.
**UI** Reason picker.
**Dep** QUE-002, QUE-015.
**OOS** Auto-purge, hard delete.
**Test** Report exclusion; history retrieval.

**QUE-008 · Priority and emergency flags · V1 · P0 · `NURSE`,`RECEPTIONIST`,`CLINICIAN`; de-escalation `CLINICIAN`,`SUPERVISOR`**
**Release** V1
**Epic** QUE
**Priority** P0
**Persona** `NURSE`,`RECEPTIONIST`,`CLINICIAN`; de-escalation `CLINICIAN`,`SUPERVISOR`
**Story** As a triage nurse I want to raise a patient's priority so the sickest are seen first.
**Why** Basic safety in a first-come-first-served culture.
**Pre** Entry exists (`WAITING` or `CALLED`).
**Trig** Emergency arrival, triage acuity (TRI-006), or deterioration observed during the visit.
**Flow** Priority `EMERGENCY|URGENT|ROUTINE` set at check-in, inherited from triage acuity (TRI-006/QUE-001), or changed explicitly with a mandatory reason → affects sort order and colour; escalation to `EMERGENCY` raises a visible alert on the clinician queue.
**Alt** Downgrade/de-escalation requires a reason and is permitted only for `CLINICIAN`/`SUPERVISOR` — nurses may escalate but not de-escalate.
**QUE-008-AC01** GIVEN triage acuity `EMERGENCY` THEN the onward consultation entry inherits priority `EMERGENCY` automatically.
**QUE-008-AC02** GIVEN a `ROUTINE` entry escalated to `EMERGENCY` with reason "SpO2 88% on recheck" THEN the clinician queue shows it first with a red escalation banner carrying the reason and the escalating nurse's name.
**QUE-008-AC03** GIVEN a priority change THEN the audit records old/new, reason and actor.
**QUE-008-AC04** GIVEN an `EMERGENCY` entry waiting >10 min THEN it is visually escalated on all department screens.
**Perm** `queue.priority.set` (escalate: NURSE, RECEPTIONIST, CLINICIAN, SUPERVISOR; de-escalate: CLINICIAN, SUPERVISOR).
**Data** `QueueEntry.priority`, `priority_changed_at`, `priority_reason`, audit.
**Err** Everyone marked urgent → REP-004 tracks priority distribution. Change on a terminal entry → 409.
**UI** Colour + icon; never colour alone. Reason shown to the receiving clinician, not buried in audit; three quick-pick reason suggestions.
**Dep** TRI-006, QUE-002.
**OOS** Formal triage scales (MTS/ESI/SATS), automated deterioration scoring (that would be clinical decision support — explicitly out of V1 scope).
**Test** Inheritance from triage; escalate/de-escalate permission asymmetry.

**QUE-009 · No-response / recall handling (no-show) · V1 · P1 · service-point roles**
**Release** V1
**Epic** QUE
**Priority** P1
**Persona** service-point roles
**Story** As a nurse I want to record that a called patient didn't answer and re-queue them so I can move on.
**Why** Keeps throughput while being fair.
**Pre** Entry `CALLED`.
**Trig** No response, **No show** button, or automatic call timeout.
**Flow** "No response" → `call_attempts`/`no_show_count` +1 → back to `WAITING` retaining the original `queued_at` (fairness: the patient keeps their place, flagged with an attempt badge). After a configurable number of attempts (default 3; second no-show already flags reception follow-up) the entry may move to `NO_SHOW` (leaves the active queue, appears on reception's follow-up list) or be removed as `LWBS` (QUE-007/REC-009).
**Alt** Patient in the toilet/at the cashier — never auto-LWBS; a human must decide.
**QUE-009-AC01** GIVEN a no-response THEN the entry returns to `WAITING` with its original queue time preserved and `call_attempts=1`, and the row carries an attempt badge.
**QUE-009-AC02** GIVEN the second no-show THEN the entry may be set `NO_SHOW`, leaves the active queue, and reception receives a follow-up item.
**QUE-009-AC03** GIVEN the configured final attempt THEN the UI offers LWBS (QUE-007) and the row is flagged.
**QUE-009-AC04** GIVEN an `EMERGENCY`-priority entry marked no-show THEN it stays `EMERGENCY` and reception receives an immediate alert row — an emergency patient who disappears is a safety event.
**QUE-009-AC05** GIVEN marking no-show on a `WAITING` entry THEN 409.
**Perm** `queue.serve`/`queue.mark_no_show`.
**Data** `QueueEntry.call_attempts`/`no_show_count`, audit.
**Audit** `QUEUE_NO_SHOW`, `QUEUE_CALL_EXPIRED`.
**Err** Never auto-LWBS.
**UI** Attempt badge; confirm dialog only for emergency-priority entries.
**Dep** QUE-003, QUE-007, REC-009.
**OOS** Paging/announcement systems, automated recall notifications (no SMS in V1).
**Test** Fairness of retained queue time; band re-sorting; emergency alert path.

**QUE-010 · Patient location strip on every screen · V1 · P1 · all roles with `queue.read`**
**Release** V1
**Epic** QUE
**Priority** P1
**Persona** all roles with `queue.read`
**Story** As any staff member I want to see where a patient currently is so I can answer questions without hunting.
**Why** Cuts the commonest interruption in a clinic.
**QUE-010-AC01** GIVEN a patient with an active queue entry THEN the patient header shows "Currently: Laboratory — waiting (12 min)". A LabOrderItem visible in a laboratory worklist, including `AWAITING_PAYMENT`, is not a patient QueueEntry and never supplies the physical location.
**QUE-010-AC02** GIVEN an upstream entry `ON_HOLD` (e.g. consultation awaiting results) and a downstream entry active (e.g. lab `IN_SERVICE`) THEN the strip derives the current location from the active downstream entry ("Currently: Laboratory — in service") and shows the held entry as the return obligation ("Consultation — awaiting results").
**QUE-010-AC03** GIVEN a pay-before lab order before payment THEN the strip shows the cashier QueueEntry, not Laboratory; after payment creates the lab QueueEntry, it shows Laboratory.
**QUE-010-AC04** GIVEN a patient with no active entry but an open visit THEN "In facility — no active queue".
**QUE-010-AC05** GIVEN a closed visit THEN "Not present".
**Perm** `queue.read`.
**Data** Read.
**Dep** QUE-001, PAT-009. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Physical location tracking.
**Test** State-string mapping for all queue states.

**QUE-011 · Waiting-time SLA and stale-state alerts · V1 · P1 · `SUPERVISOR`,`FACILITY_ADMIN`**
**Release** V1
**Epic** QUE
**Priority** P1
**Persona** `SUPERVISOR`,`FACILITY_ADMIN`
**Story** As a supervisor I want alerts when patients wait too long or sit in a state too long so nobody is forgotten.
**Why** The main safety net against dead-ends.
**Pre** SLA config per department (default: waiting 30 min, `IN_SERVICE` 60 min, `ON_HOLD` 120 min).
**Trig** Periodic evaluation (on refresh and by a scheduled sweep every 10 min).
**Flow** Breaches surface on the supervisor dashboard and as a badge on the department queue; a daily digest lists all breaches.
**QUE-011-AC01** GIVEN an entry waiting 35 min against a 30-min SLA THEN it is flagged on the department queue and counted on the supervisor dashboard.
**QUE-011-AC02** GIVEN an `ON_HOLD(AWAITING_RESULTS)` entry older than 120 min THEN it appears on the "stuck patients" list naming the blocking lab order and the ordering clinician.
**QUE-011-AC03** GIVEN no breaches THEN the dashboard explicitly shows zero rather than an empty panel.
**Perm** `queue.read` + `supervisor.dashboard`.
**Data** Computed; `Alert` rows optional.
**Audit** None (read).
**Err** Alert fatigue → per-department tuning.
**UI** Counts with drill-down.
**Dep** QUE-006.
**OOS** SMS/email escalation.
**Test** Clock-controlled SLA tests.

**QUE-012 · Waiting-room display board · V1 · P2 · `RECEPTIONIST` (facility)**
**Release** V1
**Epic** QUE
**Priority** P2
**Persona** `RECEPTIONIST` (facility)
**Story** As a facility I want a screen showing who is being called, without exposing PHI.
**Why** Reduces crowding at the desk.
**QUE-012-AC01** GIVEN the board is displayed THEN it shows patient number or first name + initial only (facility-configurable), never full name, diagnosis, age or phone.
**QUE-012-AC02** GIVEN the board URL THEN it requires a device token and shows only currently-called entries.
**Perm** Device token, read-only.
**Dep** QUE-003, AUTH-013. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** TTS announcements.
**Test** PHI-exposure review of the rendered board.

**QUE-013 · Take over an entry locked by another user · V1 · P1 · `SUPERVISOR`,`FACILITY_ADMIN`; secondary `CLINICIAN`**
**Release** V1
**Epic** QUE
**Priority** P1
**Persona** `SUPERVISOR`,`FACILITY_ADMIN`; secondary `CLINICIAN`
*(Absorbed from the alternate-generation queue set; preserves its full behaviour.)*
**Story** As a supervisor, I want to release a queue entry that a colleague locked and then went off shift, so the patient is not stuck.
**Pre** Entry `CALLED` or `IN_SERVICE`, inactive longer than the configured threshold (default 30 min).
**Trig** **Release / take over** on the entry.
**Flow** Confirm with reason → lock released; if `IN_SERVICE` with an open stage record, the record is left intact; the new user becomes co-author or the record is reassigned per stage rules (an encounter is never silently reassigned — see ENC-022).
**QUE-013-AC01** GIVEN an entry `IN_SERVICE` idle for 45 min taken over with reason THEN the entry's `assigned_user` changes, `QUEUE_TAKEOVER` is audited with both user IDs and the reason, and the original open encounter remains authored by the original clinician.
**QUE-013-AC02** GIVEN takeover attempted after 5 min idle THEN 422 `TAKEOVER_TOO_EARLY` with remaining minutes.
**QUE-013-AC03** GIVEN a takeover of an entry with an open encounter WHEN the new clinician writes notes THEN the encounter records both a primary author and a co-author, each note line carrying its own author ID.
**Perm** `queue.takeover` (SUPERVISOR, FACILITY_ADMIN).
**Audit** `QUEUE_TAKEOVER`.
**Err** Original user active in the last 5 min → blocked.
**UI** Clear warning naming the current holder and their last activity time.
**Dep** QUE-003, ENC-022.
**OOS** Automatic takeover without human decision.
**Test** Idle-threshold boundary; authorship preservation.

**QUE-014 · Supervisor view of all queues · V1 · P1 · `SUPERVISOR`,`FACILITY_ADMIN`,`ORG_OWNER`**
**Release** V1
**Epic** QUE
**Priority** P1
**Persona** `SUPERVISOR`,`FACILITY_ADMIN`,`ORG_OWNER`
**Story** As a supervisor, I want a single board showing every queue's depth and longest wait, so I can move staff to the bottleneck.
**Pre** Supervisory role at the facility.
**Trig** **Flow board**; refresh 30 s.
**Flow** Card per stage: waiting count, in-service count, longest wait, median wait today, staff currently serving. Clicking a card opens that queue read-only.
**QUE-014-AC01** GIVEN 4 waiting at triage (longest 38 min) and 9 waiting for clinicians (longest 71 min) THEN both cards show correct counts/waits and the clinician card is flagged red per the configured threshold.
**QUE-014-AC02** GIVEN a supervisor without clinical permissions opening a queue THEN the payload contains no clinical values — only counts, names and timings.
**QUE-014-AC03** GIVEN an organisation owner with two facilities THEN only the currently selected facility's data shows (cross-branch roll-up is BRN-004).
**Perm** `queue.read_board`.
**Audit** None (aggregate, no PHI).
**UI** Deliberately simple: 5–7 cards, no charts, readable from 2 m on a wall-mounted screen.
**Dep** QUE-002.
**OOS** Predicted wait times, staffing recommendations.
**Test** Aggregate correctness against seeded data; payload PHI absence.

**QUE-015 · Queue history on the visit record · V1 · P1 · all roles with `visit.read`**
**Release** V1
**Epic** QUE
**Priority** P1
**Persona** all roles with `visit.read`
**Story** As any staff member, I want the full stage timeline of a visit, so I can explain exactly where time was spent.
**Pre** Visit exists.
**Trig** Opening the visit workspace timeline.
**Flow** Chronological list of every queue entry with stage, queued/called/started/completed timestamps, actor names, waits, and any removal or escalation reason.
**QUE-015-AC01** GIVEN a visit that passed triage → clinician → cashier → lab → clinician (resumed) → pharmacy THEN six entries appear chronologically with the second clinician entry labelled "Resumed — results review" and linked to the same encounter ID as the first.
**QUE-015-AC02** GIVEN a removed entry THEN it appears greyed with its removal reason and actor.
**QUE-015-AC03** GIVEN total visit duration THEN it equals `last_completed_at − visit.opened_at` and waits + services + untracked gaps reconcile.
**Perm** `visit.read`.
**Audit** None beyond standard.
**UI** Vertical timeline, collapsible nodes, waits in minutes.
**Dep** QUE-001..009.
**OOS** Export of the timeline (REP-008 covers exports).
**Test** Reconciliation arithmetic test.

**QUE-016 · Daily queue reset and stale-entry sweep · V1 · P1 · `SYSTEM`; secondary `FACILITY_ADMIN`**
**Release** V1
**Epic** QUE
**Priority** P1
**Persona** `SYSTEM`; secondary `FACILITY_ADMIN`
**Story** As a facility admin, I want yesterday's abandoned queue entries cleared automatically, so today's board is not polluted by stale rows.
**Pre** Scheduled job enabled; facility timezone Africa/Kampala.
**Trig** Nightly at the facility's configured cut-off (default 23:59) plus on-demand admin action.
**Flow** Entries still `WAITING`/`WAITING_PAYMENT`/`CALLED`/`NO_SHOW` from previous days → `EXPIRED` with reason `DAY_ROLLOVER` (`WAITING_PAYMENT` expiry is a real exit — the unpaid patient is never left permanently active, and unpaid abandonment never converts to payment success). Visit handling: visits with **no clinical or financial records** may auto-close `CLOSED(ABANDONED)`; visits with a signed encounter close `CLOSED(INCOMPLETE)` only after morning review; visits with a paid invoice are flagged `REVIEW_REQUIRED` with the paid amount so money is never silently written off; all other stale visits are flagged `STALE_OPEN` for morning review and are **never auto-closed** (REC-012, OD-22). `IN_SERVICE` entries are never auto-expired; they are listed on an exceptions report.
**QUE-016-AC01** GIVEN an entry `WAITING` since yesterday THEN it becomes `EXPIRED`, audited with actor `SYSTEM`; a zero-record visit may close `CLOSED(ABANDONED)`, also audited.
**QUE-016-AC02** GIVEN an `IN_SERVICE` entry from yesterday THEN it is untouched and appears on the exceptions list shown to the facility admin at next login.
**QUE-016-AC03** GIVEN a visit with a paid invoice and a waiting entry THEN the visit is flagged `REVIEW_REQUIRED` with the paid amount.
**QUE-016-AC04** GIVEN the sweep runs twice THEN no additional state changes occur (idempotent).
**Perm** System job; manual trigger `ops.run_sweep` (FACILITY_ADMIN).
**Audit** `QUEUE_SWEEP_RUN` summary plus per-entity events.
**Err** Job failure retried with backoff; ops alert after 3 failures; never partially applied without an audit record.
**UI** Exceptions list on the admin dashboard with a count badge.
**Dep** REC-012, QUE-011, OPS-004. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Configurable per-department cut-offs.
**Test** Idempotency; timezone correctness across 00:00; paid-invoice guard.

---
**Source epic context — Triage**

Purpose: capture the structured observation set that gives the clinician a head start, and record the **human-assigned** acuity. Triage is a nursing record, editable by nurses, readable by clinicians, and never overwritten silently. **KlinKlik displays neutral out-of-range markers; it never computes or suggests an acuity (OD-18).**


---

### Epic TRI — Triage

**TRI-001 · Open triage for a queued patient (triage worklist and start) · V1 · P0 · `NURSE`; secondary `MIDWIFE`**
**Release** V1
**Epic** TRI
**Priority** P0
**Persona** `NURSE`; secondary `MIDWIFE`
**Story** As a triage nurse I want to open the triage form for the next patient so I can record their baseline.
**Why** Objective data before the clinician; the clinician's first context.
**Pre** Entry `WAITING` at a `TRIAGE` department; `triage.create`.
**Trig** Nurse calls the patient (QUE-003) from the triage worklist.
**Flow** The triage home is the role queue (QUE-002) filtered to `queue_type=TRIAGE` with extra columns: age (in months if <5 years), sex, visit type, wait time, and chips for under-5 or pregnant (from the patient record / prior ANC). Call → triage form opens with patient header, visit type, last visit's key vitals for comparison; `TriageRecord(visit, patient, recorded_by, started_at, state=DRAFT)` created; queue entry `IN_SERVICE`.
**Alt** (a) Patient already triaged this visit → open the existing record in amend mode (TRI-008); never create a second, unless a re-triage is explicitly requested (TRI-010). (b) Active ANC episode → the row carries an "ANC" chip and the action routes to the ANC vitals form (ANC-004). (c) Nurse session expires mid-form → the `DRAFT` record is recoverable with autosaved values (in the authoritative record autosave every 20 s, never browser storage).
**TRI-001-AC01** GIVEN a patient aged 11 months THEN age displays "11 mo" with an "Under 5" chip.
**TRI-001-AC02** GIVEN an existing triage record for this visit WHEN triage is opened THEN the existing record loads for editing, not a new one.
**TRI-001-AC03** GIVEN opening triage THEN the queue entry becomes `IN_SERVICE`.
**TRI-001-AC04** GIVEN the previous visit had vitals THEN the last recorded weight and BP show as reference with their dates; height recorded within 12 months pre-fills marked "from [date] — confirm or change", persisted only on confirmation.
**TRI-001-AC05** GIVEN a nurse's worklist payload THEN no prior diagnoses or notes are included.
**Perm** `queue.read:TRIAGE` + `triage.create`.
**Data** `TriageRecord`.
**Audit** `TRIAGE_STARTED` + save.
**Err** Two nurses opening simultaneously → 409/412. Visit closed → 409.
**UI** Single screen, numeric keypads on mobile, tab order following the physical measurement sequence; persistent red allergy banner above the form.
**Dep** QUE-003, PAT-001, PAT-007, ANC-004. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Device integration (BP machine feeds), prior-visit clinical summary on the worklist.
**Test** No-duplicate-record test; draft recovery; age-formatting boundaries (0–23 mo, 2–4 y, ≥5 y).

**TRI-002 · Record vital signs · V1 · P0 · `NURSE`,`MIDWIFE`,`CLINICIAN`**
**Release** V1
**Epic** TRI
**Priority** P0
**Persona** `NURSE`,`MIDWIFE`,`CLINICIAN`
**Story** As a nurse I want to record vitals with sane limits so errors are caught at entry.
**Why** Wrong vitals cause wrong clinical decisions; typos are frequent. Vitals are the most reused clinical data in the system (follow-up comparison, ANC, repeat observations).
**Pre** Triage record `DRAFT`.
**Trig** Measurement taken.
**Flow** Capture temperature (°C), pulse (bpm), respiratory rate, BP systolic/diastolic (mmHg), SpO₂ (%), weight (kg), height (cm), and MUAC (cm) for children 6–59 months. Each field individually optional (or explicitly **Not done** with a reason — equipment unavailable, patient declined — which is a first-class value); at least one observation required to save; blanks are never recorded as zeros. BMI computed in the authoritative record (one decimal) whenever weight + height exist, stored as derived, **no interpretation text shown**. Values outside the configured reference band are represented only with neutral reference-band markers in the payload (`outside_reference_high`/`outside_reference_low`) and display; no clinical severity, critical conclusion, fever label, advice, or other interpretation is generated.
**Alt** Equipment unavailable → "Not done — equipment unavailable" does not block completion and displays as such everywhere (never a blank or a zero).
**TRI-002-AC01** GIVEN temperature 39.8 THEN it is saved and shown only as outside the configured reference range; it is not automatically labelled "fever", assigned clinical severity, or accompanied by advice.
**TRI-002-AC02** GIVEN temperature 3.98 or 65 THEN rejected with a range error (accepted band 30.0–45.0 °C).
**TRI-002-AC03** GIVEN systolic 120 and diastolic 130 THEN rejected (`DIASTOLIC_EXCEEDS_SYSTOLIC`).
**TRI-002-AC04** GIVEN pulse 0 THEN rejected (use blank/not-done for not measured).
**TRI-002-AC05** GIVEN weight and height THEN BMI computed in the authoritative record to 1 decimal and displayed without interpretation.
**TRI-002-AC06** GIVEN a saved vital outside a configured reference band THEN a neutral marker, no advice.
**TRI-002-AC07** GIVEN MUAC for a 14-month-old THEN the field is present (cm); BMI is not displayed for under-2s without a valid height context.
**TRI-002-AC08** GIVEN a "Not done" field THEN completion is allowed and the clinician view shows "Not done (equipment unavailable)".
**TRI-002-AC09** GIVEN save THEN values, units, recorder and timestamp are stored in the versioned `TriageRecord`/`VitalsObservation` domain records, and `TRIAGE_VITALS_RECORDED` references that record version with actor, timestamp, changed field names and content hash; the generic audit payload contains no clinical values.
**Perm** `triage.create` (record vitals).
**Data** `TriageRecord` vitals + flags, derived BMI, `VitalsObservation`.
**Audit** Non-PHI metadata, changed field names, version reference and hash.
**Err** Unit confusion (°F entry) → unit label adjacent to every field, no unit switching in V1 (a wrong unit selection is a real safety risk); extremely low SpO₂ typo caught by hard bounds.
**UI** Wide numeric inputs, units always visible, normal range for the patient's age band in small grey text, out-of-range shown after blur not per keystroke with a neutral reference-band marker; no severity colour, clinical label, advice, or other clinical implication.
**Dep** TRI-001, PAT-001. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Growth charts, paediatric early-warning scores, weight-for-age percentile bands (OD-20), device integration, trend graphs.
**Test** Boundary tests per field across age bands (neonate → elderly); BMI arithmetic; implausible-value rejection for every field.

**TRI-003 · Record presenting complaint at triage · V1 · P0 · `NURSE`**
**Release** V1
**Epic** TRI
**Priority** P0
**Persona** `NURSE`
**Story** As a nurse I want to capture why the patient came, in their words, so the clinician starts informed.
**Why** Speeds clerking; supports routing.
**Pre** Triage record `DRAFT`.
**Trig** Complaint section.
**Flow** Select one or more complaints from a facility-configurable short list (fever, cough, diarrhoea, vomiting, abdominal pain, headache, injury, rash, difficulty breathing, dizziness, pregnancy-related, review of results, other) each with a duration value + unit (hours/days/weeks), plus optional free text ≤500 chars — a **nursing observation**, explicitly not a diagnosis. Alternatively record a single verbatim free-text complaint (≤500 chars) where no list is configured.
**Alt** Blank complaint on an OPD visit → saving blocked with `COMPLAINT_REQUIRED`; "other" without free text → 422 `OTHER_REQUIRES_TEXT`.
**TRI-003-AC01** GIVEN complaints "fever" (3 days) and "cough" (5 days) THEN both persist as structured rows with durations and appear on the clinician's encounter screen read-only.
**TRI-003-AC02** GIVEN a complaint of up to 500 characters THEN it saves verbatim and appears in the clinician's triage panel (ENC-004).
**TRI-003-AC03** GIVEN common complaints THEN a quick-pick list (facility-configurable) inserts text that remains editable.
**TRI-003-AC04** GIVEN more than 5 complaints THEN 422 (triage is not a full history).
**TRI-003-AC05** GIVEN the clinician later records a diagnosis THEN the triage complaint remains visible and unmodified — the clinician cannot edit the nurse's entry, only add their own history.
**Perm** `triage.create`.
**Data** `TriageComplaint` rows / `TriageRecord.presenting_complaint`.
**Audit** `TRIAGE_COMPLAINT_RECORDED`.
**Err** Nurse writing a diagnosis here → helper text "record the patient's words, not a diagnosis".
**UI** Chip-style multi-select with duration steppers; the free-text box is deliberately small.
**Dep** TRI-001, CAT-006. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Structured symptom coding, ICD coding at triage, symptom-to-diagnosis suggestion (that is CDS — out of scope).
**Test** Verbatim round-trip incl. non-ASCII; complaint-limit rule; clinician-side immutability.

**TRI-004 · Record allergies at triage · V1 · P0 · `NURSE`; secondary `CLINICIAN`,`PHARMACIST`,`MIDWIFE`**
**Release** V1
**Epic** TRI
**Priority** P0
**Persona** `NURSE`; secondary `CLINICIAN`,`PHARMACIST`,`MIDWIFE`
**Story** As a nurse I want to record known allergies so they follow the patient permanently.
**Why** The single highest-value safety datum V1 carries; the only medication-safety data V1 collects, and triage is the reliable capture point.
**Pre** Patient exists; triage record `DRAFT`.
**Trig** Triage question — mandatory to explicitly capture allergy status as one or more allergies, `NO_KNOWN_ALLERGIES`, or `UNKNOWN`.
**Flow** Explicitly capture one of three allergy-status outcomes: `NO_KNOWN_ALLERGIES` | `UNKNOWN` | one or more active recorded allergies (substance free text or facility short-list quick-pick — penicillin, sulfa, aspirin/NSAIDs, other; reaction free text; severity `MILD|MODERATE|SEVERE`) → stored **at patient level**, not visit level, with the recording visit referenced. An existing allergy from a previous visit displays with a **Confirm still accurate** action rather than requiring re-entry.
**Alt** (a) Patient reports a new allergy later → added by clinician/pharmacist; existing entries are never silently deleted — mark `ENTERED_IN_ERROR` with a reason (clinician refuting an allergy uses the same path); the entry is struck-through in history and removed from the active banner. (b) See OD-19: an exact-string-match prescription warning exists in a draft generation; V1 performs **no automatic matching** (banner display only).
**TRI-004-AC01** GIVEN one or more active allergies are recorded THEN a `patient_allergy` row exists with `recorded_by`/`recorded_at` and the red banner appears on every screen showing this patient thereafter — triage, encounter, prescription, dispense — the same component everywhere, never dismissible.
**TRI-004-AC02** GIVEN `NO_KNOWN_ALLERGIES` THEN `patient.allergy_status=NKA` with timestamp and the banner shows "No known allergies (confirmed [date])"; GIVEN `UNKNOWN` THEN `patient.allergy_status=UNKNOWN` with timestamp and the banner shows "Allergy status unknown"; NKA and UNKNOWN are distinct and neither is "Allergies: not recorded".
**TRI-004-AC03** GIVEN no active allergy records and no explicit `NKA` / `NO_KNOWN_ALLERGIES` or `UNKNOWN` status WHEN triage completion is attempted THEN 422 `ALLERGY_STATUS_REQUIRED`.
**TRI-004-AC04** GIVEN none of one or more active allergy records, `NKA` / `NO_KNOWN_ALLERGIES`, or `UNKNOWN` has ever been explicitly captured THEN the header shows "Allergies: not recorded" in a warning style; `UNKNOWN` is not `NOT RECORDED` and `NKA` is not `UNKNOWN`.
**TRI-004-AC05** GIVEN an allergy marked entered-in-error THEN it is hidden from the banner, retained in history with the reason, and the change is audited.
**TRI-004-AC06** GIVEN the platform THEN **no automatic interaction checking is performed and the UI must not imply any** (AS-11).
**Perm** `allergy.manage` (NURSE, CLINICIAN, MIDWIFE, PHARMACIST); entered-in-error requires CLINICIAN or above.
**Data** `PatientAllergy` (patient-scoped, versioned), `patient.allergy_status`.
**Audit** `ALLERGY_RECORDED`, `ALLERGY_CONFIRMED`, `ALLERGY_ENTERED_IN_ERROR`.
**Err** "Allergy" to a food vs drug — free text accepted. Free-text allergen >100 chars → 422.
**UI** Red header chip; add dialog with three fields.
**Dep** PAT-007, PAT-009, RX-003, DSP-002. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Automated allergy–drug alerts (OD-19), coded allergen terminology, cross-reactivity logic.
**Test** Banner presence on all clinical routes; distinction among active allergies, NKA, UNKNOWN, and NOT RECORDED; entered-in-error path.

**TRI-005 · Record current medications and brief history at triage · V1 · P1 · `NURSE`**
**Release** V1
**Epic** TRI
**Priority** P1
**Persona** `NURSE`
**Story** As a nurse I want to note what the patient is already taking so the clinician doesn't duplicate therapy.
**TRI-005-AC01** GIVEN up to 10 current medications entered as free text (name, dose/frequency if known) THEN they display in the clinician's triage panel and prefill the clerking "current medications" field as editable text (ENC-010), clearly labelled "from triage".
**TRI-005-AC02** GIVEN chronic conditions ticked from a short configurable list (e.g. hypertension, diabetes, HIV, asthma, epilepsy, sickle cell) THEN they appear in the clinician's context panel and prefill ENC-008.
**Perm** `triage.create`.
**Data** `TriageRecord.current_meds_text`, `chronic_flags`.
**Err** Duplication with ENC-010 → clerking clearly labels the source.
**Dep** ENC-008, ENC-010.
**OOS** Medication reconciliation workflow.
**Test** Prefill and editability.

**TRI-006 · Set triage acuity · V1 · P0 · `NURSE`**
**Release** V1
**Epic** TRI
**Priority** P0
**Persona** `NURSE`
**Story** As a nurse I want to assign an acuity so the queue orders by clinical need.
**Why** Simple prioritisation without pretending to run a validated triage scale; the single most important safety feature of the attendance loop.
**Pre** Vitals recorded or explicitly marked not done; complaint recorded.
**Trig** Acuity section of the triage form, or emergency arrival (QUE-008).
**Flow** The **nurse selects** `EMERGENCY` (see immediately) | `URGENT` (see before routine) | `ROUTINE` (routine) with an optional reason. **V1 provides no automatic acuity computation, suggestion or pre-selection from vitals or danger signs** (AS-11; the draft-generation suggestion mechanism is recorded as OD-18 and is not V1 behaviour). Acuity propagates to the clinician queue entry priority on triage completion (TRI-007/QUE-001).
**Alt** Acuity changed → queue priority updates and the change is audited with actor and reason. Selecting a level **lower** than a previously assigned `EMERGENCY` → reason mandatory (downgrade discipline).
**TRI-006-AC01** GIVEN acuity `EMERGENCY` THEN the onward consultation queue entry has priority `EMERGENCY`, sorts first with a distinct marker, the clinician queue header shows "1 emergency waiting", and the nurse is prompted to notify a clinician directly (prompt display and the nurse's confirmation/dismissal are recorded).
**TRI-006-AC02** GIVEN acuity changed THEN the queue priority updates and the audit records old/new, actor and reason.
**TRI-006-AC03** GIVEN no acuity selected WHEN triage completion is attempted THEN 422 `ACUITY_REQUIRED` — acuity has **no automatic default and no preselection**; `ROUTINE` is stored only when an authorised human explicitly selects it.
**TRI-006-AC04** GIVEN acuity assigned THEN the acuity and its reason display in the clinician's encounter header.
**Perm** `triage.create` (NURSE, CLINICIAN, MIDWIFE).
**Data** `TriageRecord.acuity`, `acuity_reason`, `QueueEntry.priority`.
**Audit** `TRIAGE_ACUITY_ASSIGNED`, conditional `TRIAGE_ACUITY_DOWNGRADED`.
**Err** Over-use of `EMERGENCY` → distribution reported (REP-004).
**UI** Three large buttons with colour + icon + text; the nurse is accountable for the decision.
**Dep** QUE-001, QUE-008, TRI-002, TRI-003.
**OOS** MTS/ESI/CTAS/SATS scoring, automated acuity suggestion (OD-18), deterioration prediction.
**Test** Priority propagation; downgrade-reason enforcement.

**TRI-007 · Save triage and forward to the clinician · V1 · P0 · `NURSE`**
**Release** V1
**Epic** TRI
**Priority** P0
**Persona** `NURSE`
**Story** As a nurse I want to finish triage and send the patient onward so the handoff is explicit.
**Why** The Reception→Nurse→Doctor baton.
**Pre** Triage has at least one vital (or not-done reasons) + complaint + acuity.
**Trig** Nurse clicks **Complete triage / Save & send**.
**Flow** Completeness check (missing mandatory items listed) → persist triage; `TriageRecord → COMPLETED` (`completed_at`, `completed_by`), read-only thereafter except via amendment (TRI-008) → triage queue entry `COMPLETED` → create consultation (or ANC) queue entry `WAITING` with inherited priority and optional assigned clinician (destination selectable: general clinician queue, named clinician, or department) → confirmation showing destination and position.
**Alt** (a) Patient sent to Laboratory or Cashier first (facility flow) → destination selectable; routing to LAB is limited to tests already ordered by an authorised orderer — nurse-initiated test ordering is not V1 behaviour (OD-21). (b) Patient sent home from triage (wrong facility) → QUE-007 + REC-012. (c) Named clinician not on duty today → warning with the option to use the general queue; proceeding is audited. (d) Validation failure → nothing is forwarded; the nurse stays on the form with errors.
**TRI-007-AC01** GIVEN a completed triage saved and forwarded THEN the clinician's queue shows the patient with a triage summary (time, temp, BP, pulse, acuity, complaint) visible on the row or one click away; vitals, complaints, acuity, allergy banner and the nurse's name and time are all visible to the clinician without further navigation.
**TRI-007-AC02** GIVEN validation failure THEN nothing is forwarded.
**TRI-007-AC03** GIVEN forwarding THEN the audit records the triage save and the queue transition as separate correlated events (`TRIAGE_COMPLETED`, `QUEUE_HANDOFF`).
**TRI-007-AC04** GIVEN acuity `EMERGENCY` THEN the notification prompt is displayed and the clinician queue shows a red banner.
**Perm** `triage.create` + `queue.move`.
**Data** `TriageRecord`, two `QueueEntry` rows.
**Err** Network failure after save before forward → idempotent retry; the triage record must not be duplicated. Concurrent completion → 409 with current state.
**UI** Single "Save & send to…" with destination preselected; the completion screen summarises what the clinician will see.
**Dep** QUE-005, TRI-006, ENC-004, CAT-007 (OD-21). Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Nurse-initiated protocol treatment, nurse prescribing, nurse diagnosis, standing orders.
**Test** Partial-failure retry; mandatory-field matrix; emergency prompt recording.

**TRI-008 · Amend a triage record · V1 · P1 · `NURSE` (author); secondary `SUPERVISOR`**
**Release** V1
**Epic** TRI
**Priority** P1
**Persona** `NURSE` (author); secondary `SUPERVISOR`
**Story** As a nurse I want to correct a mistyped vital so the clinician isn't misled, while the original remains visible for audit.
**Pre** Triage record `COMPLETED`; amendment within the facility window (default 24 h) or supervisor permission.
**Trig** **Amend** on the triage record.
**Flow** Edit values with a mandatory reason → an amendment row stores before/after values, author and reason; the current record shows the corrected value with an "Amended" badge (hover shows "was X, corrected by Y, reason"); the original remains retrievable. Before the clinician signs the encounter, the corrected value is what the clinician sees; after signing, the amendment also notifies the signing clinician (AUD-008) and appears as an addendum-style entry in the visit timeline; the signed note content itself is unchanged.
**Alt** Non-author nurse → 403 unless `triage.amend_any` (SUPERVISOR, FACILITY_ADMIN). Window expired → 422 `AMENDMENT_WINDOW_EXPIRED` with instruction to request supervisor amendment. After visit closure → allowed with supervisor + reason; flags the visit `POST_CLOSURE_ACTIVITY`.
**TRI-008-AC01** GIVEN temperature recorded 3.74 amended to 37.4 with reason "transcription error" THEN the displayed value is 37.4, the badge and hover history are present, and the versioned amendment record retains both values while `TRIAGE_AMENDED` records its version references/hashes, changed field names, actor and reason without raw clinical values.
**TRI-008-AC02** GIVEN an amendment changes acuity after the clinician has already seen the patient THEN the queue priority is **not** retroactively changed and a notice explains why.
**TRI-008-AC03** GIVEN any amendment THEN the printed record shows the current value with an amendment footnote; amended fields carry the badge everywhere, including the clinician's triage panel.
**Perm** `triage.update` (own record within window) / `triage.amend_any` otherwise.
**Data** `TriageRecord` version/amendment rows.
**Audit** Changed field names, version references/hashes and reason; no clinical before/after JSON.
**Err** Empty reason → 422. Amendment on a closed and reported visit → flagged in REP-009 data-quality report.
**Dep** AUD-008, AUD-003. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Deleting triage (never permitted).
**Test** Version-history rendering; author vs non-author permission; window boundary.

**TRI-009 · Clinician view of triage data · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** TRI
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**Story** As a clinician I want the triage data visible while I clerk so I don't re-ask or re-measure.
**Why** The main reason clinicians trust or ignore a triage module.
**Pre** Visit has a `COMPLETED` triage record; clinician has started service.
**Trig** Opening the encounter workspace.
**Flow** A fixed triage panel (sticky/collapsible, default expanded, state stored in the authoritative record in user preferences) shows: acuity chip + reason; all vitals with units in a single row, abnormal values highlighted, normal ranges on hover; BMI; complaints with durations; current meds and chronic flags; allergy banner; recorder name and time; "recorded X min ago" freshness indicator (past the configured age it states neutrally, e.g. "Vitals recorded 3 h ago"); link to previous visits' vitals (TRI-012).
**TRI-009-AC01** GIVEN an encounter opened for a triaged visit THEN the panel shows everything above and remains visible throughout clerking; at 1366×768 all seven core vitals are visible above the fold.
**TRI-009-AC02** GIVEN a vital marked "Not done — equipment unavailable" THEN it renders as such, never a blank or zero.
**TRI-009-AC03** GIVEN vitals amended after the clinician opened the encounter THEN a "triage updated" indicator appears with the new values on refresh.
**TRI-009-AC04** GIVEN no triage exists THEN the panel states "No triage recorded for this visit" with a **Record vitals now** action if the clinician holds `triage.create`; clerking proceeds.
**TRI-009-AC05** GIVEN the clinician amends nothing THEN the triage record is byte-identical to what the nurse saved (read-only to clinicians, enforced at the API).
**TRI-009-AC06** GIVEN the panel is opened THEN the encounter-open `PHI_READ` covers it; a comparison read (TRI-012) audits separately.
**Perm** `triage.read` (CLINICIAN, MIDWIFE, NURSE, SUPERVISOR — not cashier/receptionist/pharmacist).
**Data** Read-only.
**Dep** TRI-007, ENC-004, TRI-012.
**OOS** Graphical trends, automatic interpretation of vitals.
**Test** Amendment-visibility test; above-the-fold rendering; read-only enforcement.

**TRI-010 · Re-triage / repeat vitals in the same visit · V1 · P1 · `NURSE`,`CLINICIAN`**
**Release** V1
**Epic** TRI
**Priority** P1
**Persona** `NURSE`,`CLINICIAN`
**Story** As a nurse/clinician I want to record a second set of vitals (e.g. after antipyretics, on deterioration, or before discharge) without overwriting the first.
**TRI-010-AC01** GIVEN a visit with an existing triage record WHEN a repeat set is recorded THEN a new `VitalsObservation(context=REPEAT, sequence=n)` is created linked to the same visit (and open encounter if any); both sets are visible in time order; the clinician panel shows the latest with access to earlier sets; the triage record's own values are unchanged.
**TRI-010-AC02** GIVEN a repeat set THEN the queue is not re-routed automatically.
**TRI-010-AC03** GIVEN a repeat vital falls outside its configured reference range (e.g. SpO₂ 89%) WHEN the observation is saved THEN the value is stored and displayed with a neutral out-of-range marker, its unit, timestamp and recorder — no acuity or priority recommendation is generated, no escalation action is offered, suggested or preselected because of the value, and the patient's current queue priority remains unchanged unless an authorised user explicitly changes it through the standard priority control (QUE-008; AS-11, OD-18).
**TRI-010-AC04** GIVEN a nurse records the repeat while the clinician's encounter is open THEN the new set appears on refresh without losing the clinician's unsaved note text.
**Perm** `triage.create`.
**Data** `VitalsObservation` (1..n per visit; the triage record references the first).
**Audit** `VITALS_RECORDED` (context REPEAT).
**Err** Same validation as TRI-002.
**UI** Compact inline form; only the repeated fields need values.
**Dep** TRI-002, ENC-002.
**OOS** Observation charts/graphs (P2), continuous monitoring.
**Test** Ordering and latest-selection; concurrent-edit test proving unsaved clinician text survives.

**TRI-011 · Mandatory paediatric weight · V1 · P0 · `NURSE`**
**Release** V1
**Epic** TRI
**Priority** P0
**Persona** `NURSE`
**Story** As a facility I want weight to be compulsory for under-5s because dosing depends on it.
**TRI-011-AC01** GIVEN a patient aged under 5 years WHEN triage is saved without weight (or an explicit not-done reason) THEN the save is rejected with `WEIGHT_REQUIRED_UNDER_5`.
**TRI-011-AC02** GIVEN a patient aged under 5 THEN weight is displayed prominently in the clinician header and printed on the prescription (RX-007).
**TRI-011-AC03** GIVEN an age-estimated infant THEN the same rule applies.
**Perm** `triage.create`.
**Dep** PAT-010, RX-007. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Weight-based dose calculation (explicitly excluded — AS-11).
**Test** Boundary at the 5th birthday.

**TRI-012 · View the patient's vitals history · V1 · P1 · `CLINICIAN`,`NURSE`,`MIDWIFE`**
**Release** V1
**Epic** TRI
**Priority** P1
**Persona** `CLINICIAN`,`NURSE`,`MIDWIFE`
**Story** As a clinician, I want to see this patient's previous vitals in a table, so I can judge whether today's values represent a change.
**Pre** ≥1 prior recorded vital set at this facility.
**Trig** **Compare / history** in the triage panel.
**Flow** Table: date, context (triage/repeat/ANC), each vital, recorded by. Default last 5 sets, expandable to 12 months.
**TRI-012-AC01** GIVEN 8 prior sets THEN the 5 most recent show newest first with a "show more" control.
**TRI-012-AC02** GIVEN sets recorded at another facility in the same organisation THEN they are included only if the explicitly authorised external BRN-003 sharing policy grants the dedicated cross-facility capability; each row is labelled with its facility, the read is audited, and when disabled no count of hidden records is leaked. Cross-tenant access remains denied.
**TRI-012-AC03** GIVEN history opened THEN one `PHI_READ` event records the patient ID and result count.
**Perm** `triage.read` + `patient.read_cross_facility` for the shared case.
**UI** Plain table, abnormal values highlighted per TRI-002 rules; deliberately no charts in V1.
**Dep** TRI-002, BRN-003. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Trend graphs, growth charts, export.
**Test** Cross-branch visibility both ways; audit event correctness.

**TRI-013 · Triage a patient without a prior check-in (walk-in emergency) · V1 · P1 · `NURSE`; secondary `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** TRI
**Priority** P1
**Persona** `NURSE`; secondary `CLINICIAN`,`MIDWIFE`
**Story** As a triage nurse, I want to start triage immediately for a collapsing patient and let reception complete registration afterwards, so care is never delayed by paperwork.
**Why** A system that forces registration before emergency assessment will be bypassed on paper, and the record will be lost.
**Pre** Nurse holds `triage.create_emergency`.
**Trig** **Emergency triage** button on the triage home screen.
**Flow** (1) Minimum identity set: any known name (or "Unknown male, approx 30"), approximate age, sex. (2) As the explicit `EMERGENCY_CARE_FIRST` exception, SYSTEM creates one provisional `Patient(is_provisional=true)` with a temporary identifier and one `Visit` in `OPEN`, starts one TriageRecord in `DRAFT`, and transitions that same Visit `OPEN → IN_PROGRESS` because emergency triage is substantive patient service. In the same committed outcome it creates one consultation QueueEntry that remains `WAITING` with `EMERGENCY` priority; no triage QueueEntry is required or created. It records `EMERGENCY_FINANCIAL_SETUP_PENDING`. Payer, price list, price, consultation line, Invoice, payment, and payment-gate release are neither required nor guessed, and the consultation entry is immediately actionable. (3) Triage completion reuses that same consultation QueueEntry; later clinician service moves the entry through its ordinary service states while the Visit remains `IN_PROGRESS`, without another Visit transition or another Visit/TriageRecord/QueueEntry/Encounter. (4) A task appears on reception's list: "Complete registration and financial setup — provisional emergency patient"; this pending work does not delay triage or clinician care but blocks ordinary Visit closure. (5) Reception later completes or merges the patient through PAT-002 without breaking any existing links, supplies the authoritative payer/price-list choice, and completes the financial setup on the same emergency Visit. That completion creates exactly one consultation line and one Visit-linked Invoice in `ISSUED`; patient merge, Encounter signing, and retry reuse them and never create another. Later payment follows the applicable financial rules and does not move already-started or delivered emergency care backward.
**TRI-013-AC01** GIVEN "Unknown male, approx 30" entered and emergency triage starts THEN one provisional Patient, one Visit created through `OPEN` and committed as `IN_PROGRESS`, one TriageRecord in `DRAFT`, and one consultation QueueEntry `WAITING` exist; no triage QueueEntry is required or created. The clinician queue shows the consultation entry first with `EMERGENCY`, "Provisional record", and "Registration/financial setup pending" chips; reception's follow-up list has one item; no payer, price, consultation line, Invoice, payment success, or gate release was inferred. Completing the emergency TriageRecord through SM-03 reuses that same consultation QueueEntry; later clinician service starts on the same Visit, changes the consultation entry from `WAITING` through its ordinary queue path, and does not create another Visit transition, Visit, TriageRecord, QueueEntry, or Encounter.
**TRI-013-AC02** GIVEN reception later matches and merges THEN the same Visit, TriageRecord, QueueEntry, any Encounter, and any later-created consultation line, Invoice, allocation, payment, or receipt re-point to the surviving patient ID as applicable; the provisional record is retired (not deleted), and `PATIENT_MERGED` is audited with both IDs and all moved record counts. The merge creates no new Visit, charge, Invoice, or payment; merge conflicts (both records have allergies) require explicit per-field resolution — no silent overwrite.
**TRI-013-AC03** GIVEN the emergency Visit has `EMERGENCY_FINANCIAL_SETUP_PENDING` WHEN an authorised reception/financial actor supplies the authoritative payer and price-list selections and a valid consultation price THEN, on that original Visit, exactly one consultation line and one Visit-linked Invoice in `ISSUED` are created, the pending obligation clears, and the completion is audited. Concurrent completion, retry, later merge, and Encounter signing return/reuse that same financial outcome; materially conflicting payer/price input requires explicit reconciliation and cannot silently replace or duplicate it.
**TRI-013-AC04** GIVEN the provisional identity or emergency financial setup remains incomplete for more than 24 h THEN the obligation appears on the data-quality exceptions report (REP-009) with its required next action and is neither auto-deleted nor auto-closed; the emergency Visit and all care/financial history remain intact.
**TRI-013-AC05** GIVEN a user without `triage.create_emergency` THEN 403.
**Perm** `triage.create_emergency` (NURSE, CLINICIAN, MIDWIFE).
**Data** Emergency initiation inserts provisional `patient`, `visit`, `triage_record`, and consultation `queue_entry`, commits `visit.status=IN_PROGRESS`, and records `EMERGENCY_FINANCIAL_SETUP_PENDING`; later triage/clinician work reuses those records, and later same-Visit financial completion inserts exactly one `invoice`, exactly one consultation `invoice_line`, and clears the obligation; merge re-associates existing linked records without duplication.
**Audit** `PROVISIONAL_PATIENT_CREATED`, `VISIT_OPENED`, `TRIAGE_STARTED`, `VISIT_IN_PROGRESS`, `QUEUE_ENTRY_CREATED`, `EMERGENCY_CARE_FIRST`; later clinician QueueEntry start does not emit a second `VISIT_IN_PROGRESS`; later `EMERGENCY_FINANCIAL_SETUP_COMPLETED`, `CONSULTATION_LINE_CREATED`, `INVOICE_ISSUED`, and `PATIENT_MERGED` where applicable.
**UI** Visually distinct button, single confirmation tap, four fields maximum.
**Dep** PAT-002, REC-001, QUE-001, REP-009. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Mass-casualty batch registration, unidentified-patient photography.
**Test** Mandatory: TRI-013 emergency action → one provisional Patient → one Visit created `OPEN` → one DRAFT TriageRecord with `TRIAGE_STARTED` and no triage QueueEntry → the same Visit becomes `IN_PROGRESS` in the initiation outcome → one consultation QueueEntry remains `WAITING` at EMERGENCY priority → SM-03 triage completion reuses that entry → clinician start uses the same Visit and changes only the consultation QueueEntry/service records while Visit remains `IN_PROGRESS` and no second `VISIT_IN_PROGRESS` occurs → no duplicate Visit, TriageRecord, QueueEntry, or Encounter. Emergency initiation remains care-actionable with no payer/price/line/Invoice/payment guessed; ordinary PAY_BEFORE_TRIAGE remains gated; registration and financial completion on the original Visit creates exactly one consultation line and issued Invoice; concurrent completion/retry/merge/signing cannot duplicate Patient, Visit, triage record, queue, charge, or Invoice; full merge verifies referential integrity across Visit, triage, queue, Encounter, Invoice, allocation, payment, and receipt; unresolved setup blocks REC-012 closure without rolling care backward.

---

**Source epic context — Clinical Encounter / Doctor Clerking**

> This epic is deliberately granular. The encounter is a **long-lived, resumable, versioned clinical record**, not a form submission. A patient returning from the laboratory, cashier or another room resumes the **same** encounter; a second encounter is never created for the same visit while one is open.


---

### Epic ENC — Clinical Encounter / Doctor Clerking

**ENC-001 · Start an encounter from the clinician queue · V1 · P0 · `CLINICIAN`; secondary `MIDWIFE`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`; secondary `MIDWIFE`
**Story** As a clinician I want to start seeing the next patient so an encounter record exists and my colleagues know the patient is with me.
**Why** Creates the clinical container and claims the patient.
**Pre** Queue entry `WAITING`/`CALLED` at a `CONSULTATION` department; `encounter.create`; active visit in `OPEN` or `IN_PROGRESS`.
**Trig** Clinician clicks "Start consultation".
**Flow** Call → queue entry `IN_SERVICE` → **check for an existing non-terminal encounter for this visit**: if one exists, open it (ENC-002); otherwise create `Encounter(visit, patient, provider, type=OPD, state=OPEN, started_at)`. Starting consultation on an `OPEN` Visit may cause SM-02 `OPEN → IN_PROGRESS`; an already `IN_PROGRESS` Visit remains `IN_PROGRESS` → clerking workspace opens.
**Alt** (a) Patient has an open encounter from _another_ clinician → do not create a second; show "Open encounter held by Dr X" with a takeover path (ENC-022). (b) Consultation not paid under `PAY_BEFORE` → warn with the outstanding amount; clinician may proceed with `billing.gate.override` (audited) or send the patient to the cashier.
**ENC-001-AC01** GIVEN a visit with no encounter WHEN the clinician starts THEN exactly one encounter is created in state `OPEN` linked to that visit.
**ENC-001-AC02** GIVEN a visit with an existing `OPEN`/`AWAITING_RESULTS`/`RESULTS_READY` encounter WHEN the clinician starts THEN **no new encounter is created** and the existing one opens with all previously entered content.
**ENC-001-AC03** GIVEN concurrent starts by two clinicians THEN exactly one encounter exists (active-entry uniqueness rule on `visit + state NOT IN (SIGNED,VOIDED)`).
**ENC-001-AC04** GIVEN an unpaid gated consultation THEN the clinician sees the outstanding amount before the workspace opens.
**ENC-001-AC05** GIVEN encounter creation THEN the audit records provider, visit, patient and time.
**Perm** `encounter.create`.
**Data** `Encounter`, `QueueEntry.state`.
**Audit** Create + open.
**Err** Visit `CLOSED` between queueing and starting → 409 `VISIT_CLOSED`; Visit `CANCELLED_ERROR` is terminal and is rejected with the applicable invalid/terminal Visit error (visit reopening is not defined in V1).
**UI** Workspace: left = context (patient, triage, history), centre = clerking sections, right = orders/prescriptions tray.
**Dep** QUE-003, TRI-009.
**OOS** Templates per specialty (P2).
**Test** **Single-encounter-per-visit invariant under concurrency** (mandatory regression test every release).

**ENC-002 · Resume an existing open encounter · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**Story** As a clinician I want to reopen the same encounter after the patient returns from the lab, cashier or another room so my notes continue where I left them.
**Why** **The core correction of the previous design mistake.**
**Pre** Encounter in `OPEN`/`AWAITING_RESULTS`/`RESULTS_READY`; user is the author or has takeover rights.
**Trig** Clinician clicks the patient in "On hold"/"Ready to resume", or opens the visit.
**Flow** Load the same encounter ID with all sections, draft text, orders, results and prescriptions → state moves to `OPEN` if it was `RESULTS_READY` → queue entry returns to `IN_SERVICE`.
**Alt** Encounter authored by another clinician → read-only unless takeover (ENC-022).
**ENC-002-AC01** GIVEN an encounter left in `AWAITING_RESULTS` two hours ago WHEN resumed THEN the encounter ID is unchanged, every previously entered field is present verbatim, and the previously placed orders are listed with their current statuses.
**ENC-002-AC02** GIVEN resume from `RESULTS_READY` THEN released results display inline in the encounter and the state becomes `OPEN`.
**ENC-002-AC03** GIVEN a resume across a logout/login boundary THEN behaviour is identical.
**ENC-002-AC04** GIVEN a resume THEN an audit event `ENCOUNTER_RESUMED` records actor and previous state.
**ENC-002-AC05** GIVEN the visit was closed in error WHEN resume is attempted THEN 409 `VISIT_CLOSED` and neither the Encounter nor its queue entry is modified; visit reopening is **not defined** by the supplied V1 stories and must be separately specified before any implementation.
**ENC-002-AC06** GIVEN an encounter `AWAITING_RESULTS` with only 1 of 3 blocking results released WHEN the clinician resumes early THEN the same encounter opens (`OPEN`), the consultation queue entry returns to `IN_SERVICE`, and the remaining laboratory work continues undisturbed — early manual resume never creates a second encounter.
**Perm** `encounter.update` (author) or `encounter.takeover`.
**Data** `Encounter` state, audit.
**Err** Two devices resuming the same encounter → record version conflict on save with a field-level diff.
**UI** "Ready to resume" list item shows what changed ("3 results released").
**Dep** QUE-006, LAB-018.
**OOS** Real-time collaborative editing.
**Test** Journey-B resume with identical encounter ID asserted.

**ENC-003 · Patient context panel in the encounter · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**Story** As a clinician I want the patient's key background beside my note so I don't switch screens.
**ENC-003-AC01** GIVEN an open encounter THEN the context panel shows: name, sex, age (with "est." if estimated), patient number, allergies (or NKA / UNKNOWN / not recorded), chronic flags, last 3 visits with dates and primary diagnoses, active prescriptions from the last 30 days, and the last 3 lab results with dates.
**ENC-003-AC02** GIVEN a minor THEN guardian and weight are shown.
**ENC-003-AC03** GIVEN no history THEN each section shows an explicit empty state.
**ENC-003-AC04** GIVEN the panel is opened THEN a single access-audit event is written for the encounter view, not one per sub-section.
**Perm** `encounter.read` + `patient.read`.
**Dep** PAT-009. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Cross-facility history unless the explicitly authorised external BRN-005 policy grants the dedicated same-organisation capability; any such read remains audited and never weakens cross-tenant tenant-isolation boundary.
**Test** Payload authorisation; empty states.

**ENC-004 · Triage context inside the encounter · V1 · P0 · `CLINICIAN`** — see TRI-009 for the reciprocal view.
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`
**ENC-004-AC01** GIVEN triage exists THEN vitals with units, BMI, acuity, complaint, recorder and time appear without extra navigation and are read-only to the clinician.
**ENC-004-AC02** GIVEN the clinician needs new vitals THEN they can request a repeat (creates a nursing task in the triage queue, QUE-005 / TRI-010) rather than editing the nurse's record.
**Perm** `triage.read`.
**Dep** TRI-009.
**Test** Read-only enforcement (API rejects clinician edits to triage).

**ENC-005 · Presenting complaint · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**Story** As a clinician I want to record the presenting complaint(s) and duration so the note starts correctly.
**ENC-005-AC01** GIVEN one or more complaints entered (text up to 500 chars each, optional duration value + unit `HOURS|DAYS|WEEKS|MONTHS`) THEN they are stored as an ordered list and printed as such.
**ENC-005-AC02** GIVEN the triage complaint exists THEN it is offered as a one-click copy into this field and remains separately visible.
**ENC-005-AC03** GIVEN an encounter saved without a presenting complaint THEN signing is blocked (ENC-017) although drafting is allowed.
**Data** `Encounter.complaints[]`.
**Dep** ENC-015.
**Test** Sign-blocking rule.

**ENC-006 · History of presenting complaint · V1 · P0 · `CLINICIAN`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`
**ENC-006-AC01** GIVEN free text up to 4000 characters THEN it saves, autosaves (ENC-015), preserves line breaks, and renders identically on print.
**ENC-006-AC02** GIVEN the field exceeds the limit THEN a clear character counter and a 400 error prevent silent truncation.
**Data** `Encounter.hpc`.
**Test** Round-trip of long text with newlines.

**ENC-007 · Review of systems (optional, structured-lite) · V1 · P2 · `CLINICIAN`**
**Release** V1
**Epic** ENC
**Priority** P2
**Persona** `CLINICIAN`
**ENC-007-AC01** GIVEN a configurable system checklist (CVS, RS, GIT, CNS, GUS, MSS) THEN the clinician can mark each `NOT_ASSESSED|NORMAL|ABNORMAL` with a free-text note, and only assessed systems print.
**ENC-007-AC02** GIVEN nothing is marked THEN the section is omitted from print entirely.
**Data** `Encounter.ros[]`.
**OOS** Symptom coding.

**ENC-008 · Past medical history · V1 · P0 · `CLINICIAN`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`
**ENC-008-AC01** GIVEN chronic conditions selected from the configurable list plus free text THEN they save against the **encounter** and optionally promote to a patient-level problem list entry (ENC-009) when the clinician ticks "add to problem list".
**ENC-008-AC02** GIVEN triage chronic flags THEN they are prefilled and editable, labelled "from triage".
**Data** `Encounter.pmh`, `PatientProblem` (if promoted).
**Test** Promotion behaviour.

**ENC-009 · Patient problem list · V1 · P1 · `CLINICIAN`**
**Release** V1
**Epic** ENC
**Priority** P1
**Persona** `CLINICIAN`
**Story** As a clinician I want a persistent list of the patient's ongoing problems so every future visit starts informed.
**ENC-009-AC01** GIVEN a problem added with onset date and status `ACTIVE|RESOLVED` THEN it appears on the patient header/context in all future encounters until resolved.
**ENC-009-AC02** GIVEN a problem is resolved THEN it is retained with a resolution date and is excluded from the active display.
**ENC-009-AC03** GIVEN problem changes THEN they are audited with actor and encounter reference.
**Data** `PatientProblem`.
**OOS** Automatic derivation from diagnoses (OD-08).
**Test** Persistence across visits.

**ENC-010 · Current medications in clerking · V1 · P0 · `CLINICIAN`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`
**ENC-010-AC01** GIVEN medications prefilled from triage and from prescriptions dispensed in the last 30 days THEN the clinician can confirm, edit or add entries as free text; the stored value is the clinician's confirmed list, with the source of each line indicated.
**ENC-010-AC02** GIVEN "none" is selected THEN it is stored explicitly and distinguishable from an unanswered field.
**Data** `Encounter.current_meds[]`.
**Dep** TRI-005, DSP-012.
**OOS** Interaction checking (AS-11).

**ENC-011 · Allergies review in clerking · V1 · P0 · `CLINICIAN`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`
**ENC-011-AC01** GIVEN patient allergies exist THEN the clinician must acknowledge or update them before signing (a single "reviewed" tick with timestamp).
**ENC-011-AC02** GIVEN allergy status is `NOT RECORDED` (no active allergy records, NKA, or UNKNOWN has been explicitly recorded) THEN signing is blocked until the clinician records `NKA`, `UNKNOWN`, or one or more active allergies.
**ENC-011-AC03** GIVEN an allergy is added here THEN it is stored at patient level (TRI-004) and immediately reflected in the header.
**Data** `PatientAllergy`, `Encounter.allergies_reviewed_at`.
**Dep** TRI-004, ENC-017.
**Test** Sign-blocking on `NOT RECORDED` allergy status and acceptance of active allergies, NKA, and UNKNOWN.

**ENC-012 · Family and social history · V1 · P2 · `CLINICIAN`**
**Release** V1
**Epic** ENC
**Priority** P2
**Persona** `CLINICIAN`
**ENC-012-AC01** GIVEN free-text family history and structured-lite social fields (smoking `NEVER|FORMER|CURRENT`, alcohol `NEVER|OCCASIONAL|REGULAR`, occupation) THEN they save and print when populated and are omitted when empty.
**Data** `Encounter.fh`, `Encounter.sh`.
**OOS** Risk scoring.

**ENC-013 · Surgical / obstetric / drug history · V1 · P1 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** ENC
**Priority** P1
**Persona** `CLINICIAN`,`MIDWIFE`
**ENC-013-AC01** GIVEN past surgeries (procedure, year, facility) as repeatable rows THEN they save and display in the context panel of future encounters.
**ENC-013-AC02** GIVEN a female patient of reproductive age THEN obstetric summary fields (gravida, para, living children) are available and, when the ANC module is enabled, are shared with the ANC record (ANC-003) as a single source of truth.
**Data** `Encounter.surgical_history[]`, `PatientObstetricSummary`.
**Dep** ANC-003.
**Test** Single-source consistency between ENC and ANC.

**ENC-014 · Examination findings · V1 · P0 · `CLINICIAN`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`
**ENC-014-AC01** GIVEN general examination free text plus per-system examination fields (each optional, up to 2000 chars) THEN only populated sections are stored and printed.
**ENC-014-AC02** GIVEN a "normal examination" quick action THEN it inserts editable template text and never auto-signs or auto-fills clinical findings the clinician has not reviewed.
**ENC-014-AC03** GIVEN examination text THEN it is included in the signed note verbatim.
**Data** `Encounter.examination`.
**OOS** Body diagrams, images (P2).

**ENC-015 · Autosave and explicit draft save · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**Story** As a clinician I want my typing preserved even if the power or network drops, because power cuts are routine.
**Why** Prevents the single most rage-inducing failure in Ugandan clinic software.
**Pre** Encounter `OPEN`.
**Trig** Typing pauses (debounced 3 s) or explicit Save.
**Flow** Draft content saved to the authoritative record with the current record version; success shows "Saved HH:MM:SS"; failure shows an unmistakable "Not saved — retrying" state with a manual retry.
**Alt** Offline/failed → content retained **in memory only** with a persistent warning banner; the clinician is warned not to navigate away; no PHI is written to browser storage (AUTH-013).
**ENC-015-AC01** GIVEN a clinician types HPC text and pauses 3 seconds THEN the draft is persisted in the authoritative record and the UI shows a saved indicator with the server timestamp.
**ENC-015-AC02** GIVEN the browser is closed and reopened after an autosave THEN resuming the encounter shows the saved content.
**ENC-015-AC03** GIVEN the network fails during autosave THEN the UI shows "Not saved" persistently (not a transient toast) and retries with backoff; on reconnection the content saves without duplication.
**ENC-015-AC04** GIVEN a stale record version (another device edited) THEN the save returns 412 and the clinician is shown both versions to reconcile — content is never silently overwritten.
**ENC-015-AC05** GIVEN the idle timeout fires (AUTH-012) THEN the draft is already persisted and no content is lost.
**Perm** `encounter.update`.
**Data** `Encounter` draft fields, `version`.
**Audit** Autosaves are **not** individually audited (volume); a single `ENCOUNTER_DRAFT_UPDATED` summary per session-minute is retained.
**Err** Two tabs; power loss mid-request.
**UI** Persistent save-state chip near the title; never a disappearing toast as the only indicator.
**Dep** AUD-012, AUTH-012, AUTH-013. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Offline queueing.
**Test** Kill-the-tab test; 412 reconciliation UI.

**ENC-016 · Park encounter as awaiting results · V1 · P0 · `CLINICIAN`,`MIDWIFE` (ANC encounters)`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE` (ANC encounters)`
**Story** As a clinician I want to send the patient for tests and free my room without signing the note.
**Why** Makes Journeys B and D real.
**Pre** Encounter `OPEN` with ≥1 non-terminal lab order (or an explicit "awaiting other" reason).
**Trig** Clinician clicks "Send for investigations / park".
**Flow** Encounter `OPEN → AWAITING_RESULTS`; consultation queue entry `IN_SERVICE → ON_HOLD(AWAITING_RESULTS)` (QUE-006) — the held entry is the return point. Under `LABORATORY=PAY_BEFORE`, the cashier QueueEntry is the patient's active current location and no patient-facing lab QueueEntry exists until qualifying payment; then the lab QueueEntry becomes the active location. Under `PAY_AFTER`/no gate, the lab QueueEntry may be active immediately. The entries coexist with only one `IN_SERVICE` at any instant; patient added to the clinician's "Awaiting results" list; a patient-facing slip can be printed showing where to go (cashier/lab).
**Alt** (a) No open orders → the clinician must choose a reason (`AWAITING_PROCEDURE`, `AWAITING_PAYMENT`, `PATIENT_STEPPED_OUT`) and the parked state still holds. (b) Clinician parks and goes off shift → the patient remains on a **department-level** awaiting-results list so any clinician can pick up (with takeover, ENC-022).
**ENC-016-AC01** GIVEN an encounter with 3 ordered tests WHEN the clinician parks it THEN the encounter is `AWAITING_RESULTS`, unsigned, fully editable on resume, and appears in the clinician's "Awaiting results" list with an elapsed timer.
**ENC-016-AC02** GIVEN parking THEN no diagnosis, prescription or invoice finalisation is required.
**ENC-016-AC03** GIVEN parking THEN the patient remains counted as present in the facility (REP-002).
**ENC-016-AC04** GIVEN the clinician logs out THEN the parked encounter persists and reappears at next login.
**ENC-016-AC05** GIVEN a parked encounter THEN attempting to sign it while orders are non-terminal produces a confirmation prompt (ENC-018), not a silent block.
**Perm** `encounter.update`.
**Data** `Encounter.state`, `QueueEntry`, audit.
**Audit** Park with reason and referenced orders.
**Err** Parking with zero orders and no reason → 400.
**UI** Prominent "Send for investigations" primary action next to Save; confirmation shows what the patient must do next.
**Dep** LAB-002, QUE-006.
**OOS** Auto-park on order placement (deliberate: the clinician decides).
**Test** Journey B end-to-end.

**ENC-017 · Sign / finalise the encounter · V1 · P0 · `CLINICIAN`,`MIDWIFE` (never nurses, never admins)**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE` (never nurses, never admins)
**Story** As a clinician I want to sign my note so it becomes the legal, immutable record of the consultation.
**Why** Record integrity, medico-legal defensibility, and the trigger for downstream handoffs.
**Pre** Normal Sign action: Encounter `OPEN` or `RESULTS_READY`, user is the author (or has taken over), required minimum content present. The only direct signing path from `AWAITING_RESULTS` is the explicit ENC-018 "Sign now" action.
**Trig** Clinician clicks Sign.
**Flow** (1) Server validates minimum content: ≥1 presenting complaint, allergy status explicitly captured/reviewed (active allergies, NKA, or UNKNOWN), ≥1 diagnosis (working or final) **or** an explicit "no diagnosis — reason" entry, and a disposition (DX-006). (2) Confirmation dialog summarising what will become immutable and listing any non-terminal orders. (3) On confirm: `Encounter SIGNED` with `signed_by`, `signed_at`, provider name/cadre/licence snapshot, content hash (AUD-003), `version=1`. (4) Downstream events fire: prescriptions `DRAFT → ACTIVE` (RX-005), procedure orders released to the treatment room, and queue entry `COMPLETED` with onward routing chosen by the clinician (pharmacy/cashier/exit). Charges are created by their source events under BIL-001; signing never creates a second consultation charge.
**Alt** (a) Non-terminal lab orders exist → the decision is governed **entirely by ENC-018**: "Park and wait for results" or "Sign now — results will be added as an addendum"; ENC-017 itself offers no independent sign-anyway path. (b) Minimum content missing → 400 with a checklist of what is missing. (c) The consultation charge is unpaid under `PAY_AFTER` → signing proceeds; the invoice remains outstanding.
**ENC-017-AC01** GIVEN an encounter missing a diagnosis WHEN sign is attempted THEN it is rejected with `DIAGNOSIS_REQUIRED` and the note remains editable.
**ENC-017-AC02** GIVEN a valid encounter WHEN signed THEN all clinical fields become read-only via the API (any PATCH returns 409 `RECORD_SIGNED`), a content hash is stored, and the signed note is printable with the provider's name, cadre and licence number.
**ENC-017-AC03** GIVEN signing THEN any `DRAFT` prescription for that encounter becomes `ACTIVE` and appears in the pharmacy queue within 15 seconds.
**ENC-017-AC04** GIVEN signing with an outstanding lab order through ENC-018 THEN the encounter is marked `signed_with_pending_orders=true`.
**ENC-017-AC05** GIVEN signing THEN an audit event records actor, timestamp, content hash and the downstream events triggered.
**ENC-017-AC06** GIVEN a chargeable consultation already charged at check-in THEN signing creates no second consultation line.
**ENC-017-AC07** GIVEN two sign requests with the same idempotency key THEN the encounter is signed once and no duplicate prescriptions are activated.
**Perm** `encounter.sign` (`CLINICIAN`,`MIDWIFE` only).
**Data** `Encounter` (state, signature snapshot, hash), `Prescription`, `Invoice`, `QueueEntry`.
**Audit** High-value; hash retained.
**Err** Signing an already-signed encounter (409); signing after visit closure → 409 `VISIT_CLOSED` — the encounter, its queue entry and any draft prescriptions are unchanged, no activation and no downstream fan-out occurs (the only post-closure clinical activity is the defined LAB-023/addendum workflow; visit reopening is not defined in V1); expired, missing, or uncertain clinical credential → signing is blocked (default-deny Product Spec safety outcome while OD-04 remains OPEN; no legal conclusion).
**UI** Sign is visually distinct and requires explicit confirmation; the dialog is a checklist, not a wall of text.
**Dep** DX-001, DX-002, DX-006, RX-005, REC-001, BIL-001, AUD-003. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Cryptographic e-signature with personal keys, co-signing (P2).
**Test** Immutability enforcement at API level; downstream event fan-out; idempotent sign.

**ENC-018 · Sign with pending investigations (explicit choice) · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**Story** As a clinician I want a clear choice between parking and signing when results are still pending, because sometimes I treat empirically and the result is for follow-up.
**ENC-018-AC01** GIVEN non-terminal blocking investigation orders exist WHEN Sign is clicked — whether the encounter is currently `OPEN` or `AWAITING_RESULTS` — THEN the ENC-018 dialog governs the decision and lists each pending test with exactly two actions: "Park and wait for results" or "Sign now — results will be added as an addendum" (neither preselected). **Path A — `OPEN` + Park:** as one consistent product outcome `OPEN → AWAITING_RESULTS` and consultation entry `IN_SERVICE → ON_HOLD(AWAITING_RESULTS)` (executing ENC-016); lab/payment routing proceeds normally. **Path B — `OPEN` + Sign now:** as one consistent product outcome `OPEN → SIGNED` with `signed_with_pending_orders=true` and consultation entry `IN_SERVICE → COMPLETED` with completion reason `SIGNED_WITH_PENDING_RESULTS`; items remain active; the visit may later close `CLOSED(PENDING_RESULTS)` subject to REC-012. **Path C — `AWAITING_RESULTS` + Sign now:** `AWAITING_RESULTS → SIGNED` without a fake resume to `OPEN` (and never via `ON_HOLD → IN_SERVICE → COMPLETED`), sets `signed_with_pending_orders=true`, leaves the lab order active, and **as one consistent product outcome completes the held consultation queue entry** `ON_HOLD → COMPLETED` with completion reason `SIGNED_WITH_PENDING_RESULTS` — the entry is terminal, never becomes `READY_TO_RESUME`, and is not revived when results later release (LAB-023 applies instead). Only then may the visit close `CLOSED(PENDING_RESULTS)`, subject to REC-012's remaining conditions. **Path D — `AWAITING_RESULTS` + Wait:** the encounter stays `AWAITING_RESULTS` and the entry `ON_HOLD` toward `READY_TO_RESUME` — the clinician choices remain distinct. On release the result attaches to the encounter as an addendum with a notification to the signer (LAB-023); the visit is flagged `POST_CLOSURE_ACTIVITY` as already specified — the visit, the signed encounter and the completed queue entry are never reopened or mutated.
**Dep** ENC-016, ENC-017, LAB-023.
**Test** Both branches produce correct downstream states. Mandatory tests: (1) encounter `AWAITING_RESULTS` + consultation entry `ON_HOLD` + lab entry `COMPLETED` + item `SAMPLE_COLLECTED` → "Sign now" → encounter `SIGNED` with `signed_with_pending_orders=true`, consultation entry `COMPLETED(SIGNED_WITH_PENDING_RESULTS)`, item still `SAMPLE_COLLECTED`, visit passes the queue precondition of REC-012 and closes `CLOSED(PENDING_RESULTS)`; a later release leaves the encounter `SIGNED`, the visit `CLOSED(PENDING_RESULTS)`, the entry `COMPLETED`, and triggers LAB-023 only. (2) encounter `OPEN` + blocking item + Sign → the same dialog: "Park" yields `AWAITING_RESULTS` + `ON_HOLD`; "Sign now" yields `SIGNED` + `IN_SERVICE → COMPLETED(SIGNED_WITH_PENDING_RESULTS)` directly.

**ENC-019 · Void an encounter created in error · V1 · P1 · `SUPERVISOR`; secondary `CLINICIAN`**
**Release** V1
**Epic** ENC
**Priority** P1
**Persona** `SUPERVISOR`; secondary `CLINICIAN`
**Story** As a supervisor I want to void an encounter opened on the wrong patient so the wrong chart isn't polluted.
**Pre** Encounter exists.
**Flow** Before any void, the product lists every related non-terminal LabOrderItem; the Encounter cannot become `VOIDED` until each is already resolved through LAB-022. For the exceptional signed path it additionally lists every still-actionable unhanded prescription, undispensed remainder, pharmacy QueueEntry, and provisional Dispense, which must already be non-actionable through RX-009 and DSP-005 as applicable. The void action never invents authority for its actor to perform a separately permissioned cancellation. Once clear: void with mandatory reason (min 20 chars) → state `VOIDED` → content hidden from the clinical timeline but retained in full for audit → related draft prescriptions cancelled, unbilled charges voided, released lab results **not** deleted but detached and flagged for review.
**Alt** Signed encounter → voiding requires `SUPERVISOR` + reason, resolved downstream blockers, and produces a visible "VOIDED" watermark on any reprint; the record is never physically deleted. Released results, paid financial history, and already handed-over medicines/stock movements remain preserved and use LAB-017/PAY-008/DSP-016 separately where correction is required.
**ENC-019-AC01** GIVEN a voided encounter THEN it does not appear in the patient's clinical history by default, is retrievable via an "include voided" filter by authorised roles, and is excluded from diagnosis and visit statistics.
**ENC-019-AC02** GIVEN voiding THEN the audit stores the full prior content hash, the reason and the actor.
**ENC-019-AC03** GIVEN a voided encounter with a paid invoice or already delivered/handed-over downstream work THEN the payment and delivered clinical, laboratory, dispense, and stock records are untouched by encounter voiding and their supplied correction paths must be handled separately. GIVEN any Encounter has a related non-terminal LabOrderItem, or a signed Encounter has a related still-actionable unhanded prescription remainder, pharmacy QueueEntry, or provisional Dispense, THEN voiding is refused with `PREREQUISITE_MISSING` and the exact blocker list; no active wrong-record work is silently orphaned.
**Perm** `encounter.void`.
**Err** Unresolved non-terminal lab or actionable unhanded prescription/pharmacy work → `PREREQUISITE_MISSING` with exact blockers; wrong-patient encounters that already drove physical handover → dispense reversal is a separate manual process (DSP-016), not an automatic consequence of encounter voiding.
**Test** Statistics exclusion; audit completeness; every Encounter void is refused while a related non-terminal lab blocker remains, and signed void is additionally refused until RX-009/DSP-005 prescription/pharmacy blockers are non-actionable; a concurrent downstream commit forces refresh; released/paid/handed-over history is preserved.

**ENC-020 · View a signed encounter · V1 · P0 · `CLINICIAN`,`MIDWIFE`,`SUPERVISOR`; limited others**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`,`SUPERVISOR`; limited others
**ENC-020-AC01** GIVEN a signed encounter THEN it renders read-only with the full note, orders and their results, diagnoses, prescriptions, provider identity snapshot, signed timestamp and version number, plus any addenda in chronological order.
**ENC-020-AC02** GIVEN a nurse or pharmacist opens it THEN they see only the sections their capabilities allow (pharmacist: diagnoses + prescriptions + allergies; nurse: vitals + instructions), enforced in the API payload.
**ENC-020-AC03** GIVEN any view THEN exactly one access audit event is written with `category=PHI_READ` and `action=PATIENT_RECORD_VIEWED`.
**Perm** `encounter.read` variants.
**Dep** AUD-001. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Per-role payload assertions.

**ENC-021 · Clinician's personal worklists · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**Story** As a clinician I want my own dashboard of who is waiting, who is with me, who is awaiting results and what is unsigned, so nothing falls through.
**Why** The clinician's home screen and the primary anti-dead-end mechanism.
**ENC-021-AC01** GIVEN a clinician signs in THEN their home shows four counted lists: **Waiting for me** (queue), **In progress** (open encounters), **Awaiting results** (encounters in `AWAITING_RESULTS`), and **Ready to review** (encounters in `RESULTS_READY`), plus **Unsigned** (encounters `OPEN`/`RESULTS_READY` older than 24 hours).
**ENC-021-AC02** GIVEN a result is released THEN the "Awaiting results" row's progress badge updates within 30 seconds ("2 of 3 results ready"); the patient moves to "Ready to review" only when ALL blocking dependencies are terminal (LAB-018).
**ENC-021-AC03** GIVEN an encounter has been unsigned for more than 24 hours THEN it appears in the "Unsigned" list and on the supervisor dashboard (REP-015).
**ENC-021-AC04** GIVEN a clinician with no patients THEN each list shows an explicit zero state.
**Perm** `encounter.read` (own) + `queue.read`.
**Dep** QUE-006, LAB-018, REP-015. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Badge transition timing; 24-hour unsigned rule.

**ENC-022 · Transfer or take over an encounter · V1 · P1 · `SUPERVISOR`,`CLINICIAN`**
**Release** V1
**Epic** ENC
**Priority** P1
**Persona** `SUPERVISOR`,`CLINICIAN`
**Story** As a clinician taking over from a colleague who has gone off shift, I want to continue their unsigned encounter so the patient isn't restarted.
**Pre** Encounter non-terminal; original author unavailable or consenting.
**Flow** Request takeover with reason → encounter's `current_provider` changes while `created_by` is preserved → both providers are recorded on the note and on the print ("Started by Dr A, completed by Dr B") → the new provider signs. Each note line retains its own author ID.
**ENC-022-AC01** GIVEN a takeover THEN the encounter ID is unchanged, all content is preserved, and the printed note names both providers with their roles and times.
**ENC-022-AC02** GIVEN a takeover without a reason THEN it is rejected.
**ENC-022-AC03** GIVEN a takeover THEN the original author retains read access and is notified in their worklist.
**ENC-022-AC04** GIVEN a signed encounter THEN takeover is not possible (use addendum, ENC-023).
**Perm** `encounter.takeover` (`SUPERVISOR`, or `CLINICIAN` when the author's session has been inactive for a configured period).
**Audit** High-value.
**Dep** USR-004, QUE-013. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Dual-provider print.

**ENC-023 · Amend a signed encounter (addendum) · V1 · P0 · `CLINICIAN` (author); secondary `SUPERVISOR`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN` (author); secondary `SUPERVISOR`
**Story** As a clinician I want to add a correction or new information to a signed note without altering the original, so the record stays truthful.
**Why** Real clinical need + legal integrity.
**Pre** Encounter `SIGNED`.
**Trig** New information, error found, late result.
**Flow** Create an addendum: type (`CORRECTION`|`ADDITIONAL_INFORMATION`|`LATE_RESULT`|`CLARIFICATION`), text, mandatory reason → addendum signed separately with its own timestamp and hash → encounter `version` increments; the original text remains visible and unaltered.
**Alt** Addendum by a non-author → permitted for `SUPERVISOR` with reason; the addendum is attributed to them, not to the original author.
**ENC-023-AC01** GIVEN a signed encounter WHEN an addendum is added THEN the original content is byte-identical and its hash still validates, the addendum appears below the original with its own author, timestamp and reason, and the encounter version becomes 2.
**ENC-023-AC02** GIVEN a printed note after amendment THEN it shows the original content followed by all addenda in order, each clearly labelled.
**ENC-023-AC03** GIVEN an attempt to PATCH the original signed fields THEN 409 `RECORD_SIGNED` regardless of role.
**ENC-023-AC04** GIVEN an addendum THEN a high-value audit event is written.
**Perm** `encounter.amend`.
**Data** `EncounterAddendum`, `Encounter.version`.
**Audit** High-value non-PHI metadata with version references and hashes; addendum text remains only in the signed domain record.
**Err** Addendum spam; addenda on voided encounters (blocked).
**UI** Amend button on the signed view; the dialog states plainly that the original will remain visible.
**Dep** AUD-003, AUD-008, LAB-023. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Retracting an addendum (add another).
**Test** Hash-validation-after-amendment test.

**ENC-024 · Print / export the consultation note · V1 · P0 · `CLINICIAN`**
**Release** V1
**Epic** ENC
**Priority** P0
**Persona** `CLINICIAN`
**ENC-024-AC01** GIVEN a signed encounter WHEN an actor with both `encounter.read` for that Encounter and `encounter.print` prints it THEN the document contains the facility header (TEN-003), patient identifiers, visit date, triage vitals, full clerking content, diagnoses, investigations with results (if released), treatment plan, prescriptions, follow-up, provider name/cadre/licence, signature timestamp and version, plus a "Page X of Y"; printing never expands the actor's existing clinical read scope.
**ENC-024-AC02** GIVEN an unsigned encounter WHEN an actor with the same applicable clinical read authority prints it THEN the document is watermarked "DRAFT — NOT SIGNED" and the action is audited.
**ENC-024-AC03** GIVEN a reprint THEN it is audited with actor and time (AUD-009); GIVEN a `RECEPTIONIST` who lacks the applicable `encounter.read` authority THEN print/export is denied and no full-note content or generated document is returned.
**Perm** `encounter.print` **and** applicable `encounter.read`; `RECEPTIONIST` is not granted clinical read or full-note print/export authority by the reception role.
**Dep** TEN-003, RCP-003, RCP-004. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** PDF email/WhatsApp delivery.
**Test** Snapshot of A4/A5 layouts; draft watermark; permission/payload test proving a receptionist token cannot obtain or print/export the full consultation note.

---
**Source epic context — Laboratory Orders and Results**

**Source rationale — Why the V1 laboratory statuses are what they are**

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


---

### Epic LAB — Laboratory Orders and Results

**LAB-001 · Laboratory test catalogue · V1 · P0 · `FACILITY_ADMIN`; secondary `LAB_TECH`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `FACILITY_ADMIN`; secondary `LAB_TECH`
**Story** As an administrator I want to define the tests we offer, with their analytes and reference ranges, so results are structured and consistently reported.
**Pre** Lab module enabled.
**Trig** Setup.
**Flow** Create `LabTestDefinition`: name, short code, specimen type (blood/urine/stool/sputum/swab/other), container/tube, method (optional), result type (`NUMERIC`, `CODED`, `TEXT`, `PANEL`), turnaround target, linked `Service` for pricing (CAT-001), active flag. For `PANEL`, define ordered analytes each with their own result type, unit, decimal places and reference ranges. Ranges may be defined by sex and age band, plus a free-text reference note.
**Alt** Seed a starter catalogue for a Ugandan small lab (Malaria RDT, Malaria BS, CBC/FBC panel, Hb, blood group & Rh, RBS/FBS, widal, H. pylori, HIV rapid, urinalysis panel, urine HCG, stool routine, Hep B surface antigen, RPR/syphilis, sickling test, ESR, LFTs, RFTs, urea/creatinine) with editable defaults.
**LAB-001-AC01** GIVEN a `PANEL` test with 8 analytes THEN result entry presents exactly those 8 fields in the defined order with their units.
**LAB-001-AC02** GIVEN a numeric analyte with a range 4.0–11.0 ×10⁹/L THEN entering 13.2 stores the value and flags it `HIGH` **without any interpretive text**.
**LAB-001-AC03** GIVEN sex- or age-specific ranges THEN the range applied is selected from the patient's sex and age at the time of the result and the applied range is stored on the result.
**LAB-001-AC04** GIVEN a test with no linked priced service THEN it cannot be ordered and an admin setup warning is shown.
**LAB-001-AC05** GIVEN a catalogue change THEN previously released results retain the ranges and units captured at release.
**Perm** `lab.catalogue.manage`.
**Data** `LabTestDefinition`, `LabAnalyte`, `LabReferenceRange`.
**Audit** Definition changes.
**Err** Changing a unit after results exist → new version of the definition; old results unaffected.
**UI** Test list with panel expansion; range editor with sex/age bands.
**Dep** CAT-001. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** LOINC coding, analyser interfacing, quality-control workflows.
**Test** Range-selection-by-demographics; snapshot immutability.

**LAB-002 · Clinician orders investigations · V1 · P0 · `CLINICIAN`,`MIDWIFE`; secondary `LAB_TECH`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`; secondary `LAB_TECH`
**Story** As a clinician I want to order one or more tests from inside the encounter so the lab knows exactly what to do and for whom.
**Pre** Encounter `OPEN`/`RESULTS_READY`; lab module enabled; `lab.order.create`.
**Trig** Clinician opens the Investigations tray.
**Flow** Search/select tests (multi-select, with a facility "frequently ordered" shortlist) → set priority per order (`ROUTINE`|`URGENT`) → optional clinical notes to the lab (free text, e.g. "on antimalarials since yesterday") → optional required-by time for urgent → confirm → one `LabOrder` (items in state `ORDERED`) with n `LabOrderItem`s, linked to the encounter, visit and patient.
**Alt** (a) Duplicate test already ordered in this visit and not cancelled → warn "CBC already ordered 20 minutes ago (status: sample collected)" and require confirmation. (b) Test's service is not priced → not orderable. (c) Lab module disabled → tray hidden and API 403.
**LAB-002-AC01** GIVEN a patient with an open encounter and a clinician with `lab.order.create` WHEN the clinician orders a CBC THEN a `LabOrder` is created **linked to the existing encounter**, the encounter remains `OPEN` and unsigned, the laboratory work queue displays the order, the clinician may leave the encounter without signing it, and the patient appears in the clinician's "Awaiting results" state once parked (ENC-016).
-
**LAB-002-AC02** GIVEN three tests ordered together THEN one order with three items is created, each item independently trackable.
-
**LAB-002-AC03** GIVEN priority `URGENT` THEN the order sorts above routine orders in the lab queue and is visually marked.
-
**LAB-002-AC04** GIVEN ordering THEN a charge event is emitted per orderable item (LAB-004) exactly once, even on retry with the same idempotency key.
-
**LAB-002-AC05** GIVEN a signed encounter THEN new orders cannot be added to it (a new encounter or an addendum-linked order is required — OD-07).
**Perm** `lab.order.create` (`CLINICIAN`,`MIDWIFE`; **not** nurses in V1 — see OD-21).
**Data** `LabOrder`, `LabOrderItem`, charge events, audit.
**Audit** Order creation referencing `LabOrder`/`LabOrderItem` IDs and version hashes, priority and ordering actor; ordered test details remain in the protected domain records.
**Err** Ordering after the patient has left; ordering a test whose specimen the facility can't collect (catalogue should be curated).
**UI** Tray with search, shortlist chips, selected-items list with per-item remove, single confirm.
**Dep** ENC-001, LAB-001, LAB-004.
**OOS** Order sets/protocols, standing orders, external lab referral orders (LAB-025 is P2).
**Test** Encounter linkage and open-state assertions (the canonical Journey-B acceptance test).

**LAB-003 · Order priority and clinical notes to the lab · V1 · P1 · `CLINICIAN`**
**Release** V1
**Epic** LAB
**Priority** P1
**Persona** `CLINICIAN`
**LAB-003-AC01** GIVEN priority `URGENT` THEN the lab queue shows the order at the top with an urgent marker and the target turnaround from the catalogue.
**LAB-003-AC02** GIVEN clinical notes THEN they are visible to the lab technician on the work item and are printed on the internal worksheet, but are **not** printed on the patient-facing report unless configured.
**Data** `LabOrder.priority`, `clinical_notes`.
**Dep** LAB-002.
**Test** Sort and visibility.

**LAB-004 · Charge generation on order · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `SYSTEM`
**Story** As a facility I want ordering a test to create the charge automatically so we never do unbilled lab work.
**Flow** On order creation, for each item resolve the linked service and facility price → create invoice lines on the current Visit's Invoice with `source=LAB_ORDER_ITEM` and `source_id`. For a `LAB_ONLY` Visit created by REC-001, no consultation line exists, and if no Visit-linked Invoice exists the charging event creates it under BIL-001/BIL-002; no standalone Invoice is created for this `LAB_ONLY` path. The invoice is then `ISSUED`. For `LABORATORY=PAY_BEFORE`, order/item creation and its required charge lines are a single product outcome: failure to create a required line fails the initiating operation and leaves no actionable item.
**LAB-004-AC01** GIVEN three ordered tests THEN three invoice lines exist with the current facility prices snapshotted, referencing the specific order items.
**LAB-004-AC02** GIVEN the same order submitted twice with one idempotency key THEN three lines exist, not six (uniqueness rule on `(invoice, source_type, source_id)` — BIL-013).
**LAB-004-AC03** GIVEN `LABORATORY=PAY_BEFORE` and required charge creation fails THEN the order operation returns an explicit billing/setup error and no actionable `LabOrderItem` or lab worklist entry exists.
**LAB-004-AC04** GIVEN an item is cancelled before collection THEN its invoice line is voided if unpaid, or flagged for refund/credit if paid (LAB-022).
**LAB-004-AC05** GIVEN a `LAB_ONLY` walk-in with no Encounter THEN the laboratory charges attach to that `LAB_ONLY` Visit's Invoice; if the Visit has no Invoice yet, the Visit-linked Invoice is created as part of the authoritative charging path; no standalone Invoice is created for this `LAB_ONLY` path.
**Data** `InvoiceLine`.
**Audit** Charge creation with source.
**Dep** BIL-001, BIL-013.
**Test** Duplicate-line constraint; cancellation refund path.

**LAB-005 · Payment gate for laboratory work · V1 · P0 · `SYSTEM`; secondary `CASHIER`,`LAB_TECH`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `SYSTEM`; secondary `CASHIER`,`LAB_TECH`
**Story** As a facility with a pay-before rule I want the lab to be unable to process unpaid tests, while still seeing them.
**Flow** If `LABORATORY=PAY_BEFORE`: a `LAB_ONLY` request-capture/intake surface before `LabOrder` creation is distinct from the patient-facing LAB QueueEntry and is not an `SM-01` QueueEntry or collection authority. Before qualifying payment, waiver, or valid override release, no specimen collection is permitted and no patient-facing LAB collection QueueEntry exists. For an existing order, item `ORDERED → AWAITING_PAYMENT`; the laboratory **worklist** shows it in a separate "Awaiting payment" section, not actionable. This worklist item is not a patient-facing LAB QueueEntry. The clinician's consultation entry remains `ON_HOLD(AWAITING_RESULTS)` where an Encounter-based order applies, and the patient is routed to a cashier `QueueEntry=WAITING`. When related invoice lines are fully paid, waived, or validly overridden, the items move to `READY_FOR_COLLECTION`, the cashier entry completes, and a patient-facing `QueueEntry(LAB)=WAITING` is created. If `PAY_AFTER`/`NO_GATE`: items go straight to `READY_FOR_COLLECTION` and the lab QueueEntry may be created after order/gate evaluation.
**Alt** Override by a user with `billing.gate.override` (reason mandatory) moves items to `READY_FOR_COLLECTION` while the charge stays outstanding.
**LAB-005-AC01** GIVEN `PAY_BEFORE` and an unpaid lab charge WHEN the technician attempts to record collection THEN the action is refused with `PAYMENT_REQUIRED` and the outstanding amount is displayed.
**LAB-005-AC02** GIVEN `PAY_BEFORE` before payment THEN the unpaid item appears only in the non-actionable lab worklist, the cashier QueueEntry is `WAITING`, and no patient-facing LAB QueueEntry exists.
**LAB-005-AC03** GIVEN the cashier records qualifying payment for those lines THEN the items become `READY_FOR_COLLECTION`, the cashier entry becomes `COMPLETED`, and `QueueEntry(LAB)=WAITING` is created within 15 seconds.
**LAB-005-AC04** GIVEN a partial payment covering only 2 of 3 tests THEN exactly those 2 items become collectable and the third remains `AWAITING_PAYMENT` (allocation per PAY-005).
**LAB-005-AC05** GIVEN a required gated charge line is absent THEN the item cannot become actionable.
**LAB-005-AC06** GIVEN an override THEN the item becomes collectable, the charge remains outstanding, and the audit records the actor and reason.
**Data** Item state, `gate_policy_at_charge`.
**Audit** Gate transitions and overrides.
**Err** Payment reversed after collection → the item continues (work already done) and the invoice returns to outstanding; flagged on REP-008. Payment reversed **before** collection under `PAY_BEFORE` → the item returns `READY_FOR_COLLECTION → AWAITING_PAYMENT`, the patient-facing Lab queue entry is cancelled (reason `PAYMENT_REVERSED` — including the `IN_SERVICE`-but-no-specimen-yet case, where collection is blocked immediately and any unsaved collection form is discarded), a cashier entry is created, and no active Lab entry remains until repayment (PAY-012).
**Dep** TEN-006, PAY-012. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Partial-payment line-level gating.

**LAB-006 · Derived order status · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `SYSTEM`
**LAB-006-AC01** LabOrder status is derived only.
**LAB-006-AC02** GIVEN all items `CANCELLED` THEN the order is `CANCELLED`.
**LAB-006-AC03** GIVEN all items terminal and at least one is `RELEASED` THEN the order is `COMPLETED`, including `RELEASED + CANCELLED` and `RELEASED + RELEASED`.
**LAB-006-AC04** GIVEN at least one item is `RELEASED` and at least one item remains non-terminal THEN the order is `PARTIALLY_RELEASED`, including `RELEASED + SAMPLE_COLLECTED`.
**LAB-006-AC05** GIVEN no item is released and at least one remains non-terminal THEN the order uses the pending/active derived presentation.
**LAB-006-AC06** GIVEN `ORDERED + SAMPLE_COLLECTED` THEN it uses that pending/active presentation.
**LAB-006-AC07** GIVEN mixed states THEN the worklist shows per-item states, never a misleadingly aggregated single state. `SAMPLE_REJECTED` is non-terminal and is not a readiness outcome.
**Data** Derived (computed, not stored, or stored as a denormalised cache updated in the single product outcome).
**Test** All state-combination permutations.

**LAB-007 · Laboratory work queue · V1 · P0 · `LAB_TECH`,`LAB_VERIFIER`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `LAB_TECH`,`LAB_VERIFIER`
**Story** As a lab technician I want a prioritised list of work so I know what to do next and nothing is missed.
**LAB-007-AC01** GIVEN orders exist THEN the laboratory worklist shows sections: **Awaiting payment** (visible, not actionable), **To collect** (`READY_FOR_COLLECTION`), **Collected / in bench** (`SAMPLE_COLLECTED`), **To verify** (`RESULT_ENTERED`), **Rejected / action needed** (`SAMPLE_REJECTED`). These are LabOrderItem work states, not patient QueueEntry states or physical locations.
**LAB-007-AC02** GIVEN each row THEN it shows patient name and number, test(s), priority, ordering clinician, order time and elapsed time.
**LAB-007-AC03** GIVEN an urgent order THEN it sorts first within its section.
**LAB-007-AC04** GIVEN a technician without `lab.result.verify` THEN the "To verify" section is visible but its actions are disabled with an explanatory tooltip.
**LAB-007-AC05** GIVEN 200 items in a day THEN the queue paginates and meets both NFR-01 and NFR-02 targets: API operations ≤ 400 ms p95 and an end-to-end rendered usable state ≤ 2 s p95 under the 3G-equivalent profile.
**Perm** `lab.queue.read`.
**Dep** LAB-002, LAB-005.
**Test** Section membership per state.

**LAB-008 · Record sample collection / receipt · V1 · P0 · `LAB_TECH`; secondary `NURSE`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `LAB_TECH`; secondary `NURSE`
**Story** As a lab technician I want to record that I have the specimen so custody is clear and the clock starts.
**Pre** Item `READY_FOR_COLLECTION`.
**Flow** Verify patient identity (name + patient number read-back prompt) → select items collected (may be a subset) → record specimen type (defaulted from the catalogue), collection time (defaults to now, editable within limits), collector → generate a specimen ID per item or per container → print a specimen label if a printer exists → items `SAMPLE_COLLECTED`. Once the patient-facing collection/receipt interaction is complete, the active `QueueEntry(LAB)` becomes `COMPLETED`; bench processing continues through the items independently. If another specimen is immediately due, the lab entry may remain `IN_SERVICE` until that collection episode ends; if the patient must return later, a new patient-facing lab action is created through the existing recollection workflow.
**Alt** Sample collected by a nurse in the treatment room → the nurse records collection (with `lab.sample.collect`) and the lab records receipt; both timestamps are stored. Patient not present → cannot collect.
**LAB-008-AC01** GIVEN two of three items collected THEN only those two become `SAMPLE_COLLECTED` and the third remains `READY_FOR_COLLECTION`.
**LAB-008-AC02** GIVEN collection THEN a unique specimen ID is generated per facility per day and printed on the label with patient name, number, test, date/time and collector initials.
**LAB-008-AC03** GIVEN the collection/receipt interaction ends THEN the patient-facing LAB QueueEntry is `COMPLETED` even while a collected item remains in bench processing.
**LAB-008-AC04** GIVEN an attempt to collect an `AWAITING_PAYMENT` item THEN it is refused (LAB-005).
**LAB-008-AC05** GIVEN payment is reversed mid-interaction while the entry is `IN_SERVICE` and no specimen has been recorded for the affected items THEN collection is refused with `PAYMENT_REQUIRED`, any unsaved collection form is discarded uncommitted, no `LabSpecimen` is created, and the entry is cancelled with reason `PAYMENT_REVERSED` (PAY-012/SM-01) — starting lab service alone is not the delivery boundary; the recorded specimen is.
**LAB-008-AC06** GIVEN collection THEN the audit records collector, time and specimen IDs.
**Perm** `lab.sample.collect`.
**Data** `LabSpecimen`, item state.
**Err** Wrong patient's sample → rejection/relabel path (LAB-009) plus an incident note; label printer offline → handwritten fallback with the ID displayed large on screen.
**UI** Read-back identity prompt is a required checkbox, not decorative.
**Dep** TEN-007. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Barcode scanning (P2), chain-of-custody signatures.
**Test** Partial collection; specimen ID uniqueness.

**LAB-009 · Reject a sample / unable to process · V1 · P0 · `LAB_TECH`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `LAB_TECH`
**Story** As a lab technician I want to record that a sample cannot be processed, with the reason, so the clinician knows and a recollection can happen.
**Why** Without this, the order silently dies and the patient waits forever.
**Pre** Item `SAMPLE_COLLECTED` (or `READY_FOR_COLLECTION` when the patient cannot provide a sample).
**Flow** Select item → reason (`HAEMOLYSED`, `INSUFFICIENT_VOLUME`, `CLOTTED`, `WRONG_CONTAINER`, `MISLABELLED`, `LEAKED`, `PATIENT_UNABLE_TO_PROVIDE`, `REAGENT_UNAVAILABLE`, `EQUIPMENT_DOWN`, `OTHER` + note) → item `SAMPLE_REJECTED` → the ordering clinician's worklist shows an alert; reception/nurse see a recollection task.
**Alt** Recollect → item returns to `READY_FOR_COLLECTION` with `recollection_count+1`, retaining the original order and **without a second charge** (unless the reason is patient-caused and facility policy says otherwise — OD-12); when the patient must return later, the completed prior lab QueueEntry is followed by the next patient-facing lab action. Cannot recollect → clinician or authorised supervisor cancels the item (LAB-022).
**LAB-009-AC01** GIVEN a rejected sample THEN the ordering clinician sees the rejection with its reason in their worklist within 30 seconds and the encounter remains `AWAITING_RESULTS` until the item is recollected and eventually `RELEASED`, or explicitly `CANCELLED`; `SAMPLE_REJECTED` alone never makes an encounter `RESULTS_READY`.
**LAB-009-AC02** GIVEN a rejection THEN the patient is **never** left with no next step: the item appears in the "Action needed" lab section and on the reception recollection list.
**LAB-009-AC03** GIVEN recollection THEN no duplicate invoice line is created.
**LAB-009-AC04** GIVEN rejection THEN the audit records the reason, actor and time.
**Perm** `lab.sample.reject`.
**Data** `LabOrderItem.rejection_*`, `recollection_count`.
**Err** Repeated rejections (>2) → flagged to the supervisor.
**UI** Reason list with a mandatory note for `OTHER`.
**Dep** LAB-018, LAB-022.
**Test** No-double-charge on recollection; dead-end prevention assertion.

**LAB-010 · Enter numeric and panel results · V1 · P0 · `LAB_TECH`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `LAB_TECH`
**Story** As a lab technician I want to type results into the exact fields the test defines so nothing is ambiguous.
**Pre** Item `SAMPLE_COLLECTED`; `lab.result.enter`.
**Flow** Open the item → the form renders the analytes from the catalogue with units and decimal precision → enter values → optional per-analyte comment → optional overall comment → save → item `RESULT_ENTERED`.
**LAB-010-AC01** GIVEN a CBC panel with 8 analytes THEN all 8 fields are shown with units, and saving with 6 filled is allowed only if the unfilled ones are explicitly marked "not done" (no silent blanks in a released report).
**LAB-010-AC02** GIVEN a value outside the sanity bounds for the analyte (e.g. Hb 250 g/dL) THEN the save is rejected with a range error.
**LAB-010-AC03** GIVEN a value outside the reference range THEN it is stored with a `HIGH`/`LOW` flag and rendered with a neutral marker; **no interpretation, no advice, no suggested action is displayed anywhere**.
**LAB-010-AC04** GIVEN the entering technician THEN their identity and the entry time are stored.
**LAB-010-AC05** GIVEN a result saved THEN it is **not** visible to the ordering clinician until released (LAB-015).
**Perm** `lab.result.enter`.
**Data** `LabResult` (v1), `LabResultAnalyteValue`.
**Audit** Result-version reference, changed field names, actor, timestamp and hash; raw values remain only in the LabResult domain record.
**Err** Decimal/comma confusion → strict numeric parsing with an explicit hint; unit mismatch.
**UI** Keyboard-driven grid, Enter moves to the next analyte, reference range shown greyed beside each field.
**Dep** LAB-001.
**OOS** Analyser import, delta checks, QC rules.
**Test** Not-done handling; invisibility before release.

**LAB-011 · Enter coded results · V1 · P0 · `LAB_TECH`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `LAB_TECH`
**LAB-011-AC01** GIVEN a test defined as `CODED` with options (e.g. Malaria RDT: `POSITIVE`/`NEGATIVE`/`INVALID`; Blood group: `A/B/AB/O` × `POSITIVE/NEGATIVE`) THEN the entry form presents exactly those options as a single-select and free text is not accepted in the coded field.
**LAB-011-AC02** GIVEN `INVALID` THEN a comment is mandatory.
**LAB-011-AC03** GIVEN a coded result THEN it prints as the option label and is countable in reports (REP-009).
**Data** `LabResult.coded_value`.
**Test** Option enforcement.

**LAB-012 · Enter text/descriptive results · V1 · P1 · `LAB_TECH`**
**Release** V1
**Epic** LAB
**Priority** P1
**Persona** `LAB_TECH`
**LAB-012-AC01** GIVEN a `TEXT` result type (e.g. stool microscopy, urinalysis microscopy description) THEN a structured-lite form with a free-text area up to 2000 characters is provided, optionally with facility-defined template phrases that insert editable text.
**LAB-012-AC02** GIVEN a text result THEN it prints preserving line breaks.
**Dep** LAB-010.
**Test** Long-text round trip.

**LAB-013 · Attach reference ranges and units to the stored result · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `SYSTEM`
**LAB-013-AC01** GIVEN a released result THEN the report displays the value, unit, and the reference range **as it was at the time of release**, and changing the catalogue afterwards does not alter historical reports.
**LAB-013-AC02** GIVEN a patient-specific range selection (by sex/age) THEN the applied range is stored on the result row.
**Data** Snapshot fields on `LabResultAnalyteValue`.
**Test** Catalogue-change immutability.

**LAB-014 · Save partial results within a panel · V1 · P1 · `LAB_TECH`**
**Release** V1
**Epic** LAB
**Priority** P1
**Persona** `LAB_TECH`
**LAB-014-AC01** GIVEN a panel where only some analytes are complete THEN the technician can save progress without moving the item to `RESULT_ENTERED`, and the queue shows it as "in entry" with the entering technician's name.
**LAB-014-AC02** GIVEN a partial save THEN the values are not visible to clinicians.
**LAB-014-AC03** GIVEN completion THEN the item transitions to `RESULT_ENTERED` in one explicit action.
**Dep** LAB-010.
**Test** Visibility boundary.

**LAB-015 · Verify and release a result · V1 · P0 · `LAB_VERIFIER`; secondary `LAB_TECH`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `LAB_VERIFIER`; secondary `LAB_TECH`
**Story** As the lab in-charge I want to check a result before the clinician can act on it, so we don't release a mistyped value.
**Why** The safety gate of the lab loop.
**Pre** Item `RESULT_ENTERED`; `lab.result.verify`.
**Trig** Verifier opens the "To verify" section.
**Flow** Review entered values against the reference ranges and any comments → either **Verify & release** (single action, default) or **Verify** then **Release** separately if the facility uses batch verification → item `VERIFIED → RELEASED` with verifier identity and timestamps → release event fires (LAB-018).
**Alt** Verifier rejects the entry → item returns to `SAMPLE_COLLECTED`/entry with a mandatory comment to the technician; the previous entry is retained as a non-released version.
**LAB-015-AC01** GIVEN a result in `RESULT_ENTERED` WHEN the verifier releases it THEN the item becomes `RELEASED`, the ordering clinician's encounter transitions toward `RESULTS_READY` (LAB-018), and the result becomes printable.
**LAB-015-AC02** GIVEN the entering technician lacks `lab.result.verify` THEN they cannot release, and the action is absent and API-refused.
**LAB-015-AC03** GIVEN a released result THEN it cannot be edited; corrections require an amended version (LAB-017).
**LAB-015-AC04** GIVEN verification THEN the generic audit records the verifier, timestamp, released result-version reference and content hash; the exact values remain in the immutable result version.
**LAB-015-AC05** GIVEN a rejected entry THEN the technician sees the rejection with the comment in their queue.
**Perm** `lab.result.verify`.
**Data** `LabResult.verified_by/at`, `released_at`, state.
**Audit** High-value.
**Err** Verifier releasing their own entry — permitted only under LAB-016.
**UI** Side-by-side entered values and ranges; single prominent Release action.
**Dep** LAB-010, LAB-018.
**Test** Author-cannot-self-release enforcement (unless LAB-016 is configured).

**LAB-016 · Single-technician facility configuration · V1 · P0 · `FACILITY_ADMIN`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `FACILITY_ADMIN`
**Story** As a small facility with one lab technician I need results to be releasable by the person who entered them, because there is nobody else.
**Why** Without this, the pilot lab stalls; with an unconfigured default, safety is silently lost.
**Flow** Facility setting `lab_allow_self_verification` (default **false**). When true, users holding both `lab.result.enter` and `lab.result.verify` may release their own entries; every such release is tagged `self_verified=true`.
**LAB-016-AC01** GIVEN the setting is false and a technician holding both capabilities WHEN they attempt to release their own entry THEN it is refused with `SELF_VERIFICATION_NOT_ALLOWED`.
**LAB-016-AC02** GIVEN the setting is true THEN release succeeds, the result record is marked `self_verified`, and the fact is included on the printed report footer and in REP-009.
**LAB-016-AC03** GIVEN the setting is changed THEN it is audited with actor and reason.
**Perm** `facility.policy.manage`.
**Audit** Setting change + each self-verified release.
**Dep** LAB-015.
**Test** Both configurations.

**LAB-017 · Correct or amend a released result · V1 · P0 · `LAB_VERIFIER`; secondary `SUPERVISOR`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `LAB_VERIFIER`; secondary `SUPERVISOR`
**Story** As the lab in-charge I want to correct a released result without erasing what the clinician already saw.
**Pre** Item `RELEASED`.
**Flow** Create a new result version with corrected values + mandatory reason → previous version retained and marked superseded → the item stays `RELEASED` but at version n+1 → **the ordering clinician is alerted explicitly** and, if the encounter is already signed, an addendum is created noting the corrected result (LAB-023).
**LAB-017-AC01** GIVEN a released Hb of 3.2 corrected to 13.2 THEN both versions are retained and visible, the report prints "AMENDED RESULT — supersedes version 1 released at [time]" with both values, and the clinician receives a high-visibility alert in their worklist that persists until acknowledged.
**LAB-017-AC02** GIVEN a signed encounter THEN an addendum is created automatically referencing the amendment (content authored by the system, attributed to the lab).
**LAB-017-AC03** GIVEN an amendment THEN the generic audit references both result versions/hashes and records actor and reason; the actual values remain in the LabResult version records.
**LAB-017-AC04** GIVEN a patient report was already printed THEN the reprint carries the amended marker and the print history shows both events.
**Perm** `lab.result.amend`.
**Data** `LabResult` versions.
**Audit** High-value.
**Err** Amending after the patient has been treated → alert must be unmissable; repeated amendments.
**UI** Red banner on the result; acknowledgement required by the clinician (recorded).
**Dep** LAB-023, AUD-008. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Acknowledgement persistence; print markers.

**LAB-018 · Result-ready signalling to the clinician · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `SYSTEM`
**Story** As the platform I want to tell the ordering clinician the moment results are usable, so the patient is called back promptly.
**Trig** A blocking item reaching a terminal state (`RELEASED` via LAB-015 or `CANCELLED` via LAB-022).
**Flow** On release: released items become immediately readable to authorised clinicians, with "n of m results ready" progress on the clinician's worklist. The encounter transitions `AWAITING_RESULTS → RESULTS_READY` and the held consultation queue entry `ON_HOLD → READY_TO_RESUME` **only when ALL blocking LabOrderItems referenced by the encounter hold are `RELEASED` or `CANCELLED` — across every referenced order**; completion of a subset of orders never triggers readiness; if the clinician is off shift, the patient also appears on the department-level ready list. Result release never completes a patient-facing LAB QueueEntry; that entry completed at the collection/receipt interaction (LAB-008).
**LAB-018-AC01** GIVEN an encounter awaiting three tests WHEN the first is released THEN the encounter remains `AWAITING_RESULTS` and the clinician's row shows "1 of 3 results ready" (partial visibility is permitted and results are readable immediately).
**LAB-018-AC02** GIVEN the last blocking item is released THEN within 30 seconds the encounter is `RESULTS_READY` and the patient appears in "Ready to review".
**LAB-018-AC03** GIVEN a hold referencing two orders (CBC released, blood culture pending) WHEN the CBC order alone is fully terminal THEN the encounter remains `AWAITING_RESULTS` — completion of a subset of orders never triggers readiness.
**LAB-018-AC04** GIVEN the last blocking item is instead `CANCELLED` THEN the encounter becomes `RESULTS_READY` with an indicator explaining why ("2 released, 1 cancelled").
**LAB-018-AC05** GIVEN `SAMPLE_REJECTED` THEN the encounter remains `AWAITING_RESULTS` until recollection reaches `RELEASED` or the item is explicitly `CANCELLED`.
**LAB-018-AC06** GIVEN the clinician resumes manually before all blocking results are terminal THEN the same encounter opens with its ID unchanged and the outstanding laboratory work continues normally (ENC-002/QUE-006).
**LAB-018-AC07** GIVEN a signed encounter THEN no state change occurs and LAB-023 applies instead.
**Data** `Encounter.state`, `QueueEntry.state`.
**Audit** State transitions with the triggering event.
**Err** Clinician deactivated → department-level fallback; multiple orders across two clinicians → each clinician is signalled for their own orders.
**Dep** ENC-016, QUE-006.
**Test** Partial vs full readiness (the subset-of-orders case must NOT trigger readiness); cancellation- and rejection-driven readiness including recollection-pending; early manual resume with the same encounter ID.

**LAB-019 · Clinician views results inside the encounter · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**LAB-019-AC01** GIVEN a resumed encounter with released results THEN the results appear inline in the Investigations section showing test, analyte, value, unit, reference range, flag, released time and verifier, without leaving the encounter.
**LAB-019-AC02** GIVEN an unreleased result THEN the clinician sees only the status (e.g. "sample collected 14:20"), never the unverified value.
**LAB-019-AC03** GIVEN previous results for the same test from earlier visits THEN a compact trend (last 3 values with dates) is shown for numeric analytes — values only, **no interpretation**.
**LAB-019-AC04** GIVEN the clinician views results THEN an access-audit event is written.
**Perm** `lab.result.read`.
**Dep** LAB-015, ENC-002.
**Test** Unreleased-value invisibility.

**LAB-020 · Print the laboratory report · V1 · P0 · `LAB_TECH`,`RECEPTIONIST`,`CLINICIAN`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `LAB_TECH`,`RECEPTIONIST`,`CLINICIAN`
**LAB-020-AC01** GIVEN released items WHEN printed THEN the report shows the facility header, patient identifiers, order date, specimen type and collection time, each test with values/units/ranges/flags, comments, the ordering clinician, the entering technician, the verifier and release timestamp, an amended marker if applicable, a self-verified marker if applicable, and a "results relate only to the specimen tested" footer.
**LAB-020-AC02** GIVEN unreleased items on the same order THEN they are listed as "pending" rather than omitted.
**LAB-020-AC03** GIVEN a reprint THEN it is audited.
**LAB-020-AC04** GIVEN a patient collecting results in person THEN the receptionist can print without seeing the clinician's notes (payload authorisation).
**Perm** `lab.result.print`.
**Dep** TEN-003, RCP-003, RCP-004. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Emailing/WhatsApping results.
**Test** Role-scoped print payload; A5/A4 snapshots.

**LAB-021 · Ageing and stuck-order monitoring · V1 · P0 · `LAB_TECH`,`SUPERVISOR`,`CLINICIAN`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `LAB_TECH`,`SUPERVISOR`,`CLINICIAN`
**Story** As a supervisor I want to see orders that are stuck so no patient is forgotten in the lab loop.
**Why** The explicit anti-dead-end guarantee.
**LAB-021-AC01** GIVEN an item in `AWAITING_PAYMENT` for more than 60 minutes THEN it appears on the reception/cashier "unpaid lab" list naming the patient and amount.
**LAB-021-AC02** GIVEN an item in `READY_FOR_COLLECTION` beyond its turnaround target THEN it is flagged in the lab queue and on the supervisor dashboard.
**LAB-021-AC03** GIVEN an item in `RESULT_ENTERED` for more than 60 minutes THEN it appears as "awaiting verification" on the supervisor dashboard.
**LAB-021-AC04** GIVEN any item non-terminal for more than 24 hours THEN it appears on a daily "stuck orders" report with the patient, ordering clinician, state and age.
**LAB-021-AC05** GIVEN a facility with zero stuck orders THEN the dashboard shows an explicit zero.
**Perm** `lab.queue.read`/`supervisor.dashboard`.
**Dep** QUE-011, REP-009. Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Clock-controlled ageing at each state.

**LAB-022 · Cancel an order or item · V1 · P0 · `CLINICIAN` (orderer), `SUPERVISOR`; secondary `LAB_TECH`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `CLINICIAN` (orderer), `SUPERVISOR`; secondary `LAB_TECH`
**LAB-022-AC01** GIVEN an item not yet collected WHEN the ordering clinician cancels it with a reason THEN the item is `CANCELLED`, its unpaid invoice line is voided, and the lab worklist removes it.
**LAB-022-AC02** GIVEN an item already collected WHEN cancellation is requested THEN it requires `SUPERVISOR` approval with a reason and the charge remains payable unless explicitly credited (BIL-010).
**LAB-022-AC03** GIVEN a paid item that is cancelled THEN an attributable CreditNote is created against the affected Invoice and original line/source; a full Payment reversal is used only when the entire Payment is wrong, otherwise any refundable credit uses a bounded Refund against the CreditNote with the original Payment/PaymentAllocation/Invoice context, leaving unrelated allocations, Invoices, and service gates unchanged; money is never silently retained or silently refunded.
**LAB-022-AC04** GIVEN a `SAMPLE_REJECTED` item that will not be recollected THEN clinician or authorised supervisor cancellation is required to reach `CANCELLED`.
**LAB-022-AC05** GIVEN cancellation of the last pending item THEN the encounter's awaiting-results dependency resolves (LAB-018).
**Perm** `lab.order.cancel`.
**Audit** Reason mandatory.
**Test** Financial consequence matrix (unpaid/paid × collected/not collected).

**LAB-023 · Late results after the encounter is signed · V1 · P0 · `SYSTEM`; secondary `CLINICIAN`**
**Release** V1
**Epic** LAB
**Priority** P0
**Persona** `SYSTEM`; secondary `CLINICIAN`
**Story** As a clinician who signed and sent the patient home, I want late results brought to my attention and attached to the record.
**LAB-023-AC01** GIVEN a signed encounter with a pending order WHEN the result is released THEN an addendum of type `LATE_RESULT` is attached to the encounter containing a reference to the result (not a rewrite of the note), the signing clinician receives a persistent "unreviewed result" item in their worklist, and the item remains until they acknowledge it.
**LAB-023-AC02** GIVEN the visit is already closed `PENDING_RESULTS` THEN it is flagged `POST_CLOSURE_ACTIVITY`; it is never silently reopened.
**LAB-023-AC03** GIVEN acknowledgement THEN the clinician may add a clinical addendum (ENC-023) and/or record a follow-up instruction for future APT integration, and the acknowledgement is audited with a timestamp; appointment creation is unavailable while APT authority remains UNSUPPLIED / OPEN / BLOCKED.
**LAB-023-AC04** GIVEN an abnormal-flagged late result THEN it is sorted to the top of the unreviewed list (a display order only — **no clinical interpretation**).
**LAB-023-AC05** GIVEN no acknowledgement within 48 hours THEN it appears on the supervisor dashboard.
**Data** `EncounterAddendum`, `ResultAcknowledgement`.
**Audit** Acknowledgement.
**Dep** ENC-018, ENC-023.
**Test** Persistence until acknowledged; supervisor escalation.

**LAB-024 · Walk-in / external-request lab order · V1 · P1 · `LAB_TECH`,`RECEPTIONIST`**
**Release** V1
**Epic** LAB
**Priority** P1
**Persona** `LAB_TECH`,`RECEPTIONIST`
**Story** As a lab technician I want to register a test for a patient who arrives with a request from elsewhere, so we can serve and charge them without a consultation.
**Pre** Active `LAB_ONLY` Visit in `OPEN` or `IN_PROGRESS`; actor is `LAB_TECH` or `RECEPTIONIST` with `lab.order.create.external`; laboratory module is enabled; selected tests are available and priced; supplied external-request fields satisfy LAB-024; no Encounter is required.
**Trig** Authorised external/walk-in request is captured for the active `LAB_ONLY` Visit.
**Flow** Capture the external/walk-in requested tests and create a `LabOrder` plus `LabOrderItem` records in `ORDERED` with `external_requester_name`, `external_facility` (free text) and no Encounter → remove/resolve the request-capture intake obligation → generate charges through LAB-004 on that `LAB_ONLY` Visit's Invoice → apply LAB-005 gate evaluation. For `PAY_BEFORE`, route to CASHIER first and create the patient-facing LAB QueueEntry only after `READY_FOR_COLLECTION`; for `PAY_AFTER`/`NO_GATE`, the LAB QueueEntry may be created after order/gate evaluation. Release makes the report printable; no Encounter does not mean no Visit, there is no clinician-resume step, and external requester/source data is retained.
**LAB-024-AC01** GIVEN an external order THEN it requires no encounter and the report prints "Requested by: [external requester]".
**LAB-024-AC02** GIVEN release THEN the patient/reception is notified via the reception "results ready for collection" list.
**LAB-024-AC03** GIVEN a walk-in order THEN charges follow the same gate policy on the `LAB_ONLY` Visit's Invoice under LAB-004; no standalone Invoice is created.
**Perm** `lab.order.create.external`.
**Dep** LAB-002, REC-004.
**OOS** Sending results back to the external facility electronically.
**Test** Encounter-free path integrity.

**LAB-025 · Refer a test to an external laboratory · V1 · P2 · `LAB_TECH`**
**Release** V1
**Epic** LAB
**Priority** P2
**Persona** `LAB_TECH`
**LAB-025-AC01** GIVEN a test the facility cannot perform THEN the item can be marked `REFERRED_OUT` with the destination lab name, dispatch time and a reference; the item remains non-terminal and appears on the ageing report. When a paper result returns, it is entered as an external/text result with an attached scanned-document reference, follows the appropriate result-entry and verification/release records, and only then becomes `RELEASED`, marked "performed externally at [name]".
**Perm** `lab.refer_out`.
**OOS** Electronic integration with external labs.
**Test** Ageing inclusion.

---

---

### Section 16B canonicalisation note

This section canonicalises the supplied DX, RX, PHM, INV, DSP, BIL, PAY, RCP, and ANC stories in source order. The REC, QUE, TRI, ENC, and LAB stories above were canonicalised in Q2 and remain unchanged. The supplied backlog contains story-level acceptance-criteria blocks but no permanent acceptance-criterion sub-identifiers. This Product Spec introduces deterministic sub-IDs in source order (`<STORY-ID>-AC01`, `<STORY-ID>-AC02`, and so on) without changing acceptance meaning, combining materially separate criteria, or splitting an atomic criterion. These sub-IDs are stable once introduced.

All stories below belong to the current V1 functional backlog. References to AUTH, TEN, USR, CAT, PAT, APT, REP, AUD, BRN, or OPS remain dependencies exactly as supplied; their detailed Product Spec authority is UNSUPPLIED / OPEN / BLOCKED, and no missing story is manufactured. No story outside DX, RX, PHM, INV, DSP, BIL, PAY, RCP, and ANC is populated in this phase.

### Epic DX — Diagnosis and Treatment

**DX-001 · Record working diagnosis · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** DX
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**DX-001-AC01** GIVEN an open encounter THEN the clinician can record one or more working (provisional) diagnoses, each coded (CAT-004) or free text, with an optional certainty note.
**DX-001-AC02** GIVEN a working diagnosis THEN it is clearly labelled "working" in the UI and on any draft print, and it is **not** counted in the diagnosis statistics report (REP-014).
**DX-001-AC03** GIVEN investigations are ordered THEN a working diagnosis is encouraged but not mandatory.
**Data** `Diagnosis(type=WORKING)`.
**Dep** CAT-004.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Report exclusion.

**DX-002 · Record final diagnosis · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** DX
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**DX-002-AC01** GIVEN an encounter being signed THEN at least one final diagnosis is required, or an explicit `NO_DIAGNOSIS` entry with a mandatory reason (e.g. "referred before diagnosis", "patient declined assessment").
**DX-002-AC02** GIVEN multiple final diagnoses THEN exactly one must be marked **primary** and the others secondary.
**DX-002-AC03** GIVEN a final diagnosis THEN it is counted in REP-014 and appears in the patient's chart history and on the printed note.
**DX-002-AC04** GIVEN a coded diagnosis THEN its code and label are snapshotted onto the record so later catalogue edits do not rewrite history.
**Data** `Diagnosis(type=FINAL, is_primary)`.
**Dep** ENC-017.
**Test** Primary-uniqueness constraint; sign-blocking.

**DX-003 · Diagnosis certainty and free-text fallback · V1 · P1 · `CLINICIAN`**
**Release** V1
**Epic** DX
**Priority** P1
**Persona** `CLINICIAN`
**DX-003-AC01** GIVEN no suitable coded term exists THEN the clinician may enter free text, which saves with `coded=false` and appears in reports grouped as "Uncoded".
**DX-003-AC02** GIVEN a free-text entry that closely matches a coded term THEN the UI suggests the coded term but never substitutes it automatically.
**DX-003-AC03** GIVEN more than 20% of a month's diagnoses being uncoded THEN this is surfaced on the admin dashboard as a data-quality note.
**Test** No silent substitution.

**DX-004 · Treatment plan and clinical instructions · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** DX
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**DX-004-AC01** GIVEN an encounter THEN the clinician can record a treatment plan as free text (up to 4000 chars) plus structured items: prescriptions (RX), procedures (DX-005), investigations (LAB), referral (DX-007) and follow-up (DX-008).
**DX-004-AC02** GIVEN patient advice text THEN it is printed on the patient's copy in a clearly separated section.
**DX-004-AC03** GIVEN signing THEN the plan becomes immutable with the note.
**Data** `Encounter.plan`, `Encounter.patient_advice`.
**Test** Print separation of clinician-facing vs patient-facing content.

**DX-005 · Order a procedure / nursing treatment · V1 · P1 · `CLINICIAN`; secondary `NURSE`**
**Release** V1
**Epic** DX
**Priority** P1
**Persona** `CLINICIAN`; secondary `NURSE`
**DX-005-AC01** GIVEN a procedure ordered from the catalogue (CAT-005) THEN a charge is created (per gate policy), a task appears in the treatment-room/nursing worklist with the patient, procedure, instructions and priority, and the encounter shows the procedure as pending.
**DX-005-AC02** GIVEN a `PAY_BEFORE` procedure requires a charge line and that line cannot be created THEN the initiating operation fails with an explicit billing/setup error and no performable procedure task exists.
**DX-005-AC03** GIVEN the nurse marks a procedure performed using a consumable/injectable that is **not** managed as KlinKlik inventory THEN performer, time, optional free-text batch/lot, and notes are clinical documentation only, not a stock movement.
**DX-005-AC04** GIVEN the consumable/injectable is configured as a KlinKlik-stocked Product THEN structured stock issue is mandatory: select product, non-expired batch, quantity and location; INV-005 applies and the API refuses an expired batch with no override.
**DX-005-AC05** GIVEN the procedure is gated by payment and unpaid THEN the nurse cannot mark it performed and sees the outstanding amount.
**DX-005-AC06** GIVEN a procedure ordered but not performed by visit closure THEN it appears on the unresolved-tasks report.
**Data** `ProcedureOrder`; structured stock-issue reference only when a KlinKlik-stocked product is selected.
**Dep** CAT-005, QUE-005, INV-005.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Automatic unprompted consumable deduction; expiry enforcement for externally sourced/non-inventory free-text documentation.
**Test** Gate enforcement; unresolved reporting.

**DX-006 · Record disposition · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** DX
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**DX-006-AC01** GIVEN signing THEN a disposition is mandatory, chosen from `TREATED_AND_DISCHARGED`, `REVIEW_SCHEDULED`, `REFERRED_OUT`, `ADMITTED_ELSEWHERE`, `LEFT_AGAINST_ADVICE`, `DECEASED`, `OTHER` (+ note).
**DX-006-AC02** GIVEN `REFERRED_OUT` THEN a referral record is required (DX-007).
**DX-006-AC03** GIVEN `REVIEW_SCHEDULED` THEN a follow-up date or interval is recorded (DX-008) and prints; appointment creation is unavailable unless supplied/frozen APT authority later authorises it (APT remains UNSUPPLIED / OPEN / BLOCKED).
**DX-006-AC04** GIVEN `DECEASED` THEN the patient deceased flag workflow is offered (PAT-013).
**DX-006-AC05** GIVEN disposition THEN it is included in the visit summary and REP-002.
**Data** `Encounter.disposition`.
**Test** Conditional-requirement matrix.

**DX-007 · Create a referral letter · V1 · P1 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** DX
**Priority** P1
**Persona** `CLINICIAN`,`MIDWIFE`
**DX-007-AC01** GIVEN a referral THEN the clinician records the destination facility/specialist (free text), reason for referral, clinical summary (prefilled from the encounter and editable), investigations already done with results, treatment given, and urgency.
**DX-007-AC02** GIVEN the referral is saved THEN a printable letter is produced with the facility header, patient identifiers, the clinician's name/cadre/licence and signature line, and it is retained on the patient's record.
**DX-007-AC03** GIVEN a signed encounter THEN the referral content is immutable with it.
**DX-007-AC04** GIVEN a reprint THEN it is audited.
**Data** `Referral`.
**Dep** TEN-003, RCP-003.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Electronic referral transmission, referral tracking/feedback loops.
**Test** Prefill accuracy; print snapshot.

**DX-008 · Record follow-up instruction · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** DX
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**DX-008-AC01** GIVEN a follow-up interval or date THEN it is stored on the encounter and printed on the patient's copy; it may be referenced for future APT integration, but appointment creation is unavailable while APT authority remains UNSUPPLIED / OPEN / BLOCKED.
**DX-008-AC02** GIVEN a future appointment is created only after supplied/frozen APT authority authorises the flow THEN the encounter references that appointment; no appointment can be created by this Product Spec while APT authority remains UNSUPPLIED / OPEN / BLOCKED.
**DX-008-AC03** GIVEN no appointment is created (the current V1 condition while APT authority is UNSUPPLIED / OPEN / BLOCKED) THEN the follow-up instruction still prints ("return in 3 days or earlier if worse") and may be referenced for future APT integration.
**Dep** APT-001.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Link integrity.

**DX-009 · Sick leave / medical certificate · V1 · P2 · `CLINICIAN`**
**Release** V1
**Epic** DX
**Priority** P2
**Persona** `CLINICIAN`
**DX-009-AC01** GIVEN a certificate request THEN the clinician records the number of days, the period, and a generic reason (fit/unfit for duty), producing a printable certificate with the facility header, patient identity, clinician name/cadre/licence, date and a certificate serial number.
**DX-009-AC02** GIVEN issuance THEN it is recorded on the patient record and audited, and reprints are marked as duplicates.
**Data** `MedicalCertificate`.
**OOS** Diagnosis disclosure rules per employer.
**Test** Serial uniqueness; duplicate marking.

**DX-010 · HMIS-aligned diagnosis grouping for reporting · V1 · P2 · `FACILITY_ADMIN`**
**Release** V1
**Epic** DX
**Priority** P2
**Persona** `FACILITY_ADMIN`
**DX-010-AC01** GIVEN the diagnosis catalogue THEN each entry may be mapped to an HMIS OPD diagnosis category (aligned to the Uganda outpatient register, HMIS Form 031) so that REP-016 can produce a register-shaped tally.
**DX-010-AC02** GIVEN unmapped diagnoses THEN they are grouped under "Other" and listed separately so the mapping gap is visible.
**DX-010-AC03** GIVEN the export THEN it is explicitly labelled as an aid for manual register completion and **not** as a certified HMIS/DHIS2 submission.
**Dep** CAT-004, REP-016.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** DHIS2 integration.
**Test** Mapping coverage report.

---

---

### Epic RX — Prescriptions

**RX-001 · Create a prescription within the encounter · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** RX
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**Story** As a clinician I want to prescribe medicines within the consultation so the pharmacy receives exactly what I intended.
**Pre** Encounter `OPEN`; `prescription.create`.
**Flow** Open the prescription tray → add items (RX-002) → the prescription exists as `DRAFT` bound to the encounter → activated on signing (RX-005).
**RX-001-AC01** GIVEN an open encounter THEN a single `DRAFT` prescription per encounter holds all items (no duplicate drafts).
**RX-001-AC02** GIVEN a draft prescription THEN it is **not** visible to the pharmacy.
**RX-001-AC03** GIVEN the encounter is voided THEN the draft is cancelled.
**Data** `Prescription(state=DRAFT)`.
**Dep** ENC-001.
**Test** Pharmacy invisibility of drafts.

**RX-002 · Add a prescription item · V1 · P0 · `CLINICIAN`,`MIDWIFE`**
**Release** V1
**Epic** RX
**Priority** P0
**Persona** `CLINICIAN`,`MIDWIFE`
**RX-002-AC01** GIVEN the item form THEN the clinician selects a product from the pharmacy catalogue (PHM-001) **or** enters a free-text medicine name (for items the facility does not stock), and records: dose (amount + unit), route (`PO`,`IM`,`IV`,`PR`,`PV`,`TOP`,`INH`,`SL`,`OPTH`,`OTIC`, other), frequency (`OD`,`BD`,`TDS`,`QDS`,`NOCTE`,`PRN`,`STAT`, custom), duration (value + unit), quantity to dispense, and instructions to the patient (free text).
**RX-002-AC02** GIVEN product, dose, frequency and duration THEN the system **arithmetically** proposes a quantity (dose units × frequency per day × days), which the clinician may override; the proposal is labelled as arithmetic only and performs **no dose checking** (AS-11).
**RX-002-AC03** GIVEN a free-text medicine THEN the item is flagged `external=true`, cannot be dispensed internally, and prints on an external prescription (RX-007) — an external item never leaves the prescription permanently `ACTIVE` and never blocks Visit closure (an all-external prescription terminalises `NOT_DISPENSED` at signing, reason `EXTERNAL_SUPPLY`; in a mixed prescription it carries no internal obligation — RX-005).
**RX-002-AC04** GIVEN a catalogue product flagged as controlled/Class A THEN it is **not selectable** and the UI states that controlled medicines are not supported in this system (RX-008).
**RX-002-AC05** GIVEN the patient's recorded allergies THEN they are displayed prominently beside the prescribing form; **no automatic matching or blocking occurs** and the UI must not imply it does (OD-19).
**Data** `PrescriptionItem`.
**Err** Quantity zero/negative rejected; duration beyond a configurable maximum (default 90 days) warns.
**Test** Quantity arithmetic; controlled-product block; external-item behaviour.

**RX-003 · See allergies and current medications while prescribing · V1 · P0 · `CLINICIAN`**
**Release** V1
**Epic** RX
**Priority** P0
**Persona** `CLINICIAN`
**RX-003-AC01** GIVEN the prescribing tray is open THEN the patient's active recorded allergies, NKA, UNKNOWN, or NOT RECORDED status and current medications are visible without navigation.
**RX-003-AC02** GIVEN allergy status is `NOT RECORDED` THEN a warning chip is shown and signing is blocked until recorded (ENC-011); GIVEN `UNKNOWN` THEN "Allergy status unknown" is shown, not NKA, and signing is not blocked for the allergy-status prerequisite.
**RX-003-AC03** GIVEN the platform THEN it performs no interaction or contraindication checking and displays no statement suggesting that it does.
**Dep** TRI-004, ENC-010.
**Test** UI copy review for any implied CDS.

**RX-004 · Review and edit the prescription before signing · V1 · P0 · `CLINICIAN`**
**Release** V1
**Epic** RX
**Priority** P0
**Persona** `CLINICIAN`
**RX-004-AC01** GIVEN a draft prescription THEN items can be edited or removed freely, and a summary shows each item's full sig line ("Amoxicillin 500 mg capsule — 1 cap PO TDS × 5 days = 15 capsules").
**RX-004-AC02** GIVEN a duplicate product already on the same prescription THEN a warning is shown requiring confirmation.
**RX-004-AC03** GIVEN the prescription is empty at signing THEN the encounter signs normally with no prescription created.
**Test** Sig-line rendering rules.

**RX-005 · Activate the prescription on signing · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** RX
**Priority** P0
**Persona** `SYSTEM`
**RX-005-AC01** GIVEN an encounter with a draft prescription containing **at least one internally dispensable item** and an enabled Pharmacy module WHEN the encounter is signed THEN the prescription becomes `ACTIVE`, records the prescriber identity snapshot (name, cadre, licence), and appears in the pharmacy dispensing queue within 15 seconds.
**RX-005-AC02** GIVEN activation THEN the prescription content becomes immutable; changes require cancellation and a new prescription (RX-009) or a signed addendum.
**RX-005-AC03** GIVEN activation THEN charges are **not** created yet (charging happens at dispensing, DSP-007, because quantities may change with availability).
**RX-005-AC04** GIVEN a prescription with **zero internally dispensable items** (all items `external=true` / not internally dispensable) WHEN the encounter is signed THEN the prescription terminalises directly `DRAFT → NOT_DISPENSED` with the structured reason `EXTERNAL_SUPPLY` — the external prescription remains printable (RX-007), no Pharmacy QueueEntry is created, no Dispense is created, no pharmacy stock movement occurs, no internal medicine charge is created for those external-only items, the prescription remains visible in the patient record as an external prescription with its prescriber snapshot retained, the audit references the terminalisation reason, and Visit closure (REC-012) never treats it as unresolved.
**RX-005-AC05** GIVEN the **Pharmacy module is disabled** and the prescription can only be fulfilled externally WHEN the encounter is signed THEN the same external-supply path applies with reason `PHARMACY_DISABLED`.
**RX-005-AC06** GIVEN a **mixed** prescription (internally dispensable + external-only items) WHEN the encounter is signed THEN the prescription becomes `ACTIVE` (internal pharmacy work exists): internal items enter the pharmacy workflow, external items remain part of the record marked external/non-internal with no internal DispenseLine, stock movement or internal charge, and the prescription terminalises later based only on the internal dispensing result — no duplicate prescription is created.
**Data** `Prescription.state`, prescriber snapshot.
**Audit** Activation (or external/pharmacy-disabled terminalisation with its reason) referencing the Prescription ID/version and item version hashes with the prescriber snapshot; prescribed-medicine details remain in the protected prescription record.
**Dep** ENC-017, DSP-001.
**Test** Fan-out timing; immutability; mandatory tests — (1) CLINIC facility with Pharmacy disabled: sign external prescription → `NOT_DISPENSED`(`PHARMACY_DISABLED`), printable, no pharmacy queue/dispense/stock movement, visit closable under REC-012; (2) external-only item with Pharmacy enabled → `NOT_DISPENSED`(`EXTERNAL_SUPPLY`), same guarantees; (3) mixed internal+external → `ACTIVE`, pharmacy queue entry created, internal item dispensed through normal states, external item carries no internal obligation.

**RX-006 · View prescription history · V1 · P1 · `CLINICIAN`,`PHARMACIST`**
**Release** V1
**Epic** RX
**Priority** P1
**Persona** `CLINICIAN`,`PHARMACIST`
**RX-006-AC01** GIVEN a patient chart THEN prescriptions from previous visits are listed with date, prescriber, items, and dispensing status (fully/partially/not dispensed).
**RX-006-AC02** GIVEN an item dispensed THEN the dispensed quantity, batch and date are shown to authorised roles.
**RX-006-AC03** GIVEN a pharmacist THEN they see prescriptions and allergies but not the full clinical note.
**Dep** PAT-009, DSP-012.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Role-scoped payload.

**RX-007 · Print a prescription · V1 · P0 · `CLINICIAN`,`PHARMACIST`,`RECEPTIONIST`**
**Release** V1
**Epic** RX
**Priority** P0
**Persona** `CLINICIAN`,`PHARMACIST`,`RECEPTIONIST`
**RX-007-AC01** GIVEN an active prescription WHEN printed THEN the document contains the facility header, patient name/number/age/sex (and weight for under-5s), date, each item with full sig, quantity, prescriber name/cadre/licence number, signature line, and a prescription serial number.
**RX-007-AC02** GIVEN items flagged `external=true` THEN they print on the prescription clearly marked "not dispensed here"; external-only and pharmacy-disabled prescriptions terminalised `NOT_DISPENSED` (RX-005) remain printable as external prescriptions and stay visible in the patient record with the prescriber snapshot retained.
**RX-007-AC03** GIVEN a reprint THEN it is marked as a duplicate copy and audited.
**RX-007-AC04** GIVEN a draft prescription THEN printing is blocked.
**Dep** TEN-003, USR-003, RCP-003, RCP-007.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Under-5 weight presence; duplicate marking.

**RX-008 · Controlled / Class A medicines are out of scope · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** RX
**Priority** P0
**Persona** `SYSTEM`
**Story** As the platform I must refuse to handle controlled medicines because V1 cannot satisfy the statutory register and custody requirements.
**RX-008-AC01** GIVEN a catalogue product flagged `controlled=true` THEN it cannot be added to a prescription, cannot be received into stock, cannot be dispensed, and cannot be sold, in every code path, with the message "Controlled medicines are not supported in KlinKlik V1 — use your paper controlled-drugs register".
**RX-008-AC02** GIVEN an attempt via the API THEN 403 `CONTROLLED_NOT_SUPPORTED`.
**RX-008-AC03** GIVEN an import of catalogue data containing controlled items THEN they are imported as inactive and flagged, never silently enabled.
**RX-008-AC04** GIVEN a future authorised manual set/clear path THEN `ORG_OWNER` is the only eligible application role from the supplied story, but the `ORG_OWNER` role label alone supplies neither the still-unsupplied CAT classification authority nor permission to act. While CAT governance and OD-PH1 remain UNSUPPLIED / BLOCKED, manual set/clear is unavailable to every role; the bounded import safety path in AC03 may only set `controlled=true` together with inactive status. Every later authorised classification change requires the supplied classification authority and is audited, and no change can enable controlled/Class A V1 workflow.
**Data** `Product.controlled`.
**Audit** Flag changes; blocked attempts (to detect demand).
**Dep** PHM-001, DSP-003.
**OOS** Any controlled-drug workflow.
**Test** All four workflow code paths refuse; role-only manual classification change is denied while CAT/OD-PH1 is unresolved; controlled imports remain inactive.

**RX-009 · Cancel or discontinue a prescription · V1 · P1 · `CLINICIAN` (prescriber), `SUPERVISOR`**
**Release** V1
**Epic** RX
**Priority** P1
**Persona** `CLINICIAN` (prescriber), `SUPERVISOR`
**RX-009-AC01** GIVEN an `ACTIVE` prescription with no dispensing THEN the prescriber may cancel it with a reason; it becomes `CANCELLED` and disappears from the pharmacy queue with a visible notice to pharmacy.
**RX-009-AC02** GIVEN partial dispensing has occurred THEN only the undispensed items may be cancelled; dispensed items and their stock movements are untouched.
**RX-009-AC03** GIVEN cancellation after the pharmacist has started preparing THEN the pharmacist sees an immediate alert on their open dispense screen.
**Audit** Reason mandatory.
**Test** Race between cancel and dispense (dispense wins if already committed; cancel then fails with 409).

**RX-010 · Repeat / refill an earlier prescription · V1 · P2 · `CLINICIAN`**
**Release** V1
**Epic** RX
**Priority** P2
**Persona** `CLINICIAN`
**RX-010-AC01** GIVEN a previous prescription THEN the clinician may copy it into the current encounter as a **draft**, with all items editable and the source prescription referenced.
**RX-010-AC02** GIVEN a copy THEN it never activates without the current encounter being signed, and the new prescriber is the current clinician.
**Test** Provenance recording.

**RX-011 · Nurse/midwife limited prescribing scope · V1 · P2 · `FACILITY_ADMIN`**
**Release** V1
**Epic** RX
**Priority** P2
**Persona** `FACILITY_ADMIN`
**RX-011-AC01** GIVEN a facility configuration listing products a `MIDWIFE` may prescribe (e.g. iron/folic acid, paracetamol, ORS) THEN holders of `prescription.create.limited` may prescribe only those products, and attempts to prescribe outside the list are refused with `OUTSIDE_PRESCRIBING_SCOPE`.
**RX-011-AC02** GIVEN such a prescription THEN it prints with that provider's cadre and licence and is flagged as limited-scope in the audit. **`NURSE` limited prescribing is not active in the supplied V1**: the 194-story backlog defines no nurse prescription activation/sign-off workflow (a nurse cannot sign the encounter, and no countersigning exists); enabling it later requires an explicit authorisation/sign-off specification before implementation.
**Dep** RX-002, USR-003.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Any clinical protocol enforcement; nurse limited prescribing in V1.

---

---

### Epic PHM — Pharmacy Catalogue

**PHM-001 · Create a product · V1 · P0 · `PHARMACIST`,`FACILITY_ADMIN`**
**Release** V1
**Epic** PHM
**Priority** P0
**Persona** `PHARMACIST`,`FACILITY_ADMIN`
**PHM-001-AC01** GIVEN the product form THEN the user records: generic name (required), brand/trade name (optional), dosage form (`TABLET`,`CAPSULE`,`SYRUP`,`SUSPENSION`,`INJECTION`,`CREAM`,`OINTMENT`,`DROPS`,`INHALER`,`SUPPOSITORY`,`SACHET`,`VIAL`,`TUBE`,`PIECE`), strength (text, e.g. "500 mg", "125 mg/5 mL"), pack description, dispensing unit (`TABLET`,`CAPSULE`,`ML`,`BOTTLE`,`SACHET`,`VIAL`,`TUBE`,`PIECE`), category (`MEDICINE`,`CONSUMABLE`,`SUNDRY`), prescription-only flag, controlled flag (governed separately by RX-008), active flag. `PHARMACIST` or `FACILITY_ADMIN` access to this product form does not grant controlled-classification set/clear authority; while CAT/OD-PH1 remains unresolved, the manual field is non-editable and product creation cannot bypass RX-008's fail-closed rule.
**PHM-001-AC02** GIVEN a duplicate generic+strength+form in one facility THEN a warning with the existing product is shown; creation requires confirmation.
**PHM-001-AC03** GIVEN a product THEN it is searchable by generic and brand name.
**PHM-001-AC04** GIVEN creation/edit THEN it is audited.
**Data** `Product`.
**Err** Strength typed inconsistently ("500mg" vs "500 mg") → normalise on save for search.
**OOS** National drug register import, ATC coding.
**Test** Search by both names; product-create roles cannot change controlled classification without the separately supplied authority.

**PHM-002 · Set selling price · V1 · P0 · `PHARMACIST`,`FACILITY_ADMIN`**
**Release** V1
**Epic** PHM
**Priority** P0
**Persona** `PHARMACIST`,`FACILITY_ADMIN`
**PHM-002-AC01** GIVEN a product THEN a selling price per dispensing unit is set per facility, with an optional pack price.
**PHM-002-AC02** GIVEN a dispense or sale THEN the price is snapshotted onto the invoice line so later price changes never alter historical invoices.
**PHM-002-AC03** GIVEN a price change THEN it is audited with old/new and actor and appears in the price-history view.
**PHM-002-AC04** GIVEN a product with no price THEN it cannot be dispensed or sold and appears on the setup-warnings list.
**Data** `ProductPrice`.
**Dep** CAT-002.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**OOS** Automatic margin calculation from cost (P2: display-only margin is allowed if cost is captured in INV-002).
**Test** Snapshot immutability.

**PHM-003 · Link products to prescribing · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** PHM
**Priority** P0
**Persona** `SYSTEM`
**PHM-003-AC01** GIVEN the prescribing search THEN it returns active, non-controlled products with their form and strength, showing current stock availability as an indicator (`In stock`, `Low`, `Out of stock`) **without exposing exact stock counts to clinicians unless they hold `inventory.read`**.
**PHM-003-AC02** GIVEN an out-of-stock product THEN the clinician may still prescribe it (the patient may buy elsewhere) but sees the indicator.
**Dep** RX-002, INV-006.
**Test** Indicator accuracy and permission scoping.

**PHM-004 · Deactivate a product · V1 · P1 · `PHARMACIST`**
**Release** V1
**Epic** PHM
**Priority** P1
**Persona** `PHARMACIST`
**PHM-004-AC01** GIVEN a product with zero stock THEN it may be deactivated, disappearing from prescribing, dispensing and sale searches while remaining in historical records and reports.
**PHM-004-AC02** GIVEN a product with stock on hand THEN deactivation is blocked with the quantity shown, requiring adjustment or disposal first.
**PHM-004-AC03** GIVEN reactivation THEN it is audited.
**Test** Stock-blocking rule.

**PHM-005 · Product search performance · V1 · P1 · `PHARMACIST`,`CLINICIAN`**
**Release** V1
**Epic** PHM
**Priority** P1
**Persona** `PHARMACIST`,`CLINICIAN`
**PHM-005-AC01** GIVEN a catalogue of 3,000 products WHEN a user types three characters THEN results return within 300 ms p95 from the server, ranked by exact-prefix, then generic-name match, then brand match, then frequency of use at that facility.
**Test** Latency and ranking.

**PHM-006 · Consumables and sundries · V1 · P1 · `PHARMACIST`**
**Release** V1
**Epic** PHM
**Priority** P1
**Persona** `PHARMACIST`
**PHM-006-AC01** GIVEN category `CONSUMABLE`/`SUNDRY` (gloves, syringes, gauze, cotton, plasters) THEN the item participates in stock, sale and adjustment workflows but is excluded from prescribing search by default and from the "medicines" reports, appearing instead in consumables reporting.
**Dep** INV-001.
**Test** Search exclusion.

**PHM-007 · Import a starter catalogue · V1 · P1 · `FACILITY_ADMIN`**
**Release** V1
**Epic** PHM
**Priority** P1
**Persona** `FACILITY_ADMIN`
**PHM-007-AC01** GIVEN a CSV in the published template THEN the system validates every row before importing any, reports row-level errors with line numbers, and imports only on a clean file or on explicit "import valid rows only".
**PHM-007-AC02** GIVEN a row flagged as controlled THEN it is imported inactive with the controlled flag set.
**PHM-007-AC03** GIVEN an import THEN it is audited with the file name, row counts and actor.
**Err** Duplicate rows; malformed prices; encoding issues.
**OOS** Automatic mapping to any national register.
**Test** All-or-nothing and partial modes.

**PHM-008 · Product dispensing instructions template · V1 · P2 · `PHARMACIST`**
**Release** V1
**Epic** PHM
**Priority** P2
**Persona** `PHARMACIST`
**PHM-008-AC01** GIVEN a product THEN a default patient instruction (e.g. "Take with food") may be stored and is auto-inserted, **editable**, into the dispense label and the prescription instruction field.
**PHM-008-AC02** GIVEN no template THEN nothing is inserted.
**Dep** DSP-010.
**OOS** Any clinical advice library.

---

---

### Epic INV — Inventory and Stock

**INV-001 · Stock locations · V1 · P1 · `FACILITY_ADMIN`**
**Release** V1
**Epic** INV
**Priority** P1
**Persona** `FACILITY_ADMIN`
**INV-001-AC01** GIVEN a facility THEN at least one stock location exists (default "Main Pharmacy"); additional locations (Store, Dispensary, Lab Store, Treatment Room) may be created.
**INV-001-AC02** GIVEN multiple locations THEN stock balances are tracked per location and dispensing draws from a configured default location.
**INV-001-AC03** GIVEN a location with stock THEN it cannot be deleted, only deactivated after transfer.
**Data** `StockLocation`.
**Dep** INV-007.
**Test** Per-location balance isolation.

**INV-002 · Receive stock (goods received note) · V1 · P0 · `STORE_KEEPER`,`PHARMACIST`**
**Release** V1
**Epic** INV
**Priority** P0
**Persona** `STORE_KEEPER`,`PHARMACIST`
**Story** As a pharmacist I want to record medicines received from a supplier, with batches and expiry dates, so stock and expiry control are accurate.
**Pre** Products exist.
**Trig** Delivery arrives.
**Flow** Create a GRN: supplier name (free text or from a simple supplier list), invoice/delivery-note reference, received date, receiving location, and lines of: product, batch/lot number, expiry date (month precision minimum), quantity received in the dispensing unit, unit cost (optional but recommended), and any pack-to-unit conversion. Save → stock ledger entries created → balances increase.
**INV-002-AC01** GIVEN a GRN line with an expiry date in the past WHEN saved THEN it is **rejected** with `EXPIRED_STOCK_CANNOT_BE_RECEIVED`.
**INV-002-AC02** GIVEN a GRN line with an expiry within 3 months THEN it is accepted with a prominent warning recorded on the GRN.
**INV-002-AC03** GIVEN a saved GRN THEN each line creates a `StockLedger(IN)` entry referencing the GRN, the batch record is created or incremented, and the balance for that product/batch/location increases by exactly the received quantity.
**INV-002-AC04** GIVEN the same GRN submitted twice with one idempotency key THEN stock increases once.
**INV-002-AC05** GIVEN a GRN THEN it is printable and immutable after posting; corrections require a stock adjustment (INV-011) with a reason.
**Perm** `inventory.receive`.
**Data** `GoodsReceipt`, `GoodsReceiptLine`, `Batch`, `StockLedger`, `StockBalance`.
**Audit** Posting with all lines.
**Err** Duplicate batch numbers from different suppliers → batch identity is `(product, batch_no, expiry)`; missing expiry on a product that requires it → blocked.
**UI** Fast line-entry grid with keyboard navigation; running total.
**OOS** Purchase orders, supplier invoices/payables, barcode scanning.
**Test** Past-expiry rejection; idempotency; ledger arithmetic.

**INV-003 · Batch and expiry tracking · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** INV
**Priority** P0
**Persona** `SYSTEM`
**INV-003-AC01** GIVEN any stock movement THEN it is attributed to a specific batch with its expiry date; no movement may exist without a batch for products flagged as batch-tracked (all `MEDICINE` products are batch-tracked by default).
**INV-003-AC02** GIVEN a batch THEN its remaining quantity per location is always derivable from the ledger and matches the cached balance (a nightly reconciliation job asserts this and raises a discrepancy alert).
**INV-003-AC03** GIVEN a batch reaching zero THEN it remains visible in history and is excluded from dispensing selection.
**Data** `Batch`, `StockLedger`, `StockBalance`.
**Test** Ledger-vs-balance reconciliation.

**INV-004 · FEFO batch selection · V1 · P0 · `SYSTEM`; secondary `PHARMACIST`**
**Release** V1
**Epic** INV
**Priority** P0
**Persona** `SYSTEM`; secondary `PHARMACIST`
**Story** As a pharmacist I want the system to propose the earliest-expiring usable batch so we don't accumulate expiries.
**INV-004-AC01** GIVEN three batches with different expiry dates WHEN a dispense or sale is prepared THEN the system proposes the **non-expired** batch with the earliest expiry that has sufficient quantity, and displays the batch number and expiry.
**INV-004-AC02** GIVEN insufficient quantity in the earliest batch THEN the system proposes a split across batches in expiry order and shows the split explicitly.
**INV-004-AC03** GIVEN the pharmacist selects a different (non-expired) batch THEN a reason is required and the deviation is audited and reported (INV-016).
**INV-004-AC04** GIVEN only expired batches exist THEN the product is treated as out of stock and dispensing is refused (INV-005).
**Data** Batch selection recorded on the dispense line.
**Audit** FEFO deviations.
**Dep** INV-005, DSP-003.
**Test** Split-batch arithmetic; deviation audit.

**INV-005 · Expired stock can never be dispensed or sold · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** INV
**Priority** P0
**Persona** `SYSTEM`
**Story** As a facility I need absolute certainty that expired KlinKlik-managed stock cannot be issued, dispensed, sold, or used through this system.
**Why** Patient safety and NDA compliance; the highest-severity rule in the product.
**INV-005-AC01** GIVEN a batch whose expiry date is before today WHEN it is offered for dispensing, sale, transfer-out to a dispensing location, prescription fulfilment, or structured procedure stock issue/use THEN it is excluded from selection in every interface.
**INV-005-AC02** GIVEN a direct API request specifying an expired batch THEN the request is rejected with 422 `EXPIRED_BATCH` regardless of the caller's role, including `ORG_OWNER` and `SYS_ADMIN`.
**INV-005-AC03** GIVEN **no** configuration setting, permission, capability, reason code, or override parameter exists anywhere in the system that permits dispensing expired stock (verified by a no-override assertion and all-entry-point refusal test).
**INV-005-AC04** GIVEN a batch that expires while reserved in an in-progress dispense THEN the dispense cannot be confirmed and the pharmacist is instructed to reselect a batch.
**INV-005-AC05** GIVEN expired stock on hand THEN the only permitted movements are quarantine (INV-010) and disposal write-off (INV-011). Any positive movement into an already-expired KlinKlik-managed batch is rejected or lands directly in quarantine/non-usable stock; it can never increase usable availability.
**INV-005-AC06** GIVEN a dispense attempt on an expired batch THEN the attempt is audited as a blocked action.
**Perm** No permission grants this.
**Data** None created on refusal; audit of the blocked attempt.
**Dep** INV-004, DSP-003.
**OOS** Any override mechanism — permanently.
**Test** **Security-grade test suite**: role matrix × interface matrix × direct API, all refusing; plus a no-override configuration check.

**INV-006 · Stock balance view · V1 · P0 · `PHARMACIST`,`STORE_KEEPER`,`FACILITY_ADMIN`**
**Release** V1
**Epic** INV
**Priority** P0
**Persona** `PHARMACIST`,`STORE_KEEPER`,`FACILITY_ADMIN`
**INV-006-AC01** GIVEN the stock list THEN it shows, per product: total quantity on hand at the facility, quantity by location, number of batches, earliest expiry, and status chips (`OK`, `LOW`, `OUT`, `EXPIRING_SOON`, `EXPIRED`).
**INV-006-AC02** GIVEN a product is expanded THEN each batch is listed with batch number, expiry, location and quantity.
**INV-006-AC03** GIVEN expired batches THEN they are shown in a visually distinct, non-selectable style with the quantity counted separately from usable stock (usable stock excludes expired).
**INV-006-AC04** GIVEN a search THEN it filters by product name, status and location.
**Perm** `inventory.read`.
**Test** Usable-vs-total arithmetic.

**INV-007 · Stock transfer between locations · V1 · P1 · `STORE_KEEPER`,`PHARMACIST`**
**Release** V1
**Epic** INV
**Priority** P1
**Persona** `STORE_KEEPER`,`PHARMACIST`
**INV-007-AC01** GIVEN stock at the Store THEN a transfer to the Dispensary creates paired ledger entries (OUT at source, IN at destination) preserving batch and expiry, leaving the facility total unchanged.
**INV-007-AC02** GIVEN an expired batch THEN it may be transferred **only** to a location flagged as quarantine (INV-010).
**INV-007-AC03** GIVEN a transfer THEN it is audited with actor, batches and quantities.
**INV-007-AC04** GIVEN insufficient quantity THEN it is rejected.
**Data** `StockTransfer`, ledger pairs.
**Test** Total-conservation invariant.

**INV-008 · Low-stock threshold and alerts · V1 · P0 · `PHARMACIST`,`FACILITY_ADMIN`**
**Release** V1
**Epic** INV
**Priority** P0
**Persona** `PHARMACIST`,`FACILITY_ADMIN`
**INV-008-AC01** GIVEN a reorder level set per product per facility THEN products at or below it appear on the low-stock list and on the pharmacy dashboard with the current quantity and the level.
**INV-008-AC02** GIVEN a product with no reorder level THEN it is excluded from alerts and appears on a "thresholds not set" list.
**INV-008-AC03** GIVEN a dispense that takes stock below the level THEN the product appears on the low-stock list on the next refresh.
**INV-008-AC04** GIVEN the low-stock list THEN it is exportable to CSV for ordering.
**Data** `Product.reorder_level` (per facility).
**Dep** REP-012.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Threshold-crossing detection.

**INV-009 · Expiry warnings · V1 · P0 · `PHARMACIST`,`FACILITY_ADMIN`**
**Release** V1
**Epic** INV
**Priority** P0
**Persona** `PHARMACIST`,`FACILITY_ADMIN`
**INV-009-AC01** GIVEN batches expiring within a configurable horizon (default 90 days) THEN they appear on the expiring-stock list with product, batch, expiry, quantity, location and days remaining, sorted by soonest.
**INV-009-AC02** GIVEN batches already expired THEN they appear on a separate expired list with a prompt to quarantine or write off.
**INV-009-AC03** GIVEN the pharmacy dashboard THEN it shows counts for both.
**INV-009-AC04** GIVEN a batch crossing the expiry date overnight THEN it moves from expiring to expired without manual action (evaluated on read; a nightly job refreshes cached flags).
**Dep** REP-012.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Date-boundary behaviour at midnight EAT.

**INV-010 · Quarantine expired or damaged stock · V1 · P1 · `PHARMACIST`,`STORE_KEEPER`**
**Release** V1
**Epic** INV
**Priority** P1
**Persona** `PHARMACIST`,`STORE_KEEPER`
**INV-010-AC01** GIVEN expired or damaged stock THEN it can be moved to a quarantine location, which is excluded from all availability calculations and from dispensing entirely.
**INV-010-AC02** GIVEN quarantined stock THEN it remains on the books until written off (INV-011) so it can be counted and reconciled.
**INV-010-AC03** GIVEN quarantine THEN the reason and actor are recorded.
**Data** `StockLocation(is_quarantine=true)`.
**Test** Availability exclusion.

**INV-011 · Stock adjustment and write-off with reason · V1 · P0 · `PHARMACIST`,`STORE_KEEPER`; approval `FACILITY_ADMIN`**
**Release** V1
**Epic** INV
**Priority** P0
**Persona** `PHARMACIST`,`STORE_KEEPER`; approval `FACILITY_ADMIN`
**INV-011-AC01** GIVEN a discrepancy THEN an adjustment can be recorded per product/batch/location with a signed quantity, a mandatory reason (`EXPIRY_DISPOSAL`, `DAMAGE`, `BREAKAGE`, `THEFT_LOSS`, `COUNT_CORRECTION`, `RETURN_TO_SUPPLIER`, `DONATION_OUT`, `OTHER` + note) and an optional reference (disposal certificate number).
**INV-011-AC02** GIVEN an adjustment above a configurable value threshold THEN it requires `FACILITY_ADMIN` approval before posting, and remains `PENDING_APPROVAL` until then.
**INV-011-AC03** GIVEN posting THEN a ledger entry is created and the balance changes by exactly that amount; the adjustment record is immutable thereafter.
**INV-011-AC04** GIVEN a positive adjustment or count correction into an already-expired batch THEN it is rejected or lands in quarantine/non-usable stock and cannot make that batch available.
**INV-011-AC05** GIVEN a write-off of expired stock THEN the value is reported separately in REP-012 so wastage is visible.
**INV-011-AC06** GIVEN any adjustment THEN it is audited with the actor, reason and before/after balances.
**Data** `StockAdjustment`, ledger.
**Err** Adjustment making a balance negative → rejected.
**Test** Approval threshold; negative-balance prevention.

**INV-012 · Automatic stock deduction on dispense/sale · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** INV
**Priority** P0
**Persona** `SYSTEM`
**INV-012-AC01** GIVEN a confirmed dispense or sale THEN a `StockLedger(OUT)` entry is created per batch per line **in the same product outcome** as the dispense record, and the balance decreases accordingly.
**INV-012-AC02** GIVEN insufficient stock at the moment of confirmation (a race with another dispense) THEN the whole dispense fails with no partial effect and `INSUFFICIENT_STOCK` and the pharmacist is asked to reselect; no partial deduction occurs.
**INV-012-AC03** GIVEN a reversal (DSP-016) THEN a compensating `IN` entry is created referencing the original, never a deletion; it preserves the same batch identity but, while OD-PH5 is BLOCKED, lands only in quarantine/non-usable stock and cannot increase usable availability.
**INV-012-AC04** GIVEN any ledger entry THEN it is immutable.
**Test** Concurrency race with two pharmacists dispensing the last pack.

**INV-013 · Stock count (physical inventory) · V1 · P1 · `PHARMACIST`,`STORE_KEEPER`**
**Release** V1
**Epic** INV
**Priority** P1
**Persona** `PHARMACIST`,`STORE_KEEPER`
**INV-013-AC01** GIVEN a count session THEN the system produces a count sheet (printable) listing products/batches at a location with a blank counted-quantity column and **without showing the system quantity** by default (blind count, configurable).
**INV-013-AC02** GIVEN counted quantities are entered THEN variances are shown per line with value impact.
**INV-013-AC03** GIVEN the count is posted THEN adjustments are created automatically with reason `COUNT_CORRECTION` referencing the count session, subject to the approval threshold (INV-011).
**INV-013-AC04** GIVEN an open count session THEN dispensing at that location is allowed but flagged, and movements during the count are listed so the variance can be interpreted.
**INV-013-AC05** GIVEN posting THEN the session becomes immutable.
**Data** `StockCount`, `StockCountLine`.
**Test** Variance arithmetic; movements-during-count reporting.

**INV-014 · Stock ledger / movement history · V1 · P0 · `PHARMACIST`,`FACILITY_ADMIN`,`SUPERVISOR`**
**Release** V1
**Epic** INV
**Priority** P0
**Persona** `PHARMACIST`,`FACILITY_ADMIN`,`SUPERVISOR`
**INV-014-AC01** GIVEN a product THEN a chronological ledger shows every movement with date/time, type (`IN_GRN`, `OUT_DISPENSE`, `OUT_SALE`, `TRANSFER_IN/OUT`, `ADJUSTMENT`, `REVERSAL`), quantity, batch, location, running balance, actor and source reference (GRN, dispense, sale, adjustment, count).
**INV-014-AC02** GIVEN the ledger THEN the running balance recomputed from zero equals the current balance (asserted by test and by a nightly job).
**INV-014-AC03** GIVEN any user with `inventory.read` THEN they can filter by date range, batch and movement type, and export to CSV (audited).
**Test** Recomputation invariant.

**INV-015 · Suppliers list · V1 · P2 · `STORE_KEEPER`**
**Release** V1
**Epic** INV
**Priority** P2
**Persona** `STORE_KEEPER`
**INV-015-AC01** GIVEN a simple supplier record (name, contact person, phone, notes) THEN GRNs may reference it, and a supplier view lists all GRNs received from them.
**INV-015-AC02** GIVEN no supplier record THEN free-text supplier names remain permitted on GRNs.
**OOS** Payables, purchase orders, supplier performance analytics.

**INV-016 · FEFO deviation report · V1 · P2 · `SUPERVISOR`,`FACILITY_ADMIN`**
**Release** V1
**Epic** INV
**Priority** P2
**Persona** `SUPERVISOR`,`FACILITY_ADMIN`
**INV-016-AC01** GIVEN dispenses where a non-earliest batch was chosen THEN a report lists them with product, chosen batch, earliest available batch, reason, pharmacist and date, so the practice can be reviewed.
**Dep** INV-004.

---

---

### Epic DSP — Pharmacy Dispensing and Retail

**DSP-001 · Pharmacy dispensing queue · V1 · P0 · `PHARMACIST`**
**Release** V1
**Epic** DSP
**Priority** P0
**Persona** `PHARMACIST`
**DSP-001-AC01** GIVEN active prescriptions THEN the pharmacy queue lists them with patient name and number, prescriber, time prescribed, item count, payment status of any related charges, and age.
**DSP-001-AC02** GIVEN a prescription is `ACTIVE` and undispensed THEN it appears within 15 seconds of the encounter being signed.
**DSP-001-AC03** GIVEN a prescription is being prepared by another pharmacist THEN it shows as claimed with that person's name and cannot be opened for dispensing concurrently (409).
**DSP-001-AC04** GIVEN partially dispensed prescriptions THEN they appear in a separate "Partially dispensed" section with the outstanding items listed.
**DSP-001-AC05** GIVEN a prescription older than a configurable window (default 7 days) and undispensed THEN it moves to an "Expired/uncollected" section and stops cluttering the active queue while remaining retrievable.
**Perm** `dispense.queue.read`.
**Dep** RX-005.
**Test** Claim concurrency.

**DSP-002 · Open a prescription and check availability · V1 · P0 · `PHARMACIST`**
**Release** V1
**Epic** DSP
**Priority** P0
**Persona** `PHARMACIST`
**DSP-002-AC01** GIVEN a prescription is opened THEN each item shows the prescribed product, dose, frequency, duration, prescribed quantity, current usable stock (excluding expired), the FEFO-proposed batch(es), the unit price and the line total.
**DSP-002-AC02** GIVEN an item that is out of stock THEN it is marked `OUT_OF_STOCK` with a proposed action (partially dispense, substitute per DSP-006, or not dispense).
**DSP-002-AC03** GIVEN an item that is an external free-text medicine THEN it is displayed as "not stocked here — patient to obtain externally" and excluded from the dispensable set.
**DSP-002-AC04** GIVEN patient allergies THEN they are displayed prominently on the dispensing screen; **no automatic checking occurs**.
**DSP-002-AC05** GIVEN the prescription is opened THEN the pharmacist claims it and an access-audit event is written.
**Perm** `dispense.perform`.
**Test** Availability accuracy against usable stock.

**DSP-003 · Select batches (FEFO enforced) · V1 · P0 · `PHARMACIST`**
**Release** V1
**Epic** DSP
**Priority** P0
**Persona** `PHARMACIST`
**DSP-003-AC01** GIVEN a dispensable item THEN the FEFO batch is preselected and displayed with batch number and expiry.
**DSP-003-AC02** GIVEN the pharmacist changes the batch THEN only non-expired batches with stock are selectable and a reason is required (INV-004).
**DSP-003-AC03** GIVEN a quantity greater than the selected batch holds THEN the system splits across batches in expiry order and shows each batch and quantity explicitly on the screen and on the label.
**DSP-003-AC04** GIVEN any expired batch THEN it is not selectable anywhere (INV-005).
**Dep** INV-004, INV-005.
**Test** Split display and label accuracy.

**DSP-004 · Adjust dispensed quantity · V1 · P0 · `PHARMACIST`**
**Release** V1
**Epic** DSP
**Priority** P0
**Persona** `PHARMACIST`
**DSP-004-AC01** GIVEN a prescribed quantity of 15 and only 10 in stock THEN the pharmacist may dispense 10, and the item is recorded as partially dispensed with the outstanding 5 retained on the prescription (until dispensed or closed out at visit closure — REC-012/SM-06).
**DSP-004-AC02** GIVEN a dispensed quantity greater than prescribed THEN it is rejected with `EXCEEDS_PRESCRIBED_QUANTITY` (no over-dispensing without a new prescription).
**DSP-004-AC03** GIVEN a reduced quantity THEN the charge is calculated on the dispensed quantity only — if the line was already paid, the value difference is corrected through the BIL-010 CreditNote path (DSP-007 paid-revision rules), never by editing the paid line; the CreditNote reduces CURRENT AUTHORITATIVE AMOUNT DUE and recomputes the affected Invoice under SM-08, and any resulting refundable credit uses a bounded Refund rather than a whole-Payment reversal unless the entire Payment was wrong.
**DSP-004-AC04** GIVEN a quantity change THEN the reason is recorded when it is below the prescribed amount.
**Test** Charge-quantity coupling.

**DSP-005 · Record items not dispensed · V1 · P0 · `PHARMACIST`**
**Release** V1
**Epic** DSP
**Priority** P0
**Persona** `PHARMACIST`
**DSP-005-AC01** GIVEN an item that cannot be dispensed THEN the pharmacist records a reason (`OUT_OF_STOCK`, `PATIENT_DECLINED`, `PATIENT_CANNOT_AFFORD`, `PRESCRIBER_CANCELLED`, `NOT_STOCKED`, `OTHER` + note), and no charge is created for it.
**DSP-005-AC02** GIVEN a not-dispensed item THEN the prescribing clinician sees it in their worklist with the reason within 60 seconds, so they can substitute or advise.
**DSP-005-AC03** GIVEN all items are not dispensed THEN the prescription becomes `NOT_DISPENSED` (terminal) with reasons retained.
**DSP-005-AC04** GIVEN out-of-stock reasons THEN they are aggregated into a "missed sales / stock-out impact" report (REP-011).
**DSP-005-AC05** GIVEN an unpaid provisional Dispense in `AWAITING_PAYMENT` with the pharmacy entry `ON_HOLD(AWAITING_PAYMENT)` WHEN the patient declines, cannot afford or abandons the medicines before payment/handover THEN, as one consistent product outcome: the Dispense moves `AWAITING_PAYMENT → CANCELLED` with a mandatory reason from the same vocabulary above; **no stock movement occurs**; the unpaid medicine invoice lines are voided with a reason referencing the cancelled provisional Dispense (BIL-004); the pharmacy queue entry moves `ON_HOLD → CANCELLED` with the corresponding abandonment reason; any cashier queue entry created solely for those medicine charges is `CANCELLED` when no other payable gated lines remain (it stays active otherwise); and the prescription consequence is `NOT_DISPENSED` with item-level reasons if nothing was ever supplied, or retained `PARTIALLY_DISPENSED` (closing later via REC-012's atomic `PARTIALLY_DISPENSED_CLOSED`) if an earlier completed dispense supplied part of it — after which the visit may proceed toward REC-012 closure once other blockers clear. A `CANCELLED` Dispense is an immutable historical record: never deleted, never revived, never converted to `DISPENSED`; a returning patient gets a **new** provisional Dispense.
**Dep** REP-011.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Clinician notification; report aggregation.

**DSP-006 · Generic/brand substitution · V1 · P1 · `PHARMACIST`**
**Release** V1
**Epic** DSP
**Priority** P1
**Persona** `PHARMACIST`
**DSP-006-AC01** GIVEN a prescribed product THEN the pharmacist may dispense a different product only when it is flagged as an equivalent (same generic name, same strength, same form) or when explicitly authorised by the prescriber.
**DSP-006-AC02** GIVEN a substitution THEN the substituted product, the reason, and whether the prescriber was consulted (yes/no + who) are recorded, and both the prescribed and dispensed products appear on the label, the receipt and the record.
**DSP-006-AC03** GIVEN a substitution across a different strength or form THEN it is **blocked** and requires a new prescription.
**DSP-006-AC04** GIVEN a substitution THEN the prescriber sees it in their worklist.
**Test** Equivalence rule enforcement (same generic+strength+form only).

**DSP-007 · Generate dispensing charges · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** DSP
**Priority** P0
**Persona** `SYSTEM`
**DSP-007-AC01** GIVEN the pharmacist confirms the proposed dispensing basket THEN a stable provisional `Dispense` and its proposed `DispenseLine` records are created with patient/prescription, selected products, batch allocations, quantities and price snapshots; the invoice lines are created for exactly those quantities and reference the specific dispense-line source record/version. Under `MEDICINE=PAY_BEFORE`, provisional dispense creation and its required invoice lines are atomic: if line creation fails, no payment-gated/provisional dispense becomes actionable and an explicit billing/setup error is returned.
**DSP-007-AC02** GIVEN the same basket submitted twice with one idempotency key THEN one provisional dispense and one set of lines exist.
**DSP-007-AC03** GIVEN a change to the basket before final handover THEN the prior **unpaid** invoice lines are voided, their historical dispense-line source/version remains linked, and replacement lines reference distinct new/current dispense-line source records/versions; both actions are audited. **Paid lines are never edited or voided** (BIL-004): (a) *non-financial batch reselection* — after payment but before handover, changing only the batch allocation while keeping the same product, strength/form, quantity, unit price and total requires no invoice/payment correction; the allocation is versioned and audited, the new batch must pass availability, expiry and FEFO/authorisation rules, and no stock moves until DSP-009; (b) *financial basket revision* — any change to product, quantity, unit price or total charged value uses existing correction mechanisms: a BIL-010 credit note against the original paid line/source for removed or reduced undelivered value, and new invoice lines referencing the new DispenseLine source/version for replacement/additional value (BIL-013 uniqueness continues to hold per source version). If the new total exceeds the covered value, the additional balance is due, the pharmacy entry is/remains `ON_HOLD(AWAITING_PAYMENT)` with a cashier entry `WAITING` and handover blocked until cleared (then the same entry `READY_TO_RESUME`); if equal, no additional payment is required and the entry may be/become `READY_TO_RESUME`; if less, the CreditNote creates a refundable credit; use the BIL-010/PAY-008 bounded Refund path, which references the CreditNote and affected Invoice/PaymentAllocation context, reduces only that refundable amount, leaves the original Payment CONFIRMED and unrelated allocations, Invoices, and service gates unchanged, and remains visibly pending where no authorised supported refund method exists and is not retained as general-purpose reusable patient credit unless an existing facility-credit policy explicitly authorises it. Use full Payment reversal only when the entire Payment itself was wrong; the original Payment is never edited. Historical paid/credited lines remain auditable, and no stock OUT occurs before the final DSP-009 confirmation.
**DSP-007-AC04** GIVEN a retail sale (DSP-013) THEN charges are created identically without a prescription reference.
**Dep** BIL-001.
**Test** Basket-edit line hygiene.

**DSP-008 · Payment gate for medicines · V1 · P0 · `SYSTEM`; secondary `CASHIER`,`PHARMACIST`**
**Release** V1
**Epic** DSP
**Priority** P0
**Persona** `SYSTEM`; secondary `CASHIER`,`PHARMACIST`
**DSP-008-AC01** GIVEN `MEDICINE=PAY_BEFORE` THEN the stable provisional dispense record exists in `AWAITING_PAYMENT` with its stable dispense-line invoice sources, stock is **not** deducted, and the pharmacist cannot confirm handover until the related lines are paid; the screen shows the outstanding amount and the invoice number to give the patient. **Patient movement:** the pharmacy queue entry moves `IN_SERVICE → ON_HOLD` with `hold_reason=AWAITING_PAYMENT` and `hold_ref` = the invoice/provisional dispense, and a `QueueEntry(CASHIER)=WAITING` becomes the patient's active current location — the held pharmacy entry is the return obligation (QUE-006 coexistence rules apply; the same entry is reused, never duplicated).
**DSP-008-AC02** GIVEN a required payment-gate line is absent THEN the provisional dispense cannot become actionable.
**DSP-008-AC03** GIVEN the cashier records payment THEN the same dispense becomes confirmable within 15 seconds, the cashier entry completes, and the **same** pharmacy entry moves `ON_HOLD → READY_TO_RESUME` (no second pharmacy entry is created); at handover the pharmacist resumes it (`READY_TO_RESUME → IN_SERVICE`) and confirms (DSP-009).
**DSP-008-AC04** GIVEN `PAY_AFTER` THEN no payment hold is required: the same stable provisional dispense may be confirmed immediately (`IN_SERVICE → COMPLETED` at handover while the dispense is finalised) and the charge remains outstanding on the visit invoice.
**DSP-008-AC05** GIVEN an override by `billing.gate.override` THEN the dispense proceeds without the hold, the charge remains outstanding, and actor + reason are audited.
**DSP-008-AC06** GIVEN the patient declines or cannot pay after the provisional dispense exists THEN the abandonment path of DSP-005 applies as one consistent product outcome (`AWAITING_PAYMENT → CANCELLED`, lines voided, entries terminal).
**DSP-008-AC07** GIVEN a pharmacist who also holds `CASHIER` THEN they may take payment in the same session; the payment and the dispense are separate audited records.
**Dep** TEN-006, PAY-012.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** No-stock-deduction-before-payment assertion.

**DSP-009 · Confirm dispense (handover) · V1 · P0 · `PHARMACIST`**
**Release** V1
**Epic** DSP
**Priority** P0
**Persona** `PHARMACIST`
**Story** As a pharmacist I want to confirm that the medicines were physically handed over, which is the moment stock leaves.
**DSP-009-AC01** GIVEN a payment-cleared (or non-gated) provisional basket WHEN the pharmacist confirms THEN, as one consistent product outcome, the **existing** stable `Dispense` is finalised: `AWAITING_PAYMENT → DISPENSED` where gated; its lines, batches and quantities are confirmed; stock ledger OUT entries are written; balances decrease; the prescription state updates to `DISPENSED` or `PARTIALLY_DISPENSED`; the pharmacy queue entry completes (`IN_SERVICE → COMPLETED` — the held-then-resumed **same** entry under pay-before, or the direct entry under pay-after); the dispenser identity and timestamp are recorded; and the record becomes immutable. No second dispense is created at handover.
**DSP-009-AC02** GIVEN insufficient stock at confirmation THEN the entire product outcome fails with no partial effect and the pharmacist reselects.
**DSP-009-AC03** GIVEN confirmation THEN the label(s) and receipt become printable.
**DSP-009-AC04** GIVEN a duplicate confirmation with the same idempotency key THEN exactly one dispense exists and stock is deducted once.
**DSP-009-AC05** GIVEN confirmation THEN an audit event references the immutable Dispense/DispenseLine/StockMovement records and their content hashes; patient-linked medicine, batch and quantity details remain in the protected domain records.
**Perm** `dispense.perform`.
**Data** `Dispense`, `DispenseLine`, `StockLedger`, `Prescription.state`.
**Test** consistency under injected failure; idempotency.

**DSP-010 · Print dispensing label · V1 · P0 · `PHARMACIST`**
**Release** V1
**Epic** DSP
**Priority** P0
**Persona** `PHARMACIST`
**DSP-010-AC01** GIVEN a confirmed dispense THEN a label per item is printable containing: facility name, patient name, date, product name and strength, quantity dispensed, the sig in plain language (e.g. "Take ONE tablet THREE times a day for 5 days"), any product instruction (PHM-008), batch number and expiry, and the dispenser's initials.
**DSP-010-AC02** GIVEN a syrup or suspension THEN the label includes the volume and the measuring instruction where provided.
**DSP-010-AC03** GIVEN a reprint THEN it is permitted and audited.
**DSP-010-AC04** GIVEN a label printer is unavailable THEN a compact A5 "medicines given" sheet can be printed instead, listing all items.
**Dep** TEN-003, RCP-003, RCP-004.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Sig rendering from structured fields; snapshot per layout.

**DSP-011 · Record counselling and receiver · V1 · P1 · `PHARMACIST`**
**Release** V1
**Epic** DSP
**Priority** P1
**Persona** `PHARMACIST`
**DSP-011-AC01** GIVEN handover THEN the pharmacist records who received the medicines (`PATIENT`, `GUARDIAN`, `RELATIVE` + name) and ticks the counselling points covered from a facility-configurable list (dose, timing, food, storage, side-effects to watch, completion of course).
**DSP-011-AC02** GIVEN counselling is not recorded THEN the dispense still completes but the omission is reported in REP-011.
**DSP-011-AC03** GIVEN a guardian receiving on behalf of a patient THEN their name is stored and printed on the receipt.
**Data** `Dispense.received_by_*`, `counselling_points[]`.
**OOS** Counselling content library.

**DSP-012 · Dispensing history · V1 · P1 · `PHARMACIST`,`CLINICIAN`**
**Release** V1
**Epic** DSP
**Priority** P1
**Persona** `PHARMACIST`,`CLINICIAN`
**DSP-012-AC01** GIVEN a patient THEN all dispenses are listed with date, items, quantities, batches, dispenser and prescriber, filtered by date range.
**DSP-012-AC02** GIVEN a clinician THEN they see dispensing history in the encounter context (ENC-010 prefill source).
**DSP-012-AC03** GIVEN a batch recall scenario THEN the pharmacist can search dispenses by batch number to identify affected patients.
**Perm** `dispense.read`.
**Test** Batch-based lookup.

**DSP-013 · Over-the-counter retail sale · V1 · P0 · `PHARMACIST`**
**Release** V1
**Epic** DSP
**Priority** P0
**Persona** `PHARMACIST`
**Story** As a pharmacist I want to sell directly to a walk-in customer without a clinical visit, because that is a large part of daily revenue.
**Flow** New sale → optional customer (existing patient, or name-only, or anonymous) → add products with quantity (FEFO batches) → totals → payment (cash/manual MoMo) → confirm → stock deducted, receipt printed.
**DSP-013-AC01** GIVEN an anonymous sale THEN no patient record is required and the sale completes with a receipt.
**DSP-013-AC02** GIVEN a prescription-only product (PHM-001 flag) THEN selling it requires a valid linked prescription; the pharmacist reason/acknowledgement exception is not active while OD-PH8 is BLOCKED (OD-13 remains OPEN).
**DSP-013-AC03** GIVEN a controlled product THEN the sale is refused (RX-008).
**DSP-013-AC04** GIVEN a sale THEN it creates an invoice, a payment and a receipt with the same rigour as clinical billing, and deducts stock as one consistent product outcome.
**DSP-013-AC05** GIVEN a sale to an identified patient THEN it appears in their dispensing history.
**Dep** INV-012, PAY-002, RCP-001, BIL-002.
**Test** Anonymous-sale completeness; POM control.

**DSP-014 · Dispensing log for inspection · V1 · P1 · `PHARMACIST`,`FACILITY_ADMIN`**
**Release** V1
**Epic** DSP
**Priority** P1
**Persona** `PHARMACIST`,`FACILITY_ADMIN`
**DSP-014-AC01** GIVEN a date range THEN a chronological dispensing log can be produced and printed/exported containing: date/time, patient name or "OTC", product, strength, quantity, batch, expiry, prescriber (or "OTC"), dispenser, and prescription reference — the fields a National Drug Authority inspection or an internal audit would expect from a dispensing register.
**DSP-014-AC02** GIVEN the export THEN it is audited (AUD-009).
**DSP-014-AC03** GIVEN controlled medicines THEN they are absent because they are unsupported (RX-008), and the log states this explicitly so no one assumes coverage.
**Dep** REP-011, RCP-003.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Field completeness; export audit.

**DSP-015 · Expired-stock dispensing is impossible (dispense-path assertion) · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** DSP
**Priority** P0
**Persona** `SYSTEM`
**DSP-015-AC01** GIVEN every dispensing and sale entry point, and every structured issue/use of a KlinKlik-managed procedure consumable, THEN expired batches are absent from selection and refused by the API (INV-005). Free-text documentation for externally sourced/non-inventory procedure items is not a stock issue path and carries no claimed expiry enforcement.
**DSP-015-AC02** GIVEN a dispense prepared before midnight and confirmed after a batch expires THEN confirmation is refused and the pharmacist must reselect.
**DSP-015-AC03** GIVEN a test suite THEN it asserts refusal across all KlinKlik-managed stock entry points for all roles.
**Dep** INV-005.
**Test** Midnight-boundary case.

**DSP-016 · Reverse or correct a dispense · V1 · P1 · `PHARMACIST` with `SUPERVISOR` approval**
**Release** V1
**Epic** DSP
**Priority** P1
**Persona** `PHARMACIST` with `SUPERVISOR` approval
**DSP-016-AC01** GIVEN a dispense recorded in error (wrong patient, wrong product) and the medicines are physically returned THEN a reversal creates compensating stock IN entries referencing the original dispense, marks the dispense `REVERSED` with a mandatory reason, and either voids the unpaid charge or triggers a credit/refund path (PAY-008) if paid.
**DSP-016-AC02** GIVEN medicines that were **not** returned THEN reversal is refused and the correction must be handled as a write-off (INV-011) so stock records remain truthful.
**DSP-016-AC03** GIVEN a reversal THEN the original record is retained in full and both records are linked and audited.
**DSP-016-AC04** GIVEN a reversal THEN returned stock re-enters the **same batch identity**, but while OD-PH5 is BLOCKED every returned quantity lands in quarantine/non-usable stock and cannot increase usable availability, whether expired or unexpired. Expired returned stock can never become usable under any later policy; return-to-resale for unexpired stock is unavailable unless OD-PH5 is authoritatively resolved through Product Spec change control.
**Perm** `dispense.reverse`.
**Test** Returned-vs-not-returned branches; financial consequence.

---

---

### Epic BIL — Billing and Invoicing

**BIL-001 · Automatic charge capture from clinical events · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** BIL
**Priority** P0
**Persona** `SYSTEM`
**Story** As a facility I want every chargeable act to raise a charge automatically so we stop losing revenue to forgetfulness.
**BIL-001-AC01** GIVEN a chargeable event (every ordinary chargeable OPD consultation at check-in — REC-001; the delayed consultation financial-completion event for an existing TRI-013 emergency Visit; lab order — LAB-004; procedure order — DX-005; dispense/sale — DSP-007) THEN an invoice line is created on the current Visit's open Invoice (or a new Invoice belonging to that current Visit if none exists) using the source event's stable source record/version. TRI-013 emergency initiation, patient merge, and Encounter signing are not charge events; only its authorised later financial completion creates the consultation line/Invoice, exactly once. A standalone Invoice is used only when the supplied story explicitly permits a no-Visit transaction, including BIL-002-AC02.
**BIL-001-AC02** GIVEN the clinical event fails THEN no charge is created.
**BIL-001-AC03** GIVEN the event's charge is required to enforce a `PAY_BEFORE` gate THEN the source/business record and required charge line are created as one consistent product outcome; charge failure aborts the initiating operation with an explicit billing/setup error and leaves no actionable gated service state.
**BIL-001-AC04** GIVEN the event is `PAY_AFTER` or ungated and charge creation fails THEN the clinical event may succeed only with guaranteed billing reconciliation, and the missing charge appears on the unbilled-events exception report (REP-007) within 15 minutes.
**BIL-001-AC05** GIVEN any charge THEN it records `source_type`, `source_id`, the price snapshot, the service/product reference, the gate policy at charge time, and the creating actor.
**Data** `Invoice`, `InvoiceLine`.
**Audit** Each line with source.
**Test** Failure-mode reconciliation; no orphan charges.

**BIL-002 · One open invoice per visit · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** BIL
**Priority** P0
**Persona** `SYSTEM`
**BIL-002-AC01** GIVEN a visit THEN at most one invoice is in a non-terminal state at any time, accumulating consultation, lab, procedure and medicine lines; if the Visit has no Invoice yet, its next charge creates the Visit-linked Invoice, and LAB_ONLY never uses a standalone Invoice.
**BIL-002-AC02** GIVEN a retail sale with no visit THEN a standalone invoice is created.
**BIL-002-AC03** GIVEN a concurrent charge from two sources THEN both lines land on the same invoice without duplication or conflict failure (conflict-safe retry handling).
**BIL-002-AC04** GIVEN an invoice THEN its displayed GROSS INVOICE TOTAL always equals the sum of its non-voided InvoiceLines (asserted by test and a nightly integrity job); any CURRENT AUTHORITATIVE AMOUNT DUE after valid CreditNotes/discounts/waivers is displayed separately and does not rewrite or void the original lines.
**Test** Concurrency; arithmetic invariant.

**BIL-003 · Add a manual invoice line · V1 · P1 · `CASHIER`,`FACILITY_ADMIN`**
**Release** V1
**Epic** BIL
**Priority** P1
**Persona** `CASHIER`,`FACILITY_ADMIN`
**BIL-003-AC01** GIVEN a service in the catalogue THEN a cashier may add it manually to a visit's invoice with a quantity, and the price is taken from the catalogue (not typed).
**BIL-003-AC02** GIVEN a service not in the catalogue THEN a free-text line with a typed amount requires `billing.manual_line` and a mandatory description and reason, and such lines are listed on a monthly review report.
**BIL-003-AC03** GIVEN any manual line THEN it is audited with actor and reason.
**Test** Free-text line reporting.

**BIL-004 · Void an invoice line · V1 · P0 · `CASHIER`,`FACILITY_ADMIN`**
**Release** V1
**Epic** BIL
**Priority** P0
**Persona** `CASHIER`,`FACILITY_ADMIN`
**BIL-004-AC01** GIVEN an unpaid line THEN it may be voided with a mandatory reason; the line remains visible marked `VOID` with strike-through and is excluded from totals — including the unpaid medicine lines of a pre-handover-cancelled provisional Dispense, voided with a reason referencing that cancellation (DSP-005).
**BIL-004-AC02** GIVEN a paid or partially paid line THEN voiding is refused; a credit note (BIL-010 — the path for paid pre-handover basket reductions, DSP-007) or payment reversal (PAY-008) is required.
**BIL-004-AC03** GIVEN voiding a lab or medicine line THEN the corresponding clinical record's payment gate re-evaluates (e.g. the lab item may return to `AWAITING_PAYMENT` or become gate-free).
**BIL-004-AC04** GIVEN voiding THEN it is audited with before/after totals.
**Test** Gate re-evaluation.

**BIL-005 · Issue / finalise an invoice · V1 · P0 · `SYSTEM`,`CASHIER`**
**Release** V1
**Epic** BIL
**Priority** P0
**Persona** `SYSTEM`,`CASHIER`
**BIL-005-AC01** GIVEN an invoice with at least one line THEN it is `ISSUED` and visible to the cashier with a facility invoice number (TEN-007).
**BIL-005-AC02** GIVEN an issued invoice THEN new lines may still be added while it is unpaid or partially paid (outpatient reality), and every addition updates the total and is audited.
**BIL-005-AC03** GIVEN a fully paid invoice THEN adding a line moves it back to `PARTIALLY_PAID` with the new balance, and the cashier and the patient's balance display update immediately.
**Test** Post-payment line addition.

**BIL-006 · Cashier's awaiting-payment list · V1 · P0 · `CASHIER`**
**Release** V1
**Epic** BIL
**Priority** P0
**Persona** `CASHIER`
**BIL-006-AC01** GIVEN issued invoices with an outstanding balance THEN they appear in the cashier's list with patient name and number, invoice number, GROSS INVOICE TOTAL, CURRENT AUTHORITATIVE AMOUNT DUE, effective applied value, outstanding balance, any visible REFUNDABLE CREDIT, the services included (grouped by type), the age of the invoice, and where the patient currently is (QUE-010).
**BIL-006-AC02** GIVEN a new charge is created anywhere in the facility THEN it appears in the cashier's list within 15 seconds.
**BIL-006-AC03** GIVEN a gated service blocking a patient (lab awaiting payment, medicines awaiting payment) THEN the row is marked as blocking so the cashier prioritises it.
**BIL-006-AC04** GIVEN a search by patient name, number or invoice number THEN the invoice is found immediately.
**Perm** `invoice.read`.
**Test** Freshness and blocking indicators.

**BIL-007 · View invoice detail · V1 · P0 · `CASHIER`,`FACILITY_ADMIN`,`SUPERVISOR`; limited `RECEPTIONIST`**
**Release** V1
**Epic** BIL
**Priority** P0
**Persona** `CASHIER`,`FACILITY_ADMIN`,`SUPERVISOR`; limited `RECEPTIONIST`
**BIL-007-AC01** GIVEN an invoice THEN its detail shows every line with description, quantity, unit price, line total, source (which order/dispense created it), status, plus GROSS INVOICE TOTAL, CURRENT AUTHORITATIVE AMOUNT DUE, effective applied value, payments and PaymentAllocations with method, reference, date and receipt number, CreditNotes, Refunds, any REFUNDABLE CREDIT, and the outstanding balance.
**BIL-007-AC02** GIVEN a receptionist THEN they see totals and balance but not clinical descriptions beyond service names.
**BIL-007-AC03** GIVEN a voided line THEN it is displayed with its reason and the voiding actor.
**Test** Role-scoped payload.

**BIL-008 · Patient balance across visits · V1 · P1 · `CASHIER`,`RECEPTIONIST`**
**Release** V1
**Epic** BIL
**Priority** P1
**Persona** `CASHIER`,`RECEPTIONIST`
**BIL-008-AC01** GIVEN a patient with unpaid invoices from previous visits THEN their total outstanding balance is displayed on the patient header for finance-capable roles and at check-in (REC-001).
**BIL-008-AC02** GIVEN a payment THEN it may be allocated across invoices oldest-first or explicitly chosen (PAY-005).
**BIL-008-AC03** GIVEN a facility policy requiring settlement before new services THEN check-in shows a blocking warning that `FACILITY_ADMIN` can override with a reason (BIL-014).
**Test** Multi-invoice arithmetic.

**BIL-009 · Discounts, waivers and exemptions · V1 · P1 · `FACILITY_ADMIN`,`SUPERVISOR`**
**Release** V1
**Epic** BIL
**Priority** P1
**Persona** `FACILITY_ADMIN`,`SUPERVISOR`
**BIL-009-AC01** GIVEN authority THEN a discount may be applied to a line or an invoice as a percentage or a fixed amount, with a mandatory reason from a configurable list (`STAFF`, `INDIGENT`, `GOODWILL`, `PROMOTION`, `MANAGEMENT_DECISION`, `OTHER` + note).
**BIL-009-AC02** GIVEN a discount THEN the original amount, the discount and the net are all retained and printed, so nothing is silently rewritten.
**BIL-009-AC03** GIVEN a full waiver THEN the invoice reaches zero balance through a waiver record, **never** by deleting lines.
**BIL-009-AC04** GIVEN a discount above a configurable threshold THEN it requires `FACILITY_ADMIN`.
**BIL-009-AC05** GIVEN any discount THEN it is audited and appears on a discounts report (REP-008).
**Data** `InvoiceDiscount`.
**Test** Threshold enforcement; report totals.

**BIL-010 · Credit note · V1 · P1 · `FACILITY_ADMIN`**
**Release** V1
**Epic** BIL
**Priority** P1
**Persona** `FACILITY_ADMIN`
**BIL-010-AC01** GIVEN a paid line for a service that was not delivered (cancelled lab test after payment, reversed dispense) THEN an attributable CreditNote is created against the affected Invoice and original paid InvoiceLine/source with a credited amount, mandatory reason, actor/authority, authoritative time, and its own number; it cannot exceed the remaining creditable value or double-credit, creation/retry follows the existing duplicate/single-winner guarantees, reduces CURRENT AUTHORITATIVE AMOUNT DUE without editing the original line/Payment/PaymentAllocation, and may create explicit REFUNDABLE CREDIT.
**BIL-010-AC02** GIVEN a CreditNote THEN the original Invoice, InvoiceLine, Payment, and PaymentAllocation history remains retained and unedited while the current amount due and Invoice state recompute under SM-08; the GROSS INVOICE TOTAL remains the sum of non-voided lines, and the CreditNote is displayed separately and printable.
**BIL-010-AC03** GIVEN REFUNDABLE CREDIT THEN a full Payment reversal is used only when the entire Payment itself was wrong; otherwise a bounded Refund record references the CreditNote, original Payment, specific PaymentAllocation/Invoice context, and refunding cashier/shift, cannot exceed currently refundable credit, leaves the original Payment CONFIRMED and unrelated allocations/Invoices/gates unchanged, and remains visibly pending if no authorised supported refund method exists; unless an existing facility-credit policy explicitly authorises reusable patient credit, the amount remains a pending refund obligation and is not general-purpose reusable credit; the original Payment is never edited and no provider integration is invented.
**Test** Ledger consistency between invoice, payment and credit note.

**BIL-011 · Invoice line grouping by category on print · V1 · P0 · `CASHIER`**
**Release** V1
**Epic** BIL
**Priority** P0
**Persona** `CASHIER`
**BIL-011-AC01** GIVEN an invoice with mixed lines THEN the printed invoice groups them under Consultation, Laboratory, Procedures and Medicines with subtotals, then the grand total, amount paid and balance.
**BIL-011-AC02** GIVEN medicines THEN each line shows the product, strength, quantity and unit price.
**BIL-011-AC03** GIVEN laboratory THEN each test is named individually.
**Dep** RCP-002.
**Test** Grouping snapshot.

**BIL-012 · Print or reprint an invoice · V1 · P1 · `CASHIER`**
**Release** V1
**Epic** BIL
**Priority** P1
**Persona** `CASHIER`
**BIL-012-AC01** GIVEN an invoice THEN it can be printed showing the facility header, invoice number, date, patient identity, grouped lines, totals, payments and balance, plus "This is not a receipt" when unpaid.
**BIL-012-AC02** GIVEN a reprint THEN it is audited.
**Dep** TEN-003, RCP-003.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Unpaid-marking.

**BIL-013 · Prevent duplicate charges · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** BIL
**Priority** P0
**Persona** `SYSTEM`
**BIL-013-AC01** GIVEN a charge source (order item, specific dispense-line record/version, visit consultation) THEN a uniqueness rule on `(invoice, source_type, source_id)` prevents a second line for that exact source.
**BIL-013-AC02** GIVEN a retried request THEN the constraint plus idempotency returns the original line without error.
**BIL-013-AC03** GIVEN a basket edit then the voided line remains linked to its original dispense-line source/version and the replacement line references a distinct current source record/version, so the uniqueness rule permits the auditable replacement without duplicate-charging either source.
**BIL-013-AC04** GIVEN a legitimate repeat of the same service (a second CBC the same day) THEN it has a distinct source ID and is charged separately.
**BIL-013-AC05** GIVEN a duplicate-charge attempt THEN it is logged for monitoring.
**Test** Constraint behaviour under retry and under legitimate repeats.

**BIL-014 · Outstanding balance at visit closure · V1 · P0 · `CASHIER`,`FACILITY_ADMIN`**
**Release** V1
**Epic** BIL
**Priority** P0
**Persona** `CASHIER`,`FACILITY_ADMIN`
**BIL-014-AC01** GIVEN a visit with an outstanding balance WHEN closure is attempted THEN it is blocked with the amount and the blocking lines listed.
**BIL-014-AC02** GIVEN `FACILITY_ADMIN` authority THEN the visit may be closed with the balance recorded as a debt/credit-sale with a mandatory reason and a follow-up flag, and the amount appears on the debtors report (REP-008).
**BIL-014-AC03** GIVEN a waiver instead THEN BIL-009 applies and the balance becomes zero through a waiver record.
**BIL-014-AC04** GIVEN any of these THEN the audit records which path was used, by whom and why.
**Dep** REC-012.
**Test** All three closure paths.

---

---

### Epic PAY — Payments

**PAY-001 · Payment methods configuration · V1 · P0 · `FACILITY_ADMIN`**
**Release** V1
**Epic** PAY
**Priority** P0
**Persona** `FACILITY_ADMIN`
**PAY-001-AC01** GIVEN the facility THEN the enabled payment methods are `CASH` (always), `MOBILE_MONEY_MANUAL` (with a required transaction-reference field and an optional provider label such as MTN/Airtel), and up to three facility-defined manual methods (e.g. `BANK_DEPOSIT_SLIP`, `POS_CARD_TERMINAL`, `COMPANY_ACCOUNT`) each with a configurable reference-required flag.
**PAY-001-AC02** GIVEN a method THEN it can be deactivated without affecting historical payments.
**PAY-001-AC03** GIVEN no direct integration THEN the UI never claims a payment is verified with a provider — mobile money references are **operator-entered evidence only**.
**Data** `PaymentMethodConfig`.
**OOS** MoMo/bank/card APIs, automatic reconciliation.
**Test** Reference-required enforcement.

**PAY-002 · Record a payment · V1 · P0 · `CASHIER`; secondary `PHARMACIST` (retail)**
**Release** V1
**Epic** PAY
**Priority** P0
**Persona** `CASHIER`; secondary `PHARMACIST` (retail)
**Story** As a cashier I want to record money received against an invoice so the patient can proceed and our books are right.
**Pre** Invoice with a balance; `payment.record`; an open shift if shifts are enabled (PAY-009).
**Flow** Open the invoice → enter the amount received → select the method → enter the reference if required → optionally enter the amount tendered for cash to compute change → confirm → payment recorded, allocated (PAY-005), receipt generated and printed (RCP-001), gates released (PAY-012).
**PAY-002-AC01** GIVEN an invoice with a balance of UGX 45,000 and cash of 50,000 tendered THEN the payment records 45,000 received with 5,000 change displayed, and the invoice becomes `PAID`.
**PAY-002-AC02** GIVEN a mobile-money payment without a reference when the method requires one THEN it is rejected with `REFERENCE_REQUIRED`.
**PAY-002-AC03** GIVEN an amount exceeding the balance THEN it is rejected unless the facility allows credit balances (default: not allowed; the cashier must adjust the amount). Payment confirmation rechecks the invoice/allocation state, recomputes the outstanding balance, validates the proposed allocation, then creates the payment/allocation and updates invoice state in one consistent product outcome.
**PAY-002-AC04** GIVEN two cashiers each see UGX 45,000 outstanding and both submit UGX 45,000 THEN exactly one commits; the later request re-evaluates and returns 409 `BALANCE_CHANGED` with the current balance.
**PAY-002-AC05** GIVEN a payment THEN it is immutable; corrections require reversal (PAY-008).
**PAY-002-AC06** GIVEN a duplicate submission with the same idempotency key THEN exactly one payment exists and one receipt is issued.
**PAY-002-AC07** GIVEN a payment THEN the audit records amount, method, reference, actor, shift, invoice and allocations.
**PAY-002-AC08** GIVEN a recorded payment THEN any gated service is released within 15 seconds.
**Perm** `payment.record`.
**Data** `Payment`, `PaymentAllocation`, `Receipt`.
**Test** Idempotency; over-payment rule; gate release timing.

**PAY-003 · Partial payment · V1 · P0 · `CASHIER`**
**Release** V1
**Epic** PAY
**Priority** P0
**Persona** `CASHIER`
**PAY-003-AC01** GIVEN a balance of 60,000 and 20,000 paid THEN the invoice becomes `PARTIALLY_PAID` with a 40,000 balance, a receipt is issued for 20,000 showing the remaining balance, and the patient can return to pay the rest.
**PAY-003-AC02** GIVEN multiple partial payments THEN each has its own receipt and the invoice shows the full payment history.
**PAY-003-AC03** GIVEN partial payment under a `PAY_BEFORE` gate THEN only the specific gated lines that are fully covered by the allocation are released (PAY-005/LAB-005).
**Test** Line-level release from partial payment.

**PAY-004 · Payment against multiple invoices · V1 · P2 · `CASHIER`**
**Release** V1
**Epic** PAY
**Priority** P2
**Persona** `CASHIER`
**PAY-004-AC01** GIVEN a patient with two outstanding invoices THEN one Payment may be allocated across both through explicit PaymentAllocations shown before confirmation and printed on the receipt; if that whole Payment is later reversed, every allocation and every affected Invoice is recomputed under SM-08 rather than only a selected primary Invoice.
**PAY-004-AC02** GIVEN no explicit allocation THEN the default is oldest-invoice-first.
**Dep** PAY-005.

**PAY-005 · Payment allocation rules · V1 · P0 · `SYSTEM`,`CASHIER`**
**Release** V1
**Epic** PAY
**Priority** P0
**Persona** `SYSTEM`,`CASHIER`
**PAY-005-AC01** GIVEN a payment THEN it is allocated to invoice lines with an explicit, deterministic and displayed rule: **gated unpaid lines that are currently blocking a service first (in the order the services were requested), then remaining lines oldest-first**.
**PAY-005-AC02** GIVEN the cashier wants a different allocation THEN they may allocate manually line by line before confirming. Allocation runs under the current invoice/allocation state: current outstanding balance and line allocations are recomputed before validation and commit.
**PAY-005-AC03** GIVEN allocation THEN each `PaymentAllocation` row records the Invoice line and amount, the sum of allocations equals the Payment amount exactly, and no line is over-allocated; allocation history remains attributable if its Payment is later fully reversed and becomes ineffective for current-balance purposes. If another payment changes the balance first and the requested allocation now exceeds it, the later request returns 409 `BALANCE_CHANGED` with the current outstanding balance and requires cashier re-entry/confirmation.
**PAY-005-AC04** GIVEN an allocation THEN it is displayed on the receipt so the patient knows what they have paid for.
**Test** Sum invariant; blocking-first ordering; manual override; two-cashier final-balance race (one commit, one 409 `BALANCE_CHANGED`).

**PAY-006 · Cash change calculation · V1 · P1 · `CASHIER`**
**Release** V1
**Epic** PAY
**Priority** P1
**Persona** `CASHIER`
**PAY-006-AC01** GIVEN cash tendered THEN change is computed and displayed prominently before confirmation and printed on the receipt; the stored payment amount is the amount **received against the invoice**, never the tendered amount.
**PAY-006-AC02** GIVEN tendered less than the amount being paid THEN it is rejected.
**Test** Stored-amount correctness.

**PAY-007 · Payment lookup and history · V1 · P0 · `CASHIER`,`FACILITY_ADMIN`**
**Release** V1
**Epic** PAY
**Priority** P0
**Persona** `CASHIER`,`FACILITY_ADMIN`
**PAY-007-AC01** GIVEN a date range, method, cashier or patient filter THEN matching payments are listed with time, patient, invoice, amount, method, reference, cashier, shift and receipt number, and can be exported (audited).
**PAY-007-AC02** GIVEN a receipt number THEN the payment is found directly.
**Perm** `payment.read`.
**Test** Filter correctness.

**PAY-008 · Payment reversal / correction · V1 · P0 · `SUPERVISOR`,`FACILITY_ADMIN`**
**Release** V1
**Epic** PAY
**Priority** P0
**Persona** `SUPERVISOR`,`FACILITY_ADMIN`
**Story** As a supervisor I want to reverse a payment recorded in error, in a way that leaves the original visible.
**PAY-008-AC01** GIVEN a payment THEN it can never be edited or deleted.
**PAY-008-AC02** GIVEN a full Payment reversal request with a mandatory reason (`WRONG_AMOUNT`, `WRONG_INVOICE`, `WRONG_PATIENT`, `DUPLICATE_ENTRY`, `SERVICE_NOT_RENDERED_REFUND`, `OTHER` + note) THEN one reversal record is created for the original Payment, ALL currently effective PaymentAllocations belonging to it become reversed/ineffective for current-balance purposes while their historical records remain attributable and retained, and EVERY Invoice touched by those allocations is independently recomputed for CURRENT AUTHORITATIVE AMOUNT DUE, CURRENT EFFECTIVE APPLIED VALUE, outstanding balance, and Invoice state under SM-08 as ISSUED, PARTIALLY_PAID, or PAID, never VOIDED through reversal. Every applicable gate associated with every affected allocation/Invoice is re-evaluated under the **undelivered-only principle** (PAY-012): only undelivered services may be re-gated — delivered clinical work, specimen custody, medicines handed over, and stock truth remain intact. A smaller CreditNote-driven refund is not this path and must not mark the whole Payment REVERSED.
**PAY-008-AC03** GIVEN a reversal THEN both the original receipt and the reversal are retained, a reversal note is printable, and the original receipt is marked reversed on reprint.
**PAY-008-AC04** GIVEN a cash Refund, including a bounded CreditNote-specific refund for refundable credit smaller than its originating Payment or where the Payment also covers unrelated valid Invoice(s)/lines, THEN it is recorded with the refunding cashier and shift so the drawer reconciles; in that CreditNote-specific case, a separate attributable Refund record is created against the CreditNote and specific affected Invoice/PaymentAllocation context, references the original Payment, cannot exceed current refundable credit, is recorded with the refunding cashier and shift so the drawer reconciles, reduces refundable-credit balance by the refund amount, leaves the original Payment CONFIRMED and unrelated allocations/Invoices/service gates unchanged, and remains visibly pending where no authorised supported refund method is available and is not general-purpose reusable patient credit unless an existing facility-credit policy explicitly authorises it; this is not a partial mutation of the Payment and does not create a PARTIALLY_REVERSED state.
**PAY-008-AC05** GIVEN a reversal after the shift is closed THEN it is recorded against the current open shift with a reference to the original shift, and both shift reports show it.
**PAY-008-AC06** GIVEN a reversal THEN it is a high-severity audit event and appears on the daily reversals report reviewed by the owner.
**Perm** `payment.reverse` (**not** granted to `CASHIER` by default).
**Test** Balance restoration; cross-shift accounting; gate re-evaluation.

**PAY-009 · Cashier shift open/close and reconciliation · V1 · P0 · `CASHIER`,`SUPERVISOR`**
**Release** V1
**Epic** PAY
**Priority** P0
**Persona** `CASHIER`,`SUPERVISOR`
**PAY-009-AC01** GIVEN a cashier starts work THEN they open a shift recording an opening float; payments they record are attributed to that shift.
**PAY-009-AC02** GIVEN shift close THEN the system shows expected totals by method (cash expected = float + cash received − cash refunds), the cashier enters the counted cash, and any variance is computed, requires a comment if non-zero, and is recorded.
**PAY-009-AC03** GIVEN a closed shift THEN it is immutable and a shift report is printable listing every transaction, totals by method, reversals and the variance.
**PAY-009-AC04** GIVEN an attempt to record a payment without an open shift when shifts are enabled THEN it is refused with `NO_OPEN_SHIFT`.
**PAY-009-AC05** GIVEN a shift left open past a configurable period THEN it appears on the supervisor dashboard, and `SUPERVISOR` may force-close it with a reason.
**PAY-009-AC06** GIVEN a variance beyond a configurable threshold THEN the supervisor is alerted.
**Data** `CashierShift`.
**Test** Expected-total arithmetic including reversals; force-close path.

**PAY-010 · Daily cash-up / handover · V1 · P1 · `SUPERVISOR`,`FACILITY_ADMIN`**
**Release** V1
**Epic** PAY
**Priority** P1
**Persona** `SUPERVISOR`,`FACILITY_ADMIN`
**PAY-010-AC01** GIVEN end of day THEN a facility-level summary aggregates all shifts: total collected by method, number of transactions, refunds/reversals, discounts and waivers granted, outstanding debts created, and the day's revenue by service group.
**PAY-010-AC02** GIVEN the summary THEN it is printable and exportable and reconciles exactly with the sum of shift reports (asserted by test).
**Dep** REP-006, REP-010.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Cross-report reconciliation.

**PAY-011 · Duplicate-payment prevention · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** PAY
**Priority** P0
**Persona** `SYSTEM`
**PAY-011-AC01** GIVEN a payment submitted twice due to a double click or a network retry THEN the idempotency key ensures one payment and one receipt.
**PAY-011-AC02** GIVEN two payments of the identical amount for the same invoice within 60 seconds by the same cashier without an idempotency match THEN a confirmation prompt appears warning of a possible duplicate, which the cashier must explicitly accept (some patients genuinely pay twice for two people).
**PAY-011-AC03** GIVEN two distinct cashiers concurrently attempt the final outstanding balance THEN invoice/allocation conflict handling permits only one payment to complete and the later request returns 409 `BALANCE_CHANGED` rather than creating an overpayment.
**PAY-011-AC04** GIVEN acceptance THEN the second payment is flagged `possible_duplicate` for the daily review report.
**Test** Both automatic and heuristic paths; distinct-cashier race.

**PAY-012 · Payment events release gated services · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** PAY
**Priority** P0
**Persona** `SYSTEM`
**PAY-012-AC01** GIVEN a payment that fully covers a gated lab item's required line THEN the item transitions `AWAITING_PAYMENT → READY_FOR_COLLECTION`, the cashier QueueEntry completes, and a patient-facing `QueueEntry(LAB)=WAITING` is created within 15 seconds; before payment, the unpaid lab worklist item is not a lab QueueEntry.
**PAY-012-AC02** GIVEN an ordinary gated service lacks its required charge line THEN it cannot be released/actionable. The sole supplied exception is TRI-013 `EMERGENCY_CARE_FIRST`: its consultation entry remains immediately actionable without a charge line while `EMERGENCY_FINANCIAL_SETUP_PENDING` is visible, later converges to the exact-one charge/Invoice outcome on the same Visit, and cannot close until that setup resolves; this exception grants no gate bypass to any other Visit or service.
**PAY-012-AC03** GIVEN a payment covering medicine lines THEN the same provisional dispense becomes confirmable within 15 seconds and a pharmacy entry held `ON_HOLD(AWAITING_PAYMENT)` becomes `READY_TO_RESUME` — the **same** entry is resumed, never duplicated (DSP-008).
**PAY-012-AC04** GIVEN a payment covering the consultation THEN any clinician-side warning clears (and a `WAITING_PAYMENT` queue entry becomes `WAITING`).
**PAY-012-AC05** GIVEN a reversal THEN gates re-evaluate under the **undelivered-only principle** — a reversal may re-gate only a service that has not yet been delivered; delivered services' clinical/stock records stand and only the financial state is restored. Every affected Invoice state is recomputed independently from CURRENT AUTHORITATIVE AMOUNT DUE and CURRENT EFFECTIVE APPLIED VALUE under SM-08 as ISSUED, PARTIALLY_PAID, or PAID; no affected Invoice becomes VOIDED through full Payment reversal. Specifically: **(lab, before collection — including `IN_SERVICE` at the lab service point with no specimen recorded)** opening/starting the lab queue entry does not itself constitute delivery; the decisive boundary is the item reaching `SAMPLE_COLLECTED` and/or a `LabSpecimen` custody record existing. If payment is reversed while no affected item has reached that boundary — including while the lab entry is `WAITING`, `CALLED` or `IN_SERVICE` — then collection is blocked immediately, any unsaved collection form is discarded uncommitted, no `LabSpecimen` is created and no collection event is audited as completed, the item returns `READY_FOR_COLLECTION → AWAITING_PAYMENT`, the active patient-facing lab queue entry is `CANCELLED` with reason `PAYMENT_REVERSED` (the `IN_SERVICE → CANCELLED` variant is narrowly guarded in SM-01), a `QueueEntry(CASHIER)=WAITING` is created and becomes the current operational location, the technician UI shows "Payment reversed — collection is blocked. Send patient to Cashier.", and no active lab queue entry remains (after repayment, cashier completes and a **new** Lab entry `WAITING` is created — the cancelled one is terminal — preserving the no-lab-queue-while-unpaid invariant); **(lab, at/after `SAMPLE_COLLECTED` or an existing specimen record)** the item never moves backward — `SAMPLE_COLLECTED` is never rolled back to `AWAITING_PAYMENT`, processing continues and only the balance is restored; any separate still-uncollected item that becomes unpaid must not be newly collected until its gate clears; **(consultation/triage gate, service not begun)** service begins at `IN_SERVICE`, so while the queue entry is `WAITING` **or `CALLED`** a reversal re-gates it as one consistent product outcome to `WAITING_PAYMENT` — for `CALLED` the soft call hold is released while `called_at`/`called_by`/attempt history are retained, Start is blocked with `PAYMENT_REQUIRED`, and after repayment the entry returns only to `WAITING` (the patient must be called again); entries already `IN_SERVICE`/`COMPLETED` never move backward and only the balance is restored; **(pharmacy, before handover)** the provisional dispense remains/returns `AWAITING_PAYMENT`, the pharmacy entry returns to (or remains) `ON_HOLD(AWAITING_PAYMENT)` — including `READY_TO_RESUME → ON_HOLD`, and if service had resumed `IN_SERVICE` without handover the pharmacist must explicitly acknowledge the reversal before any handover, which stays blocked, and the entry returns `ON_HOLD` with a cashier entry `WAITING` (no stock has moved); **(pharmacy, after `DISPENSED`)** the dispense, stock movements and prescription state are never automatically undone — financial reversal follows PAY-008 and any physical medicine return requires DSP-016. A full Payment reversal affects every PaymentAllocation of the Payment and every affected Invoice; every eligible undelivered gate associated with those allocations/Invoices is re-evaluated as part of the same outcome. A CreditNote-driven service correction follows the governing LAB/DSP/BIL story for the affected service; any remaining PAY_BEFORE service is actionable only when its CURRENT required charge remains covered after the financial correction. A CreditNote or bounded Refund does not re-gate unrelated services or mutate unrelated allocations/Invoices. Every re-gate raises a visible notice to the affected department.
**Dep** LAB-005, DSP-008, REC-001.
**Test** Event propagation latency and reversal behaviour.

**PAY-013 · Mobile money manual reference capture · V1 · P0 · `CASHIER`**
**Release** V1
**Epic** PAY
**Priority** P0
**Persona** `CASHIER`
**PAY-013-AC01** GIVEN a mobile-money payment THEN the cashier records the provider label, the transaction reference (validated for a minimum length and uniqueness within the facility over a rolling 90 days) and the payer phone number if given.
**PAY-013-AC02** GIVEN a duplicate reference within the window THEN a warning appears requiring confirmation, because duplicates usually indicate a mis-keyed or reused reference.
**PAY-013-AC03** GIVEN the reference THEN it prints on the receipt and appears in the payments-by-method report so manual reconciliation against the MoMo statement is possible.
**PAY-013-AC04** GIVEN the system THEN it never asserts that the transaction was verified with the provider.
**Test** Duplicate-reference warning; receipt content.

**PAY-014 · Payment permissions and segregation of duties · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** PAY
**Priority** P0
**Persona** `SYSTEM`
**PAY-014-AC01** GIVEN a `CASHIER` THEN they may record payments and print receipts but **not** reverse payments, apply discounts above the threshold, or void paid lines.
**PAY-014-AC02** GIVEN a user holding both `payment.record` and `payment.reverse` THEN the combination is permitted (small facilities) but is listed on the segregation-of-duties report (REP-013) for owner awareness.
**PAY-014-AC03** GIVEN any privileged financial action THEN it is audited with actor, reason and amount.
**Dep** AUTH-008, REP-013.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Capability matrix enforcement.

---

---

### Epic RCP — Receipts and Print

**RCP-001 · Generate and print a receipt · V1 · P0 · `CASHIER`,`PHARMACIST`**
**Release** V1
**Epic** RCP
**Priority** P0
**Persona** `CASHIER`,`PHARMACIST`
**RCP-001-AC01** GIVEN a recorded payment THEN a receipt is generated immediately with a unique facility receipt number, containing the facility header (name, address, phone, TIN), receipt number, date/time, patient name and number (or "walk-in" for anonymous sales), the items paid for with amounts (allocation from PAY-005), the total paid, the method and reference, the change given for cash, the remaining balance if any, the cashier's name, and the facility footer text.
**RCP-001-AC02** GIVEN the payment THEN the receipt prints automatically to the configured printer and can be reprinted.
**RCP-001-AC03** GIVEN a reprint THEN it is marked "DUPLICATE" and audited with actor and time.
**RCP-001-AC04** GIVEN a reversed payment THEN reprints are marked "REVERSED" with the reversal date.
**Data** `Receipt`.
**Test** Numbering uniqueness; duplicate/reversed markings.

**RCP-002 · Print layouts for 80mm thermal and A5/A4 · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** RCP
**Priority** P0
**Persona** `SYSTEM`
**RCP-002-AC01** GIVEN a receipt THEN an 80mm thermal layout is provided that prints legibly with a monochrome logo and no clipped content.
**RCP-002-AC02** GIVEN lab reports, invoices, prescriptions, consultation notes and ANC cards THEN A5 or A4 layouts are provided as appropriate.
**RCP-002-AC03** GIVEN any layout THEN page breaks preserve table headers and no content is lost at boundaries.
**RCP-002-AC04** GIVEN a printer that is unavailable THEN a print-preview view is shown that can be printed later or photographed, and the document is retrievable from the record at any time.
**Test** Snapshot tests per document per size; long-content page-break test.

**RCP-003 · Reprint with audit · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** RCP
**Priority** P0
**Persona** `SYSTEM`
**RCP-003-AC01** GIVEN any printable clinical or financial document THEN reprinting is permitted to authorised roles and every print and reprint writes an audit event with document type, record ID, actor, timestamp and copy number.
**RCP-003-AC02** GIVEN a document's print history THEN it is viewable by `SUPERVISOR`/`FACILITY_ADMIN`.
**RCP-003-AC03** GIVEN clinical documents THEN reprint counts appear in the access-review report (AUD-011).
**Dep** AUD-009.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Copy numbering.

**RCP-004 · Document header/footer service · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** RCP
**Priority** P0
**Persona** `SYSTEM`
**RCP-004-AC01** GIVEN any printable document THEN it renders the facility header from TEN-003 and a standard footer containing the page number, the generating user, the generation timestamp, and (for clinical documents) the phrase identifying the source system and record version.
**RCP-004-AC02** GIVEN a facility profile change THEN newly generated documents use the new values while previously generated PDFs stored on records (if any) remain as generated.
**Test** Header presence across all document types.

**RCP-005 · Printer configuration per workstation · V1 · P1 · `FACILITY_ADMIN`**
**Release** V1
**Epic** RCP
**Priority** P1
**Persona** `FACILITY_ADMIN`
**RCP-005-AC01** GIVEN a workstation THEN a default document-to-printer mapping (receipts → thermal, reports → A4) can be stored as a non-PHI local preference and applied through the browser print flow.
**RCP-005-AC02** GIVEN no configuration THEN the standard browser print dialog is used and nothing breaks.
**OOS** Direct raw printing/driver integration.
**Test** No PHI in stored preferences.

**RCP-006 · Patient visit summary printout · V1 · P1 · `RECEPTIONIST`,`CLINICIAN`**
**Release** V1
**Epic** RCP
**Priority** P1
**Persona** `RECEPTIONIST`,`CLINICIAN`
**RCP-006-AC01** GIVEN a completed visit THEN a one-page patient-facing summary can be printed containing the diagnosis (if the clinician has marked it shareable), the medicines dispensed with instructions, the tests done with results if released, follow-up instructions, the next appointment, and the amount paid.
**RCP-006-AC02** GIVEN clinician-only content (full clerking notes, working differentials) THEN it is excluded from the patient summary.
**Test** Content-exclusion assertions.

**RCP-007 · Document numbering and uniqueness · V1 · P0 · `SYSTEM`**
**Release** V1
**Epic** RCP
**Priority** P0
**Persona** `SYSTEM`
**RCP-007-AC01** GIVEN receipts, invoices, credit notes, lab reports, prescriptions, referrals and certificates THEN each has a unique, sequential, non-reusable number per facility per type.
**RCP-007-AC02** GIVEN concurrent generation THEN no duplicates occur.
**RCP-007-AC03** GIVEN a voided document THEN its number is retired, never reissued.
**Dep** TEN-007.
Detailed Product Spec authority for the referenced unsupplied dependencies remains UNSUPPLIED / OPEN / BLOCKED; no missing story is inferred.
**Test** Concurrency and retirement.

---

---

### Epic ANC — Antenatal Care

**ANC-001 · Enrol a patient in ANC · V1 · P0 · `MIDWIFE`; secondary `CLINICIAN`**
**Release** V1
**Epic** ANC
**Priority** P0
**Persona** `MIDWIFE`; secondary `CLINICIAN`
**ANC-001-AC01** GIVEN a pregnant patient THEN the midwife creates an ANC enrolment recording: ANC number (facility sequence, TEN-007), LMP (with a "certain/uncertain" flag) or an ultrasound-based EDD, gravida, para, number of living children, previous pregnancy outcomes summary, blood group if known, and the enrolment date and provider.
**ANC-001-AC02** GIVEN an LMP THEN the EDD is computed as LMP + 280 days and displayed as derived, editable only by entering a clinician-supplied EDD with a reason (e.g. ultrasound dating), in which case both values and the basis are stored.
**ANC-001-AC03** GIVEN an active enrolment THEN a second concurrent enrolment for the same patient is blocked.
**ANC-001-AC04** GIVEN enrolment THEN the patient's chart shows an ANC banner with EDD and current gestational age.
**ANC-001-AC05** GIVEN an obstetric summary that also exists in ENC-013 THEN a single stored record is used by both.
**Data** `ANCEnrolment`.
**Test** EDD arithmetic; single-active-enrolment constraint.

**ANC-002 · Start an ANC contact/visit · V1 · P0 · `MIDWIFE`**
**Release** V1
**Epic** ANC
**Priority** P0
**Persona** `MIDWIFE`
**ANC-002-AC01** GIVEN an enrolled patient checked in with visit type `ANC` THEN the midwife starts an ANC encounter, which is an `Encounter` of type `ANC` with an attached `ANCVisit` record carrying the contact sequence number (1..8+, auto-incremented and editable) and the visit date.
**ANC-002-AC02** GIVEN a start THEN the gestational age in completed weeks and days is computed from the EDD basis and displayed and stored on the visit.
**ANC-002-AC03** GIVEN a patient not yet enrolled THEN the midwife is prompted to enrol first (ANC-001) in the same flow.
**ANC-002-AC04** GIVEN an ANC encounter THEN all encounter lifecycle rules (draft, autosave, park for results, sign, amend) apply identically (Epic ENC) — the midwife holds `encounter.update` and `queue.hold` within ANC scope, so she may park the ANC encounter `AWAITING_RESULTS`, hold its queue entry `ON_HOLD`, and later resume the same encounter (ENC-016/ENC-002/QUE-006) without any clinician involvement.
**Data** `ANCVisit`.
**Test** GA computation at boundaries; reuse of encounter lifecycle.

**ANC-003 · Maternal, obstetric and medical history · V1 · P0 · `MIDWIFE`**
**Release** V1
**Epic** ANC
**Priority** P0
**Persona** `MIDWIFE`
**ANC-003-AC01** GIVEN the first contact THEN the midwife records: previous pregnancy details (year, outcome, mode of delivery, birth weight, complications) as repeatable rows; medical history (hypertension, diabetes, HIV status and ART if disclosed, TB, epilepsy, sickle cell, surgery); allergies (shared with TRI-004); and family/social history.
**ANC-003-AC02** GIVEN subsequent contacts THEN the history is displayed read-only with an "update history" action that versions the change.
**ANC-003-AC03** GIVEN HIV or other sensitive status THEN it is stored as recorded by the provider with no automatic disclosure in printed documents unless the document is explicitly the ANC card and the facility has enabled it (OD-17).
**Test** Version history; sensitive-field print control.

**ANC-004 · ANC vitals and measurements · V1 · P0 · `MIDWIFE`,`NURSE`**
**Release** V1
**Epic** ANC
**Priority** P0
**Persona** `MIDWIFE`,`NURSE`
**ANC-004-AC01** GIVEN a contact THEN the provider records BP, pulse, temperature, weight, height (first contact), MUAC, and Hb if tested at point of care, using the shared vitals component (TRI-002) with the same validation.
**ANC-004-AC02** GIVEN weight across contacts THEN the change since the previous contact is displayed as a computed difference **without interpretation**.
**ANC-004-AC03** GIVEN a BP value THEN it is displayed with an out-of-range marker per the configured reference band and no advice text.
**Dep** TRI-002.
**Test** Shared-component consistency.

**ANC-005 · Risk-factor documentation · V1 · P0 · `MIDWIFE`**
**Release** V1
**Epic** ANC
**Priority** P0
**Persona** `MIDWIFE`
**ANC-005-AC01** GIVEN a facility-configured checklist of risk factors (e.g. age <18 or >35, previous caesarean, previous stillbirth, multiple pregnancy, anaemia, hypertension, diabetes, HIV, previous PPH, grand multiparity) THEN the midwife may tick those present and add free-text notes.
**ANC-005-AC02** GIVEN ticked factors THEN they are displayed prominently on the ANC banner for subsequent contacts and printed on the ANC card.
**ANC-005-AC03** GIVEN the platform THEN it computes **no risk score, no risk category and no recommended action**, and the UI contains no such language.
**ANC-005-AC04** GIVEN a facility requests to display its own guidance THEN no facility-authored clinical guidance is displayed while OD-09 / OD-C6 remain unresolved; if authorised later, the guidance must be explicitly authored, owned, and attributed to that facility.
**Data** `ANCRiskFactor[]`.
**Test** UI copy audit for absence of CDS language.

**ANC-006 · Obstetric examination · V1 · P0 · `MIDWIFE`**
**Release** V1
**Epic** ANC
**Priority** P0
**Persona** `MIDWIFE`
**ANC-006-AC01** GIVEN a contact at an appropriate gestation THEN the midwife records fundal height (cm), presentation (`CEPHALIC`,`BREECH`,`TRANSVERSE`,`UNDETERMINED`), lie, fetal heart rate (bpm, or `NOT_HEARD` with a note), fetal movements (`PRESENT`,`ABSENT`,`NOT_ASSESSED`), oedema (`NONE`,`MILD`,`MODERATE`,`SEVERE`), pallor, and general examination notes.
**ANC-006-AC02** GIVEN fundal height THEN it is stored with the gestational age at that contact so the pair is retrievable; **no automatic comparison or flagging is performed**.
**ANC-006-AC03** GIVEN FHR outside a configured band THEN a neutral out-of-range marker is displayed with no advice.
**Test** Field persistence; absence of derived clinical judgement.

**ANC-007 · ANC investigations · V1 · P0 · `MIDWIFE`**
**Release** V1
**Epic** ANC
**Priority** P0
**Persona** `MIDWIFE`
**Story** As a midwife I want to order the ANC contact's investigations from inside the ANC encounter so the standard laboratory loop applies without a separate workflow.
**ANC-007-AC01** GIVEN an open ANC encounter (ANC-002) THEN the midwife orders investigations using the standard ordering flow (LAB-002; `lab.order.create` includes `MIDWIFE`) and the standard laboratory loop applies unchanged: charges (LAB-004), gate policy (LAB-005, PAY-012), and the patient-facing laboratory queue movement `WAITING → CALLED → IN_SERVICE → COMPLETED` ending with the specimen-collection/receipt interaction, while LabOrderItem processing continues independently (`SAMPLE_COLLECTED → RESULT_ENTERED → VERIFIED → RELEASED`).
**ANC-007-AC02** GIVEN the encounter is waiting for results THEN the **same** ANC encounter may be parked `AWAITING_RESULTS` with the consultation queue entry `ON_HOLD` (ENC-016/QUE-006 — the midwife holds `queue.hold` within ANC scope) and resumes with the same encounter ID (ENC-002); no second ANC encounter is ever created.
**ANC-007-AC03** GIVEN released results THEN they return to the same ANC encounter (LAB-018/LAB-019): partial results are readable with "n of m results ready" progress; automatic `RESULTS_READY` follows the all-blocking rule (every blocking item `RELEASED` or `CANCELLED`); `SAMPLE_REJECTED` remains non-terminal (recollect or cancel — LAB-009/LAB-022); unreleased values remain invisible to the midwife/clinician.
**ANC-007-AC04** GIVEN the midwife signs with pending results through ENC-018 THEN the signed record remains immutable, the ANC consultation queue entry completes with reason `SIGNED_WITH_PENDING_RESULTS`, and late results follow the LAB-023 addendum path.
**ANC-007-AC05** GIVEN the catalogue THEN ANC-routine tests (e.g. Hb, HIV/syphilis screening, urinalysis, blood group) exist only as **configurable examples**, not mandatory protocol rules.
**ANC-007-AC06** GIVEN the ANC card printout THEN released investigation results appear according to the existing ANC card layout only.
**Perm** `lab.order.create` (MIDWIFE included per LAB-002).
**Data** `LabOrder`/`LabOrderItem` linked to the ANC encounter; no ANC-specific laboratory states or statuses.
**Audit** Standard laboratory audit events (LAB-002..LAB-023).
**Err** Standard laboratory errors; no ANC-specific exceptions.
**Dep** ANC-002, LAB-002, LAB-004, LAB-005, LAB-015, LAB-018, LAB-023, ENC-016, ENC-018, ENC-002, QUE-006, PAY-012.
**OOS** Automatic ANC protocol enforcement, test-scheduling recommendations, interpretation of laboratory results, diagnosis or treatment suggestion, automatic risk classification, new HMIS fields, certified HMIS/DHIS2 submission — KlinKlik performs none of these (AS-11, OD-09).
**Test** Mandatory Journey-E integrity test: ANC visit → same ANC encounter → midwife orders a lab test → encounter parks → standard laboratory workflow → result `RELEASED` → the **same** ANC encounter receives it → resume or the signed-pending path → no duplicate encounter, no unreleased value exposed, no CDS.

---

---

---

## 17. Non-Functional Requirements

Requirements should be testable where possible and tied to a release or
invariant. Do not invent targets where the Product Spec intentionally leaves
them open.

| NFR ID | Category | Product requirement / observable outcome | Evidence / measure | Authority / references | Release | Owner / dependency | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NFR-01 | Performance | Interactive list API operations are no more than 400 ms p95 under the agreed reference dataset at normal load. This is a cross-cutting target, not a promise for an unbounded dataset or every operation. | Timed representative list calls with the agreed reference dataset and normal-load profile; report p95. | PP-07; GSC-13; backlog cross-cutting UI contract | V1 | Product and implementation evidence; reference dataset remains to be agreed | REQUIRED |
| NFR-02 | Performance / low-bandwidth | Primary worklist usable/rendered state is no more than 2 s p95 under the agreed 3G-equivalent test profile. The target applies to the primary worklists covered by the reference profile. | Repeatable 3G-equivalent run from request to usable worklist; report p95 and the tested worklist. | PP-07, PP-08; GSC-12/GSC-13; backlog cross-cutting UI contract | V1 | Product/UX/performance review; exact profile is OPEN | REQUIRED |
| NFR-03 | Low-bandwidth operation | Supported workflows show visible save state and distinguish pending, failure, unavailable, denied, stale/conflict, and unknown outcomes. High-impact clinical sign-off, payment, stock, dispensing, sale, and final actions do not complete offline. | Exercise connectivity loss, retry, and recovery at each high-impact boundary; confirm the authoritative outcome and visible next action. | PP-08; TI-15; GSC-12; J-01 through J-05 | V1 | Product, clinical, pharmacy, and operations authority | REQUIRED |
| NFR-04 | Accessibility | Core supported workflow surfaces remain perceivable and operable: keyboard operation is supported, required controls are understandable, focus and blocking reasons are visible, and loading/empty/error states are explicit. No unprovided conformance level is inferred. | Keyboard-only walkthroughs and role-appropriate accessibility review of the core journeys, including error and blocked states. | PP-06; GSC-12/GSC-13; supplied story UI obligations | V1 | Product/UX review; formal conformance target is OPEN | REQUIRED |
| NFR-05 | Availability / degraded operation | When a dependency, print surface, or connectivity path is unavailable, the product preserves already-committed truth and presents a safe displayable pending, failure, unknown, or retry outcome; it does not imply completion. | Fault-injection scenarios for network, print, and unavailable worklists; compare displayed state with the authoritative record. | PP-01, PP-02, PP-08; GSC-10/GSC-12; RCP and payment stories | V1 | Operations and product authority; recovery objectives are OPEN | REQUIRED |
| NFR-06 | Printing / documents | Paper remains the fallback for supported slips, labels, receipts, reports, and clinical or stock documents. A printer failure never changes clinical, stock, or financial truth; a screen-displayable document remains available where the story requires it. Reprints preserve the original meaning and are audited. | Print, unavailable-printer, screen-display, and reprint scenarios for REC, RCP, BIL, DSP, INV, and shift documents. | PP-02; GSC-8/GSC-12; REC-006, DSP-010, BIL-011/012, RCP stories | V1 | Product/operations; facility print configuration is a dependency | REQUIRED |
| NFR-07 | Privacy | PHI and other sensitive clinical payloads are disclosed only inside authorised product scope and are not placed in generic logs, telemetry, diagnostics, analytics, or error payloads. Protected client state is not persisted in browser storage. | Inspect role-scoped responses, logs, telemetry, diagnostics, error payloads, and browser persistence during representative journeys. | PP-05; TI-12; GSC-8/GSC-9; Section 21 | V1 | Product privacy authority and security review; exact retention authority is OPEN | REQUIRED |
| NFR-08 | Security / authority | Protected behaviour is decided from authoritative identity, organisation/facility/department scope, state, credentials, and applicable configuration. Missing, expired, stale, ambiguous, or revoked authority denies the action; presentation state cannot grant it. | Negative permission, scope, credential, state, and revocation scenarios across every protected journey and interface. | TI-01, TI-02; GSC-1 through GSC-4; Sections 8–9 | V1 | Named authority roles remain subject to AUTH/TEN/USR decisions | REQUIRED |
| NFR-09 | Audit / evidence | Every material mutation and required sensitive access produces attributable, immutable, reconstructable, non-sensitive evidence with actor, authoritative time, target, reason where required, and outcome. An action requiring audit evidence does not complete without it. | For each audited story, reconcile the product outcome to its audit/access evidence and verify that raw PHI is absent from generic audit payloads. | TI-13; GSC-8/GSC-11/GSC-13; AUD references in supplied stories | V1 | Product/security/audit authority; detailed AUD epic is UNSUPPLIED | REQUIRED |
| NFR-10 | Concurrency / retry | A stale or competing high-impact action produces one safe committed product outcome. Retried commands do not duplicate money, stock, dispensing, clinical, queue, or finalisation effects; materially different reuse is refused; stale updates are rejected or explicitly reconciled. | Repeat simultaneous create, start, sign, release, pay, dispense, reverse, resume, and close scenarios; inspect winner and loser outcomes. | TI-09, TI-10, TI-11; GSC-5/GSC-6/GSC-7; CMC-01 through CMC-17 | V1 | Product/implementation evidence; technical mechanism is Blueprint-owned | REQUIRED |
| NFR-11 | Data integrity | Final clinical, laboratory, stock, dispensing, financial, payment, receipt, and audit history is preserved. Stock changes only through attributable movements; correction uses the supplied amendment, reversal, credit, void, quarantine, disposal, or addendum outcome. | State-transition, correction, reversal, conservation, and reconstruction tests for the applicable domain records. | TI-03, TI-04, TI-07, TI-08; GSC-13; SM-01 through SM-11 | V1 | Clinical, pharmacy, finance, and product authority | REQUIRED |
| NFR-12 | Authoritative time | V1 operational time uses EAT / Africa-Kampala facility-day boundaries. The authoritative product/server clock determines expiry, ordering, elapsed time, queue timing, schedules, and audit chronology; client/device time cannot determine a protected outcome. | Clock-skew and boundary tests for queue order, expiry, schedules, elapsed thresholds, and audit chronology; distinguish entered clinical time from system chronology. | GSC-11; TI-05, TI-13; backlog operating context | V1 | Product/operations; external time authority details are OPEN | REQUIRED |
| NFR-13 | Reliability / recovery | Retryable, unknown, and externally dependent work has an explicit product-visible recovery or reconciliation outcome. A success observed by an external party but not acknowledged locally is not silently replayed or represented as failed without the defined reconciliation path. | Exercise timeout, duplicate delivery, external-success/local-failure, and reconciliation cases for any authorised effect; no effect is activated from an architectural allowance alone. | GSC-10; TI-09/TI-10/TI-13; outbound-effect contract | V1 | External-effect authority is UNSUPPLIED / OPEN; no provider integration is inferred | REQUIRED |
| NFR-14 | Backup / restore | Product release evidence must include a successful restore drill and demonstrate preservation of required clinical, financial, stock, payment, and audit meaning. No recovery-time or recovery-point number is invented where authority has not supplied one. | Recorded restore drill with integrity and reconstruction checks; record any unresolved recovery objective as OPEN. | PP-01/PP-02; V1 release strategy; blueprint release gates | V1 | Operations and product authority; recovery objectives OPEN | REQUIRED |
| NFR-15 | Scalability / capacity | Supported workflows must retain their specified correctness, privacy, and visible-state outcomes as the agreed facility reference dataset grows. No universal throughput, tenant count, or capacity target is asserted without an authority record. | Capacity and degradation review against an agreed dataset/profile before the applicable release decision. | PP-07; GSC-12/GSC-13 | V1 | Product/operations; capacity profile is OPEN | OPEN |
| NFR-16 | Browser / device support | Core workflows must remain understandable and operable on the supported browser/device set used by the facility and the constrained-connectivity profile. The supported matrix is not yet enumerated and cannot be guessed. | Device/browser matrix review covering the five canonical journeys, printing, keyboard use, and degraded states. | PP-06, PP-08; GSC-12 | V1 | Product/UX/operations; support matrix OPEN | OPEN |
| NFR-17 | Product observability | Users and authorised supervisors can see save state, queue/location, blockers, pending work, failures, unknown outcomes, correction state, and required next action. Operational evidence is attributable and minimised; implementation telemetry details remain Blueprint-owned. | Journey walkthroughs and audit/evidence reconciliation for every terminal, pending, failed, denied, stale, and degraded branch. | PP-02; GSC-8/GSC-12/GSC-13; J-01 through J-05 | V1 | Product/operations/security; detailed OPS/AUD authority is UNSUPPLIED | REQUIRED |
| NFR-18 | Clinical and medicine safety | The product refuses expired medicine and unsupported controlled/Class A workflows, preserves clinical and released-result history, and does not automatically diagnose, prescribe, dose, interpret, or classify risk. | Negative tests for all supported entry paths plus clinical/pharmacy review of the no-interpretation boundary. | TI-03 through TI-06, TI-14; GSC-3/GSC-4 | V1 | Clinical/pharmacy authority and validation gates | REQUIRED |
| NFR-19 | Data retention / deletion authority | Product integrity requires material clinical, laboratory, stock, financial, payment, receipt, and audit history to remain reconstructable through its approved correction paths. No retention period, deletion schedule, or legal obligation is invented; applicable retention authority remains an explicit decision. | Review each record class against the authorised retention/deletion register before release; verify that any deletion or export path cannot silently destroy required history. | PP-02, PP-05; TI-03/TI-04/TI-07/TI-08/TI-13; OD-L1–OD-L8 | V1 | Legal/privacy/product authority; retention register OPEN / BLOCKED | OPEN |

Quantitative values above are deliberately limited to the supplied cross-cutting
400 ms p95 API and 2 s p95 3G-equivalent worklist targets. Story-local values
remain scoped to their stories and are not promoted to universal targets.
Retention, recovery objectives, browser/device support, capacity, and any
additional external or legal obligation remain OPEN until an authorised record
supplies them. Section 17 defines product outcomes and evidence obligations;
implementation mechanisms and current execution status belong in the Blueprint.

---

## 18. Mandatory Trust Regression Suite

Feature tests are insufficient. Once a high-risk invariant or contract is
implemented, its regression test remains a permanent release gate for every
applicable release. A feature cannot weaken or delete a trust gate merely to
make a new test green.

| Gate ID | Area | Invariant / contract | Release-gate assertion | Verification requirement | Gate disposition | Applicable releases | Owner / dependency |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RG-01 | Organisation and scope isolation | TI-01 | Cross-organisation access and unauthorised facility, department, patient, object, or configuration access disclose neither existence nor data and cannot mutate the target; only an explicitly authorised same-organisation exception may succeed. | AUTOMATED REQUIRED; negative cross-scope and same-organisation exception scenarios | NON-WAIVABLE | V1 and every applicable future release | Product/security authority; BRN exception remains gated |
| RG-02 | Protected authority and state | TI-02; GSC-1 through GSC-4 | Missing, expired, stale, ambiguous, revoked, or out-of-scope identity, permission, credential, state, or configuration refuses the protected action; client presentation cannot grant it. | AUTOMATED REQUIRED; permission, credential, state, and boundary scenarios | NON-WAIVABLE | V1 and every applicable future release | Product/security authority; AUTH/TEN/USR details remain OPEN |
| RG-03 | Signed clinical history | TI-03 | A signed Encounter or clinical record remains attributable and preserved; correction uses the approved amendment, addendum, or entered-in-error path and never silently rewrites the prior history. | AUTOMATED REQUIRED; sign, correction, duplicate, and forbidden-delete scenarios | NON-WAIVABLE | V1 and every applicable future release | Clinical authority; ENC-017/018/019; SM-04 |
| RG-04 | Released laboratory history | TI-04 | Only verified results release; a post-release correction preserves the released result, creates the attributable amended result, and produces the required review/notification outcome without silently changing history. | AUTOMATED REQUIRED; verification, release, partial, late-amendment, and notification scenarios | NON-WAIVABLE | V1 and every applicable future release | Laboratory authority; LAB-015/017/018/023; SM-05 |
| RG-05 | Expired-stock refusal | TI-05 | An expired KlinKlik-managed medicine can never become usable through normal receiving into usable stock, preparation, confirmation, sale, dispensing, prescription fulfilment, transfer to a dispensing or other usable location, structured issue/use, or any override. Normal receipt of already-expired stock is refused. Expired stock already on hand may move only through supplied safe non-usable or correction paths such as quarantine and disposal/write-off; a positive correction is refused or remains/lodges directly in quarantine/non-usable stock and can never increase usable availability. Quarantine and disposal/write-off are permitted safety outcomes. | AUTOMATED REQUIRED; boundary-date, every usable-entry-path negative scenario, and safe quarantine/disposal/correction scenarios | NON-WAIVABLE | V1 and every applicable future release | Pharmacy authority; INV-002/005/010/011; DSP-003/009/015 |
| RG-06 | Controlled/Class A refusal | TI-06 | Baseline V1 refuses receiving, prescribing, dispensing, sale, and external-prescription completion for a controlled/Class A product; classification authority cannot enable the unsupported workflow. | AUTOMATED REQUIRED; catalogue and workflow-entry negative scenarios | NON-WAIVABLE | V1 | Pharmacy/product authority; RX-008; PHM classification |
| RG-07 | Stock-ledger integrity | TI-07 | Stock changes only through attributable movements; no direct or silent balance rewrite or negative usable balance is possible, and corrections preserve movement history through the approved path. While OD-PH5 is BLOCKED, every physical medicine return preserves batch identity but lands only in quarantine/non-usable stock and cannot increase usable availability. | AUTOMATED REQUIRED; movement conservation, FEFO, adjustment, reversal, return-to-non-usable, quarantine, and disposal scenarios | NON-WAIVABLE | V1 and every applicable future release | Pharmacy/stock authority; INV-004/005/011/012/014; DSP-016; SM-07; OD-PH5 |
| RG-08 | Financial and allocation integrity | TI-08 | Final financial records and payments remain preserved; invoices, lines, allocations, receipts, reversals, CreditNotes, Refunds, and waivers reconcile without silent over-allocation, double-credit, over-refund, or unapproved excess outcome. GROSS INVOICE TOTAL remains the sum of non-voided lines; CreditNotes adjust CURRENT AUTHORITATIVE AMOUNT DUE without editing paid lines; full Payment reversal recomputes every affected Invoice from CURRENT EFFECTIVE APPLIED VALUE as ISSUED, PARTIALLY_PAID, or PAID, never VOIDED; bounded Refunds affect only their credited context. | AUTOMATED REQUIRED; (1) one Payment allocated across Invoice A and Invoice B then fully reversed: all allocations reversed, both Invoices independently recomputed, and only eligible undelivered gates re-gated; (2) a paid Invoice CreditNote reduces amount due without excess and state recomputes; (3) a CreditNote creates REFUNDABLE CREDIT and the Invoice remains PAID with the credit explicit; (4) a credit smaller than a Payment also covering another Invoice uses a bounded Refund that affects only the credited context, leaves the Payment CONFIRMED, and leaves unrelated allocation/Invoice/gate unchanged; (5) retry/concurrency yields no duplicate CreditNote, duplicate Refund, double reversal, or over-refund. | NON-WAIVABLE | V1 and every applicable future release | Finance authority; BIL-001..014; PAY-002/005/008/012; SM-08/09 |
| RG-09 | Single committed outcome | TI-09; GSC-6 | Competing high-impact requests leave one committed product outcome and no partial bundle or multiple winner; losing requests receive the safe current-state result. | AUTOMATED REQUIRED; simultaneous create/start/sign/release/pay/dispense/close scenarios | NON-WAIVABLE | V1 and every applicable future release | Product/operations authority; CMC-01..17 |
| RG-10 | Duplicate and retry safety | TI-10; GSC-7 | A retry with the same request identity returns the original safe outcome without a duplicate clinical, queue, stock, dispense, payment, or finalisation effect; materially different reuse is refused. | AUTOMATED REQUIRED; duplicate-click, network-retry, replay, and conflicting-identity scenarios | NON-WAIVABLE | V1 and every applicable future release | Product/operations authority; CMC-06/08/09/12/17 |
| RG-11 | Stale-state conflict safety | TI-11; GSC-5 | A stale actor cannot silently overwrite newer authoritative mutable state; the action is refused with current state or follows the explicitly defined reconciliation path. | AUTOMATED REQUIRED; stale read/write and current-state reconciliation scenarios | NON-WAIVABLE | V1 and every applicable future release | Product/implementation evidence; technical mechanism is Blueprint-owned |
| RG-12 | PHI minimisation | TI-12; GSC-9 | PHI is visible only inside authorised product scope; generic logs, telemetry, diagnostics, analytics, error payloads, and audit payloads contain no raw sensitive clinical content. | MANUAL REVIEW; named human privacy review with reproducible inspection and negative paths | NON-WAIVABLE | V1 and every applicable future release | Product privacy/security authority; retention details OPEN |
| RG-13 | Audit integrity | TI-13; GSC-8 | Every required mutation or sensitive access completes with attributable, immutable, non-sensitive reconstruction evidence using authoritative time; missing required evidence blocks completion. | AUTOMATED REQUIRED; audit-presence, attribution, chronology, tamper, and failure scenarios | NON-WAIVABLE | V1 and every applicable future release | Product/security/audit authority; AUD epic UNSUPPLIED |
| RG-14 | No unapproved clinical interpretation | TI-14 | V1 records and presents human-entered workflow information but does not automatically diagnose, prescribe, dose, match allergies/interactions, classify risk, interpret results, or issue critical-result conclusions. | MANUAL REVIEW; named clinical reviewer exercises positive and negative paths | NON-WAIVABLE | V1 and every applicable future release | Clinical authority; validation gates remain OPEN/BLOCKED |
| RG-15 | No high-impact offline completion | TI-15 | Clinical sign-off, payment, stock receipt/adjustment, dispensing, sale, and other high-impact final actions complete only after authoritative confirmation; a queued/local attempt is not a completed outcome. | AUTOMATED REQUIRED; disconnect, reconnect, replay, and finalisation scenarios | NON-WAIVABLE | V1 and every applicable future release | Product/operations authority; offline completion is prohibited |

### Core-flow reconciliation regression coverage

The following scenarios extend the applicable existing regression gates; no new
Regression Gate IDs are introduced:

- **OPD active-Visit start (RG-09/RG-10/RG-11/RG-13):** check-in creates
  Visit `OPEN` → triage starts → Visit becomes `IN_PROGRESS` →
  the clinician starts `ENC-001` successfully on that same Visit →
  exactly one Visit and one non-terminal Encounter remain.
- **LAB_ONLY PAY_BEFORE (RG-08/RG-09/RG-10/RG-13):** check-in creates the
  `LAB_ONLY` Visit → request capture → `LabOrderItem ORDERED` →
  Visit-linked charge → `AWAITING_PAYMENT` → cashier QueueEntry →
  no patient-facing LAB QueueEntry → qualifying payment/waiver/override →
  `READY_FOR_COLLECTION` → patient-facing LAB QueueEntry
  `WAITING`.
- **LAB_ONLY PAY_AFTER/NO_GATE (RG-09/RG-10/RG-13):** check-in → request
  capture → `ORDERED` → `READY_FOR_COLLECTION` →
  patient-facing LAB QueueEntry `WAITING`.
- **LAB_ONLY external order (RG-01/RG-02/RG-09/RG-10/RG-13):** no Encounter
  exists, but an authorised actor using `lab.order.create.external`
  succeeds through LAB-024 and the order/items are linked to the active Visit.
- **Reception privacy (RG-02/RG-12/RG-13):** the RECEPTIONIST check-in
  payload contains administrative context only and no allergy status or other
  clinical fields; the required attributable check-in evidence is retained.

### Gate rules

- Each gate has a concrete assertion and a reproducible fixture or scenario.
- Include negative, permission, scope-isolation, stale-write, retry, and
  concurrency cases when the invariant applies.
- A Regression Gate explicitly designated as the proving/enforcement regression
  gate for a currently effective frozen Trust Invariant or currently applicable
  External Binding Authority obligation is, by definition, directly proving
  that guarantee and is NON-WAIVABLE while that guarantee remains in force.
  This designation may appear in a Trust Invariant row, the External Binding
  Authority's declared regression mapping where used, or another canonical
  Product Spec contract that explicitly designates the gate.
- Supplementary tests that merely contribute supporting evidence are not
  automatically NON-WAIVABLE unless the Product Spec explicitly designates
  them as proving the guarantee. A gate named as the proving gate cannot evade
  NON-WAIVABLE status by claiming it only partially proves the invariant.
- Such a gate may not be converted to WAIVABLE RISK merely by changing the
  gate row. The underlying Trust Invariant must first be lawfully changed
  through Product Spec change control, or the External Binding Authority
  obligation must first cease to apply or be changed through its authorised
  external process.
- A gate-only edit is not authority to weaken the underlying guarantee.
- A failed NON-WAIVABLE gate blocks release, promotion, or publication;
  ordinary residual-risk acceptance cannot override it. The guarantee itself
  must first be lawfully changed through the applicable Product Spec or
  external-authority process if changing it is genuinely intended.
- WAIVABLE RISK remains available only for lower-order gates that do not
  directly prove a currently effective frozen Trust Invariant or applicable
  External Binding Authority obligation, and only where the Product Spec
  explicitly classifies the gate as waivable. A waiver requires a qualified
  named authority, exact failing assertion, affected IDs, bounded
  release/scope, compensating controls, residual risk, expiry/re-review
  condition, and re-verification requirement. The ordinary gate owner is not
  automatically sufficient authority.
- Do not make all gates non-waivable; lower-order risks may use the bounded
  WAIVABLE RISK path when explicitly classified.
- NOT APPLICABLE means the regression gate itself does not apply to the current
  project or release because its underlying invariant, contract, or obligation
  is not applicable to that scope; it is not permission to avoid execution. If
  the underlying guarantee remains applicable, use AUTOMATED REQUIRED,
  AUTOMATED WHERE FEASIBLE, or MANUAL REVIEW. A gate mapped as the proving gate
  for an active Trust Invariant or applicable External Binding Authority
  obligation cannot use NOT APPLICABLE. When legitimate, retain the row with a
  rationale and reopening condition where materially relevant.
- Verification requirement describes the protection required by the product;
  it is not a current implementation result. Current automation,
  implementation, and pass/fail status belongs in the Blueprint's LIVE
  EXECUTION STATE.

### Manual trust gate discipline

For every Product Spec trust gate marked **MANUAL REVIEW**, record all of the
following in the gate definition or its approved evidence record:

| Required field | Requirement |
| --- | --- |
| Human reviewer | Named HUMAN role; an AI agent alone cannot satisfy the review. |
| Procedure / scenario | Exact reproducible procedure or scenario. |
| Negative / failure paths | The denial, failure, unsafe, or boundary paths to exercise. |
| Evidence | Artifact or reference produced by the execution. |
| Trigger | The release, promotion, publication, or other execution trigger. |
| Maximum evidence age | Maximum age after which prior evidence is not valid. |
| Result | PASS / FAIL / NOT SATISFIED with reviewer and date. |

Machine-testable scope, permissions, concurrency, stale-write, idempotency,
duplicate-safety, and security guarantees should be **AUTOMATED REQUIRED**
where feasible. If a gate is marked **AUTOMATED WHERE FEASIBLE** and
automation does not currently exist, it MUST execute using the **MANUAL
REVIEW** discipline until automation exists. That fallback requires a named
HUMAN role, exact reproducible scenario, negative/failure paths, evidence
reference, execution trigger, maximum evidence age, and result. Missing or
expired fallback evidence is NOT SATISFIED. **AUTOMATED WHERE FEASIBLE** is
not permission to omit execution or merely document why it was not tested.
The full applicable trust suite is required before release,
promotion, or publication; Blueprint Section 18 defines the proportionate
per-slice cadence.

---

## 19. Coverage Matrix

This matrix describes specification coverage, not implementation completion.

| Capability | Product Goal IDs | Personas / authority | Journeys | Canonical stories / epic | State machines | Trust invariants / regression gates | Dependencies | Release | Specification status | Missing decision / gap |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Organisation, facility, and protected access boundary | G5, G7 | P-01/P-02/P-03/P-04/P-05; AUTH/TEN/USR authority | J-01–J-05 context | AUTH/TEN/USR UNSUPPLIED; permission and governance sections | SM-01/SM-02/SM-04/SM-08/SM-09 | TI-01/TI-02/TI-12/TI-13; RG-01/RG-02/RG-12/RG-13 | Authoritative identity, grants, revocation, facility configuration | V1 | PARTIAL / BLOCKED | AUTH, TEN, and USR detailed authority, revocation, and cross-facility rules remain OPEN |
| Patient identity and duplicate control | G1, G5, G7 | P-06/P-04/P-07; PAT authority | J-01–J-05 entry | PAT-001/002 references in REC; PAT epic UNSUPPLIED | SM-02 | TI-01/TI-02/TI-10/TI-13; RG-01/RG-02/RG-10/RG-13 | Patient-number scheme, duplicate policy, privacy and scope authority | V1 | PARTIAL / BLOCKED | PAT detailed story authority and any cross-facility patient-sharing rule are UNSUPPLIED |
| Reception, check-in, and visit creation | G1, G4, G5, G7 | P-06/P-04/P-07/P-16 | J-01–J-05 | REC-001–REC-013 | SM-01/SM-02/SM-08/SM-09 | TI-01/TI-02/TI-08/TI-09/TI-10/TI-11/TI-13/TI-15; RG-01/RG-02/RG-08–RG-11/RG-13/RG-15 | PAT identity, pricing, destination, facility configuration | V1 | PARTIAL | Appointment-driven and some authority/configuration branches depend on unsupplied APT/TEN decisions |
| Queue and handoff management | G1, G5, G6, G7 | P-06/P-07/P-08/P-09/P-10/P-12/P-14/P-16 | J-01–J-05 | QUE-001–QUE-016 | SM-01/SM-02/SM-03/SM-04/SM-05/SM-07 | TI-01/TI-02/TI-09/TI-10/TI-11/TI-13/TI-15; RG-01/RG-02/RG-09–RG-11/RG-13/RG-15 | Department queues, scope grants, authoritative time, state rules | V1 | PARTIAL | BRN/OPS policy and revocation details remain OPEN; no unsupplied queue behaviour inferred |
| Triage and observation | G1, G2, G5, G7 | P-07/P-08 where ANC scope applies/P-16 | J-01–J-05 | TRI-001–TRI-013 | SM-01/SM-03/SM-04 | TI-01/TI-02/TI-03/TI-09/TI-10/TI-11/TI-13/TI-14/TI-15; RG-01–RG-03/RG-09–RG-11/RG-13–RG-15 | Credential and grant scope; no diagnosis or automatic interpretation | V1 | PARTIAL | Clinical validation remains a release dependency where marked OPEN/BLOCKED |
| Clinical encounter and signing | G1, G2, G5, G7 | P-09/P-08; P-07 only where explicitly permitted | J-01–J-05 | ENC-001–ENC-024 | SM-01/SM-04 | TI-01/TI-02/TI-03/TI-09/TI-10/TI-11/TI-13/TI-14/TI-15; RG-01–RG-03/RG-09–RG-11/RG-13–RG-15 | Credential, signing, amendment, laboratory hold, closure checklist | V1 | PARTIAL | Professional validation gates and AUTH/USR revocation remain OPEN/BLOCKED |
| Laboratory collection, verification, and release | G1, G2, G5, G6, G7 | P-10/P-11/P-09/P-16 | J-02/J-04/J-05 | LAB-001–LAB-025 | SM-01/SM-04/SM-05 | TI-01/TI-02/TI-03/TI-04/TI-09/TI-10/TI-11/TI-13/TI-14/TI-15; RG-01–RG-04/RG-09–RG-11/RG-13–RG-15 | Lab configuration, verifier separation, payment gates, notification/review authority | V1 | PARTIAL | Detailed LAB authority is supplied; external notification effect remains subject to GSC-10 authority |
| Diagnosis and treatment documentation | G1, G2, G5, G7 | P-09/P-08; no automatic system authority | J-01–J-05 | DX-001–DX-010 | SM-04/SM-06 | TI-02/TI-03/TI-09/TI-10/TI-11/TI-13/TI-14; RG-02/RG-03/RG-09–RG-11/RG-13/RG-14 | Clinical credential, encounter state, no-interpretation boundary | V1 | PARTIAL | Clinical validation for any future interpretation remains OPEN/BLOCKED |
| Prescriptions | G2, G3, G5, G7 | P-09/P-08/P-12 | J-03/J-04/J-05 | RX-001–RX-011 | SM-04/SM-06/SM-07 | TI-02/TI-03/TI-06/TI-09/TI-10/TI-11/TI-13/TI-14/TI-15; RG-02/RG-03/RG-06/RG-09–RG-11/RG-13–RG-15 | Signed Encounter, product classification, pharmacy mode and credential | V1 | PARTIAL | Controlled/Class A workflow remains prohibited; external-only prescription detail is bounded |
| Pharmacy catalogue and classification | G3, G5, G7 | P-12/P-13/P-04; CAT authority | J-03/J-04 | PHM-001–PHM-008 | SM-06/SM-07 | TI-02/TI-05/TI-06/TI-07/TI-13/TI-14; RG-02/RG-05–RG-07/RG-13/RG-14 | Product identity, classification owner, price and stock configuration | V1 | PARTIAL / BLOCKED | CAT configuration authority and unsupplied catalogue governance remain OPEN |
| Inventory, batches, expiry, and movements | G3, G5, G7 | P-12/P-13/P-04/P-16 | J-03/J-04 | INV-001–INV-016 | SM-07 | TI-01/TI-02/TI-05/TI-06/TI-07/TI-09/TI-10/TI-11/TI-13/TI-15; RG-01/RG-02/RG-05–RG-07/RG-09–RG-11/RG-13/RG-15 | Catalogue classification, receiving, approvals, authoritative time | V1 | PARTIAL | OPS reporting/sweep authority and any additional stock policy remain OPEN |
| Pharmacy dispensing and retail sale | G3, G4, G5, G7 | P-12/P-14/P-04/P-16 | J-03/J-04 | DSP-001–DSP-016 | SM-01/SM-06/SM-07/SM-08/SM-09 | TI-01/TI-02/TI-05/TI-06/TI-07/TI-08/TI-09/TI-10/TI-11/TI-13/TI-15; RG-01/RG-02/RG-05–RG-10/RG-11/RG-13/RG-15 | Signed prescription, eligible stock, payment gate, print and correction paths | V1 | PARTIAL | Retail/customer identity and future external effects remain bounded by authority |
| Billing and invoicing | G1, G3, G4, G7 | P-06/P-14/P-15/P-04/P-16 | J-01–J-05 | BIL-001–BIL-014 | SM-02/SM-07/SM-08/SM-09 | TI-02/TI-08/TI-09/TI-10/TI-11/TI-13/TI-15; RG-02/RG-08–RG-11/RG-13/RG-15 | Service pricing, source-event identity, payment and closure authority | V1 | PARTIAL | Financial authority, credit/debt policy, and unsupplied reporting remain OPEN where marked |
| Payments, allocation, reversals, and shifts | G4, G5, G7 | P-14/P-15/P-04/P-05/P-16 | J-01–J-05 | PAY-001–PAY-014 | SM-08/SM-09 | TI-01/TI-02/TI-08/TI-09/TI-10/TI-11/TI-13/TI-15; RG-01/RG-02/RG-08–RG-11/RG-13/RG-15 | Invoice truth, cashier shift, approved reversal/refund/waiver authority | V1 | PARTIAL | Provider integration is not implied; manually entered references remain in-scope only where supplied |
| Receipts, labels, slips, and print fallback | G1, G3, G4, G6, G7 | P-06/P-12/P-14/P-04 | J-01–J-05 | RCP-001–RCP-007 plus print obligations in REC/DSP/BIL/INV | SM-02/SM-07/SM-08/SM-09 | TI-02/TI-08/TI-09/TI-10/TI-13/TI-15; RG-02/RG-08–RG-10/RG-13/RG-15 | Facility headers, printer availability, reprint authority | V1 | PARTIAL | Facility print configuration and document retention authority remain OPEN |
| Antenatal care | G1, G2, G5, G6, G7 | P-08/P-09/P-07/P-06 | J-05 | ANC-001–ANC-007 | SM-01/SM-03/SM-04/SM-05/SM-06/SM-07/SM-08/SM-09/SM-11 | TI-01/TI-02/TI-03/TI-04/TI-09/TI-10/TI-11/TI-13/TI-14/TI-15; RG-01–RG-04/RG-09–RG-11/RG-13–RG-15 | ANC credential and clinical validation; standard lab/prescription/financial paths | V1 | PARTIAL / BLOCKED | ANC clinical validation and APT follow-up detail remain OPEN/BLOCKED |
| Appointments and scheduling | G1, G5, G6, G7 | P-06/P-04/P-09/P-08; APT authority | J-01/J-05 dependency only | APT-001 reference; APT epic UNSUPPLIED | SM-10 placeholder only; no populated appointment machine | TI-01/TI-02/TI-09/TI-10/TI-11/TI-13; RG-01/RG-02/RG-09–RG-11/RG-13 | APT scope, slot, reminder, no-show, clinician routing, and permissions | V1 | MISSING / BLOCKED | No appointment workflow, slot, reminder, or permission behaviour is inferred |
| Reporting and management outputs | G4, G5, G7 | P-04/P-05/P-15/P-16; REP authority | J-01–J-05 output dependencies | REP references in supplied stories; REP epic UNSUPPLIED | No additional state machine supplied | TI-01/TI-02/TI-08/TI-12/TI-13; RG-01/RG-02/RG-08/RG-12/RG-13 | Authoritative source records, report scope, export and privacy authority | V1 | MISSING / BLOCKED | REP story definitions, role scope, export and retention rules remain OPEN |
| Audit and access evidence | G7, G5 | P-01/P-03/P-04/P-05/P-16; AUD authority | J-01–J-05 cross-cutting | AUD references in supplied stories; AUD epic UNSUPPLIED | Cross-cutting; no separate machine | TI-01/TI-02/TI-12/TI-13; RG-01/RG-02/RG-12/RG-13 | Actor identity, authoritative time, evidence integrity, non-sensitive payload | V1 | PARTIAL / BLOCKED | Detailed AUD events, access review, tamper/reconstruction and retention authority remain OPEN |
| Branch / cross-facility operations | G5, G7 | P-02/P-03/P-04/P-05; BRN authority | J-01–J-05 boundary dependency | BRN exception references only; BRN epic UNSUPPLIED | SM-01/SM-02 where supplied boundary applies | TI-01/TI-02/TI-09/TI-10/TI-11/TI-13; RG-01/RG-02/RG-09–RG-11/RG-13 | Organisation root, facility grants, explicit exception capability | V1 | MISSING / BLOCKED | No cross-facility exception is active without explicit authority; BRN policy remains OPEN |
| Operations, notification, and resilience governance | G6, G7 | P-01/P-04/P-05/P-16; OPS authority | J-01–J-05 cross-cutting | OPS references in supplied stories; OPS epic UNSUPPLIED | Cross-cutting; no additional machine | TI-02/TI-09/TI-10/TI-13/TI-15; RG-02/RG-09/RG-10/RG-13/RG-15 | Degraded state, restore, notifications, sweeps, monitoring and operational ownership | V1 | MISSING / BLOCKED | OPS authority, notification effects, recovery objectives and revocation handling remain OPEN |

Keep implementation status in the Blueprint's status matrix. Do not silently
mark a specified capability implemented because its story is complete.

The matrix uses PARTIAL for supplied behaviour because specification coverage
does not mean implementation complete: it is not a release approval or a
claim that evidence, authority, or implementation exists. Unsupplied AUTH,
TEN, USR, CAT, PAT, APT, REP, AUD, BRN, and OPS dependencies remain visible and
can keep a V1 slice BLOCKED. No separate Product Goal set is invented; G1–G7
are the canonical Product Goals in Section 3.

---

## 20. Data / Domain Model — Conceptual

This section is conceptual. It defines ownership and product meaning, not a
database framework or physical schema, unless a product rule depends on a
specific persistence property.

| Entity | Meaning | Relationships | Ownership / scope | Important uniqueness | Lifecycle authority | Integrity rule | Privacy classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Organisation | Tenant root for one clinic, pharmacy, or combined operation. | Owns facilities, memberships/grants, enabled capabilities, and organisation-scoped records. | Organisation authority; all tenant-owned records resolve to an organisation. | Organisation identity is stable; cross-organisation references are never accepted as same-scope. | Organisation authority; lifecycle and closure details are AUTH/TEN/USR-dependent. | No record may escape its organisation boundary; missing scope denies access. | Restricted tenant metadata |
| Facility | A branch/location within an organisation, not a tenant. | Belongs to one organisation; owns departments, local numbering/configuration, queues, and facility-scoped work. | Facility authority within the organisation. | Facility identity and organisation association are stable; same-day rules are facility-scoped. | Facility administration subject to organisation authority. | Facility context is explicit for protected actions; a branch cannot cross the organisation boundary. | Restricted operational |
| Department | A facility service destination such as reception, triage, consultation, laboratory, pharmacy, or cashier. | Belongs to a facility; receives QueueEntries and role-scoped work. | Facility authority with configured department scope. | Department destination is explicit and cannot be silently substituted when unavailable. | Facility configuration; activation/deactivation remains auditable. | Handoffs land on a defined receiving surface or an explicit terminal outcome. | Internal operational |
| User identity | A human or system identity used to attribute action and access. | May hold organisation/facility/department memberships or grants; acts on domain records. | Identity authority plus granted scope; professional authority is not inferred from login identity. | Identity is stable for attribution; ambiguous or stale identity denies protected action. | AUTH/USR authority; revocation behaviour is UNSUPPLIED / OPEN. | Identity, credential, scope, and current state are all checked at protected action time. | Sensitive identity |
| Membership / grant concept | The bounded relationship that supplies organisation, facility, department, capability, credential, or assurance scope. | Links a user identity to an organisation/facility/department and permitted capabilities. | AUTH/TEN/USR authority; never a product shortcut to professional authority. | A grant has one effective scope and status; conflicting or stale grants do not widen access. | Grant issue, change, expiry, and revocation require authorised governance. | Default deny; a missing, ambiguous, stale, or revoked grant cannot authorise an action. | Sensitive authority |
| Patient | The protected person record used across supported care episodes. | Has facility/organisation context; may have Visits, Encounters, results, prescriptions, payments, and ANC records. | Patient authority is organisation/facility-scoped; cross-facility sharing remains BRN/PAT-gated. | Duplicate detection and configured patient-number rules apply; a failed check-in does not create an orphan Visit. | Reception and authorised correction paths; clinical history is separately governed. | Identity corrections preserve attribution and do not merge or delete history by convenience. | PHI / highly sensitive |
| Visit | One attendance episode tying the patient to a facility and operational care path. | Contains QueueEntries, Encounter(s), orders, prescriptions, invoices, payments, receipts, and closure evidence. | Facility-scoped patient episode. | At most one same-day open Visit per patient/facility unless an authorised exception applies; one consultation charge where applicable. TRI-013 may open the episode before payer/price exists, but later setup converges on that same Visit and exact-one charge/Invoice. | SM-02; reception and closure authority. | Visit closure is terminal under REC-012; unresolved emergency financial setup blocks closure; no unsafe reopen or duplicate episode. | PHI / financial-sensitive |
| QueueEntry | The auditable operational location and handoff record for a Visit or service. | Belongs to a Visit and department/service; may reference cashier, laboratory, pharmacy, or consultation work. | Facility/department scope; SYSTEM may create only under an approved rule. | One active entry for the defined visit/department/work path; retries return the existing safe outcome. | SM-01; receiving role and SYSTEM transition rules. | Every handoff has a defined next surface or terminal state; no patient silently disappears. | PHI-linked operational |
| TriageRecord | Human-entered observations and selected acuity used before clinician work. | Belongs to a Visit/patient and feeds the consultation queue priority. | NURSE or authorised MIDWIFE scope; facility-scoped. | One applicable current triage outcome per Visit with attributed amendments where allowed. | SM-03; clinical correction authority. | Triage observes and records; it does not diagnose or automatically interpret. | PHI / clinical |
| Encounter | The long-lived clinical record for a consultation, including laboratory holds and resume. | Belongs to a Visit/patient; links diagnoses, treatment, prescriptions, orders, and amendments. | CLINICIAN or authorised MIDWIFE scope; credential-gated. | One consultation Encounter for the supplied path; laboratory resume uses the same Encounter. | SM-04; authoring clinician and approved correction path. | SIGNED history is preserved; signing, pending-result, and close states remain consistent. | PHI / clinical |
| Clinical amendment / addendum | Attributed correction or additional information linked to an existing clinical record. | References the original Encounter or signed clinical record and its author/reason. | Authoring clinician or explicitly authorised correction role. | Each amendment is attributable and does not overwrite the prior signed content. | Clinical correction authority; state-specific amendment path. | Prior history remains reconstructable; entered-in-error is explicit rather than deletion. | PHI / clinical |
| Diagnosis | Human-entered diagnosis or clinical assessment attached to an Encounter. | Belongs to an Encounter; may inform treatment and prescription records. | CLINICIAN/MIDWIFE within authorised scope. | Diagnosis entries retain author and encounter context; no automatic inference. | Encounter lifecycle; correction uses the clinical amendment path. | No system-generated diagnosis or hidden interpretation is permitted in V1. | PHI / clinical |
| Prescription | A clinician-authored medication or supplement instruction derived from a signed Encounter. | Belongs to an Encounter/patient; may create pharmacy work and an Invoice line. | CLINICIAN/MIDWIFE authority; PHARMACIST consumes the active prescription. | One stable prescription outcome per supplied clinical action; no activation from an unsigned record. | SM-06; signing and pharmacy completion rules. | Controlled/Class A products remain refused; draft prescriptions are not pharmacy-visible. | PHI / medication |
| LabOrder | The clinician's laboratory request grouping one or more ordered items. | Belongs to an Encounter; contains LabOrderItems and may hold the Encounter. | CLINICIAN/MIDWIFE; laboratory receives the authorised order. | Order identity remains stable across payment, collection, result, and late-result paths. | Order and Encounter rules; no result release by ordering alone. | A pending order is visible only to authorised roles and does not imply a released result. | PHI / clinical |
| LabOrderItem | One requested test with its own payment, specimen, result, verification, and release lifecycle. | Belongs to a LabOrder; may have a LabSpecimen and released result history. | Ordering clinician plus laboratory roles for custody and verification. | Item status is independent; partial release never falsely makes every blocker ready. | SM-05; LAB-015/017/018/023 authority. | Unverified values are not clinically released; post-release changes preserve history. | PHI / laboratory |
| LabSpecimen | The collected specimen/custody record for a LabOrderItem. | Belongs to one item and records collection/custody context. | LAB_TECH / laboratory authority. | A specimen is not silently duplicated, reused, or created when collection did not commit. | Collection and rejection/recollection rules. | Custody and result linkage remain attributable and scope-limited. | PHI / laboratory |
| Dispense | The pharmacy handover outcome for a prescription or retail sale. | Links patient or sale, prescription/product lines, stock batches, payment, and receipt. | PHARMACIST within facility scope; cashier and SYSTEM provide bounded supporting steps. | One provisional/committed handover per request identity; retry cannot create a second dispense. | SM-07; DSP-005/009/016 authority. | Handover is authoritative; no stock or final dispense completes offline. | PHI / medication / financial |
| Product / catalogue item | A sellable or prescribable medicine/product definition with instructions and classification. | Referenced by prescriptions, dispense lines, stock batches, pricing, and sales. | Pharmacy/catalogue authority within organisation/facility configuration. | Product identity and controlled/Class A classification are stable for the relevant outcome. | PHM authority; classification changes are attributable. | V1 refuses controlled/Class A workflows; no clinical interpretation is derived from catalogue data. | Internal / medication-sensitive |
| StockBatch | A received lot of a catalogue product with quantity, lot identity, and expiry. | Belongs to a product and facility; changes through StockMovements; selected by dispense. | STORE_KEEPER/PHARMACIST within facility scope. | Batch identity and expiry are stable; expired stock is never usable. A return preserves batch identity without implying that the returned location balance is usable. | Receiving, quarantine, disposal, adjustment, return, and correction authority. | FEFO is a product outcome; expired or quarantined stock cannot become usable by override, and all returns remain non-usable while OD-PH5 is BLOCKED. | Internal stock-sensitive |
| StockMovement | An attributable event explaining a stock increase, decrease, quarantine, disposal, or correction. | References a StockBatch, product event, actor, reason, and any linked dispense/return. | Facility stock authority; SYSTEM only under an approved transition. | Movement history is append-only and each correction references the original context; a return movement records its non-usable/quarantine destination while OD-PH5 is BLOCKED. | INV authority; movement is never silently removed. | No direct balance rewrite, negative usable balance, unlinked stock effect, or returned-stock increase to usable availability while OD-PH5 is unresolved. | Internal stock-sensitive |
| Invoice | The authoritative charge container for a Visit or standalone retail sale. | Contains InvoiceLines, Payments/Allocations, CreditNotes, Refunds, credits/voids, and Receipt records. GROSS INVOICE TOTAL is the sum of non-voided InvoiceLines; CURRENT AUTHORITATIVE AMOUNT DUE is separately recomputed under SM-08. | Facility financial authority. | At most one non-terminal Visit invoice; chargeable source events are not duplicated. | SM-08; issue, payment, CreditNote, Refund, correction, and closure rules. | Gross total is never silently redefined as post-credit; current due, effective applied value, outstanding balance, and any REFUNDABLE CREDIT remain visible and reconstructable. | Financial-sensitive |
| InvoiceLine | A chargeable source event and price snapshot within an Invoice. | References its source order, consultation, procedure, dispense, or sale outcome. | Financial authority with source-event attribution. | A source event/version yields one active charge line; correction creates a linked replacement or credit path. | Invoice lifecycle; void/credit rules preserve original. | No silent price, quantity, or source rewrite after finalisation. | Financial-sensitive |
| Payment | An immutable record of value received against one or more Invoices. | One Payment may fund one or more Invoices through explicit PaymentAllocations; links cashier shift, receipt, method, reference, and full-reversal history. | CASHIER/financial authority within facility scope. | One committed Payment per request identity; amount and method remain immutable; a bounded Refund does not mutate the Payment. | SM-09; PAY-005/008/012 authority. | Over-allocation is refused; full correction is whole-Payment reversal, while a CreditNote-specific partial refund is a separate Refund record. | Financial-sensitive |
| PaymentAllocation | The explicit application of a Payment to one Invoice balance/line and amount. | Links one Payment to one Invoice/line and the amount applied; historical identity remains attributable when its Payment is fully reversed and the allocation becomes ineffective for current-balance purposes. | Cashier/financial authority. | Allocation totals cannot exceed the authoritative outstanding balance; multi-Invoice allocation is explicit and every allocation is included in a full Payment reversal. | Payment commit and reversal authority. | Confirmed valid allocations contribute to CURRENT EFFECTIVE APPLIED VALUE; full reversal removes all of that Payment's allocations for current purposes; unrelated allocations remain effective. | Financial-sensitive |
| CreditNote | An attributable compensating financial record against a credited InvoiceLine/source and affected Invoice. | References the affected Invoice, original paid InvoiceLine/source, credited amount, mandatory reason, actor/authority, authoritative time, and any resulting REFUNDABLE CREDIT. | Facility financial authority. | Cannot exceed the remaining creditable value; no double-credit; original line, Invoice, Payment, and PaymentAllocation history remains retained. | SM-08 / BIL-010 correction authority. | Changes CURRENT AUTHORITATIVE AMOUNT DUE without rewriting GROSS INVOICE TOTAL or paid lines; recomputes Invoice state and makes any refundable credit explicit. | Financial-sensitive |
| Refund | A separate attributable compensating money-out record against refundable credit from a CreditNote/Invoice context. | References the CreditNote, affected Invoice, original Payment and specific PaymentAllocation where applicable, refund amount, cashier, and shift. | Facility financial authority. | Cannot exceed current refundable credit; no duplicate or over-refund; unrelated allocations, Invoices, and service gates remain unchanged. | SM-08 / PAY-008 bounded-refund authority. | A bounded partial Refund leaves the original Payment CONFIRMED and reduces refundable-credit balance; pending remains visible where no authorised supported method exists; no provider integration is implied. | Financial-sensitive |
| Receipt | The customer-facing evidence of a committed payment or supported document outcome. | Links Payment, Invoice, facility header, and any reprint history. | Cashier/facility document authority. | Reprint preserves the original meaning and has an auditable count; receipt identity is stable. | RCP authority; reversal marks history without deleting the original. | Print failure does not change payment truth. | Financial-sensitive |
| CashierShift | The accountable period linking a cashier's transactions and counted cash. | Belongs to a cashier/facility; contains payments, refunds, variance, and close evidence. | CASHIER; supervisor force-close only under approved authority. | A cashier has one applicable open shift; closed shift history is immutable. | Shift open, close, variance, and review rules. | Expected totals reconcile to transactions, reversals, and counted cash. | Financial-sensitive |
| ANCEnrolment | The supported ANC episode/contact context for a patient. | Links patient, ANC visits/contacts, observations, investigations, prescriptions, and follow-up dependency. | MIDWIFE/CLINICIAN within ANC scope; clinical validation applies. | Contact identity and actual booking context are preserved; no invented schedule rule. | SM-11 plus standard Visit/Encounter/Lab paths. | No automatic risk classification, dosing, interpretation, or unsupported appointment behaviour. | PHI / clinical |
| Appointment detail | The prospective scheduling record and any clinician/slot/follow-up details. | Would link patient, facility, clinician, Visit, and no-show/check-in outcome. | APT authority is UNSUPPLIED / OPEN / BLOCKED. | No appointment uniqueness, slot, reminder, or status rule is invented here. | SM-10 is a SUPPLIED FRAGMENT only: the supplied later-same-day appointment-arrival path includes NO_SHOW → CHECKED_IN and its clinician-routing effect. The fragment does not constitute a complete Appointment lifecycle. The complete APT state machine remains UNSUPPLIED / OPEN / BLOCKED; no slot, scheduling, reminder, cancellation, uniqueness, or other APT behaviour may be inferred. | Appointment behaviour cannot be implemented from this conceptual fragment. | PHI / operational |
| Audit / access evidence | Non-sensitive reconstruction evidence for material mutations and required protected access. | References actor, organisation/facility scope, target record, authoritative time, reason, outcome, and content reference where required. | Product/security/audit authority; SYSTEM may emit only under an approved rule. | Evidence is attributable and immutable for the event; it does not become a second business truth. | Cross-cutting with each source record; detailed AUD authority remains UNSUPPLIED. | Missing required evidence blocks the protected action; raw PHI is excluded from generic evidence. | Sensitive audit metadata |

### Domain rules

- Organisation is the tenant root and Facility is a branch. Every protected
  record and action has an explicit organisation/facility scope; missing or
  ambiguous scope denies the action.
- Clinical, laboratory, stock, dispensing, financial, payment, receipt, and
  audit history is preserved. Amendments, addenda, reversals, credits, voids,
  quarantine, disposal, and other correction records reference the original
  outcome rather than silently replacing it.
- Product identity, source-event identity, Visit/Invoice relationships,
  active queue/handoff outcomes, payment allocations, stock movements, and
  request retries have the stated uniqueness and single-outcome meaning. A
  technical persistence choice may not weaken those outcomes.
- A full Payment reversal is a whole-Payment correction: every allocation and
  every affected Invoice participates in the independently reconciled outcome.
  A CreditNote-specific Refund is bounded to its credited Invoice context;
  unrelated allocations, Invoices, and service-gate truth remain unchanged,
  and no general-purpose patient credit is assumed without explicit facility
  policy.
- Final clinical and financial history, medication and laboratory content,
  and patient identity are PHI or otherwise sensitive. Generic logs,
  telemetry, diagnostics, analytics, and audit payloads use minimised
  non-sensitive references; no retention period or legal obligation is
  invented where the authority register is OPEN.
- The conceptual model is WHAT-level only. Persistence and implementation
  mechanisms belong in the Blueprint and may not change these product
  meanings.

Do not prescribe tables, indexes, queues, or services here unless the
physical property is itself a product invariant; put implementation choices
in the Blueprint or an approved architecture record.

---

## 21. Security / Privacy / Abuse Analysis

Include abuse cases, not only accidental failures.

| Threat / abuse case | Impact | Product protection | Residual risk / open decision | Required review | Owner / status |
| --- | --- | --- | --- | --- | --- |
| Cross-organisation request or crafted identifier | Disclosure or mutation of another tenant's clinical, financial, stock, or operational data. | Default deny; explicit organisation and facility context; hidden-record non-disclosure; TI-01/TI-02; RG-01/RG-02. | No same-organisation exception is active without explicit BRN authority. | Security and product trust review | Product/security authority; REQUIRED, BRN exception OPEN |
| Cross-facility or cross-department overreach | A user sees or changes a record outside the granted branch or department. | Scope is checked at each protected action; facility is a branch, not a tenant; explicit grant and state are required. | Exact cross-facility sharing and revocation rules are AUTH/TEN/USR/BRN OPEN. | Security, organisation, and facility authority review | Product/security authority; BLOCKED where authority is missing |
| Inference from hidden records | A denied caller learns that a patient, visit, result, invoice, or queue entry exists. | Denial does not expose existence or protected fields; response and UI use a safe current-state outcome. | Detailed enumeration testing and reporting scope remain implementation evidence obligations. | Security review | Product/security authority; REQUIRED |
| Client presentation or role-label escalation | A modified client, stale tab, or misleading role label appears to grant a protected action. | Server-authoritative identity, permission, scope, credential, configuration, and state checks; default deny. | AUTH/USR credential and grant lifecycle details remain OPEN. | Security and permission review | Product/security authority; REQUIRED / AUTH-USR OPEN |
| Revoked or expired authority used by session or background work | A user continues to perform protected work after authority should no longer apply. | Recheck authoritative identity, grant, credential, state, and configuration at each protected action; deny uncertainty; audit the outcome. | Exact revocation timing, active-session behaviour, and background-job cancellation are UNSUPPLIED. | Security, governance, and operations review | AUTH/TEN/USR owners; BLOCKED until supplied |
| Duplicate click, retry, or replay | A second payment, charge, stock movement, dispense, clinical record, queue entry, or finalisation effect occurs. | Stable request identity and single-outcome rules; same retry returns the committed result; materially different reuse is refused; TI-09/TI-10. | Evidence and current execution belong in the Blueprint. | Trust regression review | Product/implementation evidence; REQUIRED |
| Concurrent or stale update | A stale actor silently overwrites newer clinical, queue, inventory, or financial state. | Stale state is refused with current state or explicit reconciliation; one committed winner; TI-11/GSC-5. | Technical mechanism is not prescribed here; conflict scenarios require evidence. | Product and trust review | Product/implementation evidence; REQUIRED |
| Deliberate alternate-path bypass | A user uses an error, print, payment, handoff, reversal, or re-entry path to bypass a gate. | Every material alternate path returns to the same scope, state, payment, audit, expiry, and approval rules; CMC constraints remain applicable. | Unsupplied epics may contain unmodelled paths and remain BLOCKED. | Product, security, and domain-owner review | Product authority; REQUIRED for supplied paths |
| PHI in logs, telemetry, diagnostics, analytics, or errors | Secondary disclosure through operational tooling or support channels. | PHI minimisation; generic records carry non-sensitive references only; TI-12/RG-12; no raw PHI in error or telemetry payloads. | Exact operational redaction and retention policy is legal/privacy OPEN. | Privacy/DPO and security review | Privacy authority; REQUIRED / legal details OPEN |
| Support, export, backup, or analytics access outside care scope | A support or operational actor uses a maintenance, export, backup, or analytics surface to read or infer protected patient content. | Support and non-care surfaces inherit organisation, facility, department, capability, state, and PHI-minimisation boundaries; no support role or export path is an implicit clinical permission. Access is attributable and reviewed where required. | Exact support-access, export, and backup review workflow is AUTH/AUD/REP/OPS OPEN. | Security, privacy/DPO, audit, and operations review | Product/security authority; BLOCKED where the governing epic is unsupplied |
| PHI in browser persistence or shared device | A later user or compromised device reads a patient chart or token from local storage. | No PHI in local or persistent browser storage; protected data remains role/scope controlled; access token is not treated as durable product state. | Device hardening and timeout details are not supplied here. | Privacy and security review | Product/security authority; REQUIRED |
| Patient snooping by an otherwise valid role | An authorised user browses records without a care or operational need. | Patient access is scope- and capability-gated, sensitive access is auditable, and hidden records are not disclosed. | Detailed purpose-of-use and review workflow remains AUD/USR OPEN. | Privacy/DPO and audit review | Product privacy/audit authority; BLOCKED where AUD is unsupplied |
| Conflicting role combination or authority substitution | One person or an administrator uses a convenient combined role to approve, perform, verify, and correct the same high-impact outcome without the required separation. | Role/capability/credential boundaries remain explicit; verifier, author, cashier, pharmacist, and approver separation is preserved where the supplied workflow requires it; an administrator cannot substitute for clinical authority. | Exact role-combination and separation matrix is AUTH/USR OPEN where not supplied. | Product, clinical, pharmacy, finance, and security review | Governance authority; REQUIRED / matrix OPEN |
| Privileged override, discount, waiver, explicitly supplied closure exception, CashierShift force-close, or takeover abuse | An operator bypasses a gate or changes a material outcome without accountability. | Separate approval authority, mandatory reason where supplied, bounded scope, visible evidence, no general Visit force-close, and no admin substitution for clinical authority. | Exact authority matrix and exception expiry remain AUTH/TEN/USR/financial OPEN. | Product, finance, clinical, and security review | Named qualified authority per action; REQUIRED / gaps OPEN |
| Financial manipulation | Overpayment, duplicate charge, silent discount, refund abuse, or an unreconciled cashier shift. | Immutable payments and final records; exact allocation and invoice reconciliation; reversal/credit/refund paths; shift variance evidence; TI-08/RG-08. | Credit-balance and legal/fiscal rules remain authority-dependent where marked OPEN. | Finance and audit review | Finance authority; REQUIRED |
| Stock or medicine abuse | Expired or controlled medicine is sold/dispensed, stock becomes negative, or movement history is rewritten. | Absolute expired-stock refusal; controlled/Class A V1 refusal; append-only attributable movements; FEFO and quarantine/disposal paths; TI-05/TI-06/TI-07. | Facility stock-approval details and reporting authority remain OPEN. | Pharmacy and stock-owner review | Pharmacy authority; REQUIRED |
| Unapproved clinical interpretation or unsafe sign-off | Product is mistaken for a clinical decision maker or an incomplete record becomes final. | No automated diagnosis, dosing, allergy/interaction matching, risk classification, result interpretation, or critical-result conclusion; signing and amendment rules; TI-03/TI-04/TI-14. | Clinical validation gates and credential scope remain OPEN/BLOCKED. | Clinical authority review | Clinical authority; BLOCKED until applicable validation |
| Released-result tampering or notification failure | A clinician acts on an unverified or silently changed result, or the required amendment/review path is lost. | Verification before release; released history preserved; attributable amendment and required review/notification outcome; RG-04. | External notification effect is not activated without GSC-10 authority. | Laboratory, clinical, privacy, and operations review | Laboratory authority; REQUIRED / notification OPEN |
| Offline or disconnected high-impact completion | A local attempt is treated as final without authoritative stock, money, clinical, or audit safeguards. | TI-15/RG-15; visible save/pending/unknown state; no offline completion of sign-off, payment, stock, dispensing, sale, or final action. | Draft persistence and recovery details must follow the supplied product path; no offline shortcut is inferred. | Product, clinical, pharmacy, and operations review | Product/operations authority; REQUIRED |
| External effect timeout or compromised provider | A provider succeeds, fails, duplicates, or returns an unknown result and local truth becomes unsafe. | GSC-10 outbound contract requires ordering, idempotency, authoritative facts, timeout/unknown semantics, pending/failure state, reconciliation, compensation, and audit; no provider class is enabled by architecture alone. | Actual effect and provider authority are UNSUPPLIED / OPEN. | Product, security, legal/privacy, and operations review | External-effect authority; BLOCKED until specified |
| Print, reprint, or document substitution | A failed printer changes truth, or a reprint is used to forge or hide a financial/clinical outcome. | Screen-displayable fallback; print failure does not alter truth; stable document identity and audited reprint; role-scoped documents. | Facility document retention and tamper-evidence detail remain OPEN. | Product, finance, pharmacy, and operations review | Facility/product authority; REQUIRED |
| Audit evidence suppression or tampering | A material action cannot be reconstructed or appears completed without evidence. | Required audit/access evidence is attributable, immutable, non-sensitive, and part of action completion; missing required evidence blocks completion; TI-13/RG-13. | Detailed AUD records, review cadence, and retention are UNSUPPLIED. | Security, audit, and privacy review | Audit authority; BLOCKED until AUD detail supplied |
| Availability or degraded-state deception | A blank, stale, or partial surface causes an unsafe action or hides pending work. | Standard loading, empty, error, unavailable, denied, stale/conflict, degraded, read-only, and terminal states; visible next action; preserve committed truth. | Recovery objectives and operations runbook are OPEN; no availability number is invented. | Operations and product review | OPS authority; REQUIRED / OPS detail OPEN |
| Appointment, reporting, branch, or operations gap exploited as permission | An unsupplied capability is inferred from a reference and used to access or change data. | Unsupplied APT, REP, BRN, OPS, AUTH, TEN, USR, CAT, PAT, and AUD behaviour is marked OPEN/BLOCKED; absence is not permission. | Detailed authority must be supplied through the applicable change/validation process. | Product, security, and governance review | Product authority; BLOCKED |
| Retention or external-obligation assumption | Records are retained, deleted, exported, or waived contrary to a future legal or binding requirement. | This Product Spec makes no new legal retention claim; records are preserved according to product integrity rules, while legal/privacy obligations remain explicit OPEN decisions. | OD-L1–OD-L8 and any applicable External Binding Authority must be resolved before affected release. | Qualified legal/privacy authority | Legal/DPO authority; OPEN / BLOCKED |

### Security / privacy review rule

The mitigations above are product protections, not implementation permission.
Server-side authority, state and credential validation, scope isolation,
auditability, and visible safe outcomes remain mandatory across every interface.
No support, export, report, background operation, or alternate path may be
treated as outside the same boundaries. Current implementation status and
evidence belong in the Blueprint LIVE EXECUTION STATE; unresolved AUTH, TEN,
USR, CAT, PAT, APT, REP, AUD, BRN, and OPS decisions remain OPEN/BLOCKED.
No legal retention period or external obligation is invented by this section.

---

## 22. Blockers

A blocker must never be silently resolved by an implementation agent.

| Blocker ID | Category | Statement | Affected behaviour / release | Owner | Required decision or evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| BL-01 | External authority / legal blocker | No External Binding Authority source, applicability record, or authorised interpretation has been supplied. | Any legal, regulatory, contractual, privacy, fiscal, retention, HMIS, or compliance claim; infrastructure and affected release gates. | Ugandan counsel + DPO; named external interpreters are OPEN | Supply exact source/version, applicability, authorised interpretation, affected IDs, monitoring owner, and review trigger in the EBA register; resolve OD-L1–OD-L8. | BLOCKED |
| BL-02 | Product authority blocker | The authorised Product Spec/project-level owner and approver is Mutambo Bernard; OD-P1 V1-boundary approval is APPROVED as written; the assigned project level is KEEP LEVEL 3. Human governance prerequisites, the independent whole-candidate review, and final human freeze approval are complete; Product Spec v1.0 is formally frozen. OD-P2..OD-P9 remain individually OPEN/BLOCKED with their own downstream gates and are not universal Product Spec freeze blockers; they may remain unresolved in a frozen Product Spec only while their affected gates remain closed and are not resolved or implemented by this freeze. | V1 boundary, commercial/subscription choices, service configuration, debt/credit policy, pharmacy pilot eligibility, reporting priority, Product Spec freeze, and each affected implementation, pilot, commercial, reporting, finance, privacy, pharmacy, or release gate. | Mutambo Bernard | Human governance approvals, independent review by GPT-5.5 Sol xhigh, and final human freeze approval are recorded 2026-08-30; Product Spec v1.0 freeze is complete. Resolve each OD-P2..OD-P9 before its own affected gate; Product Spec freeze does not resolve them and implementation agents may not choose their answers. | RESOLVED |
| BL-03 | Authority and identity blocker | Detailed AUTH, TEN, and USR story authority is unsupplied, including grant/credential lifecycle, revocation propagation, active-session behaviour, and background-operation maximum/channel semantics. | Organisation/facility access, user and professional authority, revocation, support access, and every V1 protected capability that depends on these rules. | Product owner + authorised identity/tenancy domain owners | Supply the missing stories and authority matrix; define revocation detection, propagation, and safe denial evidence before dependent implementation or release. | BLOCKED |
| BL-04 | Unsupplied capability dependency blocker | CAT, PAT, REP, AUD, BRN, and OPS story definitions and governing authority are not supplied, although V1 stories reference them. | Catalogue/price configuration, patient identity, reporting/export, audit/access evidence, cross-facility policy, sweeps, notifications, and operational readiness. | Product owner + affected domain owners | Reconcile the referenced IDs to authoritative stories and decisions; absence of detail is not implementation permission. | BLOCKED |
| BL-05 | Appointment and journey-source blocker | The full APT state/workflow is absent and the source part containing Journey F is absent; only the supplied appointment fragment and Journeys A–E are canonical here. | Appointment scheduling, reminders, slot/no-show lifecycle, follow-up behavior, and any J-06-dependent release or implementation scope. | Product owner + APT authority | Supply the APT epic/state machine and missing Journey F source, or explicitly remove the dependency through approved change control. | BLOCKED |
| BL-06 | Clinical and professional-authority blocker | OD-C1–OD-C12 clinical/ANC decisions and professional credential rules remain OPEN/BLOCKED, including credential handling; current V1 signing blocks expired, missing, or uncertain clinical credentials while OD-04 remains OPEN. | ANC, diagnosis/signing, triage, laboratory interpretation/release, paediatric claims, clinical copy, and any professional-authority gate. | Contracted clinical advisor + authorised credential authority | Record clinical validation, credential evidence, affected IDs, and release disposition; agents may not invent thresholds or professional authority. | BLOCKED |
| BL-07 | ANC provenance blocker | ANC-007 was truncated in the supplied source and its surviving behaviour was completed from already-established laboratory/encounter rules; provenance and clinical acceptance remain review concerns. | ANC investigation ordering, payment/collection/result loop, same-Encounter resume, pending-result signing, and ANC release readiness. | Product owner + contracted clinical advisor | Confirm the reconstructed boundary against authoritative source or approve the completed canonical ACs through the applicable review/change record. | BLOCKED |
| BL-08 | Pharmacy and regulatory blocker | OD-PH1–OD-PH9 remain unresolved for pharmacy pilot eligibility, pharmacist supervision, external prescriptions, dispensing-register content/retention, returns, disposal, cold-chain scope, exceptions, and credential absence. | Pharmacy go-live, compliance claims, external Rx, returns/disposal, controlled-medicine pilot decisions, and any affected V1/V1.1 gate. | Contracted pharmacist advisor + regulatory authority | Record pharmacist/regulatory decisions and evidence; baseline expired-stock and controlled/Class A prohibitions remain in force. | BLOCKED |
| BL-09 | Pilot and operational-readiness blocker | OD-R1–OD-R9 and site evidence are not complete for paper ANC timing, network conditions, payment dominance, duplicates, role combinations/shared devices, appointments, reports, or printers. | Pilot selection, usability/performance judgments, printing, low-bandwidth operation, and V1 rollout readiness. | Product/pilot owner + facility operators | Complete the named pilot research and operational evidence; no site condition is assumed from a generic environment. | BLOCKED |
| BL-10 | Cross-cutting decision blocker | OD-18–OD-22 remain open: triage acuity/auto-suggestion, allergy warning, paediatric percentile display, nurse-initiated laboratory ordering, and stale-visit sweep/closure. | TRI/QUE/LAB/REC/ANC behavior, clinical safety, and OPS-dependent closure. Current safe V1 boundaries remain explicit but are not silently finalised. | Existing named product/clinical/operations owners | Resolve each existing decision record with affected IDs, evidence, and any required Product Spec change; do not create duplicates. | OPEN / BLOCKED |
| BL-11 | Technical authority blocker | OD-T1–OD-T3 and any infrastructure/implementation choice requiring Product Spec authority remain unresolved; technical convenience cannot supply product meaning. | Outbox need, idempotency evidence-retention period, stock-count approver exception, and any dependent Blueprint implementation decision. | Engineering lead + product owner | Record the technical decision and its Product Spec/Blueprint impact; if behaviour changes, use Product Spec change control. | OPEN |

No additional contradiction was found during the Sections 15–21 self-review
that can be safely closed here. Existing ambiguity remains represented by the
blockers and decisions above; implementation agents must not treat an OPEN or
BLOCKED row as permission.

If a blocker is removed by a product or architecture decision, record that
decision and its scope impact under Section 26.

---

## 23. Assumptions

Make assumptions explicit and classify their implementation impact.

| Assumption ID | Assumption | Why needed | Consequence if false | Owner | Validation method | Classification | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AS-01 | The initial V1 operating context is a Ugandan private-sector facility, with the pilot context described as a single-branch Kampala medical centre, EAT timezone, and UGX currency. | It bounds the current release context, facility-day behavior, and operating examples without asserting a legal or market fact. | Pilot usability, time, currency, and release evidence may not represent the intended site; affected context and Product Spec scope require review. | Product / pilot owner | Confirm pilot site, timezone, currency, and release context before the pilot gate. | MUST BE VALIDATED | OPEN |
| AS-02 | Organisation is the tenant root and Facility is a branch, not a tenant; cross-facility access fails closed unless an explicitly authorised exception applies. | It preserves the supplied tenancy and trust boundary across every V1 workflow. | Tenant isolation and all dependent scope decisions would be wrong; a Product Spec change and trust re-review would be required. | Product and tenancy authority | Verify against Section 1, Sections 8–9, TI-01, and RG-01 in the authority review. | MAY SAFELY REMAIN | CONFIRMED |
| AS-03 | V1 must be usable in low-bandwidth, unreliable-power conditions with visible save state and no offline completion of high-impact actions. | It is the operating premise for NFR-01–NFR-03 and the safe degraded-state contract. | Performance and resilience evidence would not represent the intended facility; affected NFR scope and pilot readiness must be revisited. | Product / pilot owner | Measure the agreed site network and device profile and run the NFR-01/NFR-02 scenarios. | MUST BE VALIDATED | OPEN |
| AS-04 | Insurance is not a V1 payer path; the supplied payer set is CASH and SELF_PAY_MOMO. | It keeps billing and payment behavior bounded to the supplied V1 scope. | A different payer scope changes stories, billing, privacy, and release boundaries; it cannot be added by implementation convenience. | Product owner | Resolve the affected OD-P product boundary before billing or commercial approval. | MUST BE VALIDATED | OPEN |
| AS-05 | Direct Mobile Money, bank, card, SMS, WhatsApp, and other provider integrations are not enabled by the current V1 authority; an operator-entered reference is evidence only. | It prevents an external effect or provider obligation from being inferred from a payment field or architecture allowance. | Any intended integration requires a new Product Spec contract, external authority, and applicable change control. | Product / external-effect authority | Review GSC-10 and the external-authority register before any effect is specified. | MAY SAFELY REMAIN | CONFIRMED |
| AS-06 | Pay-before versus pay-after is configurable by service family; the dominant rule is not assumed to apply identically everywhere. | It supports the supplied triage, laboratory, pharmacy, and billing branches without hard-coding a universal policy. | Queue, payment, and handoff behavior could be unsafe or misleading at a facility; affected policy requires product decision. | Product owner + facility pilot owner | Collect site evidence and resolve OD-R3 before the affected pilot/release gate. | MUST BE VALIDATED | OPEN |
| AS-07 | The target laboratory context is a small clinic with one technician, RDT/microscopy/haematology work, minutes-scale bench work, and batch verify-and-release. | It bounds the supplied laboratory workflow and explains why no extra bench state is currently required. | Laboratory staffing, worklist, and state evidence may not fit the site; OD-10 and operational readiness require review. | Laboratory/product owner | Validate staffing and bench flow during pilot research and review LAB evidence. | MUST BE VALIDATED | OPEN |
| AS-08 | Pharmacy is both retail and dispensing, and a dispensing register is a material operational need; this does not assert regulatory compliance. | It supports the supplied pharmacy, stock, retail, and register stories while keeping compliance claims open. | Pharmacy scope, register content, or pilot eligibility may change; affected PHM/DSP/INV behavior and OD-PH decisions require review. | Pharmacist advisor + product owner | Validate the pilot catalogue, supervision, register, and compliance requirements under OD-PH1–OD-PH9 and OD-L7. | MUST BE VALIDATED | OPEN |
| AS-09 | HMIS Form 031 and Form 071 may shape reporting aids for manual completion, but V1 does not claim certified HMIS/DHIS2 submission. | It preserves the source boundary without inventing a statutory obligation or certification. | Any reporting, form, or compliance statement would need legal/MoH authority and may be blocked or changed. | Product owner + Ugandan counsel / DPO | Resolve OD-L5 and record the exact applicable authority before making any claim. | BLOCKS IMPLEMENTATION | OPEN |
| AS-10 | Paper is the fallback for supported print flows, and a screen-displayable document is used when a print surface is unavailable. | It preserves the supplied resilience and document outcomes for slips, labels, receipts, and reports. | A printer outage could hide or misstate a committed outcome; print and operations evidence would fail. | Product / operations owner | Validate facility printer models, paper sizes, and fallback flows under OD-R9. | MAY SAFELY REMAIN | CONFIRMED |
| AS-11 | V1 provides no clinical decision support: no interaction or contraindication checking, dose checking, acuity computation, diagnosis suggestion, or result interpretation; reference displays remain neutral. | It is the explicit safety boundary used by TRI, RX, ANC, TI-14, and RG-14. | Any relaxation would change clinical product meaning and require clinical authority, a new or superseding frozen Product Spec, and trust re-review. | Contracted clinical advisor + product owner | Keep the negative regression gate active; resolve OD-18–OD-21 only through the existing decision records. | MAY SAFELY REMAIN | CONFIRMED |
| AS-12 | Controlled/Class A medicines are unsupported in baseline V1, and expired KlinKlik-managed stock cannot be issued, dispensed, sold, or used. | It is the explicit medicine-safety boundary for catalogue, stock, prescription, and dispensing flows. | A prohibited medicine could enter the product; release is blocked and a lawful Product Spec change would be required. | Pharmacist advisor + product owner | Exercise TI-05/TI-06 and RG-05/RG-06 across all supported entry paths. | MAY SAFELY REMAIN | CONFIRMED |
| AS-13 | Signed clinical records are immutable; corrections use attributed addenda, amendments, versioning, or entered-in-error paths rather than destructive rewriting. | It preserves clinical provenance and the supplied encounter/laboratory correction model. | Clinical history could become unsafe or unreconstructable; trust gates fail and the correction path requires authority review. | Clinical authority | Exercise TI-03/RG-03 and the applicable ENC/LAB amendment scenarios. | MAY SAFELY REMAIN | CONFIRMED |
| AS-14 | PHI is not placed in browser persistence, generic logs, telemetry, diagnostics, analytics, or audit payloads; access tokens are not treated as durable product state and patient charts are not SSR content. | It is the explicit privacy boundary for NFR-07, TI-12, and Section 21. | Secondary disclosure or unsafe shared-device exposure occurs; privacy/security review blocks the affected release. | Privacy/DPO + security authority | Inspect representative responses, browser persistence, logs, telemetry, diagnostics, and access evidence. | MAY SAFELY REMAIN | CONFIRMED |
| AS-15 | Every material mutation is audited; money, clinical, and stock creations are retry-safe, and concurrent edits produce one safe authoritative outcome. | It binds the supplied trust, integrity, concurrency, and audit contracts across the V1 journeys. | Duplicate or contradictory high-impact effects become possible; RG-09–RG-13 fail and implementation is blocked. | Product, security, finance, clinical, and pharmacy authorities | Run the applicable trust suite and reconcile evidence in the Blueprint LIVE EXECUTION STATE. | MAY SAFELY REMAIN | CONFIRMED |

An assumption marked MUST BE VALIDATED is not permission to implement a
guessed outcome. If it blocks behaviour, use Section 22 and Section 27.

---

## 24. Open Decisions

Implementation agents must not choose answers to unresolved decisions unless
explicitly authorised in the decision record.

Questions requiring interpretation of law, regulation, a binding contract, or
formal external policy must name the authorised human, legal, compliance, or
domain authority. An agent recommendation is never an interpretation or an
approval.

| Decision ID | Question | Owner | Affected Product Spec IDs / capabilities | Blocking effect / needed before | Current safe handling (non-authoritative) | Decision evidence required | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OD-P1 | Confirm the revised V1 boundary, including direct receiving, basic counts, simple appointments, and minimal disposal. | Mutambo Bernard | Entire V1 backlog; Sections 3, 6, 19, 25 | V1-boundary approval was blocking before final epic decomposition and freeze; this prerequisite is satisfied by the recorded human approval. | Use only the supplied 194 stories and explicit boundaries; do not expand scope. | Approver: Mutambo Bernard; Decision: Current V1 boundary approved as written; Date: 2026-08-30; no scope expansion; supplied 194 stories remain canonical; OD-P2..OD-P9 remain unresolved and individually gated. | APPROVED |
| OD-P2 | Confirm the pricing model and infrastructure cost basis, including whether a per-facility model is authorised. | Product owner | Commercial model; product-owner decisions; any commercial story | Needed before pilot commercial conversation; no price promise is authorised. | No infrastructure figure or commercial commitment is asserted. | Approved commercial decision and supporting vendor/operating evidence. | OPEN |
| OD-P3 | Decide default cross-branch patient visibility beyond the supplied stub. | Product owner + BRN/privacy authority | Sections 8–9; TI-01; GSC-2; PAT/BRN behavior | Needed before a multi-branch pilot or any cross-facility patient read. | Cross-facility access fails closed; no exception is active. | Explicit scope, privacy, and BRN capability decision with affected IDs. | OPEN |
| OD-P4 | Decide whether unpaid invoices and credit customers are needed in V1. | Product owner + finance authority | BIL/PAY/REP; G4; closure/debt paths | Needed before the billing slice and any debtor reporting behavior. | Supplied debt/waiver paths remain bounded; no new credit behavior is inferred. | Pilot demand and approved financial/product policy. | OPEN |
| OD-P5 | Confirm pilot site selection and wave sequence. | Product / pilot owner | V1 release; OD-R1–OD-R9; Sections 6, 17, 19 | Blocking for pilot/Wave A readiness. | No site-specific readiness is assumed. | Named site, wave plan, and recorded pilot approval. | BLOCKED |
| OD-P6 | Decide whether staff may configure catalogue/prices or owner approval is required. | Product owner + organisation authority | PHM/CAT; PP-04; pricing permissions | Needed before settings build and price-change permissions. | Protected price/configuration authority remains default-deny and OPEN. | Approved authority matrix and audit/revocation rules. | OPEN |
| OD-P7 | Decide whether target pharmacies can operate without controlled medicines. | Product owner + pharmacist/regulatory authority | PHM/RX/DSP/INV; TI-06; pharmacy pilot | Blocking for pharmacy pilot selection and go-live. | Controlled/Class A workflow remains unsupported in baseline V1. | Pilot evidence plus pharmacist and regulatory decision. | BLOCKED |
| OD-P8 | Decide which report formats are essential on day one. | Product / pilot owner | REP/RCP; reporting and export scope | Needed before the reporting slice. | Only supplied print/export behavior is retained; no format is promised. | Pilot usage evidence and approved format list. | OPEN |
| OD-P9 | Decide the billing-safe invoice-description policy for clinic-mode medication lines. | Product owner + privacy/finance authority | BIL/DSP; PP-05; NFR-07 | Needed before clinic billing behavior is released. | Use minimised service/product descriptions; do not expose unnecessary clinical detail. | Privacy and finance review of examples and affected stories. | OPEN |
| OD-C1 | Confirm the complete ANC field set. | Contracted clinical advisor | ANC-001–ANC-004; SM-11; Section 19 | Blocking for ANC implementation and release. | Use only the supplied fields; no clinical field is invented. | Signed clinical validation and versioned field record. | BLOCKED |
| OD-C2 | Confirm GA/EDD precedence and dating-scan cut-off. | Contracted clinical advisor | ANC-002; ANC state and summaries | Blocking for ANC dating behavior. | No precedence or cut-off beyond the supplied rule is assumed. | Clinical validation of the precedence rule and affected ACs. | BLOCKED |
| OD-C3 | Confirm the late-booking combined-goals rule. | Contracted clinical advisor | ANC-002/005; J-05 | Blocking for late-booking ANC behavior. | Preserve actual booking context; do not invent a combination algorithm. | Clinical approval of the versioned schedule rule. | BLOCKED |
| OD-C4 | Decide whether diagnosis is mandatory before sign-off. | Contracted clinical advisor | ENC-017; DX-002; TI-14 | Non-blocking to baseline only while the safe default remains off. | Do not force diagnosis from this open decision; record explicit human entry where supplied. | Clinical decision and sign-off acceptance criteria. | OPEN |
| OD-C5 | Confirm required ANC observations and gestational thresholds. | Contracted clinical advisor | ANC-003/004; SM-11 | Blocking for any ANC threshold or required-field behavior. | Do not hard-code thresholds; retain an explicit unable-to-measure reason path where supplied. | Clinical validation and versioned rule record. | BLOCKED |
| OD-C6 | Confirm manual risk-flag vocabulary and all clinical copy. | Contracted clinical advisor | ANC-005/006; TI-14 | Blocking for ANC risk-flag and guidance content. | No automatic risk classification or platform guidance is enabled. | Clinical review of vocabulary, copy, ownership, and boundaries. | BLOCKED |
| OD-C7 | Confirm pregnancy closure vocabulary. | Contracted clinical advisor | ANC-001; SM-11 | Blocking for any pregnancy-episode closure claim. | No closure reason beyond supplied structure is invented. | Clinical validation of reasons and terminal handling. | BLOCKED |
| OD-C8 | Decide whether a critical-lab workflow is approved or prohibited. | Contracted clinical advisor + laboratory authority | LAB-023; TI-04; GSC-10 if notification is used | Non-blocking for baseline V1; blocked for any automated critical-value behavior. | Manual flag/acknowledgement only where supplied; no automated rule pack. | Clinical/laboratory approval and notification contract. | OPEN |
| OD-C9 | Decide the clinical amendment-window policy. | Contracted clinical advisor | ENC/LAB amendment paths; TI-03/TI-04 | Needed before any bounded amendment-window claim. | Preserve history and allow only the supplied attributed correction path. | Clinical decision on window, roles, and affected evidence. | OPEN |
| OD-C10 | Confirm paediatric vitals and minimum paediatric workflow. | Contracted clinical advisor | TRI-002/011; PAT dependencies | Blocking for any paediatric product claim. | No percentile or paediatric clinical interpretation is enabled. | Clinical validation of fields, ranges, and scope. | BLOCKED |
| OD-C11 | Confirm consultation templates and copy-forward behavior. | Contracted clinical advisor | ENC documentation; G2 | Medium priority before the affected consultation UX is frozen. | No silent copy-forward or template semantics are inferred. | Clinical review of template content and provenance. | OPEN |
| OD-C12 | Decide whether an SFH reference band may be displayed and from what source. | Contracted clinical advisor | ANC-004/005; TI-14 | Non-blocking for baseline; blocked for any reference-band display. | No SFH interpretation or band is displayed. | Clinical validation and authoritative source citation. | OPEN |
| OD-PH1 | Confirm pilot catalogue classification. | Contracted pharmacist advisor | PHM-001; TI-05/TI-06 | Blocking for pharmacy go-live. | Only a validated test catalogue may be used; controlled/Class A remains refused. | Pharmacist-approved classification and pilot catalogue. | BLOCKED |
| OD-PH2 | Decide pharmacist presence/supervision and block-versus-warn behavior. | Contracted pharmacist advisor | PHM/DSP/INV; P-12/P-16 | Blocking for pharmacy operations requiring the decision. | Do not infer professional supervision from a role label. | Pharmacist and regulatory approval of supervision and gate behavior. | BLOCKED |
| OD-PH3 | Confirm external-prescription minimum fields and validity. | Contracted pharmacist advisor + regulatory authority | RX-007; external prescription path | Blocking for external Rx behavior. | External items remain printable but no validity or legal claim is invented. | Pharmacist/regulatory field and validity decision. | BLOCKED |
| OD-PH4 | Confirm dispensing-register contents and retention. | Contracted pharmacist advisor + legal/regulatory authority | DSP-013; REP/AUD; NFR-19 | Blocking for a compliance claim, not for a non-claim internal log. | No statutory completeness or retention period is claimed. | Approved register specification and applicable authority/retention record. | BLOCKED |
| OD-PH5 | Decide the return-to-resale default. | Contracted pharmacist advisor | DSP-016; INV correction paths | Blocking for returns. | Safe non-resale/quarantine handling remains the default until approved. | Pharmacist decision with stock-safety evidence. | BLOCKED |
| OD-PH6 | Confirm disposal record fields, witnesses, and certificates. | Contracted pharmacist advisor + regulatory authority | INV-011; V1.1 disposal | Blocking for the affected V1.1 disposal scope. | No disposal certificate or witness rule is invented. | Pharmacist/regulatory record and retention decision. | BLOCKED |
| OD-PH7 | Decide cold-chain scope in the pilot. | Contracted pharmacist advisor | PHM/INV; pilot facility | Blocking only for a site that stocks cold-chain products. | Temperature monitoring/excursion management remains outside V1. | Site catalogue evidence and pharmacist decision. | BLOCKED |
| OD-PH8 | Decide whether any pharmacist-authorised prescription-required exception may exist. | Contracted pharmacist advisor + product authority | DSP-013; PHM-001 | Blocking for an exception; default is no exception. | No override weakens the controlled/expired medicine guarantees. | Explicit pharmacist/product authority and bounded audit rule. | BLOCKED |
| OD-PH9 | Confirm credential-absence behavior per pharmacy action. | Contracted pharmacist advisor | PHM/DSP/INV; TI-02 | Needed before credential-gated pharmacy actions are released. | Default is block on missing/uncertain credential; no professional authority is inferred. | Credential decision and action-by-action matrix. | OPEN |
| OD-L1 | Confirm hosting and processor arrangements covering all data resting places. | Ugandan counsel + DPO | NFR-07/NFR-19; infrastructure and all sensitive data | Blocking before infrastructure is provisioned. | No processor, hosting, or retention claim is inferred. | Exact authority source, applicability, and authorised interpretation. | BLOCKED |
| OD-L2 | Confirm permissibility and documentation of cross-border processing. | Ugandan counsel + DPO | NFR-07; organisation and data scope | Blocking before cross-border processing or contract. | No cross-border processing permission is assumed. | Legal interpretation and affected data-flow record. | BLOCKED |
| OD-L3 | Confirm controller/processor roles, DPA, registration, DPO, DPIA, and breach handling. | Ugandan counsel + DPO | Privacy/security/audit; pilot readiness | Blocking before pilot. | No legal role or breach obligation is invented. | Authorised legal/privacy decision and evidence register. | BLOCKED |
| OD-L4 | Confirm clinical and financial retention periods. | Ugandan counsel + DPO | NFR-19; clinical, financial, stock, and audit history | Blocking before general availability. | Product integrity preserves history; no period is asserted. | Applicable legal/regulatory source and retention schedule. | BLOCKED |
| OD-L5 | Confirm current HMIS forms and private-facility obligations. | Ugandan counsel + MoH/regulatory authority | REP; HMIS Form 031/071 references | Blocking before any claim beyond transcription assistance. | Reports remain aids for manual completion, not certified submissions. | Current form versions and authorised interpretation. | BLOCKED |
| OD-L6 | Confirm fiscal invoicing, VAT, numbering, and credit-note obligations. | Ugandan counsel + tax authority | BIL/PAY/RCP; financial claims | Blocking before tax feature or compliance claim. | No EFRIS/VAT/fiscal claim is made. | Applicable fiscal authority and approved interpretation. | BLOCKED |
| OD-L7 | Confirm pharmacy regulatory requirements for records, restricted medicines, destruction, recalls, and disposal. | Ugandan counsel + pharmacist/regulatory authority | PHM/INV/DSP; compliance claims | Blocking before pharmacy compliance claim. | Baseline V1 refuses controlled/Class A and expired stock; no wider compliance claim. | Exact regulation/guidance and authorised interpretation. | BLOCKED |
| OD-L8 | Decide whether customers must be contractually required to register with the data-protection regulator. | Ugandan counsel + DPO | Organisation onboarding and contracts | Medium; needed before any contractual requirement. | No customer legal obligation is asserted. | Legal advice and contractual policy record. | OPEN |
| OD-R1 | Establish the paper ANC timing baseline. | Product / pilot owner | ANC usability gate; J-05; NFR-06 | Required before the ANC usability gate can be judged. | No timing target is invented. | Observed site workflow and pilot record. | BLOCKED |
| OD-R2 | Establish real network conditions at the site. | Product / pilot owner | NFR-01–NFR-03; G6 | Needed before low-bandwidth/performance readiness is judged. | Use the agreed profile only after site measurement. | Measured site conditions and reproducible test profile. | OPEN |
| OD-R3 | Establish pay-before versus pay-after dominance. | Product / pilot owner | REC/TRI/LAB/DSP/PAY gates | Needed before facility payment-gate configuration. | Service-family configuration remains explicit and reversible through authority. | Pilot observations and product policy decision. | OPEN |
| OD-R4 | Establish duplicate-creation rate and phone availability. | Product / pilot owner | PAT/REC; duplicate and contact flows | Needed for identity and operational readiness. | Duplicate safety remains mandatory regardless of measured rate. | Pilot evidence with privacy-safe aggregate data. | OPEN |
| OD-R5 | Establish receiving, counting, and selling behavior in practice. | Product / pilot owner + pharmacist | INV/DSP/PHM | Needed before stock/POS pilot readiness. | Append-only stock and expiry guarantees remain mandatory. | Observed workflow and pharmacist sign-off. | OPEN |
| OD-R6 | Establish role combinations and shared-device behavior. | Product / pilot owner + governance authority | AUTH/TEN/USR; Section 21 role separation | Needed before access and shared-device readiness. | Default deny and role separation remain; no combined-role permission is inferred. | Role research and approved authority matrix. | OPEN |
| OD-R7 | Establish sufficiency of a day-list appointment. | Product / pilot owner | APT-001; J-01/J-05 dependency | Needed before appointment scope is selected. | No appointment lifecycle is enabled from the fragment. | Pilot evidence and product decision. | OPEN |
| OD-R8 | Establish which reports are actually used. | Product / pilot owner | REP references; NFR-17 | Needed before reporting scope and format choice. | No unsupplied report is treated as complete. | Pilot usage evidence and approved report list. | OPEN |
| OD-R9 | Establish printer models and paper sizes on site. | Product / pilot owner | RCP/REC/DSP/BIL; NFR-06/NFR-16 | Needed before print readiness is judged. | Screen-displayable fallback remains required. | Site inventory and print walkthrough evidence. | OPEN |
| OD-T1 | Decide whether an outbox mechanism is genuinely needed in V1 or can be deferred. | Engineering lead + product owner | GSC-10; Blueprint implementation choice | Needed before the affected technical implementation is frozen. | No implementation mechanism is required by this Product Spec. | Product-owned technical decision and Blueprint impact record. | OPEN |
| OD-T2 | Decide exact idempotency-record retention beyond 24 hours for money and stock operations. | Engineering lead + product/finance authority | TI-10; NFR-10; payment/stock evidence | Needed before evidence and reconciliation retention are frozen. | Financial reconciliation must not be weakened; no duration beyond supplied guidance is asserted. | Technical/product/finance decision with evidence-age rule. | OPEN |
| OD-T3 | Decide whether a second stock-count approver may be waived for single-authorised-user facilities and how the gap is disclosed. | Engineering lead + product/stock authority | INV count approval; TI-07/TI-13 | Needed before the affected approval exception is released. | No second-approver waiver is active; the gap must be disclosed if approved. | Product/stock authority and pilot evidence. | OPEN |
| OD-04 | Decide whether an expired clinician licence at signing blocks or warns. | Clinical/legal authority + product owner | ENC-017; TI-02/TI-03 | Needed before a medico-legal signing rule is claimed. | Current safe handling is default-deny: an expired, missing, or uncertain clinical credential blocks signing while OD-04 remains unresolved; this is a Product Spec safety outcome, not a legal conclusion. Any later policy change requires Product Spec change control and authorised clinical/legal/product authority. | Authorised medico-legal interpretation and affected ACs. | OPEN |
| OD-07 | Decide whether orders after a signed Encounter require a new Encounter or an addendum-linked order. | Clinical/product authority | LAB-002; ENC-023; LAB-023 | Needed before late-order behavior is frozen. | Current safe handling preserves signed history and uses the supplied addendum path. | Clinical/product decision and state/evidence mapping. | OPEN |
| OD-08 | Decide whether the problem list may be auto-derived from diagnoses. | Clinical/product authority | ENC-009; TI-14 | Needed before any automatic problem derivation. | Manual promotion only; no automatic derivation is enabled. | Clinical validation and explicit product decision. | OPEN |
| OD-09 | Decide whether facility-authored ANC guidance text may be displayed and how ownership/liability is attributed. | Clinical/product authority | ANC-005 and ANC content; TI-14 | Needed before any facility guidance is enabled. | No platform guidance; facility-authored content must be clearly attributed if later approved. | Clinical/product/privacy decision and copy record. | OPEN |
| OD-10 | Confirm whether a laboratory IN_PROGRESS bench-tracking state is needed. | Product / pilot owner + laboratory authority | LAB-007/LAB-010; SM-05 | Needed before a bench-tracking state is added. | State is dropped for V1; no extra click is required by this Product Spec. | Pilot workflow evidence and approved state-machine change. | OPEN |
| OD-12 | Decide recollection charging when rejection is patient-caused. | Product/finance + laboratory authority | LAB-009; BIL/PAY | Needed before a policy hook or charge is introduced. | Recollection does not recharge under the safe current handling. | Product/finance/lab decision and charge evidence. | OPEN |
| OD-13 | Decide control-and-report versus hard prohibition for OTC sale of prescription-only medicines. | Pharmacist + product/regulatory authority | DSP-013; PHM-001; TI-06 | Needed before the affected retail policy is frozen. | Current safe handling requires a valid linked prescription; no pharmacist reason/acknowledgement exception is active while OD-PH8 is BLOCKED; this is a Product Spec safety outcome, not a compliance claim. | Pharmacist/regulatory decision and report requirement. | OPEN |
| OD-15 | Confirm injectable batch/lot capture boundary for treatment-room items. | Product + pharmacist/clinical authority | DX-005; INV-005; DSP-015 | Needed before treatment-room stock behavior is claimed. | Free-text external items are documentation only; managed stock requires structured non-expired issue. | Domain-owner decision and affected inventory evidence. | OPEN |
| OD-17 | Decide ANC sensitive-field printing, including HIV status. | Clinical/privacy authority | ANC-003; NFR-07; TI-12 | Needed before sensitive ANC-card print behavior is frozen. | No automatic disclosure; explicit card/facility enablement remains the safe boundary. | Privacy/clinical decision and document examples. | OPEN |
| OD-18 | Decide the validated triage acuity scheme and whether any automated suggestion/pre-selection is permitted. | Contracted clinical advisor + product owner | TRI-002/003/006; QUE-001/008; TI-14 | Blocking for any clinical decision-support behavior; current V1 boundary is safe but remains under validation. | Human-assigned EMERGENCY/URGENT/ROUTINE and neutral flags; no computation or suggestion. | Clinical validation and explicit Product Spec decision. | OPEN / BLOCKED |
| OD-19 | Decide whether an allergy exact-string-match warning is permitted. | Contracted clinical advisor + product owner | TRI-004; RX-002/003; DSP-002; TI-14 | Blocking for any matching, warning, or override behavior. | Banner display only; no automatic matching, warning, or blocking. | Clinical safety review and approved copy/behavior. | OPEN / BLOCKED |
| OD-20 | Decide whether paediatric weight-for-age percentile bands may be displayed. | Contracted clinical advisor | TRI-002/011; TI-14 | Blocking for any percentile or growth-chart claim. | Reference-range display only; no percentile computation. | Clinical validation and source reference. | OPEN / BLOCKED |
| OD-21 | Decide whether nurses may initiate laboratory orders from a configured list. | Product + clinical authority | TRI-007; LAB-002; CAT-007 dependency | Blocking for nurse-order behavior. | V1 ordering remains CLINICIAN/MIDWIFE-only; nurses may route. | Product/clinical permission decision and affected state/gate mapping. | OPEN / BLOCKED |
| OD-22 | Confirm nightly sweep versus never-auto-close handling for stale visits. | Product/operations owner | QUE-016; REC-012/005; OPS-004 dependency; SM-01/02 | Needed before operational stale-visit behavior and pilot readiness are final. | Auto-close only zero-record visits; other stale visits are flagged for human review. | Facility evidence and approved operational rule. | OPEN / BLOCKED |

The current recommendation is context, not approval. A product decision
becomes authoritative only when reflected in an approved or superseding frozen
Product Spec version. An approved change record does not silently override
contradictory frozen product behaviour. An ARCHITECTURE DECISION may fill an
implementation choice left open by the Product Spec itself or resolve a
Product Spec-owned architecture decision; a Blueprint-only Frozen Core HOW
choice follows Blueprint Frozen Core change control. It may never contradict
frozen behaviour. An OPEN Product Decision remains OPEN: an
ARCHITECTURE DECISION may not resolve, narrow, bypass, or moot an OPEN Product
Decision. An
ARCHITECTURE DECISION may not change user-observable, auditor-observable,
contractual, financial, clinical, privacy, permission, state-outcome, or
external-system semantics.
If a choice changes WHAT the user or auditor experiences, classify it through
Product Spec authority, normally as a PRODUCT SCOPE CHANGE unless the
evidence-based CORRECTION rules in Section 26 apply.

If a change record is intentionally effective before document republication,
the temporary mechanism may apply only within the allowed meaning of
CLARIFICATION, CORRECTION, or ARCHITECTURE DECISION, and only when the
existing change-control rules are satisfied, including an effective date,
mandatory expiry date, republish-by date, affected IDs, named approving
authority, and exact temporary conflict resolution. It NEVER applies to
PRODUCT SCOPE CHANGE. A PRODUCT SCOPE CHANGE becomes effective only through
the explicitly approved new or superseding frozen Product Spec version. If
the allowed temporary authority information is not unambiguous, affected
implementation stops.

---

## 25. Out-of-Scope Register (Canonical Detailed Source)

| OOS ID | Capability / behaviour | Classification | Release impact | Revisit condition | Owner |
| --- | --- | --- | --- | --- | --- |
| OOS-01 | Any mechanism that allows expired KlinKlik-managed stock to become usable, issued, dispensed, sold, or used through an override is permanently excluded. Quarantine, disposal/write-off, and safe correction paths are permitted safety outcomes and are not excluded. | OUT OF SCOPE (PERMANENT SAFETY BOUNDARY) | No role, permission, configuration, reason, or temporary authority may make expired stock usable. | Only an authorised change to the underlying safety guarantee through Product Spec change control could alter this permanent boundary; safe non-usable/correction paths remain available. | Product + pharmacist authority |
| OOS-02 | V1.1, Phase 2, Phase 3, and other capability groups explicitly marked for a later release are not current V1 behavior. | DEFERRED | Not part of current V1 implementation or release acceptance. | New/superseding frozen Product Spec selects the capability for a named release and supplies its authority/evidence. | Product owner OPEN |
| OOS-03 | Superseded drafts, conflicting proposals, and rejected ideas do not regain authority or become implementation scope. | REJECTED | No implementation or release work may be based on the superseded material. | Only an approved change-control record can re-charter the idea; a new Product Spec version is required where behavior changes. | Product owner OPEN |
| OOS-04 | Future possibilities requiring later clinical, pharmacy, legal, regulatory, pilot, or product authority are not enabled by this Product Spec. | UNSUPPLIED / BLOCKED | Dependent behavior remains blocked; missing detail is not a deferral or permission. | Supply the authority and, where behavior changes, approve a new/superseding frozen Product Spec. | Product owner + affected domain authority |
| OOS-05 | Controlled/Class A medicine receiving, prescribing, dispensing, sale, and external-prescription completion are unsupported in baseline V1. | OUT OF SCOPE (V1 baseline) | All entry paths remain refused; no role, reason, configuration, or classification action enables them. | A lawful pharmacy/regulatory decision and new/superseding frozen Product Spec with the required trust and compliance gates. | Product + pharmacist/regulatory authority |
| OOS-06 | Expired-stock override or use of expired KlinKlik-managed medicine is not supported; the no-override rule is permanent. Expired stock already on hand may move only through supplied quarantine, disposal/write-off, or other safe non-usable/correction paths. | OUT OF SCOPE (PERMANENT SAFETY BOUNDARY) | Expired medicine cannot become usable, issued, dispensed, sold, or used; quarantine/disposal/write-off and safe correction remain permitted and cannot increase usable availability. | Only an authorised change to the underlying safety guarantee through Product Spec change control could alter this; no temporary authority may do so. | Product + pharmacist authority |
| OOS-07 | Clinical decision support and automatic diagnosis, risk classification, prescribing/dose recommendation, allergy/interaction matching, or laboratory-result interpretation are not V1 behavior. | OUT OF SCOPE (V1 safety boundary) | The product records and presents human-entered information only; no automated interpretation is released. | Clinical validation and approved Product Spec change; trust gate RG-14 remains non-waivable while the guarantee is in force. | Product + clinical authority |
| OOS-08 | Direct Mobile Money, bank, card, SMS, WhatsApp, public webhook, and other external-provider integrations are not authorised by the current V1 Product Spec. | UNSUPPLIED / BLOCKED | Operator-entered references may remain evidence where supplied; no provider effect or contract may be implemented. | Define the outbound effect contract, external authority, and new/superseding frozen Product Spec before activation. | Product + external-effect authority |
| OOS-09 | Offline finalisation of high-impact clinical sign-off, payment, stock receipt/adjustment, dispensing, sale, or other final action is not supported. | OUT OF SCOPE (V1 safety boundary) | A local or queued attempt is pending, failed, or unknown, never a completed product outcome. | A new/superseding Product Spec and trust review would be required; temporary authority cannot enable it. | Product + clinical/pharmacy/finance authority |
| OOS-10 | Journey F and any behavior defined only in the absent source part are not reconstructed or treated as current scope. | UNSUPPLIED / BLOCKED | No J-06 behavior, acceptance criteria, or implementation scope is created from the reference alone. | Supply the missing source and reconcile it through Product Spec change control. | Product owner OPEN |
| OOS-11 | AUTH, TEN, USR, CAT, PAT, APT, REP, AUD, BRN, and OPS detailed epic behavior is not supplied by the current source set. | UNSUPPLIED / BLOCKED | Referenced capabilities remain dependencies/gaps and may block V1; absence does not mean deferred or permitted. | Supply and approve the missing authority/stories, then update affected coverage, gates, and release readiness. | Product owner + affected domain owners |
| OOS-12 | Story-level OOS notes remain traceable in their source story; they are not silently promoted into additional top-level exclusions or used to create new behavior. | OUT OF SCOPE (tracking boundary) | The canonical register remains concise while story-level exclusions continue to bind their stories. | Revisit only when a product decision requires a top-level classification or new Product Spec version. | Product owner |

Section 25 is the one canonical detailed OOS source. “OUT OF SCOPE” here is
release- or safety-boundary specific unless the row expressly states a
permanent exclusion. “DEFERRED” means a named later-release choice;
“REJECTED” means the idea has no current authority; and “UNSUPPLIED /
BLOCKED” means the authority or source is missing and must not be guessed.
Missing specification alone never changes a row to DEFERRED.

This register is the one canonical detailed source and guard against feature
creep. A technically easy addition is still out of scope until its
classification changes through change control.

---

## 26. Change Control

Frozen files must never be silently rewritten. Every material change is
classified and recorded.

### Change classes

| Class | Meaning | May change product behaviour? | Approval expectation |
| --- | --- | --- | --- |
| CLARIFICATION | Wording or presentation made clearer with no behaviour change; may authorise the wording correction under this process. | No | Owner review; update references and tests if needed. |
| CORRECTION | Fixes a contradiction or correctness defect while preserving approved intent and authorises preparation of the corrected frozen revision. | Only to restore approved intent | Named product owner and affected-domain review; conflicting implementation must not proceed until effective authority is unambiguous. |
| ARCHITECTURE DECISION | Defines HOW an approved rule is implemented or fills an implementation choice left open by the Product Spec itself or resolves a Product Spec-owned architecture decision. | No | Architecture authority; it may never contradict frozen product behaviour. |
| PRODUCT SCOPE CHANGE | Adds, removes, or materially changes product behaviour. | Yes | Not effective merely because a change record exists; temporary pre-republication authority is prohibited; requires explicit approval of a new or superseding frozen Product Spec version. |

An ARCHITECTURE DECISION is limited to a genuinely open technical choice owned
by the Product Spec. It
cannot resolve, narrow, bypass, or moot an OPEN Product Decision, and cannot
change user-observable, auditor-observable, contractual, financial, clinical,
privacy, permission, state-outcome, or external-system semantics. A choice
that changes WHAT the experience does belongs in Product Spec authority,
normally as PRODUCT SCOPE CHANGE unless the evidence-based CORRECTION rules
below apply. It may NOT contradict frozen Product Spec behaviour.

A change affecting ONLY existing Blueprint Frozen Core HOW uses the BLUEPRINT
FROZEN CORE CHANGE process. This includes selecting or changing a technical
implementation mechanism, resolving an implementation choice left open by the
Blueprint, changing normative Blueprint architecture or implementation
guidance, or other Frozen Core HOW that does not alter Product Spec meaning. A
Product Spec ARCHITECTURE DECISION is used only when the Product Spec itself
owns the unresolved implementation/architecture decision or authority record,
for example a Product Spec architecture blocker/decision, Product Spec
temporary effective authority, Product Spec-owned open technical decision, or
Product Spec change-control traceability. If it requires a resulting Blueprint
Frozen Core edit, that edit still follows Blueprint Frozen Core change control
and increments the Frozen Core version: the Product Spec CHG records WHY and
governing authority, while the BLUEPRINT-CHG records the resulting HOW, with
cross-referenced IDs. Do not create duplicate competing CHG and BLUEPRINT-CHG
records for a pure-HOW decision, and do not place ordinary Blueprint-only
technical changes in the Product Spec In-Flight Authority Index.

When a CORRECTION changes observable behaviour, the record must include:

- the exact frozen text being corrected;
- the contradiction or correctness defect;
- the prior approved decision, requirement, external authority, or other
  authoritative evidence that establishes the intended behaviour.

Approved intent cannot be established merely by preference, implementation
convenience, existing code, or an agent's interpretation. If that evidence is
absent, the change is not a CORRECTION and must not use that class.

### Authority, freeze, and identifier continuity

After freeze, the Product Spec is Rank 1 internal product authority and the
Frozen Implementation Blueprint is Rank 2 implementation translation. An
external binding obligation remains Rank 0 for the obligation it binds. No
tracker, backlog, code change, review note, or architecture record can create,
remove, or override Product Spec behavior, and no third canonical product
document is created.

Every material change records its affected stories, acceptance criteria,
invariants, contracts, journeys, state machines, blockers, OOS IDs, release
gates, and Blueprint/capability IDs. Stable identifiers are never silently
renumbered or reassigned. A retired identifier receives a cumulative compact
tombstone that records its retirement, supersession or merge, and replacement
reference where one exists; the identifier is never reused for different
meaning. Regression and evidence impact must be reconsidered for every
affected ID before the changed authority is frozen or dependent work
continues.

### Current change-register status

| Record | Status | Scope note |
| --- | --- | --- |
| NONE — no active Product Spec change record | NOT ACTIVE | Q5 populated Sections 22–26 and Q6 completed Sections 27–30; there is no active Product Spec change record, no temporary authority, and no product-scope change. |

### Change record template

This is a future capture form, not an active authority record. A future record
must replace the N/A values with the approved stable ID, evidence, affected
IDs, approvals, and lifecycle fields below before it can be effective.

| Field | Value |
| --- | --- |
| Change ID | N/A — no active record |
| Class | N/A — no active record; a future record must choose CLARIFICATION, CORRECTION, ARCHITECTURE DECISION, or PRODUCT SCOPE CHANGE |
| Rationale | N/A — future record must state why |
| Affected sections / stories / invariants | NONE — future record must identify these |
| Before behaviour | N/A — future record must quote the canonical behavior |
| After behaviour | N/A — future record must state the approved result |
| Validation impact | N/A — future record must identify tests, gates, and reviews |
| Reviewer / owner | OPEN — named owner required for a future record |
| Authority owner | N/A — no active record |
| Scope impact | NONE for this future-form record |
| Effective authority | N/A — no active authority; frozen Product Spec Rank 1 applies |
| Effective date / version | N/A — no active change record; Product Spec v1.0 is frozen |
| Temporary expiry date | N/A — no active temporary authority |
| Republish-by date | N/A — no active temporary authority |
| Expiry-monitor owner | N/A — no active temporary authority |
| Expiry detection / review trigger | N/A — no active temporary authority |
| Temporary approver | N/A — no active temporary authority |
| Affected Product Spec IDs | NONE — future record must identify them |
| Affected Blueprint / capability IDs | NONE |
| Affected Blueprint sections / required Blueprint reconciliation | NONE — record REQUIRED if the Blueprint is affected |
| Blueprint reconciliation status | NOT REQUIRED for this future-form record |
| Runtime expiry disposition | N/A — no active temporary authority |
| Escalation owner / path | N/A — no active temporary authority |
| Temporary conflict resolution | N/A — temporary authority is not active |
| Record status | NOT ACTIVE |

Every approved Product Spec change must explicitly state whether the Blueprint
is affected. If it is affected, identify the relevant Blueprint sections and
capabilities, reconcile the Blueprint before dependent implementation
proceeds, update its Product Spec path/version binding, and reconsider affected
Frozen Core or LIVE EXECUTION STATE evidence as appropriate. If it is not
affected, record **NONE** explicitly. A known Product Spec change must not
require agents to manually diff the entire two-document pair to discover its
declared Blueprint impact.

### Canonical-document concurrency

Both canonical documents must have durable version history. A normative
Product Spec or Frozen Core edit has one explicit edit owner at a time unless
the edits are safely partitioned and reconciliation ownership is explicit.
Never silently overwrite another author's canonical-document changes. Before
publishing a normative revision, reconcile concurrent edits against the
latest authoritative base. Conflicts are explicitly resolved; never use
"last save wins." This rule is provider-neutral and does not require Git or a
specific hosting provider.

### Change effectiveness

Clarifications and corrections still require traceability; a “small” edit
must not hide a product-scope change. A correction prepares the corrected
frozen revision; it is not a silent override of the current frozen Product
Spec. A product-scope change takes effect only with the explicitly approved
new or superseding frozen Product Spec version. An approved change record may
state a temporary effective authority before republication only for
CLARIFICATION, CORRECTION, or ARCHITECTURE DECISION, only within that class's
allowed meaning, and only when its effective authority, effective date,
mandatory expiry date, expiry-monitor owner, expiry detection / review trigger,
republish-by date, affected Product Spec and Blueprint/capability IDs, named
authority owner and approver, runtime expiry disposition, escalation
owner/path, and exact temporary conflict resolution are explicit before the
record becomes ACTIVE. The temporary mechanism NEVER applies to PRODUCT SCOPE
CHANGE. At expiry, the temporary authority lapses automatically; ACTIVE must
no longer be treated as effective merely because a human forgot to edit the
table; the approved runtime expiry disposition is triggered, affected new
implementation remains BLOCKED, escalation occurs, and agents must not guess.
Production is not automatically reverted solely because authority expired;
automatic rollback is not required and may be unsafe. Expired behaviour may
not continue indefinitely as normal authority. If immediate disablement or
containment would cause material harm, a pre-approved bounded containment mode
must name its authority, explicit boundaries, hard end condition/date, and
escalation path; it is not an indefinite extension.

### In-Flight Authority Index

This index is the compact Section 26 record of temporary or not-yet-
incorporated authority. It is part of this Product Spec, not a third
canonical document.

No record may become ACTIVE until its authority owner, expiry-monitor owner,
expiry detection / review trigger, republish-by date, affected Product Spec
IDs, affected Blueprint/capability IDs where known, runtime expiry
disposition, escalation owner/path, approver, and exact conflict resolution
are recorded.

| Change ID | Class | Effective date | Expiry | Republish by | Authority owner | Expiry-monitor owner | Expiry detection / review trigger | Affected Product Spec IDs | Affected Blueprint / capability IDs | Runtime expiry disposition | Escalation owner / path | Approver | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NONE — no active in-flight authority | N/A | N/A | N/A | N/A | N/A | N/A | N/A | NONE | NONE | N/A | N/A | N/A | NONE ACTIVE |

At expiry, an ACTIVE record lapses automatically, the runtime expiry
disposition is triggered, affected new implementation remains BLOCKED, and
the escalation path is used. INCORPORATED, LAPSED, or WITHDRAWN records cannot
authorise new work; an expired record cannot continue as effective because its
status cell was not manually changed.

---

## 27. Implementation Readiness

Readiness is per capability or slice, not a claim that the whole product is
ready. Implementation Readiness in this Product Spec means SPECIFICATION
READINESS AT THE CURRENT FROZEN VERSION, not live implementation-progress
state. Blueprint LIVE EXECUTION STATE tracks implementation progress
separately.

| Capability / slice | Release | Status | Evidence required | Owner | Blocker / decision |
| --- | --- | --- | --- | --- | --- |
| Region-agnostic, non-production preparation with no product behaviour or infrastructure provisioning | V1 | READY | Sections 1, 10–13, 17–18, 26; frozen source release/validation boundary in K:/new/clinicopus2.md §§53–55 and §58 | Engineering lead OPEN | NONE for this bounded preparation; BL-01 / OD-L1–OD-L2 still block infrastructure provisioning and hosting/processor commitments |
| Supplied V1 clinical and operations slices (REC, QUE, TRI, ENC, LAB, DX, RX, PHM, INV, DSP, BIL, PAY, RCP, ANC) | V1 | BLOCKED | Sections 15–21; 194 supplied stories and ACs; TI-01..TI-15 / RG-01..RG-15; applicable authority and pilot evidence | Product and affected domain owners OPEN | BL-06, BL-07, BL-08, BL-09, BL-10; affected OPEN decisions |
| Organisation, facility, and protected access (AUTH, TEN, USR) | V1 | BLOCKED | Sections 1, 8, 9, 19; TI-01/TI-02/TI-12/TI-13; RG-01/RG-02/RG-12/RG-13 | Product + identity/tenancy authority OPEN | BL-03; detailed grant, credential, revocation, and background-operation authority is unsupplied |
| Patient identity and duplicate control (PAT) | V1 | BLOCKED | Sections 14, 16, 19; REC dependencies; TI-01/TI-02/TI-10/TI-13 | Product + patient-domain owner OPEN | BL-04; PAT epic authority and cross-facility sharing rule remain unsupplied |
| Catalogue, classification, and pricing configuration (CAT) | V1 | BLOCKED | Sections 16, 19; PHM/INV dependencies; TI-05/TI-06/TI-07 | Product + pharmacy authority OPEN | BL-04, BL-08; catalogue governance and classification authority remain OPEN |
| Appointments and scheduling (APT; SM-10 fragment) | V1 | MISSING | Section 15 SM-10 fragment; APT dependency references; Section 19 | Product + APT authority OPEN | BL-05; no appointment workflow, slot, reminder, no-show, or permission behaviour is inferred |
| Reporting and management outputs (REP) | V1 | MISSING | Sections 17, 19, 21; supplied report references | Product + reporting authority OPEN | BL-04; REP stories, scope, export, and retention rules remain unsupplied |
| Audit and access evidence (AUD) | V1 | BLOCKED | Sections 10–13, 18–21; TI-12/TI-13; RG-12/RG-13 | Product/security/audit authority OPEN | BL-04; detailed AUD events, access review, retention, and reconstruction authority remain unsupplied |
| Branch and cross-facility operations (BRN) | V1 | MISSING | Sections 1, 8, 9, 19; TI-01/TI-02/TI-09/TI-13 | Product + branch authority OPEN | BL-04; no cross-facility exception is active without explicit authority |
| Operations, notifications, and resilience governance (OPS) | V1 | BLOCKED | Sections 10–13, 17–21; TI-02/TI-09/TI-10/TI-13/TI-15; RG-02/RG-09/RG-10/RG-13/RG-15 | Product + operations authority OPEN | BL-04, BL-09, BL-11; notification effects, recovery objectives, and sweep authority remain OPEN |
| Release and pilot enablement across the named V1 slices | V1 | BLOCKED | Sections 17–21, 28; RG-01..RG-15; K:/new/clinicopus2.md §§53–55 and §58 | Product owner, clinical/pharmacy/legal/pilot approvers OPEN | BL-01, BL-06, BL-08, BL-09; OD-L*, OD-R*, and applicable OD-C/OD-PH decisions |

No product-behaviour row is marked READY: the current FROZEN Product Spec has explicit
authority, validation, dependency, and pilot blockers. The single READY row is
limited to region-agnostic, non-production preparation with no product
behaviour or infrastructure provisioning. This is specification readiness, not
a claim about implementation progress. A product slice may be reconsidered
only after the named blocker/decision is resolved and the affected evidence is
reconciled.
The dispositions trace to Sections 19 and 22–26, the supplied story and state
records in Sections 15–16, and the frozen source release/validation gates in
K:/new/clinicopus2.md §§53–55 and §58.

### Status meanings

- **READY**: specification readiness at the current frozen Product Spec
  version: no OPEN blocker affects the slice; no OPEN Product Decision whose
  Needed before includes it affects the slice; no MUST BE VALIDATED or
  BLOCKS IMPLEMENTATION assumption affects its behaviour; and authority,
  dependencies, acceptance criteria, and required trust coverage are
  sufficient to begin the named implementation slice. READY is not a claim
  about live implementation progress.
- **NEEDS DECISION**: a non-blocking choice is still open; do not implement
  the affected decision-dependent behaviour.
- **BLOCKED**: an unresolved product, architecture, legal, operational, or
  external constraint prevents safe implementation.
- **MISSING**: required specification, acceptance, dependency, or test
  coverage has not been authored.

Do not start implementation for a BLOCKED or MISSING slice. Do not mark a
slice READY merely because a developer can make a plausible guess. If an OPEN
decision affects only a bounded portion, an unaffected slice is READY only
when the decision-dependent behaviour is explicitly excluded; otherwise mark
the slice NEEDS DECISION or BLOCKED. Blueprint LIVE EXECUTION STATE tracks
implementation progress separately.

---

## 28. Specification Self-Review Checklist

Mark each item PASS, FAIL, or NOT APPLICABLE with a note. A frozen document must have no
unexplained FAIL.

- [ ] Contradictions were searched for and resolved or recorded as blockers.
- [ ] Every story has an owner, release, dependencies, and negative paths.
- [ ] Every stateful domain has complete states, transitions, guards, and
  terminal/reversal behaviour.
- [ ] Every interacting state-machine rule is named in Cross-Machine
  Constraints with required consistency/atomicity outcome, product-visible
  recovery, canonical error, and regression mapping; projects with none record
  a reasoned NOT APPLICABLE.
- [ ] Cross-machine Product Spec entries define WHAT must be guaranteed only;
  technical coordination and transaction strategy remain in the Blueprint.
- [ ] Each transition declares an applicable USER, SYSTEM, TIME, or EXTERNAL
  trigger type, with the required clock, actor/job, event-contract,
  retry/idempotency, concurrency, and audit semantics.
- [ ] Permissions are explicit, default-deny, scoped, and state-aware.
- [ ] Failure, retry, stale-write, and concurrent-request behaviour is defined.
- [ ] GSC-10 covers inbound webhooks, callbacks, provider events, imports, and
  async confirmations, including trust, replay, ordering, correlation,
  disagreement, quarantine, audit, and reconciliation.
- [ ] Safe external scope disclosure preserves SCOPE_NOT_FOUND internally and
  does not reveal hidden cross-scope existence.
- [ ] Revocation propagation covers active sessions, tokens, in-flight work,
  queued jobs, links, caches, timing, and regression evidence where applicable.
- [ ] Dependencies and external authorities are visible.
- [ ] External Binding Authority is rank 0 for applicable obligations, the
  Product Spec is the highest INTERNAL authority, and agents do not interpret
  ambiguous law or regulation independently.
- [ ] All normative frozen Product Spec content, including stories and
  acceptance criteria, is Rank 1; neither the story section nor its criteria
  appear as a lower-ranked authority.
- [ ] The External Binding Authority Register indexes source, authorised
  interpreter, affected IDs, status, implementation blocking, review date,
  monitoring owner, and next-review/trigger; it is not a separate legal
  document or AI interpretation.
- [ ] Each External Binding Authority record identifies the exact source,
  citation/version, applicability date, authorised interpretation reference
  and approval date, supersession/review trigger, and affected Product Spec
  IDs; supporting interpretation artifacts are not canonical product
  documents.
- [ ] Section 4 is only a scope-boundary summary and every detailed exclusion
  has one canonical OOS record in Section 25.
- [ ] Product Spec stories and canonical acceptance criteria are authoritative;
  external trackers are planning/progress artifacts only.
- [ ] The two canonical documents remain the only product and implementation
  authorities; no third canonical backlog or document was created.
- [ ] Current implementable release and future context are distinguished;
  superseded behaviour and acceptance criteria cannot appear current beside a
  replacement.
- [ ] Silence in a story inherits every applicable GSC, and any override names
  the exact GSC, narrowed behaviour, authority, residual risk, affected
  invariants, gates, and validation impact.
- [ ] No silent scope expansion or invented capability remains.
- [ ] Acceptance criteria are observable and testable.
- [ ] Acceptance-criteria sub-IDs are stable and every applicable criterion
  has an authority-backed disposition in Blueprint LIVE EXECUTION STATE using
  the canonical per-AC vocabulary; the Product Spec is not a competing live
  status ledger.
- [ ] Published canonical IDs are never reused for a different meaning, and
  retired identifiers have cumulative, permanent compact tombstones with
  replacement or NONE.
- [ ] Unresolved blockers are not disguised as decisions or recommendations.
- [ ] Trust invariants have enforcement and permanent regression gates.
- [ ] Negative, security, privacy, accessibility, and concurrency tests are
  mapped where applicable.
- [ ] Coverage matrix exposes missing product specification.
- [ ] Coverage Matrix directly records a Goal ID or ENABLING INFRASTRUCTURE
  for every capability.
- [ ] GSC-5 states the required stale/concurrent-update outcome without
  prescribing a version, ETag, lock, timestamp, or database mechanism.
- [ ] Change records distinguish clarification, correction, architecture, and
  scope change; correction evidence and architecture boundaries are explicit;
  pure Blueprint Frozen Core HOW uses BLUEPRINT FROZEN CORE CHANGE, while a
  Product Spec ARCHITECTURE DECISION is reserved for Product Spec-owned
  authority and cross-references any resulting Blueprint change;
  every approved Product Spec change declares affected Blueprint sections and
  required reconciliation or records NONE, with reconciliation status tracked
  before dependent implementation proceeds;
  temporary authority has bounded precedence, expiry/index lifecycle fields,
  runtime expiry disposition, escalation, and automatic lapse; and
  product-scope changes require a new or superseding frozen Product Spec.
- [ ] Canonical Product Spec / Blueprint document edits use durable version
  history, explicit edit and reconciliation ownership, and explicit conflict
  resolution rather than silent last-save-wins.
- [ ] ACTIVE temporary authority is limited to affected IDs, exact temporary
  conflict resolution, valid period, and allowed class; it cannot rewrite
  unrelated Product Spec content.
- [ ] Readiness means specification readiness at the current frozen version,
  with OPEN decisions, validation assumptions, and bounded exclusions
  cross-checked.
- [ ] Manual trust gates name a human role, reproducible scenario, negative
  paths, evidence reference, trigger, maximum age, and result; machine-testable
  guarantees marked AUTOMATED WHERE FEASIBLE use disciplined MANUAL REVIEW
  fallback until automation exists, with missing or expired evidence
  NOT SATISFIED.
- [ ] Trust gates have NON-WAIVABLE / WAIVABLE RISK disposition; gates directly
  designated as the proving/enforcement gate for a currently effective frozen
  Trust Invariant or applicable External Binding Authority obligation remain
  NON-WAIVABLE while that guarantee is in force and cannot be reclassified by
  gate-row editing; supplementary tests are not automatically NON-WAIVABLE,
  lower-order waivers are qualified, bounded, compensating, expiring, and
  require re-verification, and an applicable proving gate cannot be
  NOT APPLICABLE.
- [ ] GSC-10 has a canonical outbound-effect contract covering ordering,
  duplicate safety, authority, unknown results, pending/failure outcomes,
  external-success/local-failure, reconciliation, and audit.
- [ ] Template-only notes are explicitly marked and permanent standard rules
  are retained.
- [ ] Material NOT APPLICABLE controls record rationale and reopening
  conditions; N/A shorthand carries the same meaning and stale exclusions are
  reconsidered when domain or scope changes.
- [ ] MATERIAL uses the single canonical definition in Section 30; uncertain
  materiality is treated as material until reviewed.
- [ ] NOT APPLICABLE is the canonical semantic state and N/A shorthand carries
  exactly the same rationale and reopening requirements.
- [ ] Project level and project-level owner/approver are recorded; material
  growth triggers PROJECT-LEVEL REVIEW with KEEP LEVEL 3 / CHANGE LEVEL rather
  than automatic Level-3 promotion.
- [ ] A Level-1 project may group checklist items that only test an entire
  section already marked NOT APPLICABLE with a valid section-level rationale;
  applicable material controls still receive direct review and no blanket
  all-items N/A is allowed.
- [ ] The Blueprint can translate the approved journeys without redefining
  them.

| Review date | Reviewer | Result | Follow-up IDs |
| --- | --- | --- | --- |
| 2026-08-29 | Luna/Codex Q6 authoring self-audit | FAIL — explained open authority and downstream-evidence items remain in this DRAFT | BL-01..BL-11; OD-P*, OD-C*, OD-PH*, OD-L*, OD-R*, OD-T* |

### Q6 checklist dispositions

Each checklist item above is explicitly dispositioned below. PASS means the
Product Spec rule or traceability check is satisfied at this Product Spec revision;
NOT APPLICABLE means the item belongs to a future project level or future
implementation document and is intentionally not claimed here; FAIL identifies
an explained open prerequisite, not permission to guess or implement.

| # | Checklist item (in order above) | Disposition | Note / traceability |
| --- | --- | --- | --- |
| 1 | Contradictions searched and resolved or recorded | PASS | Whole-document reconciliation; unresolved matters remain in BL-01..BL-11 and Section 24. |
| 2 | Story owner, release, dependencies, and negative paths | PASS | 194 supplied stories retain the canonical story-field structure; missing dependencies stay explicit. |
| 3 | Stateful domains have states, transitions, guards, and terminal/reversal behaviour | PASS | SM-01..SM-11 are present; the unsupplied appointment fragment is explicitly marked. |
| 4 | Interacting state-machine rules named with outcomes, recovery, errors, and gates | PASS | CMC-01..CMC-17 and RG mappings are retained. |
| 5 | Cross-machine entries define WHAT; technical coordination remains Blueprint-owned | PASS | Section 15 boundary language is preserved. |
| 6 | Transition trigger, clock, actor/job, retry, concurrency, and audit semantics | PASS | Transition fields are retained or explicitly OPEN where source authority is missing. |
| 7 | Permissions are default-deny, scoped, and state-aware | PASS | Sections 8–9 and applicable story permission fields. |
| 8 | Failure, retry, stale-write, and concurrent-request behaviour | PASS | GSC-5/GSC-6/GSC-7 and state-machine error paths. |
| 9 | GSC-10 inbound coverage | PASS | Inbound trust, replay, ordering, correlation, quarantine, audit, and reconciliation remain defined; unapproved provider effects remain blocked. |
| 10 | Safe external scope disclosure | PASS | SCOPE_NOT_FOUND and hidden-existence protection are explicit. |
| 11 | Revocation propagation | PASS | Sessions, tokens, queued/in-flight work, links, caches, timing, and evidence are covered or remain OPEN by authority record. |
| 12 | Dependencies and external authorities visible | PASS | Sections 8, 19, 22–24, and EBA-00 expose them. |
| 13 | EBA rank 0 / Product Spec highest internal authority / no agent interpretation | PASS | Section 1 and EBA register rules. |
| 14 | All normative frozen Product Spec content is Rank 1 | PASS | Stories and canonical ACs are expressly Rank 1 and never subordinate. |
| 15 | EBA register required index fields | PASS | EBA-00 records missing source, applicability, interpreter, status, blocking, monitoring, and trigger explicitly. |
| 16 | EBA records exact source/citation/interpretation fields | PASS | No source is invented; EBA-00 remains INTERPRETATION REQUIRED. |
| 17 | Section 4 summary and Section 25 canonical OOS detail | PASS | Section 4 reconciles to OOS-01..OOS-12; Section 25 remains canonical. |
| 18 | Product Spec stories/ACs authoritative; trackers planning-only | PASS | Sections 1 and 16 retain the boundary. |
| 19 | Only two canonical documents; no third backlog/document | PASS | No IMPLEMENTATION_BLUEPRINT.md or other canonical artifact was created. |
| 20 | Current release distinguished from future context | PASS | V1 and V1.1/Phase 2/Phase 3 context remain separated. |
| 21 | Story silence inherits applicable GSCs | PASS | Section 16 and Section 10 inheritance rules retained. |
| 22 | No silent scope expansion or invented capability | PASS | Unsupplied epics and Journey F remain blocked/unsupplied. |
| 23 | Acceptance criteria observable and testable | PASS | Canonical ACs remain stable and outcome-based. |
| 24 | Per-AC live dispositions belong in Blueprint LIVE EXECUTION STATE | NOT APPLICABLE | No implementation Blueprint is created in Q6; Product Spec does not claim live status. Populate and reconcile before dependent implementation. |
| 25 | Stable IDs and cumulative tombstones | PASS | Identifier lifecycle and tombstone rules remain in Sections 16 and 26. |
| 26 | Unresolved blockers not disguised as decisions/recommendations | PASS | Sections 22–24 preserve status and owner distinctions. |
| 27 | Trust invariants have enforcement and permanent gates | PASS | TI-01..TI-15 map to RG-01..RG-15; all are NON-WAIVABLE. |
| 28 | Negative, security, privacy, accessibility, and concurrency tests mapped | PASS | Sections 17–21 and 18 gate requirements map the applicable evidence. |
| 29 | Coverage matrix exposes missing specification | PASS | Section 19 marks PARTIAL/MISSING/BLOCKED capabilities and gaps. |
| 30 | Coverage rows record Goal ID or ENABLING INFRASTRUCTURE | PASS | Section 19 rows retain G1–G7 or explicit enabling context. |
| 31 | GSC-5 outcome-only concurrency language | PASS | Stale-write/conflict outcome is specified without a mechanism. |
| 32 | Change classes, boundaries, reconciliation, temporary authority, and scope-change rule | PASS | Section 26 retains the complete change-control rules; PRODUCT SCOPE CHANGE cannot be temporary. |
| 33 | Durable version history and explicit conflict resolution | PASS | Document Control and Section 26 preserve the history/concurrency rule. |
| 34 | ACTIVE temporary authority bounded to affected IDs/text/period/class | PASS | Section 26 lifecycle and automatic lapse rules. |
| 35 | Readiness means specification readiness at the current version | PASS | Section 27 explicitly separates readiness from live implementation state. |
| 36 | Manual trust gate discipline and AUTOMATED WHERE FEASIBLE fallback | PASS | Section 18 requires the named human/manual fallback fields and evidence age. |
| 37 | Non-waivable proving gates and bounded lower-order waivers | PASS | Gate-only reclassification cannot weaken a live Trust Invariant or EBA obligation. |
| 38 | GSC-10 outbound-effect contract | PASS | Ordering, duplicate safety, unknown results, local failure, reconciliation, and audit are defined; activation remains authority-gated. |
| 39 | Template-only notes marked and permanent rules retained | PASS | Template-note convention and permanent-rule language remain explicit. |
| 40 | Material N/A rationale and reopening conditions | PASS | Section 30 vocabulary and applicable rows retain rationale/conditions. |
| 41 | Single canonical MATERIAL definition | PASS | Section 30 definition is retained and referenced. |
| 42 | NOT APPLICABLE / N/A semantic equivalence | PASS | Section 30 defines the single meaning and reopening requirements. |
| 43 | Project level and named project-level owner/approver | PASS | LEVEL 3, Mutambo Bernard as named owner/approver, and KEEP LEVEL 3 approval are recorded 2026-08-30; independent whole-candidate review and final human freeze approval are recorded 2026-08-30; no AI approval is claimed. |
| 44 | Level-1 grouped checklist rule | NOT APPLICABLE | This project is recorded as LEVEL 3; the Level-1 exception does not apply. |
| 45 | Blueprint can translate approved journeys without redefining them | NOT APPLICABLE | The implementation Blueprint is intentionally not created in Q6; verify this downstream before implementation. |

---

## 29. Scaling Model

The same authority model applies at every level; depth changes, not the
meaning of the controls.

### Current project-level record

| Field | Value | Status / evidence |
| --- | --- | --- |
| Assigned project level | LEVEL 3 | Recorded in Document Control; healthcare, financial, multi-tenant, and safety-sensitive scope triggers the Level-3 controls. |
| Project-level owner / approver | Mutambo Bernard | RECORDED — supplied human owner/approver; independent whole-candidate review and final human freeze approval recorded 2026-08-30. |
| Human approval of assigned project level | KEEP LEVEL 3 | APPROVED / RECORDED — Mutambo Bernard, 2026-08-30; rationale: healthcare, sensitive clinical data, financial state, multi-tenancy, pharmacy/medicine safety, stock integrity, audit, concurrency, and safety-sensitive shared mutable state. |
| Latest project-level review | COMPLETE / FROZEN | Independent whole-candidate review and final human freeze approval recorded 2026-08-30; Product Spec v1.0 is formally frozen. |
| Material-growth review rule | PROJECT-LEVEL REVIEW | KEEP LEVEL 3 / CHANGE LEVEL must be decided by the named owner when a material trigger occurs; no automatic promotion is inferred. |

### Project-level governance

Document Control records the assigned project level as **LEVEL 1**, **LEVEL
2**, or **LEVEL 3**, together with a named project-level owner / approver. On
2026-08-30, Mutambo Bernard deliberately approved the assigned level as **KEEP
LEVEL 3**. An implementation agent may not silently choose the level or perform
that approval. Any future material change still requires the named authorised
owner to record **KEEP LEVEL 3** or an authorised **CHANGE LEVEL** with rationale.

A **PROJECT-LEVEL REVIEW** is required when the project materially gains a
risk or complexity trigger such as:

- a second tenant, customer, or scope boundary;
- a materially sensitive-data path;
- money movement;
- a material external integration;
- a public or customer-facing release;
- regulated or binding external authority;
- safety-sensitive behaviour;
- substantial shared mutable or concurrent state; or
- another project-specific material-risk trigger.

A trigger does not automatically mean Level 3. It requires review of whether
the current level remains appropriate. Record **KEEP LEVEL 3** or **CHANGE
LEVEL** with the named owner, date, and authorised rationale. Level 1 remains
proportionate; do not add enterprise ceremony merely because a trigger was
considered.

### LEVEL 1 — SMALL

Examples include a simple marketing site, small internal CRUD tool, or tiny
SaaS. Use only applicable sections. Mark unused sections NOT APPLICABLE with a short
rationale. Keep a compact product definition, goals, non-goals, actors,
permissions, relevant states, journeys, error families, assumptions, open
decisions, change control, readiness, and a small trust regression set.
Do not manufacture enterprise, tenancy, or compliance complexity.

When an entire section is genuinely NOT APPLICABLE at Level 1 (for example, no-UI
visual requirements or static/local deployment), one section-level rationale
is sufficient; do not repeat NOT APPLICABLE rows. Applicable trust, permission, privacy,
and scope controls cannot be skipped.

For any material control involving trust or safety, tenancy or scope,
permissions, privacy, concurrency, external services, audit, accessibility of
core workflows, or release/deployment safety, NOT APPLICABLE must state
why it does not apply and the condition that would make it applicable again.
Reopening conditions include a second tenant, acting role, sensitive-data
path, external integration, customer-facing release, or shared mutable state.
If the domain or scope changes so the rationale is no longer true, reconsider
the control before dependent implementation; do not silently carry stale NOT APPLICABLE decisions.

### LEVEL 2 — STANDARD

Normal commercial SaaS projects should complete most sections, including
personas, governance, scope, conceptual domains, global contracts,
state machines, NFRs, coverage, security/abuse analysis, regression gates,
and implementation readiness. Apply concurrency, audit, and privacy contracts
where shared or sensitive state makes them relevant.

### LEVEL 3 — HIGH-RISK / COMPLEX

Healthcare, financial, large multi-tenant, regulated, and safety-sensitive
systems require explicit trust invariants, Global Story Contracts, state
machines, concurrency rules, audit and sensitive-payload rules,
security/privacy/abuse analysis, permanent regression gates, change control,
and explicit blockers. Require named owners and evidence for legal,
operational, and external dependencies. Do not relax controls because a
prototype appears to work.

---

## 30. Writing and Unknown-Decision Rules

Write in precise, direct, test-oriented language. Prefer stable IDs, tables,
short explanations, and concrete placeholder examples. Avoid corporate
filler, consulting language, motivational prose, unnecessary repetition, and
unbounded lists of invented requirements.

Use placeholders such as [PRODUCT_NAME], [RELEASE], and [OWNER]. Clearly mark
instructions that must be removed when this template is populated.

When required information is missing, classify it as:

- **OPEN**: a decision is required and owned.
- **ASSUMPTION**: a stated premise with a validation class and owner.
- **BLOCKER**: implementation or release cannot safely proceed.
- **NOT APPLICABLE**: considered and intentionally excluded.

Never silently complete a specification using “best practices.” A useful
unknown is safer than an invented requirement.

### N/A vocabulary

**NOT APPLICABLE** is the canonical semantic state. **N/A** may remain as
compact table shorthand, but it means **NOT APPLICABLE** exactly and carries
the same rationale and reopening requirements. The two forms must never
acquire different meanings.

### Canonical materiality definition

**MATERIAL** means a change, condition, dependency, or effect that could
plausibly alter one or more of:

- user-observable behaviour;
- auditor-observable behaviour;
- a Trust Invariant;
- permission or scope outcome;
- privacy/security boundary;
- data integrity;
- state-machine outcome;
- external effect;
- concurrency/idempotency guarantee;
- release/deployment safety.

A purely editorial change with no plausible effect on those areas is not
material. When materiality is genuinely uncertain and cannot be bounded safely,
treat it as material until reviewed. The Blueprint references this canonical
definition and must not invent a second meaning.
