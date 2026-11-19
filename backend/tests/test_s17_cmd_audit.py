"""S-17 machine cross-checks for the CMD audit artifact."""

import json
import re
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DATA = ROOT / "docs/implementation/s17-cmd-audit.json"


def _url_map():
    from django.urls import get_resolver

    def walk(patterns, prefix=""):
        for pattern in patterns:
            if hasattr(pattern, "url_patterns"):
                yield from walk(pattern.url_patterns, prefix + str(pattern.pattern))
            else:
                yield pattern

    result = {}
    for pattern in walk(get_resolver().url_patterns):
        view = getattr(pattern.callback, "view_class", None)
        if view is None:
            continue
        name = f"{view.__module__}.{view.__name__}"
        result.setdefault(name, []).append(str(pattern.pattern))
    return result


def _audit():
    return json.loads(DATA.read_text(encoding="utf-8"))


def test_s17_inventory_is_complete_and_all_rows_have_verdicts():
    audit = _audit()
    commands = audit["commands"]
    ids = [command["id"] for command in commands]
    assert len(ids) == 134 == len(set(ids))
    assert {"CMD-097", "CMD-107"}.isdisjoint(ids)
    assert {f"CMD-{i:03d}" for i in range(1, 137)} - {"CMD-097", "CMD-107"} == set(ids)
    assert audit["summary"]["active_commands"] == 134
    for command in commands:
        assert command["verdict"] in {"VERIFIED", "PARTIAL", "MISMATCH", "FENCED"}, command["id"]
        assert command["evidence_pointer"], command["id"]
        if command["verdict"] in {"PARTIAL", "MISMATCH", "FENCED"}:
            assert command["discrepancy"], command["id"]


def test_s17_code_idempotency_labels_are_registered_or_documented_as_mismatch():
    audit = _audit()
    active = {command["id"] for command in audit["commands"]}
    labels = set()
    for path in BACKEND.rglob("*.py"):
        if "migrations" in path.parts or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        labels.update(re.findall(r'idempotency_operation\s*=\s*"([^"]+)"', text))
    unknown = labels - active
    assert unknown == {"inventory.stock_transfer"}, unknown
    mismatch = next(
        command for command in audit["commands"] if command["id"] == "CMD-064"
    )
    assert mismatch["verdict"] == "MISMATCH"
    assert "inventory.stock_transfer" in mismatch["discrepancy"]


def test_s17_declared_routes_and_methods_match_for_non_mismatch_commands():
    audit = _audit()
    urls = _url_map()
    for command in audit["commands"]:
        for view in command["views"]:
            assert view["view"] in urls, (command["id"], view["view"])
            assert urls[view["view"]], (command["id"], view["view"])
        if command["verdict"] != "MISMATCH" and command["views"]:
            assert command["method_match"] is not False, command["id"]
            for view in command["views"]:
                assert command["http_method"].lower() in view["methods"], (
                    command["id"], view["view"], command["http_method"], view["methods"]
                )


def test_s17_audit_codes_and_internal_steps_support_the_verdicts():
    audit = _audit()
    for command in audit["commands"]:
        if command["verdict"] == "VERIFIED":
            assert not command["missing_audit_codes"], command["id"]
        if command["missing_audit_codes"] and command["verdict"] != "FENCED":
            assert command["verdict"] in {"PARTIAL", "MISMATCH"}, command["id"]
        if command["internal"] and command["verdict"] != "MISMATCH":
            if not any(check["defined"] for check in command["service_checks"]):
                assert command["verdict"] == "FENCED", command["id"]


def test_s17_summary_and_report_counts_match_the_records():
    audit = _audit()
    expected = {
        verdict: sum(1 for command in audit["commands"] if command["verdict"] == verdict)
        for verdict in ("VERIFIED", "PARTIAL", "MISMATCH", "FENCED")
    }
    assert audit["summary"]["verdict_counts"] == expected
    assert audit["summary"]["severity_counts"] == {"P1": 18, "P2": 43}
    report = (ROOT / "docs/implementation/s17-cmd-audit.md").read_text(encoding="utf-8")
    assert "P1 18" in report
    assert "P2 43" in report
    for verdict, count in expected.items():
        assert f"{verdict} {count}" in report
    assert "P1 | CMD-042" in report
    assert "P1 | CMD-064" in report
