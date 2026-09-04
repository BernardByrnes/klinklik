from django.db import models
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from billing.models import Invoice, Payment, ServiceCatalogItem
from billing.serializers import (
    InvoiceCreateSerializer,
    InvoiceSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
    ReceiptSerializer,
    ServiceCatalogSerializer,
)
from billing.services import create_invoice, post_payment
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
        ).prefetch_related("items", "payments").select_related("patient").order_by("-created_at")

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


class InvoiceDetailView(TenantAPIView):
    capability = "billing.invoice.create"
    response_serializer_class = InvoiceSerializer

    def get(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.prefetch_related("items", "payments"),
            id=pk,
            organisation=request.organisation,
            facility=request.facility,
        )
        return Response(InvoiceSerializer(invoice).data)


class InvoicePaymentView(TenantAPIView):
    capability = "billing.payment.record"
    serializer_class = PaymentCreateSerializer
    response_serializer_class = PaymentSerializer

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
                **serializer.validated_data,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


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
        payment = invoice.payments.filter(status="POSTED").order_by("-received_at").first()
        if payment is None:
            return Response({"detail": "No posted payment exists for this invoice."}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "receipt_no": payment.receipt_no,
            "invoice_no": invoice.invoice_no,
            "patient_name": invoice.patient.display_name,
            "patient_no": invoice.patient.patient_no,
            "amount": str(payment.amount),
            "currency": invoice.currency,
            "method": payment.method,
            "reference": payment.reference,
            "received_at": payment.received_at,
            "invoice_total": str(invoice.total),
            "invoice_balance": str(invoice.balance),
            "printable_text": f"{request.organisation.name} | Receipt {payment.receipt_no} | {invoice.patient.display_name} | {invoice.currency} {payment.amount}",
        })
