"""S-10 blind counts, threshold approvals, quarantine and disposal proofs."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from accounts.models import (
    OrganisationMembership,
    Permission,
    Role,
    RolePermission,
    User,
    UserFacilityRole,
)
from audit.models import AuditEvent
from core.services import tenant_atomic
from inventory.models import (
    BatchLocationBalance,
    DisposalRecord,
    QuarantineRecord,
    StockAdjustment,
    StockBatch,
    StockCount,
    StockCountLine,
    StockMovement,
)
from tenancy.models import FacilityWorkflowPolicy
from tests.test_s09_inventory import (
    TODAY,
    _locations,
    _product,
    _receive,
)


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


def _price(client, product_id, amount="500.00"):
    response = client.post(
        "/api/v1/inventory/prices/",
        {
            "product_id": product_id,
            "amount": amount,
            "effective_from": TODAY.isoformat(),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"price-{uuid4().hex}",
    )
    assert response.status_code == 201, response.data
    return response.data


def _second_admin(tenant):
    with tenant_atomic(tenant.organisation.id):
        user = User.objects.create_user(f"s10-admin-{uuid4().hex[:8]}", "test-password-123")
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=user)
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=user,
            role=Role.objects.get(
                organisation=tenant.organisation, template_code="OWNER_ADMIN"
            ),
            facility=tenant.facility,
            department=tenant.department,
        )
    from rest_framework.test import APIClient

    client = APIClient()
    login = client.post(
        "/api/v1/auth/login/",
        {
            "username": user.username,
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    assert login.status_code == 200
    client.defaults["HTTP_X_FACILITY_ID"] = str(tenant.facility.id)
    client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    return client, user


def test_s10_blind_count_submits_and_posts_exact_correction(tenant, authed_client):
    _threshold(tenant)
    location = _locations(authed_client)[0]
    product = _product(authed_client)
    _price(authed_client, product["id"])
    received = _receive(authed_client, product["id"], location["id"], quantity="100.00")
    assert received.status_code == 201

    opened = authed_client.post(
        "/api/v1/inventory/counts/open/",
        {"location_id": location["id"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-count-open",
    )
    assert opened.status_code == 201, opened.data
    count_id = opened.data["id"]
    blind = authed_client.get(f"/api/v1/inventory/counts/{count_id}/")
    assert blind.status_code == 200
    assert blind.data["blind"] is True
    assert "expected_qty" not in blind.data["lines"][0]
    revealed = authed_client.get(f"/api/v1/inventory/counts/{count_id}/?reveal=1")
    assert revealed.data["blind"] is False
    assert revealed.data["lines"][0]["expected_qty"] == "100.00"
    line_id = blind.data["lines"][0]["id"]

    submitted = authed_client.post(
        f"/api/v1/inventory/counts/{count_id}/submit/",
        {"expected_version": opened.data["version"], "lines": [{"line_id": line_id, "counted_qty": "95.00"}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-count-submit",
    )
    assert submitted.status_code == 200, submitted.data
    assert submitted.data["state"] == "SUBMITTED"

    approved = authed_client.post(
        f"/api/v1/inventory/counts/{count_id}/approve/",
        {"expected_version": submitted.data["version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-count-approve",
    )
    assert approved.status_code == 200, approved.data
    assert approved.data["state"] == "POSTED"
    assert approved.data["adjustment_count"] == 1
    with tenant_atomic(tenant.organisation.id):
        assert StockCount.objects.get(id=count_id).state == "POSTED"
        assert StockCountLine.objects.get(id=line_id).variance_qty == Decimal("-5.00")
        adjustment = StockAdjustment.objects.get(count_id=count_id)
        assert adjustment.reason_code == "COUNT_CORRECTION"
        assert adjustment.state == "POSTED"
        assert BatchLocationBalance.objects.get(
            product_id=product["id"], location_id=location["id"]
        ).quantity == Decimal("95.00")
        assert StockMovement.objects.filter(
            movement_type="ADJUSTMENT", quantity=Decimal("-5.00")
        ).count() == 1
        assert AuditEvent.objects.filter(event_code="STOCK_COUNT_APPROVED").count() == 1
    again = authed_client.post(
        f"/api/v1/inventory/counts/{count_id}/approve/",
        {"expected_version": approved.data["version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-count-approve-again",
    )
    assert again.status_code == 409


def test_s10_above_threshold_count_needs_distinct_admin(tenant, authed_client):
    # CMD-066 — mechanical evidence for s17-cmd-audit.
    _threshold(tenant, "100.00")
    location = _locations(authed_client)[0]
    product = _product(authed_client)
    _price(authed_client, product["id"], amount="500.00")
    _receive(authed_client, product["id"], location["id"], quantity="100.00")
    opened = authed_client.post(
        "/api/v1/inventory/counts/open/",
        {"location_id": location["id"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-threshold-open",
    )
    count_id = opened.data["id"]
    line_id = authed_client.get(f"/api/v1/inventory/counts/{count_id}/").data["lines"][0]["id"]
    submitted = authed_client.post(
        f"/api/v1/inventory/counts/{count_id}/submit/",
        {"expected_version": opened.data["version"], "lines": [{"line_id": line_id, "counted_qty": "90.00"}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-threshold-submit",
    )
    refused = authed_client.post(
        f"/api/v1/inventory/counts/{count_id}/approve/",
        {"expected_version": submitted.data["version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-threshold-owner",
    )
    assert refused.status_code == 403
    assert refused.data["code"] == "SEPARATION_OF_DUTIES_REQUIRED"
    admin_client, _admin = _second_admin(tenant)
    approved = admin_client.post(
        f"/api/v1/inventory/counts/{count_id}/approve/",
        {"expected_version": submitted.data["version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-threshold-admin",
    )
    assert approved.status_code == 200, approved.data
    with tenant_atomic(tenant.organisation.id):
        assert BatchLocationBalance.objects.get(
            product_id=product["id"], location_id=location["id"]
        ).quantity == Decimal("90.00")


def test_s10_standalone_adjustment_threshold_and_approval(tenant, authed_client):
    # CMD-131 — mechanical evidence for s17-cmd-audit.
    _threshold(tenant, "1000.00")
    location = _locations(authed_client)[0]
    product = _product(authed_client)
    _price(authed_client, product["id"], amount="500.00")
    _receive(authed_client, product["id"], location["id"], quantity="100.00")
    with tenant_atomic(tenant.organisation.id):
        batch_id = str(StockBatch.objects.get(product_id=product["id"]).id)

    small = authed_client.post(
        "/api/v1/inventory/adjustments/",
        {
            "batch_id": batch_id,
            "location_id": location["id"],
            "quantity": "-1.00",
            "reason_code": "BREAKAGE",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-adjust-small",
    )
    assert small.status_code == 201, small.data
    assert small.data["state"] == "POSTED"
    large = authed_client.post(
        "/api/v1/inventory/adjustments/",
        {
            "batch_id": batch_id,
            "location_id": location["id"],
            "quantity": "-10.00",
            "reason_code": "BREAKAGE",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-adjust-large",
    )
    assert large.status_code == 201, large.data
    assert large.data["state"] == "PENDING_APPROVAL"
    with tenant_atomic(tenant.organisation.id):
        assert StockMovement.objects.filter(source_type="StockAdjustment").count() == 1
    same = authed_client.post(
        f"/api/v1/inventory/adjustments/{large.data['id']}/approve/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-adjust-same",
    )
    assert same.status_code == 403
    admin_client, _admin = _second_admin(tenant)
    approved = admin_client.post(
        f"/api/v1/inventory/adjustments/{large.data['id']}/approve/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-adjust-admin",
    )
    assert approved.status_code == 200, approved.data
    assert approved.data["state"] == "POSTED"
    with tenant_atomic(tenant.organisation.id):
        assert BatchLocationBalance.objects.get(
            product_id=product["id"], location_id=location["id"]
        ).quantity == Decimal("89.00")


def test_s10_adjustment_requires_configured_threshold(tenant, authed_client):
    location = _locations(authed_client)[0]
    product = _product(authed_client)
    _receive(authed_client, product["id"], location["id"], quantity="10.00")
    with tenant_atomic(tenant.organisation.id):
        batch_id = str(StockBatch.objects.get(product_id=product["id"]).id)
    refused = authed_client.post(
        "/api/v1/inventory/adjustments/",
        {
            "batch_id": batch_id,
            "location_id": location["id"],
            "quantity": "-1.00",
            "reason_code": "BREAKAGE",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-no-threshold",
    )
    assert refused.status_code == 422
    assert refused.data["code"] == "PREREQUISITE_MISSING"


def test_s10_quarantine_then_disposal_is_append_only(tenant, authed_client):
    # CMD-069 — mechanical evidence for s17-cmd-audit.
    # CMD-068 — mechanical evidence for s17-cmd-audit.
    _threshold(tenant)
    location = _locations(authed_client)[0]
    product = _product(authed_client)
    _receive(authed_client, product["id"], location["id"], quantity="100.00")
    quarantine = authed_client.post(
        "/api/v1/inventory/locations/",
        {"code": "QUAR-S10", "name": "Quarantine", "location_type": "QUARANTINE"},
        format="json",
    )
    assert quarantine.status_code == 201
    with tenant_atomic(tenant.organisation.id):
        batch = StockBatch.objects.get(product_id=product["id"])
        batch_id = str(batch.id)
    quarantined = authed_client.post(
        "/api/v1/inventory/quarantine/",
        {
            "batch_id": batch_id,
            "location_id": location["id"],
            "quantity": "20.00",
            "reason": "Synthetic damaged stock",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-quarantine",
    )
    assert quarantined.status_code == 201, quarantined.data
    with tenant_atomic(tenant.organisation.id):
        assert BatchLocationBalance.objects.get(
            batch_id=batch_id, location_id=location["id"]
        ).quantity == Decimal("80.00")
        assert QuarantineRecord.objects.count() == 1
        assert AuditEvent.objects.filter(event_code="STOCK_QUARANTINED").count() == 1
    disposed = authed_client.post(
        "/api/v1/inventory/disposals/",
        {
            "batch_id": batch_id,
            "location_id": quarantine.data["id"],
            "quantity": "5.00",
            "reason": "Synthetic disposal",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-disposal",
    )
    assert disposed.status_code == 201, disposed.data
    with tenant_atomic(tenant.organisation.id):
        assert BatchLocationBalance.objects.get(
            batch_id=batch_id, location_id=quarantine.data["id"]
        ).quantity == Decimal("15.00")
        assert DisposalRecord.objects.count() == 1
        assert AuditEvent.objects.filter(event_code="STOCK_DISPOSED").count() == 1
    refused = authed_client.post(
        "/api/v1/inventory/disposals/",
        {
            "batch_id": batch_id,
            "location_id": location["id"],
            "quantity": "5.00",
            "reason": "Synthetic invalid disposal",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-disposal-usable",
    )
    assert refused.status_code == 422


def test_s10_ledger_running_balance_and_audited_export(tenant, authed_client):
    _threshold(tenant)
    location = _locations(authed_client)[0]
    product = _product(authed_client)
    _receive(authed_client, product["id"], location["id"], quantity="100.00")
    with tenant_atomic(tenant.organisation.id):
        batch_id = str(StockBatch.objects.get(product_id=product["id"]).id)
    authed_client.post(
        "/api/v1/inventory/adjustments/",
        {
            "batch_id": batch_id,
            "location_id": location["id"],
            "quantity": "-5.00",
            "reason_code": "DAMAGE",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s10-ledger-adjust",
    )
    ledger = authed_client.get(f"/api/v1/inventory/ledger/?product_id={product['id']}")
    assert ledger.status_code == 200, ledger.data
    assert [row["running_balance"] for row in ledger.data] == ["100.00", "95.00"]
    exported = authed_client.get(
        f"/api/v1/inventory/ledger/export/?product_id={product['id']}"
    )
    assert exported.status_code == 200
    assert "running_balance" in exported.content.decode()
    with tenant_atomic(tenant.organisation.id):
        assert AuditEvent.objects.filter(event_code="INVENTORY_LEDGER_EXPORTED").count() == 1


def test_s29_r2_incomplete_count_rejected_without_state_audit_or_movement(tenant, authed_client):
    """S-29-R2: an unobserved line cannot become a recorded zero."""

    _threshold(tenant)
    location = _locations(authed_client)[0]
    first = _product(authed_client)
    second = _product(
        authed_client,
        generic_name="Synthetic Second Count Product",
        strength="250 mg",
    )
    _price(authed_client, first["id"])
    _price(authed_client, second["id"])
    assert _receive(authed_client, first["id"], location["id"], quantity="100.00").status_code == 201
    assert _receive(authed_client, second["id"], location["id"], quantity="50.00").status_code == 201
    opened = authed_client.post(
        "/api/v1/inventory/counts/open/",
        {"location_id": location["id"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s29-r2-count-open",
    )
    assert opened.status_code == 201, opened.data
    count_id = opened.data["id"]
    sheet = authed_client.get(f"/api/v1/inventory/counts/{count_id}/")
    assert sheet.status_code == 200, sheet.data
    assert len(sheet.data["lines"]) == 2

    with tenant_atomic(tenant.organisation.id):
        before = (
            StockCount.objects.get(id=count_id).state,
            StockCount.objects.get(id=count_id).version,
            tuple(
                StockCountLine.objects.filter(count_id=count_id)
                .order_by("id")
                .values_list("counted_qty", flat=True)
            ),
            AuditEvent.objects.count(),
            StockMovement.objects.filter(movement_type="ADJUSTMENT").count(),
            StockAdjustment.objects.count(),
        )

    refused = authed_client.post(
        f"/api/v1/inventory/counts/{count_id}/submit/",
        {
            "expected_version": opened.data["version"],
            "lines": [
                {
                    "line_id": sheet.data["lines"][0]["id"],
                    "counted_qty": "95.00",
                }
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s29-r2-count-submit-incomplete",
    )
    assert refused.status_code == 422, refused.data
    assert refused.data["code"] == "PREREQUISITE_MISSING"

    with tenant_atomic(tenant.organisation.id):
        after = (
            StockCount.objects.get(id=count_id).state,
            StockCount.objects.get(id=count_id).version,
            tuple(
                StockCountLine.objects.filter(count_id=count_id)
                .order_by("id")
                .values_list("counted_qty", flat=True)
            ),
            AuditEvent.objects.count(),
            StockMovement.objects.filter(movement_type="ADJUSTMENT").count(),
            StockAdjustment.objects.count(),
        )
    assert after == before


def test_s32_approver_lists_submitted_counts_and_opens_blind_sheet(tenant, authed_client):
    """S-32: an approver discovers submitted counts without a shared URL."""

    location = _locations(authed_client)[0]
    product = _product(authed_client)
    _price(authed_client, product["id"])
    assert _receive(authed_client, product["id"], location["id"], quantity="100.00").status_code == 201
    opened = authed_client.post(
        "/api/v1/inventory/counts/open/",
        {"location_id": location["id"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s32-count-open",
    )
    assert opened.status_code == 201, opened.data
    count_id = opened.data["id"]
    # D-04: create a movement after the count opens so the approver has data to interpret.
    assert _receive(authed_client, product["id"], location["id"], quantity="5.00").status_code == 201
    sheet = authed_client.get(f"/api/v1/inventory/counts/{count_id}/")
    submitted = authed_client.post(
        f"/api/v1/inventory/counts/{count_id}/submit/",
        {
            "expected_version": sheet.data["version"],
            "lines": [
                {"line_id": row["id"], "counted_qty": "95.00"}
                for row in sheet.data["lines"]
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s32-count-submit",
    )
    assert submitted.status_code == 200, submitted.data

    approver, _ = _second_admin(tenant)
    listing = approver.get("/api/v1/inventory/counts/")
    assert listing.status_code == 200, listing.data
    row = next(item for item in listing.data["counts"] if item["id"] == count_id)
    assert row["state"] == "SUBMITTED"
    assert row["location_id"] == location["id"]
    assert row["submitted_by_name"]
    assert "expected_qty" not in row
    assert "variance_qty" not in row

    detail = approver.get(f"/api/v1/inventory/counts/{count_id}/?reveal=1")
    assert detail.status_code == 200, detail.data
    assert detail.data["lines"][0]["expected_qty"]
    assert len(detail.data["movements_during_count"]) >= 1
    assert detail.data["blind"] is False

    blind = approver.get(f"/api/v1/inventory/counts/{count_id}/")
    assert blind.status_code == 200
    assert "expected_qty" not in blind.data["lines"][0]

    with tenant_atomic(tenant.organisation.id):
        reader = User.objects.create_user(
            f"s10-reader-{uuid4().hex[:6]}", "test-password-123"
        )
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=reader)
        role = Role.objects.create(
            organisation=tenant.organisation,
            name=f"S10 reader {uuid4().hex[:6]}",
            template_code="S10_COUNT_READER",
        )
        permission, _ = Permission.objects.get_or_create(code="inventory.read")
        RolePermission.objects.create(
            organisation=tenant.organisation, role=role, permission=permission
        )
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=reader,
            role=role,
            facility=tenant.facility,
            department=tenant.department,
        )
    from rest_framework.test import APIClient

    reader_client = APIClient()
    login = reader_client.post(
        "/api/v1/auth/login/",
        {
            "username": reader.username,
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    reader_client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    reader_client.defaults["HTTP_X_FACILITY_ID"] = str(tenant.facility.id)
    reader_detail = reader_client.get(f"/api/v1/inventory/counts/{count_id}/?reveal=1")
    assert reader_detail.status_code == 200, reader_detail.data
    assert "expected_qty" not in reader_detail.data["lines"][0]
    assert "variance_qty" not in reader_detail.data["lines"][0]
    assert reader_detail.data["movements_during_count"] == []
