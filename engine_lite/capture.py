"""Capture native 1.18.8 scopes through their actual campaign entry points.

Run on the Ubuntu host holding the selected native installation. Each scope
gets an isolated temporary add-on. Captures and logs are retained in a new
output directory; existing frozen rules are never overwritten.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from .freeze import canonical, freeze_captures
from .inventory import build_inventory
from learning.common import ROOT
from vendor.arena.native import lua


def campaign_defines(source):
    """Use the campaign's first define, not difficulty definitions below it."""
    match = re.search(r'^\s*define\s*=\s*"?([A-Za-z_][A-Za-z_0-9]*)', source, re.M)
    return [match[1]] if match else []


def scenario(data_root, scope, options, terrain_includes=()):
    includes = ''
    if scope != 'core':
        entry = data_root / 'campaigns' / scope / '_main.cfg'
        defines = campaign_defines(entry.read_text(encoding='utf-8-sig'))
        # Multiplayer loads core macros before our campaign difficulty is set.
        # Reload difficulty-dependent utilities in the selected NORMAL context.
        includes = '{core/macros/utils.cfg}\n'
        includes += ''.join(f'#define {name}\n#enddef\n' for name in defines)
        includes += f'{{campaigns/{scope}/_main.cfg}}\n'
    # Terrain aliases are registered by campaign files, but rules are shared by
    # every unit in the frozen runtime. Load all campaign terrain declarations in
    # every scope so core units are expanded against the same real definitions.
    includes += ''.join(f'{{{path}}}\n' for path in terrain_includes)
    return f'''#ifdef MULTIPLAYER
#ifndef NORMAL
#define NORMAL
#enddef
#endif
{includes}
[multiplayer]
id=learning_rules_capture
name="Rule capture"
victory_when_enemies_defeated=no
turns=1
map_data="Gg,Gg,Gg
Gg,Gg,Gg
Gg,Gg,Gg"
[side]
side=1
controller=ai
no_leader=yes
[/side]
[side]
side=2
controller=ai
no_leader=yes
[/side]
[event]
name=prestart
[lua]
code=<<
local options={lua(options)}
local data=wesnoth.require('~add-ons/LearningRulesCapture/export_rules.lua').capture(options)
local json=wesnoth.require '~add-ons/LearningRulesCapture/capture_json.lua'
std_print('RULE_CAPTURE '..json.encode(data))
wesnoth.wml_actions.endlevel{{result='victory',linger_mode=false,carryover_report=false,save=false}}
>>
[/lua]
[/event]
[/multiplayer]
#endif
'''


def terrain_definition_files(data_root):
    """Return WML files that declare campaign terrain types, relative to data root."""
    files = []
    for path in (data_root / 'campaigns').rglob('*.cfg'):
        source = path.read_text(encoding='utf-8-sig', errors='replace')
        if '[terrain_type]' in source:
            files.append(path.relative_to(data_root).as_posix())
    return sorted(files)


