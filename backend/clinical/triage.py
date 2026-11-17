"""SM-03/PC-008: the clinical owner service for versioned human triage.

The legacy ``TriageAssessment`` writer remains available for its admitted
callers. This module owns the canonical ``TriageRecord`` head, its immutable
versions, and the typed vitals/triage observations. It never computes or
suggests acuity, diagnosis, priority, treatment or interpretation.
"""

from decimal import Decimal, InvalidOperation
import hashlib

from django.utils import timezone

from audit.services import record_fact
from clinical.allergies import ALLERGY_STATUS_NOT_RECORDED, patient_allergy_snapshot
from clinical.complaints import ComplaintValidationError, normalize_complaints
from clinical.models import TriageRecord, TriageRecordVersion, VitalsObservation
from core.errors import CanonicalError
from core.idempotency import canonical_json
from core.services import assert_transaction_active
from scheduling.models import Visit

TRIAGE_CONTEXT = "TRIAGE"
REPEAT_CONTEXT = "REPEAT"
UNABLE_REASONS = ("EQUIPMENT_UNAVAILABLE", "PATIENT_DECLINED")
ACUITY_CHOICES = ("EMERGENCY", "URGENT", "ROUTINE")
MAX_COMPLAINTS = 5
MAX_MEDICATIONS = 10
MAX_MEDICATION_LENGTH = 200
MAX_CHRONIC_LENGTH = 100
MAX_ACUITY_REASON = 240

MEASUREMENT_FIELDS = (
    "systolic",
    "diastolic",
    "pulse",
    "temperature_c",
    "respiratory_rate",
    "oxygen_saturation",
    "weight_kg",
    "height_cm",
    "muac_cm",
)


class TriageDomainError(CanonicalError):
    pass


def _error(code, detail, *, status_code=422, metadata=None):
    return TriageDomainError(code, detail, status_code=status_code, metadata=metadata)


def _digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _as_decimal(value, *, field, places, minimum=None, maximum=None):
    if isinstance(value, bool):
        raise _error("INVALID_VITAL", f"{field} must be numeric.", status_code=400)
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise _error("INVALID_VITAL", f"{field} must be numeric.", status_code=400) from None
    if not result.is_finite():
        raise _error("INVALID_VITAL", f"{field} must be finite.", status_code=400)
    if minimum is not None and result < minimum:
        raise _error(
            "VITAL_OUT_OF_RANGE",
            f"{field} is outside the accepted range.",
            metadata={"field": field, "minimum": str(minimum), "maximum": str(maximum)},
        )
    if maximum is not None and result > maximum:
        raise _error(
            "VITAL_OUT_OF_RANGE",
            f"{field} is outside the accepted range.",
            metadata={"field": field, "minimum": str(minimum), "maximum": str(maximum)},
        )
    return result.quantize(Decimal(1).scaleb(-places))


def _as_positive_int(value, *, field, maximum=None):
    if isinstance(value, bool):
        raise _error("INVALID_VITAL", f"{field} must be a whole number.", status_code=400)
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        raise _error("INVALID_VITAL", f"{field} must be a whole number.", status_code=400) from None
    if result < 1 or (maximum is not None and result > maximum):
        raise _error(
            "VITAL_OUT_OF_RANGE",
            f"{field} is outside the accepted range.",
            metadata={"field": field, "minimum": 1, "maximum": maximum},
        )
    return result


