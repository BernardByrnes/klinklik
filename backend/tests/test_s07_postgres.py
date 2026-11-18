"""S-07 PostgreSQL repricing race, immutability and RLS proofs."""

import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from django.db import close_old_connections, connection, transaction
from django.db.utils import DatabaseError

from accounts.models import User
from audit.models import AuditEvent
from billing.models import (
    Invoice,
    InvoiceItem,
    PriceList,
    ServicePrice,
    VisitPayerBinding,
)
from billing.services import confirm_payment, reprice_invoice
from core.clock import local_service_date
from core.errors import CanonicalError
from core.rls import rls_status
from core.services import tenant_atomic
from tests.test_s05_billing import check_in, register

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="S-07 PostgreSQL proof gate"),
]


def _price_list(tenant, amount="35000.00"):
    with tenant_atomic(tenant.organisation.id):
        price_list = PriceList.objects.create(
            organisation=tenant.organisation,
            stable_code=f"S07-{amount}",
            name=f"Synthetic S07 {amount}",
            payer_type="CASH",
            effective_from=local_service_date(),
            version=2,
        )
        ServicePrice.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            service=tenant.service,
            price_list=price_list,
            amount=amount,
            currency="UGX",
            effective_from=local_service_date(),
        )
        return price_list.id


def _setup(tenant, client):
    patient_id = register(client, f"s07-pg-{tenant.organisation.id}")
    checked_in = check_in(client, patient_id, tenant, f"s07-pg-checkin-{patient_id}")
    with tenant_atomic(tenant.organisation.id):
        invoice = Invoice.objects.get(id=checked_in["invoice_id"])
        return invoice.id, invoice.version


def test_pg_s07_reprice_rls_and_prior_version_immutability(tenant, authed_client, enabled_mig001_target):
    invoice_id, version = _setup(tenant, authed_client)
    price_list_id = _price_list(tenant)
    response = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/reprice/",
        {"expected_version": version, "price_list_id": str(price_list_id)},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s07-pg-reprice",
    )
    assert response.status_code == 200, response.data
    status = rls_status()
    assert status["enforced"] is True
    with tenant_atomic(tenant.organisation.id):
        invoice = Invoice.objects.get(id=invoice_id)
        old_line = InvoiceItem.objects.get(invoice=invoice, line_set_version=1)
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                InvoiceItem.objects.filter(id=old_line.id).update(amount=Decimal("1.00"))
        assert InvoiceItem.objects.get(id=old_line.id).amount == Decimal("30000.00")
        assert InvoiceItem.objects.filter(invoice=invoice).count() == 2
        assert invoice.current_line_set_version == 2


def test_pg_s07_concurrent_reprices_have_one_winner(tenant, authed_client, enabled_mig001_target):
    invoice_id, version = _setup(tenant, authed_client)
    price_list_id = _price_list(tenant)
    with tenant_atomic(tenant.organisation.id):
        organisation = tenant.organisation
        facility = tenant.facility
        actor = User.objects.get(id=tenant.user.id)

    barrier = threading.Barrier(2)

    def attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                invoice, _binding, _before = reprice_invoice(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    invoice_id=invoice_id,
                    expected_version=version,
                    price_list_id=price_list_id,
                )
                return ("ok", invoice.current_line_set_version)
        except (CanonicalError, ValueError) as exc:
            return ("error", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: attempt(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    assert ("ok", 2) in results
    with tenant_atomic(organisation.id):
        invoice = Invoice.objects.get(id=invoice_id)
        assert invoice.current_line_set_version == 2
        assert InvoiceItem.objects.filter(invoice=invoice).count() == 2
        assert AuditEvent.objects.filter(event_code="INVOICE_REPRICED").count() == 1


def test_pg_s07_reprice_and_payment_race_has_no_mixed_state(tenant, authed_client, enabled_mig001_target):
    invoice_id, version = _setup(tenant, authed_client)
    price_list_id = _price_list(tenant)
    with tenant_atomic(tenant.organisation.id):
        organisation = tenant.organisation
        facility = tenant.facility
        actor = User.objects.get(id=tenant.user.id)

    barrier = threading.Barrier(2)

    def reprice_attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                invoice, _binding, _before = reprice_invoice(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    invoice_id=invoice_id,
                    expected_version=version,
                    price_list_id=price_list_id,
                )
                return ("repriced", str(invoice.total))
        except (CanonicalError, ValueError) as exc:
            return ("refused", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    def payment_attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                outcome = confirm_payment(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    amount="30000.00",
                    method="CASH",
                    invoice_id=invoice_id,
                    require_shift=False,
                )
                return ("paid", str(outcome.payment.amount))
        except (CanonicalError, ValueError) as exc:
            return ("refused", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        reprice_future = executor.submit(reprice_attempt)
        payment_future = executor.submit(payment_attempt)
        reprice_result = reprice_future.result()
        payment_result = payment_future.result()
    with tenant_atomic(organisation.id):
        invoice = Invoice.objects.get(id=invoice_id)
        if reprice_result[0] == "repriced":
            assert invoice.total == Decimal("35000.00")
            assert invoice.current_line_set_version == 2
            if payment_result[0] == "paid":
                assert invoice.amount_paid == Decimal("30000.00")
                assert invoice.balance == Decimal("5000.00")
                assert invoice.status == "PARTIALLY_PAID"
            else:
                assert invoice.amount_paid == Decimal("0.00")
                assert invoice.balance == Decimal("35000.00")
        else:
            assert payment_result[0] == "paid"
            assert invoice.total == Decimal("30000.00")
            assert invoice.current_line_set_version == 1
            assert invoice.amount_paid == Decimal("30000.00")
            assert invoice.status == "PAID"
