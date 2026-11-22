import pytest
from django.test import override_settings
from rest_framework.test import APIClient


@pytest.mark.parametrize("refresh_days", [7, 30])
def test_session_responses_report_effective_refresh_lifetime(tenant, refresh_days):
    expected_seconds = refresh_days * 24 * 60 * 60
    client = APIClient()
    credentials = {
        "username": tenant.user.username,
        "password": "test-password-123",
        "organisation_id": str(tenant.organisation.id),
    }

    with override_settings(REFRESH_TOKEN_DAYS=refresh_days):
        login = client.post("/api/v1/auth/login/", credentials, format="json")
        assert login.status_code == 200, login.data
        assert login.data["refresh_lifetime_seconds"] == expected_seconds
        assert int(login.cookies["clinicopus_refresh"]["max-age"]) == expected_seconds

        refresh = client.post("/api/v1/auth/refresh/", {}, format="json")
        assert refresh.status_code == 200, refresh.data
        assert refresh.data["refresh_lifetime_seconds"] == expected_seconds
        assert int(refresh.cookies["clinicopus_refresh"]["max-age"]) == expected_seconds
