from django.conf import settings
from django.db import models

from core.models import FacilityScopedModel, OrganisationScopedModel


class Patient(OrganisationScopedModel):
    SEX_CHOICES = [
        ("FEMALE", "Female"),
        ("MALE", "Male"),
        ("INTERSEX", "Intersex"),
        ("UNKNOWN", "Unknown"),
        ("NOT_STATED", "Not stated"),
    ]
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("DECEASED", "Deceased"),
        ("ARCHIVED", "Archived"),
    ]

    patient_no = models.CharField(max_length=40)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    sex = models.CharField(max_length=20, choices=SEX_CHOICES, default="NOT_STATED")
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    deceased_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organisation", "patient_no"], name="uniq_patient_org_no")
        ]
        indexes = [
            models.Index(fields=["organisation", "last_name", "first_name"]),
            models.Index(fields=["organisation", "phone"]),
        ]

    @property
    def display_name(self):
        return " ".join(part for part in [self.first_name, self.middle_name, self.last_name] if part).strip()


class PatientIdentifier(OrganisationScopedModel):
    IDENTIFIER_TYPES = [
        ("NATIONAL_ID", "National ID"),
        ("PASSPORT", "Passport"),
        ("INSURANCE", "Insurance"),
        ("OTHER", "Other"),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="identifiers")
    identifier_type = models.CharField(max_length=30, choices=IDENTIFIER_TYPES)
    value = models.CharField(max_length=150)
    normalized_value = models.CharField(max_length=150)
    verified = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "identifier_type", "normalized_value"],
                name="uniq_patient_identifier_org_value",
            )
        ]


class PatientContact(OrganisationScopedModel):
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="contacts")
    relationship = models.CharField(max_length=80)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=40)
    is_primary = models.BooleanField(default=False)


class PatientLink(OrganisationScopedModel):
    LINK_TYPES = [
        ("SUSPECTED_DUPLICATE", "Suspected duplicate"),
        ("RELATED", "Related"),
        ("EMERGENCY_CONTACT", "Emergency contact"),
    ]
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("CONFIRMED", "Confirmed"),
        ("REJECTED", "Rejected"),
    ]

    source_patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="outgoing_links")
    target_patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="incoming_links")
    link_type = models.CharField(max_length=30, choices=LINK_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_patient_links"
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_patient_links",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "source_patient", "target_patient", "link_type"],
                name="uniq_patient_link",
            )
        ]


class Consent(OrganisationScopedModel):
    CONSENT_TYPES = [
        ("TREATMENT", "Treatment"),
        ("DATA_PROCESSING", "Data processing"),
        ("COMMUNICATION", "Communication"),
    ]
    STATUS_CHOICES = [("GRANTED", "Granted"), ("WITHDRAWN", "Withdrawn")]

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="consents")
    consent_type = models.CharField(max_length=30, choices=CONSENT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="GRANTED")
    captured_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    captured_at = models.DateTimeField(auto_now_add=True)
    notice_version = models.CharField(max_length=50, blank=True)
