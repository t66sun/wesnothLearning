# Strict all-format bounded loop on Ubuntu

**FAIL at final evaluation.** The run completed ordinary BC and two separately requested PPO phases in all three formats. It scored 287 of 420 scheduled final games and completed 71 of 90 required blocks. Duel completed its panel. FFA missed two blocks and team missed 17. The driver exited 1 before export. L2 remains open.

The driver ran for 27m12.24s on 2026-11-04, from 07:42:15.056 to 08:09:27.299 Asia/Shanghai. The stage processes all exited 0, with no external stage kill. The trainer's evaluation deadline interrupted games before the stage's 900-second ceiling. The driver then rejected the incomplete reports.

| Stage | Elapsed | Declared stage ceiling | Observed outcome |
| --- | ---: | ---: | --- |
| Warm-start BC including calibration | 117.06 s | 1,200 s, five committed batches | Three new ordinary gates passed |
| First PPO request | 213.13 s | 450 s, four batches | One applied batch per format |
| Resumed PPO request and periodic validation | 433.38 s | 450 s, four batches | One further applied batch per format. Team's validation panel was incomplete |
| Frozen final evaluation | 865.84 s | 900 s | Incomplete FFA and team panels |
| Audited export | NOT RUN | 300 s | The driver stopped at its panel check. No package or sequence-parity result was produced |

## Calibration and ordinary BC

Each child started from the compatible v6 parent weights, its checkpoint-owned 56/48/48 teacher games and four duel DAgger correction shards. It used the single fixed Astra calibration route, fresh Adam state, child counters and the original scenario-family train/validation split. The three BC batch schedules contained zero new games. The existing corpus met the 24/24/24 target. The retained validation families had already influenced parent checkpoint selection. [Parent artifacts and provenance](../bc_ordinary_v6_20261103/REPORT.md) · [Initialization checks](../bc_branch_restart_20261104/REPORT.md)

| Format | New BC steps | Eligible teacher games / target | Coverage, matched / total | Distinct scenarios | Held-out rows | Accuracy | CE / uniform |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Duel | 56 | 56 / 24 | 5,533 / 6,128 | 31 | 749 | 56.88% | 2.7333 / 3.5650 |
| FFA | 64 | 48 / 24 | 8,278 / 9,133 | 39 | 674 | 66.91% | 1.2528 / 3.5506 |
| Team | 56 | 48 / 24 | 11,034 / 11,836 | 47 | 1,011 | 62.51% | 1.3246 / 3.5769 |

| Format | Recruit exact | Move exact | Attack exact | Coverage by class, recruit / move / attack |
| --- | ---: | ---: | ---: | --- |
| Duel | 91 / 134 | 210 / 310 | 95 / 253 | 801/919 · 2,400/2,597 · 1,658/1,938 |
| FFA | 47 / 75 | 169 / 257 | 142 / 245 | 804/908 · 3,421/3,702 · 2,735/3,205 |
| Team | 48 / 78 | 428 / 621 | 76 / 183 | 719/794 · 6,918/7,388 · 1,967/2,224 |

Each v1 checkpoint records one child BC batch and a true effective gate. The corpus, candidate coverage, held-out imitation and scenario design all passed. The original opening field reads `passed=false, blocking=false`.

## Two committed PPO handoffs

| Format | First PPO applied / planned steps | Resumed PPO applied / planned steps | Cumulative optimizer steps at BC → first PPO → resume | Completed rollout games, first / resumed | Turn-limit outcomes, first / resumed |
| --- | ---: | ---: | --- | --- | --- |
| Duel | 4 / 12 | 4 / 8 | 56 → 60 → 64 | 4 / 4 | 0 / 0 |
| FFA | 7 / 16 | 14 / 16 | 64 → 71 → 85 | 4 / 4 | 4 / 4 |
| Team | 10 / 16 | 7 / 16 | 56 → 66 → 73 | 4 / 4 | 3 / 4 |

The first request consumed rollout batch 1 and committed v2. The resumed request consumed batch 2 and committed v3. The remaining planned optimizer steps stopped at the ordinary KL guard. Each of the 24 eligible PPO jobs has one frozen schedule entry, one scheduler start, one finish and one complete raw result, with zero faults. Each phase added its own four rollout shards per format. The resumed checkpoint preserves the entire preceding committed history and its counter deltas equal the appended entries. Model tensors changed in each PPO phase. All nine intermediate checkpoint runner states match the stage JSON snapshots and pin the child manifest. Each BC/PPO boundary has empty pending training, validation and error fields. Both PPO requests were unforced. These checks cover continuity and new work across this actual resume. [Handoff hashes and IDs](handoffs.json) · [Partial-run verifier](check_handoffs.py)

## Periodic validation during the resumed phase

Validation interval 3 scheduled the ordinary trend panel and reward references after v3. The subsequent PPO phase completion record cleared the pending request for each format. Raw schedules and results establish how much validation actually finished.

| Format | Trend games complete / planned | Scored blocks / planned | Distinct scored scenarios | Status | Reference games complete / planned | Turn limits, trend / reference |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| Duel | 6 / 6 | 3 / 3 | 3 | `not_passed` | 12 / 12 | 0 / 1 |
| FFA | 4 / 4 | 1 / 1 | 1 | `insufficient_design` | 12 / 12 | 4 / 10 |
| Team | 1 / 8 | 0 / 1 | 0 | `inconclusive` | 0 / 12 | 0 / 0 |

All eight team trend games started. One Astra-partner game completed and seven games reached their deadline. All 12 team reference results were `budget_interrupted` before worker start. No trend or reference game recorded a gameplay fault. Each format's reward-control report was inconclusive with zero accepted validation blocks.

## Selection and final panel

