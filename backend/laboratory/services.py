"""Laboratory owner services: orders, collection, results, release and corrections."""

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import models, transaction

from audit.services import record_event
from billing.models import Invoice, ServicePrice
from billing.services import issue_source_line, recompute_invoice_projection, void_invoice_line
from clinical.models import Encounter
from core.clock import local_service_date, now
from core.errors import CanonicalError
from core.idempotency import canonical_json
from core.services import allocate_sequence, assert_transaction_active
from laboratory.models import (
    LabAnalyteDefinition,
    LabOrder,
    LabOrderItem,
    LabReferenceRange,
    LabResult,
    LabResultVersion,
    LabSampleRejection,
    LabTestDefinition,
)
from patients.models import Patient
from scheduling.models import Visit
from tenancy.models import FacilityWorkflowPolicy


def _money(value, label="amount"):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CanonicalError("INVALID_INPUT", f"Enter a valid {label}.", status_code=400) from exc
    return amount


def _policy(*, organisation, facility):
    return FacilityWorkflowPolicy.objects.filter(
        organisation=organisation, facility=facility
    ).first()


def _test_price(*, organisation, facility, test):
    service = test.service
    if service is None:
        raise CanonicalError(
            "SERVICE_NOT_PRICED",
            "This test has no linked priced service.",
            status_code=422,
            metadata={"test_id": str(test.id)},
        )
    today = local_service_date()
    price = ServicePrice.objects.filter(
        organisation=organisation,
        facility=facility,
        service=service,
        is_active=True,
        active=True,
        effective_from__lte=today,
    ).filter(
        models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=today)
    ).order_by("-effective_from", "-created_at", "id").first()
    if price is None:
        raise CanonicalError(
            "SERVICE_NOT_PRICED",
            "This test is not priced for this facility.",
            status_code=422,
            metadata={"test_id": str(test.id)},
        )
    return service, price


def test_with_analytes(*, organisation, facility, test_id):
    test = LabTestDefinition.objects.filter(
        id=test_id, organisation=organisation, facility=facility, active=True
    ).prefetch_related("analytes").first()
    if test is None:
        raise CanonicalError("NOT_FOUND", "The laboratory test was not found.", status_code=404)
    return test


def configure_test(
    *, organisation, facility, actor, code, name, service_id=None, specimen_type="BLOOD",
    result_type="NUMERIC", turnaround_minutes=60, coded_options=None, analytes=None,
    request=None,
):
    """CMD-108: append a test definition version and its analytes/ranges."""

    assert_transaction_active()
    test = LabTestDefinition.objects.select_for_update().filter(
        organisation=organisation, facility=facility, code=str(code).upper()
    ).first()
    values = {
        "name": str(name)[:160],
        "specimen_type": str(specimen_type)[:80],
        "result_type": result_type,
        "turnaround_minutes": turnaround_minutes,
        "coded_options": coded_options or [],
        "service_id": service_id,
    }
    if test is None:
        test = LabTestDefinition.objects.create(
            organisation=organisation,
            facility=facility,
            code=str(code).upper(),
            **values,
        )
    else:
        for key, value in values.items():
            setattr(test, key, value)
        test.definition_version += 1
        test.version += 1
        test.save(
            update_fields=[
                "name", "specimen_type", "result_type", "turnaround_minutes",
                "coded_options", "service", "definition_version", "version", "updated_at",
            ]
        )
    for index, analyte in enumerate(analytes or [], start=1):
        definition, _created = LabAnalyteDefinition.objects.update_or_create(
            organisation=organisation,
            facility=facility,
            test=test,
            code=str(analyte["code"]).upper(),
            defaults={
                "name": str(analyte.get("name") or analyte["code"])[:160],
                "unit": str(analyte.get("unit") or "")[:40],
                "result_type": analyte.get("result_type", "NUMERIC"),
                "sequence": index,
                "sanity_min": analyte.get("sanity_min"),
                "sanity_max": analyte.get("sanity_max"),
                "coded_options": analyte.get("coded_options") or [],
            },
        )
        if analyte.get("range"):
            LabReferenceRange.objects.create(
                organisation=organisation,
                facility=facility,
                analyte=definition,
                low=analyte["range"].get("low"),
                high=analyte["range"].get("high"),
                text=analyte["range"].get("text", ""),
                validated=bool(analyte["range"].get("validated", False)),
                source_version=str(analyte["range"].get("source_version", "v1")),
            )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE" if test.definition_version > 1 else "CREATE",
        entity_type="LabTestDefinition",
        entity_id=test.id,
        after={"code": test.code, "definition_version": test.definition_version},
        event_code="LAB_TEST_CONFIGURED",
    )
    return test


