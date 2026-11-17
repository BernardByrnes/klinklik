"""Role-minimal, read-only QueueEntry projections for S-02."""

import statistics

from django.db import models

from accounts.models import UserFacilityRole
from billing.models import Invoice
from clinical.models import TriageAssessment
from core.clock import now
from core.errors import CanonicalError
from core.permissions import UNRESTRICTED_SCOPE, queue_scope_pairs, scope_query
from core.services import assert_transaction_active
from scheduling.models import QueueEntry, Visit
from tenancy.models import Department, FacilityWorkflowPolicy


WAITING_SLA_MINUTES = 30
IN_SERVICE_SLA_MINUTES = 60
ON_HOLD_SLA_MINUTES = 120
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
# Route capabilities. Every read resolves grant pairs from these; the queue
# type and department stay paired so a two-department grant never becomes a
# cross product.
QUEUE_READ_CAPABILITIES = ("queue.read", "queue.view")
QUEUE_HISTORY_CAPABILITIES = ("visit.read", "queue.read", "queue.view")
QUEUE_SUPERVISOR_CAPABILITIES = ("queue.read_board", "queue.supervise")


def _organisation_id(organisation):
    return getattr(organisation, "id", organisation)


def _facility_id(facility):
    return getattr(facility, "id", facility)


def _role_templates(*, organisation, actor, facility_id, department_id=None):
    if actor is None:
        return set()
    grants = UserFacilityRole.objects.filter(
        organisation_id=_organisation_id(organisation),
        user_id=actor.id,
        status="ACTIVE",
    ).filter(
        models.Q(facility_id=facility_id) | models.Q(facility_id__isnull=True),
        models.Q(department_id=department_id) | models.Q(department_id__isnull=True),
    )
    return set(grants.values_list("role__template_code", flat=True))


def _resolve_scope(*, organisation, facility, actor, capabilities, allowed_scopes=None):
    """Return this actor's paired ``(department, work type)`` grants.

    The API passes the pairs it already resolved from the route's declared
    capabilities so the read applies exactly the authorization that admitted
    the request. Direct service callers omit them and get the projection's own
    default capability set. ``None`` from either source means unrestricted.
    """

    if allowed_scopes is not None:
        return allowed_scopes
    if actor is None:
        # Internal and system reads have no actor to resolve; their call site
        # still applies the mandatory organisation and facility filters.
        return None
    return queue_scope_pairs(
        organisation=organisation,
        facility=facility,
        user=actor,
        capabilities=capabilities,
    )


def _apply_queue_scope(queryset, pairs):
    """Intersect a queryset with the paired scope, before ordering or paging."""

    predicate = scope_query(pairs)
    if predicate is UNRESTRICTED_SCOPE:
        return queryset
    return queryset.filter(predicate)


def _scoped_department_ids(pairs):
    """Return the departments a card may be shown for, or ``None`` for all."""

    if pairs is None:
        return None
    department_ids = set()
    for department_id, _ in pairs:
        if department_id is None:
            return None
        department_ids.add(department_id)
    return department_ids


def _require_target_reads(organisation):
    """Prevent canonical projections from bypassing the MIG-002 read fence."""

    from core.migration_reconciliation import target_reads_enabled_mig002

    if not target_reads_enabled_mig002(organisation):
        raise CanonicalError(
            "MIGRATION_TARGET_DISABLED",
            "Canonical QueueEntry reads are temporarily unavailable while migration compatibility is restored.",
            status_code=503,
            retryable=True,
        )


def _age_display(birth_date, *, as_of):
    if not birth_date:
        return None
    months = max(0, (as_of.year - birth_date.year) * 12 + as_of.month - birth_date.month)
    if as_of.day < birth_date.day:
        months = max(0, months - 1)
    if months < 60:
        return f"{months} mo"
    return f"{months // 12} y"


def _wait_seconds(entry, *, as_of):
    if entry.wait_seconds is not None and entry.state in {"IN_SERVICE", "ON_HOLD", "READY_TO_RESUME"}:
        return int(entry.wait_seconds)
    if entry.queue_time is None:
        return 0
    return max(0, int((as_of - entry.queue_time).total_seconds()))


