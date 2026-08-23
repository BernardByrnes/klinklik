from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from clinical.concurrency import (
    ClinicalNoteRevisionConflict,
    consultation_note_etag,
    require_current_consultation_etag,
)
from clinical.diagnosis_state import active_diagnosis_snapshot
from clinical.models import ClinicalNote, Diagnosis, Encounter


class DiagnosisDomainError(ValueError):
    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__(detail)


class DiagnosisRevisionConflict(ValueError):
    def __init__(self, *, encounter, note, current_etag):
        self.current_etag = current_etag
        self.current_encounter_status = encounter.status
        self.current_diagnoses = active_diagnosis_snapshot(encounter)
        self.current_note_status = note.status if note is not None else "ABSENT"
        super().__init__("The consultation changed elsewhere; review the current diagnoses before retrying.")


def _lock_encounter(*, organisation, facility, encounter):
    locked = Encounter.objects.select_for_update().filter(
        id=encounter.id,
        organisation=organisation,
        facility=facility,
    ).first()
    if locked is None:
        raise DiagnosisDomainError("ENCOUNTER_NOT_FOUND", "Encounter is outside the active facility.")
    return locked


def _lock_note(*, organisation, facility, encounter):
    return ClinicalNote.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        encounter=encounter,
        note_type="CONSULTATION",
    ).first()


def _require_current_etag(*, encounter, note, expected_etag):
    try:
        return require_current_consultation_etag(
            encounter=encounter,
            note=note,
            expected_etag=expected_etag,
        )
    except ClinicalNoteRevisionConflict as exc:
        raise DiagnosisRevisionConflict(
            encounter=encounter,
            note=note,
            current_etag=exc.current_etag,
        ) from exc


def _ensure_mutable(*, encounter, note):
    if encounter.status in {"SIGNED", "CLOSED", "CANCELLED"}:
        raise DiagnosisDomainError(
            "DIAGNOSIS_IMMUTABLE",
            "Diagnoses cannot be changed after this encounter is signed or closed.",
        )
    if note is not None and note.status in {"SIGNED", "AMENDED"}:
        raise DiagnosisDomainError(
            "DIAGNOSIS_IMMUTABLE",
            "Diagnoses cannot be changed after this consultation is signed.",
        )


def _candidate_values(*, data, current=None):
    values = {
        "diagnosis_type": current.diagnosis_type if current is not None else "FINAL",
        "code": current.code if current is not None else "",
        "label": current.label if current is not None else "",
        "certainty_note": current.certainty_note if current is not None else "",
        "is_primary": current.is_primary if current is not None else False,
        "no_diagnosis_reason": current.no_diagnosis_reason if current is not None else "",
    }
    values.update({key: value for key, value in data.items() if key in values})
    diagnosis_type = values["diagnosis_type"]
    code = values["code"]
    label = values["label"]
    certainty_note = values["certainty_note"]
    no_diagnosis_reason = values["no_diagnosis_reason"]
    explicit_code = "code" in data
    explicit_certainty = "certainty_note" in data
    explicit_primary = "is_primary" in data
    if diagnosis_type in {"WORKING", "FINAL"}:
        if not isinstance(label, str) or not label.strip():
            raise DiagnosisDomainError(
                "DIAGNOSIS_LABEL_REQUIRED",
                "A working or final diagnosis requires a non-blank label.",
            )
        if diagnosis_type == "WORKING" and values["is_primary"] and explicit_primary:
            raise DiagnosisDomainError(
                "PRIMARY_DIAGNOSIS_INVALID",
                "A working diagnosis cannot be primary.",
            )
        return {
            "diagnosis_type": diagnosis_type,
            "code": code if code.strip() else "",
            "label": label,
            "coded": bool(code.strip()),
            "certainty_note": certainty_note,
            "is_primary": bool(values["is_primary"]) if diagnosis_type == "FINAL" else False,
            "no_diagnosis_reason": "",
        }
    if diagnosis_type == "NO_DIAGNOSIS":
        if (explicit_code and code.strip()) or (explicit_certainty and certainty_note.strip()) or (
            explicit_primary and values["is_primary"]
        ):
            raise DiagnosisDomainError(
                "DIAGNOSIS_STATE_INVALID",
                "No diagnosis cannot include a code, certainty note, or primary flag.",
            )
        if not isinstance(no_diagnosis_reason, str) or not no_diagnosis_reason.strip():
            raise DiagnosisDomainError(
                "NO_DIAGNOSIS_REASON_REQUIRED",
                "A no-diagnosis entry requires a non-blank reason.",
            )
        return {
            "diagnosis_type": "NO_DIAGNOSIS",
            "code": "",
            "label": "",
            "coded": False,
            "certainty_note": "",
            "is_primary": False,
            "no_diagnosis_reason": no_diagnosis_reason,
        }
    raise DiagnosisDomainError("DIAGNOSIS_STATE_INVALID", "The diagnosis type is not supported.")


