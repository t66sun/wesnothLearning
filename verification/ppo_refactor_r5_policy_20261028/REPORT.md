# R5 policy rehearsal opt-in - Windows reference checks and Ubuntu acceptance

Date: 2026-10-28 (Asia/Shanghai). Parent plan: [docs/ppo_refactor_plan.md](../../docs/ppo_refactor_plan.md) R5.
Branch `codex/r5-policy-rehearsal`, implementation `c19d5ad4d996690ab5919ebe1a0e877ff2d4e95c`
(parent `91ac367bc75fbd26af643f37cae3bb2df3a36a82`). Ubuntu is the acceptance environment: the
same targets were rerun there from archive `r5policy_a16d385.tar` (SHA-256
`3874d3b88700976487b312a53359944e720e2fe0506907de2ed14b386a8d4777`, source `a16d385`) and pass.
Nothing here is training, collection or strength evidence.

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

## Ubuntu acceptance (2026-10-28)

Environment: Linux 7.0.0-38-generic, Python 3.12.3, torch 2.9.1+cpu, rules
`d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`. The archive carries a partial
tracked `data/` tree, so `rerun_ubuntu.sh` removes it before linking the frozen
`training_lite30h_20261025/source/data`; that script change is committed with this evidence. Logs in
[`ubuntu/`](ubuntu/).

| Check | Result | Log |
| --- | --- | --- |
| `tests/v5/test_rehearsal_source.py` | **6 PASS** | `ubuntu/rehearsal.log` |
| PPO plan + validation cadence + rehearsal suites | **18 PASS** | `ubuntu/related.log` |
| `py_compile` of both changed files | pass | script step, exit 0 |
| Revert `allow_policy_rehearsal` | fails with `no rehearsal data distinct from the evaluation control` (exit 1) | `ubuntu/revert.log` |
| Revert the pool admission | fails with the same error (exit 1) | `ubuntu/revert.log` |
| Restored `learning/experiment.py` | `sha256sum -c` OK (`1647e889...`) | `ubuntu/restored.log` |

Source hashes before the reverts: `learning/experiment.py` `1647e889...`,
`tests/v5/test_rehearsal_source.py` `2e0ac6c9...`. The acceptance claim is limited to these targets;
no corpus, BC/PPO run or native game was started.

## Limits
- **No training or games.** No corpus, BC/PPO run, native match or strength measurement was
  started. The runner log cap is a separate change; the missing human replay corpus is untouched.
- **Strength effect unmeasured.** Rehearsing on the run's own frozen rows removes the empty-pool
  failure; it says nothing about convergence, forgetting or strength.
- **Current-batch inclusion.** The first PPO update rehearses on the same rows it optimizes, which
  doubles their auxiliary weight relative to later batches; the report exposes this through
  `rehearsal_sources` but does not quantify it.
- **No human data.** The curated corpus still has no 1.18.8 `era_default` standard-multiplayer
  replay, so `source='human'` rehearsal remains absent.
