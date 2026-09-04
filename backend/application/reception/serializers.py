from rest_framework import serializers

from patients.models import Patient
from patients.serializers import PatientCreateSerializer, PatientSerializer
from scheduling.models import ArrivalEnquiry, Visit


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


__all__ = [
    "ArrivalEnquirySerializer",
    "ArrivalEnquiryWriteSerializer",
    "PatientRegisterSerializer",
    "PatientSerializer",
    "ReferralSourceSerializer",
    "VisitCheckInSerializer",
    "VisitCancelErrorSerializer",
    "VisitSerializer",
]
