import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOSSIER = ROOT / 'docs/implementation/s25-owner-questions.json'
DOC = ROOT / 'docs/implementation/s25-owner-questions.md'
CITED_IN_WORKTREE = [
    'IMPLEMENTATION_BLUEPRINT.md',
    'blueprint-validation/TRACEABILITY.md',
    'docs/implementation/s17-cmd-audit.md',
    'docs/implementation/s22-audit-code-map.md',
]


def _open_ids():
    s17 = json.loads((ROOT / 'docs/implementation/s17-cmd-audit.json').read_text())
    audit_map = json.loads((ROOT / 'docs/implementation/s22-audit-code-map.json').read_text())
    ids = {row['id'] for row in s17['commands'] if row['verdict'] == 'MISMATCH'}
    ids.update(
        row['command_id']
        for row in audit_map['rows']
        for entry in row['entries']
        if entry['classification'] == 'MISSING_EMISSION'
        and entry['risk_class'] in {'money', 'dispensing'}
    )
    return ids


def test_s25_dossier_exists_and_covers_the_exact_open_id_set():
    text = DOC.read_text(encoding='utf-8')
    section = text.split('## Open ID coverage', 1)[1].split('\n---', 1)[0]
    listed = set(re.findall(r'CMD-\d{3}', section))
    assert listed == _open_ids()
    for number in range(1, 7):
        assert f'## Q{number} —' in text


def test_s25_cited_files_and_status_summary_exist():
    text = DOC.read_text(encoding='utf-8')
    for relative in CITED_IN_WORKTREE:
        assert (ROOT / relative).exists(), relative
        assert relative in text, relative
    assert '28 VERIFIED / 52 PARTIAL / 2 MISMATCH / 52 FENCED' in text
    assert 'P1 0, P2 54' in text
    assert 'lead-decisions.md' in text
    assert 'review-25' in text
    assert 'default, not decision' in text
