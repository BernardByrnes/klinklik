"""S-19 idempotency enforcement proofs for clinical mutation views."""

from uuid import uuid4
import json

import pytest

from tests.test_s04_encounter import (
    _canonical_encounter,
    enabled_mig002_target,
    enabled_mig003_target,
)

pytestmark = pytest.mark.django_db

ENFORCED_ENDPOINTS = [
    ("PATCH", "/api/v1/clinic/encounters/{id}/notes/"),
    ("POST", "/api/v1/clinic/encounters/{id}/sign/"),
    ("POST", "/api/v1/clinic/encounters/{id}/amend/"),
    ("POST", "/api/v1/clinic/patients/{id}/allergies/"),
    ("POST", "/api/v1/clinic/patients/{id}/allergy-status/"),
    ("POST", "/api/v1/clinic/patients/{id}/allergies/{id}/entered-in-error/"),
    ("POST", "/api/v1/clinic/encounters/{id}/allergies/review/"),
    ("POST", "/api/v1/clinic/encounters/{id}/diagnoses/"),
    ("PATCH", "/api/v1/clinic/encounters/{id}/disposition/"),
    ("PATCH", "/api/v1/clinic/encounters/{id}/follow-up/"),
]


def test_s19_all_enforced_endpoints_require_an_idempotency_key(
    tenant, authed_client, enabled_mig003_target
):
    target = str(uuid4())
    for method, template in ENFORCED_ENDPOINTS:
        path = template.format(id=target)
        response = authed_client.generic(
            method, path, {}, format="json", HTTP_IF_MATCH='"1"'
        )
        assert response.status_code == 400, (method, path, response.data)
        assert response.data["code"] == "IDEMPOTENCY_KEY_REQUIRED", (path, response.data)


def test_s19_note_save_replays_conflicts_and_reports_missing_key(
    tenant, authed_client, enabled_mig003_target
):
    from clinical.models import ClinicalNote, ClinicalNoteVersion

    setup = _canonical_encounter(tenant, authed_client)
    encounter_id = setup["encounter"]["id"]
    etag = setup["encounter"]["consultation_etag"]
    path = f"/api/v1/clinic/encounters/{encounter_id}/notes/"
    body = {"content": {"hpi": "S-19 synthetic idempotent note"}}
    key = f"s19-note-{uuid4()}"

    missing = authed_client.patch(
        path, body, format="json", HTTP_IF_MATCH=etag
    )
    assert missing.status_code == 400
    assert missing.data["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    before = ClinicalNoteVersion.objects.filter(note__encounter_id=encounter_id).count()
    first = authed_client.patch(
        path, body, format="json", HTTP_IF_MATCH=etag, HTTP_IDEMPOTENCY_KEY=key
    )
    assert first.status_code == 200, first.data
    after_first = ClinicalNoteVersion.objects.filter(note__encounter_id=encounter_id).count()

    replay = authed_client.patch(
        path, body, format="json", HTTP_IF_MATCH=etag, HTTP_IDEMPOTENCY_KEY=key
    )
    assert replay.status_code == 200
    assert replay["Idempotent-Replay"] == "true"
    assert json.dumps(replay.data, default=str, sort_keys=True) == json.dumps(first.data, default=str, sort_keys=True)

    changed = authed_client.patch(
        path,
        {"content": {"hpi": "S-19 synthetic changed note"}},
        format="json",
        HTTP_IF_MATCH=etag,
        HTTP_IDEMPOTENCY_KEY=key,
    )
    assert changed.status_code == 409
    assert changed.data["code"] == "IDEMPOTENCY_CONFLICT"
    assert ClinicalNoteVersion.objects.filter(note__encounter_id=encounter_id).count() == after_first
    note = ClinicalNote.objects.get(encounter_id=encounter_id)
    assert note.content.get("hpi") == "S-19 synthetic idempotent note"
    assert ClinicalNote.objects.filter(encounter_id=encounter_id).count() == 1
