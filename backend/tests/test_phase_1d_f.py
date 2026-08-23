import pytest

from audit.models import AuditEvent
from clinical.models import ClinicalNote, ClinicalNoteVersion

from tests.clinical_test_helpers import establish_synthetic_final_diagnosis, establish_synthetic_nka_review, note_headers

pytestmark = pytest.mark.django_db


INITIAL_CONTENT = {
    "family_history": "Phase 1D-F synthetic original family",
    "social_history": "Phase 1D-F synthetic original social",
    "hpi": "Phase 1D-F synthetic original HPI",
    "consultation": "Phase 1D-F synthetic original consultation",
    "assessment": "Phase 1D-F synthetic original assessment",
    "plan": "Phase 1D-F synthetic original plan",
}


def create_encounter(tenant, client, label="Phase1DF"):
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
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1D-F synthetic triage"},
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


@pytest.mark.parametrize(
    ("first_field", "first_value", "second_field", "second_value"),
    [
        (
            "family_history",
            "Phase 1D-F synthetic updated family",
            "social_history",
            "Phase 1D-F synthetic updated social",
        ),
        (
            "family_history",
            "Phase 1D-F synthetic family for HPI pair",
            "hpi",
            "Phase 1D-F synthetic updated HPI",
        ),
        (
            "family_history",
            "Phase 1D-F synthetic family for plan pair",
            "plan",
            "Phase 1D-F synthetic updated plan",
        ),
    ],
)
def test_phase_1d_f_stale_clients_preserve_untouched_fields_and_audit_only_submitted_keys(
    tenant,
    authed_client,
    first_field,
    first_value,
    second_field,
    second_value,
):
    encounter_id = create_encounter(tenant, authed_client)
    initial = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": INITIAL_CONTENT},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert initial.status_code == 200

    first_update = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {first_field: first_value}},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert first_update.status_code == 200

    second_update = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {second_field: second_value}},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert second_update.status_code == 200

    expected = {**INITIAL_CONTENT, first_field: first_value, second_field: second_value}
    assert second_update.data["content"] == expected

    note_id = second_update.data["note"]
    update_events = list(
        AuditEvent.objects.filter(
            organisation=tenant.organisation,
            entity_type="ClinicalNote",
            entity_id=note_id,
            action="UPDATE",
        ).order_by("occurred_at", "id")
    )
    assert update_events[-1].after["fields"] == [second_field]
    assert first_field not in update_events[-1].after["fields"]
    assert first_value not in str(update_events[-1].after)
    assert second_value not in str(update_events[-1].after)


def test_phase_1d_f_stale_partial_sign_preserves_newer_server_content(tenant, authed_client):
    encounter_id = create_encounter(tenant, authed_client, label="Phase1DFSign")
    saved = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": INITIAL_CONTENT},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert saved.status_code == 200

    family_update = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"family_history": "Phase 1D-F synthetic newer family"}},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert family_update.status_code == 200

    signed = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"social_history": "Phase 1D-F synthetic signed social"}, "complaints": [{"text": "Phase 1L-A compatibility synthetic complaint", "duration_value": None, "duration_unit": None}]},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert signed.status_code == 200

    expected = {
        **INITIAL_CONTENT,
        "family_history": "Phase 1D-F synthetic newer family",
        "social_history": "Phase 1D-F synthetic signed social",
    }
    note = ClinicalNote.objects.get(encounter_id=encounter_id)
    version = ClinicalNoteVersion.objects.get(note=note, version_number=1)
    assert signed.data["content"] == expected
    assert note.content == expected
    assert version.content == expected
    assert signed.data["current_version"] == 1
