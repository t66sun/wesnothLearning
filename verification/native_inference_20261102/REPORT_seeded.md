# Seeded native inference acceptance

2026-11-02: **C1 PASS**. This is the current acceptance result. `REPORT.md` retains the initial unseeded timing observations; `RUNTIME.md` explains why their early C1 conclusion was insufficient for strict paired acceptance. Neither historical record was rewritten.

## Frozen environment and workload

Baseline source `01b5170fdce9ae3eb2a122c4f3123ec65ec9795c` and optimized source `5b90f02f0576b4f8d4a0834459dd9e793fcb6174` were extracted from their original git archives into new Ubuntu directories `/home/tongshu/acceptance/native_inference_profile_seeded_20261102` and `native_inference_sparse_seeded_20261102`. Production code is the same as the already-tested sparse linear/scorer repair.

Both trees compile the existing entropy shim exactly as setup.sh specifies, using GCC 13.3.0. Library SHA-256: `f12d763303445aa437de06d0dba129dc923e3d81fd1fc82d72b8e331916480cf`; source SHA-256: `707dd06bf27494a7c5b17631486a14e71b16d7949eec2c5845c811259af80bd7`. Native executable SHA-256: `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`; rules SHA-256: `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`. Runtime/host snapshots and complete export identities accompany each panel. The two `policy_export.json` files compare byte-identical (`cmp` exit 0), including each format's weight hash.

The unchanged `verification/candidate_work_budget_20261031/check.py` ran baseline then optimized, without concurrent training/inference tests. `native_timing_seeded.sh` records the exact command, environment and 1800 s outer limit for each panel. Both exited 0 naturally. Source/evidence transfers occurred during the panel; host snapshots are retained. Each panel played the same six games: seeds 20261101/20261102, three formats, seed-0 exported models, fixed 21x15 dense map, 20-turn cap, unchanged one-second native timeout and 37-candidate/12,000-work limits. Every format reached ten midgame decisions, so the existing 30-turn fallback was not used.

## Timing

| Metric | Baseline duel / ffa4 / team2v2 | Optimized duel / ffa4 / team2v2 |
| --- | --- | --- |
| Scoring p95, ms (limit 400) | 243 / 276 / 251 | **122 / 133 / 114** |
| Generation p95, ms (limit 250) | 26 / 50 / 17 | 28 / 50 / 18 |
| Generation max, ms (limit 500) | 29 / 64 / 29 | 29 / 62 / 29 |
| Evaluation RETURN max, ms (limit <800) | 78 / 326 / 529 | 65 / 179 / 386 |
| Execution RETURN max, ms (separately reported) | 566 / 569 / 357 | 419 / 419 / 207 |
| Midgame decisions | 21 / 968 / 227 | 21 / 968 / 227 |
| Maximum candidates | 37 / 37 / 37 | 37 / 37 / 37 |
| Maximum charged work | 5811 / 11715 / 7967 | 5811 / 11715 / 7967 |
| Faulted games / over-budget decisions | 0 / 0 / 0 | 0 / 0 / 0 |

Total panel time changes from **467.06 s to 257.46 s**, a **44.9% reduction** on this paired workload. Both ffa4 games end at turn 20; the four duel/team games end by leader/team elimination. Summary-level `truncated` counts are candidate-generation cuts, not turn-limited game counts. The unchanged baseline also passes the idle-host timing gates; earlier overlapping-load failures remain historical evidence.

## Exact behavior comparison

`tests/compare_native_inference.py`, source `1322c8c4e3e578da574eb3cd15e1265746d9b6a7`, compares every event and payload, including snapshots, observations, candidates, chosen actions, value/log-probability, memory writes, rewards and outcomes. It removes only `RETURN.data.elapsed_ms` and the four elapsed-duration fields under `LEARN.data.timing`; work/call/cut counters remain compared.

The first comparison reported a difference before any action in four-player games. Inspection traced it to `runtime.lua`: initial `METRIC` and terminal `BOOTSTRAP` reports are emitted through `pairs(config.learning)`. Their per-side order is unspecified. The helper now canonicalizes only contiguous batches of these independent reports by side/turn/event; it retains every report and all gameplay order. No tolerance or gate was relaxed, and no game was rerun for this logging-order correction. The original comparison remains in `comparison_initial/`.

All **six event streams, 7,248 events per implementation**, match exactly after this normalization. Per-game counts are 326, 404, 2462, 2498, 963 and 595; each normalized SHA-256 pair matches in `comparison/seeded_compare.json`. As a negative control, the same helper rejects all six earlier unseeded pairs at real `LEARN` differences, exit 1 (`comparison/unseeded_compare.json`).

From `/home/tongshu/acceptance/native_inference_compare_reports_20261102`:

```sh
/home/tongshu/venv/bin/python tests/compare_native_inference.py \
  --before /home/tongshu/acceptance/native_inference_profile_seeded_20261102/native/games \
  --after /home/tongshu/acceptance/native_inference_sparse_seeded_20261102/native/games \
  --output seeded_compare.json
```

Exit 0. The negative-control command uses the original unseeded directories and `--output unseeded_compare.json`, exit 1 as expected. Both were executed only after native timing completed.

## Reused evidence and remaining scope

The production Lua SHA-256 is unchanged from the 35 passing Ubuntu tests and three trained-model exact-output comparisons in the initial report. Reuse those results: the new instruction-budget test fails at 90.92 M instructions before the repair and passes under the predeclared 70 M bound after; Python/Lua <=1e-5 parity covers recurrent replay, 33-turn memory overflow, and 128-entity/candidate stress. Fixed-observation replay costs fall 55%-62%. No new training assertions, exception wrappers, model changes or candidate reductions were introduced.

C1 is closed. This compact-map seeded performance panel does not establish arbitrary-map latency, BC readiness, teacher strength, native rule equivalence, selected-checkpoint final evaluation or the all-format ordinary training loop. Blockers 5, 9, 10 and 11 remain open. Their gates are unchanged.
