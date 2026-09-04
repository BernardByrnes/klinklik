import secrets
import string
from decimal import Decimal

from django.db import models, transaction
from audit.services import record_event
from billing.models import (
    Invoice,
    InvoiceItem,
    Payment,
    PaymentAllocation,
    PriceList,
    ServiceCatalogItem,
    ServicePrice,
    VisitPayerBinding,
)
from clinical.models import Encounter
from core.clock import local_service_date, now
from core.errors import CanonicalError
from core.services import allocate_sequence, assert_transaction_active
from patients.models import Patient
from scheduling.models import Visit


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
    subtotal = sum(
        (line.amount for line in invoice.items.filter(state="ACTIVE")),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    invoice.subtotal = subtotal
    invoice.total = subtotal
    invoice.balance = max(Decimal("0.00"), subtotal - invoice.amount_paid).quantize(Decimal("0.01"))
    invoice.status = "ISSUED"
    invoice.issued_at = invoice.issued_at or now()
    invoice.version += 1
    invoice.save(
        update_fields=[
            "subtotal",
            "total",
            "balance",
            "status",
            "issued_at",
            "version",
            "updated_at",
        ]
    )
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
        status="POSTED",
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
    total = max(Decimal("0.00"), subtotal - Decimal(str(discount))).quantize(Decimal("0.01"))
    invoice.subtotal = subtotal
    invoice.total = total
    invoice.balance = total
    invoice.status = "ISSUED"
    invoice.issued_at = now()
    invoice.save(update_fields=["subtotal", "total", "balance", "status", "issued_at", "updated_at"])
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


@transaction.atomic
def post_payment(*, organisation, facility, actor, invoice_id, amount, method, reference="", request=None):
    invoice = Invoice.objects.select_for_update().filter(
        id=invoice_id, organisation=organisation, facility=facility
    ).first()
    if invoice is None:
        raise ValueError("Invoice was not found in this facility.")
    if invoice.status in {"PAID", "VOID"}:
        raise ValueError("This invoice cannot accept a payment.")
    amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    if amount <= 0 or amount > invoice.balance:
        raise ValueError("Payment amount must be positive and no greater than the invoice balance.")
    payment = Payment.objects.create(
        organisation=organisation,
        facility=facility,
        invoice=invoice,
        receipt_no=_reference("RCT"),
        amount=amount,
        method=method,
        reference=reference,
        received_by=actor,
    )
    PaymentAllocation.objects.create(
        organisation=organisation,
        payment=payment,
        invoice=invoice,
        facility=facility,
        amount=amount,
    )
    invoice.amount_paid = (invoice.amount_paid + amount).quantize(Decimal("0.01"))
    invoice.balance = (invoice.total - invoice.amount_paid).quantize(Decimal("0.01"))
    invoice.status = "PAID" if invoice.balance == 0 else "PARTIALLY_PAID"
    invoice.save(update_fields=["amount_paid", "balance", "status", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="PAYMENT",
        entity_type="Payment",
        entity_id=payment.id,
        after={"invoice_id": str(invoice.id), "receipt_no": payment.receipt_no, "amount": str(amount), "method": method},
    )
    return payment
