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
from tests.clinical_test_helpers import establish_synthetic_final_diagnosis, establish_synthetic_nka_review

pytestmark = pytest.mark.django_db

SYNTHETIC_ABDOMINAL = "Phase 1H verification - synthetic abdominal examination"
SYNTHETIC_ABDOMINAL_UPDATED = "Phase 1H verification - updated synthetic abdominal examination"
SYNTHETIC_ABDOMINAL_SIGNED = "Phase 1H verification - signed synthetic abdominal examination"
SYNTHETIC_NEUROLOGICAL = "Phase 1H verification - synthetic neurological examination"
SYNTHETIC_NEUROLOGICAL_UPDATED = "Phase 1H verification - updated synthetic neurological examination"
SYNTHETIC_NEUROLOGICAL_SIGNED = "Phase 1H verification - signed synthetic neurological examination"
SYNTHETIC_GENITOURINARY = "Phase 1H verification - synthetic genitourinary examination"
SYNTHETIC_GENITOURINARY_UPDATED = "Phase 1H verification - updated synthetic genitourinary examination"
SYNTHETIC_GENITOURINARY_SIGNED = "Phase 1H verification - signed synthetic genitourinary examination"
SYNTHETIC_MUSCULOSKELETAL = "Phase 1H verification - synthetic musculoskeletal examination"
SYNTHETIC_MUSCULOSKELETAL_UPDATED = "Phase 1H verification - updated synthetic musculoskeletal examination"
SYNTHETIC_MUSCULOSKELETAL_SIGNED = "Phase 1H verification - signed synthetic musculoskeletal examination"
SYNTHETIC_GENERAL = "Phase 1H verification - synthetic general examination"


def create_encounter(tenant, client, label="Phase1H"):
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
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1H verification - synthetic triage"},
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
    diagnosis = establish_synthetic_final_diagnosis(client, encounter.data["id"])
    encounter.data["consultation_etag"] = diagnosis["consultation_etag"]
    return encounter.data


def save_note(client, encounter_id, content, etag):
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": content},
        **{"HTTP_IF_MATCH": etag},
        format="json",
    )


def full_content(abdominal=SYNTHETIC_ABDOMINAL, neurological=SYNTHETIC_NEUROLOGICAL, genitourinary=SYNTHETIC_GENITOURINARY, musculoskeletal=SYNTHETIC_MUSCULOSKELETAL):
    return {
        "presenting_complaint": "Phase 1H verification - synthetic presenting complaint",
        "hpi": "Phase 1H verification - synthetic HPI",
        "past_medical_history": "Phase 1H verification - synthetic past medical history",
        "past_surgical_history": "Phase 1H verification - synthetic past surgical history",
        "family_history": "Phase 1H verification - synthetic family history",
        "social_history": "Phase 1H verification - synthetic social history",
        "general_examination": SYNTHETIC_GENERAL,
        "abdominal_examination": abdominal,
        "neurological_examination": neurological,
        "genitourinary_examination": genitourinary,
        "musculoskeletal_examination": musculoskeletal,
        "consultation": "Phase 1H verification - synthetic assessment and plan note",
        "assessment": "Phase 1H verification - synthetic assessment",
        "plan": "Phase 1H verification - synthetic plan",
    }


def test_phase_1h_both_systems_round_trip_association_and_audit(tenant, authed_client):
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
    assert SYNTHETIC_ABDOMINAL not in audit_json
    assert SYNTHETIC_NEUROLOGICAL not in audit_json
    assert "abdominal_examination" in audit_json
    assert "neurological_examination" in audit_json
    assert SYNTHETIC_GENITOURINARY not in audit_json
    assert SYNTHETIC_MUSCULOSKELETAL not in audit_json
    assert "genitourinary_examination" in audit_json
    assert "musculoskeletal_examination" in audit_json


