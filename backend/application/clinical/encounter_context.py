"""QRY-003: the owner projection for a Visit's clinical context."""

from dataclasses import dataclass

from django.db.models import Prefetch, Q

from clinical.models import (
    ClinicalNote,
    Diagnosis,
    Encounter,
    TriageAssessment,
    VitalsObservation,
)
from clinical.queries import query_allergy_projection
from clinical.concurrency import consultation_note_for_encounter, follow_up_recommendation_for_encounter
from clinical.diagnosis_state import active_diagnosis_snapshot
from laboratory.queries import query_laboratory_projection
from patients.queries import query_patient_projection
from pharmacy.queries import query_dispense_projection, query_prescription_projection
from scheduling.models import FollowUpRecommendation
from scheduling.queries import query_visit_history_projection


@dataclass(frozen=True)
class EncounterContextProjection:
    encounters: tuple
    clinical_values: tuple = ()
    patient_projections: tuple = ()
    allergy_projections: tuple = ()
    visit_history: tuple = ()
    laboratory: tuple = ()
    prescriptions: tuple = ()
    dispenses: tuple = ()

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
    # A composed context is owned by the requested Visit.  The compatibility
    # queue predicate may encounter stale or mismatched legacy links, so keep
    # those rows out of the patient and clinical projections as well.
    queryset = queryset.filter(patient_id=visit.patient_id)
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
        # The composed Visit context has one patient even when there is no
        # clinical Encounter yet.  Load that identity through the patient
        # owner so the authorised empty state still has a stable patient
        # projection without falling back to a serializer-triggered query.
        patient_ids = {visit.patient_id} | {encounter.patient_id for encounter in encounters}
        queue_ids = {encounter.queue_entry_id for encounter in encounters if encounter.queue_entry_id}
        patient_projections = query_patient_projection(
            organisation=organisation,
            patient_ids=patient_ids,
        )
        patient_by_id = {projection.id: projection for projection in patient_projections}
        allergy_by_patient = query_allergy_projection(
            organisation=organisation,
            facility=facility,
            patient_ids=patient_ids,
        )
        visit_history_by_patient = query_visit_history_projection(
            organisation=organisation,
            facility=facility,
            patient_ids=patient_ids,
        )
        laboratory_by_patient = query_laboratory_projection(
            organisation=organisation,
            facility=facility,
            patient_ids=patient_ids,
            visit_id=visit.id,
        )
        prescription_by_patient = query_prescription_projection(
            organisation=organisation,
            facility=facility,
            patient_ids=patient_ids,
            visit_id=visit.id,
        )
        dispense_by_patient = query_dispense_projection(
            organisation=organisation,
            facility=facility,
            patient_ids=patient_ids,
            visit_id=visit.id,
        )
        triage_complaints = dict(
            TriageAssessment.objects.filter(
                organisation=organisation,
                facility=facility,
                queue_entry_id__in=queue_ids,
            ).values_list("queue_entry_id", "chief_complaint")
        )
        for encounter in encounters:
            patient_key = str(encounter.patient_id)
            encounter._patient_projection_for_serialization = patient_by_id.get(patient_key)
            encounter._allergy_snapshot = allergy_by_patient.get(
                patient_key,
                {
                    "patient_id": patient_key,
                    "status": "NOT_RECORDED",
                    "revision": 0,
                    "active_allergies": [],
                    "etag": "",
                },
            )
            encounter._visit_history_for_serialization = visit_history_by_patient.get(patient_key, ())
            encounter._laboratory_for_serialization = laboratory_by_patient.get(patient_key, ())
            encounter._prescriptions_for_serialization = prescription_by_patient.get(patient_key, ())
            encounter._dispenses_for_serialization = dispense_by_patient.get(patient_key, ())
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
        return EncounterContextProjection(
            encounters=projected,
            clinical_values=projected,
            patient_projections=tuple(patient_projections),
            allergy_projections=tuple(
                allergy_by_patient[patient_id]
                for patient_id in sorted(allergy_by_patient)
            ),
            visit_history=tuple(
                item
                for patient_id in sorted(visit_history_by_patient)
                for item in visit_history_by_patient[patient_id]
            ),
            laboratory=tuple(
                item
                for patient_id in sorted(laboratory_by_patient)
                for item in laboratory_by_patient[patient_id]
            ),
            prescriptions=tuple(
                item
                for patient_id in sorted(prescription_by_patient)
                for item in prescription_by_patient[patient_id]
            ),
            dispenses=tuple(
                item
                for patient_id in sorted(dispense_by_patient)
                for item in dispense_by_patient[patient_id]
            ),
        )

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
