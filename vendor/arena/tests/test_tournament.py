from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import addons
from tournament import discover, ffa_groups


class TournamentTests(unittest.TestCase):
    def test_discovery_and_duplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            a=addons.create('TeamA',root);addons.create('TeamB',root)
            self.assertEqual(sorted(discover(root)),['TeamA','TeamB'])
            addons.pack(a,root/'TeamA.zip')
            with self.assertRaises(ValueError): discover(root)
    def test_groups(self):
        names=[f'Team{i}' for i in range(8)]
        self.assertEqual(len(ffa_groups(names,4)),70)
        self.assertEqual(ffa_groups(names,8),[tuple(names)])
        many=[f'Team{i}' for i in range(20)]
        groups=ffa_groups(many,4)
        self.assertEqual(len(groups),70)
        self.assertEqual(groups,ffa_groups(many,4))
        self.assertEqual(set(n for g in groups for n in g),set(many))


if __name__=='__main__': unittest.main()
