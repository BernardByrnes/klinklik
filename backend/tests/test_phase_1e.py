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
from tests.clinical_test_helpers import establish_synthetic_nka_review, note_headers


pytestmark = pytest.mark.django_db

SYNTHETIC_EXAMINATION = "Phase 1E verification - synthetic development general examination"
SYNTHETIC_EXAMINATION_UPDATED = "Phase 1E verification - updated synthetic development general examination"
SYNTHETIC_EXAMINATION_SIGNED = "Phase 1E verification - signed synthetic development general examination"
SYNTHETIC_EXAMINATION_AMENDED = "Phase 1E verification - amended synthetic development general examination"
SYNTHETIC_HPI = "Phase 1E verification - synthetic HPI"
SYNTHETIC_FAMILY = "Phase 1E verification - synthetic family history"
SYNTHETIC_PLAN = "Phase 1E verification - synthetic plan"


def create_encounter(tenant, client, label="Phase1E"):
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
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1E verification - synthetic triage"},
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
    return encounter.data


def save_note(client, encounter_id, content, etag):
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": content},
        **{"HTTP_IF_MATCH": etag},
        format="json",
    )


def full_content(general_examination=SYNTHETIC_EXAMINATION):
    return {
        "presenting_complaint": "Phase 1E verification - synthetic presenting complaint",
        "hpi": SYNTHETIC_HPI,
        "past_medical_history": "Phase 1E verification - synthetic past medical history",
        "past_surgical_history": "Phase 1E verification - synthetic past surgical history",
        "family_history": SYNTHETIC_FAMILY,
        "social_history": "Phase 1E verification - synthetic social history",
        "general_examination": general_examination,
        "consultation": "Phase 1E verification - synthetic assessment and plan note",
        "assessment": "Phase 1E verification - synthetic assessment",
        "plan": SYNTHETIC_PLAN,
    }


def test_phase_1e_general_examination_round_trip_association_reload_and_audit(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client)
    content = full_content()
    saved = save_note(authed_client, encounter["id"], content, encounter["consultation_etag"])

    assert saved.status_code == 200
    note_id = saved.data["note"]
    note = ClinicalNote.objects.get(id=note_id)
    assert str(note.encounter_id) == encounter["id"]
    assert note.content == content

    reloaded = authed_client.get(f"/api/v1/clinic/encounters/{encounter['id']}/")
    assert reloaded.status_code == 200
    assert reloaded.data["notes"][0]["content"] == content

    audit_json = json.dumps(
        [
            {"before": event.before, "after": event.after, "reason": event.reason}
            for event in AuditEvent.objects.filter(
                organisation=tenant.organisation,
                entity_type="ClinicalNote",
                entity_id=note_id,
            )
        ]
    )
    assert SYNTHETIC_EXAMINATION not in audit_json
    assert "general_examination" in audit_json


def test_phase_1e_partial_general_examination_update_preserves_existing_note_fields(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1EPartial")
    initial = full_content()
    saved = save_note(authed_client, encounter["id"], initial, encounter["consultation_etag"])
    assert saved.status_code == 200

    updated = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_EXAMINATION_UPDATED},
        saved.data["etag"],
    )
    assert updated.status_code == 200
    assert updated.data["content"] == {
        **initial,
        "general_examination": SYNTHETIC_EXAMINATION_UPDATED,
    }


def test_phase_1e_general_examination_accepts_exactly_2000_characters(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1ELimit")
    value = "x" * 2000
    saved = save_note(authed_client, encounter["id"], {"general_examination": value}, encounter["consultation_etag"])

    assert saved.status_code == 200
    assert saved.data["content"]["general_examination"] == value
    assert len(ClinicalNote.objects.get(id=saved.data["note"]).content["general_examination"]) == 2000


@pytest.mark.parametrize(
    "invalid_value",
    [42, ["Phase 1E verification - invalid synthetic value"]],
)
def test_phase_1e_general_examination_rejects_non_string_without_creating_note(tenant, authed_client, invalid_value):
    encounter = create_encounter(tenant, authed_client, label="Phase1EType")
    response = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": invalid_value},
        encounter["consultation_etag"],
    )

    assert response.status_code == 400
    assert "general_examination" in response.data["content"]
    assert not ClinicalNote.objects.filter(encounter_id=encounter["id"]).exists()


def test_phase_1e_general_examination_rejects_2001_characters_without_truncation(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1ETooLong")
    value = "x" * 2001
    response = save_note(authed_client, encounter["id"], {"general_examination": value}, encounter["consultation_etag"])

    assert response.status_code == 400
    assert "general_examination" in response.data["content"]
    assert not ClinicalNote.objects.filter(encounter_id=encounter["id"]).exists()


def test_phase_1e_missing_if_match_fails_closed_for_general_examination(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1EPrecondition")
    response = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/notes/",
        {"content": {"general_examination": SYNTHETIC_EXAMINATION}},
        format="json",
    )

    assert response.status_code == 428
    assert response.data["code"] == "PRECONDITION_REQUIRED"
    assert not ClinicalNote.objects.filter(encounter_id=encounter["id"]).exists()


def test_phase_1e_stale_same_field_write_returns_current_value_without_overwrite(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1ESameField")
    baseline = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_EXAMINATION},
        encounter["consultation_etag"],
    )
    latest = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_EXAMINATION_UPDATED},
        baseline.data["etag"],
    )
    conflict = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": "Phase 1E verification - stale synthetic examination"},
        baseline.data["etag"],
    )

    assert latest.status_code == 200
    assert conflict.status_code == 409
    assert conflict.data["content"]["general_examination"] == SYNTHETIC_EXAMINATION_UPDATED
    assert ClinicalNote.objects.get(id=latest.data["note"]).content["general_examination"] == SYNTHETIC_EXAMINATION_UPDATED


