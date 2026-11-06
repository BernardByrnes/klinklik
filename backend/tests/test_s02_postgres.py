from datetime import date
from concurrent.futures import ThreadPoolExecutor
import threading
from uuid import uuid4

import pytest
from django.db import DatabaseError, IntegrityError, close_old_connections, connection, transaction

from accounts.models import User
from application.reception.commands import visit_check_in
from audit.models import AuditEvent
from billing.models import Invoice
from clinical.models import Encounter, TriageAssessment
from core.rls import rls_status
from core.migration_reconciliation import (
    backfill_mig002,
    cutover_mig002,
    inventory_mig002,
    legacy_writes_enabled_mig002,
    resolve_mig002_reconciliation,
    rollback_mig002,
    target_writes_enabled_mig002,
    verify_mig002,
)
from core.services import tenant_atomic
from core.models import MigrationCutover, MigrationReconciliation
from patients.models import Patient
from scheduling.models import QueueEntry, Visit
from tenancy.models import Department, Facility, Organisation


pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="S-02 PostgreSQL proof gate"),
]


@pytest.fixture
def enabled_mig002_postgres(tenant, enabled_mig001_target):
    with tenant_atomic(tenant.organisation.id):
        inventory_mig002(organisation=tenant.organisation)
        backfill_mig002(organisation=tenant.organisation)
        cutover_mig002(organisation=tenant.organisation)
        # Read the switch inside the tenant transaction: RLS refuses this row
        # outside a tenant context.
        switch = MigrationCutover.objects.get(
            organisation=tenant.organisation,
            migration_id="MIG-002",
        )
    return switch


def _sqlstate(error):
    cause = error.value if hasattr(error, "value") else error
    seen = set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        state = (
            getattr(cause, "sqlstate", None)
            or getattr(cause, "pgcode", None)
            or getattr(getattr(cause, "diag", None), "sqlstate", None)
        )
        if state:
            return state
        cause = getattr(cause, "__cause__", None) or getattr(cause, "__context__", None)
    return None


