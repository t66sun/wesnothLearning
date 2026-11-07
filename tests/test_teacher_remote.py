import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from learning import teacher_remote


class TeacherRemoteTests(unittest.TestCase):
    def capture_script(self, root, destination):
        with patch.object(teacher_remote, 'ROOT', root), \
                patch.object(teacher_remote.subprocess, 'check_output', return_value='a' * 40), \
                patch.object(teacher_remote.subprocess, 'run') as run:
            teacher_remote.ship('true', destination=str(destination))
            return run.call_args.kwargs

    def test_ssh_receives_lf_bytes_without_windows_text_translation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sent = self.capture_script(root, root / 'fresh')
        self.assertIsInstance(sent['input'], bytes)
        self.assertNotIn(b'\r\n', sent['input'])
        self.assertNotIn('text', sent)
        self.assertTrue(sent['input'].startswith(b'set -eu\n'))

    def test_existing_directory_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / 'existing'
            target.mkdir()
            sentinel = target / 'keep'
            sentinel.write_text('untouched')
            sent = self.capture_script(root, target)
            result = subprocess.run(['bash', '-s'], input=sent['input'], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'File exists', result.stderr)
            self.assertEqual(sentinel.read_text(), 'untouched')
            self.assertFalse((target / 'SOURCE_COMMIT').exists())


if __name__ == '__main__':
    unittest.main()
