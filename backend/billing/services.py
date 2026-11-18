import hashlib
import secrets
import string
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.db import models, transaction
from audit.services import record_event
from billing.models import (
    CashierShift,
    Invoice,
    InvoiceItem,
    Payment,
    PaymentAllocation,
    PaymentMethodConfig,
    PaymentReceipt,
    PriceList,
    ServiceCatalogItem,
    ServicePrice,
    VisitPayerBinding,
)
from clinical.models import Encounter
from core.clock import local_service_date, now
from core.errors import CanonicalError
from core.idempotency import canonical_json
from core.services import allocate_sequence, assert_transaction_active
from patients.models import Patient
from scheduling.models import QueueEntry, Visit


def _reference(prefix):
    alphabet = string.ascii_uppercase + string.digits
    return prefix + "-" + "".join(secrets.choice(alphabet) for _ in range(10))


def select_price_list(*, organisation, payer_type, price_list_id=None):
    """Lock and resolve the one applicable immutable PriceList."""

    assert_transaction_active()
    today = local_service_date()
    queryset = PriceList.objects.select_for_update().filter(
        organisation=organisation,
        active=True,
        payer_type=payer_type,
        effective_from__lte=today,
    ).filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=today))
    if price_list_id:
        queryset = queryset.filter(id=price_list_id)
    return queryset.order_by("-version", "-effective_from", "id").first()


def select_consultation_price(*, organisation, facility, payer_type, price_list_id=None, service_code="CONSULTATION"):
    """Resolve the supplied price source without creating a financial record.

    A missing PriceList is intentionally distinct from an unpriced service. There
    is no legacy NULL-price-list branch: target commands must fail closed.
    """

    assert_transaction_active()
    today = local_service_date()
    price_list = select_price_list(
        organisation=organisation,
        payer_type=payer_type,
        price_list_id=price_list_id,
    )
    if price_list is None:
        return None, None, None
    service = ServiceCatalogItem.objects.select_for_update().filter(
        organisation=organisation,
        code=service_code,
        is_active=True,
    ).first()
    if service is None:
        return price_list, None, None

    prices = ServicePrice.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        service=service,
        is_active=True,
        active=True,
        effective_from__lte=today,
    ).filter(models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=today))
    prices = prices.filter(price_list=price_list)
    price = prices.order_by("-effective_from", "-created_at", "id").first()
    return price_list, service, price


def create_payer_binding(*, organisation, facility, visit, actor, payer_type, price_list=None):
    """Append the initial immutable payer binding for a Visit."""

    assert_transaction_active()
    if price_list is None:
        raise ValueError("A PriceList is required for every Visit payer binding.")
    if (
        visit.organisation_id != getattr(organisation, "id", organisation)
        or visit.facility_id != getattr(facility, "id", facility)
        or price_list.organisation_id != getattr(organisation, "id", organisation)
        or price_list.payer_type != payer_type
        or not price_list.active
        or price_list.effective_from > local_service_date()
        or (price_list.effective_to is not None and price_list.effective_to < local_service_date())
    ):
        raise ValueError("The payer binding references a different tenant or facility.")
    current = VisitPayerBinding.objects.select_for_update().filter(visit=visit, active=True).first()
    if current is not None:
        if current.payer_type == payer_type and current.price_list_id == getattr(price_list, "id", price_list):
            return current, False
        raise ValueError("The Visit already has an active payer binding.")
    last_version = VisitPayerBinding.objects.filter(visit=visit).order_by("-binding_version").first()
    binding = VisitPayerBinding.objects.create(
        organisation=organisation,
        facility=facility,
        visit=visit,
        price_list=price_list,
        payer_type=payer_type,
        binding_version=(last_version.binding_version + 1) if last_version else 1,
        bound_by=actor,
        source_event_id=f"VISIT:{visit.id}:PAYER",
    )
    return binding, True


def issue_exact_source_lines(*, organisation, facility, actor, visit, service, price, request=None):
    """Issue the one source-versioned consultation line for a Visit."""

    assert_transaction_active()
    if service is None or price is None or price.price_list_id is None:
        raise ValueError("A priced service from an applicable PriceList is required.")
    if service.organisation_id != organisation.id or price.organisation_id != organisation.id:
        raise ValueError("The service price is outside the request organisation.")
    if price.facility_id != facility.id or price.service_id != service.id:
        raise ValueError("The service price is outside the request facility.")
    binding = VisitPayerBinding.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        visit=visit,
        active=True,
    ).first()
    if binding is None or binding.price_list_id != price.price_list_id:
        raise ValueError("The consultation price does not match the Visit payer binding.")
    existing = Invoice.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        visit=visit,
    ).exclude(status__in=["VOID", "VOIDED"]).first()
    source_line_identity = "CONSULTATION"
    if existing is not None:
        line = InvoiceItem.objects.filter(
            organisation=organisation,
            invoice=existing,
            source_type="CONSULTATION",
            source_id=visit.id,
            source_line_identity=source_line_identity,
            state="ACTIVE",
        ).first()
        if line is not None:
            return existing, False
        invoice = existing
    else:
        period = local_service_date().isoformat()
        sequence = allocate_sequence(
            organisation=organisation,
            facility=facility,
            sequence_type="INVOICE",
            period_key=period,
        )
        invoice = Invoice.objects.create(
            organisation=organisation,
            facility=facility,
            invoice_no=f"INV-{period.replace('-', '')}-{sequence:06d}",
            patient=visit.patient,
            visit=visit,
            status="DRAFT",
            currency=price.currency,
            created_by=actor,
        )
    amount = price.amount.quantize(Decimal("0.01"))
    InvoiceItem.objects.create(
        organisation=organisation,
        invoice=invoice,
        facility=facility,
        service=service,
        description=service.name,
        quantity=Decimal("1.00"),
        unit_price=price.amount,
        amount=amount,
        line_set_version=invoice.current_line_set_version,
        source_type="CONSULTATION",
        source_id=visit.id,
        source_version=price.source_version,
        source_line_identity=source_line_identity,
        created_by=actor,
    )
    invoice.issued_at = invoice.issued_at or now()
    invoice.save(update_fields=["issued_at", "updated_at"])
    invoice = recompute_invoice_projection(invoice)
    return invoice, True


