# Frozen-batch BC learning curve and duplicate-read cost

Ubuntu diagnostic, 2026-11-02. Ordinary BC readiness remains **FAIL**. No production learning, candidate, gate or engine code changes in this experiment.

## Identity and procedure

- Curve source: `27d2b4b99822fc3950bdcf85f9f13082b1a24a58`, extracted archive at `/home/tongshu/acceptance/bc_learning_curve_rules_20261102`.
- Read-cost source: `b254c4fa6c7f4106714b96f239260e3ee648a507`, extracted at `/home/tongshu/acceptance/bc_read_cost_20261102`.
- Frozen parent: `/home/tongshu/acceptance/team_bc_readiness_20261102/runs/team_bc`, team2v2 v3. Checkpoint SHA256 `ffb554ca152ac93e3602bd45c98841238ef7ee59640b5bf7fb4ba64ba8148a97`, verified unchanged after execution in `checkpoint.sha256`.
- Rules: `data/rules` symlink to `/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules`; training rules SHA256 `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`. Parent identities and collection evidence remain in `verification/team_bc_readiness_20261102/REPORT.md`.
- Original objective/window sampler, restored Adam/Python/Torch RNG, one CPU thread, exact 2048 training / 1024 validation reads, seeds 20261103 / 20261101. No new games, resampling, checkpoint writes, model selection or gate overrides.
- Predeclared cap: 600 additional updates / 900 seconds, external 1080 seconds. Measurements at 0/50/150/300/600. Completed 600 updates, 60 epochs, 140,256 decision visits, all 37 prepared windows visited, 671.202 seconds including intermediate and final evaluation (excluding loading and initial measurement); exit 0, not interrupted.
- Initial attempt in `/home/tongshu/acceptance/bc_learning_curve_20261102` lacked the rules symlink. Existing schema validation rejected the checkpoint before training; exit 1 and traceback retained in `missing_rules/`. Environment was corrected in a fresh directory; no guard was bypassed.

From the corresponding archive roots, with `PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1`:

```sh
timeout --signal=TERM --kill-after=10 1080 /home/tongshu/venv/bin/python -u tests/diagnose_bc_learning_curve.py --run /home/tongshu/acceptance/team_bc_readiness_20261102/runs/team_bc --format team2v2 --output curve.json --updates 600 --seconds 900 >curve.log 2>curve.err
timeout --signal=TERM --kill-after=10 180 /home/tongshu/venv/bin/python -u tests/diagnose_bc_read_cost.py --run /home/tongshu/acceptance/team_bc_readiness_20261102/runs/team_bc --format team2v2 --output reads.json >reads.log 2>reads.err
```

Both corrected commands exit 0 with empty stderr. The read diagnostic ran after fitting ended. Raw JSON, logs and exit files accompany this report.

## Learning curve

Accuracy percentages; denominators stay fixed (train recruit 98, attack 339, move 1382; validation recruit 59, attack 216, move 584). Initial counts reproduce the preceding committed-batch audit exactly.

| Additional updates | Train recruit | Train attack | Train move | Validation recruit | Validation attack | Validation move |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 24.49 | 25.37 | 56.66 | 18.64 | 13.89 | 52.91 |
| 50 | 43.88 | 35.99 | 58.32 | 20.34 | 24.07 | 51.54 |
| 150 | 44.90 | 30.68 | 64.98 | 25.42 | 25.00 | 55.82 |
| 300 | 53.06 | 48.38 | 67.51 | 25.42 | 34.26 | 50.68 |
| 600 | 71.43 | 77.58 | 81.55 | 40.68 | 37.04 | 47.43 |

At 600 updates, held-out overall accuracy is 49.25%; CE is 2.78427 versus uniform 3.54499, still below the unchanged 0.85 ratio but worse than initial CE 2.06949. Attack clears 35% at this fixed final point; recruit remains below 60%. Training recruit type/slot matches are 77/98 and 88/98, versus validation 32/59 and 46/59. Correct action kind is 59/59 on validation recruits, so the remaining recruit mistakes concern type/placement ranking.

This establishes substantial underoptimization in the original 120-update checkpoint and a remaining generalization gap. It does not prove that still more updates, balancing or a larger model would fix recruitment. Movement and CE deterioration also rule out adopting a simple epoch increase as an established all-class improvement. The frozen corpus remains 24/48 required games; no ordinary readiness, all-format loop or strength pass is claimed. The diagnostic copy's weights were discarded.

## Duplicate-read cost

`learn()` fully reads the training shards only to test non-emptiness, then `finish_train()` reads them again using its actual training seed. A single sequential reproduction on the same frozen 24-shard pool measures:

| Existing read | Seed | Returned rows | Decoded families | Compressed bytes | Seconds |
| --- | --- | --- | --- | --- | --- |
| Preflight, discarded | 19 | 2048 | 13 | 68,166,646 | 11.904 |
| Training batch | 20261103 | 2048 | 12 | 67,943,528 | 11.568 |

The first read is discarded before the second, as in production. These are individual warm-host observations, not a full-run speedup or repeated benchmark. They identify concrete redundant work; removing the preflight must preserve empty-batch handling, actual sampling seeds/byte limits, checkpoint identity and resume semantics. No such production repair is included here.

Next: eliminate that measured duplicate at its owning BC boundary with regression coverage, and diagnose recruit type/placement generalization before further collection or feature tuning. All unresolved blocker acceptance remains open.
