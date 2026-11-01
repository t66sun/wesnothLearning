"""Bound interpreter work at the public forward interface, independent of host load."""
import unittest

import torch
from lupa.lua54 import LuaRuntime

from learning.common import ROOT
from learning.export import compact_lua, lua_parameters
from learning.model import Policy
from tests.profile_lua_inference import dense_decision


class LuaInferenceWorkTests(unittest.TestCase):
    def test_dense_native_forward_instruction_budget(self):
        row, _ = dense_decision(ROOT / 'verification/bc_root_20261101/native_v8/games', 'ffa4')
        self.assertEqual(len(row['spatial']['entities']), 30)
        torch.manual_seed(0)
        lua = LuaRuntime(unpack_returned_tuples=True)
        network = lua.execute((ROOT / 'lua/relational.lua').read_text(encoding='utf-8'))
        weights = lua.eval(compact_lua(lua_parameters(Policy('ffa4'))))
        inputs = [lua.table_from(row[key], recursive=True)
                  for key in ('global', 'opponents', 'candidates', 'spatial')]
        lua.execute("ticks=0; debug.sethook(function() ticks=ticks+1 end, '', 10000)")
        scores, _, _ = network.forward(weights, *inputs, lua.table(), row['turn'])
        lua.execute('debug.sethook()')
        self.assertEqual(len(scores), 37)
        # Frozen 30-entity, 37-candidate input; baseline uses over 90 M instructions.
        self.assertLess(lua.globals().ticks * 10000, 70_000_000)


if __name__ == '__main__':
    unittest.main()
