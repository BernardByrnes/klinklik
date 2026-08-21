import pytest


pytestmark = pytest.mark.django_db


def test_idempotency_replay_and_etag(tenant, authed_client):
    payload = {"first_name": "Retry", "last_name": "Safe", "sex": "UNKNOWN"}
    headers = {"HTTP_IDEMPOTENCY_KEY": "patient-create-001"}
    first = authed_client.post("/api/v1/patients/", payload, format="json", **headers)
    second = authed_client.post("/api/v1/patients/", payload, format="json", **headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert second["Idempotent-Replay"] == "true"
    assert first.data["id"] == second.data["id"]

    listing = authed_client.get("/api/v1/patients/")
    assert listing.status_code == 200
    assert listing["ETag"].startswith('"')
