"""Match stock engine events to independently captured public policy inputs."""
from copy import deepcopy
from .common import ROOT, sha256

KINDS = ('recruit', 'recall', 'moveto', 'attack', 'advance')
PUBLIC_ROW = ('schema', 'global', 'opponents', 'spatial', 'candidates', 'timing',
              'side', 'turn', 'format', 'version', 'memory_write')


def capture_sha256():
    import hashlib
    paths = sorted((ROOT / 'lua/stock_rca_capture').glob('*.lua'))
    return hashlib.sha256(''.join(p.name + ':' + sha256(p) + '\n' for p in paths).encode()).hexdigest()


def frames_to_labels(frames, *, side, candidates_fn):
    """One context labels at most one event; later actions cannot reuse stale inputs.

    candidates_fn receives only the public context, never an event or referee
    snapshot. Native contexts already contain shared candidates.lua output.
    """
    coverage = {kind: dict(matched=0, unmatched=0, ambiguous=0) for kind in KINDS}
    rows, contexts, latest, used = [], {}, None, set()
    for frame in frames:
        if frame.get('side') != side:
            continue
        kind = frame.get('kind')
        if frame.get('type') == 'CONTEXT':
            latest = frame['id']
            contexts = {latest: frame}
            continue
        if frame.get('type') == 'AFTER':
            for row in reversed(rows):
                if row['capture_context'] == frame.get('context'):
                    row['memory_write'] = deepcopy(frame['memory_write'])
                    break
            continue
        if frame.get('type') != 'ACTION' or kind not in coverage:
            continue
        context_id = frame.get('context')
        context = contexts.get(context_id)
        fresh = (context is not None and context_id == latest and context_id not in used
                 and context.get('turn') == frame.get('turn'))
        used.add(context_id)
        if not fresh or frame.get('visible') is not True:
            coverage[kind]['unmatched'] += 1
            continue
        row = {k: deepcopy(v) for k, v in context['row'].items() if k in PUBLIC_ROW}
        candidates = candidates_fn(deepcopy(row))
        unit, target, to = frame.get('unit', {}), frame.get('target', {}), frame.get('to', {})
        actual = dict(kind='move' if kind == 'moveto' else kind)
        if kind == 'recruit':
            actual.update(type=frame.get('type_id'), x=to.get('x'), y=to.get('y'))
        elif kind in ('moveto', 'attack'):
            dest = to if kind == 'moveto' else target
            actual.update(x=unit.get('x'), y=unit.get('y'), tx=dest.get('x'), ty=dest.get('y'))
            if kind == 'attack' and frame.get('weapon') is not None:
                actual['weapon'] = frame['weapon']
        matches = [i for i, c in enumerate(candidates) if kind not in ('recall', 'advance')
                   and all(value is not None and c.get(key) == value for key, value in actual.items())]
        ambiguous = len(matches) > 1
        choice = matches[0] if len(matches) == 1 else -1
        coverage[kind]['ambiguous' if ambiguous else 'matched' if choice >= 0 else 'unmatched'] += 1
        if choice >= 0:
            # Include disambiguating fields only when the event has one legal interpretation.
            actual = {k: v for k, v in candidates[choice].items()
                      if k in ('kind', 'type', 'x', 'y', 'tx', 'ty', 'weapon', 'full')}
        row.update(candidates=candidates, choice=choice, actual=actual, label_ambiguous=ambiguous,
                   representable=choice >= 0, source='stock_rca', teacher='wesnoth_default_rca',
                   capture_context=context_id, action_source='engine_events', committed=True,
                   log_probability=0, value=0, value_valid=False)
        rows.append(row)
    return rows, coverage
