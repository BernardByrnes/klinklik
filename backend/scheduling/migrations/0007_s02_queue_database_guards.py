"""Owner-run database guards for the canonical QueueEntry state.

The MIG-002 expansion in ``0005_s02_mig002_canonical_queueentry`` declares the
four queue constraints in migration state through ``SeparateDatabaseAndState``
with an empty database operation list. Creating them needs DDL privileges the
application role deliberately does not have, and a global ``SET NOT NULL``
would impose one organisation's cutover on every other tenant.

This migration is run by the schema owner through ``manage.py migrate``. It
installs the four database objects once, plus a per-organisation guard that
requires a canonical state only after that organisation's own MIG-002 cutover.
``QueueEntry.state`` stays nullable at the schema level; the database-wide
non-null contract belongs to a later contract step.
"""

from django.db import migrations


APPLY_SQL = """
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'queue_entry_state_valid'
          AND conrelid = 'scheduling_queueentry'::regclass
    ) THEN
        ALTER TABLE scheduling_queueentry
        ADD CONSTRAINT queue_entry_state_valid
        CHECK (state IN ('WAITING_PAYMENT','WAITING','CALLED','IN_SERVICE',
                         'ON_HOLD','READY_TO_RESUME','COMPLETED','TRANSFERRED',
                         'CANCELLED','LWBS','NO_SHOW','EXPIRED'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'queue_entry_attempt_counts_nonnegative'
          AND conrelid = 'scheduling_queueentry'::regclass
    ) THEN
        ALTER TABLE scheduling_queueentry
        ADD CONSTRAINT queue_entry_attempt_counts_nonnegative
        CHECK (call_attempts >= 0 AND no_show_count >= 0);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uniq_active_queue_visit_department
ON scheduling_queueentry (organisation_id, visit_id, department_id)
WHERE visit_id IS NOT NULL AND state IN
('WAITING_PAYMENT','WAITING','CALLED','IN_SERVICE','ON_HOLD','READY_TO_RESUME');

CREATE UNIQUE INDEX IF NOT EXISTS uniq_in_service_queue_visit
ON scheduling_queueentry (organisation_id, visit_id)
WHERE visit_id IS NOT NULL AND state = 'IN_SERVICE';

CREATE OR REPLACE FUNCTION klin_klink_queue_state_guard()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE target_active boolean;
BEGIN
    IF NEW.state IS NOT NULL THEN
        RETURN NEW;
    END IF;
    SELECT (target_reads_enabled OR target_writes_enabled) INTO target_active
    FROM core_migrationcutover
    WHERE organisation_id = NEW.organisation_id
      AND migration_id = 'MIG-002';
    IF target_active THEN
        RAISE EXCEPTION 'QueueEntry state is required after MIG-002 cutover'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS klin_klink_queue_state ON scheduling_queueentry;
CREATE TRIGGER klin_klink_queue_state
BEFORE INSERT OR UPDATE OF state, organisation_id
ON scheduling_queueentry FOR EACH ROW EXECUTE FUNCTION klin_klink_queue_state_guard();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS klin_klink_queue_state ON scheduling_queueentry;
DROP FUNCTION IF EXISTS klin_klink_queue_state_guard();
DROP INDEX IF EXISTS uniq_in_service_queue_visit;
DROP INDEX IF EXISTS uniq_active_queue_visit_department;
ALTER TABLE scheduling_queueentry DROP CONSTRAINT IF EXISTS queue_entry_attempt_counts_nonnegative;
ALTER TABLE scheduling_queueentry DROP CONSTRAINT IF EXISTS queue_entry_state_valid;
"""


def apply_queue_database_guards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(APPLY_SQL)


def reverse_queue_database_guards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_s01_mig001_durable_proof"),
        ("scheduling", "0006_s02_stale_review_flags"),
    ]

    operations = [
        migrations.RunPython(apply_queue_database_guards, reverse_queue_database_guards),
    ]
