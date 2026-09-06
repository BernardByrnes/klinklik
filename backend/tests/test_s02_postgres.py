from datetime import date
from concurrent.futures import ThreadPoolExecutor
import threading
from uuid import uuid4

import pytest
from django.db import DatabaseError, IntegrityError, close_old_connections, connection, transaction

from core.rls import rls_status
from core.migration_reconciliation import backfill_mig002, cutover_mig002, inventory_mig002
from core.services import tenant_atomic
from core.models import MigrationCutover
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
    return MigrationCutover.objects.get(
        organisation=tenant.organisation,
        migration_id="MIG-002",
    )


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
    assert QueueEntry.objects.filter(
        organisation=tenant.organisation,
        facility=tenant.facility,
        visit_id=visit.id,
        department=tenant.department,
        work_identity="PG-S02-RACE-ACTIVE-PATH",
    ).count() == 1
