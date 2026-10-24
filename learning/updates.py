"""Shared preparation for the BC and PPO update loops.

This module only prepares validated training rows and the CPU/GPU microbatch
size. Objectives, sampling and stopping live in ``bc.py`` and ``ppo.py``.
"""
import hashlib
import json

from .data import validate_record
from .sequences import attach_histories, training_windows


def prepare(model, records, bc_records=None):
    """Attach histories, validate, and keep the train split.

    Validation order matches the original combined trainer: every supplied
    record is checked before the empty-training check and method-specific
    rejections.
    """
    if not all('_history' in r for r in records):
        records = attach_histories(records)
    for r in records:
        validate_record(r, model.format_name)
    for r in bc_records or []:
        validate_record(r, model.format_name)
    records = [r for r in records if r['split'] == 'train']
    if not records:
        raise ValueError('no training games')
    return records


def setup(model, records, minibatch):
    """Return the window plan and computation microbatch for one update."""
    device = next(model.parameters()).device
    windows = training_windows(records, turns=8)
    sequence_count = 4 if device.type == 'cpu' else 8
    micro = min(minibatch, 32 if device.type == 'cpu' else 64)
    if micro < 1:
        raise ValueError('minibatch must be positive')
    steps = max(1, (len(windows) + sequence_count - 1) // sequence_count)
    return device, windows, sequence_count, micro, steps


def rollout_identity(rows):
    """Hash the immutable order and provenance of one planned update."""
    digest = hashlib.sha256()
    targets = []
    for row in rows:
        if row.get('choice', -1) < 0:
            continue
        targets.append((row.get('game_id'), row.get('side'), row.get('turn'), row.get('decision'), row))
    targets.sort(key=lambda item: (str(item[0]), str(item[1]), int(item[2]), str(item[3])))
    for game_id, side, turn, decision, row in targets:
        payload = {key: row.get(key) for key in ('version', 'engine_id', 'rules_version', 'rng_version',
                                                  'reward_version', 'reward_formula_id', 'game_family')}
        digest.update(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode())
        digest.update(b'\n')
    return digest.hexdigest()
