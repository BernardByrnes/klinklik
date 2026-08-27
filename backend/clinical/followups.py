from django.db import transaction

from audit.services import record_event
from clinical.concurrency import (
    ClinicalNoteRevisionConflict,
    consultation_note_etag,
    require_current_consultation_etag,
)
from clinical.models import ClinicalNote, Encounter
from scheduling.models import FollowUpRecommendation


FOLLOW_UP_INTERVAL_UNITS = frozenset(
    choice for choice, _label in FollowUpRecommendation.INTERVAL_UNIT_CHOICES
)
_MISSING = object()


class FollowUpDomainError(ValueError):
    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__(detail)


class FollowUpRevisionConflict(ValueError):
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
        super().__init__("The consultation changed elsewhere; review the current follow-up before retrying.")


def _lock_encounter(*, organisation, facility, encounter):
    locked = Encounter.objects.select_for_update().filter(
        id=encounter.id,
        organisation=organisation,
        facility=facility,
    ).select_related("patient").first()
    if locked is None:
        raise FollowUpDomainError("ENCOUNTER_NOT_FOUND", "Encounter is outside the active facility.")
    return locked


def _lock_note(*, organisation, facility, encounter):
    return ClinicalNote.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        encounter=encounter,
        note_type="CONSULTATION",
    ).first()


def _ensure_mutable(*, encounter, note):
    if encounter.status in {"SIGNED", "CLOSED", "CANCELLED"}:
        raise FollowUpDomainError(
            "FOLLOW_UP_IMMUTABLE",
            "Follow-up cannot be changed after this encounter is signed or closed.",
        )
    if note is not None and note.status in {"SIGNED", "AMENDED"}:
        raise FollowUpDomainError(
            "FOLLOW_UP_IMMUTABLE",
            "Follow-up cannot be changed after this consultation is signed.",
        )


def follow_up_schedule_mode(*, recommended_date, interval_value, interval_unit):
    normalized_unit = interval_unit or ""
    if recommended_date is not None:
        return "DATE" if interval_value is None and not normalized_unit else None
    if interval_value is None or not normalized_unit:
        return None
    try:
        valid_value = int(interval_value) > 0
    except (TypeError, ValueError):
        valid_value = False
    return "INTERVAL" if valid_value and normalized_unit in FOLLOW_UP_INTERVAL_UNITS else None


def _validate_schedule(*, recommended_date, interval_value, interval_unit):
    mode = follow_up_schedule_mode(
        recommended_date=recommended_date,
        interval_value=interval_value,
        interval_unit=interval_unit,
    )
    if mode is None:
        raise FollowUpDomainError(
            "FOLLOW_UP_SCHEDULE_INVALID",
            "Provide exactly one valid follow-up date or interval (positive value with DAYS, WEEKS, or MONTHS).",
        )
    return mode


def _audit_state(follow_up):
    return {
        "encounter_id": str(follow_up.encounter_id),
        "follow_up_id": str(follow_up.id),
        "schedule_mode": follow_up_schedule_mode(
            recommended_date=follow_up.recommended_date,
            interval_value=follow_up.interval_value,
            interval_unit=follow_up.interval_unit,
        ),
        "recommended_date_present": follow_up.recommended_date is not None,
        "interval_value_present": follow_up.interval_value is not None,
        "interval_unit_present": bool(follow_up.interval_unit),
        "instructions_present": bool(follow_up.instructions),
    }


