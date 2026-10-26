"""Export the selected completed run for a separate local installation."""
from pathlib import Path
import gzip
import hashlib
import json
import os
import shutil
import sys
import tarfile

ROOT = Path('/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source')
RUN = ROOT / 'runs/v5_lite30h_20261025'
OUT = ROOT.parent / 'exports/lite_final_20261026_v2'
os.chdir(ROOT)
sys.path[:0] = [str(ROOT), str(ROOT / 'vendor/arena')]
sys.dont_write_bytecode = True
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '1'
manifest = json.loads((RUN / 'manifest.json').read_text())
os.environ['WESNOTH_RULES_DIR'] = manifest['config']['rules_dir']

import torch
from learning.adapters import ENGINE_VERSION, RNG_VERSION, COMBAT_VERSION
from learning.checkpoints import validate_checkpoint
from learning.common import sha256, write_json
from learning.export import load_model, verify_numerics, export
from learning.manifest import verify_frozen
from learning.rowpack import unpack_line
from learning.sequences import read_raw_shards
from learning.teachers import identity as teacher_identity

torch.set_num_threads(1)
summary = json.loads((RUN / 'summary.json').read_text())
assert summary['status'] == 'finished'
assert all(code == 0 for code in summary['scheduler']['exit_codes'].values())
verify_frozen(manifest)
assert not OUT.exists(), OUT
OUT.mkdir(parents=True)
(OUT / 'checkpoints').mkdir()
(OUT / 'audit').mkdir()
for name in ('manifest.json', 'summary.json', 'clock.json'):
    shutil.copyfile(RUN / name, OUT / name)
expected = dict(engine='lite', engine_version=ENGINE_VERSION, rng_version=RNG_VERSION,
                combat_version=COMBAT_VERSION, **teacher_identity())
models = {}
versions = {}
audits = {}
evaluations = {}
for fmt in ('duel', 'ffa4', 'team2v2'):
    result = summary['formats'][fmt]
    checkpoint = RUN / fmt / 'selected.pt'
    assert sha256(checkpoint) == result['checkpoint_sha256']
    model, state = load_model(checkpoint, fmt, 'cpu')
    validate_checkpoint(state, fmt, sha256(RUN / 'manifest.json'))
    actual = {key:state.get(key) for key in expected}
    assert actual == expected, (fmt, actual, expected)
    assert state['runner']['version'] == result['version'] > 0
    assert not state['runner'].get('pending_train')
    shutil.copyfile(checkpoint, OUT / 'checkpoints' / (fmt + '.pt'))
    shutil.copyfile(RUN / fmt / 'selection.json', OUT / (fmt + '_selection.json'))
    source = Path(state['runner']['teacher_shards'][0])
    audit = OUT / 'audit' / (fmt + '.jsonl.gz')
    turns = set()
    full = False
    count = 0
    with gzip.open(source, 'rt', encoding='utf-8') as stream, gzip.open(audit, 'wt', encoding='utf-8') as target:
        for line in stream:
            row, numeric_bytes = unpack_line(line)
            turns.add(row['turn'])
            full = full or len(row['candidates']) == 128
            target.write(line)
            count += 1
            if len(turns) >= 2 and full:
                break
            if count >= 256:
                raise ValueError('first teacher prefix lacks required audit coverage: ' + fmt)
    assert len(turns) >= 2 and full, fmt
    rows = read_raw_shards([audit], format_name=fmt)
    error = verify_numerics(model, rows)
    models[fmt] = model
    versions[fmt] = dict(version=result['version'], checkpoint_sha256=sha256(checkpoint))
    evaluations[fmt] = result['status'] + '; deterministic-lite Astra only; native strength not evaluated'
    audits[fmt] = dict(raw_rows=count, supervised_rows=len(rows), turns=sorted(turns),
                      full_candidates=full, python_lua_max_error=error, source=str(source),
                      source_sha256=sha256(source), audit_sha256=sha256(audit))
    print(json.dumps(dict(format=fmt, checkpoint=versions[fmt], audit=audits[fmt])), flush=True)

# Explicit local directory export uses the existing unbundled API. Competition
# archive assembly and its unchanged 16 MiB gate are separate operations.
addon = export(models, OUT, name='NeuralArena20261026', version=versions,
               package=False, evaluation=evaluations, identity=expected)
export_manifest = json.loads((OUT / 'export.json').read_text())
for fmt in models:
    export_manifest['models'][fmt]['python_lua_max_error'] = audits[fmt]['python_lua_max_error']
write_json(OUT / 'export.json', export_manifest)
files = {str(p.relative_to(addon)):sha256(p) for p in sorted(addon.rglob('*')) if p.is_file()}
write_json(OUT / 'installation_manifest.json', dict(run=str(RUN), source_revision='822082d654cd19a6474aa36f837137c1ec7cb83c',
    manifest_sha256=sha256(RUN / 'manifest.json'), checkpoints=versions, audits=audits, identity=expected,
    files=files, evaluation=evaluations, scope='local installation; not an SDK competition submission'))
archive = OUT.parent / 'lite_final_20261026_v2.tar.gz'
assert not archive.exists(), archive
with tarfile.open(archive, 'w:gz') as package:
    package.add(OUT, arcname=OUT.name)
print(json.dumps(dict(exported=str(addon), files=len(files), archive=str(archive),
                      archive_sha256=sha256(archive), bytes=archive.stat().st_size)), flush=True)
