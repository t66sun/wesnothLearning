import tempfile
import unittest
import zipfile
from pathlib import Path
from learning.package import package_project


class PackageTests(unittest.TestCase):
    def test_engineering_package_is_portable_and_contains_no_run_state(self):
        with tempfile.TemporaryDirectory() as temp:
            path=package_project(Path(temp)/'engineering.zip')
            with zipfile.ZipFile(path) as archive:
                self.assertIsNone(archive.testzip())
                names=archive.namelist()
                self.assertIn('WesnothLearning/setup.sh',names)
                self.assertIn('WesnothLearning/run.sh',names)
                self.assertIn('WesnothLearning/learning/model.py',names)
                self.assertIn('WesnothLearning/vendor/arena/runtime/runtime.lua',names)
                self.assertEqual(sum(n.startswith('WesnothLearning/opponents/') and n.endswith('.zip') for n in names),1)
                for name in names:
                    self.assertFalse(set(name.split('/')) & {'.venv','.cache','.ssh','runs','tmp','verification','delivery','__pycache__','references','humanData','datasets'})
                self.assertIn('WesnothLearning/humanData_curated/games.jsonl',names)
                for name in ('setup.sh','run.sh'):
                    info=archive.getinfo('WesnothLearning/'+name)
                    self.assertEqual(info.create_system,3)
                    self.assertEqual((info.external_attr>>16)&0o777,0o755)


if __name__=='__main__': unittest.main()
