import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import threading
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection

from application.clinical.commands import encounter_open, encounter_sign
from audit.models import AuditEvent
from clinical.models import ClinicalNoteVersion, Encounter
from core.errors import CanonicalError
from core.mig004 import (
    backfill_mig004,
    constrain_mig004,
    cutover_mig004,
    inventory_mig004,
    verify_mig004,
)
from core.mig003 import (
    backfill_mig003,
    constrain_mig003,
    cutover_mig003,
    inventory_mig003,
    verify_mig003,
)
from core.migration_reconciliation import (
    backfill_mig002,
    cutover_mig002,
    inventory_mig002,
)
from core.models import MigrationCutover
from core.rls import rls_status
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import QueueEntry, Visit
from scheduling.queue import create_or_reuse_destination
from tenancy.models import Organisation
from tests.test_s04_encounter import _canonical_encounter, _save_and_sign

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="S-04 PostgreSQL proof gate"),
]

OWNER_DSN = os.getenv("S02_OWNER_DSN")


@pytest.fixture
def enabled_mig002_target(tenant, enabled_mig001_target):
    with tenant_atomic(tenant.organisation.id):
        inventory_mig002(organisation=tenant.organisation)
        backfill_mig002(organisation=tenant.organisation)
        cutover_mig002(organisation=tenant.organisation)
        return MigrationCutover.objects.get(
            organisation=tenant.organisation, migration_id="MIG-002"
        )


@pytest.fixture
def enabled_mig003_target(tenant, enabled_mig002_target):
    with tenant_atomic(tenant.organisation.id):
        inventory_mig003(organisation=tenant.organisation)
        backfill_mig003(organisation=tenant.organisation)
        verify_mig003(organisation=tenant.organisation)
        verify_mig003(organisation=tenant.organisation)
        constrain_mig003(organisation=tenant.organisation)
        cutover_mig003(organisation=tenant.organisation)
        return MigrationCutover.objects.get(
            organisation=tenant.organisation, migration_id="MIG-003"
        )


def _consultation_queue(tenant):
    with tenant_atomic(tenant.organisation.id):
        patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no=f"P-PG-S04-{uuid4().hex[:8]}",
            first_name="S04 PG",
            last_name="Synthetic",
            sex="UNKNOWN",
            date_of_birth=date(1990, 1, 1),
        )
        visit = Visit.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=patient,
            local_service_date=date.today(),
            visit_type="OUTPATIENT_NEW",
            opened_by=tenant.user,
        )
        queue, created = create_or_reuse_destination(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            visit=visit,
            department=tenant.department,
            queue_type="CONSULTATION",
            source_stage="RECEPTION",
        )
        assert created
    return visit, queue


def test_pg_s04_guards_are_force_rls_and_one_open_encounter(tenant):
    status = rls_status()
    assert status["enforced"] is True
    tables = {table["name"]: table for table in status["tables"]}
    for name in (
        "clinical_encounter",
        "clinical_clinicalnote",
        "clinical_clinicalnoteversion",
    ):
        assert tables[name]["rowsecurity"] is True
        assert tables[name]["force"] is True
        assert tables[name]["owner"] != status["role"]["name"]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'clinical_encounter'
              AND indexname = 'uniq_open_encounter_visit'
            """
        )
        assert cursor.fetchone() is not None
        cursor.execute(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'clinical_clinicalnoteversion'::regclass
              AND conname = 'note_version_hash_valid' AND convalidated
            """
        )
        assert cursor.fetchone() is not None
        cursor.execute(
            """
            SELECT tgname FROM pg_trigger
            WHERE tgrelid IN ('clinical_encounter'::regclass,
                              'clinical_clinicalnoteversion'::regclass)
              AND NOT tgisinternal AND tgenabled = 'O'
            """
        )
        assert {
            "klin_klink_encounter_retained",
            "klin_klink_note_version_immutable",
        } <= {row[0] for row in cursor.fetchall()}


