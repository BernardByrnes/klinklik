"""Transactional S-01 reception commands.

The HTTP layer owns authorization and response serialization. These functions
are deliberately transaction-neutral and must be called inside the one outer
tenant transaction provided by the application runner/API boundary.
"""

from dataclasses import dataclass
import hashlib

from django.db import IntegrityError, transaction

from application.contracts import CommandSpec
from audit.services import record_fact
from billing.models import Invoice, Payment, PaymentAllocation, PriceList
from billing.services import (
    create_payer_binding,
    issue_exact_source_lines,
    select_consultation_price,
    void_unpaid_visit_invoice,
)
from core.clock import local_service_date, now
from core.errors import CanonicalError
from core.services import assert_transaction_active
from clinical.models import Encounter, TriageAssessment, VitalsObservation
from patients.models import Patient
from patients.services import create_registered_patient, find_duplicate_candidates
from scheduling.models import ArrivalEnquiry, QueueEntry, Visit
from scheduling.services import (
    cancel_error_visit,
    convert_arrival_enquiry,
    create_initial_queue_entry,
    open_visit,
    record_arrival_enquiry,
    resolve_department,
    set_referral_source,
)
from tenancy.models import Facility, FacilityWorkflowPolicy, Organisation


CMD_001_SPEC = CommandSpec(
    operation_id="CMD-001",
    rank1_id="REC-001",
    capability="visit.create",
    owner_service="scheduling.visit.open",
    lock_plan=(
        "Facility",
        "FacilityWorkflowPolicy",
        "Department",
        "PriceList",
        "ServicePrice",
        "Patient",
        "ArrivalEnquiry",
        "Visit",
        "QueueEntry",
        "Invoice",
        "NumberSequence",
    ),
)
CMD_002_SPEC = CommandSpec(
    operation_id="CMD-002",
    rank1_id="REC-002",
    capability="patient.create",
    owner_service="patients.create_or_authorized_duplicate_resolution",
    lock_plan=("Patient", "NumberSequence"),
)
CMD_010_SPEC = CommandSpec(
    operation_id="CMD-010",
    rank1_id="REC-008",
    capability="visit.create",
    owner_service="scheduling.visit.set_referral_source",
    lock_plan=("Visit",),
)
CMD_011_SPEC = CommandSpec(
    operation_id="CMD-011",
    rank1_id="REC-013",
    capability="visit.create",
    owner_service="scheduling.arrival_enquiry.record",
    lock_plan=("Facility",),
)
CMD_006_SPEC = CommandSpec(
    operation_id="CMD-006",
    rank1_id="REC-010",
    capability="visit.cancel_error",
    owner_service="scheduling.services.visit.cancel_error",
    lock_plan=("Visit", "QueueEntry", "Invoice"),
)


CHARGEABLE_VISIT_TYPES = frozenset(
    {"OUTPATIENT_NEW", "OUTPATIENT_REVIEW", "ANC", "FOLLOW_UP_RESULTS"}
)
DESTINATION_CODES = {
    "OUTPATIENT_NEW": "OPD",
    "OUTPATIENT_REVIEW": "OPD",
    "FOLLOW_UP_RESULTS": "OPD",
    "ANC": "ANC",
    "PHARMACY_ONLY": "PHARMACY",
    "LAB_ONLY": "LAB",
}
QUEUE_TYPES = {
    "OUTPATIENT_NEW": "TRIAGE",
    "OUTPATIENT_REVIEW": "TRIAGE",
    "FOLLOW_UP_RESULTS": "CLINICIAN",
    "ANC": "ANC",
    "PHARMACY_ONLY": "PHARMACY",
}


@dataclass(frozen=True)
class PatientRegisterOutcome:
    patient: Patient | None
    duplicate_candidates: tuple[Patient, ...] = ()
    created: bool = False

    @property
    def status_code(self):
        return 201 if self.created else 200


@dataclass(frozen=True)
class VisitCheckInOutcome:
    visit: Visit
    queue: object | None
    invoice: object | None
    payer_binding: object
    arrival_enquiry: ArrivalEnquiry | None = None


