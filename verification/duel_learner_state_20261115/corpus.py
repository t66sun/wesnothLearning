"""Read-only audit and fixed training-target plans for #334."""
import argparse
from collections import Counter, defaultdict
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import random
import time

import torch

from learning.common import ROOT, read_json, sha256
from learning.coverage import matching, matches
from learning.data import record_split
from learning.features import schema
from learning.rowpack import ROW_SCHEMA, pack_line
from learning.sequences import _iter_rows, _validate_raw
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new
from verification.ppo_batch_comparison_20261107.driver import bc_endpoint, worker_identity
from verification.ppo_batch_comparison_20261107.panels import INPUTS as BASE
from verification.ppo_terminal_return_20261108.driver import PARENT, RULES

SOURCE_RUN = Path('/home/tongshu/acceptance/ppo322-formal-20261114-wGKDQ4/source/runs/ppo322')
SOURCE_SEEDS = (202611141, 202611142, 202611143)
SEEDS = (202611151, 202611152, 202611153)
TARGET_KINDS = ('move', 'recruit')
STEPS, SHARED, SWAPPED = 64, 48, 16
EXTENSION_SHA = '56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4'
SOURCE_LAUNCH_SHA = '835a2f973a9f80eea0360079c8109125dea086e5b6c2e9ac360352a428020a60'
ACTOR_FIELDS = ('global', 'opponents', 'spatial', 'candidates', 'turn')


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_inputs(commit):
    import _engine_lite

    worker = worker_identity(dict(source=str(ROOT), commit=commit, extension=_engine_lite.__file__,
                                  extension_sha256=EXTENSION_SHA))
    endpoint = bc_endpoint(PARENT)['endpoint']
    if (endpoint['version'] != 38 or any(endpoint[key] != value for key, value in BASE['base_bc'].items())
            or sha256(RULES/'rules.json') != BASE['rules_sha256']
            or sha256(SOURCE_RUN/'launch.json') != SOURCE_LAUNCH_SHA
            or read_json(SOURCE_RUN/'run-exit.json')['status'] != 'complete'):
        raise ValueError('frozen BC, Lite rules or source rollout identity differs')
    config = schema()
    worker['candidate_version'] = f"schema{config['version']}-"+config['candidate_selection']['version']
    return worker, endpoint


def lookup(path):
    result = {}
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['id'] in result:
                raise ValueError(f"duplicate reply {row['id']}: {path}")
            result[row['id']] = row
    return result


def provenance(job, reply):
    result, meta = reply['result'], job['meta']
    if (reply['status'] != 'complete' or not reply['training_eligible'] or not result['task_terminal']
            or result['faults'] or result['bots'] != job['bots'] or result['factions'] != job['factions']
            or job['task_id'] != BASE['task_id'] or result['task_id'] != BASE['task_id']
            or job['engine'] != 'lite' or job['max_turns'] != 30 or meta['teacher_lineage'] != BASE['astra']):
        raise ValueError(f"source game differs: {job['id']}")
    seat = meta['seat']
    return dict(game=job['id'], family=job['game_family'], scenario=job['scenario_family'], seat=seat,
                faction=job['factions'][seat-1], board=board_digest(job['map_override']), map=meta['map'],
                partition=record_split(job), rows=reply['training_shard']['raw_records'])


def check_row(row, game, candidate_version, source):
    if (row['schema'] != ROW_SCHEMA or row['task_id'] != BASE['task_id'] or row['format'] != 'duel'
            or row['rules_sha256'] != BASE['rules_sha256'] or row['candidate_version'] != candidate_version
            or row['engine_id'] != 'lite' or row['source'] != source or row['side'] != game['seat']
            or row['game_id'] != game['game'] or row['game_family'] != game['family']
            or row['scenario_family'] != game['scenario'] or row['faction'] != game['faction']
            or row['split'] != game['partition'] or row['split'] != record_split(row) or row['faults']):
        raise ValueError(f"row provenance differs in {game['game']}")


def stratum(game, row):
    return game['board'], game['seat'], game['faction'], row['actual']['kind'], ('1–5' if row['turn'] <= 5 else '6–30')


