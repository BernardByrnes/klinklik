from decimal import Decimal

from django.conf import settings
from django.db import models

from core.clock import now
from core.models import FacilityScopedModel


class LabTestDefinition(FacilityScopedModel):
    RESULT_TYPES = [
        ("NUMERIC", "Numeric"),
        ("CODED", "Coded"),
        ("TEXT", "Text"),
        ("PANEL", "Panel"),
    ]

    code = models.CharField(max_length=60)
    name = models.CharField(max_length=160)
    specimen_type = models.CharField(max_length=80, default="BLOOD")
    result_type = models.CharField(max_length=20, choices=RESULT_TYPES, default="NUMERIC")
    service = models.ForeignKey(
        "billing.ServiceCatalogItem",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lab_tests",
    )
    turnaround_minutes = models.PositiveIntegerField(default=60)
    coded_options = models.JSONField(default=list)
    text_template = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    definition_version = models.PositiveBigIntegerField(default=1)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "facility", "code"],
                name="uniq_lab_test_facility_code",
            )
        ]


class LabAnalyteDefinition(FacilityScopedModel):
    test = models.ForeignKey(
        LabTestDefinition, on_delete=models.PROTECT, related_name="analytes"
    )
    code = models.CharField(max_length=60)
    name = models.CharField(max_length=160)
    unit = models.CharField(max_length=40, blank=True)
    result_type = models.CharField(max_length=20, default="NUMERIC")
    sequence = models.PositiveIntegerField(default=1)
    sanity_min = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True
    )
    sanity_max = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True
    )
    coded_options = models.JSONField(default=list)
    active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["test", "code"], name="uniq_lab_analyte_test_code"
            )
        ]


class LabReferenceRange(FacilityScopedModel):
    analyte = models.ForeignKey(
        LabAnalyteDefinition, on_delete=models.PROTECT, related_name="ranges"
    )
    sex = models.CharField(max_length=20, default="ANY")
    age_min_days = models.PositiveIntegerField(default=0)
    age_max_days = models.PositiveIntegerField(null=True, blank=True)
    low = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    high = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    text = models.CharField(max_length=160, blank=True)
    validated = models.BooleanField(default=False)
    source_version = models.CharField(max_length=60, default="v1")
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["analyte", "sex", "age_min_days", "age_max_days", "source_version"],
                name="uniq_lab_range_scope_version",
            )
        ]


class LabOrder(FacilityScopedModel):
    PRIORITIES = [("ROUTINE", "Routine"), ("URGENT", "Urgent")]

    visit = models.ForeignKey(
        "scheduling.Visit", on_delete=models.PROTECT, related_name="lab_orders"
    )
    encounter = models.ForeignKey(
        "clinical.Encounter",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lab_orders",
    )
    ordered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lab_orders"
    )
    priority = models.CharField(max_length=20, choices=PRIORITIES, default="ROUTINE")
    clinical_notes = models.TextField(blank=True)
    source_event_id = models.CharField(max_length=120)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "source_event_id"],
                name="uniq_lab_order_source",
            )
        ]


class LabOrderItem(FacilityScopedModel):
    STATES = [
        ("ORDERED", "Ordered"),
        ("AWAITING_PAYMENT", "Awaiting payment"),
        ("READY_FOR_COLLECTION", "Ready for collection"),
        ("SAMPLE_COLLECTED", "Sample collected"),
        ("SAMPLE_REJECTED", "Sample rejected"),
        ("RESULT_ENTERED", "Result entered"),
        ("RELEASED", "Released"),
        ("CANCELLED", "Cancelled"),
        ("REFERRED_OUT", "Referred out"),
    ]

    order = models.ForeignKey(LabOrder, on_delete=models.PROTECT, related_name="items")
    test = models.ForeignKey(
        LabTestDefinition, on_delete=models.PROTECT, related_name="order_items"
    )
    state = models.CharField(max_length=30, choices=STATES, default="ORDERED")
    priority = models.CharField(max_length=20, default="ROUTINE")
    price_snapshot = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="UGX")
    invoice_line = models.ForeignKey(
        "billing.InvoiceItem",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lab_order_items",
    )
    specimen_id = models.CharField(max_length=60, blank=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="collected_lab_items",
    )
    collected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=240, blank=True)
    referred_to = models.CharField(max_length=160, blank=True)
    referred_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "test"], name="uniq_lab_order_test"
            )
        ]


class LabResult(FacilityScopedModel):
    item = models.OneToOneField(
        LabOrderItem, on_delete=models.PROTECT, related_name="result"
    )
    state = models.CharField(max_length=20, default="DRAFT")
    current_version = models.PositiveIntegerField(default=0)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entered_lab_results",
    )
    entered_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verified_lab_results",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    self_verified = models.BooleanField(default=False)
    version = models.PositiveBigIntegerField(default=1)


class LabResultVersion(FacilityScopedModel):
    result = models.ForeignKey(
        LabResult, on_delete=models.PROTECT, related_name="versions"
    )
    version_no = models.PositiveIntegerField()
    values = models.JSONField(default=list)
    comments = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lab_result_versions",
    )
    entered_at = models.DateTimeField(default=now)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verified_lab_result_versions",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    released = models.BooleanField(default=False)
    amendment_reason = models.CharField(max_length=240, blank=True)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseding_versions",
    )
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["result", "version_no"], name="uniq_lab_result_version_no"
            ),
            models.CheckConstraint(
                condition=models.Q(content_hash__regex=r"^[0-9a-f]{64}$"),
                name="lab_result_hash_valid",
            ),
        ]


class LabSampleRejection(FacilityScopedModel):
    item = models.ForeignKey(
        LabOrderItem, on_delete=models.PROTECT, related_name="rejections"
    )
    reason = models.CharField(max_length=240)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lab_rejections"
    )
    rejected_at = models.DateTimeField(default=now)
