"""Shared preparation for the BC and PPO update loops.

This module only prepares validated training rows and the CPU/GPU microbatch
size. Objectives, sampling and stopping live in ``bc.py`` and ``ppo.py``.
"""
import hashlib
import json
from itertools import count
import struct

import numpy as np

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
    from .tasks import LEGACY_TASK
    if len({r.get('task_id', LEGACY_TASK) for rows in (records, bc_records or []) for r in rows}) > 1:
        raise ValueError('training batch mixes tasks')
    if len({r['schema'] for rows in (records,bc_records or []) for r in rows})>1:
        raise ValueError('training batch mixes row schemas')
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


def _vector_content_hash(payload, encoder):
    """Hash canonical JSON metadata and the float vectors it references."""
    vectors = hashlib.sha256()
    positions = count()

    def replace(value):
        position = next(positions)
        if isinstance(value, dict):
            return {key: replace(value[key]) for key in sorted(value)}
        if isinstance(value, np.ndarray):
            if value.ndim > 1:
                return [replace(part) for part in value]
            if value.ndim == 1 and value.size and value.dtype.kind == 'f' and value.dtype.itemsize <= 8:
                vector = np.ascontiguousarray(value, dtype='<f8')
                if not np.isfinite(vector).all():
                    raise ValueError('Out of range float values are not JSON compliant')
                # Preorder position binds a vector even when its JSON placeholder
                # is beside an ordinary null. The length frames each byte block.
                vectors.update(struct.pack('>QQ', position, vector.size))
                vectors.update(memoryview(vector).cast('B'))
                return None
            value = value.tolist()
        if isinstance(value, (list, tuple)):
            return [replace(part) for part in value]
        return value

    metadata = encoder.encode(replace(payload)).encode()
    return hashlib.sha256(metadata + b'\0' + vectors.digest()).hexdigest()


def rollout_identity(rows, *, version=2):
    """Bind target identity, training content and legal raw recurrent prefixes.

    Hash one row at a time; shared prefix slots are hashed once per call. Numeric
    vector lists and arrays use the existing float64 compaction convention.
    Version 2 remains available for saved pending batches.
    """
    if version not in (2, 3):
        raise ValueError('unknown rollout identity version')
    from .rowpack import compact_row
    encoder = json.JSONEncoder(sort_keys=True, separators=(',', ':'), allow_nan=False,
                               default=lambda value: value.tolist())
    def content_hash(payload):
        compact = compact_row(payload)
        if version == 3:
            return _vector_content_hash(compact, encoder)
        return hashlib.sha256(encoder.encode(compact).encode()).hexdigest()

    ordered = sorted(rows, key=lambda r: (str(r.get('format')), str(r.get('source')),
        str(r.get('engine_id')), str(r.get('game_family')), str(r.get('game_id')),
        str(r.get('side')), int(r['turn']), int(r.get('decision', r.get('action_index', 0)))))
    if not all('_history' in row for row in ordered):
        ordered = attach_histories(ordered)
    digest = hashlib.sha256(f'rollout-content-v{version}\n'.encode())
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
    return 'v3:' + digest.hexdigest() if version == 3 else digest.hexdigest()
