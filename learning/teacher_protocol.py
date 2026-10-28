"""A teacher is queried only through a capability its record declares.

The stock RCA teacher publishes decisions by observing full native games, so it
has no per-decision query and therefore no DAgger channel. Any code path that
wants to query a teacher per decision must ask here first; requesting a query
from a teacher that does not expose one is an error, never a silent fallback to
another teacher.
"""
STOCK_STATUS = 'unsupported_with_stock_rca'


def dagger_status(record):
    """DAgger availability of the frozen teacher record, recorded in state and reports."""
    query = (record or {}).get('query')
    return 'active' if query and query != 'none' else STOCK_STATUS


def require_query(record):
    """Returns the declared per-decision query of a record or raises."""
    query = (record or {}).get('query')
    if query != 'per_decision':
        raise ValueError('teacher has no per-decision query capability: ' + str((record or {}).get('kind')))
    return query


def dagger_teacher(record, path):
    """The controller a DAgger relabel pass may use; stock records have none."""
    require_query(record)
    if not path:
        raise ValueError('queryable teacher record lacks its controller path')
    return path


def stock_capture_job_sides(players):
    """Every seat of a stock teacher game is baseline, so every seat can be labelled."""
    return list(range(1, players + 1))
