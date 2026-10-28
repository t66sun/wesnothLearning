"""Ask the accepted labeler why an event stayed unlabelled.

Run against the captured event streams of an accepted probe run:

    python verification/ppo_refactor_r8b_20261030/unmatched_reasons.py <run>/replays/*.events.jsonl.gz

Each reason names the branch the labeler took: no fresh context, an invisible
actor, no matching candidate, or more than one distinct intent.
"""
import gzip, json, sys, types
from pathlib import Path

source = Path('learning/stock_rca.py').read_text()
source = source.replace(
    "        if context is None or visible is not True:\n            coverage[kind]['unmatched'] += 1\n            return",
    "        if context is None or visible is not True:\n            coverage[kind]['unmatched'] += 1\n"
    "            REASONS.append(dict(kind=kind,why='context' if context is None else 'invisible'))\n            return")
source = source.replace(
    "        ambiguous = len(intents) > 1\n",
    "        ambiguous = len(intents) > 1\n"
    "        if not matches:\n"
    "            REASONS.append(dict(kind=kind,why='absent',candidates=len(candidates),actual=actual))\n"
    "        elif ambiguous:\n"
    "            REASONS.append(dict(kind=kind,why='ambiguous',actual=actual))\n")
source = source.replace('from .common import ROOT, sha256', 'from learning.common import ROOT, sha256')
source = 'REASONS=[]\n' + source
module = types.ModuleType('debug_stock_rca')
exec(compile(source, 'debug_stock_rca.py', 'exec'), module.__dict__)
for path in sys.argv[1:]:
    module.REASONS.clear()
    frames = []
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        for line in handle:
            event = json.loads(line)
            if event['event'] == 'STOCK':
                frames.append(event['data'])
    for side in (1, 2):
        rows, coverage = module.frames_to_labels(frames, side=side,
                                                 candidates_fn=lambda row: row['candidates'])
        reasons = list(module.REASONS)
        module.REASONS.clear()
        print(Path(path).name, 'side', side, 'rows', len(rows), 'why', reasons)
