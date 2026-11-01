# BC coverage root-cause diagnosis and bounded repair

Date: 2026-11-01. Ubuntu acceptance; no Windows tests were run.

## Result and scope

The fixed 40-game coverage check passes for all three formats under `work-12000-v8`. The four generation defects below are repaired at the shared Lua boundary with the same 37-candidate and 12,000-work limits. The 45 affected tests pass. This does not complete teacher-strength or ordinary BC-to-PPO acceptance: the separately bounded ordinary BC result is recorded under `readiness/`; TEST.md L2/R3 retain their unmet requirements. Native timing fails under the observed shared-host workload and stays open as C1.

Only candidate generation/selection and its schema identifier change in production. The optimizer, training losses, gate thresholds, teacher, native timeout and frozen replay schedules are unchanged. No production try/catch or assertions were added. Diagnostic instrumentation, referee snapshots and unbounded ablations stay in test tooling; no teacher intent or referee-only state is fed to candidate generation.

## Identities and inputs

- Baseline master: `06859a8`; v7 tracing: `52b288f` (same production baseline); final behavioral source: `8ce517935da9d59c1dba23309c246e365960f5e3`.
- Diagnostic helper cleanup: `7cb81b03cfbbd0d7b47f5ced57cd415fece42686`; only a selection comment changes after the final behavioral source. The final documentation commit does not change behavior.
- Each tested source was committed, sent with `git archive --format=tar`, and extracted into a fresh `/home/tongshu/acceptance/bc_root_20261101_*` directory. No server git checkout or installed AI was modified.
- Frozen teacher schedules/checkpoints: `/home/tongshu/acceptance/bounded_loop_20261101/runs/bounded_loop`. Select the 24 duel and first 8 ffa4/team2v2 jobs that reproduce the old committed gate denominators. Checkpoint hashes remain in `verification/bounded_loop_20261101/verification/bounded_loop_observed/checkpoints.sha256`.
- Rules: `1.18.8-training`, SHA256 `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`; unchanged expected-damage profile. Frozen teacher package SHA256 `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`.
- Ubuntu Python 3.12.3, Linux `7.0.0-38-generic`, `/home/tongshu/venv/bin/python`; native Wesnoth 1.18.8 binary SHA256 `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`.
- Snapshot fixtures are new captures under `data/datasets/diagnostic/bc_{priority,budget,retreat,right_side}_20261101.json[.gz]`. Existing data, run manifests and dated evidence remain unmodified.

## Why more retained candidates did not solve it

Instrumentation compares the teacher intent with both the generated pool and final retained candidates, on the unchanged teacher trajectory:

| v7 frozen subset | Missed intents | Absent before selection | Generated but dropped |
| --- | ---: | ---: | ---: |
| ffa4, 8 games | 669 | 619 (92.53%) | 50 |
| team2v2, 8 games | 1,168 | 1,127 (96.49%) | 41 |

See `baseline_trace/*/summary.json` and per-decision logs. Ffa4 loses 341 moves and 272 moving attacks in generation; team2v2 loses 1,017 moves and 110 moving attacks. Enlarging final retention cannot recover these missing actions.

1. **An attack landing kept its first noncombat category.** In the frozen attack case, `(6,8) -> (6,9), target (7,10), weapon 2` is reachable, shortlisted and selected as a village landing, but never probed before the 48-move-probe cap. Increasing total work or the position/rating caps independently still misses it. Retaining an independent combat flag recovers it with 48 probes and the same 8,170 work in the isolated ablation. Production keeps each actor's primary move first, then its combat landings. Final selection preserves generated primary moves so additional attacks do not eject actors entirely.
2. **Planning consumed work needed to emit actions.** A recorded ffa4 state consumes all 12,000 work after planning ten actors and performs zero move probes, leaving an empty actionable pool. Reserve `48*2 + 36*30 = 1,176` work for probes/forecasts and divide remaining planning work among remaining mobile actors. The regression requires the later actor's legal move and real forecasts on retained combat entries, within the same total budget.
3. **Proximity screening removed safe retreats before risk evaluation.** `(10,8) -> (6,7)` is one of 122 reachable positions but absent from the 64-position shortlist. Increasing probes or total work alone does not recover it; increasing positions alone still leaves it outside eager risk evaluation. The all-search v7 diagnostic finds it with zero risk, but spends 13,063 work. Interleave proximity and threat-count order through the existing 64-position and 40-rating caps instead. The frozen retreat regression then passes without raising either limit.
4. **A map-coordinate village prefix hid the right side.** A 27x26 team map has 24 villages; the first-16 prefix excludes all eight rightmost villages, including `(24,6)` and `(27,5)`. A right-side actor consequently lacks its nearby objectives. Select up to 16 nearby known villages per actor and rank the 12 retained tactical goals by bonus minus travel distance. The real-state right-side teacher move is retained after the fix. The scan is charged to that actor's planning allowance.

