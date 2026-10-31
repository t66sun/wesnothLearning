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


TAIL_CHUNK = 1 << 20


def repair_tail(path):
    """Drop the unterminated trailing line left by an interrupted writer.

    Scans backwards in bounded chunks, so the cost is the trailing line plus one
    chunk, never the whole log. Complete records are never removed.
    """
    path = Path(path)
    if not path.exists():
        return
    size = path.stat().st_size
    if not size:
        return
    with path.open('rb+') as stream:
        stream.seek(size - 1)
        if stream.read(1) == b'\n':
            return
        end = size
        while end > 0:
            start = max(0, end - TAIL_CHUNK)
            stream.seek(start)
            index = stream.read(end - start).rfind(b'\n')
            if index >= 0:
                stream.truncate(start + index + 1)
                return
            end = start
        stream.truncate(0)
