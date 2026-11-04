# Strict bounded-loop confirmation on Ubuntu

**FAIL at the team final panel.** All three formats passed fresh ordinary BC, committed PPO work before and after resume, completed their due trend games and froze their v3 selections. The duel and FFA panels completed all 30 blocks. Team completed 25/30 blocks and 209/240 games. The driver exited 1 before export, leaving package generation and sequence parity **NOT RUN**. [Prelaunch profile](PLAN.md)

From 08:51:55.845 to 09:17:51.039 Asia/Shanghai on 2026-11-04, the driver took 25m55.19s. All four stage subprocesses exited 0 without an external kill. The driver rejected the final report when the ordinary evaluation phase deadline left the team panel incomplete.

| Stage | First strict run | Confirmation | Confirmation result |
| --- | ---: | ---: | --- |
| Calibration and ordinary BC | 117.06 s | 94.04 s | Three new effective v1 checkpoints |
| First PPO request | 213.13 s | 159.10 s | Three new v2 checkpoints |
| Resumed PPO request, including periodic validation | 433.38 s | 433.39 s | Three new v3 checkpoints and all 18 due trend games |
| Frozen final evaluation | 865.84 s | 865.88 s | 389/420 games, 85/90 blocks |
| Audited export | NOT RUN | NOT RUN | No export command, delivery package or parity errors |

Both runs had a 1,200-second BC ceiling, two 450-second PPO ceilings, a 900-second final ceiling, a 300-second export ceiling, and an outer timeout of 3,600 seconds. The final phase request used .24 hours (864 s). The confirmation completed 102 more final games and 14 more blocks in essentially the same final-stage time. The original finished 287 games, interrupted eight in progress and never started 125. This run finished 389, interrupted eight in progress and never started 23. The final scheduler recorded 6,892.36 occupied worker-seconds across 397 started games, compared with 6,891.92 across 295 starts previously. [First strict result](../bounded_loop_strict_20261104/REPORT.md)

## Ordinary BC and committed PPO

The child calibrated on the single fixed Astra route and reused the compatible v6 weights, 56/48/48 teacher games and four duel DAgger shards. The 24/24/24 teacher target was already met, and all three child BC schedules were empty. Each child nevertheless started a fresh Adam, committed its own BC updates and recomputed the original corpus, coverage, imitation and scenario gates. The reused validation families had influenced the parent checkpoint selection. [Parent readiness](../bc_ordinary_v6_20261103/REPORT.md)

| Format | Child BC steps | Teacher coverage, matched / total | Distinct scenarios | Held-out decisions, accuracy | Exact recruit / move / attack | CE / uniform |
| --- | ---: | ---: | ---: | --- | --- | --- |
| Duel | 56 | 5,533 / 6,128 | 31 | 749, 56.88% | 91/134 · 210/310 · 95/253 | 2.7333 / 3.5650 |
| FFA | 64 | 8,278 / 9,133 | 39 | 674, 66.91% | 47/75 · 169/257 · 142/245 | 1.2528 / 3.5506 |
| Team | 56 | 11,034 / 11,836 | 47 | 1,011, 62.51% | 48/78 · 428/621 · 76/183 | 1.3246 / 3.5769 |

| Format | First PPO applied / planned steps | Resumed PPO applied / planned steps | Cumulative optimizer steps at BC → first PPO → resume | Completed first / resumed rollout games | First / resumed turn-limit games |
| --- | ---: | ---: | --- | --- | --- |
| Duel | 4 / 12 | 4 / 8 | 56 → 60 → 64 | 4 / 4 | 0 / 0 |
| FFA | 7 / 16 | 14 / 16 | 64 → 71 → 85 | 4 / 4 | 4 / 4 |
| Team | 10 / 16 | 7 / 16 | 56 → 66 → 73 | 4 / 4 | 3 / 4 |

The original strict handoff verifier ran unchanged against this run. Each of the nine retained checkpoints matches its phase snapshot and pins the confirmation manifest. Both unforced requests preserve preceding committed history and add a batch of four distinct eligible rollouts per format. Each of the 24 raw jobs has one scheduler start, one finish, one complete result and zero faults. Their new shard identities, optimizer-counter deltas and changed model tensors agree with the two boundaries. All nine checkpoint states have empty pending training, validation and error fields. This establishes continuation without repeating committed work within the observed run. [Exact IDs and checkpoint hashes](handoffs.json) · [Reused verifier](../bounded_loop_strict_20261104/check_handoffs.py)

## Due trend and optional references

At v3 the real trend completed 18/18 games. The previous strict attempt completed 11/18, including only one team game. The ordinary trend design provides three blocks for duel and one each for FFA and team. The one-block FFA and team trends scored their games and reported `insufficient_design` at the three-scenario minimum.

| Format | Trend games / planned | Trend blocks / planned | Distinct trend scenarios | Trend status | Reference games / planned | Turn limits, trend / references |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| Duel | 6 / 6 | 3 / 3 | 3 | `not_passed` | 12 / 12 | 0 / 1 |
| FFA | 4 / 4 | 1 / 1 | 1 | `insufficient_design` | 12 / 12 | 4 / 10 |
| Team | 8 / 8 | 1 / 1 | 1 | `insufficient_design` | 11 / 12 | 6 / 4 |

