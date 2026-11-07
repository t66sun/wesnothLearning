"""One no-game fixture for the scored learner timing and its weight aliases."""
from pathlib import Path
import pickle
import unittest
from unittest.mock import patch

from learning import sample
from learning.lite_host import LiteHost
from learning.lite_policy import FrozenPolicies
from verification.ppo_batch_comparison_20261107 import decision_timing


class DecisionTimingTests(unittest.TestCase):
    def test_holdout_times_only_the_learner_path_once_per_weight(self):
        millisecond = 1_000_000
        now = 0
        executed = []

        def decide(_host, _side, **options):
            nonlocal now
            now += options.get('observation_ms', 100)*millisecond
            return {}

        def choose(_policy, _row, _side, bootstrap=False):
            nonlocal now
            now += millisecond
            return {'choice': 0}

        def play(job):
            nonlocal now
            learner, = job['meta']['policy_sides']
            host = LiteHost.__new__(LiteHost)
            policy = FrozenPolicies.__new__(FrozenPolicies)
            executed.append(job['id'])
            for duration_ms in job['expected_ms']:
                host.decision(3-learner, teacher=True, score_only_astra=True)
                host.decision(learner, generate_candidates=False)
                row = host.decision(learner, score_only_policy=True, observation_ms=duration_ms-1)
                policy.choose(row, learner)
                now += 500*millisecond
            return dict(id=job['id'], status='complete', result={'faults': job.get('faults', [])})

        def submit(jobs, workers, _log):
            self.assertEqual(workers, 8)
            worker = pickle.loads(pickle.dumps(sample.play_job))
            return [worker(job) for job in jobs]

        def job(name, side, values, faults=()):
            return dict(id=name, engine='lite', score_only_policy=True, expected_ms=values, faults=faults,
                        meta=dict(policy_sides=[side], map_partition='final', weights_sha256='shared-weights'))

        jobs = [job('first-seat', 1, list(range(1, 11))), job('second-seat', 2, list(range(11, 20))+[500]),
                job('faulted', 1, [900], ['fault'])]
        original_worker = sample.play_job
        with patch.object(LiteHost, 'decision', decide), patch.object(FrozenPolicies, 'choose', choose), \
                patch.object(decision_timing, 'perf_counter_ns', side_effect=lambda: now), \
                patch.object(decision_timing, 'production_play_job', side_effect=play), \
                patch.object(sample, 'collect', side_effect=submit):
            results = decision_timing.collect(jobs, 8, Path('unused'))
        self.assertIs(sample.play_job, original_worker)
        self.assertEqual(executed, [job['id'] for job in jobs])
        for game, result in zip(jobs, results):
            self.assertEqual(result['learner_decision_ns'], [value*millisecond for value in game['expected_ms']])

        aliases = {'base/bc': 'shared-weights', 'a-202611071/wall': 'shared-weights'}
        report = decision_timing.summarize(jobs, results, aliases)
        self.assertEqual(report, dict(weights={'shared-weights': dict(count=20, p95_ms=19.)}, aliases=aliases))
