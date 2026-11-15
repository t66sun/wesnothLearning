"""Find the first common archived prefix that passes the #334 support gate."""
import argparse
import json
from pathlib import Path
import time

from learning.common import read_json
from verification.duel_learner_state_20261115 import corpus
from verification.duel_ppo_comparison_20261106.audit import write_new

BASE_BATCHES = 12


def cells():
    result = []
    for seed in corpus.SOURCE_SEEDS:
        arm = f'astra-{seed}'
        root = corpus.SOURCE_RUN/'cells'/arm
        duel = root/'duel'
        budget = read_json(root/'budget.json')
        ledger = read_json(corpus.SOURCE_RUN/f'{arm}-ledger.json')
        history = read_json(duel/'state.json')['history'][budget['history_start']:]
        if ledger['settled_batches'] != len(history) or ledger['opponents'] != {'astra': 8*len(history)}:
            raise ValueError(f'frozen pure-Astra ledger differs: {arm}')
        result.append(dict(seed=seed, duel=duel, history=history, stream=ledger['stream'],
                           replies=corpus.lookup(duel/'jobs.jsonl'), exports={}))
    return result


def add_batch(cell, offset, worker, games, labels_by_stratum, counts):
    entry = cell['history'][offset]
    path = cell['duel']/'schedules'/f"ppo-batch-{entry['batch']:06}.json"
    jobs = read_json(path)
    if len(jobs) != 8:
        raise ValueError(f'settled batch count differs: {path}')
    stream = []
    for job in jobs:
        game = corpus.provenance(job, cell['replies'][job['id']])
        seat = game['seat']
        opponent = job['meta']['experimental_opponent']
        learner = job['learning']['sides'][str(seat)]
        control = job['bots'][2-seat]
        if (opponent['kind'] != 'astra' or opponent['side'] != 3-seat
                or opponent['sha256'] != corpus.BASE['astra']['teacher_parent_sha256']
                or job['learning']['dagger_teacher'] != control or game['partition'] != 'train'):
            raise ValueError(f'learner job is outside the pure-Astra cohort: {job["id"]}')
        stream.append([game['scenario'], game['family'], job['seed'], job['factions'], seat, learner['sampling_seed']])
        addon = Path(job['bots'][seat-1])
        if addon not in cell['exports']:
            cell['exports'][addon] = corpus.file_sha(addon.parent/'model.pt')
        shard = Path(job['shard'])
        label_path = shard.with_name(shard.name.replace('.jsonl.gz', '.dagger.jsonl.gz'))
        game.update(shard=str(shard), sha256=corpus.file_sha(shard), labels=str(label_path),
                    labels_sha256=corpus.file_sha(label_path), source_seed=cell['seed'],
                    version=learner['version'], model_sha256=cell['exports'][addon])
        index = len(games)
        games.append(game)
        for row in corpus.paired_rows(shard, label_path, game, worker['candidate_version'], counts):
            labels_by_stratum[corpus.stratum(game, row)].append([index, row['decision']])
    if stream != cell['stream'][offset*8:(offset+1)*8]:
        raise ValueError(f'settled stream differs: {path}')


def freeze(output, commit, archive):
    started = time.monotonic()
    worker, endpoint = corpus.verify_inputs(commit)
    teacher_games, shared, teacher, teacher_counts = corpus.teacher_targets(worker)
    learner_games, learner, learner_counts = corpus.learner_targets(worker)
    original_games = len(learner_games)
    source_cells = cells()
    trace = []
    for batches in range(BASE_BATCHES, min(len(c['history']) for c in source_cells)+1):
        if batches > BASE_BATCHES:
            for cell in source_cells:
                add_batch(cell, batches-1, worker, learner_games, learner, learner_counts)
        num_games = batches * 8 * len(source_cells)
        if len(learner_games) != num_games or len({g['family'] for g in learner_games}) != num_games:
            raise ValueError('archived learner game families repeat across the audited prefix')
        support, frozen = corpus.plans(shared, teacher, learner, learner_games)
        passed = len(frozen) == len(corpus.SEEDS)
        trace.append(dict(batches_per_cell=batches, games=num_games, support=support, passed=passed))
        print(json.dumps(dict(batches=batches, games=num_games, pairs=support[0]['available'], passed=passed)), flush=True)
        if passed:
            break
    details = [dict(board=key[0], seat=key[1], faction=key[2], kind=key[3], rounds=key[4],
                    teacher=len(teacher.get(key, [])), learner=len(learner.get(key, [])))
               for key in sorted(teacher.keys() | learner.keys())]
    write_new(output/'audit.json', dict(source_commit=commit, archive_sha256=corpus.file_sha(archive),
              worker=worker, endpoint=endpoint, original_games=original_games, trace=trace,
              teacher_counts=teacher_counts, learner_counts=learner_counts, strata=details,
              passed=passed, seconds=time.monotonic()-started))
    if passed:
        write_new(output/'corpus.json', dict(teacher=teacher_games, learner=learner_games, plans=frozen))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('commit')
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    freeze(args.output, args.commit, args.archive)
