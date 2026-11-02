"""Finite native weapon declarations supported by the compact combat core."""
from .wml import children

_DISPLAY = {'id', 'name', 'female_name', 'description', 'special_note',
            'name_inactive', 'female_name_inactive', 'description_inactive', 'halo_image'}
_BACKSTAB = 'enemy_of(self, flanker) and not flanker.petrified where flanker = unit_at(direction_from(loc, other.facing))'


def compile_special(tag, cfg):
    attrs = {k: v for k, v in cfg.items() if not k.isdecimal() and k not in _DISPLAY}
    nested = list(children(cfg))
    if tag == 'damage' and attrs == dict(active_on='offense', multiply=2):
        if len(nested) == 1 and nested[0][0] == 'filter_opponent':
            condition = nested[0][1]
            if set(condition) == {'formula'} and ' '.join(condition['formula'].split()) == _BACKSTAB:
                return 'backstab', {}
    if nested:
        return None
    if tag in ('poison', 'slow', 'firststrike', 'petrifies', 'stun', 'swarm') and not attrs:
        return tag, {}
    if tag == 'drains' and set(attrs) <= {'value'}:
        value = attrs.get('value', 50)
        if isinstance(value, int) and 0 <= value <= 100:
            return 'drains', dict(drain_percent=value)
    if tag == 'plague' and set(attrs) <= {'type'}:
        target = attrs.get('type')
        if isinstance(target, str) and target and target != 'null':
            return 'plague', dict(plague_type=target)
    if tag == 'berserk' and attrs == dict(value=30):
        return 'berserk', {}
    if tag == 'chance_to_hit':
        if attrs == dict(value=70, cumulative=False):
            return 'magical', {}
        if attrs == dict(active_on='offense', value=60, cumulative=True):
            return 'marksman', {}
        if attrs == dict(apply_to='opponent', active_on='defense', cumulative=True, sub=10):
            return 'deflect', dict(defense_cth_sub=10)
    if tag == 'damage':
        if attrs == dict(active_on='offense', apply_to='both', multiply=2):
            return 'charge', {}
        if attrs.get('apply_to') == 'opponent' and set(attrs) == {'apply_to', 'multiply'}:
            if attrs['multiply'] in (0.6, 0.75):
                return 'absorb', dict(opponent_damage_percent=round(attrs['multiply']*100))
    if tag == 'attacks' and attrs.get('value') in (0, 1):
        value = attrs['value']
        if attrs == dict(apply_to='opponent', active_on='offense', value=value):
            return 'swift' if value == 0 else 'shock', dict(opponent_attacks=value)
    return None
