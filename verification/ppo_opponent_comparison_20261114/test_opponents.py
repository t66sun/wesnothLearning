from copy import deepcopy
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, patch

from learning import experiment
from learning.common import read_json, sha256, write_json
from learning.lite_policy import FrozenPolicies
from tests.v5 import helpers
from verification.ppo_batch_contract_20261107.driver import ordinal_rollouts
from verification.ppo_terminal_return_20261108.driver import PARENT, RULES
from . import opponents


class OpponentComparisonTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(helpers.temporary_directory())
        self.astra = read_json(PARENT / 'manifest.json')['opponents'][0]['path']
        self.bc = dict(path=str(self.root / 'FrozenDuelBC'), weights_sha256='fixture')

    def jobs(self, arm, offset):
        kwargs = dict(first_batch=38, contract=dict(arm=arm, astra=self.astra, bc=self.bc))
        return opponents.rollouts(self.root, 'learner', ['history'], [self.astra], 'support',
                                  'v38', 38+offset, 202611141, time.time()+60,
                                  'unused', **kwargs)

    def test_exact_mix_and_unchanged_ordinal_stream(self):
        for offset in range(27):
            baseline = self.jobs('astra', offset)
            mixed = self.jobs('mixed', offset)
            previous = ordinal_rollouts(self.root, 'learner', ['history'], [self.astra],
                                        'support', 'v38', 38+offset, 202611141, 0,
                                        'unused', 8, first_batch=38)
            selected = [job for job in mixed if self.bc['path'] in job['bots']]
            self.assertEqual(len(selected), 2)
            self.assertEqual({job['meta']['seat'] for job in selected}, {1, 2})
            for g, (a, b, c) in enumerate(zip(baseline, mixed, previous, strict=True)):
                seat = a['meta']['seat']
                self.assertEqual(a['bots'][2-seat], self.astra)
                self.assertEqual(b['bots'][seat-1], 'learner')
                self.assertEqual(b['meta']['experimental_opponent']['ordinal'], offset*8+g)
                for key in ('id', 'seed', 'factions', 'map_override', 'learning',
                            'training_scenario', 'scenario_family', 'game_family'):
                    self.assertEqual(a[key], c[key])
                    self.assertEqual(b[key], c[key])
                self.assertEqual(set(b['learning']['sides']), {str(seat)})

    def test_exact_resume_reuses_frozen_jobs_and_rejects_opponent_drift(self):
        runner = object.__new__(opponents.OpponentExperiment)
        runner.directory = self.root / 'duel'
        runner.teachers = [self.astra]
        runner.config = dict(task_id='official-score-30-v1', engine='lite', rules_dir=str(RULES),
                             training_max_turns=30, rollout_games=8, allow_approximate=True)
        runner.controller = Mock()
        runner.controller.freeze.return_value = {}
        name = 'ppo-batch-00038'
        captured = []
        def collect(jobs, log):
            captured.append(deepcopy(jobs))
            log.write_text(''.join(
                f'{{"id":"{job["id"]}","status":"complete","training_eligible":true,"result":{{"faults":[]}}}}\n'
                for job in jobs), encoding='utf-8')
        runner.collector = collect
        first = self.jobs('mixed', 0)
        for job in first:
            job['learning']['dagger_teacher'] = self.astra
        accepted, _ = runner.execute(first, name)
        resumed = self.jobs('mixed', 0)
        for job in resumed:
            job['learning']['dagger_teacher'] = self.astra
        replayed, _ = runner.execute(resumed, name)
        self.assertEqual(accepted, replayed)
        self.assertEqual(len(captured), 1)
        path = runner.directory / 'schedules' / (name+'.json')
        frozen = read_json(path)
        frozen[0]['bots'][2-frozen[0]['meta']['seat']] = 'wrong'
        write_json(path, frozen)
        with self.assertRaisesRegex(ValueError, 'different opponent'):
            runner.execute(resumed, name)

    def test_lite_loads_original_bc_tensor_in_greedy_mode(self):
        record = opponents.export_opponent(PARENT / 'duel/last_bc.pt', self.root / 'policy')
        self.bc = record
        job = next(j for j in self.jobs('mixed', 0) if record['path'] in j['bots'])
        seat = job['meta']['seat']
        job['bots'][seat-1] = self.astra
        policies = FrozenPolicies(job)
        self.assertEqual(set(policies.models), {3-seat})
        self.assertFalse(policies.modes[3-seat])
        torch_state = policies.models[3-seat].float().state_dict()
        from learning.bc_anchor import weights_sha256
        self.assertEqual(weights_sha256(torch_state), record['weights_sha256'])
        Path(record['path'], 'lua/config.lua').write_text('return {["mode"]="sample"}\n')
        with self.assertRaisesRegex(ValueError, 'identity or greedy'):
            opponents.verify_opponent(record)

    def test_mixed_fixture_only_writes_learner_ppo_and_dagger_rows(self):
        from learning.data import read_shards
        from learning.lite_host import play_lite_job
        from learning.rowpack import unpack_line
        from learning.lite_policy import FrozenPolicies
        from learning.tasks import reward_config, TASK_ID
        import gzip

        record = opponents.export_opponent(PARENT / 'duel/last_bc.pt', self.root / 'policy')
        self.bc = record
        for job in self.jobs('mixed', 0):
            if record['path'] not in job['bots']:
                continue
            seat = job['meta']['seat']
            job['bots'][seat-1] = record['path']
            job['learning']['dagger_teacher'] = self.astra
            job.update(task_id=TASK_ID, reward_config=reward_config(mode='fixed'),
                       rules_dir=str(RULES), allow_approximate=True, max_turns=30)
            observed = set()
            def end_turn(_policies, row, active):
                observed.add(active)
                action = next(i for i, candidate in enumerate(row['candidates'])
                              if candidate['kind'] == 'end_turn')
                return dict(choice=action, log_probability=0., value=0.)
            with patch.object(FrozenPolicies, 'choose', end_turn):
                result = play_lite_job(job)
            self.assertEqual(result['status'], 'complete', result)
            self.assertEqual(observed, {1, 2})
            self.assertEqual({row['side'] for row in
                              read_shards([job['shard']], expected_task=TASK_ID)}, {seat})
            dagger = job['shard'].replace('.jsonl.gz', '.dagger.jsonl.gz')
            with gzip.open(dagger, 'rt') as file:
                rows = [unpack_line(line)[0] for line in file]
            self.assertEqual({(row['side'], row['source']) for row in rows}, {(seat, 'astra')})
            self.assertTrue(any(row.get('query_only') for row in rows))

    def test_all_roles_are_paired_and_independent_scoring_matches(self):
        import json

        from learning.maps import frozen_map
        from verification.duel_ppo_comparison_20261106.audit import board_digest
        from verification.duel_ppo_comparison_20261106.panels import panel_scores
        from verification.ppo_batch_comparison_20261107 import panels
        from .driver import audit_panel, compare

        roles = ['bc'] + [f'{arm}-{seed}' for arm, seed in opponents.INPUTS['order']]
        jobs = [job for name in roles for job in panels.plan_jobs(
            self.root, 'learner', self.astra, 'unused', name, 0, str(RULES), 'validation')]
        plan = dict(partition='validation', blocks=15, roles={name: {} for name in roles},
                    aliases={name: name for name in roles}, jobs=jobs)
        results = [dict(id=job['id'], status='complete', meta=job['meta'], result=dict(
            bots=job['bots'], faults=[], task_terminal=True,
            winner=job['meta']['policy_sides'][0] if job['meta']['weights_sha256'].startswith('mixed') else 0))
            for job in jobs]
        self.assertEqual(len(results), 210)
        (self.root/'results.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in results))
        scored = dict(panel_scores(plan, results), planned_games=210, actual_games=210)
        write_json(self.root/'summary.json', scored)
        board, digest = frozen_map('hamlets')
        identity = dict(file_sha256=digest, board_sha256=board_digest(board))
        audited = audit_panel(self.root, plan, identity, self.astra)
        with patch('verification.ppo_opponent_comparison_20261114.driver.EVAL',
                   opponents.INPUTS['evaluation'] | dict(bootstrap_samples=30)):
            stats = compare([audited])
        self.assertTrue(stats['pass'])
        self.assertAlmostEqual(stats['differences']['b_minus_a'], 2/3)
        self.assertAlmostEqual(stats['differences']['b_minus_bc'], 2/3)
        broken = deepcopy(plan)
        broken['jobs'][0]['seed'] += 1
        with self.assertRaisesRegex(ValueError, 'different paired scenarios'):
            audit_panel(self.root, broken, identity, self.astra)
