"""Complete-return diagnostics from recorded PPO behavior, with no new games."""
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
from statistics import mean, pvariance
import time

from learning.common import read_json
from learning.evaluate import bootstrap
from learning.rowpack import unpack_line


def metrics(rows):
    predicted = [row[0] for row in rows]
    targets = [row[1] for row in rows]
    errors = [a-b for a, b in zip(predicted, targets)]
    variance = pvariance(targets)
    return dict(decisions=len(rows), bias=mean(errors), mse=mean(e*e for e in errors),
                explained_variance=1-pvariance(errors)/variance if variance else None)


def diagnose(cells, deadline=float('inf')):
    trajectories, external, missing = {}, [], []
    fields = ('global', 'opponents', 'candidates', 'spatial', 'turn', 'side', 'decision',
              'choice', 'value', 'reward_step', 'terminal_reward', 'truncated')
    for cell in cells:
        entries = cell.get('ledger', {}).get('history', [])
        if not entries:
            missing.append(cell['name'])
            continue
        chosen = [('first_ppo_bc_behavior', entries[0]), ('late_ppo_behavior', entries[-1])]
        for label, entry in chosen:
            path = Path(cell['run'])/'duel/schedules'/f"ppo-batch-{entry['batch']:06}.json"
            for job in read_json(path):
                if time.time() >= deadline:
                    return dict(status='budget_incomplete', trajectories=len(trajectories), missing=missing)
                source = Path(job['shard'])
                if not source.exists():
                    missing.append(str(source))
                    continue
                with gzip.open(source, 'rt', encoding='utf-8') as stream:
                    rows = [unpack_line(line, plain=True)[0] for line in stream]
                if not rows:
                    continue
                reference = dict(cell=cell['name'], phase=label, shard=str(source),
                    version=rows[0]['version'], behavior_weights_sha256=entry['policy_sha256_before'])
                if any(row.get('truncated') for row in rows):
                    external.append(reference)
                    continue
                if any(row.get('source') != 'policy' or row.get('reward_step') is None for row in rows):
                    raise ValueError('MC diagnostic requires complete policy behavior rewards')
                semantic = [{key: row.get(key) for key in fields} for row in rows]
                key = hashlib.sha256(json.dumps(semantic, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                if key in trajectories:
                    trajectories[key]['aliases'].append(reference)
                    continue
                returns = defaultdict(float)
                values = []
                for row in reversed(rows):
                    returns[row['side']] += row['reward_step']
                    if row.get('choice', -1) >= 0:
                        values.append((row['value'], returns[row['side']]))
                trajectories[key] = dict(aliases=[reference], scenario=job['scenario_family'],
                                          values=values, **metrics(values))
    grouped = defaultdict(list)
    for row in trajectories.values():
        grouped[row['scenario']].append(row['bias'])
    output = dict(status='observed', scope='complete MC versus the recorded on-policy behavior value; '
        'training-time diagnostic, not final-checkpoint calibration; no teacher continuation targets',
        unique_trajectories=len(trajectories), aliased_trajectories=sum(len(row['aliases'])-1 for row in trajectories.values()),
        trajectories={key: {k: v for k, v in row.items() if k != 'values'} for key, row in trajectories.items()},
        external_cuts=external, missing=missing)
    if trajectories:
        output['pooled_unique_trajectories'] = metrics([value for row in trajectories.values() for value in row['values']])
        output['scenario_mean_bias_interval95'] = bootstrap([mean(values) for values in grouped.values()])
    return output
