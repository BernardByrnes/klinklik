import hashlib
import hmac
import json

from django.conf import settings

from clinical.diagnosis_state import active_diagnosis_snapshot, diagnosis_revision_snapshot
from clinical.models import ClinicalNote


def follow_up_recommendation_for_encounter(encounter):
    from scheduling.models import FollowUpRecommendation

    prefetched = getattr(encounter, "_prefetched_objects_cache", {}).get("follow_ups")
    if prefetched is not None:
        scoped = [
            follow_up
            for follow_up in prefetched
            if follow_up.organisation_id == encounter.organisation_id
            and follow_up.facility_id == encounter.facility_id
        ]
        return max(scoped, key=lambda follow_up: (follow_up.created_at, str(follow_up.id)), default=None)
    return (
        FollowUpRecommendation.objects.filter(
            organisation=encounter.organisation_id,
            facility=encounter.facility_id,
            encounter=encounter,
        )
        .order_by("-created_at", "-id")
        .first()
    )


def follow_up_snapshot(encounter):
    follow_up = follow_up_recommendation_for_encounter(encounter)
    if follow_up is None:
        return None
    return {
        "id": str(follow_up.id),
        "patient": str(follow_up.patient_id),
        "encounter": str(follow_up.encounter_id),
        "recommended_date": follow_up.recommended_date.isoformat() if follow_up.recommended_date else None,
        "interval_value": follow_up.interval_value,
        "interval_unit": follow_up.interval_unit,
        "instructions": follow_up.instructions,
        "status": follow_up.status,
        "created_by": str(follow_up.created_by_id),
        "created_at": follow_up.created_at.isoformat(),
        "updated_at": follow_up.updated_at.isoformat(),
    }


class ClinicalNoteRevisionConflict(ValueError):
    def __init__(self, *, encounter, note, current_etag):
        self.current_etag = current_etag
        self.current_status = note.status if note is not None else "ABSENT"
        self.current_encounter_status = encounter.status
        self.current_content = dict(note.content or {}) if note is not None else {}
        self.current_complaints = list(encounter.complaints or [])
        self.current_diagnoses = active_diagnosis_snapshot(encounter)
        self.current_disposition = encounter.disposition
        self.current_disposition_note = encounter.disposition_note
        self.current_follow_up = follow_up_snapshot(encounter)
        self.current_saved_at = note.updated_at.isoformat() if note is not None else None
        super().__init__("Clinical note revision is stale.")


def consultation_note_for_encounter(encounter):
    prefetched_notes = getattr(encounter, "_prefetched_objects_cache", {}).get("notes")
    if prefetched_notes is not None:
        return next((note for note in prefetched_notes if note.note_type == "CONSULTATION"), None)
    return ClinicalNote.objects.filter(
        organisation=encounter.organisation_id,
        facility=encounter.facility_id,
        encounter=encounter,
        note_type="CONSULTATION",
    ).first()


def consultation_note_etag(*, encounter, note):
    state = {
        "scope": "clinical-note-consultation-v1",
        "organisation": str(encounter.organisation_id),
        "facility": str(encounter.facility_id),
        "encounter": str(encounter.id),
        "note": str(note.id) if note is not None else None,
        "note_status": note.status if note is not None else None,
        "current_version": note.current_version if note is not None else None,
        "updated_at": note.updated_at.isoformat() if note is not None else None,
        "content": note.content if note is not None else None,
        "complaints": list(encounter.complaints or []),
        "diagnoses": diagnosis_revision_snapshot(encounter),
        "disposition": encounter.disposition,
        "disposition_note": encounter.disposition_note,
        "follow_up": follow_up_snapshot(encounter),
    }
    payload = json.dumps(state, default=str, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(settings.SECRET_KEY.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return '"' + digest + '"'


def require_current_consultation_etag(*, encounter, note, expected_etag):
    current_etag = consultation_note_etag(encounter=encounter, note=note)
    if expected_etag is not None and not hmac.compare_digest(expected_etag, current_etag):
        raise ClinicalNoteRevisionConflict(
            encounter=encounter,
            note=note,
            current_etag=current_etag,
        )
    return current_etag