@dataclass(frozen=True)
class ArrivalEnquiryOutcome:
    enquiry: ArrivalEnquiry
    created: bool = True


@dataclass(frozen=True)
class VisitCancelErrorOutcome:
    visit: Visit
    queue_entries: tuple
    invoice: Invoice | None


@dataclass(frozen=True)
class VisitContextOutcome:
    visit: Visit
    queue_entries: tuple
    invoice: Invoice | None
    encounters: tuple
    clinical_values_returned: bool


def _metadata(**values):
    return {key: str(value) for key, value in values.items() if value is not None}


def _reason_hash(reason):
    return hashlib.sha256(str(reason).strip().encode("utf-8")).hexdigest()


def _duplicate_resolution(data):
    resolution = data.get("duplicate_resolution") or data.get("duplicate_override")
    if isinstance(resolution, str):
        resolution = {"decision": resolution}
    if not isinstance(resolution, dict):
        resolution = {}
    if data.get("duplicate_override_reason") and "reason" not in resolution:
        resolution = {**resolution, "reason": data["duplicate_override_reason"]}
    return resolution


def patient_register(*, organisation, actor, data, request=None):
    assert_transaction_active()
    values = dict(data)
    # Serialised duplicate-resolution data is command input, never Patient data.
    resolution = _duplicate_resolution(values)
    values.pop("duplicate_resolution", None)
    values.pop("duplicate_override", None)
    values.pop("duplicate_override_reason", None)

    # The organisation lock serializes the exact-match decision even when no
    # candidate row exists yet, so two identical first registrations cannot
    # both pass the duplicate check.
    organisation = Organisation.objects.select_for_update().get(id=organisation.id)
    candidates = tuple(find_duplicate_candidates(organisation=organisation, data=values, for_update=True))
    decision = str(resolution.get("decision", "")).upper()
    if decision and decision not in {"NOT_THE_SAME", "CREATE_NEW", "OVERRIDE"}:
        raise CanonicalError(
            "DUPLICATE_RESOLUTION_INVALID",
            "The duplicate resolution decision is not supported.",
            status_code=422,
        )
    if resolution and not candidates:
        raise CanonicalError(
            "DUPLICATE_RESOLUTION_INVALID",
            "Duplicate resolution can only be supplied after a duplicate match.",
            status_code=422,
        )
    if candidates and decision not in {"NOT_THE_SAME", "CREATE_NEW", "OVERRIDE"}:
        return PatientRegisterOutcome(patient=None, duplicate_candidates=candidates, created=False)

    rejected_ids = resolution.get("rejected_candidate_ids")
    candidate_ids = {str(candidate.id) for candidate in candidates}
    if rejected_ids is None:
        rejected_ids = sorted(candidate_ids)
    if (
        not isinstance(rejected_ids, (list, tuple))
        or len(rejected_ids) != len(set(map(str, rejected_ids)))
        or set(map(str, rejected_ids)) != candidate_ids
    ):
        raise CanonicalError(
            "DUPLICATE_RESOLUTION_INVALID",
            "Duplicate resolution references an invalid candidate.",
            status_code=422,
        )
    if candidates and len(str(resolution.get("reason", "")).strip()) < 3:
        raise CanonicalError(
            "DUPLICATE_OVERRIDE_REASON_REQUIRED",
            "A reason is required when creating a patient after a duplicate match.",
            status_code=422,
        )

    patient = create_registered_patient(organisation=organisation, actor=actor, data=values)
    record_fact(
        organisation=organisation,
        actor=actor,
        event_code="PATIENT_CREATED",
        action="CREATE",
        entity_type="Patient",
        entity_id=patient.id,
        source_ids={"patient_id": patient.id},
        after={"identity_status": patient.identity_status, "status": patient.status},
    )
    if candidates:
        record_fact(
            organisation=organisation,
            actor=actor,
            event_code="DUPLICATE_OVERRIDE",
            action="CREATE",
            entity_type="Patient",
            entity_id=patient.id,
            source_ids={
                "patient_id": patient.id,
                "rejected_candidate_ids": sorted(map(str, rejected_ids)),
            },
            after={"reason_hash": _reason_hash(resolution["reason"]), "candidate_count": len(candidates)},
        )
    return PatientRegisterOutcome(patient=patient, created=True)


