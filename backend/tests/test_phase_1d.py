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
from tests.clinical_test_helpers import note_headers


pytestmark = pytest.mark.django_db

SYNTHETIC_FAMILY = "Phase 1D verification - synthetic family history"
SYNTHETIC_SOCIAL = "Phase 1D verification - synthetic social history"
UPDATED_FAMILY = "Phase 1D verification - updated synthetic family history"
UPDATED_SOCIAL = "Phase 1D verification - updated synthetic social history"
SYNTHETIC_COMPLAINT = "Phase 1D verification - synthetic presenting complaint"
SYNTHETIC_HPI = "Phase 1D verification - synthetic HPI"
SYNTHETIC_PMH = "Phase 1D verification - synthetic past medical history"
SYNTHETIC_PSH = "Phase 1D verification - synthetic past surgical history"
SYNTHETIC_ASSESSMENT = "Phase 1D verification - synthetic assessment"
SYNTHETIC_PLAN = "Phase 1D verification - synthetic plan"


def create_encounter(tenant, client, label="Phase1D"):
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
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1D verification - synthetic triage"},
        format="json",
    )
    assert triage.status_code == 201
    encounter = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": queue_id},
        format="json",
    )
    assert encounter.status_code == 201
    return encounter.data["id"]


def full_content():
    return {
        "presenting_complaint": SYNTHETIC_COMPLAINT,
        "hpi": SYNTHETIC_HPI,
        "past_medical_history": SYNTHETIC_PMH,
        "past_surgical_history": SYNTHETIC_PSH,
        "family_history": SYNTHETIC_FAMILY,
        "social_history": SYNTHETIC_SOCIAL,
        "consultation": "Phase 1D verification - synthetic consultation note",
        "assessment": SYNTHETIC_ASSESSMENT,
        "plan": SYNTHETIC_PLAN,
    }


def note_content(note_id):
    return ClinicalNote.objects.get(id=note_id).content


def test_phase_1d_family_social_round_trip_association_and_audit(tenant, authed_client):
    encounter_id = create_encounter(tenant, authed_client)
    content = full_content()

    saved = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": content},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert saved.status_code == 200
    note_id = saved.data["note"]
    assert str(ClinicalNote.objects.get(id=note_id).encounter_id) == encounter_id

    reloaded = authed_client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
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
    assert SYNTHETIC_FAMILY not in audit_json
    assert SYNTHETIC_SOCIAL not in audit_json
    assert "family_history" in audit_json
    assert "social_history" in audit_json


def test_phase_1d_partial_family_and_social_updates_preserve_all_note_fields(tenant, authed_client):
    encounter_id = create_encounter(tenant, authed_client)
    initial = full_content()
    saved = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": initial},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert saved.status_code == 200

    family_update = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"family_history": UPDATED_FAMILY}},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert family_update.status_code == 200
    expected_after_family = {**initial, "family_history": UPDATED_FAMILY}
    assert family_update.data["content"] == expected_after_family

    social_update = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"social_history": UPDATED_SOCIAL}},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert social_update.status_code == 200
    expected_after_social = {**expected_after_family, "social_history": UPDATED_SOCIAL}
    assert social_update.data["content"] == expected_after_social

    reloaded = authed_client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert reloaded.status_code == 200
    assert reloaded.data["notes"][0]["content"] == expected_after_social


def test_phase_1d_sign_preserves_all_history_and_note_content_and_rejects_normal_write(tenant, authed_client):
    encounter_id = create_encounter(tenant, authed_client, label="Phase1DSign")
    initial = full_content()
    saved = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": initial},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert saved.status_code == 200
    note_id = saved.data["note"]

    signed_family = "Phase 1D verification - signed synthetic family history"
    signed_social = "Phase 1D verification - signed synthetic social history"
    signed = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"family_history": signed_family, "social_history": signed_social}},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert signed.status_code == 200
    expected_signed = {
        **initial,
        "family_history": signed_family,
        "social_history": signed_social,
    }
    assert ClinicalNoteVersion.objects.get(note_id=note_id).content == expected_signed

    rejected = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"family_history": "Phase 1D verification - rejected overwrite"}},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert rejected.status_code == 400
    assert note_content(note_id) == expected_signed


@pytest.mark.parametrize("field_name", ["family_history", "social_history"])
def test_phase_1d_history_fields_validate_type_and_length(tenant, authed_client, field_name):
    encounter_id = create_encounter(tenant, authed_client, label=f"Phase1D{field_name}")
    invalid_type = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {field_name: 42}},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert invalid_type.status_code == 400
    assert field_name in invalid_type.data["content"]

    too_long = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {field_name: "x" * 4001}},
        **note_headers(authed_client, encounter_id),
        format="json",
    )
    assert too_long.status_code == 400
    assert field_name in too_long.data["content"]
    assert not ClinicalNote.objects.filter(encounter_id=encounter_id).exists()


def test_phase_1d_non_clinical_role_cannot_edit_history(tenant, authed_client):
    encounter_id = create_encounter(tenant, authed_client, label="Phase1DRole")
    nurse = User.objects.create_user("phase1d-nurse")
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
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"family_history": SYNTHETIC_FAMILY, "social_history": SYNTHETIC_SOCIAL}},
        format="json",
    )
    assert response.status_code == 403


def test_phase_1d_tenant_and_facility_isolation(tenant, authed_client):
    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="Phase 1D Other Facility",
            code="OTHER",
            mode="CLINIC",
        )
        facility_patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no="P-OTHER-FACILITY-PHASE1D",
            first_name="Other Facility",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        facility_encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            patient=facility_patient,
            encounter_no="ENC-OTHER-FACILITY-PHASE1D",
            clinician=tenant.user,
        )

    assert authed_client.get(f"/api/v1/clinic/encounters/{facility_encounter.id}/").status_code == 404
    assert authed_client.post(
        f"/api/v1/clinic/encounters/{facility_encounter.id}/notes/",
        {"content": {"family_history": SYNTHETIC_FAMILY}},
        format="json",
    ).status_code == 404

    other_org = Organisation.objects.create(name="Other Phase 1D Clinic", slug="other-phase-1d")
    with tenant_atomic(other_org.id):
        other_facility = Facility.objects.create(
            organisation=other_org,
            name="Other Facility",
            code="MAIN",
            mode="CLINIC",
        )
        other_patient = Patient.objects.create(
            organisation=other_org,
            patient_no="P-OTHER-ORG-PHASE1D",
            first_name="Other Organisation",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        other_user = User.objects.create_user("phase1d-other")
        other_encounter = Encounter.objects.create(
            organisation=other_org,
            facility=other_facility,
            patient=other_patient,
            encounter_no="ENC-OTHER-ORG-PHASE1D",
            clinician=other_user,
        )

    assert authed_client.get(f"/api/v1/clinic/encounters/{other_encounter.id}/").status_code == 404
    assert authed_client.post(
        f"/api/v1/clinic/encounters/{other_encounter.id}/notes/",
        {"content": {"social_history": SYNTHETIC_SOCIAL}},
        format="json",
    ).status_code == 404
