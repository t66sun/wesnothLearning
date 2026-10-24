"""Repeat only the failed pressure arm with disk-backed full trajectories."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import sys

import stress_probe as probe


def collector(index, output, ready, release, results, legacy=False):
    from learning.rowpack import unpack_line, plain_row
    from learning.trajectory_buffer import TrajectoryBuffer
    from learning.sequences import IndexedSequenceStore
    from learning.reward_metrics import summarize_game
    assert not legacy
    with TrajectoryBuffer() as rows:
        with gzip.open(probe.TRACE, 'rt') as stream:
            for number, line in enumerate(stream):
                row, _ = unpack_line(line, plain=True)
                rows.append(row)
        ready.put(dict(role='collector', index=index, rows=len(rows), pid=os.getpid()))
        if not release.wait(600):raise TimeoutError('write barrier')
        with IndexedSequenceStore(Path(output)/f'collector-{index}') as store:
            assert store.write(rows) == len(rows)
            payloads = [(key, hashlib.sha256(payload).hexdigest()) for key, payload in
                        store.connection.execute('SELECT id,payload FROM sequences ORDER BY id')]
            entries = store.index()
        evidence = None
        with (probe.RUN/'team2v2/jobs.jsonl').open() as stream:
            for line in stream:
                item=json.loads(line)
                if item['id']=='rollout-00042-team2v2-g1':evidence=item;break
        assert evidence is not None
        diagnostics = summarize_game(rows.metric_rows(), evidence['result'],
            dict(id=evidence['id'],engine='lite',meta=evidence.get('meta',{}),factions=evidence['result']['factions']))
        results.put(dict(role='collector', index=index, rows=len(rows), payloads=payloads,
                         indexed_decisions=sum(x['decisions'] for x in entries),
                         metric_sides=len(diagnostics),temporary_bytes=rows.file.seek(0,2),
                         peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def main():
    output=Path(sys.argv[1]);output.mkdir()
    reference=json.loads(Path(__file__).with_name('baseline_reference.json').read_text())
    probe.collector=collector
    pressure=probe.phase(str(output/'pressure'))
    collectors=[r for r in pressure['results'] if r['role']=='collector']
    assert len(collectors)==8
    for result in collectors:
        assert result['rows']==reference['result']['rows']==1621
        assert result['indexed_decisions']==reference['result']['indexed_decisions']
        assert result['payloads']==[tuple(x) for x in reference['result']['payloads']]
        assert result['metric_sides']>0
    assert len([r for r in pressure['results'] if r['role']=='trainer'])==3
    report=dict(passed=True,trace=str(probe.TRACE),baseline_reference=reference,pressure=pressure)
    (output/'result.json').write_text(json.dumps(report,indent=2))
    print('STRESS_RESULT',json.dumps(report),flush=True)


if __name__=='__main__':main()
