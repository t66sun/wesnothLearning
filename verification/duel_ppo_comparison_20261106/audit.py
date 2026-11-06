"""Read-only identities and physical-board exposure for this one experiment."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import torch

from learning.common import ROOT, read_json, sha256
from learning.rules_catalog import load
from .contract import INPUTS


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def board_digest(board):
    terrain = board['terrain']
    physical = dict(terrain=terrain, starts=board['starts'],
                    width=board.get('width', len(terrain[0])), height=board.get('height', len(terrain)))
    return hashlib.sha256(json.dumps(physical, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def shard_boards(state):
    paths = {str(Path(p).resolve()).replace('.dagger.jsonl.gz', '.jsonl.gz')
             for key in ('teacher_shards', 'dagger_shards', 'policy_shards') for p in state.get(key, [])}
    directories = {Path(p).parents[1] for p in paths}
    matched, boards, partitions = {}, defaultdict(set), Counter()
    for directory in sorted(directories):
        for path in sorted((directory / 'schedules').glob('*.json')):
            for job in read_json(path):
                if job.get('shard') in paths:
                    matched[job['shard']] = job
    if set(matched) != paths:
        raise ValueError('retained optimization shards lack their frozen schedules')
    for job in matched.values():
        boards[job['meta']['map']].add(board_digest(job['map_override']))
        partitions[job['meta']['map_partition']] += 1
    holdout = {row['board_sha256'] for row in INPUTS['holdout_boards'].values()}
    overlap = set().union(*boards.values()) & holdout if boards else set()
    if overlap:
        raise ValueError('optimization data overlaps the final holdout board')
    return dict(shards=len(paths), matched=len(matched), boards={key: sorted(value) for key, value in boards.items()},
                partitions=dict(partitions), holdout_overlap=sorted(overlap))


def initial_audit():
    import _engine_lite
    from learning.features import schema
    from learning.model import ARCHITECTURE
    from learning.teachers import identity
    parent = Path(INPUTS['parent'])
    if sha256(parent / 'manifest.json') != INPUTS['parent_manifest_sha256']:
        raise ValueError('old initializer manifest changed')
    if sha256(parent / 'duel/last_bc.pt') != INPUTS['parent_bc_sha256']:
        raise ValueError('old initializer checkpoint changed')
    old = torch.load(parent / 'duel/last_bc.pt', map_location='cpu', weights_only=False)
    if old['runner']['version'] != INPUTS['parent_bc_version'] or old['runner'].get('lineage'):
        raise ValueError('old initializer lineage differs')
    manifest = read_json(parent / 'manifest.json')
    if sha256(manifest['opponents'][0]['path']) != INPUTS['opponent_sha256']:
        raise ValueError('frozen Astra changed')
    if load(INPUTS['rules_dir'])['rules_file_sha256'] != INPUTS['rules_sha256']:
        raise ValueError('rules changed')
    if sha256(_engine_lite.__file__) != INPUTS['extension_sha256']:
        raise ValueError('provisioned extension changed')
    human = list((Path(manifest['config']['human_data']) / 'duel').glob('*.jsonl.gz'))
    if human:
        raise ValueError('old BC human inputs require an additional exposure audit')
    boards = shard_boards(old['runner'])
    if boards['shards'] != 304 or boards['boards'] != {k: [v] for k, v in INPUTS['old_bc_boards'].items()}:
        raise ValueError('old BC exposure differs from the frozen protocol')
    for name, expected in INPUTS['holdout_boards'].items():
        path = ROOT / 'data/rules/1.18.8/maps' / (name + '.json')
        if sha256(path) != expected['file_sha256'] or board_digest(read_json(path)['board']) != expected['board_sha256']:
            raise ValueError('holdout map identity differs')
    return dict(parent=INPUTS['parent'], exposure=boards, old_human_shards=0,
                architecture=ARCHITECTURE, features=schema(), teacher=identity(),
                extension=str(_engine_lite.__file__), extension_sha256=sha256(_engine_lite.__file__))
