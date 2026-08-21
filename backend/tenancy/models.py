from django.db import models
from core.models import OrganisationScopedModel, FacilityScopedModel, UUIDModel


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
