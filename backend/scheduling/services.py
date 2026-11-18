from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from audit.services import record_event
from core.clock import now
from core.services import allocate_sequence, assert_transaction_active
from patients.models import Patient
from scheduling.models import ArrivalEnquiry, QueueEntry, Visit
from tenancy.models import Department


def resolve_department(*, organisation, facility, department_id=None, preferred_code=None, required=True):
    """Resolve a destination in the active facility, never across facilities."""

    assert_transaction_active()
    departments = Department.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        is_active=True,
    )
    if department_id:
        department = departments.filter(id=department_id).first()
    elif preferred_code:
        department = departments.filter(code__iexact=preferred_code).first()
    else:
        department = departments.order_by("code", "id").first()
    if department is None and required:
        raise ValueError("An active destination department is required for check-in.")
    return department


def open_visit(
    *,
    organisation,
    facility,
    actor,
    patient,
    local_service_day,
    visit_type,
    reason_for_visit="",
    referral_source_type="SELF",
    referral_source_name="",
    results_review=False,
):
    assert_transaction_active()
    from core.migration_reconciliation import target_writes_enabled

    if not target_writes_enabled(organisation):
        raise ValueError("The canonical Visit writer is disabled by the MIG-001 cutover fence.")
    if (
        patient.organisation_id != organisation.id
        or facility.organisation_id != organisation.id
    ):
        raise ValueError("The Visit references a different organisation or facility.")
    return Visit.objects.create(
        organisation=organisation,
        facility=facility,
        patient=patient,
        local_service_date=local_service_day,
        visit_type=visit_type,
        state="OPEN",
        reason_for_visit=reason_for_visit,
        opened_at=now(),
        opened_by=actor,
        referral_source_type=referral_source_type,
        referral_source_name=referral_source_name,
        results_review=results_review,
    )


def cancel_error_visit(*, organisation, facility, actor, visit_id, reason, expected_version=None):
    """Cancel an unstarted Visit and its queue entries without deleting records."""

    assert_transaction_active()
    from core.migration_reconciliation import target_writes_enabled

    if not target_writes_enabled(organisation):
        raise ValueError("The canonical Visit writer is disabled by the MIG-001 cutover fence.")
    visit = Visit.objects.select_for_update().filter(
        id=visit_id,
        organisation=organisation,
        facility=facility,
    ).first()
    if visit is None:
        raise ValueError("Visit was not found in this facility.")
    if expected_version is not None and visit.version != expected_version:
        raise ValueError("The Visit changed; refresh before cancelling it.")
    if visit.state != "OPEN":
        raise ValueError("Only an open Visit can be cancelled as an erroneous check-in.")

    cancelled_at = now()
    queue_entries = list(
        QueueEntry.objects.select_for_update()
        .filter(organisation=organisation, facility=facility, visit=visit)
        .order_by("queue_time", "sequence", "id")
    )
    for entry in queue_entries:
        if entry.status not in {"COMPLETED", "CANCELLED"}:
            entry.status = "CANCELLED"
            entry.state = "CANCELLED"
            entry.completed_at = cancelled_at
            entry.version += 1
            entry.save(update_fields=["status", "state", "completed_at", "version", "updated_at"])

    visit.state = "CANCELLED_ERROR"
    visit.closure_reason = reason
    visit.closed_at = cancelled_at
    visit.closed_by = actor
    visit.version += 1
    visit.save(update_fields=["state", "closure_reason", "closed_at", "closed_by", "version", "updated_at"])
    return visit, queue_entries


