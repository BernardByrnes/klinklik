"""Append-only audit facts with a deliberately small safe metadata surface."""

from dataclasses import dataclass
import hashlib
import re

from django.db import IntegrityError, transaction

from audit.models import AuditEvent
from core.clock import now
from core.errors import CanonicalError
from core.idempotency import canonical_json, json_safe, validate_idempotency_key
from core.services import (
    assert_transaction_active,
    consume_post_rollback_boundary,
    tenant_atomic,
)
from core.services import request_id, safe_user_agent


_SAFE_CODE = re.compile(r"^[A-Z][A-Z0-9_.:-]{0,79}$")
_SENSITIVE_KEY = re.compile(
    r"(?:^|_)(?:name|phone|address|email|dob|birth|complaint|diagnos|medicat|"
    r"prescription|result|content|note|symptom|history|amount|price|payment|"
    r"patient|clinical|free_text)(?:_|$)",
    re.IGNORECASE,
)


class DenialAuditConflict(CanonicalError):
    def __init__(self):
        super().__init__(
            "DENIAL_AUDIT_CONFLICT",
            "The denial evidence identity was already used for different evidence.",
            status_code=409,
        )


@dataclass(frozen=True)
class AuditFact:
    event_code: str
    entity_type: str
    entity_id: str
    action: str
    source_ids: dict
    before: object
    after: object
    reason_code: str


def _safe_code(value, label):
    value = str(value or "")
    if not _SAFE_CODE.fullmatch(value):
        raise ValueError(f"{label} must be an uppercase stable code.")
    return value


def _safe_identifier(value, label):
    value = str(value or "")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,119}", value):
        raise ValueError(f"{label} must be a stable identifier.")
    return value


