from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, Event, Lock
from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, connections, transaction
from django.utils import timezone

from accounts.models import User
from application.reception.commands import (
    arrival_enquiry_record,
    patient_register,
    visit_cancel_error,
    visit_check_in,
)
from application.reception.visit_query import get_visit_projection
from audit.models import AuditEvent
from billing.models import Invoice, InvoiceItem, PriceList, ServiceCatalogItem, ServicePrice, VisitPayerBinding
from clinical.models import Encounter
from clinical.services import start_encounter
from core.errors import CanonicalError
from core.models import MigrationCutover, MigrationReconciliation
from core.migration_reconciliation import (
    backfill_mig001,
    cutover_mig001,
    inventory_mig001,
    legacy_writes_enabled,
    rollback_mig001,
    resolve_reconciliation,
    target_writes_enabled,
    verify_mig001,
)
from core.rls import rls_status
from core.services import run_in_tenant, tenant_atomic
from patients.models import Patient
from scheduling.models import ArrivalEnquiry, QueueEntry, Visit
from scheduling.services import check_in_patient, open_visit
from tenancy.models import Department, Facility, FacilityWorkflowPolicy, Organisation


pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="S-01 PostgreSQL proof gate"),
]


CHARGEABLE_TYPES = {"OUTPATIENT_NEW", "OUTPATIENT_REVIEW", "ANC", "FOLLOW_UP_RESULTS"}


def _sqlstate(error):
    cause = error.value if hasattr(error, "value") else error
    seen = set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        state = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
        state = state or getattr(getattr(cause, "diag", None), "sqlstate", None)
        if state:
            return state
        cause = getattr(cause, "__cause__", None) or getattr(cause, "__context__", None)
    return None


def _new_patient(tenant, label):
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        return Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S01-{label}-{uuid4().hex[:8]}",
            first_name="Synthetic",
            last_name=label,
            sex="UNKNOWN",
            date_of_birth=date(1980, 1, 1),
        )


def _race(tenant, operation):
    barrier = Barrier(2)

    def attempt():
        connections.close_all()
        try:
            def callback():
                barrier.wait(timeout=20)
                return operation()

            try:
                return ("ok", run_in_tenant(tenant.organisation.id, callback))
            except (CanonicalError, ValueError) as exc:
                return ("error", getattr(exc, "code", str(exc)))
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(lambda _item: attempt(), range(2)))


def test_pg_competing_registrations_have_one_patient_and_one_duplicate_resolution(tenant):
    payload = {
        "first_name": "Competing",
        "last_name": "Registration",
        "sex": "FEMALE",
        "date_of_birth": date(1990, 1, 1),
        "phone": "0700000001",
    }

    def operation():
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        actor = User.objects.get(id=tenant.user.id)
        outcome = patient_register(
            organisation=organisation,
            actor=actor,
            data=payload,
        )
        return (
            outcome.created,
            str(outcome.patient.id) if outcome.patient is not None else None,
            tuple(str(candidate.id) for candidate in outcome.duplicate_candidates),
        )

    results = _race(tenant, operation)

    assert sorted(result[0] for result in results) == ["ok", "ok"]
    assert sorted(result[1][0] for result in results) == [False, True]
    duplicate_result = next(result[1] for result in results if not result[1][0])
    created_result = next(result[1] for result in results if result[1][0])
    assert duplicate_result[2] == (created_result[1],)
    with tenant_atomic(tenant.organisation.id):
        assert Patient.objects.filter(organisation=tenant.organisation, last_name="Registration").count() == 1


