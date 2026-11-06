from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import json
import multiprocessing
from pathlib import Path
import time
import traceback
from learning.common import ROOT
from learning.formats import FORMATS, PLAYERS
from learning.maps import SPLITS, bind_scenario, frozen_map, run_family
from learning.schedule import evaluation_jobs, starting_factions
from .packages import digest, read, write_new
import match


GAMES_PER_BLOCK = dict(duel=2, ffa4=4, team2v2=8)
HORIZONS = (30, 100)


def jobs_for(directory, candidate, control, fmt, horizon, blocks, partition, deadline,
             executable, *, seed=20261107, offset=0):
    names = SPLITS[fmt][partition]
    factions = starting_factions(PLAYERS[fmt], fmt)
    scenes = [dict(map_index=0, factions=list(factions[((i+offset)//len(names)) % len(factions)]))
              for i in range(blocks)]
    label = f'{Path(directory).name}-{candidate["name"]}-{control["name"]}-{horizon}'
    jobs = evaluation_jobs(directory, candidate['package'], control['package'], ['baseline'],
                           blocks, seed + horizon * 1009 + FORMATS.index(fmt) * 100003 + offset,
                           deadline, executable, label=label, formats=(fmt,),
                           scenarios={fmt: scenes}, min_distinct=1)
    for job in jobs:
        index = job['meta']['block'] + offset
        name = names[index % len(names)]
        board, map_hash = frozen_map(name)
        job.update(engine='native', max_turns=horizon, map_override=board, timeout=1, first_timeout=10)
        job['meta'].update(map=name, map_sha256=map_hash, map_partition=partition,
                           panel=Path(directory).name,
                           horizon=horizon, candidate=candidate['name'], opponent=control['name'],
                           engine_version='native-1.18.8', combat_version='native-1.18.8',
                           rules_version='wesnoth-1.18.8-native-v2')
        job['seat_timeouts'] = {str(side): dict(timeout=2 if bot==candidate['package'] else control.get('timeout', 1),
                                              first_timeout=20 if bot==candidate['package'] else control.get('first_timeout', 10))
                                for side, bot in enumerate(job['bots'], 1) if bot!='baseline'}
        job['game_family'] = run_family(job)
        bind_scenario(job)
    return jobs


def timings(path, policy_sides, limits):
    rows = []
    overruns = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row['event'] != 'RETURN':
            continue
        event = row['data']
        side = event['side']
        expected = limits[str(side)]['first_timeout' if event['first'] else 'timeout']
        if event['budget'] != expected or event['elapsed_ms'] > expected * 1000:
            overruns.append(event)
        if side in policy_sides:
            rows.append(event['elapsed_ms'])
    rows.sort()
    return dict(decisions=len(rows), mean_ms=sum(rows)/len(rows) if rows else None,
                p95_ms=rows[int(.95*(len(rows)-1))] if rows else None,
                max_ms=rows[-1] if rows else None, overruns=overruns)


def play(job):
    started = time.time()
    if started >= job['deadline']:
        return dict(id=job['id'], status='budget_interrupted', started=started, finished=started)
    try:
        result = match.play_game(job['bots'], seed=job['seed'], factions=job['factions'],
                                 max_turns=job['max_turns'], teams=job.get('teams'),
                                 wesnoth=job['wesnoth'], timeout=job['timeout'], first_timeout=job['first_timeout'],
                                 seat_timeouts=job['seat_timeouts'], experiment_deadline=job['deadline'],
                                 map_override=job['map_override'], replay_path=job['output'])
        timing = timings(Path(job['output']).with_suffix('.events.jsonl'),
                         job['meta']['policy_sides'], job['seat_timeouts'])
        return dict(id=job['id'], status='complete' if time.time()<=job['deadline'] else 'budget_interrupted',
                    result=result, timing=timing, started=started, finished=time.time())
    except Exception as exc:
        return dict(id=job['id'], status='budget_interrupted' if time.time()>=job['deadline'] else 'infrastructure_error',
                    error=str(exc), traceback=traceback.format_exc(), started=started, finished=time.time())


def execute(directory, jobs, *, workers=8, metadata=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    ids = [job['id'] for job in jobs]
    if len(ids) != len(set(ids)):
        raise ValueError('panel job ids must be unique')
    write_new(directory / 'schedule.json', jobs)
    plan = dict(created=time.time(), workers=workers, games=len(jobs),
                deadline=min(job['deadline'] for job in jobs), schedule_sha256=digest(directory / 'schedule.json'),
                metadata=metadata or {})
    write_new(directory / 'plan.json', plan)
    jobs = sorted(jobs, key=lambda j: (j['meta']['block'], j['meta']['rotation'],
                                     j['meta']['format'], j['meta']['horizon'], j['meta']['candidate'],
                                     j['meta']['context']))
    results = []
    remaining = iter(jobs)
    with (directory / 'jobs.jsonl').open('x', encoding='utf-8') as log, \
            ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        pending = {}

        def record(result):
            results.append(result)
            log.write(json.dumps(result, separators=(',', ':')) + '\n')
            log.flush()
            print(json.dumps(dict(completed=len(results), planned=len(jobs), id=result['id'],
                                  status=result['status'], faults=result.get('result', {}).get('faults', {}))), flush=True)

        def submit():
            while len(pending) < workers:
                job = next(remaining, None)
                if job is None:
                    break
                if time.time() >= job['deadline']:
                    record(dict(id=job['id'], status='budget_interrupted', finished=time.time()))
                else:
                    pending[pool.submit(play, job)] = job

        submit()
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                job = pending.pop(future)
                try:
                    result = future.result()
                except Exception as exc:
                    result = dict(id=job['id'], status='infrastructure_error', error=str(exc), finished=time.time())
                record(result)
            submit()
    write_new(directory / 'results.json', results)
    return results
