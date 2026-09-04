from rest_framework import serializers

from billing.models import Invoice, InvoiceItem, Payment, ServiceCatalogItem, ServicePrice


class ServicePriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePrice
        fields = ["id", "price_list", "amount", "currency", "effective_from", "effective_to", "is_active", "active", "source_version"]


class ServiceCatalogSerializer(serializers.ModelSerializer):
    prices = ServicePriceSerializer(many=True, read_only=True)

    class Meta:
        model = ServiceCatalogItem
        fields = ["id", "code", "name", "category", "description", "is_active", "prices"]


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            "id", "service", "description", "quantity", "unit_price", "amount",
            "line_set_version", "source_type", "source_id", "source_version",
            "source_line_identity", "state",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "receipt_no", "amount", "method", "reference", "status", "received_by", "received_at"]


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "invoice_no", "patient", "patient_name", "visit", "encounter", "status", "currency",
            "subtotal", "discount", "total", "amount_paid", "balance", "issued_at", "items", "payments",
            "voided_at", "voided_by", "current_line_set_version", "version",
        ]


class InvoiceCreateSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    encounter_id = serializers.UUIDField(required=False)
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    discount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, default="0.00")


class PaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    method = serializers.ChoiceField(choices=Payment.METHOD_CHOICES)
    reference = serializers.CharField(required=False, allow_blank=True)


class ReceiptSerializer(serializers.Serializer):
    receipt_no = serializers.CharField()
    invoice_no = serializers.CharField()
    patient_name = serializers.CharField()
    patient_no = serializers.CharField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField()
    method = serializers.CharField()
    reference = serializers.CharField(allow_null=True)
    received_at = serializers.DateTimeField()
    invoice_total = serializers.DecimalField(max_digits=14, decimal_places=2)
    invoice_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    printable_text = serializers.CharField()
