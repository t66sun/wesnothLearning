# R9 acceptance — teacher protocol v2 and DAgger retirement

Date: 2026-10-28 (Ubuntu host `cpuServer`, Linux 7.0.0-38-generic).
Source revision: `f54e6fe4f6b3a31ec018c12d0e0f5aa98ba16c5e` on branch
`codex/r9-teacher-protocol`, packaged as `/tmp/wesnoth-r9.tar`
(sha256 `5cf8370efb3c9bc74198ce579dd3a047ed876ebc9d702faa7bd621d52a75b731`, 7,686,144 bytes),
extracted to
`/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r9b_20261029/source` with `SOURCE_REVISION`
holding that full commit id. `revert_ubuntu.sh` was added in the next commit
(`f5d3e2835de322834bc449a571540a2989936b7c`) and run against that same extracted tree, so the
implementation under test is unchanged.

## Behavior accepted

A frozen teacher reaches a game only through a capability its record declares.

- `learning/teacher_protocol.py` is the single place that decides the mode: `dagger_status(record)`
  returns `active` only for a record whose `query` is not `none` (and is exactly `per_decision` for
  `require_query`), otherwise `unsupported_with_stock_rca`. `dagger_teacher(record, path)` refuses a
  teacher without a per-decision query and refuses an empty controller path.
- `learning/schedule.py:stock_teacher_jobs` builds a teacher game for a query-less teacher: every seat
  is `baseline`, `learning.stock_capture` names those seats, `learning.sides` stays empty, and no
  `dagger_teacher` key is written. The builder rejects a record that claims a query and a record that
  lacks the `runtime_sha256` it was frozen against.
- `learning/experiment.py:FormatExperiment.teacher_batch` picks the job builder from the recorded
  capability instead of from the teacher list; `dagger_status` is stored in `state.json` on both fresh
  and resumed runs; a DAgger shard from a query-less teacher is refused; `complete_phase()` records
  `teacher = {kind, version, query, dagger_status, dagger_shards}` in `report/summary.json`.
- `learning/sample.py` refuses a stock-capture job that names a per-decision teacher for one of its
  watched seats, so the Lua capture can never be turned into an Astra query.
- `learning/native_rpc.lua:teacher` already returned `stock teacher has no per-decision query
  capability` for any non-Astra request, so the native path needed no change; no new wrapper was
  added because no caller exists.

Takeover stays out of scope: R8 measured that Wesnoth 1.18.8 exposes no per-turn query hook, so the
record keeps `query=none` and the runner records `unsupported_with_stock_rca` whenever a stock teacher
is selected.

## Revert evidence

`tests/v5/test_teacher_protocol.py` fails when the behavior is removed.
`verification/ppo_refactor_r9_20261029/revert_ubuntu.sh` replaces `teacher_batch` with the
unconditional `teacher_jobs` call in the accepted source tree and runs
`test_runner_collects_stock_games_without_a_teacher_seat`; it errors with
`ValueError: teacher has no query capability; use full native event capture`
(`learning/schedule.py:93`, `rerun/revert.log`), then restores the file and the same test passes
(`rerun/restore.log`). `stock_teacher_jobs` also raises
`stock teacher jobs require a teacher without a per-decision query` if its guard is dropped, which
`test_stock_teacher_games_are_full_native_games` covers.

## Ubuntu procedure

```
bash verification/ppo_refactor_r9_20261029/rerun_ubuntu.sh 5cf8370efb3c9bc74198ce579dd3a047ed876ebc9d702faa7bd621d52a75b731
```

The script verifies the archive hash, refuses an existing root, extracts to a fresh directory, links
`data` to the provisioned training data (`.../training_lite30h_20261025/source/data`), compiles the
deterministic entropy shim from `verification/ppo_refactor_r8_20261028/deterministic_entropy.c`
(sha256 `c5b31dd29138ee747f20033e66642255bc6eae79e72c85baf9e5b4899ffccd09`) and exports it as
`LD_PRELOAD` so the game is reproducible from its seed, then runs:

```
python -m unittest tests.v5.test_teacher_protocol tests.v5.test_teacher_identity \
    tests.v5.test_native_capture tests.v5.test_reward_row_schema -v
python verification/ppo_refactor_r9_20261029/stock_bc_probe.py <root>/probe <wesnoth>
```

`stock_bc_probe.py` builds the support addon, derives the frozen record
(`teacher_identity('wesnoth_default_rca')` plus `runtime_sha256`), calls `stock_teacher_jobs` for one
`duel` game, plays it through `sample.play_job`, and asserts the summary is complete without faults,
the shard rows all carry `source=stock_rca`, `teacher=wesnoth_default_rca`,
`teacher_identity.query=none`, `action_source=engine_events` and `engine_id=native`.

Environment (`rerun/environment.log`): Wesnoth 1.18.8, runtime sha256
`33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`, rules sha256
`d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`, Python 3.12.3, torch 2.9.1+cpu.

## Result

- Targeted tests: **23 tests, OK** (`rerun/targeted.log`). This covers the four new protocol tests plus
  the teacher-identity, native-capture and reward-row suites.
- Stock teacher game: `status=complete`, no faults, Drakes vs Knalgan Alliance on the `duel` holdout
  roster entry, seed 2292032331, both seats `baseline`, `stock_capture=[1,2]`, four turns, winner side 1
  by last leader (`rerun/summary.json`).
- Shard: sha256 `0dd6cf1dc257b2382bcbc363b7bc934546af2e3fb6127126a7eea46a26730894`; 30 stored rows, of
  which **7 are indexed decisions** with an exact label (3 recruit, 2 move, 2 move_attack); the rest
  are ambiguous or unmatched rows kept for audit.
- Teacher identity recorded on every row and in `probe.json`: `capture_sha256`
  `26d2894a09ccc66e5d7274d684644815d659d56b0110b0f0d22a83eb0e539557` (the canonical LF hash of
  `lua/stock_rca_capture`, matching R8), `rules_sha256` above, `teacher_query=none`,
  `dagger_status=unsupported_with_stock_rca`.
- `stock_coverage`: recruit matched 3 / merged 9; moveto matched 2 / ambiguous 7 / merged 16 /
  unmatched 1; attack matched 2 / ambiguous 14 / unmatched 1; recall and advance 0. Merged counts are
  engine events folded into the label of the same decision (a recruit batch, or a move that continues
  into an attack), not lost labels.

## Limits and open decisions

- One game, one format, four turns, one scenario; the numbers prove the path and the identity, not
  corpus size or label quality.
- Attacks stay ambiguous for multi-weapon units because the 1.18.8 `attack` event exposes no weapon
  index; 14 of 17 attack events here were ambiguous. Moveto can be ambiguous when one public
  `(x, y, tx, ty)` matches several candidate entries, and one moveto and one attack were unmatched
  because the 200 ms candidate budget truncated the list before the executed action.
- No training, evaluation, corpus collection or gate change was run. `learning/experiment.py`
  `coverage_gate` is therefore not exercised: with merged counted as represented, this game gives
  moveto 18/19 and attack 16/17, but ambiguous events cannot be trained (`choice=-1`), so the
  `matched/total >= 0.8` gate still needs a stock attack disambiguation decision before R6 corpus work.
- R5 stays blocked for the recorded reason: the rehearsal pool exclusion
  (`learning/data.py:255-258`) is exact, and the repository holds no human or policy row shard that
  is admissible, so no code change is justified there.
