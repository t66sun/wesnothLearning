# Shared worker-pool failure shutdown acceptance

Date: 2026-10-24. This is the independent coordinator fix following the
[PPO OOM incident](../bc_oom_20261024/REPORT.md). Collection storage and the
separate eight-worker memory test are in the [memory report](../bc_memory_repair_20261024_1321/REPORT.md).

`Experiment.run` formerly terminated live trainers only for KeyboardInterrupt.
A broken ProcessPoolExecutor could instead raise from submit while a trainer
waited on replies.get; finally then joined that live trainer indefinitely.
The failure handler now terminates this experiment's remaining trainers for
any BaseException, re-raises the original failure and joins/closes its own
processes/queues. It neither retries lost work nor reports a failed batch as
successful. Normal trainer exit and format isolation are unchanged.

The focused unit regression failed before repair with `joining a live trainer
blocked on its reply queue`, then passed. The existing round-robin/global
worker-limit regression also passed locally and on Ubuntu. These were the
two coordinator checks in the first Ubuntu regression invocation; neither
depended on the initially missing teacher-package link, so they were not rerun.

`fault_probe.py` exercises actual spawned trainers and the real broker/pool,
with a worker intentionally exiting via os._exit(71). Follow-up submission
raises BrokenProcessPool. The real coordinator handler must terminate waiting
trainers, and the child asserts multiprocessing.active_children() is empty.
An outer 45-second timeout fails and stops only this test's own process group
if shutdown hangs. The actual Ubuntu result is:

```text
EXPECTED_POOL_FAILURE A child process terminated abruptly, the process pool is not usable anymore
FAULT_RESULT {"passed": true, "children": 0}
EXIT 0
```

The original execution was in
`validation_memory_repair_20261024_1321/verification/bc_memory_repair_20261024_1321/fault_probe.py`;
the script and captured output are copied byte-for-byte here. It starts no
games and performs no optimizer updates. Tested coordinator source includes
the local repair commit `98cc08d`; its modified run method matches the
independent publication branch. No other experiment was signaled.

The final shared validation integrity check confirms no formal or validation
Python processes remain and all three old checkpoints retain their prior
hashes; see `bc_memory_repair_20261024_1321/unchanged.ubuntu.txt`. The formal
experiment remains stopped. No old manifest/source migration or resume was
performed. There is no pending acceptance item for this completed scope.
