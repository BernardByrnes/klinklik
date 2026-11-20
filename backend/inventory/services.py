"""Inventory owner services: append-only movements, receiving, FEFO and alerts."""

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import uuid4
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, models, transaction

from audit.services import record_event, record_fact
from core.clock import local_service_date, now
from core.errors import CanonicalError
from core.services import assert_transaction_active
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
from pharmacy.models import MedicationProduct

EXPIRY_HORIZON_DAYS = 90
ADJUSTMENT_REASONS = {
    "EXPIRY_DISPOSAL",
    "DAMAGE",
    "BREAKAGE",
    "THEFT_LOSS",
    "COUNT_CORRECTION",
    "RETURN_TO_SUPPLIER",
    "DONATION_OUT",
    "OTHER",
}


def _money(value, label="quantity"):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CanonicalError("INVALID_INPUT", f"Enter a valid {label}.", status_code=400) from exc
    return amount


def _today():
    return local_service_date()


def batch_expiry_state(batch, *, horizon_days=EXPIRY_HORIZON_DAYS, today=None):
    today = today or _today()
    if batch.expiry_date < today:
        return "EXPIRED"
    if batch.expiry_date <= today + timedelta(days=horizon_days):
        return "EXPIRING_SOON"
    return "OK"


def batch_is_expired(batch, *, today=None):
    return batch.expiry_date < (today or _today())


def _lock_balance(*, organisation, facility, batch, location):
    balance = BatchLocationBalance.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        batch=batch,
        location=location,
    ).first()
    if balance is None:
        try:
            with transaction.atomic():
                balance = BatchLocationBalance.objects.create(
                    organisation=organisation,
                    facility=facility,
                    product=batch.product,
                    batch=batch,
                    location=location,
                )
        except IntegrityError:
            balance = BatchLocationBalance.objects.select_for_update().get(
                organisation=organisation,
                facility=facility,
                batch=batch,
                location=location,
            )
    return balance


def append_movement(
    *,
    organisation,
    facility,
    actor,
    product,
    batch,
    location,
    movement_type,
    quantity,
    source_type,
    source_id,
    reason_code="",
    receipt_line=None,
    allow_expired=False,
):
    """The only stock quantity writer: append a movement and update its balance."""

    assert_transaction_active()
    quantity = _money(quantity)
    if quantity == 0:
        raise CanonicalError("INVALID_INPUT", "A stock movement cannot be zero.", status_code=400)
    if str(batch.product_id) != str(product.id):
        raise CanonicalError("INVALID_INPUT", "The batch belongs to another product.", status_code=409)
    if batch_is_expired(batch) and quantity > 0 and not allow_expired:
        raise CanonicalError(
            "EXPIRED_BATCH",
            "Expired stock cannot receive a positive usable movement.",
            status_code=422,
        )
    if batch_is_expired(batch) and not location.is_quarantine and movement_type not in {
        "QUARANTINE",
        "WRITE_OFF",
        "TRANSFER_OUT",
    }:
        raise CanonicalError(
            "EXPIRED_BATCH",
            "Expired stock may only move to quarantine or write-off.",
            status_code=422,
        )
    balance = _lock_balance(
        organisation=organisation, facility=facility, batch=batch, location=location
    )
    new_quantity = (balance.quantity + quantity).quantize(Decimal("0.01"))
    if new_quantity < 0:
        raise CanonicalError(
            "INSUFFICIENT_STOCK",
            "The location does not hold enough stock for this movement.",
            status_code=409,
        )
    try:
        movement = StockMovement.objects.create(
            organisation=organisation,
            facility=facility,
            product=product,
            batch=batch,
            location=location,
            movement_type=movement_type,
            quantity=quantity,
            source_type=source_type,
            source_id=str(source_id),
            reason_code=reason_code,
            actor=actor,
            receipt_line=receipt_line,
        )
    except IntegrityError as exc:
        raise CanonicalError(
            "ALREADY_EXISTS", "This stock movement was already recorded.", status_code=409
        ) from exc
    balance.quantity = new_quantity
    balance.version += 1
    balance.save(update_fields=["quantity", "version", "updated_at"])
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="STOCK_MOVED",
        action="UPDATE",
        entity_type="StockMovement",
        entity_id=movement.id,
        source_ids={"batch_id": str(batch.id), "location_id": str(location.id)},
        before={"units_before": str(balance.quantity - quantity)},
        after={"units_after": str(balance.quantity)},
    )
    return movement


