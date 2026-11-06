"""HTTP coordinators for S-02 queue commands and read projections."""

from datetime import date

from django.db import models
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from accounts.models import RolePermission, UserFacilityRole
from application.queue.commands import (
    queue_assign,
    queue_call,
    queue_cancel,
    queue_no_response,
    queue_priority_change,
    queue_requeue,
    queue_takeover,
    queue_transfer,
)
from core.errors import CanonicalError
from core.idempotency import json_safe
from core.permissions import IsTenantMember, queue_scope_pairs, scope_allows
from core.tenant_api import TenantAPIView
from scheduling.operational_queries import (
    operational_queue_projection,
    public_board_projection,
    queue_history_projection,
    queue_location_projection,
    queue_priority_projection,
    supervisor_queue_projection,
)
from scheduling.models import QueueEntry
from tenancy.models import FacilityWorkflowPolicy
from scheduling.serializers import (
    OperationalQueueEnvelopeSerializer,
    OperationalQueueRowSerializer,
    PublicBoardRowSerializer,
    QueueAssignSerializer,
    QueueCallSerializer,
    QueueCancelSerializer,
    QueueHistoryItemSerializer,
    QueueLocationSerializer,
    QueueMutationResponseSerializer,
    QueueNoResponseSerializer,
    QueuePrioritySerializer,
    QueueRequeueSerializer,
    QueueSupervisorRowSerializer,
    QueueSweepSerializer,
    QueueTakeoverSerializer,
    QueueTransferSerializer,
)


QUEUE_READ_CAPABILITIES = ("queue.read", "queue.view")


class QueueCapability(BasePermission):
    """Accept canonical queue capabilities and the S-01 compatibility grants.

    The scope is resolved from the actor's active grants for the facility and,
    when the request names one, the department. Omitted filters never widen a
    department-scoped grant: the handler receives the same resolved scope.
    """

    @staticmethod
    def _scope(request, capabilities):
        return queue_scope_pairs(
            organisation=request.organisation,
            facility=request.facility,
            user=request.user,
            capabilities=capabilities,
        )

    @staticmethod
    def _requested_scope(request):
        """Resolve the command scope from the values the handler will use.

        For writes the body is authoritative; a query string may only supply a
        value the body omits. Naming two different scopes is refused rather
        than silently authorizing the narrower one.
        """

        query_department = request.query_params.get("department_id")
        query_type = request.query_params.get("queue_type")
        if request.method not in {"POST", "PUT", "PATCH"}:
            return query_department, query_type, True
        body_department = request.data.get("department_id")
        body_type = request.data.get("queue_type")
        if body_department and query_department and str(body_department) != str(query_department):
            return None, None, False
        if body_type and query_type and str(body_type).upper() != str(query_type).upper():
            return None, None, False
        return (
            body_department or query_department,
            body_type or query_type,
            True,
        )

    def _has_permission(self, request, view, capabilities=None):
        capabilities = tuple(
            capabilities if capabilities is not None else getattr(view, "queue_capabilities", ()) or ()
        )
        if not capabilities:
            capabilities = (getattr(view, "capability", None),)
        requested_department, requested_type, consistent = self._requested_scope(request)
        if not consistent:
            return False

        target_department = None
        target_type = None
        if request.method in {"POST", "PUT", "PATCH"}:
            target_department = request.data.get("target_department_id")
            target_type = request.data.get("target_queue_type")
            if not target_department:
                target_type = target_type or requested_type

        source_identifier = (
            request.parser_context.get("kwargs", {}).get("pk")
            if getattr(request, "parser_context", None)
            else None
        )
        source_identifier = source_identifier or request.query_params.get("queue_entry_id")
        if not source_identifier and request.method in {"POST", "PUT", "PATCH"}:
            source_identifier = request.data.get("queue_entry_id") or request.data.get("source_queue_entry_id")
        source_department = requested_department
        source_type = requested_type
        if source_identifier:
            source = QueueEntry.objects.filter(
                organisation_id=request.organisation.id,
                facility_id=request.facility.id,
                id=source_identifier,
            ).values("department_id", "queue_type").first()
            if source is not None:
                # A caller may narrow a source request, but may not relabel
                # the authoritative entry to obtain another department/type
                # grant.  A transfer's target is checked separately below.
                if source_department and str(source_department) != str(source["department_id"]):
                    return False
                if source_type and str(source_type).upper() != str(source["queue_type"]).upper():
                    return False
                source_department = source["department_id"]
                source_type = source["queue_type"]

        scope = self._scope(request, capabilities)
        if not scope_allows(scope, source_department, source_type):
            return False
        if target_department and not scope_allows(scope, target_department, target_type):
            return False
        return True

    def has_permission(self, request, view):
        return self._has_permission(request, view)


