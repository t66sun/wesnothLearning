"""Audit actual checkpoint weights over complete recorded policy sequences."""
import copy
import gzip
import math
import pickle
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


def _combine(measurements):
    return _Measurement(any(m.full_budget for m in measurements), sum(m.turns for m in measurements),
                        max((m.max_error for m in measurements), default=0.))


def _checked_error(fmt, measurements):
    total = _combine(measurements)
    if not total.full_budget:
        raise ValueError('numerical audit requires a real sequence with at least 37 retained candidates')
    if total.turns < 2:
        raise ValueError('numerical audit requires continuous turn memory')
    error = total.max_error
    if not math.isfinite(error) or error > 1e-5:
        raise ValueError(f'{fmt}: Python/Lua error {error} exceeds 1e-5')
    return error


def _game_side(row):
    fmt, _, engine, family, game, side = sequence_key(row)
    return fmt, engine, family, game, side


def _same_inputs(policy, dagger):
    # read_raw_shards has validated and ordered both sequences. Starting at the
    # same prefix, equal commits and writes reconstruct every subsequent prefix.
    if len(policy) != len(dagger) or pickle.dumps(policy[0]['_history']) != pickle.dumps(dagger[0]['_history']):
        return False
    fields = ('turn', 'decision', 'action_index', 'side', 'committed', 'global', 'opponents',
              'candidates', 'spatial', 'memory_write')
    def encoded(row):
        return pickle.dumps({k: row[k] for k in fields if k in row}, protocol=5)
    return all(encoded(a) == encoded(b) for a, b in zip(policy, dagger))


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
            # Repeated feature lists must materialize at each occurrence, as in a Lua literal.
            if isinstance(value, dict):
                return lua.table_from({str(k): table(v) for k, v in value.items()})
            if isinstance(value, (list, tuple)):
                return lua.table_from([table(v) for v in value])
            return value
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
        games = defaultdict(lambda: defaultdict(list))
        for row in read_raw_shards(paths, self.model.format_name):
            games[_game_side(row)][row['source']].append(row)
        results = []
        for sources in games.values():
            policy = sources.pop('policy', None)
            if policy:
                policy_result = self.measure(policy)
                results.append(policy_result)
            for source, rows in sources.items():
                if (policy and source == 'astra' and all(r.get('data_pool') == 'dagger' for r in rows)
                        and _same_inputs(policy, rows)):
                    results.append(policy_result)
                else:
                    results.append(self.measure(rows))
        return _combine(results)


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
            keys = {_game_side(row) for row in metadata if not row.get('faults')}
        for key in keys:
            previous = owners.setdefault(key, index)
            parents[root(index)] = root(previous)
    groups = defaultdict(list)
    for index, path in enumerate(paths):
        groups[root(index)].append(path)
    return list(groups.values())


_worker_models = {}
_worker_audits = {}


def _start_worker(models):
    global _worker_models
    torch.set_num_threads(1)
    _worker_models = models


def _measure_group(task):
    fmt, paths = task
    if fmt not in _worker_audits:
        _worker_audits[fmt] = _ParityAudit(_worker_models[fmt])
    return _worker_audits[fmt].measure_files(paths)


def verify_shard_numerics(models, audit_paths, workers=1):
    if workers < 1:
        raise ValueError('audit workers must be positive')
    groups = {}
    for fmt in models:
        if not audit_paths.get(fmt):
            raise ValueError('delivery export requires actual current-schema sequence parity data for ' + fmt)
        groups[fmt] = _sequence_file_groups(audit_paths[fmt])
    tasks = [(fmt, paths) for fmt in models for paths in groups[fmt]]
    results = defaultdict(list)
    if workers == 1 or len(tasks) == 1:
        for fmt, model in models.items():
            audit = _ParityAudit(model)
            results[fmt] = [audit.measure_files(paths) for paths in groups[fmt]]
    else:
        tasks.sort(key=lambda task: sum(Path(path).stat().st_size for path in task[1]), reverse=True)
        with ProcessPoolExecutor(max_workers=min(workers, len(tasks)), mp_context=get_context('spawn'),
                                 initializer=_start_worker, initargs=(models,)) as pool:
            for (fmt, _), measurement in zip(tasks, pool.map(_measure_group, tasks)):
                results[fmt].append(measurement)
    return {fmt: _checked_error(fmt, results[fmt]) for fmt in models}
