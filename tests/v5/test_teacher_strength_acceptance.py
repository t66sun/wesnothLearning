"""The optional teacher NI report must not weaken the original comparison."""
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
from argparse import Namespace
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from learning.common import write_json
from learning.sample import opening_map
from learning.schedule import evaluation_jobs
from tests import acceptance_teacher_strength as acceptance


def complete_report():
    plan = acceptance.panel_design(True)
    plan['games'] = dict(duel=1920, ffa4=1200, team2v2=1440)
    comparison, counts = {}, {}
    for fmt, blocks in plan['required_blocks'].items():
        scale, games = plan['scales'][fmt], plan['games'][fmt]
        comparison[fmt] = dict(status='not_passed', blocks=blocks, planned_blocks=blocks,
            missing_blocks=0, fault_games=0, distinct_scenarios=15,
            difference=-0.03 * scale, interval95=[-0.04 * scale, -0.02 * scale])
        counts[fmt] = dict(planned=games, observed=games, statuses={'complete': games}, fault_games=0)
    return plan, comparison, counts


class TeacherStrengthAcceptanceTests(unittest.TestCase):
    def test_ni_prepare_requires_archive_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'panel'
            args = Namespace(root=temporary, output=str(output), wesnoth='unused',
                             source_commit='unit-test', noninferiority=True, source_archive=None)
            with self.assertRaisesRegex(ValueError, '--source-archive'):
                acceptance.prepare(args)
            args.source_archive = str(Path(temporary) / 'missing.tar')
            with self.assertRaises(FileNotFoundError):
                acceptance.prepare(args)
            self.assertFalse(output.exists())

    def test_cli_mode_is_fixed_at_prepare(self):
        args = ['acceptance', 'prepare', '--root', str(Path.cwd()), '--output', 'unused',
                '--wesnoth', 'unused', '--source-commit', 'unit-test']
        for extra, expected in (([], False), (['--noninferiority'], True)):
            with patch.object(sys, 'argv', args + extra), patch.object(sys, 'path', sys.path.copy()), \
                    patch.object(acceptance, 'prepare') as prepare:
                acceptance.main()
                self.assertEqual(prepare.call_args.args[0].noninferiority, expected)
        with patch.object(sys, 'argv', ['acceptance', 'report', '--output', 'unused', '--noninferiority']), \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            acceptance.main()
        self.assertEqual(error.exception.code, 2)

    def test_declared_schedule_covers_full_roster_and_original_contexts(self):
        def frozen_map(name):
            return opening_map(2 if name == 'hamlets' else 4), '0' * 64

        with patch('learning.maps.frozen_map', side_effect=frozen_map), \
                patch('learning.schedule.evaluation_jobs', wraps=evaluation_jobs) as scheduled:
            jobs = acceptance.panel_jobs('.', 'policy', 'control', 3000000000, 'unused',
                                         acceptance.panel_design(True))
            original = acceptance.panel_jobs('.', 'policy', 'control', 3000000000, 'unused',
                                             acceptance.panel_design())
        self.assertEqual([call.args[5] for call in scheduled.call_args_list[:3]],
                         [20261104, 20361107, 20461110])
        self.assertEqual(Counter(j['meta']['format'] for j in jobs),
                         dict(duel=1920, ffa4=1200, team2v2=1440))
        self.assertEqual(Counter(j['meta']['format'] for j in original),
                         dict(duel=24, ffa4=48, team2v2=96))
        self.assertEqual(len({j['id'] for j in jobs}), 4560)
        for fmt, repeats in (('duel', 64), ('ffa4', 20), ('team2v2', 12)):
            blocks = {j['meta']['block']: j['scenario_family'] for j in jobs if j['meta']['format'] == fmt}
            self.assertEqual(sorted(Counter(blocks.values()).values()), [repeats] * 15)
        self.assertEqual(Counter(j['meta']['context'] for j in jobs if j['meta']['format'] == 'team2v2'),
                         dict(baseline_partner=720, self_team=720))
        self.assertEqual([j['meta']['format'] for j in jobs[:4]], ['duel', 'ffa4', 'team2v2', 'team2v2'])
        self.assertEqual({j['max_turns'] for j in jobs}, {30})
        self.assertEqual({j['meta']['map_partition'] for j in jobs}, {'validation'})

    def test_small_negative_superiority_result_can_pass_ni(self):
        plan, comparison, counts = complete_report()
        original = copy.deepcopy(comparison)
        result = acceptance.noninferiority(plan, comparison, counts)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(comparison, original)
        self.assertEqual(result['formats']['duel']['interval95'], [-0.04, -0.02])

    def test_exact_margin_never_passes_and_all_formats_are_required(self):
        for fmt, lower in (('duel', -0.15), ('ffa4', -0.05), ('team2v2', -0.15)):
            plan, comparison, counts = complete_report()
            comparison[fmt]['interval95'][0] = lower
            result = acceptance.noninferiority(plan, comparison, counts)
            self.assertEqual(result['formats'][fmt]['interval95'][0], -0.05)
            self.assertEqual(result['formats'][fmt]['status'], 'not_passed')
            self.assertEqual(result['status'], 'not_passed')
        del comparison['team2v2']
        self.assertEqual(acceptance.noninferiority(plan, comparison, counts)['formats']['team2v2']['status'],
                         'inconclusive')

    def test_missing_faulted_or_incomplete_design_cannot_pass(self):
        for defect in ('missing_job', 'missing_block', 'fault', 'few_families', 'missing_identity'):
            with self.subTest(defect=defect):
                plan, comparison, counts = complete_report()
                if defect == 'missing_job':
                    counts['duel']['observed'] -= 1
                elif defect == 'missing_block':
                    comparison['duel']['missing_blocks'] = 1
                elif defect == 'fault':
                    counts['duel']['fault_games'] = 1
                elif defect == 'few_families':
                    comparison['duel']['distinct_scenarios'] = 14
                else:
                    comparison['duel']['status'] = 'insufficient_design'
                result = acceptance.noninferiority(plan, comparison, counts)
                self.assertEqual(result['formats']['duel']['status'], 'inconclusive')
                self.assertEqual(result['status'], 'not_passed')

    def test_report_preserves_original_superiority_result(self):
        jobs, results = [], []
        for block in range(12):
            for rotation in range(2):
                identifier = f'{block}-{rotation}'
                jobs.append(dict(id=identifier, scenario_family=f'family-{block}',
                    meta=dict(format='duel', block=block, control='control', context='solo',
                              policy_sides=[1], control_sides=[2])))
                results.append(dict(id=identifier, status='complete', result=dict(
                    bots=['policy', 'control'], winner=0, faults={}, reason='turn_limit')))
        comparisons = []
        for ni in (False, True):
            with tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary)
                plan = acceptance.panel_design(ni)
                plan['games'] = dict(duel=1920, ffa4=1200, team2v2=1440)
                write_json(output / 'plan.json', plan)
                write_json(output / 'schedule.json', jobs)
                (output / 'jobs.jsonl').write_text('\n'.join(json.dumps(row) for row in results))
                with redirect_stdout(io.StringIO()):
                    acceptance.report(output)
                summary = json.loads((output / 'summary.json').read_text())
                comparisons.append(summary['comparison'])
                self.assertEqual('noninferiority' in summary, ni)
                self.assertEqual(summary['comparison']['duel']['status'], 'not_passed')
        self.assertEqual(comparisons[0], comparisons[1])

    def test_compatibility_transform_is_only_used_when_requested(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            (source / 'lua').mkdir(parents=True)
            (source / 'lua/bot.lua').write_text('return {}\n')
            metadata = {'files': {'lua/duel.lua': {'old_sha256': 'old', 'new_sha256': 'new'}}}
            with patch('tests.teacher_control_compatibility.apply_ambush_compatibility',
                       return_value=metadata) as transform:
                _, unchanged = acceptance.stage(source, 'astra_frozen', root)
                self.assertIsNone(unchanged)
                transform.assert_not_called()
                _, changed = acceptance.stage(source, 'astra_control_compatible', root, compatible=True)
                self.assertEqual(changed, metadata)
                transform.assert_called_once()


if __name__ == '__main__':
    unittest.main()
