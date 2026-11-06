import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from learning.teacher_lab.packages import read,write_new
from learning.teacher_lab.selection import selection_source,shortlists
from learning.teacher_lab.report import compare
from tests.test_teacher_lab import schedule,outcome


class TeacherEligibilityTests(unittest.TestCase):
    def test_excluded_high_scoring_versions_cannot_enter_selection_or_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('old','fixed'):
                write_new(root/'candidates'/name/'candidate.json',dict(name=name,registered=1))
            jobs=schedule(root/'train','old')+schedule(root/'train','fixed')
            summary=compare(jobs,[outcome(j) for j in jobs])
            for evidence in (summary,{}):
                selected=shortlists(root,evidence,'astra',{'old'})
                self.assertTrue(all([r['name'] for r in rows]==['fixed'] for rows in selected.values()))
            self.assertEqual(read(root/'candidates/old/candidate.json')['name'],'old')
            with self.assertRaisesRegex(ValueError,'no eligible'):
                shortlists(root,summary,'astra',{'old','fixed'})

    def test_selection_source_is_pinned_before_deadline_without_changing_baseline_or_clock(self):
        manifest=dict(source_commit='original',baseline=dict(package_sha256='baseline'))
        timer=dict(started=10,exploration_end=100,selection_end=120,final_end=150)
        release=dict(source_commit='reviewed',evaluator_root='/reviewed',base_source_commit='original',
                     baseline_sha256='baseline',exploration_end=100,frozen=90,
                     exclusions={'old':dict(reason='query side effect',evidence='audit.json')})
        cases=[({},True),({'frozen':100},False),({'base_source_commit':'other'},False),
               ({'baseline_sha256':'other'},False),({'exploration_end':101},False),
               ({'exclusions':{'old':dict(reason='',evidence='audit.json')}},False)]
        for change,valid in cases:
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);write_new(root/'selection_source.json',dict(release,**change))
                with patch('learning.teacher_lab.selection.require_evaluator') as require:
                    if valid:
                        identity,excluded=selection_source(root,manifest,timer)
                        require.assert_called_once_with(release)
                        self.assertEqual(identity['source_commit'],'reviewed')
                        self.assertIn('old',excluded)
                    else:
                        with self.assertRaises(ValueError): selection_source(root,manifest,timer)
                self.assertEqual(timer,dict(started=10,exploration_end=100,selection_end=120,final_end=150))
                self.assertEqual(manifest['baseline']['package_sha256'],'baseline')


if __name__=='__main__':
    unittest.main()
