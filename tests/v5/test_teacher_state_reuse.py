"""Exercise real Rust/Lua teacher queries across JSON restore and reset."""
import json
import unittest

from learning.adapters import LiteAdapter
from . import helpers


class TeacherStateReuseTests(unittest.TestCase):
    def test_teacher_query_survives_json_snapshot_round_trip(self):
        for teams in (('1','2','3','4'),('A','B','A','B')):
            with self.subTest(teams=teams):
                spec=helpers.spec(sides=4,fog=False)
                for side,team in zip(spec['sides'],teams):
                    side['team']=team;side['gold']=0
                engine=helpers.engine(game_spec=spec)
                before=json.loads(engine.decision(1, True))
                snapshot=engine.snapshot()
                engine.restore(snapshot)
                after=json.loads(engine.decision(1, True))
                self.assertEqual(after['teacher_action'],before['teacher_action'])
                self.assertEqual(after['global'],before['global'])
                self.assertEqual(json.loads(engine.snapshot())['game'],json.loads(snapshot)['game'])
                # The restored tables must also remain serializable and reusable.
                engine.restore(engine.snapshot())
                again=json.loads(engine.decision(1, True))
                self.assertEqual(again['teacher_action'],before['teacher_action'])

    def test_adapter_reset_reuses_configured_host_once(self):
        original=helpers.spec(sides=4,fog=False)
        adapter=LiteAdapter.__new__(LiteAdapter)
        adapter.core=helpers.engine(game_spec=original)
        adapter.modules=helpers.host_modules()
        adapter.decision(1,teacher=True)
        changed=helpers.spec(sides=4,fog=False,seed=31)
        for side in changed['sides']:side['gold']=0
        adapter.reset(changed)
        actual=adapter.decision(1,teacher=True)
        fresh=helpers.engine(game_spec=changed)
        expected=json.loads(fresh.decision(1,True))
        self.assertEqual(actual['global'],expected['global'])
        self.assertEqual(actual['teacher_action'],expected['teacher_action'])
        self.assertEqual(json.loads(adapter.core.snapshot())['game'],json.loads(fresh.snapshot())['game'])


if __name__=='__main__':unittest.main()
