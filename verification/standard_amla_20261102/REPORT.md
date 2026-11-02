# Standard AMLA acceptance — 2026-11-02

Standard AMLA execution passes the affected Ubuntu checks and five fixed native comparisons. Item 5 remains OPEN: weapon accuracy/parry and complete declaration filtering, followed by separately authorized native transfer/strength acceptance, are still outstanding. No collection, training, Windows tests or strength panel ran.

## Source and inputs

- Production combat/profile source: `0ba23c778be86272096df89e59da71cd46a0e9ab`; final native fixtures and feeding assertion: `a8c38191a2ccdc7fdad1e1c0f814a4dbd5cc1562`. Their production Rust/Lua/coordinator sources are identical. Final audit-report correction and its regression: `ae13302bddc00bd32ef55df895c1cb55768d8f4c`. Subsequent changes are evidence and trailing-whitespace cleanup only.
- Each source was shipped by `git archive` and extracted into a fresh `/home/tongshu/acceptance/amla_*_20261102` directory. Full commits, archive SHA256 and PAX commit headers: `identities.json`.
- Current extension SHA256: `b72907e1df600c76ae8181aae84bf3557dc8c99446c69a8240e24a736071f250`. Native executable SHA256: `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`. Native transport SHA256: `0f811064ebd71e8820ec2b88a6f3d1fc0d9583e567dc29c69873705ed57d7203`.
- New provisioned directory: `data/rules/1.18.8-amla`, rule version `lite-amla-1-58ead901dadf8ebe`, source hash `58ead901dadf8ebec9f55384d15daee3ba9414eccb3932a4bc2a02bb784e361c`, rules SHA256 `f4bec4fb5bc9fad7944e4aed873c431d6aa5fc3aac92ef2f22d7893ef60a2afe`. 587 units, 438 terrains; coverage 0 exact / 467 approximate / 120 unsupported. The actual 158-unit training closure has 65 standard AMLA declarations and no unsupported declarations. Full native/performance flags remain false.
- Historical `1.18.8-training/rules.json` remains SHA256 `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`. Captures are reused byte-for-byte, not collected or edited. New compiled data is provisioned locally and on Ubuntu, as are the older ignored input bundles.

Reproduce the new package from the old immutable captures, in catalog order, using the committed compiler:

```python
import hashlib, json
from pathlib import Path
from engine_lite.freeze import freeze_captures
base = Path('data/rules/1.18.8-training')
paths = []
for capture in json.loads((base / 'catalog.json').read_bytes())['captures']:
    path = base / 'captures' / (capture['sha256'] + '.json')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == capture['sha256']
    paths.append(path)
freeze_captures(paths, Path('data/rules/1.18.8-amla'))
```

## Behavior

The compiler accepts the exact native `amla_default` declaration, not its display name or the absence of a normal advancement. Execution adds 3 maximum HP, fully heals, clears poison/slow, consumes the old XP threshold and increases the threshold by rounded 20%, at most 100 times. Feeding bonuses survive exactly once. The new `probabilistic_combat_v3` identity separates old snapshots/teacher outputs; the training gate rejects old rules without compiled AMLA declarations. Numeric WML child keys in `native_cfg` are restored before native unit creation, allowing real repeated-advancement modifiers in fixtures.

## Commands and results

On Ubuntu, `PATH=/home/tongshu/.cargo/bin:/usr/local/bin:/usr/bin:/bin PYO3_PYTHON=/home/tongshu/venv/bin/python cargo test --manifest-path engine_lite/Cargo.toml` passes all 21 Rust tests (`rust.log`); the release extension build passes (`build.log`). Python uses `/home/tongshu/venv/bin/python`, `PYTHONPATH=.extension:.:vendor/arena`, and `OMP_NUM_THREADS=1`.

The final production archive ran `python -m unittest` with these modules:

```text
tests.v5.test_amla tests.v5.test_amla_declarations
tests.v5.test_coverage_audit_regressions tests.v5.test_rules_catalog
tests.test_bundle tests.test_bundle_scripts
tests.v5.test_combat_probability tests.v5.test_retaliation
tests.v5.test_engine_contract tests.v5.test_rule_abilities_completion
tests.v5.test_teacher_engine_identity tests.v5.test_astra_adaptation
tests.v5.test_four_player_teacher tests.v5.test_differential_runner
tests.v5.test_checkpoint_export_identity tests.test_core
```

- `python.log`: 154 cases, 149 passed; five setup fixture failures because the fixture still declared the old default rules path. The fixture path was corrected without weakening assertions.
- `verified.log`: all 21 cases passed: `tests.v5.test_amla tests.test_bundle_scripts tests.v5.test_native_rpc`, including the five corrected cases, an added feeding case and four native RPC cases. `WESNOTH_EXE` points at the installed native executable; none skipped.
- `audit.log`: all nine cases passed: `tests.v5.test_amla_declarations tests.v5.test_rule_coverage_completion`. This adds the standard-AMLA audit assertion and five existing closure checks.
- Together these provide passing evidence for 165 distinct Python cases, reusing unaffected checks; there were no skips. `python-latest-outcomes.json` indexes the 162 single-line test results (three unittest results use two lines in the raw log). Python/Lua maximum absolute error was `9.554692134705611e-09`.
- Before implementation, `amla-red.log` records two failures and one error among the four new execution cases. Two older feeding fixtures also assumed a guaranteed hit under stochastic combat; `baseline-feeding.log` reproduces both failures on the previous v2 baseline. Their defender terrain now specifies 100% hit chance, preserving both feeding assertions.

Native invocation, from the a8c3819 archive using the unchanged production extension:

```sh
python tests/diagnose_native_amla.py --rules data/rules/1.18.8-amla --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth --source a8c3819 --output native
```

All five fixed Dwarvish Lord cases pass: attacker, defender, kill, repeated AMLA, and three prior AMLAs with 70% XP. Full predicted HP distributions/average and poison/slow marginals agree within 1e-9; sampled advancements match each engine's own combat result. Repeat reaches max HP 80 / next XP 216; training repeat reaches max HP 86 / next XP 217. Raw inputs, predictions, resulting snapshots and identities are in `native/` and `native.log`.

## Remaining failure and limits

The first Elvish Champion fixture failed forecast parity: native sword hit chance is 70%, lite 60%, and defender mean HP is 24 versus 26. Captured sword `accuracy=10` is omitted by the existing compact export/compiler. Both executions did perform the same AMLA. The original failure is preserved in `accuracy_failure/`; it is the next required repair, not an accepted case. The passing AMLA fixtures isolate the same standard advancement using Dwarvish Lord, which has no such modifier.

General custom AMLA/advancement choices, complete weapon filters, accuracy/parry and native training/selection transfer remain outside this accepted phase. Forecast advancement retains the documented native pre-level-max-HP approximation. These fixed positions do not establish convergence, strength or whole-package native equivalence. Source line-length inspection found only the two untouched grandfathered test files over 1000 lines.
