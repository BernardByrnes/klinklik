"""MIG-003: expand/backfill/verify/activate versioned triage records.

The legacy ``TriageAssessment`` remains readable during and after the
migration. MIG-003 creates one completed ``TriageRecord`` head and one
immutable version per clean legacy assessment, records non-PHI evidence for
every source row, and only activates canonical triage writes after the
owner-installed guards and two stable parity scans pass.

The phases mirror MIG-001/MIG-002 and reuse ``MigrationCutover`` and
``MigrationReconciliation``. They are application-role operations: schema
DDL lives in ``clinical.0011_s03_versioned_triage``.
"""

import hashlib
import uuid

from django.db import connection, transaction
from django.db.models import Count

from clinical.models import TriageAssessment, TriageRecord, TriageRecordVersion
from core.clock import now
from core.idempotency import canonical_json
from core.models import MigrationCutover, MigrationReconciliation
from scheduling.models import QueueEntry, Visit

MIG003_ID = "MIG-003"
MIG003_LEGACY_TABLE = "clinical_triageassessment"
MIG003_REQUIRED_VERSION = 1


class Mig003Summary:
    def __init__(
        self,
        *,
        phase,
        inspected=0,
        classified=0,
        exceptions=0,
        unresolved=0,
        target_count=0,
        parity_digest="",
        stable_full_scan_count=0,
        blocker_checks_passed=False,
        run_id=None,
    ):
        self.phase = phase
        self.inspected = inspected
        self.classified = classified
        self.exceptions = exceptions
        self.unresolved = unresolved
        self.target_count = target_count
        self.parity_digest = parity_digest
        self.stable_full_scan_count = stable_full_scan_count
        self.blocker_checks_passed = blocker_checks_passed
        self.run_id = run_id

    def as_dict(self):
        return {
            "migration_id": MIG003_ID,
            "phase": self.phase,
            "inspected": self.inspected,
            "classified": self.classified,
            "exceptions": self.exceptions,
            "unresolved": self.unresolved,
            "target_count": self.target_count,
            "parity_digest": self.parity_digest,
            "stable_full_scan_count": self.stable_full_scan_count,
            "blocker_checks_passed": self.blocker_checks_passed,
            "run_id": str(self.run_id) if self.run_id else "",
        }


def _organisation_id(organisation):
    return getattr(organisation, "id", organisation)


def _digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _switch(organisation, *, phase="EXPANDED"):
    switch, _ = MigrationCutover.objects.get_or_create(
        organisation_id=_organisation_id(organisation),
        migration_id=MIG003_ID,
        defaults={"phase": phase},
    )
    return switch


def target_reads_enabled_mig003(organisation):
    return MigrationCutover.objects.filter(
        organisation_id=_organisation_id(organisation),
        migration_id=MIG003_ID,
        phase__in={"CONSTRAINED", "CUTOVER"},
        target_reads_enabled=True,
    ).exists()


def target_writes_enabled_mig003(organisation):
    return MigrationCutover.objects.filter(
        organisation_id=_organisation_id(organisation),
        migration_id=MIG003_ID,
        phase__in={"CONSTRAINED", "CUTOVER"},
        target_writes_enabled=True,
    ).exists()


def legacy_writes_enabled_mig003(organisation):
    return not target_writes_enabled_mig003(organisation)


def _assessment_population(*, organisation):
    return TriageAssessment.objects.filter(
        organisation_id=_organisation_id(organisation)
    ).order_by("id")


def _assessment_context(assessment):
    """Return the assessment's source queue, Visit, and patient when linked."""

    queue = QueueEntry.objects.filter(
        organisation_id=assessment.organisation_id,
        id=assessment.queue_entry_id,
    ).first()
    visit = None
    if queue is not None and queue.visit_id:
        visit = Visit.objects.filter(
            organisation_id=assessment.organisation_id,
            facility_id=queue.facility_id,
            id=queue.visit_id,
        ).first()
    return queue, visit


