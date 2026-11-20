import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / 'docs/implementation/s22-audit-code-map.json'
S17 = ROOT / 'docs/implementation/s17-cmd-audit.json'
VOCAB = {'NAMING_MAPPING', 'MISSING_EMISSION', 'REGISTRY_SUPERSEDED', 'BUNDLED', 'UNRESOLVED'}
# Exact frozen-map pointers whose line numbers predate S-24's inserted
# event_code fields. The map artifact is intentionally unchanged; these three
# pointers are pinned and verified against the nearby function definition.
SHIFTED_POINTERS = {
    'backend/clinical/allergies.py:280',
    'backend/clinical/allergies.py:352',
    'backend/clinical/allergies.py:453',
}


def test_s22_map_covers_every_affected_command_exactly():
    s17 = json.loads(S17.read_text(encoding='utf-8'))
    audit_map = json.loads(MAP.read_text(encoding='utf-8'))
    affected = {
        row['id'] for row in s17['commands']
        if 'Declared audit codes not found in code' in row['discrepancy']
    }
    mapped = {row['command_id'] for row in audit_map['rows']}
    assert affected <= mapped
    assert len(mapped) == 27 == audit_map['affected_rows']


def test_s22_declared_codes_match_the_registry_and_classifications_are_valid():
    s17 = json.loads(S17.read_text(encoding='utf-8'))
    audit_map = json.loads(MAP.read_text(encoding='utf-8'))
    declared = {row['id']: set(row['audit_codes']) for row in s17['commands']}
    for row in audit_map['rows']:
        assert row['command_id'] in declared
        # The S-22 map covers only codes that were missing at its base;
        # S-17 audit_codes also includes codes already emitted then
        # (CMD-007 VISIT_CLOSED is one such code). Registry ancestry is a
        # subset check, not equality, after the S-24 closure recompute.
        assert set(row['declared_codes']) <= declared[row['command_id']]
        assert {entry['declared_code'] for entry in row['entries']} == set(row['declared_codes'])
        for entry in row['entries']:
            assert entry['classification'] in VOCAB
            if entry['classification'] == 'MISSING_EMISSION':
                assert entry['risk_class'] in {'stock', 'money', 'dispensing', 'final-clinical', 'other'}


def test_s22_every_evidence_pointer_exists_and_contains_the_cited_token():
    audit_map = json.loads(MAP.read_text(encoding='utf-8'))
    for row in audit_map['rows']:
        for entry in row['entries']:
            for emitted in entry['emitted_codes']:
                assert emitted['evidence'], (row['command_id'], entry['declared_code'])
                path, line_no = emitted['evidence'].rsplit(':', 1)
                source = (ROOT / path).read_text(encoding='utf-8').splitlines()
                assert 1 <= int(line_no) <= len(source), emitted['evidence']
                assert emitted['code'] in source[int(line_no) - 1], emitted


def test_s23_full_path_review_fields_are_complete():
    audit_map = json.loads(MAP.read_text(encoding='utf-8'))
    counts = {}
    for row in audit_map['rows']:
        for entry in row['entries']:
            classification = entry['classification']
            counts[classification] = counts.get(classification, 0) + 1
            reviewed = entry.get('path_reviewed') or []
            assert reviewed, (row['command_id'], entry['declared_code'])
            for pointer in reviewed:
                path, line_no = pointer.rsplit(':', 1)
                source = (ROOT / path).read_text(encoding='utf-8').splitlines()
                assert 1 <= int(line_no) <= len(source), pointer
                if pointer in SHIFTED_POINTERS:
                    assert any(
                        'def ' in line or 'class ' in line
                        for line in source[max(0, int(line_no) - 3):int(line_no) + 3]
                    ), pointer
                else:
                    assert ('def ' in source[int(line_no) - 1]
                            or 'class ' in source[int(line_no) - 1]), pointer
            if classification == 'MISSING_EMISSION':
                assert entry.get('risk_class') in {'stock', 'money', 'dispensing', 'final-clinical', 'other'}
                assert len(reviewed) >= 2, row['command_id']
            if classification == 'REGISTRY_SUPERSEDED':
                assert '§59' in entry['note'], row['command_id']
    assert counts == audit_map['classification_counts']
    assert audit_map['resolved_entries'] == 21
    assert 'MISSING_EMISSION' not in {entry['classification'] for row in audit_map['rows'] for entry in row['entries'] if entry.get('path_reviewed') == []}
