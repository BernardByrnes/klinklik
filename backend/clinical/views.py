from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from clinical.concurrency import ClinicalNoteRevisionConflict, consultation_note_etag
from clinical.models import Encounter
from clinical.serializers import (
    EncounterSerializer,
    NoteAmendSerializer,
    NoteWriteSerializer,
    TriageSerializer,
)
from clinical.services import amend_note, record_triage, save_note, sign_note, start_encounter
from core.tenant_api import TenantAPIView
from scheduling.models import QueueEntry
from scheduling.serializers import QueueEntrySerializer


class TriageView(TenantAPIView):
    capability = "triage.record"

    def post(self, request, queue_id):
        serializer = TriageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assessment = record_triage(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                queue_entry_id=queue_id,
                data=serializer.validated_data,
                request=request,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "id": assessment.id,
            "queue_entry": QueueEntrySerializer(assessment.queue_entry).data,
            "acuity": assessment.acuity,
            "chief_complaint": assessment.chief_complaint,
            "observations": assessment.observations,
        }, status=status.HTTP_201_CREATED)


def _required_if_match(request):
    expected_etag = request.headers.get("If-Match")
    if not expected_etag:
        return None, Response(
            {
                "code": "PRECONDITION_REQUIRED",
                "detail": "If-Match is required for clinical note mutations.",
            },
            status=status.HTTP_428_PRECONDITION_REQUIRED,
        )
    return expected_etag, None


def _revision_conflict_response(exc, http_status=status.HTTP_409_CONFLICT):
    response = Response(
        {
            "code": "CLINICAL_NOTE_REVISION_CONFLICT",
            "detail": "This consultation changed elsewhere; review the current record before retrying.",
            "etag": exc.current_etag,
            "status": exc.current_status,
            "encounter_status": exc.current_encounter_status,
            "content": exc.current_content,
            "saved_at": exc.current_saved_at,
        },
        status=http_status,
    )
    response["ETag"] = exc.current_etag
    return response


def _note_response(*, encounter, note, include_version=False):
    note.refresh_from_db(fields=["updated_at"])
    data = {
        "note": note.id,
        "status": note.status,
        "content": note.content,
        "etag": consultation_note_etag(encounter=encounter, note=note),
        "saved_at": note.updated_at.isoformat(),
    }
    if include_version:
        data["current_version"] = note.current_version
    response = Response(data)
    response["ETag"] = data["etag"]
    return response


class EncounterListCreateView(TenantAPIView):
    capability = "clinical.note.create"

    def post(self, request):
        queue_entry_id = request.data.get("queue_entry_id")
        if not queue_entry_id:
            return Response({"detail": "queue_entry_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            encounter = start_encounter(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                queue_entry_id=queue_entry_id,
                request=request,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        data = EncounterSerializer(encounter).data
        response = Response(data, status=status.HTTP_201_CREATED)
        response["ETag"] = data["consultation_etag"]
        return response


class EncounterDetailView(TenantAPIView):
    capability = "clinical.note.create"

    def get_object(self, request, pk):
        return get_object_or_404(
            Encounter.objects.prefetch_related("notes"),
            id=pk,
            organisation=request.organisation,
            facility=request.facility,
        )

    def get(self, request, pk):
        data = EncounterSerializer(self.get_object(request, pk)).data
        response = Response(data)
        response["ETag"] = data["consultation_etag"]
        return response


class EncounterNoteView(TenantAPIView):
    capability = "clinical.note.create"

    def _save(self, request, pk, conflict_status):
        encounter = get_object_or_404(
            Encounter, id=pk, organisation=request.organisation, facility=request.facility
        )
        expected_etag, error_response = _required_if_match(request)
        if error_response is not None:
            return error_response
        serializer = NoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            note = save_note(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                content=serializer.validated_data["content"],
                expected_etag=expected_etag,
                request=request,
            )
        except ClinicalNoteRevisionConflict as exc:
            return _revision_conflict_response(exc, http_status=conflict_status)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _note_response(encounter=encounter, note=note)

    def post(self, request, pk):
        return self._save(request, pk, conflict_status=status.HTTP_409_CONFLICT)

    def patch(self, request, pk):
        return self._save(request, pk, conflict_status=status.HTTP_412_PRECONDITION_FAILED)

class EncounterSignView(TenantAPIView):
    capability = "clinical.note.sign"

    def post(self, request, pk):
        encounter = get_object_or_404(
            Encounter, id=pk, organisation=request.organisation, facility=request.facility
        )
        expected_etag, error_response = _required_if_match(request)
        if error_response is not None:
            return error_response
        serializer = NoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            note = sign_note(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                content=serializer.validated_data["content"],
                expected_etag=expected_etag,
                request=request,
            )
        except ClinicalNoteRevisionConflict as exc:
            return _revision_conflict_response(exc)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _note_response(encounter=encounter, note=note, include_version=True)


class EncounterAmendView(TenantAPIView):
    capability = "clinical.note.amend"

    def post(self, request, pk):
        encounter = get_object_or_404(
            Encounter, id=pk, organisation=request.organisation, facility=request.facility
        )
        expected_etag, error_response = _required_if_match(request)
        if error_response is not None:
            return error_response
        serializer = NoteAmendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            note = amend_note(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                content=serializer.validated_data["content"],
                reason=serializer.validated_data["reason"],
                expected_etag=expected_etag,
                request=request,
            )
        except ClinicalNoteRevisionConflict as exc:
            return _revision_conflict_response(exc)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return _note_response(encounter=encounter, note=note, include_version=True)
