"""Read-only acceptance of the shared #352 capture and exact weight diagnostics."""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
from statistics import correlation, mean, pvariance
import sys
import tarfile

import torch

from learning.common import read_json, sha256
from learning.data import advantages, read_shards
from learning.export import load_model
from learning.model import batch
from learning.sequences import training_windows
from learning.tasks import TASK_ID, value_target

from audit_archive import paired, records, slot, terminal_points
from replay import absolute_summary, normalized, reward_and_clock

LAUNCH_SHA = 'b0e68cff203e2d2b315a9aa4aaf782fb2587d9dc1acc1b28224b8756a2a67699'
TURN = {'01-05':lambda n:n<=5, '06-15':lambda n:6<=n<=15, '16-30':lambda n:n>=16}
ROUNDS = ('the_freelands','weldyn_channel','fallenstar_lake')


def verify_capture(base):
    parent=base.parent
    adapter=parent/'verification/ppo_diagnosis_20261115'
    sys.path.append(str(adapter))
    from capture import preflight
    assert (parent/'capture-launcher.exit').read_text().strip()=='0'
    m,frozen=preflight(base,LAUNCH_SHA)
    runtime=read_json(base/'runtime-schedule.json')
    deadline,={j['deadline'] for j in runtime}
    assert runtime==[dict(j,deadline=deadline) for j in frozen]
    start,end=[read_json(base/f'capture-{name}.json') for name in ('start','exit')]
    assert start['launch_sha256']==LAUNCH_SHA and end['status']=='complete'
    assert 0<=deadline-1200-start['started']<=m['seconds']['preflight']
    thru=records(base/'results.throughput.jsonl')
    stats,=thru
    assert stats['workers']==8 and stats['games']==stats['completed']==96
    assert stats['started']+stats['seconds']<=deadline
    assert 0<=end['wall_seconds']<=m['seconds']['total']
    assert 0<=start['started']+end['wall_seconds']-(stats['started']+stats['seconds'])<=m['seconds']['audit']
    artifact=base/'capture-metadata.tar.gz'
    with tarfile.open(artifact,'r:gz') as archive:
        expected={'capture-launch.json','capture-schedule.json','confirmation-reserve.json',
                  'runtime-schedule.json','results.jsonl','results.throughput.jsonl','capture-ledger.json'}
        assert set(archive.getnames())==expected
        for name in expected:
            assert archive.extractfile(name).read()==(base/name).read_bytes()
    ledger=read_json(base/'capture-ledger.json')
    assert ledger['total']==len(ledger['games'])==96 and ledger['optimizer_updates']==0
    results=records(base/'results.jsonl')
    join={r['id']:r for r in results}
    counts={r['id']:r for r in ledger['games']}
    assert len(join)==len(counts)==len(results)==96 and join.keys()==counts.keys()=={j['id'] for j in runtime}
    for j in runtime:
        ledger_row,reply=counts[j['id']],join[j['id']]
        points=terminal_points(j,reply,j['meta']['policy_sides'][0])
        assert reply['meta']==j['meta'] and reply['engine']=='lite'
        assert ledger_row['score']==points and ledger_row['role']==j['meta']['role']
        assert ledger_row['records']==reply['training_shard']['written']>0
        assert ledger_row['trajectory_sha256']==sha256(Path(j['shard']))
    return m,runtime,join,counts,dict(
        archive_sha256=sha256(artifact), archive_bytes=artifact.stat().st_size,
        replies_sha256=sha256(base/'results.jsonl'), capture_ledger_sha256=sha256(base/'capture-ledger.json'),
        started=start['started'], finished=start['started']+end['wall_seconds'],
        preflight_seconds=deadline-1200-start['started'], collection_seconds=stats['seconds'],
        audit_seconds=start['started']+end['wall_seconds']-(stats['started']+stats['seconds']),
        wall_seconds=end['wall_seconds'], games=96, paired_slots=24, optimizer_updates=0)


