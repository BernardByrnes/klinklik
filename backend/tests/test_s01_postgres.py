import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, Event, Lock, get_ident
from uuid import uuid4

import pytest
from django.db import DatabaseError, connection, connections, transaction
from django.utils import timezone

import core.migration_reconciliation as migration_reconciliation

from accounts.models import User
from application.reception.commands import (
    arrival_enquiry_record,
    patient_register,
    visit_cancel_error,
    visit_check_in,
)
from application.reception.visit_query import get_visit_projection
from audit.models import AuditEvent
from billing.models import Invoice, InvoiceItem, PaymentAllocation, PriceList, ServiceCatalogItem, ServicePrice, VisitPayerBinding
from billing.services import create_invoice, post_payment
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


_LOCK_CONTENTION_SQL = """
SELECT
    blocked.pid AS blocked_pid,
    blocker.pid AS blocking_pid,
    blocked.state AS blocked_state,
    blocked.wait_event_type AS blocked_wait_event_type,
    blocked.wait_event AS blocked_wait_event,
    blocked.query AS blocked_query,
    blocker.query AS blocking_query,
    blocked_lock.locktype AS blocked_locktype,
    blocker_lock.locktype AS blocking_locktype,
    blocked_lock.granted AS blocked_granted,
    blocker_lock.granted AS blocking_granted,
    blocked_lock.relation::regclass::text AS blocked_relation,
    blocker_lock.relation::regclass::text AS blocking_relation
FROM pg_stat_activity AS blocked
JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS blocker_pid(pid) ON TRUE
JOIN pg_stat_activity AS blocker ON blocker.pid = blocker_pid.pid
JOIN pg_locks AS blocked_lock
  ON blocked_lock.pid = blocked.pid
 AND blocked_lock.granted = FALSE
JOIN pg_locks AS blocker_lock
  ON blocker_lock.pid = blocker.pid
 AND blocker_lock.granted = TRUE
 AND blocker_lock.locktype = blocked_lock.locktype
 AND blocker_lock.database IS NOT DISTINCT FROM blocked_lock.database
 AND blocker_lock.relation IS NOT DISTINCT FROM blocked_lock.relation
 AND blocker_lock.page IS NOT DISTINCT FROM blocked_lock.page
 AND blocker_lock.tuple IS NOT DISTINCT FROM blocked_lock.tuple
 AND blocker_lock.virtualxid IS NOT DISTINCT FROM blocked_lock.virtualxid
 AND blocker_lock.transactionid IS NOT DISTINCT FROM blocked_lock.transactionid
 AND blocker_lock.classid IS NOT DISTINCT FROM blocked_lock.classid
 AND blocker_lock.objid IS NOT DISTINCT FROM blocked_lock.objid
 AND blocker_lock.objsubid IS NOT DISTINCT FROM blocked_lock.objsubid
WHERE blocked.pid = %s
  AND blocker.pid = %s
  AND blocked.wait_event_type = 'Lock'
  AND blocked_lock.locktype = 'transactionid'
  AND blocked.query ILIKE %s
  AND blocker.query ILIKE %s
"""


def _capture_backend_pid(*, key, backend_pids, backend_pids_lock, ready):
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        backend_pid = cursor.fetchone()[0]
    with backend_pids_lock:
        backend_pids[key] = backend_pid
    ready.set()
    return backend_pid


def _wait_for_lock_contention(*, blocked_pid, blocking_pid, query_fragment, timeout=20):
    """Observe a real PostgreSQL wait before allowing the owning worker to proceed."""

    observer = connections["default"].copy()
    deadline = time.monotonic() + timeout
    try:
        observer.connect()
        while time.monotonic() < deadline:
            with observer.cursor() as cursor:
                cursor.execute(
                    _LOCK_CONTENTION_SQL,
                    [
                        blocked_pid,
                        blocking_pid,
                        f"%{query_fragment}%",
                        f"%{query_fragment}%",
                    ],
                )
                row = cursor.fetchone()
                if row is not None:
                    columns = [column.name for column in cursor.description]
                    return dict(zip(columns, row))
            time.sleep(0.02)
    finally:
        observer.close()
    raise AssertionError(
        f"PostgreSQL did not expose the expected {query_fragment} lock wait "
        f"(blocked pid {blocked_pid}, blocking pid {blocking_pid})."
    )


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