def void_unpaid_visit_invoice(*, organisation, facility, actor, invoice, reason_hash):
    """Void only an unpaid Visit invoice, retaining its lines and auditability."""

    assert_transaction_active()
    invoice = Invoice.objects.select_for_update().filter(
        id=invoice.id,
        organisation=organisation,
        facility=facility,
    ).first()
    if invoice is None:
        raise ValueError("Invoice was not found in this facility.")
    if invoice.status == "VOIDED":
        return invoice, False
    if invoice.status in {"PAID", "PARTIALLY_PAID"} or invoice.amount_paid > 0:
        raise ValueError("A payment exists for this invoice.")
    if PaymentAllocation.objects.filter(invoice=invoice).exists() or Payment.objects.filter(
        invoice=invoice,
        status__in=Payment.EFFECTIVE_STATUSES,
    ).exists():
        raise ValueError("A payment exists for this invoice.")
    if invoice.status not in {"DRAFT", "ISSUED", "VOID"}:
        raise ValueError("The invoice cannot be voided in its current state.")

    InvoiceItem.objects.select_for_update().filter(
        invoice=invoice,
        state="ACTIVE",
    ).update(state="VOIDED", void_reason=reason_hash)
    invoice.status = "VOIDED"
    invoice.voided_at = now()
    invoice.voided_by = actor
    invoice.version += 1
    invoice.save(update_fields=["status", "voided_at", "voided_by", "version", "updated_at"])
    return invoice, True


def require_visit_invoice(*, organisation, encounter):
    """Refuse generic invoice creation when the Encounter already has a Visit.

    A Visit-linked Encounter is billed through the single Invoice that check-in
    (or the authorised financial setup path) already owns. The generic create
    path writes an Invoice without a Visit link, so the Visit's unique-invoice
    constraint cannot catch the duplicate; it must refuse instead. The refusal
    is based on the stored Visit link only. A Visit whose Invoice is missing is
    still owned by that Visit path and is not repairable here.

    Legacy Encounters can predate the Visit link while still naming their queue
    entry. That fallback only trusts a queue entry that agrees with the scoped
    Encounter on organisation, facility, and patient, the same scope test the
    S-01 migration applies. An explicit link that cannot be resolved in scope
    fails closed rather than falling through to a duplicate charge.
    """

    linked_visit_id = encounter.visit_id
    if linked_visit_id is None and encounter.queue_entry_id is not None:
        queue_visit = QueueEntry.objects.filter(
            id=encounter.queue_entry_id,
            organisation=organisation,
            facility_id=encounter.facility_id,
            patient_id=encounter.patient_id,
        ).values("visit_id").first()
        if queue_visit is None:
            raise CanonicalError(
                "VISIT_INVOICE_REQUIRED",
                "Use the invoice for this Visit.",
                status_code=409,
            )
        linked_visit_id = queue_visit["visit_id"]
    if linked_visit_id is not None:
        raise CanonicalError(
            "VISIT_INVOICE_REQUIRED",
            "Use the invoice for this Visit.",
            status_code=409,
        )


