# Open blockers — 2026-10-31

Temporary working note; delete this file when the list is empty or the task it serves ends.
Each blocker states the measured evidence and the smallest action that would clear it.

Cleared items were removed on 2026-10-31; their facts stay in `docs/architecture.md`,
`docs/TEST.md` and `verification/`: the Windows native-start route (Ubuntu acceptance used
instead, L1 archived twice), the curated-corpus version policy (197 1.18.8 games enabled, the
rest kept as staging), the Ubuntu tooling gap (sources shipped as tarballs by `scp`, packages
only from the Tsinghua mirror), the stale home checkout and the missing L1 archive (acceptance
stages fresh source archives and archives its results). The host-memory blocker was cleared
earlier (`verification/server_release_20261031/REPORT.md` — 32 orphaned pool workers released,
14 GB available), as was the BC start-block blocker (`verification/curated_bc_20261031/REPORT.md`
— three lobby-archive replays played by official 1.18.8 and imported as 84 BC rows).

## 2. A lite policy exported to Lua is slower than the native action budget

**Evidence:** all 120 final-evaluation games of the 2026-10-31 Astra re-entry faulted with
`watchdog_timeout: candidate evaluation/execution` at `turns 1` (`a/duel-summary.json`,
`a/duel-jobs.jsonl` in `verification/acceptance_20261031_astra/`). The first decision, given the
10 s first budget, reported `elapsed_ms 1946`; every later decision is judged against
`vendor/arena/params.py:8 ACTION_TIMEOUT = 1.0` and faults. `learning/export.py:62` declares
`candidate_budget_ms=200` for candidate generation only, which does not bound model inference.

**Solution:** reduce the exported forward pass (fewer candidates scored, cached or quantized
weights) until a decision fits the frozen 1 s budget, and assert it with one native game against
the exported policy. Raising `ACTION_TIMEOUT` is not available: it is the frozen competition
profile.

## Not blockers

- Corpus versions: only 197 of the 1,076 curated games are recorded under 1.18.8 and reach BC
  (`learning/human.py:73` returns `other_version` for anything else). The rest stays staging until
  a version policy exists; freezing rule snapshots per old version costs more than it returns.
- Ubuntu host tooling: no `git`, no GitHub, no PyPI; `sudo -n` needs a password. Work is shipped as
  source tarballs over `scp` and packages come from `https://pypi.tuna.tsinghua.edu.cn/simple`.
- The home checkout on that host is stale (`tests.test_replay_curate` runs 8 tests instead of 12).
  Acceptance runs from freshly extracted archives, so do not run gates from that tree.
- Windows is the reference environment only: it has no `.runtime/` and no Wesnoth, so native work
  runs on the Ubuntu host.
- No run has a convergence or playing-strength claim (`docs/architecture.md:205-211`); formal
  training and collection start only on explicit instruction.
- PKG1 (training-bundle acceptance) was dropped by the operator, so it needs nothing.
- Lite rules approximate 470 of 587 units: a declared limit that only forbids native-equivalence
  claims, not training progress.
