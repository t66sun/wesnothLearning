"""Read-only focal-faction exposure for teacher schedule prefixes; no games."""
import argparse
from collections import Counter
import json
from pathlib import Path

import params
from learning.data import split
from learning.schedule import teacher_jobs


def audit():
    result = {}
    for fmt, total in [('duel', 300), ('ffa4', 600), ('team2v2', 400)]:
        jobs = teacher_jobs('.', ['gpt6astra'], ['baseline'], 'support', 0,
                            20261101, 1000, 'unused', formats=[fmt], count=total)
        rows = [dict(id=j['id'], seat=j['meta']['seat'], factions=j['factions'],
                     focal=j['factions'][j['meta']['seat']-1],
                     scenario=j['scenario_family'], partition=split(j['scenario_family']),
                     map=j['meta']['map']) for j in jobs]
        prefixes = {}
        for count in (12, 24, 32, 48, 60, total):
            prefix = rows[:count]
            prefixes[count] = dict(
                scenarios=len({r['scenario'] for r in prefix}),
                factions={p: dict(Counter(r['focal'] for r in prefix if r['partition'] == p))
                          for p in ('train', 'validation')},
                seats={s: dict(Counter(r['focal'] for r in prefix if r['seat'] == s))
                       for s in range(1, len(jobs[0]['bots'])+1)})
        result[fmt] = dict(prefixes=prefixes, rows=rows,
            first_train_index={f: next((i for i, r in enumerate(rows)
                if r['partition'] == 'train' and r['focal'] == f), None) for f in params.FACTIONS})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(), indent=2)+'\n', encoding='utf-8')
