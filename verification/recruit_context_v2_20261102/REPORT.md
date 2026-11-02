# Matched legal-context probe on the v2 team batch

Date: 2026-11-02 (Asia/Shanghai). One bounded follow-up under the user's continuing authorization for this task. No new games, production features, loss changes, checkpoint edits, PPO or native evaluation.

## Identity and frozen comparison

- Probe source: `905eae5013ba6c8ba9dc052cca96c8c2fd7925a8`, based on `40d4a93`.
- Source archive SHA-256: `42a057f5fc554a68f00dd3b8a4778f754d77f29136099002951ecc714bcc0c70`.
- Ubuntu source root `/home/tongshu/acceptance/recruit_context_v2_20261102`; parent run `/home/tongshu/acceptance/team_bc_v2_20261102/runs/team_bc_v2` remains read-only.
- Same Python 3.12.3 / torch 2.9.1+cpu / one-thread environment and isolated v2 extension as the parent. Extension SHA-256 `ccb7c763cbce620e5d07736e6ae73df2c3891bdd9f281ab79ee10d63e2675365`; frozen rule, teacher and input identities are in [the parent report](../team_bc_v2_20261102/REPORT.md).
- Parent version-5 model SHA-256 `2fd567c68ae75ed3f5f9f62dc012d6e02965502937e63cbd8bf58f6f0905732c`.
- [plan.json](plan.json) freezes 2048 training / 1024 validation rows, max 600 updates using complete epochs (**588 planned**), 900 s update deadline, 1200 s external cap, original loss/sampler/Adam/RNG, one arm, no added seed or collection.

The existing diagnostic appends two zero-initialized scorer columns on an in-memory copy: candidate-type own nonleader count / 10, and recruit-slot distance to current visible enemies / 50. Both use the policy's recorded legal view, never teacher preferences or referee state. Production schema and exported policy code remain unchanged. All recorded own contexts are complete (`incomplete_own_context_rows = 0`).

## Entry-point verification

The old helper accepted only an eight-epoch/600-second probe, so it could not match the v2 control. With the same `--updates 600 --seconds 900` arguments, old source `959ae6a` exits **2** before training with unrecognized arguments: [budget_baseline.log](budget_baseline.log).

The helper now accepts explicit update/time caps, reports planned versus actual updates, asserts complete-epoch update counts and logs progress. Omitted arguments retain eight epochs / 600 seconds. No learner or model implementation is changed.

```bash
cd /home/tongshu/acceptance/recruit_context_v2_20261102
export PYTHONPATH="$PWD/.extension:$PWD:$PWD/vendor/arena"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
timeout --signal=TERM --kill-after=10 1200 /home/tongshu/venv/bin/python -u \
  tests/diagnose_bc_recruit_context.py \
  --run /home/tongshu/acceptance/team_bc_v2_20261102/runs/team_bc_v2 \
  --format team2v2 --output verification/recruit_context_v2_20261102/result.json \
  --updates 600 --seconds 900
```

Observed exit **0**, **588/588** updates, not interrupted, **412.23 s** update-loop time. Outputs: [result.json](result.json), [probe.log](probe.log), [comparison.json](comparison.json). No local Windows tests were run.

After termination, assertions verify identical starting held-out kind metrics, identical update counts/window visits/decisions seen, and unchanged parent checkpoint hash. The old CLI fails this invocation; the new command and update-count assertions pass, proving budget wiring. The original-loss control is the immutable parent [original_loss_curve.json](../team_bc_v2_20261102/original_loss_curve.json).

## Result: complete imitation gate FAIL; inputs not adopted

| Held-out metric | Original-loss control | Explicit-context arm |
| --- | ---: | ---: |
| Recruit exact | 32/57 (56.14%) | 35/57 (61.40%) |
| Recruit type | 39/57 | 39/57 |
| Recruit slot | 48/57 | 46/57 |
| Move exact | 425/722 (58.86%) | 415/722 (57.48%) |
| Attack exact | 32/128 (25.00%) | 33/128 (25.78%) |
| Overall accuracy | 58.31% | 57.72% |
| Cross-entropy | 1.93817 | 2.03776 |

Training recruit improves to 153/165 (92.73%), but held-out type matches stay unchanged. Attack still fails the unchanged 35% floor; overall accuracy and CE worsen. The predeclared full-gate criterion is not met, so this is not a production feature change or ordinary-readiness pass. No additional seeds, input variants or retries are launched within this comparison.

Raw loop times are not a speed comparison: the control performs intermediate validation within its timed update loop; this arm logs progress and evaluates at the end. Quality uses the same endpoint sample/update budgets and matching start. No statistical strength, full-loop acceptance or native transfer conclusion is supported.
