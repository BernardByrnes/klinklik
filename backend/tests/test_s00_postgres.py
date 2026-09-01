from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connection, connections

from core.idempotency import execute_idempotent
from core.models import IdempotencyRecord
from core.rls import rls_status
from core.services import tenant_atomic
from application.contracts import CommandResult
from tenancy.models import FacilityWorkflowPolicy, Organisation


pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="PostgreSQL proof gate"),
]


def test_pg_rls_is_enabled_for_every_tenant_table():
    status = rls_status()
    assert status["enforced"] is True
    assert status["role"]["superuser"] is False
    assert status["role"]["bypass_rls"] is False
    assert all(table["rowsecurity"] and table["force"] for table in status["tables"])
    assert all(table["owner"] != status["role"]["name"] for table in status["tables"])
    assert all("current_setting" in table["policy_using"] for table in status["tables"])
    assert all("current_setting" in table["policy_check"] for table in status["tables"])


def test_pg_missing_tenant_context_fails_closed():
    connection.close()
    with connection.cursor() as cursor:
        with pytest.raises(Exception) as error:
            cursor.execute("SELECT 1 FROM core_idempotencyrecord LIMIT 1")
    cause = getattr(error.value, "__cause__", error.value)
    assert getattr(cause, "pgcode", None) in {"42704", "22P02"}


def test_pg_policy_seam_is_tenant_scoped(tenant):
    with tenant_atomic(tenant.organisation.id):
        FacilityWorkflowPolicy.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            updated_by=tenant.user,
        )
    other_organisation = Organisation.objects.create(name="Other Clinic", slug="other-clinic")
    with tenant_atomic(other_organisation.id):
        from tenancy.models import Facility

        other_facility = Facility.objects.create(
            organisation=other_organisation,
            name="Other Facility",
            code="OTHER",
        )
    with tenant_atomic(tenant.organisation.id):
        assert not FacilityWorkflowPolicy.objects.filter(facility=other_facility).exists()


def test_pg_idempotency_first_use_has_one_winner(tenant):
    barrier = Barrier(2)

    def attempt():
        connections.close_all()
        try:
            with tenant_atomic(tenant.organisation.id):
                barrier.wait(timeout=10)
                result = execute_idempotent(
                    organisation=tenant.organisation.id,
                    operation="CMD-001",
                    key="pg-race-key",
                    fingerprint="a" * 64,
                    callback=lambda: CommandResult(status_code=201, body={"winner": True}),
                )
                return result.replay
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: attempt(), range(2)))
    assert sorted(results) == [False, True]
    assert IdempotencyRecord.objects.filter(
        organisation=tenant.organisation,
        operation="CMD-001",
    ).count() == 1
