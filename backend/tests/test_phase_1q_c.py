import json

import pytest

from audit.models import AuditEvent
from clinical.models import Encounter
from scheduling.models import FollowUpRecommendation
from tests.clinical_test_helpers import establish_synthetic_final_diagnosis, establish_synthetic_nka_review


pytestmark = pytest.mark.django_db(transaction=True)

SYNTHETIC_TRIAGE = "Phase 1Q-C verification - synthetic triage complaint"
SYNTHETIC_COMPLAINT = {
    "text": "Phase 1Q-C verification - synthetic presenting complaint",
    "duration_value": None,
    "duration_unit": None,
}


def create_encounter(tenant, client, label="Phase1QCSynthetic"):
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
    claimed = client.post(f"/api/v1/clinic/queue/{check_in.data['id']}/claim/", {}, format="json")
    assert claimed.status_code == 200, claimed.data
    triage = client.post(
        f"/api/v1/clinic/triage/{check_in.data['id']}/",
        {"acuity": "ROUTINE", "chief_complaint": SYNTHETIC_TRIAGE},
        format="json",
    )
    assert triage.status_code == 201, triage.data
    encounter = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": check_in.data["id"]},
        format="json",
    )
    assert encounter.status_code == 201, encounter.data
    return encounter.data


def read_encounter(client, encounter_id):
    response = client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert response.status_code == 200, response.data
    return response.data


def follow_up_url(encounter_id):
    return f"/api/v1/clinic/encounters/{encounter_id}/follow-up/"


def patch_follow_up(client, encounter_id, payload, etag):
    return client.patch(
        follow_up_url(encounter_id),
        payload,
        HTTP_IF_MATCH=etag,
        format="json",
    )


def sign_encounter(client, encounter_id, etag):
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {
            "content": {"hpi": "Phase 1Q-C verification - synthetic signing note"},
            "complaints": [SYNTHETIC_COMPLAINT],
        },
        HTTP_IF_MATCH=etag,
        format="json",
    )


def prepare_review_scheduled(tenant, client, label):
    encounter = create_encounter(tenant, client, label)
    establish_synthetic_nka_review(client, encounter["id"])
    diagnosis = establish_synthetic_final_diagnosis(client, encounter["id"], include_disposition=False)
    disposition = client.patch(
        f"/api/v1/clinic/encounters/{encounter['id']}/disposition/",
        {"disposition": "REVIEW_SCHEDULED", "disposition_note": ""},
        HTTP_IF_MATCH=diagnosis["consultation_etag"],
        format="json",
    )
    assert disposition.status_code == 200, disposition.data
    return encounter, disposition.data["consultation_etag"]


def test_phase_1q_c_date_mode_round_trips_on_encounter(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QCDate")
    initial = read_encounter(authed_client, encounter["id"])
    saved = patch_follow_up(
        authed_client,
        encounter["id"],
        {
            "recommended_date": "2030-01-15",
            "instructions": "Phase 1Q-C synthetic date instruction.",
        },
        initial["consultation_etag"],
    )

    assert saved.status_code == 200, saved.data
    follow_up = saved.data["follow_up"]
    assert follow_up["recommended_date"] == "2030-01-15"
    assert follow_up["interval_value"] is None
    assert follow_up["interval_unit"] is None
    assert follow_up["instructions"] == "Phase 1Q-C synthetic date instruction."
    reloaded = read_encounter(authed_client, encounter["id"])
    assert reloaded["follow_up"] == follow_up
    assert reloaded["consultation_etag"] == saved.data["consultation_etag"]


def test_phase_1q_c_days_interval_round_trips_on_encounter(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QCDays")
    initial = read_encounter(authed_client, encounter["id"])
    saved = patch_follow_up(
        authed_client,
        encounter["id"],
        {
            "recommended_date": None,
            "interval_value": 3,
            "interval_unit": "DAYS",
            "instructions": "Phase 1Q-C synthetic three-day interval.",
        },
        initial["consultation_etag"],
    )

    assert saved.status_code == 200, saved.data
    follow_up = saved.data["follow_up"]
    assert follow_up["recommended_date"] is None
    assert follow_up["interval_value"] == 3
    assert follow_up["interval_unit"] == "DAYS"
    assert follow_up["instructions"] == "Phase 1Q-C synthetic three-day interval."
    reloaded = read_encounter(authed_client, encounter["id"])
    assert reloaded["follow_up"] == follow_up
    assert reloaded["consultation_etag"] == saved.data["consultation_etag"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"recommended_date": None, "interval_value": 3},
        {"recommended_date": None, "interval_unit": "DAYS"},
        {"recommended_date": None, "interval_value": 0, "interval_unit": "DAYS"},
        {"recommended_date": None, "interval_value": -1, "interval_unit": "DAYS"},
        {"recommended_date": None, "interval_value": 3, "interval_unit": "HOURS"},
        {"recommended_date": "2030-02-01", "interval_value": 3, "interval_unit": "DAYS"},
    ],
)
def test_phase_1q_c_invalid_schedule_has_stable_code(tenant, authed_client, payload):
    encounter = create_encounter(tenant, authed_client, "Phase1QCInvalid")
    initial = read_encounter(authed_client, encounter["id"])
    response = patch_follow_up(
        authed_client,
        encounter["id"],
        payload,
        initial["consultation_etag"],
    )

    assert response.status_code == 400, response.data
    assert response.data["code"] == "FOLLOW_UP_SCHEDULE_INVALID"
    assert FollowUpRecommendation.objects.filter(encounter_id=encounter["id"]).count() == 0


