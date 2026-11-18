import pytest

from clinical.models import ClinicalNoteVersion, Encounter
from core.mig004 import (
    backfill_mig004,
    constrain_mig004,
    cutover_mig004,
    inventory_mig004,
    rollback_mig004,
    target_writes_enabled_mig004,
    verify_mig004,
)
from core.mig003 import (
    backfill_mig003,
    constrain_mig003,
    cutover_mig003,
    inventory_mig003,
    verify_mig003,
)
from core.migration_reconciliation import (
    backfill_mig002,
    cutover_mig002,
    inventory_mig002,
)
from core.models import MigrationCutover, MigrationReconciliation
from core.services import tenant_atomic
from tests.test_s04_encounter import _canonical_encounter, _save_and_sign

pytestmark = pytest.mark.django_db


@pytest.fixture
def enabled_mig002_target(tenant, enabled_mig001_target):
    with tenant_atomic(tenant.organisation.id):
        inventory_mig002(organisation=tenant.organisation)
        backfill_mig002(organisation=tenant.organisation)
        cutover_mig002(organisation=tenant.organisation)
        return MigrationCutover.objects.get(
            organisation=tenant.organisation, migration_id="MIG-002"
        )


@pytest.fixture
def enabled_mig003_target(tenant, enabled_mig002_target):
    with tenant_atomic(tenant.organisation.id):
        inventory_mig003(organisation=tenant.organisation)
        backfill_mig003(organisation=tenant.organisation)
        verify_mig003(organisation=tenant.organisation)
        verify_mig003(organisation=tenant.organisation)
        constrain_mig003(organisation=tenant.organisation)
        cutover_mig003(organisation=tenant.organisation)
        return MigrationCutover.objects.get(
            organisation=tenant.organisation, migration_id="MIG-003"
        )


def test_s04_mig004_verifies_clean_encounters_then_rolls_back(
    tenant, authed_client, enabled_mig003_target
):
    setup = _canonical_encounter(tenant, authed_client)
    encounter_id = setup["encounter"]["id"]
    _saved, signed = _save_and_sign(
        authed_client, encounter_id, setup["encounter"]["consultation_etag"]
    )
    assert signed.status_code == 200, signed.data
    with tenant_atomic(tenant.organisation.id):
        inventory_mig004(organisation=tenant.organisation)
        backfill_mig004(organisation=tenant.organisation)
        first = verify_mig004(organisation=tenant.organisation)
        second = verify_mig004(organisation=tenant.organisation)
        assert first.unresolved == 0, first.as_dict()
        assert second.stable_full_scan_count >= 2
        assert second.signed_versions >= 1
        constrain_mig004(organisation=tenant.organisation)
        cutover_mig004(organisation=tenant.organisation)
        assert target_writes_enabled_mig004(tenant.organisation) is True
        evidence = MigrationReconciliation.objects.get(
            organisation=tenant.organisation,
            migration_id="MIG-004",
            legacy_pk=str(encounter_id),
        )
        assert evidence.resolution_state == "RESOLVED"
        rollback_mig004(organisation=tenant.organisation, reason="S04 rollback proof")
        assert target_writes_enabled_mig004(tenant.organisation) is False
        assert Encounter.objects.filter(id=encounter_id).exists()
        assert ClinicalNoteVersion.objects.filter(
            note__encounter_id=encounter_id
        ).exists()


def test_s04_mig004_legacy_terminal_status_blocks_activation(
    tenant, authed_client, enabled_mig003_target
):
    setup = _canonical_encounter(tenant, authed_client)
    encounter_id = setup["encounter"]["id"]
    with tenant_atomic(tenant.organisation.id):
        Encounter.objects.filter(id=encounter_id).update(status="CLOSED")
        inventory_mig004(organisation=tenant.organisation)
        backfill_mig004(organisation=tenant.organisation)
        summary = verify_mig004(organisation=tenant.organisation)
        assert summary.unresolved >= 1
        with pytest.raises(ValueError, match="E=0 and two stable"):
            constrain_mig004(organisation=tenant.organisation)
