from pathlib import Path
import hashlib
import json
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'vendor' / 'arena'
sys.path.insert(0, str(VENDOR))
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME',str(ROOT/'.cache'))
os.environ.setdefault('CUDA_CACHE_PATH',str(ROOT/'.cache/cuda'))
(ROOT / 'tmp').mkdir(exist_ok=True)
tempfile.tempdir = str(ROOT / 'tmp')


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
