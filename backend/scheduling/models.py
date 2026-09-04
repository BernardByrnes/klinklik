from django.conf import settings
from django.db import models

from core.clock import now
from core.models import FacilityScopedModel


class Visit(FacilityScopedModel):
    VISIT_TYPE_CHOICES = [
        ("OUTPATIENT_NEW", "Outpatient new"),
        ("OUTPATIENT_REVIEW", "Outpatient review"),
        ("ANC", "ANC"),
        ("LAB_ONLY", "Lab only"),
        ("PHARMACY_ONLY", "Pharmacy only"),
        ("FOLLOW_UP_RESULTS", "Follow-up results"),
    ]
    STATE_CHOICES = [
        ("OPEN", "Open"),
        ("IN_PROGRESS", "In progress"),
        ("CLOSED", "Closed"),
        ("CANCELLED_ERROR", "Cancelled in error"),
    ]
    REFERRAL_SOURCE_CHOICES = [
        ("SELF", "Self"),
        ("REFERRED_FACILITY", "Referred facility"),
        ("REFERRED_PERSON", "Referred person"),
        ("CAMP_OUTREACH", "Camp/outreach"),
        ("WALK_BY", "Walk-by"),
    ]

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="visits")
    local_service_date = models.DateField()
    visit_type = models.CharField(max_length=40, choices=VISIT_TYPE_CHOICES)
    state = models.CharField(max_length=30, choices=STATE_CHOICES, default="OPEN")
    closure_reason = models.CharField(max_length=120, blank=True)
    reason_for_visit = models.CharField(max_length=120, blank=True)
    opened_at = models.DateTimeField(default=now)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="opened_visits",
    )
    in_progress_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="closed_visits",
    )
    payer_binding_id = models.UUIDField(null=True, blank=True)
    legacy_source_key = models.CharField(max_length=160, null=True, blank=True)
    emergency_setup_pending = models.BooleanField(default=False)
    related_visit = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="related_visits",
    )
    slip_print_count = models.PositiveIntegerField(default=0)
    referral_source_type = models.CharField(
        max_length=30,
        choices=REFERRAL_SOURCE_CHOICES,
        default="SELF",
    )
    referral_source_name = models.CharField(max_length=100, blank=True)
    results_review = models.BooleanField(default=False)
    version = models.PositiveBigIntegerField(default=1)

    ACTIVE_STATES = ("OPEN", "IN_PROGRESS")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "facility", "patient", "local_service_date"],
                condition=models.Q(state__in=["OPEN", "IN_PROGRESS"]),
                name="uniq_active_visit_patient_facility_day",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        state__in=["OPEN", "IN_PROGRESS"],
                        closed_at__isnull=True,
                        closed_by__isnull=True,
                        closure_reason="",
                    )
                    | models.Q(
                        state__in=["CLOSED", "CANCELLED_ERROR"],
                        closed_at__isnull=False,
                        closed_by__isnull=False,
                        closure_reason__gt="",
                    )
                ),
                name="visit_closure_fields_match_state",
            ),
            models.UniqueConstraint(
                fields=["organisation", "legacy_source_key"],
                condition=models.Q(legacy_source_key__isnull=False),
                name="uniq_visit_legacy_source_key",
            ),
        ]
        indexes = [
            models.Index(fields=["organisation", "facility", "local_service_date", "state"]),
            models.Index(fields=["organisation", "patient", "created_at"]),
        ]


class ArrivalEnquiry(FacilityScopedModel):
    REASON_CHOICES = [
        ("NO_CLINICIAN", "No clinician"),
        ("SERVICE_UNAVAILABLE", "Service unavailable"),
        ("PRICE", "Price"),
        ("REFERRED_OUT", "Referred out"),
        ("OTHER", "Other"),
    ]
    STATE_CHOICES = [("OPEN", "Open"), ("CONVERTED", "Converted")]

    reason_code = models.CharField(max_length=30, choices=REASON_CHOICES)
    occurred_at = models.DateTimeField(default=now)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_arrival_enquiries",
    )
    source_event_id = models.CharField(max_length=120)
    safe_notes = models.TextField(blank=True)
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default="OPEN")
    converted_visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="arrival_enquiries",
    )
    converted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="converted_arrival_enquiries",
    )
    converted_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "source_event_id"],
                name="uniq_arrival_enquiry_org_source",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        state="OPEN",
                        converted_visit__isnull=True,
                        converted_by__isnull=True,
                        converted_at__isnull=True,
                    )
                    | models.Q(
                        state="CONVERTED",
                        converted_visit__isnull=False,
                        converted_by__isnull=False,
                        converted_at__isnull=False,
                    )
                ),
                name="arrival_enquiry_conversion_fields_match_state",
            ),
        ]
        indexes = [
            models.Index(fields=["organisation", "facility", "occurred_at"]),
            models.Index(fields=["organisation", "facility", "state"]),
        ]


class QueueEntry(FacilityScopedModel):
    STATUS_CHOICES = [
        ("WAITING", "Waiting"),
        ("WAITING_PAYMENT", "Waiting for payment"),
        ("ON_HOLD", "On hold"),
        ("READY_TO_RESUME", "Ready to resume"),
        ("CALLED", "Called"),
        ("IN_TRIAGE", "In triage"),
        ("TRIAGED", "Triaged"),
        ("IN_CONSULTATION", "In consultation"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    visit = models.ForeignKey(
        Visit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="queue_entries",
    )
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="queue_entries")
    department = models.ForeignKey("tenancy.Department", on_delete=models.PROTECT, related_name="queue_entries")
    queue_date = models.DateField()
    sequence = models.PositiveIntegerField()
    queue_type = models.CharField(max_length=40, default="TRIAGE")
    work_identity = models.CharField(max_length=120, default="")
    hold_reason = models.CharField(max_length=120, blank=True)
    priority = models.CharField(max_length=20, default="ROUTINE")
    priority_changed_at = models.DateTimeField(null=True, blank=True)
    priority_reason = models.CharField(max_length=240, blank=True)
    visit_type = models.CharField(max_length=40, default="WALK_IN")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="WAITING")
    current_stage = models.CharField(max_length=40, default="RECEPTION")
    arrival_at = models.DateTimeField(auto_now_add=True)
    queue_time = models.DateTimeField(default=now)
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
    source_event_id = models.CharField(max_length=120, default="")
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "queue_date", "sequence"],
                name="uniq_queue_sequence_facility_date",
            ),
            models.UniqueConstraint(
                fields=["organisation", "facility", "visit", "queue_type", "work_identity"],
                condition=models.Q(visit__isnull=False, work_identity__gt=""),
                name="uniq_visit_queue_work_identity",
            ),
        ]
        indexes = [
            models.Index(fields=["facility", "queue_date", "status"]),
            models.Index(fields=["organisation", "patient", "created_at"]),
        ]

    @property
    def queue_label(self):
        return f"{self.department.code}-{self.sequence:03d}"

    @property
    def state(self):
        """Compatibility alias while the legacy queue field is expanded in place."""

        return self.status


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