def create_initial_queue_entry(
    *,
    organisation,
    facility,
    actor,
    visit,
    department,
    queue_type,
    status="WAITING",
    notes="",
):
    assert_transaction_active()
    from core.migration_reconciliation import target_writes_enabled_mig002

    if not target_writes_enabled_mig002(organisation):
        raise ValueError("The canonical QueueEntry writer is disabled by the queue migration cutover fence.")
    if (
        visit.organisation_id != organisation.id
        or visit.facility_id != facility.id
        or department.organisation_id != organisation.id
        or department.facility_id != facility.id
    ):
        raise ValueError("The queue entry references a different tenant or facility.")
    queue_date = visit.local_service_date
    last = QueueEntry.objects.filter(facility=facility, queue_date=queue_date).order_by("-sequence").first()
    sequence = allocate_sequence(
        organisation=organisation,
        facility=facility,
        sequence_type="QUEUE",
        period_key=queue_date.isoformat(),
        initial_value=(last.sequence + 1) if last else 1,
    )
    return QueueEntry.objects.create(
        organisation=organisation,
        facility=facility,
        visit=visit,
        patient=visit.patient,
        department=department,
        queue_date=queue_date,
        sequence=sequence,
        queue_type=queue_type,
        work_identity=f"VISIT:{visit.id}:{queue_type}",
        priority="ROUTINE",
        visit_type=visit.visit_type,
        status=status,
        state=QueueEntry.LEGACY_STATE_MAP.get(status, status),
        current_stage="PAYMENT" if status == "WAITING_PAYMENT" else "RECEPTION",
        source_stage="RECEPTION",
        queue_time=now(),
        notes=notes,
        source_event_id=f"VISIT:{visit.id}:{queue_type}",
        last_activity_at=now(),
    )


def record_arrival_enquiry(*, organisation, facility, actor, reason_code, source_event_id, safe_notes=""):
    assert_transaction_active()
    from core.migration_reconciliation import target_writes_enabled

    if not target_writes_enabled(organisation):
        raise ValueError("The canonical ArrivalEnquiry writer is disabled by the MIG-001 cutover fence.")
    return ArrivalEnquiry.objects.create(
        organisation=organisation,
        facility=facility,
        reason_code=reason_code,
        occurred_at=now(),
        recorded_by=actor,
        source_event_id=source_event_id,
        safe_notes=safe_notes,
    )


def convert_arrival_enquiry(*, enquiry, visit, actor):
    assert_transaction_active()
    from core.migration_reconciliation import target_writes_enabled

    if not target_writes_enabled(visit.organisation_id):
        raise ValueError("The canonical ArrivalEnquiry writer is disabled by the MIG-001 cutover fence.")
    if enquiry.organisation_id != visit.organisation_id or enquiry.facility_id != visit.facility_id:
        raise ValueError("The arrival enquiry and Visit must belong to the same facility.")
    if visit.state not in Visit.ACTIVE_STATES:
        raise ValueError("Only an active Visit can convert an arrival enquiry.")
    if enquiry.state != "OPEN":
        if enquiry.converted_visit_id == visit.id:
            return enquiry, False
        raise ValueError("The arrival enquiry has already been converted.")
    enquiry.state = "CONVERTED"
    enquiry.converted_visit = visit
    enquiry.converted_by = actor
    enquiry.converted_at = now()
    enquiry.version += 1
    enquiry.save(
        update_fields=["state", "converted_visit", "converted_by", "converted_at", "version", "updated_at"]
    )
    return enquiry, True


def set_referral_source(*, organisation, facility, actor, visit, source_type, source_name="", expected_version=None):
    assert_transaction_active()
    from core.migration_reconciliation import target_writes_enabled

    if not target_writes_enabled(organisation):
        raise ValueError("The canonical Visit writer is disabled by the MIG-001 cutover fence.")
    visit = Visit.objects.select_for_update().filter(
        id=visit.id,
        organisation=organisation,
        facility=facility,
    ).first()
    if visit is None:
        raise ValueError("Visit was not found in this facility.")
    if visit.state not in Visit.ACTIVE_STATES:
        raise ValueError("Referral source can only be recorded on an open Visit.")
    if expected_version is not None and visit.version != expected_version:
        raise ValueError("The Visit changed; refresh before recording referral source.")
    visit.referral_source_type = source_type
    visit.referral_source_name = source_name
    visit.version += 1
    visit.save(update_fields=["referral_source_type", "referral_source_name", "version", "updated_at"])
    return visit


