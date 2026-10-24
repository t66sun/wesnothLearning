"""A failed pool must not strand trainers in Experiment.run's final join."""
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from learning.coordinator import Experiment


class PoolFailureTests(unittest.TestCase):
    def test_broken_pool_terminates_live_trainers_before_join(self):
        children = []

        class Child:
            def __init__(self, **kwargs):
                self.alive = True
                children.append(self)

            def start(self):
                pass

            def is_alive(self):
                return self.alive

            def terminate(self):
                self.alive = False

            def join(self):
                if self.alive:
                    raise AssertionError('joining a live trainer blocked on its reply queue')

        ctx = SimpleNamespace(Process=Child, Queue=mock.Mock)
        with tempfile.TemporaryDirectory() as directory:
            experiment = Experiment.__new__(Experiment)
            experiment.directory = Path(directory)
            experiment.config = dict(formats=['duel', 'team2v2'], workers=8)
            experiment.manifest = {};experiment.clock = {};experiment.resume = False
            with mock.patch('learning.coordinator.get_context', return_value=ctx), mock.patch(
                'learning.coordinator.broker', side_effect=BrokenProcessPool('injected worker loss')
            ):
                with self.assertRaisesRegex(BrokenProcessPool, 'injected worker loss'):
                    experiment.run()
        self.assertEqual(len(children), 2)
        self.assertTrue(all(not child.is_alive() for child in children))


if __name__ == '__main__':
    unittest.main()
