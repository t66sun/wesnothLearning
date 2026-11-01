# Candidate retention under `work-12000-v7`, measured on the frozen bounded-loop decisions

Date: 2026-11-01. Acceptance host: Ubuntu (`cpuServer`), python `/home/tongshu/venv/bin/python`.

## What was measured

`verification/teacher_coverage_20261101/REPORT.md` separated the two failures the bounded-loop BC gate
used to fold together and corrected the candidate generator where the measured reason codes named a
retention defect. Under `work-12000-v6` duel retention reached 2205/2602, but recruit `type_absent`
(87) and the combat quota were still the dominant losses, and every format stayed below the gate's
per-class threshold. This report measures one further retention change and nothing else.

The change is a contract bump to `work-12000-v7` with two knobs:

1. **Recruit probe budget 64 → 192.** Recruit generation walks the affordable types and, per type, the
   castles nearest to the enemy; the earlier per-type cursor stopped after eight castles, so with a
   64-probe budget the later types were never probed. `recruit:type_absent` was the largest single
   reason code in all three formats under `v6`.
2. **Per-class reserve of the 36 actionable slots 16/12/8 → 28/6/2 (combat/recruit/move).** The
   generator's ceiling experiment (selection limits lifted to 999) showed attack retention rising from
   0.7103 to 0.8632 on duel while recruit stayed at 0.7814, i.e. attack was quota-bound and recruit was
   generation-bound; the reserve was re-cut accordingly. Move keeps two first-pass slots because the
   ranked refill already gives every mobile unit its best full move, and
   `tests/v5/test_candidate_pool_budget.py::test_every_unit_with_moves_keeps_one_full_move_from_its_hex`
   rejects any split that drops move below two.

No threshold, teacher, seed, gate, panel or training schedule was changed. No collection game was
played: both sides of the comparison replay the frozen schedules of the committed bounded-loop run.

## Source identities

| side | branch commit | shipped tree | replay output |
|---|---|---|---|
| before (`work-12000-v6`) | `0e6ca84` | `tree_prc` at `a5166b1` minus the Lua/features hunks | `verification/teacher_coverage_20261101/out_after` |
| after (`work-12000-v7`) | `a5166b1` | `/home/tongshu/acceptance/teacher_coverage_20261101/tree_prc` | `verification/teacher_coverage_20261101/out_prc` |

`git diff 0e6ca84 a5166b1 -- lua learning` is the entire behaviour change; every other hunk in that
range is a test literal or this documentation.

## Method

`verification/teacher_coverage_20261101/replay.py` reads the recorded job ids of
`/home/tongshu/acceptance/bounded_loop_20261101/runs/bounded_loop/<format>/jobs.jsonl`, loads the frozen
`bc-batch-*.json` schedules, keeps only the jobs the committed gate covered (all 24 duel games, the
first 8 ffa4 and the first 8 team2v2 games — the smallest id-sorted prefix that reproduces the committed
denominators), forces `engine='lite'`, drops `shard`, and runs `learning.sample.collect` followed by
`learning.experiment.coverage_gate`. Teacher seats execute the teacher plan verbatim regardless of
`choice` (`learning/lite_host.py:180-196`), so the trajectory and every teacher intent are reproduced
exactly and only the candidate set and its matching outcome are recomputed.

Command, identical for both sides:

```
python verification/teacher_coverage_20261101/replay.py \
  --schedules /home/tongshu/acceptance/bounded_loop_20261101/runs/bounded_loop \
  --out verification/teacher_coverage_20261101/out_prc --workers 8
```

Determinism oracle: the replayed per-kind totals must equal the committed denominators — duel
2602/398/1187/687, ffa4 2423/255/1074/778, team2v2 3203/168/2248/397. All three report
`determinism: ok`.

## Gate result, before and after

| format | contract | all | recruit | move | attack | truncated |
|---|---|---|---|---|---|---|
| duel (24 games) | `v6` | 2205/2602 = 0.8474 | 311/398 = 0.7814 | 1076/1187 = 0.9065 | 488/687 = 0.7103 | 2253 |
| duel (24 games) | `v7` | **2303/2602 = 0.8851** | **349/398 = 0.8769** | 1076/1187 = 0.9065 | **548/687 = 0.7977** | **2210** |
| ffa4 (8 games) | `v6` | 1646/2423 = 0.6793 | 164/255 = 0.6431 | 720/1074 = 0.6704 | 446/778 = 0.5733 | 2290 |
| ffa4 (8 games) | `v7` | **1754/2423 = 0.7239** | **234/255 = 0.9176** | 719/1074 = 0.6695 | **485/778 = 0.6234** | **2264** |
| team2v2 (8 games) | `v6` | 1958/3203 = 0.6113 | 103/168 = 0.6131 | 1215/2248 = 0.5405 | 250/397 = 0.6297 | 2929 |
| team2v2 (8 games) | `v7` | **2035/3203 = 0.6353** | **158/168 = 0.9405** | 1215/2248 = 0.5405 | **272/397 = 0.6851** | **2889** |

The gate's own thresholds (`learning/experiment.py:128-139`) are `all ≥ 0.90` and every class `≥ 0.80`.
They are still **not met**: duel misses `all` (0.8851) and `attack` (0.7977, by 0.0023), ffa4 and
team2v2 miss all four. Per the plan's stop rule the measured ratios are recorded and no cap, threshold,
seed or schedule was raised further.

## Reason tables

Reasons are counted where coverage is counted (`learning/trajectory_buffer.py`, `learning/sample.py`)
and summed by `coverage_gate`. `move_attack:*` keys are kept separate so the attack-own share can be
recovered as `attack:* − move_attack:*`; the `attack` totals above fold both, exactly as the gate does.

