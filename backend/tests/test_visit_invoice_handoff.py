"""Bounded clinic handoff: the signed consultation pays the check-in invoice.

The ordinary outpatient journey issues one consultation Invoice at check-in.
The signed consultation opens that same Invoice, the cashier pays it, and the
receipt names it. A generic invoice-create request for a Visit-linked Encounter
is refused instead of adding a second consultation charge.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import models as django_models
from rest_framework.test import APIClient

from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from audit.models import AuditEvent
from billing.models import Invoice, InvoiceItem, Payment, PaymentAllocation
from billing.services import create_invoice
from clinical.models import Encounter
from core.errors import CanonicalError
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import Visit
from tenancy.models import Department, Facility, Organisation
from tests.clinical_test_helpers import (
    establish_synthetic_final_diagnosis,
    establish_synthetic_nka_review,
    note_headers,
)


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def s01_target_cutover(enabled_mig001_target):
    """Canonical reception routes are gated by the S-01 cutover."""

    return enabled_mig001_target


def registration_payload(**overrides):
    payload = {
        "first_name": "Handoff",
        "last_name": "Patient",
        "sex": "FEMALE",
        "date_of_birth": "1991-02-03",
        "phone": "0700000001",
        "village": "Kisenyi",
        "parish": "Central",
        "sub_county": "Kampala",
        "district": "Kampala",
    }
    payload.update(overrides)
    return payload


def register(client, key, **overrides):
    payload = registration_payload()
    # Each synthetic patient must be distinct or registration resolves a duplicate.
    payload["last_name"] = "Handoff" + uuid4().hex[:8]
    payload.update(overrides)
    response = client.post(
        "/api/v1/reception/patients/register/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert response.status_code == 201, response.data
    return response.data["patient_id"]


def check_in(client, patient_id, tenant, key, **overrides):
    payload = {
        "patient_id": str(patient_id),
        "visit_type": "OUTPATIENT_NEW",
        "payer_type": "CASH",
        "department_id": str(tenant.department.id),
    }
    payload.update(overrides)
    response = client.post(
        "/api/v1/reception/visits/check-in/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert response.status_code == 201, response.data
    return response.data


def signed_encounter_for(client, queue_id):
    """Start and sign the consultation that belongs to a canonical check-in."""

    created = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": str(queue_id)},
        format="json",
    )
    assert created.status_code == 201, created.data
    encounter_id = created.data["id"]
    assert created.data["visit"], "A canonical encounter must carry its Visit."
    establish_synthetic_nka_review(client, encounter_id)
    establish_synthetic_final_diagnosis(client, encounter_id)
    signed = client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {
            "content": {"assessment": "Stable", "plan": "Hydration"},
            "complaints": [
                {
                    "text": "Synthetic handoff complaint",
                    "duration_value": None,
                    "duration_unit": None,
                }
            ],
        },
        **note_headers(client, encounter_id),
        format="json",
    )
    assert signed.status_code == 200, signed.data
    with tenant_atomic(Encounter.objects.get(id=encounter_id).organisation_id):
        assert Encounter.objects.get(id=encounter_id).status == "SIGNED"
    return encounter_id


def invoice_create_payload(patient_id, encounter_id, service_id):
    return {
        "patient_id": str(patient_id),
        "encounter_id": str(encounter_id),
        "items": [{"service_id": str(service_id), "quantity": "1"}],
    }


def visit_invoice_url(visit_id):
    return f"/api/v1/billing/invoices/by-visit/{visit_id}/"


def create_billing_user(tenant, username, template_code, *, facility=None):
    user = User.objects.create_user(username, "test-password-123")
    with tenant_atomic(tenant.organisation.id):
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=user)
        role = Role.objects.get(organisation=tenant.organisation, template_code=template_code)
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=user,
            role=role,
            facility=facility or tenant.facility,
        )
    return user


def login_as(user, organisation, facility):
    client = APIClient()
    response = client.post(
        "/api/v1/auth/login/",
        {
            "username": user.username,
            "password": "test-password-123",
            "organisation_id": str(organisation.id),
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access_token"])
    client.defaults["HTTP_X_FACILITY_ID"] = str(facility.id)
    return client


def test_signed_consultation_refuses_a_second_invoice_for_the_visit(tenant, authed_client):
    patient_id = register(authed_client, "handoff-register-refusal")
    checked_in = check_in(authed_client, patient_id, tenant, "handoff-checkin-refusal")
    visit_id = checked_in["visit_id"]
    invoice_id = checked_in["invoice_id"]
    assert invoice_id is not None

    with tenant_atomic(tenant.organisation.id):
        original = Invoice.objects.get(id=invoice_id)
        original_number = original.invoice_no
        assert original.visit_id == Visit.objects.get(id=visit_id).id
        assert original.items.filter(source_type="CONSULTATION", state="ACTIVE").count() == 1

    encounter_id = signed_encounter_for(authed_client, checked_in["queue_id"])

    # The service refuses before pricing, invoice creation, lines, or audit.
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        encounter = Encounter.objects.get(id=encounter_id)
        with pytest.raises(CanonicalError) as refused:
            create_invoice(
                organisation=organisation,
                facility=facility,
                actor=actor,
                patient_id=Patient.objects.get(id=patient_id).id,
                encounter_id=encounter.id,
                items=[{"service_id": str(tenant.service.id), "quantity": "1"}],
            )
        assert refused.value.code == "VISIT_INVOICE_REQUIRED"
        assert refused.value.status_code == 409

    payload = invoice_create_payload(patient_id, encounter_id, tenant.service.id)
    for attempt in range(2):
        response = authed_client.post(
            "/api/v1/billing/invoices/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=f"handoff-duplicate-{attempt}",
        )
        assert response.status_code == 409, response.data
        assert response.data["code"] == "VISIT_INVOICE_REQUIRED"
        assert response.data["detail"] == "Use the invoice for this Visit."

    with tenant_atomic(tenant.organisation.id):
        linked = Invoice.objects.filter(
            django_models.Q(patient_id=patient_id)
            | django_models.Q(visit_id=visit_id)
            | django_models.Q(encounter_id=encounter_id)
        )
        assert linked.count() == 1
        assert list(linked.values_list("id", flat=True)) == [original.id]
        assert Invoice.objects.filter(encounter_id=encounter_id).count() == 0
        assert InvoiceItem.objects.filter(source_type="CONSULTATION", state="ACTIVE").count() == 1
        assert Payment.objects.count() == 0
        assert PaymentAllocation.objects.count() == 0
        assert not AuditEvent.objects.filter(
            event_code="CREATE", entity_type="Invoice"
        ).exists()
        assert AuditEvent.objects.filter(
            event_code="INVOICE_ISSUED", entity_id=invoice_id
        ).count() == 1
        assert Invoice.objects.get(id=invoice_id).invoice_no == original_number


def test_visit_invoice_read_returns_the_check_in_invoice(tenant, authed_client):
    patient_id = register(authed_client, "handoff-register-read")
    checked_in = check_in(authed_client, patient_id, tenant, "handoff-checkin-read")
    visit_id = checked_in["visit_id"]
    invoice_id = checked_in["invoice_id"]

    response = authed_client.get(visit_invoice_url(visit_id))
    assert response.status_code == 200, response.data
    assert str(response.data["id"]) == invoice_id
    assert str(response.data["visit"]) == visit_id
    assert response.data["status"] == "ISSUED"
    active_lines = [line for line in response.data["items"] if line["state"] == "ACTIVE"]
    assert len(active_lines) == 1
    assert active_lines[0]["source_type"] == "CONSULTATION"
    assert str(active_lines[0]["source_id"]) == visit_id
    with tenant_atomic(tenant.organisation.id):
        invoice = Invoice.objects.get(id=invoice_id)
        invoice_number = invoice.invoice_no
        assert invoice.total == Decimal("30000.00")

    paid = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay/",
        {"amount": "30000.00", "method": "CASH"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="handoff-read-pay",
    )
    assert paid.status_code == 201, paid.data
    settled = authed_client.get(visit_invoice_url(visit_id))
    assert settled.status_code == 200, settled.data
    assert str(settled.data["id"]) == invoice_id
    assert settled.data["invoice_no"] == invoice_number
    assert settled.data["status"] == "PAID"
    assert settled.data["balance"] == "0.00"


def test_visit_invoice_read_is_scoped_to_tenant_facility_and_role(tenant, authed_client):
    patient_id = register(authed_client, "handoff-register-scope")
    checked_in = check_in(authed_client, patient_id, tenant, "handoff-checkin-scope")
    visit_id = checked_in["visit_id"]
    invoice_id = checked_in["invoice_id"]

    # A real billing role may read the invoice for the Visit.
    cashier = create_billing_user(tenant, "handoff-cashier", "RECEPTION_CASHIER")
    cashier_client = login_as(cashier, tenant.organisation, tenant.facility)
    allowed = cashier_client.get(visit_invoice_url(visit_id))
    assert allowed.status_code == 200, allowed.data
    assert str(allowed.data["id"]) == invoice_id

    # A role without the billing capability is refused outright.
    clinician = create_billing_user(tenant, "handoff-clinician", "CLINICIAN")
    clinician_client = login_as(clinician, tenant.organisation, tenant.facility)
    denied = clinician_client.get(visit_invoice_url(visit_id))
    assert denied.status_code == 403

    # Another facility in the same organisation cannot see the invoice.
    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="Handoff Other Facility",
            code="HANDOFF-OTHER",
            mode="CLINIC",
        )
        Department.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            name="Other OPD",
            code="OPD",
        )
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=cashier,
            role=Role.objects.get(
                organisation=tenant.organisation, template_code="RECEPTION_CASHIER"
            ),
            facility=other_facility,
        )
    cross_facility = cashier_client.get(
        visit_invoice_url(visit_id), HTTP_X_FACILITY_ID=str(other_facility.id)
    )
    assert cross_facility.status_code == 404

    # Another organisation cannot see the invoice even with its own Visit id.
    other_org = Organisation.objects.create(
        name="Handoff Other Clinic", slug="handoff-other-clinic"
    )
    with tenant_atomic(tenant.organisation.id):
        visit_service_date = Visit.objects.get(id=visit_id).local_service_date
    with tenant_atomic(other_org.id):
        other_org_facility = Facility.objects.create(
            organisation=other_org, name="Other Clinic Main", code="MAIN", mode="CLINIC"
        )
        other_actor = User.objects.create_user("handoff-other-owner", "test-password-123")
        other_patient = Patient.objects.create(
            organisation=other_org,
            patient_no="P-HANDOFF-OTHER",
            first_name="Other",
            last_name="Tenant",
            sex="UNKNOWN",
        )
        other_visit = Visit.objects.create(
            organisation=other_org,
            facility=other_org_facility,
            patient=other_patient,
            local_service_date=visit_service_date,
            visit_type="OUTPATIENT_NEW",
            opened_by=other_actor,
        )
        other_invoice = Invoice.objects.create(
            organisation=other_org,
            facility=other_org_facility,
            invoice_no="INV-HANDOFF-OTHER-000001",
            patient=other_patient,
            visit=other_visit,
            status="ISSUED",
            total=Decimal("30000.00"),
            balance=Decimal("30000.00"),
            created_by=other_actor,
        )
    foreign = authed_client.get(visit_invoice_url(other_visit.id))
    assert foreign.status_code == 404
    assert str(other_invoice.id) != invoice_id


def test_visit_invoice_read_returns_404_for_missing_and_voided_invoice(tenant, authed_client):
    missing = authed_client.get(visit_invoice_url(uuid4()))
    assert missing.status_code == 404

    patient_id = register(authed_client, "handoff-register-void")
    checked_in = check_in(authed_client, patient_id, tenant, "handoff-checkin-void")
    visit_id = checked_in["visit_id"]
    with tenant_atomic(tenant.organisation.id):
        visit_version = Visit.objects.get(id=visit_id).version
    cancelled = authed_client.post(
        f"/api/v1/reception/visits/{visit_id}/cancel-error/",
        {"reason": "Synthetic erroneous check-in", "expected_version": visit_version},
        format="json",
        HTTP_IDEMPOTENCY_KEY="handoff-cancel-error",
    )
    assert cancelled.status_code == 200, cancelled.data
    with tenant_atomic(tenant.organisation.id):
        assert Invoice.objects.get(id=checked_in["invoice_id"]).status == "VOIDED"
    voided = authed_client.get(visit_invoice_url(visit_id))
    assert voided.status_code == 404


def test_payment_posts_to_the_original_visit_invoice(tenant, authed_client):
    patient_id = register(authed_client, "handoff-register-pay")
    checked_in = check_in(authed_client, patient_id, tenant, "handoff-checkin-pay")
    visit_id = checked_in["visit_id"]
    invoice_id = checked_in["invoice_id"]
    with tenant_atomic(tenant.organisation.id):
        invoice_number = Invoice.objects.get(id=invoice_id).invoice_no

    paid = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay/",
        {"amount": "30000.00", "method": "CASH", "reference": "SYNTHETIC-REF"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="handoff-pay-original",
    )
    assert paid.status_code == 201, paid.data
    payment_id = paid.data["id"]

    receipt = authed_client.get(f"/api/v1/billing/invoices/{invoice_id}/receipt/")
    assert receipt.status_code == 200, receipt.data
    assert receipt.data["invoice_no"] == invoice_number
    assert receipt.data["amount"] == "30000.00"
    assert receipt.data["invoice_balance"] == "0.00"

    with tenant_atomic(tenant.organisation.id):
        invoice = Invoice.objects.get(id=invoice_id)
        assert invoice.status == "PAID"
        assert invoice.balance == Decimal("0.00")
        assert invoice.amount_paid == Decimal("30000.00")
        allocation = PaymentAllocation.objects.get(payment_id=payment_id)
        assert allocation.invoice_id == invoice.id
        assert allocation.amount == Decimal("30000.00")
        event = AuditEvent.objects.get(
            event_code="PAYMENT", entity_type="Payment", entity_id=str(payment_id)
        )
        assert event.action == "PAYMENT"
        assert event.after["invoice_id"] == str(invoice.id)
        assert event.after["receipt_no"] == paid.data["receipt_no"]
        assert event.after["method"] == "CASH"
        assert "amount" not in event.after

    repeated = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay/",
        {"amount": "30000.00", "method": "CASH"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="handoff-pay-repeat",
    )
    assert repeated.status_code == 400
    with tenant_atomic(tenant.organisation.id):
        assert Payment.objects.filter(invoice_id=invoice_id).count() == 1
        assert PaymentAllocation.objects.filter(invoice_id=invoice_id).count() == 1
        assert AuditEvent.objects.filter(event_code="PAYMENT", entity_type="Payment").count() == 1

    # A voided invoice refuses payment and records nothing.
    second_patient = register(authed_client, "handoff-register-pay-void", phone="0700000002")
    second = check_in(authed_client, second_patient, tenant, "handoff-checkin-pay-void")
    with tenant_atomic(tenant.organisation.id):
        second_version = Visit.objects.get(id=second["visit_id"]).version
    cancelled = authed_client.post(
        f"/api/v1/reception/visits/{second['visit_id']}/cancel-error/",
        {"reason": "Synthetic erroneous check-in", "expected_version": second_version},
        format="json",
        HTTP_IDEMPOTENCY_KEY="handoff-cancel-error-pay",
    )
    assert cancelled.status_code == 200, cancelled.data
    refused = authed_client.post(
        f"/api/v1/billing/invoices/{second['invoice_id']}/pay/",
        {"amount": "30000.00", "method": "CASH"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="handoff-pay-voided",
    )
    assert refused.status_code == 400
    with tenant_atomic(tenant.organisation.id):
        assert not Payment.objects.filter(invoice_id=second["invoice_id"]).exists()
        assert not PaymentAllocation.objects.filter(invoice_id=second["invoice_id"]).exists()
        assert AuditEvent.objects.filter(event_code="PAYMENT", entity_type="Payment").count() == 1
        assert Invoice.objects.get(id=second["invoice_id"]).status == "VOIDED"
        assert Invoice.objects.get(id=second["invoice_id"]).amount_paid == Decimal("0.00")
