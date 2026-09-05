from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0006_s01_mig001_cutover_gates")]

    operations = [
        migrations.AddField(
            model_name="migrationcutover",
            name="backfill_facility_counts",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="backfill_organisation_counts",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="deterministic_row_evidence",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="inventory_facility_counts",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="inventory_organisation_counts",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="last_run_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="shadow_read_digest",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="shadow_read_equal",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="stable_full_scan_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="migrationcutover",
            name="write_fence",
            field=models.PositiveBigIntegerField(default=1),
        ),
    ]
