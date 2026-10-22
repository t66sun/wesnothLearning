"""Contract tests for the schema-4 learning core.

Every row used here comes from the real Lua capture path in ``tests/v5/helpers``;
there is no native Wesnoth data in this repository, so these are contract and
numerical-parity tests, not native/full-data acceptance tests.
"""
import copy
import gzip
import json
import math
import random
import unittest
from unittest import mock

import torch

from tests.v5 import helpers
from learning import rewards
from learning.audit import INTENT_FIELDS, audit_bc
from learning.data import make_bc_sampler, split, validate_record
from learning.export import load_model, verify_numerics
from learning.features import (ACTION, ENTITY, GEOMETRY, GLOBAL, OPPONENT,
                               SPATIAL_CHANNELS, UNIT_TYPES)
from learning.model import ARCHITECTURE, batch
from learning.rewards import (ControlMap, economy_potential, hex_neighbors,
                              RewardConfig, terminal_rewards, transition_reward)
from learning.sequences import (IndexedSequenceStore, attach_histories,
                                read_raw_shards, read_shards, training_windows)
from learning.train import checkpoint, imitation_quality, restore_rng, train


def _rows(turns=2, decisions_per_turn=2, **kwargs):
    return helpers.sequence_rows(turns=turns, decisions_per_turn=decisions_per_turn, **kwargs)


def _split_rows(rows):
    for row in rows:
        row['split'] = split(row['game_family'])
    return rows


def _local_width():
    return 19 * len(SPATIAL_CHANNELS)


class PolicyArchitectureTests(unittest.TestCase):
    def test_architecture_constants(self):
        model = helpers.model()
        self.assertEqual(ARCHITECTURE['id'], 'relational_v5')
        self.assertEqual(ARCHITECTURE['unit_embedding'], 16)
        self.assertEqual(ARCHITECTURE['entity_hidden'], 64)
        self.assertEqual(ARCHITECTURE['entity_layers'], 2)
        self.assertEqual(ARCHITECTURE['heads'], 4)
        self.assertEqual(ARCHITECTURE['ffn'], 128)
        self.assertEqual(ARCHITECTURE['spatial_size'], 16)
        self.assertEqual(ARCHITECTURE['spatial_channels'], len(SPATIAL_CHANNELS))
        self.assertEqual(ARCHITECTURE['conv_channels'], 16)
        self.assertEqual(ARCHITECTURE['local_hexes'], 19)
        self.assertEqual(ARCHITECTURE['local_hidden'], 32)
        self.assertEqual(ARCHITECTURE['gru'], 128)
        self.assertEqual(ARCHITECTURE['memory_slots'], 32)
        self.assertEqual(ARCHITECTURE['memory_hidden'], 64)
        self.assertEqual(ARCHITECTURE['scorer_hidden'], [512, 256, 128])
        self.assertEqual(ARCHITECTURE['value_hidden'], 128)
        self.assertEqual(ARCHITECTURE['replay_turns'], 8)
        self.assertEqual(model.unit_embedding.embedding_dim, 16)
        self.assertEqual(model.unit_embedding.num_embeddings, len(UNIT_TYPES))
        self.assertEqual(model.scene_width, len(GLOBAL) + 32 + 64 + 16)
        with self.assertRaises(ValueError):
            helpers.model(format_name='schema-3')

    def test_forward_logits_mask_and_value(self):
        model = helpers.model()
        row = _rows(turns=1, decisions_per_turn=1)[0]
        tensors = batch([row])
        with torch.no_grad():
            logits, values = model(*tensors)
        self.assertEqual(logits.shape, (1, len(row['candidates'])))
        self.assertTrue(torch.isfinite(logits).all())
        mask = tensors[4].clone()
        mask[0, 1] = False
        with torch.no_grad():
            masked, _ = model(tensors[0], tensors[1], tensors[2], tensors[3], mask, tensors[5])
        self.assertEqual(float(masked[0, 1]), -math.inf)
        self.assertTrue(torch.isfinite(masked[0, 2:]).all())

    def test_forward_value_has_batch_channel(self):
        """Training indexes `values[valid]` with a 1-D reward mask, so the
        public forward value contract is one scalar per batch row ``(B,)``.
        """
        model = helpers.model()
        row = _rows(turns=1, decisions_per_turn=1)[0]
        with torch.no_grad():
            _, values = model(*batch([row]))
        self.assertEqual(values.shape, (1,))

    def test_unit_embedding_indexes_entity_types(self):
        model = helpers.model()
        row = _rows(turns=1, decisions_per_turn=1)[0]
        _, _, _, _, _, payload = batch([row])
        expected = [entity['type_index'] for entity in row['spatial']['entities']]
        self.assertEqual(payload['types'][0, :len(expected)].tolist(), expected)
        embedded = model.unit_embedding(payload['types'])
        self.assertTrue(torch.equal(embedded, model.unit_embedding.weight[payload['types']]))

    def test_attended_and_direct_actor_paths_are_identical(self):
        # Make the entity stack an identity so attended scene tokens equal the
        # direct projection of the same features/type. Then both gather paths
        # must produce identical logits.
        model = helpers.model()
        for block in model.entities:
            for parameter in block.parameters():
                parameter.data.zero_()
        row = copy.deepcopy(_rows(turns=1, decisions_per_turn=1)[0])
        row['candidates'] = [c for c in row['candidates'] if c.get('actor')]
        row['choice'] = 0
        g, opponents, actions, opponent_mask, action_mask, payload = batch([row])
        direct_payload = copy.deepcopy(payload)
        direct_payload['actors_indices'].fill_(-1)
        direct_payload['actors_present'].fill_(1)
        direct_payload['actors'][:] = payload['entities'][:, 0][:, None, :]
        direct_payload['actors_types'][:] = payload['types'][:, 0][:, None]
        with torch.no_grad():
            direct, _ = model(g, opponents, actions, opponent_mask, action_mask, direct_payload)
        forced = copy.deepcopy(direct_payload)
        forced['actors_indices'].fill_(0)
        with torch.no_grad():
            attended, _ = model(g, opponents, actions, opponent_mask, action_mask, forced)
        torch.testing.assert_close(attended, direct, atol=1e-6, rtol=1e-6)

    def test_entity_mask_removes_padded_entities(self):
        model = helpers.model()
        row = _rows(turns=1, decisions_per_turn=1)[0]
        g, opponents, actions, opponent_mask, action_mask, payload = batch([row])
        extra = copy.deepcopy(payload)
        real = len(row['spatial']['entities'])
        extra['entities'][0, real:real + 4] = 1e3
        extra['types'][0, real:real + 4] = 0
        extra['entity_mask'][0, real:real + 4] = False
        with torch.no_grad():
            base_scene, _ = model.encode_scene(g, opponents, opponent_mask, payload)
            extra_scene, _ = model.encode_scene(g, opponents, opponent_mask, extra)
        torch.testing.assert_close(base_scene, extra_scene, atol=1e-6, rtol=1e-6)

    def test_single_and_128_candidates_forward(self):
        model = helpers.model()
        row = _rows(turns=1, decisions_per_turn=1)[0]
        one = copy.deepcopy(row)
        one['candidates'] = one['candidates'][:1]
        one['choice'] = 0
        with torch.no_grad():
            logits, _ = model(*batch([one]))
        self.assertEqual(logits.shape, (1, 1))
        self.assertTrue(torch.isfinite(logits).all())
        many = copy.deepcopy(row)
        helpers.pad_candidates(many, 128)
        with torch.no_grad():
            logits, _ = model(*batch([many]))
        self.assertEqual(logits.shape, (1, 128))
        self.assertTrue(torch.isfinite(logits).all())

    def test_local_and_geometry_width_enforced(self):
        row = _rows(turns=1, decisions_per_turn=1)[0]
        self.assertEqual(len(row['candidates'][0]['local']), _local_width())
        bad = copy.deepcopy(row)
        bad['candidates'][0]['local'] = bad['candidates'][0]['local'][:-1]
        with self.assertRaisesRegex(ValueError, 'geometry'):
            validate_record(bad, 'duel')
        bad = copy.deepcopy(row)
        bad['candidates'][0].pop('geometry')
        with self.assertRaisesRegex(ValueError, 'geometry'):
            validate_record(bad, 'duel')