def teacher_targets(worker):
    from learning.export import validate_checkpoint

    checkpoint = validate_checkpoint(torch.load(PARENT/'duel/last_bc.pt', map_location='cpu',
                                                weights_only=False), 'duel')
    original = set(checkpoint['runner']['teacher_shards'])
    replies = lookup(PARENT/'duel/jobs.jsonl')
    games, shared, eligible, counts = [], [], defaultdict(list), Counter()
    for schedule in sorted((PARENT/'duel/schedules').glob('bc-batch-*.json')):
        for job in read_json(schedule):
            shard = job['shard']
            if shard not in original:
                continue
            original.remove(shard)
            game = provenance(job, replies[job['id']])
            counts[f"games_{game['partition']}"] += 1
            if game['partition'] != 'train':
                continue
            key = len(games)
            games.append(game | dict(shard=shard, sha256=file_sha(shard)))
            count = 0
            for row in _iter_rows(shard):
                check_row(row, game, worker['candidate_version'], 'astra')
                count += 1
                counts['train_rows'] += 1
                index = row['choice']
                if index < 0:
                    counts['train_unretained'] += 1
                    continue
                if matching(row['candidates'], row['actual']) != index:
                    raise ValueError(f"stored teacher intent differs in {game['game']}")
                _validate_raw(row, 'duel')
                ref = [key, row['decision']]
                shared.append(ref)
                if row['actual']['kind'] in TARGET_KINDS:
                    eligible[stratum(game, row)].append(ref)
            if count != game['rows']:
                raise ValueError(f"teacher shard count differs: {shard}")
    if original or sum(n for k, n in counts.items() if k.startswith('games_')) != BASE['bc_games']:
        raise ValueError('qualified teacher games do not match the frozen schedules')
    return games, shared, eligible, counts


def paired_rows(shard, labels, game, version, counts):
    """Verify the DAgger stream pairs to the complete actual learner sequence."""
    paired = zip_longest(_iter_rows(shard), _iter_rows(labels))
    rows = 0
    previous = (-1, 0)
    for policy, label in paired:
        rows += 1
        if policy is None or label is None:
            raise ValueError(f"sparse or unequal raw streams: {game['game']}")
        check_row(policy, game, version, 'policy')
        check_row(label, game, version, 'astra')
        position = policy['turn'], policy['decision']
        if (position != (label['turn'], label['decision']) or position[0] < previous[0]
                or position[1] <= previous[1] or (rows == 1 and position[0] != 1)
                or policy['version'] != game['version'] or label['version'] != game['version']
                or label['data_pool'] != 'dagger'):
            raise ValueError(f"broken learner chronology: {game['game']}")
        previous = position
        fields = ('committed', 'memory_write')
        if pack_line({k: policy.get(k) for k in fields}) != pack_line({k: label.get(k) for k in fields}):
            raise ValueError(f"learner memory write differs: {game['game']} decision {position[1]}")
        if not label.get('query_only'):
            if label['choice'] != -1:
                raise ValueError('an unsampled DAgger decision has a label')
            continue
        kind = label['actual']['kind']
        counts['queries'] += 1
        counts[f'query_{kind}'] += 1
        fields = ACTOR_FIELDS
        if pack_line({k: policy[k] for k in fields}) != pack_line({k: label[k] for k in fields}):
            raise ValueError(f"queried actor input differs: {game['game']} decision {position[1]}")
        index = matching(policy['candidates'], label['actual'])
        if index != label['choice']:
            raise ValueError(f"stored query choice differs: {game['game']} decision {position[1]}")
        if index < 0:
            counts[f'unretained_{kind}'] += 1
            continue
        counts[f'retained_{kind}'] += 1
        if kind not in TARGET_KINDS:
            continue
        counts[f"eligible_{game['map']}"] += 1
        counts[f"{'agree' if matches(policy['actual'], label['actual']) else 'disagree'}_{kind}"] += 1
        _validate_raw(label, 'duel')
        yield label
    if rows != game['rows']:
        raise ValueError(f"learner shard count differs: {game['game']}")


