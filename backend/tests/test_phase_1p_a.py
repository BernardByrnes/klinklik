import json

import pytest
from rest_framework.test import APIClient

from accounts.bootstrap import open_session
from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from audit.models import AuditEvent
from clinical.dispositions import set_disposition
from clinical.models import ClinicalNote, ClinicalNoteVersion, Encounter
from core.services import tenant_atomic
from patients.models import Patient
from tenancy.models import Facility, Organisation
from tests.clinical_test_helpers import establish_synthetic_final_diagnosis, establish_synthetic_nka_review


pytestmark = pytest.mark.django_db(transaction=True)

SYNTHETIC_TRIAGE = "Phase 1P-A verification - synthetic triage complaint"
SYNTHETIC_COMPLAINT = {
    "text": "Phase 1P-A verification - synthetic presenting complaint",
    "duration_value": None,
    "duration_unit": None,
}
SYNTHETIC_OTHER_NOTE = "Phase 1P-A verification - synthetic disposition note"

CANONICAL_DISPOSITIONS = [
    "TREATED_AND_DISCHARGED",
    "REVIEW_SCHEDULED",
    "REFERRED_OUT",
    "ADMITTED_ELSEWHERE",
    "LEFT_AGAINST_ADVICE",
    "DECEASED",
    "OTHER",
]


def create_encounter(tenant, client, label="Phase1PASynthetic"):
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
    claimed = client.post(f"/api/v1/clinic/queue/{queue_id}/claim/", {}, format="json")
    assert claimed.status_code == 200, claimed.data

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
    return encounter.data


def read_encounter(client, encounter_id):
    response = client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert response.status_code == 200, response.data
    return response.data


def disposition_url(encounter_id):
    return f"/api/v1/clinic/encounters/{encounter_id}/disposition/"


def patch_disposition(client, encounter_id, payload, etag):
    return client.patch(
        disposition_url(encounter_id),
        payload,
        format="json",
        HTTP_IF_MATCH=etag,
    )


def sign_note(client, encounter_id, etag):
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {
            "content": {"hpi": "Phase 1P-A verification - synthetic signing note"},
            "complaints": [SYNTHETIC_COMPLAINT],
        },
        format="json",
        HTTP_IF_MATCH=etag,
    )


def prepare_signable(tenant, client, label):
    encounter = create_encounter(tenant, client, label)
    review = establish_synthetic_nka_review(client, encounter["id"])
    assert review["allergies_review_is_current"] is True
    diagnosis = establish_synthetic_final_diagnosis(client, encounter["id"], include_disposition=False)
    return encounter, diagnosis["consultation_etag"]


def test_disposition_round_trip_is_exposed_and_changes_shared_consultation_etag(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1PARoundTrip")
    initial = read_encounter(authed_client, encounter["id"])

    assert initial["status"] == "OPEN"
    assert initial["disposition"] is None
    assert initial["disposition_note"] == ""

    saved = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "TREATED_AND_DISCHARGED", "disposition_note": ""},
        initial["consultation_etag"],
    )

    assert saved.status_code == 200, saved.data
    assert saved.data["disposition"] == "TREATED_AND_DISCHARGED"
    assert saved.data["disposition_note"] == ""
    assert saved.data["encounter_status"] == "OPEN"
    assert saved.data["consultation_etag"] != initial["consultation_etag"]
    assert saved["ETag"] == saved.data["consultation_etag"]

    reloaded = read_encounter(authed_client, encounter["id"])
    assert reloaded["disposition"] == "TREATED_AND_DISCHARGED"
    assert reloaded["disposition_note"] == ""
    assert reloaded["consultation_etag"] == saved.data["consultation_etag"]
    assert "disposition" not in json.dumps(reloaded.get("notes", []))


