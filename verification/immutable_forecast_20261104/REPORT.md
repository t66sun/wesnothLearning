# Public units in hypothetical combat forecasts

On the original Ubuntu release, moving an unseen, submerged Death Knight between two deep-water hexes changed a teacher forecast and two ordinary student candidates. Both twins had identical public inputs. The corrected release returned the full probability distribution and candidate rows of the originally unaffected twin in both positions. The referee state stayed unchanged. [Static outputs](reconceal.json) · [Original candidate feature differences](../worker_components_20261104/REPORT.md)

## Visibility and combat checks

The Lua host now builds the observing side's public unit list once, verifies the original attacker and target IDs, and checks that the landing terrain is known. It relocates only the visible attacker in that list. The existing tile visibility and concealment predicates can remove an originally public unit after the move. Only projected public allies can reveal it. The same combat calculation handles both current and hypothetical positions, including status immunities, weapon errors and exact HP probabilities. The forecast borrows the game immutably. A counted Rust host call went from one referee clone and two public rosters to zero clones and one public roster.

| Frozen board | Original mean HP, attacker / defender | Corrected mean HP, attacker / defender |
| --- | --- | --- |
| Spearman vs Skeleton, hidden Death Knight near | 18.0 / 28.6 | 23.4 / 28.6 |
| Same legal public inputs, hidden Death Knight far | 23.4 / 28.6 | 23.4 / 28.6 |
| Rogue vs Skeleton, previously visible FFA flanker re-conceals | 29.2 / 26.8 | 29.2 / 26.8 |
| Same attack without a flanker | 29.2 / 26.8 | 29.2 / 26.8 |
| Same attack with a visible flanker | 29.2 / 21.4 | 29.2 / 21.4 |

The two corrected hidden-donor queries matched across the full forecast, all 30 generated candidates, public view, public legal list and student scene. Each of the three Rogue fixtures matched its original release across the full distributions and all 37 candidates. The Rogue's hypothetical landing belongs to its ordinary public legal list. The positive control shows that a visible hostile third-side flanker still grants backstab. Each query checked its own pre/post snapshot, and no board was stepped for these static comparisons. [Exact distributions and input/output digests](reconceal.json)

On the original extension, the hidden-donor equality assertion failed on the forecast. The original Rust work-count assertion observed `(1, 2)` instead of the required `(0, 1)`. The original and corrected releases both passed the positive re-concealment checks. The corrected release passed the full **25 Rust tests** and **34 targeted Python checks**. Coverage includes hidden original IDs, projected attacker/target visibility, unknown or out-of-bounds landings, invalid weapon, snapshot/RNG preservation and the unchanged visibility-search count across successful and rejected queries. [Original failing assertions and corrected test logs](results.tar.gz)

Reuse of the registered v6 inputs is limited to the audited 158 reachable units, adjacent attack geometry and recorded scenario settings. The broader filtered catalog contains the reproduced hidden donor. The frozen teacher and rules file digests are unchanged, while the engine source and extension have new identities. [Bounded compatibility and reproducible roster extraction](BOUNDED-COMPATIBILITY.md)

## One matched validation game

The preselected Loris River team board was `val000010-team2v2-b0000-astra_partner-r0`, seed `2791729219`. Both score-only flags were on. The same v10 model, teacher, source schedule, filtered rules, seats, numerical threads and 30-turn limit were used in the two records. The integrated baseline already existed. The candidate game ran once on `cpuServer` and exited 0.

| Whole-worker measurement | Integrated baseline | Corrected forecast |
| --- | ---: | ---: |
| CPU, seconds | 17.010085134 | 14.765023324 |
| Wall, seconds | 17.012544049 | 14.768974524 |
| Astra / student decisions | 903 / 128 | 903 / 128 |

The **13.20% CPU reduction** passed the predeclared 6% threshold of at most 15.989480026 CPU seconds. The ordered 1,031 actions and referee events retained SHA256 `3a0ddf8a35de37fe1a8463cfbd42d2acbc43b42c33609ef63e85b6e3517a70d1`. All four public views at the initial position and after each action, 4,128 observations, retained SHA256 `480a568b163719c99385e4077683c1053197aaa283169b269c88d93ef95ddedd`. Both complete official results matched the archived fault-free turn-limit draw with four survivors. This measurement covers one validation board. No training or final holdout was run for this change. [Whole-worker profiles, view hashes and comparison](results.tar.gz)

## Identities and commands

The timing reference used integrated source `7889264e74a5151ebd21d7185f7b220662818c37` with evidence-only probe `90c81a5cf9204bb2a9fc46d59c457183f4c8f836`. Ubuntu received separate Git archives in `/home/tongshu/acceptance/immutable_forecast_20261104`, using distinct Cargo target directories. The original test-only source reused the integrated baseline release for the Python fixture. [Integrated baseline provenance](../lite_intent_legality_20261104/REPORT.md)

| Source | Tested commit | Git archive SHA256 | Release extension SHA256 |
| --- | --- | --- | --- |
| Original implementation with failing tests | `0a32703484fdcafd7912deb377c6a9711aaac1c0` | `55791458a47560e122b6109e35d1b28593e8595a3cdedc94253fe480dd5d2d75` | `fa0519eb3e5c8eced558e00598046950ae2edb8a2c0cd5f9352ccf7f84a13d69` |
| Corrected implementation | `98820244140cafb1a78755f42dc8cb6b3092b421` | `4349e169de6dba0e9cb39d2ff78bd5ccf23f7637069e388bd74ff5ed4476ab76` | `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` |

The workspace mounted the frozen rules, opponents, schedules and archived policy from their original locations. With the corresponding `.extension/_engine_lite.so` and source root on `PYTHONPATH`, the affected checks and the one candidate timing used

```sh
cd /home/tongshu/acceptance/immutable_forecast_20261104/green
export CARGO_TARGET_DIR="$PWD/.build" PYTHONPATH=.extension:.:vendor/arena
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export SOURCE_COMMIT=98820244140cafb1a78755f42dc8cb6b3092b421
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
cargo test --release --locked --offline --manifest-path engine_lite/Cargo.toml
cargo build --release --locked --offline --manifest-path engine_lite/Cargo.toml
/home/tongshu/venv/bin/python -B -m unittest -v tests.v5.test_forecast_public_context \
  tests.v5.test_combat_probability tests.v5.test_combat_immunity tests.v5.test_teacher_state_reuse \
  tests.v5.test_four_player_teacher tests.v5.test_engine_contract.InformationIsolationTest \
  tests.v5.test_engine_contract.SnapshotTest tests.v5.test_engine_contract.CombatTest
timeout --signal=TERM --kill-after=3s 150s /home/tongshu/venv/bin/python -B -u \
  verification/immutable_forecast_20261104/measure.py \
  /home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness ../after --score-only-astra
```

The results archive SHA256 is `70647f9904e0cca25f6c5640e616d0857c5a506f352cd440b9b55b94a661ca9e`. The standalone static forecast capture SHA256 is `840d490d70664ffa9d061f6d068941945be0ae826335204b2a377a96220f20ab`.
