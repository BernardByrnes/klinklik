from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from billing.models import Invoice
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import QueueEntry
from tenancy.models import Department, Facility, Organisation

pytestmark = pytest.mark.django_db

NURSE_CAPABILITIES = {"patient.view", "queue.view", "queue.claim", "triage.record", "allergy.manage"}


def login_client(username, password, organisation_id, facility_id):
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {
            "username": username,
            "password": password,
            "organisation_id": str(organisation_id),
        },
        format="json",
    )
    assert login.status_code == 200, login.data
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + login.data["access_token"],
        HTTP_X_FACILITY_ID=str(facility_id),
    )
    return client, login.data


def grant_role(tenant, user, template_code):
    with tenant_atomic(tenant.organisation.id):
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=user)
        role = Role.objects.get(organisation=tenant.organisation, template_code=template_code)
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=user,
            role=role,
            facility=tenant.facility,
            department=tenant.department,
        )


def create_invoice_for(tenant, client, first_name, last_name):
    patient = client.post(
        "/api/v1/patients/",
        {"first_name": first_name, "last_name": last_name, "sex": "UNKNOWN"},
        format="json",
    ).data
    invoice = client.post(
        "/api/v1/billing/invoices/",
        {"patient_id": patient["id"], "items": [{"service_id": str(tenant.service.id), "quantity": "1"}]},
        format="json",
    )
    assert invoice.status_code == 201, invoice.data
    return invoice.data


def test_login_includes_roles_and_capabilities(tenant):
    client, session = login_client(
        tenant.user.username, "test-password-123", tenant.organisation.id, tenant.facility.id
    )
    templates = [role["template_code"] for role in session["roles"]]
    assert templates == ["OWNER_ADMIN"]
    owner_role = session["roles"][0]
    assert owner_role["facility"] == str(tenant.facility.id)
    assert owner_role["department"] == str(tenant.department.id)
    assert owner_role["department_code"] == "OPD"
    assert "billing.payment.record" in session["capabilities"]
    assert "staff.permission.grant" in session["capabilities"]
    assert len(session["capabilities"]) == 16


def test_me_includes_roles_and_capabilities(tenant):
    client, _ = login_client(
        tenant.user.username, "test-password-123", tenant.organisation.id, tenant.facility.id
    )
    me = client.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert [role["template_code"] for role in me.data["roles"]] == ["OWNER_ADMIN"]
    assert "patient.view" in me.data["capabilities"]


def test_capabilities_reflect_role_template(tenant):
    nurse = User.objects.create_user("triage-nurse", "test-password-123")
    grant_role(tenant, nurse, "NURSE_TRIAGE")
    _, session = login_client("triage-nurse", "test-password-123", tenant.organisation.id, tenant.facility.id)
    assert [role["template_code"] for role in session["roles"]] == ["NURSE_TRIAGE"]
    assert set(session["capabilities"]) == NURSE_CAPABILITIES


def test_expired_grant_is_excluded_from_session(tenant):
    from django.utils import timezone
    from datetime import timedelta

    temp_user = User.objects.create_user("temp-staff", "test-password-123")
    with tenant_atomic(tenant.organisation.id):
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=temp_user)
        role = Role.objects.get(organisation=tenant.organisation, template_code="RECEPTION_CASHIER")
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=temp_user,
            role=role,
            facility=tenant.facility,
            status="REVOKED",
            valid_until=timezone.now() - timedelta(days=1),
        )
    _, session = login_client("temp-staff", "test-password-123", tenant.organisation.id, tenant.facility.id)
    assert session["roles"] == []
    assert session["capabilities"] == []


def test_invoice_list_filters_by_status(tenant, authed_client):
    paid = create_invoice_for(tenant, authed_client, "Paid", "Invoice")
    partial = create_invoice_for(tenant, authed_client, "Partial", "Invoice")
    outstanding = create_invoice_for(tenant, authed_client, "Open", "Invoice")

    assert (
        authed_client.post(
            f"/api/v1/billing/invoices/{paid['id']}/pay/",
            {"amount": "30000.00", "method": "CASH"},
            format="json",
        ).status_code
        == 201
    )
    assert (
        authed_client.post(
            f"/api/v1/billing/invoices/{partial['id']}/pay/",
            {"amount": "10000.00", "method": "CASH"},
            format="json",
        ).status_code
        == 201
    )

    def invoice_nos(query):
        response = authed_client.get("/api/v1/billing/invoices/" + query)
        assert response.status_code == 200, response.data
        return {invoice["invoice_no"] for invoice in response.data}

    assert invoice_nos("?status=PAID") == {paid["invoice_no"]}
    assert invoice_nos("?status=PARTIALLY_PAID") == {partial["invoice_no"]}
    assert invoice_nos("?status=ISSUED") == {outstanding["invoice_no"]}
    assert invoice_nos("?status=ISSUED,PARTIALLY_PAID") == {partial["invoice_no"], outstanding["invoice_no"]}
    assert invoice_nos("?status=ISSUED&status=PAID") == {paid["invoice_no"], outstanding["invoice_no"]}
    assert invoice_nos("") == {paid["invoice_no"], partial["invoice_no"], outstanding["invoice_no"]}


def test_invoice_list_rejects_unknown_status(tenant, authed_client):
    response = authed_client.get("/api/v1/billing/invoices/?status=UNPAID")
    assert response.status_code == 400
    assert "UNPAID" in response.data["detail"]