def test_pg_competing_checkins_have_one_visit_invoice_and_consultation_line(tenant, enabled_mig001_target):
    patient = _new_patient(tenant, "CheckInRace")

    def operation():
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        outcome = visit_check_in(
            organisation=organisation,
            facility=facility,
            actor=actor,
            patient_id=patient.id,
            department_id=tenant.department.id,
            visit_type="OUTPATIENT_NEW",
            payer_type="CASH",
        )
        return str(outcome.visit.id)

    results = _race(tenant, operation)

    assert sorted(result[0] for result in results) == ["error", "ok"]
    assert next(result[1] for result in results if result[0] == "error") == "VISIT_ALREADY_OPEN"
    with tenant_atomic(tenant.organisation.id):
        visit = Visit.objects.get(patient=patient)
        invoice = Invoice.objects.get(visit=visit)
        assert Visit.objects.filter(patient=patient).count() == 1
        assert QueueEntry.objects.filter(visit=visit).count() == 1
        assert Invoice.objects.filter(visit=visit).count() == 1
        assert InvoiceItem.objects.filter(
            invoice=invoice,
            source_type="CONSULTATION",
            state="ACTIVE",
        ).count() == 1


def test_pg_competing_enquiry_conversions_have_one_winner_and_no_orphan_visit(tenant, enabled_mig001_target):
    first_patient = _new_patient(tenant, "EnquiryWinnerA")
    second_patient = _new_patient(tenant, "EnquiryWinnerB")
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        enquiry = arrival_enquiry_record(
            organisation=organisation,
            facility=facility,
            actor=actor,
            reason_code="SERVICE_UNAVAILABLE",
            source_event_id=f"pg-s01-enquiry-{uuid4()}",
        ).enquiry
        enquiry_id = enquiry.id
        enquiry_version = enquiry.version

    patient_ids = [first_patient.id, second_patient.id]
    patient_ids_lock = Lock()

    def operation():
        with patient_ids_lock:
            patient_id = patient_ids.pop()
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        outcome = visit_check_in(
            organisation=organisation,
            facility=facility,
            actor=actor,
            patient_id=patient_id,
            department_id=tenant.department.id,
            visit_type="OUTPATIENT_NEW",
            payer_type="CASH",
            arrival_enquiry_id=enquiry_id,
            arrival_enquiry_version=enquiry_version,
        )
        return str(outcome.visit.id)

    results = _race(tenant, operation)

    assert sorted(result[0] for result in results) == ["error", "ok"]
    assert next(result[1] for result in results if result[0] == "error") in {
        "VERSION_CONFLICT",
        "ARRIVAL_ENQUIRY_ALREADY_CONVERTED",
    }
    with tenant_atomic(tenant.organisation.id):
        enquiry = ArrivalEnquiry.objects.get(id=enquiry_id)
        assert enquiry.state == "CONVERTED"
        assert Visit.objects.filter(id=enquiry.converted_visit_id).count() == 1
        assert Visit.objects.filter(patient_id__in=(first_patient.id, second_patient.id)).count() == 1


def test_pg_cancellation_and_clinical_creation_have_one_serialized_outcome(tenant, enabled_mig001_target):
    patient = _new_patient(tenant, "CancelClinicalRace")
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        checkin = visit_check_in(
            organisation=organisation,
            facility=facility,
            actor=actor,
            patient_id=patient.id,
            department_id=tenant.department.id,
            visit_type="OUTPATIENT_NEW",
            payer_type="CASH",
        )
        visit_id = checkin.visit.id
        queue_id = checkin.queue.id

    def cancel_operation():
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        outcome = visit_cancel_error(
            organisation=organisation,
            facility=facility,
            actor=actor,
            visit_id=visit_id,
            reason="Concurrent synthetic cancellation",
        )
        return "cancelled", str(outcome.visit.id)

    def clinical_operation():
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        encounter = start_encounter(
            organisation=organisation,
            facility=facility,
            actor=actor,
            queue_entry_id=queue_id,
        )
        return "encounter", str(encounter.id)

    barrier = Barrier(2)

    def attempt(operation):
        connections.close_all()
        try:
            def callback():
                barrier.wait(timeout=20)
                return operation()

            try:
                return run_in_tenant(tenant.organisation.id, callback)
            except (CanonicalError, ValueError) as exc:
                return "error", getattr(exc, "code", str(exc))
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        cancel_future = executor.submit(attempt, cancel_operation)
        clinical_future = executor.submit(attempt, clinical_operation)
        cancel_result = cancel_future.result()
        clinical_result = clinical_future.result()

    assert (cancel_result[0], clinical_result[0]) in {
        ("cancelled", "error"),
        ("error", "encounter"),
    }
    with tenant_atomic(tenant.organisation.id):
        visit = Visit.objects.get(id=visit_id)
        encounters = Encounter.objects.filter(visit=visit)
        if visit.state == "CANCELLED_ERROR":
            assert not encounters.exists()
            assert Invoice.objects.get(visit=visit).status == "VOIDED"
            assert clinical_result[0] == "error"
        else:
            assert visit.state == "IN_PROGRESS"
            assert encounters.count() == 1
            assert cancel_result[0] == "error"


