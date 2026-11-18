"""S-08 PostgreSQL closure races, gates and durable denial proofs."""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone

from accounts.models import User
from application.reception.closure import visit_close
from audit.models import AuditEvent
from billing.models import Invoice, InvoiceItem
from billing.services import confirm_payment
from clinical.models import Encounter
from core.errors import CanonicalError
from core.services import tenant_atomic
from patients.models import Patient
from scheduling.models import QueueEntry, Visit
from tenancy.models import FacilityWorkflowPolicy

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="S-08 PostgreSQL proof gate"),
]


def _closable_visit(tenant, amount="30000.00"):
    with tenant_atomic(tenant.organisation.id):
        patient = Patient.objects.create(
            organisation=tenant.organisation,
            patient_no=f"P-PG-S08-{uuid4().hex[:8]}",
            first_name="S08 PG",
            last_name="Synthetic",
            sex="UNKNOWN",
            date_of_birth=date(1990, 1, 1),
        )
        visit = Visit.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=patient,
            local_service_date=date.today(),
            visit_type="OUTPATIENT_NEW",
            opened_by=tenant.user,
        )
        invoice = Invoice.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            invoice_no=f"INV-PG-S08-{uuid4().hex[:8]}",
            patient=patient,
            visit=visit,
            status="ISSUED",
            subtotal=Decimal(amount),
            total=Decimal(amount),
            balance=Decimal(amount),
            issued_at=timezone.now(),
            created_by=tenant.user,
        )
        InvoiceItem.objects.create(
            organisation=tenant.organisation,
            invoice=invoice,
            facility=tenant.facility,
            description="Synthetic S08 consultation",
            quantity=Decimal("1.00"),
            unit_price=Decimal(amount),
            amount=Decimal(amount),
            source_type="CONSULTATION",
            source_id=visit.id,
            source_line_identity="CONSULTATION",
            created_by=tenant.user,
        )
        Encounter.objects.create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            patient=patient,
            visit=visit,
            clinician=tenant.user,
            encounter_no=f"ENC-PG-S08-{uuid4().hex[:8]}",
            status="SIGNED",
        )
        return visit.id, visit.version, invoice.id


def test_pg_s08_concurrent_close_has_one_winner(tenant):
    visit_id, version, _invoice_id = _closable_visit(tenant, amount="0.00")
    with tenant_atomic(tenant.organisation.id):
        organisation = tenant.organisation
        facility = tenant.facility
        actor = User.objects.get(id=tenant.user.id)
    barrier = threading.Barrier(2)

    def attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                outcome = visit_close(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    visit_id=visit_id,
                    expected_version=version,
                )
                return ("ok", outcome.visit.state)
        except (CanonicalError, ValueError) as exc:
            return ("error", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _item: attempt(), range(2)))
    assert sorted(result[0] for result in results) == ["error", "ok"]
    with tenant_atomic(organisation.id):
        assert Visit.objects.get(id=visit_id).state == "CLOSED"
        assert AuditEvent.objects.filter(event_code="VISIT_CLOSED").count() == 1


def test_pg_s08_close_and_payment_never_leave_closed_unpaid(tenant):
    visit_id, version, invoice_id = _closable_visit(tenant)
    with tenant_atomic(tenant.organisation.id):
        organisation = tenant.organisation
        facility = tenant.facility
        actor = User.objects.get(id=tenant.user.id)
    barrier = threading.Barrier(2)

    def close_attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                outcome = visit_close(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    visit_id=visit_id,
                    expected_version=version,
                )
                return ("closed", outcome.visit.state)
        except (CanonicalError, ValueError) as exc:
            return ("refused", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    def payment_attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                outcome = confirm_payment(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    amount="30000.00",
                    method="CASH",
                    invoice_id=invoice_id,
                    require_shift=False,
                )
                return ("paid", str(outcome.payment.id))
        except (CanonicalError, ValueError) as exc:
            return ("refused", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        close_future = executor.submit(close_attempt)
        payment_future = executor.submit(payment_attempt)
        close_result = close_future.result()
        payment_result = payment_future.result()
    with tenant_atomic(organisation.id):
        visit = Visit.objects.get(id=visit_id)
        invoice = Invoice.objects.get(id=invoice_id)
        if visit.state == "CLOSED":
            assert invoice.balance == Decimal("0.00")
            assert payment_result[0] == "paid"
        else:
            assert close_result[0] in {"refused", "closed"}
            assert invoice.balance == Decimal("30000.00") or payment_result[0] == "paid"


def test_pg_s08_payment_gate_and_closure_serialize(tenant, authed_client, enabled_mig001_target):
    with tenant_atomic(tenant.organisation.id):
        FacilityWorkflowPolicy.objects.update_or_create(
            organisation=tenant.organisation,
            facility=tenant.facility,
            defaults={
                "consultation_payment_timing": "PAY_BEFORE_TRIAGE",
                "updated_by": tenant.user,
            },
        )
    from tests.test_s05_billing import check_in, register

    patient_id = register(authed_client, "s08-pg-register-gate")
    checked_in = check_in(authed_client, patient_id, tenant, "s08-pg-checkin-gate")
    with tenant_atomic(tenant.organisation.id):
        organisation = tenant.organisation
        facility = tenant.facility
        actor = User.objects.get(id=tenant.user.id)
        visit = Visit.objects.get(id=checked_in["visit_id"])
        assert QueueEntry.objects.get(id=checked_in["queue_id"]).state == "WAITING_PAYMENT"
        version = visit.version
    barrier = threading.Barrier(2)

    def close_attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                outcome = visit_close(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    visit_id=checked_in["visit_id"],
                    expected_version=version,
                )
                return ("closed", outcome.visit.state)
        except (CanonicalError, ValueError) as exc:
            return ("refused", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    def payment_attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=20)
            with tenant_atomic(organisation.id):
                outcome = confirm_payment(
                    organisation=organisation,
                    facility=facility,
                    actor=actor,
                    amount="30000.00",
                    method="CASH",
                    invoice_id=checked_in["invoice_id"],
                    require_shift=False,
                )
                return ("paid", str(outcome.payment.id))
        except (CanonicalError, ValueError) as exc:
            return ("refused", getattr(exc, "code", type(exc).__name__))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        close_future = executor.submit(close_attempt)
        payment_future = executor.submit(payment_attempt)
        close_result = close_future.result()
        payment_result = payment_future.result()
    assert payment_result[0] == "paid"
    assert close_result[0] == "refused"
    with tenant_atomic(organisation.id):
        assert Visit.objects.get(id=checked_in["visit_id"]).state != "CLOSED"
        assert QueueEntry.objects.get(id=checked_in["queue_id"]).state == "WAITING"
        assert AuditEvent.objects.filter(event_code="PAYMENT_GATE_RELEASED").count() == 1
