import secrets
import string

from django.db import transaction
from django.db.models import Q

from audit.services import record_event
from core.services import allocate_sequence
from patients.models import Patient, PatientContact, PatientIdentifier, PatientLink


def _patient_number(organisation):
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(20):
        candidate = "P-" + "".join(secrets.choice(alphabet) for _ in range(8))
        if not Patient.objects.filter(organisation=organisation, patient_no=candidate).exists():
            return candidate
    raise RuntimeError("Could not allocate a patient number.")


def _allocated_patient_number(organisation):
    return f"P-{allocate_sequence(organisation=organisation, sequence_type='PATIENT', period_key='GLOBAL'):06d}"


def find_duplicate_candidates(*, organisation, data, for_update=False):
    """Return only the frozen exact duplicate match used by REC-002."""

    date_of_birth = data.get("date_of_birth")
    if not date_of_birth:
        return Patient.objects.none()
    queryset = Patient.objects.filter(
        organisation=organisation,
        last_name__iexact=str(data.get("last_name", "")).strip(),
        sex=data.get("sex"),
        date_of_birth=date_of_birth,
        identity_status__in=["ACTIVE", "PROVISIONAL"],
    ).order_by("last_name", "first_name", "id")
    return queryset.select_for_update() if for_update else queryset


def create_registered_patient(*, organisation, actor, data):
    """Create the S-01 patient record inside the caller's tenant transaction."""

    from core.services import assert_transaction_active

    assert_transaction_active()
    values = dict(data)
    identifier = values.pop("identifier", None)
    next_of_kin = values.pop("next_of_kin", None) or {}
    patient = Patient.objects.create(
        organisation=organisation,
        patient_no=_allocated_patient_number(organisation),
        **values,
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
    kin_name = next_of_kin.get("name") or patient.next_of_kin_name or ""
    kin_phone = next_of_kin.get("phone") or patient.next_of_kin_phone or ""
    if kin_name or kin_phone:
        PatientContact.objects.create(
            organisation=organisation,
            patient=patient,
            relationship="NEXT_OF_KIN",
            name=kin_name,
            phone=kin_phone,
            is_primary=True,
        )
    return patient


@transaction.atomic
def create_patient(*, organisation, actor, data, request=None):
    patient = create_registered_patient(organisation=organisation, actor=actor, data=dict(data))
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
    queryset = Patient.objects.filter(
        organisation=organisation,
        status="ACTIVE",
        identity_status__in=["ACTIVE", "PROVISIONAL"],
    ).prefetch_related(
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