def _ageing_seconds(entry, *, as_of):
    if entry.state in {"ON_HOLD", "READY_TO_RESUME"} and entry.held_at:
        return max(0, int((as_of - entry.held_at).total_seconds()))
    return _wait_seconds(entry, as_of=as_of)


def _invoice_projection(*, organisation, facility, visit_id):
    if not visit_id:
        return None
    invoice = Invoice.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
        visit_id=visit_id,
    ).exclude(status__in={"VOID", "VOIDED"}).order_by("-created_at", "id").first()
    if invoice is None:
        return None
    return {
        "invoice_no": invoice.invoice_no,
        "amount_due": str(invoice.balance),
        "currency": invoice.currency,
        "status": invoice.status,
    }


def _row_for_entry(*, entry, organisation, facility, actor, as_of, policy=None):
    patient = entry.patient
    role_templates = _role_templates(
        organisation=organisation,
        actor=actor,
        facility_id=entry.facility_id,
        department_id=entry.department_id,
    )
    queue_type = entry.queue_type.upper()
    final_attempts = max(1, int(policy.queue_no_show_final_attempts)) if policy else 3
    row = {
        "id": str(entry.id),
        "visit_id": str(entry.visit_id) if entry.visit_id else None,
        "patient_id": str(entry.patient_id),
        "patient_no": patient.patient_no,
        "patient_name": patient.display_name,
        "sex": patient.sex,
        "age": _age_display(patient.date_of_birth, as_of=as_of.date()),
        "queue_label": entry.queue_label,
        "token": entry.token,
        "department_id": str(entry.department_id),
        "department_name": entry.department.name,
        "queue_type": entry.queue_type,
        "state": entry.state,
        "status": entry.status,
        "current_stage": entry.current_stage,
        "source_stage": entry.source_stage,
        "priority": entry.priority,
        "priority_reason": entry.priority_reason,
        "queue_time": entry.queue_time,
        "called_at": entry.called_at,
        "started_at": entry.started_at or entry.service_started_at,
        "service_started_at": entry.service_started_at or entry.started_at,
        "completed_at": entry.completed_at,
        "wait_seconds": _wait_seconds(entry, as_of=as_of),
        "service_seconds": entry.service_seconds,
        "hold_reason": entry.hold_reason,
        "hold_ref": entry.hold_ref,
        "hold_age_seconds": _ageing_seconds(entry, as_of=as_of)
        if entry.state in {"ON_HOLD", "READY_TO_RESUME"}
        else None,
        "call_attempts": entry.call_attempts,
        "no_show_count": entry.no_show_count,
        "assigned_user_id": str(entry.assigned_user_id) if entry.assigned_user_id else None,
        "assigned_user_name": entry.assigned_user.get_full_name() if entry.assigned_user_id else None,
        "called_by_id": str(entry.called_by_id or entry.claimed_by_id)
        if (entry.called_by_id or entry.claimed_by_id)
        else None,
        "called_by_name": (
            (entry.called_by or entry.claimed_by).get_full_name()
            if (entry.called_by_id or entry.claimed_by_id)
            else None
        ),
        "served_by_id": str(entry.served_by_id) if entry.served_by_id else None,
        "served_by_name": entry.served_by.get_full_name() if entry.served_by_id else None,
        "handoff_note": entry.notes,
        "version": entry.version,
        "stale": False,
        "stale_review_required": bool(
            entry.visit_id
            and Visit.objects.filter(
                id=entry.visit_id,
                organisation_id=entry.organisation_id,
                facility_id=entry.facility_id,
                stale_review_required=True,
            ).exists()
        ),
        "sla_minutes": None,
        "sla_breached": False,
        "follow_up_required": entry.no_show_count >= 2 or entry.state == "NO_SHOW",
        "final_attempt": entry.call_attempts >= final_attempts,
        "lwbs_action_available": entry.call_attempts >= final_attempts
        and entry.state in {"WAITING", "WAITING_PAYMENT", "NO_SHOW"},
        "emergency_escalation": entry.priority == "EMERGENCY"
        and (
            entry.state == "NO_SHOW"
            or _wait_seconds(entry, as_of=as_of) >= 10 * 60
        ),
    }
    if entry.state in {"WAITING", "WAITING_PAYMENT", "CALLED"}:
        row["sla_minutes"] = WAITING_SLA_MINUTES
    elif entry.state == "IN_SERVICE":
        row["sla_minutes"] = IN_SERVICE_SLA_MINUTES
    elif entry.state in {"ON_HOLD", "READY_TO_RESUME"}:
        row["sla_minutes"] = ON_HOLD_SLA_MINUTES
    if row["sla_minutes"] is not None:
        row["sla_breached"] = row["wait_seconds"] > row["sla_minutes"] * 60
        if entry.state in {"ON_HOLD", "READY_TO_RESUME"}:
            row["sla_breached"] = row["hold_age_seconds"] > row["sla_minutes"] * 60
        row["stale"] = row["sla_breached"]

    if "CLINICIAN" in role_templates:
        assessment = TriageAssessment.objects.filter(
            organisation_id=entry.organisation_id,
            facility_id=entry.facility_id,
            queue_entry_id=entry.id,
        ).first()
        if assessment is not None:
            row["triage_acuity"] = assessment.acuity
    if queue_type.startswith("LAB"):
        # Laboratory order models belong to the later laboratory slice.  The
        # safe query contract exposes a stable empty collection until that
        # owner is enabled; it never substitutes clinical text.
        row["test_names"] = []
    if role_templates.intersection({"RECEPTION_CASHIER", "CASHIER", "OWNER_ADMIN", "FACILITY_ADMIN"}):
        invoice = _invoice_projection(
            organisation=organisation,
            facility=facility,
            visit_id=entry.visit_id,
        )
        if invoice is not None:
            row["invoice_no"] = invoice["invoice_no"]
            row["amount_due"] = invoice["amount_due"]
            row["currency"] = invoice["currency"]
            row["invoice_status"] = invoice["status"]
    return row


