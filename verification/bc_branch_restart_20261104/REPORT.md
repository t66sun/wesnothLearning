# Fresh BC initialization from the compatible v6 parent

The new branch mode brings the parent's policy weights, teacher and DAgger shards, and lineage into a fresh calibrated BC phase. The parent gate influenced selection of the starting weights. The child checks the same scenario-family split after an optimizer update. This tests a warm start on an existing validation design.

## Ubuntu observations

| Check | Result |
| --- | --- |
| Original branch with an effective parent | Expected regression failure at the first stage assertion. The branch started at `bc` and the test expected `calibration`. Exit 1 in 0.551 s. [Log](red.log) |
| Restart, ordinary branch and checkpoint tests | 13 passed, exit 0 in 1.048 s. The positive-path fixture exercised branch preparation and single-Astra calibration. It committed one synthetic optimizer update using one training decision and then measured one held-out decision. Its own BC gate failed and remained false on resume. [Log](unit.log) |
| Item-10 real inputs | Verified the three copied models tensor by tensor and all 156 retained shards against the published hashes. Corpus and coverage match the original eligible jobs. All three child states start at `calibration`, `effective=false`, batch/version 0 and an empty Adam state. The inspection stops before the phase runs. [Results](real_inputs.json) · [Inspection](inspect_inputs.py) · [Parent inventory](../bc_ordinary_v6_20261103/metadata/artifacts.json) |

| Format | Teacher games | DAgger shards | Train / validation scenario families in shard headers | Matched / total teacher choices |
| --- | ---: | ---: | ---: | ---: |
| Duel | 56 | 4 | 25 / 6 | 5,533 / 6,128 |
| FFA | 48 | 0 | 35 / 4 | 8,278 / 9,133 |
| Team | 48 | 0 | 35 / 13 | 11,034 / 11,836 |

The input check reads the first record from each original single-game shard and checks its scenario partition, teacher profile, row schema and candidate version. Train and validation family sets are disjoint within each format. The inherited trainer state references four duel DAgger corrections. Their four unreferenced policy-rollout siblings stay outside the child input pool.

## Reproduction

Each archive was created with `git archive`, transferred by `scp`, checked by SHA256 and extracted in its own directory under `/home/tongshu/acceptance` on cpuServer. The first two archives used `--format=tar.gz --output=ARCHIVE COMMIT -- . ':(exclude)verification' ':(exclude)runs' ':(exclude)delivery'`. The inspection archive selected the two paths in the last command below.

| Directory | Commit | Archive SHA256 |
| --- | --- | --- |
| `bc_branch_restart_red_20261104` | `16b33b3b9baf5ac05ed0e141f284d83ab2b17b8a` | `8cd18b9f257fbc3bcb1124c0ecf44c2dbb4b71647d90a1ae4b7f6f101d42b27c` |
| `bc_branch_restart_green_20261104` | `70bc3e2953c01aabc8dd0efe80c44e809df0e20a` | `ffe5ebc25bc630b20348c103f4e14054872da3f577e268e6d3278b476a145585` |
| `bc_branch_restart_inputs_20261104` | `f78ca113b1152ca402d1debdf9e776fbb43e135d` | `e4316ee2dc0b3aeae93c40822db0bf5a63916cf040fa1a452dfd3009b7ec8fa0` |

The unit fixtures use the existing synthetic engine rules. Both source directories link `.extension` and `data/rules` from `bc_v6_readiness_20261103`. The real input run uses its original format checkpoints, rule digest `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`, extension `63b1c119670d4d0981925fafef4f781ab274f05fb0aa2fedafc8b24dfd503059` and parent manifest `32adc2420926f9dc9e2f88a5c2a4e35956d486f121dd94b970485b1f3244a9be`. The host ran Python 3.12.3 and PyTorch 2.9.1+cpu. Every command used one thread per numerical library.

```sh
export PYTHONPATH=.extension:.:vendor/arena OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
py=/home/tongshu/venv/bin/python
cd /home/tongshu/acceptance/bc_branch_restart_red_20261104
"$py" -B -m unittest -v tests.v5.test_branch_restart_bc.BranchRestartBCTests.test_child_calibrates_trains_and_rechecks_its_own_gate
cd ../bc_branch_restart_green_20261104
"$py" -B -m unittest -v tests.v5.test_branch_restart_bc tests.v5.test_checkpoint_ops tests.v5.test_branch_teacher_evidence
"$py" -B ../bc_branch_restart_inputs_20261104/verification/bc_branch_restart_20261104/inspect_inputs.py \
    ../bc_branch_restart_inputs_20261104/verification/bc_ordinary_v6_20261103/metadata/artifacts.json
```

L2 still requires the live child BC gates, PPO, resume, full evaluation and audited export within the bounded profile.
