# A3 equal-wall duel PPO comparison

Eight-game batches produced **37,799 fresh eligible decisions per measured PPO hour**, versus **23,367** for four-game batches (+61.8%). Committed decision visits increased **11.8%**. The equal-wall score difference was **+1.11 percentage points** on Hamlets (crossed 95% interval **[−20.74, +24.44]**) and **+0.19 points** on Silverhead Crossing (**[−10.93, +11.67]**). Both intervals cross zero, as do the intervals for either arm against the shared BC policy. The run establishes an observed throughput gain under the frozen Lite duel setup. Playing-strength improvement and score equivalence remain unestablished. Keep the four-game default. [A3 #272](https://github.com/t66sun/wesnothLearning/issues/272) · [Roadmap #269](https://github.com/t66sun/wesnothLearning/issues/269)

## Frozen comparison

Four and eight games per PPO batch used the same baseline commit `07db85b8ba4def9bfebc7b42fe4c7bec0c4fd1b0` and Lite extension, `official-score-30-v1`, fixed Astra `gpt6astra` / `probabilistic_combat_v6`, historical-action CE, KL ceiling 0.02, and the same optimizer, rehearsal and evaluation exclusions. Both arms used eight rollout workers and one trainer thread. Each of the three pairs started from the same qualified v38 BC actor and critic with Adam reset. The reused BC gate passed with 300 qualifying teacher games, 32 distinct scenario families and 90.59% overall candidate coverage. The original BC cost was 3,859.09 seconds, incurred once before this launch and shared by both arms. [Frozen inputs](../ppo_batch_comparison_20261107/inputs.json) · [BC qualification and original cost](../duel_ppo_acceptance_20261107/REPORT.md)

On Ubuntu `cpuServer`, the shared driver at `3cfb191640b693f19ce417f047d4596919df4175` used a 5,400-second PPO cap and a 5,100-second new-batch admission cutoff for each cell. The primary endpoint is the last complete checkpoint within that cap. Each cell was allowed the same window, and its actual elapsed time includes startup, admitted work and settlement. The shared driver exited 0 after 12 cells, 1,314 validation games and 900 holdout games. No route met both positive lower bounds on Hamlets required for nomination, so the conditional native comparison did not run. [Frozen protocol](../ppo_batch_comparison_20261107/PROTOCOL.md) · [Shared launch and recorded evidence](../ppo_roadmap_acceptance_20261108/REPORT.md)

The online check matched the first A8 batch against the first two baseline batches for each seed by ordinal, scenario and game family, combat seed, seat, factions and sampling seed. Each A8 first batch used ordinals 0–7 from the shared stream at one policy version, v38. All eight trajectories settled, with 960, 1,138 and 1,161 fresh targets and 3, 1 and 6 committed optimizer steps in seed order. [Prior scheduling and recovery evidence](../ppo_batch_contract_20261107/REPORT.md)

## Official score

Scores use the learner's official points divided by three, averaging the two seat rotations within each scenario. Hamlets full validation used 15 paired scenarios and the 10k panel used its six frozen scenarios. Silverhead Crossing used 30 paired scenarios on the frozen Lite board, with both seat rotations. The paired crossed bootstrap used 10,000 draws with seed `202611079`, resampling training seeds and matching scenarios within map. Each panel had one physical map. The Silverhead result covers that board. Shared BC and weight aliases used one physical evaluation per matching scenario and seat. The base execution contract, which covers both A3 arms and their shared BC, contributed 642 actual Hamlets games and 420 Silverhead games.

| Equal-wall panel | Shared BC | Four-game means by seed | Eight-game means by seed |
| --- | ---: | --- | --- |
| Hamlets | 0.41111 | 0.47778 / 0.53333 / 0.26667 | 0.42222 / 0.38889 / 0.50000 |
| Silverhead Crossing | 0.35000 | 0.43889 / 0.45000 / 0.38333 | 0.42222 / 0.41667 / 0.43889 |

All per-seed columns and lists follow `202611071`, `202611072`, `202611073`. Differences are percentage points.

| Panel and endpoint | Contrast | Per seed | Pooled mean [crossed 95% interval] |
| --- | --- | --- | --- |
| Hamlets wall | 8 − 4 | −5.56 / −14.44 / +23.33 | +1.11 [−20.74, +24.44] |
| Hamlets wall | 4 − BC | +6.67 / +12.22 / −14.44 | +1.48 [−19.26, +21.48] |
| Hamlets wall | 8 − BC | +1.11 / −2.22 / +8.89 | +2.59 [−19.26, +21.85] |
| Silverhead wall | 8 − 4 | −1.67 / −3.33 / +5.56 | +0.19 [−10.93, +11.67] |
| Silverhead wall | 4 − BC | +8.89 / +10.00 / +3.33 | +7.41 [−4.07, +19.81] |
| Silverhead wall | 8 − BC | +7.22 / +6.67 / +8.89 | +7.59 [−5.74, +20.93] |
| Hamlets 10k | 8 − 4 | +27.78 / −5.56 / −16.67 | +1.85 [−27.78, +33.33] |
| Hamlets 10k | 4 − BC | −25.00 / +5.56 / +8.33 | −3.70 [−40.74, +29.63] |
| Hamlets 10k | 8 − BC | +2.78 / 0.00 / −8.33 | −1.85 [−24.07, +17.59] |
| Hamlets 30k | 8 − 4 | +21.11 / +1.11 / 0.00 | +7.41 [−16.67, +30.37] |
| Hamlets 30k | 4 − BC | −8.89 / +7.78 / −1.11 | −0.74 [−20.00, +18.52] |
| Hamlets 30k | 8 − BC | +12.22 / +8.89 / −1.11 | +6.67 [−15.56, +27.78] |
| Hamlets selected | 8 − 4 | +14.44 / +12.22 / +4.44 | +10.37 [−6.67, +27.04] |
| Hamlets selected | 4 − BC | +3.33 / +1.11 / −4.44 | 0.00 [−14.81, +15.19] |
| Hamlets selected | 8 − BC | +17.78 / +13.33 / 0.00 | +10.37 [−7.04, +24.07] |

The shared BC score on the small 10k panel was 0.52778. Both 10k and 30k were reached in every cell. The table gives the first full boundary, with the number of fresh decisions beyond the threshold and approximate seconds from the runner's cell clock. These are paired validation endpoints at nearby decision counts. Production `selected` is reported separately on full Hamlets. Silverhead used the preregistered wall endpoint and BC.

| Seed | Games per batch | 10k decisions (overshoot), elapsed s | 30k decisions (overshoot), elapsed s |
| --- | ---: | ---: | ---: |
| 202611071 | 4 | 10,111 (+111), 1,490 | 30,068 (+68), 4,618 |
| 202611071 | 8 | 10,110 (+110), 938 | 30,312 (+312), 2,837 |
| 202611072 | 4 | 10,110 (+110), 1,508 | 30,493 (+493), 4,638 |
| 202611072 | 8 | 10,105 (+105), 909 | 30,415 (+415), 2,855 |
| 202611073 | 4 | 10,353 (+353), 1,518 | 30,033 (+33), 4,701 |
| 202611073 | 8 | 10,574 (+574), 981 | 30,857 (+857), 2,900 |

## Rollout and update cost

Every game counted below has a distinct game-family identity within its cell. Scenario families measure physical scenario reuse and numbered 92 in each cell. Fresh eligible decisions count each settled batch's targets once, including when KL rejects an update. Visits count the decisions inspected by optimizer steps and can repeat a target. Rejected visits are inspected minus committed visits. Planned steps that never executed are separate from both.

| Seed | Games per batch | Settled batches | Games | Fresh decisions | Fresh/hour | Committed visits | Rejected visits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 202611071 | 4 | 82 | 328 | 33,463 | 23,385 | 68,957 | 13,862 |
| 202611071 | 8 | 68 | 544 | 54,492 | 38,108 | 74,897 | 11,945 |
| 202611072 | 4 | 82 | 328 | 33,828 | 23,781 | 66,085 | 13,237 |
| 202611072 | 8 | 68 | 544 | 53,225 | 37,389 | 76,433 | 12,174 |
| 202611073 | 4 | 86 | 344 | 32,630 | 22,934 | 67,658 | 13,464 |
| 202611073 | 8 | 66 | 528 | 54,285 | 37,897 | 75,242 | 12,334 |
| Total or pooled rate | 4 | 250 | 1,000 | 99,921 | 23,367 | 202,700 | 40,563 |
| Total or pooled rate | 8 | 202 | 1,616 | 162,002 | 37,799 | 226,572 | 36,453 |

Pooled rates divide total fresh decisions by the sum of measured cell times. The throughput gains by seed were +63.0%, +57.2% and +65.2%. Four-game cells committed 1,179 optimizer steps, rejected 247 at the KL guard and left 990 planned steps unattempted. Eight-game cells committed 1,245, rejected 202 and left 2,217 unattempted. Committed visits per fresh target fell from 2.03 to 1.40.

| Seed | Games per batch | Cell wall, s | Rollout, s | Preparation, s | Training, s | Internal validation, s | Prep / update | Prep / wall | Trainer peak RSS, MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 202611071 | 4 | 5151.5 | 1222.6 | 2112.4 | 1555.1 | 237.9 | 57.6% | 41.0% | 1,368 |
| 202611071 | 8 | 5147.7 | 1434.8 | 1880.1 | 1631.3 | 180.7 | 53.5% | 36.5% | 1,433 |
| 202611072 | 4 | 5120.9 | 1265.4 | 2120.4 | 1483.8 | 227.5 | 58.8% | 41.4% | 1,320 |
| 202611072 | 8 | 5124.8 | 1358.8 | 1900.3 | 1649.7 | 194.9 | 53.5% | 37.1% | 1,487 |
| 202611073 | 4 | 5122.1 | 1180.9 | 2197.4 | 1510.3 | 208.5 | 59.3% | 42.9% | 1,383 |
| 202611073 | 8 | 5156.7 | 1446.7 | 1847.1 | 1652.5 | 189.5 | 52.8% | 35.8% | 1,434 |

Preparation includes post-rollout input and rehearsal work plus PPO prepare/setup. Training time excludes this preparation. Summed preparation fell from 6,430.2 to 5,627.5 seconds and from 6.43 to 3.48 seconds per settled game. Its share fell from 58.6% to 53.3% of preparation plus optimization and from 41.8% to 36.5% of actual cell wall. Summed rollout wall rose from 3,668.9 to 4,240.3 seconds and optimization wall from 4,549.1 to 4,933.6 seconds. Peak trainer RSS across cells rose from 1,383 to 1,487 MiB.

One admitted batch per cell settled after the admission cutoff. For four games, those tails settled 34.174 / 4.591 / 20.853 seconds after cutoff and accounted for 497 / 361 / 516 fresh decisions. For eight games, the tails settled after 46.530 / 23.609 / 55.504 seconds and accounted for 984 / 783 / 635 decisions. All six finished before the hard deadline with zero unsettled eligible decisions, zero discarded history entries and no pending updates or validation.

## Recorded-behavior critic diagnostic

The existing MC diagnostic used complete trajectories from the first and last settled batches. First-batch behavior was the shared v38 BC policy. The late behavior versions were v119 / v119 / v123 for four games and v105 / v105 / v103 for eight games, recorded before each final update. The pooled base-contract result contained 60 distinct trajectories and 12 aliases, with 7,035 scored decisions, zero external cuts and zero missing trajectories. Recorded value minus complete return had pooled bias −0.0473, MSE 0.5374 and explained variance 0.3324. The scenario-mean bias interval was [−0.0975, +0.2520]. The diagnostic compares the values logged by the behavior policies with their own returns and leaves final-checkpoint calibration unmeasured.

## Evidence provenance

The original Ubuntu output is `/home/tongshu/acceptance/ppo269_shared_20261107_gzzXd6`. The shared report records the command, launch manifest and source/rule identities. The score table reads the original `experiment/result.json` and the base-contract panel `summary.json` files. Costs and boundaries come from `experiment/{base,a}-<seed>-ledger.json` and their recorded `duel/times` files. The first-batch check is recorded in `experiment/first-online-a8-<seed>.json` and MC in `experiment/mc-base-result`. Read-only checks verified the six A3 ledgers, terminal status, cutoff and threshold boundaries, and complete score panels. This report reused the original run for all results. [Shared archive](../ppo_roadmap_acceptance_20261108/REPORT.md)
