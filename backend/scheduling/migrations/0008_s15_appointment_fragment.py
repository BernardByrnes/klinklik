import django.db.models.deletion
from django.db import migrations, models

from core.clock import local_service_date


def backfill_service_day(apps, schema_editor):
    Appointment = apps.get_model("scheduling", "Appointment")
    for appointment in Appointment.objects.filter(service_day__isnull=True).iterator():
        try:
            service_day = local_service_date(appointment.scheduled_start)
        except ValueError:
            service_day = appointment.scheduled_start.date()
        Appointment.objects.filter(id=appointment.id).update(service_day=service_day)


def apply_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    table = "scheduling_appointment"
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"
            f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"
            f"DROP POLICY IF EXISTS clinicopus_tenant_isolation ON {table};"
            f"CREATE POLICY clinicopus_tenant_isolation ON {table} "
            "USING (organisation_id = current_setting('app.current_org_id')::uuid) "
            "WITH CHECK (organisation_id = current_setting('app.current_org_id')::uuid);"
        )


def reverse_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    table = "scheduling_appointment"
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            f"DROP POLICY IF EXISTS clinicopus_tenant_isolation ON {table};"
            f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;"
            f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("scheduling", "0007_s02_queue_database_guards"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="service_day",
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name="appointment",
            name="checked_in_visit",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="appointment_fragments",
                to="scheduling.visit",
            ),
        ),
        migrations.AddField(
            model_name="appointment",
            name="version",
            field=models.PositiveBigIntegerField(default=1),
        ),
        migrations.RunPython(backfill_service_day, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="appointment",
            name="service_day",
            field=models.DateField(),
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.UniqueConstraint(
                condition=models.Q(checked_in_visit__isnull=False),
                fields=("organisation", "checked_in_visit"),
                name="uniq_appointment_checked_in_visit",
            ),
        ),
        migrations.AddIndex(
            model_name="appointment",
            index=models.Index(
                fields=["organisation", "facility", "service_day"],
                name="appt_fragment_day_idx",
            ),
        ),
        migrations.RunPython(apply_rls, reverse_rls),
    ]
