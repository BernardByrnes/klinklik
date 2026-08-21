from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from audit.services import record_event
from patients.models import Patient
from scheduling.models import QueueEntry
from tenancy.models import Department


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
