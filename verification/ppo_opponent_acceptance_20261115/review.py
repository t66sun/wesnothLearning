"""Recheck the finished #322 experiment without modifying the run."""
from collections import Counter
from pathlib import Path
import json
import sys
from unittest.mock import patch

import torch

from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from verification.ppo_opponent_comparison_20261114 import driver


def review(run):
    launch_path = run / 'launch.json'
    launch = read_json(launch_path)
    start = read_json(run / 'run-start.json')
    end = read_json(run / 'run-exit.json')
    limits = launch['plan']['seconds']
    assert sha256(launch_path) == start['launch_sha256'] == (
        '835a2f973a9f80eea0360079c8109125dea086e5b6c2e9ac360352a428020a60')
    driver.verify_launch(run, launch)
    assert end['status'] == 'complete'
    assert start['started'] == end['started'] < end['finished'] <= end['deadline'] == start['deadline']
    assert end['deadline'] - end['started'] == limits['total']
    archive = read_json(run / 'archive.json')
    metadata = Path(archive['path'])
    assert sha256(metadata) == archive['sha256'] and metadata.stat().st_size == archive['bytes']
    roles = read_json(run / 'endpoints.json')
    for role in roles.values():
        path = Path(role['path'])
        assert sha256(path) == role['checkpoint_sha256']
        checkpoint = torch.load(path, map_location='cpu', weights_only=False)
        assert weights_sha256(checkpoint['model']) == role['weights_sha256']
        assert checkpoint['runner']['version'] == role['version']

    def stage(name, maximum, previous):
        record = read_json(run / f'{name}-exit.json')
        assert record['exit_code'] == 0 and record['timed_out'] is False
        assert previous <= record['started'] < record['finished'] <= record['deadline'] <= end['deadline']
        assert record['deadline'] - record['started'] <= maximum
        assert record['wall_seconds'] == record['finished'] - record['started'] <= maximum
        return record

    cells, streams = {}, {}
    previous = end['started']
    for arm, seed in launch['plan']['order']:
        name = f'{arm}-{seed}'
        exit_record = stage(name, limits['cell'], previous)
        if not cells:
            assert exit_record['started'] - end['started'] <= limits['prepare']
        previous = exit_record['finished']
        cell = run / 'cells' / name
        budget = read_json(cell / 'budget.json')
        first = read_json(cell / 'first-online.json')
        assert budget['hard_deadline'] == exit_record['deadline']
        assert budget['hard_deadline'] - budget['admission_deadline'] == limits['cell'] - limits['admission']
        assert exit_record['started'] <= first['settled_at'] <= exit_record['finished']
        assert first['gae_lambda'] == launch['config']['gae_lambda'] == .95 and first['games'] == 8
        with patch.object(driver, 'write_new') as captured:
            endpoint, stream = driver.settled(run, name, exit_record, arm)
        captured_path, reconstructed = captured.call_args.args
        assert read_json(captured_path) == reconstructed and endpoint == roles[name]
        assert sum(reconstructed['learner_decisions'].values()) == reconstructed['fresh_targets']
        assert sum(reconstructed['opponents'].values()) == len(stream) == reconstructed['settled_batches'] * 8
        streams[name] = stream
        cells[name] = {key: value for key, value in reconstructed.items() if key != 'stream'}
        cells[name]['wall_seconds'] = exit_record['wall_seconds']
    ppo_seconds = sum(cell['wall_seconds'] for cell in cells.values())
    assert ppo_seconds <= limits['ppo']
    pairs = {}
    for seed in launch['plan']['seeds']:
        astra, mixed = streams[f'astra-{seed}'], streams[f'mixed-{seed}']
        common = min(len(astra), len(mixed))
        assert common and astra[:common] == mixed[:common]
        pairs[str(seed)] = dict(astra_games=len(astra), mixed_games=len(mixed), common_games=common)
    assert pairs == read_json(run / 'training-pairs.json')

    stages = {}
    for name in ('validation', 'holdout', 'audit'):
        record = stage(name, limits[name], previous)
        stages[name] = record['wall_seconds']
        previous = record['finished']
    stages['grace_after_audit'] = end['finished'] - previous
    assert stages['grace_after_audit'] >= 0
    observed = driver.audit(run)
    assert observed == read_json(run / 'audit-result.json')
    assert ppo_seconds == observed['ppo_seconds']
    counts = {}
    for partition, maps in (('holdout', launch['plan']['holdout']), ('validation', ('hamlets',))):
        for name in maps:
            folder = run / partition / name
            plan = read_json(folder / 'plan.json')
            for role, endpoint in roles.items():
                path = folder.parent / 'policies' / role / 'model.pt'
                assert sha256(path) == endpoint['checkpoint_sha256']
            by_id = {job['id']: job['meta']['policy_sides'][0] for job in plan['jobs']}
            replies = driver.read_lines(folder / 'results.jsonl')
            outcomes = Counter(
                'draw' if (winner := row['result']['winner']) == 0 else
                'win' if winner == by_id[row['id']] else 'loss' for row in replies)
            expected = (30 if partition == 'holdout' else 15) * len(roles) * 2
            assert len(replies) == expected
            counts[name] = dict(games=len(replies), complete=True, wins_draws_losses=outcomes)
    assert sum(counts[name]['games'] for name in launch['plan']['holdout']) == 840
    return dict(started=end['started'], finished=end['finished'],
                total_seconds=end['finished']-end['started'], ppo_seconds=ppo_seconds,
                stage_seconds=stages, cells=cells, pairs=pairs, panels=counts,
                scores={key: observed[key] for key in ('overall', 'per_map', 'validation')},
                archive=archive, source=launch['source'], launch_sha256=start['launch_sha256'])


if __name__ == '__main__':
    print(json.dumps(review(Path(sys.argv[1])), indent=2))
