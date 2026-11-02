# Native combat status and advancement boundaries

Ubuntu cpuServer, 2026-11-02. No collection, formal training or optimizer tuning. This phase repairs blocker 5 boundary semantics, not its remaining native-transfer acceptance.

## Change and observed result

`probabilistic_combat_v2` preserves seeded strike execution while matching native prediction of fatal poison/slow and combat/kill advancement. Prediction heals survivors to their original max HP, clears slow on the corresponding branches and uses native poison marginal recovery estimates. These advancement forecasts report approximate, as does the pre-existing berserk cutoff. Counter scoring now uses native marginal poison cost. Execution awards 4 XP, not 8, for a level-zero kill. Ordinary predictions skip the post-combat merge when advancement cannot occur. Combat and teacher identities change together; old data/snapshots keep their original identities.

Final source: `a44864d0fb68cd0537a3f369876baddf15b1ed34`. **21 Rust tests pass; release build succeeds; 90 Python/Lua tests pass; 21 fixed native battles pass all HP-bin, mean HP, poison and slow comparisons at absolute error <1e-9.** The battle checks also validate sampled experience gains and status clearing against each engine's own outcome, without equating independent RNG streams. Python/Lua export error is 9.554692134705611e-09. No skips or Windows tests.

Raw output: `rust.log`, `build.log`, `python.log`, `native.log`, `tactical/`. Native checks took 31.973 seconds. Each position repeats forecasts 100 times and checks identical results and unchanged snapshots. Ordinary positions cost 9.45–37.99 microseconds per forecast, berserk 360.44 microseconds, including Python JSON/assertion overhead. These timings do not establish whole-game or dense-board performance.

## Reproduction and source identity

Every phase was shipped with `git archive --format=tar` and extracted into a fresh directory under `/home/tongshu/acceptance`:

- `62d6a8e`, `combat_boundaries_red_20261102`: 20 native positions against the previously accepted v1 extension. Lethal debuffs, advancement HP/status and zero-level XP fail (`initial-native.log`).
- `2928ce4`, `combat_boundaries_fix_20261102`: first boundary implementation passes 21 Rust tests and 20 native positions. Initial compilation could not find cc because the command supplied a malformed PATH; correcting PATH resolved this setup failure. No code test result was inferred from it.
- `7502a27`, `combat_boundaries_final_20261102`: version isolation and six automated regressions, 89 Python tests pass.
- `ec3e52b`, `combat_boundaries_audit_20261102`: execution assertions added; six boundary tests and 20 native positions pass on the unchanged extension. Five behavioral tests fail against the original v1 extension (six failing subcases, `baseline-boundaries.log`).
- `107bd7b`, `combat_boundaries_poison_20261102`: review counterexample shows a conditional-healing formula inventing 0.1894736842105263 poison probability without a poison weapon (`no-poison-red.log`).
- `a44864d`, `combat_boundaries_verified_20261102`: restrict recovery calculation to a nonzero poison marginal; all final checks above pass, including mutual advancement without poison.

Final commands, from the extracted root (all final checks exit 0):

```sh
export PATH=/home/tongshu/.cargo/bin:/usr/local/bin:/usr/bin:/bin
export PYO3_PYTHON=/home/tongshu/venv/bin/python
cargo test --manifest-path engine_lite/Cargo.toml --lib
cargo build --manifest-path engine_lite/Cargo.toml --release
cp engine_lite/target/release/lib_engine_lite.so .extension/_engine_lite.so
export PYTHONPATH=.extension:.:vendor/arena OMP_NUM_THREADS=1
/home/tongshu/venv/bin/python -m unittest \
 tests.v5.test_combat_probability tests.v5.test_retaliation tests.v5.test_engine_contract \
 tests.v5.test_rule_abilities_completion tests.v5.test_teacher_engine_identity \
 tests.v5.test_astra_adaptation tests.v5.test_four_player_teacher \
 tests.v5.test_differential_runner tests.v5.test_checkpoint_export_identity tests.test_core -v
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
/home/tongshu/venv/bin/python tests/diagnose_native_tactics.py \
 --rules data/rules/1.18.8-training \
 --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
 --source HEAD_PLACEHOLDER --output tactical
```

The final native invocation accidentally supplied the literal source label `HEAD_PLACEHOLDER`; its original output is preserved. Actual shipped source is independently established by the git archive PAX commit header, archive SHA256 and a byte comparison of every extracted source file with the tar contents: no differences. See `source-identity.json`. This metadata error does not replace or relabel any historical result.

- Archive SHA256: `c821ed529430b1d5ef2d6de46feebc94bfd5cf4fe187fa2a7d3fd20e3ea0231d`.
- Extension SHA256: `a7f0b3ded924701f6ff5132357915ae565d21ebf8de66a764c9a4a315e4feb7c`.
- Rules SHA256: `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`.
- Native executable SHA256: `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`.
- Native transport SHA256: `23a43b4f400aaca2c18cd81bac5bd359866515e1f2f760fdc2e11fa4d05143cc`.

## Limits and next acceptance

Native reference: installed Wesnoth 1.18.8 `src/attack_prediction.cpp` (forced/conditional levelup and calculate_probability_of_debuff), `src/actions/attack.cpp` (better_combat), `src/game_config.hpp` (kill_xp). The predictor's conditional poison estimate is a marginal approximation, not an exact joint survivor/status probability. No full native equivalence or strength claim follows from these fixed cases.

Blocker 5 remains open for complete weapon declaration filtering, standard AMLA execution and native training/selection transfer. TEST.md R4/R3 track these. The default AMLA implementation was confirmed absent in Lite; native's standard declaration adds 3 max HP, increases max XP by 20% and clears poison/slow. It needs its own failing fixture and implementation. Old profiles require their original source/build; no migration, collection or training was performed.

No changed source exceeds 1000 lines. The two pre-existing grandfathered test files remain untouched. The guard skill was applied as guidance; no claim of runtime enforcement is made.
