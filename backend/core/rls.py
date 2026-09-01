import re

from django.db import connection


_TENANT_POLICY_EXPRESSION = re.compile(
    r"^\(*organisation_id\)*=\(*current_setting\('app\.current_org_id'(?:\:\:text)?(?:,true)?\)\)*\:\:uuid\)*$",
    re.IGNORECASE,
)


def is_tenant_policy_expression(expression):
    if not expression:
        return False
    normalized = re.sub(r"\s+", "", str(expression)).lower()
    return bool(_TENANT_POLICY_EXPRESSION.fullmatch(normalized))


def rls_status():
    if connection.vendor != "postgresql":
        return {"backend": connection.vendor, "enforced": False, "reason": "PostgreSQL required"}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT relation.relname,
                   relation.relrowsecurity,
                   relation.relforcerowsecurity,
                   COALESCE(pg_get_expr(policy.polqual, relation.oid), ''),
                   COALESCE(pg_get_expr(policy.polwithcheck, relation.oid), ''),
                   COALESCE(policy.polcmd, ''),
                   COALESCE(policy.polpermissive, TRUE),
                   pg_get_userbyid(relation.relowner)
            FROM pg_class relation
            JOIN pg_namespace namespace
              ON namespace.oid = relation.relnamespace
            LEFT JOIN pg_policy policy
              ON policy.polrelid = relation.oid
             AND policy.polname = 'clinicopus_tenant_isolation'
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
            SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolcanlogin
            FROM pg_roles
            WHERE rolname = current_user
            """
        )
        role = cursor.fetchone()
    role_safe = bool(role) and bool(role[5]) and not role[1] and not role[2]
    owner_safe = bool(role) and bool(rows) and all(row[7] != role[0] for row in rows)
    tables_enforced = bool(rows) and all(
        row[1]
        and row[2]
        and is_tenant_policy_expression(row[3])
        and is_tenant_policy_expression(row[4])
        and row[5] == "*"
        and row[6] is True
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
                "login": role[5],
            }
            if role
            else None
        ),
        "tables": [
            {
                "name": row[0],
                "rowsecurity": row[1],
                "force": row[2],
                "tenant_policy": (
                    is_tenant_policy_expression(row[3])
                    and is_tenant_policy_expression(row[4])
                    and row[5] == "*"
                    and row[6] is True
                ),
                "policy_using": row[3],
                "policy_check": row[4],
                "policy_command": row[5],
                "policy_permissive": row[6],
                "owner": row[7],
            }
            for row in rows
        ],
    }
