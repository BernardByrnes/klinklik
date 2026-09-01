from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

from django.db import DatabaseError, connection, transaction

from core.errors import RetryableCommandFailure


MAX_TRANSACTION_ATTEMPTS = 3
_POST_ROLLBACK_BOUNDARY = ContextVar("post_rollback_boundary", default=False)


def validate_organisation_id(organisation_id):
    try:
        return UUID(str(organisation_id))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("A valid organisation UUID is required before tenant access.") from exc


@contextmanager
def tenant_atomic(organisation_id):
    organisation_id = validate_organisation_id(organisation_id)
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.current_org_id', %s, true)",
                    [str(organisation_id)],
                )
        yield


def assert_transaction_active():
    if not connection.in_atomic_block:
        raise RuntimeError("Tenant-scoped work must run inside tenant_atomic().")


def consume_post_rollback_boundary():
    boundary = _POST_ROLLBACK_BOUNDARY.get()
    _POST_ROLLBACK_BOUNDARY.set(False)
    return boundary


def is_retryable_database_error(error):
    cause = error
    while cause is not None:
        if getattr(cause, "pgcode", None) in {"40001", "40P01"}:
            return True
        cause = getattr(cause, "__cause__", None)
    return False


def run_in_tenant(organisation_id, callback, *, max_attempts=MAX_TRANSACTION_ATTEMPTS):
    """Run the complete callback in one tenant transaction per retry attempt."""

    if max_attempts < 1 or max_attempts > MAX_TRANSACTION_ATTEMPTS:
        raise ValueError(f"max_attempts must be between 1 and {MAX_TRANSACTION_ATTEMPTS}.")
    _POST_ROLLBACK_BOUNDARY.set(False)
    for attempt in range(max_attempts):
        try:
            with tenant_atomic(organisation_id):
                result = callback()
                _POST_ROLLBACK_BOUNDARY.set(False)
                return result
        except DatabaseError as error:
            if connection.vendor != "postgresql" or not is_retryable_database_error(error):
                _POST_ROLLBACK_BOUNDARY.set(True)
                raise
            if attempt + 1 == max_attempts:
                _POST_ROLLBACK_BOUNDARY.set(True)
                raise RetryableCommandFailure() from error
        except BaseException:
            _POST_ROLLBACK_BOUNDARY.set(True)
            raise
    raise AssertionError("The tenant transaction loop must return or raise.")


def request_id(request):
    return request.headers.get("X-Request-Id") or request.META.get("HTTP_X_REQUEST_ID") or ""


def safe_user_agent(request):
    return (request.META.get("HTTP_USER_AGENT") or "")[:300]
