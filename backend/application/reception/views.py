from rest_framework import status
from rest_framework.response import Response

from application.reception.commands import (
    arrival_enquiry_record,
    patient_register,
    visit_cancel_error,
    visit_check_in,
    visit_referral_source_record,
)
from application.reception.audited_reads import audit_clinical_projection
from application.reception.visit_query import (
    get_clinical_projection,
    get_patient_checkin_projection,
    get_visit_projection,
)
from application.reception.serializers import (
    ArrivalEnquiryResponseSerializer,
    ArrivalEnquiryWriteSerializer,
    PatientRegisterSerializer,
    PatientDuplicateCandidateSerializer,
    PatientDuplicateResponseSerializer,
    PatientRegisterResponseSerializer,
    PatientCheckInSummarySerializer,
    ReferralSourceSerializer,
    ReferralSourceResponseSerializer,
    VisitCheckInSerializer,
    VisitCancelErrorSerializer,
    VisitCancelErrorResponseSerializer,
    VisitContextResponseSerializer,
    VisitCheckInResponseSerializer,
    VisitSerializer,
)
from clinical.serializers import (
    AllergyContextProjectionSerializer,
    EncounterSerializer,
    PatientContextProjectionSerializer,
    VisitHistoryProjectionSerializer,
)
from core.tenant_api import TenantAPIView
from core.idempotency import UncommittedResponse, json_safe


def _store_exact_idempotent_response(response, *, stored_body=None):
    """Set the canonical, PHI-minimal result persisted in PC-048."""

    # DRF serializers may leave UUID, Decimal, and datetime instances in
    # ``Response.data`` until rendering.  Normalize once before both the
    # first response and the durable replay record are finalized so replay is
    # equivalent at the JSON boundary as well as at the Python payload level.
    public_body = json_safe(response.data)
    response.data = public_body
    response.idempotency_body = json_safe(public_body if stored_body is None else stored_body)
    return response


class PatientRegisterView(TenantAPIView):
    capability = "patient.create"
    idempotency_operation = "CMD-002"
    requires_idempotency = True
    serializer_class = PatientRegisterSerializer
    response_serializer_class = PatientRegisterResponseSerializer
    response_serializer_classes_by_status = {
        "POST": {
            "200": PatientDuplicateResponseSerializer,
            "201": PatientRegisterResponseSerializer,
        },
    }

    def replay_idempotent_response(self, record):
        return record.response_body

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
            response = Response(
                {
                    "duplicate_candidates": PatientDuplicateCandidateSerializer(
                        outcome.duplicate_candidates,
                        many=True,
                    ).data,
                    "next_action": "RESOLVE_DUPLICATE",
                },
                status=status.HTTP_200_OK,
            )
            # Duplicate discovery is a non-committing decision point. Do not
            # persist a replay body containing candidate PHI in IdempotencyRecord.
            raise UncommittedResponse(response)
        response = Response(
            {
                "patient_id": str(outcome.patient.id),
                "next_action": "CHECK_IN",
            },
            status=status.HTTP_201_CREATED,
        )
        _store_exact_idempotent_response(
            response,
            stored_body={
                "patient_id": str(outcome.patient.id),
                "next_action": "CHECK_IN",
            },
        )
        response.result_reference = {"entity_type": "Patient", "entity_id": str(outcome.patient.id)}
        return response


class VisitCheckInView(TenantAPIView):
    capability = "visit.create"
    idempotency_operation = "CMD-001"
    requires_idempotency = True
    serializer_class = VisitCheckInSerializer
    response_serializer_class = VisitCheckInResponseSerializer

    def replay_idempotent_response(self, record):
        return record.response_body

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
        response = Response(
            {
                "visit_id": str(outcome.visit.id),
                "queue_id": str(outcome.queue.id) if outcome.queue is not None else None,
                "invoice_id": str(outcome.invoice.id) if outcome.invoice is not None else None,
                "patient_id": str(outcome.visit.patient_id),
                "next_action": (
                    "LAB_REQUEST_CAPTURE"
                    if outcome.visit.visit_type == "LAB_ONLY"
                    else "CHECK_IN_COMPLETE"
                ),
            },
            status=status.HTTP_201_CREATED,
        )
        _store_exact_idempotent_response(
            response,
            stored_body={
                "visit_id": str(outcome.visit.id),
                "queue_id": str(outcome.queue.id) if outcome.queue is not None else None,
                "invoice_id": str(outcome.invoice.id) if outcome.invoice is not None else None,
                "patient_id": str(outcome.visit.patient_id),
                "next_action": (
                    "LAB_REQUEST_CAPTURE"
                    if outcome.visit.visit_type == "LAB_ONLY"
                    else "CHECK_IN_COMPLETE"
                ),
            },
        )
        # PC-048 needs only the committed owner result reference. Queue,
        # invoice, payer, and enquiry identifiers are already represented by
        # the PHI-minimal response body and are not needed to replay it.
        response.result_reference = {"entity_type": "Visit", "entity_id": str(outcome.visit.id)}
        return response


