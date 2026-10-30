import sys
import tempfile
import unittest
import zipfile
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

    def test_contestant_slot_accepts_an_oversized_directory_and_rejects_an_oversized_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            bot = addons.create('TeamA', Path(temp))
            (bot / 'lua' / 'weights.lua').write_bytes(b' ' * (addons.MAX_PACKAGE_BYTES + 1))
            with addons.contestant(bot) as (addon, name):
                self.assertEqual(name, 'TeamA')
                self.assertEqual(addon, bot.resolve())
            archive = Path(temp) / 'TeamA.zip'
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as package:
                package.writestr('TeamA/lua/bot.lua', 'return {}')
                package.writestr('TeamA/lua/weights.lua', b' ' * (addons.MAX_PACKAGE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, 'size limit'):
                with addons.contestant(archive):
                    self.fail('submission zip above the cap must not become a contestant')


if __name__ == '__main__':
    unittest.main()
