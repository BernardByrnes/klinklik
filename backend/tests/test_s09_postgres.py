"""S-09 PostgreSQL inventory RLS, append-only guards and race proofs."""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection, transaction
from django.db.utils import DatabaseError

from accounts.models import User
from audit.models import AuditEvent
from core.errors import CanonicalError
from core.rls import rls_status
from core.services import tenant_atomic
from inventory.models import (
    BatchLocationBalance,
    StockBatch,
    StockLocation,
    StockMovement,
)
from inventory.services import adjust_stock, append_movement, receive_stock
from pharmacy.models import MedicationProduct, ProductPrice
from tenancy.models import Facility
from tests.test_s09_inventory import (
    _catalogue_csv,
    _catalogue_row,
    _facility_client,
)

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="S-09 PostgreSQL proof gate"),
]


def _catalogue(tenant, client):
    location = client.get("/api/v1/inventory/locations/").data[0]
    product = client.post(
        "/api/v1/inventory/products/",
        {
            "code": f"PG-{uuid4().hex[:8]}",
            "generic_name": "Synthetic PG Medicine",
            "dosage_form": "TABLET",
            "dispensing_unit": "TABLET",
            "category": "MEDICINE",
        },
        format="json",
    ).data
    client.post(
        "/api/v1/inventory/prices/",
        {
            "product_id": product["id"],
            "amount": "500.00",
            "effective_from": date.today().isoformat(),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"pg-price-{uuid4().hex}",
    )
    return product, location


def test_pg_s09_force_rls_and_append_only_guards(tenant, authed_client):
    product, location = _catalogue(tenant, authed_client)
    received = authed_client.post(
        "/api/v1/inventory/receipts/",
        {
            "receipt_no": f"PG-GRN-{uuid4().hex[:8]}",
            "lines": [
                {
                    "product_id": product["id"],
                    "location_id": location["id"],
                    "batch_no": "PG-BATCH",
                    "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
                    "quantity": "100.00",
                }
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"pg-grn-{uuid4().hex}",
    )
    assert received.status_code == 201, received.data
    status = rls_status()
    assert status["enforced"] is True
    tables = {table["name"]: table for table in status["tables"]}
    for name in (
        "inventory_stockmovement",
        "inventory_batchlocationbalance",
        "inventory_stockreceipt",
        "pharmacy_medicationproduct",
    ):
        assert tables[name]["rowsecurity"] is True
        assert tables[name]["force"] is True
        assert tables[name]["owner"] != status["role"]["name"]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tgname FROM pg_trigger
            WHERE tgrelid IN ('inventory_stockmovement'::regclass,
                              'inventory_batchlocationbalance'::regclass,
                              'pharmacy_productprice'::regclass)
              AND NOT tgisinternal AND tgenabled = 'O'
            """
        )
        triggers = {row[0] for row in cursor.fetchall()}
        assert {
            "klin_klink_stock_movement_immutable",
            "klin_klink_balance_guard",
            "klin_klink_product_price_immutable",
        } <= triggers
    with tenant_atomic(tenant.organisation.id):
        movement = StockMovement.objects.first()
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                StockMovement.objects.filter(id=movement.id).update(quantity=Decimal("1.00"))


def test_pg_s09_concurrent_receipts_serialize_the_balance(tenant, authed_client):
    product, location = _catalogue(tenant, authed_client)
    expiry = date.today() + timedelta(days=365)
    with tenant_atomic(tenant.organisation.id):
        organisation = tenant.organisation
        facility = tenant.facility
        actor = User.objects.get(id=tenant.user.id)
        med = MedicationProduct.objects.get(id=product["id"])
        loc = StockLocation.objects.get(id=location["id"])
    barrier = threading.Barrier(2)

    def receive(key):
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                receipt, movements = receive_stock(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    receipt_no=f"RACE-{key}",
                    lines=[
                        {
                            "product_id": med.id,
                            "location_id": loc.id,
                            "batch_no": "RACE-BATCH",
                            "expiry_date": expiry,
                            "quantity": "50.00",
                        }
                    ],
                    source_event_id=f"race-{key}",
                )
                return ("ok", str(receipt.id))
        except (CanonicalError, ValueError) as exc:
            return ("error", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(receive, (1, 2)))
    assert [result[0] for result in results] == ["ok", "ok"]
    with tenant_atomic(organisation.id):
        batch = StockBatch.objects.get(product=med, batch_no="RACE-BATCH")
        assert BatchLocationBalance.objects.get(batch=batch, location=loc).quantity == 100
        assert StockMovement.objects.filter(batch=batch).count() == 2


def test_pg_s09_concurrent_out_movements_cannot_oversell(tenant, authed_client):
    product, location = _catalogue(tenant, authed_client)
    expiry = date.today() + timedelta(days=365)
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
            receipt_no="RACE-OUT",
            lines=[
                {
                    "product_id": med.id,
                    "location_id": loc.id,
                    "batch_no": "RACE-OUT-BATCH",
                    "expiry_date": expiry,
                    "quantity": "100.00",
                }
            ],
            source_event_id="race-out",
        )
        batch = StockBatch.objects.get(product=med, batch_no="RACE-OUT-BATCH")
    barrier = threading.Barrier(2)

    def take(key):
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                movement = adjust_stock(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    batch_id=batch.id,
                    location_id=loc.id,
                    quantity="-80.00",
                    reason_code="BREAKAGE",
                    note=f"Race {key}",
                )
                return ("ok", str(movement.id))
        except (CanonicalError, ValueError) as exc:
            return ("error", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(take, (1, 2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    with tenant_atomic(organisation.id):
        assert BatchLocationBalance.objects.get(batch=batch, location=loc).quantity == 20
        assert StockMovement.objects.filter(
            batch=batch, movement_type="WRITE_OFF"
        ).count() == 1


def test_pg_s09_multi_line_receipt_and_quarantined_availability(tenant, authed_client):
    """S-09 PG: one multi-line receipt posts two movements; quarantine is excluded from usable stock."""

    product, location = _catalogue(tenant, authed_client)
    expiry = (date.today() + timedelta(days=120)).isoformat()
    posted = authed_client.post(
        "/api/v1/inventory/receipts/",
        {
            "receipt_no": f"PG-S32-{uuid4().hex[:6]}",
            "lines": [
                {
                    "product_id": product["id"],
                    "location_id": location["id"],
                    "batch_no": "PG-S32-A",
                    "expiry_date": expiry,
                    "quantity": "20.00",
                },
                {
                    "product_id": product["id"],
                    "location_id": location["id"],
                    "batch_no": "PG-S32-B",
                    "expiry_date": expiry,
                    "quantity": "30.00",
                },
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"pg-s32-receipt-{uuid4().hex}",
    )
    assert posted.status_code == 201, posted.data
    assert posted.data["movement_count"] == 2
    summary = authed_client.get("/api/v1/inventory/stock/")
    row = next(item for item in summary.data if item["product_id"] == product["id"])
    assert row["usable_quantity"] == "50.00"
    assert row["total_quantity"] == "50.00"


def test_pg_s41_catalogue_preview_writes_nothing_and_import_stays_scoped(
    tenant, authed_client
):
    status = rls_status()
    assert status["enforced"] is True
    assert status["role"]["bypass_rls"] is False

    content = _catalogue_csv(
        _catalogue_row("PGCAT1", pack_price="900.00"),
        _catalogue_row("PGCTRL1", controlled="true"),
    )
    preview = authed_client.post(
        "/api/v1/inventory/catalogue/import/preview/",
        {"content": content},
        format="json",
    )
    assert preview.status_code == 200, preview.data
    assert preview.data["valid_rows"] == 2
    with tenant_atomic(tenant.organisation.id):
        assert MedicationProduct.objects.count() == 0
        assert ProductPrice.objects.count() == 0
        assert StockMovement.objects.count() == 0
        assert AuditEvent.objects.filter(event_code="CATALOGUE_IMPORTED").count() == 0

    imported = authed_client.post(
        "/api/v1/inventory/catalogue/import/",
        {"content": content, "mode": "ALL_OR_NOTHING"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="pg-s41-catalogue-import",
    )
    assert imported.status_code == 201, imported.data
    assert imported.data["imported"] == 2
    with tenant_atomic(tenant.organisation.id):
        assert MedicationProduct.objects.filter(
            code__in=["PGCAT1", "PGCTRL1"]
        ).count() == 2
        assert MedicationProduct.objects.get(code="PGCTRL1").active is False
        assert ProductPrice.objects.count() == 2
        assert ProductPrice.objects.get(product__code="PGCAT1").pack_price == Decimal("900.00")
        assert StockMovement.objects.count() == 0
        assert AuditEvent.objects.filter(event_code="CATALOGUE_IMPORTED").count() == 1

    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="S41 PG Facility",
            code="S41-PG",
            mode="CLINIC",
        )
        MedicationProduct.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            code="PGOTHER1",
            generic_name="Synthetic PG Other",
            dosage_form="TABLET",
            dispensing_unit="TABLET",
            category="MEDICINE",
        )
    other_content = _catalogue_csv(_catalogue_row("PGOTHER1"))
    current = authed_client.post(
        "/api/v1/inventory/catalogue/import/preview/",
        {"content": other_content},
        format="json",
    )
    assert current.status_code == 200, current.data
    assert current.data["skipped"] == 0
    other_client = _facility_client(tenant, other_facility, "pg-s41-other-facility")
    scoped = other_client.post(
        "/api/v1/inventory/catalogue/import/preview/",
        {"content": other_content},
        format="json",
    )
    assert scoped.status_code == 200, scoped.data
    assert scoped.data["skipped"] == 1
    assert scoped.data["existing_codes"] == ["PGOTHER1"]
