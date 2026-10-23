"""Bounded T5 acceptance; no formal run/checkpoint/config is read or changed."""
import argparse,collections,copy,hashlib,json,math,pathlib,random,time
from concurrent.futures import ProcessPoolExecutor,as_completed
from learning.common import ROOT,read_json,write_json,sha256
from learning.data import split
from learning.features import ACTION,ENTITY,MOVE_FEATURES,schema
from learning.formats import TEAM2V2
from learning.maps import frozen_map
from learning.rules_catalog import resolve_dir

OUT=ROOT/'verification/bc_quality_ubuntu_20261023'
FORMATS=('ffa4','team2v2')
MAX_UPDATES=120

def make_plan():
    import params
    plan=[]
    for fmt in FORMATS:
        for part in ('train','validation'):
            for index,name in enumerate(('clash','isars_cross')):
                board,digest=frozen_map(name)
                rotation=(0,4)[index] if part=='train' else (4,2)[index]
                factions=[params.FACTIONS[(rotation+i)%6] for i in range(4)]
                teams=list(TEAM2V2) if fmt=='team2v2' else [1,2,3,4]
                for seed in range(202610230,202611230):
                    physical=dict(format=fmt,map=digest,seed=seed,factions=factions,teams=teams)
                    family=hashlib.sha256(json.dumps(physical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    if split(family)==part:break
                ident=f't5-{fmt}-{part}-{index}'
                plan.append(dict(id=ident,game_family=family,split=part,seed=seed,factions=factions,
                    teams=teams,map=name,map_sha256=digest,max_turns=12))
    assert len({p['game_family'] for p in plan})==8
    return plan

def play(item):
    from learning.lite_host import play_lite_job
    fmt=item['id'].split('-')[1]
    directory=OUT/'data'/fmt;directory.mkdir(parents=True,exist_ok=True)
    result_path=directory/(item['id']+'.result.json')
    shard=directory/(item['id']+'.jsonl.gz')
    if result_path.exists():
        result=read_json(result_path)
        assert result['status']=='complete' and shard.is_file(),result
        print('REUSE',item['id'],flush=True)
        return result
    board,digest=frozen_map(item['map']);assert digest==item['map_sha256']
    teacher=str(ROOT/'opponents/gpt6astra.zip')
    job=dict(id=item['id'],bots=[teacher]*4,seed=item['seed'],factions=item['factions'],teams=item['teams'],
        map_override=board,max_turns=12,rules_dir=str(resolve_dir()),shard=str(shard),
        deadline=time.time()+600,max_decisions=20000,allow_approximate=True,game_family=item['game_family'],
        engine='lite',meta=dict(format=fmt,map=item['map'],map_sha256=digest,map_partition='train',
            diagnostic_split=item['split'],context='astra_partner' if fmt=='team2v2' else 'solo'),
        learning=dict(sides={str(i):dict(teacher='gpt6astra',version='teacher-frozen') for i in range(1,5)}))
    write_json(directory/(item['id']+'.job.json'),job)
    started=time.monotonic();result=play_lite_job(job);result['wall_seconds']=time.monotonic()-started
    write_json(result_path,result)
    assert result['status']=='complete' and result['training_eligible'] and not result['result']['faults'],result
    print('COLLECTED',item['id'],item['split'],'seconds',round(result['wall_seconds'],2),'coverage',result['coverage'],flush=True)
    return result

def collect():
    OUT.mkdir(parents=True,exist_ok=True)
    plan=make_plan();path=OUT/'plan.json'
    if path.exists():assert read_json(path)==plan,'frozen T5 plan changed'
    else:write_json(path,plan)
    write_json(OUT/'protocol.json',dict(formats=FORMATS,game_families=8,max_turns=12,workers=2,
        train_families_per_format=2,validation_families_per_format=2,optimizer_update_cap=MAX_UPDATES,
        initialization_seed=99,sampler_seed=99,read_seed=71,train_record_limit=2048,validation_record_limit=1024,
        learning_rate=3e-4,selection='final fixed update only; no validation-based tuning',
        criteria=dict(min_move_labels=32,min_validation_families=2,move_accuracy=.35,
                      strictly_better_than_ablation=True,move_coverage=.8,overall_coverage=.9)))
    print('FROZEN_PLAN',json.dumps(plan),flush=True)
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(play,p) for p in plan]
        for future in as_completed(futures):future.result()
    print('COLLECTION_COMPLETE',len(plan),flush=True)

def compare_format(fmt):
    import torch
    from learning.model import Policy
    from learning.sequences import read_shards,training_windows
    from learning.train import train,imitation_quality
    torch.set_num_threads(1)
    masks=[i for i,(name,_) in enumerate(ACTION) if name in {n for n,_ in MOVE_FEATURES}]
    phase=next(i for i,(name,_) in enumerate(ENTITY) if name=='next_round')
    class ZeroedInputs(Policy):
        def encode_scene(self,g,opponents,om,p):
            p=dict(p);p['entities']=p['entities'].clone();p['entities'][...,phase]=0
            return super().encode_scene(g,opponents,om,p)
        def forward(self,g,opponents,actions,om,am,payload):
            actions=actions.clone();actions[:,:,masks]=0;payload=dict(payload)
            for key in ('actors','targets'):
                payload[key]=payload[key].clone();payload[key][...,phase]=0
            return super().forward(g,opponents,actions,om,am,payload)
    plan=[p for p in read_json(OUT/'plan.json') if p['id'].split('-')[1]==fmt]
    paths=[OUT/'data'/fmt/(p['id']+'.jsonl.gz') for p in plan]
    stats={}
    training=read_shards(paths,partition='train',limit=2048,seed=71,format_name=fmt,stats=stats.setdefault('train',{}))
    validation=read_shards(paths,partition='validation',limit=1024,seed=71,format_name=fmt,stats=stats.setdefault('validation',{}))
    families={part:sorted({r['game_family'] for r in rows}) for part,rows in [('train',training),('validation',validation)]}
    factions={part:sorted({r['faction'] for r in rows}) for part,rows in [('train',training),('validation',validation)]}
    assert len(families['train'])==len(families['validation'])==2 and not set(families['train'])&set(families['validation'])
    assert len(factions['train'])==6,factions
    assert all(r['schema']==5 and r['source']=='astra' and r['candidate_version']=='schema5-fixed-20000-v3' for r in training+validation)
    coverage={}
    for part in ('train','validation'):
        total=collections.Counter();matched=collections.Counter()
        for item in plan:
            if item['split']!=part:continue
            result=read_json(OUT/'data'/fmt/(item['id']+'.result.json'))
            total['all']+=result['coverage']['total'];matched['all']+=result['coverage']['matched']
            for kind in ('recruit','move','attack'):
                counts=result['coverage']['kinds'][kind];total[kind]+=counts['total'];matched[kind]+=counts['matched']
        coverage[part]={k:dict(total=total[k],matched=matched[k],ratio=matched[k]/max(1,total[k])) for k in total}
    windows=training_windows(training);steps=max(1,math.ceil(len(windows)/4));epochs=MAX_UPDATES//steps
    assert epochs>0
    intended=epochs*steps
    torch.manual_seed(99);initial=copy.deepcopy(Policy(fmt).state_dict())
    initialization_sha=hashlib.sha256(b''.join(x.numpy().tobytes() for x in initial.values())).hexdigest()
    report=dict(format=fmt,features_version=5,stats=stats,families=families,factions=factions,coverage=coverage,
        shard_sha256={p.name:sha256(p) for p in paths},epochs=epochs,intended_updates=intended,
        initialization_sha256=initialization_sha,masks=dict(actions=[ACTION[i][0] for i in masks],entity='next_round',
          history='encode_scene masks both current and replayed raw histories'),arms={})
    print('DATA',fmt,json.dumps({k:v for k,v in report.items() if k not in ('shard_sha256','families')}),flush=True)
    for arm,cls in [('zeroed_inputs',ZeroedInputs),('tactical_inputs',Policy)]:
        torch.manual_seed(99);random.seed(99)
        model=cls(fmt);model.load_state_dict(initial)
        optimizer=torch.optim.Adam(model.parameters(),lr=3e-4);started=time.monotonic()
        trace=hashlib.sha256()
        def progress(cursor):
            trace.update(str(cursor['decisions_seen']).encode()+b'\n')
            if cursor['updates']%20==0:print('OPTIMIZER',fmt,arm,cursor['updates'],'seconds',round(time.monotonic()-started,1),flush=True)
        result=train(model,optimizer,training,'bc',epochs=epochs,minibatch=256,deadline=time.time()+1800,on_step=progress)
        assert not result['interrupted'] and result['updates']==intended and result['updates']<=MAX_UPDATES,result
        quality=imitation_quality(model,validation)
        per_faction={name:imitation_quality(model,[r for r in validation if r['faction']==name])['formats'][fmt]
                     for name in factions['validation']}
        report['arms'][arm]=dict(training=result,quality=quality,by_faction=per_faction,
            seconds=time.monotonic()-started,sampling_decision_count_trace_sha256=trace.hexdigest())
        torch.save(dict(model=model.state_dict(),features=schema(),format=fmt,initialization_sha256=initialization_sha),OUT/(fmt+'_'+arm+'.pt'))
        write_json(OUT/('comparison_'+fmt+'.json'),report)
        print('RESULT',fmt,arm,json.dumps(report['arms'][arm]),flush=True)
    a=report['arms'];normal=a['tactical_inputs']['quality']['formats'][fmt];zero=a['zeroed_inputs']['quality']['formats'][fmt]
    assert a['tactical_inputs']['sampling_decision_count_trace_sha256']==a['zeroed_inputs']['sampling_decision_count_trace_sha256']
    checks=dict(six_training_factions=len(factions['train'])==6,two_validation_families=len(families['validation'])>=2,
        move_samples=normal['kinds']['move']['samples']>=32,move_accuracy=normal['kinds']['move']['accuracy']>=.35,
        move_gain=normal['kinds']['move']['accuracy']>zero['kinds']['move']['accuracy'],
        move_coverage=all(v['move']['ratio']>=.8 for v in coverage.values()),
        overall_coverage=all(v['all']['ratio']>=.9 for v in coverage.values()))
    status=('inconclusive' if not checks['move_samples'] else 'passed' if all(checks.values()) else 'failed')
    report['acceptance']=dict(status=status,checks=checks,
        formal_bc_gate=report['arms']['tactical_inputs']['quality']['effective'])
    write_json(OUT/('comparison_'+fmt+'.json'),report)
    print('T5_FORMAT',fmt,json.dumps(report['acceptance']),flush=True)
    return report

def compare():
    with ProcessPoolExecutor(max_workers=2) as pool:
        reports=list(pool.map(compare_format,FORMATS))
    statuses=[r['acceptance']['status'] for r in reports]
    result=dict(status='failed' if 'failed' in statuses else 'inconclusive' if 'inconclusive' in statuses else 'passed',
                formats={r['format']:r for r in reports})
    write_json(OUT/'summary.json',result)
    print('T5_COMPLETE',result['status'],flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['collect','compare'])
    args=parser.parse_args();(collect if args.mode=='collect' else compare)()
