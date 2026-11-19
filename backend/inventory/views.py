from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from application.catalogue.imports import import_catalogue
from core.errors import CanonicalError
from core.tenant_api import TenantAPIView
from inventory.models import (
    BatchLocationBalance,
    InventoryThreshold,
    StockAdjustment,
    StockBatch,
    StockLocation,
    StockReceipt,
    Supplier,
)
from inventory.serializers import (
    AdjustmentSerializer,
    CatalogueImportSerializer,
    DisposalSerializer,
    FefoSerializer,
    MovementSerializer,
    ProductCreateSerializer,
    ProductDeactivateSerializer,
    ProductPriceSerializer,
    ProductPriceSetSerializer,
    ProductSerializer,
    QuarantineSerializer,
    StockAdjustmentApproveSerializer,
    StockAdjustmentCreateSerializer,
    StockCountApproveSerializer,
    StockCountOpenSerializer,
    StockCountSubmitSerializer,
    StockLocationSerializer,
    StockLocationWriteSerializer,
    StockReceiptSerializer,
    SupplierSerializer,
    SupplierWriteSerializer,
    ThresholdSerializer,
    ThresholdWriteSerializer,
    TransferSerializer,
)
from inventory.counts import (
    approve_adjustment,
    approve_count,
    count_sheet,
    create_adjustment,
    dispose_stock,
    open_count,
    quarantine_stock,
    submit_count,
)
from inventory.services import (
    adjust_stock,
    configure_location,
    ensure_default_location,
    fefo_selection,
    ledger_movements,
    receive_stock,
    reconcile_ledger,
    stock_batches,
    stock_summary,
    product_ledger,
    export_movements_csv,
    transfer_stock,
    upsert_supplier,
    upsert_threshold,
)
from pharmacy.models import MedicationProduct, ProductPrice
from pharmacy.services import (
    create_product,
    deactivate_product,
    search_products,
    set_product_price,
)


def _require(request, capability):
    if not request.user.has_capability(capability, getattr(request, "facility", None)):
        raise PermissionDenied("You do not have permission to perform this action.")


class ProductListCreateView(TenantAPIView):
    capability = "inventory.read"
    serializer_class = ProductCreateSerializer
    response_serializer_class = ProductSerializer
    response_is_list = {"GET": True, "POST": False}
    idempotency_operation = "CMD-088"

    def get(self, request):
        query = request.query_params.get("q", "")
        prescribing = request.query_params.get("prescribing", "").lower() in {"1", "true", "yes"}
        category = request.query_params.get("category")
        products = search_products(
            organisation=request.organisation,
            facility=request.facility,
            query=query,
            category=category,
            prescribing=prescribing,
        )
        return Response(ProductSerializer(products, many=True).data)

    def post(self, request):
        _require(request, "catalogue.manage")
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        confirm = data.pop("confirm_duplicate", False)
        product = create_product(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            payload=data,
            confirm_duplicate=confirm,
            request=request,
        )
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


