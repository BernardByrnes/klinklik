import importlib
import json

import pytest
from rest_framework.test import APIClient

from accounts.bootstrap import open_session
from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from audit.models import AuditEvent
from clinical.allergies import add_allergy as add_allergy_service
from clinical.models import Allergy, ClinicalNote, ClinicalNoteVersion, Encounter, PatientAllergyState
from core.services import tenant_atomic
from patients.models import Patient
from tenancy.models import Facility
from tests.clinical_test_helpers import establish_synthetic_final_diagnosis, establish_synthetic_nka_review

pytestmark = pytest.mark.django_db(transaction=True)

SYNTHETIC_HPI = "Phase 1M-A verification - synthetic HPI"
SYNTHETIC_SUBSTANCE = "Phase 1M-A synthetic Penicillin"
SYNTHETIC_REACTION = "Phase 1M-A synthetic rash"
SYNTHETIC_REASON = "Phase 1M-A synthetic correction reason"


def create_patient(client, label="Phase1MA"):
    response = client.post(
        "/api/v1/patients/",
        {"first_name": label, "last_name": "Synthetic", "sex": "UNKNOWN"},
        format="json",
    )
    assert response.status_code == 201, response.data
    return response.data["id"]


def create_encounter(tenant, client, label="Phase1MA"):
    patient_id = create_patient(client, label)
    return create_encounter_for_patient(tenant, client, patient_id)


def create_encounter_for_patient(tenant, client, patient_id):
    check_in = client.post(
        "/api/v1/clinic/check-ins/",
        {"patient_id": patient_id, "department_id": str(tenant.department.id)},
        format="json",
    )
    assert check_in.status_code == 201, check_in.data
    queue_id = check_in.data["id"]
    assert client.post(f"/api/v1/clinic/queue/{queue_id}/claim/", {}, format="json").status_code == 200
    triage = client.post(
        f"/api/v1/clinic/triage/{queue_id}/",
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1M-A synthetic triage"},
        format="json",
    )
    assert triage.status_code == 201, triage.data
    encounter = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": queue_id},
        format="json",
    )
    assert encounter.status_code == 201, encounter.data
    diagnosis = establish_synthetic_final_diagnosis(client, encounter.data["id"])
    encounter.data["consultation_etag"] = diagnosis["consultation_etag"]
    return encounter.data


def encounter_read(client, encounter_id):
    response = client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert response.status_code == 200, response.data
    return response.data


def allergy_etag(client, encounter_id):
    return encounter_read(client, encounter_id)["allergy_state_etag"]


def add_allergy(client, patient_id, *, substance=SYNTHETIC_SUBSTANCE, reaction=SYNTHETIC_REACTION, severity="MODERATE", facility_id=None):
    headers = {}
    if facility_id is not None:
        headers["HTTP_X_FACILITY_ID"] = str(facility_id)
    return client.post(
        f"/api/v1/clinic/patients/{patient_id}/allergies/",
        {"substance": substance, "reaction": reaction, "severity": severity},
        format="json",
        **headers,
    )


def set_allergy_status(client, patient_id, status, etag):
    return client.post(
        f"/api/v1/clinic/patients/{patient_id}/allergy-status/",
        {"status": status},
        format="json",
        HTTP_IF_MATCH=etag,
    )


def enter_in_error(client, patient_id, allergy_id, reason, etag):
    return client.post(
        f"/api/v1/clinic/patients/{patient_id}/allergies/{allergy_id}/entered-in-error/",
        {"reason": reason},
        format="json",
        HTTP_IF_MATCH=etag,
    )


def review_allergies(client, encounter_id, etag):
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/allergies/review/",
        {},
        format="json",
        HTTP_IF_MATCH=etag,
    )


def save_complaint_note(client, encounter):
    response = client.patch(
        f"/api/v1/clinic/encounters/{encounter['id']}/notes/",
        {"content": {"hpi": SYNTHETIC_HPI}, "complaints": [{
            "text": "Phase 1M-A synthetic presenting complaint",
            "duration_value": None,
            "duration_unit": None,
        }]},
        format="json",
        HTTP_IF_MATCH=encounter["consultation_etag"],
    )
    assert response.status_code == 200, response.data
    return response.data


