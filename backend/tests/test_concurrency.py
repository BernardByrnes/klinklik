import pytest


pytestmark = pytest.mark.django_db


def test_patient_edits_require_current_if_match(tenant, authed_client):
    patient = authed_client.post(
        "/api/v1/patients/",
        {"first_name": "Concurrent", "last_name": "Patient", "sex": "UNKNOWN"},
        format="json",
    ).data
    detail_url = f"/api/v1/patients/{patient['id']}/"
    read = authed_client.get(detail_url)
    etag = read["ETag"]
    updated = authed_client.patch(
        detail_url, {"phone": "0700000000"}, format="json", HTTP_IF_MATCH=etag
    )
    assert updated.status_code == 200
    assert authed_client.patch(
        detail_url, {"phone": "0700000001"}, format="json", HTTP_IF_MATCH=etag
    ).status_code == 412
    assert authed_client.patch(detail_url, {"phone": "0700000002"}, format="json").status_code == 428
