"""Frozen-package collection through the real Lite worker and shard writer."""
from pathlib import Path
import unittest

from learning.lite_host import play_lite_job
from learning.teachers.registry import freeze_set, execution_identity
from tests.v5 import helpers
from tests.v5 import test_pipeline_contract as pipeline


class LiteTeacherCollectionTests(unittest.TestCase):
    def setUp(self):
        fixture=pipeline.LiteJobTests('test_astra_job_writes_schema_four_shard')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=fixture
        self.contract=freeze_set(fixture.directory/'teachers','mixed-20261107')

    def job(self,fmt,*,student=False):
        roles=self.contract['formats'][fmt];teacher=roles['supervision']
        players=2 if fmt=='duel' else 4
        state=helpers.spec(sides=players,fog=False,max_turns=2)
        for side in state['sides']:
            side['gold']=28 if side['id']==1 else 0
            if fmt!='team2v2':side['team']=str(side['id'])
        for unit in state['units']:
            if unit['side']==1 and unit['leader']:unit.update(hp=1000,resolved_max_hp=1000)
        bots=[teacher['package']]*players
        learning=dict(sides={'1':dict(teacher=teacher['teacher'])},version='fixture')
        if student:
            bots[0]=str(self.fixture.frozen_addon(fmt))
            learning=dict(sides={'1':{}},version='fixture',dagger_teacher=teacher['package'])
        return self.fixture.job(id=fmt+('-query' if student else '-collect'),format=fmt,bots=bots,
            teacher_roles=roles,game_spec=state,max_turns=2,learning=learning,
            teams=[1,2,1,2] if fmt=='team2v2' else None,
            factions=['Fighter']*players,
            meta=dict(format=fmt,phase='ppo' if student else 'teacher',context='teacher_partner' if fmt=='team2v2' else 'solo'))

    def run_job(self,job):
        with pipeline.catalog_patch(self.fixture.rules_dir):result=play_lite_job(job)
        self.assertEqual(result['status'],'complete',result)
        self.assertFalse(result['result']['faults'])
        return result

    def assert_identity(self,rows,fmt):
        expected=execution_identity(self.contract['formats'][fmt]['supervision'],'lite')
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row['source'],'teacher')
            self.assertEqual({key:row.get(key) for key in expected},expected)

    def test_frozen_teacher_collection_records_actual_identity_for_each_format(self):
        for fmt in ('duel','ffa4','team2v2'):
            with self.subTest(format=fmt):
                job=self.job(fmt)
                result=self.run_job(job)
                rows=pipeline.read_gzip(job['shard'])
                self.assert_identity(rows,fmt)
                self.assertGreater(result['training_shard']['written'],0)
                self.assertTrue(all('actual' in row for row in rows))

    def test_student_history_and_nonzero_queries_retain_the_selected_teacher(self):
        job=self.job('team2v2',student=True)
        result=self.run_job(job)
        self.assertGreater(result['teacher_queries']['queries'],0)
        self.assertGreater(result['teacher_queries']['valid'],0)
        self.assertFalse(result['teacher_queries']['errors'])
        policy=pipeline.read_gzip(job['shard'])
        path=Path(job['shard'])
        labels=pipeline.read_gzip(path.with_name(path.name.replace('.jsonl.gz','.dagger.jsonl.gz')))
        self.assertEqual(len(labels),len(policy))
        self.assert_identity(labels,'team2v2')
        queried=[r for r in labels if r.get('query_only')]
        self.assertTrue(queried)
        self.assertEqual(queried[0]['query_budget'],20)
        self.assertTrue(all(r['source']=='policy' and not r.get('teacher_contract') for r in policy))


if __name__=='__main__':unittest.main()
