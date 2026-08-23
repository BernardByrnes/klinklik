import hashlib
import hmac
import json

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from audit.services import record_event
from clinical.models import Allergy, Encounter, PatientAllergyState
from patients.models import Patient


ALLERGY_STATUS_NOT_RECORDED = "NOT_RECORDED"
ALLERGY_STATUS_NKA = "NKA"
ALLERGY_STATUS_UNKNOWN = "UNKNOWN"
ALLERGY_STATUS_RECORDED = "RECORDED"
ALLERGY_STATUS_CHOICES = (
    ALLERGY_STATUS_NOT_RECORDED,
    ALLERGY_STATUS_NKA,
    ALLERGY_STATUS_UNKNOWN,
    ALLERGY_STATUS_RECORDED,
)


class AllergyDomainError(ValueError):
    code = "ALLERGY_MUTATION_INVALID"

    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)


class AllergyPatientNotFound(AllergyDomainError):
    code = "ALLERGY_PATIENT_NOT_FOUND"


class AllergyStateConflict(AllergyDomainError):
    code = "ALLERGY_STATE_REVISION_CONFLICT"

    def __init__(self, detail, snapshot):
        self.snapshot = snapshot
        super().__init__(detail)


class AllergyStatusRequired(AllergyDomainError):
    code = "ALLERGY_STATUS_REQUIRED"

    def __init__(self):
        super().__init__("Record NKA, UNKNOWN, or one or more active allergies before signing.")


class AllergyReviewRequired(AllergyDomainError):
    code = "ALLERGY_REVIEW_REQUIRED"

    def __init__(self):
        super().__init__("Review the current patient allergy state before signing.")


class AllergyReviewStale(AllergyDomainError):
    code = "ALLERGY_REVIEW_STALE"

    def __init__(self):
        super().__init__("The patient allergy state changed after this encounter was reviewed.")


def active_allergy_payload(allergy):
    return {
        "id": str(allergy.id),
        "substance": allergy.substance,
        "reaction": allergy.reaction,
        "severity": allergy.severity,
    }


def _state_query(*, organisation_id, facility_id, patient_id, lock=False):
    queryset = PatientAllergyState.objects
    if lock:
        queryset = queryset.select_for_update()
    return queryset.filter(
        organisation_id=organisation_id,
        facility_id=facility_id,
        patient_id=patient_id,
    ).first()


def _active_allergies(*, organisation_id, facility_id, patient_id, lock=False):
    queryset = Allergy.objects
    if lock:
        queryset = queryset.select_for_update()
    return list(
        queryset.filter(
            organisation_id=organisation_id,
            facility_id=facility_id,
            patient_id=patient_id,
            status="ACTIVE",
        ).order_by("recorded_at", "created_at", "id")
    )


def _snapshot(*, organisation_id, facility_id, patient_id, state=None, active=None):
    if state is None:
        state = _state_query(
            organisation_id=organisation_id,
            facility_id=facility_id,
            patient_id=patient_id,
        )
    if active is None:
        active = _active_allergies(
            organisation_id=organisation_id,
            facility_id=facility_id,
            patient_id=patient_id,
        )
    status = state.status if state is not None else ALLERGY_STATUS_NOT_RECORDED
    revision = state.revision if state is not None else 0
    return {
        "status": status,
        "revision": revision,
        "active_allergies": [active_allergy_payload(item) for item in active],
        "etag": patient_allergy_state_etag(
            organisation_id=organisation_id,
            facility_id=facility_id,
            patient_id=patient_id,
            state=state,
            active=active,
        ),
    }


