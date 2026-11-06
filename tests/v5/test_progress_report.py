"""BC, selected and latest complete policies are distinct evaluation objects."""
import shutil
import copy
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import torch

from learning.train import checkpoint
from learning.common import read_json, sha256, write_json
from learning.progress import ROLES, paired_progress, plan, run, write_report
from learning.schedule import evaluation_jobs
from tests.v5 import helpers, test_final_nomination


class ProgressIdentityTests(unittest.TestCase):
    def test_final_report_distinguishes_bc_selected_latest_and_pending_update(self):
        with helpers.temporary_directory() as directory:
            runner = test_final_nomination.FinalNominationTests().runner(directory)
            model = helpers.model(format_name='duel')
            optimizer = torch.optim.Adam(model.parameters())
            checkpoint(directory/'last_bc.pt', model, optimizer, runner=dict(version=38, pending_train=None))
            checkpoint(directory/'latest.pt', model, optimizer,
                       runner=dict(version=144, pending_train=dict(method='ppo')))
            shutil.copyfile(directory/'best.pt', directory/'selected.pt')
            runner._select_final = lambda: (directory/'selected.pt', 'champion', dict(selected_version=100))
            runner.state.update(effective=False, error=None, history=[])
            runner.save = Mock()
            runner.teacher_evidence = lambda: []
            runner.execute = lambda jobs, name: (jobs, [])
            with patch('learning.experiment.time.time', return_value=1.):
                summary = runner.final_evaluation()
            self.assertIn('checkpoint_roles', summary)
            roles = summary['checkpoint_roles']
            self.assertEqual(roles['bc']['version'], 38)
            self.assertEqual(roles['selected']['version'], 100)
            self.assertEqual(roles['latest']['version'], 143)
            self.assertTrue(roles['latest']['path'].endswith('last_ppo.pt'))
            self.assertEqual(roles['pending']['version'], 144)
            self.assertFalse(roles['pending']['complete'])
            self.assertEqual(len({roles[k]['checkpoint_sha256'] for k in ('bc', 'selected', 'latest')}), 3)
            text = (directory/'report'/'REPORT.md').read_text(encoding='utf-8')
            for expected in ('bc | 38', 'selected | 100', 'latest | 143', 'pending | 144'):
                self.assertIn(expected, text)


def plans(fmt='duel', blocks=12):
    jobs = []
    for role in ROLES:
        part = evaluation_jobs('.', role, 'astra', ['astra'], blocks, 19, 1000, 'unused',
            label='progress-'+role, formats=[fmt], team_contexts=('astra_partner', 'self_team'))
        for job in part:
            job['meta']['progress_role'] = role
        jobs.extend(part)
    return jobs


def replies(jobs, outcomes=None):
    outcomes = outcomes or dict(bc=-1, selected=0, latest=1)
    rows = []
    for job in jobs:
        role = job['meta']['progress_role']
        outcome = outcomes[role]
        if callable(outcome):
            outcome = outcome(job)
        side = job['meta']['policy_sides'][0]
        other = job['meta']['control_sides'][0]
        result = dict(bots=job['bots'], teams=job['teams'], faults={})
        if job['teams']:
            result['winning_team'] = 0 if outcome == 0 else job['teams'][(side if outcome > 0 else other)-1]
        elif len(job['bots']) == 2:
            result['winner'] = 0 if outcome == 0 else side if outcome > 0 else other
        else:
            result['rank_points'] = {str(s): ((outcome+1)*1.5 if s == side else 0) for s in range(1, 5)}
        rows.append(dict(id=job['id'], status='complete', result=result))
    return rows


