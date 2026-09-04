from datetime import date, timedelta

import pytest
from django.db import connection
from django.utils import timezone

from application.reception.commands import patient_register, visit_check_in
from audit.models import AuditEvent
from billing.models import Invoice, InvoiceItem, ServicePrice
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import ArrivalEnquiry, QueueEntry, Visit
from tenancy.models import Department, FacilityWorkflowPolicy, Organisation


pytestmark = pytest.mark.django_db


def registration_payload():
    return {
        "first_name": "Amina",
        "last_name": "Nabirye",
        "sex": "FEMALE",
        "date_of_birth": "1990-01-01",
        "phone": "0700000000",
        "village": "Kisenyi",
        "parish": "Central",
        "sub_county": "Kampala",
        "district": "Kampala",
        "next_of_kin_name": "Kato",
        "next_of_kin_phone": "0711111111",
    }


def register(client, payload=None, key="s01-register-1"):
    return client.post(
        "/api/v1/reception/patients/register/",
        payload or registration_payload(),
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def check_in(client, patient_id, key="s01-checkin-1", **extra):
    payload = {"patient_id": str(patient_id), **extra}
    return client.post(
        "/api/v1/reception/visits/check-in/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def test_registration_duplicate_resolution_and_audit(tenant, authed_client):
    first = register(authed_client)
    assert first.status_code == 201, first.data
    patient_id = first.data["patient_id"]
    assert first.data["next_action"] == "CHECK_IN"
    assert first.data["contacts"][0]["relationship"] == "NEXT_OF_KIN"

    duplicate = register(authed_client, key="s01-register-duplicate")
    assert duplicate.status_code == 200, duplicate.data
    assert [candidate["id"] for candidate in duplicate.data["duplicate_candidates"]] == [patient_id]
    assert Patient.objects.count() == 1

    override = register(
        authed_client,
        {
            **registration_payload(),
            "first_name": "Another",
            "duplicate_resolution": {
                "decision": "NOT_THE_SAME",
                "reason": "Different person confirmed at desk",
                "rejected_candidate_ids": [patient_id],
            },
        },
        key="s01-register-override",
    )
    assert override.status_code == 201, override.data
    assert Patient.objects.count() == 2
    assert AuditEvent.objects.filter(event_code="PATIENT_CREATED").count() == 2
    override_event = AuditEvent.objects.get(event_code="DUPLICATE_OVERRIDE")
    assert override_event.source_ids["rejected_candidate_ids"] == [patient_id]
    assert "Different person" not in str(override_event.__dict__)


def test_registration_requires_idempotency_key(tenant, authed_client):
    response = authed_client.post(
        "/api/v1/reception/patients/register/",
        registration_payload(),
        format="json",
    )
    assert response.status_code == 400
    assert response.data["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert Patient.objects.count() == 0


def test_registration_accepts_partial_next_of_kin_contact(tenant, authed_client):
    response = register(
        authed_client,
        {
            **registration_payload(),
            "first_name": "Partial",
            "date_of_birth": "1993-03-03",
            "next_of_kin_name": "Kato",
            "next_of_kin_phone": "",
        },
        key="s01-register-partial-kin",
    )
    assert response.status_code == 201, response.data
    assert response.data["contacts"][0]["name"] == "Kato"
    assert response.data["contacts"][0]["phone"] == ""


def test_check_in_opens_visit_queue_and_issued_consultation_invoice(tenant, authed_client):
    patient = register(authed_client, key="s01-register-checkin").data
    response = check_in(
        authed_client,
        patient["patient_id"],
        key="s01-checkin-success",
        visit_type="OUTPATIENT_NEW",
        payer_type="CASH",
        department_id=str(tenant.department.id),
    )
    assert response.status_code == 201, response.data
    assert response.data["next_action"] == "CHECK_IN_COMPLETE"
    assert response.data["invoice"]["status"] == "ISSUED"
    assert response.data["queue"]["status"] == "WAITING"

    visit = Visit.objects.get(id=response.data["visit_id"])
    queue = QueueEntry.objects.get(id=response.data["queue_id"])
    invoice = Invoice.objects.get(id=response.data["invoice_id"])
    assert visit.state == "OPEN"
    assert queue.visit_id == visit.id
    assert queue.queue_type == "TRIAGE"
    assert invoice.visit_id == visit.id
    assert invoice.items.filter(source_type="CONSULTATION", state="ACTIVE").count() == 1
    assert InvoiceItem.objects.filter(invoice=invoice).count() == 1
    assert AuditEvent.objects.filter(entity_id=str(visit.id), event_code="VISIT_OPENED").exists()
    assert AuditEvent.objects.filter(entity_id=str(queue.id), event_code="QUEUE_ENTRY_CREATED").exists()
    assert AuditEvent.objects.filter(entity_id=str(invoice.id), event_code="INVOICE_ISSUED").exists()
    assert Patient.objects.get(id=patient["patient_id"]).last_seen_at is not None

    replay = check_in(
        authed_client,
        patient["patient_id"],
        key="s01-checkin-success",
        visit_type="OUTPATIENT_NEW",
        payer_type="CASH",
        department_id=str(tenant.department.id),
    )
    assert replay.status_code == 201
    assert replay["Idempotent-Replay"] == "true"
    assert replay.data["visit_id"] == response.data["visit_id"]

    duplicate = check_in(
        authed_client,
        patient["patient_id"],
        key="s01-checkin-duplicate",
        visit_type="OUTPATIENT_NEW",
        payer_type="CASH",
        department_id=str(tenant.department.id),
    )
    assert duplicate.status_code == 409
    assert duplicate.data["code"] == "VISIT_ALREADY_OPEN"
    assert duplicate.data["visit_id"] == response.data["visit_id"]
    assert Visit.objects.count() == 1
    assert QueueEntry.objects.filter(visit=visit).count() == 1
    assert Invoice.objects.filter(visit=visit).count() == 1


def test_check_in_warns_and_audits_when_patient_has_prior_balance(tenant, authed_client):
    patient = register(
        authed_client,
        {**registration_payload(), "first_name": "Balance", "date_of_birth": "1990-09-09"},
        key="s01-register-balance",
    ).data
    with tenant_atomic(tenant.organisation.id):
        Invoice.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient_id=patient["patient_id"],
            invoice_no="INV-PRIOR-BALANCE",
            status="ISSUED",
            total="15000.00",
            balance="15000.00",
            created_by=tenant.user,
        )

    summary = authed_client.get(
        f"/api/v1/reception/patients/{patient['patient_id']}/check-in-summary/"
    )
    assert summary.status_code == 200, summary.data
    assert summary.data["outstanding_balance"] == "15000.00"
    assert summary.data["outstanding_invoice_no"] == "INV-PRIOR-BALANCE"

    response = check_in(
        authed_client,
        patient["patient_id"],
        key="s01-checkin-balance",
        department_id=str(tenant.department.id),
    )
    assert response.status_code == 201, response.data
    event = AuditEvent.objects.get(event_code="OUTSTANDING_BALANCE_OVERRIDDEN")
    assert event.after == {"outstanding_balance_present": True}
    assert "15000" not in str(event.after)


def test_check_in_failure_keeps_registered_patient_and_creates_no_visit(tenant, authed_client):
    patient = register(authed_client, key="s01-register-unpriced").data
    with tenant_atomic(tenant.organisation.id):
        ServicePrice.objects.filter(service=tenant.service, facility=tenant.facility).update(
            is_active=False,
            active=False,
        )
    response = check_in(
        authed_client,
        patient["patient_id"],
        key="s01-checkin-unpriced",
        department_id=str(tenant.department.id),
    )
    assert response.status_code == 422
    assert response.data["code"] == "SERVICE_NOT_PRICED"
    assert response.data["service_code"] == "CONSULTATION"
    assert Patient.objects.filter(id=patient["patient_id"]).exists()
    assert not Visit.objects.filter(patient_id=patient["patient_id"]).exists()
    assert not QueueEntry.objects.filter(patient_id=patient["patient_id"]).exists()


def test_check_in_cannot_use_a_patient_from_another_organisation(tenant, authed_client):
    other_organisation = Organisation.objects.create(name="Other Clinic", slug="other-clinic")
    with tenant_atomic(other_organisation.id):
        other_patient = Patient.objects.create(
            organisation=other_organisation,
            patient_no="P-OTHER-0001",
            first_name="Other",
            last_name="Tenant",
            sex="UNKNOWN",
            date_of_birth=date(1980, 1, 1),
        )

    response = check_in(
        authed_client,
        other_patient.id,
        key="s01-checkin-cross-tenant",
        department_id=str(tenant.department.id),
    )
    assert response.status_code == 404
    assert response.data["code"] == "PATIENT_NOT_FOUND"
    assert not Visit.objects.filter(patient_id=other_patient.id).exists()


def test_check_in_policy_and_non_consultation_visit_types(tenant, authed_client):
    with tenant_atomic(tenant.organisation.id):
        FacilityWorkflowPolicy.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            updated_by=tenant.user,
            consultation_payment_timing="PAY_BEFORE_TRIAGE",
        )
        lab = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="Laboratory",
            code="LAB",
        )
    patient = register(authed_client, key="s01-register-payment-gate").data
    gated = check_in(
        authed_client,
        patient["patient_id"],
        key="s01-checkin-payment-gate",
        department_id=str(tenant.department.id),
    )
    assert gated.status_code == 201, gated.data
    assert gated.data["queue"]["status"] == "WAITING_PAYMENT"
    visible_queue = authed_client.get("/api/v1/clinic/queue/")
    assert visible_queue.status_code == 200, visible_queue.data
    assert gated.data["queue_id"] not in {entry["id"] for entry in visible_queue.data}

    lab_patient = register(
        authed_client,
        {**registration_payload(), "first_name": "Lab", "date_of_birth": "1991-02-02"},
        key="s01-register-lab",
    ).data
    lab_checkin = check_in(
        authed_client,
        lab_patient["patient_id"],
        key="s01-checkin-lab",
        visit_type="LAB_ONLY",
        payer_type="CASH",
        department_id=str(lab.id),
    )
    assert lab_checkin.status_code == 201, lab_checkin.data
    assert lab_checkin.data["queue_id"] is None
    assert lab_checkin.data["invoice_id"] is None
    lab_visit = Visit.objects.get(id=lab_checkin.data["visit_id"])
    assert not QueueEntry.objects.filter(visit=lab_visit).exists()
    assert not Invoice.objects.filter(visit=lab_visit).exists()
    assert Department.objects.filter(id=lab.id).exists()