@pytest.mark.parametrize("payment_timing", ["PAY_AFTER", "PAY_BEFORE_TRIAGE"])
def test_pg_all_visit_types_and_payment_policies(tenant, enabled_mig001_target, payment_timing):
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        FacilityWorkflowPolicy.objects.create(
            organisation=organisation,
            facility=facility,
            updated_by=actor,
            consultation_payment_timing=payment_timing,
        )
        departments = {
            "OPD": tenant.department.id,
            "ANC": Department.objects.create(
                organisation=organisation,
                facility=facility,
                name="Antenatal care",
                code="ANC",
            ).id,
            "LAB": Department.objects.create(
                organisation=organisation,
                facility=facility,
                name="Laboratory",
                code="LAB",
            ).id,
            "PHARMACY": Department.objects.create(
                organisation=organisation,
                facility=facility,
                name="Pharmacy",
                code="PHARMACY",
            ).id,
        }

    department_for_type = {
        "OUTPATIENT_NEW": departments["OPD"],
        "OUTPATIENT_REVIEW": departments["OPD"],
        "ANC": departments["ANC"],
        "LAB_ONLY": departments["LAB"],
        "PHARMACY_ONLY": departments["PHARMACY"],
        "FOLLOW_UP_RESULTS": departments["OPD"],
    }
    for index, visit_type in enumerate(department_for_type):
        patient = _new_patient(tenant, f"AllTypes{payment_timing[:2]}{index}")
        with tenant_atomic(tenant.organisation.id):
            organisation = Organisation.objects.get(id=tenant.organisation.id)
            facility = Facility.objects.get(id=tenant.facility.id)
            actor = User.objects.get(id=tenant.user.id)
            outcome = visit_check_in(
                organisation=organisation,
                facility=facility,
                actor=actor,
                patient_id=patient.id,
                department_id=department_for_type[visit_type],
                visit_type=visit_type,
                payer_type="CASH",
            )
            assert (outcome.invoice is not None) is (visit_type in CHARGEABLE_TYPES)
            if visit_type in CHARGEABLE_TYPES:
                assert outcome.invoice.items.filter(source_type="CONSULTATION", state="ACTIVE").count() == 1
                assert outcome.queue.status == (
                    "WAITING_PAYMENT" if payment_timing == "PAY_BEFORE_TRIAGE" else "WAITING"
                )
            elif visit_type == "LAB_ONLY":
                assert outcome.queue is None
            else:
                assert outcome.queue.status == "WAITING"


def test_pg_force_rls_and_non_bypass_role_cover_s01_tables():
    status = rls_status()
    assert status["enforced"] is True
    assert status["role"]["bypass_rls"] is False
    tables = {table["name"]: table for table in status["tables"]}
    for table_name in (
        "core_migrationreconciliation",
        "core_migrationcutover",
        "scheduling_visit",
        "scheduling_arrivalenquiry",
        "billing_pricelist",
        "billing_serviceprice",
        "billing_visitpayerbinding",
        "clinical_encounter",
        "billing_invoice",
    ):
        assert tables[table_name]["rowsecurity"] is True
        assert tables[table_name]["force"] is True
        assert tables[table_name]["tenant_policy"] is True


