from django.core.exceptions import ValidationError
from django.db import models
from core.models import OrganisationScopedModel, FacilityScopedModel, UUIDModel


def default_option_list():
    return []


class Organisation(UUIDModel):
    STATUS_CHOICES = [("ACTIVE", "Active"), ("SUSPENDED", "Suspended"), ("CLOSED", "Closed")]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    timezone = models.CharField(max_length=64, default="Africa/Kampala")
    default_currency = models.CharField(max_length=3, default="UGX")
    privacy_notice_version = models.CharField(max_length=50, default="v1")
    dpo_email = models.EmailField(blank=True)

    def __str__(self):
        return self.name


class Facility(OrganisationScopedModel):
    MODE_CHOICES = [
        ("CLINIC", "Clinic"),
        ("PHARMACY", "Pharmacy"),
        ("CLINIC_PHARMACY", "Clinic + Pharmacy"),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=40)
    mode = models.CharField(max_length=30, choices=MODE_CHOICES, default="CLINIC")
    timezone = models.CharField(max_length=64, default="Africa/Kampala")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organisation", "code"], name="uniq_facility_org_code")
        ]

    def __str__(self):
        return self.name


class Department(FacilityScopedModel):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=40)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["facility", "code"], name="uniq_department_facility_code")
        ]


class Module(UUIDModel):
    code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=120)


class FacilityModule(OrganisationScopedModel):
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="enabled_modules")
    module = models.ForeignKey(Module, on_delete=models.PROTECT, related_name="facility_modules")
    enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["facility", "module"], name="uniq_facility_module")
        ]


class Subscription(OrganisationScopedModel):
    STATUS_CHOICES = [
        ("TRIAL", "Trial"),
        ("ACTIVE", "Active"),
        ("PAST_DUE", "Past due"),
        ("CANCELLED", "Cancelled"),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="TRIAL")
    valid_until = models.DateTimeField(null=True, blank=True)


class FacilityWorkflowPolicy(FacilityScopedModel):
    """Typed, inert configuration seam reserved for later authorized slices."""

    CONSULTATION_PAYMENT_TIMINGS = [
        ("PAY_AFTER", "Pay after consultation"),
        ("PAY_BEFORE_TRIAGE", "Pay before triage"),
    ]

    PUBLIC_BOARD_MODES = [
        ("PATIENT_NUMBER", "Patient number"),
        ("FIRST_NAME_INITIAL", "First-name initial"),
    ]

    queue_call_expiry_minutes = models.PositiveIntegerField(default=10)
    queue_no_show_final_attempts = models.PositiveIntegerField(default=3)
    consultation_payment_timing = models.CharField(
        max_length=30,
        choices=CONSULTATION_PAYMENT_TIMINGS,
        default="PAY_AFTER",
    )
    public_board_identity_mode = models.CharField(
        max_length=32,
        choices=PUBLIC_BOARD_MODES,
        null=True,
        blank=True,
    )
    triage_complaint_options = models.JSONField(default=default_option_list)
    chronic_condition_options = models.JSONField(default=default_option_list)
    examination_system_options = models.JSONField(default=default_option_list)
    prescription_duration_warning_days = models.PositiveIntegerField(default=90)
    inventory_expiry_warning_horizon_days = models.PositiveIntegerField(default=90)
    blind_stock_count = models.BooleanField(default=True)
    prescription_uncollected_window_days = models.PositiveIntegerField(default=7)
    counselling_point_options = models.JSONField(default=default_option_list)
    discount_reason_options = models.JSONField(default=default_option_list)
    discount_approval_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    cashier_shift_stale_after_minutes = models.PositiveIntegerField(null=True, blank=True)
    cashier_variance_alert_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    lab_allow_self_verification = models.BooleanField(default=False)
    version = models.PositiveBigIntegerField(default=1)
    updated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="updated_workflow_policies",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["facility"], name="uniq_workflow_policy_facility"),
            models.CheckConstraint(
                condition=models.Q(queue_call_expiry_minutes__gt=0),
                name="workflow_policy_queue_expiry_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(queue_no_show_final_attempts__gt=0),
                name="workflow_policy_no_show_attempts_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(public_board_identity_mode__isnull=True)
                | models.Q(public_board_identity_mode__in=["PATIENT_NUMBER", "FIRST_NAME_INITIAL"]),
                name="workflow_policy_board_identity_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(prescription_duration_warning_days__gt=0),
                name="workflow_policy_prescription_warning_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(inventory_expiry_warning_horizon_days__gt=0),
                name="workflow_policy_inventory_warning_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(prescription_uncollected_window_days__gt=0),
                name="workflow_policy_uncollected_window_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_approval_threshold__isnull=True)
                | models.Q(discount_approval_threshold__gte=0),
                name="workflow_policy_discount_threshold_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(cashier_variance_alert_threshold__isnull=True)
                | models.Q(cashier_variance_alert_threshold__gte=0),
                name="workflow_policy_variance_threshold_nonnegative",
            ),
        ]

    def clean(self):
        super().clean()
        if self.facility_id and self.organisation_id:
            if self.facility.organisation_id != self.organisation_id:
                raise ValidationError("Facility and organisation must belong to the same tenant.")
        for field_name in (
            "triage_complaint_options",
            "chronic_condition_options",
            "examination_system_options",
            "counselling_point_options",
            "discount_reason_options",
        ):
            if not isinstance(getattr(self, field_name), list):
                raise ValidationError({field_name: "Options must be a JSON list."})

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)
