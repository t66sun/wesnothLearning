# BC window sampling and recurrent work reuse

Ubuntu acceptance, 2026-11-01. Tested source `da35fc1e159d6a63bb157293faa4ae3a8614e363`; baseline `558f0c20f89544788427c09067aae9e239bb14d2`. Both shipped by git archive to fresh directories on cpuServer: `/home/tongshu/acceptance/window_memory_20261101_v1` and `window_memory_20261101_base`. Python `/home/tongshu/venv/bin/python`; existing lite extension and read-only rules link to `/home/tongshu/myDev/wesnothLearning/WesnothLearning/data/rules`. Contract tests use synthetic rows. No formal training, collection or native games.

## Behavior

BC indexes one representative per eight-turn window through the existing pool/source/engine/family sampler, then trains the selected complete windows. Sampling remains with replacement; long windows no longer have additional lottery entries. Window visit, unique-window and repeated-window counters are recorded, with visited indices in the existing step cursor for continuation. Historical decision-pass metrics remain visit counts, not unique coverage.

BC and PPO create a detached scene/prefix cache at each logical optimizer step. Active replay suffixes are recomputed with gradients; detached scenes and prefix GRU states can be reused across microbatches and PPO rehearsal. Cached rows are retained for the lifetime of that step so Python identities cannot be recycled. A new step creates a new cache; no cache is persisted to checkpoints.

Frozen lite inference advances each side's hidden state and 32 slots only over newly committed history rows. Same-turn decisions and bootstrap reuse that state, while age-dependent reads are recomputed when turn/history changes. State belongs to the job/side, not the shared model cache.

## Commands and observations

From v1, with `PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python -m unittest`:

- `tests.v5.test_window_memory_cost tests.v5.test_replay_optimization tests.v5.test_lite_policy_memory tests.v5.test_learner_extraction tests.v5.test_ppo_resume_counters -v`: 17 tests, 15 PASS, 2 FAIL (5.444 s), `checks.log`.
- `tests.v5.test_learning_core tests.v5.test_ppo_plan tests.v5.test_kl_defer -v`: 46 PASS (15.848 s), `extended.log`.

The two failures are the historical fixed loss expectations in learner extraction. Running that unchanged suite on baseline yields the same two failures and exact actual losses: BC 3.878143310546875 versus expected 4.353553771972656; PPO 0.8904262781143188 versus expected 0.9339113235473633. See `baseline.log`. No expectations were lowered or replaced and no exception was suppressed.

New checks demonstrate: two unequal-length windows contribute exactly two representatives with near-equal frequency in 4,000 fixed-seed draws; committed visit counts distinguish repeats; cached output/gradients match fresh computation across two optimizer updates while encoding fewer rows; 35-turn frozen inference encodes 69 rows instead of baseline 630, with value parity through slot overflow. Existing tests cover sampling probabilities, bootstrap RNG preservation, side/job isolation, PPO same-future resume, KL rejection and deadlines.

Revert sensitivity: copying only the new test file into baseline and running `tests.v5.test_window_memory_cost.WindowMemoryTests tests.v5.test_window_memory_cost.IncrementalMemoryTests.test_long_rollout_encodes_each_history_row_once -v` gives two assertion failures (18 representatives instead of 2; 630 encodes instead of 69) and one missing-cache-interface error. See `revert.log`. The unchanged-weight cache assertions pass on v1.

## Limits

61 passing test executions include inherited/repeated memory test cases; this is not a claim of 61 unique scenarios. Two baseline failures remain failures. These are functional and counted-work results, not a measured full-training speedup or convergence/strength evidence. No cache spans a training optimizer update; callers of the optional cache must keep that lifetime. BC distribution changes intentionally, so an old in-progress BC run is not claimed to reproduce the pre-change future. No frozen artifacts or old evidence were modified.
