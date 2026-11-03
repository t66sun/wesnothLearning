"""After export: python -B audit.py RUN_DIR OBSERVED_DIR EXPORT_DIR > handoffs.json"""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256 as digest
import json
from pathlib import Path
from zipfile import ZipFile

import torch

from learning.common import read_json, sha256
from learning.experiment import bc_effective
from learning.formats import FORMATS, PLAYERS
from learning.selection import validate_frozen_selection


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def lines(path):
    with path.open(encoding='utf-8') as source:
        return [json.loads(line) for line in source if line.strip()]


def weights_equal(left, right):
    return left.keys() == right.keys() and all(torch.equal(left[k], right[k]) for k in left)


def progression(previous, current):
    """Bind new counters to the suffix of the history that the later checkpoint saved."""
    commands = current['phase_history']
    require(commands[:-1] == previous.get('phase_history', []) and commands[-1]['phase']=='ppo'
            and commands[-1]['pretraining_complete'] and not commands[-1]['force'],
            'PPO phase request did not extend the prior committed state normally')
    before, after = previous['history'], current['history']
    require(after[:len(before)] == before, 'committed history changed on resume')
    suffix = after[len(before):]
    batches = list(range(previous['batch'], current['batch']))
    indices = [h['batch'] for h in suffix]
    require(indices == sorted(set(indices)) and set(indices) <= set(batches), 'PPO history repeated a batch')
    require(suffix and all(h['method']=='ppo' for h in suffix), 'missing new PPO history')
    updates = sum(h['updates'] for h in suffix)
    require(updates > 0, 'no newly committed PPO updates')
    for counter, metric in (('optimizer_steps','updates'), ('committed_steps','committed_steps')):
        delta = current['counters'][counter] - previous['counters'].get(counter, 0)
        require(delta == sum(h[metric] for h in suffix), 'PPO counter delta differs from history: '+counter)
    require(current['version'] - previous['version'] == sum(h['updates']>0 for h in suffix),
            'model version delta differs from new applied batches')
    return batches, updates


def result_for(job, results, events):
    ident = job['id']
    require(len(results[ident])==1, 'expected exactly one raw result: '+ident)
    row = results[ident][0]
    if row['status']=='complete':
        require(events['start',ident] == events['finish',ident] == 1, 'game execution count differs: '+ident)
    return row


def rollouts(directory, previous, current, results, events):
    batches, updates = progression(previous, current)
    statuses, ids, eligible = Counter(), set(), set()
    truncated = faulted = 0
    for batch in batches:
        jobs = read_json(directory/'schedules'/f'ppo-batch-{batch:06}.json')
        require(len(jobs)==4, f'expected four scheduled PPO rollouts in batch {batch}')
        for job in jobs:
            ident = job['id']
            require(ident not in ids and job['meta']['phase']=='ppo', 'invalid or repeated PPO job: '+ident)
            ids.add(ident)
            row = result_for(job, results, events)
            statuses[row['status']] += 1
            actual = row.get('result', {})
            truncated += bool(actual.get('truncated'))
            faulted += bool(actual.get('faults'))
            if row['status']=='complete' and not actual['faults'] and row['training_eligible']:
                require(Path(job['shard']).is_file(), 'missing committed rollout shard: '+ident)
                eligible.add(job['shard'])
    old, new = set(previous['policy_shards']), set(current['policy_shards'])
    require(eligible and eligible.isdisjoint(old) and new == old | eligible, 'new PPO shard pool differs from jobs')
    return dict(batches=batches, optimizer_updates=updates, jobs=sorted(ids), status=dict(statuses),
                eligible_shards=len(eligible), truncated=truncated, faulted=faulted)


def final_panel(directory, selected, results, events, summary):
    fmt = directory.name
    seats = PLAYERS[fmt]
    contexts = ['astra_partner','self_team'] if fmt=='team2v2' else ['solo']
    expected = Counter((block, rotation, ctx) for block in range(30) for rotation in range(seats) for ctx in contexts)
    jobs = read_json(directory/'schedules/final.json')
    actual, scenarios, policies, ids = Counter(), set(), set(), set()
    truncated = 0
    for job in jobs:
        meta = job['meta']
        require(job['id'] not in ids and meta['label']=='final-gpt6astra', 'invalid final game: '+job['id'])
        ids.add(job['id'])
        actual[meta['block'],meta['rotation'],meta['context']] += 1
        require(meta['map_partition']=='final' and job['scenario_family'], 'missing final scenario: '+job['id'])
        scenarios.add(job['scenario_family'])
        policies.add(Path(meta['policy']).parent/'model.pt')
        row = result_for(job, results, events)
        require(row['status']=='complete' and not row['result']['faults'] and row['result']['bots']==job['bots'],
                'final result incomplete, faulted or played different bots: '+job['id'])
        require(all(row['meta'][k]==meta[k] for k in ('block','rotation','context','label','policy')),
                'final result differs from its frozen schedule: '+job['id'])
        truncated += bool(row['result']['truncated'])
    raw_final = {ident for ident, rows in results.items() if any(r.get('meta',{}).get('map_partition')=='final' for r in rows)}
    require(actual==expected and raw_final==ids and len(policies)==1, 'final seats, contexts, jobs or policy differ')
    control = summary['controls']['gpt6astra']
    require(len(scenarios)==control['distinct_scenarios'] and len(scenarios)>=12, 'final scenario count differs')
    require(control['blocks']==30 and control['missing_blocks']==control['fault_games']==0, 'final control report differs')
    policy = policies.pop()
    require(weights_equal(selected['model'], torch.load(policy, map_location='cpu', weights_only=False)['model']),
            'final Lite worker policy tensors differ from the selected checkpoint')
    return dict(games=len(ids), blocks=control['blocks'], contexts=contexts, distinct_scenarios=len(scenarios),
                faulted=0, truncated=truncated, policy_sha256=sha256(policy))


