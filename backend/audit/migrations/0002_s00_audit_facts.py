from django.db import migrations, models


def backfill_event_codes(apps, schema_editor):
    audit_model = apps.get_model("audit", "AuditEvent")
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        audit_model.objects.filter(event_code="").update(event_code=models.F("action"))
        return

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tgenabled
            FROM pg_trigger
            WHERE tgrelid = 'audit_auditevent'::regclass
              AND tgname = 'clinicopus_audit_immutable'
            """
        )
        trigger = cursor.fetchone()
        restore_trigger = bool(trigger and trigger[0] != "D")
        if restore_trigger:
            cursor.execute(
                "ALTER TABLE audit_auditevent DISABLE TRIGGER clinicopus_audit_immutable"
            )
        try:
            cursor.execute("SELECT id FROM tenancy_organisation ORDER BY id")
            organisation_ids = [row[0] for row in cursor.fetchall()]
            for organisation_id in organisation_ids:
                cursor.execute(
                    "SELECT set_config('app.current_org_id', %s, true)",
                    [str(organisation_id)],
                )
                audit_model.objects.filter(
                    organisation_id=organisation_id,
                    event_code="",
                ).update(event_code=models.F("action"))
        finally:
            if restore_trigger:
                cursor.execute(
                    "ALTER TABLE audit_auditevent ENABLE TRIGGER clinicopus_audit_immutable"
                )


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditevent",
            name="event_code",
            field=models.CharField(default="", max_length=120),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="source_ids",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="reason_code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="denial_identity",
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="denial_fingerprint",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="denial_event_code",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="copy_number",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_event_codes, noop_reverse),
        migrations.AddConstraint(
            model_name="auditevent",
            constraint=models.UniqueConstraint(
                condition=models.Q(copy_number__isnull=False),
                fields=("organisation", "event_code", "entity_type", "entity_id", "copy_number"),
                name="uniq_audit_copy_event",
            ),
        ),
        migrations.AddConstraint(
            model_name="auditevent",
            constraint=models.UniqueConstraint(
                condition=models.Q(denial_identity__isnull=False),
                fields=("organisation", "denial_identity"),
                name="uniq_audit_denial_identity",
            ),
        ),
    ]