@transaction.atomic
def create_invoice(*, organisation, facility, actor, patient_id, encounter_id=None, items=None, discount=Decimal("0.00"), request=None):
    patient = Patient.objects.filter(id=patient_id, organisation=organisation, status="ACTIVE").first()
    if patient is None:
        raise ValueError("Patient was not found in this organisation.")
    encounter = None
    if encounter_id:
        encounter = Encounter.objects.filter(
            id=encounter_id, organisation=organisation, facility=facility, patient=patient
        ).first()
        if encounter is None:
            raise ValueError("Encounter was not found in this facility.")
        if encounter.status not in {"SIGNED", "CLOSED"}:
            raise ValueError("The consultation must be signed before billing.")
        require_visit_invoice(organisation=organisation, encounter=encounter)
    if not items:
        raise ValueError("At least one service item is required.")
    today = local_service_date()
    price_list = select_price_list(
        organisation=organisation,
        payer_type="CASH",
    )
    if price_list is None:
        raise CanonicalError(
            "NO_PRICE_LIST",
            "No active price list is available for this payer.",
            status_code=422,
        )
    invoice = Invoice.objects.create(
        organisation=organisation,
        facility=facility,
        invoice_no=_reference("INV"),
        patient=patient,
        encounter=encounter,
        status="DRAFT",
        currency=organisation.default_currency,
        discount=Decimal(str(discount)),
        created_by=actor,
    )
    subtotal = Decimal("0.00")
    for item in items:
        service = ServiceCatalogItem.objects.filter(
            id=item.get("service_id"), organisation=organisation, is_active=True
        ).first()
        if service is None:
            raise CanonicalError(
                "SERVICE_NOT_PRICED",
                "The selected service is not available in the active catalogue.",
                status_code=422,
                metadata={"service_id": str(item.get("service_id"))},
            )
        price = ServicePrice.objects.select_for_update().filter(
            organisation=organisation,
            facility=facility,
            service=service,
            price_list=price_list,
            is_active=True,
            active=True,
            effective_from__lte=today,
        ).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=today)
        ).filter(
            models.Q(price_list__effective_to__isnull=True) | models.Q(price_list__effective_to__gte=today)
        ).order_by("-price_list__version", "-effective_from").first()
        if price is None:
            raise CanonicalError(
                "SERVICE_NOT_PRICED",
                "The selected service is not priced for this facility and payer.",
                status_code=422,
                metadata={"service_id": str(service.id), "service_code": service.code},
            )
        quantity = Decimal(str(item.get("quantity", "1")))
        if quantity <= 0:
            raise ValueError("Service quantity must be positive.")
        amount = (price.amount * quantity).quantize(Decimal("0.01"))
        InvoiceItem.objects.create(
            organisation=organisation,
            invoice=invoice,
            facility=facility,
            service=service,
            description=service.name,
            quantity=quantity,
            unit_price=price.amount,
            amount=amount,
        )
        subtotal += amount
    invoice.issued_at = now()
    invoice.save(update_fields=["issued_at", "updated_at"])
    invoice = recompute_invoice_projection(invoice)
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="Invoice",
        entity_id=invoice.id,
        after={"invoice_no": invoice.invoice_no, "total": str(invoice.total), "status": invoice.status},
    )
    return invoice


def _money(value):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CanonicalError(
            "PAYMENT_AMOUNT_INVALID",
            "Enter a valid money amount with at most two decimal places.",
            status_code=400,
        ) from exc
    if amount != Decimal(str(value)):
        raise CanonicalError(
            "PAYMENT_AMOUNT_INVALID",
            "Money amounts must use at most two decimal places.",
            status_code=400,
        )
    return amount


def effective_allocation_total(*, invoice):
    total = PaymentAllocation.objects.filter(
        organisation_id=invoice.organisation_id,
        invoice=invoice,
        payment__status__in=Payment.EFFECTIVE_STATUSES,
    ).aggregate(total=models.Sum("amount"))["total"]
    return (total or Decimal("0.00")).quantize(Decimal("0.01"))


def recompute_invoice_projection(invoice):
    """Recompute the invoice from its current line set and effective allocations.

    The gross total is always the sum of non-voided lines; ``discount`` is
    retained separately. ``amount_paid`` and ``balance`` remain compatibility
    projections for existing readers and are never independent facts.
    """

    assert_transaction_active()
    invoice = Invoice.objects.select_for_update().filter(id=invoice.id).first()
    if invoice is None:
        raise CanonicalError("INVOICE_NOT_FOUND", "Invoice was not found.", status_code=404)
    if invoice.status in {"VOID", "VOIDED"}:
        return invoice
    subtotal = sum(
        (
            line.amount
            for line in invoice.items.filter(state="ACTIVE")
        ),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    discount = min(invoice.discount, subtotal).quantize(Decimal("0.01"))
    total = (subtotal - discount).quantize(Decimal("0.01"))
    applied = effective_allocation_total(invoice=invoice)
    if applied > total:
        raise CanonicalError(
            "INVOICE_OVERPAID",
            "The effective allocations exceed the invoice total.",
            status_code=409,
        )
    balance = (total - applied).quantize(Decimal("0.01"))
    if total > 0 and balance == 0:
        status = "PAID"
    elif applied > 0:
        status = "PARTIALLY_PAID"
    else:
        status = "ISSUED" if invoice.issued_at else "DRAFT"
    invoice.subtotal = subtotal
    invoice.discount = discount
    invoice.total = total
    invoice.amount_paid = applied
    invoice.balance = balance
    invoice.status = status
    invoice.version += 1
    invoice.save(
        update_fields=[
            "subtotal",
            "discount",
            "total",
            "amount_paid",
            "balance",
            "status",
            "version",
            "updated_at",
        ]
    )
    return invoice


def resolve_payment_method(*, organisation, facility, method, reference):
    """Resolve one supplied method without claiming provider verification."""

    code = (method or "").strip().upper()
    if code == "MOBILE_MONEY":
        code = "MOBILE_MONEY_MANUAL"
    if code == "CASH":
        return code, None
    if code == "MOBILE_MONEY_MANUAL":
        if not (reference or "").strip():
            raise CanonicalError(
                "PAYMENT_REFERENCE_REQUIRED",
                "A transaction reference is required for a manual mobile-money payment.",
                status_code=400,
            )
        return code, None
    config = PaymentMethodConfig.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        code=code,
        is_active=True,
    ).first()
    if config is None:
        raise CanonicalError(
            "PAYMENT_METHOD_NOT_CONFIGURED",
            "The selected payment method is not enabled for this facility.",
            status_code=422,
        )
    if config.reference_required and not (reference or "").strip():
        raise CanonicalError(
            "PAYMENT_REFERENCE_REQUIRED",
            "This payment method requires a reference.",
            status_code=400,
        )
    return code, config


