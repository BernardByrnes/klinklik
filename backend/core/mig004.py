"""MIG-004: prove the Visit-linked Encounter and signed note evidence.

The existing Encounter/note tables already carry the canonical target. This
migration pass adds the additive signed-version hash (owner migration 0012),
classifies every Encounter as clean or a PC-050 exception, proves one open
Encounter per Visit and signed-version actor/hash parity, and activates only
after the owner-installed guards pass two stable scans.

It never rewrites a legacy status, invents a signature, pending Lab outcome
or void, or removes a target row.
"""

import hashlib
import uuid

from django.db import connection
from django.db.models import Count

from clinical.models import ClinicalNote, ClinicalNoteVersion, Encounter
from core.clock import now
from core.idempotency import canonical_json
from core.models import MigrationCutover, MigrationReconciliation

MIG004_ID = "MIG-004"
MIG004_LEGACY_TABLE = "clinical_encounter"


class Mig004Summary:
    def __init__(
        self,
        *,
        phase,
        inspected=0,
        classified=0,
        exceptions=0,
        unresolved=0,
        signed_versions=0,
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
        self.signed_versions = signed_versions
        self.parity_digest = parity_digest
        self.stable_full_scan_count = stable_full_scan_count
        self.blocker_checks_passed = blocker_checks_passed
        self.run_id = run_id

    def as_dict(self):
        return {
            "migration_id": MIG004_ID,
            "phase": self.phase,
            "inspected": self.inspected,
            "classified": self.classified,
            "exceptions": self.exceptions,
            "unresolved": self.unresolved,
            "signed_versions": self.signed_versions,
            "parity_digest": self.parity_digest,
            "stable_full_scan_count": self.stable_full_scan_count,
            "blocker_checks_passed": self.blocker_checks_passed,
            "run_id": str(self.run_id) if self.run_id else "",
        }


def _organisation_id(organisation):
    return getattr(organisation, "id", organisation)


def _hash(content):
    return hashlib.sha256(canonical_json(content or {}).encode("utf-8")).hexdigest()


def _switch(organisation, *, phase="EXPANDED"):
    switch, _ = MigrationCutover.objects.get_or_create(
        organisation_id=_organisation_id(organisation),
        migration_id=MIG004_ID,
        defaults={"phase": phase},
    )
    return switch


def target_reads_enabled_mig004(organisation):
    return MigrationCutover.objects.filter(
        organisation_id=_organisation_id(organisation),
        migration_id=MIG004_ID,
        phase__in={"CONSTRAINED", "CUTOVER"},
        target_reads_enabled=True,
    ).exists()


def target_writes_enabled_mig004(organisation):
    return MigrationCutover.objects.filter(
        organisation_id=_organisation_id(organisation),
        migration_id=MIG004_ID,
        phase__in={"CONSTRAINED", "CUTOVER"},
        target_writes_enabled=True,
    ).exists()


def legacy_writes_enabled_mig004(organisation):
    return not target_writes_enabled_mig004(organisation)


def _population(*, organisation, facility_id=None):
    queryset = (
        Encounter.objects.filter(organisation_id=_organisation_id(organisation))
        .select_related("visit", "patient", "clinician")
        .order_by("id")
    )
    if facility_id:
        queryset = queryset.filter(facility_id=facility_id)
    return queryset


def _consultation_note(encounter):
    return ClinicalNote.objects.filter(
        organisation_id=encounter.organisation_id,
        facility_id=encounter.facility_id,
        encounter=encounter,
        note_type="CONSULTATION",
    ).first()


def _current_version(note):
    if note is None or note.current_version < 1:
        return None
    return ClinicalNoteVersion.objects.filter(
        note=note, version_number=note.current_version
    ).first()


def _competitors(*, organisation):
    return set(
        Encounter.objects.filter(
            organisation_id=_organisation_id(organisation),
            visit_id__isnull=False,
            status="OPEN",
        )
        .values("visit_id")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
        .values_list("visit_id", flat=True)
    )


def _classify(encounter, *, competing_visits):
    codes = []
    visit = encounter.visit
    if encounter.visit_id is None or visit is None:
        codes.append("MISSING_VISIT_LINK")
    else:
        if (
            visit.organisation_id != encounter.organisation_id
            or visit.facility_id != encounter.facility_id
        ):
            codes.append("VISIT_SCOPE_MISMATCH")
        if visit.patient_id != encounter.patient_id:
            codes.append("PATIENT_SCOPE_MISMATCH")
        if visit.id in competing_visits:
            codes.append("COMPETING_OPEN_ENCOUNTER")
    note = _consultation_note(encounter)
    version = _current_version(note)
    if encounter.status == "OPEN":
        if note is not None and note.status in {"SIGNED", "AMENDED"}:
            codes.append("OPEN_WITH_SIGNED_NOTE")
    elif encounter.status == "SIGNED":
        if note is None or note.status not in {"SIGNED", "AMENDED"}:
            codes.append("UNPROVEN_SIGNATURE")
        elif note.signed_by_id is None or note.signed_at is None or encounter.signed_at is None:
            codes.append("UNPROVEN_SIGNATURE")
        elif version is None:
            codes.append("MISSING_SIGNED_VERSION")
        elif version.created_by_id != note.signed_by_id:
            codes.append("SIGNED_ACTOR_MISMATCH")
        elif version.content_hash != _hash(version.content):
            codes.append("SIGNED_HASH_MISMATCH")
    elif encounter.status in {"CLOSED", "CANCELLED"}:
        codes.append("LEGACY_TERMINAL_STATUS")
    else:
        codes.append("UNKNOWN_STATUS")
    return codes


def _source_hash(encounter):
    note = _consultation_note(encounter)
    version = _current_version(note)
    return _hash(
        {
            "migration_id": MIG004_ID,
            "encounter_id": str(encounter.id),
            "organisation_id": str(encounter.organisation_id),
            "facility_id": str(encounter.facility_id),
            "visit_id": str(encounter.visit_id) if encounter.visit_id else None,
            "patient_id": str(encounter.patient_id),
            "clinician_id": str(encounter.clinician_id),
            "status": encounter.status,
            "signed_at": encounter.signed_at.isoformat() if encounter.signed_at else None,
            "note_id": str(note.id) if note else None,
            "note_status": note.status if note else None,
            "note_version": version.version_number if version else None,
            "note_hash": version.content_hash if version else None,
        }
    )


def _record(*, encounter, codes, source_hash, resolution_state="PENDING", target_refs=None, target_hash=""):
    resolved = resolution_state == "RESOLVED"
    MigrationReconciliation.objects.update_or_create(
        organisation_id=encounter.organisation_id,
        migration_id=MIG004_ID,
        legacy_table=MIG004_LEGACY_TABLE,
        legacy_pk=str(encounter.id),
        defaults={
            "facility_id": encounter.facility_id,
            "evidence_codes": codes,
            "source_hash": source_hash,
            "target_hash": target_hash,
            "proposed_target_refs": target_refs,
            "resolution_state": resolution_state,
            "resolved_by_id": encounter.clinician_id if resolved else None,
            "resolved_at": (encounter.signed_at or encounter.started_at) if resolved else None,
            "reason": "MIG-004 verified target" if resolved else "",
        },
    )


def inventory_mig004(*, organisation, facility_id=None):
    run_id = uuid.uuid4()
    competing = _competitors(organisation=organisation)
    inspected = 0
    exceptions = 0
    hashes = []
    for encounter in _population(organisation=organisation, facility_id=facility_id):
        inspected += 1
        source_hash = _source_hash(encounter)
        codes = _classify(encounter, competing_visits=competing)
        if codes:
            exceptions += 1
            _record(encounter=encounter, codes=codes, source_hash=source_hash)
        else:
            _record(encounter=encounter, codes=[], source_hash=source_hash)
            hashes.append((str(encounter.id), source_hash))
    switch = _switch(organisation, phase="EXPANDED")
    switch.phase = "INVENTORY"
    switch.target_reads_enabled = False
    switch.target_writes_enabled = False
    switch.inventory_completed_at = now()
    switch.inventory_source_count = inspected
    switch.inventory_digest = _hash(sorted(hashes))
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
    return Mig004Summary(
        phase="INVENTORY",
        inspected=inspected,
        exceptions=exceptions,
        unresolved=exceptions,
        run_id=run_id,
    )


def backfill_mig004(*, organisation, facility_id=None, batch_size=500, after_id=None):
    """Resolve provenance evidence. The owner migration already hashed versions."""

    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    run_id = uuid.uuid4()
    queryset = _population(organisation=organisation, facility_id=facility_id)
    if after_id:
        queryset = queryset.filter(id__gt=after_id)
    encounters = list(queryset[:batch_size])
    competing = _competitors(organisation=organisation)
    resolved = 0
    exceptions = 0
    for encounter in encounters:
        source_hash = _source_hash(encounter)
        codes = _classify(encounter, competing_visits=competing)
        if codes:
            exceptions += 1
            _record(encounter=encounter, codes=codes, source_hash=source_hash)
            continue
        note = _consultation_note(encounter)
        version = _current_version(note)
        _record(
            encounter=encounter,
            codes=[],
            source_hash=source_hash,
            resolution_state="RESOLVED",
            target_refs={
                "encounter_id": str(encounter.id),
                "note_id": str(note.id) if note else None,
                "version_id": str(version.id) if version else None,
                "version_number": version.version_number if version else None,
            },
            target_hash=version.content_hash if version else "",
        )
        resolved += 1
    switch = _switch(organisation, phase="BACKFILL")
    switch.phase = "BACKFILL"
    switch.backfill_completed_at = now()
    switch.backfill_source_count = Encounter.objects.filter(
        organisation_id=_organisation_id(organisation)
    ).count()
    switch.backfill_digest = _hash(
        sorted(
            (row.legacy_pk, row.source_hash)
            for row in MigrationReconciliation.objects.filter(
                organisation_id=_organisation_id(organisation),
                migration_id=MIG004_ID,
                resolution_state="RESOLVED",
            )
        )
    )
    switch.last_run_id = run_id
    switch.version += 1
    switch.save()
    return Mig004Summary(
        phase="BACKFILL",
        inspected=len(encounters),
        classified=resolved,
        exceptions=exceptions,
        run_id=run_id,
    )


def _guard_names():
    if connection.vendor != "postgresql":
        return []
    missing = []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 'clinical_encounter'::regclass::oid, "
            "'clinical_clinicalnoteversion'::regclass::oid"
        )
        encounter_oid, version_oid = cursor.fetchone()
        cursor.execute(
            """
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'clinical_encounter'
              AND indexname = 'uniq_open_encounter_visit'
            """
        )
        if cursor.fetchone() is None:
            missing.append("uniq_open_encounter_visit")
        cursor.execute(
            """
            SELECT conname FROM pg_constraint
            WHERE conrelid = %s AND convalidated
              AND conname = 'note_version_hash_valid'
            """,
            [version_oid],
        )
        if cursor.fetchone() is None:
            missing.append("note_version_hash_valid")
        cursor.execute(
            """
            SELECT tgname FROM pg_trigger
            WHERE tgrelid IN (%s, %s) AND NOT tgisinternal AND tgenabled = 'O'
              AND tgname IN ('klin_klink_note_version_immutable',
                             'klin_klink_encounter_retained')
            """,
            [encounter_oid, version_oid],
        )
        triggers = {row[0] for row in cursor.fetchall()}
        for name in (
            "klin_klink_note_version_immutable",
            "klin_klink_encounter_retained",
        ):
            if name not in triggers:
                missing.append(name)
        cursor.execute(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname IN ('clinical_encounter', 'clinical_clinicalnote',
                              'clinical_clinicalnoteversion')
            """
        )
        for name, enabled, forced in cursor.fetchall():
            if not enabled or not forced:
                missing.append(f"{name}:force_rls")
    return missing


def _require_mig004_database_guards():
    missing = _guard_names()
    if missing:
        raise ValueError(
            "MIG-004 database guards are missing or unusable ("
            + ", ".join(sorted(missing))
            + "). Apply the owner migration first: "
            "python backend/manage.py migrate clinical 0012"
        )


def verify_mig004(*, organisation, facility_id=None):
    queryset = _population(organisation=organisation, facility_id=facility_id)
    competing = _competitors(organisation=organisation)
    inspected = 0
    classified = 0
    exceptions = 0
    unresolved = 0
    signed_versions = 0
    parity_rows = []
    for encounter in queryset:
        inspected += 1
        source_hash = _source_hash(encounter)
        codes = _classify(encounter, competing_visits=competing)
        evidence = MigrationReconciliation.objects.filter(
            organisation_id=encounter.organisation_id,
            migration_id=MIG004_ID,
            legacy_table=MIG004_LEGACY_TABLE,
            legacy_pk=str(encounter.id),
        ).first()
        if codes:
            exceptions += 1
            if evidence is None or evidence.resolution_state != "RESOLVED":
                unresolved += 1
            continue
        if evidence is None or evidence.resolution_state != "RESOLVED":
            unresolved += 1
            continue
        if evidence.source_hash != source_hash:
            unresolved += 1
            continue
        note = _consultation_note(encounter)
        version = _current_version(note)
        if encounter.status == "SIGNED":
            if version is None:
                unresolved += 1
                continue
            if version.content_hash != _hash(version.content):
                unresolved += 1
                continue
            if evidence.target_hash != version.content_hash:
                unresolved += 1
                continue
            if version.created_by_id != note.signed_by_id:
                unresolved += 1
                continue
            signed_versions += 1
        classified += 1
        parity_rows.append(
            (
                str(encounter.id),
                version.content_hash if version is not None else "",
            )
        )
    duplicate_opens = len(competing)
    if duplicate_opens:
        unresolved += duplicate_opens
    parity_digest = _hash(sorted(parity_rows))
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
    return Mig004Summary(
        phase="VERIFY",
        inspected=inspected,
        classified=classified,
        exceptions=exceptions,
        unresolved=unresolved,
        signed_versions=signed_versions,
        parity_digest=parity_digest,
        stable_full_scan_count=stable,
        blocker_checks_passed=unresolved == 0,
    )


def constrain_mig004(*, organisation):
    summary = verify_mig004(organisation=organisation)
    switch = _switch(organisation, phase="BACKFILL")
    if switch.phase not in {"BACKFILL", "CONSTRAINED", "CUTOVER"}:
        raise ValueError("MIG-004 constraints require completed inventory and backfill evidence.")
    if (
        summary.unresolved
        or switch.inventory_completed_at is None
        or not switch.inventory_digest
        or switch.backfill_completed_at is None
        or not switch.backfill_digest
        or summary.stable_full_scan_count < 2
    ):
        raise ValueError("MIG-004 constrain requires E=0 and two stable verification scans.")
    _require_mig004_database_guards()
    already_active = bool(switch.target_reads_enabled and switch.target_writes_enabled)
    if not already_active:
        switch.phase = "CONSTRAINED"
        switch.target_reads_enabled = False
        switch.target_writes_enabled = False
    switch.blocker_checks_passed = summary.blocker_checks_passed
    switch.version += 1
    switch.save()
    return summary


def cutover_mig004(*, organisation, parity_passes=2):
    if parity_passes < 2:
        raise ValueError("MIG-004 cutover requires two stable parity passes.")
    switch = _switch(organisation)
    if switch.phase == "ROLLBACK":
        raise ValueError("MIG-004 cutover requires a new inventory/backfill cycle after rollback.")
    if switch.inventory_completed_at is None or not switch.inventory_digest:
        raise ValueError("MIG-004 cutover requires durable inventory evidence.")
    if switch.backfill_completed_at is None or not switch.backfill_digest:
        raise ValueError("MIG-004 cutover requires a completed durable backfill.")
    if switch.phase != "CONSTRAINED":
        constrain_mig004(organisation=organisation)
        switch = _switch(organisation)
    summary = verify_mig004(organisation=organisation)
    if summary.unresolved or summary.stable_full_scan_count < 2:
        raise ValueError("MIG-004 cutover is blocked by unresolved state or scope evidence.")
    _require_mig004_database_guards()
    switch.phase = "CUTOVER"
    switch.target_reads_enabled = True
    switch.target_writes_enabled = True
    switch.parity_passes = parity_passes
    switch.version += 1
    switch.save()
    return summary


def rollback_mig004(*, organisation, reason):
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
