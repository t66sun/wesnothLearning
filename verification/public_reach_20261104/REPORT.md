# Reuse public reach inputs during Lite pathfinding

The same frozen team validation game used **19.289 CPU seconds after the change, down from 20.663 seconds**, a 6.65% saving on one worker against the predeclared 3% minimum. The matched jobs ran on Ubuntu without concurrent timing work. Both executed the original 1,031 actions and produced identical referee events, all 4,128 public observations and the archived official fault-free turn-limit result.

| Measurement | Original | New search |
| --- | ---: | ---: |
| Whole-worker CPU seconds | 20.6631 | 19.2885 |
| Whole-worker wall seconds | 20.6674 | 19.2927 |
| Local neighbor lists built in the nine-hex Rust search | 50 | 9 |

The original search enumerated local neighbors to produce destinations, then enumerated them again to determine whether each destination was reached by teleport. The revised search retains the ordered local prefix, appends only remote owned villages and applies the teleport cost only to that tail. The counted-work fixture also checks that an adjacent owned village costs two movement points on its terrain and a remote owned village costs one, both with the same direct predecessor. The existing occupancy, ZOC, unknown-terrain and slow rules still apply. The Lua reach/path bridge and legal-action enumerator can pass their existing same-side public unit slice directly into this search.

## Inputs and results

The case was `val000010-team2v2-b0000-astra_partner-r0`, seed 2791729219, on the v6 BC validation schedule. The harness ran 903 score-only Astra actions and 128 student actions with full observations. Formal final jobs also select the compact student path. This one-worker timing does not measure the duration of the 420-game final panel.

Both arms produced action/event SHA256 `3a0ddf8a35de37fe1a8463cfbd42d2acbc43b42c33609ef63e85b6e3517a70d1` and all-side observation SHA256 `480a568b163719c99385e4077683c1053197aaa283169b269c88d93ef95ddedd`. The rule SHA256 was `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`, teacher `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5`, student tensor file `5bfcc4af54fee1d2c4ef87cdb7712c1f5b84e1cd8edefd51377fd696b892c01b` and validation schedule `e033edaabbb9610f3b0c88dda7787f0d35af6daea15adbf039cf67d5fca627a2`. [Frozen fixture and measurement wrapper](../vision_footprint_20261104/measure_views.py)

| Ubuntu source | Identity | Observed check |
| --- | --- | --- |
| `combined_validation_rotation_20261104/src` | Baseline `3b109bd4639a56d54ceb63d099225a48ede1d0c7`, extension `8d7abbeda2b31636369cf5253a8b34e286435103876b38d83080a985f5b7d036` | Completed baseline trace in `reach_public_baseline_20261104` |
| `reach_public_red_20261104` | Test commit `89391a9744dc2151c14f65ada96a986c0106ef62`, source archive `16717132ffb92caf717bf45461cb882543be9263175acc3f31672c394e2a7dcb` | Regression observed 50 expansions versus 9 expected |
| `reach_public_green_20261104` | Candidate `d8bb5cac31751696751387b07bc6b786b62d1f50`, source archive `db1e2e2488e86cc83db9e66fd45f4d097a7c3163cc695e12267474b77536c410`, extension `fa0519eb3e5c8eced558e00598046950ae2edb8a2c0cd5f9352ccf7f84a13d69` | 23 Rust and 22 movement, information-isolation, snapshot and atomic-batch Python checks passed. Gate and complete trace verified. |

Each changed source was shipped by `git archive` into a fresh directory under `/home/tongshu/acceptance`. Rust used the existing offline release dependency cache and `PYO3_PYTHON=/home/tongshu/venv/bin/python`. The game runs used Python 3.12.3, PyTorch 2.9.1+cpu and one thread per numerical library. Each valid timing arm ran once.

```sh
base=/home/tongshu/acceptance
py=/home/tongshu/venv/bin/python
export PYTHONPATH=.extension:.:vendor/arena OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
parent=$base/bc_v6_readiness_20261103/runs/bc_readiness
cd "$base/combined_validation_rotation_20261104/src"
SOURCE_COMMIT=3b109bd timeout --signal=TERM --kill-after=5s 150s "$py" -B \
  "$base/vision_footprint_baseline_20261104/verification/vision_footprint_20261104/measure_views.py" \
  "$parent" "$base/reach_public_baseline_20261104/trace" --score-only-astra
cd "$base/reach_public_red_20261104"
export PYO3_PYTHON="$py" CARGO_TARGET_DIR="$PWD/.build"
cargo test --release --offline --manifest-path engine_lite/Cargo.toml reach_expands_local_neighbors_once -- --nocapture
cd "$base/reach_public_green_20261104"
export CARGO_TARGET_DIR="$PWD/.build"
cargo test --release --offline --manifest-path engine_lite/Cargo.toml
cargo build --release --offline --manifest-path engine_lite/Cargo.toml
cp .build/release/lib_engine_lite.so .extension/_engine_lite.so
SOURCE_COMMIT=d8bb5cac31751696751387b07bc6b786b62d1f50 timeout --signal=TERM --kill-after=5s 150s "$py" -B \
  verification/vision_footprint_20261104/measure_views.py "$parent" trace --score-only-astra
"$py" -B -m unittest -v tests.v5.test_engine_contract.InformationIsolationTest \
  tests.v5.test_engine_contract.SnapshotTest tests.v5.test_engine_contract.BatchApiTest tests.v5.test_engine_contract.MovementTest
```

The raw archive SHA256 is `e7390d05a6972cade4ecd59b95b645630f5f9bd2f32462af3cd824302d575c8b`. [Paired raw timings, traces and test logs](profiles-and-checks.tar.gz)
