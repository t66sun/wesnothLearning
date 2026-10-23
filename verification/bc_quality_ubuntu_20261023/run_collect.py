import subprocess,sys
from learning.common import ROOT
raise SystemExit(subprocess.run([sys.executable,'-u','-m','verification.bc_quality_ubuntu_20261023.quality_t5','collect'],timeout=1800).returncode)
