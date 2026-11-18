"""MIG-001 operational phases.

The module deliberately stores identifiers, classifier codes, and hashes only.
It never copies patient names, dates of birth, notes, or other PHI into
reconciliation evidence.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import uuid4

from django.db import IntegrityError, connection, models, transaction
from django.utils.timezone import now

from audit.services import record_fact
from core.models import MigrationCutover, MigrationReconciliation
from core.services import allocate_sequence, assert_transaction_active
from clinical.models import Encounter, TriageAssessment
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
    organisation_counts: dict = None
    facility_counts: dict = None
    shadow_read_equal: bool = False
    shadow_read_digest: str = ""
    stable_full_scan_count: int = 0
    applicable_blockers: tuple = ()
    run_id: str = ""

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
            "organisation_counts": self.organisation_counts or {},
            "facility_counts": self.facility_counts or {},
            "shadow_read_equal": self.shadow_read_equal,
            "shadow_read_digest": self.shadow_read_digest,
            "stable_full_scan_count": self.stable_full_scan_count,
            "applicable_blockers": list(self.applicable_blockers),
            "run_id": str(self.run_id) if self.run_id else "",
        }


def _stable_hash(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _scope_counts(queues):
    """Return non-PHI source counts by organisation and facility."""

    organisation_counts = {}
    facility_counts = {}
    for queue in queues:
        organisation_key = str(queue.organisation_id)
        facility_key = str(queue.facility_id)
        organisation_counts[organisation_key] = organisation_counts.get(organisation_key, 0) + 1
        facility_counts[facility_key] = facility_counts.get(facility_key, 0) + 1
    return organisation_counts, facility_counts


def _shadow_legacy_projection(queue):
    """The stable, non-PHI journey identity exposed by the legacy reader."""

    return {
        "organisation_id": str(queue.organisation_id),
        "facility_id": str(queue.facility_id),
        "patient_id": str(queue.patient_id),
        "local_service_date": queue.queue_date.isoformat(),
        "visit_type": "OUTPATIENT_NEW" if queue.visit_type == "WALK_IN" else queue.visit_type,
    }


def _shadow_target_projection(queue):
    """The matching identity from the canonical Visit reader."""

    visit = getattr(queue, "visit", None)
    if visit is None:
        return None
    return {
        "organisation_id": str(visit.organisation_id),
        "facility_id": str(visit.facility_id),
        "patient_id": str(visit.patient_id),
        "local_service_date": visit.local_service_date.isoformat(),
        "visit_type": visit.visit_type,
    }


def _shadow_read_snapshot(queues):
    rows = []
    for queue in queues:
        legacy = _shadow_legacy_projection(queue)
        target = _shadow_target_projection(queue)
        rows.append(
            {
                "source_key": f"queue:{queue.id}",
                "legacy": legacy,
                "target": target,
                "equal": target == legacy,
            }
        )
    return {
        "equal": all(row["equal"] for row in rows),
        "digest": _stable_hash(rows),
        "rows": rows,
    }


def _target_invoices_for_visit(*, organisation_id, visit_id):
    return list(
        Invoice.objects.filter(
            organisation_id=organisation_id,
            visit_id=visit_id,
        ).order_by("id")
    )


def _deterministic_row_evidence(*, queues, run_id):
    """Build durable per-source proof without copying any patient payload."""

    evidence = {}
    for queue in queues:
        visit = getattr(queue, "visit", None)
        if visit is None:
            continue
        encounters = list(
            Encounter.objects.filter(
                organisation_id=queue.organisation_id,
                queue_entry_id=queue.id,
            ).order_by("id")
        )
        source = _source_evidence(queue, encounters)
        target = _target_evidence(
            queue=queue,
            visit=visit,
            encounters=encounters,
            invoices=_target_invoices_for_visit(
                organisation_id=queue.organisation_id,
                visit_id=visit.id,
            ),
        )
        evidence[f"{LEGACY_QUEUE_TABLE}:{queue.id}"] = {
            "legacy_table": LEGACY_QUEUE_TABLE,
            "legacy_pk": str(queue.id),
            "organisation_id": str(queue.organisation_id),
            "facility_id": str(queue.facility_id),
            "source_hash": _stable_hash(source),
            "target_hash": _stable_hash({"source": source, "target": target}),
            "backfill_run_id": str(run_id),
            "target_refs": {
                "queue_id": str(queue.id),
                "visit_id": str(visit.id),
            },
        }
    return evidence


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
    if not target_hash and target_refs:
        target_hash = _stable_hash(
            {
                "source_hash": source_hash,
                "target_refs": target_refs,
            }
        )
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
    queues_seen = []
    queue_exception_count = 0
    queues = _legacy_queue_population(
        organisation=organisation,
        facility_id=facility_id,
    ).select_related("facility", "patient", "department")
    for queue in queues.iterator():
        queues_seen.append(queue)
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
    organisation_counts, facility_counts = _scope_counts(queues_seen)
    return {
        "source_count": len(queue_rows),
        "exception_count": queue_exception_count + len(orphan_encounter_rows) + len(orphan_invoice_rows),
        "organisation_counts": organisation_counts,
        "facility_counts": facility_counts,
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
            linked_encounters = list(
                Encounter.objects.filter(
                    organisation_id=queue.organisation_id,
                    queue_entry_id=queue.id,
                ).order_by("id")
            )
            target = _target_evidence(
                queue=queue,
                visit=visit,
                encounters=linked_encounters,
                invoices=_target_invoices_for_visit(
                    organisation_id=queue.organisation_id,
                    visit_id=visit.id,
                ),
            )
            target_refs = {"queue_id": str(queue.id), "visit_id": str(visit.id)}
            target_hash = _stable_hash({"source": source, "target": target})
            evidence = MigrationReconciliation.objects.filter(
                organisation_id=queue.organisation_id,
                migration_id=MIGRATION_ID,
                legacy_table=LEGACY_QUEUE_TABLE,
                legacy_pk=str(queue.id),
            ).first()
            if evidence is not None:
                evidence.source_hash = source_hash
                evidence.proposed_target_refs = target_refs
                evidence.target_hash = target_hash
                evidence.backfill_run_id = run_id
                evidence.save(
                    update_fields=[
                        "source_hash", "proposed_target_refs", "target_hash",
                        "backfill_run_id", "updated_at",
                    ]
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


def inventory_mig001(*, organisation, facility_id=None, run_id=None):
    """Classify every legacy source row and persist only exception evidence."""

    assert_transaction_active()
    run_id = run_id or uuid4()
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
                run_id=run_id,
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
            run_id=run_id,
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
            run_id=run_id,
        )
    snapshot = _inventory_snapshot(organisation=organisation, facility_id=facility_id)
    switch = _cutover_switch(organisation)
    switch.phase = "EXPANDED"
    switch.target_reads_enabled = False
    switch.target_writes_enabled = False
    switch.inventory_completed_at = now()
    switch.inventory_source_count = snapshot["source_count"]
    switch.inventory_digest = snapshot["digest"]
    switch.inventory_organisation_counts = snapshot["organisation_counts"]
    switch.inventory_facility_counts = snapshot["facility_counts"]
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
    switch.backfill_organisation_counts = {}
    switch.backfill_facility_counts = {}
    switch.deterministic_row_evidence = {}
    switch.shadow_read_equal = False
    switch.shadow_read_digest = ""
    switch.stable_full_scan_count = 0
    switch.last_run_id = run_id
    switch.write_fence += 1
    switch.version += 1
    switch.save(
        update_fields=[
            "phase", "target_reads_enabled", "target_writes_enabled",
            "inventory_completed_at", "inventory_source_count", "inventory_digest",
            "inventory_organisation_counts", "inventory_facility_counts",
            "backfill_completed_at", "backfill_source_count", "backfill_digest",
            "last_verified_at", "parity_digest", "parity_passes",
            "scope_link_hash_verified", "blocker_checks_passed",
            "backfill_organisation_counts", "backfill_facility_counts",
            "deterministic_row_evidence", "shadow_read_equal", "shadow_read_digest",
            "stable_full_scan_count", "last_run_id", "write_fence", "version", "updated_at",
        ]
    )
    return MigrationSummary(
        MIGRATION_ID,
        "INVENTORY",
        inspected=snapshot["source_count"],
        exceptions=snapshot["exception_count"],
        organisation_counts=snapshot["organisation_counts"],
        facility_counts=snapshot["facility_counts"],
        run_id=str(run_id),
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
    proof_queues = list(
        _legacy_queue_population(
            organisation=organisation,
            facility_id=facility_id,
        ).select_related("facility", "patient", "department", "visit").order_by("id")
    )
    population_rows = [{"id": queue.id, "visit_id": queue.visit_id} for queue in proof_queues]
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
    deterministic_evidence = _deterministic_row_evidence(
        queues=proof_queues,
        run_id=run_id,
    )
    persisted_deterministic_evidence = dict(switch.deterministic_row_evidence or {})
    if facility_id:
        persisted_deterministic_evidence.update(deterministic_evidence)
    else:
        persisted_deterministic_evidence = deterministic_evidence
    switch.phase = "EXPANDED"
    switch.target_reads_enabled = False
    switch.target_writes_enabled = False
    if backfill_complete and not facility_id:
        switch.backfill_completed_at = now()
        switch.backfill_source_count = snapshot["source_count"]
        switch.backfill_digest = snapshot["digest"]
        switch.backfill_organisation_counts = snapshot["organisation_counts"]
        switch.backfill_facility_counts = snapshot["facility_counts"]
    else:
        switch.backfill_completed_at = None
        switch.backfill_source_count = 0
        switch.backfill_digest = ""
        switch.backfill_organisation_counts = {}
        switch.backfill_facility_counts = {}
    switch.last_verified_at = None
    switch.parity_digest = ""
    switch.parity_passes = 0
    switch.scope_link_hash_verified = False
    switch.blocker_checks_passed = False
    switch.deterministic_row_evidence = persisted_deterministic_evidence
    switch.shadow_read_equal = False
    switch.shadow_read_digest = ""
    switch.stable_full_scan_count = 0
    switch.last_run_id = run_id
    switch.write_fence += 1
    switch.version += 1
    switch.save(
        update_fields=[
            "phase", "target_reads_enabled", "target_writes_enabled",
            "backfill_completed_at", "backfill_source_count", "backfill_digest",
            "backfill_organisation_counts", "backfill_facility_counts",
            "last_verified_at", "parity_digest", "parity_passes",
            "scope_link_hash_verified", "blocker_checks_passed",
            "deterministic_row_evidence", "shadow_read_equal", "shadow_read_digest",
            "stable_full_scan_count", "last_run_id", "write_fence", "version", "updated_at",
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
        organisation_counts=snapshot["organisation_counts"],
        facility_counts=snapshot["facility_counts"],
        run_id=str(run_id),
    )


def verify_mig001(*, organisation, facility_id=None):
    """Run the frozen MIG-001 gates without changing product data."""

    assert_transaction_active()
    switch = _cutover_switch(organisation)
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
    unresolved_keys = {
        (evidence.legacy_table, str(evidence.legacy_pk))
        for evidence in pending_reconciliations
    }
    unresolved = len(unresolved_keys)

    def mark_unresolved(legacy_table, legacy_pk):
        nonlocal unresolved
        key = (legacy_table, str(legacy_pk))
        if key not in unresolved_keys:
            unresolved_keys.add(key)
            unresolved += 1

    pending_queue_keys = {
        (LEGACY_QUEUE_TABLE, str(evidence.legacy_pk))
        for evidence in pending_reconciliations
        if evidence.legacy_table == LEGACY_QUEUE_TABLE
    }
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
            elif (
                LEGACY_QUEUE_TABLE,
                visit.legacy_source_key[len("queue:"):],
            ) not in pending_queue_keys:
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
                mark_unresolved(LEGACY_QUEUE_TABLE, queue.id)
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
                visit=visit,
            ).order_by("id")
        )
        invoice_link_failure = any(
            invoice.facility_id != queue.facility_id
            or invoice.patient_id != queue.patient_id
            or (
                invoice.encounter_id is not None
                and invoice.encounter_id not in encounter_ids
            )
            for invoice in linked_invoices
        )
        if invoice_link_failure:
            linked_invoice_mismatches += 1
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
        persisted_proof = (switch.deterministic_row_evidence or {}).get(
            f"{LEGACY_QUEUE_TABLE}:{queue.id}"
        )
        if (
            not persisted_proof
            or persisted_proof.get("source_hash") != source_hash
            or persisted_proof.get("target_hash") != target_hash
            or not persisted_proof.get("backfill_run_id")
            or persisted_proof.get("target_refs") != {
                "queue_id": str(queue.id),
                "visit_id": str(visit.id),
            }
        ):
            mark_unresolved(LEGACY_QUEUE_TABLE, queue.id)
            hash_verified = False

    if queue_without_visit or linked_encounter_mismatches or linked_invoice_mismatches:
        hash_verified = False
    deterministic_visit_count = len(deterministic_visits)
    pending_linked_visit_count = sum(
        1
        for queue in queues
        if queue.visit_id is not None
        and (LEGACY_QUEUE_TABLE, str(queue.id)) in pending_queue_keys
    )
    if len(deterministic_visits) + pending_linked_visit_count != linked_visit_count:
        scope_mismatches += abs(
            len(deterministic_visits) + pending_linked_visit_count - linked_visit_count
        )
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
        mark_unresolved(LEGACY_QUEUE_TABLE, "QUEUE_POPULATION_PARITY")
        hash_verified = False
    for evidence in reconciliation_rows:
        if not evidence.source_hash:
            hash_verified = False
        if evidence.resolution_state == "RESOLVED":
            current_source_hash = _current_source_hash(evidence)
            if not current_source_hash or current_source_hash != evidence.source_hash:
                mark_unresolved(evidence.legacy_table, evidence.legacy_pk)
                hash_verified = False
            converged, target_refs = _reconciliation_target(evidence)
            stored_refs = evidence.proposed_target_refs or {}
            if not converged or stored_refs != target_refs:
                mark_unresolved(evidence.legacy_table, evidence.legacy_pk)
                hash_verified = False
            else:
                expected_target_hash = _stable_hash(
                    {
                        "source_hash": evidence.source_hash,
                        "target_refs": stored_refs,
                    }
                )
                if not evidence.target_hash or evidence.target_hash != expected_target_hash:
                    mark_unresolved(evidence.legacy_table, evidence.legacy_pk)
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
    blocker_query = Visit.objects.filter(
        organisation=organisation,
        legacy_source_key__startswith="queue:",
        emergency_setup_pending=True,
        **({"facility_id": facility_id} if facility_id else {}),
    )
    applicable_blockers = ("EMERGENCY_SETUP_PENDING",) if blocker_query.exists() else ()
    blocker_checks_passed = not applicable_blockers
    shadow = _shadow_read_snapshot(queues)
    organisation_counts, facility_counts = _scope_counts(queues)
    parity_digest = _stable_hash(
        {
            "queue_count": queue_count,
            "deterministic_visit_count": deterministic_visit_count,
            "rows": sorted(row_hashes, key=lambda row: json.dumps(row, sort_keys=True)),
        }
    )
    scope_link_hash_verified = hash_verified and not scope_mismatches and not consistency_failures
    stable_full_scan_count = (
        min(2, switch.stable_full_scan_count + 1)
        if switch.parity_digest == parity_digest
        and switch.shadow_read_digest == shadow["digest"]
        and switch.shadow_read_equal == shadow["equal"]
        else 1
    )
    switch.last_verified_at = now()
    switch.parity_digest = parity_digest
    switch.scope_link_hash_verified = scope_link_hash_verified
    switch.blocker_checks_passed = blocker_checks_passed
    switch.shadow_read_equal = shadow["equal"]
    switch.shadow_read_digest = shadow["digest"]
    switch.stable_full_scan_count = stable_full_scan_count
    switch.save(
        update_fields=[
            "last_verified_at", "parity_digest", "scope_link_hash_verified",
            "blocker_checks_passed", "shadow_read_equal", "shadow_read_digest",
            "stable_full_scan_count", "updated_at",
        ]
    )
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
        organisation_counts=organisation_counts,
        facility_counts=facility_counts,
        shadow_read_equal=shadow["equal"],
        shadow_read_digest=shadow["digest"],
        stable_full_scan_count=stable_full_scan_count,
        applicable_blockers=applicable_blockers,
        run_id=str(switch.last_run_id) if switch.last_run_id else "",
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
        if not current.shadow_read_equal:
            raise ValueError("MIG-001 cutover is blocked by unequal legacy/target shadow reads.")
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
    if summary is None or summary.stable_full_scan_count < 2:
        raise ValueError("MIG-001 cutover requires two stable full scans.")
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
    switch.write_fence += 1
    switch.version += 1
    switch.save(
        update_fields=[
            "phase", "target_reads_enabled", "target_writes_enabled",
            "last_verified_at", "parity_digest", "parity_passes",
            "scope_link_hash_verified", "blocker_checks_passed",
            "rollback_at", "rollback_reason", "write_fence", "version", "updated_at",
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
    switch.shadow_read_equal = False
    switch.shadow_read_digest = ""
    switch.stable_full_scan_count = 0
    switch.write_fence += 1
    switch.version += 1
    switch.save(
        update_fields=[
            "phase", "target_reads_enabled", "target_writes_enabled",
            "rollback_at", "rollback_reason", "last_verified_at", "parity_digest",
            "parity_passes", "scope_link_hash_verified", "blocker_checks_passed",
            "shadow_read_equal", "shadow_read_digest", "stable_full_scan_count",
            "write_fence", "version", "updated_at",
        ]
    )
    return switch


def target_reads_enabled(organisation):
    assert_transaction_active()
    switch = MigrationCutover.objects.filter(organisation=organisation, migration_id=MIGRATION_ID).first()
    return bool(switch is not None and switch.target_reads_enabled)


def target_writes_enabled(organisation):
    """Lock the MIG-001 fence for the full duration of a target write.

    Cutover and rollback take this same row lock and hold it until their
    outer tenant transaction commits.  A writer that acquired the lock first
    therefore commits before the transition; a writer that acquires it after
    the transition observes the new flag and refuses to mutate.
    """

    assert_transaction_active()
    switch = _cutover_switch(organisation)
    return bool(switch.target_writes_enabled)


def legacy_writes_enabled(organisation):
    """Keep the pre-Visit queue writer available only before cutover or after rollback."""

    assert_transaction_active()
    switch = _cutover_switch(organisation)
    return not switch.target_writes_enabled


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
    was_resolved = evidence.resolution_state == "RESOLVED"
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
    if not was_resolved:
        record_fact(
            organisation=organisation,
            actor=actor,
            event_code="MIGRATION_RECONCILIATION_RESOLVED",
            action="UPDATE",
            entity_type="MigrationReconciliation",
            entity_id=evidence.id,
            source_ids={
                "reconciliation_id": evidence.id,
                "migration_id": evidence.migration_id,
                "legacy_table": evidence.legacy_table,
                "legacy_pk": evidence.legacy_pk,
                "backfill_run_id": evidence.backfill_run_id or "none",
            },
            after={
                "resolution_state": evidence.resolution_state,
                "source_hash": evidence.source_hash,
                "target_hash": evidence.target_hash,
                "reason_hash": _stable_hash(str(reason).strip()),
            },
        )
    return evidence


# ---------------------------------------------------------------------------
# MIG-002: canonical QueueEntry state adaptation
# ---------------------------------------------------------------------------

MIG002_ID = "MIG-002"
MIG_002_ID = MIG002_ID
MIG002_LEGACY_TABLE = "scheduling_queueentry"
MIG002_CANONICAL_STATES = frozenset(
    {
        "WAITING_PAYMENT",
        "WAITING",
        "CALLED",
        "IN_SERVICE",
        "ON_HOLD",
        "READY_TO_RESUME",
        "COMPLETED",
        "TRANSFERRED",
        "CANCELLED",
        "LWBS",
        "NO_SHOW",
        "EXPIRED",
    }
)
MIG002_ACTIVE_STATES = frozenset(
    {
        "WAITING_PAYMENT",
        "WAITING",
        "CALLED",
        "IN_SERVICE",
        "ON_HOLD",
        "READY_TO_RESUME",
    }
)
MIG002_LEGACY_STATE_MAP = {
    "WAITING": "WAITING",
    "CALLED": "CALLED",
    "CANCELLED": "CANCELLED",
    "IN_TRIAGE": "IN_SERVICE",
    "TRIAGED": "COMPLETED",
    "IN_CONSULTATION": "IN_SERVICE",
    "COMPLETED": "COMPLETED",
}
MIG002_SUPPORTED_LEGACY_STATES = frozenset(MIG002_LEGACY_STATE_MAP)
MIG002_TARGET_WORK_IDENTITY_PREFIXES = (
    "MIG-002:CONSULTATION:",
    "COMPATIBILITY:MIG-002-ROLLBACK:",
)


def _mig002_source_evidence(queue, *, assessment_ids=(), encounter_ids=()):
    """Return source and scope evidence without copying PHI.

    Target-only fields such as ``state`` and ``work_identity`` are deliberately
    excluded.  A backfill must not change the source hash it is proving.
    """

    visit = getattr(queue, "visit", None)
    department = getattr(queue, "department", None)

    return {
        "legacy_table": MIG002_LEGACY_TABLE,
        "legacy_pk": str(queue.id),
        "organisation_id": str(queue.organisation_id),
        "facility_id": str(queue.facility_id),
        "visit_id": str(queue.visit_id) if queue.visit_id else None,
        "patient_id": str(queue.patient_id),
        "department_id": str(queue.department_id),
        "queue_date": queue.queue_date.isoformat(),
        "queue_type": queue.queue_type,
        "status": queue.status,
        "current_stage": queue.current_stage,
        "hold_reason_present": bool(queue.hold_reason),
        "priority": queue.priority,
        "priority_reason_present": bool(queue.priority_reason),
        "arrival_at": queue.arrival_at.isoformat() if queue.arrival_at else None,
        "queue_time": queue.queue_time.isoformat() if queue.queue_time else None,
        "called_at": queue.called_at.isoformat() if queue.called_at else None,
        "called_by_id": str(queue.called_by_id) if queue.called_by_id else None,
        "claimed_by_id": str(queue.claimed_by_id) if queue.claimed_by_id else None,
        "claimed_at": queue.claimed_at.isoformat() if queue.claimed_at else None,
        "assigned_user_id": str(queue.assigned_user_id) if queue.assigned_user_id else None,
        "served_by_id": str(queue.served_by_id) if queue.served_by_id else None,
        "started_at": queue.started_at.isoformat() if queue.started_at else None,
        "service_started_at": (
            queue.service_started_at.isoformat() if queue.service_started_at else None
        ),
        "completed_by_id": str(queue.completed_by_id) if queue.completed_by_id else None,
        "completed_at": queue.completed_at.isoformat() if queue.completed_at else None,
        "removed_by_id": str(queue.removed_by_id) if queue.removed_by_id else None,
        "removed_at": queue.removed_at.isoformat() if queue.removed_at else None,
        "visit_scope": {
            "organisation_id": str(visit.organisation_id),
            "facility_id": str(visit.facility_id),
            "patient_id": str(visit.patient_id),
            "local_service_date": visit.local_service_date.isoformat(),
        } if visit is not None else None,
        "department_scope": {
            "organisation_id": str(department.organisation_id),
            "facility_id": str(department.facility_id),
            "department_id": str(department.id),
            "code": department.code,
        } if department is not None else None,
        "assessment_ids": sorted(str(value) for value in assessment_ids),
        "encounter_ids": sorted(str(value) for value in encounter_ids),
    }


def _mig002_source_hash(queue, *, assessment_ids=(), encounter_ids=()):
    return _stable_hash(
        _mig002_source_evidence(
            queue,
            assessment_ids=assessment_ids,
            encounter_ids=encounter_ids,
        )
    )


def _mig002_related_ids(queue):
    assessment_ids = list(
        TriageAssessment.objects.filter(
            organisation_id=queue.organisation_id,
            queue_entry_id=queue.id,
        )
        .order_by("id")
        .values_list("id", flat=True)
    )
    encounter_ids = list(
        Encounter.objects.filter(
            organisation_id=queue.organisation_id,
            queue_entry_id=queue.id,
        )
        .order_by("id")
        .values_list("id", flat=True)
    )
    return assessment_ids, encounter_ids


def _mig002_consultation_destination(queue):
    """Resolve the only supported triage-to-consultation mapping.

    MIG-002 has no authority to invent a cross-department destination.  The
    source department is therefore the destination scope, and the stage must
    explicitly identify consultation work.  Anything else is quarantined for
    PC-050 review.
    """

    department = getattr(queue, "department", None)
    if department is None or queue.current_stage != "CONSULTATION" or queue.queue_type != "TRIAGE":
        return None
    if (
        department.organisation_id != queue.organisation_id
        or department.facility_id != queue.facility_id
    ):
        return None
    return department


def _mig002_consultation_candidates(queue):
    """Return active consultation work competing for a TRIAGED source.

    The source QueueEntry and its Visit are the authority for the destination
    scope.  The query intentionally does not pre-filter facility or patient:
    a row with either value corrupted is evidence for PC-050, not a row that
    can disappear from the migration decision.
    """

    if not queue.visit_id or queue.department_id is None:
        return []
    return list(
        QueueEntry.objects.filter(
            organisation_id=queue.organisation_id,
            visit_id=queue.visit_id,
            queue_type="CONSULTATION",
        ).filter(
            models.Q(state__in=MIG002_ACTIVE_STATES)
            | models.Q(state__isnull=True, status="WAITING")
        )
        .exclude(id=queue.id)
        .order_by("id")
    )


def _mig002_consultation_scope_matches(source, destination):
    """Check the exact Visit/department identity for a mapped destination."""

    return bool(
        destination.organisation_id == source.organisation_id
        and destination.facility_id == source.facility_id
        and destination.visit_id == source.visit_id
        and destination.patient_id == source.patient_id
        and destination.department_id == source.department_id
        and destination.queue_type == "CONSULTATION"
        and destination.status == "WAITING"
        and destination.state in {None, "WAITING"}
    )


def _mig002_classify(queue, *, assessment_ids=None, encounter_ids=None):
    assessment_ids, encounter_ids = (
        _mig002_related_ids(queue)
        if assessment_ids is None or encounter_ids is None
        else (assessment_ids, encounter_ids)
    )
    codes = []
    target_state = MIG002_LEGACY_STATE_MAP.get(queue.status)
    if target_state is None:
        # Unsupported legacy names are evidence, not state classifiers.  In
        # particular ON_HOLD/LWBS/NO_SHOW/EXPIRED must not be guessed into a
        # canonical target merely because the strings look familiar.
        codes.append("UNKNOWN_LEGACY_STATE")
        target_state = None
    if queue.visit_id is None:
        codes.append("MISSING_VISIT")
    else:
        visit = getattr(queue, "visit", None)
        if visit is None or (
            visit.organisation_id != queue.organisation_id
            or visit.facility_id != queue.facility_id
            or visit.patient_id != queue.patient_id
        ):
            codes.append("VISIT_SCOPE_MISMATCH")
    department = getattr(queue, "department", None)
    if department is None or (
        department.organisation_id != queue.organisation_id
        or department.facility_id != queue.facility_id
    ):
        codes.append("DEPARTMENT_SCOPE_MISMATCH")
    if queue.status in MIG002_SUPPORTED_LEGACY_STATES and not str(queue.queue_type or "").strip():
        codes.append("UNKNOWN_DEPARTMENT_WORK_IDENTITY")
    if queue.status in {"WAITING", "CALLED", "CANCELLED", "COMPLETED"} and (
        assessment_ids or encounter_ids
    ):
        codes.append("STATUS_WORK_RECORD_MISMATCH")
    if queue.status == "IN_TRIAGE":
        if queue.current_stage != "TRIAGE" or queue.queue_type != "TRIAGE":
            codes.append("TRIAGE_STAGE_MISMATCH" if queue.current_stage != "TRIAGE" else "UNKNOWN_DEPARTMENT_WORK_IDENTITY")
        if assessment_ids or encounter_ids:
            codes.append("TRIAGE_WORK_RECORD_MISMATCH")
    if queue.status == "TRIAGED":
        if len(assessment_ids) != 1:
            codes.append("TRIAGE_ASSESSMENT_MISMATCH")
        if _mig002_consultation_destination(queue) is None:
            codes.append("UNKNOWN_DEPARTMENT_WORK_IDENTITY")
        if encounter_ids:
            codes.append("TRIAGE_ENCOUNTER_MISMATCH")
        assessment = (
            TriageAssessment.objects.filter(
                organisation_id=queue.organisation_id,
                id=assessment_ids[0],
            ).first()
            if len(assessment_ids) == 1
            else None
        )
        if len(assessment_ids) == 1 and (
            assessment is None
            or assessment.facility_id != queue.facility_id
            or assessment.patient_id != queue.patient_id
            or assessment.queue_entry_id != queue.id
        ):
            codes.append("TRIAGE_SCOPE_MISMATCH")
        elif assessment is not None and assessment.acuity not in {"EMERGENCY", "URGENT", "ROUTINE"}:
            codes.append("TRIAGE_ACUITY_INVALID")
    if queue.status == "IN_CONSULTATION":
        if assessment_ids:
            codes.append("CONSULTATION_TRIAGE_MISMATCH")
        if len(encounter_ids) != 1:
            codes.append("CONSULTATION_ENCOUNTER_MISMATCH")
        else:
            encounter = Encounter.objects.filter(
                organisation_id=queue.organisation_id,
                id=encounter_ids[0],
            ).first()
            if encounter is None or (
                encounter.organisation_id != queue.organisation_id
                or encounter.facility_id != queue.facility_id
                or encounter.patient_id != queue.patient_id
                or encounter.visit_id != queue.visit_id
                or encounter.queue_entry_id != queue.id
            ):
                codes.append("CONSULTATION_SCOPE_MISMATCH")
        if queue.current_stage != "CONSULTATION" or queue.queue_type not in {"CONSULTATION", "CLINICIAN"}:
            codes.append("UNKNOWN_DEPARTMENT_WORK_IDENTITY")
    if queue.status == "COMPLETED" and not str(queue.queue_type or "").strip():
        codes.append("UNKNOWN_DEPARTMENT_WORK_IDENTITY")
    if queue.status == "TRIAGED" and queue.visit_id and _mig002_consultation_destination(queue) is not None:
        active_destinations = _mig002_consultation_candidates(queue)
        same_department = [
            destination
            for destination in active_destinations
            if destination.department_id == queue.department_id
        ]
        matching_destinations = [
            destination
            for destination in same_department
            if _mig002_consultation_scope_matches(queue, destination)
        ]
        if len(matching_destinations) > 1 or len(same_department) > 1:
            codes.append("DUPLICATE_ACTIVE_DESTINATION")
        elif same_department and not matching_destinations:
            codes.append("CONSULTATION_DESTINATION_SCOPE_MISMATCH")
        elif active_destinations and not same_department:
            # MIG-002 has no authority to invent a cross-department
            # consultation destination.  A competing department identity is
            # therefore quarantined instead of being silently reused.
            codes.append("UNKNOWN_DEPARTMENT_WORK_IDENTITY")

        identity = f"MIG-002:CONSULTATION:{queue.id}"
        identity_rows = list(
            QueueEntry.objects.filter(
                organisation_id=queue.organisation_id,
                visit_id=queue.visit_id,
                work_identity=identity,
            )
            .exclude(id=queue.id)
            .order_by("id")
        )
        if identity_rows and not (
            len(identity_rows) == 1
            and _mig002_consultation_scope_matches(queue, identity_rows[0])
        ):
            codes.append("CONSULTATION_DESTINATION_SCOPE_MISMATCH")
    # A newly added state column may contain NULL/WAITING from an older
    # expand pass. Any other disagreement is durable drift and must be
    # reconciled rather than silently repaired by a model save.
    if (
        target_state is not None
        and queue.state not in {None, "WAITING", target_state}
    ):
        codes.append("LEGACY_CANONICAL_STATE_MISMATCH")
    return sorted(set(codes)), target_state, assessment_ids, encounter_ids


def _mig002_population(*, organisation, facility_id=None):
    # Rows created by MIG-002 backfill or its Visit-linked rollback writer are
    # target/compatibility rows, not additional legacy source population.
    # Excluding both identities keeps L_queue stable across backfill, rollback,
    # and a later migration evidence scan.
    queryset = QueueEntry.objects.filter(organisation=organisation)
    for prefix in MIG002_TARGET_WORK_IDENTITY_PREFIXES:
        queryset = queryset.exclude(work_identity__startswith=prefix)
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    return queryset.select_related("visit", "department").order_by("id")


def _mig002_switch(organisation, *, phase="EXPANDED"):
    switch, _ = MigrationCutover.objects.select_for_update().get_or_create(
        organisation_id=getattr(organisation, "id", organisation),
        migration_id=MIG002_ID,
        defaults={
            "phase": phase,
            "target_reads_enabled": False,
            "target_writes_enabled": False,
        },
    )
    return switch


def _mig002_record_exception(*, queue, codes, source_hash, target_refs=None, run_id=None):
    evidence, created = MigrationReconciliation.objects.get_or_create(
        organisation_id=queue.organisation_id,
        migration_id=MIG002_ID,
        legacy_table=MIG002_LEGACY_TABLE,
        legacy_pk=str(queue.id),
        defaults={
            "facility_id": queue.facility_id,
            "evidence_codes": sorted(set(codes)),
            "proposed_target_refs": target_refs,
            "source_hash": source_hash,
            "target_hash": _stable_hash({"source_hash": source_hash, "target_refs": target_refs}),
            "backfill_run_id": run_id,
        },
    )
    if not created:
        evidence.facility_id = queue.facility_id
        evidence.evidence_codes = sorted(set(codes))
        evidence.proposed_target_refs = target_refs
        evidence.source_hash = source_hash
        evidence.target_hash = _stable_hash({"source_hash": source_hash, "target_refs": target_refs})
        evidence.backfill_run_id = run_id
        if evidence.resolution_state == "RESOLVED":
            evidence.resolution_state = "PENDING"
            evidence.resolved_by = None
            evidence.resolved_at = None
            evidence.reason = ""
        evidence.save(
            update_fields=[
                "facility", "evidence_codes", "proposed_target_refs", "source_hash",
                "target_hash", "backfill_run_id", "resolution_state", "resolved_by",
                "resolved_at", "reason", "updated_at",
            ]
        )
    return evidence


def _mig002_snapshot(*, organisation, facility_id=None):
    rows = []
    queues = list(_mig002_population(organisation=organisation, facility_id=facility_id))
    exception_count = 0
    for queue in queues:
        assessment_ids, encounter_ids = _mig002_related_ids(queue)
        codes, _, _, _ = _mig002_classify(
            queue,
            assessment_ids=assessment_ids,
            encounter_ids=encounter_ids,
        )
        exception_count += bool(codes)
        rows.append(
            {
                "legacy_pk": str(queue.id),
                "source_hash": _mig002_source_hash(
                    queue,
                    assessment_ids=assessment_ids,
                    encounter_ids=encounter_ids,
                ),
                "evidence_codes": codes,
            }
        )
    organisation_counts, facility_counts = _scope_counts(queues)
    return {
        "source_count": len(rows),
        "exception_count": exception_count,
        "organisation_counts": organisation_counts,
        "facility_counts": facility_counts,
        "digest": _stable_hash(rows),
        "rows": rows,
    }


def _mig002_target_refs(queue):
    refs = {"queue_id": str(queue.id)}
    if queue.visit_id:
        refs["visit_id"] = str(queue.visit_id)
    destinations = []
    if queue.status == "TRIAGED" and _mig002_consultation_destination(queue) is not None:
        destinations = [
            destination
            for destination in _mig002_consultation_candidates(queue)
            if _mig002_consultation_scope_matches(queue, destination)
        ]
    if len(destinations) == 1:
        destination = destinations[0]
        refs["consultation_queue_id"] = str(destination.id)
    return refs


def _mig002_target_hash(queue):
    return _stable_hash(
        {
            "state": queue.state,
            "work_identity": queue.work_identity,
            "source_event_id": queue.source_event_id,
            "source_stage": queue.source_stage,
            "target_refs": _mig002_target_refs(queue),
        }
    )


def expand_mig002(*, organisation):
    """Record the additive MIG-002 expansion without touching legacy rows."""

    assert_transaction_active()
    switch = _mig002_switch(organisation, phase="EXPANDED")
    switch.phase = "EXPANDED"
    switch.target_reads_enabled = False
    switch.target_writes_enabled = False
    switch.blocker_checks_passed = False
    switch.write_fence += 1
    switch.version += 1
    switch.save(
        update_fields=[
            "phase",
            "target_reads_enabled",
            "target_writes_enabled",
            "blocker_checks_passed",
            "write_fence",
            "version",
            "updated_at",
        ]
    )
    return MigrationSummary(MIG002_ID, "EXPAND", run_id=str(switch.last_run_id or ""))


def _mig002_promote_existing_consultation(destination):
    """Complete target fields on a proven pre-expand destination row.

    A destination that predates the nullable MIG-002 fields can be a valid
    existing work row with ``state`` still NULL.  Reuse it in place and fill
    only the canonical state field; the destination remains part of the
    legacy source population until its own stable-key row is backfilled.
    """

    updates = {}
    if destination.state is None:
        updates["state"] = "WAITING"
    if updates:
        QueueEntry.objects.filter(id=destination.id).update(**updates)
        destination.refresh_from_db()
    return destination


def _mig002_ensure_consultation(queue, *, assessment_ids):
    department = _mig002_consultation_destination(queue)
    if not queue.visit_id or len(assessment_ids) != 1 or department is None:
        return None
    identity = f"MIG-002:CONSULTATION:{queue.id}"
    identity_rows = list(
        QueueEntry.objects.select_for_update().filter(
            organisation_id=queue.organisation_id,
            visit_id=queue.visit_id,
            work_identity=identity,
        )
        .exclude(id=queue.id)
        .order_by("id")
    )
    if identity_rows:
        if len(identity_rows) == 1 and _mig002_consultation_scope_matches(queue, identity_rows[0]):
            return _mig002_promote_existing_consultation(identity_rows[0])
        raise ValueError("MIG-002 consultation destination has invalid scope or state.")

    existing_destinations = [
        destination
        for destination in _mig002_consultation_candidates(queue)
        if destination.department_id == queue.department_id
    ]
    matching_destinations = [
        destination
        for destination in existing_destinations
        if _mig002_consultation_scope_matches(queue, destination)
    ]
    if len(existing_destinations) > 1 or len(matching_destinations) > 1:
        raise ValueError("MIG-002 has duplicate active consultation destinations.")
    if existing_destinations:
        if len(matching_destinations) != 1:
            raise ValueError("MIG-002 consultation destination has invalid scope or state.")
        return _mig002_promote_existing_consultation(matching_destinations[0])
    assessment = TriageAssessment.objects.filter(
        organisation_id=queue.organisation_id,
        facility_id=queue.facility_id,
        id=assessment_ids[0],
    ).first()
    priority = getattr(assessment, "acuity", None) if assessment else None
    if priority not in {"EMERGENCY", "URGENT", "ROUTINE"}:
        raise ValueError("MIG-002 triage evidence has no supported acuity.")
    last = (
        QueueEntry.objects.filter(
            organisation_id=queue.organisation_id,
            facility_id=queue.facility_id,
            queue_date=queue.queue_date,
        )
        .order_by("-sequence")
        .values_list("sequence", flat=True)
        .first()
    )
    sequence = allocate_sequence(
        organisation=queue.organisation_id,
        facility=queue.facility_id,
        sequence_type="QUEUE",
        period_key=queue.queue_date.isoformat(),
        initial_value=(last or 0) + 1,
    )
    try:
        with transaction.atomic():
            destination = QueueEntry.objects.create(
                organisation_id=queue.organisation_id,
                facility_id=queue.facility_id,
                visit_id=queue.visit_id,
                patient_id=queue.patient_id,
                department_id=department.id,
                queue_date=queue.queue_date,
                sequence=sequence,
                queue_type="CONSULTATION",
                work_identity=identity,
                priority=priority,
                visit_type=queue.visit_type,
                status="WAITING",
                state="WAITING",
                current_stage="CONSULTATION",
                source_stage="TRIAGE",
                queue_time=queue.queue_time or now(),
                last_activity_at=queue.updated_at or queue.queue_time or now(),
                source_event_id=f"MIG-002:CONSULTATION:{queue.id}",
            )
    except IntegrityError:
        destination = QueueEntry.objects.select_for_update().filter(
            organisation_id=queue.organisation_id,
            facility_id=queue.facility_id,
            visit_id=queue.visit_id,
            work_identity=identity,
        ).first()
        if destination is None:
            raise
    return destination


def inventory_mig002(*, organisation, facility_id=None, run_id=None):
    """Inventory every QueueEntry and persist only non-PHI exceptions."""

    assert_transaction_active()
    run_id = run_id or uuid4()
    snapshot = _mig002_snapshot(organisation=organisation, facility_id=facility_id)
    for queue in _mig002_population(organisation=organisation, facility_id=facility_id):
        assessment_ids, encounter_ids = _mig002_related_ids(queue)
        codes, _, _, _ = _mig002_classify(
            queue,
            assessment_ids=assessment_ids,
            encounter_ids=encounter_ids,
        )
        if codes:
            _mig002_record_exception(
                queue=queue,
                codes=codes,
                source_hash=_mig002_source_hash(
                    queue,
                    assessment_ids=assessment_ids,
                    encounter_ids=encounter_ids,
                ),
                target_refs=_mig002_target_refs(queue),
                run_id=run_id,
            )
    switch = _mig002_switch(organisation)
    switch.phase = "INVENTORY"
    switch.target_reads_enabled = False
    switch.target_writes_enabled = False
    switch.inventory_completed_at = now()
    switch.inventory_source_count = snapshot["source_count"]
    switch.inventory_digest = snapshot["digest"]
    switch.inventory_organisation_counts = snapshot["organisation_counts"]
    switch.inventory_facility_counts = snapshot["facility_counts"]
    switch.backfill_completed_at = None
    switch.backfill_source_count = 0
    switch.backfill_digest = ""
    switch.backfill_organisation_counts = {}
    switch.backfill_facility_counts = {}
    switch.deterministic_row_evidence = {}
    switch.last_verified_at = None
    switch.parity_digest = ""
    switch.parity_passes = 0
    switch.scope_link_hash_verified = False
    switch.blocker_checks_passed = False
    switch.shadow_read_equal = False
    switch.shadow_read_digest = ""
    switch.stable_full_scan_count = 0
    switch.last_run_id = run_id
    switch.write_fence += 1
    switch.version += 1
    switch.save(
        update_fields=[
            "phase", "target_reads_enabled", "target_writes_enabled", "inventory_completed_at",
            "inventory_source_count", "inventory_digest", "inventory_organisation_counts",
            "inventory_facility_counts", "backfill_completed_at", "backfill_source_count",
            "backfill_digest", "backfill_organisation_counts", "backfill_facility_counts",
            "deterministic_row_evidence", "last_verified_at", "parity_digest", "parity_passes",
            "scope_link_hash_verified", "blocker_checks_passed", "shadow_read_equal",
            "shadow_read_digest", "stable_full_scan_count", "last_run_id", "write_fence",
            "version", "updated_at",
        ]
    )
    return MigrationSummary(
        MIG002_ID,
        "INVENTORY",
        inspected=snapshot["source_count"],
        exceptions=snapshot["exception_count"],
        organisation_counts=snapshot["organisation_counts"],
        facility_counts=snapshot["facility_counts"],
        run_id=str(run_id),
    )


def backfill_mig002(*, organisation, facility_id=None, batch_size=500, after_id=None, run_id=None):
    """Restartable stable-key state backfill and destination convergence."""

    assert_transaction_active()
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    run_id = run_id or uuid4()
    queryset = _mig002_population(organisation=organisation, facility_id=facility_id)
    if after_id:
        queryset = queryset.filter(id__gt=after_id)
    # Lock only the QueueEntry rows. The nullable Visit join cannot take part in
    # a FOR UPDATE, and locking Department/Patient would widen the fence.
    queues = list(queryset.select_for_update(of=("self",))[:batch_size])
    inspected = 0
    backfilled = 0
    exceptions = 0
    for queue in queues:
        inspected += 1
        assessment_ids, encounter_ids = _mig002_related_ids(queue)
        codes, target_state, _, _ = _mig002_classify(
            queue,
            assessment_ids=assessment_ids,
            encounter_ids=encounter_ids,
        )
        source_hash = _mig002_source_hash(
            queue,
            assessment_ids=assessment_ids,
            encounter_ids=encounter_ids,
        )
        if codes:
            exceptions += 1
            _mig002_record_exception(
                queue=queue,
                codes=codes,
                source_hash=source_hash,
                target_refs=_mig002_target_refs(queue),
                run_id=run_id,
            )
            continue
        before = (
            queue.state,
            queue.work_identity,
            queue.source_event_id,
            queue.source_stage,
        )
        work_identity = queue.work_identity or f"MIG-002:QUEUE:{queue.id}"
        source_event_id = queue.source_event_id or f"MIG-002:QUEUE:{queue.id}"
        source_stage = queue.source_stage or queue.current_stage or "RECEPTION"
        # QuerySet.update is intentional: a legacy TRIAGED shadow must not be
        # remapped a second time by QueueEntry.save().
        QueueEntry.objects.filter(id=queue.id).update(
            state=target_state,
            work_identity=work_identity,
            source_event_id=source_event_id,
            source_stage=source_stage,
            last_activity_at=queue.last_activity_at or queue.updated_at or queue.queue_time or now(),
        )
        queue.refresh_from_db()
        if queue.status == "TRIAGED":
            _mig002_ensure_consultation(queue, assessment_ids=assessment_ids)
        if before != (target_state, work_identity, source_event_id, source_stage):
            backfilled += 1

    all_queues = list(_mig002_population(organisation=organisation, facility_id=facility_id))
    snapshot = _mig002_snapshot(organisation=organisation, facility_id=facility_id)
    exception_keys = set(
        MigrationReconciliation.objects.filter(
            organisation=organisation,
            migration_id=MIG002_ID,
            legacy_table=MIG002_LEGACY_TABLE,
            legacy_pk__in=[str(queue.id) for queue in all_queues],
        ).values_list("legacy_pk", flat=True)
    )
    complete = all(
        str(queue.id) in exception_keys
        or (
            queue.state in MIG002_CANONICAL_STATES
            and bool(queue.work_identity)
            and bool(queue.source_event_id)
        )
        for queue in all_queues
    )
    switch = _mig002_switch(organisation)
    deterministic = {}
    for queue in all_queues:
        assessment_ids, encounter_ids = _mig002_related_ids(queue)
        codes, _, _, _ = _mig002_classify(
            queue,
            assessment_ids=assessment_ids,
            encounter_ids=encounter_ids,
        )
        if not codes and queue.state in MIG002_CANONICAL_STATES:
            deterministic[f"{MIG002_LEGACY_TABLE}:{queue.id}"] = {
                "legacy_table": MIG002_LEGACY_TABLE,
                "legacy_pk": str(queue.id),
                "organisation_id": str(queue.organisation_id),
                "facility_id": str(queue.facility_id),
                "source_hash": _mig002_source_hash(
                    queue,
                    assessment_ids=assessment_ids,
                    encounter_ids=encounter_ids,
                ),
                "target_hash": _mig002_target_hash(queue),
                "backfill_run_id": str(run_id),
                "target_refs": _mig002_target_refs(queue),
            }
    persisted = dict(switch.deterministic_row_evidence or {})
    if facility_id:
        persisted.update(deterministic)
    else:
        persisted = deterministic
    unresolved = MigrationReconciliation.objects.filter(
        organisation=organisation,
        migration_id=MIG002_ID,
        resolution_state="PENDING",
    )
    if facility_id:
        unresolved = unresolved.filter(facility_id=facility_id)
    switch.phase = "BACKFILL"
    switch.target_reads_enabled = False
    switch.target_writes_enabled = False
    if complete and not facility_id:
        switch.backfill_completed_at = now()
        switch.backfill_source_count = snapshot["source_count"]
        switch.backfill_digest = snapshot["digest"]
        switch.backfill_organisation_counts = snapshot["organisation_counts"]
        switch.backfill_facility_counts = snapshot["facility_counts"]
    else:
        switch.backfill_completed_at = None
        switch.backfill_source_count = 0
        switch.backfill_digest = ""
        switch.backfill_organisation_counts = {}
        switch.backfill_facility_counts = {}
    switch.deterministic_row_evidence = persisted
    switch.last_verified_at = None
    switch.parity_digest = ""
    switch.parity_passes = 0
    switch.scope_link_hash_verified = False
    switch.blocker_checks_passed = False
    switch.shadow_read_equal = False
    switch.shadow_read_digest = ""
    switch.stable_full_scan_count = 0
    switch.last_run_id = run_id
    switch.write_fence += 1
    switch.version += 1
    switch.save(
        update_fields=[
            "phase", "target_reads_enabled", "target_writes_enabled", "backfill_completed_at",
            "backfill_source_count", "backfill_digest", "backfill_organisation_counts",
            "backfill_facility_counts", "deterministic_row_evidence", "last_verified_at",
            "parity_digest", "parity_passes", "scope_link_hash_verified", "blocker_checks_passed",
            "shadow_read_equal", "shadow_read_digest", "stable_full_scan_count", "last_run_id",
            "write_fence", "version", "updated_at",
        ]
    )
    return MigrationSummary(
        MIG002_ID,
        "BACKFILL",
        inspected=inspected,
        backfilled=backfilled,
        exceptions=exceptions,
        unresolved=unresolved.count(),
        parity_digest=snapshot["digest"],
        organisation_counts=snapshot["organisation_counts"],
        facility_counts=snapshot["facility_counts"],
        run_id=str(run_id),
    )


def verify_mig002(*, organisation, facility_id=None):
    """Run state, scope, uniqueness, and source/target parity gates."""

    assert_transaction_active()
    switch = _mig002_switch(organisation)
    queues = list(_mig002_population(organisation=organisation, facility_id=facility_id))
    reconciliation_query = MigrationReconciliation.objects.filter(
        organisation=organisation,
        migration_id=MIG002_ID,
    )
    if facility_id:
        reconciliation_query = reconciliation_query.filter(facility_id=facility_id)
    evidence_rows = list(reconciliation_query.order_by("id"))
    pending = {
        (evidence.legacy_table, str(evidence.legacy_pk))
        for evidence in evidence_rows
        if evidence.resolution_state == "PENDING"
    }
    unresolved = len(pending)
    row_hashes = []
    scope_ok = True
    shadow_equal = True
    classified = 0
    exceptions = 0
    for queue in queues:
        assessment_ids, encounter_ids = _mig002_related_ids(queue)
        codes, expected_state, _, _ = _mig002_classify(
            queue,
            assessment_ids=assessment_ids,
            encounter_ids=encounter_ids,
        )
        key = (MIG002_LEGACY_TABLE, str(queue.id))
        if codes:
            exceptions += 1
            if key not in pending:
                pending.add(key)
                unresolved += 1
            continue
        classified += 1
        target_refs = _mig002_target_refs(queue)
        target_state_ok = (
            queue.state == expected_state
            and queue.state in MIG002_CANONICAL_STATES
            and bool(queue.work_identity)
            and bool(queue.source_event_id)
        )
        if queue.visit_id:
            visit = queue.visit
            target_state_ok = target_state_ok and visit is not None and (
                visit.organisation_id == queue.organisation_id
                and visit.facility_id == queue.facility_id
                and visit.patient_id == queue.patient_id
            )
        if queue.status == "TRIAGED" and "consultation_queue_id" not in target_refs:
            target_state_ok = False
        if not target_state_ok:
            shadow_equal = False
            if key not in pending:
                pending.add(key)
                unresolved += 1
        else:
            proof = (switch.deterministic_row_evidence or {}).get(
                f"{MIG002_LEGACY_TABLE}:{queue.id}"
            )
            current_source_hash = _mig002_source_hash(
                queue,
                assessment_ids=assessment_ids,
                encounter_ids=encounter_ids,
            )
            if proof is None or proof.get("source_hash") != current_source_hash or proof.get("target_refs") != target_refs:
                shadow_equal = False
                if key not in pending:
                    pending.add(key)
                    unresolved += 1
            row_hashes.append(
                {
                    "queue_id": str(queue.id),
                    "source_hash": current_source_hash,
                    "target_hash": _mig002_target_hash(queue),
                }
            )
        if queue.visit_id and (
            queue.visit is None
            or queue.visit.organisation_id != queue.organisation_id
            or queue.visit.facility_id != queue.facility_id
            or queue.visit.patient_id != queue.patient_id
        ):
            scope_ok = False

    active_duplicates = (
        QueueEntry.objects.filter(
            organisation=organisation,
            visit_id__isnull=False,
            state__in=MIG002_ACTIVE_STATES,
            **({"facility_id": facility_id} if facility_id else {}),
        )
        .values("visit_id", "department_id")
        .annotate(row_count=models.Count("id"))
        .filter(row_count__gt=1)
        .count()
    )
    in_service_duplicates = (
        QueueEntry.objects.filter(
            organisation=organisation,
            visit_id__isnull=False,
            state="IN_SERVICE",
            **({"facility_id": facility_id} if facility_id else {}),
        )
        .values("visit_id")
        .annotate(row_count=models.Count("id"))
        .filter(row_count__gt=1)
        .count()
    )
    if active_duplicates or in_service_duplicates:
        scope_ok = False
        unresolved += active_duplicates + in_service_duplicates
    source_count = len(queues)
    if source_count != classified + exceptions:
        shadow_equal = False
        unresolved += abs(source_count - classified - exceptions)
    parity_digest = _stable_hash(
        {
            "source_count": source_count,
            "classified": classified,
            "exceptions": exceptions,
            "rows": row_hashes,
        }
    )
    stable_full_scan_count = (
        min(2, switch.stable_full_scan_count + 1)
        if switch.parity_digest == parity_digest
        and switch.shadow_read_digest == parity_digest
        and switch.shadow_read_equal == shadow_equal
        else 1
    )
    gates_passed = bool(
        unresolved == 0
        and scope_ok
        and shadow_equal
        and source_count == classified + exceptions
    )
    switch.last_verified_at = now()
    switch.parity_digest = parity_digest
    switch.scope_link_hash_verified = scope_ok
    switch.blocker_checks_passed = gates_passed
    switch.shadow_read_equal = shadow_equal and not unresolved
    switch.shadow_read_digest = parity_digest
    switch.stable_full_scan_count = stable_full_scan_count
    switch.save(
        update_fields=[
            "last_verified_at", "parity_digest", "scope_link_hash_verified",
            "blocker_checks_passed", "shadow_read_equal", "shadow_read_digest",
            "stable_full_scan_count", "updated_at",
        ]
    )
    return MigrationSummary(
        MIG002_ID,
        "VERIFY",
        inspected=source_count,
        exceptions=exceptions,
        unresolved=unresolved,
        linked_visit_count=sum(1 for queue in queues if queue.visit_id),
        parity_digest=parity_digest,
        scope_link_hash_verified=scope_ok,
        blocker_checks_passed=gates_passed,
        shadow_read_equal=shadow_equal and not unresolved,
        shadow_read_digest=parity_digest,
        stable_full_scan_count=stable_full_scan_count,
        run_id=str(switch.last_run_id) if switch.last_run_id else "",
    )


def _require_mig002_database_guards():
    """Verify the owner-installed queue guards without runtime DDL.

    The application role has DML privileges only. Creating the constraints or a
    global NOT NULL here would either fail or impose one tenant's cutover on
    every other organisation, so activation only verifies what the schema owner
    installed in ``scheduling.0007_s02_queue_database_guards``.

    The check is bound to the target table OID and rejects objects that exist
    but are unusable: an unvalidated CHECK, an invalid or not-ready index, or a
    state trigger that is disabled for normal application writes.
    """

    if connection.vendor != "postgresql":
        return
    missing = []
    with connection.cursor() as cursor:
        cursor.execute("SELECT 'scheduling_queueentry'::regclass::oid")
        table_oid = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = %s
              AND contype = 'c'
              AND convalidated
              AND conname IN ('queue_entry_state_valid', 'queue_entry_attempt_counts_nonnegative')
            """,
            [table_oid],
        )
        present_constraints = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            """
            SELECT c.relname FROM pg_index i
            JOIN pg_class c ON c.oid = i.indexrelid
            WHERE i.indrelid = %s
              AND i.indisunique
              AND i.indisvalid
              AND i.indisready
              AND c.relname IN ('uniq_active_queue_visit_department', 'uniq_in_service_queue_visit')
            """,
            [table_oid],
        )
        present_indexes = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            """
            SELECT tgname FROM pg_trigger
            WHERE tgrelid = %s
              AND tgname = 'klin_klink_queue_state'
              AND NOT tgisinternal
              AND tgenabled = 'O'
            """,
            [table_oid],
        )
        present_triggers = {row[0] for row in cursor.fetchall()}
    for name in ("queue_entry_state_valid", "queue_entry_attempt_counts_nonnegative"):
        if name not in present_constraints:
            missing.append(name)
    for name in ("uniq_active_queue_visit_department", "uniq_in_service_queue_visit"):
        if name not in present_indexes:
            missing.append(name)
    if "klin_klink_queue_state" not in present_triggers:
        missing.append("klin_klink_queue_state")
    if missing:
        raise ValueError(
            "MIG-002 database guards are missing or unusable ("
            + ", ".join(sorted(missing))
            + "). Apply the owner migration first: "
            "python backend/manage.py migrate scheduling 0007"
        )