def test_all_canonical_dispositions_can_be_stored_without_dependent_records(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1PAMatrix")
    etag = read_encounter(authed_client, encounter["id"])["consultation_etag"]

    for disposition in CANONICAL_DISPOSITIONS:
        note = SYNTHETIC_OTHER_NOTE if disposition == "OTHER" else ""
        response = patch_disposition(
            authed_client,
            encounter["id"],
            {"disposition": disposition, "disposition_note": note},
            etag,
        )
        assert response.status_code == 200, response.data
        assert response.data["disposition"] == disposition
        assert response.data["disposition_note"] == note
        etag = response.data["consultation_etag"]


def test_invalid_disposition_enum_is_rejected_without_mutation(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1PAInvalidEnum")
    initial = read_encounter(authed_client, encounter["id"])

    rejected = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "NOT_A_CANONICAL_DISPOSITION", "disposition_note": ""},
        initial["consultation_etag"],
    )

    assert rejected.status_code == 400
    assert "disposition" in rejected.data
    current = read_encounter(authed_client, encounter["id"])
    assert current["disposition"] is None
    assert current["disposition_note"] == ""
    assert current["consultation_etag"] == initial["consultation_etag"]

def test_other_requires_non_whitespace_note_and_patch_preserves_or_clears_note(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1PAOther")
    etag = read_encounter(authed_client, encounter["id"])["consultation_etag"]

    blank = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "OTHER", "disposition_note": "   "},
        etag,
    )
    assert blank.status_code == 400
    assert blank.data["code"] == "DISPOSITION_NOTE_REQUIRED"

    saved = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "OTHER", "disposition_note": SYNTHETIC_OTHER_NOTE},
        etag,
    )
    assert saved.status_code == 200, saved.data

    preserved = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "ADMITTED_ELSEWHERE"},
        saved.data["consultation_etag"],
    )
    assert preserved.status_code == 200, preserved.data
    assert preserved.data["disposition_note"] == SYNTHETIC_OTHER_NOTE

    cleared = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "TREATED_AND_DISCHARGED", "disposition_note": ""},
        preserved.data["consultation_etag"],
    )
    assert cleared.status_code == 200, cleared.data
    assert cleared.data["disposition_note"] == ""


def test_disposition_requires_if_match_and_rejects_stale_shared_etag(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1PAConcurrency")
    initial = read_encounter(authed_client, encounter["id"])

    missing = authed_client.patch(
        disposition_url(encounter["id"]),
        {"disposition": "TREATED_AND_DISCHARGED", "disposition_note": ""},
        format="json",
    )
    assert missing.status_code == 428
    assert missing.data["code"] == "PRECONDITION_REQUIRED"

    first = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "TREATED_AND_DISCHARGED", "disposition_note": ""},
        initial["consultation_etag"],
    )
    assert first.status_code == 200, first.data

    stale = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "DECEASED", "disposition_note": ""},
        initial["consultation_etag"],
    )
    assert stale.status_code == 412, stale.data
    assert stale.data["code"] == "DISPOSITION_REVISION_CONFLICT"
    assert stale.data["disposition"] == "TREATED_AND_DISCHARGED"
    assert stale.data["disposition_note"] == ""
    assert stale.data["consultation_etag"] == first.data["consultation_etag"]
    assert stale["ETag"] == first.data["consultation_etag"]

    current = read_encounter(authed_client, encounter["id"])
    assert current["disposition"] == "TREATED_AND_DISCHARGED"
    assert current["consultation_etag"] == first.data["consultation_etag"]


def test_disposition_participates_in_note_etag_and_note_conflict_authority(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1PASharedEtag")
    initial = read_encounter(authed_client, encounter["id"])

    disposition = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "LEFT_AGAINST_ADVICE", "disposition_note": ""},
        initial["consultation_etag"],
    )
    assert disposition.status_code == 200, disposition.data

    note = authed_client.patch(
        f"/api/v1/clinic/encounters/{encounter['id']}/notes/",
        {"content": {"hpi": "Phase 1P-A verification - synthetic shared ETag note"}},
        format="json",
        HTTP_IF_MATCH=disposition.data["consultation_etag"],
    )
    assert note.status_code == 200, note.data

    stale_disposition = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "DECEASED", "disposition_note": ""},
        disposition.data["consultation_etag"],
    )
    assert stale_disposition.status_code == 412, stale_disposition.data
    assert stale_disposition.data["disposition"] == "LEFT_AGAINST_ADVICE"
    assert stale_disposition.data["content"]["hpi"] == "Phase 1P-A verification - synthetic shared ETag note"
    assert stale_disposition.data["consultation_etag"] == note.data["etag"]