def _classify_assessment(assessment, *, competitors):
    """Return ``(evidence_codes,)`` for one legacy assessment.

    PC-050 exceptions are non-PHI codes only. A clean row must link one
    TRIAGED source queue entry to one Visit and patient in the same scope.
    """

    codes = []
    queue, visit = _assessment_context(assessment)
    if queue is None:
        codes.append("MISSING_SOURCE_QUEUE")
        return codes
    if queue.visit_id is None or visit is None:
        codes.append("MISSING_VISIT_LINK")
        return codes
    if queue.facility_id != assessment.facility_id or visit.facility_id != assessment.facility_id:
        codes.append("FACILITY_SCOPE_MISMATCH")
    if queue.organisation_id != assessment.organisation_id or visit.organisation_id != assessment.organisation_id:
        codes.append("ORGANISATION_SCOPE_MISMATCH")
    if queue.patient_id != assessment.patient_id or visit.patient_id != assessment.patient_id:
        codes.append("PATIENT_SCOPE_MISMATCH")
    if str(queue.status or "").upper() != "TRIAGED":
        codes.append("NON_TRIAGED_SOURCE")
    if visit.id in competitors:
        codes.append("COMPETING_ASSESSMENT_FOR_VISIT")
    return codes


def _source_hash(assessment, queue):
    return _digest(
        {
            "migration_id": MIG003_ID,
            "assessment_id": str(assessment.id),
            "organisation_id": str(assessment.organisation_id),
            "facility_id": str(assessment.facility_id),
            "queue_entry_id": str(queue.id),
            "visit_id": str(queue.visit_id),
            "patient_id": str(assessment.patient_id),
            "acuity": assessment.acuity,
            "chief_complaint": assessment.chief_complaint,
            "observations": assessment.observations,
            "assessed_by_id": str(assessment.assessed_by_id),
            "recorded_at": assessment.recorded_at.isoformat(),
        }
    )


def _target_content(assessment, queue):
    complaint_text = str(assessment.chief_complaint or "").strip()
    return {
        "source": MIG003_ID,
        "source_assessment_id": str(assessment.id),
        "source_queue_entry_id": str(queue.id),
        "source_visit_id": str(queue.visit_id),
        "source_patient_id": str(assessment.patient_id),
        "source_status": str(queue.status or ""),
        "acuity": assessment.acuity,
        "presenting_complaints": (
            [{"text": complaint_text, "duration_value": None, "duration_unit": None}]
            if complaint_text
            else []
        ),
        "current_medications": {"medications": [], "chronic_conditions": []},
        "legacy_observations": assessment.observations or {},
        "recorded_by_id": str(assessment.assessed_by_id),
        "recorded_at": assessment.recorded_at.isoformat(),
        "completed_at": assessment.recorded_at.isoformat(),
    }


def _record_exception(*, assessment, codes, source_hash):
    evidence, _ = MigrationReconciliation.objects.update_or_create(
        organisation_id=assessment.organisation_id,
        migration_id=MIG003_ID,
        legacy_table=MIG003_LEGACY_TABLE,
        legacy_pk=str(assessment.id),
        defaults={
            "facility_id": assessment.facility_id,
            "evidence_codes": codes,
            "source_hash": source_hash,
            "target_hash": "",
            "proposed_target_refs": None,
            "resolution_state": "PENDING",
            "resolved_by": None,
            "resolved_at": None,
            "reason": "",
        },
    )
    return evidence


def _competitors_by_visit(*, organisation):
    seen = {}
    competitors = set()
    for assessment in _assessment_population(organisation=organisation).only(
        "id", "queue_entry_id"
    ):
        queue, visit = _assessment_context(assessment)
        if queue is None or visit is None:
            continue
        if visit.id in seen:
            competitors.add(visit.id)
        else:
            seen[visit.id] = assessment.id
    return competitors


