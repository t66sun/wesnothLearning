# Exported policy inside the frozen native action budget

Ubuntu acceptance, 2026-10-31. Clears blocker 2 of `docs/blockers_temp.md`: a lite policy
exported to Lua was slower than the frozen native action budget, so every final-evaluation game
of the Astra re-entry faulted with `watchdog_timeout` before the second decision
(`verification/acceptance_20261031/L1/REPORT.md:63-73`: `CALL{phase:evaluation,budget:10,first:true}`
→ `RETURN{phase:execution,elapsed_ms:1946}` → `CALL{budget:1}` → fault).

## What changed

- `lua/bot.lua:19-22` truncates the generator's ranked candidate list to `config.score_limit`
  after `C.generate` and before `N.forward`. `candidates[1]` is always `end_turn`
  (`lua/candidates.lua:214`), so the fallback survives; the truncated table is the same object
  fed to `data.learning_record.candidates` and `C.diagnostics`, so choice, plan and record stay
  aligned. A config without the key scores every candidate.
- `lua/relational.lua:88-115` accumulates the candidate-independent context contribution to the
  first scorer layer once (`split = #context`) and adds only each candidate's tail in the same
  column order, instead of rebuilding the full 658-column row per candidate. Bit-identical: the
  same float64 products in the same ascending order as `linear` (`lua/relational.lua:5`).
- `learning/export.py:37,43,71,123` — `write_config()` and `SCORE_LIMIT = 24`; a delivered add-on
  carries `score_limit`, and `export()`/`export_checkpoints()` write it.
- `learning/experiment.py:268-281,714` — `ensure_export(score_limit=...)`, the reuse branch
  regenerates `config.lua` from code, and `final_evaluation` passes `SCORE_LIMIT`. Snapshot,
  support and nomination add-ons pass nothing, so they keep scoring all 128 candidates.

## Identities

| Item | Value |
| --- | --- |
| shipped source | `git archive` of branch `native/action-budget` at `6bc8acb` |
| tree identity | `6bc8acb` was rebased onto `origin/master` as `cffa7e4` after these runs; `git diff 6bc8acb cffa7e4 -- lua learning tests` is empty, so the measured code and tests are byte-identical |
| host tree | `~/acceptance/action_budget_6bc8acb` on `cpuServer` (hostname `server`), no `git` |
| python | `/home/tongshu/venv/bin/python`, torch 2.9.1+cpu |
| wesnoth | `$HOME/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth` 1.18.8 |
| policy | `Policy('duel')`, 771,714 parameters, `torch.manual_seed(0)`, format `duel` |
| `lua/weights_duel.lua` | 16,667,210 bytes, SHA-256 `3969f11f2d5a7b7cb0b2c9c2cf383dd9bb3255cdc700e4903b95836486ff369e` (identical for all seeds) |
| exported `lua/config.lua` | `return {["mode"]="greedy",["version"]="timing",["formats"]={"duel"},["candidate_budget_ms"]=200,["score_limit"]=24}` |
| `SCORE_LIMIT` | 24 candidates scored per decision |

## V1 — revert-sensitive unit check

```
cd ~/acceptance/action_budget_6bc8acb && PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python \
  -m unittest discover -s tests -p "test_lua_contracts.py" -v
```

12 tests, `OK`. `test_deployed_config_scores_only_the_candidate_prefix` is the new assertion: with
`score_limit = 2` the recorded candidate list handed to the stubbed network equals the head of the
uncapped list, `learning_record.candidates` has 2 entries, `choice == 1` and `plan.kind` names the
chosen candidate. Removing the two `lua/bot.lua` cap lines makes it fail against the full list.

## V2 — deployment parity unchanged by the hoist

```
cd ~/acceptance/action_budget_6bc8acb && PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python \
  -m unittest discover -s tests/v5 -t . -p "test_learning_core.py" -v
```

