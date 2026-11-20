"""S-10 PostgreSQL count approval, adjustment and quarantine race proofs."""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection

from accounts.models import User
from core.errors import CanonicalError
from core.rls import rls_status
from core.services import tenant_atomic
from inventory.counts import (
    approve_count,
    create_adjustment,
    open_count,
    quarantine_stock,
    submit_count,
)
from inventory.models import (
    BatchLocationBalance,
    StockAdjustment,
    StockBatch,
    StockCount,
    StockLocation,
)
from inventory.services import receive_stock
from pharmacy.models import MedicationProduct
from tenancy.models import FacilityWorkflowPolicy
from tests.test_s09_postgres import _catalogue

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="S-10 PostgreSQL proof gate"),
]


def _setup(tenant, client, quantity="100.00"):
    product, location = _catalogue(tenant, client)
    with tenant_atomic(tenant.organisation.id):
        organisation = tenant.organisation
        facility = tenant.facility
        actor = User.objects.get(id=tenant.user.id)
        med = MedicationProduct.objects.get(id=product["id"])
        loc = StockLocation.objects.get(id=location["id"])
        receipt, _movements = receive_stock(
            organisation=organisation,
            facility=facility,
            actor=actor,
            receipt_no=f"S10-{uuid4().hex[:8]}",
            lines=[
                {
                    "product_id": med.id,
                    "location_id": loc.id,
                    "batch_no": "S10-BATCH",
                    "expiry_date": date.today() + timedelta(days=365),
                    "quantity": quantity,
                }
            ],
            source_event_id=f"S10-{uuid4().hex}",
        )
        FacilityWorkflowPolicy.objects.update_or_create(
            organisation=organisation,
            facility=facility,
            defaults={
                "stock_adjustment_approval_threshold": Decimal("1000000.00"),
                "updated_by": actor,
            },
        )
        batch = StockBatch.objects.get(product=med, batch_no="S10-BATCH")
    return organisation, facility, actor, med, loc, batch


