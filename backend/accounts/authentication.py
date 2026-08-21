from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from accounts.models import AuthSession
from accounts.services import decode_token, hash_token
from core.services import tenant_atomic


class BearerAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header:
            return None
        if header[0].lower() != b"bearer" or len(header) != 2:
            raise AuthenticationFailed("Invalid authorization header.")
        token = header[1].decode("utf-8")
        payload = decode_token(token)
        if not payload or payload.get("typ") != "access":
            raise AuthenticationFailed("Access token is invalid or expired.")
        context = tenant_atomic(payload["org"])
        context.__enter__()
        request._tenant_context = context
        raw_request = getattr(request, "_request", None)
        if raw_request is not None:
            raw_request._tenant_context = context
        try:
            session = AuthSession.objects.select_related("user", "organisation").get(
                organisation_id=payload["org"],
                user_id=payload["sub"],
                access_token_hash=hash_token(token),
                revoked_at__isnull=True,
                access_expires_at__gt=timezone.now(),
            )
        except AuthSession.DoesNotExist as exc:
            context.__exit__(type(exc), exc, exc.__traceback__)
            request._tenant_context = None
            if raw_request is not None:
                raw_request._tenant_context = None
            raise AuthenticationFailed("Access token is revoked or expired.") from exc
        request.organisation = session.organisation
        session.user._request_organisation = session.organisation
        return session.user, session

    def authenticate_header(self, request):
        return "Bearer"
