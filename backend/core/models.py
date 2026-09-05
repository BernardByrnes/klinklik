import secrets
import time
import uuid
from django.db import models


def uuid7():
    if hasattr(uuid, "uuid7"):
        return uuid.uuid7()
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    random_a = secrets.randbits(12)
    random_b = secrets.randbits(62)
    value = (timestamp_ms << 80) | (7 << 76) | (random_a << 64) | (0b10 << 62) | random_b
    return uuid.UUID(int=value)


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OrganisationScopedModel(UUIDModel, TimeStampedModel):
    organisation = models.ForeignKey(
        "tenancy.Organisation", on_delete=models.PROTECT, related_name="%(class)s_records"
    )

    class Meta:
        abstract = True


class FacilityScopedModel(OrganisationScopedModel):
    facility = models.ForeignKey(
        "tenancy.Facility", on_delete=models.PROTECT, related_name="%(class)s_records"
    )

    class Meta:
        abstract = True


class IdempotencyRecord(OrganisationScopedModel):
    operation = models.CharField(max_length=120)
    key_hash = models.CharField(max_length=64)
    fingerprint = models.CharField(max_length=64)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(default=dict)
    response_headers = models.JSONField(default=dict)
    response_schema_version = models.CharField(max_length=32, default="v1")
    result_reference = models.JSONField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "operation", "key_hash"],
                name="uniq_idempotency_org_op_key_hash",
            ),
            models.CheckConstraint(
                condition=models.Q(status_code__isnull=True)
                | models.Q(status_code__gte=200, status_code__lte=599),
                name="idempotency_status_code_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(completed_at__isnull=True)
                | models.Q(status_code__isnull=False),
                name="idempotency_completed_has_status",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("completed_at").first()
            if previous and previous["completed_at"] is not None:
                raise ValueError("Completed idempotency records are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Idempotency records are append-only.")


class NumberSequence(OrganisationScopedModel):
    """Locked, tenant-scoped allocator for human-facing references."""

    facility = models.ForeignKey(
        "tenancy.Facility",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="number_sequences",
    )
    scope_key = models.CharField(max_length=120)
    sequence_type = models.CharField(max_length=80)
    period_key = models.CharField(max_length=40)
    next_value = models.PositiveBigIntegerField(default=1)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "scope_key", "sequence_type", "period_key"],
                name="uniq_number_sequence_scope_type_period",
            ),
            models.CheckConstraint(
                condition=models.Q(next_value__gt=0),
                name="number_sequence_next_value_positive",
            ),
        ]


class MigrationReconciliation(OrganisationScopedModel):
    """Non-PHI evidence for a legacy row that needs migration reconciliation."""

    RESOLUTION_STATES = [("PENDING", "Pending"), ("RESOLVED", "Resolved")]

    migration_id = models.CharField(max_length=40)
    facility = models.ForeignKey(
        "tenancy.Facility",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="migration_reconciliation_records",
    )
    legacy_table = models.CharField(max_length=120)
    legacy_pk = models.CharField(max_length=120)
    evidence_codes = models.JSONField(default=list)
    proposed_target_refs = models.JSONField(null=True, blank=True)
    source_hash = models.CharField(max_length=64, blank=True)
    target_hash = models.CharField(max_length=64, blank=True)
    backfill_run_id = models.UUIDField(null=True, blank=True)
    resolution_state = models.CharField(max_length=20, choices=RESOLUTION_STATES, default="PENDING")
    resolved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resolved_migration_reconciliations",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=240, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "migration_id", "legacy_table", "legacy_pk"],
                name="uniq_migration_reconciliation_source",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(resolution_state="PENDING", resolved_by__isnull=True, resolved_at__isnull=True)
                    | models.Q(resolution_state="RESOLVED", resolved_by__isnull=False, resolved_at__isnull=False)
                ),
                name="migration_reconciliation_resolution_fields_match",
            ),
        ]


class MigrationCutover(OrganisationScopedModel):
    """Persistent route switches used by reversible material migrations."""

    migration_id = models.CharField(max_length=40)
    phase = models.CharField(max_length=30, default="EXPANDED")
    target_reads_enabled = models.BooleanField(default=False)
    target_writes_enabled = models.BooleanField(default=False)
    write_fence = models.PositiveBigIntegerField(default=1)
    inventory_completed_at = models.DateTimeField(null=True, blank=True)
    inventory_source_count = models.PositiveBigIntegerField(default=0)
    inventory_digest = models.CharField(max_length=64, blank=True)
    backfill_completed_at = models.DateTimeField(null=True, blank=True)
    backfill_source_count = models.PositiveBigIntegerField(default=0)
    backfill_digest = models.CharField(max_length=64, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    parity_digest = models.CharField(max_length=64, blank=True)
    parity_passes = models.PositiveSmallIntegerField(default=0)
    scope_link_hash_verified = models.BooleanField(default=False)
    blocker_checks_passed = models.BooleanField(default=False)
    inventory_organisation_counts = models.JSONField(default=dict)
    inventory_facility_counts = models.JSONField(default=dict)
    backfill_organisation_counts = models.JSONField(default=dict)
    backfill_facility_counts = models.JSONField(default=dict)
    deterministic_row_evidence = models.JSONField(default=dict)
    shadow_read_equal = models.BooleanField(default=False)
    shadow_read_digest = models.CharField(max_length=64, blank=True)
    stable_full_scan_count = models.PositiveSmallIntegerField(default=0)
    last_run_id = models.UUIDField(null=True, blank=True)
    rollback_at = models.DateTimeField(null=True, blank=True)
    rollback_reason = models.CharField(max_length=240, blank=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "migration_id"],
                name="uniq_migration_cutover_org_id",
            ),
        ]
