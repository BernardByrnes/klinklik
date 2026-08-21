from rest_framework.response import Response

from audit.models import AuditEvent
from audit.serializers import AuditEventSerializer
from core.tenant_api import TenantAPIView


class AuditEventListView(TenantAPIView):
    capability = "audit.log.view"

    def get(self, request):
        queryset = AuditEvent.objects.filter(organisation=request.organisation).order_by("-occurred_at")
        entity_type = request.query_params.get("entity_type")
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        return Response(AuditEventSerializer(queryset[:200], many=True).data)
