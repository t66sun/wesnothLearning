"""Exercise the supplied archives, without launching a game or changing their bytes."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from learning.common import ROOT,sha256
from learning.manifest import freeze,verify_frozen
import addons


class OpponentTests(unittest.TestCase):
    def test_active_astra_archive_validates_without_changes(self):
        paths=sorted((ROOT/'opponents').glob('*.zip'))
        self.assertEqual([p.stem for p in paths],['gpt6astra'])
        for path in paths:
            with self.subTest(archive=path.name):
                before=sha256(path)
                with addons.open_addon(path) as addon:
                    self.assertEqual(addons.validate(addon),path.stem)
                self.assertEqual(sha256(path),before)

    def test_actual_four_archives_freeze_and_verify(self):
        with tempfile.TemporaryDirectory() as temporary:
            run=Path(temporary)
            runtime=run/'not-an-executable';runtime.write_bytes(b'unit-test runtime reference')
            with patch('learning.manifest.native.find_wesnoth',return_value=str(runtime)),patch('learning.manifest.dependency_versions',return_value=dict(packages=dict(torch='2.9.1+cpu'))):
                manifest,teachers=freeze(run,ROOT/'opponents',None,dict(device='cuda'))
            self.assertEqual(len(teachers),1)
            for opponent in manifest['opponents']:
                self.assertEqual(sha256(opponent['source']),opponent['sha256'])
                self.assertEqual(sha256(opponent['path']),opponent['sha256'])
            verify_frozen(manifest)

    def test_dots_do_not_allow_reserved_or_unsafe_names(self):
        for name in ('team.v1','deepseek4.1fwithDSH','NeuralArena'):
            self.assertEqual(addons.valid_name(name),name)
        for name in ('con.v1','COM1.bot','lpt9.v1','team.','team..v1','.team','../team','team/bot','baseline','arena_runtime'):
            with self.subTest(name=name),self.assertRaises(ValueError):
                addons.valid_name(name)


if __name__=='__main__': unittest.main()
