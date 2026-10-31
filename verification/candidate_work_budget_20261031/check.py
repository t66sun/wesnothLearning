"""Play native games for every format under the deterministic work budget.

Usage: python check.py <repo-root> <output-dir> <wesnoth-binary> <source-commit>

Exports one policy add-on carrying all three formats plus a support add-on, then
plays two seeded games per format on a fixed dense synthetic map with the frozen
one-second action budget.  Every learner decision emits a LEARN row whose timing
carries generation, scoring and charged work, so generation and scoring are
judged separately from the decision total.
"""
import gzip
import hashlib
import json
import statistics
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
wesnoth = str(Path(sys.argv[3]).resolve())
commit = sys.argv[4] if len(sys.argv) > 4 else 'unknown'
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'vendor/arena'))

import torch
from learning.export import export
from learning.features import schema
from learning.formats import FORMATS, PLAYERS, TEAM2V2
from learning.model import Policy
from vendor.arena import match, params

SEEDS = (20261101, 20261102)
TURNS = 20
RETURNED = Path(out) / 'games'


def dense_map(players):
    """One fixed 21x15 grass map: a keep and castle ring per start, seven villages."""
    width, height = 21, 15
    rows = [['Gg'] * width for _ in range(height)]
    starts = [(4, 4), (18, 4), (4, 12), (18, 12)][:players]
    for x, y in starts:
        rows[y - 1][x - 1] = 'Kh'
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, 1), (1, 1)):
            nx, ny = x + dx, y + dy
            if 1 <= nx <= width and 1 <= ny <= height and rows[ny - 1][nx - 1] == 'Gg':
                rows[ny - 1][nx - 1] = 'Ch'
    for x, y in ((8, 7), (14, 7), (10, 5), (12, 5), (8, 9), (14, 9), (11, 7)):
        rows[y - 1][x - 1] = 'Gg^Vh'
    return dict(terrain=rows, starts=starts, width=width, height=height)


def percentile(values, share):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(share * (len(ordered) - 1)))))
    return ordered[index]


def play(policy, support, fmt, seed, max_turns):
    path = RETURNED / f'{fmt}-{seed}-{max_turns}.replay'
    result = match.play_game(bots=[str(policy)] * PLAYERS[fmt], seed=seed,
                             factions=[params.FACTIONS[i % 6] for i in range(PLAYERS[fmt])],
                             teams=TEAM2V2 if fmt == 'team2v2' else None,
                             max_turns=max_turns, timeout=1, first_timeout=10, fog=True,
                             wesnoth=wesnoth, map_override=dense_map(PLAYERS[fmt]),
                             replay_path=str(path),
                             learning=dict(support=str(support),
                                           sides={str(side): dict(teacher=False, version='timing')
                                                  for side in range(1, PLAYERS[fmt] + 1)}))
    events = [json.loads(line) for line in
              gzip.open(path.with_suffix('.events.jsonl.gz'), 'rt', encoding='utf-8')]
    return result, events


def measure(result, events):
    collected, evaluation, execution = [], [], []
    over = []
    for event in events:
        data = event['data']
        if event['event'] == 'LEARN' and data.get('turn', 0) >= 5:
            timing = data.get('timing') or {}
            collected.append(dict(turn=data['turn'], side=data['side'], work=timing.get('work'),
                                  truncated=timing.get('truncated'),
                                  generate_ms=timing.get('generate_ms', timing.get('ms')),
                                  score_ms=timing.get('score_ms'),
                                  candidates=len(data.get('candidates') or [])))
        elif event['event'] == 'RETURN':
            (evaluation if data.get('phase') == 'evaluation' else execution).append(data.get('elapsed_ms'))
            if data.get('phase') == 'evaluation' and data.get('elapsed_ms', 0) >= 800:
                over.append(data['elapsed_ms'])
    for row in collected:
        if row['candidates'] > 37 or (row['work'] or 0) > 12000:
            over.append(row)
    return collected, evaluation, execution, over


