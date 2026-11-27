"""Freeze the one map change and run matched #306 PPO cells on Ubuntu."""
from collections import Counter
from copy import deepcopy
from functools import partial
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import torch

from learning import coordinator, schedule
from learning.common import ROOT, read_json, sha256
from learning.data import split
from learning.maps import bind_scenario, run_family
from learning.phases import request_phase
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new
from verification.duel_ppo_comparison_20261106.contract import production_trainer
from verification.duel_ppo_comparison_20261106.panels import role
from verification.ppo_batch_contract_20261107 import driver as paired
from verification.ppo_terminal_return_20261108.driver import PARENT, TerminalReturnExperiment
from audit_archive import RUNS
from lineage import worker

HERE = Path(__file__).resolve().parent
RESERVE = Path('/home/tongshu/acceptance/ppo-diagnosis-20261115-Z8O0k3/capture/confirmation-reserve.json')
RESERVE_SHA = '57043fb6c9de3a68d14d36c5ce315927cab5741a31de2e319a0faf06d6e1dbb4'
SEEDS = (202611271, 202611272, 202611273)
ORDER = [f'{arm}-{seed}' for i, seed in enumerate(SEEDS)
         for arm in (('cover','stock') if i != 1 else ('stock','cover'))]
GAMES = 1400
GROUP = 40
CELL_SECONDS = 14400
ORIGINAL = schedule.compose_training_scenario


def replace_board(job, name, board):
    m = job['meta']
    job['map_override'] = board['board']
    m.update(map=name, map_sha256=board['file_sha256'])
    job['game_family'] = run_family(job)
    bind_scenario(job)
    assert split(job['scenario_family']) == 'train'


def assign_group(jobs, boards):
    # Match four slots per new layout to stock Arena2 games whose unchanged
    # ordered roster belongs to the production training split on that layout.
    allowed = {name: [] for name in boards}
    for idx, job in enumerate(jobs):
        if job['meta']['map'] != 'arena2':
            continue
        for name, board in boards.items():
            trial = deepcopy(job)
            trial['map_override'] = board['board']
            if split(bind_scenario(trial)['scenario_family']) == 'train':
                allowed[name].append(idx)
    assert sum(j['meta']['map']=='arena2' for j in jobs) == 20
    matches = {}

    def match(name, seen):
        for pos in allowed[name]:
            if pos in seen:
                continue
            seen.add(pos)
            if pos not in matches or match(matches[pos], seen):
                matches[pos] = name
                return True
        return False

    for _ in range(4):
        for name in sorted(boards):
            assert match(name, set()), f'no eligible matched slots for {name}'
    assert Counter(matches.values()) == {name:4 for name in boards}
    return matches