`ablation/attack.jsonl` and `move.jsonl` retain the original v7 interventions. In these early files, `reason` was mistakenly populated even for a successful match; interpret `matched`/`generated` as authoritative. The corrected helper writes `reason: null` on success and requires an explicit frozen v7 `--source-tree`; its final smoke is `helper/snapshot.jsonl`. In `ablation/safe.jsonl`, the all-search intervention was applied after budget reservation existed, so its expanded probe cap also enlarged the reserve: that line is invalid as an all-search comparison and is not used for conclusions. The successful bounded safety intervention and the original v7 all-search evidence are separate.

## Fixed-schedule coverage

Thresholds remain >=90% overall and >=80% for recruit, move and attack. Moving attacks belong to attack; end turn contributes to overall.

| Format | Overall v7 | Overall v8 | Recruit v8 | Move v8 | Attack v8 | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| duel | 2303/2602 (88.51%) | 2371/2602 (91.12%) | 345/398 (86.68%) | 1092/1187 (92.00%) | 604/687 (87.92%) | PASS |
| ffa4 | 1754/2423 (72.39%) | 2184/2423 (90.14%) | 209/255 (81.96%) | 994/1074 (92.55%) | 665/778 (85.48%) | PASS |
| team2v2 | 2035/3203 (63.53%) | 2969/3203 (92.69%) | 146/168 (86.90%) | 2077/2248 (92.39%) | 356/397 (89.67%) | PASS |

`fixed_gate.jsonl` contains exact ratios/reasons. The replay reports `determinism: ok` for every format: this verifies the committed per-kind denominators, not a cryptographic comparison of every final trajectory event. Teacher code/execution remains unchanged. Baseline trace digests are retained in the trace summaries. The same schedules are diagnostic data used during repair, not an unseen acceptance or strength panel.

Tradeoff: recruit retention falls from v7's 87.69%/91.76%/94.05%, while staying above its gate. Primary actor moves consume some formerly available class slots. No duplicate padding, hidden larger candidate pool at inference or gate adjustment was introduced. The fresh ordinary run measures additional schedules separately.

The replay log's top-level `truncated` counts candidate-generation cuts, not truncated games. Actual game truncation is `result.truncated`: the fixed replay completes 24/8/8 games with zero faults and 1/3/4 turn-truncated games. Inspecting all original bounded-loop job records gives 24/16/13 complete games and 1/6/6 true turn truncations; the historical claim that every game was truncated conflated the two fields. The frozen lite jobs use the engine's 60-turn default and can report turn 61; a historical prose claim of 30 turns is not the observed job limit. Historical reports were not rewritten.

## Coverage is not imitation fit

The old checkpoints (versions 5/1/1) were evaluated offline with their original rows/weights. No formal resume, checkpoint mutation or schema migration occurred. The representation audit receives decoded Python lists with feature schema 5; row storage schema 6 does not change those vectors.

| Format | Available train / held-out rows | Held-out overall | Recruit / move / attack accuracy | Tiny-set fit |
| --- | ---: | ---: | --- | --- |
| duel | 1534 / 354 | 31.33% | 53.33% / 27.75% / 26.92% | 64/64 after 200 steps |
| ffa4 | 1965 / 701 | 22.93% | 0% / 0% / 0% | 64/64 after 200 steps |
| team2v2 | 1650 / 152 | 42.47% | 0% / 26.09% / 7.14% | 64/64 after 200 steps |

Quality excludes single-candidate decisions (332/689/146 held-out samples). Duel's recruit class has only 30 samples; team2v2 recruit/attack have 2/14, below the unchanged minimum of 32 each. Ffa4's available shards include a newly collected pending batch, so its 16-game available pool is not the exact set already trained by its one committed batch. Do not interpret its train score as training-set accuracy on a known visited set.

The audited 354/701/152 held-out rows contain no exact input collisions with conflicting labels, teacher aliases, or missing actor/target/local/geometry components. They are **surviving labeled rows**; the audit's 100% coverage does not measure lost teacher decisions. Small-set copies reach 100% with CE 0.0050/0.0045/0.0325 in 200 steps, seed 19. This rules out a universal inability to learn these examples; it does not prove generalization, good teacher rankings or affordable convergence. The ordinary run below is the independent readiness check.

