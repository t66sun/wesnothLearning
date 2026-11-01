"""Read-only audit of the bounded reader's actual family admission decisions."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import torch

from learning import sequences
from learning.export import load_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    config = json.loads((args.run / 'manifest.json').read_text())['config']
    results = {}
    for fmt in config['formats']:
        checkpoint = args.run / fmt / 'last_bc.pt'
        _, saved = load_model(checkpoint, fmt)
        state = saved['runner']
        observed = {}

        def trace_return(frame, event, arg):
            if event == 'return':
                local = frame.f_locals
                observed.update({k: local[k] for k in ('charged', 'blocked_gz', 'blocked_retain')})
                observed['pending_buckets'] = len(local['pending'])
                observed['families'] = [dict(family=e['windows'][0][0]['game_family'],
                    capacity=e['capacity'], prefix=e['prefix'],
                    faction=e['windows'][0][0].get('faction')) for e in local['admitted']]
            return trace_return

        def trace(frame, event, arg):
            if frame.f_code is sequences._read_bounded.__code__:
                return trace_return

        stats = {}
        sys.settrace(trace)
        rows = sequences.read_shards(state['teacher_shards'], partition='train', format_name=fmt,
            limit=config['bc_records'], seed=config['seed'] + state['version'] - 1, stats=stats)
        sys.settrace(None)
        results[fmt] = dict(version=state['version'],
            checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            stats=stats, admission=observed,
            faction_rows=dict(Counter(r.get('faction') for r in rows)))
        print(json.dumps(dict(format=fmt, **results[fmt])), flush=True)
        args.output.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
