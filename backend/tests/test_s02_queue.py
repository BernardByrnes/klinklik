from datetime import timedelta
from uuid import UUID, uuid4

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


def scoped_queue_client(tenant, *, username, department):
    """Return a client granted one department and only TRIAGE call work."""

    from rest_framework.test import APIClient

    from accounts.models import OrganisationMembership

    user = User.objects.create_user(username, "test-password-123")
    with tenant_atomic(tenant.organisation.id):
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=user)
        role = Role.objects.create(
            organisation=tenant.organisation,
            name="Scoped Triage Caller",
            template_code="SCOPED_TRIAGE_CALLER",
        )
        for code in ("queue.call:TRIAGE", "queue.view", "triage.record", "clinical.note.create"):
            permission, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"name": code, "sensitivity_tier": "T1"},
            )
            RolePermission.objects.create(
                organisation=tenant.organisation, role=role, permission=permission
            )
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=user,
            role=role,
            facility=tenant.facility,
            department=department,
        )
    client = APIClient()
    response = client.post(
        "/api/v1/auth/login/",
        {
            "username": username,
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    client.defaults["HTTP_X_FACILITY_ID"] = str(tenant.facility.id)
    client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access_token"])
    return client


def test_s02_command_scope_is_bound_to_the_granted_department(
    tenant, enabled_mig002_target
):
    with tenant_atomic(tenant.organisation.id):
        hidden_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Hidden Department",
            code="HIDDEN",
        )
    _, hidden_visit, hidden = make_entry(
        tenant, label="Hidden Urgent", department=hidden_department, priority="URGENT"
    )
    _, allowed_visit, allowed = make_entry(
        tenant, label="Allowed Routine", department=tenant.department, priority="ROUTINE"
    )
    client = scoped_queue_client(
        tenant, username="s02-scoped", department=tenant.department
    )

    # Omitted filters must not reach the hidden department's higher-priority row.
    called = client.post(
        "/api/v1/clinic/queue/call-next/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-scope-call-next",
    )
    assert called.status_code == 200, called.data
    assert called.data["queue_entry_id"] == str(allowed.id)
    with tenant_atomic(tenant.organisation.id):
        assert QueueEntry.objects.get(id=hidden.id).state == "WAITING"
        assert QueueEntry.objects.get(id=allowed.id).state == "CALLED"

    # Explicit filters naming the hidden department or a mismatched type are
    # refused by the same resolved scope.
    denied_department = client.post(
        "/api/v1/clinic/queue/call-next/",
        {"department_id": str(hidden_department.id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-scope-call-next-hidden",
    )
    assert denied_department.status_code == 403, denied_department.data
    denied_type = client.post(
        "/api/v1/clinic/queue/call-next/",
        {"queue_type": "PHARMACY"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-scope-call-next-type",
    )
    assert denied_type.status_code == 403, denied_type.data

    # Stage commands cannot target a known hidden UUID either.
    with tenant_atomic(tenant.organisation.id):
        hidden_version = QueueEntry.objects.get(id=hidden.id).version
    denied_triage = client.post(
        f"/api/v1/clinic/triage/{hidden.id}/",
        {"expected_version": hidden_version, "acuity": "URGENT", "chief_complaint": "Hidden"},
        format="json",
        HTTP_IF_MATCH=f'"{hidden_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-scope-triage-hidden",
    )
    assert denied_triage.status_code == 403, denied_triage.data
    denied_encounter = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": str(hidden.id), "expected_version": hidden_version},
        format="json",
        HTTP_IF_MATCH=f'"{hidden_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-scope-encounter-hidden",
    )
    assert denied_encounter.status_code == 403, denied_encounter.data
    with tenant_atomic(tenant.organisation.id):
        unchanged = QueueEntry.objects.get(id=hidden.id)
        assert unchanged.state == "WAITING"
        assert unchanged.version == hidden_version
        assert not TriageAssessment.objects.filter(queue_entry_id=hidden.id).exists()
        assert not Encounter.objects.filter(queue_entry_id=hidden.id).exists()
        assert not AuditEvent.objects.filter(
            entity_id=str(hidden.id), event_code__in=["TRIAGE_COMPLETED", "QUEUE_CALLED"]
        ).exists()

    # The authorised row still completes the same commands.
    with tenant_atomic(tenant.organisation.id):
        allowed_version = QueueEntry.objects.get(id=allowed.id).version
    triaged = client.post(
        f"/api/v1/clinic/triage/{allowed.id}/",
        {"expected_version": allowed_version, "acuity": "ROUTINE", "chief_complaint": "Allowed"},
        format="json",
        HTTP_IF_MATCH=f'"{allowed_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-scope-triage-allowed",
    )
    assert triaged.status_code == 201, triaged.data
    assert triaged.data["queue_entry"]["state"] == "COMPLETED"


def test_s02_canonical_stage_commands_require_the_current_version(
    tenant, authed_client, enabled_mig002_target
):
    _, _, entry = make_entry(tenant, label="Version Required")
    missing = authed_client.post(
        f"/api/v1/clinic/triage/{entry.id}/",
        {"acuity": "ROUTINE", "chief_complaint": "No version"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-version-missing",
    )
    assert missing.status_code == 428, missing.data
    assert missing.data["code"] == "PRECONDITION_REQUIRED"

    with tenant_atomic(tenant.organisation.id):
        unchanged = QueueEntry.objects.get(id=entry.id)
        assert unchanged.state == "WAITING"
        assert unchanged.version == entry.version
        assert not TriageAssessment.objects.filter(queue_entry_id=entry.id).exists()
        # A positive but stale version, so the guard is exercised rather than
        # the If-Match syntax check.
        QueueEntry.objects.filter(id=entry.id).update(version=2)

    stale = authed_client.post(
        f"/api/v1/clinic/triage/{entry.id}/",
        {"expected_version": 1, "acuity": "ROUTINE", "chief_complaint": "Stale"},
        format="json",
        HTTP_IF_MATCH='"1"',
        HTTP_IDEMPOTENCY_KEY="s02-version-stale",
    )
    assert stale.status_code == 412, stale.data
    with tenant_atomic(tenant.organisation.id):
        assert QueueEntry.objects.get(id=entry.id).version == 2
        assert not TriageAssessment.objects.filter(queue_entry_id=entry.id).exists()

    _, _, consultation = make_entry(
        tenant, label="Encounter Version", queue_type="CONSULTATION"
    )
    encounter_missing = authed_client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": str(consultation.id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-encounter-version-missing",
    )
    assert encounter_missing.status_code == 428, encounter_missing.data
    with tenant_atomic(tenant.organisation.id):
        assert not Encounter.objects.filter(queue_entry_id=consultation.id).exists()
        assert QueueEntry.objects.get(id=consultation.id).state == "WAITING"


def test_mig002_constrain_does_not_activate_target_routes(
    tenant, authed_client, enabled_mig001_target
):
    _, _, entry = make_entry(tenant, label="Constrain Only")
    with tenant_atomic(tenant.organisation.id):
        inventory_mig002(organisation=tenant.organisation)
        backfill_mig002(organisation=tenant.organisation)
        verify_mig002(organisation=tenant.organisation)
        verify_mig002(organisation=tenant.organisation)
        constrain_mig002(organisation=tenant.organisation)
        switch = MigrationCutover.objects.get(
            organisation=tenant.organisation, migration_id="MIG-002"
        )
        assert switch.phase == "CONSTRAINED"
        assert switch.target_reads_enabled is False
        assert switch.target_writes_enabled is False

    # Constrain records verification; it must not open the target routes.
    fenced_read = authed_client.get("/api/v1/clinic/queue/operational/")
    assert fenced_read.status_code == 503, fenced_read.data
    with pytest.raises(QueueDomainError) as fenced_write:
        with tenant_atomic(tenant.organisation.id):
            call_next_or_exact(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                department_id=tenant.department.id,
                queue_type="TRIAGE",
            )
    assert fenced_write.value.code == "MIGRATION_TARGET_DISABLED"

    with tenant_atomic(tenant.organisation.id):
        cutover_mig002(organisation=tenant.organisation)
        active = MigrationCutover.objects.get(
            organisation=tenant.organisation, migration_id="MIG-002"
        )
        assert active.phase == "CUTOVER"
        assert active.target_reads_enabled is True
        assert active.target_writes_enabled is True

    live_read = authed_client.get("/api/v1/clinic/queue/operational/")
    assert live_read.status_code == 200, live_read.data
    assert str(entry.id) in {row["id"] for row in live_read.data["entries"]}


def test_s02_consultation_worklist_pages_and_includes_clinician(
    tenant, authed_client, enabled_mig002_target
):
    consultation_ids = []
    for index in range(26):
        _, _, entry = make_entry(
            tenant, label=f"Page Row {index}", queue_type="CONSULTATION"
        )
        consultation_ids.append(str(entry.id))
    _, _, clinician = make_entry(
        tenant, label="Clinician Work", queue_type="CLINICIAN"
    )
    _, _, triage_source = make_entry(tenant, label="Triage Source", queue_type="TRIAGE")

    first = authed_client.get(
        "/api/v1/clinic/queue/operational/?queue_type=CONSULTATION&state=WAITING&page=1&page_size=25"
    )
    assert first.status_code == 200, first.data
    assert len(first.data["entries"]) == 25
    assert first.data["has_next"] is True
    assert first.data["page"] == 1

    second = authed_client.get(
        "/api/v1/clinic/queue/operational/?queue_type=CONSULTATION&state=WAITING&page=2&page_size=25"
    )
    assert second.status_code == 200, second.data
    assert len(second.data["entries"]) == 1
    assert second.data["has_next"] is False

    reached = {row["id"] for row in first.data["entries"]} | {
        row["id"] for row in second.data["entries"]
    }
    assert reached == set(consultation_ids)
    assert str(triage_source.id) not in reached

    clinician_page = authed_client.get(
        "/api/v1/clinic/queue/operational/?queue_type=CLINICIAN&state=WAITING"
    )
    assert clinician_page.status_code == 200, clinician_page.data
    assert [row["id"] for row in clinician_page.data["entries"]] == [str(clinician.id)]
    assert str(triage_source.id) not in {
        row["id"] for row in clinician_page.data["entries"]
    }


# --- S-02 review follow-up: paired grants, command scope, replay, target validation ---


def queue_scope_client(tenant, *, username, grants):
    """Return a client whose scope is exactly the given (department, codes) grants.

    Each grant is its own role so the work type stays bound to its department,
    which is what a real two-department reader looks like.
    """

    from rest_framework.test import APIClient

    from accounts.models import OrganisationMembership

    user = User.objects.create_user(username, "test-password-123")
    with tenant_atomic(tenant.organisation.id):
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=user)
        for index, (department, codes) in enumerate(grants):
            role = Role.objects.create(
                organisation=tenant.organisation,
                name=f"{username} role {index}",
                template_code=f"SCOPED_{username.upper().replace('-', '_')}_{index}",
            )
            for code in codes:
                permission, _ = Permission.objects.get_or_create(
                    code=code,
                    defaults={"name": code, "sensitivity_tier": "T1"},
                )
                RolePermission.objects.create(
                    organisation=tenant.organisation,
                    role=role,
                    permission=permission,
                )
            UserFacilityRole.objects.create(
                organisation=tenant.organisation,
                user=user,
                role=role,
                facility=tenant.facility,
                department=department,
            )
    client = APIClient()
    response = client.post(
        "/api/v1/auth/login/",
        {
            "username": username,
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    client.defaults["HTTP_X_FACILITY_ID"] = str(tenant.facility.id)
    client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access_token"])
    return client, user


def test_queue_reads_keep_department_and_work_type_paired(tenant, enabled_mig002_target):
    with tenant_atomic(tenant.organisation.id):
        department_b = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Second Department",
            code="SECOND",
        )
    _, _, a_triage = make_entry(
        tenant, label="A Triage", department=tenant.department, queue_type="TRIAGE"
    )
    _, _, a_consultation = make_entry(
        tenant,
        label="A Consultation",
        department=tenant.department,
        queue_type="CONSULTATION",
    )
    _, _, b_triage = make_entry(
        tenant, label="B Triage", department=department_b, queue_type="TRIAGE"
    )
    _, _, b_consultation = make_entry(
        tenant,
        label="B Consultation",
        department=department_b,
        queue_type="CONSULTATION",
    )
    client, _ = queue_scope_client(
        tenant,
        username="paired-reader",
        grants=[
            (tenant.department, ("queue.read:TRIAGE",)),
            (department_b, ("queue.read:CONSULTATION",)),
        ],
    )
    allowed_ids = {str(a_triage.id), str(b_consultation.id)}

    worklist = client.get("/api/v1/clinic/queue/operational/?include_terminal=true")
    assert worklist.status_code == 200, worklist.data
    assert {row["id"] for row in worklist.data["entries"]} == allowed_ids
    assert worklist.data["count"] == 2
    assert str(a_consultation.id) not in str(worklist.data)
    assert str(b_triage.id) not in str(worklist.data)

    narrowed = client.get(
        f"/api/v1/clinic/queue/operational/?department_id={tenant.department.id}"
    )
    assert narrowed.status_code == 200, narrowed.data
    assert [row["id"] for row in narrowed.data["entries"]] == [str(a_triage.id)]
    assert narrowed.data["count"] == 1

    # An explicit combination the reader does not hold is refused with no
    # hidden identifier or patient field in the response.
    out_of_scope = client.get(
        f"/api/v1/clinic/queue/operational/?department_id={department_b.id}&queue_type=TRIAGE"
    )
    assert out_of_scope.status_code == 403, out_of_scope.data
    assert str(b_triage.id) not in str(out_of_scope.data)
    assert "patient" not in str(out_of_scope.data).lower()

    priority = client.get("/api/v1/clinic/queue/priority-projection/")
    assert priority.status_code == 200, priority.data
    assert {row["id"] for row in priority.data} == allowed_ids

    # The visit timeline and derived location use the same paired predicate:
    # B/TRIAGE is hidden even though it would rank ahead of A/TRIAGE.
    _, visit, visible = make_entry(
        tenant, label="Scoped Location", department=tenant.department, queue_type="TRIAGE"
    )
    with tenant_atomic(tenant.organisation.id):
        hidden, created = create_or_reuse_destination(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            visit=visit,
            department=department_b,
            queue_type="TRIAGE",
            source_stage="TRIAGE",
            work_identity=f"LOCATION-HIDDEN:{uuid4().hex}",
        )
        assert created
        QueueEntry.objects.filter(id=hidden.id).update(
            state="IN_SERVICE", status="IN_TRIAGE"
        )

    location = client.get(f"/api/v1/clinic/queue/location/{visit.id}/")
    assert location.status_code == 200, location.data
    assert location.data["current"]["queue_entry_id"] == str(visible.id)
    assert location.data["current"]["department_id"] == str(tenant.department.id)
    assert str(hidden.id) not in str(location.data)

    history = client.get(f"/api/v1/clinic/queue/history/{visit.id}/")
    assert history.status_code == 200, history.data
    assert {row["id"] for row in history.data} == {str(visible.id)}

    # A role without a queue-read capability sees nothing at all.
    unrelated, _ = queue_scope_client(
        tenant,
        username="unrelated-reader",
        grants=[(tenant.department, ("clinical.note.create",))],
    )
    denied = unrelated.get("/api/v1/clinic/queue/operational/")
    assert denied.status_code == 403, denied.data

    # Supervisor cards stay inside the supervisor's authorized departments.
    supervisor, _ = queue_scope_client(
        tenant,
        username="department-supervisor",
        grants=[(tenant.department, ("queue.read_board",))],
    )
    cards = supervisor.get("/api/v1/clinic/queue/supervisor/")
    assert cards.status_code == 200, cards.data
    assert {card["department_id"] for card in cards.data} == {str(tenant.department.id)}


def test_call_next_facility_wide_grant_reaches_a_waiting_row(tenant, enabled_mig002_target):
    _, _, entry = make_entry(tenant, label="Facility Wide Call")
    client, _ = queue_scope_client(
        tenant,
        username="facility-caller",
        grants=[(None, ("queue.call", "queue.view"))],
    )
    called = client.post(
        "/api/v1/clinic/queue/call-next/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-facility-wide-call",
    )
    assert called.status_code == 200, called.data
    assert called.data["queue_entry_id"] == str(entry.id)
    assert QueueEntry.objects.get(id=entry.id).state == "CALLED"


def test_call_next_command_filters_come_from_the_validated_body(tenant, enabled_mig002_target):
    with tenant_atomic(tenant.organisation.id):
        department_b = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Filtered Department",
            code="FILTERED",
        )
    _, _, urgent_b = make_entry(
        tenant,
        label="Other Department Urgent",
        department=department_b,
        queue_type="TRIAGE",
        priority="URGENT",
    )
    _, _, routine_a = make_entry(
        tenant, label="Requested Department Routine", queue_type="TRIAGE"
    )
    client, _ = queue_scope_client(
        tenant,
        username="two-department-caller",
        grants=[
            (tenant.department, ("queue.call", "queue.view")),
            (department_b, ("queue.call", "queue.view")),
        ],
    )

    # The body filter is the command input, so the higher-priority row in the
    # other granted department is not called.
    called = client.post(
        "/api/v1/clinic/queue/call-next/",
        {"department_id": str(tenant.department.id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-body-filter-call",
    )
    assert called.status_code == 200, called.data
    assert called.data["queue_entry_id"] == str(routine_a.id)
    assert QueueEntry.objects.get(id=urgent_b.id).state == "WAITING"

    replay = client.post(
        "/api/v1/clinic/queue/call-next/",
        {"department_id": str(tenant.department.id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-body-filter-call",
    )
    assert replay.status_code == 200, replay.data
    assert replay["Idempotent-Replay"] == "true"
    assert replay.data == called.data

    # A command scope in the query string is refused before any idempotency
    # lookup or execution, including for an already-used key.
    rejected = client.post(
        f"/api/v1/clinic/queue/call-next/?department_id={department_b.id}",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-query-scope-new",
    )
    assert rejected.status_code == 400, rejected.data
    assert rejected.data["code"] == "INVALID_QUERY_SCOPE"
    assert not IdempotencyRecord.objects.filter(
        organisation=tenant.organisation, key_hash=key_hash("s02-query-scope-new")
    ).exists()
    assert QueueEntry.objects.get(id=urgent_b.id).state == "WAITING"

    rejected_replay = client.post(
        f"/api/v1/clinic/queue/call-next/?department_id={department_b.id}",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-body-filter-call",
    )
    assert rejected_replay.status_code == 400, rejected_replay.data
    assert rejected_replay.data["code"] == "INVALID_QUERY_SCOPE"
    assert "Idempotent-Replay" not in rejected_replay
    assert QueueEntry.objects.get(id=routine_a.id).state == "CALLED"

    # Presence, not truthiness: a blank or repeated query key is a supplied
    # but unusable filter, never an omitted one.
    blank_queries = (
        ("department_id=", "s02-blank-query-department"),
        ("queue_type=", "s02-blank-query-type"),
        ("department_id=&department_id=", "s02-repeated-query-department"),
    )
    for suffix, key in blank_queries:
        blank = client.post(
            f"/api/v1/clinic/queue/call-next/?{suffix}",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        assert blank.status_code == 400, blank.data
        assert blank.data["code"] == "INVALID_QUERY_SCOPE"
        assert not IdempotencyRecord.objects.filter(
            organisation=tenant.organisation, key_hash=key_hash(key)
        ).exists()
    assert QueueEntry.objects.get(id=urgent_b.id).state == "WAITING"
    assert not AuditEvent.objects.filter(
        entity_id=str(urgent_b.id), event_code="QUEUE_CALLED"
    ).exists()

    # The same key with a different accepted body is still the existing
    # fingerprint conflict.
    conflict = client.post(
        "/api/v1/clinic/queue/call-next/",
        {"department_id": str(department_b.id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-body-filter-call",
    )
    assert conflict.status_code == 409, conflict.data
    assert conflict.data["code"] == "IDEMPOTENCY_CONFLICT"
    assert QueueEntry.objects.get(id=urgent_b.id).state == "WAITING"


def test_call_next_with_empty_grants_has_no_candidates(tenant, enabled_mig002_target):
    _, _, entry = make_entry(tenant, label="Empty Grant Row")
    client, user = queue_scope_client(
        tenant,
        username="no-queue-grant",
        grants=[(tenant.department, ("clinical.note.create",))],
    )
    denied = client.post(
        "/api/v1/clinic/queue/call-next/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-empty-grant-call",
    )
    assert denied.status_code == 403, denied.data
    with tenant_atomic(tenant.organisation.id):
        assert (
            call_next_or_exact(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=user,
                allowed_scopes=[],
            )
            is None
        )
    assert QueueEntry.objects.get(id=entry.id).state == "WAITING"
    assert not AuditEvent.objects.filter(
        entity_id=str(entry.id), event_code="QUEUE_CALLED"
    ).exists()


def test_call_next_replay_reauthorizes_the_stored_row(tenant, enabled_mig002_target):
    from types import SimpleNamespace

    from application.queue.views import QueueCallView

    with tenant_atomic(tenant.organisation.id):
        department_b = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Replay Department",
            code="REPLAY",
        )
    _, _, entry = make_entry(tenant, label="Replay Scope Row")
    client, user = queue_scope_client(
        tenant,
        username="moving-caller",
        grants=[(tenant.department, ("queue.call", "queue.view"))],
    )
    first = client.post(
        "/api/v1/clinic/queue/call-next/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-replay-scope",
    )
    assert first.status_code == 200, first.data
    assert first.data["queue_entry_id"] == str(entry.id)

    replay = client.post(
        "/api/v1/clinic/queue/call-next/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-replay-scope",
    )
    assert replay.status_code == 200, replay.data
    assert replay["Idempotent-Replay"] == "true"
    assert replay.data == first.data

    with tenant_atomic(tenant.organisation.id):
        UserFacilityRole.objects.filter(
            organisation=tenant.organisation, user=user
        ).update(department=department_b)

    denied = client.post(
        "/api/v1/clinic/queue/call-next/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-replay-scope",
    )
    assert denied.status_code == 404, denied.data
    assert denied.data["code"] == "NOT_FOUND"
    for field in ("queue_entry_id", "called_by_id", "version", "state", "served_by_id"):
        assert field not in denied.data
    with tenant_atomic(tenant.organisation.id):
        unchanged = QueueEntry.objects.get(id=entry.id)
        assert unchanged.state == "CALLED"
        assert unchanged.version == first.data["version"]
        record = IdempotencyRecord.objects.get(
            organisation=tenant.organisation,
            operation="CMD-013",
            key_hash=key_hash("s02-replay-scope"),
        )
        assert record.response_body["queue_entry_id"] == str(entry.id)
    assert AuditEvent.objects.filter(
        entity_id=str(entry.id), event_code="QUEUE_CALLED"
    ).count() == 1

    # Prove the row-level check independently of the authority fingerprint:
    # the same callback must refuse a synthetic stored result outside scope.
    view = QueueCallView()
    view.request = SimpleNamespace(
        organisation=tenant.organisation,
        facility=tenant.facility,
        user=user,
    )
    stored = SimpleNamespace(
        response_body={
            "queue_entry_id": str(entry.id),
            "state": "CALLED",
            "version": first.data["version"],
            "called_by_id": str(user.id),
        },
        result_reference={"entity_type": "QueueEntry", "entity_id": str(entry.id)},
    )
    with tenant_atomic(tenant.organisation.id):
        with pytest.raises(CanonicalError) as refused:
            view.replay_idempotent_response(stored)
        assert refused.value.code == "NOT_FOUND"
        assert str(entry.id) not in str(refused.value.detail)


def test_call_next_empty_result_replays_as_empty(tenant, enabled_mig002_target):
    client, _ = queue_scope_client(
        tenant,
        username="empty-result-caller",
        grants=[(None, ("queue.call",))],
    )
    first = client.post(
        "/api/v1/clinic/queue/call-next/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-empty-result",
    )
    assert first.status_code == 200, first.data
    assert first.data == {"queue_entry_id": None}
    replay = client.post(
        "/api/v1/clinic/queue/call-next/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s02-empty-result",
    )
    assert replay.status_code == 200, replay.data
    assert replay["Idempotent-Replay"] == "true"
    assert replay.data == {"queue_entry_id": None}


def test_encounter_rejects_a_malformed_queue_target_before_lookup(
    tenant, enabled_mig002_target
):
    client, _ = queue_scope_client(
        tenant,
        username="malformed-target-caller",
        grants=[(tenant.department, ("clinical.note.create", "queue.view"))],
    )
    malformed = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": "not-a-uuid", "expected_version": 1},
        format="json",
        HTTP_IF_MATCH='"1"',
        HTTP_IDEMPOTENCY_KEY="s02-malformed-encounter",
    )
    assert malformed.status_code == 400, malformed.data
    assert "queue_entry_id" in malformed.data
    with tenant_atomic(tenant.organisation.id):
        assert not Encounter.objects.filter(organisation=tenant.organisation).exists()
        assert not AuditEvent.objects.filter(
            organisation=tenant.organisation, event_code="ENCOUNTER_OPENED"
        ).exists()
        assert not IdempotencyRecord.objects.filter(
            organisation=tenant.organisation,
            key_hash=key_hash("s02-malformed-encounter"),
        ).exists()

    # A well-formed but unknown target keeps the command's own missing-row
    # contract instead of becoming a permission denial.
    missing = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": str(uuid4()), "expected_version": 1},
        format="json",
        HTTP_IF_MATCH='"1"',
        HTTP_IDEMPOTENCY_KEY="s02-missing-encounter",
    )
    assert missing.status_code == 404, missing.data
    assert missing.data["code"] == "NOT_FOUND"


def serializer_uuid_representations(value):
    """Every representation DRF's UUIDField accepts as the same identifier."""

    return (
        str(value),
        value.hex,
        "{" + str(value) + "}",
        f"urn:uuid:{value}",
        value.int,
    )


def test_encounter_permission_matches_every_serializer_identifier_representation(
    tenant, enabled_mig002_target
):
    from types import SimpleNamespace

    from core.permissions import QueueScopePermission

    with tenant_atomic(tenant.organisation.id):
        other_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Identifier Department",
            code="IDENTIFIER",
        )
    _, _, authorized = make_entry(
        tenant, label="Identifier Authorized", queue_type="CONSULTATION"
    )
    _, _, hidden = make_entry(
        tenant,
        label="Identifier Hidden",
        department=other_department,
        queue_type="CONSULTATION",
    )
    with tenant_atomic(tenant.organisation.id):
        # The nil UUID is valid UUIDField input and its integer form is the
        # falsey value ``0``; a supplied identifier must never look omitted.
        QueueEntry.objects.filter(id=hidden.id).update(id=UUID(int=0))
    hidden = QueueEntry.objects.get(id=UUID(int=0))
    client = scoped_queue_client(
        tenant, username="s02-encounter-id-forms", department=tenant.department
    )
    user = User.objects.get(username="s02-encounter-id-forms")
    permission = QueueScopePermission()
    view = SimpleNamespace(capability="clinical.note.create")

    def decision(value):
        request = SimpleNamespace(
            organisation=tenant.organisation,
            facility=tenant.facility,
            user=user,
            parser_context={},
            data={"queue_entry_id": value},
        )
        with tenant_atomic(tenant.organisation.id):
            return permission.has_permission(request, view)

    for representation in serializer_uuid_representations(authorized.id):
        assert decision(representation) is True, representation
    for representation in serializer_uuid_representations(hidden.id):
        assert decision(representation) is False, representation
    assert decision(0) is False

    # The falsey integer form must deny before the command runs, disclosing
    # nothing and leaving both the QueueEntry and Encounter unchanged.
    with tenant_atomic(tenant.organisation.id):
        hidden_version = QueueEntry.objects.get(id=UUID(int=0)).version
    denied = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": 0, "expected_version": hidden_version},
        format="json",
        HTTP_IF_MATCH=f'"{hidden_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-identifier-form-denied",
    )
    assert denied.status_code == 403, denied.data
    assert str(hidden.id) not in str(denied.data)
    assert "patient" not in str(denied.data).lower()
    with tenant_atomic(tenant.organisation.id):
        unchanged = QueueEntry.objects.get(id=UUID(int=0))
        assert unchanged.state == "WAITING"
        assert unchanged.version == hidden_version
        assert not Encounter.objects.filter(queue_entry_id=unchanged.id).exists()
        assert not Encounter.objects.filter(organisation=tenant.organisation).exists()
        assert not AuditEvent.objects.filter(
            organisation=tenant.organisation, event_code="ENCOUNTER_OPENED"
        ).exists()
        assert not IdempotencyRecord.objects.filter(
            organisation=tenant.organisation,
            key_hash=key_hash("s02-identifier-form-denied"),
        ).exists()

    # The authorized target still completes the command through the same
    # integer representation the permission now authorizes.
    allowed = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": authorized.id.int, "expected_version": authorized.version},
        format="json",
        HTTP_IF_MATCH=f'"{authorized.version}"',
        HTTP_IDEMPOTENCY_KEY="s02-identifier-form-allowed",
    )
    assert allowed.status_code == 201, allowed.data
    with tenant_atomic(tenant.organisation.id):
        assert Encounter.objects.filter(queue_entry_id=authorized.id).exists()


def test_queue_call_permission_matches_every_serializer_identifier_representation(
    tenant, enabled_mig002_target
):
    from types import SimpleNamespace

    from django.http import QueryDict

    from application.queue.views import QueueCapability

    with tenant_atomic(tenant.organisation.id):
        other_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Call Identifier Department",
            code="CALL_IDENTIFIER",
        )
    _, _, authorized = make_entry(tenant, label="Call Identifier Authorized")
    _, _, hidden = make_entry(
        tenant,
        label="Call Identifier Hidden",
        department=other_department,
        queue_type="TRIAGE",
    )
    with tenant_atomic(tenant.organisation.id):
        QueueEntry.objects.filter(id=hidden.id).update(id=UUID(int=0))
    client = scoped_queue_client(
        tenant, username="s02-call-id-forms", department=tenant.department
    )
    user = User.objects.get(username="s02-call-id-forms")
    permission = QueueCapability()
    view = SimpleNamespace(queue_capabilities=("queue.call", "queue.serve", "queue.claim"))

    def decision(value):
        request = SimpleNamespace(
            method="POST",
            organisation=tenant.organisation,
            facility=tenant.facility,
            user=user,
            parser_context={},
            query_params=QueryDict(mutable=False),
            data={"queue_entry_id": value},
        )
        with tenant_atomic(tenant.organisation.id):
            return permission.has_permission(request, view)

    for representation in serializer_uuid_representations(authorized.id):
        assert decision(representation) is True, representation
    for representation in serializer_uuid_representations(UUID(int=0)):
        assert decision(representation) is False, representation
    assert decision(0) is False

    with tenant_atomic(tenant.organisation.id):
        hidden_version = QueueEntry.objects.get(id=UUID(int=0)).version
    denied = client.post(
        "/api/v1/clinic/queue/call/",
        {"queue_entry_id": 0, "expected_version": hidden_version},
        format="json",
        HTTP_IF_MATCH=f'"{hidden_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-call-identifier-denied",
    )
    assert denied.status_code == 403, denied.data
    with tenant_atomic(tenant.organisation.id):
        unchanged = QueueEntry.objects.get(id=UUID(int=0))
        assert unchanged.state == "WAITING"
        assert unchanged.version == hidden_version
        assert not AuditEvent.objects.filter(
            entity_id=str(unchanged.id), event_code="QUEUE_CALLED"
        ).exists()
        assert not IdempotencyRecord.objects.filter(
            organisation=tenant.organisation,
            key_hash=key_hash("s02-call-identifier-denied"),
        ).exists()

    allowed = client.post(
        "/api/v1/clinic/queue/call/",
        {"queue_entry_id": authorized.id.int, "expected_version": authorized.version},
        format="json",
        HTTP_IF_MATCH=f'"{authorized.version}"',
        HTTP_IDEMPOTENCY_KEY="s02-call-identifier-allowed",
    )
    assert allowed.status_code == 200, allowed.data
    assert allowed.data["queue_entry_id"] == str(authorized.id)
    assert QueueEntry.objects.get(id=authorized.id).state == "CALLED"


def test_transfer_authorizes_the_effective_destination_work_type(
    tenant, enabled_mig002_target
):
    with tenant_atomic(tenant.organisation.id):
        destination_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Transfer Destination Department",
            code="DEST_B",
        )
    _, _, denied_source = make_entry(tenant, label="Transfer Default Denied")
    _, _, explicit_source = make_entry(tenant, label="Transfer Explicit Target")
    _, _, default_source = make_entry(tenant, label="Transfer Default Allowed")
    with tenant_atomic(tenant.organisation.id):
        for row in (denied_source, explicit_source, default_source):
            start_service(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                queue_entry_id=row.id,
            )

    # The actor holds TRIAGE in both departments. Omitting the work type
    # resolves to DEST_B, the destination department's code, which the actor
    # does not hold; only the matching department grant must not admit it.
    limited_client, _ = queue_scope_client(
        tenant,
        username="s02-transfer-default-denied",
        grants=[
            (tenant.department, ("queue.transfer:TRIAGE",)),
            (destination_department, ("queue.transfer:TRIAGE",)),
        ],
    )
    with tenant_atomic(tenant.organisation.id):
        denied_version = QueueEntry.objects.get(id=denied_source.id).version
    denied = limited_client.post(
        "/api/v1/clinic/queue/transfer/",
        {
            "source_queue_entry_id": str(denied_source.id),
            "target_department_id": str(destination_department.id),
            "expected_version": denied_version,
        },
        format="json",
        HTTP_IF_MATCH=f'"{denied_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-transfer-default-denied",
    )
    assert denied.status_code == 403, denied.data
    assert str(denied_source.id) not in str(denied.data)
    with tenant_atomic(tenant.organisation.id):
        unchanged = QueueEntry.objects.get(id=denied_source.id)
        assert unchanged.state == "IN_SERVICE"
        assert unchanged.version == denied_version
        assert not QueueEntry.objects.filter(
            work_identity=(
                f"QUEUE-HANDOFF:{denied_source.id}:{destination_department.id}:DEST_B"
            )
        ).exists()
        assert not AuditEvent.objects.filter(
            entity_id=str(denied_source.id),
            event_code__in=["QUEUE_HANDOFF", "QUEUE_SERVICE_COMPLETED", "QUEUE_TRANSFERRED"],
        ).exists()
        assert not IdempotencyRecord.objects.filter(
            organisation=tenant.organisation,
            key_hash=key_hash("s02-transfer-default-denied"),
        ).exists()

    # Malformed destination fields keep the serializer's normal 400 instead of
    # becoming a scope decision.
    for index, (target, queue_type) in enumerate(
        (("not-a-uuid", None), (destination_department.id, ""))
    ):
        malformed = limited_client.post(
            "/api/v1/clinic/queue/transfer/",
            {
                "source_queue_entry_id": str(denied_source.id),
                "target_department_id": str(target),
                **({"target_queue_type": queue_type} if queue_type is not None else {}),
                "expected_version": denied_version,
            },
            format="json",
            HTTP_IF_MATCH=f'"{denied_version}"',
            HTTP_IDEMPOTENCY_KEY=f"s02-transfer-malformed-target-{index}",
        )
        assert malformed.status_code == 400, (target, queue_type, malformed.data)
    with tenant_atomic(tenant.organisation.id):
        still_waiting = QueueEntry.objects.get(id=denied_source.id)
        assert still_waiting.state == "IN_SERVICE"
        assert still_waiting.version == denied_version

    # A valid explicit destination type in the same department is allowed.
    with tenant_atomic(tenant.organisation.id):
        explicit_version = QueueEntry.objects.get(id=explicit_source.id).version
    explicit = limited_client.post(
        "/api/v1/clinic/queue/transfer/",
        {
            "source_queue_entry_id": str(explicit_source.id),
            "target_department_id": str(destination_department.id),
            "target_queue_type": "TRIAGE",
            "expected_version": explicit_version,
        },
        format="json",
        HTTP_IF_MATCH=f'"{explicit_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-transfer-explicit-target",
    )
    assert explicit.status_code == 200, explicit.data
    with tenant_atomic(tenant.organisation.id):
        destination = QueueEntry.objects.get(
            id=explicit.data["destination_queue_entry_id"]
        )
        assert destination.department_id == destination_department.id
        assert destination.queue_type == "TRIAGE"

    # A department-wide default the actor does hold is authorized and the
    # handler creates exactly the checked work type.
    default_client, _ = queue_scope_client(
        tenant,
        username="s02-transfer-default-allowed",
        grants=[
            (tenant.department, ("queue.transfer:TRIAGE",)),
            (tenant.department, ("queue.transfer:OPD",)),
        ],
    )
    with tenant_atomic(tenant.organisation.id):
        default_version = QueueEntry.objects.get(id=default_source.id).version
    defaulted = default_client.post(
        "/api/v1/clinic/queue/transfer/",
        {
            "source_queue_entry_id": str(default_source.id),
            "target_department_id": str(tenant.department.id),
            "expected_version": default_version,
        },
        format="json",
        HTTP_IF_MATCH=f'"{default_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-transfer-default-allowed",
    )
    assert defaulted.status_code == 200, defaulted.data
    with tenant_atomic(tenant.organisation.id):
        destination = QueueEntry.objects.get(
            id=defaulted.data["destination_queue_entry_id"]
        )
        assert destination.department_id == tenant.department.id
        assert destination.queue_type == "OPD"


def test_transfer_replay_reauthorizes_the_stored_destination(
    tenant, enabled_mig002_target
):
    from types import SimpleNamespace

    from application.queue.views import QueueTransferView

    with tenant_atomic(tenant.organisation.id):
        other_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Transfer Replay Department",
            code="REPLAY_DEST",
        )
    _, _, source = make_entry(tenant, label="Transfer Replay Source")
    with tenant_atomic(tenant.organisation.id):
        start_service(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=source.id,
        )
    client, user = queue_scope_client(
        tenant,
        username="s02-transfer-replay",
        grants=[
            (tenant.department, ("queue.transfer:TRIAGE",)),
            (tenant.department, ("queue.transfer:OPD",)),
        ],
    )
    with tenant_atomic(tenant.organisation.id):
        source_version = QueueEntry.objects.get(id=source.id).version
    body = {
        "source_queue_entry_id": str(source.id),
        "target_department_id": str(tenant.department.id),
        "expected_version": source_version,
    }
    first = client.post(
        "/api/v1/clinic/queue/transfer/",
        body,
        format="json",
        HTTP_IF_MATCH=f'"{source_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-transfer-replay",
    )
    assert first.status_code == 200, first.data
    destination_id = first.data["destination_queue_entry_id"]

    replay = client.post(
        "/api/v1/clinic/queue/transfer/",
        body,
        format="json",
        HTTP_IF_MATCH=f'"{source_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-transfer-replay",
    )
    assert replay.status_code == 200, replay.data
    assert replay["Idempotent-Replay"] == "true"
    assert replay.data == first.data
    with tenant_atomic(tenant.organisation.id):
        assert AuditEvent.objects.filter(
            entity_id=str(source.id), event_code="QUEUE_HANDOFF"
        ).count() == 1
        assert QueueEntry.objects.filter(
            work_identity=f"QUEUE-HANDOFF:{source.id}:{tenant.department.id}:OPD"
        ).count() == 1
        record = IdempotencyRecord.objects.get(
            organisation=tenant.organisation,
            operation="CMD-018",
            key_hash=key_hash("s02-transfer-replay"),
        )
        assert record.response_body["destination_queue_entry_id"] == destination_id

    # The callback itself still returns the saved outcome while the stored
    # destination is authorized.
    view = QueueTransferView()
    view.request = SimpleNamespace(
        organisation=tenant.organisation,
        facility=tenant.facility,
        user=user,
    )
    with tenant_atomic(tenant.organisation.id):
        assert view.replay_idempotent_response(record) == first.data

    # Move the actor's grants: the request permission now denies the source,
    # and the callback must independently refuse the stored destination.
    with tenant_atomic(tenant.organisation.id):
        UserFacilityRole.objects.filter(
            organisation=tenant.organisation, user=user
        ).update(department=other_department)
    denied = client.post(
        "/api/v1/clinic/queue/transfer/",
        body,
        format="json",
        HTTP_IF_MATCH=f'"{source_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-transfer-replay",
    )
    assert denied.status_code == 403, denied.data
    with tenant_atomic(tenant.organisation.id):
        assert AuditEvent.objects.filter(
            entity_id=str(source.id), event_code="QUEUE_HANDOFF"
        ).count() == 1
        assert QueueEntry.objects.filter(
            work_identity=f"QUEUE-HANDOFF:{source.id}:{tenant.department.id}:OPD"
        ).count() == 1
        assert IdempotencyRecord.objects.filter(
            organisation=tenant.organisation,
            key_hash=key_hash("s02-transfer-replay"),
        ).exists()

    stored = SimpleNamespace(
        response_body=record.response_body,
        result_reference={"entity_type": "QueueEntry", "entity_id": destination_id},
    )
    denied_view = QueueTransferView()
    denied_view.request = SimpleNamespace(
        organisation=tenant.organisation,
        facility=tenant.facility,
        user=user,
    )
    with tenant_atomic(tenant.organisation.id):
        with pytest.raises(CanonicalError) as refused:
            denied_view.replay_idempotent_response(stored)
        assert refused.value.code == "NOT_FOUND"
        assert destination_id not in str(refused.value.detail)