def test_phase_1e_stale_non_overlapping_retry_preserves_hpi_and_general_examination(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1ENonOverlap")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI, "general_examination": SYNTHETIC_EXAMINATION},
        encounter["consultation_etag"],
    )
    writer_a = save_note(
        authed_client,
        encounter["id"],
        {"hpi": "Phase 1E verification - updated synthetic HPI"},
        initial.data["etag"],
    )
    stale = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_EXAMINATION_UPDATED},
        initial.data["etag"],
    )
    retry = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_EXAMINATION_UPDATED},
        stale.data["etag"],
    )

    assert writer_a.status_code == 200
    assert stale.status_code == 409
    assert retry.status_code == 200
    assert retry.data["content"] == {
        "hpi": "Phase 1E verification - updated synthetic HPI",
        "general_examination": SYNTHETIC_EXAMINATION_UPDATED,
    }


def test_phase_1e_sign_persists_exact_text_and_rejects_post_sign_write(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1ESign")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI, "general_examination": SYNTHETIC_EXAMINATION},
        encounter["consultation_etag"],
    )
    signed = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": {"general_examination": SYNTHETIC_EXAMINATION_SIGNED}, "complaints": [{"text": "Phase 1L-A compatibility synthetic complaint", "duration_value": None, "duration_unit": None}]},
        **{"HTTP_IF_MATCH": initial.data["etag"]},
        format="json",
    )

    assert signed.status_code == 200
    assert signed.data["content"] == {
        "hpi": SYNTHETIC_HPI,
        "general_examination": SYNTHETIC_EXAMINATION_SIGNED,
    }
    assert ClinicalNoteVersion.objects.get(note_id=signed.data["note"]).content == signed.data["content"]
    assert Encounter.objects.get(id=encounter["id"]).status == "SIGNED"

    rejected = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": "Phase 1E verification - rejected post-sign synthetic write"},
        signed.data["etag"],
    )
    assert rejected.status_code == 400
    assert ClinicalNote.objects.get(id=signed.data["note"]).content == signed.data["content"]


def test_phase_1e_amendment_preserves_prior_version_and_exact_examination_text(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1EAmend")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_EXAMINATION},
        encounter["consultation_etag"],
    )
    signed = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": {}, "complaints": [{"text": "Phase 1L-A compatibility synthetic complaint", "duration_value": None, "duration_unit": None}]},
        **{"HTTP_IF_MATCH": initial.data["etag"]},
        format="json",
    )
    amended = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/amend/",
        {
            "content": {"general_examination": SYNTHETIC_EXAMINATION_AMENDED},
            "reason": "Phase 1E verification - synthetic amendment reason",
        },
        **{"HTTP_IF_MATCH": signed.data["etag"]},
        format="json",
    )

    assert signed.status_code == 200
    assert amended.status_code == 200
    assert amended.data["status"] == "AMENDED"
    assert amended.data["current_version"] == 2
    assert amended.data["content"] == {"general_examination": SYNTHETIC_EXAMINATION_AMENDED}
    assert ClinicalNoteVersion.objects.filter(note_id=amended.data["note"]).count() == 2


def test_phase_1e_non_clinical_role_cannot_edit_general_examination(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1ERole")
    nurse = User.objects.create_user("phase1e-nurse")
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
        f"/api/v1/clinic/encounters/{encounter['id']}/notes/",
        {"content": {"general_examination": SYNTHETIC_EXAMINATION}},
        format="json",
    )

    assert response.status_code == 403


def test_phase_1e_facility_and_tenant_isolation(tenant, authed_client):
    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="Phase 1E Other Facility",
            code="OTHER",
            mode="CLINIC",
        )
        facility_patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no="P-OTHER-FACILITY-PHASE1E",
            first_name="Other Facility",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        facility_encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            patient=facility_patient,
            encounter_no="ENC-OTHER-FACILITY-PHASE1E",
            clinician=tenant.user,
        )

    facility_url = f"/api/v1/clinic/encounters/{facility_encounter.id}"
    assert authed_client.get(facility_url + "/").status_code == 404
    assert authed_client.post(
        facility_url + "/notes/",
        {"content": {"general_examination": SYNTHETIC_EXAMINATION}},
        format="json",
    ).status_code == 404

    other_org = Organisation.objects.create(name="Other Phase 1E Clinic", slug="other-phase-1e")
    with tenant_atomic(other_org.id):
        other_facility = Facility.objects.create(
            organisation=other_org,
            name="Other Facility",
            code="MAIN",
            mode="CLINIC",
        )
        other_patient = Patient.objects.create(
            organisation=other_org,
            patient_no="P-OTHER-ORG-PHASE1E",
            first_name="Other Organisation",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        other_user = User.objects.create_user("phase1e-other")
        other_encounter = Encounter.objects.create(
            organisation=other_org,
            facility=other_facility,
            patient=other_patient,
            encounter_no="ENC-OTHER-ORG-PHASE1E",
            clinician=other_user,
        )

    other_url = f"/api/v1/clinic/encounters/{other_encounter.id}"
    assert authed_client.get(other_url + "/").status_code == 404
    assert authed_client.post(
        other_url + "/notes/",
        {"content": {"general_examination": SYNTHETIC_EXAMINATION}},
        format="json",
    ).status_code == 404
