# Bounded candidate work budget and separate generation timing

Ubuntu (cpuServer), 2026-10-31. Source `818ef00914a18745c95b6f78fc931bd785a8621a`
(`codex/candidate-work-budget`), shipped by `git archive` to
`/home/tongshu/acceptance/candidate_work_budget_20261031_v1`. Candidate contract
`schema5-work-12000-v5`: `lua/candidates.lua` charges a deterministic work budget
instead of consulting a clock or a call counter, every caller uses that one
generator contract, and `lua/bot.lua` reports generation (`generate_ms`) and
scoring (`score_ms`) separately.

This closes the open acceptance item C1 of `docs/TEST.md` and static-review items 3
and 4 of `docs/blockers_temp.md`: a full shared candidate pool inside the unchanged
one-second native action budget, measured on dense midgame positions in all three
formats.

## Identity

| Item | Value |
| --- | --- |
| Source commit | `818ef00914a18745c95b6f78fc931bd785a8621a` |
| Rules | native Wesnoth 1.18.8, unchanged |
| Wesnoth binary | `/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth` |
| Wesnoth SHA-256 | `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf` |
| Candidate contract | `work-12000-v5` (`total=12000`, caps 28 `find_reach`, 8 `find_path`, 24 `ai.check_recruit`, 32 `ai.check_attack`, 32 `ai.check_move`, 16 forecasts) |
| Schema version | `5` |
| Policy weights | randomly initialized `learning.model.Policy`, exported per format (`WorkBudget`, version `timing`) |

`schema()['rules_sha256']` is `null` in `summary.json` because the frozen catalog
(`data/rules/`) is provisioned rather than authored and is absent from the shipped
tree. Native games do not read that catalog; the rule identity of this run is the
1.18.8 executable hash above.

## Command

```sh
cd /home/tongshu/acceptance/candidate_work_budget_20261031_v1
./.venv/bin/python verification/candidate_work_budget_20261031/check.py . \
    verification/candidate_work_budget_20261031/out \
    /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
    818ef00914a18745c95b6f78fc931bd785a8621a
```

`check.py` exports one policy add-on carrying all three formats plus one support
add-on, then plays two seeded games per format (`seeds 20261101, 20261102`,
`max_turns=20`, `timeout=1`, `first_timeout=10`, `fog=True`) on one fixed synthetic
map: 21x15 all-grass, four keeps at `(4,4) (18,4) (4,12) (18,12)` with a castle ring
each, and `Gg^Vh` villages at `(8,7) (14,7) (10,5) (12,5) (8,9) (14,9) (11,7)`.
Every learner decision emits a `LEARN` row whose `timing` carries generation,
scoring, charged work and the per-stage counters; `RETURN` rows carry the decision
elapsed time. `max_work` never exceeded the budget and no decision exceeded 37
candidates, so no calibration retry was needed.

## Results

Decisions counted are collected `LEARN` rows with `turn>=5`; decision time is the
`RETURN` `elapsed_ms` of the evaluation phase.

| Format | Games | Decisions | generate_ms p50/p95/max | score_ms p50/p95/max | decision max | max candidates | max work | faults | timeouts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| duel | 2 (turns 9, 9) | 34 | 4 / 6 / 6 | 193 / 229 / 230 | 46 ms | 37 | 1152 | 0 | 0 |
| ffa4 | 2 (turns 11, 19) | 198 | 6 / 13 / 21 | 220 / 246 / 256 | 232 ms | 37 | 3862 | 0 | 0 |
| team2v2 | 2 (turns 20, 20) | 160 | 3 / 4 / 11 | 158 / 191 / 200 | 212 ms | 29 | 427 | 0 | 0 |

Execution (`C.execute`) is slower than evaluation and independent of the candidate
budget: 547 ms max in duel, 517 ms in ffa4, 518 ms in team2v2.

## Verdict

| Threshold | duel | ffa4 | team2v2 |
| --- | --- | --- | --- |
| at least 10 midgame decisions | pass (34) | pass (198) | pass (160) |
| `generate_ms` p95 <= 250 ms and max <= 500 ms | pass | pass | pass |
| `score_ms` p95 <= 400 ms | pass | pass | pass |
| decision max < 800 ms | pass (46) | pass (232) | pass (212) |
| zero faults and zero watchdog timeouts | pass | pass | pass |
| at most 37 candidates and at most 12000 work per decision | pass | pass | pass |

Accepted: the shared candidate set, generated under the deterministic work budget,
completes inside the unchanged one-second native action budget on this map in all
three formats, with generation and scoring bounded separately.

Affected checks on the same host and source: 89 tests in 13 candidate, lua-contract
and learning-core modules pass. The full suite runs 537 tests with 44 failing names
whose set equals the `ab0490a` baseline on the same host minus the five
candidate-contract tests this change fixes (provisioned
`data/rules`/`data/rules/1.18.8/maps` inputs are absent and several unrelated
modules fail there); no other failure appears or disappears.

## Limits

- The policy is randomly initialized and the map is a compact synthetic fixture, so
  this is a latency and contract acceptance, not strength or convergence evidence.
- Two games per format; the measured worst case is bounded by the work budget but
  larger boards and longer games were not measured.
- The frozen 1 s native timeout was met on this host only; Windows remains reference.
- Final evaluation, nomination and long-run stability are not covered here; item 9 of
  `docs/blockers_temp.md` stays open, and collection or training is not authorized by
  this report.
- `WORK.total=12000` is the only calibrated value; stage caps and the 12/12/12
  selection were not relaxed.
