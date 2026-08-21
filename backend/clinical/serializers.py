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


class NoteWriteSerializer(serializers.Serializer):
    content = serializers.JSONField()


class NoteAmendSerializer(serializers.Serializer):
    content = serializers.JSONField()
    reason = serializers.CharField(min_length=3)


class EncounterSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    notes = ClinicalNoteSerializer(many=True, read_only=True)

    class Meta:
        model = Encounter
        fields = [
            "id", "encounter_no", "patient", "patient_name", "queue_entry", "facility",
            "clinician", "status", "started_at", "signed_at", "closed_at", "notes",
        ]
