import hashlib
import json

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from core.tenant_api import TenantAPIView
from patients.models import Patient
from patients.serializers import (
    PatientCreateSerializer,
    PatientLinkResponseSerializer,
    PatientLinkSerializer,
    PatientSerializer,
)
from patients.services import create_patient, link_patients, search_patients


def patient_etag(patient):
    payload = json.dumps(PatientSerializer(patient).data, default=str, sort_keys=True).encode("utf-8")
    return '"' + hashlib.sha256(payload).hexdigest() + '"'


class PatientListCreateView(TenantAPIView):
    serializer_class = PatientCreateSerializer
    response_serializer_classes = {"GET": PatientSerializer, "POST": PatientSerializer}
    response_is_list = {"GET": True, "POST": False}
    def get_permissions(self):
        self.capability = "patient.create" if self.request.method == "POST" else "patient.view"
        return super().get_permissions()

    def get(self, request):
        return Response(
            PatientSerializer(
                search_patients(organisation=request.organisation, term=request.query_params.get("q", "")),
                many=True,
            ).data
        )

    def post(self, request):
        serializer = PatientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = create_patient(
            organisation=request.organisation,
            actor=request.user,
            data=dict(serializer.validated_data),
            request=request,
        )
        return Response(PatientSerializer(patient).data, status=status.HTTP_201_CREATED)


class PatientDetailView(TenantAPIView):
    serializer_class = PatientSerializer
    response_serializer_class = PatientSerializer
    def get_permissions(self):
        self.capability = "patient.edit" if self.request.method in {"PATCH", "PUT"} else "patient.view"
        return super().get_permissions()

    def get_object(self, request, pk):
        return get_object_or_404(Patient, id=pk, organisation=request.organisation)

    def get(self, request, pk):
        return Response(PatientSerializer(self.get_object(request, pk)).data)

    def patch(self, request, pk):
        patient = self.get_object(request, pk)
        expected = request.headers.get("If-Match")
        if not expected:
            return Response({"detail": "If-Match is required for demographic edits."}, status=428)
        if expected != patient_etag(patient):
            return Response({"detail": "The patient record changed; refresh before editing."}, status=412)
        serializer = PatientSerializer(patient, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PatientLinkView(TenantAPIView):
    capability = "patient.link"
    serializer_class = PatientLinkSerializer
    response_serializer_class = PatientLinkResponseSerializer

    def post(self, request, pk):
        source = get_object_or_404(Patient, id=pk, organisation=request.organisation)
        serializer = PatientLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = get_object_or_404(
            Patient, id=serializer.validated_data["target_patient_id"], organisation=request.organisation
        )
        try:
            link = link_patients(
                organisation=request.organisation,
                actor=request.user,
                source_patient=source,
                target_patient=target,
                link_type=serializer.validated_data["link_type"],
                reason=serializer.validated_data.get("reason", ""),
                request=request,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"id": link.id, "status": link.status}, status=status.HTTP_201_CREATED)