Raw output: `fit/{duel,ffa4,team2v2}.json`. Durations were approximately 185/328/308 seconds, including audit and fit, under shared-host load; these are not throughput benchmarks.

## Checks and commands

The following use `/home/tongshu/venv/bin/python` with `PYTHONPATH=.:vendor/arena`, `OMP_NUM_THREADS=1`; collection/training also set MKL/OpenBLAS threads to 1 and SDL video/audio to dummy. Paths below abbreviate the acceptance root and frozen run named above.

```sh
# v7 traces, source bc_root_20261101_r3
python tests/diagnose_bc_coverage.py --run "$frozen_run" --format ffa4 --games 8 --out tmp/ffa_all
python tests/diagnose_bc_coverage.py --run "$frozen_run" --format team2v2 --games 8 --out tmp/team_all
# Historical fit diagnostic, source bc_root_20261101_fit (b7d70f9)
python tests/diagnose_bc_fit.py --run "$frozen_run" --format duel --output tmp/duel-fit.json
# Same command for ffa4 and team2v2, separate outputs; default 200 steps.
# Final frozen replay, source bc_root_20261101_right_fix (8ce5179)
python verification/teacher_coverage_20261101/replay.py --schedules "$frozen_run" --out tmp/replay_after --workers 8
python -m unittest tests.v5.test_combat_destination_priority tests.v5.test_candidate_pool_budget tests.v5.test_candidate_gating tests.v5.test_candidate_provenance tests.v5.test_tactical_inputs tests.v5.test_duel_hurt_branch tests.test_candidate_budget tests.test_lua_contracts -v
# Helper cleanup source bc_root_20261101_review (7cb81b0)
python tests/diagnose_bc_snapshot.py data/datasets/diagnostic/bc_priority_20261101.json --source-tree ../bc_root_20261101_r3
python -m py_compile tests/diagnose_bc_coverage.py tests/diagnose_bc_fit.py tests/diagnose_bc_snapshot.py
```

- Final targeted suite: **45 PASS**, exit 0, 3.648 seconds (`targeted.log`); helper smoke and compilation exit 0.
- Red states were observed before each fix: attack source `c0ebe3b` missed the intent; budget source `66d1dfa` missed the actor; retreat source `70c959a` missed the intent; right-side source `ee5f870` missed the intent. Budget/retreat stderr is archived here; attack/right-side red stdout was observed in the tool session but not saved as a standalone log. No retrospective log is fabricated.
- An intermediate combat-only fix exposed the existing primary-move test; preserving primary moves resolves it. Final tests include this existing contract.
- Early diagnostic harness failures (reconfiguring an initialized host, then incompatible audit row encoding) were fixed in test tooling before interpreting results. They are not evidence of production faults.

## Native latency: failed check, limited attribution

The existing native benchmark was run on final `8ce5179` and baseline `06859a8`: seed-0 exported policy, seeds 20261101/20261102, dense 21x15 map, unchanged one-second timeout. Each format plays a pair at 20 turns; the pre-existing fallback plays a new 30-turn pair when fewer than ten midgame decisions are available. V8 duel used that fallback; both original and fallback raw events remain available. Summaries describe the final pairs, not every played game.

| Version | Generation p95, duel/ffa4/team2v2 (ms) | Scoring p95 (ms) | Team maximum measured decision (ms) | Faulted games |
| --- | --- | --- | ---: | ---: |
| v7 baseline | 44 / 93 / 36 | 445 / 478 / 467 | 1028 | 0 |
| v8 final | 55 / 84 / 26 | 459 / 488 / 456 | 1056 | 0 |

Both benchmark processes exit 1. Both fail the unchanged scoring p95 <=400 ms and team decision <800 ms checks; each team summary counts two decisions over its contract. V8 stays within 37 candidates and 12,000 charged work. Native event streams and evaluator decision logs measure different seats/stages, so their maxima are not interchangeable.

These runs overlapped each other and the ordinary training start. They establish the observed failure under that load, but do not establish an unloaded regression/non-regression or attribute the excess to Lua generation. An earlier intermediate v8 run (`06bf585`) also failed duel scoring p95 (464 ms); its summary is retained, not selected away. No threshold was relaxed and no repeat was launched merely to obtain a pass. See TEST.md C1 for the isolated remaining acceptance.

