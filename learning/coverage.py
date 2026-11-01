"""The one Python definition of when a teacher intent survives candidate retention.

The Lua generators keep their own field lists; this module is the single Python
statement of the same contract, so the matching test and the miss reason cannot
disagree about what "the same action" means.
"""

FIELDS = {'end_turn': (), 'move': ('x', 'y', 'tx', 'ty', 'full'),
          'attack': ('x', 'y', 'tx', 'ty', 'weapon'),
          'move_attack': ('x', 'y', 'tx', 'ty', 'ex', 'ey', 'weapon'),
          'recruit': ('type', 'x', 'y')}


def matches(candidate, action):
    """True when the candidate is the same action as the intent."""
    if candidate.get('kind') != action.get('kind'):
        return False
    return all(candidate.get(k) == action.get(k) for k in FIELDS[action['kind']])


def matching(candidates, action):
    """Index of the first candidate equal to the intent, else -1."""
    for i, candidate in enumerate(candidates):
        if matches(candidate, action):
            return i
    return -1


def actor(candidate):
    """The acting unit's hex, as the intent records it."""
    return candidate.get('x'), candidate.get('y')


def destination(candidate):
    """The hex the action lands on; a stationary action stays put."""
    x, y = candidate.get('x'), candidate.get('y')
    return candidate.get('tx', x), candidate.get('ty', y)


def reason(candidates, action):
    """Why an unmatched intent is absent: the first retention stage that lost it.

    Only candidates of the intent's own kind are considered, so a kind that was
    generated but filtered by the class quota still reports the finer cause.
    """
    kind = action['kind']
    same = [c for c in candidates if c.get('kind') == kind]
    if not same:
        return 'kind_absent'
    if kind == 'recruit':
        typed = [c for c in same if c.get('type') == action.get('type')]
        return 'slot_absent' if typed else 'type_absent'
    here = [c for c in same if actor(c) == actor(action)]
    if not here:
        return 'actor_absent'
    there = [c for c in here if destination(c) == destination(action)]
    if not there:
        return 'destination_absent'
    if kind == 'attack':
        return 'weapon_absent'
    if kind == 'move_attack':
        enemy = (action.get('ex', action.get('tx')), action.get('ey', action.get('ty')))
        if not any((c.get('ex', c.get('tx')), c.get('ey', c.get('ty'))) == enemy for c in there):
            return 'enemy_absent'
        return 'weapon_absent'
    return 'mode_absent'
