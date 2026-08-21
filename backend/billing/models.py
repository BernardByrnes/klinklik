from decimal import Decimal

from django.conf import settings
from django.db import models

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


class ServicePrice(FacilityScopedModel):
    service = models.ForeignKey(ServiceCatalogItem, on_delete=models.PROTECT, related_name="prices")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)


class Invoice(FacilityScopedModel):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("ISSUED", "Issued"),
        ("PARTIALLY_PAID", "Partially paid"),
        ("PAID", "Paid"),
        ("VOID", "Void"),
    ]

    invoice_no = models.CharField(max_length=50)
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="invoices")
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
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organisation", "invoice_no"], name="uniq_invoice_org_no")
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
