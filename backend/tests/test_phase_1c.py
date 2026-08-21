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


pytestmark = pytest.mark.django_db

SYNTHETIC_COMPLAINT = "Phase 1C verification — synthetic presenting complaint"
SYNTHETIC_HPI = "Phase 1C verification — synthetic HPI"
SYNTHETIC_PMH = "Phase 1C verification — synthetic past medical history"
SYNTHETIC_PSH = "Phase 1C verification — synthetic past surgical history"
SYNTHETIC_ASSESSMENT = "Phase 1C verification — synthetic assessment"
SYNTHETIC_PLAN = "Phase 1C verification — synthetic plan"


def create_encounter(tenant, client, label="Phase1C"):
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
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1C verification — synthetic triage"},
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
        "assessment": SYNTHETIC_ASSESSMENT,
        "plan": SYNTHETIC_PLAN,
    }


def test_phase_1c_history_merge_reload_association_audit_and_signed_immutability(tenant, authed_client):
    encounter_id = create_encounter(tenant, authed_client)
    initial = full_content()

    saved = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": initial},
        format="json",
    )
    assert saved.status_code == 200
    note_id = saved.data["note"]
    assert str(ClinicalNote.objects.get(id=note_id).encounter_id) == encounter_id

    updated_pmh = "Phase 1C verification — updated synthetic past medical history"
    pmh_update = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"past_medical_history": updated_pmh}},
        format="json",
    )
    assert pmh_update.status_code == 200

    updated_hpi = "Phase 1C verification — updated synthetic HPI"
    updated_assessment = "Phase 1C verification — updated synthetic assessment"
    second_update = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"hpi": updated_hpi, "assessment": updated_assessment}},
        format="json",
    )
    assert second_update.status_code == 200

    expected_before_sign = {
        **initial,
        "past_medical_history": updated_pmh,
        "hpi": updated_hpi,
        "assessment": updated_assessment,
    }
    reloaded = authed_client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert reloaded.status_code == 200
    assert reloaded.data["notes"][0]["content"] == expected_before_sign

    audit_events = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        entity_type="ClinicalNote",
        entity_id=note_id,
    )
    audit_json = json.dumps(
        [{"before": event.before, "after": event.after, "reason": event.reason} for event in audit_events]
    )
    for raw_value in (SYNTHETIC_PMH, updated_pmh, SYNTHETIC_PSH, SYNTHETIC_HPI, updated_hpi):
        assert raw_value not in audit_json
    assert "past_medical_history" in audit_json
    assert "past_surgical_history" in audit_json

    signed_surgical_history = "Phase 1C verification — signed synthetic surgical history"
    signed = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"past_surgical_history": signed_surgical_history}},
        format="json",
    )
    assert signed.status_code == 200
    assert Encounter.objects.get(id=encounter_id).status == "SIGNED"
    assert ClinicalNoteVersion.objects.get(note_id=note_id).content == {
        **expected_before_sign,
        "past_surgical_history": signed_surgical_history,
    }

    rejected = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"past_medical_history": "Phase 1C verification — rejected overwrite"}},
        format="json",
    )
    assert rejected.status_code == 400
    unchanged = authed_client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert unchanged.status_code == 200
    assert unchanged.data["notes"][0]["content"] == {
        **expected_before_sign,
        "past_surgical_history": signed_surgical_history,
    }


def test_phase_1c_history_tenant_and_facility_isolation(tenant, authed_client):
    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="Phase 1C Other Facility",
            code="OTHER",
            mode="CLINIC",
        )
        facility_patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no="P-OTHER-FACILITY-PHASE1C",
            first_name="Other Facility",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        facility_encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            patient=facility_patient,
            encounter_no="ENC-OTHER-FACILITY-PHASE1C",
            clinician=tenant.user,
        )

    assert authed_client.get(f"/api/v1/clinic/encounters/{facility_encounter.id}/").status_code == 404
    assert authed_client.post(
        f"/api/v1/clinic/encounters/{facility_encounter.id}/notes/",
        {"content": {"past_medical_history": SYNTHETIC_PMH}},
        format="json",
    ).status_code == 404

    other_org = Organisation.objects.create(name="Other Phase 1C Clinic", slug="other-phase-1c")
    with tenant_atomic(other_org.id):
        other_facility = Facility.objects.create(
            organisation=other_org,
            name="Other Facility",
            code="MAIN",
            mode="CLINIC",
        )
        other_patient = Patient.objects.create(
            organisation=other_org,
            patient_no="P-OTHER-ORG-PHASE1C",
            first_name="Other Organisation",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        other_user = User.objects.create_user("phase1c-other")
        other_encounter = Encounter.objects.create(
            organisation=other_org,
            facility=other_facility,
            patient=other_patient,
            encounter_no="ENC-OTHER-ORG-PHASE1C",
            clinician=other_user,
        )

    assert authed_client.get(f"/api/v1/clinic/encounters/{other_encounter.id}/").status_code == 404
    assert authed_client.post(
        f"/api/v1/clinic/encounters/{other_encounter.id}/notes/",
        {"content": {"past_surgical_history": SYNTHETIC_PSH}},
        format="json",
    ).status_code == 404


def test_phase_1c_non_clinical_role_cannot_edit_history(tenant, authed_client):
    encounter_id = create_encounter(tenant, authed_client, label="Phase1CRole")
    nurse = User.objects.create_user("phase1c-nurse")
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
        {"content": {"past_medical_history": SYNTHETIC_PMH}},
        format="json",
    )
    assert response.status_code == 403