class ProductPriceView(TenantAPIView):
    capability = "catalogue.manage"
    serializer_class = ProductPriceSetSerializer
    response_serializer_class = ProductPriceSerializer
    idempotency_operation = "CMD-089"
    requires_idempotency = True

    def post(self, request):
        serializer = ProductPriceSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        price = set_product_price(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(ProductPriceSerializer(price).data, status=status.HTTP_201_CREATED)


class ProductDeactivateView(TenantAPIView):
    capability = "catalogue.manage"
    serializer_class = ProductDeactivateSerializer
    response_serializer_class = ProductSerializer
    idempotency_operation = "CMD-090"
    requires_idempotency = True

    def post(self, request, pk):
        serializer = ProductDeactivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = deactivate_product(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            product_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(ProductSerializer(product).data)


class CatalogueImportView(TenantAPIView):
    capability = "catalogue.import"
    serializer_class = CatalogueImportSerializer
    idempotency_operation = "CMD-091"
    requires_idempotency = True

    def post(self, request):
        serializer = CatalogueImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = import_catalogue(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(result, status=status.HTTP_201_CREATED)


class StockLocationListCreateView(TenantAPIView):
    capability = "inventory.read"
    serializer_class = StockLocationWriteSerializer
    response_serializer_class = StockLocationSerializer
    response_is_list = {"GET": True, "POST": False}
    idempotency_operation = "CMD-104"

    def get(self, request):
        ensure_default_location(
            organisation=request.organisation, facility=request.facility
        )
        locations = StockLocation.objects.filter(
            organisation=request.organisation, facility=request.facility
        ).order_by("code")
        return Response(StockLocationSerializer(locations, many=True).data)

    def post(self, request):
        _require(request, "inventory.configure")
        serializer = StockLocationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = configure_location(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(StockLocationSerializer(location).data, status=status.HTTP_201_CREATED)


class SupplierListCreateView(TenantAPIView):
    capability = "inventory.read"
    serializer_class = SupplierWriteSerializer
    response_serializer_class = SupplierSerializer
    response_is_list = {"GET": True, "POST": False}
    idempotency_operation = "CMD-105"

    def get(self, request):
        suppliers = Supplier.objects.filter(
            organisation=request.organisation, facility=request.facility
        ).order_by("name")
        return Response(SupplierSerializer(suppliers, many=True).data)

    def post(self, request):
        _require(request, "inventory.configure")
        serializer = SupplierWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        supplier = upsert_supplier(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(SupplierSerializer(supplier).data, status=status.HTTP_201_CREATED)


class StockReceiptView(TenantAPIView):
    capability = "inventory.receive"
    serializer_class = StockReceiptSerializer
    idempotency_operation = "CMD-063"
    requires_idempotency = True

    def post(self, request):
        serializer = StockReceiptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        receipt, movements = receive_stock(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            lines=values.pop("lines"),
            **values,
        )
        return Response(
            {
                "id": str(receipt.id),
                "receipt_no": receipt.receipt_no,
                "warning_near_expiry": receipt.warning_near_expiry,
                "movement_count": len(movements),
                "movement_ids": [str(movement.id) for movement in movements],
            },
            status=status.HTTP_201_CREATED,
        )


class StockSummaryView(TenantAPIView):
    capability = "inventory.read"

    def get(self, request):
        rows = stock_summary(
            organisation=request.organisation,
            facility=request.facility,
            query=request.query_params.get("q", ""),
            category=request.query_params.get("category"),
            status=request.query_params.get("status"),
        )
        return Response(rows)


class StockBatchListView(TenantAPIView):
    capability = "inventory.read"

    def get(self, request):
        return Response(
            stock_batches(
                organisation=request.organisation,
                facility=request.facility,
                product_id=request.query_params.get("product_id"),
            )
        )


class FefoView(TenantAPIView):
    capability = "inventory.read"
    serializer_class = FefoSerializer

    def post(self, request):
        serializer = FefoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        proposals = fefo_selection(
            organisation=request.organisation,
            facility=request.facility,
            **serializer.validated_data,
        )
        return Response({"proposals": proposals})


class MovementListView(TenantAPIView):
    capability = "inventory.read"
    response_serializer_class = MovementSerializer
    response_is_list = True

    def get(self, request):
        movements = ledger_movements(
            organisation=request.organisation,
            facility=request.facility,
            batch_id=request.query_params.get("batch_id"),
            movement_type=request.query_params.get("movement_type"),
        )[:500]
        return Response(MovementSerializer(movements, many=True).data)


class StockTransferView(TenantAPIView):
    capability = "inventory.adjust"
    serializer_class = TransferSerializer
    idempotency_operation = "CMD-064"
    requires_idempotency = True

    def post(self, request):
        serializer = TransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        out, incoming = transfer_stock(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            {"out_movement_id": str(out.id), "in_movement_id": str(incoming.id)},
            status=status.HTTP_201_CREATED,
        )


class StockAdjustmentView(TenantAPIView):
    capability = "inventory.adjust"
    serializer_class = StockAdjustmentCreateSerializer
    idempotency_operation = "CMD-067"
    requires_idempotency = True

    def get(self, request):
        adjustments = StockAdjustment.objects.filter(
            organisation=request.organisation, facility=request.facility
        ).order_by("-created_at")
        return Response(
            [
                {
                    "id": str(item.id),
                    "batch_id": str(item.batch_id),
                    "location_id": str(item.location_id),
                    "quantity": str(item.quantity),
                    "reason_code": item.reason_code,
                    "state": item.state,
                    "version": item.version,
                }
                for item in adjustments[:100]
            ]
        )

    def post(self, request):
        serializer = StockAdjustmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        adjustment = create_adjustment(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            {
                "id": str(adjustment.id),
                "state": adjustment.state,
                "quantity": str(adjustment.quantity),
            },
            status=status.HTTP_201_CREATED,
        )


class StockAdjustmentApproveView(TenantAPIView):
    capability = "inventory.approve"
    serializer_class = StockAdjustmentApproveSerializer
    idempotency_operation = "CMD-131"
    requires_idempotency = True

    def post(self, request, pk):
        adjustment = approve_adjustment(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            adjustment_id=pk,
            approver_is_facility_admin=request.user.has_capability(
                "inventory.approve", request.facility
            ),
            request=request,
        )
        return Response({"id": str(adjustment.id), "state": adjustment.state})


class StockCountOpenView(TenantAPIView):
    capability = "inventory.adjust"
    serializer_class = StockCountOpenSerializer
    idempotency_operation = "CMD-065"
    requires_idempotency = True

    def post(self, request):
        serializer = StockCountOpenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = open_count(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            location_id=serializer.validated_data["location_id"],
        )
        return Response(
            {"id": str(count.id), "state": count.state, "version": count.version},
            status=status.HTTP_201_CREATED,
        )


class StockCountDetailView(TenantAPIView):
    capability = "inventory.read"

    def get(self, request, pk):
        from inventory.models import StockCount

        count = StockCount.objects.filter(
            id=pk, organisation=request.organisation, facility=request.facility
        ).first()
        if count is None:
            raise CanonicalError("NOT_FOUND", "Stock count was not found.", 404)
        reveal = request.query_params.get("reveal", "").lower() in {"1", "true", "yes"}
        if reveal and not request.user.has_capability("inventory.approve", request.facility):
            reveal = False
        return Response(
            count_sheet(
                organisation=request.organisation,
                facility=request.facility,
                count=count,
                reveal_expected=reveal or None,
            )
        )


class StockCountSubmitView(TenantAPIView):
    capability = "inventory.adjust"
    serializer_class = StockCountSubmitSerializer
    idempotency_operation = "CMD-065"
    requires_idempotency = True

    def post(self, request, pk):
        serializer = StockCountSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = submit_count(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            count_id=pk,
            expected_version=serializer.validated_data["expected_version"],
            line_counts=serializer.validated_data["lines"],
            request=request,
        )
        return Response({"id": str(count.id), "state": count.state, "version": count.version})


class StockCountApproveView(TenantAPIView):
    capability = "inventory.approve"
    serializer_class = StockCountApproveSerializer
    idempotency_operation = "CMD-066"
    requires_idempotency = True

    def post(self, request, pk):
        serializer = StockCountApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count, adjustments = approve_count(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            count_id=pk,
            expected_version=serializer.validated_data["expected_version"],
            approver_is_facility_admin=request.user.has_capability(
                "inventory.approve", request.facility
            ),
            request=request,
        )
        return Response(
            {
                "id": str(count.id),
                "state": count.state,
                "adjustment_count": len(adjustments),
                "version": count.version,
            }
        )


class QuarantineView(TenantAPIView):
    capability = "inventory.adjust"
    serializer_class = QuarantineSerializer
    idempotency_operation = "CMD-068"
    requires_idempotency = True

    def post(self, request):
        serializer = QuarantineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = quarantine_stock(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            {"id": str(record.id), "quantity": str(record.quantity)},
            status=status.HTTP_201_CREATED,
        )


class DisposalView(TenantAPIView):
    capability = "inventory.adjust"
    serializer_class = DisposalSerializer
    idempotency_operation = "CMD-069"
    requires_idempotency = True

    def post(self, request):
        serializer = DisposalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = dispose_stock(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            {"id": str(record.id), "quantity": str(record.quantity)},
            status=status.HTTP_201_CREATED,
        )


class ThresholdListCreateView(TenantAPIView):
    capability = "inventory.read"
    serializer_class = ThresholdWriteSerializer
    response_serializer_class = ThresholdSerializer
    response_is_list = {"GET": True, "POST": False}
    idempotency_operation = "CMD-111"

    def get(self, request):
        thresholds = InventoryThreshold.objects.filter(
            organisation=request.organisation, facility=request.facility
        ).order_by("product_id", "location_id")
        return Response(ThresholdSerializer(thresholds, many=True).data)

    def post(self, request):
        _require(request, "inventory.configure")
        serializer = ThresholdWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        threshold = upsert_threshold(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(ThresholdSerializer(threshold).data, status=status.HTTP_201_CREATED)


class LedgerReconcileView(TenantAPIView):
    capability = "inventory.reconcile"
    idempotency_operation = "CMD-136"
    requires_idempotency = True

    def post(self, request):
        fact, discrepancies = reconcile_ledger(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
        )
        return Response(
            {
                "event_code": fact.event_code,
                "discrepancy_count": len(discrepancies),
                "discrepancies": discrepancies[:20],
            }
        )


def _ledger_filters(request):
    return {
        "product_id": request.query_params.get("product_id"),
        "date_from": request.query_params.get("date_from") or None,
        "date_to": request.query_params.get("date_to") or None,
        "batch_id": request.query_params.get("batch_id") or None,
        "movement_type": request.query_params.get("movement_type") or None,
    }


class InventoryLedgerView(TenantAPIView):
    capability = "inventory.read"

    def get(self, request):
        filters = _ledger_filters(request)
        if not filters["product_id"]:
            raise CanonicalError("INVALID_INPUT", "A product is required.", 400)
        return Response(
            product_ledger(
                organisation=request.organisation,
                facility=request.facility,
                **filters,
            )
        )


class InventoryLedgerExportView(TenantAPIView):
    capability = "inventory.read"

    def get(self, request):
        filters = _ledger_filters(request)
        if not filters["product_id"]:
            raise CanonicalError("INVALID_INPUT", "A product is required.", 400)
        content = export_movements_csv(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **filters,
        )
        response = HttpResponse(content, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="stock-ledger.csv"'
        return response
