from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, Lock

import psycopg
import pytest
from django.db import DatabaseError, connection, connections

from application.contracts import CommandResult
from audit.models import AuditEvent
from audit.services import record_event, record_fact, write_denial_audit
from core.errors import IdempotencyConflict, RetryableCommandFailure
from core.idempotency import IdempotencyRecord, UncommittedResponse, execute_idempotent, key_hash
from core.rls import is_tenant_policy_expression, rls_status
from core.services import run_in_tenant, tenant_atomic
from clinical.models import Encounter
from patients.models import Patient
from scheduling.models import QueueEntry
from tenancy.models import Department, FacilityWorkflowPolicy, Organisation


pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="PostgreSQL proof gate"),
]


@pytest.mark.parametrize(
    ("failure_type", "sqlstate"),
    [
        (psycopg.errors.SerializationFailure, "40001"),
        (psycopg.errors.DeadlockDetected, "40P01"),
    ],
)
def test_pg_retry_handles_psycopg3_failures_inside_real_transactions(tenant, failure_type, sqlstate):
    attempts = []

    def callback():
        attempts.append(True)
        if len(attempts) == 1:
            error = DatabaseError("representative PostgreSQL retry failure")
            error.__cause__ = failure_type()
            raise error
        return "committed"

    assert run_in_tenant(tenant.organisation.id, callback) == "committed"
    assert len(attempts) == 2
    assert sqlstate in {"40001", "40P01"}


def test_pg_retry_exhaustion_is_bounded_and_maps_to_canonical_failure(tenant):
    attempts = []

    def callback():
        attempts.append(True)
        error = DatabaseError("representative PostgreSQL deadlock")
        error.__cause__ = psycopg.errors.DeadlockDetected()
        raise error

    with pytest.raises(RetryableCommandFailure):
        run_in_tenant(tenant.organisation.id, callback)
    assert len(attempts) == 3


def test_pg_rls_is_enabled_for_every_tenant_table():
    status = rls_status()
    assert status["enforced"] is True
    assert status["role"]["superuser"] is False
    assert status["role"]["bypass_rls"] is False
    assert status["role"]["login"] is True
    assert all(table["rowsecurity"] and table["force"] for table in status["tables"])
    assert all(table["owner"] != status["role"]["name"] for table in status["tables"])
    assert all(table["tenant_policy"] for table in status["tables"])
    assert all(table["policy_command"] == "*" for table in status["tables"])
    assert all(table["policy_permissive"] is True for table in status["tables"])
    assert all(is_tenant_policy_expression(table["policy_using"]) for table in status["tables"])
    assert all(is_tenant_policy_expression(table["policy_check"]) for table in status["tables"])


def test_pg_missing_tenant_context_fails_closed():
    connection.close()
    with connection.cursor() as cursor:
        with pytest.raises(DatabaseError) as error:
            cursor.execute("SELECT 1 FROM core_idempotencyrecord LIMIT 1")
    cause = getattr(error.value, "__cause__", error.value)
    sqlstate = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
    assert sqlstate in {"42704", "22P02"}


def test_pg_policy_seam_is_tenant_scoped(tenant):
    with tenant_atomic(tenant.organisation.id):
        FacilityWorkflowPolicy.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            updated_by=tenant.user,
        )
    other_organisation = Organisation.objects.create(name="Other Clinic", slug="other-clinic")
    with tenant_atomic(other_organisation.id):
        other_facility = Facility.objects.create(
            organisation=other_organisation,
            name="Other Facility",
            code="OTHER",
        )
    with tenant_atomic(tenant.organisation.id):
        assert not FacilityWorkflowPolicy.objects.filter(facility=other_facility).exists()


def test_pg_cross_facility_read_and_write_are_denied_by_application_scope(tenant, authed_client):
    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="Unauthorised Facility",
            code="OTHER",
        )
        other_department = Department.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            name="Other Outpatient",
            code="OPD",
        )
        patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no="P-PG-FACILITY",
            first_name="Synthetic",
            last_name="Facility",
            sex="UNKNOWN",
        )
        other_queue = QueueEntry.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            patient=patient,
            department=other_department,
            queue_date=date.today(),
            sequence=1,
        )
        other_encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            patient=patient,
            queue_entry=None,
            encounter_no="ENC-PG-FACILITY",
            clinician=tenant.user,
        )

    headers = {"HTTP_X_FACILITY_ID": str(other_facility.id)}
    read = authed_client.get(f"/api/v1/clinic/encounters/{other_encounter.id}/", **headers)
    assert read.status_code == 403
    write = authed_client.post(
        "/api/v1/clinic/encounters/",
        {"queue_entry_id": str(other_queue.id)},
        format="json",
        **headers,
    )
    assert write.status_code == 403
    with tenant_atomic(tenant.organisation.id):
        assert not Encounter.objects.filter(queue_entry=other_queue).exists()