def test_pg_cross_facility_links_are_rejected_by_database_scope_guards(tenant):
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        other_facility = Facility.objects.create(
            organisation=organisation,
            name="Other S01 Facility",
            code="S01-OTHER",
        )
        other_department = Department.objects.create(
            organisation=organisation,
            facility=other_facility,
            name="Other OPD",
            code="OPD",
        )
        patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S01-SCOPE-{uuid4().hex[:8]}",
            first_name="Scope",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        visit = Visit.objects.create(
            organisation=organisation,
            facility=facility,
            patient=patient,
            local_service_date=timezone.localdate(),
            visit_type="OUTPATIENT_NEW",
            opened_by=actor,
        )

        attempts = (
            lambda: QueueEntry.objects.create(
                organisation=organisation,
                facility=other_facility,
                visit=visit,
                patient=patient,
                department=other_department,
                queue_date=timezone.localdate(),
                sequence=1,
            ),
            lambda: Encounter.objects.create(
                organisation=organisation,
                facility=other_facility,
                patient=patient,
                visit=visit,
                clinician=actor,
                encounter_no=f"ENC-PG-S01-SCOPE-{uuid4().hex[:8]}",
            ),
            lambda: Invoice.objects.create(
                organisation=organisation,
                facility=other_facility,
                patient=patient,
                visit=visit,
                invoice_no=f"INV-PG-S01-SCOPE-{uuid4().hex[:8]}",
                created_by=actor,
            ),
            lambda: VisitPayerBinding.objects.create(
                organisation=organisation,
                facility=other_facility,
                visit=visit,
                price_list=tenant.price_list,
                payer_type="CASH",
                bound_by=actor,
            ),
        )
        for attempt in attempts:
            with pytest.raises(DatabaseError) as error:
                with transaction.atomic():
                    attempt()
            assert _sqlstate(error) == "23514"


def test_pg_cross_tenant_visit_is_hidden_from_query_and_rls(tenant, enabled_mig001_target, authed_client):
    other_organisation = Organisation.objects.create(
        name="Other S01 Clinic",
        slug=f"other-s01-{uuid4().hex[:8]}",
    )
    with tenant_atomic(other_organisation.id):
        other_facility = Facility.objects.create(
            organisation=other_organisation,
            name="Other S01 Facility",
            code="MAIN",
        )
        other_department = Department.objects.create(
            organisation=other_organisation,
            facility=other_facility,
            name="Outpatient",
            code="OPD",
        )
        other_patient = Patient.objects.create(
            organisation=other_organisation,
            patient_no="P-PG-S01-OTHER",
            first_name="Other",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        other_visit = Visit.objects.create(
            organisation=other_organisation,
            facility=other_facility,
            patient=other_patient,
            local_service_date=timezone.localdate(),
            visit_type="OUTPATIENT_NEW",
            opened_by=tenant.user,
        )
        QueueEntry.objects.create(
            organisation=other_organisation,
            facility=other_facility,
            visit=other_visit,
            patient=other_patient,
            department=other_department,
            queue_date=timezone.localdate(),
            sequence=1,
        )

    with tenant_atomic(tenant.organisation.id):
        assert not Visit.objects.filter(id=other_visit.id).exists()
    response = authed_client.get(f"/api/v1/reception/visits/{other_visit.id}/context/")
    assert response.status_code == 404
    assert response.data["code"] == "VISIT_NOT_FOUND"


def test_pg_price_contracts_fail_closed_and_keep_referenced_history(tenant):
    with tenant_atomic(tenant.organisation.id):
        with pytest.raises(DatabaseError) as overlap:
            with transaction.atomic():
                ServicePrice.objects.create(
                    organisation=tenant.organisation,
                    facility=tenant.facility,
                    service=tenant.service,
                    price_list=tenant.price_list,
                    amount="35000.00",
                    currency="UGX",
                    effective_from=timezone.localdate(),
                )
        assert _sqlstate(overlap) == "23P01"

        with pytest.raises(DatabaseError) as price_list_update:
            with transaction.atomic():
                PriceList.objects.filter(id=tenant.price_list.id).update(name="Attempted rewrite")
        assert _sqlstate(price_list_update) == "55006"

        patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no=f"P-PG-S01-BIND-{uuid4().hex[:8]}",
            first_name="Binding",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        visit = Visit.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=patient,
            local_service_date=timezone.localdate(),
            visit_type="LAB_ONLY",
            opened_by=tenant.user,
        )
        binding = VisitPayerBinding.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            visit=visit,
            price_list=tenant.price_list,
            payer_type="CASH",
            bound_by=tenant.user,
        )
        with pytest.raises(DatabaseError) as binding_update:
            with transaction.atomic():
                VisitPayerBinding.objects.filter(id=binding.id).update(active=False)
        assert _sqlstate(binding_update) == "55006"