def ensure_default_location(*, organisation, facility):
    """INV-001: every facility has at least a usable Main Pharmacy location."""

    assert_transaction_active()
    location = StockLocation.objects.filter(
        organisation=organisation, facility=facility, active=True
    ).order_by("-is_default", "code").first()
    if location is not None:
        return location
    return StockLocation.objects.create(
        organisation=organisation,
        facility=facility,
        code="MAIN",
        name="Main Pharmacy",
        location_type="MAIN",
        is_default=True,
    )


def configure_location(
    *, organisation, facility, actor, code, name, location_type="STORE",
    is_default=False, is_quarantine=False, active=True, expected_version=None, request=None,
):
    assert_transaction_active()
    code = str(code or "").strip().upper()
    if not code or not str(name or "").strip():
        raise CanonicalError("INVALID_INPUT", "A location code and name are required.", status_code=400)
    location = StockLocation.objects.select_for_update().filter(
        organisation=organisation, facility=facility, code=code
    ).first()
    if location is not None and expected_version is not None and location.version != expected_version:
        raise CanonicalError("VERSION_CONFLICT", "The location changed; refresh.", status_code=409)
    if is_default:
        StockLocation.objects.filter(
            organisation=organisation, facility=facility, is_default=True
        ).exclude(id=getattr(location, "id", None)).update(is_default=False)
    if location is None:
        location = StockLocation.objects.create(
            organisation=organisation,
            facility=facility,
            code=code,
            name=str(name).strip(),
            location_type=location_type,
            is_default=is_default,
            is_quarantine=is_quarantine or location_type == "QUARANTINE",
            active=active,
        )
    else:
        location.name = str(name).strip()
        location.location_type = location_type
        location.is_default = is_default
        location.is_quarantine = is_quarantine or location_type == "QUARANTINE"
        location.active = active
        location.version += 1
        location.save(
            update_fields=[
                "name", "location_type", "is_default", "is_quarantine", "active",
                "version", "updated_at",
            ]
        )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE" if expected_version else "CREATE",
        entity_type="StockLocation",
        entity_id=location.id,
        after={"code": code, "name": location.name, "active": location.active},
        event_code="STOCK_LOCATION_CONFIGURED",
    )
    return location


def upsert_supplier(
    *, organisation, facility, actor, code, name, contact_person="", phone="",
    notes="", active=True, expected_version=None, request=None,
):
    assert_transaction_active()
    code = str(code or "").strip().upper()
    if not code or not str(name or "").strip():
        raise CanonicalError("INVALID_INPUT", "A supplier code and name are required.", status_code=400)
    supplier = Supplier.objects.select_for_update().filter(
        organisation=organisation, facility=facility, code=code
    ).first()
    if supplier is not None and expected_version is not None and supplier.version != expected_version:
        raise CanonicalError("VERSION_CONFLICT", "The supplier changed; refresh.", status_code=409)
    if supplier is None:
        supplier = Supplier.objects.create(
            organisation=organisation,
            facility=facility,
            code=code,
            name=str(name).strip(),
            contact_person=contact_person,
            phone=phone,
            notes=notes,
            active=active,
        )
    else:
        supplier.name = str(name).strip()
        supplier.contact_person = contact_person
        supplier.phone = phone
        supplier.notes = notes
        supplier.active = active
        supplier.version += 1
        supplier.save(
            update_fields=[
                "name", "contact_person", "phone", "notes", "active", "version", "updated_at"
            ]
        )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE" if expected_version else "CREATE",
        entity_type="Supplier",
        entity_id=supplier.id,
        after={"code": code, "name": supplier.name, "active": supplier.active},
        event_code="SUPPLIER_CONFIGURED",
    )
    return supplier


