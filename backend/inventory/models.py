from decimal import Decimal

from django.conf import settings
from django.db import models

from core.clock import now
from core.models import FacilityScopedModel


class StockLocation(FacilityScopedModel):
    LOCATION_TYPES = [
        ("MAIN", "Main pharmacy"),
        ("STORE", "Store"),
        ("DISPENSARY", "Dispensary"),
        ("LAB_STORE", "Laboratory store"),
        ("TREATMENT_ROOM", "Treatment room"),
        ("QUARANTINE", "Quarantine"),
    ]

    code = models.CharField(max_length=40)
    name = models.CharField(max_length=120)
    location_type = models.CharField(max_length=30, choices=LOCATION_TYPES, default="STORE")
    is_default = models.BooleanField(default=False)
    is_quarantine = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "facility", "code"],
                name="uniq_stock_location_facility_code",
            ),
            models.UniqueConstraint(
                fields=["organisation", "facility"],
                condition=models.Q(is_default=True),
                name="uniq_default_stock_location",
            ),
        ]


class Supplier(FacilityScopedModel):
    code = models.CharField(max_length=60)
    name = models.CharField(max_length=160)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "facility", "code"],
                name="uniq_supplier_facility_code",
            )
        ]


class StockBatch(FacilityScopedModel):
    product = models.ForeignKey(
        "pharmacy.MedicationProduct", on_delete=models.PROTECT, related_name="batches"
    )
    batch_no = models.CharField(max_length=80)
    expiry_date = models.DateField()
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, null=True, blank=True, related_name="batches"
    )
    received_at = models.DateTimeField(default=now)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "facility", "product", "batch_no", "expiry_date"],
                name="uniq_batch_product_number_expiry",
            )
        ]


class StockReceipt(FacilityScopedModel):
    receipt_no = models.CharField(max_length=60)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, null=True, blank=True, related_name="receipts"
    )
    supplier_name = models.CharField(max_length=160, blank=True)
    reference = models.CharField(max_length=120, blank=True)
    warning_near_expiry = models.BooleanField(default=False)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="posted_stock_receipts"
    )
    posted_at = models.DateTimeField(default=now)
    source_event_id = models.CharField(max_length=120)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "facility", "receipt_no"],
                name="uniq_stock_receipt_facility_no",
            ),
            models.UniqueConstraint(
                fields=["organisation", "source_event_id"],
                name="uniq_stock_receipt_source",
            ),
        ]


class StockReceiptLine(FacilityScopedModel):
    receipt = models.ForeignKey(
        StockReceipt, on_delete=models.PROTECT, related_name="lines"
    )
    product = models.ForeignKey(
        "pharmacy.MedicationProduct", on_delete=models.PROTECT, related_name="receipt_lines"
    )
    batch = models.ForeignKey(
        StockBatch, on_delete=models.PROTECT, related_name="receipt_lines"
    )
    location = models.ForeignKey(
        StockLocation, on_delete=models.PROTECT, related_name="receipt_lines"
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_cost = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    line_no = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["receipt", "line_no"], name="uniq_stock_receipt_line_no"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="stock_receipt_line_quantity_positive"
            ),
        ]


class StockMovement(FacilityScopedModel):
    MOVEMENT_TYPES = [
        ("IN_GRN", "Goods received"),
        ("OUT_DISPENSE", "Dispensed"),
        ("OUT_SALE", "Sold"),
        ("TRANSFER_IN", "Transfer in"),
        ("TRANSFER_OUT", "Transfer out"),
        ("ADJUSTMENT", "Adjustment"),
        ("WRITE_OFF", "Write-off"),
        ("QUARANTINE", "Quarantine"),
        ("REVERSAL", "Reversal"),
        ("OPENING", "Opening balance"),
    ]

    product = models.ForeignKey(
        "pharmacy.MedicationProduct", on_delete=models.PROTECT, related_name="movements"
    )
    batch = models.ForeignKey(
        StockBatch, on_delete=models.PROTECT, related_name="movements"
    )
    location = models.ForeignKey(
        StockLocation, on_delete=models.PROTECT, related_name="movements"
    )
    movement_type = models.CharField(max_length=30, choices=MOVEMENT_TYPES)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    source_type = models.CharField(max_length=40)
    source_id = models.CharField(max_length=120)
    reason_code = models.CharField(max_length=40, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stock_movements"
    )
    occurred_at = models.DateTimeField(default=now)
    receipt_line = models.ForeignKey(
        StockReceiptLine,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity=0), name="stock_movement_quantity_nonzero"
            ),
            models.UniqueConstraint(
                fields=["organisation", "source_type", "source_id", "movement_type", "batch", "location"],
                name="uniq_stock_movement_source",
            ),
        ]


class BatchLocationBalance(FacilityScopedModel):
    product = models.ForeignKey(
        "pharmacy.MedicationProduct", on_delete=models.PROTECT, related_name="balances"
    )
    batch = models.ForeignKey(
        StockBatch, on_delete=models.PROTECT, related_name="balances"
    )
    location = models.ForeignKey(
        StockLocation, on_delete=models.PROTECT, related_name="balances"
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "facility", "batch", "location"],
                name="uniq_balance_batch_location",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0), name="balance_quantity_nonnegative"
            ),
        ]


