import contextlib
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from learning.bundle import (ARCHIVE_ROOT, CATALOG, HUMAN_CURATED, MANIFEST_NAME, REQUIRED_PATHS, RULES_DIR,
                             SUMS_NAME, build_bundle, verify_bundle)
from learning.__main__ import main

STAMP = '2026-10-25T00:00:00Z'


def _write(root, files):
    for name, data in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))


def _fixture(root):
    """Minimal tree with every required path plus excluded local state."""
    rules = {'source_version': '1.18.8', 'source_hash': 'a' * 64}
    rules_bytes = (json.dumps(rules, indent=2) + '\n').encode('utf-8')
    summary = {'summary_version': 1, 'source_version': '1.18.8', 'source_hash': rules['source_hash'],
               'rules_file_sha256': hashlib.sha256(rules_bytes).hexdigest(), 'unit_count': 3, 'terrain_count': 2}
    files = {name: '# fixture\n' for name in REQUIRED_PATHS}
    files.update({
        'README.md': '# WesnothLearning\n', 'LICENSE': 'MIT\n', 'requirements.txt': 'torch==2.9.1\n',
        'setup.sh': '#!/bin/sh\nset -eu\n', 'run.sh': '#!/bin/sh\nset -eu\n', 'train.sh': '#!/bin/sh\nset -eu\n',
        '.gitattributes': '* text=auto eol=lf\n',
        'learning/__main__.py': 'def main(): pass\n', 'learning/bundle.py': '# bundle\n',
        'tests/test_bundle.py': '# fixture\n', 'benchmarks/README.md': 'bench\n',
        RULES_DIR + '/rules.json': rules_bytes,
        CATALOG: (json.dumps(summary, indent=2) + '\n').encode('utf-8'),
        RULES_DIR + '/coverage.json': b'{}\n', RULES_DIR + '/catalog.json': b'{"catalog": 1}\n',
        'data/opponents/gpt6astra.zip': b'PK\x03\x04fixture',
        HUMAN_CURATED: '{"format": "duel"}\n',
        'data/datasets/human/import.json': '{"games": 0}\n',
    })
    files.update({
        'runs/first/latest.pt': b'weights', 'verification/report.json': '{}', 'delivery/x.tar.gz': b'x',
        'tmp/scratch.txt': 'x', '.venv/pyvenv.cfg': 'x', '__pycache__/mod.cpython-312.pyc': b'x',
        'learning/__pycache__/bundle.cpython-312.pyc': b'x', 'AGENTS.md': '# agents\n',
        'data/references/upstream.txt': 'x', 'data/humanData/raw.log': 'x',
        'data/rules/1.18.8/old-rules.json': '{}', 'engine_lite/target/debug/out': b'x',
        'learning/native.dll': b'MZ', 'learning/native.pyd': b'MZ', '.cache/matplotlib/x': 'x',
    })
    _write(root, files)


def _members(archive):
    with tarfile.open(archive, 'r:gz') as tar:
        return {member.name.rstrip('/'): (member, tar.extractfile(member).read() if member.isfile() else None)
                for member in tar.getmembers()}