def constrain_mig002(*, organisation):
    """Activate semantic database constraints only after E=0 is proven."""

    assert_transaction_active()
    if not _mig001_target_writer_active(organisation):
        raise ValueError("MIG-002 requires an active MIG-001 Visit writer.")
    summary = verify_mig002(organisation=organisation)
    switch = _mig002_switch(organisation)
    if switch.phase not in {"BACKFILL", "CONSTRAINED", "CUTOVER"}:
        raise ValueError("MIG-002 constraints require completed inventory and backfill evidence.")
    unresolved_targets = QueueEntry.objects.filter(
        organisation=organisation,
        state__isnull=True,
    ).exists()
    if (
        summary.unresolved
        or switch.inventory_completed_at is None
        or not switch.inventory_digest
        or switch.backfill_completed_at is None
        or not switch.backfill_digest
        or unresolved_targets
        or not summary.blocker_checks_passed
        or not summary.scope_link_hash_verified
        or not summary.shadow_read_equal
        or summary.stable_full_scan_count < 2
    ):
        raise ValueError("MIG-002 constrain requires E=0 and two stable verification scans.")

    _require_mig002_database_guards()
    # Constrain records that the guards and evidence were verified. Activation
    # belongs to cutover: a tenant that is not already active stays fenced.
    already_active = bool(switch.target_reads_enabled and switch.target_writes_enabled)
    if not already_active:
        switch.phase = "CONSTRAINED"
        switch.target_reads_enabled = False
        switch.target_writes_enabled = False
    switch.blocker_checks_passed = summary.blocker_checks_passed
    switch.write_fence += 1
    switch.version += 1
    switch.save(
        update_fields=[
            "phase",
            "target_reads_enabled",
            "target_writes_enabled",
            "blocker_checks_passed",
            "write_fence",
            "version",
            "updated_at",
        ]
    )
    return MigrationSummary(
        **{
            **summary.as_dict(),
            "phase": "CONSTRAIN",
            "blocker_checks_passed": summary.blocker_checks_passed,
        }
    )


