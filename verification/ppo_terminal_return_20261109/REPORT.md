# PPO terminal-return comparison

[#306](https://github.com/t66sun/wesnothLearning/issues/306) completed six PPO cells in three pairs and 840 holdout games. The λ=1.0 arm scored **−5.19 percentage points** against λ=0.95, with a paired 95% interval of **[−10.28, 0.00]**, and **−3.06 points** against shared BC, with an interval of **[−7.13, +0.83]**. The main point estimate was negative for all three training seeds, and its interval touched zero. The comparison leaves the gain unconfirmed and λ=0.95 remains the default. [Frozen protocol](../ppo_terminal_return_20261108/PROTOCOL.md)

## Budget and training

Preparation began on 2026-11-08 at 21:04:12 Asia/Shanghai. The driver started at 21:09:41 and its report stage finished on 2026-11-09 at 21:22:10. All nine launched stages exited 0 within their deadlines. The preparation clock includes the unsuccessful terrain preflight of the original multiplayer candidates. The final holdout used unmodified 1.18.8 campaign layouts as standard Lite duel boards.

| Phase | Actual seconds | Cap seconds |
| --- | ---: | ---: |
| Preparation through launch | 329.63 | 1,800 |
| PPO, six cells | 84,759.21 | 86,400 |
| Hamlets validation | 334.99 | 3,600 |
| Two-board holdout | 2,042.98 | 12,600 |
| Report and inter-cell accounting | 11.37 | 3,600 |
| Total from preparation | 87,478.27 | 108,000 |

The total includes 0.08 seconds between measured stages. Each cell reached its 14,100-second admission cutoff and finished before its 14,400-second hard deadline. The six wall endpoints have complete histories and no pending update or validation. All 1,097 settled batches had eight eligible task-terminal games, one sampled policy version, and the frozen arm λ. The shared prefixes for seeds 202611081, 202611082 and 202611083 matched for 1,456, 1,456 and 1,448 games respectively, including the physical scenario, combat seed, factions, learner seat and sampling seed.

| Seed | λ | Wall seconds | Settled batches | Fresh decisions | Fresh/hour | Committed visits | KL-rejected visits | Endpoint |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 202611081 | 0.95 | 14,118.68 | 183 | 146,912 | 37,460 | 229,860 | 32,699 | v221 `a00d02fc8852` |
| 202611081 | 1.0 | 14,120.76 | 182 | 147,441 | 37,589 | 234,856 | 32,511 | v220 `b287eaf0e3dd` |
| 202611082 | 0.95 | 14,127.45 | 182 | 147,193 | 37,508 | 232,774 | 32,148 | v220 `3e6e8efea9da` |
| 202611082 | 1.0 | 14,114.17 | 187 | 147,922 | 37,729 | 224,025 | 33,576 | v225 `6c33749c9563` |
| 202611083 | 0.95 | 14,138.90 | 181 | 149,719 | 38,121 | 234,271 | 31,909 | v219 `1001f2362592` |
| 202611083 | 1.0 | 14,139.26 | 182 | 146,261 | 37,240 | 234,164 | 32,417 | v220 `c362bcc99d4b` |

Every cell initialized with the same qualified BC actor and critic and an empty Adam state. The shared v38 BC checkpoint SHA-256 was `8fc61bbb0be5c2ad8d2ec5b56760ce3dbfa08eed008c490e9b2233624ea91ebe`. The actual first λ=1.0 updates checked `G_t = z − Φ(s_t)` and `A_t = G_t − V_t` on 1,052, 897 and 1,144 decisions respectively and committed 3, 2 and 5 optimizer steps. The three λ=0.95 cells also committed first-batch updates with their own frozen value. [Full endpoint identities, initialization and counters](audit.json)

## Paired scores

All seven distinct checkpoint roles played the same ordered faction pairs, combat seeds and two seat rotations in each panel. Each holdout contributed 30 scenario blocks and 420 actual games. Hamlets contributed 15 blocks and 210 games. Every game completed without faults. Official duel scores are 3/1/0, divided by 3. The 95% intervals use 10,000 crossed bootstrap draws at seed `202611079`, pairing the training seeds and the resampled scenario blocks within each map.

| Holdout | Games | BC score | λ=0.95 score | λ=1.0 score |
| --- | ---: | ---: | ---: | ---: |
| The Road to Weldyn | 420 | 51.11% | 47.59% | 42.78% |
| A Summer of Storms | 420 | 34.44% | 42.22% | 36.67% |
| Both maps | 840 | 42.78% | 44.91% | 39.72% |

Differences and paired 95% intervals are in percentage points.

| Panel | λ=1.0 − λ=0.95 | λ=0.95 − BC | λ=1.0 − BC |
| --- | ---: | ---: | ---: |
| Both holdouts | −5.19 [−10.28, 0.00] | +2.13 [−2.78, +7.04] | −3.06 [−7.13, +0.83] |
| The Road to Weldyn | −4.81 [−11.11, +1.11] | −3.52 [−9.44, +2.22] | −8.33 [−13.89, −3.70] |
| A Summer of Storms | −5.56 [−13.33, +2.78] | +7.78 [+1.11, +15.00] | +2.22 [−4.26, +8.33] |
| Hamlets validation | −1.11 [−17.78, +16.67] | +1.11 [−15.93, +17.04] | 0.00 [−16.67, +17.41] |

| Training seed | λ=1.0 − λ=0.95 | λ=0.95 − BC | λ=1.0 − BC |
| --- | ---: | ---: | ---: |
| 202611081 | −1.94 | −0.83 | −2.78 |
| 202611082 | −5.28 | +1.67 | −3.61 |
| 202611083 | −8.33 | +5.56 | −2.78 |

The pooled main comparison touches zero at the reported precision. The λ=1.0 score relative to BC varied by holdout map. These results apply to the paired Lite duel design. [Unrounded intervals and per-map seed effects](audit.json)

## Reproduction and evidence

The run used the committed Git archive of `68fbf6b0b087b196526c674f28baffbfae3eb8c4` on `cpuServer`, Ubuntu 24.04.5 LTS and Python 3.12.3. The archive SHA-256 was `240009bf8a55096203d548d4ee349c2e34d574927ff2325c30ef08ef4aef69d2`. The [preregistered launch](https://github.com/t66sun/wesnothLearning/issues/306#issuecomment-6721897371) matches the recorded launch SHA-256 `5ac6d19cab756ce8dade4c739c5f2127e86bb9ea34cec033934625fbd03bf02c`.

| Frozen input | SHA-256 |
| --- | --- |
| Rules | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Lite extension | `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` |
| Astra package | `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933` |
| The Road to Weldyn physical board | `a0712d09f18da79296c9df4d1e62b0bb01af3607eb0cb0371747c6b859bad451` |
| A Summer of Storms physical board | `bb5972c96d25081eafb56c6f171e57dd35b170fe0d2caa6e6e5d4e007d9ee403` |

The audit read the original runtime archive, checkpoint roles, per-cell schedules and raw game replies. It rebuilt each paired score from the learner seat and recorded winner, then reran the preregistered bootstrap. The recomputation matched the driver output exactly. The holdout board hashes were absent from the recorded initialization, training and validation layouts.

The [audit script](audit.py) was transferred using `git archive --format=tar cb41e4d4b72604ae5fd979f3a0ed91278389b667 -- verification/ppo_terminal_return_20261109/audit.py`, SHA-256 `5bae5731b822e17f4675e25cbf6dd671a46abcb98eeef825d445e3ecac36f807`. From its fresh Ubuntu extraction, the audit ran against the original frozen source as follows.

```sh
base=/home/tongshu/acceptance/ppo306_20261108_Miwoyq
review=/home/tongshu/acceptance/ppo306_audit_20261109_JqdyJL
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONPATH="$base/source:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONHASHSEED=0
cd "$base/source"
out=$(mktemp -d /home/tongshu/acceptance/ppo306_review_XXXXXX)
/home/tongshu/venv/bin/python -u "$review/verification/ppo_terminal_return_20261109/audit.py" "$base" "$out"
```

The [raw metadata archive](raw-metadata.tar.gz) preserves 1,347 original files, including the frozen launch, full schedules, job replies, checkpoints' identity records, timing and score outputs. It is 8,413,863 bytes with SHA-256 `4b5f56f6dab9b788f886abf029877d8244ca9cc092ff1ca8af6bb606cb0730f9`. Model binaries and shards remain at the recorded run paths. The [recomputed audit output](audit.json) has SHA-256 `86cef957258549b0d04f3042e9f707e4233d35e77c6815caa241066d84b1eefc`.
