from decimal import Decimal
import math


COMPLAINT_DURATION_UNITS = ("HOURS", "DAYS", "WEEKS", "MONTHS")


class ComplaintValidationError(ValueError):
    """Raised when structured presenting complaints are not canonical."""


def normalize_complaints(value):
    if not isinstance(value, list):
        raise ComplaintValidationError("Complaints must be a list.")

    normalized = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ComplaintValidationError(f"Complaint {index + 1} must be an object.")

        text = item.get("text")
        if not isinstance(text, str):
            raise ComplaintValidationError(f"Complaint {index + 1} text must be text.")
        if not text.strip():
            raise ComplaintValidationError(f"Complaint {index + 1} text cannot be blank.")
        if len(text) > 500:
            raise ComplaintValidationError(f"Complaint {index + 1} text must be 500 characters or fewer.")

        duration_value = item.get("duration_value")
        duration_unit = item.get("duration_unit")
        if (duration_value is None) != (duration_unit is None):
            raise ComplaintValidationError(
                f"Complaint {index + 1} duration_value and duration_unit must be supplied together."
            )
        if duration_value is not None:
            if isinstance(duration_value, bool) or not isinstance(duration_value, (int, float, Decimal)):
                raise ComplaintValidationError(f"Complaint {index + 1} duration_value must be numeric.")
            if isinstance(duration_value, float) and not math.isfinite(duration_value):
                raise ComplaintValidationError(f"Complaint {index + 1} duration_value must be finite.")
            if duration_value <= 0:
                raise ComplaintValidationError(f"Complaint {index + 1} duration_value must be positive.")
            if duration_unit not in COMPLAINT_DURATION_UNITS:
                raise ComplaintValidationError(
                    f"Complaint {index + 1} duration_unit must be one of: {', '.join(COMPLAINT_DURATION_UNITS)}."
                )

        normalized.append(
            {
                "text": text,
                "duration_value": duration_value,
                "duration_unit": duration_unit,
            }
        )
    return normalized


def legacy_complaint_from_content(content):
    if "presenting_complaint" not in content:
        return None
    value = content["presenting_complaint"]
    if not isinstance(value, str):
        raise ComplaintValidationError("presenting_complaint must be text.")
    if not value.strip():
        return []
    return normalize_complaints(
        [{"text": value, "duration_value": None, "duration_unit": None}]
    )


def resolve_complaints(*, content, complaints=None):
    """Return normalized complaints, or None when the structured field was omitted."""
    if complaints is not None:
        return normalize_complaints(complaints)
    return legacy_complaint_from_content(content)
