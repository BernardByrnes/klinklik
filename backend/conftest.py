from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from accounts.services import ensure_default_permissions
from billing.models import PriceList, ServiceCatalogItem, ServicePrice
from core.clock import local_service_date
from core.services import tenant_atomic
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
