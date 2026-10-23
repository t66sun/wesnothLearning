"""Explicit BC/PPO/evaluation requests, applied by the owning trainer at a batch boundary."""
import math
from pathlib import Path
import time
import uuid
from .common import read_json
from .control import _atomic, _locked

PHASES = ('auto', 'bc', 'ppo', 'evaluate')


def request_phase(run_dir, phase, *, formats=None, force=False, reason='', hours=None):
    if phase not in PHASES: raise ValueError('unknown phase')
    if force and phase != 'ppo': raise ValueError('--force is only valid for PPO')
    if force and not reason.strip(): raise ValueError('forced PPO requires --reason')
    if hours is not None and (not math.isfinite(hours) or hours <= 0): raise ValueError('phase hours must be positive and finite')
    root=Path(run_dir)
    manifest=read_json(root/'manifest.json')
    from .features import VERSION
    if manifest.get('features',{}).get('version',VERSION)!=VERSION:
        raise ValueError('phase request requires matching data schema; do not use old checkpoints with new source')
    targets=formats or manifest['config']['formats']
    if not targets or not set(targets)<=set(manifest['config']['formats']): raise ValueError('phase formats must belong to the run')
    now=time.time();commands={}
    clock=read_json(root/'clock.json')
    inherited=clock['update_deadline' if phase=='auto' else 'deadline']
    if hours is None and inherited<=now: raise ValueError('original budget expired; provide explicit phase --hours')
    with _locked(root/'phase'):
        for fmt in targets:
            state=read_json(root/fmt/'state.json')
            if state['stage'] in ('final','finished') or state.get('failed_stage')=='final':
                raise ValueError('evaluation has started; create a new run for further training')
            if phase=='ppo' and not force and not state.get('effective'):
                raise ValueError(f'{fmt}: BC gates not passed; use --force --reason to enter PPO explicitly')
            commands[fmt]=dict(id=uuid.uuid4().hex,phase=phase,force=force,reason=reason,
                               requested_at=now,deadline=now+hours*3600 if hours is not None else None)
        for fmt,command in commands.items(): _atomic(root/'phase'/f'{fmt}.pending.json',command)
    return commands


def show_phases(run_dir):
    root=Path(run_dir);manifest=read_json(root/'manifest.json')
    result={}
    for fmt in manifest['config']['formats']:
        state=read_json(root/fmt/'state.json');path=root/'phase'/f'{fmt}.pending.json'
        result[fmt]=dict(stage=state['stage'],phase=state.get('phase','auto'),
                        pretraining_complete=state.get('effective',False),
                        history=state.get('phase_history',[]),pending=read_json(path) if path.exists() else None)
    return result


def apply_phase(runner):
    root=runner.directory.parent;path=root/'phase'/f'{runner.fmt}.pending.json'
    if not path.exists(): return
    with _locked(root/'phase'):
        if not path.exists(): return
        command=read_json(path)
        state=runner.state
        if command['id'] != state.get('phase_command_id'):
            phase=command['phase']
            if phase=='ppo' and not command['force'] and not state.get('effective'):
                raise ValueError('BC gates not passed for queued PPO phase')
            state.setdefault('phase_history',[]).append(dict(command,previous_phase=state.get('phase','auto'),
                pretraining_complete=state.get('effective',False),applied_at=time.time()))
            state.update(phase=phase,phase_deadline=command['deadline'],phase_command_id=command['id'])
            state.pop('status',None)
            if phase=='ppo' and command['force']:
                state['forced_ppo']=dict(reason=command['reason'],command_id=command['id'],version=state['version'])
            if state['stage'].endswith('_complete'):
                state['stage']='bc' if phase=='auto' else phase
            runner.save()
        path.unlink()