def _check_active_exclusivity(*, encounter, candidate, current=None):
    active = Diagnosis.objects.select_for_update().filter(
        organisation=encounter.organisation_id,
        facility=encounter.facility_id,
        encounter=encounter,
        status="ACTIVE",
    )
    if current is not None:
        active = active.exclude(id=current.id)
    diagnosis_type = candidate["diagnosis_type"]
    if diagnosis_type == "NO_DIAGNOSIS":
        if active.filter(diagnosis_type__in=["FINAL", "NO_DIAGNOSIS"]).exists():
            raise DiagnosisDomainError(
                "DIAGNOSIS_STATE_INVALID",
                "No diagnosis cannot coexist with an active final diagnosis or another no-diagnosis entry.",
            )
    elif diagnosis_type == "FINAL" and active.filter(diagnosis_type="NO_DIAGNOSIS").exists():
        raise DiagnosisDomainError(
            "DIAGNOSIS_STATE_INVALID",
            "A final diagnosis cannot coexist with an active no-diagnosis entry.",
        )
    if candidate["diagnosis_type"] == "FINAL" and candidate["is_primary"]:
        if active.filter(diagnosis_type="FINAL", is_primary=True).exists():
            raise DiagnosisDomainError(
                "PRIMARY_DIAGNOSIS_INVALID",
                "Only one active final diagnosis may be primary.",
            )


def _audit_state(diagnosis):
    return {
        "encounter_id": str(diagnosis.encounter_id),
        "diagnosis_type": diagnosis.diagnosis_type,
        "coded": diagnosis.coded,
        "is_primary": diagnosis.is_primary,
        "status": diagnosis.status,
    }


def _result(*, encounter, note, diagnosis):
    return {
        "encounter": encounter,
        "note": note,
        "diagnosis": diagnosis,
        "diagnoses": active_diagnosis_snapshot(encounter),
        "consultation_etag": consultation_note_etag(encounter=encounter, note=note),
    }


@transaction.atomic
def create_diagnosis(*, organisation, facility, actor, encounter, data, expected_etag=None, request=None):
    encounter = _lock_encounter(organisation=organisation, facility=facility, encounter=encounter)
    note = _lock_note(organisation=organisation, facility=facility, encounter=encounter)
    _require_current_etag(encounter=encounter, note=note, expected_etag=expected_etag)
    _ensure_mutable(encounter=encounter, note=note)
    candidate = _candidate_values(data=data)
    _check_active_exclusivity(encounter=encounter, candidate=candidate)
    diagnosis = Diagnosis.objects.create(
        organisation=organisation,
        facility=facility,
        encounter=encounter,
        recorded_by=actor,
        **candidate,
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="Diagnosis",
        entity_id=diagnosis.id,
        after=_audit_state(diagnosis),
    )
    return _result(encounter=encounter, note=note, diagnosis=diagnosis)


