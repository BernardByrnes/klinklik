"""Object-scope permissions for the versioned triage routes."""

from rest_framework.permissions import BasePermission

from clinical.models import TriageRecord
from core.permissions import coerce_queue_identifier, queue_scope_pairs, scope_allows
from scheduling.models import QueueEntry


class TriageMethodCapability(BasePermission):
    """Check the read or write triage capability for the request method."""

    def has_permission(self, request, view):
        if request.method in {"POST", "PUT", "PATCH"}:
            capability = getattr(view, "triage_write_capability", "") or ""
        else:
            capability = getattr(view, "triage_read_capability", "") or ""
        if not capability:
            return True
        return request.user.has_capability(capability, request.facility)


class TriageRecordScopePermission(BasePermission):
    """Authorize a triage record by its Visit's TRIAGE source pair.

    The record carries no department, so scope comes from the triage source
    QueueEntry of the same Visit. The same capability set that admitted the
    route resolves the grant pairs; read and write routes declare their own.
    """

    def has_permission(self, request, view):
        write = request.method in {"POST", "PUT", "PATCH"}
        attribute = "triage_write_capabilities" if write else "triage_read_capabilities"
        capabilities = tuple(
            getattr(view, attribute, ())
            or getattr(view, "triage_capabilities", ())
            or (getattr(view, "capability", None),)
        )
        if not any(capabilities):
            return True
        parser_context = getattr(request, "parser_context", None) or {}
        kwargs = parser_context.get("kwargs") or {}
        identifier = kwargs.get("pk") or kwargs.get("record_id")
        if identifier is None:
            return True
        record_id = coerce_queue_identifier(identifier)
        if record_id is None:
            return True
        record = TriageRecord.objects.filter(
            organisation_id=request.organisation.id,
            facility_id=request.facility.id,
            id=record_id,
        ).values("visit_id").first()
        if record is None:
            # The command owns the missing-record contract; no scope is
            # disclosed for an unavailable row.
            return True
        source = QueueEntry.objects.filter(
            organisation_id=request.organisation.id,
            facility_id=request.facility.id,
            visit_id=record["visit_id"],
            queue_type="TRIAGE",
        ).values("department_id", "queue_type").first()
        if source is None:
            return False
        pairs = queue_scope_pairs(
            organisation=request.organisation,
            facility=request.facility,
            user=request.user,
            capabilities=capabilities,
        )
        return scope_allows(pairs, source["department_id"], source["queue_type"])
