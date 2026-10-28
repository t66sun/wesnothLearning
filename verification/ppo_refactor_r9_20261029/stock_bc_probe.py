"""One real stock teacher game collected through the runner's BC job builder."""
from pathlib import Path
import sys
import time

from learning.common import ROOT, sha256, write_json
from learning.data import read_shards
from learning.features import schema
from learning.manifest import teacher_identity
from learning.sample import play_job
from learning.schedule import stock_teacher_jobs
import native


def main():
    destination = Path(sys.argv[1])
    exe = native.find_wesnoth(sys.argv[2])
    destination.mkdir()  # Never overwrite a prior attempt.
    support = destination/'support'
    (support/'lua').mkdir(parents=True)
    for path in (ROOT/'lua').glob('*.lua'):
        (support/'lua'/path.name).write_text(path.read_text().replace('@ADDON@', 'LearningSupport'))
    (support/'lua/features.lua').write_text('return '+native.lua(schema()))
    (support/'lua/config.lua').write_text('return {candidate_budget_ms=200}')
    record = dict(teacher_identity('wesnoth_default_rca'), runtime_sha256=sha256(exe))
    jobs = stock_teacher_jobs(destination/'run', record, str(support), 0, 20261029,
        time.time()+600, exe, formats=['duel'], count=1, index_stride=1)
    job = jobs[0]
    write_json(destination/'job.json', job)
    summary = play_job(job)
    write_json(destination/'summary.json', summary)
    assert summary['status'] == 'complete', summary
    assert not summary['result']['faults'], summary
    stock = summary['stock_coverage']
    assert stock, 'stock capture produced no label coverage'
    assert sum(c['matched'] for c in stock.values()) > 0, stock
    rows = read_shards([job['shard']], format_name='duel')
    assert rows, 'stock teacher game wrote no rows'
    assert all(row['source'] == 'stock_rca' for row in rows)
    assert all(row['teacher'] == 'wesnoth_default_rca' for row in rows)
    assert all(row['teacher_identity']['query'] == 'none' for row in rows)
    assert all(row['action_source'] == 'engine_events' for row in rows)
    assert all(row['engine_id'] == 'native' for row in rows)
    write_json(destination/'probe.json', dict(
        status='passed', rows=len(rows), seed=job['seed'],
        bots=job['bots'], stock_capture=job['learning']['stock_capture'],
        dagger_status='unsupported_with_stock_rca',
        stock_coverage=stock, shard_sha256=sha256(job['shard']),
        capture_sha256=record['capture_sha256'], runtime_sha256=record['runtime_sha256'],
        rules_sha256=record['rules_sha256'], teacher_query=record['query'],
        kinds=sorted({row['actual']['kind'] for row in rows})))
    print('passed', len(rows), 'rows from one stock teacher game')


if __name__ == '__main__':
    main()
