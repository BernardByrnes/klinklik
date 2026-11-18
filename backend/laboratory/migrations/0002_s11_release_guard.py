from django.db import migrations


RELEASE_GUARD = """
CREATE OR REPLACE FUNCTION klin_klink_lab_result_version_immutable()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Laboratory result versions are append-only' USING ERRCODE = '55006';
    END IF;
    IF OLD.released THEN
        RAISE EXCEPTION 'A released laboratory result version is immutable' USING ERRCODE = '55006';
    END IF;
    IF (to_jsonb(OLD) - 'released' - 'released_at' - 'verified_by_id' - 'verified_at' - 'updated_at')
       <> (to_jsonb(NEW) - 'released' - 'released_at' - 'verified_by_id' - 'verified_at' - 'updated_at') THEN
        RAISE EXCEPTION 'Laboratory result values are immutable' USING ERRCODE = '55006';
    END IF;
    RETURN NEW;
END;
$$;
"""


def apply_guard(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(RELEASE_GUARD)


class Migration(migrations.Migration):
    dependencies = [("laboratory", "0001_s11_lab_foundations")]
    operations = [migrations.RunPython(apply_guard, migrations.RunPython.noop)]
