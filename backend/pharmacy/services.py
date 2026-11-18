"""Pharmacy catalogue owner services: products, prices and import primitives."""

from decimal import Decimal, InvalidOperation
from datetime import date

from django.db import transaction
from django.db.models import Q

from audit.services import record_event
from core.clock import now
from core.errors import CanonicalError
from core.services import assert_transaction_active
from pharmacy.models import MedicationProduct, ProductPrice


DOSAGE_FORMS = {choice[0] for choice in MedicationProduct.DOSAGE_FORMS}
DISPENSING_UNITS = {choice[0] for choice in MedicationProduct.DISPENSING_UNITS}
CATEGORIES = {choice[0] for choice in MedicationProduct.CATEGORIES}


def _product_payload(payload):
    code = str(payload.get("code") or "").strip().upper()
    generic = str(payload.get("generic_name") or "").strip()
    form = str(payload.get("dosage_form") or "").strip().upper()
    unit = str(payload.get("dispensing_unit") or "").strip().upper()
    category = str(payload.get("category") or "MEDICINE").strip().upper()
    if not code or not generic:
        raise CanonicalError("INVALID_INPUT", "A code and generic name are required.", status_code=400)
    if form not in DOSAGE_FORMS:
        raise CanonicalError("INVALID_INPUT", "Select a valid dosage form.", status_code=400)
    if unit not in DISPENSING_UNITS:
        raise CanonicalError("INVALID_INPUT", "Select a valid dispensing unit.", status_code=400)
    if category not in CATEGORIES:
        raise CanonicalError("INVALID_INPUT", "Select a valid product category.", status_code=400)
    return {
        "code": code,
        "generic_name": generic,
        "brand_name": str(payload.get("brand_name") or "").strip(),
        "dosage_form": form,
        "strength": str(payload.get("strength") or "").strip(),
        "pack_description": str(payload.get("pack_description") or "").strip(),
        "dispensing_unit": unit,
        "category": category,
        "prescription_only": bool(payload.get("prescription_only", True)),
        "controlled": bool(payload.get("controlled", False)),
        "instructions_template": str(payload.get("instructions_template") or "").strip()[:240],
    }


@transaction.atomic
def create_product(
    *, organisation, facility, actor, payload, confirm_duplicate=False, request=None
):
    assert_transaction_active()
    values = _product_payload(payload)
    if MedicationProduct.objects.filter(
        organisation=organisation, facility=facility, code=values["code"]
    ).exists():
        raise CanonicalError("ALREADY_EXISTS", "A product with this code already exists.", status_code=409)
    duplicates = MedicationProduct.objects.filter(
        organisation=organisation,
        facility=facility,
        generic_name__iexact=values["generic_name"],
        strength__iexact=values["strength"],
        dosage_form=values["dosage_form"],
    )
    if duplicates.exists() and not confirm_duplicate:
        existing = duplicates.first()
        raise CanonicalError(
            "DUPLICATE_PRODUCT_WARNING",
            "A matching product already exists; confirm to create another.",
            status_code=409,
            metadata={
                "existing_product_id": str(existing.id),
                "existing_code": existing.code,
            },
        )
    payload_active = bool(payload.get("active", True))
    if values["controlled"]:
        # Controlled/Class A medicines remain blocked in baseline V1.
        payload_active = False
    values.pop("active", None)
    product = MedicationProduct.objects.create(
        organisation=organisation,
        facility=facility,
        active=payload_active,
        source=str(payload.get("source") or "MANUAL")[:30],
        **values,
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="MedicationProduct",
        entity_id=product.id,
        after={"code": product.code, "category": product.category, "controlled": product.controlled},
        event_code="MEDICATION_PRODUCT_CREATED",
    )
    return product


def search_products(
    *, organisation, facility, query="", category=None, prescribing=False, limit=50
):
    assert_transaction_active()
    products = MedicationProduct.objects.filter(
        organisation=organisation, facility=facility, active=True
    )
    if category:
        products = products.filter(category=str(category).upper())
    if prescribing:
        products = products.filter(category="MEDICINE", controlled=False)
    text = str(query or "").strip()
    if text:
        products = products.filter(
            Q(generic_name__icontains=text) | Q(brand_name__icontains=text) | Q(code__icontains=text)
        )
    return products.order_by("generic_name", "strength", "id")[: max(1, min(limit, 100))]


