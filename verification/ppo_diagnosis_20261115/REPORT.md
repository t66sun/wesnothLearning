# Duel PPO root-cause archive audit and shared capture freeze

#353 recounted 3,462 frozen replies across #227, #272, #306 and #349 and audited the three selected #306 histories. All four #349 checkpoint and weight identities matched. The audit, trajectory replays and preparation started zero new games and zero optimizer updates. [Roadmap](https://github.com/t66sun/wesnothLearning/issues/352)

## Archived learning curves

| Cohort and exact contrast | Physical board | Matched slots | Difference, pp | Paired 95% interval, pp |
| --- | --- | ---: | ---: | ---: |
| #272 eight-game 10k − v38 | Hamlets subset | 12 | −1.85 | [−25.00, +16.67] |
| #272 eight-game 30k − v38 | Hamlets | 30 | +6.67 | [−15.56, +27.78] |
| #272 eight-game wall − 30k | Hamlets | 30 | −4.07 | [−24.44, +15.56] |
| #272 eight-game wall − selected | Hamlets | 30 | −7.78 | [−28.89, +13.33] |
| #306 v200 − v100 | Hamlets promotion panel | 72 | +3.24 | [−12.04, +19.44] |

The #272 contrasts use the intersection of exact physical layout, ordered factions, combat seed, learner seat, official task and Astra file digest. The six-block slice at 10k and the full 15-block set are distinct estimates. The #306 v100/v200 comparison has 12 two-seat blocks per history and 144 raw replies. Its seeds differ between histories, so the interval resamples matched scenario blocks within each independently sampled history. Effects were +6.94, +11.11 and −8.33 pp. The v100 tensors survive as the three best PPO checkpoints. The v200 identity comes from the recorded PPO batch digest and matching version-tagged evaluation jobs. The v200 tensor exports are absent from their original paths.

These results leave a transient gain or a selection/transfer effect open. Evidence of a common late collapse is weak. Hamlets was a selection layout and is shared across the historical comparisons. The final #306 physical holdouts and the later #349 holdouts have no overlap. #306 settled effects were −3.52 pp on The Road to Weldyn and +7.78 pp on A Summer of Storms. The same three endpoints averaged +0.25 pp on #349. The archive has no matched 10k-to-wall #306 holdout curve, so #272 remains a separate recipe-specific trace. [Archive inventory and physical overlap](inventory.json.gz) · [v100/v200 recount](promotion.json) · [#349 formal result](../ppo_vs_bc_acceptance_20261115/REPORT.md)

## Available diagnostics

