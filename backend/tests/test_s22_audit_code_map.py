import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / 'docs/implementation/s22-audit-code-map.json'
S17 = ROOT / 'docs/implementation/s17-cmd-audit.json'
VOCAB = {'NAMING_MAPPING', 'MISSING_EMISSION', 'REGISTRY_SUPERSEDED', 'BUNDLED', 'UNRESOLVED'}


def test_s22_map_covers_every_affected_command_exactly():
    s17 = json.loads(S17.read_text(encoding='utf-8'))
    audit_map = json.loads(MAP.read_text(encoding='utf-8'))
    affected = {
        row['id'] for row in s17['commands']
        if 'Declared audit codes not found in code' in row['discrepancy']
    }
    mapped = {row['command_id'] for row in audit_map['rows']}
    assert mapped == affected
    assert audit_map['affected_rows'] == len(affected)


def test_s22_declared_codes_match_the_registry_and_classifications_are_valid():
    s17 = json.loads(S17.read_text(encoding='utf-8'))
    audit_map = json.loads(MAP.read_text(encoding='utf-8'))
    declared = {row['id']: set(row['missing_audit_codes']) for row in s17['commands']}
    for row in audit_map['rows']:
        assert set(row['declared_codes']) == declared[row['command_id']]
        assert {entry['declared_code'] for entry in row['entries']} == declared[row['command_id']]
        for entry in row['entries']:
            assert entry['classification'] in VOCAB
            if entry['classification'] == 'MISSING_EMISSION':
                assert entry['risk_class'] in {'stock', 'money', 'dispensing', 'final clinical', 'other'}


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
