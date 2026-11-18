from decimal import Decimal

from django.db import models

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
    source_event_id = models.CharField(max_length=120, unique=True)
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
        ]
