# BC gate scenario coverage — evidence for D9

**Date:** 2026-10-26
**Scope:** quantify how many distinct scenarios stand behind the BC gate verdict of run `v5_lite30h_20261025`, and confirm the gate artifact reports none of it. Read-only against the frozen run; no game played, no optimizer step, no rewrite of any historical artifact.
**Related:** [`../ppo_rootcause_20261026/REPORT.md`](../ppo_rootcause_20261026/REPORT.md) (finding F6), `docs/ppo_refactor_plan.md` R4, `docs/architecture.md` D9.

## Identity

- Run directory: `/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/runs/v5_lite30h_20261025`, the complete 30 h run (duel 470 / ffa4 213 / team2v2 136 versions).
- Code tree the probe imports: `/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source`, the frozen training source (`822082d6…` per the run record). `learning/rowpack.py` there is identical to master's (sha256 recorded in the 2026-10-26 PPO report's identity table).
- Inputs read: `<run>/<format>/data/teacher-*.jsonl.gz` only. `bc_gate.json`, `state.json`, `jobs.jsonl` and every checkpoint were opened read-only and not modified.
- Probe: `k_gate_scope.py` in this directory (80 lines), copied to `cpuServer:/home/tongshu/myDev/wesnothLearning/diag_ppo_20261026/`.

## Commands

All run on `cpuServer`, from the frozen source tree, single-threaded BLAS.

```sh
cd /home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source
export WL_SOURCE=$PWD WL_RUN=$PWD/runs/v5_lite30h_20261025 OMP_NUM_THREADS=1
PY=/home/tongshu/venv/bin/python
D=/home/tongshu/myDev/wesnothLearning/diag_ppo_20261026
```

