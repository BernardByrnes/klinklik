import hashlib
import json

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.idempotency import find_replay, request_hash, save_response
from core.permissions import HasCapability, IsTenantMember, TenantAPIViewMixin
from tenancy.models import Facility


class TenantAPIView(TenantAPIViewMixin, APIView):
    """Tenant-aware APIView with facility resolution and safe mutation retries."""

    permission_classes = [IsAuthenticated, IsTenantMember, HasCapability]

    def initial(self, request, *args, **kwargs):
        self.format_kwarg = self.get_format_suffix(**kwargs)
        request.accepted_renderer, request.accepted_media_type = self.perform_content_negotiation(request)
        self.perform_authentication(request)
        raw_request = getattr(request, "_request", None)
        if raw_request is not None and getattr(request, "_tenant_context", None) is not None:
            raw_request._tenant_context = request._tenant_context
        facility_id = request.headers.get("X-Facility-Id")
        facilities = Facility.objects.filter(organisation=request.organisation, is_active=True)
        if facility_id:
            request.facility = facilities.filter(id=facility_id).first()
            if request.facility is None:
                from rest_framework.exceptions import NotFound

                raise NotFound("Facility is not available in this organisation.")
        else:
            request.facility = facilities.first()
        request.user._request_organisation = request.organisation
        self.check_permissions(request)
        self.check_throttles(request)
        self._idempotency_key = request.headers.get("Idempotency-Key")
        self._idempotency_hash = request_hash(request) if self._idempotency_key else None
        self._idempotency_replay = None
        if self._idempotency_key and request.method in {"POST", "PUT", "PATCH"}:
            try:
                self._idempotency_replay = find_replay(
                    organisation=request.organisation,
                    key=self._idempotency_key,
                    body_hash=self._idempotency_hash,
                )
            except ValueError as exc:
                from rest_framework.exceptions import APIException

                error = APIException(str(exc))
                error.status_code = 409
                raise error

    def dispatch(self, request, *args, **kwargs):
        drf_request = self.initialize_request(request, *args, **kwargs)
        self.request = drf_request
        self.args = args
        self.kwargs = kwargs
        self.headers = self.default_response_headers
        exception = None
        try:
            self.initial(drf_request, *args, **kwargs)
            if self._idempotency_replay is not None:
                response = Response(
                    self._idempotency_replay.response_body,
                    status=self._idempotency_replay.status_code,
                    headers={"Idempotent-Replay": "true"},
                )
            else:
                handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
                response = handler(drf_request, *args, **kwargs)
        except Exception as exc:
            exception = exc
            response = self.handle_exception(exc)
        if (
            exception is None
            and getattr(self, "_idempotency_key", None)
            and getattr(self, "_idempotency_replay", None) is None
            and request.method in {"POST", "PUT", "PATCH"}
            and 200 <= response.status_code < 300
        ):
            save_response(
                organisation=drf_request.organisation,
                key=self._idempotency_key,
                body_hash=self._idempotency_hash,
                status_code=response.status_code,
                response_body=response.data,
            )
        if request.method == "GET" and response.status_code == 200 and getattr(response, "data", None) is not None:
            payload = json.dumps(response.data, default=str, sort_keys=True).encode("utf-8")
            response["ETag"] = '"' + hashlib.sha256(payload).hexdigest() + '"'
        response = self.finalize_response(drf_request, response, *args, **kwargs)
        context = getattr(drf_request, "_tenant_context", None) or getattr(request, "_tenant_context", None)
        if context is not None:
            if exception is None:
                context.__exit__(None, None, None)
            else:
                context.__exit__(type(exception), exception, exception.__traceback__)
            drf_request._tenant_context = None
            if hasattr(request, "_tenant_context"):
                request._tenant_context = None
        return response
