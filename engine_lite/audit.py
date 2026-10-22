"""Read-only, per-declaration audit of a frozen native rules capture.

The report records preserved WML and known implementation gaps. It never
changes coverage or substitutes an inventory check for native acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy

from .freeze import ABILITIES, SPECIALS, _validate_raw_wml, canonical, write


DISPLAY_ATTRIBUTES = {
    'name', 'female_name', 'description', 'special_note', 'name_inactive',
    'female_name_inactive', 'description_inactive', 'halo_image',
}
GLOBAL_GAPS = [
    'native compound combat modifier rounding and declaration filters need differential acceptance',
    'random trait generation and trait preservation across advancement are not implemented',
    'advancement choice and AMLA execution are not implemented',
    'separate vision_costs and jamming are not implemented',
    'runtime unit variations are not implemented',
]


def children(cfg):
    """Read the exporter's JSON object form and legacy JSON array form."""
    if isinstance(cfg, dict):
        pairs = [cfg[key] for key in sorted(
            (key for key in cfg if str(key).isdecimal()), key=lambda key: int(key))]
    else:
        pairs = cfg if isinstance(cfg, list) else []
    for pair in pairs:
        if isinstance(pair, dict):
            tag, value = pair.get('1'), pair.get('2')
        elif isinstance(pair, list) and len(pair) == 2:
            tag, value = pair
        else:
            raise ValueError('raw WML child is not a tag/config pair')
        if value == []:
            value = {}
        if not isinstance(tag, str) or not isinstance(value, dict):
            raise ValueError('raw WML child has no tag/config')
        yield tag, value


def semantic(cfg):
    """Keep all rule attributes/filters, leaving presentation out of groups."""
    if isinstance(cfg, dict):
        return {key: semantic(value) for key, value in cfg.items()
                if key not in DISPLAY_ATTRIBUTES}
    if isinstance(cfg, list):
        return [semantic(value) for value in cfg]
    return cfg


def declaration(tag, cfg, path):
    definition = semantic(cfg)
    return dict(tag=tag, id=cfg.get('id', tag), path=path,
                definition=definition,
                semantic_sha256=hashlib.sha256(canonical([tag, definition])).hexdigest())


def inspect_definition(cfg):
    result = dict(abilities=[], weapon_specials=[], events=[], traits=[], advancements=[],
                  cost_overrides=[])

    def visit(node, path):
        for index, (tag, value) in enumerate(children(node), 1):
            here = f'{path}/{tag}[{index}]'
            if tag in ('event', 'lua', 'command'):
                result['events'].append(dict(tag=tag, path=here))
            if tag == 'abilities':
                for ability, params in children(value):
                    result['abilities'].append(declaration(ability, params, here))
            elif tag == 'specials':
                for special, params in children(value):
                    result['weapon_specials'].append(declaration(special, params, here))
            elif tag == 'trait':
                result['traits'].append(declaration(tag, value, here))
            elif tag == 'advancement':
                result['advancements'].append(declaration(tag, value, here))
            elif tag in ('vision_costs', 'jamming_costs'):
                result['cost_overrides'].append(dict(tag=tag, definition=semantic(value), path=here))
            visit(value, here)

    visit(cfg, 'unit_type')
    return result


def implementation_reasons(unit, coverage):
    """Check compiled declarations, not abilities nested inside AMLA/event WML."""
    reasons = set(unit.get('unsupported', []))
    reasons.update(f'ability:{name}' for name in unit.get('abilities', [])
                   if name not in ABILITIES)
    for weapon in unit.get('weapons', []):
        reasons.update(f'weapon:{weapon["id"]}:{name}'
                       for name in weapon.get('specials', []) if name not in SPECIALS)
        if 'plague' in weapon.get('specials', []) and not weapon.get('plague_type'):
            reasons.add(f'weapon:{weapon["id"]}:plague_without_type')
    if coverage is None:
        reasons.add('missing_coverage_entry')
    elif coverage.get('status') == 'unsupported_script':
        reasons.update(coverage.get('reasons') or ['unsupported_without_reason'])
    elif coverage.get('status') not in ('exact', 'approximate'):
        reasons.add(f'unknown_coverage_status:{coverage.get("status")}')
    return sorted(reasons)


