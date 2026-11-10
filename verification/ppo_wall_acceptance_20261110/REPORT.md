# Equal-work Duel PPO wall-time acceptance

[#312](https://github.com/t66sun/wesnothLearning/issues/312) under [#309](https://github.com/t66sun/wesnothLearning/issues/309), measured on cpuServer on 2026-11-10 Asia/Shanghai.

The optimized arm took **3,019.77 s** versus **3,659.35 s** for the same settled work across three paired seeds. This reduces wall time by **17.48%**, saving **639.57 s**. Each pair exceeds the 10% threshold. All schedule, reply, trajectory, history, validation, model, Adam and RNG comparisons match. Peak trainer RSS across the three seeds was 1,434 MiB on the baseline and 1,417 MiB with the changes. [Independent audit](audit.json)

## Paired work and wall time

| Training seed | Baseline, s | Optimized, s | Wall reduction | Settled PPO batches per arm | PPO / validation games per arm | Fresh decisions per arm | Committed steps per arm | Peak trainer RSS, baseline / optimized MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 202611081 | 1,258.53 | 1,043.78 | 17.06% | 16 | 128 / 12 | 14,059 | 80 | 1,434 / 1,417 |
| 202611082 | 1,171.50 | 959.97 | 18.06% | 16 | 128 / 12 | 13,001 | 82 | 1,386 / 1,363 |
| 202611083 | 1,229.31 | 1,016.01 | 17.35% | 16 | 128 / 12 | 13,835 | 87 | 1,379 / 1,382 |
| Pooled | 3,659.35 | 3,019.77 | 17.48% | 48 | 384 / 36 | 40,895 | 249 | 1,434 / 1,417 |

All six cells started from the same qualifying #306 BC actor and critic with an empty Adam state. Each used the frozen 8-game batches, lambda 0.95, 8 workers, one trainer thread, Astra and the same 30-turn scored task. Each cell settled 16 positive-update batches and completed the two due validation panels, at versions 40 and 50. A cell starts at process launch and ends on process exit after checkpointing and validation. The order alternates within pairs as frozen in [launch.json](launch.json).

The audit compares all 768 PPO and 72 validation game records across both arms, the 1,536 policy and DAgger shards, and the 96 settled update records. It binds complete schedules, packed trajectory content, losses, KL decisions, update counts, and the actor, critic and Adam tensors. It also compares the saved Python and Torch RNG states. Run-local path prefixes, deadlines and wall or memory telemetry are normalized for pair comparison. The packed shard comparison omits only the measured timing.ms field. Gzip charged bytes are excluded from history parity because the timing telemetry can change compressed size. The original checkpoint file hashes, per-field comparison results and exact endpoint digests are retained in the audit.

| Three-cell totals, s | Baseline | Optimized |
| --- | ---: | ---: |
| PPO collection spans | 1,073.01 | 1,027.81 |
| Due validation worker spans | 124.32 | 118.49 |
| Remaining cell wall, including preparation, update and saves | 2,462.02 | 1,873.47 |

Worker spans use the time from the first submission to the last completion in each physical batch. They do not sum concurrent workers' CPU or isolate preparation from optimizer and save time. [Earlier fixed-input measurements](../ppo_wall_speed_20261110/REPORT.md)

## Budget and release decision

| Event or interval | Observed, Asia/Shanghai |
| --- | --- |
| Driver start | 18:48:59.335 |
| Six cells complete | 20:40:20.600 |
| Original continuous deadline | 21:48:59.335 |
| Read-only audit start | 22:32:03.027 |
| Read-only audit finish | 22:34:15.992 |
| Active driver wall through all cells | 6,681.26 s |
| Wait from driver completion to audit start | 6,702.43 s |
| Read-only audit wall | 132.96 s |
| Measured active driver and audit wall | 6,814.23 s |
| Continuous elapsed wall through audit | 13,516.66 s |

All six cells finished before their 1,500 s caps and the driver finished inside the 9,000 s training allowance. The read-only audit took less than the reserved 1,800 s. The requested monitoring pause extended past the original continuous deadline. The audit preserves that missed clock with audited_in_budget=false and adoption=false. The user subsequently specified the release rule of at least 10% speedup and equivalent work and model states. Those technical conditions and the memory limit pass. The release uses that instruction, with the original elapsed-budget result recorded separately.

## Source and evidence

The frozen source archives were checked before launch. The base and optimized production trees used the same compiled Lite extension, Astra source and package, BC endpoint and five workload maps. Complete identities and limits are in [launch.json](launch.json).

| Artifact | Source or SHA-256 |
| --- | --- |
| Baseline source | 14a9c0decba616642f2e643f4e0bb2365801a535 |
| Baseline Git archive | 2a3cda0517c6bd98866236fee1dc7a68062623bbad3421e85e93fd87f17887bb |
| Optimized source | be5acc8b8ec00ed23688b148b3c09c87ce333d37 |
| Optimized Git archive | e96971e0e90560a59da9a07bb724cea74f3b25e7f4e37cf82505c9fb216088a9 |
| Driver Git archive source | 28a732096895ce246c4eda2339439f8b00ceab59 |
| Driver Git archive | 6e0adea428e39b954fc057e2826c614a01c4134e9aeefd6a775a13a5dfad91c6 |
| Audit Git archive source | 20bf8b8234803cf2204693a717872a2223a8a841 |
| Audit Git archive | 303c5db090553d31fc1e874c43f0bcd7368bd96c49503d60a85428af333fc1e7 |
| Launch manifest | e584b518dc3475d405bb280f899ac9ea25953ef2c038777af372b1f36e0289de |
| Audit output | b2f6f372dc4426c38e6a00f0914c83ff3fdd427f0f1f7c579c6a683999a6c4b7 |
| Raw metadata archive | 482abe07d8e39cc93ec19e76d5a6628417cb136519627dcbeec2445683360ba8 |

[Raw metadata](raw-metadata.tar.gz) preserves 216 files, including the launch, all cell process and exit records, schedules, game replies, state, validation and coordinator logs. The original checkpoints, shards and sources remain in /home/tongshu/acceptance/ppo312_20261110_lNyy9W. [Driver](driver.py) · [Audit code](audit.py)
