"""Shared preparation for the BC and PPO update loops.

This module only prepares validated training rows and the CPU/GPU microbatch
size. Objectives, sampling and stopping live in ``bc.py`` and ``ppo.py``.
"""
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