class InventoryThreshold(FacilityScopedModel):
    product = models.ForeignKey(
        "pharmacy.MedicationProduct", on_delete=models.PROTECT, related_name="thresholds"
    )
    location = models.ForeignKey(
        StockLocation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="thresholds",
    )
    reorder_level = models.DecimalField(max_digits=14, decimal_places=2)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "facility", "product", "location"],
                name="uniq_threshold_product_location",
            ),
            models.CheckConstraint(
                condition=models.Q(reorder_level__gte=0),
                name="threshold_reorder_nonnegative",
            ),
        ]


class StockCount(FacilityScopedModel):
    STATE_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("PENDING_APPROVAL", "Pending approval"),
        ("POSTED", "Posted"),
    ]

    location = models.ForeignKey(
        StockLocation, on_delete=models.PROTECT, related_name="counts"
    )
    state = models.CharField(max_length=30, choices=STATE_CHOICES, default="DRAFT")
    snapshot_movement_watermark = models.UUIDField()
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opened_stock_counts"
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="submitted_stock_counts",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_stock_counts",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_reason = models.CharField(max_length=240, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "facility", "location"],
                condition=models.Q(state__in=["DRAFT", "SUBMITTED", "PENDING_APPROVAL"]),
                name="uniq_open_stock_count_location",
            )
        ]


class StockCountLine(FacilityScopedModel):
    count = models.ForeignKey(StockCount, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey(
        "pharmacy.MedicationProduct", on_delete=models.PROTECT, related_name="count_lines"
    )
    batch = models.ForeignKey(StockBatch, on_delete=models.PROTECT, related_name="count_lines")
    location = models.ForeignKey(
        StockLocation, on_delete=models.PROTECT, related_name="count_lines"
    )
    expected_qty = models.DecimalField(max_digits=14, decimal_places=2)
    counted_qty = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    variance_qty = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    source_line_identity = models.CharField(max_length=120)
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="counted_stock_lines",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["count", "batch", "location"], name="uniq_stock_count_batch_location"
            )
        ]


class StockAdjustment(FacilityScopedModel):
    STATE_CHOICES = [
        ("PENDING_APPROVAL", "Pending approval"),
        ("POSTED", "Posted"),
        ("REJECTED", "Rejected"),
    ]
    REASON_CODES = [
        "EXPIRY_DISPOSAL",
        "DAMAGE",
        "BREAKAGE",
        "THEFT_LOSS",
        "COUNT_CORRECTION",
        "RETURN_TO_SUPPLIER",
        "DONATION_OUT",
        "OTHER",
    ]

    count = models.ForeignKey(
        StockCount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="adjustments",
    )
    product = models.ForeignKey(
        "pharmacy.MedicationProduct", on_delete=models.PROTECT, related_name="adjustments"
    )
    batch = models.ForeignKey(
        StockBatch, on_delete=models.PROTECT, related_name="adjustments"
    )
    location = models.ForeignKey(
        StockLocation, on_delete=models.PROTECT, related_name="adjustments"
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    reason_code = models.CharField(max_length=40, choices=[(code, code) for code in REASON_CODES])
    note = models.CharField(max_length=240, blank=True)
    reference = models.CharField(max_length=120, blank=True)
    state = models.CharField(
        max_length=30, choices=STATE_CHOICES, default="PENDING_APPROVAL"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_stock_adjustments"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_stock_adjustments",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    source_event_id = models.CharField(max_length=120)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "source_event_id"],
                name="uniq_stock_adjustment_source",
            ),
            models.CheckConstraint(
                condition=~models.Q(quantity=0), name="stock_adjustment_quantity_nonzero"
            ),
        ]


class QuarantineRecord(FacilityScopedModel):
    product = models.ForeignKey(
        "pharmacy.MedicationProduct", on_delete=models.PROTECT, related_name="quarantine_records"
    )
    batch = models.ForeignKey(
        StockBatch, on_delete=models.PROTECT, related_name="quarantine_records"
    )
    location = models.ForeignKey(
        StockLocation, on_delete=models.PROTECT, related_name="quarantine_records"
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.CharField(max_length=240)
    source_type = models.CharField(max_length=40)
    source_id = models.CharField(max_length=120)
    source_line_identity = models.CharField(max_length=120)
    quarantined_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="quarantined_stock"
    )
    quarantined_at = models.DateTimeField(default=now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "source_type", "source_id", "source_line_identity"],
                name="uniq_quarantine_source",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="quarantine_quantity_positive"
            ),
        ]


class DisposalRecord(FacilityScopedModel):
    product = models.ForeignKey(
        "pharmacy.MedicationProduct", on_delete=models.PROTECT, related_name="disposal_records"
    )
    batch = models.ForeignKey(
        StockBatch, on_delete=models.PROTECT, related_name="disposal_records"
    )
    location = models.ForeignKey(
        StockLocation, on_delete=models.PROTECT, related_name="disposal_records"
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.CharField(max_length=240)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_disposals",
    )
    disposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="disposed_stock"
    )
    disposed_at = models.DateTimeField(default=now)
    source_event_id = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "source_event_id"], name="uniq_disposal_source"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="disposal_quantity_positive"
            ),
        ]
