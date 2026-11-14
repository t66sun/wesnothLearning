"""Eight-game duel opponent contrast on the accepted ordinal PPO runner."""
from functools import partial
from pathlib import Path
import shutil
from unittest.mock import patch

from learning import coordinator, experiment
from learning.common import read_json, sha256
from learning.export import export, load_model
from verification.duel_ppo_comparison_20261106.contract import production_trainer
from verification.ppo_batch_comparison_20261107.panels import INPUTS as PREVIOUS
from verification.ppo_batch_contract_20261107.driver import CollectionCutoff, ordinal_rollouts
from verification.ppo_terminal_return_20261108.driver import TerminalReturnExperiment

PROTOCOL = Path(__file__).resolve().parents[1] / 'ppo_opponent_protocol_20261114'
INPUTS = read_json(PROTOCOL / 'inputs.json')


def export_opponent(checkpoint, directory):
    if sha256(checkpoint) != PREVIOUS['base_bc']['checkpoint_sha256']:
        raise ValueError('qualified BC checkpoint changed')
    model, _ = load_model(checkpoint, 'duel')
    addon = export(model, directory, name='FrozenDuelBC', mode='greedy',
                   version='v38', package=False)
    shutil.copyfile(checkpoint, directory / 'model.pt')
    record = dict(path=str(addon), weights_sha256=PREVIOUS['base_bc']['weights_sha256'],
                  config_sha256=sha256(addon / 'lua/config.lua'))
    verify_opponent(record)
    return record


def verify_opponent(record):
    addon = Path(record['path'])
    tensor = addon.parent / 'model.pt'
    mode = addon / 'lua/config.lua'
    if (record['weights_sha256'] != PREVIOUS['base_bc']['weights_sha256']
            or sha256(tensor) != PREVIOUS['base_bc']['checkpoint_sha256']
            or sha256(mode) != record['config_sha256']
            or '["mode"]="greedy"' not in mode.read_text(encoding='utf-8').replace(' ', '')):
        raise ValueError('frozen BC opponent identity or greedy mode differs')


def rollouts(directory, policy, history, fixed, support, version, batch_index,
             seed, deadline, wesnoth, games_per_format=8, current=None,
             formats=('duel',), *, first_batch, contract):
    if games_per_format != INPUTS['batch_games'] or tuple(formats) != ('duel',):
        raise ValueError('opponent comparison requires eight duel games')
    if contract['arm'] not in ('astra', 'mixed') or list(fixed) != [contract['astra']]:
        raise ValueError('opponent comparison has an unexpected arm or Astra path')
    if batch_index < first_batch:
        raise ValueError('comparison batch precedes the frozen ordinal stream')
    jobs = ordinal_rollouts(directory, policy, history, fixed, support, version,
                            batch_index, seed, deadline, wesnoth, games_per_format,
                            current=current, formats=formats, first_batch=first_batch)
    offset = batch_index - first_batch
    slots = INPUTS['bc_slots']
    selected = slots[offset % len(slots)] if contract['arm'] == 'mixed' else ()
    for index, job in enumerate(jobs):
        seat = job['meta']['seat']
        bc = index in selected
        path = contract['bc']['path'] if bc else contract['astra']
        sha = contract['bc']['weights_sha256'] if bc else PREVIOUS['astra']['teacher_parent_sha256']
        job['bots'][2-seat] = path
        job['meta']['composition'] = [dict(role='frozen_bc' if bc else 'fixed_astra', path=path)]
        job['meta']['experimental_opponent'] = dict(side=3-seat, sha256=sha,
            kind='frozen_bc' if bc else 'astra', ordinal=offset*games_per_format+index)
    if selected and {jobs[index]['meta']['seat'] for index in selected} != {1, 2}:
        raise ValueError('frozen BC did not play against both learner seats')
    return jobs


def check_frozen_jobs(frozen, expected, astra):
    if len(frozen) != len(expected):
        raise ValueError('frozen PPO schedule has the wrong batch size')
    for saved, current in zip(frozen, expected):
        if (saved['id'] != current['id'] or saved['bots'] != current['bots']
                or saved['meta']['experimental_opponent'] != current['meta']['experimental_opponent']
                or saved['learning']['sides'] != current['learning']['sides']
                or saved['learning']['dagger_teacher'] != astra):
            raise ValueError('frozen PPO schedule has a different opponent or learner')


class OpponentExperiment(TerminalReturnExperiment):
    def learn(self):
        if self.state.get('phase') != 'ppo':
            return super().learn()
        root = self.directory.parent
        budget = read_json(root / 'budget.json')
        contract = read_json(root / 'opponents.json')
        if sha256(contract['astra']) != PREVIOUS['astra']['teacher_parent_sha256']:
            raise ValueError('frozen Astra differs')
        verify_opponent(contract['bc'])
        schedule = partial(rollouts, first_batch=budget['first_batch'], contract=contract)
        with patch.object(experiment, 'rollout_jobs', schedule):
            try:
                return experiment.FormatExperiment.learn(self)
            except CollectionCutoff:
                return

    def execute(self, jobs, name):
        if name.startswith('ppo-batch-'):
            path = self.directory / 'schedules' / (name + '.json')
            if path.exists():
                check_frozen_jobs(read_json(path), jobs, self.teachers[0])
        return super().execute(jobs, name)


def trainer_main(*args, **kwargs):
    with patch.object(coordinator, 'FormatExperiment', OpponentExperiment):
        return production_trainer(*args, **kwargs)


def resume(root):
    with patch.object(coordinator, 'trainer_main', trainer_main):
        return coordinator.Experiment(root, resume=True).run()
