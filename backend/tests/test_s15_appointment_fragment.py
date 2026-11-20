"""S-15 supplied Appointment fragment: NO_SHOW -> CHECKED_IN only."""

from datetime import date
from uuid import uuid4

import pytest

from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from audit.models import AuditEvent
from core.clock import local_service_date, now
from core.errors import CanonicalError
from core.services import tenant_atomic
from scheduling.appointment import assert_no_show_fragment
from scheduling.models import Appointment, QueueEntry, Visit
from tests.test_s05_billing import register

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def s01_target_cutover(enabled_mig001_target):
    return enabled_mig001_target


def _patient(client):
    return register(client, f"s15-patient-{uuid4().hex}")


def _appointment(tenant, patient_id, *, status="NO_SHOW", service_day=None):
    with tenant_atomic(tenant.organisation.id):
        return Appointment.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient_id=patient_id,
            department=tenant.department,
            scheduled_start=now(),
            service_day=service_day or local_service_date(),
            status=status,
            created_by=tenant.user,
        )


def _check_in(client, appointment_id, key=None, **overrides):
    payload = {"visit_type": "OUTPATIENT_NEW", "payer_type": "CASH"}
    payload.update(overrides)
    return client.post(
        f"/api/v1/reception/appointments/{appointment_id}/no-show-check-in/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key or f"s15-checkin-{uuid4().hex}",
    )


def _role_user(tenant, template):
    with tenant_atomic(tenant.organisation.id):
        user = User.objects.create_user(
            f"s15-{template.lower()}-{uuid4().hex[:6]}", "test-password-123"
        )
        OrganisationMembership.objects.create(
            organisation=tenant.organisation, user=user
        )
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=user,
            role=Role.objects.get(
                organisation=tenant.organisation, template_code=template
            ),
            facility=tenant.facility,
            department=tenant.department,
        )
    return user


