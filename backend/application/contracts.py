"""Validated, model-free contracts for application commands."""

from dataclasses import dataclass, field
from uuid import UUID
import re


_COMMAND_ID = re.compile(r"^CMD-[0-9]{3}$")
_RANK1_ID = re.compile(r"^(?:REC|QUE|TRI|ENC|LAB|DX|RX|PHM|INV|DSP|BIL|PAY|RCP|ANC)-[0-9]{3}$")
_CODE = re.compile(r"^[a-z][a-z0-9_.:-]{0,119}$")


def _uuid(value, label, *, required=True):
    if value is None and not required:
        return None
    try:
        return UUID(str(value))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a UUID.") from exc


def _code(value, label):
    value = str(value or "")
    if not _CODE.fullmatch(value):
        raise ValueError(f"{label} must be a stable lowercase code.")
    return value


@dataclass(frozen=True)
class CommandSpec:
    operation_id: str
    rank1_id: str
    capability: str
    owner_service: str
    lock_plan: tuple[str, ...] = field(default_factory=tuple)
    requires_idempotency: bool = True

    def __post_init__(self):
        if not _COMMAND_ID.fullmatch(self.operation_id):
            raise ValueError("operation_id must be a frozen CMD-### identifier.")
        if not _RANK1_ID.fullmatch(self.rank1_id):
            raise ValueError("rank1_id must be a frozen Rank 1 story identifier.")
        _code(self.capability, "capability")
        _code(self.owner_service, "owner_service")
        if tuple(self.lock_plan) != self.lock_plan:
            raise ValueError("lock_plan must be an ordered tuple.")
        if len(set(self.lock_plan)) != len(self.lock_plan):
            raise ValueError("lock_plan must not contain duplicate lock names.")


@dataclass(frozen=True)
class CommandContext:
    organisation_id: UUID
    actor_id: UUID | None = None
    facility_id: UUID | None = None
    capability: str = ""
    scope: str = ""
    idempotency_key: str | None = None
    fingerprint: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "organisation_id", _uuid(self.organisation_id, "organisation_id"))
        object.__setattr__(self, "actor_id", _uuid(self.actor_id, "actor_id", required=False))
        object.__setattr__(self, "facility_id", _uuid(self.facility_id, "facility_id", required=False))
        _code(self.capability, "capability")
        _code(self.scope, "scope")
        if self.fingerprint is not None and not re.fullmatch(r"[0-9a-f]{64}", self.fingerprint):
            raise ValueError("fingerprint must be a lowercase SHA-256 hex digest.")


@dataclass(frozen=True)
class CommandResult:
    status_code: int
    body: object = None
    headers: dict = field(default_factory=dict)
    result_reference: object = None
    replayed: bool = False

    def __post_init__(self):
        if not 200 <= self.status_code < 600:
            raise ValueError("status_code must be an HTTP status code.")
