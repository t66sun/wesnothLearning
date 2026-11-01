# Per-kind BC label coverage and held-out fit, measured on the frozen bounded-loop decisions

Date: 2026-11-01. Acceptance host: Ubuntu (`cpuServer`), python `/home/tongshu/venv/bin/python`.

## What was measured

`docs/blockers_temp.md` item 10 was unproven because one gate folded two different failures into one
verdict: whether the teacher's action survived candidate retention (label coverage) and whether the
policy ranks the candidates it did receive (imitation fit). A coverage miss produced no row at all
(`learning/data.py:190` drops `choice<0`), so nothing in the repository said which candidate
coordinate went missing, and the per-kind accuracy was computed only over the survivors.

Two changes were made and are measured here.

1. **Measurement (no decision changes).** `learning/coverage.py` is now the single Python definition
   of the intent↔candidate contract, and `learning/lite_host.py` imports it instead of keeping a
   private field table. `learning/trajectory_buffer.py` and `learning/sample.py` count every coverage
   miss under a reason code (`kind_absent`, `actor_absent`, `destination_absent`, `enemy_absent`,
   `weapon_absent`, `mode_absent`, `type_absent`, `slot_absent`) with the same `move_attack`→`attack`
   fold the per-kind totals use, so for every kind the summed reason counts equal that kind's
   `total − matched`. `learning/experiment.py` `coverage_gate` sums the reasons into the gate record.
   `learning/bc.py` `imitation_quality` additionally reports, per kind, `same_kind`, `same_actor`,
   `same_destination`, label-rank buckets (`1`, `2-3`, `4-8`, `9-16`, `17+`) and `mean_candidates`
   over the rows that survived retention.
2. **Retention repair.** `lua/candidates.lua` and `lua/candidate_selection.lua` were corrected where
   the measured reasons named a retention defect, and the contract version moved from
   `work-12000-v5` to `work-12000-v6`.

No training run, teacher, panel, gate threshold or seed was changed. No collection games were played:
both replays replay the frozen schedules of the committed bounded-loop run.

## How the numbers were produced

`verification/teacher_coverage_20261101/replay.py` reads the frozen schedules of
`/home/tongshu/acceptance/bounded_loop_20261101/runs/bounded_loop/<fmt>/schedules/bc-batch-*.json`,
keeps only jobs whose id appears in that run's `jobs.jsonl`, forces `engine='lite'`, and runs
`learning.sample.collect` followed by `learning.experiment.coverage_gate`. Teacher seats execute the
teacher plan verbatim regardless of `choice` (`learning/lite_host.py:180-196`), so the trajectory and
every teacher intent are reproduced exactly; only the candidate set and the matching outcome are
recomputed.

`determinism` compares the replayed per-kind totals with the denominators committed in that run's
`bc_gate.json`: duel `all 2602 / recruit 398 / move 1187 / attack 687`, ffa4
`2423 / 255 / 1074 / 778`, team2v2 `3203 / 168 / 2248 / 397`. The committed gate covered the first
eight id-sorted games of ffa4 and team2v2 (`corpus games 8`) and all 24 duel games, so the replay
selects exactly that prefix; a mismatch would mean the teacher or engine identity drifted.

Run directories and commits:

| run | measured code | tree on the host |
|---|---|---|
| baseline (`out/`) | `e76aea8` (`lua/`, `learning/` byte-identical to the extracted `154eea6`) | `/home/tongshu/acceptance/teacher_coverage_20261101/pr_a_154eea6` |
| repaired (`out_after/`) | `aab2a5d` (`lua/`, `learning/` byte-identical to the extracted `74713ae`) | `/home/tongshu/acceptance/teacher_coverage_20261101/pr_b_74713ae` |

Both trees were extracted from the commit named in their directory and then updated in place with the
replay script's job-subset fix. The code under measurement is therefore each branch head:
`git diff --stat 154eea6 e76aea8 -- lua learning` and `git diff --stat 74713ae aab2a5d -- lua learning`
are both empty, and the only files that differ between each extracted commit and its branch head are a
test file and the replay script.

Command, identical for both runs except `--out`:

```
python verification/teacher_coverage_20261101/replay.py \
  --schedules /home/tongshu/acceptance/bounded_loop_20261101/runs/bounded_loop \
  --out verification/teacher_coverage_20261101/out --workers 8
```

`determinism` was `ok` for all three formats in both runs, so the replay reproduces the committed
denominators exactly and the comparison below is between the same decisions.

