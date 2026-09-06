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
    system_queue_expire_sweep,
)
from core.errors import CanonicalError
from core.idempotency import json_safe
from core.permissions import IsTenantMember
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
    """Accept canonical queue capabilities and the S-01 compatibility grants."""

    @staticmethod
    def _permission_codes(request, *, department_id=None):
        if request.user.is_superuser:
            return None
        grants = UserFacilityRole.objects.filter(
            organisation_id=request.organisation.id,
            user_id=request.user.id,
            status="ACTIVE",
        ).filter(
            models.Q(facility_id=request.facility.id) | models.Q(facility_id__isnull=True)
        )
        if department_id:
            grants = grants.filter(
                models.Q(department_id=department_id) | models.Q(department_id__isnull=True)
            )
        return set(
            RolePermission.objects.filter(
                organisation_id=request.organisation.id,
                role_id__in=grants.values("role_id"),
            ).values_list("permission__code", flat=True)
        )

    @staticmethod
    def _allows(capabilities, permission_codes, requested_type):
        if permission_codes is None:
            return True
        normalized_codes = {
            str(code).strip().lower() for code in permission_codes
        }
        normalized_type = str(requested_type or "").strip().lower()
        for capability in dict.fromkeys(capabilities):
            if not capability:
                continue
            normalized_capability = str(capability).strip().lower()
            if normalized_capability in normalized_codes:
                return True
            if normalized_type and f"{normalized_capability}:{normalized_type}" in normalized_codes:
                return True
            if not normalized_type and any(
                code.startswith(f"{normalized_capability}:") for code in normalized_codes
            ):
                return True
        return False

    def _has_permission(self, request, view, capabilities=None):
        capabilities = tuple(
            capabilities if capabilities is not None else getattr(view, "queue_capabilities", ()) or ()
        )
        if not capabilities:
            capabilities = (getattr(view, "capability", None),)
        requested_type = request.query_params.get("queue_type")
        requested_department = request.query_params.get("department_id")
        if not requested_type and request.method in {"POST", "PUT", "PATCH"}:
            requested_type = request.data.get("queue_type") or request.data.get("target_queue_type")
            requested_department = (
                request.data.get("department_id")
                or request.data.get("target_department_id")
                or requested_department
            )

        target_department = None
        target_type = None
        if request.method in {"POST", "PUT", "PATCH"}:
            target_department = request.data.get("target_department_id")
            target_type = request.data.get("target_queue_type") or requested_type

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
        if source_identifier and (not source_department or not source_type):
            source = QueueEntry.objects.filter(
                organisation_id=request.organisation.id,
                facility_id=request.facility.id,
                id=source_identifier,
            ).values("department_id", "queue_type").first()
            if source is not None:
                source_department = source_department or source["department_id"]
                source_type = source_type or source["queue_type"]

        scope_requests = [(source_department, source_type)]
        if target_department and target_department != source_department:
            scope_requests.append((target_department, target_type))
        return all(
            self._allows(
                capabilities,
                self._permission_codes(request, department_id=department_id),
                queue_type,
            )
            for department_id, queue_type in scope_requests
        )

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


class QueueCallView(QueueTenantAPIView):
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
        entry = queue_call(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            department_id=values.get("department_id"),
            queue_type=values.get("queue_type"),
            expected_version=values.get("expected_version"),
            ordering_watermark=values.get("ordering_watermark"),
            out_of_order_reason=values.get("out_of_order_reason", ""),
            queue_entry_id=values.get("queue_entry_id"),
        )
        body = {"queue_entry_id": None} if entry is None else _entry_result(entry)
        reference = (
            {"entity_type": "QueueEntry", "entity_id": str(entry.id)}
            if entry is not None
            else None
        )
        return _mutation_response(body, result_reference=reference)


class QueueAssignView(QueueTenantAPIView):
    queue_capabilities = ("queue.assign", "queue.claim")
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
        entry = queue_assign(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=_entry_id(values, path_id=pk),
            target_user_id=values["target_user_id"],
            expected_version=values.get("expected_version"),
        )
        return _mutation_response(
            _entry_result(entry),
            result_reference={"entity_type": "QueueEntry", "entity_id": str(entry.id)},
        )


class QueueTransferView(QueueTenantAPIView):
    queue_capabilities = ("queue.transfer", "queue.move", "queue.claim")
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
        source, destination = queue_transfer(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            source_queue_entry_id=source_id,
            target_department_id=values["target_department_id"],
            target_queue_type=values.get("target_queue_type"),
            handoff_note=values.get("handoff_note", ""),
            reason=values.get("reason", ""),
            expected_version=values.get("expected_version"),
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
    queue_capabilities = ("queue.priority.set", "queue.priority_change", "queue.claim")
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
        entry = queue_priority_change(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=_entry_id(values, path_id=pk),
            priority=values["priority"],
            reason=values["reason"],
            expected_version=values.get("expected_version"),
        )
        return _mutation_response(
            _entry_result(entry),
            result_reference={"entity_type": "QueueEntry", "entity_id": str(entry.id)},
        )

    def patch(self, request, pk=None):
        return self._mutate(request, pk=pk)


class QueueNoResponseView(QueueTenantAPIView):
    queue_capabilities = ("queue.no_response", "queue.serve", "queue.claim")
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
        entry = queue_no_response(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=_entry_id(values, path_id=pk),
            outcome=values.get("outcome", "REQUEUE"),
            emergency_acknowledged=values.get("emergency_acknowledged", False),
            expected_version=values.get("expected_version"),
        )
        return _mutation_response(
            _entry_result(entry),
            result_reference={"entity_type": "QueueEntry", "entity_id": str(entry.id)},
        )


class QueueRequeueView(QueueTenantAPIView):
    queue_capabilities = ("queue.requeue", "queue.claim")
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
        entry = queue_requeue(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=_entry_id(values, path_id=pk),
            reason=values["reason"],
            expected_version=values.get("expected_version"),
        )
        return _mutation_response(
            _entry_result(entry),
            result_reference={"entity_type": "QueueEntry", "entity_id": str(entry.id)},
        )


class QueueCancelView(QueueTenantAPIView):
    queue_capabilities = ("queue.remove", "queue.cancel", "queue.claim")
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
        entry = queue_cancel(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=_entry_id(values, path_id=pk),
            reason=values["reason"],
            lwbs=values.get("lwbs", False),
            expected_version=values.get("expected_version"),
        )
        return _mutation_response(
            _entry_result(entry),
            result_reference={"entity_type": "QueueEntry", "entity_id": str(entry.id)},
        )


class QueueTakeoverView(QueueTenantAPIView):
    queue_capabilities = ("queue.takeover", "queue.claim")
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
        entry = queue_takeover(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            queue_entry_id=_entry_id(values, path_id=pk),
            new_user_id=values.get("new_user_id"),
            reason=values["reason"],
            expected_version=values.get("expected_version"),
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
        serializer = QueueSweepSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = system_queue_expire_sweep(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            **serializer.validated_data,
        )
        return _mutation_response(result.as_dict())


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
