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
            "hold_ref",
            "held_at",
            "terminal_reason",
            "priority",
            "priority_changed_at",
            "priority_reason",
            "visit_type",
            "status",
            "state",
            "current_stage",
            "source_stage",
            "arrival_at",
            "queue_time",
            "called_at",
            "called_by",
            "claimed_by",
            "claimed_at",
            "assigned_user",
            "served_by",
            "started_at",
            "service_started_at",
            "completed_at",
            "completed_by",
            "removed_at",
            "removed_by",
            "wait_seconds",
            "service_seconds",
            "call_attempts",
            "no_show_count",
            "last_activity_at",
            "notes",
            "source_event_id",
            "version",
        ]


class QueueMutationResponseSerializer(serializers.Serializer):
    """PHI-minimal result envelope shared by queue command responses."""

    queue_entry_id = serializers.UUIDField(required=False, allow_null=True)
    state = serializers.CharField(required=False, allow_null=True)
    version = serializers.IntegerField(required=False, min_value=1)
    call_attempts = serializers.IntegerField(required=False, min_value=0)
    no_show_count = serializers.IntegerField(required=False, min_value=0)
    called_by_id = serializers.UUIDField(required=False, allow_null=True)
    served_by_id = serializers.UUIDField(required=False, allow_null=True)
    assigned_user_id = serializers.UUIDField(required=False, allow_null=True)
    source_queue_entry_id = serializers.UUIDField(required=False, allow_null=True)
    destination_queue_entry_id = serializers.UUIDField(required=False, allow_null=True)
    source_state = serializers.CharField(required=False, allow_null=True)
    destination_state = serializers.CharField(required=False, allow_null=True)
    priority = serializers.CharField(required=False, allow_null=True)
    expired_entry_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )
    exceptions = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )
    closed_visit_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )
    review_visit_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )
    expired_count = serializers.IntegerField(required=False, min_value=0)
    exception_count = serializers.IntegerField(required=False, min_value=0)


class QueueCallSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField(required=False)
    department_id = serializers.UUIDField(required=False)
    queue_type = serializers.CharField(required=False, max_length=40)
    expected_version = serializers.IntegerField(required=False, min_value=1)
    ordering_watermark = serializers.DateTimeField(required=False)
    out_of_order_reason = serializers.CharField(required=False, allow_blank=True, max_length=240)


class QueueAssignSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField(required=False)
    target_user_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(required=False, min_value=1)


class QueueTransferSerializer(serializers.Serializer):
    source_queue_entry_id = serializers.UUIDField(required=False)
    target_department_id = serializers.UUIDField()
    target_queue_type = serializers.CharField(required=False, max_length=40)
    handoff_note = serializers.CharField(required=False, allow_blank=True, max_length=240)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=240)
    expected_version = serializers.IntegerField(required=False, min_value=1)


class QueuePrioritySerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField(required=False)
    priority = serializers.ChoiceField(choices=["EMERGENCY", "URGENT", "ROUTINE"])
    reason = serializers.CharField(max_length=240)
    expected_version = serializers.IntegerField(required=False, min_value=1)


class QueueNoResponseSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField(required=False)
    outcome = serializers.ChoiceField(choices=["REQUEUE", "NO_SHOW"], default="REQUEUE")
    emergency_acknowledged = serializers.BooleanField(required=False, default=False)
    expected_version = serializers.IntegerField(required=False, min_value=1)


class QueueRequeueSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField(required=False)
    reason = serializers.CharField(max_length=240)
    expected_version = serializers.IntegerField(required=False, min_value=1)


class QueueCancelSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField(required=False)
    reason = serializers.ChoiceField(
        choices=[
            "LEFT_WITHOUT_BEING_SEEN",
            "WRONG_QUEUE",
            "DUPLICATE",
            "SENT_HOME",
            "SENT_ELSEWHERE",
            "ROUTED_IN_ERROR",
            "OTHER",
        ]
    )
    lwbs = serializers.BooleanField(required=False, default=False)
    expected_version = serializers.IntegerField(required=False, min_value=1)


class QueueTakeoverSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField(required=False)
    new_user_id = serializers.UUIDField(required=False)
    reason = serializers.CharField(max_length=240)
    expected_version = serializers.IntegerField(required=False, min_value=1)
    observed_at = serializers.DateTimeField(required=False)


class QueueSweepSerializer(serializers.Serializer):
    local_service_day = serializers.DateField(required=False)
    cutoff = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        if attrs.get("local_service_day") is not None and attrs.get("cutoff") is not None:
            raise serializers.ValidationError("Supply local_service_day or cutoff, not both.")
        return attrs


class OperationalQueueRowSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    visit_id = serializers.UUIDField(required=False, allow_null=True)
    patient_id = serializers.UUIDField(required=False)
    patient_no = serializers.CharField()
    patient_name = serializers.CharField()
    sex = serializers.CharField()
    age = serializers.CharField(required=False, allow_null=True)
    queue_label = serializers.CharField()
    token = serializers.CharField()
    department_id = serializers.UUIDField()
    department_name = serializers.CharField()
    queue_type = serializers.CharField()
    state = serializers.CharField()
    status = serializers.CharField()
    current_stage = serializers.CharField()
    source_stage = serializers.CharField()
    priority = serializers.CharField()
    priority_reason = serializers.CharField()
    queue_time = serializers.DateTimeField()
    called_at = serializers.DateTimeField(required=False, allow_null=True)
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    service_started_at = serializers.DateTimeField(required=False, allow_null=True)
    completed_at = serializers.DateTimeField(required=False, allow_null=True)
    wait_seconds = serializers.IntegerField()
    service_seconds = serializers.IntegerField(required=False, allow_null=True)
    hold_reason = serializers.CharField()
    hold_ref = serializers.CharField(required=False, allow_null=True)
    hold_age_seconds = serializers.IntegerField(required=False, allow_null=True)
    call_attempts = serializers.IntegerField()
    no_show_count = serializers.IntegerField()
    assigned_user_id = serializers.UUIDField(required=False, allow_null=True)
    assigned_user_name = serializers.CharField(required=False, allow_null=True)
    called_by_id = serializers.UUIDField(required=False, allow_null=True)
    called_by_name = serializers.CharField(required=False, allow_null=True)
    served_by_id = serializers.UUIDField(required=False, allow_null=True)
    served_by_name = serializers.CharField(required=False, allow_null=True)
    handoff_note = serializers.CharField()
    version = serializers.IntegerField()
    stale = serializers.BooleanField()
    sla_minutes = serializers.IntegerField(required=False, allow_null=True)
    sla_breached = serializers.BooleanField()
    longest_wait_seconds = serializers.IntegerField(required=False)
    triage_acuity = serializers.CharField(required=False)
    test_names = serializers.ListField(child=serializers.CharField(), required=False)
    invoice_no = serializers.CharField(required=False)
    amount_due = serializers.CharField(required=False)
    currency = serializers.CharField(required=False)
    invoice_status = serializers.CharField(required=False)


class OperationalQueueEnvelopeSerializer(serializers.Serializer):
    entries = OperationalQueueRowSerializer(many=True)
    count = serializers.IntegerField()
    row_count = serializers.IntegerField()
    longest_wait_seconds = serializers.IntegerField()
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    has_next = serializers.BooleanField()
    server_time = serializers.DateTimeField()
    refresh_after_seconds = serializers.IntegerField()


class QueueLocationSerializer(serializers.Serializer):
    visit_id = serializers.UUIDField()
    state = serializers.CharField()
    label = serializers.CharField()
    current = serializers.JSONField(allow_null=True)
    return_obligations = serializers.ListField(child=serializers.JSONField())


class QueueHistoryItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    queue_label = serializers.CharField()
    department_id = serializers.UUIDField()
    department_name = serializers.CharField()
    queue_type = serializers.CharField()
    state = serializers.CharField()
    status = serializers.CharField()
    source_stage = serializers.CharField()
    queue_time = serializers.DateTimeField()
    called_at = serializers.DateTimeField(required=False, allow_null=True)
    called_by = serializers.UUIDField(required=False, allow_null=True)
    started_at = serializers.DateTimeField(required=False, allow_null=True)
    served_by = serializers.UUIDField(required=False, allow_null=True)
    completed_at = serializers.DateTimeField(required=False, allow_null=True)
    completed_by = serializers.UUIDField(required=False, allow_null=True)
    wait_seconds = serializers.IntegerField(required=False, allow_null=True)
    service_seconds = serializers.IntegerField(required=False, allow_null=True)
    priority = serializers.CharField()
    priority_reason = serializers.CharField()
    hold_reason = serializers.CharField()
    hold_ref = serializers.CharField(required=False, allow_null=True)
    terminal_reason = serializers.CharField(required=False, allow_null=True)
    removed_by = serializers.UUIDField(required=False, allow_null=True)
    removed_at = serializers.DateTimeField(required=False, allow_null=True)
    version = serializers.IntegerField()


class QueueSupervisorRowSerializer(serializers.Serializer):
    department_id = serializers.UUIDField()
    department_name = serializers.CharField()
    waiting_count = serializers.IntegerField()
    in_service_count = serializers.IntegerField()
    on_hold_count = serializers.IntegerField()
    longest_wait_seconds = serializers.IntegerField()
    median_wait_seconds = serializers.IntegerField()
    staff_serving = serializers.ListField(child=serializers.CharField())
    sla_breached = serializers.BooleanField()


class PublicBoardRowSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField()
    identity = serializers.CharField()
    queue_label = serializers.CharField()


class CheckInSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    department_id = serializers.UUIDField(required=False)
    visit_type = serializers.CharField(required=False, default="WALK_IN")
    notes = serializers.CharField(required=False, allow_blank=True)


class QueueEntryListSerializer(serializers.ListSerializer):
    child = QueueEntrySerializer()
