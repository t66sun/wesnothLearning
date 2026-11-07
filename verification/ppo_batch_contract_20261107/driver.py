"""Launch and resume the bounded fixed-Astra 4/8-game duel comparison."""
from functools import partial
from pathlib import Path
import time

import torch

from learning import coordinator, experiment
from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.phases import request_phase
from verification.duel_ppo_comparison_20261106.audit import write_new
from verification.duel_ppo_comparison_20261106.contract import (
    admission_deadline, fixed_rollouts, production_trainer,
)
from verification.duel_ppo_comparison_20261106.driver import configuration


def ordinal_rollouts(directory, policy, history, fixed, support, version,
                     batch_index, seed, deadline, wesnoth, games_per_format=4,
                     current=None, formats=('duel',), *, first_batch):
    # The existing four-game design owns the seats, scenarios and RNG.
    # Regroup that same stream at each arm's physical update boundary.
    first_ordinal = (batch_index - first_batch) * games_per_format
    return [job
            for ordinal in range(first_ordinal, first_ordinal + games_per_format, 4)
            for job in fixed_rollouts(directory, policy, history, fixed, support, version,
                                      ordinal // 4, seed, deadline, wesnoth, 4,
                                      current=current, formats=formats)]


class CollectionCutoff(Exception):
    """The hard deadline interrupted at least one game in the physical batch."""


class PairedExperiment(experiment.FormatExperiment):
    def update_deadline(self):
        hard = super().update_deadline()
        if self.state.get('phase') != 'ppo':
            return hard
        budget = read_json(self.directory.parent / 'budget.json')
        # The wall-clock experiment records fresh targets without stopping at them.
        budget.setdefault('fresh_targets', float('inf'))
        return admission_deadline(self.state, budget, min(hard, budget['hard_deadline']), time.time())

    def learn(self):
        budget = read_json(self.directory.parent / 'budget.json')
        schedule = experiment.rollout_jobs
        experiment.rollout_jobs = partial(ordinal_rollouts, first_batch=budget['first_batch'])
        try:
            super().learn()
        except CollectionCutoff:
            return
        finally:
            experiment.rollout_jobs = schedule

    def execute(self, jobs, name):
        jobs, results = super().execute(jobs, name)
        if name.startswith('ppo-batch-'):
            expected = {job['id'] for job in jobs}
            complete = {row['id'] for row in results if row['status'] == 'complete'
                        and row.get('training_eligible') and not row['result'].get('faults')}
            interrupted = {row['id'] for row in results if row['status'] == 'budget_interrupted'}
            if len(expected) != self.config['rollout_games'] or expected != complete | interrupted:
                raise RuntimeError(f'incomplete PPO batch {name}; inspect jobs.jsonl')
            if interrupted:
                raise CollectionCutoff
        return jobs, results


def trainer_main(*args, **kwargs):
    # Only the dedicated comparison trainer uses the ordinal schedule and gate.
    coordinator.FormatExperiment = PairedExperiment
    return production_trainer(*args, **kwargs)


def resume_arm(root):
    """Resume from the frozen manifest, budget and PPO stage request."""
    trainer = coordinator.trainer_main
    coordinator.trainer_main = trainer_main
    try:
        return coordinator.Experiment(root, resume=True).run()
    finally:
        coordinator.trainer_main = trainer


def start_arm(root, parent, empty_human, endpoint, *, seed, rollout_games,
              admission, deadline, fresh_targets=None):
    """Initialize from the qualified BC endpoint, then enter the frozen PPO budget."""
    if rollout_games not in (4, 8):
        raise ValueError('the comparison uses four or eight rollout games')
    root, parent = Path(root), Path(parent)
    config = configuration(empty_human, seed, (deadline - time.time()) / 3600)
    config.update(branch_reset_optimizer=True, rollout_games=rollout_games)
    run = coordinator.Experiment(root, config=config, branch_from=parent)
    branch = read_json(root / 'branch.json')['checkpoints']['duel']
    if branch.get('bc_endpoint', {}).get('sha256') != endpoint['checkpoint_sha256']:
        raise ValueError('the branch did not inherit the frozen qualifying BC endpoint')
    # The inherited qualified BC phase returns without collecting or updating.
    run.run()
    checkpoint = root / 'duel/latest.pt'
    initialized = torch.load(checkpoint, map_location='cpu', weights_only=False)
    weights = weights_sha256(initialized['model'])
    if weights != endpoint['weights_sha256'] or initialized['optimizer']['state']:
        raise ValueError('PPO arm did not initialize from common weights and fresh Adam')
    state = initialized['runner']
    budget = dict(admission_deadline=admission, hard_deadline=deadline,
                  history_start=len(state['history']), first_batch=state['batch'])
    if fresh_targets is not None:
        budget['fresh_targets'] = fresh_targets
    write_new(root / 'budget.json', budget)
    write_new(root / 'initialization.json', dict(weights_sha256=weights,
              checkpoint_sha256=sha256(checkpoint), optimizer_states=0))
    request_phase(root, 'ppo', hours=(deadline - time.time()) / 3600)
    return resume_arm(root)
