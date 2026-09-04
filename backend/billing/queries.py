"""Pure billing projections used by cross-domain read coordinators."""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Sum

from billing.models import Invoice
from core.services import assert_transaction_active


@dataclass(frozen=True)
class PatientOutstandingBalanceProjection:
    amount: Decimal
    invoice_no: str | None
    visit_id: str | None


def patient_outstanding_balance(*, organisation, facility, patient):
    """Return current-facility unpaid balance without changing billing state."""

    assert_transaction_active()
    invoices = Invoice.objects.filter(
        organisation=organisation,
        facility=facility,
        patient=patient,
        status__in=("ISSUED", "PARTIALLY_PAID"),
    ).order_by("-created_at", "-id")
    total = invoices.aggregate(total=Sum("balance"))["total"] or Decimal("0.00")
    latest = invoices.first()
    return PatientOutstandingBalanceProjection(
        amount=total.quantize(Decimal("0.01")),
        invoice_no=latest.invoice_no if latest is not None else None,
        visit_id=str(latest.visit_id) if latest is not None and latest.visit_id else None,
    )
