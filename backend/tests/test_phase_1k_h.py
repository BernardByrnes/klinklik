import json

import pytest

from audit.models import AuditEvent
from clinical.models import ClinicalNote


pytestmark = pytest.mark.django_db

SYNTHETIC_GENERAL = "Phase 1K-H verification - synthetic general examination"
SYNTHETIC_GENERAL_UPDATED = "Phase 1K-H verification - updated synthetic general examination"
SYNTHETIC_HPI = "Phase 1K-H verification - synthetic HPI"


def create_encounter(tenant, client, label="Phase1KH"):
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
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1K-H verification - synthetic triage"},
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


def post_note(client, encounter_id, content, etag=None, *, autosave=False):
    headers = {}
    if etag is not None:
        headers["HTTP_IF_MATCH"] = etag
    if autosave:
        headers["HTTP_X_KLINKLIK_AUTOSAVE"] = "1"
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": content},
        **headers,
        format="json",
    )


def patch_note(client, encounter_id, content, etag=None, *, autosave=False):
    headers = {}
    if etag is not None:
        headers["HTTP_IF_MATCH"] = etag
    if autosave:
        headers["HTTP_X_KLINKLIK_AUTOSAVE"] = "1"
    return client.patch(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": content},
        **headers,
        format="json",
    )


def test_phase_1k_h_patch_saves_with_current_etag_and_returns_etag_and_saved_at(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client)
    response = patch_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
    )

    assert response.status_code == 200
    assert response.data["content"] == {"hpi": SYNTHETIC_HPI}
    assert response.data["saved_at"]
    assert response.data["etag"]
    assert response["ETag"] == response.data["etag"]


def test_phase_1k_h_patch_requires_if_match(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KHPrecondition")
    response = patch_note(authed_client, encounter["id"], {"hpi": SYNTHETIC_HPI})

    assert response.status_code == 428
    assert response.data["code"] == "PRECONDITION_REQUIRED"


def test_phase_1k_h_patch_stale_etag_returns_412_reconciliation_body(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KHConflict")
    initial = post_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL},
        encounter["consultation_etag"],
    )
    latest = patch_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL_UPDATED},
        initial.data["etag"],
    )
    stale = patch_note(
        authed_client,
        encounter["id"],
        {"general_examination": "Phase 1K-H verification - stale synthetic replacement"},
        initial.data["etag"],
    )

    assert latest.status_code == 200
    assert stale.status_code == 412
    assert {
        "code", "detail", "etag", "status", "encounter_status", "content", "saved_at"
    }.issubset(stale.data)
    assert stale.data["code"] == "CLINICAL_NOTE_REVISION_CONFLICT"
    assert stale.data["content"] == {"general_examination": SYNTHETIC_GENERAL_UPDATED}
    assert stale["ETag"] == stale.data["etag"]


def test_phase_1k_h_legacy_post_stale_etag_remains_409(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KHPostCompatibility")
    initial = post_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
    )
    latest = post_note(
        authed_client,
        encounter["id"],
        {"hpi": "Phase 1K-H verification - updated synthetic HPI"},
        initial.data["etag"],
    )
    stale = post_note(
        authed_client,
        encounter["id"],
        {"hpi": "Phase 1K-H verification - stale synthetic HPI"},
        initial.data["etag"],
    )

    assert latest.status_code == 200
    assert stale.status_code == 409
    assert stale.data["code"] == "CLINICAL_NOTE_REVISION_CONFLICT"
    assert stale["ETag"] == stale.data["etag"]


def test_phase_1k_h_patch_uses_examination_normalization_for_clear(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KHNormalization")
    initial = patch_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL, "hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
    )
    cleared = patch_note(
        authed_client,
        encounter["id"],
        {"general_examination": "   "},
        initial.data["etag"],
    )

    assert cleared.status_code == 200
    assert cleared.data["content"] == {"hpi": SYNTHETIC_HPI}
    assert "general_examination" not in ClinicalNote.objects.get(id=cleared.data["note"]).content


def test_phase_1k_h_autosave_patch_preserves_safe_summary_audit(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KHAudit")
    initial = patch_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL},
        encounter["consultation_etag"],
    )
    autosaved = patch_note(
        authed_client,
        encounter["id"],
        {"general_examination": ""},
        initial.data["etag"],
        autosave=True,
    )

    assert autosaved.status_code == 200
    assert autosaved.data["content"] == {}
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
        "minute": summaries.first().after["minute"],
    }
    assert SYNTHETIC_GENERAL not in json.dumps([event.after for event in summaries], default=str)
