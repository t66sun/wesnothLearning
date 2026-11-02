"""Explicitly authorized, single-format ordinary BC with frozen stage bounds."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests import bounded_training_loop as loop
from learning import adapters
from learning.teachers import identity
import _engine_lite


def main():
    loop.FORMATS = ['team2v2']
    loop.RUN = ROOT/'runs/team_bc_v2'
    loop.OUT = ROOT/'verification/team_bc_v2_20261102/observed'
    loop.OUT.mkdir(exist_ok=False)
    expected = (adapters.ENGINE_VERSION, adapters.RNG_VERSION, adapters.COMBAT_VERSION)
    actual = (_engine_lite.ENGINE_VERSION, _engine_lite.RNG_VERSION, _engine_lite.COMBAT_VERSION)
    if actual != expected:
        raise ValueError(f'extension identity mismatch: {actual} != {expected}')
    args = loop.command('run', '--run-dir', loop.RUN, '--hours', 1/3, '--phase', 'bc',
        '--formats', 'team2v2', '--device', 'cpu', '--engine', 'lite',
        '--evaluation-engine', 'lite', '--workers', 8, '--trainer-threads', 1,
        '--seed', 20261101, '--bc-games', 48, 48, 48, '--native-bc-games', 0, 0, 0,
        '--bc-batch-games', 8, '--bc-records', 2048, '--bc-validation-records', 1024,
        '--training-max-turns', 30, '--wesnoth', os.environ['WESNOTH_EXE'])
    extension = Path(_engine_lite.__file__)
    plan = dict(source_commit=os.environ['SOURCE_COMMIT'], command=args,
        format='team2v2', seed=20261101, workers=8, trainer_threads=1,
        phase_seconds=1200, external_seconds=1320, committed_batches_max=5,
        teacher_game_target=48, training_max_turns=30, bc_records=2048,
        bc_validation_records=1024, epochs=4, minibatch=256,
        extension=str(extension), extension_sha256=hashlib.sha256(extension.read_bytes()).hexdigest(),
        engine_version=actual[0], rng_version=actual[1], combat_version=actual[2],
        teacher=identity(),
        authorization='User authorized this bounded BC diagnosis and equivalent bounded diagnostics in this task.',
        limits='Original loss, sampling and ordinary gates. No forced PPO, phase extension, later stage or retry.')
    (loop.OUT/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    (loop.OUT/'driver_pid').write_text(str(os.getpid())+'\n')
    completed = loop.stage('bc', args, plan['external_seconds'], batch_limit=plan['committed_batches_max'])
    state = loop.states()['team2v2']
    gate = loop.read(loop.RUN/'team2v2/bc_gate.json')
    status = 'PASS' if completed and state.get('effective') and not state.get('error') else 'FAIL'
    result = dict(status=status, stage_completed=completed, gate=gate, state=state)
    (loop.OUT/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(status, 'ordinary team BC; no later phase launched', flush=True)
    return 0 if status == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
