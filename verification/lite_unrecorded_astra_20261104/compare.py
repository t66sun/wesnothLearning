"""Replay the v10 team validation job with its real learner and complete reward evidence."""
import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
from time import monotonic, process_time, time
from unittest.mock import patch

import _engine_lite

from learning import reward_metrics
from learning.common import sha256
from learning.lite_host import LiteHost
from learning.lite_policy import FrozenPolicies
from learning.rowpack import plain_row
from learning.sample import play_job
from learning.trajectory_buffer import TrajectoryBuffer


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_run',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    base=args.source_run/'team2v2';schedule=base/'schedules/validation-000010.json'
    job_id='val000010-team2v2-b0000-astra_partner-r0'
    job,=(j for j in json.loads(schedule.read_text()) if j['id']==job_id)
    expected,=(r for line in (base/'jobs.jsonl').read_text().splitlines() if (r:=json.loads(line))['id']==job_id)
    assert job['meta']['map_partition']=='validation' and not job.get('shard')
    assert set(job['learning']['sides'])=={'1'} and job['meta']['policy_sides']==[1]
    # v10 predates the ordinary validation phase tag. Current production sets it
    # before execution so the reward controller receives horizon 5 and 10.
    job['meta']['phase']='validation'
    job.update(deadline=time()+115,output=str(args.output/'replay.json'))
    hashes={k:hashlib.sha256() for k in ('learner_rows','policy_inputs','predictions','writes','snapshots','actions')}
    counts=Counter();route=Counter();cpu_by_role=Counter();side=None
    def record(key,value):
        hashes[key].update(json.dumps(value,sort_keys=True,separators=(',',':')).encode()+b'\n');counts[key]+=1
    def stable(row):
        value=plain_row(row)
        if 'timing' in value: value['timing']={k:v for k,v in value['timing'].items() if k!='ms'}
        return value
    decide,execute,choose,commit=LiteHost.decision,LiteHost.execute,FrozenPolicies.choose,FrozenPolicies.commit
    append,summarize=TrajectoryBuffer.append,reward_metrics.summarize_game
    def observed(host,seat,**options):
        nonlocal side
        side=seat;t=process_time();row=decide(host,seat,**options)
        cpu_by_role['decision'+str(seat)]+=process_time()-t
        route[(str(seat)+'_compact') if set(row)=={'teacher_action'} else (str(seat)+'_full')]+=1
        return row
    def played(host,action,**options):
        t=process_time();out=execute(host,action,**options);cpu_by_role['execute'+str(side)]+=process_time()-t
        fields={k:action[k] for k in ('kind','x','y','tx','ty','ex','ey','type','weapon','full') if k in action}
        record('actions',[side,fields,out['events'],out['committed']]);return out
    def chosen(policies,row,seat,bootstrap=False):
        record('policy_inputs',[seat,bootstrap,stable(row)])
        result=choose(policies,row,seat,bootstrap=bootstrap);record('predictions',[seat,bootstrap,result]);return result
    def written(policies,seat,row,out):
        size=len(policies.histories[seat]);commit(policies,seat,row,out)
        if len(policies.histories[seat])>size: record('writes',[seat,row['turn'],out['memory_write']])
    def kept(buffer,row):
        record('learner_rows',stable(row));return append(buffer,row)
    def measured(rows,result,job,snapshots=()):
        for item in snapshots: record('snapshots',plain_row(item))
        return summarize(rows,result,job,snapshots=snapshots)
    with ExitStack() as stack:
        for obj,key,f in ((LiteHost,'decision',observed),(LiteHost,'execute',played),(FrozenPolicies,'choose',chosen),
                          (FrozenPolicies,'commit',written),(TrajectoryBuffer,'append',kept),(reward_metrics,'summarize_game',measured)):
            stack.enter_context(patch.object(obj,key,f))
        start,cpu=monotonic(),process_time();result=play_job(job);elapsed=monotonic()-start;cpu=process_time()-cpu
    summary=dict(source=os.environ['SOURCE_COMMIT'],extension_sha256=sha256(_engine_lite.__file__),
        rules_sha256=sha256(Path(job['rules_dir'])/'rules.json'), teacher_sha256=job['meta']['teacher_source_sha256'],
        schedule_sha256=sha256(schedule),model_sha256=sha256(Path(job['meta']['policy']).parent/'model.pt'),
        job=job_id,seed=job['seed'],wall=elapsed,cpu=cpu,role_cpu=cpu_by_role,route=route,counts=counts,
        hashes={k:d.hexdigest() for k,d in hashes.items()},record=result)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ('wall','cpu','route','counts','hashes')}),flush=True)
    assert result['status']=='complete' and result['result']==expected['result'] and not result['result']['faults'],result
    diagnostic,=result['reward_diagnostics'];assert diagnostic['side']==1 and diagnostic['complete']
    assert all(diagnostic['horizons'][str(t)] is not None for t in (5,10)) and counts['learner_rows']>0


if __name__=='__main__':main()
