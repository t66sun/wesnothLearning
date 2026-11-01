# Frozen BC error decomposition

Source: `6a8fa46` on Ubuntu cpuServer. Command, in the fresh source archive
`/home/tongshu/acceptance/bc_fit_parts_20261102`:

```sh
PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 /home/tongshu/venv/bin/python \
  tests/diagnose_bc_parts.py \
  --run /home/tongshu/acceptance/bc_root_20261101_readiness/runs/bc_readiness \
  --output parts.json > parts.log 2> parts.err
```

Exit 0; stderr empty. `parts.json` records checkpoint SHA-256 identities and full
counts. No weights, frozen inputs or experiment state were changed. Last committed
versions are duel 10, ffa4 5 and team2v2 3. Reads reproduce each checkpoint's final
2048-row training batch and its fixed up-to-1024-row validation batch. Every
train/validation per-kind sample and correct count equals the previous
`verification/bc_root_20261101/readiness/committed_fit.json` result.

| Format | Train recruit exact | Validation recruit exact / type / slot | Train attack exact | Validation attack exact / within-kind best |
| --- | --- | --- | --- | --- |
| duel | 238/345 | 65 / 79 / 108 of 127 | 374/556 | 69 / 80 of 200 |
| ffa4 | 75/207 | 32 / 47 / 59 of 78 | 212/583 | 127 / 181 of 452 |
| team2v2 | 28/113 | 9 / 27 / 25 of 59 | 70/335 | 28 / 63 of 149 |

Type/slot counts require a recruit prediction; within-kind best selects only
among candidates of the label's action kind. Attack position components here
also require an attack prediction, unlike some older marginal metrics. They
are diagnostics, not alternative gate definitions. Exact gates stay unchanged.

Expected class loss mass under the actual teacher-only equal-family/equal-window
sampler:

| Format | Recruit | Attack | Move | End turn |
| --- | --- | --- | --- | --- |
| duel | 18.86% | 27.64% | 36.98% | 16.52% |
| ffa4 | 9.07% | 27.18% | 45.44% | 18.31% |
| team2v2 | 5.23% | 15.74% | 64.49% | 14.54% |

These are row weights, including one-candidate rows whose policy CE is zero;
they are not measured gradient norms. The normal sampler has not regressed to
decision-count-biased window selection. The larger-format training fit leaves
both insufficient optimization and difficult representation plausible. The
weight imbalance motivates a bounded matched-sampling ablation, not a production
change by itself.

The frozen schedule/job logs identify a separate corpus limitation. At the last
committed team2v2 batch, the 24 completed teacher games split into 19 train and 5
validation games. Focal training factions are Knalgan Alliance 4, Drakes 4,
Northerners 5, Rebels 3 and Loyalists 3: **zero Undead training games**. Validation
has Drakes 2, Undead 1 and Knalgan Alliance 2. Its 59 recruit labels include 19
Undead recruits. The eight subsequently completed games, which were not part of
this committed batch, still add no Undead training game (their Undead game 26
is validation). This is derived from the archived schedules, phase/status and
focal seat, using the unchanged SHA-256 scenario partition. It does not justify
moving validation games into training or changing the partition rule.

All ordinary gates remain failed. No new games, full teacher-strength panel,
PPO, final evaluation or export were run by this decomposition.
