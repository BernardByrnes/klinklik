from hashlib import sha256
import json
import uuid

from django.db import migrations, models
import django.db.models.deletion


MIGRATION_ID = "MIG-001"
BACKFILL_RUN_ID = uuid.uuid5(uuid.NAMESPACE_URL, "klinklik:MIG-001:0009")


def _hash(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _evidence(reconciliation, *, organisation_id, facility_id, legacy_table, legacy_pk, codes, target_refs=None, source=None, target=None):
    reconciliation.objects.update_or_create(
        organisation_id=organisation_id,
        migration_id=MIGRATION_ID,
        legacy_table=legacy_table,
        legacy_pk=str(legacy_pk),
        defaults={
            "facility_id": facility_id,
            "evidence_codes": sorted(set(codes)),
            "proposed_target_refs": target_refs,
            "source_hash": _hash(source or {"legacy_table": legacy_table, "legacy_pk": str(legacy_pk)}),
            "target_hash": _hash(target) if target else "",
            "backfill_run_id": BACKFILL_RUN_ID,
        },
    )


def backfill_encounter_visits(apps, schema_editor):
    connection = schema_editor.connection
    organisation_model = apps.get_model("tenancy", "Organisation")
    encounter_model = apps.get_model("clinical", "Encounter")
    queue_model = apps.get_model("scheduling", "QueueEntry")
    invoice_model = apps.get_model("billing", "Invoice")
    reconciliation = apps.get_model("core", "MigrationReconciliation")

    for organisation in organisation_model.objects.order_by("id").iterator():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.current_org_id', %s, true)", [str(organisation.id)])
        for encounter in encounter_model.objects.filter(
            organisation_id=organisation.id,
            visit_id__isnull=True,
            queue_entry_id__isnull=False,
        ).select_related("queue_entry"):
            queue = encounter.queue_entry
            if queue.visit_id is None:
                _evidence(
                    reconciliation,
                    organisation_id=encounter.organisation_id,
                    facility_id=encounter.facility_id,
                    legacy_table="clinical_encounter",
                    legacy_pk=encounter.id,
                    codes=["QUEUE_UNLINKED"],
                    target_refs={"queue_id": str(queue.id)},
                    source={"encounter_id": str(encounter.id), "queue_id": str(queue.id)},
                )
                continue
            if (
                encounter.facility_id != queue.facility_id
                or encounter.patient_id != queue.patient_id
                or encounter.organisation_id != queue.organisation_id
            ):
                _evidence(
                    reconciliation,
                    organisation_id=encounter.organisation_id,
                    facility_id=encounter.facility_id,
                    legacy_table="clinical_encounter",
                    legacy_pk=encounter.id,
                    codes=["LINK_SCOPE_MISMATCH"],
                    target_refs={"queue_id": str(queue.id), "visit_id": str(queue.visit_id)},
                    source={"encounter_id": str(encounter.id), "queue_id": str(queue.id)},
                    target={"visit_id": str(queue.visit_id)},
                )
                continue
            encounter.visit_id = queue.visit_id
            encounter.save(update_fields=["visit", "updated_at"])

        for invoice in invoice_model.objects.filter(
            organisation_id=organisation.id,
            encounter_id__isnull=False,
        ).select_related("encounter"):
            encounter = invoice.encounter
            if encounter.visit_id is None:
                if invoice.visit_id is not None and (
                    invoice.organisation_id != encounter.organisation_id
                    or invoice.facility_id != encounter.facility_id
                    or invoice.patient_id != encounter.patient_id
                ):
                    _evidence(
                        reconciliation,
                        organisation_id=invoice.organisation_id,
                        facility_id=invoice.facility_id,
                        legacy_table="billing_invoice",
                        legacy_pk=invoice.id,
                        codes=["INVOICE_ALREADY_LINKED", "LINK_SCOPE_MISMATCH"],
                        target_refs={"encounter_id": str(encounter.id)},
                        source={"invoice_id": str(invoice.id), "encounter_id": str(encounter.id)},
                        target={"visit_id": str(invoice.visit_id)},
                    )
                continue
            if invoice.visit_id == encounter.visit_id:
                continue
            if invoice.visit_id is not None and invoice.visit_id != encounter.visit_id:
                _evidence(
                    reconciliation,
                    organisation_id=invoice.organisation_id,
                    facility_id=invoice.facility_id,
                    legacy_table="billing_invoice",
                    legacy_pk=invoice.id,
                    codes=["INVOICE_ALREADY_LINKED", "LINK_SCOPE_MISMATCH"],
                    target_refs={"encounter_id": str(encounter.id), "visit_id": str(encounter.visit_id)},
                    source={"invoice_id": str(invoice.id), "encounter_id": str(encounter.id)},
                    target={"visit_id": str(invoice.visit_id)},
                )
                continue
            if (
                invoice.facility_id != encounter.facility_id
                or invoice.patient_id != encounter.patient_id
                or invoice.organisation_id != encounter.organisation_id
            ):
                _evidence(
                    reconciliation,
                    organisation_id=invoice.organisation_id,
                    facility_id=invoice.facility_id,
                    legacy_table="billing_invoice",
                    legacy_pk=invoice.id,
                    codes=["LINK_SCOPE_MISMATCH"],
                    target_refs={"encounter_id": str(encounter.id), "visit_id": str(encounter.visit_id)},
                    source={"invoice_id": str(invoice.id), "encounter_id": str(encounter.id)},
                    target={"visit_id": str(encounter.visit_id)},
                )
                continue
            invoice.visit_id = encounter.visit_id
            invoice.save(update_fields=["visit", "updated_at"])


def reverse_backfill(apps, schema_editor):
    return None


SCOPE_SQL = """
CREATE OR REPLACE FUNCTION klin_klink_encounter_visit_scope_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE visit_org uuid; visit_facility uuid; visit_patient uuid; queue_visit uuid;
BEGIN
    IF NEW.visit_id IS NOT NULL THEN
        SELECT organisation_id, facility_id, patient_id INTO visit_org, visit_facility, visit_patient
        FROM scheduling_visit WHERE id = NEW.visit_id;
        IF visit_org IS NULL OR visit_org <> NEW.organisation_id OR visit_facility <> NEW.facility_id OR visit_patient <> NEW.patient_id THEN
            RAISE EXCEPTION 'Encounter Visit scope mismatch' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NEW.visit_id IS NOT NULL AND NEW.queue_entry_id IS NOT NULL THEN
        SELECT visit_id INTO queue_visit FROM scheduling_queueentry WHERE id = NEW.queue_entry_id;
        IF queue_visit IS NOT NULL AND queue_visit <> NEW.visit_id THEN
            RAISE EXCEPTION 'Encounter queue Visit mismatch' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_encounter_visit_scope ON clinical_encounter;
CREATE TRIGGER klin_klink_encounter_visit_scope BEFORE INSERT OR UPDATE OF organisation_id, facility_id, patient_id, queue_entry_id, visit_id ON clinical_encounter
FOR EACH ROW EXECUTE FUNCTION klin_klink_encounter_visit_scope_guard();
"""

REVERSE_SCOPE_SQL = """
DROP TRIGGER IF EXISTS klin_klink_encounter_visit_scope ON clinical_encounter;
DROP FUNCTION IF EXISTS klin_klink_encounter_visit_scope_guard();
"""


def apply_scope_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(SCOPE_SQL)


def reverse_scope_guard(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(REVERSE_SCOPE_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("clinical", "0008_s00_tenant_rls_repair"),
        ("scheduling", "0004_s01_mig001_target_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="encounter",
            name="visit",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="encounters",
                to="scheduling.visit",
            ),
        ),
        migrations.RunPython(backfill_encounter_visits, reverse_backfill),
        migrations.RunPython(apply_scope_guard, reverse_scope_guard),
    ]
