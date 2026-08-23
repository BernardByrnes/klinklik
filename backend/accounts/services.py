import base64
import hashlib
import hmac
import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import (
    AuthSession,
    OrganisationMembership,
    Permission,
    Role,
    RolePermission,
    UserFacilityRole,
)


def hash_token(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _encode(payload):
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    signature = hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
    return body + "." + signature


def _decode(token):
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(
            settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if int(payload["exp"]) <= int(timezone.now().timestamp()):
            return None
        return payload
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None


def decode_token(token):
    return _decode(token)


@transaction.atomic
def issue_session(user, organisation, rotated_from=None):
    now = timezone.now()
    access_expires = now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    refresh_expires = now + timedelta(days=settings.REFRESH_TOKEN_DAYS)
    session_id = uuid.uuid4()
    access = _encode(
        {
            "sid": str(session_id),
            "sub": str(user.id),
            "org": str(organisation.id),
            "typ": "access",
            "exp": int(access_expires.timestamp()),
        }
    )
    refresh = _encode(
        {
            "sid": str(session_id),
            "sub": str(user.id),
            "org": str(organisation.id),
            "typ": "refresh",
            "exp": int(refresh_expires.timestamp()),
        }
    )
    session = AuthSession.objects.create(
        id=session_id,
        organisation=organisation,
        user=user,
        access_token_hash=hash_token(access),
        refresh_token_hash=hash_token(refresh),
        access_expires_at=access_expires,
        refresh_expires_at=refresh_expires,
        rotated_from=rotated_from,
    )
    return session, access, refresh


def rotate_session(session):
    session.revoked_at = timezone.now()
    session.save(update_fields=["revoked_at", "updated_at"])
    return issue_session(session.user, session.organisation, rotated_from=session)


def revoke_access_token(token):
    token_hash = hash_token(token)
    session = AuthSession.objects.filter(access_token_hash=token_hash, revoked_at__isnull=True).first()
    if session:
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked_at", "updated_at"])


def ensure_default_permissions(organisation):
    definitions = [
        ("patient.view", "View patients", "T1"),
        ("patient.create", "Create patients", "T1"),
        ("patient.edit", "Edit patient demographics", "T2"),
        ("patient.link", "Link suspected duplicate patients", "T3"),
        ("queue.view", "View department queue", "T1"),
        ("queue.claim", "Claim queue entries", "T1"),
        ("triage.record", "Record triage", "T1"),
        ("clinical.note.create", "Create clinical notes", "T1"),
        ("clinical.note.sign", "Sign clinical notes", "T2"),
        ("allergy.manage", "Manage patient allergy state", "T2"),
        ("clinical.note.amend", "Amend clinical notes", "T2"),
        ("billing.invoice.create", "Create invoices", "T1"),
        ("billing.payment.record", "Record payments", "T1"),
        ("billing.receipt.print", "Print receipts", "T1"),
        ("audit.log.view", "View audit logs", "T3"),
        ("staff.permission.grant", "Grant permissions", "T3"),
    ]
    permissions = {}
    for code, name, tier in definitions:
        permission, _ = Permission.objects.get_or_create(
            code=code, defaults={"name": name, "sensitivity_tier": tier}
        )
        permissions[code] = permission
    templates = {
        "OWNER_ADMIN": list(permissions),
        "RECEPTION_CASHIER": [
            "patient.view",
            "patient.create",
            "patient.edit",
            "queue.view",
            "queue.claim",
            "billing.invoice.create",
            "billing.payment.record",
            "billing.receipt.print",
        ],
        "NURSE_TRIAGE": ["patient.view", "queue.view", "queue.claim", "triage.record", "allergy.manage"],
        "CLINICIAN": [
            "patient.view",
            "queue.view",
            "queue.claim",
            "clinical.note.create",
            "clinical.note.sign",
            "allergy.manage",
            "clinical.note.amend",
        ],
    }
    for template_code, codes in templates.items():
        role, _ = Role.objects.get_or_create(
            organisation=organisation,
            template_code=template_code,
            defaults={"name": template_code.replace("_", " ").title(), "is_system": True},
        )
        for code in codes:
            RolePermission.objects.get_or_create(
                organisation=organisation, role=role, permission=permissions[code]
            )
    return permissions


def active_membership(user, organisation):
    return OrganisationMembership.objects.filter(
        user=user, organisation=organisation, status="ACTIVE"
    ).first()


def session_role_context(user, organisation):
    """Role/capability summary attached to session responses.

    Frontend navigation and action gating are UX only; capability enforcement
    remains server-side via HasCapability/User.has_capability.
    """
    grants = (
        UserFacilityRole.objects.filter(
            organisation=organisation, user=user, status="ACTIVE"
        )
        .select_related("role", "facility", "department")
        .order_by("role__name", "id")
    )
    roles = [
        {
            "name": grant.role.name,
            "template_code": grant.role.template_code,
            "facility": str(grant.facility_id) if grant.facility_id else None,
            "department": str(grant.department_id) if grant.department_id else None,
            "department_code": grant.department.code if grant.department_id else None,
        }
        for grant in grants
    ]
    if user.is_superuser:
        capabilities = sorted(set(Permission.objects.values_list("code", flat=True)))
    else:
        capabilities = sorted(
            set(
                RolePermission.objects.filter(
                    organisation=organisation,
                    role_id__in=[grant.role_id for grant in grants],
                ).values_list("permission__code", flat=True)
            )
        )
    return {"roles": roles, "capabilities": capabilities}
