from django.urls import path
from rest_framework.response import Response

from core.tenant_api import TenantAPIView
from tenancy.models import Department, Facility
from tenancy.serializers import DepartmentEnvelopeSerializer, DepartmentSerializer, FacilityEnvelopeSerializer, FacilitySerializer


class FacilityListView(TenantAPIView):
    response_serializer_class = FacilityEnvelopeSerializer
    response_is_list = False
    def get(self, request):
        facilities = Facility.objects.filter(organisation=request.organisation, is_active=True)
        return Response({"facilities": FacilitySerializer(facilities, many=True).data})


class DepartmentListView(TenantAPIView):
    response_serializer_class = DepartmentEnvelopeSerializer
    response_is_list = False
    def get(self, request):
        departments = Department.objects.filter(
            organisation=request.organisation, facility=request.facility, is_active=True
        ) if request.facility else Department.objects.none()
        return Response({"departments": DepartmentSerializer(departments, many=True).data})


urlpatterns = [
    path("facilities/", FacilityListView.as_view(), name="facility-list"),
    path("departments/", DepartmentListView.as_view(), name="department-list"),
]
