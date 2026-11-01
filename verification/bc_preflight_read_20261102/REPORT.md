# Reuse the actual BC batch for its nonempty check

Ubuntu acceptance, 2026-11-02. **PASS: 29 affected checks**, exit 0, 5.536 seconds. No games or training experiment launched for this repair; learner unit tests exercise synthetic updates.

## Behavior

The previous `learn()` decoded a full training pool with default seed 19 only to test non-emptiness, discarded it, and immediately decoded the actual batch again in `finish_train()`. The frozen team diagnosis measured those reads at 11.904 and 11.568 seconds respectively (`verification/bc_learning_curve_20261102/REPORT.md`).

`read_bc_batch()` now owns the existing pool composition, versioned seed, row limit and read statistics. Fresh BC uses that actual batch for both the nonempty check and update. The transient tuple is released immediately after the update attempt; it is never checkpointed or retained across collection. An empty actual batch advances only the batch counter and creates no pending update. Resuming calls `finish_train()` without prepared rows, reconstructs the batch and runs the unchanged content-identity check. PPO keeps its existing policy preflight and training/rehearsal reads.

The empty check now deliberately uses the actual teacher/DAgger/human training pool and training seed, rather than a separate teacher/human read with default seed 19. The actual optimizer input selection, byte/row limits, validation reads, objective, gates and checkpoint content contract are unchanged. No production exception handler or assertion was added.

This removes one full read per fresh nonempty BC batch. The 11.904-second prior measurement identifies the eliminated work on that frozen pool; no end-to-end training speedup is measured and no ordinary BC/strength acceptance is inferred.

## Sources and commands

- Regression-only baseline: `3a16ab010319b3870843313197965f7755b0bb74`, `/home/tongshu/acceptance/bc_preflight_red_20261102`.
- Implementation: `6df5fa4e8701d2bcb5243b92b8ec02e7767d5415`, `/home/tongshu/acceptance/bc_preflight_fixed_20261102`.
- Each tree was shipped with `git archive`; `data/rules` points to the existing frozen server rules. Python `/home/tongshu/venv/bin/python`, `PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1`.

Baseline:

```sh
python -m unittest tests.v5.test_bc_preflight_read.BcPreflightReadTests -v
```

Exit 1: the new actual-batch test fails because three reads occur instead of two. The empty-pool test reports the old read's missing explicit training seed (`KeyError: seed`). Both raw failures are preserved in `baseline.log`.

Fixed:

```sh
python -m unittest tests.v5.test_bc_preflight_read tests.test_validation_cadence tests.v5.test_training_failure_fixes tests.v5.test_bc_cancel_rng tests.v5.test_ppo_resume_counters tests.v5.test_rollout_content_identity -v
```

29/29 pass; `checks.log` and `checks.exit` retain the complete output. New checks cover one training plus one validation read, actual seed/row cap/full pool, fresh reads on pending resume, no premature version increment, and empty-batch handling. Existing checks cover phase transitions, validation cadence, BC cancellation/RNG continuation, real PPO checkpoint counters and content mutation rejection.

The synthetic read-count regression is the reversible assertion for this change; the frozen-data timing measurement is reused rather than repeated as a full training benchmark. Recruitment generalization and remaining blockers stay open.