@transaction.atomic
def receive_stock(
    *,
    organisation,
    facility,
    actor,
    receipt_no,
    lines,
    supplier_id=None,
    supplier_name="",
    reference="",
    source_event_id=None,
    request=None,
):
    """CMD-063: receive only non-expired stock; all-or-nothing per receipt."""

    assert_transaction_active()
    receipt_no = str(receipt_no or "").strip()
    if not receipt_no or not lines:
        raise CanonicalError("INVALID_INPUT", "A receipt number and at least one line are required.", status_code=400)
    if StockReceipt.objects.filter(
        organisation=organisation, facility=facility, receipt_no=receipt_no
    ).exists():
        raise CanonicalError("ALREADY_EXISTS", "This receipt number was already posted.", status_code=409)
    supplier = None
    if supplier_id:
        supplier = Supplier.objects.filter(
            id=supplier_id, organisation=organisation, facility=facility, active=True
        ).first()
        if supplier is None:
            raise CanonicalError("INVALID_INPUT", "The supplier is not available.", status_code=409)
    elif str(supplier_name or "").strip():
        supplier_name = str(supplier_name).strip()[:160]
    accepted = []
    warning = False
    today = _today()
    for index, raw in enumerate(lines, start=1):
        product = MedicationProduct.objects.select_for_update().filter(
            id=raw.get("product_id"),
            organisation=organisation,
            facility=facility,
            active=True,
        ).first()
        if product is None:
            raise CanonicalError(
                "INVALID_INPUT", f"Line {index}: product was not found.", status_code=400
            )
        if product.controlled:
            raise CanonicalError(
                "UNSUPPORTED_OPERATION",
                f"Line {index}: controlled medicines are blocked in baseline V1.",
                status_code=422,
            )
        location = StockLocation.objects.select_for_update().filter(
            id=raw.get("location_id"),
            organisation=organisation,
            facility=facility,
            active=True,
        ).first()
        if location is None:
            raise CanonicalError(
                "INVALID_INPUT", f"Line {index}: stock location was not found.", status_code=400
            )
        try:
            expiry = raw.get("expiry_date")
            if isinstance(expiry, str):
                expiry = date.fromisoformat(expiry)
        except (TypeError, ValueError) as exc:
            raise CanonicalError(
                "INVALID_INPUT", f"Line {index}: expiry date is invalid.", status_code=400
            ) from exc
        if expiry is None:
            raise CanonicalError("INVALID_INPUT", f"Line {index}: expiry date is required.", status_code=400)
        if expiry < today:
            raise CanonicalError(
                "EXPIRED_STOCK_CANNOT_BE_RECEIVED",
                f"Line {index}: expired stock cannot be received.",
                status_code=422,
            )
        if expiry <= today + timedelta(days=EXPIRY_HORIZON_DAYS):
            warning = True
        quantity = _money(raw.get("quantity"))
        if quantity <= 0:
            raise CanonicalError(
                "INVALID_INPUT", f"Line {index}: quantity must be positive.", status_code=400
            )
        batch = StockBatch.objects.select_for_update().filter(
            organisation=organisation,
            facility=facility,
            product=product,
            batch_no=str(raw.get("batch_no") or "").strip(),
            expiry_date=expiry,
        ).first()
        if batch is None:
            batch_no = str(raw.get("batch_no") or "").strip()
            if not batch_no:
                raise CanonicalError(
                    "INVALID_INPUT", f"Line {index}: batch number is required.", status_code=400
                )
            try:
                with transaction.atomic():
                    batch = StockBatch.objects.create(
                        organisation=organisation,
                        facility=facility,
                        product=product,
                        batch_no=batch_no,
                        expiry_date=expiry,
                        supplier=supplier,
                    )
            except IntegrityError:
                batch = StockBatch.objects.select_for_update().get(
                    organisation=organisation,
                    facility=facility,
                    product=product,
                    batch_no=batch_no,
                    expiry_date=expiry,
                )
        accepted.append((index, product, location, batch, quantity, raw.get("unit_cost")))
    receipt = StockReceipt.objects.create(
        organisation=organisation,
        facility=facility,
        receipt_no=receipt_no,
        supplier=supplier,
        supplier_name=supplier_name,
        reference=str(reference or "")[:120],
        warning_near_expiry=warning,
        posted_by=actor,
        source_event_id=source_event_id or f"GRN:{facility.id}:{receipt_no}",
    )
    movements = []
    for index, product, location, batch, quantity, unit_cost in accepted:
        line = StockReceiptLine.objects.create(
            organisation=organisation,
            facility=facility,
            receipt=receipt,
            product=product,
            batch=batch,
            location=location,
            quantity=quantity,
            unit_cost=_money(unit_cost) if unit_cost not in (None, "") else None,
            line_no=index,
        )
        movements.append(
            append_movement(
                organisation=organisation,
                facility=facility,
                actor=actor,
                product=product,
                batch=batch,
                location=location,
                movement_type="IN_GRN",
                quantity=quantity,
                source_type="StockReceiptLine",
                source_id=str(line.id),
                receipt_line=line,
            )
        )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="StockReceipt",
        entity_id=receipt.id,
        after={
            "receipt_no": receipt.receipt_no,
            "line_count": len(movements),
            "warning_near_expiry": warning,
        },
        event_code="STOCK_RECEIVED",
    )
    return receipt, movements