def normalize_measurements(raw):
    """Return ``(measurements, unable_reasons)`` for a supplied observation.

    Only typed measurements or an explicit supplied unable-to-measure reason
    are accepted. Blanks are omissions, never zeros. Clinical range checks are
    limited to the supplied acceptance limits; no interpretation is added.
    """

    if not isinstance(raw, dict):
        raise _error("INVALID_OBSERVATION", "Observations must be an object.", status_code=400)
    unknown = set(raw) - {"measurements", "unable_reason_fields"} - set(MEASUREMENT_FIELDS)
    if unknown:
        raise _error(
            "INVALID_OBSERVATION",
            "The observation contains unsupported fields.",
            status_code=400,
            metadata={"fields": sorted(unknown)},
        )
    if "measurements" in raw or "unable_reason_fields" in raw:
        measurements_raw = raw.get("measurements") or {}
        unable_raw = raw.get("unable_reason_fields") or {}
    else:
        measurements_raw = raw
        unable_raw = {}
    if not isinstance(measurements_raw, dict) or not isinstance(unable_raw, dict):
        raise _error("INVALID_OBSERVATION", "Observation fields must be objects.", status_code=400)

    measurements = {}
    for field in MEASUREMENT_FIELDS:
        if field not in measurements_raw:
            continue
        value = measurements_raw.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        if field == "temperature_c":
            measurements[field] = _as_decimal(
                value, field=field, places=1, minimum=Decimal("30.0"), maximum=Decimal("45.0")
            )
        elif field in {"weight_kg", "height_cm", "muac_cm"}:
            measurements[field] = _as_decimal(
                value, field=field, places=2, minimum=Decimal("0.01")
            )
        elif field == "oxygen_saturation":
            measurements[field] = _as_positive_int(value, field=field, maximum=100)
        else:
            measurements[field] = _as_positive_int(value, field=field)

    unable = {}
    for field, reason in unable_raw.items():
        if field not in MEASUREMENT_FIELDS:
            raise _error(
                "INVALID_OBSERVATION",
                "An unable-to-measure reason names an unsupported field.",
                status_code=400,
                metadata={"field": str(field)},
            )
        if field in measurements:
            raise _error(
                "INVALID_OBSERVATION",
                f"{field} cannot be both measured and marked not done.",
                status_code=400,
                metadata={"field": field},
            )
        normalized = str(reason or "").strip().upper()
        if normalized not in UNABLE_REASONS:
            raise _error(
                "INVALID_OBSERVATION",
                "The unable-to-measure reason is not supported.",
                status_code=400,
                metadata={"field": field, "reasons": list(UNABLE_REASONS)},
            )
        unable[field] = normalized

    systolic = measurements.get("systolic")
    diastolic = measurements.get("diastolic")
    if (systolic is None) != (diastolic is None):
        raise _error(
            "BLOOD_PRESSURE_PAIR_REQUIRED",
            "Systolic and diastolic must be recorded together.",
            metadata={"fields": ["systolic", "diastolic"]},
        )
    if systolic is not None and diastolic >= systolic:
        raise _error(
            "DIASTOLIC_EXCEEDS_SYSTOLIC",
            "Diastolic must be lower than systolic.",
            metadata={"fields": ["systolic", "diastolic"]},
        )
    if (("systolic" in unable) != ("diastolic" in unable)):
        raise _error(
            "BLOOD_PRESSURE_PAIR_REQUIRED",
            "Systolic and diastolic must be marked not done together.",
            metadata={"fields": ["systolic", "diastolic"]},
        )
    if not measurements and not unable:
        raise _error(
            "OBSERVATION_REQUIRED",
            "Record at least one measurement or an explicit not-done reason.",
        )
    return measurements, unable


def normalize_complaint_input(payload, *, required=False):
    """Return normalized complaints, or ``None`` when the field was omitted."""

    if "presenting_complaints" in payload and payload.get("presenting_complaints") is not None:
        raw = payload.get("presenting_complaints")
    elif payload.get("chief_complaint") is not None:
        text = str(payload.get("chief_complaint") or "").strip()
        raw = [{"text": text}] if text else []
    else:
        return None
    try:
        complaints = normalize_complaints(raw)
    except ComplaintValidationError as exc:
        raise _error("INVALID_COMPLAINT", str(exc), status_code=400) from exc
    if len(complaints) > MAX_COMPLAINTS:
        raise _error(
            "COMPLAINT_LIMIT_EXCEEDED",
            f"At most {MAX_COMPLAINTS} complaints can be recorded at triage.",
            metadata={"maximum": MAX_COMPLAINTS},
        )
    if required and not complaints:
        raise _error(
            "COMPLAINT_REQUIRED",
            "A presenting complaint is required before completing triage.",
        )
    return complaints


