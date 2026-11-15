"""Recount the exact within-history v100 to v200 #306 selection panels."""
from collections import defaultdict
import json
from pathlib import Path
import random
from statistics import mean
import sys

from audit_archive import RUNS, WALL, records, slot, terminal_points
from learning.common import read_json, sha256


def within_cell(duel, versions):
    log = {r['id']:r for r in records(duel/'jobs.jsonl') if r.get('meta',{}).get('phase')=='validation'}
    scores, identities = {}, {}
    for version in (100,200):
        path=duel/'schedules'/f'validation-{version:06d}.json'
        rows=read_json(path)
        score={}
        for j in rows:
            assert f'/v{version:06d}-greedy/' in j['meta']['policy']
            key=slot(j)
            assert j['meta']['map']=='hamlets' and key not in score
            score[key]=terminal_points(j,log[j['id']],key[4])
        assert len(score)==24
        identities[str(version)]=dict(schedule_sha256=sha256(path),weights_sha256=versions[f'v{version}'])
        scores[version]=score
    assert scores[100].keys()==scores[200].keys()
    blocks=defaultdict(list)
    for k,v in scores[200].items():
        blocks[k[:4]+k[5:]].append((k[4],v-scores[100][k]))
    assert len(blocks)==12 and all({s for s,_ in row}=={1,2} and len(row)==2 for row in blocks.values())
    deltas=[sum(v for _,v in row)/6 for row in blocks.values()]
    return dict(identities=identities,score100=sum(scores[100].values())/72,
                score200=sum(scores[200].values())/72,deltas=deltas,point=mean(deltas))


def main():
    inventory=read_json(Path(sys.argv[1]))
    out={}
    for name in WALL:
        duel=RUNS['306']/'cells'/name/'duel'
        row=inventory['inventory_306'][name]
        evidence=within_cell(duel,row['exact_behavior_versions'])
        assert evidence['identities']['100']['weights_sha256']==row['checkpoints']['best_ppo.pt']['weights_sha256']
        out[name]=evidence
    rng=random.Random(2026111753)
    sets=[r['deltas'] for r in out.values()]
    draws=sorted(mean(mean(rng.choices(r,k=len(r))) for r in rng.choices(sets,k=len(sets)))
                 for _ in range(10000))
    print(json.dumps(dict(cells=out,board='hamlets',paired_slots=72,point=mean(r['point'] for r in out.values()),
                          interval95=[draws[250],draws[9750]],approval='read-only existing results'),indent=2))


if __name__=='__main__':
    main()
