# Eight-worker Lite validation throughput

At 07:13:48 Asia/Shanghai on November 4, 2026, `cpuServer` launched one 14-game rotation using the production `learning.sample.collect` eight-process pool. All 14 games finished with zero faults in **71.86 seconds**, including pool startup and the final partly occupied interval. Each official result matched the archived result from the original float32 validation job. All eight workers reported `torch.float64` for their frozen policy weights. [Frozen plan, timings and results](rotation.tar.gz)

| Format | Complete | Occupied worker seconds | Process CPU seconds |
| --- | ---: | ---: | ---: |
| Duel | 2/2 | 44.72 | 44.18 |
| Four-player FFA | 4/4 | 160.71 | 159.68 |
| Team, both partner contexts | 8/8 | 277.09 | 276.05 |

These games occupied workers for 482.52 seconds. Thirty comparable rotations at full utilization would need **1,809 seconds** across eight slots. The bounded final phase allows 864 seconds before its 900-second external cap. The estimate includes eight first games in fresh worker processes. Holdout maps, scenario mix, models and terminal turns can change the actual cost. This run measures one validation block and supplies no holdout score or strength verdict.

## Inputs and execution

The protocol selected block zero of the [archived v6 BC](../bc_ordinary_v6_20261103/REPORT.md) `validation-000010.json` schedule for every format. It retained all rotations and used Hamlets for duel and Loris River for both four-player formats. Seeds were 2791729219 for duel and team with the Astra partner, 4090059549 for FFA, and 488635208 for self-team. Each job used its archived v10 model, factions, team, seats and 30-turn limit. The probe removed validation learner instrumentation and requested the score-only Astra path. The plan recorded all jobs before dispatch with SHA256 `c3341386436375b1cde7ff6908bc31e54bafa635341725a41da95feb49b10fd9`. All original schedules and models were read-only.

Committed source `3ffad39b6a86a7251234c742dd807e0d7ddb2974` combined the measured [score-only worker](../lite_final_worker_20261104/REPORT.md) and [frozen fp64 inference](../trained_export_precision_20261104/REPORT.md). The shipped source archive SHA256 was `39fbca4a7d7b2c8ffffbb29ef0cf20cb91a2356a03411641c7518778a518e9d7`. In the fresh `/home/tongshu/acceptance/lite_panel_throughput_20261104/src` directory, the existing score-only extension was linked after verifying its source was identical. The plan records the extension, model, schedule, filtered rules and teacher hashes. The eight hardware threads share four physical cores. The other acceptance work paused for this run.

```sh
export PYTHONPATH=.extension:.:vendor/arena
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SOURCE_COMMIT=3ffad39b6a86a7251234c742dd807e0d7ddb2974
timeout --signal=TERM --kill-after=4s 240s /home/tongshu/venv/bin/python -B -u \
  verification/lite_panel_throughput_20261104/probe.py \
  /home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness ../panel
```

The process exited 0 at 07:15:00. The raw archive's SHA256 is `1a45922ea8ec78fc5c88b38c71e5977d842d1ed42b8caae85bb3d1ef52454f95`. It contains per-job start/end, worker PID and CPU times, stock throughput metrics, source identities, exit status and host details.
