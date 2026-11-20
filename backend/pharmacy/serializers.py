from rest_framework import serializers


class PrescriptionItemInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField(required=False, allow_null=True)
    medicine_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    dose_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    dose_unit = serializers.CharField(required=False, allow_blank=True, max_length=30)
    route = serializers.CharField(required=False, allow_blank=True, max_length=20)
    frequency = serializers.CharField(required=False, allow_blank=True, max_length=30)
    duration_value = serializers.IntegerField(required=False, min_value=1)
    duration_unit = serializers.CharField(required=False, allow_blank=True, max_length=20)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2)
    instructions = serializers.CharField(required=False, allow_blank=True, max_length=500)


class PrescriptionDraftSerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    source_prescription_id = serializers.UUIDField(required=False, allow_null=True)
    items = PrescriptionItemInputSerializer(many=True)


class PrescriptionCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=240)


class NotDispensedSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(
        choices=[
            "OUT_OF_STOCK",
            "PATIENT_DECLINED",
            "PATIENT_CANNOT_AFFORD",
            "PRESCRIBER_CANCELLED",
            "NOT_STOCKED",
            "OTHER",
        ]
    )


class DispenseLineInputSerializer(serializers.Serializer):
    prescription_item_id = serializers.UUIDField()
    product_id = serializers.UUIDField(required=False, allow_null=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    substitution_reason = serializers.CharField(
        required=False, allow_blank=True, max_length=240
    )
    prescriber_consulted = serializers.BooleanField(required=False, default=False)
    prescriber_consulted_name = serializers.CharField(
        required=False, allow_blank=True, max_length=120
    )


class DispensePrepareSerializer(serializers.Serializer):
    lines = DispenseLineInputSerializer(many=True)


class DispenseReviewSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    prescription_id = serializers.UUIDField(allow_null=True)
    encounter_id = serializers.UUIDField(allow_null=True)
    visit_id = serializers.UUIDField(allow_null=True)
    patient_id = serializers.UUIDField(allow_null=True)
    patient_name = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    total = serializers.CharField()
    currency = serializers.CharField()
    version = serializers.IntegerField()
    claim_holder_id = serializers.CharField(allow_null=True)
    claim_holder_name = serializers.CharField(allow_null=True)
    allergy = serializers.DictField(allow_null=True)
    eligible = serializers.BooleanField()
    blocked_reason = serializers.CharField(allow_null=True)
    lines = serializers.ListField(child=serializers.DictField())


class OTCSaleLineInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2)


class OTCSaleCreateSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField(required=False, allow_null=True)
    customer_name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    method = serializers.CharField(required=False, allow_blank=True, max_length=40)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=120)
    lines = OTCSaleLineInputSerializer(many=True)


class InstructionTemplateSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=240, allow_blank=True)
    expected_version = serializers.IntegerField(min_value=1)
