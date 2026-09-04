"""MIG-001 expand, deterministic legacy backfill, and scope guards."""

from hashlib import sha256
import json
import uuid

from django.db import migrations, models


MIGRATION_ID = "MIG-001"
BACKFILL_RUN_ID = uuid.uuid5(uuid.NAMESPACE_URL, "klinklik:MIG-001:0004")


def _hash(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _evidence(apps, *, organisation_id, facility_id, legacy_table, legacy_pk, codes, target_refs=None, source_hash="", target_hash=""):
    reconciliation = apps.get_model("core", "MigrationReconciliation")
    reconciliation.objects.update_or_create(
        organisation_id=organisation_id,
        migration_id=MIGRATION_ID,
        legacy_table=legacy_table,
        legacy_pk=str(legacy_pk),
        defaults={
            "facility_id": facility_id,
            "evidence_codes": sorted(set(codes)),
            "proposed_target_refs": target_refs,
            "source_hash": source_hash,
            "target_hash": target_hash,
            "backfill_run_id": BACKFILL_RUN_ID,
        },
    )


def _backfill_queue_entries(apps, schema_editor):
    connection = schema_editor.connection
    organisation_model = apps.get_model("tenancy", "Organisation")
    queue_model = apps.get_model("scheduling", "QueueEntry")
    visit_model = apps.get_model("scheduling", "Visit")
    encounter_model = apps.get_model("clinical", "Encounter")
    invoice_model = apps.get_model("billing", "Invoice")

    for organisation in organisation_model.objects.order_by("id").iterator():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.current_org_id', %s, true)", [str(organisation.id)])

        pending = list(
            queue_model.objects.filter(organisation_id=organisation.id, visit_id__isnull=True)
            .select_related("facility", "patient", "department")
            .order_by("id")
        )
        grouped = {}
        for queue in pending:
            grouped.setdefault(
                (str(queue.organisation_id), str(queue.facility_id), str(queue.patient_id), queue.queue_date),
                [],
            ).append(queue)

        for queue in pending:
            source = {
                "legacy_table": "scheduling_queueentry",
                "legacy_pk": str(queue.id),
                "organisation_id": str(queue.organisation_id),
                "facility_id": str(queue.facility_id),
                "patient_id": str(queue.patient_id),
                "queue_date": queue.queue_date.isoformat(),
                "arrival_at": queue.arrival_at.isoformat() if queue.arrival_at else None,
                "encounter_ids": [str(value) for value in encounter_model.objects.filter(queue_entry_id=queue.id).values_list("id", flat=True)],
            }
            source_hash = _hash(source)
            errors = []
            if queue.facility.organisation_id != queue.organisation_id:
                errors.append("FACILITY_ORGANISATION_MISMATCH")
            if queue.patient.organisation_id != queue.organisation_id:
                errors.append("PATIENT_ORGANISATION_MISMATCH")
            if queue.department.organisation_id != queue.organisation_id or queue.department.facility_id != queue.facility_id:
                errors.append("DEPARTMENT_SCOPE_MISMATCH")
            if len(grouped[(str(queue.organisation_id), str(queue.facility_id), str(queue.patient_id), queue.queue_date)]) > 1:
                errors.append("AMBIGUOUS_EPISODE")

            visit_type = queue.visit_type
            if visit_type == "WALK_IN":
                visit_type = "OUTPATIENT_NEW"
            if visit_type not in {"OUTPATIENT_NEW", "OUTPATIENT_REVIEW", "ANC", "LAB_ONLY", "PHARMACY_ONLY", "FOLLOW_UP_RESULTS"}:
                errors.append("UNSUPPORTED_VISIT_TYPE")
            encounters = list(encounter_model.objects.filter(queue_entry_id=queue.id).order_by("id"))
            opened_by_id = queue.claimed_by_id or (encounters[0].clinician_id if len(encounters) == 1 else None)
            if opened_by_id is None:
                errors.append("MISSING_OPENED_BY")
            if len(encounters) > 1:
                errors.append("MULTIPLE_ENCOUNTER_LINEAGE")
            if any(
                encounter.organisation_id != queue.organisation_id
                or encounter.facility_id != queue.facility_id
                or encounter.patient_id != queue.patient_id
                for encounter in encounters
            ):
                errors.append("LINK_SCOPE_MISMATCH")

            if errors:
                _evidence(
                    apps,
                    organisation_id=queue.organisation_id,
                    facility_id=queue.facility_id,
                    legacy_table="scheduling_queueentry",
                    legacy_pk=queue.id,
                    codes=errors,
                    target_refs={"queue_id": str(queue.id)},
                    source_hash=source_hash,
                )
                continue

            source_key = f"queue:{queue.id}"
            visit = visit_model.objects.filter(
                organisation_id=queue.organisation_id,
                legacy_source_key=source_key,
            ).first()
            if visit is not None and (
                visit.facility_id != queue.facility_id
                or visit.patient_id != queue.patient_id
                or visit.local_service_date != queue.queue_date
            ):
                _evidence(
                    apps,
                    organisation_id=queue.organisation_id,
                    facility_id=queue.facility_id,
                    legacy_table="scheduling_queueentry",
                    legacy_pk=queue.id,
                    codes=["TARGET_SCOPE_MISMATCH"],
                    target_refs={"queue_id": str(queue.id), "visit_id": str(visit.id)},
                    source_hash=source_hash,
                )
                continue
            if visit is None:
                existing_active = visit_model.objects.filter(
                    organisation_id=queue.organisation_id,
                    facility_id=queue.facility_id,
                    patient_id=queue.patient_id,
                    local_service_date=queue.queue_date,
                    state__in=["OPEN", "IN_PROGRESS"],
                ).order_by("id").first()
                if existing_active is not None:
                    _evidence(
                        apps,
                        organisation_id=queue.organisation_id,
                        facility_id=queue.facility_id,
                        legacy_table="scheduling_queueentry",
                        legacy_pk=queue.id,
                        codes=["EXISTING_ACTIVE_VISIT"],
                        target_refs={"queue_id": str(queue.id), "visit_id": str(existing_active.id)},
                        source_hash=source_hash,
                    )
                    continue
            if visit is None:
                visit = visit_model.objects.create(
                    organisation_id=queue.organisation_id,
                    facility_id=queue.facility_id,
                    patient_id=queue.patient_id,
                    local_service_date=queue.queue_date,
                    visit_type=visit_type,
                    state="OPEN",
                    opened_at=queue.arrival_at or queue.queue_time or queue.created_at,
                    opened_by_id=opened_by_id,
                    legacy_source_key=source_key,
                )
            queue.visit_id = visit.id
            queue.save(update_fields=["visit", "updated_at"])

            target_refs = {"visit_id": str(visit.id), "queue_id": str(queue.id)}
            target_hash = _hash(target_refs)
            if len(encounters) == 1:
                invoices = list(invoice_model.objects.filter(encounter_id=encounters[0].id).order_by("id"))
                if len(invoices) > 1:
                    _evidence(
                        apps,
                        organisation_id=queue.organisation_id,
                        facility_id=queue.facility_id,
                        legacy_table="billing_invoice",
                        legacy_pk=encounters[0].id,
                        codes=["INVOICE_LINEAGE_AMBIGUOUS"],
                        target_refs=target_refs,
                        source_hash=source_hash,
                        target_hash=target_hash,
                    )
                elif invoices:
                    invoice = invoices[0]
                    if invoice.visit_id == visit.id:
                        continue
                    if invoice.visit_id is None and invoice.organisation_id == queue.organisation_id and invoice.facility_id == queue.facility_id and invoice.patient_id == queue.patient_id:
                        invoice.visit_id = visit.id
                        invoice.save(update_fields=["visit", "updated_at"])
                    else:
                        _evidence(
                            apps,
                            organisation_id=queue.organisation_id,
                            facility_id=queue.facility_id,
                            legacy_table="billing_invoice",
                            legacy_pk=invoice.id,
                            codes=["INVOICE_ALREADY_LINKED", "LINK_SCOPE_MISMATCH"],
                            target_refs=target_refs,
                            source_hash=source_hash,
                            target_hash=target_hash,
                        )


def _record_queue_less_lineage(apps, schema_editor):
    connection = schema_editor.connection
    organisation_model = apps.get_model("tenancy", "Organisation")
    encounter_model = apps.get_model("clinical", "Encounter")
    invoice_model = apps.get_model("billing", "Invoice")
    for organisation in organisation_model.objects.order_by("id").iterator():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.current_org_id', %s, true)", [str(organisation.id)])
        for encounter in encounter_model.objects.filter(organisation_id=organisation.id, queue_entry_id__isnull=True).order_by("id"):
            _evidence(
                apps,
                organisation_id=encounter.organisation_id,
                facility_id=encounter.facility_id,
                legacy_table="clinical_encounter",
                legacy_pk=encounter.id,
                codes=["QUEUELESS_ENCOUNTER"],
                target_refs=None,
                source_hash=_hash({"encounter_id": str(encounter.id), "patient_id": str(encounter.patient_id), "facility_id": str(encounter.facility_id)}),
            )
        for invoice in invoice_model.objects.filter(organisation_id=organisation.id, encounter_id__isnull=True, visit_id__isnull=True).order_by("id"):
            _evidence(
                apps,
                organisation_id=invoice.organisation_id,
                facility_id=invoice.facility_id,
                legacy_table="billing_invoice",
                legacy_pk=invoice.id,
                codes=["QUEUELESS_INVOICE_NO_LINEAGE"],
                target_refs=None,
                source_hash=_hash({"invoice_id": str(invoice.id), "patient_id": str(invoice.patient_id), "facility_id": str(invoice.facility_id)}),
            )


def backfill_mig001(apps, schema_editor):
    _backfill_queue_entries(apps, schema_editor)
    _record_queue_less_lineage(apps, schema_editor)


def reverse_backfill(apps, schema_editor):
    # MIG-001 rollback retains Visits and links. A later deployment can remove
    # compatibility readers only after the evidence has been reconciled.
    return None


SCOPE_SQL = """
CREATE OR REPLACE FUNCTION klin_klink_visit_scope_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE facility_org uuid; patient_org uuid; related_org uuid; related_facility uuid; related_patient uuid;
BEGIN
    SELECT organisation_id INTO facility_org FROM tenancy_facility WHERE id = NEW.facility_id;
    SELECT organisation_id INTO patient_org FROM patients_patient WHERE id = NEW.patient_id;
    IF facility_org IS NULL OR facility_org <> NEW.organisation_id OR patient_org IS NULL OR patient_org <> NEW.organisation_id THEN
        RAISE EXCEPTION 'Visit scope mismatch' USING ERRCODE = '23514';
    END IF;
    IF NEW.related_visit_id IS NOT NULL THEN
        SELECT organisation_id, facility_id, patient_id INTO related_org, related_facility, related_patient
        FROM scheduling_visit WHERE id = NEW.related_visit_id;
        IF related_org IS NULL OR related_org <> NEW.organisation_id OR related_facility <> NEW.facility_id OR related_patient <> NEW.patient_id THEN
            RAISE EXCEPTION 'Related Visit scope mismatch' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_visit_scope ON scheduling_visit;
CREATE TRIGGER klin_klink_visit_scope BEFORE INSERT OR UPDATE OF organisation_id, facility_id, patient_id, related_visit_id ON scheduling_visit
FOR EACH ROW EXECUTE FUNCTION klin_klink_visit_scope_guard();

CREATE OR REPLACE FUNCTION klin_klink_queue_visit_scope_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE visit_org uuid; visit_facility uuid; visit_patient uuid;
BEGIN
    IF NEW.visit_id IS NOT NULL THEN
        SELECT organisation_id, facility_id, patient_id INTO visit_org, visit_facility, visit_patient
        FROM scheduling_visit WHERE id = NEW.visit_id;
        IF visit_org IS NULL OR visit_org <> NEW.organisation_id OR visit_facility <> NEW.facility_id OR visit_patient <> NEW.patient_id THEN
            RAISE EXCEPTION 'QueueEntry Visit scope mismatch' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_queue_visit_scope ON scheduling_queueentry;
CREATE TRIGGER klin_klink_queue_visit_scope BEFORE INSERT OR UPDATE OF organisation_id, facility_id, patient_id, visit_id ON scheduling_queueentry
FOR EACH ROW EXECUTE FUNCTION klin_klink_queue_visit_scope_guard();

CREATE OR REPLACE FUNCTION klin_klink_enquiry_visit_scope_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE visit_org uuid; visit_facility uuid;
BEGIN
    IF NEW.converted_visit_id IS NOT NULL THEN
        SELECT organisation_id, facility_id INTO visit_org, visit_facility FROM scheduling_visit WHERE id = NEW.converted_visit_id;
        IF visit_org IS NULL OR visit_org <> NEW.organisation_id OR visit_facility <> NEW.facility_id THEN
            RAISE EXCEPTION 'ArrivalEnquiry Visit scope mismatch' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_enquiry_visit_scope ON scheduling_arrivalenquiry;
CREATE TRIGGER klin_klink_enquiry_visit_scope BEFORE INSERT OR UPDATE OF organisation_id, facility_id, converted_visit_id ON scheduling_arrivalenquiry
FOR EACH ROW EXECUTE FUNCTION klin_klink_enquiry_visit_scope_guard();
"""

REVERSE_SCOPE_SQL = """
DROP TRIGGER IF EXISTS klin_klink_enquiry_visit_scope ON scheduling_arrivalenquiry;
DROP FUNCTION IF EXISTS klin_klink_enquiry_visit_scope_guard();
DROP TRIGGER IF EXISTS klin_klink_queue_visit_scope ON scheduling_queueentry;
DROP FUNCTION IF EXISTS klin_klink_queue_visit_scope_guard();
DROP TRIGGER IF EXISTS klin_klink_visit_scope ON scheduling_visit;
DROP FUNCTION IF EXISTS klin_klink_visit_scope_guard();
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
        ("billing", "0003_s01_registration_visit_checkin"),
        ("clinical", "0008_s00_tenant_rls_repair"),
        ("core", "0005_s01_mig001_reconciliation"),
        ("scheduling", "0003_s01_registration_visit_checkin"),
    ]

    operations = [
        migrations.AddField(
            model_name="visit",
            name="legacy_source_key",
            field=models.CharField(blank=True, max_length=160, null=True),
        ),
        migrations.AddConstraint(
            model_name="visit",
            constraint=models.UniqueConstraint(
                condition=models.Q(("legacy_source_key__isnull", False)),
                fields=("organisation", "legacy_source_key"),
                name="uniq_visit_legacy_source_key",
            ),
        ),
        migrations.RunPython(backfill_mig001, reverse_backfill),
        migrations.RunPython(apply_scope_guards, reverse_scope_guards),
    ]
