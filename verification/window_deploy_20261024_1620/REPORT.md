# Best-checkpoint continuation with window repair — 2026-10-24

User instruction: pause the current training, deploy the accepted reward-window
repair, continue from the strongest recent usable checkpoint, and extend the
training's total deadline to tonight at 24:00: **2026-10-25 00:00 Asia/Shanghai**.

## Active run

Source root: `/home/tongshu/myDev/wesnothLearning/validation_window_fix_20261024_1630`.
Run: `runs/v5_lite_windowfix_20261024_1630`.
Detached wrapper PID/PGID **202233**, initial coordinator **202234**.
Started **16:31:29**. Inspect `launch.json`, `continuation.log`, `scheduler.jsonl`,
per-format `state.json` and `latest.pt`. The wrapper runs PPO, requires successful
`ppo_complete` states, then queues final evaluation with the existing phase API.
It adds no evaluation hours and stops on failure.

Original start **2026-10-24 00:35:14.067086** is retained. Extended total deadline
**2026-10-25 00:00:00**; original 10/12 update + 2/12 evaluation split gives PPO
cutoff **2026-10-24 20:05:52.344514**. Clock/config are derived explicitly; normal
`run --resume --hours` was not used to pretend to extend the old frozen budget.

CPU, lite/lite, 8 global workers, one trainer thread, 300/600/400 teacher targets,
zero native anchors, seed, learning/reward settings, real BC eligibility and
existing FF4/2v2 forced-PPO reasons/command IDs are preserved. Actual reward
coefficients are still version 0 at startup. Automatic updates follow the repaired
controller at its existing boundaries; no manual tuning command was issued.

## Pause and checkpoint selection

Parent: `/home/tongshu/myDev/wesnothLearning/validation_memory_repair_20261024_1321/runs/v5_lite_resume_20261024_1420`.
Its wrapper was stopped before interrupting its own group, preventing accidental
entry into final evaluation. Trainers received SIGINT to save; remaining waiting
coordinator/workers were terminated after a bounded wait. At **16:21:48** no live
members of that recorded group remained. Atomic saved checkpoints loaded normally.

| Format | Stopped latest | Selected checkpoint | Selected optimizer step | Selection basis |
| --- | ---: | --- | ---: | --- |
| duel | 277 | parent duel/best.pt, v100 | 1780 | Retained promoted champion with full optimizer/RNG |
| ffa4 | 111 | parent ffa4/best.pt, v100 | 1820 | Latest retained complete promotion-best checkpoint |
| team2v2 | 60 | parent team2v2/latest.pt, v60 | 746 | No promoted best exists; latest legal complete fallback |

"Best" follows the experiment's existing promotion/champion checks, not the
largest small-panel score. Duel v200's direct champion panel has difference
+.625, 95% interval [-.125, 1.375], status inconclusive, so it never replaced v100.
Later good trend exports lack a complete matching optimizer/RNG checkpoint and
are not silently assembled into a hybrid resume. FF4 v100's 12-block Astra panel
still scores below Astra; best among saved candidates does not mean strong AI.
Team2v2 v60 is explicitly **not** claimed to be proven strongest. Single-block
v50/v60 score differences on changing panels do not establish a superior model.

Duel/FF4 history and counters deliberately resume from their selected v100 state,
not from the stopped latest counters. Original v277/v111/v60 checkpoints and all
later trajectories/results stay intact in the parent. This rollback is traceable
in `migration.json`; nothing is deleted or relabelled as a success.

## Deployment and minimal recovery verification

A new isolated source tree copies the parent's frozen sources and applies exactly
one production difference: the accepted `control.py` loop-condition repair.
The installed environment/compiled engine are reused because neither Rust nor
embedded Lua changes. Directory links retain the same captured rules/teacher.

The initial source-copy attempt failed because optional `benchmarks/` is absent;
`deploy.ubuntu.txt` preserves that failure, and the partial `_1622` directory is
not used. `deploy_v2.py` copies only existing directories into the new `_1630`
root and compares every frozen source tree, permitting only the controller hash
change. Parent source and manifest are untouched. No acceptance suite was rerun;
the prior [14-check Ubuntu acceptance](../reward_window_fix_20261024_1607/REPORT.md)
remains valid for this exact patch.

`migrate.py` freezes a new derivative manifest, validates selected checkpoint
schema/architecture/format, finite model/optimizer tensors and restorable RNG,
and requires no pending train update. It retains frozen teacher/reward-reference
evidence but excludes future on-policy results and post-selected validation from
the derivative job log. Historical files remain at their original absolute paths.

The v100 best checkpoints were saved during validation before its bookkeeping
completed. Their already-complete validation schedules/results are replayed
through real `FormatExperiment.validate_model`, using a collector that raises
if any new game is requested. This clears pending validation and reconstructs
selection/control metadata without repeating those games. Actual model, optimizer
and Python/Torch RNG equality to each selected checkpoint is asserted afterwards;
versions, eligibility and forced-PPO provenance stay unchanged. The actual normal
resume loader and `verify_frozen` pass with the new source root.

`migrate.ubuntu.txt` records all assertions and `launch.ubuntu.txt` verifies the
actual loaded controller path and frozen repaired hash before detaching. The
migration never edits the parent manifest, clock, source or saved checkpoints;
progress probes recheck these identities after launch.

## Progress evidence and handoff limits

At 16:36:28, new duel PPO progressed v100→v102 / optimizer 1780→1786; FF4 progressed
v100→v101 / 1820→1822. Both have new eligible rollouts and no error. Team2v2 had
two completed eligible new games and two still processing, with its saved v60 /
746-step state not yet advanced at that snapshot. The shared scheduler reached
8 live games. Process-group PSS was 6.04 GiB, host MemAvailable 7892 MiB and swap
174 MiB. See `progress-start.ubuntu.txt` and `progress-check.ubuntu.txt`.

These bounded startup checks establish real collection and updating for the
observed stages; they do not claim future final evaluation completion or better
play strength. Any later optimizer confirmation is a separate dated handoff file.
Do not restart a parent, start a second wrapper or alter the phase/deadline while
this wrapper owns the continuation. Both parent roots and the original
`validation_training_repair_20261023_194022` environment/rules/corpus/policies
remain required and must not be moved or cleaned up.

Rule SHA:
`d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`.
Patched controller SHA:
`2d79571785ab3ebd1b4299653791b78e7a3f85c3cf9338684de855a3c858d1a9`.
New manifest SHA:
`1ceea35797063f5eb44ede68707826540c4bcd372d9faa2424e856233ac54a3ee`.
The raw manifest, migration, clock and launch records are captured beside this
report. TEST.md's already accepted scopes are not reopened; T6 remains pending.
