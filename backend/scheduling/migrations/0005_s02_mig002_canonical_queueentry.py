"""MIG-002 additive QueueEntry state expansion.

The schema migration adds the canonical state column and supporting fields
without classifying legacy rows. Runtime phases own inventory, backfill,
reconciliation, verification, cutover, and constraint activation.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import core.clock


def backfill_mig002(apps, schema_editor):
    """Compatibility hook retained for migration importers; never writes rows."""
    return None


def reverse_mig002(apps, schema_editor):
    # Target state, links, and reconciliation evidence are retained on
    # rollback.  Legacy readers can be selected by the application fence.
    return None


SCOPE_SQL = """
CREATE OR REPLACE FUNCTION klin_klink_queue_visit_scope_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE visit_org uuid; visit_facility uuid; visit_patient uuid;
        department_org uuid; department_facility uuid;
BEGIN
    SELECT organisation_id, facility_id INTO department_org, department_facility
    FROM tenancy_department WHERE id = NEW.department_id;
    IF department_org IS NULL OR department_org <> NEW.organisation_id
       OR department_facility <> NEW.facility_id THEN
        RAISE EXCEPTION 'QueueEntry Department scope mismatch' USING ERRCODE = '23514';
    END IF;
    IF NEW.visit_id IS NOT NULL THEN
        SELECT organisation_id, facility_id, patient_id INTO visit_org, visit_facility, visit_patient
        FROM scheduling_visit WHERE id = NEW.visit_id;
        IF visit_org IS NULL OR visit_org <> NEW.organisation_id
           OR visit_facility <> NEW.facility_id OR visit_patient <> NEW.patient_id THEN
            RAISE EXCEPTION 'QueueEntry Visit scope mismatch' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_queue_visit_scope ON scheduling_queueentry;
CREATE TRIGGER klin_klink_queue_visit_scope
BEFORE INSERT OR UPDATE OF organisation_id, facility_id, patient_id, visit_id, department_id
ON scheduling_queueentry FOR EACH ROW EXECUTE FUNCTION klin_klink_queue_visit_scope_guard();

ALTER TABLE scheduling_queueentry ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduling_queueentry FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS clinicopus_tenant_isolation ON scheduling_queueentry;
CREATE POLICY clinicopus_tenant_isolation ON scheduling_queueentry
USING (organisation_id = current_setting('app.current_org_id')::uuid)
WITH CHECK (organisation_id = current_setting('app.current_org_id')::uuid);
"""

REVERSE_SCOPE_SQL = """
DROP TRIGGER IF EXISTS klin_klink_queue_visit_scope ON scheduling_queueentry;
CREATE OR REPLACE FUNCTION klin_klink_queue_visit_scope_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE visit_org uuid; visit_facility uuid; visit_patient uuid;
BEGIN
    IF NEW.visit_id IS NOT NULL THEN
        SELECT organisation_id, facility_id, patient_id INTO visit_org, visit_facility, visit_patient
        FROM scheduling_visit WHERE id = NEW.visit_id;
        IF visit_org IS NULL OR visit_org <> NEW.organisation_id
           OR visit_facility <> NEW.facility_id OR visit_patient <> NEW.patient_id THEN
            RAISE EXCEPTION 'QueueEntry Visit scope mismatch' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER klin_klink_queue_visit_scope
