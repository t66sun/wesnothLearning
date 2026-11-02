"""Fixed legal-board teacher queries; no collection, training or full games."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time

from _engine_lite import LiteEngine
from engine_lite.differential import game_spec, unit
from learning.lite_host import host_modules, teacher_candidate
from learning.native_transport import NativeTransport
from learning.teachers import identity


CASES = {
    'lethal_target': ('Elvish Fighter', 'Orcish Grunt', 'defender', 1),
    'survive_retaliation': ('Elvish Fighter', 'Orcish Grunt', 'alternative', 1),
    'magical_weapon': ('Mage', 'Elvish Fighter', 'defender', 2),
    'poison_weapon': ('Orcish Assassin', 'Elvish Fighter', 'defender', 2),
    'slow_weapon': ('Elvish Shaman', 'Orcish Grunt', 'defender', 2),
    'poison_immunity': ('Orcish Assassin', 'Elvish Fighter', 'alternative', 2),
}


def board(rules, name, fmt):
    attacker, defender, _, _ = CASES[name]
    spec = game_spec(rules, attacker, defender)
    if fmt != 'duel':
        for side, pos in ((3, 42), (4, 6)):
            spec['sides'].append(dict(spec['sides'][1], id=side, team=str(side)))
            spec['units'].append(unit(rules, f'leader{side}', 'Orcish Warrior', side, pos, leader=True))
    for side in spec['sides']:
        side['gold'] = 0
        if fmt == 'team2v2':
            side['team'] = str((side['id'] - 1) % 2 + 1)
    if name in ('lethal_target', 'survive_retaliation', 'poison_immunity'):
        kind = 'Dark Adept' if name == 'survive_retaliation' else defender
        spec['units'].append(unit(rules, 'alternative', kind, 2, 16))
    if name == 'lethal_target':
        spec['units'][3]['hp'] = 1
    if name == 'survive_retaliation':
        spec['units'][2]['hp'] = 1
    if name == 'poison_immunity':
        spec['units'][3]['status'] = ['unpoisonable']
    for u in spec['units']:
        u['moves'] = 0
        if u['leader']:
            u['attacks_left'] = 0
    return spec


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def check_lite(rules, spec):
    engine = LiteEngine(json.dumps(rules), json.dumps(spec))
    engine.configure_host(json.dumps(host_modules()))
    student = json.loads(engine.decision(1, False))
    saved = engine.snapshot()
    decision = json.loads(engine.decision(1, True))
    assert json.loads(engine.snapshot())['game'] == json.loads(saved)['game']
    assert decision['candidates'] == student['candidates']
    engine.restore(saved)
    repeated = json.loads(engine.decision(1, True))
    assert repeated['teacher_action'] == decision['teacher_action']
    outcome = json.loads(engine.execute_candidate(json.dumps(teacher_candidate(decision['teacher_action']))))
    assert outcome['committed'], outcome
    return decision, outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rules', type=Path, required=True)
    parser.add_argument('--wesnoth', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', choices=CASES)
    parser.add_argument('--format', action='append', choices=('duel', 'ffa4', 'team2v2'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    raw = (args.rules / 'rules.json').read_bytes()
    rules = json.loads(raw)
    rows = []
    started = time.monotonic()
    with NativeTransport(wesnoth=args.wesnoth, timeout=30, startup_timeout=120) as native:
        for fmt in args.format or ('duel', 'ffa4', 'team2v2'):
            for name in args.case or CASES:
                spec = board(rules, name, fmt)
                row = dict(name=name, format=fmt, spec=spec)
                try:
                    lite, outcome = check_lite(rules, spec)
                    row.update(lite=lite, lite_outcome=outcome)
                    other_seed = copy.deepcopy(spec)
                    other_seed['seed'] = 714
                    repeated, _ = check_lite(rules, other_seed)
                    assert repeated['teacher_action'] == lite['teacher_action']
                    native.reset(spec)
                    student = native.decision(1)
                    before = native.observe(1)
                    decision = native.decision(1, teacher=True)
                    row['native'] = decision
                    assert not decision.get('teacher_skipped'), decision
                    assert native.observe(1) == before
                    assert decision['candidates'] == student['candidates']
                    plan = decision['teacher_action']
                    assert plan == lite['teacher_action'], (plan, lite['teacher_action'])
                    _, _, target, weapon = CASES[name]
                    assert (plan['kind'], plan['id'], plan['enemy'], plan['weapon']) == ('combat', 'attacker', target, weapon), plan
                    outcome = native.execute_candidate(teacher_candidate(plan))
                    row['native_outcome'] = outcome
                    assert outcome['committed'], outcome
                    row['status'] = 'PASS'
                except Exception as exc:
                    row.update(status='FAIL', error=repr(exc))
                write(args.output / f'{fmt}-{name}.json', row)
                rows.append(dict(name=name, format=fmt, status=row['status'], error=row.get('error')))
                print(fmt, name, row['status'], row.get('error', ''), flush=True)
        executable_hash = native.executable_hash
    write(args.output / 'summary.json', dict(
        source=args.source, rules_sha256=hashlib.sha256(raw).hexdigest(),
        native_executable_sha256=executable_hash, teacher=identity(),
        wall_seconds=time.monotonic()-started, cases=rows,
        limits='Fixed first-decision boards only; no strength or full-game claim.'))
    assert all(row['status'] == 'PASS' for row in rows), 'teacher board checks failed'


if __name__ == '__main__':
    main()
