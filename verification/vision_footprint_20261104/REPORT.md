# Reuse stationary vision footprints on the Lite map

One fixed team validation game consumed **20.396 CPU seconds after the change, down from 23.327 seconds**. The 12.56% saving exceeded the predeclared 5% threshold on this game. The worker executed 1,031 actions and produced the same ordered action/event trace, every side's complete observation after each action, and the original official result.

## What the sample measured

The diagnostic read each side's public observation once before the first action and once after each committed action. Across the 1,032 four-side observations it counted 39,905 living-unit appearances in their owners' views. For 39,028 of them (97.80%) the same unit had the same type and hex in the preceding observation. These are action-boundary counts. Movement can refresh visibility several times within an action.

| Single worker, seconds | Original | Unit footprints |
| --- | ---: | ---: |
| Whole-game CPU, including the diagnostic | 23.3270 | 20.3960 |
| Whole-game elapsed | 23.3317 | 20.4004 |
| Astra execution | 6.4145 | 4.0463 |
| Student execution | 2.7837 | 2.5468 |

The game was the archived v6 BC validation case `val000010-team2v2-b0000-astra_partner-r0`, seed 2791729219. It used one student and three Astra seats, with 128 student and 903 Astra actions. Both runs matched the recorded fault-free 30-turn draw (reported turn 31), rank points, factions, teams and survivors. The action/event hash also matches the original validation-board profile. The CPU comparison includes all four additional diagnostic observations at each boundary in both arms. These timings apply to the student path in source `ba13e33` and its footprint-only successor. An eight-worker stage time was not measured. [Original board and profiling procedure](../lite_final_worker_20261104/REPORT.md)

| Identity | SHA256 |
| --- | --- |
| All 4,128 public observations, in order, both arms | `480a568b163719c99385e4077683c1053197aaa283169b269c88d93ef95ddedd` |
| All 1,031 action/event records, both arms | `3a0ddf8a35de37fe1a8463cfbd42d2acbc43b42c33609ef63e85b6e3517a70d1` |
| Frozen validation schedule | `e033edaabbb9610f3b0c88dda7787f0d35af6daea15adbf039cf67d5fca627a2` |
| Student tensor file | `5bfcc4af54fee1d2c4ef87cdb7712c1f5b84e1cd8edefd51377fd696b892c01b` |
| Rules | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Teacher | `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5` |

## Implementation and deterministic checks

Each game keeps at most one footprint per unit slot. A live unit's type, position, fixed terrain and rules determine the existing movement-cost Dijkstra search. A new type or origin replaces the cached tile list. Death releases it. Every refresh still unions each live unit's tiles into its current side's sight, then performs the existing fog, shroud, allied sharing, village ownership, concealment and enemy-memory updates. Every intermediate movement step still calls the same visibility update. Snapshot serialization omits the derived state. Clones start with an empty cache, including the clones used by forecasts and atomic batch rollback.

All 22 release-mode Rust tests passed. The new fixture counts Dijkstra executions for stationary units, relocation, type change, death and replacement. It compares serialized state at each mutation with a cold reference and checks the cache is absent from snapshots. The 22 Python information-isolation, restore, batch rollback and movement fixtures also passed. [Raw profiles, counters, build and test logs](traces-and-checks.tar.gz)

## Ubuntu commands

Each source was shipped by `git archive` into a fresh directory under `/home/tongshu/acceptance`. Both source trees linked `data/rules` from the frozen v6 readiness source. The baseline linked the accepted Lite extension from `lite_lua_cost_20261104/fast/.extension`. The candidate built offline with the same toolchain and cached release dependencies. Python was 3.12.3 and PyTorch was 2.9.1+cpu.

| Source directory | Source commit | Archive SHA256 | Extension SHA256 |
| --- | --- | --- | --- |
| `vision_footprint_baseline_20261104` | `ba13e33e79f33832bb93d2cfd299eb24ed538a81` | `df4d924c0c69a79ee459ca72ba8ecd05ec74d6f6839146258fab2e989d59755c` | `4d228e11e980ee3f91b93d79b71b9efbb429b8ea0eb3797bb18a2afbae512263` |
| `vision_footprint_candidate_20261104` | `f90d830a42718a6d6bab4d010d233abb6b8fa4ff` | `8b4d2a69cc943a0fc943c735f06b7b55003f79fabac6cb77b1f3888cf80c177f` | `bcd12b0a20f8d12c374aba8c1a15a30fed69875f685fdc3c56050f2fbb7cedd1` |

The first baseline invocation completed gameplay but exited 1 while assembling its profile because `SOURCE_COMMIT` was unset. Its Python profiler output survived, and its full-view digest and footprint count were unavailable. The corrected baseline set the source identity and wrote its output in a fresh directory. Each valid arm ran exactly once, under a 150-second timeout. Neither arm used holdout games or updated a learner. [Measurement wrapper](measure_views.py)

```sh
export PYTHONPATH=.extension:.:vendor/arena OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
py=/home/tongshu/venv/bin/python
parent=/home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness
cd /home/tongshu/acceptance/vision_footprint_baseline_20261104
SOURCE_COMMIT=ba13e33e79f33832bb93d2cfd299eb24ed538a81 timeout --signal=TERM --kill-after=5s 150s \
  "$py" -B verification/vision_footprint_20261104/measure_views.py "$parent" baseline-views-corrected --score-only-astra
cd ../vision_footprint_candidate_20261104
export PYO3_PYTHON="$py" CARGO_TARGET_DIR="$PWD/.build"
cargo test --release --offline --manifest-path engine_lite/Cargo.toml
cargo build --release --offline --manifest-path engine_lite/Cargo.toml
cp .build/release/lib_engine_lite.so .extension/_engine_lite.so
SOURCE_COMMIT=f90d830a42718a6d6bab4d010d233abb6b8fa4ff timeout --signal=TERM --kill-after=5s 150s \
  "$py" -B verification/vision_footprint_20261104/measure_views.py "$parent" candidate-views --score-only-astra
"$py" -B -m unittest -v tests.v5.test_engine_contract.InformationIsolationTest \
  tests.v5.test_engine_contract.SnapshotTest tests.v5.test_engine_contract.BatchApiTest tests.v5.test_engine_contract.MovementTest
```

The raw archive SHA256 is `7c8157ed8549ecf553183e85e29dee8a060789e036c01a18a13e0ccd96183930`.
