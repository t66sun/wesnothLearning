# R5 rehearsal prerequisite audit — 2026-10-29

Issue #60, parent #48. Runtime implementation `9fee653`; this audit follows the [R5 acceptance](../ppo_refactor_r5_20261027/REPORT.md), whose remaining limit reads: "A teacher-only run has no qualified PPO rehearsal at positive coefficient and fails explicitly; supplying suitable data is a separate data decision". Here that decision is resolved as far as the existing inputs allow: the blocker is **data insufficiency plus one provenance defect**, and the exact decision needed is named.

## Round 1 — the exclusion predicate is not the defect

`learning/data.py:230-278` admits `astra`/`stock_rca`/`human` (and `policy` only when the opt-in flag is set), skips rows that are not `split='train'`, have `choice<0` or carry faults, excludes teacher rows whose `teacher`/`teacher_impl` or `teacher_source_sha256` matches the run's evaluation control, and excludes human/policy rows only by their own `policy_sha256`. The raising branch is reached only when an exclusion is active and nothing survives. There is no over-broad filter to relax.

`allow_policy_rehearsal` is a library argument (`learning/ppo.py:47`, forwarded at `learning/train.py:12`), and the run's single `train(...)` call (`learning/experiment.py:398`) does not pass it — confirmed by AST scan, see `runner_passes_opt_in: [false]` in [probe.json](ubuntu/probe.json). So a run can never admit `policy` rows: the documented opt-in exists only at the sampler API. R5's declared interface does not require a runner-level opt-in, so this is a boundary of the accepted behaviour, not a regression against it.

## Round 2 — no existing corpus can fill the pool

[probe.json](ubuntu/probe.json), recomputed on Ubuntu from the frozen inputs:

| Fact | Observed |
| --- | --- |
| Human row shards under `data/datasets/` | none (`dataset_shards: []`) |
| Recorded import result | 43 games, 2 `compatible_pending_native_replay`, 0 samples, observer `native-observer-v3.1` |
| Curated inventory | 159 rows; 30 at 1.18.8, all of them custom-era multiplayer (`era_brutal_triad`, `era_heroes`) |
| Selected standard-multiplayer games | 5, versions 1.18.2 ×4 and 1.18.7 ×1 |
| Selected 1.18.8 `era_default` standard-multiplayer games | none |

`learning/human.py:52-53` requires `category=='standard_multiplayer'` and `era=='era_default'`, so the custom-era 1.18.8 replays are correctly skipped. The two `compatible_pending_native_replay` entries are `game_0040` (1.18.2) and `game_0042` (1.18.7).

Historical `policy` rows do exist (`verification/v5_completion_20261020/remote-final-20261020/small-loop/data/v4-policy*.jsonl.gz`), but they are schema 4, carry `rules_version 625de0ac…` rather than the frozen `d6fceafe…`, have `policy_sha256: null`, and are mostly `validation`. They cannot serve as qualified on-policy rehearsal for a schema-5 run, and the runner cannot opt into them anyway.

## Round 3 — the reuse path was open and mislabeled

The import entry would have accepted those two older replays. `compatibility()` checked category, era, format, mods, initial state and controller transitions but never the replay's own version, while `import_capture()` stamps every row `native_version='1.18.8'`. A 1.18.2 or 1.18.7 game is recorded under different combat, recruit and terrain numbers, so replaying it in 1.18.8 can complete cleanly and still yield labels that do not describe the frozen rules.

`learning/human.py` now refuses such a replay before preparation:

```python
if row.get('version')!='1.18.8': return 'other_version'
```

A fresh inventory run over the same curated corpus now reports `{'skipped': 43}`, with exactly two `other_version` entries and no prepared or compatible game ([inventory.log](ubuntu/inventory.log), [import.json](ubuntu/import.json)).

## Revert proof

`revert_ubuntu.sh` removes only the version guard. `tests.test_human.HumanTests.test_labels_never_come_from_a_replay_recorded_under_older_rules` then fails with `AssertionError: None != 'other_version'` ([reverted.log](ubuntu/reverted.log)); restoring the module returns all five checks to `OK` ([restored.log](ubuntu/restored.log)).

## Ubuntu acceptance

Ubuntu 24.04 (`7.0.0-38-generic`), Python 3.12.3, torch 2.9.1+cpu, root `/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r5_20261029b`. Source-only archive from `git archive ee8a968` with `data/` removed and `SOURCE_REVISION ee8a968156e91c458ca8b919b87a0cb4d7c9974f` written: 7,841,792 bytes, SHA-256 `0b91b096123f29410faf9667345754b9cacbd7fa0d2cbe3cf43b5c00ec18068f`; frozen inputs staged separately (3.3 MB, SHA-256 `05e7d15148d20a6ea4aacc5105314bda0b3cbdd10db50bbbf50c030d842fd1f2`); `games.jsonl` sha256 `1c94bb8d…` unchanged ([environment.log](ubuntu/environment.log)).

| Check | Observed | Evidence |
| --- | --- | --- |
| Human import, preparation and capture checks | 5 PASS, 0.497 s | [targeted.log](ubuntu/targeted.log) |
| Input audit | `passed: no existing input can fill the R5 rehearsal pool` | [audit.log](ubuntu/audit.log) |
| Guarded inventory | `{'skipped': 43}`, two `other_version`, none prepared | [inventory.log](ubuntu/inventory.log) |

## Decision needed

No code path can manufacture a qualified pool. The blocker is a data decision, and the options are:

1. **Supply human 1.18.8 replays (recommended).** Record standard-multiplayer, `era_default`, unmodified 1.18.8 games, then use the documented route: `python -m learning import-human` (prepare) → play each prepared `.cfg` in the official 1.18.8 replay viewer retaining full logs → `import-human --captures`. This needs human play, not bot games, and cannot be synthesized by the repository.
2. **Authorize a runner-level policy-rehearsal opt-in plus a policy corpus.** This is new behaviour (config key → `train(allow_policy_rehearsal=…)`), must not weaken the control exclusion, and still needs on-policy rows from a checkpoint that exists and loads.
3. **Accept no PPO rehearsal** and record that `bc_aux` imitation operates on an empty pool, keeping the current explicit failure at positive weight.

Until one is chosen, R5's accepted exclusion behaviour stands, and a PPO run with `bc_aux > 0` continues to fail before any parameter change with `ValueError('no rehearsal data distinct from the evaluation control')` rather than rehearsing on the control.

## Limits

No game was played, no corpus was written, no optimizer step ran, no full suite ran. The audit reads frozen inputs and reports raw counts; the guard is proven on a fixture replay tree, not on a real capture. Nothing here authorizes collection or lowers `bc_aux`, and R5's coefficient, gates and thresholds are unchanged.
