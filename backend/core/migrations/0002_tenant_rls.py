from django.db import migrations


RLS_SQL = """
DO $$
DECLARE
    table_name text;
BEGIN
    FOR table_name IN
        SELECT DISTINCT c.table_name
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.column_name = 'organisation_id'
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS clinicopus_tenant_isolation ON %I', table_name);
        EXECUTE format(
            'CREATE POLICY clinicopus_tenant_isolation ON %I USING (organisation_id = current_setting(''app.current_org_id'')::uuid) WITH CHECK (organisation_id = current_setting(''app.current_org_id'')::uuid)',
            table_name
        );
    END LOOP;
END $$;

CREATE OR REPLACE FUNCTION clinicopus_block_audit_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Audit events are append-only';
END;
$$;

DROP TRIGGER IF EXISTS clinicopus_audit_immutable ON audit_auditevent;
CREATE TRIGGER clinicopus_audit_immutable
BEFORE UPDATE OR DELETE ON audit_auditevent
FOR EACH ROW EXECUTE FUNCTION clinicopus_block_audit_mutation();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS clinicopus_audit_immutable ON audit_auditevent;
DROP FUNCTION IF EXISTS clinicopus_block_audit_mutation();
DO $$
DECLARE
    table_name text;
BEGIN
    FOR table_name IN
        SELECT DISTINCT c.table_name
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.column_name = 'organisation_id'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS clinicopus_tenant_isolation ON %I', table_name);
        EXECUTE format('ALTER TABLE %I NO FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I DISABLE ROW LEVEL SECURITY', table_name);
    END LOOP;
END $$;
"""


def apply_rls(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(RLS_SQL)


def reverse_rls(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("accounts", "0001_initial"),
        ("audit", "0001_initial"),
        ("patients", "0001_initial"),
        ("scheduling", "0001_initial"),
        ("clinical", "0002_initial"),
        ("billing", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(apply_rls, reverse_rls),
    ]
