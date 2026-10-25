"""V4: cancelled logical BC batches replay the same sampler future."""
import random
import unittest
from unittest.mock import patch

import torch

from learning import bc
from learning.data import BCSampler, split
from learning.ppo import _digest
from learning.train import checkpoint, restore_rng
from tests.v5 import helpers


class BcCancelRngTests(unittest.TestCase):
    def assert_nested_equal(self, a, b):
        if isinstance(a, torch.Tensor): self.assertTrue(torch.equal(a,b))
        elif isinstance(a, dict):
            self.assertEqual(a.keys(),b.keys())
            for key in a: self.assert_nested_equal(a[key],b[key])
        elif isinstance(a, (tuple,list)):
            self.assertEqual(len(a),len(b))
            for x,y in zip(a,b): self.assert_nested_equal(x,y)
        else: self.assertEqual(a,b)

    def test_cancel_at_each_batch_boundary_restores_sampling_and_exact_future(self):
        rows=helpers.sequence_rows(turns=1,decisions_per_turn=2,game_family='family-1')
        for row in rows: row['split']=split(row['game_family'])
        sampled=[]
        original=BCSampler.sample
        def sample(sampler,*args,**kwargs):
            result=original(sampler,*args,**kwargs)
            sampled.append([(r['game_id'],r['side'],r['turn'],r['decision']) for r in result])
            return result
        def setup():
            model=helpers.model(seed=73)
            optimizer=torch.optim.Adam(model.parameters(),lr=1e-3)
            random.seed(125)
            return model,optimizer
        control,control_optimizer=setup()
        with patch.object(BCSampler,'sample',sample):
            bc.update(control,control_optimizer,rows,epochs=1,minibatch=1)
        expected_ids=sampled.pop()
        expected_rng=random.getstate()
        for cutoff in (2,3,10):
            with self.subTest(clock_call=cutoff), helpers.temporary_directory() as directory:
                model,optimizer=setup()
                before_rng=random.getstate()
                before_weights=_digest(model)
                calls=[0]
                def clock():
                    calls[0]+=1
                    return 2. if calls[0]>=cutoff else 0.
                with patch.object(BCSampler,'sample',sample), patch('learning.bc.time.time',side_effect=clock):
                    stopped=bc.update(model,optimizer,rows,epochs=1,minibatch=1,deadline=1.)
                self.assertTrue(stopped['interrupted'])
                self.assertEqual(stopped['updates'],0)
                self.assertEqual(_digest(model),before_weights)
                self.assertEqual(optimizer.state_dict()['state'],{})
                self.assertTrue(all(p.grad is None or not torch.count_nonzero(p.grad) for p in model.parameters()))
                self.assertEqual(random.getstate(),before_rng)
                self.assertEqual(sampled.pop(),expected_ids)
                checkpoint(directory/'state.pt',model,optimizer)
                saved=torch.load(directory/'state.pt',weights_only=False)
                resumed,resumed_optimizer=setup()
                resumed.load_state_dict(saved['model'])
                resumed_optimizer.load_state_dict(saved['optimizer'])
                restore_rng(saved)
                with patch.object(BCSampler,'sample',sample):
                    result=bc.update(resumed,resumed_optimizer,rows,epochs=1,minibatch=1)
                self.assertEqual(result['updates'],1)
                self.assertEqual(sampled.pop(),expected_ids)
                self.assertEqual(_digest(resumed),_digest(control))
                self.assert_nested_equal(resumed_optimizer.state_dict(),control_optimizer.state_dict())
                self.assertEqual(random.getstate(),expected_rng)


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