def cutover_mig002(*, organisation, facility_id=None, parity_passes=2):
    """Enable canonical QueueEntry routes only after stable parity gates."""

    assert_transaction_active()
    if not _mig001_target_writer_active(organisation):
        raise ValueError("MIG-002 requires an active MIG-001 Visit writer.")
    if parity_passes < 2:
        raise ValueError("MIG-002 cutover requires two stable parity passes.")
    if facility_id:
        raise ValueError("MIG-002 cutover is organisation-wide; verify without a facility filter.")
    switch = _mig002_switch(organisation)
    if switch.phase == "ROLLBACK":
        raise ValueError("MIG-002 cutover requires a new inventory/backfill cycle after rollback.")
    if switch.inventory_completed_at is None or not switch.inventory_digest:
        raise ValueError("MIG-002 cutover requires durable inventory evidence.")
    if switch.backfill_completed_at is None or not switch.backfill_digest:
        raise ValueError("MIG-002 cutover requires a completed durable backfill.")
    current = _mig002_snapshot(organisation=organisation)
    if (
        current["source_count"] != switch.inventory_source_count
        or current["digest"] != switch.inventory_digest
        or current["source_count"] != switch.backfill_source_count
        or current["digest"] != switch.backfill_digest
    ):
        raise ValueError("MIG-002 inventory/backfill evidence is stale; run the phases again.")
    previous_signature = None
    summary = None
    for _ in range(parity_passes):
        summary = verify_mig002(organisation=organisation)
        if (
            summary.unresolved
            or not summary.scope_link_hash_verified
            or not summary.shadow_read_equal
            or not summary.blocker_checks_passed
        ):
            raise ValueError("MIG-002 cutover is blocked by unresolved state or scope evidence.")
        signature = (
            summary.inspected,
            summary.unresolved,
            summary.parity_digest,
            summary.scope_link_hash_verified,
            summary.shadow_read_equal,
        )
        if previous_signature is not None and signature != previous_signature:
            raise ValueError("MIG-002 parity scans are not stable.")
        previous_signature = signature
    if summary is None or summary.stable_full_scan_count < 2:
        raise ValueError("MIG-002 cutover requires two stable full scans.")
    # The public cutover command is the final gate: callers may omit the
    # separately named constraint phase, but cutover itself must prove and
    # activate the same database constraints before enabling target routes.
    if switch.phase != "CONSTRAINED":
        constrain_mig002(organisation=organisation)
        switch = _mig002_switch(organisation)
    # Activation is the explicit gate: re-verify the installed guards even for
    # a tenant already marked CONSTRAINED, so a disabled or invalid object can
    # never be activated by an earlier verification.
    _require_mig002_database_guards()
    switch.phase = "CUTOVER"
    switch.target_reads_enabled = True
    switch.target_writes_enabled = True
    switch.parity_passes = parity_passes
    switch.write_fence += 1
    switch.version += 1
    switch.save(
        update_fields=[
            "phase", "target_reads_enabled", "target_writes_enabled", "parity_passes",
            "write_fence", "version", "updated_at",
        ]
    )
    return MigrationSummary(
        **{**summary.as_dict(), "phase": "CUTOVER", "parity_passes": parity_passes}
    )