class BatchTests(unittest.TestCase):
    def test_batch_shapes_and_provenance(self):
        rows = helpers.attach(_rows(turns=2, decisions_per_turn=2))
        g, opponents, actions, opponent_mask, action_mask, payload = batch(rows)
        b = len(rows)
        a = max(len(row['candidates']) for row in rows)
        self.assertEqual(tuple(g.shape), (b, len(GLOBAL)))
        self.assertEqual(tuple(opponents.shape), (b, 1, len(OPPONENT)))
        self.assertEqual(tuple(actions.shape), (b, a, len(ACTION)))
        self.assertEqual(tuple(payload['board'].shape), (b, 9, 16, 16))
        self.assertEqual(tuple(payload['local'].shape), (b, a, _local_width()))
        self.assertEqual(tuple(payload['geometry'].shape), (b, a, len(GEOMETRY)))
        self.assertEqual(tuple(payload['entities'].shape), (b, 128, len(ENTITY)))
        self.assertEqual(tuple(payload['entity_mask'].shape), (b, 128))
        self.assertEqual(payload['turns'], [row['turn'] for row in rows])
        self.assertEqual(payload['histories'], [row['_history'] for row in rows])
        self.assertTrue(opponent_mask.all())
        for i, row in enumerate(rows):
            self.assertEqual(int(payload['entity_mask'][i].sum()), len(row['spatial']['entities']))
            actors = sum(1 for candidate in row['candidates'] if candidate.get('actor'))
            targets = sum(1 for candidate in row['candidates'] if candidate.get('target'))
            self.assertEqual(int(payload['actors_present'][i].sum()), actors)
            self.assertEqual(int(payload['targets_present'][i].sum()), targets)
            for j, candidate in enumerate(row['candidates']):
                if candidate.get('actor') and candidate['actor']['id'] not in {
                        entity['id'] for entity in row['spatial']['entities']}:
                    self.assertEqual(int(payload['actors_indices'][i, j]), -1)

    def test_single_and_batched_forward_agree_and_padding_is_masked(self):
        rows = helpers.attach(_rows(turns=2, decisions_per_turn=2))
        first = rows[0]
        second = copy.deepcopy(rows[1])
        second['candidates'] = second['candidates'][:30]
        second['choice'] = min(second['choice'], 29)
        model = helpers.model()
        with torch.no_grad():
            single_logits, single_value = model(*batch([first]))
            logits, values = model(*batch([first, second]))
        torch.testing.assert_close(logits[0, :single_logits.shape[1]], single_logits[0],
                                   atol=1e-5, rtol=1e-5)
        torch.testing.assert_close(values[0], single_value[0], atol=1e-5, rtol=1e-5)
        self.assertTrue(torch.isinf(logits[1, 30:]).all())
        self.assertTrue((logits[1, 30:] < 0).all())
        self.assertTrue(torch.isfinite(logits[1, :30]).all())


