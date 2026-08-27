import json

import pytest
from rest_framework.test import APIClient

from accounts.bootstrap import open_session
from accounts.models import OrganisationMembership, Permission, Role, User, UserFacilityRole
from audit.models import AuditEvent
from clinical.models import Encounter
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import FollowUpRecommendation
from tenancy.models import Facility, Organisation
from tests.clinical_test_helpers import establish_synthetic_final_diagnosis, establish_synthetic_nka_review


pytestmark = pytest.mark.django_db(transaction=True)

SYNTHETIC_TRIAGE = "Phase 1Q-A verification - synthetic triage complaint"
SYNTHETIC_COMPLAINT = {
    "text": "Phase 1Q-A verification - synthetic presenting complaint",
    "duration_value": None,
    "duration_unit": None,
}
SYNTHETIC_INSTRUCTIONS = "  Phase 1Q-A verification - synthetic follow-up instruction.\nReturn in 7 days.  "


def create_encounter(tenant, client, label="Phase1QASynthetic"):
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
            "content": {"hpi": "Phase 1Q-A verification - synthetic signing note"},
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


def test_follow_up_create_round_trips_and_is_exposed_on_encounter(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QACreate")
    initial = read_encounter(authed_client, encounter["id"])
    assert initial["follow_up"] is None

    missing_if_match = authed_client.patch(
        follow_up_url(encounter["id"]),
        {"recommended_date": "2030-01-15", "instructions": SYNTHETIC_INSTRUCTIONS},
        format="json",
    )
    assert missing_if_match.status_code == 428

    saved = patch_follow_up(
        authed_client,
        encounter["id"],
        {"recommended_date": "2030-01-15", "instructions": SYNTHETIC_INSTRUCTIONS},
        initial["consultation_etag"],
    )
    assert saved.status_code == 200, saved.data
    assert saved["ETag"] == saved.data["consultation_etag"]
    assert saved.data["consultation_etag"] != initial["consultation_etag"]
    assert str(saved.data["follow_up"]["patient"]) == str(encounter["patient"])
    assert str(saved.data["follow_up"]["encounter"]) == encounter["id"]
    assert saved.data["follow_up"]["recommended_date"] == "2030-01-15"
    assert saved.data["follow_up"]["instructions"] == SYNTHETIC_INSTRUCTIONS
    assert FollowUpRecommendation.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        encounter_id=encounter["id"],
    ).count() == 1

    endpoint_reload = authed_client.get(follow_up_url(encounter["id"]))
    assert endpoint_reload.status_code == 200, endpoint_reload.data
    assert endpoint_reload.data["follow_up"] == saved.data["follow_up"]
    encounter_reload = read_encounter(authed_client, encounter["id"])
    assert encounter_reload["follow_up"] == saved.data["follow_up"]
    assert encounter_reload["consultation_etag"] == saved.data["consultation_etag"]


def test_follow_up_update_reuses_one_authoritative_record_and_preserves_partial_fields(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QAUpdate")
    first = patch_follow_up(
        authed_client,
        encounter["id"],
        {"recommended_date": "2030-02-01", "instructions": "Phase 1Q-A synthetic first instruction."},
        read_encounter(authed_client, encounter["id"])["consultation_etag"],
    )
    assert first.status_code == 200, first.data

    second = patch_follow_up(
        authed_client,
        encounter["id"],
        {"instructions": "Phase 1Q-A synthetic updated instruction."},
        first.data["consultation_etag"],
    )
    assert second.status_code == 200, second.data
    assert second.data["follow_up"]["id"] == first.data["follow_up"]["id"]
    assert second.data["follow_up"]["recommended_date"] == "2030-02-01"
    assert second.data["follow_up"]["instructions"] == "Phase 1Q-A synthetic updated instruction."
    assert FollowUpRecommendation.objects.filter(encounter_id=encounter["id"]).count() == 1

    third = patch_follow_up(
        authed_client,
        encounter["id"],
        {"recommended_date": "2030-02-14"},
        second.data["consultation_etag"],
    )
    assert third.status_code == 200, third.data
    assert third.data["follow_up"]["recommended_date"] == "2030-02-14"
    assert third.data["follow_up"]["instructions"] == "Phase 1Q-A synthetic updated instruction."
    assert FollowUpRecommendation.objects.filter(encounter_id=encounter["id"]).count() == 1


def test_stale_follow_up_mutation_returns_412_and_preserves_authoritative_record(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QAStale")
    stale_etag = read_encounter(authed_client, encounter["id"])["consultation_etag"]
    first = patch_follow_up(
        authed_client,
        encounter["id"],
        {"recommended_date": "2030-03-01", "instructions": "Phase 1Q-A synthetic authoritative instruction."},
        stale_etag,
    )
    assert first.status_code == 200, first.data
    audit_count = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        entity_type="FollowUpRecommendation",
        entity_id=first.data["follow_up"]["id"],
    ).count()

    stale = patch_follow_up(
        authed_client,
        encounter["id"],
        {"recommended_date": "2030-04-01", "instructions": "Phase 1Q-A synthetic stale instruction."},
        stale_etag,
    )
    assert stale.status_code == 412, stale.data
    assert stale.data["code"] == "FOLLOW_UP_REVISION_CONFLICT"
    assert stale.data["consultation_etag"] == first.data["consultation_etag"]
    assert stale["ETag"] == first.data["consultation_etag"]
    assert stale.data["follow_up"]["instructions"] == "Phase 1Q-A synthetic authoritative instruction."
    assert FollowUpRecommendation.objects.get(id=first.data["follow_up"]["id"]).instructions == (
        "Phase 1Q-A synthetic authoritative instruction."
    )
    assert AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        entity_type="FollowUpRecommendation",
        entity_id=first.data["follow_up"]["id"],
    ).count() == audit_count


