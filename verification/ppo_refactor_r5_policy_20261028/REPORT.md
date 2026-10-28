# R5 policy rehearsal opt-in - Windows reference checks, NOT Ubuntu acceptance

Date: 2026-10-28 (Asia/Shanghai). Parent plan: [docs/ppo_refactor_plan.md](../../docs/ppo_refactor_plan.md) R5.
Branch `codex/r5-policy-rehearsal`, implementation `c19d5ad4d996690ab5919ebe1a0e877ff2d4e95c`
(parent `91ac367bc75fbd26af643f37cae3bb2df3a36a82`). Ubuntu is the acceptance environment and
was **not** run in this phase; nothing here is acceptance, training or collection evidence.

## What changed

- `learning/experiment.py`: `state['policy_shards']` persists every successful PPO rollout shard;
  `finish_train` appends those shards to the PPO rehearsal pool and passes
  `allow_policy_rehearsal=method=='ppo'` to `train(...)`. The BC stage is unchanged and still reads
  teacher labels only; library defaults in `learning/ppo.py` and `learning/train.py` stay `False`,
  so the opt-in is per run and per stage, not a new default.
- `tests/v5/test_rehearsal_source.py`: `test_runner_rehearses_ppo_on_its_own_policy_shards` drives
  `FormatExperiment.finish_train` with a control-only pool plus one policy shard and asserts the
  rehearsal report `[{'source':'policy','teacher_impl':None,'sha256':'student-sha'}]`,
  `rehearsal_rows_excluded=2`, and one committed update.

Decision recorded: the current batch is included in the pool. Excluding it reproduces
`ValueError('no rehearsal data distinct from the evaluation control')` at the first PPO update,
which would make the opt-in inert. The auxiliary CE therefore rehearses the frozen policy's own
rows; that is self-imitation, disclosed through `rehearsal_sources`, and it is not expert
supervision and adds no human labels. `bc_aux` stays 0.10; no gate, coefficient or corpus changed.

## Checks run (Windows, CPU)

Environment: Python 3.12.14, torch 2.9.1+cpu. Logs in [`windows/`](windows/).

| Check | Result | Log |
| --- | --- | --- |
| `tests/v5/test_rehearsal_source.py` | **6 PASS** | `windows/rehearsal_tests.log` |
| PPO plan + validation cadence + rehearsal suites | **18 PASS** | `windows/related_suites.log` |
| `py_compile` of both changed files | pass | `windows/compile.log` |
| Revert `allow_policy_rehearsal` | test fails with the empty-pool error | `windows/revert.log` |
| Revert the pool admission | test fails with the empty-pool error | `windows/revert.log` |
| Restored tree after reverts | clean | `windows/restored.log` |

Source identities: `windows/source.txt` (commit), `windows/source.sha256`
(`learning/experiment.py` `4d994f45...`, `tests/v5/test_rehearsal_source.py` `2b2964fa...`).

## Limits

- **Ubuntu acceptance not run.** These are Windows reference checks only; the Ubuntu variants of
  the same `unittest` targets remain the acceptance gate.
- **No training or games.** No corpus, BC/PPO run, native match or strength measurement was
  started; the 16 MiB runner log cap and the missing human replay corpus are untouched.
- **Strength effect unmeasured.** Rehearsing on the run's own frozen rows removes the empty-pool
  failure; it says nothing about convergence, forgetting or strength.
- **Current-batch inclusion.** The first PPO update rehearses on the same rows it optimizes, which
  doubles their auxiliary weight relative to later batches; the report exposes this through
  `rehearsal_sources` but does not quantify it.
- **No human data.** The curated corpus still has no 1.18.8 `era_default` standard-multiplayer
  replay, so `source='human'` rehearsal remains absent.