def test_disposition_service_mutation_is_transactional_and_returns_authoritative_etag(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1PAService")
    current = read_encounter(authed_client, encounter["id"])
    model_encounter = Encounter.objects.get(id=encounter["id"])

    result = set_disposition(
        organisation=tenant.organisation,
        facility=tenant.facility,
        actor=tenant.user,
        encounter=model_encounter,
        data={"disposition": "TREATED_AND_DISCHARGED", "disposition_note": ""},
        expected_etag=current["consultation_etag"],
    )

    assert result["encounter"].disposition == "TREATED_AND_DISCHARGED"
    assert result["consultation_etag"]
    assert Encounter.objects.get(id=encounter["id"]).disposition == "TREATED_AND_DISCHARGED"


def assert_no_sign_side_effects(tenant, encounter_id):
    assert Encounter.objects.get(id=encounter_id).status == "OPEN"
    assert not ClinicalNoteVersion.objects.filter(note__encounter_id=encounter_id).exists()
    assert not AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        action="SIGN",
        entity_type="ClinicalNote",
    ).exists()

def test_signing_requires_disposition_and_blocks_unimplemented_dependencies(tenant, authed_client):
    encounter, etag = prepare_signable(tenant, authed_client, "Phase1PASignDependencies")

    missing = sign_note(authed_client, encounter["id"], etag)
    assert missing.status_code == 400, missing.data
    assert missing.data["code"] == "DISPOSITION_REQUIRED"


    referred = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "REFERRED_OUT", "disposition_note": ""},
        etag,
    )
    assert referred.status_code == 200, referred.data

    referral_missing = sign_note(authed_client, encounter["id"], referred.data["consultation_etag"])
    assert referral_missing.status_code == 400, referral_missing.data
    assert referral_missing.data["code"] == "REFERRAL_REQUIRED"


    review = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "REVIEW_SCHEDULED", "disposition_note": ""},
        referred.data["consultation_etag"],
    )
    assert review.status_code == 200, review.data

    follow_up_missing = sign_note(authed_client, encounter["id"], review.data["consultation_etag"])
    assert follow_up_missing.status_code == 400, follow_up_missing.data
    assert follow_up_missing.data["code"] == "FOLLOW_UP_REQUIRED"



def test_treated_and_other_and_deceased_can_satisfy_signing_when_other_rules_pass(tenant, authed_client):
    for label, disposition, note in [
        ("Phase1PATreatedSign", "TREATED_AND_DISCHARGED", ""),
        ("Phase1PAAdmittedSign", "ADMITTED_ELSEWHERE", ""),
        ("Phase1PALeftSign", "LEFT_AGAINST_ADVICE", ""),
        ("Phase1PAOtherSign", "OTHER", SYNTHETIC_OTHER_NOTE),
        ("Phase1PADeceasedSign", "DECEASED", ""),
    ]:
        encounter, etag = prepare_signable(tenant, authed_client, label)
        saved = patch_disposition(
            authed_client,
            encounter["id"],
            {"disposition": disposition, "disposition_note": note},
            etag,
        )
        assert saved.status_code == 200, saved.data

        signed = sign_note(authed_client, encounter["id"], saved.data["consultation_etag"])
        assert signed.status_code == 200, signed.data
        assert signed.data["status"] == "SIGNED"
        assert Encounter.objects.get(id=encounter["id"]).disposition == disposition
        assert ClinicalNoteVersion.objects.filter(note__encounter_id=encounter["id"]).count() == 1


def test_signed_encounter_rejects_disposition_mutation_without_state_change(tenant, authed_client):
    encounter, etag = prepare_signable(tenant, authed_client, "Phase1PASignedImmutable")
    saved = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "TREATED_AND_DISCHARGED", "disposition_note": ""},
        etag,
    )
    assert saved.status_code == 200, saved.data

    signed = sign_note(authed_client, encounter["id"], saved.data["consultation_etag"])
    assert signed.status_code == 200, signed.data

    rejected = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "OTHER", "disposition_note": SYNTHETIC_OTHER_NOTE},
        signed.data["etag"],
    )
    assert rejected.status_code == 400, rejected.data
    assert rejected.data["code"] == "DISPOSITION_IMMUTABLE"
    final = Encounter.objects.get(id=encounter["id"])
    assert final.status == "SIGNED"
    assert final.disposition == "TREATED_AND_DISCHARGED"
    assert final.disposition_note == ""


