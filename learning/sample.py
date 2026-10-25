from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from multiprocessing import get_context
import json
import gzip
import os
import time
from .common import ROOT, write_json
from .data import write_shard
import match
_priority_set=False


def compatible_map(players):
    """Separate compatibility fixture, never used for 2/4/8 strength claims."""
    width, height = 8 * players + 4, 15
    terrain = [['Gg' for _ in range(width)] for _ in range(height)]
    starts = []
    for i in range(players):
        x, y = 5 + 8 * i, 5 if i % 2 == 0 else 11
        starts.append([x, y])
        terrain[y-1][x-1] = 'Kh'
        for dx, dy in ((-1,0),(1,0),(0,1),(0,-1)):
            terrain[y+dy-1][x+dx-1] = 'Ch'
        terrain[7][x-1] = 'Gg^Vh'
    return dict(terrain=terrain, starts=starts, width=width, height=height)


def opening_map(players):
    """Fixed safe probe: own neutral village four hexes away, distant opponents."""
    width,height=128*players+10,11
    terrain=[['Gg']*width for _ in range(height)];starts=[]
    for i in range(players):
        x,y=5+128*i,6;starts.append([x,y]);terrain[y-1][x-1]='Kh'
        for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)): terrain[y+dy-1][x+dx-1]='Ch'
        terrain[y-1][x+3]='Gg^Vh'
    return dict(terrain=terrain,starts=starts,width=width,height=height)


def play_job(job):
    global _priority_set
    if not _priority_set:
        os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
        if os.name != 'nt': os.nice(5)
        else:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
        _priority_set=True
    output = Path(job['output'])
    if time.time() >= job['deadline']:
        return dict(id=job['id'], status='budget_interrupted')
    if job.get('engine','native')=='lite':
        from .lite_host import play_lite_job
        return play_lite_job(job)
    try:
        result = match.play_game(bots=job['bots'], seed=job['seed'], factions=job['factions'],
            max_turns=job.get('max_turns',30), wesnoth=job['wesnoth'], replay_path=output,
            learning=job.get('learning'), experiment_deadline=job['deadline'],
            timeout=job.get('timeout',1), first_timeout=job.get('first_timeout',10),
            teams=job.get('teams'),fog=job.get('fog',True),shroud=job.get('shroud',False),
            share_view=job.get('share_view',True),share_maps=job.get('share_maps',True),
            map_override=job.get('map_override') or (compatible_map(len(job['bots'])) if len(job['bots']) not in (2,4,8) else None))
    except RuntimeError as exc:
        status='budget_interrupted' if 'experiment_budget_interrupted' in str(exc) else 'infrastructure_error'
        return dict(id=job['id'], status=status, error=str(exc))
    records=[];native_timings=[];bootstraps={};metric_snapshots=[]
    event_path=output.with_suffix('.events.jsonl.gz') if job.get('learning') else output.with_suffix('.events.jsonl')
    event_stream=gzip.open(event_path,'rt',encoding='utf-8') if job.get('learning') else event_path.open(encoding='utf-8')
    with event_stream as stream:
        for line in stream:
            event=json.loads(line)
            if event['event']=='LEARN': records.append(event['data'])
            elif event['event']=='METRIC': metric_snapshots.append(event['data'])
            elif event['event']=='BOOTSTRAP':bootstraps[str(event['data']['side'])]=event['data']
            elif event['event']=='RETURN' and 'elapsed_ms' in event['data']:
                native_timings.append(event['data'])
    matched=sum(r['choice']>=0 for r in records)
    coverage={}
    for kind in ('recruit','move','attack','end_turn'):
        rows=[r for r in records if (r.get('actual',{}).get('kind')==kind or kind=='attack' and r.get('actual',{}).get('kind')=='move_attack') and r.get('representable',True)]
        coverage[kind]=dict(total=len(rows),matched=sum(r['choice']>=0 for r in rows))
    eligible=[r for r in records if r.get('representable',True)]
    written=None
    if job.get('shard'):
        from dataclasses import asdict
        from .features import schema
        from .rewards import RewardConfig
        reward_config=job.get('reward_config') or asdict(RewardConfig())
        provenance=dict(engine='native',engine_id='native',engine_version='1.18.8',native_version='1.18.8',
            rules_version=schema().get('rules_sha256') or 'native-1.18.8',rng_version='native-1.18.8',
            combat_version='native-1.18.8',teacher_profile='native',teacher_source_sha256='native-1.18.8',
            architecture_id='relational_v5',
            reward_config=reward_config,reward_version=reward_config['reward_version'],reward_formula_id=reward_config['reward_formula_id'],
            data_pool='original',teacher_impl='astra_native',game_family=job.get('game_family',job['id']),
            map=job.get('meta',{}).get('map'),map_sha256=job.get('meta',{}).get('map_sha256'),map_partition=job.get('meta',{}).get('map_partition'),
            teammate_context=job.get('meta',{}).get('context','baseline_partner' if job.get('teams') else 'solo'))
        for i,r in enumerate(records):
            r['decision']=i
            r.setdefault('candidate_version',f"schema{r.get('schema')}-"+r['timing'].get('budget','fixed-20000-v1'))
        written=write_shard(job['shard'],job['id'],records,result,bootstraps,provenance)
        if job.get('learning',{}).get('dagger_teacher'):
            dagger=[]
            for row in records:
                label=row.get('dagger') or {}
                context={k:v for k,v in row.items() if k!='dagger'}
                context.update(choice=-1,source='astra',teacher='gpt6astra',data_pool='dagger',value_valid=False)
                if not label.get('error') and label.get('choice',-1)>=0: context.update(label)
                dagger.append(context)
            dagger_path=Path(job['shard']).with_name(Path(job['shard']).name.replace('.jsonl.gz','.dagger.jsonl.gz'))
            write_shard(dagger_path,job['id'],dagger,result,bootstraps,dict(provenance,data_pool='dagger'))
    timings=[r['timing']['ms']+r['timing'].get('inference_ms',0) for r in records]
    from .reward_metrics import summarize_game
    return dict(id=job['id'],status='complete',result=result,meta=job.get('meta',{}),reward_diagnostics=summarize_game(records,result,job,snapshots=metric_snapshots),
        training_eligible=not result.get('faults') and (written is None or bool(written['written'])),training_shard=written,
        coverage=dict(total=len(eligible),matched=sum(r['choice']>=0 for r in eligible),
                      all_actions=len(records),all_matched=matched,kinds=coverage),
        behavior=[r['diagnostics'] for r in records if r.get('diagnostics')],
        timings=timings,native_timings=native_timings,truncated=sum(r['timing']['truncated'] for r in records))


