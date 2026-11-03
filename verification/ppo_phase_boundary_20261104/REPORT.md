# PPO phase completion at a committed batch boundary

The explicit `phase ppo --ppo-batches N` request passed its three simulated Ubuntu checks. Each format counts newly scheduled batches that apply at least one optimizer step. The request survives a checkpoint reload, completes due validation, and returns `ppo_complete` before scheduling another rollout. A later request starts a new count.

## Source and environment

| Source | Commit | Archive SHA256 |
| --- | --- | --- |
| Failing assertions | `ca734aad6c04f5f579e4e1c9cacb98a58be45bbf` | `78c1973ebf2275268193b9ef45a8072362d127fdb3551bfc48a1ba94f0a73b35` |
| Implementation | `38aa8dffb8efcf14d626a8e6cd3373da0bb5a49f` | `f95c2a0413df6d0ddde869a753ca74f4eda7860210f2c6518792b9e386e4ef7e` |

Both source packages were made with `git archive --format=tar.gz --output=<archive> HEAD -- learning lua engine_lite tests vendor benchmarks`, transferred to `cpuServer` with `scp`, checked against the local SHA256 and extracted into fresh directories. Ubuntu used Linux `7.0.0-38-generic` x86_64, Python 3.12.3 and torch 2.9.1+cpu. `WESNOTH_RULES_DIR` pointed to `/home/tongshu/myDev/wesnothLearning/WesnothLearning/data/rules/1.18.8-training`. Its `rules.json` SHA256 was `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`. `OMP_NUM_THREADS`, `MKL_NUM_THREADS` and `OPENBLAS_NUM_THREADS` were all 1.

## Ubuntu commands and results

```sh
cd /home/tongshu/acceptance/ppo_phase_boundary_red2_20261104
/home/tongshu/venv/bin/python -m unittest tests.v5.test_ppo_phase_boundary -v
```

The baseline exited 1 in 0.015 s. The phase runner scheduled another rollout after both new batches had committed. The CLI and request API had no batch-target parameter. An earlier fixture draft lacked `policy_shards` and stopped before reaching the boundary. The corrected fixture above exposed the extra rollout. [Baseline output](baseline.txt.gz)

```sh
cd /home/tongshu/acceptance/ppo_phase_boundary_green_20261104
/home/tongshu/venv/bin/python -m unittest tests.v5.test_ppo_phase_boundary \
  tests.v5.test_training_failure_fixes.PhaseEntryTests tests.v5.test_bounded_loop_progress -v
```

Eleven of 12 tests passed in the first invocation (0.063 s, exit 1). The existing auto-phase test could not construct its schedule because the archive lacked `data/rules/1.18.8/maps/the_freelands.json`. Its ordinary BC and PPO subcases both reported this missing input. [First output](checks.txt.gz)

```sh
mkdir data
ln -s /home/tongshu/myDev/wesnothLearning/WesnothLearning/data/rules data/rules
/home/tongshu/venv/bin/python -m unittest \
  tests.v5.test_training_failure_fixes.PhaseEntryTests.test_auto_uses_next_sampling_method_after_bc_gate -v
```

With the frozen maps available, the affected test passed both subcases (0.005 s, exit 0). `the_freelands.json` SHA256 was `36e9ccd11e045e27544b5319ee8edfce7c795e27efdc075f53d68eab893dead8`. [Map-dependent check](maps-check.txt)

| Coverage | Result |
| --- | --- |
| Positive integer target on a PPO request, including CLI propagation | PASS |
| Two consecutive one-batch requests at clean boundaries each need a new applied batch | PASS |
| Restored request excludes the old pending batch and a zero-update KL rejection, counts two new applied batches and completes due validation | PASS |
| Existing phase entry, gate, pending-work ordering and bounded-runner checks | PASS across both invocations |

The fixtures simulate collection and learner results. They played zero games and executed zero optimizer steps. Real all-format PPO, same-future resume, final selection, final panels and audited export remain in the separate integrated acceptance.
