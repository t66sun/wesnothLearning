# Agent Training Operations Guide

> Language: English | [中文](instructions_zh.md)

Updated 2026-10-23. For agents taking over startup, maintenance and instruction-driven tuning. Architecture and current parameters are authoritative in [architecture.md](architecture.md); implemented-but-unaccepted items and minimal plans are in [TEST.md](TEST.md); historical acceptance evidence is linked from the architecture document. This file gives operational steps and does not duplicate architecture status or the full hyperparameter table.

## 1. Determine the task first

Read the root `AGENTS.md` first, then read the matching chapter below:

| User instruction | Steps | Done when |
| --- | --- | --- |
| Start new training | 2–4 | Config matches the authorization, the training process is alive, and at least one valid collection batch and checkpoint exist; creating only a manifest is not a successful start |
| Continue / resume training | 2, 5 | The original experiment's config, weights, optimizer, RNG state and original deadline are restored and progress is confirmed |
| Check progress, maintain, diagnose | 6–7 | Current phase, valid sampling/update progress, fault evidence and necessary action are reported; config stays unchanged |
| Tune parameters on instruction | 8 | Only the named format/fields change, actual effective values and versions are verified, before/after is recorded |

With explicit authorization, complete the operation without asking again step by step. Reading this guide, tidying docs or checking status does not authorize starting training. A maintenance task does not implicitly include changing rewards, lowering gates, expanding sampling or swapping models. Automatic adjustment by the default adaptive controller within its established range continues per the original experiment.

## 2. Environment and working directory

The primary environment is the Ubuntu CPU server. Usually connected from this machine:

```bash
ssh cpuServer
```

Use existing SSH config or the user-provided authentication; passwords never go into docs, commands, logs or scripts. When the alias is unavailable in the execution environment, the known endpoint is `tongshu@192.168.122.118`.

On the server:

```bash
project=/home/tongshu/myDev/wesnothLearning/WesnothLearning
python=/home/tongshu/venv/bin/python
wesnoth="$project/.runtime/install/bin/wesnoth"
cd "$project" || exit 1
export PYTHONPATH="$project"
export PATH="/home/tongshu/.cargo/bin:$PATH"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
```

This is the main project holding recent changes; `releases/v5_completion_20261020` is a historical isolated working directory. Resuming an old experiment uses its matching sources; do not mix the two directories just because the paths look similar. The server uses the absolute Python path above; the repository `run.sh` uses `.venv/bin/python`, so use the wrapper script only after confirming that virtual environment is valid. An existing environment does not need setup again.

A quick self-check verifies only the environment and identity, without launching the game:

```bash
"$python" -m learning run --help
"$wesnoth" --version
"$python" -c 'import sys, torch, _engine_lite; print(sys.executable); print("torch", torch.__version__); print("CUDA", torch.cuda.is_available()); print("lite", _engine_lite.__file__)'
```

Native should be 1.18.8 and the project frozen entry requires PyTorch 2.9.1. The CPU server defaults to 8 global game workers with 1 thread per trainer, and the three trainers share those 8 workers. Windows is reference only; no full Windows acceptance is planned.

The 2026-10-22 per-seat candidate optimization added decision parameters to the Rust extension; before using the new sources, rebuild `_engine_lite` in the matching virtual environment instead of only copying Python/Lua files. That change and the 300/600/400, 8-worker defaults passed restricted Ubuntu acceptance T1–T4 on 2026-10-22 (including the real 8-worker chain and peak PSS 4.02 GiB); conclusions and evidence are in architecture.md section 8 and `verification/pretrain_acceptance_20261022/`. Starting formal training still needs a later explicit user instruction.

The current implementation as of 2026-10-23 is schema 5 / candidate v3. The Ubuntu isolated directory `/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022` has completed the minimal phase-wiring and resume acceptance and uses its own `.venv/bin/python` (shared installed dependencies, its own newly compiled extension). If the main directory has not yet synced the fixes, verify entries in that isolated directory or deploy the accepted sources first and rebuild the matching environment; the deployment record is in the repair report. Rust embeds `engine_lite/lua/host.lua` via `include_str!`, so copying Lua alone does not update an installed extension. The original 20-hour formal experiment has ended in failure and old schema 4/v2 checkpoints only work with their original matching sources; new and old corpora/checkpoints are never mixed. Restricted movement quality acceptance is archived in the [follow-up report](../verification/bc_rootcause_20261023_2318/REPORT.md); the real full BC gates still run as usual.

## 3. Verify the actually runnable scope before starting

