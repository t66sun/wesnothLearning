"""One bounded memory stress run, using an existing complete rollout."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

OLD = Path('/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022')
RUN = OLD / 'runs/v5_lite18h_20261024_003512'
TRACE = RUN / 'team2v2/data/rollout-00042-team2v2-g1.jsonl.gz'


def collector(index, output, ready, release, results, legacy=False):
    from learning.rowpack import unpack_line, compact_row
    from learning.sequences import IndexedSequenceStore
    rows = []
    with gzip.open(TRACE, 'rt') as stream:
        for number, line in enumerate(stream):
            row, _ = unpack_line(line, plain=True)
            compact = row if legacy else compact_row(row)
            if number in (0, 810, 1620):
                from learning.rowpack import plain_row
                assert plain_row(compact) == row
            rows.append(compact)
    ready.put(dict(role='collector', index=index, rows=len(rows), pid=os.getpid()))
    if not release.wait(600):raise TimeoutError('write barrier')
    if legacy:
        spec = importlib.util.spec_from_file_location('learning.legacy_sequences', Path(__file__).with_name('legacy_sequences.py'))
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        store_type = module.IndexedSequenceStore
    else:
        store_type = IndexedSequenceStore
    with store_type(Path(output)/f'collector-{index}') as store:
        assert store.write(rows) == len(rows)
        payloads = [(key, hashlib.sha256(payload).hexdigest()) for key, payload in
                    store.connection.execute('SELECT id,payload FROM sequences ORDER BY id')]
        entries = store.index()
    results.put(dict(role='collector', index=index, rows=len(rows), payloads=payloads,
                     indexed_decisions=sum(x['decisions'] for x in entries),
                     peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def trainer(fmt, ready, release, results):
    import torch
    torch.set_num_threads(1)
    from learning.export import load_model
    from learning.data import read_shards
    from learning.model import batch
    path = RUN / fmt / 'latest.pt'
    model, checkpoint = load_model(path, fmt, 'cpu')
    optimizer = torch.optim.Adam(model.parameters())
    optimizer.load_state_dict(checkpoint['optimizer'])
    state = checkpoint['runner']
    rows = read_shards(state['teacher_shards'], partition='train', limit=2048,
                       seed=20261017 + state['version'], format_name=fmt)
    # Exercise the compact-compatible forward/backward path once, independently
    # of the frozen experiment. No model/checkpoint is saved and no game starts.
    model.train();selected = rows[:8]
    logits, values = model(*batch(selected, 'cpu'))
    loss = torch.nn.functional.cross_entropy(logits, torch.tensor([r['choice'] for r in selected]))
    (loss + .01 * values.square().mean()).backward()
    ready.put(dict(role='trainer', format=fmt, rows=len(rows), pid=os.getpid()))
    if not release.wait(600):raise TimeoutError('trainer hold')
    results.put(dict(role='trainer', format=fmt, rows=len(rows), loss=float(loss.detach()),
                     peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def memory(processes):
    rss = pss = 0
    for child in processes:
        try:
            values = dict((x.split(':')[0], int(x.split()[1])) for x in
                          Path(f'/proc/{child.pid}/smaps_rollup').read_text().splitlines() if x.startswith(('Rss:', 'Pss:')))
            rss += values.get('Rss', 0);pss += values.get('Pss', 0)
        except (FileNotFoundError, ProcessLookupError):pass
    mem = dict((x.split(':')[0], int(x.split()[1])) for x in Path('/proc/meminfo').read_text().splitlines() if ':' in x and x.split()[1].isdigit())
    return dict(rss_kib=rss, pss_kib=pss, available_kib=mem['MemAvailable'], swap_used_kib=mem['SwapTotal']-mem['SwapFree'])


def phase(output, legacy=False):
    ctx = mp.get_context('spawn');ready = ctx.Queue();results = ctx.Queue()
    write = ctx.Event();finish = ctx.Event()
    processes = [ctx.Process(target=collector, args=(i,output,ready,write,results,legacy)) for i in range(1 if legacy else 8)]
    if not legacy:
        processes += [ctx.Process(target=trainer, args=(fmt,ready,finish,results)) for fmt in ('duel','ffa4','team2v2')]
    for child in processes:child.start()
    start = last = time.monotonic();loaded=[];done=[];peak_pss=peak_rss=peak_swap=0;min_available=10**12
    try:
        while len(done)<len(processes):
            m=memory(processes);peak_pss=max(peak_pss,m['pss_kib']);peak_rss=max(peak_rss,m['rss_kib'])
            peak_swap=max(peak_swap,m['swap_used_kib']);min_available=min(min_available,m['available_kib'])
            if m['available_kib'] < 1536*1024:raise MemoryError(f'host reserve reached: {m}')
            if time.monotonic()-start>720:raise TimeoutError('pressure deadline')
            for child in processes:
                if child.exitcode not in (None,0):raise RuntimeError(f'child {child.pid} exited {child.exitcode}')
            from queue import Empty
            while True:
                try:item=ready.get_nowait();loaded.append(item);print('READY',json.dumps(item),flush=True)
                except Empty:break
            if len(loaded)==len(processes):write.set()
            while True:
                try:item=results.get_nowait();done.append(item);print('DONE',json.dumps(item),flush=True)
                except Empty:break
            if sum(x['role']=='collector' for x in done)==(1 if legacy else 8):finish.set()
            if time.monotonic()-last>20:print('MEMORY',json.dumps(m),flush=True);last=time.monotonic()
            time.sleep(.25)
        for child in processes:child.join(timeout=10)
        assert all(not child.is_alive() and child.exitcode==0 for child in processes)
        return dict(seconds=time.monotonic()-start,peak_pss_kib=peak_pss,peak_rss_kib=peak_rss,
                    peak_swap_used_kib=peak_swap,min_available_kib=min_available,results=done)
    finally:
        for child in processes:
            if child.is_alive():child.terminate()
        for child in processes:child.join(timeout=5)
        for child in processes:
            if child.is_alive():child.kill();child.join()
        ready.close();results.close()


def main():
    output=Path(sys.argv[1]);output.mkdir()
    baseline=phase(str(output/'baseline'),legacy=True)
    pressure=phase(str(output/'pressure'))
    reference=baseline['results'][0]
    for result in pressure['results']:
        if result['role']=='collector':
            assert result['rows']==reference['rows']==1621
            assert result['indexed_decisions']==reference['indexed_decisions']
            assert result['payloads']==reference['payloads']
    assert len([r for r in pressure['results'] if r['role']=='trainer'])==3
    report=dict(passed=True,trace=str(TRACE),baseline=baseline,pressure=pressure)
    (output/'result.json').write_text(json.dumps(report,indent=2))
    print('STRESS_RESULT',json.dumps(report),flush=True)


if __name__=='__main__':main()
