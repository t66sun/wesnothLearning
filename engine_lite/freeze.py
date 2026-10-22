"""Freeze explicit 1.18.8 runtime captures, without inventing missing rules.

The capture contract is produced by lua/export_rules.lua in each native scope.
This module does not launch Wesnoth. It deliberately records incomplete scope
inventories and never converts a partial export into a full-coverage claim.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SPECIALS = {'poison', 'slow', 'drains', 'magical', 'marksman', 'charge',
            'firststrike', 'berserk', 'swarm', 'plague', 'petrifies', 'backstab',
            'stun', 'absorb', 'deflect', 'shock', 'swift'}
ABILITIES = {'skirmisher', 'teleport', 'ambush', 'submerge', 'concealment', 'nightstalk',
             'heals', 'healing', 'curing', 'regenerates', 'regeneration', 'leadership',
             'illuminates', 'steadfast', 'feeding', 'unpoisonable', 'undrainable', 'unplagueable',
             'distract', 'inspire', 'diversion', 'vanguard', 'initiative'}
DAMAGE_TYPES = {'blade', 'pierce', 'impact', 'fire', 'cold', 'arcane'}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def _validate_raw_wml(value, location):
    """Reject the known mixed-key serialization loss in raw capture evidence."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f'{location}.{key}'
            if str(key).isdecimal() and child is None:
                raise ValueError(f'{child_location}: null WML child; recapture the native definition')
            _validate_raw_wml(child, child_location)
    elif isinstance(value, list):
        for index, child in enumerate(value, 1):
            if child is None:
                raise ValueError(f'{location}.{index}: null WML child; recapture the native definition')
            _validate_raw_wml(child, f'{location}.{index}')


def write_catalog_summary(rules_dir):
    """Write the small immutable catalog projection used at runtime startup.

    Acceptance flags stay in the full catalog and are read only when a caller
    explicitly requests accepted rules. This keeps the 49 MB capture provenance
    out of every benchmark/game process without duplicating mutable policy.
    """
    rules_dir = Path(rules_dir)
    catalog = json.loads((rules_dir / 'catalog.json').read_text(encoding='utf-8'))
    rules_bytes = (rules_dir / 'rules.json').read_bytes()
    digest = hashlib.sha256(rules_bytes).hexdigest()
    if digest != catalog.get('rules_file_sha256'):
        raise ValueError('rules.json differs from the frozen catalog hash')
    rules = json.loads(rules_bytes)
    if rules.get('source_hash') != catalog.get('source_hash'):
        raise ValueError('catalog/rules source provenance mismatch')
    summary = {
        'summary_version': 1,
        'source_version': catalog['source_version'],
        'rules_version': catalog['rules_version'],
        'source_hash': catalog['source_hash'],
        'rules_file_sha256': digest,
        'unit_count': catalog['unit_count'],
        'terrain_count': catalog['terrain_count'],
        'scope_inventory_complete': catalog.get('scope_inventory_complete', False),
        'missing_scopes': list(catalog.get('missing_scopes', [])),
        'coverage_counts': catalog.get('coverage_counts', {}),
        'vocabulary': catalog['vocabulary'],
    }
    write(rules_dir / 'catalog-summary.json', summary)
    return summary