def test_pg_concurrent_overlapping_service_prices_have_one_database_winner(tenant):
    """The exclusion constraint must arbitrate an actual overlapping race."""

    with tenant_atomic(tenant.organisation.id):
        service = ServiceCatalogItem.objects.create(
            organisation=tenant.organisation,
            code=f"RACE-{uuid4().hex[:12]}",
            name="Concurrent synthetic service",
        )
        service_id = service.id

    barrier = Barrier(2)

    def attempt():
        connections.close_all()
        try:
            with tenant_atomic(tenant.organisation.id):
                organisation = Organisation.objects.get(id=tenant.organisation.id)
                facility = Facility.objects.get(id=tenant.facility.id)
                price_list = PriceList.objects.get(id=tenant.price_list.id)
                service = ServiceCatalogItem.objects.get(id=service_id)
                barrier.wait(timeout=20)
                try:
                    with transaction.atomic():
                        ServicePrice.objects.create(
                            organisation=organisation,
                            facility=facility,
                            service=service,
                            price_list=price_list,
                            amount="42000.00",
                            currency="UGX",
                            effective_from=date(2030, 1, 1),
                            effective_to=date(2030, 12, 31),
                        )
                except DatabaseError as exc:
                    return ("error", _sqlstate(exc))
                return ("ok", None)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: attempt(), range(2)))

    assert sorted(result[0] for result in results) == ["error", "ok"]
    assert next(result[1] for result in results if result[0] == "error") == "23P01"
    with tenant_atomic(tenant.organisation.id):
        assert ServicePrice.objects.filter(
            organisation=tenant.organisation,
            facility=tenant.facility,
            service_id=service_id,
            price_list=tenant.price_list,
        ).count() == 1


def test_pg_mig001_backfill_cutover_and_rollback_retain_target_links(tenant):
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S01-MIG-{uuid4().hex[:8]}",
            first_name="Migration",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        queue = QueueEntry.objects.create(
            organisation=organisation,
            facility=facility,
            patient=patient,
            department=tenant.department,
            queue_date=timezone.localdate(),
            sequence=1,
            visit_type="WALK_IN",
            claimed_by=actor,
        )
        run_id = uuid4()
        inventory = inventory_mig001(organisation=organisation)
        assert inventory.inspected == 1
        assert inventory.organisation_counts[str(organisation.id)] == 1
        assert inventory.facility_counts[str(facility.id)] == 1
        summary = backfill_mig001(organisation=organisation, run_id=run_id)
        assert summary.backfilled == 1
        assert summary.run_id == str(run_id)
        migrated_visit = Visit.objects.get(legacy_source_key=f"queue:{queue.id}")
        queue.refresh_from_db()
        assert queue.visit_id == migrated_visit.id
        assert migrated_visit.visit_type == "OUTPATIENT_NEW"

        # Native target rows created during the dual-write window do not alter
        # the immutable legacy L_queue parity population.
        native_patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S01-NATIVE-{uuid4().hex[:8]}",
            first_name="Native",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        native_visit = Visit.objects.create(
            organisation=organisation,
            facility=facility,
            patient=native_patient,
            local_service_date=timezone.localdate(),
            visit_type="LAB_ONLY",
            opened_by=actor,
        )
        QueueEntry.objects.create(
            organisation=organisation,
            facility=facility,
            visit=native_visit,
            patient=native_patient,
            department=tenant.department,
            queue_date=timezone.localdate(),
            sequence=2,
            visit_type="LAB_ONLY",
        )
        verified = verify_mig001(organisation=organisation)
        assert verified.unresolved == 0
        assert verified.queue_without_visit == 0
        assert verified.shadow_read_equal is True
        assert verified.stable_full_scan_count == 1
        assert verified.organisation_counts[str(organisation.id)] == 1
        assert verified.facility_counts[str(facility.id)] == 1
        switch = MigrationCutover.objects.get(
            organisation=organisation,
            migration_id="MIG-001",
        )
        proof = switch.deterministic_row_evidence[f"scheduling_queueentry:{queue.id}"]
        assert len(proof["source_hash"]) == 64
        assert len(proof["target_hash"]) == 64
        assert proof["backfill_run_id"] == str(run_id)
        assert proof["target_refs"] == {
            "queue_id": str(queue.id),
            "visit_id": str(migrated_visit.id),
        }

        cutover = cutover_mig001(organisation=organisation)
        assert cutover.parity_passes == 2
        assert cutover.stable_full_scan_count == 2
        switch = MigrationCutover.objects.get(
            organisation=organisation,
            migration_id="MIG-001",
        )
        assert switch.target_reads_enabled is True
        assert switch.target_writes_enabled is True

        rollback_mig001(
            organisation=organisation,
            actor=actor,
            reason="Restore legacy compatibility for synthetic proof",
        )
        switch.refresh_from_db()
        assert switch.target_reads_enabled is False
        assert switch.target_writes_enabled is False
        assert Visit.objects.filter(id=migrated_visit.id).exists()
        assert QueueEntry.objects.filter(id=queue.id, visit=migrated_visit).exists()

    with tenant_atomic(tenant.organisation.id):
        with pytest.raises(CanonicalError) as disabled:
            get_visit_projection(
                organisation=tenant.organisation,
                facility=tenant.facility,
                visit_id=migrated_visit.id,
            )
        assert disabled.value.code == "MIGRATION_TARGET_DISABLED"


