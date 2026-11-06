from collections import defaultdict
import math
from pathlib import Path
from statistics import mean
import time
from learning.formats import FORMATS
from .packages import compose, digest, read, require_evaluator, write_new
from .panels import GAMES_PER_BLOCK, HORIZONS, execute, jobs_for
from .report import candidate_cells, compare, load_panels, rank_key, report_panel, valid


def estimates(jobs, results):
    lookup = {r['id']: r for r in results}
    cells = defaultdict(list)
    for job in jobs:
        row = lookup.get(job['id'])
        if valid(row):
            cells[(job['meta']['format'], job['meta']['horizon'])].append(row['result']['seconds'])
    return {key: max(1, sorted(values)[math.ceil(.9*len(values))-1]) for key, values in cells.items()}


def shortlists(directory, summary, baseline_name):
    registry = {read(p)['name']: read(p) for p in sorted((directory/'candidates').glob('*/candidate.json'))}
    if not registry:
        raise ValueError('no completed candidate packages')
    result = {}
    for fmt in FORMATS:
        ranked = []
        for name, row in registry.items():
            cells = candidate_cells(summary, name, baseline_name)
            key = rank_key(cells, fmt)
            if key is not None:
                ranked.append((key, name))
        ranked.sort(reverse=True)
        if not ranked:
            # This is an explicitly unqualified fallback, not a claimed validation winner.
            def fallback(name):
                rows = list(candidate_cells(summary, name, baseline_name).values())
                rows = [r for r in rows if r['format']==fmt]
                return (-sum(r['fault_games'] for r in rows), sum(r['blocks'] for r in rows),
                        mean(r['difference'] for r in rows if r['difference'] is not None)
                        if any(r['difference'] is not None for r in rows) else -1,
                        -registry[name]['registered'])
            ranked = [(fallback(name), name) for name in registry]
            ranked.sort(reverse=True)
        result[fmt] = [registry[name] for _, name in ranked[:3]]
    return result


def matched_selection(jobs, results, shortlist):
    """Rank every contender on the same completed validation blocks in each cell."""
    lookup = {r['id']: r for r in results}
    groups = defaultdict(list)
    for job in jobs:
        m=job['meta'];groups[(m['candidate'],m['format'],m['horizon'],m['block'])].append(job)
    keep = set()
    for fmt in FORMATS:
        names = [r['name'] for r in shortlist[fmt]]
        disqualified = {j['meta']['candidate'] for j in jobs if j['meta']['format']==fmt and
                        j['id'] in lookup and (lookup[j['id']].get('result',{}).get('faults') or
                        lookup[j['id']].get('timing',{}).get('overruns') or
                        lookup[j['id']]['status']=='infrastructure_error')}
        names = [name for name in names if name not in disqualified]
        for horizon in HORIZONS:
            completed = []
            for name in names:
                completed.append({block for (n,f,h,block), group in groups.items()
                                  if (n,f,h)==(name,fmt,horizon) and len(group)==GAMES_PER_BLOCK[fmt]
                                  and all(valid(lookup.get(j['id'])) for j in group)})
            common = set.intersection(*completed) if completed else set()
            for (name,f,h,block), group in groups.items():
                if name in names and (f,h)==(fmt,horizon) and block in common:
                    keep.update(j['id'] for j in group)
    return compare([j for j in jobs if j['id'] in keep], [r for r in results if r['id'] in keep])