def patient_allergy_state_etag(*, organisation_id, facility_id, patient_id, state=None, active=None):
    if state is None:
        state = _state_query(
            organisation_id=organisation_id,
            facility_id=facility_id,
            patient_id=patient_id,
        )
    if active is None:
        active = _active_allergies(
            organisation_id=organisation_id,
            facility_id=facility_id,
            patient_id=patient_id,
        )
    payload = {
        "scope": "patient-allergy-state-v1",
        "organisation": str(organisation_id),
        "facility": str(facility_id),
        "patient": str(patient_id),
        "status": state.status if state is not None else ALLERGY_STATUS_NOT_RECORDED,
        "revision": state.revision if state is not None else 0,
        "active_allergies": [
            {
                "id": str(item.id),
                "status": item.status,
                "updated_at": item.updated_at.isoformat(),
            }
            for item in active
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hmac.new(settings.SECRET_KEY.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return '"' + digest + '"'


def patient_allergy_snapshot(*, organisation, facility, patient):
    return _snapshot(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
    )


def _lock_patient(*, organisation, patient):
    locked = Patient.objects.select_for_update().filter(
        id=patient.id,
        organisation=organisation,
    ).first()
    if locked is None:
        raise AllergyPatientNotFound("Patient is not available in this organisation.")
    return locked


def _set_state(*, organisation, facility, patient, actor, status, state=None, revision=None):
    if state is None:
        state = PatientAllergyState.objects.create(
            organisation=organisation,
            facility=facility,
            patient=patient,
            status=status,
            revision=1 if revision is None else revision,
            updated_by=actor,
        )
        return state
    state.status = status
    state.revision = state.revision + 1 if revision is None else revision
    state.updated_by = actor
    state.save(update_fields=["status", "revision", "updated_by", "updated_at"])
    return state


def _require_expected_etag(*, expected_etag, snapshot):
    if expected_etag is not None and not hmac.compare_digest(expected_etag, snapshot["etag"]):
        raise AllergyStateConflict(
            "The patient allergy state changed elsewhere; reload it before retrying.",
            snapshot,
        )


@transaction.atomic
def add_allergy(*, organisation, facility, patient, actor, substance, reaction, severity, request=None):
    patient = _lock_patient(organisation=organisation, patient=patient)
    state = _state_query(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        lock=True,
    )
    now = timezone.now()
    allergy = Allergy.objects.create(
        organisation=organisation,
        facility=facility,
        patient=patient,
        substance=substance,
        reaction=reaction,
        severity=severity,
        status="ACTIVE",
        recorded_by=actor,
        recorded_at=now,
    )
    if state is None:
        state = _set_state(
            organisation=organisation,
            facility=facility,
            patient=patient,
            actor=actor,
            state=state,
            status=ALLERGY_STATUS_RECORDED,
            revision=1,
        )
    else:
        state = _set_state(
            organisation=organisation,
            facility=facility,
            patient=patient,
            actor=actor,
            state=state,
            status=ALLERGY_STATUS_RECORDED,
        )
    active = _active_allergies(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        lock=True,
    )
    snapshot = _snapshot(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        state=state,
        active=active,
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="Allergy",
        entity_id=allergy.id,
        after={
            "status": "ACTIVE",
            "changed_fields": ["status", "recorded_at"],
            "allergy_state_status": state.status,
            "allergy_state_revision": state.revision,
        },
    )
    return allergy, snapshot


@transaction.atomic
def set_allergy_status(*, organisation, facility, patient, actor, status, expected_etag, request=None):
    if status not in {ALLERGY_STATUS_NKA, ALLERGY_STATUS_UNKNOWN}:
        raise AllergyDomainError("Only NKA or UNKNOWN may be set explicitly.")
    patient = _lock_patient(organisation=organisation, patient=patient)
    state = _state_query(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        lock=True,
    )
    active = _active_allergies(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        lock=True,
    )
    current = _snapshot(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        state=state,
        active=active,
    )
    _require_expected_etag(expected_etag=expected_etag, snapshot=current)
    if active:
        raise AllergyDomainError("Mark active allergies entered in error before setting NKA or UNKNOWN.")
    previous_status = current["status"]
    if state is None:
        state = _set_state(
            organisation=organisation,
            facility=facility,
            patient=patient,
            actor=actor,
            state=state,
            status=status,
            revision=1,
        )
    else:
        state = _set_state(
            organisation=organisation,
            facility=facility,
            patient=patient,
            actor=actor,
            state=state,
            status=status,
        )
    snapshot = _snapshot(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        state=state,
        active=[],
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE" if previous_status == ALLERGY_STATUS_NOT_RECORDED and state.revision == 1 else "UPDATE",
        entity_type="PatientAllergyState",
        entity_id=state.id,
        before={"status": previous_status},
        after={
            "status": state.status,
            "changed_fields": ["status", "revision"],
            "revision": state.revision,
        },
    )
    return state, snapshot


@transaction.atomic
def enter_allergy_in_error(
    *, organisation, facility, patient, allergy, actor, reason, expected_etag, request=None
):
    patient = _lock_patient(organisation=organisation, patient=patient)
    locked_allergy = Allergy.objects.select_for_update().filter(
        id=allergy.id,
        organisation=organisation,
        facility=facility,
        patient=patient,
    ).first()
    if locked_allergy is None:
        raise AllergyDomainError("Allergy is not available in this facility.")
    if locked_allergy.status != "ACTIVE":
        raise AllergyDomainError("Only an active allergy can be entered in error.")
    state = _state_query(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        lock=True,
    )
    active_before = _active_allergies(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        lock=True,
    )
    current = _snapshot(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        state=state,
        active=active_before,
    )
    _require_expected_etag(expected_etag=expected_etag, snapshot=current)
    now = timezone.now()
    locked_allergy.status = "ENTERED_IN_ERROR"
    locked_allergy.entered_in_error_reason = reason
    locked_allergy.entered_in_error_by = actor
    locked_allergy.entered_in_error_at = now
    locked_allergy.save(
        update_fields=[
            "status",
            "entered_in_error_reason",
            "entered_in_error_by",
            "entered_in_error_at",
            "updated_at",
        ]
    )
    active_after = [item for item in active_before if item.id != locked_allergy.id]
    next_status = ALLERGY_STATUS_RECORDED if active_after else ALLERGY_STATUS_NOT_RECORDED
    if state is None:
        state = _set_state(
            organisation=organisation,
            facility=facility,
            patient=patient,
            actor=actor,
            state=state,
            status=next_status,
            revision=1,
        )
    else:
        state = _set_state(
            organisation=organisation,
            facility=facility,
            patient=patient,
            actor=actor,
            state=state,
            status=next_status,
        )
    snapshot = _snapshot(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        state=state,
        active=active_after,
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="Allergy",
        entity_id=locked_allergy.id,
        after={
            "status": "ENTERED_IN_ERROR",
            "changed_fields": [
                "status",
                "entered_in_error_reason",
                "entered_in_error_by",
                "entered_in_error_at",
            ],
            "reason_recorded": True,
            "allergy_state_status": state.status,
            "allergy_state_revision": state.revision,
        },
    )
    return locked_allergy, state, snapshot


@transaction.atomic
def review_encounter_allergies(*, organisation, facility, actor, encounter, expected_etag, request=None):
    locked_encounter = Encounter.objects.select_for_update().filter(
        id=encounter.id,
        organisation=organisation,
        facility=facility,
    ).select_related("patient").first()
    if locked_encounter is None:
        raise AllergyDomainError("Encounter is not available in this facility.")
    if locked_encounter.status != "OPEN":
        raise AllergyDomainError("A signed or closed encounter cannot be reviewed again.")
    patient = _lock_patient(organisation=organisation, patient=locked_encounter.patient)
    state = _state_query(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        lock=True,
    )
    active = _active_allergies(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        lock=True,
    )
    snapshot = _snapshot(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        state=state,
        active=active,
    )
    _require_expected_etag(expected_etag=expected_etag, snapshot=snapshot)
    if snapshot["status"] == ALLERGY_STATUS_NOT_RECORDED:
        raise AllergyStatusRequired()
    now = timezone.now()
    locked_encounter.allergies_reviewed_at = now
    locked_encounter.allergies_reviewed_by = actor
    locked_encounter.allergies_reviewed_revision = snapshot["revision"]
    locked_encounter.save(
        update_fields=[
            "allergies_reviewed_at",
            "allergies_reviewed_by",
            "allergies_reviewed_revision",
            "updated_at",
        ]
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="Encounter",
        entity_id=locked_encounter.id,
        after={
            "changed_fields": [
                "allergies_reviewed_at",
                "allergies_reviewed_by",
                "allergies_reviewed_revision",
            ],
            "allergy_revision": snapshot["revision"],
        },
    )
    return locked_encounter, snapshot


def require_current_allergy_review(*, organisation, facility, encounter):
    patient = _lock_patient(organisation=organisation, patient=encounter.patient)
    state = _state_query(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        lock=True,
    )
    active = _active_allergies(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        lock=True,
    )
    snapshot = _snapshot(
        organisation_id=organisation.id,
        facility_id=facility.id,
        patient_id=patient.id,
        state=state,
        active=active,
    )
    if snapshot["status"] == ALLERGY_STATUS_NOT_RECORDED:
        raise AllergyStatusRequired()
    if (
        encounter.allergies_reviewed_at is None
        or encounter.allergies_reviewed_by_id is None
    ):
        raise AllergyReviewRequired()
    if encounter.allergies_reviewed_revision != snapshot["revision"]:
        raise AllergyReviewStale()
    return snapshot
