"""Indexed raw sequence blocks and replay prefixes; never persist hidden states.

One compressed block contains one complete game/side/source/engine sequence.
SQLite indexes metadata without decoding observations. An instance keeps a bounded
decoded-block cache across minibatches. Pass complete sequences to attach_histories;
slice its result, rather than attaching history to a random suffix.
"""
from collections import OrderedDict, defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import struct
import zlib

from .data import split
from .rowpack import unpack_line, plain_row


def sequence_key(row):
    return (row.get('format'), row.get('source'), row.get('engine_id', row.get('engine')),
            row.get('game_family'), row.get('game_id'), row.get('side'))


def _raw(row):
    return {k: v for k, v in row.items() if k not in ('_history', '_sequence_complete')}


def _memory_row(row):
    row = row.get('memory_write', row)
    return {k: row[k] for k in ('global', 'opponents', 'spatial', 'turn') if k in row} | {'candidates': []}


def _validate_raw(row, format_name=None):
    from .data import validate_record
    from .features import VERSION
    if row.get('choice', -1) >= 0:
        validate_record(row, format_name)
    else:
        # Uncovered teacher intents still committed and advanced online memory.
        # They are raw context, never supervised labels.
        if row.get('schema') != VERSION or any(k not in row for k in
                ('global', 'opponents', 'spatial', 'turn', 'game_family', 'game_id', 'source', 'format', 'side')):
            raise ValueError('uncovered raw record lacks current-schema context/provenance')
        if format_name is not None and row['format'] != format_name:
            raise ValueError('cross-format sample rejected')


def attach_histories(records, prefixes=None):
    """Attach raw committed-turn prefixes in original order, using current weights later.

    prefixes maps sequence_key to raw first-committed-decision observations. Callers
    providing a suffix must supply its prefix; a marked incomplete sequence is
    rejected otherwise. No cached embedding or old-policy hidden state is reused.
    """
    histories = {key: [_memory_row(r) for r in rows] for key, rows in (prefixes or {}).items()}
    last_turn = {}
    result = []
    for row in records:
        key = sequence_key(row)
        if key not in histories:
            supplied = row.get('_history')
            if supplied is None and (row.get('_sequence_complete') is False or row.get('sequence_start') is False
                    or (row['turn'] > 1 and not row.get('sequence_start', False))):
                raise ValueError('sequence suffix requires its complete raw prefix')
            histories[key] = [_memory_row(r) for r in supplied] if supplied is not None else []
        history = histories[key]
        turn = row['turn']
        previous = last_turn.get(key, history[-1]['turn'] if history else -1)
        if turn < previous:
            raise ValueError('sequence must preserve chronological turn order')
        current = dict(row, _history=list(history))
        result.append(current)
        # A training record normally denotes a successful commit. Failed attempts
        # and teacher queries explicitly opt out, exactly like online inference.
        if row.get('committed', True):
            if not history or history[-1]['turn'] != turn:
                history.append(_memory_row(row))
        last_turn[key] = turn
    return result


def training_windows(records, rng=None, turns=8):
    """Group once per training batch, then sample whole own-turn windows.

    Already attached prefixes are preserved, including suffixes read under a
    record budget. The training loop must not call this after sampling single
    decisions; doing so would remove chronology before the window is built.
    """
    if turns < 1:
        raise ValueError('window turns must be positive')
    records = list(records)
    if not all('_history' in r for r in records):
        records = attach_histories(records)
    groups = defaultdict(list)
    for row in records:
        groups[sequence_key(row)].append(row)
    windows = []
    for rows in groups.values():
        turn_ids = list(dict.fromkeys(r['turn'] for r in rows))
        if turn_ids != sorted(turn_ids):
            raise ValueError('window source is not chronologically ordered')
        for start in range(0, len(turn_ids), turns):
            chosen = set(turn_ids[start:start + turns])
            window = [r for r in rows if r['turn'] in chosen and r.get('choice', -1) >= 0]
            if window:
                windows.append(window)
    if rng is not None:
        rng.shuffle(windows)
    return windows