class PatientCheckInSummaryView(TenantAPIView):
    capability = "visit.read"
    response_serializer_class = PatientCheckInSummarySerializer
    response_is_list = False

    def get(self, request, pk):
        projection = get_patient_checkin_projection(
            organisation=request.organisation,
            facility=request.facility,
            patient_id=pk,
        )
        return Response(
            PatientCheckInSummarySerializer(
                {
                    "patient": projection.patient,
                    "outstanding_balance": projection.outstanding_balance,
                    "outstanding_invoice_no": projection.outstanding_invoice_no,
                    "outstanding_visit_id": projection.outstanding_visit_id,
                    "active_visit": projection.active_visit,
                    "active_queue_label": projection.active_queue_label,
                }
            ).data
        )


class ArrivalEnquiryView(TenantAPIView):
    capability = "visit.create"
    idempotency_operation = "CMD-011"
    requires_idempotency = True
    serializer_class = ArrivalEnquiryWriteSerializer
    response_serializer_class = ArrivalEnquiryResponseSerializer

    def replay_idempotent_response(self, record):
        return record.response_body

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
        response = Response(
            {"enquiry_id": str(outcome.enquiry.id)},
            status=status.HTTP_201_CREATED,
        )
        _store_exact_idempotent_response(
            response,
            stored_body={"enquiry_id": str(outcome.enquiry.id)},
        )
        response.result_reference = {"entity_type": "ArrivalEnquiry", "entity_id": str(outcome.enquiry.id)}
        return response


class ReferralSourceView(TenantAPIView):
    capability = "visit.create"
    idempotency_operation = "CMD-010"
    requires_idempotency = True
    serializer_class = ReferralSourceSerializer
    response_serializer_class = ReferralSourceResponseSerializer

    def replay_idempotent_response(self, record):
        return record.response_body

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
        response = Response({"visit_id": str(visit.id), "version": visit.version})
        _store_exact_idempotent_response(
            response,
            stored_body={"visit_id": str(visit.id), "version": visit.version},
        )
        response.result_reference = {"entity_type": "Visit", "entity_id": str(visit.id)}
        return response


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
    response_serializer_class = VisitContextResponseSerializer
    response_is_list = False

    def get(self, request, pk):
        include_clinical = request.user.has_capability("encounter.read", request.facility)
        projection = get_visit_projection(
            organisation=request.organisation,
            facility=request.facility,
            visit_id=pk,
        )
        clinical_projection = get_clinical_projection(
            organisation=request.organisation,
            facility=request.facility,
            projection=projection,
            include_clinical=include_clinical,
        )
        clinical_summary = _clinical_summary_payload(clinical_projection.encounters)
        if include_clinical:
            audit_clinical_projection(
                organisation=request.organisation,
                actor=request.user,
                facility=request.facility,
                visit=projection.visit,
                encounters=clinical_projection.encounters,
            )
        return Response(
            {
                "visit": VisitSerializer(projection.visit).data,
                "queue_history": _queue_history_payload(projection.queue_entries),
                "invoice": _invoice_summary_payload(projection.invoice),
                "clinical_summary": clinical_summary,
                "clinical": (
                    EncounterSerializer(
                        clinical_projection.clinical_values,
                        many=True,
                        context={"request": request},
                    ).data
                    if clinical_projection is not None and clinical_projection.has_clinical_values
                    else None
                ),
                "patient": (
                    PatientContextProjectionSerializer(
                        clinical_projection.patient_projections[0]
                    ).data
                    if include_clinical and clinical_projection.patient_projections
                    else None
                ),
                "allergy": (
                    AllergyContextProjectionSerializer(
                        clinical_projection.allergy_projections[0]
                    ).data
                    if include_clinical and clinical_projection.allergy_projections
                    else None
                ),
                "visit_history": (
                    VisitHistoryProjectionSerializer(
                        clinical_projection.visit_history,
                        many=True,
                    ).data
                    if include_clinical
                    else []
                ),
                "laboratory": list(clinical_projection.laboratory) if include_clinical else [],
                "prescriptions": list(clinical_projection.prescriptions) if include_clinical else [],
                "dispenses": list(clinical_projection.dispenses) if include_clinical else [],
            }
        )


def _clinical_summary_payload(summaries):
    return [
        {
            "encounter_id": str(summary.id),
            "status": summary.status,
            "clinician": str(summary.clinician_id),
            "clinician_name": summary.clinician.get_full_name(),
            "started_at": summary.started_at,
            "signed_at": summary.signed_at,
            "closed_at": summary.closed_at,
        }
        for summary in summaries
    ]


class VisitCancelErrorView(TenantAPIView):
    capability = "visit.cancel_error"
    idempotency_operation = "CMD-006"
    requires_idempotency = True
    serializer_class = VisitCancelErrorSerializer
    response_serializer_class = VisitCancelErrorResponseSerializer

    def replay_idempotent_response(self, record):
        return record.response_body

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
        response = Response({"visit_id": str(outcome.visit.id), "state": outcome.visit.state})
        _store_exact_idempotent_response(
            response,
            stored_body={"visit_id": str(outcome.visit.id), "state": outcome.visit.state},
        )
        response.result_reference = {"entity_type": "Visit", "entity_id": str(outcome.visit.id)}
        return response