def test_transfer_authorizes_the_source_field_its_serializer_declares(
    tenant, enabled_mig002_target
):
    with tenant_atomic(tenant.organisation.id):
        other_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Transfer Source Department",
            code="TRANSFER_SOURCE",
        )
    _, _, in_scope_decoy = make_entry(
        tenant, label="Transfer Decoy Source", queue_type="TRIAGE"
    )
    _, _, hidden_source = make_entry(
        tenant,
        label="Transfer Hidden Source",
        department=other_department,
        queue_type="TRIAGE",
    )
    _, _, authorized_source = make_entry(
        tenant, label="Transfer Authorized Source", queue_type="TRIAGE"
    )
    _, _, path_source = make_entry(
        tenant, label="Transfer Path Source", queue_type="TRIAGE"
    )
    with tenant_atomic(tenant.organisation.id):
        for row in (in_scope_decoy, hidden_source, authorized_source, path_source):
            start_service(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                queue_entry_id=row.id,
            )
    client, _ = queue_scope_client(
        tenant,
        username="s02-transfer-source",
        grants=[(tenant.department, ("queue.transfer",))],
    )

    # The Transfer serializer converts source_queue_entry_id. An unrelated,
    # in-scope queue_entry_id must not authorize the hidden source the handler
    # actually moves.
    with tenant_atomic(tenant.organisation.id):
        hidden_version = QueueEntry.objects.get(id=hidden_source.id).version
    denied = client.post(
        "/api/v1/clinic/queue/transfer/",
        {
            "source_queue_entry_id": str(hidden_source.id),
            "queue_entry_id": str(in_scope_decoy.id),
            "target_department_id": str(tenant.department.id),
            "target_queue_type": "CONSULTATION",
            "reason": "ROUTED_IN_ERROR",
            "expected_version": hidden_version,
        },
        format="json",
        HTTP_IF_MATCH=f'"{hidden_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-transfer-source-denied",
    )
    assert denied.status_code == 403, denied.data
    assert str(hidden_source.id) not in str(denied.data)
    with tenant_atomic(tenant.organisation.id):
        unchanged = QueueEntry.objects.get(id=hidden_source.id)
        assert unchanged.state == "IN_SERVICE"
        assert unchanged.version == hidden_version
        assert QueueEntry.objects.get(id=in_scope_decoy.id).state == "IN_SERVICE"
        assert not QueueEntry.objects.filter(
            work_identity=(
                f"QUEUE-HANDOFF:{hidden_source.id}:{tenant.department.id}:CONSULTATION"
            )
        ).exists()
        assert not AuditEvent.objects.filter(
            entity_id=str(hidden_source.id),
            event_code__in=["QUEUE_HANDOFF", "QUEUE_SERVICE_COMPLETED", "QUEUE_TRANSFERRED"],
        ).exists()
        assert not IdempotencyRecord.objects.filter(
            organisation=tenant.organisation,
            key_hash=key_hash("s02-transfer-source-denied"),
        ).exists()

    # The declared source field still authorizes and completes a transfer.
    with tenant_atomic(tenant.organisation.id):
        authorized_version = QueueEntry.objects.get(id=authorized_source.id).version
    allowed = client.post(
        "/api/v1/clinic/queue/transfer/",
        {
            "source_queue_entry_id": str(authorized_source.id),
            "target_department_id": str(tenant.department.id),
            "target_queue_type": "CONSULTATION",
            "expected_version": authorized_version,
        },
        format="json",
        HTTP_IF_MATCH=f'"{authorized_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-transfer-source-allowed",
    )
    assert allowed.status_code == 200, allowed.data
    assert allowed.data["source_queue_entry_id"] == str(authorized_source.id)
    with tenant_atomic(tenant.organisation.id):
        assert QueueEntry.objects.get(id=authorized_source.id).state == "COMPLETED"
        destination = QueueEntry.objects.get(
            id=allowed.data["destination_queue_entry_id"]
        )
        assert destination.state == "WAITING"
        assert destination.queue_type == "CONSULTATION"

    # The path target stays authoritative for the path-based route; a body
    # source naming another row cannot redirect the command.
    with tenant_atomic(tenant.organisation.id):
        path_version = QueueEntry.objects.get(id=path_source.id).version
    precedence = client.post(
        f"/api/v1/clinic/queue/{path_source.id}/transfer/",
        {
            "source_queue_entry_id": str(hidden_source.id),
            "target_department_id": str(tenant.department.id),
            "target_queue_type": "CONSULTATION",
            "expected_version": path_version,
        },
        format="json",
        HTTP_IF_MATCH=f'"{path_version}"',
        HTTP_IDEMPOTENCY_KEY="s02-transfer-path-precedence",
    )
    assert precedence.status_code == 200, precedence.data
    assert precedence.data["source_queue_entry_id"] == str(path_source.id)
    with tenant_atomic(tenant.organisation.id):
        assert QueueEntry.objects.get(id=path_source.id).state == "COMPLETED"
        assert QueueEntry.objects.get(id=hidden_source.id).state == "IN_SERVICE"
        assert QueueEntry.objects.get(id=hidden_source.id).version == hidden_version


