"""S-09 inventory foundations: receiving, ledger, FEFO, import and alerts."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from audit.models import AuditEvent
from core.services import tenant_atomic
from inventory.models import (
    BatchLocationBalance,
    StockBatch,
    StockLocation,
    StockMovement,
    StockReceipt,
)
from inventory.services import append_movement
from pharmacy.models import MedicationProduct, ProductPrice
from tenancy.models import FacilityWorkflowPolicy

pytestmark = pytest.mark.django_db

TODAY = date.today()


def _threshold(tenant, value="1000000.00"):
    with tenant_atomic(tenant.organisation.id):
        FacilityWorkflowPolicy.objects.update_or_create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            defaults={
                "stock_adjustment_approval_threshold": Decimal(value),
                "updated_by": tenant.user,
            },
        )


def _locations(client):
    response = client.get("/api/v1/inventory/locations/")
    assert response.status_code == 200, response.data
    return response.data


def _product(client, code=None, **overrides):
    payload = {
        "code": code or f"P-{uuid4().hex[:8]}",
        "generic_name": "Synthetic Paracetamol",
        "dosage_form": "TABLET",
        "dispensing_unit": "TABLET",
        "strength": "500 mg",
        "category": "MEDICINE",
    }
    payload.update(overrides)
    response = client.post("/api/v1/inventory/products/", payload, format="json")
    assert response.status_code == 201, response.data
    return response.data


def _receive(client, product_id, location_id, quantity="100.00", expiry=None, key=None):
    expiry = expiry or (TODAY + timedelta(days=365))
    return client.post(
        "/api/v1/inventory/receipts/",
        {
            "receipt_no": f"GRN-{uuid4().hex[:8]}",
            "lines": [
                {
                    "product_id": product_id,
                    "location_id": location_id,
                    "batch_no": f"B-{uuid4().hex[:8]}",
                    "expiry_date": expiry.isoformat(),
                    "quantity": quantity,
                    "unit_cost": "100.00",
                }
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key or f"grn-{uuid4().hex}",
    )


def test_s09_receive_creates_exact_ledger_and_idempotent_receipt(tenant, authed_client):
    location = _locations(authed_client)[0]
    product = _product(authed_client)
    price = authed_client.post(
        "/api/v1/inventory/prices/",
        {
            "product_id": product["id"],
            "amount": "500.00",
            "effective_from": TODAY.isoformat(),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s09-price",
    )
    assert price.status_code == 201, price.data

    received = _receive(
        authed_client,
        product["id"],
        location["id"],
        expiry=TODAY + timedelta(days=30),
        key="s09-receipt",
    )
    assert received.status_code == 201, received.data
    assert received.data["warning_near_expiry"] is True
    with tenant_atomic(tenant.organisation.id):
        receipt_no = StockReceipt.objects.get().receipt_no
        batch_no = StockBatch.objects.get().batch_no
    replay = authed_client.post(
        "/api/v1/inventory/receipts/",
        {
            "receipt_no": receipt_no,
            "lines": [
                {
                    "product_id": product["id"],
                    "location_id": location["id"],
                    "batch_no": batch_no,
                    "expiry_date": (TODAY + timedelta(days=30)).isoformat(),
                    "quantity": "100.00",
                    "unit_cost": "100.00",
                }
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s09-receipt",
    )
    assert replay.status_code == 201
    assert replay.headers["Idempotent-Replay"] == "true"

    stock = authed_client.get("/api/v1/inventory/stock/")
    assert stock.status_code == 200
    row = next(item for item in stock.data if item["product_id"] == product["id"])
    assert row["usable_quantity"] == "100.00"
    assert row["status"] == "EXPIRING_SOON"
    assert row["batch_count"] == 1

    movements = authed_client.get("/api/v1/inventory/movements/")
    assert movements.status_code == 200
    assert len(movements.data) == 1
    assert movements.data[0]["movement_type"] == "IN_GRN"
    batches = authed_client.get("/api/v1/inventory/batches/")
    assert batches.status_code == 200
    assert batches.data[0]["batch_no"]
    assert batches.data[0]["locations"][0]["quantity"] == "100.00"
    with tenant_atomic(tenant.organisation.id):
        assert StockReceipt.objects.count() == 1
        assert StockMovement.objects.count() == 1
        assert BatchLocationBalance.objects.get(product_id=product["id"]).quantity == Decimal("100.00")
        assert AuditEvent.objects.filter(event_code="STOCK_RECEIVED").count() == 1
        assert AuditEvent.objects.filter(event_code="MEDICATION_PRODUCT_CREATED").count() == 1


def test_s09_expired_receipt_is_refused_without_partial_records(tenant, authed_client):
    location = _locations(authed_client)[0]
    product = _product(authed_client)
    response = _receive(
        authed_client,
        product["id"],
        location["id"],
        expiry=TODAY - timedelta(days=1),
    )
    assert response.status_code == 422
    assert response.data["code"] == "EXPIRED_STOCK_CANNOT_BE_RECEIVED"
    with tenant_atomic(tenant.organisation.id):
        assert StockReceipt.objects.count() == 0
        assert StockMovement.objects.count() == 0
        assert StockBatch.objects.count() == 0


def test_s09_fefo_selects_earliest_and_splits_without_expired(tenant, authed_client):
    location = _locations(authed_client)[0]
    product = _product(authed_client)
    first = _receive(
        authed_client, product["id"], location["id"], quantity="30.00",
        expiry=TODAY + timedelta(days=60),
    )
    second = _receive(
        authed_client, product["id"], location["id"], quantity="80.00",
        expiry=TODAY + timedelta(days=120),
    )
    assert first.status_code == 201 and second.status_code == 201
    with tenant_atomic(tenant.organisation.id):
        expired_batch = StockBatch.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            product_id=product["id"],
            batch_no="EXPIRED-BATCH",
            expiry_date=TODAY - timedelta(days=1),
        )
        BatchLocationBalance.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            product_id=product["id"],
            batch=expired_batch,
            location_id=location["id"],
            quantity=Decimal("50.00"),
        )
    selected = authed_client.post(
        "/api/v1/inventory/fefo/",
        {"product_id": product["id"], "quantity": "40.00"},
        format="json",
    )
    assert selected.status_code == 200, selected.data
    proposals = selected.data["proposals"]
    assert len(proposals) == 2
    assert proposals[0]["quantity"] == "30.00"
    assert proposals[1]["quantity"] == "10.00"
    assert all(item["batch_id"] != str(expired_batch.id) for item in proposals)


def test_s09_transfer_and_expired_quarantine_rules(tenant, authed_client):
    locations = _locations(authed_client)
    assert locations[0]["is_default"] is True
    quarantine = authed_client.post(
        "/api/v1/inventory/locations/",
        {"code": "QUAR", "name": "Quarantine", "location_type": "QUARANTINE"},
        format="json",
    )
    assert quarantine.status_code == 201, quarantine.data
    destination = authed_client.post(
        "/api/v1/inventory/locations/",
        {"code": "DISP", "name": "Dispensary", "location_type": "DISPENSARY"},
        format="json",
    )
    assert destination.status_code == 201
    product = _product(authed_client)
    received = _receive(authed_client, product["id"], locations[0]["id"])
    assert received.status_code == 201
    with tenant_atomic(tenant.organisation.id):
        batch = StockBatch.objects.get(product_id=product["id"])
        batch_id = str(batch.id)
    transfer = authed_client.post(
        "/api/v1/inventory/transfers/",
        {
            "batch_id": batch_id,
            "from_location_id": locations[0]["id"],
            "to_location_id": destination.data["id"],
            "quantity": "20.00",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s09-transfer",
    )
    assert transfer.status_code == 201, transfer.data
    with tenant_atomic(tenant.organisation.id):
        assert BatchLocationBalance.objects.get(
            batch_id=batch_id, location_id=destination.data["id"]
        ).quantity == Decimal("20.00")
        assert BatchLocationBalance.objects.get(
            batch_id=batch_id, location_id=locations[0]["id"]
        ).quantity == Decimal("80.00")
        assert AuditEvent.objects.filter(event_code="STOCK_TRANSFERRED").count() == 1
        batch.expiry_date = TODAY - timedelta(days=1)
        batch.save(update_fields=["expiry_date"])
    refused = authed_client.post(
        "/api/v1/inventory/transfers/",
        {
            "batch_id": batch_id,
            "from_location_id": locations[0]["id"],
            "to_location_id": destination.data["id"],
            "quantity": "5.00",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s09-transfer-expired",
    )
    assert refused.status_code == 422
    assert refused.data["code"] == "EXPIRED_BATCH"
    quarantined = authed_client.post(
        "/api/v1/inventory/transfers/",
        {
            "batch_id": batch_id,
            "from_location_id": locations[0]["id"],
            "to_location_id": quarantine.data["id"],
            "quantity": "10.00",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s09-transfer-quarantine",
    )
    assert quarantined.status_code == 201, quarantined.data


def test_s09_adjustment_reconcile_and_threshold(tenant, authed_client):
    _threshold(tenant)
    location = _locations(authed_client)[0]
    product = _product(authed_client)
    _receive(authed_client, product["id"], location["id"], quantity="100.00")
    with tenant_atomic(tenant.organisation.id):
        batch = StockBatch.objects.get(product_id=product["id"])
        batch_id = str(batch.id)
    adjusted = authed_client.post(
        "/api/v1/inventory/adjustments/",
        {
            "batch_id": batch_id,
            "location_id": location["id"],
            "quantity": "-5.00",
            "reason_code": "DAMAGE",
            "note": "Synthetic breakage",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s09-adjust",
    )
    assert adjusted.status_code == 201, adjusted.data
    threshold = authed_client.post(
        "/api/v1/inventory/thresholds/",
        {"product_id": product["id"], "reorder_level": "95.00"},
        format="json",
    )
    assert threshold.status_code == 201, threshold.data
    stock = authed_client.get("/api/v1/inventory/stock/")
    row = next(item for item in stock.data if item["product_id"] == product["id"])
    assert row["usable_quantity"] == "95.00"
    assert row["status"] == "LOW"
    with tenant_atomic(tenant.organisation.id):
        assert AuditEvent.objects.filter(event_code="STOCK_ADJUSTED").count() == 1

    passed = authed_client.post(
        "/api/v1/inventory/reconcile/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY="s09-reconcile-ok",
    )
    assert passed.status_code == 200, passed.data
    assert passed.data["event_code"] == "STOCK_LEDGER_RECONCILIATION_PASSED"
    with tenant_atomic(tenant.organisation.id):
        balance = BatchLocationBalance.objects.get(batch_id=batch_id)
        balance.quantity = Decimal("99.00")
        balance.version += 1
        balance.save(update_fields=["quantity", "version", "updated_at"])
    discrepancy = authed_client.post(
        "/api/v1/inventory/reconcile/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY="s09-reconcile-bad",
    )
    assert discrepancy.status_code == 200
    assert discrepancy.data["event_code"] == "STOCK_LEDGER_DISCREPANCY_DETECTED"
    assert discrepancy.data["discrepancy_count"] == 1
    with tenant_atomic(tenant.organisation.id):
        assert BatchLocationBalance.objects.get(batch_id=batch_id).quantity == Decimal("99.00")


def test_s09_catalogue_import_is_atomic_and_controlled_rows_are_inactive(
    tenant, authed_client
):
    header = "code,generic_name,dosage_form,dispensing_unit,category,strength,controlled,price,effective_from\n"
    bad = header + "BAD1,,TABLET,TABLET,MEDICINE,500 mg,false,100,2026-01-01\n"
    refused = authed_client.post(
        "/api/v1/inventory/catalogue/import/",
        {"content": bad, "mode": "ALL_OR_NOTHING"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s09-import-bad",
    )
    assert refused.status_code == 400
    assert refused.data["row_errors"][0]["line"] == 2
    with tenant_atomic(tenant.organisation.id):
        assert MedicationProduct.objects.count() == 0

    good = header + (
        "GOOD1,Synthetic Amoxicillin,CAPSULE,CAPSULE,MEDICINE,250 mg,false,300,2026-01-01\n"
        "CTRL1,Synthetic Controlled,TABLET,TABLET,MEDICINE,10 mg,true,500,2026-01-01\n"
    )
    imported = authed_client.post(
        "/api/v1/inventory/catalogue/import/",
        {"content": good, "mode": "ALL_OR_NOTHING"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s09-import-good",
    )
    assert imported.status_code == 201, imported.data
    assert imported.data["imported"] == 2
    with tenant_atomic(tenant.organisation.id):
        controlled = MedicationProduct.objects.get(code="CTRL1")
        assert controlled.controlled is True
        assert controlled.active is False
        assert ProductPrice.objects.filter(product__code="GOOD1").count() == 1
        assert AuditEvent.objects.filter(event_code="CATALOGUE_IMPORTED").count() == 1


def test_s09_product_deactivation_requires_zero_stock(tenant, authed_client):
    _threshold(tenant)
    location = _locations(authed_client)[0]
    product = _product(authed_client)
    _receive(authed_client, product["id"], location["id"], quantity="10.00")
    with tenant_atomic(tenant.organisation.id):
        version = MedicationProduct.objects.get(id=product["id"]).version
    blocked = authed_client.post(
        f"/api/v1/inventory/products/{product['id']}/deactivate/",
        {"reason": "Synthetic withdrawal", "expected_version": version},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s09-deactivate-blocked",
    )
    assert blocked.status_code == 409
    assert blocked.data["code"] == "STOCK_ON_HAND"
    with tenant_atomic(tenant.organisation.id):
        batch = StockBatch.objects.get(product_id=product["id"])
        batch_id = str(batch.id)
        version = MedicationProduct.objects.get(id=product["id"]).version
    out = authed_client.post(
        "/api/v1/inventory/adjustments/",
        {
            "batch_id": batch_id,
            "location_id": location["id"],
            "quantity": "-10.00",
            "reason_code": "EXPIRY_DISPOSAL",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s09-empty",
    )
    assert out.status_code == 201
    deactivated = authed_client.post(
        f"/api/v1/inventory/products/{product['id']}/deactivate/",
        {"reason": "Synthetic withdrawal", "expected_version": version},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s09-deactivate",
    )
    assert deactivated.status_code == 200, deactivated.data
    search = authed_client.get("/api/v1/inventory/products/?q=Synthetic")
    assert all(item["id"] != product["id"] for item in search.data)


def test_s09_expired_positive_movement_never_increases_usable_stock(tenant, authed_client):
    location = _locations(authed_client)[0]
    product = _product(authed_client)
    with tenant_atomic(tenant.organisation.id):
        batch = StockBatch.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            product_id=product["id"],
            batch_no="OLD",
            expiry_date=TODAY - timedelta(days=1),
        )
        with pytest.raises(Exception) as refused:
            append_movement(
                organisation=tenant.organisation,
                facility=tenant.facility,
                actor=tenant.user,
                product=MedicationProduct.objects.get(id=product["id"]),
                batch=batch,
                location=StockLocation.objects.get(id=location["id"]),
                movement_type="ADJUSTMENT",
                quantity="5.00",
                source_type="Test",
                source_id="expired-positive",
            )
        assert refused.value.code == "EXPIRED_BATCH"