Committed evidence: `out/gate.jsonl` and `out_after/gate.jsonl` hold the three gate objects printed by
each run, and `out/<fmt>.jsonl` / `out_after/<fmt>.jsonl` hold the per-job records (id, status, result,
per-job coverage with its reason codes, truncated) the gate was computed from. `*.throughput.jsonl`
holds the per-format wall time.

## Gate result before and after the repair

| format | run | all | recruit | move | attack | truncated |
|---|---|---|---|---|---|---|
| duel | before | 1888/2602 = 0.7256 | 151/398 = 0.3794 | 1043/1187 = 0.8787 | 364/687 = 0.5298 | 2283 |
| duel | after | 2205/2602 = 0.8474 | 311/398 = 0.7814 | 1076/1187 = 0.9065 | 488/687 = 0.7103 | 2253 |
| ffa4 | before | 1399/2423 = 0.5774 | 100/255 = 0.3922 | 743/1074 = 0.6918 | 240/778 = 0.3085 | 2281 |
| ffa4 | after | 1646/2423 = 0.6793 | 164/255 = 0.6431 | 720/1074 = 0.6704 | 446/778 = 0.5733 | 2290 |
| team2v2 | before | 1802/3203 = 0.5626 | 56/168 = 0.3333 | 1230/2248 = 0.5472 | 126/397 = 0.3174 | 2915 |
| team2v2 | after | 1958/3203 = 0.6113 | 103/168 = 0.6131 | 1215/2248 = 0.5405 | 250/397 = 0.6297 | 2929 |

The gate's own thresholds are overall ≥ 0.90 and every class ≥ 0.80. The repair does not reach them:
duel recruit (0.7814) and attack (0.7103) stay below 0.80, and ffa4 and team2v2 stay below 0.80 on
every class. On ffa4 and team2v2 the truncated count rose slightly (2281 → 2290, 2915 → 2929) and move
coverage fell slightly (0.6918 → 0.6704, 0.5472 → 0.5405): the larger per-stage caps spend work that
those formats were already short of. No cap was raised after this measurement and no threshold was
changed, so these ratios stand as the measured result.

## Reason codes before and after

Per format, counted over the decisions the gate scored. `attack:` and `move_attack:` are reported
separately by the counter and summed into the gate's `attack` class; the per-kind invariant
`sum(reasons) == total − matched` holds exactly for each of them.

duel, before: `recruit` 247 misses = `type_absent` 163, `kind_absent` 71, `slot_absent` 13;
`move` 144 = `destination_absent` 126, `actor_absent` 12, `kind_absent` 6;
`attack` 323 = `actor_absent` 126, `destination_absent` 117, `kind_absent` 76, `weapon_absent` 3,
`enemy_absent` 1, of which the `move_attack` share is `actor_absent` 117, `destination_absent` 114,
`kind_absent` 76, `weapon_absent` 2, `enemy_absent` 1 — so an immobile attack was retained 364/377
times and a moving attack 0/310 times.

duel, after: `recruit` 87 = `type_absent` 87; `move` 111 = `destination_absent` 96, `actor_absent` 14,
`kind_absent` 1; `attack` 199 = `destination_absent` 128, `actor_absent` 41, `kind_absent` 14,
`weapon_absent` 10, `enemy_absent` 6, of which `move_attack` contributes `destination_absent` 125,
`actor_absent` 32, `kind_absent` 12, `weapon_absent` 6, `enemy_absent` 6.

ffa4, before: `recruit` 155 = `type_absent` 149, `slot_absent` 6; `move` 331 =
`destination_absent` 196, `actor_absent` 119, `kind_absent` 16; `attack` 538 =
`kind_absent` 330, `actor_absent` 113, `destination_absent` 94, `weapon_absent` 1.

ffa4, after: `recruit` 91 = `type_absent` 91; `move` 354 = `destination_absent` 203,
`actor_absent` 123, `kind_absent` 28; `attack` 332 = `destination_absent` 153, `kind_absent` 105,
`actor_absent` 65, `weapon_absent` 5, `enemy_absent` 4.

team2v2, before: `recruit` 112 = `type_absent` 108, `slot_absent` 4; `move` 1018 =
`destination_absent` 775, `actor_absent` 186, `kind_absent` 57; `attack` 271 = `kind_absent` 177,
`actor_absent` 51, `destination_absent` 42, `weapon_absent` 1.

team2v2, after: `recruit` 65 = `type_absent` 64, `slot_absent` 1; `move` 1033 =
`destination_absent` 778, `actor_absent` 204, `kind_absent` 51; `attack` 147 =
`destination_absent` 66, `kind_absent` 46, `actor_absent` 26, `weapon_absent` 6, `enemy_absent` 3.

