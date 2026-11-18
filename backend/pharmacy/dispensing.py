"""S-12 prescribing, dispensing and OTC owner services.

Every stock change goes through ``inventory.services.append_movement``. A
dispense confirmation moves stock, appends the exact billing charge and
commits the dispense state in one tenant transaction.
"""

from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.db import models, transaction

from audit.services import record_event
from billing.models import Invoice
from billing.services import issue_source_line, recompute_invoice_projection
from core.clock import local_service_date, now
from core.errors import CanonicalError
from core.services import assert_transaction_active
from inventory.services import append_movement, batch_is_expired, fefo_selection
from patients.models import Patient
from pharmacy.models import (
    Dispense,
    DispenseLine,
    MedicationProduct,
    OTCSale,
    OTCSaleLine,
    Prescription,
    PrescriptionClaim,
    PrescriptionItem,
    ProductPrice,
)
from tenancy.models import FacilityWorkflowPolicy


def _money(value, label="amount"):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CanonicalError(
            "INVALID_INPUT", f"Enter a valid {label}.", status_code=400
        ) from exc


def _price(*, organisation, facility, product):
    today = local_service_date()
    price = (
        ProductPrice.objects.filter(
            organisation=organisation,
            facility=facility,
            product=product,
            effective_from__lte=today,
        )
        .filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=today)
        )
        .order_by("-effective_from", "-id")
        .first()
    )
    if price is None:
        raise CanonicalError(
            "SERVICE_NOT_PRICED",
            "This product has no selling price.",
            status_code=422,
            metadata={"product_id": str(product.id)},
        )
    return price


def _policy(*, organisation, facility):
    return FacilityWorkflowPolicy.objects.filter(
        organisation=organisation, facility=facility
    ).first()


def _assigned_claim(*, prescription, actor):
    claim = (
        PrescriptionClaim.objects.select_for_update()
        .filter(prescription=prescription, released_at__isnull=True)
        .first()
    )
    actor_id = getattr(actor, "id", actor)
    if claim is not None and claim.claimed_by_id != actor_id:
        raise CanonicalError(
            "PRESCRIPTION_CLAIMED",
            "Another pharmacist is preparing this prescription.",
            status_code=409,
        )
    return claim


def _remaining_quantity(*, item):
    dispensed = (
        DispenseLine.objects.filter(
            prescription_item=item,
            dispense__status__in=("PROVISIONAL", "AWAITING_PAYMENT", "CONFIRMED"),
        ).aggregate(total=models.Sum("quantity"))["total"]
        or Decimal("0.00")
    )
    return max(item.quantity - dispensed, Decimal("0.00"))


