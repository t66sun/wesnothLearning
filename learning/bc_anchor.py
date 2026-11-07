"""One immutable, complete BC endpoint for optional PPO distribution rehearsal."""
import copy
import hashlib
import shutil

import torch

from .checkpoints import branch_lineage, validate_checkpoint
from .common import sha256
from .export import load_model
from .rowpack import ROW_SCHEMA

TARGETS = ('historical_action', 'frozen_bc_kl')
ANCHOR_FILE = 'frozen_bc.pt'


def target_mode(config):
    mode = config.get('ppo_aux_target', 'historical_action')
    if mode not in TARGETS:
        raise ValueError('unknown PPO auxiliary target: ' + str(mode))
    return mode


def weights_sha256(state):
    digest = hashlib.sha256()
    for name in sorted(state):
        digest.update(name.encode())
        digest.update(state[name].detach().cpu().numpy().tobytes())
    return digest.hexdigest()


def _endpoint(state, fmt):
    from .teachers.provenance import metadata as teacher_metadata
    validate_checkpoint(state, fmt)
    runner = state.get('runner', {})
    history = runner.get('history', [])
    if (not all(key in state for key in ('optimizer', 'python_rng', 'torch_rng', 'manifest_sha256'))
            or runner.get('pending_train') or not runner.get('effective')
            or runner.get('version', 0) <= 0 or not history
            or history[-1].get('method') != 'bc' or history[-1].get('updates', 0) <= 0):
        raise ValueError('frozen BC requires a complete qualifying BC endpoint')
    return dict(format=state['format'], features=state['features'], architecture=state['architecture'],
                checkpoint_version=state.get('checkpoint_version', 1),
                manifest_sha256=state['manifest_sha256'], version=runner['version'],
                task_id=state.get('task_id'),
                weights_sha256=weights_sha256(state['model']),
                teacher=teacher_metadata(state),
                parent_lineage=copy.deepcopy(runner.get('lineage', [])),
                parent_branch=copy.deepcopy(runner.get('branch')))


def _load(runner, identity):
    if not {'teacher_initialization', 'initialization_lineage'} <= identity.keys():
        raise ValueError('frozen BC anchor lineage is missing')
    if identity.get('path') != ANCHOR_FILE:
        raise ValueError('frozen BC anchor path differs')
    path = runner.directory / ANCHOR_FILE
    if not path.is_file():
        raise ValueError('frozen BC anchor is missing')
    if sha256(path) != identity.get('checkpoint_sha256'):
        raise ValueError('frozen BC anchor checkpoint hash differs')
    cached = getattr(runner, '_bc_anchor', None)
    if cached is not None:
        if identity != runner._bc_anchor_identity:
            raise ValueError('frozen BC anchor identity differs')
        if weights_sha256(cached.state_dict()) != identity['weights_sha256']:
            raise ValueError('frozen BC anchor weights changed in memory')
        return cached
    device = torch.device(runner.device)
    devices = [device.index if device.index is not None else torch.cuda.current_device()] if device.type == 'cuda' else []
    # Constructing Policy initializes parameters. It must not advance restored
    # RNG streams or make the historical-action comparison start elsewhere.
    with torch.random.fork_rng(devices=devices):
        model, state = load_model(path, runner.fmt, runner.device)
    endpoint = _endpoint(state, runner.fmt)
    if any(identity.get(key) != value for key, value in endpoint.items()):
        raise ValueError('frozen BC anchor identity differs')
    if identity.get('row_schema') != runner.manifest.get('row_schema', ROW_SCHEMA):
        raise ValueError('frozen BC anchor row schema differs')
    if endpoint['task_id'] != runner.config.get('task_id'):
        raise ValueError('frozen BC anchor task differs')
    model.eval().requires_grad_(False)
    runner._bc_anchor = model
    runner._bc_anchor_identity = copy.deepcopy(identity)
    return model


def restore_anchor(runner, loaded, *, branch=False):
    """Validate the saved mode and anchor before resuming any update or export."""
    mode = target_mode(runner.config)
    saved_mode = (loaded.get('execution') or {}).get('ppo_aux_target', 'historical_action')
    if not branch and saved_mode != mode:
        raise ValueError('checkpoint PPO auxiliary target differs from frozen configuration')
    if mode != 'frozen_bc_kl':
        return
    identity = runner.state.get('frozen_bc_anchor')
    if identity:
        _load(runner, identity)
    elif runner.state.get('stage') in ('ppo', 'ppo_complete') or (runner.state.get('pending_train', {}) or {}).get('method') == 'ppo' or any(
            entry['method'] == 'ppo' for entry in runner.state.get('history', [])):
        raise ValueError('frozen BC anchor identity is missing from PPO checkpoint')


def ensure_anchor(runner):
    """Pin last_bc once at the PPO boundary; never consult latest or selected."""
    if target_mode(runner.config) != 'frozen_bc_kl':
        return None
    identity = runner.state.get('frozen_bc_anchor')
    if identity:
        return _load(runner, identity)
    if any(entry['method'] == 'ppo' for entry in runner.state.get('history', [])):
        raise ValueError('frozen BC anchor identity is missing from PPO checkpoint')
    source = runner.directory / 'last_bc.pt'
    if not source.is_file():
        raise ValueError('frozen BC requires a complete qualifying last_bc.pt')
    state = torch.load(source, map_location='cpu', weights_only=False)
    endpoint = _endpoint(state, runner.fmt)
    from .teachers.roles import identity as teacher_identity
    teacher = teacher_identity(runner) or runner.manifest.get('teacher')
    if endpoint['manifest_sha256'] != sha256(runner.directory.parent / 'manifest.json'):
        lineage = branch_lineage(runner.directory) or {}
        inherited = lineage.get('checkpoints', {}).get(runner.fmt, {}).get('bc_endpoint', {})
        if (endpoint['manifest_sha256'] != inherited.get('manifest_sha256')
                or sha256(source) != inherited.get('sha256')):
            raise ValueError('frozen BC endpoint must belong to this run or its pinned BC initialization')
        teacher = inherited.get('teacher_initialization')
    if endpoint['task_id'] != runner.config.get('task_id'):
        raise ValueError('frozen BC anchor task differs')
    identity = dict(endpoint, path=ANCHOR_FILE, checkpoint_sha256=sha256(source),
                    row_schema=runner.manifest.get('row_schema', ROW_SCHEMA),
                    initialization_lineage=copy.deepcopy(runner.state.get('lineage', [])),
                    teacher_initialization=copy.deepcopy(teacher))
    path = runner.directory / ANCHOR_FILE
    if path.exists():
        if sha256(path) != identity['checkpoint_sha256']:
            raise ValueError('existing frozen BC anchor differs from the BC endpoint')
    else:
        temporary = path.with_suffix('.tmp')
        shutil.copyfile(source, temporary)
        temporary.replace(path)
    model = _load(runner, identity)
    runner.state['frozen_bc_anchor'] = identity
    runner.save()
    return model


def forward_kl(anchor_logits, current_logits, mask):
    """KL(stop_gradient(anchor) || current), finite on padded legal supports."""
    anchor_logp = anchor_logits.detach().masked_fill(~mask, -torch.inf).log_softmax(-1)
    current_logp = current_logits.masked_fill(~mask, -torch.inf).log_softmax(-1)
    difference = current_logp.masked_fill(~mask, 0)
    difference = anchor_logp.masked_fill(~mask, 0) - difference
    return (anchor_logp.exp() * difference).sum(-1)
