# Frozen PPO layout and opponent transfer

Ubuntu cpuServer, 2026-11-15. [#361](https://github.com/t66sun/wesnothLearning/issues/361) · [#352](https://github.com/t66sun/wesnothLearning/issues/352)

## Result

Against Astra, PPO gained +16.67 pp on the two seen layouts and lost 3.70 pp on the prior holdouts. Against greedy v38, it gained +3.70 pp on the seen layouts and +13.89 pp on the prior holdouts. The seen-to-holdout change was −20.37 pp against Astra and +10.19 pp against v38. All three histories gave each opponent's respective direction. Both transfer intervals cross zero. The difference between transfer contrasts was +30.56 pp [−8.33, +72.22]. The opponent interaction averaged +2.31 pp [−17.59, +22.69] across the four maps.

Fallenstar Lake against greedy v38 supplied a local positive result of +29.63 pp [+3.70, +55.56], with positive effects in all three histories. Sulla’s Ruins against the same opponent gave −1.85 pp [−22.22, +20.37]. The crossover is suggestive and the matrix remains inconclusive on a general transfer loss or fixed-Astra specialization. No training intervention is nominated from these four layouts.

All 120 new duels completed and a separate raw archive recount verified the full 192-game matrix with 72 exact #359 replies. There were zero faults and zero optimizer updates. Collection took 593.624 seconds and the full runner took 595.485 seconds inside the 30-minute allowance.

The contrast is the three PPO checkpoints minus the shared v38 learner, in percentage points of the official 3/1/0 score. Each map and opponent contributes three paired roster blocks. The 10,000 crossed bootstrap draws resample histories and within-map roster blocks, preserving the two seats and all opponent and role cells together. Maps have equal weights within each stratum.

| Board or stratum | Against Astra, pp [95% interval] | Against greedy v38, pp [95% interval] | v38 minus Astra, pp [95% interval] |
| --- | ---: | ---: | ---: |
| The Freelands | +12.96 [−22.22, +44.44] | −3.70 [−42.59, +27.78] | −16.67 [−53.70, +31.48] |
| Weldyn Channel | +20.37 [−18.52, +66.67] | +11.11 [+0.00, +33.33] | −9.26 [−57.41, +27.78] |
| Fallenstar Lake | +1.85 [−20.37, +27.78] | +29.63 [+3.70, +55.56] | +27.78 [−16.67, +66.67] |
| Sulla’s Ruins | −9.26 [−40.74, +25.93] | −1.85 [−22.22, +20.37] | +7.41 [−35.19, +44.44] |
| Seen mean | +16.67 [−11.11, +46.30] | +3.70 [−12.04, +16.67] | −12.96 [−41.67, +13.89] |
| Prior-holdout mean | −3.70 [−24.07, +19.44] | +13.89 [−2.78, +30.56] | +17.59 [−12.96, +45.37] |

| Interaction | Pooled effect, pp [95% interval] | Per-history effects, pp |
| --- | ---: | ---: |
| Prior holdout minus seen against Astra | −20.37 [−59.26, +13.89] | −36.11 / −16.67 / −8.33 |
| Prior holdout minus seen against v38 | +10.19 [−11.11, +30.56] | +5.56 / +8.33 / +16.67 |
| v38 minus Astra across four maps | +2.31 [−17.59, +22.69] | +6.94 / +4.17 / −4.17 |
| Transfer versus v38 minus transfer versus Astra | +30.56 [−8.33, +72.22] | +41.67 / +25.00 / +25.00 |

The per-history order is 202611081, 202611082, 202611083. Machine-readable per-map and per-opponent history estimates are in the [recount](result.json).

## Physical exposure and overlap

The #306 settled `λ=0.95` histories joined 4,368 scheduled games to their official results and eligible decision counts. All opponent packages matched frozen Astra SHA-256 `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`. Learner seat totals were 2,184 per seat. The materialized census records each physical hash, ordered matchup, learner seat and training history.

| #306 rollout layout | Origin | Games by history | Total | Distinct ordered rosters per history |
| --- | --- | ---: | ---: | ---: |
| Arena2 | Synthetic Lite fixture | 732 / 728 / 724 | 2,184 | 20 |
| The Freelands | Native 1.18.8 export | 244 / 243 / 242 | 729 | 23 |
| Weldyn Channel | Native 1.18.8 export | 244 / 243 / 242 | 729 | 26 |
| Sablestone Delta | Native 1.18.8 export | 244 / 242 / 240 | 726 | 23 |

Current production duel validation and archived periodic #306 validation resolve to the same Hamlets physical hash, with zero overlap with the four settled rollout layouts. The audited #227, #272, #306 and #349 score plans likewise have zero physical rollout overlap. The #355 sampled and #359 mode panels both overlap exactly on The Freelands and Weldyn Channel.

| Selected layout | Stratum | Physical SHA-256 | Derived terrain | Archive reuse |
| --- | --- | --- | --- | ---: |
| The Freelands | Seen | `f4a0aa04cfad87b05bcbdb72dc6e469a547454178e6a34e335e45a8eb3fbb810` | Native export | 24 |
| Weldyn Channel | Seen | `e14d55816d6b3241036cdb9d9685f37195522c585adf542c04e0137240a771fa` | Native export | 24 |
| Fallenstar Lake | Prior holdout | `2f9037f75f58c917343aa4cbc82ba48d27d7a8120b1244893012773da307180d` | Two mountain-village substitutions | 24 |
| Sulla’s Ruins | Prior holdout | `47e311d38e3630d29cff7e8f05e75d1e23720819083c3c1ca7fe6d98529cd958` | Two mountain-village substitutions | 0 |

The two prior multiplayer holdouts are physically absent from the #306 rollout hashes and the broader #349 lineage exposure. Both use the recorded `Mm^Vhh` to `Hh^Vhh` tile substitutions in the pinned Lite boards. The three reserved confirmation board hashes remain disjoint. The seen mean measures two native layouts. Arena2 accounted for half the original rollout volume and sits outside this panel.

## Frozen crossed panel

The same four frozen weights and stock greedy choices run on both sides of the opponent contrast. Blocks 0, 12 and 24 cover the six initial factions exactly once as ordered pairs and use both learner seats. The evaluator scores one designated learner seat in every cell. In the v38 mirror the fixed opponent alias has the same model and addon bytes as the learner export. Distinct paths provide separate side-specific policy instances. Both policies receive public decisions through the unchanged Lite worker.

The 72 reused Astra replies are the exact greedy subset of #359 for the same maps, roles, physical hashes, ordered factions, seeds, seats and full learner candidate path. The frozen schedule keeps their jobs and replies unchanged. The 24 Sulla Astra games use fresh combat seeds 2026111900–2026111902 and the same full learner path. The compact #349 scorer used a different learner execution path. The 96 v38 games retain the same paired scenarios as Astra, use the same full learner selector and substitute only the opponent.

## Raw score matrix

Each entry gives wins/draws/losses (turn caps, points out of 18).

| Board | Opponent | v38 learner | PPO 202611081 | PPO 202611082 | PPO 202611083 |
| --- | --- | ---: | ---: | ---: | ---: |
| The Freelands | Astra | 2/1/3 (1, 7/18) | 3/0/3 (0, 9/18) | 3/1/2 (1, 10/18) | 3/0/3 (0, 9/18) |
| The Freelands | Greedy v38 | 3/0/3 (0, 9/18) | 4/0/2 (0, 12/18) | 3/1/2 (1, 10/18) | 1/0/5 (0, 3/18) |
| Weldyn Channel | Astra | 2/0/4 (0, 6/18) | 4/0/2 (0, 12/18) | 2/1/3 (1, 7/18) | 3/1/2 (1, 10/18) |
| Weldyn Channel | Greedy v38 | 3/0/3 (0, 9/18) | 3/0/3 (0, 9/18) | 3/0/3 (0, 9/18) | 5/0/1 (0, 15/18) |
| Fallenstar Lake | Astra | 2/1/3 (1, 7/18) | 1/4/1 (4, 7/18) | 1/4/1 (4, 7/18) | 2/2/2 (2, 8/18) |
| Fallenstar Lake | Greedy v38 | 0/6/0 (6, 6/18) | 3/2/1 (2, 11/18) | 3/3/0 (3, 12/18) | 3/2/1 (2, 11/18) |
| Sulla’s Ruins | Astra | 3/2/1 (2, 11/18) | 1/3/2 (3, 6/18) | 2/3/1 (3, 9/18) | 4/1/1 (1, 13/18) |
| Sulla’s Ruins | Greedy v38 | 1/4/1 (4, 7/18) | 2/1/3 (1, 7/18) | 1/2/3 (2, 5/18) | 2/2/2 (2, 8/18) |

## Evidence and reproduction

- Approved launch digest `e54e4009326b583e872705c27b3b18db7ef579a7d0e05f1abb017fb74810ef76`. [Manifest](launch.json) · [Ubuntu no-game preflight](preflight.json)
- Raw archive SHA-256 `0d85e5f89110b1229fa7a9ba327e97788fc1dd837a545baab8f52cd4403a057b`. It contains the physical census, exact frozen and active schedules, 120 new replies, 72 archived Astra replies, launcher status and repeated raw recount. [Raw evidence](raw-transfer-metadata.tar.gz)
- Result SHA-256 `d74ee40b9ec29e3f61f0e480e6e005daa277a5c2dfe65980c56b2f6b780cf456` and recount SHA-256 `258440e885b74f24066c69637a0d29f4be848d73aa083bf6c5ed00e492070fa3`. The recount verified all 32 six-game cells and matched every score, interval and history effect printed by the runner. [Result](result.json)
- Adapter archive commit `4aba1911e74b5a7dc826be7aa6c3f7e0e6508e08` and tar SHA-256 `468147d99116d6bd86a5ed01b24dfd130a7a721870f0062ea9607d32c807ea03`. [Adapter used on Ubuntu](transfer.py)

```bash
set -eu
b=/home/tongshu/acceptance
s=$b/ppo306_20261108_Miwoyq/source
c=$b/ppo-diagnosis-20261115-Z8O0k3/capture
m=$b/ppo-mode-interaction-20261115-sgUXX6/freeze
h=$b/ppo-v38-20261115-8dIsba/formal
p=/home/tongshu/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export WESNOTH_RULES_DIR=$b/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONPATH=$s:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
cd "$s"
a=/home/tongshu/acceptance/ppo-transfer-361-20261115-MjHy2d
d=$a/freeze
script=$a/verification/ppo_transfer_20261115/transfer.py
export PYTHONPATH=$PYTHONPATH:$a/verification/ppo_diagnosis_20261115
"$p" -u "$script" recount "$d" e54e4009326b583e872705c27b3b18db7ef579a7d0e05f1abb017fb74810ef76
```
