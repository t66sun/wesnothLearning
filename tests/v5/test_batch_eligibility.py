"""Frozen PPO batches cannot silently lose non-training decisions."""
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace


class BatchEligibilityTests(unittest.TestCase):
    def test_validation_row_in_batch_raises(self):
        from learning.data import split
        from learning.updates import prepare
        from tests.v5.helpers import synthetic_decision_row

        row = synthetic_decision_row()
        train_family = next('train-' + str(i) for i in range(30) if split('train-' + str(i)) == 'train')
        val_family = next('val-' + str(i) for i in range(30) if split('val-' + str(i)) == 'validation')
        rows = [dict(row, game_id=str(i), game_family=val_family if i < 3 else train_family,
                     split='validation' if i < 3 else 'train') for i in range(10)]
        with self.assertRaisesRegex(ValueError, 'batch row excluded by split: 3 of 10'):
            prepare(SimpleNamespace(format_name='duel'), rows)

    def test_rollouts_are_eligible_before_freezing_and_after_engine_override(self):
        from learning.common import ROOT
        from learning.data import split
        from learning.schedule import compose_training_scenario, rollout_jobs

        for batch in range(20):
            jobs = rollout_jobs(ROOT, 'student', ['history'], ['gpt6astra.zip'],
                                'support', 'v1', batch, 19, 1000, 'unused')
            self.assertEqual(len(jobs), 12)
            for job in jobs:
                self.assertEqual(split(job['scenario_family']), 'train')
                original = (job['meta']['composition'][:], job['bots'][:], job['seed'])
                job['engine'] = 'native'
                compose_training_scenario(job)
                self.assertEqual(split(job['scenario_family']), 'train')
                self.assertEqual(original, (job['meta']['composition'], job['bots'], job['seed']))
                before = (job['scenario_family'], job['game_family'], dict(job['meta']['eligibility_swap']))
                compose_training_scenario(job)
                self.assertEqual(before, (job['scenario_family'], job['game_family'], job['meta']['eligibility_swap']))

    def test_all_ten_eligible_rows_are_reported_and_committed(self):
        from tests.v5.test_ppo_plan import _records, _run

        rows = _records([('b', 2, 0.), ('c', 3, 0.), ('d', 4, 0.), ('e', 1, 0.)])
        _, _, result = _run(rows)
        self.assertEqual(result['eligible_decisions'], 10)
        self.assertEqual(result['excluded_decisions'], 0)
        self.assertEqual(result['excluded_games'], 0)
        self.assertEqual(result['committed_decisions'], 10)

    def test_four_player_updates_report_zero_excluded_rows(self):
        import torch
        from learning import ppo
        from learning.data import split
        from learning.model import batch
        from learning.sequences import attach_histories
        from tests.v5 import helpers

        for fmt in ('ffa4', 'team2v2'):
            with self.subTest(format=fmt):
                rows = helpers.sequence_rows(turns=2, format_name=fmt, source='policy',
                                             game_id='b', game_family='b')
                rehearsal = helpers.sequence_rows(turns=1, format_name=fmt,
                                                   game_id='bc-1', game_family='bc-1')
                for row in rows + rehearsal:
                    row['split'] = split(row['game_family'])
                rows = attach_histories(rows)
                model = helpers.model(format_name=fmt)
                with torch.no_grad():
                    logits, values = model(*batch(rows))
                    dist = torch.distributions.Categorical(logits=logits)
                    logp = dist.log_prob(torch.tensor([r['choice'] for r in rows])).tolist()
                for row, value, prediction in zip(rows, logp, values.flatten().tolist()):
                    row['log_probability'] = value
                    row['value'] = prediction
                    row['reward'] = 0.
                optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
                result = ppo.update(model, optimizer, rows, bc_records=rehearsal, epochs=1)
                self.assertEqual(result['eligible_decisions'], len(rows))
                self.assertEqual(result['committed_decisions'], len(rows))
                self.assertEqual(result['excluded_decisions'], 0)
                self.assertEqual(result['excluded_games'], 0)

    def test_legacy_manifest_cannot_resume_with_the_new_batch_contract(self):
        from learning.common import sha256
        from learning.manifest import verify_frozen

        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / 'runtime-reference'
            runtime.write_bytes(b'frozen runtime identity; never executed')
            legacy = dict(schema=4, opponents=[], source={},
                          baseline=dict(path=str(runtime), sha256=sha256(runtime)))
            with self.assertRaisesRegex(ValueError, 'original frozen sources'):
                verify_frozen(legacy)


if __name__ == '__main__':
    unittest.main()