def test_pg_mig001_ambiguous_legacy_rows_are_pc050_and_block_cutover(tenant):
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S01-AMB-{uuid4().hex[:8]}",
            first_name="Ambiguous",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        for sequence in (1, 2):
            QueueEntry.objects.create(
                organisation=organisation,
                facility=facility,
                patient=patient,
                department=tenant.department,
                queue_date=timezone.localdate(),
                sequence=sequence,
                visit_type="WALK_IN",
                claimed_by=actor,
            )
        inventory_mig001(organisation=organisation)
        summary = backfill_mig001(organisation=organisation, run_id=uuid4())
        assert summary.backfilled == 0
        assert summary.exceptions == 2
        assert MigrationReconciliation.objects.filter(
            organisation=organisation,
            legacy_table="scheduling_queueentry",
            evidence_codes__contains=["AMBIGUOUS_EPISODE"],
        ).count() == 2
        verified = verify_mig001(organisation=organisation)
        assert verified.queue_without_visit == 2
        assert verified.unresolved == 2
        with pytest.raises(ValueError, match="unresolved"):
            cutover_mig001(organisation=organisation)


def test_pg_mig001_reconciliation_resolution_converges_and_is_idempotent(tenant):
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S01-RESOLVE-{uuid4().hex[:8]}",
            first_name="Resolution",
            last_name="Synthetic",
            sex="UNKNOWN",
        )
        queue = QueueEntry.objects.create(
            organisation=organisation,
            facility=facility,
            patient=patient,
            department=tenant.department,
            queue_date=timezone.localdate(),
            sequence=1,
            visit_type="WALK_IN",
        )

        inventory_mig001(organisation=organisation)
        backfill_mig001(organisation=organisation, run_id=uuid4())
        evidence = MigrationReconciliation.objects.get(
            organisation=organisation,
            migration_id="MIG-001",
            legacy_table="scheduling_queueentry",
            legacy_pk=str(queue.id),
        )
        assert evidence.resolution_state == "PENDING"

        # Correct the source attribution, then rerun the restartable backfill.
        # Resolution is allowed only after the deterministic target exists.
        queue.claimed_by = actor
        queue.claimed_at = timezone.now()
        queue.save(update_fields=["claimed_by", "claimed_at", "updated_at"])
        backfill_mig001(organisation=organisation, run_id=uuid4())
        queue.refresh_from_db()
        assert queue.visit_id is not None

        resolved = resolve_reconciliation(
            organisation=organisation,
            reconciliation_id=evidence.id,
            actor=actor,
            reason="Corrected legacy opener attribution",
        )
        resolved.proposed_target_refs = {
            **resolved.proposed_target_refs,
            "stale_target_ref": "must be removed by convergence",
        }
        resolved.save(update_fields=["proposed_target_refs", "updated_at"])
        repeated = resolve_reconciliation(
            organisation=organisation,
            reconciliation_id=evidence.id,
            actor=actor,
            reason="Repeated convergence check",
        )
        assert resolved.id == repeated.id == evidence.id
        assert repeated.resolution_state == "RESOLVED"
        assert repeated.proposed_target_refs == {
            "queue_id": str(queue.id),
            "visit_id": str(queue.visit_id),
        }
        reconciliation_audit = AuditEvent.objects.get(
            event_code="MIGRATION_RECONCILIATION_RESOLVED",
            entity_id=str(evidence.id),
        )
        assert reconciliation_audit.source_ids["reconciliation_id"] == str(evidence.id)
        assert "Corrected legacy opener attribution" not in str(reconciliation_audit.__dict__)
        verified = verify_mig001(organisation=organisation)
        assert verified.unresolved == 0
        assert verified.queue_without_visit == 0
        assert verified.scope_link_hash_verified is True

        queue.claimed_by = None
        queue.save(update_fields=["claimed_by", "updated_at"])
        source_drift = verify_mig001(organisation=organisation)
        assert source_drift.unresolved == 1
        assert source_drift.scope_link_hash_verified is False


