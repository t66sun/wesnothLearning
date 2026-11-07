"""One paired duel design, evaluated by each arm's actual source contract."""
from itertools import permutations
from pathlib import Path
import time

import torch

from learning import experiment
from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.export import export, load_model
from learning.maps import bind_scenario, run_family
from learning.phases import apply_phase, request_phase
from learning.sample import collect
from learning.schedule import evaluation_jobs, starting_factions
from learning.tasks import reward_config
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new
from verification.duel_ppo_comparison_20261106.contract import aliases, crossed_statistics
from verification.duel_ppo_comparison_20261106.panels import panel_scores, role

INPUTS = read_json(Path(__file__).with_name('inputs.json'))
ROUTES = ('a', 'b', 'c')


def select_checkpoint(cell, deadline):
    root = Path(cell['run'])
    with experiment.run_lock(root):
        request_phase(root, 'evaluate', hours=(deadline-time.time())/3600)
        runner = experiment.FormatExperiment(
            root/'duel', 'duel', read_json(root/'manifest.json'), read_json(root/'clock.json'),
            lambda jobs, log: collect(jobs, INPUTS['workers'], log), resume=True)
        apply_phase(runner)
        selected, _, _ = runner._select_final()
        record = role(selected)
    if record['version'] > cell['roles']['wall']['version']:
        raise ValueError('selection exceeded the complete wall-clock endpoint')
    return record


def roster(partition):
    pairs = starting_factions(2, 'duel')
    if partition == 'holdout':
        factions = sorted({name for pair in pairs for name in pair})
        pairs = permutations(factions, 2)
    return [dict(map_index=0, factions=list(pair)) for pair in pairs]


def plan_jobs(output, addon, control, wesnoth, key, deadline, rules_dir, partition, board=None):
    scenarios = roster(partition)
    label = ('final-' if partition == 'holdout' else 'comparison-') + key
    seed = INPUTS['holdout_seed' if partition == 'holdout' else 'validation_seed']
    jobs = evaluation_jobs(output, addon, control, [control], len(scenarios), seed,
                           deadline, wesnoth, label=label, formats=['duel'], scenarios=scenarios)
    for job in jobs:
        job.update(engine='lite', rules_dir=rules_dir, allow_approximate=True,
                   score_only_astra=True, score_only_policy=True,
                   task_id=INPUTS['task_id'], reward_config=reward_config(mode='fixed'))
        job['meta'].update(weights_sha256=key, rules_sha256=INPUTS['rules_sha256'])
        if partition == 'holdout':
            job['map_override'] = board['board']
            job['meta'].update(map=board['name'], map_sha256=board['file_sha256'])
            job['game_family'] = run_family(job)
        bind_scenario(job)
    return jobs


def panel_view(jobs, names, mapping, blocks, results):
    role_keys = {name: mapping[name] for name in names}
    keys = set(role_keys.values())
    selected = [job for job in jobs if job['meta']['weights_sha256'] in keys
                and job['meta']['block'] < blocks]
    design = sorted({(job['scenario_family'], job['seed'], job['meta']['rotation'],
                      tuple(job['meta']['policy_sides'])) for job in selected})
    scored = panel_scores(dict(jobs=selected, aliases=role_keys, blocks=blocks), results)
    return dict(scored, design=design)


