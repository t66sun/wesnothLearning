# B3 candidate support and playing strength

Ubuntu `cpuServer`, 2026-11-07 to 2026-11-08. [#275](https://github.com/t66sun/wesnothLearning/issues/275) · [Common #269 run and frozen records](../ppo_roadmap_acceptance_20261108/REPORT.md)

B1+B2 raised final BC coverage from **90.59% to 90.95%**, driven by 124 more exact combat matches. Across 1,016 settled PPO games, the learner selected a B1 replacement weapon or B2 low-exposure recruit in **557 games**. On Silverhead Crossing, equal-time B PPO scored **43.33%** versus **42.41%** for base PPO and **43.33%** for its own BC. The paired intervals include benefit and harm. B did not qualify for deployment nomination on Hamlets, and the strength evidence does not support promoting v10 to the default candidate set.

## Frozen comparison

The four-game B and base cells used seeds `202611071`, `202611072`, `202611073`, the same ordinal scenario stream, fixed Astra, and `official-score-30-v1`. Both used relational-v5, the existing reward, historical-action CE and KL limit 0.02. The B-only execution source was `e3213830f6fe4f37a259b491a534d61c765ee83d` (`work-12000-v10`), base was `07db85b8ba4def9bfebc7b42fe4c7bec0c4fd1b0` (`work-12000-v8`), and the shared driver was `3cfb191640b693f19ce417f047d4596919df4175`. The launch manifest SHA-256 was `35691d7b2e21c73a5cfee79aa97da0f39c75841811999076d4b46c8ee8c7dd49`. The common archive identifies the source tarballs, extensions, rules, teacher and maps. The B mechanisms and the experimental prerequisites have separate evidence. [B1 weapon retention](https://github.com/t66sun/wesnothLearning/blob/433c44300e1f75b7415b07fb49703b78882fd63b/verification/candidate_weapon_retention_20261107/REPORT.md) · [B2 recruit positions](https://github.com/t66sun/wesnothLearning/blob/5aadffd8415cdc543703947b609afdc42e5ffdf2/verification/candidate_recruit_positions_20261107/REPORT.md) · [#298 initializer](https://github.com/t66sun/wesnothLearning/pull/298) · [#299 telemetry](https://github.com/t66sun/wesnothLearning/pull/299)

## BC qualification and coverage

Both BC arms used the same pinned v8 actor initializer, seed `202611060`, fresh critic, Adam and corpus, and a 150-minute cap. B collected fresh v10 rows and matched all 300 teacher job IDs to the historical base qualification by seed, game family, scenario family, map hash and teacher source. Both reached v38 with 300 valid teacher games and passed the existing coverage, imitation and scenario gates. Their qualification records counted 30 distinct scenarios for B and 32 for base, both above the minimum of 12. The opening probe failed in both arms and was nonblocking. B BC took **3,444.40 s** (57.41 minutes) in this launch. The compatible v8 base endpoint took **3,859.09 s** (64.32 minutes) in #227 and was reused. [Historical qualification and cost](../duel_ppo_acceptance_20261107/REPORT.md)

| Teacher action class | Base final match | B final match | Change in matches |
| --- | ---: | ---: | ---: |
| All | 29,693 / 32,779 (90.59%) | 29,812 / 32,779 (90.95%) | +119 |
| Recruit | 4,249 / 4,843 (87.73%) | 4,244 / 4,843 (87.63%) | −5 |
| Move | 12,841 / 13,999 (91.73%) | 12,841 / 13,999 (91.73%) | 0 |
| Combat, gate class | 8,973 / 10,307 (87.06%) | 9,097 / 10,307 (88.26%) | +124 |
| Stationary attack | 2,086 / 2,250 (92.71%) | 2,102 / 2,250 (93.42%) | +16 |
| Move-attack | 6,887 / 8,057 (85.48%) | 6,995 / 8,057 (86.82%) | +108 |
| End turn | 3,630 / 3,630 (100%) | 3,630 / 3,630 (100%) | 0 |

| Imitation gate measure | Base BC | B BC |
| --- | ---: | ---: |
| Effective | Yes | Yes |
| All sampled intents, top-1 | 691 / 925 (74.70%) | 694 / 927 (74.87%) |
| Recruit, top-1 | 188 / 220 (85.45%) | 190 / 220 (86.36%) |
| Move, top-1 | 302 / 371 (81.40%) | 315 / 369 (85.37%) |
| Combat, top-1 | 173 / 299 (57.86%) | 161 / 304 (52.96%) |
| Cross-entropy (uniform reference) | 1.56594 (3.55509) | 1.59873 (3.55628) |

The v10 support counters use the actual Astra intent and the actual proposal pool in that same state. `Not proposed` means absent from the proposal pool and final list. `Truncated` means the intent was proposed and absent from the final list. The teacher acts in BC, so the model-selection split applies to DAgger queries on learner decisions. The historical v8 BC and base PPO records lack these proposal observations. Their final-match counts cannot split misses by proposal stage. [Telemetry definition and fixture](https://github.com/t66sun/wesnothLearning/blob/8205c60d30b3f69933fd0c817833b64302be3e82/verification/candidate_support_telemetry_20261107/REPORT.md)

| B BC teacher intent | Total | Not proposed | Truncated | Retained |
| --- | ---: | ---: | ---: | ---: |
| Recruit | 4,843 | 307 | 292 | 4,244 |
| Move | 13,999 | 1,111 | 47 | 12,841 |
| Stationary attack | 2,250 | 0 | 148 | 2,102 |
| Move-attack | 8,057 | 187 | 875 | 6,995 |
| End turn | 3,630 | 0 | 0 | 3,630 |
| **All** | **32,779** | **1,605** | **1,362** | **29,812** |

## PPO selection in settled rollouts

The three B cells had **100,621 learner decisions in 1,016 unique game families**, compared with 99,921 in 1,000 unique game families for base. Each arm visited 92 distinct scenario families. All of these policy games completed with eligible training shards. The selection counts use the wall checkpoint's settled batch history to join job IDs to the original schedules. An offer counts once per decision if any final candidate carries the tag. A B1 tag marks an actual weapon replacement in a slot. A B2 tag marks a retained candidate from the lower-exposure recruit lane. Its overlap with v9 offers is unmeasured.

| Affected candidate | Offered decisions (% of all learner decisions) | Selected / offered | Selected / all learner decisions | Games with offer / selection |
| --- | ---: | ---: | ---: | ---: |
| B1 weapon replacement | 8,111 (8.06%) | 545 / 8,111 (6.72%) | 0.54% | 830 / 343 |
| B2 low-exposure recruit | 2,420 (2.41%) | 688 / 2,420 (28.43%) | 0.68% | 734 / 379 |

| Seed | B games | B1 selected / offered (games with selection) | B2 selected / offered (games with selection) | Games with either selection |
| --- | ---: | ---: | ---: | ---: |
| 202611071 | 336 | 187 / 2,634 (109) | 226 / 804 (128) | 180 |
| 202611072 | 336 | 188 / 2,819 (116) | 233 / 805 (125) | 186 |
| 202611073 | 344 | 170 / 2,658 (118) | 229 / 811 (126) | 191 |

DAgger separately compares the teacher intent with the sampled learner action when a teacher query occurs. The denominator below is the **19,851 actual queries** in the same settled B rollouts. Of 17,641 retained teacher intents, the learner chose 10,674 (60.51%) and passed over 6,967 (39.49%). These queries cover all action classes. The evaluation panels used score-only jobs, so the counts describe rollout behavior during training.

| B PPO DAgger intent | Queries | Not proposed | Truncated | Retained, learner passed over | Retained, learner selected |
| --- | ---: | ---: | ---: | ---: | ---: |
| Recruit | 2,480 | 172 | 211 | 1,189 | 908 |
| Move | 7,001 | 844 | 12 | 2,165 | 3,980 |
| Stationary attack | 1,437 | 0 | 98 | 610 | 729 |
| Move-attack | 6,080 | 106 | 767 | 2,866 | 2,341 |
| End turn | 2,853 | 0 | 0 | 137 | 2,716 |
| **All** | **19,851** | **1,122** | **1,088** | **6,967** | **10,674** |

## Official score and cost

Score is official duel points divided by three, averaged over both seats, scenarios and training seeds. Intervals use 10,000 paired crossed draws of seeds and scenarios stratified by map. Each distinct weight set is evaluated once per contract and reused for aliases. The common panels contain 15 Hamlets validation scenarios (six for 10k) and 30 Silverhead holdout scenarios. Each scenario has two seat rotations, with combat seeds paired across arms. Silverhead contributes one physical board. [Frozen panel protocol](../ppo_batch_comparison_20261107/PROTOCOL.md)

| Panel and endpoint | Base PPO score | B PPO score | B − base, pp [95% interval] | B − own BC, pp [95% interval] | Base − shared BC, pp [95% interval] |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Silverhead, wall** | **42.41%** | **43.33%** | **+0.93 [−9.44, +10.74]** | **0.00 [−12.41, +12.41]** | **+7.41 [−4.07, +19.81]** |
| Hamlets, wall | 42.59% | 35.93% | −6.67 [−24.44, +13.70] | −6.30 [−22.96, +9.63] | +1.48 [−19.26, +21.48] |
| Hamlets, 10k | 49.07% | 40.74% | −8.33 [−32.41, +19.44] | +7.41 [−31.48, +39.81] | −3.70 [−40.74, +29.63] |
| Hamlets, 30k | 40.37% | 46.30% | +5.93 [−13.33, +24.81] | +4.07 [−11.11, +21.48] | −0.74 [−20.00, +18.52] |
| Hamlets, production-selected | 41.11% | 38.52% | −2.59 [−17.78, +12.96] | −3.70 [−23.33, +15.56] | 0.00 [−14.81, +15.19] |

| BC endpoint | Hamlets full | Hamlets 10k subset | Silverhead |
| --- | ---: | ---: | ---: |
| Shared base BC | 41.11% | 52.78% | 35.00% |
| B BC | 42.22% | 33.33% | 43.33% |

| Training seed | Silverhead base PPO | Silverhead B PPO | B − base, pp | B − own BC, pp |
| --- | ---: | ---: | ---: | ---: |
| 202611071 | 43.89% | 45.56% | +1.67 | +2.22 |
| 202611072 | 45.00% | 44.44% | −0.56 | +1.11 |
| 202611073 | 38.33% | 40.00% | +1.67 | −3.33 |

Wall roles use the last complete batch inside the common 90-minute ceiling with 85 minutes of new-batch admission. The 10k and 30k roles use first complete crossings. All six B and base cells reached both. Fresh decisions per hour divide settled fresh targets by observed PPO cell wall time, including startup and validation. Learner decision p95 uses the score-only policy path on the same Silverhead panel, from observation and candidate generation through feature encoding and policy selection. The timing boundary ends before the game step. Times and counts below are base / B in each column. [Timing contract](../ppo_batch_comparison_20261107/DECISION_TIMING.md)

| Seed | PPO wall, seconds | Settled games | 10k fresh | 30k fresh | Wall fresh | Fresh per hour | Wall p95, ms (timed decisions) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 202611071 | 5,151.53 / 5,140.95 | 328 / 336 | 10,111 / 10,110 | 30,068 / 30,436 | 33,463 / 33,600 | 23,385 / 23,529 | 58.44 (11,803) / 57.93 (11,454) |
| 202611072 | 5,120.90 / 5,103.35 | 328 / 336 | 10,110 / 10,333 | 30,493 / 30,147 | 33,828 / 33,818 | 23,781 / 23,856 | 58.44 (11,044) / 57.35 (11,343) |
| 202611073 | 5,122.07 / 5,122.54 | 344 / 344 | 10,353 / 10,063 | 30,033 / 30,264 | 32,630 / 33,203 | 22,934 / 23,334 | 58.07 (10,029) / 58.27 (11,457) |

Pooled PPO throughput was **23,573 fresh/hour for B** and **23,367 for base**. BC endpoint p95 was 56.77 ms over 10,812 B decisions and 59.13 ms over 11,738 base decisions. Across the three PPO cells, B used 15,366.84 seconds and base 15,394.50 seconds. Including B's fresh BC, B training used 18,811.24 seconds. The analogous base training sum with its historical BC is 19,253.59 seconds, of which 15,394.50 seconds were spent in this launch. B panel workers added 771.42 seconds for validation and 355.35 seconds for holdout. The base worker times, 1,482.24 and 627.22 seconds, include A roles and are shared overhead. The common report accounts for the remaining launch stages.

## First real BC, PPO, export and checkpoint reopen

- The first B BC batch wrote 846 of 946 teacher decisions in eight games. The first update read 728 Astra rows from six training families and 118 validation rows from two families. It completed 16 optimizer steps. The run later qualified the v10 `last_bc.pt` at SHA-256 `8f9d0063507fe2800e26329c4df295b695e001087aea18db3616152a263e7b4f`.
- For seed `202611071`, the branch recorded the qualifying BC identity and zero Adam states, then the driver reopened the saved v10 child with `resume=True` after the PPO phase request. The first rollout used its v38 sample export, with candidate identity `work-12000-v10`, in four complete games at ordinals 0–3. The exported `export.json` SHA-256 was `d88419c588d00d580c0a474ab1eeecbfaf99292c0169b8e8aa19d5a7c2d793e9`. The first update admitted 456 fresh decisions, committed three steps, hit `kl_stop`, and changed weights from `0426b087…` to `15503177…`. The panel worker later loaded and exported the pinned final v10 checkpoints for the recorded Lite games.
- The real reopen exercised the saved BC-to-PPO transition. Recovery from a process interruption within a B update was unobserved. The earlier Ubuntu fixtures cover the explicit v8-to-v10 initialization, strict reload and checkpoint behavior. The fixed B1/B2 legality witnesses and the proposal fixture remain the implementation-level evidence. [Initializer and reload](https://github.com/t66sun/wesnothLearning/blob/6a4a5d3f40da4faeeb62bbc814394e4d0522fe54/verification/candidate_actor_transfer_20261107/REPORT.md)

## Disposition and reproduction

B qualified, recovered combat coverage and used both affected candidate groups in sampled games. The joint experiment estimates B1+B2 together. Hamlets failed both positive-lower-bound nomination criteria for B. The frozen `deployment.json` recorded no route, so the conditional native strength stage had no eligible candidate. The Silverhead results leave equal-time strength and incremental PPO benefit unestablished for B. The modest measured Lite cost differences do not supply a strength reason to adopt v10.

The [read-only recount](count_support.py) uses the original BC gates and teacher job logs, the six `*-ledger.json` records, and each ledger's `duel/schedules/ppo-batch-*.json` and `duel/jobs.jsonl`. It verifies the settled job join, game-family uniqueness, fresh targets and BC support totals. Run from the evidence source on `cpuServer` against the original frozen paths.

```sh
python3 verification/candidate_support_strength_20261108/count_support.py \
  /home/tongshu/acceptance/ppo269_shared_20261107_gzzXd6
```

Scores and p95 come from `experiment/validation.json`, `experiment/holdout.json` and the matching panel result summaries. The B BC stage and gate come from `experiment/bc-b-qualification.json`. The [common run archive](../ppo_roadmap_acceptance_20261108/REPORT.md) preserves these records and the launch, job and checkpoint provenance.
