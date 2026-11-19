#!/usr/bin/env python3
"""Apply S-17 manual audit findings to the generated inventory and render reports."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/implementation/s17-cmd-audit.json"
MD = ROOT / "docs/implementation/s17-cmd-audit.md"

OVERRIDES = {
    "CMD-001": {
        "verdict": "VERIFIED", "severity": "P2",
        "discrepancy": "Legacy scheduling.CheckInView also exposes a POST check-ins route without declaring CMD-001; the canonical CMD-001 view is correctly labelled.",
        "evidence_pointer": "backend/scheduling/views.py",
    },
    "CMD-002": {
        "verdict": "VERIFIED", "severity": "P2",
        "discrepancy": "Legacy patients.PatientListCreateView also exposes a POST patient-create route without declaring CMD-002; the canonical reception view is correctly labelled.",
        "evidence_pointer": "backend/patients/views.py",
    },
    "CMD-014": {
        "verdict": "MISMATCH", "severity": "P2",
        "discrepancy": "queue_start_service is exposed by QueueClaimView (POST queue/<pk>/claim/) without an idempotency_operation label.",
        "evidence_pointer": "backend/scheduling/views.py:QueueClaimView",
    },
    "CMD-024": {
        "verdict": "PARTIAL", "severity": "P2",
        "discrepancy": "QueueExpireSweepView declares CMD-024, but S-16 fenced the slice and no operational cutoff/authorization evidence was found; route exists, authority not evidenced.",
        "evidence_pointer": "backend/application/queue/views.py:QueueExpireSweepView",
    },
    "CMD-031": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "encounter_draft_save is implemented by EncounterNoteView (POST/PATCH notes) which declares no idempotency_operation, so the registry idempotency namespace is absent.",
        "evidence_pointer": "backend/clinical/views.py:EncounterNoteView",
    },
    "CMD-035": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "encounter_sign is implemented by EncounterSignView (POST sign) which declares no idempotency_operation.",
        "evidence_pointer": "backend/clinical/views.py:EncounterSignView",
    },
    "CMD-038": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "encounter_addendum is implemented by EncounterAmendView (POST amend) which declares no idempotency_operation.",
        "evidence_pointer": "backend/clinical/views.py:EncounterAmendView",
    },
    "CMD-071": {
        "verdict": "MISMATCH", "severity": "P2",
        "discrepancy": "invoice_issue is also exposed by InvoiceListCreateView (POST invoices/) without declaring CMD-071; the canonical issue path runs through visit check-in.",
        "evidence_pointer": "backend/billing/views.py:InvoiceListCreateView",
    },
    "CMD-092": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "patient_allergy_record is implemented by PatientAllergyView (POST allergies) without an idempotency_operation label.",
        "evidence_pointer": "backend/clinical/views.py:PatientAllergyView",
    },
    "CMD-093": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "patient_allergy_status_set is implemented by PatientAllergyStatusView (POST allergy-status) without an idempotency_operation label.",
        "evidence_pointer": "backend/clinical/views.py:PatientAllergyStatusView",
    },
    "CMD-094": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "allergy_entered_error is implemented by PatientAllergyEnteredInErrorView without an idempotency_operation label.",
        "evidence_pointer": "backend/clinical/views.py:PatientAllergyEnteredInErrorView",
    },
    "CMD-095": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "encounter_allergy_review is implemented by EncounterAllergyReviewView (POST allergies/review) without an idempotency_operation label.",
        "evidence_pointer": "backend/clinical/views.py:EncounterAllergyReviewView",
    },
    "CMD-096": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "diagnosis_save is implemented by EncounterDiagnosisListCreateView (POST diagnoses) without an idempotency_operation label.",
        "evidence_pointer": "backend/clinical/views.py:EncounterDiagnosisListCreateView",
    },
    "CMD-099": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "disposition_set is implemented by EncounterDispositionView (PATCH disposition) without an idempotency_operation label.",
        "evidence_pointer": "backend/clinical/views.py:EncounterDispositionView",
    },
    "CMD-101": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "followup_record is implemented by EncounterFollowUpView (PATCH follow-up) without an idempotency_operation label.",
        "evidence_pointer": "backend/clinical/views.py:EncounterFollowUpView",
    },
    "CMD-106": {
        "verdict": "MISMATCH", "severity": "P2",
        "discrepancy": "payment_method_configure is implemented by PaymentMethodListView (POST payment-methods) without declaring CMD-106.",
        "evidence_pointer": "backend/billing/views.py:PaymentMethodListView",
    },
    "CMD-034": {
        "verdict": "PARTIAL", "severity": "P2",
        "discrepancy": "encounter_resume service exists but no dedicated route declares CMD-034; resume appears folded into the encounter open path under CMD-030.",
        "evidence_pointer": "backend/clinical/services.py",
    },
    "CMD-039": {
        "verdict": "PARTIAL", "severity": "P2",
        "discrepancy": "encounter_transfer_takeover service exists but no route or idempotency namespace declares CMD-039.",
        "evidence_pointer": "backend/clinical/services.py",
    },
    "CMD-059": {
        "verdict": "FENCED", "severity": "P3",
        "discrepancy": "dispense_cancel has service code but no route; S-12 scope fence leaves dispense cancellation out of the supplied slice.",
        "evidence_pointer": "IMPLEMENTATION_BLUEPRINT.md",
    },
    "CMD-042": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "lab_collect is implemented by LabItemCollectView but that view declares CMD-043; CMD-042 has no correct idempotency namespace.",
        "evidence_pointer": "backend/laboratory/views.py:108",
    },
    "CMD-043": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "lab_reject_specimen is implemented by LabItemRejectView but that view declares CMD-044.",
        "evidence_pointer": "backend/laboratory/views.py:125",
    },
    "CMD-044": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "lab_result_save is implemented by LabResultSaveView but that view declares CMD-047; the registry verb is PATCH while the view implements POST.",
        "evidence_pointer": "backend/laboratory/views.py:145",
    },
    "CMD-045": {
        "verdict": "PARTIAL", "severity": "P2",
        "discrepancy": "No dedicated lab_verify route declares CMD-045; verification is bundled with release in LabResultReleaseView, so the standalone command is not evidenced.",
        "evidence_pointer": "backend/laboratory/views.py:173",
    },
    "CMD-046": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "lab_release is implemented by LabResultReleaseView but that view declares CMD-048.",
        "evidence_pointer": "backend/laboratory/views.py:173",
    },
    "CMD-047": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "lab_cancel is implemented by LabItemCancelView but that view declares CMD-051.",
        "evidence_pointer": "backend/laboratory/views.py:224",
    },
    "CMD-048": {
        "verdict": "FENCED", "severity": "P3",
        "discrepancy": "No lab_refer_out route exists; external referral/notification remains a registry fence.",
        "evidence_pointer": "IMPLEMENTATION_BLUEPRINT.md",
    },
    "CMD-051": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "CMD-051 (lab_external_order) is declared on LabItemCancelView, a cancel operation; no external-order route is evidenced.",
        "evidence_pointer": "backend/laboratory/views.py:224",
    },
    "CMD-064": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "stock_transfer is implemented by StockTransferView but its idempotency_operation is the non-registry label 'inventory.stock_transfer' instead of CMD-064.",
        "evidence_pointer": "backend/inventory/views.py:329",
    },
    "CMD-065": {
        "verdict": "MISMATCH", "severity": "P2",
        "discrepancy": "StockCountOpenView and StockCountSubmitView both declare CMD-065; open and submit are distinct operations sharing one idempotency namespace.",
        "evidence_pointer": "backend/inventory/views.py:416,462",
    },
    "CMD-027": {
        "verdict": "PARTIAL", "severity": "P2",
        "discrepancy": "TriageView and TriageRecordCompleteView both declare CMD-027; they are MIG-002 mode-gated compatibility/canonical routes, so no simultaneous collision was proven, but one namespace serves two routes.",
        "evidence_pointer": "backend/clinical/views.py:119,1287",
    },
    "CMD-075": {
        "verdict": "MISMATCH", "severity": "P1",
        "discrepancy": "Legacy InvoicePaymentView shares CMD-075 with the canonical InvoiceCanonicalPaymentView but does not set requires_idempotency; the same namespace covers a non-idempotent compatibility route.",
        "evidence_pointer": "backend/billing/views.py:175,203",
    },
    "CMD-078": {
        "verdict": "FENCED", "severity": "P3",
        "discrepancy": "RefundFencedView and RefundRejectFencedView both declare CMD-078, but both refuse the command until §973 MFA authority; no state-changing route is active.",
        "evidence_pointer": "backend/billing/views.py:598",
    },
    "CMD-136": {
        "verdict": "MISMATCH", "severity": "P2",
        "discrepancy": "Registry declares stock_ledger_reconcile as INTERNAL, but LedgerReconcileView is an HTTP POST route declaring CMD-136; route/declared-location conflict.",
        "evidence_pointer": "backend/inventory/views.py:581",
    },
    "CMD-110": {
        "verdict": "MISMATCH", "severity": "P2",
        "discrepancy": "Registry declares POST product_instruction_template_set; ProductInstructionTemplateView implements PATCH only.",
        "evidence_pointer": "backend/pharmacy/views.py:283",
    },
}


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    for command in data["commands"]:
        override = OVERRIDES.get(command["id"])
        if override:
            command.update(override)
            if override["severity"] != "P3":
                command["manual_finding"] = True
        command.setdefault("severity", "P3" if command["verdict"] == "FENCED" else "P2")
    data["summary"]["verdict_counts"] = dict(
        Counter(command["verdict"] for command in data["commands"])
    )
    data["summary"]["severity_counts"] = dict(
        Counter(command["severity"] for command in data["commands"] if command["verdict"] in {"MISMATCH", "PARTIAL"})
    )
    data["summary"]["manual_overrides"] = len(OVERRIDES)
    DATA.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# S-17 CMD-by-command contract audit",
        "",
        "Base: `54291e4` (published main / release/v1-clinic-spine).",
        "Generated: 2026-11-19 (Africa/Kampala), local verification worktree `codex/s17-cmd-audit`.",
        "",
        "This is an evidence audit. It does not change product code, add routes, or fix defects.",
        "",
        "## Summary",
        "",
        f"- Active commands audited: {len(data['commands'])} of 134; retired CMD-097 and CMD-107 excluded.",
        "- Verdicts: " + ", ".join(
            f"{key} {value}" for key, value in sorted(data["summary"]["verdict_counts"].items())
        ) + ".",
        "- Machine inventory: `docs/implementation/s17-cmd-audit.json`; machine assertions: `backend/tests/test_s17_cmd_audit.py`.",
        "- Discrepancy severity: " + ", ".join(
            f"{key} {value}" for key, value in sorted(data["summary"]["severity_counts"].items())
        ) + ".",
        f"- Manual findings applied: {data['summary']['manual_overrides']}.",
        "",
        "## Discrepancy list (severity ordered)",
        "",
        "| Severity | CMD | Operation | Verdict | Discrepancy | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    severity_order = {"P1": 0, "P2": 1, "P3": 2}
    discrepancies = sorted(
        (command for command in data["commands"] if command["discrepancy"]),
        key=lambda command: (severity_order.get(command["severity"], 9), command["id"]),
    )
    for command in discrepancies:
        lines.append(
            f"| {command['severity']} | {command['id']} | {command['operation']} | {command['verdict']} | "
            f"{command['discrepancy'].replace('|', '/')} | `{command['evidence_pointer']}` |"
        )

    lines += [
        "",
        "## Full command table",
        "",
        "| CMD | Operation | Slice(s) | Idempotency | Verdict | Severity | Evidence / discrepancy |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for command in data["commands"]:
        note = command["discrepancy"] or f"Route/service/audit/test evidence indexed at `{command['evidence_pointer']}`."
        lines.append(
            f"| {command['id']} | {command['operation']} | {','.join(command['slices']) or '-'} | "
            f"{'YES' if command['idempotency_required'] else 'NO'} | {command['verdict']} | {command['severity']} | "
            f"{note.replace('|', '/')} |"
        )

    lines += [
        "",
        "## Honest limits",
        "",
        "- Machine checks verify inventory, URL callback linkage, idempotency-label namespace and declared audit-code presence. They cannot prove a service function performs the named state transition or that a test asserts the outcome.",
        "- Manual verdicts are based on declared facts, view/service source inspection and slice-test indexing; `VERIFIED` means the declared route, label, capability, audit codes and named slice test were located and found consistent, not that every error branch was executed.",
        "- Many registry audit event names differ from implementation names (for example `DISPENSE_CREATED` vs `DISPENSE_PREPARED`). Those rows are `PARTIAL`, not `VERIFIED`.",
        "- Capability declarations use role names in the registry and code strings in views; direct equality is rarely possible, so capability enforcement is checked qualitatively, not machine-asserted.",
        "- FENCED commands are authority/scope fences, not failures. A few FENCED rows additionally carry a real duplicate-label note where both fenced views refuse state change.",
        "- The P1 label misroutes in laboratory, inventory and clinical/billing routes, and the non-registry 'inventory.stock_transfer' label, are findings only. No product code was changed; fixing them is an owner decision.",
        "- Plan-17 asks for a route with 'the same path', but the registry declares operation names (for example `POST lab_collect`), not URL paths. The audit uses the authoritative idempotency label -> view -> URL callback link; URL names differ by app (underscored reception names vs hyphenated clinical/pharmacy names), so operation-name-to-URL-name equality was not used.",
        "- A systemic finding of this manual pass is mutating views with no `idempotency_operation` at all (clinical note/sign/diagnosis/disposition/allergy/follow-up, legacy patient/check-in/claim/create routes). These are MISMATCH rows because the registry requires idempotency for every active CMD; no route or code was added to repair them.",
    ]
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(data["summary"])


if __name__ == "__main__":
    main()
