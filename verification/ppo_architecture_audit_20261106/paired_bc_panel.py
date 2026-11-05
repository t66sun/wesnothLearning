"""Add a BC anchor to existing complete latest-PPO validation panels.

Only BC matches are new. Original latest results, weights and schedules remain
read-only. No optimizer, collection shard, holdout or selection is invoked.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy
import hashlib
import json
from multiprocessing import get_context
from pathlib import Path
import statistics
import time

import torch

from learning.evaluate import bootstrap, comparisons, official_score
from learning.lite_host import play_lite_job


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def play(job):
    torch.set_num_threads(1)
    return play_lite_job(job)


def main(root, output):
    output.mkdir(parents=True,exist_ok=False)
    plans, original, results, identities = {}, {}, {}, {}
    work=[]
    for fmt, version in (('duel',38),('team2v2',53)):
        directory=root/fmt
        schedules=list((directory/'schedules').glob('nominate-*-astra-*.json'))
        assert len(schedules)==1
        plan=json.loads(schedules[0].read_text())
        ids={j['id'] for j in plan}
        recorded=[json.loads(line) for line in (directory/'jobs.jsonl').open()]
        original[fmt]=[r for r in recorded if r['id'] in ids]
        assert len(original[fmt])==len(plan)
        assert all(r['status']=='complete' and not r['result']['faults'] for r in original[fmt])
        bc=directory/'policies'/f'v{version:06}-greedy'/f'SnapV{version:06}'
        # Confirm the exported BC tensors are exactly the pre-PPO checkpoint.
        a=torch.load(directory/'last_bc.pt',map_location='cpu',weights_only=False)['model']
        b=torch.load(bc.parent/'model.pt',map_location='cpu',weights_only=False)['model']
        assert a.keys()==b.keys() and all(torch.equal(a[k],b[k]) for k in a)
        latest_path=Path(plan[0]['meta']['policy']).parent/'model.pt'
        a=torch.load(directory/'last_ppo.pt',map_location='cpu',weights_only=False)['model']
        b=torch.load(latest_path,map_location='cpu',weights_only=False)['model']
        assert a.keys()==b.keys() and all(torch.equal(a[k],b[k]) for k in a)
        plans[fmt]=dict(latest=plan,bc=[])
        identities[fmt]=dict(original_schedule=str(schedules[0]),schedule_sha256=digest(schedules[0]),
            bc_checkpoint_sha256=digest(directory/'last_bc.pt'),bc_export_sha256=digest(bc.parent/'model.pt'),
            latest_checkpoint_sha256=digest(directory/'last_ppo.pt'),latest_export_sha256=digest(latest_path))
        for j in plan:
            job=copy.deepcopy(j)
            job['id']='bc-anchor-'+j['id']
            job['deadline']=time.time()+7200
            job['output']=str(output/(job['id']+'.json'))
            for key in ('learning','shard'): job.pop(key,None)
            for side in job['meta']['policy_sides']: job['bots'][side-1]=str(bc)
            job['meta']['policy']=str(bc)
            job['meta']['original_id']=j['id']
            job['score_only_astra']=True
            job['score_only_policy']=True
            plans[fmt]['bc'].append(job)
            work.append(job)
        results[fmt]=[]
    (output/'plan.json').write_text(json.dumps(plans,indent=2)+'\n')
    (output/'identities.json').write_text(json.dumps(identities,indent=2)+'\n')
    started=time.time()
    with ProcessPoolExecutor(max_workers=8,mp_context=get_context('spawn')) as pool:
        futures={pool.submit(play,j):j for j in work}
        with (output/'results.jsonl').open('w') as stream:
            for index,future in enumerate(as_completed(futures),1):
                job=futures[future]
                result=future.result()
                results[job['meta']['format']].append(result)
                stream.write(json.dumps(result)+'\n');stream.flush()
                if index%12==0: print(index,'/',len(work),'games',round(time.time()-started,1),'s',flush=True)
    report=dict(wall_seconds=time.time()-started,new_games=len(work),formats={})
    for fmt in plans:
        contexts=('astra_partner','self_team')
        summaries={}
        for name,values in (('bc',results[fmt]),('latest',original[fmt])):
            summaries[name]=comparisons(plans[fmt][name],values,min_blocks=12,min_distinct=12,
                                        team_contexts=contexts)[fmt]
        lookup={r['id']:r for r in original[fmt]+results[fmt]}
        differences={}
        for job in plans[fmt]['bc']:
            old=lookup[job['id']]
            new=lookup[job['meta']['original_id']]
            assert old['status']=='complete' and not old['result']['faults']
            values=[]
            for r in (old,new):
                values.append(statistics.mean(official_score(r['result'],s) for s in job['meta']['policy_sides']))
            key=job['scenario_family']
            differences.setdefault(key,[]).append((values[1]-values[0])/3.)
        paired=[statistics.mean(values) for values in differences.values()]
        summaries['paired_latest_minus_bc_normalized_policy_score']=dict(
            mean=statistics.mean(paired),interval95=bootstrap(paired),distinct_scenarios=len(paired),
            scenario_differences=differences)
        report['formats'][fmt]=summaries
    (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('run',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    main(args.run,args.output)
