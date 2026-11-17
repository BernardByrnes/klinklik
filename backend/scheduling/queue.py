"""Canonical QueueEntry transition services.

This module is deliberately transaction-neutral.  Application commands and
``TenantAPIView`` provide the outer tenant transaction; these functions own
QueueEntry state, locking, and safe audit facts only.
"""

from dataclasses import dataclass
from datetime import date, timedelta
import math

from django.db import IntegrityError, models, transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from accounts.models import User, UserFacilityRole
from audit.services import record_fact
from core.clock import now
from core.errors import CanonicalError
from core.permissions import UNRESTRICTED_SCOPE, scope_allows, scope_query
from core.services import allocate_sequence, assert_transaction_active
from clinical.models import Encounter, EncounterCoAuthor, TriageAssessment, VitalsObservation
from billing.models import Invoice, Payment, PaymentAllocation
from billing.services import void_unpaid_visit_invoice
from scheduling.models import QueueEntry, Visit
from tenancy.models import Department, FacilityWorkflowPolicy


PRIORITY_ORDER = {"EMERGENCY": 0, "URGENT": 1, "ROUTINE": 2}
PRIORITIES = frozenset(PRIORITY_ORDER)
ACTIVE_STATES = QueueEntry.ACTIVE_STATES
TERMINAL_STATES = QueueEntry.TERMINAL_STATES
NO_RESPONSE_OUTCOMES = frozenset({"REQUEUE", "NO_SHOW"})
HOLD_REASONS = frozenset({"AWAITING_RESULTS", "AWAITING_PAYMENT", "AWAITING_PROCEDURE"})
REMOVAL_REASONS = frozenset(
    {
        "LEFT_WITHOUT_BEING_SEEN",
        "WRONG_QUEUE",
        "DUPLICATE",
        "SENT_HOME",
        "SENT_ELSEWHERE",
        "ROUTED_IN_ERROR",
        "OTHER",
    }
)
LWBS_REASONS = frozenset(value for value, _ in QueueEntry.LWBS_REASON_CHOICES)


class QueueDomainError(CanonicalError, ValueError):
    """Expected queue failure usable by both service and API callers."""


class QueueStageRefusal(QueueDomainError):
    """A parent command may handle this after the CALLED transition commits."""

    def __init__(self, detail="The stage workspace could not be opened."):
        super().__init__("PREREQUISITE_MISSING", detail, status_code=422)


@dataclass(frozen=True)
class QueueSweepResult:
    expired_entry_ids: tuple = ()
    exceptions: tuple = ()
    closed_visit_ids: tuple = ()
    review_visit_ids: tuple = ()

    @property
    def expired_count(self):
        return len(self.expired_entry_ids)

    def as_dict(self):
        return {
            "expired_entry_ids": [str(value) for value in self.expired_entry_ids],
            "exceptions": [str(value) for value in self.exceptions],
            "closed_visit_ids": [str(value) for value in self.closed_visit_ids],
            "review_visit_ids": [str(value) for value in self.review_visit_ids],
            "expired_count": self.expired_count,
            "exception_count": len(self.exceptions),
        }


def _error(code, detail, *, status_code=409, metadata=None):
    return QueueDomainError(code, detail, status_code=status_code, metadata=metadata)


def _reason_hash(reason):
    import hashlib

    return hashlib.sha256(str(reason or "").strip().encode("utf-8")).hexdigest()


def _lwbs_notes(entry, reason_text):
    """Retain the supplied OTHER explanation without putting it in audit data."""

    reason_text = str(reason_text or "").strip()
    if not reason_text:
        return entry.notes
    return f"{entry.notes}\nLWBS_OTHER: {reason_text}".strip()


def _identifier(value):
    return str(getattr(value, "id", value)) if value is not None else None


def _actor_id(actor):
    return getattr(actor, "id", actor) if actor is not None else None


def _require_transaction():
    assert_transaction_active()


def _require_target_write(organisation):
    """Honor the durable MIG-002 writer fence before any queue mutation."""

    from core.migration_reconciliation import target_writes_enabled_mig002

    if not target_writes_enabled_mig002(organisation):
        raise QueueDomainError(
            "MIGRATION_TARGET_DISABLED",
            "Canonical QueueEntry writes are temporarily unavailable while migration compatibility is restored.",
            status_code=503,
            retryable=True,
        )


def _facility_id(facility):
    return getattr(facility, "id", facility)


def _organisation_id(organisation):
    return getattr(organisation, "id", organisation)


def _lock_entry(*, organisation, facility=None, queue_entry_id=None, entry_id=None):
    _require_transaction()
    identifier = queue_entry_id or entry_id
    if identifier is None:
        raise _error("QUEUE_ENTRY_REQUIRED", "A queue entry is required.", status_code=400)
    # Lock only the QueueEntry row. The Visit link is nullable, so a plain
    # FOR UPDATE over this join is rejected by PostgreSQL ("nullable side of an
    # outer join") and would also take incidental locks on Department/Patient.
    queryset = QueueEntry.objects.select_for_update(of=("self",)).filter(
        organisation_id=_organisation_id(organisation),
        id=identifier,
    )
    if facility is not None:
        queryset = queryset.filter(facility_id=_facility_id(facility))
    entry = queryset.select_related("visit", "department", "patient").first()
    if entry is None:
        raise _error("NOT_FOUND", "The queue entry was not found in this facility.", status_code=404)
    return entry


def _require_linked_visit(entry):
    """Require the S-01 Visit identity before a canonical mutation."""

    visit = getattr(entry, "visit", None)
    if not entry.visit_id or visit is None:
        raise _error(
            "PREREQUISITE_MISSING",
            "The canonical queue entry requires a linked Visit.",
            status_code=422,
        )
    if (
        visit.organisation_id != entry.organisation_id
        or visit.facility_id != entry.facility_id
        or visit.patient_id != entry.patient_id
    ):
        raise _error(
            "PREREQUISITE_MISSING",
            "The queue entry Visit does not match its tenant and facility scope.",
            status_code=422,
        )
    return visit


def _lock_entry_after_visit(*, organisation, facility, queue_entry_id):
    """Acquire Visit then QueueEntry according to LOCK-01."""

    identity = QueueEntry.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
        id=queue_entry_id,
    ).values("visit_id").first()
    if identity is None:
        raise _error("NOT_FOUND", "The queue entry was not found in this facility.", status_code=404)
    if not identity["visit_id"]:
        raise _error(
            "PREREQUISITE_MISSING",
            "The canonical queue entry requires a linked Visit.",
            status_code=422,
        )
    visit = Visit.objects.select_for_update().filter(
        id=identity["visit_id"],
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
    ).first()
    if visit is None:
        raise _error("NOT_FOUND", "The queue entry Visit is not available in this facility.", status_code=404)
    entry = _lock_entry(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id,
    )
    linked_visit = _require_linked_visit(entry)
    if linked_visit.id != visit.id:
        raise _error(
            "PREREQUISITE_MISSING",
            "The queue entry Visit changed while the command was acquiring its lock.",
            status_code=422,
        )
    return visit, entry


def _lock_lwbs_context(*, organisation, facility, queue_entry_id):
    """Lock the REC-009 aggregate in Visit -> QueueEntry order."""

    identity = QueueEntry.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
        id=queue_entry_id,
    ).values("visit_id").first()
    if identity is None:
        raise _error("NOT_FOUND", "The queue entry was not found in this facility.", status_code=404)
    if not identity["visit_id"]:
        raise _error("PREREQUISITE_MISSING", "LWBS requires a linked Visit.", status_code=422)
    visit = Visit.objects.select_for_update().filter(
        id=identity["visit_id"],
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
    ).first()
    if visit is None:
        raise _error("NOT_FOUND", "The queue entry Visit is not available in this facility.", status_code=404)
    entries = list(
        QueueEntry.objects.select_for_update().filter(
            organisation_id=_organisation_id(organisation),
            facility_id=_facility_id(facility),
            visit_id=visit.id,
        ).select_related("department", "patient").order_by("id")
    )
    entry = next(
        (candidate for candidate in entries if str(candidate.id) == str(queue_entry_id)),
        None,
    )
    if entry is None:
        raise _error("NOT_FOUND", "The queue entry was not found in this facility.", status_code=404)
    return visit, entry, entries


def _lock_department(*, organisation, facility, department=None, department_id=None, required=False):
    identifier = department_id or _identifier(department)
    queryset = Department.objects.select_for_update().filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
    )
    if identifier:
        queryset = queryset.filter(id=identifier)
    elif required:
        raise _error("DEPARTMENT_REQUIRED", "A destination department is required.", status_code=400)
    result = queryset.filter(is_active=True).order_by("code", "id").first()
    if result is None and (identifier or required):
        raise _error("OUT_OF_SCOPE", "The department is not available in this facility.", status_code=404)
    return result