def test_pg_visit_invoice_handoff_refuses_duplicate_and_pays_the_original(tenant, enabled_mig001_target):
    """The Visit invoice is the only charge, and payment targets it under RLS."""

    patient = _new_patient(tenant, "VisitInvoiceHandoff")
    with tenant_atomic(tenant.organisation.id):
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
        visit_id = outcome.visit.id
        invoice_id = outcome.invoice.id
        invoice_no = outcome.invoice.invoice_no
        queue_id = outcome.queue.id

    with tenant_atomic(tenant.organisation.id):
        encounter = start_encounter(
            organisation=organisation,
            facility=facility,
            actor=actor,
            queue_entry_id=queue_id,
        )
        assert encounter.visit_id == visit_id
        # Synthetic signature: this test exercises the billing guard, not the
        # clinical signing workflow.
        Encounter.objects.filter(id=encounter.id).update(status="SIGNED")

        with pytest.raises(CanonicalError) as refused:
            create_invoice(
                organisation=organisation,
                facility=facility,
                actor=actor,
                patient_id=patient.id,
                encounter_id=encounter.id,
                items=[{"service_id": str(tenant.service.id), "quantity": "1"}],
            )
        assert refused.value.code == "VISIT_INVOICE_REQUIRED"
        assert refused.value.status_code == 409

        assert Invoice.objects.filter(visit_id=visit_id).count() == 1
        assert Invoice.objects.filter(encounter_id=encounter.id).count() == 0
        assert InvoiceItem.objects.filter(source_type="CONSULTATION", state="ACTIVE").count() == 1
        assert not AuditEvent.objects.filter(event_code="CREATE", entity_type="Invoice").exists()

    with tenant_atomic(tenant.organisation.id):
        payment = post_payment(
            organisation=organisation,
            facility=facility,
            actor=actor,
            invoice_id=invoice_id,
            amount="30000.00",
            method="CASH",
        )
        assert payment.invoice_id == invoice_id
        allocation = PaymentAllocation.objects.get(payment=payment)
        assert allocation.invoice_id == invoice_id
        invoice = Invoice.objects.get(id=invoice_id)
        assert invoice.status == "PAID"
        assert invoice.balance == 0
        assert invoice.invoice_no == invoice_no
        event = AuditEvent.objects.get(
            event_code="PAYMENT", entity_type="Payment", entity_id=str(payment.id)
        )
        assert event.after["invoice_id"] == str(invoice_id)


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


