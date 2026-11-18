from decimal import Decimal

from django.db import models

from core.clock import now
from core.models import FacilityScopedModel


class MedicationProduct(FacilityScopedModel):
    DOSAGE_FORMS = [
        ("TABLET", "Tablet"),
        ("CAPSULE", "Capsule"),
        ("SYRUP", "Syrup"),
        ("SUSPENSION", "Suspension"),
        ("INJECTION", "Injection"),
        ("CREAM", "Cream"),
        ("OINTMENT", "Ointment"),
        ("DROPS", "Drops"),
        ("INHALER", "Inhaler"),
        ("SUPPOSITORY", "Suppository"),
        ("SACHET", "Sachet"),
        ("VIAL", "Vial"),
        ("TUBE", "Tube"),
        ("PIECE", "Piece"),
    ]
    DISPENSING_UNITS = [
        ("TABLET", "Tablet"),
        ("CAPSULE", "Capsule"),
        ("ML", "Millilitre"),
        ("BOTTLE", "Bottle"),
        ("SACHET", "Sachet"),
        ("VIAL", "Vial"),
        ("TUBE", "Tube"),
        ("PIECE", "Piece"),
    ]
    CATEGORIES = [
        ("MEDICINE", "Medicine"),
        ("CONSUMABLE", "Consumable"),
        ("SUNDRY", "Sundry"),
    ]

    code = models.CharField(max_length=60)
    generic_name = models.CharField(max_length=200)
    brand_name = models.CharField(max_length=200, blank=True)
    dosage_form = models.CharField(max_length=30, choices=DOSAGE_FORMS)
    strength = models.CharField(max_length=80, blank=True)
    pack_description = models.CharField(max_length=120, blank=True)
    dispensing_unit = models.CharField(max_length=30, choices=DISPENSING_UNITS)
    category = models.CharField(max_length=20, choices=CATEGORIES, default="MEDICINE")
    prescription_only = models.BooleanField(default=True)
    controlled = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    instructions_template = models.CharField(max_length=240, blank=True)
    source = models.CharField(max_length=30, default="MANUAL")
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "facility", "code"],
                name="uniq_product_facility_code",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    dispensing_unit__in=[
                        "TABLET", "CAPSULE", "ML", "BOTTLE", "SACHET", "VIAL", "TUBE", "PIECE"
                    ]
                ),
                name="product_dispensing_unit_valid",
            ),
        ]


class ProductPrice(FacilityScopedModel):
    product = models.ForeignKey(
        MedicationProduct, on_delete=models.PROTECT, related_name="prices"
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    pack_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    currency = models.CharField(max_length=3, default="UGX")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    source_event_id = models.CharField(max_length=120)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="created_product_prices"
    )
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="product_price_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="product_price_dates_valid",
            ),
            models.UniqueConstraint(
                fields=["organisation", "source_event_id"],
                name="uniq_product_price_org_source",
            ),
        ]


class Prescription(FacilityScopedModel):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("ACTIVE", "Active"),
        ("CANCELLED", "Cancelled"),
        ("NOT_DISPENSED", "Not dispensed"),
        ("COMPLETED", "Completed"),
    ]

    visit = models.ForeignKey(
        "scheduling.Visit", on_delete=models.PROTECT, related_name="prescriptions"
    )
    encounter = models.ForeignKey(
        "clinical.Encounter", on_delete=models.PROTECT, related_name="prescriptions"
    )
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.PROTECT, related_name="prescriptions"
    )
    prescribed_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="prescriptions"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    source_prescription = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="copies"
    )
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["encounter"],
                condition=models.Q(status="DRAFT"),
                name="uniq_draft_prescription_encounter",
            )
        ]