def _parse_page(page, page_size):
    try:
        page = max(1, int(page))
        page_size = min(MAX_PAGE_SIZE, max(1, int(page_size)))
    except (TypeError, ValueError):
        raise CanonicalError("INVALID_PAGINATION", "Page and page_size must be positive integers.", status_code=400)
    return page, page_size


def operational_queue_projection(
    *,
    organisation,
    facility,
    actor=None,
    department_id=None,
    queue_type=None,
    queue_date=None,
    states=None,
    status=None,
    page=1,
    page_size=DEFAULT_PAGE_SIZE,
    as_of=None,
    envelope=False,
    include_terminal=False,
    allowed_scopes=None,
):
    """Return a deterministic, role-minimal operational worklist.

    This function only reads.  It never acquires workflow locks, mutates
    QueueEntry, or emits a per-row PHI audit event.
    """

    assert_transaction_active()
    _require_target_reads(organisation)
    as_of = as_of or now()
    page, page_size = _parse_page(page, page_size)
    policy = FacilityWorkflowPolicy.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
    ).first()
    queryset = QueueEntry.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
        visit_id__isnull=False,
    ).select_related(
        "patient",
        "department",
        "assigned_user",
        "called_by",
        "claimed_by",
        "served_by",
    )
    if queue_date:
        queryset = queryset.filter(queue_date=queue_date)
    # The paired grant filter is applied to the organisation/facility queryset
    # before any ordering, counting, or paging. Explicit request filters below
    # can only narrow it.
    queryset = _apply_queue_scope(
        queryset,
        _resolve_scope(
            organisation=organisation,
            facility=facility,
            actor=actor,
            capabilities=QUEUE_READ_CAPABILITIES,
            allowed_scopes=allowed_scopes,
        ),
    )
    if department_id:
        queryset = queryset.filter(department_id=department_id)
    state_values = []
    for value in states or []:
        state_values.extend(str(value).upper().split(","))
    if status:
        state_values.extend(str(status).upper().split(","))
    state_values = [value.strip() for value in state_values if value.strip()]
    if state_values:
        valid = QueueEntry.CANONICAL_STATES | {value for value, _ in QueueEntry.STATUS_CHOICES}
        unknown = [value for value in state_values if value not in valid]
        if unknown:
            raise CanonicalError(
                "INVALID_QUEUE_STATE",
                "The queue state is not supported.",
                status_code=400,
                metadata={"states": sorted(set(unknown))},
            )
        # Legacy shadow values are retained for old rows and are part of the
        # compatibility read; canonical rows use state as authority.
        queryset = queryset.filter(models.Q(state__in=state_values) | models.Q(status__in=state_values))
    elif not include_terminal:
        queryset = queryset.filter(state__in=QueueEntry.ACTIVE_STATES | {"NO_SHOW"})
    if queue_type:
        queryset = queryset.filter(queue_type=str(queue_type).upper())
    assignment_rank = models.Case(
        models.When(assigned_user_id=getattr(actor, "id", None), then=models.Value(0)),
        models.When(assigned_user__isnull=True, then=models.Value(1)),
        default=models.Value(2),
        output_field=models.IntegerField(),
    )
    queryset = queryset.order_by(
        models.Case(
            models.When(priority="EMERGENCY", then=models.Value(0)),
            models.When(priority="URGENT", then=models.Value(1)),
            default=models.Value(2),
            output_field=models.IntegerField(),
        ),
        assignment_rank,
        "queue_time",
        "id",
    )
    all_entries = list(queryset)
    total = len(all_entries)
    start = (page - 1) * page_size
    selected = all_entries[start : start + page_size]
    rows = [
        _row_for_entry(
            entry=entry,
            organisation=organisation,
            facility=facility,
            actor=actor,
            as_of=as_of,
            policy=policy,
        )
        for entry in selected
    ]
    longest_wait = max((_wait_seconds(entry, as_of=as_of) for entry in all_entries), default=0)
    for row in rows:
        row["longest_wait_seconds"] = longest_wait
    if not envelope:
        return rows
    return {
        "entries": rows,
        "count": total,
        "row_count": len(rows),
        # This is a whole-result metric, not a page-local metric.
        "longest_wait_seconds": longest_wait,
        "page": page,
        "page_size": page_size,
        "has_next": start + len(rows) < total,
        "server_time": as_of,
        "refresh_after_seconds": 15,
    }