@pytest.mark.parametrize("first_operation", ["cancel", "clinical"])
def test_pg_cancellation_and_clinical_creation_have_one_serialized_outcome(
    tenant,
    enabled_mig001_target,
    first_operation,
):
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
        invoice_id = checkin.invoice.id

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

    first_backend_pid_ready = Event()
    first_lock_acquired = Event()
    second_backend_pid_ready = Event()
    release_first = Event()
    backend_pids = {}
    backend_pids_lock = Lock()

    def attempt(operation, *, label, lock_acquired=None, backend_pid_ready=None, release=None):
        connections.close_all()
        try:
            def callback():
                _capture_backend_pid(
                    key=label,
                    backend_pids=backend_pids,
                    backend_pids_lock=backend_pids_lock,
                    ready=backend_pid_ready,
                )
                Visit.objects.select_for_update().get(
                    id=visit_id,
                    organisation_id=tenant.organisation.id,
                )
                if lock_acquired is not None:
                    lock_acquired.set()
                if release is not None and not release.wait(timeout=20):
                    raise RuntimeError("cancellation test release was not signalled")
                return operation()

            try:
                return run_in_tenant(tenant.organisation.id, callback)
            except (CanonicalError, ValueError) as exc:
                return "error", getattr(exc, "code", str(exc))
        finally:
            connections.close_all()

    operations = {
        "cancel": cancel_operation,
        "clinical": clinical_operation,
    }
    losing_operation = "clinical" if first_operation == "cancel" else "cancel"
    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            attempt,
            operations[first_operation],
            label="first",
            backend_pid_ready=first_backend_pid_ready,
            lock_acquired=first_lock_acquired,
            release=release_first,
        )
        assert first_lock_acquired.wait(timeout=20)
        second_future = executor.submit(
            attempt,
            operations[losing_operation],
            label="second",
            backend_pid_ready=second_backend_pid_ready,
        )
        try:
            assert second_backend_pid_ready.wait(timeout=20)
            with backend_pids_lock:
                first_backend_pid = backend_pids["first"]
                second_backend_pid = backend_pids["second"]
            observation = _wait_for_lock_contention(
                blocked_pid=second_backend_pid,
                blocking_pid=first_backend_pid,
                query_fragment="scheduling_visit",
            )
            assert observation["blocked_pid"] == second_backend_pid
            assert observation["blocking_pid"] == first_backend_pid
            assert observation["blocked_wait_event_type"] == "Lock"
            assert observation["blocked_locktype"] == "transactionid"
            assert observation["blocking_locktype"] == "transactionid"
            assert observation["blocked_granted"] is False
            assert observation["blocking_granted"] is True
            assert "scheduling_visit" in observation["blocked_query"].lower()
            assert "scheduling_visit" in observation["blocking_query"].lower()
        finally:
            release_first.set()
        worker_results = {
            first_operation: first_future.result(timeout=20),
            losing_operation: second_future.result(timeout=20),
        }

    cancel_result = worker_results["cancel"]
    clinical_result = worker_results["clinical"]
    if first_operation == "cancel":
        assert cancel_result == ("cancelled", str(visit_id))
        assert clinical_result == ("error", "This Visit is no longer available for clinical work.")
    else:
        assert clinical_result[0] == "encounter"
        assert cancel_result == ("error", "INVALID_STATE")

    with tenant_atomic(tenant.organisation.id):
        visit = Visit.objects.get(id=visit_id)
        queues = list(QueueEntry.objects.filter(visit=visit))
        encounters = list(Encounter.objects.filter(visit=visit))
        invoices = list(Invoice.objects.filter(visit=visit))
        assert Visit.objects.filter(patient_id=patient.id).count() == 1
        assert QueueEntry.objects.filter(patient_id=patient.id).count() == 1
        assert Invoice.objects.filter(patient_id=patient.id).count() == 1
        assert len(queues) == 1
        assert len(invoices) == 1
        assert invoices[0].id == invoice_id
        assert queues[0].patient_id == patient.id
        assert queues[0].visit_id == visit.id
        assert invoices[0].patient_id == patient.id
        assert invoices[0].visit_id == visit.id
        assert Encounter.objects.filter(patient_id=patient.id).count() == len(encounters)
        assert InvoiceItem.objects.filter(
            invoice=invoices[0],
            source_type="CONSULTATION",
        ).count() == 1
        if first_operation == "cancel":
            assert visit.state == "CANCELLED_ERROR"
            assert queues[0].status == "CANCELLED"
            assert not encounters
            assert invoices[0].status == "VOIDED"
            assert InvoiceItem.objects.filter(
                invoice=invoices[0],
                source_type="CONSULTATION",
                state="VOIDED",
            ).count() == 1
        else:
            assert visit.state == "IN_PROGRESS"
            assert queues[0].status == "IN_CONSULTATION"
            assert len(encounters) == 1
            assert clinical_result == ("encounter", str(encounters[0].id))
            assert encounters[0].queue_entry_id == queues[0].id
            assert encounters[0].visit_id == visit.id
            assert invoices[0].status == "ISSUED"
            assert InvoiceItem.objects.filter(
                invoice=invoices[0],
                source_type="CONSULTATION",
                state="ACTIVE",
            ).count() == 1


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
        # S-07 permits only the supersession transition; every financial or
        # identity field remains append-only, and reactivation is forbidden.
        VisitPayerBinding.objects.filter(id=binding.id).update(active=False)
        with pytest.raises(DatabaseError) as binding_update:
            with transaction.atomic():
                VisitPayerBinding.objects.filter(id=binding.id).update(
                    payer_type="SELF_PAY_MOMO"
                )
        assert _sqlstate(binding_update) == "55006"
        with pytest.raises(DatabaseError) as binding_reactivate:
            with transaction.atomic():
                VisitPayerBinding.objects.filter(id=binding.id).update(active=True)
        assert _sqlstate(binding_reactivate) == "55006"


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


