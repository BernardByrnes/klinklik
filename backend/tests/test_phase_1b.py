import json

import pytest
from rest_framework.test import APIClient

from accounts.bootstrap import open_session
from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from audit.models import AuditEvent
from clinical.models import ClinicalNote, ClinicalNoteVersion, Encounter
from core.services import tenant_atomic
from patients.models import Patient
from tenancy.models import Facility, Organisation

from tests.clinical_test_helpers import establish_synthetic_final_diagnosis, establish_synthetic_nka_review, note_headers


pytestmark = pytest.mark.django_db

SYNTHETIC_COMPLAINT = "Phase 1B verification — synthetic presenting complaint"
SYNTHETIC_HPI = "Phase 1B verification — synthetic HPI\nSecond synthetic line."
SYNTHETIC_ASSESSMENT_PLAN = "Phase 1B verification — synthetic assessment and plan."


def create_encounter(tenant, client, label="Phase1B"):
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
        {"acuity": "ROUTINE", "chief_complaint": "Synthetic triage complaint"},
        format="json",
    )
    assert triage.status_code == 201
    encounter = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": queue_id},
        format="json",
    )
    assert encounter.status_code == 201
    establish_synthetic_nka_review(client, encounter.data["id"])
    establish_synthetic_final_diagnosis(client, encounter.data["id"])
    return encounter.data["id"]


def note_content(hpi=SYNTHETIC_HPI):
    return {
        "presenting_complaint": SYNTHETIC_COMPLAINT,
        "hpi": hpi,
        "consultation": SYNTHETIC_ASSESSMENT_PLAN,
    }


def test_phase_1b_draft_round_trip_audit_and_signed_immutability(tenant, authed_client):
    encounter_id = create_encounter(tenant, authed_client)
    content = note_content()

    saved = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": content},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert saved.status_code == 200
    assert saved.data["content"] == content

    updated_content = note_content("Phase 1B verification — updated synthetic HPI.")
    updated = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": updated_content},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert updated.status_code == 200
    reloaded = authed_client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert reloaded.status_code == 200
    assert reloaded.data["notes"][0]["content"] == updated_content

    update_audit = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        entity_type="ClinicalNote",
        entity_id=updated.data["note"],
        action="UPDATE",
    ).latest("occurred_at")
    audit_json = json.dumps({"before": update_audit.before, "after": update_audit.after})
    assert SYNTHETIC_COMPLAINT not in audit_json
    assert "updated synthetic HPI" not in audit_json
    assert "presenting_complaint" in audit_json
    assert "hpi" in audit_json

    signed = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": updated_content},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert signed.status_code == 200
    assert Encounter.objects.get(id=encounter_id).status == "SIGNED"
    assert ClinicalNoteVersion.objects.filter(note__encounter_id=encounter_id).count() == 1

    rejected = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": note_content("Phase 1B verification — rejected synthetic overwrite.")},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert rejected.status_code == 400
    unchanged = authed_client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert unchanged.status_code == 200
    assert unchanged.data["notes"][0]["content"] == updated_content


def test_phase_1b_content_limits_are_server_enforced(tenant, authed_client):
    encounter_id = create_encounter(tenant, authed_client, label="Phase1BLimit")
    response = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"presenting_complaint": "x" * 501, "hpi": ""}},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert response.status_code == 400
    assert not ClinicalNote.objects.filter(encounter_id=encounter_id).exists()


def test_phase_1b_encounter_and_note_are_tenant_isolated(tenant, authed_client):
    other_org = Organisation.objects.create(name="Other Phase 1B Clinic", slug="other-phase-1b")
    with tenant_atomic(other_org.id):
        other_facility = Facility.objects.create(
            organisation=other_org, name="Other Facility", code="MAIN", mode="CLINIC"
        )
        other_patient = Patient.objects.create(
            organisation=other_org,
            patient_no="P-OTHER-PHASE1B",
            first_name="Other",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        other_user = User.objects.create_user("phase1b-other")
        other_encounter = Encounter.objects.create(
            organisation=other_org,
            facility=other_facility,
            patient=other_patient,
            encounter_no="ENC-OTHER-PHASE1B",
            clinician=other_user,
        )

    encounter_url = f"/api/v1/clinic/encounters/{other_encounter.id}/"
    notes_url = f"/api/v1/clinic/encounters/{other_encounter.id}/notes/"
    assert authed_client.get(encounter_url).status_code == 404
    assert authed_client.post(notes_url, {"content": note_content()}, format="json").status_code == 404


def test_phase_1b_non_clinical_role_cannot_edit_notes(tenant, authed_client):
    encounter_id = create_encounter(tenant, authed_client, label="Phase1BRole")
    nurse = User.objects.create_user("phase1b-nurse")
    with tenant_atomic(tenant.organisation.id):
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=nurse)
        role = Role.objects.get(organisation=tenant.organisation, template_code="NURSE_TRIAGE")
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=nurse,
            role=role,
            facility=tenant.facility,
            department=tenant.department,
        )

    nurse_client = APIClient()
    opened = open_session(nurse, tenant.organisation.id)
    nurse_client.credentials(
        HTTP_AUTHORIZATION="Bearer " + opened.access_token,
        HTTP_X_FACILITY_ID=str(tenant.facility.id),
    )
    response = nurse_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": note_content()},
        format="json",
    )
    assert response.status_code == 403
