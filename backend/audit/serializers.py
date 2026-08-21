from rest_framework import serializers

from audit.models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "action",
            "entity_type",
            "entity_id",
            "actor",
            "facility",
            "request_id",
            "reason",
            "before",
            "after",
            "occurred_at",
        ]
