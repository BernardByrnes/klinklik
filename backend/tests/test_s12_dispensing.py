"""S-12 prescribing, dispensing and OTC service/API proofs."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from audit.models import AuditEvent
from billing.models import Invoice
from clinical.models import Encounter
from core.errors import CanonicalError
from core.services import tenant_atomic
from inventory.models import (
    BatchLocationBalance,
    StockBatch,
    StockLocation,
    StockMovement,
)
from pharmacy.dispensing import (
    activate_for_encounter,
    claim_prescription,
    confirm_dispense,
    prepare_dispense,
    record_not_dispensed,
    save_draft,
)
from pharmacy.models import (
    Dispense,
    DispenseLine,
    MedicationProduct,
    OTCSale,
    Prescription,
    PrescriptionClaim,
    PrescriptionItem,
    ProductPrice,
)
from scheduling.models import Visit
from tests.test_s05_billing import check_in, register
from tests.test_s09_inventory import _locations, _product, _receive

pytestmark = pytest.mark.django_db
TODAY = date.today()


@pytest.fixture(autouse=True)
def s01_target_cutover(enabled_mig001_target):
    return enabled_mig001_target


def _stock(client, tenant, quantity="100.00", expiry=None, **product_overrides):
    location = _locations(client)[0]
    product = _product(client, **product_overrides)
    receipt = _receive(
        client,
        product["id"],
        location["id"],
        quantity=quantity,
        expiry=expiry or (TODAY + timedelta(days=365)),
    )
    assert receipt.status_code == 201, receipt.data
    price = client.post(
        "/api/v1/inventory/prices/",
        {
            "product_id": product["id"],
            "amount": "500.00",
            "effective_from": TODAY.isoformat(),
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-price-{uuid4().hex}",
    )
    assert price.status_code == 201, price.data
    with tenant_atomic(tenant.organisation.id):
        batch_id = str(
            StockBatch.objects.filter(product_id=product["id"]).first().id
        )
        location_id = str(StockLocation.objects.filter(id=location["id"]).first().id)
    return {
        "product": product,
        "batch_id": batch_id,
        "location_id": location_id,
    }


def _encounter(client, tenant, patient_id, visit_id, status="OPEN"):
    with tenant_atomic(tenant.organisation.id):
        visit = Visit.objects.get(id=visit_id)
        encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=visit.patient,
            visit=visit,
            clinician=tenant.user,
            encounter_no=f"ENC-RX-{uuid4().hex[:8]}",
            status=status,
        )
        return encounter


def _visit(client, tenant):
    patient_id = register(client, f"s12-patient-{uuid4().hex}")
    checked_in = check_in(client, patient_id, tenant, f"s12-checkin-{uuid4().hex}")
    return patient_id, checked_in


def _draft(client, encounter_id, product_id, quantity="10.00", key=None):
    return client.patch(
        "/api/v1/pharmacy/prescriptions/draft/",
        {
            "encounter_id": str(encounter_id),
            "items": [
                {
                    "product_id": str(product_id),
                    "dose_amount": "1.00",
                    "dose_unit": "TABLET",
                    "route": "PO",
                    "frequency": "BD",
                    "duration_value": 5,
                    "duration_unit": "DAYS",
                    "quantity": quantity,
                    "instructions": "Synthetic S12 instructions",
                }
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key or f"s12-draft-{uuid4().hex}",
    )


def _active_prescription(client, tenant, product_id, quantity="10.00"):
    patient_id, checked_in = _visit(client, tenant)
    encounter = _encounter(client, tenant, patient_id, checked_in["visit_id"])
    drafted = _draft(client, encounter.id, product_id, quantity=quantity)
    assert drafted.status_code == 200, drafted.data
    with tenant_atomic(tenant.organisation.id):
        encounter = Encounter.objects.get(id=encounter.id)
        encounter.status = "SIGNED"
        encounter.save(update_fields=["status", "updated_at"])
        prescription = activate_for_encounter(encounter=encounter, actor=tenant.user)
        return prescription, checked_in


def test_s12_draft_activation_and_queue_projection(tenant, authed_client):
    stock = _stock(authed_client, tenant)
    patient_id, checked_in = _visit(authed_client, tenant)
    encounter = _encounter(authed_client, tenant, patient_id, checked_in["visit_id"])
    drafted = _draft(authed_client, encounter.id, stock["product"]["id"])
    assert drafted.status_code == 200, drafted.data
    assert drafted.data["status"] == "DRAFT"
    assert drafted.data["items"][0]["state"] == "PENDING"

    with tenant_atomic(tenant.organisation.id):
        encounter = Encounter.objects.get(id=encounter.id)
        encounter.status = "SIGNED"
        encounter.save(update_fields=["status", "updated_at"])
        prescription = activate_for_encounter(encounter=encounter, actor=tenant.user)
        assert prescription.status == "ACTIVE"
        assert AuditEvent.objects.filter(
            event_code="PRESCRIPTION_ACTIVATED", entity_id=prescription.id
        ).count() == 1

    queue = authed_client.get("/api/v1/pharmacy/queue/")
    assert queue.status_code == 200, queue.data
    assert any(
        row["prescription_id"] == str(prescription.id) for row in queue.data["active"]
    )
    assert queue.data["uncollected_window_days"] == 7


def test_s12_controlled_medicine_is_refused_outright(tenant, authed_client):
    product = _product(authed_client, controlled=True)
    patient_id, checked_in = _visit(authed_client, tenant)
    encounter = _encounter(authed_client, tenant, patient_id, checked_in["visit_id"])
    response = _draft(authed_client, encounter.id, product["id"])
    assert response.status_code == 403, response.data
    assert response.data["code"] == "CONTROLLED_NOT_SUPPORTED"
    with tenant_atomic(tenant.organisation.id):
        assert Prescription.objects.filter(encounter_id=encounter.id).count() == 0


def test_s12_claim_has_exactly_one_winner(tenant, authed_client):
    stock = _stock(authed_client, tenant)
    prescription, _checked_in = _active_prescription(
        authed_client, tenant, stock["product"]["id"]
    )
    first = authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/claim/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-claim-a-{uuid4().hex}",
    )
    assert first.status_code == 201, first.data
    replay = authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/claim/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-claim-b-{uuid4().hex}",
    )
    assert replay.status_code == 200, replay.data
    assert replay.data["created"] is False

    with tenant_atomic(tenant.organisation.id):
        other = User.objects.create_user(
            f"s12-other-{uuid4().hex[:6]}", "test-password-123"
        )
        OrganisationMembership.objects.create(
            organisation=tenant.organisation, user=other
        )
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=other,
            role=Role.objects.get(
                organisation=tenant.organisation, template_code="OWNER_ADMIN"
            ),
            facility=tenant.facility,
        )
        organisation = tenant.organisation
        facility = tenant.facility
    other_client = authed_client.__class__()
    login = other_client.post(
        "/api/v1/auth/login/",
        {
            "username": other.username,
            "password": "test-password-123",
            "organisation_id": str(organisation.id),
        },
        format="json",
    )
    other_client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    other_client.defaults["HTTP_X_FACILITY_ID"] = str(facility.id)
    denied = other_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/claim/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-claim-c-{uuid4().hex}",
    )
    assert denied.status_code == 409
    assert denied.data["code"] == "PRESCRIPTION_CLAIMED"
    with tenant_atomic(tenant.organisation.id):
        assert PrescriptionClaim.objects.filter(
            prescription_id=prescription.id, released_at__isnull=True
        ).count() == 1


def test_s12_dispense_moves_stock_and_charges_one_exact_snapshot(
    tenant, authed_client
):
    stock = _stock(authed_client, tenant, quantity="100.00")
    prescription, checked_in = _active_prescription(
        authed_client, tenant, stock["product"]["id"], quantity="10.00"
    )
    claimed = authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/claim/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-claim-d-{uuid4().hex}",
    )
    assert claimed.status_code == 201, claimed.data
    with tenant_atomic(tenant.organisation.id):
        item = PrescriptionItem.objects.get(prescription_id=prescription.id)
    prepared = authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/dispenses/",
        {"lines": [{"prescription_item_id": str(item.id), "quantity": "10.00"}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-prepare-{uuid4().hex}",
    )
    assert prepared.status_code == 201, prepared.data
    assert prepared.data["status"] == "PROVISIONAL"
    assert prepared.data["total"] == "5000.00"
    dispense_id = prepared.data["id"]
    assert prepared.data["lines"][0]["batch_id"] == stock["batch_id"]
    with tenant_atomic(tenant.organisation.id):
        assert StockMovement.objects.filter(
            source_type="DispenseLine"
        ).count() == 0

    confirmed = authed_client.post(
        f"/api/v1/pharmacy/dispenses/{dispense_id}/confirm/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-confirm-{uuid4().hex}",
    )
    assert confirmed.status_code == 200, confirmed.data
    assert confirmed.data["status"] == "CONFIRMED"
    with tenant_atomic(tenant.organisation.id):
        movement = StockMovement.objects.get(source_type="DispenseLine")
        assert movement.movement_type == "OUT_DISPENSE"
        assert movement.quantity == Decimal("-10.00")
        balance = BatchLocationBalance.objects.get(
            batch_id=stock["batch_id"], location_id=stock["location_id"]
        )
        assert balance.quantity == Decimal("90.00")
        item = PrescriptionItem.objects.get(id=item.id)
        assert item.state == "DISPENSED"
        invoice = Invoice.objects.get(id=checked_in["invoice_id"])
        charge = invoice.items.get(source_type="DISPENSE_LINE")
        assert charge.amount == Decimal("5000.00")
        assert invoice.total == Decimal("35000.00")
        assert AuditEvent.objects.filter(event_code="DISPENSE_CONFIRMED").count() == 1
        assert AuditEvent.objects.filter(event_code="INVOICE_LINE_ADDED").count() >= 1
        assert Dispense.objects.get(id=dispense_id).status == "CONFIRMED"


def test_s12_expired_batch_blocks_handover_and_rolls_back(tenant, authed_client):
    stock = _stock(authed_client, tenant, quantity="20.00")
    prescription, checked_in = _active_prescription(
        authed_client, tenant, stock["product"]["id"], quantity="5.00"
    )
    authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/claim/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-claim-e-{uuid4().hex}",
    )
    with tenant_atomic(tenant.organisation.id):
        item = PrescriptionItem.objects.get(prescription_id=prescription.id)
    prepared = authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/dispenses/",
        {"lines": [{"prescription_item_id": str(item.id), "quantity": "5.00"}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-prepare-e-{uuid4().hex}",
    )
    assert prepared.status_code == 201, prepared.data
    with tenant_atomic(tenant.organisation.id):
        StockBatch.objects.filter(id=stock["batch_id"]).update(
            expiry_date=TODAY - timedelta(days=1)
        )
    confirmed = authed_client.post(
        f"/api/v1/pharmacy/dispenses/{prepared.data['id']}/confirm/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-confirm-e-{uuid4().hex}",
    )
    assert confirmed.status_code == 422
    assert confirmed.data["code"] == "EXPIRED_BATCH"
    with tenant_atomic(tenant.organisation.id):
        assert StockMovement.objects.filter(source_type="DispenseLine").count() == 0
        assert (
            Invoice.objects.get(id=checked_in["invoice_id"])
            .items.filter(source_type="DISPENSE_LINE")
            .count()
            == 0
        )
        assert Dispense.objects.get(id=prepared.data["id"]).status == "PROVISIONAL"


def test_s12_substitution_requires_same_generic_and_consultation_evidence(
    tenant, authed_client
):
    stock = _stock(authed_client, tenant, quantity="50.00")
    alternative = _stock(
        authed_client,
        tenant,
        quantity="50.00",
        brand_name="Other Brand",
        confirm_duplicate=True,
    )
    prescription, _checked_in = _active_prescription(
        authed_client, tenant, stock["product"]["id"], quantity="2.00"
    )
    authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/claim/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-claim-f-{uuid4().hex}",
    )
    with tenant_atomic(tenant.organisation.id):
        item = PrescriptionItem.objects.get(prescription_id=prescription.id)
    no_reason = authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/dispenses/",
        {
            "lines": [
                {
                    "prescription_item_id": str(item.id),
                    "product_id": alternative["product"]["id"],
                    "quantity": "2.00",
                }
            ]
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-sub-a-{uuid4().hex}",
    )
    assert no_reason.status_code == 400
    no_consult = authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/dispenses/",
        {
            "lines": [
                {
                    "prescription_item_id": str(item.id),
                    "product_id": alternative["product"]["id"],
                    "quantity": "2.00",
                    "substitution_reason": "Same generic in stock",
                }
            ]
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-sub-b-{uuid4().hex}",
    )
    assert no_consult.status_code == 409
    assert no_consult.data["code"] == "SUBSTITUTION_EVIDENCE_REQUIRED"
    accepted = authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/dispenses/",
        {
            "lines": [
                {
                    "prescription_item_id": str(item.id),
                    "product_id": alternative["product"]["id"],
                    "quantity": "2.00",
                    "substitution_reason": "Same generic in stock",
                    "prescriber_consulted": True,
                    "prescriber_consulted_name": "Synthetic Prescriber",
                }
            ]
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-sub-c-{uuid4().hex}",
    )
    assert accepted.status_code == 201, accepted.data
    line = accepted.data["lines"][0]
    assert line["substitution_reason"] == "Same generic in stock"
    assert line["prescriber_consulted"] is True
    assert line["prescriber_consulted_name"] == "Synthetic Prescriber"


def test_s12_oversell_is_refused_before_any_dispense_exists(tenant, authed_client):
    stock = _stock(authed_client, tenant, quantity="3.00")
    prescription, _checked_in = _active_prescription(
        authed_client, tenant, stock["product"]["id"], quantity="10.00"
    )
    authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/claim/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-claim-g-{uuid4().hex}",
    )
    with tenant_atomic(tenant.organisation.id):
        item = PrescriptionItem.objects.get(prescription_id=prescription.id)
    response = authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/dispenses/",
        {"lines": [{"prescription_item_id": str(item.id), "quantity": "10.00"}]},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-oversell-{uuid4().hex}",
    )
    assert response.status_code == 409
    assert response.data["code"] == "INSUFFICIENT_STOCK"
    with tenant_atomic(tenant.organisation.id):
        assert Dispense.objects.filter(prescription_id=prescription.id).count() == 0
        assert StockMovement.objects.filter(source_type="DispenseLine").count() == 0


@pytest.mark.parametrize("customer_kind", ["anonymous", "name-only", "patient"])
def test_s12_otc_sells_stock_and_money_atomically(
    tenant, authed_client, customer_kind
):
    stock = _stock(authed_client, tenant, quantity="10.00", prescription_only=False)
    payload = {
        "method": "CASH",
        "lines": [{"product_id": stock["product"]["id"], "quantity": "3.00"}],
    }
    if customer_kind == "name-only":
        payload["customer_name"] = "Synthetic Walk-in"
    if customer_kind == "patient":
        patient_id, _checked_in = _visit(authed_client, tenant)
        payload["patient_id"] = patient_id
    response = authed_client.post(
        "/api/v1/pharmacy/otc/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-otc-{uuid4().hex}",
    )
    assert response.status_code == 201, response.data
    assert response.data["total"] == "1500.00"
    with tenant_atomic(tenant.organisation.id):
        sale = OTCSale.objects.get(id=response.data["id"])
        assert sale.total == Decimal("1500.00")
        assert sale.state == "CONFIRMED"
        movement = StockMovement.objects.get(source_type="OTCSaleLine")
        assert movement.movement_type == "OUT_SALE"
        assert movement.quantity == Decimal("-3.00")
        assert BatchLocationBalance.objects.get(
            batch_id=stock["batch_id"], location_id=stock["location_id"]
        ).quantity == Decimal("7.00")
        assert AuditEvent.objects.filter(event_code="OTC_SALE_COMPLETED").count() == 1


def test_s12_otc_oversell_leaves_no_money_or_stock_partial(tenant, authed_client):
    stock = _stock(authed_client, tenant, quantity="2.00", prescription_only=False)
    response = authed_client.post(
        "/api/v1/pharmacy/otc/",
        {
            "lines": [{"product_id": stock["product"]["id"], "quantity": "5.00"}],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-otc-over-{uuid4().hex}",
    )
    assert response.status_code == 409
    assert response.data["code"] == "INSUFFICIENT_STOCK"
    with tenant_atomic(tenant.organisation.id):
        assert OTCSale.objects.count() == 0
        assert StockMovement.objects.filter(source_type="OTCSaleLine").count() == 0


def test_s12_otc_refuses_controlled_and_prescription_only(tenant, authed_client):
    controlled = _product(authed_client, controlled=True)
    rx_only = _stock(
        authed_client, tenant, quantity="5.00", prescription_only=True, confirm_duplicate=True
    )
    for stock, code in (
        ({"product": controlled}, "CONTROLLED_NOT_SUPPORTED"),
        (rx_only, "PRESCRIPTION_REQUIRED"),
    ):
        response = authed_client.post(
            "/api/v1/pharmacy/otc/",
            {"lines": [{"product_id": stock["product"]["id"], "quantity": "1.00"}]},
            format="json",
            HTTP_IDEMPOTENCY_KEY=f"s12-otc-denied-{uuid4().hex}",
        )
        assert response.status_code == 403
        assert response.data["code"] == code
    with tenant_atomic(tenant.organisation.id):
        assert OTCSale.objects.count() == 0
        assert StockMovement.objects.filter(source_type="OTCSaleLine").count() == 0


def test_s12_not_dispensed_reason_and_uncollected_projection(tenant, authed_client):
    stock = _stock(authed_client, tenant)
    prescription, _checked_in = _active_prescription(
        authed_client, tenant, stock["product"]["id"]
    )
    with tenant_atomic(tenant.organisation.id):
        item = PrescriptionItem.objects.get(prescription_id=prescription.id)
    response = authed_client.post(
        f"/api/v1/pharmacy/items/{item.id}/not-dispensed/",
        {"reason": "OUT_OF_STOCK"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-notdisp-{uuid4().hex}",
    )
    assert response.status_code == 200, response.data
    assert response.data["state"] == "NOT_DISPENSED"
    assert response.data["not_dispensed_reason"] == "OUT_OF_STOCK"

    patient_id, checked_in = _visit(authed_client, tenant)
    encounter = _encounter(authed_client, tenant, patient_id, checked_in["visit_id"])
    drafted = _draft(authed_client, encounter.id, stock["product"]["id"])
    assert drafted.status_code == 200
    with tenant_atomic(tenant.organisation.id):
        encounter = Encounter.objects.get(id=encounter.id)
        encounter.status = "SIGNED"
        encounter.save(update_fields=["status", "updated_at"])
        stale = activate_for_encounter(encounter=encounter, actor=tenant.user)
        Prescription.objects.filter(id=stale.id).update(
            created_at=stale.created_at - timedelta(days=10)
        )
    queue = authed_client.get("/api/v1/pharmacy/queue/")
    assert queue.status_code == 200
    assert any(
        row["prescription_id"] == str(stale.id) for row in queue.data["uncollected"]
    )


def test_s12_permissions_and_tenant_isolation(tenant, authed_client):
    stock = _stock(authed_client, tenant)
    prescription, _checked_in = _active_prescription(
        authed_client, tenant, stock["product"]["id"]
    )
    with tenant_atomic(tenant.organisation.id):
        nurse = User.objects.create_user(
            f"s12-nurse-{uuid4().hex[:6]}", "test-password-123"
        )
        OrganisationMembership.objects.create(
            organisation=tenant.organisation, user=nurse
        )
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=nurse,
            role=Role.objects.get(
                organisation=tenant.organisation, template_code="NURSE_TRIAGE"
            ),
            facility=tenant.facility,
        )
    nurse_client = authed_client.__class__()
    login = nurse_client.post(
        "/api/v1/auth/login/",
        {
            "username": nurse.username,
            "password": "test-password-123",
            "organisation_id": str(tenant.organisation.id),
        },
        format="json",
    )
    nurse_client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    nurse_client.defaults["HTTP_X_FACILITY_ID"] = str(tenant.facility.id)
    denied = nurse_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/claim/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-denied-{uuid4().hex}",
    )
    assert denied.status_code == 403
    queue = nurse_client.get("/api/v1/pharmacy/queue/")
    assert queue.status_code == 403

    with tenant_atomic(tenant.organisation.id):
        other = User.objects.create_user(
            f"s12-admin-{uuid4().hex[:6]}", "test-password-123"
        )
        other_org = OrganisationMembership.objects.create(
            organisation=tenant.organisation, user=other
        )
        assert other_org is not None
    assert authed_client.get(f"/api/v1/pharmacy/dispenses/{uuid4()}/").status_code == 404


def test_s12_audit_redacts_no_clinical_payload(tenant, authed_client):
    stock = _stock(authed_client, tenant)
    prescription, _checked_in = _active_prescription(
        authed_client, tenant, stock["product"]["id"]
    )
    with tenant_atomic(tenant.organisation.id):
        events = AuditEvent.objects.filter(
            event_code__in=(
                "PRESCRIPTION_DRAFT_SAVED",
                "PRESCRIPTION_ACTIVATED",
            )
        )
        for event in events:
            payload = str(event.after)
            assert "Synthetic S12 instructions" not in payload
            assert "medicine_name" not in payload
        assert events.count() >= 2


def test_s12_draft_replaces_once_and_supports_external_items(tenant, authed_client):
    stock = _stock(authed_client, tenant)
    patient_id, checked_in = _visit(authed_client, tenant)
    encounter = _encounter(authed_client, tenant, patient_id, checked_in["visit_id"])
    first = _draft(authed_client, encounter.id, stock["product"]["id"], quantity="4.00")
    assert first.status_code == 200, first.data
    second = authed_client.patch(
        "/api/v1/pharmacy/prescriptions/draft/",
        {
            "encounter_id": str(encounter.id),
            "items": [
                {
                    "product_id": stock["product"]["id"],
                    "quantity": "6.00",
                },
                {
                    "medicine_name": "Synthetic external medicine",
                    "quantity": "2.00",
                },
            ],
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-draft-replace-{uuid4().hex}",
    )
    assert second.status_code == 200, second.data
    assert len(second.data["items"]) == 2
    assert second.data["items"][0]["quantity"] == "6.00"
    assert second.data["items"][1]["external"] is True
    with tenant_atomic(tenant.organisation.id):
        assert Prescription.objects.filter(encounter_id=encounter.id).count() == 1
        assert PrescriptionItem.objects.filter(
            prescription_id=first.data["id"]
        ).count() == 2
    zero = _draft(authed_client, encounter.id, stock["product"]["id"], quantity="0.00")
    assert zero.status_code == 400


def test_s12_signed_encounter_refuses_new_prescription(tenant, authed_client):
    stock = _stock(authed_client, tenant)
    patient_id, checked_in = _visit(authed_client, tenant)
    encounter = _encounter(
        authed_client, tenant, patient_id, checked_in["visit_id"], status="SIGNED"
    )
    response = _draft(authed_client, encounter.id, stock["product"]["id"])
    assert response.status_code == 409
    assert response.data["code"] == "INVALID_STATE"


def test_s12_cancel_retains_items_and_cancels_pending_only(tenant, authed_client):
    stock = _stock(authed_client, tenant, quantity="100.00")
    prescription, _checked_in = _active_prescription(
        authed_client, tenant, stock["product"]["id"], quantity="4.00"
    )
    response = authed_client.post(
        f"/api/v1/pharmacy/prescriptions/{prescription.id}/cancel/",
        {"reason": "Synthetic prescriber cancellation"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-cancel-prescription-{uuid4().hex}",
    )
    assert response.status_code == 200, response.data
    assert response.data["status"] == "CANCELLED"
    with tenant_atomic(tenant.organisation.id):
        items = PrescriptionItem.objects.filter(prescription_id=prescription.id)
        assert items.count() == 1
        assert items.first().state == "CANCELLED"
        assert AuditEvent.objects.filter(
            event_code="PRESCRIPTION_CANCELLED", entity_id=prescription.id
        ).count() == 1


def test_s12_instruction_template_has_version_and_audit(tenant, authed_client):
    stock = _stock(authed_client, tenant)
    product = stock["product"]
    response = authed_client.patch(
        f"/api/v1/pharmacy/products/{product['id']}/instruction-template/",
        {"content": "Take with food", "expected_version": product["version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-template-{uuid4().hex}",
    )
    assert response.status_code == 200, response.data
    assert response.data["instructions_template"] == "Take with food"
    assert response.data["version"] == product["version"] + 1
    stale = authed_client.patch(
        f"/api/v1/pharmacy/products/{product['id']}/instruction-template/",
        {"content": "Take after food", "expected_version": product["version"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s12-template-stale-{uuid4().hex}",
    )
    assert stale.status_code == 409
    with tenant_atomic(tenant.organisation.id):
        assert AuditEvent.objects.filter(
            event_code="PRODUCT_INSTRUCTION_TEMPLATE_SET"
        ).count() == 1
