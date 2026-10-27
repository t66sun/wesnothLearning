"""Shared preparation for the BC and PPO update loops.

This module only prepares validated training rows and the CPU/GPU microbatch
size. Objectives, sampling and stopping live in ``bc.py`` and ``ppo.py``.
"""
import hashlib
import json

from .data import validate_record
from .sequences import attach_histories, training_windows

BATCH_CONTRACT = 'scenario-v2/no-drop-v1'


def eligible_rows(records, *, allow_drop=False):
    """Check a composed batch before freezing its identity or applying updates."""
    excluded = sum(r.get('split') != 'train' for r in records)
    if excluded and not allow_drop:
        raise ValueError(f'batch row excluded by split: {excluded} of {len(records)}')
    return [r for r in records if r['split'] == 'train'] if excluded else records


def prepare(model, records, bc_records=None, *, allow_drop=False):
    """Attach histories and validate; PPO rejects rather than drops ineligible rows.

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
    rules = {r.get('split_rule', 'family-seed-v1') for rows in (records, bc_records or []) for r in rows}
    if len(rules) > 1:
        raise ValueError('training batch mixes split rules')
    records = eligible_rows(records, allow_drop=allow_drop)
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
    """Bind target identity, training content and legal raw recurrent prefixes.

    Hash one row at a time; shared prefix slots are hashed once per call. Numeric
    vector lists and arrays use the existing float64 compaction convention.
    """
    from .rowpack import compact_row
    encoder = json.JSONEncoder(sort_keys=True, separators=(',', ':'), allow_nan=False,
                               default=lambda value: value.tolist())
    def content_hash(payload):
        content = hashlib.sha256()
        for piece in encoder.iterencode(compact_row(payload)):
            content.update(piece.encode())
        return content.hexdigest()

    ordered = sorted(rows, key=lambda r: (str(r.get('format')), str(r.get('source')),
        str(r.get('engine_id')), str(r.get('game_family')), str(r.get('game_id')),
        str(r.get('side')), int(r['turn']), int(r.get('decision', r.get('action_index', 0)))))
    if not all('_history' in row for row in ordered):
        ordered = attach_histories(ordered)
    digest = hashlib.sha256(b'rollout-content-v2\n')
    prefixes = {}
    for row in ordered:
        if row.get('choice', -1) < 0:
            continue
        history = []
        for slot in row['_history']:
            if id(slot) not in prefixes:
                prefixes[id(slot)] = content_hash(slot)
            history.append(prefixes[id(slot)])
        payload = {key: value for key, value in row.items() if key not in ('_history', '_sequence_complete')}
        payload['_history'] = history
        digest.update(content_hash(payload).encode())
        digest.update(b'\n')
    return digest.hexdigest()
