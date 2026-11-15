"""Recount the #360 one-action control matrix from the retained official replies."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
from statistics import mean
import sys


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def points(reply, seat):
    assert reply['task_id'] == 'official-score-30-v1'
    assert reply['task_terminal'] and not reply['faults']
    w = reply['winner']
    assert w in (0, 1, 2)
    assert reply['reason'] != 'turn_limit' or w == 0 and reply['turns'] == 31
    return 3 if w == seat else 1 if w == 0 else 0


def recount(root, capture, expected):
    launch = root/'retained-launch.json'
    assert sha(launch) == expected
    plan = read(launch)
    declared = read(root/'retained-result.json')
    assert declared['launch_sha256'] == expected and declared['optimizer_updates'] == 0
    assert plan['slate_sha256'] == sha(root.parent/'retained-opportunities.json')
    source = capture/'results.jsonl'
    assert plan['capture']['replies_sha256'] == sha(source)
    original = {r['id']:r for line in source.read_text().splitlines() if (r := json.loads(line))}
    records = plan['cases']
    roster = {r['game_id']:r for r in records}
    assert len(roster) == len(records) == 17
    receipt = declared['results']
    assert receipt.keys() == roster.keys()
    counts = Counter()
    for n, case in enumerate(records):
        r, game = receipt[case['game_id']], case['game_id']
        lines = (root/f'worker-{n}.jsonl').read_text().splitlines()
        states = [(d['stage'],d['state']) for line in lines if (d := json.loads(line))]
        counts.update(f'{x}:{y}' for x,y in states)
        if r['status'] == 'complete':
            assert states == [(phase,status) for phase in ('baseline','identical','alternate') for status in ('started','complete')]
            assert points(original[game]['result'],case['side']) == points(r['outcome'],case['side'])
            assert r['outcome'] == original[game]['result']
            assert all(r[k]==v for k,v in case.items())
            for k in ('engine_id', 'rng_version','combat_version','factions','bots','task_id'):
                assert r['outcome'][k] == r['alternate_outcome'][k]
            assert r['logp_error'] <= 1e-5
    assert counts == declared['counts']
    exit_code = int((root/'retained-launcher.exit').read_text().strip())
    complete = all(r['status']=='complete' for r in receipt.values()) and len(receipt)==17
    assert complete == declared['passed'] == (exit_code==0)
    results = {}
    for game,r in receipt.items():
        if r['status'] != 'complete':
            results[game]=dict(status=r['status'],error=r.get('error'))
            continue
        baseline, variation = (points(r[s],r['side']) for s in ('outcome','alternate_outcome'))
        delta=variation-baseline
        if complete:
            assert [baseline,variation,delta]==[r['original_points'],r['alternate_points'],r['point_change']]
        results[game]=dict(status='complete', original=baseline, alternate=variation, delta=delta)
    contrast = None
    if complete:
        shift=[r['delta']/3 for r in results.values()]
        rng=random.Random(2026111760)
        support=sorted(mean(rng.choices(shift,k=len(shift))) for _ in range(10000))
        labels=Counter('improvement' if v>0 else 'decline' if v<0 else 'tie' for v in shift)
        contrast=dict(point=mean(shift),interval95=[support[250],support[9750]],direction=labels)
        assert all(declared['contrast'][k]==v for k,v in contrast.items())
        contrast['original_wdl']=[sum(r['original']==v for r in results.values()) for v in (3,1,0)]
        contrast['alternate_wdl']=[sum(r['alternate']==v for r in results.values()) for v in (3,1,0)]
    else:
        assert declared['contrast'] is None
    return dict(launch_sha256=expected, result_sha256=sha(root/'retained-result.json'),
                exit_code=exit_code, completed_set=complete, counts=counts, contrast=contrast,
                wall_seconds=declared['wall_s'], optimizer_updates=0, results=results)


if __name__=='__main__':
    run, source, digest, output = sys.argv[1:]
    with Path(output).open('x',encoding='utf-8') as stream:
        result=recount(Path(run),Path(source),digest)
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='results'}))
