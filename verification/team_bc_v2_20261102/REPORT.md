# Bounded ordinary team BC under expected_damage_v2

Date: 2026-11-02 (Asia/Shanghai). The user explicitly authorized this bounded diagnosis and equivalent bounded diagnoses within this task. Original loss, sampling and all ordinary gates are preserved. No PPO, final evaluation or export was launched.

## Frozen identity and environment

- Source `959ae6a676449b3bb4192f4cf9349698c53c48da`, based on `b2864ac`; git-archive SHA-256 `01bd54141c9bc6a0fcbf679afa491c5e2d73992afb9b0caa829382e38359e79d`.
- Fresh Ubuntu source directory: `/home/tongshu/acceptance/team_bc_v2_20261102`.
- Python 3.12.3, torch 2.9.1+cpu, one trainer thread; `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1`.
- Rules SHA-256 `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`, linked read-only by use from the provisioned main-tree `data/rules`.
- The shared venv still contains v1. A matching v2 release was built in isolation, copied to `.extension/_engine_lite.so` and loaded through `PYTHONPATH=.extension:.:vendor/arena`; nothing was installed into the shared venv. Extension SHA-256 `ccb7c763cbce620e5d07736e6ae73df2c3891bdd9f281ab79ee10d63e2675365`, engine `lite-0.2`, RNG `deterministic-expected_damage_v2`, combat `expected_damage_v2`.
- Teacher source SHA-256 `09d13f55960bd85d8700a5015296026c3cf4f96a86c6bd4f69e7ae4ec68770c2`; parent package SHA-256 `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`.
- Only the archived human import inventory is present; it supplies no eligible human shard. This is a fresh teacher-only experiment.

Build command, exit 0 in 3.29 s ([build.log](build.log)):

```bash
PATH=/home/tongshu/.cargo/bin:$PATH PYO3_PYTHON=/home/tongshu/venv/bin/python \
CARGO_TARGET_DIR=/home/tongshu/acceptance/retaliation_fixed_20261102/engine_lite/target \
cargo build --manifest-path engine_lite/Cargo.toml --release
```

## Ordinary run: FAIL at the declared batch cap

[driver.py](driver.py) freezes the complete command and identities in [observed/plan.json](observed/plan.json) before launching. One team format, seed 20261101, eight shared workers, 48 valid teacher-game target, 30 full training turns, 2048/1024 training/validation rows, four epochs, minibatch 256; a 1200 s phase deadline, 1320 s external cap and at most five committed batches. Eight games per batch means at most 40 games reach a committed gate before that cap; the 48-game gate is not lowered.

```bash
export PYTHONPATH="$PWD/.extension:$PWD:$PWD/vendor/arena"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
export SOURCE_COMMIT=959ae6a676449b3bb4192f4cf9349698c53c48da
export WESNOTH_EXE=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
/home/tongshu/venv/bin/python -u verification/team_bc_v2_20261102/driver.py
```

Observed driver exit **1**, child exit **-15**, `committed_batch_limit`, **933.30 s** (15m33s). Both time ceilings remain unused; there is no retry or parent-run extension. Five batches commit **216 updates**, version 5, no pending training. All owned processes exit.

The scheduler records **48 submitted / 40 finished** jobs. The final eight were submitted but have no final job result when the cap terminates the process group; they are not scored as completed or relabelled as recorded faults. Of 40 completed games, **37 are true turn-truncated**, three finish earlier, and **zero recorded faults** occur. Truncated terminal frames report turn 31 after the full-turn limit 30; this is not candidate-work truncation. Focal factions across completed jobs: Knalgan 6, Drakes 6, Loyalists 7, Northerners 8, Rebels 7, Undead 6.

The complete version-5 checkpoint is `runs/team_bc_v2/team2v2/last_bc.pt`, SHA-256 `2fd567c68ae75ed3f5f9f62dc012d6e02965502937e63cbd8bf58f6f0905732c`. It matches state version 5. All model/shard hashes are in [input_model_hashes.json](input_model_hashes.json); manifest, clock, schedules, state, gate and scheduler/job logs are in [run_metadata.tar.gz](run_metadata.tar.gz). Models and shards remain at the recorded server run path.

