"""Time one archived self-team validation game and fingerprint each student decision."""
from argparse import ArgumentParser
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
from time import monotonic, process_time, time
from unittest.mock import patch

import _engine_lite

from learning import lite_host
from learning.common import sha256
from learning.lite_policy import FrozenPolicies
from learning.sample import play_job


def fingerprint(digest, value):
    digest.update(json.dumps(value, sort_keys=True, separators=(',', ':')).encode() + b'\n')


def timed_modules(original, output, *args):
    modules = original(*args)
    functions = {'observation.lua': ('capture',), 'spatial.lua': ('memory_observation',),
                 'candidates.lua': ('generate', 'diagnostics'), 'rewards.lua': ('capture',)}
    for name, methods in functions.items():
        source = modules[name]
        wrapper = '''
            if not __cost then
                __cost={}
                local open=io.open
                local write=OUTPUT
                __cost_finalizer=setmetatable({}, {__gc=function()
                    local stream=assert(open(write,'w'))
                    for k,values in pairs(__cost) do
                        stream:write(k,'\\t',table.concat(values,','),'\\n')
                    end
                    stream:close()
                end})
            end
            local function time_method(key,method)
                local run=mod[method];local samples={};__cost[key]=samples
                mod[method]=function(...)
                    local start=os.clock();local values=table.pack(run(...))
                    samples[#samples+1]=os.clock()-start
                    return table.unpack(values,1,values.n)
                end
            end
        '''.replace('OUTPUT', json.dumps(str(output)))
        for method in methods:
            wrapper += f'\ntime_method("{name}/{method}","{method}")'
        modules[name] = 'local mod=(function()\n'+source+'\nend)()\n'+wrapper+'\nreturn mod\n'
    return modules


def main():
    parser=ArgumentParser(description=__doc__)
    parser.add_argument('source_run',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--score-policy',action='store_true')
    args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    base=args.source_run/'team2v2';schedule=base/'schedules/validation-000010.json'
    job_id='val000010-team2v2-b0000-self_team-r0'
    job,=(j for j in json.loads(schedule.read_text()) if j['id']==job_id)
    expected,=(r for line in (base/'jobs.jsonl').read_text().splitlines() if (r:=json.loads(line))['id']==job_id)
    assert job['meta']['map_partition']=='validation' and not job.get('shard') and not job.get('learner_sides')
    del job['learning']
    job.update(output=str(output/'replay.json'),deadline=time()+115,score_only_astra=True,score_only_policy=args.score_policy)
    totals=Counter();counts=Counter();streams={k:hashlib.sha256() for k in ('policy_inputs','model_output','writes','actions')}
    decide,execute=lite_host.LiteHost.decision,lite_host.LiteHost.execute
    init,commit=FrozenPolicies.__init__,FrozenPolicies.commit
    original=lite_host.host_modules;role=None

    def capture_row(host,side,**opts):
        nonlocal role
        role='astra' if opts['teacher'] else 'policy'
        t=process_time();row=decide(host,side,**opts);totals[role+'_decision']+=process_time()-t
        counts[role]+=1
        if role=='policy':
            fingerprint(streams['policy_inputs'],[row[k] for k in ('side','turn','global','opponents','spatial','candidates')])
        return row

    def capture_execution(host,action,**opts):
        t=process_time();out=execute(host,action,**opts);totals[role+'_execute']+=process_time()-t
        fields={k:action[k] for k in ('kind','x','y','tx','ty','ex','ey','type','weapon','full') if k in action}
        fingerprint(streams['actions'],[role,fields,out['events'],out['committed']]);return out

    def capture_output(module,inputs,result):
        for tensor in result: streams['model_output'].update(tensor.detach().contiguous().numpy().tobytes())

    def capture_init(policies,job):
        init(policies,job)
        for model in set(policies.models.values()): model.register_forward_hook(capture_output)

    def capture_commit(policies,side,row,outcome):
        size=len(policies.histories[side]);commit(policies,side,row,outcome)
        if len(policies.histories[side])>size:
            counts['writes']+=1;fingerprint(streams['writes'],[side,row['turn'],outcome['memory_write']])

    with ExitStack() as stack:
        for obj,name,replacement in ((lite_host,'host_modules',lambda *a:timed_modules(original,output/'lua.tsv',*a)),
                (lite_host.LiteHost,'decision',capture_row),(lite_host.LiteHost,'execute',capture_execution),
                (FrozenPolicies,'__init__',capture_init),(FrozenPolicies,'commit',capture_commit)):
            stack.enter_context(patch.object(obj,name,replacement))
        start,cpu=monotonic(),process_time();result=play_job(job);wall,cpu=monotonic()-start,process_time()-cpu
    summary=dict(source=os.environ['SOURCE_COMMIT'],extension_sha256=sha256(_engine_lite.__file__),
        schedule_sha256=sha256(schedule),model_sha256=sha256(Path(job['meta']['policy']).parent/'model.pt'),
        rules_sha256=sha256(Path(job['rules_dir'])/'rules.json'),teacher_sha256=job['meta']['teacher_source_sha256'],
        id=job_id,seed=job['seed'],score_only_policy=args.score_policy,status=result['status'],error=result.get('error'),
        counts=counts,cpu_by_role=totals,cpu=cpu,wall=wall,hashes={k:s.hexdigest() for k,s in streams.items()},
        result=result.get('result'),archived_result=expected['result'])
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ('status','counts','cpu_by_role','cpu','wall','hashes')}),flush=True)
    assert result['status']=='complete' and result['result']==expected['result'] and not result['result']['faults'],result


if __name__=='__main__':
    main()
