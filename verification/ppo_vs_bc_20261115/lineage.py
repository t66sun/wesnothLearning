"""Read-only audit of the fixed #306 cohort and its evaluation worker."""
from collections import defaultdict
from hashlib import sha256 as digest
from pathlib import Path
import tarfile

import torch

from learning.common import ROOT, read_json, sha256
from learning.rules_catalog import load, resolve_dir
from learning.tasks import TASK_ID
from verification.duel_ppo_comparison_20261106.audit import board_digest, initial_audit
from verification.duel_ppo_comparison_20261106.panels import role
from verification.ppo_batch_comparison_20261107.driver import bc_endpoint, worker_identity


HERE = Path(__file__).resolve().parent
ADAPTER = HERE.parents[1]
INPUTS = read_json(HERE / 'inputs.json')
HISTORY = Path(INPUTS['old_launch']).parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def member_hashes(archive_path, prefixes, files):
    with tarfile.open(archive_path) as archive:
        return {member.name: digest(archive.extractfile(member).read()).hexdigest()
                for member in archive if member.isfile()
                and (member.name in files or member.name.startswith(prefixes))}


def verify_tree(root, expected, prefixes):
    for filename, sha in expected.items():
        require(sha256(root / filename) == sha, f'source changed: {filename}')
    for prefix in prefixes:
        actual = {path.relative_to(root).as_posix() for path in (root / prefix).rglob('*')
                  if path.is_file() and '__pycache__' not in path.parts}
        require(actual == {name for name in expected if name.startswith(prefix)},
                f'unexpected executable inputs in {prefix}')


def worker():
    original = Path(INPUTS['old_launch'])
    require(sha256(original) == INPUTS['old_launch_sha256'], '#306 launch archive changed')
    prior = read_json(original)
    source = prior['source']
    require(sha256(Path(source['archive'])) == source['archive_sha256'], '#306 source archive changed')
    worker_identity(source)
    prefixes = ('learning/', 'lua/', 'vendor/arena/', 'verification/duel_ppo_comparison_20261106/',
                'verification/ppo_batch_comparison_20261107/')
    # The worker and the reused helpers must still match the archived commit.
    members = member_hashes(source['archive'], prefixes, {'data/opponents/gpt6astra.zip'})
    require(all(any(name.startswith(prefix) for name in members) for prefix in prefixes),
            '#306 source archive is incomplete')
    verify_tree(ROOT, members, prefixes[:3])
    require(resolve_dir() == Path(prior['rules']['path'])
            and load(resolve_dir())['rules_file_sha256'] == prior['rules']['sha256'], 'rules differ')
    require(sha256(Path(prior['astra']['path'])) == prior['astra']['teacher_parent_sha256'],
            'frozen Astra archive differs')
    return dict(source=source, rules=prior['rules'], astra=prior['astra'], source_files=len(members))


def adapter_identity(archive, commit):
    with tarfile.open(archive) as stream:
        require(stream.pax_headers.get('comment') == commit, 'adapter archive commit differs')
    prefixes = (HERE.relative_to(ADAPTER).as_posix()+'/',)
    board_paths = {record['path'] for record in INPUTS['boards'].values()}
    members = member_hashes(archive, prefixes, board_paths)
    require(board_paths | {p.relative_to(ADAPTER).as_posix() for p in HERE.glob('*.py')}
            | {f'{prefixes[0]}inputs.json'} <= members.keys(), 'adapter archive is incomplete')
    verify_tree(ADAPTER, members, prefixes)
    return dict(commit=commit, archive=str(archive), archive_sha256=sha256(archive))


