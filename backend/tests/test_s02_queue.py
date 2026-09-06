from datetime import timedelta
from uuid import uuid4

import pytest

from audit.models import AuditEvent
from core.clock import local_service_date
from core.idempotency import key_hash
from core.migration_reconciliation import (
    backfill_mig002,
    cutover_mig002,
    inventory_mig002,
    rollback_mig002,
    verify_mig002,
)
from core.models import IdempotencyRecord, MigrationCutover, MigrationReconciliation
from core.services import tenant_atomic
from clinical.models import TriageAssessment
from patients.models import Patient
from scheduling.models import QueueEntry, Visit
from scheduling.queue import (
    QueueDomainError,
    QueueStageRefusal,
    call_next_or_exact,
    change_priority,
    create_or_reuse_destination,
    expire_sweep,
    hold,
    no_response,
    mark_ready_to_resume,
    requeue_same_entry,
    resume,
    start_service,
    transfer,
)
from tenancy.models import Department, Facility, Organisation


pytestmark = pytest.mark.django_db


@pytest.fixture
def enabled_mig002_target(tenant, enabled_mig001_target):
    with tenant_atomic(tenant.organisation.id):
        inventory_mig002(organisation=tenant.organisation)
        backfill_mig002(organisation=tenant.organisation)
        cutover_mig002(organisation=tenant.organisation)
    return MigrationCutover.objects.get(
        organisation=tenant.organisation,
        migration_id="MIG-002",
    )


def test_mig002_maps_proven_triage_and_creates_one_consultation_target(tenant, enabled_mig001_target):
    _, visit, source = make_entry(tenant, label="Migrated Triage")
    with tenant_atomic(tenant.organisation.id):
        # Exercise the legacy shadow exactly as it existed before the
        # canonical state column became authoritative.
        QueueEntry.objects.filter(id=source.id).update(
            status="TRIAGED",
            state="WAITING",
            current_stage="CONSULTATION",
        )
        TriageAssessment.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            queue_entry_id=source.id,
            patient_id=source.patient_id,
            assessed_by=tenant.user,
            acuity="URGENT",
        )
        inventory = inventory_mig002(organisation=tenant.organisation)
        assert inventory.exceptions == 0
        backfill = backfill_mig002(organisation=tenant.organisation)
        assert inventory.inspected == 1
        assert backfill.exceptions == 0
        destination = QueueEntry.objects.get(
            organisation=tenant.organisation,
            work_identity=f"MIG-002:CONSULTATION:{source.id}",
        )
        assert QueueEntry.objects.get(id=source.id).state == "COMPLETED"
        assert destination.state == "WAITING"
        assert destination.priority == "URGENT"
        assert backfill.parity_digest
        verification = verify_mig002(organisation=tenant.organisation)
        assert verification.shadow_read_equal, verification.as_dict()
        cutover_mig002(organisation=tenant.organisation)

    assert QueueEntry.objects.filter(
        visit_id=visit.id,
        work_identity=f"MIG-002:CONSULTATION:{source.id}",
    ).count() == 1


def test_mig002_quarantines_ambiguous_triage_without_inference(tenant, enabled_mig001_target):
    _, _, source = make_entry(tenant, label="Ambiguous Triage")
    with tenant_atomic(tenant.organisation.id):
        QueueEntry.objects.filter(id=source.id).update(
            status="TRIAGED",
            state="WAITING",
            current_stage="CONSULTATION",
        )
        inventory = inventory_mig002(organisation=tenant.organisation)
        assert inventory.exceptions == 1
        backfill = backfill_mig002(organisation=tenant.organisation)
        assert backfill.exceptions == 1
        evidence = MigrationReconciliation.objects.get(
            organisation=tenant.organisation,
            migration_id="MIG-002",
            legacy_pk=str(source.id),
        )
        assert evidence.resolution_state == "PENDING"
        assert evidence.evidence_codes == ["TRIAGE_ASSESSMENT_MISMATCH"]
        assert not QueueEntry.objects.filter(
            work_identity=f"MIG-002:CONSULTATION:{source.id}"
        ).exists()
        verification = verify_mig002(organisation=tenant.organisation)
        assert verification.unresolved == 1
        with pytest.raises(ValueError, match="unresolved state or scope evidence"):
            cutover_mig002(organisation=tenant.organisation)


