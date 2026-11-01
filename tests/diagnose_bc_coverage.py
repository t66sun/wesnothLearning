"""Manual frozen-game diagnosis. Instrumentation exists only in this harness."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

from learning.coverage import FIELDS, matching, reason
from learning.lite_host import LiteHost, teacher_candidate, host_modules
from learning.lite_policy import game_spec
from learning.rules_catalog import resolve_dir


def traced(source):
    source = source.replace('local work,cut=0,false', 'local work,cut=0,false\n    local trace={actors={}}')
    source = source.replace('return {truncated=cut,ms=', 'return {trace=trace,truncated=cut,ms=')
    source = source.replace('local threats=threat_map(obs,enemies,allow,charge)',
        'trace.before_threat=work\n    local threats=threat_map(obs,enemies,allow,charge)\n    trace.after_threat=work')
    source = source.replace('local reach=wesnoth.paths.find_reach(u,',
        'trace.actors[#trace.actors+1]={x=u.x,y=u.y,start=work}\n            local reach=wesnoth.paths.find_reach(u,')
    source = source.replace('local depth=0', 'trace.before_probes=work\n    trace.plans=#plans\n    local depth=0')
    source = source.replace('for _,a in ipairs(Selection.select(pool)) do',
        "trace.pool={}\n    for _,a in ipairs(pool) do trace.pool[#trace.pool+1]={kind=a.kind,x=a.x,y=a.y,tx=a.tx,ty=a.ty,ex=a.ex,ey=a.ey,weapon=a.weapon,full=a.full,type=a.type} end\n    for _,a in ipairs(Selection.select(pool)) do")
    return source


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--format', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--games', type=int, default=1)
    p.add_argument('--variant', choices=['baseline', 'unlimited_work', 'no_threat'], default='baseline')
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    records = sorted([json.loads(x) for x in (args.run/args.format/'jobs.jsonl').read_text().splitlines()], key=lambda x:x['id'])[:args.games]
    wanted = {r['id'] for r in records}
    jobs = {j['id']:j for f in sorted((args.run/args.format/'schedules').glob('*.json')) for j in json.loads(f.read_text()) if j['id'] in wanted}
    counts, stages = Counter(), Counter()
    digest = hashlib.sha256()
    started = time.monotonic()
    with (args.out/'decisions.jsonl').open('w') as log:
        for job in jobs.values():
            rules_dir = resolve_dir(job.get('rules_dir'))
            rules = json.loads((rules_dir/'rules.json').read_text())
            modules = host_modules()
            source = modules['candidates.lua']
            if args.variant == 'unlimited_work': source = source.replace('total=12000,', 'total=10000000,')
            if args.variant == 'no_threat': source = source.replace('local threats=threat_map(obs,enemies,allow,charge)', 'local threats={}')
            modules['candidates.lua'] = traced(source)
            with patch('learning.lite_host.host_modules', return_value=modules):
                host = LiteHost(game_spec(job, rules), rules_dir)
            sides = set(map(int, job['learning']['sides']))
            decision = 0
            view = host.adapter.observe(1)
            while not view['finished']:
                side = view['current_side']
                row = host.decision(side, teacher=True, generate_candidates=side in sides)
                intent = teacher_candidate(row['teacher_action'])
                decision += 1
                digest.update(json.dumps([job['id'], decision, side, row['turn'], intent], sort_keys=True).encode())
                if side in sides:
                    timing = row['timing']; trace = timing.pop('trace')
                    pool = trace.pop('pool', [])
                    matched = matching(row['candidates'], intent) >= 0
                    generated = matching(pool, intent) >= 0 or intent['kind'] == 'end_turn'
                    kind = intent['kind']
                    counts[kind+':total'] += 1
                    counts[kind+':matched'] += matched
                    counts[kind+':generated'] += generated
                    missing = None if matched else reason(row['candidates'], intent)
                    cause = 'matched' if matched else 'selection' if generated else 'generation'
                    stages[kind+':'+cause] += 1
                    data = dict(job=job['id'], decision=decision, turn=row['turn'], side=side,
                                intent=intent, cause=cause, reason=missing, timing=timing, trace=trace,
                                pool=len(pool), candidates=len(row['candidates']))
                    log.write(json.dumps(data)+'\n')
                    # Retain one public-interface reproduction for each missed kind.
                    snapshot = args.out/(kind+'-'+cause+'.json')
                    if not matched and not snapshot.exists():
                        snapshot.write_text(json.dumps(dict(spec=host.adapter.spec, snapshot=host.snapshot(),
                                                           side=side, intent=intent, row=row)))
                    if cause=='generation' and not pool:
                        empty = args.out/'empty-generation.json'
                        if not empty.exists():
                            empty.write_text(json.dumps(dict(spec=host.adapter.spec, snapshot=host.snapshot(),
                                                             side=side, intent=intent, row=row)))
                view = host.execute(intent)['view']
            host.adapter.close()
    result = dict(format=args.format, variant=args.variant, games=len(jobs), counts=counts,
                  stages=stages, trajectory_sha256=digest.hexdigest(), seconds=time.monotonic()-started)
    (args.out/'summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
