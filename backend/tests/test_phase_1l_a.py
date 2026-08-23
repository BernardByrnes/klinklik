import importlib
import json

import pytest

from audit.models import AuditEvent
from clinical.models import ClinicalNote, ClinicalNoteVersion, Encounter
from tests.clinical_test_helpers import establish_synthetic_final_diagnosis, establish_synthetic_nka_review

pytestmark = pytest.mark.django_db

SYNTHETIC_TRIAGE = "Phase 1L-A verification - synthetic triage complaint"
SYNTHETIC_HPI = "Phase 1L-A verification - synthetic HPI"
SYNTHETIC_COMPLAINT = "Phase 1L-A verification - synthetic headache"
SYNTHETIC_COMPLAINT_2 = "Phase 1L-A verification - synthetic fever"
_MISSING = object()


def create_encounter(tenant, client, label="Phase1LA"):
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
        {"acuity": "ROUTINE", "chief_complaint": SYNTHETIC_TRIAGE},
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
    diagnosis = establish_synthetic_final_diagnosis(client, encounter.data["id"])
    encounter.data["consultation_etag"] = diagnosis["consultation_etag"]
    return encounter.data


def patch_note(client, encounter_id, content=None, etag=None, complaints=_MISSING, *, autosave=False):
    payload = {"content": content or {}}
    if complaints is not _MISSING:
        payload["complaints"] = complaints
    headers = {}
    if etag is not None:
        headers["HTTP_IF_MATCH"] = etag
    if autosave:
        headers["HTTP_X_KLINKLIK_AUTOSAVE"] = "1"
    return client.patch(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        payload,
        **headers,
        format="json",
    )


def post_note(client, encounter_id, content=None, etag=None, complaints=_MISSING):
    payload = {"content": content or {}}
    if complaints is not _MISSING:
        payload["complaints"] = complaints
    headers = {}
    if etag is not None:
        headers["HTTP_IF_MATCH"] = etag
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        payload,
        **headers,
        format="json",
    )


def sign_note(client, encounter_id, content=None, etag=None, complaints=_MISSING):
    payload = {"content": content or {}}
    if complaints is not _MISSING:
        payload["complaints"] = complaints
    return client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        payload,
        HTTP_IF_MATCH=etag,
        format="json",
    )


def complaint(text, value=None, unit=None):
    return {"text": text, "duration_value": value, "duration_unit": unit}


def test_phase_1l_a_structured_save_preserves_order_response_and_etag(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client)
    complaints = [
        complaint(SYNTHETIC_COMPLAINT, 2, "DAYS"),
        complaint(SYNTHETIC_COMPLAINT_2),
    ]

    response = patch_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
        complaints,
    )

    assert response.status_code == 200
    assert response.data["complaints"] == complaints
    assert Encounter.objects.get(id=encounter["id"]).complaints == complaints
    assert response.data["etag"] != encounter["consultation_etag"]
    assert response["ETag"] == response.data["etag"]
    reloaded = authed_client.get(f"/api/v1/clinic/encounters/{encounter['id']}/")
    assert reloaded.status_code == 200
    assert reloaded.data["complaints"] == complaints