def queue_priority_projection(
    *, organisation, facility, actor=None, department_id=None, as_of=None, allowed_scopes=None
):
    return operational_queue_projection(
        organisation=organisation,
        facility=facility,
        actor=actor,
        department_id=department_id,
        states=["WAITING_PAYMENT", "WAITING", "CALLED"],
        as_of=as_of,
        envelope=False,
        allowed_scopes=allowed_scopes,
    )


def queue_location_projection(
    *, organisation, facility, visit_id, actor=None, as_of=None, allowed_scopes=None
):
    """Derive current downstream location and any held return obligation."""

    assert_transaction_active()
    _require_target_reads(organisation)
    as_of = as_of or now()
    visit = Visit.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
        id=visit_id,
    ).first()
    if visit is None:
        raise CanonicalError("NOT_FOUND", "The Visit was not found in this facility.", status_code=404)
    # Scope before ranking: a hidden stage must not decide the displayed
    # location or contribute a return obligation.
    entries_queryset = QueueEntry.objects.filter(
        organisation_id=visit.organisation_id,
        facility_id=visit.facility_id,
        visit_id=visit.id,
    ).select_related("patient", "department", "assigned_user", "served_by", "called_by", "claimed_by")
    entries_queryset = _apply_queue_scope(
        entries_queryset,
        _resolve_scope(
            organisation=organisation,
            facility=facility,
            actor=actor,
            capabilities=QUEUE_READ_CAPABILITIES,
            allowed_scopes=allowed_scopes,
        ),
    )
    entries = list(entries_queryset.order_by("queue_time", "sequence", "id"))
    active = [entry for entry in entries if entry.state in QueueEntry.ACTIVE_STATES]
    held = [entry for entry in active if entry.state in {"ON_HOLD", "READY_TO_RESUME"}]
    current_candidates = [entry for entry in active if entry.state not in {"ON_HOLD", "READY_TO_RESUME"}]
    rank = {"IN_SERVICE": 0, "CALLED": 1, "WAITING": 2, "WAITING_PAYMENT": 3}
    current = min(
        current_candidates,
        key=lambda entry: (rank.get(entry.state, 9), entry.queue_time, str(entry.id)),
        default=None,
    )

    def compact(entry):
        row = _row_for_entry(
            entry=entry,
            organisation=organisation,
            facility=facility,
            actor=actor,
            as_of=as_of,
        )
        return {
            "queue_entry_id": row["id"],
            "department_id": row["department_id"],
            "department_name": row["department_name"],
            "queue_type": row["queue_type"],
            "state": row["state"],
            "wait_seconds": row["wait_seconds"],
            "hold_reason": row["hold_reason"],
            "hold_ref": row["hold_ref"],
            "label": f"{row['department_name']} — {row['state'].replace('_', ' ').lower()}",
        }

    if current is not None:
        current_projection = compact(current)
        label = (
            f"Currently: {current_projection['department_name']} — "
            f"{current_projection['state'].replace('_', ' ').lower()}"
        )
    elif visit.state in Visit.ACTIVE_STATES:
        current_projection = None
        label = "In facility — no active queue"
    else:
        current_projection = None
        label = "Not present"
    return {
        "visit_id": str(visit.id),
        "state": "CURRENT" if current_projection else (
            "IN_FACILITY_NO_ACTIVE_QUEUE" if visit.state in Visit.ACTIVE_STATES else "NOT_PRESENT"
        ),
        "label": label,
        "current": current_projection,
        "return_obligations": [compact(entry) for entry in held],
    }