34 tests, `OK`, including `test_verify_numerics_128_candidates_two_turns` and
`test_verify_numerics_memory_overflow_and_128_entities`: Python/Lua maximum error stays ≤ 1e-5 on
a 128-candidate sequence, so the hoist changed no number.

## V3 — native games against the exported add-on

```
cd ~/acceptance/action_budget_6bc8acb && PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python \
  verification/action_budget_20261031/check.py . verification/action_budget_20261031/seed<seed> \
  $HOME/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth <seed>
```

`check.py` exports a `duel` policy with `score_limit = SCORE_LIMIT`, plays one native duel against
the official `baseline` (`match.play_game`, default `timeout = 1.0` and `first_timeout = 10`, i.e.
the acceptance profile), reads every `RETURN` `elapsed_ms` from the recorded event stream and writes
`check_<seed>.json`. Seeds 20261101-20261108 were run and all attempts are recorded.

| seed | reason | turns | actions | decisions | first decision ms (10 s budget) | max decision ms (1 s budget) | median ms | seconds | winner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261101 | `last_leader` | 2 | 5 | 5 | 483 | 231 | 69 | 1.9826 | 2 |
| 20261102 | `last_leader` | 2 | 5 | 5 | 484 | 233 | 69 | 1.9979 | 2 |
| 20261103 | `last_leader` | 2 | 6 | 6 | 483 | 229 | 68 | 2.0675 | 2 |
| 20261104 | `last_leader` | 2 | 5 | 5 | 483 | 232 | 68 | 1.9863 | 2 |
| 20261105 | `last_leader` | 2 | 5 | 5 | 484 | 234 | 69 | 2.0474 | 2 |
| 20261106 | `last_leader` | 3 | 8 | 8 | 483 | 232 | 69 | 2.3861 | 2 |
| 20261107 | `last_leader` | 2 | 5 | 5 | 482 | 232 | 69 | 2.0122 | 2 |
| 20261108 | `last_leader` | 2 | 5 | 5 | 483 | 234 | 68 | 2.0323 | 2 |

No game faulted: `reason` is a normal finish, `faults` is `{}` in all eight, and no decision came
near the frozen `ACTION_TIMEOUT = 1.0`. The first decision of a game is charged against the 10 s
`first_timeout` and includes loading the add-on and its 16.7 MB weight table; every later decision
is charged against 1 s and the 36 such decisions across the eight games ranged 40-234 ms. The
failure this clears was a 1946 ms first decision followed by a fault on the next 1 s decision.

Pass criteria (seed 20261103 and 20261106): `reason != watchdog_timeout`, `faults == {}`,
`actions >= 6`, `decisions >= 6`, `max_elapsed_ms < 800`. The other six seeds played only five
decisions because the random-weight leader died on turn 2; by the pre-decided rule they are
recorded as insufficient evidence rather than passes, and none of them faulted.

`SCORE_LIMIT = 16` (the pre-decided fallback) was not needed.

## Limits

- Timing and wiring only. The policy is a `torch.manual_seed(0)` random-weight `Policy('duel')`:
  layer shapes, not weight values, set the arithmetic cost, and this keeps the check reproducible
  from source with no dependence on a run tree. No playing-strength, convergence or promotion claim
  follows, and none is made.
- Eight games, one map, `duel` at two players. Games ended on turn 2-3 with a leader kill, so the
  observed decision count is small (44 decisions in total) and long battles are unmeasured. The
  `team2v2` and `ffa4` add-ons carry the same `score_limit` from the same code but are not measured.
- Training-time add-ons (rollout snapshots, support, nominations) still score every candidate by
  design; a native-engine *training* run that rolls out such an add-on under the 1 s budget is a
  different behaviour and unchanged here.
- The 120-game final evaluation of the Astra acceptance run is NOT RUN: it needs an explicit
  instruction to collect and evaluate, and its result would be the strength record, not this one.
