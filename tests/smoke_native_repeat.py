"""Prove a stock native duel replays from its seed: two processes, same events."""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKIP = ('SNAPSHOT', 'TURN', 'EXECUTE', 'RETURN', 'CALL')


def events(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        return [event for event in map(json.loads, stream) if event.get('event') not in SKIP]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wesnoth', default=os.environ.get('WESNOTH_EXE'))
    parser.add_argument('--output', required=True)
    parser.add_argument('--seed', type=int, default=20261017)
    parser.add_argument('--turns', type=int, default=30)
    args = parser.parse_args()
    shim = REPO / '.runtime' / 'entropy.so'
    if not shim.is_file():
        raise SystemExit(f'missing {shim}; run ./setup.sh first')
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(REPO / 'vendor' / 'arena'))
    from vendor.arena import match

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    def play(tag):
        result = match.play_game(bots=['baseline', 'baseline'], seed=args.seed, max_turns=args.turns,
                                 wesnoth=args.wesnoth, map_override=None,
                                 replay_path=str(out / f'{tag}.replay.gz'), lenient=True)
        plain = out / f'{tag}.replay.events.jsonl'
        return result, events(plain if plain.is_file() else plain.with_name(plain.name + '.gz'))

    first, first_events = play('first')
    second, second_events = play('second')
    fields = ('reason', 'turns', 'seed')
    report = {
        'first': {key: first.get(key) for key in fields},
        'second': {key: second.get(key) for key in fields},
        'event_counts': [len(first_events), len(second_events)],
        'events_equal': first_events == second_events,
    }
    (out / 'repeat.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report['events_equal'] and report['first'] == report['second'] else 1)


if __name__ == '__main__':
    main()