def normalize_medication_input(payload):
    """Return the normalized medication/chronic context, or ``None``."""

    if "current_medications" not in payload:
        return None
    raw = payload.get("current_medications")
    if isinstance(raw, list):
        medications = raw
        chronic = []
    elif isinstance(raw, dict):
        unknown = set(raw) - {"medications", "chronic_conditions"}
        if unknown:
            raise _error(
                "INVALID_MEDICATIONS",
                "The medication context contains unsupported fields.",
                status_code=400,
                metadata={"fields": sorted(unknown)},
            )
        medications = raw.get("medications") or []
        chronic = raw.get("chronic_conditions") or []
    else:
        raise _error("INVALID_MEDICATIONS", "Medications must be a list or object.", status_code=400)
    if not isinstance(medications, list) or not isinstance(chronic, list):
        raise _error("INVALID_MEDICATIONS", "Medications must be lists.", status_code=400)
    if len(medications) > MAX_MEDICATIONS:
        raise _error(
            "MEDICATION_LIMIT_EXCEEDED",
            f"At most {MAX_MEDICATIONS} current medications can be recorded.",
            metadata={"maximum": MAX_MEDICATIONS},
        )
    normalized_medications = []
    for item in medications:
        text = str(item or "").strip()
        if not text:
            continue
        if len(text) > MAX_MEDICATION_LENGTH:
            raise _error("INVALID_MEDICATIONS", "A medication entry is too long.", status_code=400)
        normalized_medications.append(text)
    normalized_chronic = []
    for item in chronic:
        text = str(item or "").strip()
        if not text:
            continue
        if len(text) > MAX_CHRONIC_LENGTH:
            raise _error("INVALID_MEDICATIONS", "A chronic-condition entry is too long.", status_code=400)
        normalized_chronic.append(text)
    return {"medications": normalized_medications, "chronic_conditions": normalized_chronic}


def normalize_acuity(value):
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if normalized not in ACUITY_CHOICES:
        raise _error("INVALID_ACUITY", "The acuity is not supported.", status_code=400)
    return normalized


def normalize_acuity_reason(value):
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > MAX_ACUITY_REASON:
        raise _error("INVALID_ACUITY_REASON", "The acuity reason is too long.", status_code=400)
    return text


def _age_months(patient, *, as_of):
    birth_date = getattr(patient, "date_of_birth", None)
    if not birth_date:
        return None
    months = (as_of.year - birth_date.year) * 12 + as_of.month - birth_date.month
    if as_of.day < birth_date.day:
        months = max(0, months - 1)
    return max(0, months)


def _bmi(observation):
    if observation is None:
        return None
    weight = observation.weight_kg
    height = observation.height_cm
    if weight is None or height is None or Decimal(height) <= 0:
        return None
    metres = Decimal(height) / Decimal(100)
    value = Decimal(weight) / (metres * metres)
    return str(value.quantize(Decimal("0.1")))


def latest_observation(record):
    return (
        VitalsObservation.objects.filter(
            organisation_id=record.organisation_id,
            facility_id=record.facility_id,
            visit_id=record.visit_id,
            triage_record_id=record.id,
            context=TRIAGE_CONTEXT,
        )
        .order_by("-sequence", "-measured_at", "-id")
        .first()
    )


def observation_payload(observation):
    if observation is None:
        return None
    return {
        "id": str(observation.id),
        "sequence": observation.sequence,
        "context": observation.context,
        "systolic": observation.systolic,
        "diastolic": observation.diastolic,
        "pulse": observation.pulse,
        "temperature_c": str(observation.temperature_c) if observation.temperature_c is not None else None,
        "respiratory_rate": observation.respiratory_rate,
        "oxygen_saturation": observation.oxygen_saturation,
        "weight_kg": str(observation.weight_kg) if observation.weight_kg is not None else None,
        "height_cm": str(observation.height_cm) if observation.height_cm is not None else None,
        "muac_cm": str(observation.muac_cm) if observation.muac_cm is not None else None,
        "unable_reason_fields": observation.unable_reason_fields or {},
        "measured_by_id": str(observation.measured_by_id),
        "measured_at": observation.measured_at.isoformat(),
        "supersedes_id": str(observation.supersedes_id) if observation.supersedes_id else None,
    }


def snapshot(record, *, observation=None):
    observation = observation if observation is not None else latest_observation(record)
    return {
        "id": str(record.id),
        "visit_id": str(record.visit_id),
        "patient_id": str(record.patient_id),
        "state": record.state,
        "acuity": record.acuity,
        "presenting_complaints": record.presenting_complaints or [],
        "current_medications": record.current_medications or {
            "medications": [],
            "chronic_conditions": [],
        },
        "recorded_by_id": str(record.recorded_by_id),
        "completed_by_id": str(record.completed_by_id) if record.completed_by_id else None,
        "completed_at": record.completed_at,
        "current_version": record.current_version,
        "version": record.row_version,
        "observation": observation_payload(observation),
        "bmi": _bmi(observation),
    }


