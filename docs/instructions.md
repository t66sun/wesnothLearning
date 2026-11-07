# Agent Training Operations Guide

> Language: English | [中文](instructions_zh.md)

See the [architecture](architecture.md) for runtime contracts and parameters, and the [acceptance list](TEST.md) for pending checks.

**Current route:** every manifest freezes the sole custom teacher package `gpt6astra` and its lineage, so teacher games, DAgger corrections and exports carry one identity. Lite is the default engine and the default evaluation engine, so a fresh run collects lite Astra teacher games (`native_bc_games` 0) and its final comparison is lite Astra; official-baseline seats stay native-only. Capabilities and limits are in architecture.md §4–§5.

Current lite combat/teacher profile is `probabilistic_combat_v6`, RNG `splitmix64-rejection-v1`. Rebuild the matching extension. Resume expected_damage_v1/v2 and probabilistic_combat_v1/v2/v3/v4/v5 runs with their original source/build; never relabel frozen data, snapshots or checkpoints. Old weights require the existing explicit initialization/reset-optimizer route and new-rule acceptance.

The current compiled package can be provisioned from the immutable prior captures using the recipe in `verification/weapon_filters_20261103/REPORT.md`; use a new output directory and keep old packages unchanged.
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

Resume each experiment with its frozen source and matching environment. The `run.sh` wrapper uses `.venv/bin/python`. Check that interpreter before using the wrapper.

A quick self-check verifies only the environment and identity, without launching the game:

```bash
"$python" -m learning run --help
"$wesnoth" --version
"$python" -c 'import sys, torch, _engine_lite; print(sys.executable); print("torch", torch.__version__); print("CUDA", torch.cuda.is_available()); print("lite", _engine_lite.__file__)'
```

Native should be 1.18.8 and the project frozen entry requires PyTorch 2.9.1. The CPU server defaults to 8 global game workers with 1 thread per trainer, and the three trainers share those 8 workers. Windows is reference only; no full Windows acceptance is planned. The CPU server has no `git` and no `gh`, and `sudo -n` needs a password, so changes reach it as `git archive` tarballs extracted into a fresh dated directory, and acceptance runs from that extraction rather than from a long-lived checkout.

Fresh source archives lack compiled runtime files. Before paired native comparisons, build the existing entropy shim in the extracted tree and record its hash. Without it, `match._child_env` omits preloading and `--rng-seed` alone cannot pin native action RNG.

```sh
mkdir -p .runtime
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
sha256sum .runtime/entropy.so
```

Rebuild `_engine_lite` in the matching virtual environment when its Rust or embedded Lua changes. Rust embeds `engine_lite/lua/host.lua` through `include_str!`.

### Clean Ubuntu 24.04 training bundle

An archive from `python -m learning bundle --output PATH`, checked by `python -m learning verify-bundle PATH`, is how a clean Ubuntu 24.04 `x86_64` machine receives this project. It is an alternative to the server environment above, never a replacement, so keep the existing server directory untouched.

The archive carries the source tree, the frozen `1.18.8-combat-filtered` rules, curated human games, dataset inputs and the opponent packages kept under `data/opponents/` (the frozen `gpt6astra.zip`), which `BUNDLE_MANIFEST.json` lists under `data.opponents`; the verifier requires at least one. It excludes `.git`, virtual environments, caches, `.runtime/`, `runs/`, `verification/`, `delivery/`, `tmp/`, `data/rules/1.18.8`, `data/humanData`, `data/references`, compiled suffixes, Cargo `target/` and `AGENTS.md`, so it records no run, strength result or delivery decision. `docs/instructions.md` and its mirror are required members: the builder refuses an archive without them.

```bash
python -m learning bundle --output dist/WesnothLearning-training.tar.gz \
    --created-at 2026-10-25T00:00:00Z \
    --wheel dist/wesnoth_learning_lite-0.2.0-cp312-cp312-manylinux_2_34_x86_64.whl
python -m learning verify-bundle dist/WesnothLearning-training.tar.gz --require-wheel
```

