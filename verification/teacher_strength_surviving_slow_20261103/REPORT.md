# Native teacher panel after surviving-slow repair — 2026-11-03

All 168 planned jobs complete without recorded gameplay faults. The three
comparisons remain **inconclusive** under the unchanged superiority gate.
TEST.md R3 and blocker 5 remain open.

## Scope and frozen design

The final scorer excludes fatal outcomes from slow benefit. Its independent
fixed-board diagnosis and real native/Lite red/green acceptance are preserved in
`verification/teacher_lethal_slow_20261103/REPORT.md` and
`verification/teacher_surviving_slow_20261103/REPORT.md`. The repair changes no
coefficient, forecast, poison score, four-player exposure or frozen opponent.

This is one execution of the existing 168-game design for the changed scorer:
seed 20261103, 12 complete rotation blocks / 12 scenario families per format,
eight workers, 30 turns, one-second action and ten-second first-action timeout,
six-hour deadline, validation maps only. There are 24 duel, 48 FFA and 96 team
jobs; team includes `baseline_partner` and `self_team`. No final holdout is used.
There is no retry, additional seed, extended deadline or post-result tuning.

- Source: `9118fac3628542b585a35f27d2115560057d4ddc`.
- Git archive SHA256: `79838efc62399020802684e3ff2c3dfdda78cd9780da6cfbfb1347f021d726de`.
- Ubuntu root: `/home/tongshu/acceptance/teacher_surviving_slow_green_20261103`.
- Teacher source SHA256: `ad75d870ce68fa6b489ad922fd8bb3059e29bbe7626f296e74d2b6fad828c7d4`.
- Schedule SHA256: `fcd7259ce0db646a9cfcf731cb703898b0be568cac80ccf0d6edaed4bcaf8799`.
- Identities SHA256: `262ffe0cddbf5f4d0ca6b9207d5137fb3f769338bff92f5c73df12490e47a648`.
- Full output `panel.tar.gz` SHA256: `587f71a1c1dc22e6fc8fd03f13ac9bd92a3d80e4258fd1a26408b0926726f4ed` (local/server match).

Native executable, entropy shim, rules, frozen opponent and evaluation source
hashes are recorded in `panel-r3/identities.json`. The accepted v6 extension is
used for the separate fixed-board checks; this full panel runs native Wesnoth.

## Commands and result

From the extracted source, with numerical libraries set to one thread and dummy
SDL video/audio drivers:

```sh
/home/tongshu/venv/bin/python tests/acceptance_teacher_strength.py prepare \
  --root /home/tongshu/acceptance/teacher_surviving_slow_green_20261103 \
  --output /home/tongshu/acceptance/teacher_surviving_slow_green_20261103/panel-r3 \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --source-commit 9118fac3628542b585a35f27d2115560057d4ddc
/home/tongshu/venv/bin/python tests/acceptance_teacher_strength.py run \
  --output /home/tongshu/acceptance/teacher_surviving_slow_green_20261103/panel-r3
```

Both commands exit 0. Run start to summary is 419.681 seconds. Exit 0 denotes
operational completion, not a statistical pass.

| Format | Completed | Blocks / families | Difference | 95% interval | Turn-limit outcomes | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| duel | 24/24 | 12/12 | 0 | [-0.75, 0.75] | 2 | inconclusive |
| ffa4 | 48/48 | 12/12 | -0.003472 | [-0.121528, 0.131944] | 22 | inconclusive |
| team2v2 | 96/96 | 12/12 | -0.09375 | [-0.375, 0.1875] | 29 | inconclusive |

There are zero faults, zero missing blocks and zero candidate truncations.
Separately, 53 games reach `turn_limit`; these are not natural terminal outcomes.
Team baseline-partner difference is -0.0625, interval [-0.75, 0.6875]; self-team
is -0.125, interval [-0.375, 0]. No result meets the strict CI lower-bound > 0
criterion. Inconclusive is neither a strength pass nor proof of degradation.

## Remaining acceptance decision

Correct target attribution and removal of dead-target slow reward have concrete
regression evidence. They do not establish maintained strength. The existing
evaluator tests superiority; a maintained-strength/non-inferiority target has no
declared margin. No margin was selected from these results and no gate changed.
The next strength experiment needs a resolved target and a predeclared design;
repeating this panel or adding seeds until a favorable result is not acceptance.

The archive retains the complete schedule, identities, packages, job/results,
logs and replays. Plan, execution, identities and summary are also extracted for
review. Earlier panels remain at their original paths. No collection, training
or Windows tests ran; no convergence, full-native-semantics or trained-policy
strength claim follows from this panel.
