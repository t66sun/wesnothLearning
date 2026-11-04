"""The final student uses the same legal scene, candidates and committed turn memory."""
import json
import unittest

from . import helpers


class ScorePolicyTests(unittest.TestCase):
    def test_score_only_preserves_observations_and_every_consumed_write(self):
        spec = helpers.spec(max_turns=4, fog=True, shroud=True)
        full, score = (helpers.engine(game_spec=spec) for _ in range(2))
        turns = {}
        kinds = set()
        for step in range(40):
            view = json.loads(full.observe(1))
            if view['finished']:
                break
            side = view['current_side']
            original = json.loads(full.decision(side))
            compact = json.loads(score.decision(side, score_only_policy=True))
            self.assertIn('reward_raw', original)
            self.assertNotIn('reward_raw', compact)
            for field in ('side', 'turn', 'global', 'opponents', 'spatial', 'candidates', 'potential'):
                self.assertEqual(original[field], compact[field], (step, field))
            actions = compact['candidates']
            action = (next(a for a in actions if a['kind'] == 'end_turn') if step % 4 == 0 else actions[0])
            needed = turns.get(side) != compact['turn']
            old = json.loads(full.execute_candidate(json.dumps(action)))
            new = json.loads(score.execute_candidate(json.dumps(action), policy_memory_write=needed))
            for field in ('events', 'view', 'committed'):
                self.assertEqual(old[field], new[field], (step, field))
            self.assertNotIn('reward_after', new)
            self.assertNotIn('diagnostics', new)
            if needed and old['committed']:
                turns[side] = compact['turn']
                self.assertEqual(old['memory_write'], new['memory_write'])
                kinds.add('turn_end' if action['kind']=='end_turn' else 'first_action')
            else:
                self.assertNotIn('memory_write', new)
                kinds.add('omitted')
            states = [json.loads(engine.snapshot()) for engine in (full, score)]
            self.assertEqual(states[0]['game'], states[1]['game'])
            self.assertEqual(states[0]['host']['teacher_memory'], states[1]['host']['teacher_memory'])
            # The reward controller owns this label ledger. Compare every field
            # the policy can observe, including sightings, villages and terrain.
            for state in states:
                for memory in state['host']['memory'].values():
                    memory.pop('reward', None)
            self.assertEqual(states[0]['host']['memory'], states[1]['host']['memory'])
        self.assertEqual(kinds, {'turn_end', 'first_action', 'omitted'})


if __name__ == '__main__':
    unittest.main()
