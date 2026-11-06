"""Summarize the fixed 30-turn objective on recorded prefixes, without relabeling.

This joins result metadata to a completed scalar census. It reconstructs only
the signed terminal outcome and official team score at turn 30. It cannot
recover all endpoint potentials/exploration needed for shaped 30-turn targets.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import mean

from verification.team_critic_horizon_20261106.probe import digest


def prefix_outcome(result, terminal_reward, horizon=30):
    """A game still in progress after the complete horizon is a scored draw."""
    assert result['reason'] in ('victory', 'turn_limit')
    return terminal_reward if result['reason'] == 'victory' and result['turns'] <= horizon else 0.


def team_score(signed_outcome):
    return {-1.: 0., 0.: 1., 1.: 3.}[signed_outcome]


def summarize(run, calibration_path):
    calibration = json.loads(calibration_path.read_text())
    assert digest(run / 'manifest.json') == calibration['identities']['manifest_sha256']
    assert digest(run / 'team2v2' / 'state.json') == calibration['identities']['state_sha256']
    jobs_path = run / 'team2v2' / 'jobs.jsonl'
    games = {game['id']: game for game in calibration['trajectories']}
    assert len(games) == calibration['games']
    selected = {}
    with jobs_path.open() as stream:
        for line in stream:
            job = json.loads(line)
            if job['id'] not in games:
                continue
            assert job['id'] not in selected, 'ambiguous recorded result'
            assert job['status'] == 'complete' and not job['result']['faults']
            selected[job['id']] = job
    assert selected.keys() == games.keys()
    groups = defaultdict(list)
    for identifier, game in games.items():
        result = selected[identifier]['result']
        assert game['max_turns'] == 60
        assert (result['reason'] == 'turn_limit') == game['truncated']
        outcome30 = prefix_outcome(result, game['terminal_reward'])
        item = dict(id=identifier, result_turn=result['turns'], phase=game['phase'],
                    reason=result['reason'], signed_outcome60=game['terminal_reward'],
                    signed_outcome30=outcome30, official_score30=team_score(outcome30),
                    official_score60=team_score(game['terminal_reward']),
                    recorded_rows=game['rows'],
                    bootstrap_value=game['bootstrap_value'] if game['truncated'] else None,
                    bootstrap_out_of_bounds=game['bootstrap_out_of_bounds'])
        groups['all'].append(item)
        groups[game['phase']].append(item)
    summaries = {}
    for phase, items in groups.items():
        turns = [item['result_turn'] for item in items]
        counts = Counter('cap60' if item['reason'] == 'turn_limit' else
                         'natural_through30' if item['result_turn'] <= 30 else 'natural_after30'
                         for item in items)
        capped = [item for item in items if item['reason'] == 'turn_limit']
        rows = sum(item['recorded_rows'] for item in items)
        bands = ('early', 'middle', 'late') if phase == 'all' else (phase,)
        after30 = sum(calibration['cohorts'][f'{band}/{kind}/turn_31_plus']['counts']['rows']
                      for band in bands for kind in ('natural', 'truncated'))
        summaries[phase] = dict(
            games=len(items), counts=dict(counts), decisions=rows,
            decisions_after30=after30, decisions_after30_fraction=after30 / rows,
            ongoing_at30=counts['cap60'] + counts['natural_after30'],
            terminal_outcomes60=dict(Counter(str(item['signed_outcome60']) for item in items)),
            terminal_outcomes30=dict(Counter(str(item['signed_outcome30']) for item in items)),
            signed_outcome_changes=sum(item['signed_outcome30'] != item['signed_outcome60'] for item in items),
            official_score60_mean=mean(item['official_score60'] for item in items),
            official_score30_mean=mean(item['official_score30'] for item in items),
            result_turn_min=min(turns), result_turn_max=max(turns),
            bootstrap_mean=mean(item['bootstrap_value'] for item in capped),
            bootstrap_min=min(item['bootstrap_value'] for item in capped),
            bootstrap_max=max(item['bootstrap_value'] for item in capped),
            bootstrap_outside_complete_support=sum(item['bootstrap_out_of_bounds'] for item in capped))
    return dict(scope='same recorded action prefix; terminal component only, not new training labels',
                target_horizon=30, recorded_training_horizon=60,
                identities=dict(calibration_sha256=digest(calibration_path), jobs_sha256=digest(jobs_path),
                                manifest_sha256=calibration['identities']['manifest_sha256'],
                                state_sha256=calibration['identities']['state_sha256']),
                cohorts=summaries, games=groups['all'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('calibration', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('new evidence path required: ' + str(args.output))
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(summarize(args.run, args.calibration), stream, indent=2, allow_nan=False)
        stream.write('\n')
