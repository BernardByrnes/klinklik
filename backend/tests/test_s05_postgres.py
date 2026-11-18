"""S-05 PostgreSQL money, guard, RLS and concurrency proofs."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection

from accounts.models import User
from audit.models import AuditEvent
from billing.models import (
    CashierShift,
    Invoice,
    Payment,
    PaymentAllocation,
    PaymentReceipt,
)
from billing.services import confirm_payment, create_invoice
from core.errors import CanonicalError
from core.rls import rls_status
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import Visit
from tenancy.models import Facility, Organisation
from tests.test_s05_billing import check_in, open_shift as api_open_shift, pay, register

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="S-05 PostgreSQL proof gate"),
]


def test_pg_s05_force_rls_receipt_guards_and_money_constraints(tenant):
    status = rls_status()
    assert status["enforced"] is True
    tables = {table["name"]: table for table in status["tables"]}
    for name in (
        "billing_payment",
        "billing_paymentallocation",
        "billing_paymentreceipt",
        "billing_paymentmethodconfig",
        "billing_invoiceitem",
        "billing_cashiershift",
    ):
        assert tables[name]["rowsecurity"] is True
        assert tables[name]["force"] is True
        assert tables[name]["owner"] != status["role"]["name"]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tgname FROM pg_trigger
            WHERE tgrelid IN ('billing_payment'::regclass,
                              'billing_paymentreceipt'::regclass,
                              'billing_paymentallocation'::regclass,
                              'billing_invoiceitem'::regclass)
              AND NOT tgisinternal AND tgenabled = 'O'
            """
        )
        triggers = {row[0] for row in cursor.fetchall()}
        assert {
            "klin_klink_payment_evidence_immutable",
            "klin_klink_receipt_evidence_immutable",
            "klin_klink_allocation_evidence_immutable",
            "klin_klink_invoice_item_financial_immutable",
        } <= triggers
        cursor.execute(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'billing_payment'::regclass
              AND conname = 'payment_amount_positive' AND convalidated
            """
        )
        assert cursor.fetchone() is not None
        cursor.execute(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'billing_cashiershift'
              AND indexname = 'uniq_open_cashier_shift'
            """
        )
        assert cursor.fetchone() is not None