class PrescriptionItem(FacilityScopedModel):
    STATES = [
        ("PENDING", "Pending"),
        ("DISPENSED", "Dispensed"),
        ("PARTIALLY_DISPENSED", "Partially dispensed"),
        ("NOT_DISPENSED", "Not dispensed"),
        ("CANCELLED", "Cancelled"),
    ]

    prescription = models.ForeignKey(
        Prescription, on_delete=models.PROTECT, related_name="items"
    )
    product = models.ForeignKey(
        MedicationProduct, on_delete=models.PROTECT, null=True, blank=True, related_name="prescription_items"
    )
    medicine_name = models.CharField(max_length=200)
    dose_amount = models.DecimalField(max_digits=10, decimal_places=2)
    dose_unit = models.CharField(max_length=30)
    route = models.CharField(max_length=20, default="PO")
    frequency = models.CharField(max_length=30, default="OD")
    duration_value = models.PositiveIntegerField(default=1)
    duration_unit = models.CharField(max_length=20, default="DAYS")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    instructions = models.CharField(max_length=500, blank=True)
    external = models.BooleanField(default=False)
    state = models.CharField(max_length=30, choices=STATES, default="PENDING")
    not_dispensed_reason = models.CharField(max_length=40, blank=True)
    version = models.PositiveBigIntegerField(default=1)


class PrescriptionClaim(FacilityScopedModel):
    prescription = models.ForeignKey(
        Prescription, on_delete=models.PROTECT, related_name="claims"
    )
    claimed_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="prescription_claims"
    )
    claimed_at = models.DateTimeField(default=now)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["prescription"],
                condition=models.Q(released_at__isnull=True),
                name="uniq_active_prescription_claim",
            )
        ]


class Dispense(FacilityScopedModel):
    STATUS_CHOICES = [
        ("PROVISIONAL", "Provisional"),
        ("AWAITING_PAYMENT", "Awaiting payment"),
        ("CONFIRMED", "Confirmed"),
        ("CANCELLED", "Cancelled"),
        ("REVERSED", "Reversed"),
    ]

    prescription = models.ForeignKey(
        Prescription, on_delete=models.PROTECT, null=True, blank=True, related_name="dispenses"
    )
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.PROTECT, null=True, blank=True, related_name="dispenses"
    )
    visit = models.ForeignKey(
        "scheduling.Visit", on_delete=models.PROTECT, null=True, blank=True, related_name="dispenses"
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="PROVISIONAL")
    prepared_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="prepared_dispenses"
    )
    confirmed_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, blank=True, related_name="confirmed_dispenses"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="UGX")
    source_event_id = models.CharField(max_length=120)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "source_event_id"], name="uniq_dispense_source"
            )
        ]


class DispenseLine(FacilityScopedModel):
    dispense = models.ForeignKey(Dispense, on_delete=models.PROTECT, related_name="lines")
    prescription_item = models.ForeignKey(
        PrescriptionItem, on_delete=models.PROTECT, null=True, blank=True, related_name="dispense_lines"
    )
    product = models.ForeignKey(
        MedicationProduct, on_delete=models.PROTECT, related_name="dispense_lines"
    )
    batch = models.ForeignKey(
        "inventory.StockBatch", on_delete=models.PROTECT, related_name="dispense_lines"
    )
    location = models.ForeignKey(
        "inventory.StockLocation", on_delete=models.PROTECT, related_name="dispense_lines"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    substitution_reason = models.CharField(max_length=240, blank=True)
    prescriber_consulted = models.BooleanField(default=False)
    prescriber_consulted_name = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=20, default="ACTIVE")
    version = models.PositiveBigIntegerField(default=1)


class OTCSale(FacilityScopedModel):
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.PROTECT, null=True, blank=True, related_name="otc_sales"
    )
    customer_name = models.CharField(max_length=160, blank=True)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")
    method = models.CharField(max_length=40, default="CASH")
    reference = models.CharField(max_length=120, blank=True)
    sold_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="otc_sales"
    )
    sold_at = models.DateTimeField(default=now)
    source_event_id = models.CharField(max_length=120)
    state = models.CharField(max_length=20, default="CONFIRMED")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "source_event_id"], name="uniq_otc_sale_source"
            )
        ]


class OTCSaleLine(FacilityScopedModel):
    sale = models.ForeignKey(OTCSale, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey(
        MedicationProduct, on_delete=models.PROTECT, related_name="otc_sale_lines"
    )
    batch = models.ForeignKey(
        "inventory.StockBatch", on_delete=models.PROTECT, related_name="otc_sale_lines"
    )
    location = models.ForeignKey(
        "inventory.StockLocation", on_delete=models.PROTECT, related_name="otc_sale_lines"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