class RewardTests(unittest.TestCase):
    def test_terminal_rewards_duel_draw_team_and_ffa(self):
        two = {'bots': ['a', 'b']}
        self.assertEqual(terminal_rewards(dict(two, winner=1)), {1: 1., 2: -1.})
        self.assertEqual(terminal_rewards(dict(two, winner=0)), {1: 0., 2: 0.})
        team = {'bots': list(range(4)), 'teams': [1, 2, 1, 2], 'winning_team': 1}
        self.assertEqual(terminal_rewards(team), {1: 1., 2: -1., 3: 1., 4: -1.})
        team['winning_team'] = 0
        self.assertEqual(terminal_rewards(team), {1: 0., 2: 0., 3: 0., 4: 0.})
        ffa = {'bots': list(range(4)), 'rank_points': {1: 3, 2: 1, 3: 0, 4: 0}}
        scores = terminal_rewards(ffa)
        self.assertAlmostEqual(sum(scores.values()) / 4, 0.)
        self.assertAlmostEqual(max(abs(value) for value in scores.values()), 1.)
        self.assertEqual(scores, {1: 1., 2: 0., 3: -.5, 4: -.5})
        three = {'bots': list(range(3)), 'ranks': {1: 2, 2: 1, 3: 0}}
        self.assertEqual(terminal_rewards(three), {1: 1., 2: 0., 3: -1.})
        with self.assertRaisesRegex(ValueError, 'rank points'):
            terminal_rewards({'bots': list(range(4))})

    def test_economy_potential_formula_team_average_and_normalization(self):
        one = {'gold': 100., 'units': [], 'villages': 0}
        self.assertEqual(economy_potential(1, {1: one, 2: copy.deepcopy(one)}), 0.)
        sides = {1: {'gold': 100., 'units': [], 'villages': 0},
                 2: {'gold': 0., 'units': [], 'villages': 0},
                 3: {'gold': 200., 'units': [], 'villages': 0},
                 4: {'gold': 0., 'units': [], 'villages': 0}}
        teams = {1: 'A', 2: 'B', 3: 'A', 4: 'B'}
        value = economy_potential(1, sides, teams)
        self.assertAlmostEqual(value, 150. / 350.)
        negative = {1: {'gold': -50., 'units': [], 'villages': 0},
                    2: {'gold': 50., 'units': [], 'villages': 0}}
        self.assertAlmostEqual(economy_potential(1, negative), -100. / 300.)
        army = {'gold': 0., 'units': [{'cost': 10., 'hp': 5., 'max_hp': 10.}],
                'villages': 1}
        self.assertAlmostEqual(economy_potential(1, {1: army, 2: {'gold': 0., 'units': [], 'villages': 0}}),
                               25. / 225.)
        before = {1: {'gold': 114., 'units': [], 'villages': 0},
                  2: {'gold': 100., 'units': [], 'villages': 0}}
        after = {1: {'gold': 100., 'units': [{'cost': 14., 'hp': 10., 'max_hp': 10.}],
                     'villages': 0},
                 2: {'gold': 100., 'units': [], 'villages': 0}}
        self.assertAlmostEqual(economy_potential(1, before), economy_potential(1, after))

    def test_transition_reward_discount_terminal_and_exploration(self):
        config = helpers.config(economy=.1, control=.1, explore=.1, gamma=.9)
        now = {'economy': .2, 'control': .1, 'explored': .2}
        following = {'economy': .4, 'control': .3, 'explored': .5}
        total, pieces = transition_reward(now, following, config, delta_turn=2, components=True)
        self.assertAlmostEqual(pieces['economy'], .1 * (.81 * .4 - .2))
        self.assertAlmostEqual(pieces['control'], .1 * (.81 * .3 - .1))
        self.assertAlmostEqual(pieces['explore'], .1 * .3)
        self.assertAlmostEqual(total, sum(pieces.values()))
        same = transition_reward(now, following, config, delta_turn=0, components=True)[1]
        self.assertAlmostEqual(same['economy'], .1 * (.4 - .2))
        terminal = transition_reward(now, following, config, terminal=True,
                                     terminal_reward=.5, delta_turn=2, components=True)[1]
        self.assertAlmostEqual(terminal['terminal'], .5)
        self.assertAlmostEqual(terminal['economy'], -.1 * .2)
        self.assertAlmostEqual(terminal['control'], -.1 * .1)
        self.assertAlmostEqual(terminal['explore'], .1 * .3)
        self.assertAlmostEqual(transition_reward(
            {'economy': 0., 'control': 0., 'explored': .9},
            {'economy': 0., 'control': 0., 'explored': 1.}, config), .01)
        with self.assertRaisesRegex(ValueError, 'negative own-turn span'):
            transition_reward(now, following, config, delta_turn=-1)
        with self.assertRaisesRegex(ValueError, 'invalid discount'):
            transition_reward(now, following, config, gamma=0.)
        with self.assertRaisesRegex(ValueError, 'nonfinite terminal'):
            transition_reward(now, following, config, terminal_reward=math.inf)
        with self.assertRaisesRegex(ValueError, 'nonfinite reward potential'):
            transition_reward({'economy': math.nan, 'control': 0., 'explored': 0.},
                              following, config)
        with self.assertRaisesRegex(ValueError, 'regressed'):
            transition_reward({'economy': 0., 'control': 0., 'explored': .5},
                              {'economy': 0., 'control': 0., 'explored': .4}, config)
        with self.assertRaisesRegex(ValueError, 'cumulative exploration'):
            transition_reward({'economy': 0., 'control': 0., 'explored': 0.},
                              {'economy': 0., 'control': 0., 'explored': 1.2}, config)

    def test_control_map_neighbors_parity_and_lua_contract(self):
        lua_source = (helpers.ROOT / 'lua/rewards.lua').read_text(encoding='utf-8')
        from lupa import LuaRuntime
        lua = LuaRuntime(unpack_returned_tuples=True)
        module = lua.execute(lua_source.rsplit('return M', 1)[0] +
                             'M.neighbors=neighbors\nreturn M')
        for x in (3, 4, 5, 6):
            cell = (x, 3)
            neighbors = set(hex_neighbors(cell))
            self.assertNotIn(cell, neighbors)
            self.assertEqual(neighbors, {(a, b) for a in range(1, 10) for b in range(1, 10)
                                         if helpers.cube_distance(cell, (a, b)) == 1})
            lua_set = {(module.neighbors(x, 3)[i][1], module.neighbors(x, 3)[i][2])
                       for i in range(1, len(module.neighbors(x, 3)) + 1)}
            self.assertEqual(neighbors, lua_set)
            for other in neighbors:
                self.assertIn(cell, set(hex_neighbors(other)))
        # 1-based odd-q: odd columns offset the x-1/x+1 rows upward.
        self.assertEqual(set(hex_neighbors((3, 3))),
                         {(3, 2), (3, 4), (2, 2), (2, 3), (4, 2), (4, 3)})
        self.assertEqual(set(hex_neighbors((4, 3))),
                         {(4, 2), (4, 4), (3, 3), (3, 4), (5, 3), (5, 4)})

    def test_control_map_known_cells_cache_and_bounds(self):
        control = ControlMap()
        costs = {'inf': {(1, 1): 1., (1, 2): 1., (1, 4): 1.}}
        own = [{'cell': (1, 1), 'class': 'inf', 'strength': 1., 'age': 0}]
        weights = {(1, 2): .5, (1, 4): .5}
        value = control.potential(costs, own, [], weights, 1., turn=1, view_version=10)
        self.assertAlmostEqual(value, .75)
        self.assertEqual({key[0] for key in control.cache}, {10})
        again = control.potential(costs, own, [], weights, 1., turn=1, view_version=11)
        self.assertAlmostEqual(again, value)
        self.assertEqual({key[0] for key in control.cache}, {11})
        control.potential(costs, own, [], weights, 1., turn=2, view_version=12)
        self.assertEqual({key[0] for key in control.cache}, {12})
        hidden = control.potential({'inf': {(1, 1): 1.}}, [{'cell': (9, 9), 'class': 'inf'}],
                                   [], {(1, 1): 1.}, 1., turn=2, view_version=12)
        self.assertAlmostEqual(hidden, .5)
        with self.assertRaisesRegex(ValueError, 'at most four'):
            control.potential({str(i): {(1, 1): 1.} for i in range(5)}, [], [], {}, 1.,
                              turn=3, view_version=13)
        with self.assertRaisesRegex(ValueError, 'normalization'):
            control.potential({'inf': {(1, 1): 1.}}, [], [], {}, 0., turn=3, view_version=13)
        with self.assertRaisesRegex(ValueError, 'normalization'):
            control.potential({'inf': {(1, 1): 1.}}, [], [], {(1, 1): 2.}, 1., turn=3,
                              view_version=13)
        for strength in (0., .25, 1.):
            for age in (0, 10):
                value = control.potential(costs, [{'cell': (1, 1), 'class': 'inf',
                                                   'strength': strength, 'age': age}],
                                          [], weights, 1., turn=4, view_version=14)
                self.assertGreaterEqual(value, 0.)
                self.assertLessEqual(value, 1.)

    def test_gae_hand_computed_and_truncated_tail(self):
        from learning.data import advantages
        config = helpers.config(economy=.1, control=.1, explore=0., gamma=1., gae_lambda=.5)
        base = helpers.synthetic_decision_row(seed=4)

        def recorded(turn, value, reward, raw):
            row = copy.deepcopy(base)
            row.update(turn=turn, value=value, reward=reward, reward_raw=raw,
                       reward_config=config, truncated=False)
            return row

        rows = [recorded(1, .5, 5., {'economy': 0., 'control': 0., 'explored': 0.}),
                recorded(2, .4, 5., {'economy': .1, 'control': 0., 'explored': 0.}),
                recorded(3, .3, 1., {'economy': .2, 'control': 0., 'explored': 0.})]
        adv, returns = advantages(rows)
        for actual, expected in zip(adv, [.035, .25, .68]):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(returns, [.535, .65, .98]):
            self.assertAlmostEqual(actual, expected)
        last = copy.deepcopy(rows[-1])
        last.update(truncated=True, bootstrap_value=.7, bootstrap_turn=4,
                    bootstrap_raw={'economy': .3, 'control': 0., 'explored': 0.})
        truncated_adv, truncated_returns = advantages([rows[0], rows[1], last])
        self.assertEqual(len(truncated_adv), 3)
        self.assertTrue(all(math.isfinite(value) for value in truncated_adv + truncated_returns))
        missing = copy.deepcopy(rows[-1])
        missing['truncated'] = True
        with self.assertRaisesRegex(ValueError, 'bootstrap value'):
            advantages([rows[0], missing])
        # Two games are returned in input order, grouped independently.
        left = [recorded(1, .5, 1., {'economy': 0., 'control': 0., 'explored': 0.}),
                recorded(2, .0, 1., {'economy': 0., 'control': 0., 'explored': 0.})]
        right = [recorded(1, .2, 1., {'economy': 0., 'control': 0., 'explored': 0.})]
        for row in left:
            row['game_id'] = 'g-left'
        for row in right:
            row['game_id'] = 'g-right'
        two_adv, _ = advantages(left + right)
        self.assertEqual(len(two_adv), 3)
        self.assertAlmostEqual(two_adv[-1], 1. - right[0]['value'])


