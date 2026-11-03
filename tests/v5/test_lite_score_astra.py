"""Score-only Astra seats use the same public plan, ledger and referee transitions."""
from unittest.mock import patch
import unittest

from learning.lite_host import LiteHost, play_lite_job
from tests.v5 import test_pipeline_contract as pipeline


class ScoreAstraTests(unittest.TestCase):
    def setUp(self):
        fixture = pipeline.LiteJobTests('test_astra_job_writes_schema_four_shard')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.rules = fixture.rules_dir
        self.job = fixture.job()

    def replay(self, job):
        plans, outcomes, compact = [], [], []
        decide, execute = LiteHost.decision, LiteHost.execute

        def capture_plan(host, side, **options):
            row = decide(host, side, **options)
            if options['teacher']:
                ledger = host.snapshot()['host']['teacher_memory']
                plans.append((row['teacher_action'], ledger))
                compact.append(set(row) == {'teacher_action'})
            return row

        def capture_outcome(host, action, **options):
            value = execute(host, action, **options)
            outcomes.append((value['events'], value['committed'], value['view']))
            if options.get('score_only_astra'):
                self.assertEqual(set(value), {'events', 'committed', 'view'})
            return value

        with pipeline.catalog_patch(self.rules), patch.object(LiteHost, 'decision', capture_plan), \
                patch.object(LiteHost, 'execute', capture_outcome):
            result = play_lite_job(job)
        self.assertEqual(result['status'], 'complete', result.get('error'))
        self.assertFalse(result['result']['faults'])
        return plans, outcomes, result, compact

    def test_score_only_reproduces_full_plans_ledger_and_transitions(self):
        job = {k: v for k, v in self.job.items() if k not in ('learning', 'shard')}
        full = self.replay(job)
        fast = self.replay(dict(job, score_only_astra=True))
        self.assertEqual(full[:3], fast[:3])
        self.assertGreater(len(fast[0]), 1)
        self.assertFalse(any(full[3]))
        self.assertTrue(all(fast[3]))

    def test_learning_and_opening_keep_full_records(self):
        for kind in ('learning', 'opening', 'reward_reference'):
            with self.subTest(kind=kind):
                job = dict(self.job, score_only_astra=True)
                if kind != 'learning':
                    job.pop('learning')
                    job.pop('shard')
                    job['meta'] = dict(job['meta'], phase=kind, opening=kind == 'opening')
                _, _, result, compact = self.replay(job)
                self.assertFalse(any(compact))
                if kind == 'learning':
                    self.assertGreater(result['training_shard']['written'], 0)
                elif kind == 'opening':
                    self.assertTrue(result['behavior'])
                else:
                    self.assertIn('reward_diagnostics', result)


if __name__ == '__main__':
    unittest.main()
