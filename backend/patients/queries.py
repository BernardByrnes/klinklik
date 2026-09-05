"""Read-only patient projections owned by the patients domain."""

from dataclasses import dataclass

from core.services import assert_transaction_active
from patients.models import Patient


@dataclass(frozen=True)
class PatientContextProjection:
    id: str
    patient_no: str
    display_name: str
    sex: str
    date_of_birth: object
    version: int


def query_patient_projection(*, organisation, patient_ids):
    """Return only the identity fields authorised for a composed context.

    Contact, address, identifiers, and free-text fields are intentionally not
    part of QRY-003's patient projection.
    """

    assert_transaction_active()
    identifiers = sorted({str(identifier) for identifier in patient_ids})
    if not identifiers:
        return ()
    rows = Patient.objects.filter(
        organisation=organisation,
        id__in=identifiers,
    ).only(
        "id",
        "patient_no",
        "first_name",
        "middle_name",
        "last_name",
        "sex",
        "date_of_birth",
        "version",
    ).order_by("id")
    return tuple(
        PatientContextProjection(
            id=str(patient.id),
            patient_no=patient.patient_no,
            display_name=patient.display_name,
            sex=patient.sex,
            date_of_birth=patient.date_of_birth,
            version=patient.version,
        )
        for patient in rows
    )


# Explicit alias for application coordinators and contract-oriented tests.
patient_context_projection = query_patient_projection