def queue_history_projection(
    *, organisation, facility, visit_id, actor=None, allowed_scopes=None
):
    assert_transaction_active()
    _require_target_reads(organisation)
    visit = Visit.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
        id=visit_id,
    ).first()
    if visit is None:
        raise CanonicalError("NOT_FOUND", "The Visit was not found in this facility.", status_code=404)
    entries = QueueEntry.objects.filter(
        organisation_id=visit.organisation_id,
        facility_id=visit.facility_id,
        visit_id=visit.id,
    ).select_related("department", "called_by", "claimed_by", "served_by", "completed_by", "removed_by")
    # The displayed history is selected from the paired scope, so a hidden
    # stage never appears in the visit timeline.
    entries = _apply_queue_scope(
        entries,
        _resolve_scope(
            organisation=organisation,
            facility=facility,
            actor=actor,
            capabilities=QUEUE_HISTORY_CAPABILITIES,
            allowed_scopes=allowed_scopes,
        ),
    ).order_by("queue_time", "sequence", "id")
    return [
        {
            "id": str(entry.id),
            "queue_label": entry.queue_label,
            "department_id": str(entry.department_id),
            "department_name": entry.department.name,
            "queue_type": entry.queue_type,
            "state": entry.state,
            "status": entry.status,
            "source_stage": entry.source_stage,
            "queue_time": entry.queue_time,
            "called_at": entry.called_at,
            "called_by": str(entry.called_by_id or entry.claimed_by_id)
            if (entry.called_by_id or entry.claimed_by_id)
            else None,
            "started_at": entry.started_at or entry.service_started_at,
            "served_by": str(entry.served_by_id) if entry.served_by_id else None,
            "completed_at": entry.completed_at,
            "completed_by": str(entry.completed_by_id) if entry.completed_by_id else None,
            "wait_seconds": entry.wait_seconds,
            "service_seconds": entry.service_seconds,
            "priority": entry.priority,
            "priority_reason": entry.priority_reason,
            "hold_reason": entry.hold_reason,
            "hold_ref": entry.hold_ref,
            "terminal_reason": entry.terminal_reason,
            "removed_by": str(entry.removed_by_id) if entry.removed_by_id else None,
            "removed_at": entry.removed_at,
            "version": entry.version,
        }
        for entry in entries
    ]


