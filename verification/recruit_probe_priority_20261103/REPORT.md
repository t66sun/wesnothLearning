# Recruit probe coverage on the Sablestone Delta opening

On Ubuntu, candidate contract `work-12000-v9` retains the teacher's Spearman on (15, 23). Contract v8 spent its 192 recruit probes on the first four affordable types and lost this legal action before candidate selection.

## Frozen decision

The source is duel job `teacher-00035-duel-t0`, Sablestone Delta, seed 3264892820, Knalgan Alliance versus Loyalists. The schedule is `/home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness/duel/schedules/bc-batch-000004.json`. The turn-one prefix consists of side 1 ending its turn, followed by side 2 recruiting Spearmen on (14, 22) and (14, 23). Both candidate contracts then queried the same saved state at decision 4. The unchanged d64e1178 teacher chose Spearman on (15, 23), and the public Lite legality interface accepted its execution.

The public legal actions listed eight affordable types at each of two slots, (14, 24) and (15, 23). Every recorded probe result matched that interface. The probe log records each ordered call as `[type, x, y, accepted]` together with the rules, schedule, map and teacher identities. [Decision trace](trace.json)

| Same decision | v8 | v9 |
| --- | ---: | ---: |
| Recruit probes | 192 | 192 |
| Successful / rejected probes | 8 / 184 | 16 / 176 |
| Unique rejected coordinates | 47 | 47 |
| Charged work | 863 | 863 |
| Candidates before selection, excluding end turn | 35 | 43 |
| Retained recruit / move / end turn | 8 / 27 / 1 | 16 / 20 / 1 |
| Exact teacher intent in pool and final set | Absent | Present |

V8 probed Bowman, Cavalryman and Fencer 49 times each, followed by Heavy Infantryman 45 times. Each type succeeded twice. The other 137 rejected calls after the first rejection at each of the 47 illegal coordinates consumed most of the budget. V9 checks the remaining affordable types at each confirmed slot with their own real legality probes. A rejection for one type leaves the other types eligible for later probes. The eight-location ceiling per type and all work/candidate caps stay in force.

The extra eight legal recruits are Horseman, Mage, Merman Fighter and Spearman at both slots. Seven partial leader moves leave the final set. All original full moves remain. The trace identifies every displaced destination. This one decision provides no all-format coverage, imitation or native timing result for v9.

## Ubuntu verification

Both sources were shipped as git archives to new directories under `/home/tongshu/acceptance/`. The rules file SHA256 is `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`, and the accepted v6 extension is `teacher_immunity_checked_20261103/.extension/_engine_lite.so`, SHA256 `63b1c119670d4d0981925fafef4f781ab274f05fb0aa2fedafc8b24dfd503059`. Each working tree linked the frozen maps and combat-filtered rules. Runs used one numerical thread at niceness 19.

| Build | Source commit | Archive SHA256 | Directory |
| --- | --- | --- | --- |
| Red | `0b5ddf8ea0d2520b75e0f33e0757be1865b072dd` | `d8c2219dbca9881da72905d70105d1fa0b831beabcdffb7273e4a2938b3178d8` | `recruit_probe_priority_red_20261103` |
| Green | `4f9680fbe5c3b813e8cfa2bd59d51f07ae17b745` | `de414c338021c42c3aa7e25dded1c896d4eb425daf6a046952141d6cb556d123` | `recruit_probe_priority_green_20261103` |

From the matching source directory, use the linked rules and maps and set the extension first on the Python path.

```sh
export PYTHONPATH=/home/tongshu/acceptance/teacher_immunity_checked_20261103/.extension:.:vendor/arena
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
nice -n 19 /home/tongshu/venv/bin/python -B -m unittest -v tests.v5.test_recruit_probe_priority
```

Red exited 1 in 0.892 s. The exact match index was −1 after the independent legality assertion passed. The green run also exercised the existing dense roster check in the same invocation.

```sh
nice -n 19 /home/tongshu/venv/bin/python -B -m unittest -v \
  tests.v5.test_recruit_probe_priority \
  tests.v5.test_candidate_pool_budget.CandidatePoolBudgetTests.test_recruit_probe_budget_spans_every_affordable_type
```

Both green checks passed in 0.814 s. The matched inspection used `tests.diagnose_bc_coverage.traced` and a test-only wrapper around the original `ai.check_recruit` to observe calls. Collection and BC ran separately under their original v8 contract.
