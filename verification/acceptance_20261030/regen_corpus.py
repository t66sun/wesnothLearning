"""Regenerate the curated corpus from the packed months and compare it with the shipped one.

Usage: python3 regen_corpus_srv.py <root> <stage> <output>

<root> holds `data/replays_curated/` and `data/replays/{202412,202607,202608,202609}.tar`.
Only the members named by the recorded inventory are extracted, then
`learning.replay_curate` runs into a fresh directory.

`curated_sha256` records the gzip container, whose bytes follow the zlib build
(1.3 on Ubuntu 24.04, 1.3.2 on the Windows reference), so the row comparison masks
that one field and checks it separately against the shipped file itself.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

MONTHS = ('202412', '202607', '202608', '202609')
PLATFORM_FIELD = 'curated_sha256'


def main(argv: list[str]) -> int:
    root, stage, output = Path(argv[1]), Path(argv[2]), Path(argv[3])
    corpus = root / 'data/replays_curated'
    for path in (stage, output):
        shutil.rmtree(path, ignore_errors=True)

    recorded = {json.loads(line)['source']: json.loads(line)
                for line in (corpus / 'inventory.jsonl').read_text(encoding='utf-8').splitlines()
                if line.strip()}
    print(f'recorded sources: {len(recorded)}')

    missing = set(recorded)
    for month in MONTHS:
        with tarfile.open(root / 'data/replays' / f'{month}.tar') as tar:
            for member in tar:
                if member.name in missing:
                    target = stage / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(tar.extractfile(member).read())
                    missing.discard(member.name)
    staged = len(list(stage.rglob('*.bz2')))
    print(f'staged: {staged} missing: {len(missing)} {sorted(missing)[:3]}')

    origin = json.loads((corpus / 'summary.json').read_text(encoding='utf-8'))['origin']
    done = subprocess.run([sys.executable, '-m', 'learning.replay_curate', '--source', str(stage),
                           '--output', str(output), '--origin', origin],
                          cwd=root, capture_output=True, text=True)
    if done.returncode != 0:
        print(done.stdout[-2000:], done.stderr[-2000:])
        return 1

    fresh = {json.loads(line)['source']: json.loads(line)
             for line in (output / 'inventory.jsonl').read_text(encoding='utf-8').splitlines()
             if line.strip()}
    differing_fields = sorted({name for source, row in fresh.items()
                               for name, value in row.items()
                               if name != PLATFORM_FIELD and recorded[source][name] != value})
    print(f'rows: {len(fresh)} fields differing besides {PLATFORM_FIELD}: {differing_fields or "none"}')

    shipped_bad = regenerated_payload_bad = decisions = 0
    for source, row in fresh.items():
        decisions += row['actions']
        regenerated = (output / row['curated_path']).read_bytes()
        if hashlib.sha256(gzip.decompress(regenerated)).hexdigest() != recorded[source]['payload_sha256']:
            regenerated_payload_bad += 1
            print('  payload differs from the recorded one', source)
        packed = (corpus / recorded[source]['curated_path']).read_bytes()
        if hashlib.sha256(packed).hexdigest() != recorded[source][PLATFORM_FIELD]:
            shipped_bad += 1
            print('  shipped container digest mismatch', source)
    summary = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
    print(f'decision intents: {decisions}  shipped container mismatches: {shipped_bad}'
          f'  regenerated payload mismatches: {regenerated_payload_bad}')
    print('summary:', {k: summary[k] for k in ('source_files', 'selected_replays',
                                               'selected_families', 'selected_formats')})
    ok = (not differing_fields and shipped_bad == 0 and regenerated_payload_bad == 0
          and not missing and staged == len(recorded) and decisions == 359526)
    print('RESULT:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
