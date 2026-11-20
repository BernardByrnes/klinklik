# Owner §59 question dossier — KlinKlik clinic spine

Status after S-24 (`392a0b1`): **28 VERIFIED / 52 PARTIAL / 2 MISMATCH / 52 FENCED** across 134 active CMD contracts; **P1 0, P2 54**. This dossier contains only owner-reserved questions that remain open. It makes no decisions on the owner's behalf.

Owner-maintained records cited by name but not shipped in the release worktree: `K:/clinicopus/docs/implementation/lead-decisions.md` and review notes `review-18` through `review-25` in `K:/clinicopus/docs/implementation/`. In-worktree evidence files are `IMPLEMENTATION_BLUEPRINT.md`, `blueprint-validation/TRACEABILITY.md`, `docs/implementation/s17-cmd-audit.md`, and `docs/implementation/s22-audit-code-map.md`.

## Already settled — do not re-ask

| Decision | Settled position | Source |
| --- | --- | --- |
| D-01 | Lead decides engineering scope, sequence, evidence standards, remediation priority and publication; owner reserves clinical content, §973 MFA exceptions, finance policy, deployment/pilot and new authority areas. | lead-decisions.md |
| D-03 / D-13 | Compatibility namespaces are an accepted pattern (legacy payment, count-open, invoice-issue); CMD-065/071/106 are closed, no route retired. | lead-decisions.md; S-21 review-22 |
| D-08 | Refund MFA has **no waiver**; refund issuance stays fenced pending §973 MFA or an explicit owner-approved time-limited exception. Q5 must not re-open this baseline. | lead-decisions.md |
| D-11 | Accepted work is published to `main`/`release/v1-clinic-spine` under standing authorization; deployment and pilot remain unauthorized. | lead-decisions.md |
| D-12 | Registry verbs are authoritative; the four S-20 verb swaps are closed. | lead-decisions.md; review-21 |
| S-18/S-19 | Pharmacy/lab label fixes and clinical idempotency enforcement are closed; P1 count is zero. | review-19, review-20 |

## Open ID coverage (exact set from artifacts)

| CMD ID | Source of openness | Artifact evidence |
| --- | --- | --- |
| CMD-014 | S-17 MISMATCH row | `s17-cmd-audit.md` P2 row: `queue_start_service is exposed by QueueClaimView ... without an idempotency_operation label` |
| CMD-136 | S-17 MISMATCH row | `s17-cmd-audit.md` P2 row: `Registry declares stock_ledger_reconcile as INTERNAL, but LedgerReconcileView is an HTTP POST route` |
| CMD-058 | S-23 money/dispensing MISSING_EMISSION | `s22-audit-code-map.md`: `PRESCRIPTION_CLAIM_RELEASED`, `PRESCRIPTION_OUTCOME`, risk class `dispensing` |
| CMD-062 | S-23 money/dispensing MISSING_EMISSION | `s22-audit-code-map.md`: `RECEIPT_ISSUED`, risk class `money` |
| CMD-076 | S-23 money/dispensing MISSING_EMISSION | `s22-audit-code-map.md`: `ALLOCATIONS_REVERSED`, `INVOICE_STATE`, risk class `money` |
| CMD-077 | S-23 money/dispensing MISSING_EMISSION | `s22-audit-code-map.md`: `INVOICE_STATE`, risk class `money` |

---

## Q1 — CMD-014 `queue_start_service`: INTERNAL declaration vs live HTTP route

**Question.** Should the registry be revised to declare the live HTTP route for `queue_start_service`, should the route be fenced, or should the divergence be accepted as a documented standing deviation?

**Evidence.** The registry declares `CMD-014 | queue_start_service / application.queue / INTERNAL queue_start_service`, and says "INTERNAL COMPOSED STEP used only by the stage-owning parent such as CMD-025 or CMD-030 ... no standalone start route can detach location from its stage record" (`IMPLEMENTATION_BLUEPRINT.md:1405`). The live route is `backend/scheduling/views.py:61` (`class QueueClaimView`, POST `queue/<pk>/claim/`); the S-17 row is P2 MISMATCH (`s17-cmd-audit.md`). D-13 already records "no behavior change" and places this on the owner's §59 list.

