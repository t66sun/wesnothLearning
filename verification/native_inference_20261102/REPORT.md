# Native inference cost acceptance

2026-11-02, Ubuntu `cpuServer`. C1 **PASS**; blockers 5, 9, 10 and 11 remain open.

## Change and root cause

The relational Lua forward pass multiplied every feature, including zeros, in every linear output and the first candidate scorer layer. Three frozen dense native observations attribute approximately 80% of sampled Lua instructions to the linear/scoring paths, with convolution taking approximately 20%. The older network implementation already used sparse inputs; the relational implementation did not.

`lua/relational.lua` now builds ascending nonzero column/value lists once per input and shares them across output rows. Only exact zeros are omitted; nonzero accumulation order, weights, architecture, candidate selection and memory semantics are unchanged. No production exception handler or assertion was added. There is no training or model change.

## Source and inputs

- Parent: `8abb6b287a7b31efcdbc4ff7139cb86b31dfd66c`.
- Baseline profiling/native source: `01b5170fdce9ae3eb2a122c4f3123ec65ec9795c`.
- Failing regression source: `70673e58ba624ce3f8aac02d9f8c282c7f4dae39`.
- Production repair and 35-check/native source: `5b90f02f0576b4f8d4a0834459dd9e793fcb6174`.
- Trained-checkpoint comparison helper: `fee9b0c62ca163f238427c6785d17f0493b31e22` (same production Lua).
- Each source was shipped with `git archive` to its own fresh `/home/tongshu/acceptance/native_inference_{profile,red,sparse,audit}_20261102` directory. Rules were linked read-only from the provisioned server data.
- Rules: `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`; candidate contract `work-12000-v8`, feature schema 5, 37 candidates and 12,000 charged work unchanged. Native executable identity is in both raw summaries.
- Replay inputs: existing `verification/bc_root_20261101/native_v8/games`, first maximum-entity decision with 37 candidates at turn >=5 per format. The profiler records exact input-file and Lua hashes. These are diagnostic inputs, not unseen strength data.

## Checks and results

| Check | Before | After |
| --- | --- | --- |
| Frozen ffa4 forward instruction regression | FAIL: 90,920,000 >= 70,000,000 | PASS below the unchanged bound |
| Affected Ubuntu suite | Regression red recorded separately | 35 tests PASS in 11.416 s |
| Same-input replay median, duel | 256.55 ms | 114.37 ms |
| Same-input replay median, ffa4 | 284.51 ms | 123.79 ms |
| Same-input replay median, team2v2 | 258.85 ms | 99.39 ms |
| Trained checkpoints, old/new Lua score/value/pending hidden/summary | Original implementation | Exact equality, max error 0 in each format |

The 35 tests include Python/Lua <=1e-5 parity at 37 candidates and two turns, 33-turn memory overflow, 128 entities/candidates, direct entity fallback, and existing learner contracts. The instruction check executes the public `forward` interface in Lua 5.4; it is independent of wall-clock load and fails when the optimization is reverted. Five timed calls follow one warmup in each replay measurement; hook profiling is a separate call outside the timed samples.

Trained weights are read from the completed ordinary BC run's immutable `last_bc.pt` files (duel/ffa4/team2v2 versions 10/5/3). Their hashes and exact-output comparisons are in `trained.jsonl`; the diagnostic writes no checkpoint or experiment state. This is one dense frozen observation per trained model with initially empty memory; the multi-turn/memory-overflow coverage comes from the separate parity tests, not from this three-observation comparison.

## Native timing

The existing `verification/candidate_work_budget_20261031/check.py` ran unmodified, baseline first and optimized second, with no concurrent training or inference tests. Both exit **0**. Initial load was zero; before/after load and process snapshots are retained. Small source/evidence transfers occurred while panels ran. The 1800 s outer ceiling for each panel did not fire. Baseline took 479.49 s; optimized took 296.03 s.

| Metric (ms except counts) | Baseline duel / ffa4 / team2v2 | Optimized duel / ffa4 / team2v2 |
| --- | --- | --- |
| Scoring p95 (limit 400) | 256 / 276 / 251 | **126 / 134 / 109** |
| Generation p95 (limit 250) | 34 / 51 / 15 | 33 / 55 / 14 |
| Generation max (limit 500) | 37 / 61 / 25 | 38 / 66 / 17 |
| Evaluation RETURN max (limit <800) | 85 / 320 / 531 | 70 / 175 / 386 |
| Execution RETURN max (reported separately) | 576 / 571 / 350 | 422 / 418 / 206 |
| Turn>=5 recorded decisions | 51 / 983 / 194 | 118 / 1069 / 205 |
| Max candidates | 37 / 37 / 37 | 37 / 37 / 37 |
| Max charged work | 7739 / 11728 / 5820 | 8743 / 11730 / 4808 |
| Faulted games | 0 / 0 / 0 | 0 / 0 / 0 |

Each panel used six games: two per format, seeds 20261101/20261102, the existing dense 21x15 map and seed-0 exported weights. Every format exceeded the ten-midgame-decision minimum at 20 turns, so neither panel invoked the existing 30-turn fallback. In each panel the two ffa4 games reached the turn cap; all four duel/team games ended by leader/team elimination. Summary-level `truncated` counts are candidate-work cuts, not game truncations.

The original implementation also passes on this idle host. Earlier overlapping-load failures remain unchanged historical evidence; the improvement is reduced inference cost and additional time margin, not proof that the old code intrinsically failed on an idle machine. Native trajectories differ between panels, so their total durations and timing percentiles are workload observations, not an exact paired speedup. The controlled same-input replays demonstrate the 55%-62% reduction. All raw game event streams and logs are retained; neither native panel measures playing strength.

## Commands

Run from each identified source tree with `/home/tongshu/venv/bin/python` and `PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1`:

```sh
python tests/profile_lua_inference.py --events verification/bc_root_20261101/native_v8/games
python -m unittest tests.v5.test_lua_inference_work -v
python -m unittest tests.v5.test_lua_inference_work tests.v5.test_learning_core -v
```

The red instruction check failed as intended; the repaired suite and both profiling commands passed. The exact sequential native invocation, timeout and environment are archived in `native_timing.sh`; raw terminal codes are `baseline/native.exit` and `optimized/native.exit`.

After both panels ended, from the audit tree:

```sh
python tests/profile_lua_inference.py \
  --events verification/bc_root_20261101/native_v8/games \
  --checkpoint-dir /home/tongshu/acceptance/bc_root_20261101_readiness/runs/bc_readiness \
  --reference /home/tongshu/acceptance/native_inference_profile_20261102/lua/relational.lua
```

Exit 0, recorded in `trained.exit`. No Windows tests were run. Local diff and source-size checks pass; the two pre-existing grandfathered oversized test files were untouched. Candidate generation/provenance was unchanged, so the existing 45-check coverage evidence is reused. BC readiness, teacher strength, native rule equivalence, selected-checkpoint final evaluation and the complete ordinary training loop are not accepted by this change.
