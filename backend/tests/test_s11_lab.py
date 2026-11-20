"""S-11 laboratory order, collection, result, release and correction proofs."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from accounts.models import (
    OrganisationMembership,
    Role,
    RolePermission,
    User,
    UserFacilityRole,
)
from audit.models import AuditEvent
from billing.models import Invoice, InvoiceItem
from clinical.models import Encounter
from core.services import tenant_atomic
from laboratory.models import (
    LabAnalyteDefinition,
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
        f"/api/v1/lab/items/{item_id}/release/",
        {"expected_version": saved.data["version_no"]},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s11-release-self",
    )
    assert self_release.status_code == 403
    assert self_release.data["code"] == "SELF_VERIFICATION_NOT_ALLOWED"
    admin_client, _admin = _admin_client(tenant)
    released = admin_client.post(
        f"/api/v1/lab/items/{item_id}/release/",
        {"expected_version": saved.data["version_no"]},
        format="json",
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
        f"/api/v1/lab/items/{item_id}/release/",
        {"expected_version": 1},
        format="json",
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
        analyte = LabAnalyteDefinition.objects.filter(
            test_id=test["id"]
        ).order_by("sequence", "id").first()
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


def _capability_client(tenant, username, codes, *, facility=None):
    """Return a login-bound client with exactly the named capability grants."""

    from rest_framework.test import APIClient

    from accounts.models import OrganisationMembership, Permission

    with tenant_atomic(tenant.organisation.id):
        user = User.objects.create_user(username, "test-password-123")
        OrganisationMembership.objects.create(organisation=tenant.organisation, user=user)
        role = Role.objects.create(
            organisation=tenant.organisation,
            name=f"S-29 lab role {uuid4().hex[:8]}",
            template_code="S29_LAB_SCOPED",
        )
        for code in codes:
            permission, _ = Permission.objects.get_or_create(
                code=code,
                defaults={"name": code, "sensitivity_tier": "T1"},
            )
            RolePermission.objects.create(
                organisation=tenant.organisation, role=role, permission=permission
            )
        UserFacilityRole.objects.create(
            organisation=tenant.organisation,
            user=user,
            role=role,
            facility=facility or tenant.facility,
            department=tenant.department,
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
    client.defaults["HTTP_X_FACILITY_ID"] = str((facility or tenant.facility).id)
    client.credentials(HTTP_AUTHORIZATION="Bearer " + login.data["access_token"])
    return client


def test_s29_r1_worklist_requires_lab_capability_and_scopes_facility(tenant, authed_client):
    """S-29-R1: worklist access follows lab capability, not stock read."""

    patient_id = register(authed_client, "s29-r1-register")
    checked_in = check_in(authed_client, patient_id, tenant, "s29-r1-checkin")
    encounter_id = _encounter(tenant, checked_in["visit_id"])
    test = _test(authed_client, tenant, code="R1LAB")
    ordered = _order(authed_client, encounter_id, test["id"], key="s29-r1-order")
    assert ordered.status_code == 201, ordered.data
    item_id = ordered.data["items"][0]["id"]

    for capability in ("lab.result.entry", "lab.result.verify"):
        client = _capability_client(
            tenant, f"s29-r1-{capability.replace('.', '-')}", (capability,)
        )
        response = client.get("/api/v1/lab/worklist/")
        assert response.status_code == 200, response.data
        assert any(
            row["item_id"] == item_id and row["patient_name"]
            for section_name in (
                "awaiting_payment", "to_collect", "in_bench", "to_verify", "rejected", "released"
            )
            for row in response.data[section_name]
        )

    stock_only = _capability_client(tenant, "s29-r1-stock-only", ("inventory.read",))
    denied = stock_only.get("/api/v1/lab/worklist/")
    assert denied.status_code == 403
    assert not any(
        key in denied.data
        for key in ("awaiting_payment", "to_collect", "in_bench", "to_verify", "rejected", "released")
    )

    from tenancy.models import Facility

    with tenant_atomic(tenant.organisation.id):
        other_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="S-29 second facility",
            code="S29SECOND",
            mode="CLINIC",
        )
    wrong_facility = _capability_client(
        tenant, "s29-r1-other-facility", ("lab.result.entry",)
    )
    wrong_facility.defaults["HTTP_X_FACILITY_ID"] = str(other_facility.id)
    other = wrong_facility.get("/api/v1/lab/worklist/")
    assert other.status_code == 403
    assert not any(
        key in other.data
        for key in ("awaiting_payment", "to_collect", "in_bench", "to_verify", "rejected", "released")
    )

    from rest_framework.test import APIClient
    from tenancy.models import Organisation

    other_organisation = Organisation.objects.create(
        name="S-29 other tenant", slug="s29-other-tenant"
    )
    with tenant_atomic(other_organisation.id):
        other_tenant_facility = Facility.objects.create(
            organisation=other_organisation,
            name="S-29 other tenant facility",
            code="S29OTHER",
            mode="CLINIC",
        )
        other_tenant_user = User.objects.create_user(
            "s29-r1-other-tenant", "test-password-123"
        )
        OrganisationMembership.objects.create(
            organisation=other_organisation, user=other_tenant_user
        )
    foreign = APIClient()
    foreign_login = foreign.post(
        "/api/v1/auth/login/",
        {
            "username": other_tenant_user.username,
            "password": "test-password-123",
            "organisation_id": str(other_organisation.id),
        },
        format="json",
    )
    assert foreign_login.status_code == 200, foreign_login.data
    foreign.defaults["HTTP_X_FACILITY_ID"] = str(other_tenant_facility.id)
    foreign.credentials(HTTP_AUTHORIZATION="Bearer " + foreign_login.data["access_token"])
    foreign_response = foreign.get("/api/v1/lab/worklist/")
    assert foreign_response.status_code == 403
    assert not any(
        key in foreign_response.data
        for key in ("awaiting_payment", "to_collect", "in_bench", "to_verify", "rejected", "released")
    )


def _s30_entered_item(tenant, client, code="S30READ"):
    """Create one collected item with an entered result and its version."""

    patient_id = register(client, f"s30-{code.lower()}-register")
    checked_in = check_in(client, patient_id, tenant, f"s30-{code.lower()}-checkin")
    encounter_id = _encounter(tenant, checked_in["visit_id"])
    test = _test(client, tenant, code=code)
    ordered = _order(client, encounter_id, test["id"], key=f"s30-{code.lower()}-order")
    assert ordered.status_code == 201, ordered.data
    item_id = ordered.data["items"][0]["id"]
    collected = client.post(
        f"/api/v1/lab/items/{item_id}/collect/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY=f"s30-{code.lower()}-collect",
    )
    assert collected.status_code == 200, collected.data
    with tenant_atomic(tenant.organisation.id):
        analytes = list(
            LabAnalyteDefinition.objects.filter(test_id=test["id"]).order_by("sequence", "id")
        )
    saved = client.patch(
        f"/api/v1/lab/items/{item_id}/results/",
        {
            "values": [
                {"analyte_id": str(analyte.id), "value": "13.2" if index == 0 else "6.0"}
                for index, analyte in enumerate(analytes)
            ],
            "complete": True,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=f"s30-{code.lower()}-result",
    )
    assert saved.status_code == 201, saved.data
    return encounter_id, item_id, analytes[0].id


def test_s30_detail_read_is_lab_scoped_and_draft_values_stay_out_of_projections(
    tenant, authed_client
):
    """S-30: only lab roles read a bounded draft; values stay in the domain record."""

    encounter_id, item_id, _analyte_id = _s30_entered_item(tenant, authed_client)
    for capability in ("lab.result.entry", "lab.result.verify"):
        client = _capability_client(
            tenant, f"s30-detail-{capability.replace('.', '-')}", (capability,)
        )
        detail = client.get(f"/api/v1/lab/items/{item_id}/detail/")
        assert detail.status_code == 200, detail.data
        assert detail.data["item_id"] == item_id
        assert detail.data["version_no"] >= 1
        assert detail.data["values"]
        assert any(value["value"] == "13.2" for value in detail.data["values"])

    stock_only = _capability_client(tenant, "s30-detail-stock", ("inventory.read",))
    denied = stock_only.get(f"/api/v1/lab/items/{item_id}/detail/")
    assert denied.status_code == 403
    assert "values" not in denied.data

    from rest_framework.test import APIClient
    from tenancy.models import Facility, Organisation

    with tenant_atomic(tenant.organisation.id):
        second_facility = Facility.objects.create(
            organisation=tenant.organisation,
            name="S-30 second facility",
            code="S30SECOND",
            mode="CLINIC",
        )
    wrong_facility = _capability_client(tenant, "s30-detail-facility", ("lab.result.verify",))
    wrong_facility.defaults["HTTP_X_FACILITY_ID"] = str(second_facility.id)
    other_facility = wrong_facility.get(f"/api/v1/lab/items/{item_id}/detail/")
    assert other_facility.status_code == 403
    assert "values" not in other_facility.data

    other_organisation = Organisation.objects.create(
        name="S-30 other tenant", slug="s30-other-tenant"
    )
    with tenant_atomic(other_organisation.id):
        foreign_facility = Facility.objects.create(
            organisation=other_organisation,
            name="S-30 foreign facility",
            code="S30FOREIGN",
            mode="CLINIC",
        )
        foreign_user = User.objects.create_user("s30-detail-foreign", "test-password-123")
        OrganisationMembership.objects.create(
            organisation=other_organisation, user=foreign_user
        )
    foreign = APIClient()
    foreign_login = foreign.post(
        "/api/v1/auth/login/",
        {
            "username": foreign_user.username,
            "password": "test-password-123",
            "organisation_id": str(other_organisation.id),
        },
        format="json",
    )
    assert foreign_login.status_code == 200, foreign_login.data
    foreign.defaults["HTTP_X_FACILITY_ID"] = str(foreign_facility.id)
    foreign.credentials(HTTP_AUTHORIZATION="Bearer " + foreign_login.data["access_token"])
    foreign_response = foreign.get(f"/api/v1/lab/items/{item_id}/detail/")
    assert foreign_response.status_code in {403, 404}
    assert "values" not in foreign_response.data

    worklist = authed_client.get("/api/v1/lab/worklist/")
    assert worklist.status_code == 200
    assert "13.2" not in str(worklist.data)
    clinician = authed_client.get(f"/api/v1/lab/encounters/{encounter_id}/results/")
    assert clinician.status_code == 200
    assert clinician.data["results"] == []
    with tenant_atomic(tenant.organisation.id):
        read_events = AuditEvent.objects.filter(event_code="LAB_RESULTS_READ")
        assert read_events.exists()
        for event in read_events:
            assert "13.2" not in str(event.after)
            assert "13.2" not in str(event.before)


def test_s30_release_is_bound_to_observed_version(tenant, authed_client):
    """S-30: a stale review cannot release a newer draft version."""

    _encounter_id, item_id, analyte_id = _s30_entered_item(tenant, authed_client, code="S30STALE")
    verifier = _admin_client(tenant)[0]
    detail = verifier.get(f"/api/v1/lab/items/{item_id}/detail/")
    assert detail.status_code == 200, detail.data
    observed_version = detail.data["version_no"]

    with tenant_atomic(tenant.organisation.id):
        analytes = list(
            LabAnalyteDefinition.objects.filter(
                test_id=LabOrderItem.objects.get(id=item_id).test_id
            ).order_by("sequence", "id")
        )
    updated = authed_client.patch(
        f"/api/v1/lab/items/{item_id}/results/",
        {
            "values": [
                {
                    "analyte_id": str(analyte.id),
                    "value": "14.1" if analyte.id == analyte_id else "6.0",
                }
                for analyte in analytes
            ],
            "complete": True,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="s30-stale-second-save",
    )
    assert updated.status_code == 201, updated.data
    assert updated.data["version_no"] == observed_version + 1

    stale = verifier.post(
        f"/api/v1/lab/items/{item_id}/release/",
        {"expected_version": observed_version},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s30-stale-release",
    )
    assert stale.status_code == 412, stale.data
    assert stale.data["code"] == "VERSION_CONFLICT"
    with tenant_atomic(tenant.organisation.id):
        assert LabOrderItem.objects.get(id=item_id).state == "RESULT_ENTERED"
        assert not LabResultVersion.objects.get(
            result__item_id=item_id, version_no=observed_version
        ).released
        assert (
            AuditEvent.objects.filter(event_code="LAB_RESULT_RELEASED").count() == 0
        )

    current = verifier.post(
        f"/api/v1/lab/items/{item_id}/release/",
        {"expected_version": observed_version + 1},
        format="json",
        HTTP_IDEMPOTENCY_KEY="s30-current-release",
    )
    assert current.status_code == 200, current.data
    assert current.data["version_no"] == observed_version + 1
    with tenant_atomic(tenant.organisation.id):
        assert LabOrderItem.objects.get(id=item_id).state == "RELEASED"
        assert AuditEvent.objects.filter(event_code="LAB_RESULT_RELEASED").count() == 1


def test_s30_repeated_result_submit_replays_one_version(tenant, authed_client):
    """S-30: resending one save intent does not create another version."""

    patient_id = register(authed_client, "s30-register-replay")
    checked_in = check_in(authed_client, patient_id, tenant, "s30-checkin-replay")
    encounter_id = _encounter(tenant, checked_in["visit_id"])
    test = _test(authed_client, tenant, code="S30REPLAY")
    ordered = _order(authed_client, encounter_id, test["id"], key="s30-order-replay")
    assert ordered.status_code == 201, ordered.data
    item_id = ordered.data["items"][0]["id"]
    collected = authed_client.post(
        f"/api/v1/lab/items/{item_id}/collect/", {}, format="json",
        HTTP_IDEMPOTENCY_KEY="s30-collect-replay",
    )
    assert collected.status_code == 200, collected.data
    with tenant_atomic(tenant.organisation.id):
        analytes = list(
            LabAnalyteDefinition.objects.filter(test_id=test["id"]).order_by("sequence", "id")
        )
    body = {
        "values": [
            {"analyte_id": str(analyte.id), "value": "12.1" if index == 0 else "6.0"}
            for index, analyte in enumerate(analytes)
        ],
        "complete": True,
    }
    first = authed_client.patch(
        f"/api/v1/lab/items/{item_id}/results/", body, format="json",
        HTTP_IDEMPOTENCY_KEY="s30-save-replay",
    )
    assert first.status_code == 201, first.data
    second = authed_client.patch(
        f"/api/v1/lab/items/{item_id}/results/", body, format="json",
        HTTP_IDEMPOTENCY_KEY="s30-save-replay",
    )
    assert second.status_code == 201, second.data
    assert second.headers["Idempotent-Replay"] == "true"
    with tenant_atomic(tenant.organisation.id):
        assert LabResultVersion.objects.filter(result__item_id=item_id).count() == 1
        assert AuditEvent.objects.filter(event_code="LAB_RESULT_SAVED").count() == 1


def test_s30_worklist_rows_carry_review_fields_and_stable_urgent_order(
    tenant, authed_client
):
    """S-30: worklist rows carry safe review metadata and urgent-first order."""

    patient_id = register(authed_client, "s30-register-queue")
    checked_in = check_in(authed_client, patient_id, tenant, "s30-checkin-queue")
    encounter_id = _encounter(tenant, checked_in["visit_id"])
    test = _test(authed_client, tenant, code="S30QUEUE")
    routine = _order(
        authed_client, encounter_id, test["id"], key="s30-order-routine", priority="ROUTINE"
    )
    assert routine.status_code == 201, routine.data
    urgent = _order(
        authed_client, encounter_id, test["id"], key="s30-order-urgent", priority="URGENT"
    )
    assert urgent.status_code == 201, urgent.data

    worklist = authed_client.get("/api/v1/lab/worklist/")
    assert worklist.status_code == 200, worklist.data
    ids = [row["item_id"] for row in worklist.data["to_collect"]]
    assert ids[0] == urgent.data["items"][0]["id"]
    assert routine.data["items"][0]["id"] in ids
    row = next(item for item in worklist.data["to_collect"] if item["item_id"] == ids[0])
    for key in (
        "test_id",
        "ordered_by_name",
        "elapsed_minutes",
        "rejection_reason",
        "recollection_count",
        "version_no",
    ):
        assert key in row


def test_s30_worklist_supports_bounded_pages(tenant, authed_client):
    """S-30: the worklist can be read in bounded pages without changing its shape."""

    patient_id = register(authed_client, "s30-register-page")
    checked_in = check_in(authed_client, patient_id, tenant, "s30-checkin-page")
    encounter_id = _encounter(tenant, checked_in["visit_id"])
    test = _test(authed_client, tenant, code="S30PAGE")
    for index in range(3):
        ordered = _order(
            authed_client, encounter_id, test["id"], key=f"s30-order-page-{index}"
        )
        assert ordered.status_code == 201, ordered.data

    first = authed_client.get("/api/v1/lab/worklist/?limit=2&offset=0")
    second = authed_client.get("/api/v1/lab/worklist/?limit=2&offset=2")
    assert first.status_code == 200, first.data
    assert second.status_code == 200, second.data
    assert first.data["pagination"]["has_more"] is True
    assert second.data["pagination"]["has_more"] is False
    assert len(first.data["to_collect"]) == 2
    assert len(second.data["to_collect"]) == 1


def test_s30_encounter_payload_shows_status_without_draft_values(tenant, authed_client):
    """S-30: unreleased encounter results expose only work state, never values."""

    encounter_id, item_id, _analyte_id = _s30_entered_item(tenant, authed_client, code="S30ENC")
    before = authed_client.get(f"/api/v1/lab/encounters/{encounter_id}/results/")
    assert before.status_code == 200, before.data
    assert before.data["results"] == []
    assert any(
        row["item_id"] == item_id and row["state"] == "RESULT_ENTERED" and "values" not in row
        for row in before.data["items"]
    )
    assert "13.2" not in str(before.data)
