"""Record full-batch boundaries around the accepted fixed-Astra 4/8-game adapter."""
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import os
import time

import torch

from learning import coordinator, experiment, ppo
from learning.common import read_json, sha256
from verification.duel_ppo_comparison_20261106.audit import write_new
from verification.duel_ppo_comparison_20261106.contract import fresh_targets, ledger, production_trainer
from verification.duel_ppo_comparison_20261106.panels import role
from verification.ppo_batch_contract_20261107 import driver as paired

INPUTS = read_json(Path(__file__).with_name('inputs.json'))


def preserve_boundary(directory, state, budget, finished_at):
    """Pin the exact settled checkpoint before another batch can replace latest."""
    if state.get('pending_train') or finished_at > budget['hard_deadline']:
        return
    entry = state['history'][-1]
    if entry['method'] != 'ppo':
        return
    fresh = fresh_targets(state, budget['history_start'])
    directory = Path(directory)
    endpoints = directory / 'endpoints'
    endpoints.mkdir(exist_ok=True)
    latest = directory / 'latest.pt'
    previous = fresh - entry['planned_targets']
    for threshold in INPUTS['fresh_endpoints']:
        if previous < threshold <= fresh:
            os.link(latest, endpoints / f'fresh-{threshold}.pt')
    next_wall = endpoints / 'wall.next'
    os.link(latest, next_wall)
    next_wall.replace(endpoints / 'wall.pt')


class WallExperiment(paired.PairedExperiment):
    def execute(self, jobs, name):
        started = time.monotonic()
        try:
            return super().execute(jobs, name)
        finally:
            finished = time.monotonic()
            self._collection_finished = finished
            if name.startswith(('ppo-batch-', 'validation-')):
                write_new(self.directory / 'times' / f'{name}.json',
                          dict(phase='rollout' if name.startswith('ppo-') else 'validation',
                               wall_seconds=finished-started))

    def finish_train(self, prepared_bc=None, *, prepared_ppo=None):
        if self.state['pending_train']['method'] != 'ppo':
            return super().finish_train(prepared_bc, prepared_ppo=prepared_ppo)
        started = time.monotonic()
        before_update = None
        training_seconds = inner_preparation = 0.

        def measure_prepare(function):
            def measured(*args, **kwargs):
                nonlocal inner_preparation
                before = time.monotonic()
                try:
                    return function(*args, **kwargs)
                finally:
                    inner_preparation += time.monotonic() - before
            return measured

        train = experiment.train

        def measured_train(*args, **kwargs):
            nonlocal before_update, training_seconds
            before_update = time.monotonic()
            try:
                return train(*args, **kwargs)
            finally:
                training_seconds = time.monotonic() - before_update

        batch = self.state['batch']
        with ExitStack() as scope:
            scope.enter_context(patch.object(experiment, 'train', measured_train))
            scope.enter_context(patch.object(ppo, 'prepare', measure_prepare(ppo.prepare)))
            scope.enter_context(patch.object(ppo, 'setup', measure_prepare(ppo.setup)))
            settled = super().finish_train(prepared_bc, prepared_ppo=prepared_ppo)
        finished_at = time.time()
        budget = read_json(self.directory.parent / 'budget.json')
        if settled:
            preserve_boundary(self.directory, self.state, budget, finished_at)
        if before_update is not None:
            prepared_from = getattr(self, '_collection_finished', started)
            write_new(self.directory / 'times' / f'update-{batch:06}.json',
                      dict(phase='update', settled=settled, finished_at=finished_at,
                           preparation_seconds=before_update-prepared_from+inner_preparation,
                           training_seconds=training_seconds-inner_preparation))
        return settled


def trainer_main(*args, **kwargs):
    coordinator.FormatExperiment = WallExperiment
    return production_trainer(*args, **kwargs)


def resume_arm(root):
    with patch.object(coordinator, 'trainer_main', trainer_main):
        return coordinator.Experiment(root, resume=True).run()


