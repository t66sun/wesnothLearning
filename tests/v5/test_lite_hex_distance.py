"""The Lite Lua distance API must preserve odd-column geometry at bounded work."""
import unittest

from lupa.lua54 import LuaRuntime

from learning.common import ROOT


class LiteHexDistanceTests(unittest.TestCase):
    def test_distance_and_instruction_count_across_both_column_parities(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute('''
            __bridge=function(op) assert(op=='rules');return {units={},terrains={}} end
            __clock_ms=function() return 0 end
            __module_sources={}
        ''')
        lua.execute((ROOT/'engine_lite/lua/host.lua').read_text(encoding='utf-8'))
        ticks, cube_ticks = lua.execute('''
            local function cube(x,y,tx,ty)
                local q=x-1;local r=y-1-math.floor(q/2)
                local tq=tx-1;local tr=ty-1-math.floor(tq/2)
                return math.max(math.abs(q-tq),math.abs(r-tr),math.abs(q+r-tq-tr))
            end
            local dist=wesnoth.map.distance_between
            for x=-6,7 do for y=-6,7 do for tx=-6,7 do for ty=-6,7 do
                assert(dist(x,y,tx,ty)==cube(x,y,tx,ty))
            end end end end
            assert(dist(-100001,100003,70000,-80000)==cube(-100001,100003,70000,-80000))
            local function measure(f)
                local ticks=0;local sum=0
                debug.sethook(function() ticks=ticks+1 end,'',1000)
                for x=-9,10 do for y=-9,10 do for tx=-9,10 do for ty=-9,10 do
                    sum=sum+f(x,y,tx,ty)
                end end end end
                debug.sethook()
                return ticks,sum
            end
            local work,actual=measure(dist);local reference,wanted=measure(cube)
            assert(actual==wanted)
            return work,reference
        ''')
        self.assertLess(ticks, .8*cube_ticks, (ticks, cube_ticks))


if __name__ == '__main__':
    unittest.main()
