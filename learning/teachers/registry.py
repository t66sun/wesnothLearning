"""Frozen teacher sets shared by collection, opponents and reference jobs."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import zipfile
from functools import lru_cache
from pathlib import Path

from ..common import ROOT, sha256
from ..formats import FORMATS
from . import build, lineage, source_digest

CONTRACT_VERSION = 1
SETS = ('astra', 'mixed-20261107')
# Activation follows the bounded integration acceptance panel.
DEFAULT_SET = 'astra'
RUNTIME_SETS = ('astra',)
ROLES = ('supervision', 'opponent', 'evaluation', 'reward_reference')
DELIVERY = ROOT / 'delivery/search_teacher_20261107'
SELECTED_SHA256 = '6b461de4e99303321b0119a7b88babd575c2d786500b28da4cb45d3c2bdabdb3'


def validate_set(name):
    if name not in SETS:
        raise ValueError('unknown teacher set: ' + str(name))
    return name


def require_runtime(name):
    validate_set(name)
    if name not in RUNTIME_SETS:
        raise ValueError('teacher runtime integration is pending: ' + name)


def selected_manifest():
    metadata = json.loads((DELIVERY / 'manifest.json').read_text(encoding='utf-8'))
    if metadata['package_sha256'] != SELECTED_SHA256:
        raise ValueError('selected teacher delivery identity changed')
    return metadata


def _strategy_digest(archive, prefix):
    digest = hashlib.sha256()
    names = sorted(n for n in archive.namelist() if n.startswith(prefix) and n.endswith('.lua'))
    if not names:
        raise ValueError('teacher strategy has no Lua modules')
    for name in names:
        digest.update(name[len(prefix):].encode())
        digest.update(b'\0')
        digest.update(archive.read(name))
        digest.update(b'\0')
    return digest.hexdigest()


def describe(path, fmt):
    """Describe actual executable bytes, separately from the Astra parent archive."""
    if fmt not in FORMATS:
        raise ValueError('unknown teacher format: ' + str(fmt))
    path = Path(path).resolve()
    package_hash = sha256(path)
    with zipfile.ZipFile(path) as archive:
        registrations = [n for n in archive.namelist() if n.count('/') == 1 and n.endswith('/arena.json')]
        if len(registrations) != 1:
            raise ValueError('teacher package must have one registration')
        registration = json.loads(archive.read(registrations[0]))
        name = registration['id']
        if name == 'selected_teacher':
            if package_hash != SELECTED_SHA256:
                raise ValueError('selected teacher package differs from the frozen delivery')
            strategy = selected_manifest()['strategies'][fmt]
            entry = f'~add-ons/{name}/lua/{fmt}/bot.lua'
            profile = 'search-local-v1'
            source_hash = _strategy_digest(archive, f'{name}/lua/{fmt}/')
            parameters = strategy['parameters']
            candidate = strategy['candidate']
            commit = strategy['source_commit']
            timeout, first = 2, 20
        elif name == 'gpt6astra':
            # Training executes the maintained source, never the frozen lineage ZIP.
            from . import SOURCE
            expected = {f'gpt6astra/{p.relative_to(SOURCE).as_posix()}': p.read_bytes()
                        for p in SOURCE.rglob('*') if p.is_file()}
            if set(archive.namelist()) != set(expected) or any(archive.read(n) != b for n, b in expected.items()):
                raise ValueError('Astra executable package differs from maintained source')
            entry = f'~add-ons/{name}/lua/{"duel" if fmt == "duel" else "four"}.lua'
            profile = lineage()['teacher_profile']
            source_hash = source_digest()
            parameters, candidate, commit = {}, 'maintained_astra', None
            timeout, first = 1, 10
        else:
            raise ValueError('unsupported teacher package: ' + str(name))
    return dict(contract=CONTRACT_VERSION, teacher=name, format=fmt, package=str(path),
                package_sha256=package_hash, source_sha256=source_hash, profile=profile,
                strategy=candidate, source_commit=commit, entry=entry,
                parameters=copy.deepcopy(parameters), timeout=timeout, first_timeout=first)


def freeze_set(directory, name):
    """Create an immutable set; the caller owns the new experiment directory."""
    validate_set(name)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    astra = build(directory / 'gpt6astra.zip')
    selected = None
    if name == 'mixed-20261107':
        metadata = selected_manifest()
        source = DELIVERY / metadata['package']
        if sha256(source) != SELECTED_SHA256:
            raise ValueError('selected teacher package differs from the frozen delivery')
        selected = directory / source.name
        shutil.copyfile(source, selected)
    formats = {}
    for fmt in FORMATS:
        spec = describe(selected if selected and fmt != 'ffa4' else astra, fmt)
        formats[fmt] = {role: copy.deepcopy(spec) for role in ROLES}
    return dict(version=CONTRACT_VERSION, name=name, formats=formats,
                astra_parent=lineage().get('teacher_parent_sha256'))


def role(manifest, fmt, name='supervision'):
    contract = manifest.get('teacher_set')
    if contract is None:
        return None
    if contract.get('version') != CONTRACT_VERSION or name not in ROLES:
        raise ValueError('unsupported teacher contract or role')
    return copy.deepcopy(contract['formats'][fmt][name])


def verify_set(contract):
    if contract.get('version') != CONTRACT_VERSION:
        raise ValueError('unsupported teacher contract')
    validate_set(contract['name'])
    if set(contract['formats']) != set(FORMATS):
        raise ValueError('teacher set must describe all formats')
    for fmt, roles in contract['formats'].items():
        if set(roles) != set(ROLES):
            raise ValueError('teacher role set changed')
        expected_name = 'selected_teacher' if contract['name'] == 'mixed-20261107' and fmt != 'ffa4' else 'gpt6astra'
        for spec in roles.values():
            if spec['teacher'] != expected_name or spec != describe(spec['package'], fmt):
                raise ValueError('frozen teacher descriptor changed: ' + fmt)


def require_same_teachers(parent, child, formats):
    """A same-name set can change executable bytes; raw supervision cannot follow."""
    before, after = parent.get('teacher_set'), child.get('teacher_set')
    if before is None and after is None:
        same = parent.get('teacher') == child.get('teacher')
    elif before is None:
        legacy = parent.get('teacher', {})
        same = all((spec['teacher'], spec['profile'], spec['source_sha256']) ==
                   (legacy.get('teacher'), legacy.get('teacher_profile'), legacy.get('teacher_source_sha256'))
                   for fmt in formats for spec in after['formats'][fmt].values())
    elif after is None:
        same = False
    else:
        def portable(spec):
            return {key: value for key, value in spec.items() if key != 'package'}
        same = all(portable(before['formats'][fmt][name]) == portable(after['formats'][fmt][name])
                   for fmt in formats for name in ROLES)
    if not same:
        raise ValueError('teacher execution identity changed; use explicit weights-only initialization')


@lru_cache(maxsize=2)
def adapter_digest(engine):
    paths = (['learning/lite_host.py', 'engine_lite/src/lib.rs', 'engine_lite/src/host.rs',
              'engine_lite/lua/host.lua'] if engine == 'lite' else
             ['learning/sample.py', 'learning/collector.lua', 'lua/teacher.lua',
              'vendor/arena/match.py', 'vendor/arena/runtime/candidate.lua'])
    digest = hashlib.sha256()
    for name in paths:
        path = ROOT / name
        digest.update(name.encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def execution_identity(spec, engine):
    if engine not in ('native', 'lite'):
        raise ValueError('unsupported teacher backend')
    return dict(teacher_contract=CONTRACT_VERSION, teacher=spec['teacher'],
                teacher_profile=spec['profile'], teacher_source_sha256=spec['source_sha256'],
                teacher_package_sha256=spec['package_sha256'], teacher_strategy=spec['strategy'],
                teacher_adapter_sha256=adapter_digest(engine), teacher_backend=engine)


def module_sources(spec):
    if sha256(spec['package']) != spec['package_sha256']:
        raise ValueError('frozen teacher package changed')
    with zipfile.ZipFile(spec['package']) as archive:
        return {'~add-ons/' + name: archive.read(name).decode('utf-8')
                for name in archive.namelist() if name.endswith('.lua')}