def test_phase_1l_a_500_character_text_is_accepted_and_501_is_rejected_without_mutation(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1LATextLimit")
    accepted = patch_note(
        authed_client,
        encounter["id"],
        complaints=[complaint("x" * 500)],
        etag=encounter["consultation_etag"],
    )
    rejected = patch_note(
        authed_client,
        encounter["id"],
        complaints=[complaint("x" * 501)],
        etag=accepted.data["etag"],
    )

    assert accepted.status_code == 200
    assert rejected.status_code == 400
    assert Encounter.objects.get(id=encounter["id"]).complaints == [complaint("x" * 500)]
    assert ClinicalNote.objects.get(encounter_id=encounter["id"]).content == {}


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_phase_1l_a_blank_complaint_text_is_rejected(tenant, authed_client, text):
    encounter = create_encounter(tenant, authed_client, label="Phase1LABlank")
    response = patch_note(
        authed_client,
        encounter["id"],
        complaints=[complaint(text)],
        etag=encounter["consultation_etag"],
    )

    assert response.status_code == 400
    assert Encounter.objects.get(id=encounter["id"]).complaints == []
    assert not ClinicalNote.objects.filter(encounter_id=encounter["id"]).exists()


@pytest.mark.parametrize("unit", ["HOURS", "DAYS", "WEEKS", "MONTHS"])
def test_phase_1l_a_allowed_duration_units_are_accepted(tenant, authed_client, unit):
    encounter = create_encounter(tenant, authed_client, label="Phase1LAUnit")
    response = patch_note(
        authed_client,
        encounter["id"],
        complaints=[complaint(SYNTHETIC_COMPLAINT, 2, unit)],
        etag=encounter["consultation_etag"],
    )

    assert response.status_code == 200
    assert response.data["complaints"] == [complaint(SYNTHETIC_COMPLAINT, 2, unit)]


@pytest.mark.parametrize(
    "item",
    [
        {"text": SYNTHETIC_COMPLAINT, "duration_value": 2},
        {"text": SYNTHETIC_COMPLAINT, "duration_unit": "DAYS"},
        {"text": SYNTHETIC_COMPLAINT, "duration_value": 2, "duration_unit": "FORTNIGHTS"},
        {"text": SYNTHETIC_COMPLAINT, "duration_value": 0, "duration_unit": "DAYS"},
        {"text": SYNTHETIC_COMPLAINT, "duration_value": -1, "duration_unit": "DAYS"},
    ],
)
def test_phase_1l_a_invalid_duration_is_rejected(tenant, authed_client, item):
    encounter = create_encounter(tenant, authed_client, label="Phase1LAInvalidDuration")
    response = patch_note(
        authed_client,
        encounter["id"],
        complaints=[item],
        etag=encounter["consultation_etag"],
    )

    assert response.status_code == 400
    assert Encounter.objects.get(id=encounter["id"]).complaints == []


def test_phase_1l_a_explicit_clear_and_omitted_complaints_semantics(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1LAClear")
    initial = patch_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
        [complaint(SYNTHETIC_COMPLAINT)],
    )
    omitted = patch_note(
        authed_client,
        encounter["id"],
        {"hpi": "Phase 1L-A verification - updated synthetic HPI"},
        initial.data["etag"],
    )
    cleared = patch_note(
        authed_client,
        encounter["id"],
        {"hpi": "Phase 1L-A verification - cleared synthetic complaint"},
        omitted.data["etag"],
        [],
    )

    assert initial.status_code == 200
    assert omitted.status_code == 200
    assert omitted.data["complaints"] == [complaint(SYNTHETIC_COMPLAINT)]
    assert cleared.status_code == 200
    assert cleared.data["complaints"] == []
    assert Encounter.objects.get(id=encounter["id"]).complaints == []


def test_phase_1l_a_legacy_bridge_preserves_content_and_explicit_structured_wins(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1LABridge")
    legacy_text = "  Phase 1L-A verification - synthetic legacy complaint  "
    legacy = patch_note(
        authed_client,
        encounter["id"],
        {"presenting_complaint": legacy_text},
        encounter["consultation_etag"],
    )
    explicit = [complaint(SYNTHETIC_COMPLAINT_2, 3, "HOURS")]
    structured = patch_note(
        authed_client,
        encounter["id"],
        {"presenting_complaint": "Phase 1L-A verification - synthetic legacy replacement"},
        legacy.data["etag"],
        explicit,
    )

    assert legacy.status_code == 200
    assert legacy.data["complaints"] == [complaint(legacy_text)]
    assert structured.status_code == 200
    assert structured.data["complaints"] == explicit
    note = ClinicalNote.objects.get(encounter_id=encounter["id"])
    assert note.content["presenting_complaint"] == "Phase 1L-A verification - synthetic legacy replacement"
    assert Encounter.objects.get(id=encounter["id"]).complaints == explicit


def test_phase_1l_a_stale_patch_and_legacy_post_return_current_complaints(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1LAConflict")
    first = patch_note(
        authed_client,
        encounter["id"],
        complaints=[complaint(SYNTHETIC_COMPLAINT)],
        etag=encounter["consultation_etag"],
    )
    latest = patch_note(
        authed_client,
        encounter["id"],
        complaints=[complaint(SYNTHETIC_COMPLAINT_2)],
        etag=first.data["etag"],
    )
    stale = patch_note(
        authed_client,
        encounter["id"],
        complaints=[complaint("Phase 1L-A verification - stale synthetic complaint")],
        etag=first.data["etag"],
    )
    stale_post = post_note(
        authed_client,
        encounter["id"],
        complaints=[complaint("Phase 1L-A verification - stale legacy post complaint")],
        etag=first.data["etag"],
    )

    assert latest.status_code == 200
    assert stale.status_code == 412
    assert stale_post.status_code == 409
    for response in (stale, stale_post):
        assert {
            "code", "detail", "etag", "status", "encounter_status", "content", "saved_at", "complaints"
        }.issubset(response.data)
        assert response.data["complaints"] == [complaint(SYNTHETIC_COMPLAINT_2)]
        assert response["ETag"] == response.data["etag"]


def test_phase_1l_a_sign_without_complaint_is_blocked_without_version_or_sign_audit(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1LASignBlock")
    draft = patch_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
    )
    sign = sign_note(authed_client, encounter["id"], {"hpi": SYNTHETIC_HPI}, draft.data["etag"])

    assert sign.status_code == 400
    assert sign.data["code"] == "PRESENTING_COMPLAINT_REQUIRED"
    assert Encounter.objects.get(id=encounter["id"]).status == "OPEN"
    note = ClinicalNote.objects.get(encounter_id=encounter["id"])
    assert note.status == "DRAFT"
    assert ClinicalNoteVersion.objects.filter(note=note).count() == 0
    assert not AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        action="SIGN",
        entity_type="ClinicalNote",
        entity_id=note.id,
    ).exists()


def test_phase_1l_a_sign_succeeds_with_structured_complaint(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1LASignSuccess")
    draft = patch_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
        [complaint(SYNTHETIC_COMPLAINT, 2, "DAYS")],
    )
    sign = sign_note(authed_client, encounter["id"], {"hpi": SYNTHETIC_HPI}, draft.data["etag"])

    assert sign.status_code == 200
    assert sign.data["complaints"] == [complaint(SYNTHETIC_COMPLAINT, 2, "DAYS")]
    assert Encounter.objects.get(id=encounter["id"]).status == "SIGNED"
    note = ClinicalNote.objects.get(encounter_id=encounter["id"])
    assert note.status == "SIGNED"
    assert ClinicalNoteVersion.objects.filter(note=note).count() == 1
    assert AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        action="SIGN",
        entity_type="ClinicalNote",
        entity_id=note.id,
    ).count() == 1


def test_phase_1l_a_triage_is_separate_context_and_does_not_satisfy_sign(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1LATriageContext")
    assert encounter["triage_complaint"] == SYNTHETIC_TRIAGE
    assert encounter["complaints"] == []
    sign = sign_note(authed_client, encounter["id"], {"hpi": SYNTHETIC_HPI}, encounter["consultation_etag"])

    assert sign.status_code == 400
    assert sign.data["code"] == "PRESENTING_COMPLAINT_REQUIRED"
    assert Encounter.objects.get(id=encounter["id"]).complaints == []


def test_phase_1l_a_complaint_audit_metadata_has_no_raw_text_and_autosave_is_summary_only(tenant, authed_client):
    encounter = create_encounter(tenant, authed_client, label="Phase1LAAudit")
    manual_text = "Phase 1L-A verification - synthetic manual complaint"
    manual = patch_note(
        authed_client,
        encounter["id"],
        {"hpi": SYNTHETIC_HPI},
        encounter["consultation_etag"],
        [complaint(manual_text)],
    )
    note_id = manual.data["note"]
    manual_events = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        entity_type="ClinicalNote",
        entity_id=note_id,
    )
    assert "complaints" in manual_events.latest("occurred_at").after["fields"]
    assert manual_text not in json.dumps(
        [{"before": event.before, "after": event.after, "reason": event.reason} for event in manual_events],
        default=str,
    )

    autosave_text = "Phase 1L-A verification - synthetic autosave complaint"
    autosave = patch_note(
        authed_client,
        encounter["id"],
        {"hpi": "Phase 1L-A verification - updated synthetic autosave HPI"},
        manual.data["etag"],
        [complaint(autosave_text)],
        autosave=True,
    )
    summaries = AuditEvent.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        actor=tenant.user,
        action="UPDATE",
        entity_type="Encounter",
        entity_id=encounter["id"],
        after__reason="ENCOUNTER_DRAFT_UPDATED",
    )
    assert autosave.status_code == 200
    assert summaries.count() == 1
    assert summaries.first().after["reason"] == "ENCOUNTER_DRAFT_UPDATED"
    assert autosave_text not in json.dumps([event.after for event in summaries], default=str)
    assert AuditEvent.objects.filter(entity_type="ClinicalNote", entity_id=note_id, action="UPDATE").count() == 0


