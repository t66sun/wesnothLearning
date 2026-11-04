# Forecast compatibility of the item-10 inputs

The ordinary BC source was `87a68eac666f1fe4f3384f39016d17feaf423e05`. The reference forecast and static-board geometry below use confirmation source `7889264e74a5151ebd21d7185f7b220662818c37`.

The item-10 v6 BC run and the strict confirmation both froze the same **158 unit IDs**. Recomputing the registered six factions' leaders, recruits, advancements and plague descendants gives that exact list. Both manifests pin profile SHA256 `3c1423bd63ac8ac708e65d39cc59265076abbb9325f58fa5f32a69cff972d71a` and rules SHA256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. The SHA256 of the sorted IDs encoded below is `dd6a0130cbcb06e321389fe3b86d564da3947ccc10a56e6911d47fab117c0fe2`. The item-10 archive records 56/48/48 ordinary teacher jobs and four duel DAgger refresh jobs. All used shared vision and the registered faction setup. [Item-10 metadata](../bc_ordinary_v6_20261103/metadata/README.md) · [Confirmation metadata](../bounded_loop_confirmation_20261104/metadata/run_metadata.tar.gz)

| Ability category within the 158 | Unit IDs |
| --- | --- |
| Can conceal (16) | Ancient Wose, Banebow, Bone Shooter, Deathblade, Draug, Elder Wose, Elvish Avenger, Elvish Ranger, Fugitive, Lich, Nightgaunt, Revenant, Shadow, Skeleton, Skeleton Archer, Wose |
| Leadership (8) | Drake Flameheart, Drake Flare, Elvish Captain, Elvish Marshal, General, Goblin Rouser, Grand Marshal, Lieutenant |
| Illumination (1) | Mage of Light (+25) |
| Vanguard, diversion, initiative or inspire | None |
| Offensive backstab (5) | Assassin, Nightgaunt, Rogue, Shadow, Thief |

On the historical code, the host checked that attacker and defender were visible and the landing terrain was known. It then moved the attacker on a referee clone and recomputed the public unit list against the **unchanged** visibility grid. Both the Astra teacher and shared candidate generator forecast their own unit attacking a visible enemy from an adjacent hex. A hypothetical move can newly expose a previously concealed unit only beside the new landing. None of the 16 concealable types supplies a combat aura. With no vanguard or diversion, the remaining modifier that can depend on an ordinary bystander is offensive backstab. Its opposite hex lies two hexes from the attacker across the adjacent defender. A newly exposed unit beside the attacker cannot be that flanker. These constraints support retaining the sealed item-10 inputs with the corrected forecast on their recorded roster, geometry and vision settings. [Historical host preconditions](https://github.com/t66sun/wesnothLearning/blob/7889264e74a5151ebd21d7185f7b220662818c37/engine_lite/src/host.rs#L36-L45) · [Projected modifiers](https://github.com/t66sun/wesnothLearning/blob/7889264e74a5151ebd21d7185f7b220662818c37/engine_lite/src/state.rs#L507-L557) · [Offensive damage rule](https://github.com/t66sun/wesnothLearning/blob/7889264e74a5151ebd21d7185f7b220662818c37/engine_lite/src/combat.rs#L56-L61)

An **initially visible** flanker can re-conceal. The static seven-by-seven FFA fixture places a Knalgan Rogue at 25, a defender at 24 and a hostile third-side Skeleton on deep-water hex 32. The original attacker exposes the Skeleton. The Rogue has backstab and skirmisher, can move via 17 to 23, and ends two hexes from the submerged flanker. On the original and corrected releases the re-concealed case and the unflanked control both gave defender mean HP **26.8**. The visible-flanker control gave **21.4** on both, with attacker mean HP 29.2 throughout. The full forecasts and candidate rows matched across releases in all three cases. [Static re-concealment oracle](reconceal.json) · [Fixture and legality check](../../tests/v5/test_forecast_public_context.py)

The broader catalog includes **Death Knight**, which both submerges and supplies leadership. On two boards with identical original observations and legal actions, the historical forecast gave attacker mean HP **18.0** with the hidden knight near the landing and **23.4** with it far away. The corrected forecast gave **23.4** in both cases. Defender mean HP was 28.6 throughout. Death Knight is absent from the 158 registered IDs. [Static oracle and fixture](../../tests/v5/test_forecast_public_context.py)

## Reproduce the roster

Run in the provisioned repository with its frozen rules and archived JSON. This read-only extraction invokes the production closure calculation, compares both sealed manifests and prints the full sorted list.

```sh
python -B - <<'PY'
import hashlib, json, tarfile
from pathlib import Path
from engine_lite.audit import training_closure

root = Path('data/rules/1.18.8-combat-filtered')
rules_bytes = (root/'rules.json').read_bytes()
rules = json.loads(rules_bytes)
closure = training_closure(rules, json.loads((root/'coverage.json').read_bytes()))
ids = sorted(closure['unit_ids'])
source_hash = hashlib.sha256(Path('vendor/arena/params.py').read_bytes()).hexdigest()
for directory, run in [('bc_ordinary_v6_20261103','bc_readiness'),
                       ('bounded_loop_confirmation_20261104','bounded_loop')]:
    with tarfile.open(Path('verification')/directory/'metadata/run_metadata.tar.gz') as archive:
        manifest = json.load(archive.extractfile(f'runs/{run}/manifest.json'))
    registered = manifest['rules']['training_acceptance']
    assert sorted(registered['unit_ids']) == ids and registered['unit_count'] == len(ids) == 158
    assert registered['profile_sha256'] == source_hash
    assert registered['rules_file_sha256'] == hashlib.sha256(rules_bytes).hexdigest()
print(json.dumps(ids))
print(hashlib.sha256(json.dumps(ids, separators=(',',':')).encode()).hexdigest())
units = rules['units']
hide = {n for n in ids if units[n].get('concealment_terrains') or 'nightstalk' in units[n]['abilities']
        or any(set(units[n]['abilities']).intersection(t.get('concealment', [])) for t in rules['terrains'].values())}
modifiers = {'leadership','inspire','initiative','diversion','vanguard','illuminates'}
auras = {n for n in ids if modifiers.intersection(units[n]['abilities']) or units[n].get('illumination')}
assert len(hide) == 16 and not hide.intersection(auras) and 'Death Knight' not in ids
print(sorted(hide), sorted(auras))
PY
```