@transaction.atomic
def check_in_patient(*, organisation, facility, actor, patient_id, department_id=None, visit_type="WALK_IN", notes="", request=None):
    from core.errors import CanonicalError
    from core.migration_reconciliation import (
        legacy_writes_enabled,
        legacy_writes_enabled_mig002,
        mig002_rollback_active,
    )

    # Both migration fences are part of the same writer decision.  In
    # particular, a MIG-002 rollback must not reopen the pre-Visit writer that
    # MIG-001 already retired.
    if not legacy_writes_enabled_mig002(organisation):
        raise CanonicalError(
            "LEGACY_WRITER_DISABLED",
            "The legacy queue writer is disabled after MIG-002 cutover; use Visit check-in.",
            status_code=503,
            retryable=True,
        )
    if mig002_rollback_active(organisation):
        return _check_in_with_visit_compatibility(
            organisation=organisation,
            facility=facility,
            actor=actor,
            patient_id=patient_id,
            department_id=department_id,
            visit_type=visit_type,
            notes=notes,
            request=request,
        )
    if not legacy_writes_enabled(organisation):
        raise CanonicalError(
            "LEGACY_WRITER_DISABLED",
            "The pre-Visit queue writer is disabled after MIG-001 cutover; use Visit check-in.",
            status_code=503,
            retryable=True,
        )
    patient = Patient.objects.filter(id=patient_id, organisation=organisation, status="ACTIVE").first()
    if patient is None:
        raise ValueError("Patient was not found in this organisation.")
    department = Department.objects.filter(
        id=department_id, organisation=organisation, facility=facility, is_active=True
    ).first() if department_id else Department.objects.filter(
        organisation=organisation, facility=facility, is_active=True
    ).order_by("code").first()
    if department is None:
        raise ValueError("An active department is required for check-in.")
    today = timezone.localdate()
    last = QueueEntry.objects.filter(facility=facility, queue_date=today).aggregate(max_sequence=Max("sequence"))
    sequence = allocate_sequence(
        organisation=organisation,
        facility=facility,
        sequence_type="QUEUE",
        period_key=today.isoformat(),
        initial_value=(last["max_sequence"] or 0) + 1,
    )
    entry = QueueEntry.objects.create(
        organisation=organisation,
        facility=facility,
        patient=patient,
        department=department,
        queue_date=today,
        sequence=sequence,
        visit_type=visit_type,
        notes=notes,
        # A new WAITING check-in is an explicit, deterministic state. Existing
        # ambiguous historical rows remain untouched for MIG-002 reconciliation.
        status="WAITING",
        state="WAITING",
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="QueueEntry",
        entity_id=entry.id,
        after={"patient_id": str(patient.id), "status": entry.status, "queue_label": entry.queue_label},
    )
    return entry


