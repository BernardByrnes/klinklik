from rest_framework import serializers

from laboratory.models import LabAnalyteDefinition, LabOrderItem, LabResult, LabTestDefinition


class LabAnalyteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabAnalyteDefinition
        fields = ["id", "code", "name", "unit", "result_type", "sequence", "coded_options"]


class LabTestSerializer(serializers.ModelSerializer):
    analytes = LabAnalyteSerializer(many=True, read_only=True)

    class Meta:
        model = LabTestDefinition
        fields = [
            "id", "code", "name", "specimen_type", "result_type", "service",
            "turnaround_minutes", "coded_options", "text_template", "active",
            "definition_version", "version", "analytes",
        ]


class LabTestConfigureSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=60)
    name = serializers.CharField(max_length=160)
    service_id = serializers.UUIDField(required=False, allow_null=True)
    specimen_type = serializers.CharField(required=False, default="BLOOD")
    result_type = serializers.ChoiceField(
        choices=["NUMERIC", "CODED", "TEXT", "PANEL"], required=False, default="NUMERIC"
    )
    turnaround_minutes = serializers.IntegerField(required=False, default=60)
    coded_options = serializers.ListField(child=serializers.CharField(), required=False)
    analytes = serializers.ListField(child=serializers.DictField(), required=False)


class LabOrderCreateSerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    test_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    priority = serializers.ChoiceField(choices=["ROUTINE", "URGENT"], required=False, default="ROUTINE")
    clinical_notes = serializers.CharField(required=False, allow_blank=True, default="")
    source_event_id = serializers.CharField(required=False, allow_blank=True)


class LabWorklistQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, max_value=200, required=False, default=50)
    offset = serializers.IntegerField(min_value=0, required=False, default=0)
    view = serializers.ChoiceField(
        choices=["active", "history"], required=False, default="active"
    )


class LabItemSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source="test.name", read_only=True)

    class Meta:
        model = LabOrderItem
        fields = [
            "id", "order", "test", "test_name", "state", "priority",
            "price_snapshot", "currency", "specimen_id", "collected_at",
            "rejection_reason", "version",
        ]


class LabRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=240)


class LabCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=240)


class LabResultSaveSerializer(serializers.Serializer):
    values = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    comments = serializers.CharField(required=False, allow_blank=True, default="")
    complete = serializers.BooleanField(required=False, default=False)


class LabResultDetailSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    test_name = serializers.CharField()
    specimen_id = serializers.CharField(allow_null=True)
    state = serializers.CharField()
    result_state = serializers.CharField(allow_null=True)
    priority = serializers.CharField()
    version_no = serializers.IntegerField(allow_null=True)
    analytes = serializers.ListField(child=serializers.DictField())
    values = serializers.ListField(child=serializers.DictField())
    comments = serializers.CharField()
    entered_by = serializers.CharField(allow_null=True)
    entered_at = serializers.DateTimeField(allow_null=True)
    released_at = serializers.DateTimeField(allow_null=True)
    verified_by = serializers.CharField(allow_null=True)


class LabResultReleaseSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class LabAmendSerializer(serializers.Serializer):
    values = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    comments = serializers.CharField(required=False, allow_blank=True, default="")
    reason = serializers.CharField(max_length=240)
