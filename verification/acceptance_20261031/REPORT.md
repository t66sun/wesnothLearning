# Acceptance run 2026-10-31 — N1, L1, R3 on native Wesnoth 1.18.8

Host: `cpuServer` (Ubuntu 24.04.5 LTS, 8 cores, 15 GB RAM, 197 GB free disk).
Tree: `git archive` of `master` at `32c3ff37d3448b09203a33537136ff91c8be5bb8d52424295932afd9a0c44c18`,
extracted to `~/myDev/wesnothLearning/acceptance_20261031/src` with `data/rules`, `data/opponents`
and `.runtime` symlinked to the existing 1.18.8 build.

## Identity

| Item | Value |
| --- | --- |
| Engine | `Battle for Wesnoth v1.18.8` (`--simple-version` → `1.18.8`) |
| Executable SHA-256 | `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf` |
| Frozen rules | `data/rules/1.18.8`, `rules.json` `c769a4d62cd95ed96028cd8931e7030883547b12ec5972f194ef9272741a9021`, `catalog.json` `a1f366ea93e00a5f4fa7a2a2ea9f2267b7bebaf1040c7828e81adcb19f9cac5a` |
| `_engine_lite` | rebuilt in place with `maturin develop --release` (12.5 s); `ENGINE_VERSION lite-0.2`, `COMBAT_VERSION expected_damage_v1` |
| Python | `~/venv/bin/python` (torch 2.9.1+cpu, maturin 1.15.0) |
| Rules profile used by every N1 metric row | `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca` |

Commands are the two runners stored beside this report (`n1_native.py`, `r3_astra.py`,
`l1_drive.py`); each takes `<repo-root> <output-dir> <wesnoth-binary>`.

## N1 — terminal and truncated games

Procedure (`N1/`): `python -m learning.sample.play_job` with `engine=native`, two stock
`baseline` seats, a `LearningSupport` add-on exported from an untrained `Policy('duel')`
(support add-ons are copied, never validated — `vendor/arena/addons.py:95-97`), `max_turns`
5 and `meta.phase='validation'`. Fixed boards: `CLOSE` = 1×2 hexes `Gg` (leaders spawn
adjacent), `FAR` = 1×40 hexes with starts `(1,1)` and `(40,1)`.

Results — nine close-board games and one truncation control, all `status=complete`:

| Game | Factions (side 1 / side 2) | Reason | Turns | Survivors | METRIC | ELIMINATED | BOOTSTRAP | Errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `terminal-0-7` | Drakes / Undead | `last_leader` | 4 | `[1]` | 4 | `2@4` | 0 | 0 |
| `terminal-0-11` | Drakes / Undead | `last_leader` | 4 | `[1]` | 4 | `2@4` | 0 | 0 |
| `terminal-0-23` | Drakes / Undead | `last_leader` | 4 | `[1]` | 4 | `2@4` | 0 | 0 |
| `terminal-1-7` | Northerners / Undead | `last_leader` | 4 | `[2]` | 4 | `1@4` | 0 | 0 |
| `terminal-1-11` | Northerners / Undead | `last_leader` | 3 | `[2]` | 4 | `1@3` | 0 | 0 |
| `terminal-1-23` | Northerners / Undead | `last_leader` | 5 | `[2]` | 4 | `1@5` | 0 | 0 |
| `terminal-2-7` | Drakes / Rebels | `turn_limit` | 5 | `[1, 2]` | 2 | — | 0 | 0 |
| `terminal-2-11` | Drakes / Rebels | `turn_limit` | 5 | `[1, 2]` | 2 | — | 0 | 0 |
| `terminal-2-23` | Drakes / Rebels | `turn_limit` | 5 | `[1, 2]` | 2 | — | 0 | 0 |
| `truncation-control` | Drakes / Undead, far board | `turn_limit` | 2 | `[1, 2]` | 2 | — | 0 | 0 |

`METRIC` rows per game: `initial` × 2 for every game; terminal games add `eliminated` × 1 and
`terminal` × 1, truncated games add none (`vendor/arena/runtime/runtime.lua:63,84-88`).

- Surviving sides keep real own HP. `reward_diagnostics` horizon rows of the winner:
  `absorbing: true`, `entity_coverage_complete: true`, `loss` computed as
  `observed-own-hp-decrements/unique-own-unit-max-hp` (`0.1636`, `0.1455`, `0.1091` on the three
  Drakes wins), `leader_survival 1.0`. The eliminated side shows `leader_survival 0.0`,
  `loss 1.0`, `control 0.0`. Truncated games carry `horizons: {5: null, 10: null}`,
  `complete: false`, `missing: ["turn5","turn10","map","map_sha256","map_partition"]`.
