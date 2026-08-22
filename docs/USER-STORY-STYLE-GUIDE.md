# User Story House Standard

**How we write implementation-ready user stories.**

This is our house standard for writing user stories. It was extracted from the writing methodology of our mature, production-grade canonical backlog (a reconciled, 190+ story specification for an operations platform), and it is deliberately **domain-independent**: it can be applied to inventory systems, school systems, NGO field platforms, CRMs, HR systems, finance/admin tools, SaaS products — any product where correctness, auditability, and scope control matter.

It is **not** a generic Agile template guide. The familiar form — *"As a user, I want X, so that Y"* — is, in our standard, merely the **index entry** for a story. The real requirement lives in structured, observable, testable acceptance criteria plus a set of conditional sections (state machines, permissions, concurrency, audit, finalisation, non-goals) that make a story:

- **implementation-ready** — an engineer or coding agent can build it without inventing business behaviour;
- **reviewable** — a reviewer can check the implementation against enumerated criteria;
- **testable** — QA can derive PASS/FAIL directly from the story text;
- **scope-controlled** — non-goals and open decisions stop both humans and AI agents from drifting.

**How to use this document.** Give it, plus a product description, to a writer (human or AI agent) and say: *"Generate the canonical backlog using our house user-story standard."* The result should carry the same clarity, edge-case thinking, and implementation usefulness as the backlog this standard was derived from.

**Status of this document.** Reusable standard. It supersedes ad-hoc story-writing habits on all new projects. It does not change the requirements of any existing product backlog.

---

## 1. Core Principles

These principles were observed throughout the source backlog. They are the reason the style works.

