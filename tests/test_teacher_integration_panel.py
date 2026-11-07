"""Design/report assertions run without starting acceptance games."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from learning.common import read_json
from tests.acceptance_teacher_integration import prepare,validate_design,summarize,audit_rows


class TeacherIntegrationPanelTests(unittest.TestCase):
    def test_frozen_design_uses_actual_production_routes_without_optimization(self):
        with tempfile.TemporaryDirectory() as temp,patch('torch.optim.Adam',side_effect=AssertionError('optimizer forbidden')):
            output=Path(temp)/'panel'
            manifest,jobs=prepare(output,started=100.)
            self.assertEqual(len(jobs),48)
            self.assertEqual(manifest['deadline'],3700.)
            self.assertEqual(manifest['workers'],8)
            self.assertEqual(read_json(output/'jobs.json'),jobs)
            for job in jobs:
                self.assertEqual(job['meta']['teacher_roles']['supervision']['teacher'],
                                 'gpt6astra' if job['format']=='ffa4' else 'selected_teacher')
                self.assertEqual(job['reward_config']['explore'],0.)
                self.assertEqual(job['reward_config']['gamma'],1.)
            bad=copy.deepcopy(jobs);bad[0]['meta']['map_partition']='validation'
            with self.assertRaisesRegex(ValueError,'train'):validate_design(bad)
            with self.assertRaisesRegex(ValueError,'48'):validate_design(jobs[:-1])
            report=summarize(output,manifest,jobs,[],200.)
            self.assertFalse(report['passed'])
            self.assertTrue(all(cell['completed']==0 and not cell['passed'] for cell in report['cells'].values()))
            for j in jobs:
                Path(j['shard']).parent.mkdir(parents=True,exist_ok=True)
            import gzip
            ppo=next(j for j in jobs if j['meta']['phase']=='ppo')
            for path in (ppo['shard'],ppo['shard'].replace('.jsonl.gz','.dagger.jsonl.gz')):
                with gzip.open(path,'wt'):pass
            self.assertIn('empty student or teacher shard',audit_rows(ppo)['errors'])
            records=[dict(id=j['id'],status='complete',meta=j['meta'],result=dict(faults=[]),
                coverage=dict(total=100,matched=100,kinds={k:dict(total=10,matched=10) for k in ('recruit','move','attack')}),
                teacher_queries=dict(valid=1,queries=1) if j['meta']['phase']=='ppo' else {}) for j in jobs]
            missing=dict(rows=1,valid=1,unmatched=0,dagger_rows=1,dagger_valid=0,dagger_queries=1,errors=[])
            with patch('tests.acceptance_teacher_integration.audit_rows',return_value=missing):
                report=summarize(output,manifest,jobs,records,200.)
            self.assertFalse(report['passed'])
            self.assertTrue(all(any('stored DAgger labels' in e for e in cell['errors']) for cell in report['cells'].values()))
            with self.assertRaises(FileExistsError):prepare(output)


if __name__=='__main__':unittest.main()