Command: `python verification/candidate_work_budget_20261031/check.py ROOT OUT WESNOTH COMMIT`, with the exact identities in `native_v7/summary.json` and `native_v8/summary.json`. Exported diagnostic weight packages remain on the server; summaries, logs and raw compressed game events are retained in this evidence directory.

## Ordinary bounded BC run

Source `8ce5179`, fresh directory `/home/tongshu/acceptance/bc_root_20261101_readiness`, new run `runs/bc_readiness`; no historical weights resumed. The predeclared command is:

```sh
timeout --signal=TERM --kill-after=15s 1950s python -u -m learning run \
  --run-dir runs/bc_readiness --hours 0.5 --phase bc \
  --formats duel ffa4 team2v2 --workers 8 --trainer-threads 1 --seed 20261101 \
  --bc-games 48 48 48 --native-bc-games 0 0 0 \
  --bc-records 2048 --bc-validation-records 1024 --wesnoth "$wesnoth"
```

The 30-minute ordinary phase has no artificial five-batch stop. Normal adaptive collection remains enabled; no seeds, gate thresholds or phase deadlines are changed after launch. The outer 1,950-second bound only limits shutdown overruns. Phase BC does not request PPO or final evaluation. The manifest, final states/gates, completed job logs, checkpoint hashes and final summary are retained under `readiness/`. The process exits 0 naturally after **1,863.20 seconds** (31m03s, including preparation/drain); the outer timeout does not fire. All formats report `bc_complete`, but `effective=false`: completion of the bounded phase is not passage of the gate. No task-owned processes remain after exit. Every pending next batch has cursor epoch 0 / step 0, so it has no uncommitted optimizer progress.

| Format | Committed batches / updates | Complete teacher games | Games in last gate / target | Coverage in last gate | Imitation overall | Recruit / move / attack |
| --- | --- | ---: | --- | ---: | ---: | --- |
| duel | 10 / 500 | 48 | 48 / 48 | 90.87%, PASS | 45.21% | 51.18% / 47.72% / 34.50% |
| ffa4 | 5 / 248 | 45 | 40 / 48 | 91.21%, PASS | 45.31% | 41.03% / 53.76% / 28.10% |
| team2v2 | 3 / 128 | 32 | 24 / 48 | 93.62%, PASS | 46.59% | 15.25% / 52.19% / 18.79% |

All three imitation gates fail the unchanged per-class targets (60% recruit, 35% move/attack; 40% overall, at least 32 samples each and CE below 85% of uniform). All classes now have enough held-out samples. Ffa4/team2v2 also lack their required corpus at the last committed gate. Additional completed games after that gate are not retroactively counted as trained/accepted evidence.

There are 125 complete teacher games, zero recorded game faults, and three ffa4 jobs interrupted by the deadline. True teacher-game turn truncations are 2/13/20. Duel additionally runs six ordinary validation games and twelve automatic reward-reference games at version 10; these are real training costs, not teacher corpus. Total recorded complete games including those jobs are 66/45/32, with 8/13/20 true turn truncations. These validation/reference games were part of the normal pipeline; their presence does not accept the teacher-strength panel or final evaluation.

A read-only check loads each `last_bc.pt`, uses its own frozen `runner.teacher_shards`, and reproduces the last train read (`limit=2048`, seed=config.seed+version-1) and validation read (`limit=1024`, seed=config.seed). Evaluate `imitation_quality` on the train view and the unchanged validation view; no optimization or checkpoint write. `readiness/committed_fit.json` reproduces all three stored imitation gates exactly. Train accuracy is **69.72% / 55.63% / 54.45%**, versus held-out **45.21% / 45.31% / 46.59%**. Train recruit accuracy is 68.99% / 36.23% / 24.78%; train attack is 67.27% / 36.36% / 20.90%. Thus duel shows a substantial generalization gap, while the larger formats still fit recruit/attack poorly even on their sampled training rows. This identifies the remaining limitation without claiming a specific optimizer/representation cause that these measurements do not establish.

The next BC investigation should separate recruit type versus slot prediction and attack ranking on frozen train/held-out examples, using these checkpoints. More retained candidates is not a supported repair for that fitting gap. The full item remains open; no thresholds, seeds or validation selection were changed to obtain a pass.

Full legal-board teacher ranking, the paired 12-block teacher-strength panel, PPO, stop/resume, selected-policy final evaluation and audited export are NOT RUN in this task. Item 10's measured coverage causes are repaired; these broader acceptance requirements cannot be marked complete from this evidence.
