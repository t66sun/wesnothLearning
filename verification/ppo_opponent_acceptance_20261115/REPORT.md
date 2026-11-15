# Mixed-opponent Lite duel PPO acceptance

[#322](https://github.com/t66sun/wesnothLearning/issues/322) under [#319](https://github.com/t66sun/wesnothLearning/issues/319) completed within the frozen budget. The mixed arm scored **40.37%** against Astra on the two holdout maps. Pure-Astra PPO and shared v38 BC each scored **39.44%**. The mixed arm gained **0.93 percentage points** against each comparator. Both 95% intervals crossed zero and both point estimates fell below the frozen thresholds. The mixed training recipe and endpoints did not pass the strength gate. [Protocol](../ppo_opponent_protocol_20261114/PROTOCOL.md)

## Budget and workload

The run started at 19:13:25.736 on 2026-11-14 and completed at 04:05:41.892 on 2026-11-15, Asia/Shanghai. The total was **8h 52m 16.156s** against 12h. The six cells used **8h 34m 57.649s** of their aggregate 9h cap. All six exited normally after the 85-minute admission window and before the 90-minute hard deadline. Hamlets validation used 322.756s, the holdout used 707.181s, and the automatic audit used 6.173s. The raw archive finished 1.585s after the audit.

| Seed | Arm | Wall (s) | Settled batches | PPO games | Fresh learner decisions | Committed optimizer steps | Astra / frozen BC games | Wall checkpoint |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 202611141 | Pure Astra | 5,161.070 | 82 | 656 | 64,541 | 485 | 656 / 0 | v120 |
| 202611141 | Mixed | 5,181.071 | 77 | 616 | 62,962 | 483 | 462 / 154 | v115 |
| 202611142 | Pure Astra | 5,113.629 | 80 | 640 | 64,704 | 473 | 640 / 0 | v118 |
| 202611142 | Mixed | 5,165.095 | 78 | 624 | 61,762 | 475 | 468 / 156 | v116 |
| 202611143 | Pure Astra | 5,105.337 | 82 | 656 | 64,523 | 494 | 656 / 0 | v120 |
| 202611143 | Mixed | 5,171.449 | 79 | 632 | 62,621 | 501 | 474 / 158 | v117 |
| All | Pure Astra | 15,380.035 | 244 | 1,952 | 193,768 | 1,452 | 1,952 / 0 | |
| All | Mixed | 15,517.614 | 234 | 1,872 | 187,345 | 1,459 | 1,404 / 468 | |

The common ordered training prefixes were 616, 624, and 632 games. Boards, factions, learner seats, combat seeds, and declared learner sampling seeds matched over each prefix. Every mixed batch put frozen greedy BC in two non-learner seats with different learner seat rotations. Astra supplied DAgger in both arms. All cells used λ = 0.95, the same v38 initial weights and empty Adam. All displayed endpoints were complete. Zero rollout replies recorded a budget interruption.

## Paired scoring

All **840 holdout games** and **210 separate Hamlets validation games** completed without faults. Both holdouts had 420 games, with seven checkpoint roles × 30 ordered faction pairs × two learner seat rotations. Raw winners were rescored as 3/1/0 and divided by 3. The 10,000-draw bootstrap crosses paired training seeds with within-map scenario resampling. Maps have equal weight.

| Panel | Shared BC | Pure Astra PPO | Mixed PPO | Mixed − pure PPO, pp [95% CI] | Mixed − BC, pp [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: |
| Two-map holdout | 39.44% | 39.44% | 40.37% | +0.93 [−4.72, +6.94] | +0.93 [−5.83, +7.22] |
| Ur-Thorodor | 45.56% | 45.56% | 47.41% | +1.85 [−9.44, +13.52] | +1.85 [−11.30, +14.26] |
| Face of the Enemy | 33.33% | 33.33% | 33.33% | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| Hamlets validation | 41.11% | 52.59% | 44.44% | −8.15 [−24.07, +6.67] | +3.33 [−12.96, +20.74] |

| Seed | Pure Astra PPO | Mixed PPO | Mixed − pure PPO | Mixed − shared BC |
| --- | ---: | ---: | ---: | ---: |
| 202611141 | 39.44% | 43.06% | +3.61 pp | +3.61 pp |
| 202611142 | 40.00% | 41.11% | +1.11 pp | +1.67 pp |
| 202611143 | 38.89% | 36.94% | −1.94 pp | −2.50 pp |

Face of the Enemy has no villages and all 420 games on it were draws. As a result, the observed score difference comes entirely from Ur-Thorodor. The preregistered equal weighting applies to both maps. The +8 pp PPO-relative and +5 pp BC-relative gates, each with a 95% lower bound above zero, remain unmet.

## Evidence and reproduction

Training and evaluation used Git archive commit `23029d7b1d092f73a3cc616bfe5672920417a803` on cpuServer. The source archive SHA-256 is `381aafd334e1edcdef11bf4a9765d65f930b977a06e4585d9b000cda0712f09f`. The launch SHA-256 is `835a2f973a9f80eea0360079c8109125dea086e5b6c2e9ac360352a428020a60`. The launcher created [original metadata](raw-metadata.tar.gz) at SHA-256 `e80b9c59f321dc4b11770f84c48b498ad6156066ac7776da4373ece2721e2454` (16,771,975 bytes). Its records cover schedules, raw game replies, budgets, launch, endpoint identities and the original automated scoring. The [run exit](run-exit.json) was written after the archive and is preserved separately. Model binaries and training shards remain at the run paths.

The [read-only review](review.py) came from Git archive commit `3d454f0f7c952728590130849089b5524c6e99b5`, tar SHA-256 `016b3a0429e36ca58114906e5bccd3b24174030913e60102dae5c520dca3f236`. It rebuilt all six workload ledgers with read-only capture, checked process timing, verified the seven checkpoints and panel tensor copies, and recomputed the paired scores from raw replies. [Review output](review.json) SHA-256 `9072774f3e20e984ffbd456f54f966621eb9e4c4d79154a19692fbeb8bcd2e61`.

```bash
base=/home/tongshu/acceptance/ppo322-formal-20261114-wGKDQ4/source
audit=/home/tongshu/acceptance/ppo322-review-20261115-oTUgtc
export PYTHONPATH="$base:/home/tongshu/acceptance/immutable_forecast_20261104/green/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
cd "$base"
/home/tongshu/venv/bin/python -u "$audit/verification/ppo_opponent_acceptance_20261115/review.py" "$base/runs/ppo322"
```
