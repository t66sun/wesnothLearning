"""Recover native weapon attributes omitted by older compact captures."""
from .wml import children


def compile_weapons(raw, compact):
    declarations = [cfg for tag, cfg in children(raw) if tag == 'attack']
    if len(declarations) != len(compact):
        raise ValueError('raw and compact weapon inventories differ')
    weapons = []
    for declaration, original in zip(declarations, compact):
        if declaration.get('name') != original['id']:
            raise ValueError('raw and compact weapon order differs')
        weapon = dict(original)
        for field in ('accuracy', 'parry'):
            value = declaration.get(field, 0)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f'weapon {field} must be an integer')
            weapon[field] = value
        weapons.append(weapon)
    return weapons