def map_terrain_codes(directory):
    """Include real base/overlay combinations that have no standalone WML row."""
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    codes = set()
    for path in sorted(directory.glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        board = data.get('board', data)
        rows = board.get('terrain')
        if not isinstance(rows, list) or not rows or any(
                not isinstance(row, list) or not row or any(
                    not isinstance(code, str) or not code for code in row) for row in rows):
            raise ValueError(f'{path}: map terrain must contain rows of native terrain codes')
        codes.update(code for row in rows for code in row)
    return codes


def capture_scope(executable, data_root, scope, inventory, terrain_codes, output, timeout,
                  terrain_includes=()):
    options = dict(source_version='1.18.8', source_build_sha256=inventory['manifest_sha256'],
                   source_manifest=inventory, scope=scope,
                   required_scopes=inventory['required_scopes'], terrain_codes=terrain_codes)
    with tempfile.TemporaryDirectory(prefix='rules-capture-') as temporary:
        user = Path(temporary)
        addon = user / 'data/add-ons/LearningRulesCapture'
        addon.mkdir(parents=True)
        for name in ('export_rules.lua', 'capture_json.lua'):
            shutil.copyfile(ROOT / 'engine_lite/lua' / name, addon / name)
        (addon / '_main.cfg').write_text(scenario(data_root, scope, options, terrain_includes), encoding='utf-8')
        command = [str(executable), '--userdata-dir', str(user), '--usercache-dir', str(user / 'cache'),
                   '--multiplayer', '--scenario=learning_rules_capture', '--era=era_default',
                   '--rng-seed=1', '--turns=1', '--nogui', '--nomusic', '--nosound',
                   '--nobanner', '--no-log-to-file']
        env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
        completed = subprocess.run(command, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=timeout)
    capture = None
    diagnostics = []
    for line in completed.stdout.decode('utf-8', errors='replace').splitlines():
        if line.startswith('RULE_CAPTURE '):
            capture = json.loads(line[len('RULE_CAPTURE '):])
        else:
            diagnostics.append(line)
    (output / f'{scope}.log').write_text('\n'.join(diagnostics) + '\n', encoding='utf-8')
    if capture is None or completed.returncode:
        raise RuntimeError(f'{scope}: native capture exit {completed.returncode}; see {output / (scope+".log")}')
    return capture


def scope_conflicts(captures):
    """Keep native IDs in evidence; namespace only differing compact definitions."""
    canonical_units = {}
    mappings = {}
    for capture in captures:
        mapping = {}
        for name, unit in capture['units'].items():
            definition = {k: v for k, v in unit.items() if k != 'scope'}
            previous = canonical_units.setdefault(name, definition)
            mapping[name] = name if canonical(previous) == canonical(definition) else f'{capture["scope"]}::{name}'
        mappings[capture['scope']] = mapping
    result = copy.deepcopy(captures)
    for capture in result:
        mapping = mappings[capture['scope']]
        units = {}
        for native_id, unit in capture['units'].items():
            name = mapping[native_id]
            unit['id'] = name
            if name != native_id:
                unit['native_id'] = native_id
            unit['advances_to'] = [mapping.get(n, n) for n in unit.get('advances_to', [])]
            for weapon in unit.get('weapons', []):
                if weapon.get('plague_type'):
                    weapon['plague_type'] = mapping.get(weapon['plague_type'], weapon['plague_type'])
            units[name] = unit
        capture['units'] = units
        capture['expected_units'] = sorted(units)
        for field in ('raw_definitions', 'variations'):
            capture[field] = {mapping.get(name, name): value for name, value in capture[field].items()}
    return result


def run(executable, data_root, output, *, scopes=None, terrain_rules=None, maps_dir=None, timeout=180):
    executable, data_root, output = Path(executable).resolve(), Path(data_root).resolve(), Path(output)
    version = subprocess.run([str(executable), '--simple-version'], check=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()
    if version != '1.18.8':
        raise ValueError(f'expected native 1.18.8, got {version}')
    output.mkdir(parents=True, exist_ok=False)
    inventory = build_inventory(data_root, binary=executable)
    (output / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n', encoding='utf-8')
    # Native terrain_types is an indexed userdata, not an iterable registry.
    # Enumerate declaration strings from the selected installation; all movement,
    # defense and terrain semantics are still queried in the actual native scope.
    terrain_codes = set()
    for path in data_root.rglob('*.cfg'):
        source = path.read_text(encoding='utf-8-sig', errors='replace')
        terrain_codes.update(re.findall(r'^\s*string\s*=\s*"?([A-Za-z0-9_^+/-]+)"?\s*(?:#.*)?$', source, re.M))
    if terrain_rules:
        terrain_codes.update(json.loads(Path(terrain_rules).read_text(encoding='utf-8'))['terrains'])
    frozen_maps = Path(maps_dir) if maps_dir is not None else ROOT / 'rules/1.18.8/maps'
    if maps_dir is not None or frozen_maps.exists():
        terrain_codes.update(map_terrain_codes(frozen_maps))
    terrain_codes = sorted(terrain_codes)
    terrain_includes = terrain_definition_files(data_root)
    selected = scopes or inventory['required_scopes']
    captures = []
    raw_dir = output / 'raw'
    raw_dir.mkdir()
    for scope in selected:
        if scope not in inventory['required_scopes']:
            raise ValueError(f'unknown native scope: {scope}')
        capture = capture_scope(executable, data_root, scope, inventory, terrain_codes, output, timeout,
                                terrain_includes)
        captures.append(capture)
        (raw_dir / (scope + '.json')).write_text(json.dumps(capture, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
        print(f'{scope}: {len(capture["units"])} units, {len(capture["terrains"])} terrains', flush=True)
    capture_dir = output / 'captures'
    capture_dir.mkdir()
    paths = []
    for capture in scope_conflicts(captures):
        path = capture_dir / (capture['scope'] + '.json')
        path.write_text(json.dumps(capture, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
        paths.append(path)
    catalog = freeze_captures(paths, output / 'frozen')
    print(json.dumps({k: catalog[k] for k in ('unit_count', 'terrain_count', 'scope_inventory_complete', 'coverage_counts')}), flush=True)
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', required=True)
    parser.add_argument('--data-root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--scope', action='append')
    parser.add_argument('--terrain-rules')
    parser.add_argument('--maps-dir', help='frozen map JSON directory; defaults to rules/1.18.8/maps when present')
    parser.add_argument('--timeout', type=float, default=180)
    args = parser.parse_args()
    run(args.executable, args.data_root, args.output, scopes=args.scope,
        terrain_rules=args.terrain_rules, maps_dir=args.maps_dir, timeout=args.timeout)


if __name__ == '__main__':
    main()
