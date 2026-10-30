"""Checkpoint serialization and RNG restoration."""
import hashlib
import json
import random
from pathlib import Path

import torch

from .features import schema
from .model import ARCHITECTURE

CHECKPOINT_VERSION = 2
EXECUTION_VERSION = 2


def checkpoint(path, model, optimizer, execution=None, **metadata):
    """Atomically replace one complete training state.

    ``execution`` names the scheduling format understood by the saved cursor.
    Older readers reject a newer version instead of guessing field meanings.
    """
    state = dict(model=model.state_dict(), optimizer=optimizer.state_dict(),
                 python_rng=random.getstate(), torch_rng=torch.get_rng_state(),
                 cuda_rng=torch.cuda.get_rng_state_all() if next(model.parameters()).device.type == 'cuda' else [],
                 features=schema(), architecture=ARCHITECTURE,
                 checkpoint_version=CHECKPOINT_VERSION,
                 execution=dict(version=EXECUTION_VERSION, **(execution or {})), **metadata)
    state['format'] = model.format_name
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    torch.save(state, temporary)
    temporary.replace(path)


def restore_rng(state, device='cpu'):
    random.setstate(state['python_rng'])
    torch.set_rng_state(state['torch_rng'].cpu())
    if torch.device(device).type == 'cuda' and state.get('cuda_rng'):
        torch.cuda.set_rng_state_all([r.cpu() for r in state['cuda_rng']])


def branch_lineage(directory):
    """The branch record beside one format directory, when this run was branched."""
    path = Path(directory).parent / 'branch.json'
    return json.loads(path.read_text()) if path.is_file() else None


def inherited_checkpoint(directory, state):
    """The branch record when ``state`` is still the checkpoint the branch inherited.

    A branch copies its parent's ``latest.pt``, which pins the parent manifest and carries
    the parent clock until the child saves a checkpoint of its own.
    """
    lineage = branch_lineage(directory)
    if lineage and state.get('manifest_sha256') == lineage.get('parent_manifest_sha256'):
        return lineage
    return None


def resume_pins(directory):
    """Manifest digests a checkpoint may pin when resuming one format directory."""
    run = Path(directory).parent
    pins = {hashlib.sha256((run / 'manifest.json').read_bytes()).hexdigest()}
    lineage = branch_lineage(directory)
    if lineage and lineage.get('parent_manifest_sha256'):
        pins.add(lineage['parent_manifest_sha256'])
    return pins


def validate_checkpoint(state, format_name=None, manifest_sha256=None):
    """Reject a checkpoint that this execution cannot resume exactly."""
    version = state.get('checkpoint_version', 1)
    if version > CHECKPOINT_VERSION:
        raise ValueError('checkpoint was written by a newer execution format')
    if state.get('features') != schema():
        raise ValueError('checkpoint feature schema does not match this engine')
    if state.get('architecture') != ARCHITECTURE:
        raise ValueError('checkpoint network architecture does not match this engine')
    if format_name is not None and state.get('format') != format_name:
        raise ValueError('checkpoint belongs to a different format')
    execution = state.get('execution') or {}
    if execution.get('version', 1) > EXECUTION_VERSION:
        raise ValueError('checkpoint execution format is not supported')
    if manifest_sha256 is not None:
        accepted = manifest_sha256 if isinstance(manifest_sha256, (set, frozenset, list, tuple)) else (manifest_sha256,)
        if state.get('manifest_sha256') not in accepted:
            raise ValueError('manifest changed')
    return state
