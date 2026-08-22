import json
from datetime import datetime

import pytest
from django.utils import timezone
from accounts.models import User
from audit.models import AuditEvent
from clinical.models import ClinicalNote, Encounter
from core.services import tenant_atomic
from patients.models import Patient
from tenancy.models import Facility, Organisation


pytestmark = pytest.mark.django_db

SYNTHETIC_HPI = "Phase 1J verification — synthetic HPI autosave"
SYNTHETIC_HPI_UPDATED = "Phase 1J verification — updated synthetic HPI autosave"
SYNTHETIC_GENERAL = "Phase 1J verification — synthetic general examination autosave"
SYNTHETIC_NOTE = "Phase 1J verification — synthetic development record"


def create_encounter(tenant, client, label="Phase1J"):
    patient = client.post(
        "/api/v1/patients/",
        {"first_name": label, "last_name": "Synthetic", "sex": "UNKNOWN"},
        format="json",
    )
    assert patient.status_code == 201
    check_in = client.post(
        "/api/v1/clinic/check-ins/",
        {"patient_id": patient.data["id"], "department_id": str(tenant.department.id)},
        format="json",
    )
    assert check_in.status_code == 201
    queue_id = check_in.data["id"]
    assert client.post(f"/api/v1/clinic/queue/{queue_id}/claim/", {}, format="json").status_code == 200
    triage = client.post(
        f"/api/v1/clinic/triage/{queue_id}/",
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1J verification — synthetic triage"},
        format="json",
    )
    assert triage.status_code == 201
    encounter = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": queue_id},
        format="json",
    )
    assert encounter.status_code == 201
    return encounter.data


def save_note(client, encounter_id, content, etag, *, autosave=False):
    headers = {"HTTP_IF_MATCH": etag}
    if autosave:
        headers["HTTP_X_KLINKLIK_AUTOSAVE"] = "1"
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": content},
        **headers,
        format="json",
    )


def test_phase_1j_successful_note_response_returns_persisted_saved_at(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client)
    saved = save_note(
        authed_client,
        encounter["id"],
        {"consultation": SYNTHETIC_NOTE},
        encounter["consultation_etag"],
    )

    assert saved.status_code == 200
    note = ClinicalNote.objects.get(id=saved.data["note"])
    assert saved.data["saved_at"] == note.updated_at.isoformat()
    assert saved.data["saved_at"]


def test_phase_1j_autosave_still_requires_if_match(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1JPrecondition")
    response = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/notes/",
        {"content": {"hpi": SYNTHETIC_HPI}},
        HTTP_X_KLINKLIK_AUTOSAVE="1",
        format="json",
    )

    assert response.status_code == 428
    assert response.data["code"] == "PRECONDITION_REQUIRED"
    assert not ClinicalNote.objects.filter(encounter_id=encounter["id"]).exists()


def test_phase_1j_autosave_merges_dirty_content_and_emits_one_safe_summary(tenant, authed_client, monkeypatch):
    encounter = create_encounter(tenant, authed_client, label="Phase1JAudit")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"consultation": SYNTHETIC_NOTE},
        encounter["consultation_etag"],
    )
    assert initial.status_code == 200
    note_id = initial.data["note"]
    ordinary_before = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        entity_type="ClinicalNote",
        entity_id=str(note_id),
    ).count()

    fixed_now = timezone.make_aware(datetime(2026, 8, 22, 12, 0, 15))
    monkeypatch.setattr("clinical.services.timezone.now", lambda: fixed_now)
    first = save_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI},
        initial.data["etag"],
        autosave=True,
    )
    assert first.status_code == 200
    assert first.data["content"] == {"consultation": SYNTHETIC_NOTE, "hpi": SYNTHETIC_HPI}
    assert first.data["saved_at"] == ClinicalNote.objects.get(id=note_id).updated_at.isoformat()

    second = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL},
        first.data["etag"],
        autosave=True,
    )
    assert second.status_code == 200
    assert second.data["content"] == {
        "consultation": SYNTHETIC_NOTE,
        "hpi": SYNTHETIC_HPI,
        "general_examination": SYNTHETIC_GENERAL,
    }

    summaries = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        actor=tenant.user,
        action="UPDATE",
        entity_type="Encounter",
        entity_id=encounter["id"],
    )
    assert summaries.count() == 1
    assert summaries.first().after == {
        "reason": "ENCOUNTER_DRAFT_UPDATED",
        "note_type": "CONSULTATION",
        "minute": fixed_now.replace(second=0, microsecond=0).isoformat(),
    }
    audit_json = json.dumps([event.after for event in summaries])
    assert SYNTHETIC_HPI not in audit_json
    assert SYNTHETIC_GENERAL not in audit_json
    assert AuditEvent.objects.filter(
        organisation=tenant.organisation,
        entity_type="ClinicalNote",
        entity_id=str(note_id),
    ).count() == ordinary_before