New experiments use lite by default, with rules defaulting to `data/rules/1.18.8-training` (587 units, 438 terrains). The startup gate verifies the actual 158-unit closure of the six factions, accepts recorded approximations and rejects unsupported types and missing references; whole-package semantics/performance flags keep their original values. All three formats use the frozen real Astra teacher; accepted scope and evidence are in architecture.md section 8.

The default directory is usually enough. Captured inputs moved under `data/` on 2026-10-24, so a checkout predating that move keeps `rules/`, `datasets/`, `humanData*`, `opponents/` and `references/` at the root: move them into `data/` before running, or the defaults no longer resolve. When the user specifies another frozen package, pass it:

```bash
rules_dir="$project/data/rules/1.18.8-training"
# add --rules-dir "$rules_dir" to the new training command
```

`--rules-dir` binds features, jobs, adapters and the manifest at once and takes precedence over the environment variable; without an explicit parameter `WESNOTH_RULES_DIR` may be used. The programmatic API passes `config.rules_dir`. Resume automatically uses the original manifest's directory and must not be pointed at the newest package.

The default rule identity is `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`; the 10 formal maps are frozen in `data/rules/1.18.8/maps`. When capturing a new package use `python -m engine_lite.capture --maps-dir data/rules/1.18.8/maps` plus the other required parameters, keeping map composite terrains. After changing the rule hash/vocabulary, start a new experiment; historical weights keep their original matching schema.

Pass criteria: the rule hash matches `features.schema()`, the six-faction closure has no missing/unsupported declarations, the maps and Astra exist, and the chosen format really has a teacher chain; reuse evidence when existing validation is valid and run one affected minimal check only if the wiring code changed. Handling of strict statistical precision, peripheral campaigns and package limits is bounded by the architecture document and must not re-expand into a full test task.

## 4. Create and start training

First establish the user-specified formats, device, duration, workers and experiment name. Default collection specification is in architecture.md section 5.1; the numbers are valid-teacher-game targets, and filling them also requires passing the BC quality/coverage/opening gates. Verify the generated config matches the authorization.

Below is the template for an **authorized new 18-hour CPU three-format pure lite experiment**; replace items when the user specifies another duration or formats:

```bash
run_dir="runs/v5_$(date +%Y%m%d_%H%M%S)"
test ! -e "$run_dir" || exit 1
mkdir -p runs/logs
set -o pipefail
"$python" -u -m learning run \
  --run-dir "$run_dir" \
  --engine lite --evaluation-engine lite \
  --bc-games 300 600 400 --native-bc-games 0 0 0 \
  --device cpu --workers 8 --trainer-threads 1 \
  --hours 18 --formats duel ffa4 team2v2 \
  --wesnoth "$wesnoth" \
  2>&1 | tee "runs/logs/${run_dir##*/}.log"
```

The experiment directory must be created by the program; do not `mkdir "$run_dir"` beforehand. Logs go to `runs/logs/` outside it. Omitting engine parameters means lite; pass `--engine native` explicitly for native-only, where the native teacher floor defaults to the matching total target. Native anchors are not collected by default and the final comparison is also lite-only against Astra; native play-strength evaluation runs separately and explicitly. `--bc-games` sets the three-format total target while the native quota is controlled by `native_bc_games`.

Long tasks belong in an existing persistent terminal; with tmux, run `tmux new -s wesnoth-v5` first, set up the environment and start command inside, detach with Ctrl-b, d, and reattach with `tmux attach -t wesnoth-v5`. Record the session, main PID, full command, log and experiment directory, and confirm that dropping SSH does not end training. Do not let a short-lived SSH tool request hold the whole long experiment.

Post-start checks:

- `manifest.json` `config` matches the instruction, with correct rule/architecture/vocabulary and engine binding.
- `clock.json` start and deadline match this budget; by default updates are allowed for the first 10/12 of the duration and the last 2/12 are frozen evaluation.
- Every enabled format has `hardware.json`, `state.json`, `latest.pt`, and at least one valid collection batch keeps advancing `jobs.jsonl` and training counters.
- No `trainer_error.log`, `errors.log` or persistent `infrastructure_error`; phase and teacher identity are as expected. Report a failed start as a failure instead of substituting a background PID for progress.

This guide does not prescribe a default pre-flight rerun of 277 tests, the 30-block performance matrix or large-sample combat statistics.

## 5. Resuming existing training

