import json
import unittest
from pathlib import Path

from learning.experiment import FormatExperiment
from learning.selection import decide, validate_frozen_selection
from tests.v5.helpers import temporary_directory


def panel(difference, blocks=12, status='passed', seed=19, control='astra', missing=0, faults=0):
    return dict(format='duel', engine_id='lite', seed=seed, blocks=blocks, control=control,
                contexts=['astra_partner', 'self_team'],
                comparison=dict(duel=dict(blocks=blocks, distinct_scenarios=blocks, min_distinct=12,
                    status=status, missing=missing, faults=faults, difference=difference)))


class SelectionTests(unittest.TestCase):
    def test_candidate_must_beat_champion_on_matching_panels(self):
        self.assertEqual(decide(panel(0.2), panel(0.1), 'duel')['choice'], 'candidate')
        self.assertEqual(decide(panel(0.1), panel(0.1), 'duel')['choice'], 'champion')
        self.assertEqual(decide(panel(0.05), panel(0.1), 'duel')['choice'], 'champion')

    def test_incomplete_or_mismatched_panels_keep_champion(self):
        for candidate in [panel(0.9, blocks=11), panel(0.9, missing=1), panel(0.9, faults=1),
                          panel(0.9, status='inconclusive'), panel(0.9, seed=20), panel(0.9, control='other')]:
            self.assertEqual(decide(candidate, panel(0.1), 'duel')['choice'], 'champion')
        self.assertEqual(decide(panel(0.9, status='not_passed'), panel(0.1), 'duel')['choice'], 'champion')

    def test_frozen_selection_detects_changed_checkpoint(self):
        with temporary_directory() as directory:
            path = directory / 'selection.json'
            path.write_text(json.dumps(dict(selected_sha256='abc')), encoding='utf-8')
            self.assertEqual(validate_frozen_selection(path, 'abc')['selected_sha256'], 'abc')
            with self.assertRaises(ValueError):
                validate_frozen_selection(path, 'def')

    def test_final_entry_freezes_one_selection_before_holdout(self):
        with temporary_directory() as directory:
            (directory / 'validation').mkdir()
            for name in ('best.pt', 'last_ppo.pt'):
                (directory / name).write_bytes(name.encode())
            (directory / 'validation/v000100.json').write_text(json.dumps(panel(0.1)), encoding='utf-8')
            (directory / 'validation/v000110.json').write_text(json.dumps(panel(0.2)), encoding='utf-8')
            experiment = FormatExperiment.__new__(FormatExperiment)
            experiment.directory = directory
            experiment.fmt = 'duel'
            versions = {'best.pt': 100, 'last_ppo.pt': 110}
            experiment._checkpoint_version = lambda path: versions[Path(path).name]
            experiment._nominate_final = lambda candidate, champion: decide(
                json.loads((directory/'validation/v000110.json').read_text()),
                json.loads((directory/'validation/v000100.json').read_text()), 'duel')
            frozen, kind, saved = experiment._select_final()
            self.assertEqual(kind, 'candidate')
            self.assertEqual(frozen.read_bytes(), b'last_ppo.pt')
            self.assertEqual(saved['selected_sha256'], __import__('learning.common', fromlist=['sha256']).sha256(frozen))
            self.assertTrue(saved['frozen_before_holdout'])
            again = experiment._select_final()
            self.assertEqual(again[2], saved)

    def test_underfilled_candidate_keeps_champion(self):
        with temporary_directory() as directory:
            (directory / 'validation').mkdir()
            (directory / 'best.pt').write_bytes(b'best')
            (directory / 'last_ppo.pt').write_bytes(b'candidate')
            (directory / 'validation/v000100.json').write_text(json.dumps(panel(0.1)), encoding='utf-8')
            (directory / 'validation/v000110.json').write_text(json.dumps(panel(0.9, blocks=11)), encoding='utf-8')
            experiment = FormatExperiment.__new__(FormatExperiment)
            experiment.directory = directory
            experiment.fmt = 'duel'
            versions = {'best.pt': 100, 'last_ppo.pt': 110}
            experiment._checkpoint_version = lambda path: versions[Path(path).name]
            experiment._nominate_final = lambda candidate, champion: decide(
                json.loads((directory/'validation/v000110.json').read_text()),
                json.loads((directory/'validation/v000100.json').read_text()), 'duel')
            frozen, kind, saved = experiment._select_final()
            self.assertEqual(kind, 'champion')
            self.assertEqual(frozen.read_bytes(), b'best')
            self.assertIn('incomplete', saved['reason'])


if __name__ == '__main__':
    unittest.main()