def _assert_active_visit(visit):
    if visit is not None and visit.state not in Visit.ACTIVE_STATES:
        raise _error("INVALID_STATE", "The Visit is no longer available for queue work.")


def _version_guard(entry, expected_version):
    if expected_version is not None and entry.version != expected_version:
        raise _error(
            "VERSION_CONFLICT",
            "The queue entry changed; refresh before retrying.",
            status_code=412,
            metadata={"current_version": entry.version},
        )


def _state_guard(entry, allowed, *, detail="The queue entry is not in a valid state for this action."):
    if entry.state not in allowed:
        raise _error("INVALID_STATE", detail, metadata={"state": entry.state})


def _safe_transition_event(
    *,
    organisation,
    facility,
    actor,
    event_code,
    entry,
    before,
    after,
    reason_code="",
    source_ids=None,
):
    return record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code=event_code,
        action="UPDATE",
        entity_type="QueueEntry",
        entity_id=entry.id,
        source_ids={
            "queue_entry_id": entry.id,
            **(source_ids or {}),
        },
        before=before,
        after=after,
        reason_code=reason_code,
    )


def _state_snapshot(entry):
    return {
        "state": entry.state,
        "version": entry.version,
        "called_by_id": str(entry.called_by_id) if entry.called_by_id else None,
        "served_by_id": str(entry.served_by_id) if entry.served_by_id else None,
        "assigned_user_id": str(entry.assigned_user_id) if entry.assigned_user_id else None,
    }


def _legacy_status_for_state(entry, state):
    """Dual-write the legacy status without putting workflow inference in save()."""

    if state != "IN_SERVICE":
        return state
    if entry.status in {"IN_TRIAGE", "IN_CONSULTATION"}:
        return entry.status
    if str(entry.current_stage or "").upper() == "TRIAGE" or entry.queue_type.upper() == "TRIAGE":
        return "IN_TRIAGE"
    return "IN_CONSULTATION"


def _persist(entry, *, state=None, actor_fields=None, extra_fields=None, increment=True):
    actor_fields = actor_fields or {}
    extra_fields = extra_fields or {}
    before = _state_snapshot(entry)
    if state is not None:
        entry.state = state
        entry.status = _legacy_status_for_state(entry, state)
    for field, value in {**actor_fields, **extra_fields}.items():
        setattr(entry, field, value)
    if increment:
        entry.version += 1
    entry.last_activity_at = now()
    fields = {"state", "status", "version", "last_activity_at"}
    fields.update(actor_fields)
    fields.update(extra_fields)
    entry.save(update_fields=fields | {"updated_at"})
    return before


def _priority_ordering(queryset):
    return queryset.annotate(
        _priority_rank=Case(
            When(priority="EMERGENCY", then=Value(0)),
            When(priority="URGENT", then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
    ).order_by("_priority_rank", "queue_time", "id")


def _candidate_queryset(*, organisation, facility, department=None, department_id=None, queue_type=None):
    queryset = QueueEntry.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
        visit_id__isnull=False,
        state="WAITING",
    )
    department_identifier = department_id or _identifier(department)
    if department_identifier:
        queryset = queryset.filter(department_id=department_identifier)
    if queue_type:
        queryset = queryset.filter(queue_type=str(queue_type).upper())
    return _priority_ordering(queryset)


def _called_error(entry):
    caller = str(entry.called_by_id or entry.claimed_by_id) if (entry.called_by_id or entry.claimed_by_id) else None
    code = "ALREADY_CALLED" if entry.state == "CALLED" else "ENTRY_LOCKED"
    return _error(
        code,
        "This queue entry has already been called by another user.",
        metadata={"called_by_id": caller} if caller else None,
    )


def _call_locked(
    *,
    organisation,
    facility,
    actor,
    entry,
    out_of_order=False,
    skipped_count=0,
    out_of_order_reason="",
):
    if entry.state != "WAITING":
        if entry.state == "CALLED":
            raise _called_error(entry)
        raise _error("INVALID_STATE", "Only a waiting queue entry can be called.", metadata={"state": entry.state})
    called_at = now()
    before = _persist(
        entry,
        state="CALLED",
        actor_fields={
            "called_by": actor,
            "claimed_by": actor,
            "called_at": called_at,
            "claimed_at": called_at,
        },
    )
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_CALLED",
        entry=entry,
        before=before,
        after={"state": entry.state, "version": entry.version, "called_by_id": str(actor.id)},
    )
    if out_of_order:
        record_fact(
            organisation=organisation,
            actor=actor,
            facility=facility,
            event_code="QUEUE_CALLED_OUT_OF_ORDER",
            action="UPDATE",
            entity_type="QueueEntry",
            entity_id=entry.id,
            source_ids={"queue_entry_id": entry.id},
            after={
                "skipped_count": skipped_count,
                "reason_present": bool(str(out_of_order_reason or "").strip()),
            },
            reason_code="OUT_OF_ORDER",
        )
    return entry


def call_next_or_exact(
    *,
    organisation,
    facility,
    actor,
    queue_entry_id=None,
    entry_id=None,
    exact_queue_entry_id=None,
    department=None,
    department_id=None,
    queue_type=None,
    expected_version=None,
    ordering_watermark=None,
    out_of_order_reason="",
    reason="",
    allowed_scopes=None,
):
    """Call exactly one entry, or the first conditionally locked candidate.

    ``allowed_scopes`` is the actor's resolved ``(department, work type)``
    grant. The API resolves it from the authenticated actor so an omitted
    request filter cannot reach another department's work; ``None`` is reserved
    for internal callers that already own the scope.
    """

    _require_transaction()
    _require_target_write(organisation)
    exact_id = exact_queue_entry_id or queue_entry_id or entry_id
    if exact_id is not None:
        entry = _lock_entry(organisation=organisation, facility=facility, queue_entry_id=exact_id)
        _require_linked_visit(entry)
        if allowed_scopes is not None and not scope_allows(
            allowed_scopes, entry.department_id, entry.queue_type
        ):
            raise _error(
                "OUT_OF_SCOPE",
                "The queue entry is outside your granted queue scope.",
                status_code=404,
            )
        # A row another caller already called answers as ALREADY_CALLED even
        # when the loser still holds the version it observed before the race;
        # 412 stays reserved for a stale version on actionable work.
        if entry.state == "CALLED":
            raise _called_error(entry)
        _version_guard(entry, expected_version)
        if department_id and str(entry.department_id) != str(department_id):
            raise _error("OUT_OF_SCOPE", "The queue entry is outside the requested department.", status_code=404)
        if queue_type and entry.queue_type != str(queue_type).upper():
            raise _error("OUT_OF_SCOPE", "The queue entry is outside the requested queue type.", status_code=404)
        # Once the source row is known, its persisted scope is authoritative
        # for ordering and mutation.  Caller-provided filters may narrow or
        # validate it, but cannot broaden/relabel the candidate set.
        source_department_id = entry.department_id
        source_queue_type = entry.queue_type
        candidates = _candidate_queryset(
            organisation=organisation,
            facility=facility,
            department_id=source_department_id,
            queue_type=source_queue_type,
        )
        ordered_ids = list(candidates.values_list("id", flat=True))
        try:
            skipped_count = ordered_ids.index(entry.id)
        except ValueError:
            skipped_count = 0
        return _call_locked(
            organisation=organisation,
            facility=facility,
            actor=actor,
            entry=entry,
            out_of_order=bool(skipped_count),
            skipped_count=skipped_count,
            out_of_order_reason=out_of_order_reason or reason,
        )

    # The candidate query is intentionally ordered and conditionally locked.
    # PostgreSQL skip_locked lets competing callers advance to distinct rows.
    candidates = _candidate_queryset(
        organisation=organisation,
        facility=facility,
        department=department,
        department_id=department_id,
        queue_type=queue_type,
    )
    if allowed_scopes is not None:
        # Intersect the actor's grants before ordering and locking, so the
        # first candidate is always one the caller may actually call. An empty
        # grant set matches no row; a facility-wide wildcard adds no condition.
        predicate = scope_query(allowed_scopes)
        if predicate is not UNRESTRICTED_SCOPE:
            candidates = candidates.filter(predicate)
    if ordering_watermark is not None:
        candidates = candidates.filter(queue_time__lte=ordering_watermark)
    try:
        entry = candidates.select_for_update(skip_locked=True).first()
    except TypeError:  # pragma: no cover - compatibility with older Django
        entry = candidates.select_for_update().first()
    if entry is None:
        return None
    return _call_locked(
        organisation=organisation,
        facility=facility,
        actor=actor,
        entry=entry,
    )


