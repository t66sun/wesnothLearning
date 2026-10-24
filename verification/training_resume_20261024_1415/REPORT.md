# Checkpoint-preserving continuation — 2026-10-24

The user requested recovery of the interrupted training and a total deadline of
2026-10-24 22:30 Asia/Shanghai. This is a continuation of schema-5 PPO, with the
accepted collector memory and coordinator shutdown repairs. It is not a fresh BC
run or a new BC qualification claim.

## Active location and controls

Source root:
`/home/tongshu/myDev/wesnothLearning/validation_memory_repair_20261024_1321`

Run: `runs/v5_lite_resume_20261024_1420`.
Detached continuation wrapper PID/PGID: **200356**; initial coordinator **200357**.
Started 14:20:14; inherited CPU, lite/lite, 8 global workers, 1 trainer thread,
300/600/400 teacher targets, 0 native anchors, seed, reward configuration, trainer
memory guard, minibatch, epochs, validation cadence and BC rehearsal settings.

Clock retains original start 00:35:14.067086, with the authorized total duration
extension: PPO update deadline **18:50:52.344514**, total deadline **22:30:00**.
The original 10/12 update + 2/12 final-evaluation split is retained. All three
formats use explicit PPO to the update deadline; `continue_run.py` waits for
successful `ppo_complete` states, requests `phase evaluate` through the existing
API without extra hours, and resumes final evaluation within the shared deadline.
Failures stop the wrapper and remain visible; there are no automatic retries.
Final evaluation has not occurred at handoff and full evaluation completion or
play strength is not claimed.

Inspect `launch.json`, `continuation.log`, `scheduler.jsonl`, each format's
`state.json`/`latest.pt`, and any new `errors.log`. A stale failed state can remain
on disk until the first recovered collection saves; inspect the new scheduler
and checkpoint timestamps rather than treating the copied old error as a new
failure. Do not launch a second wrapper or another phase command concurrently.

## Preserved parent and migration boundary

Parent source root:
`/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022`

Parent run: `runs/v5_lite18h_20261024_003512`.
The parent remains stopped and unchanged. Its absolute teacher/DAgger corpus and
historical policy paths remain required read-only inputs of the continuation.
Do not clean up or move the parent, its environment or its rule package.

The new manifest was created by the existing `freeze` function from accepted
sources. The original manifest was neither edited nor rebound in place. A new
checkpoint derivative binds the new manifest and extended clock; original model,
optimizer, Python/Torch/CUDA RNG, architecture, features, runner history, counters,
reward-controller state and eligibility are asserted unchanged. Source pointers
and SHA-256 lineage are in `migration.json`; the real `FormatExperiment(...,
resume=True)` loader and `Experiment(..., resume=True)` frozen-source verifier
both passed before launch. Actual checkpoints, not `best` or `selected`, were
used for optimizer continuation.

| Format | Restored version | Optimizer steps at restore | BC effective | PPO provenance |
| --- | ---: | ---: | --- | --- |
| duel | 212 | 2173 | true | Normal gate; normal PPO phase request at recovery |
| ffa4 | 88 | 1772 | false | Original user-authorized 08:00 force request, applied at v63 |
| team2v2 | 50 | 695 | false | Original user-authorized 08:00 force request, applied at v41 |

FF4/2v2 force reasons, command IDs and phase histories remain intact. Only their
active PPO deadlines were extended; `effective` was not changed. Duel's normal
phase command has no force flag. The wrapper explicitly enters final evaluation
after PPO instead of switching unqualified formats to `auto`, which would return
them to BC.

All restored checkpoints have no pending optimizer update or validation. The
interrupted collection is recollected in the derivative directory with the same
batch index; its old results and frozen schedule stay in the parent. The new log
keeps historical evidence but omits results from that uncommitted batch, including
three complete games never committed by a training update and five infrastructure
errors. These exclusions are individually recorded in `migration.json`. No
completed optimizer update or teacher corpus was discarded, and no failed game
was relabelled successful.

## Compatibility and minimal validation

`inspect.ubuntu.txt` confirms no prior training processes, about 14.4 GiB initial
available memory, enough disk space, original checkpoint identities and phase
provenance. `compatibility.ubuntu.txt` confirms unchanged model, training loss /
optimizer algorithm, feature definitions and gameplay Lua; the experiment code
diff is only the default dataset path. Embedded host.lua differs by an empty
trailing line, and uses the previously accepted compiled extension. Accepted
memory/shutdown tests and heavy replay pressure results are reused from their
original reports; they were not rerun.

`migrate.ubuntu.txt` records a preflight filename error (`lua/memory.lua` does not
exist); it exited before creating the destination. The corrected
`migrate_v2.py`/`migrate-v2.ubuntu.txt` performs the actual migration and assertions,
including exact original frozen-source hashes, schema/architecture/format checks,
finite model/optimizer tensors, restored RNG, exact optimizer tensor equality,
real resume loader checks and unchanged original checkpoint hashes afterwards.
`launch.ubuntu.txt` also passes normal frozen-source `Experiment` resume.

Live checkpoint and memory snapshots are preserved in `progress-*.ubuntu.txt`.
The initial scheduler reaches 8 live games; new jobs complete and write eligible
shards. `status-start.ubuntu.txt` / `status-progress.ubuntu.txt` find no kernel OOM
since 14:15 and no newly written errors. These are bounded observations, not a
claim that all future training or final acceptance will succeed.

Frozen rule SHA-256:
`d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`.
Parent manifest SHA-256:
`43cd83777cd213771cf7e574143a848020dcd975b073763c143fe66048de1bf3`.
Derivative manifest SHA-256:
`8ec090d7b5626a093695a5f94fb6a809f5d7bb0f252aaf49af73067cc0140569`.
Full parent/migrated checkpoint hashes and clocks are in the captured
`migration.json`; initial `manifest.json`, `clock.json` and `launch.json` are raw
copies. Original latest checkpoint hashes are rechecked in the progress snapshots.

This task changes operational recovery evidence and maintained status documents;
it adds no general migration CLI, changes no learning semantics or BC read-share
allocation, and reruns no unrelated acceptance suite. TEST.md keeps only its
existing unaccepted native terminal-state capture item.

## Handoff observation

At 14:27:36, duel advanced v212 → v216 and optimizer 2173 → 2188;
FF4 advanced v88 → v89 and optimizer 1772 → 1777. Both have new eligible
rollouts and error=null. FF4 later reaches its v90 validation schedule.
Team2v2 has two eligible complete new rollouts; g1/g3 are still processing and
its copied on-disk checkpoint has not yet saved a new update. A five-second
read-only worker sample at 14:28:37 shows active CPU work, including the two long
trajectory workers, with no new error file; see `live-workers.ubuntu.txt`.
The 14:27 process group PSS is 6.20 GiB, host MemAvailable 7,812 MiB, swap stays
at the initial 174 MiB. First recovered team2v2 optimizer advancement is therefore
not yet claimed by this snapshot.