def test_cancel_error_is_reversible_and_does_not_recycle_queue_number(tenant, authed_client):
    patient = register(
        authed_client,
        {**registration_payload(), "first_name": "Cancel", "date_of_birth": "1994-04-04"},
        key="s01-register-cancel",
    ).data
    checked_in = check_in(
        authed_client,
        patient["patient_id"],
        key="s01-checkin-cancel",
        department_id=str(tenant.department.id),
    )
    assert checked_in.status_code == 201, checked_in.data
    visit = Visit.objects.get(id=checked_in.data["visit_id"])
    queue = QueueEntry.objects.get(id=checked_in.data["queue_id"])
    invoice = Invoice.objects.get(id=checked_in.data["invoice_id"])

    cancelled = authed_client.post(
        f"/api/v1/reception/visits/{visit.id}/cancel-error/",
        {"reason": "Wrong patient selected", "expected_version": visit.version},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s01-cancel-error",
    )
    assert cancelled.status_code == 200, cancelled.data
    visit.refresh_from_db()
    queue.refresh_from_db()
    invoice.refresh_from_db()
    assert visit.state == "CANCELLED_ERROR"
    assert queue.status == "CANCELLED"
    assert invoice.status == "VOIDED"
    assert invoice.items.get().state == "VOIDED"
    assert AuditEvent.objects.filter(entity_id=str(visit.id), event_code="VISIT_CANCELLED_ERROR").exists()
    assert AuditEvent.objects.filter(entity_id=str(queue.id), event_code="QUEUE_CANCELLED").exists()
    assert AuditEvent.objects.filter(entity_id=str(invoice.id), event_code="INVOICE_VOIDED").exists()

    replacement = check_in(
        authed_client,
        patient["patient_id"],
        key="s01-checkin-after-cancel",
        department_id=str(tenant.department.id),
    )
    assert replacement.status_code == 201, replacement.data
    assert replacement.data["queue"]["sequence"] > queue.sequence
    assert replacement.data["invoice"]["invoice_no"] != invoice.invoice_no


