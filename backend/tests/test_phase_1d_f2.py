import pytest

from audit.models import AuditEvent
from clinical.models import ClinicalNote, ClinicalNoteVersion, Encounter


pytestmark = pytest.mark.django_db


def create_encounter(tenant, client, label="Phase1DF2"):
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
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1D-F2 synthetic triage"},
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


def current_etag(client, encounter_id):
    response = client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert response.status_code == 200
    return response.data["consultation_etag"]


def match(etag):
    return {"HTTP_IF_MATCH": etag}


def save_note(client, encounter_id, content, etag):
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": content},
        format="json",
        **match(etag),
    )


def test_no_note_etag_is_authoritative_and_stale_first_save_is_rejected(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client)
    encounter_id = encounter["id"]
    no_note_etag = encounter["consultation_etag"]
    assert no_note_etag == current_etag(authed_client, encounter_id)

    missing = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"assessment": "Phase 1D-F2 synthetic missing precondition"}},
        format="json",
    )
    assert missing.status_code == 428
    assert missing.data["code"] == "PRECONDITION_REQUIRED"

    first_content = {"assessment": "Phase 1D-F2 synthetic first draft"}
    first = save_note(authed_client, encounter_id, first_content, no_note_etag)
    assert first.status_code == 200
    assert first.data["etag"] == first["ETag"]
    assert first.data["etag"] != no_note_etag

    stale = save_note(
        authed_client,
        encounter_id,
        {"assessment": "Phase 1D-F2 synthetic stale first draft"},
        no_note_etag,
    )
    assert stale.status_code == 409
    assert stale.data["code"] == "CLINICAL_NOTE_REVISION_CONFLICT"
    assert stale.data["etag"] == first.data["etag"]
    assert stale["ETag"] == first.data["etag"]
    assert stale.data["content"] == first_content
    assert current_etag(authed_client, encounter_id) == first.data["etag"]

@pytest.mark.parametrize(
    ("stale_field", "stale_value"),
    [
        ("family_history", "Phase 1D-F2 synthetic stale family"),
        ("social_history", "Phase 1D-F2 synthetic stale social"),
    ],
)
def test_stale_api_writes_are_rejected_with_current_content_and_no_audit(
    tenant, authed_client, stale_field, stale_value
):
    encounter = create_encounter(tenant, authed_client, label="Phase1DF2Fields")
    encounter_id = encounter["id"]
    initial = save_note(
        authed_client,
        encounter_id,
        {
            "family_history": "Phase 1D-F2 synthetic baseline family",
            "social_history": "Phase 1D-F2 synthetic baseline social",
        },
        encounter["consultation_etag"],
    )
    assert initial.status_code == 200
    stale_etag = initial.data["etag"]
    latest = save_note(
        authed_client,
        encounter_id,
        {"family_history": "Phase 1D-F2 synthetic latest family"},
        stale_etag,
    )
    assert latest.status_code == 200
    update_count = AuditEvent.objects.filter(
        entity_type="ClinicalNote", entity_id=latest.data["note"], action="UPDATE"
    ).count()
    conflict = save_note(authed_client, encounter_id, {stale_field: stale_value}, stale_etag)
    assert conflict.status_code == 409
    assert conflict.data["etag"] == latest.data["etag"]
    assert conflict.data["content"] == latest.data["content"]
    assert AuditEvent.objects.filter(
        entity_type="ClinicalNote", entity_id=latest.data["note"], action="UPDATE"
    ).count() == update_count
    assert stale_value not in str(conflict.data.get("detail", ""))


def test_missing_if_match_fails_closed_for_sign_and_amend(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1DF2Precondition")
    encounter_id = encounter["id"]
    sign = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"assessment": "Phase 1D-F2 synthetic sign"}},
        format="json",
    )
    assert sign.status_code == 428
    amend = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/amend/",
        {
            "content": {"assessment": "Phase 1D-F2 synthetic amendment"},
            "reason": "Phase 1D-F2 synthetic precondition test",
        },
        format="json",
    )
    assert amend.status_code == 428

