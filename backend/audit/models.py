from django.conf import settings
from django.db import models

from core.models import FacilityScopedModel, OrganisationScopedModel


class AuditEvent(OrganisationScopedModel):
    ACTIONS = [
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("READ", "Read"),
        ("SIGN", "Sign"),
        ("AMEND", "Amend"),
        ("LINK", "Link"),
        ("PAYMENT", "Payment"),
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
        ("EXPORT", "Export"),
    ]

    event_code = models.CharField(max_length=120, default="")
    action = models.CharField(max_length=20, choices=ACTIONS)
    entity_type = models.CharField(max_length=120)
    entity_id = models.CharField(max_length=80)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    facility = models.ForeignKey(
        "tenancy.Facility",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    request_id = models.CharField(max_length=120, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    reason = models.TextField(blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    source_ids = models.JSONField(default=dict)
    reason_code = models.CharField(max_length=80, blank=True)
    denial_identity = models.CharField(max_length=200, null=True, blank=True)
    denial_fingerprint = models.CharField(max_length=64, null=True, blank=True)
    denial_event_code = models.CharField(max_length=120, null=True, blank=True)
    copy_number = models.PositiveIntegerField(null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "event_code", "entity_type", "entity_id", "copy_number"],
                condition=models.Q(copy_number__isnull=False),
                name="uniq_audit_copy_event",
            ),
            models.UniqueConstraint(
                fields=["organisation", "denial_identity"],
                condition=models.Q(denial_identity__isnull=False),
                name="uniq_audit_denial_identity",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not kwargs.get("force_insert"):
            raise ValueError("Audit events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit events are append-only.")
