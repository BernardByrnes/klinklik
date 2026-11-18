"""MIG-010 credit/refund reconciliation proofs."""

import pytest

from accounts.models import User
from billing.models import Invoice
from billing.services import approve_refund, request_refund
from core.mig010 import (
    constrain_mig010,
    cutover_mig010,
    inventory_mig010,
    rollback_mig010,
    verify_mig010,
)
from core.models import MigrationCutover
from core.services import tenant_atomic
from tests.test_s05_billing import check_in, open_shift, pay, register

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def s01_target_cutover(enabled_mig001_target):
    return enabled_mig001_target


def _credited_refund(tenant, authed_client):
    patient_id = register(authed_client, "s06-mig-register")
    checked_in = check_in(authed_client, patient_id, tenant, "s06-mig-checkin")
    invoice_id = checked_in["invoice_id"]
    open_shift(authed_client)
    paid = pay(authed_client, invoice_id, "30000.00", "s06-mig-pay")
    credit = authed_client.post(
        f"/api/v1/billing/invoices/{invoice_id}/credit-notes/",
        {"amount": "10000.00", "reason": "Synthetic MIG credit"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s06-mig-credit",
    )
    assert credit.status_code == 201, credit.data
    with tenant_atomic(tenant.organisation.id):
        approver = User.objects.create_user("s06-mig-approver", "test-password-123")
        refund = request_refund(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=tenant.user,
            payment_id=paid.data["id"],
            credit_note_id=credit.data["id"],
            amount="4000.00",
            reason="Synthetic MIG refund",
        )
        approve_refund(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=approver,
            refund_id=refund.id,
            mfa_verified=True,
        )
    return invoice_id


def test_s06_mig010_reaches_cutover_and_rolls_back(tenant, authed_client):
    _credited_refund(tenant, authed_client)
    with tenant_atomic(tenant.organisation.id):
        inventory = inventory_mig010(organisation=tenant.organisation)
        assert inventory["source_count"] == 2
        verify_mig010(organisation=tenant.organisation)
        second = verify_mig010(organisation=tenant.organisation)
        assert second["issue_count"] == 0, second
        assert second["parity_passes"] >= 2
        constrain_mig010(organisation=tenant.organisation)
        cutover = cutover_mig010(organisation=tenant.organisation)
        assert cutover["phase"] == "CUTOVER"
        rolled_back = rollback_mig010(
            organisation=tenant.organisation, reason="Synthetic rehearsal rollback"
        )
        assert rolled_back["phase"] == "EXPANDED"
        row = MigrationCutover.objects.get(
            organisation=tenant.organisation, migration_id="MIG-010"
        )
        assert row.write_fence >= 3
        assert row.rollback_reason == "Synthetic rehearsal rollback"


def test_s06_mig010_projection_mismatch_blocks_cutover(tenant, authed_client):
    invoice_id = _credited_refund(tenant, authed_client)
    with tenant_atomic(tenant.organisation.id):
        Invoice.objects.filter(id=invoice_id).update(credit_total="1.00")
        inventory_mig010(organisation=tenant.organisation)
        verify_mig010(organisation=tenant.organisation)
        verify_mig010(organisation=tenant.organisation)
        row = MigrationCutover.objects.get(
            organisation=tenant.organisation, migration_id="MIG-010"
        )
        assert row.phase == "BLOCKED"
        assert row.parity_passes == 0
        with pytest.raises(ValueError):
            constrain_mig010(organisation=tenant.organisation)
