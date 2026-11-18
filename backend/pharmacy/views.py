from rest_framework import status
from rest_framework.response import Response

from core.tenant_api import TenantAPIView
from pharmacy.dispensing import (
    cancel_prescription,
    claim_prescription,
    confirm_dispense,
    counselling_projection,
    create_otc_sale,
    prepare_dispense,
    queue,
    record_not_dispensed,
    save_draft,
)
from pharmacy.models import Dispense, OTCSale
from pharmacy.serializers import (
    DispensePrepareSerializer,
    InstructionTemplateSerializer,
    NotDispensedSerializer,
    OTCSaleCreateSerializer,
    PrescriptionCancelSerializer,
    PrescriptionDraftSerializer,
)


def prescription_payload(prescription):
    return {
        "id": str(prescription.id),
        "encounter_id": str(prescription.encounter_id),
        "patient_id": str(prescription.patient_id),
        "patient_name": prescription.patient.display_name,
        "status": prescription.status,
        "version": prescription.version,
        "created_at": prescription.created_at,
        "items": [
            {
                "id": str(item.id),
                "product_id": str(item.product_id) if item.product_id else None,
                "medicine_name": item.medicine_name,
                "dose_amount": str(item.dose_amount),
                "dose_unit": item.dose_unit,
                "route": item.route,
                "frequency": item.frequency,
                "duration_value": item.duration_value,
                "duration_unit": item.duration_unit,
                "quantity": str(item.quantity),
                "instructions": item.instructions,
                "external": item.external,
                "state": item.state,
            }
            for item in prescription.items.order_by("created_at", "id")
        ],
    }


def dispense_payload(dispense):
    return {
        "id": str(dispense.id),
        "prescription_id": (
            str(dispense.prescription_id) if dispense.prescription_id else None
        ),
        "visit_id": str(dispense.visit_id) if dispense.visit_id else None,
        "status": dispense.status,
        "total": str(dispense.total),
        "currency": dispense.currency,
        "version": dispense.version,
        "lines": [
            {
                "id": str(line.id),
                "prescription_item_id": (
                    str(line.prescription_item_id)
                    if line.prescription_item_id
                    else None
                ),
                "product_id": str(line.product_id),
                "product_name": line.product.generic_name,
                "batch_id": str(line.batch_id),
                "batch_no": line.batch.batch_no,
                "expiry_date": line.batch.expiry_date.isoformat(),
                "location_id": str(line.location_id),
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "amount": str(line.amount),
                "substitution_reason": line.substitution_reason,
                "prescriber_consulted": line.prescriber_consulted,
                "prescriber_consulted_name": line.prescriber_consulted_name,
            }
            for line in dispense.lines.select_related("product", "batch").order_by(
                "id"
            )
        ],
    }


def otc_payload(sale):
    return {
        "id": str(sale.id),
        "patient_id": str(sale.patient_id) if sale.patient_id else None,
        "customer_name": sale.customer_name,
        "total": str(sale.total),
        "currency": sale.currency,
        "method": sale.method,
        "reference": sale.reference,
        "state": sale.state,
        "sold_at": sale.sold_at,
        "lines": [
            {
                "id": str(line.id),
                "product_id": str(line.product_id),
                "product_name": line.product.generic_name,
                "batch_id": str(line.batch_id),
                "batch_no": line.batch.batch_no,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "amount": str(line.amount),
            }
            for line in sale.lines.select_related("product", "batch").order_by("id")
        ],
    }