def test_pg_s10_count_tables_force_rls_and_count_immutability(tenant, authed_client):
    organisation, facility, actor, med, loc, batch = _setup(tenant, authed_client)
    with tenant_atomic(organisation.id):
        count = open_count(
            organisation=organisation, facility=facility, actor=actor, location_id=loc.id
        )
        submit_count(
            organisation=organisation,
            facility=facility,
            actor=actor,
            count_id=count.id,
            expected_version=count.version,
            line_counts=[
                {"line_id": count.lines.first().id, "counted_qty": "100.00"}
            ],
        )
        approve_count(
            organisation=organisation,
            facility=facility,
            actor=actor,
            count_id=count.id,
            expected_version=StockCount.objects.get(id=count.id).version,
            approver_is_facility_admin=True,
        )
    status = rls_status()
    tables = {table["name"]: table for table in status["tables"]}
    for name in (
        "inventory_stockcount",
        "inventory_stockcountline",
        "inventory_stockadjustment",
        "inventory_quarantinerecord",
        "inventory_disposalrecord",
    ):
        assert tables[name]["rowsecurity"] is True
        assert tables[name]["force"] is True
        assert tables[name]["owner"] != status["role"]["name"]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tgname FROM pg_trigger
            WHERE tgrelid IN ('inventory_stockcount'::regclass,
                              'inventory_stockcountline'::regclass,
                              'inventory_stockadjustment'::regclass,
                              'inventory_quarantinerecord'::regclass,
                              'inventory_disposalrecord'::regclass)
              AND NOT tgisinternal AND tgenabled = 'O'
            """
        )
        triggers = {row[0] for row in cursor.fetchall()}
        assert {
            "klin_klink_count_evidence_immutable",
            "klin_klink_count_line_immutable",
            "klin_klink_adjustment_immutable",
            "klin_klink_quarantine_immutable",
            "klin_klink_disposal_immutable",
        } <= triggers


def test_pg_s10_concurrent_count_approval_has_one_winner(tenant, authed_client):
    organisation, facility, actor, med, loc, batch = _setup(tenant, authed_client)
    with tenant_atomic(organisation.id):
        count = open_count(
            organisation=organisation, facility=facility, actor=actor, location_id=loc.id
        )
        line_id = count.lines.first().id
        count = submit_count(
            organisation=organisation,
            facility=facility,
            actor=actor,
            count_id=count.id,
            expected_version=count.version,
            line_counts=[{"line_id": line_id, "counted_qty": "95.00"}],
        )
        count_id = count.id
        version = count.version
    barrier = threading.Barrier(2)

    def approve():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                approved, adjustments = approve_count(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    count_id=count_id,
                    expected_version=version,
                    approver_is_facility_admin=True,
                )
                return ("ok", len(adjustments))
        except (CanonicalError, ValueError) as exc:
            return ("error", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: approve(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    with tenant_atomic(organisation.id):
        assert StockCount.objects.get(id=count_id).state == "POSTED"
        assert StockAdjustment.objects.filter(count_id=count_id).count() == 1
        assert BatchLocationBalance.objects.get(batch=batch, location=loc).quantity == 95


def test_pg_s10_adjustment_and_quarantine_races_cannot_oversell(tenant, authed_client):
    organisation, facility, actor, med, loc, batch = _setup(tenant, authed_client)
    barrier = threading.Barrier(2)

    def adjust():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                adjustment = create_adjustment(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    batch_id=batch.id,
                    location_id=loc.id,
                    quantity="-80.00",
                    reason_code="BREAKAGE",
                )
                return ("ok", adjustment.state)
        except (CanonicalError, ValueError) as exc:
            return ("error", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: adjust(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    with tenant_atomic(organisation.id):
        assert BatchLocationBalance.objects.get(batch=batch, location=loc).quantity == 20

    with tenant_atomic(organisation.id):
        quarantine = StockLocation.objects.create(
            organisation=organisation,
            facility=facility,
            code=f"QUAR-{uuid4().hex[:6]}",
            name="Quarantine",
            location_type="QUARANTINE",
            is_quarantine=True,
        )
    barrier = threading.Barrier(2)

    def quarantine_attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                record = quarantine_stock(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    batch_id=batch.id,
                    location_id=loc.id,
                    quantity="15.00",
                    reason="Synthetic quarantine race",
                )
                return ("ok", str(record.id))
        except (CanonicalError, ValueError) as exc:
            return ("error", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: quarantine_attempt(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    with tenant_atomic(organisation.id):
        assert BatchLocationBalance.objects.get(batch=batch, location=loc).quantity == 5
        assert BatchLocationBalance.objects.get(batch=batch, location=quarantine).quantity == 15


def test_pg_s10_count_list_and_movements_during_count(tenant, authed_client):
    """S-10 PG: submitted counts are discoverable and D-04 movements are projected."""

    organisation, facility, actor, med, loc, _batch = _setup(tenant, authed_client)
    with tenant_atomic(organisation.id):
        count = open_count(
            organisation=organisation,
            facility=facility,
            actor=actor,
            location_id=loc.id,
        )
    lines = count.lines.all()
    with tenant_atomic(organisation.id):
        submit_count(
            organisation=organisation,
            facility=facility,
            actor=actor,
            count_id=count.id,
            expected_version=count.version,
            line_counts=[
                {"line_id": line.id, "counted_qty": "95.00"} for line in lines
            ],
        )
    listing = authed_client.get("/api/v1/inventory/counts/")
    assert listing.status_code == 200, listing.data
    row = next(item for item in listing.data["counts"] if item["id"] == str(count.id))
    assert row["state"] == "SUBMITTED"
    assert "expected_qty" not in row
    detail = authed_client.get(f"/api/v1/inventory/counts/{count.id}/?reveal=1")
    assert detail.status_code == 200, detail.data
    assert detail.data["lines"][0]["variance_qty"] == "-5.00"
    assert "movements_during_count" in detail.data
