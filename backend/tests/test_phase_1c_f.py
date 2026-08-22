import threading

import pytest
from django.db import close_old_connections, connection, IntegrityError, transaction

from clinical.models import ClinicalNote, ClinicalNoteVersion, Encounter
from clinical.services import save_note, sign_note
from core.services import tenant_atomic
from tests.clinical_test_helpers import note_headers


pytestmark = pytest.mark.django_db(transaction=True)


def create_encounter(tenant, client, label="Phase1CF"):
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
        {"acuity": "ROUTINE", "chief_complaint": "Phase 1C-F synthetic triage"},
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


def require_postgres():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL is required for row-lock concurrency verification")


def _thread_objects(tenant, encounter_id):
    from accounts.models import User
    from tenancy.models import Facility, Organisation

    organisation = Organisation.objects.get(id=tenant.organisation.id)
    facility = Facility.objects.get(id=tenant.facility.id)
    actor = User.objects.get(id=tenant.user.id)
    encounter = Encounter.objects.get(id=encounter_id)
    return organisation, facility, actor, encounter


def test_database_uniqueness_rejects_duplicate_consultation_note(tenant, authed_client):
    encounter_id = create_encounter(tenant, authed_client)
    saved = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"presenting_complaint": "Phase 1C-F synthetic note"}},
        format="json",
        **note_headers(authed_client, encounter_id),
    )
    assert saved.status_code == 200

    with tenant_atomic(tenant.organisation.id):
        encounter = Encounter.objects.get(id=encounter_id)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ClinicalNote.objects.create(
                    organisation=tenant.organisation,
                    facility=tenant.facility,
                    encounter=encounter,
                    note_type="CONSULTATION",
                    content={"hpi": "Phase 1C-F duplicate synthetic note"},
                    author=tenant.user,
                )

    assert ClinicalNote.objects.filter(encounter_id=encounter_id, note_type="CONSULTATION").count() == 1


def test_amendment_and_post_sign_normal_save_regression(tenant, authed_client):
    encounter_id = create_encounter(tenant, authed_client, label="Phase1CFAmend")
    signed = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/sign/",
        {"content": {"hpi": "Phase 1C-F signed synthetic note"}},
        format="json",
        **note_headers(authed_client, encounter_id),
    )
    assert signed.status_code == 200

    amended_content = {
        "hpi": "Phase 1C-F amended synthetic note",
        "past_medical_history": "Phase 1C-F amended synthetic history",
    }
    amended = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/amend/",
        {"content": amended_content, "reason": "Phase 1C-F correction verification"},
        format="json",
        **note_headers(authed_client, encounter_id),
    )
    assert amended.status_code == 200

    note = ClinicalNote.objects.get(encounter_id=encounter_id, note_type="CONSULTATION")
    assert note.status == "AMENDED"
    assert note.content == amended_content
    assert note.current_version == 2
    assert ClinicalNoteVersion.objects.get(note=note, version_number=2).content == amended_content

    rejected = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": {"hpi": "Phase 1C-F rejected normal save"}},
        format="json",
        **note_headers(authed_client, encounter_id),
    )
    assert rejected.status_code == 400


def test_postgres_save_vs_sign_serializes_signed_note_content(tenant, authed_client):
    require_postgres()
    encounter_id = create_encounter(tenant, authed_client, label="Phase1CFRace")
    initial_content = {
        "presenting_complaint": "Phase 1C-F initial synthetic complaint",
        "hpi": "Phase 1C-F initial synthetic HPI",
        "past_medical_history": "Phase 1C-F initial synthetic PMH",
        "past_surgical_history": "Phase 1C-F initial synthetic PSH",
        "assessment": "Phase 1C-F initial synthetic assessment",
        "plan": "Phase 1C-F initial synthetic plan",
    }
    saved = authed_client.post(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {"content": initial_content},
        format="json",
        **note_headers(authed_client, encounter_id),
    )
    assert saved.status_code == 200
    note_id = saved.data["note"]

    sign_locked = threading.Event()
    allow_sign = threading.Event()
    save_started = threading.Event()
    outcomes = {}

    def sign_worker():
        close_old_connections()
        try:
            with tenant_atomic(tenant.organisation.id):
                organisation, facility, actor, encounter = _thread_objects(tenant, encounter_id)
                with transaction.atomic():
                    locked = Encounter.objects.select_for_update().get(id=encounter_id)
                    sign_locked.set()
                    if not allow_sign.wait(timeout=10):
                        raise AssertionError("sign worker was not released")
                    sign_note(
                        organisation=organisation,
                        facility=facility,
                        actor=actor,
                        encounter=locked,
                        content={"hpi": "Phase 1C-F signed synthetic HPI"},
                    )
            outcomes["sign"] = "ok"
        except BaseException as exc:
            outcomes["sign"] = exc
        finally:
            close_old_connections()
            connection.close()

    def save_worker():
        close_old_connections()
        try:
            with tenant_atomic(tenant.organisation.id):
                organisation, facility, actor, encounter = _thread_objects(tenant, encounter_id)
                save_started.set()
                save_note(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    encounter=encounter,
                    content={"hpi": "Phase 1C-F late synthetic save"},
                )
            outcomes["save"] = "unexpectedly succeeded"
        except BaseException as exc:
            outcomes["save"] = exc
        finally:
            close_old_connections()
            connection.close()

    signer = threading.Thread(target=sign_worker)
    saver = threading.Thread(target=save_worker)
    signer.start()
    assert sign_locked.wait(timeout=10)
    saver.start()
    assert save_started.wait(timeout=10)
    allow_sign.set()
    signer.join(timeout=15)
    saver.join(timeout=15)

    assert not signer.is_alive()
    assert not saver.is_alive()
    assert outcomes["sign"] == "ok"
    assert isinstance(outcomes["save"], ValueError)

    note = ClinicalNote.objects.get(id=note_id)
    version = ClinicalNoteVersion.objects.get(note_id=note_id, version_number=1)
    assert note.status == "SIGNED"
    assert note.content == version.content
    assert note.content["hpi"] == "Phase 1C-F signed synthetic HPI"


def test_postgres_concurrent_first_save_creates_one_consultation_note(tenant, authed_client):
    require_postgres()
    encounter_id = create_encounter(tenant, authed_client, label="Phase1CFCreate")
    barrier = threading.Barrier(2)
    outcomes = []

    def worker(content):
        close_old_connections()
        try:
            with tenant_atomic(tenant.organisation.id):
                organisation, facility, actor, encounter = _thread_objects(tenant, encounter_id)
                barrier.wait(timeout=10)
                note = save_note(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    encounter=encounter,
                    content=content,
                )
                outcomes.append(("ok", str(note.id)))
        except BaseException as exc:
            outcomes.append(("error", exc))
        finally:
            close_old_connections()
            connection.close()

    threads = [
        threading.Thread(
            target=worker,
            args=({"hpi": "Phase 1C-F concurrent synthetic save A"},),
        ),
        threading.Thread(
            target=worker,
            args=({"hpi": "Phase 1C-F concurrent synthetic save B"},),
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert all(not thread.is_alive() for thread in threads)
    assert len(outcomes) == 2
    assert all(outcome[0] == "ok" for outcome in outcomes)
    assert ClinicalNote.objects.filter(encounter_id=encounter_id, note_type="CONSULTATION").count() == 1