def _resolve_price(*, organisation, facility, payer_type, price_list_id):
    price_list, service, price = select_consultation_price(
        organisation=organisation,
        facility=facility,
        payer_type=payer_type,
        price_list_id=price_list_id,
    )
    if (price_list_id or PriceList.objects.filter(organisation=organisation).exists()) and price_list is None:
        raise CanonicalError(
            "NO_PRICE_LIST",
            "No active price list is available for this payer.",
            status_code=422,
        )
    if price is None:
        raise CanonicalError(
            "SERVICE_NOT_PRICED",
            "The consultation service is not priced for this facility and payer.",
            status_code=422,
            metadata={"service_code": "CONSULTATION"},
        )
    return price_list, service, price


def _destination(*, organisation, facility, visit_type, department_id):
    preferred_code = DESTINATION_CODES[visit_type]
    try:
        return resolve_department(
            organisation=organisation,
            facility=facility,
            department_id=department_id,
            preferred_code=preferred_code,
            required=True,
        )
    except ValueError as exc:
        raise CanonicalError(
            "DESTINATION_UNAVAILABLE",
            "The selected check-in destination is not available.",
            status_code=422,
        ) from exc


def visit_check_in(
    *,
    organisation,
    facility,
    actor,
    patient_id,
    department_id=None,
    visit_type="OUTPATIENT_NEW",
    payer_type="CASH",
    reason_for_visit="",
    referral_source_type="SELF",
    referral_source_name="",
    price_list_id=None,
    arrival_enquiry_id=None,
    arrival_enquiry_version=None,
    notes="",
    request=None,
):
    assert_transaction_active()
    visit_type = str(visit_type or "").upper()
    payer_type = str(payer_type or "").upper()
    if visit_type == "WALK_IN":
        visit_type = "OUTPATIENT_NEW"
    if visit_type not in dict(Visit.VISIT_TYPE_CHOICES):
        raise CanonicalError("INVALID_INPUT", "The visit type is not supported.", status_code=422)
    if payer_type not in {choice[0] for choice in PriceList.PAYER_TYPE_CHOICES}:
        raise CanonicalError("INVALID_INPUT", "The payer type is not supported.", status_code=422)
    if referral_source_type not in dict(Visit.REFERRAL_SOURCE_CHOICES):
        raise CanonicalError("INVALID_INPUT", "The referral source is not supported.", status_code=422)
    if len(referral_source_name or "") > 100:
        raise CanonicalError("INVALID_INPUT", "The referral source name is too long.", status_code=422)

    facility = Facility.objects.select_for_update().filter(
        id=facility.id,
        organisation=organisation,
        is_active=True,
    ).first()
    if facility is None:
        raise CanonicalError("FACILITY_INACTIVE", "The selected facility is not active.", status_code=422)
    policy = FacilityWorkflowPolicy.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
    ).first()
    department = _destination(
        organisation=organisation,
        facility=facility,
        visit_type=visit_type,
        department_id=department_id,
    )
    price_list = service = price = None
    if visit_type in CHARGEABLE_VISIT_TYPES:
        price_list, service, price = _resolve_price(
            organisation=organisation,
            facility=facility,
            payer_type=payer_type,
            price_list_id=price_list_id,
        )

    patient = Patient.objects.select_for_update().filter(
        id=patient_id,
        organisation=organisation,
    ).first()
    if patient is None:
        raise CanonicalError(
            "PATIENT_NOT_FOUND",
            "The patient was not found in this organisation.",
            status_code=404,
        )
    if patient.status != "ACTIVE" or patient.identity_status == "MERGED":
        raise CanonicalError(
            "PATIENT_INACTIVE",
            "The patient is inactive and cannot be checked in.",
            status_code=422,
            metadata={"patient_id": str(patient.id)},
        )

    service_day = local_service_date()
    enquiry = None
    if arrival_enquiry_id:
        enquiry = ArrivalEnquiry.objects.select_for_update().filter(
            id=arrival_enquiry_id,
            organisation=organisation,
            facility=facility,
        ).first()
        if enquiry is None:
            raise CanonicalError(
                "ARRIVAL_ENQUIRY_NOT_FOUND",
                "The arrival enquiry was not found in this facility.",
                status_code=404,
            )
        if arrival_enquiry_version is not None and enquiry.version != arrival_enquiry_version:
            raise CanonicalError(
                "VERSION_CONFLICT",
                "The arrival enquiry changed; refresh before converting it.",
                status_code=409,
            )
        if enquiry.state != "OPEN":
            raise CanonicalError(
                "ARRIVAL_ENQUIRY_ALREADY_CONVERTED",
                "The arrival enquiry has already been converted.",
                status_code=409,
                metadata={"enquiry_id": str(enquiry.id)},
            )

    existing_visit = Visit.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        patient=patient,
        local_service_date=service_day,
        state__in=Visit.ACTIVE_STATES,
    ).first()
    if existing_visit is not None:
        current_queue = (
            QueueEntry.objects.select_related("department", "claimed_by")
            .filter(
                organisation=organisation,
                facility=facility,
                visit=existing_visit,
            )
            .exclude(status__in={"COMPLETED", "CANCELLED"})
            .order_by("queue_time", "sequence", "id")
            .first()
        )
        raise CanonicalError(
            "VISIT_ALREADY_OPEN",
            "The patient already has an open Visit today.",
            status_code=409,
            metadata={
                "visit_id": str(existing_visit.id),
                "visit_state": existing_visit.state,
                "current_queue": current_queue.queue_label if current_queue else None,
                "assigned_clinician": str(current_queue.claimed_by_id) if current_queue and current_queue.claimed_by_id else None,
            },
        )

    visit = open_visit(
        organisation=organisation,
        facility=facility,
        actor=actor,
        patient=patient,
        local_service_day=service_day,
        visit_type=visit_type,
        reason_for_visit=reason_for_visit,
        referral_source_type=referral_source_type,
        referral_source_name=referral_source_name,
        results_review=visit_type == "FOLLOW_UP_RESULTS",
    )
    payer_binding, _ = create_payer_binding(
        organisation=organisation,
        facility=facility,
        visit=visit,
        actor=actor,
        payer_type=payer_type,
        price_list=price_list,
    )
    visit.payer_binding_id = payer_binding.id
    visit.save(update_fields=["payer_binding_id", "updated_at"])

    queue = None
    if department is not None and visit_type != "LAB_ONLY":
        queue_type = QUEUE_TYPES[visit_type]
        payment_before = (
            policy is not None
            and policy.consultation_payment_timing == "PAY_BEFORE_TRIAGE"
            and visit_type in CHARGEABLE_VISIT_TYPES
        )
        queue = create_initial_queue_entry(
            organisation=organisation,
            facility=facility,
            actor=actor,
            visit=visit,
            department=department,
            queue_type=queue_type,
            status="WAITING_PAYMENT" if payment_before else "WAITING",
            notes=notes,
        )

    invoice = None
    if visit_type in CHARGEABLE_VISIT_TYPES:
        invoice, _ = issue_exact_source_lines(
            organisation=organisation,
            facility=facility,
            actor=actor,
            visit=visit,
            service=service,
            price=price,
            request=request,
        )

    patient.last_seen_at = now()
    patient.version += 1
    patient.save(update_fields=["last_seen_at", "version", "updated_at"])

    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="VISIT_OPENED",
        action="CREATE",
        entity_type="Visit",
        entity_id=visit.id,
        source_ids=_metadata(
            visit_id=visit.id,
            patient_id=patient.id,
            payer_binding_id=payer_binding.id,
            arrival_enquiry_id=enquiry.id if enquiry else None,
        ),
        after={
            "state": visit.state,
            "visit_type": visit.visit_type,
            "referral_source_type": visit.referral_source_type,
        },
    )
    if queue is not None:
        record_fact(
            organisation=organisation,
            actor=actor,
            facility=facility,
            event_code="QUEUE_ENTRY_CREATED",
            action="CREATE",
            entity_type="QueueEntry",
            entity_id=queue.id,
            source_ids={"visit_id": visit.id, "queue_entry_id": queue.id},
            after={"state": queue.status, "queue_type": queue.queue_type},
        )
    if department is not None and department.code.upper() != DESTINATION_CODES[visit_type]:
        record_fact(
            organisation=organisation,
            actor=actor,
            facility=facility,
            event_code="ROUTING_OVERRIDDEN",
            action="CREATE",
            entity_type="Visit",
            entity_id=visit.id,
            source_ids={"visit_id": visit.id},
            after={
                "default_destination": DESTINATION_CODES[visit_type],
                "selected_destination": department.code,
            },
        )
    if invoice is not None:
        record_fact(
            organisation=organisation,
            actor=actor,
            facility=facility,
            event_code="INVOICE_ISSUED",
            action="CREATE",
            entity_type="Invoice",
            entity_id=invoice.id,
            source_ids={"visit_id": visit.id, "invoice_id": invoice.id},
            after={"state": invoice.status, "line_count": 1},
        )
    if enquiry is not None:
        try:
            enquiry, _ = convert_arrival_enquiry(enquiry=enquiry, visit=visit, actor=actor)
        except ValueError as exc:
            raise CanonicalError("VERSION_CONFLICT", str(exc), status_code=409) from exc
        record_fact(
            organisation=organisation,
            actor=actor,
            facility=facility,
            event_code="ARRIVAL_ENQUIRY_CONVERTED",
            action="UPDATE",
            entity_type="ArrivalEnquiry",
            entity_id=enquiry.id,
            source_ids={"enquiry_id": enquiry.id, "visit_id": visit.id},
            after={"state": enquiry.state},
        )
    return VisitCheckInOutcome(
        visit=visit,
        queue=queue,
        invoice=invoice,
        payer_binding=payer_binding,
        arrival_enquiry=enquiry,
    )


