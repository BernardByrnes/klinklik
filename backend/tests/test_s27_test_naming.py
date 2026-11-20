"""S-27 mechanical proof that weak-evidence CMDs are named where exercised."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (CMD, test file, test function, endpoint token in the function or its helper)
NAMED = [
    ('CMD-026', 'backend/tests/test_s03_triage.py', 'test_s03_start_save_complete_preserves_the_check_in_invoice', 'triage-records/'),
    ('CMD-038', 'backend/tests/test_phase_1d_f2.py', 'test_amendment_is_etag_protected_and_preserves_versions', 'amend/'),
    ('CMD-047', 'backend/tests/test_s11_lab.py', 'test_s11_cancel_before_collection_voids_unpaid_line', 'cancel/'),
    ('CMD-063', 'backend/tests/test_s09_inventory.py', 'test_s09_receive_creates_exact_ledger_and_idempotent_receipt', 'receipts/'),
    ('CMD-064', 'backend/tests/test_s09_inventory.py', 'test_s09_transfer_and_expired_quarantine_rules', 'transfers/'),
    ('CMD-066', 'backend/tests/test_s10_counts.py', 'test_s10_above_threshold_count_needs_distinct_admin', 'counts/'),
    ('CMD-068', 'backend/tests/test_s10_counts.py', 'test_s10_quarantine_then_disposal_is_append_only', 'quarantine/'),
    ('CMD-069', 'backend/tests/test_s10_counts.py', 'test_s10_quarantine_then_disposal_is_append_only', 'disposals/'),
    ('CMD-087', 'backend/tests/test_s15_appointment_fragment.py', 'test_s15_no_show_check_in_creates_one_linked_handover', '_check_in('),
    ('CMD-088', 'backend/tests/test_s09_inventory.py', 'test_s09_product_deactivation_requires_zero_stock', 'products/'),
    ('CMD-089', 'backend/tests/test_s09_inventory.py', 'test_s09_receive_creates_exact_ledger_and_idempotent_receipt', 'prices/'),
    ('CMD-092', 'backend/tests/test_phase_1m_a.py', 'test_add_allergy_creates_active_recorded_state_and_revision', 'add_allergy('),
    ('CMD-093', 'backend/tests/test_phase_1m_a.py', 'test_explicit_nka_requires_empty_active_state', 'set_allergy_status('),
    ('CMD-094', 'backend/tests/test_phase_1m_a.py', 'test_entered_in_error_preserves_row_and_hides_it_from_active_state', 'enter_in_error('),
    ('CMD-096', 'backend/tests/test_phase_1n_a.py', 'test_diagnosis_type_transitions_preserve_symmetric_exclusivity', 'diagnosis_url('),
    ('CMD-099', 'backend/tests/test_phase_1p_a.py', 'test_disposition_requires_if_match_and_rejects_stale_shared_etag', 'disposition_url('),
    ('CMD-101', 'backend/tests/test_phase_1q_a.py', 'test_follow_up_create_round_trips_and_is_exposed_on_encounter', 'follow_up_url('),
    ('CMD-104', 'backend/tests/test_s09_inventory.py', 'test_s09_transfer_and_expired_quarantine_rules', 'locations/'),
    ('CMD-111', 'backend/tests/test_s09_inventory.py', 'test_s09_adjustment_reconcile_and_threshold', 'thresholds/'),
    ('CMD-131', 'backend/tests/test_s10_counts.py', 'test_s10_standalone_adjustment_threshold_and_approval', 'adjustments/'),
]

HELPER_ENDPOINTS = {
    '_check_in(': 'no-show-check-in/',
    'add_allergy(': 'allergies/',
    'set_allergy_status(': 'allergy-status/',
    'enter_in_error(': 'entered-in-error/',
    'diagnosis_url(': '/diagnoses/',
    'disposition_url(': '/disposition/',
    'follow_up_url(': '/follow-up/',
}


def _function_body(lines, name):
    starts = [i for i, line in enumerate(lines) if re.match(r'(?:async )?def ', line)]
    for i in starts:
        if lines[i].startswith(f'def {name}('):
            end = next((j for j in starts if j > i), len(lines))
            return '\n'.join(lines[i:end])
    raise AssertionError(name)


def test_s27_each_named_row_has_cmd_and_endpoint_reference_in_its_test_function():
    for cid, relative, function, endpoint_token in NAMED:
        source = ROOT / relative
        assert source.exists(), (cid, relative)
        text = source.read_text(encoding='utf-8')
        body = _function_body(text.splitlines(), function)
        assert cid in body, (cid, function)
        assert endpoint_token in body, (cid, function, endpoint_token)
        if endpoint_token in HELPER_ENDPOINTS:
            assert HELPER_ENDPOINTS[endpoint_token] in text, (cid, endpoint_token)


def test_s27_three_rows_remain_honestly_partial():
    import json

    audit = json.loads((ROOT / 'docs/implementation/s17-cmd-audit.json').read_text())
    remaining = {
        row['id']
        for row in audit['commands']
        if 'Slice test file does not name this CMD or operation' in row['discrepancy']
    }
    assert remaining == {'CMD-020', 'CMD-105', 'CMD-108'}
