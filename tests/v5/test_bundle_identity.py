"""A packaged stock-RCA run names its teacher and ships nothing that teacher cannot read."""
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from learning import bundle
from learning.bundle import ARCHIVE_ROOT, CATALOG, HUMAN_CURATED, MANIFEST_NAME, REQUIRED_PATHS, RULES_DIR, SUMS_NAME
from learning.stock_rca import capture_sha256_from

STAMP = '2026-10-28T00:00:00Z'
TEACHER_PATH = 'data/opponents/gpt6astra.zip'


def _write(root, files):
    for name, data in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))


def _fixture(root):
    rules = {'source_version': '1.18.8', 'source_hash': 'b' * 64,
             'units': {'spearman': {'level': 1}}, 'terrains': {'grassland': {'movement_cost': 1}}}
    rules_bytes = (json.dumps(rules, indent=2) + '\n').encode('utf-8')
    summary = {'summary_version': 1, 'source_version': '1.18.8', 'source_hash': rules['source_hash'],
               'rules_file_sha256': hashlib.sha256(rules_bytes).hexdigest(), 'unit_count': 1, 'terrain_count': 1}
    files = {name: '# fixture\n' for name in REQUIRED_PATHS}
    files.update({
        'README.md': '# WesnothLearning\n', 'LICENSE': 'MIT\n', 'requirements.txt': 'torch==2.9.1\n',
        'setup.sh': '#!/bin/sh\nset -eu\n', 'run.sh': '#!/bin/sh\nset -eu\n', 'train.sh': '#!/bin/sh\nset -eu\n',
        '.gitattributes': '* text=auto eol=lf\n',
        'learning/__main__.py': 'def main(): pass\n', 'learning/bundle.py': '# bundle\n',
        'benchmarks/README.md': 'bench\n', 'tests/test_bundle_identity.py': '# fixture\n',
        RULES_DIR + '/rules.json': rules_bytes,
        CATALOG: (json.dumps(summary, indent=2) + '\n').encode('utf-8'),
        RULES_DIR + '/coverage.json': b'{}\n', RULES_DIR + '/catalog.json': b'{"catalog": 1}\n',
        'data/opponents/gpt6astra.zip': b'PK\x03\x04unused',
        HUMAN_CURATED: '{"format": "duel"}\n',
        'data/datasets/human/import.json': '{"games": 0}\n',
    })
    _write(root, files)


def _members(archive):
    with tarfile.open(archive, 'r:gz') as tar:
        return {member.name: (member, tar.extractfile(member).read() if member.isfile() else None)
                for member in tar.getmembers()}


def _retar(source, target, add=()):
    with tarfile.open(source, 'r:gz') as src, tarfile.open(target, 'w:gz') as dst:
        for member in src:
            data = src.extractfile(member).read() if member.isfile() else None
            dst.addfile(member, io.BytesIO(data) if data is not None else None)
        for name, data in add:
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o644
            dst.addfile(info, io.BytesIO(data))