def arrival_enquiry_record(*, organisation, facility, actor, reason_code, source_event_id, safe_notes="", request=None):
    assert_transaction_active()
    facility = Facility.objects.select_for_update().filter(
        id=facility.id,
        organisation=organisation,
        is_active=True,
    ).first()
    if facility is None:
        raise CanonicalError("FACILITY_INACTIVE", "The selected facility is not active.", status_code=422)
    existing = ArrivalEnquiry.objects.filter(
        organisation=organisation,
        source_event_id=source_event_id,
    ).first()
    if existing is not None:
        raise CanonicalError(
            "ARRIVAL_ENQUIRY_ALREADY_EXISTS",
            "The source event has already recorded an arrival enquiry.",
            status_code=409,
            metadata={"enquiry_id": str(existing.id)},
        )
    try:
        with transaction.atomic():
            enquiry = record_arrival_enquiry(
                organisation=organisation,
                facility=facility,
                actor=actor,
                reason_code=reason_code,
                source_event_id=source_event_id,
                safe_notes=safe_notes,
            )
    except IntegrityError as exc:
        raise CanonicalError(
            "ARRIVAL_ENQUIRY_ALREADY_EXISTS",
            "The source event has already recorded an arrival enquiry.",
            status_code=409,
        ) from exc
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="ARRIVAL_ENQUIRY_RECORDED",
        action="CREATE",
        entity_type="ArrivalEnquiry",
        entity_id=enquiry.id,
        source_ids={"enquiry_id": enquiry.id, "source_event_id": source_event_id},
        after={"state": enquiry.state, "reason_code": enquiry.reason_code},
    )
    return ArrivalEnquiryOutcome(enquiry=enquiry)


