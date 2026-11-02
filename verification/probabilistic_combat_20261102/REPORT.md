# Seeded probabilistic combat acceptance

Ubuntu cpuServer, 2026-11-02. No collection, optimizer updates or training ran. Frozen rules, old reports and shared installed extension were not changed.

## Change

Replace guaranteed rounded expected damage with full-damage hit/miss execution. Referee-only SplitMix64 uses rejection sampling for unbiased percent rolls. Its state lives in Game, so snapshots and atomic batch rollback preserve the same future. Forecasts read legal public units/terrain, never RNG, and merge equal HP/status states after each strike. Retaliation compares distributions with native 0.01 tolerance; zero/one-counter execution skips prediction. Native half-damage rounding and eight-point poison replace surrogate constants; the teacher and combat/RNG identities change together.

The initial full-30-round berserk distribution differed from the original predictor. Inspection of installed 1.18.8 `src/attack_prediction.cpp:2139` established its >=99% death stopping rule. Forecasts now reproduce that rule and report `approximate=true` when stopped early; execution retains the complete 30-round rule. No probability threshold was relaxed in the native comparison.

## Source and checks

Each source was shipped using `git archive --format=tar` and extracted into a fresh directory under `/home/tongshu/acceptance`.

- `6fa73d6`: `combat_red_20261102`, two new probability/reproducibility regressions fail on the deterministic engine (wrong mean HP and seven-point damage instead of hit/miss 0/10).
- `f51f699`: first implementation; both new regressions pass, 12 legacy deterministic assertions fail. Existing test cases were retained and migrated to the new contract.
- `00bbd41`: `combat_integration_20261102`, 82 Python cases, ten failures/subtests in old damage fixtures. Guaranteed-hit mechanics fixtures and a plague fixture whose two weapons became tied were corrected. Initial output is `initial-python.log`.
- `dd4da1d`: `combat_expanded_20261102`, first strict expanded native comparison exposed native berserk early termination (`initial-native.log`).
- `a1ac914980acc1d76e94ced818bdd819119ff579`: `combat_final_20261102`, final production source. **21 Rust checks pass**, release build succeeds, **82 Python/Lua cases pass**, and **nine native positions pass** complete HP-bin, mean HP, poison and slow comparisons with absolute tolerance 1e-9. No skips.
- `c8aebe7`: `combat_privacy_20261102`, adds the public-API RNG privacy/failed-batch rollback/v2 snapshot rejection test; **3/3 retaliation cases pass** using the unchanged final release extension. This gives **83 distinct Python cases** with prior unchanged passes reused.

Commands (from each extracted root):

```sh
export PATH=/home/tongshu/.cargo/bin:$PATH
export PYO3_PYTHON=/home/tongshu/venv/bin/python
cargo test --manifest-path engine_lite/Cargo.toml --lib
cargo build --manifest-path engine_lite/Cargo.toml --release
# Separate .extension/_engine_lite.so copied from that release build.
export PYTHONPATH=.extension:.:vendor/arena OMP_NUM_THREADS=1
/home/tongshu/venv/bin/python -m unittest \
 tests.v5.test_retaliation tests.v5.test_engine_contract \
 tests.v5.test_rule_abilities_completion tests.v5.test_teacher_engine_identity \
 tests.v5.test_astra_adaptation tests.v5.test_four_player_teacher \
 tests.v5.test_differential_runner tests.v5.test_checkpoint_export_identity tests.test_core -v
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
timeout 180 /home/tongshu/venv/bin/python tests/diagnose_native_tactics.py \
 --rules data/rules/1.18.8-training \
 --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
 --source a1ac914980acc1d76e94ced818bdd819119ff579 --output tactical
```

Full output is in `rust.log`, `build.log`, `python.log`, `privacy.log`, `native.log` and `tactical/`. The native run completed in 13.823 seconds. Rule/native executable/transport hashes are in `tactical/summary.json`. Python/Lua export maximum absolute error is 9.554692134705611e-09.

## Observations and limits

Kill threshold probability is 0.4752, attacker death 0.84, poison 0.936 and slow 0.84, matching native. Skeleton/hammer mean remaining HP is 22. Extended cases cover berserk, drain and slow affecting subsequent retaliation. Per-case 100 repeated forecasts preserve the snapshot and result. Measured small-position costs are about 10–37 microseconds for ordinary cases and 366.5 microseconds for berserk. This includes Python decoding/assertions, is not a pure Rust benchmark, and establishes neither overall speedup nor dense-board timing acceptance.

No new source file exceeds 1000 lines. The pre-existing grandfathered test files remain unchanged. No Windows tests ran.

This closes the structural deterministic-certainty defect, not all of blocker 5. Complete weapon declaration filtering, advancement/status boundary cases and native playing-strength transfer remain unaccepted (TEST.md R4/R3). The nine fixed positions do not establish full native equivalence. Approximation startup guards remain. Old v1/v2 rows, snapshots and checkpoints keep their original identities and require their original source/build; no migration or new training readiness is claimed.