def test_phase_1l_a_data_migration_bridges_legacy_without_rewriting_note_history(tenant, authed_client):
    migration = importlib.import_module("clinical.migrations.0004_encounter_complaints")
    first = Encounter.objects.get(id=create_encounter(tenant, authed_client, label="Phase1LAMigrate")['id'])
    blank = Encounter.objects.get(id=create_encounter(tenant, authed_client, label="Phase1LAMigrateBlank")['id'])
    signed = Encounter.objects.get(id=create_encounter(tenant, authed_client, label="Phase1LAMigrateSigned")['id'])
    first.complaints = []
    blank.complaints = []
    signed.complaints = []
    Encounter.objects.bulk_update([first, blank, signed], ["complaints"])

    legacy_text = "Phase 1L-A verification - synthetic migrated complaint"
    first_note = ClinicalNote.objects.create(
        organisation=tenant.organisation,
        facility=tenant.facility,
        encounter=first,
        note_type="CONSULTATION",
        content={"presenting_complaint": legacy_text},
        author=tenant.user,
    )
    blank_note = ClinicalNote.objects.create(
        organisation=tenant.organisation,
        facility=tenant.facility,
        encounter=blank,
        note_type="CONSULTATION",
        content={"presenting_complaint": "   "},
        author=tenant.user,
    )
    signed_content = {"presenting_complaint": "Phase 1L-A verification - synthetic signed history"}
    signed_note = ClinicalNote.objects.create(
        organisation=tenant.organisation,
        facility=tenant.facility,
        encounter=signed,
        note_type="CONSULTATION",
        content=signed_content,
        status="SIGNED",
        author=tenant.user,
        signed_by=tenant.user,
        current_version=1,
    )
    signed_version = ClinicalNoteVersion.objects.create(
        organisation=tenant.organisation,
        note=signed_note,
        version_number=1,
        content=signed_content,
        created_by=tenant.user,
    )

    class MigrationApps:
        def get_model(self, app_label, model_name):
            assert app_label == "clinical"
            return {"Encounter": Encounter, "ClinicalNote": ClinicalNote}[model_name]

    migration.migrate_legacy_complaints(MigrationApps(), None)

    assert Encounter.objects.get(id=first.id).complaints == [complaint(legacy_text)]
    assert Encounter.objects.get(id=blank.id).complaints == []
    assert ClinicalNote.objects.get(id=first_note.id).content == {"presenting_complaint": legacy_text}
    assert ClinicalNote.objects.get(id=blank_note.id).content == {"presenting_complaint": "   "}
    assert ClinicalNote.objects.get(id=signed_note.id).content == signed_content
    assert ClinicalNoteVersion.objects.get(id=signed_version.id).content == signed_content