def make_entry(tenant, *, label="Queue Patient", department=None, queue_type="TRIAGE", priority="ROUTINE"):
    with tenant_atomic(tenant.organisation.id):
        patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no=f"P-S02-{Patient.objects.filter(organisation=tenant.organisation).count() + 1}",
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
            priority=priority,
            source_stage="RECEPTION",
        )
        assert created
    return patient, visit, entry


def test_mig002_requires_two_stable_scans_and_rolls_back_without_removing_rows(tenant, enabled_mig002_target):
    assert enabled_mig002_target.target_reads_enabled
    assert enabled_mig002_target.target_writes_enabled
    with tenant_atomic(tenant.organisation.id):
        patient, visit, entry = make_entry(tenant)
        rollback_mig002(organisation=tenant.organisation, actor=tenant.user, reason="S02 rollback proof")
    assert QueueEntry.objects.filter(id=entry.id).exists()
    assert MigrationCutover.objects.get(
        organisation=tenant.organisation,
        migration_id="MIG-002",
    ).target_writes_enabled is False


def test_call_next_is_idempotent_and_persists_a_safe_audit(tenant, authed_client, enabled_mig002_target):
    patient, visit, entry = make_entry(tenant)
    first = authed_client.post(
        "/api/v1/clinic/queue/call-next/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-call-next-1",
    )
    replay = authed_client.post(
        "/api/v1/clinic/queue/call-next/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-call-next-1",
    )
    assert first.status_code == replay.status_code == 200, first.data
    assert first.data == replay.data
    assert replay["Idempotent-Replay"] == "true"
    assert first.data["queue_entry_id"] == str(entry.id)
    assert first.data["state"] == "CALLED"
    with tenant_atomic(tenant.organisation.id):
        record = IdempotencyRecord.objects.get(
            organisation=tenant.organisation,
            operation="CMD-013",
            key_hash=key_hash("s02-call-next-1"),
        )
        assert record.response_body == first.data
        assert "patient" not in str(record.response_body).lower()
    assert AuditEvent.objects.filter(
        organisation=tenant.organisation,
        entity_id=str(entry.id),
        event_code="QUEUE_CALLED",
    ).count() == 1
    assert QueueEntry.objects.get(id=entry.id).called_by_id == tenant.user.id


def test_direct_start_records_both_semantic_transitions_and_stage_refusal_stays_called(tenant, enabled_mig002_target):
    patient, visit, entry = make_entry(tenant, label="Direct Start")
    with tenant_atomic(tenant.organisation.id):
        started = start_service(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
        )
        assert started.state == "IN_SERVICE"
        assert started.called_at == started.service_started_at == started.started_at
        assert started.called_by_id == started.served_by_id == tenant.user.id
    assert AuditEvent.objects.filter(entity_id=str(entry.id), event_code="QUEUE_CALLED").exists()
    assert AuditEvent.objects.filter(entity_id=str(entry.id), event_code="QUEUE_SERVICE_STARTED").exists()

    _, _, refused_entry = make_entry(tenant, label="Refused Start")
    with tenant_atomic(tenant.organisation.id):
        refused = start_service(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=refused_entry.id,
            stage_callback=lambda **_: (_ for _ in ()).throw(QueueStageRefusal("workspace unavailable")),
        )
        assert refused.state == "CALLED"
    assert QueueEntry.objects.get(id=refused_entry.id).state == "CALLED"
    assert not AuditEvent.objects.filter(
        entity_id=str(refused_entry.id),
        event_code="QUEUE_SERVICE_STARTED",
    ).exists()


