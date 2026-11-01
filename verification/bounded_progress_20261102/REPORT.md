# Bounded runner PPO progress accounting

Date: 2026-11-02 (Asia/Shanghai).

Scope: blocker 11, manual runner batch limits and committed start/resume boundaries. No collection, games, optimizer execution, final panel or delivery export was launched. Windows ran source/document inspection only.

## Identity

- Baseline plus failing assertions: `2dc0573bd2c9e3a5075ed56e08fde402086f1731` (original runner from `7b63460`).
- Accepted source: `e3f9b9646e7e8a6c1209e20acb298e930e120530`.
- Source archive SHA-256: `66a4c81418c0fce1b0717a8148158e399eddecf5be3485f3c7104a5dea458379`.
- Ubuntu acceptance host `cpuServer`: Linux `7.0.0-38-generic`, x86_64; Python 3.12.3; torch 2.9.1+cpu.
- Existing frozen rules: `/home/tongshu/myDev/wesnothLearning/WesnothLearning/data/rules/1.18.8-training`, linked read-only by use into the fresh source directory. No rule, checkpoint or corpus was changed; these checks do not execute combat or numerical inference.

## Commands and results

Local source delivery used `git archive --format=tar.gz --output=.ops/bounded-progress-{red,green}.tar.gz HEAD`, then `scp` and extraction into fresh `/home/tongshu/myDev/wesnothLearning/bounded_progress_{red,green}_20261102` directories. The host has no git.

Baseline command in `bounded_progress_red_20261102`:

```bash
/home/tongshu/venv/bin/python -m unittest tests.v5.test_bounded_loop_progress -v
```

Observed: exit 1, 3 tests, 4 assertion failures, 0.006 seconds. The first PPO limit was the scalar 5 instead of duel/FFA/team limits 9/6/5. A resume with no new updates, pending work or a failed trainer still advanced to evaluation. Those are the expected regressions; no missing dependency caused the failures.

Accepted command in `bounded_progress_green_20261102`:

```bash
WESNOTH_RULES_DIR=/home/tongshu/myDev/wesnothLearning/WesnothLearning/data/rules/1.18.8-training \
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
/home/tongshu/venv/bin/python -m unittest \
  tests.v5.test_bounded_loop_progress tests.v5.test_training_turn_limit -v
```

Observed: **10 tests, OK**, 0.108 seconds; SSH command exit 0. Full output: [ubuntu.log](ubuntu.log). `FAIL ...` lines within the output are the manual runner's expected rejected-stage messages; unittest marks those cases `ok`.

| Check | Result | Observation |
| --- | --- | --- |
| Per-format PPO allowance | PASS | BC batches 5/2/1 produce first limits 9/6/5 and resumed limits 10/7/6 |
| Applied stage limits | PASS | Initial 5/2/1 does not stop; FFA reaching its own limit stops with `committed_batch_limit` |
| Resume progress | PASS | Earlier PPO updates cannot satisfy the resumed phase |
| Committed boundary | PASS | Pending training and failed state both stop before evaluation |
| Training turn-limit contracts | PASS | Six existing checks remain passing, including the manual-runner CLI |

## Limits and remaining blockers

This accepts the runner's progress accounting only. The real post-BC chain, same-future resume, selected-checkpoint final evaluation, ordinary BC readiness, native transfer and teacher strength remain open. No performance improvement or training-quality gain is measured. Hard caps remain failure exits; gates, candidate/work/time limits and frozen historical evidence are unchanged.