def _assert_global_in_service(*, organisation, visit, facility=None, entry_id=None):
    if visit is None:
        return
    other = QueueEntry.objects.filter(
        organisation_id=visit.organisation_id,
        facility_id=_facility_id(facility) if facility is not None else visit.facility_id,
        visit_id=visit.id,
        state="IN_SERVICE",
    ).exclude(id=entry_id).order_by("id").first()
    if other is not None:
        raise _error(
            "INVALID_STATE",
            "Another queue stage for this Visit is already in service.",
            metadata={"active_queue_entry_id": str(other.id)},
        )


def start_service(
    *,
    organisation,
    facility,
    actor,
    queue_entry_id=None,
    entry_id=None,
    expected_version=None,
    stage_callback=None,
    stage_record_callback=None,
):
    """Start a called entry, with a safe direct WAITING convenience path.

    A ``QueueStageRefusal`` from the optional parent callback is returned as a
    committed CALLED outcome.  Unexpected exceptions propagate and roll back
    the caller's outer transaction.
    """

    _require_transaction()
    _require_target_write(organisation)
    identifier = queue_entry_id or entry_id
    visit, entry = _lock_entry_after_visit(
        organisation=organisation,
        facility=facility,
        queue_entry_id=identifier,
    )
    _version_guard(entry, expected_version)
    _assert_active_visit(visit)
    callback = stage_callback or stage_record_callback
    if entry.state == "IN_SERVICE":
        if callback is not None:
            try:
                with transaction.atomic():
                    callback(entry=entry, visit=visit)
            except QueueStageRefusal:
                return QueueEntry.objects.get(id=entry.id)
            entry.refresh_from_db()
        return entry
    _state_guard(entry, {"WAITING", "CALLED"}, detail="Only a waiting or called entry can start service.")
    direct = entry.state == "WAITING"
    transition_time = now() if direct else None
    if direct:
        before = _persist(
            entry,
            state="CALLED",
            actor_fields={
                "called_by": actor,
                "claimed_by": actor,
                "called_at": transition_time,
                "claimed_at": transition_time,
            },
        )
        _safe_transition_event(
            organisation=organisation,
            facility=facility,
            actor=actor,
            event_code="QUEUE_CALLED",
            entry=entry,
            before=before,
            after={"state": "CALLED", "version": entry.version, "called_by_id": str(actor.id)},
        )
    if callback is not None:
        try:
            # A caught stage refusal must roll back every partial child write
            # while retaining the already-committed CALLED transition.
            with transaction.atomic():
                callback(entry=entry, visit=visit)
        except QueueStageRefusal:
            return QueueEntry.objects.get(id=entry.id)
    entry.refresh_from_db()
    _assert_global_in_service(
        organisation=organisation,
        visit=visit,
        facility=facility,
        entry_id=entry.id,
    )
    started_at = transition_time or now()
    wait_seconds = max(0, math.floor((started_at - entry.queue_time).total_seconds())) if entry.queue_time else 0
    before = _persist(
        entry,
        state="IN_SERVICE",
        actor_fields={"served_by": actor},
        extra_fields={
            "started_at": started_at,
            "service_started_at": started_at,
            "wait_seconds": wait_seconds,
            "current_stage": entry.current_stage or entry.source_stage or "SERVICE",
        },
    )
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_SERVICE_STARTED",
        entry=entry,
        before=before,
        after={
            "state": entry.state,
            "version": entry.version,
            "served_by_id": str(actor.id),
            "wait_seconds": entry.wait_seconds,
        },
    )
    if visit is not None and visit.state == "OPEN":
        visit.state = "IN_PROGRESS"
        visit.in_progress_at = started_at
        visit.version += 1
        visit.save(update_fields=["state", "in_progress_at", "version", "updated_at"])
        record_fact(
            organisation=organisation,
            actor=actor,
            facility=facility,
            event_code="VISIT_IN_PROGRESS",
            action="UPDATE",
            entity_type="Visit",
            entity_id=visit.id,
            source_ids={"visit_id": visit.id, "queue_entry_id": entry.id},
            after={"state": visit.state, "version": visit.version},
        )
    return entry


def complete(
    *,
    organisation,
    facility,
    actor,
    queue_entry_id=None,
    entry_id=None,
    expected_version=None,
    terminal_reason=None,
    allow_held=False,
):
    """Complete an in-service stage; parent commands may hand off afterward."""

    _require_transaction()
    _require_target_write(organisation)
    identifier = queue_entry_id or entry_id
    visit, entry = _lock_entry_after_visit(
        organisation=organisation,
        facility=facility,
        queue_entry_id=identifier,
    )
    _version_guard(entry, expected_version)
    _assert_active_visit(visit)
    allowed = {"IN_SERVICE"} | ({"ON_HOLD", "READY_TO_RESUME"} if allow_held else set())
    _state_guard(entry, allowed, detail="Only an in-service entry can be completed.")
    completed_at = now()
    service_start = entry.started_at or entry.service_started_at
    service_seconds = (
        max(0, math.floor((completed_at - service_start).total_seconds()))
        if service_start
        else None
    )
    before = _persist(
        entry,
        state="COMPLETED",
        actor_fields={"completed_by": actor},
        extra_fields={
            "completed_at": completed_at,
            "service_seconds": service_seconds,
            "terminal_reason": terminal_reason or entry.terminal_reason,
            "removed_at": None,
            "removed_by": None,
        },
    )
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_SERVICE_COMPLETED",
        entry=entry,
        before=before,
        after={"state": entry.state, "version": entry.version, "service_seconds": service_seconds},
    )
    return entry


def _create_destination_locked(
    *,
    organisation,
    facility,
    actor,
    visit,
    department,
    queue_type,
    priority="ROUTINE",
    source_stage="",
    handoff_note="",
    work_identity=None,
    source_event_id=None,
):
    if visit is None:
        raise _error("PREREQUISITE_MISSING", "A Visit is required before creating a queue entry.", status_code=422)
    _assert_active_visit(visit)
    if department is None or not department.is_active:
        raise _error("DESTINATION_DISABLED", "The destination department is not available.", status_code=422)
    if priority not in PRIORITIES:
        raise _error("INVALID_PRIORITY", "The queue priority is not supported.", status_code=400)
    queue_type = str(queue_type or department.code).upper()
    work_identity = work_identity or f"VISIT:{visit.id}:{queue_type}"
    source_event_id = source_event_id or work_identity
    existing = QueueEntry.objects.select_for_update().filter(
        organisation_id=visit.organisation_id,
        facility_id=facility.id,
        visit_id=visit.id,
        work_identity=work_identity,
    ).order_by("id").first()
    if existing is not None:
        return existing, False
    active_same_department = QueueEntry.objects.select_for_update().filter(
        organisation_id=visit.organisation_id,
        facility_id=facility.id,
        visit_id=visit.id,
        department_id=department.id,
        state__in=ACTIVE_STATES,
    ).order_by("id").first()
    if active_same_department is not None:
        return active_same_department, False
    last = QueueEntry.objects.filter(
        facility_id=facility.id,
        queue_date=visit.local_service_date,
    ).order_by("-sequence").values_list("sequence", flat=True).first()
    sequence = allocate_sequence(
        organisation=organisation,
        facility=facility,
        sequence_type="QUEUE",
        period_key=visit.local_service_date.isoformat(),
        initial_value=(last or 0) + 1,
    )
    queued_at = now()
    try:
        # PostgreSQL uniqueness races leave the outer transaction unusable
        # unless the losing insert is isolated in a recoverable savepoint.
        with transaction.atomic():
            entry = QueueEntry.objects.create(
                organisation=organisation,
                facility=facility,
                visit=visit,
                patient=visit.patient,
                department=department,
                queue_date=visit.local_service_date,
                sequence=sequence,
                queue_type=queue_type,
                work_identity=work_identity,
                hold_reason="",
                hold_ref=None,
                priority=priority,
                visit_type=visit.visit_type,
                status="WAITING",
                state="WAITING",
                current_stage=department.code,
                source_stage=source_stage or department.code,
                queue_time=queued_at,
                notes=handoff_note or "",
                source_event_id=source_event_id,
                last_activity_at=queued_at,
            )
    except IntegrityError:
        entry = QueueEntry.objects.select_for_update().filter(
            organisation_id=visit.organisation_id,
            facility_id=facility.id,
            visit_id=visit.id,
            work_identity=work_identity,
        ).first()
        if entry is None:
            entry = QueueEntry.objects.select_for_update().filter(
                organisation_id=visit.organisation_id,
                facility_id=facility.id,
                visit_id=visit.id,
                department_id=department.id,
                state__in=ACTIVE_STATES,
            ).order_by("id").first()
        if entry is None:
            raise _error(
                "DESTINATION_CONFLICT",
                "The destination queue is already occupied and could not be reconciled safely.",
                metadata={"department_id": str(department.id)},
            )
        return entry, False
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="QUEUE_ENTRY_CREATED",
        action="CREATE",
        entity_type="QueueEntry",
        entity_id=entry.id,
        source_ids={"queue_entry_id": entry.id, "visit_id": visit.id},
        after={
            "state": entry.state,
            "queue_type": entry.queue_type,
            "source_stage": entry.source_stage,
            "priority": entry.priority,
        },
    )
    return entry, True


