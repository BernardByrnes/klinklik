"""QRY-003: the owner projection for a Visit's clinical context."""

from dataclasses import dataclass

from django.db.models import Q

from clinical.models import Encounter


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
        encounters = tuple(queryset.select_related("patient").order_by("started_at", "id"))
        return EncounterContextProjection(encounters=encounters, clinical_values=encounters)

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