def learner_targets(worker):
    games, eligible, counts = [], defaultdict(list), Counter()
    for seed in SOURCE_SEEDS:
        arm = f'astra-{seed}'
        cell = SOURCE_RUN/'cells'/arm
        duel = cell/'duel'
        budget = read_json(cell/'budget.json')
        ledger = read_json(SOURCE_RUN/f'{arm}-ledger.json')
        history = read_json(duel/'state.json')['history'][budget['history_start']:]
        if ledger['settled_batches'] != len(history) or len(history) < 12 or ledger['opponents'] != {'astra': 8*len(history)}:
            raise ValueError(f'frozen pure-Astra ledger differs: {arm}')
        replies = lookup(duel/'jobs.jsonl')
        exports, stream = {}, []
        for entry in history[:12]:
            jobs = read_json(duel/'schedules'/f"ppo-batch-{entry['batch']:06}.json")
            if len(jobs) != 8:
                raise ValueError('settled batch is short')
            for job in jobs:
                game = provenance(job, replies[job['id']])
                seat = game['seat']
                control = job['bots'][2-seat]
                opponent = job['meta']['experimental_opponent']
                learner = job['learning']['sides'][str(seat)]
                if (opponent['kind'] != 'astra' or opponent['side'] != 3-seat
                        or opponent['sha256'] != BASE['astra']['teacher_parent_sha256']
                        or job['learning']['dagger_teacher'] != control or game['partition'] != 'train'):
                    raise ValueError(f'learner job is outside the preregistered cohort: {job["id"]}')
                stream.append([game['scenario'], game['family'], job['seed'], job['factions'],
                               seat, learner['sampling_seed']])
                addon = Path(job['bots'][seat-1])
                if addon not in exports:
                    exports[addon] = file_sha(addon.parent/'model.pt')
                shard = Path(job['shard'])
                labels = shard.with_name(shard.name.replace('.jsonl.gz', '.dagger.jsonl.gz'))
                game.update(shard=str(shard), sha256=file_sha(shard), labels=str(labels), labels_sha256=file_sha(labels),
                            source_seed=seed, version=learner['version'], model_sha256=exports[addon])
                key = len(games)
                games.append(game)
                for label in paired_rows(shard, labels, game, worker['candidate_version'], counts):
                    eligible[stratum(game, label)].append([key, label['decision']])
        if stream != ledger['stream'][:96]:
            raise ValueError(f'source jobs differ from the settled prefix: {arm}')
    if len(games) != 288 or len({g['family'] for g in games}) != len(games):
        raise ValueError('source learner game families differ from the 288-game design')
    return games, eligible, counts


def spread(pairs, learner_games):
    from params import FACTIONS

    games = [learner_games[right[0]] for _, right in pairs]
    stat = dict(families=len({g['family'] for g in games}), maps=sorted({g['map'] for g in games}),
                seats=sorted({g['seat'] for g in games}), factions=sorted({g['faction'] for g in games}))
    stat['passed'] = stat['families'] >= 64 and len(stat['maps']) >= 3 and stat['seats'] == [1, 2] and stat['factions'] == sorted(FACTIONS)
    return stat


def plans(shared, teacher, learner, learner_games):
    support = []
    frozen = {}
    for seed in SEEDS:
        rng = random.Random(seed)
        pairs = []
        for key in sorted(learner.keys() & teacher.keys()):
            left, right = list(teacher[key]), list(learner[key])
            rng.shuffle(left)
            rng.shuffle(right)
            pairs.extend(zip(left, right))
        rng.shuffle(pairs)
        selected = pairs[:STEPS*SWAPPED]
        stat = spread(selected, learner_games)
        stat.update(seed=seed, available=len(pairs), selected=len(selected))
        stat['passed'] &= len(selected) == STEPS*SWAPPED
        support.append(stat)
        if stat['passed']:
            used = {tuple(left) for left, _ in selected}
            common = rng.sample([ref for ref in shared if tuple(ref) not in used], STEPS*SHARED)
            frozen[str(seed)] = [
                dict(shared=common[i*SHARED:(i+1)*SHARED], swaps=selected[i*SWAPPED:(i+1)*SWAPPED])
                for i in range(STEPS)]
    return support, frozen


def audit(output, commit, archive):
    started = time.monotonic()
    worker, endpoint = verify_inputs(commit)
    teacher_games, shared, teacher, teacher_counts = teacher_targets(worker)
    learner_games, learner, learner_counts = learner_targets(worker)
    support, frozen = plans(shared, teacher, learner, learner_games)
    passed = all(stat['passed'] for stat in support)
    details = [dict(board=key[0], seat=key[1], faction=key[2], kind=key[3], rounds=key[4],
                    teacher=len(teacher.get(key, [])), learner=len(learner.get(key, [])))
               for key in sorted(teacher.keys() | learner.keys())]
    write_new(output/'audit.json', dict(source_commit=commit, archive_sha256=file_sha(archive),
              worker=worker, endpoint=endpoint, teacher_counts=teacher_counts, learner_counts=learner_counts,
              learner_games=len(learner_games), strata=details, support=support, passed=passed,
              seconds=time.monotonic()-started))
    if passed:
        write_new(output/'corpus.json', dict(teacher=teacher_games, learner=learner_games, plans=frozen))
    print(json.dumps(dict(passed=passed, support=support, teacher=teacher_counts, learner=learner_counts)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('commit')
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    audit(args.output, args.commit, args.archive)
