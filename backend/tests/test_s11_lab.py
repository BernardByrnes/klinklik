"""S-11 laboratory order, collection, result, release and correction proofs."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from accounts.models import OrganisationMembership, Role, User, UserFacilityRole
from audit.models import AuditEvent
from billing.models import Invoice, InvoiceItem
from clinical.models import Encounter
from core.services import tenant_atomic
from laboratory.models import (
    LabOrderItem,
    LabResult,
    LabResultVersion,
    LabTestDefinition,
)
from tests.test_s05_billing import check_in, register

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def s01_target_cutover(enabled_mig001_target):
    return enabled_mig001_target


def _encounter(tenant, visit_id):
    with tenant_atomic(tenant.organisation.id):
        from scheduling.models import Visit

        visit = Visit.objects.get(id=visit_id)
        encounter = Encounter.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=visit.patient,
            visit=visit,
            clinician=tenant.user,
            encounter_no=f"ENC-LAB-{uuid4().hex[:8]}",
            status="OPEN",
        )
        return str(encounter.id)


def _test(client, tenant, code="CBC", analytes=None):
    analytes = analytes or [
        {
            "code": "HB",
            "name": "Haemoglobin",
            "unit": "g/dL",
            "result_type": "NUMERIC",
            "sanity_min": "0",
            "sanity_max": "250",
            "range": {"low": "4", "high": "11", "validated": False},
        },
        {
            "code": "WBC",
            "name": "White cell count",
            "unit": "x10^9/L",
            "result_type": "NUMERIC",
            "sanity_min": "0",
            "sanity_max": "100",
            "range": {"low": "4", "high": "11", "validated": False},
        },
    ]
    response = client.post(
        "/api/v1/lab/tests/",
        {
            "code": code,
            "name": "Synthetic complete blood count",
            "service_id": str(tenant.service.id),
            "specimen_type": "BLOOD",
            "result_type": "PANEL",
            "analytes": analytes,
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    return response.data


def _order(client, encounter_id, test_id, key="lab-order", priority="ROUTINE"):
    return client.post(
        "/api/v1/lab/orders/",
        {
            "encounter_id": encounter_id,
            "test_ids": [test_id],
            "priority": priority,
            "clinical_notes": "Synthetic lab notes",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def _analytes(client, test_id):
    response = client.get("/api/v1/lab/tests/")
    test = next(item for item in response.data if item["id"] == test_id)
    from laboratory.models import LabAnalyteDefinition

    with tenant_atomic_from(test):
        return list(
            LabAnalyteDefinition.objects.filter(test_id=test_id).order_by("sequence")
        )


def tenant_atomic_from(_test):
    from core.services import tenant_atomic

    return tenant_atomic(_test["organisation"])


def _admin_client(tenant):
    from rest_framework.test import APIClient

    with tenant_atomic(tenant.organisation.id):
        user = User.objects.create_user(f"lab-admin-{uuid4().hex[:8]}", "test-password-123")
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


def test_s11_order_collect_enter_release_and_amend(tenant, authed_client):
    patient_id = register(authed_client, "s11-register")
    checked_in = check_in(authed_client, patient_id, tenant, "s11-checkin")
    encounter_id = _encounter(tenant, checked_in["visit_id"])
    test = _test(authed_client, tenant)
    ordered = _order(authed_client, encounter_id, test["id"], key="s11-order")
    assert ordered.status_code == 201, ordered.data
    item_id = ordered.data["items"][0]["id"]
    with tenant_atomic(tenant.organisation.id):
        item = LabOrderItem.objects.get(id=item_id)
        assert item.state == "READY_FOR_COLLECTION"
        assert item.invoice_line is not None
        assert item.invoice_line.source_type == "LAB_ORDER_ITEM"
        invoice = Invoice.objects.get(id=checked_in["invoice_id"])
        assert invoice.balance == Decimal("60000.00")

    worklist = authed_client.get("/api/v1/lab/worklist/")
    assert worklist.status_code == 200
    assert any(row["item_id"] == item_id for row in worklist.data["to_collect"])

    collected = authed_client.post(
        f"/api/v1/lab/items/{item_id}/collect/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY="s11-collect",
    )
    assert collected.status_code == 200, collected.data
    specimen_id = collected.data["specimen_id"]
    assert specimen_id.startswith("SPEC-")

    from laboratory.models import LabAnalyteDefinition

    with tenant_atomic(tenant.organisation.id):
        analytes = list(
            LabAnalyteDefinition.objects.filter(test_id=test["id"]).order_by("sequence")
        )
    values = [
        {"analyte_id": str(analytes[0].id), "value": "13.2"},
        {"analyte_id": str(analytes[1].id), "value": "6.0"},
    ]
    saved = authed_client.patch(
        f"/api/v1/lab/items/{item_id}/results/",
        {"values": values, "complete": True, "comments": "Synthetic result"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s11-result",
    )
    assert saved.status_code == 201, saved.data
    assert saved.data["state"] == "RESULT_ENTERED"
    with tenant_atomic(tenant.organisation.id):
        version = LabResultVersion.objects.get(result__item_id=item_id)
        hb = next(value for value in version.values if value["code"] == "HB")
        assert hb["flag"] == "HIGH"
        assert hb["range_high"] == "11.0000"

    # Clinician cannot read unreleased values.
    before = authed_client.get(f"/api/v1/lab/encounters/{encounter_id}/results/")
    assert before.data["results"] == []
    self_release = authed_client.post(
        f"/api/v1/lab/items/{item_id}/release/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY="s11-release-self",
    )
    assert self_release.status_code == 403
    assert self_release.data["code"] == "SELF_VERIFICATION_NOT_ALLOWED"
    admin_client, _admin = _admin_client(tenant)
    released = admin_client.post(
        f"/api/v1/lab/items/{item_id}/release/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY="s11-release",
    )
    assert released.status_code == 200, released.data
    assert released.data["state"] == "RELEASED"
    with tenant_atomic(tenant.organisation.id):
        assert LabOrderItem.objects.get(id=item_id).state == "RELEASED"
        assert AuditEvent.objects.filter(event_code="LAB_RESULT_RELEASED").count() == 1

    after = authed_client.get(f"/api/v1/lab/encounters/{encounter_id}/results/")
    assert after.status_code == 200
    assert len(after.data["results"]) == 1
    assert after.data["results"][0]["values"][0]["value"] == "13.2"
    with tenant_atomic(tenant.organisation.id):
        assert AuditEvent.objects.filter(event_code="LAB_RESULTS_READ").count() == 2

    amended = admin_client.post(
        f"/api/v1/lab/items/{item_id}/amend/",
        {
            "values": [
                {"analyte_id": str(analytes[0].id), "value": "10.0"},
                {"analyte_id": str(analytes[1].id), "value": "6.0"},
            ],
            "reason": "Synthetic transcription correction",
            "comments": "Amended result",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s11-amend",
    )
    assert amended.status_code == 201, amended.data
    assert amended.data["version_no"] == 2
    with tenant_atomic(tenant.organisation.id):
        versions = LabResultVersion.objects.filter(result__item_id=item_id).order_by("version_no")
        assert versions.count() == 2
        assert versions.last().supersedes_id == versions.first().id
        assert LabResult.objects.get(item_id=item_id).state == "RELEASED"


def test_s11_self_verification_policy_allows_when_enabled(tenant, authed_client):
    from tenancy.models import FacilityWorkflowPolicy

    with tenant_atomic(tenant.organisation.id):
        FacilityWorkflowPolicy.objects.update_or_create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            defaults={"lab_allow_self_verification": True, "updated_by": tenant.user},
        )
    patient_id = register(authed_client, "s11-register-self")
    checked_in = check_in(authed_client, patient_id, tenant, "s11-checkin-self")
    encounter_id = _encounter(tenant, checked_in["visit_id"])
    test = _test(authed_client, tenant, code="SELF")
    ordered = _order(authed_client, encounter_id, test["id"], key="s11-order-self")
    item_id = ordered.data["items"][0]["id"]
    authed_client.post(
        f"/api/v1/lab/items/{item_id}/collect/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY="s11-collect-self",
    )
    from laboratory.models import LabAnalyteDefinition

    with tenant_atomic(tenant.organisation.id):
        analytes = list(LabAnalyteDefinition.objects.filter(test_id=test["id"]).order_by("sequence"))
    authed_client.patch(
        f"/api/v1/lab/items/{item_id}/results/",
        {
            "values": [
                {"analyte_id": str(analytes[0].id), "value": "8.0"},
                {"analyte_id": str(analytes[1].id), "value": "5.0"},
            ],
            "complete": True,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s11-result-self",
    )
    released = authed_client.post(
        f"/api/v1/lab/items/{item_id}/release/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY="s11-release-self-policy",
    )
    assert released.status_code == 200, released.data
    assert released.data["self_verified"] is True


def test_s11_cancel_before_collection_voids_unpaid_line(tenant, authed_client):
    # CMD-047 — mechanical evidence for s17-cmd-audit.
    patient_id = register(authed_client, "s11-register-cancel")
    checked_in = check_in(authed_client, patient_id, tenant, "s11-checkin-cancel")
    encounter_id = _encounter(tenant, checked_in["visit_id"])
    test = _test(authed_client, tenant, code="CANCEL")
    ordered = _order(authed_client, encounter_id, test["id"], key="s11-order-cancel")
    item_id = ordered.data["items"][0]["id"]
    cancelled = authed_client.post(
        f"/api/v1/lab/items/{item_id}/cancel/",
        {"reason": "Synthetic ordering error"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s11-cancel",
    )
    assert cancelled.status_code == 200, cancelled.data
    assert cancelled.data["state"] == "CANCELLED"
    with tenant_atomic(tenant.organisation.id):
        item = LabOrderItem.objects.get(id=item_id)
        assert item.invoice_line.state == "VOIDED"
        assert Invoice.objects.get(id=checked_in["invoice_id"]).balance == Decimal("30000.00")


def test_s11_rejection_recollection_does_not_duplicate_charge(tenant, authed_client):
    patient_id = register(authed_client, "s11-register-reject")
    checked_in = check_in(authed_client, patient_id, tenant, "s11-checkin-reject")
    encounter_id = _encounter(tenant, checked_in["visit_id"])
    test = _test(authed_client, tenant, code="REJECT")
    ordered = _order(authed_client, encounter_id, test["id"], key="s11-order-reject")
    item_id = ordered.data["items"][0]["id"]
    authed_client.post(
        f"/api/v1/lab/items/{item_id}/collect/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY="s11-collect-reject",
    )
    rejected = authed_client.post(
        f"/api/v1/lab/items/{item_id}/reject/",
        {"reason": "Synthetic haemolysed sample"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s11-reject",
    )
    assert rejected.status_code == 200
    with tenant_atomic(tenant.organisation.id):
        assert LabOrderItem.objects.get(id=item_id).state == "SAMPLE_REJECTED"
        lines_before = InvoiceItem.objects.filter(
            invoice_id=checked_in["invoice_id"], source_type="LAB_ORDER_ITEM"
        ).count()
    recollected = authed_client.post(
        f"/api/v1/lab/items/{item_id}/collect/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY="s11-recollect",
    )
    assert recollected.status_code == 200
    with tenant_atomic(tenant.organisation.id):
        assert LabOrderItem.objects.get(id=item_id).state == "SAMPLE_COLLECTED"
        assert (
            InvoiceItem.objects.filter(
                invoice_id=checked_in["invoice_id"], source_type="LAB_ORDER_ITEM"
            ).count()
            == lines_before
        )


def test_s11_result_validation_coded_sanity_and_partial_save(tenant, authed_client):
    patient_id = register(authed_client, "s11-register-validation")
    checked_in = check_in(authed_client, patient_id, tenant, "s11-checkin-validation")
    encounter_id = _encounter(tenant, checked_in["visit_id"])
    test = _test(
        authed_client,
        tenant,
        code="CODED",
        analytes=[
            {
                "code": "MAL",
                "name": "Malaria RDT",
                "result_type": "CODED",
                "coded_options": ["POSITIVE", "NEGATIVE", "INVALID"],
            }
        ],
    )
    ordered = _order(authed_client, encounter_id, test["id"], key="s11-order-coded")
    item_id = ordered.data["items"][0]["id"]
    authed_client.post(
        f"/api/v1/lab/items/{item_id}/collect/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY="s11-collect-coded",
    )
    from laboratory.models import LabAnalyteDefinition

    with tenant_atomic(tenant.organisation.id):
        analyte = LabAnalyteDefinition.objects.get(test_id=test["id"])
    invalid = authed_client.patch(
        f"/api/v1/lab/items/{item_id}/results/",
        {
            "values": [{"analyte_id": str(analyte.id), "value": "INVALID"}],
            "complete": True,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s11-result-invalid",
    )
    assert invalid.status_code == 400
    free_text = authed_client.patch(
        f"/api/v1/lab/items/{item_id}/results/",
        {
            "values": [{"analyte_id": str(analyte.id), "value": "MAYBE"}],
            "complete": True,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s11-result-free",
    )
    assert free_text.status_code == 400
    draft = authed_client.patch(
        f"/api/v1/lab/items/{item_id}/results/",
        {
            "values": [{"analyte_id": str(analyte.id), "value": "NEGATIVE"}],
            "complete": False,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s11-result-draft",
    )
    assert draft.status_code == 201
    assert draft.data["state"] == "DRAFT"
    with tenant_atomic(tenant.organisation.id):
        assert LabOrderItem.objects.get(id=item_id).state == "SAMPLE_COLLECTED"
