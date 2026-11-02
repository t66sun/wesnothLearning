"""Compile supported advancement declarations from immutable native captures."""
from .wml import children

_PRESENTATION = {'name', 'description', 'image'}
_EFFECTS = [
    {'apply_to': 'hitpoints', 'increase_total': 3, 'heal_full': True},
    {'apply_to': 'max_experience', 'increase': '20%'},
    {'apply_to': 'status', 'remove': 'poisoned'},
    {'apply_to': 'status', 'remove': 'slowed'},
]


def compile_advancement(raw):
    declarations = [cfg for tag, cfg in children(raw) if tag == 'advancement']
    if not declarations:
        return False, []
    if len(declarations) == 1:
        cfg = declarations[0]
        attributes = {k: v for k, v in cfg.items()
                      if not k.isdecimal() and k not in _PRESENTATION}
        effects = list(children(cfg))
        if (attributes == dict(id='amla_default', max_times=100, strict_amla=True)
                and effects == [('effect', effect) for effect in _EFFECTS]):
            return True, []
    return False, ['unsupported_advancement_declaration']
