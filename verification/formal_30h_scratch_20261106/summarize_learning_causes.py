"""Read existing run state, jobs, validation metrics and checkpoint metadata.
Writes no run artifact and launches no collection, training or games.
Usage: /home/tongshu/venv/bin/python -B summarize_learning_causes.py
"""
import collections
import hashlib
import json
from pathlib import Path
import statistics
import torch

ROOT = Path('/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041')
RUN = ROOT / 'source/runs/formal_30h_scratch'

def dedup_jobs(directory):
    return list({row['id']: row for row in map(json.loads, (directory/'jobs.jsonl').read_text().splitlines())}.values())

def kind(path):
    return 'astra' if Path(path).name == 'gpt6astra.zip' else 'baseline' if path == 'baseline' else 'policy'

def counts(items):
    return dict(collections.Counter(items))

out = {'source_commit': (ROOT/'SOURCE_COMMIT').read_text().strip(), 'run': str(RUN), 'formats': {}}
for fmt in ('ffa4', 'team2v2'):
    directory = RUN / fmt
    state = json.loads((directory/'state.json').read_text())
    jobs = dedup_jobs(directory)
    gate = json.loads((directory/'bc_gate.json').read_text())
    item = {key: state.get(key) for key in ('version','batch','effective','bc_refreshes','bc_plateau','bc_quality_best','counters')}
    item['bc_gate'] = gate
    item['phases'] = {}
    for phase in ('teacher','dagger_refresh','ppo','validation','reward_reference'):
        group = [row for row in jobs if row.get('meta',{}).get('phase') == phase]
        phase_stats = dict(games=len(group), statuses=counts(row['status'] for row in group),
            result_reasons=counts(row['result'].get('reason') for row in group),
            mean_turns=statistics.mean(row['result']['turns'] for row in group) if group else None,
            maps=counts(row['meta'].get('map') for row in group),
            bot_classes=counts(kind(bot) for row in group for bot in row['result']['bots']),
            contexts=counts(row['meta'].get('context') for row in group))
        if phase in ('ppo','dagger_refresh'):
            phase_stats['composition_roles'] = counts(c['role'] for row in group for c in row['meta'].get('composition',[]))
            phase_stats['enemy_classes'] = counts(kind(c['path']) for row in group for c in row['meta'].get('composition',[]) if c['role'] != 'teammate')
            phase_stats['teammate_classes'] = counts(kind(c['path']) for row in group for c in row['meta'].get('composition',[]) if c['role'] == 'teammate')
        if phase == 'teacher':
            phase_stats['coverage'] = [dict(label=label,games=len(subset),
                matched=sum(row['coverage']['matched'] for row in subset),
                total=sum(row['coverage']['total'] for row in subset))
                for label,subset in [('first600',group[:600]),('after600',group[600:]),('all',group)]]
        item['phases'][phase] = phase_stats
    item['history'] = {}
    for method in ('bc','ppo'):
        group = [row for row in state['history'] if row['method'] == method]
        if not group:
            item['history'][method] = {'batches': 0}
            continue
        summary = dict(batches=len(group),first_batch=group[0]['batch'],last_batch=group[-1]['batch'],
            first_completed_hours=group[0]['elapsed_hours'],last_completed_hours=group[-1]['elapsed_hours'],
            sums={key:sum(row.get(key,0) for row in group) for key in ('updates','decisions_seen','planned_steps','committed_steps','stopped_by_kl_steps','kl_stopped')})
        if method == 'ppo':
            summary['rehearsal_source_sets'] = counts(','.join(sorted(set(x['source'] for x in row['rehearsal_sources']))) for row in group)
            excluded = [row['rehearsal_rows_excluded'] for row in group]
            summary['rehearsal_rows_excluded'] = dict(min=min(excluded),mean=statistics.mean(excluded),max=max(excluded))
            summary['same_weight_digest_batches'] = sum(row['policy_sha256_before']==row['policy_sha256_after'] for row in group)
            summary['mean_approx_kl'] = statistics.mean(row['approx_kl'] for row in group)
            summary['max_approx_kl'] = max(row['approx_kl'] for row in group)
        item['history'][method] = summary
    controller = state['reward_controller']
    item['reward_controller'] = {key:controller.get(key) for key in ('config','cursor','last_check','games','last_error','metrics_error','windows')}
    rms = []
    all_metric_files = sorted((directory/'validation').glob('control-v*.json'))
    for path in all_metric_files:
        value = json.loads(path.read_text())
        shaping,terminal = value.get('shaping_rms'),value.get('terminal_rms')
        if shaping is not None and terminal:
            rms.append(dict(file=path.name,shaping_rms=shaping,terminal_rms=terminal,ratio=shaping/terminal))
    item['validation_reward_rms'] = dict(files=len(all_metric_files),available=len(rms),rows=rms)
    panels = []
    for path in sorted((directory/'validation').glob('v*.json')):
        value=json.loads(path.read_text())
        comparison=value['comparison'][fmt]
        panels.append(dict(file=path.name, tier=value['tier'], **{key:comparison.get(key) for key in
            ('status','blocks','distinct_scenarios','min_distinct','difference','interval95','policy_score','control_score','contexts')}))
    item['validation_panels'] = panels
    item['checkpoints'] = {}
    for name in ('last_bc.pt','last_ppo.pt','selected.pt','latest.pt'):
        path = directory/name
        if path.exists():
            cp = torch.load(path,map_location='cpu',weights_only=False)
            runner = cp.get('runner',{})
            item['checkpoints'][name] = dict(version=runner.get('version'),pending_train=bool(runner.get('pending_train')),
                learning_rates=[group['lr'] for group in cp.get('optimizer',{}).get('param_groups',[])])
            del cp
    out['formats'][fmt] = item
out['limits'] = [
    'No tactical coordination label or attack-opportunity counter was computed; poorer self-team outcomes do not identify a specific tactical cause.',
    'The BC gate is the last BC prerequisite report, not a new imitation measurement after PPO.',
    'Reward RMS comes from recorded validation diagnostics, not a full decomposition of all training-rollout gradients.',
    'PPO collected games include the final pending batch; committed history counts are reported separately.',
    'All run engines were Lite; no official baseline games or native strength acceptance are claimed.'
]
print(json.dumps(out,indent=2))
