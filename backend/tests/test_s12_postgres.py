"""S-12 PostgreSQL RLS, guard and concurrency proofs."""

from datetime import date
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from django.db import DatabaseError, close_old_connections, connection

from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from audit.models import AuditEvent
from core.errors import CanonicalError
from core.rls import rls_status
from core.services import tenant_atomic
from inventory.models import BatchLocationBalance, StockMovement
from pharmacy.dispensing import (
    activate_for_encounter,
    claim_prescription,
    confirm_dispense,
    create_otc_sale,
    prepare_dispense,
)
from pharmacy.models import (
    Dispense,
    OTCSale,
    Prescription,
    PrescriptionClaim,
    PrescriptionItem,
)
from tests.test_s05_billing import check_in, register
from tests.test_s09_inventory import _locations, _product, _receive
from tests.test_s12_dispensing import _draft, _encounter, _stock

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="S-12 PostgreSQL proof gate"
    ),
]


def _role_user(tenant, template="OWNER_ADMIN", prefix="s12-pg"):
    with tenant_atomic(tenant.organisation.id):
        user = User.objects.create_user(
            f"{prefix}-{uuid4().hex[:6]}", "test-password-123"
        )
        OrganisationMembership.objects.create(
            organisation=tenant.organisation, user=user
        )
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=user,
            role=Role.objects.get(
                organisation=tenant.organisation, template_code=template
            ),
            facility=tenant.facility,
        )
        return user


def _active(tenant, client, quantity="10.00", stock_quantity="100.00"):
    stock = _stock(client, tenant, quantity=stock_quantity)
    patient_id = register(client, f"s12-pg-{uuid4().hex[:8]}")
    checked_in = check_in(
        client, patient_id, tenant, f"s12-pg-checkin-{uuid4().hex}"
    )
    encounter = _encounter(client, tenant, patient_id, checked_in["visit_id"])
    drafted = _draft(client, encounter.id, stock["product"]["id"], quantity=quantity)
    assert drafted.status_code == 200, drafted.data
    with tenant_atomic(tenant.organisation.id):
        encounter = type(encounter).objects.get(id=encounter.id)
        encounter.status = "SIGNED"
        encounter.save(update_fields=["status", "updated_at"])
        prescription = activate_for_encounter(
            encounter=encounter, actor=tenant.user
        )
    return stock, prescription, checked_in


