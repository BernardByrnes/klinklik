import json

import pytest

from audit.models import AuditEvent
from clinical.models import ClinicalNote, ClinicalNoteVersion, Encounter


pytestmark = pytest.mark.django_db

SYNTHETIC_CARDIOVASCULAR = "Phase 1K-G verification - synthetic cardiovascular finding"
SYNTHETIC_GENERAL = "Phase 1K-G verification - synthetic general finding"
SYNTHETIC_GENERAL_UPDATED = "Phase 1K-G verification - updated synthetic general finding"
SYNTHETIC_HPI = "Phase 1K-G verification - synthetic HPI"


def create_encounter(tenant, client, label="Phase1KG"):
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
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1K-G verification - synthetic triage"},
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


def test_phase_1k_g_new_note_omits_blank_examination_only(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client)
    saved = save_note(
        authed_client,
        encounter["id"],
        {
            "general_examination": "",
            "cardiovascular_examination": SYNTHETIC_CARDIOVASCULAR,
            "hpi": "",
        },
        encounter["consultation_etag"],
    )

    assert saved.status_code == 200
    assert saved.data["content"] == {
        "cardiovascular_examination": SYNTHETIC_CARDIOVASCULAR,
        "hpi": "",
    }
    note = ClinicalNote.objects.get(id=saved.data["note"])
    assert "general_examination" not in note.content
    assert note.content["cardiovascular_examination"] == SYNTHETIC_CARDIOVASCULAR
    assert note.content["hpi"] == ""


def test_phase_1k_g_whitespace_only_examination_is_absent(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KGWhitespace")
    saved = save_note(
        authed_client,
        encounter["id"],
        {"respiratory_examination": "   \n  "},
        encounter["consultation_etag"],
    )

    assert saved.status_code == 200
    assert saved.data["content"] == {}
    assert ClinicalNote.objects.get(id=saved.data["note"]).content == {}


def test_phase_1k_g_populated_examination_text_is_verbatim(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KGVerbatim")
    value = "  Mild ankle swelling noted.  "
    saved = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": value},
        encounter["consultation_etag"],
    )

    assert saved.status_code == 200
    assert saved.data["content"]["general_examination"] == value
    assert ClinicalNote.objects.get(id=saved.data["note"]).content["general_examination"] == value


def test_phase_1k_g_clearing_saved_examination_removes_only_that_key(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KGClear")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL, "hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
    )
    cleared = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": ""},
        initial.data["etag"],
    )

    assert initial.status_code == 200
    assert cleared.status_code == 200
    assert cleared.data["etag"] != initial.data["etag"]
    assert cleared.data["content"] == {"hpi": SYNTHETIC_HPI}
    note = ClinicalNote.objects.get(id=cleared.data["note"])
    assert note.content == {"hpi": SYNTHETIC_HPI}


def test_phase_1k_g_sign_after_clear_has_no_blank_examination_in_note_or_version(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KGSignClear")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL, "hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
    )
    cleared = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": ""},
        initial.data["etag"],
    )
    signed = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": {}},
        **{"HTTP_IF_MATCH": cleared.data["etag"]},
        format="json",
    )

    assert signed.status_code == 200
    assert signed.data["content"] == {"hpi": SYNTHETIC_HPI}
    note = ClinicalNote.objects.get(id=signed.data["note"])
    version = ClinicalNoteVersion.objects.get(note=note, version_number=1)
    assert note.content == {"hpi": SYNTHETIC_HPI}
    assert version.content == {"hpi": SYNTHETIC_HPI}


def test_phase_1k_g_sign_with_whitespace_examination_omits_key_from_version(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KGSignWhitespace")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
    )
    signed = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": {"general_examination": " \t\n "}},
        **{"HTTP_IF_MATCH": initial.data["etag"]},
        format="json",
    )

    assert signed.status_code == 200
    assert signed.data["content"] == {"hpi": SYNTHETIC_HPI}
    note = ClinicalNote.objects.get(id=signed.data["note"])
    version = ClinicalNoteVersion.objects.get(note=note, version_number=1)
    assert "general_examination" not in note.content
    assert "general_examination" not in version.content


def test_phase_1k_g_stale_clear_keeps_existing_conflict_semantics(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KGConflict")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL},
        encounter["consultation_etag"],
    )
    latest = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL_UPDATED},
        initial.data["etag"],
    )
    stale_clear = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": ""},
        initial.data["etag"],
    )

    assert latest.status_code == 200
    assert stale_clear.status_code == 409
    assert stale_clear.data["content"]["general_examination"] == SYNTHETIC_GENERAL_UPDATED
    assert ClinicalNote.objects.get(id=latest.data["note"]).content == {
        "general_examination": SYNTHETIC_GENERAL_UPDATED,
    }


def test_phase_1k_g_clear_audit_is_safe_and_autosave_summary_is_preserved(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KGAudit")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL, "hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
    )
    note_id = initial.data["note"]
    cleared = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": ""},
        initial.data["etag"],
    )
    assert cleared.status_code == 200
    manual_events = list(
        AuditEvent.objects.filter(
            organisation=tenant.organisation,
            entity_type="ClinicalNote",
            entity_id=str(note_id),
        )
    )
    assert "general_examination" in manual_events[-1].after["fields"]
    assert SYNTHETIC_GENERAL not in json.dumps(
        [{"before": event.before, "after": event.after} for event in manual_events],
        default=str,
    )

    autosaved = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": "   "},
        cleared.data["etag"],
        autosave=True,
    )
    assert autosaved.status_code == 200
    assert autosaved.data["content"] == {"hpi": SYNTHETIC_HPI}
    summaries = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        actor=tenant.user,
        action="UPDATE",
        entity_type="Encounter",
        entity_id=encounter["id"],
    )
    assert summaries.count() == 1
    assert summaries.first().after["reason"] == "ENCOUNTER_DRAFT_UPDATED"
    assert SYNTHETIC_GENERAL not in json.dumps([event.after for event in summaries], default=str)


def test_phase_1k_g_amendment_version_omits_blank_examination(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1KGAmend")
    initial = save_note(
        authed_client,
        encounter["id"],
        {"general_examination": SYNTHETIC_GENERAL, "hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
    )
    signed = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": {}},
        **{"HTTP_IF_MATCH": initial.data["etag"]},
        format="json",
    )
    amended = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/amend/",
        {
            "content": {"general_examination": " \n ", "hpi": SYNTHETIC_HPI},
            "reason": "Phase 1K-G verification - synthetic amendment",
        },
        **{"HTTP_IF_MATCH": signed.data["etag"]},
        format="json",
    )

    assert signed.status_code == 200
    assert amended.status_code == 200
    assert amended.data["content"] == {"hpi": SYNTHETIC_HPI}
    note = ClinicalNote.objects.get(id=amended.data["note"])
    version = ClinicalNoteVersion.objects.get(note=note, version_number=2)
    assert note.content == {"hpi": SYNTHETIC_HPI}
    assert version.content == {"hpi": SYNTHETIC_HPI}
