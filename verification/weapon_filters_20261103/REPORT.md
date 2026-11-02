# Supported weapon declaration acceptance — 2026-11-03

R4 is accepted for the declared supported-rule scope. Exact weapon declarations are compiled rather than inferred from display IDs, nonpositive defense weights exclude counters, and standard backstab works with a third hostile FFA faction. Unknown custom filters/disable declarations remain explicitly unsupported. Item 5 remains OPEN for full legal-board teacher ranking and the separately authorized R3 native transfer/strength panel.

## Source and inputs

- Final production source: `8b001003aa6a94ef47f66b37506e82b229240364`; extension SHA256 `fea9729adb4e85cd22c16cfbb53acf19027c2c27e7e7296a88391bc3a2d51d85`. The broader checks ran on `4feb93797d4943a8a1308212051013fe0c00a407`, with the final one-line FFA backstab condition subsequently verified through all affected tests and native fixtures.
- Native executable SHA256 `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`; native transport SHA256 `0f811064ebd71e8820ec2b88a6f3d1fc0d9583e567dc29c69873705ed57d7203`.
- Each archive was extracted into a fresh Ubuntu `/home/tongshu/acceptance/filters_*_20261103` directory. `source-identity.json` records commit headers, archive hashes and byte comparisons of every shipped file (zero mismatches). The early conditions runner labelled its source `conditions`; the independently verified archive establishes its full commit as `0eb65aaccb92c85f3e3bde2abcfef1733751a38d`.
- New provisioned default: `data/rules/1.18.8-combat-filtered`; version `lite-combat-2-58ead901dadf8ebe`; source hash `58ead901dadf8ebec9f55384d15daee3ba9414eccb3932a4bc2a02bb784e361c`; rules SHA256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. Old packages and raw captures remain unchanged. This package is provisioned on Ubuntu and the local workstation.
- Frozen coverage remains 0 exact / 467 approximate / 120 unsupported, 587 units / 438 terrains. All 158 training-closure units retain support. No previously supported unit becomes unsupported (`freeze.log`). Full-package native/performance flags remain false.

Reproduce the package with the committed compiler, without collection:

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
freeze_captures(paths, Path('data/rules/1.18.8-combat-filtered'))
```

## Contract and fixes

The actual training closure contains ten semantic weapon declaration shapes; the supported whole inventory contains twenty. The compiler matches structural rules and parameters, ignoring presentation only. Poison/slow/drains/firststrike/plague, magic/marksman, berserk, charge/backstab and existing extended specials retain their implemented parameters. An arbitrary condition, altered magnitude or disable tag cannot masquerade as a standard rule by reusing its ID. WML decimal strings such as `defense_weight="4.0"` are preserved numerically; the initial stricter numeric-only parser failure is retained in `freeze-initial-failure.log`.

Native 1.18.8 `src/actions/attack.cpp:587–653` excludes nonpositive defense weights before counter comparison. Both lite counter-selection entry points now do the same, retaining the zero/one-counter fast path. Explicit attacks with attack_weight=0 remain legal. Positive weights do not override the native distribution choice in the pinned implementation: its min_rating starts at zero and the maximum is assigned before the strict-greater branch. The positive-weight native regression retains that observed contract rather than inventing a different heuristic.

A native activated-backstab fixture exposed a separate condition defect within this owner: lite required the flanker to be allied with the attacker, but native requires hostility to the defender. In four-way FFA the original defender average HP was 31.184 versus native 24.368. The corrected predicate uses defender hostility and retains public-context/petrified checks. The repaired native fixture asserts actual backstab activation (8 damage, versus 4 for a petrified flanker), so a misplaced flanker cannot produce a false pass.

The `probabilistic_combat_v5` profile and required compiled weight fields prevent older snapshots/rules/teacher rows from silently sharing the new semantics. No broad restructuring or extra forecast/cache layer was added.

## Ubuntu checks

`commands.sh` contains the full broad check command. Python is `/home/tongshu/venv/bin/python`; `PYTHONPATH=.extension:.:vendor/arena`, `OMP_NUM_THREADS=1`, and `PYO3_PYTHON` points to that interpreter.

- Baseline v4 extension: three failures among five filter/compiler tests (`baseline.log`), including invalid nonpositive counters.
- `cargo test --manifest-path engine_lite/Cargo.toml`: all 21 tests pass, both before and after the final backstab fix (`rust.log`, `backstab_after/rust.log`). Both release builds pass.
- All 170 affected Python cases pass with no skips (`python.log`). After the one-line backstab repair, all 20 changed-dependency cases pass: `tests.v5.test_weapon_filters tests.v5.test_rule_abilities_completion tests.v5.test_retaliation` (`backstab_after/python.log`); reuse the other unchanged passes. Python/Lua maximum absolute error is `9.554692134705611e-09`.
- Four real native counter-weight cases pass (`weights/`): zero/negative exclude axe and select hammer; no eligible counter produces no retaliation; large positive hammer weight still selects the better axe distribution. Explicit zero-attack-weight actions are legal in both engines.
- Twenty-one native combat/advancement cases pass (`tactics/`), retaining the exact full HP/status prediction checks at 1e-9.
- Firststrike, marksman and charge pass (`conditions/`). That early run stopped at a later unsupported three-side fixture; the three complete unchanged raw cases were independently checked, with max error recorded in `source-identity.json`. The invalid fixture is not counted. The initial backstab placement did not activate the condition and is also not counted.
- Three correctly placed backstab cases pass after repair (`backstab_after/`): allied flanker, third hostile FFA faction, and petrified flanker. `backstab_before/` retains the full pre-fix FFA distribution failure. Commands use `tests/diagnose_native_tactics.py --case backstab --case backstab_ffa --case backstab_petrified`, the new rules package and recorded source commit.

Thus 31 distinct fixed native cases have passing evidence, alongside 170 Python cases and 21 Rust cases. No collection, training, strength panel or Windows tests ran. Native samples are checked against each engine's own outcomes; random streams need not match. Source/diff checks find only the two untouched grandfathered tests above 1000 lines.

## Limits

Acceptance covers the compiled supported declarations and recorded native cases. Campaign events, arbitrary dynamic weapon/disable filters and custom advancement choices remain unsupported or under the existing approximation guard. R4 acceptance is not universal native equivalence and does not promote inventory rows to exact. R3 full legal-board teacher query/ranking and native transfer/strength evidence remain required before item 5 can close. No gate threshold was reduced.