All formats selected the fallback last PPO v3 because there was no retained champion. Each `selection.json` records `frozen_before_holdout=true`. The actual `selected.pt`, `last_ppo.pt`, selection and final report SHA256 agree. The selected model tensors match the resumed PPO boundary. The final control in each format was the frozen Lite Astra.

| Format | Scheduled | Complete | Complete at turn limit | Interrupted after start | Interrupted before start | Scored blocks / planned | Distinct scored scenarios | Selected checkpoint SHA256 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Duel | 60 | 60 | 5 | 0 | 0 | 30 / 30 | 30 | `473cabb568edc1ea4644c7f490ec860e6b7be0f49a305c83521feac55ccd9816` |
| FFA | 120 | 114 | 38 | 4 | 2 | 28 / 30 | 15 | `11df49191e9c863fd3740a1a5b326bd64a51e2849e607776bef2f999c1edf89c` |
| Team | 240 | 113 | 54 | 4 | 123 | 13 / 30 | 13 | `69d2dc94b2598ea94374bda8dfb144994fb949dd531a39f9ca806ee69d851248` |
| **Total** | **420** | **287** | **97** | **8** | **125** | **71 / 90** | | |

All 420 scheduled IDs have a result and the gameplay fault count is zero. An interruption before start has a `budget_interrupted` result and no scheduler start. A started interruption has a start and finish. The 97 turn-limit games are among the 287 completed results. Each control's final comparison reported `inconclusive`. FFA completed two rotations in zero-based block 28 and none in block 29. Team completed 58/120 Astra-partner games and 55/120 self-team games, including 23 and 31 turn limits respectively. Team blocks 13 and 14 completed seven and two of their eight rotations. Blocks 15–29 had no completed rotations.

## Source and commands

The input archive was built from `7665583e9a57e1d754e6d53bb16bfd02e7d055cf` and had SHA256 `be8c80b8a51ac0d3d9ca4f67bfe9e1cce1445e79e72a01d2e5d5fc4ab71667d2`. The child manifest SHA256 is `f8a5886ac78286e874eaf6df49588b1a51aa73beefbcf928129df3fa15d8a757`. The run used Python 3.12.3 and PyTorch 2.9.1+cpu, eight shared Lite workers, one trainer thread per format, seed 20261101, 30-turn training and unchanged 2,048/1,024 BC train/validation row limits. The teacher was `probabilistic_combat_v6`, source `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5`, with the `work-12000-v8` candidate contract. The rules SHA256 is `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. The Lite extension SHA256 is `4d228e11e980ee3f91b93d79b71b9efbb429b8ea0eb3797bb18a2afbae512263`. The archive's `inputs.sha256` also pins the entropy shim, Wesnoth executable, parent manifest and three parent checkpoints.

The original launch invocation below names its fresh run directory. The wrapper links the rules and extension, builds the shim, pins the libraries to one thread, and records the clocks, inputs and process exit. Its outer timeout was `timeout --signal=TERM --kill-after=15s 3600 /home/tongshu/venv/bin/python -u tests/bounded_training_loop.py`. [Original launch wrapper](metadata/launch.sh)

```sh
bash /home/tongshu/acceptance/launch-bounded-v6.sh bounded_loop_v6_strict_20261104 \
  7665583e9a57e1d754e6d53bb16bfd02e7d055cf \
  be8c80b8a51ac0d3d9ca4f67bfe9e1cce1445e79e72a01d2e5d5fc4ab71667d2 \
  /home/tongshu/acceptance/lite_lua_cost_20261104/fast/.extension
```

The actual BC command is recorded in `verification/bounded_loop_observed/bc.json` inside the metadata archive. The runner submitted two `phase ppo --hours .12 --ppo-batches 1` requests and one `phase evaluate --hours .24` request. Each request was followed by `python -u -m learning run --resume RUN`. The archived plan, request logs and stage JSON contain the command arguments, result and timing.

## Archive verification

After the driver exited 1 and its PID disappeared, the read-only capture ran once into a fresh sibling directory. The archive has 116 regular members, 9,489,383 uncompressed bytes and 495,010 compressed bytes. It includes all run and stage JSON/JSONL/logs, the outer exit and command logs, identities and timestamps. The 69 checkpoint and child shard files listed in the SHA inventory remain on Ubuntu. Direct tar comparison against the terminal source directory and all 69 artifact hash checks passed. After transfer the tar member names and three metadata digests matched the original inventories. [Original compressed metadata](metadata/run_metadata.tar.gz) · [Member list](metadata/members.txt) · [Artifact hashes](metadata/artifacts.sha256) · [Metadata checksums](metadata/SHA256SUMS) · [Capture command](metadata/capture.sh)

```sh
base=/home/tongshu/acceptance
root=$base/bounded_loop_v6_strict_20261104
meta=$base/bounded_loop_strict_metadata_20261104
sh "$base/capture-bounded-loop.sh" "$root" "$meta"
(cd "$meta" && sha256sum -c SHA256SUMS)
(cd "$root" && tar -dzf "$meta/run_metadata.tar.gz" && sha256sum --quiet -c "$meta/artifacts.sha256")
```

The handoff verifier ran from source `31f7c2a27c94781f2b0ef3310b3aca67d459eb31` in a separate fresh directory and read the strict run in place. The two-script verification archive SHA256 was `8837ae4099d14e46206ded05606c26f966e06ccc7e670eab634070cb96ce2f0f`. Its output SHA256 was `c3ad7d868f16afd30444458672e573cf1a72cd4b1a3e01cfd594977c8eeb42f2`.

```sh
cd "$root"
PYTHONPATH=.extension:.:vendor/arena OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /home/tongshu/venv/bin/python -B \
  ../bounded_strict_handoffs_20261104/verification/bounded_loop_strict_20261104/check_handoffs.py .
```