def sign_note(client, encounter_id, etag):
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"hpi": SYNTHETIC_HPI}},
        format="json",
        HTTP_IF_MATCH=etag,
    )


def test_default_allergy_state_is_not_recorded(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MADefault")
    data = encounter_read(authed_client, encounter["id"])

    assert data["allergy_status"] == "NOT_RECORDED"
    assert data["active_allergies"] == []
    assert data["allergy_revision"] == 0
    assert data["allergies_review_is_current"] is False
    assert not PatientAllergyState.objects.filter(patient_id=encounter["patient"]).exists()


def test_add_allergy_creates_active_recorded_state_and_revision(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MAAdd")
    response = add_allergy(authed_client, encounter["patient"])

    assert response.status_code == 201, response.data
    assert response.data["allergy_status"] == "RECORDED"
    assert response.data["allergy_revision"] == 1
    assert len(response.data["active_allergies"]) == 1
    allergy = Allergy.objects.get(id=response.data["allergy"]["id"])
    assert allergy.status == "ACTIVE"
    assert allergy.recorded_by_id == tenant.user.id
    assert allergy.recorded_at is not None
    assert encounter_read(authed_client, encounter["id"])["active_allergies"][0]["substance"] == SYNTHETIC_SUBSTANCE


def test_explicit_nka_requires_empty_active_state(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MANKA")
    response = set_allergy_status(
        authed_client,
        encounter["patient"],
        "NKA",
        allergy_etag(authed_client, encounter["id"]),
    )

    assert response.status_code == 200, response.data
    assert response.data["allergy_status"] == "NKA"
    assert response.data["allergy_revision"] == 1
    assert encounter_read(authed_client, encounter["id"])["allergy_status"] == "NKA"


def test_explicit_unknown_requires_empty_active_state(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MAUnknown")
    response = set_allergy_status(
        authed_client,
        encounter["patient"],
        "UNKNOWN",
        allergy_etag(authed_client, encounter["id"]),
    )

    assert response.status_code == 200, response.data
    assert response.data["allergy_status"] == "UNKNOWN"
    assert response.data["allergy_revision"] == 1


@pytest.mark.parametrize("requested_status", ["NKA", "UNKNOWN"])
def test_nka_or_unknown_rejects_active_allergies(tenant, authed_client, requested_status):
    encounter = create_encounter(tenant, authed_client, "Phase1MAInvalidStatus")
    added = add_allergy(authed_client, encounter["patient"])
    response = set_allergy_status(
        authed_client,
        encounter["patient"],
        requested_status,
        added.data["allergy_state_etag"],
    )

    assert response.status_code == 400
    assert Allergy.objects.get(id=added.data["allergy"]["id"]).status == "ACTIVE"
    state = PatientAllergyState.objects.get(patient_id=encounter["patient"])
    assert state.status == "RECORDED"
    assert state.revision == 1


def test_entered_in_error_preserves_row_and_hides_it_from_active_state(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MAError")
    added = add_allergy(authed_client, encounter["patient"])
    response = enter_in_error(
        authed_client,
        encounter["patient"],
        added.data["allergy"]["id"],
        SYNTHETIC_REASON,
        added.data["allergy_state_etag"],
    )

    assert response.status_code == 200, response.data
    allergy = Allergy.objects.get(id=added.data["allergy"]["id"])
    assert allergy.status == "ENTERED_IN_ERROR"
    assert allergy.entered_in_error_reason == SYNTHETIC_REASON
    assert allergy.entered_in_error_by_id == tenant.user.id
    assert allergy.entered_in_error_at is not None
    assert response.data["allergy_status"] == "NOT_RECORDED"
    assert response.data["active_allergies"] == []
    assert response.data["allergy_revision"] == 2
    assert "entered_in_error_reason" not in json.dumps(encounter_read(authed_client, encounter["id"]), default=str)


def test_last_entered_in_error_does_not_infer_nka(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MALastError")
    added = add_allergy(authed_client, encounter["patient"])
    response = enter_in_error(
        authed_client,
        encounter["patient"],
        added.data["allergy"]["id"],
        SYNTHETIC_REASON,
        added.data["allergy_state_etag"],
    )

    assert response.status_code == 200
    assert response.data["allergy_status"] == "NOT_RECORDED"
    assert PatientAllergyState.objects.get(patient_id=encounter["patient"]).status == "NOT_RECORDED"


def test_multiple_allergies_keep_recorded_state_after_one_error(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MAMultiple")
    first = add_allergy(authed_client, encounter["patient"], substance="Phase 1M-A synthetic first")
    second = add_allergy(authed_client, encounter["patient"], substance="Phase 1M-A synthetic second")
    response = enter_in_error(
        authed_client,
        encounter["patient"],
        first.data["allergy"]["id"],
        SYNTHETIC_REASON,
        second.data["allergy_state_etag"],
    )

    assert response.status_code == 200
    assert response.data["allergy_status"] == "RECORDED"
    assert len(response.data["active_allergies"]) == 1
    assert response.data["allergy_revision"] == 3


def test_review_nka_records_current_revision_and_is_encounter_specific(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MAReviewNKA")
    status_response = set_allergy_status(
        authed_client,
        encounter["patient"],
        "NKA",
        allergy_etag(authed_client, encounter["id"]),
    )
    reviewed = review_allergies(authed_client, encounter["id"], status_response.data["allergy_state_etag"])

    assert reviewed.status_code == 200, reviewed.data
    assert reviewed.data["allergy_status"] == "NKA"
    assert reviewed.data["allergies_reviewed_revision"] == 1
    assert reviewed.data["allergies_review_is_current"] is True
    data = encounter_read(authed_client, encounter["id"])
    assert data["allergies_reviewed_at"]
    assert data["allergies_reviewed_revision"] == 1
    assert data["allergies_review_is_current"] is True


def test_review_recorded_allergies_records_current_revision(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MAReviewRecorded")
    added = add_allergy(authed_client, encounter["patient"])
    reviewed = review_allergies(authed_client, encounter["id"], added.data["allergy_state_etag"])

    assert reviewed.status_code == 200, reviewed.data
    assert reviewed.data["allergy_status"] == "RECORDED"
    assert reviewed.data["active_allergies"][0]["substance"] == SYNTHETIC_SUBSTANCE
    assert reviewed.data["allergies_reviewed_revision"] == 1


def test_sign_blocks_when_allergy_status_not_recorded_without_version_or_sign_audit(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MASignStatus")
    draft = save_complaint_note(authed_client, encounter)
    before_sign_audits = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        action="SIGN",
    ).count()
    response = sign_note(authed_client, encounter["id"], draft["etag"])

    assert response.status_code == 400
    assert response.data["code"] == "ALLERGY_STATUS_REQUIRED"
    note = ClinicalNote.objects.get(id=draft["note"])
    assert note.status == "DRAFT"
    assert ClinicalNoteVersion.objects.filter(note=note).count() == 0
    assert AuditEvent.objects.filter(organisation=tenant.organisation, facility=tenant.facility, action="SIGN").count() == before_sign_audits


def test_sign_blocks_when_allergy_state_has_not_been_reviewed(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MASignReview")
    status_response = set_allergy_status(
        authed_client,
        encounter["patient"],
        "NKA",
        allergy_etag(authed_client, encounter["id"]),
    )
    draft = save_complaint_note(authed_client, encounter)
    response = sign_note(authed_client, encounter["id"], draft["etag"])

    assert status_response.status_code == 200
    assert response.status_code == 400
    assert response.data["code"] == "ALLERGY_REVIEW_REQUIRED"
    assert ClinicalNoteVersion.objects.filter(note_id=draft["note"]).count() == 0


def test_sign_blocks_when_review_is_stale_after_allergy_mutation(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MASignStale")
    status_response = set_allergy_status(
        authed_client,
        encounter["patient"],
        "NKA",
        allergy_etag(authed_client, encounter["id"]),
    )
    reviewed = review_allergies(authed_client, encounter["id"], status_response.data["allergy_state_etag"])
    draft = save_complaint_note(authed_client, encounter)
    changed = add_allergy(authed_client, encounter["patient"])

    response = sign_note(authed_client, encounter["id"], draft["etag"])

    assert reviewed.status_code == 200
    assert changed.status_code == 201
    assert response.status_code == 400
    assert response.data["code"] == "ALLERGY_REVIEW_STALE"
    assert ClinicalNoteVersion.objects.filter(note_id=draft["note"]).count() == 0


def test_sign_succeeds_with_current_review(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MASignSuccess")
    status_response = set_allergy_status(
        authed_client,
        encounter["patient"],
        "NKA",
        allergy_etag(authed_client, encounter["id"]),
    )
    reviewed = review_allergies(authed_client, encounter["id"], status_response.data["allergy_state_etag"])
    draft = save_complaint_note(authed_client, encounter)
    response = sign_note(authed_client, encounter["id"], draft["etag"])

    assert reviewed.status_code == 200
    assert response.status_code == 200, response.data
    assert response.data["status"] == "SIGNED"
    assert ClinicalNoteVersion.objects.filter(note_id=draft["note"]).count() == 1


def test_patient_allergy_state_persists_to_second_encounter_but_review_does_not(tenant, authed_client):
    first = create_encounter(tenant, authed_client, "Phase1MAPersist")
    status_response = set_allergy_status(
        authed_client,
        first["patient"],
        "UNKNOWN",
        allergy_etag(authed_client, first["id"]),
    )
    reviewed = review_allergies(authed_client, first["id"], status_response.data["allergy_state_etag"])
    second = create_encounter_for_patient(tenant, authed_client, first["patient"])

    assert reviewed.status_code == 200
    second_data = encounter_read(authed_client, second["id"])
    assert second_data["allergy_status"] == "UNKNOWN"
    assert second_data["allergies_reviewed_at"] is None
    assert second_data["allergies_review_is_current"] is False
    first_data = encounter_read(authed_client, first["id"])
    assert first_data["allergies_review_is_current"] is True


def test_active_banner_excludes_entered_in_error_history(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MABanner")
    first = add_allergy(authed_client, encounter["patient"], substance="Phase 1M-A synthetic hidden")
    second = add_allergy(authed_client, encounter["patient"], substance="Phase 1M-A synthetic active")
    entered = enter_in_error(
        authed_client,
        encounter["patient"],
        first.data["allergy"]["id"],
        SYNTHETIC_REASON,
        second.data["allergy_state_etag"],
    )
    data = encounter_read(authed_client, encounter["id"])

    assert entered.status_code == 200
    assert [item["substance"] for item in data["active_allergies"]] == ["Phase 1M-A synthetic active"]
    assert "entered_in_error_reason" not in json.dumps(data, default=str)


def test_stale_allergy_status_mutation_returns_412_without_overwrite(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MAStale")
    initial_etag = allergy_etag(authed_client, encounter["id"])
    first = set_allergy_status(authed_client, encounter["patient"], "NKA", initial_etag)
    stale = set_allergy_status(authed_client, encounter["patient"], "UNKNOWN", initial_etag)

    assert first.status_code == 200
    assert stale.status_code == 412
    assert stale.data["code"] == "ALLERGY_STATE_REVISION_CONFLICT"
    assert stale.data["allergy_status"] == "NKA"
    assert PatientAllergyState.objects.get(patient_id=encounter["patient"]).status == "NKA"


def test_allergy_mutation_capability_excludes_reception(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MAPermission")
    reception = User.objects.create_user("phase1ma-reception")
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

    response = add_allergy(reception_client, encounter["patient"])
    assert response.status_code == 403


def test_cross_facility_allergy_record_is_not_mutable_from_other_facility(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MAScope")
    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="Other Facility",
            code="OTHER",
            mode="CLINIC",
        )
        allergy = Allergy.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            patient_id=encounter["patient"],
            substance="Phase 1M-A other facility synthetic allergy",
            reaction="Phase 1M-A other facility reaction",
            severity="MILD",
            status="ACTIVE",
            recorded_by=tenant.user,
        )
    response = enter_in_error(
        authed_client,
        encounter["patient"],
        allergy.id,
        "Phase 1M-A cross facility reason",
        "not-the-other-facility-etag",
    )
    assert response.status_code == 404


def test_audit_records_safe_allergy_metadata_without_raw_clinical_values(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MAAudit")
    added = add_allergy(authed_client, encounter["patient"])
    entered = enter_in_error(
        authed_client,
        encounter["patient"],
        added.data["allergy"]["id"],
        SYNTHETIC_REASON,
        added.data["allergy_state_etag"],
    )
    events = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        entity_type__in=["Allergy", "PatientAllergyState"],
    )
    audit_json = json.dumps(
        [{"before": event.before, "after": event.after, "reason": event.reason} for event in events],
        default=str,
    )
    assert entered.status_code == 200
    assert SYNTHETIC_SUBSTANCE not in audit_json
    assert SYNTHETIC_REACTION not in audit_json
    assert "MODERATE" not in audit_json
    assert SYNTHETIC_REASON not in audit_json
    assert "reason_recorded" in audit_json


def test_migration_reconciles_active_allergy_only(tenant, authed_client):
    patient_id = create_patient(authed_client, "Phase1MAMigrationActive")
    blank_patient_id = create_patient(authed_client, "Phase1MAMigrationBlank")
    active_patient = Patient.objects.get(id=patient_id)
    Allergy.objects.create(
        organisation=tenant.organisation,
        facility=tenant.facility,
        patient=active_patient,
        substance="Phase 1M-A migration synthetic allergy",
        reaction="Phase 1M-A migration synthetic reaction",
        severity="SEVERE",
        status="ACTIVE",
        recorded_by=tenant.user,
    )
    migration = importlib.import_module("clinical.migrations.0005_allergy_entered_in_error_at_and_more")

    class MigrationApps:
        def get_model(self, app_label, model_name):
            assert app_label == "clinical"
            return {
                "Allergy": Allergy,
                "PatientAllergyState": PatientAllergyState,
            }[model_name]

    migration.reconcile_existing_active_allergies(MigrationApps(), None)

    state = PatientAllergyState.objects.get(patient_id=patient_id)
    assert state.status == "RECORDED"
    assert state.revision == 1
    assert not PatientAllergyState.objects.filter(patient_id=blank_patient_id).exists()
    assert Allergy.objects.get(patient_id=patient_id).substance == "Phase 1M-A migration synthetic allergy"


def test_service_add_allergy_updates_state_and_returns_revision(tenant, authed_client):
    patient_id = create_patient(authed_client, "Phase1MAService")
    patient = Patient.objects.get(id=patient_id)

    allergy, snapshot = add_allergy_service(
        organisation=tenant.organisation,
        facility=tenant.facility,
        patient=patient,
        actor=tenant.user,
        substance="Phase 1M-A service synthetic substance",
        reaction="Phase 1M-A service synthetic reaction",
        severity="MILD",
    )

    state = PatientAllergyState.objects.get(patient=patient)
    assert allergy.status == "ACTIVE"
    assert state.status == "RECORDED"
    assert state.revision == 1
    assert snapshot["revision"] == 1
    assert snapshot["active_allergies"][0]["id"] == str(allergy.id)


def test_signed_encounter_cannot_be_re_reviewed_but_patient_state_may_change(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1MASignedReview")
    establish_synthetic_nka_review(authed_client, encounter["id"])
    draft = save_complaint_note(authed_client, encounter)
    signed = sign_note(authed_client, encounter["id"], draft["etag"])
    assert signed.status_code == 200

    signed_data = encounter_read(authed_client, encounter["id"])
    review_again = review_allergies(authed_client, encounter["id"], signed_data["allergy_state_etag"])
    changed = add_allergy(authed_client, encounter["patient"], substance="Phase 1M-A post-sign synthetic allergy")

    assert review_again.status_code == 400
    assert changed.status_code == 201
    assert encounter_read(authed_client, encounter["id"])["allergy_status"] == "RECORDED"
