import hashlib
import json

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.errors import CanonicalError, safe_error_payload
from core.idempotency import (
    UncommittedResponse,
    execute_idempotent,
    request_fingerprint,
    request_operation,
    validate_idempotency_key,
)
from core.permissions import HasCapability, IsTenantMember
from core.services import run_in_tenant, tenant_atomic
from tenancy.models import Facility


class TenantAPIView(APIView):
    """Tenant-aware APIView with one tenant transaction for each handler."""

    permission_classes = [IsAuthenticated, IsTenantMember, HasCapability]
    denial_audit_required = False
    requires_idempotency = False
    idempotency_operation = None
    serializer_class = None
    serializer_classes = None
    response_serializer_class = None
    response_serializer_classes = None

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.serializer_class
        serializer_classes = self.serializer_classes or {}
        method = getattr(getattr(self, "request", None), "method", "").upper()
        serializer_class = serializer_classes.get(method, serializer_class)
        if serializer_class is None:
            return None
        return serializer_class(*args, **kwargs)

    def initial(self, request, *args, **kwargs):
        self.format_kwarg = self.get_format_suffix(**kwargs)
        request.accepted_renderer, request.accepted_media_type = self.perform_content_negotiation(request)
        self.perform_authentication(request)
        with tenant_atomic(request.organisation.id):
            facility_id = request.headers.get("X-Facility-Id")
            facilities = Facility.objects.filter(
                organisation=request.organisation,
                is_active=True,
            )
            if facility_id:
                request.facility = facilities.filter(id=facility_id).first()
                if request.facility is None:
                    from rest_framework.exceptions import NotFound

                    raise NotFound("Facility is not available in this organisation.")
            else:
                request.facility = facilities.first()
            request.user._request_organisation = request.organisation
        self._idempotency_key = request.headers.get("Idempotency-Key")
        if self._idempotency_key:
            try:
                validate_idempotency_key(self._idempotency_key)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
        self._idempotency_operation = self.idempotency_operation or request_operation(
            request, fallback=f"{request.method}:{request.path}"
        )
        self._request_fingerprint = request_fingerprint(
            request,
            operation=self._idempotency_operation,
        )
        self._idempotency_fingerprint = (
            self._request_fingerprint if self._idempotency_key else None
        )

    def _invoke_handler(self, request, *args, **kwargs):
        self.check_permissions(request)
        self.check_throttles(request)
        if self.requires_idempotency and request.method in {"POST", "PUT", "PATCH"} and not self._idempotency_key:
            raise CanonicalError(
                "IDEMPOTENCY_KEY_REQUIRED",
                "This command requires an Idempotency-Key.",
                status_code=400,
            )
        handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
        if not self._idempotency_key or request.method not in {"POST", "PUT", "PATCH"}:
            return handler(request, *args, **kwargs)
        outcome = execute_idempotent(
            organisation=request.organisation,
            operation=self._idempotency_operation,
            key=self._idempotency_key,
            fingerprint=self._idempotency_fingerprint,
            callback=lambda: handler(request, *args, **kwargs),
            replay_callback=(
                getattr(self, "replay_idempotent_response", None)
                if callable(getattr(self, "replay_idempotent_response", None))
                else None
            ),
        )
        if outcome.replay:
            response = Response(
                outcome.body,
                status=outcome.status_code,
                headers=outcome.headers or {},
            )
            response["Idempotent-Replay"] = "true"
            return response
        return outcome.value

    def dispatch(self, request, *args, **kwargs):
        drf_request = self.initialize_request(request, *args, **kwargs)
        self.request = drf_request
        self.args = args
        self.kwargs = kwargs
        self.headers = self.default_response_headers
        try:
            self.initial(drf_request, *args, **kwargs)
            response = run_in_tenant(
                drf_request.organisation.id,
                lambda: self._invoke_handler(drf_request, *args, **kwargs),
            )
        except UncommittedResponse as exc:
            response = exc.response
        except CanonicalError as exc:
            response = Response(safe_error_payload(exc), status=exc.status_code)
        except Exception as exc:
            if isinstance(exc, PermissionDenied) and self.denial_audit_required:
                try:
                    self._write_denial_evidence(drf_request)
                except CanonicalError as denial_error:
                    response = Response(
                        safe_error_payload(denial_error),
                        status=denial_error.status_code,
                    )
                except Exception:
                    response = Response(
                        {
                            "code": "DENIAL_AUDIT_UNAVAILABLE",
                            "detail": "The request could not be completed safely; retry.",
                        },
                        status=503,
                    )
                else:
                    response = self.handle_exception(exc)
            else:
                response = self.handle_exception(exc)
        if (
            request.method == "GET"
            and response.status_code == 200
            and getattr(response, "data", None) is not None
        ):
            payload = json.dumps(response.data, default=str, sort_keys=True).encode("utf-8")
            response["ETag"] = '"' + hashlib.sha256(payload).hexdigest() + '"'
        response = self.finalize_response(drf_request, response, *args, **kwargs)
        return response

    def _write_denial_evidence(self, request):
        if not getattr(request, "organisation", None):
            return
        from audit.services import write_denial_audit

        write_denial_audit(
            organisation=request.organisation,
            actor_id=getattr(request.user, "id", None),
            facility_id=getattr(getattr(request, "facility", None), "id", None),
            capability=getattr(self, "capability", None) or "permission",
            action=request.method,
            blocker_type="PERMISSION",
            opaque_ref=hashlib.sha256(request.path.encode("utf-8")).hexdigest()[:32],
            request_fingerprint=self._request_fingerprint,
            operation=self._idempotency_operation,
            authority_epoch=getattr(request.user, "authority_epoch", 0),
            idempotency_key=self._idempotency_key,
            target_identifiers={
                key: str(value)
                for key, value in getattr(self, "kwargs", {}).items()
            },
        )