def freeze_captures(captures, output):
    """Return the catalog; write rules/catalog/coverage plus immutable captures.

    Duplicate IDs are accepted only when their expanded definitions agree.
    Context-specific redefinitions require distinct capture IDs (scope::type).
    A missing movement/defense entry is an error, never a grassland fallback.
    """
    captures = [Path(p) for p in captures]
    if not captures:
        raise ValueError('at least one real native 1.18.8 capture is required')
    output = Path(output)
    if (output / 'catalog.json').exists():
        raise FileExistsError(f'frozen catalog already exists: {output}; choose a new output directory')
    units, terrains, coverage, provenance, scopes, required_scopes = {}, {}, {}, [], set(), set()
    loaded = []
    inventory_hash = None
    for path in captures:
        raw = path.read_bytes()
        capture = json.loads(raw)
        if capture.get('source_version') != '1.18.8':
            raise ValueError(f'{path}: capture is not from Wesnoth 1.18.8')
        if not capture.get('source_build_sha256'):
            raise ValueError(f'{path}: source build/data provenance hash is required')
        manifest = capture.get('source_manifest')
        if not isinstance(manifest, dict) or not manifest.get('files') or not manifest.get('required_scopes'):
            raise ValueError(f'{path}: include the independently generated distribution source_manifest')
        unsigned = {k: v for k, v in manifest.items() if k != 'manifest_sha256'}
        manifest_hash = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if manifest_hash != manifest.get('manifest_sha256') or capture['source_build_sha256'] != manifest_hash:
            raise ValueError(f'{path}: source inventory hash mismatch')
        if inventory_hash not in (None, manifest_hash):
            raise ValueError('captures come from different native build/data inventories')
        inventory_hash = manifest_hash
        scope = capture['scope']
        scopes.add(scope)
        required_scopes.update(manifest['required_scopes'])
        if scope not in required_scopes:
            raise ValueError(f'{path}: scope {scope} is absent from the native distribution inventory')
        if not capture.get('units') or not capture.get('terrains'):
            raise ValueError(f'{path}: capture has empty units or terrains')
        expected = set(capture.get('expected_units', []))
        actual = set(capture['units'])
        if not expected or expected != actual:
            raise ValueError(f'{path}: expected native unit inventory differs from captured definitions')
        for field in ('raw_definitions', 'variations'):
            _validate_raw_wml(capture.get(field, {}), f'{path}:{field}')
        for code, terrain in capture['terrains'].items():
            if terrain.get('id') != code:
                raise ValueError(f'{path}: terrain ID mismatch {code}')
            if code in terrains and canonical(terrains[code]) != canonical(terrain):
                raise ValueError(f'conflicting terrain {code} between scopes')
            terrains[code] = terrain
        loaded.append((path, raw, capture))
        provenance.append({'file': path.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                           'scope': scope, 'source_build_sha256': capture['source_build_sha256'],
                           'source_manifest': capture.get('source_manifest', {})})
    for path, raw, capture in loaded:
        for unit_id, original in capture['units'].items():
            unit = dict(original)
            if unit.get('id') != unit_id or unit.get('hp', 0) <= 0 or unit.get('experience', 0) <= 0:
                raise ValueError(f'{path}: malformed unit {unit_id}')
            if set(unit['movement']) != set(terrains) or set(unit['defense']) != set(terrains):
                raise ValueError(f'{unit_id}: capture must expand movement and defense for the union terrain inventory')
            if not DAMAGE_TYPES.issubset(unit['resistance']):
                raise ValueError(f'{unit_id}: missing native damage resistance')
            if any(not isinstance(v, int) or v < 0 for v in unit['movement'].values()):
                raise ValueError(f'{unit_id}: invalid movement cost')
            if any(not isinstance(v, int) or not 0 <= v <= 100 for v in unit['defense'].values()):
                raise ValueError(f'{unit_id}: defense must be native chance-to-hit percent')
            unsupported = list(unit.get('unsupported', []))
            unsupported += [f'ability:{a}' for a in unit.get('abilities', []) if a not in ABILITIES]
            for weapon in unit.get('weapons', []):
                unsupported += [f'weapon:{weapon["id"]}:{s}' for s in weapon.get('specials', []) if s not in SPECIALS]
                if 'plague' in weapon.get('specials', []) and not weapon.get('plague_type'):
                    unsupported.append(f'weapon:{weapon["id"]}:plague_without_type')
            # Preserve the original WML/variation/traits in the capture; the compact
            # core can accept only declarations it actually implements.
            unit['unsupported'] = sorted(set(unsupported))
            unit['approximation_reasons'] = sorted(set(unit.get('approximation_reasons', [])))
            if unit_id in units:
                left, right = dict(units[unit_id]), dict(unit)
                left.pop('scope', None); right.pop('scope', None)
                if canonical(left) != canonical(right):
                    raise ValueError(f'{unit_id}: conflicting scope definitions; export explicit scoped IDs')
            else:
                units[unit_id] = unit
            coverage.setdefault(unit_id, {'scopes': [], 'status': 'approximate', 'reasons': []})
            coverage[unit_id]['scopes'].append(capture['scope'])
            coverage[unit_id]['reasons'] = unit['unsupported'] or (unit['approximation_reasons'] + ['lite-0.1 rounding/conditions/traits require native differential acceptance'])
            if unit['unsupported']:
                coverage[unit_id]['status'] = 'unsupported_script'
    for unit_id, unit in units.items():
        for next_id in unit.get('advances_to', []):
            if next_id not in units:
                raise ValueError(f'{unit_id}: advancement {next_id} absent; capture its native scope')
        for weapon in unit.get('weapons', []):
            if weapon.get('plague_type') and weapon['plague_type'] not in units:
                raise ValueError(f'{unit_id}: plague type absent')
    source_hash = hashlib.sha256(canonical(provenance)).hexdigest()
    rules = {'source_version': '1.18.8', 'rules_version': 'lite-0.1-' + source_hash[:16],
             'source_hash': source_hash, 'units': units, 'terrains': terrains,
             'lawful_bonus': [0, 25, 25, 0, -25, -25]}
    missing_scopes = sorted(required_scopes - scopes)
    data_complete = bool(required_scopes and 'core' in scopes and not missing_scopes)
    catalog = {'source_version': '1.18.8', 'rules_version': rules['rules_version'],
               'source_hash': source_hash, 'complete': False,
               'scope_inventory_complete': data_complete,
               'native_accepted': False, 'performance_accepted': False,
               'status': 'scope_captured_definition_audit_pending' if data_complete else 'incomplete_scope_inventory',
               'unit_count': len(units), 'terrain_count': len(terrains),
               'scopes': sorted(scopes), 'required_scopes': sorted(required_scopes),
               'missing_scopes': missing_scopes,
               'vocabulary': {'units': ['<unknown>'] + sorted(units),
                              'terrains': ['<unknown>'] + sorted(terrains)},
               'captures': provenance,
               'coverage_counts': {status: sum(v['status'] == status for v in coverage.values())
                                   for status in ('exact', 'approximate', 'unsupported_script')}}
    output.mkdir(parents=True, exist_ok=True)
    raw_dir = output / 'captures'; raw_dir.mkdir(exist_ok=True)
    for _, raw, capture in loaded:
        name = hashlib.sha256(raw).hexdigest() + '.json'
        target = raw_dir / name
        if not target.exists():
            target.write_bytes(raw)
    write(output / 'rules.json', rules)
    write(output / 'coverage.json', coverage)
    catalog['rules_file_sha256'] = hashlib.sha256((output / 'rules.json').read_bytes()).hexdigest()
    write(output / 'catalog.json', catalog)
    write_catalog_summary(output)
    return catalog
