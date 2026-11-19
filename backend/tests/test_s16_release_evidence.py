"""S-16 release-evidence contract assertions (machine-checkable)."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs/implementation/s16-contract-verification.json"
REPORT = ROOT / "docs/implementation/s16-contract-verification.md"

ACTIVE_PC = {f"PC-{i:03d}" for i in range(1, 82)} - {"PC-061"}
ACTIVE_CMD = {f"CMD-{i:03d}" for i in range(1, 137)} - {"CMD-097", "CMD-107"}
ACTIVE_MIG = {f"MIG-{i:03d}" for i in range(1, 12)}
ACTIVE_ADR = {f"ADR-C-{i:02d}" for i in range(1, 15)}

FENCED_PC = {
    "PC-043", "PC-046", "PC-057", "PC-068", "PC-069", "PC-070",
    "PC-071", "PC-072", "PC-073", "PC-074", "PC-075",
}
PARTIAL_PC = {"PC-017", "PC-022", "PC-025", "PC-037", "PC-040", "PC-077", "PC-080"}
FENCED_CMD_REQUIRED = {
    "CMD-012", "CMD-055", "CMD-060", "CMD-061", "CMD-085",
    "CMD-086", "CMD-100", "CMD-103", "CMD-114", "CMD-120", "CMD-121",
    "CMD-122", "CMD-123", "CMD-125", "CMD-126",
}


def _records():
    return json.loads(DATA.read_text(encoding="utf-8"))["records"]


def test_s16_contract_families_are_complete_and_not_duplicated():
    records = _records()
    ids = [record["id"] for record in records]
    assert len(ids) == len(set(ids))
    families = {}
    for record in records:
        families.setdefault(record["family"], set()).add(record["id"])
    assert families["PC"] == ACTIVE_PC
    assert families["CMD"] == ACTIVE_CMD
    assert families["MIG"] == ACTIVE_MIG
    assert families["ADR"] == ACTIVE_ADR
    assert {"PC-061", "CMD-097", "CMD-107"}.isdisjoint(ids)


def test_s16_contract_status_map_matches_the_declared_evidence_classes():
    records = _records()
    statuses = {(record["family"], record["id"]): record["status"] for record in records}
    assert {key[1] for key, value in statuses.items() if value == "FENCED" and key[0] == "PC"} == FENCED_PC
    assert {key[1] for key, value in statuses.items() if value == "PARTIAL" and key[0] == "PC"} == PARTIAL_PC
    assert FENCED_CMD_REQUIRED <= {
        key[1] for key, value in statuses.items() if value == "FENCED"
    }
    assert sum(1 for key, value in statuses.items() if key[0] == "CMD" and value == "EVIDENCE LINKED") == 103
    assert sum(1 for key, value in statuses.items() if key[0] == "CMD" and value == "FENCED") == 30
    assert sum(1 for key, value in statuses.items() if key[0] == "CMD" and value == "PARTIAL") == 1
    assert sum(1 for key, value in statuses.items() if key[0] == "PC" and value == "IMPLEMENTED") == 62
    assert sum(1 for key, value in statuses.items() if key[0] == "MIG" and value == "IMPLEMENTED") == 11
    assert sum(1 for key, value in statuses.items() if key[0] == "ADR" and value == "SETTLED") == 14


def test_s16_every_contract_has_an_existing_evidence_pointer():
    for record in _records():
        pointer = record["evidence"].split("#", 1)[0]
        assert pointer, record["id"]
        assert (ROOT / pointer).exists(), (record["id"], pointer)


def test_s16_markdown_report_matches_the_machine_data():
    report = REPORT.read_text(encoding="utf-8")
    assert "| PC | 80 |" in report
    assert "| CMD | 134 |" in report
    assert "| MIG | 11 |" in report
    assert "| ADR | 14 |" in report
    table_rows = {
        family: sum(1 for line in report.splitlines() if line.startswith(f"| {family}-"))
        for family in ("PC", "CMD", "MIG", "ADR")
    }
    assert table_rows == {"PC": 80, "CMD": 134, "MIG": 11, "ADR": 14}


def test_s16_dossier_states_scope_and_non_authorization():
    dossier = (ROOT / "docs/release/v1-evidence.md").read_text(encoding="utf-8")
    assert "Deployment is not authorized" in dossier
    assert "J-05 ANC" in dossier
    assert "440 passed, 92 skipped" in dossier
    assert "102,184 bytes" in dossier
    assert "S-12 CMD idempotency labels were mismatched with the registry — FIXED" in dossier
    assert "evidence index, not a branch-by-branch contract audit" in dossier
    assert "Plan-16 scope gaps" in dossier


def test_s16_pharmacy_views_use_the_registry_command_identifiers():
    from pharmacy.views import (
        DispenseConfirmView,
        DispensePrepareView,
        OTCSaleCreateView,
        PrescriptionCancelView,
        PrescriptionClaimView,
        PrescriptionDraftView,
        PrescriptionItemNotDispensedView,
        ProductInstructionTemplateView,
    )

    expected = {
        PrescriptionDraftView: "CMD-052",
        PrescriptionClaimView: "CMD-124",
        DispensePrepareView: "CMD-056",
        DispenseConfirmView: "CMD-058",
        PrescriptionCancelView: "CMD-054",
        PrescriptionItemNotDispensedView: "CMD-115",
        ProductInstructionTemplateView: "CMD-110",
        OTCSaleCreateView: "CMD-062",
    }
    for view, command_id in expected.items():
        assert view.idempotency_operation == command_id, view.__name__
    assert "CMD-113" not in {view.idempotency_operation for view in expected}
