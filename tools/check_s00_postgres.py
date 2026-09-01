#!/usr/bin/env python3
"""Run direct application-role checks for the PostgreSQL S-00 proof surface."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


EXPECTED_MIGRATIONS = {
    ("core", "0003_s00_verification_foundation"),
    ("audit", "0002_s00_audit_facts"),
    ("tenancy", "0002_s00_facility_workflow_policy"),
}
EXPECTED_CONSTRAINTS = {
    ("core_idempotencyrecord", "uniq_idempotency_org_op_key_hash"),
    ("core_idempotencyrecord", "idempotency_status_code_valid"),
    ("core_idempotencyrecord", "idempotency_completed_has_status"),
    ("audit_auditevent", "uniq_audit_copy_event"),
    ("audit_auditevent", "uniq_audit_denial_identity"),
    ("tenancy_facilityworkflowpolicy", "uniq_workflow_policy_facility"),
    ("tenancy_facilityworkflowpolicy", "workflow_policy_options_are_arrays"),
    ("tenancy_facilityworkflowpolicy", "workflow_policy_queue_expiry_positive"),
    ("tenancy_facilityworkflowpolicy", "workflow_policy_no_show_attempts_positive"),
    ("tenancy_facilityworkflowpolicy", "workflow_policy_board_identity_valid"),
    ("tenancy_facilityworkflowpolicy", "workflow_policy_prescription_warning_positive"),
    ("tenancy_facilityworkflowpolicy", "workflow_policy_inventory_warning_positive"),
    ("tenancy_facilityworkflowpolicy", "workflow_policy_uncollected_window_positive"),
    ("tenancy_facilityworkflowpolicy", "workflow_policy_discount_threshold_nonnegative"),
    ("tenancy_facilityworkflowpolicy", "workflow_policy_variance_threshold_nonnegative"),
}


def _check_required_constraints(cursor, failures):
    for table, constraint in sorted(EXPECTED_CONSTRAINTS):
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = %s::regclass
                  AND conname = %s
            )
            """,
            [table, constraint],
        )
        if not cursor.fetchone()[0]:
            failures.append(f"{table}: required constraint {constraint} is missing")


def _check_backfill(cursor, failures):
    cursor.execute(
        """
        SELECT
            (SELECT count(*) FROM core_idempotencyrecord
             WHERE operation IS NULL OR operation = ''
                OR key_hash IS NULL OR key_hash = ''
                OR fingerprint IS NULL OR fingerprint = ''
                OR (completed_at IS NULL AND status_code IS NOT NULL)) AS incomplete_idempotency,
            (SELECT count(*) FROM audit_auditevent
             WHERE event_code IS NULL OR event_code = '') AS incomplete_audit
        """
    )
    incomplete_idempotency, incomplete_audit = cursor.fetchone()
    if incomplete_idempotency:
        failures.append(f"idempotency backfill is incomplete for {incomplete_idempotency} rows")
    if incomplete_audit:
        failures.append(f"audit event-code backfill is incomplete for {incomplete_audit} rows")


def main():
    if os.getenv("DB_ENGINE", "").lower() not in {"postgres", "postgresql"}:
        print("NOT EXECUTED: DB_ENGINE is not PostgreSQL.")
        return 2
    from core.rls import is_tenant_policy_expression

    connection = psycopg.connect(
        dbname=os.getenv("DB_NAME", "clinicopus"),
        user=os.getenv("DB_USER", "clinicopus_app"),
        password=os.getenv("DB_PASSWORD", "clinicopus_app_dev_only"),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
        autocommit=True,
    )
    failures = []
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT current_user, rolsuper, rolbypassrls, rolcreaterole,
                       rolcreatedb, rolcanlogin
                FROM pg_roles
                WHERE rolname = current_user
                """
            )
            role = cursor.fetchone()
            if role is None:
                failures.append("application role is not visible in pg_roles")
            else:
                if role[1] or role[2]:
                    failures.append(
                        f"unsafe application role attributes: superuser={role[1]} bypassrls={role[2]}"
                    )
                if not role[5]:
                    failures.append("application role is not LOGIN-enabled")

            cursor.execute(
                """
                SELECT DISTINCT table_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND column_name = 'organisation_id'
                ORDER BY table_name
                """
            )
            tables = [row[0] for row in cursor.fetchall()]
            if not tables:
                failures.append("no organisation-scoped tables found")
            for table in tables:
                cursor.execute(
                    """
                    SELECT c.relrowsecurity,
                           c.relforcerowsecurity,
                           COALESCE(pg_get_expr(p.polqual, p.polrelid), ''),
                           COALESCE(pg_get_expr(p.polwithcheck, p.polrelid), ''),
                           COALESCE(p.polcmd, ''),
                           COALESCE(p.polpermissive, TRUE),
                           pg_get_userbyid(c.relowner)
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    LEFT JOIN pg_policy p
                      ON p.polrelid = c.oid
                     AND p.polname = 'clinicopus_tenant_isolation'
                    WHERE n.nspname = 'public' AND c.relname = %s
                    """,
                    [table],
                )
                status = cursor.fetchone()
                policy_ok = bool(
                    status
                    and status[0]
                    and status[1]
                    and is_tenant_policy_expression(status[2])
                    and is_tenant_policy_expression(status[3])
                    and status[4] == "*"
                    and status[5] is True
                )
                owner_matches = bool(status) and role is not None and status[6] == role[0]
                if not policy_ok or owner_matches:
                    failures.append(f"{table}: missing ENABLE/FORCE or exact tenant policy semantics")
                try:
                    cursor.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier(table)))
                except psycopg.Error as error:
                    if error.sqlstate not in {"42704", "22P02"}:
                        failures.append(f"{table}: missing-context check returned SQLSTATE {error.sqlstate}")
                else:
                    failures.append(f"{table}: query succeeded without app.current_org_id")

            cursor.execute(
                """
                SELECT app, name
                FROM django_migrations
                WHERE (app = 'core' AND name = '0003_s00_verification_foundation')
                   OR (app = 'audit' AND name = '0002_s00_audit_facts')
                   OR (app = 'tenancy' AND name = '0002_s00_facility_workflow_policy')
                ORDER BY app, name
                """
            )
            applied = {(row[0], row[1]) for row in cursor.fetchall()}
            if applied != EXPECTED_MIGRATIONS:
                failures.append(
                    f"required S-00 migrations missing: {sorted(EXPECTED_MIGRATIONS - applied)}"
                )
            else:
                _check_required_constraints(cursor, failures)
                _check_backfill(cursor, failures)

            cursor.execute(
                """
                SELECT tgname
                FROM pg_trigger
                WHERE tgrelid = 'core_idempotencyrecord'::regclass
                  AND NOT tgisinternal
                """
            )
            if "clinicopus_idempotency_immutable" not in {row[0] for row in cursor.fetchall()}:
                failures.append("idempotency immutability trigger is missing")

            cursor.execute(
                """
                SELECT tgname
                FROM pg_trigger
                WHERE tgrelid = 'audit_auditevent'::regclass
                  AND NOT tgisinternal
                """
            )
            if "clinicopus_audit_immutable" not in {row[0] for row in cursor.fetchall()}:
                failures.append("audit immutability trigger is missing")

    connection.close()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("PASS: PostgreSQL application-role policy, scope, migration, backfill, constraint, and trigger proofs passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
