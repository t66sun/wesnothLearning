"""Read frozen scalar trajectories; no model update, simulation or input write.

Natural-terminal Monte Carlo returns are observed targets. Truncated returns
depend on the recorded critic, so their residuals are self-consistency measures,
not calibration against an observed eventual outcome. The finite-cap target is
an explicitly counterfactual alternative objective at the *recorded* cap.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import time

from learning.data import advantages, record_split
from learning.rewards import row_transition
from learning.rowpack import row_meta


FIELDS = (
    'schema', 'game_id', 'game_family', 'scenario_family', 'split_rule', 'split',
    'side', 'turn', 'decision', 'value', 'terminal_reward', 'reward', 'reward_raw',
    'reward_after', 'reward_config', 'reward_step', 'truncated', 'bootstrap_value',
    'bootstrap_raw', 'bootstrap_turn', 'value_valid', 'version', 'source',
    'rules_sha256', 'reward_version', 'engine_id', 'choice', 'faults',
)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Metrics:
    def __init__(self):
        self.n = 0
        self.weight = self.pred = self.target = self.error = 0.
        self.target2 = self.error2 = self.abs_error = 0.
        self.pred_min = self.target_min = math.inf
        self.pred_max = self.target_max = -math.inf

    def add(self, prediction, target, weight=1.):
        assert all(math.isfinite(x) for x in (prediction, target, weight))
        error = prediction - target
        self.n += 1
        self.weight += weight
        self.pred += weight * prediction
        self.target += weight * target
        self.error += weight * error
        self.target2 += weight * target * target
        self.error2 += weight * error * error
        self.abs_error += weight * abs(error)
        self.pred_min = min(self.pred_min, prediction)
        self.pred_max = max(self.pred_max, prediction)
        self.target_min = min(self.target_min, target)
        self.target_max = max(self.target_max, target)

    def result(self):
        weight = self.weight
        assert weight > 0
        bias = self.error / weight
        variance = max(0., self.target2 / weight - (self.target / weight) ** 2)
        error_variance = max(0., self.error2 / weight - bias * bias)
        return dict(rows=self.n, weight=weight, prediction_mean=self.pred / weight,
                    target_mean=self.target / weight, bias=bias,
                    mse=self.error2 / weight, mae=self.abs_error / weight,
                    target_variance=variance,
                    explained_variance=1. - error_variance / variance if variance > 1e-12 else None,
                    prediction_min=self.pred_min, prediction_max=self.pred_max,
                    target_min=self.target_min, target_max=self.target_max)


def returns(rows, *, cap_terminal=False):
    """Independent discounted reward sum, with the recorded boundary condition."""
    tail = rows[-1]
    following_value = tail['bootstrap_value'] if tail['truncated'] and not cap_terminal else 0.
    result = [0.] * len(rows)
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        following = rows[index + 1] if index + 1 < len(rows) else None
        if following is None and cap_terminal and row['truncated']:
            row = dict(row, truncated=False, reward_after=row['bootstrap_raw'])
        reward, turns = row_transition(row, following)
        following_value = reward + row['reward_config']['gamma'] ** turns * following_value
        result[index] = following_value
    return result


def completed_return_bounds(raw, config):
    """Realized-state interval, not a bound conditioned on partial observation."""
    assert config['gamma'] == 1., 'bounds here require undiscounted potential telescoping'
    phi = config['economy'] * raw['economy'] + config['control'] * raw['control']
    return -1. - phi, 1. - phi + config['explore'] * (1. - raw['explored'])


def critic_return_bounds(config):
    """Conservative support over all hidden states compatible with a legal view."""
    assert config['gamma'] == 1.
    return -1. - config['economy'] - config['control'], 1. + config['economy'] + config['explore']


def scalar_rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            meta = row_meta(line)
            row = {key: meta[key] for key in FIELDS if key in meta}
            assert row['source'] == 'policy' and row['choice'] >= 0 and not row['faults']
            assert record_split(row) == row['split'] == 'train'
            yield row


def band(turn):
    return 'turn_01_10' if turn <= 10 else 'turn_11_30' if turn <= 30 else 'turn_31_plus'


def inspect(run):
    started = time.monotonic()
    directory = run / 'team2v2'
    state_path = directory / 'state.json'
    history = [h for h in json.loads(state_path.read_text())['history'] if h['method'] == 'ppo']
    games = []
    metrics = defaultdict(lambda: defaultdict(lambda: defaultdict(Metrics)))
    cohorts = defaultdict(Counter)
    identities = dict(manifest_sha256=digest(run / 'manifest.json'), state_sha256=digest(state_path), batches=[])
    max_step_error = 0.
    for order, entry in enumerate(history):
        phase = ('early', 'middle', 'late')[min(2, 3 * order // len(history))]
        schedule = directory / 'schedules' / f"ppo-batch-{entry['batch']:06}.json"
        jobs = json.loads(schedule.read_text())
        batch_identity = dict(batch=entry['batch'], phase=phase, schedule_sha256=digest(schedule), shards=[])
        batch_rows = 0
        for job in jobs:
            path = Path(job['shard'])
            rows = list(scalar_rows(path))
            rows.sort(key=lambda row: (row['turn'], row['decision']))
            assert rows and len({(row['game_id'], row['side']) for row in rows}) == 1
            assert all(row['version'] == job['meta']['version'] for row in rows)
            assert all(row['reward_config'] == rows[0]['reward_config'] for row in rows)
            assert rows[0]['reward_config']['gamma'] == 1.
            tail = rows[-1]
            truncated = tail['truncated']
            assert all(row['truncated'] == truncated for row in rows)
            # The production implementation independently audits stored step rewards.
            _, gae = advantages(rows)
            observed_or_bootstrapped = returns(rows)
            counterfactual = returns(rows, cap_terminal=True) if truncated else None
            kind = 'truncated' if truncated else 'natural'
            target_name = 'bootstrap_return' if truncated else 'observed_mc_return'
            targets = {target_name: observed_or_bootstrapped, 'gae_target': gae}
            if truncated:
                targets['counterfactual_cap_terminal'] = counterfactual
            groups = defaultdict(list)
            outside = 0
            lo, hi = critic_return_bounds(tail['reward_config'])
            for index, row in enumerate(rows):
                outside += not lo - 1e-9 <= row['value'] <= hi + 1e-9
                if not truncated:
                    realized_lo, realized_hi = completed_return_bounds(row['reward_raw'], row['reward_config'])
                    assert realized_lo - 1e-9 <= observed_or_bootstrapped[index] <= realized_hi + 1e-9
                following = rows[index + 1] if index + 1 < len(rows) else None
                max_step_error = max(max_step_error, abs(row_transition(row, following)[0] - row['reward_step']))
                for name in (f'all/{kind}', f'{phase}/{kind}',
                             f'{phase}/{kind}/outcome_{tail["terminal_reward"]:+g}',
                             f'{phase}/{kind}/{band(row["turn"])}'):
                    groups[name].append(index)
            for name, indices in groups.items():
                cohorts[name]['games'] += 1
                cohorts[name]['rows'] += len(indices)
                cohorts[name]['out_of_complete_return_bounds'] += sum(
                    not lo - 1e-9 <= rows[i]['value'] <= hi + 1e-9
                    for i in indices)
                for target, values in targets.items():
                    for index in indices:
                        metrics[name][target]['row_weighted'].add(rows[index]['value'], values[index])
                        metrics[name][target]['game_weighted'].add(rows[index]['value'], values[index], 1. / len(indices))
            boot_bounds = critic_return_bounds(tail['reward_config']) if truncated else None
            game = dict(id=tail['game_id'], batch=entry['batch'], phase=phase, rows=len(rows),
                        scenario_family=tail['scenario_family'], terminal_reward=tail['terminal_reward'],
                        truncated=truncated, last_action_turn=tail['turn'], max_turns=job['max_turns'],
                        value_min=min(row['value'] for row in rows), value_max=max(row['value'] for row in rows),
                        out_of_complete_return_bounds=outside,
                        bootstrap_value=tail['bootstrap_value'], bootstrap_turn=tail['bootstrap_turn'],
                        bootstrap_complete_return_bounds=boot_bounds,
                        bootstrap_out_of_bounds=(not boot_bounds[0] <= tail['bootstrap_value'] <= boot_bounds[1]) if truncated else None,
                        final_step_reward=tail['reward_step'], last_value=tail['value'],
                        first_return=observed_or_bootstrapped[0], final_return=observed_or_bootstrapped[-1],
                        first_cap_terminal_return=counterfactual[0] if truncated else None)
            games.append(game)
            batch_rows += len(rows)
            batch_identity['shards'].append(dict(path=str(path), sha256=digest(path), rows=len(rows),
                                                 rules_sha256=tail['rules_sha256'], reward_version=tail['reward_version']))
        assert batch_rows == entry['eligible_decisions'], (entry['batch'], batch_rows, entry['eligible_decisions'])
        identities['batches'].append(batch_identity)
        if order % 10 == 0 or order + 1 == len(history):
            print(f'{order + 1}/{len(history)} batches; {len(games)} games; {time.monotonic()-started:.1f}s', flush=True)
    assert sum(game['rows'] for game in games) == sum(h['eligible_decisions'] for h in history)
    return dict(scope='all complete team PPO batches; pending batch excluded',
                value_bounds_scope='global completed-return support across hidden states; not realized-state interval',
                identities=identities, batches=len(history), games=len(games),
                decisions=sum(game['rows'] for game in games),
                counts=dict(Counter('truncated' if game['truncated'] else 'natural' for game in games)),
                max_stored_step_error=max_step_error, wall_seconds=time.monotonic()-started,
                cohorts={name: dict(counts=cohorts[name], targets={target: {weighting: summary.result()
                         for weighting, summary in weighted.items()} for target, weighted in targets.items()})
                         for name, targets in sorted(metrics.items())}, trajectories=games)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('new evidence path required: ' + str(args.output))
    result = inspect(args.run)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
