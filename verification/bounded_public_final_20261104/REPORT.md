# Ordinary gated bounded loop and audited export

**PASS for L2.** The Ubuntu run on `3b6bc0682fc887e062377fa955fdaccdaeb23203` earned fresh ordinary BC gates, committed PPO updates on both sides of a restart, completed the due trend and reward-reference games, froze three selections and scored all **420 final games in 90 complete blocks**. The package export passed the existing sequence-parity test for all three selected policies. The independent post-run auditor ran once and exited 0. [Prelaunch plan](PLAN.md) · [Joined checkpoint, job and package evidence](handoffs.json)

The driver ran from **10:09:10.889 to 10:37:55.268 Asia/Shanghai on November 4, 2026**, a wall time of **28m44.38s**. The driver returned `OBSERVED` and exited 0. Every stage subprocess exited 0 with no external stop. The previous confirmation reached 389/420 final games and stopped before export. This run completed its own frozen panel and export. [Previous confirmation](../bounded_loop_confirmation_20261104/REPORT.md)

| Stage | Wall seconds | Internal allocation / external ceiling | Reached |
| --- | ---: | --- | --- |
| Single-Astra calibration and ordinary BC | 94.05 | 1,152 / 1,200 s, five committed batches | New v1 checkpoint in every format |
| First PPO request | 173.10 | 432 / 450 s, four batches | One applied batch per format, v2 |
| Resumed PPO and periodic validation | 404.36 | 432 / 450 s, four batches | One further applied batch per format, v3 |
| Frozen final evaluation | 851.87 | 864 / 900 s | 60 duel, 120 FFA and 240 team games |
| Sequence audit and package export | 198.20 | 300 s external ceiling | Three selected weight sets in `NeuralArena.zip` |

The predeclared stage ceilings totalled 3,300 s and the outer timeout was 3,600 s. Eight shared workers reached a peak of eight final jobs in flight. Their start/finish intervals occupied 6,697.97 worker-seconds over 847.50 s from the first final start to the last finish. The last worker finished **13.93 s before** the ordinary evaluation deadline.

## Calibration and ordinary BC

The run selected the single fixed Astra control. Each child initialized from compatible v6 parent weights and the parent's retained 56/48/48 teacher games (four additional duel DAgger shards), started a fresh Adam with zero child counters and made a new BC update. Each child BC schedule had zero new games because the inherited teacher corpus met its target of 24. The original scenario-family split was preserved, including the validation families used to select the parent weights. This tests warm-start operational readiness on that design. [Parent provenance](../bc_ordinary_v6_20261103/REPORT.md) · [Restart semantics](../bc_branch_restart_20261104/REPORT.md) · [Public-forecast compatibility of the 158-unit roster](../immutable_forecast_20261104/BOUNDED-COMPATIBILITY.md)

| Format | New optimizer steps | Teacher games / target | Overall label coverage | Distinct scenarios / minimum | Held-out decisions | Accuracy | CE / uniform |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Duel | 56 | 56 / 24 | 5,533/6,128 (90.29%) | 31 / 12 | 749 | 56.88% | 2.7333 / 3.5650 |
| FFA | 64 | 48 / 24 | 8,278/9,133 (90.64%) | 39 / 12 | 674 | 66.91% | 1.2528 / 3.5506 |
| Team | 56 | 48 / 24 | 11,034/11,836 (93.22%) | 47 / 12 | 1,011 | 62.51% | 1.3246 / 3.5769 |

| Format | Recruit exact | Move exact | Attack exact | Candidate coverage by class, recruit / move / attack |
| --- | ---: | ---: | ---: | --- |
| Duel | 91/134 | 210/310 | 95/253 | 801/919 · 2,400/2,597 · 1,658/1,938 |
| FFA | 47/75 | 169/257 | 142/245 | 804/908 · 3,421/3,702 · 2,735/3,205 |
| Team | 48/78 | 428/621 | 76/183 | 719/794 · 6,918/7,388 · 1,967/2,224 |

Each format read 2,048 training rows. The validation reader returned 804/703/1,024 rows before the multi-candidate filter. All three ordinary corpus, coverage, imitation and scenario-design gates passed with zero missing scenario rows. Each class had at least 32 held-out decisions. The recorded opening field remained `passed=false, blocking=false`.

## Committed PPO, resume and due validation

| Format | First applied / planned PPO steps | Resumed applied / planned PPO steps | Cumulative optimizer count, BC → first → resumed | Rollouts completed, first / resumed | Turn limits, first / resumed |
| --- | ---: | ---: | --- | ---: | ---: |
| Duel | 4 / 12 | 4 / 8 | 56 → 60 → 64 | 4 / 4 | 0 / 0 |
| FFA | 7 / 16 | 14 / 16 | 64 → 71 → 85 | 4 / 4 | 4 / 4 |
| Team | 10 / 16 | 7 / 16 | 56 → 66 → 73 | 4 / 4 | 3 / 4 |