def create_or_reuse_destination(
    *,
    organisation,
    facility,
    actor,
    visit,
    department=None,
    department_id=None,
    queue_type=None,
    priority=None,
    source_stage="",
    handoff_note="",
    work_identity=None,
    source_event_id=None,
):
    """Create one waiting destination or return its existing source identity."""

    _require_transaction()
    _require_target_write(organisation)
    # Facility/Department are rank-1 configuration rows and must be locked
    # before the Visit/QueueEntry aggregate under LOCK-01.
    department = _lock_department(
        organisation=organisation,
        facility=facility,
        department=department,
        department_id=department_id,
        required=True,
    )
    visit = Visit.objects.select_for_update().filter(
        id=_identifier(visit),
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
    ).first()
    if visit is None:
        raise _error("NOT_FOUND", "The Visit was not found in this facility.", status_code=404)
    _assert_active_visit(visit)
    selected_priority = priority or "ROUTINE"
    if priority is None:
        source = QueueEntry.objects.filter(
            organisation_id=visit.organisation_id,
            facility_id=facility.id,
            visit_id=visit.id,
            state__in=ACTIVE_STATES,
        ).order_by("id").first()
        selected_priority = source.priority if source else "ROUTINE"
    return _create_destination_locked(
        organisation=organisation,
        facility=facility,
        actor=actor,
        visit=visit,
        department=department,
        queue_type=queue_type,
        priority=selected_priority,
        source_stage=source_stage,
        handoff_note=handoff_note,
        work_identity=work_identity,
        source_event_id=source_event_id,
    )


def resolve_transfer_destination(*, organisation, facility, target_department_id=None):
    """Return the effective ``(department_id, work type)`` for a transfer.

    The work type is the requested value or, when omitted, the department's
    code, which is the same rule ``transfer`` applies when it creates the
    destination. ``(None, None)`` means the department is not available in
    this facility, so the command keeps its existing scoped error.

    This is a read-only resolution for authorization; the command still locks
    the department when it executes.
    """

    if not target_department_id:
        return None, None
    department = Department.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
        id=target_department_id,
        is_active=True,
    ).only("id", "code").first()
    if department is None:
        return None, None
    return department.id, str(department.code).upper()


def transfer(
    *,
    organisation,
    facility,
    actor,
    source_queue_entry_id=None,
    queue_entry_id=None,
    target_department=None,
    target_department_id=None,
    target_queue_type=None,
    handoff_note="",
    reason="",
    expected_version=None,
):
    """Complete/transfer a source stage and create one waiting destination."""

    _require_transaction()
    _require_target_write(organisation)
    source_id = source_queue_entry_id or queue_entry_id
    department = _lock_department(
        organisation=organisation,
        facility=facility,
        department=target_department,
        department_id=target_department_id,
        required=True,
    )
    identity = QueueEntry.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
        id=source_id,
    ).values("visit_id").first()
    if identity is None:
        raise _error("NOT_FOUND", "The source queue entry was not found in this facility.", status_code=404)
    visit = Visit.objects.select_for_update().filter(
        id=identity["visit_id"],
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
    ).first()
    if visit is None:
        raise _error("PREREQUISITE_MISSING", "A transfer requires a linked Visit.", status_code=422)
    _assert_active_visit(visit)
    source_probe = QueueEntry.objects.filter(
        id=source_id,
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
    ).first()
    if source_probe is None:
        raise _error("NOT_FOUND", "The source queue entry was not found in this facility.", status_code=404)
    source_stage = source_probe.current_stage or source_probe.source_stage
    normalized_target_type = str(target_queue_type or department.code).upper()
    handoff_identity = f"QUEUE-HANDOFF:{source_probe.id}:{department.id}:{normalized_target_type}"
    candidate_ids = set(
        QueueEntry.objects.filter(
            organisation_id=visit.organisation_id,
            facility_id=facility.id,
            visit_id=visit.id,
            work_identity=handoff_identity,
        ).values_list("id", flat=True)
    )
    if source_probe.state == "TRANSFERRED":
        candidate_ids.update(
            QueueEntry.objects.filter(
                organisation_id=visit.organisation_id,
                facility_id=facility.id,
                visit_id=visit.id,
                department_id=department.id,
                source_stage=source_stage,
                state="WAITING",
            ).values_list("id", flat=True)
        )
    locked_ids = candidate_ids | {source_probe.id}
    locked_entries = list(
        QueueEntry.objects.select_for_update().filter(
            organisation_id=_organisation_id(organisation),
            facility_id=_facility_id(facility),
            id__in=locked_ids,
        ).order_by("id")
    )
    locked_by_id = {entry.id: entry for entry in locked_entries}
    source = locked_by_id.get(source_probe.id)
    if source is None:
        raise _error("NOT_FOUND", "The source queue entry was not found in this facility.", status_code=404)
    linked_source_visit = _require_linked_visit(source)
    if linked_source_visit.id != visit.id:
        raise _error(
            "PREREQUISITE_MISSING",
            "The source queue entry Visit changed while the transfer was acquiring its lock.",
            status_code=422,
        )
    if source.version != source_probe.version or source.state != source_probe.state:
        raise _error(
            "VERSION_CONFLICT",
            "The source queue entry changed; refresh before transferring it.",
            status_code=412,
            metadata={"current_version": source.version},
        )
    _version_guard(source, expected_version)
    redirect = str(reason or "").strip().upper() in {"WRONG_QUEUE", "ROUTED_IN_ERROR"}
    # A transfer owns completion of the source stage. Waiting/called rows
    # cannot be redirected around mandatory stage-completion guards.
    allowed_states = {"IN_SERVICE", "COMPLETED", "TRANSFERRED"}
    _state_guard(
        source,
        allowed_states,
        detail="Only an in-service or completed stage can be handed off; wrong-queue redirects may leave waiting work.",
    )
    existing = next(
        (entry for entry in locked_entries if entry.work_identity == handoff_identity),
        None,
    )
    if existing is None and source.state == "TRANSFERRED":
        existing = next(
            (
                entry
                for entry in locked_entries
                if entry.department_id == department.id
                and entry.source_stage == source_stage
                and entry.state == "WAITING"
            ),
            None,
        )
    if source.state in {"COMPLETED", "TRANSFERRED"}:
        if existing is None:
            raise _error(
                "INVALID_STATE",
                "The source stage is already terminal and has no matching handoff to replay.",
                metadata={"state": source.state},
            )
        return source, existing

    source_terminal_state = "TRANSFERRED" if redirect else "COMPLETED"
    completed_at = now()
    service_start = source.started_at or source.service_started_at
    service_seconds = (
        max(0, math.floor((completed_at - service_start).total_seconds()))
        if service_start
        else None
    )
    before = _persist(
        source,
        state=source_terminal_state,
        actor_fields=(
            {"completed_by": actor, "removed_by": actor}
            if redirect
            else {"completed_by": actor}
        ),
        extra_fields={
            "completed_at": completed_at,
            "removed_at": completed_at if redirect else None,
            "service_seconds": service_seconds,
            "terminal_reason": reason.strip() or source_terminal_state,
        },
    )
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_TRANSFERRED" if redirect else "QUEUE_SERVICE_COMPLETED",
        entry=source,
        before=before,
        after={"state": source.state, "version": source.version, "reason_hash": _reason_hash(reason)},
    )
    destination, _ = _create_destination_locked(
        organisation=organisation,
        facility=facility,
        actor=actor,
        visit=visit,
        department=department,
        queue_type=normalized_target_type,
        priority=source.priority,
        source_stage=source_stage,
        handoff_note=handoff_note,
        work_identity=handoff_identity,
        source_event_id=handoff_identity,
    )
    # A handoff is one atomic command even for a wrong-queue redirect.  Keep
    # the pre-transition snapshot in the audit fact; the old implementation
    # recorded the already-mutated source and omitted redirects entirely.
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="QUEUE_HANDOFF",
        action="UPDATE",
        entity_type="QueueEntry",
        entity_id=source.id,
        source_ids={
            "source_queue_entry_id": source.id,
            "destination_queue_entry_id": destination.id,
            "visit_id": visit.id,
        },
        before={"state": before["state"], "version": before["version"]},
        after={
            "state": source.state,
            "version": source.version,
            "destination_queue_entry_id": str(destination.id),
            "reason_hash": _reason_hash(reason),
        },
        reason_code="QUEUE_HANDOFF",
    )
    return source, destination