class SequenceTests(unittest.TestCase):
    def test_attach_history_order_suffix_and_commit_rules(self):
        rows = _rows(turns=3, decisions_per_turn=1)
        attached = attach_histories(rows)
        self.assertEqual([len(row['_history']) for row in attached], [0, 1, 2])
        with self.assertRaisesRegex(ValueError, 'chronological'):
            attach_histories([attached[2], attached[0]])
        with self.assertRaisesRegex(ValueError, 'complete raw prefix'):
            attach_histories([rows[1]])
        starts = copy.deepcopy(rows[1])
        starts['sequence_start'] = True
        accepted = attach_histories([starts])
        self.assertEqual(accepted[0]['_history'], [])
        refused = copy.deepcopy(rows[0])
        refused['sequence_start'] = False
        with self.assertRaisesRegex(ValueError, 'complete raw prefix'):
            attach_histories([refused])
        incomplete = copy.deepcopy(rows[0])
        incomplete['_sequence_complete'] = False
        with self.assertRaisesRegex(ValueError, 'complete raw prefix'):
            attach_histories([incomplete])

    def test_committed_false_does_not_advance_memory(self):
        rows = _rows(turns=2, decisions_per_turn=1)
        rows[0]['committed'] = False
        attached = attach_histories(rows)
        self.assertEqual([len(row['_history']) for row in attached], [0, 0])
        normal = attach_histories(_rows(turns=2, decisions_per_turn=2))
        self.assertEqual([len(row['_history']) for row in normal], [0, 1, 1, 2])

    def test_indexed_store_write_sample_read_idempotence_and_lru(self):
        first = _split_rows(_rows(turns=3, decisions_per_turn=1))
        second = _split_rows(_rows(turns=2, decisions_per_turn=1, game_id='seq-2'))
        with helpers.temporary_directory() as directory:
            with IndexedSequenceStore(directory, cache_bytes=1) as store:
                self.assertEqual(store.write(first), 3)
                self.assertEqual(store.write(first), 3)
                self.assertEqual(len(store.index(partition='train')), 1)
                self.assertEqual([row['turn'] for row in store.iter_records()], [1, 2, 3])
                windows = store.sample_windows(1, seed=5)
                self.assertTrue(windows)
                self.assertTrue(all(row['choice'] >= 0 for row in windows[0]))
                changed = copy.deepcopy(first)
                changed[0]['global'][0] += 1.
                with self.assertRaisesRegex(ValueError, 'different raw content'):
                    store.write(changed)
                incomplete = copy.deepcopy(first)
                incomplete[0]['_sequence_complete'] = False
                with self.assertRaisesRegex(ValueError, 'incomplete'):
                    store.write(incomplete)
                crossed = copy.deepcopy(first)
                crossed[0]['split'] = 'validation'
                with self.assertRaisesRegex(ValueError, 'crosses data partitions'):
                    store.write(crossed)
                self.assertEqual(store.write(second), 2)
                index = store.index(partition='train')
                self.assertEqual(len(index), 2)
                one = store._decode(index[0]['id'])
                two = store._decode(index[1]['id'])
                one_again = store._decode(index[0]['id'])
                self.assertEqual(one, one_again)
                self.assertEqual(two, store._decode(index[1]['id']))
                self.assertEqual([len(row['_history']) for row in
                                  attach_histories(store._decode(index[0]['id']))],
                                 [0, 1, 2] if index[0]['id'] == store.index()[0]['id'] else [0, 1])

    def test_shards_attach_prefix_before_limit_and_raw_reader(self):
        rows = _split_rows(_rows(turns=3, decisions_per_turn=1))
        rows[0]['choice'] = -1
        with helpers.temporary_directory() as directory:
            path = directory / 'shard.jsonl.gz'
            with gzip.open(path, 'wt', encoding='utf-8') as stream:
                for row in rows:
                    stream.write(json.dumps(row, separators=(',', ':')) + '\n')
            selected = read_shards([str(path)], limit=1, seed=2)
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0]['turn'], 2)
            self.assertEqual([past['turn'] for past in selected[0]['_history']], [1])
            full = read_shards([str(path)])
            self.assertEqual([row['turn'] for row in full], [2, 3])
            raw = read_raw_shards([str(path)])
            self.assertEqual([row['turn'] for row in raw], [1, 2, 3])
            self.assertEqual(raw[0]['choice'], -1)
            self.assertEqual([len(row['_history']) for row in raw], [0, 1, 2])

    def test_training_windows_eight_turns_chronological_and_supervised(self):
        rows = _rows(turns=10, decisions_per_turn=2)
        windows = training_windows(attach_histories(rows), turns=8)
        self.assertEqual(len(windows), 2)
        self.assertEqual(len({row['turn'] for row in windows[0]}), 8)
        self.assertEqual({row['turn'] for row in windows[1]}, {9, 10})
        for window in windows:
            turns = [row['turn'] for row in window]
            self.assertEqual(turns, sorted(turns))
            self.assertTrue(all(row['choice'] >= 0 for row in window))
        attached = attach_histories(rows)
        attached[9]['choice'] = -1
        filtered = training_windows(attached, turns=8)
        self.assertTrue(all(row['choice'] >= 0 for window in filtered for row in window))
        self.assertTrue(all(len({row['turn'] for row in window}) == 8
                            for window in filtered[:1]))


