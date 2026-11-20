import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'docs/release/v1-evidence.md'
S17 = ROOT / 'docs/implementation/s17-cmd-audit.json'


def test_s26_dossier_counts_match_s17_artifact_and_keep_owner_limits():
    text = DOC.read_text(encoding='utf-8')
    summary = json.loads(S17.read_text(encoding='utf-8'))['summary']
    counts = summary['verdict_counts']

    # Contract counts are pinned to the S-17 artifact, not restated from the dossier.
    assert counts == {'VERIFIED': 48, 'PARTIAL': 32, 'MISMATCH': 2, 'FENCED': 52}
    for label in ('VERIFIED', 'PARTIAL', 'MISMATCH', 'FENCED'):
        assert f'| {label} | {counts[label]} |' in text
    assert f"P1 **{summary['severity_counts'].get('P1', 0)}**" in text
    assert f"P2 **{summary['severity_counts']['P2']}**" in text

    # Work-order close-out facts, pinned to the accepted tips and executed gates.
    assert 'Current evidence base: `d5d930e`' in text
    assert '482 passed, 97 skipped' in text
    for accepted_sha in ('6ec1245', '21225e8', '771e2f5', 'e6de464', 'd5d930e'):
        assert f'`{accepted_sha}`' in text
    for repair_sha in (
        'd1e5050', '4216bed', '4878b8d', 'd749686', '6e5bdc0', 'ed58eb2'
    ):
        assert f'`{repair_sha}`' in text
    assert '82 tables' in text
    assert 'bypass_rls=false' in text
    assert '47,439 ms' in text
    assert 'not a budget claim' in text
    assert 'check_s00_postgres.py' in text

    # Owner limits and evidence discipline remain explicit.
    assert '**Deployment is not authorized.**' in text
    assert 's25-owner-questions.md' in text
    assert 'answered by D-14' in text
    assert 'no waiver' in text
    assert 'Historical' in text and 'are not migrated' in text
    assert 's17-cmd-audit.json' in text
    assert 'evidence-at-SHA' in text
