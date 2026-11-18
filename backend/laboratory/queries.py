"""Laboratory read-owner seams for composed context queries.

The laboratory persistence contracts are not part of S-01. Returning a typed
empty projection makes that absence visible to the coordinator without
inventing orders, results, or interpretations.
"""

from core.services import assert_transaction_active


def query_laboratory_projection(*, organisation, facility, patient_ids, visit_id=None):
    assert_transaction_active()
    return {str(patient_id): () for patient_id in patient_ids}


def blocking_visit_records(*, organisation, facility, visit_id):
    """Return lab records which legally block a pre-service Visit closure.

    S-02 has no laboratory persistence owner yet.  The explicit empty result
    is safer than inferring a blocker from a future schema and gives the LWBS
    command a stable owner seam for the laboratory slice.
    """

    assert_transaction_active()
    return ()


laboratory_projection = query_laboratory_projection
