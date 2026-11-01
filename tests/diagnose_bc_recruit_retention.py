"""One bounded recruit-exposure arm using the existing frozen learning curve.

Keep each baseline family's row quota; reserve up to one quarter for recruits,
then keep baseline non-recruit rows. No validation labels influence selection.
Run with the frozen v1 runtime on PYTHONPATH, like diagnose_recruit_ranking.py.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import sys
from unittest.mock import patch

from learning.data import _shard_identity
from learning.sequences import (_family_windows, _ordered_rows, _row_bytes,
                                GZ_BUDGET, RETAIN_BUDGET, sequence_key)
from tests import diagnose_bc_learning_curve as curve


def identity(row):
    return sequence_key(row) + (row['turn'], row.get('decision', row.get('action_index')))


def recruit(row):
    return row['candidates'][row['choice']]['kind'] == 'recruit'


def select(paths, rows, seed, format_name):
    families = defaultdict(list)
    for row in rows:
        families[row['game_family']].append(row)
    files = defaultdict(list)
    for name in paths:
        path = Path(name)
        stat = path.stat()
        key = _shard_identity(str(path), stat.st_size, stat.st_mtime_ns)
        if key is not None and key[2] == 'train' and key[3] in families:
            files[key[3]].append((path, stat))
    compressed = sum(stat.st_size for group in files.values() for _, stat in group)
    assert compressed <= GZ_BUDGET
    rng = random.Random(seed)
    selected = []
    report = []
    retained = 0
    for family, baseline in sorted(families.items()):
        windows, prefix = _family_windows(files[family], 'train', format_name, 8)
        available = [row for window in windows for row in window]
        original_ids = {identity(row) for row in baseline}
        assert len(original_ids) == len(baseline)
        assert original_ids <= {identity(row) for row in available}
        original_recruits = [row for row in baseline if recruit(row)]
        extras = [row for row in available if recruit(row) and identity(row) not in original_ids]
        rng.shuffle(extras)
        reserve = max(len(original_recruits), (len(baseline)+3)//4)
        chosen = original_recruits + extras[:reserve-len(original_recruits)]
        ordinary = [row for row in baseline if not recruit(row)]
        rng.shuffle(ordinary)
        chosen += ordinary[:len(baseline)-len(chosen)]
        assert len(chosen) == len(baseline)
        selected.append(chosen)
        retained += prefix + sum(_row_bytes(row) for row in chosen)
        report.append(dict(family=family, rows=len(chosen), before_recruits=len(original_recruits),
                           after_recruits=sum(map(recruit, chosen)), available_recruits=sum(map(recruit, available))))
    assert retained <= RETAIN_BUDGET
    result = _ordered_rows(selected)
    assert len(result) == len(rows)
    assert len({identity(row) for row in result}) == len(result)
    assert sum(map(recruit, result)) > sum(map(recruit, rows))
    kinds = lambda values: dict(Counter(row['candidates'][row['choice']]['kind'] for row in values))
    return result, dict(seed=seed, families=report, compressed_bytes=compressed, retained_estimate=retained,
                        before=kinds(rows), after=kinds(result))


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--selection-output', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0]] + remaining
    original_read = curve.read_shards

    def read(paths, **kwargs):
        rows = original_read(paths, **kwargs)
        if kwargs['partition'] != 'train':
            return rows
        # Fixed parent and read must match the recorded control experiment.
        assert len(rows) == 2048 and sum(map(recruit, rows)) == 98
        selected, report = select(paths, rows, kwargs['seed'], kwargs['format_name'])
        args.selection_output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({key: value for key, value in report.items() if key != 'families'}), flush=True)
        return selected

    with patch.object(curve, 'read_shards', read):
        curve.main()


if __name__ == '__main__':
    main()