**Active continuation, 2026-10-24:** work from `/home/tongshu/myDev/wesnothLearning/validation_memory_repair_20261024_1321`, run `runs/v5_lite_resume_20261024_1420`. The detached wrapper PID is initially 200356, coordinator 200357; read `launch.json`, `continuation.log`, per-format states and scheduler events for current identity/progress. The original `validation_training_repair_20261023_194022/runs/v5_lite18h_20261024_003512` stays stopped and supplies historical corpus/policies: do not delete, move or resume it. PPO updates end at 18:50:52 and the wrapper then requests final evaluation within the **22:30 Asia/Shanghai** total deadline. Do not start a second wrapper or create another phase override while this one owns the continuation. If the wrapper exits with failure, inspect evidence before resuming; do not relaunch the one-time migration. Its final-stage call has not yet occurred at handoff. Full lineage and recovery checks are in the [continuation report](../verification/training_resume_20261024_1415/REPORT.md).

`runs/v5_20261021_203930` stopped at 2026-10-21 21:48 because two trainers hit OOM and its data and checkpoints are retained; after the read-path fix and acceptance, `runs/v5_20261022_000850` started at 2026-10-22 00:08 and was stopped by user request at 01:03:45. The most recent pure lite / 6000×3 / 18 h experiment `runs/v5_lite6000_replay_20261022_012336` was stopped by user request at 2026-10-22 06:53:44 without reaching PPO; its originally planned 19:23:37 deadline does not mean it is still running. Stop status is in architecture.md section 1 and historical issues in its archive reports; do not resume or create training without a new instruction. Old experiment source hashes have changed, so a direct resume triggers `verify_frozen`; only handle it as a controlled migration when the user explicitly asks, keeping the original manifest and budget.

Inspect the original experiment's manifest, clock, latest checkpoint and error records first, confirm no active main process in the same directory, then run against matching sources, environment and rules:

```bash
run_dir=runs/<user-specified experiment directory>
test -f "$run_dir/manifest.json" || exit 1
"$python" -u -m learning run --resume "$run_dir"
```

`--resume` uses the device, workers, formats, sampling targets and original deadline frozen in the manifest. Appending `--hours`, `--workers`, `--bc-games` and similar does not change an existing experiment; when the budget has expired, resume goes to evaluation/finish and does not gain new budget automatically.

Confirm that checkpoints, optimizer, RNG, reward controller and unfinished batches are restored and counters keep growing. On `source changed`, `manifest changed` or rule/vocabulary mismatch, diagnose with the original matching version and keep the original manifest and checksums. New config/new architecture means a separate experiment per user instruction or an explicit migration, never editing frozen files to pretend it was an unchanged resume.

`run.lock` is a file lock; an existing file does not mean it is running. On `already running`, identify the lock holder first and never start a second process in the same directory by deleting the lock file.

The 2026-10-24 rolling reward-window fix has passed isolated Ubuntu acceptance but is not deployed to the active continuation's frozen source. Do not copy the new `control.py` into that directory or rewrite its manifest. Apply it to a new run or an explicitly authorized controlled migration; the [acceptance report](../verification/reward_window_fix_20261024_1607/REPORT.md) records the exact code and evidence.

## 6. Daily maintenance and progress judgement

### Running BC, PPO and final evaluation separately

These entries apply to new experiments matching the current schema/sources. Finished schema 4 experiments cannot be resumed directly with schema 5. The default `run` is still the auto flow; for BC only, create the experiment with `--phase bc`; after BC passes or the phase budget ends it is saved as `bc_complete` and PPO/final evaluation never start automatically.

```bash
"$python" -m learning run --run-dir runs/new_bc --phase bc --hours 4
"$python" -m learning phase show --run-dir runs/new_bc
# A normal switch requires the BC gate to have passed; --formats selects a subset.
"$python" -m learning phase ppo --run-dir runs/new_bc --hours 8
# Only use under an explicit user override: keeps failed gate results, records the reason, does not change effective.
"$python" -m learning phase ppo --run-dir runs/new_bc --force --reason 'user explicitly asked to end BC' --hours 8
"$python" -m learning run --resume runs/new_bc
"$python" -m learning phase evaluate --run-dir runs/new_bc --hours 2
"$python" -m learning run --resume runs/new_bc
```

The normal/forced PPO commands above are alternatives. The command writes a phase request first: a running trainer reads it after finishing the current batch; a stopped experiment needs a later resume and no second process may be started against a still-locked experiment. On resume, existing `pending_train` finishes with its frozen method before the new phase samples. PPO end is saved as `ppo_complete` and final evaluation must be requested explicitly. Formal BC/PPO sample, reward-version and rehearsal requirements still apply; a force override guarantees no training quality and invents no BC data.

