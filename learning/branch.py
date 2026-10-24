"""Explicit branching from one complete checkpoint into a new run.

A branch never edits the parent run.  It copies the latest complete checkpoint,
records the parent identities, and starts the child with a new clock, seed and
rollout plan.  Optimizer state is kept unless the caller asks to reset it.
"""
import copy
import hashlib
import json
import time
from pathlib import Path

import torch

BRANCH_VERSION = 1


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _atomic_copy(source, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    with Path(source).open('rb') as reader, temporary.open('wb') as writer:
        for block in iter(lambda: reader.read(1 << 20), b''):
            writer.write(block)
    temporary.replace(destination)


def prepare(source, destination, formats, *, seed, reset_optimizer=False, clock=None):
    """Copy each format's latest checkpoint and describe the new lineage."""
    source = Path(source)
    destination = Path(destination)
    records = {}
    for fmt in formats:
        checkpoint = source / fmt / 'latest.pt'
        if not checkpoint.is_file():
            raise ValueError(f'branch source has no latest checkpoint for {fmt}')
        target = destination / fmt / 'latest.pt'
        _atomic_copy(checkpoint, target)
        state = torch.load(target, map_location='cpu', weights_only=False)
        if state.get('format') != fmt:
            raise ValueError(f'branch source checkpoint is not {fmt}')
        records[fmt] = dict(sha256=_sha256(target), version=state.get('runner', {}).get('version'),
                            checkpoint_version=state.get('checkpoint_version', 1))
    return dict(schema=BRANCH_VERSION, created=time.time(), seed=seed,
                reset_optimizer=bool(reset_optimizer), clock=clock, checkpoints=records)


def adopt(state, branch, clock, phase):
    """Return the child runner state for a copied checkpoint."""
    state = copy.deepcopy(state)
    state.setdefault('lineage', []).append(dict(
        parent=branch['parent'], parent_manifest_sha256=branch['parent_manifest_sha256'],
        parent_clock=branch['parent_clock'], seed=branch['seed'],
        optimizer='reset' if branch['reset_optimizer'] else 'kept',
        checkpoints=branch['checkpoints'], created=branch['created']))
    state['clock'] = clock
    state['stage'] = 'bc'
    state['phase'] = phase
    state['pending_train'] = None
    state['pending_validation'] = None
    state['error'] = None
    state['branch'] = dict(parent=branch['parent'], manifest_sha256=branch['parent_manifest_sha256'])
    return state
