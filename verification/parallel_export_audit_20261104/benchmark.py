"""Time the file-backed audit on the eight retained v6 duel shards on Ubuntu."""
import os
import threading
from pathlib import Path

def resident_memory(stop, peaks, pid=None):
    root_pid = os.getpid() if pid is None else pid
    while not stop.is_set():
        pending = [root_pid]
        seen = set()
        rss = pss = 0
        while pending:
            pid = pending.pop()
            if pid in seen:
                continue
            seen.add(pid)
            proc = Path('/proc', str(pid))
            try:
                for children in (proc / 'task').glob('*/children'):
                    pending.extend(map(int, children.read_text().split()))
                for line in (proc / 'smaps_rollup').read_text().splitlines():
                    if line.startswith('Rss:'):
                        rss += int(line.split()[1])
                    if line.startswith('Pss:'):
                        pss += int(line.split()[1])
            except (FileNotFoundError, ProcessLookupError):
                continue
        peaks['rss_kib'] = max(peaks['rss_kib'], rss)
        peaks['pss_kib'] = max(peaks['pss_kib'], pss)
        stop.wait(1)


if __name__ == '__main__':
    from learning.export import load_model
    from learning.sequence_parity import verify_shard_numerics
    run = Path('/home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness/duel')
    paths = sorted((run / 'data').glob('rollout-00036-duel-g*.jsonl.gz'))
    assert len(paths) == 8
    model, _ = load_model(run / 'last_bc.pt', 'duel')
    stop = threading.Event()
    peaks = dict(rss_kib=0, pss_kib=0)
    monitor = threading.Thread(target=resident_memory, args=(stop, peaks))
    monitor.start()
    try:
        error = verify_shard_numerics({'duel': model}, {'duel': paths}, workers=8)['duel']
        print('files', len(paths), 'maximum_error', error)
    finally:
        stop.set()
        monitor.join()
        print('sampled_process_tree_peak', peaks)
