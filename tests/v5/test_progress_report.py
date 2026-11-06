"""BC, selected and latest complete policies are distinct evaluation objects."""
import shutil
import unittest
from unittest.mock import Mock, patch

import torch

from learning.train import checkpoint
from tests.v5 import helpers, test_final_nomination


class ProgressIdentityTests(unittest.TestCase):
    def test_final_report_distinguishes_bc_selected_latest_and_pending_update(self):
        with helpers.temporary_directory() as directory:
            runner = test_final_nomination.FinalNominationTests().runner(directory)
            model = helpers.model(format_name='duel')
            optimizer = torch.optim.Adam(model.parameters())
            checkpoint(directory/'last_bc.pt', model, optimizer, runner=dict(version=38, pending_train=None))
            checkpoint(directory/'latest.pt', model, optimizer,
                       runner=dict(version=144, pending_train=dict(method='ppo')))
            shutil.copyfile(directory/'best.pt', directory/'selected.pt')
            runner._select_final = lambda: (directory/'selected.pt', 'champion', dict(selected_version=100))
            runner.state.update(effective=False, error=None, history=[])
            runner.save = Mock()
            runner.teacher_evidence = lambda: []
            runner.execute = lambda jobs, name: (jobs, [])
            with patch('learning.experiment.time.time', return_value=1.):
                summary = runner.final_evaluation()
            self.assertIn('checkpoint_roles', summary)
            roles = summary['checkpoint_roles']
            self.assertEqual(roles['bc']['version'], 38)
            self.assertEqual(roles['selected']['version'], 100)
            self.assertEqual(roles['latest']['version'], 143)
            self.assertTrue(roles['latest']['path'].endswith('last_ppo.pt'))
            self.assertEqual(roles['pending']['version'], 144)
            self.assertFalse(roles['pending']['complete'])
            self.assertEqual(len({roles[k]['checkpoint_sha256'] for k in ('bc', 'selected', 'latest')}), 3)
            text = (directory/'report'/'REPORT.md').read_text(encoding='utf-8')
            for expected in ('bc | 38', 'selected | 100', 'latest | 143', 'pending | 144'):
                self.assertIn(expected, text)
