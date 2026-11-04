# Combined final-scoring validation rotation

All 14 validation games finished with zero faults and matched their archived v10 official outcomes. On the production eight-worker pool, the combined `score_only_astra` and `score_only_policy` paths took **51.80 seconds** including startup and the partially occupied final interval. The archived reference took 71.86 seconds. Applying each observed speed ratio to its corresponding strict-run workload projects **889.88 seconds**, 25.88 seconds above the 864-second internal final-panel budget. [Frozen inputs, official results, build and timings](after.tar.gz) · [Original timing](../lite_panel_throughput_20261104/REPORT.md)

## Occupied worker time

| Group | Validation games | Baseline worker seconds | Combined worker seconds | After / before | Strict mean seconds × required games | Projected seconds at eight slots |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Duel | 2 | 44.72 | 30.84 | 0.68955 | 26.37 × 60 | 136.38 |
| Four-player FFA | 4 | 160.71 | 118.88 | 0.73971 | 18.58 × 120 | 206.16 |
| Team with Astra partner | 4 | 177.80 | 129.98 | 0.73100 | 21.33 × 120 | 233.88 |
| Team with learned partner | 4 | 99.28 | 64.33 | 0.64797 | 32.25 × 120 | 313.46 |
| Total | 14 | 482.52 | 344.02 | | 420 | **889.88** |

The projection multiplies each strict completed-game mean by its own validation after/before ratio and scheduled count, then divides the total occupied seconds by eight. The unadjusted strict workload projects to 1,280.18 seconds. The final game mix, policy versions and game durations can differ from these validation inputs. The calculation assumes full worker utilization and excludes handoff and tail time. This rotation measured validation throughput only.

## Source, binary and execution

Production Git source was `3b109bd4639a56d54ceb63d099225a48ede1d0c7`. Its archive SHA256 was `0315696876f521f4197f60d89bbaeb129a53e6e2e7547a606f9186e8949be0ae`. The after-only driver was shipped separately at `740271450653485f325a0182463588097df8f588`, archive SHA256 `fd75173e297eae4de3e02a73ebf5afeb3349edb2b9aec81a215e76a88762813a`. Both Git archives were verified locally and on Ubuntu before extraction into `/home/tongshu/acceptance/combined_validation_rotation_20261104/src`. [Driver](after.py)

The release build ran `cargo build --release --locked --offline --manifest-path engine_lite/Cargo.toml` with four build jobs, a fresh target directory and `PYO3_PYTHON=/home/tongshu/venv/bin/python`. It completed in 12.50 seconds. The installed, hash-verified binary is `cpuServer:/home/tongshu/acceptance/combined_validation_rotation_20261104/src/.extension/_engine_lite.so` (2,742,416 bytes, SHA256 `8d7abbeda2b31636369cf5253a8b34e286435103876b38d83080a985f5b7d036`).

The driver used the original block-zero validation jobs and official outcomes from `/home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness`. It checked the original 14 IDs and ordering, per-format schedules and v10 model hashes, maps, factions, seeds, policy seats, worker count, 30-turn limit, 235-second internal deadline, teacher and filtered-rule digests before dispatch. Learning instrumentation was absent. Both scoring flags were enabled for the measured games, and all workers reported frozen fp64 weights. The pre-dispatch plan SHA256 was `4810bdc1e7a0577171c6c06ba69ec253ae38743803c76a9a5dfe43af03cd6a82`, and the separate comparison plan SHA256 was `f48d07f6b9869c1a01661eab2db8abf8861a4e316a15a0914fcda9c4578ab519`.

```sh
cd /home/tongshu/acceptance/combined_validation_rotation_20261104/src
export SOURCE_COMMIT=3b109bd4639a56d54ceb63d099225a48ede1d0c7
export SOURCE_ARCHIVE_SHA256=0315696876f521f4197f60d89bbaeb129a53e6e2e7547a606f9186e8949be0ae
export EXTENSION_SHA256=8d7abbeda2b31636369cf5253a8b34e286435103876b38d83080a985f5b7d036
export PYTHONPATH=.extension:.:vendor/arena
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
timeout --signal=TERM --kill-after=4s 240s /home/tongshu/venv/bin/python -B -u \
  verification/combined_validation_rotation_20261104/after.py \
  /home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness ../panel
```

The single new invocation ran from 08:42:36 to 08:43:28 Asia/Shanghai and exited 0. The result archive SHA256 was `7fab2069c3dce382ed821bdb19d54ca477dd2bb1642b14d1e54c4551ff369347`. Its `panel/combined.json` records the strict-weighted projection. The inherited `panel/summary.json` also records the cost of repeating this validation rotation 30 times, a separate calculation.
