# KlinKlik v1 clinic-spine release evidence

**Status: local verification evidence only. Deployment is not authorized.**

Current evidence base: `ab1e259` (published `main` / `release/v1-clinic-spine`).
This is a documentation refresh of the accepted S-16 dossier. It restates S-16 heavy-lane results as **evidence-at-SHA** (not re-run in S-26) and adds the S-17..S-25 evidence line. It is not a release approval, pilot approval, security certification, or legal/fiscal attestation.

## 1. Current contract state (recomputed from artifacts at `ab1e259`)

Source: `docs/implementation/s17-cmd-audit.json` (`summary.verdict_counts`, `summary.severity_counts`).

| Verdict | Count |
| --- | --- |
| VERIFIED | 48 |
| PARTIAL | 32 |
| MISMATCH | 2 |
| FENCED | 52 |
| Total active CMDs | 134 (retired CMD-097/CMD-107 excluded) |

P1 **0**, P2 **34**.

Earlier S-16 contract inventory (`docs/implementation/s16-contract-verification.json`, evidence-at-`54291e4`): PC 80 = 62 IMPLEMENTED / 7 PARTIAL / 11 FENCED; CMD 134 = 103 EVIDENCE LINKED / 1 PARTIAL / 30 FENCED; MIG 11 IMPLEMENTED; ADR 14 SETTLED. That table was an evidence index, not a branch-level audit; the S-17 command audit supersedes its CMD verdicts.

### What moved which rows

| Slice | Accepted SHA | Change reflected here |
| --- | --- | --- |
| S-18 | `fa9848d` | Label-only: lab views CMD-042/043/044/046/047, StockTransferView CMD-064, CMD-051 FENCED (review-19). |
| S-19 | `e5d603f` | Ten active clinical views gained registry CMD labels and `requires_idempotency=True`; CMD-097 retired routes deliberately unlabelled; legacy payment compatibility namespace (review-20). |
| S-20 | `afeb57c` | Four verbs aligned to registry: CMD-044 PATCH, CMD-099/101/110 POST (review-21). |
| S-21 | `93c1af7` | D-13 residual namespaces: count-open and invoice-issue compat namespaces; CMD-106 canonical; CMD-014/136 left as owner §59 divergences (review-22). |
| S-24 | `392a0b1` | Eight declared audit codes attached to existing writers: note amend, four allergy codes, diagnosis, disposition, follow-up; money/dispensing entries left as findings (review-25). |
| S-25 | `ab1e259` | Owner §59 question dossier assembled; no product change (review-26). |
| S-27 | in progress | Test-evidence naming closed 20 of 23 weak rows; 3 rows remain PARTIAL with named gaps. S-17 verdicts recomputed; no product code. |

## 2. New evidence line (S-17..S-25)

- **Command-by-command audit:** `docs/implementation/s17-cmd-audit.json` and `.md`, built by `tools/s17_cmd_inventory.py` plus `tools/s17_apply_manual.py`; machine assertions in `backend/tests/test_s17_cmd_audit.py` (**9 tests collected**). This is the evidence that replaced the S-16 “EVIDENCE LINKED” class.
- **Audit-code map:** `docs/implementation/s22-audit-code-map.json` and `.md` (27 affected rows, 37 declared-code entries); full-path resolutions in `tools/s23_resolve_unresolved.py`. Final map: 20 NAMING_MAPPING / 15 MISSING_EMISSION / 2 REGISTRY_SUPERSEDED / 0 UNRESOLVED. Machine assertions in `backend/tests/test_s22_audit_code_map.py` (**4 tests collected**). The map remains the pre-fix evidence record; S-24 closures are noted in its header, not reclassified post-hoc.
- **Owner questions:** [`s25-owner-questions.md`](../implementation/s25-owner-questions.md) is the annex of open owner-reserved questions Q1..Q6, with exact evidence and default-not-decision framing. Settled lead decisions D-01/D-03/D-08/D-11/D-12/D-13 and accepted S-18/S-19 outcomes are listed there so the owner is not re-asked.

The two S-17 MISMATCH rows are CMD-014 and CMD-136 (registry INTERNAL vs live HTTP routes). The money/dispensing MISSING_EMISSION findings and the two REGISTRY_SUPERSEDED framings are owner questions in the annex; this dossier makes no recommendation that decides them.

## 3. Verification posture