The twelfth team reward reference started and returned `budget_interrupted`. This interruption occurred after completion of the due team trend. The optional control reports were inconclusive in all formats, with 2/0/0 accepted validation blocks for duel/FFA/team. No recorded trend or reference gameplay fault occurred.

## Frozen final selections and 420 raw results

All three formats had no retained champion and froze their fallback `last_ppo.pt` v3 before holdout. The selected bytes, source checkpoint, selection record and final report SHA256 agree. Their model tensors match the corresponding resumed PPO boundary. Each final control was the frozen Lite Astra.

| Format | Completed / planned | Completed at turn limit | Interrupted after start | Never started | Scored blocks / 30 | Distinct scored scenarios | Comparison |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Duel | 60 / 60 | 5 | 0 | 0 | 30 | 30 | `inconclusive` |
| FFA | 120 / 120 | 39 | 0 | 0 | 30 | 15 | `not_passed` |
| Team | 209 / 240 | 104 | 8 | 23 | 25 | 15 | `inconclusive` |
| **Total** | **389 / 420** | **148** | **8** | **23** | **85 / 90** | | |

All 420 schedule IDs have one raw result, and the final gameplay fault count was zero. Each of the 397 started games has one scheduler finish. Every unstarted game has a `budget_interrupted` result. Team completed 106/120 Astra-partner games, with three active interruptions and 11 unstarted. It completed 103/120 self-team games, with five active interruptions and 12 unstarted. Those contexts reached the turn limit in 47 and 57 completed games respectively. Zero-based blocks 25 and 26 completed seven and two of their eight games. Blocks 27–29 had no completed games.

| Format | Selected v3 checkpoint SHA256 |
| --- | --- |
| Duel | `2584b2dfb948f0cfc28ac662b4eb07480ed291ca53fc4d3da5cee51115e4b8d1` |
| FFA | `12e9581ec92bcf2abfd3cc6a93b966f8fe5def76bd66f4ef6796a192ea6934ee` |
| Team | `ade92e4935e6543e2596f828ec26f780901fd746930cbe382a3c39199137ff27` |

## Run identity and archival

The committed source was `7889264e74a5151ebd21d7185f7b220662818c37`. The source archive SHA256 was `86478fe5f163210d58a56f5e4044e31437da00e10a8d5749381437611a1b3b9a`. The child manifest SHA256 was `5244f326ad3b2df1ecd8dad8178525c36dfe90c045dc28fe45491b80baa2a25b`. The release extension was `fa0519eb3e5c8eced558e00598046950ae2edb8a2c0cd5f9352ccf7f84a13d69`, the rules `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` and the v6 teacher `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5`. The archived `inputs.sha256` pins the parent manifest and all three inherited weights. The host used Python 3.12.3, PyTorch 2.9.1+cpu, seed 20261101, eight shared workers, one numerical thread per trainer, 30 training turns and validation interval 3.

The confirmation reused the byte-identical launch and capture scripts from the first strict run. The wrapper executed `timeout --signal=TERM --kill-after=15s 3600 /home/tongshu/venv/bin/python -u tests/bounded_training_loop.py`. The full child commands and independent phase deadlines are in the archived stage JSON and request logs. [Launch wrapper](../bounded_loop_strict_20261104/metadata/launch.sh) · [Capture script](../bounded_loop_strict_20261104/metadata/capture.sh)

```sh
base=/home/tongshu/acceptance
root=$base/bounded_loop_v6_confirmation_20261104
meta=$base/bounded_loop_confirmation_metadata_20261104
bash "$base/launch-bounded-v6.sh" bounded_loop_v6_confirmation_20261104 \
  7889264e74a5151ebd21d7185f7b220662818c37 \
  86478fe5f163210d58a56f5e4044e31437da00e10a8d5749381437611a1b3b9a \
  "$base/reach_public_green_20261104/.extension"
# After the terminal driver.exit (1) and process exit:
sh "$base/capture-bounded-loop.sh" "$root" "$meta"
(cd "$meta" && sha256sum -c SHA256SUMS)
(cd "$root" && tar -dzf "$meta/run_metadata.tar.gz" && sha256sum --quiet -c "$meta/artifacts.sha256")
cd "$root"
PYTHONPATH=.extension:.:vendor/arena OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /home/tongshu/venv/bin/python -B "$base/bounded_strict_handoffs_20261104/verification/bounded_loop_strict_20261104/check_handoffs.py" . \
  > "$meta/handoffs.json"
```

The capture ran once after exit. All 116 metadata members (9,965,870 original bytes, 514,691 compressed bytes) matched the terminal source and all 69 checkpoint/shard hashes verified on Ubuntu. The received tar, member list and artifact inventory matched their original SHA256 values. The metadata tar SHA256 is `ca30988ac2934fb59f2dbec31238aa83f2ed6ad202aece122fdffa44c964a6ac`. The independent nine-checkpoint verification exited 0 and its JSON SHA256 is `6f5f6bd5c71cd6858d9b5fc5155fe10162d1c8c87992b75814bb435313f70676`. [Original metadata archive](metadata/run_metadata.tar.gz) · [Members](metadata/members.txt) · [Checkpoint and shard digests](metadata/artifacts.sha256) · [Metadata checksums](metadata/SHA256SUMS)
