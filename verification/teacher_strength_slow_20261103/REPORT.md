# Native teacher panel after target-specific slow valuation — 2026-11-03

The complete frozen panel finishes 168/168 jobs with zero gameplay faults.
All three strength comparisons remain **inconclusive** under the unchanged
superiority gate. This does not close TEST.md R3 or blocker 5.

## Design and identities

The target-attribution change was developed against the independently declared
fixed pair in `verification/teacher_slow_risk_20261103/REPORT.md`, with red/green
acceptance in `verification/teacher_slow_attribution_20261103/REPORT.md`. No panel
score was used to choose a coefficient or search a board/seed combination.

- Source commit: `cbee1cf4ec48fe204a3cded7513680e57642def6`.
- Git archive SHA256: `b5f608a2369bf2587e4966e48716acaf599f7144c48c5c38d7cebe33ccc3c5bb`.
- Ubuntu root: `/home/tongshu/acceptance/teacher_slow_attribution_green_20261103`.
- Teacher source SHA256: `02ea1d360add0950be8db9cf11d9c2997ad1ad8ae2562f31bc44ab69c2d0311a`.
- Schedule SHA256: `b2e3cb673277c1aed224d72a1e9954be66cdbd4c162999e0503a7672eb3830cf`.
- Identities SHA256: `0e9f4724a92eaeca370fd521a1aa2398f9c952731b83af72f37c6cf1d24f7ce5`.
- Full evidence archive `panel.tar.gz`, SHA256: `66b402f61a96604dace2ac46167f35cde27acef2ee946df2e2a4aa05cfe3e84f` (local/server match).

The unchanged design uses seed 20261103, 12 complete rotation blocks and at least
12 distinct scenario families per format, eight workers, 30 turns, one-second
action / ten-second first-action timeouts, and a six-hour deadline. Team games
include both `baseline_partner` and `self_team`. The 24 duel, 48 FFA and 96 team
jobs use validation maps only; the final holdout is untouched. A read-only
comparison with the previous completed panel confirms identical job IDs, seeds,
factions, teams, maps, scenario families, roles, contexts, limits and partitions.
Only the source/package identities and output paths differ.

The native executable, entropy shim, rules and frozen opponent identities are
recorded in `panel-r3/identities.json`. No rule capture or training input changed.

## Commands

From the extracted Ubuntu source, with single-threaded numerical libraries and
dummy SDL video/audio drivers:

```sh
/home/tongshu/venv/bin/python tests/acceptance_teacher_strength.py prepare \
  --root /home/tongshu/acceptance/teacher_slow_attribution_green_20261103 \
  --output /home/tongshu/acceptance/teacher_slow_attribution_green_20261103/panel-r3 \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --source-commit cbee1cf4ec48fe204a3cded7513680e57642def6
/home/tongshu/venv/bin/python tests/acceptance_teacher_strength.py run \
  --output /home/tongshu/acceptance/teacher_slow_attribution_green_20261103/panel-r3
```

Both commands exit 0. Run start to summary is 419.060 seconds. The one-shot
runner ran once, without retry, resumed games or an extended deadline. Its exit
code denotes completion; the statistical decisions below remain inconclusive.

## Results

| Format | Jobs | Valid blocks / families | Score difference | 95% interval | Turn-limit outcomes | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| duel | 24/24 | 12/12 | 0 | [-0.75, 0.75] | 2 | inconclusive |
| ffa4 | 48/48 | 12/12 | 0.006944 | [-0.118056, 0.145833] | 22 | inconclusive |
| team2v2 | 96/96 | 12/12 | -0.09375 | [-0.375, 0.1875] | 29 | inconclusive |

Every job has status `complete`, with zero recorded faults and zero candidate
truncations. Separately, 53 games end at `turn_limit`; those are not natural
leader/team terminal outcomes. Candidate truncation is a different measurement.
The team baseline-partner context is -0.0625, interval [-0.75, 0.6875]; self-team
is -0.125, interval [-0.375, 0].

The unchanged evaluator requires a strictly positive lower confidence bound.
None meets it. No non-inferiority margin was specified or retrofitted. Zero faults
and a positive FFA point estimate do not establish maintained strength.

## Evidence and limits

`panel.tar.gz` preserves the entire output: frozen schedule, packages, identities,
execution record, jobs/results, logs, replays and summary. The plan, identities,
execution and summary are also extracted under `panel-r3/` for review. Prior
reports and artifacts remain unchanged. Fixed-board acceptance proves the target
attribution repair, not full-game transfer, convergence or trained-policy quality.
No collection, training or Windows tests ran.