def _retar(source, target, replace=None, drop=(), add=()):
    """Rewrite an archive so the verifier sees tampered, missing or extra members."""
    replace = replace or {}
    with tarfile.open(source, 'r:gz') as src, tarfile.open(target, 'w:gz') as dst:
        for member in src:
            if member.name.rstrip('/') in drop:
                continue
            data = replace.get(member.name)
            if data is None and member.isfile():
                data = src.extractfile(member).read()
            if data is not None and member.isfile():
                member.size = len(data)
                dst.addfile(member, io.BytesIO(data))
            else:
                dst.addfile(member)
        for name, data in add:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            dst.addfile(info, io.BytesIO(data))


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'source'
        _fixture(self.root)

    def build(self, name='bundle.tar.gz', **options):
        return build_bundle(self.base / name, root=self.root, created_at=STAMP, **options)

    def test_build_produces_installable_archive(self):
        result = self.build()
        self.assertEqual(result['created_at'], STAMP)
        self.assertIsNone(result['wheel'])
        self.assertIsNone(result['source']['commit'])
        self.assertIsNone(result['source']['dirty'])
        members = _members(self.base / 'bundle.tar.gz')
        self.assertIsNone(members[ARCHIVE_ROOT][1])
        for name in REQUIRED_PATHS:
            self.assertIn(ARCHIVE_ROOT + '/' + name, members)
        manifest = json.loads(members[ARCHIVE_ROOT + '/' + MANIFEST_NAME][1])
        self.assertEqual(manifest['schema'], 1)
        self.assertEqual(manifest['target'],
                         {'os': 'ubuntu', 'version': '24.04', 'arch': 'x86_64', 'python': '3.12', 'device': 'cpu'})
        self.assertEqual(manifest['verification'], {'static': True, 'ubuntu_runtime': 'pending'})
        self.assertEqual(manifest['build'], {'wheel': None, 'torch': '2.9.1'})
        self.assertIsNone(manifest['source']['commit'])
        rules = manifest['data']['rules']
        self.assertEqual(rules['directory'], RULES_DIR)
        self.assertEqual(rules['unit_count'], 3)
        self.assertEqual(rules['terrain_count'], 2)
        archived_rules = members[ARCHIVE_ROOT + '/' + RULES_DIR + '/rules.json'][1]
        self.assertEqual(rules['rules_file_sha256'], hashlib.sha256(archived_rules).hexdigest())
        self.assertEqual([row['path'] for row in manifest['data']['opponents']], ['data/opponents/gpt6astra.zip'])
        self.assertEqual(manifest['data']['human_curated']['path'], HUMAN_CURATED)
        self.assertEqual(manifest['totals']['files'], len(manifest['files']))
        self.assertEqual(manifest['totals']['bytes'], sum(row['size'] for row in manifest['files']))
        payload = {name for name, (_, data) in members.items()
                   if data is not None and name not in (ARCHIVE_ROOT + '/' + MANIFEST_NAME, ARCHIVE_ROOT + '/' + SUMS_NAME)}
        self.assertEqual({ARCHIVE_ROOT + '/' + row['path'] for row in manifest['files']}, payload)
        for row in manifest['files']:
            member, data = members[ARCHIVE_ROOT + '/' + row['path']]
            self.assertEqual(row['size'], len(data))
            self.assertEqual(row['sha256'], hashlib.sha256(data).hexdigest())
            self.assertEqual(row['mode'], '%04o' % (member.mode & 0o777))
        sums = members[ARCHIVE_ROOT + '/' + SUMS_NAME][1].decode('utf-8').splitlines()
        self.assertEqual({line.split('  ', 1)[1] for line in sums},
                         {row['path'] for row in manifest['files']} | {MANIFEST_NAME})
        for line in sums:
            digest, path = line.split('  ', 1)
            self.assertEqual(hashlib.sha256(members[ARCHIVE_ROOT + '/' + path][1]).hexdigest(), digest)
        raw = (self.base / 'bundle.tar.gz').read_bytes()
        self.assertEqual(raw[:4], b'\x1f\x8b\x08\x00')
        self.assertEqual(raw[4:8], b'\x00\x00\x00\x00')
        report = verify_bundle(self.base / 'bundle.tar.gz')
        self.assertTrue(report['ok'], report['errors'])
        self.assertEqual(report['files'], len(payload) + 2)
        self.assertEqual(report['rules'], rules)
        self.assertEqual(report['source'], {'commit': None, 'dirty': None})

    def test_local_state_and_reference_data_are_excluded(self):
        self.build()
        members = _members(self.base / 'bundle.tar.gz')
        for name in members:
            for token in ('__pycache__', '/runs/', '/verification/', '/delivery/', '/tmp/', '/.venv/', '/.cache/',
                          'data/references', 'data/humanData/', 'data/rules/1.18.8/', 'AGENTS.md', '/target/'):
                self.assertNotIn(token, name)
            self.assertFalse(name.endswith(('.pyc', '.pyo', '.pyd', '.dll', '.exe')), name)
        self.assertIn(ARCHIVE_ROOT + '/' + HUMAN_CURATED, members)
        self.assertIn(ARCHIVE_ROOT + '/' + RULES_DIR + '/rules.json', members)

    def test_same_created_at_reproduces_bytes(self):
        first = self.build('first.tar.gz')
        second = self.build('second.tar.gz')
        self.assertEqual(first['sha256'], second['sha256'])
        self.assertEqual((self.base / 'first.tar.gz').read_bytes(), (self.base / 'second.tar.gz').read_bytes())

    def test_modes_are_fixed_for_extraction(self):
        self.build()
        members = _members(self.base / 'bundle.tar.gz')
        for name in ('setup.sh', 'run.sh', 'train.sh'):
            self.assertEqual(members[ARCHIVE_ROOT + '/' + name][0].mode & 0o777, 0o755, name)
        self.assertEqual(members[ARCHIVE_ROOT + '/README.md'][0].mode & 0o777, 0o644)
        for name, (member, data) in members.items():
            expected = 0o755 if data is None or name.endswith('.sh') else 0o644
            self.assertEqual(member.mode & 0o777, expected, name)
            self.assertEqual(member.uid, 0)
            self.assertEqual(member.gid, 0)
            self.assertEqual(member.mtime, 0)

    def test_wheel_is_copied_only_when_manylinux_x86_64(self):
        good = self.base / 'torch-2.9.1-cp312-cp312-manylinux_2_28_x86_64.whl'
        good.write_bytes(b'whl')
        result = self.build(wheel=good)
        self.assertEqual(result['wheel'], 'dist/' + good.name)
        members = _members(self.base / 'bundle.tar.gz')
        self.assertEqual(members[ARCHIVE_ROOT + '/dist/' + good.name][1], b'whl')
        manifest = json.loads(members[ARCHIVE_ROOT + '/' + MANIFEST_NAME][1])
        self.assertEqual(manifest['build']['wheel'], 'dist/' + good.name)
        self.assertTrue(verify_bundle(self.base / 'bundle.tar.gz', require_wheel=True)['ok'])
        for bad in ('numpy-1.0-cp312-win_amd64.whl', 'torch-2.9.1-cp312-cp312-manylinux_2_28_aarch64.whl', 'notes.txt'):
            path = self.base / bad
            path.write_bytes(b'x')
            with self.assertRaises(ValueError):
                build_bundle(self.base / ('bad-' + bad), root=self.root, wheel=path, created_at=STAMP)

    def test_require_wheel_rejects_archive_without_wheel(self):
        self.build()
        report = verify_bundle(self.base / 'bundle.tar.gz', require_wheel=True)
        self.assertFalse(report['ok'])
        self.assertIn('--require-wheel', ' '.join(report['errors']))

    def test_verifier_rejects_tampered_file(self):
        self.build()
        tampered = self.base / 'tampered.tar.gz'
        _retar(self.base / 'bundle.tar.gz', tampered,
               replace={ARCHIVE_ROOT + '/learning/bundle.py': b'# tampered bundle\n'})
        report = verify_bundle(tampered)
        self.assertFalse(report['ok'])
        self.assertTrue(any('learning/bundle.py' in error and 'mismatch' in error for error in report['errors']),
                        report['errors'])
        self.assertTrue(any(error.startswith(SUMS_NAME) and 'learning/bundle.py' in error for error in report['errors']))

    def test_verifier_rejects_forbidden_path(self):
        self.build()
        archive = self.base / 'forbidden.tar.gz'
        _retar(self.base / 'bundle.tar.gz', archive, add=[(ARCHIVE_ROOT + '/runs/latest.pt', b'x')])
        report = verify_bundle(archive)
        self.assertFalse(report['ok'])
        self.assertTrue(any('forbidden member' in error and 'runs/latest.pt' in error for error in report['errors']),
                        report['errors'])

    def test_verifier_rejects_missing_required_path(self):
        self.build()
        archive = self.base / 'missing.tar.gz'
        _retar(self.base / 'bundle.tar.gz', archive, drop={ARCHIVE_ROOT + '/train.sh'})
        report = verify_bundle(archive)
        self.assertFalse(report['ok'])
        self.assertTrue(any('missing required path' in error and 'train.sh' in error for error in report['errors']),
                        report['errors'])

    def test_verifier_rejects_unsafe_or_duplicate_members(self):
        self.build()
        archive = self.base / 'unsafe.tar.gz'
        _retar(self.base / 'bundle.tar.gz', archive,
               add=[(ARCHIVE_ROOT + '/../escape.txt', b'x'), (ARCHIVE_ROOT + '/a\\b.txt', b'x'),
                    ('/absolute.txt', b'x'), (ARCHIVE_ROOT + '/README.md', b'duplicate\n')])
        report = verify_bundle(archive)
        self.assertFalse(report['ok'])
        joined = '\n'.join(report['errors'])
        self.assertIn('parent reference', joined)
        self.assertIn('backslash', joined)
        self.assertIn('absolute member name', joined)
        self.assertIn('duplicate member', joined)

    def test_verifier_reports_absent_archive(self):
        report = verify_bundle(self.base / 'absent.tar.gz')
        self.assertFalse(report['ok'])
        self.assertTrue(any('archive is missing' in error for error in report['errors']))

    def test_cli_help_exposes_both_commands(self):
        for argv, expected in ((['bundle', '--help'], '--created-at'),
                               (['verify-bundle', '--help'], '--require-wheel')):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
                main(argv)
            self.assertEqual(raised.exception.code, 0)
            self.assertIn(expected, output.getvalue())


if __name__ == '__main__':
    unittest.main()