def visit_referral_source_record(
    *, organisation, facility, actor, visit_id, source_type, source_name="", expected_version=None, request=None
):
    assert_transaction_active()
    visit = Visit.objects.filter(id=visit_id, organisation=organisation, facility=facility).first()
    if visit is None:
        raise CanonicalError("VISIT_NOT_FOUND", "The Visit was not found in this facility.", status_code=404)
    try:
        visit = set_referral_source(
            organisation=organisation,
            facility=facility,
            actor=actor,
            visit=visit,
            source_type=source_type,
            source_name=source_name,
            expected_version=expected_version,
        )
    except ValueError as exc:
        code = "VERSION_CONFLICT" if "changed" in str(exc) else "INVALID_STATE"
        raise CanonicalError(code, str(exc), status_code=409 if code == "VERSION_CONFLICT" else 422) from exc
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="VISIT_REFERRAL_SOURCE_RECORDED",
        action="UPDATE",
        entity_type="Visit",
        entity_id=visit.id,
        source_ids={"visit_id": visit.id},
        after={"referral_source_type": visit.referral_source_type, "version": visit.version},
    )
    return visit


def visit_cancel_error(
    *,
    organisation,
    facility,
    actor,
    visit_id,
    reason,
    expected_version=None,
    request=None,
):
    """Cancel a mistaken, unstarted check-in within the 15-minute grace window."""

    assert_transaction_active()
    facility = Facility.objects.select_for_update().filter(
        id=facility.id,
        organisation=organisation,
        is_active=True,
    ).first()
    if facility is None:
        raise CanonicalError("FACILITY_INACTIVE", "The selected facility is not active.", status_code=422)

    visit = Visit.objects.select_for_update().filter(
        id=visit_id,
        organisation=organisation,
        facility=facility,
    ).first()
    if visit is None:
        raise CanonicalError("VISIT_NOT_FOUND", "The Visit was not found in this facility.", status_code=404)
    if expected_version is not None and visit.version != expected_version:
        raise CanonicalError(
            "VERSION_CONFLICT",
            "The Visit changed; refresh before cancelling it.",
            status_code=409,
        )
    if visit.state != "OPEN":
        raise CanonicalError(
            "INVALID_STATE",
            "Only an open Visit can be cancelled as an erroneous check-in.",
            status_code=409,
            metadata={"visit_state": visit.state},
        )

    queue_entries = tuple(
        QueueEntry.objects.select_for_update()
        .filter(organisation=organisation, facility=facility, visit=visit)
        .order_by("queue_time", "sequence", "id")
    )
    queue_ids = [entry.id for entry in queue_entries]
    triage = TriageAssessment.objects.filter(
        organisation=organisation,
        facility=facility,
        queue_entry_id__in=queue_ids,
    ).order_by("id").first()
    if triage is not None:
        raise CanonicalError(
            "CLINICAL_DATA_EXISTS",
            "The Visit has downstream clinical data and cannot be cancelled here.",
            status_code=409,
            metadata={"blocking_record_type": "TriageAssessment"},
        )
    encounter = Encounter.objects.filter(
        organisation=organisation,
        facility=facility,
        queue_entry_id__in=queue_ids,
    ).order_by("id").first()
    if encounter is not None:
        raise CanonicalError(
            "CLINICAL_DATA_EXISTS",
            "The Visit has downstream clinical data and cannot be cancelled here.",
            status_code=409,
            metadata={"blocking_record_type": "Encounter"},
        )
    vitals = VitalsObservation.objects.filter(
        organisation=organisation,
        facility=facility,
        patient_id=visit.patient_id,
        measured_at__gte=visit.opened_at,
    ).order_by("id").first()
    if vitals is not None:
        raise CanonicalError(
            "CLINICAL_DATA_EXISTS",
            "The Visit has downstream clinical data and cannot be cancelled here.",
            status_code=409,
            metadata={"blocking_record_type": "VitalsObservation"},
        )

    invoice = Invoice.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        visit=visit,
    ).order_by("created_at", "id").first()
    if invoice is not None and (
        invoice.amount_paid > 0
        or invoice.status in {"PAID", "PARTIALLY_PAID"}
        or PaymentAllocation.objects.filter(invoice=invoice).exists()
        or Payment.objects.filter(invoice=invoice, status="POSTED").exists()
    ):
        raise CanonicalError(
            "PAYMENT_EXISTS",
            "The Visit has downstream payment data and cannot be cancelled here.",
            status_code=409,
            metadata={"blocking_record_type": "Payment"},
        )

    elapsed_seconds = max(0, int((now() - visit.opened_at).total_seconds()))
    if elapsed_seconds >= 15 * 60:
        raise CanonicalError(
            "GRACE_WINDOW_EXPIRED",
            "The erroneous check-in grace window has expired.",
            status_code=422,
            metadata={"elapsed_seconds": elapsed_seconds},
        )

    reason_hash = _reason_hash(reason)
    if invoice is not None:
        try:
            invoice, _ = void_unpaid_visit_invoice(
                organisation=organisation,
                facility=facility,
                actor=actor,
                invoice=invoice,
                reason_hash=reason_hash,
            )
        except ValueError as exc:
            raise CanonicalError(
                "PAYMENT_EXISTS",
                "The Visit has downstream payment data and cannot be cancelled here.",
                status_code=409,
                metadata={"blocking_record_type": "Payment"},
            ) from exc

    try:
        visit, queue_entries = cancel_error_visit(
            organisation=organisation,
            facility=facility,
            actor=actor,
            visit_id=visit.id,
            reason=reason,
            expected_version=expected_version,
        )
    except ValueError as exc:
        code = "VERSION_CONFLICT" if "changed" in str(exc) else "INVALID_STATE"
        raise CanonicalError(code, str(exc), status_code=409) from exc

    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="VISIT_CANCELLED_ERROR",
        action="UPDATE",
        entity_type="Visit",
        entity_id=visit.id,
        source_ids={"visit_id": visit.id, "patient_id": visit.patient_id},
        after={
            "state": visit.state,
            "elapsed_seconds": elapsed_seconds,
            "reason_hash": reason_hash,
        },
    )
    for entry in queue_entries:
        if entry.status == "CANCELLED":
            record_fact(
                organisation=organisation,
                actor=actor,
                facility=facility,
                event_code="QUEUE_CANCELLED",
                action="UPDATE",
                entity_type="QueueEntry",
                entity_id=entry.id,
                source_ids={"visit_id": visit.id, "queue_entry_id": entry.id},
                after={"state": entry.status, "reason_hash": reason_hash},
            )
    if invoice is not None and invoice.status == "VOIDED":
        record_fact(
            organisation=organisation,
            actor=actor,
            facility=facility,
            event_code="INVOICE_VOIDED",
            action="UPDATE",
            entity_type="Invoice",
            entity_id=invoice.id,
            source_ids={"visit_id": visit.id, "invoice_id": invoice.id},
            after={"state": invoice.status, "reason_hash": reason_hash},
        )
    return VisitCancelErrorOutcome(
        visit=visit,
        queue_entries=tuple(queue_entries),
        invoice=invoice,
    )


