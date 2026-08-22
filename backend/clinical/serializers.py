from rest_framework import serializers

from clinical.complaints import ComplaintValidationError, normalize_complaints
from clinical.concurrency import consultation_note_etag, consultation_note_for_encounter
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
        "general_examination": 2000,
        "cardiovascular_examination": 2000,
        "respiratory_examination": 2000,
        "abdominal_examination": 2000,
        "neurological_examination": 2000,
        "genitourinary_examination": 2000,
        "musculoskeletal_examination": 2000,
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
    complaints = serializers.JSONField(required=False)

    def validate_content(self, value):
        return validate_note_content(value)

    def validate_complaints(self, value):
        try:
            return normalize_complaints(value)
        except ComplaintValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class NoteAmendSerializer(serializers.Serializer):
    content = serializers.DictField()
    reason = serializers.CharField(min_length=3)

    def validate_content(self, value):
        return validate_note_content(value)


class EncounterSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    notes = ClinicalNoteSerializer(many=True, read_only=True)
    complaints = serializers.JSONField(read_only=True)
    triage_complaint = serializers.SerializerMethodField()
    consultation_etag = serializers.SerializerMethodField()

    def get_triage_complaint(self, obj):
        if obj.queue_entry_id is None:
            return None
        return TriageAssessment.objects.filter(
            organisation=obj.organisation_id,
            facility=obj.facility_id,
            queue_entry_id=obj.queue_entry_id,
        ).values_list("chief_complaint", flat=True).first()

    def get_consultation_etag(self, obj):
        return consultation_note_etag(encounter=obj, note=consultation_note_for_encounter(obj))

    class Meta:
        model = Encounter
        fields = [
            "id", "encounter_no", "patient", "patient_name", "queue_entry", "complaints", "triage_complaint", "facility",
            "clinician", "status", "started_at", "signed_at", "closed_at", "notes", "consultation_etag",
        ]
