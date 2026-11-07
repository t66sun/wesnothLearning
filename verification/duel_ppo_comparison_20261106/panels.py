"""Freeze checkpoint roles and execute this experiment's two matched panels."""
from collections import defaultdict
from pathlib import Path
from statistics import mean
import time

import torch

from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.evaluate import official_score
from learning.experiment import FormatExperiment, run_lock
from learning.export import export, load_model
from learning.maps import bind_scenario
from learning.phases import apply_phase, request_phase
from learning.progress import checkpoint_roles
from learning.sample import collect
from learning.schedule import evaluation_jobs
from learning.tasks import TASK_ID, reward_config
from .audit import shard_boards, write_new
from .contract import INPUTS, aliases, crossed_statistics


def role(path):
    loaded = torch.load(path, map_location='cpu', weights_only=False)
    if loaded['runner'].get('pending_train'):
        raise ValueError('incomplete checkpoint cannot enter a scored panel')
    return dict(path=str(path), checkpoint_sha256=sha256(path), version=loaded['runner']['version'],
                weights_sha256=weights_sha256(loaded['model']))


def freeze_roles(output, bc_root, cells, deadline):
    roles = {'bc': role(bc_root / 'duel/last_bc.pt')}
    for cell in cells:
        root = Path(cell['run'])
        with run_lock(root):
            # This calls selection only. Pending optimization is never resumed
            # using evaluation time, and holdout does not start here.
            if time.time() < deadline:
                request_phase(root, 'evaluate', hours=(deadline-time.time())/3600)
            manifest, clock = read_json(root / 'manifest.json'), read_json(root / 'clock.json')
            runner = FormatExperiment(root/'duel', 'duel', manifest, clock,
                lambda jobs, log: collect(jobs, INPUTS['workers'], log), resume=True)
            apply_phase(runner)
            selected, _, _ = runner._select_final()
            current = checkpoint_roles(root / 'duel')
            roles[cell['name']+'/selected'] = role(selected)
            roles[cell['name']+'/latest'] = role(Path(current['latest']['path']))
            write_new(output / (cell['name']+'-exposure.json'), shard_boards(runner.state))
    write_new(output / 'roles.json', roles)
    return roles


def make_panel(output, roles, parent_manifest, *, partition, deadline):
    unique, mapping = aliases(roles)
    output.mkdir(parents=True, exist_ok=False)
    control = parent_manifest['opponents'][0]['path']
    if sha256(control) != INPUTS['opponent_sha256']:
        raise ValueError('panel opponent differs')
    blocks = 15 if partition == 'validation' else 30
    seed = INPUTS['validation_seed' if partition == 'validation' else 'holdout_seed']
    jobs = []
    for key, checkpoint in unique.items():
        model, state = load_model(checkpoint['path'], 'duel')
        if weights_sha256(state['model']) != key or sha256(checkpoint['path']) != checkpoint['checkpoint_sha256']:
            raise ValueError('checkpoint changed before export')
        destination = output / 'policies' / key
        name = 'DuelComparison'
        export({'duel': model}, destination, name=name, mode='greedy', package=False,
               version=str(checkpoint['version']))
        torch.save(dict(model=model.state_dict(), features=state['features'], architecture=state['architecture'],
                        format='duel'), destination / 'model.pt')
        label = ('final-' if partition == 'holdout' else 'comparison-') + key[:16]
        planned = evaluation_jobs(output, str(destination/name), control, [control], blocks, seed,
            deadline, parent_manifest['baseline']['path'], label=label, formats=['duel'], min_distinct=12)
        for job in planned:
            job.update(engine='lite', rules_dir=INPUTS['rules_dir'], allow_approximate=True,
                       score_only_astra=True, score_only_policy=True,
                       task_id=TASK_ID, reward_config=reward_config(mode='fixed'))
            job['meta'].update(weights_sha256=key, rules_sha256=INPUTS['rules_sha256'])
            bind_scenario(job)
        jobs.extend(planned)
    jobs.sort(key=lambda j: (j['meta']['block'], j['meta']['rotation'], j['meta']['weights_sha256']))
    plan = dict(partition=partition, blocks=blocks, seed=seed, deadline=deadline,
                aliases=mapping, distinct_policies=len(unique), roles=roles, jobs=jobs)
    write_new(output/'plan.json', plan)
    return plan


def panel_scores(plan, results):
    """One physical result may serve several equal-weight roles, once each."""
    lookup = {row['id']: row for row in results}
    groups, missing, scenario_maps = defaultdict(list), [], {}
    for job in plan['jobs']:
        meta = job['meta']
        scene = job['scenario_family']
        scenario_maps[scene] = meta['map']
        groups[meta['weights_sha256'], scene].append(job)
    scores = defaultdict(dict)
    for (key, scene), jobs in groups.items():
        rows = [lookup.get(job['id']) for job in jobs]
        if (len(jobs) != 2 or {j['meta']['rotation'] for j in jobs} != {0, 1}
                or any(not r or r['status'] != 'complete' or r['result'].get('faults') for r in rows)):
            missing.append(dict(weights=key, scenario=scene))
            continue
        scores[key][scene] = mean(official_score(row['result'], job['meta']['policy_sides'][0])/3.
                                  for job, row in zip(jobs, rows))
    # Verify physical scenario and combat-seed matching for every actual policy.
    design = defaultdict(dict)
    for job in plan['jobs']:
        design[job['meta']['weights_sha256']][job['scenario_family'], job['meta']['rotation']] = job['seed']
    if not design or any(len(value) != 2*plan['blocks'] for value in design.values()):
        raise ValueError('policy panel does not contain its complete scenario roster')
    if design and any(value != next(iter(design.values())) for value in design.values()):
        raise ValueError('policy panels have unmatched scenarios or seeds')
    return dict(complete=not missing, missing=missing, scenario_maps=scenario_maps,
                roles={name: scores[key] for name, key in plan['aliases'].items()})


def comparison(plan, results, cells):
    scored = panel_scores(plan, results)
    output = dict(partition=plan['partition'], blocks=plan['blocks'], distinct_policies=plan['distinct_policies'],
                  complete=scored['complete'], missing=scored['missing'], aliases=plan['aliases'])
    if not scored['complete']:
        output['status'] = 'incomplete_panel'
        return output
    for checkpoint_role in ('latest', 'selected'):
        a, b = {}, {}
        for cell in cells:
            target = a if cell['mode'] == 'historical_action' else b
            target[cell['seed']] = scored['roles'][cell['name']+'/'+checkpoint_role]
        output[checkpoint_role] = crossed_statistics(a, b, scored['roles']['bc'], scored['scenario_maps'],
            seed=INPUTS['analysis_seed'], samples=INPUTS['bootstrap_samples'])
    output['status'] = 'observed'
    return output


def execute(output, bc_root, cells, hard_deadline):
    started = time.time()
    validation_deadline = min(hard_deadline-3600, started+INPUTS['seconds']['selection_validation'])
    roles = freeze_roles(output, bc_root, cells, validation_deadline)
    manifest = read_json(bc_root/'manifest.json')
    reports = {}
    for partition, deadline in (('validation', validation_deadline), ('holdout', hard_deadline)):
        plan = make_panel(output/partition, roles, manifest, partition=partition, deadline=deadline)
        results = collect(plan['jobs'], INPUTS['workers'], output/partition/'results.jsonl')
        write_new(output/partition/'results.json', results)
        reports[partition] = comparison(plan, results, cells)
        write_new(output/partition/'summary.json', reports[partition])
    write_new(output/'summary.json', dict(wall_seconds=time.time()-started, **reports))
    return reports
