from rest_framework import status
from rest_framework.response import Response

from core.tenant_api import TenantAPIView
from scheduling.models import QueueEntry
from scheduling.serializers import CheckInSerializer, QueueEntrySerializer
from scheduling.services import check_in_patient, claim_queue_entry


class CheckInView(TenantAPIView):
    capability = "queue.view"

    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            entry = check_in_patient(
                organisation=request.organisation,
                facility=request.facility,
                actor=request.user,
                request=request,
                **serializer.validated_data,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(QueueEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


QUEUE_STATUSES = {choice[0] for choice in QueueEntry.STATUS_CHOICES}


class QueueListView(TenantAPIView):
    capability = "queue.view"

    def get(self, request):
        queryset = QueueEntry.objects.filter(organisation=request.organisation, facility=request.facility)
        queue_date = request.query_params.get("date")
        if queue_date:
            queryset = queryset.filter(queue_date=queue_date)
        statuses = []
        for value in request.query_params.getlist("status"):
            statuses.extend(part.strip().upper() for part in value.split(",") if part.strip())
        if statuses:
            unknown = [value for value in statuses if value not in QUEUE_STATUSES]
            if unknown:
                return Response(
                    {"detail": "Unknown queue status: " + ", ".join(unknown) + "."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(status__in=statuses)
        else:
            queryset = queryset.exclude(status__in=["COMPLETED", "CANCELLED"])
        return Response(QueueEntrySerializer(queryset.select_related("patient", "department"), many=True).data)


class QueueClaimView(TenantAPIView):
    capability = "queue.claim"

    def post(self, request, pk):
        try:
            entry = claim_queue_entry(
                organisation=request.organisation, actor=request.user, queue_id=pk, request=request
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(QueueEntrySerializer(entry).data)
