"""Measure fixed public board states and replay captured fixture rows."""
import argparse
import gzip
from pathlib import Path
import resource
import runpy
import shutil
from tempfile import TemporaryDirectory

import torch

from learning.common import ROOT, read_json, sha256, write_json
from learning.data import read_shards, write_shard
from learning.export import load_model, verify_numerics
from learning.features import VERSION
from learning.lite_host import LiteHost
from learning.lite_policy import FrozenPolicies, game_spec
from learning.maps import frozen_map
from learning.model import ARCHITECTURE
from learning.rowpack import plain_row
from learning.rules_catalog import load, provenance
from learning.sequence_parity import _ParityAudit
from learning.sequences import read_raw_shards
from tests.v5 import helpers


C1 = runpy.run_path(ROOT / 'verification/spatial_position_readout_20261107/probe.py')
FIXTURES = runpy.run_path(ROOT / 'verification/representation_information_20261106/fixtures.py')
RESULT = dict(bots=['fixture', 'fixture'], winner=1, faults={})


def measured_host(name, rules_dir):
    import params
    if name == 'arena2':
        map_path = ROOT / 'vendor/arena/maps/arena2.json'
        board, digest = read_json(map_path), sha256(map_path)
    else:
        board, digest = frozen_map(name)
    rules, _ = provenance(load(rules_dir), rules_dir)
    spec = game_spec(dict(bots=['fixture', 'fixture'], seed=228, factions=params.FACTIONS[:2],
                          allow_approximate=True, fog=True, max_turns=30, map_override=board), rules)
    return LiteHost(spec, rules_dir), digest


def fixture_row(decision, game, *, turn=1, committed=True, write=None, labelled=True):
    row = helpers.record_from_decision(decision, game_id=game, game_family=game)
    row.update(turn=turn, committed=committed)
    if write is not None:
        row['memory_write'] = dict(write, turn=turn)
    if not labelled:
        row.update(choice=-1, actual=None)
    return row


def persist(directory, name, rows):
    path = directory / (name + '.jsonl.gz')
    result = write_shard(path, name, rows, RESULT)
    assert result['raw_records'] == len(rows)
    return path


def history_rows():
    _, traces = FIXTURES['within_turn_traces']()
    first, current = traces[0][0], traces[0][-1]
    # Repeat the first legal public write exactly as in the original #229 cost fixture.
    rows = [fixture_row(first, 'history', turn=turn, write=first['memory_write'], labelled=False)
            for turn in range(1, 41)]
    rows.append(fixture_row(current, 'history', turn=41, committed=False))
    return rows


def timings(runner, row, host):
    history = row.get('_history', [])
    policies = FrozenPolicies(dict(format='duel', bots=[runner.support, 'gpt6astra'], seed=228))
    if history:
        policies.histories[1] = history[:-1]
        policies.choose(row, 1)
    memory_states, contexts = policies.memory_states.copy(), policies.memory_contexts.copy()

    def restore():
        policies.histories[1] = history
        policies.memory_states = memory_states.copy()
        policies.memory_contexts = contexts.copy()

    lite, decision = C1['measure'](lambda: policies.choose(host.decision(1) if host else row, 1), restore)
    lua, lua_choice = C1['measure'](C1['lua_decision'](_ParityAudit(runner.model), plain_row(row)))
    assert decision['choice'] == lua_choice['choice']
    assert abs(decision['value'] - lua_choice['value']) < 1e-5
    assert abs(decision['log_probability'] - lua_choice['log_probability']) < 1e-5
    return dict(lite_ms=lite, lua_ms=lua, training=C1['training_times'](runner.model, row), decision=decision)


def parity(runner, args, directory, history):
    fixture_path = ROOT / 'verification/candidate_support_20261106/measured.json'
    case = next(case for case in read_json(fixture_path)['fixtures'] if case['name'] == 'combat_slots')
    dense = LiteHost(case['spec'], args.rules).decision(1)
    assert len(dense['candidates']) == 37
    paths = [history, persist(directory, 'combat_slots', [fixture_row(dense, 'combat_slots')])]
    for name, spec in zip(('route_open', 'route_closed'), FIXTURES['pairs']()['resampling_connectivity']):
        _, decision = FIXTURES['capture'](spec)
        paths.append(persist(directory, name, [fixture_row(decision, name)]))
    records = read_raw_shards(paths, 'duel')
    assert len(records) == 44
    assert len(records[40]['_history']) == 40
    with torch.no_grad():
        runner.model.board_readout.weight[:, 16:32] = .125 * torch.eye(16)
        runner.model.board_readout.weight[:, 32:] = -.25 * torch.eye(16)
    runner.save()
    reloaded, _ = load_model(runner.directory/'latest.pt', 'duel')
    assert torch.equal(reloaded.board_readout.weight, runner.model.board_readout.weight)
    error = verify_numerics(reloaded, records)
    assert not runner.optimizer.state
    try:
        read_raw_shards([args.old_shard], 'duel')
    except ValueError as error_old:
        assert 'schema' in str(error_old)
    else:
        raise AssertionError('pooled raw rows were admitted as native-grid history')
    saved = args.output.parent / 'fixture_rows'
    saved.mkdir()
    for path in paths:
        shutil.copyfile(path, saved/path.name)
    return dict(rows=len(records), replay_prefix=len(records[40]['_history']), max_error=error,
                old_shard_sha256=sha256(args.old_shard), raw_shards={path.name: sha256(path) for path in paths})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', choices=('arena2', 'ruined_passage', 'history'))
    parser.add_argument('parent', type=Path)
    parser.add_argument('rules', type=Path)
    parser.add_argument('old_shard', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    assert not args.output.exists()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    with TemporaryDirectory(dir=ROOT, prefix='native-grid-') as temporary:
        directory = Path(temporary)
        runner, initializer = C1['initialized_runner'](args.parent, directory/'child', args.rules)
        if args.case == 'history':
            rows, host, digest = history_rows(), None, None
            width, height = 32, 16
        else:
            host, digest = measured_host(args.case, args.rules)
            rows = [fixture_row(host.decision(1), args.case)]
            width, height = host.adapter.spec['width'], host.adapter.spec['height']
        path = persist(directory/'rows', args.case, rows)
        read_ms, targets = C1['measure'](lambda: read_shards([path], format_name='duel'))
        assert len(targets) == 1
        row = targets[0]
        assert len(row['_history']) == (40 if args.case == 'history' else 0)
        with gzip.open(path, 'rb') as stream:
            row_bytes = [len(line.rstrip(b'\n')) for line in stream]
        result = dict(case=args.case, width=width, height=height, map_sha256=digest,
                      candidates=len(row['candidates']), entities=len(row['spatial']['entities']),
                      history=len(row['_history']), persisted_rows=len(rows), packed_row_bytes=row_bytes[-1],
                      packed_prefix_row_bytes=row_bytes[0] if args.case == 'history' else None,
                      gzip_shard_bytes=path.stat().st_size,
                      architecture=ARCHITECTURE, feature_schema=VERSION, initializer=initializer,
                      rules_sha256=runner.manifest['rules']['rules_sha256'], read_ms=read_ms, **timings(runner, row, host))
        result['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if VERSION == 7 and args.case == 'history':
            result['parity'] = parity(runner, args, directory/'rows', path)
        write_json(args.output, result)
        print(args.output, f'{width}×{height}, {len(row["_history"])} history rows')


if __name__ == '__main__':
    main()
