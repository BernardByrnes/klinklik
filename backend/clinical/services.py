import secrets
import string

from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from clinical.models import ClinicalNote, ClinicalNoteVersion, Encounter, TriageAssessment, VitalsObservation
from patients.models import Patient
from scheduling.models import QueueEntry


def _reference(prefix):
    alphabet = string.ascii_uppercase + string.digits
    return prefix + "-" + "".join(secrets.choice(alphabet) for _ in range(10))


@transaction.atomic
def start_encounter(*, organisation, facility, actor, queue_entry_id, request=None):
    queue = QueueEntry.objects.select_for_update().filter(
        id=queue_entry_id, organisation=organisation, facility=facility
    ).select_related("patient").first()
    if queue is None:
        raise ValueError("Queue entry was not found in this facility.")
    if queue.status in {"COMPLETED", "CANCELLED"}:
        raise ValueError("This queue entry is already closed.")
    encounter = Encounter.objects.filter(organisation=organisation, queue_entry=queue).first()
    if encounter is None:
        encounter = Encounter.objects.create(
            organisation=organisation,
            facility=facility,
            patient=queue.patient,
            queue_entry=queue,
            encounter_no=_reference("ENC"),
            clinician=actor,
        )
    queue.status = "IN_CONSULTATION"
    queue.current_stage = "CONSULTATION"
    queue.claimed_by = queue.claimed_by or actor
    queue.save(update_fields=["status", "current_stage", "claimed_by", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="Encounter",
        entity_id=encounter.id,
        after={"encounter_no": encounter.encounter_no, "patient_id": str(encounter.patient_id)},
    )
    return encounter


@transaction.atomic
def record_triage(*, organisation, facility, actor, queue_entry_id, data, request=None):
    queue = QueueEntry.objects.select_for_update().filter(
        id=queue_entry_id, organisation=organisation, facility=facility
    ).select_related("patient").first()
    if queue is None:
        raise ValueError("Queue entry was not found in this facility.")
    if queue.status in {"COMPLETED", "CANCELLED"}:
        raise ValueError("This queue entry is already closed.")
    assessment, _ = TriageAssessment.objects.update_or_create(
        organisation=organisation,
        facility=facility,
        queue_entry=queue,
        defaults={
            "patient": queue.patient,
            "acuity": data.get("acuity", "ROUTINE"),
            "chief_complaint": data.get("chief_complaint", ""),
            "observations": data.get("observations", {}),
            "assessed_by": actor,
        },
    )
    vitals = data.get("vitals") or {}
    if vitals:
        VitalsObservation.objects.create(
            organisation=organisation,
            facility=facility,
            patient=queue.patient,
            measured_by=actor,
            **{key: value for key, value in vitals.items() if key in {
                "systolic", "diastolic", "pulse", "temperature_c", "respiratory_rate",
                "oxygen_saturation", "weight_kg", "height_cm",
            }},
        )
    queue.status = "TRIAGED"
    queue.current_stage = "CONSULTATION"
    queue.save(update_fields=["status", "current_stage", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="TriageAssessment",
        entity_id=assessment.id,
        after={"queue_entry_id": str(queue.id), "acuity": assessment.acuity},
    )
    return assessment


def _note_audit_metadata(content):
    return {
        "note_type": "CONSULTATION",
        "fields": sorted(
            field for field in (
                "presenting_complaint", "hpi", "past_medical_history", "past_surgical_history",
                "consultation", "assessment", "plan",
            )
            if field in content
        ),
    }


@transaction.atomic
def save_note(*, organisation, facility, actor, encounter, content, request=None):
    if encounter.organisation_id != organisation.id or encounter.facility_id != facility.id:
        raise ValueError("Encounter is outside the active facility.")
    if encounter.status in {"CLOSED", "CANCELLED"}:
        raise ValueError("This encounter is closed.")
    note = encounter.notes.filter(note_type="CONSULTATION").first()
    previous_status = note.status if note is not None else None
    if note is None:
        note = ClinicalNote.objects.create(
            organisation=organisation,
            facility=facility,
            encounter=encounter,
            note_type="CONSULTATION",
            content=content,
            author=actor,
        )
    elif note.status in {"SIGNED", "AMENDED"}:
        raise ValueError("Signed clinical history is immutable; use amend.")
    else:
        note.content = {**(note.content or {}), **content}
        note.save(update_fields=["content", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE" if previous_status is None else "UPDATE",
        entity_type="ClinicalNote",
        entity_id=note.id,
        before={"status": previous_status} if previous_status is not None else None,
        after={**_note_audit_metadata(content), "status": note.status},
    )
    return note


@transaction.atomic
def sign_note(*, organisation, facility, actor, encounter, content=None, request=None):
    note = encounter.notes.select_for_update().filter(
        organisation=organisation, facility=facility, note_type="CONSULTATION"
    ).first()
    if note is None:
        note = save_note(
            organisation=organisation, facility=facility, actor=actor, encounter=encounter,
            content=content or {}, request=request
        )
    if note.status in {"SIGNED", "AMENDED"}:
        raise ValueError("This note is already signed.")
    if content is not None:
        note.content = {**(note.content or {}), **content}
    version = ClinicalNoteVersion.objects.create(
        organisation=organisation,
        note=note,
        version_number=note.current_version + 1,
        content=note.content,
        created_by=actor,
        reason="Initial signature",
    )
    now = timezone.now()
    note.status = "SIGNED"
    note.signed_by = actor
    note.signed_at = now
    note.current_version = version.version_number
    note.save(update_fields=["content", "status", "signed_by", "signed_at", "current_version", "updated_at"])
    encounter.status = "SIGNED"
    encounter.signed_at = now
    encounter.save(update_fields=["status", "signed_at", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="SIGN",
        entity_type="ClinicalNote",
        entity_id=note.id,
        after={"version": version.version_number, "encounter_id": str(encounter.id)},
    )
    return note


@transaction.atomic
def amend_note(*, organisation, facility, actor, encounter, content, reason, request=None):
    note = encounter.notes.select_for_update().filter(
        organisation=organisation, facility=facility, note_type="CONSULTATION"
    ).first()
    if note is None or note.status not in {"SIGNED", "AMENDED"}:
        raise ValueError("Only a signed clinical note can be amended.")
    version = ClinicalNoteVersion.objects.create(
        organisation=organisation,
        note=note,
        version_number=note.current_version + 1,
        content=content,
        created_by=actor,
        reason=reason,
    )
    note.content = content
    note.status = "AMENDED"
    note.current_version = version.version_number
    note.save(update_fields=["content", "status", "current_version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="AMEND",
        entity_type="ClinicalNote",
        entity_id=note.id,
        after={"version": version.version_number, "reason": reason},
        reason=reason,
    )
    return note