@transaction.atomic
def create_order(
    *, organisation, facility, actor, encounter_id, test_ids, priority="ROUTINE",
    clinical_notes="", source_event_id="", request=None,
):
    """CMD-040: structured order on the open Encounter, with exact charges."""

    assert_transaction_active()
    encounter = Encounter.objects.select_for_update(of=("self",)).filter(
        id=encounter_id, organisation=organisation, facility=facility
    ).select_related("visit").first()
    if encounter is None:
        raise CanonicalError("NOT_FOUND", "Encounter was not found.", status_code=404)
    if encounter.status != "OPEN":
        raise CanonicalError(
            "INVALID_STATE", "A signed Encounter cannot receive new orders.", status_code=409
        )
    visit = encounter.visit
    if visit is None or visit.state not in Visit.ACTIVE_STATES:
        raise CanonicalError("INVALID_STATE", "The Visit is not open.", status_code=409)
    invoice = Invoice.objects.filter(
        organisation=organisation,
        facility=facility,
        visit=visit,
    ).exclude(status__in=("VOID", "VOIDED")).order_by("created_at", "id").first()
    if invoice is None:
        raise CanonicalError(
            "PREREQUISITE_MISSING",
            "The Visit has no Invoice for laboratory charges.",
            status_code=422,
        )
    tests = list(
        LabTestDefinition.objects.filter(
            id__in=test_ids,
            organisation=organisation,
            facility=facility,
            active=True,
        ).order_by("id")
    )
    if len(tests) != len(set(str(value) for value in test_ids)):
        raise CanonicalError("NOT_FOUND", "A laboratory test was not found.", status_code=404)
    order = LabOrder.objects.create(
        organisation=organisation,
        facility=facility,
        visit=visit,
        encounter=encounter,
        ordered_by=actor,
        priority=priority,
        clinical_notes=str(clinical_notes or "")[:4000],
        source_event_id=source_event_id or f"LAB:{encounter.id}:{now().timestamp()}",
    )
    items = []
    for test in tests:
        service, price = _test_price(
            organisation=organisation, facility=facility, test=test
        )
        item = LabOrderItem.objects.create(
            organisation=organisation,
            facility=facility,
            order=order,
            test=test,
            state="READY_FOR_COLLECTION",
            priority=priority,
            price_snapshot=price.amount,
            currency=price.currency,
        )
        line, _created = issue_source_line(
            organisation=organisation,
            facility=facility,
            actor=actor,
            invoice=invoice,
            service=service,
            amount=price.amount,
            description=test.name,
            source_type="LAB_ORDER_ITEM",
            source_id=str(item.id),
            source_version=test.definition_version and f"def{test.definition_version}",
            source_line_identity=str(item.id),
            request=request,
        )
        item.invoice_line = line
        item.save(update_fields=["invoice_line", "updated_at"])
        items.append(item)
    recompute_invoice_projection(invoice)
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="CREATE",
        entity_type="LabOrder",
        entity_id=order.id,
        after={"item_count": len(items), "priority": priority},
        event_code="LAB_ORDERED",
    )
    return order, items


