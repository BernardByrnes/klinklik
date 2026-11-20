"""S-11 PostgreSQL laboratory RLS, release and correction race proofs."""

import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection

from accounts.models import User
from audit.models import AuditEvent
from core.errors import CanonicalError
from core.rls import rls_status
from core.services import tenant_atomic
from laboratory.models import LabOrderItem, LabResultVersion
from laboratory.services import release_result
from tests.test_s05_billing import check_in, register

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="S-11 PostgreSQL proof gate"),
]


def _setup(tenant, client):
    patient_id = register(client, f"s11-pg-{uuid4().hex[:8]}")
    checked_in = check_in(client, patient_id, tenant, f"s11-pg-checkin-{uuid4().hex}")
    with tenant_atomic(tenant.organisation.id):
        from clinical.models import Encounter
        from scheduling.models import Visit

        visit = Visit.objects.get(id=checked_in["visit_id"])
        encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=visit.patient,
            visit=visit,
            clinician=tenant.user,
            encounter_no=f"ENC-PG-LAB-{uuid4().hex[:8]}",
            status="OPEN",
        )
    test = client.post(
        "/api/v1/lab/tests/",
        {
            "code": f"PG-{uuid4().hex[:6]}",
            "name": "Synthetic PG lab",
            "service_id": str(tenant.service.id),
            "result_type": "PANEL",
            "analytes": [
                {
                    "code": "HB",
                    "name": "Haemoglobin",
                    "unit": "g/dL",
                    "result_type": "NUMERIC",
                    "sanity_min": "0",
                    "sanity_max": "250",
                    "range": {"low": "4", "high": "11"},
                }
            ],
        },
        format="json",
    ).data
    ordered = client.post(
        "/api/v1/lab/orders/",
        {
            "encounter_id": str(encounter.id),
            "test_ids": [test["id"]],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s11-pg-order-{uuid4().hex}",
    )
    assert ordered.status_code == 201, ordered.data
    return ordered.data["items"][0]["id"], test


def test_pg_s11_force_rls_and_result_version_guards(tenant, authed_client, enabled_mig001_target):
    item_id, _test = _setup(tenant, authed_client)
    status = rls_status()
    tables = {table["name"]: table for table in status["tables"]}
    for name in (
        "laboratory_laborder",
        "laboratory_laborderitem",
        "laboratory_labresult",
        "laboratory_labresultversion",
        "laboratory_labtestdefinition",
    ):
        assert tables[name]["rowsecurity"] is True
        assert tables[name]["force"] is True
        assert tables[name]["owner"] != status["role"]["name"]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tgname FROM pg_trigger
            WHERE tgrelid = 'laboratory_labresultversion'::regclass
              AND NOT tgisinternal AND tgenabled = 'O'
            """
        )
        assert "klin_klink_lab_result_version_immutable" in {row[0] for row in cursor.fetchall()}


def test_pg_s11_concurrent_release_has_one_winner(tenant, authed_client, enabled_mig001_target):
    item_id, test = _setup(tenant, authed_client)
    authed_client.post(
        f"/api/v1/lab/items/{item_id}/collect/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY=f"s11-pg-collect-{uuid4().hex}",
    )
    from laboratory.models import LabAnalyteDefinition

    with tenant_atomic(tenant.organisation.id):
        analyte = LabAnalyteDefinition.objects.get(test_id=test["id"])
    saved = authed_client.patch(
        f"/api/v1/lab/items/{item_id}/results/",
        {
            "values": [{"analyte_id": str(analyte.id), "value": "10.0"}],
            "complete": True,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s11-pg-result-{uuid4().hex}",
    )
    assert saved.status_code == 201, saved.data
    with tenant_atomic(tenant.organisation.id):
        from accounts.models import OrganisationMembership, Role, UserFacilityRole

        verifier = User.objects.create_user(f"s11-pg-verifier-{uuid4().hex[:6]}", "test-password-123")
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=verifier)
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=verifier,
            role=Role.objects.get(organisation=tenant.organisation, template_code="OWNER_ADMIN"),
            facility=tenant.facility,
            department=tenant.department,
        )
        item = LabOrderItem.objects.get(id=item_id)
        organisation = tenant.organisation
        facility = tenant.facility
        actor = verifier
    barrier = threading.Barrier(2)

    def release():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                result, version = release_result(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    item_id=item.id,
                )
                return ("ok", version.version_no)
        except (CanonicalError, ValueError) as exc:
            return ("error", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: release(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    with tenant_atomic(organisation.id):
        assert LabOrderItem.objects.get(id=item_id).state == "RELEASED"
        assert LabResultVersion.objects.filter(result__item_id=item_id).count() == 1
        assert AuditEvent.objects.filter(event_code="LAB_RESULT_RELEASED").count() == 1


def test_pg_s30_detail_read_and_stale_release_conflict(
    tenant, authed_client, enabled_mig001_target
):
    """S-30 (PG): bounded draft read and version guard hold under the app role."""

    from laboratory.models import LabAnalyteDefinition
    from tests.test_s11_lab import _admin_client

    item_id, test = _setup(tenant, authed_client)
    collected = authed_client.post(
        f"/api/v1/lab/items/{item_id}/collect/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY=f"s30-pg-collect-{uuid4().hex}",
    )
    assert collected.status_code == 200, collected.data
    with tenant_atomic(tenant.organisation.id):
        analyte = LabAnalyteDefinition.objects.get(test_id=test["id"])
    first = authed_client.patch(
        f"/api/v1/lab/items/{item_id}/results/",
        {"values": [{"analyte_id": str(analyte.id), "value": "10.0"}], "complete": True},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s30-pg-result-1-{uuid4().hex}",
    )
    assert first.status_code == 201, first.data
    observed = first.data["version_no"]

    verifier, _ = _admin_client(tenant)
    detail = verifier.get(f"/api/v1/lab/items/{item_id}/detail/")
    assert detail.status_code == 200, detail.data
    assert detail.data["version_no"] == observed
    assert any(value["value"] == "10.0" for value in detail.data["values"])

    second = authed_client.patch(
        f"/api/v1/lab/items/{item_id}/results/",
        {"values": [{"analyte_id": str(analyte.id), "value": "11.0"}], "complete": True},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s30-pg-result-2-{uuid4().hex}",
    )
    assert second.status_code == 201, second.data
    stale = verifier.post(
        f"/api/v1/lab/items/{item_id}/release/",
        {"expected_version": observed},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s30-pg-stale-{uuid4().hex}",
    )
    assert stale.status_code == 412, stale.data
    current = verifier.post(
        f"/api/v1/lab/items/{item_id}/release/",
        {"expected_version": observed + 1},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s30-pg-current-{uuid4().hex}",
    )
    assert current.status_code == 200, current.data
    with tenant_atomic(tenant.organisation.id):
        assert LabOrderItem.objects.get(id=item_id).state == "RELEASED"
        assert AuditEvent.objects.filter(event_code="LAB_RESULT_RELEASED").count() == 1
        for event in AuditEvent.objects.filter(event_code="LAB_RESULTS_READ"):
            assert "10.0" not in str(event.after)