1. **The story sentence is the index, not the requirement.** The one-line user story exists so humans can find and talk about the story. The requirement is the acceptance criteria and the conditional sections beneath it. Never treat the sentence as sufficient.
2. **Specify observable product behaviour, not implementation fantasy.** A story says what the product does, what state results, what the user sees, and what the API returns. It does not narrate internal design — but product-level invariants (e.g. "quantities change only through append-only movement records") *are* requirements and belong in the story.
3. **Numbers, names, and codes beat adjectives.** Concrete values (amounts, thresholds, timeouts, boundaries), named states, named error codes. Words like *properly*, *normally*, *appropriately*, *correctly*, *efficiently* are banned unless the behaviour they stand for is defined in the same story. "Handle errors appropriately" is not a requirement; "`422 PAYER_LOCKED`, payment change blocked" is.
4. **One canonical vocabulary.** Every domain concept has exactly one name (e.g. a request record is `SUBMITTED`, never "logged" or "pending intake" in other places). Synonyms are normalised away at authoring time. Ambiguous vocabulary produces ambiguous software.
5. **Stateful records get explicit state machines.** If a record has status, the story (or the backlog's state-machine appendix, which the story must match exactly) defines every state, every allowed transition, who may trigger it, the guards, and whether it is terminal. The system must never invent a transition the backlog does not define.
6. **Irreversibility is declared and always paired with a correction path.** When an action finalises a record (sign, post, approve, pay, issue, close, publish), the story states what becomes immutable and how corrections happen: amendment, new version, reversal record, compensating entry — never silent edits, never deletion.
7. **Concurrency is a first-class requirement.** Wherever two actors (or two devices, or a double-click) can touch the same record, the story defines who wins, what the loser receives, and what data state results.
8. **Server-side rules are authoritative.** Hiding a button is not authorisation. Every permission, scope, and validation rule is enforced by the server; the UI is convenience only.
9. **Every mutation leaves an audit trail — but sensitive values stay out of generic payloads.** Audit events record who, what, when, why, and references. Raw sensitive content lives in the versioned domain record, not in logs, error telemetry, or audit JSON.
10. **Failures are first-class citizens.** Important failure cases (duplicates, stale versions, invalid state, denied permission, wrong tenant, missing prerequisites) are enumerated in the story with named error codes and a defined user next step. No dead ends: every path a record can take ends in either a resolvable next step owned by a named role, or a declared terminal state.
11. **Explicit non-goals.** Every story states what it does *not* include. This is the primary defence against scope creep and against AI agents inventing adjacent functionality.
12. **Hoist defaults into a global contract — defaults, not laws.** Rules that apply to every story (tenancy, audit, idempotency, concurrency, validation, UI states, test obligations) are written once in a Global Story Contract and are implicitly part of each story's acceptance criteria. Stories stay compact; defaults are never repeated per story and should not be casually contradicted. However, a story **may explicitly override** a contract default where the product requires different behaviour: the override must be deliberate, visible, and unambiguous — worded as an explicit exception, not left as a bare contradiction — and **the narrower story rule wins for that story's case**. Reviewers treat *unexplained* contradiction as a specification defect; explicit override is not the same thing as accidental inconsistency.
13. **Priority is not sequence.** P0/P1/P2 express importance. Sequencing comes from dependencies and delivery waves. A P1 story can be a hard prerequisite for a P0-dominated slice; a P0 can be deferred from the first pilot with a stated reason.
14. **Open decisions remain open.** Where a product decision is unresolved (especially anything safety-, legal-, or finance-related), it is recorded in an open-decision register with a *safe temporary assumption* — it is never silently settled by an implementer.
15. **Each story is independently testable.** Acceptance criteria tell QA exactly what PASS means, at the service, API, permission, isolation, and UI levels.

---

## 2. Story Identification Standard

**Epic code.** Two to four uppercase letters naming a stable business capability: `ORD`, `STK`, `PAY`, `ENR`, `ADM`. The epic catalogue is defined once at backlog level (§16).

**Story ID.** `EPIC-NNN` with zero-padded three-digit sequence: `STK-002`, `ENR-014`, `PAY-011`.

**Header line format** (always the first line of a story):

```
STK-011 · Adjust stock quantity with reason and approval · P0 · `STORE_OFFICER`; approval `SITE_ADMIN`
```

**ID stability rules:**

- IDs are permanent. Story wording may change; the ID may not.
- IDs are never reused for different content, and never renumbered casually — other stories, matrices, and test plans reference them. If a renumber is unavoidable, every reference is remapped and the remap is logged in the backlog's change log.
- Never let two different stories share an ID (this sounds obvious; duplicated numbering is a classic multi-draft failure and is expensive to reconcile later).
- A story split produces *new* IDs, with the parent ID retired in the change log.

**Where IDs must be referenced:** implementation prompts and slices, commits and PR descriptions, code review, bug reports, test plans and test names, release notes. Tests trace back to the story ID; a bug that maps to no story maps to a missing story.

**Title.** A short verb phrase ("Adjust stock quantity with reason and approval"), recognisable at a glance, stable enough that humans can pair it with the ID from memory.

---

## 3. Priority Standard

Three priorities, used consistently:

| Priority | Meaning |
| --- | --- |
| **P0** | A release-blocking core business capability, integrity/safety rule, or operational invariant without which the target release cannot reliably perform its intended core job. Safety, legal, financial, and data-integrity risks are common reasons for P0 — but not the only ones. In our source backlog roughly two-thirds of V1 stories were P0 — a safety-critical or money-handling product is *mostly* P0, and that is normal. |
| **P1** | Operationally important, but a usable manual workaround exists; deferring it past the first release does not break the core loop or create uncorrectable records. |
| **P2** | Genuine later improvements: convenience, polish, breadth. Dropping a P2 entirely should still leave a working product. |

Rules:

- Priority is assigned per story at authoring time and shown in the header.
- **Priority ≠ implementation order.** Sequencing comes from `Dep` (dependencies) and from delivery waves (vertical slices of existing stories). A P1 can be a hard prerequisite (in the source backlog, a P1 "stock locations" story was a hard prerequisite for the P0 stock core). A P0 may be deferred from the first pilot only with an explicit, recorded reason.
- Priorities are summed per epic in a priority summary table so the shape of the backlog is visible at a glance.
- Priority disagreement between draft versions is a **product reconciliation decision**, never an automatic rule: do not auto-promote P1 → P0. Preserve both candidate priorities during reconciliation if necessary, resolve the discrepancy explicitly using business impact, release necessity, risk, dependencies, and stakeholder/product-owner intent — and record the resolved priority in the reconciliation/change log whenever the disagreement was material.

---

## 4. Actor Standard

**Never "the user."** Actors are specific operational roles that exist in the customer's organisation.

Bad:

> As a user, I want to manage inventory.

Better:

> As a **store officer**, I want to …
> As a **finance officer**, I want to …
> As a **programme administrator**, I want to …
> As a **field officer**, I want to …
> As a **registrar**, I want to …

**Canonical role table.** At backlog level, define every role once: a technical role ID and a one-line meaning (e.g. `SUPERVISOR` — senior on-site role: overrides, approvals, takeovers). Human-facing prose may use friendlier aliases ("doctor", "front desk"), but permission definitions and story headers use exactly the canonical IDs. Aliases found in source material are normalised to canonical IDs.

**Include the automated actor.** If the platform itself performs behaviour (derived statuses, scheduled sweeps, gate releases, event fan-out), it is an actor too — canonically `SYSTEM` — and its actions are attributed and audited as such.

**Role headers.** Each story names a **primary role** and, where applicable, **secondary roles**: `P0 · REGISTRAR; secondary ADMISSIONS_OFFICER, SUPERVISOR`.

**When to split by role.** Two roles get separate stories when their *behaviour, permission, or audit profile differs* — e.g. "escalate priority" vs "de-escalate priority" (even if the same screen). Roles that share identical behaviour appear together in one story's header. If you find yourself writing "as a nurse-admin hybrid…", you have two stories.

---

## 5. User Story Statement

Structure:

```
**Story** As a [specific actor],
I want [specific capability],
so that [business/user outcome].
**Value** [why this story earns its place — the failure mode it prevents or the gain it creates; quantify when possible.]
```

Rules:

- The capability is specific and bounded: "record who received the goods and generate the dispatch note", not "manage goods".
- The outcome is a business outcome, not a feature restatement: "so the day's cash reconciles" (good), "so the payment screen is populated" (bad).
- The **Value** line justifies the story's existence. The strongest value lines name the real-world failure without the story ("duplicate records inflate statutory reporting, split the history across two records, and create two invoices for one episode").
- Short-form stories (§18) may omit the sentence, but never the meaning.
- **The sentence alone is NOT the full requirement.** It is the handle. The acceptance criteria are the contract. A story consisting of only the sentence is incomplete by definition.

---

## 6. Acceptance Criteria Standard

This is the heart of the standard. Acceptance criteria are what QA tests, what reviewers diff against, and what coding agents implement to.

### 6.1 Format

Use compact **GIVEN / WHEN / THEN** clauses, several per story, each independently testable:

```
**AC** GIVEN an open request for supplier "Northside" WHEN a second identical open request exists
THEN 409 REQUEST_ALREADY_OPEN with the existing request_id and no second record is created.
GIVEN an adjustment above the configured value threshold WHEN posted
THEN it remains PENDING_APPROVAL until a SITE_ADMIN approves it, and the ledger entry is written only on approval.
```

### 6.2 What each criterion specifies

As relevant to the story, a criterion states:

- **Trigger / precondition** (GIVEN): the concrete starting state, with real values.
- **Actor and permission**: who acts, and what a non-permitted actor receives (403-equivalent + no partial data).
- **Behaviour** (WHEN): the action.
- **Resulting state** (THEN): named record states, persisted fields, timestamps, who is recorded as actor.
- **API-visible result**: status codes and **named error codes** in `SCREAMING_SNAKE_CASE` (`PAYER_LOCKED`, `GRACE_WINDOW_EXPIRED`, `INSUFFICIENT_STOCK`).
- **Timing budget**: where freshness matters ("appears within 15 seconds", "within one refresh cycle").
- **Audit event**: which named event is written, with which key fields.
- **Payload shape**: what is included — and what is excluded (negative-content criteria such as "the list payload contains no salary data for a non-finance role" are valid, valuable, and contract-testable).

### 6.3 Concreteness

Use real numbers and boundary values. "A quantity of −5 is rejected with `NEGATIVE_QUANTITY`", "created 14 minutes ago succeeds; 16 minutes fails with `GRACE_WINDOW_EXPIRED`", "3 routine and 1 urgent entry: the urgent sorts first regardless of arrival time". Test matrices belong in the story when the outcome depends on a combination of states ("matrix of prior-record states × payment states").

### 6.4 How many criteria

- Simple stories: 1–3 criteria.
- Feature stories: typically 4–10, covering **the happy path, each important error path, permission denial, scope/tenant isolation, concurrency where relevant, and audit**.
- If a criterion merely restates the story sentence, delete it and write a real one.

**BAD:**

> AC: The system validates the adjustment correctly.

**GOOD:**

> GIVEN a counted quantity of −40 for a batch with 12 on hand WHEN the adjustment is submitted THEN the API returns 422 `NEGATIVE_BALANCE_FORBIDDEN`, no ledger entry is created, and the balance remains 12.

**BAD:**

> AC: Users cannot submit the form twice.

**GOOD:**

> GIVEN the same submission sent twice with one idempotency key THEN exactly one record exists and the replay returns the original result. GIVEN two different users confirm the same pending action concurrently THEN exactly one commits; the other receives 409 naming the committed actor.

### 6.5 Forbidden-behaviour criteria

Where an AI agent or an eager implementer might invent behaviour (auto-suggestions, automatic checks, silent normalisation), add criteria that **prohibit** it: "no automatic matching occurs and the UI must not imply that it does". Prohibitions are requirements, testable by UI-copy review and API payload inspection.

---

## 7. Workflow and State Transitions

When a record has a status, "how it moves" is a requirement, not an implementation detail. Undocumented transitions are where products rot.

### 7.1 Inline transition syntax (inside a story)

```
**State / Workflow**
DRAFT → SUBMITTED → SCREENING → APPROVED → ENROLLED
                       │                        (terminal)
                       └→ REJECTED (terminal, reason retained)
WITHDRAWN reachable from SUBMITTED..SCREENING (requester only, reason mandatory)
REOPEN: not defined in V1 — a rejected application requires a new submission linked to the original.
```

### 7.2 Full state-machine table (backlog appendix)

For every stateful record, the backlog carries an authoritative machine that stories must match exactly:

| State | Meaning | Allowed from | Allowed to | Who may trigger | Guards | Terminal? |
| --- | --- | --- | --- | --- | --- | --- |

Plus **invariants**: cross-record rules the machine must preserve (e.g. "at most one active request per client per branch"; "at most one `IN_SERVICE` task per worker globally at any instant"; "entries are never hard-deleted").

### 7.3 What must always be defined

- **Terminal states** — explicitly marked; nothing leaves a terminal state except via a defined *correction record* (§12), never by mutation.
- **Forbidden transitions** — stated outright: "`CANCELLED → FULFILLED` is forbidden", "`COLLECTED` never moves backward on a payment reversal — delivered work stands; only the financial state is restored."
- **Re-open rules** — if reopening exists: who, with what reason, what is preserved. If it does not exist, *say so*: "reopening is not defined in V1 and must not be implemented."
- **Cancellation** — who may cancel, from which states, mandatory reason vocabulary, consequences for related records and money.
- **Reversal / correction** — the compensating path (§12).
- **Expiration** — scheduled sweeps: what they may auto-expire, what they must only *flag* for human review, idempotency of the sweep, timezone correctness.
- **Resumption / hold** — for records that wait on an external dependency (results, payments, approvals): the hold state, the reference to the blocking dependency, that held records **never disappear from worklists**, auto-resolve conditions ("only when ALL blocking dependencies are terminal — never a subset"), and manual early-resume rules.
- **Guards** — mandatory data, mandatory reasons, threshold checks, audit actor + reason wherever a guard says "reason".

### 7.4 Derived vs stored status

Prefer per-item machines over aggregates; aggregate status is **derived** with explicit derivation rules ("all items terminal and ≥1 completed → `COMPLETED`; at least one completed and one non-terminal → `PARTIALLY_COMPLETED`; never display an aggregate that hides per-item states"). Say whether the derived value may be cached — updated in the same transaction.

---

## 8. Error and Edge Case Standard

Important failure cases belong **in the story** (an `Err` section plus matching acceptance criteria) — not in the developer's judgment on delivery day.

The standard failure checklist — walk it for every story and include everything that applies:

- Missing mandatory information (named field, named error code).
- **Duplicates** — same record created twice; double-submit; retry after network failure. Define the guard (unique constraint, idempotency) and the client-visible result.
- **Stale versions** — two actors editing the same record (§10).
- Resource unavailable — out of stock, no price configured, capacity full, prerequisite record missing.
- **Already-completed action** — acting on a terminal record (409 with current state).
- Cancelled / closed record — what still works (read, print, amendment) and what never does.
- **Permission denied** — 403-equivalent, no partial data, no record IDs leaked in the error body.
- **Wrong organisation / branch** — where revealing record existence is itself sensitive, cross-scope access should fail closed as *not found* (never *forbidden*, which leaks existence), unless an explicit authorised sharing capability exists; if the domain deliberately exposes existence while denying access, the backlog may explicitly define that alternative — cross-tenant access must still never leak unauthorised record data.
- **Invalid state** — the action is legal somewhere in the lifecycle but not from this state; name the state and the correct path.
- **Simultaneous changes** — who wins (§10).
- Boundary values — age thresholds, window expiry at 14:59 vs 15:01, quantity limits, text lengths (never silently truncate).
- Abandonment — the human-left-the-desk case; require a human decision where safety matters ("never auto-cancel automatically; a human must decide").
- Partial failure / atomicity — multi-write operations are all-or-nothing; state what rolls back ("an injected failure on the second write leaves no orphaned first write").

For each: the **named error code**, the **client-visible behaviour**, what happens to the data (nothing partial, nothing silently corrected), and the **user's next step**. Conflict panels are informative, not dead ends — every branch has a button or a named path; never a bare error toast.

---

## 9. Permission and Scope Standard

### 9.1 Named capabilities

Permissions are named capabilities in `resource.verb` form — `request.create`, `enrolment.decide`, `payment.reverse` — never free prose. Each story's `Perm` field names the capability and the roles that hold it; the backlog carries a consolidated role × capability matrix compiled from the stories.

### 9.2 Granularity and asymmetry

- Distinguish **read / create / update / approve / reverse / override** as separate capabilities. "Edit" is not one permission when approve and reverse exist.
- Asymmetries are explicit: "operators may escalate a priority; only supervisors and managers may de-escalate".
- Approval thresholds: value- or risk-based thresholds route an action to an approver role; approval is a *state* (`PENDING_APPROVAL`), not an afterthought.
- Segregation of duties: state forbidden or permitted-but-reported combinations ("recording and reversing payments in the same role is permitted for small teams but listed on the duties report").
- Override powers (gate overrides, force-close) always require a **mandatory reason** and are audited as high-value events.

### 9.3 Scope: tenant, branch, ownership

- Every tenant-owned record carries organisation (tenant) context; often a branch/site dimension as well. All queries are scope-filtered by session context, enforced at the data layer — not only in application code.
- Where revealing record existence is itself sensitive — the default for multi-tenant products — **cross-scope access fails closed as not-found**, so existence is not leaked. A domain that deliberately exposes existence while denying access may define that alternative behaviour explicitly in the backlog; whatever the choice, cross-tenant access is always denied and must never leak unauthorised record data. Same-organisation cross-branch sharing exists only as an explicitly authorised, audited, dedicated capability.
- **Record ownership:** where records have explicit author ownership (typical for professional records), the backlog defines who may edit, whether collaboration is allowed, whether takeover exists, how original authorship is preserved, and the takeover reason/audit rules — with dual attribution on any output. Author-ownership with takeover is a strong pattern, not a mandate for every application.
- Field-level payload filtering is server-side (a role either receives a field or the API never returns it — CSS-hiding is not access control).

### 9.4 Frontend is UX, server is law

Every story states permission behaviour server-side. Hiding a control in the UI is a convenience; the API rejects regardless. Both layers are tested.

---

## 10. Concurrency Standard

Concurrency is a major feature of our house style. Stories do not hope for the best; they name the collision and the winner.

### 10.1 When concurrency criteria are REQUIRED

- The same record edited on **two devices / two sessions**.
- Two users **claiming the same task, ticket, or work item**.
- **Counters and quantities** — two workers issuing from the same balance, the last unit sold twice.
- **Approvals** — two approvers acting simultaneously.
- **Payments / financial allocation** — two cashiers recording against the same outstanding balance.
- **Queue / worklist operations** — N callers pressing "take next" at once.
- Any **state transition with a single legal winner** (sign, post, finalise, close).
- **Sequential numbering** — two documents generated at the same instant must not share a number.

### 10.2 Specify the product behaviour, not the mechanism

The story defines **outcomes**; the architecture may implement them via ETag/If-Match, version numbers, row locks, optimistic checks, or unique constraints — the story does not mandate a specific one (unless the product contract explicitly does). Required outcome vocabulary:

- **Exactly one wins**; the loser receives a defined result, not an error wall — typically 409/412-equivalent with a **named code** (`ENTRY_LOCKED`, `BALANCE_CHANGED`) naming the winner or the current state.
- **Stale updates are rejected** with the server's **current version** returned, so the client can reconcile ("both versions shown to the user to reconcile — content is never silently overwritten").
- **Newer state is preserved**; no silent overwrite, ever.
- **No duplicate processing** — idempotent replay returns the original result (creations with financial or legal consequences accept an idempotency key; replay returns the original response).
- **No partial effects** — the losing or failing operation leaves zero writes ("fails atomically; no partial deduction occurs").
- Race outcomes are **named**: "a race between cancellation and fulfilment: whichever commits first wins; the other fails with 409".

### 10.3 Example

> **Concurrency** GIVEN the same request open in two sessions WHEN both save edits THEN the first save succeeds and the second is rejected (412 `VERSION_CONFLICT`) with the current version and a field-level diff; neither device's content is silently lost. GIVEN five workers pressing "Take next" on a queue with three items WHEN the requests arrive within one second THEN each worker receives a distinct item or an explicit empty result; no item is assigned twice. GIVEN a worker and a supervisor cancelling and confirming the same action simultaneously THEN whichever commits first stands and the other receives 409 naming the committed actor.

---

## 11. Audit and History Standard

### 11.1 When audit expectations are stated

- Every **mutation** (create, update, state transition) — by role, including `SYSTEM`.
- **Sensitive-record reads** — where viewing the record itself is security-, privacy-, regulatory-, or business-sensitive, the backlog explicitly defines read-access audit requirements (typically one access-audit event per record view, not per screen section). Per-read auditing is conditional, not universal.
- Every **privileged action**: override, force-close, takeover, approval, reversal, discount/waiver, configuration change.
- Every **print / export** of sensitive documents, with copy numbers.

### 11.2 What an audit event records

`actor (user id + role), organisation/branch scope, entity type + id (+ version reference), action name (a named constant — `REQUEST_APPROVED`, `PAYMENT_REVERSED`), changed field names, reason (wherever the guard demands one), timestamp, request context (ip, agent, correlation id).`

Events are **immutable and append-only**. Corrections never rewrite history.

### 11.3 Sensitive values stay out of generic payloads

The generic audit event carries **references, field names, and content hashes — never raw sensitive values, personal-case text, or content dumps**. Reconstruction uses the immutable, versioned domain record itself. The same rule applies to application logs, error telemetry, and crash reports. Stories that touch sensitive data carry explicit criteria asserting this ("the audit event references the record version and hash; the payload contains no values").

### 11.4 Version history

Amendments store before/after with author and reason; the original is always retrievable; amended fields display an "amended" marker; printed documents show current values with amendment footnotes. High-value events (signatures, financial postings, reversals, mergers) are flagged and may carry content hashes for tamper evidence.

---

## 12. Finalisation and Immutability Standard

Any record that can become **signed, posted, approved, issued, paid, completed, closed, or published** must declare its finalisation rules explicitly. Never leave this implicit.

For each finalising action, the story states:

1. **Which action finalises** and the confirmation UX (explicit confirmation summarising what becomes immutable — a checklist, not a wall of text).
2. **What becomes immutable** — typically: the whole record; edits via the API are refused with a named error (`RECORD_SIGNED`) regardless of role.
3. **Which correction mechanisms exist**, if any:
   - **Amendment / addendum** — an attributed correction appended to the original, which remains byte-identical; version increments; hash still validates.
   - **New version** — correction supersedes, both versions retained and visible.
   - **Reversal record** — compensating entry referencing the original; the original is never edited.
   - **Cancellation** — pre-final only, or with escalated approval post-final.
4. **What is never allowed**: hard deletion, number reuse, retroactive rewriting, reopening (unless reopening is explicitly defined).
5. **Post-finalisation downstream behaviour** — what may still *append* (e.g. a late result attaching as an addendum; an audit flag) and the guarantee that appending never reopens or mutates the finalised record.
6. **Sequential numbers** assigned at finalisation are unique, never reused, and retired (not recycled) if voided — with concurrency-safe generation.

Pattern summary: **original + attributed correction; compensating entries for ledgers; addenda for documents; reversal records for payments. The original always remains.**

---

## 13. External Side Effects

For every story that triggers an external effect — email, SMS, payment gateway, webhook, third-party API, file export, printing:

- **When it fires** (which commit, with what expected latency).
- **What happens if it fails** — retry policy, backoff, who is notified.
- **Duplicate prevention / idempotency** — the same trigger twice sends/charges once.
- **Whether failure blocks the main action.** Notifications usually must not block the business operation (queued and reported); payment-gated operations usually must block. State which.
- **What the user sees** in each case — including on the receiving end.
- **Honesty about verification.** If a reference number is operator-entered evidence (e.g. a manual money-transfer reference), the system must never claim it verified the transaction with the provider — and the UI copy must not imply it.

For lean MVPs: prefer manual/evidence-based integration over live APIs, and say so explicitly in non-goals plus an open-decision entry for the future integration. A deferred integration is a *documented decision*, not an omission.

---

## 14. Explicit Non-Goals

Every story carries an `OOS` (out of scope) section. It is **REQUIRED** wherever scope could plausibly expand, and recommended everywhere.

```
**OOS** Automatic reordering, supplier invoices/payables, barcode scanning, multi-currency pricing.
```

Rules:

- Non-goals are the primary scope-creep defence for humans and the primary invention-defence for AI agents.
- Safety-adjacent prohibitions get their own acceptance criteria and UI-copy rules: "no automatic checking is performed and the UI must not imply that it does".
- Product-level non-goals ("no offline completion of money or stock operations") live once in the Global Story Contract and are referenced, not restated.
- Non-goals are honest boundaries, not wishes: items deferred to a future phase may reference an open decision or a P2 story; items permanently rejected say so.

---

## 15. Story Splitting Rules

**One story = one testable unit of behaviour** that a reviewer can verify and a release can carry independently.

**Split when:**

- Different **roles** have different permissions or audit profiles for the same area (escalate vs de-escalate; create vs approve).
- Different **states or transitions** of a lifecycle need separate ownership (create / resume / finalise / amend are separate stories for long-lived records — encouraged).
- An **error/edge cluster** is large enough to have its own matrix (duplicate prevention, reversal handling).
- The story spans **two epics** (it is two stories).
- The acceptance criteria exceed roughly a dozen, or the flow section needs more than ~4 alternates with distinct outcomes.

**Do NOT split when:**

- It would produce a story per **field or screen control**. Simple field captures coalesce into one story ("record applicant contact details") and may use the short form (§18).
- The "split" is really **layers** (a "backend story" and a "frontend story" for one behaviour is one story — vertical slices only).
- The alternate path is minor: genuinely small branches stay as `Alt` entries inside the parent story. Promote an alternate to its own story only when it has its own permission, state, or audit profile.

**Priority at split time.** Each child gets its own priority; never smuggle a second feature in through an "and also" clause.

---

## 16. Epic Design

Epics represent **stable business capabilities**, never screens, layers, or phases.

- Named by a 2–4 letter code plus a capability name: `CLI — Client Records`, `ORD — Orders`, `STK — Inventory & Stock`, `PAY — Payments`, `REP — Reporting`, `ADM — Administration`.
- Each epic opens with a short **purpose preamble** — one paragraph stating what the epic is for and its core idea ("an order is the customer's intent; every handoff between departments is an explicit, auditable transition; no order silently disappears between stages").
- Epic boundaries follow the domain's capability map and ownership; avoid grab-bag epics ("Misc", "Setup & Tools") — admin/setup concerns get their own properly scoped epic.
- Dependencies between epics flow one way where possible; stories declare cross-epic `Dep` references freely (and undefined-but-referenced IDs are catalogued, never invented — §22).
- **Do not copy another product's epic architecture into a new domain.** Derive the epic set from *that* domain's capability map. The examples above are illustrative codes, not a template.
- The epic catalogue table (epic, name, story counts, P0/P1/P2) appears once at backlog level.

---

## 17. Canonical Story Template (full form)

Copy this for any story with workflow, permissions, state, or money involved. Field status: **[R] = REQUIRED**, **[C] = CONDITIONAL** (include when it applies; the Global Story Contract supplies defaults otherwise), **[R\*] = required wherever the situation exists** (e.g. concurrency criteria are required exactly when a collision is possible).

Use compact inline formatting (bold labels, not sub-headings) — density is a feature.

```markdown
### [EPIC]-[NNN] · [Short title] · [P0|P1|P2] · `[PRIMARY_ROLE]`; secondary `[ROLES]`  [R]

**Story** [R]
As a [specific actor], I want [specific capability], so that [business outcome].
**Value** [why it exists; the failure it prevents; quantify when possible]

**Pre** [C — workflow stories]
[Preconditions: records that must exist, states, configuration, permissions]

**Trig** [C — workflow stories]
[What starts it: a user action, an event, a schedule]

**Flow** [C — workflow stories]
[The main path, concretely: what the user does, what the system creates/changes,
named states, what downstream records appear, all in one transaction where atomicity matters]

**Alt** [C]
(a) [alternate path and its outcome]
(b) [alternate path and its outcome]
[Every branch ends in a defined outcome — no dead ends]

**AC** [R]
GIVEN [concrete state with real values] WHEN [action] THEN [observable result:
named states, persisted fields, status + error codes, timing, audit event].
[Cover: happy path, each important error, permissions, scope isolation,
concurrency (R* when collisions possible), audit, negative-content payload rules,
and explicit prohibitions where invention is likely]

**Perm** [C — required when the story grants or refines permissions]
[Named capabilities + roles; approval thresholds; override powers + mandatory reason]

**Data** [C — recommended]
[Records and key fields written/read; derived fields and their rule]

**Audit** [C — required when the story adds named audit events]
[Named events + key fields; high-value flags; no sensitive values in payloads]

**Err** [C — strongly recommended]
[Named error codes with causes; edge cases; atomicity on partial failure;
boundary values; what the user does next]

**UI** [C — required for new screens/workflows]
[Layout intent, save-state indicators, empty/loading/error states, accessibility
notes (never colour alone), and where sensitive personal data may not persist]

**Dep** [R when the story references or needs other stories]
[Story IDs. Externally-defined IDs are marked explicitly, e.g.
`REP-003 [external reference — definition not present in this backlog]`;
if the external source has no stable ID, use a descriptive external-dependency entry —
never fabricate a story ID merely to satisfy the dependency]

**OOS** [R* — required wherever scope could expand; recommended everywhere]
[What this story deliberately does NOT include]

**Test** [R]

Standard tests (as relevant to this story):
[service-level · API contract incl. error codes · permission and scope-isolation ·
concurrency races · state-transition legality · audit assertions · UI happy + negative
paths · boundary/matrix cases]

Mandatory release regression tests (only for high-risk / high-value behaviours):
[explicitly named scenarios that must permanently remain in the release regression
suite — most stories have none]
```

**Provenance note for reviewers:** the field set is deliberately the full house set (story, value, preconditions, trigger, flow, alternates, acceptance criteria, permissions, data, audit, errors, UI, dependencies, non-goals, tests). Trimming fields is allowed per the status marks; *weakening* acceptance criteria is not.

---

## 18. Short-Form Template

Not every requirement deserves a full specification. For genuinely simple stories — a single field capture, a small read-only view, a minor configuration, a display rule — use the short form. **Judgement rule:** if the story involves state transitions, money, permissions beyond default, concurrency, or finalisation, it does not qualify for short form.

```markdown
### [EPIC]-[NNN] · [Short title] · [P0|P1|P2] · `[ROLE]`

**AC** GIVEN [state] WHEN [action] THEN [observable result with codes/states].
GIVEN [second case if needed] THEN ...

**Data** [if non-obvious] · **Dep** [if referenced] · **OOS** [if scope could creep] · **Test** [required]
```

When the short form is appropriate:

- single-field / few-field capture with simple validation;
- read-only display or formatting rules;
- small defaults and configuration toggles;
- minor list-view behaviour (filter, badge, sort rule).

If review reveals the "simple" story secretly has alternate flows or permission branches, promote it to the full form — that discovery is the checklist working.

---

## 19. Story Quality Checklist

Reviewer checklist — tick every line before a story enters the canonical backlog:

- [ ] Story ID unique, correctly prefixed, priority assigned; header lists primary (and secondary) roles.
- [ ] Actor is a specific canonical role — no "user", no "admin" without saying which.
- [ ] Story sentence states a bounded capability; **Value** explains the failure mode or gain it addresses.
- [ ] Acceptance criteria are observable and independently testable; each has a trigger, behaviour, and verifiable result.
- [ ] Criteria use concrete values and boundary cases — no "correctly/properly/appropriately" left undefined.
- [ ] Error paths enumerated with **named codes** and user next steps; no dead ends.
- [ ] Permissions defined (named capabilities, roles, thresholds, overrides-with-reason); asymmetries explicit.
- [ ] Scope/tenancy behaviour defined; where revealing record existence is sensitive, cross-scope access fails closed as not-found unless the backlog explicitly defines another safe behaviour — and unauthorised cross-tenant record data must never leak.
- [ ] State transitions defined if the record is stateful — states, allowed/forbidden transitions, guards, terminal flags; matches the state-machine appendix exactly.
- [ ] Invariants stated (uniqueness, at-most-one, never-disappear rules).
- [ ] Finalisation/immutability rules defined for anything that can be signed/posted/approved/paid/closed; correction paths named; deletion and reopening addressed.
- [ ] Concurrency considered — collisions identified, winner defined, stale-update behaviour defined (or explicitly not applicable).
- [ ] Idempotency defined for creations with legal/financial consequence.
- [ ] Audit events named where required; sensitive values excluded from generic payloads; read-access auditing defined where viewing the record itself is security-, privacy-, regulatory-, or business-sensitive.
- [ ] External side effects (email/SMS/print/export/webhook) specify timing, failure, idempotency, and blocking behaviour — or are non-goals.
- [ ] Non-goals defined wherever scope could expand; prohibitions explicit where invention is likely.
- [ ] Dependencies listed; referenced-but-undefined IDs flagged, never invented.
- [ ] No accidental contradictions between criteria; any Global Contract default is overridden only by a deliberate, visible story-level exception — which wins for that story's case.
- [ ] Tests specified at every level (service, API/permissions, isolation, concurrency, state legality, audit, UI happy/negative); mandatory release regression tests explicitly named where a high-risk/high-value behaviour warrants the designation.
- [ ] The story is implementable by a competent stranger without a meeting — and by an AI agent without inventing behaviour.

---

## 20. Common Anti-Patterns

Each bad example, why it fails, and a rewrite in our standard.

### 20.1 "User can manage inventory."

*Why inadequate:* no actor (who — store officer? buyer? accountant?); "manage" hides at least six behaviours (receive, transfer, adjust, count, write off, view) with different permissions; nothing testable.

*Rewrite:* split into `STK-002 Receive stock (goods receipt) · P0 · STORE_OFFICER`, `STK-007 Transfer stock between locations · P1 · STORE_OFFICER`, `STK-011 Adjust stock quantity with reason and approval · P0 · STORE_OFFICER; approval SITE_ADMIN` — each with acceptance criteria per §6.

### 20.2 "System should work correctly."

*Why inadequate:* "correctly" is undefined; no trigger; no observable result; untestable; unfalsifiable.

*Rewrite:* define the correct behaviour as criteria: "GIVEN a counted quantity differing from system quantity WHEN the count is posted THEN an adjustment is created with reason `COUNT_CORRECTION` and the variance value is displayed per line."

### 20.3 "Admin can edit things."

*Why inadequate:* "admin" is not a role; "things" is not a record; edit-after-finalisation is exactly where products need rules (§12); no permission name.

*Rewrite:* "`ADM-005 · Amend a posted record (addendum) · P0 · RECORD_OWNER; secondary SUPERVISOR` — GIVEN a posted record WHEN the author adds an amendment with reason THEN the original stays byte-identical, the amendment shows below it with author/timestamp/reason, and the version increments."

### 20.4 "Handle errors appropriately."

*Why inadequate:* names neither the failure cases nor the behaviour; guarantees nothing.

*Rewrite:* enumerate: "Err: duplicate reference → 409 `REFERENCE_ALREADY_USED`; missing price → 422 `SERVICE_NOT_PRICED` and the operation is refused (no free service by accident); double-submit → idempotency key returns the original result."

### 20.5 "Make the page responsive."

*Why inadequate:* no target, no device, no measurement, no failure state; unverifiable.

*Rewrite:* "UI: the worklist renders a usable state ≤ 2 s p95 on the agreed 3G-equivalent profile; list API operations ≤ 400 ms p95; dense rows work on a 13-inch laptop without horizontal scroll and on tablets with large touch targets; refresh failure shows a stale-data banner with last-updated time — never a blank panel."

### 20.6 "Prevent duplicates."

*Why inadequate:* which duplicate (creation, payment, submission)? Prevented how, observed as what, and what happens to the second actor?

*Rewrite:* "GIVEN the same creation submitted twice with one idempotency key THEN one record exists and the replay returns the original result. GIVEN a database unique constraint on (invoice, source_type, source_id) WHEN a retried charge arrives THEN the original line is returned without error. GIVEN two identical manual submissions within 60 s by the same operator THEN a confirmation prompt warns of a possible duplicate and requires explicit acceptance."

---

## 21. AI-Agent Implementation Rules

Future backlogs will routinely be handed to coding agents. These rules are part of the standard and should be included (verbatim or adapted) in any agent working agreement on a project using this backlog style.

1. **The story ID and its acceptance criteria are authoritative.** Not the story title, not the summary, not your recollection of similar products. The Global Story Contract is authoritative by default; where a story carries an explicit, narrower override, the story rule wins for that case — accidental contradiction remains a defect.
2. **Do not invent missing business behaviour.** If acceptance criteria are ambiguous or silent on a case that matters, *stop and report the ambiguity*. Silence is a specification gap, not permission.
3. **Do not expand story scope** because adjacent functionality seems useful, obvious, or "expected". Adjacent ideas go into a findings report, not the implementation.
4. **Implement only the authorised story/slice.** Do not silently implement P1/P2 stories while implementing a P0, and do not implement stories from future phases.
5. **Open decisions (OD entries) must not be settled by assumption.** Where the backlog records an unresolved decision with a safe temporary assumption, implement the assumption exactly — and never treat it as license to choose a different resolution.
6. **Referenced-but-undefined story IDs are external references.** Do not fabricate their behaviour; ask for their definitions or treat them as out of your slice.
7. **Canonical vocabulary is exact.** Use the backlog's named states, error codes, role IDs, and field names verbatim. Do not synonymise.
8. **Never weaken an invariant to make implementation easier** (uniqueness rules, never-delete rules, terminal-state rules, scope isolation, no-sensitive-data-in-payload rules). If an invariant seems wrong, report it; do not quietly relax it.
9. **Corrections go through the defined paths** (amendment, reversal, compensating entry, new version). Never implement a destructive shortcut — no hard deletes of final records, no editing immutable originals, no reusing retired numbers.
10. **Existing architecture constrains HOW, never WHAT.** Refactor within the architecture rules; never silently change product behaviour to fit a preferred design.
11. **Tests map back to acceptance criteria**, at the levels the story's `Test` field names. Where a story marks a test as a mandatory release regression test, it stays mandatory.
12. **Report discovered requirements separately** instead of implementing them. A found bug in another story, a missing error case, a needed permission — these are findings, not work items.
13. **UI copy must not imply behaviour the product does not perform** (checks, verifications, validations that don't exist). Prohibition criteria are requirements.
14. **A task is not complete merely because the UI works.** Service, API, permission, isolation, concurrency, audit, and state-legality tests must pass as specified.

---

## 22. Backlog-Level Standard

The house style is more than story format. A canonical backlog carries document-level machinery that keeps dozens — or hundreds — of stories internally consistent. **Apply the machinery proportionally: use the smallest backlog-level machinery that preserves correctness, traceability, and cross-story consistency.** Do not make a 12-story product create heavyweight matrices that add no value; equally, do not let a large, stateful, multi-role product skip the machinery needed to stay internally consistent. Classify each mechanism by applicability:

**CORE — every canonical product backlog:**

- **Document status block.** "CANONICAL BACKLOG" marking, date, what it supersedes, and a reconciliation note for how conflicting drafts were merged. One authoritative document; earlier drafts are historical.
- **Executive/product summary.** Half a page: what the product is, the loop that makes it work, and the three or four safety/money/integrity principles that shape every story.
- **Actors and roles table** (where the product has multiple roles — nearly always; a single-role tool may fold this into the summary). Canonical role IDs + meanings + alias normalisations (§4).
- **Epic catalogue table.** Epic, name, story counts, P0/P1/P2 per epic, totals.
- **Global Story Contract.** The per-story defaults: tenancy/scope filtering, permission-denial behaviour, audit defaults, idempotency, concurrency defaults, validation authority, UI/performance targets, and the standard test obligation per story. Explicitly *"part of each story's acceptance criteria and not repeated per story"* — and explicitly overridable by a narrower story rule where the product requires it (§1, principle 12).
- **Canonical vocabulary block.** The exact term list — record names, state names, enumeration values, timestamp field names — with "never X" notes where synonyms were killed.
- **Priority/story summary table** (per-epic P0/P1/P2 counts and reconciliation of totals).
- **Open Product Decisions register.** `OD-ID · Question · Why unresolved · Affected stories · Safe temporary assumption`. Items needing domain-expert, legal, or regulatory validation are labelled and **must not be silently settled**.
- **Reconciliation / change log.** Editorial record of merges, renumberings, terminology unifications, and resolved priority disagreements. Explicitly *not part of product requirements*.

**CONDITIONAL — include when the product needs them:**

- **Operating assumptions**, when the environment constrains the stories (connectivity, currency, regulations, scale, integration reality). Assumptions are compiled from the stories, not invented.
- **End-to-end journeys**, when a workflow spans multiple stories/roles: named walkthroughs (A, B, C…) proving the story set realises the full workflow *story-by-story with no dead ends, no duplicated records, no duplicated charges*. A journey that cannot be walked is a backlog bug.
- **State-machine appendix**, when records are stateful: one authoritative table per stateful record (§7.2) that every story referencing those states must match exactly.
- **Handoff matrix**, for multi-role workflows: role → action (story) → receiving role → resulting record/state → what the receiver sees. Consolidates cross-role flow in one view.
- **Permissions matrix**, when permission granularity warrants a consolidated view: role × capability grid compiled from story `Perm` fields, with marks for explicit grants, conditional grants, and denials.
- **Audit event catalogue**, when the product has substantive audit obligations: named events per domain, with high-value flags.
- **External-reference catalogue**, when the backlog references story IDs defined elsewhere: every referenced-but-undefined ID, listed so no reference dangles invisibly. *No story from an undefined epic is ever invented.* This catalogue remains the authoritative list of all such references.
- **Pilot core / release subset**, when a phased first deployment is planned — a named subset of *existing* story IDs sufficient for the first deployment, plus explicitly-reasoned deferrals.

**LARGE / COMPLEX PROJECTS — when delivery planning requires them:**

- **Implementation waves.** Vertical slices of existing story IDs, each with a one-line deliverable, derived from dependencies — not from priority alone.
- **Expanded Definition of Done catalogue.** The compiled test/quality obligations (service tests, API contract tests incl. 403/404/409, UI happy+negative with explicit loading/empty/error states, scope-isolation tests, audit assertions, state-transition legality tests, accessibility, generated-type validation, migration/rollback path, idempotency and concurrency tests). Closing line: *"A task is not complete merely because the UI works."* A brief per-story DoD line belongs in the Global Contract everywhere; the fully compiled catalogue earns its keep on larger or regulated projects.

---

## 23. Worked Examples

Three complete stories in the house style, from three unrelated domains. They demonstrate the standard's range: state machines, permissions, concurrency, finalisation, and error/edge discipline. (Domains: wholesale inventory; school admissions; NGO field operations.)

---

### Example A — Inventory domain

**STK-011 · Adjust stock quantity with reason and approval · P0 · `STORE_OFFICER`; approval `SITE_ADMIN`**

**Story** As a store officer, I want to correct stock quantities when physical reality diverges from the system, with a reason and — for large corrections — a supervisor's approval, so the books stay truthful and discrepancies are visible and attributable. **Value** Quantities edited directly rot silently; an append-only adjustment ledger makes every divergence explainable, auditable, and reportable, and deters both error and theft.

**Pre** Product and batch records exist; the officer holds `inventory.adjust`; the location is active.

**Trig** Discrepancy found during a count, damage, expiry, theft, or supplier return.

**Flow** Select product + batch + location → enter signed quantity and direction → select reason (`COUNT_CORRECTION`, `DAMAGE`, `BREAKAGE`, `THEFT_LOSS`, `EXPIRY_DISPOSAL`, `RETURN_TO_SUPPLIER`, `OTHER`) + mandatory note for `OTHER` → optional reference (disposal certificate, count session) → submit. Above the configurable value threshold the adjustment is `PENDING_APPROVAL` and changes nothing; `SITE_ADMIN` approval posts it. On posting, an append-only ledger entry is written and the balance changes by exactly the entered amount. The adjustment record is immutable thereafter.

**Alt** (a) Below threshold → posts immediately, no approval step. (b) Approval rejected → adjustment becomes `REJECTED` (terminal) with reason; balance unchanged. (c) Adjustment would make the balance negative → refused in both draft and approval paths. (d) Count-session adjustments reference the session and inherit its approval state.

**AC** GIVEN a variance of −14 at 4,500 per unit against a 10,000 threshold WHEN submitted THEN the adjustment is `PENDING_APPROVAL`, no ledger entry exists, and the approving admin sees product, batch, variance, value impact and reason. GIVEN approval with reason "count sheet signed" THEN the ledger entry is written, the balance decreases by exactly 14, and the adjustment becomes immutable. GIVEN an adjustment that would drive the balance below zero WHEN submitted or approved THEN 422 `NEGATIVE_BALANCE_FORBIDDEN` and nothing changes. GIVEN a rejection THEN the adjustment is `REJECTED` (terminal), the balance is unchanged, and both submitter and approver actions are audited. GIVEN the same adjustment submitted twice with one idempotency key THEN one adjustment and one eventual ledger entry exist. GIVEN a write-off with reason `EXPIRY_DISPOSAL` THEN its value appears in the monthly wastage report, separated from theft/damage. GIVEN another site's session WHEN the adjustment is requested THEN not-found, no existence leak.

**Perm** `inventory.adjust` (STORE_OFFICER, SITE_ADMIN); posting above threshold additionally requires `inventory.adjust.approve` (SITE_ADMIN only); an approver may not approve their own submission (`SELF_APPROVAL_FORBIDDEN`).

**Data** `StockAdjustment` (reason, note, reference, value snapshot, states `PENDING_APPROVAL | POSTED | REJECTED`), `StockLedger(ADJUSTMENT)` entry on posting only. Balances are never edited directly — only via ledger entries.

**Audit** `ADJUSTMENT_SUBMITTED`, `ADJUSTMENT_APPROVED`/`ADJUSTMENT_REJECTED` (actor, reason), `ADJUSTMENT_POSTED` with before/after balances.

**Err** Missing reason → 422 `REASON_REQUIRED`; `OTHER` without note → 422 `OTHER_REQUIRES_NOTE`. Concurrent adjustments on the same batch → each validates against the *current* balance inside its transaction; a combination that would go negative → 422 with the current balance returned. Adjustment against a batch in a closed count session → 409 naming the session.

**UI** Fast line-entry grid; running value impact displayed live; the approval queue shows ageing; below-threshold path never shows an approval step; every state has an explicit empty state.

**Dep** STK-002 (receive stock), STK-006 (batch records), STK-014 (movement ledger), REP-003 (wastage report; external reference).

**OOS** Direct balance editing (never permitted), purchase orders, supplier invoices/payables, barcode scanning, negative-stock "debt" balances.

**Test** Threshold boundary at exactly the configured value; negative-balance matrix (draft-time vs approval-time); self-approval refusal; idempotency; ledger arithmetic (recomputed-from-zero equals displayed balance); report attribution by reason.

---

### Example B — School system domain

**ENR-004 · Decide an enrolment application (approve / reject) · P0 · `ADMISSIONS_OFFICER`; secondary `REGISTRAR`**

**Story** As an admissions officer, I want to approve or reject a screened application with a recorded decision, so that the applicant's place is secured or freed, the family is notified, and the decision is defensible on review. **Value** The decision is the pivot of the admissions workflow; an unrecorded or duplicated decision either double-books scarce places or loses paying applicants.

**Pre** Application in `READY_FOR_DECISION` (all mandatory screening complete: documents verified, assessment recorded, capacity check passed); officer holds `enrolment.decide` for the grade in scope.

**Trig** Officer opens the decision action from the admissions worklist.

**Flow** Decision screen summarises the application, screening evidence, capacity position, and any flags → officer selects **Approve** (place reserved; offer issued) or **Reject** (reason from list: `CAPACITY_FULL`, `ASSESSMENT_BELOW_THRESHOLD`, `DOCUMENTS_UNSATISFACTORY`, `GRADE_INELIGIBLE_AGE`, `OTHER` + note) with mandatory reason for both paths → on confirm, application `APPROVED`/`REJECTED` (terminal); approval reserves exactly one capacity slot, records decider and timestamp, fires the offer notification (ENR-006), and creates the enrolment task for the registrar.

**Alt** (a) Capacity changed since screening (another approval consumed the slot) → the decision screen shows the new position; approving a full grade → 409 `CAPACITY_EXHAUSTED` unless the waitlist-override capability is used (reason mandatory). (b) Applicant withdrew between screening and decision → decision is refused; the withdrawal path (ENR-005) is the only exit; application `WITHDRAWN`. (c) Rejection later contested → a linked appeal application (ENR-009) is a new record referencing the original; the original decision is never reopened or edited. (d) Decision by registrar on behalf → permitted; both decider-of-record and acting user are stored.

**AC** GIVEN a `READY_FOR_DECISION` application with one remaining capacity slot WHEN approved THEN the application is `APPROVED` (terminal), the slot is consumed atomically, decider and timestamp are recorded, and the registrar's enrolment task exists. GIVEN two officers deciding the last remaining slot simultaneously THEN exactly one approval commits; the other receives 409 `CAPACITY_EXHAUSTED` with the current capacity position — never a double-booking. GIVEN rejection with `ASSESSMENT_BELOW_THRESHOLD` THEN the application is `REJECTED` (terminal) with the reason retained, the slot is untouched, and the applicant notification cites the reason category only (not assessor identities). GIVEN the offer notification fails to send THEN the approval stands, the failure is shown on the officer's worklist with a retry action, and the notification is queued — notification failure never blocks the decision. GIVEN approval of an application whose applicant already holds an active enrolment at the school THEN 409 `ALREADY_ENROLLED`. GIVEN an officer without `enrolment.decide` for that grade THEN 403-equivalent with no application details in the response. GIVEN a parent portal session WHEN the decision is published THEN the status shows `APPROVED`/`REJECTED` with the published timestamp only; internal decider notes are never exposed.

**Perm** `enrolment.decide` (ADMISSIONS_OFFICER, REGISTRAR — grade-scoped); waitlist override `enrolment.decide.override` (REGISTRAR; reason mandatory, audited).

**State / Workflow**
```
SUBMITTED → SCREENING → READY_FOR_DECISION → APPROVED (terminal) → enrolment task (ENR-007)
                          │                 └→ REJECTED (terminal, reason retained)
                          └→ (withdrawal only via ENR-005: WITHDRAWN, terminal)
Re-open: not defined — appeals are new linked applications (ENR-009).
Invariant: Σ approved-and-active applications per grade ≤ capacity at every instant.
```

**Data** `Application.decision`, `decision_reason`, `decided_by/at`, `capacity_slot_id`; notification outbox entry (ENR-006).

**Audit** `APPLICATION_DECIDED` (outcome, reason, decider, capacity position at decision); `DECISION_OVERRIDE` for waitlist overrides — high-value.

**Err** Decision on a terminal application → 409 naming the current state. Reason missing → 422 `REASON_REQUIRED`. Double-confirm → idempotency returns the original decision; a repeated confirm never consumes a second slot. Notification endpoint down → queued with backoff (3 attempts), officer alerted, decision intact.

**UI** Decision screen shows capacity position and flags above the fold; **Approve** and **Reject** are equally reachable (no dark pattern); confirmation summarises what becomes immutable and what the applicant will see; worklist rows show decision age against the intake deadline.

**Dep** ENR-001 (submission), ENR-003 (screening), ENR-006 (offer notification), ENR-007 (enrolment task), ENR-009 (appeals; external reference).

**OOS** Automatic scoring/ranking of applicants, bulk decisions, waitlist reordering (ENR-008), scholarship/fee assessment, interviews scheduling.

**Test** The two-officer last-slot race (exactly one commits) is a **mandatory release regression test**; decision-on-terminal-state matrix; permission and grade-scope denial; notification-failure non-blocking path; capacity invariant test under concurrent approvals across grades.

---

### Example C — NGO field-operations domain

**FVR-003 · Submit a field visit report · P0 · `FIELD_OFFICER`**

**Story** As a field officer, I want to complete and submit the report for a monitoring visit while the details are fresh — from the field, on a patchy connection — so the programme has timely, attributable evidence and the work I have typed is preserved across transient network failures while my session stays open. **Value** Reports written from memory days later are unreliable; field tools that silently discard typed work during connectivity drops destroy officer trust and cause re-visits the budget cannot afford. The promise is deliberately scoped: drafts autosave to the server, so an open session survives network outages — but drafts are held in memory only, so a crashed or closed session can still lose the last unsaved typing, which is exactly why the save-state indicator is persistent and unmistakable and final submission is an explicit, idempotent action.

**Pre** Visit assigned to the officer and in `IN_PROGRESS` or `COMPLETED_VISIT` state; officer holds `report.create` for that visit.

**Trig** Officer opens the visit's report form (auto-created `DRAFT` on first open).

**Flow** Form sections: attendance counts, service-delivery checklist, free-text observations (≤4000 chars, line breaks preserved), photos optional, GPS location captured automatically at first save → autosave to the server every ~20 s of typing pause with a visible save-state chip ("Saved 14:32:05" / "Not saved — retrying", never a vanishing toast) → officer reviews the completeness checklist → **Submit** → server validates mandatory sections → report `SUBMITTED` (immutable from that moment), attributed to the officer with timestamp and the visit's location; programme supervisor's review queue gains the item.

**Alt** (a) Connection drops during autosave → content retained in memory only with a persistent warning banner; retry with backoff; on reconnection the draft saves without duplication. (b) Mandatory section incomplete at submit → 422 listing every missing field; the report stays `DRAFT` and nothing is submitted. (c) Supervisor requires corrections after submission → an addendum is added by the officer (FVR-005); the submitted original is never edited. (d) Officer submits, then taps submit again on a slow network → idempotency: one submission, original result returned. (e) Visit reassigned mid-draft → the draft follows the visit with the original author retained as co-author; both attributions display.

**AC** GIVEN a draft with all mandatory sections complete WHEN submitted THEN the report is `SUBMITTED` (immutable — any edit returns 409 `REPORT_SUBMITTED`), carries officer, timestamp, GPS point and visit reference, and appears in the supervisor review queue within 30 seconds. GIVEN the same draft open on two devices WHEN both save THEN the first save applies and the second is rejected with 412 `VERSION_CONFLICT` plus the current version and a field-level diff — content is never silently overwritten from either device. GIVEN submit tapped twice on a slow connection THEN exactly one submission exists; the replay returns the original result. GIVEN a mandatory section empty WHEN submitted THEN 422 `MANDATORY_SECTIONS_MISSING` listing each missing field; the draft (including autosaved text) is fully retained. GIVEN attendance count of −5 or 10,000 for a single visit WHEN saved THEN 422 `VALUE_OUT_OF_RANGE` with the accepted range. GIVEN the network fails mid-submit THEN the outcome is unambiguous: either the report is `SUBMITTED` (idempotent retry confirms) or still `DRAFT` with the officer's content — never a half-submitted record. GIVEN a report on a visit belonging to another programme WHEN accessed by this officer THEN not-found; no existence leak. GIVEN submission THEN `REPORT_SUBMITTED` is audited with report version reference and content hash; the free-text body stays only in the report record, never in the audit payload.

**Perm** `report.create` (FIELD_OFFICER, own assignment); `report.read` (programme-scoped SUPERVISOR, PROGRAMME_MANAGER); addendum `report.amend` (author; FVR-005).

**Data** `FieldVisitReport` (states `DRAFT | SUBMITTED`; sections, GPS, version), addendum rows (FVR-005), review-queue item.

**Audit** `REPORT_SUBMITTED` (officer, visit, version reference, hash); autosaves *not* individually audited (volume) — one summary event per session.

**Err** GPS unavailable → submission proceeds with `location=null` flagged "location not captured" (never fabricated coordinates); photos exceed size cap → per-file rejection with guidance, never a silent drop; clock skew on the device → server time is authoritative for all timestamps.

**UI** Single-scroll form with section progress; save-state chip permanently visible; the completeness checklist disables **Submit** only for *hard* mandatory items (soft gaps warn, not block — a field officer must be able to submit evidence with noted gaps); works one-handed on a budget smartphone; explicit empty state for a visit with no report yet.

**Dep** FVR-001 (visit assignment), FVR-002 (visit state machine), FVR-005 (addendum), REP-002 (programme reporting; external reference).

**OOS** Offline final submission (drafts may be held in memory but a report is only submitted online — no offline completion of final records), signature capture, beneficiary personally-identifying data in the report body (see data-protection policy DP-1), automated report quality scoring.

**Test** Two-device stale-save conflict; double-submit idempotency; mandatory-section matrix; immutability enforcement at the API; network-failure atomicity (submitted-or-draft, never both, never neither); range boundaries; GPS-absent path; **the two-device conflict and double-submit tests are mandatory release regression tests**.

---

*End of standard. Derived from our production backlog methodology; maintained as the house standard for all future projects.*
