"""Apply the frozen 48 shared / 16 matched actor-only BC update."""
from collections import defaultdict
from pathlib import Path
import random
import time

import torch
from torch.nn import functional as F

from learning.bc import auxiliary_loss
from learning.bc_anchor import weights_sha256
from learning.checkpoints import checkpoint
from learning.coverage import matching
from learning.export import load_model
from learning.model import batch
from learning.rowpack import pack_line
from learning.sequences import _iter_rows, _validate_raw, attach_histories
from verification.duel_learner_state_20261115 import corpus
from verification.duel_ppo_comparison_20261106.audit import write_new
from .protocol import CONTROL, TREATMENT


def matched_refs(step, role):
    if role not in (CONTROL, TREATMENT):
        raise ValueError('unknown BC comparison arm')
    if len(step['shared']) != corpus.SHARED or len(step['swaps']) != corpus.SWAPPED:
        raise ValueError('frozen step does not have 48 shared and 16 matched targets')
    side = 1 if role == TREATMENT else 0
    yield from ((CONTROL, tuple(ref)) for ref in step['shared'])
    yield from ((role, tuple(pair[side])) for pair in step['swaps'])


def selected_rows(game, requested, role, candidate_version):
    shard = Path(game['shard'])
    if game['partition'] != 'train' or corpus.file_sha(shard) != game['sha256']:
        raise ValueError(f"ineligible or changed shard: {shard}")
    rows = list(_iter_rows(shard))
    source = 'policy' if role == TREATMENT else 'astra'
    if (len(rows) != game['rows'] or not rows or rows[0]['turn'] != 1
            or sorted({row['decision'] for row in rows}) != [row['decision'] for row in rows]):
        raise ValueError(f'incomplete original learner or teacher chronology: {shard}')
    for row in rows:
        corpus.check_row(row, game, candidate_version, source)
    origins = {row['decision']: row for row in attach_histories(rows) if row['decision'] in requested}
    if origins.keys() != requested:
        raise ValueError(f'frozen target is absent: {shard}')
    labels = origins
    if role == TREATMENT:
        label_path = Path(game['labels'])
        if corpus.file_sha(label_path) != game['labels_sha256']:
            raise ValueError(f'changed DAgger shard: {label_path}')
        labels = {}
        for row in _iter_rows(label_path):
            ordinal = row['decision']
            if ordinal not in requested:
                continue
            if ordinal in labels:
                raise ValueError(f'duplicate DAgger target: {ordinal}')
            corpus.check_row(row, game, candidate_version, 'astra')
            if not row.get('query_only') or row['actual']['kind'] not in corpus.TARGET_KINDS:
                raise ValueError(f'ineligible DAgger target: {ordinal}')
            labels[ordinal] = row
        if labels.keys() != requested:
            raise ValueError(f'frozen DAgger target is absent: {label_path}')
    for decision, origin in origins.items():
        label = labels[decision]
        choice = label['choice']
        _validate_raw(label, 'duel')
        if choice < 0 or matching(origin['candidates'], label['actual']) != choice:
            raise ValueError(f'exact label mismatch at {shard}:{decision}')
        public = {key: origin[key] for key in corpus.ACTOR_FIELDS}
        if role == TREATMENT and pack_line(public) != pack_line({key: label[key] for key in corpus.ACTOR_FIELDS}):
            raise ValueError(f'learner view differs from its DAgger copy: {shard}:{decision}')
        yield decision, (dict(public, _history=origin['_history'], choice=choice), corpus.stratum(game, label))


def read_targets(data, plan, role, version):
    requested = defaultdict(set)
    if len(plan) != corpus.STEPS:
        raise ValueError('frozen plan does not contain 64 steps')
    for step in plan:
        for source, (game, ordinal) in matched_refs(step, role):
            requested[source, game].add(ordinal)
        if role == TREATMENT:
            for (game, ordinal), _ in step['swaps']:
                requested[CONTROL, game].add(ordinal)
    result = {}
    for (source, game), ordinals in requested.items():
        group = 'teacher' if source == CONTROL else 'learner'
        for ordinal, target in selected_rows(data[group][game], ordinals, source, version):
            result[source, (game, ordinal)] = target
    if role == TREATMENT:
        for step in plan:
            for left, right in step['swaps']:
                if result[CONTROL, tuple(left)][1] != result[TREATMENT, tuple(right)][1]:
                    raise ValueError('prepared target stratum differs between the two arms')
    return result


def update_step(model, optimizer, rows, objective):
    optimizer.zero_grad()
    loss_value = 0.
    cache = {}
    for start in range(0, len(rows), 32):
        micro = rows[start:start+32]
        logits, _ = model(*batch(micro, history_cache=cache))
        target = torch.tensor([row['choice'] for row in micro], dtype=torch.long)
        loss = F.cross_entropy(logits, target) + objective['marginal_weight'] * auxiliary_loss(logits, micro)
        if not torch.isfinite(loss):
            raise ValueError('nonfinite actor loss')
        loss = loss * (len(micro)/len(rows))
        loss.backward()
        loss_value += float(loss.detach())
    torch.nn.utils.clip_grad_norm_(model.parameters(), objective['max_grad_norm'], error_if_nonfinite=True)
    optimizer.step()
    return loss_value


def fit(folder, seed, role, data, inputs, deadline):
    torch.set_num_threads(inputs['trainer_threads'])
    torch.manual_seed(seed)
    random.seed(seed)
    plan = data['plans'][str(seed)]
    origin = corpus.PARENT/'duel/last_bc.pt'
    model, _ = load_model(origin, 'duel')
    if weights_sha256(model.state_dict()) != inputs['checkpoint']['weights_sha256']:
        raise ValueError('initial weights differ from qualified v38')
    model.train()
    model.value.requires_grad_(False)
    value_sha = weights_sha256(model.value.state_dict())
    optimizer = torch.optim.Adam([parameter for parameter in model.parameters() if parameter.requires_grad],
                                 lr=inputs['learning_rate'])
    targets = read_targets(data, plan, role, inputs['environment']['candidate_version'])
    folder.mkdir(parents=True)
    losses, visits = [], 0
    for index, step in enumerate(plan, 1):
        if time.time() >= deadline:
            raise RuntimeError(f'training deadline before step {index}')
        rows = [targets[ref][0] for ref in matched_refs(step, role)]
        losses.append(update_step(model, optimizer, rows, inputs))
        visits += len(rows)
    file = folder/'endpoint.pt'
    checkpoint(file, model, optimizer, task_id=inputs['task'], seed=seed, role=role,
               optimizer_steps=len(losses), target_visits=visits, initial_weights_sha256=inputs['checkpoint']['weights_sha256'])
    reopened, state = load_model(file, 'duel')
    weights = weights_sha256(reopened.state_dict())
    if (weights_sha256(reopened.value.state_dict()) != value_sha or weights != weights_sha256(model.state_dict())
            or len(losses) != corpus.STEPS or visits != corpus.STEPS*(corpus.SHARED+corpus.SWAPPED)):
        raise ValueError('incomplete or inconsistent endpoint')
    write_new(folder/'endpoint.json', dict(path=str(file), sha256=corpus.file_sha(file), weights_sha256=weights,
        steps=state['optimizer_steps'], visits=state['target_visits'], losses=losses, value_sha256=value_sha))
