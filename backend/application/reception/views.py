from rest_framework import status
from rest_framework.response import Response

from application.reception.commands import (
    arrival_enquiry_record,
    patient_register,
    visit_cancel_error,
    visit_check_in,
    visit_context,
    visit_referral_source_record,
)
from application.reception.serializers import (
    ArrivalEnquirySerializer,
    ArrivalEnquiryWriteSerializer,
    PatientRegisterSerializer,
    PatientSerializer,
    ReferralSourceSerializer,
    VisitCheckInSerializer,
    VisitCancelErrorSerializer,
    VisitSerializer,
)
from billing.serializers import InvoiceSerializer
from clinical.serializers import EncounterSerializer
from core.tenant_api import TenantAPIView
from scheduling.serializers import QueueEntrySerializer


class PatientRegisterView(TenantAPIView):
    capability = "patient.create"
    idempotency_operation = "CMD-002"
    requires_idempotency = True

    def post(self, request):
        serializer = PatientRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = patient_register(
            organisation=request.organisation,
            actor=request.user,
            data=dict(serializer.validated_data),
            request=request,
        )
        if not outcome.created:
            return Response(
                {
                    "duplicate_candidates": PatientSerializer(
                        outcome.duplicate_candidates,
                        many=True,
                    ).data,
                    "next_action": "RESOLVE_DUPLICATE",
                },
                status=status.HTTP_200_OK,
            )
        patient_data = PatientSerializer(outcome.patient).data
        return Response(
            {
                **patient_data,
                "patient": patient_data,
                "patient_id": str(outcome.patient.id),
                "next_action": "CHECK_IN",
            },
            status=status.HTTP_201_CREATED,
        )


class VisitCheckInView(TenantAPIView):
    capability = "visit.create"
    idempotency_operation = "CMD-001"
    requires_idempotency = True

    def post(self, request):
        serializer = VisitCheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = visit_check_in(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        visit_data = VisitSerializer(outcome.visit).data
        queue_data = QueueEntrySerializer(outcome.queue).data if outcome.queue is not None else None
        invoice_data = InvoiceSerializer(outcome.invoice).data if outcome.invoice is not None else None
        return Response(
            {
                "id": str(outcome.queue.id if outcome.queue is not None else outcome.visit.id),
                "visit_id": str(outcome.visit.id),
                "queue_id": str(outcome.queue.id) if outcome.queue is not None else None,
                "invoice_id": str(outcome.invoice.id) if outcome.invoice is not None else None,
                "patient_id": str(outcome.visit.patient_id),
                "next_action": (
                    "LAB_REQUEST_CAPTURE"
                    if outcome.visit.visit_type == "LAB_ONLY"
                    else "CHECK_IN_COMPLETE"
                ),
                "visit": visit_data,
                "queue": queue_data,
                "invoice": invoice_data,
                "payer_binding": {
                    "id": str(outcome.payer_binding.id),
                    "payer_type": outcome.payer_binding.payer_type,
                    "price_list_id": (
                        str(outcome.payer_binding.price_list_id)
                        if outcome.payer_binding.price_list_id
                        else None
                    ),
                },
                "arrival_enquiry": (
                    ArrivalEnquirySerializer(outcome.arrival_enquiry).data
                    if outcome.arrival_enquiry is not None
                    else None
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class ArrivalEnquiryView(TenantAPIView):
    capability = "visit.create"
    idempotency_operation = "CMD-011"
    requires_idempotency = True

    def post(self, request):
        serializer = ArrivalEnquiryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = arrival_enquiry_record(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        data = ArrivalEnquirySerializer(outcome.enquiry).data
        return Response(
            {"id": str(outcome.enquiry.id), "enquiry_id": str(outcome.enquiry.id), "enquiry": data},
            status=status.HTTP_201_CREATED,
        )


class ReferralSourceView(TenantAPIView):
    capability = "visit.create"
    idempotency_operation = "CMD-010"
    requires_idempotency = True

    def post(self, request, pk):
        serializer = ReferralSourceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visit = visit_referral_source_record(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            visit_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(VisitSerializer(visit).data)


def _queue_history_payload(entries):
    return [
        {
            "id": str(entry.id),
            "queue_label": entry.queue_label,
            "department": str(entry.department_id),
            "department_name": entry.department.name,
            "queue_type": entry.queue_type,
            "status": entry.status,
            "current_stage": entry.current_stage,
            "queue_time": entry.queue_time,
            "called_at": entry.called_at,
            "claimed_by": str(entry.claimed_by_id) if entry.claimed_by_id else None,
            "claimed_by_name": entry.claimed_by.get_full_name() if entry.claimed_by_id else None,
            "claimed_at": entry.claimed_at,
            "completed_at": entry.completed_at,
            "hold_reason": entry.hold_reason,
            "version": entry.version,
        }
        for entry in entries
    ]


def _invoice_summary_payload(invoice):
    if invoice is None:
        return None
    return {
        "id": str(invoice.id),
        "invoice_no": invoice.invoice_no,
        "status": invoice.status,
        "currency": invoice.currency,
        "subtotal": invoice.subtotal,
        "total": invoice.total,
        "amount_paid": invoice.amount_paid,
        "balance": invoice.balance,
        "issued_at": invoice.issued_at,
        "voided_at": invoice.voided_at,
        "version": invoice.version,
    }


class VisitContextView(TenantAPIView):
    capability = "visit.read"

    def get(self, request, pk):
        include_clinical = request.user.has_capability("encounter.read", request.facility)
        outcome = visit_context(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            visit_id=pk,
            include_clinical=include_clinical,
            request=request,
        )
        clinical_summary = [
            {
                "encounter_id": str(encounter.id),
                "status": encounter.status,
                "clinician": str(encounter.clinician_id),
                "clinician_name": encounter.clinician.get_full_name(),
                "started_at": encounter.started_at,
                "signed_at": encounter.signed_at,
                "closed_at": encounter.closed_at,
            }
            for encounter in (
                outcome.encounters
                if include_clinical
                else _encounters_for_summary(outcome.queue_entries, outcome.visit)
            )
        ]
        return Response(
            {
                "visit": VisitSerializer(outcome.visit).data,
                "queue_history": _queue_history_payload(outcome.queue_entries),
                "invoice": _invoice_summary_payload(outcome.invoice),
                "clinical_summary": clinical_summary,
                "clinical": (
                    EncounterSerializer(outcome.encounters, many=True, context={"request": request}).data
                    if outcome.clinical_values_returned
                    else None
                ),
            }
        )


def _encounters_for_summary(entries, visit):
    from clinical.models import Encounter

    queue_ids = [entry.id for entry in entries]
    return Encounter.objects.select_related("clinician").filter(
        organisation=visit.organisation,
        facility=visit.facility,
        queue_entry_id__in=queue_ids,
    ).order_by("started_at", "id")


class VisitCancelErrorView(TenantAPIView):
    capability = "visit.cancel_error"
    idempotency_operation = "CMD-006"
    requires_idempotency = True

    def post(self, request, pk):
        serializer = VisitCancelErrorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        outcome = visit_cancel_error(
            organisation=request.organisation,
            facility=request.facility,
            actor=request.user,
            visit_id=pk,
            request=request,
            **serializer.validated_data,
        )
        return Response(
            {
                "visit_id": str(outcome.visit.id),
                "visit": VisitSerializer(outcome.visit).data,
                "queue_entries": QueueEntrySerializer(outcome.queue_entries, many=True).data,
                "invoice": InvoiceSerializer(outcome.invoice).data if outcome.invoice is not None else None,
            }
        )
