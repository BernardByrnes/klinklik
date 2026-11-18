"""MIG-005..009 cashier reconciliation proofs."""

from decimal import Decimal

import pytest

from billing.models import Invoice
from core.mig005 import (
    MIGRATION_IDS,
    constrain_mig005,
    cutover_mig005,
    inventory_mig005,
    rollback_mig005,
    verify_mig005,
)
from core.models import MigrationCutover
from core.services import tenant_atomic
from tests.test_s05_billing import check_in, open_shift, pay, register

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def s01_target_cutover(enabled_mig001_target):
    return enabled_mig001_target


def _pay_once(tenant, authed_client):
    patient_id = register(authed_client, "s05-mig-register")
    checked_in = check_in(authed_client, patient_id, tenant, "s05-mig-checkin")
    open_shift(authed_client)
    response = pay(authed_client, checked_in["invoice_id"], "30000.00", "s05-mig-pay")
    assert response.status_code == 201, response.data
    return checked_in["invoice_id"]


def test_s05_all_migrations_reach_cutover_and_roll_back(tenant, authed_client):
    _pay_once(tenant, authed_client)
    for migration_id in MIGRATION_IDS:
        with tenant_atomic(tenant.organisation.id):
            inventory = inventory_mig005(
                organisation=tenant.organisation, migration_id=migration_id
            )
            assert inventory["source_count"] >= 0
            first = verify_mig005(
                organisation=tenant.organisation, migration_id=migration_id
            )
            second = verify_mig005(
                organisation=tenant.organisation, migration_id=migration_id
            )
            assert second["issue_count"] == 0, second
            assert second["parity_passes"] >= 2
            constrain_mig005(
                organisation=tenant.organisation, migration_id=migration_id
            )
            cutover = cutover_mig005(
                organisation=tenant.organisation, migration_id=migration_id
            )
            assert cutover["phase"] == "CUTOVER"
            assert cutover["target_reads_enabled"] is True
            assert cutover["target_writes_enabled"] is True
            rolled_back = rollback_mig005(
                organisation=tenant.organisation,
                migration_id=migration_id,
                reason="Synthetic rehearsal rollback",
            )
            assert rolled_back["phase"] == "EXPANDED"
            assert rolled_back["target_reads_enabled"] is False
            cutover_row = MigrationCutover.objects.get(
                organisation=tenant.organisation, migration_id=migration_id
            )
            assert cutover_row.write_fence >= 3
            assert cutover_row.rollback_reason == "Synthetic rehearsal rollback"


def test_s05_projection_mismatch_blocks_constrained(tenant, authed_client):
    invoice_id = _pay_once(tenant, authed_client)
    with tenant_atomic(tenant.organisation.id):
        Invoice.objects.filter(id=invoice_id).update(balance=Decimal("1.00"))
        inventory_mig005(
            organisation=tenant.organisation, migration_id="MIG-005"
        )
        verify_mig005(organisation=tenant.organisation, migration_id="MIG-005")
        verify_mig005(organisation=tenant.organisation, migration_id="MIG-005")
        row = MigrationCutover.objects.get(
            organisation=tenant.organisation, migration_id="MIG-005"
        )
        assert row.phase == "BLOCKED"
        assert row.parity_passes == 0
        with pytest.raises(ValueError) as refused:
            constrain_mig005(
                organisation=tenant.organisation, migration_id="MIG-005"
            )
        assert "two stable clean scans" in str(refused.value)
