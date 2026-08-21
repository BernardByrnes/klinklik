from django.conf import settings
from django.db import models

from core.models import FacilityScopedModel, OrganisationScopedModel


class Encounter(FacilityScopedModel):
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("SIGNED", "Signed"),
        ("CLOSED", "Closed"),
        ("CANCELLED", "Cancelled"),
    ]

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="encounters")
    queue_entry = models.OneToOneField(
        "scheduling.QueueEntry", on_delete=models.PROTECT, null=True, blank=True, related_name="encounter"
    )
    encounter_no = models.CharField(max_length=50)
    clinician = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="clinical_encounters"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    started_at = models.DateTimeField(auto_now_add=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organisation", "encounter_no"], name="uniq_encounter_org_no")
        ]


class ClinicalNote(FacilityScopedModel):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SIGNED", "Signed"),
        ("AMENDED", "Amended"),
    ]

    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name="notes")
    note_type = models.CharField(max_length=40, default="CONSULTATION")
    content = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_notes")
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="signed_notes",
    )
    signed_at = models.DateTimeField(null=True, blank=True)
    current_version = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["encounter", "note_type"], name="uniq_clinical_note_encounter_type")
        ]


class ClinicalNoteVersion(OrganisationScopedModel):
    note = models.ForeignKey(ClinicalNote, on_delete=models.PROTECT, related_name="versions")
    version_number = models.PositiveIntegerField()
    content = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["note", "version_number"], name="uniq_note_version")
        ]


class TriageAssessment(FacilityScopedModel):
    ACUITY_CHOICES = [
        ("ROUTINE", "Routine"),
        ("URGENT", "Urgent"),
        ("EMERGENCY", "Emergency"),
    ]

    queue_entry = models.OneToOneField(
        "scheduling.QueueEntry", on_delete=models.PROTECT, related_name="triage_assessment"
    )
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="triage_assessments")
    acuity = models.CharField(max_length=20, choices=ACUITY_CHOICES, default="ROUTINE")
    chief_complaint = models.TextField(blank=True)
    observations = models.JSONField(default=dict)
    assessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)


class VitalsObservation(FacilityScopedModel):
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="vitals")
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name="vitals", null=True, blank=True)
    measured_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    systolic = models.PositiveSmallIntegerField(null=True, blank=True)
    diastolic = models.PositiveSmallIntegerField(null=True, blank=True)
    pulse = models.PositiveSmallIntegerField(null=True, blank=True)
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    respiratory_rate = models.PositiveSmallIntegerField(null=True, blank=True)
    oxygen_saturation = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    measured_at = models.DateTimeField(auto_now_add=True)


class Diagnosis(FacilityScopedModel):
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name="diagnoses")
    code = models.CharField(max_length=40, blank=True)
    label = models.CharField(max_length=200)
    status = models.CharField(max_length=20, default="ACTIVE")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class Allergy(FacilityScopedModel):
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="allergies")
    substance = models.CharField(max_length=150)
    reaction = models.CharField(max_length=200, blank=True)
    severity = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, default="ACTIVE")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class Procedure(FacilityScopedModel):
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name="procedures")
    name = models.CharField(max_length=200)
    outcome = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class Referral(FacilityScopedModel):
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name="referrals")
    destination = models.CharField(max_length=200)
    reason = models.TextField()
    status = models.CharField(max_length=20, default="OPEN")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