class PublicBoardCapability(QueueCapability):
    """Keep the disabled default observable without authorizing a live board."""

    def has_permission(self, request, view):
        policy = FacilityWorkflowPolicy.objects.filter(
            organisation_id=request.organisation.id,
            facility_id=request.facility.id,
        ).first()
        capabilities = None
        if policy is None or not policy.public_board_identity_mode:
            # Existing queue readers receive the canonical 422 configuration
            # response.  Once a mode exists, only the explicit board grant is
            # accepted; the device-token branch remains separately blocked.
            capabilities = ("queue.board", "queue.view")
        return self._has_permission(request, view, capabilities=capabilities)


class QueueTenantAPIView(TenantAPIView):
    permission_classes = [IsAuthenticated, IsTenantMember, QueueCapability]
    denial_audit_required = False
    operation_id = None


def _mutation_response(data, *, status_code=status.HTTP_200_OK, result_reference=None):
    body = json_safe(data)
    response = Response(body, status=status_code)
    if isinstance(body, dict) and body.get("version") is not None:
        response["ETag"] = f'"{body["version"]}"'
    # TenantAPIView persists this exact PHI-minimal envelope in PC-048.
    response.idempotency_body = body
    response.result_reference = result_reference
    return response


def _entry_result(entry, *, extra=None):
    data = {
        "queue_entry_id": str(entry.id),
        "state": entry.state,
        "version": entry.version,
        "call_attempts": entry.call_attempts,
        "no_show_count": entry.no_show_count,
        "called_by_id": str(entry.called_by_id) if entry.called_by_id else None,
        "served_by_id": str(entry.served_by_id) if entry.served_by_id else None,
        "assigned_user_id": str(entry.assigned_user_id) if entry.assigned_user_id else None,
        "priority": entry.priority,
    }
    data.update(extra or {})
    return data


def _entry_id(data, *, path_id=None):
    identifier = path_id or data.get("queue_entry_id") or data.get("source_queue_entry_id")
    if identifier is None:
        raise CanonicalError("QUEUE_ENTRY_REQUIRED", "A queue entry is required.", status_code=400)
    return identifier


def _expected_version(request, values, *, required=True):
    """Resolve a body version or strong If-Match precondition consistently."""

    body_version = values.get("expected_version")
    header = request.headers.get("If-Match")
    header_version = None
    if header:
        value = str(header).strip()
        if value.startswith("W/"):
            raise CanonicalError("INVALID_IF_MATCH", "If-Match must be a strong queue version.", status_code=400)
        value = value.strip('"')
        try:
            header_version = int(value)
        except (TypeError, ValueError) as exc:
            raise CanonicalError("INVALID_IF_MATCH", "If-Match must contain the queue version.", status_code=400) from exc
        if header_version < 1:
            raise CanonicalError("INVALID_IF_MATCH", "If-Match must contain a positive queue version.", status_code=400)
    if body_version is not None and header_version is not None and int(body_version) != header_version:
        raise CanonicalError("VERSION_CONFLICT", "The body version and If-Match value do not agree.", status_code=412)
    resolved = header_version if header_version is not None else body_version
    if required and resolved is None:
        raise CanonicalError(
            "PRECONDITION_REQUIRED",
            "A current queue version is required in expected_version or If-Match.",
            status_code=428,
        )
    return resolved


