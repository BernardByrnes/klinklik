"""Read-only scheduling owner projections."""

from core.services import assert_transaction_active
from scheduling.models import Visit


def query_visit_history_projection(*, organisation, facility, patient_ids):
    """Return the current facility's retained Visit history by patient."""

    assert_transaction_active()
    patient_ids = tuple(sorted({str(identifier) for identifier in patient_ids}))
    if not patient_ids:
        return {}
    history = {}
    visits = Visit.objects.filter(
        organisation=organisation,
        facility=facility,
        patient_id__in=patient_ids,
    ).only(
        "id",
        "patient_id",
        "local_service_date",
        "visit_type",
        "state",
        "opened_at",
        "closed_at",
        "version",
    ).order_by("patient_id", "-local_service_date", "-opened_at", "-id")
    for visit in visits:
        history.setdefault(str(visit.patient_id), []).append(
            {
                "id": str(visit.id),
                "local_service_date": visit.local_service_date,
                "visit_type": visit.visit_type,
                "state": visit.state,
                "opened_at": visit.opened_at,
                "closed_at": visit.closed_at,
                "version": visit.version,
            }
        )
    return {patient_id: tuple(history.get(patient_id, ())) for patient_id in patient_ids}


visit_history_projection = query_visit_history_projection