def test_follow_up_participates_in_shared_consultation_etag(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QASharedEtag")
    initial = read_encounter(authed_client, encounter["id"])
    saved = patch_follow_up(
        authed_client,
        encounter["id"],
        {"recommended_date": "2030-05-01", "instructions": "Phase 1Q-A synthetic shared ETag instruction."},
        initial["consultation_etag"],
    )
    assert saved.status_code == 200, saved.data
    stale_note = authed_client.patch(
        f"/api/v1/clinic/encounters/{encounter['id']}/notes/",
        {"content": {"hpi": "Phase 1Q-A synthetic stale note"}},
        HTTP_IF_MATCH=initial["consultation_etag"],
        format="json",
    )
    assert stale_note.status_code == 412, stale_note.data
    assert stale_note.data["follow_up"]["instructions"] == "Phase 1Q-A synthetic shared ETag instruction."
    assert stale_note.data["consultation_etag"] == saved.data["consultation_etag"]


def test_review_scheduled_sign_requires_follow_up_then_succeeds(tenant, authed_client):
    encounter, etag = prepare_review_scheduled(tenant, authed_client, "Phase1QAReviewSign")
    missing = sign_encounter(authed_client, encounter["id"], etag)
    assert missing.status_code == 400, missing.data
    assert missing.data["code"] == "FOLLOW_UP_REQUIRED"

    saved = patch_follow_up(
        authed_client,
        encounter["id"],
        {"recommended_date": "2030-06-01", "instructions": "Phase 1Q-A synthetic review follow-up."},
        etag,
    )
    assert saved.status_code == 200, saved.data
    signed = sign_encounter(authed_client, encounter["id"], saved.data["consultation_etag"])
    assert signed.status_code == 200, signed.data
    assert signed.data["status"] == "SIGNED"
    assert Encounter.objects.get(id=encounter["id"]).status == "SIGNED"


def test_signed_encounter_blocks_follow_up_mutation(tenant, authed_client):
    encounter, etag = prepare_review_scheduled(tenant, authed_client, "Phase1QASigned")
    saved = patch_follow_up(
        authed_client,
        encounter["id"],
        {"recommended_date": "2030-07-01", "instructions": "Phase 1Q-A synthetic signed follow-up."},
        etag,
    )
    assert saved.status_code == 200, saved.data
    signed = sign_encounter(authed_client, encounter["id"], saved.data["consultation_etag"])
    assert signed.status_code == 200, signed.data

    rejected = patch_follow_up(
        authed_client,
        encounter["id"],
        {"recommended_date": "2030-08-01", "instructions": "Phase 1Q-A synthetic forbidden mutation."},
        signed.data["etag"],
    )
    assert rejected.status_code == 400, rejected.data
    assert rejected.data["code"] == "FOLLOW_UP_IMMUTABLE"
    current = FollowUpRecommendation.objects.get(encounter_id=encounter["id"])
    assert current.recommended_date.isoformat() == "2030-07-01"
    assert current.instructions == "Phase 1Q-A synthetic signed follow-up."


def test_follow_up_requires_clinical_capability_and_allows_midwife_role(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QARoles")
    etag = read_encounter(authed_client, encounter["id"])["consultation_etag"]
    midwife = User.objects.create_user("phase1qa-midwife")
    reception = User.objects.create_user("phase1qa-reception")
    with tenant_atomic(tenant.organisation.id):
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=midwife)
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=reception)
        midwife_role = Role.objects.create(
            organisation=tenant.organisation,
            name="Phase 1Q-A Midwife",
            template_code="MIDWIFE",
        )
        clinical_permission = Permission.objects.get(code="clinical.note.create")
        from accounts.models import RolePermission

        RolePermission.objects.create(
            organisation=tenant.organisation,
            role=midwife_role,
            permission=clinical_permission,
        )
        reception_role = Role.objects.get(organisation=tenant.organisation, template_code="RECEPTION_CASHIER")
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=midwife,
            role=midwife_role,
            facility=tenant.facility,
            department=tenant.department,
        )
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=reception,
            role=reception_role,
            facility=tenant.facility,
            department=tenant.department,
        )

    midwife_client = APIClient()
    midwife_session = open_session(midwife, tenant.organisation.id)
    midwife_client.credentials(
        HTTP_AUTHORIZATION="Bearer " + midwife_session.access_token,
        HTTP_X_FACILITY_ID=str(tenant.facility.id),
    )
    allowed = patch_follow_up(
        midwife_client,
        encounter["id"],
        {"recommended_date": "2030-09-01", "instructions": "Phase 1Q-A synthetic midwife instruction."},
        etag,
    )
    assert allowed.status_code == 200, allowed.data

    reception_client = APIClient()
    reception_session = open_session(reception, tenant.organisation.id)
    reception_client.credentials(
        HTTP_AUTHORIZATION="Bearer " + reception_session.access_token,
        HTTP_X_FACILITY_ID=str(tenant.facility.id),
    )
    denied = patch_follow_up(
        reception_client,
        encounter["id"],
        {"recommended_date": "2030-10-01", "instructions": "Phase 1Q-A synthetic denied instruction."},
        allowed.data["consultation_etag"],
    )
    assert denied.status_code == 403


