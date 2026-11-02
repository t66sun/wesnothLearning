"""A branch counts only eligible teacher games owned by its inherited checkpoint."""
import json
from pathlib import Path
import tempfile
import unittest

from learning.experiment import FormatExperiment, coverage_gate


def result(ident, *, matched=10, **changes):
    row = dict(id=ident, meta=dict(phase='teacher'), status='complete',
               result=dict(faults=[]), training_eligible=True,
               coverage=dict(total=10, matched=matched,
                             kinds={kind: dict(total=10, matched=matched)
                                    for kind in ('recruit', 'move', 'attack')}))
    return row | changes


def write_log(directory, rows):
    directory.mkdir(parents=True)
    (directory/'jobs.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))


def runner(directory, shards, parents):
    experiment = object.__new__(FormatExperiment)
    experiment.directory = directory
    experiment.fmt = directory.name
    experiment.state = dict(teacher_shards=list(map(str, shards)),
                            lineage=[dict(parent=str(parent)) for parent in parents])
    return experiment


class BranchTeacherEvidenceTests(unittest.TestCase):
    def test_inherited_and_child_games_supply_the_same_corpus_and_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent, child = root/'parent/team2v2', root/'child/team2v2'
            write_log(parent, [result('parent', matched=9)])
            write_log(child, [result('child')])
            experiment = runner(child, [parent/'data/parent.jsonl.gz', child/'data/child.jsonl.gz'],
                                [parent.parent])
            evidence = experiment.teacher_evidence()
            self.assertEqual({row['id'] for row in evidence}, {'parent', 'child'})
            self.assertTrue(coverage_gate(evidence)['passed'])
            self.assertEqual(coverage_gate(evidence)['actions']['all']['total'], 20)

    def test_later_parent_collection_and_ineligible_results_are_not_inherited(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent, child = root/'parent/team2v2', root/'child/team2v2'
            rows = [result('included'), result('after-checkpoint'),
                    result('faulted', result=dict(faults=['failure'])),
                    result('excluded', training_eligible=False),
                    result('unfinished', status='budget_interrupted'),
                    result('uncovered', matched=0), result('policy', meta=dict(phase='ppo'))]
            write_log(parent, rows)
            write_log(child, [])
            inherited = [parent/'data'/(row['id']+'.jsonl.gz') for row in rows
                         if row['id'] != 'after-checkpoint']
            experiment = runner(child, inherited, [parent.parent])
            self.assertEqual([row['id'] for row in experiment.teacher_evidence()], ['included'])

    def test_nested_lineage_deduplicates_paths_and_keeps_format_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ancestor, parent, child = (root/name/'team2v2' for name in ('ancestor', 'parent', 'child'))
            write_log(ancestor, [result('same-id')])
            write_log(parent, [result('same-id')])
            write_log(root/'ancestor/duel', [result('wrong-format')])
            write_log(child, [])
            shards = [directory/'data/same-id.jsonl.gz' for directory in (ancestor, parent)]
            experiment = runner(child, shards, [ancestor.parent, parent.parent, ancestor.parent])
            evidence = experiment.teacher_evidence()
            self.assertEqual(len(evidence), 2)  # Different shard paths may have the same local job ID.
            self.assertEqual([row['id'] for row in evidence], ['same-id', 'same-id'])

    def test_fresh_run_keeps_current_log_eligibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)/'team2v2'
            write_log(directory, [result('valid'), result('bad', training_eligible=False)])
            experiment = runner(directory, [], [])
            self.assertEqual([row['id'] for row in experiment.teacher_evidence()], ['valid'])


if __name__ == '__main__':
    unittest.main()
