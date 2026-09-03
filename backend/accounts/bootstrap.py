"""The deliberately small pre-session authentication boundary.

Credential verification uses the global User identity only. Once the password
is accepted, the caller-provided organisation is treated as a candidate and
must prove membership inside a tenant_atomic transaction before any session or
facility data is read or written.
"""

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone

from accounts.models import AuthSession, OrganisationMembership
from accounts.services import (
    active_membership,
    decode_token,
    hash_token,
    issue_session,
    rotate_session,
    session_role_context,
)
from core.services import tenant_atomic
from tenancy.models import Facility, Organisation


class BootstrapError(Exception):
    def __init__(self, detail, status_code):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass
class OpenSession:
    user: object
    organisation: object
    session: object
    access_token: str
    refresh_token: str
    facilities: list
    roles: list
    capabilities: list


def authenticate_identity(request, username, password):
    """Verify only the global credential identity; do not touch tenant tables."""
    user = authenticate(request, username=username, password=password)
    if user is None:
        raise BootstrapError("Invalid credentials.", 401)
    if not user.is_active:
        raise BootstrapError("Account is inactive.", 403)
    return user


def open_session(user, organisation_id):
    """Resolve membership and create a session inside the candidate tenant."""
    is_postgres = settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
    if is_postgres and not organisation_id:
        raise BootstrapError("organisation_id is required when using PostgreSQL.", 400)

    if organisation_id:
        organisation = Organisation.objects.filter(id=organisation_id, status="ACTIVE").first()
        if organisation is None:
            raise BootstrapError("The requested organisation is not active.", 403)
        with tenant_atomic(organisation.id):
            membership = active_membership(user, organisation)
            if membership is None:
                raise BootstrapError("No active organisation membership was found.", 403)
            user._request_organisation = organisation
            session, access, refresh = issue_session(user, organisation)
            facilities = list(Facility.objects.filter(organisation=organisation, is_active=True))
            role_context = session_role_context(user, organisation)
        return OpenSession(
            user,
            organisation,
            session,
            access,
            refresh,
            facilities,
            role_context["roles"],
            role_context["capabilities"],
        )

    # SQLite remains convenient for the existing local unit-test workflow.
    membership = (
        OrganisationMembership.objects.filter(user=user, status="ACTIVE")
        .select_related("organisation")
        .first()
    )
    organisation = membership.organisation if membership else None
    if membership is None or organisation is None:
        raise BootstrapError("No active organisation membership was found.", 403)
    with tenant_atomic(organisation.id):
        membership = active_membership(user, organisation)
        if membership is None:
            raise BootstrapError("No active organisation membership was found.", 403)
        user._request_organisation = organisation
        session, access, refresh = issue_session(user, organisation)
        facilities = list(Facility.objects.filter(organisation=organisation, is_active=True))
        role_context = session_role_context(user, organisation)
    return OpenSession(
        user,
        organisation,
        session,
        access,
        refresh,
        facilities,
        role_context["roles"],
        role_context["capabilities"],
    )


def rotate_refresh_session(refresh_token):
    """Rotate a refresh session only after entering its signed tenant context."""
    payload = decode_token(refresh_token or "")
    if not payload or payload.get("typ") != "refresh":
        raise BootstrapError("Refresh token is invalid or expired.", 401)

    organisation = Organisation.objects.filter(id=payload.get("org"), status="ACTIVE").first()
    if organisation is None:
        raise BootstrapError("Refresh token organisation is invalid.", 401)

    with tenant_atomic(organisation.id):
        session = (
            AuthSession.objects.filter(
                organisation_id=organisation.id,
                refresh_token_hash=hash_token(refresh_token),
                revoked_at__isnull=True,
                refresh_expires_at__gt=timezone.now(),
            )
            .select_related("user", "organisation")
            .first()
        )
        if session is None:
            raise BootstrapError("Refresh token is revoked or expired.", 401)
        session.user._request_organisation = organisation
        rotated, access, new_refresh = rotate_session(session)
        facilities = list(Facility.objects.filter(organisation=organisation, is_active=True))
        role_context = session_role_context(session.user, organisation)
    return OpenSession(
        session.user,
        organisation,
        rotated,
        access,
        new_refresh,
        facilities,
        role_context["roles"],
        role_context["capabilities"],
    )