def test_malformed_non_object_bodies_reach_normal_validation(
    tenant, enabled_mig002_target
):
    client = scoped_queue_client(
        tenant, username="s02-malformed-body", department=tenant.department
    )

    encounter_bodies = (
        "queue_entry_id",
        ["queue_entry_id"],
        [{"queue_entry_id": "not-a-uuid"}],
        {"queue_entry_id": None},
    )
    for index, body in enumerate(encounter_bodies):
        response = client.post(
            "/api/v1/clinic/encounters/",
            body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=f"s02-malformed-body-encounter-{index}",
        )
        assert response.status_code == 400, (body, response.data)
    with tenant_atomic(tenant.organisation.id):
        assert not Encounter.objects.filter(organisation=tenant.organisation).exists()
        assert not AuditEvent.objects.filter(
            organisation=tenant.organisation, event_code="ENCOUNTER_OPENED"
        ).exists()
        assert not IdempotencyRecord.objects.filter(
            organisation=tenant.organisation,
            key_hash__in=[
                key_hash(f"s02-malformed-body-encounter-{index}")
                for index in range(len(encounter_bodies))
            ],
        ).exists()

    # Queue commands use the same mapping guard before the serializer's own
    # "expected a dictionary" validation.
    for index, body in enumerate(("queue_entry_id", ["queue_entry_id"])):
        response = client.post(
            "/api/v1/clinic/queue/call-next/",
            body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=f"s02-malformed-body-call-{index}",
        )
        assert response.status_code == 400, (body, response.data)
    with tenant_atomic(tenant.organisation.id):
        assert not IdempotencyRecord.objects.filter(
            organisation=tenant.organisation,
            key_hash__in=[
                key_hash("s02-malformed-body-call-0"),
                key_hash("s02-malformed-body-call-1"),
            ],
        ).exists()


