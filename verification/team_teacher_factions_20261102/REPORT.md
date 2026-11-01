# Team teacher faction exposure

## Scope and identities

Ubuntu `cpuServer`, 2026-11-02. Baseline source `429c7d16df84d878566093a7215420bb732013f9`; fixed source `f89aad6e9f30b2660983eacb5ec6c8e6b2844c4c`. Each was shipped with `git archive` into `/home/tongshu/acceptance/team_teacher_{red,fixed}_20261102`. Both use the existing `/home/tongshu/venv/bin/python` and frozen rules linked from `/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules`. No games, collection or fitting ran in this acceptance.

## Cause and repair

The team starting roster chooses every allied pair but always takes the first two remaining factions as opponents. Rotating the teacher through those seats leaves focal exposure unequal: the first 32 planned games contain no Undead training game; the 400-game plan contains 20 versus 80 Knalgan training games. This reproduces the missing faction in the prior ordinary run. It is one corpus defect, not proof of the sole cause of failed imitation.

Only team teacher jobs now cyclically relabel all four factions so each faction is assigned to each focal seat exactly once per aligned 24-game block. The whole design is relabelled together, retaining distinct factions, all 15 allied pairs over the checked 120-game span, bot roles and the baseline teammate. Non-team teacher and all evaluation schedules keep their previous implementation. Maps, RNG, scenario hashing, split algorithm, candidate budgets and gates are unchanged. The algorithm does not inspect partitions, labels or model scores. Existing frozen schedules are not rewritten.

An initial read-only comparison of advancing the faction design only after completing its seat rotations moved the first Undead training game earlier but left full-cycle imbalance intact; that alternative was not adopted.

## Results

`baseline/schedule.json` and `fixed/schedule.json` contain every planned job's focal faction, seat, map and scenario/partition identity, including prefixes and formal target counts. Game numbers below are one-based; JSON indices are zero-based.

| Team measure | Before | After |
| --- | ---: | ---: |
| First Undead training game | 35 | 12 |
| Undead training games, first 24 / 32 / 48 | 0 / 0 / 2 | 2 / 2 / 6 |
| Distinct scenarios, first 12 / 48 | 12 / 39 | 12 / 48 |
| Training games at target 400, Drakes | 79 | 55 |
| Knalgan Alliance | 80 | 49 |
| Loyalists | 72 | 58 |
| Northerners | 54 | 57 |
| Rebels | 27 | 46 |
| Undead | 20 | 52 |

Before splitting, every 24-game block is balanced by faction and seat; hashing still determines the resulting training/validation counts. No balance claim is made for arbitrary completed-game subsets. Duel/FFA audit outputs are unchanged.

Baseline regression: 3 tests, 4 assertion failures (three imbalanced blocks and missing Undead), exit 1. Fixed run: **46 tests pass, 1 pre-existing error**, exit 1. All four faction regressions and the original distinct-scenario/partition/role checks pass. The error is `PhaseEntryTests.test_auto_uses_next_sampling_method_after_bc_gate`: its synthetic runner lacks `policy_shards`. The same isolated test errors on baseline; see `baseline/baseline_phase.log`. It is not relabelled as passed or repaired by this change.

## Commands

From each extracted root, with `PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1`:

```bash
/home/tongshu/venv/bin/python tests/diagnose_teacher_schedule.py --output schedule.json
# Baseline (exit 1):
/home/tongshu/venv/bin/python -m unittest tests.v5.test_teacher_factions -v
# Fixed (exit 1, 46 pass / 1 error):
/home/tongshu/venv/bin/python -m unittest tests.v5.test_teacher_factions tests.test_schedule tests.v5.test_evaluation_design tests.v5.test_scenario_identity tests.v5.test_training_failure_fixes -v
# Baseline control (same error, exit 1):
/home/tongshu/venv/bin/python -m unittest tests.v5.test_training_failure_fixes.PhaseEntryTests.test_auto_uses_next_sampling_method_after_bc_gate -v
```

Raw outputs and exit files are retained under `baseline/` and `fixed/`. The fixed checks took 2.175 seconds. Ordinary post-repair BC fitting, legal-board teacher ranking and teacher strength remain unaccepted. This schedule check cannot establish readiness or playing strength.
