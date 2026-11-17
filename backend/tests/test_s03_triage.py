from datetime import date, timedelta
import json
import uuid

import pytest
from django.utils import timezone

from accounts.models import OrganisationMembership, Permission, Role, RolePermission, User, UserFacilityRole
from audit.models import AuditEvent
from billing.models import Invoice
from clinical.models import (
    PatientAllergyState,
    TriageRecord,
    TriageRecordVersion,
    VitalsObservation,
)
from core.idempotency import key_hash
from core.mig003 import (
    backfill_mig003,
    constrain_mig003,
    cutover_mig003,
    inventory_mig003,
    verify_mig003,
)
from core.migration_reconciliation import (
    backfill_mig002,
    cutover_mig002,
    inventory_mig002,
)
from core.models import IdempotencyRecord, MigrationCutover
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import QueueEntry
from tenancy.models import Department, Facility, Organisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def enabled_mig002_target(tenant, enabled_mig001_target):
    with tenant_atomic(tenant.organisation.id):
        inventory_mig002(organisation=tenant.organisation)
        backfill_mig002(organisation=tenant.organisation)
        cutover_mig002(organisation=tenant.organisation)
    return MigrationCutover.objects.get(
        organisation=tenant.organisation, migration_id="MIG-002"
    )


@pytest.fixture
def enabled_mig003_target(tenant, enabled_mig002_target):
    with tenant_atomic(tenant.organisation.id):
        inventory_mig003(organisation=tenant.organisation)
        backfill_mig003(organisation=tenant.organisation)
        verify_mig003(organisation=tenant.organisation)
        verify_mig003(organisation=tenant.organisation)
        constrain_mig003(organisation=tenant.organisation)
        cutover_mig003(organisation=tenant.organisation)
    return MigrationCutover.objects.get(
        organisation=tenant.organisation, migration_id="MIG-003"
    )


def _registration_payload():
    return {
        "first_name": "Synthetic",
        "last_name": f"Triage-{uuid.uuid4().hex[:6]}",
        "sex": "FEMALE",
        "phone": "0700000000",
        "date_of_birth": date(1994, 4, 12).isoformat(),
    }


