from types import SimpleNamespace
import re

import pytest
from rest_framework.test import APIClient

from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from accounts.services import ensure_default_permissions
from billing.models import PriceList, ServiceCatalogItem, ServicePrice
from core.clock import local_service_date
from core.migration_reconciliation import backfill_mig001, cutover_mig001, inventory_mig001
from core.services import tenant_atomic
from core.models import MigrationCutover
from tenancy.models import Department, Facility, Organisation


@pytest.fixture
def tenant(db):
    organisation = Organisation.objects.create(name="Test Clinic", slug="test-clinic")
    with tenant_atomic(organisation.id):
        facility = Facility.objects.create(
            organisation=organisation, name="Test Facility", code="MAIN", mode="CLINIC"
        )
        department = Department.objects.create(
            organisation=organisation, facility=facility, name="Outpatient", code="OPD"
        )
        user = User.objects.create_user("clinician", "test-password-123")
        OrganisationMembership.objects.create(organisation=organisation, user=user)
        ensure_default_permissions(organisation)
        role = Role.objects.get(organisation=organisation, template_code="OWNER_ADMIN")
        UserFacilityRole.objects.create(
            organisation=organisation,
            user=user,
            role=role,
            facility=facility,
            department=department,
        )
        service = ServiceCatalogItem.objects.create(
            organisation=organisation, code="CONSULTATION", name="General consultation"
        )
        price_list = PriceList.objects.create(
            organisation=organisation,
            stable_code="STANDARD",
            name="Standard cash",
            payer_type="CASH",
            effective_from=local_service_date(),
        )
        ServicePrice.objects.create(
            organisation=organisation,
            facility=facility,
            service=service,
            price_list=price_list,
            amount="30000.00",
            currency="UGX",
            effective_from=local_service_date(),
        )
    return SimpleNamespace(
        organisation=organisation,
        facility=facility,
        department=department,
        user=user,
        service=service,
        price_list=price_list,
    )


@pytest.fixture
def enabled_mig001_target(tenant):
    """Opt tests into S-01 only through the same durable cutover gates."""

    with tenant_atomic(tenant.organisation.id):
        inventory_mig001(organisation=tenant.organisation)
        backfill_mig001(organisation=tenant.organisation)
        cutover_mig001(organisation=tenant.organisation)
        return MigrationCutover.objects.get(
            organisation=tenant.organisation,
            migration_id="MIG-001",
        )


@pytest.fixture
def authed_client(tenant):
    client = APIClient()
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
    client.defaults["HTTP_X_FACILITY_ID"] = str(tenant.facility.id)
    client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access_token"])
    return client


_S19_ENFORCED_PATH = re.compile(
    r"/api/v1/(?:clinic|clinical)/(?:"
    r"encounters/[^/]+/(?:notes|sign|amend|diagnoses|disposition|follow-up|allergies/review)"
    r"|patients/[^/]+/(?:allergies|allergy-status)"
    r")"
)


@pytest.fixture(autouse=True)
def s19_legacy_test_idempotency(request, monkeypatch):
    """Give legacy backend tests a unique key for newly enforced clinical calls.

    Explicit S-19 tests opt out by module name so they can assert missing-key,
    replay and conflict behaviour directly.
    """
    if request.module.__name__.endswith("test_s19_idempotency"):
        return
    from django.test import Client
    import itertools

    original_request = Client.request
    counter = itertools.count(1)

    def request_with_key(self, **kwargs):
        path = kwargs.get("PATH_INFO", "")
        method = kwargs.get("REQUEST_METHOD", "")
        if (
            method in {"POST", "PATCH", "PUT"}
            and _S19_ENFORCED_PATH.search(path)
            and "HTTP_IDEMPOTENCY_KEY" not in kwargs
        ):
            kwargs = dict(kwargs)
            kwargs["HTTP_IDEMPOTENCY_KEY"] = f"s19-legacy-auto-{next(counter)}"
        return original_request(self, **kwargs)

    monkeypatch.setattr(Client, "request", request_with_key)
