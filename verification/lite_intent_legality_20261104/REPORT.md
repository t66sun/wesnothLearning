# Single-intent Lite legality experiment

**The candidate missed its predeclared 5% whole-worker CPU threshold.** On one frozen team validation game, worker CPU went from 17.010085 to 16.737681 seconds, a 1.60% reduction. Wall time went from 17.012544 to 16.740340 seconds. The existing engine remains in production. [Raw traces and gate calculation](measurements.tar.gz)

The candidate validated a submitted action against the same movement, attack or recruitment rules used for the public legal list. A move reused its public search predecessors during execution. In a fixed two-actor Rust fixture, the existing step performed 2, 3, 2 and 2 public reach searches for end turn, move, attack and recruit respectively. The candidate performed 0, 1, 0 and 0. Astra execution took 3.616 CPU seconds in the original game and 3.240 in the candidate. Astra decision calls took 9.062 and 9.171 seconds. The counted improvement applied to only part of the complete worker cost. [Retained candidate source](https://github.com/t66sun/wesnothLearning/commit/2d9db4456c46a95f4b7be160ffd9a3097d5a4afc)

## Matched contract

- All 1,031 committed actions and ordered referee events matched SHA256 `3a0ddf8a35de37fe1a8463cfbd42d2acbc43b42c33609ef63e85b6e3517a70d1`. Each game reached the archived fault-free official turn-limit result.
- All 4,128 public observations matched SHA256 `480a568b163719c99385e4077683c1053197aaa283169b269c88d93ef95ddedd`, including each side's initial view and its view after each committed action.
- Separate two- and four-side fixtures compared ordered public lists, ordinary and full moves, recruits, attacks, end turns and execution results on 42 boundaries. Original and candidate JSONL outputs were byte-identical, SHA256 `26e786a0abb598dffad1ddec7d2e5bf460a111b23120fb80b8b6f0c6342ed7a4`. The Rust rejection test compared both full-move values, unavailable recruit types, friendly and petrified targets, invalid actors, weapons and destinations against public enumeration and checked that rejected requests preserved the snapshot.
- On Ubuntu, 25 Rust tests and 33 Python movement, fog, isolation, snapshot, combat and atomic-batch checks passed on the candidate. The baseline failed the search-count assertion with `[2,3,2,2]` and passed the public membership assertion. [Check logs and full list comparison](measurements.tar.gz)

## Identity and execution

The integrated baseline was `7889264e74a5151ebd21d7185f7b220662818c37`. `cpuServer` ran the fixed v10 `val000010-team2v2-b0000-astra_partner-r0` board, Loris River validation, seed 2791729219. Both formal scoring paths were enabled. The original model, teacher, filtered rules, seat rotation, 30-turn limit and one numerical thread were identical in the two arms. Source packages were shipped with `git archive` and extracted separately under `/home/tongshu/acceptance/lite_intent_legality_20261104`. Other timed workloads used separate host slots. The probe compares one validation board and supplies no formal holdout evidence.

| Arm | Commit | Archive SHA256 | Release extension SHA256 |
| --- | --- | --- | --- |
| Baseline plus timing harness | `90c81a5cf9204bb2a9fc46d59c457183f4c8f836` | `866c7e9ca341d748abcc3c71d411507f4d39bd3d8b5bf5630b1f102cc4146d42` | `fa0519eb3e5c8eced558e00598046950ae2edb8a2c0cd5f9352ccf7f84a13d69` |
| Baseline with failing assertion | `4eb3001f0c4b43c376f45d19d1ca667530da67c2` | `4e18cb24e9bf42861b97460c6a8d9546a695114c79d4205ce7db6bd29ae17da1` | Test binary only |
| Candidate | `2d9db4456c46a95f4b7be160ffd9a3097d5a4afc` | `03c76a50dc17c85dd28bb3269259cff0b3dd2b430f283e64e51ae80ed357c04f` | `246fa95894429c73d49d03fc8f5fd515d634a839d9eb3725f4d4751fe9c66cbe` |

The candidate and baseline assertion used distinct Cargo target directories. From the corresponding source directories, with local `.extension`, repository root and `vendor/arena` on `PYTHONPATH`, the filtered rules bound through `WESNOTH_RULES_DIR` and `SOURCE_COMMIT` set to the archive identity, the commands were

```sh
cargo test --release --locked --offline --manifest-path engine_lite/Cargo.toml
cargo build --release --locked --offline --manifest-path engine_lite/Cargo.toml
/home/tongshu/venv/bin/python -B -m unittest -v tests.v5.test_engine_contract.InformationIsolationTest \
  tests.v5.test_engine_contract.SnapshotTest tests.v5.test_engine_contract.BatchApiTest \
  tests.v5.test_engine_contract.MovementTest tests.v5.test_engine_contract.CombatTest
/home/tongshu/venv/bin/python -B verification/lite_intent_legality_20261104/lists.py
timeout --signal=TERM --kill-after=3s 150s /home/tongshu/venv/bin/python -B -u \
  verification/lite_intent_legality_20261104/measure.py \
  /home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness ../after --score-only-astra
```

The baseline used `../before`. Each game ran once and exited 0. The threshold required at most 16.159581 CPU seconds on the candidate. The evidence archive has SHA256 `d7437c846cad97700b0d767dad7d3f7c297ad4215b1d5ceb536168cde079dc6d`.
