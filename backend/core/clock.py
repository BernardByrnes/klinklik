"""Authoritative time helpers for the verification foundation."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


KAMPALA = ZoneInfo("Africa/Kampala")


def now():
    """Return an aware UTC timestamp suitable for persistence and comparisons."""

    return datetime.now(timezone.utc)


def local_service_date(value=None):
    """Return the service date in the only currently approved local timezone."""

    value = value or now()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Service timestamps must be timezone-aware.")
    return value.astimezone(KAMPALA).date()


def require_aware(value):
    """Reject naive datetimes at a foundation boundary."""

    if not isinstance(value, datetime):
        raise TypeError("Expected a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamps must be timezone-aware.")
    return value


def is_utc(value):
    return require_aware(value).utcoffset() == timezone.utc.utcoffset(value)


__all__ = ["KAMPALA", "is_utc", "local_service_date", "now", "require_aware"]