| Route | Read-only result | Remaining discriminator |
| --- | --- | --- |
| #354 replay | Six exact #322 pure-Astra behavior batches, 48 games, 5,581 terminal learner rows and 768 recomputed probabilities. Maximum absolute log probability difference 7.42e−6, value difference 2.44e−7. Candidate-order and recurrent-prefix perturbations were detected. Every stored eligible target mapped into exactly one window. | Repeat for the exact #306 wall tensors on shared capture rows. The old #306 live paths retain zero of 4,368 policy shards and zero of 546 behavior exports. |
| #355 critic and credit | The 24 exact v38 games had mean game-level overprediction +0.431 in reward units. The 24 #322 late behavior games had +0.345. MSE was 0.639 and 0.667, respectively. The game-weighted MSE difference versus a leave-one-game-out outcome constant had a 95% interval spanning zero in both samples. | Calibration on sampled games from the three exact #306 wall policies. The #322 late versions were v119, v117 and v119. |
| #356 optimizer delivery | 545 of 546 #306 batches stopped on the production KL check. The three histories recorded 443,824 fresh targets, 696,905 committed visits and 96,756 inspected rejected visits out of 793,661 inspected. 3,711 of 9,720 planned steps committed. | Identify useful-target loss using measured policy movement. The ledger cannot identify unrealized policy counterfactuals. |
| #357 loss components | In one held-fixed micro-window per #322 late behavior policy, the critic/actor cosine in the first shared convolution was −0.991, −0.998 and +0.996. Weighted critic norm exceeded actor norm there in all three probes. | Replicate across windows and test whether the effect reaches action margins. The probes used recorded first-batch policy rows as a fixed rehearsal control and computed gradients without Adam steps. |
| #358 reward clock | Complete Monte Carlo returns telescope to the finite-task target. Changing only potential coordinates preserved GAE to maximum error 1.78e−15. Normalized GAE and Monte Carlo advantage signs agreed on 89.1–97.6% of rows across the sampled batches. For late policies, turns with 12 or more choices accounted for 8.3–21.2% of the equal-window absolute advantage mass and 6.1–22.1% under equal-turn weighting. | Measure whether any shift reliably moves credit toward useful actions. The mass statistic measures normalized advantages and window weights. |
| #359 sampled vs greedy | On the same 384 late #322 public-row probes, matching the sampled action to that policy's own greedy action occurred 299 times. Mean entropy rose in all three late policies relative to v38 evaluated on the same rows. | Matched official-score mode interaction for exact wall policies. |
| #360 action headroom | The late #322 policies and v38 disagreed on the greedy retained action in 72 of those 384 same-state probes. | A legal, fixed one-action branch and matched continuation to identify value. Branch outcomes and omitted-action value are unmeasured. |
| #361 transfer | All 4,368 matched-set #306 rollout replies faced the same Astra package. Arena2 supplied 2,184 games. The three other maps supplied 729, 729 and 726. All four maps cover 20–26 ordered rosters per history. | Compare the same frozen policies on seen and prior holdout boards and a second supported opponent. The historical #322 training mixture changed what the policy learned and does not identify the evaluation-opponent interaction. |

Matched pre/post weights from the last actual #322 batch changed the greedy action in 7, 8 and 4 of 128 sampled rows per history. Mean full-distribution forward KL was 0.01210, 0.02943 and 0.00906. The applied probability move agreed with normalized advantage sign on 62.6%, 60.2% and 50.0% of materially moving rows. This is a full-batch shift across distinct histories and targets. The production threshold applies to its pre-step sampled-action statistic on an individual logical batch.

No repair is nominated. The main positive leads are repeated early stopping in #306 and a possible actor/critic conflict in shared features. Exact-checkpoint credit, reproducible action effects and paired scores determine whether either justifies a causal test. [Archived trajectory replay and weighted gradients](replay.json)

## Frozen shared capture for review

The missing data is complete terminal learner trajectories from the three exact #306 wall checkpoints, with contemporaneous v38 as the comparator. Capture the four roles in sampled mode against the frozen #306 Astra under official-score-30-v1. Use The Freelands, Weldyn Channel and the archived Fallenstar Lake layout. Select ordered roster blocks 0, 8, 16 and 24 on each board. Both seats and all roles share the combat seed within block. Seeds 2026111740 through 2026111751 cleared the #306 and #349 schedules. The shipped Lite learner samples using combat seed plus learner seat times 100003. The schedule records the actual sampler seed.

The archive establishes 96 scheduled games, 24 per role, on 24 paired slots, eight workers, and a continuous 30-minute cap. Allow 5 minutes for launch checks, 20 minutes to collect and 5 minutes for audit. There are zero optimizer updates. One shared cohort supports #354, #355 and #358 and provides inputs for the follow-on diagnostics. The capture ends before any greedy mode contrast, counterfactual continuation, opponent trial or optimizer intervention.

Acceptance requires all 96 unique replies to match their frozen job, model, layout, opponent, seed and learner seat, finish at the official terminal, and retain a nonempty fault-free learner shard with the correct reward and policy version. A cutoff, missing reply, invalid row or budget miss yields incomplete evidence. Replay 768 stratified sampled rows with their exact public prefixes and log probability/selected value absolute error within 1e−5 before using the data for calibration. Rebuild return and advantage diagnostics with game-clustered uncertainty. This is diagnostic acceptance. The roadmap's score gates apply only to a separately frozen causal experiment.

