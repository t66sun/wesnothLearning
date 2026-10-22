"""Compact numeric blocks for raw shard lines.

A long 2v2 decision serializes to ~1.5 MiB of Python objects while its
observations are only ~100-140 KiB of float32: JSON lines box every number and
pay for hundreds of thousands of individual float objects per game. This module
keeps labels, provenance and strings as JSON metadata and moves the numeric
tensors into one float32 block per row, so a reader gets numpy views over a
single buffer instead of boxed lists.

The line format is ``{"v": 2, "m": <metadata>, "b": <base64 float32 block>}``.
Numeric leaves are replaced by ``{"$": [offset, count], "s": shape}`` markers.
Readers accept unpacked JSON lines as well, so old shards stay readable.
"""
import base64
import json

import numpy as np

VERSION = 2
MARK = 'v'
BLOCK = '$'
SHAPE = 's'
DTYPE = np.float32
PACK_MIN_FLOATS = 4096


def _number(value):
    # Floats only: integer labels (turn, side, decision, type_index, x, y) must
    # come back as Python ints, because consumers test ``isinstance(..., int)``.
    return isinstance(value, (float, np.floating)) and not isinstance(value, (bool, np.bool_))


def _element(value):
    # Inside a vector, integers are plain numbers too: recorders emit ``0`` for
    # integral features, and refusing those would box every float beside them.
    # Scalars outside a vector keep their type, so labels stay Python ints.
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, (bool, np.bool_))


def _flat(value):
    """Flatten uniform numeric nesting into one array, or None when not numeric."""
    if isinstance(value, np.ndarray):
        if value.dtype.kind not in 'uf':
            return None
        return value.reshape(-1).astype(DTYPE, copy=False), [int(v) for v in value.shape]
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        if all(_element(x) for x in value):
            return np.asarray(value, dtype=DTYPE), [len(value)]
        parts = [_flat(x) for x in value]
        if any(part is None for part in parts):
            return None
        shapes = {tuple(part[1]) for part in parts}
        if len(shapes) != 1:
            return None
        return np.concatenate([part[0] for part in parts]), [len(value)] + parts[0][1]
    return None


def pack_line(row):
    """Serialize one record; numeric leaves become views into a float32 block."""
    blocks = []
    total = 0

    def walk(value):
        nonlocal total
        flat = _flat(value)
        if flat is not None:
            data, shape = flat
            marker = {BLOCK: [total, int(data.size)]}
            if len(shape) > 1:
                marker[SHAPE] = shape
            total += int(data.size)
            blocks.append(data)
            return marker
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [walk(v) for v in value]
        if isinstance(value, np.ndarray):
            return [walk(v) for v in value.tolist()]
        if isinstance(value, np.generic):
            return value.item()
        return value

    metadata = walk(row)
    payload = {MARK: VERSION, 'm': metadata}
    if blocks:
        payload['b'] = base64.b64encode(np.concatenate(blocks).tobytes()).decode('ascii')
    text = json.dumps(payload, separators=(',', ':'), allow_nan=False)
    # Packing costs ~0.3 bytes more per float on disk (base64 is 5.3 bytes per
    # float, short JSON decimals are ~5.0) but saves ~12x in memory, because a
    # boxed Python float costs 24 bytes plus a list pointer. Memory is what
    # killed the 18-hour run, so every large row is packed unconditionally.
    return text if total >= PACK_MIN_FLOATS else json_or_text(row, text)


def _decode(meta, buffer):
    if isinstance(meta, dict):
        if BLOCK in meta:
            offset, count = meta[BLOCK]
            piece = buffer[offset:offset + count]
            shape = meta.get(SHAPE)
            return piece.reshape(shape) if shape else piece
        return {k: _decode(v, buffer) for k, v in meta.items()}
    if isinstance(meta, list):
        return [_decode(v, buffer) for v in meta]
    return meta


def unpack_line(line, plain=False):
    """Return ``(row, numeric_bytes)`` for one shard line.

    With ``plain`` every numeric block is materialized as a Python list, which
    keeps audit and export consumers byte-identical to the legacy reader.
    """
    if isinstance(line, bytes):
        line = line.decode('utf-8')
    if not line.startswith('{"v":'):
        return json.loads(line), 0
    payload = json.loads(line)
    if payload.get(MARK) != VERSION:
        raise ValueError('unsupported packed row version')
    raw = base64.b64decode(payload.get('b', ''))
    buffer = np.frombuffer(raw, dtype=DTYPE)
    row = _decode(payload['m'], buffer)
    if plain:
        row = plain_row(row)
    return row, len(raw)


def row_meta(line):
    """Metadata of one shard line without decoding numeric blocks."""
    if isinstance(line, bytes):
        line = line.decode('utf-8')
    if not line.startswith('{"v":'):
        return json.loads(line)
    payload = json.loads(line)
    if payload.get(MARK) != VERSION:
        raise ValueError('unsupported packed row version')
    return payload['m']


def json_or_text(row, text):
    """Fallback line for small rows: plain JSON unless it cannot serialize."""
    try:
        return json.dumps(row, separators=(',', ':'), allow_nan=False)
    except TypeError:
        return text


def plain_row(row):
    """Materialize numpy blocks as nested lists for JSON and Lua consumers."""
    if isinstance(row, np.ndarray):
        return row.tolist()
    if isinstance(row, dict):
        return {k: plain_row(v) for k, v in row.items()}
    if isinstance(row, list):
        return [plain_row(v) for v in row]
    return row


def _board_count(board):
    count = 1
    for dimension in np.shape(board):
        count *= int(dimension)
    return count


def float_count(row):
    """Count numeric leaves of one row without materializing them."""
    total = len(row['global']) + sum(len(opponent) for opponent in row['opponents'])
    spatial = row['spatial']
    total += _board_count(spatial['board'])
    for entity in spatial['entities']:
        total += len(entity['features'])
    for candidate in row['candidates']:
        total += len(candidate['features']) + len(candidate.get('local', ())) + len(candidate.get('geometry', ()))
        for key in ('actor', 'target'):
            entity = candidate.get(key)
            if entity is not None:
                total += len(entity['features'])
    return total


def memory_float_count(row):
    """Count numeric leaves of one history slot (no candidates, no labels)."""
    spatial = row['spatial']
    total = len(row['global']) + sum(len(opponent) for opponent in row['opponents'])
    total += _board_count(spatial['board'])
    for entity in spatial['entities']:
        total += len(entity['features'])
    return total
