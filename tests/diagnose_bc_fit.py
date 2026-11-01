"""Offline historical-checkpoint fit diagnosis; no experiment state is written."""
import argparse
import copy
import json
from pathlib import Path
import time

import torch
from learning.audit import audit_bc, fit_small_set
from learning.bc import imitation_quality
from learning.model import Policy
from learning.sequences import read_shards


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--format', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--steps', type=int, default=200)
    args = p.parse_args()
    torch.set_num_threads(1)
    started = time.monotonic()
    directory = args.run/args.format
    checkpoint = torch.load(directory/'latest.pt', map_location='cpu', weights_only=False)
    state = checkpoint['runner']
    paths = state['teacher_shards']
    rows = read_shards(paths, format_name=args.format)
    model = Policy(args.format)
    # These frozen v5 rows and weights are evaluated together. This is an offline
    # historical diagnostic, never a schema migration or a formal resumed run.
    model.load_state_dict(checkpoint['model'])
    valid = [r for r in rows if r['split']=='validation']
    train = [r for r in rows if r['split']=='train']
    training_view = [dict(r, split='validation') for r in train]
    result = dict(format=args.format, source_run=str(args.run), version=state['version'],
                  train_rows=len(train), validation_rows=len(valid),
                  train_fit=imitation_quality(model, training_view),
                  heldout_fit=imitation_quality(model,valid),
                  representation=audit_bc(valid),
                  tiny_fit=fit_small_set(model,train,steps=args.steps),
                  seconds=time.monotonic()-started)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='representation'}),flush=True)


if __name__=='__main__':
    main()
