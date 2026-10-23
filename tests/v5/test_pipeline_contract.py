"""V5 pipeline contract: adapters, shards, rewards, control, schedules and reports.

All data is synthetic. Native Wesnoth is never launched and real performance
numbers are never claimed: `run_benchmarks` is exercised only with deterministic
runner doubles, so every speedup statement here is an assertion about the
verification code, not about engines.
"""
from __future__ import annotations

import contextlib
import copy
import gzip
import hashlib
import json
import math
import sys
import tempfile
import time
import unittest
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import torch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import helpers
from learning import benchmark, control, features, manifest, maps, package, report, rewards
from learning import reward_metrics, schedule
from learning.adapters import LiteAdapter, NativeAdapter, create_adapter
from learning.control import RewardController, queue_control, show_control
from learning.data import write_shard
from learning.experiment import FormatExperiment, coverage_gate, default_config, opening_gate, validate_config
from learning.formats import FORMATS, PLAYERS
from learning.lite_host import LiteHost, play_lite_job
from learning.rowpack import unpack_line
from learning.reward_metrics import build_control_metrics, summarize_game
from learning.sequences import IndexedSequenceStore, read_raw_shards, read_shards


def frozen_rules(directory, *, complete=True, native=True, performance=True, rules_data=None,
                 rules_version='synthetic-v5'):
    """Synthetic frozen catalogue; helpers.write_rules_dir ignores `accepted`."""
    rules_dir = helpers.write_rules_dir(directory, rules_data, complete=complete,
                                        native_accepted=native,
                                        performance_accepted=performance)
    catalog_path = rules_dir / 'catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    catalog['rules_version'] = rules_version
    catalog_path.write_text(json.dumps(catalog), encoding='utf-8')
    return rules_dir


def catalog_patch(rules_dir):
    return mock.patch.object(features, 'RULES_PATH', Path(rules_dir) / 'catalog.json')


def read_gzip(path):
    """Decode shard lines written by `learning.data.write_shard`.

    Large records are packed into a float32 block, so audit assertions must
    decode them back to plain Python values instead of reading raw JSON.
    """
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [unpack_line(line, plain=True)[0] for line in stream]


def write_pending(run_dir, format_name, commands):
    directory = Path(run_dir) / 'control'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f'{format_name}.pending.json').write_text(json.dumps(commands), encoding='utf-8')


def event_body(event):
    return {key: value for key, value in event.items() if key != 'checksum'}