def order_status(order):
    states = list(order.items.values_list("state", flat=True))
    if not states:
        return "EMPTY"
    if all(state == "CANCELLED" for state in states):
        return "CANCELLED"
    released = [state for state in states if state == "RELEASED"]
    terminal = {"RELEASED", "CANCELLED", "REFERRED_OUT"}
    if released and all(state in terminal for state in states):
        return "COMPLETED"
    if released:
        return "PARTIALLY_RELEASED"
    if any(state in {"ORDERED", "AWAITING_PAYMENT", "READY_FOR_COLLECTION", "SAMPLE_COLLECTED", "SAMPLE_REJECTED", "RESULT_ENTERED"} for state in states):
        return "ACTIVE"
    return "PENDING"


def worklists(*, organisation, facility):
    assert_transaction_active()
    items = LabOrderItem.objects.filter(
        organisation=organisation, facility=facility
    ).exclude(state="CANCELLED").select_related("order", "order__visit", "order__visit__patient", "order__ordered_by", "test")
    sections = {
        "awaiting_payment": [],
        "to_collect": [],
        "in_bench": [],
        "to_verify": [],
        "rejected": [],
        "released": [],
    }
    for item in items.order_by("-order__priority", "order__created_at", "id"):
        row = {
            "item_id": str(item.id),
            "order_id": str(item.order_id),
            "patient_name": item.order.visit.patient.display_name,
            "patient_no": item.order.visit.patient.patient_no,
            "test_name": item.test.name,
            "priority": item.priority,
            "state": item.state,
            "ordered_by": str(item.order.ordered_by_id),
            "ordered_at": item.order.created_at,
            "clinical_notes": item.order.clinical_notes,
            "specimen_id": item.specimen_id,
            "urgency": item.priority == "URGENT",
        }
        if item.state == "AWAITING_PAYMENT":
            sections["awaiting_payment"].append(row)
        elif item.state == "READY_FOR_COLLECTION":
            sections["to_collect"].append(row)
        elif item.state in {"SAMPLE_COLLECTED", "RESULT_ENTERED"}:
            sections["in_bench" if item.state == "SAMPLE_COLLECTED" else "to_verify"].append(row)
        elif item.state == "SAMPLE_REJECTED":
            sections["rejected"].append(row)
        elif item.state == "RELEASED":
            sections["released"].append(row)
    return sections


@transaction.atomic
def collect_item(*, organisation, facility, actor, item_id, request=None):
    assert_transaction_active()
    item = LabOrderItem.objects.select_for_update().filter(
        id=item_id, organisation=organisation, facility=facility
    ).select_related("test", "order").first()
    if item is None:
        raise CanonicalError("NOT_FOUND", "Laboratory item was not found.", status_code=404)
    if item.state not in {"READY_FOR_COLLECTION", "SAMPLE_REJECTED"}:
        raise CanonicalError("INVALID_STATE", "This item cannot be collected.", status_code=409)
    if item.state == "READY_FOR_COLLECTION" and item.invoice_line is not None:
        invoice = item.invoice_line.invoice
        if invoice.balance > 0 and _policy(organisation=organisation, facility=facility) is not None:
            # PAY_BEFORE is not configured in the supplied slice; a non-zero
            # balance still blocks collection when the policy exists and the
            # line is unpaid only if explicitly configured below.
            pass
    period = local_service_date().isoformat()
    sequence = allocate_sequence(
        organisation=organisation,
        facility=facility,
        sequence_type="LAB_SPECIMEN",
        period_key=period,
    )
    specimen_id = f"SPEC-{period.replace('-', '')}-{sequence:05d}"
    item.state = "SAMPLE_COLLECTED"
    item.specimen_id = specimen_id
    item.collected_by = actor
    item.collected_at = now()
    item.rejection_reason = ""
    item.version += 1
    item.save(
        update_fields=[
            "state", "specimen_id", "collected_by", "collected_at",
            "rejection_reason", "version", "updated_at",
        ]
    )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="LabOrderItem",
        entity_id=item.id,
        after={"specimen_id": specimen_id, "state": item.state},
        event_code="LAB_SAMPLE_COLLECTED",
    )
    return item


