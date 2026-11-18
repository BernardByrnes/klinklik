"""S-06 PostgreSQL credit/refund evidence, RLS and concurrency proofs."""

import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection

from accounts.models import User
from billing.models import CreditNote, Invoice, Refund
from billing.services import issue_credit_note, request_refund
from core.errors import CanonicalError
from core.rls import rls_status
from core.services import tenant_atomic
from tests.test_s05_billing import check_in, open_shift, pay, register

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="S-06 PostgreSQL proof gate"),
]


def test_pg_s06_credit_evidence_force_rls_and_guards(tenant, authed_client, enabled_mig001_target):
    patient_id = register(authed_client, "s06-pg-register-credit")
    checked_in = check_in(authed_client, patient_id, tenant, "s06-pg-checkin-credit")
    credit = authed_client.post(
        f"/api/v1/billing/invoices/{checked_in['invoice_id']}/credit-notes/",
        {"amount": "5000.00", "reason": "Synthetic PG credit"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s06-pg-credit",
    )
    assert credit.status_code == 201, credit.data

    status = rls_status()
    assert status["enforced"] is True
    tables = {table["name"]: table for table in status["tables"]}
    for name in ("billing_creditnote", "billing_refund", "billing_invoice"):
        assert tables[name]["rowsecurity"] is True
        assert tables[name]["force"] is True
        assert tables[name]["owner"] != status["role"]["name"]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tgname FROM pg_trigger
            WHERE tgrelid IN ('billing_creditnote'::regclass, 'billing_refund'::regclass)
              AND NOT tgisinternal AND tgenabled = 'O'
            """
        )
        triggers = {row[0] for row in cursor.fetchall()}
        assert {
            "klin_klink_credit_note_immutable",
            "klin_klink_refund_evidence_immutable",
        } <= triggers
    with tenant_atomic(tenant.organisation.id):
        invoice = Invoice.objects.get(id=checked_in["invoice_id"])
        assert invoice.credit_total == Decimal("5000.00")
        assert invoice.balance == Decimal("25000.00")
        assert invoice.total == Decimal("30000.00")
        assert invoice.amount_paid == Decimal("0.00")
        assert CreditNote.objects.filter(invoice=invoice).count() == 1


def test_pg_s06_concurrent_credits_cannot_exceed_creditable_value(
    tenant, authed_client, enabled_mig001_target
):
    patient_id = register(authed_client, "s06-pg-register-concurrent")
    checked_in = check_in(authed_client, patient_id, tenant, "s06-pg-checkin-concurrent")
    invoice_id = checked_in["invoice_id"]
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
                credit, invoice = issue_credit_note(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    invoice_id=invoice_id,
                    amount="20000.00",
                    reason="Synthetic concurrent credit",
                )
                return ("ok", str(credit.id), str(invoice.balance))
        except (CanonicalError, ValueError) as exc:
            return ("error", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: attempt(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    with tenant_atomic(organisation.id):
        invoice = Invoice.objects.get(id=invoice_id)
        assert invoice.credit_total == Decimal("20000.00")
        assert invoice.balance == Decimal("10000.00")
        assert CreditNote.objects.filter(invoice=invoice).count() == 1


def test_pg_s06_refund_request_is_bounded_by_refundable_credit(
    tenant, authed_client, enabled_mig001_target
):
    patient_id = register(authed_client, "s06-pg-register-refund")
    checked_in = check_in(authed_client, patient_id, tenant, "s06-pg-checkin-refund")
    invoice_id = checked_in["invoice_id"]
    open_shift(authed_client)
    paid = pay(authed_client, invoice_id, "30000.00", "s06-pg-pay")
    assert paid.status_code == 201
    credit = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/credit-notes/",
        {"amount": "10000.00", "reason": "Synthetic PG refundable"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s06-pg-credit-refund",
    )
    assert credit.status_code == 201
    with tenant_atomic(tenant.organisation.id):
        refund = request_refund(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            payment_id=paid.data["id"],
            credit_note_id=credit.data["id"],
            amount="4000.00",
            reason="Synthetic PG refund",
        )
        assert refund.status == "REQUESTED"
        assert Refund.objects.filter(payment_id=paid.data["id"]).count() == 1
        with pytest.raises(CanonicalError) as excessive:
            request_refund(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                payment_id=paid.data["id"],
                credit_note_id=credit.data["id"],
                amount="6000.00",
                reason="Synthetic PG excess",
            )
        assert excessive.value.code in {"REFUND_ALREADY_REQUESTED", "REFUND_EXCEEDS_REFUNDABLE"}
        assert Invoice.objects.get(id=invoice_id).refundable_credit == Decimal("10000.00")
