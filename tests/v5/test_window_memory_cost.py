import copy
import random
import unittest
from unittest.mock import patch
import torch
from learning import bc
from learning.model import Policy, batch
from tests.v5.test_replay_optimization import samples
from tests.v5.test_lite_policy_memory import FrozenMemoryTests, row
from tests.v5 import helpers


class WindowMemoryTests(unittest.TestCase):
    def test_bc_indexes_windows_not_decisions(self):
        rows=helpers.sequence_rows(turns=9, decisions_per_turn=1)
        for r in rows: r['split']='train'
        rows=rows[:8]*1+rows[8:]*10
        # Chronological rows: 8 decisions in the first window, 10 in the second.
        model=helpers.model(); optimizer=torch.optim.SGD(model.parameters(), lr=.001)
        original=bc.make_bc_sampler
        def check(representatives):
            self.assertEqual(len(representatives),2)
            sampler=original(representatives)
            draws=sampler.sample(4000,random.Random(17))
            count=sum(r is representatives[0] for r in draws)
            self.assertTrue(1800<count<2200,count)
            return sampler
        with patch.object(bc,'make_bc_sampler',side_effect=check):
            result=bc.update(model,optimizer,rows,epochs=1,minibatch=16)
        self.assertEqual(result['window_visits'],4)
        self.assertEqual(result['repeated_window_visits'],4-result['unique_windows_seen'])

    def test_detached_cache_preserves_gradients_and_reduces_encoding(self):
        torch.set_num_threads(1);torch.manual_seed(13)
        model=Policy('duel'); reference=copy.deepcopy(model)
        records=samples()[-3:-1]
        optim=torch.optim.SGD(model.parameters(),lr=.01)
        refoptim=torch.optim.SGD(reference.parameters(),lr=.01)
        for _ in range(2):
            cache={};model.zero_grad();reference.zero_grad()
            with patch.object(model,'encode_scene',wraps=model.encode_scene) as encoder:
                for record in records:
                    actual=model(*batch([record],history_cache=cache))
                    expected=reference(*batch([record]))
                    for a,b in zip(actual,expected): torch.testing.assert_close(a,b,atol=2e-6,rtol=2e-5)
                    sum(x.square().mean() for x in actual).backward()
                    sum(x.square().mean() for x in expected).backward()
                work=sum(c.args[0].shape[0] for c in encoder.call_args_list)
            self.assertLess(work,sum(1+len(r['_history']) for r in records))
            for a,b in zip(model.parameters(),reference.parameters()):
                if a.grad is not None: torch.testing.assert_close(a.grad,b.grad,atol=3e-6,rtol=3e-4)
            optim.step();refoptim.step()


class IncrementalMemoryTests(FrozenMemoryTests):
    def test_long_rollout_encodes_each_history_row_once(self):
        model=self.policy.models[1]
        with patch.object(model,'encode_scene',wraps=model.encode_scene) as encoder:
            for turn in range(1,36):
                record=row(turn)
                actual=self.policy.choose(record,1,bootstrap=True)
                expected=self.expected(record,self.policy.histories[1],bootstrap=True)
                self.assertAlmostEqual(actual,expected,places=6)
                self.policy.commit(1,record,dict(committed=True,memory_write=record))
            count=sum(c.args[0].shape[0] for c in encoder.call_args_list)
        self.assertEqual(count,35+34)

if __name__=='__main__': unittest.main()