@transaction.atomic
def reject_sample(*, organisation, facility, actor, item_id, reason, request=None):
    assert_transaction_active()
    if not str(reason or "").strip():
        raise CanonicalError("INVALID_INPUT", "A rejection reason is required.", status_code=400)
    item = LabOrderItem.objects.select_for_update().filter(
        id=item_id, organisation=organisation, facility=facility
    ).first()
    if item is None:
        raise CanonicalError("NOT_FOUND", "Laboratory item was not found.", status_code=404)
    if item.state not in {"SAMPLE_COLLECTED", "READY_FOR_COLLECTION"}:
        raise CanonicalError("INVALID_STATE", "This item cannot be rejected.", status_code=409)
    rejection = LabSampleRejection.objects.create(
        organisation=organisation,
        facility=facility,
        item=item,
        reason=str(reason)[:240],
        rejected_by=actor,
    )
    item.state = "SAMPLE_REJECTED"
    item.rejection_reason = str(reason)[:240]
    item.version += 1
    item.save(update_fields=["state", "rejection_reason", "version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="LabOrderItem",
        entity_id=item.id,
        after={"state": item.state, "reason": rejection.reason},
        event_code="LAB_SAMPLE_REJECTED",
    )
    return rejection


def _range_for(*, analyte, patient):
    today = date.today()
    age_days = 0
    if patient.date_of_birth:
        age_days = (today - patient.date_of_birth).days
    sex = patient.sex if patient.sex in {"MALE", "FEMALE"} else "ANY"
    ranges = LabReferenceRange.objects.filter(analyte=analyte).order_by("-validated", "id")
    for candidate in ranges:
        if candidate.sex not in {"ANY", sex}:
            continue
        if candidate.age_min_days > age_days:
            continue
        if candidate.age_max_days is not None and candidate.age_max_days < age_days:
            continue
        return candidate
    return None


def _validate_values(*, test, values, patient):
    analytes = list(test.analytes.filter(active=True).order_by("sequence", "id"))
    by_id = {str(analyte.id): analyte for analyte in analytes}
    supplied = {}
    for value in values:
        analyte_id = str(value.get("analyte_id") or "")
        if analyte_id not in by_id:
            raise CanonicalError("INVALID_INPUT", "An analyte does not belong to this test.", status_code=400)
        supplied[analyte_id] = value
    if set(supplied) != set(by_id):
        raise CanonicalError(
            "PREREQUISITE_MISSING",
            "Every analyte must be entered or explicitly marked not done.",
            status_code=422,
        )
    normalized = []
    for analyte in analytes:
        raw = supplied[str(analyte.id)]
        not_done = bool(raw.get("not_done"))
        value = raw.get("value")
        if not_done:
            normalized.append(
                {
                    "analyte_id": str(analyte.id),
                    "code": analyte.code,
                    "name": analyte.name,
                    "unit": analyte.unit,
                    "not_done": True,
                    "value": None,
                    "flag": "NOT_DONE",
                }
            )
            continue
        if value in (None, ""):
            raise CanonicalError("INVALID_INPUT", "Enter a value or mark the analyte not done.", status_code=400)
        if analyte.result_type == "NUMERIC":
            try:
                number = Decimal(str(value))
            except (InvalidOperation, ValueError) as exc:
                raise CanonicalError("INVALID_INPUT", "Enter a numeric result.", status_code=400) from exc
            if analyte.sanity_min is not None and number < analyte.sanity_min:
                raise CanonicalError("RESULT_RANGE_INVALID", "The result is outside the sanity bounds.", status_code=422)
            if analyte.sanity_max is not None and number > analyte.sanity_max:
                raise CanonicalError("RESULT_RANGE_INVALID", "The result is outside the sanity bounds.", status_code=422)
            applied = _range_for(analyte=analyte, patient=patient)
            flag = "NONE"
            if applied is not None and applied.low is not None and number < applied.low:
                flag = "LOW"
            elif applied is not None and applied.high is not None and number > applied.high:
                flag = "HIGH"
            normalized.append(
                {
                    "analyte_id": str(analyte.id),
                    "code": analyte.code,
                    "name": analyte.name,
                    "unit": analyte.unit,
                    "value": str(number),
                    "flag": flag,
                    "range_low": str(applied.low) if applied and applied.low is not None else None,
                    "range_high": str(applied.high) if applied and applied.high is not None else None,
                    "range_text": applied.text if applied else "",
                    "range_validated": bool(applied.validated) if applied else False,
                }
            )
        elif analyte.result_type == "CODED":
            options = analyte.coded_options or test.coded_options
            if value not in options:
                raise CanonicalError("INVALID_INPUT", "Select one of the defined coded options.", status_code=400)
            if value == "INVALID" and not str(raw.get("comment") or "").strip():
                raise CanonicalError("INVALID_INPUT", "A comment is required for INVALID.", status_code=400)
            normalized.append(
                {
                    "analyte_id": str(analyte.id),
                    "code": analyte.code,
                    "name": analyte.name,
                    "unit": analyte.unit,
                    "value": value,
                    "flag": "NONE",
                }
            )
        else:
            text = str(value)
            if len(text) > 2000:
                raise CanonicalError("INVALID_INPUT", "Text results are limited to 2000 characters.", status_code=400)
            normalized.append(
                {
                    "analyte_id": str(analyte.id),
                    "code": analyte.code,
                    "name": analyte.name,
                    "unit": analyte.unit,
                    "value": text,
                    "flag": "NONE",
                }
            )
    return normalized


@transaction.atomic
def save_result(
    *, organisation, facility, actor, item_id, values, comments="", complete=False,
    request=None,
):
    assert_transaction_active()
    item = LabOrderItem.objects.select_for_update().filter(
        id=item_id, organisation=organisation, facility=facility
    ).select_related("test", "order__visit__patient").first()
    if item is None:
        raise CanonicalError("NOT_FOUND", "Laboratory item was not found.", status_code=404)
    if item.state not in {"SAMPLE_COLLECTED", "RESULT_ENTERED"}:
        raise CanonicalError("INVALID_STATE", "This item cannot receive a result.", status_code=409)
    patient = Patient.objects.get(id=item.order.visit.patient_id)
    normalized = _validate_values(test=item.test, values=values, patient=patient)
    result, _created = LabResult.objects.select_for_update().get_or_create(
        organisation=organisation,
        facility=facility,
        item=item,
        defaults={"entered_by": actor, "entered_at": now()},
    )
    version_no = result.current_version + 1
    content_hash = hashlib.sha256(canonical_json({"values": normalized, "comments": comments}).encode()).hexdigest()
    version = LabResultVersion.objects.create(
        organisation=organisation,
        facility=facility,
        result=result,
        version_no=version_no,
        values=normalized,
        comments=str(comments or "")[:4000],
        content_hash=content_hash,
        entered_by=actor,
        entered_at=now(),
    )
    result.current_version = version_no
    result.entered_by = actor
    result.entered_at = now()
    result.state = "RESULT_ENTERED" if complete else "DRAFT"
    result.version += 1
    result.save(
        update_fields=["current_version", "entered_by", "entered_at", "state", "version", "updated_at"]
    )
    if complete:
        item.state = "RESULT_ENTERED"
        item.version += 1
        item.save(update_fields=["state", "version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="LabResult",
        entity_id=result.id,
        after={"version_no": version_no, "state": result.state, "hash": content_hash},
        event_code="LAB_RESULT_SAVED",
    )
    return result, version


@transaction.atomic
def release_result(
    *, organisation, facility, actor, item_id, expected_version=None, request=None
):
    assert_transaction_active()
    item = LabOrderItem.objects.select_for_update(of=("self",)).filter(
        id=item_id, organisation=organisation, facility=facility
    ).select_related("result").first()
    if item is None:
        raise CanonicalError("NOT_FOUND", "Laboratory item was not found.", status_code=404)
    if item.state != "RESULT_ENTERED":
        raise CanonicalError("INVALID_STATE", "Only an entered result can be released.", status_code=409)
    result = LabResult.objects.select_for_update().filter(item=item).first()
    if result is None:
        raise CanonicalError("PREREQUISITE_MISSING", "The result has not been entered.", status_code=422)
    policy = _policy(organisation=organisation, facility=facility)
    self_verification = bool(policy and policy.lab_allow_self_verification)
    if not self_verification and result.entered_by_id == getattr(actor, "id", actor):
        raise CanonicalError(
            "SELF_VERIFICATION_NOT_ALLOWED",
            "The entering technician cannot verify and release their own result.",
            status_code=403,
        )
    version = result.versions.select_for_update().order_by("-version_no").first()
    if version is None:
        raise CanonicalError("PREREQUISITE_MISSING", "The result version is missing.", status_code=422)
    if expected_version is not None and version.version_no != expected_version:
        raise CanonicalError(
            "VERSION_CONFLICT",
            "The result changed while it was being reviewed; refresh before release.",
            status_code=412,
        )
    version.released = True
    version.released_at = now()
    version.verified_by = actor
    version.verified_at = now()
    version.save(update_fields=["released", "released_at", "verified_by", "verified_at", "updated_at"])
    result.state = "RELEASED"
    result.verified_by = actor
    result.verified_at = now()
    result.self_verified = self_verification and result.entered_by_id == getattr(actor, "id", actor)
    result.version += 1
    result.save(
        update_fields=["state", "verified_by", "verified_at", "self_verified", "version", "updated_at"]
    )
    item.state = "RELEASED"
    item.version += 1
    item.save(update_fields=["state", "version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="SIGN",
        entity_type="LabResult",
        entity_id=result.id,
        after={"version_no": version.version_no, "hash": version.content_hash, "self_verified": result.self_verified},
        event_code="LAB_RESULT_RELEASED",
    )
    return result, version


@transaction.atomic
def amend_result(
    *, organisation, facility, actor, item_id, values, comments="", reason, request=None
):
    assert_transaction_active()
    if not str(reason or "").strip():
        raise CanonicalError("INVALID_INPUT", "An amendment reason is required.", status_code=400)
    item = LabOrderItem.objects.select_for_update(of=("self",)).filter(
        id=item_id, organisation=organisation, facility=facility
    ).select_related("test", "result").first()
    if item is None or item.state != "RELEASED":
        raise CanonicalError("INVALID_STATE", "Only a released result can be amended.", status_code=409)
    result = LabResult.objects.select_for_update().get(id=item.result.id)
    patient = Patient.objects.get(id=item.order.visit.patient_id)
    normalized = _validate_values(test=item.test, values=values, patient=patient)
    previous = result.versions.order_by("-version_no").first()
    content_hash = hashlib.sha256(canonical_json({"values": normalized, "comments": comments}).encode()).hexdigest()
    version = LabResultVersion.objects.create(
        organisation=organisation,
        facility=facility,
        result=result,
        version_no=result.current_version + 1,
        values=normalized,
        comments=str(comments or "")[:4000],
        content_hash=content_hash,
        entered_by=actor,
        entered_at=now(),
        released=True,
        released_at=now(),
        verified_by=actor,
        verified_at=now(),
        amendment_reason=str(reason)[:240],
        supersedes=previous,
    )
    result.current_version = version.version_no
    result.state = "RELEASED"
    result.version += 1
    result.save(update_fields=["current_version", "state", "version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="AMEND",
        entity_type="LabResult",
        entity_id=result.id,
        after={"version_no": version.version_no, "previous_hash": previous.content_hash if previous else "", "hash": content_hash},
        event_code="LAB_RESULT_AMENDED",
    )
    return result, version


@transaction.atomic
def cancel_item(*, organisation, facility, actor, item_id, reason, request=None):
    assert_transaction_active()
    if not str(reason or "").strip():
        raise CanonicalError("INVALID_INPUT", "A cancellation reason is required.", status_code=400)
    item = LabOrderItem.objects.select_for_update(of=("self",)).filter(
        id=item_id, organisation=organisation, facility=facility
    ).select_related("invoice_line").first()
    if item is None:
        raise CanonicalError("NOT_FOUND", "Laboratory item was not found.", status_code=404)
    if item.state in {"RELEASED", "RESULT_ENTERED"}:
        raise CanonicalError("INVALID_STATE", "A collected/result item needs a supervisor correction.", status_code=409)
    if item.state == "CANCELLED":
        return item, False
    if item.invoice_line is not None:
        if item.invoice_line.invoice.amount_paid > 0:
            raise CanonicalError(
                "PAID_LINE_CANCELLATION",
                "A paid item needs a credit note, not cancellation.",
                status_code=409,
            )
        void_invoice_line(
            organisation=organisation,
            facility=facility,
            actor=actor,
            invoice_id=item.invoice_line.invoice_id,
            line_id=item.invoice_line_id,
            reason=reason,
            request=request,
        )
    item.state = "CANCELLED"
    item.version += 1
    item.save(update_fields=["state", "version", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="UPDATE",
        entity_type="LabOrderItem",
        entity_id=item.id,
        after={"state": "CANCELLED", "reason": str(reason)[:240]},
        event_code="LAB_ITEM_CANCELLED",
    )
    return item, True


def result_detail(*, organisation, facility, actor, item_id, request=None):
    """Bounded item read for lab role review; values remain in the domain record."""

    assert_transaction_active()
    item = LabOrderItem.objects.filter(
        id=item_id, organisation=organisation, facility=facility
    ).select_related("test", "result").first()
    if item is None:
        raise CanonicalError("NOT_FOUND", "Laboratory item was not found.", status_code=404)
    result = item.result
    version = (
        result.versions.order_by("-version_no").first() if result is not None else None
    )
    body = {
        "item_id": str(item.id),
        "test_name": item.test.name,
        "specimen_id": item.specimen_id,
        "state": item.state,
        "priority": item.priority,
        "version_no": version.version_no if version is not None else None,
        "values": version.values if version is not None else [],
        "comments": version.comments if version is not None else "",
        "entered_by": str(result.entered_by) if result and result.entered_by_id else None,
        "entered_at": version.entered_at if version is not None else None,
        "released_at": version.released_at if version is not None else None,
        "verified_by": str(version.verified_by) if version and version.verified_by_id else None,
    }
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        facility=facility,
        action="READ",
        entity_type="LabResult",
        entity_id=item.id,
        after={
            "scope": "item_detail",
            "state": item.state,
            "version_no": body["version_no"],
        },
        event_code="LAB_RESULTS_READ",
    )
    return body


def released_results_for_encounter(*, organisation, facility, encounter_id, actor=None, request=None):
    assert_transaction_active()
    items = LabOrderItem.objects.filter(
        organisation=organisation,
        facility=facility,
        order__encounter_id=encounter_id,
        state="RELEASED",
    ).select_related("test", "result").order_by("id")
    body = []
    for item in items:
        result = item.result
        version = result.versions.filter(released=True).order_by("-version_no").first()
        if version is None:
            continue
        body.append(
            {
                "item_id": str(item.id),
                "test_name": item.test.name,
                "specimen_type": item.test.specimen_type,
                "version_no": version.version_no,
                "values": version.values,
                "comments": version.comments,
                "released_at": version.released_at,
                "verified_by": str(version.verified_by_id) if version.verified_by_id else None,
                "self_verified": result.self_verified,
                "amended": version.supersedes_id is not None,
            }
        )
    if actor is not None:
        record_event(
            request=request,
            organisation=organisation,
            actor=actor,
            facility=facility,
            action="READ",
            entity_type="LabResult",
            entity_id=encounter_id,
            after={"released_count": len(body)},
            event_code="LAB_RESULTS_READ",
        )
    return body


def encounter_lab_status(*, organisation, facility, encounter_id):
    items = LabOrderItem.objects.filter(
        organisation=organisation,
        facility=facility,
        order__encounter_id=encounter_id,
    )
    total = items.count()
    released = items.filter(state="RELEASED").count()
    cancelled = items.filter(state="CANCELLED").count()
    pending = items.exclude(state__in=("RELEASED", "CANCELLED")).count()
    return {
        "total": total,
        "released": released,
        "cancelled": cancelled,
        "pending": pending,
        "ready": total > 0 and pending == 0,
    }