def start_arm(*args, **kwargs):
    # Reuse the accepted lineage, optimizer and phase setup. The spawned
    # trainer alone replaces the PPO class, after inherited BC has returned.
    with patch.object(paired, 'resume_arm', resume_arm):
        return paired.start_arm(*args, **kwargs)


def endpoint_record(path, budget):
    record = role(path)
    state = torch.load(path, map_location='cpu', weights_only=False)['runner']
    entries = state['history'][budget['history_start']:]
    record.update(fresh_targets=sum(row['planned_targets'] for row in entries),
                  settled_batches=len(entries), batch=entries[-1]['batch'] if entries else None)
    return record, state


def summarize(root, outcome):
    directory = root / 'duel'
    budget = read_json(root / 'budget.json')
    state = read_json(directory / 'state.json')
    wall = directory / 'endpoints' / 'wall.pt'
    final, complete_state = endpoint_record(wall if wall.exists() else directory/'last_bc.pt', budget)
    entries = complete_state['history'][budget['history_start']:]
    value = ledger(complete_state, dict(budget, fresh_targets=float('inf')))
    del value['overshoot'], value['budget_complete']
    value.update(history=entries, pending_train=state.get('pending_train'),
                 pending_validation=state.get('pending_validation'), error=state.get('error'),
                 unsettled_history_entries=len(state['history'][budget['history_start']:])-len(entries))
    jobs = [row for row in experiment.read_log(directory / 'jobs.jsonl')
            if row.get('meta', {}).get('phase') == 'ppo']
    settled_batches = [read_json(directory / 'schedules' / f"ppo-batch-{row['batch']:06}.json")
                       for row in entries]
    settled_jobs = [job for batch in settled_batches for job in batch]
    samples = sum((row.get('training_shard') or {}).get('written', 0) for row in jobs)
    value.update(sampled_eligible_decisions=samples, unsettled_eligible_decisions=samples-value['fresh_targets'],
                 policy_games=len(settled_jobs), attempted_policy_games=len(jobs),
                 scenario_families=len({job['scenario_family'] for job in settled_jobs}),
                 game_families=len({job['game_family'] for job in settled_jobs}),
                 fresh_per_hour=value['fresh_targets']*3600/outcome['wall_seconds'],
                 trainer_peak_rss_mb=max((row['peak_rss_mb'] for row in entries), default=None))
    timings = [read_json(path) for path in (directory/'times').glob('*.json')]
    value.update(rollout_seconds=sum(row['wall_seconds'] for row in timings if row['phase']=='rollout'),
                 validation_seconds=sum(row['wall_seconds'] for row in timings if row['phase']=='validation'),
                 preparation_seconds=sum(row.get('preparation_seconds', 0) for row in timings),
                 training_seconds=sum(row.get('training_seconds', 0) for row in timings))
    update_seconds = value['preparation_seconds'] + value['training_seconds']
    value['preparation_share_of_update'] = value['preparation_seconds']/update_seconds if update_seconds else None
    value['preparation_share_of_wall'] = value['preparation_seconds']/outcome['wall_seconds']
    roles = {'wall': final}
    for threshold in INPUTS['fresh_endpoints']:
        path = directory / 'endpoints' / f'fresh-{threshold}.pt'
        roles[str(threshold)] = None
        if path.exists():
            record, _ = endpoint_record(path, budget)
            record['overshoot'] = record['fresh_targets'] - threshold
            roles[str(threshold)] = record
    if settled_batches:
        first = settled_batches[0]
        value['first_online_batch'] = dict(
            games=len(first), targets=entries[0]['planned_targets'],
            versions=sorted({job['meta']['version'] for job in first}),
            ordinals=[job['training_scenario']['index'] for job in first],
            schedule_sha256=sha256(directory/'schedules'/f"ppo-batch-{entries[0]['batch']:06}.json"))
    return dict(ledger=value, roles=roles)