class TrainingTests(unittest.TestCase):
    def test_ppo_policy_rehearsal_requires_explicit_opt_in(self):
        rows = _split_rows(_rows(turns=1, decisions_per_turn=2, source='policy'))
        with self.assertRaisesRegex(ValueError, 'Astra or compatible human'):
            make_bc_sampler(rows)
        sampler = make_bc_sampler(rows, allow_policy=True)
        self.assertTrue(sampler.sample(1))

    def test_checkpoint_restores_model_optimizer_and_rng_and_models_are_independent(self):
        with helpers.temporary_directory() as directory:
            path = directory / 'policy.pt'
            model = helpers.model(seed=21)
            optimizer = torch.optim.Adam(model.parameters(), lr=.0123)
            loss = sum(parameter.square().sum() for parameter in model.parameters())
            loss.backward()
            optimizer.step()
            random.seed(123)
            torch.manual_seed(456)
            checkpoint(path, model, optimizer, note='unit')
            state = torch.load(path, map_location='cpu', weights_only=False)
            self.assertEqual(state['format'], 'duel')
            self.assertEqual(state['optimizer']['param_groups'][0]['lr'], .0123)
            self.assertTrue(state['optimizer']['state'])
            loaded, loaded_state = load_model(path, 'duel')
            for name, tensor in model.state_dict().items():
                torch.testing.assert_close(loaded.state_dict()[name], tensor)
            random.random()
            torch.rand(5)
            restore_rng(loaded_state)
            self.assertEqual(random.getstate(), loaded_state['python_rng'])
            self.assertTrue(torch.equal(torch.get_rng_state(), loaded_state['torch_rng'].cpu()))
            with self.assertRaisesRegex(ValueError, 'different format'):
                load_model(path, 'ffa4')

        models = [helpers.model(seed=seed) for seed in (31, 32, 33)]
        snapshots = [{key: value.clone() for key, value in model.state_dict().items()}
                     for model in models]
        identifiers = [id(parameter) for model in models for parameter in model.parameters()]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        update = torch.optim.SGD(models[0].parameters(), lr=.1)
        models[0].unit_embedding.weight.sum().backward()
        update.step()
        for model, snapshot in zip(models[1:], snapshots[1:]):
            for key, value in model.state_dict().items():
                torch.testing.assert_close(value, snapshot[key])
        self.assertNotEqual(models[0].unit_embedding.weight.sum().item(),
                            models[1].unit_embedding.weight.sum().item())

    def _bc_rows(self):
        return _split_rows(_rows(turns=2, decisions_per_turn=2))

    def _ppo_rows(self, model=None):
        rows = _split_rows(_rows(turns=2, decisions_per_turn=2, source='policy',
                                 game_id='ppo-1', game_family='family-1'))
        for row in rows:
            row['value'] = .3
            row['reward'] = 0.
            row['reward_after'] = dict(row['reward_raw'])
            row['truncated'] = False
        rows[-1]['reward'] = 1.
        rows[-1]['reward_after'] = dict(rows[-1]['reward_raw'])
        rows = attach_histories(rows)
        if model is None:
            model = helpers.model(seed=41)
        with torch.no_grad():
            logits, _ = model(*batch(rows))
            target = torch.tensor([row['choice'] for row in rows])
            logp = torch.distributions.Categorical(logits=logits).log_prob(target)
        for row, value in zip(rows, logp.tolist()):
            row['log_probability'] = value
        return rows, logp, model

    def test_bc_train_finite_loss_and_counter(self):
        model = helpers.model(seed=51)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        result = train(model, optimizer, self._bc_rows(), method='bc', epochs=1, minibatch=4)
        self.assertGreaterEqual(result['updates'], 1)
        self.assertGreater(result['decisions_seen'], 0)
        self.assertTrue(math.isfinite(result['loss']))
        self.assertEqual(result['sequence_windows'], 1)

    def test_ppo_replay_ratio_grad_state_and_clipping(self):
        rows, logp, model = self._ppo_rows()
        with torch.no_grad():
            logits, _ = model(*batch(rows))
            target = torch.tensor([row['choice'] for row in rows])
            replay = torch.distributions.Categorical(logits=logits).log_prob(target)
        ratio = torch.exp(replay - torch.tensor([row['log_probability'] for row in rows]))
        self.assertLessEqual(abs(float(ratio.max()) - 1.), 1e-6)
        self.assertGreaterEqual(float(ratio.min()), 1. - 1e-6)
        self.assertTrue(all(parameter.grad is None for parameter in model.parameters()))
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        calls = []
        original = torch.nn.utils.clip_grad_norm_

        def wrapper(parameters, max_norm, *args, **kwargs):
            calls.append(max_norm)
            return original(parameters, max_norm, *args, **kwargs)

        with mock.patch('torch.nn.utils.clip_grad_norm_', side_effect=wrapper):
            result = train(model, optimizer, rows, method='ppo', epochs=1, minibatch=4,
                           bc_records=self._bc_rows())
        self.assertEqual(result['updates'], 1)
        self.assertEqual(calls, [.5])
        self.assertTrue(math.isfinite(result['loss']))

    def test_ppo_kl_stop_is_a_no_update(self):
        rows, _, model = self._ppo_rows()
        for row in rows:
            row['log_probability'] -= .5
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        before = {key: value.clone() for key, value in model.state_dict().items()}
        result = train(model, optimizer, rows, method='ppo', epochs=1, minibatch=4,
                       bc_records=self._bc_rows())
        self.assertTrue(result['kl_stopped'])
        self.assertFalse(result['interrupted'])
        self.assertGreater(result['approx_kl'], .02)
        self.assertEqual(result['updates'], 0)
        for key, value in model.state_dict().items():
            torch.testing.assert_close(value, before[key])
        self.assertTrue(all(parameter.grad is None for parameter in model.parameters()))

    def test_ppo_rejects_mixed_rewards_engine_and_rng(self):
        rows, _, _ = self._ppo_rows()
        config = RewardConfig()
        self.assertEqual(config.entropy, .01)
        self.assertEqual(config.bc_aux, .1)
        import inspect
        parameters = inspect.signature(train).parameters
        self.assertEqual(parameters['entropy'].default, .01)
        self.assertEqual(parameters['bc_aux'].default, .1)
        variants = {
            'engine_id': lambda copy_rows: copy_rows[1].__setitem__('engine_id', 'other-engine'),
            'reward configurations': lambda copy_rows: copy_rows[1].__setitem__(
                'reward_config', helpers.config(economy=.12)),
            'rng_version': lambda copy_rows: copy_rows[1].__setitem__('rng_version', 'other-rng'),
        }
        for message, mutate in variants.items():
            with self.subTest(message=message):
                changed = copy.deepcopy(rows)
                mutate(changed)
                model = helpers.model(seed=61)
                optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
                with self.assertRaisesRegex(ValueError, message):
                    train(model, optimizer, changed, method='ppo', epochs=1, minibatch=4,
                          bc_records=self._bc_rows())


