# Compact delivery weight acceptance

2026-11-02 (Asia/Shanghai): **PASS for the SDK size/loading blocker**. Ordinary BC, teacher strength, selected-checkpoint final evaluation and the complete training loop remain open.

## Cause and change

Three independent models were serialized as 17-significant-digit decimal Lua literals. The regression export measured 50,380,768 uncompressed bytes, including 50,274,331 bytes of weights, against the unchanged 16,777,216-byte SDK limit. `test_sdk_package` also failed at the real SDK check. Its old mutation of `MAX_PACKAGE_BYTES` did not change the already-bound `validate` default; that misleading workaround is removed.

`learning/weight_export.py` writes little-endian float32 vectors as base64, with a self-contained Lua decoder using bit operations and `string.unpack`. The original nested tables, parameter values, network computation and lazy loading remain intact. There is no quantization, new dependency, training assertion or exception handler. Export and sequence numerical audit now execute the same serialization.

The same size regression now measures **12,718,530 bytes (12.13 MiB)**, with **4,204,031 bytes per model**. Every loaded coefficient matches its Python float value bit-for-bit as a double, including explicit positive/negative zero, subnormal and extreme finite float32 fixtures. Loading each model in Lupa took 0.428/0.450/0.435 seconds in this check; these isolated timings are not native decision timings.

## Source and environment

- Baseline regression source: `7a81ce9e0d9463c6775011c597fcb2bf53c1e485`; production still uses decimal weights.
- Fixed source: `2542e8dfa971f5063d12ac109c4942c67ea7f3a5`.
- Each committed tree was shipped with `git archive` and extracted into a fresh Ubuntu directory: `/home/tongshu/acceptance/compact_weights_{red,fixed}_20261102`.
- Python 3.12.3: `/home/tongshu/venv/bin/python`; `OMP_NUM_THREADS=1`; `PYTHONPATH=/home/tongshu/acceptance/retaliation_fixed_20261102/.extension:.:vendor/arena`.
- Both use the isolated v2 extension with SHA-256 `ccb7c763cbce620e5d07736e6ae73df2c3891bdd9f281ab79ee10d63e2675365`; the shared installed extension was not replaced.
- Frozen rules are symlinked from `/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules`. Archive, extension, rules, entropy shim and native executable identities are recorded in the accompanying logs/JSON.

## Regression and contract checks

Baseline, 180-second external cap:

```sh
python -u -m unittest tests.v5.test_weight_export tests.test_core.CoreTests.test_sdk_package -v
```

Exit 1 after 5.642 seconds: size assertion fails and real SDK export errors. Raw output: `red/tests.log`.

Fixed source, 300-second external cap:

```sh
python -u -m unittest tests.v5.test_weight_export tests.test_core \
  tests.v5.test_checkpoint_export_identity tests.v5.test_learning_core \
  tests.test_lua_contracts -v
```

Exit 0: **59 tests pass in 22.356 seconds**. Includes actual three-format checkpoint export, SDK pack/open/validate, model identities, full coefficient round-trip, 37-candidate/two-turn sequence parity, memory overflow/128-entity stress, and deployed routing contracts. The tests use synthetic checkpoint/audit fixtures, so this is export integration acceptance, not a trained-policy readiness claim. Raw output: `fixed/tests.log`.

## Original-game loading and timing

`native.sh` runs the unchanged `verification/candidate_work_budget_20261031/check.py` (copied as `check_native.py`) after compiling the existing entropy shim. It exports seeded policies, then plays two games per format on the established 21x15 dense map, seeds 20261101/20261102, 20-turn limit, one-second action timeout, 37 candidates and 12,000 work. The existing 30-turn fallback was not used. The outer 900-second cap was declared before launch. No concurrent training or inference tests ran.

All six games finish without faults; four end by leader/team elimination and two FFA games reach the 20-turn cap. Exit 0 after **259.63 seconds**, all unchanged timing gates pass:

| Metric | duel | ffa4 | team2v2 |
| --- | ---: | ---: | ---: |
| Midgame decisions | 21 | 968 | 227 |
| Generation p95, ms | 21 | 53 | 19 |
| Scoring p95, ms | 113 | 136 | 117 |
| Evaluation RETURN maximum, ms | 78 | 188 | 617 |
| Other RETURN maximum, ms | 664 | 647 | 214 |
| Faults / over-budget decisions | 0 / 0 | 0 / 0 | 0 / 0 |

These games prove native loading and bounded execution on this panel, not strength or arbitrary-map performance. The helper's `truncated` summary counts candidate-generation cuts; game turn caps are reported above separately. Raw game events/logs/replays are in `native_games.tar.gz`, with summary, export hashes, command and artifact hashes alongside it. Historical evidence and frozen input data were not edited.
