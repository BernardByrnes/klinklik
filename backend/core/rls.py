from django.db import connection


def rls_status():
    if connection.vendor != "postgresql":
        return {"backend": connection.vendor, "enforced": False, "reason": "PostgreSQL required"}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT relation.relname,
                   relation.relrowsecurity,
                   relation.relforcerowsecurity,
                   EXISTS (
                       SELECT 1
                       FROM pg_policies policy
                       WHERE policy.schemaname = 'public'
                         AND policy.tablename = relation.relname
                         AND policy.policyname = 'clinicopus_tenant_isolation'
                   ) AS has_tenant_policy
            FROM pg_class relation
            JOIN pg_namespace namespace
              ON namespace.oid = relation.relnamespace
            WHERE namespace.nspname = 'public'
              AND relation.relkind = 'r'
              AND EXISTS (
                  SELECT 1
                  FROM information_schema.columns column_info
                  WHERE column_info.table_schema = 'public'
                    AND column_info.table_name = relation.relname
                    AND column_info.column_name = 'organisation_id'
              )
            ORDER BY relation.relname
            """
        )
        rows = cursor.fetchall()
    return {
        "backend": connection.vendor,
        "enforced": bool(rows) and all(row[1] and row[2] and row[3] for row in rows),
        "tables": [
            {
                "name": row[0],
                "rowsecurity": row[1],
                "force": row[2],
                "tenant_policy": row[3],
            }
            for row in rows
        ],
    }
