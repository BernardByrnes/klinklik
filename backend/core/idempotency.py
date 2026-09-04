"""Transactional idempotency primitives for application commands and APIs."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re

from django.db import IntegrityError, transaction

from core.clock import now
from core.errors import IdempotencyConflict, IdempotencyInProgress
from core.models import IdempotencyRecord
from core.services import assert_transaction_active


IDEMPOTENCY_KEY_MAX_LENGTH = 200
DEFAULT_OPERATION = "legacy"
RESPONSE_SCHEMA_VERSION = "v1"
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")


class UncommittedResponse(Exception):
    """Carries a non-success response out of a transaction that must roll back."""

    def __init__(self, response):
        super().__init__("The response is not a committed idempotent result.")
        self.response = response


@dataclass(frozen=True)
class IdempotencyOutcome:
    value: object
    replay: bool = False
    status_code: int | None = None
    body: object = None
    headers: dict | None = None
    result_reference: object = None


def json_safe(value):
    return json.loads(json.dumps(value, default=str, ensure_ascii=True, allow_nan=False))


def canonical_json(value):
    return json.dumps(
        _normalise(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _normalise(value):
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            raise ValueError("Non-finite numbers are not valid request values.")
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalise(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    if hasattr(value, "items"):
        return _normalise(dict(value.items()))
    return str(value)


def validate_idempotency_key(key):
    if not isinstance(key, str) or not key or len(key) > IDEMPOTENCY_KEY_MAX_LENGTH:
        raise ValueError("Idempotency-Key must be a non-empty value of at most 200 characters.")
    if _CONTROL_CHARACTER.search(key) or key != key.strip():
        raise ValueError("Idempotency-Key contains invalid whitespace or control characters.")
    return key


def key_hash(key):
    return hashlib.sha256(validate_idempotency_key(key).encode("utf-8")).hexdigest()


def fingerprint_for_request(
    *,
    operation,
    organisation_id=None,
    actor=None,
    facility_id=None,
    method=None,
    path=None,
    payload=None,
    target_identifiers=None,
):
    material = {
        "operation": str(operation),
        "organisation_id": str(organisation_id) if organisation_id is not None else None,
        "actor_id": str(getattr(actor, "id", actor)) if actor is not None else None,
        "authority_epoch": getattr(actor, "authority_epoch", 0) if actor is not None else 0,
        "facility_id": str(facility_id) if facility_id is not None else None,
        "method": method or None,
        "path": path or None,
        "target_identifiers": target_identifiers or {},
        "payload": payload if payload is not None else {},
    }
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


def request_operation(request, *, fallback=DEFAULT_OPERATION):
    resolver_match = getattr(request, "resolver_match", None)
    view_name = getattr(resolver_match, "view_name", None)
    operation = getattr(request, "idempotency_operation", None) or view_name or fallback
    return str(operation)[:120]


def request_fingerprint(request, *, operation=None):
    try:
        payload = request.data
    except Exception:
        payload = {"body_sha256": hashlib.sha256(request.body or b"").hexdigest()}
    return fingerprint_for_request(
        operation=operation or request_operation(request),
        organisation_id=getattr(getattr(request, "organisation", None), "id", None),
        actor=getattr(request, "user", None),
        facility_id=getattr(getattr(request, "facility", None), "id", None),
        method=request.method,
        path=request.path,
        payload=payload,
        target_identifiers=(getattr(request, "parser_context", None) or {}).get("kwargs", {}),
    )


def request_hash(request):
    """Compatibility wrapper returning the new canonical request fingerprint."""

    return request_fingerprint(request, operation=DEFAULT_OPERATION)


def claim(*, organisation, operation, key, fingerprint, response_schema_version=RESPONSE_SCHEMA_VERSION):
    """Claim a key inside the caller's outer tenant transaction."""

    assert_transaction_active()
    validate_idempotency_key(key)
    operation = str(operation).strip()
    if not operation or len(operation) > 120:
        raise ValueError("Idempotency operation must be a non-empty value of at most 120 characters.")
    if not re.fullmatch(r"[0-9a-f]{64}", str(fingerprint)):
        raise ValueError("fingerprint must be a lowercase SHA-256 hex digest.")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,32}", str(response_schema_version)):
        raise ValueError("response_schema_version must be a stable version code.")
    hashed_key = key_hash(key)
    organisation_id = getattr(organisation, "id", organisation)
    queryset = IdempotencyRecord.objects.select_for_update()
    try:
        with transaction.atomic():
            record = IdempotencyRecord.objects.create(
                organisation_id=organisation_id,
                operation=operation,
                key_hash=hashed_key,
                fingerprint=fingerprint,
                response_schema_version=response_schema_version,
            )
        return record, False
    except IntegrityError:
        record = queryset.get(
            organisation_id=organisation_id,
            operation=operation,
            key_hash=hashed_key,
        )
        if record.fingerprint != fingerprint or record.response_schema_version != response_schema_version:
            raise IdempotencyConflict()
        if record.completed_at is None or record.status_code is None:
            raise IdempotencyInProgress()
        return record, True


