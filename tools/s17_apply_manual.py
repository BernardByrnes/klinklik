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
    "CMD-071": {
        "verdict": "PARTIAL", "severity": "P2",
        "discrepancy": "D-13: canonical invoice_issue runs through visit check-in (issue_exact_source_lines); manual InvoiceListCreateView now uses the documented compat namespace and is allowlisted.",
        "evidence_pointer": "backend/billing/views.py:71,112",
    },
    "CMD-106": {
        "verdict": "VERIFIED", "severity": "P3",
        "discrepancy": "",
        "evidence_pointer": "backend/billing/views.py:443,466",
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
    "CMD-045": {
        "verdict": "PARTIAL", "severity": "P2",
        "discrepancy": "No dedicated lab_verify route declares CMD-045; verification is bundled with release in LabResultReleaseView, so the standalone command is not evidenced.",
        "evidence_pointer": "backend/laboratory/views.py:172",
    },
    "CMD-048": {
        "verdict": "FENCED", "severity": "P3",
        "discrepancy": "No lab_refer_out route exists; external referral/notification remains a registry fence.",
        "evidence_pointer": "IMPLEMENTATION_BLUEPRINT.md",
    },
    "CMD-051": {
        "verdict": "FENCED", "severity": "P3",
        "discrepancy": "lab_external_order is fenced by the S-11 slice; no external-order route is expected. The former wrong reference from LabItemCancelView was removed with the label fix.",
        "evidence_pointer": "IMPLEMENTATION_BLUEPRINT.md",
    },
    "CMD-027": {
        "verdict": "PARTIAL", "severity": "P2",
        "discrepancy": "TriageView and TriageRecordCompleteView both declare CMD-027; they are MIG-002 mode-gated compatibility/canonical routes, so no simultaneous collision was proven, but one namespace serves two routes.",
        "evidence_pointer": "backend/clinical/views.py:119,1287",
    },
    "CMD-075": {
        "verdict": "PARTIAL", "severity": "P2",
        "discrepancy": "Owner-authorised compatibility namespace: legacy InvoicePaymentView uses 'legacy.invoice.payment.compat' and is allowlisted in the machine test; canonical InvoiceCanonicalPaymentView retains CMD-075. No route retired.",
        "evidence_pointer": "backend/billing/views.py:175,205",
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
        "- At the S-17 base d6a92b6 the laboratory/inventory label misroutes were findings only. This S-18 branch corrected CMD-042/043/044/046/047/064 and re-marked CMD-051 FENCED; no other product behavior, verb, route or unlabeled clinical view was changed.",
        "- Plan-17 asks for a route with 'the same path', but the registry declares operation names (for example `POST lab_collect`), not URL paths. The audit uses the authoritative idempotency label -> view -> URL callback link; URL names differ by app (underscored reception names vs hyphenated clinical/pharmacy names), so operation-name-to-URL-name equality was not used.",
        "- S-21 resolved three D-13 residuals: CMD-065 is now claimed only by StockCountSubmitView (open uses a documented compat namespace); InvoiceListCreateView uses a documented compat namespace because canonical invoice issue runs through visit check-in; PaymentMethodListView is the actual canonical CMD-106 path and now carries that registry label. CMD-014 and CMD-136 remain MISMATCH rows by owner decision (no code change).",
        "- S-20 aligned the four registry verbs (CMD-044 PATCH, CMD-099/101/110 POST) with the same paths, payloads and idempotency namespaces. The three clinical/lab rows remain PARTIAL only because declared audit event names differ from code names; CMD-110 is VERIFIED.",
        "- S-19 closed the clinical P1 class: ten active clinical views now carry their registry CMD id and `requires_idempotency=True`. EncounterDiagnosisDetailView/RemoveView remain unlabelled by design: registry CMD-097 is a retired tombstone and no active id was invented. P1 count is now zero; all remaining discrepancy rows are P2 owner-deferred findings (verbs, duplicate legacy routes, compatibility namespaces, audit-name/test-naming limits).",
    ]
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(data["summary"])


if __name__ == "__main__":
    main()
