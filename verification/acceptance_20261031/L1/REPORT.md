# L1 — Reduced full-loop run

Status: **FAIL** (one clause met, one unverifiable by measurement, one blocked). Host: `cpuServer`, Ubuntu 24.04.5 LTS, 8 cores, 15 GB RAM. Date: 2026-10-31. Every number below comes from the artifacts in this directory or from `docs/TEST.md`'s named commands.

## Scope

`docs/TEST.md` item L1: one lite configuration with the smallest panel that reaches BC, at least two applied PPO updates, one stop/resume from a committed-batch checkpoint and the final-evaluation entry, with its stop reasons reported.

Activated: the whole item. Not activated: any other format than duel, any corpus work, any tuning. Nothing here authorizes collection or formal training; the panel is deliberately reduced and therefore inconclusive for strength.

## Identity

| Component | Value |
| --- | --- |
| Source | `master` at `5038258`, extracted to `acceptance_20261031/src`; `learning/checkpoints.py` and `learning/experiment.py` replaced with the fixed versions of #107/#109 before the re-entry |
| Native engine | `Battle for Wesnoth v1.18.8`, executable SHA-256 `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf` |
| Lite engine | `lite-0.2`, combat `expected_damage_v1`, RNG `deterministic_expected_damage_v1` |
| Rules | `data/rules/1.18.8/rules.json` `c769a4d62cd95ed96028cd8931e7030883547b12ec5972f194ef9272741a9021`, catalog `a1f366ea93e00a5f4fa7a2a2ea9f2267b7bebaf1040c7828e81adcb19f9cac5a`, metric profile `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca` |
| Python / torch | `~/venv/bin/python`, torch 2.9.1+cpu, `maturin` build of `_engine_lite` |
| Seed / panel | `20261017`; `--formats duel --bc-games 40 1 1 --native-bc-games 0 0 0 --bc-batch-games 20 --bc-records 2048 --bc-validation-records 1024 --final-blocks 30 --engine lite --evaluation-engine native --workers 8 --trainer-threads 1 --device cpu --hours 0.25` |
| Run `a` | BC → forced PPO → stop/resume → evaluation; `selected.pt` = `last_ppo.pt` `8d44a306f10c66f25b193e3bad63f6ed763644b80f60573464b762fc9532fd11` |
| Run `b` | Twin, uninterrupted BC only; `latest.pt` at stop |
| Run `c` | Branch of `a` resuming the inherited checkpoint, final evaluation only |

Full flag set and per-run checkpoint digests: `identities.json`.

## Commands

