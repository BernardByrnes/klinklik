from rest_framework import serializers

from clinical.allergies import patient_allergy_snapshot
from clinical.complaints import ComplaintValidationError, normalize_complaints
from clinical.concurrency import consultation_note_etag, consultation_note_for_encounter
from clinical.diagnosis_state import active_diagnosis_snapshot
from clinical.models import Allergy, ClinicalNote, Diagnosis, Encounter, TriageAssessment


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


class DiagnosisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diagnosis
        fields = [
            "id", "encounter", "diagnosis_type", "code", "label", "coded", "certainty_note",
            "is_primary", "no_diagnosis_reason", "status", "recorded_by", "created_at", "updated_at",
            "removed_by", "removed_at",
        ]
        read_only_fields = [
            "id", "encounter", "coded", "status", "recorded_by", "created_at", "updated_at",
            "removed_by", "removed_at",
        ]


class DiagnosisWriteSerializer(serializers.Serializer):
    diagnosis_type = serializers.ChoiceField(choices=Diagnosis.TYPE_CHOICES, required=False, default="FINAL")
    code = serializers.CharField(max_length=40, required=False, allow_blank=True)
    label = serializers.CharField(max_length=200, required=False, allow_blank=True)
    certainty_note = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    is_primary = serializers.BooleanField(required=False, default=False)
    no_diagnosis_reason = serializers.CharField(max_length=4000, required=False, allow_blank=True)



def validate_note_content(value):
    for field_name, max_length in {
        "presenting_complaint": 500,
        "hpi": 4000,
        "past_medical_history": 4000,
        "past_surgical_history": 4000,
        "family_history": 4000,
        "social_history": 4000,
        "treatment_plan": 4000,
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


class AllergyCreateSerializer(serializers.Serializer):
    substance = serializers.CharField(max_length=150, allow_blank=False)
    reaction = serializers.CharField(max_length=200, required=False, allow_blank=True)
    severity = serializers.ChoiceField(choices=Allergy.SEVERITY_CHOICES)


class AllergyStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[("NKA", "No known allergies"), ("UNKNOWN", "Unknown")])


class AllergyEnteredInErrorSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, allow_blank=False)


class EncounterSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    notes = ClinicalNoteSerializer(many=True, read_only=True)
    diagnoses = serializers.SerializerMethodField()
    complaints = serializers.JSONField(read_only=True)
    triage_complaint = serializers.SerializerMethodField()
    allergy_status = serializers.SerializerMethodField()
    active_allergies = serializers.SerializerMethodField()
    allergy_revision = serializers.SerializerMethodField()
    allergy_state_etag = serializers.SerializerMethodField()
    allergies_reviewed_at = serializers.DateTimeField(read_only=True)
    allergies_reviewed_revision = serializers.IntegerField(read_only=True, allow_null=True)
    allergies_review_is_current = serializers.SerializerMethodField()
    consultation_etag = serializers.SerializerMethodField()

    def _allergy_snapshot(self, obj):
        if not hasattr(obj, "_allergy_snapshot"):
            obj._allergy_snapshot = patient_allergy_snapshot(
                organisation=obj.organisation,
                facility=obj.facility,
                patient=obj.patient,
            )
        return obj._allergy_snapshot

    def get_diagnoses(self, obj):
        return active_diagnosis_snapshot(obj)

    def get_triage_complaint(self, obj):
        if obj.queue_entry_id is None:
            return None
        return TriageAssessment.objects.filter(
            organisation=obj.organisation_id,
            facility=obj.facility_id,
            queue_entry_id=obj.queue_entry_id,
        ).values_list("chief_complaint", flat=True).first()

    def get_allergy_status(self, obj):
        return self._allergy_snapshot(obj)["status"]

    def get_active_allergies(self, obj):
        return self._allergy_snapshot(obj)["active_allergies"]

    def get_allergy_revision(self, obj):
        return self._allergy_snapshot(obj)["revision"]

    def get_allergy_state_etag(self, obj):
        return self._allergy_snapshot(obj)["etag"]

    def get_allergies_review_is_current(self, obj):
        snapshot = self._allergy_snapshot(obj)
        return (
            snapshot["status"] != "NOT_RECORDED"
            and obj.allergies_reviewed_at is not None
            and obj.allergies_reviewed_revision == snapshot["revision"]
        )

    def get_consultation_etag(self, obj):
        return consultation_note_etag(encounter=obj, note=consultation_note_for_encounter(obj))

    class Meta:
        model = Encounter
        fields = [
            "id", "encounter_no", "patient", "patient_name", "queue_entry", "complaints", "triage_complaint",
            "allergy_status", "active_allergies", "allergy_revision", "allergy_state_etag",
            "allergies_reviewed_at", "allergies_reviewed_revision", "allergies_review_is_current",
            "facility", "clinician", "status", "started_at", "signed_at", "closed_at", "notes", "diagnoses",
            "consultation_etag",
        ]
