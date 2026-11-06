# Valid ordinary trend budgets

Issue: #222. Ordinary panels now fund the unchanged three-scenario minimum:
duel 6, FFA 12 and team 24 games, including every seat and both team contexts.
This explicitly increases the total per event from 18 to 42 games. Promotion
and final holdout budgets and all statistical floors are unchanged.

The configuration rejects insufficient trend budgets and floors exceeding the
validation/holdout roster capacity or fixed 12-block promotion capacity.
Trend panels advance by their block count through the validation roster instead
of cycling only three starting offsets. Each panel records `planned_games`.
Frozen historical manifests and outputs were not rewritten.

## Ubuntu evidence

- Red source `6035bb76682645b8fc1d4c329db873edcf74132e`: four tests, eleven
  subcase failures, zero errors in 0.256 seconds. The assertions expose the
  old one-scenario FFA/team panels, invalid accepted budgets, impossible floors
  and partial duel roster coverage. [red.log](red.log)
- First green attempt `d5bfaf13e23c986588f164bf93793ef3b902e062`: 48 tests,
  one failure in a pre-existing one-block faction-coverage fixture. That fixture
  queried only three of the current fifteen roster entries. Its six-faction
  assertion was retained; its schedule now uses actual three-block trend panels.
  [old_fixture_failure.log](old_fixture_failure.log)
- Accepted source `2153f1dd6cdd3f851c4bef74f4bef780db86252f`: all 48 affected
  tests pass in 8.951 seconds. [green.log](green.log)

Accepted command:

```sh
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
/home/tongshu/venv/bin/python -m unittest \
  tests.v5.test_trend_budget tests.v5.test_pipeline_schedule \
  tests.test_validation_cadence tests.test_training_revision \
  tests.v5.test_evaluation_design tests.v5.test_final_nomination
```

Each commit was shipped with `git archive` into a fresh Ubuntu directory.
Frozen maps were provisioned through the existing
`/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8` directory.

| Stage | Directory under `/home/tongshu/acceptance/` | Archive SHA-256 |
| --- | --- | --- |
| Red | `issue222_trend_red_20261106` | `9f03a47782093dadb8c024408b925a12f2b62922e79d5c516db6cd2da48d3e0b` |
| Accepted | `issue222_trend_green2_20261106` | `d99ae0ad23cb8ddea2b7bfcf933fabea99bf7e11f59412bea1c2b0484676d28f` |

The actual `FormatExperiment.validate_model` entry point is exercised with
recorded synthetic replies, five consecutive panels per format. All fifteen
faction designs are reached, each panel has three complete distinct scenarios,
and both team contexts remain present. Existing scenario-cluster checks still
reject repeated seeds on the same physical scene as independent evidence.

No Windows tests, new matches, collection or formal training ran. These checks
establish budget/design wiring, not PPO strength or throughput.
