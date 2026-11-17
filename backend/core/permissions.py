"""Actor-scoped queue authorization shared by commands and views.

A grant carries a facility and optionally a department. The permission code may
be the bare capability (any work type in that scope) or a type-qualified code
such as ``queue.call:TRIAGE``. Command handlers and permission checks must use
the same resolved scope so an omitted request filter can never widen what the
actor was granted.

The resolved scope is a set of ``(department, work type)`` pairs, not two
independent axes: a reader granted TRIAGE in department A and CONSULTATION in
department B may read neither A's consultation work nor B's triage work.
"""

from django.db import models
from rest_framework import serializers
from rest_framework.permissions import BasePermission


def coerce_queue_identifier(value):
    """Return the UUID that the request serializers would accept.

    DRF's ``UUIDField`` accepts a UUID instance, an integer, and the hex,
    compact, braced, or URN string forms. A permission check must accept
    exactly the same representations: otherwise a valid identifier could reach
    a command while its department/work-type check was skipped. ``None`` means
    the value is not a valid identifier.
    """

    try:
        return serializers.UUIDField().to_internal_value(value)
    except (TypeError, ValueError, serializers.ValidationError):
        return None


class TenantAPIViewMixin:
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        finally:
            context = getattr(request, "_tenant_context", None)
            if context is not None:
                context.__exit__(None, None, None)
                request._tenant_context = None


class IsTenantMember(BasePermission):
    message = "You are not a member of this organisation."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request, "organisation", None))


class HasCapability(BasePermission):
    capability = None

    def has_permission(self, request, view):
        capability = getattr(view, "capability", None) or self.capability
        if not capability:
            return True
        return request.user.has_capability(capability, getattr(request, "facility", None))


def queue_scope_pairs(*, organisation, facility, user, capabilities):
    """Return the allowed ``(department_id, queue_type)`` pairs for the actor.

    ``None`` means unrestricted (superuser). A pair of ``(None, None)`` means a
    facility-wide grant for every work type; ``(department, None)`` is a
    department-wide grant; ``(None, "TRIAGE")`` is a work type across the
    facility.
    """

    if getattr(user, "is_superuser", False):
        return None
    from accounts.models import RolePermission, UserFacilityRole

    organisation_id = getattr(organisation, "id", organisation)
    facility_id = getattr(facility, "id", facility)
    grants = UserFacilityRole.objects.filter(
        organisation_id=organisation_id,
        user_id=getattr(user, "id", user),
        status="ACTIVE",
    ).filter(
        models.Q(facility_id=facility_id) | models.Q(facility_id__isnull=True)
    )
    codes_by_role = {}
    pairs = set()
    for grant in grants:
        if grant.role_id not in codes_by_role:
            codes_by_role[grant.role_id] = {
                str(code).strip().lower()
                for code in RolePermission.objects.filter(
                    organisation_id=organisation_id,
                    role_id=grant.role_id,
                ).values_list("permission__code", flat=True)
            }
        codes = codes_by_role[grant.role_id]
        department = str(grant.department_id) if grant.department_id else None
        for capability in capabilities:
            normalized = str(capability or "").strip().lower()
            if not normalized:
                continue
            if normalized in codes:
                pairs.add((department, None))
            prefix = f"{normalized}:"
            for code in codes:
                if code.startswith(prefix) and len(code) > len(prefix):
                    pairs.add((department, code[len(prefix):].upper()))
    return sorted(pairs, key=lambda pair: (pair[0] or "", pair[1] or ""))


def scope_allows(pairs, department_id, queue_type):
    """Return whether the resolved scope covers one department/work type.

    ``None`` on either axis means the request did not narrow that axis, so any
    grant on the other axis covers it. The handler still filters candidates by
    the full scope, so an omitted filter can only narrow, never widen.
    """

    if pairs is None:
        return True
    for allowed_department, allowed_type in pairs:
        if (
            department_id is not None
            and allowed_department is not None
            and str(allowed_department) != str(department_id)
        ):
            continue
        if (
            queue_type is not None
            and allowed_type is not None
            and str(allowed_type).upper() != str(queue_type).upper()
        ):
            continue
        return True
    return False


class _UnrestrictedScope:
    """Marker for a resolved scope that narrows nothing.

    The facility/organisation filters are mandatory at every call site, so an
    unrestricted department/work-type condition is safe: it cannot reach
    another tenant or another branch.
    """

    __slots__ = ()

    def __repr__(self):  # pragma: no cover - debugging aid
        return "<queue scope: unrestricted>"


UNRESTRICTED_SCOPE = _UnrestrictedScope()


def scope_query(pairs):
    """Return a queryset filter for the resolved scope, or ``UNRESTRICTED_SCOPE``.

    ``None`` and the facility-wide wildcard pair ``(None, None)`` mean the
    resolver found no department/type restriction. Call sites must skip the
    filter for the sentinel. An empty collection is the opposite case: it
    matches no row. Within one pair the conditions are ANDed and the pairs are
    ORed, so a grant never contributes a second department's work type.
    """

    if pairs is None:
        return UNRESTRICTED_SCOPE
    clauses = []
    for department_id, queue_type in pairs:
        if department_id is None and queue_type is None:
            # A wildcard stays effective even alongside narrower grants.
            return UNRESTRICTED_SCOPE
        clause = models.Q()
        if department_id is not None:
            clause &= models.Q(department_id=department_id)
        if queue_type is not None:
            clause &= models.Q(queue_type=queue_type)
        clauses.append(clause)
    query = models.Q(pk__in=[])
    for clause in clauses:
        query |= clause
    return query


class QueueScopePermission(BasePermission):
    """Check a targeted queue row against the actor's granted department scope."""

    capability = None

    def has_permission(self, request, view):
        capability = (
            getattr(view, "scope_capability", None)
            or getattr(view, "capability", None)
            or self.capability
        )
        if not capability:
            return True
        identifier, supplied = self._target_identifier(request)
        if not supplied:
            # The command owns the missing-identifier contract; nothing is
            # disclosed here.
            return True
        target_id = coerce_queue_identifier(identifier)
        if target_id is None:
            # A malformed or falsey supplied identifier is a request-shape
            # problem. Defer to the command serializer so the caller receives
            # its field-level 400 without a UUID-column lookup or a scope
            # disclosure.
            return True
        from scheduling.models import QueueEntry

        row = QueueEntry.objects.filter(
            organisation_id=request.organisation.id,
            facility_id=request.facility.id,
            id=target_id,
        ).values("department_id", "queue_type").first()
        if row is None:
            return True
        pairs = queue_scope_pairs(
            organisation=request.organisation,
            facility=request.facility,
            user=request.user,
            capabilities=(capability,),
        )
        return scope_allows(pairs, row["department_id"], row["queue_type"])

    @staticmethod
    def _target_identifier(request):
        """Return ``(value, supplied)`` with the route's own target first.

        Presence is checked explicitly so a falsey supplied value (``0``,
        ``""``, ``null``) is not mistaken for an absent identifier. The URL
        target takes precedence for routes scoped by their path.
        """

        parser_context = getattr(request, "parser_context", None) or {}
        kwargs = parser_context.get("kwargs") or {}
        for name in ("pk", "queue_id", "queue_entry_id"):
            if name in kwargs and kwargs[name] is not None:
                return kwargs[name], True
        data = getattr(request, "data", None)
        if data is not None and hasattr(data, "__contains__"):
            for name in ("queue_entry_id", "source_queue_entry_id"):
                if name in data:
                    return data.get(name), True
        return None, False
