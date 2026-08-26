import importlib
import json

import pytest
from rest_framework.test import APIClient

from accounts.bootstrap import open_session
from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from audit.models import AuditEvent
from clinical.models import ClinicalNote, ClinicalNoteVersion, Diagnosis, Encounter
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import QueueEntry
from tenancy.models import Facility
from tests.clinical_test_helpers import establish_synthetic_disposition, establish_synthetic_nka_review


pytestmark = pytest.mark.django_db(transaction=True)

SYNTHETIC_LABEL = "Phase 1N-A synthetic diagnosis label"
SYNTHETIC_CODE = "DX-1NA"
SYNTHETIC_CERTAINTY = "Phase 1N-A synthetic certainty note"
SYNTHETIC_REASON = "Phase 1N-A synthetic no-diagnosis reason"
SYNTHETIC_COMPLAINT = {
    "text": "Phase 1N-A synthetic presenting complaint",
    "duration_value": None,
    "duration_unit": None,
}


def create_encounter(tenant, client, label="Phase1NA"):
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
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1N-A synthetic triage"},
        format="json",
    )
    assert triage.status_code == 201, triage.data
    encounter = client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": queue_id},
        format="json",
    )
    assert encounter.status_code == 201, encounter.data
    disposition = establish_synthetic_disposition(client, encounter.data["id"])
    encounter.data["consultation_etag"] = disposition["consultation_etag"]
    return encounter.data


def read_encounter(client, encounter_id):
    response = client.get(f"/api/v1/clinic/encounters/{encounter_id}/")
    assert response.status_code == 200, response.data
    return response.data


def diagnosis_url(encounter_id):
    return f"/api/v1/clinic/encounters/{encounter_id}/diagnoses/"


def add_diagnosis(client, encounter, payload, etag=None):
    request_etag = etag
    if request_etag is None:
        request_etag = read_encounter(client, encounter["id"])["consultation_etag"]
    response = client.post(
        diagnosis_url(encounter["id"]),
        payload,
        format="json",
        HTTP_IF_MATCH=request_etag,
    )
    return response


def add_final(client, encounter, *, label=SYNTHETIC_LABEL, code=SYNTHETIC_CODE, primary=True, etag=None):
    return add_diagnosis(
        client,
        encounter,
        {
            "diagnosis_type": "FINAL",
            "label": label,
            "code": code,
            "certainty_note": SYNTHETIC_CERTAINTY,
            "is_primary": primary,
        },
        etag=etag,
    )


def sign_with_complaint(client, encounter, etag):
    return client.post(
        f"/api/v1/clinic/encounters/{encounter['id']}/sign/",
        {"content": {"hpi": "Phase 1N-A synthetic sign note"}, "complaints": [SYNTHETIC_COMPLAINT]},
        format="json",
        HTTP_IF_MATCH=etag,
    )


def review_allergies(client, encounter):
    return establish_synthetic_nka_review(client, encounter["id"])