`--output` must resolve inside the project root and must not exist; the builder renames a temporary file, so a failed build leaves no partial archive. `--created-at` normalizes to UTC `YYYY-MM-DDTHH:MM:SSZ` and makes repeated builds byte-identical. `--wheel` accepts only a name ending `.whl` that contains `manylinux` and `x86_64`, and `verify-bundle --require-wheel` fails an archive without one, which is what an offline Rust-free install needs. Both commands print JSON (`archive`, `sha256`, `files`, `bytes`, `created_at`, `source`, `rules`, `wheel`; then `ok`, `errors`, exit 2 when not ok); record the archive `sha256` in the release note. The builder refuses a rule identity that disagrees between `rules.json` and `catalog-summary.json` in `rules_file_sha256`, `source_hash`, `unit_count` or `terrain_count`.

The archive is one sorted PAX gzip under root `WesnothLearning/`, with `mtime` and gzip header time 0, `uid`/`gid` 0, empty `uname`/`gname`, mode `0644` (`0755` for `*.sh` and directories), and `BUNDLE_MANIFEST.json` (schema 1) plus `SHA256SUMS` at the root, so `cd WesnothLearning && sha256sum --check SHA256SUMS` works after extraction. The verifier recomputes every member size, hash and mode and the totals, the Ubuntu 24.04 `x86_64` target, the absence of absolute, parent-escaping or duplicate members, the exclusion classes, the rules identity against the archived JSON, the `data.opponents` list (at least one package, each under `data/opponents/`, hash-checked), the curated human file and the optional wheel.

```bash
tar -xzf WesnothLearning-training.tar.gz && cd WesnothLearning
./setup.sh --preflight          # checksum only: no OS gate, no download, no write
./setup.sh --device cpu         # apt packages, venv, torch 2.9.1, _engine_lite, Wesnoth 1.18.8
./train.sh --help               # prints options; creates nothing
```

The target is Ubuntu 24.04 `x86_64` with `sudo` or root and network access; 22.04 runs with a note, any other distribution exits 2 before touching the system. `--device auto` (default) selects `cu128` only when `nvidia-smi` works, so state `--device cpu` on a CPU-only machine; `--wesnoth PATH` reuses a binary that reports 1.18.8, `--skip-system-deps` requires the packages to be present, `--jobs N` sizes the Cargo and Wesnoth builds, and `WESNOTH_EXE`/`BUILD_JOBS` supply the same values. Setup installs a bundled `dist/*.whl` with `--force-reinstall --no-deps` and never installs Rust in that case; otherwise it installs rustup only when `cargo` is absent and runs `maturin develop --release` in `engine_lite/`. It then checks `rules.json` against `catalog-summary.json`, `source_version` 1.18.8, and the extension's `ENGINE_VERSION`/`RNG_VERSION`/`COMBAT_VERSION` against `learning.adapters`, reuses or builds pinned Wesnoth (SHA-256 `fce3bd71d4ed32c9d11c0f707d19743cec6adf5c34761fab94ab72754aaedd89`), writes `.runtime/environment.sh`, and logs through `tee` to `.cache/setup.log`. Reuse is idempotent for the venv, torch, requirements and Wesnoth; the extension is reinstalled or rebuilt every run. Setup starts no sampling, game or training, and the archive's presence is not authorization to start work.

Failures: `preflight: SHA256SUMS verification failed` means the extracted copy differs from the archive — re-extract into a fresh directory and never repair hashes by hand; a missing `SHA256SUMS` means an incomplete extraction. An OS-gate or sudo refusal is satisfied by Ubuntu 24.04 `x86_64` with root/`sudo`, or by `--skip-system-deps` after installing the packages yourself. `identity: engine build … does not match declared …` means a stale extension: rerun setup. A wheel that is not picked up has two causes: `setup.sh` only searches `dist/` for names starting `wesnoth_learning_lite-`, `_engine_lite-` or `engine_lite-` (and `--preflight` prints the file it found), while the builder additionally demands `manylinux` and `x86_64` in the name. `train.sh` refuses without `.runtime/environment.sh`, `.venv/bin/python`, an importable `_engine_lite`, an executable `WESNOTH_EXE` or a free run directory. Section 4 starts a run once the user authorizes it.

The reference workstation verified the archive layout and scripts. Extraction, installation and startup on a clean Ubuntu 24.04 host remain unverified. [Bundle verification record](../verification/acceptance_20261030/REPORT.md)

## 3. Verify the actually runnable scope before starting