def test_phase_1j_manual_save_keeps_existing_clinical_note_audit(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1JManualAudit")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"consultation": SYNTHETIC_NOTE},
        encounter["consultation_etag"],
    )
    assert initial.status_code == 200
    note_id = initial.data["note"]
    before = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        entity_type="ClinicalNote",
        entity_id=str(note_id),
    ).count()
    updated = save_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI_UPDATED},
        initial.data["etag"],
    )

    assert updated.status_code == 200
    assert AuditEvent.objects.filter(
        organisation=tenant.organisation,
        entity_type="ClinicalNote",
        entity_id=str(note_id),
    ).count() == before + 1
    summary_events = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        entity_type="Encounter",
        entity_id=encounter["id"],
    )
    assert not any(
        (event.after or {}).get("reason") == "ENCOUNTER_DRAFT_UPDATED"
        for event in summary_events
    )


def test_phase_1j_stale_autosave_conflict_does_not_write_audit(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1JConflict")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"consultation": SYNTHETIC_NOTE},
        encounter["consultation_etag"],
    )
    assert initial.status_code == 200
    writer = save_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI},
        initial.data["etag"],
    )
    assert writer.status_code == 200
    rejected = save_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI_UPDATED},
        initial.data["etag"],
        autosave=True,
    )

    assert rejected.status_code == 409
    assert rejected.data["content"]["hpi"] == SYNTHETIC_HPI
    summary_events = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        entity_type="Encounter",
        entity_id=encounter["id"],
    )
    assert not any(
        (event.after or {}).get("reason") == "ENCOUNTER_DRAFT_UPDATED"
        for event in summary_events
    )


def test_phase_1j_note_endpoint_keeps_tenant_and_facility_isolation(tenant, authed_client):
    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="Phase 1J Other Facility",
            code="PHASE1J-OTHER",
            mode="CLINIC",
        )
        other_patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no="P-PHASE1J-OTHER-FACILITY",
            first_name="Other Facility",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        other_facility_encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            patient=other_patient,
            encounter_no="ENC-PHASE1J-OTHER-FACILITY",
            clinician=tenant.user,
        )

    assert authed_client.get(
        f"/api/v1/clinic/encounters/{other_facility_encounter.id}/"
    ).status_code == 404
    assert authed_client.post(
        f"/api/v1/clinic/encounters/{other_facility_encounter.id}/notes/",
        {"content": {"hpi": SYNTHETIC_HPI}},
        HTTP_X_KLINKLIK_AUTOSAVE="1",
        format="json",
    ).status_code == 404

    other_org = Organisation.objects.create(name="Phase 1J Other Clinic", slug="phase-1j-other-clinic")
    with tenant_atomic(other_org.id):
        other_org_facility = Facility.objects.create(
            organisation=other_org,
            name="Phase 1J Other Organisation Facility",
            code="MAIN",
            mode="CLINIC",
        )
        other_org_patient = Patient.objects.create(
            organisation=other_org,
            patient_no="P-PHASE1J-OTHER-ORG",
            first_name="Other Organisation",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        other_org_user = User.objects.create_user("phase1j-other-clinician")
        other_org_encounter = Encounter.objects.create(
            organisation=other_org,
            facility=other_org_facility,
            patient=other_org_patient,
            encounter_no="ENC-PHASE1J-OTHER-ORG",
            clinician=other_org_user,
        )

    assert authed_client.get(
        f"/api/v1/clinic/encounters/{other_org_encounter.id}/"
    ).status_code == 404
    assert authed_client.post(
        f"/api/v1/clinic/encounters/{other_org_encounter.id}/notes/",
        {"content": {"hpi": SYNTHETIC_HPI}},
        format="json",
    ).status_code == 404
