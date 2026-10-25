"""V1: final selection uses production schedules with recorded replies only."""
import unittest
from unittest.mock import Mock, patch

import torch

from learning.experiment import FormatExperiment, default_config
from learning.train import checkpoint
from tests.v5 import helpers


class FinalNominationTests(unittest.TestCase):
    def runner(self, directory, fmt='duel'):
        r = FormatExperiment.__new__(FormatExperiment)
        r.directory, r.fmt = directory, fmt
        r.config = default_config(engine='lite')
        r.clock = dict(deadline=100., update_deadline=0.)
        r.state = dict(version=143, phase='evaluate')
        r.teachers, r.fixed, r.support, r.exe = ['astra'], ['astra'], 'support', 'unused'
        r.ensure_export = Mock(side_effect=lambda model, folder, *a, **k: folder)
        model = helpers.model(format_name=fmt)
        optimizer = torch.optim.Adam(model.parameters())
        checkpoint(directory/'best.pt', model, optimizer, runner=dict(version=100, best_key=.1))
        checkpoint(directory/'last_ppo.pt', model, optimizer, runner=dict(version=143, pending_train=None))
        r.identity = lambda: dict(engine='lite', combat_version='expected_damage_v1')
        self.calls = []
        def execute(jobs, name):
            self.assertFalse((directory/'selected.pt').exists())
            self.assertTrue(all(j['deadline'] == 100. for j in jobs))
            self.assertEqual({j['meta']['block'] for j in jobs}, set(range(12)))
            self.calls.append((jobs, name))
            results = []
            for j in jobs:
                result = dict(bots=j['bots'], teams=j.get('teams'), faults={})
                side = j['meta']['policy_sides'][0]
                if fmt == 'team2v2': result['winning_team'] = j['teams'][side-1]
                elif fmt == 'ffa4': result['rank_points'] = {str(s): 3 if s == side else 0 for s in range(1,5)}
                else: result['winner'] = side
                results.append(dict(id=j['id'], status='complete', result=result))
            return jobs, results
        r.execute = execute
        return r

    def test_offcycle_candidate_runs_full_panels_and_freezes_once(self):
        for fmt in ('duel', 'ffa4', 'team2v2'):
            with self.subTest(fmt=fmt), helpers.temporary_directory() as directory:
                r = self.runner(directory, fmt)
                with patch('learning.experiment.time.time', return_value=1.), patch('learning.maps.frozen_map', return_value=('Gg,Gg\nGg,Gg', '0'*64)):
                    frozen, kind, saved = r._select_final()
                    self.assertEqual(kind, 'candidate')
                    self.assertEqual(len(self.calls), 2)
                    self.assertEqual(frozen.read_bytes(), (directory/'last_ppo.pt').read_bytes())
                    self.assertEqual(r._select_final()[2], saved)
                    self.assertEqual(len(self.calls), 2)

    def test_no_time_or_underfilled_panel_keeps_champion(self):
        for no_time in (True, False):
            with self.subTest(no_time=no_time), helpers.temporary_directory() as directory:
                r = self.runner(directory)
                if not no_time: r.execute = lambda jobs, name: (jobs, [])
                with patch('learning.experiment.time.time', return_value=101. if no_time else 1.), patch('learning.maps.frozen_map', return_value=('Gg,Gg\nGg,Gg', '0'*64)):
                    frozen, kind, saved = r._select_final()
                self.assertEqual(kind, 'champion')
                self.assertEqual(frozen.read_bytes(), (directory/'best.pt').read_bytes())
                self.assertIn('time' if no_time else 'incomplete', saved['reason'])
                self.assertEqual(len(self.calls), 0)

    def test_complete_nomination_reuses_only_exact_checkpoint_identity(self):
        with helpers.temporary_directory() as directory:
            r = self.runner(directory)
            with patch('learning.experiment.time.time', return_value=1.), patch('learning.maps.frozen_map', return_value=('Gg,Gg\nGg,Gg', '0'*64)):
                r._select_final()
                (directory/'selection.json').unlink()
                (directory/'selected.pt').unlink()
                r._select_final()
                self.assertEqual(len(self.calls), 2)
                (directory/'selection.json').unlink()
                (directory/'selected.pt').unlink()
                # A different complete checkpoint at the same version cannot reuse its panel.
                state = torch.load(directory/'last_ppo.pt', weights_only=False)
                state['model'][next(iter(state['model']))].add_(.1)
                torch.save(state, directory/'last_ppo.pt')
                r._select_final()
                self.assertEqual(len(self.calls), 4)


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
