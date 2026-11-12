# Final submission readiness audit

Audited the clean `main` baseline at `e6598c84d71ac57b57817fdf23a7ee445135de1b` in a temporary Git archive using Python 3.11.14. The ablation branch `ae7eea7337a0efdf7b91192c8e9db98a77b4848f` remains separate and is not part of this submission tree. This report is the only intended addition to the baseline. Source of truth: `BRIEF.md`.

## Specification checklist

| Requirement | Status | Evidence |
|---|---|---|
| Root `policy.py`, importable module | PASS | Imported from clean archive with `/home/kiit/.pyenv/versions/3.11.14/bin/python3.11`. |
| Exact constructor and allocation interface | PASS | Runtime signatures are `Policy(creatives, daily_budget, seed)` and `allocate(day, history)`. |
| Python 3.11+ compatibility | PASS | Import and all tests ran under Python 3.11.14. |
| Output shape and accepted creative IDs | PASS | Returns a dictionary keyed by the 50 IDs supplied in `creatives`; checked against actual CSV. |
| Empty and valid histories | PASS | Direct allocation checks passed for empty history and the reported historical rows. |
| Incomplete and malformed rows | PASS | Missing fields default safely; invalid, nonfinite, negative, fractional-day, zero-spend, and unknown-ID rows were exercised. |
| Duplicate and future rows | PASS | Duplicate `(day, creative_id)` uses the last supplied row; current/future rows do not change the decision. |
| All 50 creatives and cold starts | PASS | All IDs are returned; all 10 never-served creatives receive at least the $8 floor in the empty-history check. |
| Finite, nonnegative, normalized output | PASS | Adversarial cases remained finite/nonnegative; shares summed to 1 within `1e-10`. |
| Budget and per-creative limits | PASS | At a $2,000 budget, shares total $2,000 after scaling and no creative exceeds $400. |
| Determinism | PASS | Repeated calls on the same instance and inputs returned identical dictionaries. |
| Runtime | PASS | Maximum observed call was 0.0106 seconds over 30 decisions on the complete history, far below 10 seconds. |
| No simulator or ground-truth access | PASS | Clean import left `simulator` and `config` absent from `sys.modules`; source imports only `math`, `collections`, and `typing`. |
| No network or local-file dependency in policy | PASS | Policy imports no networking or file APIs and works from an extracted temporary checkout. No external packages are used. |
| External evaluator enforces network isolation | NOT VERIFIED | The evaluation host is outside this repository; its network sandbox setting was not independently inspected. The policy itself makes no network calls or imports. |
| Documented setup, test, and evaluation commands | PASS | Python 3.11.14 virtual environment creation/activation and both commands ran successfully from a clean archive. |
| Baseline evaluation reproducibility | PASS | See results below; figures match the established baseline. |
| README limit and required content | PASS | Root `README.md` is 263 words and covers method, exclusions, evidence limits, next-day work, and commands. |
| Assessment instructions preserved | PASS | `ASSESSMENT_KIT_README.md` is byte-identical to the original root README (SHA-256 `438b2a5dc448b08b5ae47cde21ce79c778758c4483f81e21f11aa51b42f8b6d7`). |
| Experimental ablations excluded from target tree | PASS | Target is the baseline tree; it contains no `ABLATION_REPORT.md`, `analysis/policy_ablation.py`, or ablation result JSON. The research branch remains available separately. |
| Assessment infrastructure unchanged | PASS | No differences from baseline in `.interview/`, hook/configuration directories, panel files, or submission scripts. |
| Accidental credentials | PASS (bounded scan) | No credential-like filenames, suspicious JSON key names, common token/private-key patterns, or credential assignments found across the 73 baseline tracked files. No dedicated third-party secret scanner was available; the scan is heuristic, not a guarantee. |

## Independent verification