def collect(jobs, workers, log_path):
    if not 1 <= workers <= 16:
        raise ValueError('workers must be in [1,16]')
    results=[]
    Path(log_path).parent.mkdir(parents=True,exist_ok=True)
    if Path(log_path).exists():
        # A crash may leave one uncommitted JSON line. Preserve every complete record.
        with Path(log_path).open('r+b') as stream:
            content=stream.read()
            if content and not content.endswith(b'\n'):
                stream.truncate(content.rfind(b'\n')+1)
    batch_started=time.time()
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as executor, Path(log_path).open('a',encoding='utf-8') as log:
        pending={executor.submit(play_job,j): j for j in jobs}
        for future in as_completed(pending):
            j=pending[future]
            try: r=future.result()
            except Exception as exc: r=dict(id=j['id'],status='infrastructure_error',error=repr(exc))
            results.append(r)
            log.write(json.dumps(r,ensure_ascii=False)+'\n');log.flush()
    elapsed=time.time()-batch_started
    metrics=dict(started=batch_started,seconds=elapsed,workers=workers,games=len(results),
        completed=sum(r['status']=='complete' for r in results),
        decisions=sum(r.get('coverage',{}).get('total',0) for r in results))
    metrics['completed_games_per_hour']=metrics['completed']/max(elapsed,1e-9)*3600
    with Path(log_path).with_suffix('.throughput.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(metrics)+'\n')
    return sorted(results,key=lambda r:r['id'])