def test_pg_mig001_cutover_and_rollback_fences_real_writers(tenant, monkeypatch):
    """Real phase transitions fence the legacy and canonical write services."""

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
        legacy_queue = QueueEntry.objects.create(
            organisation=organisation,
            facility=facility,
            patient=legacy_patient,
            department=tenant.department,
            queue_date=timezone.localdate(),
            sequence=1,
            visit_type="WALK_IN",
            claimed_by=actor,
        )
        inventory = inventory_mig001(organisation=organisation)
        assert inventory.inspected == 1
        backfill = backfill_mig001(organisation=organisation, run_id=uuid4())
        assert backfill.backfilled == 1
        migrated_visit = Visit.objects.get(legacy_source_key=f"queue:{legacy_queue.id}")
        legacy_queue.refresh_from_db()
        assert legacy_queue.visit_id == migrated_visit.id
        switch = MigrationCutover.objects.get(
            organisation=organisation,
            migration_id="MIG-001",
        )
        pre_cutover_fence = switch.write_fence

    writer_labels = {}
    writer_labels_lock = Lock()
    backend_pids = {}
    backend_pids_lock = Lock()
    backend_pid_ready = {
        label: Event() for label in ("cutover", "legacy", "target", "rollback")
    }
    cutover_fence_acquired = Event()
    release_cutover = Event()
    target_fence_acquired = Event()
    release_target = Event()
    original_cutover_switch = migration_reconciliation._cutover_switch

    def set_writer_label(label):
        with writer_labels_lock:
            writer_labels[get_ident()] = label

    def clear_writer_label():
        with writer_labels_lock:
            writer_labels.pop(get_ident(), None)

    def current_writer_label():
        with writer_labels_lock:
            return writer_labels.get(get_ident())

    def instrumented_cutover_switch(*args, **kwargs):
        label = current_writer_label()
        if label == "cutover" and not cutover_fence_acquired.is_set():
            switch = original_cutover_switch(*args, **kwargs)
            cutover_fence_acquired.set()
            if not release_cutover.wait(timeout=20):
                raise RuntimeError("cutover test release was not signalled")
            return switch
        if label == "target" and not target_fence_acquired.is_set():
            switch = original_cutover_switch(*args, **kwargs)
            target_fence_acquired.set()
            return switch
        return original_cutover_switch(*args, **kwargs)

    monkeypatch.setattr(migration_reconciliation, "_cutover_switch", instrumented_cutover_switch)

    def cutover_writer():
        connections.close_all()
        set_writer_label("cutover")
        try:
            with tenant_atomic(tenant.organisation.id):
                _capture_backend_pid(
                    key="cutover",
                    backend_pids=backend_pids,
                    backend_pids_lock=backend_pids_lock,
                    ready=backend_pid_ready["cutover"],
                )
                organisation = Organisation.objects.get(id=tenant.organisation.id)
                result = cutover_mig001(organisation=organisation)
                return (result.phase, result.parity_passes, result.stable_full_scan_count)
        finally:
            clear_writer_label()
            connections.close_all()

    def legacy_writer():
        connections.close_all()
        set_writer_label("legacy")
        try:
            try:
                with tenant_atomic(tenant.organisation.id):
                    _capture_backend_pid(
                        key="legacy",
                        backend_pids=backend_pids,
                        backend_pids_lock=backend_pids_lock,
                        ready=backend_pid_ready["legacy"],
                    )
                    organisation = Organisation.objects.get(id=tenant.organisation.id)
                    facility = Facility.objects.get(id=tenant.facility.id)
                    actor = User.objects.get(id=tenant.user.id)
                    check_in_patient(
                        organisation=organisation,
                        facility=facility,
                        actor=actor,
                        patient_id=legacy_patient.id,
                        department_id=tenant.department.id,
                    )
            except CanonicalError as exc:
                return ("blocked", exc.code)
            return ("committed",)
        finally:
            clear_writer_label()
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        cutover_future = executor.submit(cutover_writer)
        assert cutover_fence_acquired.wait(timeout=20)
        assert backend_pid_ready["cutover"].is_set()
        with backend_pids_lock:
            cutover_backend_pid = backend_pids["cutover"]
        legacy_future = executor.submit(legacy_writer)
        try:
            assert backend_pid_ready["legacy"].wait(timeout=20)
            with backend_pids_lock:
                legacy_backend_pid = backend_pids["legacy"]
            observation = _wait_for_lock_contention(
                blocked_pid=legacy_backend_pid,
                blocking_pid=cutover_backend_pid,
                query_fragment="core_migrationcutover",
            )
            assert observation["blocked_pid"] == legacy_backend_pid
            assert observation["blocking_pid"] == cutover_backend_pid
            assert observation["blocked_wait_event_type"] == "Lock"
            assert observation["blocked_locktype"] == "transactionid"
            assert observation["blocking_locktype"] == "transactionid"
            assert observation["blocked_granted"] is False
            assert observation["blocking_granted"] is True
            assert "core_migrationcutover" in observation["blocked_query"].lower()
            assert "core_migrationcutover" in observation["blocking_query"].lower()
        finally:
            release_cutover.set()
        cutover_result = cutover_future.result(timeout=20)
        legacy_result = legacy_future.result(timeout=20)
        assert cutover_result == ("CUTOVER", 2, 2)
        assert legacy_result == ("blocked", "LEGACY_WRITER_DISABLED")

    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        switch = MigrationCutover.objects.get(
            organisation=organisation,
            migration_id="MIG-001",
        )
        assert switch.phase == "CUTOVER"
        assert switch.target_reads_enabled is True
        assert switch.target_writes_enabled is True
        cutover_fence = switch.write_fence
        assert cutover_fence == pre_cutover_fence + 1
        assert Visit.objects.filter(patient_id=legacy_patient.id).count() == 1
        assert QueueEntry.objects.filter(id=legacy_queue.id, visit_id=migrated_visit.id).exists()
        assert QueueEntry.objects.filter(patient_id=legacy_patient.id).count() == 1
        assert Encounter.objects.filter(patient_id=legacy_patient.id).count() == 0
        assert Invoice.objects.filter(patient_id=legacy_patient.id).count() == 0
        assert not QueueEntry.objects.filter(
            organisation=organisation,
            facility_id=facility.id,
            patient_id=legacy_patient.id,
            visit_id__isnull=True,
        ).exists()

    def target_writer():
        connections.close_all()
        set_writer_label("target")
        try:
            with tenant_atomic(tenant.organisation.id):
                _capture_backend_pid(
                    key="target",
                    backend_pids=backend_pids,
                    backend_pids_lock=backend_pids_lock,
                    ready=backend_pid_ready["target"],
                )
                organisation = Organisation.objects.get(id=tenant.organisation.id)
                facility = Facility.objects.get(id=tenant.facility.id)
                actor = User.objects.get(id=tenant.user.id)
                patient = Patient.objects.get(id=target_patient.id)
                assert target_writes_enabled(organisation) is True
                if not release_target.wait(timeout=20):
                    raise RuntimeError("target test release was not signalled")
                outcome = visit_check_in(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    patient_id=patient.id,
                    department_id=tenant.department.id,
                    visit_type="OUTPATIENT_NEW",
                    payer_type="CASH",
                )
                return (str(outcome.visit.id), str(outcome.queue.id), str(outcome.invoice.id))
        finally:
            clear_writer_label()
            connections.close_all()

    def rollback_writer():
        connections.close_all()
        set_writer_label("rollback")
        try:
            with tenant_atomic(tenant.organisation.id):
                _capture_backend_pid(
                    key="rollback",
                    backend_pids=backend_pids,
                    backend_pids_lock=backend_pids_lock,
                    ready=backend_pid_ready["rollback"],
                )
                organisation = Organisation.objects.get(id=tenant.organisation.id)
                actor = User.objects.get(id=tenant.user.id)
                switch = rollback_mig001(
                    organisation=organisation,
                    actor=actor,
                    reason="Synthetic fence race rollback",
                )
                return (switch.phase, switch.write_fence)
        finally:
            clear_writer_label()
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        target_future = executor.submit(target_writer)
        assert target_fence_acquired.wait(timeout=20)
        assert backend_pid_ready["target"].is_set()
        with backend_pids_lock:
            target_backend_pid = backend_pids["target"]
        rollback_future = executor.submit(rollback_writer)
        try:
            assert backend_pid_ready["rollback"].wait(timeout=20)
            with backend_pids_lock:
                rollback_backend_pid = backend_pids["rollback"]
            observation = _wait_for_lock_contention(
                blocked_pid=rollback_backend_pid,
                blocking_pid=target_backend_pid,
                query_fragment="core_migrationcutover",
            )
            assert observation["blocked_pid"] == rollback_backend_pid
            assert observation["blocking_pid"] == target_backend_pid
            assert observation["blocked_wait_event_type"] == "Lock"
            assert observation["blocked_locktype"] == "transactionid"
            assert observation["blocking_locktype"] == "transactionid"
            assert observation["blocked_granted"] is False
            assert observation["blocking_granted"] is True
            assert "core_migrationcutover" in observation["blocked_query"].lower()
            assert "core_migrationcutover" in observation["blocking_query"].lower()
        finally:
            release_target.set()
        target_result = target_future.result(timeout=20)
        rollback_result = rollback_future.result(timeout=20)

    with tenant_atomic(tenant.organisation.id):
        organisation = Organisation.objects.get(id=tenant.organisation.id)
        facility = Facility.objects.get(id=tenant.facility.id)
        actor = User.objects.get(id=tenant.user.id)
        target_visit_id, target_queue_id, target_invoice_id = target_result
        assert Visit.objects.filter(id=target_visit_id, patient_id=target_patient.id, state="OPEN").exists()
        assert QueueEntry.objects.filter(id=target_queue_id, visit_id=target_visit_id).exists()
        assert Invoice.objects.filter(id=target_invoice_id, visit_id=target_visit_id, status="ISSUED").exists()
        assert Visit.objects.filter(patient_id=target_patient.id).count() == 1
        assert QueueEntry.objects.filter(patient_id=target_patient.id, visit_id=target_visit_id).count() == 1
        assert Invoice.objects.filter(patient_id=target_patient.id, visit_id=target_visit_id).count() == 1
        assert InvoiceItem.objects.filter(
            invoice_id=target_invoice_id,
            source_type="CONSULTATION",
            state="ACTIVE",
        ).count() == 1
        assert Encounter.objects.filter(patient_id=target_patient.id).count() == 0
        switch = MigrationCutover.objects.get(
            organisation=organisation,
            migration_id="MIG-001",
        )
        assert rollback_result == ("ROLLBACK", switch.write_fence)
        assert switch.phase == "ROLLBACK"
        assert switch.target_reads_enabled is False
        assert switch.target_writes_enabled is False
        assert switch.write_fence == cutover_fence + 1
        assert QueueEntry.objects.filter(id=legacy_queue.id, visit_id=migrated_visit.id).exists()
        assert legacy_writes_enabled(organisation) is True

        blocked_patient = Patient.objects.create(
            organisation=organisation,
            patient_no=f"P-PG-S01-FENCE-BLOCKED-{uuid4().hex[:8]}",
            first_name="Blocked",
            last_name="Target",
            sex="UNKNOWN",
        )
        with pytest.raises(CanonicalError) as target_disabled:
            visit_check_in(
                organisation=organisation,
                facility=facility,
                actor=actor,
                patient_id=blocked_patient.id,
                department_id=tenant.department.id,
                visit_type="OUTPATIENT_NEW",
                payer_type="CASH",
            )
        assert target_disabled.value.code == "MIGRATION_TARGET_DISABLED"
        assert Visit.objects.filter(patient_id=blocked_patient.id).count() == 0
        assert QueueEntry.objects.filter(patient_id=blocked_patient.id).count() == 0
        assert Invoice.objects.filter(patient_id=blocked_patient.id).count() == 0


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
