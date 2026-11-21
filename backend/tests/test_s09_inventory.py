"""S-09 inventory foundations: receiving, ledger, FEFO, import and alerts."""

import time
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from accounts.services import ensure_default_permissions
from application.catalogue.imports import (
    CATALOGUE_HEADER,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    validate_catalogue_csv,
)
from audit.models import AuditEvent
from core.errors import CanonicalError
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
from tenancy.models import Department, Facility, FacilityWorkflowPolicy, Organisation

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
    # CMD-089 — mechanical evidence for s17-cmd-audit.
    # CMD-063 — mechanical evidence for s17-cmd-audit.
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
    # CMD-104 — mechanical evidence for s17-cmd-audit.
    # CMD-064 — mechanical evidence for s17-cmd-audit.
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
    # CMD-111 — mechanical evidence for s17-cmd-audit.
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


CATALOGUE_COLUMNS = sorted(REQUIRED_COLUMNS) + sorted(OPTIONAL_COLUMNS)
CATALOGUE_HEADER_LINE = CATALOGUE_HEADER + "\n"


def _catalogue_csv(*rows):
    lines = [CATALOGUE_HEADER_LINE]
    for row in rows:
        lines.append(",".join(str(row.get(column, "")) for column in CATALOGUE_COLUMNS) + "\n")
    return "".join(lines)


def _with_extra_column(content):
    lines = content.rstrip("\n").split("\n")
    lines[-1] += ",EXTRA"
    return "\n".join(lines) + "\n"


def _catalogue_row(code, **overrides):
    row = {
        "code": code,
        "generic_name": f"Synthetic {code}",
        "dosage_form": "TABLET",
        "dispensing_unit": "TABLET",
        "category": "MEDICINE",
        "price": "100.00",
        "effective_from": "2026-01-01",
    }
    row.update(overrides)
    return row


