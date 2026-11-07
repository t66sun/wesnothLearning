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
            restart_bc=False, weights_only=False, checkpoint_name='latest'):
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
        anchor = state.get('runner', {}).get('frozen_bc_anchor')
        if anchor and not restart_bc and not weights_only:
            from .bc_anchor import ANCHOR_FILE
            frozen = source / fmt / ANCHOR_FILE
            if anchor.get('path') != ANCHOR_FILE or not frozen.is_file() or _sha256(frozen) != anchor.get('checkpoint_sha256'):
                raise ValueError('branch frozen BC anchor is missing or changed')
            _atomic_copy(frozen, destination / fmt / ANCHOR_FILE)
        records[fmt] = dict(sha256=_sha256(target), version=state.get('runner', {}).get('version'),
                            checkpoint_version=state.get('checkpoint_version', 1),
                            source=str(checkpoint), role=checkpoint_name, task_id=state.get('task_id'))
        runner = state.get('runner', {})
        history = runner.get('history', [])
        if (not restart_bc and not weights_only and runner.get('effective') and not runner.get('pending_train') and history
                and history[-1].get('method') == 'bc' and (source / fmt / 'last_bc.pt').is_file()):
            from .bc_anchor import _endpoint
            endpoint_path = source / fmt / 'last_bc.pt'
            endpoint = _endpoint(torch.load(endpoint_path, map_location='cpu', weights_only=False), fmt)
            initial = _endpoint(state, fmt)
            if any(endpoint[key] != initial[key] for key in ('version', 'weights_sha256', 'task_id', 'features', 'architecture')):
                raise ValueError('branch BC endpoint differs from its initial checkpoint')
            origin = json.loads((source / 'manifest.json').read_text())
            from .teachers.registry import role, execution_identity
            from .teachers.provenance import engine_identity
            spec=role(origin,fmt)
            engine=origin['config'].get('engine','native')
            teacher = dict(engine_identity(engine),**execution_identity(spec,engine)) if spec else origin.get('teacher')
            if endpoint['manifest_sha256'] != _sha256(source / 'manifest.json'):
                from .checkpoints import branch_lineage
                prior = (branch_lineage(source / fmt) or {}).get('checkpoints', {}).get(fmt, {}).get('bc_endpoint', {})
                if prior.get('sha256') != _sha256(endpoint_path):
                    raise ValueError('branch BC endpoint is outside its recorded lineage')
                teacher = prior.get('teacher_initialization')
            records[fmt]['bc_endpoint'] = dict(sha256=_sha256(endpoint_path), version=endpoint['version'],
                manifest_sha256=endpoint['manifest_sha256'], teacher_initialization=teacher)
            _atomic_copy(endpoint_path, destination / fmt / 'last_bc.pt')
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
