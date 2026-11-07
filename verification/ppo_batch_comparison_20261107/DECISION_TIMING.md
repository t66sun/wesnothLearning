# Formal holdout learner decision timing

Part of [#272](https://github.com/t66sun/wesnothLearning/issues/272), [#275](https://github.com/t66sun/wesnothLearning/issues/275) and [#278](https://github.com/t66sun/wesnothLearning/issues/278).

The official common holdout uses the existing collector and its existing job list. Its top-level worker times each scored learner decision from the score-only Lite observation/candidate entry through return from `FrozenPolicies.choose`. The interval includes public input construction, feature encoding and policy inference. Astra turns, diagnostic observations and game-step execution stay outside the interval.

Each holdout game result preserves its integer `learner_decision_ns` samples in the existing result logs. Completed fault-free games supply the reported count and nearest-rank p95 in milliseconds. Each source-contract panel reports one timing entry per real weight hash and a role-to-weight alias map. The common `holdout.json` retains those entries under the contract names. Equal-weight aliases reuse the same games and timing samples. Incomplete or faulted game samples remain available in the raw output.

On `cpuServer`, one no-game fixture passed in 0.001 s from commit `c1b71c8f68c40c402bbe7274fcf1e7d9a6740243`. It checked a pickle round-trip for the top-level worker, the unchanged submitted game list, both learner seats, exclusion of Astra/diagnostic/step work, all raw samples and alias reuse. Twenty synthetic scored decisions produced count 20 and p95 19 ms. A faulted game's raw sample remained present and stayed outside the scored timing summary.

The source archive SHA-256 was `1f18ac8e335bb0693594accf1ba812c75f807a6f3bd573db72f229bd8c106ba9`. The one-file reversion `847449d39cc0bccbe2cd2ba6db585605b867d449` moved the clock start after observation/candidate work. Its archive SHA-256 was `209c7ec7dde9016767fa3b9e35098e0e1ddf4cf925baf6e9cc5c0a2b73c03ae1`. Both archives verified before extraction. The reverted fixture failed at the raw interval assertion, where the second decision retained only 1 ms instead of 2 ms.

```sh
cd /home/tongshu/acceptance/ppo_formal_decision_timing_20261107_c1b71c8
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONPATH=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python=/home/tongshu/venv/bin/python
fixture=verification.ppo_batch_comparison_20261107.test_decision_timing
(cd red && "$python" -m unittest -v "$fixture") > red.log 2>&1
(cd green && "$python" -m unittest -v "$fixture") > green.log 2>&1
```

This fixture supplied simulated decisions and mocked the collector executor. It ran no games, collection, training or measured policy benchmark. Formal p95 values come from the separately authorized common holdout. Native timing remains a separate decision for a validation-nominated deployment route.
