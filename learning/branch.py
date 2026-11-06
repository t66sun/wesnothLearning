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


def prepare(source, destination, formats, *, seed, reset_optimizer=False, clock=None,
            weights_only=False, checkpoint_name='latest'):
    """Copy each format's latest checkpoint and describe the new lineage."""
    source = Path(source)
    destination = Path(destination)
    records = {}
    for fmt in formats:
        checkpoint = source / fmt / (checkpoint_name+'.pt')
        if not checkpoint.is_file():
            raise ValueError(f'branch source has no latest checkpoint for {fmt}')
        target = destination / fmt / 'latest.pt'
        _atomic_copy(checkpoint, target)
        state = torch.load(target, map_location='cpu', weights_only=False)
        if state.get('format') != fmt:
            raise ValueError(f'branch source checkpoint is not {fmt}')
        if weights_only and state.get('runner', {}).get('pending_train'):
            raise ValueError('weights-only initialization requires a complete checkpoint')
        records[fmt] = dict(sha256=_sha256(target), version=state.get('runner', {}).get('version'),
                            checkpoint_version=state.get('checkpoint_version', 1),
                            source=str(checkpoint), role=checkpoint_name, task_id=state.get('task_id'))
    return dict(schema=BRANCH_VERSION, created=time.time(), seed=seed,
                reset_optimizer=bool(reset_optimizer), weights_only=bool(weights_only), clock=clock, checkpoints=records)


def fresh_state(fmt, clock, phase):
    return dict(format=fmt, stage='calibration', phase=phase, clock=clock, batch=0, version=0,
                history=[], snapshots=[], best_key=None, bc_key=None, ppo_key=None, best_kind=None,
                pending_train=None, pending_validation=None, teacher_shards=[], effective=False, error=None)


def validate_bc_inputs(parent, child):
    """A restarted BC phase consumes the parent's raw supervision on its original split."""
    for key in ('row_schema', 'batch_contract', 'teacher', 'task_id'):
        if parent.get(key) != child.get(key):
            raise ValueError(f'BC branch requires matching {key}')
    if ([o['sha256'] for o in parent['opponents']] != [o['sha256'] for o in child['opponents']]
            or parent['config'].get('training_max_turns', 60) != child['config'].get('training_max_turns', 60)):
        raise ValueError('BC branch requires matching opponent packages and training turn limit')


def adopt(state, branch, clock, phase):
    """Return the child runner state for a copied checkpoint."""
    if branch.get('weights_only'):
        state = fresh_state(state['format'], clock, phase)
    elif branch.get('restart_bc'):
        if state.get('pending_train') or state.get('pending_validation'):
            raise ValueError('BC branch requires a committed parent boundary')
        initial = fresh_state(state['format'], clock, phase)
        for key in ('teacher_shards', 'dagger_shards', 'lineage'):
            initial[key] = list(state.get(key, []))
        state = initial
    else:
        state = copy.deepcopy(state)
        state.update(clock=clock, stage='bc', phase=phase, pending_train=None, pending_validation=None, error=None)
    state.setdefault('lineage', []).append(dict(
        parent=branch['parent'], parent_manifest_sha256=branch['parent_manifest_sha256'],
        parent_clock=branch['parent_clock'], seed=branch['seed'],
        optimizer='reset' if branch['reset_optimizer'] else 'kept',
        checkpoints=branch['checkpoints'], created=branch['created']))
    state['branch'] = dict(parent=branch['parent'], manifest_sha256=branch['parent_manifest_sha256'])
    return state
