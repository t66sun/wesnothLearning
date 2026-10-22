"""Locate the pinned official runtime and generate native WML scenarios."""
from functools import lru_cache
from pathlib import Path
import json
import os
import shutil
import subprocess
import params as P

ROOT = Path(__file__).resolve().parent


def creationflags():
    return subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def console_options():
    return ['--wnoconsole'] if os.name=='nt' else []


def find_wesnoth(value=None):
    value = value or os.environ.get('WESNOTH_EXE') or shutil.which('wesnoth')
    if not value or not Path(value).is_file():
        raise ValueError('set WESNOTH_EXE or pass --wesnoth with the Wesnoth 1.18.8 executable')
    exe = str(Path(value).resolve())
    check_version(exe)
    return exe


@lru_cache(maxsize=8)
def check_version(exe):
    result = subprocess.run([exe,'--simple-version',*console_options()],capture_output=True,text=True,timeout=20,creationflags=creationflags())
    if result.returncode or result.stdout.strip() != P.WESNOTH_VERSION:
        raise ValueError(f'Wesnoth {P.WESNOTH_VERSION} required; found {result.stdout.strip()!r}')
    return result.stdout.strip()


def userdata_path(exe):
    result = subprocess.run([exe,'--userdata-path',*console_options()],capture_output=True,text=True,encoding='utf-8',timeout=20,creationflags=creationflags())
    if result.returncode or not result.stdout.strip():
        raise RuntimeError('cannot determine Wesnoth userdata path')
    return Path(result.stdout.strip())


def lua(value):
    if value is None:
        return 'nil'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return '{' + ','.join(lua(v) for v in value) + '}'
    return '{' + ','.join('[' + lua(str(k)) + ']=' + lua(v) for k, v in value.items()) + '}'


def load_map(players):
    return json.loads((ROOT / f'maps/arena{players}.json').read_text(encoding='utf-8'))


def map_wml(board):
    rows = [r[:] for r in board['terrain']]
    for side, (x, y) in enumerate(board['starts'], 1):
        rows[y-1][x-1] = str(side) + ' ' + rows[y-1][x-1]
    border = ['Gg'] * (len(rows[0]) + 2)
    return '\n'.join(','.join(row) for row in [border] + [['Gg', *r, 'Gg'] for r in rows] + [border])


def contestant_ai(entry, side):
    return f'''[ai]
id=arena_contestant_{side}
[stage]
id=main_loop
name=ai_default_rca::candidate_action_evaluation_loop
[candidate_action]
engine=lua
id=arena_bot
name=arena_bot
max_score=1000000
location="~add-ons/arena_runtime/candidate.lua"
[args]
entry="{entry}"
[/args]
[/candidate_action]
[/stage]
[/ai]
'''


def scenario(config, factions, human_side=0):
    sides = []
    for side, faction in enumerate(factions, 1):
        i = P.FACTIONS.index(faction)
        sides.append(f'''[side]
side={side}
controller={'human' if side == human_side else 'ai'}
team_name={'team_'+str(config['teams'][side-1]) if config.get('teams') else 'side_'+str(side)}
share_view={'yes' if config.get('share_view',True) else 'no'}
share_maps={'yes' if config.get('share_maps',True) else 'no'}
user_team_name="Player {side}"
type={P.LEADERS[i]}
random_traits=no
gold={P.START_GOLD}
income=0
village_gold=2
village_support=1
recruit={P.RECRUITS[i]}
fog={'yes' if config['fog'] else 'no'}
shroud={'yes' if config.get('shroud',False) else 'no'}
[/side]''')
    return '''[multiplayer]
id=arena_native
name="Wesnoth Native Arena"
victory_when_enemies_defeated=no
turns=''' + str(config['max_turns']) + '''
experience_modifier=''' + str(P.XP_MODIFIER) + '''
map_data="''' + map_wml(config.get('map_override') or load_map(len(factions))) + '''"
{DEFAULT_SCHEDULE}
''' + '\n'.join(sides) + '''
[event]
name=preload
first_time_only=no
[lua]
code=<< wesnoth.require('~add-ons/arena_runtime/runtime.lua').setup(''' + lua(config) + ''') >>
[/lua]
[/event]
[/multiplayer]
'''