def test_queue_state_guards_priority_hold_resume_and_transfer(tenant, enabled_mig002_target):
    _, _, entry = make_entry(tenant, label="State Guard")
    with tenant_atomic(tenant.organisation.id):
        with pytest.raises(QueueDomainError) as invalid_transfer:
            transfer(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                source_queue_entry_id=entry.id,
                target_department_id=tenant.department.id,
                target_queue_type="TRIAGE",
            )
        assert invalid_transfer.value.code == "INVALID_STATE"
        change_priority(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
            priority="EMERGENCY",
            reason="SpO2 recheck is low",
        )
        start_service(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
        )
        held = hold(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
            hold_reason="AWAITING_RESULTS",
            hold_ref="ORDER-S02-1",
        )
        assert held.state == "ON_HOLD"
        consultation = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Consultation",
            code="CONSULTATION",
        )
        _, downstream_created = create_or_reuse_destination(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            visit=Visit.objects.get(id=entry.visit_id),
            department=consultation,
            queue_type="CONSULTATION",
            source_stage="TRIAGE",
            priority="EMERGENCY",
        )
        assert downstream_created
        ready = mark_ready_to_resume(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
        )
        assert ready.state == "READY_TO_RESUME"
        resumed = resume(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
        )
        assert resumed.state == "IN_SERVICE"
        pharmacy = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Pharmacy",
            code="PHARMACY",
        )
        source, destination = transfer(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            source_queue_entry_id=entry.id,
            target_department_id=pharmacy.id,
            target_queue_type="PHARMACY",
            handoff_note="Synthetic handoff",
            reason="ROUTED_IN_ERROR",
        )
        assert source.state == "TRANSFERRED"
        assert destination.state == "WAITING"
        assert destination.notes == "Synthetic handoff"
    assert AuditEvent.objects.filter(entity_id=str(entry.id), event_code="QUEUE_PRIORITY_CHANGED").exists()
    assert AuditEvent.objects.filter(entity_id=str(entry.id), event_code="QUEUE_HELD").exists()
    assert AuditEvent.objects.filter(entity_id=str(entry.id), event_code="QUEUE_RESUMED").exists()
    assert AuditEvent.objects.filter(entity_id=str(entry.id), event_code="QUEUE_TRANSFERRED").exists()


def test_no_response_preserves_queue_time_and_requeue_preserves_same_entry(tenant, enabled_mig002_target):
    _, _, entry = make_entry(tenant, label="No Response")
    with tenant_atomic(tenant.organisation.id):
        called = call_next_or_exact(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
        )
        original_queue_time = called.queue_time
        requeued = no_response(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
            outcome="REQUEUE",
            observed_at=called.called_at + timedelta(minutes=1),
        )
        assert requeued.state == "WAITING"
        assert requeued.queue_time == original_queue_time
        assert requeued.call_attempts == 1
        called_again = call_next_or_exact(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
        )
        no_show = no_response(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
            outcome="NO_SHOW",
            emergency_acknowledged=True,
            observed_at=called_again.called_at + timedelta(minutes=2),
        )
        assert no_show.state == "NO_SHOW"
        same = requeue_same_entry(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
            reason="Patient returned to reception",
        )
        assert same.id == entry.id
        assert same.state == "WAITING"
    assert QueueEntry.objects.filter(id=entry.id).count() == 1
    assert AuditEvent.objects.filter(entity_id=str(entry.id), event_code="QUEUE_REQUEUED").exists()


