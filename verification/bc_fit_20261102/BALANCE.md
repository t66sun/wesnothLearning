# Matched-window BC objective comparison

Diagnostic source `5298e5293da1fc00e52a83ef863392b7a91e21bc`, Ubuntu cpuServer,
fresh archive `/home/tongshu/acceptance/bc_balance_20261102`.

```sh
PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 timeout 1300 \
  /home/tongshu/venv/bin/python -u tests/diagnose_bc_balance.py \
  --run /home/tongshu/acceptance/bc_root_20261101_readiness/runs/bc_readiness \
  --format team2v2 --output balance.json > balance.log 2> balance.err
```

Both arms start from the same frozen team2v2 v3 model, independent copies of its
Adam state and its saved Python/Torch RNG. The exact checkpoint hash is in
`balance/balance.json`. The predeclared limit is eight epochs and 600 seconds per
arm. Original gates, rows, recurrent histories, sampler, value and auxiliary
objectives remain unchanged. The experimental arm changes only exact policy CE:
equal class weight within each selected window, preserving total window weight.
Production code is unchanged.

Both complete 88 optimizer steps, 352 window visits and 18,912 decision visits;
all 41 windows appear. Their full recorded sampling cursors are equal. Baseline
training takes 89.98 seconds and the alternative 88.14 seconds. These elapsed
times are diagnostic costs, not a controlled throughput benchmark.

| Metric | Original checkpoint | Additional ordinary updates | Class-balanced alternative |
| --- | --- | --- | --- |
| Train recruit | 28/113 | 35/113 | 47/113 |
| Train attack | 70/335 | 101/335 | 116/335 |
| Train move | 816/1314 | 854/1314 | 629/1314 |
| Validation recruit | 9/59 | 17/59 | 21/59 |
| Validation attack | 28/149 | 39/149 | 47/149 |
| Validation move | 357/684 | 336/684 | 266/684 |
| Validation overall | 46.59% | 47.18% | 41.84% |
| Validation CE | See original audit | 1.8523 | 2.0145 |
| Ordinary imitation gate | FAIL | FAIL | FAIL |

This supports sensitivity to class weighting, but not adoption: the modest
recruit/attack gains accompany substantial move deterioration. Additional
ordinary optimization also improves the minority classes; weighting is not
established as their sole cause. No production loss change is accepted.

`balance.exit` records experiment exit 0 and stderr is empty. The PowerShell-fed
SSH wrapper subsequently returned 1 because its final `exit "0"` contained a
carriage return (`exit: 0\r: numeric argument required`). This occurred after
the complete JSON and experiment exit record were written. It was not a learner
failure, timeout or retry; the experiment was not rerun. Later wrappers use an
LF-only encoded script. No original checkpoints or run files were modified.