@transaction.atomic
def save_draft(
    *,
    organisation,
    facility,
    actor,
    encounter_id,
    items,
    source_prescription_id=None,
    request=None,
):
    """Create or replace the single DRAFT prescription for an open Encounter."""

    assert_transaction_active()
    from clinical.models import Encounter

    encounter = (
        Encounter.objects.select_for_update()
        .filter(id=encounter_id, organisation=organisation, facility=facility)
        .first()
    )
    if encounter is None:
        raise CanonicalError("NOT_FOUND", "Encounter was not found.", status_code=404)
    if encounter.status != "OPEN":
        raise CanonicalError(
            "INVALID_STATE", "A signed Encounter cannot be prescribed to.", status_code=409
        )
    if not items:
        raise CanonicalError(
            "INVALID_INPUT", "Add at least one prescription item.", status_code=400
        )
    source = None
    if source_prescription_id:
        source = Prescription.objects.filter(
            id=source_prescription_id, organisation=organisation, facility=facility
        ).first()
        if source is None:
            raise CanonicalError(
                "NOT_FOUND", "The source prescription was not found.", status_code=404
            )
    prescription = (
        Prescription.objects.select_for_update()
        .filter(
            organisation=organisation,
            facility=facility,
            encounter=encounter,
            status="DRAFT",
        )
        .first()
    )
    created = prescription is None
    if prescription is None:
        prescription = Prescription.objects.create(
            organisation=organisation,
            facility=facility,
            visit=encounter.visit,
            encounter=encounter,
            patient=encounter.patient,
            prescribed_by=actor,
            source_prescription=source,
        )
    else:
        prescription.items.all().delete()
    staged = []
    for raw in items:
        product = None
        if raw.get("product_id"):
            product = MedicationProduct.objects.filter(
                id=raw["product_id"],
                organisation=organisation,
                facility=facility,
            ).first()
            if product is None:
                raise CanonicalError(
                    "NOT_FOUND", "The product was not found.", status_code=404
                )
            if product.controlled:
                raise CanonicalError(
                    "CONTROLLED_NOT_SUPPORTED",
                    "Controlled medicines are not supported in this system.",
                    status_code=403,
                )
            if not product.active:
                raise CanonicalError(
                    "INVALID_STATE", "This product is inactive.", status_code=409
                )
        medicine_name = str(
            raw.get("medicine_name") or (product.generic_name if product else "")
        ).strip()
        if not medicine_name:
            raise CanonicalError(
                "INVALID_INPUT", "A medicine name is required.", status_code=400
            )
        quantity = _money(raw.get("quantity"), "quantity")
        if quantity <= 0:
            raise CanonicalError(
                "INVALID_INPUT", "Quantity must be positive.", status_code=400
            )
        staged.append(
            {
                "product": product,
                "medicine_name": medicine_name[:200],
                "dose_amount": _money(raw.get("dose_amount", "1"), "dose"),
                "dose_unit": str(raw.get("dose_unit") or "unit")[:30],
                "route": str(raw.get("route") or "PO")[:20],
                "frequency": str(raw.get("frequency") or "OD")[:30],
                "duration_value": int(raw.get("duration_value") or 1),
                "duration_unit": str(raw.get("duration_unit") or "DAYS")[:20],
                "quantity": quantity,
                "instructions": str(raw.get("instructions") or "")[:500],
                "external": product is None,
            }
        )
    for fields in staged:
        PrescriptionItem.objects.create(
            organisation=organisation,
            facility=facility,
            prescription=prescription,
            **fields,
        )
    prescription.version += 1
    prescription.save(update_fields=["version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE" if created else "UPDATE",
        entity_type="Prescription",
        entity_id=prescription.id,
        after={"item_count": len(staged), "status": prescription.status},
        event_code="PRESCRIPTION_DRAFT_SAVED",
    )
    return prescription


@transaction.atomic
def activate_for_encounter(*, encounter, actor=None, request=None):
    """Activate the Encounter's draft when the Encounter is signed."""

    assert_transaction_active()
    prescription = (
        Prescription.objects.select_for_update()
        .filter(
            organisation_id=encounter.organisation_id,
            encounter=encounter,
            status="DRAFT",
        )
        .first()
    )
    if prescription is None:
        return None
    internal = prescription.items.filter(external=False).exists()
    prescription.status = "ACTIVE" if internal else "NOT_DISPENSED"
    prescription.version += 1
    prescription.save(update_fields=["status", "version", "updated_at"])
    record_event(
        request=request,
        organisation=prescription.organisation,
        actor=actor,
        facility=prescription.facility,
        action="UPDATE",
        entity_type="Prescription",
        entity_id=prescription.id,
        after={"status": prescription.status},
        event_code="PRESCRIPTION_ACTIVATED",
    )
    return prescription


def queue(*, organisation, facility):
    """Active, partially dispensed and uncollected prescription projection."""

    assert_transaction_active()
    today = local_service_date()
    policy = _policy(organisation=organisation, facility=facility)
    window = policy.prescription_uncollected_window_days if policy else 7
    active_rows = []
    partial_rows = []
    uncollected_rows = []
    prescriptions = (
        Prescription.objects.filter(
            organisation=organisation,
            facility=facility,
            status__in=("ACTIVE", "COMPLETED"),
        )
        .select_related("patient", "encounter", "prescribed_by")
        .order_by("created_at")
    )
    for prescription in prescriptions:
        items = list(prescription.items.all())
        dispensed = sum(
            1 for item in items if item.state in {"DISPENSED", "PARTIALLY_DISPENSED"}
        )
        age_days = (today - local_service_date(prescription.created_at)).days
        row = {
            "prescription_id": str(prescription.id),
            "patient_name": prescription.patient.display_name,
            "patient_no": prescription.patient.patient_no,
            "prescribed_by": str(prescription.prescribed_by_id),
            "prescribed_at": prescription.created_at,
            "item_count": len(items),
            "state": prescription.status,
            "dispensed_count": dispensed,
            "age_days": age_days,
            "items": [
                {
                    "id": str(item.id),
                    "medicine_name": item.medicine_name,
                    "quantity": str(item.quantity),
                    "state": item.state,
                }
                for item in items
            ],
        }
        if prescription.status == "ACTIVE" and age_days > window:
            uncollected_rows.append(row)
        elif 0 < dispensed < len(items):
            partial_rows.append(row)
        elif prescription.status == "ACTIVE":
            active_rows.append(row)
    return {
        "active": active_rows,
        "partially_dispensed": partial_rows,
        "uncollected": uncollected_rows,
        "uncollected_window_days": window,
    }


@transaction.atomic
def claim_prescription(
    *, organisation, facility, actor, prescription_id, request=None
):
    """Claim an ACTIVE prescription; the partial unique index picks one winner."""

    assert_transaction_active()
    prescription = (
        Prescription.objects.select_for_update()
        .filter(
            id=prescription_id,
            organisation=organisation,
            facility=facility,
            status="ACTIVE",
        )
        .first()
    )
    if prescription is None:
        raise CanonicalError(
            "NOT_FOUND", "Active prescription was not found.", status_code=404
        )
    existing = (
        PrescriptionClaim.objects.select_for_update()
        .filter(prescription=prescription, released_at__isnull=True)
        .first()
    )
    if existing is not None:
        if existing.claimed_by_id == getattr(actor, "id", actor):
            return existing, False
        raise CanonicalError(
            "PRESCRIPTION_CLAIMED",
            "Another pharmacist is preparing this prescription.",
            status_code=409,
        )
    claim = PrescriptionClaim.objects.create(
        organisation=organisation,
        facility=facility,
        prescription=prescription,
        claimed_by=actor,
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="Prescription",
        entity_id=prescription.id,
        after={"claimed_by": str(actor.id)},
        event_code="PRESCRIPTION_CLAIMED",
    )
    return claim, True


def _validate_substitution(prescribed, chosen):
    if prescribed is None or chosen is None:
        return False
    if prescribed.id == chosen.id:
        return False
    if (
        prescribed.generic_name.strip().lower() == chosen.generic_name.strip().lower()
        and prescribed.strength.strip().lower() == chosen.strength.strip().lower()
        and prescribed.dosage_form == chosen.dosage_form
    ):
        return True
    raise CanonicalError(
        "SUBSTITUTION_NOT_ALLOWED",
        "Substitution requires the same generic, strength and form.",
        status_code=409,
    )


@transaction.atomic
def prepare_dispense(
    *,
    organisation,
    facility,
    actor,
    prescription_id,
    lines,
    request=None,
):
    """Create the provisional dispense and FEFO batch lines; stock is untouched."""

    assert_transaction_active()
    prescription = (
        Prescription.objects.select_for_update()
        .filter(
            id=prescription_id,
            organisation=organisation,
            facility=facility,
            status="ACTIVE",
        )
        .select_related("encounter", "visit", "patient")
        .first()
    )
    if prescription is None:
        raise CanonicalError(
            "NOT_FOUND", "Active prescription was not found.", status_code=404
        )
    _assigned_claim(prescription=prescription, actor=actor)
    if prescription.encounter_id and prescription.encounter.status != "SIGNED":
        raise CanonicalError(
            "INVALID_STATE", "The prescription is not active yet.", status_code=409
        )
    items = {str(item.id): item for item in prescription.items.all()}
    if not lines:
        raise CanonicalError(
            "INVALID_INPUT", "Select at least one item to dispense.", status_code=400
        )
    dispense = Dispense.objects.create(
        organisation=organisation,
        facility=facility,
        prescription=prescription,
        patient=prescription.patient,
        visit=prescription.visit,
        status="PROVISIONAL",
        prepared_by=actor,
        currency=organisation.default_currency,
        source_event_id=f"DISPENSE:{uuid4().hex}",
    )
    total = Decimal("0.00")
    for raw in lines:
        item = items.get(str(raw.get("prescription_item_id") or ""))
        if item is None:
            raise CanonicalError(
                "INVALID_INPUT", "A prescription item was not found.", status_code=400
            )
        if item.state in {"DISPENSED", "CANCELLED", "NOT_DISPENSED"}:
            raise CanonicalError(
                "INVALID_STATE", "This item is already terminal.", status_code=409
            )
        if item.external or item.product is None:
            raise CanonicalError(
                "INVALID_STATE", "An external item cannot be dispensed here.", status_code=409
            )
        chosen = item.product
        if raw.get("product_id") and str(raw["product_id"]) != str(item.product_id):
            chosen = MedicationProduct.objects.filter(
                id=raw["product_id"],
                organisation=organisation,
                facility=facility,
            ).first()
            if chosen is None:
                raise CanonicalError(
                    "NOT_FOUND", "The substitute product was not found.", status_code=404
                )
            if chosen.controlled:
                raise CanonicalError(
                    "CONTROLLED_NOT_SUPPORTED",
                    "Controlled medicines are not supported.",
                    status_code=403,
                )
            if not chosen.active:
                raise CanonicalError(
                    "INVALID_STATE", "The substitute product is inactive.", status_code=409
                )
        substituted = _validate_substitution(item.product, chosen)
        if substituted and not str(raw.get("substitution_reason") or "").strip():
            raise CanonicalError(
                "INVALID_INPUT", "A substitution reason is required.", status_code=400
            )
        if substituted and not (
            raw.get("prescriber_consulted")
            and str(raw.get("prescriber_consulted_name") or "").strip()
        ):
            raise CanonicalError(
                "SUBSTITUTION_EVIDENCE_REQUIRED",
                "Record prescriber consultation before substituting.",
                status_code=409,
            )
        remaining = _remaining_quantity(item=item)
        quantity = _money(raw.get("quantity", remaining), "quantity")
        if quantity <= 0:
            raise CanonicalError(
                "INVALID_INPUT", "Quantity must be positive.", status_code=400
            )
        if quantity > remaining:
            raise CanonicalError(
                "EXCEEDS_PRESCRIBED_QUANTITY",
                "The dispensed quantity exceeds the remaining prescribed quantity.",
                status_code=409,
            )
        price = _price(organisation=organisation, facility=facility, product=chosen)
        proposals = fefo_selection(
            organisation=organisation,
            facility=facility,
            product_id=chosen.id,
            quantity=quantity,
        )
        for proposal in proposals:
            line_quantity = _money(proposal["quantity"])
            amount = (price.amount * line_quantity).quantize(Decimal("0.01"))
            DispenseLine.objects.create(
                organisation=organisation,
                facility=facility,
                dispense=dispense,
                prescription_item=item,
                product=chosen,
                batch_id=proposal["batch_id"],
                location_id=proposal["location_id"],
                quantity=line_quantity,
                unit_price=price.amount,
                amount=amount,
                substitution_reason=(
                    str(raw.get("substitution_reason") or "")[:240]
                    if substituted
                    else ""
                ),
                prescriber_consulted=bool(raw.get("prescriber_consulted", False)),
                prescriber_consulted_name=str(
                    raw.get("prescriber_consulted_name") or ""
                )[:120],
            )
            total += amount
    dispense.total = total
    dispense.version += 1
    dispense.save(update_fields=["total", "version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="Dispense",
        entity_id=dispense.id,
        after={"line_count": dispense.lines.count(), "total": str(total)},
        event_code="DISPENSE_PREPARED",
    )
    return dispense


@transaction.atomic
def confirm_dispense(*, organisation, facility, actor, dispense_id, request=None):
    """Hand over: stock movement, billing charge and dispense state atomically."""

    assert_transaction_active()
    dispense = (
        Dispense.objects.select_for_update(of=("self",))
        .filter(id=dispense_id, organisation=organisation, facility=facility)
        .select_related("prescription", "visit")
        .first()
    )
    if dispense is None:
        raise CanonicalError("NOT_FOUND", "Dispense was not found.", status_code=404)
    if dispense.status != "PROVISIONAL":
        raise CanonicalError(
            "INVALID_STATE", "This dispense cannot be confirmed.", status_code=409
        )
    if dispense.prescription is not None:
        _assigned_claim(prescription=dispense.prescription, actor=actor)
    invoice = None
    if dispense.visit_id:
        invoice = (
            Invoice.objects.filter(
                organisation=organisation, facility=facility, visit_id=dispense.visit_id
            )
            .exclude(status__in=("VOID", "VOIDED"))
            .order_by("created_at", "id")
            .first()
        )
        if invoice is None:
            raise CanonicalError(
                "PREREQUISITE_MISSING",
                "The Visit has no Invoice for dispensing charges.",
                status_code=422,
            )
    lines = list(
        dispense.lines.select_related(
            "product", "batch", "location", "prescription_item"
        ).order_by("id")
    )
    if not lines:
        raise CanonicalError(
            "INVALID_STATE", "A dispense must have at least one line.", status_code=409
        )
    for line in lines:
        if batch_is_expired(line.batch):
            raise CanonicalError(
                "EXPIRED_BATCH",
                "The selected batch has expired; reselect.",
                status_code=422,
            )
        append_movement(
            organisation=organisation,
            facility=facility,
            actor=actor,
            product=line.product,
            batch=line.batch,
            location=line.location,
            movement_type="OUT_DISPENSE",
            quantity=-line.quantity,
            source_type="DispenseLine",
            source_id=str(line.id),
        )
        if invoice is not None:
            issue_source_line(
                organisation=organisation,
                facility=facility,
                actor=actor,
                invoice=invoice,
                service=None,
                amount=line.amount,
                description=f"{line.product.generic_name} {line.product.strength}".strip(),
                source_type="DISPENSE_LINE",
                source_id=str(line.id),
                source_line_identity=str(line.id),
                request=request,
            )
        if line.prescription_item is not None:
            item = line.prescription_item
            item.state = (
                "DISPENSED"
                if _remaining_quantity(item=item) <= Decimal("0.00")
                else "PARTIALLY_DISPENSED"
            )
            item.version += 1
            item.save(update_fields=["state", "version", "updated_at"])
    dispense.status = "CONFIRMED"
    dispense.confirmed_by = actor
    dispense.confirmed_at = now()
    dispense.version += 1
    dispense.save(
        update_fields=[
            "status",
            "confirmed_by",
            "confirmed_at",
            "version",
            "updated_at",
        ]
    )
    if dispense.prescription is not None:
        prescription = dispense.prescription
        if all(
            item.state in {"DISPENSED", "CANCELLED", "NOT_DISPENSED"}
            for item in prescription.items.all()
        ):
            prescription.status = "COMPLETED"
            prescription.version += 1
            prescription.save(
                update_fields=["status", "version", "updated_at"]
            )
    if invoice is not None:
        recompute_invoice_projection(invoice)
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="Dispense",
        entity_id=dispense.id,
        after={"status": dispense.status, "line_count": len(lines)},
        event_code="DISPENSE_CONFIRMED",
    )
    return dispense


@transaction.atomic
def cancel_prescription(
    *, organisation, facility, actor, prescription_id, reason, request=None
):
    assert_transaction_active()
    if not str(reason or "").strip():
        raise CanonicalError(
            "INVALID_INPUT", "A cancellation reason is required.", status_code=400
        )
    prescription = (
        Prescription.objects.select_for_update()
        .filter(id=prescription_id, organisation=organisation, facility=facility)
        .first()
    )
    if prescription is None:
        raise CanonicalError("NOT_FOUND", "Prescription was not found.", status_code=404)
    if prescription.status != "ACTIVE":
        raise CanonicalError(
            "INVALID_STATE",
            "Only an active prescription can be cancelled.",
            status_code=409,
        )
    for item in prescription.items.all():
        if item.state not in {"DISPENSED", "PARTIALLY_DISPENSED"}:
            item.state = "CANCELLED"
            item.version += 1
            item.save(update_fields=["state", "version", "updated_at"])
    prescription.status = "CANCELLED"
    prescription.version += 1
    prescription.save(update_fields=["status", "version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="Prescription",
        entity_id=prescription.id,
        after={"status": "CANCELLED", "reason": str(reason)[:240]},
        event_code="PRESCRIPTION_CANCELLED",
    )
    return prescription


@transaction.atomic
def record_not_dispensed(
    *, organisation, facility, actor, prescription_item_id, reason, request=None
):
    assert_transaction_active()
    reasons = {
        "OUT_OF_STOCK",
        "PATIENT_DECLINED",
        "PATIENT_CANNOT_AFFORD",
        "PRESCRIBER_CANCELLED",
        "NOT_STOCKED",
        "OTHER",
    }
    if reason not in reasons:
        raise CanonicalError(
            "INVALID_INPUT", "Select a valid not-dispensed reason.", status_code=400
        )
    item = (
        PrescriptionItem.objects.select_for_update()
        .filter(
            id=prescription_item_id,
            organisation=organisation,
            facility=facility,
        )
        .first()
    )
    if item is None:
        raise CanonicalError(
            "NOT_FOUND", "Prescription item was not found.", status_code=404
        )
    if item.state not in {"PENDING", "PARTIALLY_DISPENSED"}:
        raise CanonicalError(
            "INVALID_STATE",
            "This item cannot be marked not dispensed.",
            status_code=409,
        )
    item.state = "NOT_DISPENSED"
    item.not_dispensed_reason = reason
    item.version += 1
    item.save(
        update_fields=["state", "not_dispensed_reason", "version", "updated_at"]
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="PrescriptionItem",
        entity_id=item.id,
        after={"reason": reason},
        event_code="PRESCRIPTION_ITEM_NOT_DISPENSED",
    )
    return item


@transaction.atomic
def create_otc_sale(
    *,
    organisation,
    facility,
    actor,
    lines,
    patient_id=None,
    customer_name="",
    method="CASH",
    reference="",
    request=None,
):
    """Sell OTC stock and record the money atomically; controlled always refused."""

    assert_transaction_active()
    if not lines:
        raise CanonicalError(
            "INVALID_INPUT", "Add at least one sale line.", status_code=400
        )
    patient = None
    if patient_id:
        patient = Patient.objects.filter(
            id=patient_id, organisation=organisation, status="ACTIVE"
        ).first()
        if patient is None:
            raise CanonicalError(
                "NOT_FOUND", "Patient was not found.", status_code=404
            )
    staged = []
    total = Decimal("0.00")
    for raw in lines:
        product = (
            MedicationProduct.objects.select_for_update()
            .filter(
                id=raw.get("product_id"),
                organisation=organisation,
                facility=facility,
            )
            .first()
        )
        if product is None:
            raise CanonicalError(
                "NOT_FOUND", "The product was not found.", status_code=404
            )
        if product.controlled:
            raise CanonicalError(
                "CONTROLLED_NOT_SUPPORTED",
                "Controlled medicines are not supported.",
                status_code=403,
            )
        if not product.active:
            raise CanonicalError(
                "INVALID_STATE", "This product is inactive.", status_code=409
            )
        if product.prescription_only:
            raise CanonicalError(
                "PRESCRIPTION_REQUIRED",
                "A prescription-only product requires a linked prescription.",
                status_code=403,
            )
        quantity = _money(raw.get("quantity"), "quantity")
        if quantity <= 0:
            raise CanonicalError(
                "INVALID_INPUT", "Quantity must be positive.", status_code=400
            )
        price = _price(organisation=organisation, facility=facility, product=product)
        proposals = fefo_selection(
            organisation=organisation,
            facility=facility,
            product_id=product.id,
            quantity=quantity,
        )
        for proposal in proposals:
            line_quantity = _money(proposal["quantity"])
            amount = (price.amount * line_quantity).quantize(Decimal("0.01"))
            staged.append(
                {
                    "product": product,
                    "batch_id": proposal["batch_id"],
                    "location_id": proposal["location_id"],
                    "quantity": line_quantity,
                    "unit_price": price.amount,
                    "amount": amount,
                }
            )
            total += amount
    sale = OTCSale.objects.create(
        organisation=organisation,
        facility=facility,
        patient=patient,
        customer_name=str(customer_name or "")[:160],
        total=total,
        currency=organisation.default_currency,
        method=str(method or "CASH")[:40],
        reference=str(reference or "")[:120],
        sold_by=actor,
        source_event_id=f"OTC:{facility.id}:{uuid4().hex}",
    )
    for staged_line in staged:
        line = OTCSaleLine.objects.create(
            organisation=organisation,
            facility=facility,
            sale=sale,
            **staged_line,
        )
        append_movement(
            organisation=organisation,
            facility=facility,
            actor=actor,
            product=line.product,
            batch=line.batch,
            location=line.location,
            movement_type="OUT_SALE",
            quantity=-line.quantity,
            source_type="OTCSaleLine",
            source_id=str(line.id),
        )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="OTCSale",
        entity_id=sale.id,
        after={"total": str(total), "method": sale.method},
        event_code="OTC_SALE_COMPLETED",
    )
    return sale


def counselling_projection(*, organisation, facility):
    """Confirmed dispenses that still need counselling evidence are surfaced."""

    assert_transaction_active()
    rows = []
    dispenses = (
        Dispense.objects.filter(
            organisation=organisation,
            facility=facility,
            status="CONFIRMED",
        )
        .select_related("patient", "prescription")
        .order_by("-confirmed_at")[:50]
    )
    for dispense in dispenses:
        rows.append(
            {
                "dispense_id": str(dispense.id),
                "patient_name": (
                    dispense.patient.display_name if dispense.patient else "Walk-in"
                ),
                "line_count": dispense.lines.count(),
                "confirmed_at": dispense.confirmed_at,
                "counselling_recorded": False,
            }
        )
    return rows
