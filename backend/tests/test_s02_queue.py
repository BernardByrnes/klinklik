from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from accounts.models import Permission, Role, RolePermission, User, UserFacilityRole
from audit.models import AuditEvent
from core.clock import local_service_date
from core.errors import CanonicalError
from core.idempotency import fingerprint_for_request, key_hash
from core.migration_reconciliation import (
    backfill_mig002,
    constrain_mig002,
    cutover_mig002,
    inventory_mig002,
    legacy_writes_enabled_mig002,
    mig002_rollback_active,
    resolve_mig002_reconciliation,
    rollback_mig001,
    rollback_mig002,
    target_writes_enabled_mig002,
    verify_mig002,
)
from core.models import IdempotencyRecord, MigrationCutover, MigrationReconciliation
from core.services import tenant_atomic
from clinical.models import Encounter, EncounterCoAuthor, TriageAssessment
from patients.models import Patient
from scheduling.models import QueueEntry, Visit
from scheduling.queue import (
    QueueDomainError,
    QueueStageRefusal,
    call_next_or_exact,
    cancel,
    change_priority,
    create_or_reuse_destination,
    expire_sweep,
    hold,
    no_response,
    mark_ready_to_resume,
    requeue_same_entry,
    resume,
    start_service,
    takeover,
    transfer,
)
from scheduling.operational_queries import (
    operational_queue_projection,
    public_board_projection,
    queue_priority_projection,
    supervisor_queue_projection,
)
from scheduling.services import check_in_patient
from tenancy.models import Department, Facility, FacilityWorkflowPolicy, Organisation


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


def test_mig002_reuses_only_the_authoritative_consultation_destination(tenant, enabled_mig001_target):
    _, visit, source = make_entry(tenant, label="Existing Consultation")
    with tenant_atomic(tenant.organisation.id):
        QueueEntry.objects.filter(id=source.id).update(
            status="TRIAGED",
            state="COMPLETED",
            current_stage="CONSULTATION",
        )
        TriageAssessment.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            queue_entry_id=source.id,
            patient_id=source.patient_id,
            assessed_by=tenant.user,
            acuity="ROUTINE",
        )
        _, created = create_or_reuse_destination(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            visit=visit,
            department=tenant.department,
            queue_type="CONSULTATION",
            source_stage="TRIAGE",
        )
        assert created
        existing = QueueEntry.objects.get(
            visit=visit,
            queue_type="CONSULTATION",
        )
        # The destination may predate MIG-002's nullable canonical fields.
        QueueEntry.objects.filter(id=existing.id).update(state=None)
        QueueEntry.objects.filter(id=source.id).update(state="WAITING")

        inventory = inventory_mig002(organisation=tenant.organisation)
        assert inventory.exceptions == 0
        backfill_mig002(organisation=tenant.organisation)

        assert not QueueEntry.objects.filter(
            work_identity=f"MIG-002:CONSULTATION:{source.id}"
        ).exists()
        evidence = MigrationReconciliation.objects.get(
            organisation=tenant.organisation,
            migration_id="MIG-002",
            legacy_pk=str(source.id),
        ) if MigrationReconciliation.objects.filter(
            organisation=tenant.organisation,
            migration_id="MIG-002",
            legacy_pk=str(source.id),
        ).exists() else None
        assert evidence is None
        verification = verify_mig002(organisation=tenant.organisation)
        assert verification.unresolved == 0, verification.as_dict()
        assert verification.blocker_checks_passed is True
        target_refs = (MigrationCutover.objects.get(
            organisation=tenant.organisation,
            migration_id="MIG-002",
        ).deterministic_row_evidence or {})[
            f"scheduling_queueentry:{source.id}"
        ]["target_refs"]
        assert target_refs["consultation_queue_id"] == str(existing.id)
        assert QueueEntry.objects.get(id=existing.id).state == "WAITING"