def test_pg_mig001_cutover_and_rollback_fences_serialize_writers(tenant):
    """The transition row lock fences both legacy and canonical writers."""

    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        legacy_patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S01-FENCE-LEGACY-{uuid4().hex[:8]}",
            first_name="Legacy",
            last_name="Fence",
            sex="UNKNOWN",
        )
        target_patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S01-FENCE-TARGET-{uuid4().hex[:8]}",
            first_name="Target",
            last_name="Fence",
            sex="UNKNOWN",
        )
        MigrationCutover.objects.create(
            organisation=organisation,
            migration_id="MIG-001",
            phase="EXPANDED",
            target_reads_enabled=False,
            target_writes_enabled=False,
        )

    events = []
    events_lock = Lock()

    def mark(label):
        with events_lock:
            events.append(label)

    legacy_ready = Event()
    release_legacy = Event()

    def legacy_writer():
        connections.close_all()
        try:
            with tenant_atomic(tenant.organisation.id):
                organisation = Organisation.objects.get(id=tenant.organisation.id)
                facility = Facility.objects.get(id=tenant.facility.id)
                actor = User.objects.get(id=tenant.user.id)
                assert legacy_writes_enabled(organisation) is True
                legacy_ready.set()
                assert release_legacy.wait(timeout=20)
                check_in_patient(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    patient_id=legacy_patient.id,
                    department_id=tenant.department.id,
                )
            mark("legacy_committed")
        finally:
            connections.close_all()

    def successful_cutover_transition():
        connections.close_all()
        try:
            with tenant_atomic(tenant.organisation.id):
                switch = MigrationCutover.objects.select_for_update().get(
                    organisation_id=tenant.organisation.id,
                    migration_id="MIG-001",
                )
                switch.phase = "CUTOVER"
                switch.target_reads_enabled = True
                switch.target_writes_enabled = True
                switch.write_fence += 1
                switch.version += 1
                switch.save(
                    update_fields=[
                        "phase",
                        "target_reads_enabled",
                        "target_writes_enabled",
                        "write_fence",
                        "version",
                        "updated_at",
                    ]
                )
                mark("cutover_applied")
            mark("cutover_committed")
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        legacy_future = executor.submit(legacy_writer)
        assert legacy_ready.wait(timeout=20)
        cutover_future = executor.submit(successful_cutover_transition)
        release_legacy.set()
        legacy_future.result()
        cutover_future.result()

    assert events.index("legacy_committed") < events.index("cutover_applied")
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        post_cutover_patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S01-FENCE-POST-{uuid4().hex[:8]}",
            first_name="After",
            last_name="Cutover",
            sex="UNKNOWN",
        )
        with pytest.raises(CanonicalError) as legacy_disabled:
            check_in_patient(
                organisation=organisation,
                facility=facility,
                actor=actor,
                patient_id=post_cutover_patient.id,
                department_id=tenant.department.id,
            )
        assert legacy_disabled.value.code == "LEGACY_WRITER_DISABLED"
        assert not QueueEntry.objects.filter(patient=post_cutover_patient).exists()

    target_ready = Event()
    release_target = Event()

    def target_writer():
        connections.close_all()
        try:
            with tenant_atomic(tenant.organisation.id):
                organisation = Organisation.objects.get(id=tenant.organisation.id)
                facility = Facility.objects.get(id=tenant.facility.id)
                actor = User.objects.get(id=tenant.user.id)
                patient = Patient.objects.get(id=target_patient.id)
                assert target_writes_enabled(organisation) is True
                target_ready.set()
                assert release_target.wait(timeout=20)
                open_visit(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    patient=patient,
                    local_service_day=timezone.localdate(),
                    visit_type="OUTPATIENT_NEW",
                )
            mark("target_committed")
        finally:
            connections.close_all()

    def rollback_transition():
        connections.close_all()
        try:
            with tenant_atomic(tenant.organisation.id):
                organisation = Organisation.objects.get(id=tenant.organisation.id)
                actor = User.objects.get(id=tenant.user.id)
                rollback_mig001(
                    organisation=organisation,
                    actor=actor,
                    reason="Synthetic fence race rollback",
                )
                mark("rollback_applied")
            mark("rollback_committed")
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        target_future = executor.submit(target_writer)
        assert target_ready.wait(timeout=20)
        rollback_future = executor.submit(rollback_transition)
        release_target.set()
        target_future.result()
        rollback_future.result()

    assert events.index("target_committed") < events.index("rollback_applied")
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        patient = Patient.objects.get(id=target_patient.id)
        assert target_writes_enabled(organisation) is False
        with pytest.raises(ValueError, match="disabled"):
            open_visit(
                organisation=organisation,
                facility=facility,
                actor=actor,
                patient=patient,
                local_service_day=timezone.localdate(),
                visit_type="OUTPATIENT_NEW",
            )
        assert Visit.objects.filter(patient=patient).count() == 1