def select(directory):
    manifest=read(directory/'manifest.json');timer=read(directory/'clock.json')
    require_evaluator(manifest)
    if time.time()<timer['exploration_end']:
        raise ValueError('five-hour exploration is not finished')
    post=directory/'selection';post.mkdir(parents=True,exist_ok=False)
    baseline=manifest['baseline']
    if digest(baseline['package'])!=baseline['package_sha256']:
        raise ValueError('frozen baseline changed')
    train_jobs,train_results=load_panels(directory,opponent=baseline['name'])
    train_summary=compare(train_jobs,train_results)
    shortlist=shortlists(directory,train_summary,baseline['name'])
    costs=estimates(train_jobs,train_results)
    for entries in shortlist.values():
        for row in entries:
            if row['registered']>timer['exploration_end'] or digest(row['package'])!=row['package_sha256']:
                raise ValueError('candidate identity or registration deadline changed')
    seconds=max(0,timer['selection_end']-time.time())
    block_cost=sum(len(shortlist[fmt])*GAMES_PER_BLOCK[fmt]*costs.get((fmt,h),200*h/30)
                   for fmt in FORMATS for h in HORIZONS)
    blocks=max(1,min(12,int(seconds*manifest['workers']*.85/max(1,block_cost))))
    write_new(post/'shortlist.json',dict(candidates=shortlist,blocks=blocks,
                                       costs={f'{f}/{h}':v for (f,h),v in costs.items()},frozen=time.time()))
    # Freeze both phases from exploration throughput before seeing validation outcomes.
    holdout=post/'holdout';counts={};holdout_templates={}
    remaining=max(0,timer['final_end']-max(time.time(),timer['selection_end']))
    for fmt in FORMATS:
        for h in HORIZONS:
            cost=costs.get((fmt,h),200*h/30)
            count=max(12,min(60,int(remaining*manifest['workers']*.85/6/(GAMES_PER_BLOCK[fmt]*cost))))
            counts[f'{fmt}/{h}']=count
            holdout_templates[f'{fmt}/{h}']=jobs_for(holdout,dict(name='selected_teacher',package='FROZEN_SELECTION'),
                baseline,fmt,h,count,'holdout',timer['final_end'],manifest['executable'],seed=20261109)
    write_new(post/'holdout_design.json',dict(blocks=counts,deadline=timer['final_end'],frozen=time.time(),
                                             schedules=holdout_templates))
    validation=post/'validation'
    jobs=[j for fmt in FORMATS for row in shortlist[fmt] for h in HORIZONS
          for j in jobs_for(validation,row,baseline,fmt,h,blocks,'validation',timer['selection_end'],
                            manifest['executable'],seed=20261108)]
    results=execute(validation,jobs,workers=manifest['workers'],metadata=dict(partition='validation'))
    report_panel(validation,jobs,results)
    matched=matched_selection(jobs,results,shortlist)
    choices={};basis={}
    for fmt in FORMATS:
        ranking=[]
        for row in shortlist[fmt]:
            key=rank_key(candidate_cells(matched,row['name'],baseline['name']),fmt)
            if key is not None: ranking.append((key,row['name'],row))
        ranking.sort(key=lambda r:(r[0],r[1]),reverse=True)
        choices[fmt]=ranking[0][2] if ranking else shortlist[fmt][0]
        basis[fmt]='matched_validation' if ranking else 'exploration_fallback_validation_incomplete'
    selected=compose(choices,post/'selected_teacher.zip')
    selected.update(frozen=time.time(),basis=basis,source_candidates=choices)
    write_new(post/'selected.json',selected)
    write_new(post/'matched_validation.json',matched)
    jobs=[job for rows in holdout_templates.values() for job in rows]
    for job in jobs:
        job['bots']=[selected['package'] if bot=='FROZEN_SELECTION' else bot for bot in job['bots']]
        job['meta']['policy']=selected['package']
    results=execute(holdout,jobs,workers=manifest['workers'],metadata=dict(partition='holdout',
                    selected_sha256=selected['package_sha256']))
    summary=report_panel(holdout,jobs,results,min_distinct=manifest['min_distinct'])
    passed=len(summary)==6 and all(r['passed'] for r in summary.values())
    final=dict(selected=selected,comparison=summary,passed=passed,finished=time.time(),clock=timer,
               scope='independent native teacher only; no training integration')
    write_new(directory/'final.json',final)
    lines=['# Independent teacher result','',f"Source: `{manifest['source_commit']}`.",
           f"Selected package SHA256: `{selected['package_sha256']}`.",'',
           'Six-cell acceptance: '+('passed.' if passed else 'not achieved; see individual evidence below.'),'',
           '| Format | Turns | Gain | 95% interval | Scenes | Complete | Passed |',
           '| --- | ---: | ---: | --- | ---: | --- | --- |']
    for r in summary.values():
        lines.append(f"| {r['format']} | {r['horizon']} | {r['difference']} | {r['interval95']} | "
                     f"{r['distinct_scenarios']} | {r['complete']} | {r['passed']} |")
    lines.extend(['','Natural wins, capped games, faults, timing and unfinished jobs remain in final.json and each panel.',
                  'The selected package was frozen before holdout; no holdout-driven reselection was performed.'])
    with (directory/'REPORT.md').open('x',encoding='utf-8') as stream: stream.write('\n'.join(lines)+'\n')
    print(str(directory/'final.json'),flush=True)
