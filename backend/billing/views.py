from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from billing.models import Invoice, Payment, PaymentReceipt, ServiceCatalogItem
from billing.serializers import (
    InvoiceCreateSerializer,
    InvoiceLineCreateSerializer,
    InvoiceLineVoidSerializer,
    InvoiceMutationSerializer,
    InvoiceSerializer,
    PaymentCreateSerializer,
    PaymentMethodConfigureSerializer,
    PaymentMethodSerializer,
    PaymentResultSerializer,
    PaymentReverseResultSerializer,
    PaymentSerializer,
    ReceiptReprintSerializer,
    ReceiptSerializer,
    ServiceCatalogSerializer,
    ShiftCloseSerializer,
    ShiftOpenSerializer,
    ShiftSerializer,
)
from billing.services import (
    add_invoice_line,
    close_shift,
    configure_payment_method,
    confirm_payment,
    create_invoice,
    current_shift,
    open_shift,
    payment_method_options,
    post_payment,
    receipt_by_identity,
    receipt_payload,
    reprint_receipt,
    reverse_payment,
    void_invoice_line,
)
from core.errors import CanonicalError
from core.tenant_api import TenantAPIView

INVOICE_STATUSES = {choice[0] for choice in Invoice.STATUS_CHOICES}


class ServiceCatalogView(TenantAPIView):
    capability = "billing.invoice.create"
    response_serializer_class = ServiceCatalogSerializer
    response_is_list = True

    def get(self, request):
        services = ServiceCatalogItem.objects.filter(organisation=request.organisation, is_active=True).prefetch_related("prices")
        return Response(ServiceCatalogSerializer(services, many=True).data)