def _register(authed_client, *, key):
    response = authed_client.post(
        "/api/v1/reception/patients/register/",
        _registration_payload(),
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert response.status_code == 201, response.data
    return response.data["patient_id"]


def _check_in(tenant, authed_client, *, key, patient_id=None):
    patient_id = patient_id or _register(authed_client, key=f"{key}-register")
    response = authed_client.post(
        "/api/v1/reception/visits/check-in/",
        {
            "patient_id": patient_id,
            "visit_type": "OUTPATIENT_NEW",
            "payer_type": "CASH",
            "department_id": str(tenant.department.id),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert response.status_code == 201, response.data
    return patient_id, response.data


def _record_allergy_status(tenant, patient_id, *, status="NKA"):
    with tenant_atomic(tenant.organisation.id):
        PatientAllergyState.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient_id=patient_id,
            status=status,
            revision=1,
            updated_by=tenant.user,
        )


def _queue(tenant, queue_id):
    with tenant_atomic(tenant.organisation.id):
        return QueueEntry.objects.get(
            organisation=tenant.organisation,
            facility=tenant.facility,
            id=queue_id,
        )


def _start(client, queue_id, version, *, key="s03-start"):
    return client.post(
        f"/api/v1/clinic/triage/{queue_id}/start/",
        {"expected_version": version},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def _save(client, record_id, version, payload, *, key="s03-save"):
    return client.patch(
        f"/api/v1/clinic/triage-records/{record_id}/",
        payload,
        format="json",
        HTTP_IF_MATCH=f'"{version}"',
        HTTP_IDEMPOTENCY_KEY=key,
    )


def _complete(client, record_id, record_version, queue_version, payload, *, key="s03-complete"):
    return client.post(
        f"/api/v1/clinic/triage-records/{record_id}/complete/",
        {
            **payload,
            "expected_version": record_version,
            "expected_queue_version": queue_version,
        },
        format="json",
        HTTP_IF_MATCH=f'"{record_version}"',
        HTTP_IDEMPOTENCY_KEY=key,
    )


def test_s03_start_save_complete_preserves_the_check_in_invoice(
    tenant, authed_client, enabled_mig003_target
):
    patient_id, checked_in = _check_in(tenant, authed_client, key="s03-happy-checkin")
    _record_allergy_status(tenant, patient_id, status="NKA")
    queue = _queue(tenant, checked_in["queue_id"])
    invoice = Invoice.objects.get(id=checked_in["invoice_id"])
    invoice_line_ids = list(invoice.items.values_list("id", flat=True))
    assert len(invoice_line_ids) == 1

    started = _start(authed_client, queue.id, queue.version)
    assert started.status_code == 200, started.data
    record = started.data["triage_record"]
    assert record["state"] == "DRAFT"
    assert record["version"] == 1
    assert started.data["queue_entry"]["state"] == "IN_SERVICE"
    queue_version = started.data["queue_entry"]["version"]

    saved = _save(
        authed_client,
        record["id"],
        1,
        {
            "presenting_complaints": [
                {"text": "Fever — 3 days", "duration_value": 3, "duration_unit": "DAYS"},
                {"text": "Cough", "duration_value": 5, "duration_unit": "DAYS"},
            ],
            "current_medications": {
                "medications": ["Paracetamol 500 mg PRN"],
                "chronic_conditions": ["Asthma"],
            },
            "observation": {
                "temperature_c": "39.8",
                "pulse": 98,
                "systolic": 118,
                "diastolic": 76,
                "weight_kg": "62.4",
                "height_cm": "168.0",
            },
            "acuity": "URGENT",
            "acuity_reason": "High fever",
        },
    )
    assert saved.status_code == 200, saved.data
    assert saved.data["triage_record"]["version"] == 2
    assert saved["ETag"] == '"2"'
    assert saved.data["triage_record"]["bmi"] == "22.1"
    observation_id = saved.data["triage_record"]["observation"]["id"]

    read = authed_client.get(f"/api/v1/clinic/triage-records/{record['id']}/")
    assert read.status_code == 200, read.data
    assert read["ETag"] == '"2"'
    assert read.data["triage_record"]["presenting_complaints"][0]["text"] == "Fever — 3 days"
    assert read.data["triage_record"]["observation"]["id"] == observation_id

    completed = _complete(
        authed_client,
        record["id"],
        2,
        queue_version,
        {
            "acuity": "URGENT",
            "acuity_reason": "High fever",
            "presenting_complaints": [
                {"text": "Fever — 3 days", "duration_value": 3, "duration_unit": "DAYS"}
            ],
        },
    )
    assert completed.status_code == 200, completed.data
    assert completed.data["triage_record"]["state"] == "COMPLETED"
    assert completed.data["triage_record"]["current_version"] == 1
    assert completed.data["source_state"] == "COMPLETED"
    assert completed.data["destination_state"] == "WAITING"

    with tenant_atomic(tenant.organisation.id):
        head = TriageRecord.objects.get(id=record["id"])
        version = TriageRecordVersion.objects.get(record=head, version_number=1)
        assert head.current_version == 1
        assert head.completed_by_id == tenant.user.id
        assert version.content["acuity"] == "URGENT"
        assert version.content["presenting_complaints"][0]["text"] == "Fever — 3 days"
        assert version.content["presenting_complaints"][0]["duration_unit"] == "DAYS"
        assert len(version.content_hash) == 64
        assert VitalsObservation.objects.filter(
            triage_record=head, context="TRIAGE", sequence=1
        ).count() == 1
        source = QueueEntry.objects.get(id=queue.id)
        destination = QueueEntry.objects.get(
            id=completed.data["destination_queue_entry_id"]
        )
        assert source.state == "COMPLETED"
        assert destination.state == "WAITING"
        assert destination.queue_type == "CONSULTATION"
        assert destination.priority == "URGENT"
        assert destination.visit_id == source.visit_id
        invoice.refresh_from_db()
        assert list(invoice.items.values_list("id", flat=True)) == invoice_line_ids
        for event_code in (
            "TRIAGE_STARTED",
            "TRIAGE_DRAFT_SAVED",
            "TRIAGE_VITALS_RECORDED",
            "TRIAGE_COMPLETED",
            "QUEUE_HANDOFF",
        ):
            assert AuditEvent.objects.filter(
                organisation=tenant.organisation, event_code=event_code
            ).exists()
        for code in (
            "s03-happy-checkin",
            "s03-start",
            "s03-save",
            "s03-complete",
        ):
            record_body = json.dumps(
                IdempotencyRecord.objects.get(
                    organisation=tenant.organisation,
                    key_hash=key_hash(code),
                ).response_body
            )
            assert "Fever" not in record_body
            assert "39.8" not in record_body
            assert "Paracetamol" not in record_body


def test_s03_replay_and_concurrency_guards(tenant, authed_client, enabled_mig003_target):
    patient_id, checked_in = _check_in(tenant, authed_client, key="s03-replay-checkin")
    _record_allergy_status(tenant, patient_id)
    queue = _queue(tenant, checked_in["queue_id"])
    started = _start(authed_client, queue.id, queue.version, key="s03-replay-start")
    assert started.status_code == 200, started.data
    record_id = started.data["triage_record"]["id"]
    queue_version = started.data["queue_entry"]["version"]

    replay = _start(authed_client, queue.id, queue.version, key="s03-replay-start")
    assert replay.status_code == 200, replay.data
    assert replay["Idempotent-Replay"] == "true"
    assert replay.data == started.data

    stale = _save(authed_client, record_id, 99, {"acuity": "ROUTINE"}, key="s03-stale-save")
    assert stale.status_code == 412, stale.data
    assert stale.data["code"] == "VERSION_CONFLICT"

    invalid = _save(
        authed_client,
        record_id,
        1,
        {"observation": {"temperature_c": "3.98"}},
        key="s03-invalid-temperature",
    )
    assert invalid.status_code == 422, invalid.data
    assert invalid.data["code"] == "VITAL_OUT_OF_RANGE"

    bad_bp = _save(
        authed_client,
        record_id,
        1,
        {"observation": {"systolic": 120, "diastolic": 130}},
        key="s03-invalid-bp",
    )
    assert bad_bp.status_code == 422, bad_bp.data
    assert bad_bp.data["code"] == "DIASTOLIC_EXCEEDS_SYSTOLIC"

    zero_pulse = _save(
        authed_client,
        record_id,
        1,
        {"observation": {"pulse": 0}},
        key="s03-invalid-pulse",
    )
    assert zero_pulse.status_code == 422, zero_pulse.data
    assert zero_pulse.data["code"] == "VITAL_OUT_OF_RANGE"

    too_many_complaints = _save(
        authed_client,
        record_id,
        1,
        {
            "presenting_complaints": [{"text": f"Complaint {index}"} for index in range(6)],
            "observation": {"pulse": 70},
        },
        key="s03-complaint-limit",
    )
    assert too_many_complaints.status_code == 422, too_many_complaints.data
    assert too_many_complaints.data["code"] == "COMPLAINT_LIMIT_EXCEEDED"

    saved = _save(
        authed_client,
        record_id,
        1,
        {
            "presenting_complaints": [{"text": "Cough"}],
            "observation": {"pulse": 80, "systolic": 120, "diastolic": 70},
            "acuity": "ROUTINE",
        },
        key="s03-replay-save",
    )
    assert saved.status_code == 200, saved.data
    saved_replay = _save(
        authed_client,
        record_id,
        1,
        {
            "presenting_complaints": [{"text": "Cough"}],
            "observation": {"pulse": 80, "systolic": 120, "diastolic": 70},
            "acuity": "ROUTINE",
        },
        key="s03-replay-save",
    )
    assert saved_replay["Idempotent-Replay"] == "true"

    completed = _complete(
        authed_client,
        record_id,
        2,
        queue_version,
        {"acuity": "ROUTINE", "acuity_reason": ""},
        key="s03-replay-complete",
    )
    assert completed.status_code == 200, completed.data
    completed_replay = _complete(
        authed_client,
        record_id,
        2,
        queue_version,
        {"acuity": "ROUTINE", "acuity_reason": ""},
        key="s03-replay-complete",
    )
    assert completed_replay["Idempotent-Replay"] == "true"
    assert completed_replay.data == completed.data

    second_complete = _complete(
        authed_client,
        record_id,
        3,
        queue_version,
        {"acuity": "ROUTINE", "acuity_reason": ""},
        key="s03-second-complete",
    )
    assert second_complete.status_code == 409, second_complete.data
    with tenant_atomic(tenant.organisation.id):
        assert TriageRecordVersion.objects.filter(record_id=record_id).count() == 1
        assert QueueEntry.objects.filter(
            visit_id=checked_in["visit_id"], queue_type="CONSULTATION"
        ).count() == 1
        assert AuditEvent.objects.filter(
            entity_id=str(record_id), event_code="TRIAGE_COMPLETED"
        ).count() == 1


def test_s03_completion_requires_human_fields_and_allergy_status(
    tenant, authed_client, enabled_mig003_target
):
    patient_id, checked_in = _check_in(tenant, authed_client, key="s03-required-checkin")
    queue = _queue(tenant, checked_in["queue_id"])
    started = _start(authed_client, queue.id, queue.version, key="s03-required-start")
    assert started.status_code == 200, started.data
    record_id = started.data["triage_record"]["id"]
    queue_version = started.data["queue_entry"]["version"]

    saved = _save(
        authed_client,
        record_id,
        1,
        {
            "presenting_complaints": [{"text": "Headache"}],
            "observation": {"pulse": 76},
            "acuity": "ROUTINE",
        },
        key="s03-required-save",
    )
    assert saved.status_code == 200, saved.data

    missing_acuity = _complete(
        authed_client,
        record_id,
        2,
        queue_version,
        {"presenting_complaints": [{"text": "Headache"}]},
        key="s03-missing-acuity",
    )
    assert missing_acuity.status_code == 422, missing_acuity.data
    assert missing_acuity.data["code"] == "ACUITY_REQUIRED"

    no_allergy = _complete(
        authed_client,
        record_id,
        2,
        queue_version,
        {"acuity": "ROUTINE", "acuity_reason": ""},
        key="s03-no-allergy",
    )
    assert no_allergy.status_code == 422, no_allergy.data
    assert no_allergy.data["code"] == "ALLERGY_STATUS_REQUIRED"
    with tenant_atomic(tenant.organisation.id):
        assert TriageRecord.objects.get(id=record_id).state == "DRAFT"


def test_s03_under_five_weight_and_unicode_round_trip(
    tenant, authed_client, enabled_mig003_target
):
    patient_id, checked_in = _check_in(tenant, authed_client, key="s03-child-checkin")
    with tenant_atomic(tenant.organisation.id):
        patient = Patient.objects.get(id=patient_id)
        patient.date_of_birth = timezone.localdate() - timedelta(days=400)
        patient.save(update_fields=["date_of_birth", "updated_at"])
        PatientAllergyState.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=patient,
            status="NKA",
            revision=1,
            updated_by=tenant.user,
        )
    queue = _queue(tenant, checked_in["queue_id"])
    started = _start(authed_client, queue.id, queue.version, key="s03-child-start")
    assert started.status_code == 200, started.data
    record_id = started.data["triage_record"]["id"]
    queue_version = started.data["queue_entry"]["version"]

    missing_weight = _save(
        authed_client,
        record_id,
        1,
        {"observation": {"temperature_c": "37.1", "pulse": 110}},
        key="s03-child-no-weight",
    )
    assert missing_weight.status_code == 422, missing_weight.data
    assert missing_weight.data["code"] == "WEIGHT_REQUIRED_UNDER_5"

    saved = _save(
        authed_client,
        record_id,
        1,
        {
            "presenting_complaints": [{"text": "Kuharisha — 2 siku"}],
            "observation": {"temperature_c": "37.1", "pulse": 110, "weight_kg": "12.6"},
            "acuity": "ROUTINE",
        },
        key="s03-child-save",
    )
    assert saved.status_code == 200, saved.data
    assert (
        saved.data["triage_record"]["presenting_complaints"][0]["text"]
        == "Kuharisha — 2 siku"
    )
    completed = _complete(
        authed_client,
        record_id,
        2,
        queue_version,
        {"acuity": "ROUTINE", "acuity_reason": ""},
        key="s03-child-complete",
    )
    assert completed.status_code == 200, completed.data
    assert completed.data["triage_record"]["state"] == "COMPLETED"


def _restricted_client(tenant, *, username, department, codes):
    from rest_framework.test import APIClient

    user = User.objects.create_user(username, "test-password-123")
    with tenant_atomic(tenant.organisation.id):
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=user)
        role = Role.objects.create(
            organisation=tenant.organisation,
            name=f"{username} role",
            template_code=f"SCOPED_{username.upper().replace('-', '_')}",
        )
        for code in codes:
            permission, _ = Permission.objects.get_or_create(
                code=code, defaults={"name": code, "sensitivity_tier": "T1"}
            )
            RolePermission.objects.create(
                organisation=tenant.organisation, role=role, permission=permission
            )
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=user,
            role=role,
            facility=tenant.facility,
            department=department,
        )
    client = APIClient()
    response = client.post(
        "/api/v1/auth/login/",
        {
            "username": username,
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    client.defaults["HTTP_X_FACILITY_ID"] = str(tenant.facility.id)
    client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access_token"])
    return client


def test_s03_scope_and_tenant_isolation(tenant, authed_client, enabled_mig003_target):
    patient_id, checked_in = _check_in(tenant, authed_client, key="s03-scope-checkin")
    _record_allergy_status(tenant, patient_id)
    queue = _queue(tenant, checked_in["queue_id"])

    no_grant = _restricted_client(
        tenant, username="s03-no-grant", department=tenant.department, codes=["queue.view"]
    )
    denied = _start(no_grant, queue.id, queue.version, key="s03-no-grant-start")
    assert denied.status_code == 403, denied.data

    with tenant_atomic(tenant.organisation.id):
        other_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            name="S03 Other Department",
            code="S03_OTHER",
        )
    wrong_department = _restricted_client(
        tenant,
        username="s03-wrong-department",
        department=other_department,
        codes=["triage.create", "triage.read"],
    )
    denied_scope = _start(
        wrong_department, queue.id, queue.version, key="s03-wrong-department-start"
    )
    assert denied_scope.status_code == 403, denied_scope.data

    started = _start(authed_client, queue.id, queue.version, key="s03-scope-start")
    assert started.status_code == 200, started.data
    record_id = started.data["triage_record"]["id"]
    denied_read = wrong_department.get(f"/api/v1/clinic/triage-records/{record_id}/")
    assert denied_read.status_code == 403, denied_read.data

    other_organisation = Organisation.objects.create(
        name="S03 Other Tenant", slug=f"s03-other-{uuid.uuid4().hex[:8]}"
    )
    other_user = User.objects.create_user("s03-other-user", "test-password-123")
    with tenant_atomic(other_organisation.id):
        OrganisationMembership.objects.create(
            organisation=other_organisation, user=other_user
        )
        other_facility = Facility.objects.create(
            organisation=other_organisation, name="S03 Other Facility", code="S03F"
        )
        other_department = Department.objects.create(
            organisation=other_organisation,
            facility=other_facility,
            name="S03 Other Tenant Department",
            code="S03T",
        )
        role = Role.objects.create(
            organisation=other_organisation,
            name="S03 other role",
            template_code="S03_OTHER_ROLE",
        )
        for code in ("triage.create", "triage.read", "queue.view"):
            permission, _ = Permission.objects.get_or_create(
                code=code, defaults={"name": code, "sensitivity_tier": "T1"}
            )
            RolePermission.objects.create(
                organisation=other_organisation, role=role, permission=permission
            )
        UserFacilityRole.objects.create(
            organisation=other_organisation,
            user=other_user,
            role=role,
            facility=other_facility,
            department=other_department,
        )
    from rest_framework.test import APIClient

    with tenant_atomic(other_organisation.id):
        inventory_mig003(organisation=other_organisation)
        backfill_mig003(organisation=other_organisation)
        verify_mig003(organisation=other_organisation)
        verify_mig003(organisation=other_organisation)
        constrain_mig003(organisation=other_organisation)
        cutover_mig003(organisation=other_organisation)

    other_client = APIClient()
    login = other_client.post(
        "/api/v1/auth/login/",
        {
            "username": "s03-other-user",
            "password": "test-password-123",
            "organisation_id": str(other_organisation.id),
        },
        format="json",
    )
    assert login.status_code == 200, login.data
    other_client.defaults["HTTP_X_FACILITY_ID"] = str(other_facility.id)
    other_client.credentials(
        HTTP_AUTHORIZATION="Bearer " + login.data["access_token"]
    )
    cross_tenant = other_client.get(f"/api/v1/clinic/triage-records/{record_id}/")
    assert cross_tenant.status_code == 404, cross_tenant.data
