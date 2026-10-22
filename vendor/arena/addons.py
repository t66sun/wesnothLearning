"""Create, validate, zip, and install native WML/Lua contestant add-ons."""
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
import json
import re
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
MAX_PACKAGE_BYTES = 16 * 1024 * 1024
NAME = re.compile(r'[A-Za-z][A-Za-z0-9_.]{0,39}\Z')


def configuration(name):
    main = f'''# Generated registration. Edit lua/bot.lua, not this file.
#ifdef MULTIPLAYER
[modification]
id=arena_{name}
name="Arena AI: {name}"
description="Native Lua contestant AI: {name}"
type=hybrid
require_modification=yes
{{~add-ons/{name}/ai.cfg}}
[/modification]
#endif
'''
    ai = f'''[ai]
id=arena_{name}
description="Arena AI: {name}"
mp_rank=900
[stage]
id=main_loop
name=ai_default_rca::candidate_action_evaluation_loop
[candidate_action]
id=arena_bot
name=arena_bot
engine=lua
max_score=1000000
location="~add-ons/{name}/lua/bot.lua"
[/candidate_action]
[/stage]
[/ai]
'''
    return main, ai


def valid_name(name):
    stem = name.split('.', 1)[0]
    if not NAME.fullmatch(name) or name.endswith('.') or '..' in name or name.casefold() in {'baseline', 'human', 'arena_runtime'} or stem.casefold() in {'con', 'prn', 'aux', 'nul'} or re.fullmatch(r'(com|lpt)[1-9]', stem, re.I):
        raise ValueError('team name must be 1-40 ASCII letters/digits/underscores/dots, start with a letter, and not use reserved names, trailing dots, or consecutive dots')
    return name


def validate(directory):
    if Path(directory).is_symlink():
        raise ValueError('submission directory cannot be a symbolic link')
    root = Path(directory).resolve()
    if root.is_symlink() or not root.is_dir():
        raise ValueError('expected an add-on directory')
    try:
        meta = json.loads((root / 'arena.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'{root}: missing or invalid arena.json') from exc
    name = valid_name(meta.get('id', ''))
    if meta != {'schema': 2, 'id': name, 'entry': 'lua/bot.lua'} or root.name != name:
        raise ValueError('arena.json or directory name does not match the native-v2 submission schema')
    for filename, expected in zip(('_main.cfg', 'ai.cfg'), configuration(name)):
        if (root / filename).read_text(encoding='utf-8-sig') != expected:
            raise ValueError(f'{filename}: registration must match the SDK-generated configuration')
    total = 0
    entries = list(root.rglob('*'))
    if len(entries)+1 > 512:
        raise ValueError('submission exceeds 512 entries')
    for p in entries:
        if p.is_symlink() or not p.resolve().is_relative_to(root):
            raise ValueError('links outside the add-on are forbidden')
        if p.is_file():
            relative = p.relative_to(root)
            allowed = relative.as_posix() in {'arena.json', '_main.cfg', 'ai.cfg', 'README.md', 'LICENSE'} or (relative.parts[0] == 'lua' and p.suffix == '.lua')
            if not allowed:
                raise ValueError(f'unsupported submission file: {relative}')
            total += p.stat().st_size
    if total > MAX_PACKAGE_BYTES or not (root / 'lua/bot.lua').is_file():
        raise ValueError('missing lua/bot.lua or submission exceeds 16 MiB')
    return name


@contextmanager
def open_addon(path):
    path = Path(path).resolve()
    if path.is_dir():
        validate(path)
        yield path
        return
    if not path.is_file() or path.suffix.lower() != '.zip':
        raise ValueError(f'not a native add-on directory or zip: {path}')
    with tempfile.TemporaryDirectory(prefix='arena-submission-') as temp:
        root = Path(temp)
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > 512 or sum(i.file_size for i in infos) > MAX_PACKAGE_BYTES:
                raise ValueError('zip exceeds file count or size limit')
            names = set()
            for info in infos:
                p = PurePosixPath(info.filename)
                if not p.parts or p.is_absolute() or any(s in {'', '.', '..'} or ':' in s for s in p.parts) or '\\' in info.filename or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('unsafe zip path or symbolic link')
                if p.as_posix()!=info.filename.rstrip('/') or any(s.rstrip(' .')!=s or re.fullmatch(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?',s,re.I) for s in p.parts):
                    raise ValueError('noncanonical or reserved zip path')
                key = info.filename.casefold().rstrip('/')
                if key in names:
                    raise ValueError('duplicate zip entry')
                names.add(key)
                target = root.joinpath(*p.parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as src, target.open('wb') as dst:
                        shutil.copyfileobj(src, dst)
        dirs = list(root.iterdir())
        if len(dirs) != 1 or not dirs[0].is_dir():
            raise ValueError('zip must contain exactly one top-level add-on folder')
        validate(dirs[0])
        yield dirs[0]


def create(name, destination):
    valid_name(name)
    path = Path(destination).resolve() / name
    if path.exists():
        raise ValueError(f'already exists: {path}')
    path.mkdir(parents=True)
    (path / 'lua').mkdir()
    for filename, text in zip(('_main.cfg', 'ai.cfg'), configuration(name)):
        (path / filename).write_text(text, encoding='utf-8')
    (path / 'arena.json').write_text(json.dumps({'schema': 2, 'id': name, 'entry': 'lua/bot.lua'}, indent=2) + '\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'sdk/template_bot/lua/bot.lua', path / 'lua/bot.lua')
    return path


def pack(path, output):
    path = Path(path).resolve()
    validate(path)
    output = Path(output).resolve()
    if output.is_relative_to(path):
        raise ValueError('output zip must be outside the add-on directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(path.rglob('*')):
            if file.is_file():
                archive.write(file, f'{path.name}/{file.relative_to(path).as_posix()}')
    return output


def install(path, userdata):
    with open_addon(path) as addon:
        destination = Path(userdata).resolve() / 'data/add-ons' / addon.name
        if destination.exists():
            raise ValueError(f'will not overwrite existing add-on: {destination}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(addon, destination)
    return destination
