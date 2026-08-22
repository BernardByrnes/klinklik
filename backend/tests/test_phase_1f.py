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
from tests.clinical_test_helpers import note_headers


pytestmark = pytest.mark.django_db

SYNTHETIC_CARDIO = "Phase 1F verification - synthetic cardiovascular examination"
SYNTHETIC_CARDIO_UPDATED = "Phase 1F verification - updated synthetic cardiovascular examination"
SYNTHETIC_CARDIO_SIGNED = "Phase 1F verification - signed synthetic cardiovascular examination"
SYNTHETIC_RESPIRATORY = "Phase 1F verification - synthetic respiratory examination"
SYNTHETIC_RESPIRATORY_UPDATED = "Phase 1F verification - updated synthetic respiratory examination"
SYNTHETIC_RESPIRATORY_SIGNED = "Phase 1F verification - signed synthetic respiratory examination"
SYNTHETIC_GENERAL = "Phase 1F verification - synthetic general examination"


def create_encounter(tenant, client, label="Phase1F"):
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
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1F verification - synthetic triage"},
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


def save_note(client, encounter_id, content, etag):
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": content},
        **{"HTTP_IF_MATCH": etag},
        format="json",
    )


def full_content(cardio=SYNTHETIC_CARDIO, respiratory=SYNTHETIC_RESPIRATORY):
    return {
        "presenting_complaint": "Phase 1F verification - synthetic presenting complaint",
        "hpi": "Phase 1F verification - synthetic HPI",
        "past_medical_history": "Phase 1F verification - synthetic past medical history",
        "past_surgical_history": "Phase 1F verification - synthetic past surgical history",
        "family_history": "Phase 1F verification - synthetic family history",
        "social_history": "Phase 1F verification - synthetic social history",
        "general_examination": SYNTHETIC_GENERAL,
        "cardiovascular_examination": cardio,
        "respiratory_examination": respiratory,
        "consultation": "Phase 1F verification - synthetic assessment and plan note",
        "assessment": "Phase 1F verification - synthetic assessment",
        "plan": "Phase 1F verification - synthetic plan",
    }


def test_phase_1f_both_systems_round_trip_association_and_audit(tenant, authed_client):
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
    assert SYNTHETIC_CARDIO not in audit_json
    assert SYNTHETIC_RESPIRATORY not in audit_json
    assert "cardiovascular_examination" in audit_json
    assert "respiratory_examination" in audit_json


@pytest.mark.parametrize("field_name", ["cardiovascular_examination", "respiratory_examination"])
def test_phase_1f_exactly_2000_characters_are_accepted(tenant, authed_client, field_name):
    encounter = create_encounter(tenant, authed_client, label=f"Phase1FLimit{field_name}")
    value = "x" * 2000
    saved = save_note(authed_client, encounter["id"], {field_name: value}, encounter["consultation_etag"])

    assert saved.status_code == 200
    assert saved.data["content"][field_name] == value
    assert len(ClinicalNote.objects.get(id=saved.data["note"]).content[field_name]) == 2000


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("cardiovascular_examination", "x" * 2001),
        ("respiratory_examination", "x" * 2001),
        ("cardiovascular_examination", 42),
        ("respiratory_examination", ["Phase 1F verification - invalid synthetic value"]),
    ],
)
def test_phase_1f_invalid_type_or_length_is_rejected_without_truncation(
    tenant, authed_client, field_name, invalid_value
):
    encounter = create_encounter(tenant, authed_client, label=f"Phase1FInvalid{field_name}")
    response = save_note(
        authed_client,
        encounter["id"],
        {field_name: invalid_value},
        encounter["consultation_etag"],
    )

    assert response.status_code == 400
    assert field_name in response.data["content"]
    assert not ClinicalNote.objects.filter(encounter_id=encounter["id"]).exists()


