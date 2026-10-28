#!/usr/bin/env bash
set -euo pipefail
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r9b_20261029/source
python=/home/tongshu/venv/bin/python
cd "$root"
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
test="${1:-tests.v5.test_teacher_protocol.TeacherProtocolTests.test_runner_collects_stock_games_without_a_teacher_seat}"
cp learning/experiment.py /tmp/experiment.py.r9
"$python" - <<'PY'
from pathlib import Path
path = Path('learning/experiment.py')
source = path.read_text()
start = source.index('    def teacher_batch(self,count,index,anchor):')
end = source.index('    def teacher_evidence(self):')
reverted = '''    def teacher_batch(self,count,index,anchor):
        """Reverted: every teacher record is treated as queryable."""
        return teacher_jobs(self.directory,self.teachers,self.native_fixed if anchor else self.fixed,
            self.support,index,self.config['seed'],self.update_deadline(),self.exe,
            formats=[self.fmt],count=count,index_stride=self.config['bc_batch_games'])

'''
path.write_text(source[:start] + reverted + source[end:])
PY
if "$python" -m unittest "$test" -v > /tmp/r9_revert.log 2>&1; then
    cp /tmp/experiment.py.r9 learning/experiment.py
    echo 'revert did not fail the assertion' >&2
    exit 1
fi
cp /tmp/experiment.py.r9 learning/experiment.py
"$python" -m unittest "$test" -v > /tmp/r9_restore.log 2>&1
grep -E '^(FAILED|Reverted|ValueError|AssertionError|OK|Ran )' /tmp/r9_revert.log | head -5
echo '--- restored ---'
tail -3 /tmp/r9_restore.log
