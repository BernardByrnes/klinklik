from rest_framework import serializers

from billing.models import (
    CashierShift,
    Invoice,
    InvoiceItem,
    Payment,
    PaymentAllocation,
    PaymentMethodConfig,
    ServiceCatalogItem,
    ServicePrice,
)


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
    is_current = serializers.SerializerMethodField()

    def get_is_current(self, obj):
        return obj.line_set_version == obj.invoice.current_line_set_version

    class Meta:
        model = InvoiceItem
        fields = [
            "id", "service", "description", "quantity", "unit_price", "amount",
            "line_set_version", "is_current", "source_type", "source_id", "source_version",
            "source_line_identity", "state", "void_reason", "voided_at", "voided_by",
            "manual_reason",
        ]


class PaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_no = serializers.CharField(source="invoice.invoice_no", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = ["id", "invoice", "invoice_no", "amount"]


class PaymentSerializer(serializers.ModelSerializer):
    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    receipt_id = serializers.CharField(source="receipt.id", read_only=True, allow_null=True)
    shift_id = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = Payment
        fields = [
            "id", "receipt_no", "amount", "method", "reference", "status",
            "received_by", "received_at", "shift_id", "receipt_id",
            "reversed_at", "allocations",
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "invoice_no", "patient", "patient_name", "visit", "encounter", "status", "currency",
            "subtotal", "discount", "total", "amount_paid", "balance",
            "credit_total", "refunded_total", "refundable_credit",
            "issued_at", "items", "payments",
            "voided_at", "voided_by", "current_line_set_version", "version",
        ]


class InvoiceMutationSerializer(serializers.Serializer):
    """PHI-minimal invoice result for idempotent line commands."""

    id = serializers.UUIDField()
    invoice_no = serializers.CharField()
    status = serializers.CharField()
    currency = serializers.CharField()
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2)
    discount = serializers.DecimalField(max_digits=14, decimal_places=2)
    total = serializers.DecimalField(max_digits=14, decimal_places=2)
    amount_paid = serializers.DecimalField(max_digits=14, decimal_places=2)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    version = serializers.IntegerField()


class InvoiceCreateSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    encounter_id = serializers.UUIDField(required=False)
    items = serializers.ListField(child=serializers.DictField(), allow_empty=False)
    discount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, default="0.00")


class PaymentAllocationInputSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class PaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    method = serializers.CharField(max_length=40)
    reference = serializers.CharField(required=False, allow_blank=True)
    allocations = PaymentAllocationInputSerializer(many=True, required=False)


class AllocationSummarySerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField()
    invoice_no = serializers.CharField(required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class InvoiceProjectionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    total = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)


class PaymentResultSerializer(serializers.Serializer):
    """PHI-minimal command result; receipt content is read by its identity."""

    id = serializers.UUIDField()
    receipt_no = serializers.CharField()
    receipt_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    method = serializers.CharField()
    status = serializers.CharField()
    allocations = AllocationSummarySerializer(many=True)
    invoices = InvoiceProjectionSerializer(many=True)


class ReceiptSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    receipt_no = serializers.CharField()
    payment_id = serializers.UUIDField()
    invoice_id = serializers.UUIDField()
    invoice_no = serializers.CharField()
    patient_name = serializers.CharField()
    patient_no = serializers.CharField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField()
    method = serializers.CharField()
    reference = serializers.CharField(allow_blank=True)
    received_at = serializers.DateTimeField()
    status = serializers.CharField()
    invoice_total = serializers.DecimalField(max_digits=14, decimal_places=2)
    invoice_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    allocations = AllocationSummarySerializer(many=True)
    print_count = serializers.IntegerField()
    last_printed_at = serializers.DateTimeField(allow_null=True)
    content_hash = serializers.CharField()
    printable_text = serializers.CharField()


class ReceiptReprintSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    receipt_no = serializers.CharField()
    print_count = serializers.IntegerField()
    last_printed_at = serializers.DateTimeField(allow_null=True)


class PaymentReverseResultSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    receipt_no = serializers.CharField()
    status = serializers.CharField()
    invoices = InvoiceProjectionSerializer(many=True)