class _FixedModel:
    format_name = 'duel'

    def __init__(self, logits):
        self.logits = torch.tensor(logits)

    def eval(self):
        return self

    def parameters(self):
        return iter([torch.zeros(1)])

    def __call__(self, chunk):
        return self.logits.repeat(len(chunk), 1), torch.zeros(len(chunk))


def _quality_rows(kind, count=32, split_name='validation'):
    return [{'split': split_name, 'format': 'duel', 'choice': 0,
             'candidates': [{'kind': kind}, {'kind': kind}]} for _ in range(count)]


def _quality_set(count=32, split_name='validation'):
    return (_quality_rows('recruit', count, split_name) +
            _quality_rows('move', count, split_name) +
            _quality_rows('attack', count, split_name))


class AuditExportTests(unittest.TestCase):
    def _audit(self, base, kind, choice=0):
        row = copy.deepcopy(base)
        candidate = row['candidates'][choice]
        candidate['kind'] = kind
        fields = INTENT_FIELDS[kind]
        values = {'x': 1, 'y': 1, 'tx': 2, 'ty': 2, 'ex': 2, 'ey': 2,
                  'full': False, 'weapon': 'blade', 'type': 'Spearman'}
        for field in fields:
            candidate[field] = values[field]
        row['actual'] = dict(kind=kind, **{field: candidate[field] for field in fields})
        row['choice'] = choice
        return row

    def test_audit_coverage_strata_alias_conflict_and_thresholds(self):
        bases = [helpers.synthetic_decision_row(seed=seed) for seed in (10, 11, 12)]
        covered = [self._audit(bases[0], 'recruit'), self._audit(bases[1], 'move'),
                   self._audit(bases[2], 'attack')]
        result = audit_bc(covered)
        self.assertEqual(result['status'], 'measured')
        self.assertAlmostEqual(result['totals']['coverage'], 1.)
        self.assertTrue(result['coverage_pass'])
        self.assertEqual(result['strata']['action']['recruit']['coverage'], 1.)
        self.assertGreater(result['identical_decision_inputs'], 0)
        uncovered = self._audit(bases[1], 'move')
        uncovered['choice'] = -1
        uncovered.pop('actual', None)
        missing = audit_bc(covered + [uncovered])
        self.assertEqual(missing['status'], 'inconclusive')
        self.assertEqual(missing['totals']['missing_intent'], 1)
        self.assertFalse(missing['coverage_pass'])

        alias = self._audit(bases[0], 'move', choice=0)
        alias['candidates'] = [copy.deepcopy(alias['candidates'][0]),
                               copy.deepcopy(alias['candidates'][0])]
        pair = copy.deepcopy(alias)
        pair['choice'] = 1
        aliased = audit_bc([alias, pair, self._audit(bases[1], 'recruit'),
                            self._audit(bases[2], 'attack')])
        self.assertEqual(aliased['totals']['alias_decisions'], 2)
        self.assertEqual(aliased['totals']['teacher_nonfirst_alias'], 1)
        self.assertEqual(aliased['conflicting_exact_input_groups'], 1)
        self.assertEqual(aliased['conflicting_exact_input_decisions'], 2)
        self.assertTrue(aliased['nonfirst_alias_examples'])

        rows = ([self._audit(bases[1], 'move') for _ in range(8)] +
                [self._audit(bases[2], 'attack') for _ in range(8)] +
                [self._audit(bases[0], 'recruit') for _ in range(3)])
        unmatched = self._audit(bases[0], 'recruit')
        unmatched['actual'] = {'kind': 'recruit', 'type': 'Missing', 'x': 999, 'y': 999}
        rows.append(unmatched)
        low = audit_bc(rows)
        self.assertEqual(low['status'], 'measured')
        self.assertGreaterEqual(low['totals']['coverage'], .90)
        self.assertLess(low['strata']['action']['recruit']['coverage'], .80)
        self.assertFalse(low['coverage_pass'])

    def test_imitation_quality_gate(self):
        with mock.patch('learning.train.batch', side_effect=lambda rows, device: (rows,)):
            good = _FixedModel([[3., 0.]])
            accepted = imitation_quality(good, _quality_set())
            self.assertTrue(accepted['effective'])
            self.assertTrue(accepted['formats']['duel']['effective'])
            self.assertEqual(accepted['formats']['duel']['kinds']['recruit']['samples'], 32)
            missing = imitation_quality(good, _quality_set(split_name='train'))
            self.assertFalse(missing['effective'])
            few = imitation_quality(good, _quality_set(count=31))
            self.assertFalse(few['effective'])
            uniform = imitation_quality(_FixedModel([[0., 0.]]), _quality_set())
            self.assertFalse(uniform['effective'])
            wrong = imitation_quality(_FixedModel([[0., 3.]]), _quality_set())
            self.assertFalse(wrong['effective'])

    def test_imitation_quality_enforces_kind_precision_thresholds(self):
        rows = (_quality_rows('recruit') + _quality_rows('attack') +
                _quality_rows('move'))
        for index, row in enumerate(rows[-32:]):
            row['choice'] = 0 if index < 10 else 1
        with mock.patch('learning.train.batch', side_effect=lambda rows, device: (rows,)):
            report = imitation_quality(_FixedModel([[1., 0.]]), rows)['formats']['duel']
        self.assertGreaterEqual(report['accuracy'], .4)
        self.assertGreaterEqual(report['kinds']['recruit']['accuracy'], .6)
        self.assertGreaterEqual(report['kinds']['attack']['accuracy'], .35)
        self.assertLess(report['kinds']['move']['accuracy'], .35)
        self.assertFalse(report['effective'])

    def _checkpoint_model(self, directory):
        path = directory / 'verify.pt'
        model = helpers.model(seed=71)
        checkpoint(path, model, torch.optim.Adam(model.parameters(), lr=1e-3))
        loaded, _ = load_model(path, 'duel')
        return loaded

    def test_verify_numerics_requires_128_and_two_turns(self):
        with helpers.temporary_directory() as directory:
            model = self._checkpoint_model(directory)
            rows = _rows(turns=2, decisions_per_turn=1)
            with self.assertRaisesRegex(ValueError, '128'):
                verify_numerics(model, attach_histories(rows))
            helpers.pad_candidates(rows[0], 128)
            short = rows[:1]
            with self.assertRaisesRegex(ValueError, 'continuous turn memory'):
                verify_numerics(model, attach_histories(short))

    def test_verify_numerics_128_candidates_two_turns(self):
        with helpers.temporary_directory() as directory:
            model = self._checkpoint_model(directory)
            rows = _rows(turns=2, decisions_per_turn=1)
            helpers.pad_candidates(rows[0], 128)
            error = verify_numerics(model, attach_histories(rows))
            self.assertLessEqual(error, 1e-5)

    def test_verify_numerics_memory_overflow_and_128_entities(self):
        with helpers.temporary_directory() as directory:
            model = self._checkpoint_model(directory)
            long_rows = _rows(turns=33, decisions_per_turn=1)
            helpers.pad_candidates(long_rows[0], 128)
            for row in long_rows[1:]:
                row['candidates'] = row['candidates'][:1]
                row['choice'] = 0
            error = verify_numerics(model, attach_histories(long_rows))
            self.assertLessEqual(error, 1e-5)
            overflow = _rows(turns=2, decisions_per_turn=1)
            real = overflow[1]['spatial']['entities']
            overflow[1]['spatial']['entities'] = [
                dict(real[index % len(real)], id='overflow-%d' % index) for index in range(128)]
            overflow[1]['candidates'][0]['actor'] = dict(
                overflow[1]['candidates'][0].get('actor') or real[0], id='direct-actor')
            helpers.pad_candidates(overflow[0], 128)
            helpers.pad_candidates(overflow[1], 128)
            error = verify_numerics(model, attach_histories(overflow))
            self.assertLessEqual(error, 1e-5)

    def test_schema_three_is_rejected_without_migration(self):
        row = helpers.synthetic_decision_row(seed=12)
        row['split'] = split(row['game_family'])
        row['schema'] = 3
        with self.assertRaisesRegex(ValueError, 'feature schema mismatch'):
            validate_record(row, 'duel')
        with helpers.temporary_directory() as directory:
            path = directory / 'schema3.jsonl.gz'
            with gzip.open(path, 'wt', encoding='utf-8') as stream:
                stream.write(json.dumps(row, separators=(',', ':')) + '\n')
            with self.assertRaisesRegex(ValueError, 'feature schema mismatch'):
                read_shards([str(path)])
            self.assertEqual(row['schema'], 3)


if __name__ == '__main__':
    unittest.main()
