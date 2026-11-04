"""Emit complete ordered public lists for the same boards under either release extension."""
import json

from tests.v5 import helpers


def main():
    for sides, fog, shroud in ((2,False,False),(2,True,True),(4,True,False)):
        board=helpers.spec(sides=sides, fog=fog, shroud=shroud, seed=31, max_turns=5)
        engine=helpers.engine(game_spec=board)
        side_ids=json.dumps(list(range(1,sides+1)))
        for i in range(16):
            view=json.loads(engine.observe(1))
            if view['finished']: break
            legal=json.loads(engine.legal_batch(side_ids))
            turn=legal[view['current_side']-1]
            assert turn==json.loads(engine.legal_actions(view['current_side']))
            action=next((a for a in turn if a['kind']==('end_turn','move','recruit','attack')[i%4]),turn[0]).copy()
            if action['kind']=='move': action['full']=True
            outcome=json.loads(engine.step(json.dumps(action)))
            print(json.dumps([sides,fog,shroud,i,legal,action,outcome],sort_keys=True,separators=(',',':')))


if __name__=='__main__':main()