def prepare(root, commit):
    historical = read_json(RUNS['306']/'launch.json')
    source = worker()
    frozen = read_json(RUNS['349']/'launch.json')
    assert source == frozen['runtime'] and sha256(RESERVE) == RESERVE_SHA
    policies = {name: frozen['roles'][key] for name,key in
                [('v38','bc'),('083','lambda-0.95-202611083')]}
    assert all(role(p['path']) == p for p in policies.values())
    boards = {}
    for name, info in frozen['boards'].items():
        path = Path(info['path'])
        assert sha256(path) == info['file_sha256']
        board = read_json(path)['board']
        assert board_digest(board) == info['board_sha256']
        boards[name] = dict(board=board,file_sha256=info['file_sha256'],board_sha256=info['board_sha256'])
    holdout = read_json(RESERVE)
    withheld = {b['board_sha256'] for b in holdout.values()}
    exposed = set(read_json(RUNS['349']/'lineage.json')['exposure']['excluded_boards'])
    exposed.update(r['board_sha256'] for r in historical['training_and_prior_boards'].values())
    exposed.update(r['board_sha256'] for r in boards.values())
    assert len(withheld)==3 and withheld.isdisjoint(exposed)
    assert all(board_digest(b['board']) == b['board_sha256'] for b in holdout.values())
    original = RUNS['306']/'cells/lambda-0.95-202611083/duel/schedules'
    jobs = [j for path in sorted(original.glob('ppo-batch-*.json'))[:GAMES//8] for j in read_json(path)]
    assert [j['training_scenario']['index'] for j in jobs] == list(range(GAMES))
    design = []
    for start in range(0, GAMES, GROUP):
        block = jobs[start:start+GROUP]
        chosen = assign_group(block, boards)
        for pos, j in enumerate(block):
            m = j['meta']
            name = chosen.get(pos)
            slot = dict(stock=m['map'], stock_family=j['scenario_family'],factions=j['factions'],seat=m['seat'])
            if name:
                replace_board(j,name,boards[name])
            slot.update(cover=m['map'],cover_family=j['scenario_family'])
            design.append(slot)
    manifest = dict(config=historical['config'],endpoint=historical['endpoint'],runtime=source,
                    references=policies,training_boards=boards,holdout=holdout,reserve_sha256=RESERVE_SHA,
                    order=ORDER,seeds=SEEDS,games=GAMES,group=GROUP,cell_seconds=CELL_SECONDS,
                    admission_seconds=14100,source_commit=commit,adapter_sha256=sha256(HERE/'trial.py'),
                    score_seed=2026112900,design=design)
    root.mkdir()
    (root/'human-empty').mkdir()
    write_new(root/'launch.json',manifest)
    print('frozen',sha256(root/'launch.json'),Counter(r['cover'] for r in design),flush=True)


class CoverageExperiment(TerminalReturnExperiment):
    def execute(self, jobs, name):
        if not name.startswith('ppo-batch-'):
            return super().execute(jobs,name)
        cell = self.directory.parent
        m = read_json(cell.parent.parent/'launch.json')
        arm = cell.name.split('-')[0]

        def compose(job, *, max_turns):
            ORIGINAL(job,max_turns=max_turns)
            meta=job['meta']
            pos=job['training_scenario']['index']
            row=m['design'][pos]
            assert [meta['map'],job['scenario_family'],job['factions'],meta['seat']] == [
                row['stock'],row['stock_family'],row['factions'],row['seat']]
            if arm=='cover' and row['cover']!=row['stock']:
                replace_board(job,row['cover'],m['training_boards'][row['cover']])
                meta['eligibility_swap']=dict(design='paired-arena2-20',requested_index=pos,
                                              stock_family=row['stock_family'],learner_seat=meta['seat'])
            assert job['scenario_family']==row[arm+'_family']
            return job

        with patch.object(schedule,'compose_training_scenario',compose):
            return super().execute(jobs,name)

    def finish_train(self, prepared_bc=None, *, prepared_ppo=None):
        budget=read_json(self.directory.parent/'budget.json')
        batch=self.state['batch']
        settled=super().finish_train(prepared_bc,prepared_ppo=prepared_ppo)
        games=(batch-budget['first_batch']+1)*8
        if settled and games%GROUP==0 and time.time()<=budget['hard_deadline']:
            os.link(self.directory/'wall.pt', self.directory/f'paired-{games:04}.pt')
        return settled


def trainer(*args, **kwargs):
    coordinator.FormatExperiment=CoverageExperiment
    return production_trainer(*args, **kwargs)


def resume(cell):
    with patch.object(coordinator,'trainer_main',trainer):
        return coordinator.Experiment(cell,resume=True).run()


def train(root, name, deadline):
    m=read_json(root/'launch.json')
    assert sha256(HERE/'trial.py')==m['adapter_sha256'] and name in ORDER
    empty=root/'human-empty'
    with patch.object(paired,'resume_arm',resume), patch.object(
            paired,'request_phase',partial(request_phase,ppo_batches=GAMES//8)), patch.object(
            paired,'configuration',lambda ignored,seed,hours:m['config']|dict(
                seed=seed,hours=hours,gae_lambda=.95,human_data=str(empty))):
        status=paired.start_arm(root/'cells'/name,PARENT,empty,m['endpoint'],seed=int(name.split('-')[1]),
                                rollout_games=8,admission=deadline-300,deadline=deadline)
    assert status['status']=='stage_complete'


def run(root, digest):
    assert sha256(root/'launch.json')==digest
    m=read_json(root/'launch.json')
    assert worker()==m['runtime'] and m['order']==ORDER
    write_new(root/'start.json',dict(launch_sha256=digest,time=time.time()))
    for name in ORDER:
        start=time.time()
        deadline=start+CELL_SECONDS
        with (root/f'{name}.log').open('x') as log:
            child=subprocess.Popen([sys.executable,'-u',__file__,'cell',str(root),name,str(deadline)],
                                   stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                code=child.wait(timeout=max(0,deadline-time.time()))
            except subprocess.TimeoutExpired:
                import signal
                os.killpg(child.pid,signal.SIGKILL)
                code=child.wait()
                outcome='hard_deadline'
            else:
                outcome='exit'
        write_new(root/f'{name}-exit.json',dict(start=start,end=time.time(),deadline=deadline,
                                               exit_code=code,outcome=outcome))
        assert code==0 or outcome=='hard_deadline', (name,code)
        assert list((root/'cells'/name/'duel').glob('paired-*.pt'))
        print(name,outcome,flush=True)
    write_new(root/'train-finished.json',dict(finished=time.time(),cells=ORDER))


if __name__=='__main__':
    torch.set_num_threads(1)
    action, folder, *args=sys.argv[1:]
    root=Path(folder).resolve()
    if action=='prepare':
        prepare(root,args[0])
    elif action=='cell':
        train(root,args[0],float(args[1]))
    elif action=='run':
        run(root,args[0])
    else:
        raise ValueError(action)