def payment_method_options(*, organisation, facility):
    options = [
        {
            "code": "CASH",
            "label": "Cash",
            "kind": "CASH",
            "reference_required": False,
            "provider_label": "",
            "is_active": True,
            "configured": False,
        },
        {
            "code": "MOBILE_MONEY_MANUAL",
            "label": "Mobile money (manual reference)",
            "kind": "MOBILE_MONEY_MANUAL",
            "reference_required": True,
            "provider_label": "",
            "is_active": True,
            "configured": False,
        },
    ]
    for config in PaymentMethodConfig.objects.filter(
        organisation=organisation, facility=facility
    ).order_by("code"):
        options.append(
            {
                "code": config.code,
                "label": config.label,
                "kind": config.kind,
                "reference_required": config.reference_required,
                "provider_label": config.provider_label,
                "is_active": config.is_active,
                "configured": True,
            }
        )
    return options


def configure_payment_method(
    *, organisation, facility, actor, code, label, kind, reference_required=False,
    provider_label="", is_active=True, request=None,
):
    """Create or deactivate a facility-defined manual payment method."""

    assert_transaction_active()
    code = (code or "").strip().upper()
    if kind not in {choice[0] for choice in PaymentMethodConfig.KIND_CHOICES}:
        raise CanonicalError("PAYMENT_METHOD_KIND_INVALID", "Select a manual payment method kind.", status_code=400)
    if code in {"CASH", "MOBILE_MONEY_MANUAL", "MOBILE_MONEY"}:
        raise CanonicalError(
            "PAYMENT_METHOD_RESERVED",
            "Cash and manual mobile money are supplied methods and cannot be redefined.",
            status_code=409,
        )
    if not label.strip():
        raise CanonicalError("PAYMENT_METHOD_LABEL_REQUIRED", "A method label is required.", status_code=400)
    config = PaymentMethodConfig.objects.select_for_update().filter(
        organisation=organisation, facility=facility, code=code
    ).first()
    active_manual = PaymentMethodConfig.objects.filter(
        organisation=organisation, facility=facility, is_active=True
    )
    if is_active and (config is None or not config.is_active):
        if active_manual.count() >= 3:
            raise CanonicalError(
                "PAYMENT_METHOD_LIMIT",
                "A facility can enable at most three manual payment methods.",
                status_code=422,
            )
    if config is None:
        config = PaymentMethodConfig.objects.create(
            organisation=organisation,
            facility=facility,
            code=code,
            label=label.strip(),
            kind=kind,
            reference_required=reference_required,
            provider_label=provider_label.strip(),
            is_active=is_active,
        )
    else:
        config.label = label.strip()
        config.kind = kind
        config.reference_required = reference_required
        config.provider_label = provider_label.strip()
        config.is_active = is_active
        config.version += 1
        config.save(
            update_fields=[
                "label",
                "kind",
                "reference_required",
                "provider_label",
                "is_active",
                "version",
                "updated_at",
            ]
        )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CONFIGURE",
        entity_type="PaymentMethodConfig",
        entity_id=config.id,
        after={"code": config.code, "is_active": config.is_active},
        event_code="PAYMENT_METHOD_CONFIGURED",
    )
    return config


def open_shift(*, organisation, facility, actor, opening_float=Decimal("0.00"), request=None):
    assert_transaction_active()
    opening_float = _money(opening_float)
    if opening_float < 0:
        raise CanonicalError("SHIFT_FLOAT_INVALID", "The opening float cannot be negative.", status_code=400)
    existing = CashierShift.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        cashier=actor,
        status="OPEN",
    ).first()
    if existing is not None:
        raise CanonicalError(
            "SHIFT_ALREADY_OPEN",
            "This cashier already has an open shift.",
            status_code=409,
        )
    shift = CashierShift.objects.create(
        organisation=organisation,
        facility=facility,
        cashier=actor,
        opening_float=opening_float,
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="OPEN",
        entity_type="CashierShift",
        entity_id=shift.id,
        after={"shift_id": str(shift.id)},
        event_code="SHIFT_OPENED",
    )
    return shift


def current_shift(*, organisation, facility, actor):
    return CashierShift.objects.filter(
        organisation=organisation,
        facility=facility,
        cashier=actor,
        status="OPEN",
    ).first()