def test_existing_diagnosis_model_exposes_typed_active_snapshot_and_etag(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1NATyped")
    working = add_diagnosis(
        authed_client,
        encounter,
        {
            "diagnosis_type": "WORKING",
            "label": SYNTHETIC_LABEL,
            "certainty_note": SYNTHETIC_CERTAINTY,
        },
    )
    assert working.status_code == 201, working.data
    assert len(working.data["diagnoses"]) == 1
    assert working.data["diagnoses"][0]["diagnosis_type"] == "WORKING"
    assert working.data["diagnoses"][0]["coded"] is False
    assert working.data["diagnoses"][0]["is_primary"] is False

    final = add_final(authed_client, encounter, etag=working.data["consultation_etag"])
    assert final.status_code == 201, final.data
    assert [item["diagnosis_type"] for item in final.data["diagnoses"]] == ["WORKING", "FINAL"]
    assert final.data["diagnoses"][1]["coded"] is True
    encounter_data = read_encounter(authed_client, encounter["id"])
    assert len(encounter_data["diagnoses"]) == 2
    assert encounter_data["consultation_etag"] == final.data["consultation_etag"]
    assert final["ETag"] == final.data["consultation_etag"]


def test_diagnosis_validation_enforces_labels_no_diagnosis_reason_and_state(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1NAValidation")
    blank_working = add_diagnosis(
        authed_client,
        encounter,
        {"diagnosis_type": "WORKING", "label": "   "},
    )
    assert blank_working.status_code == 400
    assert blank_working.data["code"] == "DIAGNOSIS_LABEL_REQUIRED"

    bad_no_diagnosis = add_diagnosis(
        authed_client,
        encounter,
        {"diagnosis_type": "NO_DIAGNOSIS", "no_diagnosis_reason": "  "},
    )
    assert bad_no_diagnosis.status_code == 400
    assert bad_no_diagnosis.data["code"] == "NO_DIAGNOSIS_REASON_REQUIRED"

    no_diagnosis = add_diagnosis(
        authed_client,
        encounter,
        {"diagnosis_type": "NO_DIAGNOSIS", "no_diagnosis_reason": SYNTHETIC_REASON},
    )
    assert no_diagnosis.status_code == 201, no_diagnosis.data
    assert no_diagnosis.data["diagnoses"][0]["code"] == ""
    assert no_diagnosis.data["diagnoses"][0]["coded"] is False
    assert no_diagnosis.data["diagnoses"][0]["label"] == ""
    assert no_diagnosis.data["diagnoses"][0]["certainty_note"] == ""
    assert no_diagnosis.data["diagnoses"][0]["is_primary"] is False

    conflicting_final = add_final(authed_client, encounter, etag=no_diagnosis.data["consultation_etag"])
    assert conflicting_final.status_code == 400
    assert conflicting_final.data["code"] == "DIAGNOSIS_STATE_INVALID"



def test_working_and_no_diagnosis_can_coexist_in_either_creation_order(tenant, authed_client):
    working_first = create_encounter(tenant, authed_client, "Phase1NAWorkingFirst")
    working = add_diagnosis(
        authed_client,
        working_first,
        {"diagnosis_type": "WORKING", "label": "Phase 1N-A working-first"},
    )
    no_diagnosis = add_diagnosis(
        authed_client,
        working_first,
        {"diagnosis_type": "NO_DIAGNOSIS", "no_diagnosis_reason": SYNTHETIC_REASON},
        etag=working.data["consultation_etag"],
    )
    assert working.status_code == 201, working.data
    assert no_diagnosis.status_code == 201, no_diagnosis.data
    assert {item["diagnosis_type"] for item in no_diagnosis.data["diagnoses"]} == {
        "WORKING",
        "NO_DIAGNOSIS",
    }

    no_diagnosis_first = create_encounter(tenant, authed_client, "Phase1NANoDiagnosisFirst")
    no_diagnosis = add_diagnosis(
        authed_client,
        no_diagnosis_first,
        {"diagnosis_type": "NO_DIAGNOSIS", "no_diagnosis_reason": SYNTHETIC_REASON},
    )
    working = add_diagnosis(
        authed_client,
        no_diagnosis_first,
        {"diagnosis_type": "WORKING", "label": "Phase 1N-A no-diagnosis-first"},
        etag=no_diagnosis.data["consultation_etag"],
    )
    assert no_diagnosis.status_code == 201, no_diagnosis.data
    assert working.status_code == 201, working.data
    assert {item["diagnosis_type"] for item in working.data["diagnoses"]} == {
        "WORKING",
        "NO_DIAGNOSIS",
    }

    multiple_working = create_encounter(tenant, authed_client, "Phase1NAMultipleWorking")
    working_a = add_diagnosis(
        authed_client,
        multiple_working,
        {"diagnosis_type": "WORKING", "label": "Phase 1N-A working A"},
    )
    working_b = add_diagnosis(
        authed_client,
        multiple_working,
        {"diagnosis_type": "WORKING", "label": "Phase 1N-A working B"},
        etag=working_a.data["consultation_etag"],
    )
    no_diagnosis = add_diagnosis(
        authed_client,
        multiple_working,
        {"diagnosis_type": "NO_DIAGNOSIS", "no_diagnosis_reason": SYNTHETIC_REASON},
        etag=working_b.data["consultation_etag"],
    )
    assert working_a.status_code == 201, working_a.data
    assert working_b.status_code == 201, working_b.data
    assert no_diagnosis.status_code == 201, no_diagnosis.data
    types = [item["diagnosis_type"] for item in no_diagnosis.data["diagnoses"]]
    assert types.count("WORKING") == 2
    assert types.count("NO_DIAGNOSIS") == 1


def test_diagnosis_type_transitions_preserve_symmetric_exclusivity(tenant, authed_client):
    working_transition = create_encounter(tenant, authed_client, "Phase1NATransitions")
    working_a = add_diagnosis(
        authed_client,
        working_transition,
        {"diagnosis_type": "WORKING", "label": "Phase 1N-A transition A"},
    )
    working_b = add_diagnosis(
        authed_client,
        working_transition,
        {"diagnosis_type": "WORKING", "label": "Phase 1N-A transition B"},
        etag=working_a.data["consultation_etag"],
    )
    working_a_id = working_a.data["diagnoses"][0]["id"]
    to_no_diagnosis = authed_client.patch(
        f"{diagnosis_url(working_transition['id'])}{working_a_id}/",
        {"diagnosis_type": "NO_DIAGNOSIS", "no_diagnosis_reason": SYNTHETIC_REASON},
        format="json",
        HTTP_IF_MATCH=working_b.data["consultation_etag"],
    )
    assert to_no_diagnosis.status_code == 200, to_no_diagnosis.data
    assert {item["diagnosis_type"] for item in to_no_diagnosis.data["diagnoses"]} == {
        "WORKING",
        "NO_DIAGNOSIS",
    }

    back_to_working = authed_client.patch(
        f"{diagnosis_url(working_transition['id'])}{working_a_id}/",
        {"diagnosis_type": "WORKING", "label": "Phase 1N-A transition A revised"},
        format="json",
        HTTP_IF_MATCH=to_no_diagnosis.data["consultation_etag"],
    )
    assert back_to_working.status_code == 200, back_to_working.data
    assert [item["diagnosis_type"] for item in back_to_working.data["diagnoses"]] == [
        "WORKING",
        "WORKING",
    ]

    blocked_final = create_encounter(tenant, authed_client, "Phase1NAWorkingFinalBlocked")
    no_diagnosis = add_diagnosis(
        authed_client,
        blocked_final,
        {"diagnosis_type": "NO_DIAGNOSIS", "no_diagnosis_reason": SYNTHETIC_REASON},
    )
    working = add_diagnosis(
        authed_client,
        blocked_final,
        {"diagnosis_type": "WORKING", "label": "Phase 1N-A final transition blocked"},
        etag=no_diagnosis.data["consultation_etag"],
    )
    working_id = next(item["id"] for item in working.data["diagnoses"] if item["diagnosis_type"] == "WORKING")
    to_final = authed_client.patch(
        f"{diagnosis_url(blocked_final['id'])}{working_id}/",
        {
            "diagnosis_type": "FINAL",
            "label": "Phase 1N-A blocked final",
            "code": SYNTHETIC_CODE,
            "is_primary": True,
        },
        format="json",
        HTTP_IF_MATCH=working.data["consultation_etag"],
    )
    assert to_final.status_code == 400, to_final.data
    assert to_final.data["code"] == "DIAGNOSIS_STATE_INVALID"
    unchanged = read_encounter(authed_client, blocked_final["id"])
    assert {item["diagnosis_type"] for item in unchanged["diagnoses"]} == {"WORKING", "NO_DIAGNOSIS"}

    no_to_final = create_encounter(tenant, authed_client, "Phase1NANoDiagnosisPromotion")
    no_diagnosis = add_diagnosis(
        authed_client,
        no_to_final,
        {"diagnosis_type": "NO_DIAGNOSIS", "no_diagnosis_reason": SYNTHETIC_REASON},
    )
    promoted = authed_client.patch(
        f"{diagnosis_url(no_to_final['id'])}{no_diagnosis.data['diagnoses'][0]['id']}/",
        {
            "diagnosis_type": "FINAL",
            "label": "Phase 1N-A promoted final",
            "code": SYNTHETIC_CODE,
            "is_primary": True,
        },
        format="json",
        HTTP_IF_MATCH=no_diagnosis.data["consultation_etag"],
    )
    assert promoted.status_code == 200, promoted.data
    assert promoted.data["diagnoses"][0]["diagnosis_type"] == "FINAL"

    final_transition = create_encounter(tenant, authed_client, "Phase1NAFinalToNoBlocked")
    first_final = add_final(authed_client, final_transition)
    second_final = add_final(
        authed_client,
        final_transition,
        label="Phase 1N-A second final transition",
        code="DX-1NA-SECOND",
        primary=False,
        etag=first_final.data["consultation_etag"],
    )
    first_final_id = first_final.data["diagnoses"][0]["id"]
    final_to_no = authed_client.patch(
        f"{diagnosis_url(final_transition['id'])}{first_final_id}/",
        {"diagnosis_type": "NO_DIAGNOSIS", "no_diagnosis_reason": SYNTHETIC_REASON},
        format="json",
        HTTP_IF_MATCH=second_final.data["consultation_etag"],
    )
    assert final_to_no.status_code == 400, final_to_no.data
    assert final_to_no.data["code"] == "DIAGNOSIS_STATE_INVALID"


def test_sign_succeeds_with_working_and_no_diagnosis(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1NAWorkingNoDiagnosisSign")
    no_diagnosis = add_diagnosis(
        authed_client,
        encounter,
        {"diagnosis_type": "NO_DIAGNOSIS", "no_diagnosis_reason": SYNTHETIC_REASON},
    )
    working = add_diagnosis(
        authed_client,
        encounter,
        {"diagnosis_type": "WORKING", "label": "Phase 1N-A provisional working diagnosis"},
        etag=no_diagnosis.data["consultation_etag"],
    )
    review = review_allergies(authed_client, encounter)
    signed = sign_with_complaint(authed_client, encounter, working.data["consultation_etag"])
    assert no_diagnosis.status_code == 201, no_diagnosis.data
    assert working.status_code == 201, working.data
    assert review["allergies_review_is_current"] is True
    assert signed.status_code == 200, signed.data
    assert signed.data["status"] == "SIGNED"
    assert Encounter.objects.get(id=encounter["id"]).status == "SIGNED"
    assert ClinicalNoteVersion.objects.filter(note__encounter_id=encounter["id"]).count() == 1

def test_primary_final_is_unique_and_working_cannot_be_primary(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1NAPrimary")
    working_primary = add_diagnosis(
        authed_client,
        encounter,
        {"diagnosis_type": "WORKING", "label": SYNTHETIC_LABEL, "is_primary": True},
    )
    assert working_primary.status_code == 400
    assert working_primary.data["code"] == "PRIMARY_DIAGNOSIS_INVALID"

    first = add_final(authed_client, encounter)
    assert first.status_code == 201, first.data
    second_primary = add_final(
        authed_client,
        encounter,
        label="Phase 1N-A second synthetic final",
        code="DX-1NA-2",
        etag=first.data["consultation_etag"],
    )
    assert second_primary.status_code == 400
    assert second_primary.data["code"] == "PRIMARY_DIAGNOSIS_INVALID"
    second = add_final(
        authed_client,
        encounter,
        label="Phase 1N-A second synthetic final",
        code="DX-1NA-2",
        primary=False,
        etag=first.data["consultation_etag"],
    )
    assert second.status_code == 201, second.data
    assert len([item for item in second.data["diagnoses"] if item["is_primary"]]) == 1


def test_diagnosis_patch_recomputes_coded_and_preserves_snapshot_values(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1NAPatch")
    created = add_final(authed_client, encounter)
    diagnosis_id = created.data["diagnoses"][0]["id"]
    patched = authed_client.patch(
        f"{diagnosis_url(encounter['id'])}{diagnosis_id}/",
        {"code": "", "certainty_note": "Phase 1N-A updated certainty"},
        format="json",
        HTTP_IF_MATCH=created.data["consultation_etag"],
    )
    assert patched.status_code == 200, patched.data
    updated = patched.data["diagnoses"][0]
    assert updated["code"] == ""
    assert updated["coded"] is False
    assert updated["label"] == SYNTHETIC_LABEL
    assert updated["certainty_note"] == "Phase 1N-A updated certainty"

    working = authed_client.patch(
        f"{diagnosis_url(encounter['id'])}{diagnosis_id}/",
        {"diagnosis_type": "WORKING"},
        format="json",
        HTTP_IF_MATCH=patched.data["consultation_etag"],
    )
    assert working.status_code == 200, working.data
    assert working.data["diagnoses"][0]["diagnosis_type"] == "WORKING"
    assert working.data["diagnoses"][0]["is_primary"] is False

    no_diagnosis = authed_client.patch(
        f"{diagnosis_url(encounter['id'])}{diagnosis_id}/",
        {"diagnosis_type": "NO_DIAGNOSIS", "no_diagnosis_reason": SYNTHETIC_REASON},
        format="json",
        HTTP_IF_MATCH=working.data["consultation_etag"],
    )
    assert no_diagnosis.status_code == 200, no_diagnosis.data
    transitioned = no_diagnosis.data["diagnoses"][0]
    assert transitioned["diagnosis_type"] == "NO_DIAGNOSIS"
    assert transitioned["label"] == ""
    assert transitioned["code"] == ""
    assert transitioned["certainty_note"] == ""
    assert transitioned["coded"] is False
    assert transitioned["is_primary"] is False


def test_soft_remove_hides_active_diagnosis_and_records_actor_time(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1NARemove")
    created = add_final(authed_client, encounter)
    diagnosis_id = created.data["diagnoses"][0]["id"]
    removed = authed_client.post(
        f"{diagnosis_url(encounter['id'])}{diagnosis_id}/remove/",
        {},
        format="json",
        HTTP_IF_MATCH=created.data["consultation_etag"],
    )
    assert removed.status_code == 200, removed.data
    assert removed.data["diagnoses"] == []
    diagnosis = Diagnosis.objects.get(id=diagnosis_id)
    assert diagnosis.status == "REMOVED"
    assert diagnosis.removed_by_id == tenant.user.id
    assert diagnosis.removed_at is not None
    assert diagnosis.label == SYNTHETIC_LABEL
    assert diagnosis.code == SYNTHETIC_CODE
    listed = authed_client.get(diagnosis_url(encounter["id"]))
    assert listed.status_code == 200
    assert listed.data["diagnoses"] == []


def test_diagnosis_mutations_and_note_conflicts_are_etag_protected(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1NAEtags")
    initial = read_encounter(authed_client, encounter["id"])
    created = add_final(authed_client, encounter, etag=initial["consultation_etag"])
    stale = add_diagnosis(
        authed_client,
        encounter,
        {"diagnosis_type": "WORKING", "label": "Phase 1N-A stale working"},
        etag=initial["consultation_etag"],
    )
    assert stale.status_code == 412, stale.data
    assert stale.data["code"] == "DIAGNOSIS_REVISION_CONFLICT"
    assert stale.data["diagnoses"] == created.data["diagnoses"]
    assert stale.data["consultation_etag"] == created.data["consultation_etag"]
    assert stale["ETag"] == stale.data["consultation_etag"]

    note = authed_client.patch(
        f"/api/v1/clinic/encounters/{encounter['id']}/notes/",
        {"content": {"hpi": "Phase 1N-A synthetic note"}, "complaints": [SYNTHETIC_COMPLAINT]},
        format="json",
        HTTP_IF_MATCH=created.data["consultation_etag"],
    )
    assert note.status_code == 200, note.data
    changed = add_diagnosis(
        authed_client,
        encounter,
        {"diagnosis_type": "WORKING", "label": "Phase 1N-A second working"},
        etag=note.data["etag"],
    )
    assert changed.status_code == 201, changed.data
    stale_note = authed_client.patch(
        f"/api/v1/clinic/encounters/{encounter['id']}/notes/",
        {"content": {"assessment": "Phase 1N-A stale note"}},
        format="json",
        HTTP_IF_MATCH=note.data["etag"],
    )
    assert stale_note.status_code == 412, stale_note.data
    assert {
        "code", "detail", "etag", "status", "encounter_status", "content", "complaints", "diagnoses", "saved_at"
    }.issubset(stale_note.data)
    assert stale_note.data["diagnoses"] == changed.data["diagnoses"]


def test_sign_requires_final_primary_or_no_diagnosis_and_preserves_failure_state(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1NASignRequired")
    review = review_allergies(authed_client, encounter)
    sign = sign_with_complaint(authed_client, encounter, read_encounter(authed_client, encounter["id"])["consultation_etag"])
    assert review["allergies_review_is_current"] is True
    assert sign.status_code == 400
    assert sign.data["code"] == "DIAGNOSIS_REQUIRED"
    assert Encounter.objects.get(id=encounter["id"]).status == "OPEN"
    assert all(note.status == "DRAFT" for note in ClinicalNote.objects.filter(encounter_id=encounter["id"]))
    assert not ClinicalNoteVersion.objects.filter(note__encounter_id=encounter["id"]).exists()
    assert not AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        action="SIGN",
        entity_type="ClinicalNote",
    ).filter(entity_id__in=list(ClinicalNote.objects.filter(encounter_id=encounter["id"]).values_list("id", flat=True))).exists()


def test_working_only_and_zero_primary_final_are_blocked(tenant, authed_client):
    working_encounter = create_encounter(tenant, authed_client, "Phase1NAWorkingSign")
    working = add_diagnosis(
        authed_client,
        working_encounter,
        {"diagnosis_type": "WORKING", "label": SYNTHETIC_LABEL},
    )
    review_allergies(authed_client, working_encounter)
    working_sign = sign_with_complaint(authed_client, working_encounter, working.data["consultation_etag"])
    assert working_sign.status_code == 400
    assert working_sign.data["code"] == "DIAGNOSIS_REQUIRED"

    final_encounter = create_encounter(tenant, authed_client, "Phase1NAZeroPrimary")
    final = add_final(authed_client, final_encounter, primary=False)
    review_allergies(authed_client, final_encounter)
    final_sign = sign_with_complaint(authed_client, final_encounter, final.data["consultation_etag"])
    assert final_sign.status_code == 400
    assert final_sign.data["code"] == "PRIMARY_DIAGNOSIS_REQUIRED"
    assert ClinicalNoteVersion.objects.filter(note__encounter_id=final_encounter["id"]).count() == 0


def test_sign_succeeds_with_primary_final_or_no_diagnosis(tenant, authed_client):
    final_encounter = create_encounter(tenant, authed_client, "Phase1NAFinalSign")
    final = add_final(authed_client, final_encounter)
    review_allergies(authed_client, final_encounter)
    signed = sign_with_complaint(authed_client, final_encounter, final.data["consultation_etag"])
    assert signed.status_code == 200, signed.data
    assert signed.data["status"] == "SIGNED"
    assert ClinicalNoteVersion.objects.filter(note__encounter_id=final_encounter["id"]).count() == 1

    no_diagnosis_encounter = create_encounter(tenant, authed_client, "Phase1NANoDiagnosisSign")
    no_diagnosis = add_diagnosis(
        authed_client,
        no_diagnosis_encounter,
        {"diagnosis_type": "NO_DIAGNOSIS", "no_diagnosis_reason": SYNTHETIC_REASON},
    )
    review_allergies(authed_client, no_diagnosis_encounter)
    signed_no_diagnosis = sign_with_complaint(
        authed_client,
        no_diagnosis_encounter,
        no_diagnosis.data["consultation_etag"],
    )
    assert signed_no_diagnosis.status_code == 200, signed_no_diagnosis.data
    assert ClinicalNoteVersion.objects.filter(note__encounter_id=no_diagnosis_encounter["id"]).count() == 1


def test_signed_encounter_rejects_diagnosis_patch_and_remove(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1NASignedMutation")
    created = add_final(authed_client, encounter)
    review_allergies(authed_client, encounter)
    signed = sign_with_complaint(authed_client, encounter, created.data["consultation_etag"])
    assert signed.status_code == 200, signed.data
    diagnosis_id = created.data["diagnoses"][0]["id"]
    patch = authed_client.patch(
        f"{diagnosis_url(encounter['id'])}{diagnosis_id}/",
        {"label": "Phase 1N-A forbidden signed edit"},
        format="json",
        HTTP_IF_MATCH=signed.data["etag"],
    )
    remove = authed_client.post(
        f"{diagnosis_url(encounter['id'])}{diagnosis_id}/remove/",
        {},
        format="json",
        HTTP_IF_MATCH=signed.data["etag"],
    )
    assert patch.status_code == 400
    assert patch.data["code"] == "DIAGNOSIS_IMMUTABLE"
    assert remove.status_code == 400
    assert remove.data["code"] == "DIAGNOSIS_IMMUTABLE"
    assert Diagnosis.objects.get(id=diagnosis_id).status == "ACTIVE"


def test_diagnosis_mutation_requires_clinical_capability(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1NAPermission")
    reception = User.objects.create_user("phase1na-reception")
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
    response = add_diagnosis(
        reception_client,
        encounter,
        {"diagnosis_type": "FINAL", "label": SYNTHETIC_LABEL, "is_primary": True},
        etag=read_encounter(authed_client, encounter["id"])["consultation_etag"],
    )
    assert response.status_code == 403


def test_cross_facility_diagnoses_are_not_visible_or_mutable(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1NAScope")
    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="Phase 1N-A Other Facility",
            code="PHASE1NA-OTHER",
            mode="CLINIC",
        )
        patient = Patient.objects.get(id=encounter["patient"])
        other_encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            patient=patient,
            encounter_no="PHASE1NA-OTHER-ENC",
            clinician=tenant.user,
        )
        Diagnosis.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            encounter=other_encounter,
            diagnosis_type="FINAL",
            code=SYNTHETIC_CODE,
            coded=True,
            label=SYNTHETIC_LABEL,
            is_primary=True,
            recorded_by=tenant.user,
        )
    assert authed_client.get(diagnosis_url(str(other_encounter.id))).status_code == 404
    assert authed_client.post(
        diagnosis_url(str(other_encounter.id)),
        {"diagnosis_type": "FINAL", "label": "Phase 1N-A cross-facility"},
        format="json",
        HTTP_IF_MATCH="not-visible",
    ).status_code == 404


def test_diagnosis_audit_metadata_excludes_raw_clinical_values(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, "Phase1NAAudit")
    created = add_diagnosis(
        authed_client,
        encounter,
        {
            "diagnosis_type": "FINAL",
            "label": SYNTHETIC_LABEL,
            "code": SYNTHETIC_CODE,
            "certainty_note": SYNTHETIC_CERTAINTY,
            "is_primary": True,
        },
    )
    diagnosis_id = created.data["diagnoses"][0]["id"]
    patched = authed_client.patch(
        f"{diagnosis_url(encounter['id'])}{diagnosis_id}/",
        {"certainty_note": "Phase 1N-A second synthetic certainty"},
        format="json",
        HTTP_IF_MATCH=created.data["consultation_etag"],
    )
    removed = authed_client.post(
        f"{diagnosis_url(encounter['id'])}{diagnosis_id}/remove/",
        {},
        format="json",
        HTTP_IF_MATCH=patched.data["consultation_etag"],
    )
    events = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        entity_type="Diagnosis",
        entity_id=diagnosis_id,
    )
    audit_json = json.dumps(
        [{"before": event.before, "after": event.after, "reason": event.reason} for event in events],
        default=str,
    )
    assert created.status_code == 201
    assert patched.status_code == 200
    assert removed.status_code == 200
    assert SYNTHETIC_LABEL not in audit_json
    assert SYNTHETIC_CODE not in audit_json
    assert SYNTHETIC_CERTAINTY not in audit_json
    assert SYNTHETIC_REASON not in audit_json
    assert "diagnosis_type" in audit_json
    assert "is_primary" in audit_json


def test_legacy_diagnosis_migration_preserves_text_and_assigns_one_primary(tenant):
    patient = Patient.objects.create(
        organisation=tenant.organisation,
        first_name="Phase1NA",
        last_name="MigrationSynthetic",
        sex="UNKNOWN",
    )
    encounter = Encounter.objects.create(
        organisation=tenant.organisation,
        facility=tenant.facility,
        patient=patient,
        encounter_no="PHASE1NA-MIGRATION",
        clinician=tenant.user,
    )
    first = Diagnosis.objects.create(
        organisation=tenant.organisation,
        facility=tenant.facility,
        encounter=encounter,
        code=SYNTHETIC_CODE,
        label=SYNTHETIC_LABEL,
        status="ACTIVE",
        recorded_by=tenant.user,
    )
    second = Diagnosis.objects.create(
        organisation=tenant.organisation,
        facility=tenant.facility,
        encounter=encounter,
        code="",
        label="Phase 1N-A legacy free text",
        status="ACTIVE",
        recorded_by=tenant.user,
    )
    migration = importlib.import_module("clinical.migrations.0006_diagnosis_certainty_note_diagnosis_coded_and_more")

    class MigrationApps:
        def get_model(self, app_label, model_name):
            assert app_label == "clinical"
            assert model_name == "Diagnosis"
            return Diagnosis

    migration.migrate_legacy_diagnoses(MigrationApps(), None)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.label == SYNTHETIC_LABEL
    assert first.code == SYNTHETIC_CODE
    assert first.diagnosis_type == "FINAL"
    assert first.coded is True
    assert first.is_primary is True
    assert second.label == "Phase 1N-A legacy free text"
    assert second.code == ""
    assert second.diagnosis_type == "FINAL"
    assert second.coded is False
    assert second.is_primary is False
