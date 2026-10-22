"""Hash an explicitly selected native installation without running the game.

This inventories source files/scopes, not interpreted WML unit semantics. Runtime
captures must be checked against it; no raw-text parser can replace native WML
preprocessing or certify all campaign-dependent definitions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def build_inventory(data_root, *, binary=None):
    data_root = Path(data_root).resolve()
    if not (data_root / 'core/units').is_dir() or not (data_root / 'campaigns').is_dir():
        raise ValueError('data_root must name a complete native data directory containing core/units and campaigns')
    files = {}
    for path in sorted(data_root.rglob('*')):
        if path.is_file():
            files[path.relative_to(data_root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    campaigns = sorted(p.name for p in (data_root / 'campaigns').iterdir()
                       if p.is_dir() and (p / '_main.cfg').is_file())
    source = dict(source_version='1.18.8', files=files, required_scopes=['core'] + campaigns,
                  note='version label must be verified against the selected 1.18.8 distribution; no executable was run')
    if binary is not None:
        source['binary_sha256'] = hashlib.sha256(Path(binary).read_bytes()).hexdigest()
    source['manifest_sha256'] = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', required=True)
    parser.add_argument('--binary')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = build_inventory(args.data_root, binary=args.binary)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(f'choose a new immutable inventory path: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