class IndexedSequenceStore:
    def __init__(self, root, cache_bytes=64 << 20):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.root / 'sequences.sqlite3')
        self.connection.execute('''CREATE TABLE IF NOT EXISTS sequences (
            id TEXT PRIMARY KEY, format TEXT, source TEXT, engine TEXT,
            partition TEXT, family TEXT, game_id TEXT, side INTEGER,
            decisions INTEGER, turns INTEGER, payload BLOB NOT NULL)''')
        self.connection.execute('CREATE INDEX IF NOT EXISTS selection ON sequences(format, partition, source, engine, family)')
        self.cache_bytes = max(1, cache_bytes)
        self.cached = 0
        self.cache = OrderedDict()

    def close(self):
        self.connection.close()
        self.cache.clear()
        self.cached = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def write(self, records):
        """Atomically insert complete sequences, preserving decision order per side."""
        groups = {}
        with self.connection:
            for row in records:
                _validate_raw(row)
                if not row.get('engine_id', row.get('engine')):
                    raise ValueError('sequence requires explicit engine provenance')
                if row.get('_sequence_complete') is False or row.get('sequence_start') is False:
                    raise ValueError('cannot store an incomplete sequence without raw prefix')
                if row.get('split', split(row['game_family'])) != split(row['game_family']):
                    raise ValueError('family crosses partitions')
                key = sequence_key(row)
                raw = _raw(row)
                if key not in groups:
                    attach_histories([raw])  # retain the original complete-prefix check
                    groups[key] = dict(compressor=zlib.compressobj(), chunks=[], count=0,
                                       decisions=0, turns=set(), last_turn=row['turn'])
                group = groups[key]
                if row['turn'] < group['last_turn']:
                    raise ValueError('sequence must preserve chronological turn order')
                group['last_turn'] = row['turn']
                compressor = group['compressor']
                group['chunks'].append(compressor.compress(b',' if group['count'] else b'['))
                encoded = json.dumps(plain_row(raw), separators=(',', ':'), allow_nan=False).encode()
                group['chunks'].append(compressor.compress(encoded))
                group['count'] += 1
                group['decisions'] += row.get('choice', -1) >= 0
                group['turns'].add(row['turn'])
            for key, group in groups.items():
                fmt, source, engine, family, game_id, side = key
                identity = hashlib.sha256(json.dumps(key, separators=(',', ':')).encode()).hexdigest()
                compressor = group['compressor']
                group['chunks'].append(compressor.compress(b']'))
                group['chunks'].append(compressor.flush())
                payload = b''.join(group['chunks'])
                existing = self.connection.execute('SELECT payload FROM sequences WHERE id=?', (identity,)).fetchone()
                if existing is not None:
                    if existing[0] != payload:
                        raise ValueError('sequence identity already exists with different raw content')
                    continue
                self.connection.execute('INSERT INTO sequences VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (identity, fmt, source, engine, split(family), family, game_id, side,
                     group['decisions'], len(group['turns']), payload))
        return sum(group['count'] for group in groups.values())

    def index(self, partition=None, format_name=None, source=None, engine=None):
        filters = dict(partition=partition, format=format_name, source=source, engine=engine)
        selected = {k: v for k, v in filters.items() if v is not None}
        where = ' WHERE ' + ' AND '.join(k + '=?' for k in selected) if selected else ''
        query = 'SELECT id,format,source,engine,partition,family,game_id,side,decisions,turns FROM sequences' + where + ' ORDER BY id'
        names = ('id', 'format', 'source', 'engine', 'partition', 'family', 'game_id', 'side', 'decisions', 'turns')
        return [dict(zip(names, values)) for values in self.connection.execute(query, tuple(selected.values()))]

    def _decode(self, identity):
        if identity not in self.cache:
            value = self.connection.execute('SELECT payload FROM sequences WHERE id=?', (identity,)).fetchone()
            if value is None:
                raise KeyError(identity)
            rows = json.loads(zlib.decompress(value[0]))
            self.cache[identity] = (rows, len(value[0]))
            self.cached += len(value[0])
            # Bound the cache by decoded bytes: one long game is far larger than
            # the block count assumed, and retaining it into training is fatal.
            while len(self.cache) > 1 and self.cached > self.cache_bytes:
                _, (_, size) = self.cache.popitem(last=False)
                self.cached -= size
        self.cache.move_to_end(identity)
        return self.cache[identity][0]

    def iter_records(self, **filters):
        """Stream complete validation sequences in indexed blocks, with raw prefixes."""
        for item in self.index(**filters):
            yield from (r for r in attach_histories(self._decode(item['id'])) if r.get('choice', -1) >= 0)

    def iter_windows(self, turns=8, **filters):
        if turns < 1:
            raise ValueError('window turns must be positive')
        for item in self.index(**filters):
            rows = attach_histories(self._decode(item['id']))
            turn_ids = list(dict.fromkeys(r['turn'] for r in rows))
            for offset in range(0, len(turn_ids), turns):
                selected = set(turn_ids[offset:offset + turns])
                window = [r for r in rows if r['turn'] in selected and r.get('choice', -1) >= 0]
                if window:
                    yield window

    def sample_windows(self, count, turns=8, seed=None, **filters):
        """Choose provenance bucket, family, sequence, then an eight-own-turn window.

        Source/engine quotas can be set by separate calls; uniform buckets avoid
        weighting long games more heavily. Every suffix retains its real prefix.
        """
        if turns < 1 or count < 1:
            raise ValueError('count and turns must be positive')
        rng = random.Random(seed)
        buckets = defaultdict(lambda: defaultdict(list))
        for item in self.index(**filters):
            if item['decisions']:
                buckets[(item['format'], item['source'], item['engine'])][item['family']].append(item)
        if not buckets:
            raise ValueError('no sequences match selection')
        result = []
        for _ in range(count):
            families = buckets[rng.choice(sorted(buckets))]
            item = rng.choice(families[rng.choice(sorted(families))])
            rows = attach_histories(self._decode(item['id']))
            turn_ids = list(dict.fromkeys(r['turn'] for r in rows))
            eligible = [i for i, turn in enumerate(turn_ids) if any(r['turn'] == turn and r.get('choice', -1) >= 0 for r in rows)]
            start = rng.choice(eligible)
            selected = set(turn_ids[start:start + turns])
            window = [r for r in rows if r['turn'] in selected and r.get('choice', -1) >= 0]
            if window:
                result.append(window)
        return result


