"""S-10 stock counts: blind snapshot, submission and approved counter-movements."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from django.db import transaction

from audit.services import record_event
from core.clock import now
from core.errors import CanonicalError
from core.services import assert_transaction_active
from inventory.models import (
    BatchLocationBalance,
    QuarantineRecord,
    StockAdjustment,
    StockBatch,
    StockCount,
    StockCountLine,
    StockLocation,
    StockMovement,
    DisposalRecord,
)
from inventory.services import (
    _money,
    append_movement,
    batch_is_expired,
    transfer_stock,
)
from pharmacy.models import ProductPrice
from tenancy.models import FacilityWorkflowPolicy

ZERO_UUID = UUID("00000000-0000-0000-0000-000000000000")


def adjustment_threshold(*, organisation, facility):
    policy = FacilityWorkflowPolicy.objects.filter(
        organisation=organisation, facility=facility
    ).first()
    if policy is None or policy.stock_adjustment_approval_threshold is None:
        raise CanonicalError(
            "PREREQUISITE_MISSING",
            "The stock adjustment approval threshold is not configured.",
            status_code=422,
        )
    return policy, policy.stock_adjustment_approval_threshold


def _latest_price(*, organisation, facility, product):
    return ProductPrice.objects.filter(
        organisation=organisation, facility=facility, product=product
    ).order_by("-effective_from", "-id").first()


def adjustment_value(*, organisation, facility, product, quantity):
    price = _latest_price(organisation=organisation, facility=facility, product=product)
    if price is None:
        return Decimal("0.00")
    return (abs(quantity) * price.amount).quantize(Decimal("0.01"))


def _count_context(*, organisation, facility, count_id):
    count = StockCount.objects.select_for_update().filter(
        id=count_id, organisation=organisation, facility=facility
    ).first()
    if count is None:
        raise CanonicalError("NOT_FOUND", "Stock count was not found.", status_code=404)
    lines = list(
        StockCountLine.objects.select_for_update()
        .filter(count=count)
        .select_related("product", "batch", "location")
        .order_by("id")
    )
    return count, lines


def open_count(*, organisation, facility, actor, location_id, request=None):
    assert_transaction_active()
    location = StockLocation.objects.select_for_update().filter(
        id=location_id, organisation=organisation, facility=facility, active=True
    ).first()
    if location is None:
        raise CanonicalError("NOT_FOUND", "Stock location was not found.", status_code=404)
    active = StockCount.objects.filter(
        organisation=organisation,
        facility=facility,
        location=location,
        state__in=["DRAFT", "SUBMITTED", "PENDING_APPROVAL"],
    ).first()
    if active is not None:
        raise CanonicalError(
            "ALREADY_EXISTS",
            "An open count already exists for this location.",
            status_code=409,
            metadata={"stock_count_id": str(active.id)},
        )
    balances = list(
        BatchLocationBalance.objects.select_for_update()
        .filter(organisation=organisation, facility=facility, location=location)
        .select_related("product", "batch")
        .order_by("id")
    )
    watermark = (
        StockMovement.objects.filter(
            organisation=organisation, facility=facility, location=location
        ).order_by("-occurred_at", "-id").values_list("id", flat=True).first()
        or ZERO_UUID
    )
    count = StockCount.objects.create(
        organisation=organisation,
        facility=facility,
        location=location,
        snapshot_movement_watermark=watermark,
        opened_by=actor,
    )
    for balance in balances:
        StockCountLine.objects.create(
            organisation=organisation,
            facility=facility,
            count=count,
            product=balance.product,
            batch=balance.batch,
            location=location,
            expected_qty=balance.quantity,
            source_line_identity=f"{balance.batch_id}:{location.id}",
        )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="StockCount",
        entity_id=count.id,
        after={"location_id": str(location.id), "line_count": len(balances)},
        event_code="STOCK_COUNT_OPENED",
    )
    return count


def count_sheet(*, organisation, facility, count, reveal_expected=None):
    if reveal_expected is None:
        policy = FacilityWorkflowPolicy.objects.filter(
            organisation=organisation, facility=facility
        ).first()
        reveal_expected = not (policy.blind_stock_count if policy is not None else True)
    lines = count.lines.select_related("product", "batch", "location").order_by("id")
    body = []
    for line in lines:
        row = {
            "id": str(line.id),
            "product_id": str(line.product_id),
            "product_name": line.product.generic_name,
            "strength": line.product.strength,
            "batch_id": str(line.batch_id),
            "batch_no": line.batch.batch_no,
            "expiry_date": line.batch.expiry_date.isoformat(),
            "location_id": str(line.location_id),
            "counted_qty": str(line.counted_qty) if line.counted_qty is not None else None,
        }
        if reveal_expected:
            row["expected_qty"] = str(line.expected_qty)
            row["variance_qty"] = (
                str(line.variance_qty) if line.variance_qty is not None else None
            )
        body.append(row)
    return {
        "id": str(count.id),
        "state": count.state,
        "version": count.version,
        "location_id": str(count.location_id),
        "opened_at": count.created_at,
        "submitted_at": count.submitted_at,
        "approved_at": count.approved_at,
        "blind": not reveal_expected,
        "lines": body,
        "movements_during_count": [
            {
                "id": str(movement.id),
                "movement_type": movement.movement_type,
                "quantity": str(movement.quantity),
                "batch_id": str(movement.batch_id),
                "occurred_at": movement.occurred_at,
            }
            for movement in StockMovement.objects.filter(
                organisation=organisation,
                facility=facility,
                location_id=count.location_id,
                occurred_at__gte=count.created_at,
            ).order_by("occurred_at", "id")
        ],
    }


@transaction.atomic
def submit_count(
    *, organisation, facility, actor, count_id, expected_version, line_counts, request=None
):
    assert_transaction_active()
    count, lines = _count_context(
        organisation=organisation, facility=facility, count_id=count_id
    )
    if count.state != "DRAFT":
        raise CanonicalError("INVALID_STATE", "Only a draft count can be submitted.", status_code=409)
    if count.version != expected_version:
        raise CanonicalError("VERSION_CONFLICT", "The count changed; refresh.", status_code=409)
    by_id = {str(line.id): line for line in lines}
    supplied = {}
    for item in line_counts:
        line_id = str(item.get("line_id") or "")
        if line_id not in by_id:
            raise CanonicalError("INVALID_INPUT", "A count line was not found.", status_code=400)
        counted = _money(item.get("counted_qty"))
        if counted < 0:
            raise CanonicalError("INVALID_INPUT", "Counted quantity cannot be negative.", status_code=400)
        supplied[line_id] = counted
    if set(supplied) != set(by_id):
        raise CanonicalError(
            "PREREQUISITE_MISSING", "Every count line must be counted before submission.", 422
        )
    for line in lines:
        line.counted_qty = supplied[str(line.id)]
        line.variance_qty = (line.counted_qty - line.expected_qty).quantize(Decimal("0.01"))
        line.counted_by = actor
        line.save(update_fields=["counted_qty", "variance_qty", "counted_by", "updated_at"])
    count.state = "SUBMITTED"
    count.submitted_by = actor
    count.submitted_at = now()
    count.version += 1
    count.save(
        update_fields=["state", "submitted_by", "submitted_at", "version", "updated_at"]
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="SUBMIT",
        entity_type="StockCount",
        entity_id=count.id,
        after={"variance_count": sum(1 for line in lines if line.variance_qty)},
        event_code="STOCK_COUNT_SUBMITTED",
    )
    return count


@transaction.atomic
def approve_count(
    *,
    organisation,
    facility,
    actor,
    count_id,
    expected_version,
    approver_is_facility_admin=False,
    request=None,
):
    assert_transaction_active()
    count, lines = _count_context(
        organisation=organisation, facility=facility, count_id=count_id
    )
    if count.state != "SUBMITTED":
        raise CanonicalError("INVALID_STATE", "Only a submitted count can be approved.", status_code=409)
    if count.version != expected_version:
        raise CanonicalError("VERSION_CONFLICT", "The count changed; refresh.", status_code=409)
    policy, threshold = adjustment_threshold(organisation=organisation, facility=facility)
    total_value = sum(
        (
            adjustment_value(
                organisation=organisation,
                facility=facility,
                product=line.product,
                quantity=line.variance_qty or Decimal("0.00"),
            )
            for line in lines
        ),
        Decimal("0.00"),
    )
    if total_value > threshold:
        if not approver_is_facility_admin:
            raise CanonicalError(
                "APPROVAL_REQUIRED",
                "This count exceeds the threshold and needs FACILITY_ADMIN approval.",
                status_code=403,
            )
        if count.opened_by_id == getattr(actor, "id", actor):
            raise CanonicalError(
                "SEPARATION_OF_DUTIES_REQUIRED",
                "The counter cannot approve a threshold-exceeding count.",
                status_code=403,
            )
    adjustments = []
    for line in lines:
        variance = (line.variance_qty or Decimal("0.00")).quantize(Decimal("0.01"))
        if variance == 0:
            continue
        movement = append_movement(
            organisation=organisation,
            facility=facility,
            actor=actor,
            product=line.product,
            batch=line.batch,
            location=line.location,
            movement_type="ADJUSTMENT",
            quantity=variance,
            source_type="StockCountLine",
            source_id=str(line.id),
            reason_code="COUNT_CORRECTION",
            allow_expired=line.location.is_quarantine,
        )
        adjustments.append(
            StockAdjustment.objects.create(
                organisation=organisation,
                facility=facility,
                count=count,
                product=line.product,
                batch=line.batch,
                location=line.location,
                quantity=variance,
                reason_code="COUNT_CORRECTION",
                note="",
                state="POSTED",
                requested_by=count.opened_by,
                approved_by=actor,
                approved_at=now(),
                source_event_id=f"COUNT:{count.id}:{line.id}",
            )
        )
        record_event(
            request=request,
            organisation=organisation,
            actor=actor,
            facility=facility,
            action="UPDATE",
            entity_type="StockMovement",
            entity_id=movement.id,
            after={"count_id": str(count.id), "line_id": str(line.id)},
            event_code="STOCK_ADJUSTED",
        )
    count.state = "POSTED"
    count.approved_by = actor
    count.approved_at = now()
    count.approval_reason = policy.name if hasattr(policy, "name") else "BASE_THRESHOLD"
    count.version += 1
    count.save(
        update_fields=[
            "state", "approved_by", "approved_at", "approval_reason", "version", "updated_at"
        ]
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="StockCount",
        entity_id=count.id,
        after={"adjustment_count": len(adjustments), "value": str(total_value)},
        event_code="STOCK_COUNT_APPROVED",
    )
    return count, adjustments


@transaction.atomic
def quarantine_stock(
    *, organisation, facility, actor, batch_id, location_id, quantity, reason,
    source_type="MANUAL", source_id="", request=None,
):
    assert_transaction_active()
    if not str(reason or "").strip():
        raise CanonicalError("INVALID_INPUT", "A quarantine reason is required.", status_code=400)
    quantity = _money(quantity)
    if quantity <= 0:
        raise CanonicalError("INVALID_INPUT", "Quantity must be positive.", status_code=400)
    batch = StockBatch.objects.select_for_update().filter(
        id=batch_id, organisation=organisation, facility=facility
    ).first()
    source = StockLocation.objects.select_for_update().filter(
        id=location_id, organisation=organisation, facility=facility
    ).first()
    destination = StockLocation.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        is_quarantine=True,
        active=True,
    ).order_by("code").first()
    if batch is None or source is None or destination is None:
        raise CanonicalError(
            "PREREQUISITE_MISSING", "A quarantine location is required.", 422
        )
    if source.id == destination.id:
        raise CanonicalError("INVALID_INPUT", "Stock is already in quarantine.", status_code=409)
    transfer_stock(
        organisation=organisation,
        facility=facility,
        actor=actor,
        batch_id=batch.id,
        from_location_id=source.id,
        to_location_id=destination.id,
        quantity=quantity,
        reason=str(reason),
        request=request,
    )
    record = QuarantineRecord.objects.create(
        organisation=organisation,
        facility=facility,
        product=batch.product,
        batch=batch,
        location=destination,
        quantity=quantity,
        reason=str(reason)[:240],
        source_type=str(source_type)[:40],
        source_id=str(source_id or f"QUARANTINE:{batch.id}:{now().timestamp()}"),
        source_line_identity=str(batch.id),
        quarantined_by=actor,
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="QuarantineRecord",
        entity_id=record.id,
        after={"batch_id": str(batch.id), "reason": str(reason)[:240]},
        event_code="STOCK_QUARANTINED",
    )
    return record


@transaction.atomic
def dispose_stock(
    *, organisation, facility, actor, batch_id, location_id, quantity, reason,
    source_event_id="", request=None,
):
    assert_transaction_active()
    if not str(reason or "").strip():
        raise CanonicalError("INVALID_INPUT", "A disposal reason is required.", status_code=400)
    quantity = _money(quantity)
    if quantity <= 0:
        raise CanonicalError("INVALID_INPUT", "Quantity must be positive.", status_code=400)
    batch = StockBatch.objects.select_for_update().filter(
        id=batch_id, organisation=organisation, facility=facility
    ).first()
    location = StockLocation.objects.select_for_update().filter(
        id=location_id, organisation=organisation, facility=facility
    ).first()
    if batch is None or location is None:
        raise CanonicalError("NOT_FOUND", "The batch or location was not found.", status_code=404)
    if not location.is_quarantine and not batch_is_expired(batch):
        raise CanonicalError(
            "PREREQUISITE_MISSING",
            "Disposal is only for quarantined or expired stock.",
            status_code=422,
        )
    movement = append_movement(
        organisation=organisation,
        facility=facility,
        actor=actor,
        product=batch.product,
        batch=batch,
        location=location,
        movement_type="WRITE_OFF",
        quantity=-quantity,
        source_type="DisposalRecord",
        source_id=source_event_id or f"DISPOSAL:{batch.id}:{now().timestamp()}",
        reason_code="EXPIRY_DISPOSAL",
        allow_expired=True,
    )
    record = DisposalRecord.objects.create(
        organisation=organisation,
        facility=facility,
        product=batch.product,
        batch=batch,
        location=location,
        quantity=quantity,
        reason=str(reason)[:240],
        disposed_by=actor,
        source_event_id=source_event_id or f"DISPOSAL:{movement.id}",
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="DisposalRecord",
        entity_id=record.id,
        after={"batch_id": str(batch.id), "reason": str(reason)[:240]},
        event_code="STOCK_DISPOSED",
    )
    return record


@transaction.atomic
def create_adjustment(
    *,
    organisation,
    facility,
    actor,
    batch_id,
    location_id,
    quantity,
    reason_code,
    note="",
    reference="",
    request=None,
):
    assert_transaction_active()
    if reason_code not in dict(StockAdjustment._meta.get_field("reason_code").choices):
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
    _policy, threshold = adjustment_threshold(organisation=organisation, facility=facility)
    value = adjustment_value(
        organisation=organisation, facility=facility, product=batch.product, quantity=quantity
    )
    pending = value > threshold
    adjustment = StockAdjustment.objects.create(
        organisation=organisation,
        facility=facility,
        product=batch.product,
        batch=batch,
        location=location,
        quantity=quantity,
        reason_code=reason_code,
        note=str(note or "")[:240],
        reference=str(reference or "")[:120],
        state="PENDING_APPROVAL" if pending else "POSTED",
        requested_by=actor,
        approved_by=None if pending else actor,
        approved_at=None if pending else now(),
        source_event_id=f"ADJUSTMENT:{batch.id}:{location.id}:{now().timestamp()}",
    )
    if not pending:
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
            source_id=str(adjustment.id),
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
            after={"reason_code": reason_code},
            event_code="STOCK_ADJUSTED",
        )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="StockAdjustment",
        entity_id=adjustment.id,
        after={"state": adjustment.state, "reason_code": reason_code},
        event_code="STOCK_ADJUSTMENT_RECORDED",
    )
    return adjustment


@transaction.atomic
def approve_adjustment(
    *, organisation, facility, actor, adjustment_id, approver_is_facility_admin=False,
    request=None,
):
    assert_transaction_active()
    adjustment = StockAdjustment.objects.select_for_update().filter(
        id=adjustment_id, organisation=organisation, facility=facility
    ).first()
    if adjustment is None:
        raise CanonicalError("NOT_FOUND", "Stock adjustment was not found.", status_code=404)
    if adjustment.state != "PENDING_APPROVAL":
        raise CanonicalError("INVALID_STATE", "This adjustment is not pending approval.", status_code=409)
    if adjustment.requested_by_id == getattr(actor, "id", actor):
        raise CanonicalError(
            "SEPARATION_OF_DUTIES_REQUIRED",
            "The requester cannot approve their own adjustment.",
            status_code=403,
        )
    if not approver_is_facility_admin:
        raise CanonicalError(
            "APPROVAL_REQUIRED", "FACILITY_ADMIN approval is required.", 403
        )
    _policy, threshold = adjustment_threshold(organisation=organisation, facility=facility)
    value = adjustment_value(
        organisation=organisation,
        facility=facility,
        product=adjustment.product,
        quantity=adjustment.quantity,
    )
    if value <= threshold:
        raise CanonicalError("INVALID_STATE", "This adjustment no longer needs approval.", status_code=409)
    append_movement(
        organisation=organisation,
        facility=facility,
        actor=actor,
        product=adjustment.product,
        batch=adjustment.batch,
        location=adjustment.location,
        movement_type="WRITE_OFF" if adjustment.quantity < 0 else "ADJUSTMENT",
        quantity=adjustment.quantity,
        source_type="StockAdjustment",
        source_id=str(adjustment.id),
        reason_code=adjustment.reason_code,
        allow_expired=adjustment.location.is_quarantine,
    )
    adjustment.state = "POSTED"
    adjustment.approved_by = actor
    adjustment.approved_at = now()
    adjustment.version += 1
    adjustment.save(
        update_fields=["state", "approved_by", "approved_at", "version", "updated_at"]
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="StockAdjustment",
        entity_id=adjustment.id,
        after={"state": "POSTED"},
        event_code="STOCK_ADJUSTMENT_APPROVED",
    )
    return adjustment
