"""Time the score-only learner path in the existing official holdout workers."""
from math import ceil
from time import perf_counter_ns
from unittest.mock import patch

from learning import sample
from learning.sample import play_job as production_play_job


def play_job(job):
    """A top-level worker for the production collector's spawned executor."""
    from learning.lite_host import LiteHost
    from learning.lite_policy import FrozenPolicies

    if job.get('engine') != 'lite' or not job.get('score_only_policy') or job['meta']['map_partition'] != 'final':
        raise ValueError('learner timing requires an official score-only Lite holdout job')
    learner, = job['meta']['policy_sides']
    decide, choose = LiteHost.decision, FrozenPolicies.choose
    durations = []
    started = None

    def timed_decision(host, side, **options):
        nonlocal started
        if options.get('score_only_policy'):
            if side != learner or started is not None:
                raise ValueError('unexpected score-only decision in learner timing')
            started = perf_counter_ns()
        return decide(host, side, **options)

    def timed_choice(policy, row, side, bootstrap=False):
        nonlocal started
        if side != learner or started is None or bootstrap:
            raise ValueError('policy choice has no matching score-only learner decision')
        result = choose(policy, row, side, bootstrap=bootstrap)
        durations.append(perf_counter_ns()-started)
        started = None
        return result

    with patch.object(LiteHost, 'decision', timed_decision), patch.object(FrozenPolicies, 'choose', timed_choice):
        result = production_play_job(job)
    if result['status'] == 'complete' and started is not None:
        raise ValueError('completed holdout game has an unfinished learner decision')
    result['learner_decision_ns'] = durations
    return result


def collect(jobs, workers, log_path):
    with patch.object(sample, 'play_job', play_job):
        return sample.collect(jobs, workers, log_path)


def summarize(jobs, results, aliases):
    by_game = {row['id']: row for row in results}
    durations = {key: [] for key in set(aliases.values())}
    for job in jobs:
        row = by_game.get(job['id'])
        if row and row['status'] == 'complete' and not row['result'].get('faults'):
            durations[job['meta']['weights_sha256']].extend(row['learner_decision_ns'])
    weights = {}
    for key, values in sorted(durations.items()):
        count = len(values)
        weights[key] = dict(count=count, p95_ms=sorted(values)[ceil(.95*count)-1]/1_000_000 if count else None)
    return dict(weights=weights, aliases=aliases)
