"""A job record keeps only the per-decision evidence its consumer reads."""
import unittest

from tests.v5 import test_pipeline_contract as pipeline


class RecordEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = pipeline.LiteJobTests('test_astra_job_writes_schema_four_shard')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def play(self, phase, opening=False):
        job = self.fixture.job(bots=['p', 'p'], policy=lambda row: dict(choice=0, log_probability=0., value=0.),
                               bootstrap_policy=lambda row: 0.)
        job['meta'].update(phase=phase)
        if opening:
            job['meta']['opening'] = True
        with pipeline.catalog_patch(self.fixture.rules_dir):
            outcome = pipeline.play_lite_job(job)
        self.assertEqual(outcome['status'], 'complete', outcome.get('error'))
        return outcome

    def test_training_phases_keep_no_per_decision_evidence(self):
        for phase in ('teacher', 'ppo', 'dagger_refresh'):
            outcome = self.play(phase)
            self.assertNotIn('reward_diagnostics', outcome, phase)
            self.assertNotIn('behavior', outcome, phase)
            self.assertGreater(outcome['coverage']['total'], 0, phase)

    def test_validation_and_opening_rows_keep_what_their_reader_reads(self):
        validation = self.play('validation')
        self.assertEqual(len(validation['reward_diagnostics']), 2)
        self.assertNotIn('behavior', validation)
        opening = self.play('ppo', opening=True)
        self.assertTrue(opening['behavior'])
        self.assertNotIn('reward_diagnostics', opening)


if __name__ == '__main__':
    unittest.main()