- Bootstrap absorption is absent from every row: a `turn_limit` game emits no `terminal`
  snapshot and no absorbed terminal value, so a truncation cannot invent a terminal.
- Diagnostics never reach learning data: each game returned
  `training_shard = {raw_records: 0, written: 0, excluded: null}` while `reward_diagnostics`
  held the rows above; `tests/v5/test_record_evidence.py:27,37` asserts the same exclusion.
- The lite truncation counterexample passed on this host:
  `tests.v5.test_pipeline_contract.LiteJobTests.test_truncated_policy_game_requires_a_bootstrap_callback`
  and `…test_truncated_policy_game_writes_bootstrap_values` → `Ran 2 tests … OK`.

Limits: the native runtime emits `BOOTSTRAP` only for a `config.learning` side that is not a
teacher and exposes `module.bootstrap`, and only when `reason=='turn_limit'`
(`vendor/arena/runtime/runtime.lua:90-97`). Both seats are stock `baseline`, so no live
`BOOTSTRAP` event exists here; the absorption path is exercised by the two lite tests above.
A policy seat was not used: at the time of this run `addons.validate` re-applied the 16 MiB
submission cap to every bot (`vendor/arena/match.py:125`, `vendor/arena/addons.py:87`), and an
exported `Policy` exceeds it. That defect was found here, fixed in PR #107 (`addons.contestant`
bounds only a zip input) and proved by a three-turn game with an oversized policy bot, so the
policy-seat path is available from that commit on but was not part of this panel.

## R3 — frozen versus adapted Astra

Procedure (`R3/`): `learning.schedule.evaluation_jobs(directory, adapted, frozen, ['baseline'], 1,
seed, deadline, wesnoth, label='r3-smoke', formats=[fmt], min_distinct=1)` followed by
`python -m learning evaluate --jobs … --format <fmt> --engine native --workers 8`, then
`learning.evaluate.comparisons(jobs, results, min_blocks=1, min_distinct=1)`.
Policy = adapted (`learning/teachers/gpt6astra`, `value.lua`, profile `expected_damage_v1`);
control = frozen (`data/opponents/gpt6astra.zip`). Both staged with their own add-on id
(`astra_adapted`, `astra_frozen`) and packed by `vendor/arena/addons.py:147-158`.

| Item | Value |
| --- | --- |
| Frozen package | `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933` (staged `71d69a4b…`) |
| Adapted source | `a5d4b3a69d5af0378fa22119f315c1300fb6ad965c79b08071eb4a37c0addbef` (staged `5e80582e…`) |
| Adaptation identity | teacher `gpt6astra`, profile `expected_damage_v1` |

| Format | Games | Blocks | Distinct scenarios | Complete | Faults | Adapted score | Frozen score | Difference | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| duel (`hamlets`) | 2 | 1 | 1 | 2 | 0 | 0.5 | 2.0 | −1.5 | `not_passed` |
| ffa4 (`loris_river`) | 4 | 1 | 1 | 4 | 0 | 0.7083 | 0.5 | +0.2083 | `passed` |
| team2v2 (`loris_river`) | 8 | 1 | 1 | 8 | 0 | 0.875 | 2.0 | −1.125 | `not_passed` |

Every game `status=complete`, `truncated=0`, `faults={}`, with a native replay and rules version
`wesnoth-1.18.8-native-v2`. Outcomes: duel one `turn_limit` draw and one `last_leader` win for
the frozen bot; ffa4 three `last_leader` and one `turn_limit`; team2v2 seven `last_team` and one
`turn_limit`. `team2v2` context split: `baseline_partner` −1.5, `self_team` −0.75.

Read this as a bounded smoke: one block per format and a single distinct scenario per block, so
the interval equals the point estimate and no strength claim follows. The unchanged 12-block
contract (`docs/TEST.md`) is what a full-strength statement would need.

## L1 — reduced lite panel with stop/resume

Recorded in `L1/REPORT.md` of this directory.

## Limits

- No Ubuntu package manager work: `sudo -n` requires a password on this host; every dependency
  already present in `~/venv` and the prebuilt `.runtime` was reused as found.
- All runs used the native 1.18.8 binary for evaluation and the lite extension for BC/PPO as
  declared per item; nothing here is a convergence or strength result except R3's smoke rows,
  which are explicitly inconclusive.
