from django.db import migrations, models, transaction
import django.db.models.deletion


def reject_unresolved_price_references(apps, schema_editor):
    """Leave evidence before the NOT NULL contract makes unresolved rows fail closed."""

    service_price = apps.get_model("billing", "ServicePrice")
    binding = apps.get_model("billing", "VisitPayerBinding")
    reconciliation = apps.get_model("core", "MigrationReconciliation")
    organisation_model = apps.get_model("tenancy", "Organisation")
    unresolved = False
    for organisation in organisation_model.objects.order_by("id"):
        # The contract tables are already FORCE RLS protected by S-00. Keep
        # the evidence write inside the matching tenant transaction so a
        # non-bypass migration role can classify legacy rows safely.
        with transaction.atomic():
            if schema_editor.connection.vendor == "postgresql":
                with schema_editor.connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.current_org_id', %s, true)",
                        [str(organisation.id)],
                    )
            for price in service_price.objects.filter(
                organisation_id=organisation.id,
                price_list_id__isnull=True,
            ).order_by("id"):
                unresolved = True
                reconciliation.objects.get_or_create(
                    organisation_id=price.organisation_id,
                    migration_id="MIG-001",
                    legacy_table="billing_serviceprice",
                    legacy_pk=str(price.id),
                    defaults={
                        "facility_id": price.facility_id,
                        "evidence_codes": ["NO_PRICE_LIST_REFERENCE", "PC_066_UNRESOLVED"],
                        "proposed_target_refs": {"service_price_id": str(price.id)},
                    },
                )
            for payer_binding in binding.objects.filter(
                organisation_id=organisation.id,
                price_list_id__isnull=True,
            ).order_by("id"):
                unresolved = True
                reconciliation.objects.get_or_create(
                    organisation_id=payer_binding.organisation_id,
                    migration_id="MIG-001",
                    legacy_table="billing_visitpayerbinding",
                    legacy_pk=str(payer_binding.id),
                    defaults={
                        "facility_id": payer_binding.facility_id,
                        "evidence_codes": ["NO_PRICE_LIST_REFERENCE", "PC_067_UNRESOLVED"],
                        "proposed_target_refs": {"payer_binding_id": str(payer_binding.id)},
                    },
                )
    if unresolved:
        raise RuntimeError("MIG-001 has unresolved PC-065..067 PriceList references; refusing to invent catalogue configuration.")


def noop_reverse(apps, schema_editor):
    return None