def assert_triage_source(*, queue, visit):
    if queue is None or visit is None:
        raise _error(
            "PREREQUISITE_MISSING",
            "Triage requires a linked Visit and queue entry.",
            status_code=422,
        )
    if str(queue.queue_type or "").upper() != "TRIAGE":
        raise _error("INVALID_STATE", "Only a TRIAGE queue entry can start triage.", status_code=409)
    if queue.visit_id != visit.id or queue.patient_id != visit.patient_id:
        raise _error(
            "PREREQUISITE_MISSING",
            "The triage queue entry does not match the Visit.",
            status_code=422,
        )
    if visit.state not in Visit.ACTIVE_STATES:
        raise _error("INVALID_STATE", "The Visit is no longer available for triage.", status_code=409)


def get_or_create_draft(*, organisation, facility, actor, visit):
    record = (
        TriageRecord.objects.select_for_update()
        .filter(organisation=organisation, facility=facility, visit=visit)
        .first()
    )
    if record is not None:
        return record, False
    record = TriageRecord.objects.create(
        organisation=organisation,
        facility=facility,
        visit=visit,
        patient_id=visit.patient_id,
        state="DRAFT",
        recorded_by=actor,
        row_version=1,
    )
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="TRIAGE_STARTED",
        action="CREATE",
        entity_type="TriageRecord",
        entity_id=record.id,
        source_ids={"visit_id": visit.id, "queue_entry_id": visit.queue_entries.order_by("id").values_list("id", flat=True).first()},
        after={"state": record.state, "row_version": record.row_version},
    )
    return record, True


def _record_observation(*, organisation, facility, actor, record, measurements, unable, previous):
    sequence = 1
    if previous is not None:
        sequence = int(previous.sequence or 0) + 1
    observation = VitalsObservation.objects.create(
        organisation=organisation,
        facility=facility,
        patient_id=record.patient_id,
        visit_id=record.visit_id,
        triage_record=record,
        context=TRIAGE_CONTEXT,
        sequence=sequence,
        measured_by=actor,
        unable_reason_fields=unable,
        supersedes=previous,
        **measurements,
    )
    return observation


def _changed_field_names(before, after):
    return sorted(
        field for field in set(before) | set(after) if before.get(field) != after.get(field)
    )


def save_draft(*, organisation, facility, actor, record, payload, expected_version):
    """CMD-026 owner operation: validate and persist draft facts."""

    assert_transaction_active()
    record = TriageRecord.objects.select_for_update().get(id=record.id)
    if record.state != "DRAFT":
        raise _error(
            "INVALID_STATE",
            "A completed triage record is read-only; use the amendment path.",
            status_code=409,
            metadata={"state": record.state},
        )
    if expected_version is not None and record.row_version != expected_version:
        raise _error(
            "VERSION_CONFLICT",
            "The triage record changed; reload it before saving.",
            status_code=412,
            metadata={"current_version": record.row_version},
        )

    complaints = normalize_complaint_input(payload)
    medications = normalize_medication_input(payload)
    acuity = normalize_acuity(payload.get("acuity")) if "acuity" in payload else record.acuity
    acuity_reason = (
        normalize_acuity_reason(payload.get("acuity_reason"))
        if "acuity_reason" in payload
        else ""
    )
    previous = latest_observation(record)
    observation_input = payload.get("observation")
    if observation_input is None:
        observation_input = payload.get("vitals")
    if isinstance(observation_input, dict) and not observation_input:
        observation_input = None
    measurements = unable = None
    if observation_input is not None:
        measurements, unable = normalize_measurements(observation_input)

    if measurements is not None:
        previous_values = {}
        if previous is not None:
            previous_values = {
                field: getattr(previous, field)
                for field in MEASUREMENT_FIELDS
            }
        if previous_values != measurements or (previous.unable_reason_fields or {}) != unable:
            _record_observation(
                organisation=organisation,
                facility=facility,
                actor=actor,
                record=record,
                measurements=measurements,
                unable=unable,
                previous=previous,
            )

    age_months = _age_months(record.patient, as_of=timezone.localdate())
    under_five = age_months is not None and age_months < 60
    effective = measurements if measurements is not None else (
        {
            field: getattr(previous, field)
            for field in MEASUREMENT_FIELDS
        }
        if previous is not None
        else {}
    )
    effective_unable = unable if unable is not None else (
        (previous.unable_reason_fields or {}) if previous is not None else {}
    )
    if not any(effective.get(field) is not None for field in MEASUREMENT_FIELDS) and not effective_unable:
        raise _error(
            "OBSERVATION_REQUIRED",
            "Record at least one measurement or an explicit not-done reason.",
        )
    if under_five and effective.get("weight_kg") is None and "weight_kg" not in effective_unable:
        raise _error(
            "WEIGHT_REQUIRED_UNDER_5",
            "Weight (or an explicit not-done reason) is required for a child under 5.",
        )

    before = {
        "acuity": record.acuity,
        "presenting_complaints": record.presenting_complaints,
        "current_medications": record.current_medications,
        "row_version": record.row_version,
    }
    if complaints is not None:
        record.presenting_complaints = complaints
    if medications is not None:
        record.current_medications = medications
    if "acuity" in payload:
        record.acuity = acuity
    record.row_version += 1
    record.save(
        update_fields=[
            "presenting_complaints",
            "current_medications",
            "acuity",
            "row_version",
            "updated_at",
        ]
    )
    after = {
        "acuity": record.acuity,
        "presenting_complaints": record.presenting_complaints,
        "current_medications": record.current_medications,
        "row_version": record.row_version,
    }
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="TRIAGE_DRAFT_SAVED",
        action="UPDATE",
        entity_type="TriageRecord",
        entity_id=record.id,
        source_ids={"visit_id": record.visit_id, "triage_record_id": record.id},
        before={"row_version": before["row_version"]},
        after={
            "row_version": record.row_version,
            "changed_fields": _changed_field_names(before, after),
            "acuity_reason_present": bool(acuity_reason),
        },
    )
    return record