class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashierShift
        fields = [
            "id", "cashier", "status", "opened_at", "closed_at", "closed_by",
            "opening_float", "declared_cash", "expected_cash", "variance",
            "close_reason", "version",
        ]


class ClosedShiftSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    opened_at = serializers.DateTimeField()
    closed_at = serializers.DateTimeField(allow_null=True)
    declared_cash = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    expected_cash = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    variance = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True
    )
    close_reason = serializers.CharField(allow_blank=True)


class ShiftCurrentResponseSerializer(serializers.Serializer):
    shift = ShiftSerializer(allow_null=True)
    last_closed_shift = ClosedShiftSummarySerializer(allow_null=True)


class ShiftOpenSerializer(serializers.Serializer):
    opening_float = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default="0.00"
    )


class ShiftCloseSerializer(serializers.Serializer):
    declared_cash = serializers.DecimalField(max_digits=14, decimal_places=2)
    reason = serializers.CharField(required=False, allow_blank=True)


class PaymentMethodSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    kind = serializers.CharField()
    reference_required = serializers.BooleanField()
    provider_label = serializers.CharField(allow_blank=True)
    is_active = serializers.BooleanField()
    configured = serializers.BooleanField()


class PaymentMethodConfigureSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=40)
    label = serializers.CharField(max_length=80)
    kind = serializers.ChoiceField(choices=PaymentMethodConfig.KIND_CHOICES)
    reference_required = serializers.BooleanField(required=False, default=False)
    provider_label = serializers.CharField(max_length=80, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False, default=True)


class InvoiceLineCreateSerializer(serializers.Serializer):
    service_id = serializers.UUIDField(required=False)
    description = serializers.CharField(max_length=240, required=False, allow_blank=True)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default="1.00")
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    reason = serializers.CharField(max_length=240, required=False, allow_blank=True)
    manual = serializers.BooleanField(required=False, default=False)


class InvoiceLineVoidSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=240)


class CreditNoteSerializer(serializers.ModelSerializer):
    class Meta:
        from billing.models import CreditNote

        model = CreditNote
        fields = [
            "id", "credit_no", "invoice", "amount", "currency", "reason",
            "status", "issued_at", "issued_by", "voided_at", "voided_by", "version",
        ]


class CreditNoteResultSerializer(serializers.Serializer):
    """PHI-minimal command result."""

    id = serializers.UUIDField()
    credit_no = serializers.CharField()
    invoice_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    status = serializers.CharField()
    credit_total = serializers.DecimalField(max_digits=14, decimal_places=2)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    refundable_credit = serializers.DecimalField(max_digits=14, decimal_places=2)


class CreditNoteIssueSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    reason = serializers.CharField(max_length=240, allow_blank=True)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=240)


class ZReportSerializer(serializers.Serializer):
    shift_id = serializers.UUIDField()
    status = serializers.CharField()
    opened_at = serializers.DateTimeField()
    closed_at = serializers.DateTimeField(allow_null=True)
    opening_float = serializers.CharField()
    tenders = serializers.ListField(child=serializers.DictField())
    payment_count = serializers.IntegerField()
    reversed_count = serializers.IntegerField()
    refund_count = serializers.IntegerField()
    refund_total = serializers.CharField()
    discount_total = serializers.CharField()
    declared_cash = serializers.CharField(allow_null=True)
    expected_cash = serializers.CharField(allow_null=True)
    variance = serializers.CharField(allow_null=True)
    variance_reason = serializers.CharField(allow_blank=True)


class InvoiceRepriceSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    price_list_id = serializers.UUIDField(required=False)
    payer_type = serializers.ChoiceField(
        choices=["CASH", "SELF_PAY_MOMO"], required=False
    )


class InvoiceRepriceResultSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    invoice_no = serializers.CharField()
    status = serializers.CharField()
    before_total = serializers.DecimalField(max_digits=14, decimal_places=2)
    after_total = serializers.DecimalField(max_digits=14, decimal_places=2)
    line_set_version = serializers.IntegerField()
    version = serializers.IntegerField()
    payer_binding_id = serializers.UUIDField()