def inventory_mig003(*, organisation, facility_id=None):
    """Inventory legacy assessments and record non-PHI exceptions."""

    run_id = uuid.uuid4()
    queryset = _assessment_population(organisation=organisation)
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    competitors = _competitors_by_visit(organisation=organisation)
    inspected = 0
    exceptions = 0
    hashes = []
    for assessment in queryset:
        inspected += 1
        queue, _ = _assessment_context(assessment)
        source_hash = _source_hash(assessment, queue) if queue is not None else ""
        codes = _classify_assessment(assessment, competitors=competitors)
        if codes:
            exceptions += 1
            _record_exception(
                assessment=assessment,
                codes=codes,
                source_hash=source_hash,
            )
        else:
            evidence, created = MigrationReconciliation.objects.get_or_create(
                organisation_id=assessment.organisation_id,
                migration_id=MIG003_ID,
                legacy_table=MIG003_LEGACY_TABLE,
                legacy_pk=str(assessment.id),
                defaults={
                    "facility_id": assessment.facility_id,
                    "evidence_codes": [],
                    "source_hash": source_hash,
                    "resolution_state": "PENDING",
                    "resolved_by": None,
                    "resolved_at": None,
                },
            )
            if not created and evidence.resolution_state != "RESOLVED":
                evidence.facility_id = assessment.facility_id
                evidence.evidence_codes = []
                evidence.source_hash = source_hash
                evidence.save(update_fields=["facility", "evidence_codes", "source_hash"])
            hashes.append((str(assessment.id), source_hash))
    switch = _switch(organisation, phase="EXPANDED")
    switch.phase = "INVENTORY"
    switch.target_reads_enabled = False
    switch.target_writes_enabled = False
    switch.inventory_completed_at = now()
    switch.inventory_source_count = inspected
    switch.inventory_digest = _digest(sorted(hashes))
    switch.backfill_completed_at = None
    switch.backfill_source_count = 0
    switch.backfill_digest = ""
    switch.last_verified_at = None
    switch.parity_digest = ""
    switch.parity_passes = 0
    switch.scope_link_hash_verified = False
    switch.blocker_checks_passed = False
    switch.shadow_read_equal = False
    switch.shadow_read_digest = ""
    switch.stable_full_scan_count = 0
    switch.last_run_id = run_id
    switch.version += 1
    switch.save()
    return Mig003Summary(
        phase="INVENTORY",
        inspected=inspected,
        exceptions=exceptions,
        unresolved=exceptions,
        run_id=run_id,
    )


def _resolved_evidence(assessment):
    return MigrationReconciliation.objects.filter(
        organisation_id=assessment.organisation_id,
        migration_id=MIG003_ID,
        legacy_table=MIG003_LEGACY_TABLE,
        legacy_pk=str(assessment.id),
    ).first()