def test_phase_1f_partial_cardiovascular_and_respiratory_saves_preserve_all_content(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1FPartial")
    initial = full_content()
    saved = save_note(authed_client, encounter["id"], initial, encounter["consultation_etag"])
    assert saved.status_code == 200

    cardio_update = save_note(
        authed_client,
        encounter["id"],
        {"cardiovascular_examination": SYNTHETIC_CARDIO_UPDATED},
        saved.data["etag"],
    )
    assert cardio_update.status_code == 200
    expected_after_cardio = {**initial, "cardiovascular_examination": SYNTHETIC_CARDIO_UPDATED}
    assert cardio_update.data["content"] == expected_after_cardio

    respiratory_update = save_note(
        authed_client,
        encounter["id"],
        {"respiratory_examination": SYNTHETIC_RESPIRATORY_UPDATED},
        cardio_update.data["etag"],
    )
    assert respiratory_update.status_code == 200
    assert respiratory_update.data["content"] == {
        **expected_after_cardio,
        "respiratory_examination": SYNTHETIC_RESPIRATORY_UPDATED,
    }


def test_phase_1f_other_field_update_preserves_both_system_examinations(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1FOtherField")
    initial = full_content()
    saved = save_note(authed_client, encounter["id"], initial, encounter["consultation_etag"])
    updated = save_note(
        authed_client,
        encounter["id"],
        {"hpi": "Phase 1F verification - updated synthetic HPI"},
        saved.data["etag"],
    )

    assert updated.status_code == 200
    assert updated.data["content"]["cardiovascular_examination"] == SYNTHETIC_CARDIO
    assert updated.data["content"]["respiratory_examination"] == SYNTHETIC_RESPIRATORY


def test_phase_1f_missing_if_match_fails_closed(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1FPrecondition")
    response = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/notes/",
        {"content": {"cardiovascular_examination": SYNTHETIC_CARDIO}},
        format="json",
    )

    assert response.status_code == 428
    assert response.data["code"] == "PRECONDITION_REQUIRED"
    assert not ClinicalNote.objects.filter(encounter_id=encounter["id"]).exists()


def test_phase_1f_same_field_stale_write_is_rejected_without_overwrite(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1FSameField")
    baseline = save_note(
        authed_client,
        encounter["id"],
        {"cardiovascular_examination": SYNTHETIC_CARDIO},
        encounter["consultation_etag"],
    )
    latest = save_note(
        authed_client,
        encounter["id"],
        {"cardiovascular_examination": SYNTHETIC_CARDIO_UPDATED},
        baseline.data["etag"],
    )
    conflict = save_note(
        authed_client,
        encounter["id"],
        {"cardiovascular_examination": "Phase 1F verification - stale synthetic cardiovascular examination"},
        baseline.data["etag"],
    )

    assert latest.status_code == 200
    assert conflict.status_code == 409
    assert conflict.data["content"]["cardiovascular_examination"] == SYNTHETIC_CARDIO_UPDATED
    assert ClinicalNote.objects.get(id=latest.data["note"]).content["cardiovascular_examination"] == SYNTHETIC_CARDIO_UPDATED


def test_phase_1f_non_overlap_stale_retry_preserves_both_writers(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1FNonOverlap")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL, "respiratory_examination": SYNTHETIC_RESPIRATORY},
        encounter["consultation_etag"],
    )
    writer_a = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": "Phase 1F verification - updated synthetic general examination"},
        initial.data["etag"],
    )
    stale = save_note(
        authed_client,
        encounter["id"],
        {"respiratory_examination": SYNTHETIC_RESPIRATORY_UPDATED},
        initial.data["etag"],
    )
    retry = save_note(
        authed_client,
        encounter["id"],
        {"respiratory_examination": SYNTHETIC_RESPIRATORY_UPDATED},
        stale.data["etag"],
    )

    assert writer_a.status_code == 200
    assert stale.status_code == 409
    assert retry.status_code == 200
    assert retry.data["content"] == {
        "general_examination": "Phase 1F verification - updated synthetic general examination",
        "respiratory_examination": SYNTHETIC_RESPIRATORY_UPDATED,
    }


def test_phase_1f_sign_preserves_both_systems_and_version_content(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1FSign")
    initial = save_note(
        authed_client,
        encounter["id"],
        full_content(),
        encounter["consultation_etag"],
    )
    signed_content = {
        "cardiovascular_examination": SYNTHETIC_CARDIO_SIGNED,
        "respiratory_examination": SYNTHETIC_RESPIRATORY_SIGNED,
    }
    signed = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": signed_content},
        **{"HTTP_IF_MATCH": initial.data["etag"]},
        format="json",
    )
    expected = {**full_content(), **signed_content}

    assert signed.status_code == 200
    assert signed.data["content"] == expected
    assert ClinicalNoteVersion.objects.get(note_id=signed.data["note"]).content == expected
    assert Encounter.objects.get(id=encounter["id"]).status == "SIGNED"

    rejected = save_note(
        authed_client,
        encounter["id"],
        {"cardiovascular_examination": "Phase 1F verification - rejected post-sign synthetic write"},
        signed.data["etag"],
    )
    assert rejected.status_code == 400
    assert ClinicalNote.objects.get(id=signed.data["note"]).content == expected


def test_phase_1f_stale_sign_preserves_draft_and_requires_fresh_retry(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1FStaleSign")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"cardiovascular_examination": SYNTHETIC_CARDIO, "respiratory_examination": SYNTHETIC_RESPIRATORY},
        encounter["consultation_etag"],
    )
    latest = save_note(
        authed_client,
        encounter["id"],
        {"cardiovascular_examination": SYNTHETIC_CARDIO_UPDATED},
        initial.data["etag"],
    )
    stale_sign = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": {"respiratory_examination": SYNTHETIC_RESPIRATORY_SIGNED}, "complaints": [{"text": "Phase 1L-A compatibility synthetic complaint", "duration_value": None, "duration_unit": None}]},
        **{"HTTP_IF_MATCH": initial.data["etag"]},
        format="json",
    )

    assert latest.status_code == 200
    assert stale_sign.status_code == 409
    assert stale_sign.data["status"] == "DRAFT"
    assert stale_sign.data["encounter_status"] == "OPEN"
    assert stale_sign.data["content"]["cardiovascular_examination"] == SYNTHETIC_CARDIO_UPDATED
    assert ClinicalNote.objects.get(id=latest.data["note"]).status == "DRAFT"

    fresh_sign = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": {"respiratory_examination": SYNTHETIC_RESPIRATORY_SIGNED}, "complaints": [{"text": "Phase 1L-A compatibility synthetic complaint", "duration_value": None, "duration_unit": None}]},
        **{"HTTP_IF_MATCH": stale_sign.data["etag"]},
        format="json",
    )
    assert fresh_sign.status_code == 200
    assert fresh_sign.data["content"] == {
        "cardiovascular_examination": SYNTHETIC_CARDIO_UPDATED,
        "respiratory_examination": SYNTHETIC_RESPIRATORY_SIGNED,
    }


