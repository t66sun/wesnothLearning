"""Two real stock teacher games prove the BC coverage gate sees exact labels.

The probe collects games through the runner's own stock teacher job builder, then
feeds the serialized coverage straight into the real gate arithmetic. Nothing is
lowered: every kind the gate grades must reach its published ratio on the games
this capture actually recorded.
"""
from pathlib import Path
import sys
import time

from learning.common import ROOT, sha256, write_json
from learning.data import read_shards
from learning.experiment import coverage_gate
from learning.features import schema
from learning.manifest import teacher_identity
from learning.maps import bind_scenario
from learning.sample import play_job
from learning.schedule import stock_teacher_jobs
import native

GAMES = 2


def support_dir(destination):
    support = destination / 'support'
    (support / 'lua').mkdir(parents=True)
    for path in (ROOT / 'lua').glob('*.lua'):
        (support / 'lua' / path.name).write_text(path.read_text().replace('@ADDON@', 'LearningSupport'))
    (support / 'lua/features.lua').write_text('return ' + native.lua(schema()))
    (support / 'lua/config.lua').write_text('return {candidate_budget_ms=200}')
    return support


def main():
    destination = Path(sys.argv[1])
    exe = native.find_wesnoth(sys.argv[2])
    destination.mkdir()  # Never overwrite a prior attempt.
    support = support_dir(destination)
    record = dict(teacher_identity('wesnoth_default_rca'), runtime_sha256=sha256(exe))
    # One game per job: the native log carries the captured rows, and a long
    # stock game alone can exceed the runner's 16 MiB log limit.
    jobs = [stock_teacher_jobs(destination / 'run', record, str(support), index, 20261030,
                               time.time() + 900, exe, formats=['duel'], count=1, index_stride=1)[0]
            for index in range(GAMES)]
    for job in jobs:
        # Five labeled turns are enough to grade labels; a train-length stock game
        # can push its captured rows past the runner's 16 MiB native log limit.
        job['max_turns'] = 5
        bind_scenario(job)
    write_json(destination / 'jobs.json', jobs)
    results, games = [], []
    for job in jobs:
        summary = play_job(job)
        (destination / 'runs').mkdir(exist_ok=True)
        write_json(destination / 'runs' / (Path(job['shard']).stem + '.json'), summary)
        assert summary['status'] == 'complete', summary
        assert not summary['result']['faults'], summary
        stock = summary['stock_coverage']
        assert stock, 'stock capture produced no label coverage'
        merged = {kind: count['merged'] for kind, count in stock.items()}
        # Merged events carry no label of their own and must stay out of the
        # denominator the gate divides by.
        for kind, count in summary['coverage']['kinds'].items():
            source = 'moveto' if kind == 'move' else kind
            assert count['total'] == stock[source]['matched'] + stock[source]['unmatched'] + stock[source]['ambiguous'], (
                kind, count, stock[source])
        results.append(dict(coverage=summary['coverage'], result=summary['result']))
        games.append(dict(seed=job['seed'], stock_coverage=stock,
                          coverage=summary['coverage'], merged=merged,
                          shard_sha256=sha256(job['shard'])))
    totals = {}
    for kind in ('recruit', 'recall', 'moveto', 'attack', 'advance'):
        totals[kind] = dict((field, sum(game['stock_coverage'][kind][field] for game in games))
                            for field in ('matched', 'unmatched', 'ambiguous', 'merged'))
    assert totals['attack']['ambiguous'] == 0, totals['attack']
    assert totals['attack']['matched'] > 0, totals['attack']
    assert totals['moveto']['ambiguous'] == 0, totals['moveto']
    assert totals['recruit']['matched'] > 0, totals['recruit']
    gate = coverage_gate(results)
    write_json(destination / 'probe.json', dict(
        status='passed' if gate['passed'] else 'failed', gate=gate, totals=totals, games=games,
        capture_sha256=record['capture_sha256'], runtime_sha256=record['runtime_sha256'],
        rules_sha256=record['rules_sha256'], teacher_query=record['query']))
    assert gate['passed'], gate
    print('passed', len(games), 'stock games; gate' , gate['actions'])


if __name__ == '__main__':
    main()