New experiments use lite by default, with rules defaulting to `data/rules/1.18.8-combat-filtered` (587 units, 438 terrains). The startup gate verifies the actual 158-unit closure of the six factions, accepts recorded approximations and rejects unsupported types and missing references; whole-package semantics/performance flags keep their original values. A fresh manifest freezes the sole custom teacher package (`gpt6astra`) and its lineage; the evaluation engine follows the sampling engine unless `--evaluation-engine` overrides it. Capabilities and limits are in architecture.md §4–§5.

The default directory is usually enough. Captured inputs moved under `data/` on 2026-10-24, so a checkout predating that move keeps `rules/`, `datasets/`, `humanData*`, `opponents/` and `references/` at the root: move them into `data/` before running, or the defaults no longer resolve. When the user specifies another frozen package, pass it:

```bash
rules_dir="$project/data/rules/1.18.8-combat-filtered"
# add --rules-dir "$rules_dir" to the new training command
```

`--rules-dir` binds features, jobs, adapters and the manifest at once and takes precedence over the environment variable; without an explicit parameter `WESNOTH_RULES_DIR` may be used. The programmatic API passes `config.rules_dir`. Resume automatically uses the original manifest's directory and must not be pointed at the newest package.

The default `1.18.8-combat-filtered` rule identity is `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`; the 10 formal maps are frozen in `data/rules/1.18.8/maps`. When capturing a new package use `python -m engine_lite.capture --maps-dir data/rules/1.18.8/maps` plus the other required parameters, keeping map composite terrains. After changing the rule hash/vocabulary, start a new experiment; historical weights keep their original matching schema.

Pass criteria: the rule hash matches `features.schema()`, the six-faction closure has no missing/unsupported declarations, the maps and Astra exist, and the chosen format really has a teacher chain; reuse evidence when existing validation is valid and run one affected minimal check only if the wiring code changed. Handling of strict statistical precision, peripheral campaigns and package limits is bounded by the architecture document and must not re-expand into a full test task.

### Archive replay provisioning

Hosted replays are provisioned month by month into `data/replays/<YYYYMM>/<DD>/`, one directory per archive day; repeat `--month` for consecutive months and keep the default output unless the user names another directory:

```bash
python -m learning.replay_fetch --month 2026-07 --month 2026-08 --month 2026-09
python -m learning.replay_fetch --month 2026-07 --out data/replays/202607 --verify
```

An unreadable month listing, a failed day listing or a transfer that never succeeds is reported as a failure and the command exits non-zero; nothing counts as provisioned without evidence. Re-runs are cheap and honest: a file already on disk is kept only after it decompresses as a complete bz2 stream, so interrupted transfers are re-fetched instead of trusted. `--verify` re-reads the archive listings, compares the listed names day by day and decompresses every local file. The tool provisions captured inputs only: it parses no replay content and authorizes no collection or training.

### Engine benchmark

The paired native/lite workload is fixed by `benchmarks/contract.json`; `learning.benchmark.build_manifest` freezes the artifact hashes and `learning.benchmark_runner` measures on Linux from `/proc/*/smaps_rollup`:

```bash
python -m learning.benchmark_runner --executable "$WESNOTH_EXE" \
  --output verification/perf-smoke --formats duel --caches cold \
  --modes equal_work --densities regular --blocks 1 --seats 1 \
  --script-turns 1 --max-decisions 4
```

Drop the limits and pass `--blocks 30` for full samples; each output directory is written once and a fault is never a successful zero. `observed.json` shows measured ratios at any block count, while `acceptance.json` needs 30 complete blocks with identical host/quota/work and both wall and CPU at least 5× native; PSS has a separate 5× target and RSS is never substituted. Equal-work results cover only the fixed script, not combat, and student inference needs its own small-loop measurement.

## 4. Create and start training

First establish the user-specified formats, device, duration, workers and experiment name. Default collection specification is in architecture.md §12; the numbers are valid-teacher-game targets, and filling them also requires passing the BC quality/coverage/design gates. Verify the generated config matches the authorization.

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

For an authorized auxiliary-target comparison, add `--ppo-aux-target frozen_bc_kl` to the new run command; `--ppo-aux-target historical_action` is the default baseline. The first uses the complete, qualifying BC endpoint's frozen action distribution on eligible policy/train rehearsal states; the second uses historical sampled actions. The existing `bc_aux` coefficient remains 0.1 by default and is frozen per batch. Control exclusions, candidates, sampling quotas, history and PPO stopping remain shared. Do not combine target selection with coefficient or reward tuning when comparing the targets.

