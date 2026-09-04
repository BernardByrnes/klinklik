#!/usr/bin/env python3
"""Assert the S-00 rollback contract without requiring the newest migrations."""

from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "clinicopus.settings")

import django

django.setup()

from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


REQUIRED_S00 = frozenset(
    {
        ("core", "0003_s00_verification_foundation"),
        ("audit", "0002_s00_audit_facts"),
        ("tenancy", "0002_s00_facility_workflow_policy"),
        ("clinical", "0008_s00_tenant_rls_repair"),
    }
)


def main() -> int:
    if connection.vendor != "postgresql":
        print("NOT EXECUTED: S-00 migration-state proof requires PostgreSQL.")
        return 2
    applied = MigrationRecorder(connection).applied_migrations()
    missing = sorted(REQUIRED_S00 - applied)
    if missing:
        for app, name in missing:
            print(f"FAIL: required S-00 migration is missing: {app}.{name}", file=sys.stderr)
        return 1

    print("PASS: required S-00 migrations are applied; newer S-01 migration state is intentionally not evaluated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