def assign(
    *,
    organisation,
    facility,
    actor,
    queue_entry_id=None,
    entry_id=None,
    target_user=None,
    target_user_id=None,
    expected_version=None,
):
    _require_transaction()
    _require_target_write(organisation)
    visit, entry = _lock_entry_after_visit(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id or entry_id,
    )
    _assert_active_visit(visit)
    _version_guard(entry, expected_version)
    _state_guard(entry, ACTIVE_STATES)
    target_id = target_user_id or _identifier(target_user)
    target = User.objects.filter(id=target_id, is_active=True).first()
    if target is None:
        raise _error("OUT_OF_SCOPE", "The assigned user is not available.", status_code=422)
    in_scope = UserFacilityRole.objects.filter(
        organisation_id=entry.organisation_id,
        user_id=target.id,
        status="ACTIVE",
    ).filter(
        models.Q(facility_id=entry.facility_id) | models.Q(facility_id__isnull=True)
    ).filter(
        models.Q(department_id=entry.department_id) | models.Q(department_id__isnull=True)
    ).exists()
    if not in_scope:
        raise _error("OUT_OF_SCOPE", "The assigned user is not granted this queue scope.", status_code=422)
    before = _persist(entry, extra_fields={"assigned_user": target})
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_ASSIGNED",
        entry=entry,
        before=before,
        after={"assigned_user_id": str(target.id), "version": entry.version},
    )
    return entry


def _role_templates(*, organisation, user, facility_id, department_id=None):
    if user is None:
        return set()
    return set(
        UserFacilityRole.objects.filter(
            organisation_id=_organisation_id(organisation),
            user_id=user.id,
            status="ACTIVE",
        ).filter(
            models.Q(facility_id=facility_id) | models.Q(facility_id__isnull=True)
        ).filter(
            models.Q(department_id=department_id) | models.Q(department_id__isnull=True)
        ).values_list("role__template_code", flat=True)
    )


def change_priority(
    *,
    organisation,
    facility,
    actor,
    queue_entry_id=None,
    entry_id=None,
    priority,
    reason,
    expected_version=None,
):
    _require_transaction()
    _require_target_write(organisation)
    priority = str(priority or "").upper()
    reason = str(reason or "").strip()
    if priority not in PRIORITIES:
        raise _error("INVALID_PRIORITY", "The queue priority is not supported.", status_code=400)
    if len(reason) < 3:
        raise _error("PRIORITY_REASON_REQUIRED", "A reason is required for a priority change.", status_code=400)
    visit, entry = _lock_entry_after_visit(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id or entry_id,
    )
    _version_guard(entry, expected_version)
    _assert_active_visit(visit)
    _state_guard(entry, {"WAITING", "CALLED"}, detail="Priority can only change before service starts.")
    if priority == entry.priority:
        return entry
    old_rank = PRIORITY_ORDER.get(entry.priority, 2)
    new_rank = PRIORITY_ORDER[priority]
    templates = _role_templates(
        organisation=organisation,
        user=actor,
        facility_id=entry.facility_id,
        department_id=entry.department_id,
    )
    if new_rank > old_rank and not templates.intersection(
        {"CLINICIAN", "SUPERVISOR", "FACILITY_ADMIN", "ORG_OWNER", "OWNER_ADMIN"}
    ):
        raise _error("FORBIDDEN", "Only a clinician or supervisor can de-escalate priority.", status_code=403)
    before_priority = entry.priority
    before = _persist(
        entry,
        extra_fields={
            "priority": priority,
            "priority_changed_at": now(),
            "priority_reason": reason,
        },
    )
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_PRIORITY_CHANGED",
        entry=entry,
        before={**before, "priority": before_priority},
        after={"priority": priority, "version": entry.version, "reason_hash": _reason_hash(reason)},
        reason_code="PRIORITY_CHANGE",
    )
    return entry


def hold(
    *,
    organisation,
    facility,
    actor,
    queue_entry_id=None,
    entry_id=None,
    hold_reason="",
    hold_ref="",
    expected_version=None,
):
    _require_transaction()
    _require_target_write(organisation)
    hold_reason = str(hold_reason or "").upper()
    hold_ref = str(hold_ref or "").strip()
    if hold_reason not in HOLD_REASONS or not hold_ref:
        raise _error("PREREQUISITE_MISSING", "A hold reason and dependency reference are required.", status_code=400)
    visit, entry = _lock_entry_after_visit(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id or entry_id,
    )
    _version_guard(entry, expected_version)
    _assert_active_visit(visit)
    _state_guard(entry, {"IN_SERVICE"}, detail="Only an in-service entry can be held.")
    before = _persist(
        entry,
        state="ON_HOLD",
        extra_fields={"hold_reason": hold_reason, "hold_ref": hold_ref, "held_at": now()},
    )
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_HELD",
        entry=entry,
        before=before,
        after={"state": entry.state, "hold_reason": hold_reason, "hold_ref_present": True, "version": entry.version},
    )
    return entry


def mark_ready_to_resume(
    *,
    organisation,
    facility,
    actor=None,
    queue_entry_id=None,
    entry_id=None,
    expected_version=None,
):
    _require_transaction()
    _require_target_write(organisation)
    visit, entry = _lock_entry_after_visit(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id or entry_id,
    )
    _version_guard(entry, expected_version)
    _assert_active_visit(visit)
    _state_guard(entry, {"ON_HOLD"}, detail="Only a held entry can become ready to resume.")
    before = _persist(entry, state="READY_TO_RESUME")
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_READY_TO_RESUME",
        entry=entry,
        before=before,
        after={"state": entry.state, "version": entry.version},
    )
    return entry


def resume(
    *,
    organisation,
    facility,
    actor,
    queue_entry_id=None,
    entry_id=None,
    expected_version=None,
    allow_early=True,
):
    _require_transaction()
    _require_target_write(organisation)
    visit, entry = _lock_entry_after_visit(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id or entry_id,
    )
    _version_guard(entry, expected_version)
    _assert_active_visit(visit)
    _state_guard(entry, {"ON_HOLD", "READY_TO_RESUME"}, detail="Only a held entry can resume service.")
    if not allow_early and entry.state != "READY_TO_RESUME":
        raise _error("PREREQUISITE_MISSING", "The held dependency is not ready to resume.", status_code=422)
    _assert_global_in_service(
        organisation=organisation,
        visit=visit,
        facility=facility,
        entry_id=entry.id,
    )
    before = _persist(entry, state="IN_SERVICE", actor_fields={"served_by": actor})
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_RESUMED",
        entry=entry,
        before=before,
        after={"state": entry.state, "version": entry.version, "served_by_id": str(actor.id)},
    )
    return entry


def requeue_same_entry(
    *,
    organisation,
    facility,
    actor,
    queue_entry_id=None,
    entry_id=None,
    expected_version=None,
    reason="",
):
    _require_transaction()
    _require_target_write(organisation)
    reason = str(reason or "").strip()
    if len(reason) < 3:
        raise _error("REASON_REQUIRED", "A reason is required to re-queue a no-show entry.", status_code=400)
    visit, entry = _lock_entry_after_visit(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id or entry_id,
    )
    _version_guard(entry, expected_version)
    _assert_active_visit(visit)
    _state_guard(entry, {"NO_SHOW"}, detail="Only a no-show entry can be re-queued.")
    before = _persist(entry, state="WAITING", extra_fields={"terminal_reason": None})
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_REQUEUED",
        entry=entry,
        before=before,
        after={"state": entry.state, "version": entry.version, "reason_hash": _reason_hash(reason)},
        reason_code="REQUEUE",
    )
    return entry


