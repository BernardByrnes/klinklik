import pytest

from audit.models import AuditEvent


pytestmark = pytest.mark.django_db


def test_patient_creation_writes_audit_event(tenant, authed_client):
    response = authed_client.post(
        "/api/v1/patients/",
        {"first_name": "Audited", "last_name": "Patient", "sex": "UNKNOWN"},
        format="json",
    )
    assert response.status_code == 201
    assert AuditEvent.objects.filter(
        organisation=tenant.organisation,
        entity_type="Patient",
        entity_id=response.data["id"],
        action="CREATE",
    ).exists()
