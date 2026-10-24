# 2026-10-24 formal training OOM investigation

Run: `runs/v5_lite18h_20261024_003512` under
`/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022`.
Investigation/stop: 2026-10-24 12:58–13:05 Asia/Shanghai. This is a new
incident report; earlier acceptance and frozen run identities remain unchanged.

## Outcome and stop

The run is stopped. Main PID 192814 and its remaining children 192821/192822
were identified by command, working directory and parent relationship. SIGINT
did not finish shutdown within three seconds; SIGTERM was then sent only to
the verified remaining processes. The final process scan finds no process
whose command names this run. No source, rule, manifest, checkpoint or
training parameter on the server was edited; training was not restarted.

There is no graceful pause in this coordinator: progress already written to
disk survives; an unfinished collection batch is not guaranteed resumable.

## Confirmed failure chain

1. Kernel OOM started at **10:07:18**, not just the final kill timestamp.
   RAM was nearly exhausted and the 4 GiB swap was full. The kernel first
   killed desktop/session processes, then at **10:08:23** killed Python
   PID **192834** (anonymous RSS 3,247,612 KiB). This is `global_oom`, not
   a trainer `MemoryError` from its address-space limit.
2. The first OOM task table contains the coordinator, resource tracker,
   three trainer processes and eight pool processes. Their combined RSS is
   **15,068.87 MiB (14.72 GiB)**, with **3,407.35 MiB (3.33 GiB)** swapped.
   Whole task-table totals are 15,155.54 MiB RSS / 4,070.61 MiB swap; training
   processes dominate the recorded memory, so desktop activity is not needed
   to explain exhaustion. RSS sums can double-count shared pages; these are
   kernel RSS observations, not PSS measurements or a precise heap inventory.
3. Pool process RSS ranges from about 954 MiB to 3,213 MiB; the eight pool
   processes together account for about 11.28 GiB RSS. Five rollout jobs
   remained active at first OOM: two team2v2 and three FF4. Eight pool
   processes remain resident even when fewer than eight jobs are active.
4. Losing the worker broke the shared `ProcessPoolExecutor`. Three FF4
   `rollout-00088-ffa4-*` jobs and two `rollout-00050-team2v2-*` jobs recorded
   `BrokenProcessPool`; both trainers saved `failed_stage=ppo` and exited
   around 10:08:25/30. The surviving duel trainer and coordinator remained
   waiting until the user-requested stop, without further training progress.

The killed worker cannot be mapped to one of the five jobs from existing
logs: scheduler events contain job IDs but no worker PIDs. There is no
allocation stack for the killed process, so the exact final allocation and
whether it occurred during play or serialization are not established.

## Why the current limits did not prevent this

- `learning/coordinator.py:limit_memory` applies the 6 GiB address-space cap
  only inside `trainer_main`, not to the game pool, and it is per process,
  not a global RAM reservation.
- `learning/sequences.py` 96 MiB compressed / 768 MiB retained budgets protect
  trainer reads. They do not bound collection or the sum of eight workers
  and three trainers. The earlier sample-share underfill is a separate
  confirmed efficiency defect; fixing it alone cannot prevent this OOM.
- `learning/lite_host.py:play_lite_job` retains complete decision objects in
  `records` until a game ends. These include full candidate/spatial arrays;
  PPO also retains DAgger labels and policy history. Packing on shard write
  happens after collection, so it does not compact the live trajectory.
- `learning/data.py:write_shard` retains augmented `raw_rows` while the
  original records remain alive. `IndexedSequenceStore.write` additionally
  creates whole-sequence JSON text/bytes before compression. This is a real
  additional peak path, but the kernel log alone cannot prove it was the
  killed process's exact allocation site.
- The frozen policy model cache is bounded to four models; there is no
  evidence here of an unbounded historical-model cache. Existing successful
  team2v2 jobs reach 1,621 recorded decisions / turn limit, so multi-GB
  long-game trajectories are a concrete supported workload to investigate.

## Preserved progress and recovery limits

All three `latest.pt` files were loaded sequentially on CPU with
`torch.load(..., weights_only=False)`, without running any training. All
contain feature schema 5, 59 model tensors and 59 optimizer state entries.

| Format | Saved version | Saved phase | Latest SHA-256 |
| --- | ---: | --- | --- |
| duel | 212 | PPO | `718b9bb17d078826f7c729e3c557934ec1857e373e0387df6cec766c3cf813ff` |
| ffa4 | 88 | failed, previous PPO | `7755cedaea876a201e6816bf166045802c87844c1e47c7bae1fc2e88b4e37c6a` |
| team2v2 | 50 | failed, previous PPO | `0a9638c797e3bd648561d15160d2d3b36ca59de9c6fcc5721f34a65b24d01779` |

Duel entered PPO normally (`effective=true`). FF4/team2v2 have recorded
08:00 forced-PPO requests applied around 08:07 (`effective=false`); these
records are pre-existing and were not written by this investigation.
This crash happened during PPO sampling, not the earlier BC accuracy check.

## Repair direction; not implemented or tested in this task

1. Reduce live trajectory memory at the collector boundary and avoid whole
   sequence serialization copies; preserve complete history, candidate sets,
   labels, rewards, bootstrap and on-policy provenance.
2. Bound aggregate collection memory, including resident idle workers and
   trainer usage. Merely raising the trainer limit or read budget worsens
   the capacity problem. Lower concurrency is a possible temporary mitigation,
   not demonstrated safe here and not applied to the frozen run.
3. Repair broken-pool shutdown: `pool.submit` failures are not caught by the
   existing `future.result` handler, and `Experiment.run` joins living
   trainers in `finally` without terminating them for this non-interrupt
   failure. This can strand a trainer waiting on the coordinator. The
   observed residual processes match this failure path; no live stack was
   captured to prove the exact wait location.

Minimal future verification should use one existing long four-player trace
to measure collector/write peak memory and compare labels/history before
and after the repair, plus one intentional worker failure to assert the
whole owned process tree exits. No broad suite, game collection, formal
training, OOM reproduction or parameter change was executed for this report.

## Evidence

- `inspect_stop.py` / `.remote.txt`: process ownership, errors, targeted stop,
  first kernel excerpt and post-stop memory.
- `inspect_failure.py` / `.remote.txt`: kernel history, job failures, phase
  records, tested server source and successful checkpoint loads.
- `compact_summary.py` / `.remote.txt`: first OOM task-table totals, active
  jobs, long completed trajectories and final zero-process scan.

Scripts were streamed over the existing SSH connection into the isolated
Python environment; their stdout/stderr were saved locally. No password or
authentication material is included in these artifacts.
