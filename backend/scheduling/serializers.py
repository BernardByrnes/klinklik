from rest_framework import serializers

from scheduling.models import QueueEntry


class QueueEntrySerializer(serializers.ModelSerializer):
    queue_label = serializers.ReadOnlyField()
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = QueueEntry
        fields = [
            "id",
            "visit",
            "queue_label",
            "patient",
            "patient_name",
            "department",
            "department_name",
            "queue_date",
            "sequence",
            "queue_type",
            "work_identity",
            "hold_reason",
            "priority",
            "priority_changed_at",
            "priority_reason",
            "visit_type",
            "status",
            "current_stage",
            "arrival_at",
            "queue_time",
            "called_at",
            "claimed_by",
            "claimed_at",
            "completed_at",
            "notes",
            "source_event_id",
            "version",
        ]


class CheckInSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    department_id = serializers.UUIDField(required=False)
    visit_type = serializers.CharField(required=False, default="WALK_IN")
    notes = serializers.CharField(required=False, allow_blank=True)