class BundleIdentityTests(unittest.TestCase):
    def setUp(self):
        context = tempfile.TemporaryDirectory()
        self.directory = Path(context.name)
        self.addCleanup(context.cleanup)

    def build(self):
        _fixture(self.directory / 'tree')
        output = self.directory / 'bundle.tar.gz'
        result = bundle.build_bundle(output, root=self.directory / 'tree', created_at=STAMP)
        return output, result

    def test_bundle_omits_unused_teacher(self):
        output, result = self.build()
        members = _members(output)
        shipped = sorted(name for name in members if name.startswith(ARCHIVE_ROOT + '/data/opponents/'))
        self.assertEqual(shipped, [])
        self.assertNotIn(ARCHIVE_ROOT + '/' + TEACHER_PATH, members)
        manifest = json.loads(members[ARCHIVE_ROOT + '/' + MANIFEST_NAME][1])
        teacher = manifest['identities']['teacher']
        self.assertEqual(teacher['kind'], 'wesnoth_default_rca')
        self.assertEqual(teacher['query'], 'none')
        self.assertEqual(teacher['packages'], [])
        self.assertEqual(manifest['data']['opponents'], [])
        self.assertEqual(result['teacher']['kind'], 'wesnoth_default_rca')
        report = bundle.verify_bundle(output)
        self.assertEqual(report['errors'], [])
        self.assertTrue(report['ok'])
        self.assertEqual(report['teacher']['kind'], 'wesnoth_default_rca')

    def test_identity_matches_the_shipped_capture_sources(self):
        output, _ = self.build()
        members = _members(output)
        manifest = json.loads(members[ARCHIVE_ROOT + '/' + MANIFEST_NAME][1])
        digests = {name[len(ARCHIVE_ROOT) + 1:]: hashlib.sha256(data).hexdigest()
                   for name, (_, data) in members.items() if data is not None}
        expected = capture_sha256_from({path: digest for path, digest in digests.items()
                                        if path.startswith('lua/stock_rca_capture/')})
        self.assertEqual(manifest['identities']['teacher']['capture_sha256'], expected)

    def test_an_undeclared_member_fails_verification(self):
        output, _ = self.build()
        tampered = self.directory / 'tampered.tar.gz'
        _retar(output, tampered, add=[(ARCHIVE_ROOT + '/' + TEACHER_PATH, b'PK\x03\x04unused')])
        report = bundle.verify_bundle(tampered)
        self.assertFalse(report['ok'])
        self.assertIn('manifest is missing file: ' + TEACHER_PATH, report['errors'])

    def test_a_teacher_package_must_be_declared(self):
        """An opponent the stock teacher cannot read never verifies as part of the archive."""
        output, _ = self.build()
        members = _members(output)
        manifest = json.loads(members[ARCHIVE_ROOT + '/' + MANIFEST_NAME][1])
        manifest['data']['opponents'] = [dict(path=TEACHER_PATH, sha256='0' * 64)]
        errors = []
        bundle._read_identity(manifest, {ARCHIVE_ROOT + '/' + TEACHER_PATH: dict(relative=TEACHER_PATH,
                                                                                 sha256='0' * 64)}, errors)
        bundle._read_rules(manifest, {ARCHIVE_ROOT + '/' + TEACHER_PATH: dict(relative=TEACHER_PATH,
                                                                              sha256='0' * 64)},
                           {}, errors)
        self.assertIn('manifest ships an opponent the teacher does not need: ' + TEACHER_PATH, errors)

    def test_historical_manifest_without_identities_keeps_its_opponents(self):
        """Bundles built before R10 keep the manifest they were shipped with."""
        errors, opponent = [], 'data/opponents/gpt6astra.zip'
        files = {ARCHIVE_ROOT + '/' + RULES_DIR + '/rules.json': dict(relative=RULES_DIR + '/rules.json',
                                                                      sha256='1' * 64)}
        manifest = {'data': dict(rules=dict(), opponents=[dict(path=opponent, sha256='1' * 64)])}
        bundle._read_identity(manifest, files, errors)
        self.assertEqual(errors, [])

    def test_sums_cover_every_shipped_file(self):
        output, result = self.build()
        members = _members(output)
        sums = dict(reversed(line.split('  ', 1)) for line
                    in members[ARCHIVE_ROOT + '/' + SUMS_NAME][1].decode().splitlines())
        for name, (_, data) in members.items():
            relative = name[len(ARCHIVE_ROOT) + 1:]
            if data is None or relative == SUMS_NAME:
                continue
            self.assertEqual(sums[relative], hashlib.sha256(data).hexdigest())
        self.assertEqual(set(sums), {name[len(ARCHIVE_ROOT) + 1:] for name, (_, data) in members.items()
                                     if data is not None and not name.endswith(SUMS_NAME)})


if __name__ == '__main__':
    unittest.main()
