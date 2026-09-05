"""AUDITED-READ-01 coordinator for protected clinical payloads."""

from audit.services import record_fact
from core.errors import CanonicalError
from core.services import assert_transaction_active


def audit_clinical_projection(*, organisation, actor, facility, visit, encounters):
    """Commit one redacted PHI_READ fact before returning clinical values."""

    assert_transaction_active()
    try:
        record_fact(
            organisation=organisation,
            actor=actor,
            facility=facility,
            event_code="PHI_READ",
            action="READ",
            entity_type="Visit",
            entity_id=visit.id,
            source_ids={
                "visit_id": visit.id,
                "encounter_ids": [encounter.id for encounter in encounters],
            },
            after={"values_returned": bool(encounters), "encounter_count": len(encounters)},
        )
    except Exception as exc:
        raise CanonicalError(
            "AUDITED_READ_UNAVAILABLE",
            "The clinical context could not be released safely; retry.",
            status_code=503,
            retryable=True,
        ) from exc
