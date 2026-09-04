from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.schemas import get_schema_view


def health(request):
    return JsonResponse({"status": "ok", "service": "klinklik-api"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health, name="health"),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/tenancy/", include("tenancy.urls")),
    path("api/v1/patients/", include("patients.urls")),
    path("api/v1/reception/", include("application.reception.urls")),
    path("api/v1/clinic/", include("clinical.urls")),
    path("api/v1/billing/", include("billing.urls")),
    path("api/schema/", get_schema_view(title="KlinKlik API", description="KlinKlik Clinic Management API", version="1.0")),
]