def test_s29_r5_transfer_rejects_mismatched_department_work_reuse(
    tenant, authed_client, enabled_mig002_target
):
    """S-29-R5: department reuse must match the authorized work type."""

    with tenant_atomic(tenant.organisation.id):
        destination_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="S-29 R5 destination",
            code="S29R5_DEST",
        )
    _patient, visit, source = make_entry(tenant, label="S29R5 Source")
    with tenant_atomic(tenant.organisation.id):
        competing, created = create_or_reuse_destination(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            visit=visit,
            department=destination_department,
            queue_type="CONSULTATION",
            source_stage="RECEPTION",
        )
        assert created
        start_service(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=source.id,
        )
        source_before = QueueEntry.objects.get(id=source.id)
        competing_before = QueueEntry.objects.get(id=competing.id)
        audit_before = AuditEvent.objects.filter(
            event_code__in=["QUEUE_TRANSFERRED", "QUEUE_SERVICE_COMPLETED", "QUEUE_HANDOFF"]
        ).count()

    scoped_client, _ = queue_scope_client(
        tenant,
        username="s29-r5-transfer",
        grants=[
            (tenant.department, ("queue.transfer:TRIAGE",)),
            (destination_department, ("queue.transfer:TRIAGE",)),
        ],
    )
    refused = scoped_client.post(
        "/api/v1/clinic/queue/transfer/",
        {
            "source_queue_entry_id": str(source.id),
            "target_department_id": str(destination_department.id),
            "target_queue_type": "TRIAGE",
            "expected_version": source_before.version,
        },
        format="json",
        HTTP_IF_MATCH=f'"{source_before.version}"',
        HTTP_IDEMPOTENCY_KEY="s29-r5-transfer-mismatch",
    )
    assert refused.status_code == 409, refused.data
    assert str(competing.id) not in str(refused.data)
    assert "CONSULTATION" not in str(refused.data)
    with tenant_atomic(tenant.organisation.id):
        unchanged_source = QueueEntry.objects.get(id=source.id)
        assert unchanged_source.state == source_before.state
        assert unchanged_source.version == source_before.version
        unchanged_competing = QueueEntry.objects.get(id=competing.id)
        assert unchanged_competing.state == competing_before.state
        assert unchanged_competing.version == competing_before.version
        assert unchanged_competing.queue_type == "CONSULTATION"
        assert (
            AuditEvent.objects.filter(
                event_code__in=["QUEUE_TRANSFERRED", "QUEUE_SERVICE_COMPLETED", "QUEUE_HANDOFF"]
            ).count()
            == audit_before
        )
        assert not IdempotencyRecord.objects.filter(
            organisation=tenant.organisation,
            key_hash=key_hash("s29-r5-transfer-mismatch"),
        ).exists()