def summarise(fmt, games):
    collected = [row for game in games for row in game['collected']]
    evaluation = [value for game in games for value in game['evaluation']]
    execution = [value for game in games for value in game['execution']]
    return dict(format=fmt,
                games=[dict(seed=game['seed'], turns=game['turns'], reason=game['reason'],
                            winner=game['winner'], faults=game['faults'], max_turns=game['max_turns'])
                        for game in games],
                decisions=len(collected),
                generate_ms=dict(p50=percentile([row['generate_ms'] for row in collected], .5),
                                 p95=percentile([row['generate_ms'] for row in collected], .95),
                                 max=max([row['generate_ms'] or 0 for row in collected] or [0])),
                score_ms=dict(p50=percentile([row['score_ms'] for row in collected], .5),
                              p95=percentile([row['score_ms'] for row in collected], .95),
                              max=max([row['score_ms'] or 0 for row in collected] or [0])),
                elapsed_ms=dict(decisions=len(evaluation), max=max(evaluation or [0]),
                                p95=percentile(evaluation, .95)),
                execution_ms=dict(decisions=len(execution), max=max(execution or [0])),
                max_candidates=max([row['candidates'] for row in collected] or [0]),
                max_work=max([row['work'] or 0 for row in collected] or [0]),
                truncated=sum(1 for row in collected if row['truncated']),
                over_budget=sum(1 for game in games for _ in game['over']))


def judge(summary):
    failures = []
    if summary['decisions'] < 10:
        failures.append(f"decisions {summary['decisions']} < 10")
    if summary['generate_ms']['p95'] > 250:
        failures.append(f"generate p95 {summary['generate_ms']['p95']} > 250")
    if summary['generate_ms']['max'] > 500:
        failures.append(f"generate max {summary['generate_ms']['max']} > 500")
    if summary['score_ms']['p95'] > 400:
        failures.append(f"score p95 {summary['score_ms']['p95']} > 400")
    if summary['elapsed_ms']['max'] >= 800:
        failures.append(f"decision max {summary['elapsed_ms']['max']} >= 800")
    if summary['over_budget']:
        failures.append(f'{summary["over_budget"]} decisions over the contract')
    for game in summary['games']:
        if game['faults']:
            failures.append(f"{summary['format']} seed {game['seed']} faults {game['faults']}")
        if game['reason'] == 'watchdog_timeout':
            failures.append(f"{summary['format']} seed {game['seed']} watchdog timeout")
    return failures


out.mkdir(parents=True, exist_ok=True)
RETURNED.mkdir(parents=True, exist_ok=True)
torch.manual_seed(0)
policy = export({fmt: Policy(fmt) for fmt in FORMATS}, out / 'policy', name='WorkBudget',
                version='timing', package=False)
support = export(Policy('duel'), out / 'support', name='LearningSupport', version='timing', package=False)

formats = {}
for fmt in FORMATS:
    games = []
    for turns in (TURNS, 30):
        games = []
        for seed in SEEDS:
            result, events = play(policy, support, fmt, seed, turns)
            collected, evaluation, execution, over = measure(result, events)
            games.append(dict(seed=seed, turns=result['turns'], reason=result['reason'],
                              winner=result.get('winner'), faults=result.get('faults'),
                              max_turns=turns, collected=collected, evaluation=evaluation,
                              execution=execution, over=over))
        if sum(len(game['collected']) for game in games) >= 10:
            break
    formats[fmt] = summarise(fmt, games)
    print(json.dumps(formats[fmt], sort_keys=True))

summary = dict(source=commit, wesnoth=wesnoth,
               wesnoth_sha256=hashlib.sha256(Path(wesnoth).read_bytes()).hexdigest(),
               rules_sha256=schema()['rules_sha256'], schema=schema()['version'],
               candidate=schema()['candidate_selection'], seeds=list(SEEDS), formats=formats)
summary['failures'] = {fmt: judge(value) for fmt, value in formats.items()}
(out / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps(summary['failures'], sort_keys=True))
raise SystemExit(1 if any(summary['failures'].values()) else 0)
