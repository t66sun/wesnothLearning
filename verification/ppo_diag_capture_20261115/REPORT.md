# Exact-checkpoint Lite duel PPO capture and credit diagnostics

Ubuntu completed all 96 games on the frozen launch in **374.172 seconds** with zero faults and zero optimizer updates. Recount joined 96 scheduled IDs, replies and file-hashed learner trajectories containing **22,334 eligible decisions**. There were 72 natural finishes and 24 official round-30 draws. The sampler played 24 games per role across The Freelands, Weldyn Channel and the archived Fallenstar Lake. The capture, audit, and candidate proposal belong to [#352](https://github.com/t66sun/wesnothLearning/issues/352).

| Phase | Actual seconds | Limit seconds |
| --- | ---: | ---: |
| Launch parity | 0.655 | 300 |
| Collection | 364.134 | 1,200 |
| Audit and archive | 9.367 | 300 |
| Continuous run | 374.172 | 1,800 |

## Exact policy replay and calibration

The review verified every frozen checkpoint and export, every archived member and trajectory hash, and the runtime schedule's sole deadline binding. It replayed eight chronological decisions from each trajectory. The maximum absolute log-probability error over **768** decisions was **1.04e−6** for rollout FP64 and **6.15e−6** for trainer FP32. Maximum value errors were **6.87e−8** and **2.81e−7**. All rows entered unique training windows in their reconstructed eight-game diagnostic batches. The independent Python/Lua prefix check used eight contiguous decisions per role with 37-candidate and multi-turn coverage. Its largest numerical error was **8.53e−14**. All six selected finite-return, same-turn clock and external-cut arithmetic fixtures passed. [Replay and calibration output](review.json) · [Lua parity](lua-parity.json) · [Boundary fixtures](fixtures.log)

| Capturing policy | Decisions | Equal-game bias [95% interval] | Row MSE | Explained variance | Equal-game MSE gap vs LOO outcome constant [95% interval] |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qualified v38 | 5,559 | +0.314 [+0.099, +0.522] | 0.709 | −0.002 | −0.054 [−0.403, +0.262] |
| PPO 202611081 | 5,253 | +0.332 [+0.134, +0.516] | 0.642 | 0.197 | −0.152 [−0.488, +0.153] |
| PPO 202611082 | 5,630 | −0.001 [−0.153, +0.146] | 0.366 | 0.463 | −0.417 [−0.652, −0.209] |
| PPO 202611083 | 5,892 | +0.395 [+0.211, +0.555] | 0.670 | 0.107 | −0.033 [−0.380, +0.263] |

The target is the realized official terminal reward minus the current economy/control potential. Positive bias means overprediction. The constant estimates the mean outcome of the other games of that role. Intervals use 10,000 game resamples within fixed boards. The JSON contains strata by board, turn and outcome. The exact #306 critics vary. Two show positive bias, and the third beats the leave-one-game-out constant on this capture. That makes a common failing critic or a uniform critic-repair prescription unsupported by this diagnostic. All observed trajectories reached the scoring terminal. External interruptions are covered by the separate fixture results.

## Other root-cause routes

- **#355 credit.** PPO normalized GAE/complete-return signs agreed on 87.3–96.6% of equal-game rows by policy and map. The actor-gradient cosine to the complete-return reference across the 18 roster subfolds disjoint within each policy ranged from 0.578 to 0.996. The reference shares the realized continuation and is an observational measure. An action-specific causal effect still needs paired branches.
- **#356 and #357 delivery and loss interference.** At the exact PPO endpoint weights the full-gradient actor/critic cosine ranged from −0.060 to +0.085. The first convolution swung between approximately −1 and +1 across folds. The evidence supports measuring which updates the optimizer actually delivers. It does not single out a uniformly opposing loss component.
- **#358 clock and reduction.** Finite returns and potential-coordinate invariance held across the 12 batches. On matched, no-update gradient probes, equal-turn weighting changed mean alignment with the complete-return actor direction by −0.0265, −0.0147 and −0.0331 in the three PPO histories. Two-fold comparisons use the same visible inputs and advantages. This tested alternative did not earn a score pilot.
- **#359 and #361 mode and transfer.** The sampled v38 score was 34.72%. The three sampled PPO policies averaged 31.48%, a paired −3.24 pp [−16.67, +9.72] over the 24 matched slots. This is a capture diagnostic with three fixed layouts. Same-seed greedy and second-opponent comparisons remain separate experiments.
- **#360 supported actions.** The frozen PPO policies changed the greedy retained action relative to v38 on 41, 50 and 39 of 192 identical visible-state probes. The replay showed differences in choices. Paired continuations are needed to measure the direction and magnitude of those changes.

## Frozen #356 optimizer probe for approval

The replay probe uses one eight-game The Freelands batch from each exact role. All **6,521** policy targets are from the production train partition. A no-update Ubuntu preflight passed the real PPO read/admission and window planner for all four batches. The other 16 games per role supply held-back scores and actor movement readouts. The 1,024 rehearsal rows come from two retained #322 behavior batches, shared by every probe arm. This is an explicitly recorded replacement source for the absent #306 rehearsal pool.

Four stock arms use 1e−4 Adam. v38 starts with empty moments, as in the original PPO transition. Each PPO arm loads its own archived optimizer state. The four paired half-rate arms at 5e−5 are conditional on stock KL stopping before two effective passes in v38 and at least two PPO roles. All arms use the existing update function, same optimizer state within pair, same RNG and ordering, four epochs, minibatch 256, the same loss terms and the production KL gate of 0.02.

The budget is **zero new games, at most eight optimizer arms on copies, and 20 active minutes**. Allow 120 seconds for admission, 120 seconds per arm and 120 seconds for final audit. No existing checkpoint or optimizer state is saved over. Accept the diagnostic when the admitted inputs and both arm settings hash-match, the required arms finish within budget and the ledger reports committed/rejected work, exact held-back policy KL and the signed log-probability movement projected onto held-back Monte Carlo advantages. The alternative earns consideration for a later score experiment only when at least two PPO copies commit more visits and improve that projection with at most +0.005 additional held-back KL. That is a feasibility screen for the single prespecified change. [Probe manifest](optimizer-probe.json) · [Input preflight](optimizer-preflight.log) · [Production admission](optimizer-admission.log)

## Evidence and commands

- Capture launch SHA-256 `b0e68cff203e2d2b315a9aa4aaf782fb2587d9dc1acc1b28224b8756a2a67699`. [Original freeze](../ppo_diagnosis_20261115/capture-launch.json)
- The 361,546-byte capture metadata archive has SHA-256 `8a21da31be20c4c087aa78d35baa51c06049420a393f63fa18c55cfa72163e3a`. Its ledger binds the raw shards retained at `/home/tongshu/acceptance/ppo-diagnosis-20261115-Z8O0k3/capture/trajectory`. [Original schedule, replies, timing and trajectory ledger](capture-metadata.tar.gz) · [Run start](capture-start.json) · [Run exit](capture-exit.json)
- Review Git archive commit `455ae6ecb46e56fa31f5e67d66d8b0167cabe0b2`, tar SHA-256 `813b1b827ad8f1551f9d39d10605ab96dd9658862cbb3f114179b8e822f4a111`, and generated result SHA-256 `d498d0b0c90d150446f1c977adb916e5ff8ca526cea5365e1f225e5c4fc60df3`. [Review implementation](review.py)
- Next probe launch SHA-256 `36b2cdbb84b1df705d677a2a1dbeca343d7f92b39b7f5ea837454d0939bffad2`. Git archive commit `fa798589cb8bdeb80ffe18d27f0fe6d324bb85bc`, tar SHA-256 `26fbafc5184612dd9e7218abd02df44505fbaccfc4565699f0e358cc324cc5e7`. [Probe implementation](optimizer_probe.py)

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
cd "$s306"
export PYTHONPATH="$PWD:$extension306"
capture=/home/tongshu/acceptance/ppo-diagnosis-20261115-Z8O0k3/capture
review=/home/tongshu/acceptance/ppo-capture-review-20261115-dGKSp2
probe=/home/tongshu/acceptance/ppo-capture-review-20261115-QJUU4Z
PYTHONPATH="$PYTHONPATH:$review/verification/ppo_diagnosis_20261115" \
    "$python" -u "$review/verification/ppo_diag_capture_20261115/review.py" "$capture"
# Run the following command only after separate authorization for the probe SHA-256.
PYTHONPATH="$PYTHONPATH:$probe/verification/ppo_diagnosis_20261115" \
    timeout --signal=TERM --kill-after=5s 1195 "$python" -u "$probe/verification/ppo_diag_capture_20261115/optimizer_probe.py" \
    run "$probe/optimizer-probe.json" 36b2cdbb84b1df705d677a2a1dbeca343d7f92b39b7f5ea837454d0939bffad2 \
    "$probe/probe-result.json"
```