def test_mig002_source_hash_excludes_added_target_stage_fields(tenant, enabled_mig001_target):
    _, _, source = make_entry(tenant, label="Legacy Source Fields")
    with tenant_atomic(tenant.organisation.id):
        QueueEntry.objects.filter(id=source.id).update(
            state=None,
            work_identity="",
            source_event_id="",
            source_stage="",
        )
        inventory = inventory_mig002(organisation=tenant.organisation)
        backfill = backfill_mig002(organisation=tenant.organisation)
        assert inventory.exceptions == 0
        assert backfill.exceptions == 0
        verification = verify_mig002(organisation=tenant.organisation)
        assert verification.unresolved == 0, verification.as_dict()
        assert verification.shadow_read_equal is True
        cutover = cutover_mig002(organisation=tenant.organisation)
        assert cutover.phase == "CUTOVER"


def test_mig002_quarantines_cross_department_consultation_destination(tenant, enabled_mig001_target):
    _, visit, source = make_entry(tenant, label="Wrong Consultation Scope")
    with tenant_atomic(tenant.organisation.id):
        other_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Other Consultation",
            code="OTHER_CONSULTATION",
        )
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
            acuity="ROUTINE",
        )
        QueueEntry.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            visit=visit,
            patient=source.patient,
            department=other_department,
            queue_date=visit.local_service_date,
            sequence=999,
            queue_type="CONSULTATION",
            work_identity=f"OTHER-CONSULTATION:{source.id}",
            status="WAITING",
            state="WAITING",
            current_stage="CONSULTATION",
            source_stage="TRIAGE",
        )
        inventory = inventory_mig002(organisation=tenant.organisation)
        assert inventory.exceptions == 1
        evidence = MigrationReconciliation.objects.get(
            organisation=tenant.organisation,
            migration_id="MIG-002",
            legacy_pk=str(source.id),
        )
        assert evidence.evidence_codes == ["UNKNOWN_DEPARTMENT_WORK_IDENTITY"]
        backfill = backfill_mig002(organisation=tenant.organisation)
        assert backfill.exceptions == 1
        assert not QueueEntry.objects.filter(
            work_identity=f"MIG-002:CONSULTATION:{source.id}"
        ).exists()


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
        assert verification.blocker_checks_passed is False
        with pytest.raises(ValueError, match="unresolved state or scope evidence"):
            cutover_mig002(organisation=tenant.organisation)


def test_queue_save_preserves_legacy_state_drift_for_reconciliation(tenant, enabled_mig001_target):
    _, _, source = make_entry(tenant, label="Save Drift")
    with tenant_atomic(tenant.organisation.id):
        QueueEntry.objects.filter(id=source.id).update(status="TRIAGED", state="WAITING")
        drifted = QueueEntry.objects.get(id=source.id)
        assert drifted.legacy_state_drift == "LEGACY_CANONICAL_STATE_MISMATCH"
        drifted.save(update_fields=["status"])
        drifted.refresh_from_db()
        assert drifted.state == "WAITING"


def test_mig002_unknown_legacy_state_stays_unclassified_and_blocks(tenant, enabled_mig001_target):
    _, _, source = make_entry(tenant, label="Unknown Legacy State")
    with tenant_atomic(tenant.organisation.id):
        QueueEntry.objects.filter(id=source.id).update(status="UNSUPPORTED_LEGACY", state=None)
        inventory = inventory_mig002(organisation=tenant.organisation)
        backfill = backfill_mig002(organisation=tenant.organisation)
        assert inventory.exceptions == 1
        assert backfill.exceptions == 1
        assert QueueEntry.objects.get(id=source.id).state is None
        verification = verify_mig002(organisation=tenant.organisation)
        assert verification.unresolved == 1
        assert verification.blocker_checks_passed is False