def test_disposition_mutation_requires_clinical_capability(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1PAPermission")
    etag = read_encounter(authed_client, encounter["id"])["consultation_etag"]

    reception = User.objects.create_user("phase1pa-reception")
    with tenant_atomic(tenant.organisation.id):
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=reception)
        role = Role.objects.get(organisation=tenant.organisation, template_code="RECEPTION_CASHIER")
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=reception,
            role=role,
            facility=tenant.facility,
            department=tenant.department,
        )

    reception_client = APIClient()
    opened = open_session(reception, tenant.organisation.id)
    reception_client.credentials(
        HTTP_AUTHORIZATION="Bearer " + opened.access_token,
        HTTP_X_FACILITY_ID=str(tenant.facility.id),
    )
    response = patch_disposition(
        reception_client,
        encounter["id"],
        {"disposition": "TREATED_AND_DISCHARGED", "disposition_note": ""},
        etag,
    )
    assert response.status_code == 403


def test_disposition_scope_is_limited_to_active_facility_and_organisation(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1PAScope")

    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="Phase 1P-A Other Facility",
            code="PHASE1PA-OTHER",
            mode="CLINIC",
        )
        patient = Patient.objects.get(id=encounter["patient"])
        facility_encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            patient=patient,
            encounter_no="PHASE1PA-OTHER-ENC",
            clinician=tenant.user,
        )

    facility_response = patch_disposition(
        authed_client,
        str(facility_encounter.id),
        {"disposition": "TREATED_AND_DISCHARGED", "disposition_note": ""},
        "not-visible",
    )
    assert facility_response.status_code == 404

    other_organisation = Organisation.objects.create(
        name="Phase 1P-A Other Organisation",
        slug="phase-1pa-other-organisation",
    )
    with tenant_atomic(other_organisation.id):
        other_facility = Facility.objects.create(
            organisation=other_organisation,
            name="Phase 1P-A Other Organisation Facility",
            code="MAIN",
            mode="CLINIC",
        )
        other_patient = Patient.objects.create(
            organisation=other_organisation,
            patient_no="P1PA-OTHER-1",
            first_name="Phase1PA",
            last_name="OtherOrganisationSynthetic",
            sex="UNKNOWN",
        )
        other_user = User.objects.create_user("phase1pa-other-clinician")
        other_encounter = Encounter.objects.create(
            organisation=other_organisation,
            facility=other_facility,
            patient=other_patient,
            encounter_no="PHASE1PA-OTHER-ORG-ENC",
            clinician=other_user,
        )

    organisation_response = patch_disposition(
        authed_client,
        str(other_encounter.id),
        {"disposition": "TREATED_AND_DISCHARGED", "disposition_note": ""},
        "not-visible",
    )
    assert organisation_response.status_code == 404


def test_disposition_audit_records_state_metadata_without_raw_note(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1PAAudit")
    etag = read_encounter(authed_client, encounter["id"])["consultation_etag"]
    before_count = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        entity_type="Encounter",
        entity_id=str(encounter["id"]),
        action="UPDATE",
    ).count()

    saved = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "OTHER", "disposition_note": SYNTHETIC_OTHER_NOTE},
        etag,
    )
    assert saved.status_code == 200, saved.data

    events = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        entity_type="Encounter",
        entity_id=str(encounter["id"]),
        action="UPDATE",
    )
    assert events.count() == before_count + 1
    event = events.latest("occurred_at")
    audit_json = json.dumps({"before": event.before, "after": event.after}, default=str)
    assert "disposition" in audit_json
    assert "disposition_note_present" in audit_json
    assert SYNTHETIC_OTHER_NOTE not in audit_json
    assert event.after["changed_fields"] == ["disposition", "disposition_note"]


def test_disposition_write_does_not_create_a_clinical_note(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1PAPureEncounterState")
    etag = read_encounter(authed_client, encounter["id"])["consultation_etag"]

    saved = patch_disposition(
        authed_client,
        encounter["id"],
        {"disposition": "ADMITTED_ELSEWHERE", "disposition_note": ""},
        etag,
    )

    assert saved.status_code == 200, saved.data
    assert not ClinicalNote.objects.filter(encounter_id=encounter["id"]).exists()
    assert Encounter.objects.get(id=encounter["id"]).disposition == "ADMITTED_ELSEWHERE"
