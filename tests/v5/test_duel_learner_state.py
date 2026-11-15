"""Fixed archived-label comparison fixtures, with zero formal optimization or games."""
import copy
import gzip
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import torch

from learning.bc_anchor import weights_sha256
from learning.checkpoints import checkpoint
from learning.common import read_json
from learning.coverage import FIELDS
from learning.data import record_split
from learning.export import export, load_model
from learning.lite_policy import FrozenPolicies
from learning.rowpack import ROW_SCHEMA, pack_line
from learning.tasks import TASK_ID, reward_config
from tests.v5 import helpers
from verification.duel_learner_state_20261115 import corpus
from verification.duel_learner_state_extended_20261115 import driver, protocol, trainer

VERSION = 'schema5-work-12000-v8'
OBJECTIVE = dict(learning_rate=.0003, max_grad_norm=.5, marginal_weight=.1)


class ArchivedLearnerTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        previous = torch.get_num_threads()
        torch.set_num_threads(1)
        self.addCleanup(torch.set_num_threads, previous)

    def write(self, name, rows):
        path = self.root/name
        with gzip.open(path, 'wt', encoding='utf-8') as stream:
            for row in rows:
                stream.write(pack_line(row)+'\n')
        return str(path), corpus.file_sha(path)

    def game(self):
        game = dict(partition='train', game='fixture-game', family='fixture-family',
                    board='same-physical-layout', seat=1, faction='Loyalists', rows=3, version='v38')
        for i in range(10):
            header = dict(scenario_family=f'fixture-scenario-{i}', split_rule='scenario-v2')
            if record_split(header) == 'train':
                break
        game['scenario'] = header['scenario_family']
        rows = helpers.sequence_rows(3, decisions_per_turn=1, source='policy')
        config = reward_config(mode='fixed')
        for index, row in enumerate(rows, 1):
            row.update(header, decision=index, game_id=game['game'], game_family=game['family'],
                       schema=ROW_SCHEMA, task_id=TASK_ID, reward_config=config,
                       reward_formula_id=config['reward_formula_id'], source='policy', version='v38',
                       candidate_version=VERSION, rules_sha256=corpus.BASE['rules_sha256'],
                       engine_id='lite', engine='lite', engine_version=helpers.ENGINE_VERSION,
                       terminal_reward=0., reward_step=0., value_valid=False, faction=game['faction'],
                       split='train', committed=True, faults=[])
            row['memory_write'] = {key: copy.deepcopy(row[key]) for key in ('global', 'opponents', 'spatial', 'turn')}
            row['memory_write']['global'][0] = index/8
        game['shard'], game['sha256'] = self.write('policy.jsonl.gz', rows)
        label = copy.deepcopy(rows[-1])
        choice, candidate = next((i, c) for i, c in enumerate(label['candidates']) if c['kind'] in corpus.TARGET_KINDS)
        actual = {key: candidate[key] for key in ('kind', *FIELDS[candidate['kind']])}
        label.update(source='astra', teacher='gpt6astra', query_only=True, choice=choice, actual=actual)
        label['memory_write']['global'][0] = .875
        game['labels'], game['labels_sha256'] = self.write('sparse-labels.jsonl.gz', [label])
        return game, label

    def test_sparse_labels_use_full_learner_memory_and_exact_public_candidate(self):
        game, label = self.game()
        (decision, (row, stratum)), = trainer.selected_rows(game, {3}, protocol.TREATMENT, VERSION)
        self.assertEqual(decision, 3)
        self.assertEqual(row['choice'], label['choice'])
        self.assertEqual([past['turn'] for past in row['_history']], [1, 2])
        self.assertEqual([past['global'][0] for past in row['_history']], [.125, .25])
        self.assertEqual(stratum[:4], (game['board'], game['seat'], game['faction'], label['actual']['kind']))
        with self.assertRaisesRegex(ValueError, 'ineligible or changed shard'):
            list(trainer.selected_rows(dict(game, partition='validation'), {3}, protocol.TREATMENT, VERSION))

    def test_treatment_sends_learner_rows_into_actor_step_and_greedy_reload(self):
        game, _ = self.game()
        (_, (learner, _)), = trainer.selected_rows(game, {3}, protocol.TREATMENT, VERSION)
        teacher = copy.deepcopy(learner)
        teacher['global'][0] = .75
        step = dict(shared=[[0, i] for i in range(48)], swaps=[[[1, i], [2, i]] for i in range(16)])
        teacher_refs = list(trainer.matched_refs(step, protocol.CONTROL))
        learner_refs = list(trainer.matched_refs(step, protocol.TREATMENT))
        self.assertEqual(teacher_refs[:48], learner_refs[:48])
        self.assertEqual(learner_refs[48:], [('learner', (2, i)) for i in range(16)])
        targets = {ref: teacher for ref in teacher_refs} | {ref: learner for ref in learner_refs[48:]}
        initial = helpers.model()
        weights = weights_sha256(initial.state_dict())
        initial_value = weights_sha256(initial.value.state_dict())

        def run(rows):
            model = copy.deepcopy(initial).train()
            model.value.requires_grad_(False)
            optimizer = torch.optim.Adam((p for p in model.parameters() if p.requires_grad),
                                         lr=OBJECTIVE['learning_rate'])
            loss = trainer.update_step(model, optimizer, rows, OBJECTIVE)
            self.assertGreater(loss, 0.)
            self.assertEqual(weights_sha256(model.value.state_dict()), initial_value)
            self.assertEqual({int(record['step']) for record in optimizer.state.values()}, {1})
            return model, optimizer

        control_rows = [targets[ref] for ref in teacher_refs]
        treatment_rows = [targets[ref] for ref in learner_refs]
        control, _ = run(control_rows)
        repeat, _ = run(control_rows)
        variant, optimizer = run(treatment_rows)
        self.assertEqual(weights_sha256(control.state_dict()), weights_sha256(repeat.state_dict()))
        self.assertNotEqual(weights_sha256(variant.state_dict()), weights)
        self.assertNotEqual(weights_sha256(control.state_dict()), weights_sha256(variant.state_dict()))
        checkpoint(self.root/'model.pt', variant, optimizer, task_id=TASK_ID)
        loaded, _ = load_model(self.root/'model.pt', 'duel')
        self.assertEqual(weights_sha256(loaded.state_dict()), weights_sha256(variant.state_dict()))
        addon = export(loaded, self.root, name='FixtureDuel', mode='greedy', package=False)
        frozen = FrozenPolicies(dict(bots=[str(addon), 'astra'], seed=9, format='duel'))
        frozen.histories[1].extend(learner['_history'])
        self.assertFalse(frozen.modes[1])
        choice = frozen.choose(learner, 1)['choice']
        self.assertIn(choice, range(len(learner['candidates'])))

    def test_all_frozen_roles_and_both_contrasts_are_scored(self):
        inputs = read_json(driver.INPUTS_PATH)
        jobs, results = [], []
        for index, slot in enumerate(inputs['slots']):
            seat = slot['seat']
            for role in protocol.ROLES:
                meta = {key: slot[key] for key in ('map', 'block', 'rotation')} | dict(role=role, policy_sides=[seat])
                job = dict(id=f'{index}-{role}', seed=slot['seed'], meta=meta, scenario_family=slot['scenario'],
                           factions=slot['factions'], bots=['x', 'y'])
                winner = seat if role.startswith('learner-') else 0 if role == 'bc' else 3-seat
                result = dict(task_terminal=True, task_id=TASK_ID, faults=[], winner=winner,
                              bots=job['bots'], factions=job['factions'])
                jobs.append(job)
                results.append(dict(id=job['id'], status='complete', meta=meta, engine='lite', result=result))
        summary = driver.recount(jobs, results, inputs)
        self.assertEqual(summary['differences']['b_minus_a'], 1.)
        self.assertAlmostEqual(summary['differences']['b_minus_bc'], 2/3)
        self.assertTrue(summary['passed'])
        with self.assertRaisesRegex(ValueError, 'missing or duplicate'):
            driver.recount(jobs, results[:-1], inputs)

    def test_score_gate_treats_exact_five_points_and_zero_lower_bound_as_frozen(self):
        stats = dict(differences=dict(b_minus_a=.45-.4, b_minus_bc=.45-.4),
                     interval95=dict(b_minus_a=[1/1620, .12], b_minus_bc=[1/1620, .10]))
        self.assertTrue(driver.adoption_gate(stats, .05, 90))
        stats['interval95']['b_minus_bc'][0] = 1e-16
        self.assertFalse(driver.adoption_gate(stats, .05, 90))