def test_mig002_reconcile_applies_corrected_target_and_audits(tenant, enabled_mig001_target):
    _, _, source = make_entry(tenant, label="Reconciled Triage")
    with tenant_atomic(tenant.organisation.id):
        QueueEntry.objects.filter(id=source.id).update(
            status="TRIAGED",
            state="WAITING",
            current_stage="CONSULTATION",
        )
        inventory_mig002(organisation=tenant.organisation)
        evidence = MigrationReconciliation.objects.get(
            organisation=tenant.organisation,
            migration_id="MIG-002",
            legacy_pk=str(source.id),
        )
        backfill_mig002(organisation=tenant.organisation)
        TriageAssessment.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            queue_entry_id=source.id,
            patient_id=source.patient_id,
            assessed_by=tenant.user,
            acuity="ROUTINE",
        )
        resolved = resolve_mig002_reconciliation(
            organisation=tenant.organisation,
            reconciliation_id=evidence.id,
            actor=tenant.user,
            reason="Assessment evidence corrected",
        )
        source.refresh_from_db()
        assert resolved.resolution_state == "RESOLVED"
        assert source.state == "COMPLETED"
        assert QueueEntry.objects.filter(
            work_identity=f"MIG-002:CONSULTATION:{source.id}",
            state="WAITING",
        ).exists()
        verification = verify_mig002(organisation=tenant.organisation)
        assert verification.unresolved == 0, verification.as_dict()
        assert verification.blocker_checks_passed is True
        cutover_mig002(organisation=tenant.organisation)
    assert AuditEvent.objects.filter(
        entity_id=str(evidence.id),
        event_code="MIGRATION_RECONCILIATION_RESOLVED",
    ).exists()


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


def test_mig002_rollback_reenables_the_legacy_writer_without_down_mapping(tenant, enabled_mig002_target):
    with tenant_atomic(tenant.organisation.id):
        patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no="P-S02-ROLLBACK",
            first_name="Legacy",
            last_name="Rollback",
            sex="UNKNOWN",
        )
        constrain_mig002(organisation=tenant.organisation)
        rollback_mig002(organisation=tenant.organisation, actor=tenant.user, reason="S02 rollback proof")
        assert legacy_writes_enabled_mig002(tenant.organisation)
        legacy_entry = check_in_patient(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            patient_id=patient.id,
        )
    assert legacy_entry.status == "WAITING"
    assert legacy_entry.state == "WAITING"
    assert legacy_entry.visit_id is not None
    assert Visit.objects.filter(
        id=legacy_entry.visit_id,
        organisation=tenant.organisation,
        facility=tenant.facility,
        patient=patient,
        state="OPEN",
    ).exists()


def test_mig001_rollback_reopens_only_the_s01_writer_after_mig002_rollback(
    tenant, enabled_mig002_target
):
    with tenant_atomic(tenant.organisation.id):
        patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no="P-S02-MIG001-ROLLBACK",
            first_name="S01",
            last_name="Rollback",
            sex="UNKNOWN",
        )
        rollback_mig002(organisation=tenant.organisation, actor=tenant.user, reason="S02 rollback proof")
        rollback_mig001(organisation=tenant.organisation, reason="S01 rollback proof", actor=tenant.user)
        assert legacy_writes_enabled_mig002(tenant.organisation)
        assert not mig002_rollback_active(tenant.organisation)
        assert not target_writes_enabled_mig002(tenant.organisation)
        entry = check_in_patient(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            patient_id=patient.id,
        )
    assert entry.visit_id is None


def test_mig001_cutover_keeps_the_pre_visit_writer_fenced(tenant, enabled_mig001_target):
    with tenant_atomic(tenant.organisation.id):
        patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no="P-S02-FENCE",
            first_name="Fenced",
            last_name="Legacy",
            sex="UNKNOWN",
        )
        assert legacy_writes_enabled_mig002(tenant.organisation) is False
        with pytest.raises(CanonicalError) as refused:
            check_in_patient(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                patient_id=patient.id,
            )
        assert refused.value.code == "LEGACY_WRITER_DISABLED"
    assert not QueueEntry.objects.filter(
        organisation=tenant.organisation,
        patient=patient,
    ).exists()


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
        assert started.status == "IN_TRIAGE"
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
    assert AuditEvent.objects.filter(entity_id=str(entry.id), event_code="QUEUE_HANDOFF").exists()


