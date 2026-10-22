"""Organizer-only round robin, including 4/8-player FFA stages."""
import argparse
import csv
from datetime import datetime
import hashlib
from itertools import combinations
from pathlib import Path
import os
import json
import sys
import params as P
from arena import add_options, positive_int, run_jobs
from native import ROOT, find_wesnoth
from addons import open_addon, validate



def discover(directory):
    result={}
    for p in sorted(Path(directory).iterdir(),key=lambda p:p.name.casefold()):
        if p.name.startswith(("_",".")) or p.name.lower().startswith("readme"): continue
        if not p.is_dir() and p.suffix.lower()!=".zip": continue
        with open_addon(p) as addon: name=validate(addon)
        if name.casefold() in {n.casefold() for n in result}: raise ValueError("duplicate team ID: "+name)
        result[name]=str(p.resolve())
    if len(result)<2: raise ValueError("at least two native add-ons are required")
    return result


def ffa_groups(names,k,limit=70,seed=1):
    """Enumerate small fields; deterministic appearance-balanced selection for large fields."""
    import math
    total=math.comb(len(names),k)
    if total<=limit:return list(combinations(names,k))
    # Candidate pool is bounded even for hundreds of entrants; no giant C(N,k) allocation.
    candidates=set()
    for shift in range(len(names)):
        candidates.add(tuple(sorted(names[(shift+i)%len(names)] for i in range(k))))
    import random
    rng=random.Random(seed)
    for _ in range(limit*20):candidates.add(tuple(sorted(rng.sample(names,k))))
    counts={n:0 for n in names};selected=[]
    while candidates and len(selected)<limit:
        def key(group):
            hypothetical=[counts[n]+(n in group) for n in names]
            tie=hashlib.sha256((str(seed)+'|'.join(group)).encode()).digest()
            return max(hypothetical)-min(hypothetical),sum(v*v for v in hypothetical),tie
        group=min(candidates,key=key);candidates.remove(group);selected.append(group)
        for n in group:counts[n]+=1
    if min(counts.values())==0:raise ValueError('too many entrants for 70 balanced FFA groups; split the field')
    return selected