def _confirmed_cash_total(*, organisation, facility, shift, statuses):
    total = Payment.objects.filter(
        organisation=organisation,
        facility=facility,
        shift=shift,
        method="CASH",
        status__in=statuses,
    ).aggregate(total=models.Sum("amount"))["total"]
    return (total or Decimal("0.00")).quantize(Decimal("0.01"))


def close_shift(
    *, organisation, facility, actor, shift_id, declared_cash, request=None
):
    """Blind close: the declaration is captured before the expected cash is read."""

    assert_transaction_active()
    shift = CashierShift.objects.select_for_update().filter(
        id=shift_id,
        organisation=organisation,
        facility=facility,
    ).first()
    if shift is None:
        raise CanonicalError("SHIFT_NOT_FOUND", "Cashier shift was not found.", status_code=404)
    if shift.status == "CLOSED":
        raise CanonicalError("SHIFT_ALREADY_CLOSED", "This cashier shift is already closed.", status_code=409)
    if shift.cashier_id != getattr(actor, "id", actor):
        raise CanonicalError(
            "SHIFT_NOT_OWNED",
            "Only the cashier who opened the shift can close it.",
            status_code=403,
        )
    declared = _money(declared_cash)
    if declared < 0:
        raise CanonicalError("SHIFT_DECLARATION_INVALID", "The declared cash cannot be negative.", status_code=400)
    confirmed = _confirmed_cash_total(
        organisation=organisation,
        facility=facility,
        shift=shift,
        statuses=Payment.EFFECTIVE_STATUSES,
    )
    reversed_total = _confirmed_cash_total(
        organisation=organisation,
        facility=facility,
        shift=shift,
        statuses=("REVERSED",),
    )
    expected = (shift.opening_float + confirmed - reversed_total).quantize(Decimal("0.01"))
    shift.declared_cash = declared
    shift.expected_cash = expected
    shift.variance = (declared - expected).quantize(Decimal("0.01"))
    shift.status = "CLOSED"
    shift.closed_at = now()
    shift.closed_by = actor
    shift.version += 1
    shift.save(
        update_fields=[
            "declared_cash",
            "expected_cash",
            "variance",
            "status",
            "closed_at",
            "closed_by",
            "version",
            "updated_at",
        ]
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CLOSE",
        entity_type="CashierShift",
        entity_id=shift.id,
        after={"shift_id": str(shift.id), "variance": str(shift.variance)},
        event_code="SHIFT_CLOSED",
    )
    return shift


def _receipt_hash(*, payment, allocations):
    envelope = {
        "payment_id": str(payment.id),
        "receipt_no": payment.receipt_no,
        "amount": str(payment.amount),
        "method": payment.method,
        "received_at": payment.received_at.isoformat(),
        "allocations": [
            {"invoice_id": str(allocation.invoice_id), "amount": str(allocation.amount)}
            for allocation in allocations
        ],
    }
    return hashlib.sha256(canonical_json(envelope).encode("utf-8")).hexdigest()


def receipt_payload(receipt):
    payment = receipt.payment
    allocations = list(
        payment.allocations.select_related("invoice", "invoice__patient").order_by("invoice_id")
    )
    invoice = allocations[0].invoice if allocations else payment.invoice
    if invoice is None:
        raise CanonicalError("RECEIPT_NOT_FOUND", "The receipt has no invoice evidence.", status_code=409)
    return {
        "id": str(receipt.id),
        "receipt_no": receipt.receipt_no,
        "payment_id": str(payment.id),
        "invoice_id": str(invoice.id),
        "invoice_no": invoice.invoice_no,
        "patient_name": invoice.patient.display_name,
        "patient_no": invoice.patient.patient_no,
        "amount": str(payment.amount),
        "currency": invoice.currency,
        "method": payment.method,
        "reference": payment.reference,
        "received_at": payment.received_at,
        "status": payment.status,
        "invoice_total": str(invoice.total),
        "invoice_balance": str(invoice.balance),
        "allocations": [
            {
                "invoice_id": str(allocation.invoice_id),
                "invoice_no": allocation.invoice.invoice_no,
                "amount": str(allocation.amount),
            }
            for allocation in allocations
        ],
        "print_count": receipt.print_count,
        "last_printed_at": receipt.last_printed_at,
        "content_hash": receipt.content_hash,
        "printable_text": (
            f"{receipt.organisation.name} | Receipt {payment.receipt_no} | "
            f"{invoice.patient.display_name} | {invoice.currency} {payment.amount}"
        ),
    }


def receipt_by_identity(*, organisation, facility, receipt_id=None, receipt_no=None):
    queryset = PaymentReceipt.objects.select_related(
        "payment", "payment__invoice", "organisation"
    ).filter(organisation=organisation, facility=facility)
    if receipt_id is not None:
        queryset = queryset.filter(id=receipt_id)
    elif receipt_no:
        queryset = queryset.filter(receipt_no=receipt_no)
    else:
        raise CanonicalError("RECEIPT_IDENTITY_REQUIRED", "A receipt reference is required.", status_code=400)
    receipt = queryset.first()
    if receipt is None:
        raise CanonicalError("RECEIPT_NOT_FOUND", "Receipt was not found.", status_code=404)
    return receipt


