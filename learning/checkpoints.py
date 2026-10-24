"""Checkpoint serialization and RNG restoration."""
import random
from pathlib import Path

import torch

from .features import schema
from .model import ARCHITECTURE


def checkpoint(path, model, optimizer, **metadata):
    state = dict(model=model.state_dict(), optimizer=optimizer.state_dict(),
                 python_rng=random.getstate(), torch_rng=torch.get_rng_state(),
                 cuda_rng=torch.cuda.get_rng_state_all() if next(model.parameters()).device.type == 'cuda' else [],
                 features=schema(), architecture=ARCHITECTURE, **metadata)
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
