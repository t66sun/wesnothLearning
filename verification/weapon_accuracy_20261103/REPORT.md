# Weapon accuracy/parry acceptance — 2026-11-03

The omitted accuracy/parry fields are repaired. All 21 Rust tests, 163 Python checks and eleven fixed native cases pass on Ubuntu. No collection/training or Windows tests ran. Item 5 remains OPEN for complete weapon declaration filters and native training/selection transfer acceptance.

## Source and rule identity

Production source is `9426d774bef117fe634cb31e54c3c28fd3c334a8`; additional native boundary fixtures are `df60b46478907bb426665c89467a4b7afa0c6a9a` (production sources unchanged). Both were shipped as `git archive` tarballs into fresh `/home/tongshu/acceptance/accuracy_*_20261103` directories. `source-identity.json` records archive SHA256, commit headers and independent byte comparisons of every shipped file, with zero mismatches (1622/1623 files).

Extension SHA256: `14e1176bd85805d820a3be98046ed02049fa2fe49055d8f73770ba9c1ac43e7a`. Native program SHA256: `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`. Transport SHA256 remains `0f811064ebd71e8820ec2b88a6f3d1fc0d9583e567dc29c69873705ed57d7203`.

The new provisioned default is `data/rules/1.18.8-combat`, version `lite-combat-1-58ead901dadf8ebe`, source hash `58ead901dadf8ebec9f55384d15daee3ba9414eccb3932a4bc2a02bb784e361c`, rules SHA256 `4af6785a21267a18e18ec58dde86be09146a3c4fcdd9fce0726e014f0f8966a1`. Original captures and prior frozen packages remain unchanged. The package is available on the local workstation and Ubuntu; it is provisioned input, not tracked source. Reproduce it with the committed compiler:

```python
import hashlib, json
from pathlib import Path
from engine_lite.freeze import freeze_captures
base = Path('data/rules/1.18.8-training')
paths = []
for capture in json.loads((base/'catalog.json').read_bytes())['captures']:
    path = base/'captures'/(capture['sha256']+'.json')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == capture['sha256']
    paths.append(path)
freeze_captures(paths, Path('data/rules/1.18.8-combat'))
```

There are 17 affected weapon declarations across 587 units; the 158-unit training closure includes Elvish Champion's accuracy=10. The closure remains free of unsupported declarations; approximation/native-acceptance flags are unchanged. `freeze.log` lists every affected declaration.

## Behavior and cause

Raw captures already contain accuracy/parry; compact export, compilation and the Rust Weapon model omitted them. Compilation now checks raw/compact weapon identity and order and preserves signed integer modifiers, including explicit zeros. Native execution computes ordinary terrain chance plus attacking accuracy minus the chosen opposing weapon's parry, clamps to 0–100, then applies magical/marksman effects. The shared strike function serves both execution and exact-state probability propagation, so no extra forecasts or caches are needed. No benchmark speedup is claimed.

The profile advances to `probabilistic_combat_v4`; old snapshots and teacher records keep their old identity. The training gate requires complete weapon modifier fields, preventing silent reuse of older compiled rules. Old runs require their original build and inputs.

## Verification

Baseline source `f63a9fb` supplied only new assertions to the previous v3 extension. `red.log` records five assertion failures across three cases: modifier effects, signed limits, no-counter behavior and v3 identity rejection.

On Ubuntu, with `/home/tongshu/venv/bin/python`, `PYO3_PYTHON` pointing to that interpreter and Rust tools on PATH:

- `cargo test --manifest-path engine_lite/Cargo.toml`: all 21 Rust tests pass (`rust.log`). Release extension build passes (`build.log`).
- `PYTHONPATH=.extension:.:vendor/arena OMP_NUM_THREADS=1 python -m unittest ... -v`: all 163 checks pass with no skips (`python.log`). Modules: `tests.v5.test_weapon_accuracy`, `test_weapon_declarations`, `test_amla`, `test_amla_declarations`, `test_coverage_audit_regressions`, `test_rules_catalog`, `tests.test_bundle`, `tests.test_bundle_scripts`, `tests.v5.test_combat_probability`, `test_retaliation`, `test_engine_contract`, `test_rule_abilities_completion`, `test_teacher_engine_identity`, `test_astra_adaptation`, `test_four_player_teacher`, `test_differential_runner`, `test_checkpoint_export_identity`, and `tests.test_core` (unqualified names retain the preceding package). Python/Lua maximum absolute error: `9.554692134705611e-09`.
- `python tests/diagnose_native_amla.py --unit 'Elvish Champion' --rules data/rules/1.18.8-combat --wesnoth <installed executable> --source 9426d77 --output native`: all five native cases pass (`amla/`). The original failed attacker case now has matching 70% hit chance and complete HP/status prediction. Attacker, defender, kill, repeat and 70% XP/repeated AMLA also match.
- `python tests/diagnose_native_accuracy.py --rules data/rules/1.18.8-combat --wesnoth <installed executable> --source 9PLACEHOLDER --output native`: all six native boundary cases pass (`modifiers/`). The command mistakenly supplied a placeholder source label; the raw result is preserved. The independent archive header and byte-for-byte audit in `source-identity.json` establish the actual source as `df60b46478907bb426665c89467a4b7afa0c6a9a`.

Boundary fixtures use explicit test-only native attack objects and corresponding in-memory lite rules, without modifying frozen input. They cover 70% attacking / 50% defending chance, lower clamp 0%, upper clamp 100%, magical override 70%, offensive marksman floor 60% and absent-counter chance 80%. All full HP distributions, averages and poison/slow marginals agree within 1e-9. The baseline regression checks seeded restore and forecast purity too.

Final source/diff checks found no new file above 1000 lines; only the two untouched grandfathered tests exceed the limit. The historical Champion failure remains at `verification/standard_amla_20261102/accuracy_failure/`.

## Limits

These cases close the accuracy/parry defect, not complete native combat acceptance. Full weapon disabling, weights and conditional declaration filters remain R4 work; R3 teacher ranking/strength transfer remains separately unrun. Approximation guards and panel gates are unchanged. Fixed positions prove neither convergence nor strength.