def no_response(
    *,
    organisation,
    facility,
    actor=None,
    queue_entry_id=None,
    entry_id=None,
    expected_version=None,
    outcome="REQUEUE",
    emergency_acknowledged=False,
    system=False,
    observed_at=None,
):
    _require_transaction()
    _require_target_write(organisation)
    outcome = str(outcome or "REQUEUE").upper()
    if outcome not in NO_RESPONSE_OUTCOMES:
        raise _error("INVALID_OUTCOME", "The no-response outcome is not supported.", status_code=400)
    system = bool(system or actor is None)
    policy = FacilityWorkflowPolicy.objects.select_for_update().filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
    ).first()
    expiry_minutes = policy.queue_call_expiry_minutes if policy else 10
    final_attempts = policy.queue_no_show_final_attempts if policy else 3
    visit, entry = _lock_entry_after_visit(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id or entry_id,
    )
    _assert_active_visit(visit)
    _version_guard(entry, expected_version)
    _state_guard(entry, {"CALLED"}, detail="No-response can only be recorded for a called entry.")
    observed_at = observed_at or now()
    if system:
        if entry.called_at is None or observed_at < entry.called_at + timedelta(minutes=expiry_minutes):
            raise _error("CALL_NOT_EXPIRED", "The configured call-expiry window has not elapsed.", status_code=422)
        outcome = "REQUEUE"
    elif outcome == "NO_SHOW" and entry.priority == "EMERGENCY" and not emergency_acknowledged:
        raise _error(
            "REQUIRED_CONFIRMATION",
            "Emergency no-show handling requires explicit confirmation.",
            status_code=422,
        )
    attempts = entry.call_attempts + 1
    no_shows = entry.no_show_count + 1
    final_attempt = attempts >= max(1, int(final_attempts))
    emergency_escalation = entry.priority == "EMERGENCY" and (
        outcome == "NO_SHOW"
        or (
            entry.called_at is not None
            and observed_at >= entry.called_at + timedelta(minutes=10)
        )
    )
    if outcome == "REQUEUE":
        new_state = "WAITING"
        extra = {"call_attempts": attempts, "no_show_count": no_shows}
    else:
        new_state = "NO_SHOW"
        extra = {
            "call_attempts": attempts,
            "no_show_count": no_shows,
            "terminal_reason": "NO_RESPONSE",
            "removed_at": observed_at,
            "removed_by": actor,
        }
    before = _persist(entry, state=new_state, extra_fields=extra)
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_CALL_EXPIRED" if system else "QUEUE_NO_SHOW",
        entry=entry,
        before=before,
        after={
            "state": entry.state,
            "version": entry.version,
            "call_attempts": entry.call_attempts,
            "no_show_count": entry.no_show_count,
            "priority": entry.priority,
            "follow_up_required": no_shows >= 2 or entry.state == "NO_SHOW",
            "final_attempt": final_attempt,
            "lwbs_action_available": final_attempt and entry.state in {"WAITING", "NO_SHOW"},
            "emergency_escalation": emergency_escalation,
        },
        reason_code="CALL_EXPIRED" if system else "NO_RESPONSE",
    )
    return entry


def _mark_lwbs_locked(
    *, organisation, facility, actor, visit, entry, queue_entries, reason, reason_text="", expected_version
):
    """Apply REC-009/CMD-007's atomic pre-service closure guards."""

    reason = str(reason or "").strip().upper()
    reason_text = str(reason_text or "").strip()
    if reason not in LWBS_REASONS:
        raise _error("INVALID_LWBS_REASON", "Select a supported LWBS reason.", status_code=400)
    if reason == "OTHER" and not reason_text:
        raise _error("REASON_TEXT_REQUIRED", "OTHER requires a supplied explanation.", status_code=400)
    if reason != "OTHER" and reason_text:
        raise _error("INVALID_LWBS_REASON", "Free text is only allowed for the OTHER LWBS reason.", status_code=400)

    _version_guard(entry, expected_version)
    if entry.state == "LWBS":
        return entry
    if visit is None:
        raise _error("PREREQUISITE_MISSING", "LWBS requires a linked Visit.", status_code=422)
    _assert_active_visit(visit)
    _state_guard(
        entry,
        {"WAITING", "WAITING_PAYMENT", "CALLED", "NO_SHOW"},
        detail="Only pre-service queue work can be marked left without being seen.",
    )
    other_active_entries = [
        candidate
        for candidate in queue_entries
        if candidate.id != entry.id and candidate.state in ACTIVE_STATES
    ]
    if other_active_entries:
        raise _error(
            "INVALID_STATE",
            "Resolve the other active queue stage before closing this Visit as LWBS.",
            metadata={"active_queue_entry_id": str(other_active_entries[0].id)},
        )

    encounters = list(
        Encounter.objects.select_for_update().filter(
            organisation_id=entry.organisation_id,
            facility_id=entry.facility_id,
            visit_id=visit.id,
        ).order_by("id")
    )
    for encounter in encounters:
        if encounter.status in {"OPEN", "AWAITING_RESULTS", "RESULTS_READY"}:
            raise _error(
                "ENCOUNTER_UNRESOLVED",
                "Resolve the linked clinical record before recording LWBS.",
                status_code=409,
                metadata={"encounter_id": str(encounter.id), "encounter_state": encounter.status},
            )
        if encounter.status == "SIGNED":
            raise _error(
                "INVALID_STATE",
                "A clinical Encounter exists; use the ordinary Visit closure workflow instead of LWBS.",
                status_code=409,
                metadata={"encounter_id": str(encounter.id), "encounter_state": encounter.status},
            )

    triage_exists = TriageAssessment.objects.filter(
        organisation_id=entry.organisation_id,
        facility_id=entry.facility_id,
        queue_entry__visit_id=visit.id,
    ).exists()
    vitals_exists = VitalsObservation.objects.filter(
        organisation_id=entry.organisation_id,
        facility_id=entry.facility_id,
        encounter_id__in=[encounter.id for encounter in encounters],
    ).exists()
    if triage_exists or vitals_exists:
        raise _error(
            "CLINICAL_RECORD_EXISTS",
            "Clinical triage or observations must be resolved before recording LWBS.",
            status_code=409,
            metadata={
                "triage_record_present": triage_exists,
                "vitals_record_present": vitals_exists,
            },
        )

    from laboratory.queries import blocking_visit_records as laboratory_blockers
    from pharmacy.queries import blocking_visit_records as pharmacy_blockers

    lab_blockers = tuple(laboratory_blockers(organisation=organisation, facility=facility, visit_id=visit.id) or ())
    pharmacy_blockers = tuple(pharmacy_blockers(organisation=organisation, facility=facility, visit_id=visit.id) or ())
    if lab_blockers or pharmacy_blockers:
        raise _error(
            "DOWNSTREAM_WORK_EXISTS",
            "Laboratory or pharmacy work must be resolved before recording LWBS.",
            status_code=409,
            metadata={
                "laboratory_blocker_count": len(lab_blockers),
                "pharmacy_blocker_count": len(pharmacy_blockers),
            },
        )

    invoice_ids = list(Invoice.objects.filter(
        organisation_id=entry.organisation_id,
        facility_id=entry.facility_id,
        visit_id=visit.id,
    ).exclude(status__in={"VOID", "VOIDED"}).order_by("created_at", "id").values_list("id", flat=True))
    # Payment and allocation rows are locked before their Invoice rows.  The
    # full set is considered, rather than silently inspecting only the oldest
    # invoice for this Visit.
    payments = list(Payment.objects.select_for_update().filter(
        organisation_id=entry.organisation_id,
        facility_id=entry.facility_id,
        invoice_id__in=invoice_ids,
    ).order_by("invoice_id", "id"))
    allocations = list(PaymentAllocation.objects.select_for_update().filter(
        organisation_id=entry.organisation_id,
        facility_id=entry.facility_id,
        invoice_id__in=invoice_ids,
    ).order_by("invoice_id", "id"))
    invoices = list(Invoice.objects.select_for_update().filter(
        id__in=invoice_ids,
        organisation_id=entry.organisation_id,
        facility_id=entry.facility_id,
        visit_id=visit.id,
    ).exclude(status__in={"VOID", "VOIDED"}).order_by("created_at", "id"))
    payments_by_invoice = {}
    for payment in payments:
        payments_by_invoice.setdefault(payment.invoice_id, []).append(payment)
    allocations_by_invoice = {}
    for allocation in allocations:
        allocations_by_invoice.setdefault(allocation.invoice_id, []).append(allocation)
    invoice_payment_state = []
    for invoice in invoices:
        paid_value = invoice.amount_paid
        invoice_payments = payments_by_invoice.get(invoice.id, [])
        invoice_allocations = allocations_by_invoice.get(invoice.id, [])
        effective_payment = bool(
            paid_value > 0
            or invoice.status in {"PAID", "PARTIALLY_PAID"}
            or invoice_allocations
            or any(payment.status == "POSTED" for payment in invoice_payments)
        )
        if invoice.status == "PARTIALLY_PAID":
            raise _error(
                "PREREQUISITE_MISSING",
                "Resolve the partially paid Invoice through its authorised financial workflow before LWBS.",
                status_code=422,
                metadata={
                    "invoice_id": str(invoice.id),
                    "current_authoritative_amount_due": str(invoice.total),
                    "current_effective_applied_value": str(paid_value),
                    "remaining_balance": str(invoice.balance),
                    "financial_owner_action": "PAY-008/BIL-010",
                },
            )
        invoice_payment_state.append((invoice, effective_payment))

    reason_hash = _reason_hash(f"{reason}|{reason_text}")
    paid_invoice = None
    has_effective_payment = False
    for invoice, invoice_has_payment in invoice_payment_state:
        if invoice_has_payment:
            paid_invoice = paid_invoice or invoice
            has_effective_payment = True
            continue
        try:
            invoice, invoice_voided = void_unpaid_visit_invoice(
                organisation=organisation,
                facility=facility,
                actor=actor,
                invoice=invoice,
                reason_hash=reason_hash,
            )
        except ValueError as exc:
            raise _error(
                "PREREQUISITE_MISSING",
                "The Invoice is not in an eligible unpaid state for LWBS.",
                status_code=422,
                metadata={"invoice_id": str(invoice.id)},
            ) from exc
        if invoice_voided:
            record_fact(
                organisation=organisation,
                actor=actor,
                facility=facility,
                event_code="INVOICE_VOIDED",
                action="UPDATE",
                entity_type="Invoice",
                entity_id=invoice.id,
                source_ids={"visit_id": visit.id, "invoice_id": invoice.id},
                after={"state": invoice.status, "reason_hash": reason_hash},
            )
    for invoice, invoice_has_payment in invoice_payment_state:
        if not invoice_has_payment:
            continue
        record_fact(
            organisation=organisation,
            actor=actor,
            facility=facility,
            event_code="LWBS_PAID_REFUND_REVIEW_REQUIRED",
            action="UPDATE",
            entity_type="Invoice",
            entity_id=invoice.id,
            source_ids={"visit_id": visit.id, "invoice_id": invoice.id},
            after={
                "state": invoice.status,
                "refund_review_required": True,
                "amount_paid": str(invoice.amount_paid),
            },
            reason_code="PAY-008",
        )

    closed_at = now()
    before = _persist(
        entry,
        state="LWBS",
        actor_fields={"completed_by": actor, "removed_by": actor},
        extra_fields={
            "terminal_reason": reason,
            "completed_at": closed_at,
            "removed_at": closed_at,
            "notes": _lwbs_notes(entry, reason_text),
        },
    )
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_ENTRY_REMOVED",
        entry=entry,
        before=before,
        after={
            "state": entry.state,
            "version": entry.version,
            "reason": reason,
            "reason_hash": reason_hash,
        },
        reason_code="QUEUE_REMOVAL",
    )
    visit.state = "CLOSED"
    visit.closure_reason = "LWBS_PAID" if paid_invoice is not None and has_effective_payment else "LWBS"
    visit.closed_at = closed_at
    visit.closed_by = actor
    visit.version += 1
    visit.save(update_fields=["state", "closure_reason", "closed_at", "closed_by", "version", "updated_at"])
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="VISIT_CLOSED_LWBS",
        action="UPDATE",
        entity_type="Visit",
        entity_id=visit.id,
        source_ids={"visit_id": visit.id, "queue_entry_id": entry.id},
        after={
            "state": visit.state,
            "closure_reason": visit.closure_reason,
            "version": visit.version,
            "reason_hash": reason_hash,
        },
        reason_code="LWBS",
    )
    return entry


