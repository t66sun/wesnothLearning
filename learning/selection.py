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


def _same_layout(candidate, champion, fmt):
    return all(candidate.get(key) == champion.get(key) for key in ('format', 'engine_id', 'seed', 'control', 'blocks')) and candidate.get('format') == fmt


def reusable(candidate, champion, fmt):
    """Return (ok, reason) for reusing two recorded 12-block panels."""
    if not _panel_complete(candidate, fmt):
        return False, 'candidate panel incomplete'
    if not _panel_complete(champion, fmt):
        return False, 'champion panel incomplete'
    if not _same_layout(candidate, champion, fmt):
        return False, 'panels use different model, source, rule or schedule identity'
    if candidate['comparison'][fmt]['status'] != 'passed':
        return False, 'candidate did not pass its validation panel'
    return True, 'complete matching panels'


def decide(candidate, champion, fmt):
    """Choose the candidate only when its matched panel beats the champion."""
    ok, reason = reusable(candidate, champion, fmt)
    if not ok:
        return dict(choice='champion', reason=reason)
    candidate_score = candidate['comparison'][fmt]['difference']
    champion_score = champion['comparison'][fmt]['difference']
    if candidate_score > champion_score:
        return dict(choice='candidate', reason='candidate scored higher on the matched panel')
    return dict(choice='champion', reason='candidate did not beat the retained champion')


def validate_frozen_selection(path, selected_sha256):
    """Check a saved decision against the selected checkpoint bytes."""
    saved = json.loads(Path(path).read_text(encoding='utf-8'))
    if saved.get('selected_sha256') != selected_sha256:
        raise ValueError('selected checkpoint changed after selection was frozen')
    return saved