def reprint_receipt(*, organisation, facility, actor, receipt_id, request=None):
    assert_transaction_active()
    receipt = PaymentReceipt.objects.select_for_update().filter(
        id=receipt_id,
        organisation=organisation,
        facility=facility,
    ).first()
    if receipt is None:
        raise CanonicalError("RECEIPT_NOT_FOUND", "Receipt was not found.", status_code=404)
    if receipt.payment.status not in Payment.EFFECTIVE_STATUSES:
        raise CanonicalError(
            "RECEIPT_NOT_PRINTABLE",
            "A reversed payment receipt cannot be reprinted as a current receipt.",
            status_code=409,
        )
    receipt.print_count += 1
    receipt.last_printed_at = now()
    receipt.save(update_fields=["print_count", "last_printed_at", "updated_at"])
    receipt.payment.receipt_printed_at = receipt.last_printed_at
    receipt.payment.save(update_fields=["receipt_printed_at", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="PRINT",
        entity_type="PaymentReceipt",
        entity_id=receipt.id,
        after={"receipt_no": receipt.receipt_no, "print_count": receipt.print_count},
        event_code="RECEIPT_REPRINTED",
    )
    return receipt


@dataclass(frozen=True)
class PaymentOutcome:
    payment: Payment
    receipt: PaymentReceipt
    invoices: list = field(default_factory=list)


@transaction.atomic
def confirm_payment(
    *,
    organisation,
    facility,
    actor,
    amount,
    method,
    reference="",
    invoice_id=None,
    allocations=None,
    require_shift=False,
    request=None,
):
    """CMD-075/CMD-080: one confirmed payment, exact allocations and receipt."""

    assert_transaction_active()
    amount = _money(amount)
    if amount <= 0:
        raise CanonicalError("PAYMENT_AMOUNT_INVALID", "The payment amount must be positive.", status_code=400)
    shift = None
    if require_shift:
        shift = CashierShift.objects.select_for_update().filter(
            organisation=organisation,
            facility=facility,
            cashier=actor,
            status="OPEN",
        ).first()
        if shift is None:
            raise CanonicalError(
                "OPEN_SHIFT_REQUIRED",
                "Open a cashier shift before recording a payment.",
                status_code=409,
            )
    method, _config = resolve_payment_method(
        organisation=organisation,
        facility=facility,
        method=method,
        reference=reference,
    )
    if allocations is None:
        if invoice_id is None:
            raise CanonicalError("PAYMENT_ALLOCATION_REQUIRED", "An invoice is required.", status_code=400)
        allocations = [{"invoice_id": invoice_id, "amount": amount}]
    if not allocations:
        raise CanonicalError("PAYMENT_ALLOCATION_REQUIRED", "At least one allocation is required.", status_code=400)

    specs = {}
    for allocation in allocations:
        allocation_invoice_id = str(allocation.get("invoice_id") or "")
        allocation_amount = _money(allocation.get("amount"))
        if not allocation_invoice_id or allocation_amount <= 0:
            raise CanonicalError(
                "PAYMENT_ALLOCATION_INVALID",
                "Every allocation needs a positive amount and an invoice.",
                status_code=400,
            )
        if allocation_invoice_id in specs:
            raise CanonicalError(
                "PAYMENT_ALLOCATION_DUPLICATE",
                "An invoice can appear only once in one payment.",
                status_code=400,
            )
        specs[allocation_invoice_id] = allocation_amount
    if sum(specs.values(), Decimal("0.00")) != amount:
        raise CanonicalError(
            "PAYMENT_ALLOCATION_MISMATCH",
            "The allocations must sum exactly to the tender amount.",
            status_code=400,
        )

    invoices = list(
        Invoice.objects.select_for_update()
        .filter(
            id__in=list(specs),
            organisation=organisation,
            facility=facility,
        )
        .select_related("patient")
        .order_by("id")
    )
    if len(invoices) != len(specs):
        raise CanonicalError("INVOICE_NOT_FOUND", "An allocated invoice was not found.", status_code=404)
    patient_ids = {invoice.patient_id for invoice in invoices}
    if len(patient_ids) != 1:
        raise CanonicalError(
            "PAYMENT_ALLOCATION_PATIENT_MISMATCH",
            "All allocations must belong to the same patient.",
            status_code=409,
        )
    currencies = {invoice.currency for invoice in invoices}
    if len(currencies) != 1:
        raise CanonicalError(
            "PAYMENT_CURRENCY_MISMATCH",
            "All allocations must use one currency.",
            status_code=409,
        )
    for invoice in invoices:
        if invoice.status in {"VOID", "VOIDED"}:
            raise CanonicalError(
                "INVOICE_NOT_PAYABLE",
                "A voided invoice cannot accept a payment.",
                status_code=400,
            )
        if invoice.status == "PAID":
            raise CanonicalError(
                "INVOICE_NOT_PAYABLE",
                "This invoice cannot accept a payment.",
                status_code=400,
            )
        allocation_amount = specs[str(invoice.id)]
        if allocation_amount > invoice.balance:
            raise CanonicalError(
                "PAYMENT_EXCEEDS_BALANCE",
                "An allocation is greater than the invoice balance.",
                status_code=409,
            )

    primary_invoice = invoices[0] if len(invoices) == 1 else None
    period = local_service_date().isoformat()
    sequence = allocate_sequence(
        organisation=organisation,
        facility=facility,
        sequence_type="RECEIPT",
        period_key=period,
    )
    payment = Payment.objects.create(
        organisation=organisation,
        facility=facility,
        invoice=primary_invoice,
        receipt_no=f"RCT-{period.replace('-', '')}-{sequence:06d}",
        amount=amount,
        method=method,
        reference=(reference or "").strip(),
        status="CONFIRMED",
        received_by=actor,
        shift=shift,
    )
    allocation_rows = [
        PaymentAllocation.objects.create(
            organisation=organisation,
            facility=facility,
            payment=payment,
            invoice=invoice,
            amount=specs[str(invoice.id)],
        )
        for invoice in invoices
    ]
    for invoice in invoices:
        recompute_invoice_projection(invoice)
    receipt = PaymentReceipt.objects.create(
        organisation=organisation,
        facility=facility,
        payment=payment,
        receipt_no=payment.receipt_no,
        content_hash=_receipt_hash(payment=payment, allocations=allocation_rows),
        issued_by=actor,
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="PAYMENT",
        entity_type="Payment",
        entity_id=payment.id,
        after={
            "invoice_id": str(primary_invoice.id) if primary_invoice else "",
            "receipt_no": payment.receipt_no,
            "method": method,
            "allocations": [
                {"invoice_id": str(row.invoice_id), "amount": str(row.amount)}
                for row in allocation_rows
            ],
        },
        event_code="PAYMENT",
        source_ids={"payment_id": str(payment.id), "receipt_id": str(receipt.id)},
    )
    return PaymentOutcome(
        payment=payment,
        receipt=receipt,
        invoices=[Invoice.objects.get(id=invoice.id) for invoice in invoices],
    )


@transaction.atomic
def post_payment(*, organisation, facility, actor, invoice_id, amount, method, reference="", request=None):
    """Compatibility wrapper for the existing single-invoice route."""

    outcome = confirm_payment(
        organisation=organisation,
        facility=facility,
        actor=actor,
        amount=amount,
        method=method,
        reference=reference,
        invoice_id=invoice_id,
        require_shift=False,
        request=request,
    )
    return outcome.payment


@transaction.atomic
def reverse_payment(*, organisation, facility, actor, payment_id, reason, request=None):
    """CMD-076: reverse a whole payment and recompute every affected invoice."""

    assert_transaction_active()
    if not (reason or "").strip():
        raise CanonicalError(
            "PAYMENT_REVERSAL_REASON_REQUIRED",
            "A reason is required to reverse a payment.",
            status_code=400,
        )
    payment = Payment.objects.select_for_update().filter(
        id=payment_id,
        organisation=organisation,
        facility=facility,
    ).first()
    if payment is None:
        raise CanonicalError("PAYMENT_NOT_FOUND", "Payment was not found.", status_code=404)
    if payment.status == "REVERSED":
        raise CanonicalError("PAYMENT_ALREADY_REVERSED", "This payment is already reversed.", status_code=409)
    if payment.status not in Payment.EFFECTIVE_STATUSES:
        raise CanonicalError("PAYMENT_NOT_REVERSIBLE", "This payment cannot be reversed.", status_code=409)
    allocations = list(payment.allocations.order_by("invoice_id"))
    if not allocations:
        raise CanonicalError("PAYMENT_NOT_REVERSIBLE", "The payment has no effective allocation.", status_code=409)
    invoices = list(
        Invoice.objects.select_for_update()
        .filter(id__in=[allocation.invoice_id for allocation in allocations])
        .order_by("id")
    )
    reason_hash = hashlib.sha256(reason.strip().encode("utf-8")).hexdigest()
    payment.status = "REVERSED"
    payment.reversed_at = now()
    payment.reversed_by = actor
    payment.reversal_reason_hash = reason_hash
    payment.save(
        update_fields=[
            "status",
            "reversed_at",
            "reversed_by",
            "reversal_reason_hash",
            "updated_at",
        ]
    )
    invoices = [recompute_invoice_projection(invoice) for invoice in invoices]
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="REVERSE",
        entity_type="Payment",
        entity_id=payment.id,
        after={
            "receipt_no": payment.receipt_no,
            "invoices": [str(invoice.id) for invoice in invoices],
            "reason_hash": reason_hash,
        },
        event_code="PAYMENT_REVERSED",
        source_ids={"payment_id": str(payment.id)},
    )
    return payment, invoices