def rollback_mig002(*, organisation, reason, actor=None):
    """Disable target routes while retaining canonical rows and evidence."""

    assert_transaction_active()
    reason = str(reason or "").strip()
    if len(reason) < 3:
        raise ValueError("A rollback reason is required.")
    switch = _mig002_switch(organisation, phase="ROLLBACK")
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
    switch.shadow_read_equal = False
    switch.shadow_read_digest = ""
    switch.stable_full_scan_count = 0
    switch.write_fence += 1
    switch.version += 1
    switch.save(
        update_fields=[
            "phase", "target_reads_enabled", "target_writes_enabled", "rollback_at",
            "rollback_reason", "last_verified_at", "parity_digest", "parity_passes",
            "scope_link_hash_verified", "blocker_checks_passed", "shadow_read_equal",
            "shadow_read_digest", "stable_full_scan_count", "write_fence", "version", "updated_at",
        ]
    )
    if actor is not None:
        record_fact(
            organisation=organisation,
            actor=actor,
            event_code="MIGRATION_ROLLED_BACK",
            action="UPDATE",
            entity_type="MigrationCutover",
            entity_id=switch.id,
            source_ids={"migration_id": MIG002_ID},
            after={"phase": "ROLLBACK", "reason_hash": _stable_hash(reason)},
        )
    return switch