The KL mode pins `<format>/frozen_bc.pt` and its identity in `state.json`/complete checkpoints before PPO begins. Preserve that file alongside the checkpoints when moving or resuming the run. A same-task BC-only parent may seed both modes with `--branch-from PARENT` in separate new directories: the copied initial checkpoint must match its qualifying `last_bc.pt`, and the branch record pins that endpoint. A forced PPO phase without qualifying BC fails in KL mode. Old-task weights used for explicit actor initialization must pass the new run's BC gates before becoming its anchor. The mode cannot change on resume; `run --resume ... --ppo-aux-target ...` is rejected. Never replace the anchor with selected/latest or edit a manifest to change modes.

Long tasks belong in an existing persistent terminal; with tmux, run `tmux new -s wesnoth-v5` first, set up the environment and start command inside, detach with Ctrl-b, d, and reattach with `tmux attach -t wesnoth-v5`. Record the session, main PID, full command, log and experiment directory, and confirm that dropping SSH does not end training. Do not let a short-lived SSH tool request hold the whole long experiment.

New runs use `official-score-30-v1`: teacher, PPO and DAgger finish the complete 30th round as a scored task terminal. `--training-max-turns` accepts only 30. Gamma is 1 and exploration reward is 0; economy/control remain potential shaping. Evaluation uses 30 and opening probes use an external cut at 5. BC gates and panel sizes retain their existing thresholds. Legacy 60-turn data and manifests cannot resume or mix into this task; use an empty or compatible `--human-data` directory rather than relabelling a historical corpus.

Post-start checks:

- `manifest.json` `config` matches the instruction, with correct rule/architecture/vocabulary and engine binding.
- `clock.json` start and deadline match this budget; by default updates are allowed for the first 10/12 of the duration and the last 2/12 are frozen evaluation.
- Every enabled format has `hardware.json`, `state.json`, `latest.pt`, and at least one valid collection batch keeps advancing `jobs.jsonl` and training counters.
- No `trainer_error.log` or persistent `infrastructure_error`; phase and teacher identity are as expected. Report a failed start as a failure instead of substituting a background PID for progress.

This guide does not prescribe a default pre-flight rerun of 277 tests, the 30-block performance matrix or large-sample combat statistics.

Use `--final-holdout-hours H` to reserve H hours of the final evaluation budget (default 0, `0 <= H < hours/6`). Nomination stops H hours before the total deadline and retains the champion if incomplete. Holdout keeps the original deadline, and resume uses the frozen configuration.

## 5. Resuming existing training

Inspect the original experiment's manifest, clock, latest checkpoint and error records first, confirm no active main process in the same directory, then run against matching sources, environment and rules:

```bash
run_dir=runs/<user-specified experiment directory>
test -f "$run_dir/manifest.json" || exit 1
"$python" -u -m learning run --resume "$run_dir"
```

`--resume` uses the device, workers, formats, sampling targets and original deadline frozen in the manifest. Appending `--hours`, `--workers`, `--bc-games` and similar does not change an existing experiment; when the budget has expired, resume goes to evaluation/finish and does not gain new budget automatically.

Confirm that checkpoints, optimizer, RNG, reward controller and unfinished batches are restored and counters keep growing. On `source changed`, `manifest changed` or rule/vocabulary mismatch, diagnose with the original matching version and keep the original manifest and checksums. New config/new architecture means a separate experiment per user instruction or an explicit migration, never editing frozen files to pretend it was an unchanged resume.

`run.lock` is a file lock; an existing file does not mean it is running. On `already running`, identify the lock holder first and never start a second process in the same directory by deleting the lock file.

## 6. Daily maintenance and progress judgement

### Running BC, PPO and final evaluation separately

To start a new BC phase from a compatible parent's weights and supervision, run `python -m learning run --run-dir CHILD --branch-from PARENT --branch-restart-bc --branch-reset-optimizer --phase bc` with the parent's formats, engine and training turn limit. The parent must be at a committed boundary. The child uses its own seed and budget, starts calibration, and evaluates its first updated model on the original validation split.

