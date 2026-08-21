from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.bootstrap import BootstrapError, authenticate_identity, open_session, rotate_refresh_session
from accounts.serializers import LoginSerializer, UserSummarySerializer
from accounts.services import session_role_context
from core.permissions import TenantAPIViewMixin
from tenancy.models import Facility
from tenancy.serializers import FacilitySerializer, OrganisationSerializer


def set_refresh_cookie(response, refresh):
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh,
        max_age=settings.REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="Lax",
        path="/api/v1/auth/",
    )


def bootstrap_error_response(error):
    return Response({"detail": error.detail}, status=error.status_code)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = authenticate_identity(
                request,
                serializer.validated_data["username"].strip().lower(),
                serializer.validated_data["password"],
            )
            opened = open_session(user, serializer.validated_data.get("organisation_id"))
        except BootstrapError as error:
            return bootstrap_error_response(error)

        response = Response(
            {
                "access_token": opened.access_token,
                "access_expires_at": opened.session.access_expires_at,
                "user": UserSummarySerializer(opened.user).data,
                "organisation": OrganisationSerializer(opened.organisation).data,
                "facilities": FacilitySerializer(opened.facilities, many=True).data,
                **session_role_context(opened.user, opened.organisation),
            }
        )
        set_refresh_cookie(response, opened.refresh_token)
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            opened = rotate_refresh_session(
                request.COOKIES.get(settings.REFRESH_COOKIE_NAME, "")
            )
        except BootstrapError as error:
            return bootstrap_error_response(error)

        response = Response(
            {
                "access_token": opened.access_token,
                "access_expires_at": opened.session.access_expires_at,
                "user": UserSummarySerializer(opened.user).data,
                "organisation": OrganisationSerializer(opened.organisation).data,
                "facilities": FacilitySerializer(opened.facilities, many=True).data,
                **session_role_context(opened.user, opened.organisation),
            }
        )
        set_refresh_cookie(response, opened.refresh_token)
        return response


class LogoutView(TenantAPIViewMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.auth:
            request.auth.revoked_at = timezone.now()
            request.auth.save(update_fields=["revoked_at", "updated_at"])
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth/")
        return response


class MeView(TenantAPIViewMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        facilities = Facility.objects.filter(organisation=request.organisation, is_active=True)
        return Response(
            {
                "user": UserSummarySerializer(request.user).data,
                "organisation": OrganisationSerializer(request.organisation).data,
                "facilities": FacilitySerializer(facilities, many=True).data,
                **session_role_context(request.user, request.organisation),
            }
        )
