from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.db import models

from core.clock import now
from core.models import FacilityScopedModel, OrganisationScopedModel


class ServiceCatalogItem(OrganisationScopedModel):
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=80, default="CLINIC")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organisation", "code"], name="uniq_service_org_code")
        ]


class PriceList(OrganisationScopedModel):
    PAYER_TYPE_CHOICES = [
        ("CASH", "Cash"),
        ("SELF_PAY_MOMO", "Self-pay mobile money"),
    ]

    stable_code = models.CharField(max_length=60, default="STANDARD")
    name = models.CharField(max_length=160)
    payer_type = models.CharField(max_length=30, choices=PAYER_TYPE_CHOICES)
    active = models.BooleanField(default=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    @property
    def is_active(self):
        return self.active

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "stable_code", "version"],
                name="uniq_price_list_org_code_version",
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F("effective_from")),
                name="price_list_effective_dates_valid",
            ),
        ]


class ServicePrice(FacilityScopedModel):
    service = models.ForeignKey(ServiceCatalogItem, on_delete=models.PROTECT, related_name="prices")
    price_list = models.ForeignKey(
        PriceList,
        on_delete=models.PROTECT,
        related_name="service_prices",
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    source_version = models.CharField(max_length=40, default="v1")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=models.F("effective_from")),
                name="service_price_effective_dates_valid",
            ),
            ExclusionConstraint(
                name="service_price_active_period_excl",
                expressions=[
                    (models.F("organisation"), RangeOperators.EQUAL),
                    (models.F("facility"), RangeOperators.EQUAL),
                    (models.F("price_list"), RangeOperators.EQUAL),
                    (models.F("service"), RangeOperators.EQUAL),
                    (
                        models.Func(
                            models.F("effective_from"),
                            models.F("effective_to"),
                            models.Value("[]"),
                            function="daterange",
                            output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                condition=models.Q(is_active=True, active=True),
            ),
        ]


class Invoice(FacilityScopedModel):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("ISSUED", "Issued"),
        ("PARTIALLY_PAID", "Partially paid"),
        ("PAID", "Paid"),
        ("VOID", "Void"),
        ("VOIDED", "Voided"),
    ]

    invoice_no = models.CharField(max_length=50)
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="invoices")
    visit = models.ForeignKey(
        "scheduling.Visit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoices",
    )
    encounter = models.ForeignKey(
        "clinical.Encounter", on_delete=models.PROTECT, null=True, blank=True, related_name="invoices"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    currency = models.CharField(max_length=3, default="UGX")
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    issued_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="voided_invoices",
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    current_line_set_version = models.PositiveIntegerField(default=1)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organisation", "invoice_no"], name="uniq_invoice_org_no"),
            models.UniqueConstraint(
                fields=["organisation", "facility", "visit"],
                condition=models.Q(visit__isnull=False) & ~models.Q(status__in=["VOID", "VOIDED"]),
                name="uniq_active_visit_invoice",
            ),
        ]


class InvoiceItem(OrganisationScopedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="items")
    facility = models.ForeignKey("tenancy.Facility", on_delete=models.PROTECT, related_name="invoice_items")
    service = models.ForeignKey(
        ServiceCatalogItem, on_delete=models.PROTECT, null=True, blank=True, related_name="invoice_items"
    )
    description = models.CharField(max_length=240)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    line_set_version = models.PositiveIntegerField(default=1)
    source_type = models.CharField(max_length=40, default="LEGACY")
    source_id = models.UUIDField(null=True, blank=True)
    source_version = models.CharField(max_length=40, default="v1")
    source_line_identity = models.CharField(max_length=120, default="")
    state = models.CharField(max_length=20, default="ACTIVE")
    void_reason = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_invoice_items",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["invoice", "line_set_version", "source_line_identity", "source_version"],
                condition=models.Q(source_line_identity__gt=""),
                name="uniq_invoice_source_line_version",
            ),
        ]


InvoiceLine = InvoiceItem


class VisitPayerBinding(OrganisationScopedModel):
    PAYER_TYPE_CHOICES = PriceList.PAYER_TYPE_CHOICES

    facility = models.ForeignKey("tenancy.Facility", on_delete=models.PROTECT, related_name="payer_bindings")
    visit = models.ForeignKey("scheduling.Visit", on_delete=models.PROTECT, related_name="payer_bindings")
    price_list = models.ForeignKey(
        PriceList,
        on_delete=models.PROTECT,
        related_name="visit_bindings",
    )
    payer_type = models.CharField(max_length=30, choices=PAYER_TYPE_CHOICES)
    binding_version = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    bound_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    bound_at = models.DateTimeField(default=now)
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="superseding_bindings",
    )
    source_event_id = models.CharField(max_length=120, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["visit", "binding_version"],
                name="uniq_visit_payer_binding_version",
            ),
            models.UniqueConstraint(
                fields=["visit"],
                condition=models.Q(active=True),
                name="uniq_active_visit_payer_binding",
            ),
        ]


class Payment(FacilityScopedModel):
    METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("MOBILE_MONEY", "Mobile money"),
        ("CARD", "Card"),
        ("BANK", "Bank"),
    ]
    STATUS_CHOICES = [("POSTED", "Posted"), ("REVERSED", "Reversed")]

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    receipt_no = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=30, choices=METHOD_CHOICES)
    reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="POSTED")
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    received_at = models.DateTimeField(auto_now_add=True)
    receipt_printed_at = models.DateTimeField(null=True, blank=True)


class PaymentAllocation(OrganisationScopedModel):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="allocations")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="allocations")
    facility = models.ForeignKey("tenancy.Facility", on_delete=models.PROTECT, related_name="payment_allocations")
    amount = models.DecimalField(max_digits=14, decimal_places=2)


class CashierShift(FacilityScopedModel):
    STATUS_CHOICES = [("OPEN", "Open"), ("CLOSED", "Closed")]

    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cashier_shifts")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    opening_float = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    declared_cash = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    close_reason = models.TextField(blank=True)
