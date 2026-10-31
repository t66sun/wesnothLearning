"""Frozen schedules; official baseline participates in every 2v2 role."""
from itertools import combinations
from math import gcd
from pathlib import Path
import random
from .common import write_json, read_json, sha256
from .formats import FORMATS, PLAYERS, TEAM2V2
import params
from .maps import SPLITS, decorate


def factions(block, players):
    return [params.FACTIONS[(block*players+i)%6] for i in range(players)]


def starting_factions(players, format_name=None):
    """Every distinct faction assignment the frozen roster can start from."""
    pool=list(params.FACTIONS)
    if players==2:
        return [list(pair) for pair in combinations(pool,2)]
    if format_name=='team2v2':
        designs=[]
        for team in combinations(pool,2):
            rest=[faction for faction in pool if faction not in team]
            designs.append([team[0],rest[0],team[1],rest[1]])
        return designs
    return [list(group) for group in combinations(pool,players)]


def scenario_factions(index, players, format_name=None):
    """Cycle the frozen faction designs so collected games cover the whole roster."""
    designs=starting_factions(players,format_name)
    return list(designs[index%len(designs)])


def base_job(directory, ident, bots, seed, deadline, wesnoth, block=0, format_name=None,
             faction_list=None):
    return dict(id=ident, bots=bots, seed=seed & 0xffffffff,
                factions=list(faction_list) if faction_list else factions(block,len(bots)),
                max_turns=30, deadline=deadline,
                wesnoth=wesnoth, output=str(Path(directory)/'replays'/(ident+'.json')),
                teams=TEAM2V2 if format_name=='team2v2' else None)


def evaluation_jobs(directory, policy, control, fixed, blocks, seed, deadline, wesnoth,
                    label='selected', formats=FORMATS, team_contexts=('baseline_partner','self_team'),faction_cycle=0,
                    *, scenarios=None,repeats=None,min_distinct=12):
    """A block contains full seat rotations; 2v2 includes two teammate contexts."""
    jobs=[]
    rng=random.Random(seed)
    for fmt in formats:
        n=PLAYERS[fmt]
        from .maps import SPLITS
        phase='final' if label.startswith('final-') else 'validation'
        names=SPLITS[fmt]['holdout' if phase=='final' else 'validation']
        roster=(scenarios.get(fmt) if isinstance(scenarios,dict) else scenarios) if scenarios is not None else [
            dict(map_index=i,factions=list(group)) for group in starting_factions(n,fmt)
            for i in range(len(names))]
        if not roster: raise ValueError('empty evaluation scenario design')
        if repeats is not None and blocks!=len(roster)*repeats:
            raise ValueError('evaluation repeats must match the existing block budget')
        for block in range(blocks):
            scenario=roster[(block+faction_cycle)%len(roster)]
            contexts=team_contexts if fmt=='team2v2' else ('solo',)
            for context in contexts:
                if fmt=='team2v2':
                    partner=('baseline' if context=='baseline_partner' and 'baseline' in fixed
                             else next((p for p in fixed if p!='baseline'),None))
                    if context=='astra_partner' and partner is None: raise ValueError('Astra partner missing')
                    external=context in ('baseline_partner','astra_partner')
                    seats=[policy,control,partner,partner] if external else [policy,control,policy,control]
                    roles=['policy','control','partner','partner'] if external else ['policy','control','policy','control']
                else:
                    seats=[policy,control]+[rng.choice(fixed) for _ in range(n-2)]
                    roles=['policy','control']+['field']*(n-2)
                block_seed=rng.randrange(2**32)
                for rotation in range(n):
                    bots=seats[rotation:]+seats[:rotation]
                    rotated=roles[rotation:]+roles[:rotation]
                    ident=f'{label}-{fmt}-b{block:04}-{context}-r{rotation}'
                    job=base_job(directory,ident,bots,block_seed,deadline,wesnoth,scenario.get('faction_block',0),fmt,
                                 faction_list=scenario.get('factions'))
                    job['meta']=dict(format=fmt,block=block,rotation=rotation,context=context,
                        label=label,policy=policy,control=control,faction_cycle=faction_cycle,
                        design_scenario=dict(scenario),repeat=block//len(roster),min_distinct=min_distinct,
                        policy_sides=[i for i,r in enumerate(rotated,1) if r=='policy'],
                        control_sides=[i for i,r in enumerate(rotated,1) if r=='control'])
                    decorate(job,fmt,scenario['map_index'],phase)
                    jobs.append(job)
    # Interleave formats and blocks so the deadline cannot systematically starve FFA8/2v2.
    return sorted(jobs,key=lambda j:(j['meta']['block'],j['meta']['rotation'],FORMATS.index(j['meta']['format']),j['meta']['context']))


