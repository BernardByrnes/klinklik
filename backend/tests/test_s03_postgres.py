import os
from concurrent.futures import ThreadPoolExecutor
import threading
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection

from application.clinical.commands import (
    triage_record_complete,
    triage_record_save,
    triage_record_start,
)
from audit.models import AuditEvent
from clinical.models import (
    PatientAllergyState,
    TriageAssessment,
    TriageRecord,
    TriageRecordVersion,
)
from core.clock import local_service_date
from core.errors import CanonicalError
from core.mig003 import (
    backfill_mig003,
    constrain_mig003,
    cutover_mig003,
    inventory_mig003,
    rollback_mig003,
    target_writes_enabled_mig003,
    verify_mig003,
)
from core.migration_reconciliation import (
    backfill_mig002,
    cutover_mig002,
    inventory_mig002,
)
from core.models import MigrationCutover
from core.rls import rls_status
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import QueueEntry, Visit
from scheduling.queue import create_or_reuse_destination
from tenancy.models import Organisation

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="S-03 PostgreSQL proof gate"),
]

OWNER_DSN = os.getenv("S02_OWNER_DSN")


@pytest.fixture
def enabled_mig002_target(tenant, enabled_mig001_target):
    with tenant_atomic(tenant.organisation.id):
        inventory_mig002(organisation=tenant.organisation)
        backfill_mig002(organisation=tenant.organisation)
        cutover_mig002(organisation=tenant.organisation)
        return MigrationCutover.objects.get(
            organisation=tenant.organisation, migration_id="MIG-002"
        )


@pytest.fixture
def enabled_mig003_target(tenant, enabled_mig002_target):
    with tenant_atomic(tenant.organisation.id):
        inventory_mig003(organisation=tenant.organisation)
        backfill_mig003(organisation=tenant.organisation)
        verify_mig003(organisation=tenant.organisation)
        verify_mig003(organisation=tenant.organisation)
        constrain_mig003(organisation=tenant.organisation)
        cutover_mig003(organisation=tenant.organisation)
        return MigrationCutover.objects.get(
            organisation=tenant.organisation, migration_id="MIG-003"
        )


def _synthetic_queue(tenant, *, label="S03 PG"):
    with tenant_atomic(tenant.organisation.id):
        patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no=f"P-PG-S03-{uuid4().hex[:8]}",
            first_name=label,
            last_name="Synthetic",
            sex="UNKNOWN",
            date_of_birth=local_service_date().replace(year=1990),
        )
        visit = Visit.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=patient,
            local_service_date=local_service_date(),
            visit_type="OUTPATIENT_NEW",
            opened_by=tenant.user,
        )
        queue, created = create_or_reuse_destination(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            visit=visit,
            department=tenant.department,
            queue_type="TRIAGE",
            source_stage="RECEPTION",
        )
        assert created
        PatientAllergyState.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=patient,
            status="NKA",
            revision=1,
            updated_by=tenant.user,
        )
    return patient, visit, queue


def _started_draft(tenant):
    patient, visit, queue = _synthetic_queue(tenant)
    with tenant_atomic(tenant.organisation.id):
        started = triage_record_start(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=queue.id,
            expected_queue_version=queue.version,
        )
        record = triage_record_save(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            triage_record_id=started.record.id,
            payload={
                "presenting_complaints": [{"text": "Synthetic PG complaint"}],
                "observation": {"pulse": 88, "temperature_c": "38.1"},
                "acuity": "URGENT",
            },
            expected_version=started.record.row_version,
        )
    return patient, visit, started.queue, record


def test_pg_s03_tables_are_force_rls_and_guarded(tenant, enabled_mig003_target):
    status = rls_status()
    assert status["enforced"] is True
    assert status["role"]["superuser"] is False
    assert status["role"]["bypass_rls"] is False
    tables = {table["name"]: table for table in status["tables"]}
    for name in ("clinical_triagerecord", "clinical_triagerecordversion"):
        table = tables[name]
        assert table["rowsecurity"] is True
        assert table["force"] is True
        assert table["tenant_policy"] is True
        assert table["owner"] != status["role"]["name"]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tgname FROM pg_trigger
            WHERE tgrelid IN ('clinical_triagerecord'::regclass,
                              'clinical_triagerecordversion'::regclass,
                              'clinical_vitalsobservation'::regclass)
              AND NOT tgisinternal AND tgenabled = 'O'
            """
        )
        assert {
            "klin_klink_triage_record_state",
            "klin_klink_triage_version_immutable",
            "klin_klink_vitals_canonical_guard",
        } <= {row[0] for row in cursor.fetchall()}
        cursor.execute(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'clinical_vitalsobservation'::regclass
              AND conname = 'vital_observation_content_required' AND convalidated
            """
        )
        assert cursor.fetchone() is not None