def forward(model,rows,dtype):
    cache={}
    outputs=defaultdict(list)
    with torch.no_grad():
        for i in range(0,len(rows),16):
            part=rows[i:i+16]
            logits,value=model(*batch(part,dtype=dtype,history_cache=cache))
            d=torch.distributions.Categorical(logits=logits)
            choice=torch.tensor([r['choice'] for r in part])
            outputs['logp'].extend(d.log_prob(choice).tolist())
            outputs['value'].extend(value.tolist())
            outputs['entropy'].extend(d.entropy().tolist())
            outputs['action'].extend(logits.argmax(-1).tolist())
            p=d.probs.topk(min(2,logits.shape[-1]),dim=-1).values
            outputs['margin'].extend((p[:,0]-p[:,1] if p.shape[-1]==2 else p[:,0]).tolist())
    return outputs


def ranks(values):
    ids=sorted(range(len(values)),key=values.__getitem__)
    output=[None]*len(ids)
    start=0
    while start<len(ids):
        end=start+1
        while end<len(ids) and values[ids[end]]==values[ids[start]]:
            end+=1
        for n in ids[start:end]:
            output[n]=(start+end-1)/2
        start=end
    return output


def metrics(groups):
    rows=[r for selected in groups.values() for r in selected]
    errors=[r['value']-value_target(r) for r in rows]
    labels=[r['terminal_reward'] for r in rows]
    ref=pvariance(labels)
    return dict(games=len(groups),rows=len(rows),row_bias=mean(errors),row_mse=mean(e*e for e in errors),
                ev=(1-pvariance(errors)/ref) if ref>0 else None,
                equal_game_bias=mean(mean(r['value']-value_target(r) for r in selected)
                                    for selected in groups.values()))


def calibration(groups,meta):
    samples={k:metrics(v) for k,v in (('overall',groups), *((b,{g:r for g,r in groups.items() if meta[g]['map']==b}) for b in ROUNDS))}
    z={g:r[0]['terminal_reward'] for g,r in groups.items()}
    blocks=defaultdict(list)
    for g,rows in groups.items():
        e=[r['value']-value_target(r) for r in rows]
        loo=mean(p for h,p in z.items() if h!=g)
        blocks[meta[g]['map']].append((mean(e),mean(x*x for x in e)-(loo-z[g])**2))
    rng=random.Random(2026111755)
    draws=[list(v for b in blocks.values() for v in rng.choices(b,k=len(b))) for _ in range(10000)]
    for n,col in (('bias',0),('mse_minus_loo_constant',1)):
        ranks=sorted(mean(v[col] for v in x) for x in draws)
        samples['overall'][n+'_estimate']=mean(v[col] for b in blocks.values() for v in b)
        samples['overall'][n+'_ci95']=[ranks[250],ranks[9750]]
    bands={}
    for band,keep in TURN.items():
        strata={g:[r for r in rows if keep(r['turn'])] for g,rows in groups.items()}
        nonempty={g:rows for g,rows in strata.items() if rows}
        if nonempty: bands[band]=metrics(nonempty)
    outcome={}
    for label,result in (('win',1.),('loss',-1.),('draw',2/3-1)):
        one={g:rows for g,rows in groups.items() if rows[0]['terminal_reward']==result}
        if one: outcome[label]=metrics(one)
    return dict(maps=samples,turn_bands=bands,outcome=outcome)


