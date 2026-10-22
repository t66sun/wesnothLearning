"""Block bootstrap and format-local model/control comparisons."""
from collections import defaultdict
import random
from statistics import mean
from .data import reward
from .formats import FORMATS, PLAYERS


def official_score(result, side):
    if result.get('teams'):
        winner=result['winning_team'];return 1 if not winner else 3 if result['teams'][side-1]==winner else 0
    if len(result['bots'])==2: return 1 if not result['winner'] else 3 if result['winner']==side else 0
    ranks=result['rank_points'];return ranks.get(side,ranks.get(str(side),0))/(len(result['bots'])-1)


def bootstrap(values, seed=19, samples=5000):
    if not values:
        return None
    rng=random.Random(seed)
    means=sorted(mean(rng.choices(values,k=len(values))) for _ in range(samples))
    return [means[int(.025*samples)],means[min(samples-1,int(.975*samples))]]


def comparisons(jobs, results, min_blocks=30, formats=None, team_contexts=('baseline_partner','self_team')):
    lookup={r['id']:r for r in results}
    summary={}
    for fmt in formats or [f for f in FORMATS if any(j.get('meta',{}).get('format')==f for j in jobs)]:
        relevant=[j for j in jobs if j.get('meta',{}).get('format')==fmt]
        if len({j['meta'].get('control') for j in relevant})>1: raise ValueError('compare Astra and baseline in separate rotation blocks')
        groups=defaultdict(list)
        for job in relevant: groups[job['meta']['block']].append(job)
        differences=[];policy_scores=[];control_scores=[];context_values=defaultdict(list);block_values={}
        missing=0;infrastructure=0;fault_games=0
        for block, planned in sorted(groups.items()):
            expected=PLAYERS[fmt]*(len(team_contexts) if fmt=='team2v2' else 1)
            fault_games+=sum(bool(lookup.get(j['id'],{}).get('result',{}).get('faults')) for j in planned)
            complete=len(planned)==expected and all(lookup.get(j['id'],{}).get('status')=='complete'
                and not lookup[j['id']]['result'].get('faults') for j in planned)
            infrastructure+=sum(lookup.get(j['id'],{}).get('status')=='infrastructure_error' for j in planned)
            if not complete:
                missing+=1;continue
            block_policy=[];block_control=[];contexts=defaultdict(list)
            for j in planned:
                meta=j['meta'];result=lookup[j['id']]['result']
                a=mean(official_score(result,s) for s in meta['policy_sides'])
                b=mean(official_score(result,s) for s in meta['control_sides'])
                block_policy.append(a);block_control.append(b);contexts[meta['context']].append(a-b)
            differences.append(mean(block_policy)-mean(block_control))
            block_values[str(block)]=differences[-1]
            policy_scores.append(mean(block_policy));control_scores.append(mean(block_control))
            for context,values in contexts.items(): context_values[context].append(mean(values))
        interval=bootstrap(differences)
        enough=len(differences)>=min_blocks and missing==0 and bool(groups)
        if infrastructure: status='infrastructure_error'
        elif not enough: status='inconclusive'
        elif interval[0]>0: status='passed'
        elif interval[1]<=0: status='not_passed'
        else: status='inconclusive'
        summary[fmt]=dict(status=status,blocks=len(differences),planned_blocks=len(groups),missing_blocks=missing,fault_games=fault_games,
            block_differences=block_values,
            difference=mean(differences) if differences else None,interval95=interval,
            policy_score=mean(policy_scores) if policy_scores else None,
            control_score=mean(control_scores) if control_scores else None,
            contexts={k:dict(difference=mean(v),interval95=bootstrap(v),blocks=len(v)) for k,v in context_values.items()})
    return summary


def control_comparisons(jobs,results,min_blocks=30):
    """Public reports may contain both controls; never merge their block IDs."""
    summary={}
    for fmt in FORMATS:
        controls=sorted({j['meta']['control'] for j in jobs if j.get('meta',{}).get('format')==fmt})
        if controls:
            summary[fmt]={control:comparisons([j for j in jobs if j['meta']['format']==fmt and j['meta']['control']==control],
                results,min_blocks=min_blocks)[fmt] for control in controls}
    return summary


def overall_status(comparison):
    statuses=[v['status'] for v in comparison.values()]
    if not statuses: return 'inconclusive'
    if 'infrastructure_error' in statuses: return 'infrastructure_error'
    if all(s=='passed' for s in statuses): return 'passed'
    if 'not_passed' in statuses: return 'not_passed'
    return 'inconclusive'


def selection_key(comparison):
    if len(comparison)!=1: raise ValueError('model selection must be format-local')
    result=next(iter(comparison.values()))
    if result['difference'] is None or result['missing_blocks'] or result['status']=='infrastructure_error': return None
    return result['difference']


def ablations(variants):
    result={}
    for label,new,old in [('network','bc','rule'),('reinforcement_learning','ppo','bc')]:
        if new not in variants or old not in variants:
            result[label]=dict(available=False);continue
        formats={}
        for fmt in FORMATS:
            a=variants[new][fmt]['block_differences'];b=variants[old][fmt]['block_differences']
            common=sorted(set(a)&set(b))
            differences=[a[k]-b[k] for k in common]
            formats[fmt]=dict(blocks=len(common),difference=mean(differences) if differences else None,
                              interval95=bootstrap(differences))
        result[label]=dict(available=True,comparison=new+' minus '+old,formats=formats)
    return result


def choose_controls(jobs, results, fixed):
    lookup={r['id']:r for r in results}
    tables={fmt:{p:[] for p in fixed} for fmt in FORMATS if any(j['meta']['format']==fmt for j in jobs)}
    for job in jobs:
        r=lookup.get(job['id'],{})
        if r.get('status')!='complete':
            raise ValueError('control calibration is incomplete; cannot freeze a strongest control')
        if r.get('result',{}).get('faults'):continue
        m=job['meta'];result=r['result']
        for role in ('policy','control'):
            tables[m['format']][m[role]].append(mean(official_score(result,s) for s in m[role+'_sides']))
    controls={};rankings={}
    for fmt,table in tables.items():
        if any(not v for v in table.values()): raise ValueError('missing control calibration results')
        rows=sorted((dict(path=p,score=mean(v),games=len(v)) for p,v in table.items()),key=lambda r:(-r['score'],r['path']))
        controls[fmt]=rows[0]['path'];rankings[fmt]=rows
    return dict(controls=controls,calibration=rankings)