def test_cancel_error_rejects_expired_and_clinical_visits(tenant, authed_client):
    patient = register(
        authed_client,
        {**registration_payload(), "first_name": "Expired", "date_of_birth": "1995-05-05"},
        key="s01-register-expired",
    ).data
    checked_in = check_in(
        authed_client,
        patient["patient_id"],
        key="s01-checkin-expired",
        department_id=str(tenant.department.id),
    )
    visit = Visit.objects.get(id=checked_in.data["visit_id"])
    with tenant_atomic(tenant.organisation.id):
        Visit.objects.filter(id=visit.id).update(opened_at=timezone.now() - timedelta(minutes=20))
    expired = authed_client.post(
        f"/api/v1/reception/visits/{visit.id}/cancel-error/",
        {"reason": "Wrong patient selected"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s01-cancel-expired",
    )
    assert expired.status_code == 422, expired.data
    assert expired.data["code"] == "GRACE_WINDOW_EXPIRED"
    visit.refresh_from_db()
    assert visit.state == "OPEN"


def test_visit_context_filters_clinical_values_by_role_and_audits_clinical_read(tenant, authed_client):
    from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
    from clinical.models import Encounter
    from rest_framework.test import APIClient

    patient = register(
        authed_client,
        {**registration_payload(), "first_name": "Context", "date_of_birth": "1996-06-06"},
        key="s01-register-context",
    ).data
    checked_in = check_in(
        authed_client,
        patient["patient_id"],
        key="s01-checkin-context",
        department_id=str(tenant.department.id),
    )
    queue = QueueEntry.objects.get(id=checked_in.data["queue_id"])
    with tenant_atomic(tenant.organisation.id):
        Encounter.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient_id=patient["patient_id"],
            queue_entry=queue,
            encounter_no="ENC-CONTEXT-1",
            clinician=tenant.user,
            complaints=["cough"],
        )
        receptionist = User.objects.create_user("s01-receptionist", "test-password-123")
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=receptionist)
        reception_role = Role.objects.get(
            organisation=tenant.organisation,
            template_code="RECEPTION_CASHIER",
        )
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=receptionist,
            role=reception_role,
            facility=tenant.facility,
            department=tenant.department,
        )

    receptionist_client = APIClient()
    login = receptionist_client.post(
        "/api/v1/auth/login/",
        {
            "username": "s01-receptionist",
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    assert login.status_code == 200, login.data
    receptionist_client.credentials(
        HTTP_AUTHORIZATION="Bearer " + login.data["access_token"],
        HTTP_X_FACILITY_ID=str(tenant.facility.id),
    )
    admin_context = receptionist_client.get(
        f"/api/v1/reception/visits/{checked_in.data['visit_id']}/context/"
    )
    assert admin_context.status_code == 200, admin_context.data
    assert admin_context.data["clinical"] is None
    assert "complaints" not in str(admin_context.data)
    assert "diagnoses" not in str(admin_context.data)
    assert "vitals" not in str(admin_context.data)
    assert "medicines" not in str(admin_context.data)

    clinician_context = authed_client.get(
        f"/api/v1/reception/visits/{checked_in.data['visit_id']}/context/"
    )
    assert clinician_context.status_code == 200, clinician_context.data
    assert clinician_context.data["clinical"][0]["complaints"] == ["cough"]
    assert AuditEvent.objects.filter(event_code="PHI_READ").count() == 1


def test_arrival_enquiry_has_no_patient_and_converts_atomically(tenant, authed_client):
    enquiry_response = authed_client.post(
        "/api/v1/reception/arrival-enquiries/",
        {"reason_code": "SERVICE_UNAVAILABLE", "source_event_id": "front-desk-001"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s01-enquiry-1",
    )
    assert enquiry_response.status_code == 201, enquiry_response.data
    enquiry = ArrivalEnquiry.objects.get(id=enquiry_response.data["enquiry_id"])
    assert Patient.objects.count() == 0
    assert Visit.objects.count() == 0

    patient = register(
        authed_client,
        {**registration_payload(), "first_name": "Converted", "date_of_birth": "1992-03-03"},
        key="s01-register-converted",
    ).data
    converted = check_in(
        authed_client,
        patient["patient_id"],
        key="s01-checkin-converted",
        arrival_enquiry_id=str(enquiry.id),
        arrival_enquiry_version=enquiry.version,
        department_id=str(tenant.department.id),
    )
    assert converted.status_code == 201, converted.data
    enquiry.refresh_from_db()
    assert enquiry.state == "CONVERTED"
    assert str(enquiry.converted_visit_id) == converted.data["visit_id"]
    assert AuditEvent.objects.filter(
        entity_id=str(enquiry.id), event_code="ARRIVAL_ENQUIRY_CONVERTED"
    ).exists()


def test_canonical_check_in_permission_is_server_enforced(tenant, authed_client):
    from accounts.models import OrganisationMembership, Role, User, UserFacilityRole

    nurse = User.objects.create_user("s01-nurse", "test-password-123")
    with tenant_atomic(tenant.organisation.id):
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=nurse)
        role = Role.objects.get(organisation=tenant.organisation, template_code="CLINICIAN")
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=nurse,
            role=role,
            facility=tenant.facility,
            department=tenant.department,
        )
    from rest_framework.test import APIClient

    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {
            "username": nurse.username,
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    client.credentials(
        HTTP_AUTHORIZATION="Bearer " + login.data["access_token"],
        HTTP_X_FACILITY_ID=str(tenant.facility.id),
    )
    response = client.post(
        "/api/v1/reception/visits/check-in/",
        {"patient_id": "00000000-0000-0000-0000-000000000001"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s01-permission-denied",
    )
    assert response.status_code == 403


def test_command_service_contract_runs_inside_tenant_transaction(tenant):
    with tenant_atomic(tenant.organisation.id):
        registered = patient_register(
            organisation=tenant.organisation,
            actor=tenant.user,
            data={
                "first_name": "Service",
                "last_name": "Boundary",
                "sex": "UNKNOWN",
                "date_of_birth": date(1980, 1, 1),
            },
        )
        checked_in = visit_check_in(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            patient_id=registered.patient.id,
            department_id=tenant.department.id,
            visit_type="OUTPATIENT_NEW",
            payer_type="CASH",
        )
    assert registered.created is True
    assert checked_in.visit.state == "OPEN"
    assert checked_in.invoice.status == "ISSUED"


@pytest.mark.skipif(connection.vendor != "postgresql", reason="PostgreSQL proof gate")
def test_s01_new_tenant_tables_are_force_rls():
    from core.rls import rls_status

    status = rls_status()
    tables = {table["name"]: table for table in status["tables"]}
    for table_name in (
        "core_numbersequence",
        "scheduling_visit",
        "scheduling_arrivalenquiry",
        "billing_pricelist",
        "billing_visitpayerbinding",
    ):
        assert tables[table_name]["rowsecurity"] is True
        assert tables[table_name]["force"] is True
        assert tables[table_name]["tenant_policy"] is True
