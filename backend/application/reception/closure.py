"""S-08 Visit closure: exact blockers, Visit-first locks and durable denial."""

from dataclasses import dataclass, field

from django.db import transaction

from audit.services import record_event
from billing.models import Invoice
from clinical.models import Encounter
from core.errors import CanonicalError
from core.services import assert_transaction_active
from scheduling.models import QueueEntry, Visit
from scheduling.services import close_visit_state

CLOSURE_PATH_NORMAL = "NORMAL"
FENCED_CLOSURE_PATHS = {
    "DEBT": "OD-P4 debt/credit-sale closure is not enabled.",
    "CREDIT": "OD-P4 credit-sale closure is not enabled.",
    "WAIVER": "BIL-009 waiver policy is unset; waiver closure is not enabled.",
    "OPS": "The OPS closure branch is not supplied.",
    "OD22": "The OD-22 closure branch is not supplied.",
}


@dataclass(frozen=True)
class VisitClosureOutcome:
    visit: Visit
    closed: bool
    already_closed: bool = False
    blockers: list = field(default_factory=list)


def _blocker(code, **payload):
    return {"code": code, **payload}


def collect_visit_blockers(*, organisation, facility, visit):
    """Return the exact blocker set; callers must already hold the Visit lock.

    Queue entries, encounters and invoices are locked in stable ID order after
    the Visit, matching LOCK-01.
    """

    assert_transaction_active()
    queue_entries = list(
        QueueEntry.objects.select_for_update()
        .filter(organisation=organisation, facility=facility, visit=visit)
        .order_by("id")
    )
    encounters = list(
        Encounter.objects.select_for_update()
        .filter(organisation=organisation, facility=facility, visit=visit)
        .order_by("id")
    )
    invoices = list(
        Invoice.objects.select_for_update()
        .filter(organisation=organisation, facility=facility, visit=visit)
        .exclude(status__in=("VOID", "VOIDED"))
        .order_by("id")
    )
    blockers = []
    for entry in queue_entries:
        if entry.state in QueueEntry.ACTIVE_STATES:
            blockers.append(
                _blocker(
                    "ACTIVE_QUEUE_STAGE",
                    queue_entry_id=str(entry.id),
                    queue_type=entry.queue_type,
                    state=entry.state,
                )
            )
    for encounter in encounters:
        if encounter.status == "OPEN":
            blockers.append(
                _blocker(
                    "UNSIGNED_ENCOUNTER",
                    encounter_id=str(encounter.id),
                    clinician_id=str(encounter.clinician_id),
                )
            )
    for invoice in invoices:
        if invoice.balance > 0:
            blockers.append(
                _blocker(
                    "OUTSTANDING_BALANCE",
                    invoice_id=str(invoice.id),
                    invoice_no=invoice.invoice_no,
                    amount=str(invoice.balance),
                    currency=invoice.currency,
                )
            )
    if visit.emergency_setup_pending:
        blockers.append(
            _blocker(
                "EMERGENCY_FINANCIAL_SETUP_PENDING",
                action="complete payer, price and consultation-charge setup",
            )
        )
    return blockers


@transaction.atomic
def visit_close(
    *,
    organisation,
    facility,
    actor,
    visit_id,
    expected_version,
    closure_path=CLOSURE_PATH_NORMAL,
    request=None,
):
    """CMD-008: close one Visit only when every supplied blocker is clear."""

    assert_transaction_active()
    path = str(closure_path or CLOSURE_PATH_NORMAL).upper()
    if path in FENCED_CLOSURE_PATHS:
        error = CanonicalError(
            "PREREQUISITE_MISSING",
            FENCED_CLOSURE_PATHS[path],
            status_code=422,
            metadata={"closure_path": path, "owner_decision": "BP-BL-02/03/04/09"},
        )
        error.audit_denial = True
        error.denial_blockers = ["PREREQUISITE_MISSING"]
        error.denial_targets = {"visit_id": str(visit_id), "closure_path": path}
        error.denial_event_code = "VISIT_CLOSE_DENIED"
        raise error
    if path != CLOSURE_PATH_NORMAL:
        raise CanonicalError(
            "INVALID_STATE", "The requested closure path is not supported.", status_code=409
        )
    visit = Visit.objects.select_for_update().filter(
        id=visit_id, organisation=organisation, facility=facility
    ).first()
    if visit is None:
        raise CanonicalError("VISIT_NOT_FOUND", "Visit was not found.", status_code=404)
    if visit.state == "CANCELLED_ERROR":
        raise CanonicalError(
            "INVALID_STATE", "An erroneous check-in cannot be closed here.", status_code=409
        )
    if visit.state == "CLOSED":
        if expected_version == visit.version:
            return VisitClosureOutcome(visit=visit, closed=True, already_closed=True)
        raise CanonicalError(
            "VERSION_CONFLICT",
            "The Visit was already closed by another request.",
            status_code=409,
            metadata={"state": visit.state, "version": visit.version},
        )
    if expected_version != visit.version:
        raise CanonicalError(
            "VERSION_CONFLICT",
            "The Visit changed; refresh the checklist before closing.",
            status_code=409,
            metadata={"state": visit.state, "version": visit.version},
        )
    blockers = collect_visit_blockers(
        organisation=organisation, facility=facility, visit=visit
    )
    if blockers:
        error = CanonicalError(
            "VISIT_CLOSE_BLOCKED",
            "The Visit has unresolved blockers and was not closed.",
            status_code=409,
            metadata={"blockers": blockers},
        )
        error.audit_denial = True
        error.denial_blockers = [blocker["code"] for blocker in blockers]
        error.denial_targets = {"visit_id": str(visit.id), "visit_version": str(visit.version)}
        error.denial_event_code = "VISIT_CLOSE_DENIED"
        raise error
    visit = close_visit_state(actor=actor, visit=visit, reason="COMPLETED")
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CLOSE",
        entity_type="Visit",
        entity_id=visit.id,
        before={"state": "OPEN", "version": visit.version - 1},
        after={"state": visit.state, "closure_reason": visit.closure_reason},
        event_code="VISIT_CLOSED",
        source_ids={"visit_id": str(visit.id)},
    )
    return VisitClosureOutcome(visit=visit, closed=True, blockers=[])