| Artifact | SHA-256 |
| --- | --- |
| [Capture launch](capture-launch.json) | b0e68cff203e2d2b315a9aa4aaf782fb2587d9dc1acc1b28224b8756a2a67699 |
| [Capture schedule](capture-schedule.json.gz), decompressed | 01cefdc3f431ba576e2788371a69bf344e115a044238327048b9929aad0436c8 |
| [Confirmation layout reserve](confirmation-reserve.json) | 57043fb6c9de3a68d14d36c5ce315927cab5741a31de2e319a0faf06d6e1dbb4 |
| Archive inventory, decompressed | edd587bd483f8ed1c0703b813283fac115da62e0d1f97b0eaf7eb96e0ae99bdf |
| #306 source archive | 240009bf8a55096203d548d4ee349c2e34d574927ff2325c30ef08ef4aef69d2 |
| Lite extension | 56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4 |
| Rules | e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17 |
| Astra package | 2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933 |

A static screen examined 327 official map assets. The only eligible additional unmodified layout returned was the native source of Silverhead Crossing, previously used in #272. The reserved alternatives are three seeded, symmetric synthetic Lite maps, each with two playable keeps, 20 villages and supported terrain. Their physical digests are disjoint from the audited training and evaluation boards and the capture layouts. This choice confines any later confirmation using the reserve to those Lite layouts. No score was used to select them. [Frozen prepare output](freeze.log) · [Ubuntu no-game preflight](preflight.log)

## Reproduction

The archive, promotion recount and replay executed from Git archives on cpuServer, using the stock pinned #306 evaluator or the pinned #322 source for exact behavior replay. Paths and commands are recorded below. For the frozen capture, the run command applies only after the owner authorizes the exact launch digest.

```bash
set -eu -o pipefail
base=/home/tongshu/acceptance
s306="$base/ppo306_20261108_Miwoyq/source"
s322="$base/ppo322-formal-20261114-wGKDQ4/source"
extension306=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
extension322="$base/immutable_forecast_20261104/green/.extension"
rules="$base/filters_compiled_20261103/data/rules/1.18.8-combat-filtered"
python=/home/tongshu/venv/bin/python
export WESNOTH_RULES_DIR="$rules" PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
root=/home/tongshu/acceptance/ppo-diagnosis-20261115-Z8O0k3
cd "$s306"
export PYTHONPATH="$PWD:$extension306"
timeout --signal=TERM --kill-after=5s 1795 "$python" -u "$root/verification/ppo_diagnosis_20261115/capture.py" run "$root/capture" b0e68cff203e2d2b315a9aa4aaf782fb2587d9dc1acc1b28224b8756a2a67699
```

For the offline recounts, run the archived scripts with the appropriate source and extension as above. Use the #306 source for audit_archive.py and promotion.py, and the #322 source for replay.py.
```text
archive audit  /home/tongshu/acceptance/ppo-diagnosis-20261115-x3PwAA/inventory.json  commit 4368b6e10e4c893495d82488daaded15975ed92e  tar 8a092cdbb2c7a8fd2228ec5ad3fcd4fea0baef3b5af78c4bc09edfd797a15e78
promotion      /home/tongshu/acceptance/ppo-diagnosis-20261115-Uenmko/promotion.json  commit af3492d5f938d7007a58ef495a896660bad84a23  tar 8461d31508ae960fb81d7c1df51597c03b5568c334a7a64ec6b37dff343cc1ed
behavior       /home/tongshu/acceptance/ppo-diagnosis-20261115-964dU9/replay.json  commit f962a8baef0b8a5e6592f9fdf3da66235b9ac733  tar 0582351153163627a18b417f091683266fbfd65581a94ce4cccbd603583b876c
capture freeze /home/tongshu/acceptance/ppo-diagnosis-20261115-Z8O0k3/capture/capture-launch.json  commit a813075161bb8138e56a82bec8e578890dfc95bf  tar 8a84f38a3b2679ac0b97e0b6d79bb63e5c3df6149fb3585488fd6b77aa3be745
```