def backfill_mig003(*, organisation, facility_id=None, batch_size=500, after_id=None):
    """Create one completed head and version per clean legacy assessment."""

    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    run_id = uuid.uuid4()
    queryset = _assessment_population(organisation=organisation)
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    if after_id:
        queryset = queryset.filter(id__gt=after_id)
    assessments = list(queryset[:batch_size])
    competitors = _competitors_by_visit(organisation=organisation)
    backfilled = 0
    exceptions = 0
    for assessment in assessments:
        codes = _classify_assessment(assessment, competitors=competitors)
        queue, _ = _assessment_context(assessment)
        source_hash = _source_hash(assessment, queue) if queue is not None else ""
        if codes:
            exceptions += 1
            _record_exception(assessment=assessment, codes=codes, source_hash=source_hash)
            continue
        evidence = _resolved_evidence(assessment)
        if evidence is not None and evidence.resolution_state == "RESOLVED":
            refs = evidence.proposed_target_refs or {}
            if TriageRecord.objects.filter(
                organisation_id=assessment.organisation_id, id=refs.get("triage_record_id")
            ).exists() and TriageRecordVersion.objects.filter(
                id=refs.get("version_id")
            ).exists():
                continue
        existing = TriageRecord.objects.filter(
            organisation_id=assessment.organisation_id,
            facility_id=assessment.facility_id,
            visit_id=queue.visit_id,
        ).first()
        if existing is not None:
            version = TriageRecordVersion.objects.filter(
                record=existing, version_number=MIG003_REQUIRED_VERSION
            ).first()
            if version is not None and (version.content or {}).get(
                "source_assessment_id"
            ) == str(assessment.id):
                MigrationReconciliation.objects.update_or_create(
                    organisation_id=assessment.organisation_id,
                    migration_id=MIG003_ID,
                    legacy_table=MIG003_LEGACY_TABLE,
                    legacy_pk=str(assessment.id),
                    defaults={
                        "facility_id": assessment.facility_id,
                        "evidence_codes": [],
                        "source_hash": source_hash,
                        "target_hash": version.content_hash,
                        "proposed_target_refs": {
                            "triage_record_id": str(existing.id),
                            "version_id": str(version.id),
                            "version_number": version.version_number,
                        },
                        "resolution_state": "RESOLVED",
                        "resolved_by_id": assessment.assessed_by_id,
                        "resolved_at": assessment.recorded_at,
                        "reason": "MIG-003 deterministic legacy copy",
                    },
                )
                continue
            exceptions += 1
            _record_exception(
                assessment=assessment,
                codes=["COMPETING_TARGET_FOR_VISIT"],
                source_hash=source_hash,
            )
            continue
        content = _target_content(assessment, queue)
        content_hash = _digest(content)
        with transaction.atomic():
            record = TriageRecord.objects.create(
                organisation_id=assessment.organisation_id,
                facility_id=assessment.facility_id,
                visit_id=queue.visit_id,
                patient_id=assessment.patient_id,
                state="COMPLETED",
                acuity=assessment.acuity,
                presenting_complaints=content["presenting_complaints"],
                current_medications=content["current_medications"],
                recorded_by_id=assessment.assessed_by_id,
                completed_by_id=assessment.assessed_by_id,
                completed_at=assessment.recorded_at,
                current_version=MIG003_REQUIRED_VERSION,
                row_version=MIG003_REQUIRED_VERSION,
            )
            version = TriageRecordVersion.objects.create(
                organisation_id=assessment.organisation_id,
                record=record,
                version_number=MIG003_REQUIRED_VERSION,
                content=content,
                content_hash=content_hash,
                reason="MIG-003 legacy assessment",
                created_by_id=assessment.assessed_by_id,
            )
            MigrationReconciliation.objects.update_or_create(
                organisation_id=assessment.organisation_id,
                migration_id=MIG003_ID,
                legacy_table=MIG003_LEGACY_TABLE,
                legacy_pk=str(assessment.id),
                defaults={
                    "facility_id": assessment.facility_id,
                    "evidence_codes": [],
                    "source_hash": source_hash,
                    "target_hash": content_hash,
                    "proposed_target_refs": {
                        "triage_record_id": str(record.id),
                        "version_id": str(version.id),
                        "version_number": MIG003_REQUIRED_VERSION,
                    },
                    "resolution_state": "RESOLVED",
                    "resolved_by_id": assessment.assessed_by_id,
                    "resolved_at": assessment.recorded_at,
                    "reason": "MIG-003 deterministic legacy copy",
                },
            )
        backfilled += 1
    switch = _switch(organisation, phase="BACKFILL")
    switch.phase = "BACKFILL"
    switch.backfill_completed_at = now()
    switch.backfill_source_count = TriageAssessment.objects.filter(
        organisation_id=_organisation_id(organisation)
    ).count()
    switch.backfill_digest = _digest(
        sorted(
            (row.legacy_pk, row.source_hash)
            for row in MigrationReconciliation.objects.filter(
                organisation_id=_organisation_id(organisation),
                migration_id=MIG003_ID,
                resolution_state="RESOLVED",
            )
        )
    )
    switch.last_run_id = run_id
    switch.version += 1
    switch.save()
    return Mig003Summary(
        phase="BACKFILL",
        inspected=len(assessments),
        classified=backfilled,
        exceptions=exceptions,
        run_id=run_id,
    )


