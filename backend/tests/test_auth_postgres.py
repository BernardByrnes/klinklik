import pytest
from django.db import DatabaseError, connection, transaction
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from core.services import tenant_atomic
from patients.models import Patient
from tenancy.models import Facility, Organisation


pytestmark = pytest.mark.django_db

FORBIDDEN_BOOTSTRAP_TABLES = (
    "patients_",
    "clinical_",
    "billing_",
    "audit_",
    "scheduling_",
    "maternity_",
    "laboratory_",
    "pharmacy_",
    "inventory_",
    "reporting_",
)


def require_postgres():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL-only authentication/RLS regression")


def query_text(captured):
    return "\n".join(query["sql"].lower() for query in captured.captured_queries)


def test_invalid_credentials_do_not_enter_tenant_bootstrap(tenant):
    require_postgres()
    client = APIClient()
    with CaptureQueriesContext(connection) as captured:
        response = client.post(
            "/api/v1/auth/login/",
            {
                "username": tenant.user.username,
                "password": "not-the-password",
                "organisation_id": str(tenant.organisation.id),
            },
            format="json",
        )
    assert response.status_code == 401
    sql = query_text(captured)
    assert "accounts_organisationmembership" not in sql
    assert "accounts_authsession" not in sql
    assert not any(table in sql for table in FORBIDDEN_BOOTSTRAP_TABLES)


def test_postgres_login_bootstrap_reads_only_membership_session_and_facility(tenant):
    require_postgres()
    client = APIClient()
    with CaptureQueriesContext(connection) as captured:
        response = client.post(
            "/api/v1/auth/login/",
            {
                "username": tenant.user.username,
                "password": "test-password-123",
                "organisation_id": str(tenant.organisation.id),
            },
            format="json",
        )
    assert response.status_code == 200, response.data
    sql = query_text(captured)
    assert "accounts_organisationmembership" in sql
    assert "accounts_authsession" in sql
    assert "tenancy_facility" in sql
    assert not any(table in sql for table in FORBIDDEN_BOOTSTRAP_TABLES)


def test_postgres_refresh_bootstrap_reads_no_operational_tables(tenant):
    require_postgres()
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {
            "username": tenant.user.username,
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    assert login.status_code == 200, login.data
    with CaptureQueriesContext(connection) as captured:
        response = client.post("/api/v1/auth/refresh/", {}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["access_token"] != login.data["access_token"]
    sql = query_text(captured)
    assert "accounts_authsession" in sql
    assert "tenancy_facility" in sql
    assert not any(table in sql for table in FORBIDDEN_BOOTSTRAP_TABLES)


def test_missing_tenant_context_fails_closed_for_operational_data(tenant):
    require_postgres()
    with connection.cursor() as cursor:
        cursor.execute("RESET app.current_org_id")
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM patients_patient")


def test_postgres_cross_tenant_patient_access_is_404(tenant, authed_client):
    require_postgres()
    other_org = Organisation.objects.create(name="Other Clinic", slug="other-clinic-auth")
    with tenant_atomic(other_org.id):
        other_facility = Facility.objects.create(
            organisation=other_org,
            name="Other Facility",
            code="MAIN",
            mode="CLINIC",
        )
        other_patient = Patient.objects.create(
            organisation=other_org,
            patient_no="P-OTHER-AUTH",
            first_name="Other",
            last_name="Tenant",
            sex="UNKNOWN",
        )
    assert other_facility.organisation_id == other_org.id
    response = authed_client.get(f"/api/v1/patients/{other_patient.id}/")
    assert response.status_code == 404