def _default_content(record, observation, *, actor_id, completed_at, acuity_reason):
    return {
        "state": "COMPLETED",
        "acuity": record.acuity,
        "acuity_reason": acuity_reason,
        "presenting_complaints": record.presenting_complaints or [],
        "current_medications": record.current_medications
        or {"medications": [], "chronic_conditions": []},
        "observations": [observation_payload(observation)] if observation else [],
        "bmi": _bmi(observation),
        "recorded_by_id": str(record.recorded_by_id),
        "completed_by_id": str(actor_id),
        "completed_at": completed_at.isoformat(),
    }


def complete_triage(*, organisation, facility, actor, record, payload, expected_version):
    """CMD-027 owner operation: append version 1 and complete the head."""

    assert_transaction_active()
    record = TriageRecord.objects.select_for_update().get(id=record.id)
    if record.state != "DRAFT":
        raise _error(
            "INVALID_STATE",
            "This triage record is already completed.",
            status_code=409,
            metadata={"state": record.state},
        )
    if expected_version is None:
        raise _error(
            "PRECONDITION_REQUIRED",
            "A current triage record version is required.",
            status_code=428,
        )
    if record.row_version != expected_version:
        raise _error(
            "VERSION_CONFLICT",
            "The triage record changed; reload it before completing.",
            status_code=412,
            metadata={"current_version": record.row_version},
        )
    complaints = normalize_complaint_input(payload, required=False)
    if complaints is None:
        complaints = list(record.presenting_complaints or [])
    if not complaints:
        raise _error(
            "COMPLAINT_REQUIRED",
            "A presenting complaint is required before completing triage.",
        )
    acuity = normalize_acuity(payload.get("acuity"))
    if acuity is None:
        raise _error("ACUITY_REQUIRED", "Select an acuity before completing triage.")
    previous_acuity = record.acuity
    acuity_reason = normalize_acuity_reason(payload.get("acuity_reason"))
    if previous_acuity == "EMERGENCY" and acuity != "EMERGENCY" and not acuity_reason:
        raise _error(
            "ACUITY_REASON_REQUIRED",
            "A reason is required when lowering an emergency acuity.",
        )
    observation = latest_observation(record)
    if observation is None or (
        not any(getattr(observation, field) is not None for field in MEASUREMENT_FIELDS)
        and not (observation.unable_reason_fields or {})
    ):
        raise _error(
            "OBSERVATION_REQUIRED",
            "Record at least one observation or an explicit not-done reason.",
        )
    under_five = _age_months(record.patient, as_of=timezone.localdate()) is not None and (
        _age_months(record.patient, as_of=timezone.localdate()) < 60
    )
    if under_five and observation.weight_kg is None and "weight_kg" not in (
        observation.unable_reason_fields or {}
    ):
        raise _error(
            "WEIGHT_REQUIRED_UNDER_5",
            "Weight (or an explicit not-done reason) is required for a child under 5.",
        )
    allergy_snapshot = patient_allergy_snapshot(
        organisation=organisation, facility=facility, patient=record.patient
    )
    if allergy_snapshot.get("status") == ALLERGY_STATUS_NOT_RECORDED:
        raise _error(
            "ALLERGY_STATUS_REQUIRED",
            "Record NKA, UNKNOWN, or one or more active allergies before completing triage.",
        )

    record.presenting_complaints = complaints
    record.acuity = acuity
    completed_at = timezone.now()
    content = _default_content(
        record,
        observation,
        actor_id=actor.id,
        completed_at=completed_at,
        acuity_reason=acuity_reason,
    )
    content_hash = _digest(content)
    version = TriageRecordVersion.objects.create(
        organisation=organisation,
        record=record,
        version_number=1,
        content=content,
        content_hash=content_hash,
        reason="",
        created_by=actor,
    )
    record.state = "COMPLETED"
    record.completed_by = actor
    record.completed_at = completed_at
    record.current_version = 1
    record.row_version += 1
    record.save(
        update_fields=[
            "state",
            "presenting_complaints",
            "acuity",
            "completed_by",
            "completed_at",
            "current_version",
            "row_version",
            "updated_at",
        ]
    )
    if observation is not None:
        record_fact(
            organisation=organisation,
            actor=actor,
            facility=facility,
            event_code="TRIAGE_VITALS_RECORDED",
            action="UPDATE",
            entity_type="TriageRecord",
            entity_id=record.id,
            source_ids={"visit_id": record.visit_id, "observation_id": observation.id},
            after={
                "version": record.current_version,
                "version_id": str(version.id),
                "content_hash": content_hash,
                "observation_id": str(observation.id),
                "changed_fields": [
                    field
                    for field in MEASUREMENT_FIELDS
                    if getattr(observation, field) is not None
                ]
                + (["unable_reason_fields"] if observation.unable_reason_fields else []),
            },
        )
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="TRIAGE_COMPLAINT_RECORDED",
        action="UPDATE",
        entity_type="TriageRecord",
        entity_id=record.id,
        source_ids={"visit_id": record.visit_id, "version_id": version.id},
        after={"version": record.current_version, "complaint_count": len(complaints)},
    )
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code=(
            "TRIAGE_ACUITY_DOWNGRADED"
            if previous_acuity == "EMERGENCY" and acuity != "EMERGENCY"
            else "TRIAGE_ACUITY_ASSIGNED"
        ),
        action="UPDATE",
        entity_type="TriageRecord",
        entity_id=record.id,
        source_ids={"visit_id": record.visit_id, "version_id": version.id},
        after={
            "acuity": acuity,
            "previous_acuity": previous_acuity,
            "reason_present": bool(acuity_reason),
        },
        reason_code=(
            "ACUITY_DOWNGRADED"
            if previous_acuity == "EMERGENCY" and acuity != "EMERGENCY"
            else ""
        ),
    )
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="TRIAGE_COMPLETED",
        action="UPDATE",
        entity_type="TriageRecord",
        entity_id=record.id,
        source_ids={"visit_id": record.visit_id, "version_id": version.id},
        after={
            "state": record.state,
            "current_version": record.current_version,
            "version_id": str(version.id),
            "content_hash": content_hash,
            "acuity": acuity,
        },
    )
    return record, version, observation