@pytest.mark.parametrize("field_name", ["abdominal_examination", "neurological_examination", "genitourinary_examination", "musculoskeletal_examination"])
def test_phase_1h_exactly_2000_characters_are_accepted(tenant, authed_client, field_name):
    encounter = create_encounter(tenant, authed_client, label=f"Phase1HLimit{field_name}")
    value = "x" * 2000
    saved = save_note(authed_client, encounter["id"], {field_name: value}, encounter["consultation_etag"])

    assert saved.status_code == 200
    assert saved.data["content"][field_name] == value
    assert len(ClinicalNote.objects.get(id=saved.data["note"]).content[field_name]) == 2000


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("abdominal_examination", "x" * 2001),
        ("neurological_examination", "x" * 2001),
        ("abdominal_examination", 42),
        ("neurological_examination", ["Phase 1H verification - invalid synthetic value"]),
        ("genitourinary_examination", "x" * 2001),
        ("musculoskeletal_examination", {"synthetic": "invalid"}),
    ],
)
def test_phase_1h_invalid_type_or_length_is_rejected_without_truncation(
    tenant, authed_client, field_name, invalid_value
):
    encounter = create_encounter(tenant, authed_client, label=f"Phase1HInvalid{field_name}")
    response = save_note(
        authed_client,
        encounter["id"],
        {field_name: invalid_value},
        encounter["consultation_etag"],
    )

    assert response.status_code == 400
    assert field_name in response.data["content"]
    assert not ClinicalNote.objects.filter(encounter_id=encounter["id"]).exists()


