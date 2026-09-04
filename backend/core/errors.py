"""Canonical, non-sensitive errors shared by application commands and APIs."""


class CanonicalError(Exception):
    """An expected failure with a stable public code and HTTP status."""

    def __init__(self, code, detail, *, status_code=400, retryable=False, metadata=None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code
        self.retryable = retryable
        self.metadata = dict(metadata or {})


class IdempotencyConflict(CanonicalError):
    def __init__(self, detail="The Idempotency-Key was already used for a different request."):
        super().__init__("IDEMPOTENCY_CONFLICT", detail, status_code=409)


class IdempotencyInProgress(CanonicalError):
    def __init__(self):
        super().__init__(
            "IDEMPOTENCY_IN_PROGRESS",
            "The idempotent request is still being completed; retry with the same key.",
            status_code=409,
            retryable=True,
        )


class RetryableCommandFailure(CanonicalError):
    def __init__(self):
        super().__init__(
            "RETRYABLE_COMMAND_FAILURE",
            "The request could not be completed safely; retry the same request.",
            status_code=503,
            retryable=True,
        )


def safe_error_payload(error):
    """Return only stable, non-sensitive fields suitable for a JSON response."""

    if isinstance(error, CanonicalError):
        payload = {"code": error.code, "detail": error.detail}
        if error.metadata:
            payload.update(error.metadata)
        if error.retryable:
            payload["retryable"] = True
        return payload
    return {"code": "INTERNAL_ERROR", "detail": "The request could not be completed."}
