from contextlib import contextmanager
from django.db import connection, transaction


@contextmanager
def tenant_atomic(organisation_id):
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL app.current_org_id = %s", [str(organisation_id)])
        yield


def request_id(request):
    return request.headers.get("X-Request-Id") or request.META.get("HTTP_X_REQUEST_ID") or ""


def safe_user_agent(request):
    return (request.META.get("HTTP_USER_AGENT") or "")[:300]
