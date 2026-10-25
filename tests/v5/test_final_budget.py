"""Freeze a holdout reserve inside the original final-evaluation budget."""
import unittest
from unittest.mock import Mock, patch

from learning.__main__ import parser, run_config
from learning.experiment import default_config, validate_config
from tests.v5 import helpers, test_final_nomination as fixtures


class FinalBudgetTests(unittest.TestCase):
    def test_new_run_config_freezes_reserve_and_rejects_invalid_budgets(self):
        args=parser().parse_args(['run','--device','cpu','--hours','30','--final-holdout-hours','4'])
        config=run_config(args)
        validate_config(config)
        self.assertEqual(config['final_holdout_hours'],4.)
        self.assertEqual(config['hours'],30.)
        for hours in (-1.,5.,float('nan'),float('inf')):
            with self.subTest(hours=hours), self.assertRaisesRegex(ValueError,'holdout reserve'):
                validate_config(dict(config,final_holdout_hours=hours))
        legacy=default_config('cpu')
        legacy.pop('final_holdout_hours',None)
        validate_config(legacy)

    def test_nomination_stops_at_reserve_boundary_but_holdout_keeps_total_deadline(self):
        with helpers.temporary_directory() as directory:
            runner=fixtures.FinalNominationTests().runner(directory)
            runner.config.update(hours=30.,final_holdout_hours=4.)
            runner.clock.update(started=0.,update_deadline=25*3600.,deadline=30*3600.)
            runner.state.update(effective=False,error=None,history=[])
            runner.save=Mock()
            runner.teacher_evidence=lambda: []
            seen=[]
            def execute(jobs,name):
                deadline=30*3600. if name=='final' else 26*3600.
                self.assertTrue(all(j['deadline']==deadline for j in jobs))
                if name=='final': self.assertTrue((directory/'selected.pt').exists())
                seen.append(name)
                return jobs,[dict(id=j['id'],status='complete',result=dict(bots=j['bots'],winner=j['meta']['policy_sides'][0],faults={})) for j in jobs]
            runner.execute=execute
            with patch('learning.experiment.time.time',return_value=26*3600.+1), patch('learning.maps.frozen_map',return_value=('Gg,Gg\nGg,Gg','0'*64)), patch('learning.report.write_profile_report'):
                summary=runner.final_evaluation()
            self.assertEqual(summary['selected_kind'],'champion')
            self.assertIn('time',summary['selection']['reason'])
            self.assertEqual(seen,['final'])
            self.assertEqual(runner.clock['deadline'],30*3600.)


if __name__ == '__main__':
    import torch
    torch.set_num_threads(1)
    unittest.main()
