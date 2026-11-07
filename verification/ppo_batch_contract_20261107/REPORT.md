# Fixed-Astra duel PPO batch contract

[PPO-A2 issue #271](https://github.com/t66sun/wesnothLearning/issues/271) under [roadmap #269](https://github.com/t66sun/wesnothLearning/issues/269), verified on Ubuntu on 2026-11-07.

The comparison driver groups one PPO game-ordinal stream into 4- or 8-game physical batches. Ordinal zero starts at the frozen PPO boundary of each arm. The existing fixed-Astra four-game schedule supplies the map, factions, learner seat and random seeds. Every job in a physical batch uses the same sampled policy export. The schedule file still uses the runner batch index, so pending work and shard paths stay attached to the existing runner. [Driver](driver.py)

The driver checks the pinned, qualified BC endpoint before starting the branch and checks the copied weights and fresh Adam afterward. `start_arm` writes the ordinal origin and both deadlines to the existing budget file. `resume_arm` uses the saved run directory, manifest, stage and budget. An optional fresh-target ceiling reuses the previous comparison's admission and tail accounting. Omit it when equal wall time is the primary comparison. The first real eight-game batch belongs to [PPO-A3](https://github.com/t66sun/wesnothLearning/issues/272).

## Ubuntu results

- The scheduler paired the first 16 ordinals from 4- and 8-game groups, starting from different inherited runner batch numbers. The map, ordered roster, learner seat, physical scenario family, game family, combat seed and sampling seed matched. The existing #223 test passed its full-cycle map/seat/faction balance assertions.
- The production runner read eight complete same-version fixture trajectories containing 16 fresh targets. The interrupted path saved its cursor after one optimizer step and resumed from that checkpoint. Resume reread the eight frozen shards once, recovered the same 16 target keys and settled the same counters, cursor and saved model digest as uninterrupted execution. Both stopped at 16 on a 15-target budget.
- Missing, ineligible and deadline-interrupted collection tails admitted zero trajectories, left the prior complete checkpoint untouched and never entered the optimizer. A hard cutoff leaves logged collection work outside settlement. The same expired budget starts no new batch on restart. Missing or ineligible results surface as a failed batch.
- The reused #227 tests passed the fresh-target accounting for zero-step KL rejection, pending work at the admission cutoff and whole-tail settlement. The actual launch/resume check ran both configurations with admission closed and the broker guarded against all game requests. Each retained the same qualified BC weights, empty Adam state, ordinal origin at runner batch 38, manifest and budget, with zero game requests. [Passing fixtures](green.log), [startup evidence](startup.log), [startup check](startup_check.py)

| Reverted behavior | Committed overlay | Assertion |
| --- | --- | --- |
| Generate scenarios from the runner batch index | `48d89a20dc10adcbff944870410bb8ade6dc80aa` | The first eight ordinals were 424–431 instead of 0–7. [Log](batch_index.log) |
| Force four games regardless of configuration | `f16a9e6f9d40035ea696594b25f7183529263eb5` | The production runner handed four jobs to the fixture collector instead of eight. [Log](ignore_width.log) |
| Allow production's usual partial collection settlement | `3b7fd083ba7038f7c0ad2587c0d41d0fc6e8e025` | The three incomplete-tail cases reached the optimizer. [Log](partial_batch.log) |

## Reproduction and scope

The seven targeted tests passed in 3.655 seconds on `cpuServer`, Ubuntu 24.04.5 LTS, Linux 7.0.0-38-generic, Python 3.12.3. The committed source `347100fbb36429ad95c77c091ab2e7c17e80f07f` was shipped with `git archive --format=tar` to `/home/tongshu/acceptance/ppo_batch_contract_20261107_347100f`. Its archive SHA-256 is `1ed45ddc80fdacbbdb29760c0a26aff10f67065d2c47038bf701b23e7d2defff`. Rules and map hashes are in the green log. Each revert used a fresh extraction of the same source archive and an overlay containing only `driver.py` from the named mutation commit. Each revert test exited 1 at the assertion above. The copied logs normalize line endings and trailing whitespace.

From the extracted source, provision the existing frozen maps as in [#223](../ppo_scenario_coverage_20261106/REPORT.md) before running the checks.

```sh
mkdir -p data/rules
ln -s /home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8 data/rules/1.18.8
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python=/home/tongshu/venv/bin/python
suite=verification.ppo_batch_contract_20261107.test_contract
budget=verification.duel_ppo_comparison_20261106.test_contract.DuelComparisonContractTests
"$python" -m unittest -v "$suite" \
    "$budget.test_zero_step_batches_count_fresh_and_rejected_work" \
    "$budget.test_pending_training_and_validation_keep_hard_settlement_deadline" \
    "$budget.test_real_learn_boundary_keeps_whole_batches_and_admits_no_next_batch" \
    tests.v5.test_ppo_scenario_coverage.PPOScenarioCoverageTests.test_complete_cycles_balance_maps_seats_and_focal_factions
"$python" -u ../ppo_a2_271_startup_check.py
```

The startup command used the original copy of the linked script and the accepted #227 BC run in place. Revert commands used `"$python" -m unittest -v "$suite.BatchContractTests.$test_name"` with `test_same_ordinal_stream_with_different_boundaries`, `test_eight_complete_trajectories_match_after_pending_train_resume` and `test_incomplete_batch_keeps_previous_complete_checkpoint`, respectively.

The initial archive lacked the provisioned map link. Its setup errors are excluded from the behavior evidence. The Ubuntu checks exercise scheduling and the real pending-update path with fixture trajectories. There were zero new games and no formal training or online cost or strength measurements. Windows ran no tests.
