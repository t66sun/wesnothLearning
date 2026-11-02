"""Recover native weapon attributes omitted by older compact captures."""
import math

from .wml import children
from .weapon_specials import compile_special


def compile_weapons(raw, compact):
    declarations = [cfg for tag, cfg in children(raw) if tag == 'attack']
    if len(declarations) != len(compact):
        raise ValueError('raw and compact weapon inventories differ')
    weapons, unsupported = [], []
    for declaration, original in zip(declarations, compact):
        if declaration.get('name') != original['id']:
            raise ValueError('raw and compact weapon order differs')
        weapon = dict(original)
        for field in ('accuracy', 'parry'):
            value = declaration.get(field, 0)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f'weapon {field} must be an integer')
            weapon[field] = value
        for field in ('attack_weight', 'defense_weight'):
            value = float(declaration.get(field, 1))
            if not math.isfinite(value):
                raise ValueError(f'weapon {field} must be a finite number')
            weapon[field] = value
        weapon['specials'] = []
        for tag, group in children(declaration):
            if tag != 'specials':
                continue
            for tag, cfg in children(group):
                compiled = compile_special(tag, cfg)
                if compiled is None:
                    unsupported.append(f'weapon:{weapon["id"]}:unsupported_declaration:{tag}:{cfg.get("id", tag)}')
                    continue
                name, fields = compiled
                weapon['specials'].append(name)
                weapon.update(fields)
        weapons.append(weapon)
    return weapons, unsupported
