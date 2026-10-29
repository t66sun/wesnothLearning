"""Panel and BC verdicts expose scenario independence, including insufficiency."""
import unittest


def panel(families, differences=None):
    jobs, results = [], []
    for block, family in enumerate(families):
        difference = differences[block] if differences is not None else 3.
        for rotation in range(2):
            side = rotation + 1
            ident = f'b{block}-r{rotation}'
            jobs.append(dict(id=ident, scenario_family=family,
                meta=dict(format='duel', block=block, control='control', context='solo',
                          policy_sides=[side], control_sides=[3-side])))
            results.append(dict(id=ident, status='complete',
                result=dict(bots=['a', 'b'], winner=side if difference > 0 else 3-side, faults={})))
    return jobs, results


class EvaluationDesignTests(unittest.TestCase):
    def test_frozen_floors_and_existing_schedule_capacity(self):
        from learning.experiment import default_config, validate_config
        from learning.schedule import evaluation_jobs

        config = default_config('cpu')
        self.assertEqual(config['min_distinct'], dict(trend=3,promotion=12,final=12,gate=12))
        for key, floor in config['min_distinct'].items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_config(dict(config,min_distinct=dict(config['min_distinct'],**{key:floor-1})))
        for fmt, scenarios, games in [('duel',30,60),('ffa4',15,120),('team2v2',15,240)]:
            jobs=evaluation_jobs('.', 'policy','baseline',['baseline'],30,19,1000,'unused',
                                 label='final-test',formats=[fmt])
            self.assertEqual(len(jobs),games)
            self.assertEqual(len({job['scenario_family'] for job in jobs}),scenarios)
            self.assertTrue(all(job['meta']['map_partition']=='final' for job in jobs))
            self.assertEqual({job['meta']['min_distinct'] for job in jobs},{12})
            self.assertGreaterEqual(scenarios,12)

    def test_promotion_panel_reaches_the_distinct_floor(self):
        from learning.schedule import evaluation_jobs

        for fmt in ('duel','ffa4','team2v2'):
            jobs=evaluation_jobs('.', 'policy','baseline',['baseline'],12,19,1000,'unused',
                                 label='val000100',formats=[fmt],min_distinct=12)
            self.assertEqual(len({job['scenario_family'] for job in jobs}),12,fmt)
            from learning.formats import PLAYERS
            self.assertEqual(len(jobs),12*PLAYERS[fmt]*(2 if fmt=='team2v2' else 1))

    def test_each_panel_block_starts_from_its_own_factions(self):
        from learning.schedule import evaluation_jobs

        jobs=evaluation_jobs('.', 'policy','baseline',['baseline'],12,19,1000,'unused',
                             label='final-test',formats=['team2v2'])
        designs={(tuple(job['factions']),job['meta']['map']) for job in jobs}
        self.assertEqual(len(designs),12)
        self.assertTrue(all(len(set(factions))==4 for factions,_ in designs))

    def test_teacher_games_reach_the_bc_scenario_floor(self):
        from learning.schedule import stock_teacher_jobs

        record=dict(kind='wesnoth_default_rca',version='1.18.8',query='none',
                    runtime_sha256='a'*64)
        for fmt in ('duel','ffa4','team2v2'):
            jobs=stock_teacher_jobs('.',record,'support',0,19,1000,'unused',
                                    formats=[fmt],count=12,index_stride=12)
            self.assertEqual(len({job['scenario_family'] for job in jobs}),12,fmt)
            self.assertEqual(len({tuple(job['factions']) for job in jobs}),12,fmt)

    def test_unmeasured_legacy_panel_cannot_nominate(self):
        from learning.selection import _panel_complete
        from tests.v5.test_selection import panel as selection_panel

        candidate = selection_panel(.9)
        candidate['comparison']['duel'].pop('distinct_scenarios')
        self.assertFalse(_panel_complete(candidate,'duel'))
        self.assertTrue(_panel_complete(selection_panel(.1),'duel'))

    def test_final_report_prints_scenario_count_and_floor(self):
        from pathlib import Path
        import tempfile
        from learning.report import write_profile_report
        from learning.evaluate import comparisons

        jobs, results=panel(['same']*30)
        row=comparisons(jobs,results)['duel']
        with tempfile.TemporaryDirectory() as directory:
            write_profile_report(directory,dict(format='duel',status='insufficient_design',
                controls=dict(control=row),selected_kind='fallback',version=0,parameters=1,
                checkpoint_sha256='fixture'),[])
            report=(Path(directory)/'REPORT.md').read_text(encoding='utf-8')
            self.assertIn('Distinct scenarios | Required scenarios',report)
            self.assertIn('| control | 30 | 30 | 1 | 12 |',report)

    def test_gate_reports_distinct_scenarios(self):
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from learning.common import read_json
        from tests.test_validation_cadence import ValidationCadenceTests
        from tests.v5.helpers import synthetic_decision_row

        rows = [dict(synthetic_decision_row(), scenario_family=f's{i}',
                     game_id=f'g{i}', game_family=f'g{i}') for i in range(4)]
        with tempfile.TemporaryDirectory() as directory:
            runner = ValidationCadenceTests().runner(directory)
            runner.state['effective'] = True
            runner.state['pending_train'] = dict(method='bc', paths=[], cursor={})
            with patch('learning.experiment.read_shards', return_value=rows), \
                 patch('learning.experiment.train', return_value=dict(interrupted=False, updates=1)), \
                 patch('learning.experiment.imitation_quality', return_value=dict(effective=True, formats=dict(duel=dict(accuracy=1.)))), \
                 patch('learning.experiment.FormatExperiment._write_checkpoint'):
                runner.finish_train()
            gate = read_json(Path(directory)/'bc_gate.json')
            self.assertEqual(gate['distinct_scenarios'], 4)
            self.assertEqual(gate['min_distinct'], 12)
            self.assertEqual(gate['scope'], 'initialisation_only')
            self.assertEqual(gate['status'], 'insufficient_design')
            self.assertFalse(gate['passed'])
            self.assertFalse(runner.state['effective'])

    def test_distinct_positive_scenarios_can_pass_without_more_blocks(self):
        from learning.evaluate import comparisons

        jobs, results = panel([f's{i}' for i in range(12)])
        row = comparisons(jobs, results, min_blocks=12)['duel']
        self.assertEqual(row['distinct_scenarios'], 12)
        self.assertEqual(row['status'], 'passed')
        self.assertEqual(row['interval95'], [3., 3.])

    def test_cluster_means_do_not_weight_repetitions_as_scenarios(self):
        from learning.evaluate import comparisons

        jobs, results = panel(['a'] * 30 + ['b'], [3.] * 30 + [-3.])
        row = comparisons(jobs, results, min_blocks=31, min_distinct=2)['duel']
        self.assertEqual(row['difference'], 0.)
        self.assertEqual(row['interval95'], [-3., 3.])
        self.assertEqual(row['contexts']['solo']['distinct_scenarios'], 2)

    def test_repeated_identical_blocks_are_insufficient(self):
        from learning.evaluate import comparisons, selection_key, overall_status

        jobs, results = panel(['same'] * 30)
        summary = comparisons(jobs, results)
        self.assertEqual(summary['duel']['status'], 'insufficient_design')
        self.assertEqual(summary['duel']['distinct_scenarios'], 1)
        self.assertEqual(summary['duel']['min_distinct'], 12)
        self.assertIsNone(selection_key(summary))
        self.assertEqual(overall_status(summary), 'insufficient_design')


if __name__ == '__main__':
    unittest.main()