Both ordinary PPO requests required one newly applied batch. The remainder of the planned optimizer steps stopped at the existing KL guard. For every format, the two requests committed rollout batches 1 and 2 with disjoint IDs and new shard sets. All 24 eligible jobs had one start, one scheduler finish and one complete raw result, with zero gameplay faults. The retained v1/v2/v3 checkpoint runner states matched their recorded boundaries and pinned the child manifest. Earlier history was identical in each succeeding checkpoint, the new counter deltas equalled the appended steps, and model tensors changed after each PPO phase. All boundaries had empty pending training, pending validation and error fields. Both phase requests were unforced. This establishes non-repetition and new progress in the observed resume.

At the interval-three validation boundary, **all 18 scheduled trend games and all 36 reward-reference games** completed with zero faults, interruptions or unstarted jobs. The optional reward-control reports remained inconclusive and recorded 2/0/0 accepted validation blocks for duel/FFA/team.

| Format | Trend games | Trend blocks / distinct scenarios | Trend status | Reference games | Trend / reference turn limits |
| --- | ---: | --- | --- | ---: | ---: |
| Duel | 6/6 | 3/3 blocks, 3 scenarios | `not_passed` | 12/12 | 0 / 1 |
| FFA | 4/4 | 1/1 block, 1 scenario | `insufficient_design` | 12/12 | 4 / 10 |
| Team | 8/8 | 1/1 block, 1 scenario | `insufficient_design` | 12/12 | 6 / 5 |

## Frozen selections and final scores

Each format had no retained champion and selected the fallback last PPO v3. Selection was frozen before holdout. The auditor compared the selected checkpoint digest with the selection record, final report and export metadata, and checked the final Lite worker's model tensors against that checkpoint. It joined every frozen block, seat rotation and teammate context to exactly one raw result and one scheduler start and finish.

| Format | Games / required | Complete blocks | Distinct scored scenarios | Turn-limit games | Policy / Astra score | Difference [95% interval] | Formal comparison |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| Duel | 60 / 60 | 30 / 30 | 30 | 5 | 1.4333 / 1.4833 | −0.0500 [−0.6500, 0.5500] | `inconclusive` |
| FFA | 120 / 120 | 30 / 30 | 15 | 39 | 0.4306 / 0.5736 | −0.1431 [−0.2292, −0.0556] | `not_passed` |
| Team | 240 / 240 | 30 / 30 | 15 | 122 | 0.8833 / 1.6083 | −0.7250 [−0.9875, −0.4500] | `not_passed` |

All controls met the 12-scenario minimum and recorded zero missing blocks and zero faults. There were 166 turn-limit results among the 420 completed games. Team played 120 games per context, with 52 Astra-partner turn limits and 70 self-team turn limits. Its reported score differences were −0.4000 and −1.0500 respectively. The scores are the existing format-specific Lite measures, including normalized rank for FFA. The complete panels establish the operational gate. The comparison results grant no native or positive-strength claim.

## Audited delivery

The final export used the real child `selected.pt` files, the three `runs/audit_inputs/<format>` links to their respective child data directories, and eight audit workers. The **9,377,120-byte** archive is `delivery/bounded_loop/NeuralArena.zip` inside the formal Ubuntu source directory. Its SHA256 is **`047db8d244bfb9244be620a1ba6cb5aee1e14b7f83fe3dc21a5b1973e0b39c28`**. The independent audit verified the zip digest and each packed Lua weight member against the delivery manifest.

| Format | Selected checkpoint SHA256 | Packed weight SHA256 | Python/Lua max error |
| --- | --- | --- | ---: |
| Duel | `bf713a2bef7c6553e7d9535f4af7998a6469e9d00abf4fd7f9c47b81147041fd` | `3a7f56cc5f376208bfb2b9f77ef3e3638cafaa94d9102e00dbd60dd33ae678b0` | 7.1054×10⁻¹⁴ |
| FFA | `20c5520b59effb1249dadeb31713846c7654a1c907591210c13763ebba719635` | `eac9410be034c696c3e997ebed51a3fe1b0ee5d324da556650c15955010a60ad` | 2.3093×10⁻¹⁴ |
| Team | `a2ac371f46a837f828eb658334159b5a7c0b8027792b269b3e5ff54e26894459` | `9a415caaa7f2f0fb936e486cd07415fd9ab6a4cf32418febc3bf99c28489ee90` | 2.1316×10⁻¹⁴ |

Each 776,178-parameter policy passed the unchanged 10⁻⁵ sequence-parity tolerance. A read-only count of all nonblank gzip JSONL rows under the export inputs resolved 48 distinct physical files. Each format supplied eight policy and eight DAgger teacher files. The unique-decision count groups by format, engine, game family, game, side, turn and decision index, so corresponding policy/DAgger records share a key. Uncovered teacher intents remain raw parity inputs. All rows had schema 6 and zero fault flags. Each format reached the 37-candidate budget. [Physical files, row counts and keys](audit-inputs.json)

