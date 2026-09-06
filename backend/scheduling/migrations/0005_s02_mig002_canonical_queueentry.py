"""MIG-002 expand and deterministic legacy QueueEntry state adaptation.

The migration keeps the pre-S-02 ``status`` column as a shadow while adding
the canonical QueueEntry contract.  Ambiguous stage evidence is retained as
non-PHI PC-050 evidence and is never converted into a guessed workflow state.
"""

from hashlib import sha256
import json

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import core.clock


MIGRATION_ID = "MIG-002"
CANONICAL_STATES = {
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
}
ACTIVE_STATES = {
    "WAITING_PAYMENT",
    "WAITING",
    "CALLED",
    "IN_SERVICE",
    "ON_HOLD",
    "READY_TO_RESUME",
}
LEGACY_STATE_MAP = {
    "WAITING": "WAITING",
    "WAITING_PAYMENT": "WAITING_PAYMENT",
    "ON_HOLD": "ON_HOLD",
    "READY_TO_RESUME": "READY_TO_RESUME",
    "CALLED": "CALLED",
    "IN_TRIAGE": "IN_SERVICE",
    "TRIAGED": "COMPLETED",
    "IN_CONSULTATION": "IN_SERVICE",
    "COMPLETED": "COMPLETED",
    "TRANSFERRED": "TRANSFERRED",
    "CANCELLED": "CANCELLED",
    "LWBS": "LWBS",
    "NO_SHOW": "NO_SHOW",
    "EXPIRED": "EXPIRED",
}


