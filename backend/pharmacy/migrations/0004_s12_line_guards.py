from django.db import migrations


GUARD_SQL = """
CREATE OR REPLACE FUNCTION klin_klink_dispense_line_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE parent_status text;
BEGIN
    SELECT status INTO parent_status FROM pharmacy_dispense WHERE id = OLD.dispense_id;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Dispense lines are retained' USING ERRCODE = '55006';
    END IF;
    IF parent_status IS DISTINCT FROM 'PROVISIONAL' THEN
        RAISE EXCEPTION 'A confirmed dispense line is immutable' USING ERRCODE = '55006';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_dispense_line_guard ON pharmacy_dispenseline;
CREATE TRIGGER klin_klink_dispense_line_guard
BEFORE UPDATE OR DELETE ON pharmacy_dispenseline
FOR EACH ROW EXECUTE FUNCTION klin_klink_dispense_line_guard();

CREATE OR REPLACE FUNCTION klin_klink_otc_line_immutable()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'OTC sale lines are immutable' USING ERRCODE = '55006';
END;
$$;
DROP TRIGGER IF EXISTS klin_klink_otc_line_immutable ON pharmacy_otcsaleline;
CREATE TRIGGER klin_klink_otc_line_immutable
BEFORE UPDATE OR DELETE ON pharmacy_otcsaleline
FOR EACH ROW EXECUTE FUNCTION klin_klink_otc_line_immutable();
"""


def apply_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(GUARD_SQL)


def drop_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "DROP TRIGGER IF EXISTS klin_klink_dispense_line_guard ON pharmacy_dispenseline"
        )
        cursor.execute(
            "DROP TRIGGER IF EXISTS klin_klink_otc_line_immutable ON pharmacy_otcsaleline"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("pharmacy", "0003_s12_prescribing_dispensing"),
    ]

    operations = [
        migrations.RunPython(apply_guards, drop_guards),
    ]
