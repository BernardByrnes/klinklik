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
        ("visit.create", "Open patient visits", "T1"),
        ("visit.read", "View visit administration", "T1"),
        ("visit.update_admin", "Update visit administration", "T1"),
        ("visit.cancel_error", "Cancel an erroneous check-in", "T2"),
        ("appointment.no_show_check_in", "Check in a no-show appointment", "T1"),
        ("visit.close", "Close a Visit after the closure checklist clears", "T2"),
        ("visit.payer_reprice", "Reprice an unpaid issued invoice", "T2"),
        ("encounter.read", "View clinical encounter data", "T2"),
        ("queue.view", "View department queue", "T1"),
        ("queue.claim", "Claim queue entries", "T1"),
        ("queue.remove", "Remove pre-service queue work", "T1"),
        ("visit.close_lwbs", "Close a Visit as left without being seen", "T1"),
        ("triage.record", "Record triage", "T1"),
        ("triage.create", "Create and complete triage records", "T1"),
        ("triage.read", "Read triage records", "T1"),
        ("triage.update", "Amend own triage record", "T2"),
        ("triage.amend_any", "Amend any triage record", "T3"),
        ("clinical.note.create", "Create clinical notes", "T1"),
        ("clinical.note.sign", "Sign clinical notes", "T2"),
        ("allergy.manage", "Manage patient allergy state", "T2"),
        ("clinical.note.amend", "Amend clinical notes", "T2"),
        ("billing.invoice.create", "Create invoices", "T1"),
        ("billing.payment.record", "Record payments", "T1"),
        ("billing.receipt.print", "Print receipts", "T1"),
        ("billing.manual_line", "Add manual invoice lines", "T2"),
        ("billing.payment.reverse", "Reverse payments", "T3"),
        ("inventory.read", "View stock balances and ledgers", "T1"),
        ("inventory.receive", "Receive stock", "T1"),
        ("inventory.adjust", "Adjust or write off stock", "T2"),
        ("inventory.configure", "Configure stock locations, suppliers and thresholds", "T2"),
        ("inventory.reconcile", "Run stock ledger reconciliation", "T3"),
        ("inventory.approve", "Approve counts and stock adjustments", "T3"),
        ("lab.order.create", "Create laboratory orders", "T1"),
        ("lab.result.entry", "Enter laboratory results", "T1"),
        ("lab.result.verify", "Verify and release laboratory results", "T2"),
        ("lab.result.amend", "Amend released laboratory results", "T2"),
        ("lab.cancel", "Cancel laboratory items", "T2"),
        ("pharmacy.prescribe", "Create prescription drafts", "T2"),
        ("pharmacy.dispense", "Claim, prepare and hand over prescriptions", "T2"),
        ("pharmacy.otc.sell", "Sell over-the-counter stock", "T1"),
        ("pharmacy.queue.view", "View the pharmacy queue", "T1"),
        ("catalogue.manage", "Manage the medicine catalogue and prices", "T2"),
        ("catalogue.import", "Import a starter catalogue", "T3"),
        ("billing.payment_method.configure", "Configure payment methods", "T3"),
        ("billing.credit_note.issue", "Issue credit notes", "T3"),
        ("billing.credit_note.void", "Void credit notes", "T3"),
        ("billing.refund.request", "Request refunds", "T3"),
        ("billing.refund.approve", "Approve refunds", "T3"),
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
            "visit.create",
            "visit.read",
            "visit.update_admin",
            "visit.cancel_error",
            "appointment.no_show_check_in",
            "visit.close",
            "visit.payer_reprice",
            "queue.view",
            "queue.claim",
            "queue.remove",
            "billing.invoice.create",
            "billing.payment.record",
            "billing.receipt.print",
            "billing.manual_line",
            "pharmacy.otc.sell",
            "pharmacy.queue.view",
        ],
        "NURSE_TRIAGE": [
            "patient.view",
            "visit.create",
            "visit.read",
            "queue.view",
            "queue.claim",
            "queue.remove",
            "triage.record",
            "triage.create",
            "triage.read",
            "allergy.manage",
        ],
        "CLINICIAN": [
            "patient.view",
            "visit.read",
            "encounter.read",
            "queue.view",
            "queue.claim",
            "clinical.note.create",
            "clinical.note.sign",
            "allergy.manage",
            "clinical.note.amend",
            "triage.create",
            "triage.read",
            "pharmacy.prescribe",
            "pharmacy.queue.view",
        ],
        "LAB_TECHNICIAN": ["lab.result.entry"],
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