def _hash(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _source_evidence(queue, *, assessment_ids=(), encounter_ids=()):
    return {
        "legacy_table": "scheduling_queueentry",
        "legacy_pk": str(queue.id),
        "organisation_id": str(queue.organisation_id),
        "facility_id": str(queue.facility_id),
        "visit_id": str(queue.visit_id) if queue.visit_id else None,
        "patient_id": str(queue.patient_id),
        "department_id": str(queue.department_id),
        "status": queue.status,
        "current_stage": queue.current_stage,
        "queue_type": queue.queue_type,
        "hold_reason": queue.hold_reason,
        "priority": queue.priority,
        "priority_reason": queue.priority_reason,
        "queue_date": queue.queue_date.isoformat(),
        "queue_time": queue.queue_time.isoformat() if queue.queue_time else None,
        "called_at": queue.called_at.isoformat() if queue.called_at else None,
        "claimed_by_id": str(queue.claimed_by_id) if queue.claimed_by_id else None,
        "assessment_ids": sorted(str(value) for value in assessment_ids),
        "encounter_ids": sorted(str(value) for value in encounter_ids),
    }


def _record_evidence(
    reconciliation,
    *,
    queue,
    codes,
    source_hash,
    target_refs=None,
):
    reconciliation.objects.update_or_create(
        organisation_id=queue.organisation_id,
        migration_id=MIGRATION_ID,
        legacy_table="scheduling_queueentry",
        legacy_pk=str(queue.id),
        defaults={
            "facility_id": queue.facility_id,
            "evidence_codes": sorted(set(codes)),
            "proposed_target_refs": target_refs,
            "source_hash": source_hash,
            "target_hash": _hash({"source_hash": source_hash, "target_refs": target_refs}),
        },
    )


def _allocate_sequence(queue_model, queue):
    last = (
        queue_model.objects.filter(facility_id=queue.facility_id, queue_date=queue.queue_date)
        .order_by("-sequence")
        .values_list("sequence", flat=True)
        .first()
    )
    return (last or 0) + 1


def backfill_mig002(apps, schema_editor):
    organisation_model = apps.get_model("tenancy", "Organisation")
    queue_model = apps.get_model("scheduling", "QueueEntry")
    reconciliation = apps.get_model("core", "MigrationReconciliation")
    assessment_model = apps.get_model("clinical", "TriageAssessment")
    encounter_model = apps.get_model("clinical", "Encounter")

    for organisation in organisation_model.objects.order_by("id").iterator():
        queues = queue_model.objects.filter(organisation_id=organisation.id).order_by("id")
        for queue in queues.iterator():
            assessment_ids = list(
                assessment_model.objects.filter(queue_entry_id=queue.id)
                .order_by("id")
                .values_list("id", flat=True)
            )
            encounter_ids = list(
                encounter_model.objects.filter(queue_entry_id=queue.id)
                .order_by("id")
                .values_list("id", flat=True)
            )
            source_hash = _hash(
                _source_evidence(
                    queue,
                    assessment_ids=assessment_ids,
                    encounter_ids=encounter_ids,
                )
            )
            codes = []
            state = LEGACY_STATE_MAP.get(queue.status)
            if state is None:
                codes.append("UNKNOWN_LEGACY_STATE")
                state = "WAITING"
            if queue.visit_id is None:
                codes.append("MISSING_VISIT")
                state = "WAITING"
            else:
                visit = queue.visit
                if visit is None or (
                    visit.organisation_id != queue.organisation_id
                    or visit.facility_id != queue.facility_id
                    or visit.patient_id != queue.patient_id
                ):
                    codes.append("VISIT_SCOPE_MISMATCH")
                    state = "WAITING"
            department = queue.department
            if department is None or (
                department.organisation_id != queue.organisation_id
                or department.facility_id != queue.facility_id
            ):
                codes.append("DEPARTMENT_SCOPE_MISMATCH")
                state = "WAITING"
            if queue.status == "IN_TRIAGE" and queue.current_stage != "TRIAGE":
                codes.append("TRIAGE_STAGE_MISMATCH")
                state = "WAITING"
            if queue.status == "TRIAGED" and len(assessment_ids) != 1:
                codes.append("TRIAGE_ASSESSMENT_MISMATCH")
                state = "WAITING"
            if queue.status == "IN_CONSULTATION" and len(encounter_ids) != 1:
                codes.append("CONSULTATION_ENCOUNTER_MISMATCH")
                state = "WAITING"
            if codes:
                state = "WAITING"

            work_identity = queue.work_identity or f"MIG-002:QUEUE:{queue.id}"
            source_event_id = queue.source_event_id or f"MIG-002:QUEUE:{queue.id}"
            source_stage = queue.source_stage or queue.current_stage or "RECEPTION"
            queue_model.objects.filter(id=queue.id).update(
                state=state if state in CANONICAL_STATES else "WAITING",
                work_identity=work_identity,
                source_event_id=source_event_id,
                source_stage=source_stage,
                last_activity_at=queue.updated_at or queue.queue_time,
            )

            target_refs = {"queue_id": str(queue.id)}
            if queue.visit_id:
                target_refs["visit_id"] = str(queue.visit_id)

            # A TRIAGED legacy row with exactly one assessment has one
            # deterministic consultation destination.  The destination is
            # reused by source identity and receives no invented actor/time.
            if not codes and queue.status == "TRIAGED" and len(assessment_ids) == 1 and queue.visit_id:
                consultation_identity = f"MIG-002:CONSULTATION:{queue.id}"
                destination = queue_model.objects.filter(
                    organisation_id=queue.organisation_id,
                    facility_id=queue.facility_id,
                    visit_id=queue.visit_id,
                    work_identity=consultation_identity,
                ).first()
                assessment = assessment_model.objects.filter(id=assessment_ids[0]).first()
                priority = getattr(assessment, "acuity", "ROUTINE") if assessment else "ROUTINE"
                if priority not in {"EMERGENCY", "URGENT", "ROUTINE"}:
                    priority = "ROUTINE"
                if destination is None:
                    destination = queue_model.objects.create(
                        organisation_id=queue.organisation_id,
                        facility_id=queue.facility_id,
                        visit_id=queue.visit_id,
                        patient_id=queue.patient_id,
                        department_id=queue.department_id,
                        queue_date=queue.queue_date,
                        sequence=_allocate_sequence(queue_model, queue),
                        queue_type="CONSULTATION",
                        work_identity=consultation_identity,
                        priority=priority,
                        visit_type=queue.visit_type,
                        status="WAITING",
                        state="WAITING",
                        current_stage="CONSULTATION",
                        source_stage="TRIAGE",
                        queue_time=queue.queue_time or queue.updated_at,
                        last_activity_at=queue.updated_at or queue.queue_time,
                        source_event_id=f"MIG-002:CONSULTATION:{queue.id}",
                    )
                target_refs["consultation_queue_id"] = str(destination.id)

            if codes:
                _record_evidence(
                    reconciliation,
                    queue=queue,
                    codes=codes,
                    source_hash=source_hash,
                    target_refs=target_refs,
                )


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
                default="WAITING",
                max_length=30,
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
        migrations.RunPython(backfill_mig002, reverse_mig002),
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
        migrations.RunPython(apply_scope_guards, reverse_scope_guards),
    ]