BEFORE INSERT OR UPDATE OF organisation_id, facility_id, patient_id, visit_id
ON scheduling_queueentry FOR EACH ROW EXECUTE FUNCTION klin_klink_queue_visit_scope_guard();
"""


def apply_scope_guards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(SCOPE_SQL)


def reverse_scope_guards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(REVERSE_SCOPE_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("clinical", "0009_s01_mig001_encounter_visit"),
        ("core", "0007_s01_mig001_durable_proof"),
        ("patients", "0002_s01_registration_visit_checkin"),
        ("scheduling", "0004_s01_mig001_target_links"),
        ("tenancy", "0003_s01_registration_visit_checkin"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="queueentry",
            name="assigned_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assigned_queue_entries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="call_attempts",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="called_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="called_queue_entries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="completed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="completed_queue_entries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="held_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="hold_ref",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="last_activity_at",
            field=models.DateTimeField(default=core.clock.now),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="no_show_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="removed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="removed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="removed_queue_entries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="served_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="served_queue_entries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="service_seconds",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="service_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="source_stage",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="state",
            field=models.CharField(
                choices=[
                    ("WAITING_PAYMENT", "Waiting for payment"),
                    ("WAITING", "Waiting"),
                    ("CALLED", "Called"),
                    ("IN_SERVICE", "In service"),
                    ("ON_HOLD", "On hold"),
                    ("READY_TO_RESUME", "Ready to resume"),
                    ("COMPLETED", "Completed"),
                    ("TRANSFERRED", "Transferred"),
                    ("CANCELLED", "Cancelled"),
                    ("LWBS", "Left without being seen"),
                    ("NO_SHOW", "No show"),
                    ("EXPIRED", "Expired"),
                ],
                blank=True,
                max_length=30,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="terminal_reason",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="queueentry",
            name="wait_seconds",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="queueentry",
            name="status",
            field=models.CharField(
                choices=[
                    ("WAITING", "Waiting"),
                    ("WAITING_PAYMENT", "Waiting for payment"),
                    ("ON_HOLD", "On hold"),
                    ("READY_TO_RESUME", "Ready to resume"),
                    ("CALLED", "Called"),
                    ("IN_TRIAGE", "In triage"),
                    ("TRIAGED", "Triaged"),
                    ("IN_CONSULTATION", "In consultation"),
                    ("COMPLETED", "Completed"),
                    ("CANCELLED", "Cancelled"),
                    ("TRANSFERRED", "Transferred"),
                    ("LWBS", "Left without being seen"),
                    ("NO_SHOW", "No show"),
                    ("EXPIRED", "Expired"),
                ],
                default="WAITING",
                max_length=30,
            ),
        ),
        migrations.AddIndex(
            model_name="queueentry",
            index=models.Index(
                fields=["organisation", "facility", "department", "state", "priority", "queue_time"],
                name="scheduling__organis_ceb72f_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="queueentry",
            index=models.Index(
                fields=["organisation", "visit", "state", "queue_time"],
                name="scheduling__organis_be2957_idx",
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddConstraint(
                    model_name="queueentry",
                    constraint=models.UniqueConstraint(
                        condition=models.Q(
                            visit__isnull=False,
                            state__in=[
                                "WAITING_PAYMENT",
                                "WAITING",
                                "CALLED",
                                "IN_SERVICE",
                                "ON_HOLD",
                                "READY_TO_RESUME",
                            ],
                        ),
                        fields=("organisation", "visit", "department"),
                        name="uniq_active_queue_visit_department",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="queueentry",
                    constraint=models.UniqueConstraint(
                        condition=models.Q(visit__isnull=False, state="IN_SERVICE"),
                        fields=("organisation", "visit"),
                        name="uniq_in_service_queue_visit",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="queueentry",
                    constraint=models.CheckConstraint(
                        condition=models.Q(
                            state__in=[
                                "WAITING_PAYMENT",
                                "WAITING",
                                "CALLED",
                                "IN_SERVICE",
                                "ON_HOLD",
                                "READY_TO_RESUME",
                                "COMPLETED",
                                "TRANSFERRED",
                                "CANCELLED",
                                "LWBS",
                                "NO_SHOW",
                                "EXPIRED",
                            ]
                        ),
                        name="queue_entry_state_valid",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="queueentry",
                    constraint=models.CheckConstraint(
                        condition=models.Q(call_attempts__gte=0, no_show_count__gte=0),
                        name="queue_entry_attempt_counts_nonnegative",
                    ),
                ),
            ],
        ),
        migrations.RunPython(apply_scope_guards, reverse_scope_guards),
    ]