def audit(run, observed, export):
    require(read_json(observed/'result.json')['status']=='OBSERVED', 'full-loop runner did not finish export')
    selections = {}
    for fmt in FORMATS:
        selected = run/fmt/'selected.pt'
        selections[fmt] = validate_frozen_selection(selected.parent/'selection.json', sha256(selected))
        require(selections[fmt].get('frozen_before_holdout'), f'{fmt} selection was not frozen before holdout')
    stages = {s:read_json(observed/(s+'.json')) for s in ('bc','ppo_first','ppo_resume','evaluate','export')}
    manifest = sha256(run/'manifest.json')
    output = dict(source=read_json(observed/'plan.json')['source'], manifest_sha256=manifest, formats={},
                  stage_seconds={k:v['seconds'] for k,v in stages.items()})
    starts = lines(run/'scheduler.jsonl')
    package = read_json(export/'export.json')
    archive = export/(package['id']+'.zip')
    require(sha256(archive)==package['sha256'], 'packaged archive digest differs')
    output['export_sha256'] = package['sha256']
    for fmt in FORMATS:
        directory = run/fmt
        results = defaultdict(list)
        for row in lines(directory/'jobs.jsonl'):
            results[row['id']].append(row)
        events = Counter((r['event'],r['id']) for r in starts if r.get('format')==fmt and 'id' in r)
        boundaries, previous = {}, None
        for name in ('bc','ppo_first','ppo_resume'):
            path = observed/'checkpoints'/name/(fmt+'.pt')
            checkpoint = torch.load(path, map_location='cpu', weights_only=False)
            state = checkpoint['runner']
            require(checkpoint['manifest_sha256']==manifest and json.loads(json.dumps(state))==stages[name]['states'][fmt],
                    f'{fmt} {name} checkpoint and observed state differ')
            record = dict(sha256=sha256(path), version=state['version'], batch=state['batch'])
            if name=='bc':
                gate = read_json(directory/'bc_gate.json')
                require(bc_effective(gate) and state['effective'] and not state.get('forced_ppo'),
                        f'{fmt} child has no ordinary BC gate')
                record.update(optimizer_updates=sum(h['updates'] for h in state['history'] if h['method']=='bc'),
                              teacher_games=gate['corpus']['games'], gate_sha256=sha256(directory/'bc_gate.json'))
                require(state['counters']['optimizer_steps']==record['optimizer_updates']>0,
                        'child BC optimizer counter differs from its new history')
            else:
                record.update(rollouts(directory, previous['runner'], state, results, events))
                require(not weights_equal(previous['model'], checkpoint['model']), f'{fmt} {name} weights did not change')
            boundaries[name] = record
            previous = checkpoint
        require(set(boundaries['ppo_first']['jobs']).isdisjoint(boundaries['ppo_resume']['jobs']), 'resumed PPO replayed a job')
        selected = torch.load(directory/'selected.pt', map_location='cpu', weights_only=False)
        identity = dict(checkpoint_sha256=selections[fmt]['selected_sha256'], version=selected['runner']['version'])
        summary = read_json(directory/'report/summary.json')
        require(summary['checkpoint_sha256']==identity['checkpoint_sha256'] and summary['version']==identity['version']
                and selected['manifest_sha256']==manifest, 'reported selection differs: '+fmt)
        model = package['models'][fmt]
        require(model['version']==package['version'][fmt]==identity and 0<=model['python_lua_max_error']<=1e-5,
                'exported checkpoint or parity result differs: '+fmt)
        with ZipFile(archive) as z:
            packed_weights = z.read(package['id']+'/lua/weights_'+fmt+'.lua')
        require(digest(packed_weights).hexdigest()==model['sha256'], 'packaged weight digest differs: '+fmt)
        output['formats'][fmt] = dict(boundaries=boundaries, selected=identity,
            final=final_panel(directory, selected, results, events, summary), python_lua_max_error=model['python_lua_max_error'])
    return output


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('run','observed','export'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.run, args.observed, args.export), indent=2))