Coverage **passes**: overall 9538/10117 = **94.28%**; recruit 87.37%, move 94.38%, attack 92.56%. The ordinary gate **fails** at corpus **40/48** and imitation. All 40 scenario families are identified, exceeding the unchanged floor 12. Last committed validation: 1017 eligible multi-candidate rows, CE 1.72306 versus uniform 3.58062, overall accuracy 52.02%; recruit **16/57 = 28.07%**, move **439/722 = 60.80%**, attack **14/128 = 10.94%**. Each class exceeds the 32-sample floor. Floors remain 60% / 35% / 35%.

## Exact-batch read-only decomposition

```bash
timeout --signal=TERM --kill-after=10 300 /home/tongshu/venv/bin/python -u \
  tests/diagnose_bc_parts.py --run runs/team_bc_v2 \
  --output verification/team_bc_v2_20261102/committed_parts.json
```

Exit **0**, 25.50 s; [committed_parts.json](committed_parts.json), [parts.log](parts.log). The exact 2048-row batch retains all **32 training families**, 54 trainable windows, 165 recruits and 366 attacks. Train recruit **43/165 = 26.06%**, attack **105/366 = 28.69%**, move **782/1232 = 63.47%**. This confirms underfitting as well as possible generalization loss. The trainer's kernel peak RSS reaches 1137 MiB; no matched performance control exists.

## Separate original-loss copy probe

The conditional follow-up is frozen in [curve_plan.json](curve_plan.json): no new games, same 2048/1024 rows, restore the saved model/Adam/RNG in memory, original loss/sampler, at most 600 updates, 900 s update deadline and 1200 s external cap. It neither resumes nor edits the ordinary experiment. Complete epochs yield a predeclared **588 planned updates**.

```bash
timeout --signal=TERM --kill-after=10 1200 /home/tongshu/venv/bin/python -u \
  tests/diagnose_bc_learning_curve.py --run runs/team_bc_v2 --format team2v2 \
  --output verification/team_bc_v2_20261102/original_loss_curve.json \
  --updates 600 --seconds 900
```

Exit **0**, **588 updates**, not interrupted, **431.34 s**. [original_loss_curve.json](original_loss_curve.json) and [curve.log](curve.log) retain points 0/50/150/300/588. The parent's checkpoint hash is unchanged.

| Metric | Before extra updates | After 588 |
| --- | ---: | ---: |
| Train recruit | 43/165 (26.06%) | 133/165 (80.61%) |
| Train attack | 105/366 (28.69%) | 260/366 (71.04%) |
| Validation recruit | 16/57 (28.07%) | 32/57 (56.14%) |
| Validation attack | 14/128 (10.94%) | 32/128 (25.00%) |
| Validation move | 439/722 (60.80%) | 425/722 (58.86%) |
| Validation CE | 1.72306 | 1.93817 |
| Validation recruit type | 39/57 | 39/57 |
| Validation recruit slot | 24/57 | 48/57 |

The ordinary imitation gate still fails. More optimization improves training fit and slot prediction but does not improve held-out recruit-type matches; attack generalization remains below its original floor. No epoch/default/loss/sampler change is adopted from this probe.

## Interpretation and remaining scope

This supplies actual v2 ordinary BC and fixed-batch evidence. Candidate coverage and retention are not the remaining gate failure on this corpus. Initial underoptimization and held-out type/action ranking remain material. It does not establish ordinary readiness, all-format operation, same-future resume, native strength or convergence. Thirty-turn/current-reader/v2 evidence is not an apples-to-apples speed or quality comparison with the historical v1/60-turn run (`../team_bc_readiness_20261102/REPORT.md`).

No new runtime behavior was implemented in this phase, so accepted deterministic regression evidence remains valid; no local Windows tests were run. Blockers 5/9/10/11 remain open with narrower current evidence, not green acceptance.