def _locked_migration_switch(organisation, migration_id):
    """Lock a migration fence in the order shared by all queue writers."""

    return MigrationCutover.objects.select_for_update().filter(
        organisation=organisation,
        migration_id=migration_id,
    ).first()


def _mig001_target_writer_active(organisation):
    """Return whether the S-01 Visit writer is the active outer fence."""

    switch = _locked_migration_switch(organisation, MIGRATION_ID)
    return bool(switch is not None and switch.target_writes_enabled)


def target_reads_enabled_mig002(organisation):
    assert_transaction_active()
    # MIG-002 must never expose target reads while the authoritative S-01
    # Visit route is rolled back or has not yet been cut over.
    if not _mig001_target_writer_active(organisation):
        return False
    switch = _locked_migration_switch(organisation, MIG002_ID)
    return bool(switch is not None and switch.target_reads_enabled)


def target_writes_enabled_mig002(organisation):
    """Read the MIG-002 write fence, falling back to the S-01 target on fresh data."""

    assert_transaction_active()
    if not _mig001_target_writer_active(organisation):
        return False
    switch = _locked_migration_switch(organisation, MIG002_ID)
    if switch is not None:
        return bool(switch.target_writes_enabled)
    return True


def legacy_writes_enabled_mig002(organisation):
    assert_transaction_active()
    # MIG-001 owns the legacy-writer decision.  Its rollback must reopen the
    # original writer even if a stale MIG-002 row remains.  MIG-002 may add
    # only its explicit Visit-linked compatibility route while MIG-001 stays
    # on the canonical Visit writer.
    mig001_switch = _locked_migration_switch(organisation, MIGRATION_ID)
    mig001_legacy_enabled = mig001_switch is None or not mig001_switch.target_writes_enabled
    if mig001_legacy_enabled:
        return True
    switch = _locked_migration_switch(organisation, MIG002_ID)
    if switch is None:
        return False
    return bool(
        switch.phase == "ROLLBACK"
        and not switch.target_writes_enabled
    )