def test_pg_s02_queueentry_is_force_rls_and_has_scope_guard():
    status = rls_status()
    assert status["enforced"] is True
    assert status["role"]["bypass_rls"] is False
    queue_table = next(table for table in status["tables"] if table["name"] == "scheduling_queueentry")
    assert queue_table["rowsecurity"] is True
    assert queue_table["force"] is True
    assert queue_table["tenant_policy"] is True

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_trigger
                WHERE tgrelid = 'scheduling_queueentry'::regclass
                  AND tgname = 'klin_klink_queue_visit_scope'
                  AND NOT tgisinternal
            )
            """
        )
        assert cursor.fetchone()[0] is True
        # Owner-run migration 0007 installs the canonical state guards.
        cursor.execute(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'scheduling_queueentry'::regclass
              AND conname IN ('queue_entry_state_valid', 'queue_entry_attempt_counts_nonnegative')
            """
        )
        assert {row[0] for row in cursor.fetchall()} == {
            "queue_entry_state_valid",
            "queue_entry_attempt_counts_nonnegative",
        }
        cursor.execute(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'scheduling_queueentry'
              AND indexname IN ('uniq_active_queue_visit_department', 'uniq_in_service_queue_visit')
            """
        )
        assert {row[0] for row in cursor.fetchall()} == {
            "uniq_active_queue_visit_department",
            "uniq_in_service_queue_visit",
        }
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgrelid = 'scheduling_queueentry'::regclass
                  AND tgname = 'klin_klink_queue_state'
                  AND NOT tgisinternal
            )
            """
        )
        assert cursor.fetchone()[0] is True
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_trigger
                WHERE tgrelid = 'clinical_encountercoauthor'::regclass
                  AND tgname = 'klin_klink_encounter_co_author_scope'
                  AND NOT tgisinternal
            )
            """
        )
        assert cursor.fetchone()[0] is True


def test_pg_s02_queueentry_scope_guard_rejects_department_and_visit_mismatch(tenant):
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S02-{uuid4().hex[:8]}",
            first_name="Scope",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        visit = Visit.objects.create(
            organisation=organisation,
            facility=facility,
            patient=patient,
            local_service_date=date.today(),
            visit_type="OUTPATIENT_NEW",
            opened_by=tenant.user,
        )
        other_facility = Facility.objects.create(
            organisation=organisation,
            name="Other S02 Facility",
            code=f"S02-{uuid4().hex[:8]}",
        )
        other_department = Department.objects.create(
            organisation=organisation,
            facility=other_facility,
            name="Other S02 Department",
            code=f"S02-{uuid4().hex[:8]}",
        )

        attempts = (
            {
                "facility": facility,
                "department": other_department,
                "visit": visit,
            },
            {
                "facility": other_facility,
                "department": other_department,
                "visit": visit,
            },
        )
        for values in attempts:
            with pytest.raises(DatabaseError) as error:
                with transaction.atomic():
                    QueueEntry.objects.create(
                        organisation=organisation,
                        patient=patient,
                        queue_date=visit.local_service_date,
                        sequence=uuid4().int % 1000000 + 1,
                        queue_type="TRIAGE",
                        work_identity=f"PG-S02-{uuid4().hex}",
                        status="WAITING",
                        state="WAITING",
                        **values,
                    )
            assert _sqlstate(error) == "23514"


def test_pg_s02_active_visit_department_constraint_rejects_duplicate_path(tenant, enabled_mig002_postgres):
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S02-ACTIVE-{uuid4().hex[:8]}",
            first_name="Active",
            last_name="Path",
            sex="UNKNOWN",
        )
        visit = Visit.objects.create(
            organisation=organisation,
            facility=facility,
            patient=patient,
            local_service_date=date.today(),
            visit_type="OUTPATIENT_NEW",
            opened_by=tenant.user,
        )
        QueueEntry.objects.create(
            organisation=organisation,
            facility=facility,
            visit=visit,
            patient=patient,
            department=tenant.department,
            queue_date=visit.local_service_date,
            sequence=uuid4().int % 1000000 + 1,
            queue_type="TRIAGE",
            work_identity=f"PG-S02-ACTIVE-{uuid4().hex}",
            status="WAITING",
            state="WAITING",
        )
        with pytest.raises(IntegrityError) as error:
            with transaction.atomic():
                QueueEntry.objects.create(
                    organisation=organisation,
                    facility=facility,
                    visit=visit,
                    patient=patient,
                    department=tenant.department,
                    queue_date=visit.local_service_date,
                    sequence=uuid4().int % 1000000 + 1,
                    queue_type="CONSULTATION",
                    work_identity=f"PG-S02-ACTIVE-DUP-{uuid4().hex}",
                    status="WAITING",
                    state="WAITING",
                )
        assert _sqlstate(error) == "23505"


def test_pg_s02_queueentry_state_constraint_rejects_unclassified_target(tenant, enabled_mig002_postgres):
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S02-STATE-{uuid4().hex[:8]}",
            first_name="Invalid",
            last_name="State",
            sex="UNKNOWN",
        )
        visit = Visit.objects.create(
            organisation=organisation,
            facility=facility,
            patient=patient,
            local_service_date=date.today(),
            visit_type="OUTPATIENT_NEW",
            opened_by=tenant.user,
        )
        with pytest.raises(IntegrityError) as error:
            with transaction.atomic():
                QueueEntry.objects.create(
                    organisation=organisation,
                    facility=facility,
                    visit=visit,
                    patient=patient,
                    department=tenant.department,
                    queue_date=visit.local_service_date,
                    sequence=uuid4().int % 1000000 + 1,
                    queue_type="TRIAGE",
                    work_identity=f"PG-S02-STATE-{uuid4().hex}",
                    status="WAITING",
                    state="UNCLASSIFIED",
                )
        assert _sqlstate(error) == "23514"


def test_pg_s02_concurrent_duplicate_active_paths_have_one_winner(tenant, enabled_mig002_postgres):
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S02-RACE-{uuid4().hex[:8]}",
            first_name="Race",
            last_name="Winner",
            sex="UNKNOWN",
        )
        visit = Visit.objects.create(
            organisation=organisation,
            facility=facility,
            patient=patient,
            local_service_date=date.today(),
            visit_type="OUTPATIENT_NEW",
            opened_by=tenant.user,
        )
    barrier = threading.Barrier(2)
    organisation_id = str(tenant.organisation.id)
    facility_id = str(tenant.facility.id)
    visit_id = str(visit.id)
    patient_id = str(patient.id)
    department_id = str(tenant.department.id)

    def attempt(index):
        close_old_connections()
        try:
            with tenant_atomic(organisation_id):
                barrier.wait(timeout=10)
                try:
                    with transaction.atomic():
                        QueueEntry.objects.create(
                            organisation_id=organisation_id,
                            facility_id=facility_id,
                            visit_id=visit_id,
                            patient_id=patient_id,
                            department_id=department_id,
                            queue_date=date.today(),
                            sequence=100 + index,
                            queue_type="TRIAGE",
                            work_identity="PG-S02-RACE-ACTIVE-PATH",
                            status="WAITING",
                            state="WAITING",
                        )
                    return "created"
                except IntegrityError as error:
                    return _sqlstate(error)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, (1, 2)))
    assert sorted(results) == ["23505", "created"]
    # Count inside a fresh tenant context: the workers closed their connections
    # and FORCE RLS refuses an unscoped read.
    with tenant_atomic(tenant.organisation.id):
        assert QueueEntry.objects.filter(
            organisation=tenant.organisation,
            facility=tenant.facility,
            visit_id=visit.id,
            department=tenant.department,
            work_identity="PG-S02-RACE-ACTIVE-PATH",
        ).count() == 1


# --- S-02 recovery proofs -------------------------------------------------

def _pg_patient(tenant, label):
    organisation = Organisation.objects.get(id=tenant.organisation.id)
    return Patient.objects.create(
        organisation=organisation,
        patient_no=f"P-PG-S02-{label}-{uuid4().hex[:8]}",
        first_name=label,
        last_name="Synthetic",
        sex="UNKNOWN",
    )


def _pg_visit(tenant, patient):
    organisation = Organisation.objects.get(id=tenant.organisation.id)
    facility = Facility.objects.get(id=tenant.facility.id)
    return Visit.objects.create(
        organisation=organisation,
        facility=facility,
        patient=patient,
        local_service_date=date.today(),
        visit_type="OUTPATIENT_NEW",
        opened_by=tenant.user,
    )


def _pg_entry(
    tenant,
    visit,
    *,
    label,
    status="WAITING",
    state="WAITING",
    queue_type="TRIAGE",
    priority="ROUTINE",
    current_stage="TRIAGE",
):
    organisation = Organisation.objects.get(id=tenant.organisation.id)
    facility = Facility.objects.get(id=tenant.facility.id)
    department = Department.objects.get(id=tenant.department.id)
    sequence = (
        QueueEntry.objects.filter(
            facility=facility, queue_date=visit.local_service_date
        ).count()
        + 1
    )
    return QueueEntry.objects.create(
        organisation=organisation,
        facility=facility,
        visit=visit,
        patient=visit.patient,
        department=department,
        queue_date=visit.local_service_date,
        sequence=sequence,
        queue_type=queue_type,
        priority=priority,
        work_identity=f"PG-S02-{label}-{uuid4().hex[:8]}",
        status=status,
        state=state,
        current_stage=current_stage,
        source_stage="RECEPTION",
    )


def _pg_triage_evidence(tenant, entry, acuity="URGENT"):
    organisation = Organisation.objects.get(id=tenant.organisation.id)
    facility = Facility.objects.get(id=tenant.facility.id)
    return TriageAssessment.objects.create(
        organisation=organisation,
        facility=facility,
        queue_entry=entry,
        patient=entry.patient,
        assessed_by=tenant.user,
        acuity=acuity,
    )


def test_pg_s02_mig002_populated_backfill_reconciliation_and_cursor(
    tenant, enabled_mig001_target
):
    organisation = Organisation.objects.get(id=tenant.organisation.id)
    with tenant_atomic(organisation.id):
        waiting_visit = _pg_visit(tenant, _pg_patient(tenant, "Waiting"))
        waiting = _pg_entry(tenant, waiting_visit, label="WAIT", status="WAITING", state=None)
        triaged_visit = _pg_visit(tenant, _pg_patient(tenant, "Triaged"))
        triaged = _pg_entry(
            tenant,
            triaged_visit,
            label="TRIAGED",
            status="TRIAGED",
            state=None,
            current_stage="CONSULTATION",
        )
        _pg_triage_evidence(tenant, triaged)
        ambiguous_visit = _pg_visit(tenant, _pg_patient(tenant, "Ambiguous"))
        ambiguous = _pg_entry(
            tenant,
            ambiguous_visit,
            label="AMBIG",
            status="TRIAGED",
            state=None,
            current_stage="CONSULTATION",
        )

        inventory = inventory_mig002(organisation=organisation)
        assert inventory.inspected == 3
        assert inventory.exceptions == 1

        ordered = sorted([waiting.id, triaged.id, ambiguous.id])
        assert backfill_mig002(organisation=organisation, batch_size=1).inspected == 1
        assert backfill_mig002(
            organisation=organisation, batch_size=1, after_id=ordered[0]
        ).inspected == 1
        assert backfill_mig002(
            organisation=organisation, batch_size=1, after_id=ordered[1]
        ).inspected == 1

        assert QueueEntry.objects.get(id=waiting.id).state == "WAITING"
        source = QueueEntry.objects.get(id=triaged.id)
        assert source.state == "COMPLETED"
        destinations = QueueEntry.objects.filter(
            organisation=organisation, visit_id=triaged.visit_id, queue_type="CONSULTATION"
        )
        assert destinations.count() == 1
        destination = destinations.get()
        assert destination.state == "WAITING"

        with pytest.raises(ValueError):
            cutover_mig002(organisation=organisation)

        _pg_triage_evidence(tenant, QueueEntry.objects.get(id=ambiguous.id), acuity="ROUTINE")
        evidence = MigrationReconciliation.objects.get(
            organisation=organisation,
            migration_id="MIG-002",
            legacy_pk=str(ambiguous.id),
        )
        resolve_mig002_reconciliation(
            organisation=organisation,
            reconciliation_id=evidence.id,
            actor=tenant.user,
            reason="Synthetic corrected triage evidence",
        )
        event = AuditEvent.objects.get(
            event_code="MIGRATION_RECONCILIATION_RESOLVED", entity_id=str(evidence.id)
        )
        assert event.after["resolution_state"] == "RESOLVED"
        assert "Synthetic corrected" not in str(event.after)

        backfill_mig002(organisation=organisation)
        assert QueueEntry.objects.filter(
            visit_id=triaged.visit_id, queue_type="CONSULTATION"
        ).count() == 1
        assert QueueEntry.objects.get(id=ambiguous.id).state == "COMPLETED"
        assert QueueEntry.objects.filter(
            visit_id=ambiguous.visit_id, queue_type="CONSULTATION"
        ).count() == 1
        verification = verify_mig002(organisation=organisation)
        assert verification.shadow_read_equal, verification.as_dict()
        cutover_mig002(organisation=organisation)


def test_pg_s02_exact_call_replay_and_competing_loser(tenant, authed_client, enabled_mig002_postgres):
    organisation = Organisation.objects.get(id=tenant.organisation.id)
    with tenant_atomic(organisation.id):
        visit = _pg_visit(tenant, _pg_patient(tenant, "ExactCall"))
        entry = _pg_entry(tenant, visit, label="CALL")
        entry_id = entry.id
        version = entry.version

    headers = {
        "HTTP_IF_MATCH": f'"{version}"',
        "HTTP_IDEMPOTENCY_KEY": "pg-s02-exact-call",
    }
    first = authed_client.post(
        f"/api/v1/clinic/queue/{entry_id}/call/", {}, format="json", **headers
    )
    assert first.status_code == 200, first.data
    assert first.data["state"] == "CALLED"
    assert first.data["called_by_id"] == str(tenant.user.id)
    assert first.data["version"] == version + 1

    replay = authed_client.post(
        f"/api/v1/clinic/queue/{entry_id}/call/", {}, format="json", **headers
    )
    assert replay.status_code == 200, replay.data
    assert replay.data == first.data
    assert replay["Idempotent-Replay"] == "true"

    with tenant_atomic(organisation.id):
        assert AuditEvent.objects.filter(
            entity_id=str(entry_id), event_code="QUEUE_CALLED"
        ).count() == 1
        current_version = QueueEntry.objects.get(id=entry_id).version

    loser = authed_client.post(
        f"/api/v1/clinic/queue/{entry_id}/call/",
        {},
        format="json",
        HTTP_IF_MATCH=f'"{current_version}"',
        HTTP_IDEMPOTENCY_KEY="pg-s02-exact-call-loser",
    )
    assert loser.status_code == 409, loser.data
    assert loser.data["code"] == "ALREADY_CALLED"
    assert loser.data["called_by_id"] == str(tenant.user.id)

    with tenant_atomic(organisation.id):
        other_visit = _pg_visit(tenant, _pg_patient(tenant, "StaleCall"))
        other = _pg_entry(tenant, other_visit, label="STALE")
        other_id = other.id
        # A positive but stale version, so the guard is exercised rather than
        # the If-Match syntax check.
        QueueEntry.objects.filter(id=other_id).update(version=2)
        stale_version = 1
    stale = authed_client.post(
        f"/api/v1/clinic/queue/{other_id}/call/",
        {},
        format="json",
        HTTP_IF_MATCH=f'"{stale_version}"',
        HTTP_IDEMPOTENCY_KEY="pg-s02-exact-call-stale",
    )
    assert stale.status_code == 412, stale.data
    assert stale.data["code"] == "VERSION_CONFLICT"
    with tenant_atomic(organisation.id):
        assert QueueEntry.objects.get(id=other_id).state == "WAITING"


def test_pg_s02_call_next_skips_a_locked_candidate(tenant, authed_client, enabled_mig002_postgres):
    organisation = Organisation.objects.get(id=tenant.organisation.id)
    with tenant_atomic(organisation.id):
        urgent_visit = _pg_visit(tenant, _pg_patient(tenant, "Urgent"))
        urgent = _pg_entry(tenant, urgent_visit, label="URGENT", priority="URGENT")
        routine_visit = _pg_visit(tenant, _pg_patient(tenant, "Routine"))
        routine = _pg_entry(tenant, routine_visit, label="ROUTINE", priority="ROUTINE")
        urgent_id, routine_id = urgent.id, routine.id
        department_id = str(tenant.department.id)

    ready = threading.Event()
    release = threading.Event()
    holder = {}

    def hold_first_candidate():
        close_old_connections()
        try:
            with tenant_atomic(organisation.id):
                with transaction.atomic():
                    locked = QueueEntry.objects.select_for_update().filter(id=urgent_id).first()
                    holder["id"] = str(locked.id)
                    ready.set()
                    release.wait(timeout=20)
        finally:
            close_old_connections()

    thread = threading.Thread(target=hold_first_candidate)
    thread.start()
    try:
        assert ready.wait(timeout=20)
        first_call = authed_client.post(
            "/api/v1/clinic/queue/call-next/",
            {"department_id": department_id, "queue_type": "TRIAGE"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="pg-s02-call-next-skip",
        )
        assert first_call.status_code == 200, first_call.data
        assert first_call.data["queue_entry_id"] == str(routine_id)
    finally:
        release.set()
        thread.join(timeout=20)

    second_call = authed_client.post(
        "/api/v1/clinic/queue/call-next/",
        {"department_id": department_id, "queue_type": "TRIAGE"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="pg-s02-call-next-after-release",
    )
    assert second_call.status_code == 200, second_call.data
    assert second_call.data["queue_entry_id"] == str(urgent_id)

    empty = authed_client.post(
        "/api/v1/clinic/queue/call-next/",
        {"department_id": department_id, "queue_type": "TRIAGE"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="pg-s02-call-next-empty",
    )
    assert empty.status_code == 200, empty.data
    assert empty.data["queue_entry_id"] is None


def test_pg_s02_triage_and_encounter_handoff_keeps_one_charge(
    tenant, authed_client, enabled_mig002_postgres
):
    organisation = Organisation.objects.get(id=tenant.organisation.id)
    with tenant_atomic(organisation.id):
        patient = _pg_patient(tenant, "Journey")
        outcome = visit_check_in(
            organisation=organisation,
            facility=Facility.objects.get(id=tenant.facility.id),
            actor=tenant.user,
            patient_id=patient.id,
            department_id=tenant.department.id,
            visit_type="OUTPATIENT_NEW",
            payer_type="CASH",
        )
        visit_id = outcome.visit.id
        source_id = outcome.queue.id
        invoice_id = outcome.invoice.id
        source_version = outcome.queue.version

    called = authed_client.post(
        f"/api/v1/clinic/queue/{source_id}/call/",
        {},
        format="json",
        HTTP_IF_MATCH=f'"{source_version}"',
        HTTP_IDEMPOTENCY_KEY="pg-s02-journey-call",
    )
    assert called.status_code == 200, called.data
    assert called.data["state"] == "CALLED"
    called_version = called.data["version"]

    triaged = authed_client.post(
        f"/api/v1/clinic/triage/{source_id}/",
        {
            "expected_version": called_version,
            "acuity": "URGENT",
            "chief_complaint": "Synthetic PostgreSQL journey",
        },
        format="json",
        HTTP_IF_MATCH=f'"{called_version}"',
        HTTP_IDEMPOTENCY_KEY="pg-s02-journey-triage",
    )
    assert triaged.status_code == 201, triaged.data
    assert triaged.data["queue_entry"]["state"] == "COMPLETED"

    with tenant_atomic(organisation.id):
        source = QueueEntry.objects.get(id=source_id)
        assert source.state == "COMPLETED"
        destination = QueueEntry.objects.get(
            organisation=organisation,
            visit_id=visit_id,
            queue_type="CONSULTATION",
        )
        assert destination.id != source.id
        assert destination.state == "WAITING"
        destination_id = destination.id
        destination_version = destination.version

    opened = authed_client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": str(destination_id), "expected_version": destination_version},
        format="json",
        HTTP_IF_MATCH=f'"{destination_version}"',
        HTTP_IDEMPOTENCY_KEY="pg-s02-journey-encounter",
    )
    assert opened.status_code == 201, opened.data
    assert str(opened.data["visit"]) == str(visit_id)
    assert str(opened.data["queue_entry"]) == str(destination_id)

    with tenant_atomic(organisation.id):
        assert QueueEntry.objects.get(id=destination_id).state == "IN_SERVICE"
        charges = Invoice.objects.filter(organisation=organisation, visit_id=visit_id)
        assert charges.count() == 1
        assert str(charges.get().id) == str(invoice_id)
        assert Encounter.objects.filter(organisation=organisation, visit_id=visit_id).count() == 1

    # A handled stage refusal leaves the source CALLED with no Encounter.
    with tenant_atomic(organisation.id):
        refused_visit = _pg_visit(tenant, _pg_patient(tenant, "Refused"))
        refused = _pg_entry(tenant, refused_visit, label="REFUSED")
        refused_id = refused.id
        refused_version = refused.version
    refused_call = authed_client.post(
        f"/api/v1/clinic/queue/{refused_id}/call/",
        {},
        format="json",
        HTTP_IF_MATCH=f'"{refused_version}"',
        HTTP_IDEMPOTENCY_KEY="pg-s02-refused-call",
    )
    assert refused_call.status_code == 200, refused_call.data
    refused_current = refused_call.data["version"]
    refusal = authed_client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": str(refused_id), "expected_version": refused_current},
        format="json",
        HTTP_IF_MATCH=f'"{refused_current}"',
        HTTP_IDEMPOTENCY_KEY="pg-s02-refused-encounter",
    )
    assert refusal.status_code == 409, refusal.data
    assert refusal.data["code"] == "INVALID_STATE"
    with tenant_atomic(organisation.id):
        assert QueueEntry.objects.get(id=refused_id).state == "CALLED"
        assert not Encounter.objects.filter(queue_entry_id=refused_id).exists()


def test_pg_s02_state_guard_is_per_organisation(tenant, enabled_mig002_postgres):
    organisation = Organisation.objects.get(id=tenant.organisation.id)
    with tenant_atomic(organisation.id):
        visit = _pg_visit(tenant, _pg_patient(tenant, "Guard"))
        entry = _pg_entry(tenant, visit, label="GUARD")
        entry_id = entry.id

    with pytest.raises(IntegrityError) as error:
        with tenant_atomic(organisation.id):
            with transaction.atomic():
                QueueEntry.objects.filter(id=entry_id).update(state=None)
    assert _sqlstate(error) == "23514"

    other = Organisation.objects.create(name="S02 Other", slug=f"s02-other-{uuid4().hex[:6]}")
    with tenant_atomic(other.id):
        other_facility = Facility.objects.create(organisation=other, name="Other", code="MAIN")
        other_department = Department.objects.create(
            organisation=other, facility=other_facility, name="OPD", code="OPD"
        )
        other_user = User.objects.create_user(f"s02-other-{uuid4().hex[:6]}", "test-password-123")
        other_patient = Patient.objects.create(
            organisation=other,
            patient_no=f"P-OTHER-{uuid4().hex[:8]}",
            first_name="Other",
            last_name="Tenant",
            sex="UNKNOWN",
        )
        other_visit = Visit.objects.create(
            organisation=other,
            facility=other_facility,
            patient=other_patient,
            local_service_date=date.today(),
            visit_type="OUTPATIENT_NEW",
            opened_by=other_user,
        )
        legacy = QueueEntry.objects.create(
            organisation=other,
            facility=other_facility,
            visit=other_visit,
            patient=other_patient,
            department=other_department,
            queue_date=date.today(),
            sequence=1,
            queue_type="TRIAGE",
            work_identity=f"PG-S02-LEGACY-{uuid4().hex[:8]}",
            status="WAITING",
            state=None,
        )
        assert legacy.state is None


def test_pg_s02_rollback_fences_target_and_requires_a_new_cycle(
    tenant, authed_client, enabled_mig002_postgres
):
    organisation = Organisation.objects.get(id=tenant.organisation.id)
    with tenant_atomic(organisation.id):
        visit = _pg_visit(tenant, _pg_patient(tenant, "Rollback"))
        entry = _pg_entry(tenant, visit, label="ROLLBACK")
        entry_id = entry.id
        before = QueueEntry.objects.filter(organisation=organisation).count()
        rollback_mig002(
            organisation=organisation,
            actor=tenant.user,
            reason="Synthetic PostgreSQL rollback",
        )
        switch = MigrationCutover.objects.get(
            organisation=organisation, migration_id="MIG-002"
        )
        assert switch.phase == "ROLLBACK"
        assert switch.target_reads_enabled is False
        assert switch.target_writes_enabled is False
        assert target_writes_enabled_mig002(organisation) is False
        assert legacy_writes_enabled_mig002(organisation) is True
        assert QueueEntry.objects.filter(organisation=organisation).count() == before
        assert QueueEntry.objects.filter(id=entry_id).exists()

    with tenant_atomic(organisation.id):
        assert AuditEvent.objects.filter(event_code="MIGRATION_ROLLED_BACK").exists()

    from scheduling.queue import QueueDomainError

    with pytest.raises(QueueDomainError) as blocked:
        with tenant_atomic(organisation.id):
            from scheduling.queue import call_next_or_exact

            call_next_or_exact(
                organisation=organisation,
                facility=Facility.objects.get(id=tenant.facility.id),
                actor=tenant.user,
                department_id=tenant.department.id,
                queue_type="TRIAGE",
            )
    assert blocked.value.code == "MIGRATION_TARGET_DISABLED"

    # Target readers are fenced as well.
    fenced_read = authed_client.get("/api/v1/clinic/queue/operational/")
    assert fenced_read.status_code == 503, fenced_read.data
    assert fenced_read.data["code"] == "MIGRATION_TARGET_DISABLED"

    with tenant_atomic(organisation.id):
        with pytest.raises(ValueError):
            cutover_mig002(organisation=organisation)
