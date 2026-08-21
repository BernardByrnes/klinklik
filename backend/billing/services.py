import secrets
import string
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from audit.services import record_event
from billing.models import Invoice, InvoiceItem, Payment, PaymentAllocation, ServiceCatalogItem, ServicePrice
from clinical.models import Encounter
from patients.models import Patient


def _reference(prefix):
    alphabet = string.ascii_uppercase + string.digits
    return prefix + "-" + "".join(secrets.choice(alphabet) for _ in range(10))


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
            raise ValueError("A selected service is not available.")
        price = ServicePrice.objects.filter(
            organisation=organisation,
            facility=facility,
            service=service,
            is_active=True,
            effective_from__lte=timezone.localdate(),
        ).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=timezone.localdate())
        ).order_by("-effective_from").first()
        if price is None:
            raise ValueError(f"No active price is configured for {service.name}.")
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
    invoice.issued_at = timezone.now()
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
