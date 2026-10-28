"""Actual engine events are matched only against fresh public candidates."""
import unittest


def attack_frames(*, target_visible=True):
    from pathlib import Path
    from lupa import LuaRuntime, lua_type

    lua=LuaRuntime(unpack_returned_tuples=True)
    lua.globals().target_visible=target_visible
    lua.execute('''
        handlers={}; frames={}
        wesnoth={current={side=1,turn=2,event_context={x1=2,y1=3,x2=3,y2=3}},
          sides={{controller='ai'}},wml_actions={modify_ai=function() end},
          game_events={add=function(e) handlers[e.name]=e.action end},
          units={find_on_map=function(f)
            if f.x==2 or target_visible then return {{type='Spearman'}} else return {} end end},
          require=function() return {emit=function(_,f) frames[#frames+1]=f end} end}
    ''')
    capture=lua.execute(Path('lua/stock_rca_capture/main.lua').read_text())
    capture.setup(lua.table_from([1]))
    capture.context(lua.eval("{side=1,turn=2,candidates={{kind='attack',x=2,y=3,tx=3,ty=3,weapon=1}}}"))
    lua.globals().handlers['attack']()

    def plain(value):
        if lua_type(value)!='table': return value
        if len(value): return [plain(value[i]) for i in range(1,len(value)+1)]
        return {k:plain(v) for k,v in value.items()}
    return plain(lua.globals().frames)


class NativeCaptureTests(unittest.TestCase):
    def test_recruit_probe_does_not_draw_a_random_facing(self):
        from tests.v5 import helpers
        import json
        from _engine_lite import LiteEngine

        # Native 1.18.8 unit.cpp draws default_instance() when facing is absent.
        # Model that external constructor boundary while running shared candidates.
        modules = helpers.host_modules()
        modules['observation.lua'] = modules['observation.lua'].replace('\nreturn M', '''
local create=wesnoth.units.create
wesnoth.units.create=function(cfg)
    if cfg.id=='learning_probe' then assert(cfg.facing=='ne','probe drew random facing') end
    return create(cfg)
end
return M''')
        rules=helpers.rules()
        for old,new in (('Gg^Kh','Kh'),('Gg^Ch','Ch')):
            rules['terrains'][new]=dict(rules['terrains'][old],id=new)
            for unit in rules['units'].values():
                unit['movement'][new]=1;unit['defense'][new]=40
        spec=helpers.spec()
        spec['terrain']=[t.replace('Gg^Kh','Kh').replace('Gg^Ch','Ch') for t in spec['terrain']]
        engine=LiteEngine(json.dumps(rules),json.dumps(spec))
        engine.configure_host(json.dumps(modules))
        result=helpers.decision(engine)
        self.assertTrue(any(c['kind']=='recruit' for c in result['candidates']))

    def test_attack_event_becomes_a_label(self):
        from learning.stock_rca import frames_to_labels

        candidate = dict(kind='attack', x=2, y=3, tx=3, ty=3, weapon=1)
        rows, coverage = frames_to_labels(attack_frames(), side=1, candidates_fn=lambda row: row['candidates'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['actual'], candidate)
        self.assertEqual(rows[0]['choice'], 0)
        self.assertEqual(coverage['attack'], dict(matched=1, unmatched=0, ambiguous=0))

    def test_hidden_stale_and_ambiguous_actions_are_not_exact_labels(self):
        from learning.stock_rca import frames_to_labels

        candidates = [dict(kind='move', x=2, y=3, tx=3, ty=3, full=full) for full in (True, False)]
        context = dict(type='CONTEXT', id=1, side=1, turn=2, row=dict(secret='referee', candidates=candidates))
        move = dict(type='ACTION', context=1, side=1, turn=2, kind='moveto',
                    unit=dict(x=2, y=3), to=dict(x=3, y=3), visible=True)
        rows, coverage = frames_to_labels([context, move, move, dict(move, visible=False)], side=1,
                                          candidates_fn=lambda row: row['candidates'])
        self.assertEqual(coverage['moveto'], dict(matched=0, unmatched=2, ambiguous=1))
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['label_ambiguous'])
        self.assertEqual(rows[0]['choice'], -1)
        self.assertNotIn('secret', rows[0])

    def test_attack_handler_emits_engine_event_without_hidden_target(self):
        frame=attack_frames(target_visible=False)[1]
        self.assertEqual(frame['kind'], 'attack')
        self.assertFalse(frame['visible'])
        self.assertIsNone(frame.get('target'))


if __name__ == '__main__':
    unittest.main()
