import sys
import tempfile
import unittest
from pathlib import Path

from learning.common import VENDOR

sys.path.insert(0, str(VENDOR))
import addons


class RuntimeAddonLimitTests(unittest.TestCase):
    def test_runtime_directory_is_not_bound_by_the_submission_cap(self):
        with tempfile.TemporaryDirectory() as temp:
            bot = addons.create('TeamA', Path(temp))
            (bot / 'lua' / 'weights.lua').write_bytes(b' ' * (addons.MAX_PACKAGE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, '16 MiB'):
                addons.validate(bot)
            with addons.open_addon(bot) as unpacked:
                self.assertEqual(unpacked, bot.resolve())


if __name__ == '__main__':
    unittest.main()