To initialize the new finite task from an old BC actor, use `python -m learning run --run-dir CHILD --branch-from PARENT --branch-weights-only --branch-checkpoint last_bc --phase bc --formats duel --human-data EMPTY_OR_COMPATIBLE_DIRECTORY`, with the parent's engine and rules plus the separately authorized budget/seed. Weights-only initialization accepts a nonempty subset of the parent's formats. Ordinary branches require the same format set. Omitting `--branch-checkpoint` selects `latest`. A matching mean-board actor can seed the position readout through this command, with `[I,0,0]` weights and zero bias for the new projection. The program records the source path and hash, resets the value head and optimizer, and starts calibration with empty training state and fresh gates. Ordinary PPO requires a new task-qualified BC endpoint. Later branches from that same-task parent can reuse compatible supervision. This command starts work only when separately instructed. Account for a warm-started actor's prior map and scenario exposure when choosing a validation split.

Native-grid runs require current schema 7 observations and schema 8 training rows. Re-observe human replays and collect teacher supervision under the current source when authorized. The pooled observations and their indexes belong to their original source. The default `run` uses the auto flow. For BC only, create the experiment with `--phase bc`. When BC passes or reaches its phase budget, the run saves `bc_complete` and stops before PPO and final evaluation.

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

For a committed stop before the deadline, add `--ppo-batches N` to `phase ppo`. Each requested format finishes after N newly scheduled PPO batches have applied at least one optimizer step and any due validation has run. A resumed batch already pending at the request boundary finishes under its existing plan and falls outside this count. Each new request starts its own count. The phase deadline can end training earlier.

The bounded fixed-Astra duel comparison chooses `rollout_games=4` or `8` when `start_arm` creates the run. Its budget records the first PPO batch index and the admission and settlement deadlines. Use `resume_arm` with the same run directory to continue the saved stage within that budget. Omit `fresh_targets` for a wall-clock comparison. [Driver and Ubuntu contract](../verification/ppo_batch_contract_20261107/REPORT.md)

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
| `<format>/bc_gate.json` | Whether corpus size, imitation quality, candidate coverage and scenario design each pass; the opening probe is recorded with `blocking: false` |
| `<format>/validation/*.json` | Distinguish trend/promotion, native/lite and teammate context; a small-panel win is not final strength |
| `<format>/latest.pt`, `last_bc.pt`, `last_ppo.pt` | Whether the checkpoint updated and matches state and current phase; best/selected are selection results, not a substitute for latest when restoring |
| `control/*.json`, `control/events.jsonl` | Current config, pending commands, applied sequence, reward_version, last_error, metrics_error (adaptive is frozen when non-empty) |
| Main log, `scheduler.jsonl`, `trainer_error.log` | Whether tasks still complete, which format/phase failed, the actual stack trace |

A non-growing BC game count is not necessarily stuck: when the quota is full but quality has not passed, learning continues on existing data and sampling is added only past the plateau. Short collection phases may legitimately not update weights. Judge from the latest task completion time, pending batches, optimizer_steps and checkpoint time; high CPU utilisation alone proves neither speed nor a fault, so look at valid games/hour, CPU core-seconds/game, memory and timeouts first.

Maintain only the processes and files this task owns. Routine maintenance may resume the same config and keep fault evidence within existing authorization; do not change workers, rewards or gates just because utilisation looks low. When longer supervision is needed, use the user-authorized task scheduling capability instead of unbounded polling within one check.

### Matched BC, selected and latest progress

Final holdout reports evaluate selected only. Their checkpoint-role table also
identifies the BC endpoint, latest complete checkpoint and any pending update;
an interrupted update is excluded from latest-complete.

For a separately authorized progress evaluation, use an existing finalized run
with `last_bc.pt`, frozen `selected.pt`/`selection.json`, and a complete latest
checkpoint. Keep the source run read-only. Planning below starts no games:

```bash
"$python" -m learning.progress plan --directory "$run_dir/duel" --format duel \
  --output verification/progress_NEW --blocks 12 --seed 20261106 --hours 1
# Explicit execution starts evaluation games, without training or corpus shards.
"$python" -m learning.progress run --plan verification/progress_NEW/plan.json --workers 8
```

