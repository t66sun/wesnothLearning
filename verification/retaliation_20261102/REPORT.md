# Contextual retaliation under expected_damage_v2

Ubuntu acceptance and bounded native comparison, 2026-11-02. No collection or formal training. The installed shared extension, frozen rules, checkpoints and previous reports were not replaced.

## Change and limits

The previous selector maximized raw damage times strikes among matching-range weapons. It ignored resistance, terrain, instance damage, survival and opposing specials. The native 1.18.8 source (`src/actions/attack.cpp`, `choose_defender_weapon` / `better_defense`, lines 570 / 463) instead compares battle consequences.

The new resolver evaluates eligible counters through its existing deterministic exchange, orders outcomes by defender kill-minus-death, poison-adjusted remaining-HP balance, then damage to the attacker, and retains the first exact tie. It reuses the winning units and strike log instead of fighting again. One or zero matching counters use a direct path. Execution receives the chosen counter index for defensive plague; forecast uses the same resolver with only the requesting side's public context.

This is the native comparison ordering applied to a deterministic surrogate, not native probability equivalence. Damage uplift, 3/4 slow and six-point poison are unchanged. Captured weapon eligibility still filters by range; full native defense weights/disabling filters are not implemented by this change. Native tactical transfer remains open.

Combat/teacher profile is now `expected_damage_v2`, RNG marker `deterministic-expected_damage_v2`, engine ABI marker remains `lite-0.2`. The teacher's source digest changes with its profile marker. Existing identity checks reject v1 rows and snapshots; checkpoint resume/export require their matching combat and teacher identities. Old weights remain usable only through the existing explicit fresh-initialization route. Historical inputs are not relabelled.

## Source and commands

Every source was shipped by `git archive --format=tar` and extracted into a fresh directory under `/home/tongshu/acceptance/`.

| Source | Directory suffix | Purpose |
| --- | --- | --- |
| `9b2eac5dbf37e00da987b9d1c1d65766d7e57197` | `retaliation_red_20261102` | Five failing Rust regressions; baseline fixture failures; baseline timing |
| `3c819f4c14c91e35a0eb1cf1ae18a92b8181f8a3` | `retaliation_fixed_20261102` | Production fix, Rust suite, release build, affected Python suite, timing |
| `be242cfe13fcdce4bd564ac1b4552f292f3927d2` | `retaliation_contract_20261102` | Legal movement in new Python fixture; two regressions and six native positions |
| `7267280e4fba9fa48ef2bf9ab59b5a3d7e56111c` | `retaliation_export_20261102` | Existing export fixture corrections; exposes SDK-size failure |
| `6807b22723c057f1e44a18083e8338eb11c7f0e0` | `retaliation_identity_20261102` | Current structured-map fixture; checkpoint/export identity acceptance |

Environment: `PATH=/home/tongshu/.cargo/bin:$PATH`, `PYO3_PYTHON=/home/tongshu/venv/bin/python`, `OMP_NUM_THREADS=1`; rules symlink at `data/rules` points to the existing provisioned rules. Rust commands:

```sh
cargo test --manifest-path engine_lite/Cargo.toml --lib retaliation_ # baseline only
cargo test --manifest-path engine_lite/Cargo.toml --lib             # fixed suite
cargo build --manifest-path engine_lite/Cargo.toml --release
```

Release libraries are loaded from a separate `.extension/_engine_lite.so` using `PYTHONPATH=<fixed-root>/.extension:.:vendor/arena`; nothing is installed into the shared venv. Library SHA256: baseline `ee77ce82ddb4219a6162599364e6523b7a6e35afe322546eeea265e448925b90`, fixed `ccb7c763cbce620e5d07736e6ae73df2c3891bdd9f281ab79ee10d63e2675365`.

Affected Python command:

```sh
/home/tongshu/venv/bin/python -m unittest \
  tests.v5.test_retaliation tests.v5.test_engine_contract \
  tests.v5.test_rule_abilities_completion tests.v5.test_teacher_engine_identity \
  tests.v5.test_astra_adaptation tests.v5.test_four_player_teacher \
  tests.v5.test_differential_runner tests.v5.test_checkpoint_export_identity \
  tests.test_core -v
```

Baseline: all five new Rust regressions fail on their intended outcomes (`red/tests.log`, exit 1). Fixed: **19/19 Rust tests pass**, including stable ties and range filtering; release build exits 0.

The first affected Python run executes 82 cases: 78 pass, four fail. The new plague fixture erroneously gave a Skeleton five movement points; setting its valid four points yields **2/2 integration passes**, including forecast purity, chosen-counter plague and v1 rejection. The other three failures reproduce on baseline: a PPO mock omits required counters, the SDK fixture uses a fake teacher digest, and the parameter-count expectation predates seven action inputs and one entity input. These fixtures are corrected without changing production training/export code. The checkpoint fixture also needed the existing structured `opening_map` rather than a legacy terrain string; its full three-format checkpoint identity and numerical export check now passes. Final coverage is **81 passing cases / 82**, reusing unchanged passes; the real SDK package-size check still fails. All intermediate failures and final outputs are retained under `red/`, `fixed/`, `contract/`, `export/`, `identity/`.

The remaining `test_sdk_package` failure reaches `addons.validate`: exported text weights exceed the unchanged effective 16 MiB SDK limit. Its historical assignment to `addons.MAX_PACKAGE_BYTES` does not change the function's bound default argument. This phase does not raise that gate or claim delivery acceptance. The failure is tracked under complete-loop/export acceptance for a separate representation repair.

## Six native positions

```sh
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
PYTHONPATH=<fixed-root>/.extension:.:vendor/arena OMP_NUM_THREADS=1 \
timeout --signal=TERM --kill-after=10 360 /home/tongshu/venv/bin/python -u \
  tests/diagnose_native_tactics.py --rules data/rules/1.18.8-training \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --source be242cf --output tactical
```

All six cases complete in **7.525 s**, exit 0; every requested attack is legal and lite forecast matches execution. Rules hash `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`; native executable hash `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`. Full inputs, identities and outcomes are in `contract/tactical/`.

Skeleton versus Dwarvish Fighter now receives **two seven-HP hammer blows**, ending at 20 HP. Previously it received three three-HP axe blows and ended at 25 HP. Native selects hammer (10 base damage, two blows) and predicts mean 22 HP. The remaining two-HP difference follows the declared deterministic damage uplift/rounding. Other five recorded probability/point-mass comparisons are unchanged; native kill/poison/slow uncertainty still differs structurally from lite certainty. No strength or convergence claim follows.

## Small forecast-cost probe

After other work completed, each archived release build ran three blocks of 1000 unchanged forecasts on the same public ordinary and resistance positions, in a separate process with a 180-second cap. The probe uses `LiteAdapter(game_spec(...))`, times only repeated `forecast(1, 'attacker', 'defender', 0, 1)`, and asserts the original snapshot remains identical. Both exit 0; raw arrays and library identities are in `*/forecast_cost.json`.

| Position | v1 median microseconds/call | v2 median microseconds/call |
| --- | ---: | ---: |
| One eligible counter | 7.149 | 7.269 |
| Two eligible counters | 8.269 | 9.917 |

This fixed small-position measurement observes about 1.65 microseconds extra for comparing the second weapon. It is not an end-to-end training or dense-board performance claim. No new file exceeds 1000 source lines; only the two unchanged grandfathered tests remain over the repository cap.
