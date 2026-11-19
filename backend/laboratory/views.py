from rest_framework import status
from rest_framework.response import Response

from core.errors import CanonicalError
from core.tenant_api import TenantAPIView
from laboratory.models import LabOrderItem, LabTestDefinition
from laboratory.serializers import (
    LabAmendSerializer,
    LabCancelSerializer,
    LabItemSerializer,
    LabOrderCreateSerializer,
    LabRejectSerializer,
    LabResultSaveSerializer,
    LabTestConfigureSerializer,
    LabTestSerializer,
)
from laboratory.services import (
    amend_result,
    cancel_item,
    collect_item,
    configure_test,
    create_order,
    encounter_lab_status,
    order_status,
    released_results_for_encounter,
    reject_sample,
    release_result,
    save_result,
    worklists,
)


class LabTestListCreateView(TenantAPIView):
    capability = "inventory.read"
    serializer_class = LabTestConfigureSerializer
    response_serializer_class = LabTestSerializer
    response_is_list = {"GET": True, "POST": False}
    idempotency_operation = "CMD-108"

    def get(self, request):
        tests = LabTestDefinition.objects.filter(
            organisation=request.organisation, facility=request.facility
        ).order_by("name")
        return Response(LabTestSerializer(tests, many=True).data)

    def post(self, request):
        if not request.user.has_capability("inventory.configure", request.facility):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to configure laboratory tests.")
        serializer = LabTestConfigureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        test = configure_test(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(LabTestSerializer(test).data, status=status.HTTP_201_CREATED)


class LabOrderCreateView(TenantAPIView):
    capability = "lab.order.create"
    serializer_class = LabOrderCreateSerializer
    idempotency_operation = "CMD-040"
    requires_idempotency = True

    def post(self, request):
        serializer = LabOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order, items = create_order(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            {
                "id": str(order.id),
                "status": order_status(order),
                "items": [
                    {
                        "id": str(item.id),
                        "test_id": str(item.test_id),
                        "state": item.state,
                        "invoice_line_id": str(item.invoice_line_id) if item.invoice_line_id else None,
                    }
                    for item in items
                ],
            },
            status=status.HTTP_201_CREATED,
        )


class LabWorklistView(TenantAPIView):
    capability = "inventory.read"

    def get(self, request):
        return Response(
            worklists(organisation=request.organisation, facility=request.facility)
        )


class LabItemCollectView(TenantAPIView):
    capability = "lab.result.entry"
    idempotency_operation = "CMD-042"
    requires_idempotency = True

    def post(self, request, pk):
        item = collect_item(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            item_id=pk,
            request=request,
        )
        return Response(LabItemSerializer(item).data)


class LabItemRejectView(TenantAPIView):
    capability = "lab.result.entry"
    serializer_class = LabRejectSerializer
    idempotency_operation = "CMD-043"
    requires_idempotency = True

    def post(self, request, pk):
        serializer = LabRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rejection = reject_sample(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            item_id=pk,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response({"id": str(rejection.id), "item_id": str(rejection.item_id)})


class LabResultSaveView(TenantAPIView):
    capability = "lab.result.entry"
    serializer_class = LabResultSaveSerializer
    idempotency_operation = "CMD-044"
    requires_idempotency = True

    def patch(self, request, pk):
        serializer = LabResultSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result, version = save_result(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            item_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            {
                "id": str(result.id),
                "state": result.state,
                "version_no": version.version_no,
                "content_hash": version.content_hash,
            },
            status=status.HTTP_201_CREATED,
        )


class LabResultReleaseView(TenantAPIView):
    capability = "lab.result.verify"
    idempotency_operation = "CMD-046"
    requires_idempotency = True

    def post(self, request, pk):
        result, version = release_result(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            item_id=pk,
            request=request,
        )
        return Response(
            {
                "id": str(result.id),
                "state": result.state,
                "version_no": version.version_no,
                "self_verified": result.self_verified,
            }
        )


class LabResultAmendView(TenantAPIView):
    capability = "lab.result.amend"
    serializer_class = LabAmendSerializer
    idempotency_operation = "CMD-049"
    requires_idempotency = True

    def post(self, request, pk):
        serializer = LabAmendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result, version = amend_result(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            item_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            {
                "id": str(result.id),
                "state": result.state,
                "version_no": version.version_no,
                "content_hash": version.content_hash,
            },
            status=status.HTTP_201_CREATED,
        )


class LabItemCancelView(TenantAPIView):
    capability = "lab.cancel"
    serializer_class = LabCancelSerializer
    idempotency_operation = "CMD-047"
    requires_idempotency = True

    def post(self, request, pk):
        serializer = LabCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item, changed = cancel_item(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            item_id=pk,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response({"id": str(item.id), "state": item.state, "changed": changed})


class LabEncounterResultsView(TenantAPIView):
    capability = "encounter.read"

    def get(self, request, encounter_id):
        results = released_results_for_encounter(
            organisation=request.organisation,
            facility=request.facility,
            encounter_id=encounter_id,
            actor=request.user,
            request=request,
        )
        return Response(
            {
                "results": results,
                "status": encounter_lab_status(
                    organisation=request.organisation,
                    facility=request.facility,
                    encounter_id=encounter_id,
                ),
            }
        )