def test_pg_s04_concurrent_open_has_one_encounter(tenant, enabled_mig002_target):
    visit, queue = _consultation_queue(tenant)
    barrier = threading.Barrier(2)

    def attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(tenant.organisation.id):
                outcome = encounter_open(
                    organisation=tenant.organisation,
                    facility=tenant.facility,
                    actor=tenant.user,
                    queue_entry_id=queue.id,
                    expected_version=queue.version,
                )
                return ("ok", str(outcome.encounter.id))
        except (CanonicalError, ValueError) as exc:
            return ("error", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: attempt(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    with tenant_atomic(tenant.organisation.id):
        assert Encounter.objects.filter(visit=visit).count() == 1
        assert QueueEntry.objects.get(id=queue.id).state == "IN_SERVICE"


def test_pg_s04_concurrent_sign_has_one_version_and_completion(
    tenant, authed_client, enabled_mig003_target
):
    setup = _canonical_encounter(tenant, authed_client)
    encounter_id = setup["encounter"]["id"]
    encounter = setup["encounter"]
    draft = authed_client.patch(
        f"/api/v1/clinic/encounters/{encounter_id}/notes/",
        {
            "content": {"hpi": "S04 PG synthetic HPI"},
            "complaints": [{"text": "S04 PG synthetic complaint"}],
        },
        format="json",
        HTTP_IF_MATCH=encounter["consultation_etag"],
    )
    assert draft.status_code == 200, draft.data
    etag = draft.data["etag"]
    barrier = threading.Barrier(2)

    def attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(tenant.organisation.id):
                outcome = encounter_sign(
                    organisation=tenant.organisation,
                    facility=tenant.facility,
                    actor=tenant.user,
                    encounter_id=encounter_id,
                    content={"hpi": "S04 PG synthetic HPI"},
                    complaints=[{"text": "S04 PG synthetic complaint"}],
                    expected_etag=etag,
                )
                return ("ok", str(outcome.note.id))
        except (CanonicalError, ValueError) as exc:
            return ("error", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: attempt(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    with tenant_atomic(tenant.organisation.id):
        head = Encounter.objects.get(id=encounter_id)
        assert head.status == "SIGNED"
        assert ClinicalNoteVersion.objects.filter(
            note__encounter_id=encounter_id
        ).count() == 1
        assert QueueEntry.objects.get(id=setup["destination_id"]).state == "COMPLETED"
        assert AuditEvent.objects.filter(
            event_code="ENCOUNTER_SIGNED", entity_id=str(encounter_id)
        ).count() == 1


def test_pg_s04_disabled_guard_blocks_cutover_from_constrained(
    tenant, authed_client, enabled_mig003_target
):
    if not OWNER_DSN:
        pytest.skip("S02_OWNER_DSN is not configured for the owner-prepared guard proof")
    import psycopg

    setup = _canonical_encounter(tenant, authed_client)
    encounter_id = setup["encounter"]["id"]
    _saved, signed = _save_and_sign(
        authed_client, encounter_id, setup["encounter"]["consultation_etag"]
    )
    assert signed.status_code == 200, signed.data
    organisation = Organisation.objects.get(id=tenant.organisation.id)
    with tenant_atomic(organisation.id):
        inventory_mig004(organisation=organisation)
        backfill_mig004(organisation=organisation)
        verify_mig004(organisation=organisation)
        verify_mig004(organisation=organisation)
        constrain_mig004(organisation=organisation)
        constrained = MigrationCutover.objects.get(
            organisation=organisation, migration_id="MIG-004"
        )
        assert constrained.phase == "CONSTRAINED"
    with psycopg.connect(OWNER_DSN, autocommit=True) as owner:
        with owner.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            assert cursor.fetchone()[0] == connection.settings_dict["NAME"]
        owner.execute(
            "ALTER TABLE clinical_clinicalnoteversion DISABLE TRIGGER klin_klink_note_version_immutable"
        )
        try:
            with pytest.raises(ValueError) as refused:
                with tenant_atomic(organisation.id):
                    cutover_mig004(organisation=organisation)
            assert "klin_klink_note_version_immutable" in str(refused.value)
            assert "migrate clinical 0012" in str(refused.value)
        finally:
            owner.execute(
                "ALTER TABLE clinical_clinicalnoteversion ENABLE TRIGGER klin_klink_note_version_immutable"
            )
    with tenant_atomic(organisation.id):
        unchanged = MigrationCutover.objects.get(
            organisation=organisation, migration_id="MIG-004"
        )
        assert unchanged.phase == "CONSTRAINED"
        cutover_mig004(organisation=organisation)
        activated = MigrationCutover.objects.get(
            organisation=organisation, migration_id="MIG-004"
        )
        assert activated.phase == "CUTOVER"