`run --phase bc --hours 4` gives BC the full 4 hours with no time reserved for automatic final evaluation. `phase --hours` allocates this request's phase deadline, measured from the request time and persisted in the checkpoint; the original manifest/clock are untouched. Omitting it reuses the remaining time of the original total budget (auto reuses the original update deadline), and an expired budget requires an explicit new phase duration. A normal `run --resume --hours` still does not extend the budget. Once final evaluation starts, the directory cannot return to training; a new experiment is required. Phase commands never start or resume training themselves and do not bypass source/schema frozen checks.

Read enough state for an existing experiment in one pass; widen the scope only on the first check or a real anomaly. Confirm the manifest exists before looking at the controller so no control directory is created for a nonexistent experiment path.

```bash
test -f "$run_dir/manifest.json" || exit 1
"$python" -m learning control show --run-dir "$run_dir"
```

| File | What to read and conclude |
| --- | --- |
| `phase/*.pending.json`, state.phase_history | Phase requests, reason, independent deadline, whether explicitly forced and application records; a queued command is not a completed switch |
| `manifest.json`, `clock.json` | Actual config, source/opponent/vocabulary identity, update and final deadlines |
| `<format>/state.json` | stage, batch, version, effective, counters, pending_train/pending_validation, error; read only needed fields since history may be large |
| `<format>/jobs.jsonl` | Recent task status, faults, training_eligible, teacher coverage, engine and phase; count valid games rather than file lines |
| `<format>/bc_gate.json` | Whether corpus size, imitation quality, candidate coverage and opening behavior each pass |
| `<format>/validation/*.json` | Distinguish trend/promotion, native/lite and teammate context; a small-panel win is not final strength |
| `<format>/latest.pt`, `last_bc.pt`, `last_ppo.pt` | Whether the checkpoint updated and matches state and current phase; best/selected are selection results, not a substitute for latest when restoring |
| `control/*.json`, `control/events.jsonl` | Current config, pending commands, applied sequence, reward_version, last_error, metrics_error (adaptive is frozen when non-empty) |
| Main log, `scheduler.jsonl`, `trainer_error.log`, `errors.log` | Whether tasks still complete, which format/phase failed, the actual stack trace |

A non-growing BC game count is not necessarily stuck: when the quota is full but quality has not passed, learning continues on existing data and sampling is added only past the plateau. Short collection phases may legitimately not update weights. Judge from the latest task completion time, pending batches, optimizer_steps and checkpoint time; high CPU utilisation alone proves neither speed nor a fault, so look at valid games/hour, CPU core-seconds/game, memory and timeouts first.

Maintain only the processes and files this task owns. Routine maintenance may resume the same config and keep fault evidence within existing authorization; do not change workers, rewards or gates just because utilisation looks low. When longer supervision is needed, use the user-authorized task scheduling capability instead of unbounded polling within one check.

## 7. Stopping and fault handling

On a stop request, record the latest resumable checkpoint, unfinished batches and the target main process, then send Ctrl-C in its persistent terminal; confirm the coordinator, trainers and this experiment's game subprocesses exit. The current coordinator terminates trainers on KeyboardInterrupt and **offers no graceful pause that saves every in-flight step before exiting**, so only progress already on disk is guaranteed; verify the checkpoint loads afterwards.

When sending signals, confirm ownership by PID, parent/child relation, command and experiment directory and handle this experiment's processes one by one. Never run global cleanup by `python` or `wesnoth` name and never delete data, checkpoints or lock files to "unstick" something.

| Symptom | Minimal action |
| --- | --- |
| Rule directory/vocabulary mismatch | Compare environment variable, job.rules_dir, schema and rule hash, fix the actual wiring, never edit the hash to bypass |
| Lite four-player teacher failure | Compare `four.lua` dependencies and teacher identity; self-play must not pass as teacher collection |
| `infrastructure_error` or teacher query failure | Read the task error and teacher-returned reason first; distinguish sampling faults from correction labels allowed to skip |
| No new progress | Distinguish collection, learning on full BC data, validation/final evaluation, deadline, active workers and errors; locate with one concrete failure |
| OOM/timeout | Record concurrency, memory and failed tasks at the time; change the next experiment's config per authorization, never fake changes with resume parameters on an existing run |
| Parameter-count/real rule smoke failure | Check the current vocabulary and rule hash; capacity follows the vocabulary and tests must use the current feature directory |

After a fix, rerun only affected failed/new minimal cases and reuse accepted evidence. New output goes to a new `verification/<date or task>/`, keeping both the initial failure and the post-fix result. Routine maintenance does not modify the installed game AI, historical V4 weights or other experiments.

