# Open blockers

Temporary working note; delete this file when the list is empty. Each blocker states the measured
evidence and the smallest action that would clear it; cleared facts live in `docs/architecture.md`,
`docs/TEST.md` and `verification/`.

## 1. An exported lite policy cannot decide inside the native action budget

**Evidence:** all 120 final-evaluation games of the 2026-10-31 Astra re-entry faulted with
`watchdog_timeout: candidate evaluation/execution` at turn 1
(`verification/acceptance_20261031_astra/a/duel-jobs.jsonl`, `a/duel-summary.json`). The only
decision that ran under the 10 s first budget reported `elapsed_ms 1946`
(`verification/acceptance_20261031/L1/REPORT.md`); every later decision is judged against
`ACTION_TIMEOUT = 1.0` (`vendor/arena/params.py:8`).
`candidate_budget_ms=200` (`learning/export.py:62`) bounds candidate generation only, so it does
not bound model inference.

**Clearing it:** shrink the exported forward pass — fewer candidates scored, cached or quantised
weights — until one decision fits the frozen 1 s budget, and assert it with one native game against
the exported policy. Raising `ACTION_TIMEOUT` is unavailable: it is the competition profile.

## Not blockers

- Ubuntu host tooling: no `git`, no GitHub, no PyPI; `sudo -n` needs a password. Changes arrive as
  `git archive` tarballs over `scp` (`AGENTS.md` rule 8) and packages come from
  `https://pypi.tuna.tsinghua.edu.cn/simple`.
- The home checkout on that host is stale (`tests.test_replay_curate` runs 8 tests instead of 12).
  Acceptance runs from freshly extracted archives, so no gate runs from that tree.
- Windows is the reference environment only: it has no `.runtime/` and no Wesnoth, so native work
  runs on the Ubuntu host.
- PKG1 (training-bundle acceptance) was dropped by the operator, so nothing tracks a clean-Ubuntu
  bundle run.
