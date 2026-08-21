import hashlib
import json

from core.models import IdempotencyRecord


def request_hash(request):
    body = request.body or b""
    material = "|".join(
        [
            request.method,
            request.path,
            hashlib.sha256(body).hexdigest(),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def json_safe(value):
    return json.loads(json.dumps(value, default=str))


def find_replay(*, organisation, key, body_hash):
    record = IdempotencyRecord.objects.filter(organisation=organisation, key=key).first()
    if record is None:
        return None
    if record.request_hash != body_hash:
        raise ValueError("The Idempotency-Key was already used for a different request.")
    return record


def save_response(*, organisation, key, body_hash, status_code, response_body):
    return IdempotencyRecord.objects.create(
        organisation=organisation,
        key=key,
        request_hash=body_hash,
        status_code=status_code,
        response_body=json_safe(response_body),
    )