def test_invoice_list_searches_by_invoice_and_patient(tenant, authed_client):
    invoice = create_invoice_for(tenant, authed_client, "Searchable", "Patientname")
    patient_no = Patient.objects.get(id=invoice["patient"]).patient_no

    def invoice_nos(query):
        response = authed_client.get("/api/v1/billing/invoices/" + query)
        assert response.status_code == 200, response.data
        return {item["invoice_no"] for item in response.data}

    assert invoice_nos(f"?q={invoice['invoice_no'][0:8]}") == {invoice["invoice_no"]}
    assert invoice_nos("?q=Patientname") == {invoice["invoice_no"]}
    assert invoice_nos("?q=searchable") == {invoice["invoice_no"]}
    assert invoice_nos(f"?q={patient_no}") == {invoice["invoice_no"]}
    assert invoice_nos("?q=no-such-thing") == set()
    assert invoice_nos(f"?status=ISSUED&q=Patientname") == {invoice["invoice_no"]}
    assert invoice_nos(f"?status=PAID&q=Patientname") == set()


def test_invoice_list_requires_billing_capability(tenant):
    nurse = User.objects.create_user("lookup-nurse", "test-password-123")
    grant_role(tenant, nurse, "NURSE_TRIAGE")
    client, _ = login_client("lookup-nurse", "test-password-123", tenant.organisation.id, tenant.facility.id)
    assert client.get("/api/v1/billing/invoices/").status_code == 403
    assert client.get("/api/v1/billing/invoices/?status=ISSUED&q=x").status_code == 403


def test_queue_status_filter_accepts_lists(tenant, authed_client):
    patients = []
    for index in range(3):
        patient = authed_client.post(
            "/api/v1/patients/",
            {"first_name": f"Queue{index}", "last_name": "Filter", "sex": "UNKNOWN"},
            format="json",
        ).data
        check_in = authed_client.post(
            "/api/v1/clinic/check-ins/",
            {"patient_id": patient["id"], "department_id": str(tenant.department.id)},
            format="json",
        )
        assert check_in.status_code == 201
        patients.append(check_in.data["id"])
    # Claim the second entry → CALLED.
    assert authed_client.post(f"/api/v1/clinic/queue/{patients[1]}/claim/", {}, format="json").status_code == 200

    def queue_ids(query):
        response = authed_client.get("/api/v1/clinic/queue/" + query)
        assert response.status_code == 200, response.data
        return {entry["id"] for entry in response.data}

    expected_all = set(patients)
    assert queue_ids("?status=WAITING") == {patients[0], patients[2]}
    assert queue_ids("?status=CALLED") == {patients[1]}
    assert queue_ids("?status=WAITING,CALLED") == expected_all
    assert queue_ids("?status=WAITING&status=CALLED") == expected_all
    assert queue_ids("?status=waiting") == {patients[0], patients[2]}
    assert queue_ids("") == expected_all

    rejected = authed_client.get("/api/v1/clinic/queue/?status=BOGUS")
    assert rejected.status_code == 400
    assert "BOGUS" in rejected.data["detail"]


def test_queue_list_is_tenant_scoped_including_multi_status_filter(tenant, authed_client):
    other_org = Organisation.objects.create(name="Other Clinic Queue", slug="other-clinic-queue")
    with tenant_atomic(other_org.id):
        other_facility = Facility.objects.create(
            organisation=other_org, name="Other Facility", code="MAIN", mode="CLINIC"
        )
        other_patient = Patient.objects.create(
            organisation=other_org,
            patient_no="P-OTHER-Q",
            first_name="QueueLeak",
            last_name="Sentinel",
            sex="UNKNOWN",
        )
        other_department = Department.objects.create(
            organisation=other_org, facility=other_facility, name="Other OPD", code="OPD"
        )
        QueueEntry.objects.create(
            organisation=other_org,
            facility=other_facility,
            department=other_department,
            patient=other_patient,
            queue_date=date.today(),
            sequence=1,
            status="WAITING",
        )

    def queue_labels(query):
        response = authed_client.get("/api/v1/clinic/queue/" + query)
        assert response.status_code == 200, response.data
        return {entry["patient_name"] for entry in response.data}

    for query in ("", "?status=WAITING", "?status=WAITING,CALLED", "?status=waiting&status=TRIAGED"):
        assert "QueueLeak Sentinel" not in queue_labels(query), query


def test_invoice_list_is_tenant_scoped(tenant, authed_client):
    invoice = create_invoice_for(tenant, authed_client, "Scoped", "Searchable")
    other_org = Organisation.objects.create(name="Other Clinic", slug="other-clinic")
    with tenant_atomic(other_org.id):
        other_facility = Facility.objects.create(
            organisation=other_org, name="Other Facility", code="MAIN", mode="CLINIC"
        )
        other_patient = Patient.objects.create(
            organisation=other_org,
            patient_no="P-OTHER",
            first_name="Searchable",
            last_name="Other",
            sex="UNKNOWN",
        )
        Invoice.objects.create(
            organisation=other_org,
            facility=other_facility,
            invoice_no=invoice["invoice_no"] + "-X",
            patient=other_patient,
            status="ISSUED",
            currency="UGX",
            total=Decimal("100.00"),
            balance=Decimal("100.00"),
            created_by=tenant.user,
        )
    response = authed_client.get("/api/v1/billing/invoices/?q=Searchable")
    assert response.status_code == 200
    assert {item["invoice_no"] for item in response.data} == {invoice["invoice_no"]}
    response = authed_client.get("/api/v1/billing/invoices/?status=ISSUED")
    assert all(item["invoice_no"] != invoice["invoice_no"] + "-X" for item in response.data)