class QueueCallView(QueueTenantAPIView):
    # queue.claim is retained only for the legacy-compatible call command;
    # it is not a substitute grant for assign/transfer/cancel/etc.
    queue_capabilities = ("queue.call", "queue.serve", "queue.claim")
    idempotency_operation = "CMD-013"
    requires_idempotency = True
    request_serializer_class = QueueCallSerializer
    response_serializer_class = QueueMutationResponseSerializer
    response_serializer_classes_by_status = {"POST": {"200": QueueMutationResponseSerializer}}

    def replay_idempotent_response(self, record):
        return record.response_body

    def post(self, request, pk=None):
        serializer = QueueCallSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        if pk is not None:
            values["queue_entry_id"] = pk
        expected_version = _expected_version(
            request,
            values,
            required=bool(values.get("queue_entry_id")),
        )
        entry = queue_call(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            department_id=values.get("department_id"),
            queue_type=values.get("queue_type"),
            expected_version=expected_version,
            ordering_watermark=values.get("ordering_watermark"),
            out_of_order_reason=values.get("out_of_order_reason", ""),
            queue_entry_id=values.get("queue_entry_id"),
            # Authorize exactly the candidate scope the handler will use.
            allowed_scopes=queue_scope_pairs(
                organisation=request.organisation,
                facility=request.facility,
                user=request.user,
                capabilities=self.queue_capabilities,
            ),
        )
        body = {"queue_entry_id": None} if entry is None else _entry_result(entry)
        reference = (
            {"entity_type": "QueueEntry", "entity_id": str(entry.id)}
            if entry is not None
            else None
        )
        return _mutation_response(body, result_reference=reference)


class QueueAssignView(QueueTenantAPIView):
    queue_capabilities = ("queue.assign",)
    idempotency_operation = "CMD-015"
    requires_idempotency = True
    request_serializer_class = QueueAssignSerializer
    response_serializer_class = QueueMutationResponseSerializer
    response_serializer_classes_by_status = {"POST": {"200": QueueMutationResponseSerializer}}

    def replay_idempotent_response(self, record):
        return record.response_body

    def post(self, request, pk=None):
        serializer = QueueAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        expected_version = _expected_version(request, values)
        entry = queue_assign(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=_entry_id(values, path_id=pk),
            target_user_id=values["target_user_id"],
            expected_version=expected_version,
        )
        return _mutation_response(
            _entry_result(entry),
            result_reference={"entity_type": "QueueEntry", "entity_id": str(entry.id)},
        )


class QueueTransferView(QueueTenantAPIView):
    queue_capabilities = ("queue.transfer", "queue.move")
    idempotency_operation = "CMD-018"
    requires_idempotency = True
    request_serializer_class = QueueTransferSerializer
    response_serializer_class = QueueMutationResponseSerializer
    response_serializer_classes_by_status = {"POST": {"200": QueueMutationResponseSerializer}}

    def replay_idempotent_response(self, record):
        return record.response_body

    def post(self, request, pk=None):
        serializer = QueueTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        source_id = _entry_id(values, path_id=pk)
        expected_version = _expected_version(request, values)
        source, destination = queue_transfer(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            source_queue_entry_id=source_id,
            target_department_id=values["target_department_id"],
            target_queue_type=values.get("target_queue_type"),
            handoff_note=values.get("handoff_note", ""),
            reason=values.get("reason", ""),
            expected_version=expected_version,
        )
        body = {
            "source_queue_entry_id": str(source.id),
            "destination_queue_entry_id": str(destination.id),
            "source_state": source.state,
            "destination_state": destination.state,
            "version": source.version,
        }
        return _mutation_response(
            body,
            result_reference={"entity_type": "QueueEntry", "entity_id": str(destination.id)},
        )


class QueuePriorityView(QueueTenantAPIView):
    queue_capabilities = ("queue.priority.set", "queue.priority_change")
    idempotency_operation = "CMD-127"
    requires_idempotency = True
    request_serializer_class = QueuePrioritySerializer
    response_serializer_class = QueueMutationResponseSerializer
    response_serializer_classes_by_status = {"PATCH": {"200": QueueMutationResponseSerializer}}

    def replay_idempotent_response(self, record):
        return record.response_body

    def _mutate(self, request, pk=None):
        serializer = QueuePrioritySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        expected_version = _expected_version(request, values)
        entry = queue_priority_change(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=_entry_id(values, path_id=pk),
            priority=values["priority"],
            reason=values["reason"],
            expected_version=expected_version,
        )
        return _mutation_response(
            _entry_result(entry),
            result_reference={"entity_type": "QueueEntry", "entity_id": str(entry.id)},
        )

    def patch(self, request, pk=None):
        return self._mutate(request, pk=pk)