def training_closure(rules, coverage, profile=None):
    """Audit the actual training leaders/recruits and all reachable unit types.

    Implementation completeness does not imply native semantic acceptance.
    Unknown declarations and references remain blockers even if an input coverage
    row incorrectly calls them approximate.
    """
    profile_path = Path(__file__).resolve().parents[1] / 'vendor/arena/params.py'
    if profile is None:
        profile = runpy.run_path(str(profile_path))
    factions, leaders, recruits = (profile[key] for key in ('FACTIONS', 'LEADERS', 'RECRUITS'))
    if not len(factions) == len(leaders) == len(recruits):
        raise ValueError('training factions, leaders and recruits must have equal lengths')
    units = rules['units']

    def walk(seeds):
        pending = list(seeds)
        reached, missing, references = set(), set(), set()
        while pending:
            unit_id = pending.pop()
            if unit_id in reached or unit_id in missing:
                continue
            if unit_id not in units:
                missing.add(unit_id)
                continue
            reached.add(unit_id)
            unit = units[unit_id]
            targets = [('advancement', target) for target in unit.get('advances_to', [])]
            targets += [('plague', weapon['plague_type']) for weapon in unit.get('weapons', [])
                        if weapon.get('plague_type')]
            for kind, target in targets:
                references.add((unit_id, kind, target))
                pending.append(target)
        unsupported = {unit_id: reasons for unit_id in sorted(reached)
                       if (reasons := implementation_reasons(units[unit_id], coverage.get(unit_id)))}
        return dict(unit_count=len(reached), unit_ids=sorted(reached),
                    missing_unit_ids=sorted(missing), unsupported_unit_ids=sorted(unsupported),
                    unsupported_reasons=unsupported,
                    unsupported_reason_counts=dict(Counter(
                        reason for reasons in unsupported.values() for reason in reasons)),
                    references=[dict(source=source, kind=kind, target=target)
                                for source, kind, target in sorted(references)],
                    implementation_complete=not missing and not unsupported)

    per_faction, all_seeds = {}, set()
    for faction, leader, recruit in zip(factions, leaders, recruits):
        recruit_ids = [unit_id.strip() for unit_id in recruit.split(',') if unit_id.strip()]
        seeds = {leader, *recruit_ids}
        all_seeds.update(seeds)
        per_faction[faction] = dict(leader=leader, recruits=recruit_ids, **walk(seeds))
    return dict(profile='vendor/arena/params.py',
                scope='leaders/recruits -> advancement/plague transitive closure',
                factions=per_faction, **walk(all_seeds))


