"""Actual engine events are matched only against fresh public candidates."""
import unittest


class NativeCaptureTests(unittest.TestCase):
    def test_attack_event_becomes_a_label(self):
        from learning.stock_rca import frames_to_labels

        candidate = dict(kind='attack', x=2, y=3, tx=3, ty=3, weapon=1)
        context = dict(side=1, turn=2, global_='public')
        frames = [dict(type='CONTEXT', id=7, side=1, turn=2, row=context),
                  dict(type='ACTION', context=7, side=1, turn=2, kind='attack',
                       unit=dict(x=2, y=3), target=dict(x=3, y=3), weapon=1, visible=True)]
        rows, coverage = frames_to_labels(frames, side=1, candidates_fn=lambda row: [candidate])
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
        from pathlib import Path
        from lupa import LuaRuntime

        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute('''
            handlers={}; frames={}
            wesnoth={current={side=1,turn=2,event_context={x1=2,y1=3,x2=3,y2=3}},
              sides={{controller='ai'}},wml_actions={modify_ai=function() end},
              game_events={add=function(e) handlers[e.name]=e.action end},
              units={find_on_map=function(f) if f.x==2 then return {{type='Spearman'}} else return {} end end},
              require=function() return {emit=function(_,f) frames[#frames+1]=f end} end}
        ''')
        capture = lua.execute(Path('lua/stock_rca_capture/main.lua').read_text())
        capture.setup(lua.table_from([1]))
        lua.globals().handlers['attack']()
        frame = lua.globals().frames[1]
        self.assertEqual(frame['kind'], 'attack')
        self.assertFalse(frame['visible'])
        self.assertIsNone(frame['target'])


if __name__ == '__main__':
    unittest.main()
