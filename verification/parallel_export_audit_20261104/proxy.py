"""One prospective, 300-second CLI export on predeclared existing three-format inputs."""
import gzip
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from benchmark import resident_memory


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


if __name__ == '__main__':
    root = Path.cwd()
    inventory = json.loads((root / 'artifacts.json').read_text())
    audit = root / 'proxy-inputs'
    audit.mkdir()
    dest = root / 'delivery/proxy'
    plan = dict(source=os.environ['SOURCE_COMMIT'], workers=8, ceiling_seconds=300,
                physical_games=24, shard_files=28, host_load=os.getloadavg(), files=[], checkpoints={})
    args = [sys.executable, '-B', '-u', '-m', 'learning', 'export', '--audit-workers', '8',
            '--audit-data', str(audit), '--output', str(dest)]
    for fmt, teachers in [('duel', 4), ('ffa4', 8), ('team2v2', 8)]:
        files = sorted(inventory['formats'][fmt]['files'], key=lambda f: f['path'])
        chosen = [f for f in files if f['role'] == 'teacher'][:teachers]
        if fmt == 'duel':
            for role in ('rollout', 'dagger'):
                chosen.extend([f for f in files if f['role'] == role][:4])
        assert len(chosen) == teachers + (8 if fmt == 'duel' else 0)
        folder = audit / fmt
        folder.mkdir()
        for entry in chosen:
            path = Path(entry['path'])
            assert digest(path) == entry['sha256']
            (folder / path.name).symlink_to(path)
            with gzip.open(path, 'rb') as stream:
                rows = sum(1 for line in stream if line.strip())
            plan['files'].append(dict(format=fmt, path=str(path), role=entry['role'], rows=rows,
                                      bytes=path.stat().st_size, sha256=entry['sha256']))
        checkpoint, = [f for f in files if f['role'] == 'last_bc']
        path = Path(checkpoint['path'])
        assert digest(path) == checkpoint['sha256']
        plan['checkpoints'][fmt] = dict(path=str(path), sha256=checkpoint['sha256'])
        args.extend(['--' + fmt, str(path)])
    plan['rows'] = sum(f['rows'] for f in plan['files'])
    command = ['/usr/bin/time', '-v', '-o', 'proxy.time', 'timeout', '--signal=KILL', '300s', *args]
    plan['command'] = command
    (root / 'proxy-plan.json').write_text(json.dumps(plan, indent=2))
    with (root / 'proxy.log').open('w') as log:
        start = time.monotonic()
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        stop = threading.Event()
        peaks = dict(rss_kib=0, pss_kib=0)
        monitor = threading.Thread(target=resident_memory, args=(stop, peaks, process.pid))
        monitor.start()
        code = process.wait()
        elapsed = time.monotonic() - start
        stop.set()
        monitor.join()
    result = dict(exit=code, wall_seconds=elapsed, plan_sha256=digest(root / 'proxy-plan.json'), **peaks)
    if code == 0:
        record = json.loads((dest / 'export.json').read_text())
        result['max_errors'] = {f: m['python_lua_max_error'] for f, m in record['models'].items()}
        result['package_sha256'] = digest(dest / 'NeuralArena.zip')
        assert result['package_sha256'] == record['sha256']
    (root / 'proxy-result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    raise SystemExit(code)
