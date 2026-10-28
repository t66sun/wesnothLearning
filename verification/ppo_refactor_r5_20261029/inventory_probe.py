"""Audit whether any existing input can serve as the R5 PPO rehearsal pool.

Reads only frozen inputs. Writes probe.json, exits nonzero when a claim fails.
"""
import ast
import glob
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('tmp/r5_audit')
OUT.mkdir(parents=True, exist_ok=True)


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def selected_games():
    return load_jsonl(ROOT / 'data/humanData_curated/games.jsonl')


def inventory():
    return load_jsonl(ROOT / 'data/humanData_curated/inventory.jsonl')


def import_report():
    return json.loads((ROOT / 'data/datasets/human/import.json').read_text(encoding='utf-8'))


def shards():
    return sorted(glob.glob(str(ROOT / 'data/datasets') + '/**/*.jsonl.gz', recursive=True))


def rehearsal_opt_in():
    """Return (definitions, call_sites) for allow_policy_rehearsal."""
    definitions, calls, runner_passes = [], [], []
    for path in sorted((ROOT / 'learning').glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and any(a.arg == 'allow_policy_rehearsal' for a in node.args.args):
                definitions.append(f'{path.name}:{node.name}:{node.lineno}')
            if isinstance(node, ast.Call) and any(k.arg == 'allow_policy_rehearsal' for k in node.keywords):
                calls.append(f'{path.name}:{node.lineno}')
            if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'train' and path.name == 'experiment.py':
                runner_passes.append(any(k.arg == 'allow_policy_rehearsal' for k in node.keywords))
    return definitions, calls, runner_passes


def main():
    games = selected_games()
    rows = inventory()
    report = import_report()
    standard = [g for g in games if g.get('category') == 'standard_multiplayer']
    versions = Counter(g.get('version') for g in standard)
    native_standard = [g for g in standard if g.get('version') == '1.18.8' and g.get('era') == 'era_default']
    compatible = [g for g in report['games'] if g.get('status') == 'compatible_pending_native_replay']
    definitions, calls, runner_passes = rehearsal_opt_in()
    facts = dict(
        curated_inventory_rows=len(rows),
        curated_versions={str(k): v for k, v in Counter(r.get('version') for r in rows).items()},
        selected_games=len(games),
        selected_standard_multiplayer=len(standard),
        selected_standard_versions={str(k): v for k, v in versions.items()},
        selected_native_standard_era_default=[g['game_id'] for g in native_standard],
        import_statuses=report['statuses'],
        import_samples=report['samples'],
        import_observer=report['observer_version'],
        compatible_games=[dict(game_id=g['game_id'], format=g['format'], split=g['split']) for g in compatible],
        compatible_versions={g['game_id']: next(x.get('version') for x in games if x['game_id'] == g['game_id'])
                             for g in compatible},
        dataset_shards=[Path(p).relative_to(ROOT).as_posix() for p in shards()],
        opt_in_definitions=definitions,
        opt_in_call_sites=calls,
        runner_passes_opt_in=runner_passes,
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'probe.json').write_text(json.dumps(facts, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(facts, indent=2, sort_keys=True))
    assert facts['selected_native_standard_era_default'] == [], 'a native-era-default human game exists'
    assert facts['dataset_shards'] == [], 'human row shards already exist'
    assert facts['import_samples'] == 0, 'human import produced samples'
    assert facts['compatible_versions'] == {'game_0040': '1.18.2', 'game_0042': '1.18.7'}, facts['compatible_versions']
    assert calls == ['train.py:20'], calls
    assert runner_passes == [False], runner_passes
    print('passed: no existing input can fill the R5 rehearsal pool')


main()