| # | command | wall | exit |
|---|---|---|---|
| 1 | `timeout 240 $PY $D/k_gate_scope.py --format duel` | 59.8 s | 0 |
| 2 | `timeout 150 $PY $D/k_gate_scope.py --format ffa4 --maxfiles 40` | ~28 s | 0 |
| 3 | `timeout 150 $PY $D/k_gate_scope.py --format team2v2 --maxfiles 40` | ~28 s | 0 |
| 4 | `timeout 300 $PY $D/k_gate_scope.py --format ffa4` (all 608 shards) | 300 s | aborted (killed, printed nothing) |
| 5 | `timeout 300 $PY $D/k_gate_scope.py --format team2v2` (all 400 shards) | 300 s | aborted (killed, printed nothing) |
| 6 | `sh run.sh` (this directory's script, reproducing 1–3) | 117 s | 0 |

Commands 4 and 5 are reported as **not run to completion**, not as passing: each shard costs ≈0.2 s (duel: 300 shards in 59.8 s), so a full ffa4/team2v2 scan needs ≈2 and ≈1.5 min beyond the budget granted per command; both were re-run bounded to the first 40 shards (commands 2–3). Nothing failed silently.

## Results

Duel, **all 300 shards** (complete corpus):

```text
shards 300  games 300  distinct families 300  distinct scenarios 4
split counts (per game) {'train': 246, 'validation': 54}
games per scenario [(50, 3), (150, 1)]
150  map_sha256 654da578da1aa8499f0c1c7f7735c59cfe13737382ebd946d3e021509e998cc4
 50  map_sha256 36e9ccd11e045e27544b5319ee8edfce7c795e27efdc075f53d68eab893dead8
 50  map_sha256 e3266941853e6dbb043ea9995238959af711413a8f799acc46af7923e5e8fdc3
 50  map_sha256 5f2c6843555ecbe973d2476dbb9dd85e71699f15e7dcb52ad5b8ebf5b0743bbe
```

ffa4, **first 40 of 608 shards** (sample; 40 games):

```text
shards 40  games 40  distinct families 40  distinct scenarios 3
split counts (per game) {'train': 31, 'validation': 9}
games per scenario [(10, 2), (20, 1)]
20  map_sha256 a9d30fee2ce0083e56b43230979d43bce0f3c2a596976ea7704d70de15805406
10  map_sha256 c21f9257647f99ac07b2152d7679f72ebce2ef43bf00cb444f235a35c6ae3e90
10  map_sha256 46a2bc39ca9818605cf3a9a489083d789d945ca08d0b9fa26a229857922db8a6
```

team2v2, **first 40 of 400 shards** (sample; 40 games):

```text
shards 40  games 40  distinct families 40  distinct scenarios 3
split counts (per game) {'train': 36, 'validation': 4}
games per scenario [(10, 2), (20, 1)]
20  map_sha256 a9d30fee2ce0083e56b43230979d43bce0f3c2a596976ea7704d70de15805406
10  map_sha256 c21f9257647f99ac07b2152d7679f72ebce2ef43bf00cb444f235a35c6ae3e90
10  map_sha256 46a2bc39ca9818605cf3a9a489083d789d945ca08d0b9fa26a229857922db8a6
```

`scenario_key` = (format, `map_sha256`, `factions`, `teams`). `factions` and `teams` are `null` on every lite teacher row, so the key reduces to board identity for this corpus.

## What this proves

1. **The BC gate's verdict carries no scenario count.** `bc_gate.json` for all three formats exposes exactly `imitation`, `coverage`, `corpus`, `opening`, `passed`; `corpus` reports games (`300/300`, `608/600`, `400/400`) and `imitation`/`coverage` report per-kind decision denominators (duel recruit 240/248, ffa4 recruit 90/119, team2v2 recruit 40/43, attack 126/159). No field states how many distinct boards or families those games cover. **Proven.**
2. **Duel's 99.19 % imitation rests on 4 deterministic boards**, one of which supplies 150 of 300 games. Every one of the 300 games has a distinct `game_family` because the seed is hashed into the family (`learning/maps.py`), so the corpus *looks* like 300 independent units and is 4 units. **Proven** for duel (complete corpus).
3. **The same pattern holds in the other two formats in the sampled prefix**: 3 boards, 20/10/10 game split, again 40 distinct families for 40 games. **Supported, not complete** — 40 of 608 (ffa4) and 40 of 400 (team2v2) shards were scanned.
4. The boards shared between ffa4 and team2v2 (`a9d30fee…`, `c21f9257…`, `46a2bc39…`) match the documented FFA/2v2 map pool (Clash, Isar's Cross, Arena), so the small board count is the configured pool, not a data-collection accident inside the gate. **Proven** by the identical hashes across formats plus `learning/maps.py SPLITS`.

## What this does not prove

- It does not measure the *sampled decision* distribution of the gate: the gate reads `read_shards(..., limit=bc_records)` with a rotating version-dependent seed (`learning/experiment.py finish_train`), and that sampling was not re-executed. Board counts of the corpus bound the gate from above, not exactly.
- It says nothing about win rate. A 4-board corpus is a diversity statement, not a strength statement.
- Aborted commands 4–5 mean ffa4/team2v2 board counts are lower bounds from a 40-shard prefix, not corpus totals; the sampler draw may exclude some prefix boards just as it may exclude others.

## Reuse and supersession

- Supersedes nothing. `verification/ppo_rootcause_20261026/REPORT.md` stays as recorded; this directory adds the follow-up probe it did not include.
- The earlier report's F6 statement ("evaluation measures in-distribution imitation") is unchanged; this report only replaces the unmeasured part ("no scenario count reported") with the measured corpus shape.
- Does not re-open: input contract, forward paths, reward/GAE wiring, KL accounting — all previously settled with their own evidence.

## Resources

- 3 successful probe runs, ≈116 s CPU total; 2 aborted runs, 600 s wall spent; ≤2 GiB RSS each (gzip line streaming, one shard at a time).
- Server writes: only the probe file inside `diag_ppo_20261026/`. No writes to the frozen tree, the run directory, the environment or any checkpoint.

## Gate

- No runtime change, no test added, no gate relaxed. `TEST.md` stays untouched: `test_gate_reports_distinct_scenarios` is *proposed* in `docs/ppo_refactor_plan.md` R4 and remains unwritten until R4 is implemented.

## Limits

- One run, one frozen source, three formats, lite engine only.
- Board identity is the only varying scenario dimension available in these rows; faction/team variation of the corpus could not be counted because the fields are null on lite teacher rows.
- No historical `bc_gate.json`, `validation/*.json` or selection record was recomputed or rewritten.
