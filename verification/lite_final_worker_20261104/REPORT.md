# Lite final-panel worker on a frozen validation board

On November 4, 2026, `cpuServer` replayed one team validation game with an unrecorded Astra seat path. It took **23.07 seconds**, down from **44.29 seconds** with the full learner observation path. All 1,031 planned actions and their ordered referee events matched across the two runs. The policy took 128 actions and the three Astra seats took 903. Both games matched the archived official result, a fault-free draw at the 30-turn limit (reported turn 31). [Raw profiles and test logs](profiles-and-tests.tar.gz)

| Occupied CPU seconds | Full observations | Score-only Astra |
| --- | ---: | ---: |
| Astra decision | 15.505 | 10.938 |
| Astra execution | 21.454 | 5.123 |
| Student host decision | 2.975 | 3.002 |
| Student host execution | 2.524 | 2.627 |
| All student tensor choices | 0.397 | 0.388 |
| Whole worker | 44.259 | 23.053 |

The whole-worker wall reduction was 47.9% (1.92×). The student still received its full observation and candidate set. The score-only Astra planner kept each unit's recorded home hex and the observed village ownership before and after actions. It used the shared action executor, including the same interruptions and end-turn handling. Opening probes, reward diagnostics and jobs collecting training rows keep their full outputs.

GNU gprofng attributed 79% of baseline and 72% of optimized sampled time inclusively to the Lua VM. The optimized sample attributed 17% to `Game::update_visibility` and 10% to `Game::reach`. The native summaries contain only 451 and 239 samples respectively. Timings in the table use the measured process clock and Python profile. The host constructor took 0.30 seconds in both runs. Torch reported one intra-op thread and four inter-op threads. The baseline worker consumed one CPU over the measured interval.

## Inputs and commands

The source was shipped by `git archive` into fresh directories under `/home/tongshu/acceptance/lite_final_worker_20261104`. The table gives commit and archive SHA256.

| Purpose | Commit | Archive SHA256 |
| --- | --- | --- |
| Baseline profile | `2917f67205fd4c083b15181a4227d62a8e2b98aa` | `41e0a053fe09fd6a5f67ece3abb26c6c8cc53b546d60f52ad0d0e44234d6569f` |
| Failing assertion | `eedbd0a2bd413ca23c7779c5258339a8be70da1d` | `31988d08c4fc07280346057ecc6bd79a49654c94c62722e67f719f413c193c8f` |
| Patched replay and build | `69b45c08e940d46ee18de345aaa565cf64bd600b` | `71320a8afd3415eee675f024f10e261e2913444b1d553decec5e116fadc5fbdc` |
| Final fixture checks | `b74b35e0ddf20dc9975ae7f47903411e21707ae8` | `4c64be4e63c680a5a560b78f89b5ba8f30efc08ab599f1f7cefa37eda4fc2f68` |

The game was `val000010-team2v2-b0000-astra_partner-r0`, on the Loris River validation map, seed 2791729219. The original v10 policy weights, control, roles, factions, starting board, referee rules and turn cap came from the [v6 ordinary BC run](../bc_ordinary_v6_20261103/REPORT.md). Both replays removed the validation learner telemetry to match the final-panel request shape. They used an isolated output and deadline. The baseline's production sources matched the v6 run. Python was 3.12.3, torch 2.9.1+cpu.

- Original schedule SHA256 `e033edaabbb9610f3b0c88dda7787f0d35af6daea15adbf039cf67d5fca627a2`
- Frozen team tensor SHA256 `5bfcc4af54fee1d2c4ef87cdb7712c1f5b84e1cd8edefd51377fd696b892c01b`
- Filtered rules SHA256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`
- v6 teacher SHA256 `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5`
- Baseline / optimized extension SHA256 `63b1c119670d4d0981925fafef4f781ab274f05fb0aa2fedafc8b24dfd503059` / `385f18c03e4c08d9b13d8970470f9decf131ff83053119d5a115b3c9d5bdbc1f`
- Paired action, event and commit-status SHA256 `3a0ddf8a35de37fe1a8463cfbd42d2acbc43b42c33609ef63e85b6e3517a70d1`

The patched build used `cargo build --release --offline --manifest-path engine_lite/Cargo.toml` with four build jobs and a fresh target. Both profiled calls exited 0 under separate 120-second limits. In each extracted source directory, use its committed harness and extension, the bound filtered rules, and the three numeric thread limits set to one. The baseline used its archived v6 extension and omitted `--score-only-astra`.

```sh
export PYTHONPATH=.extension:.:vendor/arena
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SOURCE_COMMIT=69b45c08e940d46ee18de345aaa565cf64bd600b
timeout --signal=TERM --kill-after=3s 120s gprofng collect app -p 10 -F off -o ../fast-cpu.er \
  /home/tongshu/venv/bin/python -B -u verification/lite_final_worker_20261104/profile_job.py \
  /home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness ../fast-observed --score-only-astra
```

## Regression and scope

The new compact-row assertion failed once on the baseline. On the changed build the paired synthetic game matched every teacher plan, full teacher ledger, execution event, committed flag and player-visible outcome. An independent fixture error affected two existing record-evidence checks on both source versions. Their phase cases reused a game ID and shard for different raw sequences. Giving each case its own ID and file kept the SQLite collision check active. The complete affected Ubuntu command then exited 0, **22 tests in 1.922 seconds**.

```sh
/home/tongshu/venv/bin/python -B -m unittest tests.v5.test_lite_score_astra \
  tests.v5.test_teacher_state_reuse tests.v5.test_allied_village_goal \
  tests.v5.test_record_evidence \
  tests.v5.test_lite_default.LiteDefaultTests.test_lite_final_evaluation_has_only_astra_controls \
  tests.test_lua_contracts -v
```

The [raw archive](profiles-and-tests.tar.gz) includes baseline, pre-repair and passing logs, both Python profiles, sampled native data and both official results. Its SHA256 is `115a4bf380a4db429bc698baadbc90e64ea1e59af5aedccc6cc6bb9ce04c3abe`. Full gprofng experiments with their symbol archives remain on Ubuntu. No holdout seed was played. This measures one validation board on one worker. The all-format final phase still needs its complete 420-game run under the bounded runner's own clock.