def audit_catalog(directory):
    directory = Path(directory)
    catalog = json.loads((directory / 'catalog.json').read_text(encoding='utf-8'))
    rules_bytes = (directory / 'rules.json').read_bytes()
    rules = json.loads(rules_bytes)
    coverage = json.loads((directory / 'coverage.json').read_text(encoding='utf-8'))
    report = dict(schema=1, rules_directory=str(directory),
                  rules_sha256=hashlib.sha256(rules_bytes).hexdigest(),
                  rules_version=rules['rules_version'], source_hash=rules['source_hash'],
                  status='native_semantics_pending',
                  coverage_counts=dict(Counter(value['status'] for value in coverage.values())),
                  semantic_acceptance=dict(
                      complete=bool(catalog.get('complete')),
                      native_accepted=bool(catalog.get('native_accepted')),
                      performance_accepted=bool(catalog.get('performance_accepted')),
                      note='Implementation coverage does not establish native equivalence; '
                           'differential reports are separate evidence and do not promote units to exact.'),
                  global_implementation_gaps=GLOBAL_GAPS,
                  capture_integrity_errors=[], scopes={}, units={})
    if report['rules_sha256'] != catalog['rules_file_sha256']:
        raise ValueError('rules.json differs from its frozen catalog hash')
    for source in catalog['captures']:
        path = directory / 'captures' / (source['sha256'] + '.json')
        raw_bytes = path.read_bytes()
        if hashlib.sha256(raw_bytes).hexdigest() != source['sha256']:
            raise ValueError(f'{path}: capture differs from its frozen hash')
        capture = json.loads(raw_bytes)
        inventory = set(capture['units'])
        report['scopes'][capture['scope']] = dict(unit_count=len(inventory), unit_ids=sorted(inventory))
        try:
            for field in ('raw_definitions', 'variations'):
                _validate_raw_wml(capture.get(field, {}), f'{capture["scope"]}:{field}')
        except ValueError as error:
            report['capture_integrity_errors'].append(str(error))
            continue
        for unit_id, compact in capture['units'].items():
            if unit_id not in rules['units']:
                raise ValueError(f'{capture["scope"]}:{unit_id}: captured unit absent from frozen rules')
            raw_id = unit_id if unit_id in capture['raw_definitions'] else compact.get('native_id', unit_id)
            if raw_id not in capture['raw_definitions']:
                raise ValueError(f'{capture["scope"]}:{unit_id}: no raw native definition')
            raw = capture['raw_definitions'][raw_id]
            definition = inspect_definition(raw)
            variants = capture.get('variations', {}).get(raw_id, {})
            gameplay_variants = sorted(name for name in variants if name not in ('male', 'female'))
            gaps = []
            if definition['events']:
                gaps.append('scripted_type_event')
            if definition['advancements']:
                gaps.append('amla_execution_unimplemented')
            if gameplay_variants:
                gaps.append('runtime_unit_variations_unimplemented')
            gaps.extend(f'{item["tag"]}_unimplemented' for item in definition['cost_overrides'])
            row = report['units'].setdefault(unit_id, dict(
                native_id=compact.get('native_id', raw.get('id', unit_id)), scopes=[],
                coverage_status=coverage[unit_id]['status'],
                coverage_reasons=coverage[unit_id]['reasons'],
                abilities=definition['abilities'], weapon_specials=definition['weapon_specials'],
                traits=definition['traits'], advancements=definition['advancements'],
                events=definition['events'], gameplay_variants=gameplay_variants,
                definition_gaps=sorted(set(gaps)),
                compiled_healing={key: compact[key] for key in ('healing_amount', 'healing_poison')
                                  if key in compact}))
            row['scopes'].append(capture['scope'])
    core_ids = set(report['scopes'].get('core', {}).get('unit_ids', []))
    implementation = {}
    for unit_id, unit in rules['units'].items():
        reasons = implementation_reasons(unit, coverage.get(unit_id))
        events = [reason for reason in reasons if reason == 'scripted_type_event']
        declarations = [reason for reason in reasons if reason != 'scripted_type_event']
        status = ('unsupported_declarations_and_events' if declarations and events else
                  'unsupported_declarations' if declarations else
                  'event_dependent' if events else 'implemented_pending_native_acceptance')
        implementation[unit_id] = status
        if unit_id in report['units']:
            report['units'][unit_id].update(
                implementation_status=status, unsupported_declarations=declarations,
                event_dependencies=events,
                compiled_abilities=unit.get('abilities', []),
                compiled_weapon_specials=[dict(id=weapon['id'], specials=weapon.get('specials', []))
                                          for weapon in unit.get('weapons', [])],
                unverified_rule_reasons=coverage.get(unit_id, {}).get('reasons', [])
                    if coverage.get(unit_id, {}).get('status') != 'exact' else [])
    report['implementation_counts'] = dict(Counter(implementation.values()))
    report['core_coverage'] = dict(
        unit_count=len(core_ids),
        coverage_counts=dict(Counter(coverage[unit_id]['status'] for unit_id in core_ids)),
        implementation_counts=dict(Counter(implementation[unit_id] for unit_id in core_ids)),
        unsupported_units={unit_id: implementation_reasons(rules['units'][unit_id], coverage.get(unit_id))
                           for unit_id in sorted(core_ids)
                           if implementation[unit_id] != 'implemented_pending_native_acceptance'})
    report['training_closure'] = training_closure(rules, coverage)
    for scope, inventory in report['scopes'].items():
        ids = set(inventory.pop('unit_ids'))
        inventory['extra_unit_ids_from_core'] = sorted(ids - core_ids)
        inventory['identical_ids_to_core'] = scope != 'core' and ids == core_ids
    report['unit_count'] = len(rules['units'])
    report['audited_unit_count'] = len(report['units'])
    report['unaudited_unit_ids'] = sorted(set(rules['units']) - set(report['units']))
    report['definition_gap_counts'] = dict(Counter(
        reason for row in report['units'].values() for reason in row['definition_gaps']))
    report['unsupported_reason_counts'] = dict(Counter(
        reason for row in coverage.values() if row['status'] == 'unsupported_script'
        for reason in row['reasons']))
    groups = Counter()
    for row in report['units'].values():
        for item in row['abilities'] + row['weapon_specials']:
            groups[(item['tag'], item['id'], item['semantic_sha256'])] += 1
    report['declaration_groups'] = [dict(tag=tag, id=identifier, semantic_sha256=digest,
                                      unit_declaration_count=count)
                                  for (tag, identifier, digest), count in sorted(groups.items())]
    if report['capture_integrity_errors'] or report['unaudited_unit_ids']:
        report['status'] = 'blocked_incomplete_raw_evidence'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rules-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = audit_catalog(args.rules_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write(args.output, report)
    print(json.dumps({key: report[key] for key in
                      ('status', 'unit_count', 'audited_unit_count', 'coverage_counts',
                       'definition_gap_counts')}, indent=2))


if __name__ == '__main__':
    main()