def completed_summary(*, organisation, facility, visit_id):
    """Return the current scoped completed triage summary for a Visit."""

    record = (
        TriageRecord.objects.filter(
            organisation=organisation,
            facility=facility,
            visit_id=visit_id,
            state="COMPLETED",
        )
        .select_related("recorded_by", "completed_by")
        .order_by("-completed_at", "-id")
        .first()
    )
    if record is None:
        return None
    version = (
        TriageRecordVersion.objects.filter(record=record, version_number=record.current_version)
        .order_by("-version_number", "-created_at")
        .first()
    )
    return {
        "record_id": str(record.id),
        "visit_id": str(record.visit_id),
        "state": record.state,
        "current_version": record.current_version,
        "version": record.row_version,
        "acuity": record.acuity,
        "acuity_reason": (version.content or {}).get("acuity_reason", "") if version else "",
        "presenting_complaints": record.presenting_complaints or [],
        "current_medications": record.current_medications or {},
        "observation": observation_payload(latest_observation(record)),
        "bmi": _bmi(latest_observation(record)),
        "recorded_by_id": str(record.recorded_by_id),
        "recorded_by_name": record.recorded_by.get_full_name() or record.recorded_by.username,
        "completed_by_id": str(record.completed_by_id) if record.completed_by_id else None,
        "completed_by_name": (
            record.completed_by.get_full_name() or record.completed_by.username
            if record.completed_by_id
            else None
        ),
        "completed_at": record.completed_at,
        "content_hash": version.content_hash if version else "",
        "version_content": version.content if version else {},
    }
