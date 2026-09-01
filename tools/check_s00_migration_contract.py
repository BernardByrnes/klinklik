#!/usr/bin/env python3
"""Assert the explicit S-00 migration reversibility contract."""

from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def _qualified_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _tree(relative_path):
    path = ROOT / relative_path
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _has_function(tree, name):
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        for node in ast.walk(tree)
    )


def _has_run_python(tree, forward, reverse):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _qualified_name(node.func) != "migrations.RunPython":
            continue
        if len(node.args) >= 2 and (
            _qualified_name(node.args[0]) == forward
            and _qualified_name(node.args[1]) == reverse
        ):
            return True
    return False


def _has_operation(tree, operation, *, name=None):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _qualified_name(node.func) != f"migrations.{operation}":
            continue
        if name is None:
            return True
        for keyword in node.keywords:
            if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                if keyword.value.value == name:
                    return True
    return False


def _has_dependency(tree, app, migration):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Tuple) or len(node.elts) != 2:
            continue
        if all(isinstance(element, ast.Constant) for element in node.elts):
            if node.elts[0].value == app and node.elts[1].value == migration:
                return True
    return False


def main():
    failures = []

    core = _tree("backend/core/migrations/0003_s00_verification_foundation.py")
    audit = _tree("backend/audit/migrations/0002_s00_audit_facts.py")
    tenancy = _tree("backend/tenancy/migrations/0002_s00_facility_workflow_policy.py")
    clinical_repair = _tree("backend/clinical/migrations/0008_s00_tenant_rls_repair.py")

    core_expectations = (
        ("core.0003 must define an explicit no-op data reverse", _has_function(core, "noop_reverse")),
        (
            "core.0003 must declare its idempotency backfill as data-irreversible",
            _has_run_python(core, "backfill_idempotency_identity", "noop_reverse"),
        ),
        (
            "core.0003 must retain the raw key removal",
            _has_operation(core, "RemoveField", name="key"),
        ),
        (
            "core.0003 must retain the request-hash removal",
            _has_operation(core, "RemoveField", name="request_hash"),
        ),
        (
            "core.0003 must retain a reversible trigger operation",
            _has_run_python(core, "apply_immutability_trigger", "reverse_immutability_trigger"),
        ),
    )
    for message, condition in core_expectations:
        if not condition:
            failures.append(message)

    reversible_expectations = (
        (
            "audit.0002 must retain its declared backfill reverse",
            _has_run_python(audit, "backfill_event_codes", "noop_reverse"),
        ),
        (
            "tenancy.0002 must retain its reversible PostgreSQL guards",
            _has_run_python(tenancy, "apply_postgres_guards", "reverse_postgres_guards"),
        ),
    )
    for message, condition in reversible_expectations:
        if not condition:
            failures.append(message)

    repair_expectations = (
        (
            "clinical.0008 must define the late-table tenant RLS repair",
            _has_function(clinical_repair, "apply_tenant_rls_repair"),
        ),
        (
            "clinical.0008 must declare a reversible RLS repair",
            _has_run_python(
                clinical_repair,
                "apply_tenant_rls_repair",
                "reverse_tenant_rls_repair",
            ),
        ),
        (
            "clinical.0008 must run after core.0003",
            _has_dependency(
                clinical_repair,
                "core",
                "0003_s00_verification_foundation",
            ),
        ),
    )
    for message, condition in repair_expectations:
        if not condition:
            failures.append(message)

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(
        "PASS: core.0003 is forward-required/data-irreversible; "
        "audit.0002 and tenancy.0002 retain declared reverse behavior."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