def add_invoice_line(
    *, organisation, facility, actor, invoice_id, service_id=None, description="",
    quantity="1", amount=None, reason="", manual=False, request=None,
):
    """CMD-073/074: add an authoritative catalogue or manual line."""

    assert_transaction_active()
    invoice = Invoice.objects.select_for_update().filter(
        id=invoice_id, organisation=organisation, facility=facility
    ).first()
    if invoice is None:
        raise CanonicalError("INVOICE_NOT_FOUND", "Invoice was not found.", status_code=404)
    if invoice.status in {"VOID", "VOIDED"}:
        raise CanonicalError("INVOICE_NOT_EDITABLE", "A voided invoice cannot accept a line.", status_code=409)
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise CanonicalError("INVOICE_LINE_QUANTITY_INVALID", "Quantity must be positive.", status_code=400)
    before = {"total": str(invoice.total), "balance": str(invoice.balance)}
    if manual:
        if not description.strip() or not reason.strip():
            raise CanonicalError(
                "MANUAL_LINE_EVIDENCE_REQUIRED",
                "A manual line requires a description and a reason.",
                status_code=400,
            )
        unit_price = _money(amount)
        if unit_price <= 0:
            raise CanonicalError("MANUAL_LINE_AMOUNT_INVALID", "Enter a positive manual amount.", status_code=400)
        line_amount = (unit_price * quantity).quantize(Decimal("0.01"))
        line = InvoiceItem.objects.create(
            organisation=organisation,
            invoice=invoice,
            facility=facility,
            description=description.strip(),
            quantity=quantity,
            unit_price=unit_price,
            amount=line_amount,
            line_set_version=invoice.current_line_set_version,
            source_type="MANUAL",
            source_version="v1",
            source_line_identity=f"MANUAL:{uuid4()}",
            manual_reason=reason.strip(),
            created_by=actor,
        )
    else:
        service = ServiceCatalogItem.objects.filter(
            id=service_id, organisation=organisation, is_active=True
        ).first()
        if service is None:
            raise CanonicalError("SERVICE_NOT_PRICED", "The selected service is unavailable.", status_code=422)
        price_list = select_price_list(organisation=organisation, payer_type="CASH")
        if price_list is None:
            raise CanonicalError("NO_PRICE_LIST", "No active price list is available.", status_code=422)
        today = local_service_date()
        price = ServicePrice.objects.select_for_update().filter(
            organisation=organisation,
            facility=facility,
            service=service,
            price_list=price_list,
            is_active=True,
            active=True,
            effective_from__lte=today,
        ).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=today)
        ).order_by("-effective_from").first()
        if price is None:
            raise CanonicalError("SERVICE_NOT_PRICED", "The selected service is not priced.", status_code=422)
        line = InvoiceItem.objects.create(
            organisation=organisation,
            invoice=invoice,
            facility=facility,
            service=service,
            description=service.name,
            quantity=quantity,
            unit_price=price.amount,
            amount=(price.amount * quantity).quantize(Decimal("0.01")),
            line_set_version=invoice.current_line_set_version,
            source_type="MANUAL_SERVICE",
            source_version=price.source_version,
            source_line_identity=f"CATALOGUE:{uuid4()}",
            created_by=actor,
        )
    invoice = recompute_invoice_projection(invoice)
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="InvoiceItem",
        entity_id=line.id,
        before=before,
        after={"total": str(invoice.total), "balance": str(invoice.balance), "manual": manual},
        event_code="INVOICE_LINE_ADDED",
    )
    return line, invoice


