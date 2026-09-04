from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

from django.db import DatabaseError, IntegrityError, connection, transaction

from core.errors import RetryableCommandFailure
from core.models import NumberSequence


MAX_TRANSACTION_ATTEMPTS = 3
_RETRYABLE_POSTGRES_SQLSTATES = frozenset({"40001", "40P01"})
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


def allocate_sequence(
    *,
    organisation,
    sequence_type,
    period_key,
    facility=None,
    initial_value=1,
):
    """Allocate one value while holding the canonical sequence row lock."""

    assert_transaction_active()
    if initial_value < 1:
        raise ValueError("initial_value must be positive.")
    organisation_id = getattr(organisation, "id", organisation)
    facility_id = getattr(facility, "id", facility) if facility is not None else None
    scope_key = str(facility_id) if facility_id is not None else "ORG"
    queryset = NumberSequence.objects.select_for_update()
    sequence = queryset.filter(
        organisation_id=organisation_id,
        scope_key=scope_key,
        sequence_type=sequence_type,
        period_key=str(period_key),
    ).first()
    if sequence is None:
        try:
            with transaction.atomic():
                sequence = NumberSequence.objects.create(
                    organisation_id=organisation_id,
                    facility_id=facility_id,
                    scope_key=scope_key,
                    sequence_type=sequence_type,
                    period_key=str(period_key),
                    next_value=initial_value,
                )
        except IntegrityError:
            sequence = queryset.get(
                organisation_id=organisation_id,
                scope_key=scope_key,
                sequence_type=sequence_type,
                period_key=str(period_key),
            )
    if sequence.next_value < initial_value:
        sequence.next_value = initial_value
    allocated = sequence.next_value
    sequence.next_value = allocated + 1
    sequence.version += 1
    sequence.save(update_fields=["next_value", "version", "updated_at"])
    return allocated


def consume_post_rollback_boundary():
    boundary = _POST_ROLLBACK_BOUNDARY.get()
    _POST_ROLLBACK_BOUNDARY.set(False)
    return boundary


def _exception_chain(error):
    seen = set()
    cause = error
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        yield cause
        cause = getattr(cause, "__cause__", None) or getattr(cause, "__context__", None)


def _has_retryable_sqlstate(error):
    if getattr(error, "sqlstate", None) in _RETRYABLE_POSTGRES_SQLSTATES:
        return True
    diagnostic = getattr(error, "diag", None)
    if getattr(diagnostic, "sqlstate", None) in _RETRYABLE_POSTGRES_SQLSTATES:
        return True
    return getattr(error, "pgcode", None) in _RETRYABLE_POSTGRES_SQLSTATES


def is_retryable_database_error(error):
    return any(_has_retryable_sqlstate(cause) for cause in _exception_chain(error))


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