def _facility_client(tenant, facility, username, template="OWNER_ADMIN"):
    with tenant_atomic(tenant.organisation.id):
        user = User.objects.create_user(username, "test-password-123")
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=user)
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=user,
            role=Role.objects.get(organisation=tenant.organisation, template_code=template),
            facility=facility,
        )
    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {
            "username": username,
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    assert login.status_code == 200, login.data
    client.defaults["HTTP_X_FACILITY_ID"] = str(facility.id)
    client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    return client


def test_s41_ui_template_header_matches_owner_columns():
    expected = (
        "category,code,dispensing_unit,dosage_form,generic_name,active,brand_name,"
        "controlled,currency,effective_from,pack_description,pack_price,"
        "prescription_only,price,strength"
    )
    assert CATALOGUE_HEADER == expected
    assert set(CATALOGUE_HEADER.split(",")) == REQUIRED_COLUMNS | OPTIONAL_COLUMNS


def test_s41_service_oversized_csv_field_is_a_typed_input_error():
    with pytest.raises(CanonicalError) as failure:
        validate_catalogue_csv("a" * 200000)
    assert failure.value.code == "INVALID_INPUT"
    assert failure.value.status_code == 400
    assert "a" * 200000 not in str(failure.value)


def test_s41_large_header_validation_is_linear():
    duplicate_header = ",".join([""] * 64000) + "\n"
    started = time.monotonic()
    with pytest.raises(CanonicalError) as duplicate:
        validate_catalogue_csv(duplicate_header)
    duplicate_elapsed = time.monotonic() - started
    assert duplicate_elapsed < 2, duplicate_elapsed
    assert duplicate.value.code == "INVALID_INPUT"
    assert "duplicate_headers" in duplicate.value.metadata

    unknown_header = ",".join(f"c{index}" for index in range(64000)) + "\n"
    started = time.monotonic()
    with pytest.raises(CanonicalError) as unknown:
        validate_catalogue_csv(unknown_header)
    unknown_elapsed = time.monotonic() - started
    assert unknown_elapsed < 2, unknown_elapsed
    assert unknown.value.code == "INVALID_INPUT"
    assert "unknown_columns" in unknown.value.metadata


def test_s41_preview_and_commit_oversized_field_return_400(tenant, authed_client):
    original_raise = authed_client.raise_request_exception
    authed_client.raise_request_exception = False
    try:
        preview = authed_client.post(
            "/api/v1/inventory/catalogue/import/preview/",
            {"content": "a" * 200000},
            format="json",
        )
        assert preview.status_code == 400, preview.data
        assert preview.data["code"] == "INVALID_INPUT"
        assert "a" * 200000 not in str(preview.data)

        commit = authed_client.post(
            "/api/v1/inventory/catalogue/import/",
            {"content": "a" * 200000, "mode": "ALL_OR_NOTHING"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="s41-oversized-field",
        )
        assert commit.status_code == 400, commit.data
        assert commit.data["code"] == "INVALID_INPUT"
        assert "a" * 200000 not in str(commit.data)
    finally:
        authed_client.raise_request_exception = original_raise
    with tenant_atomic(tenant.organisation.id):
        assert MedicationProduct.objects.count() == 0
        assert AuditEvent.objects.filter(event_code="CATALOGUE_IMPORTED").count() == 0


def test_s41_service_parser_rejects_structural_and_value_gaps():
    duplicate_header = CATALOGUE_HEADER.replace("code,", "code,code,", 1)
    with pytest.raises(CanonicalError) as duplicate:
        validate_catalogue_csv(duplicate_header)
    assert duplicate.value.code == "INVALID_INPUT"
    assert "duplicate_headers" in duplicate.value.metadata

    wide = _with_extra_column(_catalogue_csv(_catalogue_row("WIDE1")))
    rows, errors, _digest = validate_catalogue_csv(wide)
    assert rows == []
    assert any("columns" in item for item in errors[0]["errors"])

    bad_values = _catalogue_csv(
        _catalogue_row(
            "X" * 61,
            controlled="maybe",
            pack_price="not-a-price",
            price="1.234",
            effective_from="2026-13-40",
        )
    )
    rows, errors, _digest = validate_catalogue_csv(bad_values)
    assert rows == []
    joined = " ".join(errors[0]["errors"])
    assert "controlled" in joined
    assert "pack_price" in joined
    assert "price" in joined
    assert "effective_from" in joined
    assert "code" in joined


def test_s41_preview_is_side_effect_free_and_facility_scoped(tenant, authed_client):
    _product(authed_client, code="EXIST1")
    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="S41 Other Facility",
            code="S41-OTHER",
            mode="CLINIC",
        )
        MedicationProduct.objects.create(
            organisation=tenant.organisation,
            facility=other_facility,
            code="OTHER1",
            generic_name="Synthetic Other Facility",
            dosage_form="TABLET",
            dispensing_unit="TABLET",
            category="MEDICINE",
        )
    content = _catalogue_csv(
        _catalogue_row("EXIST1"),
        _catalogue_row("NEW1"),
        _catalogue_row("OTHER1"),
    )
    preview = authed_client.post(
        "/api/v1/inventory/catalogue/import/preview/",
        {"content": content, "template_version": "1"},
        format="json",
    )
    assert preview.status_code == 200, preview.data
    assert len(preview.data["file_hash"]) == 64
    assert preview.data["template_version"] == "1"
    assert preview.data["valid_rows"] == 3
    assert preview.data["skipped"] == 1
    assert preview.data["row_errors"] == []
    assert preview.data["max_bytes"] > 0
    assert preview.data["max_rows"] > 0

    with tenant_atomic(tenant.organisation.id):
        assert MedicationProduct.objects.filter(facility=tenant.facility).count() == 1
        assert ProductPrice.objects.filter(facility=tenant.facility).count() == 0
        assert StockMovement.objects.count() == 0
        assert AuditEvent.objects.filter(event_code="CATALOGUE_IMPORTED").count() == 0

    wrong_role = _facility_client(
        tenant, other_facility, "s41-preview-wrong-role", "NURSE_TRIAGE"
    )
    denied = wrong_role.post(
        "/api/v1/inventory/catalogue/import/preview/",
        {"content": content},
        format="json",
    )
    assert denied.status_code == 403
    assert "file_hash" not in denied.data

    other_facility_client = _facility_client(
        tenant, other_facility, "s41-preview-other-facility"
    )
    facility_view = other_facility_client.post(
        "/api/v1/inventory/catalogue/import/preview/",
        {"content": content},
        format="json",
    )
    assert facility_view.status_code == 200, facility_view.data
    assert facility_view.data["skipped"] == 1
    assert facility_view.data["existing_codes"] == ["OTHER1"]
    assert "EXIST1" not in facility_view.data["existing_codes"]

    with tenant_atomic(tenant.organisation.id):
        other_org = Organisation.objects.create(
            name="S41 Other Clinic", slug="s41-other-clinic"
        )
        ensure_default_permissions(other_org)
        other_org_facility = Facility.objects.create(
            organisation=other_org, name="S41 Org Facility", code="S41-ORG", mode="CLINIC"
        )
        other_department = Department.objects.create(
            organisation=other_org,
            facility=other_org_facility,
            name="Outpatient",
            code="OPD",
        )
        user = User.objects.create_user("s41-preview-other-org", "test-password-123")
        OrganisationMembership.objects.create(organisation=other_org, user=user)
        UserFacilityRole.objects.create(
            organisation=other_org,
            user=user,
            role=Role.objects.get(organisation=other_org, template_code="OWNER_ADMIN"),
            facility=other_org_facility,
            department=other_department,
        )
        other_org_id = str(other_org.id)
        other_org_facility_id = str(other_org_facility.id)
    foreign_client = APIClient()
    login = foreign_client.post(
        "/api/v1/auth/login/",
        {
            "username": "s41-preview-other-org",
            "password": "test-password-123",
            "organisation_id": other_org_id,
        },
        format="json",
    )
    assert login.status_code == 200, login.data
    foreign_client.defaults["HTTP_X_FACILITY_ID"] = other_org_facility_id
    foreign_client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    foreign = foreign_client.post(
        "/api/v1/inventory/catalogue/import/preview/",
        {"content": content},
        format="json",
    )
    assert foreign.status_code == 200, foreign.data
    assert foreign.data["skipped"] == 0
    assert "EXIST1" not in foreign.data["existing_codes"]
    assert "OTHER1" not in foreign.data["existing_codes"]


def test_s41_preview_closes_parser_gaps_without_writing(tenant, authed_client):
    duplicate_header = CATALOGUE_HEADER.replace("code,", "code,code,", 1)
    structural = authed_client.post(
        "/api/v1/inventory/catalogue/import/preview/",
        {"content": duplicate_header},
        format="json",
    )
    assert structural.status_code == 400
    assert structural.data["code"] == "INVALID_INPUT"

    cases = {
        "duplicate_codes": (
            _catalogue_csv(_catalogue_row("DUP1"), _catalogue_row("DUP1")),
            1,
        ),
        "row_width": (
            _with_extra_column(_catalogue_csv(_catalogue_row("WIDE1"))),
            0,
        ),
        "classification": (
            _catalogue_csv(_catalogue_row("FLAG1", controlled="maybe")),
            0,
        ),
        "pack_price": (
            _catalogue_csv(_catalogue_row("PACK1", pack_price="not-a-price")),
            0,
        ),
        "price": (_catalogue_csv(_catalogue_row("PRICE1", price="1.234")), 0),
        "effective_from": (
            _catalogue_csv(_catalogue_row("DATE1", effective_from="2026-13-40")),
            0,
        ),
        "field_limit": (_catalogue_csv(_catalogue_row("X" * 61)), 0),
    }
    for label, (content, expected_valid) in cases.items():
        result = authed_client.post(
            "/api/v1/inventory/catalogue/import/preview/",
            {"content": content},
            format="json",
        )
        assert result.status_code == 200, (label, result.data)
        assert result.data["valid_rows"] == expected_valid, (label, result.data)
        assert result.data["row_errors"], label
        assert result.data["row_errors"][0]["line"] >= 2, label

    with tenant_atomic(tenant.organisation.id):
        assert MedicationProduct.objects.count() == 0
        assert ProductPrice.objects.count() == 0
        assert StockMovement.objects.count() == 0
        assert AuditEvent.objects.filter(event_code="CATALOGUE_IMPORTED").count() == 0


def test_s41_unicode_and_empty_defaults_import_without_a_price(tenant, authed_client):
    content = _catalogue_csv(
        _catalogue_row(
            "UNI1",
            generic_name="Synthétique α",
            category="",
            prescription_only="",
            controlled="",
            active="",
            currency="",
            price="",
            effective_from="",
            pack_price="",
        )
    )
    preview = authed_client.post(
        "/api/v1/inventory/catalogue/import/preview/",
        {"content": content},
        format="json",
    )
    assert preview.status_code == 200, preview.data
    assert preview.data["valid_rows"] == 1

    imported = authed_client.post(
        "/api/v1/inventory/catalogue/import/",
        {
            "content": content,
            "mode": "VALID_ROWS_ONLY",
            "file_hash": preview.data["file_hash"],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s41-unicode-import",
    )
    assert imported.status_code == 201, imported.data
    assert imported.data["imported"] == 1
    with tenant_atomic(tenant.organisation.id):
        product = MedicationProduct.objects.get(code="UNI1")
        assert product.generic_name == "Synthétique α"
        assert product.category == "MEDICINE"
        assert product.prescription_only is True
        assert product.controlled is False
        assert product.active is True
        assert ProductPrice.objects.filter(product=product).count() == 0
        assert AuditEvent.objects.filter(event_code="CATALOGUE_IMPORTED").count() == 1


def test_s41_import_modes_hash_and_lost_response_replay(tenant, authed_client):
    _product(authed_client, code="DUP1")
    content = _catalogue_csv(
        _catalogue_row("DUP1"),
        _catalogue_row("NEW2"),
        _catalogue_row("BAD2", pack_price="bad"),
    )
    preview = authed_client.post(
        "/api/v1/inventory/catalogue/import/preview/",
        {"content": content},
        format="json",
    )
    assert preview.status_code == 200, preview.data
    assert preview.data["valid_rows"] == 2
    assert preview.data["skipped"] == 1
    assert len(preview.data["row_errors"]) == 1

    strict = authed_client.post(
        "/api/v1/inventory/catalogue/import/",
        {
            "content": content,
            "mode": "ALL_OR_NOTHING",
            "file_hash": preview.data["file_hash"],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s41-strict-import",
    )
    assert strict.status_code == 400
    assert strict.data["row_errors"][0]["line"] == 4

    partial = authed_client.post(
        "/api/v1/inventory/catalogue/import/",
        {
            "content": content,
            "mode": "VALID_ROWS_ONLY",
            "file_hash": preview.data["file_hash"],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s41-partial-import",
    )
    assert partial.status_code == 201, partial.data
    assert partial.data["imported"] == 1
    assert partial.data["skipped"] == 1
    assert partial.data["error_count"] == 1
    with tenant_atomic(tenant.organisation.id):
        assert MedicationProduct.objects.filter(code="BAD2").count() == 0
        assert ProductPrice.objects.filter(product__code="NEW2").count() == 1
        assert StockMovement.objects.count() == 0
        assert AuditEvent.objects.filter(event_code="CATALOGUE_IMPORTED").count() == 1

    mismatched = authed_client.post(
        "/api/v1/inventory/catalogue/import/",
        {
            "content": content,
            "mode": "VALID_ROWS_ONLY",
            "file_hash": "0" * 64,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s41-hash-mismatch",
    )
    assert mismatched.status_code == 400
    assert mismatched.data["detail"] == "The file hash does not match."

    replay_content = _catalogue_csv(_catalogue_row("REPLAY1"))
    first = authed_client.post(
        "/api/v1/inventory/catalogue/import/",
        {"content": replay_content, "mode": "ALL_OR_NOTHING"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s41-lost-import",
    )
    assert first.status_code == 201, first.data
    replay = authed_client.post(
        "/api/v1/inventory/catalogue/import/",
        {"content": replay_content, "mode": "ALL_OR_NOTHING"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s41-lost-import",
    )
    assert replay.status_code == 201, replay.data
    assert replay.headers["Idempotent-Replay"] == "true"
    assert replay.data["file_hash"] == first.data["file_hash"]
    with tenant_atomic(tenant.organisation.id):
        assert MedicationProduct.objects.filter(code="REPLAY1").count() == 1
        assert AuditEvent.objects.filter(event_code="CATALOGUE_IMPORTED").count() == 2


def test_s09_product_deactivation_requires_zero_stock(tenant, authed_client):
    # CMD-088 — mechanical evidence for s17-cmd-audit.
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


def _s32_price(client, product_id):
    response = client.post(
        "/api/v1/inventory/prices/",
        {"product_id": product_id, "amount": "500.00", "effective_from": TODAY.isoformat()},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s32-price-{uuid4().hex}",
    )
    assert response.status_code == 201, response.data
    return response.data


def test_s32_multi_line_receipt_shares_one_document_identity(tenant, authed_client):
    """S-32: one receipt identity posts all reviewed lines once."""

    location = _locations(authed_client)[0]
    first = _product(authed_client, generic_name="S32 Receipt Product A")
    second = _product(authed_client, generic_name="S32 Receipt Product B")
    _s32_price(authed_client, first["id"])
    _s32_price(authed_client, second["id"])
    with tenant_atomic(tenant.organisation.id):
        before_receipts = StockReceipt.objects.count()
        before_movements = StockMovement.objects.count()
    expiry = (TODAY + timedelta(days=120)).isoformat()
    posted = authed_client.post(
        "/api/v1/inventory/receipts/",
        {
            "receipt_no": "GRN-S32-MULTI",
            "supplier_name": "Synthetic supplier",
            "lines": [
                {
                    "product_id": first["id"],
                    "location_id": location["id"],
                    "batch_no": "S32-A",
                    "expiry_date": expiry,
                    "quantity": "20.00",
                    "unit_cost": "100.00",
                },
                {
                    "product_id": second["id"],
                    "location_id": location["id"],
                    "batch_no": "S32-B",
                    "expiry_date": expiry,
                    "quantity": "30.00",
                    "unit_cost": "50.00",
                },
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s32-multi-receipt",
    )
    assert posted.status_code == 201, posted.data
    assert posted.data["receipt_no"] == "GRN-S32-MULTI"
    assert posted.data["movement_count"] == 2
    with tenant_atomic(tenant.organisation.id):
        assert StockReceipt.objects.count() == before_receipts + 1
        assert StockMovement.objects.count() == before_movements + 2
        receipt = StockReceipt.objects.get(receipt_no="GRN-S32-MULTI")
        assert receipt.lines.count() == 2
        assert sum((line.quantity for line in receipt.lines.all()), Decimal("0.00")) == Decimal("50.00")


def test_s32_stock_summary_separates_quarantined_stock_and_filters_location(
    tenant, authed_client
):
    """S-32: usable stock excludes quarantined balances and location filters work."""

    location = _locations(authed_client)[0]
    quarantine = authed_client.post(
        "/api/v1/inventory/locations/",
        {"code": "S32Q", "name": "S32 quarantine", "location_type": "QUARANTINE"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s32-quarantine-location",
    )
    assert quarantine.status_code == 201, quarantine.data
    product = _product(authed_client, generic_name="S32 Quarantine Product")
    _s32_price(authed_client, product["id"])
    received = _receive(authed_client, product["id"], location["id"], quantity="100.00")
    assert received.status_code == 201
    with tenant_atomic(tenant.organisation.id):
        batch_id = str(StockBatch.objects.get(product_id=product["id"]).id)
    quarantined = authed_client.post(
        "/api/v1/inventory/quarantine/",
        {
            "batch_id": batch_id,
            "location_id": location["id"],
            "quantity": "30.00",
            "reason": "S32 damage",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s32-quarantine",
    )
    assert quarantined.status_code == 201, quarantined.data

    summary = authed_client.get("/api/v1/inventory/stock/")
    assert summary.status_code == 200, summary.data
    row = next(item for item in summary.data if item["product_id"] == product["id"])
    assert row["usable_quantity"] == "70.00"
    assert row["quarantined_quantity"] == "30.00"
    assert row["total_quantity"] == "100.00"

    filtered = authed_client.get(
        f"/api/v1/inventory/stock/?location_id={quarantine.data['id']}"
    )
    assert filtered.status_code == 200, filtered.data
    quarantined_row = next(
        item for item in filtered.data if item["product_id"] == product["id"]
    )
    assert quarantined_row["usable_quantity"] == "0.00"
    assert quarantined_row["quarantined_quantity"] == "30.00"


def test_s32_drilldown_filters_by_location_and_date(tenant, authed_client):
    """S-32: batch and movement drill-downs accept location/date filters."""

    location = _locations(authed_client)[0]
    product = _product(authed_client, generic_name="S32 Filter Product")
    _s32_price(authed_client, product["id"])
    assert _receive(authed_client, product["id"], location["id"], quantity="10.00").status_code == 201

    batches = authed_client.get(
        f"/api/v1/inventory/batches/?product_id={product['id']}&location_id={location['id']}"
    )
    assert batches.status_code == 200, batches.data
    assert len(batches.data) == 1
    assert all(row["location_id"] == location["id"] for row in batches.data[0]["locations"])

    today = TODAY.isoformat()
    in_window = authed_client.get(f"/api/v1/inventory/movements/?date_from={today}")
    out_of_window = authed_client.get(
        f"/api/v1/inventory/movements/?date_to={(TODAY - timedelta(days=1)).isoformat()}"
    )
    assert in_window.status_code == 200 and out_of_window.status_code == 200
    assert len(in_window.data) >= 1
    assert out_of_window.data == []


def test_s35_r6_inventory_filters_validate_and_empty_location_hides_batches(
    tenant, authed_client
):
    """S-35 Fix 6: malformed filters fail closed and empty scopes return no rows."""

    location = _locations(authed_client)[0]
    product = _product(authed_client, generic_name="S35 Filter Product")
    _s32_price(authed_client, product["id"])
    assert _receive(authed_client, product["id"], location["id"], quantity="10.00").status_code == 201
    empty_location = authed_client.post(
        "/api/v1/inventory/locations/",
        {
            "code": f"S35-EMPTY-{uuid4().hex[:6]}",
            "name": "S35 empty location",
            "location_type": "STORE",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s35-empty-location-{uuid4().hex}",
    )
    assert empty_location.status_code == 201, empty_location.data
    empty_id = empty_location.data["id"]

    empty_batches = authed_client.get(
        f"/api/v1/inventory/batches/?product_id={product['id']}&location_id={empty_id}"
    )
    assert empty_batches.status_code == 200, empty_batches.data
    assert empty_batches.data == []

    invalid = [
        "/api/v1/inventory/batches/?expiry_from=not-a-date",
        "/api/v1/inventory/batches/?expiry_from=2030-01-01&expiry_to=2029-01-01",
        "/api/v1/inventory/movements/?date_from=not-a-date",
        "/api/v1/inventory/movements/?date_from=2030-01-01&date_to=2029-01-01",
        "/api/v1/inventory/stock/?location_id=not-a-uuid",
    ]
    for path in invalid:
        response = authed_client.get(path)
        assert response.status_code == 400, (path, response.status_code, response.data)
