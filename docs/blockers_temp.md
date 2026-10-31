# Open blockers

Temporary working note; delete this file when the list is empty. Each blocker states the measured
evidence and the smallest action that would clear it; cleared facts live in `docs/architecture.md`,
`docs/TEST.md` and `verification/`.

No blocker is open. The action-budget item was cleared on 2026-10-31: a delivered add-on carries
`score_limit=24` and the scorer hoists its candidate-independent input, so the 36 decisions after
the first of each of eight duel games ran at most 234 ms inside the frozen 1 s budget and none of
them faulted (`verification/action_budget_20261031/REPORT.md`).

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
