"""S-05 cashier, allocations, receipt identity, reversal and shift proofs."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from rest_framework.test import APIClient

from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from accounts.services import ensure_default_permissions
from audit.models import AuditEvent
from billing.models import (
    CashierShift,
    Invoice,
    InvoiceItem,
    Payment,
    PaymentAllocation,
    PaymentMethodConfig,
    PaymentReceipt,
)
from billing.services import create_invoice
from core.clock import local_service_date
from core.services import tenant_atomic
from tenancy.models import Department, Facility, Organisation


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def s01_target_cutover(enabled_mig001_target):
    return enabled_mig001_target


def register(client, key):
    response = client.post(
        "/api/v1/reception/patients/register/",
        {
            "first_name": "Cashier",
            "last_name": "Synthetic" + uuid4().hex[:8],
            "sex": "FEMALE",
            "date_of_birth": "1992-04-05",
            "phone": "07" + str(uuid4().int)[:8],
            "village": "Kisenyi",
            "parish": "Central",
            "sub_county": "Kampala",
            "district": "Kampala",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert response.status_code == 201, response.data
    return response.data["patient_id"]


def check_in(client, patient_id, tenant, key):
    response = client.post(
        "/api/v1/reception/visits/check-in/",
        {
            "patient_id": str(patient_id),
            "visit_type": "OUTPATIENT_NEW",
            "payer_type": "CASH",
            "department_id": str(tenant.department.id),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert response.status_code == 201, response.data
    return response.data


def open_shift(client, opening_float="0.00"):
    response = client.post(
        "/api/v1/billing/shifts/open/",
        {"opening_float": opening_float},
        format="json",
    )
    assert response.status_code == 201, response.data
    return response.data


def pay(client, invoice_id, amount, key, **overrides):
    payload = {"amount": amount, "method": "CASH"}
    payload.update(overrides)
    return client.post(
        f"/api/v1/billing/invoices/{invoice_id}/payments/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def test_s05_shift_bound_payment_has_exact_receipt_and_safe_replay(tenant, authed_client):
    patient_id = register(authed_client, "s05-register-receipt")
    checked_in = check_in(authed_client, patient_id, tenant, "s05-checkin-receipt")
    invoice_id = checked_in["invoice_id"]

    refused = pay(authed_client, invoice_id, "10000.00", "s05-pay-no-shift")
    assert refused.status_code == 409
    assert refused.data["code"] == "OPEN_SHIFT_REQUIRED"

    shift = open_shift(authed_client, "5000.00")
    assert shift["status"] == "OPEN"

    partial = pay(authed_client, invoice_id, "10000.00", "s05-pay-partial")
    assert partial.status_code == 201, partial.data
    payment_id = partial.data["id"]
    receipt_id = partial.data["receipt_id"]
    assert partial.data["status"] == "CONFIRMED"
    assert partial.data["allocations"] == [
        {"invoice_id": invoice_id, "amount": "10000.00"}
    ]
    assert partial.data["invoices"][0]["status"] == "PARTIALLY_PAID"
    assert partial.data["invoices"][0]["balance"] == "20000.00"

    with tenant_atomic(tenant.organisation.id):
        invoice = Invoice.objects.get(id=invoice_id)
        assert invoice.amount_paid == Decimal("10000.00")
        assert invoice.balance == Decimal("20000.00")
        assert Payment.objects.get(id=payment_id).shift_id == UUID(shift["id"])
        receipt = PaymentReceipt.objects.get(id=receipt_id)
        assert str(receipt.payment_id) == payment_id
        assert len(receipt.content_hash) == 64

    fetched = authed_client.get(f"/api/v1/billing/receipts/{receipt_id}/")
    assert fetched.status_code == 200, fetched.data
    assert fetched.data["receipt_no"] == partial.data["receipt_no"]
    assert fetched.data["amount"] == "10000.00"
    assert fetched.data["invoice_balance"] == "20000.00"

    replayed = pay(authed_client, invoice_id, "10000.00", "s05-pay-partial")
    assert replayed.status_code == 201
    assert replayed.headers["Idempotent-Replay"] == "true"
    assert replayed.data["id"] == payment_id
    with tenant_atomic(tenant.organisation.id):
        assert Payment.objects.filter(invoice_id=invoice_id).count() == 1
        assert PaymentReceipt.objects.filter(payment_id=payment_id).count() == 1

    settled = pay(authed_client, invoice_id, "20000.00", "s05-pay-final")
    assert settled.status_code == 201, settled.data
    assert settled.data["invoices"][0]["status"] == "PAID"
    assert settled.data["invoices"][0]["balance"] == "0.00"
    assert settled.data["receipt_id"] != receipt_id

    # The first receipt remains addressable by its exact identity, not "newest".
    first_again = authed_client.get(
        f"/api/v1/billing/invoices/{invoice_id}/receipt/",
        {"receipt_id": receipt_id},
    )
    assert first_again.status_code == 200
    assert first_again.data["id"] == receipt_id
    assert first_again.data["amount"] == "10000.00"


def test_s05_two_invoice_allocation_and_scope_refusals(tenant, authed_client):
    patient_id = register(authed_client, "s05-register-split")
    first = check_in(authed_client, patient_id, tenant, "s05-checkin-split")
    with tenant_atomic(tenant.organisation.id):
        second = create_invoice(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            patient_id=patient_id,
            items=[{"service_id": str(tenant.service.id), "quantity": "1"}],
        )
        second_id = str(second.id)
    open_shift(authed_client)

    mismatch = authed_client.post(
        f"/api/v1/billing/invoices/{first['invoice_id']}/payments/",
        {
            "amount": "60000.00",
            "method": "CASH",
            "allocations": [
                {"invoice_id": first["invoice_id"], "amount": "20000.00"},
                {"invoice_id": second_id, "amount": "20000.00"},
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-split-mismatch",
    )
    assert mismatch.status_code == 400
    assert mismatch.data["code"] == "PAYMENT_ALLOCATION_MISMATCH"

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
        HTTP_IDEMPOTENCY_KEY="s05-split-ok",
    )
    assert split.status_code == 201, split.data
    assert sorted(item["invoice_id"] for item in split.data["allocations"]) == sorted(
        [first["invoice_id"], second_id]
    )
    with tenant_atomic(tenant.organisation.id):
        payment = Payment.objects.get(id=split.data["id"])
        assert payment.invoice_id is None
        assert PaymentAllocation.objects.filter(payment=payment).count() == 2
        assert Invoice.objects.get(id=first["invoice_id"]).status == "PAID"
        assert Invoice.objects.get(id=second_id).status == "PAID"

    other_patient = register(authed_client, "s05-register-other")
    other = check_in(authed_client, other_patient, tenant, "s05-checkin-other")
    with tenant_atomic(tenant.organisation.id):
        fresh = create_invoice(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            patient_id=patient_id,
            items=[{"service_id": str(tenant.service.id), "quantity": "1"}],
        )
        fresh_id = str(fresh.id)
    cross_patient = authed_client.post(
        f"/api/v1/billing/invoices/{fresh_id}/payments/",
        {
            "amount": "60000.00",
            "method": "CASH",
            "allocations": [
                {"invoice_id": fresh_id, "amount": "30000.00"},
                {"invoice_id": other["invoice_id"], "amount": "30000.00"},
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-split-cross-patient",
    )
    assert cross_patient.status_code == 409
    assert cross_patient.data["code"] == "PAYMENT_ALLOCATION_PATIENT_MISMATCH"


def test_s05_reversal_preserves_evidence_and_unrelated_invoice(tenant, authed_client):
    paid_patient = register(authed_client, "s05-register-reverse")
    paid_visit = check_in(authed_client, paid_patient, tenant, "s05-checkin-reverse")
    other_patient = register(authed_client, "s05-register-unrelated")
    other_visit = check_in(authed_client, other_patient, tenant, "s05-checkin-unrelated")
    open_shift(authed_client)

    paid = pay(authed_client, paid_visit["invoice_id"], "15000.00", "s05-pay-reverse")
    assert paid.status_code == 201
    other = pay(authed_client, other_visit["invoice_id"], "5000.00", "s05-pay-unrelated")
    assert other.status_code == 201

    missing_reason = authed_client.post(
        f"/api/v1/billing/payments/{paid.data['id']}/reverse/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-reverse-no-reason",
    )
    assert missing_reason.status_code == 400
    assert missing_reason.data["code"] == "PAYMENT_REVERSAL_REASON_REQUIRED"

    reversed_response = authed_client.post(
        f"/api/v1/billing/payments/{paid.data['id']}/reverse/",
        {"reason": "Synthetic wrong tender"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-reverse-ok",
    )
    assert reversed_response.status_code == 200, reversed_response.data
    assert reversed_response.data["status"] == "REVERSED"
    assert reversed_response.data["invoices"][0]["balance"] == "30000.00"

    with tenant_atomic(tenant.organisation.id):
        payment = Payment.objects.get(id=paid.data["id"])
        assert payment.status == "REVERSED"
        assert payment.reversal_reason_hash
        assert PaymentAllocation.objects.filter(payment=payment).count() == 1
        assert PaymentReceipt.objects.filter(payment=payment).count() == 1
        reversed_invoice = Invoice.objects.get(id=paid_visit["invoice_id"])
        assert reversed_invoice.status == "ISSUED"
        assert reversed_invoice.balance == Decimal("30000.00")
        assert reversed_invoice.amount_paid == Decimal("0.00")
        unrelated = Invoice.objects.get(id=other_visit["invoice_id"])
        assert unrelated.status == "PARTIALLY_PAID"
        assert unrelated.balance == Decimal("25000.00")
        assert AuditEvent.objects.filter(
            event_code="PAYMENT_REVERSED", entity_id=str(payment.id)
        ).count() == 1

    # A reversed receipt is not presentable as current, and the payment is not
    # reversible twice.
    reprint = authed_client.post(
        f"/api/v1/billing/receipts/{paid.data['receipt_id']}/reprint/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-reprint-reversed",
    )
    assert reprint.status_code == 409
    twice = authed_client.post(
        f"/api/v1/billing/payments/{paid.data['id']}/reverse/",
        {"reason": "Synthetic repeated reversal"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-reverse-twice",
    )
    assert twice.status_code == 409
    assert twice.data["code"] == "PAYMENT_ALREADY_REVERSED"


def test_s05_blind_shift_close_and_serialized_close(tenant, authed_client):
    patient_id = register(authed_client, "s05-register-shift")
    checked_in = check_in(authed_client, patient_id, tenant, "s05-checkin-shift")
    shift = open_shift(authed_client, "5000.00")
    paid = pay(authed_client, checked_in["invoice_id"], "10000.00", "s05-pay-shift")
    assert paid.status_code == 201

    current = authed_client.get("/api/v1/billing/shifts/current/")
    assert current.status_code == 200
    assert current.data["shift"]["id"] == shift["id"]

    closed = authed_client.post(
        f"/api/v1/billing/shifts/{shift['id']}/close/",
        {"declared_cash": "14000.00", "reason": "Synthetic close"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-shift-close",
    )
    assert closed.status_code == 200, closed.data
    assert closed.data["status"] == "CLOSED"
    assert closed.data["expected_cash"] == "15000.00"
    assert closed.data["variance"] == "-1000.00"
    assert closed.data["declared_cash"] == "14000.00"
    after_close = authed_client.get("/api/v1/billing/shifts/current/")
    assert after_close.status_code == 200, after_close.data
    assert after_close.data["shift"] is None
    assert after_close.data["last_closed_shift"]["id"] == shift["id"]
    assert after_close.data["last_closed_shift"]["expected_cash"] == "15000.00"
    assert after_close.data["last_closed_shift"]["variance"] == "-1000.00"

    again = authed_client.post(
        f"/api/v1/billing/shifts/{shift['id']}/close/",
        {"declared_cash": "15000.00"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-shift-close-again",
    )
    assert again.status_code == 409
    refused_payment = pay(
        authed_client, checked_in["invoice_id"], "10000.00", "s05-pay-after-close"
    )
    assert refused_payment.status_code == 409
    assert refused_payment.data["code"] == "OPEN_SHIFT_REQUIRED"
    with tenant_atomic(tenant.organisation.id):
        assert CashierShift.objects.filter(status="OPEN").count() == 0
        assert AuditEvent.objects.filter(event_code="SHIFT_CLOSED").count() == 1


def test_s40_z_report_refuses_open_shift_before_any_projection(tenant, authed_client):
    """S-40 red: a blind close must not disclose Z-report totals."""

    patient_id = register(authed_client, "s40-register-blind")
    checked_in = check_in(authed_client, patient_id, tenant, "s40-checkin-blind")
    shift = open_shift(authed_client, "5000.00")
    paid = pay(authed_client, checked_in["invoice_id"], "10000.00", "s40-pay-blind")
    assert paid.status_code == 201

    report = authed_client.get(
        f"/api/v1/billing/shifts/{shift['id']}/z-report/"
    )
    assert report.status_code == 409, report.data
    assert report.data["code"] == "SHIFT_NOT_CLOSED"
    assert "tenders" not in report.data
    assert "expected_cash" not in report.data
    assert "10000.00" not in str(report.data)


def test_s05_payment_method_configuration_and_manual_reference(tenant, authed_client):
    options = authed_client.get("/api/v1/billing/payment-methods/")
    assert options.status_code == 200
    codes = {option["code"] for option in options.data}
    assert {"CASH", "MOBILE_MONEY_MANUAL"} <= codes

    patient_id = register(authed_client, "s05-register-method")
    checked_in = check_in(authed_client, patient_id, tenant, "s05-checkin-method")

    missing_reference = authed_client.post(
        f"/api/v1/billing/invoices/{checked_in['invoice_id']}/pay/",
        {"amount": "1000.00", "method": "MOBILE_MONEY"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-momo-no-reference",
    )
    assert missing_reference.status_code == 400
    assert missing_reference.data["code"] == "PAYMENT_REFERENCE_REQUIRED"

    with_reference = authed_client.post(
        f"/api/v1/billing/invoices/{checked_in['invoice_id']}/pay/",
        {"amount": "1000.00", "method": "MOBILE_MONEY", "reference": "SYNTH-MM-1"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-momo-reference",
    )
    assert with_reference.status_code == 201, with_reference.data
    assert with_reference.data["method"] == "MOBILE_MONEY_MANUAL"

    created = authed_client.post(
        "/api/v1/billing/payment-methods/",
        {
            "code": "BANK_DEPOSIT_SLIP",
            "label": "Bank deposit slip",
            "kind": "MANUAL",
            "reference_required": True,
        },
        format="json",
    )
    assert created.status_code == 201, created.data
    options = authed_client.get("/api/v1/billing/payment-methods/")
    custom = next(item for item in options.data if item["code"] == "BANK_DEPOSIT_SLIP")
    assert custom["reference_required"] is True

    missing = authed_client.post(
        f"/api/v1/billing/invoices/{checked_in['invoice_id']}/pay/",
        {"amount": "1000.00", "method": "BANK_DEPOSIT_SLIP"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-bank-no-reference",
    )
    assert missing.status_code == 400
    assert missing.data["code"] == "PAYMENT_REFERENCE_REQUIRED"

    deactivated = authed_client.post(
        "/api/v1/billing/payment-methods/",
        {
            "code": "BANK_DEPOSIT_SLIP",
            "label": "Bank deposit slip",
            "kind": "MANUAL",
            "reference_required": True,
            "is_active": False,
        },
        format="json",
    )
    assert deactivated.status_code == 201
    refused = authed_client.post(
        f"/api/v1/billing/invoices/{checked_in['invoice_id']}/pay/",
        {
            "amount": "1000.00",
            "method": "BANK_DEPOSIT_SLIP",
            "reference": "SLIP-1",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-bank-deactivated",
    )
    assert refused.status_code == 422
    assert refused.data["code"] == "PAYMENT_METHOD_NOT_CONFIGURED"
    with tenant_atomic(tenant.organisation.id):
        assert Payment.objects.filter(method="MOBILE_MONEY_MANUAL").count() == 1
        assert PaymentMethodConfig.objects.get(code="BANK_DEPOSIT_SLIP").is_active is False

    reserved = authed_client.post(
        "/api/v1/billing/payment-methods/",
        {"code": "CASH", "label": "Cash", "kind": "MANUAL"},
        format="json",
    )
    assert reserved.status_code == 409
    assert reserved.data["code"] == "PAYMENT_METHOD_RESERVED"


def test_s05_manual_line_and_void_protect_paid_invoices(tenant, authed_client):
    patient_id = register(authed_client, "s05-register-line")
    checked_in = check_in(authed_client, patient_id, tenant, "s05-checkin-line")
    invoice_id = checked_in["invoice_id"]

    manual = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/lines/",
        {
            "manual": True,
            "description": "Synthetic dressing",
            "quantity": "1.00",
            "amount": "5000.00",
            "reason": "Synthetic manual service",
        },
        format="json",
    )
    assert manual.status_code == 201, manual.data
    assert manual.data["total"] == "35000.00"
    assert manual.data["balance"] == "35000.00"
    detail = authed_client.get(f"/api/v1/billing/invoices/{invoice_id}/")
    assert detail.status_code == 200
    line = next(item for item in detail.data["items"] if item["source_type"] == "MANUAL")
    assert line["manual_reason"] == "Synthetic manual service"

    missing_reason = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/lines/",
        {"manual": True, "description": "Synthetic item", "amount": "1000.00"},
        format="json",
    )
    assert missing_reason.status_code == 400
    assert missing_reason.data["code"] == "MANUAL_LINE_EVIDENCE_REQUIRED"

    voided = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/lines/{line['id']}/void/",
        {"reason": "Synthetic line entered in error"},
        format="json",
    )
    assert voided.status_code == 200, voided.data
    assert voided.data["total"] == "30000.00"
    assert voided.data["balance"] == "30000.00"
    detail = authed_client.get(f"/api/v1/billing/invoices/{invoice_id}/")
    stored = next(item for item in detail.data["items"] if item["id"] == line["id"])
    assert stored["state"] == "VOIDED"
    assert stored["void_reason"] == "Synthetic line entered in error"
    assert stored["voided_by"]
    active_line = next(item for item in detail.data["items"] if item["state"] == "ACTIVE")

    open_shift(authed_client)
    paid = pay(authed_client, invoice_id, "10000.00", "s05-pay-line-guard")
    assert paid.status_code == 201
    refused = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/lines/{active_line['id']}/void/",
        {"reason": "Synthetic paid line"},
        format="json",
    )
    assert refused.status_code == 409
    assert refused.data["code"] == "PAID_LINE_VOID_REFUSED"
    with tenant_atomic(tenant.organisation.id):
        assert InvoiceItem.objects.get(id=line["id"]).state == "VOIDED"
        assert InvoiceItem.objects.filter(invoice_id=invoice_id, state="ACTIVE").count() == 1


def test_s05_catalogue_line_reopens_a_paid_invoice_with_audit(tenant, authed_client):
    patient_id = register(authed_client, "s05-register-catalogue")
    checked_in = check_in(authed_client, patient_id, tenant, "s05-checkin-catalogue")
    invoice_id = checked_in["invoice_id"]

    added = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/lines/",
        {"service_id": str(tenant.service.id), "quantity": "1.00"},
        format="json",
    )
    assert added.status_code == 201, added.data
    assert added.data["total"] == "60000.00"
    assert added.data["balance"] == "60000.00"

    open_shift(authed_client)
    paid = pay(authed_client, invoice_id, "60000.00", "s05-pay-catalogue")
    assert paid.status_code == 201
    assert paid.data["invoices"][0]["status"] == "PAID"

    reopened = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/lines/",
        {"service_id": str(tenant.service.id), "quantity": "1.00"},
        format="json",
    )
    assert reopened.status_code == 201, reopened.data
    assert reopened.data["status"] == "PARTIALLY_PAID"
    assert reopened.data["total"] == "90000.00"
    assert reopened.data["balance"] == "30000.00"
    with tenant_atomic(tenant.organisation.id):
        assert (
            AuditEvent.objects.filter(event_code="INVOICE_LINE_ADDED").count() == 2
        )
        assert InvoiceItem.objects.filter(invoice_id=invoice_id, state="ACTIVE").count() == 3


def test_s05_reprint_is_idempotent_and_audited(tenant, authed_client):
    patient_id = register(authed_client, "s05-register-reprint")
    checked_in = check_in(authed_client, patient_id, tenant, "s05-checkin-reprint")
    open_shift(authed_client)
    paid = pay(authed_client, checked_in["invoice_id"], "30000.00", "s05-pay-reprint")
    assert paid.status_code == 201

    first = authed_client.post(
        f"/api/v1/billing/receipts/{paid.data['receipt_id']}/reprint/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-reprint",
    )
    assert first.status_code == 200, first.data
    assert first.data["print_count"] == 1
    replay = authed_client.post(
        f"/api/v1/billing/receipts/{paid.data['receipt_id']}/reprint/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s05-reprint",
    )
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replay"] == "true"
    assert replay.data["print_count"] == 1
    with tenant_atomic(tenant.organisation.id):
        assert AuditEvent.objects.filter(event_code="RECEIPT_REPRINTED").count() == 1
        assert PaymentReceipt.objects.get(id=paid.data["receipt_id"]).print_count == 1


def test_s05_receipts_are_facility_scoped(tenant, authed_client):
    patient_id = register(authed_client, "s05-register-scope")
    checked_in = check_in(authed_client, patient_id, tenant, "s05-checkin-scope")
    open_shift(authed_client)
    paid = pay(authed_client, checked_in["invoice_id"], "30000.00", "s05-pay-scope")
    assert paid.status_code == 201

    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation, name="Other Facility", code="OTHER", mode="CLINIC"
        )
        other_facility_id = str(other_facility.id)
    other_client = APIClient()
    login = other_client.post(
        "/api/v1/auth/login/",
        {
            "username": tenant.user.username,
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    assert login.status_code == 200
    other_client.defaults["HTTP_X_FACILITY_ID"] = other_facility_id
    other_client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    hidden = other_client.get(f"/api/v1/billing/receipts/{paid.data['receipt_id']}/")
    assert hidden.status_code in {403, 404}


def _cashier_client(tenant, username, template, facility=None):
    facility = facility or tenant.facility
    with tenant_atomic(tenant.organisation.id):
        user = User.objects.create_user(username, "test-password-123")
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=user)
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=user,
            role=Role.objects.get(
                organisation=tenant.organisation, template_code=template
            ),
            facility=facility,
            department=tenant.department if facility == tenant.facility else None,
        )
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {
            "username": username,
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    assert login.status_code == 200
    client.defaults["HTTP_X_FACILITY_ID"] = str(facility.id)
    client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    return client


def test_s40_last_closed_shift_is_cashier_and_facility_scoped(tenant, authed_client):
    shift = open_shift(authed_client, "0.00")
    closed = authed_client.post(
        f"/api/v1/billing/shifts/{shift['id']}/close/",
        {"declared_cash": "0.00", "reason": "Synthetic scoped close"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s40-scoped-close",
    )
    assert closed.status_code == 200, closed.data

    other_cashier = _cashier_client(
        tenant, "s40-other-cashier", "OWNER_ADMIN", tenant.facility
    )
    other_view = other_cashier.get("/api/v1/billing/shifts/current/")
    assert other_view.status_code == 200, other_view.data
    assert other_view.data["shift"] is None
    assert other_view.data["last_closed_shift"] is None

    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="S40 Other Facility",
            code="S40-OTHER",
            mode="CLINIC",
        )
    facility_cashier = _cashier_client(
        tenant, "s40-facility-cashier", "OWNER_ADMIN", other_facility
    )
    facility_view = facility_cashier.get("/api/v1/billing/shifts/current/")
    assert facility_view.status_code == 200, facility_view.data
    assert facility_view.data["shift"] is None
    assert facility_view.data["last_closed_shift"] is None

    wrong_role = _cashier_client(tenant, "s40-nurse", "NURSE_TRIAGE", tenant.facility)
    denied = wrong_role.get("/api/v1/billing/shifts/current/")
    assert denied.status_code == 403
    assert "last_closed_shift" not in denied.data


def test_s40_last_closed_shift_does_not_cross_tenant(tenant, authed_client):
    shift = open_shift(authed_client, "0.00")
    closed = authed_client.post(
        f"/api/v1/billing/shifts/{shift['id']}/close/",
        {"declared_cash": "0.00"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s40-tenant-close",
    )
    assert closed.status_code == 200, closed.data

    with tenant_atomic(tenant.organisation.id):
        other_org = Organisation.objects.create(
            name="S40 Other Clinic", slug="s40-other-clinic"
        )
        ensure_default_permissions(other_org)
        other_facility = Facility.objects.create(
            organisation=other_org, name="Other Org Facility", code="S40-ORG", mode="CLINIC"
        )
        other_department = Department.objects.create(
            organisation=other_org, facility=other_facility, name="Outpatient", code="OPD"
        )
        user = User.objects.create_user("s40-other-org", "test-password-123")
        OrganisationMembership.objects.create(organisation=other_org, user=user)
        UserFacilityRole.objects.create(
            organisation=other_org,
            user=user,
            role=Role.objects.get(organisation=other_org, template_code="OWNER_ADMIN"),
            facility=other_facility,
            department=other_department,
        )
        other_org_id = str(other_org.id)
        other_facility_id = str(other_facility.id)

    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {
            "username": "s40-other-org",
            "password": "test-password-123",
            "organisation_id": other_org_id,
        },
        format="json",
    )
    assert login.status_code == 200
    client.defaults["HTTP_X_FACILITY_ID"] = other_facility_id
    client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    foreign = client.get("/api/v1/billing/shifts/current/")
    assert foreign.status_code == 200, foreign.data
    assert foreign.data["shift"] is None
    assert foreign.data["last_closed_shift"] is None
    assert shift["id"] not in str(foreign.data)


def test_s40_open_and_close_survive_lost_responses_without_duplicate_commands(
    tenant, authed_client
):
    first_open = authed_client.post(
        "/api/v1/billing/shifts/open/",
        {"opening_float": "1000.00"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s40-lost-open",
    )
    assert first_open.status_code == 201, first_open.data
    shift_id = first_open.data["id"]

    current = authed_client.get("/api/v1/billing/shifts/current/")
    assert current.status_code == 200, current.data
    assert current.data["shift"]["id"] == shift_id

    replayed_open = authed_client.post(
        "/api/v1/billing/shifts/open/",
        {"opening_float": "1000.00"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s40-lost-open",
    )
    assert replayed_open.status_code == 201, replayed_open.data
    assert replayed_open.headers["Idempotent-Replay"] == "true"
    assert replayed_open.data["id"] == shift_id

    first_close = authed_client.post(
        f"/api/v1/billing/shifts/{shift_id}/close/",
        {"declared_cash": "1000.00", "reason": "Synthetic lost-response close"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s40-lost-close",
    )
    assert first_close.status_code == 200, first_close.data
    expected = first_close.data["expected_cash"]

    replayed_close = authed_client.post(
        f"/api/v1/billing/shifts/{shift_id}/close/",
        {"declared_cash": "1000.00", "reason": "Synthetic lost-response close"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s40-lost-close",
    )
    assert replayed_close.status_code == 200, replayed_close.data
    assert replayed_close.headers["Idempotent-Replay"] == "true"
    assert replayed_close.data["id"] == shift_id
    assert replayed_close.data["expected_cash"] == expected

    refreshed = authed_client.get("/api/v1/billing/shifts/current/")
    assert refreshed.status_code == 200, refreshed.data
    assert refreshed.data["shift"] is None
    assert refreshed.data["last_closed_shift"]["id"] == shift_id
    with tenant_atomic(tenant.organisation.id):
        assert CashierShift.objects.count() == 1
        stored = CashierShift.objects.get(id=shift_id)
        assert stored.status == "CLOSED"
        assert stored.declared_cash == Decimal("1000.00")
        assert stored.expected_cash == Decimal(expected)
        assert AuditEvent.objects.filter(event_code="SHIFT_OPENED").count() == 1
        assert AuditEvent.objects.filter(event_code="SHIFT_CLOSED").count() == 1
