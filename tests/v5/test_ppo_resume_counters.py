"""V3: cumulative exposure is settled once after a pending PPO update."""
import copy
import random
import unittest
from unittest.mock import patch

import torch

from learning import ppo
from learning.common import write_json
from learning.experiment import FormatExperiment
from learning.train import restore_rng, train
from tests import test_validation_cadence as cadence
from tests.v5 import helpers
from tests.v5.test_ppo_plan import _records, _bc, _run


class PpoResumeCounterTests(unittest.TestCase):
    def test_learner_totals_survive_deadline_and_repeated_boundary_resume(self):
        rows = _records([('b',2,0.),('c',3,0.),('d',4,0.),('e',2,0.)])
        _, _, reference = _run(rows, epochs=2)
        model, optimizer, first = _run(rows, epochs=1)
        cursor = dict(first['cursor'], updates=first['updates'], loss_sum=first['loss']*first['updates'],
            decisions_seen=first['decisions_seen'], committed_decisions=first['committed_decisions'],
            inspected_decisions=first['inspected_decisions'])
        for _ in range(2):
            stopped = ppo.update(model,optimizer,rows,bc_records=_bc(),epochs=2,minibatch=2,deadline=0.,progress=cursor,plan_seed=5)
            self.assertEqual(stopped['committed_decisions'], 11)
            self.assertEqual(stopped['inspected_decisions'], 11)
        second = ppo.update(model,optimizer,rows,bc_records=_bc(),epochs=2,minibatch=2,progress=cursor,plan_seed=5)
        for key in ('updates','decisions_seen','committed_decisions','inspected_decisions','effective_dataset_passes'):
            self.assertEqual(second[key], reference[key], key)

    def test_finish_train_settles_resumed_work_once_with_real_checkpoint(self):
        rows = _records([('b',2,0.),('c',3,0.),('d',4,0.),('e',2,0.)])
        rehearsal = _bc()
        with helpers.temporary_directory() as directory:
            write_json(directory/'manifest.json', dict(test='V3'))
            def runner(name):
                folder=directory/name
                folder.mkdir()
                r=cadence.ValidationCadenceTests().runner(folder)
                r.config.update(engine='lite', epochs=2, seed=5, minibatch=2)
                r.model=helpers.model(seed=41)
                r.optimizer=torch.optim.Adam(r.model.parameters(),lr=1e-4)
                r.controller.state_dict=lambda: {}
                r.state['pending_train']=dict(method='ppo', paths=['policy'], cursor={})
                r.state['phase']='evaluate'
                r.save=lambda: FormatExperiment.save(r)
                r.update_deadline=lambda: float('inf')
                return r
            def read(paths, **kwargs): return rows if paths == ['policy'] else rehearsal
            control=runner('control')
            random.seed(13)
            with patch('learning.experiment.read_shards',side_effect=read): control.finish_train()
            resumed=runner('resumed')
            random.seed(13)
            stopped=[False]
            def interrupted_train(*args, **kwargs):
                callback=kwargs['on_step']
                def step(cursor):
                    callback(cursor)
                    stopped[0]=True
                kwargs.update(on_step=step, deadline=1.)
                with patch('learning.ppo.time.time',side_effect=lambda: 2. if stopped[0] else 0.):
                    return train(*args, **kwargs)
            with patch('learning.experiment.read_shards',side_effect=read), patch('learning.experiment.train',side_effect=interrupted_train):
                self.assertFalse(resumed.finish_train())
            self.assertEqual(resumed.state['counters']['optimizer_steps'],0)
            saved=torch.load(resumed.directory/'latest.pt',weights_only=False)
            resumed.model.load_state_dict(saved['model'])
            resumed.optimizer.load_state_dict(saved['optimizer'])
            resumed.state=copy.deepcopy(saved['runner'])
            restore_rng(saved)
            with patch('learning.experiment.read_shards',side_effect=read):
                self.assertTrue(resumed.finish_train())
            self.assertEqual(resumed.state['counters'],control.state['counters'])
            self.assertEqual(resumed.state['counters']['decisions_seen'],22)
            self.assertEqual(resumed.state['counters']['planned_steps'], 2)
            self.assertEqual(resumed.state['counters']['committed_steps'], 2)
            self.assertEqual(resumed.state['counters']['stopped_by_kl_steps'], 0)
            self.assertEqual(ppo._digest(resumed.model),ppo._digest(control.model))
            for _ in range(2):
                finished=torch.load(resumed.directory/'latest.pt',weights_only=False)
                self.assertIsNone(finished['runner']['pending_train'])
                self.assertEqual(finished['runner']['counters'],control.state['counters'])


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