def read_cohort():
    parent = Path(INPUTS['roles']['bc']['path']).parents[1]
    prior = read_json(Path(INPUTS['old_launch']))
    require(prior['parent'] == str(parent), 'wrong qualified parent')
    initializer = initial_audit()
    qualified = bc_endpoint(parent)
    endpoint = qualified['endpoint']
    require(endpoint['manifest_sha256'] == INPUTS['parent_manifest_sha256']
            and endpoint['gate_sha256'] == INPUTS['gate_sha256']
            and endpoint['task_id'] == TASK_ID, 'BC qualification differs')
    old_roles = read_json(HISTORY / 'endpoints.json')
    initial_state = INPUTS['roles']['bc']['weights_sha256']
    roles, cells = {}, {}
    for name, expected in INPUTS['roles'].items():
        path = Path(expected['path'])
        require(role(path) == expected == old_roles[name], f'checkpoint identity differs: {name}')
        roles[name] = expected
        if name == 'bc':
            continue
        cell = path.parents[1]
        manifest = read_json(cell / 'manifest.json')
        branch = read_json(cell / 'branch.json')
        init = read_json(cell / 'initialization.json')
        status = read_json(cell / 'summary.json')['formats']['duel']
        ledger = read_json(HISTORY / f'{name}-ledger.json')
        budget = read_json(HISTORY / f'{name}-exit.json')
        config = manifest['config']
        frozen = dict(task_id=TASK_ID, engine='lite', gae_lambda=.95, ppo_aux_target='historical_action',
                      rollout_games=8, reward_mode='fixed', branch_reset_optimizer=True)
        require(all(config.get(key) == value for key, value in frozen.items())
                and branch['seed'] == int(name.rsplit('-', 1)[1])
                and branch['parent'] == str(parent) and branch['reset_optimizer']
                and branch['parent_manifest_sha256'] == INPUTS['parent_manifest_sha256']
                and branch['checkpoints']['duel']['bc_endpoint']['sha256'] == roles['bc']['checkpoint_sha256']
                and init['weights_sha256'] == initial_state and init['optimizer_states'] == 0,
                f'PPO initialization differs: {name}')
        state = torch.load(path, map_location='cpu', weights_only=False)['runner']
        settled_path = path.parent/'state.json'
        settled = read_json(settled_path)
        require(status['status'] == 'stage_complete' and status['phase'] == 'ppo'
                and status['pretraining_complete'] and not status['forced_ppo'] and not status['error']
                and status['version'] == expected['version']
                and state['pending_train'] is None and settled['pending_train'] is None
                and settled['pending_validation'] is None and not settled['error']
                and settled['stage'] == 'ppo_complete' and settled['version'] == state['version'] == expected['version']
                and settled['history'] == state['history']
                and state.get('pending_validation') == ledger['pending_validation']
                and ledger['endpoint'] == expected and not ledger['pending_at_stop']
                and not ledger['validation_pending'] and ledger['committed_steps'] > 0
                and ledger['exposure']['matched'] == ledger['exposure']['shards']
                and budget['exit_code'] == 0 and not budget['timed_out'] and budget['wall_seconds'] <= 14400,
                f'PPO wall endpoint is unsettled: {name}')
        cells[name] = dict(initialization=init, manifest_sha256=sha256(cell/'manifest.json'),
                           settlement_sha256=sha256(settled_path), saved_validation=state['pending_validation'],
                           final_validation=settled['pending_validation'], wall_seconds=budget['wall_seconds'], settled_batches=ledger['settled_batches'],
                           fresh_targets=ledger['fresh_targets'], committed_steps=ledger['committed_steps'],
                           exposure=ledger['exposure'])
    return dict(initializer=initializer['exposure'], bc=qualified, roles=roles, cells=cells)


def exposure(cohort):
    sources = {
        'initializer': sorted((Path(initial_audit_parent()) / 'duel/schedules').glob('*.json')),
        'bc': sorted((Path(INPUTS['roles']['bc']['path']).parents[1] / 'duel/schedules').glob('*.json')),
        'ppo': sorted((HISTORY / 'cells').glob('*/duel/schedules/*.json')),
        'old_evaluation': sorted((HISTORY / 'validation').glob('*/plan.json')) +
                          sorted((HISTORY / 'holdout').glob('*/plan.json')),
    }
    boards, seeds, groups = set(), set(), {}
    for name, paths in sources.items():
        require(paths and (name != 'old_evaluation' or len(paths) == 3), f'missing {name} plans')
        observed = defaultdict(set)
        count = 0
        for path in paths:
            record = read_json(path)
            for job in record if isinstance(record, list) else record['jobs']:
                observed[job['meta']['map']].add(board_digest(job['map_override']))
                seeds.add(job['seed'])
                count += 1
        boards.update(value for hashes in observed.values() for value in hashes)
        groups[name] = dict(files=len(paths), jobs=count,
                            boards={key: sorted(value) for key, value in sorted(observed.items())})
    boards.update(x for hashes in cohort['initializer']['boards'].values() for x in hashes)
    boards.update(x for hashes in cohort['bc']['endpoint']['exposure']['boards'].values() for x in hashes)
    boards.update(x for row in cohort['cells'].values() for hashes in row['exposure']['boards'].values() for x in hashes)
    return dict(groups=groups, excluded_boards=sorted(boards), distinct_old_seeds=len(seeds)), seeds


def initial_audit_parent():
    from verification.duel_ppo_comparison_20261106.audit import INPUTS as historical
    return historical['parent']


def audit_boards(exposed, worker_info):
    terrains = read_json(Path(worker_info['rules']['path']) / 'rules.json')['terrains']
    result = {}
    for name, record in INPUTS['boards'].items():
        path = ADAPTER / record['path']
        native = record.get('asset', record.get('native_file'))
        data = read_json(path)
        board = data['board']
        cells = [terrains[code] for row in board['terrain'] for code in row]
        require(sha256(path) == record['file_sha256'] and board_digest(board) == record['board_sha256']
                and record['board_sha256'] not in exposed, f'holdout board changed or exposed: {name}')
        require(data['native_version'] == '1.18.8' and data['source_sha256'] == record['source_sha256']
                and len(set(map(tuple, board['starts']))) == 2
                and all(terrains[board['terrain'][y-1][x-1]]['keep'] for x, y in board['starts'])
                and sum(bool(t.get('village')) for t in cells) == record['villages'] > 0,
                f'invalid holdout geometry: {name}')
        result[name] = dict(path=str(path), native_asset=native, file_sha256=record['file_sha256'],
                            board_sha256=record['board_sha256'], width=board['width'], height=board['height'],
                            starts=board['starts'], villages=record['villages'], edits=record.get('terrain_edits', []))
    return result