def param_gradient(model,terms):
    names,parameters=zip(*model.named_parameters())
    gradients=[torch.autograd.grad(loss,parameters,retain_graph=i+1<len(terms),allow_unused=True)
               for i,loss in enumerate(terms)]
    groups=defaultdict(list)
    for i,name in enumerate(names):
        groups[name.partition('.')[0]].append(i)
    norm,cos={},{}
    score_dot=[0.,0.]
    for name,ids in groups.items():
        flat=[torch.cat([(g[i] if g[i] is not None else torch.zeros_like(parameters[i])).flatten()
                         for i in ids]) for g in gradients]
        norms=[float(x.norm()) for x in flat]
        score_dot=[total+float(torch.dot(flat[1],flat[j])) for total,j in zip(score_dot,(4,5))]
        norm[name]=norms
        cos[name]=[float(torch.dot(flat[0],v))/(norms[0]*k) if norms[0]*k else None for v,k in zip(flat,norms)]
    whole=[math.sqrt(sum(g[i]**2 for g in norm.values())) for i in range(len(terms))]
    dot=[sum(norm[k][0]*norm[k][i]*(v[i] or 0.) for k,v in cos.items()) for i in range(len(terms))]
    return dict(order=['gae_actor','mc_actor','value','entropy','equal_window','equal_turn'],whole_norm=whole,
                weighting_cosine_to_mc={n:x/(whole[1]*whole[i]) if whole[1]*whole[i] else None
                                        for n,x,i in zip(('equal_window','equal_turn'),score_dot,(4,5))},
                whole_cosine_to_gae=[x/(whole[0]*q) if whole[0]*q else None for x,q in zip(dot,whole)],
                per_module_norm=norm,per_module_cosine_to_gae=cos)