def lwbs(
    *,
    organisation,
    facility,
    actor,
    queue_entry_id=None,
    entry_id=None,
    expected_version=None,
    reason="LEFT_WITHOUT_BEING_SEEN",
    reason_text="",
):
    """Own the explicit REC-009/CMD-007 LWBS transition."""

    _require_transaction()
    _require_target_write(organisation)
    reason = str(reason or "").strip().upper()
    reason_text = str(reason_text or "").strip()
    visit, entry, queue_entries = _lock_lwbs_context(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id or entry_id,
    )
    return _mark_lwbs_locked(
        organisation=organisation,
        facility=facility,
        actor=actor,
        visit=visit,
        entry=entry,
        queue_entries=queue_entries,
        reason=reason,
        reason_text=reason_text,
        expected_version=expected_version,
    )


def cancel(
    *,
    organisation,
    facility,
    actor,
    queue_entry_id=None,
    entry_id=None,
    expected_version=None,
    reason="",
    lwbs=False,
):
    _require_transaction()
    _require_target_write(organisation)
    reason = str(reason or "").upper()
    if reason not in REMOVAL_REASONS:
        raise _error("CANCEL_REASON_REQUIRED", "A supported queue removal reason is required.", status_code=400)
    is_lwbs = lwbs or reason == "LEFT_WITHOUT_BEING_SEEN"
    if is_lwbs:
        # Keep the historical service import callable for S-01 callers.  The
        # HTTP queue command rejects this branch; reception owns LWBS through
        # the explicit ``lwbs`` command below.
        return queue_lwbs(
            organisation=organisation,
            facility=facility,
            queue_entry_id=queue_entry_id or entry_id,
            actor=actor,
            reason=reason,
            expected_version=expected_version,
        )
    visit, entry = _lock_entry_after_visit(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id or entry_id,
    )
    _assert_active_visit(visit)
    _version_guard(entry, expected_version)
    _state_guard(
        entry,
        {"WAITING", "WAITING_PAYMENT", "CALLED", "NO_SHOW"},
        detail="An in-service queue entry must be completed through its owning workflow.",
    )
    terminal_state = "CANCELLED"
    removed_at = now()
    before = _persist(
        entry,
        state=terminal_state,
        actor_fields={"completed_by": actor, "removed_by": actor},
        extra_fields={
            "terminal_reason": reason,
            "completed_at": removed_at,
            "removed_at": removed_at,
        },
    )
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_ENTRY_REMOVED",
        entry=entry,
        before=before,
        after={"state": entry.state, "version": entry.version, "reason": reason},
        reason_code="QUEUE_REMOVAL",
    )
    return entry