def execute(output, request, deadline):
    roles, partition = request['roles'], request['partition']
    board = request.get('board')
    if partition == 'holdout' and board_digest(board['board']) != INPUTS['holdout']['board_sha256']:
        raise ValueError('frozen holdout board changed')
    unique, mapping = aliases(roles)
    parent = read_json(Path(request['parent'])/'manifest.json')
    control = parent['opponents'][0]['path']
    if sha256(control) != INPUTS['astra']['teacher_parent_sha256']:
        raise ValueError('panel Astra package changed')
    full, small = request['full'], request['small']
    full_keys = {mapping[name] for name in full}
    jobs = []
    output.mkdir(parents=True, exist_ok=False)
    for key, checkpoint in unique.items():
        path = checkpoint['path']
        model, state = load_model(path, 'duel')
        if weights_sha256(state['model']) != key or sha256(path) != checkpoint['checkpoint_sha256']:
            raise ValueError('checkpoint changed before evaluation')
        destination = output/'policies'/key
        export({'duel': model}, destination, name='DuelComparison', package=False,
               version=str(checkpoint['version']))
        torch.save(dict(model=model.state_dict(), features=state['features'],
                        architecture=state['architecture'], format='duel'), destination/'model.pt')
        planned = plan_jobs(output, str(destination/'DuelComparison'), control,
                            parent['baseline']['path'], key, deadline, parent['config']['rules_dir'],
                            partition, board)
        jobs.extend(planned if key in full_keys else
                    [job for job in planned if job['meta']['block'] < INPUTS['small_validation_blocks']])
    jobs.sort(key=lambda job: (job['meta']['block'], job['meta']['rotation'], job['meta']['weights_sha256']))
    write_new(output/'plan.json', dict(partition=partition, roles=roles, aliases=mapping, jobs=jobs))
    results = collect(jobs, INPUTS['workers'], output/'results.jsonl')
    write_new(output/'results.json', results)
    report = dict(full=panel_view(jobs, full, mapping, len(roster(partition)), results))
    if small:
        report['small'] = panel_view(jobs, small, mapping, INPUTS['small_validation_blocks'], results)
    report['planned_games'] = len(jobs)
    report['actual_games'] = sum(row['status'] == 'complete' and not row['result'].get('faults')
                                 for row in results)
    write_new(output/'summary.json', report)


def paired_rows(reports, panel):
    combined = dict(roles={}, scenario_maps={}, missing=[])
    design = None
    for report in reports:
        if panel not in report:
            continue
        data = report[panel]
        if design is not None and design != data['design']:
            raise ValueError('source-specific panels differ in physical scenarios, seats or combat seeds')
        design = data['design']
        combined['roles'].update(data['roles'])
        combined['scenario_maps'].update(data['scenario_maps'])
        combined['missing'].extend(data['missing'])
    return combined


def comparison(rows, route, endpoint):
    scores = rows['roles']
    seed_set = INPUTS['seeds']
    baseline = {seed: scores.get(f'base-{seed}/{endpoint}') for seed in seed_set}
    variant = {seed: scores.get(f'{route}-{seed}/{endpoint}') for seed in seed_set}
    shared_bc = scores.get('base/bc')
    own_bc = scores.get(f'{route}/bc', shared_bc)
    scenes = set(rows['scenario_maps'])
    matched = [seed for seed in seed_set
               if set(baseline[seed] or {}) == set(variant[seed] or {}) == scenes and scenes]
    if matched != seed_set or not scenes or set(shared_bc or {}) != scenes or set(own_bc or {}) != scenes:
        return dict(status='incomplete', matched_seeds=matched)
    options = dict(seed=INPUTS['bootstrap_seed'], samples=INPUTS['bootstrap_samples'])
    result = crossed_statistics(baseline, variant, shared_bc, rows['scenario_maps'], **options)
    own = (result if own_bc is shared_bc else
           crossed_statistics(baseline, variant, own_bc, rows['scenario_maps'], **options))
    fields = dict(route_minus_baseline=(result, 'b_minus_a'), baseline_minus_bc=(result, 'a_minus_bc'),
                  route_minus_own_bc=(own, 'b_minus_bc'))
    return dict(status='observed', training_seeds=matched, scenarios=result['scenarios'], maps=result['maps'],
                bootstrap=result['bootstrap'],
                **{name: dict(point=stats['differences'][key], interval95=stats['interval95'][key],
                              per_seed={seed: row[key] for seed, row in stats['per_seed'].items()})
                   for name, (stats, key) in fields.items()})


def summarize(reports, partition):
    full = paired_rows(reports, 'full')
    contrasts = {route: {'wall': comparison(full, route, 'wall')} for route in ROUTES}
    if partition == 'validation':
        small = paired_rows(reports, 'small')
        for route, values in contrasts.items():
            values.update({key: comparison(rows, route, key) for key, rows in
                           [('10000', small), ('30000', full), ('selected', full)]})
    return dict(contrasts=contrasts, actual_games=sum(report['actual_games'] for report in reports),
                missing=full['missing'])


def deployment_choice(validation):
    """Nominate a route on validation only; confirmation governs adoption."""
    eligible = []
    for route in ROUTES:
        result = validation['contrasts'][route]['wall']
        if (result['status'] == 'observed' and result['route_minus_baseline']['interval95'][0] > 0
                and result['route_minus_own_bc']['interval95'][0] > 0):
            eligible.append(route)
    if not eligible:
        return None
    return max(eligible, key=lambda route: validation['contrasts'][route]['wall']['route_minus_baseline']['point'])