@transaction.atomic
def update_diagnosis(*, organisation, facility, actor, encounter, diagnosis_id, data, expected_etag=None, request=None):
    encounter = _lock_encounter(organisation=organisation, facility=facility, encounter=encounter)
    note = _lock_note(organisation=organisation, facility=facility, encounter=encounter)
    _require_current_etag(encounter=encounter, note=note, expected_etag=expected_etag)
    _ensure_mutable(encounter=encounter, note=note)
    diagnosis = Diagnosis.objects.select_for_update().filter(
        id=diagnosis_id,
        organisation=organisation,
        facility=facility,
        encounter=encounter,
        status="ACTIVE",
    ).first()
    if diagnosis is None:
        raise DiagnosisDomainError("DIAGNOSIS_NOT_FOUND", "Active diagnosis was not found in this encounter.")
    before = _audit_state(diagnosis)
    candidate = _candidate_values(data=data, current=diagnosis)
    _check_active_exclusivity(encounter=encounter, candidate=candidate, current=diagnosis)
    for field, value in candidate.items():
        setattr(diagnosis, field, value)
    diagnosis.save(update_fields=[*candidate.keys(), "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="Diagnosis",
        entity_id=diagnosis.id,
        before=before,
        after=_audit_state(diagnosis),
    )
    return _result(encounter=encounter, note=note, diagnosis=diagnosis)


@transaction.atomic
def remove_diagnosis(*, organisation, facility, actor, encounter, diagnosis_id, expected_etag=None, request=None):
    encounter = _lock_encounter(organisation=organisation, facility=facility, encounter=encounter)
    note = _lock_note(organisation=organisation, facility=facility, encounter=encounter)
    _require_current_etag(encounter=encounter, note=note, expected_etag=expected_etag)
    _ensure_mutable(encounter=encounter, note=note)
    diagnosis = Diagnosis.objects.select_for_update().filter(
        id=diagnosis_id,
        organisation=organisation,
        facility=facility,
        encounter=encounter,
        status="ACTIVE",
    ).first()
    if diagnosis is None:
        raise DiagnosisDomainError("DIAGNOSIS_NOT_FOUND", "Active diagnosis was not found in this encounter.")
    before = _audit_state(diagnosis)
    diagnosis.status = "REMOVED"
    diagnosis.removed_by = actor
    diagnosis.removed_at = timezone.now()
    diagnosis.is_primary = False
    diagnosis.save(update_fields=["status", "removed_by", "removed_at", "is_primary", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="Diagnosis",
        entity_id=diagnosis.id,
        before=before,
        after={
            "encounter_id": str(diagnosis.encounter_id),
            "diagnosis_type": diagnosis.diagnosis_type,
            "is_primary": False,
            "status": "REMOVED",
        },
    )
    return _result(encounter=encounter, note=note, diagnosis=diagnosis)


def require_signable_diagnosis_state(*, encounter):
    active = list(
        Diagnosis.objects.select_for_update().filter(
            organisation=encounter.organisation_id,
            facility=encounter.facility_id,
            encounter=encounter,
            status="ACTIVE",
        )
    )
    finals = [diagnosis for diagnosis in active if diagnosis.diagnosis_type == "FINAL"]
    no_diagnosis = [diagnosis for diagnosis in active if diagnosis.diagnosis_type == "NO_DIAGNOSIS"]
    if no_diagnosis and finals:
        raise DiagnosisDomainError(
            "DIAGNOSIS_STATE_INVALID",
            "No diagnosis cannot coexist with an active final diagnosis.",
        )
    if no_diagnosis:
        if len(no_diagnosis) != 1 or not no_diagnosis[0].no_diagnosis_reason.strip():
            raise DiagnosisDomainError(
                "DIAGNOSIS_STATE_INVALID",
                "The no-diagnosis state is incomplete.",
            )
        return
    if not finals:
        raise DiagnosisDomainError(
            "DIAGNOSIS_REQUIRED",
            "A final diagnosis or a documented no-diagnosis reason is required before signing.",
        )
    primary = [diagnosis for diagnosis in finals if diagnosis.is_primary]
    if len(primary) == 0:
        raise DiagnosisDomainError(
            "PRIMARY_DIAGNOSIS_REQUIRED",
            "Exactly one primary final diagnosis is required before signing.",
        )
    if len(primary) != 1 or any(diagnosis.diagnosis_type != "FINAL" for diagnosis in primary):
        raise DiagnosisDomainError(
            "PRIMARY_DIAGNOSIS_INVALID",
            "Exactly one active final diagnosis must be primary before signing.",
        )
    if any(not diagnosis.label.strip() for diagnosis in finals):
        raise DiagnosisDomainError(
            "DIAGNOSIS_STATE_INVALID",
            "Every active final diagnosis must have a non-blank label.",
        )