def transfer_stock(
    *, organisation, facility, actor, batch_id, from_location_id, to_location_id,
    quantity, reason="", request=None,
):
    assert_transaction_active()
    quantity = _money(quantity)
    if quantity <= 0:
        raise CanonicalError("INVALID_INPUT", "Quantity must be positive.", status_code=400)
    batch = StockBatch.objects.select_for_update().filter(
        id=batch_id, organisation=organisation, facility=facility
    ).first()
    source = StockLocation.objects.select_for_update().filter(
        id=from_location_id, organisation=organisation, facility=facility, active=True
    ).first()
    destination = StockLocation.objects.select_for_update().filter(
        id=to_location_id, organisation=organisation, facility=facility, active=True
    ).first()
    if batch is None or source is None or destination is None:
        raise CanonicalError("NOT_FOUND", "The batch or location was not found.", status_code=404)
    if source.id == destination.id:
        raise CanonicalError("INVALID_INPUT", "Choose a different destination.", status_code=400)
    if batch_is_expired(batch) and not destination.is_quarantine:
        raise CanonicalError(
            "EXPIRED_BATCH", "Expired stock may only transfer to quarantine.", status_code=422
        )
    transaction_key = str(uuid4())
    out = append_movement(
        organisation=organisation,
        facility=facility,
        actor=actor,
        product=batch.product,
        batch=batch,
        location=source,
        movement_type="TRANSFER_OUT",
        quantity=-quantity,
        source_type="StockTransfer",
        source_id=transaction_key,
        reason_code=str(reason or "")[:40],
        allow_expired=destination.is_quarantine,
    )
    incoming = append_movement(
        organisation=organisation,
        facility=facility,
        actor=actor,
        product=batch.product,
        batch=batch,
        location=destination,
        movement_type="TRANSFER_IN",
        quantity=quantity,
        source_type="StockTransfer",
        source_id=transaction_key,
        reason_code=str(reason or "")[:40],
        allow_expired=destination.is_quarantine,
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="StockBatch",
        entity_id=batch.id,
        after={"from": str(source.id), "to": str(destination.id), "quantity": str(quantity)},
        event_code="STOCK_TRANSFERRED",
    )
    return out, incoming


def adjust_stock(
    *, organisation, facility, actor, batch_id, location_id, quantity, reason_code,
    note="", request=None,
):
    assert_transaction_active()
    if reason_code not in ADJUSTMENT_REASONS:
        raise CanonicalError("INVALID_INPUT", "Select a valid adjustment reason.", status_code=400)
    if reason_code == "OTHER" and not str(note or "").strip():
        raise CanonicalError("INVALID_INPUT", "A note is required for OTHER.", status_code=400)
    quantity = _money(quantity)
    if quantity == 0:
        raise CanonicalError("INVALID_INPUT", "The adjustment cannot be zero.", status_code=400)
    batch = StockBatch.objects.select_for_update().filter(
        id=batch_id, organisation=organisation, facility=facility
    ).first()
    location = StockLocation.objects.select_for_update().filter(
        id=location_id, organisation=organisation, facility=facility
    ).first()
    if batch is None or location is None:
        raise CanonicalError("NOT_FOUND", "The batch or location was not found.", status_code=404)
    if quantity > 0 and batch_is_expired(batch) and not location.is_quarantine:
        raise CanonicalError(
            "EXPIRED_BATCH",
            "Positive adjustments into expired stock must land in quarantine.",
            status_code=422,
        )
    movement = append_movement(
        organisation=organisation,
        facility=facility,
        actor=actor,
        product=batch.product,
        batch=batch,
        location=location,
        movement_type="WRITE_OFF" if quantity < 0 else "ADJUSTMENT",
        quantity=quantity,
        source_type="StockAdjustment",
        source_id=f"{batch.id}:{location.id}:{now().timestamp()}",
        reason_code=reason_code,
        allow_expired=location.is_quarantine,
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="StockMovement",
        entity_id=movement.id,
        after={"reason_code": reason_code, "note": str(note or "")[:240]},
        event_code="STOCK_ADJUSTED",
    )
    return movement


