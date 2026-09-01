import hashlib

from django.db import migrations, models


def backfill_idempotency_identity(apps, schema_editor):
    record_model = apps.get_model("core", "IdempotencyRecord")
    for record in record_model.objects.all().iterator():
        record.operation = "legacy"
        record.key_hash = hashlib.sha256(record.key.encode("utf-8")).hexdigest()
        record.fingerprint = record.request_hash
        record.completed_at = record.completed_at or record.updated_at or record.created_at
        record.save(update_fields=["operation", "key_hash", "fingerprint", "completed_at"])


def noop_reverse(apps, schema_editor):
    return None


IMMUTABILITY_SQL = """
CREATE OR REPLACE FUNCTION clinicopus_block_completed_idempotency_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' OR OLD.completed_at IS NOT NULL THEN
        RAISE EXCEPTION 'Completed idempotency records are immutable';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS clinicopus_idempotency_immutable ON core_idempotencyrecord;
CREATE TRIGGER clinicopus_idempotency_immutable
BEFORE UPDATE OR DELETE ON core_idempotencyrecord
FOR EACH ROW EXECUTE FUNCTION clinicopus_block_completed_idempotency_mutation();
"""


REVERSE_IMMUTABILITY_SQL = """
DROP TRIGGER IF EXISTS clinicopus_idempotency_immutable ON core_idempotencyrecord;
DROP FUNCTION IF EXISTS clinicopus_block_completed_idempotency_mutation();
"""


def apply_immutability_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(IMMUTABILITY_SQL)


def reverse_immutability_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(REVERSE_IMMUTABILITY_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_tenant_rls"),
    ]

    operations = [
        migrations.AddField(
            model_name="idempotencyrecord",
            name="operation",
            field=models.CharField(max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="idempotencyrecord",
            name="key_hash",
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="idempotencyrecord",
            name="fingerprint",
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="idempotencyrecord",
            name="response_headers",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="idempotencyrecord",
            name="response_schema_version",
            field=models.CharField(default="v1", max_length=32),
        ),
        migrations.AddField(
            model_name="idempotencyrecord",
            name="result_reference",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="idempotencyrecord",
            name="status_code",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_idempotency_identity, noop_reverse),
        migrations.RemoveConstraint(
            model_name="idempotencyrecord",
            name="uniq_idempotency_org_key",
        ),
        migrations.RemoveField(
            model_name="idempotencyrecord",
            name="key",
        ),
        migrations.RemoveField(
            model_name="idempotencyrecord",
            name="request_hash",
        ),
        migrations.AlterField(
            model_name="idempotencyrecord",
            name="operation",
            field=models.CharField(max_length=120),
        ),
        migrations.AlterField(
            model_name="idempotencyrecord",
            name="key_hash",
            field=models.CharField(max_length=64),
        ),
        migrations.AlterField(
            model_name="idempotencyrecord",
            name="fingerprint",
            field=models.CharField(max_length=64),
        ),
        migrations.AddConstraint(
            model_name="idempotencyrecord",
            constraint=models.UniqueConstraint(
                fields=("organisation", "operation", "key_hash"),
                name="uniq_idempotency_org_op_key_hash",
            ),
        ),
        migrations.AddConstraint(
            model_name="idempotencyrecord",
            constraint=models.CheckConstraint(
                condition=models.Q(status_code__isnull=True)
                | models.Q(status_code__gte=200, status_code__lte=599),
                name="idempotency_status_code_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="idempotencyrecord",
            constraint=models.CheckConstraint(
                condition=models.Q(completed_at__isnull=True)
                | models.Q(status_code__isnull=False),
                name="idempotency_completed_has_status",
            ),
        ),
        migrations.RunPython(apply_immutability_trigger, reverse_immutability_trigger),
    ]
