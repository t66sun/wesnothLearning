"""Ordinary validation budgets must fund their unchanged scenario floor."""
import tempfile
import unittest
from pathlib import Path

from learning.common import read_json, write_json
from learning.experiment import default_config, validate_config
from learning.schedule import starting_factions
from tests import test_validation_cadence as cadence


class TrendBudgetTests(unittest.TestCase):
    def test_default_budgets_fund_three_complete_scenarios(self):
        config = default_config('cpu')
        self.assertEqual(config['validation_games'], dict(duel=6, ffa4=12, team2v2=24))
        self.assertEqual(config['min_distinct'], dict(trend=3, promotion=12, final=12, gate=12))
        validate_config(config)

    def test_reject_budget_below_declared_floor_before_running_games(self):
        config = default_config('cpu')
        for fmt, games in [('duel', 4), ('ffa4', 8), ('team2v2', 16)]:
            with self.subTest(fmt=fmt), self.assertRaisesRegex(ValueError, 'trend.*scenario'):
                validate_config(config | dict(validation_games=config['validation_games'] | {fmt: games}))
        with self.assertRaisesRegex(ValueError, 'trend.*scenario'):
            validate_config(config | dict(min_distinct=config['min_distinct'] | dict(trend=4)))

    def test_reject_more_scenarios_than_the_fixed_design_can_supply(self):
        config = default_config('cpu')
        cases = [dict(min_distinct=config['min_distinct'] | dict(promotion=13)),
                 dict(min_distinct=config['min_distinct'] | dict(final=16)),
                 dict(min_distinct=config['min_distinct'] | dict(trend=16),
                      validation_games=dict(duel=32, ffa4=64, team2v2=128))]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, 'scenario.*capacity'):
                validate_config(config | changes)

    def test_actual_validation_rotates_the_roster_with_complete_panels(self):
        for fmt, n in [('duel', 2), ('ffa4', 4), ('team2v2', 4)]:
            with self.subTest(fmt=fmt), tempfile.TemporaryDirectory() as directory:
                runner = cadence.ValidationCadenceTests().runner(directory, fmt)
                write_json(Path(directory) / 'bc_gate.json', dict(imitation=dict(effective=False)))
                rosters, panels = set(), []

                def execute(jobs, name):
                    panels.append(jobs)
                    results = []
                    for job in jobs:
                        rosters.add(tuple(job['factions']))
                        side = job['meta']['policy_sides'][0]
                        result = dict(bots=job['bots'], teams=job['teams'], faults={})
                        if fmt == 'team2v2':
                            result['winning_team'] = job['teams'][side-1]
                        elif fmt == 'duel':
                            result['winner'] = side
                        else:
                            result['rank_points'] = {str(i): 3 if i == side else 0 for i in range(1, 5)}
                        results.append(dict(id=job['id'], status='complete', result=result))
                    return jobs, results

                runner.execute = execute
                for version in (10, 20, 30, 40, 50):
                    runner.state.update(version=version, batch=version, pending_validation='bc')
                    runner.validate_model('bc')
                    panel = read_json(Path(directory) / 'validation' / f'v{version:06}.json')['comparison'][fmt]
                    self.assertEqual(panel['distinct_scenarios'], 3)
                    self.assertEqual(panel['blocks'], 3)
                    self.assertEqual(panel['missing_blocks'], 0)
                    self.assertEqual(panel['status'], 'passed')
                self.assertEqual(rosters, {tuple(row) for row in starting_factions(n, fmt)})
                self.assertEqual(len(panels), 5)
