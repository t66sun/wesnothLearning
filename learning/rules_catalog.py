"""Read the frozen rule identity without parsing capture provenance.

The full catalog embeds every raw native capture and is intentionally the audit
artifact. Runtime processes need only the immutable vocabulary, hashes, counts
and flags. Older frozen directories have no summary, so the full catalog remains
a supported fallback rather than a required migration.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


SUMMARY = 'catalog-summary.json'
ROOT = Path(__file__).resolve().parents[1]


def resolve_dir(value=None):
    """Resolve one rule directory consistently for features, jobs and adapters."""
    return Path(value or os.environ.get('WESNOTH_RULES_DIR') or
                ROOT / 'rules/1.18.8-training').resolve()


def _validate(metadata, rules_dir):
    rules_path = Path(rules_dir) / 'rules.json'
    if not rules_path.exists():
        raise RuntimeError('missing native 1.18.8 frozen rules; capture and freeze the real rule inventory first')
    digest = hashlib.sha256(rules_path.read_bytes()).hexdigest()
    if metadata.get('rules_file_sha256') != digest:
        raise ValueError('rules.json differs from the frozen catalog hash')
    if not metadata.get('source_hash'):
        raise ValueError('catalog is missing immutable rule identity')
    return metadata


def _training_acceptance(metadata, rules_dir):
    """Check the shared six-faction profile against compiled rules, not flags."""
    from engine_lite.audit import training_closure

    rules = json.loads((rules_dir / 'rules.json').read_bytes())
    if metadata.get('source_hash') != rules.get('source_hash'):
        raise ValueError('catalog/rules source provenance mismatch')
    if rules.get('source_version') != '1.18.8':
        raise ValueError('lite requires native 1.18.8 data')
    coverage_path = rules_dir / 'coverage.json'
    if not coverage_path.is_file():
        raise RuntimeError('lite P1/P2 acceptance is pending; training acceptance requires coverage.json')
    coverage = json.loads(coverage_path.read_bytes())
    closure = training_closure(rules, coverage)
    if not closure['implementation_complete']:
        raise RuntimeError('lite P1/P2 acceptance is pending; training closure is not ready: '
                           f'missing={closure["missing_unit_ids"]}, '
                           f'unsupported={closure["unsupported_unit_ids"]}')
    profile_path = ROOT / closure['profile']
    return dict(scope=closure['scope'], profile=closure['profile'],
                profile_sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest(),
                rules_file_sha256=metadata['rules_file_sha256'],
                unit_count=closure['unit_count'], unit_ids=closure['unit_ids'],
                implementation_complete=True,
                native_semantics_accepted=False, performance_accepted=False)


def load(rules_dir=None, *, require_accepted=True, acceptance_scope='training'):
    """Load small runtime metadata and check the actual supported training scope.

    Training readiness permits recorded approximations and excludes campaign-only
    scripts; it does not claim whole-inventory semantic or performance acceptance.
    ``acceptance_scope='full'`` retains the original three-flag release gate.
    Older packages without a summary retain their full catalog fallback.
    """
    if acceptance_scope not in ('training', 'full'):
        raise ValueError(f'unknown rule acceptance scope: {acceptance_scope}')
    rules_dir = resolve_dir(rules_dir)
    summary_path = rules_dir / SUMMARY
    if summary_path.exists() and (not require_accepted or acceptance_scope == 'training'):
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        if summary.get('summary_version') != 1:
            raise ValueError('unsupported catalog summary version')
        metadata = _validate(summary, rules_dir)
        if require_accepted:
            metadata['training_acceptance'] = _training_acceptance(metadata, rules_dir)
        return metadata
    catalog_path = rules_dir / 'catalog.json'
    if not catalog_path.exists():
        raise RuntimeError('missing native 1.18.8 frozen rules; capture and freeze the real rule inventory first')
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    metadata = _validate(catalog, rules_dir)
    fully_accepted = (catalog.get('complete') and catalog.get('native_accepted')
                      and catalog.get('performance_accepted'))
    if require_accepted and not fully_accepted:
        if acceptance_scope == 'full':
            raise RuntimeError('lite P1/P2 acceptance is pending')
        metadata['training_acceptance'] = _training_acceptance(metadata, rules_dir)
    return metadata
