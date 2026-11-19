"""SM-10 supplied Appointment fragment only.

The fragment is the single NO_SHOW -> CHECKED_IN transition. No other
appointment lifecycle, scheduling rule or Journey F behavior belongs here.
"""

from core.errors import CanonicalError
from scheduling.models import Appointment


def assert_no_show_fragment(appointment):
    """Refuse every transition outside the one supplied fragment."""

    if appointment.status != "NO_SHOW":
        raise CanonicalError(
            "UNSUPPORTED_OPERATION",
            "Only a no-show appointment can use the supplied check-in fragment.",
            status_code=409,
        )
    if appointment.service_day is None:
        raise CanonicalError(
            "PREREQUISITE_MISSING",
            "The appointment has no service day for the supplied fragment.",
            status_code=422,
        )
    if appointment.checked_in_visit_id is not None:
        raise CanonicalError(
            "ALREADY_EXISTS",
            "The appointment already has a linked checked-in Visit.",
            status_code=409,
        )


def link_checked_in_visit(*, appointment, visit):
    """Move exactly NO_SHOW -> CHECKED_IN and retain the Visit reference."""

    assert_no_show_fragment(appointment)
    appointment.status = "CHECKED_IN"
    appointment.checked_in_visit = visit
    appointment.version += 1
    appointment.save(
        update_fields=["status", "checked_in_visit", "version", "updated_at"]
    )
    return appointment
