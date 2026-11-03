"""Measure one complete validation rotation per format on the stock shared worker pool."""
from argparse import ArgumentParser
from itertools import zip_longest
import json
import os
from pathlib import Path
from time import monotonic, process_time, time
from unittest.mock import patch

from learning import sample
from learning.common import sha256
from learning.sample import play_job


FORMATS = ('duel', 'ffa4', 'team2v2')
SECONDS = 235


def timed_job(job):
    from learning.lite_policy import _models
    start, cpu = monotonic(), process_time()
    result = play_job(job)
    result['probe'] = dict(worker_pid=os.getpid(), start=start, end=monotonic(),
                           cpu=process_time()-cpu,
                           weights=sorted({str(next(m.parameters()).dtype) for m in _models.values()}))
    return result


def main():
    import _engine_lite
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('source_run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    jobs, expected, inputs = {}, {}, {}
    for fmt, count in zip(FORMATS, (2,4,8)):
        folder = args.source_run / fmt
        schedule = folder / 'schedules/validation-000010.json'
        rows = json.loads(schedule.read_text())
        block = [j for j in rows if j['meta']['block'] == 0]
        assert len(block) == count and all(j['meta']['map_partition'] == 'validation' for j in block)
        jobs[fmt] = block
        inputs[fmt] = dict(schedule_sha256=sha256(schedule), model_sha256=sha256(Path(block[0]['meta']['policy']).parent/'model.pt'))
        for j in block:
            assert j['engine'] == 'lite' and not j.get('shard') and not j.get('learner_sides')
            del j['learning']
            j.update(score_only_astra=True, output=str(args.output/(j['id']+'.json')))
        for line in (folder/'jobs.jsonl').read_text().splitlines():
            row = json.loads(line)
            expected[row['id']] = row['result']
    ordered = [j for group in zip_longest(*(jobs[fmt] for fmt in FORMATS)) for j in group if j]
    identities = [dict(id=j['id'], seed=j['seed'], format=j['meta']['format'], context=j['meta']['context'],
                       policy_sides=j['meta']['policy_sides'], map=j['meta']['map'], map_sha256=j['meta']['map_sha256'],
                       factions=j['factions'], scenario=j['scenario_family']) for j in ordered]
    plan = dict(source=os.environ['SOURCE_COMMIT'], extension_sha256=sha256(_engine_lite.__file__),
                inputs=inputs, games=identities, workers=8, deadline_seconds=SECONDS,
                rules_sha256=sha256(Path(ordered[0]['rules_dir'])/'rules.json'),
                teacher_sha256=ordered[0]['meta']['teacher_source_sha256'],
                max_turns=30, selection='validation v10 block 0, all rotations and both team contexts')
    assert len({j['id'] for j in ordered}) == 14 and all(j['max_turns'] == 30 for j in ordered)
    (args.output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    print('FROZEN', sha256(args.output/'plan.json'), flush=True)
    deadline = time()+SECONDS
    for j in ordered:
        j['deadline'] = deadline
    with patch.object(sample, 'play_job', timed_job):
        start = monotonic()
        results = sample.collect(ordered, 8, args.output/'jobs.jsonl')
        wall = monotonic()-start
    by_format, mismatches = {}, []
    for fmt in FORMATS:
        ids = {j['id'] for j in jobs[fmt]}
        rows = [r for r in results if r['id'] in ids]
        by_format[fmt] = dict(planned=len(ids), returned=len(rows),
            complete=sum(r['status']=='complete' for r in rows),
            faults=sum(bool(r.get('result',{}).get('faults')) for r in rows),
            worker_wall=sum(r['probe']['end']-r['probe']['start'] for r in rows if 'probe' in r),
            worker_cpu=sum(r['probe']['cpu'] for r in rows if 'probe' in r))
        mismatches.extend(r['id'] for r in rows if r.get('result') != expected[r['id']])
    summary = dict(wall=wall, formats=by_format, changed_official_results=mismatches,
                   projected_420_worker_wall_over_8=30*sum(s['worker_wall'] for s in by_format.values())/8)
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary), flush=True)
    assert all(s['planned']==s['returned']==s['complete'] and not s['faults'] for s in by_format.values())
    assert all(r['probe']['weights'] == ['torch.float64'] for r in results)


if __name__ == '__main__':
    main()
