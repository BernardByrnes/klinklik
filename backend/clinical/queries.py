"""Read-only clinical owner projections used by QRY-003."""

from clinical.allergies import active_allergy_payload, patient_allergy_state_etag
from clinical.models import Allergy, PatientAllergyState
from core.services import assert_transaction_active


def query_allergy_projection(*, organisation, facility, patient_ids):
    """Return the facility-local allergy state for each requested patient."""

    assert_transaction_active()
    patient_ids = tuple(sorted({str(identifier) for identifier in patient_ids}))
    if not patient_ids:
        return {}
    states = {
        str(state.patient_id): state
        for state in PatientAllergyState.objects.filter(
            organisation=organisation,
            facility=facility,
            patient_id__in=patient_ids,
        )
    }
    active = {}
    for allergy in Allergy.objects.filter(
        organisation=organisation,
        facility=facility,
        patient_id__in=patient_ids,
        status="ACTIVE",
    ).order_by("recorded_at", "created_at", "id"):
        active.setdefault(str(allergy.patient_id), []).append(allergy)
    return {
        patient_id: {
            "patient_id": patient_id,
            "status": states[patient_id].status if patient_id in states else "NOT_RECORDED",
            "revision": states[patient_id].revision if patient_id in states else 0,
            "active_allergies": [active_allergy_payload(item) for item in active.get(patient_id, ())],
            "etag": patient_allergy_state_etag(
                organisation_id=organisation.id,
                facility_id=facility.id,
                patient_id=patient_id,
                state=states.get(patient_id),
                active=active.get(patient_id, ()),
            ),
        }
        for patient_id in patient_ids
    }


allergy_context_projection = query_allergy_projection
