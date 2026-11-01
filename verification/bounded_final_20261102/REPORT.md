# Bounded final-panel handoff

Date: 2026-11-02 (Asia/Shanghai).

Scope: blockers 9/11, the manual runner's evaluation-to-export handoff. No collection, games, training, real evaluation or delivery export was launched. Tests simulate child-stage results.

## Identity and delivery

- Baseline assertions: `0a3016bb7aa625a8e09ee7524bbd7a86ab2e4e32`, runner from merged `5db2c6c`.
- Accepted implementation: `c60ab9f98da3284ed2ca0654b407f7d775b4c9fe`.
- Accepted source archive SHA-256: `8d99b81ac020300a4f0b73df3e971422554b19d5cf24ed937e472cf1bb885f87`.
- Same Ubuntu `cpuServer` environment as `../bounded_progress_20261102/REPORT.md`: Python 3.12.3, torch 2.9.1+cpu, x86_64 Linux 7.0.0-38-generic.
- Each commit was shipped with `git archive --format=tar.gz --output=.ops/bounded-final-{red,green}.tar.gz HEAD`, copied by scp and extracted into its fresh `/home/tongshu/myDev/wesnothLearning/bounded_final_{red,green}_20261102` directory. Existing main-tree frozen `data/rules` was linked for the unchanged turn-limit checks; no frozen inputs were edited.

## Commands and observations

In `bounded_final_red_20261102`:

```bash
/home/tongshu/venv/bin/python -m unittest tests.v5.test_bounded_loop_final -v
```

Exit **1**, 3 tests, **9 expected assertion failures**, 0.019 s. All nine incomplete/failed simulated evaluation cases advanced to the simulated export and returned success. A complete panel already accepted statistical passed/not_passed/inconclusive results. Full output: [baseline.log](baseline.log).

In `bounded_final_green_20261102`:

```bash
WESNOTH_RULES_DIR=/home/tongshu/myDev/wesnothLearning/WesnothLearning/data/rules/1.18.8-training \
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
/home/tongshu/venv/bin/python -m unittest tests.v5.test_bounded_loop_final \
  tests.v5.test_bounded_loop_progress tests.v5.test_training_turn_limit -v
```

Exit **0**, **13 tests OK**, 0.125 s. Shell preserved the unittest exit code. Full output: [ubuntu.log](ubuntu.log). The runner's printed `FAIL` messages are the expected rejection cases, not failed tests.

| Case | Result |
| --- | --- |
| Missing report, missing block, reduced planned block count | Stops before export |
| Faulted game, insufficient distinct scenarios, infrastructure error | Stops before export |
| Failed trainer, still-final state, pending train | Stops before export |
| Complete 30-block/12-scenario panel with any statistical conclusion | Continues to explicit audited export stage |
| Earlier PPO progress and turn-limit contracts | All 10 checks remain passing |

## Accepted scope and limits

The runner freezes 30 final blocks explicitly in the launch command and requires completed, error-free per-format states, nonempty control reports, all planned blocks, zero missing blocks/fault games and at least 12 distinct scenarios. Statistical victory is not required for operational completeness. The production comparison implementation and its gates are unchanged.

Real selected-checkpoint evaluation, post-BC execution, same-future resume and audited delivery remain unrun in this phase. This does not close L1/L2, ordinary BC readiness, native transfer or strength. No timing or training-quality improvement is claimed.
