"""Profile one v6 BC validation board as a score-only Lite evaluation job."""
import argparse
from collections import Counter
import cProfile
import hashlib
import json
import os
from pathlib import Path
import platform
import pstats
import time
from unittest.mock import patch

import _engine_lite
import torch

from learning.common import sha256
from learning.lite_host import LiteHost
from learning.sample import play_job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    directory = args.run / 'team2v2'
    schedule = directory / 'schedules/validation-000010.json'
    job_id = 'val000010-team2v2-b0000-astra_partner-r0'
    job, = (j for j in json.loads(schedule.read_text()) if j['id'] == job_id)
    expected, = (r for line in (directory / 'jobs.jsonl').read_text().splitlines()
                 if (r := json.loads(line))['id'] == job_id)
    assert job['meta']['map_partition'] == 'validation' and job['engine'] == 'lite'
    assert 'shard' not in job and 'learner_sides' not in job
    args.output.mkdir(parents=True, exist_ok=False)
    # Holdout jobs have no policy telemetry. Keep this validation board, its
    # frozen bots and all game settings. Only the time allowance and output move.
    job.pop('learning')
    job['output'] = str(args.output / 'replay.json')
    job['deadline'] = time.time() + 115
    model = Path(job['meta']['policy']).parent / 'model.pt'
    game_trace = hashlib.sha256()
    counts, cpu_by_role = Counter(), Counter()
    role = None
    decision, execute = LiteHost.decision, LiteHost.execute

    def timed_decision(host, side, **options):
        nonlocal role
        role = 'astra' if options['teacher'] else 'policy'
        start = time.process_time()
        value = decision(host, side, **options)
        cpu_by_role[role + '_decision'] += time.process_time() - start
        counts[role + '_decision'] += 1
        return value

    def timed_execute(host, action):
        start = time.process_time()
        outcome = execute(host, action)
        cpu_by_role[role + '_execute'] += time.process_time() - start
        counts[role + '_execute'] += 1
        identity = {k: action[k] for k in ('kind','x','y','tx','ty','ex','ey','type','weapon','full') if k in action}
        game_trace.update(json.dumps([role,identity,outcome['events'],outcome['committed']],
                                     sort_keys=True,separators=(',',':')).encode() + b'\n')
        return outcome

    profiler = cProfile.Profile()
    start, cpu = time.monotonic(), time.process_time()
    with patch.object(LiteHost, 'decision', timed_decision), patch.object(LiteHost, 'execute', timed_execute):
        result = profiler.runcall(play_job, job)
    seconds, cpu_seconds = time.monotonic() - start, time.process_time() - cpu
    profiler.dump_stats(args.output / 'python.prof')
    with (args.output / 'python.txt').open('w') as stream:
        stats = pstats.Stats(profiler, stream=stream).strip_dirs()
        stats.sort_stats('cumulative').print_stats(60)
        stats.sort_stats('tottime').print_stats(40)
    observed = dict(source=os.environ['SOURCE_COMMIT'], python=platform.python_version(),
                    torch=torch.__version__, torch_threads=torch.get_num_threads(),
                    interop_threads=torch.get_num_interop_threads(), cpu_seconds=cpu_seconds,
                    wall_seconds=seconds, cpu_by_role=cpu_by_role, calls=counts,
                    source_schedule_sha256=sha256(schedule), model_sha256=sha256(model),
                    extension_sha256=sha256(_engine_lite.__file__), job=job_id, seed=job['seed'],
                    rules_sha256=sha256(Path(job['rules_dir'])/'rules.json'),
                    teacher_sha256=job['meta']['teacher_source_sha256'],
                    action_event_sha256=game_trace.hexdigest(), status=result['status'],
                    error=result.get('error'), expected_result=expected['result'], result=result.get('result'))
    (args.output / 'profile.json').write_text(json.dumps(observed, indent=2)+'\n')
    assert result['status'] == expected['status'] == 'complete', result
    assert result['result'] == expected['result'] and not result['result']['faults']
    print(json.dumps({k: observed[k] for k in ('job','status','wall_seconds','cpu_seconds','calls','cpu_by_role','action_event_sha256')}))


if __name__ == '__main__':
    main()
