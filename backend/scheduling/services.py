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
            entry.completed_at = cancelled_at
            entry.version += 1
            entry.save(update_fields=["status", "completed_at", "version", "updated_at"])

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
        current_stage="PAYMENT" if status == "WAITING_PAYMENT" else "RECEPTION",
        queue_time=now(),
        notes=notes,
        source_event_id=f"VISIT:{visit.id}:{queue_type}",
    )


def record_arrival_enquiry(*, organisation, facility, actor, reason_code, source_event_id, safe_notes=""):
    assert_transaction_active()
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
    sequence = (last["max_sequence"] or 0) + 1
    entry = QueueEntry.objects.create(
        organisation=organisation,
        facility=facility,
        patient=patient,
        department=department,
        queue_date=today,
        sequence=sequence,
        visit_type=visit_type,
        notes=notes,
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


@transaction.atomic
def claim_queue_entry(*, organisation, actor, queue_id, request=None):
    entry = QueueEntry.objects.select_for_update().filter(id=queue_id, organisation=organisation).first()
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
