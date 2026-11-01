# Bounded training-loop acceptance — 2026-11-01

## Outcome

**FAIL at BC.** The explicitly authorized all-format loop ran on Ubuntu for 558.33 seconds (9 min 18 s). The predeclared cap stopped the process group when duel committed its fifth BC batch. The child exit code was -15 (the runner's SIGTERM), not an observed training exception. All three ordinary BC gates remained false. No gate was bypassed, no PPO was forced, and no automatic retry or time extension was performed.

The manual runner is `tests/bounded_training_loop.py`; production training code is unchanged. Ubuntu syntax compilation passed. This run exercises initialization, collection, BC updates, gate recording and the bounded failure exit. Later orchestration branches were not executed or accepted.

## Frozen identity and procedure

- Shipped source: `5f86804d1b1ae4bf25a61a3c3ad21a59c3056320` (git archive of branch `codex/bounded-loop-acceptance`).
- Host/source directory: `cpuServer:/home/tongshu/acceptance/bounded_loop_20261101`.
- Python: `/home/tongshu/venv/bin/python`, 3.12.3; torch 2.9.1+cpu; Ubuntu kernel 7.0.0-38-generic. Wesnoth 1.18.8.
- Candidate contract: `work-12000-v5`, 12 combat + 12 recruit + 12 move with refill, 36 actions plus end turn. Row schema 6; relational_v5 model.
- Rules SHA-256: `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`.
- Frozen Astra package SHA-256: `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`; adapted profile `expected_damage_v1`.
- Full immutable input/config/source identities: `runs/bounded_loop/manifest.json`. Model hashes: `verification/bounded_loop_observed/checkpoints.sha256`; checkpoints and generated shards remain on the server.
- Three formats; 8 shared workers; 1 trainer thread; seed 20261101; CPU/lite collection and intended lite evaluation; turn limit 30.
- Targets: 24 BC games per format, 2,048 train / 1,024 validation rows, 4 epochs, minibatch 256. No native BC games. Maximum 5 committed BC batches in **any** format, so slower formats may stop before their targets.
- Stage ceilings: BC 1,200 s; PPO 900 s including stop/resume; final evaluation 900 s with unchanged 30-block requirement; export 300 s. Total stage ceiling 3,300 s, leaving approximately five minutes for setup/reporting. These were ceilings, not a request to keep training after a failed gate/cap.

Commands (source was committed before shipping):

```powershell
git archive --format=tar -o bounded-loop.tar HEAD
scp bounded-loop.tar cpuServer:~/bounded-loop.tar
```

The archive was extracted in the fresh host directory. Existing `data/rules`, `data/opponents` and `data/datasets` inputs were symlinked read-only in use; they were not edited. The environment used `PYTHONPATH=.:vendor/arena`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`.

```sh
/home/tongshu/venv/bin/python -m py_compile tests/bounded_training_loop.py
SOURCE_COMMIT=5f86804d1b1ae4bf25a61a3c3ad21a59c3056320 \
WESNOTH_EXE=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
nohup /home/tongshu/venv/bin/python -u tests/bounded_training_loop.py > bounded-launch.log 2>&1 < /dev/null &
```

The exact expanded BC command, elapsed time, stop reason and state snapshot are in `verification/bounded_loop_observed/bc.json`; the prelaunch profile is `plan.json`. No matching runner/spawn/resource-tracker process remained in the post-run host process listing. No tests ran on Windows.

## Observations

| Format | Recorded complete / faulted / truncated games | Committed BC batches | Optimizer updates | Peak recorded trainer RSS MiB | Last gated corpus / target | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| duel | 24 / 0 / 24 | 5 | 176 | 755 | 24 / 24 | FAIL |
| ffa4 | 16 / 0 / 16 | 1 | 28 | 705 | 8 / 24 | FAIL |
| team2v2 | 13 / 0 / 13 | 1 | 48 | 807 | 8 / 24 | FAIL |

`complete` is the job status; every recorded game also has `truncated=true` at the configured turn cap. These are not 53 decisive, non-truncated games. Collected games can exceed the last gated corpus because another collection/training batch was in flight at the global stop. Unfinished jobs do not count as recorded complete games.

| Format | Candidate coverage: all / recruit / move / attack | Held-out imitation accuracy | Cross-entropy / uniform | Distinct gated scenarios |
| --- | --- | --- | --- | --- |
| duel | 72.56% / 37.94% / 87.87% / 52.98% | 31.33% | 2.495 / 3.490 | 24 |
| ffa4 | 57.74% / 39.22% / 69.18% / 30.85% | 23.17% | 2.706 / 3.486 | 8 |
| team2v2 | 56.26% / 33.33% / 54.72% / 31.74% | 42.47% | 1.988 / 3.548 | 8 |

Duel met its 24-game corpus and 12-scenario minimum but failed coverage and imitation. Its recruit/move/attack imitation accuracies were 53.33% / 27.75% / 26.92%, below ordinary floors 60% / 35% / 35%; overall floor is 40%. FFA4 and team2v2 also lacked the gated corpus/scenario count. Their figures describe partial training, not convergence. Per-format `bc_gate.json`, `state.json` and `jobs.jsonl` preserve the raw values.

Initialization selected the existing single-fixed-Astra control route (`controls.json`); no competitive calibration panel was played. The manifest allowed reuse of eligible human inputs, but recorded BC reads in this run contain Astra rows only.

| Stage | Result |
| --- | --- |
| Initialize / select fixed control | Observed; single-Astra route only |
| Teacher collection / BC optimizer | Observed partial all-format run |
| Ordinary BC readiness | FAIL |
| PPO rollouts and committed updates | NOT RUN |
| Checkpoint stop/resume and same-future comparison | NOT RUN |
| Validation / checkpoint selection / final panel | NOT RUN |
| Audited export | NOT RUN |

## Remaining blocker and next direction

The next bounded investigation should separate missing teacher labels from imitation fit: inspect unmatched recruit/attack actions and their mapping into the deployment-matched candidate set, then inspect held-out per-kind fit on the existing eligible rows (blocker 10). The coverage failure cannot be explained away by simply adding optimizer updates. This run does not identify the underlying selection/mapping cause, prove non-convergence, or establish playing strength/native transfer. It does not close item 9 or full-loop acceptance. Rerunning collection/training requires a new instruction after the relevant repair.
