from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from clinical.models import ClinicalNoteVersion, Encounter
from core.services import tenant_atomic
from patients.models import Patient
from tenancy.models import Facility, Organisation

import pytest

pytestmark = pytest.mark.django_db


def test_health_is_public():
    from rest_framework.test import APIClient

    response = APIClient().get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_full_patient_to_receipt_slice(tenant, authed_client):
    patient_response = authed_client.post(
        "/api/v1/patients/",
        {"first_name": "Amina", "last_name": "Nabirye", "sex": "FEMALE", "phone": "0700000000"},
        format="json",
    )
    assert patient_response.status_code == 201
    patient_id = patient_response.data["id"]
    check_in = authed_client.post(
        "/api/v1/clinic/check-ins/",
        {"patient_id": patient_id, "department_id": str(tenant.department.id)},
        format="json",
    )
    assert check_in.status_code == 201
    queue_id = check_in.data["id"]
    assert authed_client.post(f"/api/v1/clinic/queue/{queue_id}/claim/", {}, format="json").status_code == 200
    triage = authed_client.post(
        f"/api/v1/clinic/triage/{queue_id}/",
        {"acuity": "ROUTINE", "chief_complaint": "Headache", "vitals": {"pulse": 72}},
        format="json",
    )
    assert triage.status_code == 201
    encounter_response = authed_client.post(
        "/api/v1/clinic/encounters/", {"queue_entry_id": queue_id}, format="json"
    )
    assert encounter_response.status_code == 201
    encounter_id = encounter_response.data["id"]
    sign = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"assessment": "Stable", "plan": "Hydration"}},
        format="json",
    )
    assert sign.status_code == 200
    assert Encounter.objects.get(id=encounter_id).status == "SIGNED"
    invoice = authed_client.post(
        "/api/v1/billing/invoices/",
        {
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "items": [{"service_id": str(tenant.service.id), "quantity": "1"}],
        },
        format="json",
    )
    assert invoice.status_code == 201
    invoice_id = invoice.data["id"]
    assert invoice.data["balance"] == "30000.00"
    payment = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay/",
        {"amount": "30000.00", "method": "CASH"},
        format="json",
    )
    assert payment.status_code == 201
    receipt = authed_client.get(f"/api/v1/billing/invoices/{invoice_id}/receipt/")
    assert receipt.status_code == 200
    assert receipt.data["amount"] == "30000.00"
    assert receipt.data["invoice_balance"] == "0.00"


def test_tenant_boundary_returns_404(tenant, authed_client):
    other_org = Organisation.objects.create(name="Other Clinic", slug="other-clinic")
    with tenant_atomic(other_org.id):
        other_facility = Facility.objects.create(
            organisation=other_org, name="Other Facility", code="MAIN", mode="CLINIC"
        )
        other_patient = Patient.objects.create(
            organisation=other_org,
            patient_no="P-OTHER",
            first_name="Other",
            last_name="Tenant",
            sex="UNKNOWN",
        )
    assert other_facility.organisation_id == other_org.id
    assert authed_client.get(f"/api/v1/patients/{other_patient.id}/").status_code == 404


def test_capability_is_server_enforced(tenant):
    nurse = User.objects.create_user("nurse", "test-password-123")
    with tenant_atomic(tenant.organisation.id):
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=nurse)
        role = Role.objects.get(organisation=tenant.organisation, template_code="NURSE_TRIAGE")
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=nurse,
            role=role,
            facility=tenant.facility,
            department=tenant.department,
        )
    from rest_framework.test import APIClient

    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {
            "username": "nurse",
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + login.data["access_token"],
        HTTP_X_FACILITY_ID=str(tenant.facility.id),
    )
    response = client.post(
        "/api/v1/patients/",
        {"first_name": "Blocked", "last_name": "Create", "sex": "UNKNOWN"},
        format="json",
    )
    assert response.status_code == 403


def test_signed_note_is_immutable(tenant, authed_client):
    patient = authed_client.post(
        "/api/v1/patients/",
        {"first_name": "Immutable", "last_name": "Note", "sex": "UNKNOWN"},
        format="json",
    ).data
    queue = authed_client.post(
        "/api/v1/clinic/check-ins/",
        {"patient_id": patient["id"], "department_id": str(tenant.department.id)},
        format="json",
    ).data
    encounter = authed_client.post(
        "/api/v1/clinic/encounters/", {"queue_entry_id": queue["id"]}, format="json"
    ).data
    encounter_id = encounter["id"]
    assert authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"assessment": "First"}},
        format="json",
    ).status_code == 200
    rejected = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"assessment": "Overwrite"}},
        format="json",
    )
    assert rejected.status_code == 400
    assert ClinicalNoteVersion.objects.filter(note__encounter_id=encounter_id).count() == 1
