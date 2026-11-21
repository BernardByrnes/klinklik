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
    assert 'Current evidence base: `d5d930e`' not in text
    assert 'Current evidence base: `51a3e8d`' in text
    assert '482 passed, 97 skipped' in text
    assert '494 passed, 103 skipped' in text
    for accepted_sha in ('6ec1245', '21225e8', '771e2f5', 'e6de464', 'd5d930e'):
        assert f'`{accepted_sha}`' in text
    for repair_sha in (
        'd1e5050', '4216bed', '4878b8d', 'd749686', '6e5bdc0', 'ed58eb2'
    ):
        assert f'`{repair_sha}`' in text

    # S-35 is pinned verbatim, not recomputed from the dossier text.
    for s35_sha in (
        'e84ed82', '2295b74', 'b86a405', '531dacf', 'f45c76f',
        '56e3a59', 'a2c834a', '0247b14', '51a3e8d',
    ):
        assert f'`{s35_sha}`' in text
    assert 'audit-q1-q5-r1-r6-f1-f4.md' in text
    assert '409 `RESULT_NOT_SUBMITTED`' in text
    assert 'HTTP 200 `CONFIRMED`' in text
    assert 'HTTP 500' in text and 'DRF 401' in text
    assert 'epoch `2 → 3`' in text
    assert '45 passed, zero skips' in text
    assert '34 tests' in text
    assert '5,440–5,498 ms' in text
    assert '156,428–156,433 B' in text
    assert '91–92 ms' in text
    assert '7,729 B' in text
    assert 'NAMING_MAPPING 20 / MISSING_EMISSION 15 / REGISTRY_SUPERSEDED 2' in text
    assert '7/7 then 7/7' in text
    assert 's35-audit-repairs-handback.md' in text
    assert 'No browser lane was re-run' in text
    assert '82 tables' in text
    assert 'owner ≠ app role' in text
    assert 'bypass_rls=false' in text
    assert '47,439 ms' in text
    assert 'not a budget claim' in text
    assert 'check_s00_postgres.py' in text

    # Owner limits and evidence discipline remain explicit.
    assert '**Deployment is not authorized.**' in text
    assert 'It is not a release approval, pilot approval, security certification, or legal/fiscal attestation.' in text
    assert 's25-owner-questions.md' in text
    assert 'answered by D-14' in text
    assert 'Q1–Q5 remain open owner questions' in text
    assert 'D-08 no-waiver decision' in text
    assert 'no waiver' in text
    assert 'Historical' in text and 'are not migrated' in text
    assert 's17-cmd-audit.json' in text
    assert 'evidence-at-SHA' in text
