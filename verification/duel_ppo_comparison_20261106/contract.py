"""Only this experiment's admission, fixed-opponent and paired-report contract."""
from collections import defaultdict
from pathlib import Path
import random
from statistics import mean
import time

from learning import coordinator, experiment
from learning.common import read_json
from learning.experiment import FormatExperiment
from learning.schedule import rollout_jobs as production_rollouts

HERE = Path(__file__).resolve().parent
INPUTS = read_json(HERE / 'inputs.json')
production_trainer = coordinator.trainer_main


def ppo_entries(state, start=0):
    return [entry for entry in state['history'][start:] if entry['method'] == 'ppo']


def fresh_targets(state, start=0):
    # A fully KL-rejected batch still consumed fresh trajectories.
    return sum(entry['planned_targets'] for entry in ppo_entries(state, start))


def admission_deadline(state, budget, hard, now):
    if state.get('pending_train') or state.get('pending_validation'):
        return hard
    if (fresh_targets(state, budget['history_start']) >= budget['fresh_targets']
            or now >= budget['admission_deadline']):
        return 0.
    return hard


class BoundedExperiment(FormatExperiment):
    def update_deadline(self):
        hard = super().update_deadline()
        if self.state.get('phase') != 'ppo':
            return hard
        budget = read_json(self.directory.parent / 'budget.json')
        return admission_deadline(self.state, budget, min(hard, budget['hard_deadline']), time.time())


def fixed_rollouts(directory, policy, history, fixed, support, version,
                   batch_index, seed, deadline, wesnoth, games_per_format=4,
                   current=None, formats=('duel',)):
    astra = fixed[0]
    return production_rollouts(directory, policy, [astra], [astra], support,
        version, batch_index, seed, deadline, wesnoth, games_per_format,
        current=astra, formats=formats)


def trainer_main(*args, **kwargs):
    # Installed only in the dedicated PPO trainer process. Production files,
    # optimizers, finish_train and KL settlement are untouched.
    coordinator.FormatExperiment = BoundedExperiment
    experiment.rollout_jobs = fixed_rollouts
    return production_trainer(*args, **kwargs)


def ledger(state, budget):
    entries = ppo_entries(state, budget['history_start'])
    totals = {key: sum(entry.get(key, 0) for entry in entries) for key in (
        'planned_steps', 'committed_steps', 'inspected_decisions', 'committed_decisions')}
    rejected = sum(bool(entry.get('kl_stopped')) for entry in entries)
    totals.update(settled_batches=len(entries), fresh_targets=fresh_targets(state, budget['history_start']),
                  rejected_steps=rejected,
                  rejected_decision_visits=totals['inspected_decisions']-totals['committed_decisions'])
    totals['never_attempted_steps'] = totals['planned_steps']-totals['committed_steps']-rejected
    totals['overshoot'] = max(0, totals['fresh_targets']-budget['fresh_targets'])
    totals['pending_train'] = state.get('pending_train')
    totals['pending_validation'] = state.get('pending_validation')
    totals['budget_complete'] = (totals['fresh_targets'] >= budget['fresh_targets']
                                 and not totals['pending_train'] and not totals['pending_validation'])
    return totals


def aliases(roles):
    """Equal weights name one actual policy evaluation, irrespective of role."""
    unique, mapping = {}, {}
    for name, role in roles.items():
        key = role['weights_sha256']
        unique.setdefault(key, role)
        mapping[name] = key
    return unique, mapping


def completion(budgets_complete, panels, exit_code):
    panels_complete = bool(exit_code == 0 and panels and all(
        panels.get(partition, {}).get('complete') for partition in ('validation', 'holdout')))
    return dict(status='observed' if budgets_complete and panels_complete else 'incomplete',
                budgets_complete=budgets_complete, panels_complete=panels_complete)


def crossed_statistics(a, b, bc, scenario_maps, *, seed=202611069, samples=10000):
    """Draw crossed seed/scenario axes; shared BC is evaluated exactly once."""
    seeds, scenes = sorted(a), set(bc)
    if seeds != sorted(b) or not seeds or not scenes:
        raise ValueError('paired seed/scenario design is incomplete')
    if set(scenario_maps) != scenes or any(set(rows) != scenes for rows in list(a.values())+list(b.values())):
        raise ValueError('paired seed/scenario design is incomplete')
    groups = defaultdict(list)
    for scene in sorted(scenes):
        groups[scenario_maps[scene]].append(scene)
    groups = dict(sorted(groups.items()))

    def contrasts(chosen_seeds, chosen_scenes):
        def average(rows):
            return mean(mean(rows[scene] for scene in group) for group in chosen_scenes.values())
        av = mean(average(a[s]) for s in chosen_seeds)
        bv = mean(average(b[s]) for s in chosen_seeds)
        cv = average(bc)
        return dict(b_minus_a=bv-av, a_minus_bc=av-cv, b_minus_bc=bv-cv)

    point = contrasts(seeds, groups)
    draws = {key: [] for key in point}
    rng = random.Random(seed)
    for _ in range(samples):
        chosen_seeds = rng.choices(seeds, k=len(seeds))
        # One common scenario draw is used for every seed and both arms.
        chosen_scenes = {name: rng.choices(group, k=len(group)) for name, group in groups.items()}
        for key, value in contrasts(chosen_seeds, chosen_scenes).items():
            draws[key].append(value)
    intervals = {}
    for key, values in draws.items():
        values.sort()
        intervals[key] = [values[int(samples*.025)], values[min(samples-1, int(samples*.975))]]
    ba, bb = intervals['b_minus_a'], intervals['b_minus_bc']
    return dict(differences=point, interval95=intervals,
        per_seed={str(s): contrasts([s], groups) for s in seeds},
        training_seeds=len(seeds), scenarios=len(scenes), maps=len(groups),
        bootstrap=dict(method='paired crossed seed/scenario, scenarios stratified by map', samples=samples, seed=seed),
        predicates=dict(superior_to_a=ba[0]>0, inferior_to_a=ba[1]<0,
                        superior_to_bc=bb[0]>0, noninferior_to_bc_margin_05=bb[0]>-.05,
                        degraded_beyond_bc_margin_05=bb[1]<-.05))
