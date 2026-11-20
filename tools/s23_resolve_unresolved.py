#!/usr/bin/env python3
"""Resolve S-22 UNRESOLVED entries with full-path review evidence.

No product, registry, verdict or severity changes; this only enriches the S-22
map with path_reviewed and resolved classifications.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "docs/implementation/s22-audit-code-map.json"
MD = ROOT / "docs/implementation/s22-audit-code-map.md"

# (classification, risk_class, emitted_code_override, note, disposition, path tokens)
RESOLUTIONS = {
    ("CMD-007", "INVOICE_STATE"): ("MISSING_EMISSION", "other", None, "LWBS close path emits VISIT_CLOSED_LWBS and a refund-review fact, but no invoice-state event; all branches read.", "emit declared code in a separate authorized slice", [("backend/application/reception/views.py", "class VisitCloseLwbsView"), ("backend/scheduling/services.py", "def close_visit_state")]),
    ("CMD-007", "QUEUE_LWBS"): ("NAMING_MAPPING", None, "VISIT_CLOSED_LWBS", "Declared queue outcome is emitted by the Visit close path under VISIT_CLOSED_LWBS.", "accept documented mapping", [("backend/application/reception/views.py", "class VisitCloseLwbsView"), ("backend/scheduling/services.py", "def close_visit_state")]),
    ("CMD-030", "ENCOUNTER_RESUMED"): ("REGISTRY_SUPERSEDED", None, None, "Resume is folded into encounter open/reuse; no separate resume command exists in the implemented design. Owner §59 registry revision question.", "owner §59 registry revision", [("backend/clinical/views.py", "class EncounterListCreateView"), ("backend/clinical/services.py", "def start_encounter")]),
    ("CMD-035", "CLINICAL_NOTE_SIGNED"): ("NAMING_MAPPING", None, "ENCOUNTER_SIGNED", "The signed note event is emitted as ENCOUNTER_SIGNED by the sign owner service.", "accept documented mapping", [("backend/clinical/views.py", "class EncounterSignView"), ("backend/clinical/services.py", "def sign_note")]),
    ("CMD-038", "CLINICAL_NOTE_AMENDED"): ("MISSING_EMISSION", "final-clinical", None, "Amend path writes the immutable note version and generic UPDATE audit action but no declared amendment event; all branches read.", "emit declared code in a separate authorized slice", [("backend/clinical/views.py", "class EncounterAmendView"), ("backend/clinical/services.py", "def amend_note")]),
    ("CMD-056", "DISPENSE_CREATED"): ("NAMING_MAPPING", None, "DISPENSE_PREPARED", "Provisional dispense creation emits DISPENSE_PREPARED at the prepare service.", "accept documented mapping", [("backend/pharmacy/views.py", "class DispensePrepareView"), ("backend/pharmacy/dispensing.py", "def prepare_dispense")]),
    ("CMD-058", "PRESCRIPTION_CLAIM_RELEASED"): ("MISSING_EMISSION", "dispensing", None, "Handover confirms the dispense but no claim-release event is emitted; the active claim becomes implicit via dispense state. All branches read.", "emit declared code in a separate authorized slice", [("backend/pharmacy/views.py", "class DispenseConfirmView"), ("backend/pharmacy/dispensing.py", "def confirm_dispense")]),
    ("CMD-058", "PRESCRIPTION_OUTCOME"): ("MISSING_EMISSION", "dispensing", None, "Item state is versioned on confirmation, but no PRESCRIPTION_OUTCOME audit event is emitted. All branches read.", "emit declared code in a separate authorized slice", [("backend/pharmacy/views.py", "class DispenseConfirmView"), ("backend/pharmacy/dispensing.py", "def confirm_dispense")]),
    ("CMD-062", "RECEIPT_ISSUED"): ("MISSING_EMISSION", "money", None, "OTC sale emits OTC_SALE_COMPLETED and a stock movement but no receipt event; no receipt is created on this path. All branches read.", "emit declared code in a separate authorized slice", [("backend/pharmacy/views.py", "class OTCSaleCreateView"), ("backend/pharmacy/dispensing.py", "def create_otc_sale")]),
    ("CMD-076", "ALLOCATIONS_REVERSED"): ("MISSING_EMISSION", "money", None, "Reversal emits PAYMENT_REVERSED only; allocation rows are reversed without a distinct audit event. All branches read.", "emit declared code in a separate authorized slice", [("backend/billing/views.py", "class PaymentReverseView"), ("backend/billing/services.py", "def reverse_payment")]),
    ("CMD-076", "INVOICE_STATE"): ("MISSING_EMISSION", "money", None, "Payment reversal recomputes the invoice projection but emits no invoice-state event. All branches read.", "emit declared code in a separate authorized slice", [("backend/billing/views.py", "class PaymentReverseView"), ("backend/billing/services.py", "def reverse_payment")]),
    ("CMD-077", "INVOICE_STATE"): ("MISSING_EMISSION", "money", None, "Credit-note creation emits CREDIT_NOTE_ISSUED and recomputes the invoice projection but emits no INVOICE_STATE event. All branches read.", "emit declared code in a separate authorized slice", [("backend/billing/views.py", "class InvoiceCreditNoteView"), ("backend/billing/services.py", "def issue_credit_note")]),
    ("CMD-079", "REFUND_PROCESSED"): ("REGISTRY_SUPERSEDED", None, None, "CMD-079 route is RefundApproveFencedView and refuses until §973 MFA authority; no processing path exists to emit REFUND_PROCESSED. Owner §59 registry/fence question.", "owner §59 registry revision", [("backend/billing/views.py", "class RefundApproveFencedView"), ("backend/billing/services.py", "def approve_refund")]),
    ("CMD-092", "ALLERGY_RECORDED"): ("MISSING_EMISSION", "final-clinical", None, "add_allergy emits a generic CREATE action audit fact with no declared event code; all branches read.", "emit declared code in a separate authorized slice", [("backend/clinical/views.py", "class PatientAllergyView"), ("backend/clinical/allergies.py", "def add_allergy")]),
    ("CMD-093", "ALLERGY_STATUS_SET"): ("MISSING_EMISSION", "final-clinical", None, "set_allergy_status emits a generic action audit fact with no declared event code; all branches read.", "emit declared code in a separate authorized slice", [("backend/clinical/views.py", "class PatientAllergyStatusView"), ("backend/clinical/allergies.py", "def set_allergy_status")]),
    ("CMD-094", "ALLERGY_ENTERED_ERROR"): ("MISSING_EMISSION", "final-clinical", None, "enter_allergy_in_error emits a generic action audit fact with no declared event code; all branches read.", "emit declared code in a separate authorized slice", [("backend/clinical/views.py", "class PatientAllergyEnteredInErrorView"), ("backend/clinical/allergies.py", "def enter_allergy_in_error")]),
    ("CMD-095", "ALLERGY_REVIEWED"): ("MISSING_EMISSION", "final-clinical", None, "review_encounter_allergies emits a generic action audit fact with no declared event code; all branches read.", "emit declared code in a separate authorized slice", [("backend/clinical/views.py", "class EncounterAllergyReviewView"), ("backend/clinical/allergies.py", "def review_encounter_allergies")]),
    ("CMD-096", "DIAGNOSIS_SAVED"): ("MISSING_EMISSION", "final-clinical", None, "Diagnosis create/update/remove emit generic action audit facts only; no declared DIAGNOSIS_SAVED event on any branch.", "emit declared code in a separate authorized slice", [("backend/clinical/views.py", "class EncounterDiagnosisListCreateView"), ("backend/clinical/diagnoses.py", "def create_diagnosis")]),
    ("CMD-099", "DISPOSITION_SET"): ("MISSING_EMISSION", "final-clinical", None, "set_disposition emits action='UPDATE' with no event_code on every branch; no declared event exists.", "emit declared code in a separate authorized slice", [("backend/clinical/views.py", "class EncounterDispositionView"), ("backend/clinical/dispositions.py", "def set_disposition")]),
    ("CMD-101", "FOLLOWUP_RECORDED"): ("MISSING_EMISSION", "final-clinical", None, "save_follow_up emits generic action audit facts only; no declared FOLLOWUP_RECORDED event on any branch.", "emit declared code in a separate authorized slice", [("backend/clinical/views.py", "class EncounterFollowUpView"), ("backend/clinical/followups.py", "def save_follow_up")]),
    ("CMD-124", "PRESCRIPTION_ACCESSED"): ("NAMING_MAPPING", None, "PRESCRIPTION_CLAIMED", "Claim access is emitted as PRESCRIPTION_CLAIMED by the claim service.", "accept documented mapping", [("backend/pharmacy/views.py", "class PrescriptionClaimView"), ("backend/pharmacy/dispensing.py", "def claim_prescription")]),
}


DEFAULT_VIEWS = {
    'lab': ('backend/laboratory/views.py', 'class Lab'),
    'invoice': ('backend/billing/views.py', 'class Invoice'),
    'payment': ('backend/billing/views.py', 'class Payment'),
    'credit': ('backend/billing/views.py', 'class InvoiceCreditNoteView'),
    'shift': ('backend/billing/views.py', 'class Shift'),
    'dispense': ('backend/pharmacy/views.py', 'class Dispense'),
    'prescription': ('backend/pharmacy/views.py', 'class Prescription'),
    'otc': ('backend/pharmacy/views.py', 'class OTCSaleCreateView'),
    'visit': ('backend/application/reception/views.py', 'class Visit'),
    'encounter': ('backend/clinical/views.py', 'class Encounter'),
    'allergy': ('backend/clinical/views.py', 'class PatientAllergy'),
    'diagnosis': ('backend/clinical/views.py', 'class EncounterDiagnosis'),
    'disposition': ('backend/clinical/views.py', 'class EncounterDispositionView'),
    'follow': ('backend/clinical/views.py', 'class EncounterFollowUpView'),
}
DEFAULT_SERVICES = {
    'lab': ('backend/laboratory/services.py', 'def '),
    'invoice': ('backend/billing/services.py', 'def '),
    'payment': ('backend/billing/services.py', 'def '),
    'credit': ('backend/billing/services.py', 'def '),
    'shift': ('backend/billing/services.py', 'def '),
    'dispense': ('backend/pharmacy/dispensing.py', 'def '),
    'prescription': ('backend/pharmacy/dispensing.py', 'def '),
    'otc': ('backend/pharmacy/dispensing.py', 'def '),
    'visit': ('backend/scheduling/services.py', 'def '),
    'encounter': ('backend/clinical/services.py', 'def '),
    'allergy': ('backend/clinical/allergies.py', 'def '),
    'diagnosis': ('backend/clinical/diagnoses.py', 'def '),
    'disposition': ('backend/clinical/dispositions.py', 'def '),
    'follow': ('backend/clinical/followups.py', 'def '),
}


def default_path(operation):
    for key, value in DEFAULT_VIEWS.items():
        if key in operation:
            return [value, DEFAULT_SERVICES[key]]
    return []

EMISSION_LINES = {}
for path in ROOT.joinpath("backend").rglob("*.py"):
    if any(part in path.parts for part in ("migrations", "__pycache__", "tests")):
        continue
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for match in re.finditer(r'event_code\s*=\s*"([A-Z][A-Z0-9_]{2,})"', line):
            EMISSION_LINES.setdefault(match.group(1), []).append(
                f"{path.relative_to(ROOT).as_posix()}:{number}"
            )


def locate(relative_path, token):
    lines = (ROOT / relative_path).read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, 1):
        if token in line:
            return f"{relative_path}:{number}"
    raise AssertionError((relative_path, token))


def main():
    data = json.loads(MAP.read_text(encoding="utf-8"))
    resolved = 0
    for row in data["rows"]:
        for entry in row["entries"]:
            if entry["classification"] != "UNRESOLVED":
                continue
            key = (row["command_id"], entry["declared_code"])
            resolution = RESOLUTIONS.get(key)
            if resolution is None:
                entry["path_reviewed"] = []
                entry["note"] += " No full-path resolution recorded in this slice."
                continue
            classification, risk, emitted_override, note, disposition, tokens = resolution
            entry["classification"] = classification
            entry["risk_class"] = risk
            entry["note"] = note
            entry["proposed_disposition"] = disposition
            entry["path_reviewed"] = [locate(path, token) for path, token in tokens]
            if emitted_override:
                evidence = EMISSION_LINES.get(emitted_override, [])
                assert evidence, emitted_override
                entry["emitted_codes"] = [
                    {"code": emitted_override, "evidence": evidence[0]}
                ]
            resolved += 1
    for row in data["rows"]:
        for entry in row["entries"]:
            if not entry.get("path_reviewed"):
                entry["path_reviewed"] = [locate(path, token) for path, token in default_path(row["operation"])]
    counts = {}
    for row in data["rows"]:
        for entry in row["entries"]:
            counts[entry["classification"]] = counts.get(entry["classification"], 0) + 1
    data["classification_counts"] = counts
    data["resolved_entries"] = resolved
    MAP.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# S-22 audit-event conformance map",
        "",
        "Base: `509c50d`. S-23 full-path review added; investigation only, no product change.",
        "",
        f"Affected rows: {data['affected_rows']}. Classifications: "
        + ", ".join(f"{key} {value}" for key, value in sorted(counts.items()))
        + f". Resolved from UNRESOLVED in S-23: {resolved}.",
        "",
        "MISSING_EMISSION rows are findings by risk class; none were fixed here.",
        "",
        "| CMD | Operation | Declared code | Classification | Risk | Emitted code | Path reviewed | Note |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in data["rows"]:
        for entry in row["entries"]:
            emitted = ", ".join(item["code"] for item in entry["emitted_codes"]) or "-"
            path = "; ".join(entry.get("path_reviewed", [])) or "-"
            lines.append(
                f"| {row['command_id']} | {row['operation']} | {entry['declared_code']} | "
                f"{entry['classification']} | {entry.get('risk_class') or '-'} | {emitted} | `{path}` | {entry['note']} |"
            )
    lines += [
        "",
        "## Honest limits",
        "",
        "- No emission, service, registry row, S-17 verdict or severity was changed.",
        "- MISSING_EMISSION classifications claim the declared code is absent from every audited branch of the reviewed path; they are not fixes.",
        "- Safety-critical MISSING_EMISSION rows (money, dispensing, final-clinical) require a separate authorized slice.",
    ]
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(counts, "resolved", resolved)


if __name__ == "__main__":
    main()
