"""Pack data/replays/202412 into one tar and prove every member is byte-identical."""
from __future__ import annotations

import hashlib
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/replays/202412'
TARGET = ROOT / 'data/replays/202412.tar'


def sha256(stream, chunk=1 << 20):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(chunk), b''):
        digest.update(block)
    return digest.hexdigest()


def main():
    files = sorted(p for p in BASE.rglob('*') if p.is_file())
    if TARGET.exists():
        sys.exit(f'{TARGET} already exists')
    with tarfile.open(TARGET, 'w', format=tarfile.GNU_FORMAT) as archive:
        for path in files:
            archive.add(path, arcname=str(path.relative_to(BASE.parent).as_posix()),
                        recursive=False)
    manifest = {}
    with tarfile.open(TARGET) as archive:
        members = [m for m in archive.getmembers() if m.isfile()]
        for member in members:
            stream = archive.extractfile(member)
            manifest[member.name] = dict(sha256=sha256(stream), size=member.size)
    mismatched, missing = [], []
    for path in files:
        name = path.relative_to(BASE.parent).as_posix()
        entry = manifest.get(name)
        if entry is None:
            missing.append(name)
            continue
        if entry['sha256'] != sha256(path.open('rb')) or entry['size'] != path.stat().st_size:
            mismatched.append(name)
    report = dict(members=len(members), files=len(files), missing=missing[:5],
                  mismatched=mismatched[:5], missing_total=len(missing),
                  mismatched_total=len(mismatched), tar_bytes=TARGET.stat().st_size)
    (ROOT / 'tmp/replay_tar_verify.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
