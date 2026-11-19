#!/usr/bin/env python3
"""Build the S-17 CMD inventory from the frozen registry and the code.

Run from the worktree root with:
    PYTHONPATH=backend DJANGO_SETTINGS_MODULE=clinicopus.settings python tools/s17_cmd_inventory.py
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "clinicopus.settings")

import django  # noqa: E402

django.setup()
from django.urls import get_resolver  # noqa: E402

BLUEPRINT = ROOT / "IMPLEMENTATION_BLUEPRINT.md"
TRACEABILITY = ROOT / "blueprint-validation/TRACEABILITY.md"
S16 = ROOT / "docs/implementation/s16-contract-verification.json"
OUTPUT = ROOT / "docs/implementation/s17-cmd-audit.json"

NON_EVENT = {
    "PC", "CMD", "PG", "TI", "SM", "CMC", "GSC", "OD", "BP", "BL", "REP", "AUD",
    "RCP", "APT", "J", "RG", "MIG", "ADR", "DATABASE", "STATE", "WITH", "WHERE",
    "AND", "OR", "NOT", "E", "N", "NN", "NULL", "TRUE", "FALSE", "INTERNAL",
    "POST", "PATCH", "GET", "DELETE", "UNIQUE", "CHECK", "UNSUPPORTED", "OPERATION",
}


def parse_registry():
    rows = {}
    for line in BLUEPRINT.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\| (CMD-\d{3}) \|", line)
        if not match:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        operation_cell = cells[1]
        parts = [part.strip() for part in operation_cell.split("/")]
        operation = parts[0]
        module = parts[1] if len(parts) > 1 else ""
        api = parts[2] if len(parts) > 2 else ""
        method = api.split()[0] if api and not api.startswith("INTERNAL") else "INTERNAL"
        api_name = api.split()[-1] if api else ""
        actor = cells[3]
        idempotency = cells[4]
        lock_plan = cells[5]
        owner_services = cells[6]
        error_text = cells[7]
        required = idempotency.lower().startswith("yes")
        capability_match = re.search(r"\b([a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*)\b", actor)
        rows[match.group(1)] = {
            "id": match.group(1),
            "operation": operation,
            "module": module,
            "api_text": api,
            "http_method": method,
            "api_name": api_name if method != "INTERNAL" else "",
            "internal": method == "INTERNAL",
            "rank1": cells[2],
            "actor": actor,
            "idempotency_text": idempotency,
            "idempotency_required": required,
            "lock_plan": lock_plan,
            "owner_services": owner_services,
            "audit_codes": sorted({
                token for token in re.findall(r"\b[A-Z][A-Z0-9_]{3,}\b", owner_services)
                if token not in NON_EVENT and ("_" in token or token in {"VISITOPENED"})
            }),
            "error_codes": sorted({
                token for token in re.findall(r"\b[A-Z][A-Z0-9_]{3,}\b", error_text)
                if token not in NON_EVENT and ("_" in token or token.endswith("REQUIRED"))
            }),
            "declared_capability": capability_match.group(1) if capability_match else "",
            "declared_fenced": "IMPLEMENTATION AUTHORIZATION BLOCKED" in actor.upper(),
        }
    return rows


def parse_slices():
    result = defaultdict(set)
    for block in re.split(r"\n### ", TRACEABILITY.read_text(encoding="utf-8")):
        cmd_match = re.search(r"Application command ID \(`application_command_id`\): `([^`]+)`", block)
        slice_match = re.search(r"Implementation slice ID \(`implementation_slice_id`\): `([^`]+)`", block)
        if not cmd_match or not slice_match:
            continue
        for command in cmd_match.group(1).split("|"):
            for slice_id in slice_match.group(1).split("|"):
                result[command].add(slice_id)
    return result


def code_sources():
    sources = {}
    for path in BACKEND.rglob("*.py"):
        if "migrations" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            sources[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return sources


def iter_urls():
    def walk(patterns, prefix=""):
        for pattern in patterns:
            if hasattr(pattern, "url_patterns"):
                yield from walk(pattern.url_patterns, prefix + str(pattern.pattern))
            else:
                yield pattern
    return walk(get_resolver().url_patterns)


def main():
    registry = parse_registry()
    slices = parse_slices()
    sources = code_sources()
    s16 = json.loads(S16.read_text(encoding="utf-8"))
    s16_status = {row["id"]: row["status"] for row in s16["records"] if row["family"] == "CMD"}
    s16_pointer = {row["id"]: row["evidence"] for row in s16["records"] if row["family"] == "CMD"}
    retired = {"CMD-097", "CMD-107"}

    idempotency_views = defaultdict(list)
    url_by_view = defaultdict(list)
    for pattern in iter_urls():
        view = getattr(pattern.callback, "view_class", None)
        if view is None:
            continue
        name = f"{view.__module__}.{view.__name__}"
        url_by_view[name].append(str(pattern.pattern))
        source = getattr(view, "idempotency_operation", None)
        if source:
            idempotency_views[source].append({
                "view": name,
                "url": str(pattern.pattern),
                "url_name": pattern.name,
                "methods": sorted(
                    method for method in ("get", "post", "patch", "put", "delete")
                    if hasattr(view, method)
                ),
                "capability": getattr(view, "capability", ""),
                "capabilities": tuple(getattr(view, "queue_capabilities", ()) or ()),
                "capability_source": (
                    "queue_capabilities" if getattr(view, "queue_capabilities", None)
                    else "capability"
                ),
                "serializer": getattr(view, "serializer_class", None).__name__
                if getattr(view, "serializer_class", None) else "",
            })

    all_text = "\n".join(sources.values())
    commands = []
    for cid, row in sorted(registry.items()):
        if cid in retired:
            continue
        views_raw = idempotency_views.get(cid, [])
        views = list({view["view"]: view for view in views_raw}.values())
        owner = row["module"].split(".")[-1]
        owner_text = "\n".join(
            source for path, source in sources.items() if f"/{owner}/" in path
        )
        service_tokens = re.findall(r"\b(?:application|patients|scheduling|clinical|laboratory|pharmacy|inventory|billing|core|tenancy|audit|reporting)\.[a-z0-9_.]+\.[a-z][a-z0-9_]*", row["owner_services"])
        service_checks = []
        for token in service_tokens:
            function = token.rsplit(".", 1)[-1]
            service_checks.append({
                "token": token,
                "function": function,
                "defined": bool(re.search(rf"\bdef\s+{re.escape(function)}\s*\(", all_text)),
                "called": bool(re.search(rf"\b{re.escape(function)}\s*\(", all_text)),
            })
        missing_audit = [
            code for code in row["audit_codes"]
            if code not in all_text
        ]
        missing_errors = [
            code for code in row["error_codes"]
            if code not in all_text
        ]
        test_pointer = s16_pointer.get(cid, "")
        test_text = ""
        if test_pointer and (ROOT / test_pointer).exists():
            test_text = (ROOT / test_pointer).read_text(encoding="utf-8")
        distinctive = set()
        for view in views:
            for segment in view["url"].split("/"):
                if segment and not segment.startswith("<") and segment not in {"api", "v1"} and len(segment) >= 5:
                    distinctive.add(segment.strip("/"))
        test_ref = bool(
            test_text and (
                row["operation"] in test_text
                or cid in test_text
                or (len(distinctive) >= 2 and sum(1 for token in distinctive if token in test_text) >= 2)
            )
        )
        declared_capability = row["declared_capability"]
        capability_match = bool(views) and all(
            view["capability"] == declared_capability for view in views
        ) if declared_capability else None
        method_match = bool(views) and all(
            row["http_method"].lower() in view["methods"] for view in views
        )

        # Initial heuristic verdict; the manual pass below can downgrade/upgrade.
        if row["declared_fenced"] or s16_status.get(cid) == "FENCED":
            verdict = "FENCED"
            discrepancy = "Registry/slice authority fence active; no implementation claim."
        elif row["internal"]:
            if service_checks and all(check["defined"] for check in service_checks):
                if all(check["called"] for check in service_checks):
                    verdict = "PARTIAL"
                    discrepancy = "INTERNAL step: service function defined and called; parent CMD call site requires manual confirmation."
                else:
                    verdict = "PARTIAL"
                    discrepancy = "INTERNAL step: service function defined but not found as a call; parent wiring unproven."
            else:
                verdict = "FENCED"
                discrepancy = "INTERNAL step: declared service function not found."
        elif not views:
            verdict = "FENCED"
            discrepancy = "No view declares this CMD id; no HTTP route evidence."
        elif len(views) > 1:
            verdict = "MISMATCH"
            discrepancy = f"Multiple views declare this CMD id: {[v['view'] for v in views]}."
        elif not method_match:
            verdict = "MISMATCH"
            discrepancy = f"Declared {row['http_method']} but view methods are {views[0]['methods']}."
        elif missing_audit:
            verdict = "PARTIAL"
            discrepancy = f"Declared audit codes not found in code: {missing_audit}."
        elif not test_ref:
            verdict = "PARTIAL"
            discrepancy = "Slice test file does not name this CMD or operation; test exercise not proven mechanically."
        else:
            verdict = "VERIFIED"
            discrepancy = ""

        commands.append({
            **row,
            "slices": sorted(slices.get(cid, set())),
            "s16_status": s16_status.get(cid, ""),
            "s16_evidence_pointer": test_pointer,
            "views": views,
            "service_checks": service_checks,
            "missing_audit_codes": missing_audit,
            "missing_error_codes": missing_errors,
            "capability_match": capability_match,
            "method_match": method_match,
            "slice_test_references_command": test_ref,
            "verdict": verdict,
            "discrepancy": discrepancy,
            "evidence_pointer": test_pointer or "IMPLEMENTATION_BLUEPRINT.md",
        })

    summary = {
        "base": "54291e4",
        "generated_at": "2026-11-19",
        "active_commands": len(commands),
        "verdict_counts": dict(Counter(command["verdict"] for command in commands)),
        "retired_excluded": sorted(retired),
        "url_patterns": len(list(iter_urls())),
    }
    OUTPUT.write_text(
        json.dumps({"summary": summary, "commands": commands}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(summary)


if __name__ == "__main__":
    main()
