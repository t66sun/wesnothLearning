import pathlib,subprocess,sys
from learning.common import ROOT
result=subprocess.run([sys.executable,'-m','unittest','tests.v5.test_teacher_state_reuse','-v'],cwd=ROOT)
raise SystemExit(result.returncode)
