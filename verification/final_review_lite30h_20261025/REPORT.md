# Final review, budget acceptance and fresh 30-hour training — 2026-10-25

User instruction: final static review, then create/start one new 30-hour server run if clear. The user separately authorized the six exact SCP/SSH/status/evidence commands recorded below. This supersedes the earlier no-training scope for this new run only.

## Review and accepted change

Standards and specification review of `ab4fa33..4e9e0dd`, followed by the focused budget and launch-script review, found no actionable defect. Architecture §10.12 required a frozen nomination/holdout schedule before new P5b training. PR [#39](https://github.com/t66sun/wesnothLearning/pull/39) adds only an opt-in `final_holdout_hours` reserve; total deadline, training quotas, rewards and quality/promotion gates remain unchanged. Default/legacy reserve is zero. See `STATIC_REVIEW.md` and the bilingual maintained documents.

The fresh run reserves 25 hours updates, one hour nomination and four hours holdout inside the original 30-hour clock. Historical 420-game final evaluation took 36m53 in `../model_strength_20261024_2120/REPORT.md`; this is the allocation basis, not a throughput guarantee. Nomination still needs complete V1 evidence; otherwise it retains the champion. Holdout never selects the candidate.

| Check | Result | Evidence / limit |
| --- | --- | --- |
| Added reserve assertions before implementation | FAIL, one parser error and one boundary failure | `reserve_before.log`, two tests |
| Affected local reference checks | PASS, six in 7.097s | `reserve_local.log`; Windows reference only |
| Launch CLI/config, shell/Python syntax, UTF-8 docs, line caps/diff | PASS | Local preparation; two unchanged grandfathered test files excluded from line cap |
| Ubuntu affected checks | PASS, six in 1.760s; process wall 2.71s; peak RSS 307192 KiB; exit 0 | `ubuntu/preflight.log`; synthetic/recorded schedules, zero real games |
| V1–V6 repair checks | REUSED, 12 Ubuntu checks | `../refactor_repairs_20261025/REPORT.md`, original identities and limitations |
| Unchanged engine/refactor checks | REUSED, original 273 Python / 17 stage / 13 Rust results | Same prior report and original acceptance; not a new full-suite run |
| Full-board new teacher/forecast/stage contract, strength/convergence, native acceptance | NOT RUN / unaccepted as recorded previously | Startup does not close these scopes |
| SDK package assembly size gate | Prior FAIL retained | Not rerun; internal training exports use `package=False` |

## Frozen identities

- Source: `822082d654cd19a6474aa36f837137c1ec7cb83c` (merged PR #39; implementation commit `13f4e10ea69666011cadced5bc5fab62487cc99a`).
- Deployed archive SHA-256: `4e32bb063a9c53fd403bf1d93a1bcb21c8bafe1b38d62239e8834e9161ac2ce4`. `git archive` of learning/lua/vendor/arena/engine_lite/benchmarks/tests and the two launch scripts; frozen inputs excluded.
- Manifest SHA-256: `aabd9fac77292a5234a5995eed71d8d9d3a12bfd92c24e115a098655f210b437`. All recorded source files match the actual deployed archive byte-for-byte. An initial direct comparison to Git blobs differed on `vendor/arena/run_arena.bat` only because archive CRLF conversion adds four bytes; normalized bytes match. Archive bytes are the frozen runtime identity.
- Ubuntu Linux 7.0.0-38, Python 3.12.3, torch 2.9.1+cpu; existing extension `lite-0.2`, `deterministic-expected_damage_v1`, combat `expected_damage_v1`. No rebuild of unchanged Rust/Lua/teacher sources.
- Catalog SHA-256: `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`.
- Teacher: gpt6astra / `expected_damage_v1`, source `a5d4b3a69d5af0378fa22119f315c1300fb6ad965c79b08071eb4a37c0addbef`.
- Native baseline `--version` identifies 1.18.8; baseline executable hash, dependencies, complete source and teacher lineage are in `ubuntu/manifest.json` and `ubuntu/predeclared.json`. No native games launched.

## Deployment and clock

Isolated source: `/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source`.

New run: `runs/v5_lite30h_20261025` inside that source. Main PID and session ID: **225153**. `subprocess.Popen(start_new_session=True)` detaches stdin/stdout/stderr from SSH; subsequent independent status reads verify survival. No restart wrapper or automatic retry is installed.

Only rules and opponents are symlinked read-only from the provision recorded by the earlier acceptance. Rules resolve canonically to `/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8-training`; the hash above is verified. New `data/datasets/human` starts empty, and new teacher/on-policy output remains in the fresh namespace. Old models, datasets, runs and manifests are untouched. No parent weights, optimizer, RNG or clocks are imported.

Frozen config: CPU, lite collection/evaluation, duel/ffa4/team2v2, eight shared game workers, one thread per trainer; seed 20261017; BC game targets 300/600/400, zero native anchors; batch games 8, rollout games 4, four epochs, minibatch 256, BC train/validation limits 2048/1024; adaptive reward mode, validation every 10, final 30 blocks, auto phase with all original BC/PPO gates. No forced PPO. Actual complete config is in `ubuntu/manifest.json`.

All following times are Asia/Shanghai, derived from the downloaded clock:

| Boundary | Time |
| --- | --- |
| Started | 2026-10-25 14:40:27.990259 |
| Update deadline (25 hours) | 2026-10-26 15:40:27.990259 |
| Nomination deadline (26 hours) | 2026-10-26 16:40:27.990259 |
| Original total deadline (30 hours) | 2026-10-26 20:40:27.990259 |

Thirty hours is the total cap, not a promise to update for 30 hours or reach PPO. Final evaluation may finish earlier. This report records startup only; completed-run outcomes require future observation.

## Authorized commands and runtime evidence

Executed from `C:\dev\WesnothLearning`, all exit 0:

```powershell
scp tmp/wesnoth-lite30h-20261025.tar cpuServer:/tmp/wesnoth-lite30h-20261025.tar
scp verification/final_review_lite30h_20261025/launch.sh cpuServer:/tmp/wesnoth-lite30h-20261025.sh
ssh cpuServer "bash /tmp/wesnoth-lite30h-20261025.sh 822082d654cd19a6474aa36f837137c1ec7cb83c 4e32bb063a9c53fd403bf1d93a1bcb21c8bafe1b38d62239e8834e9161ac2ce4"
ssh cpuServer "bash /tmp/wesnoth-lite30h-20261025.sh status"
scp "cpuServer:/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/logs/*" verification/final_review_lite30h_20261025/ubuntu/
scp cpuServer:/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/runs/v5_lite30h_20261025/manifest.json cpuServer:/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/runs/v5_lite30h_20261025/clock.json verification/final_review_lite30h_20261025/ubuntu/
```

`launch.sh` verifies archive identity, refuses existing destination, checks environment and runs `/usr/bin/time -v /home/tongshu/venv/bin/python -B -m unittest -v tests.v5.test_final_budget tests.v5.test_final_nomination`. `pipefail` prevents launch on any failed check. The full training argv/PID/time are in `ubuntu/launch.json`; source/env/config/memory snapshot in `ubuntu/predeclared.json`; console output in `ubuntu/deploy_console.log`. The status command is repeated only for this startup confirmation, with separate numbered snapshots. Initial snapshots show first collection in progress and correctly report `startup_ready=false`.

## Startup acceptance — PASS, 14:52:47 Asia/Shanghai

`ubuntu/status_09.json` confirms `alive=true` and `startup_ready=true` after SSH has returned. All three formats have real valid teacher games, completed collection batches, committed optimizer progress and larger/newer checkpoints than `status_01.json`. No format error or trainer error file is reported. Independent snapshots 01–09 preserve initial pending states instead of treating them as passed startup.

| Format | Stage / version | Valid teacher games | Settled collection batches | Committed optimizer steps | Committed decisions | latest.pt bytes |
| --- | --- | --- | --- | --- | --- | --- |
| duel | BC / 3 | 32 | 3 | 76 | 18263 | 9423730 |
| ffa4 | BC / 1 | 16 | 2 | 40 | 8494 | 9420338 |
| team2v2 | BC / 1 | 8 | 1 | 36 | 9769 | 9418546 |

Job completion may precede settlement of its batch, so valid-game totals can exceed settled batches × 8. The above counters are observed values, not target extrapolations. All BC eligibility flags remain false at startup; no bypass/forced PPO was used. PPO, final selection, holdout results and completed 30-hour outcomes have not yet been observed. The task ends after verified startup; no recurring monitor or restart is installed. The existing detached process continues under its frozen deadline.

Updated bilingual TEST removes accepted B1 entirely and links here; remaining unwritten/unaccepted scopes stay in place. Bilingual architecture/instructions record current run/source/PID/clock and preserve previous runs as historical. Document links/UTF-8/diff and frozen archive/config/manifest comparisons passed locally; no additional model tests or games were launched for this evidence-only update.