def calibration_jobs(directory, fixed, blocks, seed, deadline, wesnoth, formats=FORMATS):
    """Reference games keep their original three-block faction rotation."""
    legacy={fmt:[dict(map_index=i,faction_block=f)
                 for f in range(len(params.FACTIONS)//gcd(PLAYERS[fmt],len(params.FACTIONS)))
                 for i in range(len(SPLITS[fmt]['validation']))] for fmt in formats}
    jobs=[]
    for pair,(a,b) in enumerate(combinations(fixed,2)):
        jobs.extend(evaluation_jobs(directory,a,b,fixed,blocks,seed+pair*100003,
                                     deadline,wesnoth,label=f'cal{pair:02}',formats=formats,
                                     scenarios=legacy))
    return jobs


def teacher_jobs(directory, teachers, fixed, support, batch_index, seed, deadline, wesnoth, formats=FORMATS,count=1,index_stride=None):
    jobs=[]
    rng=random.Random(seed+batch_index)
    if len(teachers)!=1 or Path(teachers[0]).stem!='gpt6astra': raise ValueError('only Astra may provide teacher actions')
    for fmt in formats:
        n=PLAYERS[fmt]
        for game in range(count):
            i=batch_index*(index_stride or count)+game
            teacher=teachers[0]
            bots=[teacher]+[rng.choice(fixed) for _ in range(n-1)]
            if fmt=='team2v2':
                bots[2]='baseline'  # The focal teacher must learn in a team with official RCA.
            rotation=i%n
            bots=bots[rotation:]+bots[:rotation]
            side=(n-rotation)%n+1
            ident=f'teacher-{i:05}-{fmt}-t0'
            job=base_job(directory,ident,bots,rng.randrange(2**32),deadline,wesnoth,i,fmt,
                         faction_list=scenario_factions(i,n,fmt))
            job.update(shard=str(Path(directory)/'data'/(ident+'.jsonl.gz')),
                       # Collector work is training instrumentation. Formal evaluation keeps 1/10 s.
                       timeout=10,learning=dict(support=support,sides={str(side):dict(teacher=Path(teacher).stem,version='teacher-frozen')}),
                       meta=dict(format=fmt,teacher=teacher,seat=side,phase='teacher'))
            decorate(job,fmt,i,'train')
            jobs.append(job)
    return jobs


def stock_teacher_jobs(directory, record, support, batch_index, seed, deadline, wesnoth,
                       formats=FORMATS, count=1, index_stride=None):
    """A stock teacher labels full native games; no teacher is added to any seat."""
    from .teacher_protocol import stock_capture_job_sides
    if record['query'] != 'none':
        raise ValueError('stock teacher jobs require a teacher without a per-decision query')
    if not record.get('runtime_sha256'):
        raise ValueError('stock teacher record lacks the runtime it was frozen against')
    rng = random.Random(seed + batch_index)
    jobs = []
    for fmt in formats:
        n = PLAYERS[fmt]
        for game in range(count):
            i = batch_index * (index_stride or count) + game
            bots = ['baseline'] * n
            rotation = i % n
            ident = f'stock-{i:05}-{fmt}-t0'
            job = base_job(directory, ident, bots, rng.randrange(2**32), deadline, wesnoth, i, fmt,
                           faction_list=scenario_factions(i, n, fmt))
            job.update(shard=str(Path(directory) / 'data' / (ident + '.jsonl.gz')),
                       engine='native', timeout=10,
                       learning=dict(support=support, sides={}, stock_capture=stock_capture_job_sides(n)),
                       teacher_identity=dict(record),
                       meta=dict(format=fmt, teacher='baseline', teacher_identity=dict(record),
                                 seat=None, rotation=rotation, phase='teacher'))
            decorate(job, fmt, i, 'train')
            jobs.append(job)
    return jobs


def compose_training_scenario(job):
    """Select an eligible existing training scenario without changing game roles/RNG."""
    from .data import split
    from .maps import SPLITS

    request = job['training_scenario']
    fmt = job['meta']['format']
    budget = 2 * len(SPLITS[fmt]['train']) * len(params.FACTIONS)
    for offset in range(budget):
        index = request['index'] + offset
        block = request['faction_block'] + offset
        job['factions'] = factions(block, len(job['bots']))
        decorate(job, fmt, index, 'train')
        if split(job['scenario_family']) == 'train':
            job['meta']['eligibility_swap'] = dict(requested_index=request['index'],
                requested_faction_block=request['faction_block'], selected_index=index,
                selected_faction_block=block, offset=offset)
            return job
    raise ValueError('no eligible scenario in the frozen training design: ' + fmt)


def rollout_jobs(directory, policy, history, fixed, support, version, batch_index, seed,
                 deadline, wesnoth, games_per_format=4, current=None, formats=FORMATS):
    jobs=[]
    rng=random.Random(seed+batch_index*1009)
    current=current or policy
    slot=batch_index*sum((PLAYERS[f]-(2 if f=='team2v2' else 1))*games_per_format for f in formats)
    for fmt in formats:
        n=PLAYERS[fmt]
        baseline='baseline' if 'baseline' in fixed else (fixed[0] if fixed else current)
        teammates=[p for p in fixed if p!='baseline'] or [baseline]
        for game in range(games_per_format):
            bots=[policy];composition=[]
            for enemy_slot in range(n-1):
                if fmt=='team2v2' and enemy_slot==1:
                    bots.append(baseline);composition.append(dict(role='teammate',path=baseline))
                    continue
                kind=('fixed','fixed','history','current')[slot%4];slot+=1
                path=rng.choice(fixed) if kind=='fixed' else rng.choice(history) if kind=='history' else current
                bots.append(path);composition.append(dict(role=kind,path=path))
            if fmt=='team2v2':
                # Exact 4-game teammate cycle: RCA, fixed teacher, current, current.
                teammate=(baseline,rng.choice(teammates),current,current)[game%4]
                bots[2]=teammate
                composition[1]=dict(role='teammate',path=teammate)
            rotation=(batch_index+game)%n
            bots=bots[rotation:]+bots[:rotation]
            learner_side=(n-rotation)%n+1
            ident=f'rollout-{batch_index:05}-{fmt}-g{game}'
            job=base_job(directory,ident,bots,rng.randrange(2**32),deadline,wesnoth,batch_index+game,fmt)
            job.update(shard=str(Path(directory)/'data'/(ident+'.jsonl.gz')),
                       learning=dict(support=support,sides={str(learner_side):dict(teacher=False,version=version,sampling_seed=job['seed']%2147483646+1)}),
                       meta=dict(format=fmt,phase='ppo',version=version,seat=learner_side,composition=composition))
            job['training_scenario'] = dict(index=batch_index*games_per_format+game,
                                            faction_block=batch_index+game)
            compose_training_scenario(job)
            jobs.append(job)
    # All jobs keep their policy and history paths fixed until the batch completes.
    return jobs


def freeze_schedule(path, jobs):
    path=Path(path)
    if path.exists():
        existing=read_json(path)
        if existing!=jobs:
            raise ValueError('refusing to alter an existing frozen schedule: '+str(path))
    else:
        write_json(path,jobs)
    return sha256(path)
