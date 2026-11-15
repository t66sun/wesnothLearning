# PPO optimizer delivery probe and online pilot freeze

The frozen #356 probe completed all eight optimizer copies on Ubuntu in **498.271 seconds**, with zero new games. All four stock copies hit the 0.02 production KL stop before two effective passes, so the preregistered half-rate comparison ran. Two PPO histories met the full feasibility screen. Their held-back Monte Carlo projections improved and remained below zero. The result warrants the bounded #352 live score pilot. [Frozen probe design](../ppo_diag_capture_20261115/optimizer-probe.json) · [#356](https://github.com/t66sun/wesnothLearning/issues/356)

## Measured delivery

| Initial checkpoint | Stock → half committed visits | Stock → half distinct targets | Stock → half effective passes | Stock → half held-back KL | Stock → half held-back MC projection | PPO screen |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Qualified v38 | 884 → 1,343 | 884 → 1,343 | 0.658 → 1.000 | 0.01183 → 0.00516 | +0.00443 → +0.00271 | Transition control |
| PPO 202611081 | 2,405 → 6,655 | 1,739 → 1,739 | 1.383 → 3.827 | 0.00831 → 0.00763 | −0.02238 → −0.01829 | Met |
| PPO 202611082 | 2,231 → 2,231 | 1,649 → 1,649 | 1.353 → 1.353 | 0.00688 → 0.00225 | −0.00569 → −0.00316 | Equal visits |
| PPO 202611083 | 3,167 → 4,732 | 1,790 → 1,790 | 1.769 → 2.644 | 0.01094 → 0.00757 | −0.02974 → −0.02597 | Met |

Stock abandoned 459 distinct v38 targets before their first visit. The PPO copies had already visited every distinct target at the stock rate. The half rate increased repeated eligible work for two of three PPO checkpoints. For PPO seed 202611082, the half rate reduced held-back KL and improved the MC projection at the same visit count. The v38 held-back projection fell even as coverage increased. All eight arms eventually stopped on the unchanged production KL gate.

The independent recount reconstructed each visited, KL-rejected and unattempted target window from the actual final cursor and validated the active epoch's plan hash. It reports action and turn-band counts, unique targets, the production pre-step statistic, and the exact held-back KL from the executed probe ledger. The holdback had 128 visible decision probes per copy. Its signed log-probability projection uses advantages from the already recorded complete continuations, so it measures a local update diagnostic. The study uses The Freelands for updates, two held-back layouts, and a common archived #322 rehearsal sample. The original #306 rehearsal rows are unavailable. The experiment's evidence covers this frozen replay and does not establish an official score change. [Original result](probe-result.json) · [Independent window recount](recount.json)

## Proposed online PPO pilot

Use the unchanged #306 finite-task pipeline, qualified v38, fresh Adam and the same frozen Astra. Compare **1e−4** to **5e−5** with the same 0.02 KL stop, loss recipe, 0.95 GAE and rollout/rehearsal rules. The two matched seed pairs use 2026111861 and 2026111862 with opposite arm launch order. The 10 consecutive eight-game batches per copy use the predeclared ordinal schedule and must all settle with positive updates.

| Games | Work |
| --- | --- |
| 320 | Four fresh training cells × ten complete eight-game rollouts |
| 24 | Stock due Hamlets validation at v40, six games per cell |
| 320 | Frozen greedy score panel on Fallenstar Lake and Sulla's Ruins |
| **664** | Total new games |

The two score boards use their prior archived Lite layouts. The common panel uses the final checkpoint from each of the four cells plus one unchanged v38 role. Sixteen ordered nonmirror faction pairs per map and both seats make 64 paired slots. Within each slot all five roles use the same scenario and combat seed. Official 3/1/0 scores are normalized by 3. The independent synthetic confirmation reserve stays outside training and evaluation.

**Budget.** Two active hours. Allow five minutes for launch verification, 18 minutes for each of four training cells, 35 minutes for complete paired scores, and eight minutes for audits. The Ubuntu dry run bound 160 unique rollout slots through the actual normal submission code with a mock collector. It also checked 320 paired score jobs, two playable leaders per job, and the rate wrapper on a mock optimizer. Dry-run counts were zero games and zero optimizer steps.

**Acceptance.** Require the four cells to initialize from the same v38 with empty Adam and finish the frozen 10 batches, all due validations and the fault-free official scoring panel within the budget. For **both seed pairs**, the half-rate copy must commit more eligible visits per fresh target and score strictly above its stock copy. Report seed-level, pooled paired and v38 comparisons. If one pair misses either directional condition, the pilot ends at the measured reason. The [roadmap](https://github.com/t66sun/wesnothLearning/issues/352) keeps the subsequent confirmation and its strength gates separate. The frozen online pilot awaits separate authorization for its digest.

## Evidence and reproduction

- Executed replay manifest SHA-256 `36b2cdbb84b1df705d677a2a1dbeca343d7f92b39b7f5ea837454d0939bffad2`. Its result SHA-256 is `871237bc2cd9e813dcace6c43c5b2252d8d848214c212bc45150fd1dff626fdf`. [Launch record](probe-start.utc) · [Exit code](probe-launcher.exit)
- Independent review Git archive commit `38ab473e77f74b2f9972a5a081495647a1b69e88`, tar SHA-256 `50dfe6ba33581ddb5e3a709678916c8c1d7275ab19949ebf133b02a61d320af3`. Output SHA-256 `4419ffe65dec8b7f4f6808712a3f74e7cba12bc1bca40c33d8454f4e191a52f9`. [Read-only review code](recount.py)
- Frozen next launch SHA-256 `7f3c9274f4642b0be6dd6b94ab14e08af424dc379401ef4cee010d1ab911cbaa`. Adapter archive commit `d9234be1c3bb1a51f729eb6d547678e59eecfe31`, tar SHA-256 `046e43916c408f59d96c3e4e38ecbf07759881f259c6456eadbfa442bbdd9990`. [Manifest](pilot-launch.json) · [Freeze output](pilot-preflight.log) · [No-game dry run](pilot-dry-run.log)

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
recount=/home/tongshu/acceptance/ppo-optimizer-recount-20261115-KJVuR8
pilot=/home/tongshu/acceptance/ppo-optimizer-recount-20261115-7D880c
"$python" -u "$recount/verification/ppo_optimizer_probe_20261115/recount.py" "$probe"
# Start the following only after separate approval for the frozen online pilot.
PYTHONPATH="$PYTHONPATH:$pilot/verification/ppo_diagnosis_20261115" \
    timeout --signal=TERM --kill-after=5s 7195 "$python" -u "$pilot/verification/ppo_optimizer_probe_20261115/pilot.py" \
    run "$pilot/pilot" 7f3c9274f4642b0be6dd6b94ab14e08af424dc379401ef4cee010d1ab911cbaa
```
