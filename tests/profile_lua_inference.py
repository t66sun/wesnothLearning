"""Replay one dense frozen native decision per format; no games or training."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch
from lupa.lua54 import LuaRuntime

from learning.export import compact_lua, lua_parameters
from learning.formats import FORMATS
from learning.model import Policy


def dense_decision(events, fmt):
    selected = None
    for path in sorted(events.glob(fmt + '-*.events.jsonl.gz')):
        with gzip.open(path, 'rt') as stream:
            for line in stream:
                event = json.loads(line)
                row = event['data']
                if event['event'] != 'LEARN' or row.get('turn', 0) < 5:
                    continue
                if len(row.get('candidates', [])) != 37:
                    continue
                if selected is None or len(row['spatial']['entities']) > len(selected['spatial']['entities']):
                    selected, origin = row, path
    if selected is None:
        raise ValueError('No full-budget native decision for ' + fmt)
    return selected, origin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=Path, required=True)
    parser.add_argument('--lua', type=Path, default=Path('lua/relational.lua'))
    args = parser.parse_args()
    torch.set_num_threads(1)
    torch.manual_seed(0)
    for fmt in FORMATS:
        model = Policy(fmt)
        selected, origin = dense_decision(args.events, fmt)
        lua = LuaRuntime(unpack_returned_tuples=True)
        network = lua.execute(args.lua.read_text(encoding='utf-8'))
        weights = lua.eval(compact_lua(lua_parameters(model)))
        inputs = [lua.table_from(selected[key], recursive=True)
                  for key in ('global', 'opponents', 'candidates', 'spatial')]
        forward = lambda: network.forward(weights, *inputs, lua.table(), selected['turn'])
        forward()
        timings = []
        for _ in range(5):
            start = time.perf_counter()
            forward()
            timings.append((time.perf_counter() - start) * 1000)
        lua.execute('''
            samples = {}
            debug.sethook(function()
                local info = debug.getinfo(2, 'S')
                local line = tostring(info.linedefined)
                samples[line] = (samples[line] or 0) + 1
            end, '', 10000)
        ''')
        forward()
        lua.execute('debug.sethook()')
        print(json.dumps(dict(format=fmt, source=str(args.lua),
            lua_sha256=hashlib.sha256(args.lua.read_bytes()).hexdigest(),
            event_file=str(origin), event_sha256=hashlib.sha256(origin.read_bytes()).hexdigest(),
            turn=selected['turn'], side=selected['side'], entities=len(selected['spatial']['entities']),
            candidates=37, milliseconds=timings, median_ms=statistics.median(timings),
            instruction_samples=dict(lua.globals().samples)), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
