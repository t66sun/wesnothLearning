"""Nominate at most one complete latest candidate against the champion.

Selection reuses a complete matching validation panel.  It never creates new
games, never reads the final holdout, and keeps the champion whenever the
candidate evidence is missing, underfilled or weaker.
"""
import json
from pathlib import Path


def _panel_complete(panel, fmt):
    comparison = (panel or {}).get('comparison', {}).get(fmt, {})
    blocks = int(comparison.get('blocks') or 0)
    return (panel is not None and comparison.get('status') in ('passed', 'not_passed')
            and comparison.get('distinct_scenarios',0)>=max(12,comparison.get('min_distinct',12))
            and blocks >= 12 and not comparison.get('missing_blocks', comparison.get('missing'))
            and not comparison.get('fault_games', comparison.get('faults'))
            and comparison.get('difference') is not None)


def validate_frozen_selection(path, selected_sha256):
    """Check a saved decision against the selected checkpoint bytes."""
    saved = json.loads(Path(path).read_text(encoding='utf-8'))
    if saved.get('selected_sha256') != selected_sha256:
        raise ValueError('selected checkpoint changed after selection was frozen')
    return saved
