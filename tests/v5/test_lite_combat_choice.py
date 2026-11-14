"""Check the opt-in combat decision through the Lite worker and executor."""
import unittest
from unittest.mock import patch

import torch

from learning.coverage import matching
from learning.features import schema
from learning.lite_host import COMBAT_ACTIONS, LiteHost, _combat_choice, teacher_candidate
from learning.lite_policy import FrozenPolicies
from learning.model import ARCHITECTURE, Policy
from learning.rowpack import compact_row, plain_row
from learning.sample import play_job
from learning.tasks import TASK_ID, reward_config
from tests.v5 import helpers
from tests.v5 import test_pipeline_contract as pipeline


class CombatChoiceTests(unittest.TestCase):
    def setUp(self):
        fixture = pipeline.LiteJobTests('test_astra_job_writes_schema_four_shard')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.student = fixture.directory/'Student'
        self.student.mkdir()
        with pipeline.catalog_patch(fixture.rules_dir):
            torch.save(dict(model=Policy('duel').state_dict(), features=schema(),
                            architecture=ARCHITECTURE, format='duel'), fixture.directory/'model.pt')

    def play(self, seat, route, requested, proposal=None):
        target = 3-seat
        units = [helpers._unit('learner', 'Archer', seat, 3, 2, leader=True),
                 helpers._unit('opponent', 'Fighter', target, 4, 2, leader=True, hp=1)]
        spec = helpers.spec(max_turns=30, units=units, fog=False)
        job = self.fixture.job(game_spec=spec, seed=7, teams=None, engine='lite',
                               output=str(self.fixture.directory/'unused-replay.json'),
                               task_id=TASK_ID, reward_config=reward_config(mode='fixed'),
                               score_only_astra=True, score_only_policy=True, combat_choice=route,
                               bots=[str(self.student) if side == seat else 'astra' for side in (1, 2)])
        del job['shard'], job['learning']
        trace, queries, remembered, first_candidates = [], [], [], []
        decide, execute, commit = LiteHost.decision, LiteHost.execute, FrozenPolicies.commit

        def decision(host, side, **kwargs):
            if kwargs.get('score_only_astra'):
                plan = decide(host, side, **kwargs)
                if side == target:
                    return {'teacher_action': {'kind': 'end_turn'}}
                queries.append(side)
                if proposal == 'same':
                    action = first_candidates[0]
                    return {'teacher_action': dict(kind='combat', x=action['x'], y=action['y'],
                            tx=action['x'], ty=action['y'], ex=action['tx'], ey=action['ty'],
                            weapon=action['weapon'])}
                if proposal == 'absent':
                    return {'teacher_action': dict(kind='combat', x=4, y=3, tx=4, ty=3,
                                                   ex=5, ey=3, weapon=99)}
                if proposal == 'noncombat':
                    return {'teacher_action': {'kind': 'end_turn'}}
                queries.append(teacher_candidate(plan['teacher_action']))
                return plan
            return decide(host, side, **kwargs)

        def choose(policy, row, side):
            actions = row['candidates']
            if row['turn'] == 1 and not first_candidates:
                if requested == 'different':
                    choices = [action for action in actions if action['kind'] == 'attack']
                    choice = actions.index(max(choices, key=lambda action: action['weapon']))
                else:
                    kind = 'end_turn' if requested == 'noncombat' else 'attack'
                    choice = next(i for i, action in enumerate(actions) if action['kind'] == kind)
                first_candidates.extend((actions[choice], actions))
            else:
                choice = next(i for i, action in enumerate(actions) if action['kind'] == 'end_turn')
            return dict(choice=choice, log_probability=0., value=0.)

        def execution(host, action, **kwargs):
            result = execute(host, action, **kwargs)
            if not kwargs.get('score_only_astra'):
                trace.append((action, result['view'], result.get('memory_write')))
            return result

        def remember(policy, side, row, result):
            commit(policy, side, row, result)
            if len(remembered) == 0:
                remembered.append((row['actual'], policy.histories[side][0]))

        with (pipeline.catalog_patch(self.fixture.rules_dir), patch.object(LiteHost, 'decision', decision),
              patch.object(LiteHost, 'execute', execution), patch.object(FrozenPolicies, 'choose', choose),
              patch.object(FrozenPolicies, 'commit', remember)):
            result = play_job(job)
        self.assertEqual(result['status'], 'complete', result.get('error'))
        self.assertTrue(result['result']['task_terminal'])
        self.assertEqual(remembered[0][0], trace[0][0])
        stored = plain_row(remembered[0][1])
        expected = plain_row(compact_row(dict(trace[0][2], turn=stored['turn'], candidates=[])))
        self.assertEqual(stored, expected)
        return result['combat_choice'], queries, trace, first_candidates

    def test_uses_the_exact_live_astra_combat_choice(self):
        for seat in (1, 2):
            with self.subTest(seat=seat):
                counts, queries, trace, (greedy, candidates) = self.play(seat, 'astra', 'different')
                self.assertEqual(queries[0], seat)
                wanted = queries[1]
                self.assertIn(wanted['kind'], COMBAT_ACTIONS)
                index = matching(candidates, wanted)
                self.assertGreaterEqual(index, 0)
                self.assertNotEqual(greedy, candidates[index])
                self.assertEqual(trace[0][0], candidates[index])
                self.assertEqual(counts['changed'], 1)

    def test_unchanged_decisions_preserve_observation_and_memory(self):
        _, _, control, (_, control_actions) = self.play(1, 'greedy', 'attack')
        for proposal in ('same', 'absent', 'noncombat'):
            with self.subTest(proposal=proposal):
                counts, queries, trace, (_, actions) = self.play(1, 'astra', 'attack', proposal)
                self.assertEqual(queries, [1])
                self.assertEqual(actions, control_actions)
                self.assertEqual(trace, control)
                self.assertEqual(counts['astra_noncombat' if proposal == 'noncombat' else proposal], 1)
        counts, queries, _, _ = self.play(1, 'astra', 'noncombat')
        self.assertEqual(queries, [])
        self.assertEqual(counts['combat'], 0)

    def test_move_attack_matches_landing_target_and_weapon(self):
        plan = dict(kind='combat', x=2, y=2, tx=2, ty=3, ex=3, ey=3, weapon=1)
        wanted = teacher_candidate(plan)
        candidates = [dict(wanted, weapon=0), dict(wanted, ty=4), dict(wanted, ex=1), wanted]
        counts = dict.fromkeys(('combat', 'queries', 'same', 'changed'), 0)
        with patch.object(LiteHost, 'decision', return_value={'teacher_action': plan}) as query:
            self.assertEqual(_combat_choice(LiteHost.__new__(LiteHost), 2, candidates, 0, 'astra', counts), 3)
        query.assert_called_once_with(2, teacher=True, generate_candidates=False, score_only_astra=True)
        self.assertEqual(counts, dict(combat=1, queries=1, same=0, changed=1))