GZ_BUDGET = 96 << 20
RETAIN_BUDGET = 768 << 20
FAMILIES_PER_32_ROWS = 32
WINDOW_TURNS = 8


ITEM_BYTES = 640


def _row_bytes(row):
    """Approximate live bytes of one decision row without materializing extras."""
    import numpy as np
    from .rowpack import float_count
    items = len(row['candidates']) + len(row['spatial']['entities'])
    # Packed rows keep one float32 block; legacy JSON rows box every number in a
    # 24-byte float plus a pointer, which is why the estimate differs by 10x.
    weight = 4 if isinstance(row['global'], np.ndarray) else 40
    return weight * float_count(row) + ITEM_BYTES * items


def _prefix_bytes(sequence):
    """Live prefix cost of one game, charged once per game rather than per window.

    Every decision keeps one shared history row, so a window referencing a long
    prefix must not be charged its full prefix again.
    """
    sample = sequence[0]
    row = _memory_row(sample)
    import numpy as np
    from .rowpack import memory_float_count
    weight = 4 if isinstance(row['global'], np.ndarray) else 40
    items = 1 + len(row['spatial']['entities'])
    return len(sequence) * (weight * memory_float_count(row) + ITEM_BYTES * items)


def _family_windows(files, partition, format_name, turns):
    """Decode one game family and return its supervised windows and prefix cost.

    Raw decision rows are dropped once their sequence is windowed; only the
    arrays referenced by a returned window stay alive.
    """
    groups = defaultdict(list)
    for path, stat in files:
        for row in _iter_rows(str(path)):
            if row.get('faults') or (partition is not None and row['split'] != partition):
                continue
            _validate_raw(row, format_name)
            groups[sequence_key(row)].append(row)
    windows = []
    prefix = 0
    for rows in groups.values():
        sequence = [r for r in attach_histories(rows) if r.get('choice', -1) >= 0]
        if sequence:
            prefix += _prefix_bytes(sequence)
            windows.extend(training_windows(sequence, turns=turns))
    return windows, prefix


@lru_cache(maxsize=8192)
def _payload_bytes(path, size, modified):
    """Uncompressed payload size from the gzip trailer; the body is never read."""
    if size < 8:
        return size
    with open(path, 'rb') as stream:
        stream.seek(-4, 2)
        return int(struct.unpack('<I', stream.read(4))[0])


