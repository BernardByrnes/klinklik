from rest_framework import serializers

from patients.models import Patient, PatientContact, PatientIdentifier, PatientLink


class PatientIdentifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientIdentifier
        fields = ["id", "identifier_type", "value", "verified", "is_primary"]


class PatientContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientContact
        fields = ["id", "relationship", "name", "phone", "is_primary"]


class PatientSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()
    identifiers = PatientIdentifierSerializer(many=True, read_only=True)
    contacts = PatientContactSerializer(many=True, read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id",
            "patient_no",
            "display_name",
            "first_name",
            "middle_name",
            "last_name",
            "sex",
            "date_of_birth",
            "phone",
            "email",
            "address",
            "village",
            "parish",
            "sub_county",
            "district",
            "next_of_kin_name",
            "next_of_kin_phone",
            "estimated_age_years",
            "estimated_age_months",
            "dob_estimated",
            "identity_status",
            "status",
            "last_seen_at",
            "version",
            "identifiers",
            "contacts",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "patient_no",
            "display_name",
            "status",
            "identity_status",
            "last_seen_at",
            "version",
            "identifiers",
            "contacts",
        ]


class PatientCreateSerializer(serializers.ModelSerializer):
    identifier = serializers.DictField(required=False, write_only=True)
    next_of_kin = serializers.DictField(required=False, write_only=True)

    class Meta:
        model = Patient
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "sex",
            "date_of_birth",
            "phone",
            "email",
            "address",
            "village",
            "parish",
            "sub_county",
            "district",
            "next_of_kin_name",
            "next_of_kin_phone",
            "estimated_age_years",
            "estimated_age_months",
            "dob_estimated",
            "identifier",
            "next_of_kin",
        ]


class PatientLinkSerializer(serializers.Serializer):
    target_patient_id = serializers.UUIDField()
    link_type = serializers.ChoiceField(choices=PatientLink.LINK_TYPES)
    reason = serializers.CharField(required=False, allow_blank=True)
