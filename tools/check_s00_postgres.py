#!/usr/bin/env python3
"""Run direct application-role checks for the PostgreSQL S-00 proof surface."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from uuid import UUID

import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


EXPECTED_MIGRATIONS = {
    ("core", "0003_s00_verification_foundation"),
    ("audit", "0002_s00_audit_facts"),
    ("tenancy", "0002_s00_facility_workflow_policy"),
    ("clinical", "0008_s00_tenant_rls_repair"),
}
PROOF_ORGANISATION_SLUG = "s00-backfill-clinic"
PROOF_IDEMPOTENCY_RECORD_ID = "00000000-0000-7000-8000-000000000002"
EXPECTED_CONSTRAINTS = {
    ("core_idempotencyrecord", "uniq_idempotency_org_op_key_hash"),
    ("core_idempotencyrecord", "idempotency_status_code_valid"),
    ("core_idempotencyrecord", "idempotency_completed_has_status"),
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
EXPECTED_PARTIAL_UNIQUE_INDEXES = {
    ("audit_auditevent", "uniq_audit_copy_event"): (
        ("organisation_id", "event_code", "entity_type", "entity_id", "copy_number"),
        "copy_number IS NOT NULL",
    ),
    ("audit_auditevent", "uniq_audit_denial_identity"): (
        ("organisation_id", "denial_identity"),
        "denial_identity IS NOT NULL",
    ),
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


def _normalize_sql_expression(expression):
    normalized = " ".join((expression or "").replace('"', "").lower().split())
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1].strip()
    return normalized


def _check_partial_unique_indexes(cursor, failures):
    for (table, index), (expected_columns, expected_predicate) in sorted(
        EXPECTED_PARTIAL_UNIQUE_INDEXES.items()
    ):
        cursor.execute(
            """
            SELECT
                index_class.relname,
                index_info.indisunique,
                ARRAY(
                    SELECT attribute.attname
                    FROM unnest(index_info.indkey) WITH ORDINALITY AS index_key(attnum, ordinality)
                    JOIN pg_attribute AS attribute
                      ON attribute.attrelid = index_info.indrelid
                     AND attribute.attnum = index_key.attnum
                    WHERE index_key.ordinality <= index_info.indnkeyatts
                    ORDER BY index_key.ordinality
                ) AS key_columns,
                pg_get_expr(index_info.indpred, index_info.indrelid) AS predicate,
                pg_get_indexdef(index_info.indexrelid) AS index_definition
            FROM pg_index AS index_info
            JOIN pg_class AS index_class
              ON index_class.oid = index_info.indexrelid
            JOIN pg_class AS table_class
              ON table_class.oid = index_info.indrelid
            JOIN pg_namespace AS namespace
              ON namespace.oid = table_class.relnamespace
            WHERE namespace.nspname = 'public'
              AND table_class.relname = %s
              AND index_class.relname = %s
            """,
            [table, index],
        )
        row = cursor.fetchone()
        if row is None:
            failures.append(f"{table}: required partial unique index {index} is missing")
            continue
        _, is_unique, key_columns, predicate, index_definition = row
        if not is_unique:
            failures.append(f"{table}: {index} is not UNIQUE")
        if tuple(key_columns or ()) != expected_columns:
            failures.append(
                f"{table}: {index} key columns are {tuple(key_columns or ())}, "
                f"expected {expected_columns}"
            )
        if _normalize_sql_expression(predicate) != _normalize_sql_expression(expected_predicate):
            failures.append(f"{table}: {index} predicate is not the declared partial predicate")
        if not index_definition:
            failures.append(f"{table}: {index} definition is missing")


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


def _proof_organisation_id(cursor, failures):
    cursor.execute(
        "SELECT id FROM tenancy_organisation WHERE slug = %s",
        [PROOF_ORGANISATION_SLUG],
    )
    row = cursor.fetchone()
    if row is None:
        failures.append("deterministic S-00 proof organisation is missing")
        return None
    return row[0]


def _classify_org_setting(value):
    if value is None:
        return "NULL"
    if value == "":
        return "EMPTY"
    try:
        UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return "NONEMPTY_OTHER"
    return "NONEMPTY_VALID_UUID"


def _check_unset_context_access(cursor, failures, label):
    cursor.execute("SELECT current_setting('app.current_org_id', true)")
    state = _classify_org_setting(cursor.fetchone()[0])
    if state in {"NONEMPTY_VALID_UUID", "NONEMPTY_OTHER"}:
        failures.append(f"{label}: organization context is active ({state})")

    try:
        cursor.execute(
            "SELECT id FROM core_idempotencyrecord WHERE id = %s",
            [PROOF_IDEMPOTENCY_RECORD_ID],
        )
    except psycopg.Error as error:
        if error.sqlstate not in {"42704", "22P02"}:
            failures.append(f"{label}: missing-context check returned SQLSTATE {error.sqlstate}")
    else:
        row = cursor.fetchone()
        if row is None:
            failures.append(f"{label}: protected proof row was not rejected")
        else:
            failures.append(f"{label}: protected proof row was readable")


def _check_scoped_backfill(connection, organisation_id, failures):
    # Keep the scoped backfill assertion separate from the unset-context proof.
    with connection.transaction():
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("SET LOCAL app.current_org_id = {}").format(
                    sql.Literal(str(organisation_id))
                )
            )
            _check_backfill(cursor, failures)

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org_id', true)")
        state = _classify_org_setting(cursor.fetchone()[0])
        if state in {"NONEMPTY_VALID_UUID", "NONEMPTY_OTHER"}:
            failures.append(f"scoped organization context leaked after backfill transaction ({state})")


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
                           pg_get_userbyid(c.relowner),
                           (SELECT count(*) FROM pg_policy AS all_policies
                            WHERE all_policies.polrelid = c.oid)
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
                    and status[7] == 1
                )
                owner_matches = bool(status) and role is not None and status[6] == role[0]
                if not policy_ok or owner_matches:
                    failures.append(f"{table}: missing ENABLE/FORCE or exact tenant policy semantics")

            cursor.execute(
                """
                SELECT app, name
                FROM django_migrations
                WHERE (app = 'core' AND name = '0003_s00_verification_foundation')
                   OR (app = 'audit' AND name = '0002_s00_audit_facts')
                   OR (app = 'tenancy' AND name = '0002_s00_facility_workflow_policy')
                   OR (app = 'clinical' AND name = '0008_s00_tenant_rls_repair')
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
                _check_partial_unique_indexes(cursor, failures)
                _check_unset_context_access(cursor, failures, "unset-context proof")
                proof_organisation_id = _proof_organisation_id(cursor, failures)
                if proof_organisation_id is not None:
                    _check_scoped_backfill(connection, proof_organisation_id, failures)
                    _check_unset_context_access(
                        cursor,
                        failures,
                        "post-SET-LOCAL unset-context proof",
                    )

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