class PairedProgressTests(unittest.TestCase):
    def test_all_formats_compare_normalized_own_points_on_matched_blocks(self):
        for fmt in ('duel', 'ffa4', 'team2v2'):
            with self.subTest(fmt=fmt):
                jobs = plans(fmt)
                result = paired_progress(jobs, replies(jobs), fmt, 12)
                self.assertEqual(result['latest']['difference'], 1.)
                self.assertEqual(result['latest']['interval95'], [1., 1.])
                self.assertEqual(result['latest']['status'], 'improved')
                self.assertTrue(result['latest']['complete'])
                self.assertEqual(result['latest']['distinct_scenarios'], 12)
                self.assertAlmostEqual(result['selected']['difference'], .5 if fmt == 'ffa4' else 1/3)

    def test_complete_inconclusive_is_separate_from_missing_or_faulted(self):
        jobs = plans()
        rows = replies(jobs, dict(bc=0, selected=0, latest=0))
        result = paired_progress(jobs, rows, 'duel', 12)['latest']
        self.assertEqual(result['status'], 'inconclusive')
        self.assertTrue(result['complete'])
        self.assertEqual(result['interval95'], [0., 0.])
        missing = paired_progress(jobs, rows[:-1], 'duel', 12)['latest']
        self.assertFalse(missing['complete'])
        self.assertEqual(missing['missing_blocks'], 1)
        self.assertEqual(missing['status'], 'inconclusive')
        rows[-1]['result']['faults'] = {'1': 'fixture fault'}
        faulted = paired_progress(jobs, rows, 'duel', 12)['latest']
        self.assertFalse(faulted['complete'])
        self.assertEqual(faulted['fault_games'], 1)
        self.assertEqual(faulted['status'], 'infrastructure_error')

    def test_different_seeds_on_one_scene_do_not_meet_the_scenario_floor(self):
        jobs = plans()
        for job in jobs:
            job['scenario_family'] = 'same-physical-scene'
        self.assertGreater(len({j['seed'] for j in jobs}), 1)
        result = paired_progress(jobs, replies(jobs), 'duel', 12)['latest']
        self.assertTrue(result['complete'])
        self.assertEqual(result['distinct_scenarios'], 1)
        self.assertEqual(result['status'], 'insufficient_design')

    def test_scenario_cluster_weights_do_not_follow_repeated_seed_count(self):
        jobs = plans(blocks=31)
        for job in jobs:
            block = job['meta']['block']
            job['scenario_family'] = 'repeated' if block < 20 else f'scene-{block}'
        rows = replies(jobs, dict(bc=-1, selected=-1,
            latest=lambda job: 1 if job['meta']['block'] < 20 else -1))
        result = paired_progress(jobs, rows, 'duel', 31)['latest']
        self.assertEqual(result['distinct_scenarios'], 12)
        self.assertAlmostEqual(result['difference'], 1/12)

    def test_unmatched_seed_opponent_or_holdout_cannot_claim_progress(self):
        for change in ('seed', 'opponent', 'holdout'):
            with self.subTest(change=change):
                jobs = plans()
                last = jobs[-1]
                if change == 'seed':
                    last['seed'] += 1
                elif change == 'opponent':
                    last['bots'][last['meta']['control_sides'][0]-1] = 'other'
                else:
                    last['meta']['map_partition'] = 'final'
                with self.assertRaisesRegex(ValueError, 'unmatched|validation scenarios'):
                    paired_progress(jobs, [], 'duel', 12)

    def test_regression_uses_its_own_negative_paired_interval(self):
        jobs = plans()
        rows = replies(jobs, dict(bc=1, selected=0, latest=-1))
        result = paired_progress(jobs, rows, 'duel', 12)['latest']
        self.assertEqual(result['status'], 'regressed')
        self.assertEqual(result['interval95'], [-1., -1.])

    def test_explicit_plan_and_execution_keep_the_source_run_read_only(self):
        from learning.rules_catalog import load, resolve_dir
        from learning.manifest import tree_hashes

        with helpers.temporary_directory() as directory:
            source = directory/'source-run'/'duel'
            source.mkdir(parents=True)
            model = helpers.model(format_name='duel')
            optimizer = torch.optim.Adam(model.parameters())
            for name, version in [('last_bc.pt', 38), ('selected.pt', 100), ('last_ppo.pt', 143)]:
                checkpoint(source/name, model, optimizer, runner=dict(version=version, pending_train=None))
            write_json(source/'selection.json', dict(selected_sha256=sha256(source/'selected.pt')))
            teacher = source.parent/'frozen'/'gpt6astra.zip'
            teacher.parent.mkdir()
            teacher.write_bytes(b'fixture opponent; collector is replaced')
            rules = resolve_dir()
            manifest = dict(config=dict(engine='lite', allow_approximate=True),
                rules=dict(directory=str(rules), rules_sha256=load(rules)['rules_file_sha256']),
                opponents=[dict(path=str(teacher), sha256=sha256(teacher))], baseline=dict(path='unused'))
            write_json(source.parent/'manifest.json', manifest)
            before = tree_hashes(source.parent)
            output = directory/'progress'
            record = plan(source, output, fmt='duel', blocks=12, seed=19, hours=1.)
            self.assertEqual(record['budget']['games'], 72)
            self.assertFalse((output/'execution').exists())
            jobs = read_json(output/'jobs.json')
            self.assertEqual(len(jobs), 72)
            self.assertEqual({j['max_turns'] for j in jobs}, {30})
            self.assertEqual({j['meta']['map_partition'] for j in jobs}, {'validation'})
            self.assertFalse(any(j.get('learning') or j.get('shard') for j in jobs))
            def collect(actual, workers, log):
                self.assertEqual(workers, 2)
                self.assertEqual(actual, jobs)
                return replies(actual)
            with patch('learning.sample.collect', side_effect=collect) as collector:
                summary = run(output/'plan.json', 2)
                self.assertEqual(collector.call_count, 1)
            self.assertEqual(summary['progress']['latest']['status'], 'improved')
            self.assertEqual(tree_hashes(source.parent), before)
            self.assertEqual(summary['checkpoint_roles']['bc']['version'], 38)
            rebuilt = write_report(output/'plan.json', output/'execution'/'results.json', directory/'report-copy')
            self.assertEqual(rebuilt, summary)
            jobs[0]['seed'] += 1
            write_json(output/'jobs.json', jobs)
            with self.assertRaisesRegex(ValueError, 'schedule changed'):
                write_report(output/'plan.json', output/'execution'/'results.json', directory/'bad-report')
            with self.assertRaisesRegex(ValueError, 'at least 12'):
                plan(source, directory/'underfunded', fmt='duel', blocks=11, seed=19, hours=1.)