### Duel, `v6` → `v7`

| reason | v6 | v7 |
|---|---|---|
| `recruit:type_absent` | 87 | 42 |
| `recruit:slot_absent` | 0 | 7 |
| `recruit:kind_absent` | 0 | 0 |
| `move:destination_absent` | 96 | 95 |
| `move:actor_absent` | 14 | 12 |
| `move:kind_absent` | 1 | 4 |
| `attack:destination_absent` | 128 | 86 |
| `attack:actor_absent` | 41 | 28 |
| `attack:kind_absent` | 14 | 12 |
| `attack:weapon_absent` | 10 | 12 |
| `attack:enemy_absent` | 6 | 1 |
| of which `move_attack:destination_absent` | 125 | 86 |
| of which `move_attack:actor_absent` | 32 | 25 |
| of which `move_attack:kind_absent` | 12 | 12 |
| of which `move_attack:weapon_absent` | 6 | 9 |
| of which `move_attack:enemy_absent` | 6 | 1 |

### ffa4, `v6` → `v7`

| reason | v6 | v7 |
|---|---|---|
| `recruit:type_absent` | 91 | 8 |
| `recruit:slot_absent` | 0 | 13 |
| `move:destination_absent` | 203 | 178 |
| `move:actor_absent` | 123 | 149 |
| `move:kind_absent` | 28 | 28 |
| `attack:destination_absent` | 153 | 121 |
| `attack:actor_absent` | 105 | 64 |
| `attack:kind_absent` | 65 | 104 |
| `attack:weapon_absent` | 5 | 4 |
| `attack:enemy_absent` | 4 | 0 |
| of which `move_attack:destination_absent` | 153 | 121 |
| of which `move_attack:actor_absent` | 105 | 64 |
| of which `move_attack:kind_absent` | 65 | 104 |
| of which `move_attack:weapon_absent` | 5 | 4 |

### team2v2, `v6` → `v7`

| reason | v6 | v7 |
|---|---|---|
| `recruit:type_absent` | 64 | 0 |
| `recruit:slot_absent` | 1 | 10 |
| `move:destination_absent` | 778 | 750 |
| `move:actor_absent` | 204 | 232 |
| `move:kind_absent` | 51 | 51 |
| `attack:destination_absent` | 66 | 51 |
| `attack:actor_absent` | 46 | 26 |
| `attack:kind_absent` | 26 | 46 |
| `attack:weapon_absent` | 6 | 1 |
| `attack:enemy_absent` | 3 | 1 |

Invariant, checked on every format and both contracts: for each kind the summed reason counts equal
that kind's `total − matched` — duel recruit 49, move 111, attack 139; ffa4 21, 355, 293; team2v2 10,
1033, 125. A `move_attack` row is counted twice by construction, once under its own name and once folded
into `attack`, exactly like the per-kind totals, so the `move_attack:*` rows above are the moving-attack
share of the `attack:*` rows, not extra misses: the attack-own share is `attack:* − move_attack:*`.

## What the reasons say

- **Recruit is fixed.** The 192-probe budget removes `recruit:type_absent` from the dominant position:
  duel 87 → 42, ffa4 91 → 8, team2v2 64 → 0. Recruit retention rises on every format
  (duel 0.7814 → 0.8769, ffa4 0.6431 → 0.9176, team2v2 0.6131 → 0.9405).
- **Attack is quota-bound, not budget-bound, and what is left is moving attack.** The reserve re-cut
  lifts duel attack 0.7103 → 0.7977 and ffa4 0.5733 → 0.6234. On duel, attack-own now loses only 6 of
  377 intents (actor 3, weapon 3) while moving attack loses 133 of 310: 86 `destination_absent`, 25
  `actor_absent`, 12 `kind_absent`, 9 `weapon_absent`. The same split holds on ffa4 (attack-own 0
  misses) and team2v2 (attack-own 1, moving attack 124), so the residual attack loss is the teacher's move-then-attack intent finding
  no candidate of that kind, not a missing attack candidate.
- **ffa4 and team2v2 are generation-bound, not selection-bound.** `attack:kind_absent` *rises* under
  `v7` (ffa4 65 → 104, team2v2 26 → 46) because the wider combat reserve now spends slots
  on combat candidates that exist, exposing the intents for which no candidate is generated at all. The
  earlier ceiling experiment (selection limits lifted to 999) showed the same signature: on ffa4 and
  team2v2 overall retention stays near 0.63–0.71 even with unlimited selection.
- **Work is still bounded.** Every decision stays under `WORK.total = 12000` by construction
  (`charge()` refuses a call that would exceed it), and `truncated` falls on duel and ffa4
  (2253 → 2210, 2290 → 2264) while falling on team2v2 too (2929 → 2889).

## Limits

- Both sides replay the same 24 duel / 8 ffa4 / 8 team2v2 frozen games; this measures retention on the
  decisions the committed gate covered, not a new sample and not generalization.
- Retention is not imitation: held-out fit decomposition (`exact`, `same_kind`, `same_actor`,
  `same_destination`, label-rank buckets) is implemented in `learning/bc.py` but is **not measured
  here**, because no gated BC run was authorized. A normal gated run after `work-12000-v7` is NOT RUN.
- `move_attack` remains the single largest unrecovered class. No cap, threshold, teacher, seed or
  training schedule was changed to attack it; the large-format generation stage that would is not part
  of this change.
- Nothing here is evidence about convergence, playing strength or acceptance. `docs/TEST.md` L2 stays
  FAIL at BC.