`kind_absent` for `recruit` on duel before the repair (71 of 247) and the `move_attack`-only
`kind_absent` (76 of 323) were mapping-relevant, not budget-relevant: no recruit candidate of any type
was generated, and no moving-attack candidate existed at all. Both are reported here rather than
papered over by a larger cap, and both were addressed only through generation order (see below).

## What was changed and why

Every edit below answers a reason code that accounted for at least 10% of that kind's misses.

- `recruit:type_absent` (duel 66%, ffa4 96%, team2v2 96%) and `recruit:slot_absent`: recruit slots are
  ordered by distance to the nearest enemy instead of map coordinates, and they are probed round by
  round across affordable types with a per-type castle cursor, so the probe cap cannot hide a type or
  spend itself on one type's far castles. `WORK.recruit_probes` 24 → 64.
- `attack:actor_absent` (duel 39%) and `attack:destination_absent` (36%): a unit's combat-adjacent
  destinations are probed before its position picks (categories are unchanged, only probe order), the
  combat share of the 36 actionable slots is 16 against 12 recruit and 8 move, and
  `WORK.move_probes` 32 → 48.
- `move:destination_absent` (duel 87%): `WORK.positions` 40 → 64.
- `attack:weapon_absent` (1% on duel) and `move:actor_absent` (8%) were below the threshold and were
  not edited. `attack_probes` stays 32.
- `predictions` 16 → 36: with a 16-slot combat share the refill can retain more combat candidates than
  the forecast cap covered, and every retained combat candidate must carry a forecast
  (`tests/v5/test_candidate_pool_budget.py` asserts `predictions == len(combat)` and a non-zero
  forecast flag). The cap now matches the actionable total.

Both edited Lua files bump `WORK.version` to `work-12000-v6`, and `learning/features.py` declares the
same version with the per-class shares. Every literal assertion of the old contract was updated in the
same change.

## Held-out fit decomposition

`learning/bc.py` `imitation_quality` now reports, per kind, the exact-match accuracy it already
reported plus same-kind, same-actor, same-destination, label-rank buckets and mean candidate count, so
a future `bc_gate.json` states whether a low accuracy means "the right kind was ranked too low" or
"the actor/destination was never a candidate". This report does not carry those numbers: producing them
requires a gated BC run over the collected corpus, and no training or gated run was authorized here.
The replay above measures retention only, which is the input the fit decomposition reads.

## Plan pass criteria, item by item

| criterion | result |
|---|---|
| targeted suites (`test_coverage_reasons`, `test_candidate_pool_budget`, `test_candidate_provenance`, `test_candidate_gating`, `test_tactical_inputs`, `test_duel_hurt_branch`) | PASS, 48 tests |
| `unittest discover -s tests/v5` | same 20 pre-existing environment failures/errors as `master` `93484a5`; failure sets diff empty across `93484a5`, `e76aea8` and `aab2a5d` |
| `tests.v5.test_pipeline_contract` alone | 94 tests, 2 failures + 2 errors, identical on `master` |
| replay determinism, all three formats, both runs | `ok` |
| `sum(reasons) == total − matched` per kind | holds exactly, both runs |
| every class ≥ 0.80 and overall ≥ 0.90 after the repair | NOT MET — duel recruit 0.7814, duel attack 0.7103, ffa4 every class, team2v2 every class |
| `truncated` no higher than the baseline | MET on duel (2283 → 2253), NOT MET on ffa4 (2281 → 2290) and team2v2 (2915 → 2929) |
| per-decision work under `WORK.total` | holds by construction: `charge` refuses any unit that would push `work` past `WORK.total` and returns the decision with `truncated=true` instead, so no job can exceed the budget; `truncated` above counts exactly those cuts |

Per the plan's stop rule, the measured ratios are recorded and no cap, threshold, teacher, seed or
training schedule was changed after this measurement.

## Limits

- The replay recomputes the candidate set of the frozen decisions; it does not play new games, so it
  says nothing about behaviour, strength or convergence.
- Only the decisions the committed gates scored are replayed (24 duel games, the first 8 games of ffa4
  and team2v2), which is what makes the denominators comparable.
- Retention improved on every format, but the gate is still not met: the remaining attack misses are
  dominated by destination retention (128 of 199 on duel, all but 21 of them moving attacks), and on
  ffa4 and team2v2 the movement stage is cut by `WORK.total` before its 64 positions are rated. Both
  are cap or work-allocation questions, deliberately left unedited after this measurement.
- No gate threshold, teacher, seed, panel or training schedule was changed, and no training, PPO,
  selection or final evaluation was run.