SCOPE_SQL = """
CREATE OR REPLACE FUNCTION klin_klink_service_price_scope_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE list_org uuid; service_org uuid; facility_org uuid;
BEGIN
    SELECT organisation_id INTO list_org FROM billing_pricelist WHERE id = NEW.price_list_id;
    SELECT organisation_id INTO service_org FROM billing_servicecatalogitem WHERE id = NEW.service_id;
    SELECT organisation_id INTO facility_org FROM tenancy_facility WHERE id = NEW.facility_id;
    IF list_org IS NULL OR service_org IS NULL OR facility_org IS NULL OR list_org <> NEW.organisation_id OR service_org <> NEW.organisation_id OR facility_org <> NEW.organisation_id THEN
        RAISE EXCEPTION 'ServicePrice scope mismatch' USING ERRCODE = '23514';
    END IF;
    IF NEW.effective_to IS NOT NULL AND NEW.effective_to < NEW.effective_from THEN
        RAISE EXCEPTION 'ServicePrice effective dates are invalid' USING ERRCODE = '23514';
    END IF;
    IF EXISTS (
        SELECT 1 FROM billing_serviceprice other
        WHERE other.id <> NEW.id
          AND other.organisation_id = NEW.organisation_id
          AND other.facility_id = NEW.facility_id
          AND other.service_id = NEW.service_id
          AND other.price_list_id = NEW.price_list_id
          AND other.is_active AND other.active
          AND COALESCE(other.effective_to, DATE '9999-12-31') >= NEW.effective_from
          AND COALESCE(NEW.effective_to, DATE '9999-12-31') >= other.effective_from
    ) THEN
        RAISE EXCEPTION 'Overlapping ServicePrice effective period' USING ERRCODE = '23P01';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_service_price_scope ON billing_serviceprice;
CREATE TRIGGER klin_klink_service_price_scope BEFORE INSERT OR UPDATE OF organisation_id, facility_id, service_id, price_list_id, effective_from, effective_to, is_active, active ON billing_serviceprice
FOR EACH ROW EXECUTE FUNCTION klin_klink_service_price_scope_guard();

CREATE OR REPLACE FUNCTION klin_klink_payer_binding_scope_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE visit_org uuid; visit_facility uuid; visit_patient uuid; list_org uuid; facility_org uuid;
BEGIN
    SELECT organisation_id, facility_id, patient_id INTO visit_org, visit_facility, visit_patient FROM scheduling_visit WHERE id = NEW.visit_id;
    SELECT organisation_id INTO list_org FROM billing_pricelist WHERE id = NEW.price_list_id;
    SELECT organisation_id INTO facility_org FROM tenancy_facility WHERE id = NEW.facility_id;
    IF visit_org IS NULL OR list_org IS NULL OR facility_org IS NULL OR visit_org <> NEW.organisation_id OR visit_facility <> NEW.facility_id OR list_org <> NEW.organisation_id OR facility_org <> NEW.organisation_id THEN
        RAISE EXCEPTION 'VisitPayerBinding scope mismatch' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_payer_binding_scope ON billing_visitpayerbinding;
CREATE TRIGGER klin_klink_payer_binding_scope BEFORE INSERT OR UPDATE OF organisation_id, facility_id, visit_id, price_list_id ON billing_visitpayerbinding
FOR EACH ROW EXECUTE FUNCTION klin_klink_payer_binding_scope_guard();

CREATE OR REPLACE FUNCTION klin_klink_invoice_visit_scope_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE visit_org uuid; visit_facility uuid; visit_patient uuid; encounter_org uuid; encounter_facility uuid; encounter_patient uuid;
BEGIN
    IF NEW.visit_id IS NOT NULL THEN
        SELECT organisation_id, facility_id, patient_id INTO visit_org, visit_facility, visit_patient FROM scheduling_visit WHERE id = NEW.visit_id;
        IF visit_org IS NULL OR visit_org <> NEW.organisation_id OR visit_facility <> NEW.facility_id OR visit_patient <> NEW.patient_id THEN
            RAISE EXCEPTION 'Invoice Visit scope mismatch' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NEW.encounter_id IS NOT NULL THEN
        SELECT organisation_id, facility_id, patient_id INTO encounter_org, encounter_facility, encounter_patient FROM clinical_encounter WHERE id = NEW.encounter_id;
        IF encounter_org IS NULL OR encounter_org <> NEW.organisation_id OR encounter_facility <> NEW.facility_id OR encounter_patient <> NEW.patient_id THEN
            RAISE EXCEPTION 'Invoice Encounter scope mismatch' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_invoice_visit_scope ON billing_invoice;
CREATE TRIGGER klin_klink_invoice_visit_scope BEFORE INSERT OR UPDATE OF organisation_id, facility_id, patient_id, visit_id, encounter_id ON billing_invoice
FOR EACH ROW EXECUTE FUNCTION klin_klink_invoice_visit_scope_guard();

CREATE OR REPLACE FUNCTION klin_klink_price_list_immutable_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' OR EXISTS (SELECT 1 FROM billing_serviceprice WHERE price_list_id = OLD.id)
       OR EXISTS (SELECT 1 FROM billing_visitpayerbinding WHERE price_list_id = OLD.id) THEN
        RAISE EXCEPTION 'Referenced PriceList versions are immutable' USING ERRCODE = '55006';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_price_list_immutable ON billing_pricelist;
CREATE TRIGGER klin_klink_price_list_immutable BEFORE UPDATE OR DELETE ON billing_pricelist
FOR EACH ROW EXECUTE FUNCTION klin_klink_price_list_immutable_guard();

CREATE OR REPLACE FUNCTION klin_klink_payer_binding_immutable_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'VisitPayerBinding history is append-only' USING ERRCODE = '55006';
    RETURN NULL;
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_payer_binding_immutable ON billing_visitpayerbinding;
CREATE TRIGGER klin_klink_payer_binding_immutable BEFORE UPDATE OR DELETE ON billing_visitpayerbinding
FOR EACH ROW EXECUTE FUNCTION klin_klink_payer_binding_immutable_guard();
"""

REVERSE_SCOPE_SQL = """
DROP TRIGGER IF EXISTS klin_klink_invoice_visit_scope ON billing_invoice;
DROP FUNCTION IF EXISTS klin_klink_invoice_visit_scope_guard();
DROP TRIGGER IF EXISTS klin_klink_payer_binding_immutable ON billing_visitpayerbinding;
DROP FUNCTION IF EXISTS klin_klink_payer_binding_immutable_guard();
DROP TRIGGER IF EXISTS klin_klink_price_list_immutable ON billing_pricelist;
DROP FUNCTION IF EXISTS klin_klink_price_list_immutable_guard();
DROP TRIGGER IF EXISTS klin_klink_payer_binding_scope ON billing_visitpayerbinding;
DROP FUNCTION IF EXISTS klin_klink_payer_binding_scope_guard();
DROP TRIGGER IF EXISTS klin_klink_service_price_scope ON billing_serviceprice;
DROP FUNCTION IF EXISTS klin_klink_service_price_scope_guard();
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
    # Evidence must commit even when this migration deliberately refuses to
    # apply the NOT NULL contract. Validation is first, so a failed migration
    # leaves the schema unchanged and the PC-050 inventory durable.
    atomic = False

    dependencies = [
        ("billing", "0003_s01_registration_visit_checkin"),
        ("clinical", "0009_s01_mig001_encounter_visit"),
        ("core", "0005_s01_mig001_reconciliation"),
    ]

    operations = [
        migrations.RunPython(reject_unresolved_price_references, noop_reverse),
        migrations.AddField(
            model_name="serviceprice",
            name="source_version",
            field=models.CharField(default="v1", max_length=40),
        ),
        migrations.AlterField(
            model_name="serviceprice",
            name="price_list",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="service_prices", to="billing.pricelist"),
        ),
        migrations.AlterField(
            model_name="visitpayerbinding",
            name="price_list",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="visit_bindings", to="billing.pricelist"),
        ),
        migrations.AddConstraint(
            model_name="pricelist",
            constraint=models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F("effective_from")),
                name="price_list_effective_dates_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="serviceprice",
            constraint=models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F("effective_from")),
                name="service_price_effective_dates_valid",
            ),
        ),
        migrations.RunPython(apply_scope_guards, reverse_scope_guards),
    ]