def csv_file(path,rows,fields):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description='Wesnoth tournament: RR + FFA4 + FFA8')
    p.add_argument('--bots',default=str(ROOT/'competing_bots'))
    p.add_argument('--games',type=positive_int,default=6)
    p.add_argument('--ffa-games4',type=positive_int,default=4)
    p.add_argument('--ffa-games8',type=positive_int,default=8)
    p.add_argument('--no-ffa',action='store_true');p.add_argument('--output')
    add_options(p);args=p.parse_args(argv)
    if args.no_fog:p.error('--no-fog is not permitted in a formal tournament')
    if args.games%2 or (not args.no_ffa and (args.ffa_games4%4 or args.ffa_games8%8)):
        p.error('games must be a multiple of 2; FFA games must be multiples of 4/8 for seat fairness')
    try:bots=discover(args.bots)
    except (ValueError,OSError) as exc:p.error(str(exc))
    names=sorted(bots);reverse={path:n for n,path in bots.items()}
    out=Path(args.output or ROOT/'tournament_results'/datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    out.mkdir(parents=True,exist_ok=False);(out/'replays').mkdir()
    exe=find_wesnoth(args.wesnoth)
    factions=list(P.FACTIONS);jobs=[];metadata={};counter=0
    stages=[('1v1',2,list(combinations(names,2)),args.games)]
    if not args.no_ffa:
        for k,g in [(4,args.ffa_games4),(8,args.ffa_games8)]:
            if len(names)>=k:stages.append((f'ffa{k}',k,ffa_groups(names,k,seed=args.seed),g))
    for stage,k,groups,games in stages:
        for group_id,group in enumerate(groups):
            for i in range(games):
                counter+=1;rotation=i%k;block=i//k
                seats=list(group[rotation:]+group[:rotation]);metadata[counter]={'stage':stage,'seats':seats}
                jobs.append({'id':counter,'kwargs':dict(bots=[bots[n] for n in seats],seed=(args.seed+group_id*100+block)&0xffffffff,
                    factions=[factions[(group_id+block*k+s)%len(factions)] for s in range(k)],
                    timeout=args.timeout,first_timeout=args.first_timeout,max_turns=args.max_turns,wesnoth=exe,
                    replay_path=str(out/'replays'/f'{counter:06}.json'))})
    tables={stage:{n:{'name':n,'points':0.,'games':0,'wins':0,'dq':0} for n in names} for stage,_,_,_ in stages}
    head={a:{b:0 for b in names} for a in names};records=[]
    with (out/'tournament.log').open('w',encoding='utf-8') as log:
        for ident,result in run_jobs(jobs,args.j):
            meta=metadata[ident];stage=meta['stage'];seats=meta['seats'];k=len(seats)
            record=dict(id=ident,stage=stage,seats=seats,result=result);records.append(record)
            log.write(json.dumps(record,ensure_ascii=False)+'\n');log.flush()
            for side,name in enumerate(seats,1):
                row=tables[stage][name];row['games']+=1
                row['dq']+=int(side in result['faults']);row['wins']+=int(result['winner']==side)
                if k==2:
                    points=1 if result['winner']==0 else 3 if result['winner']==side else 0
                    head[name][seats[2-side]]+=points
                else:points=result['rank_points'][side]
                row['points']+=points
    standings={}
    for stage,k,_,_ in stages:
        rows=list(tables[stage].values())
        for row in rows:
            tied=[r['name'] for r in rows if r['points']==row['points']]
            row['head_to_head']=sum(head[row['name']][other] for other in tied) if k==2 else 0
            row['normalized']=row['points']/((3 if k==2 else k-1)*row['games']) if row['games'] else 0
        rows.sort(key=lambda r:(-r['points'],-r['head_to_head'],-r['wins'],r['dq'],r['name']))
        for rank,row in enumerate(rows,1):row['rank']=rank
        standings[stage]=rows
        csv_file(out/('standings.csv' if k==2 else f'standings_{stage}.csv'),rows,
            ['rank','name','points','games','wins','dq','head_to_head','normalized'])
    overall=[];rr={r['name']:r for r in standings['1v1']}
    for name in names:
        row={'name':name,'score':sum(t[name]['normalized'] for t in tables.values()),'rr_points':rr[name]['points'],'rr_rank':rr[name]['rank']}
        overall.append(row)
    overall.sort(key=lambda r:(-r['score'],-r['rr_points'],r['rr_rank'],r['name']))
    for rank,row in enumerate(overall,1):row['rank']=rank
    csv_file(out/'standings_overall.csv',overall,['rank','name','score','rr_points','rr_rank'])
    csv_file(out/'crosstable.csv',[dict(name=n,**{'vs:'+other:head[n][other] for other in names}) for n in names],
             ['name',*['vs:'+other for other in names]])
    (out/'results.json').write_text(json.dumps({'rules_version':P.RULES_VERSION,
        'settings':vars(args),'games':sorted(records,key=lambda r:r['id']),'standings':standings,'overall':overall},ensure_ascii=False,indent=2),encoding='utf-8')
    summary='# 比赛结果\n\n冠军：'+overall[0]['name']+'\n\n|排名|队名|综合分|\n|---|---|---|\n'
    summary+=''.join(f'|{r["rank"]}|{r["name"]}|{r["score"]:.6f}|\n' for r in overall)
    summary+='\n综合分 = 1v1积分/(3×局数) + 各FFA名次分/((人数−1)×局数)。\n'
    (out/'summary.md').write_text(summary,encoding='utf-8')
    print(summary);print('Results:',out)
    return 0


if __name__=='__main__':raise SystemExit(main())
