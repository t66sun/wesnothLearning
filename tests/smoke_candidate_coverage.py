"""Two held-out native teacher rounds, with the production candidate generator."""
from pathlib import Path
import json,time
import torch
from learning.common import ROOT,write_json
from learning.model import Policy
from learning.formats import FORMATS
from learning.export import export,verify_numerics
from learning.sample import collect
from learning.experiment import coverage_gate,read_log


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--round',type=int,choices=(1,2),required=True)
    args=parser.parse_args();index=args.round
    out=ROOT/'verification/candidate_coverage_v2'
    out.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(1);torch.manual_seed(173)
    if not (out/'support/LearningSupport').exists():
        models={f:Policy(f) for f in FORMATS}
        write_json(out/'numerics.json',{f:verify_numerics(m) for f,m in models.items()})
        export(models,out/'support',name='LearningSupport',package=False)
    jobs=[];old={}
    for fmt in FORMATS:
        directory=ROOT/'runs/c3_24h_w8_20261018'/fmt
        completed=[r for r in read_log(directory/'jobs.jsonl') if r.get('meta',{}).get('phase')=='teacher' and r.get('status')=='complete' and not r['result']['faults']]
        original=completed[-index];old[fmt]=original['coverage']
        source=None
        for schedule in (directory/'schedules').glob('bc-batch-*.json'):
            for row in json.loads(schedule.read_text()):
                if row['id']==original['id']:source=row;break
            if source:break
        assert source is not None
        ident=f'coverage-v2-r{index}-{fmt}'
        source.update(id=ident,deadline=time.time()+1800,
            output=str(out/'replays'/(ident+'.json')),shard=str(out/'data'/(ident+'.jsonl.gz')))
        source['learning']['support']=str(out/'support/LearningSupport')
        jobs.append(source)
    write_json(out/f'round{index}.schedule.json',jobs)
    results=collect(jobs,workers=8,log_path=out/f'round{index}.jobs.jsonl')
    summary=dict(round=index,previous=old,formats={},faults=[])
    for fmt in FORMATS:
        rows=[r for r in results if r.get('meta',{}).get('format')==fmt]
        summary['formats'][fmt]=coverage_gate(rows)
        summary['faults'] += [dict(format=fmt,status=r['status'],faults=r.get('result',{}).get('faults'),error=r.get('error'))
            for r in rows if r['status']!='complete' or r['result']['faults']]
    summary['passed']=not summary['faults'] and all(v['passed'] for v in summary['formats'].values())
    write_json(out/f'round{index}.summary.json',summary)
    print(json.dumps(summary,indent=2),flush=True)
    if index==2:
        combined=read_log(out/'round1.jobs.jsonl')+results
        gate={f:coverage_gate([r for r in combined if r.get('meta',{}).get('format')==f]) for f in FORMATS}
        final=dict(passed=summary['passed'] and json.loads((out/'round1.summary.json').read_text())['passed']
            and all(v['passed'] for v in gate.values()),games=len(combined),formats=gate)
        write_json(out/'summary.json',final);print(json.dumps(final,indent=2),flush=True)


if __name__=='__main__':main()
