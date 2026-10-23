import subprocess,sys
from learning.common import ROOT
out=ROOT/'verification/bc_rootcause_20261023_2318'
(ROOT/'tests/v5/test_teacher_state_reuse.py').write_text((out/'state_regression_source.txt').read_text(encoding='utf-8-sig'),encoding='utf-8')
result=subprocess.run([sys.executable,'-m','unittest','tests.v5.test_teacher_state_reuse','-v'],cwd=ROOT)
raise SystemExit(result.returncode)
