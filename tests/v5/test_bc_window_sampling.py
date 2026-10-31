import random
import unittest
from unittest.mock import patch
import torch
from learning import bc
from tests.v5 import helpers


class WindowSamplingTests(unittest.TestCase):
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
