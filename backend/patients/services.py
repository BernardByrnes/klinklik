import secrets
import string
from datetime import date

from django.db import transaction
from django.db.models import Q

from audit.services import record_event
from patients.models import Patient, PatientIdentifier, PatientLink


def _patient_number(organisation):
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        candidate = "P-" + "".join(secrets.choice(alphabet) for _ in range(8))
        if not Patient.objects.filter(organisation=organisation, patient_no=candidate).exists():
            return candidate
    raise RuntimeError("Could not allocate a patient number.")


@transaction.atomic
def create_patient(*, organisation, actor, data, request=None):
    identifier = data.pop("identifier", None)
    patient = Patient.objects.create(
        organisation=organisation,
        patient_no=_patient_number(organisation),
        **data,
    )
    if identifier and identifier.get("value"):
        normalized = "".join(str(identifier["value"]).upper().split())
        PatientIdentifier.objects.create(
            organisation=organisation,
            patient=patient,
            identifier_type=identifier.get("identifier_type", "OTHER"),
            value=identifier["value"],
            normalized_value=normalized,
            verified=bool(identifier.get("verified", False)),
            is_primary=True,
        )
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        action="CREATE",
        entity_type="Patient",
        entity_id=patient.id,
        after={"patient_no": patient.patient_no, "status": patient.status},
    )
    return patient


def search_patients(*, organisation, term=""):
    queryset = Patient.objects.filter(organisation=organisation, status="ACTIVE").prefetch_related(
        "identifiers", "contacts"
    )
    term = (term or "").strip()
    if term:
        queryset = queryset.filter(
            Q(patient_no__icontains=term)
            | Q(first_name__icontains=term)
            | Q(middle_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(phone__icontains=term)
            | Q(identifiers__normalized_value__icontains="".join(term.upper().split()))
        )
    return queryset.distinct().order_by("last_name", "first_name")[:100]


@transaction.atomic
def link_patients(*, organisation, actor, source_patient, target_patient, link_type, reason="", request=None):
    if source_patient.id == target_patient.id:
        raise ValueError("A patient cannot be linked to itself.")
    if source_patient.organisation_id != organisation.id or target_patient.organisation_id != organisation.id:
        raise ValueError("Both patients must belong to the active organisation.")
    link, created = PatientLink.objects.get_or_create(
        organisation=organisation,
        source_patient=source_patient,
        target_patient=target_patient,
        link_type=link_type,
        defaults={"created_by": actor, "reason": reason},
    )
    if not created:
        link.reason = reason
        link.status = "OPEN"
        link.save(update_fields=["reason", "status", "updated_at"])
    record_event(
        request=request,
        organisation=organisation,
        actor=actor,
        action="LINK",
        entity_type="PatientLink",
        entity_id=link.id,
        after={"source_patient": str(source_patient.id), "target_patient": str(target_patient.id), "status": link.status},
        reason=reason,
    )
    return link
