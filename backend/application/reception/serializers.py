from rest_framework import serializers

from patients.models import Patient
from patients.serializers import PatientCreateSerializer, PatientSerializer
from scheduling.models import ArrivalEnquiry, Visit
from scheduling.serializers import QueueEntrySerializer
from billing.serializers import InvoiceSerializer
from clinical.serializers import EncounterSerializer


class PatientRegisterSerializer(PatientCreateSerializer):
    sex = serializers.ChoiceField(choices=Patient.SEX_CHOICES, required=True)
    duplicate_resolution = serializers.JSONField(required=False, write_only=True)
    duplicate_override = serializers.JSONField(required=False, write_only=True)
    duplicate_override_reason = serializers.CharField(required=False, write_only=True, allow_blank=True)

    class Meta(PatientCreateSerializer.Meta):
        fields = PatientCreateSerializer.Meta.fields + [
            "duplicate_resolution",
            "duplicate_override",
            "duplicate_override_reason",
        ]

    def validate_sex(self, value):
        if not value:
            raise serializers.ValidationError("Sex is required for registration.")
        return value

    def validate(self, attrs):
        date_of_birth = attrs.get("date_of_birth")
        estimated_years = attrs.get("estimated_age_years")
        estimated_months = attrs.get("estimated_age_months")
        if date_of_birth and (estimated_years is not None or estimated_months is not None):
            raise serializers.ValidationError(
                "Enter date of birth or estimated age, not both."
            )
        if estimated_months is not None and estimated_months > 11:
            raise serializers.ValidationError({"estimated_age_months": "Months must be between 0 and 11."})
        if estimated_years is not None or estimated_months is not None:
            attrs["dob_estimated"] = True
        if attrs.get("dob_estimated") and date_of_birth:
            raise serializers.ValidationError({"dob_estimated": "Estimated age cannot accompany a date of birth."})
        return attrs


class PatientDuplicateCandidateSerializer(serializers.ModelSerializer):
    """Minimal duplicate-decision projection; never serializes a patient chart."""

    display_name = serializers.ReadOnlyField()
    match_score = serializers.IntegerField(source="duplicate_match_score", read_only=True)
    last_visit_date = serializers.DateField(read_only=True, allow_null=True)

    class Meta:
        model = Patient
        fields = ["id", "patient_no", "display_name", "match_score", "last_visit_date", "last_seen_at"]
        read_only_fields = fields


class VisitCheckInSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    department_id = serializers.UUIDField(required=False, allow_null=True)
    visit_type = serializers.ChoiceField(choices=Visit.VISIT_TYPE_CHOICES, default="OUTPATIENT_NEW")
    payer_type = serializers.ChoiceField(choices=[("CASH", "Cash"), ("SELF_PAY_MOMO", "Self-pay mobile money")], default="CASH")
    reason_for_visit = serializers.CharField(required=False, allow_blank=True, max_length=120)
    referral_source_type = serializers.ChoiceField(
        choices=Visit.REFERRAL_SOURCE_CHOICES,
        required=False,
        default="SELF",
    )
    referral_source_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    price_list_id = serializers.UUIDField(required=False, allow_null=True)
    arrival_enquiry_id = serializers.UUIDField(required=False, allow_null=True)
    arrival_enquiry_version = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class VisitSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)

    class Meta:
        model = Visit
        fields = [
            "id",
            "patient",
            "patient_name",
            "facility",
            "local_service_date",
            "visit_type",
            "state",
            "closure_reason",
            "reason_for_visit",
            "opened_at",
            "opened_by",
            "in_progress_at",
            "closed_at",
            "closed_by",
            "payer_binding_id",
            "legacy_source_key",
            "emergency_setup_pending",
            "related_visit",
            "slip_print_count",
            "referral_source_type",
            "referral_source_name",
            "results_review",
            "version",
        ]
        read_only_fields = fields


class ArrivalEnquiryWriteSerializer(serializers.Serializer):
    reason_code = serializers.ChoiceField(choices=ArrivalEnquiry.REASON_CHOICES)
    source_event_id = serializers.CharField(max_length=120)
    safe_notes = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class ArrivalEnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = ArrivalEnquiry
        fields = [
            "id",
            "facility",
            "reason_code",
            "occurred_at",
            "recorded_by",
            "source_event_id",
            "safe_notes",
            "state",
            "converted_visit",
            "converted_by",
            "converted_at",
            "version",
        ]
        read_only_fields = fields


