"""MIG-001 operational phases.

The module deliberately stores identifiers, classifier codes, and hashes only.
It never copies patient names, dates of birth, notes, or other PHI into
reconciliation evidence.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID, uuid4

from django.db import IntegrityError, models, transaction
from django.utils.timezone import now

from core.models import MigrationCutover, MigrationReconciliation
from core.services import assert_transaction_active
from clinical.models import Encounter
from billing.models import Invoice
from scheduling.models import QueueEntry, Visit


MIGRATION_ID = "MIG-001"
LEGACY_QUEUE_TABLE = "scheduling_queueentry"
BACKFILLABLE_VISIT_TYPES = frozenset(
    {"OUTPATIENT_NEW", "OUTPATIENT_REVIEW", "ANC", "LAB_ONLY", "PHARMACY_ONLY", "FOLLOW_UP_RESULTS"}
)
TERMINAL_QUEUE_STATES = frozenset({"COMPLETED", "CANCELLED"})


@dataclass(frozen=True)
class MigrationSummary:
    migration_id: str
    phase: str
    inspected: int = 0
    backfilled: int = 0
    exceptions: int = 0
    unresolved: int = 0
    queue_without_visit: int = 0
    linked_visit_count: int = 0
    parity_passes: int = 0

    def as_dict(self):
        return {
            "migration_id": self.migration_id,
            "phase": self.phase,
            "inspected": self.inspected,
            "backfilled": self.backfilled,
            "exceptions": self.exceptions,
            "unresolved": self.unresolved,
            "queue_without_visit": self.queue_without_visit,
            "linked_visit_count": self.linked_visit_count,
            "parity_passes": self.parity_passes,
        }


def _stable_hash(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _source_evidence(queue, encounters):
    return {
        "legacy_table": LEGACY_QUEUE_TABLE,
        "legacy_pk": str(queue.id),
        "organisation_id": str(queue.organisation_id),
        "facility_id": str(queue.facility_id),
        "patient_id": str(queue.patient_id),
        "queue_date": queue.queue_date.isoformat(),
        "arrival_at": queue.arrival_at.isoformat() if queue.arrival_at else None,
        "encounter_ids": sorted(str(encounter.id) for encounter in encounters),
    }


def _record_exception(*, queue=None, legacy_table, legacy_pk, organisation_id, facility_id, codes, target_refs=None, source_hash="", target_hash="", run_id=None):
    evidence, _ = MigrationReconciliation.objects.update_or_create(
        organisation_id=organisation_id,
        migration_id=MIGRATION_ID,
        legacy_table=legacy_table,
        legacy_pk=str(legacy_pk),
        defaults={
            "facility_id": facility_id,
            "evidence_codes": sorted(set(codes)),
            "proposed_target_refs": target_refs,
            "source_hash": source_hash,
            "target_hash": target_hash,
            "backfill_run_id": run_id,
        },
    )
    return evidence


def _classify_queue(queue):
    encounters = list(
        Encounter.objects.filter(
            queue_entry_id=queue.id,
        ).order_by("id")
    )
    codes = []
    facility_org = getattr(queue.facility, "organisation_id", None)
    patient_org = getattr(queue.patient, "organisation_id", None)
    department_org = getattr(queue.department, "organisation_id", None)
    department_facility = getattr(queue.department, "facility_id", None)
    if facility_org != queue.organisation_id:
        codes.append("FACILITY_ORGANISATION_MISMATCH")
    if patient_org != queue.organisation_id:
        codes.append("PATIENT_ORGANISATION_MISMATCH")
    if department_org != queue.organisation_id or department_facility != queue.facility_id:
        codes.append("DEPARTMENT_SCOPE_MISMATCH")

    same_day = QueueEntry.objects.filter(
        organisation_id=queue.organisation_id,
        facility_id=queue.facility_id,
        patient_id=queue.patient_id,
        queue_date=queue.queue_date,
        visit_id__isnull=True,
    ).exclude(id=queue.id)
    if same_day.exists():
        codes.append("AMBIGUOUS_EPISODE")

    visit_type = "OUTPATIENT_NEW" if queue.visit_type == "WALK_IN" else queue.visit_type
    if visit_type not in BACKFILLABLE_VISIT_TYPES:
        codes.append("UNSUPPORTED_VISIT_TYPE")
    opened_by_id = queue.claimed_by_id or (encounters[0].clinician_id if len(encounters) == 1 else None)
    if opened_by_id is None:
        codes.append("MISSING_OPENED_BY")
    if len(encounters) > 1:
        codes.append("MULTIPLE_ENCOUNTER_LINEAGE")
    for encounter in encounters:
        if (
            encounter.organisation_id != queue.organisation_id
            or encounter.facility_id != queue.facility_id
            or encounter.patient_id != queue.patient_id
        ):
            codes.append("LINK_SCOPE_MISMATCH")
    return codes, encounters, opened_by_id, visit_type


def _link_invoice(*, visit, encounter, run_id):
    invoices = list(
        Invoice.objects.select_for_update()
        .filter(organisation_id=encounter.organisation_id, encounter_id=encounter.id)
        .order_by("id")
    )
    if len(invoices) > 1:
        _record_exception(
            legacy_table="billing_invoice_lineage",
            legacy_pk=encounter.id,
            organisation_id=encounter.organisation_id,
            facility_id=encounter.facility_id,
            codes=["INVOICE_LINEAGE_AMBIGUOUS"],
            target_refs={"visit_id": str(visit.id), "encounter_id": str(encounter.id)},
            run_id=run_id,
        )
        return False
    if not invoices:
        return True
    invoice = invoices[0]
    if invoice.visit_id is not None:
        if invoice.visit_id == visit.id:
            return True
        _record_exception(
            legacy_table="billing_invoice",
            legacy_pk=invoice.id,
            organisation_id=invoice.organisation_id,
            facility_id=invoice.facility_id,
            codes=["INVOICE_ALREADY_LINKED", "LINK_SCOPE_MISMATCH"],
            target_refs={"visit_id": str(visit.id), "encounter_id": str(encounter.id)},
            run_id=run_id,
        )
        return False
    if (
        invoice.organisation_id != visit.organisation_id
        or invoice.facility_id != visit.facility_id
        or invoice.patient_id != visit.patient_id
    ):
        _record_exception(
            legacy_table="billing_invoice",
            legacy_pk=invoice.id,
            organisation_id=invoice.organisation_id,
            facility_id=invoice.facility_id,
            codes=["LINK_SCOPE_MISMATCH"],
            target_refs={"visit_id": str(visit.id), "encounter_id": str(encounter.id)},
            run_id=run_id,
        )
        return False
    invoice.visit = visit
    invoice.save(update_fields=["visit", "updated_at"])
    return True


def _backfill_one(queue, *, run_id):
    if queue.visit_id is not None:
        return False, None
    codes, encounters, opened_by_id, visit_type = _classify_queue(queue)
    source = _source_evidence(queue, encounters)
    source_hash = _stable_hash(source)
    if codes:
        _record_exception(
            queue=queue,
            legacy_table=LEGACY_QUEUE_TABLE,
            legacy_pk=queue.id,
            organisation_id=queue.organisation_id,
            facility_id=queue.facility_id,
            codes=codes,
            target_refs={"queue_id": str(queue.id)},
            source_hash=source_hash,
            run_id=run_id,
        )
        return False, None

    source_key = f"queue:{queue.id}"
    try:
        with transaction.atomic():
            visit = Visit.objects.select_for_update().filter(
                organisation_id=queue.organisation_id,
                legacy_source_key=source_key,
            ).first()
            if visit is not None and (
                visit.facility_id != queue.facility_id
                or visit.patient_id != queue.patient_id
                or visit.local_service_date != queue.queue_date
            ):
                _record_exception(
                    queue=queue,
                    legacy_table=LEGACY_QUEUE_TABLE,
                    legacy_pk=queue.id,
                    organisation_id=queue.organisation_id,
                    facility_id=queue.facility_id,
                    codes=["TARGET_SCOPE_MISMATCH"],
                    target_refs={"queue_id": str(queue.id), "visit_id": str(visit.id)},
                    source_hash=source_hash,
                    run_id=run_id,
                )
                return False, None
            if visit is None:
                existing_active = Visit.objects.filter(
                    organisation_id=queue.organisation_id,
                    facility_id=queue.facility_id,
                    patient_id=queue.patient_id,
                    local_service_date=queue.queue_date,
                    state__in=Visit.ACTIVE_STATES,
                ).order_by("id").first()
                if existing_active is not None:
                    _record_exception(
                        queue=queue,
                        legacy_table=LEGACY_QUEUE_TABLE,
                        legacy_pk=queue.id,
                        organisation_id=queue.organisation_id,
                        facility_id=queue.facility_id,
                        codes=["EXISTING_ACTIVE_VISIT"],
                        target_refs={"queue_id": str(queue.id), "visit_id": str(existing_active.id)},
                        source_hash=source_hash,
                        run_id=run_id,
                    )
                    return False, None
                visit = Visit.objects.create(
                    organisation_id=queue.organisation_id,
                    facility_id=queue.facility_id,
                    patient_id=queue.patient_id,
                    local_service_date=queue.queue_date,
                    visit_type=visit_type,
                    state="OPEN",
                    opened_at=queue.arrival_at or queue.queue_time or queue.created_at,
                    opened_by_id=opened_by_id,
                    legacy_source_key=source_key,
                )
            queue.visit = visit
            queue.save(update_fields=["visit", "updated_at"])
            if encounters:
                encounter = encounters[0]
                if encounter.visit_id is None:
                    encounter.visit = visit
                    encounter.save(update_fields=["visit", "updated_at"])
                _link_invoice(visit=visit, encounter=encounter, run_id=run_id)
            return True, visit
    except IntegrityError:
        # A concurrent runner can only win with the same deterministic source
        # key. Re-read it; a different target is a reconciliation exception.
        visit = Visit.objects.filter(organisation_id=queue.organisation_id, legacy_source_key=source_key).first()
        if visit is not None:
            queue.visit = visit
            queue.save(update_fields=["visit", "updated_at"])
            return True, visit
        raise


def inventory_mig001(*, organisation, facility_id=None):
    """Classify every legacy source row and persist only exception evidence."""

    assert_transaction_active()
    queues = QueueEntry.objects.filter(organisation=organisation, visit_id__isnull=True).order_by("id")
    if facility_id:
        queues = queues.filter(facility_id=facility_id)
    inspected = exceptions = 0
    for queue in queues.select_related("facility", "patient", "department").iterator():
        inspected += 1
        codes, encounters, _, _ = _classify_queue(queue)
        if codes:
            exceptions += 1
            _record_exception(
                queue=queue,
                legacy_table=LEGACY_QUEUE_TABLE,
                legacy_pk=queue.id,
                organisation_id=queue.organisation_id,
                facility_id=queue.facility_id,
                codes=codes,
                target_refs={"queue_id": str(queue.id)},
                source_hash=_stable_hash(_source_evidence(queue, encounters)),
            )
    for encounter in Encounter.objects.filter(
        organisation=organisation, queue_entry_id__isnull=True, visit_id__isnull=True
    ).order_by("id"):
        exceptions += 1
        _record_exception(
            legacy_table="clinical_encounter",
            legacy_pk=encounter.id,
            organisation_id=encounter.organisation_id,
            facility_id=encounter.facility_id,
            codes=["QUEUELESS_ENCOUNTER"],
            source_hash=_stable_hash({"encounter_id": str(encounter.id), "facility_id": str(encounter.facility_id), "patient_id": str(encounter.patient_id)}),
        )
    for invoice in Invoice.objects.filter(
        organisation=organisation, encounter_id__isnull=True, visit_id__isnull=True
    ).order_by("id"):
        exceptions += 1
        _record_exception(
            legacy_table="billing_invoice",
            legacy_pk=invoice.id,
            organisation_id=invoice.organisation_id,
            facility_id=invoice.facility_id,
            codes=["QUEUELESS_INVOICE_NO_LINEAGE"],
            source_hash=_stable_hash({"invoice_id": str(invoice.id), "facility_id": str(invoice.facility_id), "patient_id": str(invoice.patient_id)}),
        )
    return MigrationSummary(MIGRATION_ID, "INVENTORY", inspected=inspected, exceptions=exceptions)


def backfill_mig001(*, organisation, facility_id=None, batch_size=500, after_id=None, run_id=None):
    """Restartable stable-key backfill. Call again with the last id checkpoint."""

    assert_transaction_active()
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    run_id = run_id or uuid4()
    queues = QueueEntry.objects.filter(organisation=organisation, visit_id__isnull=True).order_by("id")
    if facility_id:
        queues = queues.filter(facility_id=facility_id)
    if after_id:
        queues = queues.filter(id__gt=after_id)
    queues = queues.select_related("facility", "patient", "department")[:batch_size]
    inspected = backfilled = exceptions = 0
    for queue in queues:
        inspected += 1
        completed, _ = _backfill_one(queue, run_id=run_id)
        if completed:
            backfilled += 1
        else:
            exceptions += 1
    unresolved = MigrationReconciliation.objects.filter(
        organisation=organisation, migration_id=MIGRATION_ID, resolution_state="PENDING"
    )
    if facility_id:
        unresolved = unresolved.filter(facility_id=facility_id)
    return MigrationSummary(
        MIGRATION_ID,
        "BACKFILL",
        inspected=inspected,
        backfilled=backfilled,
        exceptions=exceptions,
        unresolved=unresolved.count(),
    )


def verify_mig001(*, organisation, facility_id=None):
    """Run the frozen MIG-001 gates without changing product data."""

    assert_transaction_active()
    all_queues = QueueEntry.objects.filter(organisation=organisation)
    visits = Visit.objects.filter(organisation=organisation, legacy_source_key__isnull=False)
    if facility_id:
        all_queues = all_queues.filter(facility_id=facility_id)
        visits = visits.filter(facility_id=facility_id)

    # A canonical S-01 queue is also a QueueEntry, but it is not part of the
    # immutable legacy population L_queue.  During the dual-write window the
    # source key on a migrated Visit is the only durable discriminator that
    # lets parity ignore newly-created target rows without losing old rows that
    # are still waiting for reconciliation.
    queues = all_queues.filter(
        models.Q(visit_id__isnull=True)
        | models.Q(visit__legacy_source_key__startswith="queue:")
    )
    queue_without_visit = queues.filter(visit_id__isnull=True).count()
    linked_visit_count = queues.filter(visit_id__isnull=False).count()
    unresolved_query = MigrationReconciliation.objects.filter(
        organisation=organisation, migration_id=MIGRATION_ID, resolution_state="PENDING"
    )
    if facility_id:
        unresolved_query = unresolved_query.filter(facility_id=facility_id)
    unresolved = unresolved_query.count()
    duplicate_groups = (
        visits.filter(state__in=Visit.ACTIVE_STATES)
        .values("facility_id", "patient_id", "local_service_date")
        .annotate(row_count=models.Count("id"))
        .filter(row_count__gt=1)
        .count()
    )
    scope_mismatches = 0
    linked_encounter_mismatches = 0
    linked_invoice_mismatches = 0
    for queue in queues.filter(visit_id__isnull=False).select_related("visit").iterator():
        if (
            queue.visit.organisation_id != queue.organisation_id
            or queue.visit.facility_id != queue.facility_id
            or queue.visit.patient_id != queue.patient_id
        ):
            scope_mismatches += 1
            continue
        encounters = Encounter.objects.filter(
            organisation=organisation,
            queue_entry=queue,
        ).order_by("id")
        if any(encounter.visit_id != queue.visit_id for encounter in encounters):
            linked_encounter_mismatches += 1
        if encounters.filter(visit_id=queue.visit_id).exists():
            if Invoice.objects.filter(
                organisation=organisation,
                encounter_id__in=encounters.values("id"),
            ).exclude(visit_id=queue.visit_id).exists():
                linked_invoice_mismatches += 1
        elif Invoice.objects.filter(
            organisation=organisation,
            visit=queue.visit,
        ).exclude(patient_id=queue.patient_id).exists():
            linked_invoice_mismatches += 1
    consistency_failures = linked_encounter_mismatches + linked_invoice_mismatches
    if duplicate_groups or scope_mismatches or consistency_failures:
        unresolved += duplicate_groups + scope_mismatches + consistency_failures
    queue_count = queues.count()
    deterministic_visit_count = visits.filter(legacy_source_key__startswith="queue:").count()
    exception_queues = MigrationReconciliation.objects.filter(
        organisation=organisation,
        migration_id=MIGRATION_ID,
        legacy_table=LEGACY_QUEUE_TABLE,
    )
    if facility_id:
        exception_queues = exception_queues.filter(facility_id=facility_id)
    exception_queue_count = exception_queues.count()
    if queue_count != deterministic_visit_count + exception_queue_count:
        unresolved += 1
    return MigrationSummary(
        MIGRATION_ID,
        "VERIFY",
        inspected=queues.count(),
        exceptions=unresolved,
        unresolved=unresolved,
        queue_without_visit=queue_without_visit,
        linked_visit_count=linked_visit_count,
    )


def cutover_mig001(*, organisation, facility_id=None, parity_passes=2):
    """Enable canonical target routes only after two stable verification passes."""

    assert_transaction_active()
    if parity_passes < 2:
        raise ValueError("MIG-001 cutover requires two stable parity passes.")
    if facility_id:
        raise ValueError("MIG-001 cutover is organisation-wide; verify without a facility filter.")
    summary = None
    previous_signature = None
    for _ in range(parity_passes):
        current = verify_mig001(organisation=organisation, facility_id=facility_id)
        if current.queue_without_visit or current.unresolved:
            raise ValueError("MIG-001 cutover is blocked by unresolved legacy evidence.")
        signature = (
            current.inspected,
            current.queue_without_visit,
            current.linked_visit_count,
            current.unresolved,
        )
        if previous_signature is not None and signature != previous_signature:
            raise ValueError("MIG-001 parity scans are not stable.")
        previous_signature = signature
        summary = current
    switch, _ = MigrationCutover.objects.select_for_update().get_or_create(
        organisation=organisation,
        migration_id=MIGRATION_ID,
        defaults={"phase": "CUTOVER"},
    )
    switch.phase = "CUTOVER"
    switch.target_reads_enabled = True
    switch.target_writes_enabled = True
    switch.rollback_at = None
    switch.rollback_reason = ""
    switch.version += 1
    switch.save(update_fields=["phase", "target_reads_enabled", "target_writes_enabled", "rollback_at", "rollback_reason", "version", "updated_at"])
    return MigrationSummary(**{**summary.as_dict(), "phase": "CUTOVER", "parity_passes": parity_passes})


def rollback_mig001(*, organisation, reason, actor=None):
    """Disable target readers and writers while retaining every target row/link."""

    assert_transaction_active()
    reason = str(reason or "").strip()
    if len(reason) < 3:
        raise ValueError("A rollback reason is required.")
    switch, _ = MigrationCutover.objects.select_for_update().get_or_create(
        organisation=organisation,
        migration_id=MIGRATION_ID,
        defaults={"phase": "ROLLBACK"},
    )
    switch.phase = "ROLLBACK"
    switch.target_reads_enabled = False
    switch.target_writes_enabled = False
    switch.rollback_at = now()
    switch.rollback_reason = reason[:240]
    switch.version += 1
    switch.save(update_fields=["phase", "target_reads_enabled", "target_writes_enabled", "rollback_at", "rollback_reason", "version", "updated_at"])
    return switch


def target_reads_enabled(organisation):
    assert_transaction_active()
    switch = MigrationCutover.objects.filter(organisation=organisation, migration_id=MIGRATION_ID).first()
    return switch is None or switch.target_reads_enabled


def target_writes_enabled(organisation):
    assert_transaction_active()
    switch = MigrationCutover.objects.filter(organisation=organisation, migration_id=MIGRATION_ID).first()
    return switch is None or switch.target_writes_enabled


def legacy_writes_enabled(organisation):
    """Keep the pre-Visit queue writer available only before cutover or after rollback."""

    assert_transaction_active()
    switch = MigrationCutover.objects.filter(organisation=organisation, migration_id=MIGRATION_ID).first()
    return switch is None or not switch.target_writes_enabled


def resolve_reconciliation(*, organisation, reconciliation_id, actor, reason):
    assert_transaction_active()
    if len(str(reason or "").strip()) < 3:
        raise ValueError("A reconciliation reason is required.")
    evidence = MigrationReconciliation.objects.select_for_update().filter(
        id=reconciliation_id, organisation=organisation, migration_id=MIGRATION_ID
    ).first()
    if evidence is None:
        raise ValueError("Migration evidence was not found in this organisation.")
    evidence.resolution_state = "RESOLVED"
    evidence.resolved_by = actor
    from django.utils.timezone import now

    evidence.resolved_at = now()
    evidence.reason = str(reason).strip()[:240]
    evidence.save(update_fields=["resolution_state", "resolved_by", "resolved_at", "reason", "updated_at"])
    return evidence