def test_phase_1f_non_clinical_role_cannot_edit_system_examination(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1FRole")
    nurse = User.objects.create_user("phase1f-nurse")
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
        {"content": {"respiratory_examination": SYNTHETIC_RESPIRATORY}},
        format="json",
    )

    assert response.status_code == 403


def test_phase_1f_facility_and_tenant_isolation(tenant, authed_client):
    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="Phase 1F Other Facility",
            code="OTHER",
            mode="CLINIC",
        )
        facility_patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no="P-OTHER-FACILITY-PHASE1F",
            first_name="Other Facility",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        facility_encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            patient=facility_patient,
            encounter_no="ENC-OTHER-FACILITY-PHASE1F",
            clinician=tenant.user,
        )

    facility_url = f"/api/v1/clinic/encounters/{facility_encounter.id}"
    assert authed_client.get(facility_url + "/").status_code == 404
    assert authed_client.post(
        facility_url + "/notes/",
        {"content": {"cardiovascular_examination": SYNTHETIC_CARDIO}},
        format="json",
    ).status_code == 404

    other_org = Organisation.objects.create(name="Other Phase 1F Clinic", slug="other-phase-1f")
    with tenant_atomic(other_org.id):
        other_facility = Facility.objects.create(
            organisation=other_org,
            name="Other Facility",
            code="MAIN",
            mode="CLINIC",
        )
        other_patient = Patient.objects.create(
            organisation=other_org,
            patient_no="P-OTHER-ORG-PHASE1F",
            first_name="Other Organisation",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        other_user = User.objects.create_user("phase1f-other")
        other_encounter = Encounter.objects.create(
            organisation=other_org,
            facility=other_facility,
            patient=other_patient,
            encounter_no="ENC-OTHER-ORG-PHASE1F",
            clinician=other_user,
        )

    other_url = f"/api/v1/clinic/encounters/{other_encounter.id}"
    assert authed_client.get(other_url + "/").status_code == 404
    assert authed_client.post(
        other_url + "/notes/",
        {"content": {"respiratory_examination": SYNTHETIC_RESPIRATORY}},
        format="json",
    ).status_code == 404
