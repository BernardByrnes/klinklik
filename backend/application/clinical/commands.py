"""Application command owners for the S-02 clinical queue handoff.

The clinical HTTP views coordinate these functions; queue transition services
remain the only owners of QueueEntry state changes.
"""

from dataclasses import dataclass

from application.contracts import CommandSpec
from application.queue.commands import queue_start_service, queue_transfer
from audit.services import record_fact
from clinical.models import Encounter, TriageAssessment, VitalsObservation
from clinical.services import _reference
from core.errors import CanonicalError
from core.services import assert_transaction_active
from scheduling.models import QueueEntry, Visit


CMD_025_SPEC = CommandSpec(
    operation_id="CMD-025",
    rank1_id="QUE-010",
    capability="triage.start",
    owner_service="application.clinical.commands.triage_start",
    lock_plan=("Visit", "QueueEntry"),
    requires_idempotency=True,
)
CMD_027_SPEC = CommandSpec(
    operation_id="CMD-027",
    rank1_id="QUE-011",
    capability="triage.record",
    owner_service="application.clinical.commands.triage_complete",
    lock_plan=("Visit", "QueueEntry", "TriageAssessment", "VitalsObservation", "NumberSequence"),
    requires_idempotency=True,
)
CMD_030_SPEC = CommandSpec(
    operation_id="CMD-030",
    rank1_id="QUE-012",
    capability="clinical.note.create",
    owner_service="application.clinical.commands.encounter_open",
    lock_plan=("Visit", "QueueEntry", "Encounter"),
    requires_idempotency=True,
)
CMD_039_SPEC = CommandSpec(
    operation_id="CMD-039",
    rank1_id="QUE-013",
    capability="queue.takeover",
    owner_service="application.queue.commands.queue_takeover",
    lock_plan=("QueueEntry", "Encounter"),
    requires_idempotency=True,
)


COMMAND_SPECS = {
    spec.operation_id: spec
    for spec in (CMD_025_SPEC, CMD_027_SPEC, CMD_030_SPEC, CMD_039_SPEC)
}


def _canonical_queue_writer_available(organisation):
    """Return false only for the pre-MIG-001 compatibility era.

    After MIG-001 cutover, a disabled MIG-002 target is a real outage fence;
    it must not silently fall through to the old queue writer.
    """

    from core.migration_reconciliation import (
        legacy_writes_enabled,
        target_writes_enabled_mig002,
    )

    if target_writes_enabled_mig002(organisation):
        return True
    if legacy_writes_enabled(organisation):
        return False
    raise CanonicalError(
        "MIGRATION_TARGET_DISABLED",
        "Canonical QueueEntry writes are temporarily unavailable while migration compatibility is restored.",
        status_code=503,
        retryable=True,
    )


@dataclass(frozen=True)
class EncounterOpenOutcome:
    encounter: Encounter
    queue: QueueEntry


@dataclass(frozen=True)
class TriageCompleteOutcome:
    assessment: TriageAssessment
    source: QueueEntry
    destination: QueueEntry


def _queue_identity(*, organisation, facility, queue_entry_id):
    return QueueEntry.objects.filter(
        id=queue_entry_id,
        organisation=organisation,
        facility=facility,
    ).select_related("patient").first()


def _require_queue_type(*, organisation, facility, queue_entry_id, allowed, detail):
    entry = _queue_identity(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id,
    )
    if entry is None:
        raise CanonicalError("NOT_FOUND", "The queue entry was not found in this facility.", status_code=404)
    if entry.queue_type.upper() not in {value.upper() for value in allowed}:
        raise CanonicalError("INVALID_STATE", detail, status_code=409)
    if entry.visit_id is None:
        raise CanonicalError("PREREQUISITE_MISSING", "The canonical queue entry requires a linked Visit.", status_code=422)
    return entry


def _ensure_encounter(*, organisation, facility, actor, entry, visit):
    encounter = Encounter.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        queue_entry=entry,
    ).first()
    if encounter is not None:
        if encounter.status in {"SIGNED", "CLOSED", "CANCELLED"}:
            raise CanonicalError(
                "INVALID_STATE",
                "The linked Encounter is already terminal.",
                status_code=409,
            )
        return encounter, False
    encounter = Encounter.objects.create(
        organisation=organisation,
        facility=facility,
        patient=entry.patient,
        visit=visit,
        queue_entry=entry,
        encounter_no=_reference("ENC"),
        clinician=actor,
    )
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="ENCOUNTER_OPENED",
        action="CREATE",
        entity_type="Encounter",
        entity_id=encounter.id,
        source_ids={"encounter_id": encounter.id, "queue_entry_id": entry.id, "visit_id": visit.id if visit else None},
        after={"status": encounter.status},
    )
    return encounter, True


