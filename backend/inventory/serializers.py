from decimal import Decimal

from rest_framework import serializers

from inventory.models import (
    BatchLocationBalance,
    InventoryThreshold,
    StockBatch,
    StockLocation,
    StockMovement,
    StockReceipt,
    StockReceiptLine,
    Supplier,
)
from pharmacy.models import MedicationProduct, ProductPrice


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicationProduct
        fields = [
            "id", "code", "generic_name", "brand_name", "dosage_form", "strength",
            "pack_description", "dispensing_unit", "category", "prescription_only",
            "controlled", "active", "instructions_template", "version",
        ]


class ProductCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=60)
    generic_name = serializers.CharField(max_length=200)
    brand_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    dosage_form = serializers.CharField(max_length=30)
    strength = serializers.CharField(max_length=80, required=False, allow_blank=True)
    pack_description = serializers.CharField(max_length=120, required=False, allow_blank=True)
    dispensing_unit = serializers.CharField(max_length=30)
    category = serializers.CharField(max_length=20, required=False, default="MEDICINE")
    prescription_only = serializers.BooleanField(required=False, default=True)
    controlled = serializers.BooleanField(required=False, default=False)
    active = serializers.BooleanField(required=False, default=True)
    confirm_duplicate = serializers.BooleanField(required=False, default=False)


class ProductDeactivateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=240)
    expected_version = serializers.IntegerField(min_value=1)


class ProductPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductPrice
        fields = [
            "id", "product", "amount", "pack_price", "currency",
            "effective_from", "effective_to", "version",
        ]


class ProductPriceSetSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    pack_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    currency = serializers.CharField(max_length=3, required=False, default="UGX")
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)
    source_event_id = serializers.CharField(max_length=120, required=False, allow_blank=True)


class CatalogueImportSerializer(serializers.Serializer):
    content = serializers.CharField()
    mode = serializers.ChoiceField(
        choices=["ALL_OR_NOTHING", "VALID_ROWS_ONLY"], default="ALL_OR_NOTHING"
    )
    template_version = serializers.CharField(required=False, default="1")
    file_name = serializers.CharField(required=False, default="catalogue.csv")
    file_hash = serializers.CharField(required=False, allow_blank=True, default="")


class StockLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockLocation
        fields = [
            "id", "code", "name", "location_type", "is_default", "is_quarantine",
            "active", "version",
        ]


class StockLocationWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=40)
    name = serializers.CharField(max_length=120)
    location_type = serializers.ChoiceField(
        choices=[choice[0] for choice in StockLocation.LOCATION_TYPES],
        required=False,
        default="STORE",
    )
    is_default = serializers.BooleanField(required=False, default=False)
    is_quarantine = serializers.BooleanField(required=False, default=False)
    active = serializers.BooleanField(required=False, default=True)
    expected_version = serializers.IntegerField(required=False, min_value=1)


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "code", "name", "contact_person", "phone", "notes", "active", "version"]


class SupplierWriteSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=60)
    name = serializers.CharField(max_length=160)
    contact_person = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    active = serializers.BooleanField(required=False, default=True)
    expected_version = serializers.IntegerField(required=False, min_value=1)


class ReceiptLineSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    location_id = serializers.UUIDField()
    batch_no = serializers.CharField(max_length=80)
    expiry_date = serializers.DateField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2)
    unit_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )


class StockReceiptSerializer(serializers.Serializer):
    receipt_no = serializers.CharField(max_length=60)
    lines = ReceiptLineSerializer(many=True)
    supplier_id = serializers.UUIDField(required=False, allow_null=True)
    supplier_name = serializers.CharField(required=False, allow_blank=True, default="")
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    source_event_id = serializers.CharField(required=False, allow_blank=True)


class MovementSerializer(serializers.ModelSerializer):
    batch_no = serializers.CharField(source="batch.batch_no", read_only=True)
    expiry_date = serializers.DateField(source="batch.expiry_date", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id", "product", "batch", "batch_no", "expiry_date", "location",
            "location_name", "movement_type", "quantity", "source_type", "source_id",
            "reason_code", "occurred_at",
        ]


class TransferSerializer(serializers.Serializer):
    batch_id = serializers.UUIDField()
    from_location_id = serializers.UUIDField()
    to_location_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class AdjustmentSerializer(serializers.Serializer):
    batch_id = serializers.UUIDField()
    location_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2)
    reason_code = serializers.CharField(max_length=40)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class ThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryThreshold
        fields = ["id", "product", "location", "reorder_level", "version"]


class ThresholdWriteSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    location_id = serializers.UUIDField(required=False, allow_null=True)
    reorder_level = serializers.DecimalField(max_digits=14, decimal_places=2)
    expected_version = serializers.IntegerField(required=False, min_value=1)


class FefoSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2)
    location_id = serializers.UUIDField(required=False, allow_null=True)


class StockCountOpenSerializer(serializers.Serializer):
    location_id = serializers.UUIDField()


class StockCountLineCountSerializer(serializers.Serializer):
    line_id = serializers.UUIDField()
    counted_qty = serializers.DecimalField(max_digits=14, decimal_places=2)


class StockCountSubmitSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    lines = StockCountLineCountSerializer(many=True)


class StockCountApproveSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class StockAdjustmentCreateSerializer(serializers.Serializer):
    batch_id = serializers.UUIDField()
    location_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2)
    reason_code = serializers.CharField(max_length=40)
    note = serializers.CharField(required=False, allow_blank=True, default="")
    reference = serializers.CharField(required=False, allow_blank=True, default="")


class StockAdjustmentApproveSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(required=False, min_value=1)


class QuarantineSerializer(serializers.Serializer):
    batch_id = serializers.UUIDField()
    location_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2)
    reason = serializers.CharField(max_length=240)
    source_type = serializers.CharField(required=False, allow_blank=True, default="MANUAL")
    source_id = serializers.CharField(required=False, allow_blank=True, default="")


class DisposalSerializer(serializers.Serializer):
    batch_id = serializers.UUIDField()
    location_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=2)
    reason = serializers.CharField(max_length=240)
    source_event_id = serializers.CharField(required=False, allow_blank=True, default="")
