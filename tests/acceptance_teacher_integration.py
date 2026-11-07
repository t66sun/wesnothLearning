"""Explicit fixed 48-game integration panel; never constructs an optimizer."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import time

from learning.common import ROOT, read_json, write_json, sha256
from learning.formats import FORMATS, PLAYERS
from learning.experiment import FormatExperiment, default_config, coverage_gate
from learning.maps import SPLITS
from learning.schedule import teacher_jobs, rollout_jobs
from learning.teachers import roles
from learning.teachers.registry import freeze_set, execution_matrix
from learning.tasks import TASK_ID

SEED=20261107
WORKERS=8
SECONDS=3600


def prepare(output,started=None):
    import torch
    from learning.model import Policy,ARCHITECTURE
    from learning.features import schema
    from learning.export import export
    from learning.rules_catalog import load,resolve_dir
    from learning.manifest import tree_hashes
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    started=time.time() if started is None else started
    deadline=started+SECONDS
    contract=freeze_set(output/'teachers','mixed-20261107')
    rules=resolve_dir();rule=load(rules)
    manifest=dict(source_commit=(ROOT/'SOURCE_COMMIT').read_text().strip(),teacher_set=contract,
        teacher_executions=execution_matrix(contract),task_id=TASK_ID,
        rules=dict(directory=str(rules),rules_sha256=rule['rules_file_sha256']),
        seed=SEED,workers=WORKERS,started=started,deadline=deadline,games=48,
        student='fixed seeded untrained policy; sample mode; no optimizer',
        gate='each backend/format: four BC and four PPO/DAgger; full focal-seat coverage; '+
             'all complete, no faults/hard timeouts, correct identities/labels, nonzero valid DAgger, '+
             'action coverage is diagnostic only; excluded from activation by user instruction')
    students={};supports={}
    for index,fmt in enumerate(FORMATS):
        torch.manual_seed(SEED+index)
        model=Policy(fmt).eval();destination=output/'students'/fmt
        addon=export(model,destination,name='TestStudent'+fmt,mode='sample',package=False,version='fixed-test')
        torch.save(dict(model=model.state_dict(),features=schema(),architecture=ARCHITECTURE,format=fmt),destination/'model.pt')
        students[fmt]=str(addon)
        supports[fmt]=str(export(model,output/'support'/fmt,name='LearningSupport',
                                 package=False,version='fixed-test-support'))
    jobs=[]
    for engine in ('native','lite'):
        for fmt in FORMATS:
            runner=FormatExperiment.__new__(FormatExperiment)
            runner.fmt=fmt;runner.directory=output/engine/fmt
            runner.config=default_config(engine=engine);runner.config['allow_approximate']=True
            runner.manifest=manifest;runner.support=supports[fmt]
            runner.exe=str(ROOT/'.runtime/install/bin/wesnoth')
            runner.teachers=[roles.package(runner)];runner.native_fixed=roles.fixed(runner,'native');runner.fixed=roles.fixed(runner)
            from learning.tasks import reward_config
            from types import SimpleNamespace
            runner.controller=SimpleNamespace(freeze=reward_config)
            runner.collector=lambda pending,log:None
            bc=teacher_jobs(runner.directory,runner.teachers,runner.fixed,runner.support,0,SEED,deadline,
                            runner.exe,formats=[fmt],count=4)
            ppo=rollout_jobs(runner.directory,students[fmt],[students[fmt]],runner.fixed,runner.support,
                            'fixed-test',0,SEED,deadline,runner.exe,formats=[fmt])
            for job in ppo:job['learning']['dagger_teacher']=roles.package(runner)
            for job in bc+ppo:
                job['id']=engine+'-'+job['id']
                job['shard']=str(runner.directory/'data'/(job['id']+'.jsonl.gz'))
                job['output']=str(runner.directory/'replays'/(job['id']+'.json'))
            frozen,_=runner.execute(bc+ppo,'fixed-panel')
            jobs.extend(frozen)
    # Interleave backend/format cells; the fixed eight-worker queue serves all cells.
    jobs.sort(key=lambda j:(j['meta']['phase'],j['meta']['seat'],j['engine'],j['format'],j['id']))
    validate_design(jobs)
    write_json(output/'jobs.json',jobs)
    manifest.update(schedule_sha256=sha256(output/'jobs.json'),students=tree_hashes(output/'students'),
                    support=tree_hashes(output/'support'))
    write_json(output/'manifest.json',manifest)
    return manifest,jobs


def validate_design(jobs):
    if len(jobs)!=48 or len({j['id'] for j in jobs})!=48:raise ValueError('panel requires 48 unique tasks')
    for engine in ('native','lite'):
        for fmt in FORMATS:
            for phase in ('teacher','ppo'):
                cell=[j for j in jobs if j['engine']==engine and j['format']==fmt and j['meta']['phase']==phase]
                if len(cell)!=4 or {j['meta']['seat'] for j in cell}!=set(range(1,PLAYERS[fmt]+1)):
                    raise ValueError('panel requires four games with complete focal-seat coverage')
                for j in cell:
                    if j['max_turns']!=30 or j['task_id']!=TASK_ID or j['meta']['map_partition']!='train':
                        raise ValueError('panel requires the 30-turn train task')
                    if j['meta']['map'] not in (*SPLITS[fmt]['train'],'arena'+str(PLAYERS[fmt])):
                        raise ValueError('panel map is outside train')


def audit_rows(job):
    from learning.rowpack import unpack_line,plain_row
    from hashlib import sha256 as digest
    from learning.teachers.registry import execution_identity
    from learning.teachers.provenance import validate_identity
    from learning.data import validate_record
    from learning.coverage import matching
    result=dict(rows=0,valid=0,unmatched=0,dagger_rows=0,dagger_valid=0,dagger_queries=0,errors=[])
    path=Path(job['shard'])
    is_bc=job['meta']['phase']=='teacher'
    files=[(path,is_bc,False)]
    if not is_bc:files.append((path.with_name(path.name.replace('.jsonl.gz','.dagger.jsonl.gz')),True,True))
    expected=execution_identity(job['teacher_roles']['supervision'],job['engine'])
    history=[]
    context_keys=('game_id','game_family','scenario_family','side','turn','decision','task_id',
                  'global','opponents','spatial','candidates','memory_write')
    for source,teacher,dagger in files:
        if not source.exists():
            result['errors'].append('missing shard '+str(source));continue
        with gzip.open(source,'rt') as stream:
            for line in stream:
                row=unpack_line(line)[0];choice=row.get('choice',-1)
                key='dagger_rows' if dagger else 'rows';result[key]+=1
                try:
                    if row.get('game_id')!=job['id'] or row.get('task_id')!=TASK_ID or row.get('side')!=job['meta']['seat']:
                        raise ValueError('row differs from its frozen task or focal seat')
                    public=digest(json.dumps(plain_row({k:row.get(k) for k in context_keys}),sort_keys=True).encode()).hexdigest()
                    if dagger:
                        if result[key]>len(history) or history[result[key]-1]!=public:
                            raise ValueError('DAgger public history differs from student history')
                        if row.get('teacher_query'):result['dagger_queries']+=1
                    else:history.append(public)
                    if teacher:
                        if row.get('source')!='teacher':raise ValueError('teacher row is in the wrong source category')
                        validate_identity(row,job['format'])
                        if any(row.get(k)!=v for k,v in expected.items()):raise ValueError('wrong teacher')
                    elif row.get('source')!='policy' or row.get('teacher_contract'):
                        raise ValueError('student record is labelled as teacher')
                    if choice>=0:
                        validate_record(row,job['format'])
                        if teacher and matching(row['candidates'],row['actual'])!=choice:
                            raise ValueError('label is not the exact teacher action')
                        result['dagger_valid' if dagger else 'valid']+=1
                    elif teacher and (is_bc or row.get('query_only')):
                        result['unmatched']+=1
                        if 'actual' not in row and not row.get('teacher_query',{}).get('error'):
                            raise ValueError('unmatched teacher intent was lost')
                except (ValueError,KeyError,IndexError) as exc:
                    result['errors'].append(str(exc))
    if not is_bc and result['rows']!=result['dagger_rows']:result['errors'].append('DAgger history length differs')
    if not result['rows']:result['errors'].append('empty student or teacher shard')
    return result


def summarize(output,manifest,jobs,results,finished):
    lookup={r['id']:r for r in results};cells={}
    for engine in ('native','lite'):
        for fmt in FORMATS:
            planned=[j for j in jobs if j['engine']==engine and j['format']==fmt]
            records=[lookup.get(j['id'],dict(id=j['id'],status='missing')) for j in planned]
            bc=[lookup.get(j['id'],dict(status='missing')) for j in planned if j['meta']['phase']=='teacher']
            audits={j['id']:audit_rows(j) for j in planned if lookup.get(j['id'],{}).get('status')=='complete'
                    and not lookup[j['id']].get('result',{}).get('faults')}
            faults=[dict(id=r['id'],status=r['status'],error=r.get('error'),faults=r.get('result',{}).get('faults'))
                    for r in records if r['status']!='complete' or r.get('result',{}).get('faults')]
            queries=[r.get('teacher_queries',{}) for r in records]
            errors=[e for a in audits.values() for e in a['errors']]+[e for q in queries for e in q.get('errors',[])]
            for j in planned:
                if j['meta']['phase']!='ppo' or j['id'] not in audits:continue
                audit=audits[j['id']];query=lookup[j['id']].get('teacher_queries',{})
                if audit['dagger_valid']!=query.get('valid',0) or audit['dagger_queries']!=query.get('queries',0):
                    errors.append(j['id']+': stored DAgger labels differ from query statistics')
            query_count=sum(q.get('queries',0) for q in queries)
            valid_queries=sum(q.get('valid',0) for q in queries)
            stored_queries=sum(a['dagger_valid'] for a in audits.values())
            gate=coverage_gate(bc)
            valid=sum(a['valid'] for j in planned if j['meta']['phase']=='teacher' for a in [audits.get(j['id'],dict(valid=0))])
            valid+=sum(a['dagger_valid'] for a in audits.values())
            cells[engine+'/'+fmt]=dict(completed=sum(r['status']=='complete' and not r.get('result',{}).get('faults') for r in records),
                planned=8,coverage=gate,miss_reasons=dict(sum((Counter(r.get('coverage',{}).get('reasons',{})) for r in bc),Counter())),
                queries=query_count,valid_queries=valid_queries,query_seconds=sum(q.get('seconds',0) for q in queries),
                max_query_ms=max((q.get('max_ms',0) for q in queries),default=0),
                per_game_p95_query_ms={r['id']:r.get('teacher_queries',{}).get('p95_ms',0) for r in records},
                valid_supervision=valid,valid_supervision_per_hour=valid/max(finished-manifest['started'],1e-9)*3600,
                faults=faults,errors=errors,audits=audits,
                passed=not faults and not errors and valid_queries>0 and stored_queries>0 and len(audits)==8)
    summary=dict(source_commit=manifest['source_commit'],seconds=finished-manifest['started'],games=len(results),
                 cells=cells,passed=finished<=manifest['deadline'] and all(c['passed'] for c in cells.values()),
                 scope='integration only; no BC qualification, optimizer, corpus promotion or strength claim')
    write_json(Path(output)/'summary.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    manifest,jobs=prepare(args.output)
    print(json.dumps(dict(source=manifest['source_commit'],games=len(jobs),deadline=manifest['deadline'])),flush=True)
    if args.prepare_only:return
    from learning.sample import collect
    results=collect(jobs,WORKERS,args.output/'jobs.jsonl')
    finished=time.time();write_json(args.output/'results.json',results)
    summary=summarize(args.output,manifest,jobs,results,finished)
    print(json.dumps({k:v for k,v in summary.items() if k!='cells'}),flush=True)
    for key,cell in summary['cells'].items():print(json.dumps(dict(cell=key,**{k:v for k,v in cell.items() if k!='audits'})),flush=True)


if __name__=='__main__':main()