class QueueNoResponseView(QueueTenantAPIView):
    queue_capabilities = ("queue.no_response", "queue.serve")
    idempotency_operation = "CMD-020"
    requires_idempotency = True
    request_serializer_class = QueueNoResponseSerializer
    response_serializer_class = QueueMutationResponseSerializer
    response_serializer_classes_by_status = {"POST": {"200": QueueMutationResponseSerializer}}

    def replay_idempotent_response(self, record):
        return record.response_body

    def post(self, request, pk=None):
        serializer = QueueNoResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        expected_version = _expected_version(request, values)
        entry = queue_no_response(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=_entry_id(values, path_id=pk),
            outcome=values.get("outcome", "REQUEUE"),
            emergency_acknowledged=values.get("emergency_acknowledged", False),
            expected_version=expected_version,
        )
        return _mutation_response(
            _entry_result(entry),
            result_reference={"entity_type": "QueueEntry", "entity_id": str(entry.id)},
        )


class QueueRequeueView(QueueTenantAPIView):
    queue_capabilities = ("queue.requeue",)
    idempotency_operation = "CMD-021"
    requires_idempotency = True
    request_serializer_class = QueueRequeueSerializer
    response_serializer_class = QueueMutationResponseSerializer
    response_serializer_classes_by_status = {"POST": {"200": QueueMutationResponseSerializer}}

    def replay_idempotent_response(self, record):
        return record.response_body

    def post(self, request, pk=None):
        serializer = QueueRequeueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        expected_version = _expected_version(request, values)
        entry = queue_requeue(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=_entry_id(values, path_id=pk),
            reason=values["reason"],
            expected_version=expected_version,
        )
        return _mutation_response(
            _entry_result(entry),
            result_reference={"entity_type": "QueueEntry", "entity_id": str(entry.id)},
        )


class QueueCancelView(QueueTenantAPIView):
    queue_capabilities = ("queue.remove",)
    idempotency_operation = "CMD-022"
    requires_idempotency = True
    request_serializer_class = QueueCancelSerializer
    response_serializer_class = QueueMutationResponseSerializer
    response_serializer_classes_by_status = {"POST": {"200": QueueMutationResponseSerializer}}

    def replay_idempotent_response(self, record):
        return record.response_body

    def post(self, request, pk=None):
        serializer = QueueCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        if values.get("lwbs") or str(values.get("reason", "")).upper() == "LEFT_WITHOUT_BEING_SEEN":
            raise CanonicalError(
                "WRONG_COMMAND_OWNER",
                "LWBS must be completed by the reception Visit close command.",
                status_code=409,
            )
        expected_version = _expected_version(request, values)
        entry = queue_cancel(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=_entry_id(values, path_id=pk),
            reason=values["reason"],
            lwbs=values.get("lwbs", False),
            expected_version=expected_version,
        )
        return _mutation_response(
            _entry_result(entry),
            result_reference={"entity_type": "QueueEntry", "entity_id": str(entry.id)},
        )


class QueueTakeoverView(QueueTenantAPIView):
    queue_capabilities = ("queue.takeover",)
    idempotency_operation = "CMD-023"
    requires_idempotency = True
    request_serializer_class = QueueTakeoverSerializer
    response_serializer_class = QueueMutationResponseSerializer
    response_serializer_classes_by_status = {"POST": {"200": QueueMutationResponseSerializer}}

    def replay_idempotent_response(self, record):
        return record.response_body

    def post(self, request, pk=None):
        serializer = QueueTakeoverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        expected_version = _expected_version(request, values)
        entry = queue_takeover(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=_entry_id(values, path_id=pk),
            new_user_id=values.get("new_user_id"),
            reason=values["reason"],
            expected_version=expected_version,
            observed_at=values.get("observed_at"),
        )
        return _mutation_response(
            _entry_result(entry),
            result_reference={"entity_type": "QueueEntry", "entity_id": str(entry.id)},
        )