The user-authorized archive cleanup finished on 2026-10-23: the server `runs/` now keeps only the two formal trainings `v5_lite20h_20261022_210712` and `v5_lite6000_replay_20261022_012336` plus their logs. Earlier trainings, V4 artifacts and old loopbacks are in `/home/tongshu/myDev/wesnothLearning/training_archives/20261023_212221/`. When a historical run path is missing, check that directory's `index.json`, verify the needed archive against `SHA256SUMS`, then unpack it back to the original project root per its README; archives keep full relative paths and never overwrite a newer experiment with the same name. Restores still use that experiment's original schema, frozen sources and budget; archiving does not reset training eligibility or clocks. This was a one-time cleanup with no automatic deletion task installed; details are in the [archive report](../verification/training_archive_20261023/REPORT.md).

## 8. Tuning parameters on instruction

First turn the instruction into: experiment directory, format, fields, target values, reason and observation window. Use the user-given values; if only research or evaluation was requested, report the basis first and do not tune. After approval change only the named items, keep the rest of the config, and never fake play-strength progress with higher shaping scores or lower BC gates.

### 8.1 Hot-updatable at batch boundaries

| Field | CLI | Allowed range |
| --- | --- | --- |
| economy | `--reward-economy` | 0.05–0.20 |
| control | `--reward-control` | 0.02–0.15 |
| explore | `--reward-explore` | 0–0.15 |
| mode | `--reward-mode` | fixed / scheduled / adaptive |
| entropy coefficient | `--entropy` | non-negative finite |
| BC auxiliary coefficient | `--bc-aux` | non-negative finite |

Use the existing control queue; never write state/checkpoint/config directly. The variables below must be assigned from a user instruction first; the example changes only the named format's exploration coefficient:

```bash
: "${run_dir:?specify an existing experiment}"
: "${target_format:?specify duel/ffa4/team2v2}"
: "${target_explore:?fill in the user-specified exploration coefficient}"
: "${change_reason:?record this user instruction and the reason for the change}"
test -f "$run_dir/manifest.json" || exit 1
"$python" -m learning control show --run-dir "$run_dir"
"$python" -m learning control set \
  --run-dir "$run_dir" --format "$target_format" \
  --reward-explore "$target_explore" --reason "$change_reason"
```

The returned command ID only means queued; wait for that format to finish its current batch, then check `control show` pending, actual config and applied sequence, and verify old/new values, reason and the incremented reward_version in events. Games already started keep the old frozen config and only later batches use the new version. One PPO update cannot mix reward versions.

To pause automatic tuning, switch that format's mode to fixed only when the user asks; manually changing one coefficient does not disable adaptive. Roll back the same way by queuing the old value with a reason, never deleting or rewriting the event chain.

### 8.2 Not hot-changeable on an existing run

workers, device, formats, total budget, BC game count/native anchors, model structure/vocabulary, sequence window, epochs, learning rate and PPO clip are not hot-update fields of the current control API. Adjust a new experiment's config per the user instruction or implement a compatible migration, and update the architecture document; never push them into `control set` or claim a resume parameter already took effect.

In particular: `learning_rate` currently initializes the BC optimizer while the PPO path sets 1e-4. Changing the PPO learning rate per user request means editing the code that actually owns that phase and doing a minimal verification, not just editing the initial config. Sampling quotas are the same: `bc_games` is the total valid teacher games, `native_bc_games` the native target, `bc_records` the decision limit per read, and the three are never conflated.

After each change, verify the actually effective config, then record old→new, user basis, command/event ID, effective batch/version, follow-up observations and rollback. Compare by default on valid sampling throughput, fault rate, BC sub-scores and same-engine/same-format validation; formal strength still rests on native evaluation.

## 9. Reporting and handover

Keep reports short and at least include:

```text
experiment/source directory, persistent session or main PID, log location:
formats/engine/device/global workers, rule and architecture identity:
per-format phase, valid teacher games/target, optimizer_steps, latest checkpoint:
actions completed and actual verification results:
tuning (if any): user basis, old→new, event ID, effective batch/version:
current faults or limits, next executable action:
```

Architecture/parameter/implementation status changes and acceptance evidence links go into [architecture.md](architecture.md), while [TEST.md](TEST.md) keeps only implemented-but-unaccepted items and minimal plans. Actual commands, results, source/rule identity and logs stay in dated `verification/` reports or the corresponding run; after passing, delete the whole item from the pending-acceptance list per the root AGENTS.md rules. This guide changes only when an operational entry or maintenance flow changes; do not start parallel plans or overwrite historical reports as new conclusions. Final export and installation are executed separately per user instruction, and finishing training never replaces the installed AI automatically.
