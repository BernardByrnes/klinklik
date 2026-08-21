from rest_framework import serializers

from clinical.models import ClinicalNote, Encounter, TriageAssessment


class TriageSerializer(serializers.Serializer):
    acuity = serializers.ChoiceField(choices=TriageAssessment.ACUITY_CHOICES, default="ROUTINE")
    chief_complaint = serializers.CharField(required=False, allow_blank=True)
    observations = serializers.JSONField(required=False, default=dict)
    vitals = serializers.JSONField(required=False, default=dict)


class ClinicalNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalNote
        fields = ["id", "note_type", "content", "status", "author", "signed_by", "signed_at", "current_version"]
        read_only_fields = ["id", "status", "author", "signed_by", "signed_at", "current_version"]


def validate_note_content(value):
    for field_name, max_length in {
        "presenting_complaint": 500,
        "hpi": 4000,
        "past_medical_history": 4000,
        "past_surgical_history": 4000,
        "family_history": 4000,
        "social_history": 4000,
    }.items():
        if field_name not in value:
            continue
        if not isinstance(value[field_name], str):
            raise serializers.ValidationError({field_name: "This field must be text."})
        if len(value[field_name]) > max_length:
            raise serializers.ValidationError({field_name: f"This field must be {max_length} characters or fewer."})
    return value


class NoteWriteSerializer(serializers.Serializer):
    content = serializers.DictField()

    def validate_content(self, value):
        return validate_note_content(value)


class NoteAmendSerializer(serializers.Serializer):
    content = serializers.DictField()
    reason = serializers.CharField(min_length=3)

    def validate_content(self, value):
        return validate_note_content(value)


class EncounterSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    notes = ClinicalNoteSerializer(many=True, read_only=True)

    class Meta:
        model = Encounter
        fields = [
            "id", "encounter_no", "patient", "patient_name", "queue_entry", "facility",
            "clinician", "status", "started_at", "signed_at", "closed_at", "notes",
        ]
