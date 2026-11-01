"""The BC nonempty check consumes the actual batch, without a throwaway read."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_validation_cadence import ValidationCadenceTests


class BcPreflightReadTests(unittest.TestCase):
    def runner(self, directory):
        runner = ValidationCadenceTests().runner(directory)
        runner.config['seed'] = 47
        runner.state.update(phase='bc', stage='bc', teacher_shards=['teacher'],
            dagger_shards=['dagger'])
        runner.state['counters'].update(environment_games=0, collection_batches=0)
        runner.human_paths = lambda: [Path('human')]
        runner.controller.boundary = lambda *args: None
        runner.execute = lambda *args: ([], [])
        return runner

    def test_actual_training_read_is_reused_and_resume_reads_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = self.runner(directory)
            rows = [dict(game_family='training')]
            reads = []
            def read(paths, **kwargs):
                reads.append((list(paths), kwargs))
                if 'stats' in kwargs:
                    kwargs['stats']['rows'] = len(rows)
                return rows if kwargs.get('partition') == 'train' else []
            def train(*args, **kwargs):
                self.assertEqual(args[2], rows)
                self.assertIs(kwargs['bc_records'], rows)
                return dict(interrupted=True)
            with patch('learning.experiment.teacher_jobs', return_value=[]), \
                 patch('learning.experiment.read_shards', side_effect=read), \
                 patch('learning.experiment.rollout_identity', return_value='fixed'), \
                 patch('learning.experiment.train', side_effect=train):
                runner.learn()
                self.assertEqual(len(reads), 2, 'one train read plus one validation read')
                self.assertEqual(reads[0][0], ['teacher', 'dagger', 'human'])
                self.assertEqual(reads[0][1]['seed'], 47)
                self.assertEqual(reads[0][1]['limit'], runner.config['bc_records'])
                first = runner.state['pending_train'].copy()
                rows = [dict(game_family='training')]
                self.assertFalse(runner.finish_train())
                self.assertEqual(len(reads), 4, 'resume reconstructs both batches')
                self.assertEqual(reads[2][1]['seed'], 47)
                self.assertEqual(runner.state['pending_train'], first)
                self.assertEqual(runner.state['version'], 0)

    def test_empty_actual_batch_skips_without_pending_update(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = self.runner(directory)
            def execute(*args):
                runner.clock['update_deadline'] = 0
                return [], []
            runner.execute = execute
            with patch('learning.experiment.teacher_jobs', return_value=[]), \
                 patch('learning.experiment.read_shards', return_value=[]) as read, \
                 patch('learning.experiment.train') as train:
                runner.learn()
                read.assert_called_once()
                self.assertEqual(read.call_args.kwargs['seed'], 47)
                self.assertEqual(read.call_args.args[0], ['teacher', 'dagger', 'human'])
                train.assert_not_called()
                self.assertIsNone(runner.state['pending_train'])
                self.assertEqual((runner.state['batch'], runner.state['version']), (1, 0))


if __name__ == '__main__':
    unittest.main()