def test_takeover_preserves_encounter_primary_authorship(tenant, enabled_mig002_target):
    _, visit, entry = make_entry(tenant, label="Takeover Authorship")
    with tenant_atomic(tenant.organisation.id):
        started = start_service(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
        )
        encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=entry.patient,
            visit=visit,
            queue_entry=entry,
            encounter_no=f"ENC-S02-{uuid4().hex[:8]}",
            clinician=tenant.user,
            status="OPEN",
        )
        takeover_user = User.objects.create_user("takeover-user", "takeover-password-123")
        role = Role.objects.get(organisation=tenant.organisation, template_code="OWNER_ADMIN")
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=takeover_user,
            role=role,
            facility=tenant.facility,
            department=tenant.department,
        )
        stale_at = timezone.now() - timedelta(minutes=31)
        QueueEntry.objects.filter(id=entry.id).update(last_activity_at=stale_at)
        taken = takeover(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
            new_user_id=takeover_user.id,
            reason="Original clinician unavailable",
            expected_version=started.version,
            observed_at=timezone.now(),
            threshold_minutes=30,
        )
        encounter.refresh_from_db()
    assert taken.assigned_user_id == takeover_user.id
    assert encounter.clinician_id == tenant.user.id
    co_author = EncounterCoAuthor.objects.get(encounter=encounter, user=takeover_user)
    assert co_author.added_by_id == tenant.user.id
    assert len(co_author.reason_hash) == 64
    assert AuditEvent.objects.filter(entity_id=str(entry.id), event_code="QUEUE_TAKEOVER").exists()
    assert AuditEvent.objects.filter(entity_id=str(co_author.id), event_code="ENCOUNTER_CO_AUTHOR_ADDED").exists()


def test_lwbs_is_atomic_with_visit_and_clinical_guards(tenant, enabled_mig002_target):
    _, visit, entry = make_entry(tenant, label="LWBS")
    with tenant_atomic(tenant.organisation.id):
        closed_entry = cancel(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
            reason="LEFT_WITHOUT_BEING_SEEN",
        )
        assert closed_entry.state == "LWBS"
        assert Visit.objects.get(id=visit.id).closure_reason == "LWBS"
    assert AuditEvent.objects.filter(entity_id=str(entry.id), event_code="QUEUE_ENTRY_REMOVED").exists()
    assert AuditEvent.objects.filter(entity_id=str(visit.id), event_code="VISIT_CLOSED_LWBS").exists()

    _, blocked_visit, blocked_entry = make_entry(tenant, label="LWBS Blocked")
    with tenant_atomic(tenant.organisation.id):
        Encounter.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=blocked_entry.patient,
            visit=blocked_visit,
            queue_entry=blocked_entry,
            encounter_no=f"ENC-S02-{uuid4().hex[:8]}",
            clinician=tenant.user,
            status="OPEN",
        )
        with pytest.raises(QueueDomainError) as refused:
            cancel(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                queue_entry_id=blocked_entry.id,
                reason="LEFT_WITHOUT_BEING_SEEN",
            )
        assert refused.value.code == "ENCOUNTER_UNRESOLVED"
    assert QueueEntry.objects.get(id=blocked_entry.id).state == "WAITING"
    assert Visit.objects.get(id=blocked_visit.id).state == "OPEN"


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


def test_s02_projection_states_metrics_and_configured_board_fail_closed(tenant, authed_client, enabled_mig002_target):
    _, _, oldest = make_entry(tenant, label="Oldest")
    _, _, emergency = make_entry(tenant, label="Emergency Escalation", priority="EMERGENCY")
    _, _, payment = make_entry(tenant, label="Waiting Payment")
    _, _, no_response_entry = make_entry(tenant, label="No Response Projection")
    as_of = timezone.now()
    with tenant_atomic(tenant.organisation.id):
        QueueEntry.objects.filter(id=oldest.id).update(
            queue_time=as_of - timedelta(minutes=20),
            last_activity_at=as_of - timedelta(minutes=20),
        )
        QueueEntry.objects.filter(id=emergency.id).update(
            queue_time=as_of - timedelta(minutes=11),
            last_activity_at=as_of - timedelta(minutes=11),
        )
        QueueEntry.objects.filter(id=payment.id).update(
            state="WAITING_PAYMENT",
            status="WAITING_PAYMENT",
        )
        QueueEntry.objects.filter(id=no_response_entry.id).update(
            state="NO_SHOW",
            status="NO_SHOW",
            call_attempts=3,
            no_show_count=2,
        )
        envelope = operational_queue_projection(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            page=1,
            page_size=1,
            as_of=as_of,
            envelope=True,
        )
        assert envelope["entries"][0]["id"] == str(emergency.id)
        assert envelope["entries"][0]["emergency_escalation"] is True
        assert envelope["longest_wait_seconds"] >= 20 * 60
        assert str(payment.id) in {row["id"] for row in queue_priority_projection(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
        )}
        no_response_rows = operational_queue_projection(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            states=["NO_SHOW"],
            as_of=as_of,
        )
        assert no_response_rows[0]["id"] == str(no_response_entry.id)
        assert no_response_rows[0]["follow_up_required"] is True
        assert no_response_rows[0]["final_attempt"] is True
        assert no_response_rows[0]["lwbs_action_available"] is True
        empty_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Empty Department",
            code="EMPTY",
        )
        cards = supervisor_queue_projection(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=None,
            as_of=as_of,
        )
        empty_card = next(card for card in cards if card["department_id"] == str(empty_department.id))
        assert empty_card["waiting_count"] == 0
        assert empty_card["longest_wait_seconds"] == 0
        FacilityWorkflowPolicy.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            public_board_identity_mode="PATIENT_NUMBER",
            updated_by=tenant.user,
        )
        with pytest.raises(CanonicalError) as disabled:
            public_board_projection(
                organisation=tenant.organisation,
                facility=tenant.facility,
                as_of=as_of,
            )
        assert disabled.value.code == "PUBLIC_BOARD_DISABLED"
    board = authed_client.get("/api/v1/clinic/queue/board/")
    assert board.status_code == 403


