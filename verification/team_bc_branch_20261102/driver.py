"""Authorized compatible BC branch; parent inputs remain read-only."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import torch
from tests import bounded_training_loop as loop
from learning import adapters
from learning.teachers import identity
import _engine_lite

PARENT = Path('/home/tongshu/acceptance/team_bc_v2_20261102/runs/team_bc_v2')
PARENT_HASH = '1cdb7d00b19ec57cc7bb3a40ab504d79d655ef02c5ef3086aa5dbba2b3b6c878'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    loop.FORMATS = ['team2v2']
    loop.RUN = ROOT/'runs/team_bc_branch'
    loop.OUT = ROOT/'verification/team_bc_branch_20261102/observed'
    loop.OUT.mkdir(exist_ok=False)
    checkpoint = PARENT/'team2v2/latest.pt'
    assert sha(checkpoint) == PARENT_HASH
    parent = torch.load(checkpoint, map_location='cpu', weights_only=False)['runner']
    assert parent['batch'] == parent['version'] == 5
    assert len(parent['teacher_shards']) == 40
    assert not any(parent.get(k) for k in ('effective', 'pending_train', 'pending_validation', 'error', 'bc_plateau'))
    expected = (adapters.ENGINE_VERSION, adapters.RNG_VERSION, adapters.COMBAT_VERSION)
    actual = (_engine_lite.ENGINE_VERSION, _engine_lite.RNG_VERSION, _engine_lite.COMBAT_VERSION)
    assert actual == expected, (actual, expected)
    args = loop.command('run', '--run-dir', loop.RUN, '--branch-from', PARENT,
        '--hours', 1/3, '--phase', 'bc', '--formats', 'team2v2',
        '--device', 'cpu', '--engine', 'lite', '--evaluation-engine', 'lite',
        '--workers', 8, '--trainer-threads', 1, '--seed', 20261101,
        '--bc-games', 48, 48, 48, '--native-bc-games', 0, 0, 0,
        '--bc-batch-games', 8, '--bc-records', 2048, '--bc-validation-records', 1024,
        '--training-max-turns', 30, '--wesnoth', os.environ['WESNOTH_EXE'])
    extension = Path(_engine_lite.__file__)
    plan = dict(source_commit=os.environ['SOURCE_COMMIT'], command=args,
        parent=str(PARENT), parent_checkpoint_sha256=PARENT_HASH,
        inherited_teacher_games=40, additional_teacher_games_max=8,
        initial_batch=parent['batch'], initial_version=parent['version'],
        additional_committed_batches_max=5, absolute_batch_limit=parent['batch']+5,
        format='team2v2', seed=20261101, workers=8, trainer_threads=1,
        phase_seconds=1200, external_seconds=1320, teacher_game_target=48,
        training_max_turns=30, bc_records=2048, bc_validation_records=1024,
        epochs=4, minibatch=256, extension=str(extension), extension_sha256=sha(extension),
        engine_version=actual[0], rng_version=actual[1], combat_version=actual[2],
        teacher=identity(),
        authorization='User authorized bounded BC diagnosis and equivalent bounded diagnostics in this task.',
        limits='Original loss, sampling and ordinary gates; optimizer kept. No parent extension, forced PPO, later phase or retry.')
    (loop.OUT/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    (loop.OUT/'driver_pid').write_text(str(os.getpid())+'\n')
    del parent
    completed = loop.stage('bc', args, plan['external_seconds'], batch_limit=plan['absolute_batch_limit'])
    state = loop.states()['team2v2']
    gate = loop.read(loop.RUN/'team2v2/bc_gate.json')
    unchanged = sha(checkpoint) == PARENT_HASH
    assert unchanged
    status = 'PASS' if completed and state.get('effective') and not state.get('error') else 'FAIL'
    result = dict(status=status, stage_completed=completed, parent_checkpoint_unchanged=unchanged,
        gate=gate, state=state)
    (loop.OUT/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(status, 'ordinary team BC branch; no later phase launched', flush=True)
    return 0 if status == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
