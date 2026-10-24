"""Maintained Astra teacher source adapted to the deterministic lite rules.

The frozen opponent package in ``data/opponents/gpt6astra.zip`` stays
read-only.  This package holds the derived source that the lite host loads for
Astra seats, records its lineage, and can rebuild a deployable archive.
"""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

PARENT_PACKAGE = Path(__file__).resolve().parents[2] / 'data/opponents/gpt6astra.zip'
SOURCE = Path(__file__).resolve().parent / 'gpt6astra'
PROFILE = 'expected_damage_v1'


def source_digest():
    """Hash the derived source tree, including every file the host loads."""
    digest = hashlib.sha256()
    for path in sorted(SOURCE.rglob('*')):
        if path.is_file():
            digest.update(path.relative_to(SOURCE).as_posix().encode())
            digest.update(b'\0')
            digest.update(path.read_bytes())
            digest.update(b'\0')
    return digest.hexdigest()


def parent_digest():
    if not PARENT_PACKAGE.is_file():
        return None
    return hashlib.sha256(PARENT_PACKAGE.read_bytes()).hexdigest()


def lua_modules():
    """Return host modules keyed exactly as the teacher's require calls."""
    return {'astra/' + path.name: path.read_text(encoding='utf-8')
            for path in sorted((SOURCE / 'lua').glob('*.lua'))}


def identity():
    """Stable execution identity; the parent hash is lineage, not identity."""
    return {'teacher': 'gpt6astra', 'teacher_profile': PROFILE,
            'teacher_source_sha256': source_digest()}


def lineage():
    return dict(identity(), teacher_parent_sha256=parent_digest())


def build(target):
    """Write the derived add-on archive for a native or external deployment."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SOURCE.rglob('*')):
            if path.is_file():
                archive.write(path, 'gpt6astra/' + path.relative_to(SOURCE).as_posix())
    return target
