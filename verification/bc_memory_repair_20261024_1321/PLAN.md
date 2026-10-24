# Bounded collector-memory repair acceptance

Authorized: repair the diagnosed OOM/failure shutdown and run one heavier
stress acceptance; do not resume formal training. Frozen original run and
checkpoints remain read-only.

Local changes precede deployment. Verify the real collector, exact numeric
precision, shard equality except wall-clock profiling, complete sequence
prefixes, DAgger/bootstrap and broken-pool shutdown. Reuse unrelated evidence.

Deploy sources to a new isolated Ubuntu directory using the existing venv and
rule package. Baseline: one full existing 1,621-decision 2v2 rollout replayed
with legacy collection/index serialization. Pressure: eight compact collectors
holding the same full trace and writing their indexes concurrently while three
real trainers' models, optimizers and bounded BC replay pools remain resident.
All input records retain their original identities, labels and rewards.

Measure process-tree PSS/RSS, MemAvailable, swap and each worker's peak. Assert
eight complete collectors, identical sequence payload hashes to the baseline,
resident trainer replay and zero leftover children. A 12-minute timeout or
MemAvailable below 1.5 GiB aborts this test's own process group and fails;
the stress test must not reproduce a host-wide OOM. Run one explicit worker
death through the real coordinator and assert bounded complete shutdown.

This is collection/write memory and failure recovery evidence, not a new
formal training, a convergence test, all BC/PPO phase re-acceptance or proof
that every possible future long game fits. It does not implement the separate
BC read-share underfill repair or migrate old frozen manifests.