def _login(tenant, user):
    from rest_framework.test import APIClient

    client = APIClient()
    response = client.post(
        "/api/v1/auth/login/",
        {
            "username": user.username,
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access_token"])
    client.defaults["HTTP_X_FACILITY_ID"] = str(tenant.facility.id)
    return client


def test_s15_no_show_check_in_creates_one_linked_handover(tenant, authed_client):
    # CMD-087 — mechanical evidence for s17-cmd-audit.
    patient_id = _patient(authed_client)
    appointment = _appointment(tenant, patient_id)
    response = _check_in(authed_client, appointment.id, key="s15-happy")
    assert response.status_code == 201, response.data
    body = response.data
    assert body["appointment_status"] == "CHECKED_IN"
    assert body["already_checked_in"] is False
    assert body["visit_id"] and body["queue_id"] and body["invoice_id"]

    with tenant_atomic(tenant.organisation.id):
        appointment = Appointment.objects.get(id=appointment.id)
        assert appointment.status == "CHECKED_IN"
        assert appointment.service_day is not None
        assert str(appointment.checked_in_visit_id) == body["visit_id"]
        assert appointment.version == 2
        visit = Visit.objects.get(id=body["visit_id"])
        assert str(visit.patient_id) == str(patient_id)
        assert visit.state == "OPEN"
        queue = QueueEntry.objects.get(id=body["queue_id"])
        assert queue.visit_id == visit.id
        from billing.models import Invoice, InvoiceItem

        invoice = Invoice.objects.get(id=body["invoice_id"])
        assert invoice.visit_id == visit.id
        assert InvoiceItem.objects.filter(invoice=invoice).count() >= 1
        assert AuditEvent.objects.filter(
            event_code="APPOINTMENT_CHECKED_IN",
            entity_type="Appointment",
            entity_id=appointment.id,
        ).count() == 1
        assert AuditEvent.objects.filter(event_code="VISIT_OPENED", entity_id=visit.id).count() == 1
        assert AuditEvent.objects.filter(event_code="QUEUE_ENTRY_CREATED", entity_id=queue.id).count() == 1
        assert AuditEvent.objects.filter(event_code="INVOICE_ISSUED", entity_id=invoice.id).count() == 1


def test_s15_exact_replay_and_already_exists_do_not_duplicate(tenant, authed_client):
    patient_id = _patient(authed_client)
    appointment = _appointment(tenant, patient_id)
    first = _check_in(authed_client, appointment.id, key="s15-replay")
    assert first.status_code == 201, first.data
    replay = _check_in(authed_client, appointment.id, key="s15-replay")
    assert replay.status_code == 201
    assert replay.data == first.data
    assert replay["Idempotent-Replay"] == "true"
    second = _check_in(authed_client, appointment.id, key="s15-replay-new")
    assert second.status_code == 200, second.data
    assert second.data["already_checked_in"] is True
    assert second.data["visit_id"] == first.data["visit_id"]
    with tenant_atomic(tenant.organisation.id):
        assert Visit.objects.filter(patient_id=patient_id).count() == 1
        assert QueueEntry.objects.filter(visit_id=first.data["visit_id"]).count() == 1
        assert AuditEvent.objects.filter(event_code="APPOINTMENT_CHECKED_IN").count() == 1


@pytest.mark.parametrize("status", ["BOOKED", "COMPLETED", "CANCELLED"])
def test_s15_every_other_transition_is_unsupported(
    tenant, authed_client, status
):
    patient_id = _patient(authed_client)
    appointment = _appointment(tenant, patient_id, status=status)
    response = _check_in(authed_client, appointment.id)
    assert response.status_code == 409
    assert response.data["code"] == "UNSUPPORTED_OPERATION"
    with tenant_atomic(tenant.organisation.id):
        assert Visit.objects.filter(patient_id=patient_id).count() == 0
        assert Appointment.objects.get(id=appointment.id).status == status


def test_s15_checked_in_without_link_is_refused(tenant, authed_client):
    patient_id = _patient(authed_client)
    appointment = _appointment(tenant, patient_id, status="CHECKED_IN")
    response = _check_in(authed_client, appointment.id)
    assert response.status_code == 409
    assert response.data["code"] == "ALREADY_EXISTS"
    with tenant_atomic(tenant.organisation.id):
        assert Visit.objects.filter(patient_id=patient_id).count() == 0


def test_s15_permission_requires_the_fragment_capability(tenant, authed_client):
    patient_id = _patient(authed_client)
    appointment = _appointment(tenant, patient_id)
    nurse = _role_user(tenant, "NURSE_TRIAGE")
    nurse_client = _login(tenant, nurse)
    denied = _check_in(nurse_client, appointment.id)
    assert denied.status_code == 403
    receptionist = _role_user(tenant, "RECEPTION_CASHIER")
    receptionist_client = _login(tenant, receptionist)
    accepted = _check_in(receptionist_client, appointment.id)
    assert accepted.status_code == 201, accepted.data


def test_s15_fragment_is_facility_scoped(tenant, authed_client):
    patient_id = _patient(authed_client)
    appointment = _appointment(tenant, patient_id)
    with tenant_atomic(tenant.organisation.id):
        from tenancy.models import Facility

        other_facility = Facility.objects.create(
            organisation=tenant.organisation, name="Other", code="OTHER", mode="CLINIC"
        )
        Appointment.objects.filter(id=appointment.id).update(facility=other_facility)
    response = _check_in(authed_client, appointment.id)
    assert response.status_code == 404
    assert response.data["code"] == "NOT_FOUND"


def test_s15_assert_no_show_fragment_is_exact():
    class Stub:
        status = "BOOKED"
        service_day = date(2026, 11, 19)
        checked_in_visit_id = None

    with pytest.raises(CanonicalError) as error:
        assert_no_show_fragment(Stub())
    assert error.value.code == "UNSUPPORTED_OPERATION"