def test_pg_s12_force_rls_and_guards(tenant, authed_client, enabled_mig001_target):
    _stock(authed_client, tenant)
    status = rls_status()
    tables = {table["name"]: table for table in status["tables"]}
    for name in (
        "pharmacy_prescription",
        "pharmacy_prescriptionitem",
        "pharmacy_prescriptionclaim",
        "pharmacy_dispense",
        "pharmacy_dispenseline",
        "pharmacy_otcsale",
        "pharmacy_otcsaleline",
    ):
        assert tables[name]["rowsecurity"] is True
        assert tables[name]["force"] is True
        assert tables[name]["owner"] != status["role"]["name"]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT tgname FROM pg_trigger
            WHERE tgrelid = 'pharmacy_otcsale'::regclass
              AND NOT tgisinternal AND tgenabled = 'O'
            """
        )
        assert "klin_klink_otc_evidence_immutable" in {
            row[0] for row in cursor.fetchall()
        }


def test_pg_s12_claim_race_has_one_unique_winner(
    tenant, authed_client, enabled_mig001_target
):
    _stock_row, prescription, _checked_in = _active(tenant, authed_client)
    other = _role_user(tenant)
    organisation = tenant.organisation
    facility = tenant.facility

    def claim(actor_id):
        close_old_connections()
        try:
            with tenant_atomic(organisation.id):
                actor = User.objects.get(id=actor_id)
                claim_row, created = claim_prescription(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    prescription_id=prescription.id,
                )
                return ("ok", created)
        except CanonicalError as exc:
            return ("error", exc.code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(claim, [tenant.user.id, other.id])
        )
    assert sorted(result[0] for result in results) == ["error", "ok"]
    assert [result for result in results if result[0] == "error"][0][1] == (
        "PRESCRIPTION_CLAIMED"
    )
    with tenant_atomic(organisation.id):
        assert (
            PrescriptionClaim.objects.filter(
                prescription_id=prescription.id, released_at__isnull=True
            ).count()
            == 1
        )
        assert AuditEvent.objects.filter(event_code="PRESCRIPTION_CLAIMED").count() == 1


def test_pg_s12_dispense_confirm_race_moves_stock_once(
    tenant, authed_client, enabled_mig001_target
):
    stock, prescription, _checked_in = _active(tenant, authed_client)
    otc_stock = _stock(
        authed_client,
        tenant,
        quantity="5.00",
        prescription_only=False,
        confirm_duplicate=True,
    )
    with tenant_atomic(tenant.organisation.id):
        actor = User.objects.get(id=tenant.user.id)
        claim_row, _created = claim_prescription(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=actor,
            prescription_id=prescription.id,
        )
        item = PrescriptionItem.objects.get(prescription_id=prescription.id)
        dispense = prepare_dispense(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=actor,
            prescription_id=prescription.id,
            lines=[{"prescription_item_id": str(item.id), "quantity": "10.00"}],
        )
        assert claim_row is not None
    organisation = tenant.organisation
    facility = tenant.facility

    def confirm():
        close_old_connections()
        try:
            with tenant_atomic(organisation.id):
                actor = User.objects.get(id=tenant.user.id)
                result = confirm_dispense(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    dispense_id=dispense.id,
                )
                return ("ok", result.status)
        except CanonicalError as exc:
            return ("error", exc.code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: confirm(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    with tenant_atomic(organisation.id):
        assert Dispense.objects.get(id=dispense.id).status == "CONFIRMED"
        assert (
            StockMovement.objects.filter(source_type="DispenseLine").count() == 1
        )
        assert AuditEvent.objects.filter(event_code="DISPENSE_CONFIRMED").count() == 1
        assert BatchLocationBalance.objects.get(
            batch_id=stock["batch_id"], location_id=stock["location_id"]
        ).quantity == Decimal("90.00")


def test_pg_s12_otc_oversell_race_keeps_money_and_stock_consistent(
    tenant, authed_client, enabled_mig001_target
):
    location = _locations(authed_client)[0]
    product = _product(authed_client, prescription_only=False)
    received = _receive(
        authed_client,
        product["id"],
        location["id"],
        quantity="10.00",
    )
    assert received.status_code == 201, received.data
    price = authed_client.post(
        "/api/v1/inventory/prices/",
        {
            "product_id": product["id"],
            "amount": "500.00",
            "effective_from": date.today().isoformat(),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-pg-price-{uuid4().hex}",
    )
    assert price.status_code == 201, price.data
    from inventory.models import StockBatch

    with tenant_atomic(tenant.organisation.id):
        batch = StockBatch.objects.filter(product_id=product["id"]).first()
        batch_id = batch.id
    organisation = tenant.organisation
    facility = tenant.facility
    actor_id = tenant.user.id

    def sell(_index):
        close_old_connections()
        try:
            with tenant_atomic(organisation.id):
                actor = User.objects.get(id=actor_id)
                sale = create_otc_sale(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    lines=[{"product_id": product["id"], "quantity": "8.00"}],
                )
                return ("ok", str(sale.total))
        except CanonicalError as exc:
            return ("error", exc.code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(sell, range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    assert [result for result in results if result[0] == "error"][0][1] == (
        "INSUFFICIENT_STOCK"
    )
    with tenant_atomic(organisation.id):
        assert OTCSale.objects.count() == 1
        assert OTCSale.objects.get().total == Decimal("4000.00")
        assert StockMovement.objects.filter(source_type="OTCSaleLine").count() == 1
        assert BatchLocationBalance.objects.get(batch_id=batch_id).quantity == (
            Decimal("2.00")
        )


def test_pg_s12_evidence_guards_refuse_direct_rewrites(
    tenant, authed_client, enabled_mig001_target
):
    stock, prescription, _checked_in = _active(tenant, authed_client)
    otc_stock = _stock(
        authed_client,
        tenant,
        quantity="5.00",
        prescription_only=False,
        confirm_duplicate=True,
    )
    with tenant_atomic(tenant.organisation.id):
        actor = User.objects.get(id=tenant.user.id)
        claim_prescription(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=actor,
            prescription_id=prescription.id,
        )
        item = PrescriptionItem.objects.get(prescription_id=prescription.id)
        dispense = prepare_dispense(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=actor,
            prescription_id=prescription.id,
            lines=[{"prescription_item_id": str(item.id), "quantity": "2.00"}],
        )
        confirm_dispense(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=actor,
            dispense_id=dispense.id,
        )
        sale = create_otc_sale(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=actor,
            lines=[{"product_id": otc_stock["product"]["id"], "quantity": "1.00"}],
        )
    with pytest.raises(DatabaseError):
        with tenant_atomic(tenant.organisation.id):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE pharmacy_otcsale SET total = total + 1 WHERE id = %s",
                    [str(sale.id)],
                )
    with pytest.raises(DatabaseError):
        with tenant_atomic(tenant.organisation.id):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE pharmacy_dispense SET status = 'CANCELLED' WHERE id = %s",
                    [str(dispense.id)],
                )
    with pytest.raises(DatabaseError):
        with tenant_atomic(tenant.organisation.id):
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE pharmacy_prescriptionitem SET quantity = quantity + 1 WHERE id = %s",
                    [str(item.id)],
                )


def test_pg_s12_dispense_and_payment_serialise_on_the_invoice(
    tenant, authed_client, enabled_mig001_target
):
    stock, prescription, checked_in = _active(tenant, authed_client)
    with tenant_atomic(tenant.organisation.id):
        actor = User.objects.get(id=tenant.user.id)
        claim_prescription(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=actor,
            prescription_id=prescription.id,
        )
        item = PrescriptionItem.objects.get(prescription_id=prescription.id)
        dispense = prepare_dispense(
            organisation=tenant.organisation,
            facility=tenant.facility,
            actor=actor,
            prescription_id=prescription.id,
            lines=[{"prescription_item_id": str(item.id), "quantity": "10.00"}],
        )
    organisation = tenant.organisation
    facility = tenant.facility
    invoice_id = checked_in["invoice_id"]

    def handover():
        close_old_connections()
        try:
            with tenant_atomic(organisation.id):
                actor = User.objects.get(id=tenant.user.id)
                confirm_dispense(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    dispense_id=dispense.id,
                )
                return ("ok", "dispense")
        except CanonicalError as exc:
            return ("error", exc.code)
        finally:
            close_old_connections()

    def payment():
        close_old_connections()
        try:
            with tenant_atomic(organisation.id):
                from billing.services import confirm_payment

                actor = User.objects.get(id=tenant.user.id)
                confirm_payment(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    amount="30000.00",
                    method="CASH",
                    invoice_id=invoice_id,
                )
                return ("ok", "payment")
        except CanonicalError as exc:
            return ("error", exc.code)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda fn: fn(), [handover, payment]))
    assert all(result[0] == "ok" for result in results), results
    with tenant_atomic(organisation.id):
        from billing.models import Invoice

        invoice = Invoice.objects.get(id=invoice_id)
        assert invoice.total == Decimal("35000.00")
        assert invoice.amount_paid == Decimal("30000.00")
        assert invoice.balance == Decimal("5000.00")
        assert invoice.items.filter(source_type="DISPENSE_LINE").count() == 1
        assert (
            StockMovement.objects.filter(source_type="DispenseLine").count() == 1
        )