def takeover(
    *,
    organisation,
    facility,
    actor,
    queue_entry_id=None,
    entry_id=None,
    new_user=None,
    new_user_id=None,
    reason="",
    expected_version=None,
    observed_at=None,
    threshold_minutes=30,
):
    _require_transaction()
    _require_target_write(organisation)
    reason = str(reason or "").strip()
    if len(reason) < 3:
        raise _error("TAKEOVER_REASON_REQUIRED", "A reason is required to take over a queue entry.", status_code=400)
    visit, entry = _lock_entry_after_visit(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id or entry_id,
    )
    _assert_active_visit(visit)
    _version_guard(entry, expected_version)
    _state_guard(entry, {"CALLED", "IN_SERVICE"}, detail="Only a called or in-service entry can be taken over.")
    observed_at = observed_at or now()
    last_activity = entry.last_activity_at or entry.updated_at or entry.called_at or entry.queue_time
    elapsed_seconds = max(0, (observed_at - last_activity).total_seconds())
    threshold_seconds = max(0, int(threshold_minutes)) * 60
    if elapsed_seconds < threshold_seconds:
        remaining = max(1, math.ceil((threshold_seconds - elapsed_seconds) / 60))
        raise _error(
            "TAKEOVER_TOO_EARLY",
            "The current queue holder is still active.",
            status_code=422,
            metadata={"remaining_minutes": remaining},
        )
    target_id = new_user_id or _identifier(new_user) or _actor_id(actor)
    target = User.objects.filter(id=target_id, is_active=True).first()
    if target is None:
        raise _error("OUT_OF_SCOPE", "The takeover user is not available.", status_code=422)
    in_scope = UserFacilityRole.objects.filter(
        organisation_id=entry.organisation_id,
        user_id=target.id,
        status="ACTIVE",
    ).filter(
        models.Q(facility_id=entry.facility_id) | models.Q(facility_id__isnull=True)
    ).filter(
        models.Q(department_id=entry.department_id) | models.Q(department_id__isnull=True)
    ).exists()
    if not in_scope:
        raise _error("OUT_OF_SCOPE", "The takeover user is not granted this queue scope.", status_code=422)
    old_user_id = entry.assigned_user_id or entry.served_by_id or entry.called_by_id or entry.claimed_by_id
    # Lock the existing Encounter after QueueEntry (LOCK-01 order) only to
    # prove that takeover never rewrites its primary clinician. Subsequent
    # notes carry the acting user as their own author/co-author.
    encounter = Encounter.objects.select_for_update().filter(
        organisation_id=entry.organisation_id,
        facility_id=entry.facility_id,
        queue_entry_id=entry.id,
    ).first()
    co_author = None
    co_author_created = False
    if encounter is not None and target.id != encounter.clinician_id:
        co_author, co_author_created = EncounterCoAuthor.objects.get_or_create(
            organisation_id=entry.organisation_id,
            facility_id=entry.facility_id,
            encounter=encounter,
            user=target,
            defaults={
                "added_by": actor,
                "reason_hash": _reason_hash(reason),
            },
        )
    before = _persist(entry, extra_fields={"assigned_user": target})
    _safe_transition_event(
        organisation=organisation,
        facility=facility,
        actor=actor,
        event_code="QUEUE_TAKEOVER",
        entry=entry,
        before=before,
        after={
            "old_user_id": str(old_user_id) if old_user_id else None,
            "new_user_id": str(target.id),
            "version": entry.version,
            "encounter_id": str(encounter.id) if encounter else None,
            "encounter_primary_author_id": str(encounter.clinician_id) if encounter else None,
            "encounter_co_author_id": str(co_author.id) if co_author_created else None,
            "reason_hash": _reason_hash(reason),
        },
        reason_code="TAKEOVER",
    )
    if co_author_created:
        record_fact(
            organisation=organisation,
            actor=actor,
            facility=facility,
            event_code="ENCOUNTER_CO_AUTHOR_ADDED",
            action="CREATE",
            entity_type="EncounterCoAuthor",
            entity_id=co_author.id,
            source_ids={"encounter_id": encounter.id, "queue_entry_id": entry.id, "user_id": target.id},
            after={"reason_hash": _reason_hash(reason)},
            reason_code="TAKEOVER",
        )
    return entry


def expire_sweep(
    *,
    organisation,
    facility,
    actor=None,
    local_service_day=None,
    cutoff=None,
):
    """Expire stale waiting/called/no-show rows without closing recordful Visits."""

    _require_transaction()
    _require_target_write(organisation)
    if cutoff is not None:
        raise _error(
            "INVALID_CUTOFF",
            "Queue expiry accepts only the facility local service day.",
            status_code=400,
        )
    if local_service_day is None:
        local_service_day = timezone.localdate()
    candidates = QueueEntry.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
        visit_id__isnull=False,
        state__in={"WAITING", "WAITING_PAYMENT", "CALLED", "NO_SHOW"},
    )
    if local_service_day is not None:
        if isinstance(local_service_day, str):
            local_service_day = date.fromisoformat(local_service_day)
        candidates = candidates.filter(queue_date__lt=local_service_day)
    candidate_ids = list(candidates.order_by("visit_id", "queue_time", "id").values_list("id", flat=True))
    visit_ids = sorted({str(value) for value in candidates.exclude(visit_id__isnull=True).values_list("visit_id", flat=True)})
    locked_visits = {
        str(visit.id): visit
        for visit in Visit.objects.select_for_update().filter(
            organisation_id=_organisation_id(organisation),
            facility_id=_facility_id(facility),
            id__in=visit_ids,
        ).order_by("id")
    }
    entries = list(
        QueueEntry.objects.select_for_update().filter(id__in=candidate_ids).order_by("id")
    )
    expired_ids = []
    review_visit_ids = []
    for entry in entries:
        if entry.state not in {"WAITING", "WAITING_PAYMENT", "CALLED", "NO_SHOW"}:
            continue
        expiry_time = now()
        before = _persist(
            entry,
            state="EXPIRED",
            actor_fields={"completed_by": actor, "removed_by": actor},
            extra_fields={
                "terminal_reason": "DAY_ROLLOVER",
                "completed_at": expiry_time,
                "removed_at": expiry_time,
            },
        )
        _safe_transition_event(
            organisation=organisation,
            facility=facility,
            actor=actor,
            event_code="QUEUE_EXPIRED",
            entry=entry,
            before=before,
            after={"state": entry.state, "version": entry.version, "reason": "DAY_ROLLOVER"},
            reason_code="DAY_ROLLOVER",
        )
        expired_ids.append(entry.id)
    exceptions = list(
        QueueEntry.objects.filter(
            organisation_id=_organisation_id(organisation),
            facility_id=_facility_id(facility),
            visit_id__isnull=False,
            state="IN_SERVICE",
        ).filter(
            models.Q(queue_date__lt=local_service_day)
        ).order_by("visit_id", "queue_time", "id").values_list("id", flat=True)
    )
    closed_visit_ids = []
    for visit_id, visit in locked_visits.items():
        if visit.state not in Visit.ACTIVE_STATES:
            continue
        if QueueEntry.objects.filter(
            organisation_id=visit.organisation_id,
            facility_id=visit.facility_id,
            visit_id=visit.id,
            state__in=ACTIVE_STATES,
        ).exists():
            continue
        has_encounter = Encounter.objects.filter(
            organisation_id=visit.organisation_id,
            facility_id=visit.facility_id,
            visit_id=visit.id,
        ).exists()
        invoice = Invoice.objects.filter(
            organisation_id=visit.organisation_id,
            facility_id=visit.facility_id,
            visit_id=visit.id,
        ).order_by("-created_at", "id").first()
        has_invoice = invoice is not None
        if has_encounter or has_invoice:
            review_visit_ids.append(visit.id)
            review_reason = "REVIEW_REQUIRED" if invoice is not None and invoice.status == "PAID" else "STALE_OPEN"
            visit.stale_review_required = True
            visit.stale_review_reason = review_reason
            visit.stale_review_amount = invoice.amount_paid if review_reason == "REVIEW_REQUIRED" else None
            visit.version += 1
            visit.save(
                update_fields=[
                    "stale_review_required",
                    "stale_review_reason",
                    "stale_review_amount",
                    "version",
                    "updated_at",
                ]
            )
            record_fact(
                organisation=organisation,
                actor=actor,
                facility=facility,
                event_code="VISIT_STALE_REVIEW_REQUIRED",
                action="UPDATE",
                entity_type="Visit",
                entity_id=visit.id,
                source_ids={"visit_id": visit.id},
                after={
                    "review_reason": review_reason,
                    "amount_present": visit.stale_review_amount is not None,
                },
                reason_code="DAY_ROLLOVER",
            )
        if not has_encounter and not has_invoice and actor is not None:
            closed_at = now()
            visit.state = "CLOSED"
            visit.closure_reason = "ABANDONED"
            visit.closed_at = closed_at
            visit.closed_by = actor
            visit.version += 1
            visit.save(update_fields=["state", "closure_reason", "closed_at", "closed_by", "version", "updated_at"])
            record_fact(
                organisation=organisation,
                actor=actor,
                facility=facility,
                event_code="VISIT_CLOSED",
                action="UPDATE",
                entity_type="Visit",
                entity_id=visit.id,
                source_ids={"visit_id": visit.id},
                after={"state": "CLOSED", "closure_reason": "ABANDONED", "version": visit.version},
            )
            closed_visit_ids.append(visit.id)
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="QUEUE_SWEEP_RUN",
        action="UPDATE",
        entity_type="QueueSweep",
        entity_id=facility.id,
        source_ids={"facility_id": facility.id},
        after={
            "expired_count": len(expired_ids),
            "exception_count": len(exceptions),
            "closed_visit_count": len(closed_visit_ids),
            "review_visit_count": len(review_visit_ids),
        },
    )
    return QueueSweepResult(
        expired_entry_ids=tuple(expired_ids),
        exceptions=tuple(exceptions),
        closed_visit_ids=tuple(closed_visit_ids),
        review_visit_ids=tuple(review_visit_ids),
    )


# Descriptive aliases used by application command adapters and tests.
call_queue_entry = call_next_or_exact
queue_call = call_next_or_exact
queue_start_service = start_service
queue_complete = complete
queue_transfer = transfer
queue_assign = assign
queue_priority_change = change_priority
queue_hold = hold
queue_resume = resume
queue_requeue = requeue_same_entry
queue_no_response = no_response
queue_cancel = cancel
queue_lwbs = lwbs
queue_takeover = takeover
queue_expire_sweep = expire_sweep
remove = cancel