def test_phase_1q_c_date_to_interval_clears_date_and_reuses_record(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QCDateToInterval")
    first = patch_follow_up(
        authed_client,
        encounter["id"],
        {"recommended_date": "2030-03-01", "instructions": "Phase 1Q-C synthetic first mode."},
        read_encounter(authed_client, encounter["id"])["consultation_etag"],
    )
    assert first.status_code == 200, first.data

    switched = patch_follow_up(
        authed_client,
        encounter["id"],
        {
            "recommended_date": None,
            "interval_value": 3,
            "interval_unit": "DAYS",
            "instructions": "Phase 1Q-C synthetic interval mode.",
        },
        first.data["consultation_etag"],
    )

    assert switched.status_code == 200, switched.data
    assert switched.data["follow_up"]["id"] == first.data["follow_up"]["id"]
    assert switched.data["follow_up"]["recommended_date"] is None
    assert switched.data["follow_up"]["interval_value"] == 3
    assert switched.data["follow_up"]["interval_unit"] == "DAYS"
    assert FollowUpRecommendation.objects.filter(encounter_id=encounter["id"]).count() == 1


def test_phase_1q_c_interval_to_date_clears_interval_fields(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QCIntervalToDate")
    first = patch_follow_up(
        authed_client,
        encounter["id"],
        {
            "recommended_date": None,
            "interval_value": 2,
            "interval_unit": "WEEKS",
            "instructions": "Phase 1Q-C synthetic interval first.",
        },
        read_encounter(authed_client, encounter["id"])["consultation_etag"],
    )
    assert first.status_code == 200, first.data

    switched = patch_follow_up(
        authed_client,
        encounter["id"],
        {
            "recommended_date": "2030-04-15",
            "instructions": "Phase 1Q-C synthetic date mode.",
        },
        first.data["consultation_etag"],
    )

    assert switched.status_code == 200, switched.data
    assert switched.data["follow_up"]["recommended_date"] == "2030-04-15"
    assert switched.data["follow_up"]["interval_value"] is None
    assert switched.data["follow_up"]["interval_unit"] is None
    assert switched.data["follow_up"]["instructions"] == "Phase 1Q-C synthetic date mode."


def test_phase_1q_c_schedule_changes_shared_etag(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QCEtag")
    initial = read_encounter(authed_client, encounter["id"])
    date_saved = patch_follow_up(
        authed_client,
        encounter["id"],
        {"recommended_date": "2030-05-01", "instructions": "Phase 1Q-C synthetic ETag date."},
        initial["consultation_etag"],
    )
    assert date_saved.status_code == 200, date_saved.data
    interval_saved = patch_follow_up(
        authed_client,
        encounter["id"],
        {
            "recommended_date": None,
            "interval_value": 3,
            "interval_unit": "MONTHS",
        },
        date_saved.data["consultation_etag"],
    )

    assert interval_saved.status_code == 200, interval_saved.data
    assert date_saved.data["consultation_etag"] != initial["consultation_etag"]
    assert interval_saved.data["consultation_etag"] != date_saved.data["consultation_etag"]


def test_phase_1q_c_stale_interval_returns_412_with_authoritative_state(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QCStale")
    stale_etag = read_encounter(authed_client, encounter["id"])["consultation_etag"]
    first = patch_follow_up(
        authed_client,
        encounter["id"],
        {
            "recommended_date": None,
            "interval_value": 3,
            "interval_unit": "DAYS",
            "instructions": "Phase 1Q-C synthetic authoritative interval.",
        },
        stale_etag,
    )
    assert first.status_code == 200, first.data

    stale = patch_follow_up(
        authed_client,
        encounter["id"],
        {
            "recommended_date": None,
            "interval_value": 4,
            "interval_unit": "DAYS",
            "instructions": "Phase 1Q-C synthetic stale interval.",
        },
        stale_etag,
    )

    assert stale.status_code == 412, stale.data
    assert stale.data["code"] == "FOLLOW_UP_REVISION_CONFLICT"
    assert stale.data["consultation_etag"] == first.data["consultation_etag"]
    assert stale.data["follow_up"]["interval_value"] == 3
    assert stale.data["follow_up"]["interval_unit"] == "DAYS"
    assert stale.data["follow_up"]["instructions"] == "Phase 1Q-C synthetic authoritative interval."
    current = FollowUpRecommendation.objects.get(encounter_id=encounter["id"])
    assert current.interval_value == 3
    assert current.interval_unit == "DAYS"


def test_phase_1q_c_review_scheduled_sign_accepts_interval(tenant, authed_client):
    encounter, etag = prepare_review_scheduled(tenant, authed_client, "Phase1QCIntervalSign")
    saved = patch_follow_up(
        authed_client,
        encounter["id"],
        {
            "recommended_date": None,
            "interval_value": 3,
            "interval_unit": "DAYS",
            "instructions": "Phase 1Q-C synthetic signable interval.",
        },
        etag,
    )
    assert saved.status_code == 200, saved.data

    signed = sign_encounter(authed_client, encounter["id"], saved.data["consultation_etag"])

    assert signed.status_code == 200, signed.data
    assert signed.data["status"] == "SIGNED"
    assert Encounter.objects.get(id=encounter["id"]).status == "SIGNED"


def test_phase_1q_c_missing_schedule_keeps_review_sign_blocked(tenant, authed_client):
    encounter, etag = prepare_review_scheduled(tenant, authed_client, "Phase1QCMissingSign")
    missing = sign_encounter(authed_client, encounter["id"], etag)

    assert missing.status_code == 400, missing.data
    assert missing.data["code"] == "FOLLOW_UP_REQUIRED"


def test_phase_1q_c_signed_interval_mutation_is_blocked(tenant, authed_client):
    encounter, etag = prepare_review_scheduled(tenant, authed_client, "Phase1QCSigned")
    saved = patch_follow_up(
        authed_client,
        encounter["id"],
        {
            "recommended_date": None,
            "interval_value": 3,
            "interval_unit": "DAYS",
            "instructions": "Phase 1Q-C synthetic immutable interval.",
        },
        etag,
    )
    assert saved.status_code == 200, saved.data
    signed = sign_encounter(authed_client, encounter["id"], saved.data["consultation_etag"])
    assert signed.status_code == 200, signed.data

    rejected = patch_follow_up(
        authed_client,
        encounter["id"],
        {
            "recommended_date": None,
            "interval_value": 4,
            "interval_unit": "DAYS",
            "instructions": "Phase 1Q-C synthetic forbidden interval.",
        },
        signed.data["etag"],
    )

    assert rejected.status_code == 400, rejected.data
    assert rejected.data["code"] == "FOLLOW_UP_IMMUTABLE"
    current = FollowUpRecommendation.objects.get(encounter_id=encounter["id"])
    assert current.interval_value == 3
    assert current.interval_unit == "DAYS"


def test_phase_1q_c_audit_contains_only_schedule_metadata(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QCAudit")
    instruction = "Phase 1Q-C verification - synthetic interval instruction excluded from audit"
    initial = read_encounter(authed_client, encounter["id"])
    saved = patch_follow_up(
        authed_client,
        encounter["id"],
        {
            "recommended_date": None,
            "interval_value": 3,
            "interval_unit": "DAYS",
            "instructions": instruction,
        },
        initial["consultation_etag"],
    )
    assert saved.status_code == 200, saved.data

    event = AuditEvent.objects.get(
        organisation=tenant.organisation,
        facility=tenant.facility,
        entity_type="FollowUpRecommendation",
        entity_id=saved.data["follow_up"]["id"],
    )
    audit_json = json.dumps({"before": event.before, "after": event.after}, default=str)

    assert instruction not in audit_json
    assert '"recommended_date": "2030-' not in audit_json
    assert '"interval_value": 3' not in audit_json
    assert '"interval_unit": "DAYS"' not in audit_json
    assert event.after["schedule_mode"] == "INTERVAL"
    assert event.after["interval_value_present"] is True
    assert event.after["interval_unit_present"] is True
    assert set(["interval_value", "interval_unit"]).issubset(event.after["changed_fields"])