def encounter_open(*, organisation, facility, actor, queue_entry_id, expected_version=None):
    """CMD-030: start service and open/reuse the same Visit Encounter."""

    assert_transaction_active()
    if not _canonical_queue_writer_available(organisation):
        from clinical.services import start_encounter

        encounter = start_encounter(
            organisation=organisation,
            facility=facility,
            actor=actor,
            queue_entry_id=queue_entry_id,
        )
        queue = QueueEntry.objects.get(id=queue_entry_id, organisation=organisation, facility=facility)
        return EncounterOpenOutcome(encounter=encounter, queue=queue)
    _require_queue_type(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id,
        allowed={"CONSULTATION", "CLINICIAN"},
        detail="Only a consultation queue entry can open an Encounter.",
    )
    holder = {}

    def open_stage(*, entry, visit):
        encounter, _ = _ensure_encounter(
            organisation=organisation,
            facility=facility,
            actor=actor,
            entry=entry,
            visit=visit,
        )
        # start_service owns the version increment; this stage marker is part
        # of that same persisted transition and selects IN_CONSULTATION as the
        # legacy shadow without a second writer.
        entry.current_stage = "CONSULTATION"
        entry.save(update_fields=["current_stage", "updated_at"])
        holder["encounter"] = encounter

    queue = queue_start_service(
        organisation=organisation,
        facility=facility,
        actor=actor,
        queue_entry_id=queue_entry_id,
        expected_version=expected_version,
        stage_callback=open_stage,
    )
    encounter = holder.get("encounter")
    if encounter is None:
        if queue.state != "IN_SERVICE":
            raise CanonicalError(
                "PREREQUISITE_MISSING",
                "The Encounter workspace could not be opened; the queue remains called.",
                status_code=422,
            )
        encounter, _ = _ensure_encounter(
            organisation=organisation,
            facility=facility,
            actor=actor,
            entry=queue,
            visit=Visit.objects.select_for_update().filter(
                id=queue.visit_id,
                organisation=organisation,
                facility=facility,
            ).first() if queue.visit_id else None,
        )
        if queue.current_stage != "CONSULTATION" or queue.status != "IN_CONSULTATION":
            queue.current_stage = "CONSULTATION"
            queue.status = "IN_CONSULTATION"
            queue.version += 1
            queue.save(update_fields=["current_stage", "status", "version", "updated_at"])
    return EncounterOpenOutcome(encounter=encounter, queue=queue)


def triage_start(*, organisation, facility, actor, queue_entry_id, expected_version=None):
    """CMD-025 adapter; normal triage start is the queue service start."""

    assert_transaction_active()
    _require_queue_type(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id,
        allowed={"TRIAGE"},
        detail="Only a TRIAGE queue entry can start triage.",
    )
    def mark_triage_stage(*, entry, visit):
        entry.current_stage = "TRIAGE"
        entry.save(update_fields=["current_stage", "updated_at"])

    return queue_start_service(
        organisation=organisation,
        facility=facility,
        actor=actor,
        queue_entry_id=queue_entry_id,
        expected_version=expected_version,
        stage_callback=mark_triage_stage,
    )


def triage_complete(*, organisation, facility, actor, queue_entry_id, data, expected_version=None):
    """CMD-027: complete triage, then create/reuse one consultation stage."""

    assert_transaction_active()
    if not _canonical_queue_writer_available(organisation):
        from clinical.services import record_triage

        assessment = record_triage(
            organisation=organisation,
            facility=facility,
            actor=actor,
            queue_entry_id=queue_entry_id,
            data=data,
        )
        source = QueueEntry.objects.get(id=queue_entry_id, organisation=organisation, facility=facility)
        return TriageCompleteOutcome(assessment=assessment, source=source, destination=source)
    _require_queue_type(
        organisation=organisation,
        facility=facility,
        queue_entry_id=queue_entry_id,
        allowed={"TRIAGE"},
        detail="Only a TRIAGE queue entry can be completed by CMD-027.",
    )
    def mark_triage_stage(*, entry, visit):
        entry.current_stage = "TRIAGE"
        entry.save(update_fields=["current_stage", "updated_at"])

    queue = queue_start_service(
        organisation=organisation,
        facility=facility,
        actor=actor,
        queue_entry_id=queue_entry_id,
        expected_version=expected_version,
        stage_callback=mark_triage_stage,
    )
    visit = Visit.objects.select_for_update().filter(
        id=queue.visit_id,
        organisation=organisation,
        facility=facility,
    ).first()
    if visit is None:
        raise CanonicalError("PREREQUISITE_MISSING", "Triage completion requires a linked Visit.", status_code=422)
    assessment = TriageAssessment.objects.select_for_update().filter(
        organisation=organisation,
        facility=facility,
        queue_entry=queue,
    ).first()
    created_assessment = False
    if assessment is None:
        assessment = TriageAssessment.objects.create(
            organisation=organisation,
            facility=facility,
            queue_entry=queue,
            patient=queue.patient,
            acuity=data.get("acuity", "ROUTINE"),
            chief_complaint=data.get("chief_complaint", ""),
            observations=data.get("observations", {}),
            assessed_by=actor,
        )
        created_assessment = True
    vitals = data.get("vitals") or {}
    if created_assessment and vitals:
        VitalsObservation.objects.create(
            organisation=organisation,
            facility=facility,
            patient=queue.patient,
            measured_by=actor,
            **{
                key: value for key, value in vitals.items()
                if key in {
                    "systolic", "diastolic", "pulse", "temperature_c", "respiratory_rate",
                    "oxygen_saturation", "weight_kg", "height_cm",
                }
            },
        )
    source, destination = queue_transfer(
        organisation=organisation,
        facility=facility,
        actor=actor,
        source_queue_entry_id=queue.id,
        target_department_id=queue.department_id,
        target_queue_type="CONSULTATION",
        handoff_note="",
        reason="TRIAGE_COMPLETED",
        expected_version=queue.version,
    )
    # Preserve the legacy source evidence for MIG-002 classification while
    # canonical state remains COMPLETED and the consultation row is WAITING.
    source.status = "TRIAGED"
    source.current_stage = "CONSULTATION"
    source.save(update_fields=["status", "current_stage", "updated_at"])
    record_fact(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code="TRIAGE_COMPLETED",
        action="UPDATE",
        entity_type="QueueEntry",
        entity_id=source.id,
        source_ids={
            "queue_entry_id": source.id,
            "visit_id": visit.id,
            "consultation_queue_entry_id": destination.id,
        },
        after={"source_state": source.state, "source_version": source.version, "destination_state": destination.state},
    )
    return TriageCompleteOutcome(assessment=assessment, source=source, destination=destination)
