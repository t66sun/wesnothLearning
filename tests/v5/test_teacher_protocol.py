"""A teacher is queried only through a capability its record declares."""
import unittest


class TeacherProtocolTests(unittest.TestCase):
    def test_stock_teacher_rejects_per_decision_query(self):
        from learning.manifest import teacher_identity
        from learning.teacher_protocol import STOCK_STATUS, dagger_status, dagger_teacher, require_query

        record = teacher_identity('wesnoth_default_rca')
        self.assertEqual(record['query'], 'none')
        self.assertEqual(dagger_status(record), STOCK_STATUS)
        with self.assertRaisesRegex(ValueError, 'no per-decision query capability'):
            require_query(record)
        with self.assertRaisesRegex(ValueError, 'no per-decision query capability'):
            dagger_teacher(record, 'baseline')

        astra = dict(kind='gpt6astra', version='1.0', query='per_decision', action_source='lua_wrapper')
        self.assertEqual(dagger_status(astra), 'active')
        self.assertEqual(require_query(astra), 'per_decision')
        self.assertEqual(dagger_teacher(astra, '/frozen/gpt6astra'), '/frozen/gpt6astra')
        with self.assertRaisesRegex(ValueError, 'lacks its controller path'):
            dagger_teacher(astra, None)

    def test_stock_teacher_games_are_full_native_games(self):
        from learning.manifest import teacher_identity
        from learning.schedule import stock_teacher_jobs

        record = dict(teacher_identity('wesnoth_default_rca'), runtime_sha256='1' * 64)
        jobs = stock_teacher_jobs('.', record, 'support', 0, 19, 1000, 'unused',
                                  formats=['duel'], count=2, index_stride=2)
        self.assertEqual(len(jobs), 2)
        for job in jobs:
            self.assertEqual(job['bots'], ['baseline', 'baseline'])
            self.assertEqual(job['learning']['stock_capture'], [1, 2])
            self.assertEqual(job['learning']['sides'], {})
            self.assertNotIn('dagger_teacher', job['learning'])
            self.assertEqual(job['teacher_identity']['query'], 'none')
            self.assertEqual(job['meta']['phase'], 'teacher')
            self.assertTrue(job['shard'].endswith('.jsonl.gz'))
            self.assertEqual(job['engine'], 'native')
        self.assertEqual(len({job['seed'] for job in jobs}), 2)
        with self.assertRaisesRegex(ValueError, 'without a per-decision query'):
            stock_teacher_jobs('.', dict(record, query='per_decision'), 'support', 0, 19, 1000, 'unused', formats=['duel'])

    def test_stock_capture_refuses_a_per_decision_query(self):
        import time
        from learning.common import sha256
        from learning.manifest import teacher_identity
        from learning.sample import play_job
        from tests.v5 import helpers

        with helpers.temporary_directory() as directory:
            runtime = directory / 'runtime-reference'
            runtime.write_bytes(b'unit-test runtime reference; never executed')
            record = dict(teacher_identity('wesnoth_default_rca'), runtime_sha256=sha256(runtime))
            job = dict(id='stock-query', bots=['baseline', 'baseline'], seed=19, deadline=time.time() + 60,
                wesnoth=str(runtime), output=str(directory / 'replay.json'),
                teacher_identity=record, learning=dict(stock_capture=[1, 2],
                    sides={'1': dict(teacher='wesnoth_default_rca')}))
            with self.assertRaisesRegex(ValueError, 'cannot request a per-decision teacher query'):
                play_job(job)

    def test_runner_collects_stock_games_without_a_teacher_seat(self):
        from unittest.mock import patch
        from learning.experiment import FormatExperiment, default_config
        from learning.manifest import freeze
        from tests.v5 import helpers

        with helpers.temporary_directory() as directory:
            runtime = directory / 'runtime-reference'
            runtime.write_bytes(b'unit-test runtime reference; never executed')
            with patch('learning.manifest.native.find_wesnoth', return_value=str(runtime)), \
                 patch('learning.manifest.dependency_versions', return_value=dict(packages=dict(torch='2.9.1+cpu'))):
                manifest, _ = freeze(directory / 'run', directory / 'unused', None, default_config('cpu', engine='native'))
            with patch.object(FormatExperiment, 'ensure_export', return_value='policy'):
                runner = FormatExperiment(directory / 'run/duel', 'duel', manifest,
                    dict(started=0, update_deadline=3000000000., deadline=3000000001.), lambda jobs, log: None)
            self.assertEqual(runner.state['dagger_status'], 'unsupported_with_stock_rca')
            jobs = runner.teacher_batch(1, 0, False)
            self.assertEqual([job['bots'] for job in jobs], [['baseline', 'baseline']])
            self.assertTrue(all('dagger_teacher' not in job['learning'] for job in jobs))
            self.assertIn('stock_capture', jobs[0]['learning'])
            summary = runner.complete_phase()
            self.assertEqual(summary['teacher']['query'], 'none')
            self.assertEqual(summary['teacher']['dagger_status'], 'unsupported_with_stock_rca')
            self.assertEqual(summary['teacher']['dagger_shards'], 0)
            import json
            saved = json.loads((directory / 'run/duel/report/summary.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['teacher']['query'], 'none')


if __name__ == '__main__':
    unittest.main()
