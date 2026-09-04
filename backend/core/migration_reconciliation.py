"""MIG-001 operational phases.

The module deliberately stores identifiers, classifier codes, and hashes only.
It never copies patient names, dates of birth, notes, or other PHI into
reconciliation evidence.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import uuid4

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
    parity_digest: str = ""
    scope_link_hash_verified: bool = False
    blocker_checks_passed: bool = False

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
            "parity_digest": self.parity_digest,
            "scope_link_hash_verified": self.scope_link_hash_verified,
            "blocker_checks_passed": self.blocker_checks_passed,
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
        "department_id": str(queue.department_id),
        "queue_date": queue.queue_date.isoformat(),
        "arrival_at": queue.arrival_at.isoformat() if queue.arrival_at else None,
        "queue_time": queue.queue_time.isoformat() if queue.queue_time else None,
        "visit_type": queue.visit_type,
        "claimed_by_id": str(queue.claimed_by_id) if queue.claimed_by_id else None,
        "encounter_ids": sorted(str(encounter.id) for encounter in encounters),
    }


def _target_evidence(*, queue, visit, encounters, invoices):
    return {
        "source_key": f"queue:{queue.id}",
        "visit_id": str(visit.id),
        "organisation_id": str(visit.organisation_id),
        "facility_id": str(visit.facility_id),
        "patient_id": str(visit.patient_id),
        "local_service_date": visit.local_service_date.isoformat(),
        "visit_type": visit.visit_type,
        "encounter_ids": sorted(str(encounter.id) for encounter in encounters),
        "invoice_ids": sorted(str(invoice.id) for invoice in invoices),
    }


def _invoice_lineage_source_evidence(encounter, invoices):
    return {
        "encounter_id": str(encounter.id),
        "facility_id": str(encounter.facility_id),
        "patient_id": str(encounter.patient_id),
        "invoice_ids": sorted(str(invoice.id) for invoice in invoices),
        "invoice_visits": [
            {
                "invoice_id": str(invoice.id),
                "visit_id": str(invoice.visit_id) if invoice.visit_id else None,
            }
            for invoice in invoices
        ],
    }


def _encounter_source_evidence(encounter):
    return {
        "encounter_id": str(encounter.id),
        "facility_id": str(encounter.facility_id),
        "patient_id": str(encounter.patient_id),
        "queue_entry_id": str(encounter.queue_entry_id) if encounter.queue_entry_id else None,
        "visit_id": str(encounter.visit_id) if encounter.visit_id else None,
    }


def _invoice_source_evidence(invoice):
    return {
        "invoice_id": str(invoice.id),
        "facility_id": str(invoice.facility_id),
        "patient_id": str(invoice.patient_id),
        "encounter_id": str(invoice.encounter_id) if invoice.encounter_id else None,
        "visit_id": str(invoice.visit_id) if invoice.visit_id else None,
    }


def _service_price_source_evidence(price):
    return {
        "service_price_id": str(price.id),
        "facility_id": str(price.facility_id),
        "service_id": str(price.service_id),
        "price_list_id": str(price.price_list_id) if price.price_list_id else None,
        "effective_from": price.effective_from.isoformat(),
        "effective_to": price.effective_to.isoformat() if price.effective_to else None,
        "amount": str(price.amount),
        "currency": price.currency,
        "is_active": price.is_active,
        "active": price.active,
    }


def _payer_binding_source_evidence(binding):
    return {
        "payer_binding_id": str(binding.id),
        "facility_id": str(binding.facility_id),
        "visit_id": str(binding.visit_id),
        "price_list_id": str(binding.price_list_id) if binding.price_list_id else None,
        "payer_type": binding.payer_type,
        "active": binding.active,
    }


def _current_source_hash(evidence):
    """Recompute the non-PHI source hash used for a reconciliation row."""

    if evidence.legacy_table == LEGACY_QUEUE_TABLE:
        queue = QueueEntry.objects.filter(
            organisation_id=evidence.organisation_id,
            id=evidence.legacy_pk,
        ).first()
        if queue is None:
            return ""
        encounters = list(
            Encounter.objects.filter(
                organisation_id=evidence.organisation_id,
                queue_entry_id=queue.id,
            ).order_by("id")
        )
        return _stable_hash(_source_evidence(queue, encounters))

    if evidence.legacy_table == "clinical_encounter":
        encounter = Encounter.objects.filter(
            organisation_id=evidence.organisation_id,
            id=evidence.legacy_pk,
        ).first()
        if encounter is None:
            return ""
        return _stable_hash(_encounter_source_evidence(encounter))

    if evidence.legacy_table == "billing_invoice":
        invoice = Invoice.objects.filter(
            organisation_id=evidence.organisation_id,
            id=evidence.legacy_pk,
        ).first()
        if invoice is None:
            return ""
        return _stable_hash(_invoice_source_evidence(invoice))

    if evidence.legacy_table == "billing_invoice_lineage":
        encounter = Encounter.objects.filter(
            organisation_id=evidence.organisation_id,
            id=evidence.legacy_pk,
        ).first()
        if encounter is None:
            return ""
        invoices = list(
            Invoice.objects.filter(
                organisation_id=evidence.organisation_id,
                encounter_id=encounter.id,
            ).order_by("id")
        )
        return _stable_hash(_invoice_lineage_source_evidence(encounter, invoices))

    if evidence.legacy_table == "billing_serviceprice":
        from billing.models import ServicePrice

        price = ServicePrice.objects.filter(
            organisation_id=evidence.organisation_id,
            id=evidence.legacy_pk,
        ).first()
        return _stable_hash(_service_price_source_evidence(price)) if price is not None else ""

    if evidence.legacy_table == "billing_visitpayerbinding":
        from billing.models import VisitPayerBinding

        binding = VisitPayerBinding.objects.filter(
            organisation_id=evidence.organisation_id,
            id=evidence.legacy_pk,
        ).first()
        return _stable_hash(_payer_binding_source_evidence(binding)) if binding is not None else ""

    return ""


def _legacy_queue_population(*, organisation, facility_id=None):
    queryset = QueueEntry.objects.filter(organisation=organisation).filter(
        models.Q(visit_id__isnull=True)
        | models.Q(visit__legacy_source_key__startswith="queue:")
    )
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    return queryset.order_by("id")


def _cutover_switch(organisation, *, phase="EXPANDED"):
    switch, _ = MigrationCutover.objects.select_for_update().get_or_create(
        organisation_id=getattr(organisation, "id", organisation),
        migration_id=MIGRATION_ID,
        defaults={
            "phase": phase,
            "target_reads_enabled": False,
            "target_writes_enabled": False,
        },
    )
    return switch


def _record_exception(*, queue=None, legacy_table, legacy_pk, organisation_id, facility_id, codes, target_refs=None, source_hash="", target_hash="", run_id=None):
    evidence, created = MigrationReconciliation.objects.get_or_create(
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
    if not created:
        evidence.facility_id = facility_id
        evidence.evidence_codes = sorted(set(codes))
        evidence.proposed_target_refs = target_refs
        evidence.source_hash = source_hash
        evidence.target_hash = target_hash
        evidence.backfill_run_id = run_id
        update_fields = [
            "facility",
            "evidence_codes",
            "proposed_target_refs",
            "source_hash",
            "target_hash",
            "backfill_run_id",
            "updated_at",
        ]
        # A previously approved exception is stale if the corrected source
        # becomes invalid again. Re-open it rather than allowing a stale
        # resolution to make a later cutover appear safe.
        if evidence.resolution_state == "RESOLVED":
            evidence.resolution_state = "PENDING"
            evidence.resolved_by = None
            evidence.resolved_at = None
            evidence.reason = ""
            update_fields.extend(["resolution_state", "resolved_by", "resolved_at", "reason"])
        evidence.save(update_fields=update_fields)
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


def _inventory_snapshot(*, organisation, facility_id=None):
    """Return durable, non-PHI source evidence for the current legacy population."""

    queue_rows = []
    queue_exception_count = 0
    queues = _legacy_queue_population(
        organisation=organisation,
        facility_id=facility_id,
    ).select_related("facility", "patient", "department")
    for queue in queues.iterator():
        if queue.visit_id is None:
            codes, encounters, _, _ = _classify_queue(queue)
        else:
            encounters = list(
                Encounter.objects.filter(queue_entry_id=queue.id).order_by("id")
            )
            codes = []
        if codes:
            queue_exception_count += 1
        queue_rows.append(
            {
                "legacy_pk": str(queue.id),
                "source_hash": _stable_hash(_source_evidence(queue, encounters)),
                "evidence_codes": sorted(set(codes)),
            }
        )

    orphan_encounters = list(
        Encounter.objects.filter(
            organisation=organisation,
            queue_entry_id__isnull=True,
            visit_id__isnull=True,
            **({"facility_id": facility_id} if facility_id else {}),
        )
        .order_by("id")
        .values_list("id", "facility_id", "patient_id")
    )
    orphan_invoices = list(
        Invoice.objects.filter(
            organisation=organisation,
            encounter_id__isnull=True,
            visit_id__isnull=True,
            **({"facility_id": facility_id} if facility_id else {}),
        )
        .order_by("id")
        .values_list("id", "facility_id", "patient_id")
    )
    orphan_encounter_rows = [
        {
            "legacy_pk": str(identifier),
            "source_hash": _stable_hash(
                {
                    "encounter_id": str(identifier),
                    "facility_id": str(row_facility),
                    "patient_id": str(row_patient),
                }
            ),
            "evidence_codes": ["QUEUELESS_ENCOUNTER"],
        }
        for identifier, row_facility, row_patient in orphan_encounters
    ]
    orphan_invoice_rows = [
        {
            "legacy_pk": str(identifier),
            "source_hash": _stable_hash(
                {
                    "invoice_id": str(identifier),
                    "facility_id": str(row_facility),
                    "patient_id": str(row_patient),
                }
            ),
            "evidence_codes": ["QUEUELESS_INVOICE_NO_LINEAGE"],
        }
        for identifier, row_facility, row_patient in orphan_invoices
    ]
    return {
        "source_count": len(queue_rows),
        "exception_count": queue_exception_count + len(orphan_encounter_rows) + len(orphan_invoice_rows),
        "digest": _stable_hash(
            {
                "queues": queue_rows,
                "orphan_encounters": orphan_encounter_rows,
                "orphan_invoices": orphan_invoice_rows,
            }
        ),
    }


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
            source_hash=_stable_hash(_invoice_lineage_source_evidence(encounter, invoices)),
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
            source_hash=_stable_hash(_invoice_source_evidence(invoice)),
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
            source_hash=_stable_hash(_invoice_source_evidence(invoice)),
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
            evidence = MigrationReconciliation.objects.filter(
                organisation_id=queue.organisation_id,
                migration_id=MIGRATION_ID,
                legacy_table=LEGACY_QUEUE_TABLE,
                legacy_pk=str(queue.id),
            ).first()
            if evidence is not None:
                evidence.source_hash = source_hash
                evidence.proposed_target_refs = {"queue_id": str(queue.id)}
                evidence.backfill_run_id = run_id
                evidence.save(
                    update_fields=["source_hash", "proposed_target_refs", "backfill_run_id", "updated_at"]
                )
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
    queues = _legacy_queue_population(
        organisation=organisation,
        facility_id=facility_id,
    )
    for queue in queues.filter(visit_id__isnull=True).select_related(
        "facility", "patient", "department"
    ).iterator():
        codes, encounters, _, _ = _classify_queue(queue)
        if codes:
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
        organisation=organisation,
        queue_entry_id__isnull=True,
        visit_id__isnull=True,
        **({"facility_id": facility_id} if facility_id else {}),
    ).order_by("id"):
        _record_exception(
            legacy_table="clinical_encounter",
            legacy_pk=encounter.id,
            organisation_id=encounter.organisation_id,
            facility_id=encounter.facility_id,
            codes=["QUEUELESS_ENCOUNTER"],
            source_hash=_stable_hash(_encounter_source_evidence(encounter)),
        )
    for invoice in Invoice.objects.filter(
        organisation=organisation,
        encounter_id__isnull=True,
        visit_id__isnull=True,
        **({"facility_id": facility_id} if facility_id else {}),
    ).order_by("id"):
        _record_exception(
            legacy_table="billing_invoice",
            legacy_pk=invoice.id,
            organisation_id=invoice.organisation_id,
            facility_id=invoice.facility_id,
            codes=["QUEUELESS_INVOICE_NO_LINEAGE"],
            source_hash=_stable_hash(_invoice_source_evidence(invoice)),
        )
    snapshot = _inventory_snapshot(organisation=organisation, facility_id=facility_id)
    switch = _cutover_switch(organisation)
    switch.phase = "EXPANDED"
    switch.target_reads_enabled = False
    switch.target_writes_enabled = False
    switch.inventory_completed_at = now()
    switch.inventory_source_count = snapshot["source_count"]
    switch.inventory_digest = snapshot["digest"]
    # A new inventory invalidates any older backfill/parity proof. The target
    # rows themselves remain untouched and are retained for correction/rollback.
    switch.backfill_completed_at = None
    switch.backfill_source_count = 0
    switch.backfill_digest = ""
    switch.last_verified_at = None
    switch.parity_digest = ""
    switch.parity_passes = 0
    switch.scope_link_hash_verified = False
    switch.blocker_checks_passed = False
    switch.version += 1
    switch.save(
        update_fields=[
            "phase", "target_reads_enabled", "target_writes_enabled",
            "inventory_completed_at", "inventory_source_count", "inventory_digest",
            "backfill_completed_at", "backfill_source_count", "backfill_digest",
            "last_verified_at", "parity_digest", "parity_passes",
            "scope_link_hash_verified", "blocker_checks_passed", "version", "updated_at",
        ]
    )
    return MigrationSummary(
        MIGRATION_ID,
        "INVENTORY",
        inspected=snapshot["source_count"],
        exceptions=snapshot["exception_count"],
    )


def backfill_mig001(*, organisation, facility_id=None, batch_size=500, after_id=None, run_id=None):
    """Restartable stable-key backfill. Call again with the last id checkpoint."""

    assert_transaction_active()
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    run_id = run_id or uuid4()
    queues = _legacy_queue_population(
        organisation=organisation,
        facility_id=facility_id,
    ).filter(visit_id__isnull=True)
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
    population_rows = list(
        _legacy_queue_population(
            organisation=organisation,
            facility_id=facility_id,
        ).values("id", "visit_id")
    )
    known_queue_exceptions = set(
        MigrationReconciliation.objects.filter(
            organisation=organisation,
            migration_id=MIGRATION_ID,
            legacy_table=LEGACY_QUEUE_TABLE,
            legacy_pk__in=[str(row["id"]) for row in population_rows],
        ).values_list("legacy_pk", flat=True)
    )
    backfill_complete = all(
        row["visit_id"] is not None or str(row["id"]) in known_queue_exceptions
        for row in population_rows
    )
    snapshot = _inventory_snapshot(organisation=organisation, facility_id=facility_id)
    unresolved = MigrationReconciliation.objects.filter(
        organisation=organisation, migration_id=MIGRATION_ID, resolution_state="PENDING"
    )
    if facility_id:
        unresolved = unresolved.filter(facility_id=facility_id)
    switch = _cutover_switch(organisation)
    switch.phase = "EXPANDED"
    switch.target_reads_enabled = False
    switch.target_writes_enabled = False
    if backfill_complete and not facility_id:
        switch.backfill_completed_at = now()
        switch.backfill_source_count = snapshot["source_count"]
        switch.backfill_digest = snapshot["digest"]
    else:
        switch.backfill_completed_at = None
        switch.backfill_source_count = 0
        switch.backfill_digest = ""
    switch.last_verified_at = None
    switch.parity_digest = ""
    switch.parity_passes = 0
    switch.scope_link_hash_verified = False
    switch.blocker_checks_passed = False
    switch.version += 1
    switch.save(
        update_fields=[
            "phase", "target_reads_enabled", "target_writes_enabled",
            "backfill_completed_at", "backfill_source_count", "backfill_digest",
            "last_verified_at", "parity_digest", "parity_passes",
            "scope_link_hash_verified", "blocker_checks_passed", "version", "updated_at",
        ]
    )
    return MigrationSummary(
        MIGRATION_ID,
        "BACKFILL",
        inspected=inspected,
        backfilled=backfilled,
        exceptions=exceptions,
        unresolved=unresolved.count(),
        parity_digest=snapshot["digest"],
    )


def verify_mig001(*, organisation, facility_id=None):
    """Run the frozen MIG-001 gates without changing product data."""

    assert_transaction_active()
    queues = list(
        _legacy_queue_population(
            organisation=organisation,
            facility_id=facility_id,
        ).select_related("visit").order_by("id")
    )
    visits = list(
        Visit.objects.filter(
            organisation=organisation,
            legacy_source_key__isnull=False,
            **({"facility_id": facility_id} if facility_id else {}),
        ).order_by("id")
    )
    reconciliation_query = MigrationReconciliation.objects.filter(
        organisation=organisation, migration_id=MIGRATION_ID
    )
    if facility_id:
        reconciliation_query = reconciliation_query.filter(facility_id=facility_id)
    reconciliation_rows = list(reconciliation_query.order_by("id"))
    pending_reconciliations = [
        evidence for evidence in reconciliation_rows
        if evidence.resolution_state == "PENDING"
    ]
    unresolved = len(pending_reconciliations)
    duplicate_groups = (
        Visit.objects.filter(
            id__in=[visit.id for visit in visits],
            state__in=Visit.ACTIVE_STATES,
        )
        .values("facility_id", "patient_id", "local_service_date")
        .annotate(row_count=models.Count("id"))
        .filter(row_count__gt=1)
        .count()
    )
    scope_mismatches = 0
    linked_encounter_mismatches = 0
    linked_invoice_mismatches = 0
    queue_without_visit = 0
    linked_visit_count = 0
    hash_verified = True
    row_hashes = []
    expected_source_keys = {f"queue:{queue.id}" for queue in queues}
    deterministic_visits = []
    for visit in visits:
        if visit.legacy_source_key.startswith("queue:"):
            if visit.legacy_source_key not in expected_source_keys:
                scope_mismatches += 1
                hash_verified = False
            else:
                deterministic_visits.append(visit)

    exception_by_source = {
        (e.legacy_table, e.legacy_pk): e for e in reconciliation_rows
    }
    for queue in queues:
        encounters = list(
            Encounter.objects.filter(
                organisation=organisation,
                queue_entry=queue,
            ).order_by("id")
        )
        source = _source_evidence(queue, encounters)
        source_hash = _stable_hash(source)
        if queue.visit_id is None:
            queue_without_visit += 1
            evidence = exception_by_source.get((LEGACY_QUEUE_TABLE, str(queue.id)))
            if evidence is None or not evidence.source_hash:
                hash_verified = False
                row_hashes.append({"queue_id": str(queue.id), "source_hash": source_hash, "target_hash": ""})
            else:
                row_hashes.append({"queue_id": str(queue.id), "source_hash": evidence.source_hash, "target_hash": evidence.target_hash})
            continue

        linked_visit_count += 1
        visit = queue.visit
        target_scope_ok = (
            visit.legacy_source_key == f"queue:{queue.id}"
            and visit.organisation_id == queue.organisation_id
            and visit.facility_id == queue.facility_id
            and visit.patient_id == queue.patient_id
            and visit.local_service_date == queue.queue_date
        )
        if not target_scope_ok:
            scope_mismatches += 1
            hash_verified = False
            row_hashes.append({"queue_id": str(queue.id), "source_hash": source_hash, "target_hash": ""})
            continue
        encounter_link_failure = any(
            encounter.visit_id != queue.visit_id for encounter in encounters
        )
        if encounter_link_failure:
            linked_encounter_mismatches += 1
        encounter_ids = [encounter.id for encounter in encounters]
        linked_invoices = list(
            Invoice.objects.filter(
                organisation=organisation,
                encounter_id__in=encounter_ids,
            ).order_by("id")
        ) if encounter_ids else []
        invoice_link_failure = bool(
            linked_invoices
            and any(invoice.visit_id != queue.visit_id for invoice in linked_invoices)
        )
        if invoice_link_failure:
            linked_invoice_mismatches += 1
        if not encounter_ids:
            linked_invoices = list(
                Invoice.objects.filter(
                    organisation=organisation,
                    visit=visit,
                ).exclude(patient_id=queue.patient_id).order_by("id")
            )
            if linked_invoices:
                linked_invoice_mismatches += 1
                invoice_link_failure = True
        target = _target_evidence(
            queue=queue,
            visit=visit,
            encounters=encounters,
            invoices=linked_invoices,
        )
        target_hash = _stable_hash({"source": source, "target": target})
        row_hashes.append({"queue_id": str(queue.id), "source_hash": source_hash, "target_hash": target_hash})
        if encounter_link_failure or invoice_link_failure:
            hash_verified = False

    if queue_without_visit or linked_encounter_mismatches or linked_invoice_mismatches:
        hash_verified = False
    deterministic_visit_count = len(deterministic_visits)
    if len(deterministic_visits) != linked_visit_count:
        scope_mismatches += abs(len(deterministic_visits) - linked_visit_count)
        hash_verified = False
    consistency_failures = linked_encounter_mismatches + linked_invoice_mismatches
    if duplicate_groups or scope_mismatches or consistency_failures:
        unresolved += duplicate_groups + scope_mismatches + consistency_failures
    queue_count = len(queues)
    expected_source_ids = {str(queue.id) for queue in queues}
    exception_queue_count = sum(
        1 for evidence in pending_reconciliations
        if evidence.legacy_table == LEGACY_QUEUE_TABLE
        and evidence.legacy_pk in expected_source_ids
    )
    if queue_count != deterministic_visit_count + exception_queue_count:
        unresolved += 1
        hash_verified = False
    for evidence in reconciliation_rows:
        if not evidence.source_hash:
            hash_verified = False
        if evidence.resolution_state == "RESOLVED":
            current_source_hash = _current_source_hash(evidence)
            if not current_source_hash or current_source_hash != evidence.source_hash:
                unresolved += 1
                hash_verified = False
            converged, target_refs = _reconciliation_target(evidence)
            stored_refs = evidence.proposed_target_refs or {}
            if not converged or stored_refs != target_refs:
                unresolved += 1
                hash_verified = False
            else:
                expected_target_hash = _stable_hash(
                    {
                        "source_hash": evidence.source_hash,
                        "target_refs": stored_refs,
                    }
                )
                if not evidence.target_hash or evidence.target_hash != expected_target_hash:
                    unresolved += 1
                    hash_verified = False
        if evidence.legacy_table != LEGACY_QUEUE_TABLE or evidence.legacy_pk not in expected_source_ids:
            row_hashes.append(
                {
                    "source": f"{evidence.legacy_table}:{evidence.legacy_pk}",
                    "source_hash": evidence.source_hash,
                    "target_hash": evidence.target_hash,
                    "resolution_state": evidence.resolution_state,
                    "codes": sorted(evidence.evidence_codes),
                }
            )
    blocker_checks_passed = not Visit.objects.filter(
        organisation=organisation,
        legacy_source_key__startswith="queue:",
        emergency_setup_pending=True,
        **({"facility_id": facility_id} if facility_id else {}),
    ).exists()
    parity_digest = _stable_hash(
        {
            "queue_count": queue_count,
            "deterministic_visit_count": deterministic_visit_count,
            "rows": sorted(row_hashes, key=lambda row: json.dumps(row, sort_keys=True)),
        }
    )
    scope_link_hash_verified = hash_verified and not scope_mismatches and not consistency_failures
    return MigrationSummary(
        MIGRATION_ID,
        "VERIFY",
        inspected=queue_count,
        exceptions=unresolved,
        unresolved=unresolved,
        queue_without_visit=queue_without_visit,
        linked_visit_count=linked_visit_count,
        parity_digest=parity_digest,
        scope_link_hash_verified=scope_link_hash_verified,
        blocker_checks_passed=blocker_checks_passed,
    )


def cutover_mig001(*, organisation, facility_id=None, parity_passes=2):
    """Enable canonical target routes only after two stable verification passes."""

    assert_transaction_active()
    if parity_passes < 2:
        raise ValueError("MIG-001 cutover requires two stable parity passes.")
    if facility_id:
        raise ValueError("MIG-001 cutover is organisation-wide; verify without a facility filter.")
    switch = _cutover_switch(organisation)
    if switch.inventory_completed_at is None or not switch.inventory_digest:
        raise ValueError("MIG-001 cutover requires durable inventory evidence.")
    if switch.backfill_completed_at is None or not switch.backfill_digest:
        raise ValueError("MIG-001 cutover requires a completed durable backfill.")
    current_inventory = _inventory_snapshot(organisation=organisation)
    if (
        current_inventory["source_count"] != switch.inventory_source_count
        or current_inventory["digest"] != switch.inventory_digest
        or current_inventory["source_count"] != switch.backfill_source_count
        or current_inventory["digest"] != switch.backfill_digest
    ):
        raise ValueError("MIG-001 inventory/backfill evidence is stale; run the phases again.")
    summary = None
    previous_signature = None
    for _ in range(parity_passes):
        current = verify_mig001(organisation=organisation, facility_id=facility_id)
        if current.queue_without_visit or current.unresolved:
            raise ValueError("MIG-001 cutover is blocked by unresolved legacy evidence.")
        if not current.scope_link_hash_verified:
            raise ValueError("MIG-001 cutover is blocked by scope, link, or hash verification failure.")
        if not current.blocker_checks_passed:
            raise ValueError("MIG-001 cutover is blocked by an applicable product blocker.")
        signature = (
            current.inspected,
            current.queue_without_visit,
            current.linked_visit_count,
            current.unresolved,
            current.parity_digest,
            current.scope_link_hash_verified,
            current.blocker_checks_passed,
        )
        if previous_signature is not None and signature != previous_signature:
            raise ValueError("MIG-001 parity scans are not stable.")
        previous_signature = signature
        summary = current
    switch.phase = "CUTOVER"
    switch.target_reads_enabled = True
    switch.target_writes_enabled = True
    switch.last_verified_at = now()
    switch.parity_digest = summary.parity_digest
    switch.parity_passes = parity_passes
    switch.scope_link_hash_verified = summary.scope_link_hash_verified
    switch.blocker_checks_passed = summary.blocker_checks_passed
    switch.rollback_at = None
    switch.rollback_reason = ""
    switch.version += 1
    switch.save(
        update_fields=[
            "phase", "target_reads_enabled", "target_writes_enabled",
            "last_verified_at", "parity_digest", "parity_passes",
            "scope_link_hash_verified", "blocker_checks_passed",
            "rollback_at", "rollback_reason", "version", "updated_at",
        ]
    )
    return MigrationSummary(
        **{
            **summary.as_dict(),
            "phase": "CUTOVER",
            "parity_passes": parity_passes,
        }
    )


def rollback_mig001(*, organisation, reason, actor=None):
    """Disable target readers and writers while retaining every target row/link."""

    assert_transaction_active()
    reason = str(reason or "").strip()
    if len(reason) < 3:
        raise ValueError("A rollback reason is required.")
    switch = _cutover_switch(organisation, phase="ROLLBACK")
    switch.phase = "ROLLBACK"
    switch.target_reads_enabled = False
    switch.target_writes_enabled = False
    switch.rollback_at = now()
    switch.rollback_reason = reason[:240]
    switch.last_verified_at = None
    switch.parity_digest = ""
    switch.parity_passes = 0
    switch.scope_link_hash_verified = False
    switch.blocker_checks_passed = False
    switch.version += 1
    switch.save(
        update_fields=[
            "phase", "target_reads_enabled", "target_writes_enabled",
            "rollback_at", "rollback_reason", "last_verified_at", "parity_digest",
            "parity_passes", "scope_link_hash_verified", "blocker_checks_passed",
            "version", "updated_at",
        ]
    )
    return switch


def target_reads_enabled(organisation):
    assert_transaction_active()
    switch = MigrationCutover.objects.filter(organisation=organisation, migration_id=MIGRATION_ID).first()
    return bool(switch is not None and switch.target_reads_enabled)


def target_writes_enabled(organisation):
    assert_transaction_active()
    switch = MigrationCutover.objects.filter(organisation=organisation, migration_id=MIGRATION_ID).first()
    return bool(switch is not None and switch.target_writes_enabled)


def legacy_writes_enabled(organisation):
    """Keep the pre-Visit queue writer available only before cutover or after rollback."""

    assert_transaction_active()
    switch = MigrationCutover.objects.filter(organisation=organisation, migration_id=MIGRATION_ID).first()
    return switch is None or not switch.target_writes_enabled


def _reconciliation_target(evidence):
    """Return whether the source now has an attributable, scope-safe target."""

    if evidence.legacy_table == LEGACY_QUEUE_TABLE:
        queue = QueueEntry.objects.select_related("visit").filter(
            organisation_id=evidence.organisation_id,
            id=evidence.legacy_pk,
        ).first()
        if queue is None or queue.visit_id is None or queue.visit is None:
            return False, None
        visit = queue.visit
        if (
            visit.legacy_source_key != f"queue:{queue.id}"
            or visit.organisation_id != queue.organisation_id
            or visit.facility_id != queue.facility_id
            or visit.patient_id != queue.patient_id
            or visit.local_service_date != queue.queue_date
        ):
            return False, None
        return True, {"queue_id": str(queue.id), "visit_id": str(visit.id)}

    if evidence.legacy_table == "clinical_encounter":
        encounter = Encounter.objects.select_related("visit", "queue_entry").filter(
            organisation_id=evidence.organisation_id,
            id=evidence.legacy_pk,
        ).first()
        if encounter is None or encounter.visit_id is None:
            return False, None
        visit = encounter.visit
        if visit is None or (
            encounter.facility_id != evidence.facility_id
            or visit.organisation_id != encounter.organisation_id
            or visit.facility_id != encounter.facility_id
            or visit.patient_id != encounter.patient_id
            or (
                encounter.queue_entry_id is not None
                and (
                    encounter.queue_entry.visit_id != encounter.visit_id
                    or encounter.queue_entry.organisation_id != encounter.organisation_id
                    or encounter.queue_entry.facility_id != encounter.facility_id
                    or encounter.queue_entry.patient_id != encounter.patient_id
                )
            )
        ):
            return False, None
        return True, {
            "encounter_id": str(encounter.id),
            "visit_id": str(encounter.visit_id),
            "facility_id": str(encounter.facility_id),
        }

    if evidence.legacy_table == "billing_invoice":
        invoice = Invoice.objects.select_related("visit", "encounter").filter(
            organisation_id=evidence.organisation_id,
            id=evidence.legacy_pk,
        ).first()
        if invoice is None or invoice.visit_id is None:
            return False, None
        visit = invoice.visit
        if visit is None or (
            invoice.facility_id != evidence.facility_id
            or visit.organisation_id != invoice.organisation_id
            or visit.facility_id != invoice.facility_id
            or visit.patient_id != invoice.patient_id
            or (
                invoice.encounter_id is not None
                and (
                    invoice.encounter.visit_id != invoice.visit_id
                    or invoice.encounter.organisation_id != invoice.organisation_id
                    or invoice.encounter.facility_id != invoice.facility_id
                    or invoice.encounter.patient_id != invoice.patient_id
                )
            )
        ):
            return False, None
        return True, {
            "invoice_id": str(invoice.id),
            "visit_id": str(invoice.visit_id),
            "facility_id": str(invoice.facility_id),
        }

    if evidence.legacy_table == "billing_invoice_lineage":
        encounter = Encounter.objects.filter(
            organisation_id=evidence.organisation_id,
            id=evidence.legacy_pk,
        ).first()
        if encounter is None or encounter.visit_id is None:
            return False, None
        invoices = list(Invoice.objects.filter(
            organisation_id=evidence.organisation_id,
            encounter_id=encounter.id,
            visit_id=encounter.visit_id,
        ).order_by("id"))
        if len(invoices) != 1:
            return False, None
        invoice = invoices[0]
        if (
            invoice.facility_id != encounter.facility_id
            or invoice.patient_id != encounter.patient_id
        ):
            return False, None
        return True, {
            "encounter_id": str(encounter.id),
            "visit_id": str(encounter.visit_id),
            "invoice_id": str(invoice.id),
            "facility_id": str(encounter.facility_id),
        }

    # Price-reference evidence is produced by the same migration family. It
    # converges only when the missing FK is now a real, scope-owned reference.
    if evidence.legacy_table == "billing_serviceprice":
        from billing.models import ServicePrice

        price = ServicePrice.objects.select_related("facility", "service", "price_list").filter(
            organisation_id=evidence.organisation_id,
            id=evidence.legacy_pk,
            price_list_id__isnull=False,
        ).first()
        if price is None or (
            price.facility_id != evidence.facility_id
            or price.facility.organisation_id != evidence.organisation_id
            or price.service.organisation_id != evidence.organisation_id
            or price.price_list.organisation_id != evidence.organisation_id
        ):
            return False, None
        return True, {
            "service_price_id": str(price.id),
            "facility_id": str(price.facility_id),
            "service_id": str(price.service_id),
            "price_list_id": str(price.price_list_id),
        }
    if evidence.legacy_table == "billing_visitpayerbinding":
        from billing.models import VisitPayerBinding

        binding = VisitPayerBinding.objects.select_related("facility", "visit", "price_list").filter(
            organisation_id=evidence.organisation_id,
            id=evidence.legacy_pk,
            price_list_id__isnull=False,
        ).first()
        if binding is None or (
            binding.facility_id != evidence.facility_id
            or binding.facility.organisation_id != evidence.organisation_id
            or binding.visit.organisation_id != evidence.organisation_id
            or binding.visit.facility_id != binding.facility_id
            or binding.price_list.organisation_id != evidence.organisation_id
        ):
            return False, None
        return True, {
            "payer_binding_id": str(binding.id),
            "facility_id": str(binding.facility_id),
            "visit_id": str(binding.visit_id),
            "price_list_id": str(binding.price_list_id),
        }
    return False, None


def resolve_reconciliation(*, organisation, reconciliation_id, actor, reason):
    assert_transaction_active()
    if len(str(reason or "").strip()) < 3:
        raise ValueError("A reconciliation reason is required.")
    evidence = MigrationReconciliation.objects.select_for_update().filter(
        id=reconciliation_id, organisation=organisation, migration_id=MIGRATION_ID
    ).first()
    if evidence is None:
        raise ValueError("Migration evidence was not found in this organisation.")
    current_source_hash = _current_source_hash(evidence)
    if not current_source_hash:
        raise ValueError(
            "The legacy source is unavailable; correct the source and rerun inventory before resolving this evidence."
        )
    converged, target_refs = _reconciliation_target(evidence)
    if not converged:
        raise ValueError(
            "Correct the source linkage and scope, then rerun backfill before resolving this evidence."
        )
    evidence.source_hash = current_source_hash
    evidence.proposed_target_refs = target_refs
    evidence.target_hash = _stable_hash(
        {
            "source_hash": evidence.source_hash,
            "target_refs": target_refs,
        }
    )
    if evidence.resolution_state != "RESOLVED":
        evidence.resolution_state = "RESOLVED"
        evidence.resolved_by = actor
        evidence.resolved_at = now()
        evidence.reason = str(reason).strip()[:240]
    evidence.save(
        update_fields=[
            "resolution_state", "resolved_by", "resolved_at", "reason",
            "source_hash", "proposed_target_refs", "target_hash", "updated_at",
        ]
    )
    return evidence
