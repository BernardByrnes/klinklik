from datetime import timedelta

import secrets
import string

from django.db import transaction
from django.utils import timezone

from audit.models import AuditEvent
from audit.services import record_event
from clinical.complaints import normalize_complaints, resolve_complaints
from clinical.concurrency import require_current_consultation_etag
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


_AUTOSAVE_HEADER = "X-KlinKlik-Autosave"
_AUTOSAVE_MARKER = "1"
_AUTOSAVE_REASON = "ENCOUNTER_DRAFT_UPDATED"

EXAMINATION_FIELDS = {
    "general_examination",
    "cardiovascular_examination",
    "respiratory_examination",
    "abdominal_examination",
    "neurological_examination",
    "genitourinary_examination",
    "musculoskeletal_examination",
}


class PresentingComplaintRequired(ValueError):
    code = "PRESENTING_COMPLAINT_REQUIRED"

    def __init__(self):
        super().__init__("At least one presenting complaint is required before signing.")


def normalize_examination_content(content):
    normalized = dict(content or {})
    for field in EXAMINATION_FIELDS:
        value = normalized.get(field)
        if isinstance(value, str) and value.strip() == "":
            normalized.pop(field, None)
    return normalized


def _is_autosave_request(request):
    return request is not None and request.headers.get(_AUTOSAVE_HEADER) == _AUTOSAVE_MARKER


def _record_autosave_summary(*, organisation, facility, actor, encounter, request=None):
    now = timezone.now()
    minute_start = now.replace(second=0, microsecond=0)
    minute_end = minute_start + timedelta(minutes=1)
    existing = AuditEvent.objects.filter(
        organisation=organisation,
        facility=facility,
        actor=actor,
        action="UPDATE",
        entity_type="Encounter",
        entity_id=str(encounter.id),
        occurred_at__gte=minute_start,
        occurred_at__lt=minute_end,
    )
    if any(
        (event.after or {}).get("reason") == _AUTOSAVE_REASON
        and (event.after or {}).get("note_type") == "CONSULTATION"
        for event in existing
    ):
        return
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="Encounter",
        entity_id=encounter.id,
        after={
            "reason": _AUTOSAVE_REASON,
            "note_type": "CONSULTATION",
            "minute": minute_start.isoformat(),
        },
    )
def _note_audit_metadata(content, *, complaints_changed=False):
    fields = sorted(
        field for field in (
            "presenting_complaint", "hpi", "past_medical_history", "past_surgical_history",
            "family_history", "social_history", "general_examination", "cardiovascular_examination", "respiratory_examination",
            "abdominal_examination", "neurological_examination",
            "genitourinary_examination", "musculoskeletal_examination",
            "consultation", "assessment", "plan",
        )
        if field in content
    )
    if complaints_changed:
        fields.append("complaints")
        fields.sort()
    return {"note_type": "CONSULTATION", "fields": fields}


def _lock_encounter_for_note(*, organisation, facility, encounter):
    locked_encounter = Encounter.objects.select_for_update().filter(
        id=encounter.id,
        organisation=organisation,
        facility=facility,
    ).first()
    if locked_encounter is None:
        raise ValueError("Encounter is outside the active facility.")
    return locked_encounter


def _lock_consultation_note(*, organisation, facility, encounter):
    return ClinicalNote.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        encounter=encounter,
        note_type="CONSULTATION",
    ).first()


@transaction.atomic
def save_note(*, organisation, facility, actor, encounter, content, complaints=None, expected_etag=None, request=None):
    encounter = _lock_encounter_for_note(
        organisation=organisation,
        facility=facility,
        encounter=encounter,
    )
    note = _lock_consultation_note(
        organisation=organisation,
        facility=facility,
        encounter=encounter,
    )
    require_current_consultation_etag(encounter=encounter, note=note, expected_etag=expected_etag)
    normalized_complaints = resolve_complaints(content=content, complaints=complaints)
    previous_status = note.status if note is not None else None
    if encounter.status in {"CLOSED", "CANCELLED"}:
        raise ValueError("This encounter is closed.")
    if note is None:
        note = ClinicalNote.objects.create(
            organisation=organisation,
            facility=facility,
            encounter=encounter,
            note_type="CONSULTATION",
            content=normalize_examination_content(content),
            author=actor,
        )
    elif note.status in {"SIGNED", "AMENDED"}:
        raise ValueError("Signed clinical history is immutable; use amend.")
    else:
        note.content = normalize_examination_content({**(note.content or {}), **content})
        note.save(update_fields=["content", "updated_at"])
    if normalized_complaints is not None:
        encounter.complaints = normalized_complaints
        encounter.save(update_fields=["complaints", "updated_at"])
    if _is_autosave_request(request):
        _record_autosave_summary(
            organisation=organisation,
            facility=facility,
            actor=actor,
            encounter=encounter,
            request=request,
        )
    else:
        record_event(
            request=request,
            organisation=organisation,
            actor=actor,
            facility=facility,
            action="CREATE" if previous_status is None else "UPDATE",
            entity_type="ClinicalNote",
            entity_id=note.id,
            before={"status": previous_status} if previous_status is not None else None,
            after={
                **_note_audit_metadata(content, complaints_changed=normalized_complaints is not None),
                "status": note.status,
            },
        )
    return note


@transaction.atomic
def sign_note(*, organisation, facility, actor, encounter, content=None, complaints=None, expected_etag=None, request=None):
    encounter = _lock_encounter_for_note(
        organisation=organisation,
        facility=facility,
        encounter=encounter,
    )
    note = _lock_consultation_note(
        organisation=organisation,
        facility=facility,
        encounter=encounter,
    )
    require_current_consultation_etag(encounter=encounter, note=note, expected_etag=expected_etag)
    incoming_complaints = resolve_complaints(content=content or {}, complaints=complaints)
    if note is None:
        note = save_note(
            organisation=organisation, facility=facility, actor=actor, encounter=encounter,
            content=content or {}, complaints=incoming_complaints,
            expected_etag=expected_etag, request=request
        )
    candidate_complaints = (
        incoming_complaints
        if incoming_complaints is not None
        else normalize_complaints(encounter.complaints or [])
    )
    if not candidate_complaints:
        raise PresentingComplaintRequired()
    if note.status in {"SIGNED", "AMENDED"}:
        raise ValueError("This note is already signed.")
    if content is not None:
        note.content = normalize_examination_content({**(note.content or {}), **content})
    note.content = normalize_examination_content(note.content)
    if incoming_complaints is not None:
        encounter.complaints = incoming_complaints
        encounter.save(update_fields=["complaints", "updated_at"])
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
def amend_note(*, organisation, facility, actor, encounter, content, reason, expected_etag=None, request=None):
    encounter = _lock_encounter_for_note(
        organisation=organisation,
        facility=facility,
        encounter=encounter,
    )
    note = _lock_consultation_note(
        organisation=organisation,
        facility=facility,
        encounter=encounter,
    )
    require_current_consultation_etag(encounter=encounter, note=note, expected_etag=expected_etag)
    if note is None or note.status not in {"SIGNED", "AMENDED"}:
        raise ValueError("Only a signed clinical note can be amended.")
    normalized_content = normalize_examination_content(content)
    version = ClinicalNoteVersion.objects.create(
        organisation=organisation,
        note=note,
        version_number=note.current_version + 1,
        content=normalized_content,
        created_by=actor,
        reason=reason,
    )
    note.content = normalized_content
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