def test_pg_audited_clinical_read_failure_returns_no_payload_and_no_audit(monkeypatch, tenant, enabled_mig001_target, authed_client):
    patient = _new_patient(tenant, "AuditedReadFailure")
    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        checkin = visit_check_in(
            organisation=organisation,
            facility=facility,
            actor=actor,
            patient_id=patient.id,
            department_id=tenant.department.id,
            visit_type="OUTPATIENT_NEW",
            payer_type="CASH",
        )
        Encounter.objects.create(
            organisation=organisation,
            facility=facility,
            patient=patient,
            visit=checkin.visit,
            queue_entry=checkin.queue,
            encounter_no=f"ENC-PG-S01-AUDIT-{uuid4().hex[:8]}",
            clinician=actor,
            complaints=["synthetic clinical value must not escape"],
        )
        before = AuditEvent.objects.filter(event_code="PHI_READ").count()
        visit_id = checkin.visit.id

    def fail_audit(**_kwargs):
        raise RuntimeError("synthetic audit storage failure")

    monkeypatch.setattr("application.reception.audited_reads.record_fact", fail_audit)
    response = authed_client.get(f"/api/v1/reception/visits/{visit_id}/context/")
    assert response.status_code == 503
    assert response.data["code"] == "AUDITED_READ_UNAVAILABLE"
    assert "synthetic clinical value" not in str(response.data)
    with tenant_atomic(tenant.organisation.id):
        assert AuditEvent.objects.filter(event_code="PHI_READ").count() == before
