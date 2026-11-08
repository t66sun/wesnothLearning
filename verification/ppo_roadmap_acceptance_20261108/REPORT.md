# PPO roadmap acceptance

The formal Ubuntu comparison completed all 12 cells and both shared score panels. Eight-game batches yielded 61.8% more fresh eligible decisions per measured PPO hour. Candidate support increased and the policy selected restored options. The trained spatial policy responded weakly to the two original public witness pairs. The equal-wall strength intervals for all three routes include zero on both panels. Hamlets nominated no deployment candidate. The default stays at four games with the baseline candidate and feature contracts. [Roadmap #269](https://github.com/t66sun/wesnothLearning/issues/269)

## Frozen sources and execution

| Item | Commit or SHA-256 |
| --- | --- |
| Shared driver | `3cfb191640b693f19ce417f047d4596919df4175` |
| Base and A-only batch experiment | `07db85b8ba4def9bfebc7b42fe4c7bec0c4fd1b0` |
| B-only candidates, actor transfer and telemetry | `e3213830f6fe4f37a259b491a534d61c765ee83d` |
| C-only public spatial encoder | `2e6be1838b46423b74eaf7d91932f5e0914ac047` |
| Launch manifest | `35691d7b2e21c73a5cfee79aa97da0f39c75841811999076d4b46c8ee8c7dd49` |
| Training rules | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Astra source / package | `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5` / `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933` |
| Base and C Lite extension | `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` |
| B Lite extension | `fdecbe2ee0aa10aee2d631dc14df2db713b957de6d4280f43db5804cac22a9d3` |
| Common actor initializer | `05908d7f972148ccc7b39b8df0cc00435e2176861654a632de44c379b94953ab` |
| Silverhead Crossing native file / frozen Lite board | `1cb14347604bc283a13b628f344b72cdbf5082ed6c43edcaccdec7ae1f8b6d58` / `50046e67a3d0a8bff1f6e91a5446049c193a469e9481d911da81d2837017f299` |

The Ubuntu run root is `/home/tongshu/acceptance/ppo269_shared_20261107_gzzXd6`. The original launcher started at 2026-11-07 15:29:11 UTC and finished at 2026-11-08 11:55:45 UTC with exit code 0. The driver used 73,592.18 seconds (20 h 26 min 32 s). The manifest records another 52.653 seconds of input preparation. The frozen total cap was 99,000 seconds, including 900 for preparation, 900 for preflight, 18,000 for two new BC qualifications, 64,800 for PPO, 5,400 for validation, 4,500 for holdout, 900 for reporting and 3,600 reserved for conditional native. The archive includes the actual launcher, source archives' identities, all stage requests and process records. Every launched stage exited successfully and within its deadline. Stage wall times sum to 61,669.78 seconds for PPO, 7,403.48 for new BC, 3,057.02 for validation, 1,368.08 for holdout, 63.84 for the recorded-behavior MC diagnostic and 2.95 for preflight. [Frozen design](../ppo_batch_comparison_20261107/PROTOCOL.md), [preregistered inputs](../ppo_batch_comparison_20261107/inputs.json)

All cells used eight Lite workers and one trainer thread on the same host, fixed Astra, `official-score-30-v1`, fixed rewards, the accepted control exclusion, historical-action CE and KL limit 0.02. The common learning rate was 0.0003, with four epochs and a configured minibatch of 256. Base and A started from the same qualified #227 v38 actor and critic. B and C each transferred the same historical actor initializer and separately qualified under their own data contract. All three BC endpoints used the same teacher seed and 300-game work allowance. Every PPO seed restarted Adam from its route's qualified full checkpoint.

| BC route | Teacher games | Coverage | Qualification wall, s |
| --- | ---: | ---: | ---: |
| Base, shared with A | 300 historical | 29,693 / 32,779 (90.59%) | 3,859.09 historical |
| B | 300 fresh | 29,812 / 32,779 (90.95%) | 3,444.40 |
| C | 300 fresh | 29,693 / 32,779 (90.59%) | 3,959.08 |

Each seed used a 5,400-second PPO window with a 5,100-second batch-admission cutoff. Across the matched prefix of each pair, all recorded game ordinals, scene and game families, combat seeds, learner seats, factions and sampling seeds agree. All admitted batches used one policy version and settled with all scheduled trajectories before the hard cap. All 12 cells saved the first complete 10k and 30k endpoints and the final settled wall checkpoint. The source-local BC exposure records and every recorded PPO rollout board exclude the physical Silverhead board.

| Route | PPO wall, s | Settled batches | Eligible games | Fresh decisions | Fresh per actual PPO hour |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base | 15,394.50 | 250 | 1,000 | 99,921 | 23,367 |
| A | 15,429.22 | 202 | 1,616 | 162,002 | 37,799 |
| B | 15,366.84 | 254 | 1,016 | 100,621 | 23,573 |
| C | 15,479.22 | 242 | 968 | 100,256 | 23,317 |

## Official score

Hamlets validation counted 1,314 physical games after alias deduplication, including the preregistered six-block 10k panel. The full validation has 15 faction-pair blocks. Silverhead counted 900 physical games for 12 wall and three BC policies across 30 ordered nonmirror faction assignments, each with both seat rotations. The panels used the same physical scene, combat seed, Astra package and learner seat per pair. Per-game scores are 1 for a learner win, 1/3 for a draw and 0 for a loss, as fractions of the official three-point maximum. The crossed paired bootstrap uses 10,000 draws at seed `202611079`, resampling the three training seeds and scenario blocks within map. The holdout estimates apply to one previously unused standard Lite duel board. The installed native scenario uses an additional side.

| Wall contrast | Hamlets mean [95% interval], pp | Silverhead mean [95% interval], pp |
| --- | ---: | ---: |
| Base − shared BC | +1.48 [−19.26, +21.48] | +7.41 [−4.07, +19.81] |
| A − base | +1.11 [−20.74, +24.44] | +0.19 [−10.93, +11.67] |
| A − shared BC | +2.59 [−19.26, +21.85] | +7.59 [−5.74, +20.93] |
| B − base | −6.67 [−24.44, +13.70] | +0.93 [−9.44, +10.74] |
| B − B BC | −6.30 [−22.96, +9.63] | 0.00 [−12.41, +12.41] |
| C − base | +0.74 [−12.59, +16.30] | +2.78 [−10.74, +16.11] |
| C − C BC | −6.67 [−24.07, +8.89] | +2.96 [−11.11, +17.22] |

The validation rule required positive lower bounds versus both base and own BC. The frozen `deployment.json` was written before the first holdout game and records no nominee. The conditional native panel therefore did not run. The Lite decision timing covers observation and candidate construction through learner policy choice. The original MC output covers the first and last logged behavior batches and their own complete returns. The route reports retain per-seed, 10k, 30k, production-selected, integration and cost details. [A3 evidence](https://github.com/t66sun/wesnothLearning/pull/300), [B3 evidence](https://github.com/t66sun/wesnothLearning/pull/301), [C3 evidence](https://github.com/t66sun/wesnothLearning/pull/302)

## Independent recorded-output audit

[audit.json](audit.json) records the successful read-only reconciliation of the six panel plans and all physical game results, including paired scores, frozen bootstrap contrasts and raw timing p95s. It also joins every settled PPO game to its schedule and update, checks the fresh counts, threshold boundaries, policy chain and cutoffs, and verifies the BC gates and shared input identities. The run did not include an injected training interruption. The accepted mechanism reports cover interruption and recovery with their original scope.

The Ubuntu archive `/home/tongshu/acceptance/ppo269_audit_20261108_7i3hTI/raw-metadata.tar.gz` contains 3,474 original metadata files, totaling 14,675,274 compressed bytes. It includes the preflight and launch records, panel plans and results, all PPO and BC job logs and schedules, gate and checkpoint identity records, the frozen holdout map, and the historical base BC records under `external/base-bc`. Model weights, game replays and training shards remain in the run roots identified by the archived records. The archive SHA-256 is `50786c42c28d86b7cbecf4c56ee87eb0418451feecb57546546cd4e141b3daf0`. The audit output SHA-256 is `46f250e8f283152a1634f6648a3e19ed283b4e1629cda09e2de7ce0f0d5ab7a2`.

The audit ran on Ubuntu from the Git archive of `be0d6f177b454b59aa701337ca64c6db319a0273` at `/home/tongshu/acceptance/ppo269_audit_20261108_IKnPOJ`. From a fresh extraction of the audit source on Ubuntu, the same command reads the recorded archive and the original driver's statistics code and writes a new output file.

```sh
formal=/home/tongshu/acceptance/ppo269_shared_20261107_gzzXd6
extension=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONPATH="$formal/driver/source:$extension"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mkdir recorded
tar -xzf /home/tongshu/acceptance/ppo269_audit_20261108_7i3hTI/raw-metadata.tar.gz -C recorded
/home/tongshu/venv/bin/python verification/ppo_roadmap_acceptance_20261108/audit_recorded.py \
  recorded audit.json
```
