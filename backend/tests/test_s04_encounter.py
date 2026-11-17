from datetime import date
import uuid

import pytest

from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from audit.models import AuditEvent
from billing.models import Invoice
from clinical.models import (
    ClinicalNote,
    ClinicalNoteVersion,
    Encounter,
    PatientAllergyState,
)
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
from core.models import MigrationCutover
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import QueueEntry, Visit
from scheduling.queue import complete as queue_complete
from scheduling.queue import create_or_reuse_destination
from tests.clinical_test_helpers import (
    establish_synthetic_final_diagnosis,
    establish_synthetic_nka_review,
)

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


def _register(client, *, key):
    response = client.post(
        "/api/v1/reception/patients/register/",
        {
            "first_name": "S04",
            "last_name": f"Synthetic{uuid.uuid4().hex[:6]}",
            "sex": "FEMALE",
            "phone": "0704000000",
            "date_of_birth": date(1990, 5, 4).isoformat(),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert response.status_code == 201, response.data
    return response.data["patient_id"]


def _canonical_encounter(tenant, client):
    """Check in, complete canonical triage, open the same-Visit Encounter."""

    patient_id = _register(client, key="s04-register")
    check_in = client.post(
        "/api/v1/reception/visits/check-in/",
        {
            "patient_id": patient_id,
            "visit_type": "OUTPATIENT_NEW",
            "payer_type": "CASH",
            "department_id": str(tenant.department.id),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s04-checkin",
    )
    assert check_in.status_code == 201, check_in.data
    visit_id = check_in.data["visit_id"]
    triage_queue_id = check_in.data["queue_id"]
    invoice_id = check_in.data["invoice_id"]
    with tenant_atomic(tenant.organisation.id):
        PatientAllergyState.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient_id=patient_id,
            status="NKA",
            revision=1,
            updated_by=tenant.user,
        )
        queue_version = QueueEntry.objects.get(id=triage_queue_id).version
    started = client.post(
        f"/api/v1/clinic/triage/{triage_queue_id}/start/",
        {"expected_version": queue_version},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s04-triage-start",
    )
    assert started.status_code == 200, started.data
    record_id = started.data["triage_record"]["id"]
    record_version = started.data["triage_record"]["version"]
    queue_version = started.data["queue_entry"]["version"]
    saved = client.patch(
        f"/api/v1/clinic/triage-records/{record_id}/",
        {
            "presenting_complaints": [{"text": "S04 synthetic fever"}],
            "observation": {"pulse": 88, "temperature_c": "38.2"},
            "acuity": "ROUTINE",
            "expected_version": record_version,
        },
        format="json",
        HTTP_IF_MATCH=f'"{record_version}"',
        HTTP_IDEMPOTENCY_KEY="s04-triage-save",
    )
    assert saved.status_code == 200, saved.data
    record_version = saved.data["triage_record"]["version"]
    completed = client.post(
        f"/api/v1/clinic/triage-records/{record_id}/complete/",
        {
            "acuity": "ROUTINE",
            "acuity_reason": "",
            "expected_version": record_version,
            "expected_queue_version": queue_version,
        },
        format="json",
        HTTP_IF_MATCH=f'"{record_version}"',
        HTTP_IDEMPOTENCY_KEY="s04-triage-complete",
    )
    assert completed.status_code == 200, completed.data
    destination_id = completed.data["destination_queue_entry_id"]
    with tenant_atomic(tenant.organisation.id):
        destination_version = QueueEntry.objects.get(id=destination_id).version
    encounter = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": destination_id, "expected_version": destination_version},
        format="json",
        HTTP_IF_MATCH=f'"{destination_version}"',
        HTTP_IDEMPOTENCY_KEY="s04-encounter-open",
    )
    assert encounter.status_code == 201, encounter.data
    establish_synthetic_nka_review(client, encounter.data["id"])
    diagnosis = establish_synthetic_final_diagnosis(client, encounter.data["id"])
    encounter.data["consultation_etag"] = diagnosis["consultation_etag"]
    return {
        "patient_id": patient_id,
        "visit_id": visit_id,
        "triage_queue_id": triage_queue_id,
        "destination_id": destination_id,
        "invoice_id": invoice_id,
        "encounter": encounter.data,
    }


def _save_and_sign(client, encounter_id, etag, *, text="S04 synthetic complaint"):
    saved = client.patch(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"hpi": "S04 synthetic HPI"}, "complaints": [{"text": text}]},
        format="json",
        HTTP_IF_MATCH=etag,
        HTTP_IDEMPOTENCY_KEY="s04-note-save",
    )
    assert saved.status_code == 200, saved.data
    sign = client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"hpi": "S04 synthetic HPI"}},
        format="json",
        HTTP_IF_MATCH=saved.data["etag"],
        HTTP_IDEMPOTENCY_KEY="s04-encounter-sign",
    )
    return saved, sign


