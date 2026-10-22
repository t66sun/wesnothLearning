"""Real native smoke. Each invocation owns a new output directory."""
import argparse
import json
import time
from pathlib import Path
import torch
from learning.common import ROOT,write_json
from learning.model import Policy
from learning.export import export
from learning.sample import collect
from learning.formats import TEAM2V2,FORMATS
from learning.manifest import output_path
import params


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--wesnoth',required=True);p.add_argument('--output',required=True)
    p.add_argument('--players',type=int,nargs='+',default=[2]);p.add_argument('--turns',type=int,default=2)
    p.add_argument('--team2v2',action='store_true')
    p.add_argument('--teacher');args=p.parse_args()
    out=output_path(args.output);out.mkdir(parents=True,exist_ok=False)
    torch.manual_seed(7);models={fmt:Policy(fmt) for fmt in FORMATS}
    addon=export(models,out/'bot',mode='rule')
    support=export(models,out/'support',name='LearningSupport',package=False)
    jobs=[]
    cases=[(n,False) for n in args.players]+([(4,True)] if args.team2v2 else [])
    for n,team in cases:
        bot=args.teacher or str(addon)
        training={'teacher':Path(args.teacher).stem if args.teacher else False,'version':'smoke'}
        suffix='team2v2' if team else str(n)
        jobs.append(dict(id=f'smoke-{suffix}',bots=[bot]+['baseline']*(n-1),seed=500+n,
            factions=[params.FACTIONS[i%6] for i in range(n)],max_turns=args.turns,
            wesnoth=args.wesnoth,output=str(out/f'game{suffix}.json'),shard=str(out/f'game{suffix}.jsonl.gz') if n in (2,4) else None,teams=TEAM2V2 if team else None,
            deadline=time.time()+600,timeout=10 if args.teacher else 1,
            learning=dict(support=str(support),sides={'1':training})))
    results=collect(jobs,1,out/'jobs.jsonl');write_json(out/'summary.json',results)
    print(json.dumps([{k:r[k] for k in ('id','status','coverage') if k in r} for r in results]))
    for r in results:
        assert r['status']=='complete',r
        assert not r['result']['faults'],r['result']['faults']
        assert r['coverage']['matched']>0,r


if __name__=='__main__':main()