class InvoiceListCreateView(TenantAPIView):
    capability = "billing.invoice.create"
    serializer_class = InvoiceCreateSerializer
    response_serializer_classes = {"GET": InvoiceSerializer, "POST": InvoiceSerializer}
    response_is_list = {"GET": True, "POST": False}

    def get(self, request):
        invoices = Invoice.objects.filter(
            organisation=request.organisation, facility=request.facility
        ).prefetch_related("items", "payments__allocations").select_related("patient").order_by("-created_at")

        statuses = []
        for value in request.query_params.getlist("status"):
            statuses.extend(part.strip().upper() for part in value.split(",") if part.strip())
        if statuses:
            unknown = [value for value in statuses if value not in INVOICE_STATUSES]
            if unknown:
                return Response(
                    {"detail": "Unknown invoice status: " + ", ".join(unknown) + "."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            invoices = invoices.filter(status__in=statuses)

        if request.query_params.get("outstanding", "").lower() in {"1", "true", "yes"}:
            invoices = invoices.filter(status__in=["ISSUED", "PARTIALLY_PAID"])

        search = request.query_params.get("q", "").strip()
        if search:
            invoices = invoices.filter(
                models.Q(invoice_no__icontains=search)
                | models.Q(patient__patient_no__icontains=search)
                | models.Q(patient__first_name__icontains=search)
                | models.Q(patient__last_name__icontains=search)
            )

        return Response(InvoiceSerializer(invoices[:100], many=True).data)

    def post(self, request):
        serializer = InvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invoice = create_invoice(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                request=request,
                **serializer.validated_data,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)


class InvoiceByVisitView(TenantAPIView):
    """Read the one Invoice a Visit already owns.

    Check-in issues the consultation Invoice against the Visit, and the signed
    consultation must open that same record instead of creating a new charge.
    This is a read only: it exposes no clinical detail and grants no capability
    beyond the invoice read already used for invoice detail.
    """

    capability = "billing.invoice.create"
    response_serializer_class = InvoiceSerializer
    operation_id = "retrieveVisitInvoice"

    def get(self, request, visit_id):
        invoice = (
            Invoice.objects.filter(
                organisation=request.organisation,
                facility=request.facility,
                visit_id=visit_id,
                status__in=["ISSUED", "PARTIALLY_PAID", "PAID"],
            )
            .select_related("patient")
            .prefetch_related("items", "payments__allocations")
            .order_by("created_at", "id")
            .first()
        )
        if invoice is None:
            raise Http404
        return Response(InvoiceSerializer(invoice).data)


class InvoiceDetailView(TenantAPIView):
    capability = "billing.invoice.create"
    response_serializer_class = InvoiceSerializer

    def get(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.prefetch_related("items", "payments__allocations"),
            id=pk,
            organisation=request.organisation,
            facility=request.facility,
        )
        return Response(InvoiceSerializer(invoice).data)


class InvoicePaymentView(TenantAPIView):
    """Compatibility single-invoice route; the canonical command is below."""

    capability = "billing.payment.record"
    serializer_class = PaymentCreateSerializer
    response_serializer_class = PaymentSerializer
    idempotency_operation = "CMD-075"
    operation_id = "createInvoicePaymentLegacy"

    def post(self, request, pk):
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = post_payment(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                invoice_id=pk,
                request=request,
                amount=serializer.validated_data["amount"],
                method=serializer.validated_data["method"],
                reference=serializer.validated_data.get("reference", ""),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class InvoiceCanonicalPaymentView(TenantAPIView):
    """CMD-075/CMD-080: shift-bound payment with exact allocations and receipt."""

    capability = "billing.payment.record"
    serializer_class = PaymentCreateSerializer
    response_serializer_class = PaymentResultSerializer
    idempotency_operation = "CMD-075"
    requires_idempotency = True
    operation_id = "createInvoicePayment"

    def post(self, request, pk):
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        allocations = serializer.validated_data.pop("allocations", None)
        outcome = confirm_payment(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            invoice_id=pk,
            allocations=allocations,
            request=request,
            require_shift=True,
            **serializer.validated_data,
        )
        return Response(
            {
                "id": str(outcome.payment.id),
                "receipt_no": outcome.receipt.receipt_no,
                "receipt_id": str(outcome.receipt.id),
                "amount": str(outcome.payment.amount),
                "method": outcome.payment.method,
                "status": outcome.payment.status,
                "allocations": [
                    {
                        "invoice_id": str(allocation.invoice_id),
                        "amount": str(allocation.amount),
                    }
                    for allocation in outcome.payment.allocations.order_by("invoice_id")
                ],
                "invoices": [
                    {
                        "id": str(invoice.id),
                        "status": invoice.status,
                        "total": str(invoice.total),
                        "balance": str(invoice.balance),
                    }
                    for invoice in outcome.invoices
                ],
            },
            status=status.HTTP_201_CREATED,
        )


class InvoiceReceiptView(TenantAPIView):
    capability = "billing.receipt.print"
    response_serializer_class = ReceiptSerializer

    def get(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.prefetch_related("items", "payments"),
            id=pk,
            organisation=request.organisation,
            facility=request.facility,
        )
        receipt_id = request.query_params.get("receipt_id")
        payment_id = request.query_params.get("payment_id")
        if receipt_id or payment_id:
            if receipt_id:
                receipt = PaymentReceipt.objects.filter(
                    organisation=request.organisation,
                    facility=request.facility,
                    id=receipt_id,
                    payment__invoice=invoice,
                ).first()
            else:
                receipt = PaymentReceipt.objects.filter(
                    organisation=request.organisation,
                    facility=request.facility,
                    payment_id=payment_id,
                    payment__invoice=invoice,
                ).first()
            if receipt is None:
                raise CanonicalError("RECEIPT_NOT_FOUND", "Receipt was not found for this invoice.", 404)
            return Response(receipt_payload(receipt))
        payment = invoice.payments.filter(status__in=Payment.EFFECTIVE_STATUSES).order_by("-received_at").first()
        if payment is None:
            return Response({"detail": "No posted payment exists for this invoice."}, status=status.HTTP_404_NOT_FOUND)
        receipt = PaymentReceipt.objects.filter(
            organisation=request.organisation,
            facility=request.facility,
            payment=payment,
        ).first()
        if receipt is None:
            return Response(
                {"detail": "The receipt identity for this payment is not available."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(receipt_payload(receipt))


class ReceiptDetailView(TenantAPIView):
    capability = "billing.receipt.print"
    response_serializer_class = ReceiptSerializer

    def get(self, request, pk):
        receipt = receipt_by_identity(
            organisation=request.organisation,
            facility=request.facility,
            receipt_id=pk,
        )
        return Response(receipt_payload(receipt))


class ReceiptByNumberView(TenantAPIView):
    capability = "billing.receipt.print"
    response_serializer_class = ReceiptSerializer

    def get(self, request, receipt_no):
        receipt = receipt_by_identity(
            organisation=request.organisation,
            facility=request.facility,
            receipt_no=receipt_no,
        )
        return Response(receipt_payload(receipt))


class ReceiptReprintView(TenantAPIView):
    """CMD-081: idempotent reprint intent; the printable body is read by identity."""

    capability = "billing.receipt.print"
    idempotency_operation = "CMD-081"
    requires_idempotency = True
    response_serializer_class = ReceiptReprintSerializer

    def post(self, request, pk):
        receipt = reprint_receipt(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            receipt_id=pk,
            request=request,
        )
        return Response(
            {
                "id": str(receipt.id),
                "receipt_no": receipt.receipt_no,
                "print_count": receipt.print_count,
                "last_printed_at": receipt.last_printed_at,
            },
            status=status.HTTP_200_OK,
        )


class PaymentReverseView(TenantAPIView):
    capability = "billing.payment.reverse"
    idempotency_operation = "CMD-076"
    requires_idempotency = True
    response_serializer_class = PaymentReverseResultSerializer

    def post(self, request, pk):
        reason = request.data.get("reason", "")
        payment, invoices = reverse_payment(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            payment_id=pk,
            reason=reason,
            request=request,
        )
        return Response(
            {
                "id": str(payment.id),
                "receipt_no": payment.receipt_no,
                "status": payment.status,
                "invoices": [
                    {
                        "id": str(invoice.id),
                        "status": invoice.status,
                        "balance": str(invoice.balance),
                    }
                    for invoice in invoices
                ],
            },
            status=status.HTTP_200_OK,
        )


class ShiftOpenView(TenantAPIView):
    capability = "billing.payment.record"
    serializer_class = ShiftOpenSerializer
    response_serializer_class = ShiftSerializer
    idempotency_operation = "CMD-082"

    def post(self, request):
        serializer = ShiftOpenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shift = open_shift(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(ShiftSerializer(shift).data, status=status.HTTP_201_CREATED)


class ShiftCurrentView(TenantAPIView):
    capability = "billing.payment.record"
    response_serializer_class = ShiftSerializer

    def get(self, request):
        shift = current_shift(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
        )
        if shift is None:
            return Response({"shift": None})
        return Response({"shift": ShiftSerializer(shift).data})


class ShiftCloseView(TenantAPIView):
    capability = "billing.payment.record"
    serializer_class = ShiftCloseSerializer
    response_serializer_class = ShiftSerializer
    idempotency_operation = "CMD-083"
    requires_idempotency = True

    def post(self, request, pk):
        serializer = ShiftCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shift = close_shift(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            shift_id=pk,
            declared_cash=serializer.validated_data["declared_cash"],
            request=request,
        )
        shift.close_reason = serializer.validated_data.get("reason", "")
        shift.save(update_fields=["close_reason", "updated_at"])
        return Response(ShiftSerializer(shift).data)


class PaymentMethodListView(TenantAPIView):
    capability = "billing.payment.record"
    serializer_class = PaymentMethodConfigureSerializer
    response_serializer_class = PaymentMethodSerializer
    response_is_list = True

    def _require_configure(self, request):
        if not request.user.has_capability(
            "billing.payment_method.configure", getattr(request, "facility", None)
        ):
            raise PermissionDenied("You do not have permission to configure payment methods.")

    def get(self, request):
        return Response(
            payment_method_options(
                organisation=request.organisation, facility=request.facility
            )
        )

    def post(self, request):
        self._require_configure(request)
        serializer = PaymentMethodConfigureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        configure_payment_method(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            payment_method_options(
                organisation=request.organisation, facility=request.facility
            ),
            status=status.HTTP_201_CREATED,
        )


class InvoiceLineCreateView(TenantAPIView):
    capability = "billing.invoice.create"
    serializer_class = InvoiceLineCreateSerializer
    response_serializer_class = InvoiceMutationSerializer
    idempotency_operation = "CMD-073"

    def post(self, request, pk):
        serializer = InvoiceLineCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data.get("manual") and not request.user.has_capability(
            "billing.manual_line", getattr(request, "facility", None)
        ):
            raise PermissionDenied("You do not have permission to add a manual line.")
        line, invoice = add_invoice_line(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            invoice_id=pk,
            request=request,
            **data,
        )
        return Response(InvoiceMutationSerializer(invoice).data, status=status.HTTP_201_CREATED)


class InvoiceLineVoidView(TenantAPIView):
    capability = "billing.invoice.create"
    serializer_class = InvoiceLineVoidSerializer
    response_serializer_class = InvoiceMutationSerializer
    idempotency_operation = "CMD-074"

    def post(self, request, pk, line_id):
        serializer = InvoiceLineVoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _line, invoice, _changed = void_invoice_line(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            invoice_id=pk,
            line_id=line_id,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response(InvoiceMutationSerializer(invoice).data)
