from rest_framework import serializers

from clinical.allergies import patient_allergy_snapshot
from clinical.complaints import ComplaintValidationError, normalize_complaints
from clinical.concurrency import consultation_note_etag, consultation_note_for_encounter
from clinical.diagnosis_state import active_diagnosis_snapshot
from clinical.models import Allergy, ClinicalNote, Diagnosis, Encounter, TriageAssessment
from scheduling.models import FollowUpRecommendation
from scheduling.serializers import QueueEntrySerializer


CLINICAL_NOTE_CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        field_name: {"type": "string"}
        for field_name in (
            "consultation",
            "presenting_complaint",
            "hpi",
            "past_medical_history",
            "past_surgical_history",
            "family_history",
            "social_history",
            "general_examination",
            "cardiovascular_examination",
            "respiratory_examination",
            "abdominal_examination",
            "neurological_examination",
            "genitourinary_examination",
            "musculoskeletal_examination",
            "treatment_plan",
        )
    },
    "additionalProperties": True,
}
PRESENTING_COMPLAINT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "duration_value": {"type": "integer", "nullable": True},
        "duration_unit": {
            "type": "string",
            "enum": ["HOURS", "DAYS", "WEEKS", "MONTHS"],
            "nullable": True,
        },
    },
    "required": ["text"],
}
ACTIVE_ALLERGY_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "substance": {"type": "string"},
        "reaction": {"type": "string"},
        "severity": {"type": "string", "enum": ["MILD", "MODERATE", "SEVERE"]},
    },
    "required": ["id", "substance", "reaction", "severity"],
}
DIAGNOSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "encounter": {"type": "string", "format": "uuid"},
        "diagnosis_type": {"type": "string", "enum": ["WORKING", "FINAL", "NO_DIAGNOSIS"]},
        "code": {"type": "string"},
        "label": {"type": "string"},
        "coded": {"type": "boolean"},
        "certainty_note": {"type": "string"},
        "is_primary": {"type": "boolean"},
        "no_diagnosis_reason": {"type": "string"},
        "status": {"type": "string", "enum": ["ACTIVE"]},
        "recorded_by": {"type": "string", "format": "uuid"},
        "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"},
    },
    "required": ["id", "encounter", "diagnosis_type", "code", "label", "coded", "is_primary", "status"],
}
FOLLOW_UP_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "patient": {"type": "string", "format": "uuid"},
        "encounter": {"type": "string", "format": "uuid"},
        "recommended_date": {"type": "string", "format": "date", "nullable": True},
        "interval_value": {"type": "integer", "nullable": True},
        "interval_unit": {"type": "string", "nullable": True},
        "instructions": {"type": "string"},
        "status": {"type": "string"},
        "created_by": {"type": "string", "format": "uuid"},
        "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"},
    },
}


class OpenAPISchemaField(serializers.JSONField):
    """JSON field with its response contract carried into generated OpenAPI."""

    def __init__(self, *, openapi_schema, **kwargs):
        self.openapi_schema = openapi_schema
        super().__init__(**kwargs)


class TriageSerializer(serializers.Serializer):
    acuity = serializers.ChoiceField(choices=TriageAssessment.ACUITY_CHOICES, default="ROUTINE")
    chief_complaint = serializers.CharField(required=False, allow_blank=True)
    observations = serializers.JSONField(required=False, default=dict)
    vitals = serializers.JSONField(required=False, default=dict)


class ClinicalNoteSerializer(serializers.ModelSerializer):
    content = OpenAPISchemaField(openapi_schema=CLINICAL_NOTE_CONTENT_SCHEMA)

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



class DispositionWriteSerializer(serializers.Serializer):
    disposition = serializers.ChoiceField(
        choices=Encounter.DISPOSITION_CHOICES,
        allow_null=True,
        required=True,
    )
    disposition_note = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )


class FollowUpRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUpRecommendation
        fields = [
            "id",
            "patient",
            "encounter",
            "recommended_date",
            "interval_value",
            "interval_unit",
            "instructions",
            "status",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class FollowUpWriteSerializer(serializers.Serializer):
    recommended_date = serializers.DateField(required=False, allow_null=True)
    interval_value = serializers.IntegerField(required=False, allow_null=True)
    interval_unit = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=10)
    instructions = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )


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


class AllergyStatusWriteSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[("NKA", "No known allergies"), ("UNKNOWN", "Unknown")])


class AllergyEnteredInErrorSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, allow_blank=False)


class ProjectedField(serializers.SerializerMethodField):
    """SerializerMethodField with an explicit OpenAPI response shape."""

    def __init__(self, openapi_schema, *args, **kwargs):
        self.openapi_schema = openapi_schema
        super().__init__(*args, **kwargs)


class EncounterSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    notes = ClinicalNoteSerializer(many=True, read_only=True)
    diagnoses = ProjectedField({"type": "array", "items": DIAGNOSIS_SCHEMA})
    complaints = ProjectedField({"type": "array", "items": PRESENTING_COMPLAINT_SCHEMA})
    triage_complaint = ProjectedField({"type": "string", "nullable": True})
    allergy_status = ProjectedField({"type": "string", "enum": ["NOT_RECORDED", "NKA", "UNKNOWN", "RECORDED"]})
    active_allergies = ProjectedField({"type": "array", "items": ACTIVE_ALLERGY_SCHEMA})
    allergy_revision = ProjectedField({"type": "integer"})
    allergy_state_etag = ProjectedField({"type": "string"})
    allergies_reviewed_at = serializers.DateTimeField(read_only=True)
    allergies_reviewed_revision = serializers.IntegerField(read_only=True, allow_null=True)
    allergies_review_is_current = ProjectedField({"type": "boolean"})
    consultation_etag = ProjectedField({"type": "string"})
    follow_up = ProjectedField({**FOLLOW_UP_SCHEMA, "nullable": True})

    def _allergy_snapshot(self, obj):
        if not hasattr(obj, "_allergy_snapshot"):
            obj._allergy_snapshot = patient_allergy_snapshot(
                organisation=obj.organisation,
                facility=obj.facility,
                patient=obj.patient,
            )
        return obj._allergy_snapshot

    def get_diagnoses(self, obj):
        if hasattr(obj, "_diagnosis_snapshot_for_serialization"):
            return obj._diagnosis_snapshot_for_serialization
        return active_diagnosis_snapshot(obj)

    def get_complaints(self, obj):
        return obj.complaints

    def get_triage_complaint(self, obj):
        if hasattr(obj, "_triage_complaint_for_serialization"):
            return obj._triage_complaint_for_serialization
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
        note = getattr(obj, "_consultation_note_for_serialization", None)
        if not hasattr(obj, "_consultation_note_for_serialization"):
            note = consultation_note_for_encounter(obj)
        return consultation_note_etag(encounter=obj, note=note)

    def get_follow_up(self, obj):
        follow_up = getattr(obj, "_follow_up_for_serialization", None)
        if not hasattr(obj, "_follow_up_for_serialization"):
            from clinical.concurrency import follow_up_recommendation_for_encounter

            follow_up = follow_up_recommendation_for_encounter(obj)
        return FollowUpRecommendationSerializer(follow_up).data if follow_up is not None else None

    class Meta:
        model = Encounter
        fields = [
            "id", "encounter_no", "patient", "patient_name", "visit", "queue_entry", "complaints", "triage_complaint",
            "allergy_status", "active_allergies", "allergy_revision", "allergy_state_etag",
            "allergies_reviewed_at", "allergies_reviewed_revision", "allergies_review_is_current",
            "facility", "clinician", "status", "disposition", "disposition_note", "started_at", "signed_at", "closed_at", "notes", "diagnoses",
            "follow_up", "consultation_etag",
        ]


class EncounterCreateSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField()


class TriageResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    queue_entry = QueueEntrySerializer()
    acuity = serializers.ChoiceField(choices=TriageAssessment.ACUITY_CHOICES)
    chief_complaint = serializers.CharField()
    observations = serializers.JSONField()


class AllergyStateResponseSerializer(serializers.Serializer):
    patient = serializers.UUIDField(required=False)
    allergy = OpenAPISchemaField(openapi_schema=ACTIVE_ALLERGY_SCHEMA, required=False)
    allergy_status = serializers.CharField()
    active_allergies = serializers.ListField(child=OpenAPISchemaField(openapi_schema=ACTIVE_ALLERGY_SCHEMA))
    allergy_revision = serializers.IntegerField()
    allergy_state_etag = serializers.CharField()
    allergies_reviewed_at = serializers.DateTimeField(required=False)
    allergies_reviewed_revision = serializers.IntegerField(required=False, allow_null=True)
    allergies_review_is_current = serializers.BooleanField(required=False)


class DiagnosisStateResponseSerializer(serializers.Serializer):
    diagnoses = serializers.ListField(child=OpenAPISchemaField(openapi_schema=DIAGNOSIS_SCHEMA))
    consultation_etag = serializers.CharField()


class DispositionResponseSerializer(serializers.Serializer):
    disposition = serializers.CharField(allow_null=True)
    disposition_note = serializers.CharField()
    consultation_etag = serializers.CharField()
    encounter_status = serializers.CharField()


class FollowUpStateResponseSerializer(serializers.Serializer):
    follow_up = OpenAPISchemaField(openapi_schema={**FOLLOW_UP_SCHEMA, "nullable": True}, allow_null=True)
    consultation_etag = serializers.CharField()
    encounter_status = serializers.CharField()


class NoteResponseSerializer(serializers.Serializer):
    note = serializers.UUIDField()
    status = serializers.CharField()
    content = OpenAPISchemaField(openapi_schema=CLINICAL_NOTE_CONTENT_SCHEMA)
    complaints = serializers.ListField(child=OpenAPISchemaField(openapi_schema=PRESENTING_COMPLAINT_SCHEMA))
    etag = serializers.CharField()
    saved_at = serializers.DateTimeField()
    current_version = serializers.IntegerField(required=False)
