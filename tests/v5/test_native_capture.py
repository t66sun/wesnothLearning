"""Actual engine events are matched only against fresh public candidates."""
import unittest


def lua_run(actions=('attack',), target_visible=True, weapon=None, attacks=()):
    """Run engine events through the real capture module on stubbed host modules."""
    from pathlib import Path
    from lupa import LuaRuntime, lua_type

    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().target_visible = target_visible
    lua.globals().attacks = lua.table_from([lua.table_from(dict(a)) for a in attacks])
    lua.globals().weapon = lua.table_from(dict(weapon)) if weapon is not None else None
    lua.execute('''
        handlers={}; frames={}
        wesnoth={current={side=1,turn=2,event_context={x1=2,y1=3,x2=3,y2=3}},
          sides={{controller='ai'}},wml_actions={modify_ai=function() end},
          game_events={add=function(e) handlers[e.name]=e.action end},
          units={find_on_map=function(f)
            if f.x==2 or target_visible then return {{type='Spearman',attacks=attacks}} else return {} end end},
          get_variable=function(name) if name=='weapon' then return weapon end end,
          require=function(name)
            if name:match('observation%.lua$') then return {capture=function(memory,side)
                return {side=side,global={},opponents={},spatial={},villages={}} end} end
            if name:match('candidates%.lua$') then return {
                generate=function() return {{kind='recruit',type='Spearman',x=2,y=3}},0 end,
                remember=function() end} end
            if name:match('spatial%.lua$') then return {memory_observation=function()
                return {villages={},seen={},roster={}} end} end
            if name:match('features%.lua$') then return {version='v5'} end
            if name:match('routing%.lua$') then return {select=function() return 'duel' end} end
            return {emit=function(_,f) frames[#frames+1]=f end}
          end}
    ''')
    capture = lua.execute(Path('lua/stock_rca_capture/main.lua').read_text())
    capture.setup(lua.table_from([1]))
    memory = lua.eval('{}')
    capture.context(capture.row(memory, 1), memory)
    for name in actions:
        lua.globals().handlers[name]()

    def plain(value):
        if lua_type(value) != 'table':
            return value
        if len(value):
            return [plain(value[i]) for i in range(1, len(value) + 1)]
        return {k: plain(v) for k, v in value.items()}
    return plain(lua.globals().frames)


def action_frames(frames):
    return [f for f in frames if f.get('type') == 'ACTION']


def context_frames(frames):
    return [f for f in frames if f.get('type') == 'CONTEXT']


def context(i, candidates=()):
    return dict(type='CONTEXT', id=i, side=1, turn=2, row=dict(candidates=list(candidates)))


