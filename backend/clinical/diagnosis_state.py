from clinical.models import Diagnosis


def _diagnoses_for_encounter(encounter):
    prefetched = getattr(encounter, "_prefetched_objects_cache", {}).get("diagnoses")
    if prefetched is not None:
        return sorted(
            [diagnosis for diagnosis in prefetched if diagnosis.status == "ACTIVE"],
            key=lambda diagnosis: (diagnosis.created_at, str(diagnosis.id)),
        )
    return list(
        Diagnosis.objects.filter(
            organisation=encounter.organisation_id,
            facility=encounter.facility_id,
            encounter_id=encounter.id,
            status="ACTIVE",
        ).order_by("created_at", "id")
    )


def active_diagnosis_snapshot(encounter):
    return [
        {
            "id": str(diagnosis.id),
            "encounter": str(diagnosis.encounter_id),
            "diagnosis_type": diagnosis.diagnosis_type,
            "code": diagnosis.code,
            "label": diagnosis.label,
            "coded": diagnosis.coded,
            "certainty_note": diagnosis.certainty_note,
            "is_primary": diagnosis.is_primary,
            "no_diagnosis_reason": diagnosis.no_diagnosis_reason,
            "status": diagnosis.status,
            "recorded_by": str(diagnosis.recorded_by_id),
            "created_at": diagnosis.created_at.isoformat(),
            "updated_at": diagnosis.updated_at.isoformat(),
        }
        for diagnosis in _diagnoses_for_encounter(encounter)
    ]


def diagnosis_revision_snapshot(encounter):
    prefetched = getattr(encounter, "_prefetched_objects_cache", {}).get("diagnoses")
    if prefetched is not None:
        diagnoses = sorted(prefetched, key=lambda diagnosis: str(diagnosis.id))
    else:
        diagnoses = Diagnosis.objects.filter(
            organisation=encounter.organisation_id,
            facility=encounter.facility_id,
            encounter_id=encounter.id,
        ).order_by("id")
    return [
        {
            "id": str(diagnosis.id),
            "diagnosis_type": diagnosis.diagnosis_type,
            "status": diagnosis.status,
            "is_primary": diagnosis.is_primary,
            "updated_at": diagnosis.updated_at.isoformat(),
        }
        for diagnosis in diagnoses
    ]