**Options.**
1. **Registry revision** — declare the HTTP surface as the contract; no code change, but reinterprets a frozen "no standalone start route" decision.
2. **Fence the route** — remove or disable the HTTP surface; breaks live first-party callers, needs a new authorized slice.
3. **Documented standing deviation** — accept the route as internal-step exposure with scope guards; no code change. *Engineering default (default, not decision): option 3, consistent with D-13.*

**Impact if unanswered.** CMD-014 stays MISMATCH/P2; the blueprint and implementation keep disagreeing about whether a standalone start route exists.

## Q2 — CMD-136 `stock_ledger_reconcile`: INTERNAL declaration vs live HTTP route

**Question.** Same three-way question for `stock_ledger_reconcile`: registry revision, fence, or documented deviation?

**Evidence.** Registry declares `CMD-136 | stock_ledger_reconcile / application.inventory / INTERNAL stock_ledger_reconcile`, describing a SYSTEM nightly per-f facility reconciliation or authorized manual retry (`IMPLEMENTATION_BLUEPRINT.md:1558`). Code exposes `backend/inventory/views.py:583` (`class LedgerReconcileView`, POST) declaring CMD-136; S-17 P2 MISMATCH (`s17-cmd-audit.md:75`). D-13 says no behavior change and owner §59 listing.

