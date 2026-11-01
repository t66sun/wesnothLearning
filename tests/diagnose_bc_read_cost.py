"""Measure the two existing BC training reads without collecting or updating."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import time

import torch

from learning.sequences import read_shards


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--format', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((args.run/'manifest.json').read_text())['config']
    checkpoint = args.run/args.format/'last_bc.pt'
    state = torch.load(checkpoint, map_location='cpu', weights_only=False)['runner']
    result = dict(checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(), reads={})
    for label, seed in (('preflight', 19), ('training', config['seed']+state['version']-1)):
        stats = {}
        started = time.monotonic()
        rows = read_shards(state['teacher_shards'], partition='train',
            format_name=args.format, limit=config['bc_records'], seed=seed, stats=stats)
        result['reads'][label] = dict(seconds=time.monotonic()-started, seed=seed,
            rows=len(rows), stats=stats)
        del rows
        gc.collect()
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
