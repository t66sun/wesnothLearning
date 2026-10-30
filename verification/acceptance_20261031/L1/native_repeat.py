"""Play one native stock game twice from the same seed and compare its event stream.

Usage: python native_repeat.py <repo-root> <output-dir> <wesnoth-binary>
"""
import gzip, json, sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
wesnoth = str(Path(sys.argv[3]).resolve())
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'vendor/arena'))

from vendor.arena import match

def play(tag):
    result = match.play_game(
        bots=['baseline', 'baseline'], seed=20261017, max_turns=30, wesnoth=wesnoth,
        map_override=None, replay_path=str(out / f'{tag}.replay.gz'),
        lenient=True)
    events = []
    path = out / f'{tag}.replay.events.jsonl.gz'
    if not path.exists():
        path = out / f'{tag}.replay.events.jsonl'
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            record = json.loads(line)
            data = record.get('data') or {}
            if record['event'] in ('SNAPSHOT', 'TURN', 'EXECUTE', 'RETURN', 'CALL'):
                continue
            events.append(record)
    return result, events

out.mkdir(parents=True, exist_ok=True)
first, first_events = play('first')
second, second_events = play('second')
summary = dict(
    first={k: first.get(k) for k in ('reason', 'turns', 'status', 'seed')},
    second={k: second.get(k) for k in ('reason', 'turns', 'status', 'seed')},
    events_equal=first_events == second_events,
    first_events=len(first_events), second_events=len(second_events))
(out / 'repeat.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
print(json.dumps(summary, sort_keys=True))
