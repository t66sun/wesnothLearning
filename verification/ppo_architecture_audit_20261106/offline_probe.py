"""Frozen-model inference and reward probes. No optimizer or game execution."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch

from learning.data import advantages, read_shards
from learning.export import load_model
from learning.model import batch
from learning.rewards import RewardConfig, row_transition
from learning.sequences import training_windows


def stats(values):
    values = list(values)
    return dict(n=len(values), mean=statistics.mean(values) if values else None,
                std=statistics.pstdev(values) if values else None,
                min=min(values) if values else None, max=max(values) if values else None)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inference(model, rows, dtype=torch.float32):
    logps, values, entropy, predictions, losses = [], [], [], [], []
    cache = {}
    with torch.no_grad():
        for start in range(0, len(rows), 32):
            part = rows[start:start+32]
            logits, val = model(*batch(part, dtype=dtype, history_cache=cache))
            dist = torch.distributions.Categorical(logits=logits)
            chosen = torch.tensor([r['choice'] for r in part])
            logps.extend(dist.log_prob(chosen).tolist())
            values.extend(val.tolist())
            entropy.extend(dist.entropy().tolist())
            predictions.extend(logits.argmax(-1).tolist())
            losses.extend(torch.nn.functional.cross_entropy(logits, chosen, reduction='none').tolist())
    return dict(logp=logps, value=values, entropy=entropy, prediction=predictions, ce=losses)


def retention(root, fmt):
    directory = root / fmt
    paths = sorted(directory.glob('data/teacher-*.jsonl.gz'))
    admission = {}
    rows = read_shards(paths, partition='validation', limit=2048, seed=20261017,
                       format_name=fmt, stats=admission)
    identity = [(r['game_id'], r['side'], r['turn'], r.get('decision'), r['choice']) for r in rows]
    result = dict(samples=len(rows), families=len({r['scenario_family'] for r in rows}),
                  rows_sha256=hashlib.sha256(json.dumps(identity).encode()).hexdigest(), admission=admission, models={})
    for name in ('last_bc.pt', 'selected.pt', 'last_ppo.pt'):
        path = directory / name
        model, saved = load_model(path, fmt)
        model.eval()
        measured = inference(model, rows)
        by_kind = {}
        for kind in ('recruit', 'move', 'attack', 'end_turn'):
            ids = [i for i, r in enumerate(rows) if
                   ('attack' if r['candidates'][r['choice']]['kind'] == 'move_attack' else
                    r['candidates'][r['choice']]['kind']) == kind]
            by_kind[kind] = dict(samples=len(ids), accuracy=sum(measured['prediction'][i] == rows[i]['choice'] for i in ids)/max(1,len(ids)))
        result['models'][name] = dict(sha256=digest(path), version=saved['runner']['version'],
            accuracy=sum(p == r['choice'] for p,r in zip(measured['prediction'], rows))/len(rows),
            ce=stats(measured['ce']), entropy=stats(measured['entropy']), value=stats(measured['value']), kinds=by_kind)
    return result


def rollout(root, fmt):
    directory = root / fmt
    state = json.loads((directory / 'state.json').read_text())
    history = [h for h in state['history'] if h['method'] == 'ppo']
    result = []
    for h in (history[0], history[len(history)//2], history[-1]):
        path = directory / 'schedules' / f"ppo-batch-{h['batch']:06}.json"
        jobs = json.loads(path.read_text())
        paths = [Path(j['shard']) for j in jobs]
        rows = read_shards(paths, format_name=fmt)
        model_path = Path(jobs[0]['bots'][jobs[0]['meta']['seat']-1]).parent / 'model.pt'
        model, _ = load_model(model_path, fmt)
        model.eval()
        stride = max(1, len(rows)//128)
        selected = rows[::stride][:128]
        measured = inference(model, selected)
        delta = [a-r['log_probability'] for a,r in zip(measured['logp'], selected)]
        value_error = [a-r['value'] for a,r in zip(measured['value'], selected)]
        adv, ret = advantages(rows)
        windows = training_windows(rows)
        # Same frozen trajectories, remove ONLY adjudication labels. If returns
        # change on a truncated tail, it is using an outcome it claims to ignore.
        label_free = [dict(r, terminal_reward=0.) for r in rows]
        for r in label_free: r.pop('reward_step', None)
        _, no_terminal = advantages(label_free)
        terminal_delta = [a-b for a,b in zip(ret, no_terminal)]
        by_game = {}
        for row in rows: by_game.setdefault(row['game_id'], []).append(row)
        games = []
        for game_id, game in by_game.items():
            tail = game[-1]
            games.append(dict(id=game_id, rows=len(game), last_turn=tail['turn'],
                truncated=tail['truncated'], terminal_reward=tail['terminal_reward'],
                bootstrap=tail['bootstrap_value'], bootstrap_turn=tail['bootstrap_turn'],
                last_value=tail['value'], final_reward=row_transition(tail)[0]))
        result.append(dict(batch=h['batch'], schedule_sha256=digest(path), model_sha256=digest(model_path),
            rows=len(rows), source_shards=[dict(path=str(p),sha256=digest(p)) for p in paths],
            games=games, decisions_per_window=stats(map(len,windows)),
            logp_error=stats(delta), max_abs_logp_error=max(map(abs, delta)),
            max_abs_value_error=max(map(abs,value_error)), entropy=stats(measured['entropy']),
            advantages=stats(adv), returns=stats(ret), terminal_contribution=stats(terminal_delta),
            within_turn_transitions=sum(a['game_id']==b['game_id'] and a['turn']==b['turn'] for a,b in zip(rows, rows[1:]))))
    return result


def algebra():
    config = RewardConfig().to_dict()
    row = dict(schema=6, game_id='probe', side=1, turn=60, value=0., reward_raw=dict(economy=0., control=0., explored=0.),
               reward_after=dict(economy=0.,control=0.,explored=0.), reward_config=config,
               bootstrap_raw=dict(economy=0.,control=0.,explored=0.),bootstrap_turn=61,bootstrap_value=.2)
    outputs = {}
    for truncated in (False, True):
        for outcome in (-1.,1.):
            key=f'truncated={truncated},outcome={outcome}'
            sample = dict(row,truncated=truncated,terminal_reward=outcome)
            outputs[key] = dict(immediate=row_transition(sample)[0],returns=advantages([sample])[1][0])
    outputs['assertion_truncated_outcomes_indistinguishable'] = (
        outputs['truncated=True,outcome=-1.0'] == outputs['truncated=True,outcome=1.0'])
    assert outputs['assertion_truncated_outcomes_indistinguishable']
    assert outputs['truncated=False,outcome=-1.0']['returns'] == -1.
    assert outputs['truncated=False,outcome=1.0']['returns'] == 1.
    return outputs


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('run',type=Path)
    p.add_argument('output',type=Path)
    args=p.parse_args()
    torch.set_num_threads(1)
    result=dict(algebra=algebra(),formats={})
    for fmt in ('duel','team2v2'):
        started=time.time()
        result['formats'][fmt]=dict(retention=retention(args.run,fmt),rollout=rollout(args.run,fmt))
        result['formats'][fmt]['wall_seconds']=time.time()-started
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        print(fmt,'complete',round(time.time()-started,2),flush=True)
