"""Small legal public-state pairs; no match runner, policy optimizer or corpus."""
import copy
import json

from tests.v5 import helpers as H


def rules():
    value = H.rules()
    for terrain, keep in (('Ch', False), ('Kh', True)):
        value['terrains'][terrain] = dict(id=terrain, castle=True, keep=keep, village=False, healing=0)
        for unit in value['units'].values():
            unit['movement'][terrain] = 1
            unit['defense'][terrain] = 40
    value['units']['Ghost']['movement']['Ww'] = 1
    return value


def put(spec, x, y, terrain):
    spec['terrain'][(y-1)*spec['width']+x-1] = terrain


def unit(identifier, unit_type, side, x, y, width, *, leader=False, moves=0):
    row = H._unit(identifier, unit_type, side, x-1, y-1, width=width, leader=leader)
    row.update(moves=moves, attacks_left=0)
    return row


def board(width=32, height=16, *, own=(3, 8), enemy=(30, 8), fog=False, shroud=False):
    units = [unit('own', 'Fighter', 1, *own, width, leader=True),
             unit('enemy', 'Fighter', 2, *enemy, width, leader=True)]
    spec = H.spec(width=width, height=height, units=units, terrain=['Gg']*(width*height),
                  fog=fog, shroud=shroud, max_turns=60)
    spec['sides'][0]['recruit'] = ['Fighter', 'Ghost']
    x, y = own
    put(spec, x, y, 'Kh')
    for cx, cy in ((x+1, y), (x, y-1), (x, y+1)):
        put(spec, cx, cy, 'Ch')
    return spec


def capture(spec):
    engine = H.engine(game_spec=spec, rules_data=rules())
    return engine, H.decision(engine, 1)


def pairs():
    open_gate = board()
    for y in range(1, 17):
        put(open_gate, 20, y, 'Ww')
    put(open_gate, 19, 8, 'Ww')
    put(open_gate, 20, 8, 'Gg')
    shut_gate = copy.deepcopy(open_gate)
    put(shut_gate, 19, 8, 'Gg')
    put(shut_gate, 20, 8, 'Ww')
    pooled_a = board(16, own=(2, 5), enemy=(15, 5))
    pooled_b = copy.deepcopy(pooled_a)
    put(pooled_a, 8, 5, 'Hh')
    put(pooled_b, 8, 11, 'Hh')
    local_a = board()
    local_b = copy.deepcopy(local_a)
    put(local_a, 5, 8, 'Hh')
    put(local_b, 6, 8, 'Hh')
    entity_a = board(enemy=(25, 8))
    entity_b = board(enemy=(26, 8))
    hidden_a = copy.deepcopy(open_gate)
    hidden_b = copy.deepcopy(shut_gate)
    for spec in (hidden_a, hidden_b):
        for side in spec['sides']:
            side.update(fog=True, shroud=True)
    known = board(fog=True, shroud=False)
    unknown = board(fog=True, shroud=True)
    return dict(resampling_connectivity=(open_gate, shut_gate),
                pooling_location=(pooled_a, pooled_b),
                local_patch_compensation=(local_a, local_b),
                entity_compensation=(entity_a, entity_b),
                hidden_truth_control=(hidden_a, hidden_b),
                knowledge_mask_compensation=(known, unknown))


def actor_row(decision):
    return {key: copy.deepcopy(decision[key]) for key in
            ('global', 'opponents', 'spatial', 'candidates', 'turn')}


def public_spec(spec):
    """All tiles are public in the main pairs; shroud controls remain marked."""
    width = spec['width']
    return dict(width=width, height=spec['height'], sides=spec['sides'], units=spec['units'],
                terrain_rows=[spec['terrain'][i:i+width] for i in range(0, len(spec['terrain']), width)])


def within_turn_traces():
    """Same first write and final scene; only independent own-move order differs."""
    spec = board()
    spec['sides'][0]['gold'] = 0
    spec['units'].extend(unit(name, 'Archer', 1, 5, y, 32, moves=5)
                         for name, y in (('one', 5), ('two', 7), ('first', 10)))
    traces = []
    for order in ((10, 5, 7), (10, 7, 5)):
        engine, _ = capture(spec)
        rows = []
        for index, y in enumerate(order):
            decision = H.decision(engine, 1)
            action = dict(kind='move', x=5, y=y, tx=6, ty=y, full=True)
            outcome = json.loads(engine.execute_candidate(json.dumps(action)))
            assert outcome['committed'], outcome
            row = actor_row(decision)
            row.update(format='duel', source='policy', engine_id='lite', game_id='history-order',
                       game_family='history-order', side=1, decision=index, choice=-1, committed=True,
                       memory_write=outcome['memory_write'])
            rows.append(row)
        final = actor_row(H.decision(engine, 1))
        final.update(format='duel', source='policy', engine_id='lite', game_id='history-order',
                     game_family='history-order', side=1, decision=3, choice=0, committed=False)
        rows.append(final)
        traces.append(rows)
    return public_spec(spec), traces


def last_seen_pair():
    """Same current legal view, different previously observed enemy locations."""
    from tests.test_lua_contracts import initialize
    rows = []
    for x in (6, 7):
        lua, modules = initialize()
        lua.globals().previous_x = x
        lua.execute('''
            observed_enemy=fixture.visible[3]
            observed_enemy.x=previous_x; observed_enemy.y=4
            fixture.visible={fixture.own[1],fixture.own[2],observed_enemy}
            wesnoth.map.find=function() return {} end
            memory={}
        ''')
        modules['observation.lua'].capture(lua.globals().memory, 1)
        lua.execute('''
            fixture.visible={fixture.own[1],fixture.own[2]}
            fixture.fog['6,4']=true; fixture.fog['7,4']=true
            wesnoth.current.turn=2
        ''')
        obs = modules['observation.lua'].capture(lua.globals().memory, 1)
        modules['spatial.lua'].actions(obs, lua.table())
        def plain(value):
            if hasattr(value, 'items'):
                items = dict(value.items())
                if items and all(isinstance(key, int) for key in items):
                    return [plain(items[key]) for key in sorted(items)]
                return {key: plain(val) for key, val in items.items()}
            return value
        row = {key: plain(obs[key]) for key in ('global', 'opponents', 'spatial')}
        row.update(turn=2, candidates=[])
        rows.append(row)
    return rows
