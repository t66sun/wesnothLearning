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
OUT = ROOT.parent / 'exports/lite_final_20261026_draft'
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
    previous = ROOT.parent / 'exports/lite_final_20261026_v2/audit' / (fmt + '.jsonl.gz')
    turns = set()
    full = False
    count = 0
    if previous.exists() and previous.stat().st_size > 30:
        shutil.copyfile(previous, audit)
        with gzip.open(audit, 'rt', encoding='utf-8') as stream:
            for line in stream:
                row, numeric_bytes = unpack_line(line)
                turns.add(row['turn']);full = full or len(row['candidates']) == 128;count += 1
    else:
        with gzip.open(source, 'rt', encoding='utf-8') as stream, gzip.open(audit, 'wt', encoding='utf-8') as target:
            for line in stream:
                row, numeric_bytes = unpack_line(line)
                turns.add(row['turn']);full = full or len(row['candidates']) == 128
                target.write(line);count += 1
                if len(turns) >= 2 and full: break
                if count >= 256: raise ValueError('audit prefix coverage missing: ' + fmt)
    assert len(turns) >= 2 and full, fmt
    reused = fmt in ('duel', 'ffa4')
    if fmt == 'duel':
        assert sha256(audit) == 'e0d11fde3a21f6ca474e4ca36461dd430e5429c8ac5af44fdd7359b5f47b536c'
        assert sha256(checkpoint) == '1f619c272dd132aaef5ddd7c549b8fc305b1b5195ad525d5596ddb95774d19cf'
        error = 7.683312901463069e-6
    elif fmt == 'ffa4':
        assert sha256(checkpoint) == 'e1148429ee936c5c163f09502e9381dba0139dae6c69aa00f200c7233c5b8c25'
        assert sha256(audit) == sha256(previous)
        error = 2.210623698939429e-5
    else:
        rows = read_raw_shards([audit], format_name=fmt)
        try:
            error = verify_numerics(model, rows)
        except ValueError as exc:
            import re
            match = re.fullmatch(r'team2v2: Python/Lua error ([0-9.eE+-]+) exceeds 1e-5', str(exc))
            if not match: raise
            error = float(match[1])
    passed = error <= 1e-5
    models[fmt] = model
    versions[fmt] = dict(version=result['version'], checkpoint_sha256=sha256(checkpoint))
    evaluations[fmt] = result['status'] + '; deterministic-lite Astra only; native strength not evaluated'
    audits[fmt] = dict(raw_rows=count, supervised_rows=count, turns=sorted(turns),
                      full_candidates=full, python_lua_max_error=error, source=str(source),
                      source_sha256=sha256(source), audit_sha256=sha256(audit),
                      status="passed" if passed else "not_passed", reused=reused, threshold=1e-5)
    print(json.dumps(dict(format=fmt, checkpoint=versions[fmt], audit=audits[fmt])), flush=True)

# Explicit local directory export uses the existing unbundled API. Competition
# archive assembly and its unchanged 16 MiB gate are separate operations.
addon = export(models, OUT, name='NeuralArena20261026', version=versions,
               package=False, evaluation=evaluations, identity=expected)
export_manifest = json.loads((OUT / 'export.json').read_text())
for fmt in models:
    export_manifest['models'][fmt]['python_lua_max_error'] = audits[fmt]['python_lua_max_error']
    export_manifest['models'][fmt]['numeric_audit_status'] = audits[fmt]['status']
write_json(OUT / 'export.json', export_manifest)
files = {str(p.relative_to(addon)):sha256(p) for p in sorted(addon.rglob('*')) if p.is_file()}
write_json(OUT / 'installation_manifest.json', dict(run=str(RUN), source_revision='822082d654cd19a6474aa36f837137c1ec7cb83c',
    manifest_sha256=sha256(RUN / 'manifest.json'), checkpoints=versions, audits=audits, identity=expected,
    files=files, evaluation=evaluations, installation_allowed=all(a['status']=='passed' for a in audits.values()),
    scope='UNACCEPTED draft for review; original numerical gate retained; not installed; not an SDK competition submission'))
archive = OUT.parent / 'lite_final_20261026_draft.tar.gz'
assert not archive.exists(), archive
with tarfile.open(archive, 'w:gz') as package:
    package.add(OUT, arcname=OUT.name)
print(json.dumps(dict(exported=str(addon), files=len(files), archive=str(archive),
                      archive_sha256=sha256(archive), bytes=archive.stat().st_size)), flush=True)
