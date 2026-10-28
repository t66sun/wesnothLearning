"""Revert each half of the change and require the rehearsal test to fail.

Each case restores the file before the next case runs; the caller checks that
`git status` is clean afterwards.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'learning' / 'experiment.py'
TEST = 'tests.v5.test_rehearsal_source.RehearsalSourceTests.test_runner_rehearses_ppo_on_its_own_policy_shards'
MESSAGE = 'no rehearsal data distinct from the evaluation control'
CASES = {
    'opt-in': (
        "            rehearsal_exclude=rehearsal_exclude,allow_policy_rehearsal=method=='ppo')",
        "            rehearsal_exclude=rehearsal_exclude)",
    ),
    'pool': (
        "        if method=='ppo': pool=pool+list(self.state.get('policy_shards',[]))",
        "        if False: pool=pool+list(self.state.get('policy_shards',[]))",
    ),
}

for name, (old, new) in CASES.items():
    original = SOURCE.read_text(encoding='utf-8')
    if original.count(old) != 1:
        raise SystemExit(f'{name}: expected exactly one {old!r}')
    SOURCE.write_text(original.replace(old, new), encoding='utf-8')
    try:
        result = subprocess.run([sys.executable, '-m', 'unittest', TEST],
                                cwd=ROOT, capture_output=True, text=True)
    finally:
        SOURCE.write_text(original, encoding='utf-8')
    if result.returncode == 0:
        raise SystemExit(f'{name}: the test still passes after the revert')
    if MESSAGE not in result.stderr:
        raise SystemExit(f'{name}: failed for another reason:\n{result.stderr[-2000:]}')
    print(f'{name}: reverted, test failed with "{MESSAGE}" (exit {result.returncode})')
