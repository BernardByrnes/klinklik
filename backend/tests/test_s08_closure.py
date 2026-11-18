"""S-08 Visit closure, blockers, denial audit and payment-gate proofs."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from audit.models import AuditEvent
from billing.models import Invoice
from clinical.models import Encounter
from core.services import tenant_atomic
from scheduling.models import QueueEntry, Visit
from tenancy.models import FacilityWorkflowPolicy
from tests.test_s05_billing import check_in, open_shift, pay, register

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def s01_target_cutover(enabled_mig001_target):
    return enabled_mig001_target


def _close(client, visit_id, version, key, **overrides):
    payload = {"expected_version": version, **overrides}
    return client.post(
        f"/api/v1/reception/visits/{visit_id}/close/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def _visit_version(tenant, visit_id):
    with tenant_atomic(tenant.organisation.id):
        return Visit.objects.get(id=visit_id).version


def _complete_queues(tenant, visit_id):
    with tenant_atomic(tenant.organisation.id):
        for entry in QueueEntry.objects.filter(visit_id=visit_id).exclude(
            state__in=("COMPLETED", "CANCELLED", "LWBS", "EXPIRED")
        ):
            entry.state = "COMPLETED"
            entry.status = "COMPLETED"
            entry.version += 1
            entry.save(update_fields=["state", "status", "version", "updated_at"])


def _encounter(tenant, visit_id, status="SIGNED"):
    with tenant_atomic(tenant.organisation.id):
        visit = Visit.objects.get(id=visit_id)
        encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=visit.patient,
            visit=visit,
            clinician=tenant.user,
            encounter_no=f"ENC-S08-{uuid4().hex[:8]}",
            status=status,
        )
        return encounter.id


def _check_in(tenant, client, key):
    patient_id = register(client, f"s08-register-{key}")
    return check_in(client, patient_id, tenant, f"s08-checkin-{key}")


def test_s08_blocked_closure_returns_exact_blockers_and_audits_denial(
    tenant, authed_client
):
    checked_in = _check_in(tenant, authed_client, "blocked")
    version = _visit_version(tenant, checked_in["visit_id"])
    response = _close(authed_client, checked_in["visit_id"], version, "s08-close-blocked")
    assert response.status_code == 409
    assert response.data["code"] == "VISIT_CLOSE_BLOCKED"
    codes = {blocker["code"] for blocker in response.data["blockers"]}
    assert {"ACTIVE_QUEUE_STAGE", "OUTSTANDING_BALANCE"} <= codes
    balance = next(
        blocker for blocker in response.data["blockers"] if blocker["code"] == "OUTSTANDING_BALANCE"
    )
    assert balance["amount"] == "30000.00"
    with tenant_atomic(tenant.organisation.id):
        visit = Visit.objects.get(id=checked_in["visit_id"])
        assert visit.state != "CLOSED"
        event = AuditEvent.objects.get(
            organisation=tenant.organisation, denial_event_code="VISIT_CLOSE_DENIED"
        )
        assert event.event_code == "AUTHORIZATION_DENIED"
        assert event.reason_code == "ACTIVE_QUEUE_STAGE"
        assert event.source_ids["blocker_1"] == "ACTIVE_QUEUE_STAGE"
        assert "OUTSTANDING_BALANCE" in event.source_ids.values()
        assert "S08" not in str(event.source_ids)


def test_s08_successful_closure_is_state_bearing_idempotent_and_guarded(
    tenant, authed_client
):
    checked_in = _check_in(tenant, authed_client, "success")
    invoice_id = checked_in["invoice_id"]
    open_shift(authed_client)
    paid = pay(authed_client, invoice_id, "30000.00", "s08-pay-success")
    assert paid.status_code == 201
    _complete_queues(tenant, checked_in["visit_id"])
    _encounter(tenant, checked_in["visit_id"], status="SIGNED")
    version = _visit_version(tenant, checked_in["visit_id"])

    response = _close(authed_client, checked_in["visit_id"], version, "s08-close-success")
    assert response.status_code == 200, response.data
    assert response.data["state"] == "CLOSED"
    assert response.data["closure_reason"] == "COMPLETED"
    assert response.data["closed"] is True
    assert response.data["blockers"] == []

    replay = _close(authed_client, checked_in["visit_id"], version, "s08-close-success")
    assert replay.status_code == 200
    assert replay.headers["Idempotent-Replay"] == "true"

    with tenant_atomic(tenant.organisation.id):
        visit = Visit.objects.get(id=checked_in["visit_id"])
        assert visit.state == "CLOSED"
        assert visit.closed_by_id == tenant.user.id
        assert AuditEvent.objects.filter(event_code="VISIT_CLOSED").count() == 1
        assert AuditEvent.objects.filter(denial_event_code="VISIT_CLOSE_DENIED").count() == 0

    second = _close(
        authed_client,
        checked_in["visit_id"],
        version + 1,
        "s08-close-again",
    )
    assert second.status_code == 200
    assert second.data["already_closed"] is True
    with tenant_atomic(tenant.organisation.id):
        assert AuditEvent.objects.filter(event_code="VISIT_CLOSED").count() == 1

    invoice = authed_client.get(f"/api/v1/billing/invoices/{invoice_id}/")
    line_id = invoice.data["items"][0]["id"]
    attach = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/lines/{line_id}/void/",
        {"reason": "Synthetic post-closure attempt"},
        format="json",
    )
    assert attach.status_code == 409
    assert attach.data["code"] == "VISIT_CLOSED"


def test_s08_unsigned_encounter_outstanding_and_emergency_blockers(
    tenant, authed_client
):
    checked_in = _check_in(tenant, authed_client, "blockers")
    _complete_queues(tenant, checked_in["visit_id"])
    _encounter(tenant, checked_in["visit_id"], status="OPEN")
    version = _visit_version(tenant, checked_in["visit_id"])
    response = _close(authed_client, checked_in["visit_id"], version, "s08-unsigned")
    assert response.status_code == 409
    unsigned = next(
        blocker for blocker in response.data["blockers"] if blocker["code"] == "UNSIGNED_ENCOUNTER"
    )
    assert unsigned["clinician_id"] == str(tenant.user.id)

    with tenant_atomic(tenant.organisation.id):
        Encounter.objects.filter(encounter_no__startswith="ENC-S08-").update(status="SIGNED")
        Visit.objects.filter(id=checked_in["visit_id"]).update(emergency_setup_pending=True)
        version = Visit.objects.get(id=checked_in["visit_id"]).version
    emergency = _close(authed_client, checked_in["visit_id"], version, "s08-emergency")
    assert emergency.status_code == 409
    codes = {blocker["code"] for blocker in emergency.data["blockers"]}
    assert {"OUTSTANDING_BALANCE", "EMERGENCY_FINANCIAL_SETUP_PENDING"} <= codes


def test_s08_fenced_closure_paths_are_named_not_guessed(tenant, authed_client):
    checked_in = _check_in(tenant, authed_client, "fenced")
    _complete_queues(tenant, checked_in["visit_id"])
    _encounter(tenant, checked_in["visit_id"], status="SIGNED")
    version = _visit_version(tenant, checked_in["visit_id"])
    for path in ("DEBT", "WAIVER"):
        response = _close(
            authed_client,
            checked_in["visit_id"],
            version,
            f"s08-fenced-{path}",
            closure_path=path,
        )
        assert response.status_code == 422
        assert response.data["code"] == "PREREQUISITE_MISSING"
        assert response.data["owner_decision"] == "BP-BL-02/03/04/09"
    with tenant_atomic(tenant.organisation.id):
        assert Visit.objects.get(id=checked_in["visit_id"]).state != "CLOSED"
        denials = AuditEvent.objects.filter(denial_event_code="VISIT_CLOSE_DENIED")
        assert denials.count() == 2
        assert all(
            event.source_ids["blocker_1"] == "PREREQUISITE_MISSING"
            for event in denials
        )


def test_s08_payment_gate_releases_only_when_the_visit_is_settled(tenant, authed_client):
    with tenant_atomic(tenant.organisation.id):
        FacilityWorkflowPolicy.objects.update_or_create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            defaults={
                "consultation_payment_timing": "PAY_BEFORE_TRIAGE",
                "updated_by": tenant.user,
            },
        )
    checked_in = _check_in(tenant, authed_client, "gate")
    open_shift(authed_client)
    with tenant_atomic(tenant.organisation.id):
        entry = QueueEntry.objects.get(id=checked_in["queue_id"])
        assert entry.state == "WAITING_PAYMENT"

    partial = pay(authed_client, checked_in["invoice_id"], "10000.00", "s08-gate-partial")
    assert partial.status_code == 201
    with tenant_atomic(tenant.organisation.id):
        assert QueueEntry.objects.get(id=checked_in["queue_id"]).state == "WAITING_PAYMENT"

    final = pay(authed_client, checked_in["invoice_id"], "20000.00", "s08-gate-final")
    assert final.status_code == 201
    with tenant_atomic(tenant.organisation.id):
        entry = QueueEntry.objects.get(id=checked_in["queue_id"])
        assert entry.state == "WAITING"
        assert entry.status == "WAITING"
        assert AuditEvent.objects.filter(event_code="PAYMENT_GATE_RELEASED").count() == 1


def test_s08_closure_permission_is_server_side_and_audited(tenant):
    checked_in = _check_in(tenant, _owner_client(tenant), "permission")
    with tenant_atomic(tenant.organisation.id):
        user = User.objects.create_user("s08-nurse", "test-password-123")
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=user)
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=user,
            role=Role.objects.get(
                organisation=tenant.organisation, template_code="NURSE_TRIAGE"
            ),
            facility=tenant.facility,
            department=tenant.department,
        )
        version = Visit.objects.get(id=checked_in["visit_id"]).version
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {
            "username": "s08-nurse",
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    assert login.status_code == 200
    client.defaults["HTTP_X_FACILITY_ID"] = str(tenant.facility.id)
    client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    response = _close(client, checked_in["visit_id"], version, "s08-permission")
    assert response.status_code == 403
    with tenant_atomic(tenant.organisation.id):
        assert AuditEvent.objects.filter(
            event_code="AUTHORIZATION_DENIED", actor=user
        ).exists()


def _owner_client(tenant):
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
    assert login.status_code == 200
    client.defaults["HTTP_X_FACILITY_ID"] = str(tenant.facility.id)
    client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    return client