def stock_summary(
    *, organisation, facility, query="", category=None, status=None, location_id=None
):
    assert_transaction_active()
    products = MedicationProduct.objects.filter(
        organisation=organisation, facility=facility
    )
    if query:
        products = products.filter(
            models.Q(generic_name__icontains=query)
            | models.Q(brand_name__icontains=query)
            | models.Q(code__icontains=query)
        )
    if category:
        products = products.filter(category=str(category).upper())
    today = _today()
    rows = []
    for product in products.order_by("generic_name", "id"):
        balances = BatchLocationBalance.objects.filter(
            organisation=organisation, facility=facility, product=product
        ).select_related("batch", "location")
        if location_id:
            balances = balances.filter(location_id=location_id)
        usable = Decimal("0.00")
        expired = Decimal("0.00")
        quarantined = Decimal("0.00")
        by_location = {}
        by_location_name = {}
        batch_ids = set()
        earliest = None
        states = set()
        for balance in balances:
            if balance.quantity == 0:
                continue
            batch_ids.add(balance.batch_id)
            if balance.location.is_quarantine:
                quarantined += balance.quantity
                by_location_name[f"{balance.location.name} (quarantine)"] = str(
                    Decimal(by_location_name.get(f"{balance.location.name} (quarantine)", "0.00"))
                    + balance.quantity
                )
            else:
                state = batch_expiry_state(balance.batch, today=today)
                states.add(state)
                if state == "EXPIRED":
                    expired += balance.quantity
                else:
                    usable += balance.quantity
                    if earliest is None or balance.batch.expiry_date < earliest:
                        earliest = balance.batch.expiry_date
                by_location_name[balance.location.name] = str(
                    Decimal(by_location_name.get(balance.location.name, "0.00"))
                    + balance.quantity
                )
            by_location[str(balance.location_id)] = str(
                Decimal(by_location.get(str(balance.location_id), "0.00")) + balance.quantity
            )
        chip = "OUT" if usable == 0 else "OK"
        if "EXPIRING_SOON" in states:
            chip = "EXPIRING_SOON"
        if expired > 0 and usable == 0:
            chip = "EXPIRED"
        threshold = InventoryThreshold.objects.filter(
            organisation=organisation, facility=facility, product=product
        ).first()
        if threshold is not None and usable <= threshold.reorder_level and usable > 0:
            chip = "LOW"
        if status and chip != str(status).upper():
            continue
        rows.append(
            {
                "product_id": str(product.id),
                "code": product.code,
                "generic_name": product.generic_name,
                "brand_name": product.brand_name,
                "dosage_form": product.dosage_form,
                "strength": product.strength,
                "category": product.category,
                "controlled": product.controlled,
                "usable_quantity": str(usable),
                "expired_quantity": str(expired),
                "quarantined_quantity": str(quarantined),
                "total_quantity": str(usable + expired + quarantined),
                "batch_count": len(batch_ids),
                "earliest_expiry": earliest.isoformat() if earliest else None,
                "status": chip,
                "by_location": by_location,
                "by_location_name": by_location_name,
                "reorder_level": str(threshold.reorder_level) if threshold else None,
            }
        )
    return rows


