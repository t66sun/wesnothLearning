import argparse
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from learning.formats import FORMATS
from learning.teacher_lab.batch import batch
from learning.teacher_lab.packages import digest, write_new
from learning.teacher_lab.report import candidate_cells, compare
from tests.test_teacher_lab import outcome


class TeacherBatchTests(unittest.TestCase):
    def setup_directory(self,root):
        baseline=root/'astra.zip';baseline.write_bytes(b'astra')
        control=dict(name='astra',package=str(baseline),package_sha256=digest(baseline))
        write_new(root/'manifest.json',dict(baseline=control,workers=8,source_commit='frozen',executable='wesnoth'))
        write_new(root/'clock.json',dict(exploration_end=9999999999))
        for name in ('one','two'):
            package=root/(name+'.zip');package.write_bytes(name.encode())
            write_new(root/'candidates'/name/'candidate.json',dict(name=name,package=str(package),package_sha256=digest(package)))
        return argparse.Namespace(directory=root,name='both',candidates=['one','two'],
                                  formats=FORMATS,blocks=2,offset=1,seed=19)

    def test_complete_matched_rotations_share_one_eight_worker_pool(self):
        with tempfile.TemporaryDirectory() as temp:
            args=self.setup_directory(Path(temp));observed={}
            def run(directory,jobs,workers,metadata):
                observed.update(jobs=jobs,workers=workers,metadata=metadata)
                return [outcome(j) for j in jobs]
            with patch('learning.teacher_lab.batch.require_evaluator') as identity,\
                    patch('learning.teacher_lab.batch.execute',side_effect=run) as execute,\
                    patch('learning.teacher_lab.batch.report_panel',side_effect=lambda d,j,r:compare(j,r)):
                result=batch(args)
            identity.assert_called_once();execute.assert_called_once()
            self.assertEqual(observed['workers'],8)
            self.assertEqual(len(observed['jobs']),112)
            self.assertEqual(len({j['id'] for j in observed['jobs']}),112)
            self.assertEqual(set(observed['metadata']['candidates']),{'one','two'})
            designs={name:{(j['meta']['format'],j['meta']['horizon'],j['meta']['block'],
                           j['meta']['context'],j['meta']['rotation'],j['scenario_family'],j['seed'])
                          for j in observed['jobs'] if j['meta']['candidate']==name} for name in ('one','two')}
            self.assertEqual(designs['one'],designs['two'])
            for name in ('one','two'):
                cells=candidate_cells(result,name,'astra')
                self.assertEqual(len(cells),6)
                self.assertTrue(all(r['complete'] and r['distinct_scenarios']==2 for r in cells.values()))
            self.assertTrue(all(j['deadline']==9999999999 for j in observed['jobs']))

    def test_expired_clock_or_changed_package_never_starts_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            args=self.setup_directory(Path(temp))
            with patch('learning.teacher_lab.batch.require_evaluator'),\
                    patch('learning.teacher_lab.batch.execute') as execute:
                with patch('learning.teacher_lab.batch.time.time',return_value=9999999999),self.assertRaises(ValueError):
                    batch(args)
                (args.directory/'one.zip').write_bytes(b'changed')
                with self.assertRaises(ValueError):batch(args)
                execute.assert_not_called()


if __name__=='__main__':
    unittest.main()
