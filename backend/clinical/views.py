from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

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
        return Response(EncounterSerializer(encounter).data, status=status.HTTP_201_CREATED)


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
        return Response(EncounterSerializer(self.get_object(request, pk)).data)


class EncounterNoteView(TenantAPIView):
    capability = "clinical.note.create"

    def post(self, request, pk):
        encounter = get_object_or_404(
            Encounter, id=pk, organisation=request.organisation, facility=request.facility
        )
        serializer = NoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            note = save_note(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                content=serializer.validated_data["content"],
                request=request,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"note": note.id, "status": note.status, "content": note.content})


class EncounterSignView(TenantAPIView):
    capability = "clinical.note.sign"

    def post(self, request, pk):
        encounter = get_object_or_404(
            Encounter, id=pk, organisation=request.organisation, facility=request.facility
        )
        serializer = NoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            note = sign_note(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                encounter=encounter,
                content=serializer.validated_data["content"],
                request=request,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"note": note.id, "status": note.status, "current_version": note.current_version, "content": note.content})


class EncounterAmendView(TenantAPIView):
    capability = "clinical.note.amend"

    def post(self, request, pk):
        encounter = get_object_or_404(
            Encounter, id=pk, organisation=request.organisation, facility=request.facility
        )
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
                request=request,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"note": note.id, "status": note.status, "current_version": note.current_version})