def fefo_selection(*, organisation, facility, product_id, quantity, location_id=None):
    assert_transaction_active()
    quantity = _money(quantity)
    if quantity <= 0:
        raise CanonicalError("INVALID_INPUT", "Quantity must be positive.", status_code=400)
    balances = BatchLocationBalance.objects.filter(
        organisation=organisation,
        facility=facility,
        product_id=product_id,
        quantity__gt=0,
    )
    if location_id:
        balances = balances.filter(location_id=location_id)
    balances = balances.select_related("batch", "location").order_by(
        "batch__expiry_date", "batch__batch_no", "id"
    )
    today = _today()
    proposals = []
    remaining = quantity
    for balance in balances:
        if batch_is_expired(balance.batch, today=today):
            continue
        if balance.location.is_quarantine:
            continue
        take = min(balance.quantity, remaining)
        if take <= 0:
            continue
        proposals.append(
            {
                "batch_id": str(balance.batch_id),
                "batch_no": balance.batch.batch_no,
                "expiry_date": balance.batch.expiry_date.isoformat(),
                "location_id": str(balance.location_id),
                "available": str(balance.quantity),
                "quantity": str(take),
            }
        )
        remaining -= take
        if remaining == 0:
            break
    if remaining > 0:
        raise CanonicalError(
            "INSUFFICIENT_STOCK",
            "No non-expired batch covers the requested quantity.",
            status_code=409,
        )
    return proposals


def ledger_movements(
    *, organisation, facility, batch_id=None, movement_type=None,
    location_id=None, date_from=None, date_to=None,
):
    assert_transaction_active()
    movements = StockMovement.objects.filter(
        organisation=organisation, facility=facility
    ).select_related("batch", "location", "product")
    if batch_id:
        movements = movements.filter(batch_id=batch_id)
    if movement_type:
        movements = movements.filter(movement_type=str(movement_type).upper())
    if location_id:
        movements = movements.filter(location_id=location_id)
    if date_from:
        movements = movements.filter(occurred_at__date__gte=date_from)
    if date_to:
        movements = movements.filter(occurred_at__date__lte=date_to)
    return movements.order_by("occurred_at", "id")