def test_pg_s03_disabled_guard_blocks_cutover_from_constrained(
    tenant, enabled_mig002_target
):
    if not OWNER_DSN:
        pytest.skip("S02_OWNER_DSN is not configured for the owner-prepared guard proof")
    import psycopg

    organisation = Organisation.objects.get(id=tenant.organisation.id)
    with tenant_atomic(organisation.id):
        inventory_mig003(organisation=organisation)
        backfill_mig003(organisation=organisation)
        verify_mig003(organisation=organisation)
        verify_mig003(organisation=organisation)
        constrain_mig003(organisation=organisation)
        constrained = MigrationCutover.objects.get(
            organisation=organisation, migration_id="MIG-003"
        )
        assert constrained.phase == "CONSTRAINED"
        assert constrained.target_reads_enabled is False
        assert constrained.target_writes_enabled is False
        constrained_version = constrained.version

    with psycopg.connect(OWNER_DSN, autocommit=True) as owner:
        with owner.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            assert cursor.fetchone()[0] == connection.settings_dict["NAME"], (
                "S02_OWNER_DSN must target the disposable test database"
            )
        owner.execute(
            "ALTER TABLE clinical_vitalsobservation DISABLE TRIGGER klin_klink_vitals_canonical_guard"
        )
        try:
            with pytest.raises(ValueError) as refused:
                with tenant_atomic(organisation.id):
                    cutover_mig003(organisation=organisation)
            assert "klin_klink_vitals_canonical_guard" in str(refused.value)
            assert "migrate clinical 0011" in str(refused.value)
        finally:
            owner.execute(
                "ALTER TABLE clinical_vitalsobservation ENABLE TRIGGER klin_klink_vitals_canonical_guard"
            )

    with tenant_atomic(organisation.id):
        unchanged = MigrationCutover.objects.get(
            organisation=organisation, migration_id="MIG-003"
        )
        assert unchanged.phase == "CONSTRAINED"
        assert unchanged.target_reads_enabled is False
        assert unchanged.target_writes_enabled is False
        assert unchanged.version == constrained_version
        cutover_mig003(organisation=organisation)
        activated = MigrationCutover.objects.get(
            organisation=organisation, migration_id="MIG-003"
        )
        assert activated.phase == "CUTOVER"
        assert activated.target_reads_enabled is True
        assert activated.target_writes_enabled is True


def test_pg_s03_concurrent_start_has_one_draft(tenant, enabled_mig002_target):
    patient, visit, queue = _synthetic_queue(tenant)
    barrier = threading.Barrier(2)

    def attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(tenant.organisation.id):
                outcome = triage_record_start(
                    organisation=tenant.organisation,
                    facility=tenant.facility,
                    actor=tenant.user,
                    queue_entry_id=queue.id,
                    expected_queue_version=queue.version,
                )
                return ("ok", str(outcome.record.id))
        except CanonicalError as exc:
            return ("error", exc.code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: attempt(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    with tenant_atomic(tenant.organisation.id):
        records = list(TriageRecord.objects.filter(visit=visit))
        assert len(records) == 1
        assert records[0].state == "DRAFT"
        assert QueueEntry.objects.get(id=queue.id).state == "IN_SERVICE"
        assert AuditEvent.objects.filter(
            entity_id=str(records[0].id), event_code="TRIAGE_STARTED"
        ).count() == 1


def test_pg_s03_concurrent_complete_has_one_version_and_destination(
    tenant, enabled_mig002_target
):
    patient, visit, source, record = _started_draft(tenant)
    barrier = threading.Barrier(2)
    expected_record_version = record.row_version
    expected_queue_version = source.version

    def attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(tenant.organisation.id):
                outcome = triage_record_complete(
                    organisation=tenant.organisation,
                    facility=tenant.facility,
                    actor=tenant.user,
                    triage_record_id=record.id,
                    payload={"acuity": "URGENT", "acuity_reason": ""},
                    expected_version=expected_record_version,
                    expected_queue_version=expected_queue_version,
                )
                return ("ok", str(outcome.destination.id))
        except CanonicalError as exc:
            return ("error", exc.code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: attempt(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    assert next(result[1] for result in results if result[0] == "error") in {
        "INVALID_STATE",
        "VERSION_CONFLICT",
    }
    with tenant_atomic(tenant.organisation.id):
        head = TriageRecord.objects.get(id=record.id)
        assert head.state == "COMPLETED"
        assert head.current_version == 1
        assert TriageRecordVersion.objects.filter(record=head).count() == 1
        destinations = QueueEntry.objects.filter(
            visit=visit, queue_type="CONSULTATION"
        )
        assert destinations.count() == 1
        assert destinations.first().state == "WAITING"
        assert QueueEntry.objects.get(id=source.id).state == "COMPLETED"
        assert AuditEvent.objects.filter(
            entity_id=str(record.id), event_code="TRIAGE_COMPLETED"
        ).count() == 1


def test_pg_s03_legacy_backfill_is_idempotent_and_rollback_retains(
    tenant, enabled_mig002_target
):
    patient, visit, queue = _synthetic_queue(tenant, label="Legacy PG Triage")
    with tenant_atomic(tenant.organisation.id):
        QueueEntry.objects.filter(id=queue.id).update(status="TRIAGED", state="WAITING")
        assessment = TriageAssessment.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            queue_entry=queue,
            patient=patient,
            acuity="ROUTINE",
            chief_complaint="Legacy PG complaint",
            observations={"pulse": 70},
            assessed_by=tenant.user,
        )
        assessment_id = assessment.id
        inventory_mig003(organisation=tenant.organisation)
        backfill_mig003(organisation=tenant.organisation)
        backfill_mig003(organisation=tenant.organisation)
        record = TriageRecord.objects.get(visit=visit)
        assert TriageRecord.objects.filter(visit=visit).count() == 1
        assert TriageRecordVersion.objects.filter(record=record).count() == 1
        version = TriageRecordVersion.objects.get(record=record)
        assert version.content["source_assessment_id"] == str(assessment_id)
        verify_mig003(organisation=tenant.organisation)
        verify_mig003(organisation=tenant.organisation)
        constrain_mig003(organisation=tenant.organisation)
        cutover_mig003(organisation=tenant.organisation)
        rollback_mig003(organisation=tenant.organisation, reason="S03 PG rollback")
        assert target_writes_enabled_mig003(tenant.organisation) is False
        assert TriageRecord.objects.filter(id=record.id).exists()
        assert TriageRecordVersion.objects.filter(id=version.id).exists()
        assert TriageAssessment.objects.filter(id=assessment_id).exists()