def supervisor_queue_projection(*, organisation, facility, actor=None, as_of=None, allowed_scopes=None):
    pairs = _resolve_scope(
        organisation=organisation,
        facility=facility,
        actor=actor,
        capabilities=QUEUE_SUPERVISOR_CAPABILITIES,
        allowed_scopes=allowed_scopes,
    )
    rows = []
    page = 1
    while True:
        page_rows = operational_queue_projection(
            organisation=organisation,
            facility=facility,
            actor=actor,
            as_of=as_of,
            page=page,
            page_size=MAX_PAGE_SIZE,
            envelope=False,
            allowed_scopes=pairs,
        )
        rows.extend(page_rows)
        if len(page_rows) < MAX_PAGE_SIZE:
            break
        page += 1
    scoped_departments = _scoped_department_ids(pairs)
    departments = Department.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
        is_active=True,
    ).order_by("name", "id")
    if scoped_departments is not None:
        departments = departments.filter(id__in=scoped_departments)
    grouped = {
        str(department.id): {
            "department_id": str(department.id),
            "department_name": department.name,
            "waiting_count": 0,
            "in_service_count": 0,
            "on_hold_count": 0,
            "wait_seconds": [],
            "staff_serving": set(),
        }
        for department in departments
    }
    for row in rows:
        bucket = grouped.setdefault(
            row["department_id"],
            {
                "department_id": row["department_id"],
                "department_name": row["department_name"],
                "waiting_count": 0,
                "in_service_count": 0,
                "on_hold_count": 0,
                "wait_seconds": [],
                "staff_serving": set(),
            },
        )
        if row["state"] in {"WAITING", "WAITING_PAYMENT", "CALLED"}:
            bucket["waiting_count"] += 1
            bucket["wait_seconds"].append(row["wait_seconds"])
        elif row["state"] == "IN_SERVICE":
            bucket["in_service_count"] += 1
            if row["served_by_name"]:
                bucket["staff_serving"].add(row["served_by_name"])
        elif row["state"] in {"ON_HOLD", "READY_TO_RESUME"}:
            bucket["on_hold_count"] += 1
    result = []
    for bucket in grouped.values():
        waits = bucket.pop("wait_seconds")
        staff = bucket.pop("staff_serving")
        result.append(
            {
                **bucket,
                "longest_wait_seconds": max(waits, default=0),
                "median_wait_seconds": int(statistics.median(waits)) if waits else 0,
                "staff_serving": sorted(staff),
                "sla_breached": max(waits, default=0) > WAITING_SLA_MINUTES * 60,
            }
        )
    return sorted(result, key=lambda row: row["department_name"])


def public_board_projection(*, organisation, facility, as_of=None):
    """Public board remains disabled until the exact mode is configured."""

    assert_transaction_active()
    _require_target_reads(organisation)
    policy = FacilityWorkflowPolicy.objects.filter(
        organisation_id=_organisation_id(organisation),
        facility_id=_facility_id(facility),
    ).first()
    if policy is None or not policy.public_board_identity_mode:
        raise CanonicalError(
            "PUBLIC_BOARD_NOT_CONFIGURED",
            "The waiting-room display board is not configured for this facility.",
            status_code=422,
        )
    # The public device-token identity branch is not implemented in S-02.
    # A configured identity mode must not accidentally turn the authenticated
    # staff route into a public board.
    raise CanonicalError(
        "PUBLIC_BOARD_DISABLED",
        "The waiting-room display board remains disabled until device-token authorization is enabled.",
        status_code=503,
        retryable=True,
    )


# Query naming aliases retained for application adapters.
get_operational_queue_projection = operational_queue_projection
query_operational_queue_projection = operational_queue_projection
get_queue_location_projection = queue_location_projection
get_queue_history_projection = queue_history_projection
get_supervisor_queue_projection = supervisor_queue_projection
get_public_board_projection = public_board_projection
