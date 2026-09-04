from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.db import migrations, models


RACE_SAFE_SERVICE_PRICE_SCOPE_SQL = """
CREATE OR REPLACE FUNCTION klin_klink_service_price_scope_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE list_org uuid; service_org uuid; facility_org uuid;
BEGIN
    SELECT organisation_id INTO list_org FROM billing_pricelist WHERE id = NEW.price_list_id;
    SELECT organisation_id INTO service_org FROM billing_servicecatalogitem WHERE id = NEW.service_id;
    SELECT organisation_id INTO facility_org FROM tenancy_facility WHERE id = NEW.facility_id;
    IF list_org IS NULL OR service_org IS NULL OR facility_org IS NULL
       OR list_org <> NEW.organisation_id OR service_org <> NEW.organisation_id
       OR facility_org <> NEW.organisation_id THEN
        RAISE EXCEPTION 'ServicePrice scope mismatch' USING ERRCODE = '23514';
    END IF;
    IF NEW.effective_to IS NOT NULL AND NEW.effective_to < NEW.effective_from THEN
        RAISE EXCEPTION 'ServicePrice effective dates are invalid' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_service_price_scope ON billing_serviceprice;
CREATE TRIGGER klin_klink_service_price_scope
BEFORE INSERT OR UPDATE OF organisation_id, facility_id, service_id, price_list_id,
    effective_from, effective_to, is_active, active ON billing_serviceprice
FOR EACH ROW EXECUTE FUNCTION klin_klink_service_price_scope_guard();
"""

def replace_service_price_overlap_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(RACE_SAFE_SERVICE_PRICE_SCOPE_SQL)
        cursor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        cursor.execute("ALTER TABLE billing_serviceprice DROP CONSTRAINT IF EXISTS service_price_active_period_excl")
        cursor.execute(
            """
            ALTER TABLE billing_serviceprice
            ADD CONSTRAINT service_price_active_period_excl
            EXCLUDE USING gist (
                organisation_id WITH =,
                facility_id WITH =,
                price_list_id WITH =,
                service_id WITH =,
                daterange(effective_from, effective_to, '[]') WITH &&
            )
            WHERE (is_active AND active)
            """
        )


def restore_service_price_overlap_guard(apps, schema_editor):
    # Keep the exclusion constraint and scope trigger on a state rollback.
    # Removing them would reintroduce the race-prone check-then-insert guard.
    return None


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("billing", "0004_s01_pc065_price_contracts")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(replace_service_price_overlap_guard, restore_service_price_overlap_guard),
            ],
            state_operations=[
                migrations.AddConstraint(
                    model_name="serviceprice",
                    constraint=ExclusionConstraint(
                        name="service_price_active_period_excl",
                        expressions=[
                            (models.F("organisation"), RangeOperators.EQUAL),
                            (models.F("facility"), RangeOperators.EQUAL),
                            (models.F("price_list"), RangeOperators.EQUAL),
                            (models.F("service"), RangeOperators.EQUAL),
                            (
                                models.Func(
                                    models.F("effective_from"),
                                    models.F("effective_to"),
                                    models.Value("[]"),
                                    function="daterange",
                                    output_field=DateRangeField(),
                                ),
                                RangeOperators.OVERLAPS,
                            ),
                        ],
                        condition=models.Q(is_active=True, active=True),
                    ),
                ),
            ],
        ),
    ]
