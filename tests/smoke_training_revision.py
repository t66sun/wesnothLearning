"""Finite native CPU integration: teacher collection, BC, rollout bootstrap, PPO."""
from pathlib import Path
import argparse,json,os,time,threading
import torch
from learning.common import ROOT,write_json
import addons
# The smoke harness installs internal, unpackaged policy directories. Three
# schema-4 models exceed the 16 MiB submission cap; production packaging still
# uses addons.MAX_PACKAGE_BYTES unchanged and remains a separate delivery gate.
addons.MAX_PACKAGE_BYTES = 64 * 1024 * 1024
from learning.formats import FORMATS
from learning.model import Policy
from learning.export import export,verify_numerics,load_model
from learning.schedule import teacher_jobs,rollout_jobs
from learning.sample import collect
from learning.data import read_shards,split
from learning.train import train,checkpoint
from learning.experiment import default_config,validate_config


def ident(fmt,label):
    return next(f'v4-{label}-{fmt}-{i}' for i in range(1000) if split(f'v4-{label}-{fmt}-{i}')=='train')


def main():
    p=argparse.ArgumentParser();p.add_argument('--wesnoth',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    out=(ROOT/args.output).resolve();assert out.is_relative_to(ROOT);out.mkdir(parents=True,exist_ok=False)
    config=default_config('cpu');validate_config(config);write_json(out/'config.json',config)
    torch.set_num_threads(1);torch.manual_seed(17)
    models={f:Policy(f).to('cpu') for f in FORMATS};optimizers={f:torch.optim.Adam(m.parameters(),lr=3e-4) for f,m in models.items()}
    support=export(models,out/'support',name='LearningSupport',package=False)
    fixed=[str(ROOT/'data/opponents/gpt6astra.zip'),'baseline'];deadline=time.time()+600
    jobs=teacher_jobs(out,fixed[:1],fixed,str(support),0,17,deadline,args.wesnoth,count=1)
    teacher_paths={}
    for job in jobs:
        fmt=job['meta']['format'];job['id']=ident(fmt,'teacher');job['max_turns']=2
        job['output']=str(out/'replays'/(job['id']+'.json'));job['shard']=str(out/'data'/(job['id']+'.jsonl.gz'));teacher_paths[fmt]=job['shard']
    teacher_results=collect(jobs,4,out/'teacher.jobs.jsonl')
    assert all(r['status']=='complete' and not r['result']['faults'] and r['training_eligible'] for r in teacher_results),teacher_results
    bc={};bc_updates={}
    for fmt in FORMATS:
        bc[fmt]=read_shards([teacher_paths[fmt]],partition='train',format_name=fmt)
        assert bc[fmt] and all(not r['value_valid'] for r in bc[fmt] if r['truncated'])
        bc_updates[fmt]=train(models[fmt],optimizers[fmt],bc[fmt],'bc',epochs=1,minibatch=8)
        assert bc_updates[fmt]['updates']>0
    policy=export(models,out/'policy',mode='sample',version='v4-smoke',package=False)
    groups=rollout_jobs(out,str(policy),[str(policy)],fixed,str(support),'v4-smoke',0,19,deadline,args.wesnoth)
    jobs=[]
    for fmt,count in [('duel',2),('ffa4',1),('team2v2',1)]:
        chosen=[j for j in groups if j['meta']['format']==fmt][:count]
        for i,job in enumerate(chosen):
            job['id']=ident(fmt,f'policy{i}');job.update(max_turns=2,timeout=2)
            job['output']=str(out/'replays'/(job['id']+'.json'));job['shard']=str(out/'data'/(job['id']+'.jsonl.gz'))
            jobs.append(job)
    # Record real native process concurrency; no separate per-trainer pools.
    peak=[0];stop=threading.Event()
    def monitor():
        if os.name=='nt':return
        while not stop.is_set():
            count=0
            for path in Path('/proc').iterdir():
                if not path.name.isdigit():continue
                try:
                    if (path/'cmdline').read_bytes().split(b'\0')[0]==os.fsencode(args.wesnoth):count+=1
                except (FileNotFoundError,ProcessLookupError,PermissionError):pass
            peak[0]=max(peak[0],count);stop.wait(.1)
    watcher=threading.Thread(target=monitor);watcher.start()
    try:results=collect(jobs,4,out/'policy.jobs.jsonl')
    finally:stop.set();watcher.join()
    assert all(r['status']=='complete' and not r['result']['faults'] and r['training_eligible'] for r in results),results
    ppo_updates={};numerics={};bootstrap_rows={}
    for fmt in FORMATS:
        rows=read_shards([j['shard'] for j in jobs if j['meta']['format']==fmt],format_name=fmt)
        bootstrap_rows[fmt]=sum(r['truncated'] and r['bootstrap_value'] is not None for r in rows)
        assert rows and bootstrap_rows[fmt]>0,(fmt,len(rows),bootstrap_rows)
        ppo_updates[fmt]=train(models[fmt],optimizers[fmt],rows,'ppo',epochs=1,minibatch=8,bc_records=bc[fmt])
        assert ppo_updates[fmt]['updates']>0
        path=out/(fmt+'.pt');checkpoint(path,models[fmt],optimizers[fmt]);restored,state=load_model(path,fmt,'cpu')
        assert not state['cuda_rng'];numerics[fmt]=verify_numerics(restored, bc[fmt] + rows)
    if os.name!='nt':assert peak[0]==4,peak
    summary=dict(passed=True,device='cpu',workers=4,trainer_threads=1,native_games=7,observed_peak_games=peak[0],
        bc_targets=config['bc_games'],bc_updates=bc_updates,ppo_updates=ppo_updates,bootstrap_rows=bootstrap_rows,
        python_lua_max_error=numerics,note='Finite smoke only. Production BC targets were not lowered or claimed complete.')
    write_json(out/'summary.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
