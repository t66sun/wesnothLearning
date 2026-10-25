"""Static checks for the bundle entry scripts: setup.sh and train.sh.

These run on the developer workstation with GNU bash; the Ubuntu-only steps
(apt, rustup, Wesnoth build) are never executed here.
"""
import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which('bash')

REQUIRED_PATHS = (
    'learning/__main__.py',
    'engine_lite/Cargo.toml',
    'engine_lite/pyproject.toml',
    'data/rules/1.18.8-training/rules.json',
    'data/rules/1.18.8-training/catalog-summary.json',
    'data/opponents/gpt6astra.zip',
    'data/humanData_curated/games.jsonl',
    'run.sh',
    'train.sh',
)


def bash(args, cwd):
    return subprocess.run([BASH, *args], cwd=str(cwd), capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=120)


def write_sums(root):
    lines = []
    for path in sorted(p for p in root.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root).as_posix()}")
    (root / 'SHA256SUMS').write_bytes(('\n'.join(lines) + '\n').encode('utf-8'))


@unittest.skipUnless(BASH, 'GNU bash is required for the bundle script checks')
class BundleScriptTests(unittest.TestCase):
    def fixture(self, wheels=()):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / 'WesnothLearning'
        root.mkdir()
        shutil.copy2(ROOT / 'setup.sh', root / 'setup.sh')
        shutil.copy2(ROOT / 'train.sh', root / 'train.sh')
        for relative in REQUIRED_PATHS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f'fixture {relative}\n'.encode('utf-8'))
        if wheels:
            (root / 'dist').mkdir()
            for name in wheels:
                (root / 'dist' / name).write_bytes(b'fixture wheel bytes\n')
        (root / 'BUNDLE_MANIFEST.json').write_bytes(b'{"schema": 1}\n')
        write_sums(root)
        return root

    def test_scripts_parse(self):
        for name in ('setup.sh', 'run.sh', 'train.sh'):
            with self.subTest(script=name):
                result = bash(['-n', str(ROOT / name)], ROOT)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_setup_help_changes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copy2(ROOT / 'setup.sh', root / 'setup.sh')
            result = bash(['setup.sh', '--help'], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            for flag in ('--help', '--preflight', '--device', '--skip-system-deps', '--jobs', '--wesnoth'):
                self.assertIn(flag, result.stdout)
            self.assertFalse((root / '.runtime').exists())
            self.assertFalse((root / '.cache').exists())
            self.assertFalse((root / 'tmp').exists())

    def test_preflight_accepts_matching_bundle(self):
        root = self.fixture()
        result = bash(['setup.sh', '--preflight'], root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('bundle checksums verified', result.stdout)
        self.assertIn('preflight: ok', result.stdout)
        self.assertNotIn('prebuilt extension', result.stdout)
        self.assertFalse((root / '.runtime').exists())

    def test_preflight_reports_wesnoth_learning_lite_wheel(self):
        name = 'wesnoth_learning_lite-0.1.0-cp312-cp312-manylinux_2_17_x86_64.whl'
        root = self.fixture(wheels=(name,))
        result = bash(['setup.sh', '--preflight'], root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'prebuilt extension dist/{name}', result.stdout)
        self.assertFalse((root / '.runtime').exists())

    def test_preflight_reports_legacy_engine_lite_wheel(self):
        name = '_engine_lite-0.1.0-cp312-cp312-manylinux_2_17_x86_64.whl'
        root = self.fixture(wheels=(name,))
        result = bash(['setup.sh', '--preflight'], root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'prebuilt extension dist/{name}', result.stdout)
        self.assertFalse((root / '.runtime').exists())

    def test_preflight_rejects_tampered_file(self):
        root = self.fixture()
        target = root / 'learning/__main__.py'
        target.write_bytes(target.read_bytes() + b'tampered\n')
        result = bash(['setup.sh', '--preflight'], root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SHA256SUMS verification failed', result.stderr)

    def test_preflight_requires_sums_for_extracted_bundle(self):
        root = self.fixture()
        (root / 'SHA256SUMS').unlink()
        result = bash(['setup.sh', '--preflight'], root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SHA256SUMS is missing', result.stderr)

    def test_preflight_rejects_missing_required_path(self):
        root = self.fixture()
        (root / 'train.sh').unlink()
        result = bash(['setup.sh', '--preflight'], root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing required input: train.sh', result.stderr)

    def test_train_help_prints_defaults_and_starts_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copy2(ROOT / 'train.sh', root / 'train.sh')
            result = bash(['train.sh', '--help'], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            for fragment in ('HOURS=18', 'WORKERS=8', 'DEVICE=cpu', 'TRAINER_THREADS=1',
                             'ENGINE=lite', '300 600 400', 'duel ffa4 team2v2'):
                self.assertIn(fragment, result.stdout)
            self.assertFalse((root / 'runs').exists())
            self.assertFalse((root / '.runtime').exists())

    def test_train_refuses_without_setup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copy2(ROOT / 'train.sh', root / 'train.sh')
            result = bash(['train.sh'], root)
            self.assertEqual(result.returncode, 1)
            self.assertIn('run ./setup.sh first', result.stderr)
            self.assertFalse((root / 'runs').exists())

    def test_train_forwards_arguments_and_logs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copy2(ROOT / 'train.sh', root / 'train.sh')
            (root / '.runtime').mkdir()
            wesnoth = root / 'wesnoth'
            wesnoth.write_bytes(b'#!/bin/sh\n')
            wesnoth.chmod(0o755)
            (root / '.runtime/environment.sh').write_bytes(
                f"export WESNOTH_EXE='{wesnoth.as_posix()}'\n".encode('utf-8'))
            fake_python = root / '.venv/bin/python'
            fake_python.parent.mkdir(parents=True)
            fake_python.write_bytes(
                b'#!/usr/bin/env bash\n'
                b'if [[ "${1:-}" == "-c" ]]; then exit 0; fi\n'
                b'printf "%s\\n" "$*" >> "$(dirname "$0")/argv.txt"\n'
                b'printf "fake-python %s\\n" "$*"\n')
            fake_python.chmod(0o755)
            result = bash(['train.sh', '--run-dir', 'runs/unit_test', '--hours', '4',
                           '--workers', '4', '--formats', 'duel', '--', '--resume', 'runs/old'], root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            argv = (fake_python.parent / 'argv.txt').read_text(encoding='utf-8')
            self.assertIn('-u -m learning run --run-dir runs/unit_test', argv)
            self.assertIn('--hours 4', argv)
            self.assertIn('--workers 4', argv)
            self.assertIn('--bc-games 300 600 400', argv)
            self.assertIn('--formats duel', argv)
            self.assertIn('--resume runs/old', argv)
            log = root / 'runs/logs/unit_test.log'
            self.assertTrue(log.is_file())
            self.assertIn('fake-python -u -m learning run --run-dir runs/unit_test',
                          log.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
