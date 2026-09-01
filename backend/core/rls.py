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
                   COALESCE(policy.qual::text, ''),
                   COALESCE(policy.with_check::text, ''),
                   pg_get_userbyid(relation.relowner)
            FROM pg_class relation
            JOIN pg_namespace namespace
              ON namespace.oid = relation.relnamespace
            LEFT JOIN pg_policies policy
              ON policy.schemaname = 'public'
             AND policy.tablename = relation.relname
             AND policy.policyname = 'clinicopus_tenant_isolation'
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
        cursor.execute(
            """
            SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb
            FROM pg_roles
            WHERE rolname = current_user
            """
        )
        role = cursor.fetchone()
    role_safe = bool(role) and not role[1] and not role[2]
    owner_safe = bool(role) and bool(rows) and all(row[5] != role[0] for row in rows)
    tables_enforced = bool(rows) and all(
        row[1]
        and row[2]
        and row[3]
        and row[4]
        and "current_setting" in row[3]
        and "current_setting" in row[4]
        for row in rows
    )
    return {
        "backend": connection.vendor,
        "enforced": tables_enforced and role_safe and owner_safe,
        "role": (
            {
                "name": role[0],
                "superuser": role[1],
                "bypass_rls": role[2],
                "create_role": role[3],
                "create_db": role[4],
            }
            if role
            else None
        ),
        "tables": [
            {
                "name": row[0],
                "rowsecurity": row[1],
                "force": row[2],
                "tenant_policy": bool(row[3] and row[4]),
                "policy_using": row[3],
                "policy_check": row[4],
                "owner": row[5],
            }
            for row in rows
        ],
    }
