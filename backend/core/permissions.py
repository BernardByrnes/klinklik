from rest_framework.permissions import BasePermission


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