def void_invoice_line(
    *, organisation, facility, actor, invoice_id, line_id, reason, request=None
):
    """CMD-074: void one unpaid line without deleting it or its invoice."""

    assert_transaction_active()
    if not (reason or "").strip():
        raise CanonicalError("INVOICE_LINE_VOID_REASON_REQUIRED", "A reason is required.", status_code=400)
    invoice = Invoice.objects.select_for_update().filter(
        id=invoice_id, organisation=organisation, facility=facility
    ).first()
    if invoice is None:
        raise CanonicalError("INVOICE_NOT_FOUND", "Invoice was not found.", status_code=404)
    line = InvoiceItem.objects.select_for_update().filter(
        id=line_id, invoice=invoice, organisation=organisation
    ).first()
    if line is None:
        raise CanonicalError("INVOICE_LINE_NOT_FOUND", "Invoice line was not found.", status_code=404)
    if line.state != "ACTIVE":
        return line, invoice, False
    if effective_allocation_total(invoice=invoice) > 0:
        raise CanonicalError(
            "PAID_LINE_VOID_REFUSED",
            "A paid or partially paid line cannot be voided; reverse the payment first.",
            status_code=409,
        )
    before = {"total": str(invoice.total), "balance": str(invoice.balance)}
    line.state = "VOIDED"
    line.void_reason = reason.strip()[:240]
    line.voided_at = now()
    line.voided_by = actor
    line.save(update_fields=["state", "void_reason", "voided_at", "voided_by", "updated_at"])
    invoice = recompute_invoice_projection(invoice)
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="VOID",
        entity_type="InvoiceItem",
        entity_id=line.id,
        before=before,
        after={"total": str(invoice.total), "balance": str(invoice.balance)},
        event_code="INVOICE_LINE_VOIDED",
    )
    return line, invoice, True