def upsert_threshold(
    *, organisation, facility, actor, product_id, reorder_level, location_id=None,
    expected_version=None, request=None,
):
    assert_transaction_active()
    product = MedicationProduct.objects.filter(
        id=product_id, organisation=organisation, facility=facility
    ).first()
    if product is None:
        raise CanonicalError("NOT_FOUND", "Product was not found.", status_code=404)
    location = None
    if location_id:
        location = StockLocation.objects.filter(
            id=location_id, organisation=organisation, facility=facility
        ).first()
        if location is None:
            raise CanonicalError("NOT_FOUND", "Stock location was not found.", status_code=404)
    reorder_level = _money(reorder_level, "reorder level")
    if reorder_level < 0:
        raise CanonicalError("INVALID_INPUT", "The reorder level cannot be negative.", status_code=400)
    threshold = InventoryThreshold.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        product=product,
        location=location,
    ).first()
    if threshold is not None and expected_version is not None and threshold.version != expected_version:
        raise CanonicalError("VERSION_CONFLICT", "The threshold changed; refresh.", status_code=409)
    if threshold is None:
        threshold = InventoryThreshold.objects.create(
            organisation=organisation,
            facility=facility,
            product=product,
            location=location,
            reorder_level=reorder_level,
        )
    else:
        threshold.reorder_level = reorder_level
        threshold.version += 1
        threshold.save(update_fields=["reorder_level", "version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE" if expected_version else "CREATE",
        entity_type="InventoryThreshold",
        entity_id=threshold.id,
        after={"product_id": str(product.id), "reorder_level": str(reorder_level)},
        event_code="INVENTORY_THRESHOLD_SET",
    )
    return threshold


def stock_batches(
    *, organisation, facility, product_id=None, location_id=None,
    expiry_from=None, expiry_to=None,
):
    assert_transaction_active()
    batches = StockBatch.objects.filter(
        organisation=organisation, facility=facility
    ).select_related("product")
    if product_id:
        batches = batches.filter(product_id=product_id)
    if expiry_from:
        batches = batches.filter(expiry_date__gte=expiry_from)
    if expiry_to:
        batches = batches.filter(expiry_date__lte=expiry_to)
    rows = []
    for batch in batches.order_by("expiry_date", "batch_no", "id"):
        balances = BatchLocationBalance.objects.filter(
            organisation=organisation, facility=facility, batch=batch
        ).select_related("location")
        if location_id:
            balances = balances.filter(location_id=location_id)
        rows.append(
            {
                "id": str(batch.id),
                "product_id": str(batch.product_id),
                "batch_no": batch.batch_no,
                "expiry_date": batch.expiry_date.isoformat(),
                "status": batch_expiry_state(batch),
                "locations": [
                    {
                        "location_id": str(balance.location_id),
                        "location_name": balance.location.name,
                        "quantity": str(balance.quantity),
                    }
                    for balance in balances
                    if balance.quantity != 0
                ],
            }
        )
    return rows


def reconcile_ledger(*, organisation, facility, actor, request=None):
    """Read-only INV-003 reconciliation; append one audit fact, mutate no stock."""

    assert_transaction_active()
    discrepancies = []
    balances = list(
        BatchLocationBalance.objects.select_for_update()
        .filter(organisation=organisation, facility=facility)
        .order_by("id")
    )
    for balance in balances:
        derived = sum(
            (
                movement.quantity
                for movement in StockMovement.objects.filter(
                    organisation=organisation,
                    facility=facility,
                    batch=balance.batch,
                    location=balance.location,
                )
            ),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
        if derived != balance.quantity:
            discrepancies.append(
                {
                    "batch_id": str(balance.batch_id),
                    "location_id": str(balance.location_id),
                    "cached": str(balance.quantity),
                    "derived": str(derived),
                }
            )
    event_code = (
        "STOCK_LEDGER_DISCREPANCY_DETECTED"
        if discrepancies
        else "STOCK_LEDGER_RECONCILIATION_PASSED"
    )
    fact = record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code=event_code,
        action="READ",
        entity_type="InventoryLedger",
        entity_id=str(facility.id),
        source_ids={"facility_id": str(facility.id)},
        after={
            "discrepancy_count": len(discrepancies),
            "discrepancies": discrepancies[:20],
        },
    )
    return fact, discrepancies


def product_ledger(*, organisation, facility, product_id, date_from=None, date_to=None, batch_id=None, movement_type=None):
    """Chronological ledger with a running balance recomputed from zero."""

    assert_transaction_active()
    movements = StockMovement.objects.filter(
        organisation=organisation, facility=facility, product_id=product_id
    )
    if date_from:
        movements = movements.filter(occurred_at__date__gte=date_from)
    if date_to:
        movements = movements.filter(occurred_at__date__lte=date_to)
    if batch_id:
        movements = movements.filter(batch_id=batch_id)
    if movement_type:
        movements = movements.filter(movement_type=str(movement_type).upper())
    running = Decimal("0.00")
    rows = []
    for movement in movements.select_related("batch", "location").order_by("occurred_at", "id"):
        running = (running + movement.quantity).quantize(Decimal("0.01"))
        rows.append(
            {
                "id": str(movement.id),
                "occurred_at": movement.occurred_at,
                "movement_type": movement.movement_type,
                "quantity": str(movement.quantity),
                "running_balance": str(running),
                "batch_id": str(movement.batch_id),
                "batch_no": movement.batch.batch_no,
                "location_id": str(movement.location_id),
                "location_name": movement.location.name,
                "source_type": movement.source_type,
                "source_id": movement.source_id,
                "actor_id": str(movement.actor_id),
                "reason_code": movement.reason_code,
            }
        )
    return rows


def export_movements_csv(*, organisation, facility, actor, request=None, **filters):
    import csv
    import io

    rows = product_ledger(
        organisation=organisation, facility=facility, **filters
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "occurred_at",
            "movement_type",
            "quantity",
            "running_balance",
            "batch_no",
            "location",
            "source_type",
            "source_id",
            "actor_id",
            "reason_code",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["occurred_at"].isoformat(),
                row["movement_type"],
                row["quantity"],
                row["running_balance"],
                row["batch_no"],
                row["location_name"],
                row["source_type"],
                row["source_id"],
                row["actor_id"],
                row["reason_code"],
            ]
        )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="EXPORT",
        entity_type="StockLedger",
        entity_id=str(facility.id),
        after={"row_count": len(rows)},
        event_code="INVENTORY_LEDGER_EXPORTED",
    )
    return buffer.getvalue()
