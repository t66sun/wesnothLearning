# Restarted stock-RCA run - started and stopped without a training result

Date: 2026-10-28 (Asia/Shanghai). Source `1dc3914` (runtime add-on cap exemption).
Run directory `runs/v5_stock30h_20261028_r2` under
`/home/tongshu/myDev/wesnothLearning/formal_run_20261028_r2` on cpuServer.

## Why it restarted

The first authorized attempt (`runs/v5_stock30h_20261028`, source `a495d10`) was stopped
at 22:21 after every validation and reward-reference game failed on
`submission exceeds 16 MiB`: the student's own policy export is a 17 MB directory.
PR #83 exempted runtime add-on directories from the submission cap while keeping the
archive cap; its evidence is `verification/runtime_addon_cap_20261028/REPORT.md`.

## Startup

- Started 2026-10-28 22:24:32 (clock `started=1793197472.023425`); PID 280051;
  `setsid nohup ./launch.sh` because the server has no tmux.
- Config (`ubuntu/manifest_config.json`): 30 hours with four hours of final holdout,
  eight workers, one trainer thread, seed 20261028, lite student, native evaluation,
  stock RCA teacher, 400/400/400 stock teacher targets, `native_bc_games 0 0 0`,
  `min_distinct` 3/12/12/12, empty human pool.
- Source hashes (`ubuntu/source.sha256`): `learning/experiment.py` `1647e889...`,
  `vendor/arena/addons.py` `0379f52e...`, rules `d6fceafe...`. Environment:
  Linux 7.0.0-38, Python 3.12.3, Wesnoth 1.18.8 (`ubuntu/environment.log`).
- The launch script, clock, process record and an empty error log are in `ubuntu/`.

## Stop

The user instructed to end the training at 2026-10-28 22:32:36. PID 280051 was killed;
`ps` then reported no coordinator. At the 22:30 snapshot the three formats were still in
`stage=bc`, `version=0`, with 6 duel / 11 ffa4 / 7 team2v2 jobs and no faults. No BC
checkpoint, validation game, gate result, PPO update, convergence or strength evidence was
produced by this run.

## Limits

This report records a start and a stop, nothing else. The earlier run's label-gate
snapshots remain the only run-time BC observations, and they were early-batch and
unaccepted. The authorization for a 30-hour run was consumed by this stop; it is not
reused without a new instruction.
