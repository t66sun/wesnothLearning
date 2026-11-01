# BC fitting diagnosis: no production objective or schema change accepted

The current candidate coverage repair remains valid. Ordinary BC still fails:
the larger formats underfit recruit/attack even on their training rows, and the
short team corpus has no Undead training games. The two bounded alternatives
below do not justify a production change. Keep item 10/L2 open.

## Completed evidence

- [Decomposition](DECOMPOSITION.md): source
  `6a8fa465d13abd89942c9cb48927d9004c06610c`, all three frozen final checkpoints;
  exact reproduction of previous train/held-out per-kind sample/correct counts.
- [Class balance](BALANCE.md): source `5298e5293da1fc00e52a83ef863392b7a91e21bc`,
  two matched 88-step team arms. Recruit/attack improve modestly at substantial
  move cost. Both unchanged imitation gates fail.
- Explicit recruit context: successful source
  `27bd82ab0db99cbc755c3877ce5d441a80a733da`, fresh Ubuntu archive
  `/home/tongshu/acceptance/bc_context_result_20261102`. Command:

```sh
PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 timeout 660 \
  /home/tongshu/venv/bin/python -u tests/diagnose_bc_recruit_context.py \
  --run /home/tongshu/acceptance/bc_root_20261101_readiness/runs/bc_readiness \
  --format team2v2 --output context.json > context.log 2> context.err
```

The context probe uses only recorded legal entities: nonleader own units of the
candidate recruit type, and distance to the nearest currently visible enemy.
It adds two zero-initialized scorer input columns with zero Adam moments for
those columns; all other weights and moments are restored. No production schema
or stored row changes. No referee snapshot or hidden unit information is used.

The initial decomposed validation result is identical to the original checkpoint
(including examples/margins); sampled-window cursors exactly equal the ordinary
baseline. All 3,072 input rows have the full own-unit count represented in their
entities. Eight epochs complete: 88 updates, 18,912 decisions, 88.03 training
seconds, no interruption, exit 0 and empty stderr. Both arms use the predeclared
600-second training cap; no deadline is extended.

| Context comparison | Ordinary continuation | Explicit recruit context |
| --- | --- | --- |
| Train recruit | 35/113 | 34/113 |
| Train attack | 101/335 | 101/335 |
| Validation recruit | 17/59 | 9/59 |
| Validation attack | 39/149 | 40/149 |
| Validation move | 336/684 | 334/684 |
| Validation overall | 47.18% | 46.19% |
| Validation CE | 1.8523 | 1.8596 |
| Imitation gate | FAIL | FAIL |

This fixed-budget probe does not establish that more explicit features can never
help. It fails to support adopting these two features now. The first attempt,
source `4bc039fb473201464327c632a3f911ac59891853`, failed while serializing a
NumPy integer after fitting. Its traceback and exit 1 remain in `context_initial/`.
The only correction was converting that diagnostic count to a Python integer;
the experiment was repeated in a new directory with unchanged parameters because
the first result was not saved. No failed result is relabelled as passing.

## Remaining work and limits

The 24-game committed team corpus has 19 training and 5 validation games, but
zero Undead training games; 19 of its 59 validation recruit labels are Undead.
Its bounded last training read uses only 9 of the 19 available training families.
FFA uses 22 of 33, duel 38 of 38. The retained training-row quotas and admission
budgets should be examined before another objective/architecture experiment.
These are separate observed exposure limits; neither alone proves all imitation
failures, and the unchanged ordinary gates remain necessary.

No new games or collection, original-run resume, PPO, full teacher-strength panel,
final evaluation, deployment or exported model was produced. Probe models were
discarded. Windows ran only file/JSON summaries and Git checks; all fitting and
model evaluation ran on Ubuntu. This is diagnostic evidence, not readiness,
convergence or playing-strength acceptance.
