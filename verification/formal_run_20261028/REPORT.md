# Authorized 30-hour stock-RCA run - startup evidence, training not finished

Date: 2026-10-28 (Asia/Shanghai). Source `a495d10` (`Exclude captured stock frames from
the native log cap`). Run directory `runs/v5_stock30h_20261028` under
`/home/tongshu/myDev/wesnothLearning/formal_run_20261028` on cpuServer. This report
records startup only; it is not a training, convergence or strength result.

## Authorization and config

The user authorized on 2026-10-28: no human replay corpus, a 30-hour CPU formal run,
400 stock teacher games per format (duel, ffa4, team2v2), and the turn cap left to the
implementation (60 turns for training games, the existing `learning/maps.py` phase rule).
The native log cap was raised to 80 MiB and captured `STOCK` frames were then excluded
from it (PR #80) after the first ffa4 corpus job failed.

Manifest config as read at 20:51 (`ubuntu/manifest_config.json`): hours 30, workers 8,
trainer_threads 1, seed 20261028, engine lite, evaluation_engine native, bc_games
400/400/400, native_bc_games 0/0/0, bc_batch_games 8, min_distinct trend 3 /
promotion 12 / final 12 / gate 12, final_holdout_hours 4, empty human pool,
rules `data/rules/1.18.8-training` (rules.json SHA-256 `d6fceafe...`).

The launch command, environment and process record are in `ubuntu/launch.sh`,
`ubuntu/environment.log` and `ubuntu/process.txt`: detached PID 275499, no tmux on the
server, `setsid nohup ./launch.sh` used instead. Python 3.12.3, torch 2.9.1+cpu,
Wesnoth 1.18.8. Source hashes: `learning/experiment.py` `1647e889...`,
`vendor/arena/match.py` `6076e365...` (LF-normalized archive copy; local working copy
hashes differ only by CRLF).

## Clock

`ubuntu/clock.json`: started 1793191774.2269685, update deadline 1793281774.2269685,
final deadline 1793299774.2269685, i.e. 20:49:34 on 2026-10-28, 21:49:34 on 2026-10-29
and 02:49:34 on 2026-10-30 Asia/Shanghai. H=4.

## Startup checks

- `ubuntu/startup.log` is empty at the read: no traceback, no trainer error.
- `ubuntu/jobs_snapshot.json` at 20:51: duel 5/5 complete, ffa4 6/6 complete,
  team2v2 3/3 complete, zero errors. The ffa4 jobs include the shape that previously
  exceeded the cap and now complete.
- No `trainer_error.log`, `errors.log` or `infrastructure_error` file existed under the
  run directory.
- `runs/v5_stock30h_20261028/` contains `manifest.json`, `clock.json`, `scheduler.jsonl`
  and one directory per enabled format.

An earlier start at 20:45 was stopped and its directory removed after job
`stock-00003-ffa4-t0` failed with `native log exceeds 80 MiB`; its 81 MiB log held 1,466
`STOCK` capture lines. That defect and its Ubuntu acceptance are recorded in
`verification/stock_frame_log_weight_20261028/REPORT.md`.

## First committed BC update

At the 20:55 read each format had `stage=bc`, `version=1`, `batch=1` and a fresh
`latest.pt` (about 9.1 MB), so one valid collection batch trained and committed per
format. History batch 0 losses: duel 4.314, ffa4 4.099, team2v2 3.924.

The same read shows the BC gate is **not passed yet** and reports `insufficient_design`:
8 distinct scenarios (floor 12), corpus 8/400 games. Coverage of engine decisions:
duel 793/853 = 0.930 (passes the 0.9 all-action floor), ffa4 2160/2458 = 0.879 and
team2v2 1662/1924 = 0.864 (both below it); recruit coverage is 1.0/1.0/0.996, move
0.891/0.813/0.784, attack 0.964/0.93+/0.86+ (full values in `ubuntu/first_update/`).
Imitation is not effective yet in any format. These are early-batch facts, not a code
defect claim: the run is still collecting toward 400 stock games per format, and the
unmatched move/attack events are the mechanisms R8b named (candidate budget and moves
absent from the generator selection). Whether the ratios clear 0.9 as the corpus grows is
unmeasured here; the gate is unchanged and is reported, not waived.

`ubuntu/first_update/` holds the three `bc_gate.json` and `state.json` snapshots.

## Limits

- Training was still running when this report was written; no BC/PPO counters, checkpoint
  quality, gate result or final evaluation exists here.
- The separate reduced chain L1 was not run; this run's first batches are startup evidence,
  not L1 acceptance and not learning evidence.
- The run does not prove convergence, strength, capture noninterference or corpus
  sufficiency; the 400/400/400 targets may underfill and would be reported as underfill.
