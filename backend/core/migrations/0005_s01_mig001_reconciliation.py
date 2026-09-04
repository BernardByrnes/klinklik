import core.models
import django.db.models.deletion
from django.db import migrations, models


RLS_SQL = """
DO $$
DECLARE table_name text;
BEGIN
    FOR table_name IN SELECT unnest(ARRAY['core_migrationreconciliation', 'core_migrationcutover']) LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS clinicopus_tenant_isolation ON %I', table_name);
        EXECUTE format(
            'CREATE POLICY clinicopus_tenant_isolation ON %I USING (organisation_id = current_setting(''app.current_org_id'')::uuid) WITH CHECK (organisation_id = current_setting(''app.current_org_id'')::uuid)',
            table_name
        );
    END LOOP;
END $$;
"""

REVERSE_RLS_SQL = """
DO $$
DECLARE table_name text;
BEGIN
    FOR table_name IN SELECT unnest(ARRAY['core_migrationreconciliation', 'core_migrationcutover']) LOOP
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
            cursor.execute(REVERSE_RLS_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("core", "0004_s01_registration_visit_checkin"),
    ]

    operations = [
        migrations.CreateModel(
            name="MigrationReconciliation",
            fields=[
                ("id", models.UUIDField(default=core.models.uuid7, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("migration_id", models.CharField(max_length=40)),
                ("facility", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="migration_reconciliation_records", to="tenancy.facility")),
                ("legacy_table", models.CharField(max_length=120)),
                ("legacy_pk", models.CharField(max_length=120)),
                ("evidence_codes", models.JSONField(default=list)),
                ("proposed_target_refs", models.JSONField(blank=True, null=True)),
                ("source_hash", models.CharField(blank=True, max_length=64)),
                ("target_hash", models.CharField(blank=True, max_length=64)),
                ("backfill_run_id", models.UUIDField(blank=True, null=True)),
                ("resolution_state", models.CharField(choices=[("PENDING", "Pending"), ("RESOLVED", "Resolved")], default="PENDING", max_length=20)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("reason", models.CharField(blank=True, max_length=240)),
                ("organisation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_records", to="tenancy.organisation")),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="resolved_migration_reconciliations", to="accounts.user")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("organisation", "migration_id", "legacy_table", "legacy_pk"), name="uniq_migration_reconciliation_source"),
                    models.CheckConstraint(condition=models.Q(models.Q(("resolution_state", "PENDING"), ("resolved_at__isnull", True), ("resolved_by__isnull", True)), models.Q(("resolution_state", "RESOLVED"), ("resolved_at__isnull", False), ("resolved_by__isnull", False)), _connector="OR"), name="migration_reconciliation_resolution_fields_match"),
                ],
            },
        ),
        migrations.CreateModel(
            name="MigrationCutover",
            fields=[
                ("id", models.UUIDField(default=core.models.uuid7, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("migration_id", models.CharField(max_length=40)),
                ("phase", models.CharField(default="EXPANDED", max_length=30)),
                ("target_reads_enabled", models.BooleanField(default=False)),
                ("target_writes_enabled", models.BooleanField(default=False)),
                ("rollback_at", models.DateTimeField(blank=True, null=True)),
                ("rollback_reason", models.CharField(blank=True, max_length=240)),
                ("version", models.PositiveBigIntegerField(default=1)),
                ("organisation", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(class)s_records", to="tenancy.organisation")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("organisation", "migration_id"), name="uniq_migration_cutover_org_id"),
                ],
            },
        ),
        migrations.RunPython(apply_rls, reverse_rls),
    ]
