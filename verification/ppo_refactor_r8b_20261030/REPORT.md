# Stock labels name the executed action (R8b, 2026-10-30)

Result: **passed on Ubuntu**. 33 focused checks pass, and two real stock-RCA games
collected through the runner's own teacher job builder clear the real BC coverage
gate — `all 82/88 = 0.932`, `recruit 11/11`, `move 43/46 = 0.935`,
`attack 28/30 = 0.933` — with **zero ambiguous events of every kind**. The
shipped capture hash is `12fbbb4d3b3af4fc0a2afdb3c5d4893b8df23f408a50bc4081932f08042b3b54`,
the runtime `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`
and the rules `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`.

This closes the limit R8 and R9 recorded: those runs could not grade their own
labels, because two thirds of the attack labels were ambiguous (the WML event
never named the weapon), every move destination was offered twice (full move and
stop-short variant), and the coverage denominator counted merged events. The
policy corpus stays blocked on the R5 rehearsal decision; nothing here collects
a corpus, trains, or measures strength.

## What changed

| Change | File | Why it was wrong before |
|---|---|---|
| Attack events name the weapon index the engine reports | `lua/stock_rca_capture/main.lua` | `attack` events left `frame.weapon` unset, so a unit with two usable weapons matched two candidates and the label became ambiguous |
| One action keeps one candidate | `learning/stock_rca.py` | `candidates.lua` offers every destination as a full move and a stop-short move; identical public intent counted as ambiguity |
| Coverage counts decisions | `learning/sample.py` | merged events (one recruit burst, one move+attack) were in the denominator even though the decision's label names the composed action |
| Four label checks and a totals check | `tests/v5/test_native_capture.py` | no assertion covered weapon naming, variant collapse, or the denominator |

The weapon is read from the event variable `weapon`, which 1.18.8 populates with
`name`/`type`/`number`/`damage`; only a unique match against the acting unit's
`attacks` list sets an index, so identical weapons stay unnamed instead of
guessing. `intent()` in `learning/stock_rca.py` is the tuple of public fields
that names an action (`kind`, positions, and `weapon` for attacks); candidates
that differ only in scoring fields share one intent and no longer make the label
ambiguous, while intents that differ still do.

## Revert proof

`revert_ubuntu.sh` removes each half in turn from the accepted source tree and
expects the dependent check to fail, then restores from a backup copy.

| Revert | Check that fails | Observed |
|---|---|---|
| intent dedupe removed | `test_scoring_variants_of_one_move_are_not_ambiguous` | `AssertionError: True is not false` (`ubuntu/revert/dedupe.log`) |
| weapon naming removed | `test_attack_names_the_weapon_the_engine_reports` | `KeyError: 'weapon'` (`ubuntu/revert/weapon.log`) |
| merged events counted | `test_stock_totals_count_decisions_not_events` | `AssertionError: 15 != 6` (`ubuntu/revert/totals.log`) |
| merged events counted | `label_probe.py` gate | `AssertionError: ('recruit', {... 'merged': 9, 'total': 12}, {...})` (`ubuntu/revert/gate.log`) |

Restoration reruns `tests.v5.test_native_capture`: 13 checks pass
(`ubuntu/restored.log`).

## Ubuntu procedure

Acceptance root `/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r8b_20261030`.

- Source archive built from the accepted commit `4624a896d2574cc6334cb5d186adb79644e9d618`
  with `git archive`, `data/` removed and `SOURCE_REVISION` written; 7,895,040
  bytes, sha256 `9df512fb800cb5046ade94757a345351c278d9363ecc91b53554bc263f8c0d8c`.
  Archiving from git keeps the capture sources at LF, which is what makes the
  capture hash canonical (a Windows working copy hashes differently).
- `data/` is a symlink to `training_lite30h_20261025/source/data`; the R8
  deterministic entropy shim is compiled from
  `verification/ppo_refactor_r8_20261028/deterministic_entropy.c` and preloaded,
  so both games are reproducible.
- `rerun_ubuntu.sh` runs `tests.v5.test_native_capture`, `test_teacher_protocol`,
  `test_reward_row_schema`, `test_bundle_identity`, `test_teacher_identity`
  (33 checks, `ubuntu/targeted.log`), then `label_probe.py`, then asserts the
  probe identity and gate (`ubuntu/identity.log`).
- Environment: Linux 7.0.0-38-generic, Python 3.12.3, torch 2.9.1+cpu, Wesnoth
  1.18.8 (`ubuntu/environment.log`).

The two games are five-turn duel games played by `baseline` on both sides, built
by `stock_teacher_jobs`; the probe lowers `max_turns` to 5 and rebinds the
scenario identity. A train-length stock game carries its captured rows through
the runner's native log, and one such game already exceeded the 16 MiB log limit
during development, so label evidence uses five labeled turns.

## Evidence table

| Item | Value |
|---|---|
| Focused checks | 33 pass (`ubuntu/targeted.log`) |
| Games | 2, seeds `1313236434` and `2342139474` (`ubuntu/probe.json`) |
| Gate | `all 82/88 = 0.932`, `recruit 11/11`, `move 43/46 = 0.935`, `attack 28/30 = 0.933` |
| Ambiguous events | 0 of every kind |
| Merged events (reported, not counted) | recruit 17, moveto 27 |
| Unlabelled events | moveto 3, attack 2, advance 1 |
| Capture hash | `12fbbb4d3b3af4fc0a2afdb3c5d4893b8df23f408a50bc4081932f08042b3b54` |

`unmatched_reasons.py` replays the accepted labeler over the captured streams and
names why each event stayed unlabelled (`ubuntu/unmatched_reasons.log`): three
events had the 128-candidate budget exhausted, two moves are absent from the
generator's own selection (lists of 66 and 91 candidates), and one `advance`
event has an invisible actor; the candidate generator never offers `advance`
actions. None of them is a stale-context or duplicate-intent failure.

## Limits

- Two five-turn duel games on one map rotation, `baseline` on both sides: enough
  to prove the gate arithmetic on real labels, not to characterise a corpus.
- `recall` and `advance` were never executed, so their coverage stays zero and
  unproven; the gate grades only recruit/move/attack.
- Six events remain unlabelled; four are the candidate budget, which a corpus
  needs to size, not a capture defect.
- A train-length stock game can exceed the runner's 16 MiB native log limit. That
  is a corpus-collection prerequisite (raise the limit with evidence or shorten
  the capture payload), not something this change decides.
- No corpus, BC/PPO run, strength measurement, gate change or coverage floor
  change. R5's rehearsal prerequisite remains a data decision.