def test_operational_projection_is_scoped_ordered_and_public_board_fails_closed(tenant, authed_client, enabled_mig002_target):
    _, _, routine = make_entry(tenant, label="Routine")
    _, _, emergency = make_entry(tenant, label="Emergency", priority="EMERGENCY")
    response = authed_client.get("/api/v1/clinic/queue/operational/?page_size=25")
    assert response.status_code == 200, response.data
    assert response.data["entries"][0]["id"] == str(emergency.id)
    assert response.data["row_count"] == 2
    assert response.data["entries"][0]["patient_no"]
    assert "diagnosis" not in str(response.data).lower()
    assert "clinical_notes" not in str(response.data).lower()
    board = authed_client.get("/api/v1/clinic/queue/board/")
    assert board.status_code == 422
    assert board.data["code"] == "PUBLIC_BOARD_NOT_CONFIGURED"


def test_operational_projection_denies_another_department_scope(tenant, authed_client, enabled_mig002_target):
    _, _, own = make_entry(tenant, label="Own Department")
    with tenant_atomic(tenant.organisation.id):
        other_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Other Department",
            code="OTHER",
        )
    _, _, other = make_entry(tenant, label="Other Department", department=other_department)

    response = authed_client.get("/api/v1/clinic/queue/operational/")
    assert response.status_code == 200, response.data
    assert [row["id"] for row in response.data["entries"]] == [str(own.id)]

    denied = authed_client.get(
        f"/api/v1/clinic/queue/operational/?department_id={other.department_id}"
    )
    assert denied.status_code == 403


def test_operational_projection_is_tenant_bounded(tenant, authed_client, enabled_mig002_target):
    own = make_entry(tenant, label="Tenant A")
    other_organisation = Organisation.objects.create(
        name="Other S02 Clinic",
        slug=f"other-s02-{uuid4().hex[:8]}",
    )
    with tenant_atomic(other_organisation.id):
        other_facility = Facility.objects.create(
            organisation=other_organisation,
            name="Other S02 Facility",
            code="OTHER-S02",
        )
        other_department = Department.objects.create(
            organisation=other_organisation,
            facility=other_facility,
            name="Other S02 Department",
            code="OTHER",
        )
        other_patient = Patient.objects.create(
            organisation=other_organisation,
            patient_no="P-OTHER-S02",
            first_name="Other",
            last_name="Tenant",
            sex="UNKNOWN",
        )
        other_visit = Visit.objects.create(
            organisation=other_organisation,
            facility=other_facility,
            patient=other_patient,
            local_service_date=local_service_date(),
            visit_type="OUTPATIENT_NEW",
            opened_by=tenant.user,
        )
        other_entry = QueueEntry.objects.create(
            organisation=other_organisation,
            facility=other_facility,
            visit=other_visit,
            patient=other_patient,
            department=other_department,
            queue_date=other_visit.local_service_date,
            sequence=1,
            queue_type="TRIAGE",
            work_identity=f"VISIT:{other_visit.id}:TRIAGE",
            status="WAITING",
            state="WAITING",
            current_stage="TRIAGE",
            source_stage="RECEPTION",
            source_event_id=f"VISIT:{other_visit.id}:TRIAGE",
        )

    response = authed_client.get("/api/v1/clinic/queue/operational/")
    assert response.status_code == 200, response.data
    assert [row["id"] for row in response.data["entries"]] == [str(own[2].id)]
    assert str(other_entry.id) not in response.content.decode()


def test_expiry_sweep_retires_prior_day_queue_and_closes_only_zero_record_visit(tenant, enabled_mig002_target):
    _, visit, entry = make_entry(tenant, label="Rollover")
    yesterday = visit.local_service_date - timedelta(days=1)
    with tenant_atomic(tenant.organisation.id):
        QueueEntry.objects.filter(id=entry.id).update(queue_date=yesterday)
        result = expire_sweep(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            local_service_day=visit.local_service_date,
        )
        assert entry.id in result.expired_entry_ids
        assert visit.id in result.closed_visit_ids
    assert QueueEntry.objects.get(id=entry.id).state == "EXPIRED"
    assert Visit.objects.get(id=visit.id).state == "CLOSED"