def credit(model,groups,metas,probe):
    rows=[r for g in groups.values() for r in g]
    adv,ret=advantages(rows)
    mc,_=advantages(rows,lam=1.)
    gae,reference=normalized(adv),normalized(mc)
    chronology=reward_and_clock(rows,adv,ret)
    sign=(gae>=0)==(reference>=0)
    by_game={k:[] for k in groups}
    for r,flag in zip(rows,sign.tolist()):
        by_game[r['game_id']].append(flag)
    folds=[]
    index={id(r):i for i,r in enumerate(rows)}
    # Roster blocks 0/16 and 8/24 provide disjoint two-block folds within a layout.
    win=training_windows(rows)
    turn=Counter((r['game_id'],r['turn']) for r in rows)
    w_win={id(r):1/(len(win)*len(w)) for w in win for r in w}
    assert len(w_win)==len(rows)
    for fold in (0,1):
        selected=[r for g,rs in probe.items() if (metas[g]['block']//8)%2==fold for r in rs[:4]]
        xs=[index[id(r)] for r in selected]
        logits,values=model(*batch(selected))
        d=torch.distributions.Categorical(logits=logits)
        logp=d.log_prob(torch.tensor([r['choice'] for r in selected]))
        losses=[-(logp*gae[xs]).mean(),-(logp*reference[xs]).mean(),
                .5*(values-torch.tensor(ret)[xs]).square().mean(),-.01*d.entropy().mean()]
        for weight in (
            [w_win[id(r)] for r in selected],
            [1/(len(turn)*turn[r['game_id'],r['turn']]) for r in selected],
        ):
            q=torch.tensor(weight)
            losses.append(-(logp*gae[xs]*q/q.sum()).sum())
        folds.append(dict(fold=fold,rows=len(selected),games=len({r['game_id'] for r in selected}),
                          **param_gradient(model,losses)))
    return dict(rows=len(rows),windows=len(training_windows(rows)),
                sign_agreement_equal_game=mean(mean(x) for x in by_game.values()),
                sign_by_game={k:mean(v) for k,v in by_game.items()},spearman=correlation(ranks(adv),ranks(mc)),
                recurrence=chronology, folds=folds)


def evaluate_role(name,manifest,jobs,results,ledgers,anchor):
    export=manifest['policies'][name]
    model,_=load_model(Path(export['folder'])/'model.pt','duel')
    model.eval()
    games,sampled,meta,score,windows={},{},{},Counter(),{}
    for job in jobs:
        j=job['id']
        m=job['meta']
        seat=m['policy_sides'][0]
        rows=read_shards([Path(job['shard'])],format_name='duel',expected_task=TASK_ID)
        recorded=results[j]['result']
        assert len(rows)==ledgers[j]['records'] and len(rows)>=8
        expected=2*ledgers[j]['score']/3-1
        assert all(r['game_id']==j and r['side']==seat and r['terminal_reward']==expected
                   and r['value_valid'] and not r['truncated'] and 0<=r['choice']<len(r['candidates']) for r in rows)
        points=ledgers[j]['score']
        score[points]+=1
        score['round_cap']+=int(recorded['reason']=='turn_limit')
        games[j],meta[j]=rows,m
        k=len(rows)-1
        sampled[j]=[rows[i*k//7] for i in range(8)]
    control=forward(anchor, [r for group in sampled.values() for r in group], torch.float64)
    cohort_probe=[r for group in sampled.values() for r in group]
    fp32=forward(model,cohort_probe,torch.float32)
    for board in ROUNDS:
        board_games={k:v for k,v in games.items() if meta[k]['map']==board}
        windows[board]=credit(model,board_games,meta,{k:sampled[k] for k in board_games})
    delivered=forward(model.double(),cohort_probe,torch.float64)
    residuals={}
    for name2,stats in (('rollout_fp64',delivered),('trainer_fp32',fp32)):
        logp=[p-r['log_probability'] for p,r in zip(stats['logp'],cohort_probe)]
        error=[v-r['value'] for v,r in zip(stats['value'],cohort_probe)]
        residuals[name2]=dict(log_probability=absolute_summary(logp),value=absolute_summary(error),
                              ratio=absolute_summary(math.exp(x)-1 for x in logp))
    assert max(residuals['rollout_fp64'][x]['max'] for x in ('log_probability','value'))<=1e-5
    assert sorted(m['map'] for m in meta.values())==sorted(ROUNDS*8)
    mode={}
    cursor=0
    for game,rs in sampled.items():
        end=cursor+len(rs)
        pred,base=delivered['action'][cursor:end],control['action'][cursor:end]
        mode[game]=dict(board=meta[game]['map'],rows=end-cursor,mean_entropy=mean(delivered['entropy'][cursor:end]),
                        v38_mean_entropy=mean(control['entropy'][cursor:end]),
                        mean_top2_margin=mean(delivered['margin'][cursor:end]),
                        sampled_equals_greedy=sum(r['choice']==a for r,a in zip(rs,pred)),
                        differs_from_v38=sum(a!=b for a,b in zip(pred,base)))
        cursor=end
    return dict(probed=len(cohort_probe),eligible_rows=sum(map(len,games.values())),outcomes=score,
                calibration=calibration(games,meta),credit_by_layout=windows,replay=residuals,mode_by_game=mode)


def main(base):
    manifest,jobs,results,ledgers,archive=verify_capture(base)
    anchor,_=load_model(Path(manifest['policies']['bc']['folder'])/'model.pt','duel')
    anchor.double().eval()
    out={}
    for role in manifest['roles']:
        out[role]=evaluate_role(role,manifest,[j for j in jobs if j['meta']['role']==role],results,ledgers,anchor)
    assert sum(v['probed'] for v in out.values())==768
    assert sum(v['eligible_rows'] for v in out.values())==sum(x['records'] for x in ledgers.values())
    point=defaultdict(dict)
    for job in jobs:
        point[job['meta']['role']][slot(job)]=ledgers[job['id']]['score']
    sample=paired([v for k,v in point.items() if k!='bc'],[point['bc']]*3)
    print(json.dumps(dict(launch_sha256=LAUNCH_SHA,archive=archive,roles=out,replay_rows=768,sampled_score=sample,
                          raw_rows=sum(v['eligible_rows'] for v in out.values())),indent=2,allow_nan=False))


if __name__=='__main__':
    torch.set_num_threads(1)
    main(Path(sys.argv[1]).resolve())
