# Matched online PPO learning-rate pilot

Ubuntu cpuServer, 2026-11-15. [Roadmap #352](https://github.com/t66sun/WesnothLearning/issues/352) · [Authorized freeze](https://github.com/t66sun/WesnothLearning/blob/b9e1ece2f9de95e75de2e58a4be27de5f6edd8ea/verification/ppo_optimizer_probe_20261115/REPORT.md)

## Result

The half-rate intervention missed the frozen direction gate. The roadmap stops this intervention at the pilot and does not release the formal confirmation budget. Halving Adam from 1e−4 to 5e−5 increased committed visits per fresh PPO target in both seed pairs. On the official 3/1/0 score, 2026111861 moved from 31.77% to 38.02% (+6.25 pp) and 2026111862 moved from 42.71% to 33.33% (−9.38 pp). The pooled half-minus-stock estimate was **−1.56 pp** with a crossed 95% interval of [−14.58, +11.98] pp. Half minus the shared qualified v38 BC was **−2.86 pp** [−13.02, +7.81] pp. These estimates cover two short training histories on the two frozen Lite evaluation layouts. The extra PPO visits did not translate into a consistent score gain. The underlying cause of weak PPO gains remains unresolved.

| Training seed | Half minus stock visits per target | Raw score point change | Score change | Both conditions |
| --- | ---: | ---: | ---: | --- |
| 2026111861 | +0.723 | +12 | +6.25 pp | Met |
| 2026111862 | +0.781 | -18 | −9.38 pp | Missed |

## Training and score

All four cells started with identical qualified v38 weights and empty Adam state, then settled ten eight-game PPO batches and the due six-game v40 Hamlets validation. The tracked intervention changed only the active Adam rate. GAE λ stayed at 0.95 and the production KL stop stayed at 0.02. Every included training batch committed at least one step.

| Training seed | Rate | Fresh targets | Committed visits | Visits per target | Committed/planned steps | KL stops | Wall seconds |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026111861 | Stock | 8,121 | 10,217 | 1.258 | 54/172 | 10 | 734.404 |
| 2026111861 | Half | 8,713 | 17,258 | 1.981 | 80/168 | 10 | 868.288 |
| 2026111862 | Stock | 8,524 | 11,661 | 1.368 | 60/184 | 10 | 782.302 |
| 2026111862 | Half | 8,254 | 17,740 | 2.149 | 89/172 | 10 | 897.743 |

The five greedy policies faced the same frozen Astra on 16 ordered nonmirror roster blocks with both seats on each of Fallenstar Lake and Sulla’s Ruins. A block used the same combat seed across all roles. Each cell below gives wins/draws/losses, official points, and the count of draws at the turn cap. The two layouts are equally weighted. The crossed interval resamples the scenario blocks within each map and the two training pairs with 10,000 draws. The same v38 result is reused in each matched contrast.

| Greedy policy | Fallenstar Lake | Sulla’s Ruins | Total points and normalized score |
| --- | --- | --- | ---: |
| v38 BC | 5/18/9 (33 pts, 18 turn-cap draws) | 11/8/13 (41 pts, 8 turn-cap draws) | 74/192 (38.54%) |
| stock-2026111861 | 5/15/12 (30 pts, 15 turn-cap draws) | 7/10/15 (31 pts, 10 turn-cap draws) | 61/192 (31.77%) |
| half-2026111861 | 7/14/11 (35 pts, 14 turn-cap draws) | 11/5/16 (38 pts, 5 turn-cap draws) | 73/192 (38.02%) |
| stock-2026111862 | 6/19/7 (37 pts, 19 turn-cap draws) | 14/3/15 (45 pts, 3 turn-cap draws) | 82/192 (42.71%) |
| half-2026111862 | 2/19/11 (25 pts, 19 turn-cap draws) | 11/6/15 (39 pts, 6 turn-cap draws) | 64/192 (33.33%) |

## Execution record

All **664** frozen games returned official terminal results with zero faults. The run completed 320 rollouts, 24 periodic validation games and 320 paired score games. The successful launcher took 4095.208 wall seconds. The eight-worker score panel took 810.295 seconds. The independent recount completed immediately after the run.

The initial invocation stopped at output-path validation before any game or update. The training API requires its output directory inside the pinned #306 source tree. Execution resumed in a fresh subdirectory after a digest check on the copied manifest, with a 7,185-second timeout plus five seconds of kill grace to debit the failed launch from the 120-minute active budget. All four rollout templates and 320 score-job identities still matched the freeze.

The read-only review reconstructed schedule/reply identities, official terminal scores, batch targets and visit counts, and compared final checkpoint, greedy export and optimizer identities. The review package includes both launcher attempts, the frozen schedule, raw panel replies, batch and validation replies, and optimizer ledgers. The read-only review reran no games and performed no optimizer updates.

- Ubuntu pinned source, rules, native extension and Astra identities are recorded in the frozen manifest. Manifest SHA-256 `7f3c9274f4642b0be6dd6b94ab14e08af424dc379401ef4cee010d1ab911cbaa`. Adapter Git archive commit `d9234be1c3bb1a51f729eb6d547678e59eecfe31` and tar SHA-256 `046e43916c408f59d96c3e4e38ecbf07759881f259c6456eadbfa442bbdd9990`. [Manifest](../ppo_optimizer_probe_20261115/pilot-launch.json) · [Runner](../ppo_optimizer_probe_20261115/pilot.py)
- Raw metadata archive SHA-256 `61c89b725233b06c2681a9d583404544415e47f7217fe1108ab5466149672d6e`. Independent output SHA-256 `365addba20c8771d69d4860c0b5d61f7f1d8f244bfd67e3b588a4390fd0d981a`. Launcher result SHA-256 `b2c7ef045e40414ecb529d0dbc3173e096b64abd6e65a80d583f0756f30240bd`. [Raw schedule and replies](raw-metadata.tar.gz) · [Independent recount](review.json)
- Independent review Git archive commit `3ab702e09f6c5c212ccefb5fecab4f9acc9cd0a9` and tar SHA-256 `b8ae494c91146048feeee5ff3a607162e9bd0f257ce8ba8b9348cbe6925c4f99`. [Read-only review](review.py)

```bash
set -eu -o pipefail
base=/home/tongshu/acceptance
s306="$base/ppo306_20261108_Miwoyq/source"
extension306=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
rules="$base/filters_compiled_20261103/data/rules/1.18.8-combat-filtered"
python=/home/tongshu/venv/bin/python
export WESNOTH_RULES_DIR="$rules" PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
cd "$s306"
export PYTHONPATH="$PWD:$extension306"
pilot=/home/tongshu/acceptance/ppo-optimizer-recount-20261115-7D880c
review=/home/tongshu/acceptance/ppo-pilot-review-20261115-A5Y4z4
output=/home/tongshu/acceptance/ppo306_20261108_Miwoyq/source/runs/ppo352-pilot-20261115-7cq5lA
dest=$(mktemp -d "$base/ppo-pilot-recount-XXXXXX")
export PYTHONPATH="$PYTHONPATH:$review/verification/ppo_diagnosis_20261115"
"$python" -u "$review/verification/ppo_lr_pilot_20261115/review.py" \
    "$output" "$pilot" "$dest"
```
