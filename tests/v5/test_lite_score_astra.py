"""Score-only Astra seats use the same public plan, ledger and referee transitions."""
from pathlib import Path
from unittest.mock import patch
import unittest

from learning.lite_host import LiteHost, play_lite_job
from tests.v5 import test_pipeline_contract as pipeline


class ScoreAstraTests(unittest.TestCase):
    def setUp(self):
        fixture = pipeline.LiteJobTests('test_astra_job_writes_schema_four_shard')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.rules = fixture.rules_dir
        self.job = fixture.job()

    def replay(self, job):
        plans, outcomes, compact = [], [], []
        self.calls = [];self.queries=[]
        decide, execute = LiteHost.decision, LiteHost.execute
        query=LiteHost.query_teacher

        def capture_query(host, side):
            self.queries.append(dict(side=side,student=self.calls[-1]))
            return query(host,side)

        def capture_plan(host, side, **options):
            row = decide(host, side, **options)
            self.calls.append(dict(side=side, teacher=options.get('teacher',False),
                                   generate=options.get('generate_candidates',True),
                                   compact=set(row)=={'teacher_action'}, budget='budget' in row.get('timing',{}),
                                   kwargs=sorted(options)))
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
                patch.object(LiteHost, 'execute', capture_outcome), patch.object(LiteHost,'query_teacher',capture_query):
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

    def test_reference_records_only_its_teacher_and_opening_keeps_every_seat(self):
        for opening in (False, True):
            with self.subTest(opening=opening):
                job = self.fixture.job(learning={'sides': {'1': {'teacher':'gpt6astra'}}})
                job.pop('shard')
                job['meta'].update(phase='reward_reference', opening=opening)
                _, _, result, _ = self.replay(job)
                self.assertEqual({c['side'] for c in self.calls if c['teacher'] and c['compact']},
                                 set() if opening else {2})
                learner = [c for c in self.calls if c['side']==1]
                self.assertFalse(any(c['compact'] for c in learner))
                self.assertTrue(any(c['teacher'] and c['generate'] for c in learner))
                self.assertTrue(any(not c['teacher'] and not c['generate'] for c in learner))
                self.assertEqual([m['side'] for m in result['reward_diagnostics']], [1])
                self.assertEqual(bool(result.get('behavior')), opening)

    def test_query_and_bootstrap_decisions_get_full_candidates(self):
        job = self.fixture.four_seat_job(id='query-bootstrap', bootstrap_policy=lambda row: 0.5,
            learning=dict(sides={'1':{}},version='v5-test',dagger_teacher='data/opponents/gpt6astra.zip'))
        # This case tests a surviving learner's external cut. Elimination has
        # its own terminal target and must never acquire a bootstrap value.
        for unit in job['game_spec']['units']:
            if unit['side']==1 and unit['leader']:
                unit.update(hp=1000,resolved_max_hp=1000)
        job['meta']['phase'] = 'ppo'
        _, _, result, _ = self.replay(job)
        self.assertTrue(result['result']['truncated'])
        self.assertIn(1,result['result']['survivors'])
        self.assertEqual({c['side'] for c in self.calls if c['compact']}, {2,3,4})
        queries = [c['student'] for c in self.queries if c['side']==1]
        self.assertTrue(queries)
        self.assertLessEqual(len(queries),32)
        self.assertTrue(all(c['generate'] and c['budget'] and not c['compact'] and not c['teacher'] for c in queries))
        bootstrap = [c for c in self.calls if c['kwargs']==['teacher']]
        self.assertEqual(len(bootstrap),1)
        self.assertIs(self.calls[-1],bootstrap[0])
        self.assertEqual(bootstrap[0],dict(side=1,teacher=False,generate=True,compact=False,budget=True,kwargs=['teacher']))
        rows = pipeline.read_gzip(job['shard'])
        self.assertTrue(rows)
        features = pipeline.features.schema()
        version = f"schema{features['version']}-{features['candidate_selection']['version']}"
        self.assertTrue(all(row['candidate_version']==version for row in rows))
        self.assertTrue(any(row.get('bootstrap_value') is not None for row in rows))
        path = Path(job['shard'])
        dagger_path = path.with_name(path.name.replace('.jsonl.gz','.dagger.jsonl.gz'))
        labels = [row for row in pipeline.read_gzip(dagger_path) if row.get('query_only')]
        self.assertTrue(labels)
        self.assertLessEqual(len(labels),32)
        self.assertTrue(any(len(row['candidates'])>1 and row['choice']>=0 for row in labels))
        for row in labels:
            # A fully generated set can contain only end_turn after all units
            # have acted. The independent query preserves that exact set.
            self.assertGreaterEqual(len(row['candidates']),1)
            self.assertEqual(row['candidate_version'],version)


if __name__ == '__main__':
    unittest.main()