def _safe_opaque_ref(value):
    value = str(value or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", value):
        raise ValueError("opaque_ref must be a stable opaque identifier.")
    return value


def _safe_metadata(value, *, label="metadata", depth=0, allow_identifier_keys=False):
    if depth > 4:
        raise ValueError(f"{label} is too deeply nested.")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > 160:
            raise ValueError(f"{label} contains an unsafe free-text value.")
        return value
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key = str(key)
            identifier_key = allow_identifier_keys and key.lower().endswith("_id")
            if _SENSITIVE_KEY.search(key) and not identifier_key:
                raise ValueError(f"{label} contains a prohibited sensitive field.")
            result[key] = _safe_metadata(
                item,
                label=label,
                depth=depth + 1,
                allow_identifier_keys=allow_identifier_keys,
            )
        return result
    if isinstance(value, (list, tuple)):
        return [
            _safe_metadata(
                item,
                label=label,
                depth=depth + 1,
                allow_identifier_keys=allow_identifier_keys,
            )
            for item in value
        ]
    raise ValueError(f"{label} contains an unsupported value.")


def _identity(
    *,
    organisation,
    actor_id,
    facility_id,
    capability,
    action,
    blocker_type,
    opaque_ref,
    operation,
    authority_epoch,
    request_identity,
    target_identifiers,
):
    return hashlib.sha256(
        canonical_json(
            {
                "organisation_id": str(organisation.id),
                "actor_id": str(actor_id) if actor_id is not None else None,
                "facility_id": str(facility_id) if facility_id is not None else None,
                "capability": capability,
                "action": action,
                "blocker_type": blocker_type,
                "opaque_ref": opaque_ref,
                "operation": operation,
                "authority_epoch": authority_epoch,
                "request_identity": request_identity,
                "target_identifiers": target_identifiers,
            }
        ).encode("utf-8")
    ).hexdigest()


def record_fact(
    *,
    organisation,
    actor=None,
    facility=None,
    event_code,
    action="UPDATE",
    entity_type,
    entity_id,
    source_ids=None,
    before=None,
    after=None,
    reason_code="",
    copy_number=None,
):
    """Write safe, successful-command facts inside the command transaction."""

    assert_transaction_active()
    event_code = _safe_code(event_code, "event_code")
    reason_code = _safe_code(reason_code, "reason_code") if reason_code else ""
    if action not in dict(AuditEvent.ACTIONS):
        raise ValueError("action is not a supported audit action.")
    safe_source_ids = _safe_metadata(
        source_ids or {},
        label="source_ids",
        allow_identifier_keys=True,
    )
    safe_before = _safe_metadata(before, label="before")
    safe_after = _safe_metadata(after, label="after")
    fact = AuditFact(
        event_code=event_code,
        entity_type=str(entity_type),
        entity_id=str(entity_id),
        action=action,
        source_ids=safe_source_ids,
        before=safe_before,
        after=safe_after,
        reason_code=reason_code,
    )
    return AuditEvent.objects.create(
        organisation=organisation,
        actor=actor,
        facility=facility,
        event_code=fact.event_code,
        action=fact.action,
        entity_type=fact.entity_type,
        entity_id=fact.entity_id,
        source_ids=fact.source_ids,
        before=fact.before,
        after=fact.after,
        reason_code=fact.reason_code,
        copy_number=copy_number,
    )


def write_denial_audit(
    *,
    organisation,
    actor_id=None,
    facility_id=None,
    capability,
    action,
    blocker_type,
    opaque_ref,
    request_fingerprint,
    operation="permission.denied",
    authority_epoch=0,
    idempotency_key=None,
    target_identifiers=None,
    denial_request_identity=None,
    event_code="AUTHORIZATION_DENIED",
    denial_event_code=None,
):
    """Persist denial evidence only in a separate post-rollback tenant transaction."""

    if transaction.get_autocommit() is False and not consume_post_rollback_boundary():
        raise RuntimeError("Denial evidence must be written after the refused transaction rolls back.")
    event_code = _safe_code(event_code, "event_code")
    capability = _safe_identifier(capability, "capability")
    action = _safe_code(action, "action")
    blocker_type = _safe_code(blocker_type, "blocker_type")
    opaque_ref = _safe_opaque_ref(opaque_ref)
    operation = _safe_identifier(operation, "operation")
    if not isinstance(authority_epoch, int) or authority_epoch < 0:
        raise ValueError("authority_epoch must be a non-negative integer.")
    if idempotency_key is not None:
        validate_idempotency_key(idempotency_key)
    safe_target_identifiers = _safe_metadata(
        target_identifiers or {},
        label="target_identifiers",
        allow_identifier_keys=True,
    )
    request_identity = denial_request_identity or idempotency_key or f"opaque:{opaque_ref}"
    if not request_identity:
        raise ValueError("A denial request identity is required.")
    denial_event_code = denial_event_code or event_code
    denial_event_code = _safe_code(denial_event_code, "denial_event_code")
    denial_identity = _identity(
        organisation=organisation,
        actor_id=actor_id,
        facility_id=facility_id,
        capability=capability,
        action=action,
        blocker_type=blocker_type,
        opaque_ref=opaque_ref,
        operation=operation,
        authority_epoch=authority_epoch,
        request_identity=request_identity,
        target_identifiers=safe_target_identifiers,
    )
    denial_fingerprint = hashlib.sha256(
        canonical_json(
            {
                "identity": denial_identity,
                "request_fingerprint": str(request_fingerprint),
                "event_code": event_code,
                "denial_event_code": denial_event_code,
            }
        ).encode("utf-8")
    ).hexdigest()
    try:
        with tenant_atomic(organisation.id):
            existing = (
                AuditEvent.objects.select_for_update()
                .filter(organisation=organisation, denial_identity=denial_identity)
                .first()
            )
            if existing is not None:
                if existing.denial_fingerprint != denial_fingerprint:
                    raise DenialAuditConflict()
                return existing
            return AuditEvent.objects.create(
                organisation=organisation,
                actor_id=actor_id,
                facility_id=facility_id,
                event_code=event_code,
                denial_event_code=denial_event_code,
                action="READ",
                entity_type="Authorization",
                entity_id=opaque_ref[:80],
                source_ids={"opaque_ref": opaque_ref},
                reason_code=blocker_type,
                denial_identity=denial_identity,
                denial_fingerprint=denial_fingerprint,
                occurred_at=now(),
            )
    except IntegrityError:
        with tenant_atomic(organisation.id):
            existing = AuditEvent.objects.get(
                organisation=organisation,
                denial_identity=denial_identity,
            )
            if existing.denial_fingerprint != denial_fingerprint:
                raise DenialAuditConflict()
            return existing


def record_event(
    *,
    request=None,
    organisation,
    actor=None,
    action,
    entity_type,
    entity_id,
    facility=None,
    before=None,
    after=None,
    reason="",
    event_code=None,
    source_ids=None,
    reason_code="",
):
    """Compatibility writer for existing owner services."""

    ip_address = None
    rid = ""
    agent = ""
    if request is not None:
        rid = request_id(request)
        agent = safe_user_agent(request)
        ip_address = request.META.get("REMOTE_ADDR")
    return AuditEvent.objects.create(
        organisation=organisation,
        actor=actor,
        action=action,
        event_code=event_code or action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        facility=facility,
        request_id=rid,
        ip_address=ip_address,
        user_agent=agent,
        before=before,
        after=after,
        source_ids=json_safe(source_ids or {}),
        reason_code=reason_code,
        reason=reason,
    )
