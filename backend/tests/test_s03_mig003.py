import uuid

import pytest

from clinical.models import TriageAssessment, TriageRecord, TriageRecordVersion
from core.clock import local_service_date
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
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import QueueEntry, Visit
from scheduling.queue import create_or_reuse_destination
from tenancy.models import Department

pytestmark = pytest.mark.django_db


@pytest.fixture
def enabled_mig002_target(tenant, enabled_mig001_target):
    with tenant_atomic(tenant.organisation.id):
        inventory_mig002(organisation=tenant.organisation)
        backfill_mig002(organisation=tenant.organisation)
        cutover_mig002(organisation=tenant.organisation)
        return MigrationCutover.objects.get(
            organisation=tenant.organisation, migration_id="MIG-002"
        )


def _stage_entry(tenant, *, queue_type="TRIAGE", department=None, label="S03 Stage"):
    with tenant_atomic(tenant.organisation.id):
        patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no=f"P-S03-{Patient.objects.filter(organisation=tenant.organisation).count() + 1}",
            first_name=label,
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        visit = Visit.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=patient,
            local_service_date=local_service_date(),
            visit_type="OUTPATIENT_NEW",
            opened_by=tenant.user,
        )
        entry, created = create_or_reuse_destination(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            visit=visit,
            department=department or tenant.department,
            queue_type=queue_type,
            source_stage="RECEPTION",
        )
        assert created
    return patient, visit, entry


def _mig003_cycle(tenant):
    with tenant_atomic(tenant.organisation.id):
        inventory_mig003(organisation=tenant.organisation)
        backfill_mig003(organisation=tenant.organisation)
        verify_mig003(organisation=tenant.organisation)
        verify_mig003(organisation=tenant.organisation)
        constrain_mig003(organisation=tenant.organisation)
        cutover_mig003(organisation=tenant.organisation)


def test_s03_mig003_maps_legacy_assessments_and_rolls_back(
    tenant, authed_client, enabled_mig002_target
):
    patient, visit, queue = _stage_entry(tenant, label="Legacy Triage")
    with tenant_atomic(tenant.organisation.id):
        QueueEntry.objects.filter(id=queue.id).update(status="TRIAGED", state="WAITING")
        assessment = TriageAssessment.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            queue_entry=queue,
            patient=patient,
            acuity="URGENT",
            chief_complaint="Fever and cough",
            observations={"temperature_c": "39.8", "pulse": 98},
            assessed_by=tenant.user,
        )
        assessment_id = assessment.id

    _mig003_cycle(tenant)
    with tenant_atomic(tenant.organisation.id):
        record = TriageRecord.objects.get(visit=visit)
        version = TriageRecordVersion.objects.get(record=record, version_number=1)
        assert record.state == "COMPLETED"
        assert record.acuity == "URGENT"
        assert record.completed_by_id == tenant.user.id
        assert record.completed_at is not None
        assert version.content["source_assessment_id"] == str(assessment_id)
        assert version.content["legacy_observations"]["temperature_c"] == "39.8"
        assert len(version.content_hash) == 64
        assert TriageAssessment.objects.filter(
            organisation=tenant.organisation
        ).count() == 1
    # Repeat backfill is idempotent and does not duplicate the head/version.
    with tenant_atomic(tenant.organisation.id):
        backfill_mig003(organisation=tenant.organisation)
        assert TriageRecord.objects.filter(visit=visit).count() == 1
        assert TriageRecordVersion.objects.filter(record=record).count() == 1
        summary = verify_mig003(organisation=tenant.organisation)
        assert summary.unresolved == 0

    with tenant_atomic(tenant.organisation.id):
        rollback_mig003(organisation=tenant.organisation, reason="S03 rollback proof")
        assert target_writes_enabled_mig003(tenant.organisation) is False
        assert TriageRecord.objects.filter(visit=visit).exists()
        assert TriageRecordVersion.objects.filter(record=record).exists()

    fenced = authed_client.post(
        f"/api/v1/clinic/triage/{queue.id}/start/",
        {"expected_version": 1},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s03-after-rollback",
    )
    assert fenced.status_code == 503, fenced.data


def test_s03_mig003_competing_assessment_blocks_activation(
    tenant, enabled_mig002_target
):
    with tenant_atomic(tenant.organisation.id):
        other_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="S03 Second Triage Department",
            code="S03_SECOND",
        )
    patient, visit, first_queue = _stage_entry(tenant, label="Competing One")
    with tenant_atomic(tenant.organisation.id):
        # One Visit with two TRIAGE assessments in different departments.
        second_queue, created = create_or_reuse_destination(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            visit=visit,
            department=other_department,
            queue_type="TRIAGE",
            source_stage="RECEPTION",
            work_identity=f"COMPETING:{uuid.uuid4().hex}",
        )
        assert created
        QueueEntry.objects.filter(id=first_queue.id).update(
            status="TRIAGED", state="WAITING"
        )
        QueueEntry.objects.filter(id=second_queue.id).update(
            status="TRIAGED", state="WAITING"
        )
        for queue in (first_queue, second_queue):
            TriageAssessment.objects.create(
                organisation=tenant.organisation,
                facility=tenant.facility,
                queue_entry=queue,
                patient=visit.patient,
                acuity="ROUTINE",
                chief_complaint="Synthetic complaint",
                assessed_by=tenant.user,
            )
        inventory_mig003(organisation=tenant.organisation)
        backfill_mig003(organisation=tenant.organisation)
        summary = verify_mig003(organisation=tenant.organisation)
        assert summary.unresolved >= 1
        with pytest.raises(ValueError, match="E=0 and two stable"):
            constrain_mig003(organisation=tenant.organisation)