The example budgets 72 duel games: 12 full blocks for each of BC, selected and
latest. FFA needs 144 games and team needs 288, including both partner contexts.
The deadline starts when planning; choose the authorized time budget, and create
a new plan if it expires. Frozen exports, opponent, rules, evaluator source and
schedule are checked before execution. The operation creates a new output
directory and does not rewrite source-run manifests, checkpoints or selection.

`report/summary.json` and `report/REPORT.md` show matched normalized own-score
changes versus BC. Missing/faulted games and insufficient physical scenes cannot
establish improvement. A complete interval crossing zero remains inconclusive.
These are validation-set diagnostics, separate from independent final holdout.
To recompute from existing replies without games, use a fresh report directory:

```bash
"$python" -m learning.progress report --plan verification/progress_NEW/plan.json \
  --results verification/progress_NEW/execution/results.json --output verification/progress_REPORT_NEW
```

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

To restore an archived experiment, locate its original path in the archive’s `index.json` and verify its files against `SHA256SUMS`. Follow the archive README to restore relative paths without overwriting an existing run. Resume with the original schema, frozen source and budget. [Archive location and recovery instructions](../verification/training_archive_20261023/REPORT.md)

## 8. Tuning parameters on instruction

First turn the instruction into: experiment directory, format, fields, target values, reason and observation window. Use the user-given values; if only research or evaluation was requested, report the basis first and do not tune. After approval change only the named items, keep the rest of the config, and never fake play-strength progress with higher shaping scores or lower BC gates.

### 8.1 Hot-updatable at batch boundaries

| Field | CLI | Allowed range |
| --- | --- | --- |
| economy | `--reward-economy` | 0.05–0.20 |
| control | `--reward-control` | 0.02–0.15 |
| explore | `--reward-explore` | 0 for `official-score-30-v1` |
| mode | `--reward-mode` | fixed / scheduled / adaptive |
| entropy coefficient | `--entropy` | non-negative finite |
| BC auxiliary coefficient | `--bc-aux` | non-negative finite |

Use the existing control queue; never write state/checkpoint/config directly. The variables below must be assigned from a user instruction first; the example changes only the named format's economy potential coefficient:

```bash
: "${run_dir:?specify an existing experiment}"
: "${target_format:?specify duel/ffa4/team2v2}"
: "${target_economy:?fill in the user-specified economy coefficient}"
: "${change_reason:?record this user instruction and the reason for the change}"
test -f "$run_dir/manifest.json" || exit 1
"$python" -m learning control show --run-dir "$run_dir"
"$python" -m learning control set \
  --run-dir "$run_dir" --format "$target_format" \
  --reward-economy "$target_economy" --reason "$change_reason"
```

The returned command ID only means queued; wait for that format to finish its current batch, then check `control show` pending, actual config and applied sequence, and verify old/new values, reason and the incremented reward_version in events. Games already started keep the old frozen config and only later batches use the new version. One PPO update cannot mix reward versions.

To pause automatic tuning, switch that format's mode to fixed only when the user asks; manually changing one coefficient does not disable adaptive. Roll back the same way by queuing the old value with a reason, never deleting or rewriting the event chain.

### 8.2 Not hot-changeable on an existing run

workers, device, formats, total budget, BC game count/native anchors, model structure/vocabulary, sequence window, epochs, learning rate, PPO clip and `ppo_aux_target` are not hot-update fields of the current control API. Adjust a new experiment's config per the user instruction or implement a compatible migration, and update the architecture document; never push them into `control set` or claim a resume parameter already took effect.

In particular: `learning_rate` currently initializes the BC optimizer while the PPO path sets 1e-4. Changing the PPO learning rate per user request means editing the code that actually owns that phase and doing a minimal verification, not just editing the initial config. Sampling quotas are the same: `bc_games` is the total valid teacher games, `native_bc_games` the native target, `bc_records` the decision limit per read, and the three are never conflated.

After each change, verify the actually effective config, then record old→new, user basis, command/event ID, effective batch/version, follow-up observations and rollback. Compare by default on valid sampling throughput, fault rate, BC sub-scores and same-engine/same-format validation; formal strength still rests on native evaluation.

## 9. Reporting and handover

For an authorized delivery export, `export --audit-data DIR --audit-workers N` shares up to N processes across all formats. The default is one. Each format's subdirectory supplies all of its `*.jsonl.gz` shards, including any sequence fragments stored in different files.

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