def _guard_names():
    if connection.vendor != "postgresql":
        return []
    missing = []
    with connection.cursor() as cursor:
        cursor.execute("SELECT 'clinical_triagerecord'::regclass::oid")
        record_oid = cursor.fetchone()[0]
        cursor.execute("SELECT 'clinical_triagerecordversion'::regclass::oid")
        version_oid = cursor.fetchone()[0]
        cursor.execute("SELECT 'clinical_vitalsobservation'::regclass::oid")
        vitals_oid = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = %s AND convalidated
              AND conname IN ('uniq_triage_record_visit',
                              'triage_record_state_fields_match')
            """,
            [record_oid],
        )
        record_constraints = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = %s AND convalidated
              AND conname = 'uniq_triage_record_version'
            """,
            [version_oid],
        )
        version_constraints = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = %s AND convalidated
              AND conname IN ('vital_observation_content_required')
            """,
            [vitals_oid],
        )
        vitals_constraints = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'clinical_vitalsobservation'
              AND indexname = 'uniq_vitals_visit_context_sequence'
            """
        )
        vitals_indexes = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            """
            SELECT tgname FROM pg_trigger
            WHERE tgrelid IN (%s, %s, %s)
              AND NOT tgisinternal AND tgenabled = 'O'
              AND tgname IN ('klin_klink_triage_record_state',
                             'klin_klink_triage_version_immutable',
                             'klin_klink_vitals_canonical_guard')
            """,
            [record_oid, version_oid, vitals_oid],
        )
        triggers = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE oid IN (%s, %s)
            """,
            [record_oid, version_oid],
        )
        rls = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    if "uniq_triage_record_visit" not in record_constraints:
        missing.append("uniq_triage_record_visit")
    if "triage_record_state_fields_match" not in record_constraints:
        missing.append("triage_record_state_fields_match")
    if "uniq_triage_record_version" not in version_constraints:
        missing.append("uniq_triage_record_version")
    if "uniq_vitals_visit_context_sequence" not in vitals_indexes:
        missing.append("uniq_vitals_visit_context_sequence")
    if "vital_observation_content_required" not in vitals_constraints:
        missing.append("vital_observation_content_required")
    for name in (
        "klin_klink_triage_record_state",
        "klin_klink_triage_version_immutable",
        "klin_klink_vitals_canonical_guard",
    ):
        if name not in triggers:
            missing.append(name)
    for table in ("clinical_triagerecord", "clinical_triagerecordversion"):
        enabled, forced = rls.get(table, (False, False))
        if not enabled or not forced:
            missing.append(f"{table}:force_rls")
    return missing


def _require_mig003_database_guards():
    missing = _guard_names()
    if missing:
        raise ValueError(
            "MIG-003 database guards are missing or unusable ("
            + ", ".join(sorted(missing))
            + "). Apply the owner migration first: "
            "python backend/manage.py migrate clinical 0011"
        )


def verify_mig003(*, organisation, facility_id=None):
    """Verify L_assessment = D_triage + E and stable source/target parity."""

    queryset = _assessment_population(organisation=organisation)
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    competitors = _competitors_by_visit(organisation=organisation)
    inspected = 0
    classified = 0
    exceptions = 0
    unresolved = 0
    parity_rows = []
    for assessment in queryset:
        inspected += 1
        queue, _ = _assessment_context(assessment)
        codes = _classify_assessment(assessment, competitors=competitors)
        recomputed_source = _source_hash(assessment, queue) if queue is not None else ""
        evidence = _resolved_evidence(assessment)
        if codes:
            exceptions += 1
            if evidence is None or evidence.resolution_state != "RESOLVED":
                unresolved += 1
            continue
        if evidence is None or evidence.resolution_state != "RESOLVED":
            unresolved += 1
            continue
        refs = evidence.proposed_target_refs or {}
        target = TriageRecord.objects.filter(
            organisation_id=assessment.organisation_id,
            facility_id=assessment.facility_id,
            id=refs.get("triage_record_id"),
        ).first()
        version = (
            TriageRecordVersion.objects.filter(
                record=target, id=refs.get("version_id")
            ).first()
            if target is not None
            else None
        )
        if target is None or version is None:
            unresolved += 1
            continue
        if evidence.source_hash != recomputed_source:
            unresolved += 1
            continue
        if version.content_hash != _digest(version.content or {}):
            unresolved += 1
            continue
        if version.content_hash != evidence.target_hash:
            unresolved += 1
            continue
        if (version.content or {}).get("source_assessment_id") != str(assessment.id):
            unresolved += 1
            continue
        if (
            target.state != "COMPLETED"
            or target.current_version < MIG003_REQUIRED_VERSION
            or target.completed_at is None
            or target.completed_by_id is None
        ):
            unresolved += 1
            continue
        if str(target.visit_id) != str(queue.visit_id) or str(
            target.patient_id
        ) != str(assessment.patient_id):
            unresolved += 1
            continue
        classified += 1
        parity_rows.append((str(assessment.id), version.content_hash))
    duplicate_visits = (
        TriageRecord.objects.filter(organisation_id=_organisation_id(organisation))
        .values("visit_id")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
        .count()
    )
    if duplicate_visits:
        unresolved += duplicate_visits
    parity_digest = _digest(sorted(parity_rows))
    switch = _switch(organisation, phase="BACKFILL")
    if switch.parity_digest == parity_digest and switch.last_verified_at is not None:
        stable = min(2, switch.stable_full_scan_count + 1)
    else:
        stable = 1
    switch.last_verified_at = now()
    switch.parity_digest = parity_digest
    switch.parity_passes = stable
    switch.stable_full_scan_count = stable
    switch.blocker_checks_passed = unresolved == 0
    switch.shadow_read_equal = unresolved == 0
    switch.shadow_read_digest = parity_digest
    switch.scope_link_hash_verified = unresolved == 0
    switch.version += 1
    switch.save()
    return Mig003Summary(
        phase="VERIFY",
        inspected=inspected,
        classified=classified,
        exceptions=exceptions,
        unresolved=unresolved,
        target_count=TriageRecord.objects.filter(
            organisation_id=_organisation_id(organisation)
        ).count(),
        parity_digest=parity_digest,
        stable_full_scan_count=stable,
        blocker_checks_passed=unresolved == 0,
    )


def constrain_mig003(*, organisation):
    """Record verification and constrain the target without activating it."""

    if target_writes_enabled_mig003(organisation):
        switch = _switch(organisation)
        if switch.phase not in {"CONSTRAINED", "CUTOVER"}:
            raise ValueError("MIG-003 is already active; constrain is not replayed.")
    summary = verify_mig003(organisation=organisation)
    switch = _switch(organisation, phase="BACKFILL")
    if switch.phase not in {"BACKFILL", "CONSTRAINED", "CUTOVER"}:
        raise ValueError("MIG-003 constraints require completed inventory and backfill evidence.")
    if (
        summary.unresolved
        or switch.inventory_completed_at is None
        or not switch.inventory_digest
        or switch.backfill_completed_at is None
        or not switch.backfill_digest
        or summary.stable_full_scan_count < 2
    ):
        raise ValueError("MIG-003 constrain requires E=0 and two stable verification scans.")
    _require_mig003_database_guards()
    already_active = bool(switch.target_reads_enabled and switch.target_writes_enabled)
    if not already_active:
        switch.phase = "CONSTRAINED"
        switch.target_reads_enabled = False
        switch.target_writes_enabled = False
    switch.blocker_checks_passed = summary.blocker_checks_passed
    switch.version += 1
    switch.save()
    return summary


def cutover_mig003(*, organisation, parity_passes=2):
    """Activate canonical triage reads/writes after the guards and E=0."""

    if parity_passes < 2:
        raise ValueError("MIG-003 cutover requires two stable parity passes.")
    switch = _switch(organisation)
    if switch.phase == "ROLLBACK":
        raise ValueError("MIG-003 cutover requires a new inventory/backfill cycle after rollback.")
    if switch.inventory_completed_at is None or not switch.inventory_digest:
        raise ValueError("MIG-003 cutover requires durable inventory evidence.")
    if switch.backfill_completed_at is None or not switch.backfill_digest:
        raise ValueError("MIG-003 cutover requires a completed durable backfill.")
    if switch.phase != "CONSTRAINED":
        constrain_mig003(organisation=organisation)
        switch = _switch(organisation)
    summary = verify_mig003(organisation=organisation)
    if summary.unresolved or summary.stable_full_scan_count < 2:
        raise ValueError("MIG-003 cutover is blocked by unresolved state or scope evidence.")
    _require_mig003_database_guards()
    switch.phase = "CUTOVER"
    switch.target_reads_enabled = True
    switch.target_writes_enabled = True
    switch.parity_passes = parity_passes
    switch.version += 1
    switch.save()
    return summary


def rollback_mig003(*, organisation, reason):
    """Fence canonical writes while retaining every native and migrated row."""

    reason = str(reason or "").strip()
    if len(reason) < 3:
        raise ValueError("A rollback reason is required.")
    switch = _switch(organisation)
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
    switch.version += 1
    switch.save()
    return switch