def test_queue_mutation_requires_current_version(tenant, authed_client, enabled_mig002_target):
    _, _, entry = make_entry(tenant, label="Versioned Queue")
    with tenant_atomic(tenant.organisation.id):
        role = Role.objects.get(organisation=tenant.organisation, template_code="OWNER_ADMIN")
        permission, _ = Permission.objects.get_or_create(
            code="queue.priority.set",
            defaults={"name": "Set queue priority", "sensitivity_tier": "T1"},
        )
        RolePermission.objects.get_or_create(
            organisation=tenant.organisation,
            role=role,
            permission=permission,
        )
    response = authed_client.patch(
        f"/api/v1/clinic/queue/{entry.id}/priority/",
        {"priority": "EMERGENCY", "reason": "Escalation requires review"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-missing-version",
    )
    assert response.status_code == 428, response.data
    assert response.data["code"] == "PRECONDITION_REQUIRED"


def test_queue_claim_grant_does_not_authorize_assignment(tenant, authed_client, enabled_mig002_target):
    _, _, entry = make_entry(tenant, label="Capability Boundary")
    response = authed_client.post(
        f"/api/v1/clinic/queue/{entry.id}/assign/",
        {"target_user_id": str(tenant.user.id), "expected_version": entry.version},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-claim-not-assign",
    )
    assert response.status_code == 403, response.data
    assert QueueEntry.objects.get(id=entry.id).assigned_user_id is None


def test_queue_if_match_rejects_stale_mutation(tenant, authed_client, enabled_mig002_target):
    _, _, entry = make_entry(tenant, label="If Match Queue")
    with tenant_atomic(tenant.organisation.id):
        role = Role.objects.get(organisation=tenant.organisation, template_code="OWNER_ADMIN")
        permission, _ = Permission.objects.get_or_create(
            code="queue.priority.set",
            defaults={"name": "Set queue priority", "sensitivity_tier": "T1"},
        )
        RolePermission.objects.get_or_create(
            organisation=tenant.organisation,
            role=role,
            permission=permission,
        )
    changed = authed_client.patch(
        f"/api/v1/clinic/queue/{entry.id}/priority/",
        {"priority": "URGENT", "reason": "Escalation requires review"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-if-match-current",
        HTTP_IF_MATCH=f'"{entry.version}"',
    )
    assert changed.status_code == 200, changed.data
    assert changed["ETag"] == '"2"'
    stale = authed_client.patch(
        f"/api/v1/clinic/queue/{entry.id}/priority/",
        {"priority": "EMERGENCY", "reason": "Stale escalation attempt"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-if-match-stale",
        HTTP_IF_MATCH=f'"{entry.version}"',
    )
    assert stale.status_code == 412, stale.data
    assert stale.data["code"] == "VERSION_CONFLICT"


def test_queue_capability_is_bound_to_queue_type_scope(tenant, authed_client, enabled_mig002_target):
    _, _, triage = make_entry(tenant, label="Scoped Triage", queue_type="TRIAGE")
    _, _, pharmacy = make_entry(tenant, label="Scoped Pharmacy", queue_type="PHARMACY")
    with tenant_atomic(tenant.organisation.id):
        role = Role.objects.get(organisation=tenant.organisation, template_code="OWNER_ADMIN")
        permission, _ = Permission.objects.get_or_create(
            code="queue.assign:TRIAGE",
            defaults={"name": "Assign triage queue", "sensitivity_tier": "T1"},
        )
        RolePermission.objects.get_or_create(
            organisation=tenant.organisation,
            role=role,
            permission=permission,
        )
    allowed = authed_client.post(
        f"/api/v1/clinic/queue/{triage.id}/assign/",
        {"target_user_id": str(tenant.user.id), "expected_version": triage.version},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-type-scope-allowed",
    )
    assert allowed.status_code == 200, allowed.data
    denied = authed_client.post(
        f"/api/v1/clinic/queue/{pharmacy.id}/assign/",
        {"target_user_id": str(tenant.user.id), "expected_version": pharmacy.version},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-type-scope-denied",
    )
    assert denied.status_code == 403, denied.data


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
        with pytest.raises(QueueDomainError) as invalid_cutoff:
            expire_sweep(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                cutoff=timezone.now(),
            )
        assert invalid_cutoff.value.code == "INVALID_CUTOFF"
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


def test_expiry_sweep_persists_review_for_record_bearing_visit(tenant, enabled_mig002_target):
    _, visit, entry = make_entry(tenant, label="Recordful Rollover")
    yesterday = visit.local_service_date - timedelta(days=1)
    with tenant_atomic(tenant.organisation.id):
        Encounter.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=entry.patient,
            visit=visit,
            queue_entry=entry,
            encounter_no=f"ENC-S02-{uuid4().hex[:8]}",
            clinician=tenant.user,
            status="CLOSED",
        )
        QueueEntry.objects.filter(id=entry.id).update(queue_date=yesterday)
        result = expire_sweep(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            local_service_day=visit.local_service_date,
        )
    visit.refresh_from_db()
    assert entry.id in result.expired_entry_ids
    assert visit.id in result.review_visit_ids
    assert visit.state == "OPEN"
    assert visit.stale_review_required is True
    assert visit.stale_review_reason == "STALE_OPEN"


def test_command_fingerprint_binds_strong_if_match():
    common = {
        "operation": "CMD-013",
        "organisation_id": "org-s02",
        "actor_id": "actor-s02",
        "facility_id": "facility-s02",
        "path": "/api/v1/clinic/queue/call/",
        "payload": {"queue_entry_id": "entry-s02"},
        "target_identifiers": {"pk": "entry-s02"},
    }
    first = fingerprint_for_request(**common, if_match='"1"')
    same = fingerprint_for_request(**common, if_match='"1"')
    newer = fingerprint_for_request(**common, if_match='"2"')
    assert first == same
    assert first != newer


def test_canonical_triage_api_owns_handoff_and_replays(tenant, authed_client, enabled_mig002_target):
    _, visit, entry = make_entry(tenant, label="API Triage")
    headers = {
        "HTTP_IF_MATCH": f'"{entry.version}"',
        "HTTP_IDEMPOTENCY_KEY": "s02-cmd027-replay",
    }
    payload = {
        "expected_version": entry.version,
        "acuity": "URGENT",
        "chief_complaint": "Synthetic API triage",
    }
    first = authed_client.post(
        f"/api/v1/clinic/triage/{entry.id}/",
        payload,
        format="json",
        **headers,
    )
    assert first.status_code == 201, first.data
    assert first.data["queue_entry"]["state"] == "COMPLETED"
    replay = authed_client.post(
        f"/api/v1/clinic/triage/{entry.id}/",
        payload,
        format="json",
        **headers,
    )
    assert replay.status_code == 201, replay.data
    assert replay.data == first.data
    assert replay["Idempotent-Replay"] == "true"
    source = QueueEntry.objects.get(id=entry.id)
    destination = QueueEntry.objects.get(
        organisation=tenant.organisation,
        facility=tenant.facility,
        visit=visit,
        work_identity=f"QUEUE-HANDOFF:{entry.id}:{tenant.department.id}:CONSULTATION",
    )
    assert source.state == "COMPLETED"
    assert source.status == "TRIAGED"
    assert source.version == entry.version + 3
    assert destination.state == "WAITING"
    assert AuditEvent.objects.filter(
        entity_id=str(entry.id), event_code="TRIAGE_COMPLETED"
    ).count() == 1
    with tenant_atomic(tenant.organisation.id):
        record = IdempotencyRecord.objects.get(
            organisation=tenant.organisation,
            operation="CMD-027",
            key_hash=key_hash("s02-cmd027-replay"),
        )
        assert record.response_body == {
            "id": str(TriageAssessment.objects.get(queue_entry=entry).id),
            "queue_entry_id": str(entry.id),
            "state": "COMPLETED",
        }
        assert "chief_complaint" not in str(record.response_body)
    assert AuditEvent.objects.filter(
        entity_id=str(entry.id), event_code="QUEUE_HANDOFF"
    ).count() == 1


def test_canonical_encounter_open_requires_consultation_queue_and_strong_version(
    tenant, authed_client, enabled_mig002_target
):
    _, visit, entry = make_entry(tenant, label="API Encounter")
    with tenant_atomic(tenant.organisation.id):
        start_service(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
        )
        _, consultation = transfer(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            source_queue_entry_id=entry.id,
            target_department_id=tenant.department.id,
            target_queue_type="CONSULTATION",
            reason="TRIAGE_COMPLETED",
        )
    headers = {
        "HTTP_IF_MATCH": f'"{consultation.version}"',
        "HTTP_IDEMPOTENCY_KEY": "s02-cmd030-replay",
    }
    payload = {"queue_entry_id": str(consultation.id), "expected_version": consultation.version}
    first = authed_client.post(
        "/api/v1/clinic/encounters/",
        payload,
        format="json",
        **headers,
    )
    assert first.status_code == 201, first.data
    encounter_id = first.data["id"]
    replay = authed_client.post(
        "/api/v1/clinic/encounters/",
        payload,
        format="json",
        **headers,
    )
    assert replay.status_code == 201, replay.data
    assert replay.data["id"] == encounter_id
    assert replay["Idempotent-Replay"] == "true"
    encounter = Encounter.objects.get(id=encounter_id)
    consultation.refresh_from_db()
    assert encounter.queue_entry_id == consultation.id
    assert consultation.state == "IN_SERVICE"
    with tenant_atomic(tenant.organisation.id):
        record = IdempotencyRecord.objects.get(
            organisation=tenant.organisation,
            operation="CMD-030",
            key_hash=key_hash("s02-cmd030-replay"),
        )
        assert record.response_body == {"id": str(encounter.id)}
    assert AuditEvent.objects.filter(entity_id=str(encounter.id), event_code="ENCOUNTER_OPENED").exists()


def test_triage_illegal_queue_type_does_not_mutate_state(tenant, authed_client, enabled_mig002_target):
    _, _, entry = make_entry(tenant, label="Wrong Triage Queue", queue_type="PHARMACY")
    response = authed_client.post(
        f"/api/v1/clinic/triage/{entry.id}/",
        {"acuity": "ROUTINE", "expected_version": entry.version},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-illegal-triage",
        HTTP_IF_MATCH=f'"{entry.version}"',
    )
    assert response.status_code == 409, response.data
    assert response.data["code"] == "INVALID_STATE"
    entry.refresh_from_db()
    assert entry.state == "WAITING"
    assert entry.version == 1
    assert not TriageAssessment.objects.filter(queue_entry=entry).exists()


def test_lwbs_api_is_reception_owned_and_idempotent(tenant, authed_client, enabled_mig002_target):
    _, visit, entry = make_entry(tenant, label="API LWBS")
    payload = {
        "queue_entry_id": str(entry.id),
        "reason": "WAIT_TOO_LONG",
        "expected_version": visit.version,
        "expected_queue_version": entry.version,
    }
    headers = {
        "HTTP_IF_MATCH": f'"{visit.version}"',
        "HTTP_IDEMPOTENCY_KEY": "s02-cmd007-replay",
    }
    first = authed_client.post(
        f"/api/v1/reception/visits/{visit.id}/close-lwbs/",
        payload,
        format="json",
        **headers,
    )
    assert first.status_code == 200, first.data
    assert first.data["state"] == "LWBS"
    assert first.data["visit_version"] == 2
    replay = authed_client.post(
        f"/api/v1/reception/visits/{visit.id}/close-lwbs/",
        payload,
        format="json",
        **headers,
    )
    assert replay.status_code == 200, replay.data
    assert replay.data == first.data
    assert replay["Idempotent-Replay"] == "true"
    assert Visit.objects.get(id=visit.id).state == "CLOSED"
    assert QueueEntry.objects.get(id=entry.id).state == "LWBS"


def test_lwbs_reason_contract_rejects_invalid_text_atomically(tenant, authed_client, enabled_mig002_target):
    _, visit, entry = make_entry(tenant, label="LWBS Reason Contract")
    base = {
        "queue_entry_id": str(entry.id),
        "expected_version": visit.version,
        "expected_queue_version": entry.version,
    }
    missing_text = authed_client.post(
        f"/api/v1/reception/visits/{visit.id}/close-lwbs/",
        {**base, "reason": "OTHER"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-lwbs-other-missing",
        HTTP_IF_MATCH=f'"{visit.version}"',
    )
    assert missing_text.status_code == 400, missing_text.data
    invalid_text = authed_client.post(
        f"/api/v1/reception/visits/{visit.id}/close-lwbs/",
        {**base, "reason": "WAIT_TOO_LONG", "reason_text": "not allowed here"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-lwbs-text-not-allowed",
        HTTP_IF_MATCH=f'"{visit.version}"',
    )
    assert invalid_text.status_code == 400, invalid_text.data
    entry.refresh_from_db()
    visit.refresh_from_db()
    assert entry.state == "WAITING"
    assert entry.version == 1
    assert visit.state == "OPEN"
    assert visit.version == 1


def test_queue_cancel_cannot_own_lwbs(tenant, authed_client, enabled_mig002_target):
    _, _, entry = make_entry(tenant, label="Wrong LWBS Owner")
    response = authed_client.post(
        f"/api/v1/clinic/queue/{entry.id}/cancel/",
        {"reason": "LEFT_WITHOUT_BEING_SEEN", "expected_version": entry.version},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-wrong-lwbs-owner",
        HTTP_IF_MATCH=f'"{entry.version}"',
    )
    assert response.status_code == 409, response.data
    assert response.data["code"] == "WRONG_COMMAND_OWNER"
    assert QueueEntry.objects.get(id=entry.id).state == "WAITING"


def test_audit_failure_rolls_back_queue_transition(tenant, enabled_mig002_target, monkeypatch):
    _, _, entry = make_entry(tenant, label="Audit Failure")

    def fail_audit(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr("scheduling.queue.record_fact", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        with tenant_atomic(tenant.organisation.id):
            start_service(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                queue_entry_id=entry.id,
            )
    entry.refresh_from_db()
    assert entry.state == "WAITING"
    assert entry.version == 1
    assert not AuditEvent.objects.filter(entity_id=str(entry.id), event_code="QUEUE_CALLED").exists()


def test_history_and_location_hide_out_of_scope_handoff(tenant, authed_client, enabled_mig002_target):
    _, visit, entry = make_entry(tenant, label="Scoped Handoff")
    with tenant_atomic(tenant.organisation.id):
        other_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Other Scope",
            code="OTHER_SCOPE",
        )
        start_service(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=entry.id,
        )
        _, destination = transfer(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            source_queue_entry_id=entry.id,
            target_department_id=other_department.id,
            target_queue_type="CONSULTATION",
            reason="ROUTED_IN_ERROR",
        )
    history = authed_client.get(f"/api/v1/clinic/queue/history/{visit.id}/")
    assert history.status_code == 200, history.data
    assert str(entry.id) in {row["id"] for row in history.data}
    assert str(destination.id) not in {row["id"] for row in history.data}
    location = authed_client.get(f"/api/v1/clinic/queue/location/{visit.id}/")
    assert location.status_code == 200, location.data
    assert str(destination.id) not in str(location.data)
    assert location.data["state"] == "IN_FACILITY_NO_ACTIVE_QUEUE"