**Options.**
1. **Registry revision** — declare the POST retry surface (fits the registry's "authorized manual retry" language) with no code change.
2. **Fence the route** — remove HTTP retry; needs a new authorized slice and may remove the manual retry path.
3. **Documented standing deviation** — keep the route and mark the INTERNAL wording as documentation debt. *Engineering default (default, not decision): option 1 for this command, because the registry text already names an authorized manual retry.*

**Impact if unanswered.** CMD-136 stays MISMATCH/P2; the reconciliation retry route's contract remains ambiguous.

## Q3 — Money emissions with no attachable event

**Question.** For OTC `RECEIPT_ISSUED`, payment-reversal `ALLOCATIONS_REVERSED` and `INVOICE_STATE` (CMD-076/077): add declared audit events, reclassify the registry declarations as superseded, or accept documented absence?

**Evidence.** S-23 classified these as MISSING_EMISSION/risk `money` (`s22-audit-code-map.md`). `RECEIPT_ISSUED` does not exist in code; today OTC sale emits `OTC_SALE_COMPLETED` (`backend/pharmacy/dispensing.py:916`) and the only receipt-related event is `RECEIPT_REPRINTED` (`backend/billing/services.py:876`) for a print artifact. Reversal emits `PAYMENT_REVERSED` at `backend/billing/services.py:1194` but no allocation-specific or invoice-state event; credit-note issue emits `CREDIT_NOTE_ISSUED` at `backend/billing/services.py:1435` with no invoice-state event. The reviewed functions are `reverse_payment` (`backend/billing/services.py:1137`) and `issue_credit_note` (`backend/billing/services.py:1366`). S-24 deliberately did not invent emissions.

**Options.**
1. **Add declared events** — new audited emissions in a separately authorized money slice; strongest evidence but changes audit surface.
2. **Reclassify as REGISTRY_SUPERSEDED** — owner §59 registry revision; no code change.
3. **Accept documented absence** — keep current events and record the gap explicitly. *Engineering default (default, not decision): option 2 for `RECEIPT_ISSUED` (print artifact already has its own event family); options 1 or 2 for the other three need owner policy.*

**Impact if unanswered.** CMD-062/076/077 stay PARTIAL/P2; money audit evidence remains weaker than the registry claims.

## Q4 — Dispensing emissions with no attachable event

**Question.** For `PRESCRIPTION_CLAIM_RELEASED` and `PRESCRIPTION_OUTCOME` (CMD-058): add declared events, reclassify as superseded, or accept documented absence?

**Evidence.** S-23 classified both as MISSING_EMISSION/risk `dispensing` (`s22-audit-code-map.md`). Claim is emitted as `PRESCRIPTION_CLAIMED` at `backend/pharmacy/dispensing.py:380`; `confirm_dispense` writes `DISPENSE_CONFIRMED` at `backend/pharmacy/dispensing.py:684` and versions prescription-item state, but emits no claim-release or prescription-outcome event. The full functions are `claim_prescription` (`backend/pharmacy/dispensing.py:332`) and `confirm_dispense` (`backend/pharmacy/dispensing.py:564`).

**Options.**
1. **Add declared events** — new audited emissions in a separately authorized dispensing slice.
2. **Reclassify as REGISTRY_SUPERSEDED** — accept that claim release/outcome are represented by dispense state and item versions; owner §59 registry revision.
3. **Accept documented absence** — keep the gap as a named finding. *Engineering default (default, not decision): option 2, because the state transitions are durably versioned, but this is an owner call on audit semantics.*

**Impact if unanswered.** CMD-058 stays PARTIAL/P2; dispensing audit evidence stays weaker than the registry claims.

## Q5 — Confirm or reject the two REGISTRY_SUPERSEDED framings

**Question.** Are the S-23 `REGISTRY_SUPERSEDED` classifications for CMD-030 (`ENCOUNTER_RESUMED`) and CMD-079 (`REFUND_PROCESSED`) acceptable, or should the registry declaration be reinstated with new implementation?

**Evidence.** S-23 recorded CMD-030 as "resume is folded into encounter open/reuse; no separate resume command exists" (`s22-audit-code-map.md`; `backend/clinical/services.py:34` `start_encounter`). CMD-079 is exposed only by `backend/billing/views.py:616` (`class RefundApproveFencedView`), which refuses with `REFUND_ISSUANCE_DISABLED` until §973 MFA; no refund-process path exists. D-08 settles the MFA baseline as **no waiver** — Q5 must not be read as a request to waive it.

**Options.**
1. **Confirm supersession** — owner §59 registry revision for both declarations; no code change. *Engineering default (default, not decision): option 1.*
2. **Reject and implement** — new authorized slice to restore a distinct resume command and a refund-process path after MFA authority exists.
3. **Partial confirmation** — accept CMD-030 supersession, require a future CMD-079 process path only when D-08 is satisfied.

**Impact if unanswered.** Both rows stay at their current PARTIAL/registry-gap state; refund design remains tied to the D-08 fence.

## Q6 — Standing P2 weak-test-evidence class

**Question.** Authorize a test-naming slice so slice tests name the CMD/operation they exercise, or accept the class as documented evidence?

**Evidence.** The S-17 audit has PARTIAL rows whose entire discrepancy is "Slice test file does not name this CMD or operation; test exercise not proven mechanically" (e.g. CMD-003, CMD-008, CMD-025, CMD-026, CMD-063, CMD-066; `s17-cmd-audit.md`). The tests do call the endpoints; the gap is traceability of evidence, not a product defect. S-16/S-17 already record the evidence-index limitation.

**Options.**
1. **Authorize a test-only naming slice** — add CMD/operation identifiers to existing tests and re-run the affected lanes; no product change.
2. **Accept as documented** — keep the rows PARTIAL with the named gap, no new slice. *Engineering default (default, not decision): option 1 for auditability, but this consumes an owner-authorized slot.*
3. **Scope a hybrid** — name tests only for safety-critical CMDs, accept the rest.

**Impact if unanswered.** The weak-test-evidence PARTIAL class stays open and the audit remains evidence-index-level for those commands.

---

No PHI appears in this dossier. No clinical, pharmacological, financial or regulatory rule was invented or decided; every fence remains with its owner decision named.
