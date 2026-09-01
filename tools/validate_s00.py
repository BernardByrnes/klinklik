#!/usr/bin/env python3
"""Deterministic validation of the frozen S-00 authority and trace artifact."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path


EXPECTED_HASHES = {
    "PROJECT_SPEC.md": "B1B67A2D14A378ACB0C82A49D0EBA983302D1086BD2C39C2D4AE5154EB175738",
    "IMPLEMENTATION_BLUEPRINT.md": "BAAF3ADC17FC3099F81CC485684BD090752A2497E9EBC6A3081C8A1F5311EED8",
    "blueprint-validation/TRACEABILITY.csv": (
        "F8C54261F8EE7E2950BA0E78987DB5FE7E3A8AECAF07B8BC16B2D7E253CE0341"
    ),
    "blueprint-validation/TRACEABILITY.md": (
        "35DF526D4079781288449DEDB68BEEA359000C5F9B11CF0EA7E2465F9CAD6280"
    ),
}

TRACE_FIELDS = [
    "story_id",
    "ac_id",
    "release",
    "owner_app",
    "owner_service",
    "application_command_id",
    "state_machine_ids",
    "cmc_ids",
    "trust_invariant_ids",
    "gsc_ids",
    "api_operation",
    "required_test_layers",
    "postgres_gate_ids",
    "product_blocker_ids",
    "product_authority_status",
    "blueprint_implementation_status",
    "blueprint_section",
    "implementation_slice_id",
    "coverage_status",
    "notes",
]

STORY_PATTERN = re.compile(
    r"(?m)^\*\*((?:ANC|BIL|DSP|DX|ENC|INV|LAB|PAY|PHM|QUE|RCP|REC|RX|TRI)-\d{3})\s+·"
)
AC_PATTERN = re.compile(
    r"\b((?:ANC|BIL|DSP|DX|ENC|INV|LAB|PAY|PHM|QUE|RCP|REC|RX|TRI)-\d{3}-AC\d{2})\b"
)
REFERENCE_PATTERNS = [
    re.compile(r"\bCMD-\d{3}\b"),
    re.compile(r"\bPC-\d{3}\b"),
    re.compile(r"\bQRY-\d{3}\b"),
    re.compile(r"\bMIG-\d{3}\b"),
    re.compile(r"\bSM-\d{2}\b"),
    re.compile(r"\bCMC-\d{2}\b"),
    re.compile(r"\bTI-\d{2}\b"),
    re.compile(r"\bGSC-\d+\b"),
    re.compile(r"\bPG-G\d+\b"),
    re.compile(r"\bBP-BL-\d+\b"),
    re.compile(r"\bS-\d{2}\b"),
    re.compile(r"\bADR-C-\d{2}\b"),
    re.compile(r"\b(?:AUDITED-READ|DENIAL-AUDIT|LOCK)-\d{2}\b"),
]
FIELD_REFERENCE_PATTERNS = {
    "application_command_id": re.compile(r"CMD-\d{3}"),
    "state_machine_ids": re.compile(r"SM-\d{2}"),
    "cmc_ids": re.compile(r"CMC-\d{2}"),
    "trust_invariant_ids": re.compile(r"TI-\d{2}"),
    "gsc_ids": re.compile(r"GSC-\d+"),
    "postgres_gate_ids": re.compile(r"PG-G\d+"),
    "product_blocker_ids": re.compile(r"BP-BL-\d+"),
}


class Validator:
    def __init__(self, root: Path):
        self.root = root
        self.failures: list[str] = []

    def require(self, condition, message):
        if not condition:
            self.failures.append(message)

    def read(self, relative):
        path = self.root / relative
        try:
            return path.read_bytes()
        except OSError as exc:
            self.failures.append(f"{relative}: inaccessible ({exc})")
            return b""

    def validate_hashes(self):
        for relative, expected in EXPECTED_HASHES.items():
            data = self.read(relative)
            if not data:
                continue
            actual = hashlib.sha256(data).hexdigest().upper()
            self.require(actual == expected, f"{relative}: SHA-256 {actual}, expected {expected}")

    def validate_inventory(self, product_text, rows):
        stories = set(STORY_PATTERN.findall(product_text))
        acceptance_criteria = set(AC_PATTERN.findall(product_text))
        row_stories = [row.get("story_id", "") for row in rows]
        row_acs = [row.get("ac_id", "") for row in rows]
        self.require(stories, "PROJECT_SPEC.md: no canonical story headings found.")
        self.require(acceptance_criteria, "PROJECT_SPEC.md: no canonical acceptance criteria found.")
        self.require(
            len(row_acs) == len(set(row_acs)),
            "TRACEABILITY.csv: duplicate story/AC row.",
        )
        self.require(set(row_stories) == stories, "TRACEABILITY.csv: story inventory differs from Product Spec.")
        self.require(set(row_acs) == acceptance_criteria, "TRACEABILITY.csv: AC inventory differs from Product Spec.")
        for row_number, row in enumerate(rows, start=2):
            self.require(
                row["ac_id"].startswith(row["story_id"] + "-"),
                f"TRACEABILITY.csv:{row_number}: AC is not owned by its story.",
            )

    def validate_rows(self, rows, source_text):
        for row_number, row in enumerate(rows, start=2):
            self.require(
                None not in row,
                f"TRACEABILITY.csv:{row_number}: extra columns are present.",
            )
            for field in TRACE_FIELDS:
                self.require(
                    bool(row.get(field, "").strip()),
                    f"TRACEABILITY.csv:{row_number}: blank required field {field}.",
                )
            self.require(
                row.get("release") == "V1",
                f"TRACEABILITY.csv:{row_number}: release must be V1.",
            )
            authority = row.get("product_authority_status")
            coverage = row.get("coverage_status")
            expected_coverage = {
                "SUPPLIED": "COVERED",
                "PARTIALLY_BLOCKED": "COVERED_PARTIAL_BLOCK",
                "BLOCKED": "COVERED_BLOCKED",
            }.get(authority)
            self.require(
                expected_coverage == coverage,
                f"TRACEABILITY.csv:{row_number}: status/coverage pair is invalid.",
            )
            self.require(
                row.get("blueprint_implementation_status")
                == "FROZEN_BLUEPRINT_SLICE_AUTHORIZATION_REQUIRED",
                f"TRACEABILITY.csv:{row_number}: implementation status is not frozen.",
            )
            self.require(
                all(
                    re.fullmatch(r"S-(?:0[1-9]|1[0-4])", value)
                    for value in row.get("implementation_slice_id", "").split("|")
                ),
                f"TRACEABILITY.csv:{row_number}: invalid implementation slice.",
            )
            for field, pattern in FIELD_REFERENCE_PATTERNS.items():
                for value in row.get(field, "").split("|"):
                    if value == "N/A":
                        continue
                    self.require(
                        pattern.fullmatch(value) is not None and value in source_text,
                        f"TRACEABILITY.csv:{row_number}: invalid {field} reference {value}.",
                    )
            for pattern in REFERENCE_PATTERNS:
                for value in pattern.findall(row.get("blueprint_section", "")):
                    self.require(
                        value in source_text,
                        f"TRACEABILITY.csv:{row_number}: orphan Blueprint reference {value}.",
                    )

    def run(self):
        self.validate_hashes()
        product_data = self.read("PROJECT_SPEC.md")
        blueprint_data = self.read("IMPLEMENTATION_BLUEPRINT.md")
        trace_path = self.root / "blueprint-validation/TRACEABILITY.csv"
        rows = None
        try:
            with trace_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                self.require(
                    reader.fieldnames == TRACE_FIELDS,
                    f"TRACEABILITY.csv: headers differ from frozen contract: {reader.fieldnames}",
                )
        except OSError as exc:
            self.failures.append(f"TRACEABILITY.csv: inaccessible ({exc})")
        except (UnicodeError, csv.Error) as exc:
            self.failures.append(f"TRACEABILITY.csv: invalid UTF-8/CSV ({exc})")
        if rows is not None and product_data and blueprint_data:
            try:
                product_text = product_data.decode("utf-8")
                blueprint_text = blueprint_data.decode("utf-8")
            except UnicodeDecodeError as exc:
                self.failures.append(f"Frozen source: invalid UTF-8 ({exc})")
            else:
                source_text = product_text + "\n" + blueprint_text
                self.validate_inventory(product_text, rows)
                self.validate_rows(rows, source_text)
                self.require(
                    "Version | 1.0" in product_text and "FROZEN" in product_text,
                    "PROJECT_SPEC.md: frozen v1.0 control marker missing.",
                )
                self.require(
                    "Version | 1.0" in blueprint_text and "FROZEN" in blueprint_text,
                    "IMPLEMENTATION_BLUEPRINT.md: frozen v1.0 control marker missing.",
                )
        if self.failures:
            for failure in self.failures:
                print(f"FAIL: {failure}", file=sys.stderr)
            return 1
        print("PASS: S-00 frozen artifact hashes, source-derived inventory, and trace references validated.")
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    return Validator(args.root.resolve()).run()


if __name__ == "__main__":
    raise SystemExit(main())
