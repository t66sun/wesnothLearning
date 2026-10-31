import unittest
from collections import Counter
from lupa import LuaRuntime
from learning.common import ROOT
import native
from tests.test_lua_contracts import initialize


class CandidateBudgetTests(unittest.TestCase):
    def select(self, candidates):
        lua = LuaRuntime(unpack_returned_tuples=True)
        select = lua.execute((ROOT/'lua/candidate_selection.lua').read_text())
        result = select.select(lua.eval(native.lua(candidates)))
        return [dict(row.items()) for row in result.values()]

    def pool(self, moves=30, recruits=20, attacks=20):
        rows = []
        for kind, count in [('move', moves), ('recruit', recruits), ('attack', attacks)]:
            for i in range(count):
                rows.append(dict(kind=kind, x=i+1, y=1, tx=i+1, ty=2,
                                 type='type'+str(i%3), weapon=1, rule=count-i,
                                 _serial=len(rows)+1))
        return rows

    def test_crowded_pool_reserves_all_three_classes(self):
        rows = self.select(self.pool())
        self.assertEqual(Counter(r['kind'] for r in rows), dict(move=12, recruit=12, attack=12))

    def test_refill_sparse_and_duplicate_pools(self):
        pool = self.pool(moves=50, recruits=2, attacks=0)
        rows = self.select(pool + pool)
        self.assertEqual(len(rows), 36)
        self.assertEqual(sum(r['kind']=='recruit' for r in rows), 2)
        self.assertEqual(len({(r['kind'],r['x']) for r in rows}), 36)
        self.assertEqual(rows, self.select(pool))
        self.assertEqual(len(self.select(self.pool(2,1,1))), 4)
        self.assertEqual(self.select([]), [])

    def test_move_attack_shares_combat_quota(self):
        pool = self.pool()
        for row in pool:
            if row['kind']=='attack' and row['x']%2:
                row.update(kind='move_attack', ex=row['x']+1, ey=2)
        counts = Counter(r['kind'] for r in self.select(pool))
        self.assertEqual(counts['attack']+counts['move_attack'], 12)
        self.assertGreater(counts['move_attack'], 0)

    def test_crowded_generator_keeps_combat_and_recruits(self):
        lua, modules = initialize()
        lua.execute("""
            local base=fixture.own[2]
            for i=3,30 do
                local u=base:clone();u.id='unit'..i;u.x=i;u.y=5
                fixture.own[#fixture.own+1]=u;fixture.visible[#fixture.visible+1]=u
            end
            wesnoth.paths.find_reach=function(u,cfg)
                return {{u.x,u.y,u.moves},{u.x,u.y+1,2}}
            end
        """)
        rows, _ = modules['candidates.lua'].generate(
            modules['observation.lua'].capture(lua.table()))
        kinds = Counter(row['kind'] for row in rows.values())
        self.assertEqual(len(rows), 37)
        self.assertEqual(kinds['end_turn'], 1)
        self.assertGreater(kinds['attack']+kinds['move_attack'], 0)
        self.assertGreater(kinds['recruit'], 0)

    def test_generator_returns_shared_bounded_pool(self):
        lua, modules = initialize()
        obs = modules['observation.lua'].capture(lua.table())
        rows, timing = modules['candidates.lua'].generate(obs)
        self.assertEqual(rows[1]['kind'], 'end_turn')
        self.assertLessEqual(len(rows), 37)
        self.assertEqual(timing['budget'], 'work-12000-v5')
        self.assertLessEqual(timing['work'], 12000)
        self.assertLessEqual(timing['reaches'], 28)
        self.assertLessEqual(timing['paths'], 8)
        self.assertLessEqual(timing['recruit_probes'], 24)
        self.assertLessEqual(timing['attack_probes'], 32)
        self.assertLessEqual(timing['move_probes'], 32)
        self.assertLessEqual(timing['predictions'], 16)


if __name__ == '__main__':
    unittest.main()
