"""Inspect one fixed teacher choice when slow can kill its low-HP target."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

from _engine_lite import LiteEngine
from learning.common import ROOT
from learning.lite_host import host_modules
from learning.native_transport import NativeTransport
from learning.teachers import identity
from tests.diagnose_teacher_boards import write
from tests.diagnose_teacher_slow import details, position


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rules', type=Path, required=True)
    parser.add_argument('--wesnoth', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    raw = (args.rules / 'rules.json').read_bytes()
    spec = position(json.loads(raw), False)
    spec['units'][3]['hp'] = 8
    modules = host_modules()
    wrapper = (ROOT / 'tests/fixtures/teacher_score_trace.lua').read_text()
    modules['astra/duel.lua'] = 'local teacher=(function()\n' + modules['astra/duel.lua'] + '\nend)()\n' + wrapper
    started = time.monotonic()
    with patch('learning.lite_host.host_modules', return_value=modules):
        with NativeTransport(wesnoth=args.wesnoth, timeout=30, startup_timeout=120) as native:
            lite = LiteEngine(raw.decode(), json.dumps(spec))
            lite.configure_host(json.dumps(modules))
            lite_decision = json.loads(lite.decision(1, True))
            native.reset(spec)
            native_decision = native.decision(1, teacher=True)
            row = dict(spec=spec,
                lite=details(lite_decision, json.loads(lite.legal_actions(1))),
                native=details(native_decision, native.legal_actions(1)))
            native_hash = native.executable_hash
    write(args.output / 'board.json', row)
    observations = {}
    for backend in ('native', 'lite'):
        result = row[backend]
        weapons = {trace['weapon']: trace for trace in result['trace']}
        slow, magical = weapons[2]['parameters'], weapons[3]['parameters']
        # In this unslowed, non-advancing fixture every fatal entangle hit also
        # slows the target, so kill is exactly the dead part of the slow marginal.
        observations[backend] = dict(
            selected_weapon=result['plan']['weapon'], legal=result['legal'],
            slow_score=weapons[2]['score'], magical_score=weapons[3]['score'],
            slow_kill=slow['kill'], magical_kill=magical['kill'],
            slow_marginal=slow['slow'], surviving_slow=slow['slow'] - slow['kill'],
            lower_kill_slow_selected=result['plan']['weapon'] == 2 and slow['kill'] < magical['kill'])
    summary = dict(source=args.source, teacher=identity(), rules_sha256=hashlib.sha256(raw).hexdigest(),
                   native_executable_sha256=native_hash, wall_seconds=time.monotonic() - started,
                   observations=observations,
                   limits='One predeclared first-decision board; no scorer change or strength claim.')
    write(args.output / 'summary.json', summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
