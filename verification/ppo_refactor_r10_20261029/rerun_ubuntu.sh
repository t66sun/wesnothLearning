#!/usr/bin/env bash
# R10 Ubuntu acceptance: bundle teacher identity and no unused teacher package.
# usage: rerun_ubuntu.sh <archive> <sha256>
set -euo pipefail

archive=${1:?archive}
expected=${2:?sha256}
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r10b_20261029
python=/home/tongshu/venv/bin/python
data=/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/data
curated=/home/tongshu/myDev/wesnothLearning/WesnothLearning/humanData_curated
logs=$(cd "$(dirname "$0")" && pwd)/rerun

actual=$(sha256sum "$archive" | cut -d' ' -f1)
if [[ "$actual" != "$expected" ]]; then
    echo "archive sha256 $actual != $expected" >&2
    exit 1
fi
if [[ -e "$root" ]]; then
    echo "refusing to overwrite $root" >&2
    exit 1
fi

mkdir -p "$root" "$logs"
tar -xf "$archive" -C "$root"
cd "$root"
export PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1

{
    echo "root=$root"
    echo "archive=$archive sha256=$actual"
    echo "source_revision=$(cat SOURCE_REVISION)"
    echo "python=$($python -V 2>&1)"
    echo "kernel=$(uname -sr)"
    $python -c 'import torch;print("torch="+torch.__version__)'
    $python -c 'import wesnoth_learning_lite as l;print("lite="+str(getattr(l,"__version__","unknown")))' 2>/dev/null         || echo 'lite=not installed in the base interpreter'
    $python -c 'import lupa;print("lupa="+lupa.__version__)'
} > "$logs/environment.log" 2>&1

$python -m unittest tests.v5.test_bundle_identity tests.test_bundle tests.test_bundle_scripts \
    -v > "$logs/targeted.log" 2>&1

# Real repository bundle: the extracted tree carries LF sources, so the recorded
# capture hash is the canonical one rather than a CRLF working-tree hash.
mkdir -p data
cp -a "$data/rules/." data/rules/
cp -a "$data/opponents/." data/opponents/
cp -a "$curated" data/humanData_curated
curated_sha=$(sha256sum data/humanData_curated/games.jsonl | cut -d' ' -f1)
if [[ "$curated_sha" != 1c94bb8d6ff51c192cf49fa24b5ce13adfefd8b3f6c5d08cf352e57536c3695f ]]; then
    echo "curated corpus differs: $curated_sha" >&2
    exit 1
fi
$python -m learning bundle --output tmp/r10-a.tar.gz --created-at 2026-10-28T00:00:00Z \
    > "$logs/bundle-a.log" 2>&1
$python -m learning bundle --output tmp/r10-b.tar.gz --created-at 2026-10-28T00:00:00Z \
    > "$logs/bundle-b.log" 2>&1
$python -m learning verify-bundle tmp/r10-a.tar.gz > "$logs/verify.json" 2>&1
bash setup.sh --preflight > "$logs/preflight.log" 2>&1

$python - "$logs" <<'PY'
import hashlib
import json
import sys
import tarfile
from pathlib import Path

from learning.stock_rca import capture_sha256_from

logs = Path(sys.argv[1])
first, second = Path('tmp/r10-a.tar.gz'), Path('tmp/r10-b.tar.gz')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
report = dict(
    archive_sha256=sha(first),
    reproducible=sha(first) == sha(second),
    preflight=Path(logs / 'preflight.log').read_text().strip().splitlines()[-1],
    curated_games_sha256='1c94bb8d6ff51c192cf49fa24b5ce13adfefd8b3f6c5d08cf352e57536c3695f',
    verification=json.loads((logs / 'verify.json').read_text()),
)

with tarfile.open(first) as archive:
    names = archive.getnames()
    manifest = json.load(archive.extractfile('WesnothLearning/BUNDLE_MANIFEST.json'))
    digests = {}
    for name in names:
        if name.endswith('.lua') and '/lua/stock_rca_capture/' in name:
            digests[name.split('WesnothLearning/', 1)[1]] = hashlib.sha256(
                archive.extractfile(name).read()).hexdigest()

teacher = manifest['identities']['teacher']
report.update(
    teacher=teacher,
    opponents=manifest['data']['opponents'],
    opponent_members=[name for name in names if '/data/opponents/' in name],
    capture_sources=digests,
    capture_sha256=capture_sha256_from(digests),
    verified_ok=report['verification']['ok'],
    verified_teacher=report['verification']['teacher'],
)
(logs / 'identity.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')

assert report['verified_ok'] is True, report
assert report['reproducible'] is True, report
assert teacher['kind'] == 'wesnoth_default_rca', teacher
assert teacher['query'] == 'none', teacher
assert teacher['action_source'] == 'engine_events', teacher
assert teacher['packages'] == [], teacher
assert teacher['capture_sha256'] == report['capture_sha256'], teacher
assert report['capture_sha256'] == '26d2894a09ccc66e5d7274d684644815d659d56b0110b0f0d22a83eb0e539557', report
assert report['opponents'] == [], manifest['data']['opponents']
assert report['opponent_members'] == [], report['opponent_members']
assert report['verified_teacher'] == teacher, report
assert set(digests) == {'lua/stock_rca_capture/main.lua', 'lua/stock_rca_capture/observer.lua'}, digests
assert 'preflight: ok' in report['preflight'], report['preflight']
print('passed: teacher=%s query=%s capture=%s archive=%s' % (
    teacher['kind'], teacher['query'], report['capture_sha256'], report['archive_sha256']))
PY