@transaction.atomic
def set_product_price(
    *, organisation, facility, actor, product_id, amount, currency="UGX",
    effective_from, effective_to=None, pack_price=None, source_event_id="", request=None,
):
    assert_transaction_active()
    product = MedicationProduct.objects.select_for_update().filter(
        id=product_id, organisation=organisation, facility=facility
    ).first()
    if product is None:
        raise CanonicalError("NOT_FOUND", "Product was not found.", status_code=404)
    try:
        amount = Decimal(str(amount)).quantize(Decimal("0.01"))
        pack_price = (
            Decimal(str(pack_price)).quantize(Decimal("0.01"))
            if pack_price not in (None, "")
            else None
        )
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CanonicalError("INVALID_INPUT", "Enter a valid price.", status_code=400) from exc
    if amount <= 0 or (pack_price is not None and pack_price <= 0):
        raise CanonicalError("INVALID_INPUT", "Prices must be positive.", status_code=400)
    if effective_to is not None and effective_to < effective_from:
        raise CanonicalError("INVALID_INPUT", "The price dates are invalid.", status_code=400)
    overlaps = ProductPrice.objects.filter(
        organisation=organisation,
        facility=facility,
        product=product,
        effective_from__lte=(effective_to or date.max),
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from))
    if overlaps.exists():
        raise CanonicalError(
            "OVERLAPPING_EFFECTIVE_RANGE",
            "Another price covers this effective period.",
            status_code=422,
        )
    price = ProductPrice.objects.create(
        organisation=organisation,
        facility=facility,
        product=product,
        amount=amount,
        pack_price=pack_price,
        currency=str(currency or "UGX")[:3].upper(),
        effective_from=effective_from,
        effective_to=effective_to,
        source_event_id=source_event_id or f"PRODUCT:{product.id}:{now().isoformat()}",
        created_by=actor,
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="ProductPrice",
        entity_id=price.id,
        after={"product_id": str(product.id), "amount": str(amount)},
        event_code="PRODUCT_PRICE_SET",
    )
    return price


@transaction.atomic
def deactivate_product(
    *, organisation, facility, actor, product_id, reason, expected_version, request=None
):
    assert_transaction_active()
    if not str(reason or "").strip():
        raise CanonicalError("INVALID_INPUT", "A deactivation reason is required.", status_code=400)
    product = MedicationProduct.objects.select_for_update().filter(
        id=product_id, organisation=organisation, facility=facility
    ).first()
    if product is None:
        raise CanonicalError("NOT_FOUND", "Product was not found.", status_code=404)
    if product.version != expected_version:
        raise CanonicalError("VERSION_CONFLICT", "The product changed; refresh.", status_code=409)
    from inventory.models import BatchLocationBalance

    on_hand = sum(
        (
            balance.quantity
            for balance in BatchLocationBalance.objects.filter(
                organisation=organisation, facility=facility, product=product
            )
        ),
        Decimal("0.00"),
    )
    if on_hand > 0:
        raise CanonicalError(
            "STOCK_ON_HAND",
            "A product with stock on hand cannot be deactivated.",
            status_code=409,
            metadata={"quantity": str(on_hand)},
        )
    product.active = False
    product.version += 1
    product.save(update_fields=["active", "version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="MedicationProduct",
        entity_id=product.id,
        after={"active": False, "reason": str(reason)[:240]},
        event_code="MEDICATION_PRODUCT_DEACTIVATED",
    )
    return product


@transaction.atomic
def set_instruction_template(
    *, organisation, facility, actor, product_id, content, expected_version, request=None
):
    assert_transaction_active()
    product = MedicationProduct.objects.select_for_update().filter(
        id=product_id, organisation=organisation, facility=facility
    ).first()
    if product is None:
        raise CanonicalError("NOT_FOUND", "Product was not found.", status_code=404)
    if product.version != expected_version:
        raise CanonicalError("VERSION_CONFLICT", "The product changed; refresh.", status_code=409)
    product.instructions_template = str(content or "").strip()[:240]
    product.version += 1
    product.save(update_fields=["instructions_template", "version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="MedicationProduct",
        entity_id=product.id,
        after={"instructions_template": product.instructions_template},
        event_code="PRODUCT_INSTRUCTION_TEMPLATE_SET",
    )
    return product
