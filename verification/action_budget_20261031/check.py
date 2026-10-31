"""Export a policy and play one native duel game under the frozen 1 s action budget.

Usage: python check.py <repo-root> <output-dir> <wesnoth-binary> [seed]
"""
import json, statistics, sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
wesnoth = str(Path(sys.argv[3]).resolve())
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 20261101
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'vendor/arena'))

import torch
from learning.export import export, SCORE_LIMIT
from learning.model import Policy
from vendor.arena import match

out.mkdir(parents=True, exist_ok=True)
torch.manual_seed(0)
addon = export(Policy('duel'), out / 'policy', name='BudgetCheck', version='timing', package=False, score_limit=SCORE_LIMIT)
result = match.play_game(bots=[str(addon), 'baseline'], seed=seed, max_turns=30, wesnoth=wesnoth,
                         replay_path=str(out / f'game_{seed}.replay.gz'))
events = [json.loads(line) for line in
          (out / f'game_{seed}.replay.events.jsonl').read_text(encoding='utf-8').splitlines()]
elapsed = [e['data']['elapsed_ms'] for e in events if e['event'] == 'RETURN']
summary = dict(seed=seed, score_limit=SCORE_LIMIT, reason=result['reason'], actions=result['actions'],
               turns=result['turns'], seconds=result['seconds'], faults=result['faults'], winner=result['winner'],
               decisions=len(elapsed), max_elapsed_ms=max(elapsed or [0]),
               median_elapsed_ms=statistics.median(elapsed or [0]), budget_ms=1000)
(out / f'check_{seed}.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps(summary, sort_keys=True))
if summary['reason'] == 'watchdog_timeout' or summary['decisions'] < 6 or summary['max_elapsed_ms'] >= 800:
    raise SystemExit(1)
