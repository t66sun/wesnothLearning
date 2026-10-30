"""N1 acceptance: fixed native 1.18.8 endgame (real elimination) plus a truncation control.

The policy add-on is deliberately absent: the events under test (initial/eliminated/terminal
metric snapshots and the RESULT record) come from the arena runtime, and stock sides keep the
fixture independent of any exported weights.

Usage: python n1_native.py <repo-root> <output-dir> <wesnoth-binary>
"""
import gzip, json, os, sys, time
from pathlib import Path

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

root = Path(sys.argv[1]).resolve()
outdir = Path(sys.argv[2]).resolve()
wesnoth = str(Path(sys.argv[3]).resolve())
outdir.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root))
os.chdir(root)
os.environ['WESNOTH_EXE'] = wesnoth

import torch
from learning.export import export
from learning.model import Policy
from learning.sample import play_job

torch.manual_seed(0)
support = export({'duel': Policy('duel')}, outdir / 'addons', name='LearningSupport',
                 package=False, version='n1-untrained')


def board(terrain, starts):
    return dict(terrain=terrain, starts=starts,
                width=len(terrain[0]), height=len(terrain))


CLOSE = board([['Gg'], ['Gg']], [[1, 1], [1, 2]])
FAR = board([['Gg'] * 40], [[1, 1], [40, 1]])


def job(ident, seed, max_turns, map_override, factions):
    output = outdir / (ident + '.replay.gz')
    sides = {str(i): dict(teacher=False, version='n1-untrained') for i in (1, 2)}
    return dict(id=ident, engine='native', bots=['baseline', 'baseline'],
                factions=list(factions), seed=seed, max_turns=max_turns, wesnoth=wesnoth,
                map_override=map_override, deadline=time.time() + 1800.,
                output=str(output), shard=str(outdir / (ident + '.jsonl.gz')),
                learning=dict(support=str(support), sides=sides),
                meta=dict(phase='validation', format='duel', context='solo',
                          scenario_family='n1-fixed', split_rule='family-seed-v1'))


def events(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def describe(ident, result):
    path = outdir / (ident + '.replay.events.jsonl.gz')
    rows = events(path)
    kinds = {}
    for row in rows:
        kinds[row['event']] = kinds.get(row['event'], 0) + 1
    metrics = [row['data'] for row in rows if row['event'] == 'METRIC']
    eliminated = [row['data'] for row in rows if row['event'] == 'ELIMINATED']
    bootstraps = [row['data'] for row in rows if row['event'] == 'BOOTSTRAP']
    errors = [row['data'] for row in rows if row['event'].endswith('ERROR')]
    return dict(id=ident, status=result['status'], result=result['result'], events=kinds,
                events_file=str(path), metrics=metrics, eliminated=eliminated,
                bootstraps=bootstraps, errors=errors,
                diagnostics=result.get('reward_diagnostics'),
                shard=result.get('training_shard'))


PAIRS = (('Drakes', 'Undead'), ('Northerners', 'Undead'), ('Drakes', 'Rebels'))


def main():
    report = dict(binary=wesnoth, games=[])
    for index, factions in enumerate(PAIRS):
        for seed in (7, 11, 23):
            ident = f'terminal-{index}-{seed}'
            result = play_job(job(ident, seed, 5, CLOSE, factions))
            row = describe(ident, result)
            row.update(factions=list(factions), seed=seed, max_turns=5, map='close')
            report['games'].append(row)
            print(ident, row['status'], row['result'].get('reason'),
                  row['result'].get('survivors'), row['events'],
                  [error.get('error') for error in row['errors']], flush=True)
    ident = 'truncation-control'
    result = play_job(job(ident, 5, 2, FAR, ('Drakes', 'Undead')))
    row = describe(ident, result)
    row.update(factions=['Drakes', 'Undead'], seed=5, max_turns=2, map='far')
    report['games'].append(row)
    print(ident, row['status'], row['result'].get('reason'), row['events'],
          [error.get('error') for error in row['errors']], flush=True)
    (outdir / 'n1_run.json').write_text(json.dumps(report, indent=1, sort_keys=True) + '\n',
                                        encoding='utf-8', newline='\n')


main()
