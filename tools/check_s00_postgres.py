#!/usr/bin/env python3
"""Run direct application-role checks for the PostgreSQL S-00 proof surface."""

from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql


def main():
    if os.getenv("DB_ENGINE", "").lower() not in {"postgres", "postgresql"}:
        print("NOT EXECUTED: DB_ENGINE is not PostgreSQL.")
        return 2
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
                SELECT current_user, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb
                FROM pg_roles
                WHERE rolname = current_user
                """
            )
            role = cursor.fetchone()
            if role is None:
                failures.append("application role is not visible in pg_roles")
            elif role[1] or role[2]:
                failures.append(
                    f"unsafe application role attributes: superuser={role[1]} bypassrls={role[2]}"
                )

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
                               EXISTS (
                               SELECT 1
                               FROM pg_policies p
                               WHERE p.schemaname = 'public'
                                 AND p.tablename = c.relname
                                 AND p.policyname = 'clinicopus_tenant_isolation'
                                 AND p.qual::text LIKE '%%current_setting%%'
                                   AND p.with_check::text LIKE '%%current_setting%%'
                           ),
                           pg_get_userbyid(c.relowner)
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = %s
                    """,
                    [table],
                )
                status = cursor.fetchone()
                if (
                    not status
                    or not all(status[:3])
                    or (role is not None and status[3] == role[0])
                ):
                    failures.append(f"{table}: missing ENABLE/FORCE tenant policy")
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
            expected = {
                ("core", "0003_s00_verification_foundation"),
                ("audit", "0002_s00_audit_facts"),
                ("tenancy", "0002_s00_facility_workflow_policy"),
            }
            if applied != expected:
                failures.append(f"required S-00 migrations missing: {sorted(expected - applied)}")

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

    connection.close()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("PASS: PostgreSQL application-role RLS, missing-context, migration, and trigger proofs passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
