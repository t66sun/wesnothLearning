"""Independently reconstruct #374 official W/D/L and paired score intervals."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import random
import sys
import tarfile


def check(expected, boards):
    vectors = list(boards.values())
    histories = 3
    total = 6 * 30 * len(vectors)
    per_seed = [sum(row[h] for group in vectors for row in group)/total for h in range(histories)]
    rng = random.Random(2026111753)
    draws = []
    for _ in range(10000):
        chosen = rng.choices(range(histories), k=histories)
        value = sum(row[h] for group in vectors for row in rng.choices(group,k=30) for h in chosen)
        draws.append(value)
    draws.sort()
    observed = [*expected['per_seed'],expected['point'],*expected['interval95']]
    rebuilt = [*per_seed,sum(per_seed)/3,draws[250]/(3*total),draws[9750]/(3*total)]
    assert len(observed)==len(rebuilt) and all(abs(x-y)<1e-12 for x,y in zip(observed,rebuilt))


def audit(bundle):
    with tarfile.open(bundle,'r:gz') as archive:
        def raw(name):
            return archive.extractfile(name).read()
        def data(name):
            return json.loads(raw(name))
        launch=raw('launch.json')
        assert sha256(launch).hexdigest()==data('start.json')['launch_sha256']
        manifest=json.loads(launch)
        schedule=data('panel/schedule.json')
        active=data('panel/active.json')
        result=raw('panel/results.jsonl')
        scores=data('panel/score.json')
        timing=data('panel/timing.json')
        assert sha256(result).hexdigest()==timing['results_sha256']
        assert sha256(raw('panel/score.json')).hexdigest()==timing['score_sha256']
        assert active==[dict(j,deadline=timing['start']+12600) for j in schedule]
        assert timing['end']<=timing['start']+12600
        ledger=data('panel/training.json')
        endpoints=data('panel/endpoints.json')
        verify_training(archive,manifest,ledger,endpoints)
    replies=[json.loads(line) for line in result.splitlines()]
    lookup={r['id']:r for r in replies}
    assert len(lookup)==len(schedule)==len(replies)==1440
    boards=sorted(manifest['holdout'])
    matrix={}
    counts=defaultdict(Counter)
    roster={}
    for j in schedule:
        r=lookup[j['id']]
        m=j['meta']
        t=r['result']
        seat,=m['policy_sides']
        board,block,role=m['map'],m['block'],m['role']
        assert r['status']=='complete' and r['meta']==m and t['task_terminal'] and not t['faults']
        assert t['task_id']==j['task_id']=='official-score-30-v1' and j['max_turns']==30
        assert t['factions']==j['factions'] and t['bots']==j['bots'] and t['winner'] in (0,1,2)
        assert m['board_sha256']==manifest['holdout'][board]['board_sha256']
        assert m['weights_sha256']==endpoints[role]['weights_sha256']
        assert j['seed']==m['combat_seed']==2026112900+30*boards.index(board)+block
        assert roster.setdefault(block,j['factions'])==j['factions']
        key=board,block,seat,role
        assert key not in matrix
        points=3 if t['winner']==seat else 1 if t['winner']==0 else 0
        matrix[key]=points
        tally=counts[board+'/'+role]
        tally[{0:'loss',1:'draw',3:'win'}[points]]+=1
        tally['points']+=points
        tally['caps']+=int(t['reason']=='turn_limit')
    assert len(set(map(tuple,roster.values())))==30 and len(counts)==24
    assert all(Counter(scores['counts'][k])==v for k,v in counts.items())
    for contrast,expected in scores['pooled'].items():
        left,right=contrast.split('-')
        rows={}
        for b in boards:
            groups=[]
            for block in range(30):
                diffs=[]
                for seed in manifest['seeds']:
                    def points(which):
                        name=f'{which}-{seed}' if which in ('cover','stock') else which
                        return sum(matrix[b,block,seat,name] for seat in (1,2))
                    diffs.append(points(left)-points(right))
                groups.append(diffs)
            rows[b]=groups
            check(scores['by_map'][b][contrast],{b:groups})
        check(expected,rows)
    print(json.dumps(dict(archive_sha256=sha256(bundle.read_bytes()).hexdigest(),
        score_games=len(matrix),map_role_cells=len(counts),paired_intervals=20,
        training_games_in_matched_prefix=6*ledger['common_games'],common_games=ledger['common_games'],
        gains=scores['pooled']),indent=2))


def verify_training(archive,manifest,ledger,endpoints):
    def load(path):
        return json.load(archive.extractfile(path))
    games=ledger['common_games']
    assert 0<games<=1400 and games%40==0
    by_seed={}
    for cell,entry in ledger['cells'].items():
        arm,seed=cell.split('-')
        ending=load(f'train/{cell}/exit.json')
        init=load(f'train/{cell}/initialization.json')
        assert init['weights_sha256']==manifest['references']['v38']['weights_sha256'] and init['optimizer_states']==0
        assert ending['deadline']-ending['start']==14400
        rows=[json.loads(line) for line in archive.extractfile(f'train/{cell}/jobs.jsonl')]
        receipts={r['id']:r for r in rows}
        scheduled=load(f'train/{cell}/matched-schedule.json')
        assert len(scheduled)==games
        trace=[]
        maps=Counter()
        targets=0
        for n,j in enumerate(scheduled):
            slot=manifest['design'][n]
            meta=j['meta']
            side=meta['seat']
            assert j['training_scenario']['index']==n and slot[arm]==meta['map']
            assert j['scenario_family']==slot[arm+'_family'] and j['factions']==slot['factions']
            r=receipts[j['id']]
            assert r['training_eligible'] and r['status']=='complete' and not r['result']['faults']
            assert r['result']['task_terminal'] and r['result']['task_id']==manifest['config']['task_id']
            targets+=r['training_shard']['written']
            maps[meta['map']]+=1
            trace.append((n,j['seed'],tuple(j['factions']),side,j['learning']['sides'][str(side)]['sampling_seed']))
        assert by_seed.setdefault(seed,trace)==trace
        assert maps==entry['maps'] and maps['arena2']==games//(5 if arm=='cover' else 2)
        assert targets==entry['eligible_decisions']
        assert endpoints[cell]['path'].endswith(f'/paired-{games:04}.pt')


if __name__=='__main__':
    audit(Path(sys.argv[1]))
