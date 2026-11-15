# Official PPO sampled versus greedy result

Ubuntu cpuServer, 2026-11-15. [#359](https://github.com/t66sun/wesnothLearning/issues/359) · [Frozen protocol](../ppo_mode_interaction_20261115/REPORT.md)

## Result

**The primary interaction was −14.20 pp**, with paired 95% interval [−27.47, +0.93] pp. The 95% upper bound fell below the prespecified +5 pp effect. This matrix excluded a PPO-specific sampling advantage of that size. PPO minus v38 was −2.16 pp [−12.96, +8.64] in sampled mode and +12.04 pp [−0.93, +24.69] in greedy mode. The observed data did not earn a training-time exploration or calibration contrast.

All three history-level interactions were negative. Weldyn Channel supplied the strongest negative contrast at −35.19 pp, while The Freelands had a positive point estimate of +9.26 pp. This diagnostic uses three layouts and six roster blocks per map. The separate, larger #349 greedy result was +0.25 pp on its own schedule.

Each checkpoint and selector scored 36 official games. The mode contrast is sampled minus greedy. Its units are percentage points of the maximum official 3/1/0 score.

| Checkpoint | Sampled score | Greedy score | Mode contrast [95% interval], pp |
| --- | ---: | ---: | ---: |
| v38 BC | 32.41% | 33.33% | −0.93 [−9.26, +7.41] |
| 202611081 | 26.85% | 46.30% | −19.44 [−34.26, −5.56] |
| 202611082 | 33.33% | 41.67% | −8.33 [−23.15, +7.41] |
| 202611083 | 30.56% | 48.15% | −17.59 [−29.63, −5.56] |

The primary interaction subtracts the v38 mode effect from the PPO mode effect, reusing the same v38 replies across histories. The panel contains six nonmirror roster blocks per map and both learner seats per block. The crossed percentile interval uses 10,000 draws of fixed-map roster blocks and paired PPO histories.

| PPO history | Sampled PPO−BC, pp | Greedy PPO−BC, pp | Interaction, pp |
| --- | ---: | ---: | ---: |
| 202611081 | −5.56 | +12.96 | −18.52 |
| 202611082 | +0.93 | +8.33 | −7.41 |
| 202611083 | −1.85 | +14.81 | −16.67 |

| Physical layout | Sampled PPO−BC, pp | Greedy PPO−BC, pp | Interaction [95% interval], pp |
| --- | ---: | ---: | ---: |
| The Freelands | +11.11 | +1.85 | +9.26 [−16.67, +36.11] |
| Weldyn Channel | −9.26 | +25.93 | −35.19 [−59.26, −5.56] |
| Fallenstar Lake | −8.33 | +8.33 | −16.67 [−34.26, +3.70] |

## Official tallies

Each table entry gives wins/draws/losses, the number of 30-round draws and total points.

| Layout | Role | Sampled | Greedy |
| --- | --- | ---: | ---: |
| The Freelands | v38 BC | 3/2/7 (2 caps, 11/36) | 5/1/6 (1 cap, 16/36) |
| The Freelands | 202611081 | 4/1/7 (1 cap, 13/36) | 6/0/6 (0 caps, 18/36) |
| The Freelands | 202611082 | 5/0/7 (0 caps, 15/36) | 5/1/6 (1 cap, 16/36) |
| The Freelands | 202611083 | 5/2/5 (2 caps, 17/36) | 5/1/6 (1 cap, 16/36) |
| Weldyn Channel | v38 BC | 4/0/8 (0 caps, 12/36) | 3/1/8 (1 cap, 10/36) |
| Weldyn Channel | 202611081 | 3/0/9 (0 caps, 9/36) | 6/1/5 (1 cap, 19/36) |
| Weldyn Channel | 202611082 | 3/1/8 (1 cap, 10/36) | 5/2/5 (2 caps, 17/36) |
| Weldyn Channel | 202611083 | 2/1/9 (1 cap, 7/36) | 6/4/2 (4 caps, 22/36) |
| Fallenstar Lake | v38 BC | 1/9/2 (9 caps, 12/36) | 2/4/6 (4 caps, 10/36) |
| Fallenstar Lake | 202611081 | 1/4/7 (4 caps, 7/36) | 1/10/1 (10 caps, 13/36) |
| Fallenstar Lake | 202611082 | 2/5/5 (5 caps, 11/36) | 1/9/2 (9 caps, 12/36) |
| Fallenstar Lake | 202611083 | 1/6/5 (6 caps, 9/36) | 2/8/2 (8 caps, 14/36) |

## Evidence and scope

All 192 authorized games returned valid terminal replies, including 48 sampled and 144 greedy. The 96 reused sampled games completed the 288-cell matrix with zero faults and zero optimizer updates. The collection took 603.002 seconds across eight workers and the authorized launcher took 608.504 seconds. The independent recount took 5.363 additional seconds. It rebuilt official score from winner and learner-seat records, preserved the frozen blocks and matched every reported count and interval.

The previously archived 768 probes show sampled-to-greedy action disagreement of 34.90% for PPO and 18.23% for v38. Probe observations are from sampled trajectories. The official effect above uses the matched mode matrix, including identical weights, combat seeds, public candidate path and Astra. [Public-state distribution audit](../ppo_mode_interaction_20261115/REPORT.md)

- Frozen launch SHA-256 `d50730235e9627d15c2eb11240ba6bd40a4b0c4d678cba8fecccbc1067c4aba5`. [Manifest](../ppo_mode_interaction_20261115/mode-launch.json) · [Complete frozen schedule](../ppo_mode_interaction_20261115/mode-schedule.json.gz)
- Raw evidence archive SHA-256 `5367303ce5efd98040b476eb1b6ebf9cdc317e09bafcd0602d603f7cb27b8012`. Recount SHA-256 `2117702b7ab50b1eebd580a566381a889f332ace0b76fca535d19a98f32cf6dc`. Launcher score output SHA-256 `028681a7c7e073dc92d45fef4fe1e1fb4dc9ffb531d7f45c0d609ad5faad8fbb`. [Runtime schedule, raw replies and launcher record](raw-mode-metadata.tar.gz) · [Recount output](recount.json)
- Ubuntu review Git archive commit `4518900c389cf7ec6929dc6949686aca8145d801` and tar SHA-256 `94e49780408bab4a684f6bac0f84fa3977e0d2cc7d565050e05dc515e5b8fbb2`. [Independent recount script](recount.py)

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
review=/home/tongshu/acceptance/ppo-mode-result-20261115-mtIEDU
live=/home/tongshu/acceptance/ppo-mode-interaction-20261115-sgUXX6/freeze
export PYTHONPATH="$PYTHONPATH:$review/verification/ppo_diag_capture_20261115:$review/verification/ppo_diagnosis_20261115"
out=$(mktemp -d "$base/ppo-mode-recount-XXXXXX")
"$python" -u "$review/verification/ppo_mode_interaction_result_20261115/recount.py" "$live" "$out"
```
