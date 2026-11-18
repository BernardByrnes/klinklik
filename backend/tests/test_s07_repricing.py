"""S-07 atomic ISSUED-to-ISSUED invoice repricing proofs."""

from decimal import Decimal

import pytest

from audit.models import AuditEvent
from billing.models import Invoice, InvoiceItem, PriceList, ServicePrice, VisitPayerBinding
from core.clock import local_service_date
from core.services import tenant_atomic
from tests.test_s05_billing import check_in, open_shift, pay, register

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def s01_target_cutover(enabled_mig001_target):
    return enabled_mig001_target


def _new_price_list(tenant, amount="35000.00", payer_type="CASH"):
    with tenant_atomic(tenant.organisation.id):
        price_list = PriceList.objects.create(
            organisation=tenant.organisation,
            stable_code=f"STANDARD-{amount}-{payer_type}",
            name=f"Synthetic {amount} {payer_type}",
            payer_type=payer_type,
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
        return str(price_list.id)


def _reprice(client, invoice_id, version, price_list_id, key, **overrides):
    payload = {
        "expected_version": version,
        "price_list_id": price_list_id,
        **overrides,
    }
    return client.post(
        f"/api/v1/billing/invoices/{invoice_id}/reprice/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def test_s07_issued_invoice_reprices_atomically_with_retained_versions(
    tenant, authed_client
):
    patient_id = register(authed_client, "s07-register-reprice")
    checked_in = check_in(authed_client, patient_id, tenant, "s07-checkin-reprice")
    invoice_id = checked_in["invoice_id"]
    with tenant_atomic(tenant.organisation.id):
        invoice = Invoice.objects.get(id=invoice_id)
        original = InvoiceItem.objects.get(
            invoice=invoice, line_set_version=invoice.current_line_set_version
        )
        original_amount = original.amount
        original_version = invoice.version
        original_no = invoice.invoice_no
    price_list_id = _new_price_list(tenant)

    response = _reprice(
        authed_client, invoice_id, original_version, price_list_id, "s07-reprice"
    )
    assert response.status_code == 200, response.data
    assert response.data["before_total"] == "30000.00"
    assert response.data["after_total"] == "35000.00"
    assert response.data["line_set_version"] == 2
    assert response.data["status"] == "ISSUED"

    with tenant_atomic(tenant.organisation.id):
        invoice = Invoice.objects.get(id=invoice_id)
        assert invoice.invoice_no == original_no
        assert invoice.status == "ISSUED"
        assert invoice.total == Decimal("35000.00")
        assert invoice.balance == Decimal("35000.00")
        assert invoice.current_line_set_version == 2
        old = InvoiceItem.objects.get(id=original.id)
        assert old.amount == original_amount == Decimal("30000.00")
        assert old.line_set_version == 1
        current = InvoiceItem.objects.get(
            invoice=invoice, line_set_version=2, state="ACTIVE"
        )
        assert current.amount == Decimal("35000.00")
        assert current.source_line_identity == "CONSULTATION"
        assert VisitPayerBinding.objects.filter(visit_id=checked_in["visit_id"]).count() == 2
        assert VisitPayerBinding.objects.get(
            visit_id=checked_in["visit_id"], active=True
        ).price_list_id
        event = AuditEvent.objects.get(
            event_code="INVOICE_REPRICED", entity_id=str(invoice.id)
        )
        assert event.before["line_set_version"] == 1
        assert event.after["line_set_version"] == 2

    detail = authed_client.get(f"/api/v1/billing/invoices/{invoice_id}/")
    sets = {item["line_set_version"] for item in detail.data["items"]}
    assert sets == {1, 2}
    assert all(item["is_current"] == (item["line_set_version"] == 2) for item in detail.data["items"])

    # Same key replays the committed outcome with no second set or audit.
    replay = _reprice(
        authed_client, invoice_id, original_version, price_list_id, "s07-reprice"
    )
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replay"] == "true"
    assert replay.data["line_set_version"] == 2
    with tenant_atomic(tenant.organisation.id):
        assert InvoiceItem.objects.filter(invoice_id=invoice_id).count() == 2
        assert AuditEvent.objects.filter(event_code="INVOICE_REPRICED").count() == 1


def test_s07_reprice_refuses_paid_partial_stale_and_conflicting_attempts(
    tenant, authed_client
):
    patient_id = register(authed_client, "s07-register-guards")
    checked_in = check_in(authed_client, patient_id, tenant, "s07-checkin-guards")
    invoice_id = checked_in["invoice_id"]
    with tenant_atomic(tenant.organisation.id):
        invoice = Invoice.objects.get(id=invoice_id)
        original_version = invoice.version
    price_list_id = _new_price_list(tenant)

    stale = _reprice(
        authed_client, invoice_id, original_version - 1, price_list_id, "s07-stale"
    )
    assert stale.status_code == 409
    assert stale.data["code"] == "VERSION_CONFLICT"

    with tenant_atomic(tenant.organisation.id):
        unchanged = Invoice.objects.get(id=invoice_id)
        assert unchanged.total == Decimal("30000.00")
        assert unchanged.current_line_set_version == 1

    open_shift(authed_client)
    partial = pay(authed_client, invoice_id, "10000.00", "s07-partial-payment")
    assert partial.status_code == 201
    with tenant_atomic(tenant.organisation.id):
        version = Invoice.objects.get(id=invoice_id).version
    locked = _reprice(
        authed_client, invoice_id, version, price_list_id, "s07-paid-lock"
    )
    assert locked.status_code == 409
    assert locked.data["code"] == "PAYER_LOCKED"
    with tenant_atomic(tenant.organisation.id):
        invoice = Invoice.objects.get(id=invoice_id)
        assert invoice.current_line_set_version == 1
        assert invoice.total == Decimal("30000.00")
        assert InvoiceItem.objects.filter(invoice_id=invoice_id).count() == 1

    # A second unpaid invoice priced with the same list has no change to apply.
    second_patient = register(authed_client, "s07-register-nochange")
    second = check_in(authed_client, second_patient, tenant, "s07-checkin-nochange")
    with tenant_atomic(tenant.organisation.id):
        second_version = Invoice.objects.get(id=second["invoice_id"]).version
        no_change_list = VisitPayerBinding.objects.get(
            visit_id=second["visit_id"], active=True
        ).price_list_id
    no_change = _reprice(
        authed_client,
        second["invoice_id"],
        second_version,
        str(no_change_list),
        "s07-no-change",
    )
    assert no_change.status_code == 409
    assert no_change.data["code"] == "REPRICE_NO_CHANGE"
