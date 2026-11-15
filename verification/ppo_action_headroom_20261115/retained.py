"""Measure one fixed retained alternate per distinct archived game after the proof gate."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import multiprocessing
from pathlib import Path
from random import Random
from statistics import mean
import sys
import time

import torch

from learning.common import read_json, sha256
from proof import archive_history, archive_rows, fingerprint, history_digest, public_intent, run_worker
from review import verify_capture
from verification.duel_ppo_comparison_20261106.audit import write_new

SECONDS = 660
WORKERS = 4
SEED = 2026111760
PROOF_SHA = '4d66d5e357d84821abd239816c7577c0bc4bca94876c4ef819502d34253d4a26'


def prepare(base, output, commit, archive, proof_root, slate_file):
    assert not output.exists()
    gate = read_json(proof_root/'proof-result.json')
    assert gate['launch_sha256'] == sha256(proof_root/'proof-launch.json') == PROOF_SHA and gate['pass_gate']
    assert (proof_root/'proof-launcher.exit').read_text().strip() == '0'
    assert gate['counts'] == {'baseline:started':6, 'baseline:complete':6,
                              'identical:started':6, 'identical:complete':6}
    archive_m, jobs, _, _, facts = verify_capture(base)
    registry = {job['id']:job for job in jobs}
    slate = read_json(slate_file)
    assert slate['capture_sha256'] == facts['archive_sha256']
    assert slate['games_started'] == slate['optimizer_updates'] == 0
    cases = []
    for case in slate['cases']:
        job = registry[case['game_id']]
        rows = archive_rows(job)
        cut = case['boundary']
        row = rows[cut]
        assert row['decision'] == case['decision'] and row['choice'] == case['original_choice']
        assert fingerprint(row) == case['public_sha256']
        chosen, alt = case['original_choice'], case['alternative_choice']
        a, b = (public_intent(row['candidates'][i]) for i in (chosen, alt))
        assert a != b
        history = history_digest(*archive_history(rows[:cut]))
        cases.append(dict(**case, history_sha256=history, original_intent=a, alternative_intent=b))
    n = len(cases)
    assert n == len({r['game_id'] for r in cases}) == 17
    output.mkdir()
    write_new(output/'retained-launch.json',dict(issue=360, phase='retained-action-pairs', archived=archive_m['runtime'],
             capture=facts, archive_root=str(base), source_commit=commit, git_archive_sha256=sha256(archive),
             script_sha256=sha256(Path(__file__)), proof_code_sha256=sha256(Path(__file__).with_name('proof.py')),
             proof_sha256=PROOF_SHA, proof_result_sha256=sha256(proof_root/'proof-result.json'),
             slate_sha256=sha256(slate_file), cases=cases, seconds=SECONDS, workers=WORKERS,
             original_seed_replays=n, identical_suffixes=n, alternate_suffixes=n,
             continuation_draws_per_state=1, omitted_group='unobserved', optimizer_updates=0,
             acceptance='All 17 archive and identical-action controls match exactly at stored row precision; all 17 single-alternate replies complete with no faults. No alternative executes for a failed control.'))
    print(json.dumps(dict(launch_sha256=sha256(output/'retained-launch.json'),states=n,games_started=0)))


def points(outcome, seat):
    return 3 if outcome['winner'] == seat else 1 if outcome['winner'] == 0 else 0


def summarize(results):
    contributions = []
    for r in results.values():
        seat = r['side']
        p = points(r['outcome'], seat)
        q = points(r['alternate_outcome'], seat)
        r['original_points'],r['alternate_points'],r['point_change'] = p,q,q-p
        contributions.append((q-p)/3)
    rng = Random(SEED)
    n = len(contributions)
    distribution = sorted(mean(rng.choices(contributions,k=n)) for _ in range(10000))
    return dict(point=mean(contributions), interval95=[distribution[250],distribution[9750]],
                direction=dict(Counter('improvement' if v>0 else 'decline' if v<0 else 'tie' for v in contributions)),
                bootstrap_draws=10000, bootstrap_units='distinct original games')


def run(base, output, digest):
    p = output/'retained-launch.json'
    assert sha256(p) == digest
    assert not (output/'retained-start.json').exists()
    m = read_json(p)
    assert m['script_sha256'] == sha256(Path(__file__))
    assert m['proof_code_sha256'] == sha256(Path(__file__).with_name('proof.py'))
    assert m['archive_root'] == str(base) and m['proof_sha256'] == PROOF_SHA
    started = time.time()
    write_new(output/'retained-start.json',dict(launch_sha256=digest,started=started))
    manifest, jobs, replies, _, capture = verify_capture(base)
    assert manifest['runtime'] == m['archived'] and capture == m['capture']
    registry = {j['id']: j for j in jobs}
    results = {}
    with ProcessPoolExecutor(max_workers=WORKERS, mp_context=multiprocessing.get_context('spawn')) as workers:
        queue = {}
        for ordinal, probe in enumerate(m['cases']):
            gid = probe['game_id']
            queue[workers.submit(run_worker, registry[gid], replies[gid]['result'], probe,
                                 started+SECONDS-5, output/f'worker-{ordinal}.jsonl', probe['alternative_choice'])] = gid
        for future in as_completed(queue):
            gid = queue[future]
            try:
                results[gid] = dict(status='complete', **future.result())
            except Exception as exc:
                results[gid] = dict(status='failed', error=f'{type(exc).__name__}: {exc}')
            print(gid, results[gid]['status'], results[gid].get('error',''), flush=True)
    counts = Counter()
    for p in output.glob('worker-*.jsonl'):
        for line in p.read_text().splitlines():
            row = json.loads(line)
            counts[row['stage']+':'+row['state']] += 1
    n = len(m['cases'])
    expected = {f'{phase}:{status}':n for phase in ('baseline','identical','alternate')
                for status in ('started','complete')}
    ok = counts == expected and len(results) == n and all(r['status']=='complete' for r in results.values())
    check = summarize(results) if ok else None
    write_new(output/'retained-result.json',dict(launch_sha256=digest, passed=ok, results=results,
             contrast=check, counts=counts, wall_s=time.time()-started,optimizer_updates=0))
    return int(not ok)


def main():
    torch.set_num_threads(1)
    action, root, target, *rest = sys.argv[1:]
    base, output = Path(root).resolve(), Path(target).resolve()
    if action == 'prepare':
        commit, archive, proof_root, slate = rest
        return prepare(base,output,commit,Path(archive),Path(proof_root),Path(slate))
    if action == 'run':
        digest, = rest
        return run(base,output,digest)
    raise ValueError('expected prepare or run')


if __name__ == '__main__':
    sys.exit(main())