Ran from a clean temporary archive of the intended baseline:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python3 -m unittest discover -s tests -v
python3 evaluate.py --seeds 20 --seed-start 3000
```

The complete suite passed: **22 tests**. Additional direct checks covered interface signatures, empty and historical inputs, incomplete/malformed/duplicate/future/adversarial rows, all 50 IDs, cold-start floors, output finiteness/nonnegativity/normalization, the $400 limit, same-instance determinism, and a 30-call runtime sample.

Evaluation reproduced the established 20 paired seeds (3000–3019) across baseline, faster-fatigue, and greater-uncertainty scenarios:

| Scenario | B1 revenue | B2 revenue | Policy revenue | Clairvoyant revenue | Normalized capture |
|---|---:|---:|---:|---:|---:|
| Baseline | $84,353 ($81,446–$87,260) | $99,413 ($93,134–$105,693) | $117,291 ($109,384–$125,198) | $143,036 ($127,434–$158,637) | 0.561 |
| Faster fatigue | $61,029 ($58,584–$63,474) | $76,079 ($70,037–$82,122) | $89,167 ($81,467–$96,866) | $119,996 ($104,131–$135,861) | 0.477 |
| Greater uncertainty | $82,829 ($78,900–$86,759) | $111,094 ($100,528–$121,660) | $130,418 ($116,582–$144,254) | $179,461 ($143,589–$215,333) | 0.492 |

These intervals are across seed-level revenue outcomes. Each policy uses the same seed set and scenario configuration; the simulator’s random draws are keyed by seed/day/creative. Results establish performance only under the configured simulator assumptions, not real-world advertising lift.

## Submission branch and file inventory

Intended branch: `codex/final-submission-audit`, based on stable baseline `e6598c84d71ac57b57817fdf23a7ee445135de1b`. This report is a documentation-only addition; policy, simulator, configuration, data, evaluation code/results, preregistration history, and assessment instructions are unchanged. The ablation commit is not merged.

The exact tracked baseline file inventory follows, plus this `FINAL_AUDIT.md`:

```text
.claude/settings.json
.codex/config.toml
.codex/hooks.json
.cursor/hooks.json
.cursor/mcp.json
.github/hooks/ivkit.json
.gitignore
.interview/ivkit/__init__.py
.interview/ivkit/_entry.py
.interview/ivkit/_role
.interview/ivkit/agents/__init__.py
.interview/ivkit/agents/base.py
.interview/ivkit/agents/claude_code.py
.interview/ivkit/agents/codex.py
.interview/ivkit/agents/copilot.py
.interview/ivkit/agents/cursor.py
.interview/ivkit/checkpoint.py
.interview/ivkit/cli.py
.interview/ivkit/collect.py
.interview/ivkit/configs.py
.interview/ivkit/gate.py
.interview/ivkit/hook_log.py
.interview/ivkit/launcher.py
.interview/ivkit/pack.py
.interview/ivkit/panel.py
.interview/ivkit/panel_mcp.py
.interview/ivkit/paths.py
.interview/ivkit/pause.py
.interview/ivkit/record.py
.interview/ivkit/seal.py
.interview/ivkit/session_links.py
.interview/ivkit/submit.py
.interview/ivkit/tools.py
.interview/session.json
.mcp.json
.vscode/mcp.json
ASSESSMENT_KIT_README.md
BRIEF.md
FAQ.md
POLICY.md
PREREG.md
README.md
SIMULATION.md
SOLUTION.md
analysis/audit.py
analysis/policy_signal_validation.py
artifacts/audit_summary.json
artifacts/creative_age_performance.csv
artifacts/creative_first7.csv
artifacts/creative_performance.csv
artifacts/creative_roas.svg
artifacts/format_roas.svg
artifacts/group_performance.csv
artifacts/hook_roas.svg
artifacts/policy_signal_validation.json
artifacts/simulation_benchmarks.csv
artifacts/simulation_benchmarks.json
artifacts/simulation_daily.csv
artifacts/weekly_performance.csv
artifacts/weekly_roas.svg
config.json
data/competitor_launches.csv
data/creatives.csv
data/daily_final.csv
data/daily_reported.csv
evaluate.py
interview
interview.cmd
policy.py
problem.json
simulator.py
tests/test_policy.py
tests/test_simulator.py
FINAL_AUDIT.md
```
