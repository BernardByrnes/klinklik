"""QRY-003: the owner projection for a Visit's clinical context."""

from dataclasses import dataclass

from django.db.models import Prefetch, Q

from clinical.allergies import active_allergy_payload, patient_allergy_state_etag
from clinical.models import (
    Allergy,
    ClinicalNote,
    Diagnosis,
    Encounter,
    PatientAllergyState,
    TriageAssessment,
    VitalsObservation,
)
from clinical.concurrency import consultation_note_for_encounter, follow_up_recommendation_for_encounter
from clinical.diagnosis_state import active_diagnosis_snapshot
from scheduling.models import FollowUpRecommendation


@dataclass(frozen=True)
class EncounterContextProjection:
    encounters: tuple
    clinical_values: tuple = ()

    @property
    def has_clinical_values(self):
        return bool(self.clinical_values)


def query_encounter_context(*, organisation, facility, visit, queue_entries=(), include_clinical=False):
    """Return owner-scoped Encounter objects without writing or auditing.

    The queue-entry predicate is a compatibility read for the MIG-001 expand
    window. Canonical target writers always populate Encounter.visit.
    """

    queue_ids = [entry.id for entry in queue_entries]
    queryset = Encounter.objects.select_related("clinician").filter(
        organisation=organisation,
        facility=facility,
    )
    if queue_ids:
        queryset = queryset.filter(Q(visit=visit) | Q(queue_entry_id__in=queue_ids))
    else:
        queryset = queryset.filter(visit=visit)
    if include_clinical:
        encounters = list(
            queryset
            .select_related("patient", "facility", "visit", "queue_entry", "clinician")
            .prefetch_related(
                Prefetch(
                    "notes",
                    queryset=ClinicalNote.objects.filter(
                        organisation=organisation,
                        facility=facility,
                    ).select_related("author", "signed_by").order_by("id"),
                ),
                Prefetch(
                    "diagnoses",
                    queryset=Diagnosis.objects.filter(
                        organisation=organisation,
                        facility=facility,
                    ).order_by("created_at", "id"),
                ),
                Prefetch(
                    "follow_ups",
                    queryset=FollowUpRecommendation.objects.filter(
                        organisation=organisation,
                        facility=facility,
                    ).select_related("patient", "encounter", "created_by").order_by("-created_at", "-id"),
                ),
                Prefetch(
                    "vitals",
                    queryset=VitalsObservation.objects.filter(
                        organisation=organisation,
                        facility=facility,
                    ).order_by("-measured_at", "-id"),
                ),
            )
            .order_by("started_at", "id")
        )
        patient_ids = {encounter.patient_id for encounter in encounters}
        queue_ids = {encounter.queue_entry_id for encounter in encounters if encounter.queue_entry_id}
        states = {
            state.patient_id: state
            for state in PatientAllergyState.objects.filter(
                organisation=organisation,
                facility=facility,
                patient_id__in=patient_ids,
            )
        }
        active_allergies = {}
        for allergy in Allergy.objects.filter(
            organisation=organisation,
            facility=facility,
            patient_id__in=patient_ids,
            status="ACTIVE",
        ).order_by("recorded_at", "created_at", "id"):
            active_allergies.setdefault(allergy.patient_id, []).append(allergy)
        triage_complaints = dict(
            TriageAssessment.objects.filter(
                organisation=organisation,
                facility=facility,
                queue_entry_id__in=queue_ids,
            ).values_list("queue_entry_id", "chief_complaint")
        )
        for encounter in encounters:
            state = states.get(encounter.patient_id)
            active = active_allergies.get(encounter.patient_id, [])
            encounter._allergy_snapshot = {
                "status": state.status if state is not None else "NOT_RECORDED",
                "revision": state.revision if state is not None else 0,
                "active_allergies": [active_allergy_payload(item) for item in active],
                "etag": patient_allergy_state_etag(
                    organisation_id=organisation.id,
                    facility_id=facility.id,
                    patient_id=encounter.patient_id,
                    state=state,
                    active=active,
                ),
            }
            encounter._triage_complaint_for_serialization = (
                triage_complaints.get(encounter.queue_entry_id)
                if encounter.queue_entry_id
                else None
            )
            # Materialize every owner projection before handing the objects to
            # the serializer. QRY-003 serialization is therefore a pure
            # formatting step and cannot issue a lazy PHI query.
            encounter._diagnosis_snapshot_for_serialization = active_diagnosis_snapshot(encounter)
            encounter._consultation_note_for_serialization = consultation_note_for_encounter(encounter)
            encounter._follow_up_for_serialization = follow_up_recommendation_for_encounter(encounter)
        projected = tuple(encounters)
        return EncounterContextProjection(encounters=projected, clinical_values=projected)

    # The administrative branch still returns the locked completion/staff
    # summary, but deliberately does not select clinical content fields.
    summaries = tuple(
        queryset.only(
            "id",
            "organisation_id",
            "facility_id",
            "clinician_id",
            "clinician__first_name",
            "clinician__last_name",
            "status",
            "started_at",
            "signed_at",
            "closed_at",
        ).order_by("started_at", "id")
    )
    return EncounterContextProjection(encounters=summaries)