def test_pg_s05_competing_final_payments_have_one_winner(tenant):
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S05-{uuid4().hex[:8]}",
            first_name="S05 PG",
            last_name="Synthetic",
            sex="UNKNOWN",
            date_of_birth=date(1990, 1, 1),
        )
        visit = Visit.objects.create(
            organisation=organisation,
            facility=facility,
            patient=patient,
            local_service_date=date.today(),
            visit_type="OUTPATIENT_NEW",
            opened_by=actor,
        )
        invoice = create_invoice(
            organisation=organisation,
            facility=facility,
            actor=actor,
            patient_id=patient.id,
            items=[{"service_id": str(tenant.service.id), "quantity": "1"}],
        )
        invoice_id = invoice.id

    import threading

    barrier = threading.Barrier(2)

    def attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(tenant.organisation.id):
                outcome = confirm_payment(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    amount="20000.00",
                    method="CASH",
                    invoice_id=invoice_id,
                    require_shift=False,
                )
                return ("ok", str(outcome.payment.id), outcome.receipt.receipt_no)
        except (CanonicalError, ValueError) as exc:
            return ("error", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: attempt(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    with tenant_atomic(tenant.organisation.id):
        stored = Invoice.objects.get(id=invoice_id)
        assert stored.amount_paid == Decimal("20000.00")
        assert stored.balance == Decimal("10000.00")
        assert stored.status == "PARTIALLY_PAID"
        assert Payment.objects.filter(invoice_id=invoice_id).count() == 1
        assert PaymentAllocation.objects.filter(invoice_id=invoice_id).count() == 1
        assert PaymentReceipt.objects.filter(payment__invoice_id=invoice_id).count() == 1
        assert AuditEvent.objects.filter(
            event_code="PAYMENT", entity_type="Payment"
        ).count() == 1


def test_pg_s05_reversal_restores_every_allocated_invoice(
    tenant, authed_client, enabled_mig001_target
):
    patient_id = register(authed_client, "s05-pg-register-reverse")
    first = check_in(authed_client, patient_id, tenant, "s05-pg-checkin-reverse")
    with tenant_atomic(tenant.organisation.id):
        second = create_invoice(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            patient_id=patient_id,
            items=[{"service_id": str(tenant.service.id), "quantity": "1"}],
        )
        second_id = str(second.id)
    api_open_shift(authed_client)
    split = authed_client.post(
        f"/api/v1/billing/invoices/{first['invoice_id']}/payments/",
        {
            "amount": "60000.00",
            "method": "CASH",
            "allocations": [
                {"invoice_id": first["invoice_id"], "amount": "30000.00"},
                {"invoice_id": second_id, "amount": "30000.00"},
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-pg-split",
    )
    assert split.status_code == 201, split.data
    reversed_response = authed_client.post(
        f"/api/v1/billing/payments/{split.data['id']}/reverse/",
        {"reason": "Synthetic PostgreSQL reversal"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-pg-reverse",
    )
    assert reversed_response.status_code == 200, reversed_response.data
    assert all(item["status"] == "ISSUED" for item in reversed_response.data["invoices"])
    assert all(item["balance"] == "30000.00" for item in reversed_response.data["invoices"])
    with tenant_atomic(tenant.organisation.id):
        assert Invoice.objects.get(id=first["invoice_id"]).balance == Decimal("30000.00")
        assert Invoice.objects.get(id=second_id).balance == Decimal("30000.00")
        payment = Payment.objects.get(id=split.data["id"])
        assert payment.status == "REVERSED"
        assert PaymentAllocation.objects.filter(payment=payment).count() == 2
        assert PaymentReceipt.objects.filter(payment=payment).count() == 1


def test_pg_s05_payment_and_blind_close_serialize_on_the_shift(tenant):
    from billing.services import close_shift, open_shift

    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S05-CLOSE-{uuid4().hex[:8]}",
            first_name="S05 PG",
            last_name="Synthetic",
            sex="UNKNOWN",
            date_of_birth=date(1990, 1, 1),
        )
        invoice = create_invoice(
            organisation=organisation,
            facility=facility,
            actor=actor,
            patient_id=patient.id,
            items=[{"service_id": str(tenant.service.id), "quantity": "1"}],
        )
        shift = open_shift(
            organisation=organisation,
            facility=facility,
            actor=actor,
            opening_float="0.00",
        )
        invoice_id = invoice.id
        shift_id = shift.id

    import threading
    from concurrent.futures import ThreadPoolExecutor

    barrier = threading.Barrier(2)

    def pay_attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(tenant.organisation.id):
                outcome = confirm_payment(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    amount="10000.00",
                    method="CASH",
                    invoice_id=invoice_id,
                    require_shift=True,
                )
                return ("paid", str(outcome.payment.id))
        except (CanonicalError, ValueError) as exc:
            return ("refused", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    def close_attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(tenant.organisation.id):
                stored = close_shift(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    shift_id=shift_id,
                    declared_cash="10000.00",
                )
                return ("closed", str(stored.expected_cash))
        except (CanonicalError, ValueError) as exc:
            return ("refused", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        payment_future = executor.submit(pay_attempt)
        close_future = executor.submit(close_attempt)
        payment_result = payment_future.result()
        close_result = close_future.result()
    assert close_result[0] == "closed"
    with tenant_atomic(tenant.organisation.id):
        stored = CashierShift.objects.get(id=shift_id)
        assert stored.status == "CLOSED"
        payment_count = Payment.objects.filter(shift_id=shift_id).count()
        if payment_result[0] == "paid":
            assert stored.expected_cash == Decimal("10000.00")
            assert payment_count == 1
            assert Invoice.objects.get(id=invoice_id).amount_paid == Decimal("10000.00")
        else:
            assert stored.expected_cash == Decimal("0.00")
            assert payment_count == 0
            assert Invoice.objects.get(id=invoice_id).amount_paid == Decimal("0.00")


def test_pg_s05_receipt_numbers_are_exact_and_blind_close_reads_committed_cash(
    tenant, authed_client, enabled_mig001_target
):
    patient_id = register(authed_client, "s05-pg-register-close")
    checked_in = check_in(authed_client, patient_id, tenant, "s05-pg-checkin-close")
    shift = api_open_shift(authed_client, "5000.00")
    first = pay(authed_client, checked_in["invoice_id"], "10000.00", "s05-pg-pay-1")
    second = pay(authed_client, checked_in["invoice_id"], "20000.00", "s05-pg-pay-2")
    assert first.status_code == 201, first.data
    assert second.status_code == 201, second.data
    assert first.data["receipt_no"] != second.data["receipt_no"]
    assert first.data["receipt_no"].startswith("RCT-")
    with tenant_atomic(tenant.organisation.id):
        receipts = PaymentReceipt.objects.filter(
            organisation_id=tenant.organisation.id
        ).order_by("receipt_no")
        assert receipts.count() == 2
        assert len({receipt.receipt_no for receipt in receipts}) == 2

    closed = authed_client.post(
        f"/api/v1/billing/shifts/{shift['id']}/close/",
        {"declared_cash": "34000.00"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-pg-close",
    )
    assert closed.status_code == 200, closed.data
    assert closed.data["expected_cash"] == "35000.00"
    assert closed.data["variance"] == "-1000.00"
    with tenant_atomic(tenant.organisation.id):
        stored = CashierShift.objects.get(id=shift["id"])
        assert stored.status == "CLOSED"
        assert stored.expected_cash == Decimal("35000.00")
        assert stored.variance == Decimal("-1000.00")
        assert AuditEvent.objects.filter(event_code="SHIFT_CLOSED").count() == 1