def test_s35_r5_terminal_transfer_return_rejects_mismatched_work_identity(
    tenant, enabled_mig002_target
):
    """S-35 Fix 5: canonical terminal replay must recheck destination work type."""

    with tenant_atomic(tenant.organisation.id):
        destination_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="S-35 R5 destination",
            code="S35R5_DEST",
        )
    _patient, _visit, source = make_entry(tenant, label="S35R5 Source")
    with tenant_atomic(tenant.organisation.id):
        start_service(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=source.id,
        )
        source_before = QueueEntry.objects.get(id=source.id)
        source_after, destination = transfer(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            source_queue_entry_id=source.id,
            target_department=destination_department,
            target_queue_type="TRIAGE",
            expected_version=source_before.version,
        )
        assert source_after.state == "COMPLETED"
    with tenant_atomic(tenant.organisation.id):
        other_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="S-35 R5 historical destination",
            code="S35R5_OTHER",
        )
        QueueEntry.objects.filter(id=destination.id).update(
            department_id=other_department.id, queue_type="CONSULTATION"
        )
        source_before_replay = QueueEntry.objects.get(id=source.id)
    with tenant_atomic(tenant.organisation.id):
        with pytest.raises(CanonicalError) as exc:
            transfer(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                source_queue_entry_id=source.id,
                target_department=destination_department,
                target_queue_type="TRIAGE",
                expected_version=source_before_replay.version,
            )
        assert exc.value.code == "DESTINATION_CONFLICT"
    with tenant_atomic(tenant.organisation.id):
        unchanged = QueueEntry.objects.get(id=destination.id)
        assert unchanged.department_id == other_department.id
        assert unchanged.queue_type == "CONSULTATION"
        assert QueueEntry.objects.get(id=source.id).state == "COMPLETED"
