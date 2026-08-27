from django.db import transaction

from audit.services import record_event
from clinical.concurrency import (
    ClinicalNoteRevisionConflict,
    consultation_note_etag,
    require_current_consultation_etag,
)
from clinical.models import ClinicalNote, Encounter, Referral
from scheduling.models import FollowUpRecommendation


class DispositionDomainError(ValueError):
    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__(detail)


class DispositionRevisionConflict(ValueError):
    def __init__(self, conflict):
        self.current_etag = conflict.current_etag
        self.current_status = conflict.current_status
        self.current_encounter_status = conflict.current_encounter_status
        self.current_content = conflict.current_content
        self.current_complaints = conflict.current_complaints
        self.current_diagnoses = conflict.current_diagnoses
        self.current_disposition = conflict.current_disposition
        self.current_disposition_note = conflict.current_disposition_note
        self.current_follow_up = conflict.current_follow_up
        self.current_saved_at = conflict.current_saved_at
        super().__init__("The consultation changed elsewhere; review the current disposition before retrying.")


def _lock_encounter(*, organisation, facility, encounter):
    locked = Encounter.objects.select_for_update().filter(
        id=encounter.id,
        organisation=organisation,
        facility=facility,
    ).first()
    if locked is None:
        raise DispositionDomainError("ENCOUNTER_NOT_FOUND", "Encounter is outside the active facility.")
    return locked


def _lock_note(*, organisation, facility, encounter):
    return ClinicalNote.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        encounter=encounter,
        note_type="CONSULTATION",
    ).first()


def _validate_candidate(*, disposition, disposition_note):
    allowed = {choice for choice, _label in Encounter.DISPOSITION_CHOICES}
    if disposition is not None and disposition not in allowed:
        raise DispositionDomainError("DISPOSITION_INVALID", "The disposition is not supported.")
    if not isinstance(disposition_note, str) or len(disposition_note) > 1000:
        raise DispositionDomainError(
            "DISPOSITION_NOTE_INVALID",
            "The disposition note must be text of 1000 characters or fewer.",
        )
    if disposition == "OTHER" and not disposition_note.strip():
        raise DispositionDomainError(
            "DISPOSITION_NOTE_REQUIRED",
            "An Other disposition requires a non-blank note.",
        )
    if disposition is None and disposition_note.strip():
        raise DispositionDomainError(
            "DISPOSITION_NOTE_WITHOUT_DISPOSITION",
            "A disposition note cannot be stored without a disposition.",
        )


def _ensure_mutable(*, encounter, note):
    if encounter.status in {"SIGNED", "CLOSED", "CANCELLED"}:
        raise DispositionDomainError(
            "DISPOSITION_IMMUTABLE",
            "Disposition cannot be changed after this encounter is signed or closed.",
        )
    if note is not None and note.status in {"SIGNED", "AMENDED"}:
        raise DispositionDomainError(
            "DISPOSITION_IMMUTABLE",
            "Disposition cannot be changed after this consultation is signed.",
        )


def _audit_state(encounter):
    return {
        "encounter_id": str(encounter.id),
        "disposition": encounter.disposition,
        "disposition_note_present": bool((encounter.disposition_note or "").strip()),
    }

def require_signable_disposition(*, encounter):
    disposition = encounter.disposition
    if disposition is None:
        raise DispositionDomainError(
            "DISPOSITION_REQUIRED",
            "A disposition is required before signing.",
        )
    if disposition == "OTHER" and not (encounter.disposition_note or "").strip():
        raise DispositionDomainError(
            "DISPOSITION_NOTE_REQUIRED",
            "An Other disposition requires a non-blank note.",
        )
    if disposition == "REFERRED_OUT" and not Referral.objects.filter(
        organisation=encounter.organisation_id,
        facility=encounter.facility_id,
        encounter=encounter,
    ).exists():
        raise DispositionDomainError(
            "REFERRAL_REQUIRED",
            "A referral record is required before signing a referred-out encounter.",
        )
    if disposition == "REVIEW_SCHEDULED" and not FollowUpRecommendation.objects.filter(
        organisation=encounter.organisation_id,
        facility=encounter.facility_id,
        encounter=encounter,
        recommended_date__isnull=False,
    ).exists():
        raise DispositionDomainError(
            "FOLLOW_UP_REQUIRED",
            "A follow-up date is required before signing a review-scheduled encounter.",
        )


@transaction.atomic
def set_disposition(*, organisation, facility, actor, encounter, data, expected_etag, request=None):
    encounter = _lock_encounter(organisation=organisation, facility=facility, encounter=encounter)
    note = _lock_note(organisation=organisation, facility=facility, encounter=encounter)
    try:
        require_current_consultation_etag(
            encounter=encounter,
            note=note,
            expected_etag=expected_etag,
        )
    except ClinicalNoteRevisionConflict as exc:
        raise DispositionRevisionConflict(exc) from exc
    _ensure_mutable(encounter=encounter, note=note)

    disposition = data.get("disposition")
    if "disposition_note" in data:
        disposition_note = data["disposition_note"]
    elif disposition is None:
        disposition_note = ""
    else:
        disposition_note = encounter.disposition_note or ""
    _validate_candidate(disposition=disposition, disposition_note=disposition_note)

    before = _audit_state(encounter)
    encounter.disposition = disposition
    encounter.disposition_note = disposition_note
    encounter.save(update_fields=["disposition", "disposition_note", "updated_at"])
    after = _audit_state(encounter)
    if before != after:
        record_event(
            request=request,
            organisation=organisation,
            actor=actor,
            facility=facility,
            action="UPDATE",
            entity_type="Encounter",
            entity_id=encounter.id,
            before=before,
            after={
                **after,
                "changed_fields": ["disposition", "disposition_note"],
            },
        )
    return {
        "encounter": encounter,
        "note": note,
        "consultation_etag": consultation_note_etag(encounter=encounter, note=note),
    }