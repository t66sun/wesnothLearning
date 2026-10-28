"""Match stock engine events to independently captured public policy inputs."""
from copy import deepcopy
from .common import ROOT, sha256

KINDS = ('recruit', 'recall', 'moveto', 'attack', 'advance')
PUBLIC_ROW = ('schema', 'global', 'opponents', 'spatial', 'candidates', 'timing',
              'side', 'turn', 'format', 'version', 'memory_write')


def capture_sha256():
    paths = sorted((ROOT / 'lua/stock_rca_capture').glob('*.lua'))
    return capture_sha256_from({p.relative_to(ROOT).as_posix(): sha256(p) for p in paths})


def capture_sha256_from(digests):
    """Identity of the shipped capture sources, from ``path -> file sha256``."""
    import hashlib
    rows = sorted((path.rsplit('/', 1)[-1], digest) for path, digest in digests.items()
                  if path.startswith('lua/stock_rca_capture/') and path.endswith('.lua'))
    return hashlib.sha256(''.join(name + ':' + digest + '\n' for name, digest in rows).encode()).hexdigest()


INTENT = dict(recruit=('kind', 'type', 'x', 'y'), move=('kind', 'x', 'y', 'tx', 'ty'),
              attack=('kind', 'x', 'y', 'tx', 'ty', 'weapon'),
              move_attack=('kind', 'x', 'y', 'tx', 'ty', 'ex', 'ey', 'weapon'))


def intent(candidate):
    """Public fields that name the action, ignoring candidate scoring fields."""
    fields = INTENT.get(candidate.get('kind'), ('kind',))
    return tuple(candidate.get(field) for field in fields)

def frames_to_labels(frames, *, side, candidates_fn):
    """One observer context labels the events of one engine decision.

    The observer scores zero, so the candidate loop evaluates it before the
    engine picks its next action and emits a CONTEXT. A stock decision may
    execute several engine events: a move-and-attack emits a moveto followed by
    an attack, and a recruit decision places a whole batch. All events sharing
    one context belong to that decision, so one of them matches a candidate and
    the rest are counted as ``merged`` (folded into the same label) instead of
    becoming unmatched events. A context that arrives before any action used it
    is superseded by the next CONTEXT or retired by an INVALIDATE frame and can
    never label a later action. candidates_fn receives only the public context,
    never an event or referee snapshot. Native contexts already contain shared
    candidates.lua output.
    """
    coverage = {kind: dict(matched=0, unmatched=0, ambiguous=0, merged=0) for kind in KINDS}
    rows, used, patches = [], set(), {}
    latest, current, group = None, None, None

    def record(kind, context, actual, visible, extra=None):
        if context is None or visible is not True:
            coverage[kind]['unmatched'] += 1
            return
        context_id = context['id']
        row = {k: deepcopy(v) for k, v in context['row'].items() if k in PUBLIC_ROW}
        if context_id in patches:
            row['memory_write'] = deepcopy(patches[context_id])
        candidates = candidates_fn(deepcopy(row))
        matches = [i for i, c in enumerate(candidates)
                   if all(value is not None and c.get(key) == value for key, value in actual.items())]
        # One action can appear as several scoring variants (a full move and a
        # stop-short move name the same destination). They are one intent, so the
        # label stays unique; only intents that differ are ambiguous.
        intents = {intent(candidates[i]) for i in matches}
        ambiguous = len(intents) > 1
        choice = matches[0] if matches and not ambiguous else -1
        coverage[kind]['ambiguous' if ambiguous else 'matched' if choice >= 0 else 'unmatched'] += 1
        if choice >= 0:
            # The label is the matched candidate itself, so validation can compare
            # every field the executed action intent contains.
            actual = deepcopy(candidates[choice])
        row.update(candidates=candidates, choice=choice, actual=actual, label_ambiguous=ambiguous,
                   representable=choice >= 0, source='stock_rca', teacher='wesnoth_default_rca',
                   capture_context=context_id, action_source='engine_events', committed=True,
                   log_probability=0, value=0, value_valid=False)
        if extra:
            row['extra_actions'] = deepcopy(extra)
        rows.append(row)

    def flush():
        nonlocal group
        decision, group = group, None
        if not decision:
            return
        context, actions = decision
        kinds = [action.get('kind') for action in actions]
        if len(actions) == 2 and kinds == ['moveto', 'attack']:
            move, strike = actions
            unit, dest, target = move.get('unit', {}), move.get('to', {}), strike.get('target', {})
            if strike.get('unit') == dest and target:
                coverage['moveto']['merged'] += 1
                actual = dict(kind='move_attack', x=unit.get('x'), y=unit.get('y'),
                              tx=dest.get('x'), ty=dest.get('y'),
                              ex=target.get('x'), ey=target.get('y'))
                if strike.get('weapon') is not None:
                    actual['weapon'] = strike['weapon']
                record('attack', context, actual,
                       move.get('visible') is True and strike.get('visible') is True)
                return
        if len(actions) > 1 and set(kinds) == {'recruit'}:
            first = actions[0]
            coverage['recruit']['merged'] += len(actions) - 1
            record('recruit', context,
                   dict(kind='recruit', type=first.get('type_id'),
                        x=first.get('to', {}).get('x'), y=first.get('to', {}).get('y')),
                   first.get('visible'), extra=actions[1:])
            return
        for action in actions:
            kind = action.get('kind')
            if kind not in coverage:
                continue
            unit, to, target = action.get('unit', {}), action.get('to', {}), action.get('target', {})
            if kind == 'recruit':
                actual = dict(kind='recruit', type=action.get('type_id'), x=to.get('x'), y=to.get('y'))
            elif kind == 'moveto':
                actual = dict(kind='move', x=unit.get('x'), y=unit.get('y'),
                              tx=to.get('x'), ty=to.get('y'))
            elif kind == 'attack':
                actual = dict(kind='attack', x=unit.get('x'), y=unit.get('y'),
                              tx=target.get('x'), ty=target.get('y'))
                if action.get('weapon') is not None:
                    actual['weapon'] = action['weapon']
            else:
                actual = dict(kind=kind)
            record(kind, context, actual, action.get('visible'))

    for frame in frames:
        frame_type = frame.get('type')
        if frame_type == 'INVALIDATE':
            if frame.get('side') == side and frame.get('context') == latest:
                latest = None
            continue
        if frame.get('side') != side:
            continue
        if frame_type == 'CONTEXT':
            flush()
            latest = frame['id']
            current = frame
            continue
        if frame_type == 'AFTER':
            patches[frame.get('context')] = frame['memory_write']
            continue
        if frame_type != 'ACTION':
            continue
        kind = frame.get('kind')
        context_id = frame.get('context')
        fresh = (latest is not None and context_id == latest and context_id not in used
                 and current.get('turn') == frame.get('turn'))
        if fresh:
            used.add(context_id)
            group = (current, [frame])
        elif group and group[0]['id'] == context_id:
            group[1].append(frame)
        elif kind in coverage:
            coverage[kind]['unmatched'] += 1
    flush()
    return rows, coverage