| # | Command | Exit | Result |
| --- | --- | --- | --- |
| 1 | `python l1_drive.py src src/runs/l1-20261031 <wesnoth>` (run `a`: `run --phase bc --hours 0.25`, `phase ppo --force --reason …`, SIGINT/SIGKILL, `run --resume`, `phase evaluate`, `run --resume`) | 0 | BC, 9 PPO batches, clean stop and resume, evaluation requested |
| 2 | same driver, twin `b` (BC then SIGKILL at the batch boundary) | 0 | `bc_complete`, `same_future.json` written |
| 3 | `python l1_reeval.py src src/runs/l1-20261031/a src/runs/l1-20261031/c <wesnoth>` (branch, pin `a`'s selection, request `evaluate`, resume) | 0 | 60 final games, all faulted at the native action budget |
| 4 | `python native_repeat.py src native_repeat <wesnoth>` (one stock game twice, seed `20261017`) | 0 | `repeat.json` |
| 5 | `python -m unittest tests.v5.test_checkpoint_ops` (Windows reference, fixed code) | 0 | `Ran 6 tests … OK`; reverted pin rule → `FAILED (errors=1)` |

## Results

| Case | Verdict | Counts / artifacts |
| --- | --- | --- |
| Smallest panel that reaches BC | PASS | 40/40 teacher games `complete`, 5 BC batches, 388 BC updates, `bc_gate.imitation.effective false` (duel accuracy 0.217, cross-entropy 3.261 vs uniform 4.533) — the reduced panel does not reach the BC gate and was forced into PPO with a recorded reason |
| ≥2 applied PPO updates | PASS | 9 PPO batches with 4–8 updates each, `policy_sha256_after` per batch in `a/duel-state.json` |
| Stop/resume from a committed batch | PASS | Stopped at `applied=4`, `pending_train=None`, version 9; resume continued at batch 9 and finished `ppo_complete` at version 14 with the 9 batches recorded, no recomputation of batches 5–8 |
| Final-evaluation entry | PARTIAL | `phase evaluate` accepted, `final_evaluation()` ran to `stage=finished` and wrote `c/duel-summary.json`, but all 60 games faulted |
| Final evaluation usable | FAIL | 60/60 `watchdog_timeout`, `turns 1`, `faults {"1": "watchdog timeout: candidate evaluation/execution"}`, `blocks 0/30`, `status inconclusive` |
| Resume reproduces the uninterrupted future | NOT VERIFIABLE | 40 shared teacher ids, 0 identical payloads; a same-seed native game disagrees with itself |

### Stop/resume trace (`timeline.log`)

```
00:59:29 BC start   →  01:14:39 BC exit at budget, stage bc_complete, effective False
01:14:39 phase ppo rejected: "duel: BC gates not passed; use --force --reason …"
         forced request 2899a23ac1214967be402b3eff4b8549 ("L1 reduced panel: …")
01:19:21 four PPO batches applied → SIGINT ignored → 01:22:21 SIGKILL, rc -9,
         applied=4 pending=None stage=ppo version=9   (boundary.json)
01:22:21 resume  →  01:30:11 applied=8 with a pending batch  →  01:30:12 phase evaluate
01:31:32 stage=finished, run `a` status=infrastructure_error (the 16 MiB defect, #107)
01:31:32 twin `b` BC   →  01:46:42 bc_complete, 4 BC batches, no PPO
01:46:54 compare: batches [9, 10, 11, 12, 13] identical=False
02:23:32 run `c`: branch resumed, phase evaluate, stage finished, status inconclusive
```

### Why the final evaluation produced no scored game

`vendor/arena/params.py:6` freezes `ACTION_TIMEOUT = 1.0` s and `FIRST_TIMEOUT = 10.0` s; `vendor/arena/runtime/candidate.lua:26` reports the budget it will be judged against as `CALL {budget=s.first and options.first_timeout or options.timeout}`. In `final-baseline-duel-b0001-solo-r0`:

```
{"event": "CALL",    "data": {"budget": 10, "first": true,  "phase": "evaluation", "side": 1}}
{"event": "RETURN",  "data": {"budget": 10, "elapsed_ms": 1946, "first": true, "phase": "execution", "side": 1}}
{"event": "CALL",    "data": {"budget": 1,  "first": false, "phase": "evaluation", "side": 1}}
```

One decision of the exported Lua policy costs ≈1.9 s; every decision after the first is judged against 1 s, so the seat faults on its second decision in all 60 games. The exporter declares `candidate_budget_ms=200` for candidate generation only (`learning/export.py:62`), which does not bound model inference. This is an open product gap, not a harness setting: raising the timeout would change the frozen competition profile.

### Why the same-future clause cannot be evaluated

Twin `b` played the same 40 teacher job ids with the same seeds — `learning/schedule.py:152` derives them as `random.Random(seed + batch_index)` and recomputing `random.Random(20261017+0).randrange(2**32)` × 5 gives `1204705257, 1880560222, 2849613072, 757251961, 2203277602` — the same map (`map_sha256 654da578da1aa8499f0c1c7f7735c59cfe13737382ebd946d3e021509e998cc4`), the same teacher identity and no truncation (`Counter({None: 40})`), yet **0 of 40** decompressed payloads match:

| job | run `a` records | run `b` records |
| --- | --- | --- |
| `stock-00000-duel-t0` | 20 | 19 |
| `stock-00002-duel-t0` | 75 | 22 |
| `stock-00003-duel-t0` | 377 | 249 |
| `stock-00005-duel-t0` | 190 | 222 |

`native_repeat.json` isolates the cause: one stock game played twice from the identical seed ends at turn 5 and turn 3 (`events_equal false`, 12 vs 7 decisive events). Native play is therefore not reproducible from its recorded identity, so an uninterrupted twin cannot share the stopped run's future and the clause stays unverifiable until native games are deterministic.

## Reuse

No prior L1 evidence is reused; `verification/acceptance_20261030/` holds only the curator and bundle results. PR #107 and #109 were verified on this host and merged as `6bf23a0` and `6f702f3`.

## Failure

| Defect | Symptom | Fix |
| --- | --- | --- |
| Submission cap reapplied to a bot directory (`vendor/arena/match.py:124`) | Every final game `infrastructure_error ValueError('submission exceeds 16 MiB')`; add-on tree 16,888,443 B | `vendor/arena/addons.py:contestant` keeps the cap for zips only; PR #107, merged `6bf23a0` |
| Branch resume rejected its inherited checkpoint (`learning/experiment.py:204`) | `ValueError: manifest changed`, then `ValueError: resume cannot reset shared budget`; `Experiment: partial_failure` | `checkpoints.inherited_checkpoint`/`resume_pins` plus `experiment.validate_resume`; PR #109, merged `6f702f3` |
| Exported policy slower than the native action budget | 60/60 `watchdog_timeout` at `turns 1` | **open**, not fixed here |

## Resources

10 BC games batches over 15 min of wall clock per phase budget; 76 environment games in `a` (40 teacher, 36 PPO); 60 final games in `c`; 8 workers, 1 trainer thread, CPU only, no GPU; the four L1 runs together used ≈2.2 GB of run directory before the evidence was trimmed to 2.1 MB.

## Gate

Blocked for any strength statement: the reduced panel is inconclusive by construction, and the native final evaluation currently cannot score a lite policy at all. Not blocked: the lite training loop itself, whose stop/resume and batch bookkeeping are proven above.

## Limits

- One format (duel), one seed, one short panel: nothing here measures quality, convergence or strength.
- `b` never entered PPO on its own, so the twin comparison covers BC teacher games only; the PPO stage was compared through the branch in `c`, which reproduced `a`'s history byte-for-byte but is not an independent run.
- The final evaluation measured the exported Lua policy's latency, not its strength; no compliant game exists yet.
- Scheduled 30-minute polling was not exercised; the driver polled each phase every few seconds to enforce the stop boundary.
