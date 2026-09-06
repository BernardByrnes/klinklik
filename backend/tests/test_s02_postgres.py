from datetime import date
from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, transaction

from core.rls import rls_status
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import QueueEntry, Visit
from tenancy.models import Department, Facility, Organisation


pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="S-02 PostgreSQL proof gate"),
]


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