def _check_in_with_visit_compatibility(
    *, organisation, facility, actor, patient_id, department_id=None, visit_type="WALK_IN", notes="", request=None
):
    """MIG-002 rollback writer which preserves the S-01 Visit invariant.

    This is intentionally a narrow compatibility command.  It is reachable
    only while MIG-002 has rolled back and MIG-001 remains cut over; it does
    not down-map or delete any canonical rows.
    """

    from core.errors import CanonicalError

    patient = Patient.objects.select_for_update().filter(
        id=patient_id,
        organisation=organisation,
        status="ACTIVE",
    ).first()
    if patient is None:
        raise ValueError("Patient was not found in this organisation.")
    department = Department.objects.select_for_update().filter(
        id=department_id,
        organisation=organisation,
        facility=facility,
        is_active=True,
    ).first() if department_id else Department.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        is_active=True,
    ).order_by("code", "id").first()
    if department is None:
        raise ValueError("An active department is required for check-in.")
    service_day = timezone.localdate()
    existing_visit = Visit.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        patient=patient,
        local_service_date=service_day,
        state__in=Visit.ACTIVE_STATES,
    ).first()
    if existing_visit is not None:
        raise CanonicalError(
            "VISIT_ALREADY_OPEN",
            "This patient already has an open Visit for the service day.",
            status_code=409,
        )
    normalized_visit_type = str(visit_type or "").upper()
    if normalized_visit_type == "WALK_IN" or normalized_visit_type not in dict(Visit.VISIT_TYPE_CHOICES):
        normalized_visit_type = "OUTPATIENT_NEW"
    visit = open_visit(
        organisation=organisation,
        facility=facility,
        actor=actor,
        patient=patient,
        local_service_day=service_day,
        visit_type=normalized_visit_type,
    )
    patient.last_seen_at = now()
    patient.version += 1
    patient.save(update_fields=["last_seen_at", "version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="Visit",
        entity_id=visit.id,
        event_code="VISIT_OPENED",
        source_ids={"visit_id": visit.id},
        after={"state": visit.state, "version": visit.version, "visit_type": visit.visit_type},
    )
    last = QueueEntry.objects.filter(
        organisation=organisation,
        facility=facility,
        queue_date=service_day,
    ).aggregate(max_sequence=Max("sequence"))
    sequence = allocate_sequence(
        organisation=organisation,
        facility=facility,
        sequence_type="QUEUE",
        period_key=service_day.isoformat(),
        initial_value=(last["max_sequence"] or 0) + 1,
    )
    entry = QueueEntry.objects.create(
        organisation=organisation,
        facility=facility,
        visit=visit,
        patient=patient,
        department=department,
        queue_date=service_day,
        sequence=sequence,
        queue_type="TRIAGE",
        work_identity=f"COMPATIBILITY:MIG-002-ROLLBACK:{visit.id}:TRIAGE",
        visit_type=normalized_visit_type,
        notes=notes,
        status="WAITING",
        state="WAITING",
        current_stage="RECEPTION",
        source_stage="RECEPTION",
        source_event_id=f"COMPATIBILITY:MIG-002-ROLLBACK:{visit.id}",
        queue_time=now(),
        last_activity_at=now(),
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="QueueEntry",
        entity_id=entry.id,
        event_code="COMPATIBILITY_QUEUE_ENTRY_CREATED",
        source_ids={"queue_entry_id": entry.id, "visit_id": visit.id},
        after={"state": entry.state, "version": entry.version, "migration_id": "MIG-002"},
    )
    return entry


@transaction.atomic
def claim_queue_entry(*, organisation, actor, queue_id, facility=None, request=None, allowed_scopes=None):
    from core.migration_reconciliation import (
        legacy_writes_enabled,
        target_writes_enabled_mig002,
        mig002_rollback_active,
    )

    # The legacy claim route remains available for pre-MIG-002 clients, but
    # once the canonical reader/writer switch is on it must not write the
    # shadow status independently of the QueueEntry transition owner.
    if target_writes_enabled_mig002(organisation):
        return call_next_or_exact(
            organisation=organisation,
            facility=facility,
            actor=actor,
            queue_entry_id=queue_id,
            allowed_scopes=allowed_scopes,
        )
    if mig002_rollback_active(organisation):
        return _claim_visit_linked_compatibility_entry(
            organisation=organisation,
            actor=actor,
            queue_id=queue_id,
            facility=facility,
            request=request,
        )
    if not legacy_writes_enabled(organisation):
        from core.errors import CanonicalError

        raise CanonicalError(
            "LEGACY_WRITER_DISABLED",
            "The pre-Visit queue writer is disabled after MIG-001 cutover; use canonical queue call.",
            status_code=503,
            retryable=True,
        )
    queryset = QueueEntry.objects.select_for_update().filter(id=queue_id, organisation=organisation)
    if facility is not None:
        queryset = queryset.filter(facility=facility)
    entry = queryset.first()
    if entry is None:
        raise ValueError("Queue entry was not found in this organisation.")
    if entry.status not in {"WAITING", "CALLED"}:
        raise ValueError("This queue entry is no longer available to claim.")
    entry.status = "CALLED"
    entry.current_stage = "TRIAGE"
    entry.claimed_by = actor
    entry.claimed_at = timezone.now()
    entry.called_at = entry.called_at or timezone.now()
    entry.save(update_fields=["status", "current_stage", "claimed_by", "claimed_at", "called_at", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=entry.facility,
        action="UPDATE",
        entity_type="QueueEntry",
        entity_id=entry.id,
        after={"status": entry.status, "current_stage": entry.current_stage},
    )
    return entry


def _claim_visit_linked_compatibility_entry(*, organisation, actor, queue_id, facility=None, request=None):
    """Claim a rollback-created row without bypassing canonical Visit locks."""

    queryset = QueueEntry.objects.filter(id=queue_id, organisation=organisation)
    if facility is not None:
        queryset = queryset.filter(facility=facility)
    identity = queryset.values("visit_id").first()
    if identity is None or identity["visit_id"] is None:
        raise ValueError("A MIG-001 Visit link is required while the compatibility writer is active.")
    visit = Visit.objects.select_for_update().filter(
        id=identity["visit_id"],
        organisation=organisation,
        **({"facility": facility} if facility is not None else {}),
    ).first()
    if visit is None:
        raise ValueError("The queue entry Visit was not found in this organisation.")
    entry = QueueEntry.objects.select_for_update().get(
        id=queue_id,
        organisation=organisation,
        facility=visit.facility,
    )
    if (
        visit.state not in Visit.ACTIVE_STATES
        or entry.patient_id != visit.patient_id
        or not Department.objects.filter(
            id=entry.department_id,
            organisation_id=visit.organisation_id,
            facility_id=visit.facility_id,
        ).exists()
    ):
        raise ValueError("The queue entry does not satisfy the linked Visit scope invariant.")
    if entry.status not in {"WAITING", "CALLED"} or entry.state not in {"WAITING", "CALLED"}:
        raise ValueError("This queue entry is no longer available to claim.")
    called_at = now()
    entry.status = "CALLED"
    entry.state = "CALLED"
    entry.current_stage = "TRIAGE"
    entry.claimed_by = actor
    entry.called_by = actor
    entry.claimed_at = called_at
    entry.called_at = entry.called_at or called_at
    entry.last_activity_at = called_at
    entry.version += 1
    entry.save(
        update_fields=[
            "status", "state", "current_stage", "claimed_by", "called_by", "claimed_at",
            "called_at", "last_activity_at", "version", "updated_at",
        ]
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=entry.facility,
        action="UPDATE",
        entity_type="QueueEntry",
        entity_id=entry.id,
        event_code="QUEUE_CALLED",
        source_ids={"queue_entry_id": entry.id, "visit_id": visit.id},
        after={"state": entry.state, "version": entry.version},
    )
    return entry


# S-02 keeps the historical scheduling.services import surface stable while
# the canonical QueueEntry transition owner lives in scheduling.queue.
from scheduling.queue import (  # noqa: E402  (deliberate compatibility exports)
    QueueDomainError,
    QueueStageRefusal,
    QueueSweepResult,
    assign,
    call_next_or_exact,
    cancel,
    change_priority,
    complete,
    create_or_reuse_destination,
    expire_sweep,
    hold,
    lwbs,
    mark_ready_to_resume,
    no_response,
    requeue_same_entry,
    resume,
    start_service,
    takeover,
    transfer,
)

queue_call = call_next_or_exact
queue_start_service = start_service
queue_complete = complete
queue_transfer = transfer
queue_assign = assign
queue_priority_change = change_priority
queue_hold = hold
queue_resume = resume
queue_requeue = requeue_same_entry
queue_no_response = no_response
queue_cancel = cancel
queue_lwbs = lwbs
queue_takeover = takeover
queue_expire_sweep = expire_sweep
