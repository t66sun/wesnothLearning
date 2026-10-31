# L1 — Reduced full-loop run on the restored Astra teacher route

Status: **FAIL** (three clauses met, the final-evaluation entry partial and final evaluation still unusable). Host: `cpuServer`, Ubuntu 24.04.5 LTS, 8 cores, 15 GB RAM. Date: 2026-10-31. Every number below comes from the artifacts in this directory or from the driver flags recorded in `identities.json` and `timeline.log`.

## Scope

`docs/TEST.md` item L1: one lite configuration with the smallest panel that reaches BC, at least two applied PPO updates, one stop/resume from a committed-batch checkpoint, the final-evaluation entry, the selected checkpoint and export recorded, and every stop reason reported — with the same-future clause checked where the identities match.

This run re-enters L1 after #112 restored the frozen Astra teacher (the stock-RCA route was removed). Only duel is activated; no other format, corpus, tuning or strength claim. Nothing here authorizes collection or formal training.

## Identity

| Component | Value |
| --- | --- |
| Source | `master` at `5ac67d9` (merge of #112), extracted to `acceptance_20261031_astra/src`; archive SHA-256 `e99ab382261a22dbf5d5e1c63dc88eb7dac55899e11e32092c8bfdaaa2295ca4` |
| Native engine | `Battle for Wesnoth v1.18.8`, executable SHA-256 `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf` |
| Lite engine | `lite-0.2`, combat `expected_damage_v1`, RNG `deterministic-expected_damage_v1` |
| Rules | `data/rules/1.18.8-training`, `rules_file_sha256 c769a4d62cd95ed96028cd8931e7030883547b12ec5972f194ef9272741a9021`; catalog coverage approximate 407, unsupported_script 85, `complete false` |
| Teacher | `gpt6astra`, profile `expected_damage_v1`, source SHA-256 `a5d4b3a69d5af0378fa22119f315c1300fb6ad965c79b08071eb4a37c0addbef`, lineage parent SHA-256 `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933` (= the frozen `gpt6astra.zip` file digest) |
| Python / torch | `~/venv/bin/python` 3.12.3, torch 2.9.1+cpu, maturin build of `_engine_lite` |
| Seed / panel | `20261017`; `--formats duel --bc-games 40 1 1 --native-bc-games 0 0 0 --bc-batch-games 20 --bc-records 2048 --bc-validation-records 1024 --validation-interval 100000 --final-blocks 30 --engine lite --evaluation-engine native --workers 8 --trainer-threads 1 --device cpu --hours 0.25` |
| Run `a` | BC → forced PPO → SIGKILL → resume → `phase evaluate`; `selected.pt` = `last_ppo.pt` `603e3c83d6658b96d65da62bdf5cb277e979fbb19b080d4269ee4ac6e65fff08`, version 12 |
| Run `b` | Twin, uninterrupted BC and PPO; `ppo_complete`, version 12, batch 12 pending |

Full flags and per-run checkpoint digests: `identities.json`. Run directories are not shipped; the artifacts here are the driver outputs.

## Commands

| # | Command | Exit | Result |
| --- | --- | --- | --- |
| 1 | `python src/verification/acceptance_20261031/L1/l1_drive.py src src/runs/l1-20261031b <wesnoth>` (run `a`: `run --phase bc`, `phase ppo --force --reason 'L1 reduced panel: duel BC gate not reached in 40 games'`, SIGINT then SIGKILL after two applied updates, `run --resume`, `phase evaluate`) | 0 | BC, forced PPO, stop at batch 8, resume to `ppo_complete`, evaluation requested |
| 2 | same driver, twin `b` | 0 | BC and PPO uninterrupted, `same_future.json` written |
| 3 | `python src/verification/acceptance_20261031/L1/l1_collect.py src src/runs/l1-20261031b evidence` | 0 | 17 files; `boundary.json` and `a/duel-export.json` added from the run directory |

## Results

| Case | Verdict | Counts / artifacts |
| --- | --- | --- |
| Smallest panel that reaches BC | PASS | 40/40 teacher jobs `complete` (39 `victory`, 1 `turn_limit`), all on `lite` with both seats at `a/frozen/opponents/gpt6astra.zip`; 4,139 teacher rows written, all `training_eligible`; meta carries `teacher gpt6astra`, `teacher_profile expected_damage_v1`, `teacher_source_sha256 a5d4…`; 5 BC batches, 268 updates (`44+56×4`); `bc_gate.imitation.effective false` — 683 samples, accuracy 0.4012, cross-entropy 2.3003 vs uniform 4.3879 (recruit 0.4956/113, move 0.4618/314, attack 0.2233/206); coverage 4139/4186 = 0.9888; the reduced panel was forced into PPO with the recorded reason |
| ≥2 applied PPO updates | PASS | 7 PPO batches, updates `8, 6, 8, 6, 8, 8, 8`; `a/duel-state.json` history batches 5–11 |
| Stop/resume from a committed batch | PASS | Stop condition at `applied=3`; SIGINT ignored for 3 min then SIGKILL `rc=-9` at 12:55:26 with version 8, batch 8, `pending_train` recorded in `boundary.json`; resume continued at batch 8, the interrupted process exited with batch 11 pending and the `phase evaluate` resume applied it; run `a` ends at version 12 with no recomputation of batches 0–7 |
| Final-evaluation entry | PARTIAL | `phase evaluate` accepted (`92506ee4be4946ae9f39ac09a663a63c`), stage `finished`, selection and export written, but every game faulted |
| Final evaluation usable | FAIL | 120/120 games (`60 gpt6astra`, `60 baseline`) `watchdog_timeout` at `turns 1`, `faults {"1": "watchdog timeout: candidate evaluation/execution"}`, `0/30` blocks per control, both controls `inconclusive` |
| Selected checkpoint and export recorded | PASS | `selected_kind fallback`, reason `no retained champion`: `selected.pt` = `last_ppo.pt` v12 `603e3c83…`; export `a/duel/policies/final-selected/` with `export.json` (duel-v12, 776,178 parameters, model SHA-256 `76b0c70df99bc34bd8bdb951bc41756fc6ccc0b38e737d80968cb273243a0c74`, `evaluation not_evaluated`, `teacher gpt6astra`) |
| Resume reproduces the uninterrupted future | PASS | Batches `[8, 9, 10, 11]` identical between the stopped-resumed `a` and the uninterrupted `b` (`applied_a 7`, `applied_b 7`) |

### Stop/resume trace (`timeline.log`)

```
12:31:54 A BC      →  12:47:04 bc_complete, effective=False (5 batches, 268 updates)
12:47:05 phase ppo rejected: "duel: BC gates not passed; use --force --reason …"
         forced request c5b7d746486e42c88101b6ebcd98fe75
12:52:26 stop condition met after 320 s → SIGINT ignored → 12:55:26 SIGKILL rc=-9,
         applied=3, version 8, batch 8 pending   (boundary.json)
12:55:26 resume    →  13:02:16 exits with batch 11 pending, version 11
13:02:17 phase evaluate (resume) applies batch 11, selects v12, exports, plays 120 games
13:04:57 stage=finished, status=inconclusive
13:04:57 twin b BC → 13:20:07 bc_complete  →  13:36:09 ppo_complete, version 12
13:36:09 compare: batches [8, 9, 10, 11] identical=True
```

## Why the final evaluation still produced no scored game

The same native action-budget defect measured on 2026-10-31 remains: every exported-policy decision costs ≈1.9 s while `vendor/arena/params.py:8` freezes `ACTION_TIMEOUT = 1.0`. First games end at `turns 1` after 2 actions and ≈4.9 s with `faults {"1": "watchdog timeout: candidate evaluation/execution"}`, `winner 2`, no `native_replay`. This is independent of the teacher route: teacher and PPO sampling ran on `lite`, and the fault appears only when the exported policy is driven through the native engine.

## Reuse

None. The source identity (`5ac67d9`) differs from the accepted-evidence source of `verification/acceptance_20261031/L1` (`5038258` with patched checkpoints), so the BC, PPO and same-future clauses were rerun rather than inherited. The native-budget evidence itself is unchanged and is not duplicated here beyond the fault counts.

## Failure

| Case | Failure | Evidence | Consequence |
| --- | --- | --- | --- |
| Final evaluation usable | Native action budget expires before the exported policy decides | `a/duel-jobs.jsonl` (120 `watchdog_timeout`), `a/duel-summary.json` (`0/30` blocks) | No strength or promotion claim is possible; L1 stays open |

## Resources

64 min wall clock (BC 15 min, PPO 6 + 7 min plus evaluation 3 min, twin 31 min); 8 workers, 1 trainer thread, CPU only; run tree 1.3 GB; evidence 675 KB / 17 files, copied unchanged. No retries, seeds or gates were changed during the run.

## Gate

L1 remains **FAIL**: the panel, PPO application, stop/resume, same-future and the selection/export record now pass on the Astra route, but the final evaluation still scores nothing, and a reduced panel grants no strength claim anyway. The item stays in `docs/TEST.md` with this evidence; no collection or training is authorized by this report.
