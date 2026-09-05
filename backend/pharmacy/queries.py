"""Pharmacy read-owner seams for composed context queries."""

from core.services import assert_transaction_active


def query_prescription_projection(*, organisation, facility, patient_ids, visit_id=None):
    """Return an explicit empty state until pharmacy persistence is supplied."""

    assert_transaction_active()
    return {str(patient_id): () for patient_id in patient_ids}


def query_dispense_projection(*, organisation, facility, patient_ids, visit_id=None):
    """Return an explicit empty state until pharmacy persistence is supplied."""

    assert_transaction_active()
    return {str(patient_id): () for patient_id in patient_ids}


prescription_projection = query_prescription_projection
dispense_projection = query_dispense_projection