def test_phase_1h_partial_abdominal_and_neurological_saves_preserve_all_content(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HPartial")
    initial = full_content()
    saved = save_note(authed_client, encounter["id"], initial, encounter["consultation_etag"])
    assert saved.status_code == 200

    abdominal_update = save_note(
        authed_client,
        encounter["id"],
        {"abdominal_examination": SYNTHETIC_ABDOMINAL_UPDATED},
        saved.data["etag"],
    )
    assert abdominal_update.status_code == 200
    expected_after_abdominal = {**initial, "abdominal_examination": SYNTHETIC_ABDOMINAL_UPDATED}
    assert abdominal_update.data["content"] == expected_after_abdominal

    neurological_update = save_note(
        authed_client,
        encounter["id"],
        {"neurological_examination": SYNTHETIC_NEUROLOGICAL_UPDATED},
        abdominal_update.data["etag"],
    )
    assert neurological_update.status_code == 200
    assert neurological_update.data["content"] == {
        **expected_after_abdominal,
        "neurological_examination": SYNTHETIC_NEUROLOGICAL_UPDATED,
    }


def test_phase_1h_other_field_update_preserves_both_system_examinations(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HOtherField")
    initial = full_content()
    saved = save_note(authed_client, encounter["id"], initial, encounter["consultation_etag"])
    updated = save_note(
        authed_client,
        encounter["id"],
        {"hpi": "Phase 1H verification - updated synthetic HPI"},
        saved.data["etag"],
    )

    assert updated.status_code == 200
    assert updated.data["content"]["abdominal_examination"] == SYNTHETIC_ABDOMINAL
    assert updated.data["content"]["neurological_examination"] == SYNTHETIC_NEUROLOGICAL
    assert updated.data["content"]["genitourinary_examination"] == SYNTHETIC_GENITOURINARY
    assert updated.data["content"]["musculoskeletal_examination"] == SYNTHETIC_MUSCULOSKELETAL


def test_phase_1h_missing_if_match_fails_closed(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HPrecondition")
    response = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/notes/",
        {"content": {"abdominal_examination": SYNTHETIC_ABDOMINAL}},
        format="json",
    )

    assert response.status_code == 428
    assert response.data["code"] == "PRECONDITION_REQUIRED"
    assert not ClinicalNote.objects.filter(encounter_id=encounter["id"]).exists()


def test_phase_1h_same_field_stale_write_is_rejected_without_overwrite(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HSameField")
    baseline = save_note(
        authed_client,
        encounter["id"],
        {"abdominal_examination": SYNTHETIC_ABDOMINAL},
        encounter["consultation_etag"],
    )
    latest = save_note(
        authed_client,
        encounter["id"],
        {"abdominal_examination": SYNTHETIC_ABDOMINAL_UPDATED},
        baseline.data["etag"],
    )
    conflict = save_note(
        authed_client,
        encounter["id"],
        {"abdominal_examination": "Phase 1H verification - stale synthetic abdominal examination"},
        baseline.data["etag"],
    )

    assert latest.status_code == 200
    assert conflict.status_code == 409
    assert conflict.data["content"]["abdominal_examination"] == SYNTHETIC_ABDOMINAL_UPDATED
    assert ClinicalNote.objects.get(id=latest.data["note"]).content["abdominal_examination"] == SYNTHETIC_ABDOMINAL_UPDATED


def test_phase_1h_non_overlap_stale_retry_preserves_both_writers(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HNonOverlap")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL, "neurological_examination": SYNTHETIC_NEUROLOGICAL},
        encounter["consultation_etag"],
    )
    writer_a = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": "Phase 1H verification - updated synthetic general examination"},
        initial.data["etag"],
    )
    stale = save_note(
        authed_client,
        encounter["id"],
        {"neurological_examination": SYNTHETIC_NEUROLOGICAL_UPDATED},
        initial.data["etag"],
    )
    retry = save_note(
        authed_client,
        encounter["id"],
        {"neurological_examination": SYNTHETIC_NEUROLOGICAL_UPDATED},
        stale.data["etag"],
    )

    assert writer_a.status_code == 200
    assert stale.status_code == 409
    assert retry.status_code == 200
    assert retry.data["content"] == {
        "general_examination": "Phase 1H verification - updated synthetic general examination",
        "neurological_examination": SYNTHETIC_NEUROLOGICAL_UPDATED,
    }


def test_phase_1h_sign_preserves_both_systems_and_version_content(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HSign")
    initial = save_note(
        authed_client,
        encounter["id"],
        full_content(),
        encounter["consultation_etag"],
    )
    signed_content = {
        "abdominal_examination": SYNTHETIC_ABDOMINAL_SIGNED,
        "neurological_examination": SYNTHETIC_NEUROLOGICAL_SIGNED,
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
        {"abdominal_examination": "Phase 1H verification - rejected post-sign synthetic write"},
        signed.data["etag"],
    )
    assert rejected.status_code == 400
    assert ClinicalNote.objects.get(id=signed.data["note"]).content == expected


def test_phase_1h_stale_sign_preserves_draft_and_requires_fresh_retry(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HStaleSign")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"abdominal_examination": SYNTHETIC_ABDOMINAL, "neurological_examination": SYNTHETIC_NEUROLOGICAL},
        encounter["consultation_etag"],
    )
    latest = save_note(
        authed_client,
        encounter["id"],
        {"abdominal_examination": SYNTHETIC_ABDOMINAL_UPDATED},
        initial.data["etag"],
    )
    stale_sign = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": {"neurological_examination": SYNTHETIC_NEUROLOGICAL_SIGNED}, "complaints": [{"text": "Phase 1L-A compatibility synthetic complaint", "duration_value": None, "duration_unit": None}]},
        **{"HTTP_IF_MATCH": initial.data["etag"]},
        format="json",
    )

    assert latest.status_code == 200
    assert stale_sign.status_code == 409
    assert stale_sign.data["status"] == "DRAFT"
    assert stale_sign.data["encounter_status"] == "OPEN"
    assert stale_sign.data["content"]["abdominal_examination"] == SYNTHETIC_ABDOMINAL_UPDATED
    assert ClinicalNote.objects.get(id=latest.data["note"]).status == "DRAFT"

    fresh_sign = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": {"neurological_examination": SYNTHETIC_NEUROLOGICAL_SIGNED}, "complaints": [{"text": "Phase 1L-A compatibility synthetic complaint", "duration_value": None, "duration_unit": None}]},
        **{"HTTP_IF_MATCH": stale_sign.data["etag"]},
        format="json",
    )
    assert fresh_sign.status_code == 200
    assert fresh_sign.data["content"] == {
        "abdominal_examination": SYNTHETIC_ABDOMINAL_UPDATED,
        "neurological_examination": SYNTHETIC_NEUROLOGICAL_SIGNED,
    }


def test_phase_1h_non_clinical_role_cannot_edit_system_examination(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HRole")
    nurse = User.objects.create_user("phase1h-nurse")
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
        {"content": {"genitourinary_examination": SYNTHETIC_GENITOURINARY}},
        format="json",
    )

    assert response.status_code == 403


def test_phase_1h_facility_and_tenant_isolation(tenant, authed_client):
    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="Phase 1H Other Facility",
            code="OTHER",
            mode="CLINIC",
        )
        facility_patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no="P-OTHER-FACILITY-PHASE1H",
            first_name="Other Facility",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        facility_encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            patient=facility_patient,
            encounter_no="ENC-OTHER-FACILITY-PHASE1H",
            clinician=tenant.user,
        )

    facility_url = f"/api/v1/clinic/encounters/{facility_encounter.id}"
    assert authed_client.get(facility_url + "/").status_code == 404
    assert authed_client.post(
        facility_url + "/notes/",
        {"content": {"genitourinary_examination": SYNTHETIC_GENITOURINARY}},
        format="json",
    ).status_code == 404

    other_org = Organisation.objects.create(name="Other Phase 1H Clinic", slug="other-phase-1h")
    with tenant_atomic(other_org.id):
        other_facility = Facility.objects.create(
            organisation=other_org,
            name="Other Facility",
            code="MAIN",
            mode="CLINIC",
        )
        other_patient = Patient.objects.create(
            organisation=other_org,
            patient_no="P-OTHER-ORG-PHASE1H",
            first_name="Other Organisation",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        other_user = User.objects.create_user("phase1h-other")
        other_encounter = Encounter.objects.create(
            organisation=other_org,
            facility=other_facility,
            patient=other_patient,
            encounter_no="ENC-OTHER-ORG-PHASE1H",
            clinician=other_user,
        )

    other_url = f"/api/v1/clinic/encounters/{other_encounter.id}"
    assert authed_client.get(other_url + "/").status_code == 404
    assert authed_client.post(
        other_url + "/notes/",
        {"content": {"musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL}},
        format="json",
    ).status_code == 404


def test_phase_1h_partial_new_system_saves_preserve_all_content(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HNewPartial")
    initial = full_content()
    saved = save_note(authed_client, encounter["id"], initial, encounter["consultation_etag"])
    assert saved.status_code == 200

    genitourinary_update = save_note(
        authed_client,
        encounter["id"],
        {"genitourinary_examination": SYNTHETIC_GENITOURINARY_UPDATED},
        saved.data["etag"],
    )
    assert genitourinary_update.status_code == 200
    expected_after_genitourinary = {
        **initial,
        "genitourinary_examination": SYNTHETIC_GENITOURINARY_UPDATED,
    }
    assert genitourinary_update.data["content"] == expected_after_genitourinary

    musculoskeletal_update = save_note(
        authed_client,
        encounter["id"],
        {"musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL_UPDATED},
        genitourinary_update.data["etag"],
    )
    assert musculoskeletal_update.status_code == 200
    assert musculoskeletal_update.data["content"] == {
        **expected_after_genitourinary,
        "musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL_UPDATED,
    }


def test_phase_1h_same_field_genitourinary_stale_write_is_rejected(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HNewSameField")
    baseline = save_note(
        authed_client,
        encounter["id"],
        {
            "genitourinary_examination": SYNTHETIC_GENITOURINARY,
            "musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL,
        },
        encounter["consultation_etag"],
    )
    latest = save_note(
        authed_client,
        encounter["id"],
        {"genitourinary_examination": SYNTHETIC_GENITOURINARY_UPDATED},
        baseline.data["etag"],
    )
    conflict = save_note(
        authed_client,
        encounter["id"],
        {"genitourinary_examination": "Phase 1H verification - stale synthetic genitourinary examination"},
        baseline.data["etag"],
    )

    assert latest.status_code == 200
    assert conflict.status_code == 409
    assert conflict.data["content"]["genitourinary_examination"] == SYNTHETIC_GENITOURINARY_UPDATED
    assert conflict.data["content"]["musculoskeletal_examination"] == SYNTHETIC_MUSCULOSKELETAL
    assert ClinicalNote.objects.get(id=latest.data["note"]).content["genitourinary_examination"] == SYNTHETIC_GENITOURINARY_UPDATED


def test_phase_1h_neurological_and_musculoskeletal_non_overlap_retry_preserves_both(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HNewNonOverlap")
    initial = save_note(
        authed_client,
        encounter["id"],
        {
            "neurological_examination": SYNTHETIC_NEUROLOGICAL,
            "musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL,
        },
        encounter["consultation_etag"],
    )
    writer_a = save_note(
        authed_client,
        encounter["id"],
        {"neurological_examination": SYNTHETIC_NEUROLOGICAL_UPDATED},
        initial.data["etag"],
    )
    stale = save_note(
        authed_client,
        encounter["id"],
        {"musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL_UPDATED},
        initial.data["etag"],
    )
    retry = save_note(
        authed_client,
        encounter["id"],
        {"musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL_UPDATED},
        stale.data["etag"],
    )

    assert writer_a.status_code == 200
    assert stale.status_code == 409
    assert retry.status_code == 200
    assert retry.data["content"] == {
        "neurological_examination": SYNTHETIC_NEUROLOGICAL_UPDATED,
        "musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL_UPDATED,
    }


def test_phase_1h_sign_new_systems_preserves_version_content(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HNewSign")
    initial = save_note(
        authed_client,
        encounter["id"],
        full_content(),
        encounter["consultation_etag"],
    )
    signed_content = {
        "genitourinary_examination": SYNTHETIC_GENITOURINARY_SIGNED,
        "musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL_SIGNED,
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
        {"genitourinary_examination": "Phase 1H verification - rejected post-sign synthetic genitourinary examination"},
        signed.data["etag"],
    )
    assert rejected.status_code == 400
    assert ClinicalNote.objects.get(id=signed.data["note"]).content == expected


def test_phase_1h_stale_sign_new_systems_requires_fresh_retry(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1HNewStaleSign")
    initial = save_note(
        authed_client,
        encounter["id"],
        {
            "genitourinary_examination": SYNTHETIC_GENITOURINARY,
            "musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL,
        },
        encounter["consultation_etag"],
    )
    latest = save_note(
        authed_client,
        encounter["id"],
        {"genitourinary_examination": SYNTHETIC_GENITOURINARY_UPDATED},
        initial.data["etag"],
    )
    stale_sign = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": {"musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL_SIGNED}, "complaints": [{"text": "Phase 1L-A compatibility synthetic complaint", "duration_value": None, "duration_unit": None}]},
        **{"HTTP_IF_MATCH": initial.data["etag"]},
        format="json",
    )

    assert latest.status_code == 200
    assert stale_sign.status_code == 409
    assert stale_sign.data["status"] == "DRAFT"
    assert stale_sign.data["encounter_status"] == "OPEN"
    assert stale_sign.data["content"]["genitourinary_examination"] == SYNTHETIC_GENITOURINARY_UPDATED
    assert stale_sign.data["content"]["musculoskeletal_examination"] == SYNTHETIC_MUSCULOSKELETAL
    assert ClinicalNote.objects.get(id=latest.data["note"]).status == "DRAFT"

    fresh_sign = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": {"musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL_SIGNED}, "complaints": [{"text": "Phase 1L-A compatibility synthetic complaint", "duration_value": None, "duration_unit": None}]},
        **{"HTTP_IF_MATCH": stale_sign.data["etag"]},
        format="json",
    )
    assert fresh_sign.status_code == 200
    assert fresh_sign.data["content"] == {
        "genitourinary_examination": SYNTHETIC_GENITOURINARY_UPDATED,
        "musculoskeletal_examination": SYNTHETIC_MUSCULOSKELETAL_SIGNED,
    }