class PrescriptionDraftView(TenantAPIView):
    capability = "pharmacy.prescribe"
    serializer_class = PrescriptionDraftSerializer
    idempotency_operation = "CMD-052"
    requires_idempotency = True

    def patch(self, request):
        serializer = PrescriptionDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prescription = save_draft(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(prescription_payload(prescription), status=status.HTTP_200_OK)


class PrescriptionQueueView(TenantAPIView):
    capability = "pharmacy.queue.view"

    def get(self, request):
        payload = queue(organisation=request.organisation, facility=request.facility)
        payload["counselling"] = counselling_projection(
            organisation=request.organisation, facility=request.facility
        )
        return Response(payload)


class PrescriptionClaimView(TenantAPIView):
    capability = "pharmacy.dispense"
    idempotency_operation = "CMD-055"
    requires_idempotency = True

    def post(self, request, pk):
        claim, created = claim_prescription(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            prescription_id=pk,
            request=request,
        )
        return Response(
            {
                "id": str(claim.id),
                "prescription_id": str(claim.prescription_id),
                "claimed_by": str(claim.claimed_by_id),
                "created": created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class DispensePrepareView(TenantAPIView):
    capability = "pharmacy.dispense"
    serializer_class = DispensePrepareSerializer
    idempotency_operation = "CMD-057"
    requires_idempotency = True

    def post(self, request, prescription_id):
        serializer = DispensePrepareSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dispense = prepare_dispense(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            prescription_id=prescription_id,
            request=request,
            **serializer.validated_data,
        )
        return Response(dispense_payload(dispense), status=status.HTTP_201_CREATED)


class DispenseConfirmView(TenantAPIView):
    capability = "pharmacy.dispense"
    idempotency_operation = "CMD-058"
    requires_idempotency = True

    def post(self, request, pk):
        dispense = confirm_dispense(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            dispense_id=pk,
            request=request,
        )
        return Response(dispense_payload(dispense))


class DispenseDetailView(TenantAPIView):
    capability = "pharmacy.queue.view"

    def get(self, request, pk):
        dispense = (
            Dispense.objects.filter(
                id=pk,
                organisation=request.organisation,
                facility=request.facility,
            )
            .select_related("prescription", "visit")
            .first()
        )
        if dispense is None:
            from core.errors import CanonicalError

            raise CanonicalError("NOT_FOUND", "Dispense was not found.", status_code=404)
        return Response(dispense_payload(dispense))


class PrescriptionCancelView(TenantAPIView):
    capability = "pharmacy.prescribe"
    serializer_class = PrescriptionCancelSerializer
    idempotency_operation = "CMD-059"
    requires_idempotency = True

    def post(self, request, pk):
        serializer = PrescriptionCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prescription = cancel_prescription(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            prescription_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(prescription_payload(prescription))


class PrescriptionItemNotDispensedView(TenantAPIView):
    capability = "pharmacy.dispense"
    serializer_class = NotDispensedSerializer
    idempotency_operation = "CMD-060"
    requires_idempotency = True

    def post(self, request, item_id):
        serializer = NotDispensedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = record_not_dispensed(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            prescription_item_id=item_id,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            {
                "id": str(item.id),
                "prescription_id": str(item.prescription_id),
                "state": item.state,
                "not_dispensed_reason": item.not_dispensed_reason,
            }
        )


class ProductInstructionTemplateView(TenantAPIView):
    capability = "catalogue.manage"
    serializer_class = InstructionTemplateSerializer
    idempotency_operation = "CMD-110"
    requires_idempotency = True

    def patch(self, request, pk):
        from pharmacy.services import set_instruction_template

        serializer = InstructionTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = set_instruction_template(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            product_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            {
                "id": str(product.id),
                "instructions_template": product.instructions_template,
                "version": product.version,
            }
        )


class OTCSaleCreateView(TenantAPIView):
    capability = "pharmacy.otc.sell"
    serializer_class = OTCSaleCreateSerializer
    idempotency_operation = "CMD-113"
    requires_idempotency = True

    def post(self, request):
        serializer = OTCSaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = create_otc_sale(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(otc_payload(sale), status=status.HTTP_201_CREATED)


class OTCSaleListView(TenantAPIView):
    capability = "pharmacy.queue.view"

    def get(self, request):
        sales = (
            OTCSale.objects.filter(
                organisation=request.organisation, facility=request.facility
            )
            .select_related("patient")
            .order_by("-sold_at")[:50]
        )
        return Response([otc_payload(sale) for sale in sales])
