"""Read-only acceptance of the frozen duel experiment; no games or updates.

Score and crossed-bootstrap calculations are independent of the experiment's
panels/contract modules. Only the recorded row codec and parameter hash helper
are reused from the archived execution source for MC and identity checks.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean, pvariance
import sys


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def close(actual, expected):
    assert math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12), (actual, expected)


def panel(root, partition, cells):
    directory = root / 'evaluation' / partition
    plan, saved = read(directory / 'plan.json'), read(directory / 'summary.json')
    records = read(directory / 'results.json')
    by_id = {row['id']: row for row in records}
    jobs = plan['jobs']
    assert len(by_id) == len(records) == len(jobs)
    assert set(by_id) == {job['id'] for job in jobs}
    seats, designs, maps, outcomes = defaultdict(dict), defaultdict(dict), {}, Counter()
    boundaries = Counter()
    for job in jobs:
        row = by_id[job['id']]
        meta, game = job['meta'], row['result']
        assert row['status'] == 'complete' and not game['faults']
        assert job['max_turns'] == 30 and job['task_id'] == 'official-score-30-v1'
        assert game['task_id'] == job['task_id'] and game['task_terminal']
        assert not row['truncated']
        if game['reason'] == 'turn_limit':
            assert game['truncated'] and game['turns'] == 31 and game['winner'] == 0
            boundaries['completed_round_30'] += 1
        else:
            assert game['reason'] == 'victory' and not game['truncated'] and game['turns'] <= 30
            boundaries['natural_finish'] += 1
        assert game['bots'] == job['bots'] and game['factions'] == job['factions']
        assert len(job['bots']) == 2 and game['winner'] in (0, 1, 2)
        scene, key, rotation = job['scenario_family'], meta['weights_sha256'], meta['rotation']
        side = meta['policy_sides'][0]
        assert side == 1 + rotation and job['bots'][side - 1] == meta['policy']
        assert job['bots'][2 - side] == meta['control']
        assert digest(meta['control']) == '2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933'
        points = 1 if game['winner'] == 0 else 3 if game['winner'] == side else 0
        assert rotation not in seats[key, scene]
        seats[key, scene][rotation] = points / 3
        designs[key][scene, rotation] = (job['seed'], meta['map'], tuple(job['factions']), meta['map_sha256'])
        maps[scene] = meta['map']
        outcomes[key, 'draw' if points == 1 else 'win' if points == 3 else 'loss'] += 1
    assert len(designs) == 7
    reference = next(iter(designs.values()))
    assert all(design == reference for design in designs.values())
    assert len(reference) == plan['blocks'] * 2
    assert set(maps.values()) == ({'hamlets'} if partition == 'validation' else
                                  {'caves_of_the_basilisk', 'ruined_passage'})
    assert all(count == 15 for count in Counter(maps.values()).values())
    values = defaultdict(dict)
    for (key, scene), rotations in seats.items():
        assert set(rotations) == {0, 1}
        values[key][scene] = mean(rotations.values())
    roles = {name: values[key] for name, key in plan['aliases'].items()}
    for cell in cells:
        assert plan['aliases'][cell['name'] + '/latest'] == plan['aliases'][cell['name'] + '/selected']
    seeds = sorted({cell['seed'] for cell in cells})
    groups = {name: sorted(scene for scene in maps if maps[scene] == name) for name in sorted(set(maps.values()))}
    names = {(cell['mode'], cell['seed']): cell['name'] + '/latest' for cell in cells}

    def scores(chosen_seeds, chosen_groups):
        def score(role):
            return mean(mean(roles[role][scene] for scene in scenes) for scenes in chosen_groups.values())
        a = mean(score(names['historical_action', seed]) for seed in chosen_seeds)
        b = mean(score(names['frozen_bc_kl', seed]) for seed in chosen_seeds)
        bc = score('bc')
        return dict(b_minus_a=b-a, a_minus_bc=a-bc, b_minus_bc=b-bc)

    point = scores(seeds, groups)
    samples = {key: [] for key in point}
    rng = random.Random(202611069)
    for _ in range(10000):
        chosen_seeds = rng.choices(seeds, k=3)
        chosen_groups = {name: rng.choices(scenes, k=len(scenes)) for name, scenes in groups.items()}
        for key, value in scores(chosen_seeds, chosen_groups).items():
            samples[key].append(value)
    intervals = {key: [sorted(draws)[250], sorted(draws)[9750]] for key, draws in samples.items()}
    for checkpoint_role in ('latest', 'selected'):
        observed = saved[checkpoint_role]
        for key, value in point.items():
            close(value, observed['differences'][key])
            for a, b in zip(intervals[key], observed['interval95'][key]):
                close(a, b)
        for seed in seeds:
            for key, value in scores([seed], groups).items():
                close(value, observed['per_seed'][str(seed)][key])
    return dict(games=len(jobs), unique_policies=len(designs), scenes=len(maps), maps=sorted(groups),
                boundaries=dict(boundaries),
                differences=point, interval95=intervals,
                per_seed={str(seed): scores([seed], groups) for seed in seeds},
                role_scores={name: mean(mean(rows[scene] for scene in scenes)
                    for scenes in groups.values()) for name, rows in roles.items()},
                role_outcomes={name: {outcome: outcomes[key, outcome] for outcome in ('win', 'draw', 'loss')}
                    for name, key in plan['aliases'].items()})


def budgets_and_identity(root, cells):
    import torch
    from learning.bc_anchor import weights_sha256
    endpoint = read(root / 'bc-endpoint.json')
    gate = read(root / 'runs/bc/duel/bc_gate.json')
    assert gate['passed'] and gate['corpus']['games'] == 300
    assert gate['coverage']['passed'] and gate['imitation']['effective']
    assert gate['distinct_scenarios'] >= 12 and not gate['missing_scenario_rows']
    assert not endpoint['exposure']['holdout_overlap']
    roles = read(root / 'evaluation/roles.json')
    for role in roles.values():
        assert digest(role['path']) == role['checkpoint_sha256']
        checkpoint = torch.load(role['path'], weights_only=False, map_location='cpu')
        assert weights_sha256(checkpoint['model']) == role['weights_sha256']
        assert not checkpoint['runner'].get('pending_train')
    report = {}
    previous_finish = read(root / 'bc-exit.json')['finished']
    for cell in cells:
        directory, saved = Path(cell['run']), cell['ledger']
        stage, budget = cell['stage'], read(directory / 'budget.json')
        state = read(directory / 'duel/state.json')
        rows = state['history'][budget['history_start']:]
        assert rows and all(row['method'] == 'ppo' and not row['interrupted'] for row in rows)
        assert not state.get('pending_train') and not state.get('pending_validation') and not state['error']
        targets = sum(row['planned_targets'] for row in rows)
        assert sum(row['planned_targets'] for row in rows[:-1]) < 10000 <= targets
        assert targets == saved['fresh_targets'] == saved['sampled_eligible_decisions']
        assert saved['unsettled_eligible_decisions'] == 0 and saved['budget_complete']
        assert not saved['physical_exposure']['holdout_overlap']
        for field in ('planned_steps', 'committed_steps', 'inspected_decisions', 'committed_decisions'):
            assert saved[field] == sum(row[field] for row in rows)
        rejected = sum(bool(row['kl_stopped']) for row in rows)
        assert rejected == saved['rejected_steps']
        assert saved['never_attempted_steps'] == saved['planned_steps'] - saved['committed_steps'] - rejected
        assert stage['exit_code'] == 0 and not stage['timed_out'] and stage['wall_seconds'] <= 2100
        assert previous_finish <= stage['started'] <= stage['finished'] <= budget['hard_deadline']
        previous_finish = stage['finished']
        initialization = read(directory / 'initialization.json')
        assert initialization['weights_sha256'] == endpoint['weights_sha256']
        assert initialization['optimizer_states'] == 0
        assert rows[0]['policy_sha256_before'] == endpoint['weights_sha256']
        if cell['mode'] == 'frozen_bc_kl':
            anchor = state['frozen_bc_anchor']
            assert digest(directory / 'duel/frozen_bc.pt') == endpoint['checkpoint_sha256'] == anchor['checkpoint_sha256']
            assert anchor['weights_sha256'] == endpoint['weights_sha256']
        manifests = read(directory / 'manifest.json')
        assert manifests['config']['ppo_aux_target'] == cell['mode']
        assert manifests['config']['seed'] == cell['seed']
        scenario_counts = Counter()
        for entry in rows:
            assert entry['ppo_aux_target'] == cell['mode']
            for job in read(directory / 'duel/schedules' / f"ppo-batch-{entry['batch']:06}.json"):
                side = job['meta']['seat']
                assert len(job['bots']) == 2 and digest(job['bots'][2-side]) == '2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933'
                assert job['max_turns'] == 30 and job['task_id'] == 'official-score-30-v1'
                assert job['meta']['map_partition'] == 'train'
                scenario_counts[job['scenario_family']] += 1
        assert sum(scenario_counts.values()) == saved['policy_games']
        report[cell['name']] = dict(fresh=targets, overshoot=targets-10000, batches=len(rows),
            committed_steps=saved['committed_steps'], rejected_steps=rejected,
            never_attempted_steps=saved['never_attempted_steps'], scenes=len(scenario_counts),
            games=sum(scenario_counts.values()), wall_seconds=stage['wall_seconds'])
    return report


def mc(root):
    from learning.rowpack import unpack_line
    recorded = read(root / 'mc-diagnostics.json')
    assert not recorded['external_cuts'] and not recorded['missing']
    unique, all_values = {}, []
    fields = ('global', 'opponents', 'candidates', 'spatial', 'turn', 'side', 'decision',
              'choice', 'value', 'reward_step', 'terminal_reward', 'truncated')
    for key, trajectory in recorded['trajectories'].items():
        aliases = []
        for alias in trajectory['aliases']:
            with gzip.open(alias['shard'], 'rt') as stream:
                rows = [unpack_line(line, plain=True)[0] for line in stream]
            assert all(row['source'] == 'policy' and not row.get('truncated') for row in rows)
            semantics = [{name: row.get(name) for name in fields} for row in rows]
            assert hashlib.sha256(json.dumps(semantics, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == key
            aliases.append(semantics)
        assert all(value == aliases[0] for value in aliases)
        # Complete undiscounted return from each side's chronological reward stream.
        by_side = defaultdict(list)
        for row in rows:
            by_side[row['side']].append(row)
        values = []
        for decisions in by_side.values():
            for index, row in enumerate(decisions):
                if row.get('choice', -1) >= 0:
                    values.append((row['value'], sum(item['reward_step'] for item in decisions[index:])))
        errors = [v-target for v, target in values]
        close(mean(errors), trajectory['bias'])
        close(mean(error*error for error in errors), trajectory['mse'])
        assert len(values) == trajectory['decisions']
        unique[key] = len(values)
        all_values.extend(values)
    errors = [value-target for value, target in all_values]
    targets = [target for _, target in all_values]
    observed = dict(decisions=len(all_values), bias=mean(errors), mse=mean(e*e for e in errors),
                    explained_variance=1-pvariance(errors)/pvariance(targets))
    for name, value in observed.items():
        close(value, recorded['pooled_unique_trajectories'][name])
    assert len(unique) == recorded['unique_trajectories']
    return dict(unique_trajectories=len(unique), alias_count=sum(len(t['aliases'])-1
                for t in recorded['trajectories'].values()), **observed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    root = args.run.resolve()
    sys.path.insert(0, str(root.parents[1]))
    launch, result = read(root / 'launch.json'), read(root / 'result.json')
    assert launch['source_commit'] == '43325b33696de4db8ee546e1c6bedb7230a73b37'
    assert result['status'] == 'observed' and result['budgets_complete'] and result['panels_complete']
    assert result['wall_seconds'] <= 28800 and result['hard_deadline'] == launch['hard_deadline']
    cells = read(root / 'cells.json')
    assert [cell['name'] for cell in cells] == ['a1', 'b1', 'b2', 'a2', 'a3', 'b3']
    output = dict(execution_source=launch['source_commit'], wall_seconds=result['wall_seconds'])
    output['budgets'] = budgets_and_identity(root, cells)
    for partition in ('validation', 'holdout'):
        output[partition] = panel(root, partition, cells)
        print(partition, json.dumps(output[partition]['differences']), flush=True)
    output['mc'] = mc(root)
    with args.output.open('x') as stream:
        json.dump(output, stream, indent=2)
        stream.write('\n')
    print('PASS: identities, budgets, 630 game scores, crossed intervals and complete MC returns', flush=True)


if __name__ == '__main__':
    main()
