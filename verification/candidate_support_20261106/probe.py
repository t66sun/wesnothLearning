"""Frozen public-state candidate audit: no collection, training, or teacher query."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import time

import torch

from learning.export import load_model
from learning.features import ACTION
from learning.lite_host import host_modules
from learning.model import batch
from learning.ppo import _digest
from fixtures import cases

HERE = Path(__file__).resolve().parent
FIELDS = ('kind', 'x', 'y', 'tx', 'ty', 'ex', 'ey', 'type', 'weapon', 'full')
FEATURE = {name: index for index, (name, _) in enumerate(ACTION)}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def intent(action):
    return {key: action[key] for key in FIELDS if key in action}


def key(action):
    return encode(intent(action))


def policy_input(row):
    # Deliberate allowlist: referee labels and audit goal/properties never reach
    # the network. Synthetic states have an explicitly empty prior history.
    return {name: copy.deepcopy(row[name]) for name in ('global', 'opponents', 'spatial', 'candidates', 'turn')}


def engine(rules, case, mode=None):
    from _engine_lite import LiteEngine
    instance = LiteEngine(encode(rules), encode(case['spec']))
    if case.get('turn', 1) != 1:
        # Construct a declared synthetic turn; this snapshot remains in the
        # referee fixture builder and is never an observation or network input.
        state = json.loads(instance.snapshot())
        state['game']['turn'] = case['turn']
        instance.restore(encode(state))
    modules = host_modules()
    if mode:
        source = modules['candidates.lua']
        position = source.rindex('return M')
        extension = (HERE / 'audit.lua').read_text().replace('@MODE@', mode)
        modules['candidates.lua'] = source[:position] + extension + '\n' + source[position:]
    instance.configure_host(encode(modules))
    return instance


def decision(instance):
    return json.loads(instance.decision(1, False, True))


def atom(action, width, units):
    kind = action['kind']
    if kind == 'end_turn':
        return ('end_turn',)
    if kind == 'recruit':
        return ('recruit', action['type'], (action['y'] - 1) * width + action['x'] - 1)
    actor = units[(action['x'], action['y'])]['id']
    if kind == 'move':
        return ('move', actor, (action['ty'] - 1) * width + action['tx'] - 1)
    if kind == 'attack':
        return ('attack', actor, units[(action['tx'], action['ty'])]['id'], action['weapon'] - 1)
    raise AssertionError('fixture unexpectedly requires composite move-attack legality')


def legal_atoms(instance):
    result = set()
    for action in json.loads(instance.legal_actions(1)):
        kind = action['kind']
        result.add((kind,) if kind == 'end_turn' else
                   (kind, action['unit_type'], action['to']) if kind == 'recruit' else
                   (kind, action['unit'], action['to']) if kind == 'move' else
                   (kind, action['unit'], action['target'], action['weapon']))
    return result


def useful(case, row):
    chosen = []
    for index, (action, properties) in enumerate(zip(row['candidates'], row['timing']['audit']['properties'])):
        actor = (action.get('actor') or {}).get('id')
        name = case['name']
        if name == 'recruit_positions':
            good = action['kind'] == 'recruit' and properties['outside_attack_reach']
        elif name == 'combat_slots':
            good = action['kind'] == 'attack' and actor == case['actor'] and action['weapon'] == 2
        elif name in ('retreat', 'leader_safety', 'village_timing'):
            good = (action['kind'] == 'move' and actor == case['actor'] and properties['village']
                    and properties['outside_attack_reach'] and properties.get('owner') != 1)
        elif name.startswith('wait_at_'):
            good = action['kind'] == 'end_turn'
        elif name == 'slow_first':
            good = action['kind'] == 'attack' and actor == 'slower' and action['weapon'] == 2
        elif name == 'slow_landed':
            good = action['kind'] == 'attack' and actor == 'striker' and action['weapon'] == 1
        else:
            good = False
        if good:
            chosen.append(index)
    return chosen


def pairs(row, indices, rules, gold):
    rows = [row['candidates'][index] for index in indices]
    return [(intent(a), intent(b)) for a in rows for b in rows
            if a['type'] == 'Spearman' and b['type'] == 'Mage'
            and (a['x'], a['y']) != (b['x'], b['y'])
            and rules['units'][a['type']]['cost'] + rules['units'][b['type']]['cost'] <= gold]


def make_panel(rules):
    panel = {}
    for case in cases(rules):
        print('fixture', case['name'], flush=True)
        plain = engine(rules, case)
        before = json.loads(plain.snapshot())['game']
        production = decision(plain)
        view = json.loads(plain.observe(1))
        units = {(u['pos'] % case['spec']['width'] + 1, u['pos'] // case['spec']['width'] + 1): u
                 for u in view['units']}
        legal = legal_atoms(plain)
        assert json.loads(plain.snapshot())['game'] == before
        modes = {}
        for mode in ('A', 'B', 'C'):
            instance = engine(rules, case, mode)
            before = json.loads(instance.snapshot())['game']
            row = decision(instance)
            assert json.loads(instance.snapshot())['game'] == before
            assert row['candidates'][0]['kind'] == 'end_turn'
            assert len({key(a) for a in row['candidates']}) == len(row['candidates'])
            atoms = {atom(a, case['spec']['width'], units) for a in row['candidates']}
            assert atoms <= legal, (case['name'], mode, atoms - legal)
            if mode == 'C':
                assert atoms == legal, (case['name'], legal - atoms)
            modes[mode] = row
        assert policy_input(modes['A']) == policy_input(production), case['name']
        assert len(production['candidates']) <= 37
        assert production['timing']['work'] <= 12000
        for left, right in [('A', 'B'), ('B', 'C')]:
            left_actions = {key(a): a for a in modes[left]['candidates']}
            right_actions = {key(a): a for a in modes[right]['candidates']}
            assert left_actions.keys() <= right_actions.keys()
            assert all(a == right_actions[k] for k, a in left_actions.items())
        panel[case['name']] = dict(case=case, production=production, modes=modes, legal=len(legal))
    return panel


def verify_panel(panel, rules):
    findings = {}
    for name, entry in panel.items():
        case, modes = entry['case'], entry['modes']
        selected = {mode: useful(case, row) for mode, row in modes.items()}
        findings[name] = dict(theme=case['theme'], goal=case['goal'], legal_atoms=entry['legal'],
            count={mode: len(row['candidates']) for mode, row in modes.items()},
            useful_count={mode: len(indices) for mode, indices in selected.items()},
            support={mode: [intent(a) for a in row['candidates']] for mode, row in modes.items()},
            useful={mode: [intent(modes[mode]['candidates'][index]) for index in indices]
                    for mode, indices in selected.items()},
            production_timing=entry['production']['timing'],
            diagnostic_calls={mode: row['timing']['audit']['calls'] for mode, row in modes.items()})
    combat = panel['combat_slots']
    assert not useful(combat['case'], combat['modes']['A'])
    assert len(useful(combat['case'], combat['modes']['B'])) == 1
    expanded = combat['modes']['B']['candidates']
    bow = next(a for a in expanded if (a.get('actor') or {}).get('id') == 'archer-04' and a.get('weapon') == 2)
    melee = next(a for a in combat['modes']['A']['candidates'] if (a.get('actor') or {}).get('id') == 'archer-04')
    metric = lambda a: dict(kill_probability=a['features'][16], self_death_probability=a['features'][17],
                            expected_self_damage=a['features'][15] * 50, expected_target_damage=a['features'][14] * 50)
    assert bow['features'][16] > melee['features'][16]
    assert bow['features'][17] <= melee['features'][17]
    assert bow['features'][15] < melee['features'][15]
    findings['combat_slots']['witness'] = dict(omitted=intent(bow), retained=intent(melee),
                                               omitted_forecast=metric(bow), retained_forecast=metric(melee))
    # This is immediate support, not a claim that the action is permanently lost.
    replay = engine(rules, combat['case'])
    progression = []
    for _ in range(3):
        row = decision(replay)
        present = any(key(a) == key(bow) for a in row['candidates'])
        progression.append(present)
        if present:
            break
        action = next(a for a in row['candidates'] if a['kind'] == 'attack' and a['actor']['id'] != 'archer-04')
        replay.execute_candidate(encode(action))
    assert progression[-1]
    findings['combat_slots']['retained_after_other_attacks'] = progression

    recruitment = panel['recruit_positions']
    valid_pairs = {mode: pairs(row, useful(recruitment['case'], row), rules,
                               recruitment['case']['spec']['sides'][0]['gold'])
                   for mode, row in recruitment['modes'].items()}
    assert len(valid_pairs['C']) > len(valid_pairs['B'])
    retained_pairs = {encode(pair) for pair in valid_pairs['B']}
    witness = next(pair for pair in valid_pairs['C'] if encode(pair) not in retained_pairs)
    replay = engine(rules, recruitment['case'])
    decision(replay)
    for action in witness:
        replay.execute_candidate(encode(action))
    view = json.loads(replay.observe(1))
    assert view['sides'][0]['gold'] == 0
    findings['recruit_positions'].update(safe_role_pairs={mode: len(value) for mode, value in valid_pairs.items()},
                                         witness_pair=witness, witness_pair_executed=True)

    for name in ('retreat', 'leader_safety', 'village_timing', 'slow_first', 'wait_at_night', 'wait_at_day'):
        assert findings[name]['useful_count']['A'] > 0, (name, 'local goal unexpectedly absent')
    strike = lambda name: next(a for a in panel[name]['modes']['A']['candidates']
                               if (a.get('actor') or {}).get('id') == 'striker' and a.get('weapon') == 1)
    normal, slowed = metric(strike('slow_first')), metric(strike('slow_landed'))
    assert slowed['expected_self_damage'] < normal['expected_self_damage']
    findings['slow_first']['conditional_striker_forecast'] = dict(normal=normal, target_slowed=slowed)
    attack = lambda name: next(a for a in panel[name]['modes']['A']['candidates']
                               if (a.get('actor') or {}).get('id') == 'lawful' and a.get('weapon') == 1)
    night, day = metric(attack('wait_at_night')), metric(attack('wait_at_day'))
    assert day['expected_target_damage'] > night['expected_target_damage']
    findings['wait_at_night']['paired_forecast'] = dict(night=night, day=day)
    for mode in ('A', 'B', 'C'):
        assert policy_input(panel['hidden_control']['modes'][mode]) == policy_input(panel['hidden_changed']['modes'][mode])
    return findings


def timed(call, repetitions):
    call()  # Warm model or bridge; individual observations remain in the output.
    values = []
    for _ in range(repetitions):
        wall, cpu = time.perf_counter(), time.process_time()
        call()
        values.append(dict(wall_seconds=time.perf_counter() - wall, cpu_seconds=time.process_time() - cpu))
    return dict(repetitions=values, wall_mean=statistics.mean(v['wall_seconds'] for v in values),
                cpu_mean=statistics.mean(v['cpu_seconds'] for v in values))


def measure(panel, rules, run, repetitions):
    models = {}
    for label, path in [('bc', run / 'duel/last_bc.pt'), ('latest', run / 'duel/last_ppo.pt')]:
        model, state = load_model(path, 'duel')
        model.eval()
        models[label] = (model, dict(path=str(path), file_sha256=file_hash(path), parameters_sha256=_digest(model),
                                   version=state.get('runner', {}).get('version')))
    result = dict(models={label: identity for label, (_, identity) in models.items()}, cases={})
    with torch.inference_mode():
        for name, entry in panel.items():
            if name in ('hidden_changed', 'slow_landed', 'wait_at_day'):
                continue
            case = entry['case']
            case_result = dict(generation={}, inference={}, rankings={})
            for mode in (None, 'A', 'B', 'C'):
                instance = engine(rules, case, mode)
                case_result['generation'][mode or 'production'] = timed(lambda: decision(instance), repetitions)
            for label, (model, identity) in models.items():
                case_result['inference'][label] = {}
                for mode, row in entry['modes'].items():
                    inputs = policy_input(row)
                    tensors = batch([inputs])
                    case_result['inference'][label][mode] = dict(
                        pack=timed(lambda: batch([inputs]), repetitions),
                        forward=timed(lambda: model(*tensors), repetitions))
                    if mode == 'A':
                        logits, _ = model(*tensors)
                        assert torch.isfinite(logits).all()
                        order = sorted(range(len(row['candidates'])), key=lambda index: (-float(logits[0, index]), index))
                        goals = useful(case, row)
                        case_result['rankings'][label] = dict(top=intent(row['candidates'][order[0]]),
                            goal_available=bool(goals), top_meets_local_goal=order[0] in goals,
                            best_goal_rank=min((order.index(index) + 1 for index in goals), default=None),
                            top_five=[intent(row['candidates'][index]) for index in order[:5]])
                assert _digest(model) == identity['parameters_sha256']
            result['cases'][name] = case_result
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--rules', type=Path, default=Path(os.environ['WESNOTH_RULES_DIR']) / 'rules.json')
    parser.add_argument('--run', type=Path)
    parser.add_argument('--repetitions', type=int, default=5)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be new')
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    rules = json.loads(args.rules.read_text())
    panel = make_panel(rules)
    findings = verify_panel(panel, rules)
    result = dict(host=platform.node(), python=platform.python_version(), torch=torch.__version__,
        rules_sha256=file_hash(args.rules), fixtures=cases(rules), fixtures_sha256=digest(cases(rules)),
        findings=findings, checks='A equals production; A subset B subset C; C equals public legal atoms; '
            'no game/RNG mutation; exact retained action features; hidden-state invariance; local witnesses verified')
    if args.run:
        result['measurements'] = measure(panel, rules, args.run, args.repetitions)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    for name, finding in findings.items():
        print(name, finding['count'], finding['useful_count'], flush=True)


if __name__ == '__main__':
    main()
