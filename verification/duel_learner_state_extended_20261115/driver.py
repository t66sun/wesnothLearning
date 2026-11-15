"""Prepare or execute the single authorized #336 comparison."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import shutil
from statistics import mean
import tarfile
import time
from unittest.mock import patch

import torch

from learning.bc_anchor import weights_sha256
from learning.common import ROOT, read_json
from learning.evaluate import official_score
from learning.export import export, load_model
from learning.sample import collect
from verification.duel_learner_state_20261115 import corpus
from verification.duel_ppo_comparison_20261106.audit import write_new
from verification.duel_ppo_comparison_20261106.contract import crossed_statistics
from verification.ppo_terminal_return_20261108 import driver as prior
from . import protocol, trainer

HERE = Path(__file__).resolve().parent
INPUTS_PATH = HERE/'inputs.json'
CHECKPOINT = corpus.PARENT/'duel/last_bc.pt'


def load_corpus(inputs):
    with gzip.open(HERE/'corpus.json.gz', 'rb') as stream:
        raw = stream.read()
    if hashlib.sha256(raw).hexdigest() != inputs['corpus_sha256']:
        raise ValueError('frozen corpus differs')
    return json.loads(raw)


def verify(inputs, commit):
    worker, endpoint = corpus.verify_inputs(commit)
    frozen = inputs['environment']
    if (any(worker[key] != frozen[key] for key in ('extension_sha256', 'teacher', 'candidate_version'))
            or any(endpoint[key] != value for key, value in inputs['checkpoint'].items())
            or inputs['limits'] != protocol.LIMITS or inputs['order'] != [list(pair) for pair in protocol.ORDER]
            or corpus.file_sha(HERE/'audit.json') != inputs['audit_sha256']):
        raise ValueError('frozen experimental inputs differ')
    parent = read_json(corpus.PARENT/'manifest.json')
    control = parent['opponents'][0]['path']
    if corpus.file_sha(control) != frozen['teacher']['teacher_parent_sha256']:
        raise ValueError('frozen evaluation opponent differs')
    return control, parent['baseline']['path']


def policy_paths(output):
    return {role: str(output/'policies'/role/'FrozenDuel') for role in protocol.ROLES}


def prepare(output, commit, archive):
    inputs = read_json(INPUTS_PATH)
    control, wesnoth = verify(inputs, commit)
    data = load_corpus(inputs)
    if set(data['plans']) != {str(seed) for seed in corpus.SEEDS}:
        raise ValueError('source plans do not cover the three paired seeds')
    output.mkdir()
    jobs = protocol.schedule(output, HERE/'boards', inputs, policy_paths(output), control, wesnoth, 0)
    if protocol.slots(jobs, read_json(corpus.RULES/'rules.json')) != inputs['slots']:
        raise ValueError('formal job template differs from frozen paired slots')
    schedule = output/'schedule.json'
    write_new(schedule, jobs)
    launch = dict(commit=commit, archive=str(archive.resolve()), archive_sha256=corpus.file_sha(archive),
                  inputs_sha256=corpus.file_sha(INPUTS_PATH), schedule_sha256=corpus.file_sha(schedule),
                  corpus_sha256=inputs['corpus_sha256'], source=str(ROOT), limits=inputs['limits'],
                  checkpoint=inputs['checkpoint'], roles=list(protocol.ROLES), games=len(jobs))
    write_new(output/'launch.json', launch)
    print(f"launch_sha256 {corpus.file_sha(output/'launch.json')}", flush=True)


def evaluate(output, request, inputs):
    torch.set_num_threads(inputs['trainer_threads'])
    endpoints = read_json(output/'endpoints.json')
    paths = policy_paths(output)
    for role, addon in paths.items():
        endpoint = endpoints[role]
        path = Path(endpoint['path'])
        if corpus.file_sha(path) != endpoint['sha256']:
            raise ValueError(f'checkpoint differs: {role}')
        model, _ = load_model(path, 'duel')
        if weights_sha256(model.state_dict()) != endpoint['weights_sha256']:
            raise ValueError(f'tensors differ: {role}')
        destination = Path(addon).parent
        export(model, destination, name='FrozenDuel', mode='greedy', version=role, package=False)
        shutil.copyfile(path, destination/'model.pt')
    jobs = read_json(output/'schedule.json')
    for job in jobs:
        job['deadline'] = request['deadline']
    return dict(replies=len(collect(jobs, inputs['workers'], output/'results.jsonl')))


def adoption_gate(summary, minimum, scenarios):
    # Each crossed draw has the same count of seeds, scenarios and seat rotations.
    # Use raw score units so floating-point subtraction at a gate cannot move it.
    max_points = len(corpus.SEEDS) * scenarios * 2 * 3
    minimum_points = Fraction(str(minimum)) * max_points
    return all(round(summary['differences'][key] * max_points) >= minimum_points
               and round(summary['interval95'][key][0] * max_points) > 0
               for key in ('b_minus_a', 'b_minus_bc'))


def recount(jobs, replies, inputs):
    original = {job['id']: job for job in jobs}
    if len(jobs) != 1260 or len(original) != 1260 or len(replies) != 1260 or {r['id'] for r in replies} != original.keys():
        raise ValueError('missing or duplicate official evaluation replies')
    slot_index = {(s['map'], s['block'], s['rotation']): s for s in inputs['slots']}
    outcomes = defaultdict(Counter)
    scores = defaultdict(dict)
    scene_maps = {}
    for reply in replies:
        job = original[reply['id']]
        meta, result = job['meta'], reply.get('result', {})
        seat, = meta['policy_sides']
        board, block, rotation, role = (meta[k] for k in ('map', 'block', 'rotation', 'role'))
        slot = slot_index[board, block, rotation]
        if (reply['status'] != 'complete' or reply['meta'] != meta or reply['engine'] != 'lite'
                or result['faults'] or not result['task_terminal'] or result['task_id'] != inputs['task']
                or result['winner'] not in (0, 1, 2) or result['bots'] != job['bots'] or result['factions'] != job['factions']
                or (job['seed'], seat, job['factions'], job['scenario_family']) !=
                   (slot['seed'], slot['seat'], slot['factions'], slot['scenario'])):
            raise ValueError(f"faulted or mismatched reply: {reply['id']}")
        scenario = slot['scenario']
        scene_maps[scenario] = board
        if role not in protocol.ROLES or rotation in scores[role, scenario]:
            raise ValueError('duplicated role or scenario rotation')
        points = official_score(result, seat)
        outcomes[board, role][{3: 'wins', 1: 'draws', 0: 'losses'}[points]] += 1
        scores[role, scenario][rotation] = points
    if len(scene_maps) != 90 or any(set(rows) != {0, 1} for rows in scores.values()):
        raise ValueError('paired scenario count or rotation differs')
    role_scores = {role: {scenario: sum(scores[role, scenario].values())/6 for scenario in scene_maps}
                   for role in protocol.ROLES}
    result = crossed_statistics({seed: role_scores[f'teacher-{seed}'] for seed in corpus.SEEDS},
                                {seed: role_scores[f'learner-{seed}'] for seed in corpus.SEEDS},
                                role_scores['bc'], scene_maps,
                                seed=inputs['bootstrap_seed'], samples=inputs['bootstrap_samples'])
    result['per_map'] = {
        board: {role: dict(outcomes[board, role], score=mean(value for scene, value in role_scores[role].items()
                                                            if scene_maps[scene] == board))
                for role in protocol.ROLES}
        for board in inputs['maps']}
    result['score_means'] = {role: mean(row[role]['score'] for row in result['per_map'].values())
                             for role in protocol.ROLES}
    result['passed'] = adoption_gate(result, inputs['minimum_gain'], len(scene_maps))
    return result


def stage(output, request):
    inputs = read_json(INPUTS_PATH)
    action, label = request['action'], request['label']
    if action == 'fit':
        folder = output/'cells'/label
        trainer.fit(folder, request['seed'], request['role'], load_corpus(inputs), inputs, request['deadline'])
        result = read_json(folder/'endpoint.json')
    elif action == 'panel':
        result = evaluate(output, request, inputs)
    elif action == 'audit':
        with (output/'results.jsonl').open(encoding='utf-8') as stream:
            result = recount(read_json(output/'schedule.json'), list(map(json.loads, stream)), inputs)
    else:
        raise ValueError(f'unknown stage {action}')
    write_new(output/f'{label}-result.json', result)


def run_stage(output, label, action, deadline, **options):
    with patch.object(prior, '__spec__', __spec__):
        outcome = prior.run_stage(output, label, action, deadline, **options)
    if outcome['finished'] > deadline:
        raise RuntimeError(f'{label} crossed its frozen deadline')
    return outcome


def run(output, expected):
    manifest = output/'launch.json'
    if corpus.file_sha(manifest) != expected:
        raise ValueError('launch SHA-256 differs from approved identity')
    launch = read_json(manifest)
    started = time.time()
    limits = protocol.LIMITS
    deadline = started + limits['total']
    write_new(output/'run-start.json', dict(started=started, deadline=deadline, launch_sha256=expected))
    status = 'incomplete'
    verdict = False
    try:
        inputs = read_json(INPUTS_PATH)
        verify(inputs, launch['commit'])
        load_corpus(inputs)
        if (launch['archive_sha256'] != corpus.file_sha(launch['archive']) or launch['source'] != str(ROOT)
                or launch['inputs_sha256'] != corpus.file_sha(INPUTS_PATH)
                or launch['schedule_sha256'] != corpus.file_sha(output/'schedule.json')
                or time.time() > started+limits['preflight']):
            raise ValueError('approved source or launch inputs changed, or preflight is overdue')
        endpoints = dict(bc=dict(path=str(CHECKPOINT), sha256=inputs['checkpoint']['checkpoint_sha256'],
                                 weights_sha256=inputs['checkpoint']['weights_sha256']))
        for role, seed in protocol.ORDER:
            label = f'{role}-{seed}'
            run_stage(output, label, 'fit', min(time.time()+limits['cell'], deadline), seed=seed, role=role)
            endpoint = read_json(output/f'{label}-result.json')
            if endpoint['steps'] != 64 or endpoint['visits'] != 4096:
                raise ValueError(f'endpoint failed its exact-work contract: {label}')
            endpoints[label] = endpoint
        write_new(output/'endpoints.json', endpoints)
        run_stage(output, 'panel', 'panel', min(time.time()+limits['games'], deadline))
        audit_limit = min(time.time()+limits['audit'], deadline)
        run_stage(output, 'audit', 'audit', audit_limit)
        with tarfile.open(output/'raw-metadata.tar.gz', 'x:gz', compresslevel=1) as bundle:
            for path in sorted(output.glob('*')):
                if path.is_file() and path.suffix in ('.json', '.jsonl', '.log'):
                    bundle.add(path, arcname=path.name)
        if time.time() > audit_limit:
            raise RuntimeError('archiving exceeded the audit budget')
        verdict = read_json(output/'audit-result.json')['passed']
        status = 'complete'
    finally:
        write_new(output/'run-exit.json', dict(status=status, passed=verdict, started=started,
                                              finished=time.time(), deadline=deadline))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'stage'))
    parser.add_argument('output', type=lambda path: Path(path).resolve())
    parser.add_argument('--commit')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--launch-sha256')
    parser.add_argument('--request', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output, args.commit, args.archive)
    elif args.action == 'run':
        run(args.output, args.launch_sha256)
    else:
        stage(args.output, read_json(args.request))
