import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'docs/release/v1-evidence.md'
S17 = ROOT / 'docs/implementation/s17-cmd-audit.json'


def test_s26_dossier_counts_match_s17_artifact_and_keep_owner_limits():
    text = DOC.read_text(encoding='utf-8')
    summary = json.loads(S17.read_text(encoding='utf-8'))['summary']
    counts = summary['verdict_counts']
    for label in ('VERIFIED', 'PARTIAL', 'MISMATCH', 'FENCED'):
        assert f'| {label} | {counts[label]} |' in text
    assert f"P1 **{summary['severity_counts'].get('P1', 0)}**" in text
    assert f"P2 **{summary['severity_counts']['P2']}**" in text
    assert '459 passed, 92 skipped' in text
    assert '**Deployment is not authorized.**' in text
    assert 's25-owner-questions.md' in text
    assert 's17-cmd-audit.json' in text
    assert 'evidence-at-SHA' in text
