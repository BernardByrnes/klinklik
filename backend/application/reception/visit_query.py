"""QRY-002: pure protected Visit owner projection."""

from dataclasses import dataclass

from billing.models import Invoice
from billing.queries import patient_outstanding_balance
from core.errors import CanonicalError
from core.clock import local_service_date
from core.migration_reconciliation import target_reads_enabled
from core.services import assert_transaction_active
from patients.models import Patient
from scheduling.models import QueueEntry, Visit

from application.clinical.encounter_context import query_encounter_context


@dataclass(frozen=True)
class VisitProjection:
    visit: Visit
    queue_entries: tuple
    invoice: Invoice | None


@dataclass(frozen=True)
class PatientCheckInProjection:
    patient: Patient
    outstanding_balance: object
    outstanding_invoice_no: str | None
    outstanding_visit_id: str | None
    active_visit: Visit | None
    active_queue_label: str | None


def get_visit_projection(*, organisation, facility, visit_id):
    """Read only the tenant/facility-owned administrative Visit projection."""

    assert_transaction_active()
    if not target_reads_enabled(organisation):
        raise CanonicalError(
            "MIGRATION_TARGET_DISABLED",
            "The Visit workspace is temporarily unavailable while migration compatibility is restored.",
            status_code=503,
            retryable=True,
        )
    visit = Visit.objects.select_related("patient", "opened_by", "closed_by").filter(
        id=visit_id,
        organisation=organisation,
        facility=facility,
    ).first()
    if visit is None:
        raise CanonicalError("VISIT_NOT_FOUND", "The Visit was not found in this facility.", status_code=404)
    queue_entries = tuple(
        QueueEntry.objects.select_related("department", "claimed_by")
        .filter(organisation=organisation, facility=facility, visit=visit)
        .order_by("queue_time", "sequence", "id")
    )
    invoice = (
        Invoice.objects.select_related("patient")
        .filter(organisation=organisation, facility=facility, visit=visit)
        .order_by("created_at", "id")
        .first()
    )
    return VisitProjection(
        visit=visit,
        queue_entries=queue_entries,
        invoice=invoice,
    )


def get_clinical_projection(*, organisation, facility, projection, include_clinical=True):
    """Compose QRY-003 from the protected Visit projection."""

    assert_transaction_active()
    return query_encounter_context(
        organisation=organisation,
        facility=facility,
        visit=projection.visit,
        queue_entries=projection.queue_entries,
        include_clinical=include_clinical,
    )


def get_patient_checkin_projection(*, organisation, facility, patient_id):
    """Compose the minimum administrative projection needed before check-in."""

    assert_transaction_active()
    if not target_reads_enabled(organisation):
        raise CanonicalError(
            "MIGRATION_TARGET_DISABLED",
            "The Visit workspace is temporarily unavailable while migration compatibility is restored.",
            status_code=503,
            retryable=True,
        )
    patient = Patient.objects.filter(id=patient_id, organisation=organisation).first()
    if patient is None:
        raise CanonicalError("PATIENT_NOT_FOUND", "The patient was not found in this organisation.", status_code=404)
    active_visit = Visit.objects.select_related("patient", "opened_by", "closed_by").filter(
        organisation=organisation,
        facility=facility,
        patient=patient,
        local_service_date=local_service_date(),
        state__in=Visit.ACTIVE_STATES,
    ).order_by("opened_at", "id").first()
    active_queue_label = None
    if active_visit is not None:
        active_queue = QueueEntry.objects.select_related("department").filter(
            organisation=organisation,
            facility=facility,
            visit=active_visit,
        ).exclude(status__in=("COMPLETED", "CANCELLED")).order_by("queue_time", "sequence", "id").first()
        active_queue_label = active_queue.queue_label if active_queue is not None else None
    balance = patient_outstanding_balance(
        organisation=organisation,
        facility=facility,
        patient=patient,
    )
    return PatientCheckInProjection(
        patient=patient,
        outstanding_balance=balance.amount,
        outstanding_invoice_no=balance.invoice_no,
        outstanding_visit_id=balance.visit_id,
        active_visit=active_visit,
        active_queue_label=active_queue_label,
    )