def recruit(seq, context_id, x=5, y=6):
    return dict(type='ACTION', seq=seq, context=context_id, side=1, turn=2, kind='recruit',
                type_id='Spearman', visible=True, to=dict(x=x, y=y))


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
        rows, coverage = frames_to_labels(
            lua_run(('attack',)), side=1, candidates_fn=lambda row: [dict(candidate)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['actual'], candidate)
        self.assertEqual(rows[0]['choice'], 0)
        self.assertEqual(coverage['attack']['matched'], 1)
        self.assertEqual(coverage['attack']['unmatched'], 0)
        self.assertEqual(rows[0]['memory_write'], dict(villages={}, seen={}, roster={}))

    def test_context_precedes_the_action_it_labels(self):
        frames = lua_run(('recruit',))
        self.assertEqual([f['type'] for f in frames], ['CONTEXT', 'ACTION', 'AFTER'])
        self.assertEqual(context_frames(frames)[0]['id'], action_frames(frames)[0]['context'])

    def test_guard_event_retires_an_unused_context(self):
        frames = lua_run(('side turn',))
        guards = [f for f in frames if f.get('type') == 'INVALIDATE']
        self.assertEqual(guards, [dict(type='INVALIDATE', side=1, context=1, event='side turn')])
        from learning.stock_rca import frames_to_labels

        stale = frames + [recruit(1, 1)]
        rows, coverage = frames_to_labels(stale, side=1, candidates_fn=lambda row: row['candidates'])
        self.assertEqual(rows, [])
        self.assertEqual(coverage['recruit']['unmatched'], 1)

    def test_recruit_burst_is_one_engine_decision(self):
        from learning.stock_rca import frames_to_labels

        candidate = dict(kind='recruit', type='Spearman', x=5, y=6)
        frames = [context(1, [candidate])] + [recruit(seq, 1) for seq in (1, 2, 3)]
        rows, coverage = frames_to_labels(frames, side=1, candidates_fn=lambda row: row['candidates'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['choice'], 0)
        self.assertEqual(len(rows[0]['extra_actions']), 2)
        self.assertEqual(coverage['recruit'], dict(matched=1, unmatched=0, ambiguous=0, merged=2))

    def test_move_and_attack_share_one_decision(self):
        from learning.stock_rca import frames_to_labels

        move = dict(kind='move', x=2, y=3, tx=3, ty=3)
        strike = dict(kind='move_attack', x=2, y=3, tx=3, ty=3, ex=4, ey=3)
        frames = [
            context(1, [move]),
            dict(type='ACTION', seq=1, context=1, side=1, turn=2, kind='moveto',
                 unit=dict(x=2, y=3), to=dict(x=3, y=3), visible=True),
            dict(type='ACTION', seq=2, context=1, side=1, turn=2, kind='attack',
                 unit=dict(x=3, y=3), target=dict(x=4, y=3), visible=True),
        ]
        rows, coverage = frames_to_labels(frames, side=1, candidates_fn=lambda row: [move, strike])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['choice'], 1)
        self.assertEqual(coverage['attack'], dict(matched=1, unmatched=0, ambiguous=0, merged=0))
        self.assertEqual(coverage['moveto']['merged'], 1)

    def test_stale_context_cannot_label_a_later_action(self):
        from learning.stock_rca import frames_to_labels

        candidate = dict(kind='recruit', type='Spearman', x=5, y=6)
        frames = [context(1, [candidate]), context(2, [candidate]), recruit(1, 1), recruit(2, 2)]
        rows, coverage = frames_to_labels(frames, side=1, candidates_fn=lambda row: row['candidates'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['capture_context'], 2)
        self.assertEqual(coverage['recruit']['matched'], 1)
        self.assertEqual(coverage['recruit']['unmatched'], 1)

    def test_hidden_and_stale_actions_are_not_exact_labels(self):
        from learning.stock_rca import frames_to_labels

        candidates = [dict(kind='move', x=2, y=3, tx=3, ty=3, full=full) for full in (True, False)]
        move = dict(type='ACTION', context=1, side=1, turn=2, kind='moveto',
                    unit=dict(x=2, y=3), to=dict(x=3, y=3), visible=True)
        frames = [dict(context(1, candidates), row=dict(secret='referee', candidates=candidates)),
                  move, context(2, candidates), dict(move, context=2, visible=False)]
        rows, coverage = frames_to_labels(frames, side=1, candidates_fn=lambda row: row['candidates'])
        self.assertEqual(coverage['moveto'], dict(matched=1, unmatched=1, ambiguous=0, merged=0))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['capture_context'], 1)
        self.assertNotIn('secret', rows[0])

    def test_scoring_variants_of_one_move_are_not_ambiguous(self):
        from learning.stock_rca import frames_to_labels

        candidates = [dict(kind='move', x=2, y=3, tx=3, ty=3, used=5, full=full) for full in (True, False)]
        frames = [context(1, candidates),
                  dict(type='ACTION', seq=1, context=1, side=1, turn=2, kind='moveto',
                       unit=dict(x=2, y=3), to=dict(x=3, y=3), visible=True)]
        rows, coverage = frames_to_labels(frames, side=1, candidates_fn=lambda row: row['candidates'])
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['label_ambiguous'])
        self.assertEqual(rows[0]['choice'], 0)
        self.assertEqual(coverage['moveto'], dict(matched=1, unmatched=0, ambiguous=0, merged=0))

    def test_two_weapons_leave_one_action_ambiguous(self):
        from learning.stock_rca import frames_to_labels

        candidates = [dict(kind='attack', x=2, y=3, tx=3, ty=3, weapon=weapon) for weapon in (1, 2)]
        frame = action_frames(lua_run(('attack',)))[0]
        rows, coverage = frames_to_labels([context(1, candidates), frame], side=1,
                                          candidates_fn=lambda row: row['candidates'])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['label_ambiguous'])
        self.assertEqual(rows[0]['choice'], -1)
        self.assertEqual(coverage['attack'], dict(matched=0, unmatched=0, ambiguous=1, merged=0))

    def test_attack_names_the_weapon_the_engine_reports(self):
        from learning.stock_rca import frames_to_labels

        attacks = [dict(name='axe', type='blade', number=3, damage=7),
                   dict(name='bow', type='pierce', number=2, damage=6)]
        frame = action_frames(lua_run(('attack',), weapon=attacks[1], attacks=attacks))[0]
        self.assertEqual(frame['weapon'], 2)
        candidates = [dict(kind='attack', x=2, y=3, tx=3, ty=3, weapon=weapon) for weapon in (1, 2)]
        rows, coverage = frames_to_labels([context(1, candidates), frame], side=1,
                                          candidates_fn=lambda row: row['candidates'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['choice'], 1)
        self.assertFalse(rows[0]['label_ambiguous'])
        self.assertEqual(coverage['attack'], dict(matched=1, unmatched=0, ambiguous=0, merged=0))

    def test_stock_totals_count_decisions_not_events(self):
        from learning.sample import stock_totals

        coverage = stock_totals({'moveto': dict(matched=2, unmatched=1, ambiguous=3, merged=9),
                                 'attack': dict(matched=4, unmatched=0, ambiguous=0, merged=0)})
        self.assertEqual(coverage['move']['total'], 6)
        self.assertEqual(coverage['attack']['total'], 4)
        self.assertEqual(sum(count['total'] for count in coverage.values()), 10)

    def test_attack_handler_emits_engine_event_without_hidden_target(self):
        frame = action_frames(lua_run(('attack',), target_visible=False))[0]
        self.assertEqual(frame['kind'], 'attack')
        self.assertFalse(frame['visible'])
        self.assertIsNone(frame.get('target'))


if __name__ == '__main__':
    unittest.main()
