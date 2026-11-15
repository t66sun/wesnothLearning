# Frozen archived learner-state BC runner

[#335](https://github.com/t66sun/wesnothLearning/issues/335) implements one actor-only comparison from the same qualified v38 weights and fresh Adam state in both roles. Each step has 48 shared teacher-state rows and 16 exact matched slots. The learner role uses the archived learner views and their Astra labels in those slots. The original learner's committed public memory supplies the prefix. The objective is the existing exact action CE plus 0.1 of the BC marginal loss. The value-head tensors are frozen.

## Ubuntu verification

All 26 focused tests passed in 9.666 seconds, including sparse learner histories, held-out rejection, actual optimizer updates, identical-row tensor equivalence, export and greedy reload, finite-score arithmetic and the complete synthetic paired panel. A single isolated reversion uses the teacher-side reference for an experimental slot. The source-swap assertion fails on the first such reference. [Focused tests](ubuntu-tests.txt) · [Expected revert failure](revert-test.txt)

The three real plans were loaded read-only. For each seed the loader assembled 4,096 eligible original teacher targets and 1,024 distinct learner-state targets, and checked every matched stratum and both 64-target step assignments. All 1,024 learner targets per seed carried an original committed prefix. The three load times were 41.555, 41.033 and 40.719 seconds. This check ran on source `2656d36bd0f350a775166340cf0a38bfce8b039b` with Git archive SHA-256 `5d634c2f1fa7cf3c4b11d509ddad18ca6e314378353f9d155fd1ef4446946159`. Its trainer file matches the final source byte for byte. [Read-only output](real-read.txt)

The final checks and no-game preparation ran from `b4afc707e86e5276a532cc8c3f8e06fb8d4b12a3` with Git archive SHA-256 `1b9e4773d77983752b83c9daed091f17dc48e1cfa92ba49387d391db4d457ebe`. The source implements the frozen [qualified corpus and paired design](../duel_learner_state_extended_20261115/REPORT.md). The board, rule, extension, v38, source, corpus and exact step identities are bound by the launch and cited inputs.

```sh
/home/tongshu/venv/bin/python -m unittest -v \
  tests.v5.test_duel_learner_state tests.v5.test_finite_score tests.v5.test_lite_policy_memory
```

## Reviewed launch for #336

The [launch manifest](launch.json) has SHA-256 `35694cb2c402a957a02fce88ac4a075836b435567164f21619ef5ced0bc7591d`. The [frozen schedule](formal-schedule.json.gz), before gzip, has SHA-256 `8c5bcc88a1315481e86968f58517316f94bbc3528936a08c74b1ca928b5b595d`. Preparation generated 1,260 planned games over 180 paired slots. The launch directory contains the manifest and schedule. Formal training and evaluation await explicit authorization.

The continuous limit is 14,400 seconds with 600 seconds for preflight, 1,200 per training cell, 5,400 for the game panel and 1,200 for audit and archiving. The six cells use one trainer thread and finish at exactly 64 Adam steps and 4,096 target visits each. Eight workers score all seven greedy checkpoint roles against frozen Astra. Adoption requires +5 normalized official-score points versus each comparator and positive paired 95% lower bounds for both differences.

After authorization, use the prepared Ubuntu extraction.

```sh
root=/home/tongshu/acceptance/duel-learner-state-20261115-79lhGH
cd "$root/source"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONPATH="$PWD:/home/tongshu/acceptance/immutable_forecast_20261104/green/.extension"
/home/tongshu/venv/bin/python -u -m verification.duel_learner_state_extended_20261115.driver \
  run "$root/formal" --launch-sha256 35694cb2c402a957a02fce88ac4a075836b435567164f21619ef5ced0bc7591d
```
