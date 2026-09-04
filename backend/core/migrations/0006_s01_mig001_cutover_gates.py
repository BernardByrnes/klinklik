from django.db import migrations, models


def disable_existing_switches(apps, schema_editor):
    """Make the pre-gate rows safe before the new evidence fields are used."""

    MigrationCutover = apps.get_model("core", "MigrationCutover")
    Organisation = apps.get_model("tenancy", "Organisation")
    for organisation in Organisation.objects.order_by("id").iterator():
        if schema_editor.connection.vendor == "postgresql":
            with schema_editor.connection.cursor() as cursor:
                # The reconciliation tables are FORCE RLS protected before
                # this migration.  Establish the tenant context before the
                # data migration touches any existing cutover rows.
                cursor.execute(
                    "SELECT set_config('app.current_org_id', %s, true)",
                    [str(organisation.id)],
                )
        MigrationCutover.objects.filter(
            organisation_id=organisation.id,
            migration_id="MIG-001",
        ).update(
            phase="EXPANDED",
            target_reads_enabled=False,
            target_writes_enabled=False,
            parity_passes=0,
            parity_digest="",
            scope_link_hash_verified=False,
            blocker_checks_passed=False,
        )


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [("core", "0005_s01_mig001_reconciliation")]

    operations = [
        migrations.AlterField(
            model_name="migrationcutover",
            name="phase",
            field=models.CharField(default="EXPANDED", max_length=30),
        ),
        migrations.AlterField(
            model_name="migrationcutover",
            name="target_reads_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="migrationcutover",
            name="target_writes_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="backfill_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="backfill_digest",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="backfill_source_count",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="blocker_checks_passed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="inventory_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="inventory_digest",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="inventory_source_count",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="last_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="parity_digest",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="parity_passes",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="scope_link_hash_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(disable_existing_switches, noop_reverse),
    ]
