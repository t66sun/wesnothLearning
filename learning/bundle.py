"""Build and statically verify the extraction-ready Ubuntu 24.04 training archive.

The tarball is the only thing the training box receives: the source tree, the
frozen 1.18.8 training rules, the curated human games and the opponents, but no
run state, virtual environment or machine-local cache. The builder writes every
hash the verifier checks, so a fresh machine can prove the archive was not
reshaped between the workstation and setup.sh.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from .common import ROOT

ARCHIVE_ROOT = 'WesnothLearning'
SCHEMA = 1
RULES_DIR = 'data/rules/1.18.8-training'
CATALOG = RULES_DIR + '/catalog-summary.json'
HUMAN_CURATED = 'data/humanData_curated/games.jsonl'
MANIFEST_NAME = 'BUNDLE_MANIFEST.json'
SUMS_NAME = 'SHA256SUMS'
TORCH = '2.9.1'
SOURCE_ROOTS = ('learning', 'lua', 'engine_lite', 'vendor', 'tests', 'benchmarks', 'docs')
SOURCE_FILES = ('README.md', 'LICENSE', 'requirements.txt', 'setup.sh', 'run.sh', 'train.sh', '.gitattributes')
DATA_PATHS = (RULES_DIR, 'data/humanData_curated', 'data/opponents', 'data/datasets')
EXCLUDE_PARTS = frozenset({'.git', '.venv', '__pycache__', '.cache', '.runtime', 'runs', 'verification', 'delivery',
                           'tmp', '.ssh', '.codegraph', '.pi', 'target', '.pytest_cache', '.mypy_cache', '.ruff_cache'})
EXCLUDE_PREFIXES = ('data/references', 'data/humanData', 'data/rules/1.18.8')
EXCLUDE_SUFFIXES = ('.pyc', '.pyo', '.pyd', '.dll', '.exe')
EXCLUDE_FILES = ('AGENTS.md',)
EXCLUDED = sorted(set(EXCLUDE_PARTS) | set(EXCLUDE_PREFIXES) | set(EXCLUDE_FILES)
                  | {'*' + suffix for suffix in EXCLUDE_SUFFIXES})
REQUIRED_PATHS = (
    'setup.sh', 'run.sh', 'train.sh', 'requirements.txt', 'README.md', 'LICENSE',
    'learning/__main__.py', 'learning/bundle.py',
    'engine_lite/Cargo.toml', 'engine_lite/Cargo.lock', 'engine_lite/pyproject.toml',
    'engine_lite/src/lib.rs', 'engine_lite/lua/host.lua',
    'lua/observation.lua', 'vendor/arena/runtime/runtime.lua',
    RULES_DIR + '/rules.json', RULES_DIR + '/catalog-summary.json',
    RULES_DIR + '/coverage.json', RULES_DIR + '/catalog.json',
    'data/opponents/gpt6astra.zip', HUMAN_CURATED, 'data/datasets/human/import.json',
    'docs/bundle.md', 'docs/bundle_zh.md',
)
SUM_LINE = re.compile(r'^([0-9a-f]{64}) [ *](.+)$')


def _hexdigest(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _excluded(relative):
    text = relative.as_posix()
    if text in EXCLUDE_FILES:
        return True
    if any(text == prefix or text.startswith(prefix + '/') for prefix in EXCLUDE_PREFIXES):
        return True
    return bool(EXCLUDE_PARTS.intersection(relative.parts)) or relative.suffix in EXCLUDE_SUFFIXES


def _mode(name):
    return 0o755 if name.endswith('.sh') else 0o644


def _bad_name(name):
    """Reject member names that extract outside the archive root or are ambiguous."""
    if not name:
        return 'empty member name'
    if '\\' in name:
        return 'backslash in member name'
    if name.startswith('/') or re.match(r'^[A-Za-z]:', name):
        return 'absolute member name'
    parts = name.split('/')
    if '..' in parts:
        return 'parent reference in member name'
    if any(part in ('', '.') for part in parts):
        return 'malformed member path'
    return ''


def _source_identity(root):
    """Record the commit only when the root is itself the repository top level."""
    try:
        top = subprocess.run(('git', '-C', str(root), 'rev-parse', '--show-toplevel'),
                             capture_output=True, text=True, check=True).stdout.strip()
        if Path(top).resolve() != Path(root).resolve():
            return dict(commit=None, dirty=None)
        commit = subprocess.run(('git', '-C', str(root), 'rev-parse', 'HEAD'),
                                capture_output=True, text=True, check=True).stdout.strip()
        status = subprocess.run(('git', '-C', str(root), 'status', '--porcelain'),
                                capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return dict(commit=None, dirty=None)
    return dict(commit=commit, dirty=bool(status.strip()))


def _created_at(value):
    if value is None:
        stamp = datetime.now(timezone.utc)
    else:
        try:
            stamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('created_at must be an ISO 8601 timestamp: ' + str(value)) from None
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ')


def _rules_identity(root):
    directory = Path(root) / RULES_DIR
    summary_path = directory / 'catalog-summary.json'
    rules_path = directory / 'rules.json'
    if not summary_path.is_file() or not rules_path.is_file():
        raise ValueError('missing frozen rule identity: ' + str(directory.resolve()))
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    digest = _hexdigest(rules_path)
    if summary.get('rules_file_sha256') != digest:
        raise ValueError('rules.json differs from ' + CATALOG)
    missing = [name for name in ('source_hash', 'unit_count', 'terrain_count') if summary.get(name) in (None, '')]
    if missing:
        raise ValueError(CATALOG + ' is missing ' + ', '.join(missing))
    return dict(directory=RULES_DIR, rules_file_sha256=digest, source_hash=summary['source_hash'],
                unit_count=summary['unit_count'], terrain_count=summary['terrain_count'])


def _wheel(wheel):
    if wheel is None:
        return None
    path = Path(wheel)
    if not path.is_file():
        raise ValueError('wheel does not exist: ' + str(path))
    name = path.name.lower()
    if not name.endswith('.whl'):
        raise ValueError('wheel must be a .whl file: ' + path.name)
    if 'manylinux' not in name or 'x86_64' not in name:
        raise ValueError('wheel must target manylinux x86_64: ' + path.name)
    return path


def _payload(root, wheel=None):
    root = Path(root)
    entries = {}
    for name in SOURCE_FILES:
        path = root / name
        if not path.is_file():
            raise ValueError('missing source file: ' + name)
        entries[name] = path
    for name in SOURCE_ROOTS + DATA_PATHS:
        directory = root / name
        if not directory.is_dir():
            raise ValueError('missing source directory: ' + name)
        for path in sorted(directory.rglob('*')):
            relative = path.relative_to(root)
            if not path.is_file() or _excluded(relative):
                continue
            entries[relative.as_posix()] = path
    if wheel is not None:
        entries['dist/' + wheel.name] = wheel
    missing = [name for name in REQUIRED_PATHS if name not in entries]
    if missing:
        raise ValueError('archive is missing required paths: ' + ', '.join(missing))
    return dict(sorted(entries.items()))


def _file_rows(entries):
    return [dict(path=name, size=path.stat().st_size, sha256=_hexdigest(path), mode='%04o' % _mode(name))
            for name, path in entries.items()]


def _manifest(root, rows, rules, wheel, created_at):
    by_name = {row['path']: row for row in rows}
    return {
        'schema': SCHEMA,
        'target': {'os': 'ubuntu', 'version': '24.04', 'arch': 'x86_64', 'python': '3.12', 'device': 'cpu'},
        'created_at': created_at,
        'source': _source_identity(root),
        'files': rows,
        'data': {
            'rules': rules,
            'opponents': [dict(path=name, sha256=row['sha256']) for name, row in sorted(by_name.items())
                          if name.startswith('data/opponents/')],
            'human_curated': dict(path=HUMAN_CURATED, sha256=by_name[HUMAN_CURATED]['sha256']),
        },
        'build': {'wheel': 'dist/' + wheel.name if wheel is not None else None, 'torch': TORCH},
        'totals': {'files': len(rows), 'bytes': sum(row['size'] for row in rows)},
        'excluded': EXCLUDED,
        'verification': {'static': True, 'ubuntu_runtime': 'pending'},
    }


def _sums(rows):
    """GNU sha256sum lines relative to the bundle root, so `sha256sum -c` runs after cd."""
    lines = ['%s  %s' % (row['sha256'], row['path']) for row in sorted(rows, key=lambda row: row['path'])]
    return ('\n'.join(lines) + '\n').encode('utf-8')


def _info(name, type_, mode, size=0):
    info = tarfile.TarInfo(name)
    info.type = type_
    info.mode = mode
    info.size = size
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    return info


def _write(output, blobs, paths):
    """Stream one gzip member with mtime 0 around a PAX tar of fixed-order members."""
    directories = {ARCHIVE_ROOT}
    for name in list(blobs) + list(paths):
        parent = Path(name).parent
        while parent.as_posix() not in ('', '.'):
            directories.add(parent.as_posix())
            parent = parent.parent
    with open(output, 'wb') as handle:
        with gzip.GzipFile(filename='', mode='wb', fileobj=handle, mtime=0, compresslevel=6) as gz:
            with tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as tar:
                for name in sorted(directories):
                    tar.addfile(_info(name + '/', tarfile.DIRTYPE, 0o755))
                for name in sorted(blobs):
                    data = blobs[name]
                    tar.addfile(_info(name, tarfile.REGTYPE, _mode(name), len(data)), io.BytesIO(data))
                for name in sorted(paths):
                    path = paths[name]
                    with open(path, 'rb') as stream:
                        tar.addfile(_info(name, tarfile.REGTYPE, _mode(name), path.stat().st_size), stream)


def build_bundle(output, root=ROOT, wheel=None, created_at=None):
    """Write the deterministic training archive and return its manifest summary."""
    output = Path(output)
    root = Path(root)
    if output.exists():
        raise FileExistsError(output)
    stamp = _created_at(created_at)
    wheel_path = _wheel(wheel)
    rules = _rules_identity(root)
    entries = _payload(root, wheel_path)
    rows = _file_rows(entries)
    manifest = _manifest(root, rows, rules, wheel_path, stamp)
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    manifest_row = dict(path=MANIFEST_NAME, size=len(manifest_bytes),
                        sha256=hashlib.sha256(manifest_bytes).hexdigest(), mode='%04o' % _mode(MANIFEST_NAME))
    sums_bytes = _sums(rows + [manifest_row])
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + '.tmp')
    blobs = {ARCHIVE_ROOT + '/' + MANIFEST_NAME: manifest_bytes, ARCHIVE_ROOT + '/' + SUMS_NAME: sums_bytes}
    paths = {ARCHIVE_ROOT + '/' + name: path for name, path in entries.items()}
    try:
        _write(temporary, blobs, paths)
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return dict(archive=str(output), sha256=_hexdigest(output), files=len(rows) + 2,
                bytes=sum(row['size'] for row in rows) + len(manifest_bytes) + len(sums_bytes),
                created_at=stamp, source=_source_identity(root),
                rules=dict(directory=RULES_DIR, unit_count=rules['unit_count'], terrain_count=rules['terrain_count']),
                wheel='dist/' + wheel_path.name if wheel_path is not None else None)


def _read_manifest(manifest, files, errors):
    if not isinstance(manifest, dict):
        errors.append('manifest must be a JSON object')
        return
    if manifest.get('schema') != SCHEMA:
        errors.append('manifest schema is not %d' % SCHEMA)
    target = manifest.get('target') or {}
    if target.get('version') != '24.04' or target.get('arch') != 'x86_64':
        errors.append('manifest target must be Ubuntu 24.04 x86_64')
    rows = manifest.get('files')
    if not isinstance(rows, list):
        errors.append('manifest files must be a list')
        rows = []
    listed = {}
    for row in rows:
        if not isinstance(row, dict):
            errors.append('manifest file entry must be an object')
            continue
        path = str(row.get('path', ''))
        if not path:
            errors.append('manifest entry without path')
            continue
        if path in listed:
            errors.append('duplicate manifest entry: ' + path)
            continue
        listed[path] = row
        if path in (MANIFEST_NAME, SUMS_NAME):
            errors.append('manifest must not list ' + path)
            continue
        name = ARCHIVE_ROOT + '/' + path
        if name not in files:
            errors.append('manifest lists missing file: ' + path)
            continue
        actual = files[name]
        if row.get('size') != actual['size']:
            errors.append('manifest size mismatch: ' + path)
        if row.get('sha256') != actual['sha256']:
            errors.append('manifest hash mismatch: ' + path)
        if row.get('mode') != '%04o' % (actual['mode'] & 0o777):
            errors.append('manifest mode mismatch: ' + path)
    expected = {row['relative'] for name, row in files.items()
                if row['relative'] not in (MANIFEST_NAME, SUMS_NAME)}
    for path in sorted(expected - set(listed)):
        errors.append('manifest is missing file: ' + path)
    for path in sorted(set(listed) - expected):
        errors.append('manifest lists unexpected file: ' + path)
    totals = manifest.get('totals') or {}
    if totals.get('files') != len(rows):
        errors.append('manifest totals.files does not match its own file list')
    if totals.get('bytes') != sum(row.get('size', 0) for row in rows if isinstance(row, dict)):
        errors.append('manifest totals.bytes does not match its own file list')


def _read_rules(manifest, files, captured, errors):
    data = manifest.get('data') or {}
    rules = data.get('rules') or {}
    if rules.get('directory') != RULES_DIR:
        errors.append('manifest rules directory is not ' + RULES_DIR)
    rules_name = ARCHIVE_ROOT + '/' + RULES_DIR + '/rules.json'
    if rules_name not in files:
        errors.append('missing ' + RULES_DIR + '/rules.json')
    elif rules.get('rules_file_sha256') != files[rules_name]['sha256']:
        errors.append('manifest rules hash does not match archived rules.json')
    summary = captured.get(CATALOG)
    if summary is None:
        errors.append('missing ' + CATALOG)
    else:
        try:
            catalog = json.loads(summary.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append('catalog-summary is not valid JSON: ' + str(exc))
            catalog = None
        if isinstance(catalog, dict):
            for name in ('rules_file_sha256', 'source_hash', 'unit_count', 'terrain_count'):
                if catalog.get(name) != rules.get(name):
                    errors.append('catalog-summary %s differs from the manifest' % name)
    opponents = data.get('opponents')
    if not isinstance(opponents, list) or not opponents:
        errors.append('manifest lists no opponents')
    else:
        for row in opponents:
            path = str((row or {}).get('path', ''))
            name = ARCHIVE_ROOT + '/' + path
            if name not in files:
                errors.append('manifest opponent is missing: ' + path)
            elif row.get('sha256') != files[name]['sha256']:
                errors.append('manifest opponent hash mismatch: ' + path)
            if not path.startswith('data/opponents/'):
                errors.append('manifest opponent is outside data/opponents: ' + path)
    curated = data.get('human_curated') or {}
    curated_name = ARCHIVE_ROOT + '/' + str(curated.get('path', ''))
    if curated.get('path') != HUMAN_CURATED:
        errors.append('manifest human_curated path is not ' + HUMAN_CURATED)
    elif curated_name not in files:
        errors.append('missing ' + HUMAN_CURATED)
    elif curated.get('sha256') != files[curated_name]['sha256']:
        errors.append('manifest human_curated hash mismatch')


def _read_wheel(manifest, files, require_wheel, errors):
    wheel = (manifest.get('build') or {}).get('wheel')
    if wheel is None:
        if require_wheel:
            errors.append('archive has no wheel but --require-wheel was given')
        return
    path = str(wheel)
    name = ARCHIVE_ROOT + '/' + path
    if not path.startswith('dist/'):
        errors.append('wheel must live in dist/: ' + path)
    if name not in files:
        errors.append('manifest wheel is missing: ' + path)
    lowered = path.lower()
    if 'manylinux' not in lowered or 'x86_64' not in lowered:
        errors.append('wheel is not manylinux x86_64: ' + path)


def _read_sums(captured, files, errors):
    text = captured.get(SUMS_NAME)
    if text is None:
        errors.append('missing ' + ARCHIVE_ROOT + '/' + SUMS_NAME)
        return
    listed = {}
    for number, line in enumerate(text.decode('utf-8', 'replace').splitlines(), 1):
        match = SUM_LINE.match(line)
        if not match:
            errors.append('%s line %d is not sha256sum format' % (SUMS_NAME, number))
            continue
        digest, path = match.groups()
        if path in listed:
            errors.append('%s line %d repeats %s' % (SUMS_NAME, number, path))
            continue
        listed[path] = digest
    for path, digest in listed.items():
        name = ARCHIVE_ROOT + '/' + path
        if name in files and files[name]['sha256'] != digest:
            errors.append('%s hash mismatch: %s' % (SUMS_NAME, path))
    expected = {row['relative'] for row in files.values() if row['relative'] != SUMS_NAME}
    for path in sorted(expected - set(listed)):
        errors.append('%s is missing: %s' % (SUMS_NAME, path))
    for path in sorted(set(listed) - expected):
        errors.append('%s lists unexpected file: %s' % (SUMS_NAME, path))


def verify_bundle(archive, require_wheel=False):
    """Statically verify the archive and return a JSON-ready report with ok/errors."""
    archive = Path(archive)
    errors = []
    report = {'archive': str(archive), 'ok': False, 'errors': errors}
    if not archive.is_file():
        errors.append('archive is missing: ' + str(archive))
        return report
    try:
        with tarfile.open(archive, 'r:gz') as tar:
            members = tar.getmembers()
            files = {}
            directories = {}
            seen = set()
            infos = {}
            captured = {}
            for member in members:
                name = member.name.rstrip('/')
                if name in ('', '.'):
                    errors.append('member has no path')
                    continue
                problem = _bad_name(name)
                if problem:
                    errors.append(problem + ': ' + member.name)
                    continue
                if name != ARCHIVE_ROOT and not name.startswith(ARCHIVE_ROOT + '/'):
                    errors.append('member outside %s/: %s' % (ARCHIVE_ROOT, member.name))
                    continue
                if name in seen:
                    errors.append('duplicate member: ' + member.name)
                    continue
                seen.add(name)
                relative = name[len(ARCHIVE_ROOT):].lstrip('/')
                if relative and _excluded(Path(relative)):
                    errors.append('forbidden member: ' + member.name)
                    continue
                if member.isdir():
                    directories[name] = member.mode
                    continue
                if not member.isfile():
                    errors.append('unsupported member type: ' + member.name)
                    continue
                digest = hashlib.sha256()
                size = 0
                stream = tar.extractfile(member)
                for block in iter(lambda: stream.read(1 << 20), b''):
                    digest.update(block)
                    size += len(block)
                files[name] = dict(relative=relative, size=size, sha256=digest.hexdigest(), mode=member.mode)
                infos[name] = member
            for relative in (MANIFEST_NAME, SUMS_NAME, CATALOG):
                name = ARCHIVE_ROOT + '/' + relative
                if name in infos:
                    captured[relative] = tar.extractfile(infos[name]).read()
    except (tarfile.TarError, EOFError, OSError) as exc:
        errors.append('not a readable gzip tar archive: ' + str(exc))
        return report
    if ARCHIVE_ROOT not in directories and not files:
        errors.append('archive has no %s/ root directory' % ARCHIVE_ROOT)
    for name in sorted({ARCHIVE_ROOT + '/' + path for path in REQUIRED_PATHS} - set(files)):
        errors.append('missing required path: ' + name)
    for name, row in sorted(files.items()):
        expected = 0o755 if name.endswith('.sh') else 0o644
        if row['mode'] & 0o777 != expected:
            errors.append('mode %04o for %s; expected %04o' % (row['mode'] & 0o777, name, expected))
    for name, mode in sorted(directories.items()):
        if mode & 0o777 != 0o755:
            errors.append('directory mode %04o for %s; expected 0755' % (mode & 0o777, name))
    manifest = None
    if MANIFEST_NAME not in captured:
        errors.append('missing ' + ARCHIVE_ROOT + '/' + MANIFEST_NAME)
    else:
        try:
            manifest = json.loads(captured[MANIFEST_NAME].decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append('manifest is not valid JSON: ' + str(exc))
    if isinstance(manifest, dict):
        _read_manifest(manifest, files, errors)
        _read_rules(manifest, files, captured, errors)
        _read_wheel(manifest, files, require_wheel, errors)
    _read_sums(captured, files, errors)
    report.update(ok=not errors, files=len(files), directories=len(directories),
                  bytes=sum(row['size'] for row in files.values()), sha256=_hexdigest(archive))
    if isinstance(manifest, dict):
        report.update(schema=manifest.get('schema'), created_at=manifest.get('created_at'),
                      source=manifest.get('source'), rules=(manifest.get('data') or {}).get('rules'),
                      wheel=(manifest.get('build') or {}).get('wheel'))
    return report
