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
    key = models.CharField(max_length=200)
    request_hash = models.CharField(max_length=64)
    status_code = models.PositiveSmallIntegerField()
    response_body = models.JSONField(default=dict)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organisation", "key"], name="uniq_idempotency_org_key")
        ]
