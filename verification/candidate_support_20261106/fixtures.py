"""Small explicit public tactical states; no sampled games or hidden labels."""
import copy


def unit(rules, name, kind, side, x, y, width, *, hp=None, moves=0, attacks=1, leader=False, status=()):
    data = rules['units'][kind]
    return dict(id=name, unit_type=kind, side=side, pos=(y - 1) * width + x - 1,
                hp=data['hp'] if hp is None else hp, moves=moves, attacks_left=attacks,
                leader=leader, xp=0, status=list(status), traits=[], acted=False)


def board(rules, width=24, height=9, *, gold=0, recruits=(), fog=False):
    return dict(width=width, height=height, terrain=['Gg'] * (width * height),
        units=[], seed=228, max_turns=30, allow_approximate=True,
        sides=[dict(id=side, team=str(side), gold=gold if side == 1 else 0,
                    recruit=list(recruits) if side == 1 else [], fog=fog, shroud=fog,
                    share_view=False, share_maps=False) for side in (1, 2)])


def tile(spec, x, y, terrain):
    spec['terrain'][(y - 1) * spec['width'] + x - 1] = terrain


def put(spec, rules, name, kind, side, x, y, **kwargs):
    spec['units'].append(unit(rules, name, kind, side, x, y, spec['width'], **kwargs))


def leaders(spec, rules, *, own=(2, 2), enemy=(23, 8)):
    tile(spec, *own, 'Kh')
    put(spec, rules, 'leader', 'Lieutenant', 1, *own, attacks=0, leader=True)
    put(spec, rules, 'enemy-leader', 'Orcish Leader', 2, *enemy, attacks=0, leader=True)


def cases(rules):
    result = []

    # More than eight empty connected castles. All role pairs cost exactly 34.
    spec = board(rules, gold=rules['units']['Spearman']['cost'] + rules['units']['Mage']['cost'],
                 recruits=('Spearman', 'Mage'))
    for x in range(2, 7):
        for y in range(2, 7):
            tile(spec, x, y, 'Ch')
    leaders(spec, rules, own=(2, 4))
    put(spec, rules, 'threat', 'Orcish Grunt', 2, 11, 4)
    result.append(dict(name='recruit_positions', theme='recruitment', spec=spec,
        goal='Affordable Spearman/Mage pair on distinct castles outside public next-turn attack reach.'))

    # Thirty-two direct attacks compete with recruit slots; the late actor's
    # ranged weapon can kill while its retained melee weapon cannot.
    spec = board(rules, width=39, gold=100, recruits=('Spearman', 'Mage'))
    for x in range(2, 8):
        tile(spec, x, 7, 'Ch')
    leaders(spec, rules, own=(2, 7), enemy=(38, 8))
    positions = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31]
    for index, x in enumerate(positions):
        kind = 'Elvish Marksman' if x == 9 else 'Elvish Archer'
        put(spec, rules, f'archer-{index:02}', kind, 1, x, 3)
        put(spec, rules, f'target-{index:02}', 'Orcish Grunt', 2, x, 4, hp=20 if x == 9 else None)
    # Keep visible enemy count at the production 16-enemy cap by making the
    # final target the enemy leader; this avoids an entity-cap confound.
    spec['units'] = [row for row in spec['units'] if row['id'] != 'enemy-leader']
    spec['units'][-1]['leader'] = True
    result.append(dict(name='combat_slots', theme='attack_order', spec=spec,
        actor='archer-04', goal='At this decision, retain the same actor weapon with higher kill probability and lower retaliation.'))

    for name, is_leader in [('retreat', False), ('leader_safety', True)]:
        spec = board(rules)
        leaders(spec, rules)
        if is_leader:
            spec['units'] = [row for row in spec['units'] if row['id'] != 'leader']
        put(spec, rules, 'wounded', 'Lieutenant' if is_leader else 'Spearman', 1, 7, 4,
            hp=10, moves=5, attacks=0, leader=is_leader)
        if is_leader:
            tile(spec, 7, 4, 'Kh')
        tile(spec, 3, 4, 'Gg^Vh')
        put(spec, rules, 'threat', 'Orcish Grunt', 2, 11, 4)
        result.append(dict(name=name, theme=name, spec=spec, actor='wounded',
            goal='Move the wounded actor to a healing village outside public next-turn attack reach.'))

    spec = board(rules)
    leaders(spec, rules)
    put(spec, rules, 'scout', 'Elvish Scout', 1, 4, 4, moves=9, attacks=0)
    tile(spec, 8, 4, 'Gg^Vh')
    result.append(dict(name='village_timing', theme='village_timing', spec=spec, actor='scout',
        goal='Capture the empty unowned village this turn without entering public attack reach.'))

    spec = board(rules, width=15)
    leaders(spec, rules, enemy=(14, 8))
    put(spec, rules, 'slower', 'Elvish Shaman', 1, 7, 4)
    put(spec, rules, 'striker', 'Elvish Fighter', 1, 8, 3)
    put(spec, rules, 'target', 'Troll', 2, 8, 4)
    result.append(dict(name='slow_first', theme='attack_order', spec=spec, actor='slower',
        goal='Expose a slowing attack before the melee striker; compare retaliation conditional on slow landing.'))
    slowed = copy.deepcopy(spec)
    next(row for row in slowed['units'] if row['id'] == 'target')['status'] = ['slowed']
    result.append(dict(name='slow_landed', theme='attack_order', spec=slowed, actor='striker',
        goal='Paired visible state conditional on the target already being slowed.'))

    spec = board(rules, width=15)
    leaders(spec, rules, enemy=(14, 8))
    put(spec, rules, 'lawful', 'Spearman', 1, 7, 4)
    put(spec, rules, 'chaotic', 'Orcish Grunt', 2, 8, 4)
    for turn, name in [(5, 'wait_at_night'), (2, 'wait_at_day')]:
        result.append(dict(name=name, theme='day_night_wait', spec=copy.deepcopy(spec), turn=turn,
            actor='lawful', goal='End turn remains available; compare public combat forecasts at day versus night.'))

    # Hidden-information differential control for the movement theme.
    spec = board(rules, width=30, fog=True)
    leaders(spec, rules, enemy=(29, 8))
    put(spec, rules, 'scout', 'Elvish Scout', 1, 4, 4, moves=9, attacks=0)
    result.append(dict(name='hidden_control', theme='retreat', spec=spec,
        goal='Candidate enumeration must not change when only unseen terrain and an unseen unit change.'))
    hidden = copy.deepcopy(spec)
    put(hidden, rules, 'unseen-extra', 'Troll', 2, 29, 6)
    tile(hidden, 28, 6, 'Mm')
    result.append(dict(name='hidden_changed', theme='retreat', spec=hidden,
        goal='Paired hidden-information differential control.'))
    return result