def test_stale_sign_does_not_mutate_and_fresh_retry_signs(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1DF2Sign")
    encounter_id = encounter["id"]
    initial = save_note(
        authed_client,
        encounter_id,
        {"family_history": "Phase 1D-F2 synthetic sign baseline"},
        encounter["consultation_etag"],
    )
    stale_etag = initial.data["etag"]
    latest = save_note(
        authed_client,
        encounter_id,
        {"family_history": "Phase 1D-F2 synthetic sign latest"},
        stale_etag,
    )
    stale_sign = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"social_history": "Phase 1D-F2 synthetic stale sign"}},
        format="json",
        **match(stale_etag),
    )
    assert stale_sign.status_code == 409
    assert stale_sign.data["status"] == "DRAFT"
    assert stale_sign.data["encounter_status"] == "OPEN"
    assert stale_sign.data["content"] == latest.data["content"]
    note = ClinicalNote.objects.get(id=latest.data["note"])
    assert note.status == "DRAFT"
    assert ClinicalNoteVersion.objects.filter(note=note).count() == 0

    fresh_sign = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"social_history": "Phase 1D-F2 synthetic explicit sign retry"}},
        format="json",
        **match(stale_sign.data["etag"]),
    )
    assert fresh_sign.status_code == 200
    assert fresh_sign.data["current_version"] == 1
    assert fresh_sign.data["status"] == "SIGNED"
    assert fresh_sign.data["content"]["family_history"] == "Phase 1D-F2 synthetic sign latest"
    assert fresh_sign.data["content"]["social_history"] == "Phase 1D-F2 synthetic explicit sign retry"
    assert fresh_sign.data["etag"] == fresh_sign["ETag"]
    assert Encounter.objects.get(id=encounter_id).status == "SIGNED"

    rejected_save = save_note(
        authed_client,
        encounter_id,
        {"assessment": "Phase 1D-F2 synthetic rejected post-sign save"},
        fresh_sign.data["etag"],
    )
    assert rejected_save.status_code == 400
    assert ClinicalNoteVersion.objects.filter(note=note).count() == 1


def test_amendment_is_etag_protected_and_preserves_versions(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1DF2Amend")
    encounter_id = encounter["id"]
    saved = save_note(
        authed_client,
        encounter_id,
        {"assessment": "Phase 1D-F2 synthetic signed assessment"},
        encounter["consultation_etag"],
    )
    signed = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"plan": "Phase 1D-F2 synthetic signed plan"}},
        format="json",
        **match(saved.data["etag"]),
    )
    assert signed.status_code == 200
    signed_etag = signed.data["etag"]
    amended_content = {
        "assessment": "Phase 1D-F2 synthetic amended assessment",
        "plan": "Phase 1D-F2 synthetic amended plan",
    }
    amended = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/amend/",
        {"content": amended_content, "reason": "Phase 1D-F2 synthetic correction"},
        format="json",
        **match(signed_etag),
    )
    assert amended.status_code == 200
    assert amended.data["status"] == "AMENDED"
    assert amended.data["current_version"] == 2
    assert amended.data["content"] == amended_content
    assert amended.data["etag"] != signed_etag

    stale_amend = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/amend/",
        {
            "content": {"assessment": "Phase 1D-F2 synthetic stale amendment"},
            "reason": "Phase 1D-F2 synthetic stale correction",
        },
        format="json",
        **match(signed_etag),
    )
    assert stale_amend.status_code == 409
    assert stale_amend.data["status"] == "AMENDED"
    assert stale_amend.data["content"] == amended_content
    note = ClinicalNote.objects.get(id=amended.data["note"])
    assert note.current_version == 2
    assert ClinicalNoteVersion.objects.filter(note=note).count() == 2
