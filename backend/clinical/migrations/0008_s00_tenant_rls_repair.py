from django.db import migrations


RLS_SQL = """
ALTER TABLE clinical_patientallergystate ENABLE ROW LEVEL SECURITY;
ALTER TABLE clinical_patientallergystate FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS clinicopus_tenant_isolation ON clinical_patientallergystate;
CREATE POLICY clinicopus_tenant_isolation
ON clinical_patientallergystate
USING (organisation_id = current_setting('app.current_org_id')::uuid)
WITH CHECK (organisation_id = current_setting('app.current_org_id')::uuid);
"""

REVERSE_RLS_SQL = """
DROP POLICY IF EXISTS clinicopus_tenant_isolation ON clinical_patientallergystate;
ALTER TABLE clinical_patientallergystate NO FORCE ROW LEVEL SECURITY;
ALTER TABLE clinical_patientallergystate DISABLE ROW LEVEL SECURITY;
"""


def apply_tenant_rls_repair(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(RLS_SQL)


def reverse_tenant_rls_repair(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(REVERSE_RLS_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("clinical", "0007_encounter_disposition_encounter_disposition_note"),
        ("core", "0003_s00_verification_foundation"),
    ]

    operations = [
        migrations.RunPython(apply_tenant_rls_repair, reverse_tenant_rls_repair),
    ]