Current full backend suite at `ab1e259`: **459 passed, 92 skipped** (S-25 run, 220.04s). Arithmetic from that executed run: S-24 baseline 457/92 + 2 new S-25 tests = 459/92. Machine-test collections at this base: `test_s16_release_evidence.py` 6, `test_s17_cmd_audit.py` 9, `test_s22_audit_code_map.py` 4, `test_s25_owner_questions.py` 2.

Browser gate lane definition: **17 slice/handoff/drill files, 29 tests**, executed in chunks on fresh stacks. The legacy `phase-1x` suites were red at base as pre-existing drift; they are not release blockers for this evidence line. Sustained browser load has produced `ERR_NO_BUFFER_SPACE`; the standing discipline is to chunk lanes with fresh stacks rather than run one long lane. `CLINICOPUS_E2E_PASSWORD` must be `ClinicopusDemo!2026` for legacy demo flows; `@clinicopus.local` uses `ClinicopusDemo123!` — never mix them.

S-16 journey/drill results below remain **evidence-at-SHA**; none were re-run in this documentation refresh.

### S-16 evidence-at-`3cab3c2` / `54291e4` (not re-run in S-26)

- Journey drills (J-01..J-05): consolidated fresh-stack run **26 passed in 3.2 minutes** across the sixteen canonical specs, with seed_demo and MIG-002/003/004 cutovers. J-05 ANC and general Journey F remained FENCED.
- Operational drills: `check_s00_postgres.py` PASS; `manage.py check_rls --require-postgres` PASS with 82 FORCE-RLS tables under `clinicopus_app` (`bypass_rls=false`); `pg_dump -Fc` 712,144 bytes; `pg_restore` exit 0 in 12s; restored runtime and RLS gates PASS; scheduling 0008 reversal/reapply OK.
- Accessibility / low bandwidth / print: a11y spec passed; throttled 450 ms / 50 KB/s / 20 KB/s journey PASS; Chromium print-media receipt PDF 102,184 bytes (SHA-256 `6e36c6a1cfaf3145552a6a12aa6a7779165be2178b3b1f47f2f59e36801990ca`). Physical printer certification not run.
- Earlier reused-database `clinic-slice` 120s timeout was recorded as an unproven environment hypothesis; the fresh-DB run passed.

Static gates at `ab1e259`: `generate_api_client.py --check` PASS (no schema surface change), `git diff --check` clean. No browser lane was run in S-26 (docs-only).

## 4. Fenced items and owner decisions

The open set is defined by `s25-owner-questions.md`: Q1 CMD-014, Q2 CMD-136, Q3 money emissions (CMD-062/076/077), Q4 dispensing emissions (CMD-058), Q5 REGISTRY_SUPERSEDED confirmations (CMD-030/079), Q6 the standing P2 weak-test-evidence class. Do not re-ask D-08: refund issuance is fenced on §973 MFA with no waiver.

Previously recorded fences remain: S-13 ANC/J-05 (OD-C/OD-17, BP-BL-05), S-14 reporting/print (OD-L4/L5, BP-BL-04), S-12 residual pharmacy branches, S-05/S-06 discount/waiver, general appointment lifecycle/Journey F, provider/pilot/deployment gates. The full per-contract fenced list remains in `s17-cmd-audit.md`.

## 5. Honest limits carried forward

- Historical `IdempotencyRecord` rows under pre-correction labels remain historical rows and are not migrated (S-16/S-18/S-19 statements remain true; this lineage is synthetic).
- Refund issuance remains fenced per D-08 (§973 privileged MFA, no waiver). No refusal rule was waived or invented.
- **Deployment is not authorized.**
- The S-16 heavy lanes above are evidence-at-SHA, not claims of a fresh S-26 run.
- Audit-code map status is a pre-fix record; S-24 closures are additive header notes only.
- PC `IMPLEMENTED` in the S-16 inventory proves a model/migration exists, not every field/constraint/state rule. CMD `VERIFIED` in S-17 means declared route, label, audit and named slice test were located and consistent — not that every error branch was executed.
- No PHI appears in this dossier; all records cited are synthetic or registry/evidence metadata.

## 6. Reproduce the current lightweight checks

```
cd backend
PYTHONPATH=.. python -m pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
cd ..
PYTHONPATH=. python tools/generate_api_client.py --check
git diff --check
```

Heavy PostgreSQL and browser lanes are not re-run by this documentation refresh; use the S-16 evidence-at-SHA records above.