def _candidate_plan(indexed, limit, rng):
    """Shuffle families inside each provenance bucket, then interleave buckets.

    The first tier keeps the historical pool size of at most ``limit // 32``
    families per bucket; the remaining families follow only when that pool
    cannot fill the request. Round-robin interleaving stops one bucket from
    consuming the whole read before the others contribute.
    """
    keys = sorted(indexed, key=str)
    orders = {}
    for key in keys:
        families = list(indexed[key])
        rng.shuffle(families)
        orders[key] = families
    depth = max((len(families) for families in orders.values()), default=0)
    first = max(1, limit // max(1, FAMILIES_PER_32_ROWS * len(keys)))
    plan = []
    for start, stop in ((0, min(first, depth)), (min(first, depth), depth)):
        for position in range(start, stop):
            for key in keys:
                families = orders[key]
                if position < len(families):
                    plan.append((key, families[position], indexed[key][families[position]]))
    return plan


def _water_fill(capacities, requested):
    """Equal share per family, then hand leftover capacity to whoever has room."""
    allocation = [0] * len(capacities)
    remaining = requested
    if not capacities or remaining <= 0:
        return allocation
    share = -(-requested // len(capacities))
    for index in range(len(capacities)):
        take = min(capacities[index], share, remaining)
        allocation[index] = take
        remaining -= take
        if remaining <= 0:
            return allocation
    while remaining > 0:
        active = [index for index, capacity in enumerate(capacities) if allocation[index] < capacity]
        if not active:
            break
        give = max(1, remaining // len(active))
        for index in active:
            take = min(capacities[index] - allocation[index], give, remaining)
            allocation[index] += take
            remaining -= take
            if remaining <= 0:
                break
    return allocation


def _fair_total(capacities, target):
    """Rows a bucket can serve if every family gets an equal share of the target."""
    if not capacities or target <= 0:
        return 0
    share = -(-target // len(capacities))
    return sum(min(capacity, share) for capacity in capacities)


def _bucket_targets(buckets, limit):
    """Spread the request over the indexed buckets before anything is decoded.

    Every bucket owns its target rows, so a bucket that runs out of legal data
    reports a deficit instead of silently borrowing another bucket's rows.
    """
    base, extra = divmod(limit, len(buckets))
    return {key: base + (1 if index < extra else 0) for index, key in enumerate(buckets)}


def _ordered_rows(windows):
    """Restore chronology per sequence while keeping the sampling decision fixed."""
    ordered = defaultdict(list)
    for window in windows:
        for row in window:
            ordered[sequence_key(row)].append(row)
    return [row for rows in ordered.values()
            for row in sorted(rows, key=lambda r: (r['turn'], r.get('decision', 0)))]


def _read_all(indexed, partition, format_name, turns, seed, stats):
    """Full read: every indexed family is decoded, so nothing is truncated."""
    rng = random.Random(seed)
    selected = []
    for key in sorted(indexed, key=str):
        families = list(indexed[key])
        rng.shuffle(families)
        selected.extend((key, family, indexed[key][family]) for family in families)
    rng.shuffle(selected)
    kept = []
    used = retained = decoded = 0
    for _, _, files in selected:
        cost = sum(stat.st_size for _, stat in files)
        used += cost
        decoded += 1
        windows, prefix = _family_windows(files, partition, format_name, turns)
        rng.shuffle(windows)
        if not windows:
            continue
        retained += prefix + sum(_row_bytes(row) for window in windows for row in window)
        kept.extend(windows)
    rows = _ordered_rows(kept)
    if stats is not None:
        stats.update(requested=None, rows=len(rows), families=decoded, selected=len(selected),
                     families_decoded=decoded, families_selected=len(selected),
                     gz_bytes=used, retained_bytes=retained, deficit=0,
                     # A full read has no request to miss, so it never reports a
                     # budget reason; the reason stays inside the bounded set.
                     stop_reason='window_limit')
    return rows


def _read_bounded(indexed, partition, format_name, turns, limit, seed, gz_budget, retain_budget, stats):
    """Fair first allocation then backfill from families already decoded."""
    rng = random.Random(seed)
    plan = _candidate_plan(indexed, limit, rng)
    admitted = []
    groups = {}
    buckets = sorted(indexed, key=str)
    targets = _bucket_targets(buckets, limit)
    pending = {key for key in buckets if targets[key] > 0}
    gz_used = charged = decoded = 0
    blocked_gz = blocked_retain = 0

    def allocation():
        values = [0] * len(admitted)
        for key in buckets:
            indexes = groups.get(key, [])
            if indexes:
                shares = _water_fill([admitted[index]['capacity'] for index in indexes], targets[key])
                for index, share in zip(indexes, shares):
                    values[index] = share
        return values

    for key, family, files in plan:
        # A bucket stops at its own target; the other buckets keep their turn,
        # so one bucket cannot consume the request before the rest contribute.
        if not pending:
            break
        if key not in pending:
            continue
        cost = sum(stat.st_size for _, stat in files)
        # Compressed admission is decided from metadata; a family that does not
        # fit is skipped instead of being granted an unrecorded exception.
        if gz_used + cost > gz_budget:
            blocked_gz += 1
            continue
        estimate = sum(_payload_bytes(str(path), stat.st_size, stat.st_mtime_ns) for path, stat in files)
        if charged + estimate > retain_budget:
            blocked_retain += 1
            continue
        windows, prefix = _family_windows(files, partition, format_name, turns)
        decoded += 1
        gz_used += cost
        rng.shuffle(windows)
        kept = []
        size = 0
        for window in windows:
            row_cost = sum(_row_bytes(row) for row in window)
            if charged + (prefix if not kept else 0) + size + row_cost > retain_budget:
                # Only supervised targets are shortened; the raw prefix and the
                # windows already retained stay exactly as decoded.
                blocked_retain += 1
                break
            kept.append(window)
            size += row_cost
        if not kept:
            continue
        charged += prefix + size
        capacity = sum(len(window) for window in kept)
        groups.setdefault(key, []).append(len(admitted))
        admitted.append(dict(windows=kept, prefix=prefix, capacity=capacity))
        if _fair_total([admitted[index]['capacity'] for index in groups[key]], targets[key]) >= targets[key]:
            pending.discard(key)
    selected = []
    retained = 0
    for entry, share in zip(admitted, allocation()):
        taken = []
        remaining = share
        for window in entry['windows']:
            if remaining <= 0:
                break
            piece = window[:remaining]
            taken.append(piece)
            remaining -= len(piece)
        if taken:
            retained += entry['prefix'] + sum(_row_bytes(row) for piece in taken for row in piece)
            selected.extend(taken)
    rows = _ordered_rows(selected)
    deficit = limit - len(rows)
    if not deficit:
        reason = 'window_limit'
    elif blocked_gz:
        reason = 'gz_budget'
    elif blocked_retain:
        reason = 'retain_budget'
    else:
        reason = 'insufficient_data'
    if stats is not None:
        stats.update(requested=limit, rows=len(rows), families=decoded, selected=len(plan),
                     families_decoded=decoded, families_selected=len(plan),
                     gz_bytes=gz_used, retained_bytes=retained, deficit=deficit, stop_reason=reason)
    return rows


def read_shards(paths, partition=None, limit=None, seed=19, format_name=None, turns=WINDOW_TURNS,
                gz_budget=GZ_BUDGET, retain_budget=RETAIN_BUDGET, stats=None):
    """Read complete games under explicit compressed and retained-byte budgets.

    limit bounds returned supervised rows, never their raw prefix: a returned
    window keeps every earlier decision of its game. Bounded reads admit
    families from cached shard metadata, decode each admitted family once, give
    every admitted family a fair target-row share and then backfill unused
    capacity from those already decoded families. A full read (``limit=None``)
    keeps the historical semantics and decodes everything.
    """
    from .data import _shard_identity
    if limit is not None and limit < 1:
        raise ValueError('record limit must be positive')
    indexed = defaultdict(lambda: defaultdict(list))
    for value in paths:
        path = Path(value).resolve()
        stat = path.stat()
        identity = _shard_identity(str(path), stat.st_size, stat.st_mtime_ns)
        if identity is None:
            continue
        fmt, source, part, family, engine = identity
        if partition is not None and part != partition:
            continue
        if format_name is not None and fmt != format_name:
            raise ValueError('cross-format sample rejected')
        indexed[(fmt, source, part, engine)][family].append((path, stat))
    if limit is None:
        return _read_all(indexed, partition, format_name, turns, seed, stats)
    return _read_bounded(indexed, partition, format_name, turns, limit, seed,
                         gz_budget, retain_budget, stats)


def read_raw_shards(paths,format_name=None):
    """Full audit stream, including uncovered teacher intents and their memory writes."""
    from .rowpack import plain_row
    groups=defaultdict(list)
    for value in paths:
        for row in _iter_rows(str(Path(value).resolve())):
            if row.get('faults'): continue
            _validate_raw(row,format_name);groups[sequence_key(row)].append(plain_row(row))
    result=[]
    for rows in groups.values():
        rows.sort(key=lambda r:(r['turn'],r.get('decision',r.get('action_index',0))))
        result.extend(attach_histories(rows))
    return result


def _iter_rows(path):
    """Yield packed shard rows one line at a time; never cache whole games."""
    import gzip
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield unpack_line(line)[0]