def visit_context(*, organisation, facility, actor, visit_id, include_clinical=False, request=None):
    """Return the protected administrative Visit projection and optional clinical values."""

    assert_transaction_active()
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
    invoice = Invoice.objects.filter(
        organisation=organisation,
        facility=facility,
        visit=visit,
    ).order_by("created_at", "id").first()
    queue_ids = [entry.id for entry in queue_entries]
    encounters = tuple(
        Encounter.objects.select_related("clinician")
        .filter(
            organisation=organisation,
            facility=facility,
            queue_entry_id__in=queue_ids,
        )
        .order_by("started_at", "id")
    )
    clinical_values_returned = bool(include_clinical and encounters)
    if clinical_values_returned:
        record_fact(
            organisation=organisation,
            actor=actor,
            facility=facility,
            event_code="PHI_READ",
            action="READ",
            entity_type="Visit",
            entity_id=visit.id,
            source_ids={
                "visit_id": visit.id,
                "encounter_ids": [encounter.id for encounter in encounters],
            },
            after={"values_returned": True, "encounter_count": len(encounters)},
        )
    return VisitContextOutcome(
        visit=visit,
        queue_entries=queue_entries,
        invoice=invoice,
        encounters=encounters if include_clinical else tuple(),
        clinical_values_returned=clinical_values_returned,
    )
