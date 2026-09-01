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
