# Archived learner-state BC formal acceptance

[#336](https://github.com/t66sun/wesnothLearning/issues/336) completed all six scheduled training cells and all 1,260 fault-free, task-terminal Lite games on Ubuntu `cpuServer`. The strength gate **did not pass**. Both learner-state contrasts require a gain of at least 5 percentage points and a crossed paired 95% lower bound above zero. [Machine-readable verdict](review.json) · [Raw replies, schedule and phase records](raw-metadata.tar.gz)

| Official-score contrast | Difference (pp) | Crossed paired 95% interval (pp) | Raw point difference / maximum |
| --- | ---: | ---: | ---: |
| Learner-state minus teacher-state | −4.01 | [−12.10, +3.21] | -65 / 1620 |
| Learner-state minus v38 | −0.49 | [−8.64, +7.35] | -8 / 1620 |
| Teacher-state minus v38 | +3.52 | [−2.47, +9.26] | 57 / 1620 |

The result covers the frozen corpus, initializer and three optimization-disjoint historical Lite boards.

## Scores

Games used the frozen Astra opponent and greedy inference under `official-score-30-v1`. Win/draw/loss is 3/1/0, divided by 3 to normalize the score. The 180 slots comprise 30 ordered nonmirror faction blocks on each map with both learner seats and matching combat seeds across all seven roles. The recount averages both seats within each block, weights maps equally and uses 10,000 crossed draws of the three paired training seeds and within-map scenario blocks, seeded with `2026111559`. The original v38 played each slot once and is shared across all paired comparisons.

Each map cell shows **wins/draws/losses · normalized score · round-cap count**. Each trained arm played 540 games pooled over its three checkpoints. Frozen v38 played 180 games.

| Board | Frozen v38 | Teacher-state | Learner-state |
| --- | ---: | ---: | ---: |
| The Road to Weldyn | 23/9/28 · 43.33% · 9 | 78/24/78 · 47.78% · 24 | 75/24/81 · 46.11% · 24 |
| A Summer of Storms | 10/30/20 · 33.33% · 30 | 38/101/41 · 39.81% · 101 | 30/95/55 · 34.26% · 95 |
| Ur-Thorodor | 25/7/28 · 45.56% · 7 | 75/19/86 · 45.19% · 19 | 66/20/94 · 40.37% · 20 |
| **Pooled** | 58/46/76 · 40.74% · 46 | 191/144/205 · 44.26% · 144 | 171/139/230 · 40.25% · 139 |

| Training seed | Teacher-state score | Learner-state score |
| --- | ---: | ---: |
| 202611151 | 45.74% | 33.15% |
| 202611152 | 40.93% | 40.37% |
| 202611153 | 46.11% | 47.22% |

## Work and time

Each trained role loaded the same qualified v38 actor, started fresh Adam at `0.0003` and committed exactly 64 steps with 4,096 labeled target visits. Both arms used exact action cross-entropy plus 0.1 times the existing BC marginal loss. Each step used 48 shared teacher-state rows and 16 matched slots. In the matched slots, each arm used its source's visible state, committed recurrent prefix and corresponding Astra action label. The recount verified the same v38 value-head tensor digest in all seven checkpoints. [Frozen data protocol](../duel_learner_state_extended_20261115/REPORT.md)

Run start was `2026-11-15T13:57:49.830616+08:00`. The run and raw archiving finished at `2026-11-15T14:46:17.030168+08:00` under the common deadline `2026-11-15T17:57:49.830616+08:00`. Training used one thread and the scheduled order shown below. The panel used eight workers. The launcher returned 0 with zero phase timeouts. [Launcher log](launcher.log) · [Run exit](run-exit.json)

| Phase | Actual seconds | Limit seconds |
| --- | ---: | ---: |
| Preflight | 0.199 | 600 |
| teacher-202611151 | 91.011 | 1200 |
| learner-202611151 | 108.956 | 1200 |
| learner-202611152 | 111.557 | 1200 |
| teacher-202611152 | 95.118 | 1200 |
| teacher-202611153 | 92.014 | 1200 |
| learner-202611153 | 110.239 | 1200 |
| Panel | 2294.073 | 5400 |
| Audit and raw archive | 4.027 | 1200 |
| Total active wall time | 2907.200 | 14400 |

## Frozen inputs and endpoints

[Approved launch and schedule](../duel_learner_state_runner_20261115/REPORT.md) · [Rules, extension, Astra, map and scope identities](../duel_learner_state_extended_20261115/inputs.json)

| Input | Identity |
| --- | --- |
| Formal source commit | `b4afc707e86e5276a532cc8c3f8e06fb8d4b12a3` |
| Git archive SHA-256 | `1b9e4773d77983752b83c9daed091f17dc48e1cfa92ba49387d391db4d457ebe` |
| Launch manifest SHA-256 | `35694cb2c402a957a02fce88ac4a075836b435567164f21619ef5ced0bc7591d` |
| Schedule SHA-256 | `8c5bcc88a1315481e86968f58517316f94bbc3528936a08c74b1ca928b5b595d` |
| Qualified corpus SHA-256 | `f7e3544ed07826a7350375f6bc00a1b1e3f14f1858121e9bc07859103713744e` |
| Raw replies SHA-256 | `f7fc606e3bbb6183b1e8b654f372b85687b4661e0d43ad109c3e20d12ab6c2cd` |

| Checkpoint role | Committed steps | Labeled visits | Checkpoint file SHA-256 |
| --- | ---: | ---: | --- |
| `bc` | 0 | 0 | `8fc61bbb0be5c2ad8d2ec5b56760ce3dbfa08eed008c490e9b2233624ea91ebe` |
| `teacher-202611151` | 64 | 4,096 | `cd4466b873089ffe73cffc037728e352ba617f0a49dd362f240a07eaf015079e` |
| `learner-202611151` | 64 | 4,096 | `7e157e5a729d2ae0e4f9e0df2a4655a2ac7b1e67cbd06d9754536d7db66a77b1` |
| `learner-202611152` | 64 | 4,096 | `0da9b7e102060ce29c2780aa9a5af389e472d5c1b49166ad30d0b8d699777a93` |
| `teacher-202611152` | 64 | 4,096 | `294f0850c0eb0484441354b655ed5177e369caac46ebb28b957f52fe82255e1b` |
| `teacher-202611153` | 64 | 4,096 | `28e60fbe861c05cf789a24f4a02a48bbf0a847a16f05bd71fb238c8a7058bc11` |
| `learner-202611153` | 64 | 4,096 | `f7637ca7b74189ae0d857e9bd3107f473ecb5db7f17f7c1478c83374b538dce4` |

The frozen binaries remain at the path recorded for each role in `endpoints.json` inside the raw archive. The [recount](recount.py) checked checkpoint and export bytes, model and value-head identities, Adam step counts and all seven roles. It joined raw winners and learner seats back to the schedule, recomputed integer scores and intervals independently, and matched the formal driver's point, interval and gate results. The archived launch, schedule, replies, formal audit and endpoint ledger match the Ubuntu run byte for byte. [Archive checksums](SHA256SUMS)

## Commands

The authorized run used the approved extraction and this command on Ubuntu.

```sh
root=/home/tongshu/acceptance/duel-learner-state-20261115-79lhGH
cd "$root/source"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONPATH="$PWD:/home/tongshu/acceptance/immutable_forecast_20261104/green/.extension"
/home/tongshu/venv/bin/python -u -m verification.duel_learner_state_extended_20261115.driver \
  run "$root/formal" --launch-sha256 35694cb2c402a957a02fce88ac4a075836b435567164f21619ef5ced0bc7591d
```

The read-only recount ran with the same environment from a separate Git archive of `7605be6c0c1479fdaef0733f5bdc2b70b5c4eca2`, with SHA-256 `56185477369e506f84598271987c6397a0198f5562ed942bc2f327448e180880`.

```sh
review=/home/tongshu/acceptance/duel-learner-state-review-20261115-76YPXa
/home/tongshu/venv/bin/python -u "$review/verification/duel_learner_state_acceptance_20261115/recount.py" \
  "$root/formal" "$PWD/verification/duel_learner_state_extended_20261115/inputs.json"
```
