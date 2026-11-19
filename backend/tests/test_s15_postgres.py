"""S-15 PostgreSQL fragment RLS, single-winner and link-constraint proofs."""

import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from django.db import DatabaseError, close_old_connections, connection

from accounts.models import User
from application.reception.commands import appointment_no_show_check_in
from audit.models import AuditEvent
from core.clock import local_service_date, now
from core.errors import CanonicalError
from core.rls import rls_status
from core.services import tenant_atomic
from scheduling.models import Appointment, Visit
from tests.test_s05_billing import register

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="S-15 PostgreSQL proof gate"
    ),
]


def _appointment(tenant, patient_id):
    with tenant_atomic(tenant.organisation.id):
        return Appointment.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient_id=patient_id,
            department=tenant.department,
            scheduled_start=now(),
            service_day=local_service_date(),
            status="NO_SHOW",
            created_by=tenant.user,
        )


def test_pg_s15_fragment_force_rls(tenant, authed_client, enabled_mig001_target):
    patient_id = register(authed_client, f"s15-pg-{uuid4().hex[:8]}")
    _appointment(tenant, patient_id)
    status = rls_status()
    tables = {table["name"]: table for table in status["tables"]}
    appointment = tables["scheduling_appointment"]
    assert appointment["rowsecurity"] is True
    assert appointment["force"] is True
    assert appointment["tenant_policy"] is True
    assert appointment["owner"] != status["role"]["name"]


def test_pg_s15_no_show_race_has_one_winner(
    tenant, authed_client, enabled_mig001_target
):
    patient_id = register(authed_client, f"s15-pg-race-{uuid4().hex[:8]}")
    appointment = _appointment(tenant, patient_id)
    organisation = tenant.organisation
    facility = tenant.facility
    actor_id = tenant.user.id
    barrier = threading.Barrier(2)

    def attempt(_index):
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                actor = User.objects.get(id=actor_id)
                outcome = appointment_no_show_check_in(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    appointment_id=appointment.id,
                )
                return ("ok", outcome.already_checked_in, str(outcome.visit.id))
        except CanonicalError as exc:
            return ("error", exc.code, None)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))
    assert all(result[0] == "ok" for result in results), results
    assert sorted(result[1] for result in results) == [False, True]
    assert len({result[2] for result in results}) == 1
    with tenant_atomic(organisation.id):
        assert Visit.objects.filter(patient_id=patient_id).count() == 1
        appointment = Appointment.objects.get(id=appointment.id)
        assert appointment.status == "CHECKED_IN"
        assert appointment.checked_in_visit_id is not None
        assert appointment.version == 2
        assert AuditEvent.objects.filter(
            event_code="APPOINTMENT_CHECKED_IN"
        ).count() == 1
        assert (
            AuditEvent.objects.filter(event_code="VISIT_OPENED").count() == 1
        )


def test_pg_s15_checked_in_visit_cannot_link_twice(
    tenant, authed_client, enabled_mig001_target
):
    patient_id = register(authed_client, f"s15-pg-link-{uuid4().hex[:8]}")
    first = _appointment(tenant, patient_id)
    second = _appointment(tenant, patient_id)
    with tenant_atomic(tenant.organisation.id):
        appointment = Appointment.objects.get(id=first.id)
        actor = User.objects.get(id=tenant.user.id)
        outcome = appointment_no_show_check_in(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=actor,
            appointment_id=appointment.id,
        )
        visit_id = outcome.visit.id
    with pytest.raises(DatabaseError):
        with tenant_atomic(tenant.organisation.id):
            Appointment.objects.filter(id=second.id).update(
                status="CHECKED_IN", checked_in_visit_id=visit_id
            )
