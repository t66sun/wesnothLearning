"""Audit actual checkpoint weights over complete recorded policy sequences."""
import copy
import gzip
import math
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from typing import NamedTuple

import torch

from .common import ROOT
from .model import batch
from .rowpack import row_meta
from .sequences import attach_histories, read_raw_shards, sequence_key
from .weight_export import weight_source


class _Measurement(NamedTuple):
    full_budget: bool
    turns: int
    max_error: float


def _checked_error(fmt, measurements):
    if not any(m.full_budget for m in measurements):
        raise ValueError('numerical audit requires a real sequence with at least 37 retained candidates')
    if sum(m.turns for m in measurements) < 2:
        raise ValueError('numerical audit requires continuous turn memory')
    error = max(m.max_error for m in measurements)
    if not math.isfinite(error) or error > 1e-5:
        raise ValueError(f'{fmt}: Python/Lua error {error} exceeds 1e-5')
    return error


class _ParityAudit:
    def __init__(self, model):
        from lupa import LuaRuntime
        from .export import lua_parameters
        self.model = copy.deepcopy(model).cpu().double().eval()
        self.lua = lua = LuaRuntime(unpack_returned_tuples=True)

        def require(path):
            filename = Path(path).name
            if filename != 'relational.lua':
                raise ValueError('unexpected numerical audit require: ' + path)
            return lua.execute((ROOT / 'lua' / filename).read_text(encoding='utf-8'))

        lua.globals().wesnoth = lua.table_from({'require': require})
        self.network = lua.execute((ROOT / 'lua/network.lua').read_text(encoding='utf-8'))
        self.weights = lua.execute(weight_source(lua_parameters(model)))
        self.relational = require('relational.lua')

    @torch.no_grad()
    def measure(self, records):
        if not all('_history' in row for row in records):
            records = attach_histories(records)
        lua = self.lua
        def table(value):
            return lua.table_from(value, recursive=True)
        history_cache = {}
        memories = {}
        turns = set()
        error = 0.
        for row in records:
            key = sequence_key(row)
            memory = memories.setdefault(key, lua.table())
            turns.add((key, row['turn']))
            logits, value = self.model(*batch([row], dtype=torch.float64, history_cache=history_cache))
            scores, v, _ = self.network.forward(self.weights, table(row['global']),
                table(row['opponents']), table(row['candidates']), table(row['spatial']), memory, row['turn'])
            candidate_error = max((abs(logits[0, i].item() - scores[i + 1]) for i in range(len(row['candidates']))),
                                  default=0.0)
            error = max(error, abs(value.item() - v), candidate_error)
            if row.get('committed', True) and memory.turn != row['turn']:
                write = row.get('memory_write', row)
                _, _, pending = self.network.forward(self.weights, table(write['global']),
                    table(write['opponents']), lua.table(), table(write['spatial']), memory, row['turn'])
                self.relational.commit(memory, pending)
        return _Measurement(any(len(r['candidates']) >= 37 for r in records), len(turns), error)

    def measure_files(self, paths):
        return self.measure(read_raw_shards(paths, self.model.format_name))


def verify_numerics(model, records):
    return _checked_error(model.format_name, [_ParityAudit(model).measure(records)])


def _sequence_file_groups(paths):
    """Keep shards sharing any sequence together; stable path order breaks ties within a sequence."""
    parents = list(range(len(paths)))

    def root(index):
        while index != parents[index]:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    owners = {}
    for index, path in enumerate(paths):
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            metadata = (row_meta(line) for line in stream if line.strip())
            keys = {sequence_key(row) for row in metadata if not row.get('faults')}
        for key in keys:
            previous = owners.setdefault(key, index)
            parents[root(index)] = root(previous)
    groups = defaultdict(list)
    for index, path in enumerate(paths):
        groups[root(index)].append(path)
    return sorted(groups.values(), key=lambda group: sum(Path(path).stat().st_size for path in group), reverse=True)


_worker_audit = None


def _start_worker(model):
    global _worker_audit
    torch.set_num_threads(1)
    _worker_audit = _ParityAudit(model)


def _measure_group(paths):
    return _worker_audit.measure_files(paths)


def verify_shard_numerics(model, paths, workers=1):
    if workers < 1:
        raise ValueError('audit workers must be positive')
    if not paths:
        raise ValueError('delivery export requires actual current-schema sequence parity data for ' + model.format_name)
    groups = _sequence_file_groups(paths)
    if workers == 1 or len(groups) == 1:
        audit = _ParityAudit(model)
        results = [audit.measure_files(group) for group in groups]
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(groups)), mp_context=get_context('spawn'),
                                 initializer=_start_worker, initargs=(model,)) as pool:
            results = list(pool.map(_measure_group, groups))
    return _checked_error(model.format_name, results)
