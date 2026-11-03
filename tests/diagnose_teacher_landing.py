"""Measure the frozen b0025 duel landing decision on its exact native replay prefix."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import time

import addons
import match
from learning.common import ROOT, sha256


BLOCK = 'r3-ni-panel-duel-b0025-solo-'
TRACE_AT = '                        if s>score and '
ROW = '''                        M.landing_rows[#M.landing_rows+1]={id=u.id,enemy=e.id,
                            x=x,y=y,weapon=weapon,score=s,risk=risk,risk_weight=attack_risk,
                            defense=u:defense_on(terrain(x,y)),target_damage=target_damage,
                            slow=d.slowed,kill=kill,taken=taken,dealt=dealt,death=death,
                            expected_hp=a.average_hp,own_max=u.max_hitpoints,own_value=uv,
                            enemy_max=e.max_hitpoints,enemy_value=ev}
'''


def insert(text, anchor, replacement):
    if text.count(anchor) != 1:
        raise ValueError(f'expected one frozen duel diagnostic anchor: {anchor}')
    return text.replace(anchor, replacement)


def traced_duel(source, adapted):
    text = insert(source, 'local M = {}', 'local M = {landing_rows={},landing_cutoff=false}')
    row = ROW if adapted else ROW.replace('target_damage=target_damage,', '')
    text = insert(text, TRACE_AT, row + TRACE_AT)
    cutoff = 'if sims>=240 or wesnoth.ms_since_init()-start>350 then return best end'
    return insert(text, cutoff, cutoff.replace('then return', 'then M.landing_cutoff=true;return'))


def stage(package, directory, challenger):
    with addons.open_addon(package) as addon:
        staged = directory / addon.name
        shutil.copytree(addon, staged)
    lua = staged / 'lua'
    source = (lua / 'duel.lua').read_text()
    if challenger:
        # Only the measured decision uses the challenger; every earlier decision uses the panel bot.
        source = (challenger / 'lua/duel.lua').read_text().replace(
            '~add-ons/gpt6astra/lua/value.lua', f'~add-ons/{staged.name}/lua/landing_probe_value.lua')
        shutil.copyfile(challenger / 'lua/value.lua', lua / 'landing_probe_value.lua')
    (lua / 'landing_probe_duel.lua').write_text(traced_duel(source, staged.name == 'astra_adapted'))
    wrapper = (ROOT / 'tests/fixtures/teacher_landing_probe.lua').read_text()
    (lua / 'bot.lua').write_text(wrapper.replace('ADDON', staged.name))
    return staged


def commands(path):
    replay = gzip.decompress(path.read_bytes()).split(b'\n[replay]\n', 1)[1].split(b'\n[/replay]', 1)[0]
    return re.findall(rb'\t\[command\]\n.*?\t\[/command\]', replay, re.DOTALL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panel', type=Path, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--variant', choices=('control', 'adapted', 'challenger'), required=True)
    parser.add_argument('--challenger', type=Path)
    args = parser.parse_args()
    if bool(args.challenger) != (args.variant == 'challenger'):
        parser.error('--challenger add-on directory is required only for the challenger variant')
    args.output.mkdir(parents=True, exist_ok=False)
    ident = BLOCK + ('r0' if args.variant == 'control' else 'r1')
    job = next(j for j in json.loads((args.panel / 'schedule.json').read_bytes()) if j['id'] == ident)
    identity = json.loads((args.panel / 'identities.json').read_bytes())
    inputs = [Path(job['wesnoth']), match.ENTROPY_SHIM, *map(Path, job['bots'])]
    for name in inputs:
        expected = next(h for filename, h in identity['artifacts'].items() if Path(filename).name == name.name)
        if sha256(name) != expected:
            raise ValueError(f'frozen panel input changed: {name}')
    staged = stage(job['bots'][1], args.output, args.challenger)
    output = args.output / 'native.json'
    result = match.play_game(bots=[job['bots'][0], str(staged)], factions=job['factions'],
        seed=job['seed'], wesnoth=job['wesnoth'], max_turns=4, timeout=job['timeout'],
        first_timeout=job['first_timeout'], map_override=job['map_override'], teams=job['teams'],
        experiment_deadline=time.time()+120, replay_path=output)
    if result['faults'] or result['reason'] != 'landing_diagnosis':
        raise RuntimeError(f'fixed decision not completed: {result}')
    traces = [r['data'] for r in map(json.loads, output.with_suffix('.events.jsonl').read_text().splitlines())
              if r['event'] == 'LANDING_DECISION']
    trace, = traces
    old_path = args.panel / 'replays' / f'{ident}.replay.gz'
    old = commands(old_path)
    new = commands(output.with_suffix('.replay.gz'))
    length = 191 if args.challenger else 194
    if len(new) < length or new[:length] != old[:length]:
        first = next((n for n, (a, b) in enumerate(zip(old[:length], new[:length]), 1) if a != b), len(new)+1)
        raise ValueError(f'native commands differ at command {first}')
    ranked = sorted(trace['rows'], key=lambda row: -row['score'])
    pair = [dict(row, rank=i) for i,row in enumerate(ranked,1) if row['id']=='Elvish Shaman-14'
            and row['enemy']=='Cavalryman-8' and row['weapon']==2 and (row['x'],row['y']) in ((21,19),(20,18))]
    if len(pair) != 2 or not (trace['grass_legal'] and trace['village_legal']):
        raise ValueError('both legal entangle landings must have actual score rows')
    summary = dict(source=args.source, variant=args.variant, job=ident, seed=job['seed'],
        scenario_family=job['scenario_family'], frozen_packages={Path(f).name:sha256(f) for f in job['bots']},
        native_executable_sha256=sha256(job['wesnoth']), entropy_shim_sha256=sha256(match.ENTROPY_SHIM),
        old_replay_sha256=sha256(old_path), prefix191_sha256=hashlib.sha256(b''.join(old[:191])).hexdigest(),
        matched_commands=length, candidate_count=len(ranked), cutoff=trace['cutoff'], plan=trace['plan'],
        actor=trace['actor'], target=trace['target'], village_legal=trace['village_legal'],
        grass_legal=trace['grass_legal'], landings=pair, highest_scored=ranked[0])
    if args.challenger:
        summary['challenger_duel_sha256'] = sha256(args.challenger/'lua/duel.lua')
        summary['challenger_value_sha256'] = sha256(args.challenger/'lua/value.lua')
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()