class ReferralSourceSerializer(serializers.Serializer):
    source_type = serializers.ChoiceField(choices=Visit.REFERRAL_SOURCE_CHOICES)
    source_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    expected_version = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class VisitCancelErrorSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=120, allow_blank=False)
    expected_version = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class PatientRegisterResponseSerializer(PatientSerializer):
    patient_id = serializers.UUIDField(required=False)
    next_action = serializers.CharField()
    patient = PatientSerializer(required=False)
    duplicate_candidates = PatientDuplicateCandidateSerializer(many=True, required=False)

    class Meta(PatientSerializer.Meta):
        fields = PatientSerializer.Meta.fields + ["patient_id", "next_action", "patient", "duplicate_candidates"]


class VisitCheckInResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    visit_id = serializers.UUIDField()
    queue_id = serializers.UUIDField(allow_null=True)
    invoice_id = serializers.UUIDField(allow_null=True)
    patient_id = serializers.UUIDField()
    next_action = serializers.CharField()
    visit = VisitSerializer()
    queue = QueueEntrySerializer(allow_null=True)
    invoice = InvoiceSerializer(allow_null=True)
    payer_binding = serializers.DictField()
    arrival_enquiry = ArrivalEnquirySerializer(allow_null=True, required=False)


class ArrivalEnquiryResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    enquiry_id = serializers.UUIDField()
    enquiry = ArrivalEnquirySerializer()


class QueueHistoryEntrySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    queue_label = serializers.CharField()
    department = serializers.UUIDField()
    department_name = serializers.CharField()
    queue_type = serializers.CharField()
    status = serializers.CharField()
    current_stage = serializers.CharField()
    queue_time = serializers.DateTimeField()
    called_at = serializers.DateTimeField(allow_null=True)
    claimed_by = serializers.UUIDField(allow_null=True)
    claimed_by_name = serializers.CharField(allow_null=True)
    claimed_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    hold_reason = serializers.CharField()
    version = serializers.IntegerField()


class InvoiceSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    invoice_no = serializers.CharField()
    status = serializers.CharField()
    currency = serializers.CharField()
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2)
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    amount_paid = serializers.DecimalField(max_digits=14, decimal_places=2)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    issued_at = serializers.DateTimeField(allow_null=True)
    voided_at = serializers.DateTimeField(allow_null=True)
    version = serializers.IntegerField()


class EncounterSummarySerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    status = serializers.CharField()
    clinician = serializers.UUIDField()
    clinician_name = serializers.CharField()
    started_at = serializers.DateTimeField()
    signed_at = serializers.DateTimeField(allow_null=True)
    closed_at = serializers.DateTimeField(allow_null=True)


class VisitContextResponseSerializer(serializers.Serializer):
    visit = VisitSerializer()
    queue_history = QueueHistoryEntrySerializer(many=True)
    invoice = InvoiceSummarySerializer(allow_null=True)
    clinical_summary = EncounterSummarySerializer(many=True)
    clinical = EncounterSerializer(many=True, allow_null=True, required=False)


class VisitCancelErrorResponseSerializer(serializers.Serializer):
    visit_id = serializers.UUIDField()
    visit = VisitSerializer()
    queue_entries = QueueEntrySerializer(many=True)
    invoice = InvoiceSerializer(allow_null=True)


class PatientCheckInSummarySerializer(serializers.Serializer):
    patient = PatientSerializer()
    outstanding_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    outstanding_invoice_no = serializers.CharField(allow_null=True)
    outstanding_visit_id = serializers.UUIDField(allow_null=True)
    active_visit = VisitSerializer(allow_null=True)
    active_queue_label = serializers.CharField(allow_null=True)


__all__ = [
    "ArrivalEnquirySerializer",
    "ArrivalEnquiryWriteSerializer",
    "PatientRegisterSerializer",
    "PatientDuplicateCandidateSerializer",
    "PatientSerializer",
    "ReferralSourceSerializer",
    "VisitCheckInSerializer",
    "VisitCancelErrorSerializer",
    "VisitSerializer",
    "PatientRegisterResponseSerializer",
    "VisitCheckInResponseSerializer",
    "ArrivalEnquiryResponseSerializer",
    "QueueHistoryEntrySerializer",
    "InvoiceSummarySerializer",
    "EncounterSummarySerializer",
    "VisitContextResponseSerializer",
    "VisitCancelErrorResponseSerializer",
    "PatientCheckInSummarySerializer",
]