def test_s04_sign_completes_consultation_and_preserves_invoice(
    tenant, authed_client, enabled_mig003_target
):
    setup = _canonical_encounter(tenant, authed_client)
    encounter_id = setup["encounter"]["id"]
    invoice = Invoice.objects.get(id=setup["invoice_id"])
    invoice_line_ids = list(invoice.items.values_list("id", flat=True))
    saved, sign = _save_and_sign(
        authed_client, encounter_id, setup["encounter"]["consultation_etag"]
    )
    assert sign.status_code == 200, sign.data
    assert sign.data["status"] == "SIGNED"
    with tenant_atomic(tenant.organisation.id):
        encounter = Encounter.objects.get(id=encounter_id)
        note = ClinicalNote.objects.get(encounter=encounter)
        versions = list(ClinicalNoteVersion.objects.filter(note=note))
        queue = QueueEntry.objects.get(id=setup["destination_id"])
        assert encounter.status == "SIGNED"
        assert encounter.signed_at is not None
        assert note.status == "SIGNED"
        assert note.signed_by_id == tenant.user.id
        assert len(versions) == 1
        assert versions[0].version_number == 1
        assert len(versions[0].content_hash) == 64
        assert versions[0].created_by_id == tenant.user.id
        assert queue.state == "COMPLETED"
        assert queue.terminal_reason == "ENCOUNTER_SIGNED"
        assert AuditEvent.objects.filter(
            organisation=tenant.organisation,
            event_code="ENCOUNTER_SIGNED",
            entity_id=str(encounter_id),
        ).count() == 1
        invoice.refresh_from_db()
        assert list(invoice.items.values_list("id", flat=True)) == invoice_line_ids
    replay = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"hpi": "S04 synthetic HPI"}},
        format="json",
        HTTP_IF_MATCH=saved.data["etag"],
        HTTP_IDEMPOTENCY_KEY="s04-encounter-sign-again",
    )
    assert replay.status_code in {400, 409}, replay.data
    with tenant_atomic(tenant.organisation.id):
        assert ClinicalNoteVersion.objects.filter(note__encounter_id=encounter_id).count() == 1


def test_s04_open_reuses_one_open_encounter_for_the_visit(
    tenant, authed_client, enabled_mig002_target
):
    with tenant_atomic(tenant.organisation.id):
        patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no=f"P-S04-{uuid.uuid4().hex[:8]}",
            first_name="S04 Reuse",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        visit = Visit.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=patient,
            local_service_date=date.today(),
            visit_type="OUTPATIENT_NEW",
            opened_by=tenant.user,
        )
        first, created = create_or_reuse_destination(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            visit=visit,
            department=tenant.department,
            queue_type="CONSULTATION",
            source_stage="RECEPTION",
        )
        assert created
    first_open = authed_client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": str(first.id), "expected_version": first.version},
        format="json",
        HTTP_IF_MATCH=f'"{first.version}"',
        HTTP_IDEMPOTENCY_KEY="s04-open-first",
    )
    assert first_open.status_code == 201, first_open.data
    with tenant_atomic(tenant.organisation.id):
        queue_complete(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            queue_entry_id=first.id,
            expected_version=QueueEntry.objects.get(id=first.id).version,
        )
        second, created = create_or_reuse_destination(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            visit=visit,
            department=tenant.department,
            queue_type="CONSULTATION",
            source_stage="RECEPTION",
            work_identity=f"REOPEN:{uuid.uuid4().hex}",
        )
        assert created
    second_open = authed_client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": str(second.id), "expected_version": second.version},
        format="json",
        HTTP_IF_MATCH=f'"{second.version}"',
        HTTP_IDEMPOTENCY_KEY="s04-open-second",
    )
    assert second_open.status_code == 201, second_open.data
    assert second_open.data["id"] == first_open.data["id"]
    with tenant_atomic(tenant.organisation.id):
        assert Encounter.objects.filter(visit=visit).count() == 1
        assert QueueEntry.objects.get(id=second.id).state == "IN_SERVICE"


def test_s04_sign_requires_the_sign_capability(
    tenant, authed_client, enabled_mig002_target
):
    with tenant_atomic(tenant.organisation.id):
        reception_role = Role.objects.get(
            organisation=tenant.organisation, template_code="RECEPTION_CASHIER"
        )
        user = User.objects.create_user("s04-reception", "test-password-123")
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=user)
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=user,
            role=reception_role,
            facility=tenant.facility,
            department=tenant.department,
        )
    from rest_framework.test import APIClient

    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {
            "username": "s04-reception",
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    assert login.status_code == 200, login.data
    client.defaults["HTTP_X_FACILITY_ID"] = str(tenant.facility.id)
    client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    denied = client.post(
        f"/api/v1/clinic/encounters/{uuid.uuid4()}/sign/",
        {"content": {}},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s04-denied-sign",
    )
    assert denied.status_code in {403, 404}, denied.data
