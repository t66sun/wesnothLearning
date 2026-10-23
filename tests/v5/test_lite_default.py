"""Default selection and rule binding, without launching collection or training."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from learning.common import ROOT
from learning.formats import FORMATS


class LiteDefaultTests(unittest.TestCase):
    def test_default_quota_and_explicit_native(self):
        from learning.experiment import default_config
        for device in ('cpu', 'cuda'):
            config = default_config(device)
            self.assertEqual(config['engine'], 'lite')
            self.assertTrue(config['allow_approximate'])
            self.assertEqual(config['bc_games'], dict(duel=300, ffa4=600, team2v2=400))
            self.assertEqual(config['native_bc_games'], dict.fromkeys(FORMATS, 0))
            self.assertEqual(config['evaluation_engine'], 'lite')
        native = default_config('cpu', engine='native')
        self.assertEqual(native['engine'], 'native')
        self.assertEqual(native['bc_games'], dict(duel=300, ffa4=600, team2v2=400))
        self.assertEqual(native['native_bc_games'], native['bc_games'])
        self.assertEqual(native['evaluation_engine'], 'native')

    def test_cli_native_quota_override_and_bounds(self):
        from learning.__main__ import parser, run_config
        from learning.experiment import validate_config
        config = run_config(parser().parse_args(['run', '--hours', '18', '--bc-games', '300', '600', '400',
                                               '--native-bc-games', '0', '0', '0']))
        validate_config(config)
        self.assertEqual(config['hours'], 18)
        self.assertEqual(config['evaluation_engine'], 'lite')
        self.assertEqual(config['native_bc_games'], dict.fromkeys(FORMATS, 0))
        override = run_config(parser().parse_args(['run', '--native-bc-games', '10', '20', '30',
                                                 '--evaluation-engine', 'native']))
        validate_config(override)
        self.assertEqual(override['native_bc_games'], dict(zip(FORMATS, (10, 20, 30))))
        self.assertEqual(override['evaluation_engine'], 'native')
        for invalid in (-1, 601, 1.5):
            with self.subTest(native_games=invalid):
                with self.assertRaisesRegex(ValueError, 'native BC games'):
                    validate_config(config | {'native_bc_games': dict.fromkeys(FORMATS, invalid)})

    def test_cli_omitted_defaults_match_program_api(self):
        from learning.__main__ import parser, run_config
        from learning.experiment import default_config, validate_config
        config = run_config(parser().parse_args(['run']))
        validate_config(config)
        self.assertEqual(config['bc_games'], dict(duel=300, ffa4=600, team2v2=400))
        self.assertEqual(config['native_bc_games'], dict.fromkeys(FORMATS, 0))
        self.assertEqual((config['workers'], config['trainer_threads']), (8, 1))
        self.assertEqual(config['hours'], 12.)
        self.assertEqual(config['device'], 'cpu')
        self.assertEqual((config['engine'], config['evaluation_engine']), ('lite', 'lite'))
        override = run_config(parser().parse_args(['run', '--device', 'cuda', '--workers', '6',
                                                   '--bc-games', '10', '20', '30', '--hours', '3']))
        validate_config(override)
        self.assertEqual((override['workers'], override['hours'], override['device']), (6, 3., 'cuda'))
        self.assertEqual(override['bc_games'], dict(duel=10, ffa4=20, team2v2=30))
        self.assertEqual(override['bc_games']['ffa4'], 20)
        self.assertEqual(override['native_bc_games'], dict.fromkeys(FORMATS, 0))
        for invalid in (0, 17):
            with self.subTest(workers=invalid):
                with self.assertRaisesRegex(ValueError, 'GLOBAL game process count'):
                    validate_config(default_config('cpu') | {'workers': invalid})
        run_parser = next(action for action in parser()._actions
                          if getattr(action, 'choices', None) and 'run' in action.choices).choices['run']
        help_text = ''.join(run_parser.format_help().split())
        self.assertIn('300/600/400', help_text)
        self.assertIn('默认8', help_text)

    def test_resume_keeps_frozen_targets_workers_and_deadline(self):
        from learning.common import sha256, write_json
        from learning.experiment import default_config
        from learning.__main__ import parser, run_config
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            baseline = run / 'baseline.engine'
            baseline.write_bytes(b'fixture')
            frozen = default_config('cpu') | dict(
                workers=4, hours=18., bc_games=dict.fromkeys(FORMATS, 6000),
                native_bc_games=dict.fromkeys(FORMATS, 0),
                rules_dir=str((ROOT / 'data/rules/1.18.8-training').resolve()))
            write_json(run / 'manifest.json', dict(config=frozen, opponents=[],
                baseline=dict(path=str(baseline), sha256=sha256(baseline)), source={}))
            clock = dict(started=1000., update_deadline=2000., deadline=3000.)
            write_json(run / 'clock.json', clock)
            requested = run_config(parser().parse_args(['run', '--resume', str(run), '--hours', '1',
                                                        '--workers', '2', '--bc-games', '300', '600', '400']))
            self.assertEqual((requested['workers'], requested['hours']), (2, 1.))
            from learning.coordinator import Experiment
            experiment = Experiment(run, config=requested, resume=True)
            self.assertEqual(experiment.config['workers'], 4)
            self.assertEqual(experiment.config['hours'], 18.)
            self.assertEqual(experiment.config['bc_games'], dict.fromkeys(FORMATS, 6000))
            self.assertEqual(experiment.clock, clock)

    def test_partial_batch_truncates_quota_and_failed_games_do_not_count(self):
        from learning.common import write_json
        from learning.experiment import FormatExperiment, default_config

        def evidence(native=False):
            valid = dict(id='valid', status='complete', meta=dict(phase='teacher'), result={},
                         coverage=dict(matched=1), training_eligible=True)
            if native: valid['meta']['engine_id'] = 'native'
            return [valid,
                    dict(id='faults', status='complete', meta=dict(phase='teacher'),
                         result=dict(faults={'2': 'teacher assertion'}), coverage=dict(matched=1)),
                    dict(id='status', status='infrastructure_error', meta=dict(phase='teacher'),
                         result={}, coverage=dict(matched=1)),
                    dict(id='ineligible', status='complete', meta=dict(phase='teacher'), result={},
                         coverage=dict(matched=1), training_eligible=False),
                    dict(id='uncovered', status='complete', meta=dict(phase='teacher'), result={},
                         coverage=dict(matched=0)),
                    dict(id='not-teacher', status='complete', meta=dict(phase='reward_reference'),
                         result={}, coverage=dict(matched=1))]

        def schedule(rows, native_duel):
            temporary = tempfile.TemporaryDirectory()
            self.addCleanup(temporary.cleanup)
            directory = Path(temporary.name)
            (directory / 'jobs.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
            runner = object.__new__(FormatExperiment)
            runner.directory = directory
            runner.fmt = 'duel'
            runner.config = default_config('cpu') | dict(
                bc_games=dict(duel=5, ffa4=600, team2v2=400),
                native_bc_games=dict(duel=native_duel, ffa4=0, team2v2=0))
            runner.clock = dict(update_deadline=3000000000.)
            runner.state = dict(pending_train=None, pending_validation=None, batch=0, version=0,
                                effective=False, stage='bc', teacher_shards=[], dagger_shards=[],
                                counters=dict(environment_games=0, collection_batches=0))
            runner.teachers = ['gpt6astra']
            runner.fixed = ['gpt6astra', 'baseline']
            runner.native_fixed = ['gpt6astra', 'baseline', 'native']
            runner.support = 'support'
            runner.exe = 'unused'
            runner.save = lambda: None
            runner.human_paths = lambda: []
            runner.controller = SimpleNamespace(boundary=lambda *args: None)
            calls = {}

            def fake_teacher_jobs(*args, **kwargs):
                calls['count'] = kwargs['count']
                calls['fixed'] = args[2]
                return [dict(id=f'job-{i}', meta={}) for i in range(kwargs['count'])]

            def fake_execute(_self, jobs, name):
                calls['jobs'] = jobs
                _self.clock['update_deadline'] = 0
                return jobs, []

            with mock.patch('learning.experiment.teacher_jobs', side_effect=fake_teacher_jobs), \
                 mock.patch('learning.experiment.FormatExperiment.execute', autospec=True, side_effect=fake_execute), \
                 mock.patch('learning.experiment.read_shards', return_value=[]):
                runner.learn()
            self.assertEqual(runner.clock['update_deadline'], 0)
            self.assertEqual((runner.state['batch'], runner.state['counters']),
                             (1, dict(environment_games=0, collection_batches=1)))
            return runner, calls

        runner, calls = schedule(evidence(), 0)
        self.assertEqual(calls['count'], 4)  # five-game target minus the one valid teacher game
        self.assertEqual(calls['fixed'], runner.fixed)
        self.assertTrue(all(job.get('engine') != 'native' for job in calls['jobs']))
        runner, calls = schedule(evidence(native=True), 3)
        self.assertEqual(calls['count'], 2)  # native lower bound 3 minus one native game
        self.assertEqual(calls['fixed'], runner.native_fixed)
        self.assertTrue(all(job['engine'] == 'native' for job in calls['jobs']))

    def test_lite_final_evaluation_has_only_astra_controls(self):
        import torch
        from learning.experiment import FormatExperiment, default_config
        from learning.sample import opening_map
        with tempfile.TemporaryDirectory() as temporary:
            runner = object.__new__(FormatExperiment)
            runner.directory = Path(temporary)
            runner.fmt = 'team2v2'
            runner.config = default_config('cpu')
            runner.clock = dict(deadline=3000000000.)
            runner.state = dict(best_kind=None, effective=False, error=None, history=[])
            runner.teachers = ['gpt6astra.zip']
            runner.native_fixed = runner.teachers + ['baseline']
            runner.fixed = runner.teachers
            runner.exe = 'unused'
            runner.save = lambda: None
            runner.ensure_export = lambda *args, **kwargs: 'policy'
            runner.teacher_evidence = lambda: []
            (runner.directory/'latest.pt').write_bytes(b'fixture')
            scheduled = []

            def execute(jobs, name):
                scheduled.extend(jobs)
                return jobs, []

            runner.execute = execute
            with mock.patch('learning.experiment.load_model', return_value=(torch.nn.Linear(1, 1), {'runner': {'version': 1}})), \
                 mock.patch('learning.maps.frozen_map', return_value=(opening_map(4), '0'*64)):
                summary = runner.final_evaluation()
            self.assertEqual(summary['evaluation_engine'], 'lite')
            self.assertIn('not native', summary['evaluation_scope'])
            self.assertEqual(set(summary['controls']), {'gpt6astra'})
            self.assertTrue(all(job['engine'] == 'lite' for job in scheduled))
            self.assertTrue(all(set(job['bots']) <= {'policy', 'gpt6astra.zip'} for job in scheduled))
            self.assertEqual({job['meta']['context'] for job in scheduled}, {'astra_partner', 'self_team'})
            report = (runner.directory/'report/REPORT.md').read_text(encoding='utf-8')
            self.assertIn('Evaluation engine: lite', report)
            self.assertIn(summary['evaluation_scope'], report)

    def test_cli_binds_rules_before_features_and_restores_resume(self):
        # A fresh interpreter catches an eager feature import in the CLI itself.
        rules = (ROOT / 'data/rules/1.18.8').resolve()
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            (run / 'manifest.json').write_text(json.dumps({'config': {'rules_dir': str(rules)}}), encoding='utf-8')
            script = '''
import json, os, sys
from pathlib import Path
from learning.__main__ import parser, bind_rules, run_config
assert 'learning.features' not in sys.modules, 'CLI imported feature schema before rule selection'
rules, run = map(Path, sys.argv[1:])
args = parser().parse_args(['run', '--rules-dir', str(rules)])
assert bind_rules(args) == rules
from learning.features import RULES_PATH, schema
assert RULES_PATH.parent == rules
expected = json.loads((rules/'catalog-summary.json').read_text())['rules_file_sha256']
assert schema()['rules_sha256'] == expected
assert run_config(args)['rules_dir'] == str(rules)
os.environ['WESNOTH_RULES_DIR'] = str(rules.parent/'different-rules')
resumed = parser().parse_args(['run', '--resume', str(run)])
assert bind_rules(resumed) == rules
assert run_config(resumed)['rules_dir'] == str(rules)
try:
    bind_rules(parser().parse_args(['run', '--resume', str(run), '--rules-dir', str(rules.parent/'different-rules')]))
except ValueError as exc:
    assert 'frozen rules' in str(exc)
else:
    raise AssertionError('resume allowed a different rules directory')
'''
            env = dict(os.environ)
            env.pop('WESNOTH_RULES_DIR', None)
            result = subprocess.run([sys.executable, '-c', script, str(rules), str(run)],
                                    cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_native_anchor_and_lite_jobs_share_frozen_rules(self):
        from learning.experiment import FormatExperiment
        rules = str((ROOT / 'data/rules/1.18.8-training').resolve())
        with tempfile.TemporaryDirectory() as temporary:
            runner = object.__new__(FormatExperiment)
            runner.directory = Path(temporary)
            runner.config = dict(engine='lite', rules_dir=rules, allow_approximate=True)
            runner.controller = SimpleNamespace(freeze=lambda: {'reward_version': 1})
            runner.teachers = ['gpt6astra']
            captured = []

            def collect(jobs, log):
                captured.extend(jobs)
                log.write_text(''.join(json.dumps(dict(id=j['id'], status='complete'))+'\n' for j in jobs), encoding='utf-8')

            runner.collector = collect
            jobs = [dict(id='lite', bots=['baseline', 'gpt6astra']),
                    dict(id='anchor', engine='native', bots=['baseline', 'gpt6astra'])]
            scheduled, outcomes = runner.execute(jobs, 'minimal-binding')
            self.assertEqual(len(outcomes), 2)
            self.assertEqual(captured, scheduled)
            self.assertTrue(all(j['rules_dir'] == rules for j in scheduled))
            self.assertEqual([j['engine'] for j in scheduled], ['lite', 'native'])
            self.assertEqual(scheduled[0]['bots'], ['gpt6astra', 'gpt6astra'])
            self.assertTrue(scheduled[0]['allow_approximate'])
            self.assertEqual(scheduled[1]['bots'][0], 'baseline')


if __name__ == '__main__':
    unittest.main()
