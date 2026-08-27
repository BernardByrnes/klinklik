from django.conf import settings
from django.db import models

from core.models import FacilityScopedModel


class QueueEntry(FacilityScopedModel):
    STATUS_CHOICES = [
        ("WAITING", "Waiting"),
        ("CALLED", "Called"),
        ("IN_TRIAGE", "In triage"),
        ("TRIAGED", "Triaged"),
        ("IN_CONSULTATION", "In consultation"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="queue_entries")
    department = models.ForeignKey("tenancy.Department", on_delete=models.PROTECT, related_name="queue_entries")
    queue_date = models.DateField()
    sequence = models.PositiveIntegerField()
    visit_type = models.CharField(max_length=40, default="WALK_IN")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="WAITING")
    current_stage = models.CharField(max_length=40, default="RECEPTION")
    arrival_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    claimed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="claimed_queue_entries",
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "queue_date", "sequence"],
                name="uniq_queue_sequence_facility_date",
            )
        ]
        indexes = [
            models.Index(fields=["facility", "queue_date", "status"]),
            models.Index(fields=["organisation", "patient", "created_at"]),
        ]

    @property
    def queue_label(self):
        return f"{self.department.code}-{self.sequence:03d}"


class Appointment(FacilityScopedModel):
    STATUS_CHOICES = [
        ("BOOKED", "Booked"),
        ("CHECKED_IN", "Checked in"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
        ("NO_SHOW", "No show"),
    ]

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="appointments")
    department = models.ForeignKey("tenancy.Department", on_delete=models.PROTECT, related_name="appointments")
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="BOOKED")
    reason = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class FollowUpRecommendation(FacilityScopedModel):
    INTERVAL_UNIT_CHOICES = [
        ("DAYS", "Days"),
        ("WEEKS", "Weeks"),
        ("MONTHS", "Months"),
    ]

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="follow_ups")
    encounter = models.ForeignKey(
        "clinical.Encounter", on_delete=models.PROTECT, null=True, blank=True, related_name="follow_ups"
    )
    recommended_date = models.DateField(null=True, blank=True)
    interval_value = models.PositiveIntegerField(null=True, blank=True)
    interval_unit = models.CharField(
        max_length=10,
        choices=INTERVAL_UNIT_CHOICES,
        null=True,
        blank=True,
    )
    instructions = models.TextField()
    status = models.CharField(max_length=20, default="OPEN")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