def test_pg_idempotency_replay_conflict_and_rollback_are_database_backed(tenant):
    callback_calls = 0

    def callback():
        nonlocal callback_calls
        callback_calls += 1
        return CommandResult(status_code=201, body={"reference": "pg-idempotent"})

    with tenant_atomic(tenant.organisation.id):
        first = execute_idempotent(
            organisation=tenant.organisation,
            operation="PG-S00-IDEMPOTENCY",
            key="pg-replay-key",
            fingerprint="a" * 64,
            callback=callback,
        )
    assert first.replay is False

    with tenant_atomic(tenant.organisation.id):
        replay = execute_idempotent(
            organisation=tenant.organisation,
            operation="PG-S00-IDEMPOTENCY",
            key="pg-replay-key",
            fingerprint="a" * 64,
            callback=lambda: pytest.fail("replay must not invoke the business callback"),
        )
    assert replay.replay is True
    assert callback_calls == 1

    with pytest.raises(IdempotencyConflict):
        with tenant_atomic(tenant.organisation.id):
            execute_idempotent(
                organisation=tenant.organisation,
                operation="PG-S00-IDEMPOTENCY",
                key="pg-replay-key",
                fingerprint="b" * 64,
                callback=callback,
            )

    with pytest.raises(UncommittedResponse):
        with tenant_atomic(tenant.organisation.id):
            execute_idempotent(
                organisation=tenant.organisation,
                operation="PG-S00-IDEMPOTENCY",
                key="pg-rollback-key",
                fingerprint="c" * 64,
                callback=lambda: CommandResult(status_code=400, body={"detail": "rollback"}),
            )
    with tenant_atomic(tenant.organisation.id):
        assert not IdempotencyRecord.objects.filter(
            organisation=tenant.organisation,
            operation="PG-S00-IDEMPOTENCY",
            key_hash=key_hash("pg-rollback-key"),
        ).exists()


def test_pg_idempotency_exactly_one_observable_callback_wins(tenant):
    barrier = Barrier(2)
    callback_lock = Lock()
    callback_calls = 0

    def counted_callback():
        nonlocal callback_calls
        with callback_lock:
            callback_calls += 1
        return CommandResult(status_code=201, body={"winner": True})

    def attempt():
        connections.close_all()
        try:
            with tenant_atomic(tenant.organisation.id):
                barrier.wait(timeout=10)
                outcome = execute_idempotent(
                    organisation=tenant.organisation,
                    operation="PG-S00-RACE",
                    key="pg-race-key",
                    fingerprint="d" * 64,
                    callback=counted_callback,
                )
                return outcome.replay
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: attempt(), range(2)))
    assert sorted(results) == [False, True]
    assert callback_calls == 1
    with tenant_atomic(tenant.organisation.id):
        assert IdempotencyRecord.objects.filter(
            organisation=tenant.organisation,
            operation="PG-S00-RACE",
        ).count() == 1


def test_pg_audit_durability_phi_filter_and_database_immutability(tenant):
    denial = write_denial_audit(
        organisation=tenant.organisation,
        actor_id=tenant.user.id,
        facility_id=tenant.facility.id,
        capability="patient.view",
        action="GET",
        blocker_type="PERMISSION",
        opaque_ref="pg-denial-proof",
        request_fingerprint="e" * 64,
    )
    with tenant_atomic(tenant.organisation.id):
        assert AuditEvent.objects.filter(pk=denial.pk).exists()
        with pytest.raises(ValueError):
            record_fact(
                organisation=tenant.organisation,
                actor=tenant.user,
                event_code="PG_PHI_BLOCK",
                entity_type="TechnicalProbe",
                entity_id="pg-phi-block",
                after={"patientName": "Alice Smith"},
            )
        event = record_event(
            organisation=tenant.organisation,
            actor=tenant.user,
            facility=tenant.facility,
            action="UPDATE",
            event_code="PG_SAFE_EVENT",
            entity_type="TechnicalProbe",
            entity_id="pg-safe-event",
            before={"patientName": "Alice Smith", "encounterId": "opaque-encounter"},
            after={
                "diagnosis": "Sensitive diagnosis",
                "patientId": "opaque-patient",
                "state": "READY",
            },
            source_ids={"patient_id": "Alice Smith", "safe_ref": "opaque-ref"},
            reason="Alice Smith wrote a clinical narrative",
        )
    assert event.before == {"encounterId": "opaque-encounter"}
    assert event.after == {"patientId": "opaque-patient", "state": "READY"}
    assert event.source_ids == {"safe_ref": "opaque-ref"}
    assert event.reason == ""

    with pytest.raises(DatabaseError):
        with tenant_atomic(tenant.organisation.id):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE audit_auditevent SET reason_code = reason_code WHERE id = %s",
                    [event.pk],
                )
    with pytest.raises(DatabaseError):
        with tenant_atomic(tenant.organisation.id):
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM audit_auditevent WHERE id = %s", [event.pk])
    with tenant_atomic(tenant.organisation.id):
        assert AuditEvent.objects.filter(pk=event.pk).exists()


def test_pg_patient_stale_if_match_is_rejected(tenant, authed_client):
    with tenant_atomic(tenant.organisation.id):
        patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no="P-PG-STALE",
            first_name="Before",
            last_name="Patient",
            sex="UNKNOWN",
        )
    initial = authed_client.get(f"/api/v1/patients/{patient.id}/")
    assert initial.status_code == 200
    stale_etag = initial["ETag"]
    with tenant_atomic(tenant.organisation.id):
        Patient.objects.filter(pk=patient.pk).update(first_name="Fresh")
    response = authed_client.patch(
        f"/api/v1/patients/{patient.id}/",
        {"last_name": "Rejected"},
        HTTP_IF_MATCH=stale_etag,
        format="json",
    )
    assert response.status_code == 412
    with tenant_atomic(tenant.organisation.id):
        patient.refresh_from_db()
        assert patient.first_name == "Fresh"
        assert patient.last_name == "Patient"
