"""Gate one-action continuations on exact archive replay in the pinned Lite worker."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import gzip
import hashlib
import json
import multiprocessing
from pathlib import Path
import sys
import time
from unittest.mock import patch

import torch

from learning import lite_host, lite_policy
from learning.common import read_json, sha256
from learning.rowpack import pack_line, plain_row, unpack_line
from verification.duel_ppo_comparison_20261106.audit import write_new

from review import verify_capture

SECONDS = 240
WORKERS = 4
MAPS = ('the_freelands', 'weldyn_channel', 'fallenstar_lake')
FIELDS = ('global', 'opponents', 'spatial', 'candidates', 'side', 'turn')


def archive_rows(job):
    with gzip.open(job['shard'], 'rt', encoding='utf-8') as stream:
        return [unpack_line(line)[0] for line in stream]


def canonical(value):
    if isinstance(value, dict):
        return {key: canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonical(x) for x in value]
    return value


def fingerprint(row):
    normalized = canonical(plain_row({key: row[key] for key in FIELDS}))
    return hashlib.sha256(pack_line(normalized).encode()).hexdigest()


def history_digest(rows):
    public = [canonical(plain_row(row)) for row in rows]
    return hashlib.sha256(pack_line(dict(rows=public)).encode()).hexdigest()


def archive_history(rows):
    positions = {}
    for r in rows:
        if r.get('memory_write') is not None and r.get('committed'):
            positions.setdefault(r['turn'], dict(r['memory_write'], turn=r['turn'], candidates=[]))
    return list(positions.values())


def choose_probes(jobs):
    probes = []
    roles = sorted({j['meta']['role'] for j in jobs} - {'bc'})
    for i, role in enumerate(roles):
        for seat in (1, 2):
            name = MAPS[(i + seat - 1) % len(MAPS)]
            candidates = [j for j in jobs if j['meta']['role'] == role and j['meta']['map'] == name
                          and j['meta']['policy_sides'] == [seat]]
            job = min(candidates, key=lambda j: j['meta']['block'])
            rows = archive_rows(job)
            boundary = len(rows) * (i + 1) // 4
            assert 0 < boundary < len(rows)
            row = rows[boundary]
            probes.append(dict(game_id=job['id'], boundary=boundary, decision=row['decision'],
                               turn=row['turn'], side=seat, original_choice=row['choice'],
                               candidate_count=len(row['candidates']), role=role, layout=name,
                               public_sha256=fingerprint(row),
                               history_sha256=history_digest(archive_history(rows[:boundary]))))
    assert len(probes) == len({r['game_id'] for r in probes}) == 6
    return probes


def run_worker(job, expected, probe, deadline, traces):
    rows = archive_rows(job)
    boundary = probe['boundary']
    seat = probe['side']
    assert rows[boundary]['decision'] == probe['decision']
    assert fingerprint(rows[boundary]) == probe['public_sha256']

    def play(start):
        state = dict(cursor=boundary if start is not None else 0, max_logp_error=0.,
                     first_decision=None, saved=None)
        traced = lite_host.LiteHost
        frozen = lite_policy.FrozenPolicies

        class ObservedPolicy(frozen):
            def __init__(self, args):
                super().__init__(args)
                state['policy'] = self
                if start is not None:
                    self.histories[seat] = deepcopy(start['history'])
                    self.rng[seat].setstate(start['policy_rng'])
                    assert history_digest(self.histories[seat]) == probe['history_sha256']

            def choose(self, row, side, bootstrap=False):
                assert side == seat and not bootstrap
                index = state['cursor']
                assert index < len(rows), f'Extra learner decision {index}'
                target = rows[index]
                assert row['turn'] == target['turn'], f'Turn at learner decision {index}'
                current = fingerprint(row)
                assert current == fingerprint(target), f'Public observation and candidate order at learner decision {index}'
                selection = super().choose(row, side)
                assert selection['choice'] == target['choice'], f'Action at learner decision {index}'
                delta = abs(selection['log_probability'] - target['log_probability'])
                assert delta <= 1e-5, f'Log probability at learner decision {index}: {delta}'
                state['max_logp_error'] = max(delta, state['max_logp_error'])
                state['first_decision'] = current if state['first_decision'] is None else state['first_decision']
                state['cursor'] += 1
                return selection

        class ObservedHost(traced):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if start is not None:
                    observe = self.adapter.observe

                    def enter_branch(_side):
                        self.adapter.observe = observe
                        self.restore(start['referee'])
                        return observe(seat)

                    self.adapter.observe = enter_branch

            def decision(self, side, *, teacher=False, generate_candidates=True,
                         score_only_astra=False, score_only_policy=False):
                if (start is None and not teacher and generate_candidates and side == seat
                        and state['cursor'] == boundary and state['saved'] is None):
                    policy = state['policy']
                    assert history_digest(policy.histories[seat]) == probe['history_sha256']
                    state['saved'] = dict(referee=self.snapshot(), history=deepcopy(policy.histories[seat]),
                                          policy_rng=policy.rng[seat].getstate())
                return super().decision(side, teacher=teacher, generate_candidates=generate_candidates,
                                        score_only_astra=score_only_astra, score_only_policy=score_only_policy)

        bound = {k: v for k, v in job.items() if k != 'shard'}
        bound['deadline'] = deadline
        kind = 'baseline' if start is None else 'identical'
        with traces.open('a', encoding='utf-8') as out:
            out.write(json.dumps(dict(stage=kind, state='started')) + '\n')
        with patch.object(lite_host, 'LiteHost', ObservedHost), patch.object(lite_policy, 'FrozenPolicies', ObservedPolicy):
            answer = lite_host.play_lite_job(bound)
        assert answer['status'] == 'complete', answer.get('error', answer['status'])
        assert answer['result'] == expected and not answer['result']['faults']
        assert state['cursor'] == len(rows)
        with traces.open('a', encoding='utf-8') as out:
            out.write(json.dumps(dict(stage=kind, state='complete')) + '\n')
        return state

    baseline = play(None)
    assert baseline['saved'] is not None
    control = play(baseline['saved'])
    assert control['first_decision'] == probe['public_sha256']
    return dict(**probe, outcome=expected, baseline_checked=len(rows),
                identical_checked=len(rows) - boundary,
                logp_error=max(baseline['max_logp_error'], control['max_logp_error']))


def prepare(base, output, commit, archive):
    assert not output.exists()
    start = time.time()
    manifest, jobs, _, _, facts = verify_capture(base)
    output.mkdir()
    payload = dict(issue=360, phase='identical-action-proof', source_commit=commit,
                   source_archive_sha256=sha256(archive), script_sha256=sha256(Path(__file__)),
                   archived=manifest['runtime'], capture=facts, archive_root=str(base), jobs=choose_probes(jobs),
                   workers=WORKERS, wall_cap_s=SECONDS,
                   max_baselines=6, max_identical_suffixes=6, max_alternates=0, optimizer_updates=0)
    write_new(output / 'proof-launch.json', payload)
    print(json.dumps(dict(launch_sha256=sha256(output/'proof-launch.json'),
                          planned=len(payload['jobs']), wall_s=time.time()-start, games_started=0)))
    return 0


def prove(base, output, digest):
    launch = output / 'proof-launch.json'
    assert sha256(launch) == digest
    manifest = read_json(launch)
    assert manifest['archive_root'] == str(base)
    assert manifest['script_sha256'] == sha256(Path(__file__))
    assert not (output/'proof-start.json').exists()
    assert not (output/'proof-result.json').exists()
    started = time.time()
    write_new(output/'proof-start.json', dict(launch_sha256=digest, started=started))
    raw, jobs, replies, _, capture = verify_capture(base)
    assert capture == manifest['capture'] and raw['runtime'] == manifest['archived']
    assert choose_probes(jobs) == manifest['jobs']
    registry = {j['id']: j for j in jobs}
    results = {}
    with ProcessPoolExecutor(max_workers=WORKERS, mp_context=multiprocessing.get_context('spawn')) as workers:
        queue = {}
        for ordinal, probe in enumerate(manifest['jobs']):
            gid = probe['game_id']
            queue[workers.submit(run_worker, registry[gid], replies[gid]['result'], probe,
                                 started+SECONDS-5, output/f'worker-{ordinal}.jsonl')] = gid
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
    ok = len(results) == len(manifest['jobs']) and all(r['status']=='complete' for r in results.values())
    ok = ok and counts == {'baseline:started':6, 'baseline:complete':6,
                           'identical:started':6, 'identical:complete':6}
    write_new(output/'proof-result.json', dict(pass_gate=ok, results=results, counts=counts,
             launch_sha256=digest, wall_s=time.time()-started, optimizer_updates=0, alternates=0))
    return int(not ok)


def main():
    torch.set_num_threads(1)
    action, root, target, *rest = sys.argv[1:]
    base, output = Path(root).resolve(), Path(target).resolve()
    if action == 'prepare':
        commit, archive = rest
        return prepare(base, output, commit, Path(archive))
    if action == 'prove':
        digest, = rest
        return prove(base, output, digest)
    raise ValueError('expected prepare or prove')


if __name__ == '__main__':
    sys.exit(main())