class QueueExpireSweepView(QueueTenantAPIView):
    queue_capabilities = ("ops.run_sweep", "queue.expire_sweep")
    idempotency_operation = "CMD-024"
    requires_idempotency = True
    request_serializer_class = QueueSweepSerializer
    response_serializer_class = QueueMutationResponseSerializer
    response_serializer_classes_by_status = {"POST": {"200": QueueMutationResponseSerializer}}

    def replay_idempotent_response(self, record):
        return record.response_body

    def post(self, request):
        raise CanonicalError(
            "FEATURE_DISABLED",
            "The OD-22 expiry sweep is disabled until its application.operations owner is enabled.",
            status_code=503,
            retryable=True,
        )


class OperationalQueueProjectionView(QueueTenantAPIView):
    queue_capabilities = QUEUE_READ_CAPABILITIES
    operation_id = "queueOperationalProjection"
    response_serializer_class = OperationalQueueEnvelopeSerializer
    response_is_list = False

    def get(self, request):
        state_values = request.query_params.getlist("state")
        status_values = request.query_params.getlist("status")
        include_terminal = request.query_params.get("include_terminal", "false").lower() in {"1", "true", "yes"}
        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 25))
        except ValueError as exc:
            raise CanonicalError("INVALID_PAGINATION", "Page and page_size must be integers.", status_code=400) from exc
        queue_date = request.query_params.get("date")
        if queue_date:
            try:
                queue_date = date.fromisoformat(queue_date)
            except ValueError as exc:
                raise CanonicalError("INVALID_DATE", "The queue date must be YYYY-MM-DD.", status_code=400) from exc
        result = operational_queue_projection(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            department_id=request.query_params.get("department_id"),
            queue_type=request.query_params.get("queue_type"),
            queue_date=queue_date,
            states=state_values,
            status=status_values,
            page=page,
            page_size=page_size,
            include_terminal=include_terminal,
            envelope=True,
        )
        return Response(result)


class QueuePriorityProjectionView(QueueTenantAPIView):
    queue_capabilities = QUEUE_READ_CAPABILITIES
    operation_id = "queuePriorityProjection"
    response_serializer_class = OperationalQueueRowSerializer
    response_is_list = True

    def get(self, request):
        return Response(
            queue_priority_projection(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                department_id=request.query_params.get("department_id"),
            )
        )


class QueueLocationProjectionView(QueueTenantAPIView):
    queue_capabilities = QUEUE_READ_CAPABILITIES
    operation_id = "queueLocationProjection"
    response_serializer_class = QueueLocationSerializer

    def get(self, request, visit_id):
        return Response(
            queue_location_projection(
                organisation=request.organisation,
                facility=request.facility,
                visit_id=visit_id,
                actor=request.user,
            )
        )


class QueueHistoryProjectionView(QueueTenantAPIView):
    queue_capabilities = ("visit.read", "queue.read", "queue.view")
    operation_id = "queueHistoryProjection"
    response_serializer_class = QueueHistoryItemSerializer
    response_is_list = True

    def get(self, request, visit_id):
        return Response(
            queue_history_projection(
                organisation=request.organisation,
                facility=request.facility,
                visit_id=visit_id,
                actor=request.user,
            )
        )


class SupervisorQueueProjectionView(QueueTenantAPIView):
    queue_capabilities = ("queue.read_board", "queue.supervise")
    operation_id = "supervisorQueueProjection"
    response_serializer_class = QueueSupervisorRowSerializer
    response_is_list = True

    def get(self, request):
        return Response(
            supervisor_queue_projection(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
            )
        )


class PublicBoardProjectionView(QueueTenantAPIView):
    queue_capabilities = ("queue.board",)
    permission_classes = [IsAuthenticated, IsTenantMember, PublicBoardCapability]
    operation_id = "publicBoardProjection"
    response_serializer_class = PublicBoardRowSerializer
    response_is_list = True

    def get(self, request):
        return Response(
            public_board_projection(
                organisation=request.organisation,
                facility=request.facility,
            )
        )


__all__ = [
    "OperationalQueueProjectionView",
    "PublicBoardProjectionView",
    "QueueAssignView",
    "QueueCallView",
    "QueueCancelView",
    "QueueExpireSweepView",
    "QueueHistoryProjectionView",
    "QueueLocationProjectionView",
    "QueueNoResponseView",
    "QueuePriorityProjectionView",
    "QueuePriorityView",
    "QueueRequeueView",
    "QueueTakeoverView",
    "QueueTransferView",
    "SupervisorQueueProjectionView",
]