def test_follow_up_scope_is_limited_to_active_facility_and_organisation(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QAScope")
    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="Phase 1Q-A Other Facility",
            code="PHASE1QA-OTHER",
            mode="CLINIC",
        )
        patient = Patient.objects.get(id=encounter["patient"])
        facility_encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            patient=patient,
            encounter_no="PHASE1QA-OTHER-ENC",
            clinician=tenant.user,
        )

    facility_response = patch_follow_up(
        authed_client,
        str(facility_encounter.id),
        {"recommended_date": "2030-11-01", "instructions": "Phase 1Q-A synthetic facility-hidden."},
        "not-visible",
    )
    assert facility_response.status_code == 404

    other_organisation = Organisation.objects.create(
        name="Phase 1Q-A Other Organisation",
        slug="phase-1qa-other-organisation",
    )
    with tenant_atomic(other_organisation.id):
        other_facility = Facility.objects.create(
            organisation=other_organisation,
            name="Phase 1Q-A Other Organisation Facility",
            code="MAIN",
            mode="CLINIC",
        )
        other_patient = Patient.objects.create(
            organisation=other_organisation,
            patient_no="P1QA-OTHER-1",
            first_name="Phase1QA",
            last_name="OtherOrganisationSynthetic",
            sex="UNKNOWN",
        )
        other_encounter = Encounter.objects.create(
            organisation=other_organisation,
            facility=other_facility,
            patient=other_patient,
            encounter_no="PHASE1QA-OTHER-ORG-ENC",
            clinician=tenant.user,
        )

    organisation_response = patch_follow_up(
        authed_client,
        str(other_encounter.id),
        {"recommended_date": "2030-12-01", "instructions": "Phase 1Q-A synthetic org-hidden."},
        "not-visible",
    )
    assert organisation_response.status_code == 404


def test_follow_up_audit_contains_metadata_without_raw_instructions(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1QAAudit")
    instruction = "Phase 1Q-A verification - synthetic instruction excluded from audit"
    initial = read_encounter(authed_client, encounter["id"])
    saved = patch_follow_up(
        authed_client,
        encounter["id"],
        {"recommended_date": "2031-01-01", "instructions": instruction},
        initial["consultation_etag"],
    )
    assert saved.status_code == 200, saved.data
    events = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        entity_type="FollowUpRecommendation",
        entity_id=saved.data["follow_up"]["id"],
    )
    assert events.count() == 1
    audit_json = json.dumps(
        {"before": events.first().before, "after": events.first().after},
        default=str,
    )
    assert instruction not in audit_json
    assert "instructions_present" in audit_json
    assert "changed_fields" in audit_json

    updated_instruction = "Phase 1Q-A verification - synthetic updated instruction excluded from audit"
    updated = patch_follow_up(
        authed_client,
        encounter["id"],
        {"instructions": updated_instruction},
        saved.data["consultation_etag"],
    )
    assert updated.status_code == 200, updated.data
    all_audit = json.dumps(
        [
            {"before": event.before, "after": event.after}
            for event in events.order_by("occurred_at")
        ],
        default=str,
    )
    assert instruction not in all_audit
    assert updated_instruction not in all_audit