def mig002_rollback_active(organisation):
    """Return whether the Visit-linked rollback writer is explicitly active."""

    assert_transaction_active()
    # Keep the same MIG-001 -> MIG-002 lock order used by the writer fence.
    if not _mig001_target_writer_active(organisation):
        return False
    switch = _locked_migration_switch(organisation, MIG002_ID)
    return bool(
        switch is not None
        and switch.phase == "ROLLBACK"
        and not switch.target_writes_enabled
    )


def resolve_mig002_reconciliation(*, organisation, reconciliation_id, actor, reason):
    """Resolve a corrected MIG-002 source only after target convergence."""

    assert_transaction_active()
    reason = str(reason or "").strip()
    if len(reason) < 3:
        raise ValueError("A reconciliation reason is required.")
    evidence = MigrationReconciliation.objects.select_for_update().filter(
        id=reconciliation_id,
        organisation=organisation,
        migration_id=MIG002_ID,
    ).first()
    if evidence is None:
        raise ValueError("MIG-002 evidence was not found in this organisation.")
    queue = QueueEntry.objects.select_for_update(of=("self",)).select_related("visit", "department").filter(
        organisation=organisation,
        id=evidence.legacy_pk,
        **({"facility_id": evidence.facility_id} if evidence.facility_id else {}),
    ).first()
    if queue is None:
        raise ValueError("The QueueEntry source is unavailable; rerun inventory.")
    assessment_ids, encounter_ids = _mig002_related_ids(queue)
    codes, target_state, _, _ = _mig002_classify(
        queue,
        assessment_ids=assessment_ids,
        encounter_ids=encounter_ids,
    )
    if codes:
        raise ValueError("Correct the QueueEntry source before resolving this evidence.")
    work_identity = queue.work_identity or f"MIG-002:QUEUE:{queue.id}"
    source_event_id = queue.source_event_id or f"MIG-002:QUEUE:{queue.id}"
    source_stage = queue.source_stage or queue.current_stage or "RECEPTION"
    # Reconciliation is the explicit owner of the corrected source row. The
    # model save hook must remain inert, so apply the deterministic target
    # fields here before marking the exception resolved.
    QueueEntry.objects.filter(id=queue.id).update(
        state=target_state,
        work_identity=work_identity,
        source_event_id=source_event_id,
        source_stage=source_stage,
        last_activity_at=queue.last_activity_at or queue.updated_at or queue.queue_time or now(),
    )
    queue.refresh_from_db()
    if queue.status == "TRIAGED":
        _mig002_ensure_consultation(queue, assessment_ids=assessment_ids)
    source_hash = _mig002_source_hash(
        queue,
        assessment_ids=assessment_ids,
        encounter_ids=encounter_ids,
    )
    refs = _mig002_target_refs(queue)
    switch = _mig002_switch(organisation)
    snapshot = _mig002_snapshot(organisation=organisation)
    deterministic_evidence = dict(switch.deterministic_row_evidence or {})
    deterministic_evidence[f"{MIG002_LEGACY_TABLE}:{queue.id}"] = {
        "legacy_table": MIG002_LEGACY_TABLE,
        "legacy_pk": str(queue.id),
        "organisation_id": str(queue.organisation_id),
        "facility_id": str(queue.facility_id),
        "source_hash": source_hash,
        "target_hash": _mig002_target_hash(queue),
        "backfill_run_id": str(evidence.backfill_run_id or switch.last_run_id or uuid4()),
        "target_refs": refs,
    }
    evidence.source_hash = source_hash
    evidence.proposed_target_refs = refs
    evidence.target_hash = _stable_hash({"source_hash": source_hash, "target_refs": refs})
    evidence.resolution_state = "RESOLVED"
    evidence.resolved_by = actor
    evidence.resolved_at = now()
    evidence.reason = reason[:240]
    evidence.save(
        update_fields=[
            "source_hash", "proposed_target_refs", "target_hash", "resolution_state",
            "resolved_by", "resolved_at", "reason", "updated_at",
        ]
    )
    switch.inventory_source_count = snapshot["source_count"]
    switch.inventory_digest = snapshot["digest"]
    switch.inventory_organisation_counts = snapshot["organisation_counts"]
    switch.inventory_facility_counts = snapshot["facility_counts"]
    if switch.backfill_completed_at is not None:
        switch.backfill_source_count = snapshot["source_count"]
        switch.backfill_digest = snapshot["digest"]
        switch.backfill_organisation_counts = snapshot["organisation_counts"]
        switch.backfill_facility_counts = snapshot["facility_counts"]
    switch.deterministic_row_evidence = deterministic_evidence
    switch.last_verified_at = None
    switch.parity_digest = ""
    switch.parity_passes = 0
    switch.scope_link_hash_verified = False
    switch.blocker_checks_passed = False
    switch.shadow_read_equal = False
    switch.shadow_read_digest = ""
    switch.stable_full_scan_count = 0
    switch.version += 1
    switch.save(
        update_fields=[
            "inventory_source_count", "inventory_digest", "inventory_organisation_counts",
            "inventory_facility_counts", "backfill_source_count", "backfill_digest",
            "backfill_organisation_counts", "backfill_facility_counts",
            "deterministic_row_evidence", "last_verified_at", "parity_digest",
            "parity_passes", "scope_link_hash_verified", "blocker_checks_passed",
            "shadow_read_equal", "shadow_read_digest", "stable_full_scan_count",
            "version", "updated_at",
        ]
    )
    record_fact(
        organisation=organisation,
        actor=actor,
        event_code="MIGRATION_RECONCILIATION_RESOLVED",
        action="UPDATE",
        entity_type="MigrationReconciliation",
        entity_id=evidence.id,
        source_ids={
            "reconciliation_id": evidence.id,
            "migration_id": MIG002_ID,
            "legacy_table": evidence.legacy_table,
            "legacy_pk": evidence.legacy_pk,
        },
        after={"resolution_state": "RESOLVED", "reason_hash": _stable_hash(reason)},
    )
    return evidence