def _effective_schedule(*, follow_up, data):
    current_date = follow_up.recommended_date if follow_up is not None else None
    current_value = follow_up.interval_value if follow_up is not None else None
    current_unit = follow_up.interval_unit if follow_up is not None else None

    requested_date = data.get("recommended_date", _MISSING)
    requested_value = data.get("interval_value", _MISSING)
    requested_unit = data.get("interval_unit", _MISSING)

    if requested_date is not _MISSING and requested_date is not None:
        if (
            requested_value is not _MISSING
            and requested_value is not None
        ) or (
            requested_unit is not _MISSING
            and bool(requested_unit)
        ):
            raise FollowUpDomainError(
                "FOLLOW_UP_SCHEDULE_INVALID",
                "A follow-up date cannot be combined with an interval.",
            )
        return requested_date, None, None

    if requested_date is None and requested_date is not _MISSING:
        return (
            None,
            requested_value if requested_value is not _MISSING else None,
            requested_unit if requested_unit is not _MISSING else None,
        )

    if requested_value is not _MISSING or requested_unit is not _MISSING:
        return (
            None,
            requested_value if requested_value is not _MISSING else None,
            requested_unit if requested_unit is not _MISSING else None,
        )

    return current_date, current_value, current_unit


@transaction.atomic
def save_follow_up(
    *,
    organisation,
    facility,
    actor,
    encounter,
    data,
    expected_etag,
    request=None,
):
    encounter = _lock_encounter(organisation=organisation, facility=facility, encounter=encounter)
    note = _lock_note(organisation=organisation, facility=facility, encounter=encounter)
    try:
        require_current_consultation_etag(
            encounter=encounter,
            note=note,
            expected_etag=expected_etag,
        )
    except ClinicalNoteRevisionConflict as exc:
        raise FollowUpRevisionConflict(exc) from exc
    _ensure_mutable(encounter=encounter, note=note)

    follow_up = (
        FollowUpRecommendation.objects.select_for_update()
        .filter(
            organisation=organisation,
            facility=facility,
            encounter=encounter,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if follow_up is not None and follow_up.patient_id != encounter.patient_id:
        raise FollowUpDomainError(
            "FOLLOW_UP_SCOPE_INVALID",
            "The existing follow-up is not linked to this encounter's patient.",
        )

    recommended_date, interval_value, interval_unit = _effective_schedule(
        follow_up=follow_up,
        data=data,
    )
    instructions = (
        data["instructions"]
        if "instructions" in data
        else follow_up.instructions
        if follow_up is not None
        else ""
    )
    _validate_schedule(
        recommended_date=recommended_date,
        interval_value=interval_value,
        interval_unit=interval_unit,
    )

    if follow_up is None:
        follow_up = FollowUpRecommendation.objects.create(
            organisation=organisation,
            facility=facility,
            patient=encounter.patient,
            encounter=encounter,
            recommended_date=recommended_date,
            interval_value=interval_value,
            interval_unit=interval_unit,
            instructions=instructions,
            status="OPEN",
            created_by=actor,
        )
        action = "CREATE"
        before = None
        changed_fields = ["recommended_date", "interval_value", "interval_unit", "instructions"]
    else:
        before = _audit_state(follow_up)
        changed_fields = []
        if follow_up.recommended_date != recommended_date:
            follow_up.recommended_date = recommended_date
            changed_fields.append("recommended_date")
        if follow_up.interval_value != interval_value:
            follow_up.interval_value = interval_value
            changed_fields.append("interval_value")
        if follow_up.interval_unit != interval_unit:
            follow_up.interval_unit = interval_unit
            changed_fields.append("interval_unit")
        if follow_up.instructions != instructions:
            follow_up.instructions = instructions
            changed_fields.append("instructions")
        if changed_fields:
            follow_up.save(update_fields=[*changed_fields, "updated_at"])
            action = "UPDATE"
        else:
            action = None

    if action is not None:
        after = _audit_state(follow_up)
        after["changed_fields"] = changed_fields
        record_event(
            request=request,
            organisation=organisation,
            actor=actor,
            facility=facility,
            action=action,
            entity_type="FollowUpRecommendation",
            entity_id=follow_up.id,
            before=before,
            after=after,
        )

    return {
        "encounter": encounter,
        "note": note,
        "follow_up": follow_up,
        "consultation_etag": consultation_note_etag(encounter=encounter, note=note),
    }