def result(bots=('astra', 'astra'), *, reason='victory', winner=1, faults=None,
           teams=None, survivors=(1, 2), factions=None):
    bots = list(bots)
    factions = list(factions or ['Fighter', 'Skeleton'] * max(1, len(bots) // 2))[:len(bots)]
    winning_team = 0
    if teams and winner:
        winning_team = teams[winner - 1]
    return dict(engine_id='lite-0.1', winner=winner, winning_team=winning_team,
                truncated=reason == 'turn_limit',
                reason=reason,
                survivors=list(survivors) if survivors is not None else None,
                bots=bots, factions=factions, teams=list(teams) if teams else None,
                turns=10, faults=list(faults or []),
                rank_points={str(index): 0.5 for index in range(1, len(bots) + 1)},
                approximate=True)


def observation_row(turn=1, *, side=1, game_id='game-1', game_family='family-1', hp=None):
    row = helpers.synthetic_decision_row(seed=3, format_name='duel', source='astra',
                                         game_id=game_id, game_family=game_family, turn=turn)
    row['turn'] = turn
    row['side'] = side
    row['format'] = 'duel'
    row['committed'] = True
    row['reward_raw'] = dict(economy=0.1, control=0.2, explored=0.5)
    row['reward_after'] = dict(row['reward_raw'])
    row['memory_write'] = dict(global_features=row['global'], global_=row['global'],
                               opponents=row['opponents'],
                               spatial=copy.deepcopy(row['spatial']), turn=turn, candidates=[])
    if hp is not None:
        entities = row['spatial'].get('entities', [])
        for entity in entities:
            if entity.get('side') == side and entity.get('leader'):
                entity['features'][2] = hp / 100.0
        row['memory_write']['spatial'] = copy.deepcopy(row['spatial'])
    return row


def diagnostic(*, side=1, game_family='family-1', **overrides):
    row = dict(format='duel', engine_id='lite', rules_version='synthetic-v5',
               map='map-a', map_sha256='sha-a', faction='Fighter', context='solo',
               game_family=game_family, side=side, complete=True, faults=[],
               source='astra', teacher='gpt6astra', map_partition='validation',
               coverage5=0.5, coverage10=0.6, control=0.4, leader_survival=1.0,
               loss=0.1)
    row.update(overrides)
    return row


def evidence(rows):
    return [dict(status='complete', reward_diagnostics=[row]) for row in rows]


def reference(family, **overrides):
    values = dict(game_family=family, coverage5=0.6, coverage10=0.7,
                  control=0.6, leader_survival=1.0, loss=0.1)
    values.update(overrides)
    return diagnostic(**values)


def validation_job(identifier, *, engine='lite', rotation=0, context='solo',
                   label='selected', control_name='fixed', block=0, fmt='duel',
                   policy_sides=(1,), control_sides=(2,), map_partition='validation',
                   **meta_overrides):
    meta = dict(format=fmt, map_partition=map_partition, label=label,
                control=control_name, block=block, context=context,
                rotation=rotation, policy_sides=list(policy_sides),
                control_sides=list(control_sides), map_sha256='sha-a')
    meta.update(meta_overrides)
    return dict(id=identifier, engine=engine, meta=meta, game_family='family-x', seed=1)


def validation_result(job, rows):
    return dict(id=job['id'], status='complete', reward_diagnostics=rows,
                result=dict(bots=['astra', 'astra'], faults=[], winner=1,
                            winning_team=0, teams=None,
                            rank_points={'1': 1, '2': 0}))


def strata_row(*, control_value=0.4, coverage5=0.5, coverage10=0.6, **overrides):
    row = dict(map='map-a', faction='Fighter', coverage5=coverage5,
               coverage10=coverage10, control=control_value, leader_survival=1.0,
               loss=0.1, astra_coverage5=0.6, astra_coverage10=0.7,
               astra_control=0.6, astra_leader_survival=1.0, astra_loss=0.1)
    row.update(overrides)
    return row


def control_block(identifier, *, fixed_score=2.0, native_score=None,
                  strata=None, partition='validation', complete=True, faults=None):
    return dict(id=f'block-{identifier}', complete=complete,
                faults=list(faults or []), partition=partition,
                strata=list(strata if strata is not None else [strata_row()]),
                fixed_score=fixed_score, native_score=native_score)


def approx(value, expected, tolerance=1e-9):
    return abs(value - expected) <= tolerance


class AdapterContractTests(unittest.TestCase):
    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def test_missing_catalog_is_a_runtime_error(self):
        with self.assertRaisesRegex(RuntimeError, 'missing native 1.18.8 frozen rules'):
            LiteAdapter(helpers.spec(), self.directory / 'empty')

    def test_acceptance_flags_are_required(self):
        pending = frozen_rules(self.directory / 'pending', complete=False,
                               native=False, performance=False)
        with self.assertRaisesRegex(RuntimeError, 'P1/P2 acceptance is pending'):
            LiteAdapter(helpers.spec(), pending)
        partial = frozen_rules(self.directory / 'partial', complete=False,
                               native=True, performance=True)
        with self.assertRaisesRegex(RuntimeError, 'P1/P2 acceptance is pending'):
            LiteAdapter(helpers.spec(), partial)

    def test_accepted_catalog_builds_the_real_lite_engine(self):
        rules_dir = frozen_rules(self.directory / 'rules')
        adapter = LiteAdapter(helpers.spec(), rules_dir)
        view = adapter.observe(1)
        self.assertEqual(adapter.engine_id, 'lite-0.1')
        self.assertIn('current_side', view)
        self.assertTrue(adapter.rules_sha256)

    def test_rules_hash_mismatch_is_rejected(self):
        rules_dir = frozen_rules(self.directory / 'rules')
        with open(rules_dir / 'rules.json', 'ab') as stream:
            stream.write(b'\n')
        with self.assertRaisesRegex(ValueError, 'rules.json differs from the frozen catalog hash'):
            LiteAdapter(helpers.spec(), rules_dir)

    def test_source_hash_mismatch_is_rejected(self):
        rules_dir = frozen_rules(self.directory / 'rules')
        catalog_path = rules_dir / 'catalog.json'
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        catalog['source_hash'] = 'tampered-source'
        catalog_path.write_text(json.dumps(catalog), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'catalog/rules source provenance mismatch'):
            LiteAdapter(helpers.spec(), rules_dir)

    def test_wrong_source_version_is_rejected(self):
        data = copy.deepcopy(helpers.rules())
        data['source_version'] = '1.19.0'
        rules_dir = frozen_rules(self.directory / 'rules', rules_data=data)
        with self.assertRaisesRegex(ValueError, 'lite requires native 1.18.8 data'):
            LiteAdapter(helpers.spec(), rules_dir)

    def test_experience_modifier_uses_integer_rounding(self):
        data = copy.deepcopy(helpers.rules())
        expected = {'Fighter': 53, 'Archer': 51, 'Skeleton': 50, 'Mage': 55, 'Ghost': 1}
        data['units']['Fighter']['experience'] = 42
        data['units']['Archer']['experience'] = 41
        data['units']['Skeleton']['experience'] = 40
        data['units']['Mage']['experience'] = 44
        data['units']['Ghost']['experience'] = 1
        rules_dir = frozen_rules(self.directory / 'rules', rules_data=data)
        captured = {}

        class FakeEngine:
            def __init__(self, rules_json, spec_json):
                captured['rules'] = json.loads(rules_json)
                captured['spec'] = json.loads(spec_json)

        game_spec = helpers.spec()
        game_spec['experience_modifier'] = 125
        with mock.patch('_engine_lite.LiteEngine', FakeEngine):
            LiteAdapter(game_spec, rules_dir)
        experiences = {name: unit['experience'] for name, unit in captured['rules']['units'].items()}
        self.assertEqual(experiences, expected)

    def test_invalid_experience_modifiers_are_rejected(self):
        rules_dir = frozen_rules(self.directory / 'rules')
        for modifier in (0, -5, 1.5, '100', None):
            game_spec = helpers.spec()
            game_spec['experience_modifier'] = modifier
            with self.subTest(modifier=modifier):
                with self.assertRaisesRegex(ValueError, 'invalid experience modifier'):
                    LiteAdapter(game_spec, rules_dir)

    def test_create_adapter_lite_without_catalog_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'missing native 1.18.8 frozen rules'):
            create_adapter('lite', helpers.spec(), rules_dir=self.directory / 'empty')

    def test_create_adapter_native_without_transport_fails_clearly(self):
        with mock.patch.dict('os.environ', {'WESNOTH_EXE': ''}):
            with self.assertRaisesRegex(ValueError, 'WESNOTH_EXE|Wesnoth 1.18.8'):
                create_adapter('native', helpers.spec())

    def test_create_adapter_native_uses_an_injected_transport(self):
        class Transport:
            engine_id = 'native-1.18.8'

            def __init__(self):
                self.calls = []

            def reset(self, spec):
                self.calls.append(('reset', spec))

        transport = Transport()
        adapter = create_adapter('native', helpers.spec(), transport=transport)
        self.assertIsInstance(adapter, NativeAdapter)
        self.assertEqual(adapter.engine_id, 'native-1.18.8')
        self.assertEqual(transport.calls, [])

    def test_create_adapter_unknown_engine_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unknown engine'):
            create_adapter('other', helpers.spec())


class LiteJobTests(unittest.TestCase):
    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.rules_dir = frozen_rules(self.directory / 'rules')

    def job(self, **overrides):
        value = dict(id='lite-job', seed=7, bots=['astra', 'astra'],
                     game_spec=helpers.spec(max_turns=4),
                     rules_dir=str(self.rules_dir),
                     shard=str(self.directory / 'shards' / 'job.jsonl.gz'),
                     deadline=time.time() + 120, max_decisions=1000,
                     meta=dict(format='duel', map='synthetic', map_sha256='sha-a',
                               map_partition='train', context='solo'),
                     teams=[1, 2], factions=['Fighter', 'Skeleton'],
                     game_family='family-1',
                     learning=dict(sides={'1': {}, '2': {}}, version='v5-test'))
        value.update(overrides)
        return value

    def test_astra_job_writes_schema_four_shard(self):
        job = self.job()
        with catalog_patch(self.rules_dir):
            outcome = play_lite_job(job)
        self.assertEqual(outcome['status'], 'complete', outcome.get('error'))
        self.assertEqual(outcome['engine'], 'lite')
        self.assertEqual(outcome['result']['reason'], 'turn_limit')
        self.assertTrue(outcome['result']['truncated'])
        self.assertEqual(outcome['result']['bots'], ['astra', 'astra'])
        self.assertNotIn('baseline', json.dumps(outcome['result']))
        self.assertEqual(outcome['training_shard']['written'], 24)
        rows = read_gzip(job['shard'])
        self.assertEqual(len(rows), 24)
        for row in rows:
            self.assertEqual(row['schema'], features.VERSION)
            self.assertEqual(row['source'], 'astra')
            self.assertEqual(row['engine_id'], 'lite')
            self.assertEqual(row['rules_version'], 'synthetic-v5')
            self.assertEqual(row['architecture_id'], 'relational_v5')
            selected = row['candidates'][row['choice']]
            for key, value in row['actual'].items():
                self.assertEqual(selected[key], value)
        self.assertEqual(outcome['coverage']['total'], 24)
        self.assertEqual(outcome['coverage']['matched'], 24)

    def test_policy_actor_input_excludes_teacher_and_reward_fields(self):
        seen = []

        def policy(actor_input):
            seen.append(dict(actor_input))
            return dict(choice=0, log_probability=0.0, value=0.0)

        job2 = self.job(id='policy-job', bots=['policy-a', 'policy-b'],
                        learning=dict(sides={'1': {}, '2': {}}, version='v5-test',
                                      dagger_teacher=True),
                        max_turns=6, policy=policy,
                       bootstrap_policy=lambda row: 0.0)
        with catalog_patch(self.rules_dir):
            outcome = play_lite_job(job2)
        self.assertEqual(outcome['status'], 'complete', outcome.get('error'))
        self.assertTrue(seen)
        for actor_input in seen:
            self.assertNotIn('teacher_action', actor_input)
            self.assertNotIn('reward_raw', actor_input)
            self.assertNotIn('reward_after', actor_input)
        rows = read_gzip(job2['shard'])
        self.assertTrue(all(row['source'] == 'policy' for row in rows))
        self.assertLessEqual(len(seen), 32 * 2)  # queries are capped per side
        dagger_path = Path(job2['shard']).with_name(
            Path(job2['shard']).name.replace('.jsonl.gz', '.dagger.jsonl.gz'))
        self.assertTrue(dagger_path.is_file())
        dagger = read_gzip(dagger_path)
        queries = [row for row in dagger if row.get('query_only')]
        self.assertTrue(queries)
        self.assertLessEqual(len(queries), 32)
        for row in queries:
            self.assertGreaterEqual(row['choice'], 0)
            self.assertEqual(row['candidates'][row['choice']]['kind'], row['actual']['kind'])

    def test_teacher_queries_are_capped_per_game(self):
        def policy(actor_input):
            return dict(choice=0, log_probability=0.0, value=0.0)

        job = self.job(id='query-cap', bots=['policy-a', 'policy-b'],
                       game_spec=helpers.spec(max_turns=70), max_turns=70,
                       policy=policy, bootstrap_policy=lambda row: 0.0,
                       learning=dict(sides={'1': {}, '2': {}}, version='v5-test',
                                     dagger_teacher=True))
        with catalog_patch(self.rules_dir):
            outcome = play_lite_job(job)
        self.assertEqual(outcome['status'], 'complete', outcome.get('error'))
        dagger_path = Path(job['shard']).with_name(
            Path(job['shard']).name.replace('.jsonl.gz', '.dagger.jsonl.gz'))
        queries = [row for row in read_gzip(dagger_path) if row.get('query_only')]
        self.assertLessEqual(len(queries), 32)

    def test_baseline_in_lite_is_an_infrastructure_error(self):
        job = self.job(bots=['baseline', 'astra'])
        outcome = play_lite_job(job)
        self.assertEqual(outcome['status'], 'infrastructure_error')
        self.assertIn('official baseline is native-only', outcome['error'])

    def test_truncated_policy_game_requires_a_bootstrap_callback(self):
        def policy(actor_input):
            return dict(choice=0, log_probability=0.0, value=0.0)

        job = self.job(id='truncated', bots=['policy-a', 'policy-b'],
                       policy=policy, max_turns=4,
                       learning=dict(sides={'1': {}, '2': {}}, version='v5-test'))
        with catalog_patch(self.rules_dir):
            outcome = play_lite_job(job)
        self.assertEqual(outcome['status'], 'infrastructure_error')
        self.assertIn('truncated policy game requires a frozen bootstrap_policy callback',
                      outcome['error'])

    def test_truncated_policy_game_writes_bootstrap_values(self):
        def policy(actor_input):
            return dict(choice=0, log_probability=0.0, value=0.0)

        job = self.job(id='truncated-ok', bots=['policy-a', 'policy-b'],
                       policy=policy, max_turns=4,
                       bootstrap_policy=lambda row: 0.5,
                       learning=dict(sides={'1': {}, '2': {}}, version='v5-test'))
        with catalog_patch(self.rules_dir):
            outcome = play_lite_job(job)
        self.assertEqual(outcome['status'], 'complete', outcome.get('error'))
        self.assertTrue(outcome['result']['truncated'])
        rows = [row for row in read_gzip(job['shard']) if row.get('bootstrap_value') is not None]
        self.assertTrue(rows)
        self.assertTrue(all(row['bootstrap_value'] == 0.5 for row in rows))

    def frozen_addon(self, format_name='ffa4'):
        """A real exported addon: FrozenPolicies loads model.pt beside the addon dir."""
        from learning.features import schema
        from learning.model import ARCHITECTURE, Policy
        torch.manual_seed(173)
        torch.set_num_threads(1)
        addon = self.directory / 'Student'
        (addon / 'lua').mkdir(parents=True, exist_ok=True)
        (addon / 'lua' / 'config.lua').write_text('return {["mode"]="sample"}', encoding='utf-8')
        model = Policy(format_name).eval()
        with catalog_patch(self.rules_dir):
            checkpoint = dict(model=model.state_dict(), architecture=ARCHITECTURE,
                              features=schema(), format=format_name)
        torch.save(checkpoint, self.directory / 'model.pt')
        return addon

    def four_seat_job(self, **overrides):
        """One frozen policy seat plus three Astra seats on a zero-gold ffa4 board."""
        addon = self.frozen_addon()
        spec = helpers.spec(sides=4, fog=False, max_turns=2)
        for side in spec['sides']:
            side['gold'] = 0
            side['team'] = str(side['id'])
        value = self.job(id='four-seat',
                         bots=[str(addon), 'gpt6astra', 'gpt6astra', 'gpt6astra'],
                         game_spec=spec, teams=None,
                         factions=['Fighter', 'Skeleton', 'Fighter', 'Skeleton'],
                         max_turns=2,
                         meta=dict(format='ffa4', map='synthetic', map_sha256='sha-a',
                                   map_partition='train', context='solo'),
                         learning=dict(sides={'1': {}}, version='v5-test'))
        value.update(overrides)
        return value

    def decision_spy(self, calls):
        original = LiteHost.decision

        def spy(host, side, **kwargs):
            result = original(host, side, **kwargs)
            calls.append(dict(side=side, kwargs=sorted(kwargs),
                              teacher=kwargs.get('teacher', False),
                              generate_candidates=kwargs.get('generate_candidates', True),
                              budget='budget' in result['timing']))
            return result
        return spy

    def test_uncollected_seats_skip_candidate_generation(self):
        job = self.four_seat_job()
        calls = []
        with mock.patch.object(LiteHost, 'decision', self.decision_spy(calls)):
            with catalog_patch(self.rules_dir):
                outcome = play_lite_job(job)
        self.assertEqual(outcome['status'], 'complete', outcome.get('error'))
        rows = read_gzip(job['shard'])
        self.assertTrue(rows)
        self.assertEqual({row['side'] for row in rows}, {1})
        uncollected = [call for call in calls if call['side'] != 1]
        collected = [call for call in calls if call['side'] == 1]
        self.assertTrue(uncollected, calls)
        self.assertTrue(collected, calls)
        self.assertEqual({call['side'] for call in uncollected}, {2, 3, 4}, calls)
        self.assertTrue(all(call['teacher'] for call in uncollected), calls)
        self.assertFalse(any(call['teacher'] for call in collected), calls)
        for call in uncollected:
            self.assertFalse(call['generate_candidates'], call)
            self.assertFalse(call['budget'], call)
        for call in collected:
            # Initial/terminal metrics use a public observation without search;
            # actual policy decisions still generate the full candidate set.
            self.assertEqual(call['generate_candidates'],call['budget'],call)
        self.assertTrue(any(call['generate_candidates'] for call in collected))

    def test_query_and_bootstrap_decisions_get_full_candidates(self):
        job = self.four_seat_job(id='query-bootstrap',
                                 bootstrap_policy=lambda row: 0.5,
                                 learning=dict(sides={'1': {}}, version='v5-test',
                                               dagger_teacher='data/opponents/gpt6astra.zip'))
        calls = []
        with mock.patch.object(LiteHost, 'decision', self.decision_spy(calls)):
            with catalog_patch(self.rules_dir):
                outcome = play_lite_job(job)
        self.assertEqual(outcome['status'], 'complete', outcome.get('error'))
        self.assertTrue(outcome['result']['truncated'])
        queries = [call for call in calls if call['side'] == 1 and call['teacher']]
        self.assertTrue(queries, calls)
        self.assertLessEqual(len(queries), 32, calls)
        for call in queries:
            self.assertTrue(call['generate_candidates'], call)
            self.assertTrue(call['budget'], call)
        bootstrap = [call for call in calls if call['kwargs'] == ['teacher']]
        self.assertEqual(len(bootstrap), 1, calls)
        self.assertEqual(bootstrap[0]['side'], 1)
        self.assertFalse(bootstrap[0]['teacher'])
        self.assertTrue(bootstrap[0]['generate_candidates'])
        self.assertTrue(bootstrap[0]['budget'])
        self.assertIs(calls[-1], bootstrap[0])
        rows = read_gzip(job['shard'])
        self.assertTrue(rows)
        self.assertTrue(all(row['candidate_version'] == 'schema5-fixed-20000-v3' for row in rows))
        bootstrapped = [row for row in rows if row.get('bootstrap_value') is not None]
        self.assertTrue(bootstrapped)
        dagger_path = Path(job['shard']).with_name(
            Path(job['shard']).name.replace('.jsonl.gz', '.dagger.jsonl.gz'))
        query_rows = [row for row in read_gzip(dagger_path) if row.get('query_only')]
        self.assertTrue(query_rows)
        self.assertLessEqual(len(query_rows), 32)
        for row in query_rows:
            self.assertGreater(len(row['candidates']), 1)
            self.assertEqual(row['candidate_version'], 'schema5-fixed-20000-v3')

    def test_missing_catalog_is_reported_as_infrastructure_error(self):
        job = self.job(rules_dir=str(self.directory / 'missing'))
        outcome = play_lite_job(job)
        self.assertEqual(outcome['status'], 'infrastructure_error')
        self.assertIn('missing native 1.18.8 frozen rules', outcome['error'])


class ShardSequenceTests(unittest.TestCase):
    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def policy_rows(self, turns=3, decisions=2, game_id='seq-1', family='seq-family'):
        rows = helpers.sequence_rows(turns=turns, decisions_per_turn=decisions,
                                     format_name='duel', source='policy',
                                     game_id=game_id, game_family=family, seed=5)
        for row in rows:
            row['reward_raw'] = dict(economy=0.1, control=0.2, explored=0.5)
        return rows

    def test_write_shard_attaches_full_history_before_filtering(self):
        rows = self.policy_rows(turns=8)
        path = self.directory / 'shards' / 'game.jsonl.gz'
        written = write_shard(path, 'game-1', rows, result(), provenance={'rules_version': 'synthetic-v5'})
        self.assertEqual(written['written'], len(rows))
        self.assertIsNone(written['excluded'])
        raw = read_gzip(path)
        self.assertEqual(len(raw), len(rows))
        self.assertTrue(all(row['game_id'] == 'game-1' for row in raw))
        self.assertTrue(all(row['rules_version'] == 'synthetic-v5' for row in raw))
        self.assertTrue((path.parent / 'sequences').is_dir())
        attached = read_raw_shards([path], format_name='duel')
        self.assertEqual(len(attached), len(rows))
        self.assertTrue(all('_history' in row for row in attached))
        later = [row for row in attached if row['turn'] > 1]
        self.assertTrue(later)
        self.assertTrue(any(row['_history'] for row in later))
        for row in attached:
            for history in row['_history']:
                self.assertLessEqual(history['turn'], row['turn'])
        windows = read_shards([path], partition=attached[0]['split'], limit=1,
                              seed=1, format_name='duel')
        self.assertLessEqual(len(windows), 1)
        for row in windows:
            self.assertIn('_history', row)

    def test_faulted_game_is_excluded(self):
        rows = self.policy_rows()
        path = self.directory / 'shards' / 'faulted.jsonl.gz'
        written = write_shard(path, 'faulted', rows, result(faults=['abort']))
        self.assertEqual(written, dict(written=0, excluded='faulted_game'))
        self.assertTrue(path.is_file())
        self.assertEqual(read_gzip(path), [])

    def test_missing_truncation_bootstrap_is_excluded_but_file_is_written(self):
        rows = self.policy_rows()
        path = self.directory / 'shards' / 'truncated.jsonl.gz'
        written = write_shard(path, 'truncated', rows,
                              result(reason='turn_limit', survivors=None))
        self.assertEqual(written['excluded'], 'missing_truncation_bootstrap')
        self.assertEqual(written['written'], 0)
        self.assertEqual(read_gzip(path), [])
        bootstraps = {'1': dict(value=0.5, potential=0.1, raw=0.2, turn=3)}
        written = write_shard(path, 'truncated', rows,
                              result(reason='turn_limit', survivors=None),
                              bootstraps=bootstraps)
        self.assertEqual(written['written'], len(rows))
        values = {row['bootstrap_value'] for row in read_gzip(path)}
        self.assertEqual(values, {0.5})

    def test_sequence_store_roundtrip_and_content_guard(self):
        rows = self.policy_rows()
        path = self.directory / 'shards' / 'store.jsonl.gz'
        write_shard(path, 'store-1', rows, result())
        with IndexedSequenceStore(path.parent / 'sequences') as store:
            stored = list(store.iter_records())
            self.assertEqual(len(stored), len(rows))
            self.assertTrue(any(row['_history'] for row in stored))
            self.assertEqual(store.write(rows), len(rows))  # idempotent
            changed = copy.deepcopy(rows)
            changed[0]['reward_raw'] = dict(economy=0.9, control=0.2, explored=0.5)
            changed[0]['reward_after'] = dict(changed[0]['reward_raw'])
            with self.assertRaisesRegex(ValueError,
                                        'already exists with different raw content'):
                store.write(changed)


class RewardMetricsTests(unittest.TestCase):
    def test_summarize_game_horizons_and_reward_statistics(self):
        rows = [observation_row(turn) for turn in range(1, 11)]
        job = dict(id='game-1', reward_config=helpers.config(),
                   meta=dict(format='duel', map='map-a', map_sha256='sha-a',
                             map_partition='validation', context='solo'),
                   factions=['Fighter', 'Skeleton'])
        diagnostics = summarize_game(rows, result(), job)
        self.assertEqual(len(diagnostics), 1)
        row = diagnostics[0]
        self.assertTrue(row['complete'], row['missing'])
        self.assertEqual(row['coverage5'], 0.5)
        self.assertEqual(row['coverage10'], 0.5)
        self.assertEqual(row['control'], 0.2)
        self.assertEqual(row['leader_survival'], 1.0)
        self.assertEqual(row['loss'], 0.0)
        self.assertEqual(sorted(row['horizons']), ['10', '5'])
        statistics = row['reward_statistics']
        self.assertEqual(statistics['transitions'], 10)
        self.assertEqual(statistics['terminal_square_sum'], 1.0)
        self.assertGreaterEqual(statistics['shaping_square_sum'], 0.0)

    def test_summarize_game_reports_missing_horizons_and_provenance(self):
        rows = [observation_row(turn) for turn in (1, 2, 3)]
        job = dict(id='short', meta=dict(format='duel'), factions=['Fighter', 'Skeleton'])
        row = summarize_game(rows, result(), job)[0]
        self.assertFalse(row['complete'])
        for key in ('turn5', 'turn10', 'map', 'map_sha256', 'map_partition'):
            self.assertIn(key, row['missing'])
        statistics = row['reward_statistics']
        self.assertEqual(set(statistics), {'shaping_square_sum', 'terminal_square_sum',
                                           'transitions'})
        self.assertEqual(statistics['transitions'], 3)

    def test_build_control_metrics_full_rotation_block(self):
        references = [reference(f'family-{index}') for index in range(4)]
        jobs = [validation_job('v0', rotation=0), validation_job('v1', rotation=1)]
        results = [validation_result(job, [diagnostic(game_family='family-x')])
                   for job in jobs]
        metrics = build_control_metrics(jobs, results, evidence(references),
                                        {'duel': {'status': 'passed'}})
        self.assertEqual(metrics['partition'], 'validation')
        self.assertEqual(metrics['new_games'], 0)
        self.assertEqual(metrics['faulted_games'], 0)
        self.assertEqual(metrics['reference_min_families'], 4)
        self.assertEqual(len(metrics['validation_blocks']), 1)
        block = metrics['validation_blocks'][0]
        self.assertTrue(block['complete'])
        self.assertEqual(block['engine_id'], 'lite')
        self.assertEqual(block['partition'], 'validation')
        self.assertIsNotNone(block['fixed_score'])
        self.assertIsNone(block['native_score'])
        stratum = block['strata'][0]
        self.assertEqual(stratum['map'], 'map-a')
        self.assertEqual(stratum['faction'], 'Fighter')
        self.assertEqual(stratum['astra_control'], 0.6)

    def test_build_control_metrics_keeps_native_score(self):
        references = [reference(f'family-{index}') for index in range(4)]
        jobs = [validation_job('n0', engine='native', rotation=0),
                validation_job('n1', engine='native', rotation=1)]
        results = [validation_result(job, [diagnostic(game_family='family-x')])
                   for job in jobs]
        block = build_control_metrics(jobs, results, evidence(references),
                                      {'duel': {'status': 'passed'}})['validation_blocks'][0]
        self.assertIsNotNone(block['native_score'])
        self.assertIsNone(block['fixed_score'])

    def test_build_control_metrics_rejects_wrong_partition(self):
        jobs = [validation_job('v0', rotation=0, map_partition='train'),
                validation_job('v1', rotation=1, map_partition='train')]
        metrics = build_control_metrics(jobs, [], [], {})
        self.assertEqual(metrics['validation_blocks'], [])
        self.assertEqual(metrics['excluded_evidence'][0]['reason'], 'not validation partition')

    def test_build_control_metrics_requires_four_reference_families(self):
        references = [reference(f'family-{index}') for index in range(3)]
        jobs = [validation_job('v0', rotation=0), validation_job('v1', rotation=1)]
        results = [validation_result(job, [diagnostic(game_family='family-x')])
                   for job in jobs]
        metrics = build_control_metrics(jobs, results, evidence(references), {})
        self.assertEqual(metrics['validation_blocks'], [])
        reasons = {item['reason'] for item in metrics['excluded_evidence']}
        self.assertEqual(reasons, {'insufficient exact Astra calibration'})
        self.assertEqual(metrics['excluded_evidence'][0]['reference_families'], 3)

    def test_build_control_metrics_rejects_incomplete_rotations(self):
        jobs = [validation_job('v0', rotation=0)]
        results = [validation_result(jobs[0], [diagnostic()])]
        metrics = build_control_metrics(jobs, results, evidence([diagnostic()]), {})
        self.assertEqual(metrics['validation_blocks'], [])
        self.assertEqual(metrics['excluded_evidence'][0]['reason'],
                         'incomplete or faulted rotation block')

    def test_build_control_metrics_rejects_faulted_results(self):
        jobs = [validation_job('v0', rotation=0), validation_job('v1', rotation=1)]
        results = [validation_result(jobs[0], [diagnostic()]),
                   dict(validation_result(jobs[1], [diagnostic()]),
                        result=dict(bots=['astra', 'astra'], faults=['abort']))]
        metrics = build_control_metrics(jobs, results, evidence([diagnostic()]), {})
        self.assertEqual(metrics['validation_blocks'], [])
        self.assertEqual(metrics['excluded_evidence'][0]['reason'],
                         'incomplete or faulted rotation block')

    def test_build_control_metrics_requires_map_sha(self):
        references = [reference(f'family-{index}', map_sha256=None)
                      for index in range(4)]
        jobs = [validation_job('v0', rotation=0, map_sha256=None),
                validation_job('v1', rotation=1, map_sha256=None)]
        results = [validation_result(job, [diagnostic(game_family='family-x', map_sha256=None)])
                   for job in jobs]
        metrics = build_control_metrics(jobs, results, evidence(references), {})
        self.assertEqual(metrics['validation_blocks'], [])

    def test_build_control_metrics_rejects_mismatched_strata(self):
        jobs = [validation_job('v0', rotation=0), validation_job('v1', rotation=1)]
        results = [validation_result(job, [diagnostic(game_family='family-x')])
                   for job in jobs]
        wrong_engine = [reference(f'e{index}', engine_id='native')
                        for index in range(4)]
        metrics = build_control_metrics(jobs, results, evidence(wrong_engine), {})
        self.assertEqual(metrics['validation_blocks'], [])
        excluded = metrics['excluded_evidence'][0]
        self.assertEqual(excluded['reason'], 'insufficient exact Astra calibration')
        self.assertEqual(excluded['reference_families'], 0)
        for overrides in (dict(context='astra_partner'),
                          dict(rules_version='native-1.18.8'),
                          dict(faction='Archer'),
                          dict(map_sha256='other-sha')):
            wrong = [reference(f'{key}{index}', **overrides)
                     for index, key in enumerate(('a', 'b', 'c', 'd'))]
            metrics = build_control_metrics(jobs, results, evidence(wrong), {})
            self.assertEqual(metrics['validation_blocks'], [], overrides)
            self.assertEqual(metrics['excluded_evidence'][0]['reason'],
                             'insufficient exact Astra calibration', overrides)
            self.assertEqual(metrics['excluded_evidence'][0]['reference_families'],
                             0, overrides)


class ControlQueueTests(unittest.TestCase):
    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def controller(self, fmt='duel', **kwargs):
        return RewardController(self.directory, fmt, **kwargs)

    def test_queue_writes_atomic_pending_without_applying(self):
        command = queue_control(self.directory, 'duel', {'economy': 0.17},
                                reason='manual probe')
        pending_path = self.directory / 'control' / 'duel.pending.json'
        self.assertTrue(pending_path.is_file())
        self.assertFalse(list(pending_path.parent.glob('*.tmp')))
        pending = json.loads(pending_path.read_text(encoding='utf-8'))
        self.assertEqual(pending[0]['id'], command['id'])
        self.assertEqual(pending[0]['changes'], {'economy': 0.17})
        controller = self.controller()
        self.assertEqual(controller.freeze()['economy'], 0.15)
        self.assertEqual(show_control(self.directory, 'duel')['duel']['pending'][0]['id'],
                         command['id'])

    def test_pending_applies_only_at_the_next_batch(self):
        controller = self.controller()
        frozen = controller.freeze()
        queue_control(self.directory, 'duel', {'economy': 0.17}, reason='batch boundary')
        self.assertEqual(controller.freeze(), frozen)
        applied = controller.boundary(0)
        self.assertEqual(applied['economy'], 0.17)
        self.assertEqual(applied['reward_version'], 1)

    def test_event_chain_contains_provenance_and_checksum(self):
        controller = self.controller()
        queue_control(self.directory, 'duel', {'economy': 0.17}, reason='chain')
        controller.boundary(7)
        events = [json.loads(line) for line in
                  (self.directory / 'control' / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event['seq'], 1)
        self.assertIsNone(event['previous'])
        self.assertEqual(event['format'], 'duel')
        self.assertEqual(event['old']['reward_version'], 0)
        self.assertEqual(event['new']['reward_version'], 1)
        self.assertEqual(event['source'], 'manual')
        self.assertEqual(event['reason'], 'chain')
        self.assertEqual(event['batch'], 7)
        self.assertTrue(event['command_id'])
        digest = hashlib.sha256(json.dumps(event_body(event), sort_keys=True,
                                           separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(event['checksum'], digest)

    def test_checksum_chain_links_events(self):
        controller = self.controller()
        queue_control(self.directory, 'duel', {'economy': 0.17}, reason='one')
        controller.boundary(0)
        queue_control(self.directory, 'duel', {'economy': 0.18}, reason='two')
        controller.boundary(1)
        events = [json.loads(line) for line in
                  (self.directory / 'control' / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(events[1]['previous'], events[0]['checksum'])
        with self.assertRaisesRegex(ValueError, 'invalid control event line'):
            (self.directory / 'control' / 'events.jsonl').write_text(
                json.dumps(dict(events[0], seq=2)), encoding='utf-8')
            self.controller()

    def test_adaptive_change_is_limited_to_ten_percent(self):
        with self.assertRaisesRegex(ValueError, 'adaptive change exceeds 10 percent'):
            queue_control(self.directory, 'duel', {'control': 0.12},
                          source='adaptive', reason='too large')
        queue_control(self.directory, 'duel', {'control': 0.11},
                      source='adaptive', reason='allowed')
        with self.assertRaisesRegex(ValueError, 'adaptive change exceeds 10 percent'):
            queue_control(self.directory, 'duel', {'economy': 0.12},
                          source='adaptive', reason='too large')
        with self.assertRaisesRegex(ValueError, 'empty control change'):
            queue_control(self.directory, 'duel', {}, reason='empty')
        with self.assertRaisesRegex(ValueError, 'unsupported control fields'):
            queue_control(self.directory, 'duel', {'unknown': 1}, reason='field')

    def test_crash_before_apply_replays_pending_once(self):
        queue_control(self.directory, 'duel', {'economy': 0.17}, reason='crash before')
        restarted = self.controller()
        self.assertEqual(restarted.freeze()['economy'], 0.15)
        self.assertEqual(restarted.boundary(0)['economy'], 0.17)
        events = (self.directory / 'control' / 'events.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(events), 1)

    def test_crash_after_apply_does_not_replay_the_event(self):
        command = queue_control(self.directory, 'duel', {'economy': 0.17}, reason='crash after')
        controller = self.controller()
        controller.boundary(0)
        # Simulate a crash between appending the event and clearing pending.json.
        write_pending(self.directory, 'duel', [dict(command)])
        controller.boundary(1)
        events = (self.directory / 'control' / 'events.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(events), 1)
        self.assertEqual(show_control(self.directory, 'duel')['duel']['pending'], [])

    def test_cursor_behind_replays_and_cursor_ahead_is_rejected(self):
        queue_control(self.directory, 'duel', {'economy': 0.17}, reason='cursor')
        self.controller().boundary(0)
        behind = self.controller(state=dict(cursor=0,
                                            config=rewards.RewardConfig().to_dict()))
        self.assertEqual(behind.freeze()['economy'], 0.17)
        self.assertEqual(behind.cursor, 1)
        with self.assertRaisesRegex(ValueError, 'checkpoint control cursor is ahead'):
            self.controller(state=dict(cursor=5, config=rewards.RewardConfig().to_dict()))

    def test_checkpoint_mismatch_is_rejected(self):
        queue_control(self.directory, 'duel', {'economy': 0.17}, reason='mismatch')
        self.controller().boundary(0)
        wrong = rewards.RewardConfig(economy=0.19).to_dict()
        with self.assertRaisesRegex(ValueError, 'checkpoint does not match event chain'):
            self.controller(state=dict(cursor=0, config=wrong))

    def test_three_formats_are_applied_independently(self):
        controllers = {fmt: self.controller(fmt) for fmt in FORMATS}
        for fmt in FORMATS:
            queue_control(self.directory, fmt, {'economy': 0.17}, reason=fmt)
        duel = controllers['duel'].boundary(0)
        self.assertEqual(duel['economy'], 0.17)
        for fmt in ('ffa4', 'team2v2'):
            self.assertEqual(controllers[fmt].freeze()['economy'], 0.15)
            self.assertEqual(controllers[fmt].boundary(0)['economy'], 0.17)
        formats = [json.loads(line)['format'] for line in
                   (self.directory / 'control' / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(sorted(formats), sorted(FORMATS))

    def test_invalid_change_keeps_last_valid_config_and_records_error(self):
        controller = self.controller()
        queue_control(self.directory, 'duel', {'economy': 0.17}, reason='valid')
        controller.boundary(0)
        write_pending(self.directory, 'duel', [dict(id='broken', changes={'mode': 'bogus'},
                                                    source='manual', reason='broken',
                                                    queued_at=0)])
        frozen = controller.boundary(1)
        self.assertEqual(frozen['economy'], 0.17)
        self.assertEqual(frozen['mode'], 'adaptive')
        self.assertTrue(controller.last_error)
        self.assertEqual(show_control(self.directory, 'duel')['duel']['pending'], [])
        queue_control(self.directory, 'duel', {'economy': 0.18}, reason='recovered')
        self.assertEqual(controller.boundary(2)['economy'], 0.18)

    def test_duplicate_command_id_is_idempotent(self):
        first = queue_control(self.directory, 'duel', {'economy': 0.17},
                              reason='idempotent', command_id='command-1')
        second = queue_control(self.directory, 'duel', {'economy': 0.17},
                               reason='idempotent', command_id='command-1')
        self.assertEqual(first, second)
        self.controller().boundary(0)
        again = queue_control(self.directory, 'duel', {'economy': 0.17},
                              reason='idempotent', command_id='command-1')
        self.assertEqual(again['command_id'], 'command-1')


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def controller(self, **kwargs):
        return RewardController(self.directory, 'duel', **kwargs)

    @staticmethod
    def metrics(start, count=12, *, new_games=64, **block_overrides):
        return dict(partition='validation', new_games=new_games,
                    validation_blocks=[control_block(start + index, **block_overrides)
                                       for index in range(count)])

    def test_scheduled_change_applies_at_batch_50_not_49(self):
        scheduled = rewards.RewardConfig(mode='scheduled').to_dict()
        controller = self.controller(config=scheduled,
                                     schedule=[dict(batch=50, changes={'economy': 0.18})])
        controller.boundary(49)
        self.assertEqual(controller.freeze()['economy'], 0.15)
        controller.boundary(50)
        self.assertEqual(controller.freeze()['economy'], 0.18)
        controller.boundary(50)
        events = (self.directory / 'control' / 'events.jsonl').read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(events), 1)

    def test_adaptive_requires_sixty_four_games(self):
        controller = self.controller()
        controller.boundary(50, self.metrics(0, new_games=63))
        self.assertEqual(controller.last_check, 0)
        controller.boundary(51, self.metrics(12, new_games=1))
        self.assertEqual(controller.last_check, 51)

    def test_adaptive_requires_fifty_batches(self):
        controller = self.controller()
        controller.boundary(49, self.metrics(0))
        self.assertEqual(controller.last_check, 0)
        controller.boundary(50, self.metrics(12))
        self.assertEqual(controller.last_check, 50)

    def test_eleven_blocks_are_insufficient_and_twelve_are_consumed(self):
        controller = self.controller()
        controller.blocks = [control_block(index) for index in range(11)]
        changes, reason = controller._decision({})
        self.assertEqual(changes, {})
        self.assertEqual(reason, 'insufficient rotation blocks')
        controller.blocks = [control_block(index) for index in range(12)]
        changes, reason = controller._decision({})
        self.assertEqual(changes, {})
        self.assertEqual(reason, 'insufficient rotation blocks')
        self.assertEqual(controller.blocks, [])
        mismatched = [control_block(index, strata=[strata_row(map='map-b')])
                      if index >= 12 else control_block(index, strata=[strata_row()])
                      for index in range(24)]
        controller.windows = []
        controller.blocks = mismatched
        changes, reason = controller._decision({})
        self.assertEqual(changes, {})
        self.assertEqual(reason, 'need two comparable windows')
        self.assertEqual(controller.blocks, [])

    def test_two_comparable_windows_raise_explore_and_control(self):
        controller = self.controller()
        controller.boundary(50, self.metrics(0))
        self.assertEqual(controller.last_check, 50)
        self.assertEqual(controller.freeze()['reward_version'], 0)
        frozen = controller.boundary(100, self.metrics(12))
        self.assertTrue(approx(frozen['explore'], 0.11), frozen)
        self.assertTrue(approx(frozen['control'], 0.11), frozen)
        self.assertEqual(frozen['economy'], 0.15)
        events = [json.loads(line) for line in
                  (self.directory / 'control' / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(events[-1]['source'], 'adaptive')
        self.assertEqual(events[-1]['batch'], 100)

    def test_mismatched_windows_do_not_change_config(self):
        controller = self.controller()
        controller.boundary(50, self.metrics(0))
        different = [control_block(index, strata=[strata_row(map='map-b')])
                     for index in range(12, 24)]
        frozen = controller.boundary(100, dict(partition='validation',
                                               new_games=64,
                                               validation_blocks=different))
        self.assertEqual(frozen['reward_version'], 0)
        self.assertEqual(len(controller.windows), 2)

    def test_rollback_after_two_consecutive_declines(self):
        queue_control(self.directory, 'duel', {'control': 0.11},
                      source='adaptive', reason='seed control increase')
        controller = self.controller()
        controller.boundary(0)
        self.assertEqual(controller.control_previous, 0.1)
        self.assertTrue(approx(controller.freeze()['control'], 0.11))
        for index, (score, observed) in enumerate(((3.0, 0.20), (2.0, 0.21), (1.0, 0.22))):
            start = index * 12
            metrics = self.metrics(start, fixed_score=score,
                                   strata=[strata_row(control_value=observed)])
            controller.boundary(50 * (index + 1), metrics)
        frozen = controller.freeze()
        self.assertTrue(approx(frozen['control'], 0.121 * 0.9, tolerance=1e-9), frozen)
        self.assertLess(frozen['control'], 0.121)
        events = [json.loads(line) for line in
                  (self.directory / 'control' / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertIn('rollback control after two fixed_score declines', events[-1]['reason'])

    def test_six_game_sample_cannot_trigger_adaptive_change(self):
        controller = self.controller()
        controller.boundary(50, self.metrics(0, new_games=6))
        self.assertEqual(controller.last_check, 0)
        self.assertEqual(controller.freeze()['reward_version'], 0)

    def test_holdout_and_final_partitions_are_rejected(self):
        controller = self.controller()
        with self.assertRaisesRegex(ValueError, 'final holdout cannot tune rewards'):
            controller.boundary(50, dict(partition='final', new_games=64))
        with self.assertRaisesRegex(ValueError, 'final holdout cannot tune rewards'):
            controller.boundary(50, dict(partition='validation', new_games=64,
                                         validation_blocks=[control_block(1, partition='holdout')]))

    def test_missing_faulted_and_duplicate_blocks_leave_config_unchanged(self):
        controller = self.controller()
        incomplete = [control_block(0, complete=False),
                      control_block(1, faults=['abort'])]
        controller.boundary(50, dict(partition='validation', new_games=64,
                                     validation_blocks=incomplete))
        self.assertEqual(controller.blocks, [])
        duplicate = [control_block(2), control_block(2)]
        controller.boundary(100, dict(partition='validation', new_games=64,
                                      validation_blocks=duplicate))
        self.assertEqual(len(controller.blocks), 1)
        self.assertEqual(controller.freeze()['reward_version'], 0)

    def test_training_partition_is_tunable_but_holdout_is_not(self):
        controller = self.controller()
        metrics = self.metrics(0)
        metrics['partition'] = 'train'
        controller.boundary(50, metrics)
        self.assertEqual(len(controller.seen_blocks), 12)
        self.assertEqual(controller.last_check, 50)
        with self.assertRaisesRegex(ValueError, 'final holdout cannot tune rewards'):
            controller.boundary(100, dict(partition='test', new_games=64))


class ConfigScheduleTests(unittest.TestCase):
    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.board = dict(width=8, height=6,
                          terrain=[['Gg'] * 8 for _ in range(6)],
                          starts=[[2, 2], [5, 3], [2, 4], [5, 1]])

    def test_cpu_defaults(self):
        with catalog_patch(self.directory / 'no-rules'):
            config = default_config('cpu')
        self.assertEqual(config['workers'], 8)
        self.assertEqual(config['trainer_threads'], 1)
        self.assertEqual(config['device'], 'cpu')
        self.assertEqual(config['final_blocks'], 30)
        self.assertEqual(config['validation_games'], dict(duel=6, ffa4=4, team2v2=8))
        self.assertEqual(config['engine'], 'lite')
        validate_config(config)

    def test_cuda_default_global_workers_is_eight(self):
        config = default_config('cuda')
        self.assertEqual(config['workers'], 8)

    def test_configuration_constraints(self):
        base = default_config('cpu')
        cases = [
            (dict(final_blocks=29), 'formal evaluation needs 30 full blocks per control'),
            (dict(workers=0), 'GLOBAL game process count'),
            (dict(workers=17), 'GLOBAL game process count'),
            (dict(rollout_games=6), 'multiple of four'),
            (dict(rollout_games=0), 'multiple of four'),
            (dict(validation_games=dict(duel=3, ffa4=4, team2v2=8)),
             'full seat rotations'),
            (dict(validation_games=dict(duel=6, ffa4=4, team2v2=4)),
             'both teammate contexts'),
            (dict(formats=['duel', 'duel']), 'formats'),
            (dict(shaping_weight=0.1), 'replace --shaping-weight with control set'),
            (dict(engine='other'), 'engine'),
            (dict(reward_mode='other'), 'unknown reward mode'),
            (dict(bc_accuracy=dict(all=0.4)), 'invalid BC accuracy thresholds'),
            (dict(hours=0), 'hours'),
        ]
        for changes, message in cases:
            config = dict(base, **changes)
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, message):
                    validate_config(config)

    def test_lite_selected_for_complete_accepted_catalog(self):
        accepted = frozen_rules(self.directory / 'accepted')
        with catalog_patch(accepted):
            self.assertEqual(default_config('cpu')['engine'], 'lite')

    def test_pending_catalog_does_not_silently_switch_default_engine(self):
        pending = frozen_rules(self.directory / 'pending', complete=False)
        with catalog_patch(pending):
            self.assertEqual(default_config('cpu')['engine'], 'lite')

    def test_missing_catalog_does_not_silently_switch_default_engine(self):
        with catalog_patch(self.directory / 'missing'):
            self.assertEqual(default_config('cpu')['engine'], 'lite')

    def test_coverage_gate_thresholds(self):
        base = dict(status='complete', coverage=dict(total=100, matched=90, kinds={
            'recruit': dict(total=10, matched=8),
            'move': dict(total=50, matched=40),
            'attack': dict(total=40, matched=32)}))
        self.assertTrue(coverage_gate([dict(base)])['passed'])
        self.assertFalse(coverage_gate([dict(base, coverage=dict(total=100, matched=89,
                                                                  kinds=base['coverage']['kinds']))])['passed'])
        faulted = dict(base, result=dict(faults=['abort']))
        self.assertFalse(coverage_gate([faulted])['passed'])
        ineligible = dict(base, training_eligible=False)
        self.assertFalse(coverage_gate([ineligible])['passed'])
        empty = dict(base, coverage=dict(total=0, matched=0, kinds={}))
        self.assertFalse(coverage_gate([empty])['passed'])

    def test_opening_gate_needs_two_complete_games(self):
        def completed():
            return dict(status='complete', meta=dict(seat=1), result=dict(faults=[]), behavior=[
                dict(side=1,left_castle=True, village_captured=True, end_turn=True,
                     remaining_moves=2,usable_moves=2)])
        self.assertTrue(opening_gate([completed(), completed()])['passed'])
        self.assertFalse(opening_gate([completed()])['passed'])
        broken = completed()
        broken['behavior'] = [dict(side=1,left_castle=False, village_captured=True,
                                   end_turn=True, remaining_moves=2,usable_moves=2)]
        self.assertFalse(opening_gate([completed(), broken])['passed'])

    def _evaluation(self, **kwargs):
        with mock.patch.object(maps, 'frozen_map',
                               lambda name: (copy.deepcopy(self.board), 'sha-' + name)):
            return schedule.evaluation_jobs(self.directory, 'policy', 'control',
                                            ['astra'], 1, 11, 1000.0, None,
                                            **kwargs)

    def test_evaluation_schedule_is_deterministic_and_format_aware(self):
        first = self._evaluation()
        second = self._evaluation()
        self.assertEqual([job['id'] for job in first], [job['id'] for job in second])
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        ids = [job['id'] for job in first]
        self.assertEqual(len(ids), len(set(ids)))
        groups = {}
        for job in first:
            groups.setdefault((job['meta']['format'], job['meta']['block'],
                               job['meta']['context']), []).append(job)
        for (fmt, block, context), jobs in groups.items():
            rotations = {job['meta']['rotation'] for job in jobs}
            self.assertEqual(rotations, set(range(PLAYERS[fmt])))
            self.assertEqual(len(jobs), PLAYERS[fmt])
        self.assertTrue(all(job['meta']['map_partition'] == 'validation' for job in first))
        for fmt in FORMATS:
            self.assertEqual(len([j for j in first if j['meta']['format'] == fmt]),
                             PLAYERS[fmt] * (2 if fmt == 'team2v2' else 1))

    def test_lite_schedule_contains_no_baseline_bots(self):
        jobs = self._evaluation()
        self.assertFalse(any(bot == 'baseline' for job in jobs
                             if job['meta']['context'] != 'baseline_partner'
                             for bot in job['bots']))
        with mock.patch.object(maps, 'frozen_map',
                               lambda name: (copy.deepcopy(self.board), 'sha-' + name)):
            native_jobs = schedule.evaluation_jobs(self.directory, 'policy', 'control',
                                                   ['baseline'], 1, 12, 1000.0, None,
                                                   formats=('team2v2',))
        self.assertTrue(any('baseline' in job['bots'] for job in native_jobs))

    def test_calibration_schedule_pairs_fixed_opponents(self):
        fixed = ['A', 'B', 'C']
        with mock.patch.object(maps, 'frozen_map',
                               lambda name: (copy.deepcopy(self.board), 'sha-' + name)):
            jobs = schedule.calibration_jobs(self.directory, fixed, 1, 3, 1000.0, None,
                                             formats=('duel',))
        pairs = list(combinations(fixed, 2))
        self.assertEqual(len(jobs), len(pairs) * PLAYERS['duel'])
        self.assertEqual({job['id'].split('-')[0] for job in jobs},
                         {f'cal{index:02}' for index in range(len(pairs))})
        self.assertEqual(len({job['id'] for job in jobs}), len(jobs))
        for job in jobs:
            self.assertEqual(job['meta']['map_partition'], 'validation')

    def test_base_job_format_contract(self):
        team = schedule.base_job(self.directory, 'team', ['a'] * 4, 5, time.time() + 10,
                                 None, format_name='team2v2')
        self.assertEqual(team['teams'], [1, 2, 1, 2])
        self.assertEqual(team['max_turns'], 30)
        self.assertEqual(team['factions'], schedule.factions(0, 4))
        duel = schedule.base_job(self.directory, 'duel', ['a', 'b'], 5, time.time() + 10,
                                 None, format_name='duel')
        self.assertIsNone(duel['teams'])

    def test_teacher_and_rollout_schedules(self):
        with self.assertRaisesRegex(ValueError, 'only Astra may provide teacher actions'):
            schedule.teacher_jobs(self.directory, ['/x/other.zip'], ['astra'], {}, 1, 1,
                                  time.time() + 10, None, formats=('duel',))
        with mock.patch.object(maps, 'frozen_map',
                               lambda name: (copy.deepcopy(self.board), 'sha-' + name)):
            teachers = schedule.teacher_jobs(self.directory, ['/x/gpt6astra.zip'], ['astra'],
                                             {}, 1, 1, time.time() + 10, None,
                                             formats=('duel', 'ffa4'))
        self.assertEqual(len(teachers), 2)
        self.assertTrue(all(job['meta']['phase'] == 'teacher' for job in teachers))
        self.assertTrue(all(job['shard'].endswith('.jsonl.gz') for job in teachers))
        self.assertTrue(all('sides' in job['learning'] for job in teachers))
        self.assertEqual(len({job['id'] for job in teachers}), len(teachers))
        with mock.patch.object(maps, 'frozen_map',
                               lambda name: (copy.deepcopy(self.board), 'sha-' + name)):
            rollouts = schedule.rollout_jobs(self.directory, 'policy', '/x/history.pt',
                                             ['astra'], {}, 2, 1, 1, time.time() + 10,
                                             None, formats=('duel',))
        self.assertEqual(len(rollouts), 4)
        self.assertTrue(all(job['meta']['phase'] == 'ppo' for job in rollouts))
        self.assertEqual(len({job['id'] for job in rollouts}), 4)
        self.assertTrue(all(next(iter(job['learning']['sides'].values()))['version'] == 2
                            for job in rollouts))

    def test_freeze_schedule_is_write_once(self):
        jobs = [dict(id='one'), dict(id='two')]
        path = self.directory / 'schedules' / 'unit.json'
        digest = schedule.freeze_schedule(path, jobs)
        self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(schedule.freeze_schedule(path, jobs), digest)
        with self.assertRaisesRegex(ValueError, 'refusing to alter an existing frozen schedule'):
            schedule.freeze_schedule(path, [dict(id='other')])

    def test_lite_experiment_rewrites_baseline_jobs(self):
        experiment = FormatExperiment.__new__(FormatExperiment)
        experiment.directory = self.directory
        experiment.config = dict(engine='lite', allow_approximate=False)
        experiment.teachers = ['/x/gpt6astra.zip']
        experiment.controller = SimpleNamespace(freeze=lambda: helpers.config())
        collected = []
        experiment.collector = lambda pending, log: collected.extend(pending)
        jobs = [dict(id='job-a', bots=['baseline', 'control'],
                     meta=dict(format='team2v2', context='baseline_partner'))]
        returned, results = experiment.execute(jobs, 'unit')
        self.assertEqual(returned[0]['bots'], ['/x/gpt6astra.zip', 'control'])
        self.assertEqual(returned[0]['meta']['context'], 'astra_partner')
        self.assertEqual(returned[0]['engine'], 'lite')
        self.assertEqual(returned[0]['meta']['engine_id'], 'lite')
        self.assertTrue(collected)
        self.assertEqual(results, [])


class BenchmarkReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = benchmark.build_manifest()

    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    @staticmethod
    def group(report_data, key=('duel', 'cold', 'equal_work', 'regular')):
        for group in report_data['groups']:
            if (group['format'], group['cache'], group['mode'], group['density']) == key:
                return group
        raise AssertionError(f'missing benchmark group {key}')

    @staticmethod
    def excluded_reasons(report_data):
        return [reason for item in report_data['excluded_samples']
                for reason in (item['reason'] if isinstance(item['reason'], list)
                               else [item['reason']])]

    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def group_for(self, report_data, fmt='duel', cache='cold', mode='equal_work',
                  density='regular'):
        return next(group for group in report_data['groups']
                    if (group['format'], group['cache'], group['mode'],
                        group['density']) == (fmt, cache, mode, density))

    def group_workloads(self, manifest, key):
        fmt, cache, mode, density = key
        return [work for work in manifest['workloads']
                if (work['format'], work['cache'], work['mode'], work['density'])
                == (fmt, cache, mode, density)]

    def samples(self, manifest, workloads, *, actions=lambda work, engine: 10,
                pss=lambda work, engine: 500.0 if engine == 'native' else 100.0,
                turns=3):
        rows = []
        for work in workloads:
            for engine, wall, cpu in (('native', 10.0, 20.0), ('lite', 1.0, 2.0)):
                rows.append(dict(
                    manifest_id=manifest['manifest_id'], workload_id=work['id'],
                    engine=engine, wall_seconds=wall, cpu_core_seconds=cpu,
                    peak_rss_bytes=1000.0, peak_pss_bytes=pss(work, engine),
                    disk_bytes=10.0, startup_seconds=1.0,
                    cpu_scope='process_tree_including_coordinator',
                    host_id='host-1', cpu_quota='quota-1',
                    workers=work['workers'], inference='cpu', threads=1,
                    components_seconds={name: 1.0 for name in benchmark.COMPONENTS},
                    actions=actions(work, engine), turns=turns,
                    terminal_reason='victory', cache_aligned=True,
                    work_signature=f"work-{work['block']}"))
        return rows

    def test_manifest_requires_thirty_complete_rotation_blocks(self):
        self.assertEqual(self.manifest['version'], 1)
        self.assertEqual(self.manifest['native_version'], '1.18.8')
        self.assertEqual(self.manifest['observation_schema'], features.VERSION)
        self.assertEqual(self.manifest['minimum_complete_rotation_blocks'], 30)
        self.assertEqual(self.manifest['required_speedup'], 5)
        self.assertEqual(self.manifest['required_cpu_ratio'], 5)
        self.assertEqual(self.manifest['resource_memory_ratio_target'], 1.3)
        self.assertIn('30% lower', self.manifest['acceptance'])
        groups = {}
        for work in self.manifest['workloads']:
            key = (work['format'], work['cache'], work['mode'],
                   work['density'], work['workers'])
            groups.setdefault(key, []).append(work)
            self.assertEqual(work['workers'], 1)
        self.assertEqual(len(groups), 3 * 2 * 2 * 2)
        for key, workloads in groups.items():
            blocks = {work['block'] for work in workloads}
            self.assertEqual(blocks, set(range(30)))
            self.assertEqual(len(workloads), 30 * PLAYERS[key[0]])
        self.assertEqual(benchmark.build_manifest()['manifest_id'],
                         self.manifest['manifest_id'])

    def test_thirty_blocks_pass_and_ratios_are_separate(self):
        workloads = self.group_workloads(self.manifest,
                                         ('duel', 'cold', 'equal_work', 'regular'))
        report_data = benchmark.benchmark_report(self.samples(self.manifest, workloads),
                                                 self.manifest)
        group = self.group_for(report_data)
        self.assertEqual(group['complete_rotation_blocks'], 30)
        self.assertEqual(group['missing_blocks'], [])
        self.assertEqual(group['unequal_work_blocks'], [])
        self.assertTrue(approx(group['wall_speedup'], 10.0))
        self.assertTrue(approx(group['cpu_ratio'], 10.0))
        self.assertTrue(approx(group['memory_pss_ratio'], 5.0))
        self.assertEqual(len(group['wall_speedup_ci95']), 2)
        self.assertEqual(len(group['cpu_ratio_ci95']), 2)
        self.assertEqual(group['status'], 'passed')
        self.assertNotEqual(report_data['status'], 'passed')
        self.assertFalse(report_data['artifacts_frozen'])
        self.assertEqual(group['engines']['native']['wall_seconds']['samples'], 60)
        self.assertEqual(group['engines']['lite']['wall_seconds']['p50'], 1.0)
        self.assertEqual(group['engines']['lite']['wall_seconds']['p95'], 1.0)
        self.assertEqual(group['engines']['native']['peak_pss_bytes']['p50'], 500.0)

    def test_memory_accepts_thirty_percent_reduction_but_not_less(self):
        workloads = self.group_workloads(self.manifest,
                                         ('duel', 'cold', 'equal_work', 'regular'))
        passing = benchmark.benchmark_report(
            self.samples(self.manifest, workloads,
                         pss=lambda work, engine: 500.0 if engine == 'native' else 500.0 / 1.3),
            self.manifest)
        group = self.group_for(passing)
        self.assertTrue(approx(group['memory_pss_ratio'], 1.3))
        self.assertEqual(group['status'], 'passed')
        failing = benchmark.benchmark_report(
            self.samples(self.manifest, workloads,
                         pss=lambda work, engine: 500.0 if engine == 'native' else 500.0 / 1.29),
            self.manifest)
        self.assertEqual(self.group_for(failing)['status'], 'failed')

    def test_missing_component_attribution_does_not_erase_measured_resources(self):
        workloads = self.group_workloads(self.manifest,
                                         ('duel', 'cold', 'equal_work', 'regular'))
        samples = self.samples(self.manifest, workloads)
        for sample in samples:
            sample['components_seconds'] = None
        result = benchmark.benchmark_report(samples, self.manifest)
        group = self.group_for(result)
        self.assertEqual(group['status'], 'passed')
        self.assertTrue(approx(group['wall_speedup'], 10.0))
        self.assertEqual(result['component_diagnostics']['status'], 'inconclusive')
        self.assertEqual(group['engines']['native']['components_seconds']['teacher']['samples'], 0)
        self.assertIsNone(group['engines']['native']['components_seconds']['teacher']['p50'])

    def test_twenty_nine_blocks_are_inconclusive(self):
        workloads = [work for work in
                     self.group_workloads(self.manifest,
                                          ('duel', 'cold', 'equal_work', 'regular'))
                     if work['block'] < 29]
        report_data = benchmark.benchmark_report(self.samples(self.manifest, workloads),
                                                 self.manifest)
        group = self.group_for(report_data)
        self.assertEqual(group['complete_rotation_blocks'], 29)
        self.assertEqual(group['missing_blocks'], [29])
        self.assertIsNone(group['wall_speedup'])
        self.assertIsNone(group['memory_pss_ratio'])
        self.assertEqual(group['status'], 'inconclusive')

    def test_missing_pss_is_never_replaced_by_rss(self):
        workloads = self.group_workloads(self.manifest,
                                         ('duel', 'cold', 'equal_work', 'regular'))
        zero = self.samples(self.manifest, workloads,
                            pss=lambda work, engine: 0.0 if (work['block'] == 3 and
                                                             engine == 'lite') else
                            (500.0 if engine == 'native' else 100.0))
        for sample in zero:
            sample['peak_rss_bytes'] = 999999.0
        report_data = benchmark.benchmark_report(zero, self.manifest)
        group = self.group_for(report_data)
        self.assertEqual(group['missing_blocks'], [3])
        self.assertIsNone(group['memory_pss_ratio'])
        self.assertEqual(group['status'], 'inconclusive')
        self.assertIn('nonpositive_required_resources', self.excluded_reasons(report_data))
        absent = self.samples(self.manifest, workloads,
                              pss=lambda work, engine: None if (work['block'] == 4 and
                                                                engine == 'lite') else
                              (500.0 if engine == 'native' else 100.0))
        report_data = benchmark.benchmark_report(absent, self.manifest)
        self.assertIn('missing_or_invalid_resources', self.excluded_reasons(report_data))
        self.assertIsNone(self.group_for(report_data)['memory_pss_ratio'])

    def test_equal_work_mismatch_is_rejected(self):
        workloads = self.group_workloads(self.manifest,
                                         ('duel', 'cold', 'equal_work', 'regular'))
        samples = self.samples(self.manifest, workloads,
                               actions=lambda work, engine: 11 if
                               (work['block'] == 5 and engine == 'lite') else 10)
        group = self.group_for(benchmark.benchmark_report(samples, self.manifest))
        self.assertEqual(group['unequal_work_blocks'], [5])
        self.assertEqual(group['missing_blocks'], [])
        self.assertEqual(group['complete_rotation_blocks'], 29)

    def test_end_to_end_different_finish_is_not_comparable(self):
        workloads = self.group_workloads(self.manifest,
                                         ('duel', 'cold', 'end_to_end', 'regular'))
        samples = self.samples(self.manifest, workloads)
        for sample in samples:
            if sample['engine'] == 'lite':
                sample['terminal_reason'] = 'turn_limit'
        group = self.group_for(benchmark.benchmark_report(samples, self.manifest),
                               mode='end_to_end')
        self.assertEqual(group['complete_rotation_blocks'], 0)
        self.assertEqual(group['unequal_work_blocks'], list(range(30)))
        self.assertIsNone(group['wall_speedup'])
        self.assertEqual(group['status'], 'inconclusive')

    def test_mixed_pipeline_multiplier_uses_actual_totals(self):
        native = dict(wall_seconds=100.0, cpu_core_seconds=100.0,
                      work_signature='same-work')
        four = benchmark.pipeline_report(native, dict(wall_seconds=25.0,
                                                      cpu_core_seconds=25.0,
                                                      work_signature='same-work'))
        self.assertTrue(approx(four['wall_speedup'], 4.0))
        self.assertTrue(approx(four['cpu_ratio'], 4.0))
        self.assertEqual(four['status'], 'failed')
        five = benchmark.pipeline_report(native, dict(wall_seconds=20.0,
                                                      cpu_core_seconds=20.0,
                                                      work_signature='same-work'))
        self.assertEqual(five['status'], 'passed')
        mismatch = benchmark.pipeline_report(native, dict(wall_seconds=20.0,
                                                          cpu_core_seconds=20.0,
                                                          work_signature='other-work'))
        self.assertEqual(mismatch['status'], 'inconclusive')
        missing = benchmark.pipeline_report(dict(work_signature='same-work'),
                                            dict(wall_seconds=20.0))
        self.assertEqual(missing['status'], 'inconclusive')

    def test_secondary_workers_wait_for_single_worker_evidence(self):
        self.assertTrue(all(work['workers'] == 1 for work in self.manifest['workloads']))
        workloads = self.group_workloads(self.manifest,
                                         ('duel', 'cold', 'equal_work', 'regular'))
        report_data = benchmark.benchmark_report(self.samples(self.manifest, workloads),
                                                 self.manifest)
        self.assertEqual(report_data['secondary_workers'],
                         dict(status='inconclusive', required=[4, 8]))
        self.assertTrue(all(group['workers'] == 1 for group in report_data['groups']))

    def test_fault_duplicate_and_unknown_samples_are_excluded(self):
        workloads = self.group_workloads(self.manifest,
                                         ('duel', 'cold', 'equal_work', 'regular'))
        samples = self.samples(self.manifest, workloads)
        samples[0]['faults'] = ['abort']
        samples.append(dict(samples[1]))
        samples.append(dict(samples[2], workload_id='unknown-workload'))
        samples.append(dict(samples[3], engine='compiled'))
        report_data = benchmark.benchmark_report(samples, self.manifest)
        reasons = self.excluded_reasons(report_data)
        flattened = [reason for item in reasons
                     for reason in (item if isinstance(item, list) else [item])]
        self.assertIn('faulted_game', flattened)
        self.assertIn('duplicate_sample', flattened)
        self.assertIn('unknown_workload', flattened)
        self.assertIn('unknown_engine', flattened)

    def test_run_benchmarks_with_tiny_doubles_never_claims_pass(self):
        work = dict(id='tiny-work', format='duel', cache='cold', mode='equal_work',
                    density='regular', block=0, seat=1, workers=1, inference='cpu',
                    threads=1)
        tiny = dict(manifest_id='tiny-manifest', workloads=[work], artifacts={})
        calls = []

        def runner(selected):
            calls.append(selected['id'])
            return dict(wall_seconds=10.0, cpu_core_seconds=20.0,
                        peak_rss_bytes=1000.0, peak_pss_bytes=500.0,
                        disk_bytes=1.0, startup_seconds=0.5,
                        cpu_scope='process_tree_including_coordinator',
                        host_id='host', cpu_quota='quota', workers=1,
                        inference='cpu', threads=1,
                        components_seconds={name: 1.0 for name in benchmark.COMPONENTS},
                        actions=10, turns=3, terminal_reason='victory',
                        cache_aligned=True, work_signature='tiny')
        output = self.directory / 'tiny-benchmark'
        report_data = benchmark.run_benchmarks({'native': runner, 'lite': runner},
                                               tiny, output)
        self.assertEqual(calls, ['tiny-work', 'tiny-work'])
        self.assertTrue((output / 'manifest.json').is_file())
        raw = [json.loads(line) for line in
               (output / 'raw.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([sample['engine'] for sample in raw], ['native', 'lite'])
        self.assertEqual(report_data['status'], 'inconclusive')
        written = json.loads((output / 'report.json').read_text(encoding='utf-8'))
        self.assertNotEqual(written['status'], 'passed')
        self.assertFalse(written['artifacts_frozen'])

    def test_trend_panel_every_ten_updates(self):
        history = [dict(batch=index, method='ppo', elapsed_hours=index * 0.1,
                        updates=index, loss=1.0 / max(1, index), interrupted=False)
                   for index in range(1, 21)]
        summary = dict(format='duel', status='inconclusive', controls={},
                       selected_kind='bc', version=1, parameters=10,
                       pretraining_complete=True, bc_games_collected=1,
                       bc_games_required=1, checkpoint_sha256='a' * 64)
        report.write_profile_report(self.directory / 'trend', summary, history)
        text = (self.directory / 'trend' / 'REPORT.md').read_text(encoding='utf-8')
        self.assertIn('Panel sampled every 10 updates', text)
        trend = text.split('## Trend', 1)[1]
        self.assertIn('| 10 |', trend)
        self.assertIn('| 20 |', trend)


class ReportSchemaTests(unittest.TestCase):
    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def summary(self):
        return dict(
            format='duel', status='inconclusive',
            controls={'fixed': dict(blocks=30, planned_blocks=30, fault_games=0,
                                    difference=0.01, interval95=[0.0, 0.02],
                                    status='passed',
                                    contexts={
                                        'baseline_partner': dict(blocks=15, difference=0.01,
                                                                 interval95=[0.0, 0.02]),
                                        'self_team': dict(blocks=15, difference=0.0,
                                                          interval95=[-0.01, 0.01])})},
            selected_kind='bc', version=3, parameters=123,
            pretraining_complete=True, bc_games_collected=10,
            bc_games_required=10, checkpoint_sha256='b' * 64)

    def test_profile_report_keeps_contexts_separate(self):
        directory = self.directory / 'profile'
        report.write_profile_report(directory, self.summary(),
                                    [dict(batch=1, method='ppo', elapsed_hours=0.1,
                                          updates=1, loss=1.0, interrupted=False)])
        text = (directory / 'REPORT.md').read_text(encoding='utf-8')
        self.assertIn('baseline_partner', text)
        self.assertIn('self_team', text)
        self.assertIn('inconclusive', text)
        self.assertIn('| Control | Complete blocks | Planned blocks |', text)
        self.assertIn('95% interval', text)
        self.assertIn('| fixed | 30 | 30 |', text)
        self.assertIn('| ↳ baseline_partner | 15 |', text)
        self.assertTrue((directory / 'summary.json').is_file())
        self.assertTrue((directory / 'training.csv').is_file())
        self.assertEqual(json.loads((directory / 'summary.json').read_text(encoding='utf-8')),
                         self.summary())

    def test_markdown_starts_with_conclusion_and_blockers(self):
        directory = self.directory / 'markdown'
        report.write_profile_report(directory, self.summary(), [])
        text = (directory / 'REPORT.md').read_text(encoding='utf-8')
        head = '\n'.join(text.splitlines()[:4])
        self.assertIn('Conclusion', head)
        self.assertIn('Blockers', head)

    def test_section_ten_report_schema_exists(self):
        builder = getattr(report, 'build_report', None)
        self.assertIsNotNone(builder, 'KNOWN BUG: learning/report.py only writes the per-format '
                                      'profile report; no §10 report schema builder exists')
        required = ('report_version', 'stage', 'status', 'revision', 'source_sha256',
                    'command', 'started_at', 'finished_at', 'host', 'versions',
                    'format', 'context', 'counts', 'checks', 'metrics',
                    'known_differences', 'implementation_gaps', 'artifacts',
                    'next_required_action')
        produced = builder(stage='unit', checks=[], metrics={})
        for key in required:
            self.assertIn(key, produced)

    def test_report_with_only_not_run_checks_is_not_run(self):
        produced = report.build_report(stage='P2', checks=[dict(
            id='P2.performance', status='not_run', reason='no accepted rules')],
            metrics={'wall_ratio': None})
        self.assertEqual(produced['status'], 'not_run')
        self.assertFalse(produced['stage_exit']['met'])

    def test_cli_report_never_claims_passed_without_full_blocks(self):
        jobs, results = [], []
        for fmt in FORMATS:
            contexts = ('baseline_partner', 'self_team') if fmt == 'team2v2' else ('solo',)
            for context in contexts:
                for rotation in range(PLAYERS[fmt]):
                    identifier = f'{fmt}-{context}-{rotation}'
                    jobs.append(dict(id=identifier, meta=dict(
                        format=fmt, control='fixed', block=0, label='selected',
                        context=context, rotation=rotation, policy_sides=[1],
                        control_sides=[2])))
                    results.append(dict(id=identifier, status='complete', result=dict(
                        bots=['astra'] * PLAYERS[fmt], faults=[], winner=1,
                        winning_team=0, teams=[1, 2, 1, 2] if fmt == 'team2v2' else None,
                        rank_points={str(index): 0.5
                                     for index in range(1, PLAYERS[fmt] + 1)})))
        jobs_path = self.directory / 'jobs.json'
        results_path = self.directory / 'results.json'
        output_path = self.directory / 'report.json'
        jobs_path.write_text(json.dumps(jobs), encoding='utf-8')
        results_path.write_text(json.dumps(results), encoding='utf-8')
        from learning.__main__ import main
        main(['report', '--jobs', str(jobs_path), '--results', str(results_path),
              '--output', str(output_path)])
        produced = json.loads(output_path.read_text(encoding='utf-8'))
        self.assertNotEqual(produced['status'], 'passed')
        self.assertEqual(set(produced['formats']), set(FORMATS))
        for fmt, controls in produced['formats'].items():
            self.assertEqual(set(controls), {'fixed'})
            self.assertEqual(controls['fixed']['blocks'], 1)
            self.assertNotEqual(controls['fixed']['status'], 'passed')

    def test_missing_metrics_are_null_with_a_reason(self):
        builder = getattr(report, 'build_report', None)
        self.assertIsNotNone(builder, 'KNOWN BUG: no §10 report schema builder exists')
        produced = builder(stage='unit', checks=[], metrics={'speedup': None,
                                                             'games': 0})
        self.assertIsNone(produced['metrics']['speedup'])
        self.assertEqual(produced['metrics']['games'], 0)
        self.assertIn('speedup', produced['missing'])
        self.assertTrue(produced['missing']['speedup'])
        self.assertNotIn('games', produced['missing'])
        for value in produced['counts'].values():
            self.assertIsNone(value)
        self.assertIsInstance(produced['implementation_gaps'], list)

    def test_stage_exit_condition_is_explicit(self):
        builder = getattr(report, 'build_report', None)
        self.assertIsNotNone(builder, 'KNOWN BUG: no §10 report schema builder exists')
        blocked = builder(stage='unit', checks=[dict(id='perf', status='blocked',
                                                     reason='no native binary')],
                          metrics={'speedup': None},
                          stage_exit=dict(condition='wall and cpu ratios >= 5'))
        self.assertEqual(blocked['status'], 'inconclusive')
        self.assertFalse(blocked['stage_exit']['met'])
        passed = builder(stage='unit', checks=[dict(id='perf', status='passed')],
                         metrics={'speedup': 5.0},
                         stage_exit=dict(condition='wall and cpu ratios >= 5'))
        self.assertEqual(passed['status'], 'passed')
        self.assertTrue(passed['stage_exit']['met'])
        text = report.report_markdown(blocked)
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith('# '))
        head = '\n'.join(lines[:4])
        self.assertIn('Conclusion', head)
        self.assertIn('Blockers', head)
        self.assertIn('perf: no native binary', head)
        self.assertLess(text.index('Conclusion'), text.index('## Checks'))

    def test_passed_status_cannot_override_blocked_checks(self):
        produced = report.build_report(status='passed',
                                       checks=[dict(id='perf', status='blocked',
                                                    reason='no native binary')],
                                       metrics={'speedup': None})
        self.assertNotEqual(produced['status'], 'passed')


class PackageManifestTests(unittest.TestCase):
    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def test_package_excludes_private_runtime_data(self):
        output = self.directory / 'bundle.zip'
        package.package_project(output)
        import zipfile
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
        self.assertTrue(names)
        self.assertTrue(all(name.startswith('WesnothLearning/') for name in names))
        excluded = {'.venv', '.cache', '.runtime', '.ssh', 'runs', 'verification',
                    'tmp', 'delivery', '.git', 'references', 'humanData', 'datasets',
                    '__pycache__'}
        for name in names:
            parts = set(name.split('/'))
            self.assertFalse(parts & excluded, name)
            self.assertFalse(name.endswith('.pyc'))
        sidecar = output.with_suffix('.json')
        self.assertTrue(sidecar.is_file())
        data = json.loads(sidecar.read_text(encoding='utf-8'))
        self.assertEqual(data['sha256'], hashlib.sha256(output.read_bytes()).hexdigest())

    def test_tree_hashes_detect_changed_source_tree(self):
        root = manifest.ROOT / 'tmp'
        root.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix='manifest-', dir=root))
        self.addCleanup(lambda: __import__('shutil').rmtree(directory, ignore_errors=True))
        (directory / 'lua').mkdir()
        (directory / 'lua' / 'bot.lua').write_text('return 1\n', encoding='utf-8')
        (directory / '__pycache__').mkdir()
        (directory / '__pycache__' / 'x.pyc').write_bytes(b'ignored')
        (directory / 'teacher.zip').write_bytes(b'teacher')
        (directory / 'wesnoth.exe').write_bytes(b'engine')
        relative = str(directory.relative_to(manifest.ROOT))
        data = dict(opponents=[dict(path=str(directory / 'teacher.zip'),
                                    sha256='0' * 64)],
                    baseline=dict(path=str(directory / 'wesnoth.exe'), sha256='0' * 64),
                    source={relative: manifest.tree_hashes(directory)})
        data['opponents'][0]['sha256'] = manifest.sha256(directory / 'teacher.zip')
        data['baseline']['sha256'] = manifest.sha256(directory / 'wesnoth.exe')
        manifest.verify_frozen(data)
        (directory / 'teacher.zip').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'frozen opponent changed'):
            manifest.verify_frozen(data)
        (directory / 'teacher.zip').write_bytes(b'teacher')
        (directory / 'wesnoth.exe').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'official runtime changed'):
            manifest.verify_frozen(data)
        (directory / 'wesnoth.exe').write_bytes(b'engine')
        (directory / 'lua' / 'bot.lua').write_text('return 2\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'source changed since the experiment started'):
            manifest.verify_frozen(data)

    def test_freeze_writes_hashed_manifest_and_verifies(self):
        opponents = self.directory / 'opponents'
        opponents.mkdir()
        source = opponents / 'gpt6astra.zip'
        source.write_bytes(b'synthetic addon')
        exe = self.directory / 'wesnoth.exe'
        exe.write_bytes(b'synthetic native')
        run_dir = self.directory / 'run'

        @contextlib.contextmanager
        def open_addon(path):
            yield Path(path)

        fake_native = SimpleNamespace(find_wesnoth=lambda value=None: str(exe))
        with mock.patch.object(manifest, 'native', fake_native), \
                mock.patch.object(manifest, 'addons', SimpleNamespace(
                    open_addon=open_addon, validate=lambda addon: 'gpt6astra')):
            frozen, teachers = manifest.freeze(run_dir, opponents, None,
                                               default_config('cpu'))
        self.assertTrue((run_dir / 'manifest.json').is_file())
        self.assertEqual(len(teachers), 1)
        self.assertEqual(frozen['schema'], 4)
        for folder in ('learning', 'lua', 'vendor/arena', 'engine_lite', 'rules', 'benchmarks'):
            self.assertIn(folder, frozen['source'])
        self.assertEqual(frozen['opponents'][0]['sha256'], manifest.sha256(teachers[0]))
        manifest.verify_frozen(frozen)
        Path(teachers[0]).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'frozen opponent changed'):
            manifest.verify_frozen(frozen)

    def test_output_path_rejects_paths_outside_the_project(self):
        inside = manifest.output_path('runs/unit.json')
        self.assertTrue(str(inside).startswith(str(manifest.ROOT)))
        with self.assertRaisesRegex(ValueError, 'output must be inside WesnothLearning'):
            manifest.output_path(self.directory / 'outside.json'
                                 if not str(self.directory).startswith(str(manifest.ROOT))
                                 else '..' / Path('outside.json'))


if __name__ == '__main__':
    unittest.main()