def complete_claim(record, *, status_code, response_body, response_headers=None, result_reference=None):
    assert_transaction_active()
    if not 200 <= status_code < 300:
        raise ValueError("Only successful responses may be committed as idempotent results.")
    if record.completed_at is not None:
        raise ValueError("Completed idempotency records are immutable.")
    record.status_code = status_code
    record.response_body = json_safe(response_body)
    record.response_headers = json_safe(response_headers or {})
    record.result_reference = json_safe(result_reference) if result_reference is not None else None
    record.completed_at = now()
    record.save(
        update_fields=[
            "status_code",
            "response_body",
            "response_headers",
            "result_reference",
            "completed_at",
            "updated_at",
        ]
    )
    return record


def _response_parts(value):
    status_code = int(getattr(value, "status_code", 200))
    body = getattr(value, "idempotency_body", getattr(value, "data", getattr(value, "body", value)))
    response_headers = getattr(value, "headers", None)
    headers = {}
    for name in ("Location", "Content-Type", "ETag"):
        header_value = (
            response_headers.get(name)
            if response_headers is not None
            else getattr(value, "get", lambda *_args: None)(name)
        )
        if header_value:
            headers[name] = str(header_value)
    return status_code, body, headers


def execute_idempotent(
    *,
    organisation,
    operation,
    key,
    fingerprint,
    callback,
    response_schema_version=RESPONSE_SCHEMA_VERSION,
    result_reference=None,
):
    """Run a first-use callback or return the committed result for a replay."""

    record, replay = claim(
        organisation=organisation,
        operation=operation,
        key=key,
        fingerprint=fingerprint,
        response_schema_version=response_schema_version,
    )
    if replay:
        return IdempotencyOutcome(
            value=None,
            replay=True,
            status_code=record.status_code,
            body=record.response_body,
            headers=record.response_headers,
            result_reference=record.result_reference,
        )
    value = callback()
    status_code, body, headers = _response_parts(value)
    if not 200 <= status_code < 300:
        raise UncommittedResponse(value)
    result_reference = (
        result_reference
        if result_reference is not None
        else getattr(value, "result_reference", None)
    )
    complete_claim(
        record,
        status_code=status_code,
        response_body=body,
        response_headers=headers,
        result_reference=result_reference,
    )
    return IdempotencyOutcome(value=value)


def find_replay(*, organisation, key, body_hash, operation=DEFAULT_OPERATION):
    """Legacy lookup retained for callers while all new writes use key hashes."""

    assert_transaction_active()
    try:
        validate_idempotency_key(key)
    except ValueError:
        return None
    record = (
        IdempotencyRecord.objects.select_for_update()
        .filter(
            organisation_id=getattr(organisation, "id", organisation),
            operation=operation,
            key_hash=key_hash(key),
        )
        .first()
    )
    if record is None:
        return None
    if record.fingerprint != body_hash:
        raise IdempotencyConflict()
    if record.completed_at is None or record.status_code is None:
        raise IdempotencyInProgress()
    return record


def save_response(*, organisation, key, body_hash, status_code, response_body, operation=DEFAULT_OPERATION):
    """Legacy completion wrapper; callers must already own the tenant transaction."""

    record, replay = claim(
        organisation=organisation,
        operation=operation,
        key=key,
        fingerprint=body_hash,
    )
    if replay:
        return record
    return complete_claim(
        record,
        status_code=status_code,
        response_body=response_body,
    )
