"""S-06 credit-note, refund and Z-report proofs."""

from decimal import Decimal

import pytest

from accounts.models import User
from audit.models import AuditEvent
from billing.models import CreditNote, Invoice, Payment, PaymentReceipt, Refund
from billing.services import approve_refund, reject_refund, request_refund
from core.errors import CanonicalError
from core.services import tenant_atomic
from tests.test_s05_billing import check_in, open_shift, pay, register

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def s01_target_cutover(enabled_mig001_target):
    return enabled_mig001_target


def _issue(client, invoice_id, amount, key, reason="Synthetic credit reason"):
    return client.post(
        f"/api/v1/billing/invoices/{invoice_id}/credit-notes/",
        {"amount": amount, "reason": reason},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def test_s06_credit_note_reduces_due_without_rewriting_history(tenant, authed_client):
    patient_id = register(authed_client, "s06-register-credit")
    checked_in = check_in(authed_client, patient_id, tenant, "s06-checkin-credit")
    invoice_id = checked_in["invoice_id"]

    missing_reason = _issue(authed_client, invoice_id, "5000.00", "s06-credit-no-reason", "")
    assert missing_reason.status_code == 400
    assert missing_reason.data["code"] == "CREDIT_NOTE_REASON_REQUIRED"

    credit = _issue(authed_client, invoice_id, "5000.00", "s06-credit-partial")
    assert credit.status_code == 201, credit.data
    assert credit.data["credit_no"].startswith("CN-")
    assert credit.data["credit_total"] == "5000.00"
    assert credit.data["balance"] == "25000.00"
    assert credit.data["refundable_credit"] == "0.00"

    over = _issue(authed_client, invoice_id, "30000.00", "s06-credit-over")
    assert over.status_code == 409
    assert over.data["code"] == "CREDIT_NOTE_EXCEEDS_CREDITABLE"

    detail = authed_client.get(f"/api/v1/billing/invoices/{invoice_id}/")
    assert detail.status_code == 200
    assert detail.data["credit_total"] == "5000.00"
    assert detail.data["balance"] == "25000.00"
    assert detail.data["total"] == "30000.00"
    assert detail.data["amount_paid"] == "0.00"

    note = authed_client.get(f"/api/v1/billing/credit-notes/{credit.data['id']}/")
    assert note.status_code == 200
    assert note.data["reason"] == "Synthetic credit reason"
    assert note.data["status"] == "ISSUED"

    with tenant_atomic(tenant.organisation.id):
        stored = CreditNote.objects.get(id=credit.data["id"])
        assert stored.amount == Decimal("5000.00")
        assert stored.reason_hash
        event = AuditEvent.objects.get(
            event_code="CREDIT_NOTE_ISSUED", entity_id=str(stored.id)
        )
        assert event.after["credit_no"] == stored.credit_no
        assert event.after["reason_hash"] == stored.reason_hash
        assert "amount" not in event.after
        assert "Synthetic credit reason" not in str(event.after)


def test_s06_credit_note_on_paid_invoice_creates_bounded_refundable_credit(
    tenant, authed_client
):
    patient_id = register(authed_client, "s06-register-refundable")
    checked_in = check_in(authed_client, patient_id, tenant, "s06-checkin-refundable")
    invoice_id = checked_in["invoice_id"]
    open_shift(authed_client)
    paid = pay(authed_client, invoice_id, "30000.00", "s06-pay-refundable")
    assert paid.status_code == 201
    payment_id = paid.data["id"]

    credit = _issue(authed_client, invoice_id, "10000.00", "s06-credit-refundable")
    assert credit.status_code == 201, credit.data
    assert credit.data["refundable_credit"] == "10000.00"
    assert credit.data["balance"] == "0.00"

    with tenant_atomic(tenant.organisation.id):
        invoice = Invoice.objects.get(id=invoice_id)
        assert invoice.status == "PAID"
        assert invoice.credit_total == Decimal("10000.00")
        assert invoice.amount_paid == Decimal("30000.00")
        assert invoice.refundable_credit == Decimal("10000.00")
        assert Payment.objects.get(id=payment_id).status == "CONFIRMED"
        assert PaymentReceipt.objects.filter(payment_id=payment_id).count() == 1
        assert CreditNote.objects.filter(invoice_id=invoice_id).count() == 1


def test_s06_refund_flow_requires_mfa_and_separation(tenant, authed_client):
    patient_id = register(authed_client, "s06-register-refund")
    checked_in = check_in(authed_client, patient_id, tenant, "s06-checkin-refund")
    invoice_id = checked_in["invoice_id"]
    open_shift(authed_client)
    paid = pay(authed_client, invoice_id, "30000.00", "s06-pay-refund")
    credit = _issue(authed_client, invoice_id, "10000.00", "s06-credit-refund")
    assert credit.status_code == 201

    with tenant_atomic(tenant.organisation.id):
        approver = User.objects.create_user("s06-approver", "test-password-123")
        refund = request_refund(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            payment_id=paid.data["id"],
            credit_note_id=credit.data["id"],
            amount="5000.00",
            reason="Synthetic partial refund",
        )
        assert refund.status == "REQUESTED"
        assert refund.status != "APPROVED"
        refund_id = refund.id
        with pytest.raises(CanonicalError) as duplicate:
            request_refund(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                payment_id=paid.data["id"],
                credit_note_id=credit.data["id"],
                amount="1000.00",
                reason="Synthetic duplicate",
            )
        assert duplicate.value.code == "REFUND_ALREADY_REQUESTED"

        with pytest.raises(CanonicalError) as mfa:
            approve_refund(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=approver,
                refund_id=refund_id,
                mfa_verified=False,
            )
        assert mfa.value.code == "MFA_REQUIRED"
        assert mfa.value.status_code == 403

        with pytest.raises(CanonicalError) as self_approval:
            approve_refund(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                refund_id=refund_id,
                mfa_verified=True,
            )
        assert self_approval.value.code == "REFUND_SELF_APPROVAL"

        approved, invoice = approve_refund(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=approver,
            refund_id=refund_id,
            mfa_verified=True,
        )
        assert approved.status == "APPROVED"
        assert approved.approved_by_id == approver.id
        assert invoice.refunded_total == Decimal("5000.00")
        assert invoice.refundable_credit == Decimal("5000.00")
        assert Invoice.objects.get(id=invoice_id).balance == Decimal("0.00")

        second = request_refund(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            payment_id=paid.data["id"],
            credit_note_id=credit.data["id"],
            amount="5000.00",
            reason="Synthetic second refund",
        )
        rejected = reject_refund(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=approver,
            refund_id=second.id,
            reason="Synthetic rejection",
        )
        assert rejected.status == "REJECTED"
        assert Invoice.objects.get(id=invoice_id).refundable_credit == Decimal("5000.00")
        assert AuditEvent.objects.filter(event_code="REFUND_APPROVED").count() == 1
        assert AuditEvent.objects.filter(event_code="REFUND_REJECTED").count() == 1


def test_s06_refund_endpoints_are_fenced(tenant, authed_client):
    response = authed_client.post(
        "/api/v1/billing/refunds/",
        {"payment_id": "00000000-0000-0000-0000-000000000000", "amount": "1000.00"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s06-refund-fenced",
    )
    assert response.status_code == 503
    assert response.data["code"] == "REFUND_ISSUANCE_DISABLED"
    with tenant_atomic(tenant.organisation.id):
        assert Refund.objects.count() == 0


def test_s06_z_report_uses_committed_shift_evidence(tenant, authed_client):
    patient_id = register(authed_client, "s06-register-zreport")
    checked_in = check_in(authed_client, patient_id, tenant, "s06-checkin-zreport")
    shift = open_shift(authed_client, "5000.00")
    first = pay(authed_client, checked_in["invoice_id"], "10000.00", "s06-z-cash")
    assert first.status_code == 201
    second = authed_client.post(
        f"/api/v1/billing/invoices/{checked_in['invoice_id']}/payments/",
        {
            "amount": "5000.00",
            "method": "MOBILE_MONEY",
            "reference": "S06-MM-1",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s06-z-mobile",
    )
    assert second.status_code == 201
    reversed_response = authed_client.post(
        f"/api/v1/billing/payments/{first.data['id']}/reverse/",
        {"reason": "Synthetic Z reversal"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s06-z-reverse",
    )
    assert reversed_response.status_code == 200

    report = authed_client.get(f"/api/v1/billing/shifts/{shift['id']}/z-report/")
    assert report.status_code == 200, report.data
    assert report.data["payment_count"] == 1
    assert report.data["reversed_count"] == 1
    assert {tender["method"] for tender in report.data["tenders"]} == {"MOBILE_MONEY_MANUAL"}
    assert report.data["tenders"][0]["amount"] == "5000.00"
    assert report.data["opening_float"] == "5000.00"

    closed = authed_client.post(
        f"/api/v1/billing/shifts/{shift['id']}/close/",
        {"declared_cash": "4000.00", "reason": "Synthetic Z close"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s06-z-close",
    )
    assert closed.status_code == 200
    report = authed_client.get(f"/api/v1/billing/shifts/{shift['id']}/z-report/")
    assert report.data["expected_cash"] == "5000.00"
    assert report.data["variance"] == "-1000.00"
    assert report.data["variance_reason"] == "Synthetic Z close"
