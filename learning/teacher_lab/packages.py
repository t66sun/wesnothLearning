import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from learning.common import ROOT
import addons
import native


DEFAULT_CONFIG = dict(algorithm='beam', depth=2, width=6, root_width=18, reply_width=3,
                      risk=.35, village_value=14, position_weight=.8, tactical_ms=700, planning_ms=1000)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree_digest(directory):
    return hashlib.sha256(json.dumps({p.relative_to(directory).as_posix(): digest(p)
                                     for p in sorted(Path(directory).rglob('*')) if p.is_file()},
                                    sort_keys=True).encode()).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def registration(target, name):
    for filename, content in zip(('_main.cfg', 'ai.cfg'), addons.configuration(name)):
        (target / filename).write_text(content, encoding='utf-8')
    write_new(target / 'arena.json', dict(schema=2, id=name, entry='lua/bot.lua'))


def stage(source, name, destination, parameters=None):
    source = Path(source)
    addons.valid_name(name)
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    identity = tree_digest(source)
    old_name = read(source / 'arena.json')['id']
    with tempfile.TemporaryDirectory(prefix='teacher-package-') as temporary:
        target = Path(temporary) / name
        (target / 'lua').mkdir(parents=True)
        registration(target, name)
        for path in sorted((source / 'lua').rglob('*.lua')):
            output = target / path.relative_to(source)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(path.read_text(encoding='utf-8').replace(
                f'~add-ons/{old_name}/', f'~add-ons/{name}/'), encoding='utf-8')
        config = None
        if parameters is not None:
            config = dict(DEFAULT_CONFIG, **parameters)
            if config['tactical_ms'] > 700 or config['planning_ms'] > 1000:
                raise ValueError('candidate cannot exceed the declared planning budget')
            (target / 'lua/config.lua').write_text('return ' + native.lua(config) + '\n', encoding='utf-8')
        addons.pack(target, destination)
    return dict(name=name, package=str(destination.resolve()), package_sha256=digest(destination),
                source_sha256=identity, parameters=config)


def compose(choices, destination):
    """Only namespace relocation and format dispatch; selected strategies stay unchanged."""
    name = 'selected_teacher'
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory(prefix='teacher-selection-') as temporary:
        target = Path(temporary) / name
        (target / 'lua').mkdir(parents=True)
        registration(target, name)
        for fmt in ('duel', 'ffa4', 'team2v2'):
            chosen = choices[fmt]
            if digest(chosen['package']) != chosen['package_sha256']:
                raise ValueError('selected source package changed')
            with addons.open_addon(chosen['package']) as source:
                old = read(source / 'arena.json')['id']
                for path in sorted((source / 'lua').rglob('*.lua')):
                    output = target / 'lua' / fmt / path.relative_to(source / 'lua')
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(path.read_text(encoding='utf-8').replace(
                        f'~add-ons/{old}/lua/', f'~add-ons/{name}/lua/{fmt}/'), encoding='utf-8')
        (target / 'lua/bot.lua').write_text('''local side=wesnoth.current.side
local allied=false
for other=1,#wesnoth.sides do
    if side~=other and not wesnoth.sides.is_enemy(side,other) then allied=true end
end
local format=#wesnoth.sides==2 and 'duel' or allied and 'team2v2' or 'ffa4'
return wesnoth.dofile('~add-ons/selected_teacher/lua/'..format..'/bot.lua')
''', encoding='utf-8')
        addons.pack(target, destination)
    return dict(name=name, package=str(destination.resolve()), package_sha256=digest(destination),
                choices={fmt: row['name'] for fmt, row in choices.items()})