| Format | Unique files | Policy rows | DAgger rows | Raw rows | Unique decision keys |
| --- | ---: | ---: | ---: | ---: | ---: |
| Duel | 16 | 1,024 | 1,024 | 2,048 | 1,024 |
| FFA | 16 | 1,849 | 1,849 | 3,698 | 1,849 |
| Team | 16 | 2,373 | 2,373 | 4,746 | 2,373 |
| **Total** | **48** | **5,246** | **5,246** | **10,492** | **5,246** |

## Inputs, commands and immutable evidence

The child manifest SHA256 was `c2c8811e615e40f9af8a4221e7e42d7121c3de167afbfed8634c66dd8189cb6d`. The source archive SHA256 was `f679b5af3586245a34c9bcf43a126528777c275e51be99b8fb1715395ec895f4`, the Lite extension `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4`, the `1.18.8-combat-filtered` rules `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` and the `probabilistic_combat_v6` teacher `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5`. The archived `inputs.sha256` additionally pins the entropy shim, Wesnoth executable, parent manifest and all three initial checkpoints.

The host used Linux 7.0.0-38-generic, Python 3.12.3 and PyTorch 2.9.1+cpu with eight available CPU workers and one thread per trainer and numerical library. Peak recorded trainer RSS was 1,149/1,401/1,560 MiB. The manifest fixed seed 20261101, 30 training turns, 30 final turns, four epochs, minibatch 256, and 2,048/1,024 BC train/validation row limits. The runner used the original `work-12000-v8` candidates and the 30-block final design. The prelaunch plan and parent inputs remain at their original identities.

The original launch and capture scripts matched their previous SHA256 values. The launch wrapper executes `timeout --signal=TERM --kill-after=15s 3600 /home/tongshu/venv/bin/python -u tests/bounded_training_loop.py`. The archived stage JSON records each expanded CLI invocation, exit, duration and format state. The BC phase used `--branch-from`, `--branch-restart-bc`, `--branch-reset-optimizer` and `--phase bc`. Both subsequent PPO requests used `--hours .12 --ppo-batches 1`, followed by `run --resume`. Final evaluation used `phase evaluate --hours .24` and another resume. Export used `--audit-workers 8` and named each child selection. [Launch wrapper](../bounded_loop_strict_20261104/metadata/launch.sh) · [Capture script](../bounded_loop_strict_20261104/metadata/capture.sh)

```sh
base=/home/tongshu/acceptance
root=$base/bounded_loop_public_final_20261104
meta=$base/bounded_public_final_metadata_20261104
bash "$base/launch-bounded-v6.sh" bounded_loop_public_final_20261104 \
  3b6bc0682fc887e062377fa955fdaccdaeb23203 \
  f679b5af3586245a34c9bcf43a126528777c275e51be99b8fb1715395ec895f4 \
  "$base/immutable_forecast_20261104/green/.extension"
# After driver.exit=0, OBSERVED, and termination of the driver and outer process:
sh "$base/capture-bounded-loop.sh" "$root" "$meta"
(cd "$meta" && sha256sum -c SHA256SUMS)
(cd "$root" && tar -dzf "$meta/run_metadata.tar.gz" && sha256sum --quiet -c "$meta/artifacts.sha256")
cd "$root"
auditor=$base/bounded_confirmation_auditor_20261104/verification/bounded_loop_evidence_20261104/audit.py
PYTHONPATH="$root/.extension:$root:$root/vendor/arena" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /home/tongshu/venv/bin/python -B "$auditor" "$root/runs/bounded_loop" \
  "$root/verification/bounded_loop_observed" "$root/delivery/bounded_loop" > "$meta/handoffs.json"
```

The read-only capture ran once into a fresh directory. All 119 terminal metadata members (10,157,001 original bytes, 537,444 compressed) matched the source run. All 70 checkpoint, shard and package inventory hashes verified on Ubuntu. The received tar, member list and artifact-hash file matched their original checksums. [Metadata tar](metadata/run_metadata.tar.gz) · [Members](metadata/members.txt) · [Artifact inventory](metadata/artifacts.sha256) · [Checksums](metadata/SHA256SUMS)

The staged auditor matched the exact source-commit script SHA256 `9d9f553284b6f7cd06049b0da92df2473ae80275de9160c2eeb472f448f152e3`. Its single invocation produced 6,545 bytes of JSON, empty stderr and exit 0. The output SHA256 was `e998e05ca6b2db656d1efbbd794321fb54361f5a83cd5b18d77ed9d81e3a7b10`. The separate physical-input count SHA256 was `2694e1d5e2d5044ee6b6ad848720028b5429d7f2fae816dc4255b33e80f845f5`. [Original auditor](../bounded_loop_evidence_20261104/audit.py)
