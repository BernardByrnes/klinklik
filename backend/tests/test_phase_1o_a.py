import json

import pytest

from audit.models import AuditEvent
from clinical.models import ClinicalNote, ClinicalNoteVersion, Encounter
from tests.clinical_test_helpers import establish_synthetic_final_diagnosis, establish_synthetic_nka_review


pytestmark = pytest.mark.django_db

SYNTHETIC_TRIAGE = "Phase 1O-A verification - synthetic triage complaint"
SYNTHETIC_COMPLAINT = "Phase 1O-A verification - synthetic complaint"


def create_encounter(tenant, client, label="Phase1OATreatmentPlan"):
    patient = client.post(
        "/api/v1/patients/",
        {"first_name": label, "last_name": "Synthetic", "sex": "UNKNOWN"},
        format="json",
    )
    assert patient.status_code == 201, patient.data
    check_in = client.post(
        "/api/v1/clinic/check-ins/",
        {"patient_id": patient.data["id"], "department_id": str(tenant.department.id)},
        format="json",
    )
    assert check_in.status_code == 201, check_in.data
    queue_id = check_in.data["id"]
    assert client.post(f"/api/v1/clinic/queue/{queue_id}/claim/", {}, format="json").status_code == 200
    triage = client.post(
        f"/api/v1/clinic/triage/{queue_id}/",
        {"acuity": "ROUTINE", "chief_complaint": SYNTHETIC_TRIAGE},
        format="json",
    )
    assert triage.status_code == 201, triage.data
    encounter = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": queue_id},
        format="json",
    )
    assert encounter.status_code == 201, encounter.data
    establish_synthetic_nka_review(client, encounter.data["id"])
    diagnosis = establish_synthetic_final_diagnosis(client, encounter.data["id"])
    encounter.data["consultation_etag"] = diagnosis["consultation_etag"]
    return encounter.data


def patch_note(client, encounter_id, content, etag):
    return client.patch(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": content},
        HTTP_IF_MATCH=etag,
        format="json",
    )


def sign_note(client, encounter_id, etag):
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {
            "content": {},
            "complaints": [
                {
                    "text": SYNTHETIC_COMPLAINT,
                    "duration_value": None,
                    "duration_unit": None,
                }
            ],
        },
        HTTP_IF_MATCH=etag,
        format="json",
    )


def test_treatment_plan_round_trips_multiline_with_etag_and_safe_audit(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1OARoundTrip")
    treatment_plan = (
        "Phase 1O-A synthetic management plan.\n"
        "Continue supportive care.\n"
        "Return for review if symptoms worsen."
    )
    hpi = "Phase 1O-A synthetic HPI regression value."

    saved = patch_note(
        authed_client,
        encounter["id"],
        {"hpi": hpi, "treatment_plan": treatment_plan},
        encounter["consultation_etag"],
    )

    assert saved.status_code == 200, saved.data
    assert saved.data["content"]["hpi"] == hpi
    assert saved.data["content"]["treatment_plan"] == treatment_plan
    assert saved.data["etag"] != encounter["consultation_etag"]
    assert saved["ETag"] == saved.data["etag"]

    reloaded = authed_client.get(f"/api/v1/clinic/encounters/{encounter['id']}/")
    assert reloaded.status_code == 200, reloaded.data
    assert reloaded.data["notes"][0]["content"]["hpi"] == hpi
    assert reloaded.data["notes"][0]["content"]["treatment_plan"] == treatment_plan

    event = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        entity_type="ClinicalNote",
        entity_id=saved.data["note"],
        action__in=["CREATE", "UPDATE"],
    ).latest("occurred_at")
    audit_json = json.dumps({"before": event.before, "after": event.after}, default=str)
    assert "treatment_plan" in audit_json
    assert treatment_plan not in audit_json
    assert hpi not in audit_json


def test_treatment_plan_accepts_4000_and_rejects_long_or_non_string_values(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1OALimits")
    maximum = "x" * 4000

    accepted = patch_note(
        authed_client,
        encounter["id"],
        {"treatment_plan": maximum},
        encounter["consultation_etag"],
    )
    assert accepted.status_code == 200, accepted.data
    assert accepted.data["content"]["treatment_plan"] == maximum

    too_long = patch_note(
        authed_client,
        encounter["id"],
        {"treatment_plan": "x" * 4001},
        accepted.data["etag"],
    )
    assert too_long.status_code == 400
    assert "treatment_plan" in too_long.data["content"]

    non_string = patch_note(
        authed_client,
        encounter["id"],
        {"treatment_plan": {"instruction": "not prose"}},
        accepted.data["etag"],
    )
    assert non_string.status_code == 400
    assert "treatment_plan" in non_string.data["content"]

    unchanged = authed_client.get(f"/api/v1/clinic/encounters/{encounter['id']}/")
    assert unchanged.status_code == 200, unchanged.data
    assert unchanged.data["notes"][0]["content"]["treatment_plan"] == maximum


def test_stale_treatment_plan_patch_returns_412_with_authoritative_content(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1OAConflict")
    stale_etag = encounter["consultation_etag"]
    current_plan = "Phase 1O-A synthetic authoritative treatment plan."

    device_a = patch_note(authed_client, encounter["id"], {"treatment_plan": current_plan}, stale_etag)
    assert device_a.status_code == 200, device_a.data
    audit_count = AuditEvent.objects.filter(
        entity_type="ClinicalNote",
        entity_id=device_a.data["note"],
        action="UPDATE",
    ).count()

    device_b = patch_note(
        authed_client,
        encounter["id"],
        {"treatment_plan": "Phase 1O-A synthetic stale treatment plan."},
        stale_etag,
    )

    assert device_b.status_code == 412, device_b.data
    assert device_b.data["code"] == "CLINICAL_NOTE_REVISION_CONFLICT"
    assert device_b.data["etag"] == device_a.data["etag"]
    assert device_b["ETag"] == device_a.data["etag"]
    assert device_b.data["content"]["treatment_plan"] == current_plan
    assert AuditEvent.objects.filter(
        entity_type="ClinicalNote",
        entity_id=device_a.data["note"],
        action="UPDATE",
    ).count() == audit_count


def test_signed_version_contains_treatment_plan_and_signed_mutation_is_blocked(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1OASign")
    treatment_plan = "Phase 1O-A synthetic signed treatment instructions.\nKeep exact line breaks."
    saved = patch_note(
        authed_client,
        encounter["id"],
        {"treatment_plan": treatment_plan},
        encounter["consultation_etag"],
    )
    assert saved.status_code == 200, saved.data

    signed = sign_note(authed_client, encounter["id"], saved.data["etag"])
    assert signed.status_code == 200, signed.data
    version = ClinicalNoteVersion.objects.get(note__encounter_id=encounter["id"])
    assert version.content["treatment_plan"] == treatment_plan
    assert version.content["treatment_plan"].splitlines() == treatment_plan.splitlines()

    rejected = patch_note(
        authed_client,
        encounter["id"],
        {"treatment_plan": "Phase 1O-A synthetic forbidden signed mutation."},
        signed.data["etag"],
    )
    assert rejected.status_code == 400
    assert ClinicalNoteVersion.objects.filter(note__encounter_id=encounter["id"]).count() == 1
    note = ClinicalNote.objects.get(encounter_id=encounter["id"])
    assert note.status == "SIGNED"
    assert note.content["treatment_plan"] == treatment_plan
    assert Encounter.objects.get(id=encounter["id"]).status == "SIGNED"
