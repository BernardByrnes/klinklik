import hashlib
import hmac
import json

from django.conf import settings

from clinical.models import ClinicalNote


class ClinicalNoteRevisionConflict(ValueError):
    def __init__(self, *, encounter, note, current_etag):
        self.current_etag = current_etag
        self.current_status = note.status if note is not None else "ABSENT"
        self.current_encounter_status = encounter.status
        self.current_content = dict(note.content or {}) if note is not None else {}
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
